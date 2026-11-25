"""Calibration target definition, detection and metric object points.

Two target types are supported:

* ``charuco``      - chessboard with ArUco markers in the white squares
                     (recommended: works with partial views, so corners can be
                     pushed into the extreme image corners where lens
                     distortion is strongest; every corner has a unique ID).
* ``checkerboard`` - plain chessboard, detected with the sector-based
                     ``findChessboardCornersSB`` (whole board must be visible).

Object points are generated from the *measured* printed pitch, separately in
X and Y. Printers commonly scale the two paper axes differently by 0.1-0.5 %,
which on a 350 mm board is a 0.3-1.7 mm systematic error. Entering the measured
spans removes it.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

ARUCO_DICTS = {
    name: getattr(cv2.aruco, name)
    for name in dir(cv2.aruco)
    if name.startswith("DICT_")
}


@dataclass
class BoardSpec:
    type: str = "charuco"                 # "charuco" | "checkerboard"
    squares_x: int = 14                   # number of squares along X
    squares_y: int = 10                   # number of squares along Y
    square_mm: float = 25.0               # nominal square pitch
    marker_mm: float = 18.75              # ArUco marker side (charuco only)
    dictionary: str = "DICT_4X4_100"
    legacy_pattern: bool = False
    # Measured values (fill in after printing). If absent the nominal pitch is used.
    measured_span_x_mm: Optional[float] = None   # outer pattern width  = squares_x * pitch_x
    measured_span_y_mm: Optional[float] = None   # outer pattern height = squares_y * pitch_y
    name: str = ""
    notes: str = ""
    extra: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- pitch
    @property
    def pitch_x_mm(self) -> float:
        if self.measured_span_x_mm:
            return float(self.measured_span_x_mm) / self.squares_x
        return float(self.square_mm)

    @property
    def pitch_y_mm(self) -> float:
        if self.measured_span_y_mm:
            return float(self.measured_span_y_mm) / self.squares_y
        return float(self.square_mm)

    @property
    def is_measured(self) -> bool:
        return bool(self.measured_span_x_mm and self.measured_span_y_mm)

    @property
    def inner_cols(self) -> int:
        return self.squares_x - 1

    @property
    def inner_rows(self) -> int:
        return self.squares_y - 1

    @property
    def n_corners(self) -> int:
        return self.inner_cols * self.inner_rows

    # ---------------------------------------------------------------- io
    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "BoardSpec":
        data = json.loads(Path(path).read_text())
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    # ---------------------------------------------------------------- opencv
    def aruco_dict(self):
        return cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[self.dictionary])

    def cv_charuco_board(self, unit_mm: Optional[float] = None):
        """OpenCV CharucoBoard. Geometry is nominal; metric points come from object_points()."""
        sq = unit_mm if unit_mm is not None else self.square_mm
        mk = self.marker_mm * (sq / self.square_mm)
        board = cv2.aruco.CharucoBoard((self.squares_x, self.squares_y), sq, mk, self.aruco_dict())
        board.setLegacyPattern(self.legacy_pattern)
        return board

    def object_points(self, ids: np.ndarray) -> np.ndarray:
        """Metric 3-D points (mm, Z=0) for the given inner-corner IDs.

        Corner ID k sits at column k % inner_cols, row k // inner_cols, with the
        origin at the first inner corner. This matches OpenCV's ChArUco corner
        numbering and the row-major order of findChessboardCornersSB.
        """
        ids = np.asarray(ids, dtype=np.int64).reshape(-1)
        col = ids % self.inner_cols
        row = ids // self.inner_cols
        pts = np.zeros((len(ids), 3), np.float64)
        pts[:, 0] = col * self.pitch_x_mm
        pts[:, 1] = row * self.pitch_y_mm
        return pts

    def describe(self) -> str:
        meas = (f"measured pitch {self.pitch_x_mm:.4f} x {self.pitch_y_mm:.4f} mm"
                if self.is_measured else "NOT MEASURED - using nominal pitch")
        kind = (f"ChArUco {self.dictionary}, marker {self.marker_mm} mm"
                if self.type == "charuco" else "checkerboard")
        return (f"{kind}, {self.squares_x}x{self.squares_y} squares @ {self.square_mm} mm "
                f"({self.n_corners} inner corners), {meas}")


# =============================================================================
# Detection
# =============================================================================
@dataclass
class Detection:
    ids: np.ndarray            # (N,) int   inner-corner IDs
    corners: np.ndarray        # (N,2) float64 image points (px, full resolution)
    n_total: int               # total inner corners on the board
    marker_corners: Optional[list] = None
    marker_ids: Optional[np.ndarray] = None

    @property
    def n(self) -> int:
        return 0 if self.ids is None else len(self.ids)

    @property
    def fraction(self) -> float:
        return self.n / max(1, self.n_total)


def to_gray8(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype == np.uint16:
        img = (img.astype(np.float32) / 257.0 + 0.5).clip(0, 255).astype(np.uint8)
    elif img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    return img


def to_gray_f32(img: np.ndarray) -> np.ndarray:
    """Float gray in 0..255 scale, keeping the extra precision of 16-bit averages."""
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype == np.uint16:
        return img.astype(np.float32) / 257.0
    return img.astype(np.float32)


class BoardDetector:
    """Detects the board and returns sub-pixel inner corners.

    ChArUco refinement (``refine=True``), validated against rendered ground truth:
      1. OpenCV's ChArUco corners are only an initial guess (OpenCV 4.8 returns
         them with a systematic +0.5 px offset and occasional multi-pixel errors).
      2. Per-corner cornerSubPix with a half-window of ``SUBPIX_FRAC`` x the local
         square size: big enough for precision, small enough never to include the
         ArUco marker edges (which begin 12.5 % of a square away from the corner).
      3. Grid-consistency: each corner is predicted from its refined neighbours
         by a robust local homography; outliers are re-seeded at the prediction
         and refined again; corners that still disagree are dropped.
    Plain checkerboards use findChessboardCornersSB(ACCURACY), already sub-pixel exact.
    """

    SUBPIX_FRAC = 0.08
    CONSISTENCY_PX = 0.35

    def __init__(self, spec: BoardSpec, min_marker_perimeter_rate: float = 0.01):
        self.spec = spec
        if spec.type == "charuco":
            self.board = spec.cv_charuco_board()
            dp = cv2.aruco.DetectorParameters()
            dp.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_NONE  # chessboard corners refined below
            dp.minMarkerPerimeterRate = min_marker_perimeter_rate
            dp.adaptiveThreshWinSizeMin = 3
            dp.adaptiveThreshWinSizeMax = 53
            dp.adaptiveThreshWinSizeStep = 10
            cp = cv2.aruco.CharucoParameters()
            cp.minMarkers = 2          # each corner must be confirmed by both neighbouring markers
            cp.tryRefineMarkers = True
            self.detector = cv2.aruco.CharucoDetector(self.board, cp, dp)
        elif spec.type != "checkerboard":
            raise ValueError(f"unknown board type {spec.type!r}")

    # ------------------------------------------------------------------
    def detect(self, image: np.ndarray, refine: bool = True) -> Detection:
        g8 = to_gray8(image)
        if self.spec.type == "charuco":
            det = self._detect_charuco(g8)
            if refine and det.n >= 4:
                self._refine_charuco(to_gray_f32(image), det)
        else:
            det = self._detect_checker(g8)
        return det

    def detect_fast(self, image: np.ndarray, max_width: int = 1280) -> Detection:
        """Preview-rate detection on a downscaled copy; corners returned at full scale (approximate)."""
        h, w = image.shape[:2]
        s = min(1.0, max_width / float(w))
        small = image if s >= 1.0 else cv2.resize(image, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        g8 = to_gray8(small)
        if self.spec.type == "charuco":
            det = self._detect_charuco(g8)
        else:
            det = self._detect_checker(g8, fast=True)
        if det.n:
            det.corners = (det.corners + 0.5) / s - 0.5
        return det

    # ------------------------------------------------------------------
    def _detect_charuco(self, g8: np.ndarray) -> Detection:
        ch_corners, ch_ids, m_corners, m_ids = self.detector.detectBoard(g8)
        if ch_ids is None or len(ch_ids) == 0:
            return Detection(np.zeros(0, int), np.zeros((0, 2)), self.spec.n_corners,
                             m_corners, m_ids)
        ids = ch_ids.reshape(-1).astype(int)
        pts = ch_corners.reshape(-1, 2).astype(np.float64)
        order = np.argsort(ids)
        return Detection(ids[order], pts[order], self.spec.n_corners, m_corners, m_ids)

    def _detect_checker(self, g8: np.ndarray, fast: bool = False) -> Detection:
        size = (self.spec.inner_cols, self.spec.inner_rows)
        flags = cv2.CALIB_CB_NORMALIZE_IMAGE
        if not fast:
            flags |= cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
        ok, corners = cv2.findChessboardCornersSB(g8, size, flags=flags)
        if not ok:
            return Detection(np.zeros(0, int), np.zeros((0, 2)), self.spec.n_corners)
        pts = corners.reshape(-1, 2).astype(np.float64)
        return Detection(np.arange(len(pts)), pts, self.spec.n_corners)

    # ------------------------------------------------------------------
    def _subpix(self, gray_f, pts, halves):
        out = pts.copy()
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5)
        for hw in np.unique(halves):
            sel = halves == hw
            p = pts[sel].astype(np.float32).reshape(-1, 1, 2).copy()
            cv2.cornerSubPix(gray_f, p, (int(hw), int(hw)), (-1, -1), crit)
            out[sel] = p.reshape(-1, 2)
        return out

    def _refine_charuco(self, gray_f: np.ndarray, det: Detection) -> None:
        spec = self.spec
        sq = local_square_px(det, spec, aligned=True)
        halves = np.clip(np.floor(self.SUBPIX_FRAC * sq), 2, 20).astype(int)
        pts = self._subpix(gray_f, det.corners, halves)
        keep = np.ones(det.n, bool)
        # Outlier limit adapts to the image: a local grid prediction is never exact on a real lens
        # (distortion curvature, paper texture, compression), and the error grows with square size.
        # This step only removes GROSS errors; the calibration's own robust rejection handles the rest.
        def limit(dev, ok):
            base = float(np.median(dev[ok])) if ok.sum() >= 5 else 0.0
            return np.maximum(max(self.CONSISTENCY_PX, 4.0 * base), 0.01 * sq)
        for _ in range(3):
            pred, ok = predict_from_neighbours(det.ids, pts, spec, keep)
            dev = np.linalg.norm(pts - pred, axis=1)
            bad = ok & (dev > limit(dev, ok))
            if not bad.any():
                break
            pts[bad] = self._subpix(gray_f, pred[bad], halves[bad])
        pred, ok = predict_from_neighbours(det.ids, pts, spec, keep)
        if (~ok).any():  # board-edge corners: verify with a wider neighbourhood
            pred3, ok3 = predict_from_neighbours(det.ids, pts, spec, keep, radius=3)
            pred = np.where((~ok & ok3)[:, None], pred3, pred)
            ok = ok | ok3
        dev = np.linalg.norm(pts - pred, axis=1)
        keep &= ~(ok & (dev > limit(dev, ok)))
        # corners that cannot be verified at all are kept only if refinement barely moved them
        moved = np.linalg.norm(pts - det.corners, axis=1)
        keep &= ok | (moved < 0.75)
        det.ids, det.corners = det.ids[keep], pts[keep]


def predict_from_neighbours(ids, pts, spec: BoardSpec, valid=None, radius: int = 2):
    """Predict each corner from neighbours (|dc|,|dr| <= radius, itself excluded) via robust homography."""
    ids = np.asarray(ids)
    valid = np.ones(len(ids), bool) if valid is None else valid
    cols, rows = ids % spec.inner_cols, ids // spec.inner_cols
    pred = pts.copy()
    ok = np.zeros(len(ids), bool)
    for k in range(len(ids)):
        sel = (np.abs(cols - cols[k]) <= radius) & (np.abs(rows - rows[k]) <= radius) & valid
        sel[k] = False
        if sel.sum() < 6 or len(np.unique(cols[sel])) < 2 or len(np.unique(rows[sel])) < 2:
            continue
        src = np.stack([cols[sel], rows[sel]], 1).astype(np.float64)
        Hm, _ = cv2.findHomography(src, pts[sel], cv2.LMEDS if sel.sum() >= 8 else 0)
        if Hm is None:
            continue
        q = Hm @ np.array([cols[k], rows[k], 1.0])
        pred[k] = q[:2] / q[2]
        ok[k] = True
    return pred, ok


def local_square_px(det: Detection, spec: BoardSpec, aligned: bool = False) -> np.ndarray:
    """Square size in pixels at each corner (min distance to a grid neighbour).

    aligned=True returns one value per detected corner (median used where a corner has no neighbour).
    """
    if det.n < 2:
        return np.full(max(det.n, 1), 20.0)
    lut = {int(i): p for i, p in zip(det.ids, det.corners)}
    out = []
    for i, p in zip(det.ids, det.corners):
        i = int(i)
        c, r = i % spec.inner_cols, i // spec.inner_cols
        d = []
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cc, rr = c + dc, r + dr
            if 0 <= cc < spec.inner_cols and 0 <= rr < spec.inner_rows:
                q = lut.get(rr * spec.inner_cols + cc)
                if q is not None:
                    d.append(np.linalg.norm(q - p))
        out.append(min(d) if d else np.nan)
    out = np.array(out)
    if np.isnan(out).all():
        out[:] = 20.0
    med = np.nanmedian(out)
    if aligned:
        return np.where(np.isnan(out), med, out)
    return out[~np.isnan(out)]


# =============================================================================
# Presets
# =============================================================================
PRESETS = {
    # A3 landscape (420 x 297 mm) - recommended for working distances 0.4 - 1.5 m
    "charuco_a3": BoardSpec(type="charuco", squares_x=14, squares_y=10, square_mm=25.0,
                            marker_mm=18.75, dictionary="DICT_4X4_100", name="charuco_a3"),
    # A4 landscape (297 x 210 mm) - working distances 0.2 - 0.8 m
    "charuco_a4": BoardSpec(type="charuco", squares_x=11, squares_y=8, square_mm=22.0,
                            marker_mm=16.5, dictionary="DICT_4X4_50", name="charuco_a4"),
    # Plain checkerboard alternatives (odd x even squares -> no 180 deg ambiguity)
    "checker_a3": BoardSpec(type="checkerboard", squares_x=15, squares_y=10, square_mm=23.0,
                            marker_mm=0.0, name="checker_a3"),
    "checker_a4": BoardSpec(type="checkerboard", squares_x=12, squares_y=9, square_mm=19.0,
                            marker_mm=0.0, name="checker_a4"),
}
