"""
End-to-end tests for measure.py on synthetic photos with a known answer.

A fake camera (an arbitrary 3x3 response, no white balance, uneven light across
the frame, sensor noise) photographs a ColorChecker plus a few swatches whose
true colors we know. The pipeline must recover those colors.

    python -m unittest test_measure.py

Optional real-photo check: set MEASURE_TEST_RAW to a RAW file containing a
ColorChecker (e.g. IMG_1971.CR2 from colour-science's
colour-checker-detection-examples-datasets) to test RAW decoding + detection.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import measure  # noqa: E402

import colour  # noqa: E402
import cv2  # noqa: E402

# XYZ -> camera RGB. Deliberately unlike sRGB, with unequal channel gains (no white balance).
CAMERA = np.array([[0.70, 0.45, -0.20],
                   [-0.35, 1.25, 0.10],
                   [0.03, -0.08, 0.60]])

# True swatch colors: an in-gamut color, a light neutral-ish one, and a red outside sRGB.
SWATCHES = {
    7: colour.RGB_to_XYZ(np.array([0.96, 0.96, 0.90]), "Display P3", apply_cctf_decoding=True),
    16: colour.RGB_to_XYZ(np.array([0.21, 0.47, 0.75]), "sRGB", apply_cctf_decoding=True),
    33: colour.RGB_to_XYZ(np.array([0.87, 0.16, 0.22]), "Display P3", apply_cctf_decoding=True),
}

W, H = 1500, 1000
CELL, GAP = 100, 12                       # checker cell size and gap between patches
GRID_X0, GRID_Y0 = 150, 250               # top-left of the 6x4 patch grid
SWATCH_RECTS = {7: [1000, 200, 1300, 380], 16: [1000, 420, 1300, 600], 33: [1000, 640, 1300, 820]}


def light(xx, yy):
    """Uneven window light: 45% brighter on one side, a little top-to-bottom too."""
    return 0.80 + 0.45 * xx / W + 0.10 * yy / H


def render(include_scene=True, seed=0):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    XYZ = np.empty((H, W, 3))
    XYZ[:] = colour.xy_to_XYZ(measure.D65) * 0.30          # grey board
    if include_scene:
        ref, _ = measure.checker_reference_XYZ()
        XYZ[GRID_Y0 - 30:GRID_Y0 + 4 * CELL + 30, GRID_X0 - 30:GRID_X0 + 6 * CELL + 30] = \
            colour.xy_to_XYZ(measure.D65) * 0.03            # dark chart body
        for i, v in enumerate(ref):
            r, c = divmod(i, 6)
            y0, x0 = GRID_Y0 + r * CELL + GAP, GRID_X0 + c * CELL + GAP
            XYZ[y0:y0 + CELL - 2 * GAP, x0:x0 + CELL - 2 * GAP] = v
        for n, (x0, y0, x1, y1) in SWATCH_RECTS.items():
            XYZ[y0:y1, x0:x1] = SWATCHES[n]
    cam = XYZ @ CAMERA.T * light(xx, yy)[..., None] * 0.55
    cam += np.random.default_rng(seed).normal(0, 0.002, cam.shape)
    return np.clip(cam, 0, 1)


def write_tiff16(path, rgb):
    cv2.imwrite(str(path), (rgb[..., ::-1] * 65535).round().astype(np.uint16))


def checker_corners():
    return [[GRID_X0, GRID_Y0], [GRID_X0 + 6 * CELL, GRID_Y0],
            [GRID_X0 + 6 * CELL, GRID_Y0 + 4 * CELL], [GRID_X0, GRID_Y0 + 4 * CELL]]


PALETTE = """window.PALETTE = [
  {"n": 7, "name": "Soft White", "rating": 2, "hex": "#F5F5E4", "p3": "0.9608 0.9608 0.9021", "note": "BLN", "wheel": "#FBFDF5"},
  {"n": 16, "name": "Cornflower", "rating": 3, "hex": "#3577BE", "p3": "0.2752 0.4601 0.7252", "wheel": "#3D7EC1"},
  {"n": 33, "name": "Coral Red", "rating": 3, "hex": "#F3002D", "p3": "0.8748 0.1553 0.2171", "wheel": "#D4394D"},
  {"n": 34, "name": "Rose Madder", "rating": 2, "hex": "#C2305F", "p3": "0.7007 0.2387 0.3743", "estimated": true, "wheel": "#A44659"}
];
"""


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_tiff16(self.tmp / "shot.tif", render(True))
        write_tiff16(self.tmp / "flat.tif", render(False, seed=1))
        (self.tmp / "palette.js").write_text(PALETTE)

    def run_shots(self, shot):
        (self.tmp / "shots.json").write_text(json.dumps({"shots": [shot]}))
        measure.main(["run", str(self.tmp / "shots.json"), "--palette", str(self.tmp / "palette.js"),
                      "--write-palette", "-o", str(self.tmp / "out")])
        return json.loads((self.tmp / "out" / "measurements.json").read_text())

    def errors(self, data):
        return {s["n"]: float(measure.delta_e(np.array(s["XYZ"]), SWATCHES[s["n"]])) for s in data["swatches"]}

    def base_shot(self, **kw):
        shot = {"photo": "shot.tif", "flat": "flat.tif", "checker": checker_corners(),
                "swatches": {str(n): r for n, r in SWATCH_RECTS.items()}}
        shot.update(kw)
        return shot

    def test_recovers_known_colors(self):
        data = self.run_shots(self.base_shot())
        self.assertLess(data["shots"][0]["checker_dE_mean"], 0.1)
        for n, de in self.errors(data).items():
            self.assertLess(de, 0.3, f"swatch {n} off by ΔE {de:.2f}")

        by_n = {s["n"]: s for s in data["swatches"]}
        self.assertFalse(by_n[33]["srgb_in_gamut"], "the P3 red should be flagged as outside sRGB")
        self.assertTrue(by_n[16]["srgb_in_gamut"])

        text = (self.tmp / "palette.js").read_text()
        entries = {e["n"]: e for e in measure.parse_palette(self.tmp / "palette.js")[1]}
        self.assertEqual(entries[16]["hex"], by_n[16]["hex"])
        self.assertEqual(entries[16]["wheel"], "#3D7EC1", "other fields are kept")
        self.assertTrue(entries[34].get("estimated"), "unmeasured colors are left alone")
        self.assertIn('"note": "BLN"', text)

    def test_flat_field_matters(self):
        with_flat = max(self.errors(self.run_shots(self.base_shot())).values())
        without = max(self.errors(self.run_shots(self.base_shot(flat=None))).values())
        self.assertGreater(without, with_flat * 3,
                           f"uneven light should hurt without a flat-field ({without:.2f} vs {with_flat:.2f})")

    def test_corner_order_does_not_matter(self):
        corners = checker_corners()
        rotated = corners[2:] + corners[:2]          # start from the opposite corner
        data = self.run_shots(self.base_shot(checker=rotated))
        self.assertLess(data["shots"][0]["checker_dE_mean"], 0.1)

    def test_averages_repeated_shots(self):
        write_tiff16(self.tmp / "shot2.tif", render(True, seed=7))
        shots = [self.base_shot(), self.base_shot(photo="shot2.tif")]
        (self.tmp / "shots.json").write_text(json.dumps({"shots": shots}))
        measure.main(["run", str(self.tmp / "shots.json"), "--palette", str(self.tmp / "palette.js"),
                      "-o", str(self.tmp / "out")])
        data = json.loads((self.tmp / "out" / "measurements.json").read_text())
        self.assertTrue(all(s["shots"] == 2 for s in data["swatches"]))
        self.assertTrue(all(s["shot_spread_dE"] < 0.5 for s in data["swatches"]))


@unittest.skipUnless(os.environ.get("MEASURE_TEST_RAW"), "set MEASURE_TEST_RAW to a RAW photo of a ColorChecker")
class RealRaw(unittest.TestCase):
    def test_detects_and_fits(self):
        path = Path(os.environ["MEASURE_TEST_RAW"])
        img, fit = measure.prepare(path, None, "linear", "auto", "linear")
        self.assertGreater(img.shape[1], 1000)
        self.assertLess(fit.delta_e[fit.used].mean(), 4.0)


if __name__ == "__main__":
    unittest.main()
