"""Derive calibrations for further modes from an already-calibrated mode - verified on the camera.

The module's ISP produces every mode from the same sensor by scaling (and for 1280x960 cropping).
If a mode is an exact affine re-sampling of a calibrated mode, its intrinsics follow exactly:
    x_test + 0.5 = s * (x_ref + 0.5) + b        (pixel-centre convention, same for y)
    fx' = s fx,   cx' = s (cx + 0.5) + bx - 0.5,  distortion unchanged (normalised coordinates).
This is NOT assumed: with the camera resting on the board, averaged frames are grabbed in the
reference mode, the test mode, and the reference mode again (proves nothing moved); the mapping
(s, bx, by) is fitted on the ChArUco corner IDs and must match the hardware scaling with
sub-pixel residuals, otherwise nothing is written.

    python3 -m camcal derive --ref 4k_mjpg --test 4k_yuyv
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

from .board import BoardDetector, BoardSpec
from .camera import Camera, Mode

log = logging.getLogger("camcal")


def _settle_exposure(cam: Camera, cs, mode: Mode, target_p99: float = 225.0) -> None:
    """Modes differ in ISP gain (YUYV is far brighter at the same exposure): adjust so whites don't clip."""
    if cs is None:
        return
    for _ in range(5):
        f = cam.wait_frames(1, timeout=max(10.0, 4.0 / max(mode.fps, 0.5)))[0]
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        p99 = float(np.percentile(g, 99))
        if 200 <= p99 <= 245:
            return
        cur = cs.current().get("exposure_time_absolute", 150)
        new = int(np.clip(round(cur * target_p99 / max(p99, 1.0) * (0.6 if p99 >= 254 else 1.0)), 2, 1000))
        if new == cur:
            return
        cs.set("exposure_time_absolute", new)
        time.sleep(max(0.5, 2.5 / max(mode.fps, 0.5)))


def grab_corners(device: str, mode: Mode, det: BoardDetector, n: int = 6, cs=None) -> tuple[np.ndarray, np.ndarray, int]:
    cam = Camera(device, mode)
    try:
        time.sleep(max(1.0, 2.0 / max(mode.fps, 0.5)))
        _settle_exposure(cam, cs, mode)
        frames = cam.wait_frames(n, timeout=max(10.0, 3.0 * n / max(mode.fps, 0.5)))
    finally:
        cam.release()
    mean = np.mean([f.astype(np.float32) for f in frames], axis=0)
    g = cv2.cvtColor(mean, cv2.COLOR_BGR2GRAY)
    d = det.detect(np.clip(g * 257.0 + 0.5, 0, 65535).astype(np.uint16))
    return d.ids, d.corners, len(frames)


def fit_mapping(ids_r, pr, ids_t, pt) -> dict:
    c, ia, ib = np.intersect1d(ids_r, ids_t, return_indices=True)
    if len(c) < 20:
        raise RuntimeError(f"only {len(c)} common corners - is the board fully in view in both modes?")
    a, b = pr[ia] + 0.5, pt[ib] + 0.5
    A = np.zeros((2 * len(c), 3)); y = np.zeros(2 * len(c))
    A[0::2, 0], A[0::2, 1] = a[:, 0], 1.0
    A[1::2, 0], A[1::2, 2] = a[:, 1], 1.0
    y[0::2], y[1::2] = b[:, 0], b[:, 1]
    sol, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = (A @ sol - y).reshape(-1, 2)
    return {"s": float(sol[0]), "bx": float(sol[1]), "by": float(sol[2]), "n": int(len(c)),
            "residual_rms_px": float(np.sqrt((res ** 2).sum(1).mean())),
            "residual_max_px": float(np.linalg.norm(res, axis=1).max())}


def verify_mapping(device, ref: Mode, test: Mode, spec: BoardSpec, expect: tuple[float, float, float], cs=None) -> dict:
    det = BoardDetector(spec)
    i1, p1, _ = grab_corners(device, ref, det, cs=cs)
    it, pt, nt = grab_corners(device, test, det, n=4 if test.fps < 5 else 6, cs=cs)
    i2, p2, _ = grab_corners(device, ref, det, cs=cs)
    still = fit_mapping(i1, p1, i2, p2)              # ref before vs after: must be identity
    m = fit_mapping(i1, (p1 + 0.0), it, pt)
    s_e, bx_e, by_e = expect
    ok_still = abs(still["s"] - 1) < 2e-4 and abs(still["bx"]) < 0.3 and abs(still["by"]) < 0.3
    ok_map = abs(m["s"] - s_e) < 2e-3 and abs(m["bx"] - bx_e) < 4.0 and abs(m["by"] - by_e) < 4.0 \
        and m["residual_rms_px"] < 0.35 and m["n"] >= 40
    # mapping actually used: exact hardware scale, offset as MEASURED (the ISP may start its window a pixel off)
    use = (s_e, m["bx"], m["by"])
    return {"ref": ref.key, "test": test.key, "fitted": m, "mapping_used": list(use), "expected": {"s": s_e, "bx": bx_e, "by": by_e},
            "camera_still_check": still, "camera_still": ok_still, "matches_hardware_scaling": ok_map,
            "test_frames_averaged": nt}


def write_derived(ref_json: Path, test: Mode, mapping: tuple[float, float, float], verification: dict,
                  out_root: Path) -> Path:
    from .calibrate import fov_deg
    r = json.loads(ref_json.read_text())
    s, bx, by = mapping
    K = np.array(r["camera_matrix"], float); D = np.array(r["dist_coeffs"], float).ravel()
    K2 = K.copy()
    K2[0, 0] *= s; K2[1, 1] *= s
    K2[0, 2] = s * (K[0, 2] + 0.5) + bx - 0.5
    K2[1, 2] = s * (K[1, 2] + 0.5) + by - 0.5
    size = (test.width, test.height)
    key = test.key
    out = out_root / key
    out.mkdir(parents=True, exist_ok=True)
    nk0, roi0 = cv2.getOptimalNewCameraMatrix(K2, D, size, 0.0, size)
    nk1, roi1 = cv2.getOptimalNewCameraMatrix(K2, D, size, 1.0, size)
    fov = fov_deg(K2, D, size)
    mmpp = {str(z): {"mm_per_px_x": z / K2[0, 0], "mm_per_px_y": z / K2[1, 1],
                     "field_of_view_mm": [z * size[0] / K2[0, 0], z * size[1] / K2[1, 1]]}
            for z in (150, 250, 400, 600, 800, 1000, 1500)}
    hm = r.get("holdout_metric", {})
    d = {"schema": "camcal/1", "derived": True, "mode": test.as_dict(), "mode_key": key, "image_size": list(size),
         "distortion_model": r["distortion_model"], "camera_matrix": K2.tolist(), "dist_coeffs": D.tolist(),
         "new_camera_matrix_alpha0": nk0.tolist(), "new_camera_matrix_alpha1": nk1.tolist(),
         "fov_deg": fov, "metric_resolution": mmpp, "rms_px": r["rms_px"] * s,
         "grade": "PASS" if r.get("grade") == "PASS" else r.get("grade"),
         "derived_from": {"calibration": f"calibrations/{ref_json.parent.name}/{ref_json.name}", "mode": r["mode_key"], "mapping_s_bx_by": [s, bx, by],
                          "reference_grade": r.get("grade"), "reference_holdout_metric": hm},
         "verification": verification, "geometry_controls": r.get("geometry_controls", {}),
         "created": dt.datetime.now().isoformat(timespec="seconds"),
         "issues": [f"PASS (derived): exact re-sampling of {r['mode_key']} verified on the camera - mapping residual "
                    f"{verification['fitted']['residual_rms_px']:.3f} px RMS over {verification['fitted']['n']} corners; "
                    f"reference accuracy {hm.get('holdout_mm_rms', float('nan')):.3f} mm RMS / "
                    f"{hm.get('holdout_mm_p95', float('nan')):.3f} mm p95"]}
    base = out / f"camera_{key}"
    (base.with_suffix(".json")).write_text(json.dumps(d, indent=1))
    fs = cv2.FileStorage(str(base.with_suffix(".yaml")), cv2.FILE_STORAGE_WRITE)
    fs.write("calibration_time", d["created"]); fs.write("mode_key", key)
    fs.write("image_width", size[0]); fs.write("image_height", size[1])
    fs.write("pixel_format", test.fourcc); fs.write("fps", float(test.fps))
    fs.write("distortion_model", d["distortion_model"])
    fs.write("camera_matrix", K2); fs.write("distortion_coefficients", D.reshape(1, -1))
    fs.write("new_camera_matrix_alpha0", nk0); fs.write("new_camera_matrix_alpha1", nk1)
    fs.write("rms_reprojection_px", float(d["rms_px"])); fs.write("grade", d["grade"])
    fs.write("derived_from", r["mode_key"])
    fs.write("geometry_controls", json.dumps(d["geometry_controls"]))
    fs.release()
    (out / f"camera_{key}_summary.md").write_text(
        f"# Calibration {key}  -  grade **{d['grade']}** (derived)\n\n"
        f"- derived from `{r['mode_key']}` (grade {r.get('grade')}): x' + 0.5 = {s:.6f} (x + 0.5) + ({bx:.3f}, {by:.3f})\n"
        f"- verified on the camera: mapping residual {verification['fitted']['residual_rms_px']:.3f} px RMS "
        f"(max {verification['fitted']['residual_max_px']:.3f}) over {verification['fitted']['n']} corners; "
        f"fitted s = {verification['fitted']['s']:.5f}\n"
        f"- fx {K2[0, 0]:.2f}  fy {K2[1, 1]:.2f}  cx {K2[0, 2]:.2f}  cy {K2[1, 2]:.2f}\n"
        f"- distortion ({d['distortion_model']}): " + " ".join(f"{v:+.6f}" for v in D) + "\n"
        f"- FOV {fov['horizontal']:.2f} x {fov['vertical']:.2f} deg\n"
        f"- accuracy (reference, held-out): {hm.get('holdout_mm_rms', float('nan')):.3f} mm RMS, "
        f"{hm.get('holdout_mm_p95', float('nan')):.3f} mm p95\n")
    return out
