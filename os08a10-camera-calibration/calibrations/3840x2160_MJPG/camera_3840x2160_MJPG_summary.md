# Calibration 3840x2160_MJPG  -  grade **PASS**

- created: 2026-11-25T15:11:22  |  OpenCV 4.8.0  |  model: `brown_k1k2`
- views: 132  |  points: 12891
- reprojection RMS **0.8606 px**  (mean 0.6228, p95 1.8043, max 6.7840)
- bootstrap undistortion uncertainty: mean 0.8827 px, max 2.2530 px

| param | value | 1-sigma |
|---|---|---|
| fx | 3530.9091 | 0.5279 |
| fy | 3531.7220 | 0.5322 |
| cx | 1930.7960 | 0.8074 |
| cy | 1105.0237 | 0.6743 |
| k1 | -0.16994276 | 0.00044444 |
| k2 | 0.06450518 | 0.00169008 |
| p1 | 0.00001737 | 0.00003295 |
| p2 | -0.00105832 | 0.00004100 |
| k3 | 0.00000000 | 0.00000000 |

- FOV H/V/D: 59.49 / 34.50 / 67.27 deg
- max distortion displacement: 152.79 px
- principal point offset from centre: (11.30, 25.52) px
- coverage: 94% of 16x9 cells; tilt range 2-67 deg
- focal length (assuming full-sensor scaled mode): 7.062 mm
- **held-out metric accuracy** (views never used to fit the intrinsics, board reconstructed in mm): RMS 0.159 mm, p95 0.311 mm, max 1.639 mm at median distance 593 mm
- board pitch used: X 25.0000 mm, Y 25.0413 mm  (print Y/X ratio estimated from images (+0.165%); absolute scale nominal)

## Metric resolution (1 px at distance Z on a fronto-parallel plane)

| Z (mm) | mm/px X | mm/px Y | field of view (mm) |
|---|---|---|---|
| 150 | 0.0425 | 0.0425 | 163 x 92 |
| 250 | 0.0708 | 0.0708 | 272 x 153 |
| 400 | 0.1133 | 0.1133 | 435 x 245 |
| 600 | 0.1699 | 0.1699 | 653 x 367 |
| 800 | 0.2266 | 0.2265 | 870 x 489 |
| 1000 | 0.2832 | 0.2831 | 1088 x 612 |
| 1500 | 0.4248 | 0.4247 | 1631 x 917 |

## Issues

- PASS: measured accuracy 0.159 mm RMS, 95% within 0.311 mm (target 0.5 mm) on held-out views at ~593 mm
- note: RMS reprojection 0.861 px (> 0.70)
- note: few points in image corner regions ['top_right', 'bottom_left', 'bottom_right'] - distortion is extrapolated there
- note: bootstrap undistortion uncertainty max 2.25 px

## Rejected

- {"view": "img_012_mean.png", "type": "points", "n": 2, "ids": [89, 90], "max_px": 5.281569132732077, "threshold_px": 4.827113162587065}
- {"view": "img_018_mean.png", "type": "points", "n": 34, "ids": [0, 1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 22, 23, 24, 25, 26, 27, 28, 36, 37, 38, 39, 50, 51, 98, 99, 100, 110, 111, 112, 113, 114, 115, 116], "max_px": 12.150006116743418, "threshold_px": 4.827113162587065}
- {"view": "img_020_mean.png", "type": "points", "n": 1, "ids": [12], "max_px": 4.827818794798178, "threshold_px": 4.827113162587065}
- {"view": "img_033_mean.png", "type": "points", "n": 5, "ids": [10, 11, 22, 51, 63], "max_px": 10.483309640540275, "threshold_px": 4.827113162587065}
- {"view": "img_034_mean.png", "type": "points", "n": 2, "ids": [23, 51], "max_px": 7.335818863196493, "threshold_px": 4.827113162587065}
- {"view": "img_037_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 6.783722748646626, "threshold_px": 4.827113162587065}
- {"view": "img_038_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 6.286259695491664, "threshold_px": 4.827113162587065}
- {"view": "img_039_mean.png", "type": "points", "n": 3, "ids": [38, 51, 60], "max_px": 7.600550133864518, "threshold_px": 4.827113162587065}
- {"view": "img_041_mean.png", "type": "points", "n": 2, "ids": [9, 116], "max_px": 12.6719603459734, "threshold_px": 4.827113162587065}
- {"view": "img_042_mean.png", "type": "points", "n": 6, "ids": [1, 9, 12, 38, 103, 116], "max_px": 17.97034672397351, "threshold_px": 4.827113162587065}
- {"view": "img_043_mean.png", "type": "points", "n": 2, "ids": [10, 116], "max_px": 15.93264755240243, "threshold_px": 4.827113162587065}
- {"view": "img_044_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 7.01467416269903, "threshold_px": 4.827113162587065}
- {"view": "img_045_mean.png", "type": "points", "n": 3, "ids": [10, 102, 103], "max_px": 8.509095690395863, "threshold_px": 4.827113162587065}
- {"view": "img_046_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 5.707821130558346, "threshold_px": 4.827113162587065}
- {"view": "img_047_mean.png", "type": "points", "n": 2, "ids": [10, 35], "max_px": 5.233340894225714, "threshold_px": 4.827113162587065}
- {"view": "img_062_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 7.619489341647406, "threshold_px": 4.827113162587065}
- {"view": "img_063_mean.png", "type": "points", "n": 2, "ids": [13, 115], "max_px": 10.211027316015262, "threshold_px": 4.827113162587065}
- {"view": "img_064_mean.png", "type": "points", "n": 2, "ids": [10, 102], "max_px": 7.962762829951919, "threshold_px": 4.827113162587065}
- {"view": "img_065_mean.png", "type": "points", "n": 3, "ids": [10, 91, 101], "max_px": 7.799221619559028, "threshold_px": 4.827113162587065}
- {"view": "img_066_mean.png", "type": "points", "n": 4, "ids": [10, 23, 101, 114], "max_px": 7.862313561729681, "threshold_px": 4.827113162587065}
- {"view": "img_070_mean.png", "type": "points", "n": 1, "ids": [104], "max_px": 5.216298142357865, "threshold_px": 4.827113162587065}
- {"view": "img_073_mean.png", "type": "points", "n": 2, "ids": [25, 47], "max_px": 5.353073363293367, "threshold_px": 4.827113162587065}
- {"view": "img_074_mean.png", "type": "points", "n": 2, "ids": [51, 101], "max_px": 5.266851677493729, "threshold_px": 4.827113162587065}
- {"view": "img_075_mean.png", "type": "points", "n": 1, "ids": [9], "max_px": 5.967901139898737, "threshold_px": 4.827113162587065}
- {"view": "img_077_mean.png", "type": "points", "n": 1, "ids": [38], "max_px": 8.761256988634145, "threshold_px": 4.827113162587065}
- {"view": "img_078_mean.png", "type": "points", "n": 1, "ids": [0], "max_px": 8.328334638907172, "threshold_px": 4.827113162587065}
- {"view": "img_079_mean.png", "type": "points", "n": 7, "ids": [0, 13, 26, 101, 110, 115, 116], "max_px": 15.898044799689222, "threshold_px": 4.827113162587065}
- {"view": "img_080_mean.png", "type": "points", "n": 1, "ids": [116], "max_px": 16.06796328880073, "threshold_px": 4.827113162587065}
- {"view": "img_083_mean.png", "type": "points", "n": 1, "ids": [0], "max_px": 9.303120053773991, "threshold_px": 4.827113162587065}
- {"view": "img_084_mean.png", "type": "points", "n": 1, "ids": [0], "max_px": 8.073098167674145, "threshold_px": 4.827113162587065}
- {"view": "img_085_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 4.937378834889707, "threshold_px": 4.827113162587065}
- {"view": "img_089_mean.png", "type": "points", "n": 4, "ids": [10, 11, 25, 38], "max_px": 15.322216577273432, "threshold_px": 4.827113162587065}
- {"view": "img_094_mean.png", "type": "points", "n": 2, "ids": [115, 116], "max_px": 10.627371926651282, "threshold_px": 4.827113162587065}
- {"view": "img_096_mean.png", "type": "points", "n": 1, "ids": [104], "max_px": 7.432850542228233, "threshold_px": 4.827113162587065}
- {"view": "img_097_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 6.7027554553635875, "threshold_px": 4.827113162587065}
- {"view": "img_098_mean.png", "type": "points", "n": 2, "ids": [101, 102], "max_px": 7.953411311225439, "threshold_px": 4.827113162587065}
- {"view": "img_099_mean.png", "type": "points", "n": 1, "ids": [101], "max_px": 4.829869238852977, "threshold_px": 4.827113162587065}
- {"view": "img_100_mean.png", "type": "points", "n": 2, "ids": [101, 102], "max_px": 7.6250674441204005, "threshold_px": 4.827113162587065}
- {"view": "img_102_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 8.825012163644136, "threshold_px": 4.827113162587065}
- {"view": "img_103_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 7.7203718808681625, "threshold_px": 4.827113162587065}
- {"view": "img_104_mean.png", "type": "points", "n": 5, "ids": [10, 22, 47, 59, 64], "max_px": 10.328275576093095, "threshold_px": 4.827113162587065}
- {"view": "img_105_mean.png", "type": "points", "n": 1, "ids": [104], "max_px": 4.948715758396448, "threshold_px": 4.827113162587065}
- {"view": "img_106_mean.png", "type": "points", "n": 1, "ids": [90], "max_px": 5.575596079700647, "threshold_px": 4.827113162587065}
- {"view": "img_107_mean.png", "type": "points", "n": 3, "ids": [90, 102, 114], "max_px": 6.798075793478895, "threshold_px": 4.827113162587065}
- {"view": "img_108_mean.png", "type": "points", "n": 19, "ids": [30, 31, 32, 33, 34, 35, 36, 37, 47, 48, 88, 89, 90, 100, 103, 104, 111, 112, 113], "max_px": 9.415717788059437, "threshold_px": 4.827113162587065}
- {"view": "img_109_mean.png", "type": "points", "n": 1, "ids": [35], "max_px": 5.144275974271394, "threshold_px": 4.827113162587065}
- {"view": "img_110_mean.png", "type": "points", "n": 1, "ids": [116], "max_px": 7.468618267402928, "threshold_px": 4.827113162587065}
- {"view": "img_112_mean.png", "type": "points", "n": 27, "ids": [15, 30, 31, 32, 33, 34, 36, 37, 38, 44, 45, 46, 65, 77, 78, 79, 88, 91, 92, 99, 100, 104, 105, 110, 111, 112, 116], "max_px": 17.835668599323604, "threshold_px": 4.827113162587065}
- {"view": "img_113_mean.png", "type": "points", "n": 47, "ids": [13, 14, 15, 16, 17, 18, 25, 26, 27, 28, 29, 30, 31, 32, 33, 38, 39, 40, 41, 42, 43, 44, 45, 51, 64, 76, 77, 78, 79, 80, 87, 88, 91, 92, 93, 94, 95, 96, 99, 100, 104, 105, 106, 107, 108, 109, 112], "max_px": 12.441704084737363, "threshold_px": 4.827113162587065}
- {"view": "img_115_mean.png", "type": "points", "n": 1, "ids": [90], "max_px": 5.170840640518865, "threshold_px": 4.827113162587065}
- {"view": "img_116_mean.png", "type": "points", "n": 8, "ids": [8, 10, 23, 35, 78, 91, 92, 93], "max_px": 6.08097756479779, "threshold_px": 4.827113162587065}
- {"view": "img_119_mean.png", "type": "points", "n": 1, "ids": [90], "max_px": 5.5378840920374675, "threshold_px": 4.827113162587065}
- {"view": "img_120_mean.png", "type": "points", "n": 7, "ids": [0, 1, 2, 3, 13, 23, 90], "max_px": 6.308329782786839, "threshold_px": 4.827113162587065}
- {"view": "img_121_mean.png", "type": "points", "n": 2, "ids": [0, 101], "max_px": 8.773911992945465, "threshold_px": 4.827113162587065}
- {"view": "img_122_mean.png", "type": "points", "n": 3, "ids": [0, 101, 102], "max_px": 9.67117744714091, "threshold_px": 4.827113162587065}
- {"view": "img_123_mean.png", "type": "points", "n": 4, "ids": [0, 13, 26, 116], "max_px": 13.499783652141394, "threshold_px": 4.827113162587065}
- {"view": "img_124_mean.png", "type": "points", "n": 1, "ids": [116], "max_px": 15.74963655228274, "threshold_px": 4.827113162587065}
- {"view": "img_126_mean.png", "type": "points", "n": 2, "ids": [12, 25], "max_px": 17.330739884168786, "threshold_px": 4.827113162587065}
- {"view": "img_127_mean.png", "type": "points", "n": 6, "ids": [8, 9, 38, 51, 64, 77], "max_px": 16.934733269513117, "threshold_px": 4.827113162587065}
- {"view": "img_128_mean.png", "type": "points", "n": 6, "ids": [12, 25, 38, 51, 77, 101], "max_px": 13.373347779070151, "threshold_px": 4.827113162587065}
- {"view": "img_129_mean.png", "type": "points", "n": 5, "ids": [8, 38, 51, 64, 77], "max_px": 13.918222692042285, "threshold_px": 4.827113162587065}
- {"view": "img_130_mean.png", "type": "points", "n": 4, "ids": [9, 12, 38, 101], "max_px": 14.981143587051209, "threshold_px": 4.827113162587065}
- {"view": "img_132_mean.png", "type": "points", "n": 4, "ids": [9, 12, 25, 116], "max_px": 10.793143410214412, "threshold_px": 4.827113162587065}
- {"view": "img_113_mean.png", "type": "view", "rms_px": 5.526150084300345, "threshold_px": 3.6056066090236962}
- {"view": "img_012_mean.png", "type": "points", "n": 3, "ids": [77, 88, 100], "max_px": 4.835375938778974, "threshold_px": 4.370026793374387}
- {"view": "img_018_mean.png", "type": "points", "n": 6, "ids": [21, 34, 35, 49, 63, 64], "max_px": 6.6006727100914855, "threshold_px": 4.370026793374387}
- {"view": "img_020_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 4.424429728707342, "threshold_px": 4.370026793374387}
- {"view": "img_033_mean.png", "type": "points", "n": 1, "ids": [8], "max_px": 5.359376596676197, "threshold_px": 4.370026793374387}
- {"view": "img_035_mean.png", "type": "points", "n": 1, "ids": [36], "max_px": 4.578475641549481, "threshold_px": 4.370026793374387}
- {"view": "img_036_mean.png", "type": "points", "n": 1, "ids": [8], "max_px": 4.3770460166662986, "threshold_px": 4.370026793374387}
- {"view": "img_039_mean.png", "type": "points", "n": 1, "ids": [104], "max_px": 4.381411679791606, "threshold_px": 4.370026793374387}
- {"view": "img_042_mean.png", "type": "points", "n": 2, "ids": [101, 114], "max_px": 5.581190173080685, "threshold_px": 4.370026793374387}
- {"view": "img_045_mean.png", "type": "points", "n": 2, "ids": [48, 59], "max_px": 4.645680279512889, "threshold_px": 4.370026793374387}
- {"view": "img_047_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 4.854531151517837, "threshold_px": 4.370026793374387}
- {"view": "img_048_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 4.519634820335861, "threshold_px": 4.370026793374387}
- {"view": "img_055_mean.png", "type": "points", "n": 2, "ids": [10, 116], "max_px": 4.631947413247424, "threshold_px": 4.370026793374387}
- {"view": "img_062_mean.png", "type": "points", "n": 3, "ids": [48, 101, 115], "max_px": 4.941031886257876, "threshold_px": 4.370026793374387}
- {"view": "img_063_mean.png", "type": "points", "n": 3, "ids": [1, 101, 114], "max_px": 4.681995736483956, "threshold_px": 4.370026793374387}
- {"view": "img_064_mean.png", "type": "points", "n": 2, "ids": [59, 60], "max_px": 4.858016768549745, "threshold_px": 4.370026793374387}
- {"view": "img_066_mean.png", "type": "points", "n": 1, "ids": [108], "max_px": 4.739508472196712, "threshold_px": 4.370026793374387}
- {"view": "img_069_mean.png", "type": "points", "n": 1, "ids": [104], "max_px": 4.63690617075433, "threshold_px": 4.370026793374387}
- {"view": "img_073_mean.png", "type": "points", "n": 4, "ids": [37, 48, 59, 60], "max_px": 4.501768533001309, "threshold_px": 4.370026793374387}
- {"view": "img_074_mean.png", "type": "points", "n": 3, "ids": [8, 11, 60], "max_px": 4.717005146590546, "threshold_px": 4.370026793374387}
- {"view": "img_075_mean.png", "type": "points", "n": 3, "ids": [8, 22, 101], "max_px": 4.7080859922706635, "threshold_px": 4.370026793374387}
- {"view": "img_076_mean.png", "type": "points", "n": 2, "ids": [8, 22], "max_px": 4.572326811474316, "threshold_px": 4.370026793374387}
- {"view": "img_078_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 4.5418649794782056, "threshold_px": 4.370026793374387}
- {"view": "img_083_mean.png", "type": "points", "n": 1, "ids": [101], "max_px": 4.441213596687966, "threshold_px": 4.370026793374387}
- {"view": "img_084_mean.png", "type": "points", "n": 2, "ids": [101, 115], "max_px": 4.665258265678889, "threshold_px": 4.370026793374387}
- {"view": "img_094_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 5.808878299932009, "threshold_px": 4.370026793374387}
- {"view": "img_095_mean.png", "type": "points", "n": 1, "ids": [15], "max_px": 4.471095836433809, "threshold_px": 4.370026793374387}
- {"view": "img_097_mean.png", "type": "points", "n": 1, "ids": [59], "max_px": 4.473864481843468, "threshold_px": 4.370026793374387}
- {"view": "img_102_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 4.649473544891559, "threshold_px": 4.370026793374387}
- {"view": "img_103_mean.png", "type": "points", "n": 1, "ids": [22], "max_px": 4.424617113059626, "threshold_px": 4.370026793374387}
- {"view": "img_104_mean.png", "type": "points", "n": 2, "ids": [8, 36], "max_px": 5.444071800110142, "threshold_px": 4.370026793374387}
- {"view": "img_107_mean.png", "type": "points", "n": 1, "ids": [101], "max_px": 4.809586324935363, "threshold_px": 4.370026793374387}
- {"view": "img_108_mean.png", "type": "points", "n": 6, "ids": [29, 38, 45, 77, 98, 99], "max_px": 5.681829807275294, "threshold_px": 4.370026793374387}
- {"view": "img_112_mean.png", "type": "points", "n": 3, "ids": [43, 76, 87], "max_px": 4.98201005255461, "threshold_px": 4.370026793374387}
- {"view": "img_115_mean.png", "type": "points", "n": 1, "ids": [102], "max_px": 4.544838842053902, "threshold_px": 4.370026793374387}
- {"view": "img_116_mean.png", "type": "points", "n": 5, "ids": [65, 79, 80, 94, 95], "max_px": 5.620123829742412, "threshold_px": 4.370026793374387}
- {"view": "img_120_mean.png", "type": "points", "n": 3, "ids": [14, 15, 16], "max_px": 4.887559265634471, "threshold_px": 4.370026793374387}
- {"view": "img_121_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 4.678866000738337, "threshold_px": 4.370026793374387}
- {"view": "img_122_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 4.610897416424575, "threshold_px": 4.370026793374387}
- {"view": "img_124_mean.png", "type": "points", "n": 1, "ids": [101], "max_px": 4.732435316528097, "threshold_px": 4.370026793374387}
- {"view": "img_127_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 6.445122500866266, "threshold_px": 4.370026793374387}
- {"view": "img_129_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 6.2384613144003955, "threshold_px": 4.370026793374387}
- {"view": "img_130_mean.png", "type": "points", "n": 1, "ids": [8], "max_px": 4.610531556999059, "threshold_px": 4.370026793374387}
- {"view": "img_132_mean.png", "type": "points", "n": 1, "ids": [22], "max_px": 4.408938254303464, "threshold_px": 4.370026793374387}
- {"view": "img_012_mean.png", "type": "points", "n": 1, "ids": [76], "max_px": 4.386538002028171, "threshold_px": 4.268467001377448}
- {"view": "img_018_mean.png", "type": "points", "n": 3, "ids": [7, 48, 77], "max_px": 5.012217985516211, "threshold_px": 4.268467001377448}
- {"view": "img_020_mean.png", "type": "points", "n": 2, "ids": [25, 104], "max_px": 4.444282283196035, "threshold_px": 4.268467001377448}
- {"view": "img_035_mean.png", "type": "points", "n": 1, "ids": [49], "max_px": 4.429632005948722, "threshold_px": 4.268467001377448}
- {"view": "img_036_mean.png", "type": "points", "n": 1, "ids": [22], "max_px": 4.508997783194379, "threshold_px": 4.268467001377448}
- {"view": "img_055_mean.png", "type": "points", "n": 1, "ids": [115], "max_px": 4.353765892309756, "threshold_px": 4.268467001377448}
- {"view": "img_061_mean.png", "type": "points", "n": 2, "ids": [10, 102], "max_px": 4.319329409870814, "threshold_px": 4.268467001377448}
- {"view": "img_063_mean.png", "type": "points", "n": 1, "ids": [116], "max_px": 4.4926260899684936, "threshold_px": 4.268467001377448}
- {"view": "img_064_mean.png", "type": "points", "n": 3, "ids": [8, 101, 114], "max_px": 4.484895531775824, "threshold_px": 4.268467001377448}
- {"view": "img_066_mean.png", "type": "points", "n": 1, "ids": [8], "max_px": 4.36476873828576, "threshold_px": 4.268467001377448}
- {"view": "img_070_mean.png", "type": "points", "n": 1, "ids": [105], "max_px": 4.2779974332684745, "threshold_px": 4.268467001377448}
- {"view": "img_075_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 4.307881006019984, "threshold_px": 4.268467001377448}
- {"view": "img_076_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 4.329345633049963, "threshold_px": 4.268467001377448}
- {"view": "img_084_mean.png", "type": "points", "n": 1, "ids": [114], "max_px": 4.324869025220119, "threshold_px": 4.268467001377448}
- {"view": "img_094_mean.png", "type": "points", "n": 2, "ids": [10, 102], "max_px": 4.659427952336393, "threshold_px": 4.268467001377448}
- {"view": "img_095_mean.png", "type": "points", "n": 2, "ids": [2, 3], "max_px": 4.376228501734398, "threshold_px": 4.268467001377448}
- {"view": "img_098_mean.png", "type": "points", "n": 1, "ids": [114], "max_px": 4.312567137891386, "threshold_px": 4.268467001377448}
- {"view": "img_102_mean.png", "type": "points", "n": 1, "ids": [22], "max_px": 4.361849792846435, "threshold_px": 4.268467001377448}
- {"view": "img_104_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 4.329627536153381, "threshold_px": 4.268467001377448}
- {"view": "img_107_mean.png", "type": "points", "n": 1, "ids": [113], "max_px": 4.463740950509512, "threshold_px": 4.268467001377448}
- {"view": "img_108_mean.png", "type": "points", "n": 3, "ids": [46, 76, 87], "max_px": 4.534736679228636, "threshold_px": 4.268467001377448}
- {"view": "img_112_mean.png", "type": "points", "n": 2, "ids": [64, 109], "max_px": 4.5500580481064405, "threshold_px": 4.268467001377448}
- {"view": "img_116_mean.png", "type": "points", "n": 5, "ids": [52, 66, 81, 96, 97], "max_px": 5.043770701483515, "threshold_px": 4.268467001377448}
- {"view": "img_120_mean.png", "type": "points", "n": 2, "ids": [26, 27], "max_px": 4.6928076362303495, "threshold_px": 4.268467001377448}
- {"view": "img_122_mean.png", "type": "points", "n": 2, "ids": [8, 22], "max_px": 4.424042746925722, "threshold_px": 4.268467001377448}
- {"view": "img_125_mean.png", "type": "points", "n": 1, "ids": [115], "max_px": 4.297995184908517, "threshold_px": 4.268467001377448}
- {"view": "img_132_mean.png", "type": "points", "n": 1, "ids": [8], "max_px": 4.34689363576487, "threshold_px": 4.268467001377448}
- {"view": "img_012_mean.png", "type": "points", "n": 1, "ids": [99], "max_px": 4.320067923383621, "threshold_px": 4.1943029964349385}
- {"view": "img_018_mean.png", "type": "points", "n": 3, "ids": [20, 62, 90], "max_px": 4.635731819813395, "threshold_px": 4.1943029964349385}
- {"view": "img_029_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 4.263253119255016, "threshold_px": 4.1943029964349385}
- {"view": "img_034_mean.png", "type": "points", "n": 2, "ids": [11, 22], "max_px": 4.266052837634027, "threshold_px": 4.1943029964349385}
- {"view": "img_036_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 4.195315987670815, "threshold_px": 4.1943029964349385}
- {"view": "img_040_mean.png", "type": "points", "n": 1, "ids": [22], "max_px": 4.227369405324957, "threshold_px": 4.1943029964349385}
- {"view": "img_064_mean.png", "type": "points", "n": 1, "ids": [22], "max_px": 4.305329440062705, "threshold_px": 4.1943029964349385}
- {"view": "img_066_mean.png", "type": "points", "n": 1, "ids": [22], "max_px": 4.313235002082526, "threshold_px": 4.1943029964349385}
- {"view": "img_070_mean.png", "type": "points", "n": 1, "ids": [106], "max_px": 4.202998463117226, "threshold_px": 4.1943029964349385}
- {"view": "img_083_mean.png", "type": "points", "n": 1, "ids": [114], "max_px": 4.285892313894233, "threshold_px": 4.1943029964349385}
- {"view": "img_102_mean.png", "type": "points", "n": 1, "ids": [8], "max_px": 4.313687228583058, "threshold_px": 4.1943029964349385}
- {"view": "img_103_mean.png", "type": "points", "n": 1, "ids": [8], "max_px": 4.224440293932431, "threshold_px": 4.1943029964349385}
- {"view": "img_108_mean.png", "type": "points", "n": 1, "ids": [110], "max_px": 4.299613227802276, "threshold_px": 4.1943029964349385}
- {"view": "img_112_mean.png", "type": "points", "n": 1, "ids": [98], "max_px": 4.52475240584122, "threshold_px": 4.1943029964349385}
- {"view": "img_116_mean.png", "type": "points", "n": 2, "ids": [67, 82], "max_px": 4.749854946694672, "threshold_px": 4.1943029964349385}
- {"view": "img_120_mean.png", "type": "points", "n": 1, "ids": [17], "max_px": 4.396575757611646, "threshold_px": 4.1943029964349385}
- {"view": "img_121_mean.png", "type": "points", "n": 2, "ids": [8, 22], "max_px": 4.234826461830223, "threshold_px": 4.1943029964349385}
