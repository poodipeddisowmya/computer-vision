"""Simple hand-held capture: move the camera around the board, images are taken for you.

No targets, no checklist, no warm-up. The window shows the live camera with the detected
corners, a big counter and a tint of where in the image you have already covered.

  - Auto-capture: whenever the board is clearly visible, the camera is reasonably steady and
    the view is different from the ones already taken.
  - SPACE: capture right now (board must be visible).
  - U: undo the last capture.   ENTER: done -> calibrate.   ESC / Q: quit without calibrating.

Exposure is kept short automatically (motion blur), and every camera setting is restored on exit.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .board import BoardDetector, BoardSpec, local_square_px, predict_from_neighbours, to_gray8
from .camera import Camera, ControlSession, Mode
from .capture import _fit_window, guess_K
from .guide import ExposureController, descriptor_from_points

log = logging.getLogger("camcal")
WIN = "camcal - simple calibration capture"
GREEN, RED, YELLOW, WHITE, GREY, CYAN = (60, 220, 60), (60, 60, 235), (40, 220, 240), (240, 240, 240), \
    (150, 150, 150), (230, 200, 60)
FONT = cv2.FONT_HERSHEY_SIMPLEX


class SimpleCapture:
    MIN_CORNERS = 25
    SPEED_MAX_4K = 130.0        # px/s at 3840 wide (hand-held); skew is random per view and averages out
    NOVELTY = 0.05              # pose-descriptor distance to every previous capture
    COOLDOWN_S = 0.8
    GOOD_COUNT = 35
    CORNER_FRAC = 0.15          # image-corner boxes (same definition as the calibration report)
    CORNER_NEED = 40            # corner points wanted in each box
    MAX_NOISE_PX_4K = 1.0       # reject only clearly blurred views; moderate noise averages out over 1000s of corners
    AUTO_FINISH_COUNT = 40      # finish by itself once all corner boxes are green and this many images exist
    MIN_TO_CALIBRATE = 20
    # STILL mode: camera resting on something for each shot -> clean, averaged, motion-free images
    STILL = {"speed_4k": 8.0, "avg_frames": 8, "avg_motion_px": 0.35, "noise_4k": 0.5, "auto_finish": 30,
             "cooldown_s": 1.5}

    def __init__(self, cam: Camera, spec: BoardSpec, out: Path, controls: Optional[ControlSession] = None,
                 hfov_deg: float = 70.0, max_exposure: int = 200, max_gain: int = 40, still: bool = False):
        self.cam, self.spec, self.out, self.controls = cam, spec, out, controls
        self.still = still
        if still:
            self.SPEED_MAX_4K = self.STILL["speed_4k"]
            self.MAX_NOISE_PX_4K = self.STILL["noise_4k"]
            self.AUTO_FINISH_COUNT = self.STILL["auto_finish"]
            self.GOOD_COUNT = self.STILL["auto_finish"]
            self.COOLDOWN_S = self.STILL["cooldown_s"]
        w, h = cam.mode.width, cam.mode.height
        self.size = (w, h)
        self.K = guess_K(w, h, hfov_deg)
        self.det = BoardDetector(spec)
        self.speed_max = self.SPEED_MAX_4K * w / 3840.0
        self.caps: list[dict] = []
        self.cover = np.zeros((9, 16), np.int32)
        self.corner_pts = np.zeros(4, int)        # TL, TR, BL, BR
        self.live = None                  # dict from the detection thread
        self.motion_hist: list[float] = []
        self.last_cap_t = 0.0
        self.flash_t = 0.0
        self.msg, self.msg_col, self.msg_t = "", WHITE, 0.0
        self.running = True
        self.diag_dir = out / "diagnostics"
        self.diag_dir.mkdir(parents=True, exist_ok=True)
        self._diag_t = 0.0
        self._diag = []
        key = None
        if controls is not None:
            cur = controls.current()
            key = next((k for k in ("exposure_time_absolute", "exposure_absolute") if k in cur), None)
        self.exposure = ExposureController(controls, max_exposure=max_exposure, max_gain=max_gain, exposure_key=key)
        self.out.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()

    def _corner_counts(self, pts: np.ndarray) -> np.ndarray:
        w, h = self.size
        cw, ch = self.CORNER_FRAC * w, self.CORNER_FRAC * h
        x, y = pts[:, 0], pts[:, 1]
        left, right, top, bot = x < cw, x >= w - cw, y < ch, y >= h - ch
        return np.array([(left & top).sum(), (right & top).sum(), (left & bot).sum(), (right & bot).sum()])

    # ------------------------------------------------------------------ detection + auto capture
    def _loop(self):
        while self.running:                      # a single bad frame must never stop auto-capture
            try:
                self._loop_body()
            except Exception:
                log.exception("capture loop error - continuing")
                time.sleep(0.2)

    def _loop_body(self):
        last_seq, prev, prev_t = -1, None, None
        while self.running:
            seq, frame, t_frame = self.cam.latest()
            if seq == last_seq or frame is None:
                time.sleep(0.005)
                continue
            last_seq = seq
            now = time.monotonic()
            d = self.det.detect_fast(frame, 1920)
            motion = None                     # image speed in px/s (what blur and rolling-shutter skew depend on)
            if prev is not None and d.n >= 6 and prev.n >= 6 and t_frame - prev_t > 1e-3:
                c, ia, ib = np.intersect1d(d.ids, prev.ids, return_indices=True)
                if len(c) >= 6:
                    motion = float(np.median(np.linalg.norm(d.corners[ia] - prev.corners[ib], axis=1))) / (t_frame - prev_t)
            prev, prev_t = d, t_frame
            self.motion_hist = (self.motion_hist + [motion])[-3:]
            desc = info = None
            if d.n >= 8:
                r = descriptor_from_points(d.ids, d.corners, self.spec, self.K, None, self.size)
                if r:
                    desc, info = r
            novel = desc is not None and all(np.linalg.norm(desc - c["desc"]) >= self.NOVELTY for c in self.caps)
            if desc is not None and not novel and d.n >= self.MIN_CORNERS:
                live_cc = self._corner_counts(d.corners)
                novel = bool(np.any((live_cc >= 4) & (self.corner_pts < self.CORNER_NEED)))
            need = 3 if self.still else 2
            steady = len(self.motion_hist) >= need and all(m is not None and m < self.speed_max
                                                           for m in self.motion_hist[-need:])
            self.live = {"det": d, "motion": motion, "steady": steady, "novel": novel, "desc": desc, "info": info}
            if now - self._diag_t > 2.0:
                self._diag_t = now
                n_mk = 0 if d.marker_ids is None else len(d.marker_ids)
                g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                rec = {"t": dt.datetime.now().isoformat(timespec="seconds"), "markers": n_mk, "corners": int(d.n),
                       "speed_px_s": motion, "steady": steady, "novel": novel, "brightness": round(float(g.mean()), 1),
                       "exposure": self.exposure.status, "n_captured": len(self.caps)}
                self._diag.append(rec)
                k = len(self._diag) - 1
                cv2.imwrite(str(self.diag_dir / f"diag_{k:04d}.jpg"), cv2.resize(frame, (1280, 720)),
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
                if k % 15 == 14:                                   # keep a full-res frame now and then
                    cv2.imwrite(str(self.diag_dir / f"diag_{k:04d}_full.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                (self.diag_dir / "diag.json").write_text(json.dumps(self._diag, indent=0, default=float))
            changed_before = self.exposure.last_change
            try:
                self.exposure.update(frame, d.corners if d.n >= 6 else None, now)
            except OSError:
                self.exposure.enabled = False
            exposure_settled = now - self.exposure.last_change > 0.5 and self.exposure.last_change == changed_before
            if (d.n >= self.MIN_CORNERS and steady and novel and exposure_settled
                    and now - self.last_cap_t > self.COOLDOWN_S):
                if self.still:
                    self.capture_still("auto")
                else:
                    self.capture(frame, "auto")

    def capture_still(self, why: str) -> bool:
        """Average N consecutive frames of a motionless camera (noise / compression artefacts down ~sqrt(N))."""
        self.last_cap_t = time.monotonic()
        self.say("capturing - keep still ...", YELLOW)
        n = self.STILL["avg_frames"]
        try:
            frames = self.cam.wait_frames(n, timeout=max(5.0, 3.0 * n / max(self.cam.fps, 1.0)))
        except TypeError:
            frames = self.cam.wait_frames(n)
        except (TimeoutError, RuntimeError) as e:     # dropped frames etc.: skip this shot, never stop capturing
            log.warning("still capture skipped: %s", e)
            self.say("camera hiccup - shot skipped, it will retry", YELLOW)
            return False
        if len(frames) < 2:
            return False
        a, b = self.det.detect_fast(frames[0], 1920), self.det.detect_fast(frames[-1], 1920)
        c, ia, ib = np.intersect1d(a.ids, b.ids, return_indices=True)
        motion = float(np.median(np.linalg.norm(a.corners[ia] - b.corners[ib], axis=1))) if len(c) >= 6 else 99.0
        if motion > self.STILL["avg_motion_px"] * self.size[0] / 3840.0:
            self.say(f"moved during the shot ({motion:.2f} px) - let go of the camera and wait", YELLOW)
            return False
        mean = np.mean([f.astype(np.float32) for f in frames], axis=0)
        gray = cv2.cvtColor(mean, cv2.COLOR_BGR2GRAY) if mean.ndim == 3 else mean
        gray16 = np.clip(gray * 257.0 + 0.5, 0, 65535).astype(np.uint16)
        return self.capture(frames[-1], why, mean_img=gray16, motion=motion)

    def capture(self, frame: np.ndarray, why: str, mean_img: Optional[np.ndarray] = None, motion: float = 0.0) -> bool:
        with self._lock:
            self.last_cap_t = time.monotonic()
            d = self.det.detect(mean_img if mean_img is not None else frame)   # full-resolution, sub-pixel refined
            if d.n < self.MIN_CORNERS:
                self.say(f"not captured: only {d.n} corners visible", RED)
                return False
            r = descriptor_from_points(d.ids, d.corners, self.spec, self.K, None, self.size)
            if r is None:
                self.say("not captured: board pose unclear", RED)
                return False
            desc, info = r
            pred, ok = predict_from_neighbours(d.ids, d.corners, self.spec, radius=1)
            noise = float(np.median(np.linalg.norm(d.corners - pred, axis=1)[ok])) if ok.sum() >= 5 else 0.0
            limit = self.MAX_NOISE_PX_4K * self.size[0] / 3840.0
            if noise > limit:
                self.rejected_blur = getattr(self, "rejected_blur", 0) + 1
                self.say(f"blurred ({noise:.2f} px) - not saved, move slower", YELLOW)
                return False
            idx = (self.caps[-1]["index"] + 1) if self.caps else 0
            name = f"img_{idx:03d}"
            cv2.imwrite(str(self.out / f"{name}_mean.png"), mean_img if mean_img is not None else to_gray8(frame))
            cv2.imwrite(str(self.out / f"{name}_color.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            w, h = self.size
            gx = np.clip((d.corners[:, 0] / w * 16).astype(int), 0, 15)
            gy = np.clip((d.corners[:, 1] / h * 9).astype(int), 0, 8)
            np.add.at(self.cover, (gy, gx), 1)
            cc = self._corner_counts(d.corners)
            self.corner_pts += cc
            self.caps.append({"index": idx, "name": name, "desc": desc, "gx": gx, "gy": gy, "n": int(d.n),
                              "tilt_x": float(info["tilt_x_deg"]), "tilt_y": float(info["tilt_y_deg"]),
                              "square_px": float(np.median(local_square_px(d, self.spec))), "why": why,
                              "noise_px": noise, "corner_counts": cc.tolist(), "averaged_frames":
                              (self.STILL["avg_frames"] if mean_img is not None else 1), "motion_px": motion,
                              "time": dt.datetime.now().isoformat(timespec="seconds")})
            self.flash_t = time.monotonic()
            self._write_index()
        self.say(f"captured #{len(self.caps)}  ({d.n} corners)", GREEN)
        log.info("captured %s (%s): %d corners, tilt (%+.0f, %+.0f)", name, why, d.n, info["tilt_x_deg"], info["tilt_y_deg"])
        return True

    def undo(self):
        with self._lock:
            if not self.caps:
                return
            c = self.caps.pop()
            np.add.at(self.cover, (c["gy"], c["gx"]), -1)
            self.corner_pts -= np.array(c.get("corner_counts", [0, 0, 0, 0]))
            for suf in ("_mean.png", "_color.jpg"):
                (self.out / f"{c['name']}{suf}").unlink(missing_ok=True)
            self._write_index()
        self.say(f"removed {c['name']}", YELLOW)

    def _write_index(self):
        (self.out / "captures.json").write_text(json.dumps(
            [{k: v for k, v in c.items() if k not in ("desc", "gx", "gy")} for c in self.caps], indent=1))

    def say(self, text, col=WHITE):
        self.msg, self.msg_col, self.msg_t = text, col, time.monotonic()

    # ------------------------------------------------------------------ guidance (plain words)
    def advice(self) -> tuple[str, tuple]:
        L = self.live
        if L is None:
            return "starting camera ...", GREY
        d = L["det"]
        if d.n == 0:
            n_mk = 0 if d.marker_ids is None else len(d.marker_ids)
            return ("point the camera at the board (40-60 cm away)" if n_mk == 0 else
                    "board blurred - move slower / not so close"), RED
        if d.n < self.MIN_CORNERS:
            return f"only {d.n} corners - show more of the board", YELLOW
        if not L["steady"] and self.still:
            return "set the camera down and LET GO - it shoots when the image is completely still", YELLOW
        if not L["steady"]:
            m = L["motion"]
            return (f"pause a moment - camera moving {m:.0f} px/s (need < {self.speed_max:.0f})" if m is not None
                    else "hold steady"), YELLOW
        if not L["novel"]:
            return "already have this view - move the camera to a new spot or angle", CYAN
        return "capturing ...", GREEN

    def complete(self) -> bool:
        return len(self.caps) >= self.AUTO_FINISH_COUNT and bool(np.all(self.corner_pts >= self.CORNER_NEED))

    def todo(self) -> str:
        n = len(self.caps)
        if n < 8:
            return ("rest the camera at a new spot/angle, let go, wait for the flash - fill the 4 RED corner boxes"
                    if self.still else "move the camera slowly around the board, pause ~1 s at new spots/angles - fill the 4 RED corner boxes")
        names = ["TOP-LEFT", "TOP-RIGHT", "BOTTOM-LEFT", "BOTTOM-RIGHT"]
        need = [nm for nm, k in zip(names, self.corner_pts) if k < self.CORNER_NEED]
        tl = sum(c["tilt_y"] < -15 for c in self.caps); tr = sum(c["tilt_y"] > 15 for c in self.caps)
        tu = sum(c["tilt_x"] < -15 for c in self.caps); td = sum(c["tilt_x"] > 15 for c in self.caps)
        tilts = [name for name, k in (("left", tl), ("right", tr), ("up", tu), ("down", td)) if k < 3]
        parts = []
        if need:
            parts.append("aim so the board fills the RED corner box(es): " + ", ".join(need))
        if tilts:
            parts.append("tilt the camera ~30 deg " + "/".join(tilts))
        if not parts and n >= self.GOOD_COUNT:
            return f"almost done - a few more views, it finishes by itself at {self.AUTO_FINISH_COUNT}"
        return "; ".join(parts) if parts else "good - a few more from different distances, then ENTER"

    # ------------------------------------------------------------------ drawing
    def draw(self, frame) -> np.ndarray:
        h, w = frame.shape[:2]
        vw = 1600
        s = vw / float(w)
        vh = int(h * s)
        view = cv2.resize(frame, (vw, vh), interpolation=cv2.INTER_AREA)
        ov = view.copy()
        cw, ch = vw / 16.0, vh / 9.0
        for gy in range(9):
            for gx in range(16):
                col = (0, 170, 0) if self.cover[gy, gx] > 0 else (0, 0, 170)
                cv2.rectangle(ov, (int(gx * cw), int(gy * ch)), (int((gx + 1) * cw), int((gy + 1) * ch)), col, -1)
        alpha = 0.22 if self.caps else 0.0
        view = cv2.addWeighted(ov, alpha, view, 1 - alpha, 0)
        L = self.live
        if L is not None and L["det"].marker_corners:
            ms = 1920.0 / w if w > 1920 else 1.0
            for m in L["det"].marker_corners:
                cv2.polylines(view, [(np.asarray(m).reshape(-1, 2) / ms * s).astype(np.int32)], True, (0, 165, 255), 2,
                              cv2.LINE_AA)
        if L is not None and L["det"].n:
            col = GREEN if L["steady"] else YELLOW
            for x, y in L["det"].corners:
                cv2.circle(view, (int(x * s), int(y * s)), 3, col, -1, cv2.LINE_AA)
        bw, bh = int(self.CORNER_FRAC * vw), int(self.CORNER_FRAC * vh)
        for k, (x0, y0) in enumerate(((0, 0), (vw - bw, 0), (0, vh - bh), (vw - bw, vh - bh))):
            ok = self.corner_pts[k] >= self.CORNER_NEED
            col = GREEN if ok else RED
            cv2.rectangle(view, (x0 + 2, y0 + 2), (x0 + bw - 3, y0 + bh - 3), col, 4)
            ty = (y0 + bh - 12) if y0 == 0 else (y0 + 30)
            cv2.putText(view, f"{min(self.corner_pts[k], 999)}/{self.CORNER_NEED}", (x0 + 12, ty), FONT, 0.8, col, 2,
                        cv2.LINE_AA)
        if time.monotonic() - self.flash_t < 0.25:
            cv2.rectangle(view, (0, 0), (vw - 1, vh - 1), WHITE, 14)
        # top bar
        n = len(self.caps)
        cv2.rectangle(view, (0, 0), (vw, 64), (0, 0, 0), -1)
        cv2.putText(view, f"CAPTURED {n}", (14, 46), FONT, 1.3, GREEN if n >= self.GOOD_COUNT else WHITE, 3, cv2.LINE_AA)
        cv2.putText(view, f"(aim {self.GOOD_COUNT}+)", (300, 46), FONT, 0.7, GREY, 1, cv2.LINE_AA)
        txt, col = self.advice()
        if L is not None:
            nm = 0 if L["det"].marker_ids is None else len(L["det"].marker_ids)
            cv2.putText(view, f"markers {nm}  corners {L['det'].n}", (vw - 330, int(0.15 * vh) + 32), FONT, 0.7, WHITE, 2, cv2.LINE_AA)
        cv2.putText(view, txt, (470, 44), FONT, 0.9, col, 2, cv2.LINE_AA)
        # bottom bar
        cv2.rectangle(view, (0, vh - 74), (vw, vh), (0, 0, 0), -1)
        cv2.putText(view, "next: " + self.todo(), (14, vh - 44), FONT, 0.75, CYAN, 2, cv2.LINE_AA)
        st = self.exposure.status if self.exposure.enabled else ""
        cv2.putText(view, f"finishes by itself   SPACE capture now   U undo   ENTER/ESC finish now -> calibrate      {st}",
                    (14, vh - 14), FONT, 0.55, GREY, 1, cv2.LINE_AA)
        if time.monotonic() - self.msg_t < 2.5 and self.msg:
            (tw, th), _ = cv2.getTextSize(self.msg, FONT, 1.2, 3)
            cv2.putText(view, self.msg, ((vw - tw) // 2, vh // 2), FONT, 1.2, self.msg_col, 3, cv2.LINE_AA)
        return view

    def run(self) -> str:
        """Returns 'done' (ENTER) or 'quit'."""
        cv2.namedWindow(WIN, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        fitted = shown = False
        self.done_t = None
        try:
            while True:
                seq, frame, _ = self.cam.latest()
                if frame is None:
                    continue
                canvas = self.draw(frame)
                cv2.imshow(WIN, canvas)
                if not fitted:
                    _fit_window(WIN, canvas.shape[1], canvas.shape[0])
                    fitted = True
                k = cv2.waitKey(15) & 0xFF
                vis = cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE)
                shown = shown or vis >= 1
                if k in (13, 10):
                    return "done"
                if k in (27, ord("q"), ord("Q")) or (shown and vis < 1):
                    return "done" if len(self.caps) >= self.MIN_TO_CALIBRATE else "quit"
                if self.complete():
                    if self.done_t is None:
                        self.done_t = time.monotonic()
                        self.say("COMPLETE - calibrating ...", GREEN)
                    elif time.monotonic() - self.done_t > 2.0:
                        return "done"
                if k == 32:
                    L = self.live
                    if L is None or L["det"].n < self.MIN_CORNERS:
                        self.say("board not visible enough to capture", RED)
                    else:
                        if self.still:
                            self.capture_still("manual")
                        else:
                            _, f, _ = self.cam.latest()
                            self.capture(f.copy(), "manual")
                elif k in (ord("u"), ord("U")):
                    self.undo()
        finally:
            self.running = False
            self._th.join(timeout=3.0)
            cv2.destroyWindow(WIN)
            for _ in range(5):
                cv2.waitKey(1)


def run_simple(device: str, mode: Mode, spec: BoardSpec, out: Path, lock: dict, hfov_deg: float = 70.0,
               max_exposure: int = 200, max_gain: int = 40, still: bool = False) -> tuple[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    spec.save(out / "board.json")
    (out / "session.json").write_text(json.dumps({"mode": mode.as_dict(), "tool": "still" if still else "simple",
                                                  "started": dt.datetime.now().isoformat(timespec="seconds")}, indent=1))
    with ControlSession(device, lock) as cs:
        cam = Camera(device, mode)
        try:
            time.sleep(0.3)
            cs.reapply()
            app = SimpleCapture(cam, spec, out, cs, hfov_deg, max_exposure, max_gain, still=still)
            result = app.run()
            n = len(app.caps)
        finally:
            cam.release()
    return result, n
