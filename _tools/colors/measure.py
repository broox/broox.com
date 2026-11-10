#!/usr/bin/env python3
"""
Measure fabric swatch colors from photos that include a ColorChecker.

Pipeline (per photo):
  1. Decode to *linear* camera RGB. RAW files go through LibRaw (rawpy) with no
     white balance, no tone curve and no auto-brightening; 16-bit TIFF/PNG
     exports are linearized with the --encoding you specify.
  2. Optionally divide by a flat-field frame (a blank matte board shot with the
     same light and camera position) to cancel light fall-off across the frame.
  3. Find the ColorChecker (automatic detection, or 4 corners you give), sample
     its 24 patches and fit a color-correction transform from camera RGB to
     CIE XYZ (D65), using the chart's published reference values.
  4. Sample each swatch patch (median of its inner area), convert it to XYZ and
     then to sRGB hex + Display P3.

Several photos of the same swatch are averaged in XYZ, and their spread is
reported. See README.md for how to shoot and how to use the commands.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore", module="colour")  # noisy optional-dependency warnings

import colour  # noqa: E402
import cv2  # noqa: E402

RAW_EXTENSIONS = {".arw", ".cr2", ".cr3", ".nef", ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw"}
CHECKER_REFERENCE = "ColorChecker24 - After November 2014"  # also what the Passport 2 uses
D65 = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]
CLIP_LEVEL = 0.98  # fraction of the decoded maximum treated as clipped
METHODS = {
    # name: (colour method, kwargs)
    "linear": ("Cheung 2004", {"terms": 3}),
    "root-polynomial": ("Finlayson 2015", {"degree": 2, "root_polynomial_expansion": True}),
}


# --------------------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------------------

def load_linear(path: Path, encoding: str = "linear", half_size: bool = True) -> np.ndarray:
    """Return a float32 HxWx3 image in linear camera (or file) RGB, roughly 0..1."""
    if path.suffix.lower() in RAW_EXTENSIONS:
        import rawpy

        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                half_size=half_size,          # 2x2 superpixels: no demosaicing artifacts
                gamma=(1, 1),                 # linear
                no_auto_bright=True,
                use_camera_wb=False,
                use_auto_wb=False,
                user_wb=[1.0, 1.0, 1.0, 1.0],
                output_color=rawpy.ColorSpace.raw,  # native camera RGB; the CCM does the rest
                output_bps=16,
            )
        return rgb.astype(np.float32) / 65535.0

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED | cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"Could not read {path}")
    if img.ndim == 2:
        img = np.repeat(img[..., None], 3, axis=2)
    img = img[..., :3][..., ::-1]  # BGR -> RGB
    scale = {np.dtype("uint8"): 255.0, np.dtype("uint16"): 65535.0}.get(img.dtype, 1.0)
    img = img.astype(np.float32) / scale
    if encoding == "srgb":
        img = colour.cctf_decoding(img, function="sRGB").astype(np.float32)
    elif encoding.startswith("gamma"):
        img = np.power(np.clip(img, 0, None), float(encoding[5:]))
    elif encoding != "linear":
        raise SystemExit(f"Unknown encoding {encoding!r}")
    return img


def apply_flat_field(img: np.ndarray, flat: np.ndarray) -> np.ndarray:
    """Divide out the light fall-off measured on a blank board.

    Only the brightness of the flat is used (not its color), heavily blurred, so the
    board's own tint and texture don't leak into the measurement.
    """
    if flat.shape != img.shape:
        raise SystemExit(f"Flat-field size {flat.shape[:2]} doesn't match photo {img.shape[:2]}")
    lum = flat.mean(axis=2)
    sigma = max(lum.shape) / 60.0
    lum = cv2.GaussianBlur(lum, (0, 0), sigma)
    lum = lum / np.median(lum)
    if lum.min() < 0.2:
        print("  warning: flat-field has very dark areas; is the board filling the frame?", file=sys.stderr)
    return img / np.clip(lum, 0.05, None)[..., None]


# --------------------------------------------------------------------------------------
# Sampling helpers
# --------------------------------------------------------------------------------------

def quad_from_spec(spec) -> np.ndarray:
    """Accept [x0, y0, x1, y1] or [[x, y] x 4] and return a 4x2 quad."""
    a = np.asarray(spec, dtype=np.float64)
    if a.shape == (4,):
        x0, y0, x1, y1 = a
        return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    if a.shape == (4, 2):
        return a
    raise SystemExit(f"Region must be [x0,y0,x1,y1] or four [x,y] corners, got {spec!r}")


def bilinear(quad: np.ndarray, u: float, v: float) -> np.ndarray:
    """Point at (u, v) in [0,1]^2 inside quad (corners in order q0, q1, q2, q3)."""
    q0, q1, q2, q3 = quad
    return (1 - u) * (1 - v) * q0 + u * (1 - v) * q1 + u * v * q2 + (1 - u) * v * q3


def inner_quad(quad: np.ndarray, inset: float) -> np.ndarray:
    return np.array([bilinear(quad, u, v) for u, v in
                     [(inset, inset), (1 - inset, inset), (1 - inset, 1 - inset), (inset, 1 - inset)]])


@dataclass
class Sample:
    rgb: np.ndarray          # median linear RGB
    spread: float            # relative std of luminance (texture / unevenness)
    clipped: float           # fraction of clipped pixels
    pixels: int
    quad: np.ndarray         # sampled area


def sample_region(img: np.ndarray, quad: np.ndarray, inset: float = 0.2,
                  clip_level: float = CLIP_LEVEL) -> Sample:
    q = inner_quad(quad, inset)
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, np.round(q).astype(np.int32), 1)
    px = img[mask.astype(bool)]
    if len(px) < 25:
        raise SystemExit(f"Sample area {q.round().tolist()} is too small ({len(px)} px)")
    lum = px.mean(axis=1)
    return Sample(
        rgb=np.median(px, axis=0),
        spread=float(lum.std() / max(lum.mean(), 1e-6)),
        clipped=float((px >= clip_level).any(axis=1).mean()),
        pixels=len(px),
        quad=q,
    )


# --------------------------------------------------------------------------------------
# Color checker
# --------------------------------------------------------------------------------------

def checker_reference_XYZ(name: str = CHECKER_REFERENCE) -> tuple[np.ndarray, list[str]]:
    """Reference values of the 24 patches as XYZ, adapted to D65 (Bradford)."""
    cc = colour.CCS_COLOURCHECKERS[name]
    XYZ = colour.xyY_to_XYZ(np.array(list(cc.data.values())))
    XYZ = colour.chromatic_adaptation(XYZ, colour.xy_to_XYZ(cc.illuminant), colour.xy_to_XYZ(D65),
                                      method="Von Kries", transform="Bradford")
    return XYZ, list(cc.data.keys())


def grid_cells(quad: np.ndarray) -> list[np.ndarray]:
    """24 cell quads for a 6x4 grid spanning quad, reading order along its long side."""
    q = np.asarray(quad, dtype=np.float64)
    if np.linalg.norm(q[1] - q[0]) < np.linalg.norm(q[3] - q[0]):
        q = q[[0, 3, 2, 1]]  # make q0->q1 the long (6-patch) side
    cells = []
    for r in range(4):
        for c in range(6):
            cells.append(np.array([bilinear(q, c / 6, r / 4), bilinear(q, (c + 1) / 6, r / 4),
                                   bilinear(q, (c + 1) / 6, (r + 1) / 4), bilinear(q, c / 6, (r + 1) / 4)]))
    return cells


def orientations() -> list[tuple[str, np.ndarray]]:
    """Index permutations of a 4x6 grid that map our reading order onto the chart's."""
    idx = np.arange(24).reshape(4, 6)
    # Which corner the detector (or you) listed first is arbitrary, so try each patch order
    # and keep the one that fits the reference values best; a wrong order fits terribly.
    return [("A", idx.ravel()), ("B", idx[::-1, ::-1].ravel()),
            ("C", idx[:, ::-1].ravel()), ("D", idx[::-1, :].ravel())]


def detect_checker_quad(img: np.ndarray) -> np.ndarray | None:
    """Find the ColorChecker's patch-grid corners with colour-checker-detection."""
    import colour_checker_detection as ccd

    # Detection works best on a roughly neutral, display-like image; a per-channel gain
    # (gray world) and normalization doesn't change where things are.
    gains = img.reshape(-1, 3).mean(axis=0)
    view = img / gains * (0.18 / 1.0)
    view = np.clip(view / max(np.percentile(view, 99.5), 1e-6), 0, 1).astype(np.float32)
    found = ccd.detect_colour_checkers_segmentation(view, additional_data=True)
    if not found:
        return None
    # The detector reports corners in its own resized working frame.
    scale = img.shape[1] / ccd.SETTINGS_SEGMENTATION_COLORCHECKER_CLASSIC["working_width"]
    return np.asarray(found[0].quadrilateral, dtype=np.float64) * scale


@dataclass
class Fit:
    method: str
    orientation: str
    cells: list[np.ndarray]
    samples: list[Sample]
    used: np.ndarray                 # bool mask of patches used in the fit
    ccm: np.ndarray
    delta_e: np.ndarray              # per-patch ΔE2000 after correction
    loo_delta_e: np.ndarray          # leave-one-out ΔE2000 (honest error estimate)
    names: list[str] = field(default_factory=list)

    def to_XYZ(self, rgb: np.ndarray) -> np.ndarray:
        name, kw = METHODS[self.method]
        return colour.characterisation.apply_matrix_colour_correction(
            np.atleast_2d(rgb), self.ccm, method=name, **{k: v for k, v in kw.items() if k != "terms"})


def XYZ_to_Lab(XYZ):
    return colour.XYZ_to_Lab(XYZ, D65)


def delta_e(XYZ_a, XYZ_b):
    return colour.delta_E(XYZ_to_Lab(XYZ_a), XYZ_to_Lab(XYZ_b), method="CIE 2000")


def fit_checker(img: np.ndarray, quad: np.ndarray, method: str, inset: float = 0.25) -> Fit:
    ref_XYZ, names = checker_reference_XYZ()
    cells = grid_cells(quad)
    samples = [sample_region(img, c, inset) for c in cells]
    rgb = np.array([s.rgb for s in samples])
    name, kw = METHODS[method]

    best = None
    for label, perm in orientations():
        # perm[i] = which sampled cell holds reference patch i
        cam = rgb[perm]
        used = np.array([samples[j].clipped < 0.01 for j in perm])
        if used.sum() < 12:
            continue
        ccm = colour.characterisation.matrix_colour_correction(cam[used], ref_XYZ[used], method=name, **kw)
        apply_kw = {k: v for k, v in kw.items() if k != "terms"}
        est = colour.characterisation.apply_matrix_colour_correction(cam, ccm, method=name, **apply_kw)
        de = delta_e(est, ref_XYZ)
        score = float(np.mean(de[used]))
        if best is None or score < best[0]:
            best = (score, label, perm, used, ccm, de)

    if best is None:
        raise SystemExit("Too many checker patches are clipped; lower the exposure.")
    _, label, perm, used, ccm, de = best
    cam = rgb[perm]
    apply_kw = {k: v for k, v in kw.items() if k != "terms"}

    loo = np.full(24, np.nan)
    for i in np.flatnonzero(used):
        keep = used.copy()
        keep[i] = False
        m = colour.characterisation.matrix_colour_correction(cam[keep], ref_XYZ[keep], method=name, **kw)
        est_i = colour.characterisation.apply_matrix_colour_correction(cam[i:i + 1], m, method=name, **apply_kw)
        loo[i] = float(delta_e(est_i, ref_XYZ[i:i + 1])[0])

    return Fit(method, label, [cells[j] for j in perm], [samples[j] for j in perm], used, ccm,
               np.asarray(de), loo, names)


# --------------------------------------------------------------------------------------
# Output colors
# --------------------------------------------------------------------------------------

def XYZ_to_outputs(XYZ: np.ndarray) -> dict:
    """XYZ (D65, perfect white Y=1) -> sRGB hex, Display P3 string, gamut flags."""
    XYZ = np.asarray(XYZ, dtype=np.float64)
    out = {}
    for key, space in (("srgb", "sRGB"), ("p3", "Display P3")):
        lin = colour.XYZ_to_RGB(XYZ, space, apply_cctf_encoding=False)
        out[key + "_in_gamut"] = bool(np.all(lin >= -0.002) and np.all(lin <= 1.002))
        enc = colour.RGB_COLOURSPACES[space].cctf_encoding(np.clip(lin, 0, 1))
        out[key] = enc
    out["hex"] = "#" + "".join(f"{int(round(v * 255)):02X}" for v in out.pop("srgb"))
    out["p3"] = " ".join(f"{v:.4f}" for v in out["p3"])
    return out


def hex_to_XYZ(h: str) -> np.ndarray:
    rgb = np.array([int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    return colour.RGB_to_XYZ(rgb, "sRGB", apply_cctf_decoding=True)


# --------------------------------------------------------------------------------------
# Previews
# --------------------------------------------------------------------------------------

def to_display(img: np.ndarray, fit: Fit | None) -> np.ndarray:
    """Color-corrected (or simply normalized) 8-bit sRGB image for looking at."""
    if fit is not None:
        h, w = img.shape[:2]
        XYZ = fit.to_XYZ(img.reshape(-1, 3)).reshape(h, w, 3)
        out = colour.XYZ_to_RGB(XYZ, "sRGB", apply_cctf_encoding=True)
    else:
        lin = img / max(np.percentile(img, 99.5), 1e-6)
        out = colour.cctf_encoding(np.clip(lin, 0, 1), function="sRGB")
    return (np.clip(out, 0, 1) * 255).round().astype(np.uint8)


def draw_quad(canvas, quad, color, label=None, thickness=2):
    pts = np.round(quad).astype(np.int32)
    cv2.polylines(canvas, [pts], True, color, thickness, cv2.LINE_AA)
    if label is not None:
        c = quad.mean(axis=0)
        scale = max(canvas.shape[1] / 2500.0, 0.5)
        for col, th in (((0, 0, 0), 5), ((255, 255, 255), 2)):
            cv2.putText(canvas, str(label), (int(c[0] - 12 * scale), int(c[1] + 8 * scale)),
                        cv2.FONT_HERSHEY_SIMPLEX, scale, col, th, cv2.LINE_AA)


def draw_grid(canvas, step=100):
    h, w = canvas.shape[:2]
    scale = max(w / 3000.0, 0.4)
    for x in range(0, w, step):
        major = x % (step * 5) == 0
        cv2.line(canvas, (x, 0), (x, h), (255, 255, 0) if major else (120, 120, 0), 1)
        if major:
            cv2.putText(canvas, str(x), (x + 3, int(20 * scale) + 5), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 0), 2)
    for y in range(0, h, step):
        major = y % (step * 5) == 0
        cv2.line(canvas, (0, y), (w, y), (255, 255, 0) if major else (120, 120, 0), 1)
        if major:
            cv2.putText(canvas, str(y), (3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 0), 2)


def save_rgb(path: Path, rgb8: np.ndarray, max_width: int | None = None):
    if max_width and rgb8.shape[1] > max_width:
        f = max_width / rgb8.shape[1]
        rgb8 = cv2.resize(rgb8, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), rgb8[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 92])


# --------------------------------------------------------------------------------------
# Shots
# --------------------------------------------------------------------------------------

@dataclass
class ShotResult:
    photo: str
    fit: Fit
    swatches: dict  # n -> dict(XYZ, sample)


def prepare(photo: Path, flat: Path | None, encoding: str, checker, method: str):
    img = load_linear(photo, encoding)
    if flat is not None:
        img = apply_flat_field(img, load_linear(flat, encoding))
    if checker in (None, "auto"):
        quad = detect_checker_quad(img)
        if quad is None:
            raise SystemExit(f"{photo.name}: couldn't find the ColorChecker automatically. "
                             "Add its 4 patch-grid corners as \"checker\" in the shots file.")
    else:
        quad = quad_from_spec(checker)
    return img, fit_checker(img, quad, method)


def fit_summary(fit: Fit) -> str:
    used = fit.used
    worst = int(np.nanargmax(np.where(used, fit.delta_e, np.nan)))
    return (f"checker fit ({fit.method}): mean ΔE2000 {fit.delta_e[used].mean():.2f}, "
            f"max {fit.delta_e[used].max():.2f} ({fit.names[worst]}); "
            f"leave-one-out mean {np.nanmean(fit.loo_delta_e):.2f}"
            + (f"; {int((~used).sum())} clipped patch(es) skipped" if (~used).any() else ""))


def cmd_preview(args):
    photo = Path(args.photo)
    img, fit = prepare(photo, Path(args.flat) if args.flat else None, args.encoding, args.checker, args.method)
    print(f"{photo.name}: {img.shape[1]}x{img.shape[0]} working pixels")
    print("  " + fit_summary(fit))
    canvas = to_display(img, fit)
    draw_grid(canvas)
    for i, (cell, s) in enumerate(zip(fit.cells, fit.samples)):
        draw_quad(canvas, s.quad, (0, 255, 0) if fit.used[i] else (255, 0, 0), i + 1, 2)
    out = Path(args.out or photo.parent) / f"{photo.stem}.preview.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    save_rgb(out, canvas)
    print(f"  wrote {out}  (coordinates in the shots file use these pixels)")


def parse_palette(path: Path) -> tuple[str, list[dict]]:
    text = path.read_text()
    entries = [json.loads(m.group(1)) for m in re.finditer(r'^\s*(\{"n".*\}),?\s*$', text, re.M)]
    return text, entries


def write_palette(path: Path, results: dict):
    text, _ = parse_palette(path)

    def repl(m):
        e = json.loads(m.group(2))
        r = results.get(e["n"])
        if r:
            e["hex"], e["p3"] = r["hex"], r["p3"]
            e.pop("estimated", None)
        return m.group(1) + json.dumps(e, ensure_ascii=False) + m.group(3)

    path.write_text(re.sub(r'^(\s*)(\{"n".*\})(,?\s*)$', repl, text, flags=re.M))


def cmd_run(args):
    shots_path = Path(args.shots)
    cfg = json.loads(shots_path.read_text())
    base = shots_path.parent
    method = cfg.get("method", args.method)
    out_dir = Path(args.out or base / "out")
    out_dir.mkdir(parents=True, exist_ok=True)

    per_swatch: dict[int, list] = {}
    shot_reports = []
    for shot in cfg["shots"]:
        photo = base / shot["photo"]
        flat = base / shot["flat"] if shot.get("flat") else None
        img, fit = prepare(photo, flat, shot.get("encoding", "linear"), shot.get("checker", "auto"), method)
        print(f"{photo.name}: " + fit_summary(fit))
        shot_reports.append((photo.name, fit))

        canvas = to_display(img, fit)
        for i, s in enumerate(fit.samples):
            draw_quad(canvas, s.quad, (0, 255, 0) if fit.used[i] else (255, 0, 0), None, 2)
        for n, spec in shot.get("swatches", {}).items():
            s = sample_region(img, quad_from_spec(spec), shot.get("inset", 0.2))
            XYZ = fit.to_XYZ(s.rgb)[0]
            per_swatch.setdefault(int(n), []).append({"photo": photo.name, "XYZ": XYZ, "sample": s})
            if s.clipped > 0.01:
                print(f"  warning: swatch {n} has {s.clipped:.0%} clipped pixels; lower the exposure", file=sys.stderr)
            draw_quad(canvas, quad_from_spec(spec), (255, 255, 255), n, 3)
            draw_quad(canvas, s.quad, (0, 0, 0), None, 1)
        save_rgb(out_dir / f"{photo.stem}.annotated.jpg", canvas, max_width=2400)

    palette_path = Path(args.palette) if args.palette else None
    palette = {e["n"]: e for e in parse_palette(palette_path)[1]} if palette_path and palette_path.exists() else {}

    results = {}
    for n in sorted(per_swatch):
        obs = per_swatch[n]
        XYZs = np.array([o["XYZ"] for o in obs])
        XYZ = XYZs.mean(axis=0)
        spread = max((float(delta_e(a, b)) for i, a in enumerate(XYZs) for b in XYZs[i + 1:]), default=0.0)
        r = {"n": n, "XYZ": XYZ.round(5).tolist(), "Lab": XYZ_to_Lab(XYZ).round(2).tolist(),
             "shots": len(obs), "shot_spread_dE": round(spread, 2),
             "texture": round(max(o["sample"].spread for o in obs), 3), **XYZ_to_outputs(XYZ)}
        p = palette.get(n)
        if p:
            r["name"] = p["name"]
            r["dE_vs_current"] = round(float(delta_e(XYZ, hex_to_XYZ(p["hex"]))), 2)
            if p.get("wheel"):
                r["dE_vs_wheel"] = round(float(delta_e(XYZ, hex_to_XYZ(p["wheel"]))), 2)
        results[n] = r

    (out_dir / "measurements.json").write_text(json.dumps(
        {"method": method, "checker_reference": CHECKER_REFERENCE,
         "shots": [{"photo": name, "patch_order": f.orientation,
                    "checker_dE_mean": round(float(f.delta_e[f.used].mean()), 3),
                    "checker_dE_max": round(float(f.delta_e[f.used].max()), 3),
                    "checker_dE_leave_one_out": round(float(np.nanmean(f.loo_delta_e)), 3)}
                   for name, f in shot_reports],
         "swatches": list(results.values())}, indent=1, ensure_ascii=False))
    (out_dir / "report.md").write_text(render_report(method, shot_reports, results, palette))
    print(f"wrote {out_dir / 'report.md'} and {out_dir / 'measurements.json'}")

    if palette_path and palette:
        missing = sorted(set(palette) - set(results))
        if missing:
            print(f"note: {len(missing)} swatch(es) not measured (see report); they keep their current values")
        if args.write_palette:
            write_palette(palette_path, results)
            print(f"updated {palette_path}")


def render_report(method, shot_reports, results, palette) -> str:
    lines = ["# Swatch measurements", "",
             f"Correction: `{method}` fit to the ColorChecker ({CHECKER_REFERENCE}), output relative to D65.",
             "", "## Checker fit per photo", "",
             "ΔE2000 between the corrected checker patches and their published values. "
             "Under 1 is excellent, under 2 is very good. Leave-one-out refits without each patch, "
             "so it's an honest estimate of the error on colors that aren't on the chart.", "",
             "| Photo | Mean ΔE | Max ΔE | Leave-one-out ΔE |", "|---|---|---|---|"]
    for name, f in shot_reports:
        lines.append(f"| {name} | {f.delta_e[f.used].mean():.2f} | "
                     f"{f.delta_e[f.used].max():.2f} | {np.nanmean(f.loo_delta_e):.2f} |")
    lines += ["", "## Swatches", "",
              "*Shots* = photos it was measured in; *spread* = largest ΔE between those photos; "
              "*vs current* / *vs wheel* = ΔE to the values on the page now.", "",
              "| # | Name | Hex | Display P3 | In sRGB? | Shots | Spread | vs current | vs wheel |",
              "|---|---|---|---|---|---|---|---|---|"]
    for n, r in results.items():
        lines.append(f"| {n} | {r.get('name', '')} | `{r['hex']}` | `{r['p3']}` | "
                     f"{'yes' if r['srgb_in_gamut'] else '**no**'} | {r['shots']} | {r['shot_spread_dE']:.2f} | "
                     f"{r.get('dE_vs_current', '–')} | {r.get('dE_vs_wheel', '–')} |")
    missing = sorted(set(palette) - set(results))
    if missing:
        lines += ["", "Not measured: " + ", ".join(f"{n} {palette[n]['name']}" for n in missing)]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("preview", help="correct one photo and write a gridded preview for marking swatches")
    p.add_argument("photo")
    p.add_argument("--flat", help="flat-field frame (blank board, same light and position)")
    p.add_argument("--encoding", default="linear", help="for TIFF/PNG input: linear, srgb, gamma1.8, gamma2.2")
    p.add_argument("--checker", type=lambda s: s if s == "auto" else json.loads(s), default="auto",
                   help='"auto" (default) or JSON corners [[x,y],[x,y],[x,y],[x,y]] of the patch grid')
    p.add_argument("--method", choices=METHODS, default="linear")
    p.add_argument("-o", "--out", help="output directory (default: next to the photo)")
    p.set_defaults(func=cmd_preview)

    r = sub.add_parser("run", help="measure all swatches listed in a shots file")
    r.add_argument("shots", help="shots JSON file (paths inside are relative to it)")
    r.add_argument("--method", choices=METHODS, default="linear")
    r.add_argument("--palette", default=str(Path(__file__).resolve().parents[2] / "colors" / "palette.js"),
                   help="palette.js to compare against (and update with --write-palette)")
    r.add_argument("--write-palette", action="store_true", help="write the measured hex/p3 into the palette")
    r.add_argument("-o", "--out", help="output directory (default: out/ next to the shots file)")
    r.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
