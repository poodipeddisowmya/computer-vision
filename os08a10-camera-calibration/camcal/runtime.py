"""Runtime API for vision projects.

    from camcal.runtime import CalibrationStore

    store = CalibrationStore("calibrations")                 # all calibrated modes
    calib = store.for_mode(3840, 2160, "MJPG")              # exact mode or exception
    cam   = calib.open_camera("/dev/video0")                # verifies mode + geometry controls
    seq, frame, t = cam.latest()

    # Best accuracy: detect features on the RAW image, then undistort only the points
    pts_ud = calib.undistort_points(pts_px)                  # pixel coords in the ideal pinhole image
    # Or rectify whole images (precomputed fixed-point maps, fast)
    rect = calib.undistort_image(frame, alpha=0.0)
    # Metric: pixels -> mm on a known plane (e.g. conveyor / table) given its pose
    xy_mm = calib.pixels_to_plane(pts_px, rvec, tvec)

Design rules enforced here:
  * a calibration is valid ONLY for the exact (width, height, pixel format) it was made in;
  * geometry-affecting controls (zoom/pan/tilt/focus/flip...) must match the calibration;
  * photometric controls are never touched unless the caller passes them explicitly,
    so opening the camera through this API never changes the settings another
    project relies on.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .camera import Camera, Mode
from .v4l2 import V4L2Device


class CalibrationMismatch(RuntimeError):
    pass


class Calibration:
    def __init__(self, data: dict, path: Optional[Path] = None):
        self.data = data
        self.path = path
        self.K = np.array(data["camera_matrix"], np.float64)
        self.D = np.array(data["dist_coeffs"], np.float64).reshape(-1)
        self.size = tuple(int(x) for x in data["image_size"])
        self.mode = Mode.from_dict(data["mode"]) if "fourcc" in data.get("mode", {}) else Mode(*self.size)
        self.geometry_controls: dict = data.get("geometry_controls", {}) or {}
        self._maps = {}

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, path: str | Path) -> "Calibration":
        path = Path(path)
        if path.suffix == ".json":
            return cls(json.loads(path.read_text()), path)
        fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
        d = {"camera_matrix": fs.getNode("camera_matrix").mat().tolist(),
             "dist_coeffs": fs.getNode("distortion_coefficients").mat().ravel().tolist(),
             "image_size": [int(fs.getNode("image_width").real()), int(fs.getNode("image_height").real())],
             "mode": {"width": int(fs.getNode("image_width").real()), "height": int(fs.getNode("image_height").real()),
                      "fourcc": fs.getNode("pixel_format").string(), "fps": fs.getNode("fps").real()},
             "geometry_controls": json.loads(fs.getNode("geometry_controls").string() or "{}"),
             "distortion_model": fs.getNode("distortion_model").string(),
             "rms_px": fs.getNode("rms_reprojection_px").real(),
             "grade": fs.getNode("grade").string()}
        fs.release()
        return cls(d, path)

    # ------------------------------------------------------------------ checks
    def check_frame(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        if (w, h) != self.size:
            raise CalibrationMismatch(f"frame is {w}x{h}, calibration is for {self.size[0]}x{self.size[1]}")

    def check_device(self, device: str, strict: bool = True) -> dict:
        """Compare geometry controls of the live device with the calibration."""
        with V4L2Device(device) as d:
            cur = d.snapshot()
        diff = {k: (v, cur.get(k)) for k, v in self.geometry_controls.items() if cur.get(k) != v}
        if diff and strict:
            raise CalibrationMismatch(f"geometry controls differ from calibration (calibrated, live): {diff}")
        # Edge-profile controls do not change intrinsics but shift sub-pixel edge/corner positions slightly.
        during = self.data.get("controls_during_capture", {}) or {}
        soft = {k: (during[k], cur.get(k)) for k in ("sharpness", "gamma", "contrast")
                if k in during and k in cur and cur[k] != during[k]}
        if soft:
            import logging
            logging.getLogger("camcal").warning(
                "edge-profile controls differ from calibration (calibrated, live): %s - keep them identical "
                "for best sub-pixel repeatability", soft)
        return diff

    def open_camera(self, device: str, controls: Optional[dict] = None, strict: bool = True) -> Camera:
        """Open in the calibrated mode. Only `controls` you pass are written to the device."""
        if controls:
            with V4L2Device(device) as d:
                problems = d.apply(controls)
            if problems and strict:
                raise RuntimeError(f"could not apply controls {problems}")
        self.check_device(device, strict=strict)
        return Camera(device, self.mode)

    # ------------------------------------------------------------------ geometry
    def new_camera_matrix(self, alpha: float = 0.0) -> np.ndarray:
        K, _ = cv2.getOptimalNewCameraMatrix(self.K, self.D, self.size, alpha, self.size)
        return K

    def maps(self, alpha: float = 0.0):
        if alpha not in self._maps:
            P = self.new_camera_matrix(alpha)
            m1, m2 = cv2.initUndistortRectifyMap(self.K, self.D, None, P, self.size, cv2.CV_16SC2)
            self._maps[alpha] = (m1, m2, P)
        return self._maps[alpha]

    def undistort_image(self, img: np.ndarray, alpha: float = 0.0, interpolation=cv2.INTER_LINEAR) -> np.ndarray:
        """alpha=0: only valid pixels (cropped, no black border); alpha=1: keep all source pixels."""
        self.check_frame(img)
        m1, m2, _ = self.maps(alpha)
        return cv2.remap(img, m1, m2, interpolation)

    def undistort_points(self, pts: np.ndarray, P: Optional[np.ndarray] = None) -> np.ndarray:
        """Raw pixel coords -> ideal (distortion-free) pixel coords under P (default: K). High-precision iterative."""
        pts = np.asarray(pts, np.float64).reshape(-1, 1, 2)
        crit = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 40, 1e-10)
        return cv2.undistortPointsIter(pts, self.K, self.D, None, self.K if P is None else P, crit).reshape(-1, 2)

    def pixels_to_rays(self, pts: np.ndarray) -> np.ndarray:
        """Unit-depth rays (x, y, 1) in the camera frame."""
        pts = np.asarray(pts, np.float64).reshape(-1, 1, 2)
        crit = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 40, 1e-10)
        n = cv2.undistortPointsIter(pts, self.K, self.D, None, None, crit).reshape(-1, 2)
        return np.column_stack([n, np.ones(len(n))])

    def pixels_to_plane(self, pts: np.ndarray, rvec, tvec) -> np.ndarray:
        """Intersect pixel rays with the plane Z=0 of a frame given by (rvec, tvec) -> (N,2) in that frame's units."""
        R, _ = cv2.Rodrigues(np.asarray(rvec, np.float64))
        t = np.asarray(tvec, np.float64).reshape(3)
        rays = self.pixels_to_rays(pts)
        n = R[:, 2]
        s = (n @ t) / (rays @ n)
        Pc = rays * s[:, None]
        Pw = (R.T @ (Pc - t).T).T
        return Pw[:, :2]

    def project(self, obj_pts: np.ndarray, rvec, tvec) -> np.ndarray:
        p, _ = cv2.projectPoints(np.asarray(obj_pts, np.float64).reshape(-1, 1, 3), rvec, tvec, self.K, self.D)
        return p.reshape(-1, 2)

    def mm_per_px(self, distance_mm: float) -> tuple[float, float]:
        return distance_mm / self.K[0, 0], distance_mm / self.K[1, 1]

    def __repr__(self):
        return (f"Calibration({self.mode.key}, fx={self.K[0, 0]:.2f}, fy={self.K[1, 1]:.2f}, "
                f"cx={self.K[0, 2]:.2f}, cy={self.K[1, 2]:.2f}, model={self.data.get('distortion_model')}, "
                f"rms={self.data.get('rms_px', float('nan')):.4f}px)")


class CalibrationStore:
    """All calibrations in a folder (calibrations/<mode_key>/camera_<mode_key>.json)."""

    def __init__(self, root: str | Path = "calibrations"):
        self.root = Path(root)
        self.items: dict[str, Path] = {}
        for p in sorted(self.root.glob("*/camera_*.json")):
            if p.name.endswith("_per_view.json"):
                continue
            self.items[p.stem.replace("camera_", "")] = p

    def modes(self) -> list[str]:
        return sorted(self.items)

    def for_mode(self, width: int, height: int, fourcc: str = "MJPG") -> Calibration:
        key = f"{width}x{height}_{fourcc.upper().replace('YUY2', 'YUYV')}"
        if key not in self.items:
            raise CalibrationMismatch(f"no calibration for {key}; available: {self.modes()}. "
                                      "Each resolution/format needs its own calibration.")
        return Calibration.load(self.items[key])

    def for_frame(self, frame: np.ndarray, fourcc: str = "MJPG") -> Calibration:
        h, w = frame.shape[:2]
        return self.for_mode(w, h, fourcc)
