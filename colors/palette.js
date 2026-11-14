/*
 * House of Colour — Summer palette, rated for Derek (Mid Summer).
 *
 * House of Colour doesn't publish digital color values; the swatches are fabric.
 * Each color has two candidate values, shown side by side on the page:
 *
 *   hex    Measured from RAW photos of Derek's own swatch fan with a ColorChecker in every
 *          frame and a flat-field correction (sRGB, D65). Made with _tools/colors/measure.py;
 *          see _tools/colors/shoots/2026-11-14/ for the setup, per-photo fit and report.
 *   p3     The same measurement in Display P3, used on wide-gamut screens (iPhone).
 *   wheel  Picked from House of Colour's own color wheel graphic (sRGB), mapped to the
 *          swatch numbers by hand (see broox/broox.com#1). null = not on the wheel.
 *
 * rating: 3 = WOW / power colors, 2 = excellent, 1 = significant (accents & patterns)
 * note:   BW = below waist, BLN = best light neutral, BDN = best deep neutral
 */
window.PALETTE = [
  {"n": 1, "name": "Pink Beige", "rating": 1, "hex": "#EBD8CB", "p3": "0.9078 0.8495 0.8035", "note": "BW", "wheel": "#F9ECD9"},
  {"n": 2, "name": "Powder Pink", "rating": 2, "hex": "#EFDDDA", "p3": "0.9243 0.8702 0.8570", "wheel": "#FBF1E9"},
  {"n": 3, "name": "Mushroom", "rating": 2, "hex": "#9C7B73", "p3": "0.5925 0.4877 0.4570", "wheel": "#A58D7B"},
  {"n": 4, "name": "Rose Brown", "rating": 2, "hex": "#684B49", "p3": "0.3902 0.3000 0.2894", "wheel": "#69544A"},
  {"n": 5, "name": "Musk Pink", "rating": 2, "hex": "#AF4551", "p3": "0.6376 0.2984 0.3240", "wheel": "#A84853"},
  {"n": 6, "name": "Dusty Pink", "rating": 2, "hex": "#DBB3AE", "p3": "0.8326 0.7068 0.6869", "wheel": null},
  {"n": 7, "name": "Soft White", "rating": 2, "hex": "#EEECE8", "p3": "0.9309 0.9248 0.9120", "note": "BLN", "wheel": "#FBFDF5"},
  {"n": 8, "name": "French Navy", "rating": 3, "hex": "#213343", "p3": "0.1439 0.1964 0.2563", "note": "BDN", "wheel": "#233A45"},
  {"n": 9, "name": "Dark Blue Grey", "rating": 3, "hex": "#596977", "p3": "0.3605 0.4099 0.4615", "note": "Love!", "wheel": "#697D8A"},
  {"n": 10, "name": "Light Blue Grey", "rating": 2, "hex": "#849AA8", "p3": "0.5337 0.6015 0.6517", "wheel": "#92ACB4"},
  {"n": 11, "name": "Airforce Blue", "rating": 2, "hex": "#284765", "p3": "0.1846 0.2766 0.3874", "wheel": "#2E5273"},
  {"n": 12, "name": "Delph", "rating": 3, "hex": "#375683", "p3": "0.2422 0.3356 0.4986", "wheel": "#3E6799"},
  {"n": 13, "name": "Primrose", "rating": 2, "hex": "#EBE8C1", "p3": "0.9203 0.9093 0.7713", "wheel": "#F7F7C8"},
  {"n": 14, "name": "Powder Blue", "rating": 2, "hex": "#A8C1DC", "p3": "0.6780 0.7545 0.8519", "wheel": "#C4E0F2"},
  {"n": 15, "name": "Sky Blue", "rating": 2, "hex": "#729AC7", "p3": "0.4812 0.5998 0.7633", "wheel": "#86B0DD"},
  {"n": 16, "name": "Cornflower", "rating": 3, "hex": "#186AAD", "p3": "0.2002 0.4084 0.6580", "wheel": "#3D7EC1"},
  {"n": 17, "name": "Hyacinth", "rating": 3, "hex": "#758AC8", "p3": "0.4752 0.5393 0.7670", "wheel": "#7B96CD"},
  {"n": 18, "name": "Lavender", "rating": 2, "hex": "#AA99CB", "p3": "0.6550 0.6042 0.7835", "wheel": "#B7B0D7"},
  {"n": 19, "name": "Sea Green", "rating": 3, "hex": "#04566B", "p3": "0.1412 0.3318 0.4119", "wheel": "#12656F"},
  {"n": 20, "name": "Jade", "rating": 3, "hex": "#1C8580", "p3": "0.2499 0.5120 0.4989", "wheel": "#2C957D"},
  {"n": 21, "name": "Pastel Jade", "rating": 2, "hex": "#5DAE98", "p3": "0.4430 0.6761 0.5991", "wheel": "#70C197"},
  {"n": 22, "name": "Duck Egg", "rating": 2, "hex": "#7CB6C6", "p3": "0.5359 0.7063 0.7694", "wheel": "#87C5D1"},
  {"n": 23, "name": "Pastel Aqua", "rating": 2, "hex": "#B3D1E1", "p3": "0.7255 0.8171 0.8738", "wheel": "#CBEAEC"},
  {"n": 24, "name": "Lilac", "rating": 2, "hex": "#DEC1CE", "p3": "0.8519 0.7594 0.8039", "wheel": "#E7D4E1"},
  {"n": 25, "name": "Smoked Grape", "rating": 2, "hex": "#392E3A", "p3": "0.2175 0.1820 0.2252", "wheel": "#352D3E"},
  {"n": 26, "name": "Plum", "rating": 3, "hex": "#643153", "p3": "0.3647 0.2026 0.3187", "wheel": "#562F54"},
  {"n": 27, "name": "Amethyst", "rating": 3, "hex": "#973B6B", "p3": "0.5496 0.2543 0.4148", "wheel": "#9B4980"},
  {"n": 28, "name": "Cyclamen", "rating": 3, "hex": "#C5728B", "p3": "0.7280 0.4611 0.5442", "wheel": "#C17E9C"},
  {"n": 29, "name": "Clover", "rating": 2, "hex": "#D8889C", "p3": "0.8038 0.5475 0.6132", "wheel": "#D295A7"},
  {"n": 30, "name": "Raspberry", "rating": 3, "hex": "#B72A51", "p3": "0.6616 0.2162 0.3207", "wheel": "#AF2D53"},
  {"n": 31, "name": "Burgundy", "rating": 2, "hex": "#7B2437", "p3": "0.4435 0.1672 0.2179", "wheel": "#812534"},
  {"n": 32, "name": "Cherry", "rating": 2, "hex": "#9C2134", "p3": "0.5626 0.1749 0.2158", "wheel": "#8E1928"},
  {"n": 33, "name": "Coral Red", "rating": 3, "hex": "#DD2F49", "p3": "0.7960 0.2506 0.3027", "wheel": "#D4394D"},
  {"n": 34, "name": "Rose Madder", "rating": 2, "hex": "#B24254", "p3": "0.6475 0.2875 0.3350", "wheel": "#A44659"},
  {"n": 35, "name": "Rose", "rating": 2, "hex": "#EB6A91", "p3": "0.8576 0.4452 0.5662", "wheel": "#E57CA1"},
  {"n": 36, "name": "Pastel Rose", "rating": 1, "hex": "#F3C7CA", "p3": "0.9241 0.7854 0.7927", "wheel": "#F9DBD9"}
];
