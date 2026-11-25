# Calibration summary

```
mode             grade model          rms px        fx        fy       cx       cy   HFOV unc px holdout mm (p95)  relation to 3840x2160_MJPG
1280x720_MJPG    PASS  brown_k1k2     0.2869   1176.97   1177.24   644.44   368.21  59.46    nan                -  scaled, same FOV
1280x720_YUYV    PASS  brown_k1k2     0.2869   1176.97   1177.24   644.43   368.19  59.46    nan                -  scaled, same FOV
1280x960_MJPG    PASS  brown_k1k2     0.1919   1569.82   1569.95   653.43   487.07  45.47  0.410      0.140@698mm  different FOV (crop?) f-ratio 0.445 vs size 0.333
2560x1440_MJPG   PASS  brown_k1k2     0.4192   2354.62   2354.83  1300.54   734.35  59.46  1.719      0.259@660mm  scaled, same FOV
2560x1440_YUYV   PASS  brown_k1k2     0.4192   2354.62   2354.83  1300.49   734.33  59.46    nan                -  scaled, same FOV
3840x2160_MJPG   PASS  brown_k1k2     0.8606   3530.91   3531.72  1930.80  1105.02  59.49  2.253      0.311@593mm  reference
3840x2160_YUYV   PASS  brown_k1k2     0.8606   3530.91   3531.72  1930.73  1104.92  59.49    nan                -  scaled, same FOV
640x480_MJPG     PASS  brown_k1k2     0.0959    784.91    784.98   326.46   243.29  45.44    nan                -  different FOV (crop?) f-ratio 0.222 vs size 0.167
640x480_YUYV     PASS  brown_k1k2     0.0959    784.91    784.98   326.46   243.29  45.44    nan                -  different FOV (crop?) f-ratio 0.222 vs size 0.167
```
