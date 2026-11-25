"""Calibration engine.

Pipeline
  1. Detect the target in every captured image (cached per session).
  2. Reject degenerate views (too few / collinear corners).
  3. Robust fit: point-level then view-level outlier rejection.
  4. Model selection by k-fold cross-validation over views (held-out
     reprojection error), so the distortion model is chosen for prediction
     quality, not for the lowest training RMS (which always favours the most
     parameters and over-fits).
  5. Final fit with parameter standard deviations (calibrateCameraExtended).
  6. Bootstrap over views -> per-pixel uncertainty of the undistortion map.
  7. Coverage / tilt-diversity / corner-region analysis, quality grade.
  8. Outputs: OpenCV YAML (C++/Python), full JSON, per-view CSV, report PNG/MD.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .board import BoardDetector, BoardSpec

log = logging.getLogger("camcal")

MODELS = {
    "brown_k1k2": cv2.CALIB_FIX_K3,
    "brown_k1k2k3": 0,
    "rational": cv2.CALIB_RATIONAL_MODEL,
    "rational_thinprism": cv2.CALIB_RATIONAL_MODEL | cv2.CALIB_THIN_PRISM_MODEL,
}
MODEL_ORDER = ["brown_k1k2", "brown_k1k2k3", "rational", "rational_thinprism"]  # simple -> complex
DEFAULT_CANDIDATES = ["brown_k1k2", "brown_k1k2k3", "rational"]  # thin-prism: opt-in (--models)
STD_NAMES = ["fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2", "k3", "k4", "k5", "k6",
             "s1", "s2", "s3", "s4", "tau_x", "tau_y"]
# Search fits (CV / bootstrap / rejection) use CRIT; the final reported fit uses CRIT_FINAL.
# Verified on ground truth: identical parameters to 1e-6 px RMS, 2-5x faster.
CRIT = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 60, 1e-7)
CRIT_FINAL = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 150, 1e-10)

# Sensor facts (OmniVision OS08A10 product brief v1.6)
WORKERS = max(1, (os.cpu_count() or 4))
SENSOR_ACTIVE_PX = (3840, 2160)
SENSOR_PIXEL_UM = 2.0


@dataclass
class View:
    name: str
    ids: np.ndarray
    img: np.ndarray       # (N,2)
    obj: np.ndarray = None  # (N,3) filled from BoardSpec
    meta: dict = field(default_factory=dict)

    @property
    def n(self):
        return len(self.ids)


# =============================================================================
# Detection (cached)
# =============================================================================
def _spec_hash(spec: BoardSpec) -> str:
    key = f"{spec.type}|{spec.squares_x}|{spec.squares_y}|{spec.square_mm}|{spec.marker_mm}|{spec.dictionary}|{spec.legacy_pattern}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def load_image(path: Path) -> np.ndarray:
    return cv2.imread(str(path), cv2.IMREAD_UNCHANGED)


def detect_session(session: Path, spec: BoardSpec, workers: int = 4, force: bool = False) -> tuple[list[View], dict]:
    images = sorted(session.glob("img_*_mean.png")) or sorted(session.glob("img_*.png"))
    images = [p for p in images if not p.name.endswith("_color.png")]
    cache_p = session / "detections.json"
    cache = {}
    if cache_p.exists() and not force:
        c = json.loads(cache_p.read_text())
        if c.get("board_hash") == _spec_hash(spec):
            cache = c.get("views", {})
    detector = BoardDetector(spec)
    size = None

    def work(p: Path):
        im = load_image(p)
        if im is None:
            return p.name, None, None
        shp = im.shape[:2]
        if p.name in cache:
            return p.name, cache[p.name], shp
        d = detector.detect(im)
        return p.name, {"ids": d.ids.tolist(), "corners": d.corners.tolist()}, shp

    results = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for name, det, shp in ex.map(work, images):
            if det is None:
                log.warning("unreadable image %s", name)
                continue
            if size is None:
                size = (shp[1], shp[0])
            elif (shp[1], shp[0]) != size:
                raise ValueError(f"{name}: size {shp[::-1]} differs from {size} - one session = one mode")
            results[name] = det
    cache_p.write_text(json.dumps({"board_hash": _spec_hash(spec), "views": results}))
    views = [View(n, np.array(d["ids"], int), np.array(d["corners"], float).reshape(-1, 2))
             for n, d in sorted(results.items())]
    return views, {"image_size": size, "n_images": len(images)}


def view_is_usable(v: View, spec: BoardSpec, min_corners: int) -> Optional[str]:
    if v.n < min_corners:
        return f"only {v.n} corners (< {min_corners})"
    cols = np.unique(v.ids % spec.inner_cols)
    rows = np.unique(v.ids // spec.inner_cols)
    if len(cols) < 3 or len(rows) < 3:
        return "corners span < 3 rows/cols (degenerate homography)"
    return None


# =============================================================================
# Core fitting
# =============================================================================
def _calib(views: list[View], size, model: str, K0=None, D0=None, extended=False):
    if K0 is None and any(np.abs(v.obj[:, 2]).max() > 1e-9 for v in views):
        # self-calibrated (non-planar) board: OpenCV needs an initial guess -> planar approximation first
        flat = [View(v.name, v.ids, v.img, v.obj * np.array([1.0, 1.0, 0.0]), v.meta) for v in views]
        g = _calib(flat, size, model)
        K0, D0 = g["K"], g["D"]
    flags = MODELS[model]
    K = None if K0 is None else K0.copy()
    D = None if D0 is None else D0.copy()
    if K0 is not None:
        flags |= cv2.CALIB_USE_INTRINSIC_GUESS
    obj = [v.obj.astype(np.float32).reshape(-1, 1, 3) for v in views]
    img = [v.img.astype(np.float32).reshape(-1, 1, 2) for v in views]
    if extended:
        rms, K, D, rv, tv, sdi, sde, pve = cv2.calibrateCameraExtended(obj, img, size, K, D, flags=flags,
                                                                       criteria=CRIT_FINAL)
        return dict(rms=rms, K=K, D=D.reshape(-1), rvecs=rv, tvecs=tv, std_int=sdi.reshape(-1),
                    std_ext=sde.reshape(-1), per_view=pve.reshape(-1))
    rms, K, D, rv, tv = cv2.calibrateCamera(obj, img, size, K, D, flags=flags, criteria=CRIT)
    return dict(rms=rms, K=K, D=D.reshape(-1), rvecs=rv, tvecs=tv)


def residuals(view: View, K, D, rvec, tvec) -> np.ndarray:
    proj, _ = cv2.projectPoints(view.obj.reshape(-1, 1, 3), rvec, tvec, K, D)
    return proj.reshape(-1, 2) - view.img


def solve_pose(view: View, K, D):
    ok, rv, tv = cv2.solvePnP(view.obj, view.img, K, D, flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        ok, rv, tv = cv2.solvePnP(view.obj, view.img, K, D, flags=cv2.SOLVEPNP_ITERATIVE)
    rv, tv = cv2.solvePnPRefineLM(view.obj, view.img, K, D, rv, tv)
    return rv, tv


def robust_sigma(x: np.ndarray) -> float:
    med = np.median(x)
    return float(1.4826 * np.median(np.abs(x - med))) or 1e-9


def reject_outliers(views: list[View], size, model: str, max_view_frac: float = 0.15,
                    point_floor_px: float = 0.75) -> tuple[list[View], list[dict]]:
    """Point-level then view-level robust rejection. Returns (kept views, rejection log)."""
    log_rej = []
    n0 = len(views)
    for it in range(4):
        r = _calib(views, size, model)
        all_res, per_view = [], []
        for v, rv, tv in zip(views, r["rvecs"], r["tvecs"]):
            e = np.linalg.norm(residuals(v, r["K"], r["D"], rv, tv), axis=1)
            all_res.append(e)
            per_view.append(float(np.sqrt(np.mean(e ** 2))))
        flat = np.concatenate(all_res)
        pt_thr = max(point_floor_px, float(np.median(flat) + 6.0 * robust_sigma(flat)))
        changed = False
        # --- point level (isolated mis-detections)
        for v, e in zip(views, all_res):
            bad = e > pt_thr
            if bad.any() and (~bad).sum() >= 12:
                log_rej.append({"view": v.name, "type": "points", "n": int(bad.sum()),
                                "ids": v.ids[bad].tolist(), "max_px": float(e.max()), "threshold_px": pt_thr})
                v.ids, v.img, v.obj = v.ids[~bad], v.img[~bad], v.obj[~bad]
                changed = True
        # --- view level (blur, motion, board bending, wrong exposure)
        pv = np.array(per_view)
        thr = max(0.25, float(np.median(pv) + 4.0 * robust_sigma(pv)), 2.5 * float(np.median(pv)))
        worst = int(np.argmax(pv))
        if pv[worst] > thr and (n0 - len(views) + 1) <= max_view_frac * n0 and len(views) > 12:
            log_rej.append({"view": views[worst].name, "type": "view", "rms_px": float(pv[worst]),
                            "threshold_px": thr})
            views = views[:worst] + views[worst + 1:]
            changed = True
        if not changed:
            break
    return views, log_rej


def plane_reconstruction_error_mm(v: View, K, D, rv, tv) -> np.ndarray:
    """Back-project the detected corners onto the fitted board plane; distance to true position (mm)."""
    n = cv2.undistortPoints(v.img.reshape(-1, 1, 2), K, D).reshape(-1, 2)
    rays = np.column_stack([n, np.ones(len(n))])
    R, _ = cv2.Rodrigues(rv)
    t = tv.reshape(3)
    nrm = R[:, 2]
    z = v.obj[:, 2] if v.obj.shape[1] > 2 else 0.0      # self-calibrated board: each corner at its own height
    s = (z + nrm @ t) / (rays @ nrm)
    Pw = (R.T @ (rays * s[:, None] - t).T).T
    return np.linalg.norm(Pw[:, :2] - v.obj[:, :2], axis=1)


def cross_validate(views: list[View], size, model: str, folds: int = 5, seed: int = 0) -> dict:
    """k-fold over views: fit intrinsics on k-1 folds, solve only the pose of held-out views.

    Also reports the metric (mm) reconstruction error of held-out views: their corners are
    back-projected with intrinsics that never saw them and compared with the true board layout.
    """
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(views))
    parts = np.array_split(idx, min(folds, len(views)))

    def fold(test):
        tset = set(int(i) for i in test)
        train = [views[i] for i in idx if int(i) not in tset]
        if len(train) < 6:
            return None
        r = _calib(train, size, model)
        px, mm, dist = [], [], []
        for i in test:
            v = views[i]
            rv, tv = solve_pose(v, r["K"], r["D"])
            px.append(np.linalg.norm(residuals(v, r["K"], r["D"], rv, tv), axis=1))
            mm.append(plane_reconstruction_error_mm(v, r["K"], r["D"], rv, tv))
            dist.append(float(np.linalg.norm(tv)))
        return np.concatenate(px), np.concatenate(mm), dist

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:   # OpenCV releases the GIL
        got = [g for g in ex.map(fold, parts) if g is not None]
    e = np.concatenate([g[0] for g in got])
    m = np.concatenate([g[1] for g in got])
    d = [x for g in got for x in g[2]]
    return {"cv_rms": float(np.sqrt(np.mean(e ** 2))), "cv_p95": float(np.percentile(e, 95)),
            "holdout_mm_rms": float(np.sqrt(np.mean(m ** 2))), "holdout_mm_p95": float(np.percentile(m, 95)),
            "holdout_mm_max": float(m.max()), "holdout_distance_mm_median": float(np.median(d))}


def with_aspect(views: list[View], a: float) -> list[View]:
    """Copies of views whose board Y coordinates are scaled by `a` (X untouched)."""
    return [View(v.name, v.ids, v.img, v.obj * np.array([1.0, a, 1.0]), v.meta) for v in views]


def estimate_board_aspect(views: list[View], size, model: str = "brown_k1k2k3", span: float = 0.006) -> dict:
    """Estimate the printed board's Y/X scale ratio from the images themselves.

    A planar target stretched differently in X and Y cannot be explained by any
    pinhole camera once the board is seen under varied tilts, so the residual
    sum of squares has a sharp minimum at the true aspect. Two parabolic
    refinements (6 calibrations, run in parallel) locate it; the curvature gives
    a 1-sigma uncertainty. The overall scale is NOT observable (and does not
    affect intrinsics) - only the X/Y ratio.
    """
    n_pts = sum(v.n for v in views)

    def sse(a):
        r = _calib(with_aspect(views, a), size, model)
        return float(r["rms"]) ** 2 * n_pts

    centre, info = 1.0, {}
    for step in (span, span / 5.0):
        xs = np.array([centre - step, centre, centre + step])
        with ThreadPoolExecutor(max_workers=3) as ex:
            ys = np.array(list(ex.map(sse, xs)))
        c2, c1, c0 = np.polyfit(xs - centre, ys, 2)
        if c2 <= 0:
            centre = float(xs[np.argmin(ys)])
            continue
        centre = float(np.clip(centre - c1 / (2 * c2), centre - 3 * step, centre + 3 * step))
        info = {"curvature": float(c2), "sse_min": float(c0 - c1 ** 2 / (4 * c2))}
    sigma = float("nan")
    if info:
        dof = max(1, 2 * n_pts - 6 * len(views) - 10)
        sigma = float(np.sqrt(max(info["sse_min"], 1e-12) / dof / info["curvature"]))
    return {"aspect": centre, "sigma": sigma, "n_points": n_pts}


def select_model(views, size, candidates=DEFAULT_CANDIDATES, folds=5, min_gain=0.03) -> tuple[str, dict]:
    """Pick the simplest model whose CV error is within `min_gain` of the best."""
    scores = {}
    for m in candidates:
        try:
            scores[m] = cross_validate(views, size, m, folds)
            scores[m]["train_rms"] = float(_calib(views, size, m)["rms"])
            log.info("model %-20s train %.4f px   cross-val %.4f px", m, scores[m]["train_rms"], scores[m]["cv_rms"])
        except cv2.error as e:
            log.warning("model %s failed: %s", m, e)
    best = min(scores.values(), key=lambda s: s["cv_rms"])["cv_rms"]
    for m in candidates:
        if m in scores and scores[m]["cv_rms"] <= best * (1.0 + min_gain):
            return m, scores
    return min(scores, key=lambda m: scores[m]["cv_rms"]), scores


def bootstrap(views, size, model, K, D, n: int = 30, seed: int = 1, grid=(24, 14)) -> dict:
    """Resample views with replacement; measure how much the undistortion moves (px)."""
    rng = np.random.default_rng(seed)
    w, h = size
    gx, gy = np.meshgrid(np.linspace(0, w - 1, grid[0]), np.linspace(0, h - 1, grid[1]))
    pts = np.stack([gx.ravel(), gy.ravel()], 1).reshape(-1, 1, 2).astype(np.float64)
    crit = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 100, 1e-12)
    ref = cv2.undistortPointsIter(pts, K, D, None, K, crit).reshape(-1, 2)

    def rays(Kx, Dx):
        n_ = cv2.undistortPointsIter(pts, Kx, Dx, None, None, crit).reshape(-1, 2)
        r_ = np.column_stack([n_, np.ones(len(n_))])
        return r_ / np.linalg.norm(r_, axis=1, keepdims=True)
    ray0 = rays(K, D)
    draws = [rng.integers(0, len(views), len(views)) for _ in range(n)]

    def one(draw):
        try:
            r = _calib([views[i] for i in draw], size, model, K0=K, D0=D)
        except cv2.error:
            return None
        u = cv2.undistortPointsIter(pts, r["K"], r["D"], None, K, crit).reshape(-1, 2)
        # rotation-compensated: a common rotation between two camera models is absorbed by the extrinsics
        # (pose / hand-eye / plane fit) in any real measurement, so it is not a measurement error
        r1 = rays(r["K"], r["D"])
        U, _, Vt = np.linalg.svd(r1.T @ ray0)
        Rm = Vt.T @ np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]) @ U.T
        ang = np.arccos(np.clip(np.sum((r1 @ Rm.T) * ray0, axis=1), -1, 1))
        return u - ref, [r["K"][0, 0], r["K"][1, 1], r["K"][0, 2], r["K"][1, 2]], ang * K[0, 0]

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        got = [g for g in ex.map(one, draws) if g is not None]
    samples, Ks = [g[0] for g in got], [g[1] for g in got]
    s = np.array(samples)                       # (B, P, 2)
    raw = np.sqrt(np.mean(np.sum((s - s.mean(0)) ** 2, axis=2), axis=0))  # per grid point RMS (no compensation)
    spread = np.sqrt(np.mean(np.array([g[2] for g in got]) ** 2, axis=0))  # rotation-compensated, px
    Ks = np.array(Ks)
    return {"n": len(samples), "grid": list(grid), "uncertainty_px_grid": spread.reshape(grid[1], grid[0]).tolist(),
            "uncertainty_px_mean": float(spread.mean()), "uncertainty_px_max": float(spread.max()),
            "uncertainty_px_p95": float(np.percentile(spread, 95)),
            "definition": "RMS over resampled calibrations of the projection difference after the best common "
                          "rotation (absorbed by extrinsics); raw_* = without that compensation",
            "raw_uncertainty_px_mean": float(raw.mean()), "raw_uncertainty_px_max": float(raw.max()),
            "std_fx_fy_cx_cy": Ks.std(0).tolist()}


# =============================================================================
# Diagnostics
# =============================================================================
def coverage(views: list[View], size, grid=(16, 9)) -> dict:
    w, h = size
    occ = np.zeros(grid[::-1], int)
    for v in views:
        gx = np.clip((v.img[:, 0] / w * grid[0]).astype(int), 0, grid[0] - 1)
        gy = np.clip((v.img[:, 1] / h * grid[1]).astype(int), 0, grid[1] - 1)
        np.add.at(occ, (gy, gx), 1)
    # corner regions: outer 15 % of each image corner (same rule as the live checklist)
    cw, chh = 0.15 * w, 0.15 * h
    regions = {"top_left": (0, 0), "top_right": (w - cw, 0), "bottom_left": (0, h - chh), "bottom_right": (w - cw, h - chh)}
    allpts = np.concatenate([v.img for v in views])
    corner_counts = {k: int(((allpts[:, 0] >= x) & (allpts[:, 0] < x + cw) & (allpts[:, 1] >= y) &
                             (allpts[:, 1] < y + chh)).sum()) for k, (x, y) in regions.items()}
    # radial coverage relative to max image radius from centre
    c = np.array([w / 2, h / 2])
    rr = np.linalg.norm(allpts - c, axis=1) / np.linalg.norm(c)
    return {"grid": list(grid), "cells_covered_frac": float((occ > 0).mean()), "occupancy": occ.tolist(),
            "corner_region_points": corner_counts, "max_radius_frac": float(rr.max()),
            "radius_p95_frac": float(np.percentile(rr, 95))}


def tilt_stats(rvecs) -> dict:
    tilts, ax, ay = [], [], []
    for rv in rvecs:
        R, _ = cv2.Rodrigues(rv)
        n = R[:, 2]   # board normal in camera frame
        tilts.append(math.degrees(math.acos(min(1.0, abs(n[2])))))
        ax.append(math.degrees(math.atan2(n[1], abs(n[2]))))
        ay.append(math.degrees(math.atan2(n[0], abs(n[2]))))
    t = np.array(tilts)
    return {"tilt_deg_min": float(t.min()), "tilt_deg_median": float(np.median(t)), "tilt_deg_max": float(t.max()),
            "tilt_about_x_range": [float(min(ax)), float(max(ax))], "tilt_about_y_range": [float(min(ay)), float(max(ay))]}


def fov_deg(K, D, size) -> dict:
    w, h = size
    mid = np.array([[0, h / 2], [w - 1, h / 2], [w / 2, 0], [w / 2, h - 1], [0, 0], [w - 1, h - 1]], np.float64)
    n = cv2.undistortPoints(mid.reshape(-1, 1, 2), K, D).reshape(-1, 2)
    ang = lambda a, b: math.degrees(math.acos(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))))  # noqa: E731
    r = [np.array([p[0], p[1], 1.0]) for p in n]
    return {"horizontal": ang(r[0], r[1]), "vertical": ang(r[2], r[3]), "diagonal": ang(r[4], r[5])}


def distortion_field(K, D, size, grid=(32, 18)) -> dict:
    w, h = size
    gx, gy = np.meshgrid(np.linspace(0, w - 1, grid[0]), np.linspace(0, h - 1, grid[1]))
    pts = np.stack([gx.ravel(), gy.ravel()], 1).reshape(-1, 1, 2).astype(np.float64)
    u = cv2.undistortPoints(pts, K, D, P=K).reshape(-1, 2)
    d = np.linalg.norm(u - pts.reshape(-1, 2), axis=1)
    return {"max_px": float(d.max()), "mean_px": float(d.mean()), "grid": list(grid),
            "displacement_px": d.reshape(grid[1], grid[0]).tolist()}


# =============================================================================
# Orchestration
# =============================================================================
def apply_aspect_decision(spec: BoardSpec, a_rel: float, sigma: float) -> tuple[BoardSpec, dict]:
    """Decide which board Y/X ratio to use. `a_rel` is relative to the spec's current pitch ratio."""
    import copy
    out = copy.deepcopy(spec)
    tol = max(3.0 * (sigma if np.isfinite(sigma) else 0.0), 0.0005)
    rep = {"estimated": True, "estimated_rel_to_input": a_rel, "sigma": sigma,
           "input_measured": spec.is_measured,
           "input_pitch_x_mm": spec.pitch_x_mm, "input_pitch_y_mm": spec.pitch_y_mm}
    if spec.is_measured and abs(a_rel - 1.0) <= tol:
        rep["decision"] = "measured spans confirmed by the images"
    else:
        px = spec.pitch_x_mm
        py = spec.pitch_y_mm * a_rel
        out.measured_span_x_mm = px * spec.squares_x
        out.measured_span_y_mm = py * spec.squares_y
        rep["decision"] = ("measured Y/X ratio disagrees with the images by "
                           f"{100 * (a_rel - 1):+.3f}% -> using image-estimated ratio (re-check measurement / flatness)"
                           if spec.is_measured else
                           f"print Y/X ratio estimated from images ({100 * (a_rel - 1):+.3f}%); absolute scale nominal")
        rep["disagreement"] = spec.is_measured
    rep["used_pitch_x_mm"], rep["used_pitch_y_mm"] = out.pitch_x_mm, out.pitch_y_mm
    log.info("board aspect: %s (sigma %.4f%%)", rep["decision"], 100 * sigma if np.isfinite(sigma) else float("nan"))
    return out, rep


ANALYSIS_MAX_VIEWS = 60     # aspect / model selection / bootstrap use an evenly spread subset of this size


def _spread(views: list[View], n: int = ANALYSIS_MAX_VIEWS) -> list[View]:
    """Evenly spread subset (captures are in time order, so this samples the whole session, not one burst).
    Used only for the side analyses; the final fit always uses every view."""
    if len(views) <= n:
        return views
    idx = np.unique(np.round(np.linspace(0, len(views) - 1, n)).astype(int))
    return [views[i] for i in idx]


def _self_calibrate_board(kept: list[View], size, spec: BoardSpec, model: str, out_dir: Path) -> dict:
    from .board_refine import pose_only_rms, refine_board
    nominal = np.zeros((spec.n_corners, 3))
    for v in kept:
        nominal[v.ids] = v.obj
    seen = np.zeros(spec.n_corners, int)
    for v in kept:
        seen[v.ids] += 1
    c = spec.inner_cols
    gauge = (0, c - 1, c * (spec.inner_rows - 1))
    if min(seen[list(gauge)]) < 3:
        log.info("board self-calibration skipped: reference corners seen too rarely")
        return {"applied": False, "reason": "reference corners not seen often enough"}
    obs = lambda vs: [(v.ids, v.img.astype(np.float64)) for v in vs]
    A, B = kept[0::2], kept[1::2]
    rA = _calib(A, size, model)
    base = pose_only_rms(obs(B), nominal, rA["K"], rA["D"])
    ref = refine_board(obs(A), spec.n_corners, nominal, rA["K"], rA["D"], gauge, max_nfev=150)
    test = pose_only_rms(obs(B), ref["board"], ref["K"], ref["D"])
    gain = 1.0 - np.median(test) / max(np.median(base), 1e-9)
    log.info("board self-calibration held-out check: median %.3f px (nominal board) -> %.3f px (refined)",
             np.median(base), np.median(test))
    report = {"heldout_median_px_nominal": float(np.median(base)), "heldout_median_px_refined": float(np.median(test))}
    if gain < 0.10:
        log.info("board self-calibration NOT applied (held-out gain %.0f%% < 10%%): printed board matches nominal", 100 * gain)
        return {"applied": False, **report}
    r0 = _calib(kept, size, model)
    full = refine_board(obs(kept), spec.n_corners, nominal, r0["K"], r0["D"], gauge, max_nfev=200)
    P = full["board"]
    for v in kept:
        v.obj = P[v.ids].copy()
    d = full["delta"]
    report.update({"applied": True, "rms_before_px": full["rms_before"], "rms_after_px": full["rms_after"],
                   "correction_mm_median": float(np.median(np.linalg.norm(d, axis=1))),
                   "correction_mm_max": float(np.linalg.norm(d, axis=1).max()),
                   "in_plane_mm_max": float(np.linalg.norm(d[:, :2], axis=1).max()),
                   "flatness_mm_peak_to_peak": float(d[:, 2].max() - d[:, 2].min())})
    (out_dir / "board_refined.json").write_text(json.dumps({"note": "true board corner positions (mm) estimated "
                                                            "from the images; ids = row*inner_cols+col",
                                                            "corners_mm": P.tolist(), "report": report}, indent=1))
    log.info("board self-calibration APPLIED: board out-of-flat %.2f mm peak-to-peak, in-plane print error up to "
             "%.2f mm", report["flatness_mm_peak_to_peak"], report["in_plane_mm_max"])
    return report


def calibrate_session(session: Path, spec: BoardSpec, out_dir: Path, *, model: str = "auto",
                      candidates=None,
                      min_corners: int = 15, folds: int = 5, n_boot: int = 30, workers: int = 4,
                      working_distances_mm=(150, 250, 400, 600, 800, 1000, 1500), mode: Optional[dict] = None,
                      extra_meta: Optional[dict] = None, estimate_aspect: bool = True,
                      refine_board_geometry: bool = True) -> dict:
    session = Path(session)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads((session / "session.json").read_text()) if (session / "session.json").exists() else {}
    mode = mode or meta.get("mode")

    views, info = detect_session(session, spec, workers=workers)
    size = tuple(info["image_size"])
    if mode and (mode["width"], mode["height"]) != size:
        raise ValueError(f"session images are {size}, session mode says {mode}")

    rejected = []
    usable = []
    for v in views:
        why = view_is_usable(v, spec, min_corners)
        if why:
            rejected.append({"view": v.name, "type": "unusable", "reason": why})
        else:
            v.obj = spec.object_points(v.ids)
            usable.append(v)
    if len(usable) < 8:
        raise RuntimeError(f"only {len(usable)} usable views - capture more (>= 25 recommended)")
    log.info("%d images, %d usable views, %d corners", len(views), len(usable), sum(v.n for v in usable))

    pre_model = "brown_k1k2k3" if model == "auto" else model
    # 0) board X/Y print-scale ratio from the images (before outlier rejection, which it would bias)
    aspect_log = []
    if estimate_aspect:
        est = estimate_board_aspect(_spread(usable), size, pre_model)
        aspect_log.append(est)
        usable = with_aspect(usable, est["aspect"])
    # 1) robust rejection with a flexible-enough model
    kept, rej = reject_outliers(usable, size, pre_model)
    rejected += rej
    if estimate_aspect:
        est2 = estimate_board_aspect(_spread(kept), size, pre_model)
        aspect_log.append(est2)
        kept = with_aspect(kept, est2["aspect"])
        a_total = float(np.prod([e["aspect"] for e in aspect_log]))
        spec, aspect_report = apply_aspect_decision(spec, a_total, est2["sigma"])
        # rebuild object points exactly from the decided spec (removes compounding round-off)
        for v in kept:
            v.obj = spec.object_points(v.ids)
    else:
        aspect_report = {"estimated": False}
    # 1b) board self-calibration: true 3D position of every printed corner (printer stretch, waviness).
    #     Accepted only if it improves views that were NOT used to refine it.
    board_report = {"applied": False}
    if refine_board_geometry and len(kept) >= 16:
        board_report = _self_calibrate_board(kept, size, spec, pre_model, out_dir)
    # 2) model selection
    if model == "auto":
        model, scores = select_model(_spread(kept), size, candidates=candidates or DEFAULT_CANDIDATES, folds=folds)
    else:
        scores = {model: cross_validate(_spread(kept), size, model, folds)}
    log.info("selected distortion model: %s", model)
    # 3) final fit
    r = _calib(kept, size, model, extended=True)
    K, D = r["K"], r["D"]
    per_view = []
    all_res = []
    for v, rv, tv in zip(kept, r["rvecs"], r["tvecs"]):
        e = residuals(v, K, D, rv, tv)
        all_res.append(e)
        per_view.append({"view": v.name, "n": int(v.n), "rms_px": float(np.sqrt(np.mean(np.sum(e ** 2, 1)))),
                         "max_px": float(np.linalg.norm(e, axis=1).max()),
                         "distance_mm": float(np.linalg.norm(tv)), "rvec": rv.ravel().tolist(), "tvec": tv.ravel().tolist()})
    res = np.concatenate(all_res)
    res_n = np.linalg.norm(res, axis=1)
    # 4) uncertainty
    boot = bootstrap(_spread(kept), size, model, K, D, n=n_boot) if n_boot else {}   # conservative if subset
    cov = coverage(kept, size)
    tilt = tilt_stats(r["rvecs"])
    fov = fov_deg(K, D, size)
    dist = distortion_field(K, D, size)
    newK0, roi0 = cv2.getOptimalNewCameraMatrix(K, D, size, 0.0, size)
    newK1, roi1 = cv2.getOptimalNewCameraMatrix(K, D, size, 1.0, size)

    w, h = size
    eff_pitch_mm = (SENSOR_ACTIVE_PX[0] * SENSOR_PIXEL_UM / 1000.0) / w
    same_aspect = abs(w / h - SENSOR_ACTIVE_PX[0] / SENSOR_ACTIVE_PX[1]) < 1e-3
    std = {n: float(s) for n, s in zip(STD_NAMES, r["std_int"]) if s > 0}
    mmpp = {str(z): {"mm_per_px_x": z / K[0, 0], "mm_per_px_y": z / K[1, 1],
                     "field_of_view_mm": [z * w / K[0, 0], z * h / K[1, 1]]} for z in working_distances_mm}

    grade, issues = grade_result(len(kept), float(np.sqrt(np.mean(res_n ** 2))), cov, tilt, boot, spec, mode,
                                 aspect_report, holdout=scores.get(model, {}))

    result = {
        "schema": "camcal/1",
        "camera": meta.get("device_info", {}),
        "mode": mode or {"width": w, "height": h},
        "mode_key": f"{w}x{h}_{(mode or {}).get('fourcc', 'UNK')}",
        "image_size": [w, h],
        "distortion_model": model,
        "camera_matrix": K.tolist(),
        "dist_coeffs": D.tolist(),
        "dist_coeffs_names": STD_NAMES[4:4 + len(D)],
        "fx": K[0, 0], "fy": K[1, 1], "cx": K[0, 2], "cy": K[1, 2],
        "std_dev": std,
        "rms_px": float(np.sqrt(np.mean(res_n ** 2))),
        "opencv_rms": float(r["rms"]),
        "mean_err_px": float(res_n.mean()), "p95_err_px": float(np.percentile(res_n, 95)), "max_err_px": float(res_n.max()),
        "n_views": len(kept), "n_points": int(len(res_n)),
        "model_selection": scores,
        "bootstrap": boot,
        "coverage": cov,
        "tilt": tilt,
        "fov_deg": fov,
        "distortion": {k: v for k, v in dist.items()},
        "new_camera_matrix_alpha0": newK0.tolist(), "roi_alpha0": list(map(int, roi0)),
        "new_camera_matrix_alpha1": newK1.tolist(), "roi_alpha1": list(map(int, roi1)),
        "principal_point_offset_px": [K[0, 2] - (w - 1) / 2.0, K[1, 2] - (h - 1) / 2.0],
        "aspect_fy_over_fx": K[1, 1] / K[0, 0],
        "focal_length_mm_if_full_sensor_scaled": (K[0, 0] * eff_pitch_mm) if same_aspect else None,
        "effective_pixel_pitch_um_if_full_sensor_scaled": (eff_pitch_mm * 1000) if same_aspect else None,
        "metric_resolution": mmpp,
        "board": {**spec.__dict__, "pitch_x_mm": spec.pitch_x_mm, "pitch_y_mm": spec.pitch_y_mm},
        "board_aspect": aspect_report,
        "board_refinement": board_report,
        "holdout_metric": {k: v for k, v in scores.get(model, {}).items() if k.startswith("holdout")},
        "rejected": rejected,
        "per_view": per_view,
        "grade": grade, "issues": issues,
        "controls_during_capture": meta.get("controls_locked", {}),
        "geometry_controls": meta.get("geometry_controls", {}),
        "session": f"sessions/{session.parent.name}/{session.name}",
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "opencv": cv2.__version__,
    }
    if extra_meta:
        result.update(extra_meta)
    write_outputs(result, out_dir, kept, all_res)
    return result


def grade_result(n_views, rms, cov, tilt, boot, spec: BoardSpec, mode, aspect=None, holdout=None,
                 target_mm: float = 0.5) -> tuple[str, list]:
    issues = []
    fail = warn = False

    def add(level, msg):
        nonlocal fail, warn
        issues.append(f"{level}: {msg}")
        fail |= level == "FAIL"
        warn |= level == "WARN"

    if n_views < 15:
        add("FAIL", f"only {n_views} views (need >= 15, recommended 30-45)")
    elif n_views < 25:
        add("WARN", f"{n_views} views (recommended 30-45)")
    lim = 0.35 if (mode or {}).get("fourcc", "").upper() == "MJPG" else 0.25
    if rms > 2 * lim:
        add("FAIL", f"RMS reprojection {rms:.3f} px (> {2 * lim:.2f})")
    elif rms > lim:
        add("WARN", f"RMS reprojection {rms:.3f} px (> {lim:.2f}) - check focus, motion, board flatness")
    if cov["cells_covered_frac"] < 0.6:
        add("FAIL", f"image coverage {cov['cells_covered_frac']:.0%} (< 60%)")
    elif cov["cells_covered_frac"] < 0.85:
        add("WARN", f"image coverage {cov['cells_covered_frac']:.0%} (< 85%) - push the board into edges/corners")
    weak = [k for k, n in cov["corner_region_points"].items() if n < 10]
    if weak:
        add("WARN", f"few points in image corner regions {weak} - distortion is extrapolated there")
    if tilt["tilt_deg_max"] < 25:
        add("WARN", f"max board tilt {tilt['tilt_deg_max']:.0f} deg (< 25) - focal length weakly constrained")
    if boot:
        if boot["uncertainty_px_max"] > 0.5:
            add("FAIL", f"bootstrap undistortion uncertainty max {boot['uncertainty_px_max']:.2f} px")
        elif boot["uncertainty_px_max"] > 0.2:
            add("WARN", f"bootstrap undistortion uncertainty max {boot['uncertainty_px_max']:.2f} px (target < 0.2)")
    aspect = aspect or {}
    if aspect.get("disagreement"):
        add("WARN", "caliper spans disagree with the images: " + aspect.get("decision", ""))
    if not (aspect.get("input_measured") or spec.is_measured):
        add("WARN", "board not measured: intrinsics are fine (print X/Y ratio was estimated from the images), "
                    "but mm values use the NOMINAL absolute scale - measure the spans for metric verification")
    elif not aspect.get("estimated") and not spec.is_measured:
        add("WARN", "board pitch not measured and aspect not estimated: anisotropic print scaling biases fx/fy")
    # The goal is METRIC accuracy. Measured on views never used for fitting, it overrides the pixel heuristics
    # (which assume a lab-grade rigid target): sub-target held-out error = PASS, with the notes kept as advice.
    hp95 = (holdout or {}).get("holdout_mm_p95")
    if hp95 is not None:
        if hp95 <= target_mm and n_views >= 25:
            issues = [re.sub(r"^(FAIL|WARN): ", "note: ", i) for i in issues]
            issues.insert(0, f"PASS: measured accuracy {holdout['holdout_mm_rms']:.3f} mm RMS, 95% within {hp95:.3f} mm "
                             f"(target {target_mm} mm) on held-out views at ~{holdout.get('holdout_distance_mm_median', 0):.0f} mm")
            return "PASS", issues
        issues.insert(0, f"FAIL: measured accuracy 95% within {hp95:.3f} mm (target {target_mm} mm)")
        return "FAIL", issues
    return ("FAIL" if fail else "WARN" if warn else "PASS"), issues


# =============================================================================
# Output
# =============================================================================
def write_outputs(result: dict, out_dir: Path, views: list[View], res: list[np.ndarray]) -> None:
    base = f"camera_{result['mode_key']}"
    # --- OpenCV FileStorage YAML (C++: cv::FileStorage fs(path, READ); fs["camera_matrix"] >> K;)
    fs = cv2.FileStorage(str(out_dir / f"{base}.yaml"), cv2.FILE_STORAGE_WRITE)
    fs.write("calibration_time", result["created"])
    fs.write("camera", json.dumps(result.get("camera", {})))
    fs.write("mode_key", result["mode_key"])
    fs.write("image_width", int(result["image_size"][0]))
    fs.write("image_height", int(result["image_size"][1]))
    fs.write("pixel_format", str(result["mode"].get("fourcc", "")))
    fs.write("fps", float(result["mode"].get("fps", 0)))
    fs.write("distortion_model", result["distortion_model"])
    fs.write("camera_matrix", np.array(result["camera_matrix"]))
    fs.write("distortion_coefficients", np.array(result["dist_coeffs"]).reshape(1, -1))
    fs.write("new_camera_matrix_alpha0", np.array(result["new_camera_matrix_alpha0"]))
    fs.write("roi_alpha0", np.array(result["roi_alpha0"]))
    fs.write("new_camera_matrix_alpha1", np.array(result["new_camera_matrix_alpha1"]))
    fs.write("roi_alpha1", np.array(result["roi_alpha1"]))
    fs.write("rms_reprojection_px", result["rms_px"])
    fs.write("bootstrap_uncertainty_px_max", float(result.get("bootstrap", {}).get("uncertainty_px_max", -1)))
    fs.write("n_views", result["n_views"])
    fs.write("grade", result["grade"])
    fs.write("geometry_controls", json.dumps(result.get("geometry_controls", {})))
    fs.release()
    (out_dir / f"{base}.json").write_text(json.dumps(result, indent=2, default=_np_default))
    with open(out_dir / f"{base}_per_view.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["view", "n_points", "rms_px", "max_px", "distance_mm"])
        for p in result["per_view"]:
            wr.writerow([p["view"], p["n"], f"{p['rms_px']:.4f}", f"{p['max_px']:.4f}", f"{p['distance_mm']:.1f}"])
    np.savez_compressed(out_dir / f"{base}_points.npz",
                        **{f"img_{i}": v.img for i, v in enumerate(views)},
                        **{f"res_{i}": r for i, r in enumerate(res)},
                        **{f"obj_{i}": v.obj for i, v in enumerate(views)})
    try:
        from .report import make_report
        make_report(result, views, res, out_dir / f"{base}_report.png")
    except Exception as e:  # report must never break a calibration
        log.warning("report generation failed: %s", e)
    (out_dir / f"{base}_summary.md").write_text(summary_markdown(result))


def _np_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    raise TypeError(type(o))


def summary_markdown(r: dict) -> str:
    K = np.array(r["camera_matrix"])
    s = r.get("std_dev", {})
    b = r.get("bootstrap", {})
    lines = [
        f"# Calibration {r['mode_key']}  -  grade **{r['grade']}**", "",
        f"- created: {r['created']}  |  OpenCV {r['opencv']}  |  model: `{r['distortion_model']}`",
        f"- views: {r['n_views']}  |  points: {r['n_points']}",
        f"- reprojection RMS **{r['rms_px']:.4f} px**  (mean {r['mean_err_px']:.4f}, p95 {r['p95_err_px']:.4f}, max {r['max_err_px']:.4f})",
        f"- bootstrap undistortion uncertainty: mean {b.get('uncertainty_px_mean', float('nan')):.4f} px, "
        f"max {b.get('uncertainty_px_max', float('nan')):.4f} px", "",
        "| param | value | 1-sigma |", "|---|---|---|",
        f"| fx | {K[0, 0]:.4f} | {s.get('fx', 0):.4f} |", f"| fy | {K[1, 1]:.4f} | {s.get('fy', 0):.4f} |",
        f"| cx | {K[0, 2]:.4f} | {s.get('cx', 0):.4f} |", f"| cy | {K[1, 2]:.4f} | {s.get('cy', 0):.4f} |",
    ]
    for n, v in zip(r["dist_coeffs_names"], r["dist_coeffs"]):
        lines.append(f"| {n} | {v:.8f} | {s.get(n, 0):.8f} |")
    fov = r["fov_deg"]
    lines += ["", f"- FOV H/V/D: {fov['horizontal']:.2f} / {fov['vertical']:.2f} / {fov['diagonal']:.2f} deg",
              f"- max distortion displacement: {r['distortion']['max_px']:.2f} px",
              f"- principal point offset from centre: ({r['principal_point_offset_px'][0]:.2f}, {r['principal_point_offset_px'][1]:.2f}) px",
              f"- coverage: {r['coverage']['cells_covered_frac']:.0%} of 16x9 cells; tilt range {r['tilt']['tilt_deg_min']:.0f}-{r['tilt']['tilt_deg_max']:.0f} deg"]
    if r.get("focal_length_mm_if_full_sensor_scaled"):
        lines.append(f"- focal length (assuming full-sensor scaled mode): {r['focal_length_mm_if_full_sensor_scaled']:.3f} mm")
    hm = r.get("holdout_metric") or {}
    if hm:
        lines.append(f"- **held-out metric accuracy** (views never used to fit the intrinsics, board reconstructed in mm): "
                     f"RMS {hm['holdout_mm_rms']:.3f} mm, p95 {hm['holdout_mm_p95']:.3f} mm, max {hm['holdout_mm_max']:.3f} mm "
                     f"at median distance {hm['holdout_distance_mm_median']:.0f} mm")
    ba = r.get("board_aspect") or {}
    if ba.get("estimated"):
        lines.append(f"- board pitch used: X {ba['used_pitch_x_mm']:.4f} mm, Y {ba['used_pitch_y_mm']:.4f} mm  ({ba['decision']})")
    lines += ["", "## Metric resolution (1 px at distance Z on a fronto-parallel plane)", "",
              "| Z (mm) | mm/px X | mm/px Y | field of view (mm) |", "|---|---|---|---|"]
    for z, m in r["metric_resolution"].items():
        lines.append(f"| {z} | {m['mm_per_px_x']:.4f} | {m['mm_per_px_y']:.4f} | {m['field_of_view_mm'][0]:.0f} x {m['field_of_view_mm'][1]:.0f} |")
    lines += ["", "## Issues", ""] + ([f"- {i}" for i in r["issues"]] or ["- none"])
    if r["rejected"]:
        lines += ["", "## Rejected", ""] + [f"- {json.dumps(x)}" for x in r["rejected"]]
    return "\n".join(lines) + "\n"
