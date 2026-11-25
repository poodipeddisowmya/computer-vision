"""Operator guidance: what view to capture next, when the data set is complete,
and automatic exposure control.

Pose planning
  A curated plan of target poses (board pose relative to the camera) is
  projected into the live image as a "ghost" outline. The operator moves the
  camera until the live board overlaps the ghost; the pipeline captures by
  itself when the view is still and useful. Any other still, novel and useful
  view is captured opportunistically, so the operator never has to be exact.
  Once an intermediate calibration exists, remaining targets are re-ranked by
  how much they cover uncovered / high-uncertainty image regions.

Completion
  The data set is complete when coverage, image-corner support, tilt and
  distance diversity, view count and the intermediate calibration's
  uncertainty all meet their targets.

Exposure
  Manual exposure is driven so the white squares sit at ~80 % of full scale
  without clipping, keeping the exposure short (rolling shutter + hand-held
  motion) and only then using gain.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from .board import BoardSpec


# =============================================================================
# Pose descriptors (shared by targets and captures)
# =============================================================================
def descriptor_from_points(ids, pts, spec: BoardSpec, K, D, size) -> Optional[tuple[np.ndarray, dict]]:
    """(centre x, centre y, sqrt(area), tilt_x/60, tilt_y/60) of the visible board."""
    w, h = size
    if len(ids) < 6:
        return None
    obj = spec.object_points(ids)
    ok, rv, tv = cv2.solvePnP(obj, np.asarray(pts, np.float64), K, D, flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        return None
    R, _ = cv2.Rodrigues(rv)
    n = R[:, 2]
    tx = math.degrees(math.atan2(n[1], abs(n[2])))
    ty = math.degrees(math.atan2(n[0], abs(n[2])))
    c = np.asarray(pts).mean(0)
    area = cv2.contourArea(cv2.convexHull(np.asarray(pts, np.float32))) / float(w * h)
    d = np.array([c[0] / w, c[1] / h, math.sqrt(max(area, 1e-9)), tx / 60.0, ty / 60.0])
    return d, {"tilt_x_deg": tx, "tilt_y_deg": ty, "area_frac": area, "centre": c.tolist(),
               "distance_mm": float(np.linalg.norm(tv)), "rvec": rv.ravel().tolist(), "tvec": tv.ravel().tolist()}


# =============================================================================
@dataclass
class Target:
    idx: int
    name: str
    rvec: np.ndarray
    tvec: np.ndarray
    phase: int
    proj: np.ndarray = None          # (N,2) projected inner corners (all ids)
    visible: np.ndarray = None       # bool mask inside image
    desc: np.ndarray = None
    state: str = "pending"            # pending | done | skipped
    shown_since: float = 0.0


class PosePlanner:
    # (name, phase, centre u, centre v, board-width fill, tilt_x deg, tilt_y deg)
    # Tilt about the image x axis (+ = board top away) and y axis (+ = board right away).
    PLAN = [
        ("centre frontal",            0, .50, .50, .55,   0,   0),
        ("centre, tilt left",         0, .50, .50, .50,   0, -35),
        ("centre, tilt right",        0, .50, .50, .50,   0,  35),
        ("centre, tilt up",           0, .50, .50, .50, -35,   0),
        ("centre, tilt down",         0, .50, .50, .50,  35,   0),
        ("far, centre",               0, .50, .50, .33,   0,   0),
        # image corners: a smaller (farther) board pushed right into each image corner. Corners can only be
        # detected ~1 square from the image edge (both neighbouring markers must be visible), so smaller
        # squares put many more corners into the extreme corner regions (optimised placements).
        ("top-left corner",           1, .13, .19, .32,   8,  -8),
        ("top-right corner",          1, .87, .19, .32,   8,   8),
        ("bottom-left corner",        1, .13, .81, .32,  -8,  -8),
        ("bottom-right corner",       1, .87, .81, .32,  -8,   8),
        ("top-left corner, tilted",   1, .11, .13, .32, -25,  25),
        ("top-right corner, tilted",  1, .89, .13, .32, -25, -25),
        ("bottom-left corner, tilted", 1, .11, .87, .32, 25,  25),
        ("bottom-right corner, tilted", 1, .89, .87, .32, 25, -25),
        # image edges
        ("left edge, tilt right",     2, .18, .50, .60,   0,  30),
        ("right edge, tilt left",     2, .82, .50, .60,   0, -30),
        ("top edge, tilt down",       2, .50, .18, .60,  30,   0),
        ("bottom edge, tilt up",      2, .50, .82, .60, -30,   0),
        ("left edge, near",           2, .12, .50, .85,   0,   0),
        ("right edge, near",          2, .88, .50, .85,   0,   0),
        ("top edge, near",            2, .50, .12, .85,   0,   0),
        ("bottom edge, near",         2, .50, .88, .85,   0,   0),
        # compound tilts
        ("compound up-left",          3, .40, .40, .50, -28, -28),
        ("compound up-right",         3, .60, .40, .50, -28,  28),
        ("compound down-left",        3, .40, .60, .50,  28, -28),
        ("compound down-right",       3, .60, .60, .50,  28,  28),
        ("strong tilt left",          3, .55, .50, .45,   0, -45),
        ("strong tilt right",         3, .45, .50, .45,   0,  45),
        # far / quadrants
        ("far, upper-left",           4, .30, .30, .33,  15,  15),
        ("far, upper-right",          4, .70, .30, .33,  15, -15),
        ("far, lower-left",           4, .30, .70, .33, -15,  15),
        ("far, lower-right",          4, .70, .70, .33, -15, -15),
        ("near, centre",              4, .50, .50, .95,   0,   0),
        ("near, centre tilted",       4, .50, .50, .85,  20, -20),
    ]

    def __init__(self, spec: BoardSpec, size, K: np.ndarray, D: Optional[np.ndarray] = None,
                 match_thr: float = 0.11, done_thr: float = 0.13):
        self.spec, self.size = spec, size
        self.K, self.D = K.copy(), (np.zeros(5) if D is None else D.copy())
        self.match_thr, self.done_thr = match_thr, done_thr
        self.priority_map: Optional[np.ndarray] = None   # (9,16) weights from uncertainty / coverage
        self.targets: list[Target] = []
        for i, (name, ph, u, v, fill, ax, ay) in enumerate(self.PLAN):
            rv, tv = self._pose(u, v, fill, ax, ay)
            self.targets.append(Target(i, name, rv, tv, ph))
        self.update_model(self.K, self.D)
        self._current: Optional[Target] = None

    # ------------------------------------------------------------------ geometry
    def _pose(self, u, v, fill, ax, ay):
        w, h = self.size
        sp = self.spec
        bw = sp.inner_cols * sp.pitch_x_mm
        c_obj = np.array([(sp.inner_cols - 1) * sp.pitch_x_mm / 2, (sp.inner_rows - 1) * sp.pitch_y_mm / 2, 0.0])
        R = cv2.Rodrigues(np.array([math.radians(ax), 0, 0]))[0] @ cv2.Rodrigues(np.array([0, math.radians(ay), 0]))[0]
        Z = self.K[0, 0] * bw / (fill * w)          # board width covers `fill` of the image width
        ray = np.linalg.inv(self.K) @ np.array([u * w, v * h, 1.0])
        t = ray * Z - R @ c_obj
        return cv2.Rodrigues(R)[0].ravel(), t

    def add_targets(self, specs) -> int:
        n0 = len(self.targets)
        for (name, ph, u, v, fill, ax, ay) in specs:
            rv, tv = self._pose(u, v, fill, ax, ay)
            self.targets.append(Target(len(self.targets), name, rv, tv, ph))
        self.update_model(self.K, self.D)
        return sum(1 for t in self.targets[n0:] if t.state == "pending")

    def regenerate(self, unmet: list, cover: np.ndarray, rng: np.random.Generator) -> int:
        """New targets aimed at whatever the completion checklist still lacks."""
        j = lambda a: float(rng.uniform(-a, a))  # noqa: E731
        specs = []
        for k in unmet:
            if k == "img corners":
                for (u, v, sx, sy) in ((.13, .18, -1, -1), (.87, .18, 1, -1), (.13, .82, -1, 1), (.87, .82, 1, 1)):
                    f = rng.uniform(0.30, 0.36)
                    t = rng.uniform(8, 25)
                    specs.append((f"corner retry ({'top' if sy < 0 else 'bottom'}-{'left' if sx < 0 else 'right'})", 5,
                                  u + j(.02), v + j(.02), f, -sy * t * rng.choice([-1, 1]), -sx * t))
            elif k in ("tilt L", "tilt R", "tilt U", "tilt D"):
                ax, ay = {"tilt L": (0, -35), "tilt R": (0, 35), "tilt U": (-35, 0), "tilt D": (35, 0)}[k]
                for _ in range(2):
                    specs.append((f"{k} retry", 5, .5 + j(.15), .5 + j(.15), .5, ax + j(6), ay + j(6)))
            elif k == "frontal":
                specs.append(("frontal retry", 5, .5 + j(.2), .5 + j(.2), .5, j(5), j(5)))
            elif k == "near":
                specs.append(("near retry", 5, .5 + j(.1), .5 + j(.1), .9, j(10), j(10)))
            elif k == "far":
                specs.append(("far retry", 5, .5 + j(.15), .5 + j(.15), .34, j(15), j(15)))
            elif k == "coverage":
                ys, xs = np.where(cover == 0)
                for gy, gx in list(zip(ys, xs))[:4]:
                    specs.append(("fill grey area", 5, (gx + .5) / 16, (gy + .5) / 9, .45, j(15), j(15)))
            elif k in ("views", "uncertainty"):
                for _ in range(3):
                    specs.append(("extra view", 5, .5 + j(.3), .5 + j(.25), rng.uniform(.4, .7), j(30), j(30)))
        return self.add_targets(specs) if specs else 0

    def update_model(self, K, D):
        """Re-project all targets with the latest intrinsics estimate."""
        self.K, self.D = K.copy(), np.asarray(D, float).copy()
        w, h = self.size
        ids = np.arange(self.spec.n_corners)
        obj = self.spec.object_points(ids)
        for t in self.targets:
            p, _ = cv2.projectPoints(obj, t.rvec, t.tvec, self.K, self.D)
            t.proj = p.reshape(-1, 2)
            t.visible = (t.proj[:, 0] >= 0) & (t.proj[:, 0] < w) & (t.proj[:, 1] >= 0) & (t.proj[:, 1] < h)
            r = descriptor_from_points(ids[t.visible], t.proj[t.visible], self.spec, self.K, self.D, self.size) \
                if t.visible.sum() >= 20 else None
            t.desc = None if r is None else r[0]
            if t.desc is None and t.state == "pending":
                t.state = "skipped"          # unreachable with this lens/board geometry

    # ------------------------------------------------------------------ bookkeeping
    def pending(self) -> list[Target]:
        return [t for t in self.targets if t.state == "pending"]

    def mark_captured(self, desc: np.ndarray) -> list[Target]:
        hit = []
        for t in self.pending():
            if np.linalg.norm(t.desc - desc) < self.done_thr:
                t.state = "done"
                hit.append(t)
        if self._current is not None and self._current.state != "pending":
            self._current = None
        return hit

    def skip_current(self):
        if self._current is not None:
            self._current.state = "skipped"
            self._current = None

    def score(self, t: Target) -> float:
        """Higher = more useful next. Phase order first, then uncovered / uncertain regions."""
        base = -10.0 * t.phase
        if self.priority_map is None:
            return base
        w, h = self.size
        pts = t.proj[t.visible]
        gx = np.clip((pts[:, 0] / w * 16).astype(int), 0, 15)
        gy = np.clip((pts[:, 1] / h * 9).astype(int), 0, 8)
        cells = set(zip(gy.tolist(), gx.tolist()))
        gain = sum(self.priority_map[c] for c in cells)
        return base * 0.3 + gain

    def current(self, now: float) -> Optional[Target]:
        if self._current is None or self._current.state != "pending":
            p = self.pending()
            if not p:
                self._current = None
                return None
            min_phase = min(t.phase for t in p)
            pool = [t for t in p if t.phase == min_phase] if min_phase == 0 else p
            self._current = max(pool, key=self.score)
            self._current.shown_since = now
        return self._current

    def match(self, desc: Optional[np.ndarray]) -> float:
        """Distance of the live view to the current target (inf if none)."""
        if desc is None or self._current is None or self._current.desc is None:
            return float("inf")
        return float(np.linalg.norm(self._current.desc - desc))

    def hint(self, live_desc: Optional[np.ndarray]) -> str:
        """Plain-language camera-motion hint toward the current target (board is fixed)."""
        t = self._current
        if t is None:
            return "all planned views done - fill any remaining grey cells"
        if live_desc is None:
            return f"next: {t.name} - point the camera at the board"
        d = t.desc - live_desc
        msgs = []
        if d[2] > 0.06:
            msgs.append("move CLOSER")
        elif d[2] < -0.06:
            msgs.append("move BACK")
        # board must appear further right in the image -> turn the camera left (and vice versa)
        if d[0] > 0.07:
            msgs.append("aim camera LEFT")
        elif d[0] < -0.07:
            msgs.append("aim camera RIGHT")
        if d[1] > 0.07:
            msgs.append("aim camera UP")
        elif d[1] < -0.07:
            msgs.append("aim camera DOWN")
        if abs(d[3]) > 0.15 or abs(d[4]) > 0.15:
            msgs.append("change viewing ANGLE to match the outline shape")
        return f"next: {t.name} - " + (", ".join(msgs) if msgs else "almost there, hold still")

    def outline(self, t: Target) -> np.ndarray:
        """Projected outer rectangle of the inner-corner grid (for drawing)."""
        c, r = self.spec.inner_cols, self.spec.inner_rows
        corners = [0, c - 1, c * r - 1, c * (r - 1)]
        edge = []
        for a, b in zip(corners, corners[1:] + corners[:1]):
            ca, ra = a % c, a // c
            cb, rb = b % c, b // c
            n = max(abs(cb - ca), abs(rb - ra))
            for k in range(n):
                cc = round(ca + (cb - ca) * k / n)
                rr = round(ra + (rb - ra) * k / n)
                edge.append(t.proj[rr * c + cc])
        return np.array(edge)


# =============================================================================
@dataclass
class Completion:
    min_views: int = 30
    max_views: int = 60
    min_cells: float = 0.90
    min_corner_pts: int = 10
    corner_region_frac: float = 0.15
    min_tilt_each: int = 4
    min_frontal: int = 3
    min_near: int = 4
    min_far: int = 3
    max_uncertainty_px: float = 0.15
    state: dict = field(default_factory=dict)

    def evaluate(self, captures: list, cover: np.ndarray, corner_pts: list, uncertainty: Optional[float],
                 skipped_far=False, skipped_near=False) -> tuple[bool, dict]:
        tilts = np.array([[c.metrics.get("tilt_x_deg", 0), c.metrics.get("tilt_y_deg", 0)] for c in captures]) \
            if captures else np.zeros((0, 2))
        areas = np.array([c.metrics.get("area_frac", 0) for c in captures])
        chk = {
            "views": (len(captures), self.min_views),
            "coverage": (round(float((cover > 0).mean()), 3), self.min_cells),
            "img corners": (int(min(corner_pts)) if corner_pts else 0, self.min_corner_pts),
            "tilt L": (int((tilts[:, 1] < -20).sum()) if len(tilts) else 0, self.min_tilt_each),
            "tilt R": (int((tilts[:, 1] > 20).sum()) if len(tilts) else 0, self.min_tilt_each),
            "tilt U": (int((tilts[:, 0] < -20).sum()) if len(tilts) else 0, self.min_tilt_each),
            "tilt D": (int((tilts[:, 0] > 20).sum()) if len(tilts) else 0, self.min_tilt_each),
            "frontal": (int((np.abs(tilts) < 12).all(1).sum()) if len(tilts) else 0, self.min_frontal),
            "near": (int((areas > 0.30).sum()), 0 if skipped_near else self.min_near),
            "far": (int((areas < 0.13).sum()), 0 if skipped_far else self.min_far),
        }
        ok = {k: v[0] >= v[1] for k, v in chk.items()}
        if uncertainty is None:
            ok["uncertainty"] = False
            chk["uncertainty"] = (None, self.max_uncertainty_px)
        else:
            ok["uncertainty"] = uncertainty <= self.max_uncertainty_px
            chk["uncertainty"] = (round(uncertainty, 3), self.max_uncertainty_px)
        done = all(ok.values()) or len(captures) >= self.max_views
        self.state = {"checks": chk, "ok": ok, "done": done}
        return done, self.state


# =============================================================================
class ExposureController:
    """Drives manual exposure/gain so white squares sit at `target` grey level.

    Works on the board region when the board is visible, else on the whole frame.
    Exposure is capped at `max_exposure` (V4L2 units of 100 us) to limit motion
    blur; gain is used only when exposure is at the cap.
    """

    def __init__(self, controls, target: float = 205.0, max_exposure: int = 200, max_gain: int = 40,
                 exposure_key: Optional[str] = None):
        self.controls = controls
        self.target, self.max_exposure, self.max_gain = target, max_exposure, max_gain
        self.key = exposure_key
        self.enabled = controls is not None and exposure_key is not None
        self.last_change = 0.0
        self.settle_s = 0.6
        self.converged = False
        self.limited = False
        self._next_eval = 0.0
        self.status = "exposure: not controllable" if not self.enabled else "exposure: tuning"
        if self.enabled:
            cur = controls.current()
            if cur.get("auto_exposure", 1) != 1:
                controls.set("auto_exposure", 1)
            self.has_gain = "gain" in cur

    def update(self, frame: np.ndarray, corners: Optional[np.ndarray], now: float) -> None:
        if not self.enabled or now - self.last_change < self.settle_s or now < self._next_eval:
            return
        self._next_eval = now + 0.25
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        small = cv2.resize(g, (g.shape[1] // 4, g.shape[0] // 4), interpolation=cv2.INTER_AREA) if g.shape[1] > 1600 else g
        s = small.shape[1] / g.shape[1]
        if corners is not None and len(corners) >= 6:
            m = np.zeros(small.shape, np.uint8)
            cv2.fillConvexPoly(m, cv2.convexHull((corners * s).astype(np.int32)), 255)
            vals = small[m > 0]
            white = float(np.percentile(vals, 97)) if vals.size else float(np.percentile(small, 97))
            sat = float((vals >= 250).mean()) if vals.size else 0.0
        else:
            white = float(np.percentile(small, 97))
            sat = float((small >= 250).mean())
        cur = self.controls.current()
        e = int(cur.get(self.key, 100))
        gain = int(cur.get("gain", 0)) if self.has_gain else 0
        if sat > 0.003:
            ratio = 0.7
        else:
            ratio = self.target / max(white, 1.0)
        if abs(ratio - 1.0) < 0.12:
            self.converged = True
            self.status = f"exposure OK ({e / 10:.1f} ms, gain {gain}, white {white:.0f})"
            return
        self.converged = False
        ratio = float(np.clip(ratio, 0.5, 2.0))
        new_e, new_g = e, gain
        if ratio > 1:
            new_e = min(self.max_exposure, max(e + 1, int(round(e * ratio))))
            if new_e == e and self.has_gain and gain < self.max_gain:
                new_g = min(self.max_gain, gain + max(2, int(gain * (ratio - 1))))
        else:
            if self.has_gain and gain > 0:
                new_g = max(0, int(gain * ratio) - 1)
            else:
                new_e = max(1, min(e - 1, int(round(e * ratio))))
        if new_e == e and new_g == gain:
            # at the limits (exposure cap for motion blur, gain cap for noise)
            self.limited = True
            self.status = (f"TOO DARK - add light (white {white:.0f}/{self.target:.0f} at {e / 10:.1f} ms, gain {gain})"
                           if ratio > 1 else f"TOO BRIGHT - reduce light/glare (white {white:.0f})")
            self._next_eval = now + self.settle_s      # re-check later; NOT a change (doesn't block captures)
            return
        self.limited = False
        if new_e != e:
            self.controls.set(self.key, new_e)
        if new_g != gain:
            self.controls.set("gain", new_g)
        self.last_change = now
        self.status = f"exposure tuning: {e / 10:.1f}->{new_e / 10:.1f} ms, gain {gain}->{new_g}, white {white:.0f}"
