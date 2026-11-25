# Calibration 1280x960_MJPG  -  grade **PASS**

- created: 2026-11-25T18:11:22  |  OpenCV 4.8.0  |  model: `brown_k1k2`
- views: 138  |  points: 14382
- reprojection RMS **0.1919 px**  (mean 0.1610, p95 0.3359, max 2.2345)
- bootstrap undistortion uncertainty: mean 0.2407 px, max 0.4095 px

| param | value | 1-sigma |
|---|---|---|
| fx | 1569.8150 | 0.2048 |
| fy | 1569.9521 | 0.1999 |
| cx | 653.4279 | 0.1833 |
| cy | 487.0703 | 0.1698 |
| k1 | -0.16754138 | 0.00036063 |
| k2 | 0.04703653 | 0.00205944 |
| p1 | 0.00005697 | 0.00002055 |
| p2 | -0.00023804 | 0.00002419 |
| k3 | 0.00000000 | 0.00000000 |

- FOV H/V/D: 45.47 / 34.48 / 56.06 deg
- max distortion displacement: 38.55 px
- principal point offset from centre: (13.93, 7.57) px
- coverage: 96% of 16x9 cells; tilt range 3-50 deg
- **held-out metric accuracy** (views never used to fit the intrinsics, board reconstructed in mm): RMS 0.081 mm, p95 0.140 mm, max 1.570 mm at median distance 698 mm
- board pitch used: X 25.0000 mm, Y 25.0369 mm  (print Y/X ratio estimated from images (+0.148%); absolute scale nominal)

## Metric resolution (1 px at distance Z on a fronto-parallel plane)

| Z (mm) | mm/px X | mm/px Y | field of view (mm) |
|---|---|---|---|
| 150 | 0.0956 | 0.0955 | 122 x 92 |
| 250 | 0.1593 | 0.1592 | 204 x 153 |
| 400 | 0.2548 | 0.2548 | 326 x 245 |
| 600 | 0.3822 | 0.3822 | 489 x 367 |
| 800 | 0.5096 | 0.5096 | 652 x 489 |
| 1000 | 0.6370 | 0.6370 | 815 x 611 |
| 1500 | 0.9555 | 0.9554 | 1223 x 917 |

## Issues

- PASS: measured accuracy 0.081 mm RMS, 95% within 0.140 mm (target 0.5 mm) on held-out views at ~698 mm
- note: few points in image corner regions ['top_right', 'bottom_left'] - distortion is extrapolated there
- note: bootstrap undistortion uncertainty max 0.41 px (target < 0.2)

## Rejected

- {"view": "img_000_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.2469277067403377, "threshold_px": 2.0538860578005047}
- {"view": "img_001_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.5251058672391196, "threshold_px": 2.0538860578005047}
- {"view": "img_002_mean.png", "type": "points", "n": 2, "ids": [48, 60], "max_px": 2.3068729751165646, "threshold_px": 2.0538860578005047}
- {"view": "img_004_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 5.824714431475543, "threshold_px": 2.0538860578005047}
- {"view": "img_007_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 4.755638019115422, "threshold_px": 2.0538860578005047}
- {"view": "img_016_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.400124335679726, "threshold_px": 2.0538860578005047}
- {"view": "img_019_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 2.314974551940308, "threshold_px": 2.0538860578005047}
- {"view": "img_025_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 4.3392186378773125, "threshold_px": 2.0538860578005047}
- {"view": "img_026_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 4.356254942836329, "threshold_px": 2.0538860578005047}
- {"view": "img_028_mean.png", "type": "points", "n": 2, "ids": [11, 24], "max_px": 4.68651583206514, "threshold_px": 2.0538860578005047}
- {"view": "img_035_mean.png", "type": "points", "n": 3, "ids": [11, 12, 24], "max_px": 9.85684093855106, "threshold_px": 2.0538860578005047}
- {"view": "img_043_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 5.975720232547958, "threshold_px": 2.0538860578005047}
- {"view": "img_056_mean.png", "type": "points", "n": 3, "ids": [23, 35, 48], "max_px": 2.500110365057339, "threshold_px": 2.0538860578005047}
- {"view": "img_057_mean.png", "type": "points", "n": 4, "ids": [23, 35, 48, 60], "max_px": 2.474090835922193, "threshold_px": 2.0538860578005047}
- {"view": "img_058_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.3669592298049924, "threshold_px": 2.0538860578005047}
- {"view": "img_059_mean.png", "type": "points", "n": 2, "ids": [23, 35], "max_px": 2.2856891873968657, "threshold_px": 2.0538860578005047}
- {"view": "img_072_mean.png", "type": "points", "n": 1, "ids": [0], "max_px": 5.146934909351481, "threshold_px": 2.0538860578005047}
- {"view": "img_075_mean.png", "type": "points", "n": 3, "ids": [11, 24, 37], "max_px": 4.864565195238497, "threshold_px": 2.0538860578005047}
- {"view": "img_077_mean.png", "type": "points", "n": 2, "ids": [23, 35], "max_px": 2.3669486035003824, "threshold_px": 2.0538860578005047}
- {"view": "img_079_mean.png", "type": "points", "n": 2, "ids": [0, 13], "max_px": 2.33054178221437, "threshold_px": 2.0538860578005047}
- {"view": "img_080_mean.png", "type": "points", "n": 1, "ids": [35], "max_px": 2.1453685200893626, "threshold_px": 2.0538860578005047}
- {"view": "img_083_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 2.1184672764766845, "threshold_px": 2.0538860578005047}
- {"view": "img_093_mean.png", "type": "points", "n": 1, "ids": [12], "max_px": 4.494223010966832, "threshold_px": 2.0538860578005047}
- {"view": "img_094_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.159334240591041, "threshold_px": 2.0538860578005047}
- {"view": "img_109_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.1623409893164642, "threshold_px": 2.0538860578005047}
- {"view": "img_113_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.262767569307174, "threshold_px": 2.0538860578005047}
- {"view": "img_114_mean.png", "type": "points", "n": 5, "ids": [10, 23, 48, 60, 103], "max_px": 2.6431721294855595, "threshold_px": 2.0538860578005047}
- {"view": "img_117_mean.png", "type": "points", "n": 3, "ids": [36, 59, 115], "max_px": 2.5600397619134907, "threshold_px": 2.0538860578005047}
- {"view": "img_118_mean.png", "type": "points", "n": 3, "ids": [23, 48, 60], "max_px": 2.872179092605033, "threshold_px": 2.0538860578005047}
- {"view": "img_120_mean.png", "type": "points", "n": 1, "ids": [35], "max_px": 2.203540009151299, "threshold_px": 2.0538860578005047}
- {"view": "img_126_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.1134805853993233, "threshold_px": 2.0538860578005047}
- {"view": "img_127_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.097816378681321, "threshold_px": 2.0538860578005047}
- {"view": "img_128_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.1118085018844375, "threshold_px": 2.0538860578005047}
- {"view": "img_130_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 2.3627356060479188, "threshold_px": 2.0538860578005047}
- {"view": "img_131_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 7.59036013178472, "threshold_px": 2.0538860578005047}
- {"view": "img_132_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 7.120468374648284, "threshold_px": 2.0538860578005047}
- {"view": "img_133_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 7.91942814994158, "threshold_px": 2.0538860578005047}
- {"view": "img_135_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.575178616620902, "threshold_px": 2.0538860578005047}
- {"view": "img_136_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.3531311946496305, "threshold_px": 2.0538860578005047}
- {"view": "img_000_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 2.062762085180972, "threshold_px": 2.008149363219939}
- {"view": "img_001_mean.png", "type": "points", "n": 2, "ids": [48, 60], "max_px": 2.1017368407903096, "threshold_px": 2.008149363219939}
- {"view": "img_004_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.0142863574626704, "threshold_px": 2.008149363219939}
- {"view": "img_018_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 2.0524132734522316, "threshold_px": 2.008149363219939}
- {"view": "img_019_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.064210515127173, "threshold_px": 2.008149363219939}
- {"view": "img_051_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.0267024986524227, "threshold_px": 2.008149363219939}
- {"view": "img_056_mean.png", "type": "points", "n": 1, "ids": [60], "max_px": 2.0550316738884744, "threshold_px": 2.008149363219939}
- {"view": "img_058_mean.png", "type": "points", "n": 2, "ids": [35, 48], "max_px": 2.0873674582714976, "threshold_px": 2.008149363219939}
- {"view": "img_059_mean.png", "type": "points", "n": 2, "ids": [48, 60], "max_px": 2.055368071471813, "threshold_px": 2.008149363219939}
- {"view": "img_077_mean.png", "type": "points", "n": 2, "ids": [48, 60], "max_px": 2.0772868645646616, "threshold_px": 2.008149363219939}
- {"view": "img_079_mean.png", "type": "points", "n": 1, "ids": [26], "max_px": 2.1976219083585415, "threshold_px": 2.008149363219939}
- {"view": "img_094_mean.png", "type": "points", "n": 2, "ids": [35, 48], "max_px": 2.0554539618699206, "threshold_px": 2.008149363219939}
- {"view": "img_117_mean.png", "type": "points", "n": 1, "ids": [72], "max_px": 2.028139882437912, "threshold_px": 2.008149363219939}
- {"view": "img_118_mean.png", "type": "points", "n": 1, "ids": [36], "max_px": 2.089719562210534, "threshold_px": 2.008149363219939}
- {"view": "img_125_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.0540070282229013, "threshold_px": 2.008149363219939}
- {"view": "img_126_mean.png", "type": "points", "n": 2, "ids": [35, 48], "max_px": 2.0592979315916864, "threshold_px": 2.008149363219939}
- {"view": "img_131_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.402001089358365, "threshold_px": 2.008149363219939}
- {"view": "img_132_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.2140455760197653, "threshold_px": 2.008149363219939}
- {"view": "img_133_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.3815191969926834, "threshold_px": 2.008149363219939}
- {"view": "img_000_mean.png", "type": "points", "n": 1, "ids": [60], "max_px": 2.0279108762251865, "threshold_px": 1.993915386113145}
- {"view": "img_077_mean.png", "type": "points", "n": 1, "ids": [115], "max_px": 2.0024858739383795, "threshold_px": 1.993915386113145}
- {"view": "img_094_mean.png", "type": "points", "n": 1, "ids": [60], "max_px": 2.035061294258104, "threshold_px": 1.993915386113145}
- {"view": "img_117_mean.png", "type": "points", "n": 2, "ids": [47, 103], "max_px": 2.0302285328394376, "threshold_px": 1.993915386113145}
- {"view": "img_125_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 2.0766598612446487, "threshold_px": 1.993915386113145}
- {"view": "img_125_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 2.0338124314634696, "threshold_px": 1.9929198807475323}
