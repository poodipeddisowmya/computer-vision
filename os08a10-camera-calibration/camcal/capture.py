"""Fully automatic, guided capture of calibration views.

The board stays fixed (flat, on a wall or table); the operator moves the camera.
The pipeline does the rest:

  * shows a ghost outline of the next most useful view and plain-language hints
    ("move CLOSER, aim camera LEFT"),
  * tunes exposure automatically (short exposure first, gain only if needed),
  * captures by itself whenever the camera is still and the view adds
    information (matches the target, covers new image area or fills a
    missing tilt / distance bin),
  * per capture: N fresh frames -> stillness check (rolling shutter) ->
    average to 16 bit -> full-resolution corner refinement -> quality gates,
  * runs an intermediate calibration in the background every few views:
    refines the ghost projection, removes inconsistent views automatically,
    and re-ranks remaining targets by calibration uncertainty,
  * declares the data set complete when coverage / image corners / tilt and
    distance diversity / uncertainty all meet target, then finishes.
SPACE still forces a capture; N skips a target; Q finishes early.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .board import BoardDetector, BoardSpec, local_square_px, to_gray_f32, to_gray8
from .camera import Camera, ControlSession, Mode
from .guide import Completion, ExposureController, PosePlanner, descriptor_from_points
from .v4l2 import V4L2Device, control_dump

log = logging.getLogger("camcal")

GREEN, RED, YELLOW, WHITE = (60, 220, 60), (60, 60, 240), (40, 220, 240), (240, 240, 240)
CYAN, GREY, MAGENTA = (230, 200, 60), (150, 150, 150), (230, 80, 230)


@dataclass
class CaptureConfig:
    frames_to_average: int = 2        # hand-held: 2 consecutive frames (averaged only if they agree)
    still_px: float = 1.0             # max motion between the 2 frames (~16 px/s at 4K: blur < 0.3 px at 20 ms)
    average_below_px: float = 0.35    # frames are averaged only if they moved less than this; else the sharper single frame
    stable_px_1080: float = 0.6       # preview stability threshold, scaled with image width
    stable_time_s: float = 0.30       # steadiness needed before an auto capture
    min_corners: int = 20
    min_square_px: float = 14.0
    max_saturated_frac: float = 0.005
    min_contrast: float = 60.0
    min_pose_distance: float = 0.06   # novelty threshold in pose-descriptor space
    target_views: int = 40
    warmup_minutes: float = 10.0
    nominal_hfov_deg: float = 70.0    # initial guidance only; replaced by intermediate calibration
    preview_max_width: int = 1600
    preview_detect_width: int = 1920
    warm_since: Optional[float] = None   # time.monotonic() when the camera started streaming (preview counts)
    auto_exposure: bool = True
    max_exposure: int = 200           # 100 us units (20 ms) - short for hand-held motion
    max_gain: int = 40
    target_timeout_s: float = 30.0    # the magenta target is only a suggestion; move on quickly
    intermediate_every: int = 5
    finish_countdown_s: float = 5.0
    stall_s: float = 120.0            # finish if no useful view for this long (and min_views reached)
    max_regen_rounds: int = 4
    completion: dict = field(default_factory=dict)


@dataclass
class Accepted:
    index: int
    name: str
    ids: np.ndarray
    corners: np.ndarray
    descriptor: np.ndarray
    metrics: dict = field(default_factory=dict)


# =============================================================================
class FakeCamera:
    """Replays images from a folder as a live camera (dry-runs / tests)."""

    def __init__(self, folder: str, mode: Mode, fps: float = 5.0, noise: float = 1.0):
        self.files = sorted([p for p in Path(folder).glob("*.png")] + [p for p in Path(folder).glob("*.jpg")])
        if not self.files:
            raise RuntimeError(f"no images in {folder}")
        self.mode, self.noise, self._fps = mode, noise, fps
        self.idx, self._seq, self.started = 0, 0, time.monotonic()
        self._cache = {}

    def _img(self):
        p = self.files[self.idx % len(self.files)]
        if p not in self._cache:
            im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
            if im.dtype == np.uint16:
                im = (im / 257.0).astype(np.uint8)
            if im.ndim == 2:
                im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
            if (im.shape[1], im.shape[0]) != (self.mode.width, self.mode.height):
                im = cv2.resize(im, (self.mode.width, self.mode.height), interpolation=cv2.INTER_AREA)
            self._cache = {p: im}
        im = self._cache[p].astype(np.float32)
        return np.clip(im + np.random.normal(0, self.noise, im.shape), 0, 255).astype(np.uint8)

    def next_view(self):
        self.idx += 1

    def latest(self):
        self._seq += 1
        time.sleep(1.0 / self._fps)
        return self._seq, self._img(), time.monotonic()

    def wait_frames(self, n, timeout=None):
        return [self.latest()[1] for _ in range(n)]

    @property
    def fps(self):
        return self._fps

    def release(self):
        pass


def screen_size() -> tuple[int, int]:
    """Primary screen size (falls back to 1920x1080)."""
    try:
        import subprocess
        out = subprocess.run(["xrandr", "--current"], capture_output=True, text=True, timeout=3).stdout
        for line in out.splitlines():
            if "*" in line:
                w, h = line.split()[0].split("x")
                return int(w), int(h)
    except Exception:
        pass
    return 1920, 1080


def _fit_window(window: str, w: int, h: int):
    """Make an OpenCV window as large as the screen allows (keeping aspect) and bring it to the front."""
    sw, sh = screen_size()
    s = min((sw - 40) / w, (sh - 110) / h)
    cv2.resizeWindow(window, int(w * s), int(h * s))
    cv2.moveWindow(window, 10, 40)
    try:
        cv2.setWindowProperty(window, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass
    try:
        from .winraise import raise_window
        for _ in range(3):               # the WM may not have mapped it yet: ask a few times
            cv2.waitKey(100)
            raise_window(window)         # GNOME ignores OpenCV's raise; ask the WM directly (X11)
    except Exception:
        pass


def guess_K(w: int, h: int, hfov_deg: float) -> np.ndarray:
    f = (w / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    return np.array([[f, 0, (w - 1) / 2.0], [0, f, (h - 1) / 2.0], [0, 0, 1.0]])


def board_mask(shape, corners):
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillConvexPoly(m, cv2.convexHull(corners.astype(np.float32)).astype(np.int32), 255)
    return m > 0


def photometric_metrics(gray8: np.ndarray, gray_f: np.ndarray, corners: np.ndarray, sq_px: float) -> dict:
    mask = board_mask(gray8.shape, corners)
    vals = gray8[mask]
    sat = float((vals >= 250).mean()) if vals.size else 1.0
    p5, p95 = (np.percentile(vals, [5, 95]) if vals.size else (0, 0))
    contrast = float(p95 - p5)
    gx = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)
    g = cv2.magnitude(gx, gy)
    r = max(3, int(0.35 * sq_px))
    h, w = gray8.shape[:2]
    vals_g = []
    for x, y in corners[:: max(1, len(corners) // 40)]:
        x0, x1 = int(max(0, x - r)), int(min(w, x + r + 1))
        y0, y1 = int(max(0, y - r)), int(min(h, y + r + 1))
        if x1 > x0 and y1 > y0:
            vals_g.append(float(np.percentile(g[y0:y1, x0:x1], 98)))
    sharp = float(np.median(vals_g)) / (4.0 * max(contrast, 1.0)) if vals_g else 0.0
    return {"saturated_frac": sat, "contrast": contrast, "sharpness": sharp}


def corner_region_counts(cover_pts: list, size, frac: float = 0.15) -> list[int]:
    w, h = size
    cw, ch = frac * w, frac * h
    if not cover_pts:
        return [0, 0, 0, 0]
    P = np.concatenate(cover_pts)
    out = []
    for x, y in ((0, 0), (w - cw, 0), (0, h - ch), (w - cw, h - ch)):
        out.append(int(((P[:, 0] >= x) & (P[:, 0] < x + cw) & (P[:, 1] >= y) & (P[:, 1] < y + ch)).sum()))
    return out


# =============================================================================
class CaptureApp:
    def __init__(self, cam, spec: BoardSpec, mode: Mode, out: Path, cfg: CaptureConfig,
                 controls: Optional[ControlSession] = None, auto: bool = True, resume: bool = False,
                 K0: Optional[np.ndarray] = None, D0: Optional[np.ndarray] = None):
        self.cam, self.spec, self.mode, self.out, self.cfg, self.controls = cam, spec, mode, out, cfg, controls
        self.size = (mode.width, mode.height)
        self.detector = BoardDetector(spec)
        self.K_est = np.array(K0, float) if K0 is not None else guess_K(mode.width, mode.height, cfg.nominal_hfov_deg)
        self.D_est = np.array(D0, float) if D0 is not None else np.zeros(5)
        self.planner = PosePlanner(spec, self.size, self.K_est, self.D_est)
        self.completion = Completion(**cfg.completion)
        self.accepted: list[Accepted] = []
        self.rejected = 0
        self.auto = auto
        self.msg, self.msg_col, self.msg_t = "Point the camera at the board", WHITE, time.monotonic()
        self.busy = False
        self.live = None                 # (det, desc, info) from preview detection
        self.jitter = None
        self.stable_since = None
        self.last_attempt_t = 0.0
        self.last_reject_desc = None
        self.show_grid, self.show_help = True, False
        self.inter = None                # intermediate calibration summary
        self._inter_busy = False
        self._inter_n = 0
        self.aspect = None
        self._aspect_n = 0
        self.last_accept_t = time.monotonic()
        self._regen_rounds = 0
        self._rng = np.random.default_rng(7)
        self._lock = threading.RLock()
        self.complete_since = None
        self.finished = False
        self.aborted = False
        self.last_why = (None, 0.0)             # ESC / window closed: stop the whole run, not just this mode
        self.warmup_skipped = False
        self._last_log = ("", 0.0)
        self.keep_going = False
        self._stop = False
        self.t_start = time.monotonic()
        self.cover = np.zeros((9, 16), int)
        self.stable_px = cfg.stable_px_1080 * mode.width / 1920.0
        self.out.mkdir(parents=True, exist_ok=True)
        self.exposure_key = None
        if controls is not None:
            cur = controls.current()
            self.exposure_key = next((k for k in ("exposure_time_absolute", "exposure_absolute") if k in cur), None)
        self.exposure = ExposureController(controls if cfg.auto_exposure else None, max_exposure=cfg.max_exposure,
                                           max_gain=cfg.max_gain, exposure_key=self.exposure_key)
        self.last_exposure_change = 0.0
        self.settle_s = max(1.0, 2.5 / max(mode.fps, 0.5))   # slow modes need longer to show a change
        self.exposure.settle_s = max(self.exposure.settle_s, self.settle_s)
        if resume:
            self._load_existing()
        self._det_thread = threading.Thread(target=self._preview_loop, daemon=True)
        self._det_thread.start()

    # =================================================================== persistence
    def _load_existing(self):
        p = self.out / "captures.json"
        if not p.exists():
            return
        for c in json.loads(p.read_text()):
            if not (self.out / f"{c['name']}_mean.png").exists() or "ids" not in c:
                continue
            a = Accepted(c["index"], c["name"], np.array(c["ids"], int), np.array(c["corners"], float),
                         np.array(c["descriptor"], float), c.get("metrics", {}))
            self.accepted.append(a)
            self._add_cover(a.corners, +1)
            self.planner.mark_captured(a.descriptor)
        if self.accepted:
            self.say(f"resumed session with {len(self.accepted)} captures", CYAN)
            self._maybe_intermediate(force=True)

    def _write_index(self):
        with self._lock:
            data = [{"index": a.index, "name": a.name, "metrics": a.metrics, "descriptor": a.descriptor.tolist(),
                     "ids": a.ids.tolist(), "corners": a.corners.tolist()} for a in self.accepted]
        (self.out / "captures.json").write_text(json.dumps(data, default=float))

    # =================================================================== preview / auto logic
    def _preview_loop(self):
        last_seq = -1
        prev = None
        while not self._stop:
            seq, frame, _ = self.cam.latest()
            if seq == last_seq or frame is None:
                time.sleep(0.01)
                continue
            last_seq = seq
            now = time.monotonic()
            try:
                d = self.detector.detect_fast(frame, self.cfg.preview_detect_width)
            except cv2.error:
                continue
            desc = info = None
            if d.n >= 8:
                r = descriptor_from_points(d.ids, d.corners, self.spec, self.K_est, self.D_est, self.size)
                if r:
                    desc, info = r
            if prev is not None and d.n and prev.n:
                common, ia, ib = np.intersect1d(d.ids, prev.ids, return_indices=True)
                self.jitter = float(np.percentile(np.linalg.norm(d.corners[ia] - prev.corners[ib], axis=1), 90)) \
                    if len(common) >= 4 else None
            else:
                self.jitter = None
            prev = d
            if self.jitter is not None and self.jitter < self.stable_px:
                self.stable_since = self.stable_since or now
            else:
                self.stable_since = None
            self.live = (d, desc, info)
            if not self.busy and self.exposure.enabled:
                before = self.exposure.last_change
                try:
                    self.exposure.update(frame, d.corners if d.n >= 6 else None, now)
                except OSError as e:
                    log.warning("exposure control failed: %s", e)
                    self.exposure.enabled = False
                if self.exposure.last_change != before:
                    self.last_exposure_change = now
            if self.auto and not self.busy and not self.finished:
                self._auto_decide(now)

    def _useful(self, d, desc, info) -> Optional[str]:
        """Why this live view is worth capturing (None = not useful)."""
        with self._lock:
            descs = [a.descriptor for a in self.accepted]
        if descs and min(float(np.linalg.norm(desc - x)) for x in descs) < self.cfg.min_pose_distance:
            return None
        if self.planner.match(desc) < self.planner.match_thr:
            return "matches target"
        w, h = self.size
        gx = np.clip((d.corners[:, 0] / w * 16).astype(int), 0, 15)
        gy = np.clip((d.corners[:, 1] / h * 9).astype(int), 0, 8)
        new_cells = len({(a, b) for a, b in zip(gy, gx) if self.cover[a, b] == 0})
        if new_cells >= 3:
            return f"+{new_cells} new cells"
        st = self.completion.state.get("ok", {})
        if not st.get("img corners", False):
            with self._lock:
                have = corner_region_counts([a.corners for a in self.accepted], self.size, self.completion.corner_region_frac)
            live = corner_region_counts([d.corners], self.size, self.completion.corner_region_frac)
            if any(l >= 3 and hv < self.completion.min_corner_pts for l, hv in zip(live, have)):
                return "adds image-corner points"
        tx, ty, area = info["tilt_x_deg"], info["tilt_y_deg"], info["area_frac"]
        bins = {"tilt L": ty < -20, "tilt R": ty > 20, "tilt U": tx < -20, "tilt D": tx > 20,
                "frontal": abs(tx) < 12 and abs(ty) < 12, "near": area > 0.30, "far": area < 0.13}
        for k, hit in bins.items():
            if hit and not st.get(k, False):
                return f"fills '{k}'"
        if len(descs) < self.completion.max_views:
            return "new view"          # hand-held: every steady, sharp, sufficiently different view adds data
        return None

    def _auto_decide(self, now):
        live = self.live
        if live is None or self.warmup_left > 0:
            return
        d, desc, info = live
        if desc is None or d.n < self.cfg.min_corners or self.stable_since is None:
            return
        if now - self.stable_since < self.cfg.stable_time_s or now - self.last_attempt_t < 1.0:
            return
        if now - self.last_exposure_change < self.settle_s:
            return
        if self.last_reject_desc is not None and np.linalg.norm(desc - self.last_reject_desc) < 0.03:
            return
        why = self._useful(d, desc, info)
        self.last_why = (why, now)
        if why:
            self.trigger_capture(reason=why)

    def say(self, text, col=WHITE):
        now = time.monotonic()
        self.msg, self.msg_col, self.msg_t = text, col, now
        key = text.split(":")[0]
        if key != self._last_log[0] or now - self._last_log[1] > 15:   # repeated messages: screen only
            self._last_log = (key, now)
            (log.info if col != RED else log.warning)(text)

    @property
    def warmup_left(self) -> float:
        if self.warmup_skipped:
            return 0.0
        since = self.cfg.warm_since if self.cfg.warm_since is not None else self.t_start
        return max(0.0, self.cfg.warmup_minutes * 60.0 - (time.monotonic() - since))

    # =================================================================== capture
    def trigger_capture(self, reason: str = "manual"):
        if self.busy or self.finished:
            return
        if self.warmup_left > 0:
            self.say(f"Warm-up: {self.warmup_left / 60:.1f} min left - captures start by themselves "
                     f"(W = skip warm-up)", YELLOW)
            return
        self.busy = True
        self.last_attempt_t = time.monotonic()
        threading.Thread(target=self._capture, args=(reason,), daemon=True).start()

    def _capture(self, reason):
        try:
            if self.controls is not None:
                drift = self.controls.drift()
                if drift:
                    self.say(f"camera controls changed externally {drift} - re-locking", RED)
                    self.controls.reapply()
                    return
            frames = self.cam.wait_frames(self.cfg.frames_to_average)
            d_first = self.detector.detect(frames[0])
            d_last = self.detector.detect(frames[-1])
            if min(d_first.n, d_last.n) < self.cfg.min_corners:
                return self.reject(f"too few corners ({min(d_first.n, d_last.n)})", quiet=reason != "manual")
            common, ia, ib = np.intersect1d(d_first.ids, d_last.ids, return_indices=True)
            motion = float(np.max(np.linalg.norm(d_first.corners[ia] - d_last.corners[ib], axis=1))) if len(common) else 99
            if motion > self.cfg.still_px:
                return self.reject(f"camera moved {motion:.2f}px during capture - hold still", quiet=reason != "manual")
            if motion <= self.cfg.average_below_px:
                mean = np.mean([f.astype(np.float32) for f in frames], axis=0)
            else:                      # moving slowly: one frame (20 ms exposure) is sharper than a blurred average
                mean = frames[-1].astype(np.float32)
            gray_f = cv2.cvtColor(mean, cv2.COLOR_BGR2GRAY) if mean.ndim == 3 else mean
            gray16 = np.clip(gray_f * 257.0 + 0.5, 0, 65535).astype(np.uint16)
            det = self.detector.detect(gray16)
            if det.n < self.cfg.min_corners:
                return self.reject(f"too few refined corners ({det.n})")
            sq = float(np.median(local_square_px(det, self.spec)))
            if sq < self.cfg.min_square_px:
                return self.reject(f"squares too small ({sq:.1f}px) - move closer")
            pm = photometric_metrics(to_gray8(gray16), to_gray_f32(gray16), det.corners, sq)
            if pm["saturated_frac"] > self.cfg.max_saturated_frac:
                return self.reject(f"glare / overexposed ({pm['saturated_frac']:.1%}) - change angle to avoid reflections")
            if pm["contrast"] < self.cfg.min_contrast:
                return self.reject(f"low contrast {pm['contrast']:.0f} - more light")
            with self._lock:
                sharp_ref = np.median([a.metrics["sharpness"] for a in self.accepted]) if len(self.accepted) >= 3 else None
            if sharp_ref and pm["sharpness"] < 0.55 * sharp_ref:
                return self.reject("blurry - outside the lens' sharp range or moving; change distance")
            r = descriptor_from_points(det.ids, det.corners, self.spec, self.K_est, self.D_est, self.size)
            if r is None:
                return self.reject("pose could not be estimated")
            desc, pose = r
            with self._lock:
                existing = list(self.accepted)
            if existing:
                dists = [float(np.linalg.norm(desc - a.descriptor)) for a in existing]
                j = int(np.argmin(dists))
                if dists[j] < self.cfg.min_pose_distance:
                    if reason == "manual":
                        return self.reject(f"too similar to capture #{existing[j].index} - move the camera")
                    return self.reject("too similar to an existing view", quiet=True, desc=desc)
            idx = (max(a.index for a in existing) + 1) if existing else 0
            name = f"img_{idx:03d}"
            cv2.imwrite(str(self.out / f"{name}_mean.png"), gray16)
            cv2.imwrite(str(self.out / f"{name}_color.jpg"), frames[0], [cv2.IMWRITE_JPEG_QUALITY, 92])
            metrics = {**pm, **{k: v for k, v in pose.items() if k not in ("rvec", "tvec")},
                       "n_corners": int(det.n), "square_px": sq, "motion_px": motion, "reason": reason,
                       "time": dt.datetime.now().isoformat(timespec="seconds"),
                       "uptime_s": time.monotonic() - self.t_start}
            if self.controls is not None:
                metrics["controls"] = self.controls.current()
            a = Accepted(idx, name, det.ids, det.corners, desc, metrics)
            with self._lock:
                self.accepted.append(a)
                self._add_cover(det.corners, +1)
            self.last_accept_t = time.monotonic()
            hit = self.planner.mark_captured(desc)
            self._write_index()
            self.say(f"#{idx} captured ({reason}{'; target: ' + hit[0].name if hit else ''}): {det.n} corners, "
                     f"motion {motion:.2f}px, tilt ({pose['tilt_x_deg']:+.0f},{pose['tilt_y_deg']:+.0f})", GREEN)
            if isinstance(self.cam, FakeCamera):
                self.cam.next_view()
            self._maybe_intermediate()
        except Exception as e:  # never kill the UI
            log.exception("capture failed")
            self.reject(f"capture error: {e}")
        finally:
            self.busy = False

    def reject(self, why, quiet=False, desc=None):
        self.rejected += 1
        self.last_reject_desc = desc if desc is not None else (self.live[1] if self.live else None)
        if quiet:
            log.debug("auto-capture skipped: %s", why)
        else:
            self.say("REJECTED: " + why, RED)
        if isinstance(self.cam, FakeCamera):
            self.cam.next_view()

    def remove(self, a: Accepted, why: str):
        with self._lock:
            if a not in self.accepted:
                return
            self.accepted.remove(a)
            self._add_cover(a.corners, -1)
        for suf in ("_mean.png", "_color.jpg"):
            p = self.out / f"{a.name}{suf}"
            if p.exists():
                p.unlink()
        self._write_index()
        self.say(f"removed #{a.index}: {why}", YELLOW)

    def undo(self):
        if self.accepted:
            self.remove(self.accepted[-1], "undo")

    def _add_cover(self, corners, sign):
        w, h = self.size
        gx = np.clip((corners[:, 0] / w * 16).astype(int), 0, 15)
        gy = np.clip((corners[:, 1] / h * 9).astype(int), 0, 8)
        np.add.at(self.cover, (gy, gx), sign)

    # =================================================================== intermediate calibration
    def _maybe_intermediate(self, force=False):
        n = len(self.accepted)
        if self._inter_busy or n < 10 or (not force and n - self._inter_n < self.cfg.intermediate_every):
            self._evaluate_completion()
            return
        self._inter_busy = True
        self._inter_n = n
        threading.Thread(target=self._intermediate, daemon=True).start()

    def _intermediate(self):
        from .calibrate import View, _calib, bootstrap
        try:
            with self._lock:
                caps = list(self.accepted)
            views = [View(a.name, a.ids, a.corners, self.spec.object_points(a.ids)) for a in caps]
            model = "brown_k1k2k3" if len(views) >= 15 else "brown_k1k2"
            if len(views) >= 15:
                from .calibrate import estimate_board_aspect, with_aspect
                if self.aspect is None or len(views) - self._aspect_n >= 10:
                    self.aspect = estimate_board_aspect(views, self.size, model)["aspect"]
                    self._aspect_n = len(views)
                views = with_aspect(views, self.aspect)
            r = _calib(views, self.size, model)
            pv = []
            for v, rv, tv in zip(views, r["rvecs"], r["tvecs"]):
                p, _ = cv2.projectPoints(v.obj.reshape(-1, 1, 3), rv, tv, r["K"], r["D"])
                pv.append(float(np.sqrt(np.mean(np.sum((p.reshape(-1, 2) - v.img) ** 2, 1)))))
            pv = np.array(pv)
            med = float(np.median(pv))
            bad_i = [int(i) for i in np.where(pv > max(0.8, 4.0 * med))[0]]
            for i in bad_i:     # inconsistent views (motion blur, bent board, mis-detection)
                self.remove(caps[i], f"inconsistent with the other views (RMS {pv[i]:.2f}px vs median {med:.2f})")
            if bad_i:
                views = [v for i, v in enumerate(views) if i not in bad_i]
                r = _calib(views, self.size, model)
            self.K_est, self.D_est = r["K"], r["D"]
            self.planner.update_model(self.K_est, self.D_est)
            with self._lock:
                for a in self.accepted:     # descriptors with the improved intrinsics
                    rr = descriptor_from_points(a.ids, a.corners, self.spec, self.K_est, self.D_est, self.size)
                    if rr:
                        a.descriptor = rr[0]
                        a.metrics.update({k: v for k, v in rr[1].items() if k in ("tilt_x_deg", "tilt_y_deg", "area_frac")})
            unc = None
            if len(views) >= 15:
                b = bootstrap(views, self.size, model, r["K"], r["D"], n=8, grid=(16, 9))
                unc = b["uncertainty_px_max"]
                g = np.array(b["uncertainty_px_grid"])
                self.planner.priority_map = g / max(g.max(), 1e-9) + (self.cover == 0) * 1.0
            else:
                self.planner.priority_map = (self.cover == 0) * 1.0
            self.inter = {"n": len(views), "rms": float(r["rms"]), "fx": float(r["K"][0, 0]), "uncertainty": unc}
            self.say(f"interim calibration ({len(views)} views): RMS {r['rms']:.3f}px, fx {r['K'][0, 0]:.1f}"
                     + (f", uncertainty {unc:.3f}px" if unc is not None else ""), CYAN)
        except Exception as e:
            log.warning("interim calibration failed: %s", e)
        finally:
            self._inter_busy = False
            self._evaluate_completion()
            if len(self.accepted) - self._inter_n >= self.cfg.intermediate_every:
                self._maybe_intermediate()

    def _check_progress(self, now):
        """Keep the run moving: new targets for unmet checks; finish if progress has stalled."""
        if self.warmup_left > 0 or self.complete_since is not None or self.finished:
            return
        st = self.completion.state
        unmet = [k for k, ok in st.get("ok", {}).items() if not ok] if st else []
        if not self.planner.pending() and unmet and self._regen_rounds < self.cfg.max_regen_rounds:
            n = self.planner.regenerate(unmet, self.cover, self._rng)
            self._regen_rounds += 1
            self.say(f"new guidance targets for: {', '.join(unmet)} ({n} targets)", CYAN)
        stalled = now - self.last_accept_t > self.cfg.stall_s
        if stalled and len(self.accepted) >= self.completion.min_views and not self.keep_going:
            self.complete_since = now - self.cfg.finish_countdown_s + 3.0
            self.say(f"no new useful views for {self.cfg.stall_s:.0f}s - finishing with what we have "
                     f"(unmet: {', '.join(unmet) or 'none'}); the calibration report will grade it", YELLOW)

    def _evaluate_completion(self):
        unc = self.inter["uncertainty"] if self.inter else None
        # interim uncertainty only counts if it was computed on (almost) the current data set
        if self.inter and len(self.accepted) - self.inter["n"] > self.cfg.intermediate_every:
            unc = None
        def all_skipped(word):   # waive a distance bin only if EVERY target of that kind proved unreachable
            ts = [t for t in self.planner.targets if word in t.name]
            return bool(ts) and all(t.state == "skipped" for t in ts)
        with self._lock:
            caps = list(self.accepted)
            cover = self.cover.copy()
        done, _ = self.completion.evaluate(caps, cover, corner_region_counts([a.corners for a in caps], self.size,
                                                                              self.completion.corner_region_frac), unc,
                                           skipped_far=all_skipped("far"), skipped_near=all_skipped("near"))
        if done and not self.keep_going and self.complete_since is None:
            self.complete_since = time.monotonic()
            self.say(f"DATA SET COMPLETE - finishing in {self.cfg.finish_countdown_s:.0f}s (K = keep capturing)", GREEN)
        elif not done:
            self.complete_since = None

    # =================================================================== drawing
    def live_status(self) -> tuple[str, tuple]:
        """Why the pipeline is (not) capturing right now, in plain words."""
        live = self.live
        if live is None:
            return "starting camera ...", GREY
        d = live[0]
        w = self.size[0]
        n_mk = 0 if d.marker_ids is None else len(d.marker_ids)
        if n_mk == 0:
            return "BOARD NOT FOUND - point the camera at the board (35-60 cm away)", RED
        if d.n < self.cfg.min_corners:
            s = min(1.0, self.cfg.preview_detect_width / float(w))
            side = float(np.median([cv2.arcLength(np.asarray(m, np.float32).reshape(-1, 1, 2), True) / 4.0
                                    for m in d.marker_corners])) / s if d.marker_corners else 0.0
            if side > 180.0 * w / 3840.0:
                return "TOO CLOSE / OUT OF FOCUS - move the camera BACK", RED
            return (f"BOARD SEEN BUT BLURRED ({d.n} corners) - hold still, add light on the board "
                    f"(or show more of it)"), YELLOW
        sq = float(np.median(local_square_px(d, self.spec)))
        if sq < self.cfg.min_square_px:
            return f"TOO FAR - squares are {sq:.0f}px (need {self.cfg.min_square_px:.0f}) - move CLOSER", YELLOW
        j = self.jitter
        if j is None or j >= self.stable_px:
            return (f"HOLD STILL - moving {j:.1f}px (needs < {self.stable_px:.1f}px). Rest the camera on something"
                    if j is not None else "HOLD STILL"), YELLOW
        if self.warmup_left > 0:
            m, sec = divmod(int(self.warmup_left), 60)
            return f"GOOD VIEW - warm-up {m}:{sec:02d} left, then captures start by themselves (W = skip)", CYAN
        if self.busy:
            return "CAPTURING - keep still", GREEN
        why, t = self.last_why
        if self.stable_since is not None and time.monotonic() - t < 1.5 and why is None:
            return "STILL, but this view is already covered - move to the MAGENTA outline", YELLOW
        return "STILL - capturing when useful", GREEN

    def draw(self, frame):
        h, w = frame.shape[:2]
        s = min(1.0, self.cfg.preview_max_width / float(w))
        view = cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else frame.copy()
        vh, vw = view.shape[:2]
        if self.show_grid:
            ov = view.copy()
            cw, ch = vw / 16.0, vh / 9.0
            for gy in range(9):
                for gx in range(16):
                    n = self.cover[gy, gx]
                    col = (0, int(120 + 135 * min(1.0, n / 30.0)), 0) if n > 0 else (40, 40, 160)
                    cv2.rectangle(ov, (int(gx * cw), int(gy * ch)), (int((gx + 1) * cw), int((gy + 1) * ch)), col, -1)
            view = cv2.addWeighted(ov, 0.14, view, 0.86, 0)
        t = self.planner.current(time.monotonic())
        if t is not None:
            poly = (self.planner.outline(t) * s).astype(np.int32)
            cv2.polylines(view, [poly], True, MAGENTA, 3, cv2.LINE_AA)
        live = self.live
        if live is not None and live[0].n:
            d = live[0]
            col = GREEN if self.stable_since is not None else YELLOW
            for (x, y) in d.corners[:: max(1, d.n // 60)]:
                cv2.circle(view, (int(x * s), int(y * s)), 3, col, -1, cv2.LINE_AA)
            hull = cv2.convexHull((d.corners * s).astype(np.int32))
            cv2.polylines(view, [hull], True, col, 2, cv2.LINE_AA)
        self._panel(view)
        return view

    def _panel(self, view):
        vh, vw = view.shape[:2]
        fs = 0.5 if vw < 1400 else 0.56
        lh = int(22 * fs / 0.5)
        st = self.completion.state
        lines = [(f"{self.mode.key} @ {self.cam.fps:4.1f} fps   captured {len(self.accepted)}   "
                  f"auto {'ON' if self.auto else 'OFF'}   {self.exposure.status}", WHITE)]
        if self.warmup_left > 0:
            lines.append((f"WARM-UP {self.warmup_left / 60:4.1f} min - captures start automatically afterwards", YELLOW))
        if st:
            items = [(f"{k} {val if val is not None else '-'}/{need}", GREEN if st["ok"].get(k) else RED)
                     for k, (val, need) in st["checks"].items()]
            half = (len(items) + 1) // 2
            for row in (items[:half], items[half:]):
                lines.append((row, None))
        if self.inter:
            u = self.inter["uncertainty"]
            lines.append((f"interim: RMS {self.inter['rms']:.3f}px  fx {self.inter['fx']:.1f}  "
                          f"uncertainty {'-' if u is None else f'{u:.3f}px'}", CYAN))
        live = self.live
        hint = self.planner.hint(live[1] if live else None)
        stable = "STILL - capturing when useful" if self.stable_since else "moving"
        lines.append((f"{hint}   [{stable}]", MAGENTA))
        box_h = lh * len(lines) + 14
        ov = view.copy()
        cv2.rectangle(ov, (0, 0), (vw, box_h), (0, 0, 0), -1)
        view[:] = cv2.addWeighted(ov, 0.6, view, 0.4, 0)
        y = 4
        for t, c in lines:
            y += lh
            if c is None:
                x = 10
                for txt, col in t:
                    cv2.putText(view, txt, (x, y), cv2.FONT_HERSHEY_SIMPLEX, fs, col, 1, cv2.LINE_AA)
                    x += int(cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)[0][0]) + 22
            else:
                cv2.putText(view, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, fs, c, 1, cv2.LINE_AA)
        if self.complete_since is not None:
            left = self.cfg.finish_countdown_s - (time.monotonic() - self.complete_since)
            txt = f"COMPLETE - finishing in {max(0, left):.0f}s   (K = keep capturing)"
            cv2.putText(view, txt, (max(10, vw // 2 - 330), vh // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, GREEN, 2, cv2.LINE_AA)
        if time.monotonic() - self.msg_t < 8:
            cv2.rectangle(view, (0, vh - 2 * lh - 12), (vw, vh - lh - 4), (0, 0, 0), -1)
            cv2.putText(view, self.msg, (10, vh - lh - 10), cv2.FONT_HERSHEY_SIMPLEX, fs * 1.05, self.msg_col, 1, cv2.LINE_AA)
        keys = ("captures automatically | SPACE force | N skip target | U undo | W skip warm-up | [ ] exposure | "
                "H help | Q finish this resolution | ESC stop all")
        cv2.rectangle(view, (0, vh - lh - 2), (vw, vh), (30, 30, 30), -1)
        cv2.putText(view, keys, (10, vh - 6), cv2.FONT_HERSHEY_SIMPLEX, fs * 0.9, GREY, 1, cv2.LINE_AA)
        if self.busy:
            cv2.circle(view, (vw - 30, box_h + 30), 16, YELLOW, -1)
        txt, col = self.live_status()
        bs = 0.95 if vw >= 1400 else 0.8
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, bs, 2)
        yb = vh - 2 * lh - 30
        cv2.rectangle(view, (0, yb - th - 16), (vw, yb + 12), (0, 0, 0), -1)
        cv2.putText(view, txt, (max(10, (vw - tw) // 2), yb), cv2.FONT_HERSHEY_SIMPLEX, bs, col, 2, cv2.LINE_AA)
        if self.show_help:
            hl = HELP.strip().splitlines()
            ov = view.copy()
            cv2.rectangle(ov, (40, 80), (vw - 40, 80 + 26 * len(hl) + 20), (0, 0, 0), -1)
            view[:] = cv2.addWeighted(ov, 0.85, view, 0.15, 0)
            for i, t in enumerate(hl):
                cv2.putText(view, t, (60, 110 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 1, cv2.LINE_AA)

    # =================================================================== manual exposure
    def adjust_exposure(self, factor):
        if self.controls is None or not self.exposure_key:
            self.say("exposure control not available", YELLOW)
            return
        self.exposure.enabled = False
        self.exposure.status = "exposure: manual"
        cur = self.controls.current()
        v = max(1, int(round(cur.get(self.exposure_key, 100) * factor)))
        if v == cur.get(self.exposure_key):
            v += 1 if factor > 1 else -1
        p = self.controls.set(self.exposure_key, v)
        self.last_exposure_change = time.monotonic()
        self.say(f"exposure -> {v / 10:.1f} ms (auto-exposure off, E to re-enable)" + (f" ({p})" if p else ""), CYAN)

    # =================================================================== main loop
    def run(self, window="camcal - automatic calibration capture", headless: bool = False,
            timeout_s: Optional[float] = None) -> list[Accepted]:
        if not headless:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        sized = shown = False
        t0 = time.monotonic()
        try:
            while True:
                now = time.monotonic()
                if self.complete_since is not None and now - self.complete_since >= self.cfg.finish_countdown_s:
                    self.finished = True
                    self.say("capture complete", GREEN)
                    break
                if timeout_s and now - t0 > timeout_s:
                    self.say("timeout", YELLOW)
                    break
                self._check_progress(now)
                t = self.planner.current(now)
                if t is not None and self.warmup_left <= 0 and now - max(t.shown_since, t0) > self.cfg.target_timeout_s:
                    self.say(f"skipping target '{t.name}' (not reached in {self.cfg.target_timeout_s:.0f}s)", YELLOW)
                    self.planner.skip_current()
                    self._evaluate_completion()
                if headless:
                    time.sleep(0.05)
                    continue
                seq, frame, _ = self.cam.latest()
                if frame is None:
                    continue
                canvas = self.draw(frame)
                cv2.imshow(window, canvas)
                if not sized:
                    _fit_window(window, canvas.shape[1], canvas.shape[0])
                    sized = True
                k = cv2.waitKey(15) & 0xFF
                vis = cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE)
                shown = shown or vis >= 1
                if k == 27 or (shown and vis < 1):
                    self.aborted = True
                    self.say("stopped by user (ESC / window closed) - ending the run", YELLOW)
                    break
                if k in (ord("q"), ord("Q")):
                    break
                elif k in (ord("w"), ord("W")) and self.warmup_left > 0:
                    self.warmup_skipped = True
                    self.say("warm-up skipped by user (recorded in the session)", YELLOW)
                elif k == 32:
                    self.trigger_capture("manual")
                elif k in (ord("n"), ord("N")):
                    self.planner.skip_current()
                    self._evaluate_completion()
                elif k in (ord("u"), ord("U")):
                    self.undo()
                elif k in (ord("a"), ord("A")):
                    self.auto = not self.auto
                    self.say(f"auto-capture {'ON' if self.auto else 'OFF'}", CYAN)
                elif k in (ord("e"), ord("E")):
                    self.exposure.enabled = self.exposure_key is not None and self.controls is not None
                    self.say("auto-exposure ON" if self.exposure.enabled else "auto-exposure unavailable", CYAN)
                elif k in (ord("k"), ord("K")):
                    self.keep_going, self.complete_since = True, None
                    self.say("continuing capture (Q to finish)", CYAN)
                elif k == ord("["):
                    self.adjust_exposure(1 / 1.25)
                elif k == ord("]"):
                    self.adjust_exposure(1.25)
                elif k in (ord("g"), ord("G")):
                    self.show_grid = not self.show_grid
                elif k in (ord("h"), ord("H")):
                    self.show_help = not self.show_help
        finally:
            self._stop = True
            while self.busy or self._inter_busy:
                time.sleep(0.05)
            self._det_thread.join(timeout=3.0)   # no OpenCV work left running into the next stage / exit
            if not headless:
                cv2.destroyWindow(window)
        return self.accepted


HELP = """
AUTOMATIC CAPTURE - the board stays fixed, you move the camera
 1. Board glued FLAT (glass / aluminium), fixed to a wall or table, evenly lit, no glare.
 2. Move the camera so the live board (green) overlaps the MAGENTA outline, then hold still.
    The capture happens by itself (green dots = still). Follow the text hints.
 3. Any still view that adds information is captured too - you don't need to be exact.
 4. A tripod with a ball head, or bracing the camera, makes captures fast and sharp.
 5. The run ends automatically when the checklist is all green.
Keys: SPACE force capture  N skip target  U undo  A auto on/off  E auto-exposure  W skip warm-up
      [ ] manual exposure  K keep capturing after completion  G grid  H help
      Q finish this resolution (calibrate it)   ESC / close window = stop the whole run
"""


# =============================================================================
def run_capture_session(device: Optional[str], mode: Mode, spec: BoardSpec, out: Path, cfg: CaptureConfig,
                        lock: dict, simulate: Optional[str] = None, auto: bool = True,
                        headless: bool = False, resume: bool = False, K0=None, D0=None,
                        cam=None, controls: Optional[ControlSession] = None, timeout_s=None) -> dict:
    """Run one capture session. If `controls` is given the caller owns the control session
    (multi-profile runs keep one snapshot/restore around everything)."""
    out.mkdir(parents=True, exist_ok=True)
    spec.save(out / "board.json")
    sp = out / "session.json"
    session = json.loads(sp.read_text()) if (resume and sp.exists()) else {}
    session.update({"mode": mode.as_dict(), "board": spec.__dict__, "capture_config": cfg.__dict__,
                    "lock_requested": lock})
    session.setdefault("started", dt.datetime.now().isoformat(timespec="seconds"))

    if simulate or cam is not None:
        cam = cam or FakeCamera(simulate, mode)
        app = CaptureApp(cam, spec, mode, out, cfg, None, auto, resume, K0, D0)
        app.run(headless=headless, timeout_s=timeout_s)
        session.update({"device_info": session.get("device_info") or {"simulated": str(simulate or type(cam).__name__)},
                        "n_captures": len(app.accepted), "complete": app.finished, "aborted": app.aborted,
                        "completion": app.completion.state, "finished": dt.datetime.now().isoformat(timespec="seconds")})
        sp.write_text(json.dumps(session, indent=2, default=str))
        return session

    with V4L2Device(device) as d:
        info, formats = d.info(), d.formats()
        session["device_info"] = info
        session["device_formats"] = formats
        session.setdefault("controls_before", control_dump(d.controls()))
    listed = any(f["fourcc"] == mode.fourcc and any(s.get("width") == mode.width and s.get("height") == mode.height
                                                    for s in f["sizes"]) for f in formats)
    if not listed:
        raise RuntimeError(f"{device} does not advertise {mode.key}. Run `python3 -m camcal probe`.")
    sp.write_text(json.dumps(session, indent=2, default=str))

    own = controls is None
    cs = controls or ControlSession(device, lock)
    if own:
        cs.__enter__()
    camera = None
    try:
        camera = Camera(device, mode)
        time.sleep(0.5)
        session["lock_problems"] = cs.reapply()       # some UVC firmwares reset controls at stream-on
        with V4L2Device(device) as d:
            ctrls = d.controls()
        session["geometry_controls"] = {k: v for k, v in cs.applied.items() if k in ctrls and ctrls[k].is_geometry}
        session["actual_fps"] = camera.actual_fps
        app = CaptureApp(camera, spec, mode, out, cfg, cs, auto, resume, K0, D0)
        app.run(headless=headless, timeout_s=timeout_s)
        session["controls_locked"] = cs.applied
        session["n_captures"] = len(app.accepted)
        session["n_rejected"] = app.rejected
        session["complete"] = app.finished
        session["aborted"] = app.aborted
        session["warmup_skipped"] = app.warmup_skipped
        session["completion"] = app.completion.state
    finally:
        if camera is not None:
            camera.release()
        if own:
            cs.__exit__(None, None, None)
            session["restore_diff"] = getattr(cs, "last_restore", {})
            with V4L2Device(device) as d:
                session["controls_after_restore"] = d.snapshot()
    session["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    sp.write_text(json.dumps(session, indent=2, default=str))
    return session
