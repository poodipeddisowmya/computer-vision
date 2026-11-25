"""Live accuracy verification of a finished calibration.

Hold the (measured) board anywhere in view - ideally positions NOT used for
calibration - and read:
  * reprojection RMS of a pose-only fit (intrinsics fixed)  -> should stay ~ calibration RMS
  * metric reconstruction: every corner back-projected onto the fitted board
    plane and compared with its true position (mm)          -> sub-mm target
  * span error: reconstructed vs. true distance of the two farthest corners (mm)
  * working distance and mm/px at that distance
Press U to toggle the undistorted view (straight lines must look straight),
S to log a measurement, Q to quit. Results are appended to verify_log.json.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .board import BoardDetector, BoardSpec
from .runtime import Calibration

GREEN, RED, YELLOW, WHITE = (60, 220, 60), (60, 60, 240), (40, 220, 240), (240, 240, 240)


def measure(calib: Calibration, spec: BoardSpec, det) -> Optional[dict]:
    if det.n < 12:
        return None
    obj = spec.object_points(det.ids)
    ok, rv, tv = cv2.solvePnP(obj, det.corners, calib.K, calib.D, flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        return None
    rv, tv = cv2.solvePnPRefineLM(obj, det.corners, calib.K, calib.D, rv, tv)
    proj = calib.project(obj, rv, tv)
    rpx = np.linalg.norm(proj - det.corners, axis=1)
    xy = calib.pixels_to_plane(det.corners, rv, tv)
    emm = np.linalg.norm(xy - obj[:, :2], axis=1)
    i, j = np.unravel_index(np.argmax(np.linalg.norm(obj[:, None, :2] - obj[None, :, :2], axis=2)), (len(obj), len(obj)))
    true_span = float(np.linalg.norm(obj[i, :2] - obj[j, :2]))
    meas_span = float(np.linalg.norm(xy[i] - xy[j]))
    R, _ = cv2.Rodrigues(rv)
    tilt = float(np.degrees(np.arccos(min(1.0, abs(R[2, 2])))))
    z = float(tv.ravel()[2])
    return {"n": int(det.n), "rms_px": float(np.sqrt(np.mean(rpx ** 2))), "max_px": float(rpx.max()),
            "rms_mm": float(np.sqrt(np.mean(emm ** 2))), "max_mm": float(emm.max()),
            "span_true_mm": true_span, "span_err_mm": meas_span - true_span,
            "distance_mm": float(np.linalg.norm(tv)), "z_mm": z, "tilt_deg": tilt,
            "mm_per_px": z / calib.K[0, 0]}


def run_verify(calib: Calibration, spec: BoardSpec, cam, log_path: Path, window="camcal verify",
               max_preview_width=1600, headless_frames: Optional[int] = None) -> list[dict]:
    det = BoardDetector(spec)
    state = {"m": None, "det": None, "stop": False}
    hist: list[dict] = []
    logged: list[dict] = []

    def worker():
        last = -1
        while not state["stop"]:
            seq, frame, _ = cam.latest()
            if seq == last or frame is None:
                time.sleep(0.01)
                continue
            last = seq
            d = det.detect(frame)
            m = measure(calib, spec, d)
            state["det"], state["m"] = d, m
            if m:
                hist.append(m)
                del hist[:-30]

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    undist = False
    if headless_frames is None:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    n = 0
    try:
        while True:
            seq, frame, _ = cam.latest()
            if frame is None:
                continue
            if headless_frames is not None:
                time.sleep(0.3)
                n += 1
                if n >= headless_frames:
                    if state["m"]:
                        logged.append({**state["m"], "time": dt.datetime.now().isoformat(timespec="seconds")})
                    break
                continue
            img = calib.undistort_image(frame, 0.0) if undist else frame.copy()
            h, w = img.shape[:2]
            s = min(1.0, max_preview_width / w)
            view = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
            d, m = state["det"], state["m"]
            if d is not None and d.n and not undist:
                for x, y in d.corners:
                    cv2.circle(view, (int(x * s), int(y * s)), 3, GREEN, -1, cv2.LINE_AA)
            lines = [(f"{calib.mode.key}  model {calib.data.get('distortion_model')}  calib RMS {calib.data.get('rms_px', 0):.3f}px"
                      f"   view: {'UNDISTORTED' if undist else 'raw'}", WHITE)]
            if m:
                med = {k: float(np.median([x[k] for x in hist])) for k in ("rms_px", "rms_mm", "max_mm", "span_err_mm")}
                good = med["max_mm"] < 1.0
                lines += [
                    (f"corners {m['n']}  distance {m['distance_mm']:.0f} mm  tilt {m['tilt_deg']:.0f} deg  "
                     f"{m['mm_per_px']:.4f} mm/px", WHITE),
                    (f"reprojection RMS {m['rms_px']:.3f}px (median {med['rms_px']:.3f})", GREEN if med["rms_px"] < 0.5 else YELLOW),
                    (f"metric RMS {m['rms_mm']:.3f} mm  max {m['max_mm']:.3f} mm  (median max {med['max_mm']:.3f})", GREEN if good else RED),
                    (f"span {m['span_true_mm']:.1f} mm  error {m['span_err_mm']:+.3f} mm (median {med['span_err_mm']:+.3f})",
                     GREEN if abs(med["span_err_mm"]) < 1.0 else RED),
                ]
            else:
                lines.append(("board not detected (need >= 12 corners)", YELLOW))
            lines.append(("U undistort | S log measurement | Q quit", (150, 150, 150)))
            ov = view.copy()
            cv2.rectangle(ov, (0, 0), (min(view.shape[1], 1000), 28 * len(lines) + 14), (0, 0, 0), -1)
            view = cv2.addWeighted(ov, 0.55, view, 0.45, 0)
            for i, (t, c) in enumerate(lines):
                cv2.putText(view, t, (10, 28 + 28 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.62, c, 1, cv2.LINE_AA)
            cv2.imshow(window, view)
            k = cv2.waitKey(15) & 0xFF
            if k in (ord("q"), 27):
                break
            if k == ord("u"):
                undist = not undist
            if k == ord("s") and m:
                logged.append({**m, "time": dt.datetime.now().isoformat(timespec="seconds")})
    finally:
        state["stop"] = True
        th.join(timeout=3)
        if headless_frames is None:
            cv2.destroyWindow(window)
    if logged:
        old = json.loads(log_path.read_text()) if log_path.exists() else []
        log_path.write_text(json.dumps(old + logged, indent=1))
    return logged
