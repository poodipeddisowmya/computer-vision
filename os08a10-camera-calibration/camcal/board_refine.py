"""Board self-calibration: refine the true 3D position of every printed corner.

A paper target is never exactly the nominal grid: laser printers stretch the sheet
unevenly along the feed direction, and gluing leaves sub-millimetre waves. At 4K those
errors are 1-2 px and dominate the calibration. Every corner is observed in many views
from different directions, so its true position (x, y, z) is observable jointly with the
intrinsics and the poses (bundle adjustment, cf. Strobl & Hirzinger 2011, "More accurate
pinhole camera calibration with imperfect planar target").

Gauge (7 DoF similarity between board and poses) is fixed by
  corner 0            : dx = dy = dz = 0
  last corner, row 0  : dx = dy = dz = 0   (keeps the nominal / measured X span = scale)
  first corner, last row: dz = 0
A weak prior (sigma 1.5 mm) keeps rarely seen corners well-posed without biasing the rest.
"""
from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

log = logging.getLogger("camcal")


def refine_board(views, n_corners: int, nominal: np.ndarray, K: np.ndarray, D: np.ndarray, gauge_ids: tuple,
                 prior_mm: float = 1.5, f_scale_px: float = 1.0, fix_k3: bool = False, max_nfev: int = 60) -> dict:
    """views: list of (ids, img_pts (N,2)). nominal: (n_corners,3) board points. Returns refined model."""
    D = np.zeros(5) if D is None else np.asarray(D, float).ravel()[:5]
    D = np.pad(D, (0, 5 - len(D)))
    poses = []
    for ids, img in views:
        ok, rv, tv = cv2.solvePnP(nominal[ids], img, K, D, flags=cv2.SOLVEPNP_ITERATIVE)
        rv, tv = cv2.solvePnPRefineLM(nominal[ids], img, K, D, rv, tv)
        poses.append(np.r_[rv.ravel(), tv.ravel()])
    i0, i1, i2 = gauge_ids
    free = np.ones((n_corners, 3), bool)
    free[i0, :] = False
    free[i1, :] = False
    free[i2, 2] = False
    fidx = np.flatnonzero(free.ravel())
    n_int = 4 + (4 if fix_k3 else 5)
    nv = len(views)

    def unpack(p):
        fx, fy, cx, cy = p[:4]
        d = np.zeros(5)
        d[: n_int - 4] = p[4:n_int]
        Kp = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])
        pv = p[n_int:n_int + 6 * nv].reshape(nv, 6)
        delta = np.zeros(n_corners * 3)
        delta[fidx] = p[n_int + 6 * nv:]
        return Kp, d, pv, nominal + delta.reshape(n_corners, 3)

    def resid(p):
        Kp, d, pv, P = unpack(p)
        out = []
        for (ids, img), q in zip(views, pv):
            proj, _ = cv2.projectPoints(P[ids], q[:3], q[3:], Kp, d)
            out.append((proj.reshape(-1, 2) - img).ravel())
        delta = p[n_int + 6 * nv:]
        out.append(delta * (f_scale_px / prior_mm))
        return np.concatenate(out)

    p0 = np.r_[K[0, 0], K[1, 1], K[0, 2], K[1, 2], D[: n_int - 4], np.concatenate(poses), np.zeros(len(fidx))]
    # sparsity: each observation depends on intrinsics, its view's pose and its own board point
    n_obs = sum(len(ids) for ids, _ in views)
    J = lil_matrix((2 * n_obs + len(fidx), len(p0)), dtype=np.uint8)
    col_of = -np.ones(n_corners * 3, int)
    col_of[fidx] = n_int + 6 * nv + np.arange(len(fidx))
    r = 0
    for v, (ids, _) in enumerate(views):
        for j in ids:
            for k in (0, 1):
                J[r + k, :n_int] = 1
                J[r + k, n_int + 6 * v: n_int + 6 * v + 6] = 1
                for c in range(3):
                    cc = col_of[3 * j + c]
                    if cc >= 0:
                        J[r + k, cc] = 1
            r += 2
    for t in range(len(fidx)):
        J[2 * n_obs + t, n_int + 6 * nv + t] = 1
    r0 = resid(p0)[: 2 * n_obs]
    sol = least_squares(resid, p0, jac_sparsity=J, loss="soft_l1", f_scale=f_scale_px, x_scale="jac",
                        method="trf", max_nfev=max_nfev, verbose=0)
    Kp, d, pv, P = unpack(sol.x)
    r1 = sol.fun[: 2 * n_obs].reshape(-1, 2)
    rms0 = float(np.sqrt((r0.reshape(-1, 2) ** 2).sum(1).mean()))
    rms1 = float(np.sqrt((r1 ** 2).sum(1).mean()))
    delta = P - nominal
    log.info("board self-calibration: RMS %.3f -> %.3f px; corner corrections: median %.3f mm, max %.3f mm "
             "(in-plane %.3f mm, out-of-plane %.3f mm max)", rms0, rms1, np.median(np.linalg.norm(delta, axis=1)),
             np.linalg.norm(delta, axis=1).max(), np.linalg.norm(delta[:, :2], axis=1).max(), np.abs(delta[:, 2]).max())
    return {"K": Kp, "D": d, "poses": pv, "board": P, "delta": delta, "rms_before": rms0, "rms_after": rms1,
            "success": bool(sol.success), "nfev": int(sol.nfev)}


def pose_only_rms(views, board: np.ndarray, K, D) -> np.ndarray:
    """Per-view RMS after fitting only the pose (intrinsics + board fixed) - for held-out testing."""
    out = []
    for ids, img in views:
        ok, rv, tv = cv2.solvePnP(board[ids], img, K, D, flags=cv2.SOLVEPNP_ITERATIVE)
        rv, tv = cv2.solvePnPRefineLM(board[ids], img, K, D, rv, tv)
        p, _ = cv2.projectPoints(board[ids], rv, tv, K, D)
        out.append(float(np.sqrt(((p.reshape(-1, 2) - img) ** 2).sum(1).mean())))
    return np.array(out)
