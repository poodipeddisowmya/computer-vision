# OS08A10 camera - calibration package

## What is in this folder

| path | what it is |
|---|---|
| **`os08a10_camera_config.yaml`** | **Everything about the camera in ONE file**: sensor / lens / USB identity, every video mode with its calibration (camera matrix, distortion, undistortion matrices, FOV, mm per pixel, measured accuracy), all camera controls (ranges, defaults, normal values), recommended settings and the rules that keep the calibration valid. |
| `calibrations/<mode>/camera_<mode>.yaml` | OpenCV calibration file per mode (`cv2.FileStorage`): `camera_matrix`, `distortion_coefficients` |
| `calibrations/<mode>/camera_<mode>.json` | Full details per mode; `_summary.md` readable report; `_report.png` charts (fully calibrated modes) |
| `calibrations/SUMMARY.md` | All modes side by side |
| `boards/charuco_a3.pdf` | The calibration board (print at 100 %) |
| `camcal/` | Runtime loader (`camcal.runtime`) and the calibration tools |
| `config/os08a10.yaml` | Settings of the calibration tools |

Calibrated modes (all PASS): 3840x2160 MJPG/YUYV, 2560x1440 MJPG/YUYV, 1280x960 MJPG, 1280x720 MJPG/YUYV,
640x480 MJPG/YUYV. 1920x1080 is advertised by the camera but delivers no frames.

```python
from camcal.runtime import CalibrationStore
cal = CalibrationStore("calibrations").for_frame(frame)      # picks the right mode by frame size
clean = cal.undistort_image(frame)
```

Commands: `python3 -m camcal simple` (hand-held recalibration, finishes by itself) · `python3 -m camcal still`
(camera rested per shot, most accurate) · `python3 -m camcal derive` (re-verify the derived modes) ·
`python3 -m camcal export` (rebuild `os08a10_camera_config.yaml`).

---

# OS08A10 8MP USB camera — calibration pipeline (Jetson Orin Nano)

Calibrates the camera's lens and sensor (intrinsics and distortion) for sub-mm vision work. Each resolution and pixel format is calibrated separately, and the camera's settings are protected throughout.
Everything here runs on the Jetson with the preinstalled stack (Python 3.10, OpenCV 4.8 with ArUco, NumPy, Matplotlib, PyYAML). No installs are needed.

## 0. Camera facts (datasheet + measured on this Jetson)

| Item | Value | Source |
|---|---|---|
| Sensor | OmniVision OS08A10, BSI, 2.0 µm pixels, 1/1.8", active 3840×2160 (7.68×4.32 mm), rolling shutter, CRA 11° | OVT product brief v1.6 |
| Module | USB **2.0** UVC, Sonix bridge `0c45:636d`, V4L2 card "HJ 4K Camera", fixed focus, F1.6, 650 nm IR-cut | Waveshare + `probe` |
| Lens | Datasheet is inconsistent (EFL 4.2 mm vs 4.9 mm vs FOV 60° H, which implies ≈6.6 mm). **Calibration measures the real value.** | |
| Controls | brightness, contrast, saturation, hue, gamma, gain, sharpness (0–6), WB auto/temperature, backlight comp., auto-exposure/exposure time, exposure_dynamic_framerate, power-line freq. **No zoom/pan/tilt/focus controls** | `probe` → `camera_probe.json` |

Measured on this unit:

| Mode | Delivered | Geometry vs 4K | Use for sub-mm |
|---|---|---|---|
| **3840×2160 MJPG** | 25 fps from camera (OpenCV CPU decode caps ~17–19 fps) | reference (full FOV) | **Primary live mode** |
| **3840×2160 YUYV** | 1 fps, uncompressed | same FOV | **Best for static metrology** |
| **2560×1440 MJPG** | 25 fps | exact 1.5× downscale, full FOV | Good (1.5× coarser) |
| 1920×1080 MJPG / YUYV | **no frames in first test** (also with GStreamer) — re-plug and retest | expected 2× | Close range only |
| 1280×960 MJPG | 60 fps | **centre crop** (2880×2160 of sensor) then 2.25× down → narrower FOV | No |
| 1280×720 / 640×480 | 50–60 fps | 3× / 6× downscale | No |

MJPG runs at a fixed JPEG quality of about 0.25 bits/pixel, which USB 2.0 bandwidth requires. Lowering the frame rate does **not** improve image quality; only YUYV avoids compression. The capture tool averages 4 frames per view to reduce noise.

### Resolution recommendation
1. **3840×2160 MJPG**: live inspection; best detail at 25 fps.
2. **3840×2160 YUYV**: static parts or a stop-and-measure station; uncompressed, so the best sub-pixel fidelity.
3. **2560×1440 MJPG**: when CPU or frame rate matters; full field of view.

Calibrate every mode you will run **in the same pixel format you will run it in**. A calibration is valid only for its exact `width × height × format`.

Approximate pixel footprint at 4K: about 0.15 mm/px at 500 mm if HFOV is 60°, or 0.24 mm/px if the EFL really is 4.2 mm. Multiply by 1.5 for 1440p and by 2 for 1080p. Corner and edge features localize to 0.05–0.2 px, so sub-mm is comfortably reachable at 4K out to about 1 m. The calibration output contains the real mm/px table for this lens.

## 1. Print and prepare the board (do this first)

**Use `boards/charuco_a3.pdf`.** It is a ChArUco board: 14×10 squares of 25 mm, 117 corners, DICT_4X4_100. Use `charuco_a4.pdf` (11×8 squares of 22 mm) only if you can't print A3 or your working distance is under about 40 cm.
ChArUco is still a checkerboard, but every corner has a unique ID, so partial views work. That lets you push the board into the extreme image corners, where lens distortion is largest and a plain checkerboard can't be detected. Plain-checkerboard PDFs are also provided as a fallback.

1. Print at **100% / "Actual size"** with "Fit to page" OFF. Use a laser printer and matte paper.
2. Check that both 100 mm scale bars measure 100.0 mm.
3. Glue it **perfectly flat** onto float glass, aluminium composite (Dibond) or a granite/acrylic plate. Paper on cardboard bends and destroys sub-mm accuracy. Then **fix the board** to a wall or table: the board stays still and you move the camera.
4. **Recommended:** measure the X and Y spans tick-to-tick with a caliper (nominal 350.00 × 250.00 mm):
   ```
   python3 -m camcal measure --span-x 350.12 --span-y 249.86
   ```
   - **The pipeline doesn't depend on this for intrinsics.** It estimates the print's X/Y stretch from the images themselves. In the ground-truth test it found the true ratio to 0.0005% and gave the same accuracy as perfect measurements.
   - **What the measurement adds:**
     - the absolute mm scale, used for metric verification;
     - a cross-check: if your caliper numbers disagree with the images, the pipeline flags it. In testing, it caught a deliberately mistyped 0.1% measurement.

## 2. Camera settings: what must never change after calibration

**Changes that invalidate the calibration (geometry):**
- **Resolution or pixel format.** Each mode needs its own calibration; 1280×960 is a crop, not a scale.
- **The lens.** Don't rotate, touch, re-glue or knock it. Mark it with a paint pen or thread-locker; if the mark moves, recalibrate.
- **Temperature state.** The module runs hot, so let it stream for 10–15 min before calibrating *and* before measuring. The capture tool enforces a 10-minute warm-up.
- **Camera mount.** This doesn't affect intrinsics, but it does affect any plane, robot or hand-eye calibration built on top.

**Changes that don't affect the geometry but should stay fixed in production for repeatable detection:**
- **auto_exposure → manual**, short `exposure_time_absolute`. The sensor is a **rolling shutter**, so moving parts skew; use short exposure, a strobe, or measure only when the part is still.
- **exposure_dynamic_framerate = 0.** It is currently **1** on this camera, so the frame rate drops in low light.
- **white_balance_automatic = 0**, a fixed temperature.
- **sharpness, gamma, contrast**: keep them exactly as they were during calibration. Sharpening shifts edge profiles. The runtime warns if they differ.
- **power_line_frequency** = your mains frequency (currently 50 Hz) to avoid flicker banding.

**How the pipeline protects your other projects:**
- Before capture, *every* control is snapshotted once, around the whole run. During capture the pipeline applies only:
  - the lock in `config/os08a10.yaml` (white balance, dynamic frame rate, backlight compensation);
  - its own automatic manual-exposure / gain control.
- On exit the original values are **restored and verified identical**: normal exit, Ctrl-C, SIGTERM or a crash. This was tested on this OS08A10: all 14 controls were restored identically.
- Geometry-relevant controls are never changed. They are recorded, and the runtime refuses to run if they differ later.
- The runtime API never writes a control unless your project passes it explicitly.

## 3. Calibrate (when the board is ready): one command

```
python3 -m camcal preview      # live view first; click START CALIBRATION when ready
python3 -m camcal auto         # or start the calibration directly
```
`preview` opens a live 4K view (it changes no camera settings) with the detected corners, distance, tilt,
brightness and a 2x pixel magnifier. The camera's warm-up counts while you look at it. Clicking
**START CALIBRATION** runs `auto` below. It runs these steps:
1. Finds the OS08A10 by name, so the C270 is ignored.
2. Test-streams every configured mode (`auto.profiles`: 4K MJPG, 1440p MJPG) and skips any that won't stream.
   The 1 fps uncompressed YUYV modes are not in the default run: a 1 fps live view needs a tripod.
   Add them on a tripod with `--profiles 4k_yuyv`.
3. Warms the camera up for 10 minutes, counted from when the live view opened. The window keeps detecting and
   says "GOOD VIEW - warm-up m:ss left" so you can practise; nothing is captured until warm-up ends (`W` skips it).
   A large status line always says why nothing is being captured: BOARD NOT FOUND, TOO CLOSE / OUT OF FOCUS,
   TOO FAR, HOLD STILL (with the measured motion), or "already covered - move to the MAGENTA outline".
4. For each resolution, opens a guided live window:
   - A **magenta outline** shows the next useful view, with a hint such as "move CLOSER, aim camera LEFT". Move the camera until the green live board roughly overlaps it, then hold still.
   - **Capture is automatic.** It fires when the camera has been still for about 0.5 s and the view adds information: it matches the target, covers new image area, or fills a missing tilt or distance. You never have to be exact.
   - **Exposure is automatic:** short exposure first (rolling shutter, hand-held), gain only if needed, with glare/saturation checks.
   - Every 5 views an **interim calibration** runs in the background. It sharpens the guidance outlines, **removes inconsistent views automatically**, and steers the remaining targets toward the image regions where the calibration is still uncertain.
   - The window shows a live checklist: views, coverage, image corners, tilt L/R/U/D, frontal, near, far and uncertainty. When everything is green it **finishes by itself**.
5. Calibrates the mode. If the result needs more data, it re-opens the capture where you left off.
6. Moves on to the next resolution (1-minute re-warm), and at the end writes `calibrations/SUMMARY.md` comparing all modes.
7. Restores every camera control to its original value.

Tips: hold the camera 35-60 cm from the board; closer than ~25 cm the fixed-focus lens blurs the markers.
For each view, **rest the camera on something** (a tripod with a ball head, a stack of books, the table edge):
a capture needs under 0.5 px of motion at 4K across 3 frames, which a free hand rarely holds. Keep the board
evenly lit and avoid glare.

Optional keys in the window: `SPACE` force a capture · `N` skip the current target · `U` undo · `A` auto on/off · `E` auto-exposure on · `[` `]` manual exposure · `K` keep capturing after completion · `W` skip warm-up · `G` grid · `H` help · `Q` finish this resolution now (calibrates it if it has 10+ views; otherwise the run stops) · `ESC` or closing the window stops the whole run. The run never moves on to the next resolution after a resolution ended with too few views.

Other commands:
```
python3 -m camcal capture --profile 4k_mjpg     # a single resolution
python3 -m camcal summary                       # compare calibrated modes (scaled vs cropped)
python3 -m camcal verify --profile 4k_mjpg      # live metric check in mm
python3 -m camcal selftest                      # ground-truth regression test
```
For best decode speed you can run `sudo nvpmodel -m 0 && sudo jetson_clocks` first. That changes Jetson power settings, so it's your call.

## 4. What the calibration does

The pipeline runs these steps:
1. ChArUco detection, then per-corner cornerSubPix with a window sized to avoid the markers, then a grid-consistency check against neighbours using a local homography.
   - OpenCV 4.8's ChArUco corners carry a **+0.5 px bias**. This pipeline removes it, verified on ground truth (bias < 0.003 px, median error 0.028 px).
2. **Board X/Y print-ratio estimation from the images.** A stretched planar target can't be explained by any pinhole camera once it's seen at varied tilts, so the ratio is directly measurable. The estimate is cross-checked against your caliper numbers.
3. Point-level, then view-level, robust outlier rejection.
4. Distortion model chosen by **5-fold cross-validation** from k1k2, k1k2k3 or rational. Training RMS always favours more parameters, so it isn't used for selection.
5. Final fit with 1-σ parameter standard deviations. The **held-out metric accuracy** is computed too: views never used to fit the intrinsics are reconstructed in mm.
6. **Bootstrap (30×)**: a per-pixel uncertainty map of the undistortion, an honest "how sure are we" number.
7. Grade **PASS / WARN / FAIL**:

   | Criterion | Requirement |
   |---|---|
   | Reprojection RMS | MJPG ≤ 0.35 px, YUYV ≤ 0.25 px |
   | Coverage | ≥ 85% of image cells |
   | Image corners | points in every corner region |
   | Board tilt | ≥ 25° |
   | Bootstrap uncertainty | ≤ 0.2 px |
   | Board | caliper spans agree with the images (if measured) |

**Outputs** go to `calibrations/<W>x<H>_<FORMAT>/`:

| File | Contents |
|---|---|
| `camera_*.yaml` | OpenCV FileStorage (C++ `cv::FileStorage` / Python): K, distortion, optimal new K for alpha 0 and 1, ROI, model, mode, grade |
| `camera_*.json` | everything: K, distortion, σ, FOV, focal length in mm, principal-point offset, mm/px table, distortion and uncertainty grids, coverage, tilt, per-view errors, the camera controls used, device identity |
| `camera_*_report.png` | residuals, per-view RMS, coverage, distortion field, uncertainty map |
| `camera_*_summary.md` | the same results as a short text summary |
| `camera_*_per_view.csv` | per-view errors |
| `camera_*_points.npz` | the corner points used |

## 5. Use in vision projects

```python
import sys; sys.path.insert(0, "/path/to/os08a10_calib")
from camcal.runtime import CalibrationStore
calib = CalibrationStore("/path/to/os08a10_calib/calibrations").for_mode(3840, 2160, "MJPG")
cam = calib.open_camera("/dev/video2")              # verifies the exact mode + geometry controls
seq, frame, t = cam.latest()
pts_ideal = calib.undistort_points(raw_pixel_points) # most accurate: detect on RAW image, undistort points
xy_mm = calib.pixels_to_plane(raw_pixel_points, rvec, tvec)  # metric on a known plane
rect = calib.undistort_image(frame, alpha=0.0)       # fast fixed-point remap if you need a rectified image
```
For the highest accuracy, detect edges and corners on the **raw** image and undistort only the resulting points. Undistorting the whole image first resamples it and costs some sub-pixel accuracy.

## 6. Validation (ground truth)

**Closed-loop automation test** (`python3 -m tests.virtual_rig`). A virtual camera renders the real board through a known lens. The board is an **unmeasured** print stretched +0.25% X / −0.12% Y. A virtual operator follows the on-screen targets imprecisely (±3°, ±3% position), shakes while moving, and sometimes gives up on a target.

| Result | Value |
|---|---|
| Finished by itself | **yes**, after 230 s with 37 views, **grade PASS**, no issues |
| fx / fy error | 0.008% / 0.002% |
| Principal point error | 0.08 / 0.03 px |
| Undistortion-map error | max 0.19 px, mean 0.09 px (predicted by bootstrap: 0.14 px) |
| Print-stretch estimate | 0.99637 vs true 0.99631 |
| Held-out metric error at 425 mm | **0.012 mm RMS**, 0.08 mm max |

**Offline engine tests** (`python3 -m camcal selftest`):

| Test | fx error | Principal point | Map error (max) | RMS |
|---|---|---|---|---|
| 1920×1080, 40 views | 0.0018% | 0.07 / 0.10 px | 0.19 px | 0.040 px |
| 3840×2160, stretched print, auto-estimated | 0.0010% | 0.10 / 0.02 px | 0.15 px | 0.024 px |
| same, without stretch estimation (old behaviour) | 0.16% / −0.22% | 0.44 / 3.6 px | 7.1 px → FAIL | 0.19 px |

**On the real OS08A10:**
- Every mode was test-streamed; 1080p was skipped as non-streaming.
- Auto-exposure was driven on live frames.
- The full `auto` run completed, and all 14 camera controls were restored identically afterwards.

The real accuracy check is still yours to do: measure a gauge block or a calipered part at your working distance with the calibrated camera.

## 7. Files

| Path | Contents |
|---|---|
| `boards/` | printable PDFs, previews and board definitions (`measure` writes your spans into the JSON) |
| `config/os08a10.yaml` | profiles, control lock, capture gates, calibration settings |
| `camcal/` | `v4l2` (ioctl controls), `camera` (grabber + control snapshot/restore), `board` (detection), `guide` (pose planner, completion checklist, auto-exposure), `capture` (automatic live capture), `calibrate`, `report`, `verify`, `runtime`, `__main__` (CLI incl. `auto`) |
| `tests/synthetic.py` | ground-truth renderer and engine test |
| `tests/virtual_rig.py` | closed-loop test: virtual camera + virtual operator driving the automatic capture |
| `camera_probe.json` | full mode/control dump of this OS08A10 unit |
