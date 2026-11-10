# Swatch color measurement

Turns photos of the House of Colour swatch fan (with a ColorChecker in each frame) into
precise color values for [`/colors`](../../colors/). The underscore folder name keeps this
out of the published site (GitHub Pages/Jekyll skips `_` folders).

## How it works

1. **Decode** each photo to *linear* camera RGB. RAW files (`.ARW`, `.CR2`, `.NEF`, `.DNG`, …)
   go through LibRaw ([rawpy](https://github.com/letmaik/rawpy)) with no white balance,
   tone curve or auto-brightening, at half resolution (2×2 superpixels, so there are no
   demosaicing artifacts).
2. **Flat-field (optional, recommended):** divide by a frame of a blank matte board shot in
   the same light and position, to cancel light fall-off across the frame. Only its
   brightness is used, heavily blurred.
3. **Find the ColorChecker** with
   [colour-checker-detection](https://github.com/colour-science/colour-checker-detection),
   or from 4 corners you give. Works with the Passport 2 and the Classic.
4. **Fit a color correction** from camera RGB to CIE XYZ (D65) with
   [colour-science](https://www.colour-science.org/), using the chart's published values
   (`ColorChecker24 - After November 2014`). The report gives the fit error (ΔE2000) and a
   leave-one-out error, which is an honest estimate for colors that aren't on the chart.
5. **Sample each swatch** (median of the inner 60% of its area), convert to XYZ, and output
   sRGB hex + Display P3, flagging colors outside sRGB. Swatches photographed more than once
   are averaged, and the spread between photos is reported.

Correction methods: `linear` (3×3 matrix, default, robust) or `root-polynomial`
(Finlayson 2015, degree 2; can fit the chart better but may overfit, so compare
the leave-one-out error).

## Shooting

- Shoot RAW. Manual exposure, fixed ISO/aperture/shutter, the same for every frame.
- Soft, even light at an angle to the cards (window light or bounced flash), camera
  pointing straight down. Avoid glare on the fabric.
- The ColorChecker (Classic side of the Passport) **flat, in the same plane and light as the
  swatch card**, fully in frame.
- Check the histogram: the white chart patch and the palest swatches must not clip.
- One extra frame of a blank matte white or grey board filling the frame (the flat-field),
  without moving the camera or light. Reshoot it if the setup changes.

## Usage

```sh
pip install -r requirements.txt

# 1. Correct one photo and write PHOTO.preview.jpg with a pixel grid and the checker patches
#    outlined, to read off swatch coordinates:
python measure.py preview shoot/DSC01234.ARW --flat shoot/DSC01299.ARW -o shoot/

# 2. List each photo and its swatch rectangles in shoot/shots.json (see shots.example.json).
#    Swatch keys are the swatch numbers (1–36). Regions are [x0, y0, x1, y1] or four
#    [x, y] corners, in preview-image pixels. "checker" is "auto" or the 4 corners of
#    the patch grid.

# 3. Measure everything, write shoot/out/report.md + measurements.json + annotated previews:
python measure.py run shoot/shots.json

# 4. When the report looks right, write the values into colors/palette.js:
python measure.py run shoot/shots.json --write-palette
```

`--write-palette` only replaces `hex` and `p3` for the measured swatches (and drops their
`estimated` flag). Names, ratings, notes and wheel values are left as they are.

Non-RAW input: export a 16-bit TIFF with all adjustments off and pass its encoding,
e.g. `"encoding": "srgb"` in the shot (or `--encoding srgb` for `preview`).

Photos and previews are git-ignored; commit `shots.json` and `out/report.md` /
`out/measurements.json` so the numbers can be traced back.

## Tests

```sh
python -m unittest test_measure.py
```

Synthetic photos with a known answer (fake camera, uneven light, noise): the pipeline must
recover the swatch colors to within ΔE 0.3, the flat-field must make a difference, the corner
order of the checker mustn't matter, and repeated shots are averaged. To also test RAW
decoding and checker detection on a real photo, set `MEASURE_TEST_RAW` to a RAW file of a
ColorChecker, e.g. `IMG_1971.CR2` from
[colour-checker-detection-examples-datasets](https://github.com/colour-science/colour-checker-detection-examples-datasets/tree/master/detection).
