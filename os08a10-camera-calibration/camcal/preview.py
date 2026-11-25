"""Live camera view with board overlays - look before you calibrate.

Read-only: opens the camera in the requested mode and changes NO controls.
Shows what the camera sees with everything the calibration cares about drawn on
top, plus a 1:1 pixel magnifier under the mouse. Click START (or press ENTER)
to begin the calibration; Q / ESC / closing the window quits.

    python3 -m camcal preview            # then click START
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Optional

import cv2
import numpy as np

from .board import BoardDetector, BoardSpec, local_square_px, to_gray8
from .camera import Camera, Mode
from .capture import _fit_window, guess_K

WIN = "camcal - live camera view"
VIEW_W = 1440            # displayed image width (fits a 1920x1080 screen with the side panel)
PANEL_W = 420
GREEN, RED, AMBER, CYAN, WHITE, GREY, MAGENTA = (60, 220, 60), (60, 60, 235), (0, 190, 255), (230, 200, 40), \
    (240, 240, 240), (150, 150, 150), (230, 60, 230)
FONT = cv2.FONT_HERSHEY_SIMPLEX


class _Detector(threading.Thread):
    """Runs board detection on the newest frame in the background so the view stays smooth."""

    def __init__(self, cam: Camera, spec: BoardSpec, K: np.ndarray):
        super().__init__(daemon=True)
        self.cam, self.spec, self.K = cam, spec, K
        self.det = BoardDetector(spec)
        self.result: dict = {}
        self.running = True
        self.dt = 0.0

    def run(self):
        last = -1
        while self.running:
            seq, frame, _ = self.cam.latest()
            if seq == last or frame is None:
                time.sleep(0.005)
                continue
            last = seq
            t0 = time.monotonic()
            self.result = self._analyse(frame, seq)
            self.dt = time.monotonic() - t0

    def _analyse(self, frame, seq) -> dict:
        h, w = frame.shape[:2]
        s = min(1.0, 1280.0 / w)
        d = self.det.detect_fast(frame, max_width=1280)
        out = {"seq": seq, "n": d.n, "n_total": d.n_total, "corners": d.corners, "ids": d.ids,
               "markers": [] if d.marker_corners is None else [np.asarray(m).reshape(-1, 2) / s for m in d.marker_corners],
               "t": time.monotonic()}
        g8 = to_gray8(frame if s >= 1.0 else cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA))
        out["mean"] = float(g8.mean())
        if d.n >= 4:
            sq = local_square_px(d, self.spec, aligned=True)
            out["square_px"] = float(np.median(sq))
            hull = cv2.convexHull((d.corners * s).astype(np.float32)).astype(np.int32)
            m = np.zeros(g8.shape, np.uint8)
            cv2.fillConvexPoly(m, hull, 255)
            vals = g8[m > 0]
            if vals.size:
                out["white"] = float(np.percentile(vals, 95))
                out["black"] = float(np.percentile(vals, 5))
                out["saturated"] = float((vals >= 250).mean())
            out["mm_per_px"] = 0.5 * (self.spec.pitch_x_mm + self.spec.pitch_y_mm) / max(out["square_px"], 1e-6)
            if d.n >= 6:
                obj = self.spec.object_points(d.ids).astype(np.float64)
                ok, rv, tv = cv2.solvePnP(obj, d.corners.astype(np.float64), self.K, None,
                                          flags=cv2.SOLVEPNP_IPPE if d.n >= 4 else cv2.SOLVEPNP_ITERATIVE)
                if ok:
                    R, _ = cv2.Rodrigues(rv)
                    centre = R @ np.array([self.spec.pitch_x_mm * (self.spec.inner_cols - 1) / 2,
                                           self.spec.pitch_y_mm * (self.spec.inner_rows - 1) / 2, 0]) + tv.ravel()
                    out["distance_mm"] = float(np.linalg.norm(centre))
                    n = R[:, 2]
                    out["tilt_deg"] = float(math.degrees(math.acos(min(1.0, abs(n[2])))))
                    out["tilt_lr"] = float(math.degrees(math.atan2(n[0], abs(n[2]))))
                    out["tilt_ud"] = float(math.degrees(math.atan2(n[1], abs(n[2]))))
        return out


class LivePreview:
    def __init__(self, cam: Camera, spec: BoardSpec, hfov_deg: float = 70.0, start_label: str = "START CALIBRATION",
                 warmup_s: float = 600.0, warm_since: Optional[float] = None):
        self.cam, self.spec = cam, spec
        self.warmup_s = warmup_s
        self.warm_since = warm_since if warm_since is not None else time.monotonic()
        w, h = cam.mode.width, cam.mode.height
        self.size = (w, h)
        self.scale = VIEW_W / float(w)
        self.view_h = int(round(h * self.scale))
        self.K = guess_K(w, h, hfov_deg)
        self.detector = _Detector(cam, spec, self.K)
        self.mouse: Optional[tuple[int, int]] = None
        self.clicked_start = False
        self.start_label = start_label
        self.btn = (VIEW_W + 20, self.view_h - 90, VIEW_W + PANEL_W - 20, self.view_h - 20)
        self.seen = np.zeros((9, 16), np.int32)             # where board corners have appeared so far
        self.show_seen = True
        self.show_grid = True
        self.history: deque = deque(maxlen=12)              # (t, ids, corners) for stillness
        self.hover_btn = False

    # ------------------------------------------------------------------ mouse
    def _on_mouse(self, ev, x, y, flags, _):
        self.mouse = (x, y)
        x0, y0, x1, y1 = self.btn
        self.hover_btn = x0 <= x <= x1 and y0 <= y <= y1
        if ev == cv2.EVENT_LBUTTONUP and self.hover_btn:
            self.clicked_start = True

    # ------------------------------------------------------------------ helpers
    def _stillness_px(self, r) -> Optional[float]:
        """Median corner motion (full-res px) over the last ~0.5 s; None if unknown."""
        if r.get("n", 0) < 4:
            self.history.clear()
            return None
        if not self.history or self.history[-1][0] != r["seq"]:
            self.history.append((r["seq"], r["t"], dict(zip(map(int, r["ids"]), r["corners"]))))
        recent = [hh for hh in self.history if r["t"] - hh[1] <= 0.6]
        if len(recent) < 2:
            return None
        a, b = recent[0][2], recent[-1][2]
        common = set(a) & set(b)
        if len(common) < 4:
            return None
        return float(np.median([np.linalg.norm(a[i] - b[i]) for i in common]))

    def _accumulate(self, r):
        if r.get("n", 0) < 4:
            return
        w, h = self.size
        gx = np.clip((r["corners"][:, 0] / w * 16).astype(int), 0, 15)
        gy = np.clip((r["corners"][:, 1] / h * 9).astype(int), 0, 8)
        self.seen[gy, gx] += 1

    # ------------------------------------------------------------------ drawing
    def _draw_view(self, frame, r) -> np.ndarray:
        s = self.scale
        w, h = self.size
        view = cv2.resize(frame, (VIEW_W, self.view_h), interpolation=cv2.INTER_AREA)
        if self.show_seen and self.seen.any():
            ov = view.copy()
            cw, ch = VIEW_W / 16.0, self.view_h / 9.0
            for gy in range(9):
                for gx in range(16):
                    if self.seen[gy, gx]:
                        cv2.rectangle(ov, (int(gx * cw), int(gy * ch)), (int((gx + 1) * cw), int((gy + 1) * ch)), GREEN, -1)
            view = cv2.addWeighted(ov, 0.18, view, 0.82, 0)
        if self.show_grid:
            for k in range(1, 3):
                cv2.line(view, (int(VIEW_W * k / 3), 0), (int(VIEW_W * k / 3), self.view_h), GREY, 1, cv2.LINE_AA)
                cv2.line(view, (0, int(self.view_h * k / 3)), (VIEW_W, int(self.view_h * k / 3)), GREY, 1, cv2.LINE_AA)
            cx, cy = VIEW_W // 2, self.view_h // 2
            cv2.drawMarker(view, (cx, cy), WHITE, cv2.MARKER_CROSS, 28, 1, cv2.LINE_AA)
            bw, bh = int(0.15 * VIEW_W), int(0.15 * self.view_h)
            for (x0, y0) in ((0, 0), (VIEW_W - bw, 0), (0, self.view_h - bh), (VIEW_W - bw, self.view_h - bh)):
                cv2.rectangle(view, (x0, y0), (x0 + bw - 1, y0 + bh - 1), CYAN, 1, cv2.LINE_AA)
            cv2.putText(view, "image corners: the board must reach these boxes", (bw + 8, 22), FONT, 0.5, CYAN, 1, cv2.LINE_AA)
        for m in r.get("markers", []):
            cv2.polylines(view, [(m * s).astype(np.int32)], True, AMBER, 1, cv2.LINE_AA)
        if r.get("n", 0):
            pts = r["corners"] * s
            if r["n"] >= 4:
                hull = cv2.convexHull(pts.astype(np.float32)).astype(np.int32)
                cv2.polylines(view, [hull], True, GREEN, 2, cv2.LINE_AA)
            for p in pts:
                cv2.circle(view, (int(round(p[0])), int(round(p[1]))), 3, GREEN, -1, cv2.LINE_AA)
        self._draw_loupe(view, frame)
        return view

    def _draw_loupe(self, view, frame):
        """1:1 (and 2x) crop of the full-resolution frame under the mouse."""
        if self.mouse is None or self.mouse[0] >= VIEW_W or self.mouse[1] >= self.view_h:
            return
        mx, my = self.mouse
        fx, fy = int(mx / self.scale), int(my / self.scale)
        half = 80
        h, w = frame.shape[:2]
        x0, y0 = max(0, min(w - 2 * half, fx - half)), max(0, min(h - 2 * half, fy - half))
        crop = frame[y0:y0 + 2 * half, x0:x0 + 2 * half]
        zoom = cv2.resize(crop, (4 * half, 4 * half), interpolation=cv2.INTER_NEAREST)
        cv2.rectangle(zoom, (0, 0), (zoom.shape[1] - 1, zoom.shape[0] - 1), WHITE, 2)
        cv2.putText(zoom, "2x of real pixels", (6, 18), FONT, 0.5, WHITE, 1, cv2.LINE_AA)
        zx = mx + 20 if mx + 20 + zoom.shape[1] < VIEW_W else mx - 20 - zoom.shape[1]
        zy = min(max(0, my - zoom.shape[0] // 2), self.view_h - zoom.shape[0])
        view[zy:zy + zoom.shape[0], zx:zx + zoom.shape[1]] = zoom
        cv2.rectangle(view, (int(x0 * self.scale), int(y0 * self.scale)),
                      (int((x0 + 2 * half) * self.scale), int((y0 + 2 * half) * self.scale)), WHITE, 1)

    def _panel(self, r, still, fps, det_dt) -> np.ndarray:
        p = np.full((self.view_h, PANEL_W, 3), 32, np.uint8)
        y = [28]

        def line(txt, col=WHITE, sc=0.55, th=1, gap=26):
            cv2.putText(p, txt, (16, y[0]), FONT, sc, col, th, cv2.LINE_AA)
            y[0] += gap

        def status(label, value, ok: Optional[bool], hint=""):
            col = GREY if ok is None else (GREEN if ok else AMBER)
            cv2.circle(p, (22, y[0] - 5), 6, col, -1, cv2.LINE_AA)
            cv2.putText(p, f"{label}: {value}", (36, y[0]), FONT, 0.52, WHITE, 1, cv2.LINE_AA)
            y[0] += 22
            if hint:
                cv2.putText(p, hint, (36, y[0]), FONT, 0.45, col, 1, cv2.LINE_AA)
                y[0] += 22
            y[0] += 4

        w, h = self.size
        line("LIVE CAMERA VIEW", CYAN, 0.7, 2, 30)
        line(f"{w}x{h} {self.cam.mode.fourcc}   {fps:4.1f} fps", GREY, 0.5)
        line("camera settings: untouched (view only)", GREY, 0.45, gap=26)
        left = self.warmup_s - (time.monotonic() - self.warm_since)
        if left > 0:
            m, sec = divmod(int(left), 60)
            line(f"camera warm-up: {m}:{sec:02d} left (counts here too)", AMBER, 0.5, gap=30)
        else:
            line("camera warm-up: done", GREEN, 0.5, gap=30)

        n, nt = r.get("n", 0), r.get("n_total", self.spec.n_corners)
        n_mk = len(r.get("markers", []))
        big = n_mk and float(np.median([cv2.arcLength(m.astype(np.float32).reshape(-1, 1, 2), True) / 4
                                         for m in r["markers"]])) > 180.0 * w / 3840.0
        status("Board corners", f"{n} / {nt}", n >= 20 if r else None,
               "" if n >= 20 else ("board not found - aim at it, 35-60 cm away" if n_mk == 0 else
                                   "TOO CLOSE / out of focus - move BACK" if big else
                                   "BLURRED: hold still + add light (or show more board)"))
        sq = r.get("square_px")
        if sq:
            status("Square size", f"{sq:.0f} px", sq >= 14, "" if sq >= 14 else "too far / too small - move closer")
            status("Resolution on board", f"{r['mm_per_px'] * 1000:.0f} um/px", None)
        dist = r.get("distance_mm")
        if dist:
            status("Distance (approx)", f"{dist / 10:.0f} cm", None)
            status("Tilt", f"{r['tilt_deg']:.0f} deg  (L/R {r['tilt_lr']:+.0f}, U/D {r['tilt_ud']:+.0f})", None)
        if "white" in r:
            wl, sat = r["white"], r["saturated"]
            ok = 150 <= wl <= 235 and sat < 0.005
            hint = "too dark - add light on the board" if wl < 150 else ("glare / overexposed" if not ok else "")
            status("Board white level", f"{wl:.0f} / 255  (target ~205)", ok, hint)
            status("Contrast", f"{r['white'] - r['black']:.0f}", r["white"] - r["black"] >= 60)
        else:
            status("Scene brightness", f"{r.get('mean', 0):.0f} / 255", None)
        if still is not None:
            status("Motion", f"{still:.1f} px", still < 1.0, "" if still < 1.0 else "moving")

        y[0] += 6
        line("What you see:", CYAN, 0.55)
        for t, c in (("green dots  = board corners found", GREEN), ("orange boxes = markers decoded", AMBER),
                     ("cyan boxes  = image corners", CYAN), ("green tint = where corners", GREEN),
                     ("               have been so far", GREEN), ("mouse       = 2x magnifier", WHITE)):
            line(t, c, 0.45, gap=20)
        y[0] += 8
        line("Keys: G grid  C tint  R reset tint", GREY, 0.45, gap=20)
        line("      ENTER = start   Q / ESC = quit", GREY, 0.45, gap=20)

        x0, y0, x1, y1 = self.btn
        col = (40, 170, 40) if not self.hover_btn else (60, 210, 60)
        cv2.rectangle(p, (x0 - VIEW_W, y0), (x1 - VIEW_W, y1), col, -1)
        cv2.rectangle(p, (x0 - VIEW_W, y0), (x1 - VIEW_W, y1), WHITE, 2)
        (tw, th), _ = cv2.getTextSize(self.start_label, FONT, 0.75, 2)
        cv2.putText(p, self.start_label, ((x0 + x1) // 2 - VIEW_W - tw // 2, (y0 + y1) // 2 + th // 2), FONT, 0.75,
                    WHITE, 2, cv2.LINE_AA)
        cv2.putText(p, "click when you understand the view", (x0 - VIEW_W, y0 - 12), FONT, 0.45, GREY, 1, cv2.LINE_AA)
        return p

    # ------------------------------------------------------------------ main loop
    def run(self, max_seconds: Optional[float] = None, snapshot: Optional[str] = None) -> bool:
        """Returns True if the user clicked START / pressed ENTER."""
        self.detector.start()
        headless = snapshot is not None
        if not headless:
            cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(WIN, self._on_mouse)
        t0 = time.monotonic()
        last_seq = -1
        shown = False
        fitted = False
        try:
            while True:
                seq, frame, _ = self.cam.latest()
                r = self.detector.result
                if r and r.get("seq") != last_seq:
                    last_seq = r["seq"]
                    self._accumulate(r)
                still = self._stillness_px(r) if r else None
                canvas = np.hstack([self._draw_view(frame, r), self._panel(r, still, self.cam.fps, self.detector.dt)])
                if headless:
                    if time.monotonic() - t0 > (max_seconds or 3):
                        cv2.imwrite(snapshot, canvas)
                        return False
                    time.sleep(0.03)
                    continue
                cv2.imshow(WIN, canvas)
                if not fitted:
                    _fit_window(WIN, canvas.shape[1], canvas.shape[0])
                    fitted = True
                k = cv2.waitKey(15) & 0xFF
                if k in (13, 10):
                    self.clicked_start = True
                elif k in (ord("q"), 27):
                    return False
                elif k == ord("g"):
                    self.show_grid = not self.show_grid
                elif k == ord("c"):
                    self.show_seen = not self.show_seen
                elif k == ord("r"):
                    self.seen[:] = 0
                if self.clicked_start:
                    return True
                vis = cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE)
                if vis >= 1:
                    shown = True
                elif shown:                          # GTK reports 0 until first mapped: only a close after that counts
                    return False
                if max_seconds and time.monotonic() - t0 > max_seconds:
                    return False
        finally:
            self.detector.running = False
            self.detector.join(timeout=3.0)      # never leave OpenCV work running into shutdown / the next stage
            if not headless:
                cv2.destroyWindow(WIN)
                for _ in range(5):
                    cv2.waitKey(1)


def run_preview(device: str, mode: Mode, spec: BoardSpec, hfov_deg: float = 70.0, warmup_s: float = 600.0,
                warm_since: Optional[float] = None, **kw) -> bool:
    cam = Camera(device, mode)
    try:
        return LivePreview(cam, spec, hfov_deg, warmup_s=warmup_s, warm_since=warm_since).run(**kw)
    finally:
        cam.release()
