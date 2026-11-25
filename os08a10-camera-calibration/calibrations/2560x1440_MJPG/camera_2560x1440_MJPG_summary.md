# Calibration 2560x1440_MJPG  -  grade **PASS**

- created: 2026-11-25T16:34:29  |  OpenCV 4.8.0  |  model: `brown_k1k2`
- views: 122  |  points: 12302
- reprojection RMS **0.4192 px**  (mean 0.3077, p95 0.8414, max 4.3937)
- bootstrap undistortion uncertainty: mean 0.6629 px, max 1.7190 px

| param | value | 1-sigma |
|---|---|---|
| fx | 2354.6204 | 0.2798 |
| fy | 2354.8320 | 0.2615 |
| cx | 1300.5430 | 0.4255 |
| cy | 734.3494 | 0.3854 |
| k1 | -0.16932513 | 0.00030386 |
| k2 | 0.06277795 | 0.00098140 |
| p1 | -0.00002611 | 0.00002940 |
| p2 | -0.00050173 | 0.00003390 |
| k3 | 0.00000000 | 0.00000000 |

- FOV H/V/D: 59.46 / 34.49 / 67.25 deg
- max distortion displacement: 101.37 px
- principal point offset from centre: (21.04, 14.85) px
- coverage: 96% of 16x9 cells; tilt range 6-69 deg
- focal length (assuming full-sensor scaled mode): 7.064 mm
- **held-out metric accuracy** (views never used to fit the intrinsics, board reconstructed in mm): RMS 0.143 mm, p95 0.259 mm, max 2.669 mm at median distance 660 mm
- board pitch used: X 25.0000 mm, Y 25.0407 mm  (print Y/X ratio estimated from images (+0.163%); absolute scale nominal)

## Metric resolution (1 px at distance Z on a fronto-parallel plane)

| Z (mm) | mm/px X | mm/px Y | field of view (mm) |
|---|---|---|---|
| 150 | 0.0637 | 0.0637 | 163 x 92 |
| 250 | 0.1062 | 0.1062 | 272 x 153 |
| 400 | 0.1699 | 0.1699 | 435 x 245 |
| 600 | 0.2548 | 0.2548 | 652 x 367 |
| 800 | 0.3398 | 0.3397 | 870 x 489 |
| 1000 | 0.4247 | 0.4247 | 1087 x 612 |
| 1500 | 0.6370 | 0.6370 | 1631 x 917 |

## Issues

- PASS: measured accuracy 0.143 mm RMS, 95% within 0.259 mm (target 0.5 mm) on held-out views at ~660 mm
- note: RMS reprojection 0.419 px (> 0.35) - check focus, motion, board flatness
- note: few points in image corner regions ['bottom_left', 'bottom_right'] - distortion is extrapolated there
- note: bootstrap undistortion uncertainty max 1.72 px

## Rejected

- {"view": "img_007_mean.png", "type": "points", "n": 1, "ids": [104], "max_px": 5.609182239626999, "threshold_px": 3.241576606457224}
- {"view": "img_009_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 4.0679179919969, "threshold_px": 3.241576606457224}
- {"view": "img_010_mean.png", "type": "points", "n": 2, "ids": [23, 90], "max_px": 3.7147659768978505, "threshold_px": 3.241576606457224}
- {"view": "img_011_mean.png", "type": "points", "n": 3, "ids": [105, 115, 116], "max_px": 10.33497550262013, "threshold_px": 3.241576606457224}
- {"view": "img_012_mean.png", "type": "points", "n": 1, "ids": [7], "max_px": 3.7772804033953506, "threshold_px": 3.241576606457224}
- {"view": "img_013_mean.png", "type": "points", "n": 2, "ids": [12, 115], "max_px": 3.444740770286883, "threshold_px": 3.241576606457224}
- {"view": "img_015_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.60978630326931, "threshold_px": 3.241576606457224}
- {"view": "img_017_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.3383749895356494, "threshold_px": 3.241576606457224}
- {"view": "img_018_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.701127585199206, "threshold_px": 3.241576606457224}
- {"view": "img_020_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 4.012976935910577, "threshold_px": 3.241576606457224}
- {"view": "img_021_mean.png", "type": "points", "n": 5, "ids": [0, 13, 22, 23, 116], "max_px": 10.261357403132397, "threshold_px": 3.241576606457224}
- {"view": "img_022_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.7646408679739696, "threshold_px": 3.241576606457224}
- {"view": "img_026_mean.png", "type": "points", "n": 2, "ids": [10, 11], "max_px": 5.997017970165883, "threshold_px": 3.241576606457224}
- {"view": "img_027_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.635139087385807, "threshold_px": 3.241576606457224}
- {"view": "img_028_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 3.759218227086744, "threshold_px": 3.241576606457224}
- {"view": "img_029_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 3.949862289922492, "threshold_px": 3.241576606457224}
- {"view": "img_030_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 4.016237715853924, "threshold_px": 3.241576606457224}
- {"view": "img_031_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 4.16227030737538, "threshold_px": 3.241576606457224}
- {"view": "img_032_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 4.11950077043854, "threshold_px": 3.241576606457224}
- {"view": "img_034_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 4.1451013989767205, "threshold_px": 3.241576606457224}
- {"view": "img_039_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 3.4336291250531525, "threshold_px": 3.241576606457224}
- {"view": "img_041_mean.png", "type": "points", "n": 1, "ids": [0], "max_px": 7.392171716749464, "threshold_px": 3.241576606457224}
- {"view": "img_043_mean.png", "type": "points", "n": 1, "ids": [1], "max_px": 5.895513314192039, "threshold_px": 3.241576606457224}
- {"view": "img_044_mean.png", "type": "points", "n": 2, "ids": [23, 116], "max_px": 7.3871352614625065, "threshold_px": 3.241576606457224}
- {"view": "img_045_mean.png", "type": "points", "n": 1, "ids": [116], "max_px": 7.170337394455317, "threshold_px": 3.241576606457224}
- {"view": "img_047_mean.png", "type": "points", "n": 2, "ids": [115, 116], "max_px": 11.541381627215534, "threshold_px": 3.241576606457224}
- {"view": "img_048_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.627911817658485, "threshold_px": 3.241576606457224}
- {"view": "img_049_mean.png", "type": "points", "n": 2, "ids": [115, 116], "max_px": 6.1622871509243256, "threshold_px": 3.241576606457224}
- {"view": "img_050_mean.png", "type": "points", "n": 2, "ids": [35, 116], "max_px": 6.3885988907724185, "threshold_px": 3.241576606457224}
- {"view": "img_051_mean.png", "type": "points", "n": 2, "ids": [103, 116], "max_px": 14.046241696818887, "threshold_px": 3.241576606457224}
- {"view": "img_058_mean.png", "type": "points", "n": 4, "ids": [0, 13, 26, 102], "max_px": 6.991459540510759, "threshold_px": 3.241576606457224}
- {"view": "img_059_mean.png", "type": "points", "n": 7, "ids": [0, 10, 13, 23, 26, 48, 60], "max_px": 6.774973180843555, "threshold_px": 3.241576606457224}
- {"view": "img_060_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.877797407196181, "threshold_px": 3.241576606457224}
- {"view": "img_067_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.547569739747115, "threshold_px": 3.241576606457224}
- {"view": "img_068_mean.png", "type": "points", "n": 8, "ids": [0, 10, 13, 22, 23, 48, 102, 115], "max_px": 6.240104340807587, "threshold_px": 3.241576606457224}
- {"view": "img_069_mean.png", "type": "points", "n": 7, "ids": [0, 9, 10, 13, 22, 23, 48], "max_px": 8.145856655549363, "threshold_px": 3.241576606457224}
- {"view": "img_070_mean.png", "type": "points", "n": 3, "ids": [10, 23, 48], "max_px": 5.26586870978514, "threshold_px": 3.241576606457224}
- {"view": "img_071_mean.png", "type": "points", "n": 3, "ids": [10, 13, 23], "max_px": 5.30299928208012, "threshold_px": 3.241576606457224}
- {"view": "img_072_mean.png", "type": "points", "n": 4, "ids": [0, 10, 13, 23], "max_px": 5.1274314450065885, "threshold_px": 3.241576606457224}
- {"view": "img_073_mean.png", "type": "points", "n": 3, "ids": [0, 13, 26], "max_px": 5.859567356419233, "threshold_px": 3.241576606457224}
- {"view": "img_075_mean.png", "type": "points", "n": 2, "ids": [11, 116], "max_px": 9.2207915036796, "threshold_px": 3.241576606457224}
- {"view": "img_076_mean.png", "type": "points", "n": 3, "ids": [10, 23, 35], "max_px": 3.9941159931402637, "threshold_px": 3.241576606457224}
- {"view": "img_077_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.6528397631598284, "threshold_px": 3.241576606457224}
- {"view": "img_078_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 3.497042773953702, "threshold_px": 3.241576606457224}
- {"view": "img_082_mean.png", "type": "points", "n": 4, "ids": [48, 50, 60, 102], "max_px": 5.000339569066383, "threshold_px": 3.241576606457224}
- {"view": "img_083_mean.png", "type": "points", "n": 3, "ids": [29, 47, 48], "max_px": 6.563278127589012, "threshold_px": 3.241576606457224}
- {"view": "img_084_mean.png", "type": "points", "n": 2, "ids": [59, 90], "max_px": 4.346013565050568, "threshold_px": 3.241576606457224}
- {"view": "img_085_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 4.2146128078230225, "threshold_px": 3.241576606457224}
- {"view": "img_088_mean.png", "type": "points", "n": 4, "ids": [10, 22, 23, 116], "max_px": 8.096865980864022, "threshold_px": 3.241576606457224}
- {"view": "img_089_mean.png", "type": "points", "n": 3, "ids": [22, 23, 116], "max_px": 7.723539797608756, "threshold_px": 3.241576606457224}
- {"view": "img_090_mean.png", "type": "points", "n": 7, "ids": [0, 10, 13, 22, 26, 35, 48], "max_px": 6.765401204965882, "threshold_px": 3.241576606457224}
- {"view": "img_091_mean.png", "type": "points", "n": 7, "ids": [10, 23, 38, 48, 51, 60, 103], "max_px": 5.7505726464865665, "threshold_px": 3.241576606457224}
- {"view": "img_094_mean.png", "type": "points", "n": 4, "ids": [0, 13, 26, 102], "max_px": 6.669418606869661, "threshold_px": 3.241576606457224}
- {"view": "img_095_mean.png", "type": "points", "n": 3, "ids": [10, 23, 103], "max_px": 5.39808986801009, "threshold_px": 3.241576606457224}
- {"view": "img_096_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 3.6058656267124785, "threshold_px": 3.241576606457224}
- {"view": "img_097_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 4.396992940503468, "threshold_px": 3.241576606457224}
- {"view": "img_098_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 4.4880162318354495, "threshold_px": 3.241576606457224}
- {"view": "img_099_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 4.439742968224269, "threshold_px": 3.241576606457224}
- {"view": "img_105_mean.png", "type": "points", "n": 1, "ids": [0], "max_px": 4.706373294809436, "threshold_px": 3.241576606457224}
- {"view": "img_106_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 3.928270208468369, "threshold_px": 3.241576606457224}
- {"view": "img_107_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 4.018354337649734, "threshold_px": 3.241576606457224}
- {"view": "img_108_mean.png", "type": "points", "n": 1, "ids": [35], "max_px": 3.5145339161031206, "threshold_px": 3.241576606457224}
- {"view": "img_109_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.3678323131332566, "threshold_px": 3.241576606457224}
- {"view": "img_111_mean.png", "type": "points", "n": 1, "ids": [35], "max_px": 3.2696862938859055, "threshold_px": 3.241576606457224}
- {"view": "img_115_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 4.035997379514601, "threshold_px": 3.241576606457224}
- {"view": "img_117_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 3.4055780951467676, "threshold_px": 3.241576606457224}
- {"view": "img_118_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 4.43571667323142, "threshold_px": 3.241576606457224}
- {"view": "img_119_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 4.89109612954017, "threshold_px": 3.241576606457224}
- {"view": "img_120_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 4.110328873485623, "threshold_px": 3.241576606457224}
- {"view": "img_121_mean.png", "type": "points", "n": 2, "ids": [10, 23], "max_px": 4.182857651629499, "threshold_px": 3.241576606457224}
- {"view": "img_006_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.1753748254676104, "threshold_px": 2.971062294946984}
- {"view": "img_012_mean.png", "type": "points", "n": 3, "ids": [9, 48, 102], "max_px": 3.2217607939883735, "threshold_px": 2.971062294946984}
- {"view": "img_016_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.1058935156566956, "threshold_px": 2.971062294946984}
- {"view": "img_017_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.201229754397655, "threshold_px": 2.971062294946984}
- {"view": "img_021_mean.png", "type": "points", "n": 1, "ids": [90], "max_px": 3.446676061471616, "threshold_px": 2.971062294946984}
- {"view": "img_024_mean.png", "type": "points", "n": 2, "ids": [23, 35], "max_px": 3.010127699963291, "threshold_px": 2.971062294946984}
- {"view": "img_025_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.097049316004973, "threshold_px": 2.971062294946984}
- {"view": "img_027_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.3862027445389353, "threshold_px": 2.971062294946984}
- {"view": "img_040_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 2.9968655336895886, "threshold_px": 2.971062294946984}
- {"view": "img_042_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 3.1741204405446113, "threshold_px": 2.971062294946984}
- {"view": "img_045_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 3.0407150489374275, "threshold_px": 2.971062294946984}
- {"view": "img_046_mean.png", "type": "points", "n": 2, "ids": [23, 35], "max_px": 3.1707250130606037, "threshold_px": 2.971062294946984}
- {"view": "img_048_mean.png", "type": "points", "n": 2, "ids": [23, 35], "max_px": 3.174814002098415, "threshold_px": 2.971062294946984}
- {"view": "img_059_mean.png", "type": "points", "n": 2, "ids": [36, 47], "max_px": 3.3437194010685993, "threshold_px": 2.971062294946984}
- {"view": "img_060_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.3970665531038917, "threshold_px": 2.971062294946984}
- {"view": "img_067_mean.png", "type": "points", "n": 2, "ids": [1, 39], "max_px": 3.0802558851581376, "threshold_px": 2.971062294946984}
- {"view": "img_069_mean.png", "type": "points", "n": 1, "ids": [102], "max_px": 3.080827054164382, "threshold_px": 2.971062294946984}
- {"view": "img_070_mean.png", "type": "points", "n": 1, "ids": [90], "max_px": 3.54832924745262, "threshold_px": 2.971062294946984}
- {"view": "img_071_mean.png", "type": "points", "n": 1, "ids": [47], "max_px": 3.06425290246886, "threshold_px": 2.971062294946984}
- {"view": "img_075_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.0634108084747824, "threshold_px": 2.971062294946984}
- {"view": "img_076_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 3.08155207717875, "threshold_px": 2.971062294946984}
- {"view": "img_077_mean.png", "type": "points", "n": 2, "ids": [23, 103], "max_px": 3.3246842310750355, "threshold_px": 2.971062294946984}
- {"view": "img_081_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 3.1854313076942526, "threshold_px": 2.971062294946984}
- {"view": "img_082_mean.png", "type": "points", "n": 1, "ids": [114], "max_px": 3.355894249315772, "threshold_px": 2.971062294946984}
- {"view": "img_084_mean.png", "type": "points", "n": 1, "ids": [102], "max_px": 3.5114071426574953, "threshold_px": 2.971062294946984}
- {"view": "img_090_mean.png", "type": "points", "n": 2, "ids": [36, 47], "max_px": 3.466337733812087, "threshold_px": 2.971062294946984}
- {"view": "img_091_mean.png", "type": "points", "n": 3, "ids": [47, 59, 90], "max_px": 3.1582711477840135, "threshold_px": 2.971062294946984}
- {"view": "img_092_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 3.111172744692743, "threshold_px": 2.971062294946984}
- {"view": "img_094_mean.png", "type": "points", "n": 1, "ids": [115], "max_px": 3.0863698287784986, "threshold_px": 2.971062294946984}
- {"view": "img_095_mean.png", "type": "points", "n": 1, "ids": [36], "max_px": 2.9753253031608584, "threshold_px": 2.971062294946984}
- {"view": "img_096_mean.png", "type": "points", "n": 1, "ids": [47], "max_px": 3.0253028170686025, "threshold_px": 2.971062294946984}
- {"view": "img_097_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 3.0240391365056176, "threshold_px": 2.971062294946984}
- {"view": "img_098_mean.png", "type": "points", "n": 2, "ids": [48, 103], "max_px": 3.075247139997884, "threshold_px": 2.971062294946984}
- {"view": "img_106_mean.png", "type": "points", "n": 1, "ids": [35], "max_px": 3.3672815765772617, "threshold_px": 2.971062294946984}
- {"view": "img_107_mean.png", "type": "points", "n": 1, "ids": [35], "max_px": 3.0168988271868264, "threshold_px": 2.971062294946984}
- {"view": "img_114_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.0639466547373035, "threshold_px": 2.971062294946984}
- {"view": "img_115_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.3830254816863676, "threshold_px": 2.971062294946984}
- {"view": "img_116_mean.png", "type": "points", "n": 1, "ids": [60], "max_px": 3.0548515756318744, "threshold_px": 2.971062294946984}
- {"view": "img_117_mean.png", "type": "points", "n": 1, "ids": [36], "max_px": 3.049852697168172, "threshold_px": 2.971062294946984}
- {"view": "img_118_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 3.229110963633196, "threshold_px": 2.971062294946984}
- {"view": "img_013_mean.png", "type": "points", "n": 1, "ids": [114], "max_px": 2.949513420171424, "threshold_px": 2.9188392590644208}
- {"view": "img_023_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.926237147540209, "threshold_px": 2.9188392590644208}
- {"view": "img_044_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 2.9440295446281515, "threshold_px": 2.9188392590644208}
- {"view": "img_048_mean.png", "type": "points", "n": 1, "ids": [2], "max_px": 2.976114802400242, "threshold_px": 2.9188392590644208}
- {"view": "img_059_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 2.976084338528661, "threshold_px": 2.9188392590644208}
- {"view": "img_063_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 2.9595089900910923, "threshold_px": 2.9188392590644208}
- {"view": "img_067_mean.png", "type": "points", "n": 1, "ids": [15], "max_px": 3.105444671933772, "threshold_px": 2.9188392590644208}
- {"view": "img_070_mean.png", "type": "points", "n": 1, "ids": [102], "max_px": 3.086417608604703, "threshold_px": 2.9188392590644208}
- {"view": "img_081_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 3.0062717815174804, "threshold_px": 2.9188392590644208}
- {"view": "img_086_mean.png", "type": "points", "n": 1, "ids": [10], "max_px": 2.9374180656592577, "threshold_px": 2.9188392590644208}
- {"view": "img_087_mean.png", "type": "points", "n": 1, "ids": [48], "max_px": 2.9548164939894255, "threshold_px": 2.9188392590644208}
- {"view": "img_091_mean.png", "type": "points", "n": 2, "ids": [36, 102], "max_px": 3.1636758643285066, "threshold_px": 2.9188392590644208}
- {"view": "img_094_mean.png", "type": "points", "n": 1, "ids": [114], "max_px": 2.922909751230359, "threshold_px": 2.9188392590644208}
- {"view": "img_115_mean.png", "type": "points", "n": 1, "ids": [35], "max_px": 2.949930065042872, "threshold_px": 2.9188392590644208}
- {"view": "img_007_mean.png", "type": "points", "n": 1, "ids": [103], "max_px": 2.9098181033981807, "threshold_px": 2.9094248243267953}
- {"view": "img_059_mean.png", "type": "points", "n": 1, "ids": [8], "max_px": 3.005467945695006, "threshold_px": 2.9094248243267953}
- {"view": "img_081_mean.png", "type": "points", "n": 1, "ids": [12], "max_px": 2.979707966738779, "threshold_px": 2.9094248243267953}
- {"view": "img_108_mean.png", "type": "points", "n": 1, "ids": [11], "max_px": 2.9144642292346274, "threshold_px": 2.9094248243267953}
- {"view": "img_113_mean.png", "type": "points", "n": 1, "ids": [23], "max_px": 2.912587681844103, "threshold_px": 2.9094248243267953}
