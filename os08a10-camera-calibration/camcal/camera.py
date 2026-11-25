"""Camera access: exact-mode opening, low-latency threaded grabbing, and a
control session that snapshots every camera control, applies the calibration
lock, and *always* restores the original state on exit (normal exit, Ctrl-C,
SIGTERM, exceptions).
"""
from __future__ import annotations

import atexit
import logging
import signal
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from .v4l2 import V4L2Device, fourcc_str

log = logging.getLogger("camcal")


@dataclass
class Mode:
    width: int
    height: int
    fourcc: str = "MJPG"
    fps: float = 25.0

    @property
    def key(self) -> str:
        return f"{self.width}x{self.height}_{self.fourcc}"

    @classmethod
    def from_dict(cls, d: dict) -> "Mode":
        fcc = str(d.get("fourcc", "MJPG")).upper().replace("YUY2", "YUYV")
        return cls(int(d["width"]), int(d["height"]), fcc, float(d.get("fps", 25)))

    def as_dict(self) -> dict:
        return {"width": self.width, "height": self.height, "fourcc": self.fourcc, "fps": self.fps}


class ModeMismatch(RuntimeError):
    pass


class Camera:
    """Threaded V4L2 capture that always exposes the most recent frame.

    Frames are numbered; ``wait_frames(n)`` returns *n new* consecutive frames
    captured after the call, which is what still-capture / averaging needs.
    """

    def __init__(self, device: str, mode: Mode, buffers: int = 2):
        self.device = device
        self.mode = mode
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open {device}")
        fourcc = mode.fourcc if mode.fourcc != "YUY2" else "YUYV"
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, mode.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, mode.height)
        self.cap.set(cv2.CAP_PROP_FPS, mode.fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, buffers)
        deadline = time.monotonic() + max(12.0, 6.0 / max(mode.fps, 0.1))
        ok, frame = self.cap.read()
        while (not ok or frame is None) and time.monotonic() < deadline:
            ok, frame = self.cap.read()       # slow modes (YUYV 4K @1 fps) need several seconds to start
        if not ok or frame is None:
            self.cap.release()
            raise RuntimeError(f"{device}: no frames in mode {mode.key}")
        got_w, got_h = frame.shape[1], frame.shape[0]
        got_fcc = fourcc_str(int(self.cap.get(cv2.CAP_PROP_FOURCC)) & 0xFFFFFFFF)
        if (got_w, got_h) != (mode.width, mode.height) or got_fcc.upper().replace("YUY2", "YUYV") != fourcc:
            self.cap.release()
            raise ModeMismatch(f"requested {mode.key}, camera delivered {got_w}x{got_h}_{got_fcc}")
        self.actual_fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        self._lock = threading.Condition()
        self._frame: Optional[np.ndarray] = frame
        self._seq = 0
        self._t = time.monotonic()
        self._fps_est = 0.0
        self._running = True
        self.started = time.monotonic()
        self._th = threading.Thread(target=self._loop, name="grabber", daemon=True)
        self._th.start()

    def _loop(self):
        last = time.monotonic()
        while self._running:
            ok, f = self.cap.read()
            now = time.monotonic()
            if not ok or f is None:
                time.sleep(0.005)
                continue
            with self._lock:
                self._frame = f
                self._seq += 1
                self._t = now
                dt = now - last
                if dt > 0:
                    self._fps_est = 0.9 * self._fps_est + 0.1 * (1.0 / dt) if self._fps_est else 1.0 / dt
                last = now
                self._lock.notify_all()

    def latest(self) -> tuple[int, np.ndarray, float]:
        with self._lock:
            return self._seq, self._frame, self._t

    @property
    def fps(self) -> float:
        return self._fps_est

    def wait_frames(self, n: int, timeout: Optional[float] = None) -> list[np.ndarray]:
        """Return n new consecutive frames (each a copy)."""
        timeout = timeout if timeout is not None else max(5.0, 3.0 * n / max(self.mode.fps, 0.5))
        out = []
        deadline = time.monotonic() + timeout
        with self._lock:
            seq = self._seq
            while len(out) < n:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"only {len(out)}/{n} frames within {timeout:.1f}s")
                self._lock.wait(remaining)
                if self._seq != seq:
                    if self._seq != seq + 1 and out:
                        # a frame was dropped between our reads: restart sequence for strict consecutiveness
                        out.clear()
                    seq = self._seq
                    out.append(self._frame.copy())
        return out

    def release(self):
        self._running = False
        if self._th.is_alive():
            self._th.join(timeout=2.0)
        self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.release()


# =============================================================================
class ControlSession:
    """Snapshot -> lock -> (work) -> exact restore of all camera controls.

    The restore runs from ``__exit__``, ``atexit`` and SIGINT/SIGTERM/SIGHUP,
    so an aborted calibration never leaves the camera in a modified state for
    the other vision projects that share it.
    """

    def __init__(self, device: str, lock: Optional[dict] = None, restore: bool = True):
        self.device = device
        self.lock = dict(lock or {})
        self.restore_enabled = restore
        self.baseline: dict[str, int] = {}
        self.applied: dict[str, int] = {}
        self.problems: dict[str, str] = {}
        self._restored = False
        self._prev_handlers = {}

    def __enter__(self):
        with V4L2Device(self.device) as d:
            self.baseline = d.snapshot()
            self.baseline_full = d.controls()
            if self.lock:
                self.problems = d.apply(self.lock)
            self.applied = d.snapshot()
        atexit.register(self.restore)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            try:
                self._prev_handlers[sig] = signal.signal(sig, self._on_signal)
            except (ValueError, OSError):
                pass
        if self.problems:
            log.warning("control lock issues: %s", self.problems)
        return self

    def reapply(self) -> dict:
        """Re-apply the lock (UVC devices may reset some controls at stream-on)."""
        if not self.lock:
            return {}
        with V4L2Device(self.device) as d:
            self.problems = d.apply(self.lock)
            self.applied = d.snapshot()
        return self.problems

    def current(self) -> dict[str, int]:
        with V4L2Device(self.device) as d:
            return d.snapshot()

    def drift(self) -> dict[str, tuple]:
        """Controls whose value changed since the lock was applied (e.g. another process)."""
        now = self.current()
        return {k: (v, now.get(k)) for k, v in self.applied.items() if now.get(k) != v}

    def set(self, key: str, value: int) -> Optional[str]:
        with V4L2Device(self.device) as d:
            p = d.apply({key: value})
            self.applied = d.snapshot()
        if not p:
            self.lock[key] = value
        return p.get(key)

    def restore(self) -> dict:
        if self._restored or not self.restore_enabled:
            return getattr(self, "last_restore", {})
        self._restored = True
        try:
            with V4L2Device(self.device) as d:
                problems = d.apply(self.baseline)
                after = d.snapshot()
                ctrls = d.controls()
            diff = {k: (v, after.get(k)) for k, v in self.baseline.items()
                    if after.get(k) != v and k in ctrls and ctrls[k].writable and not ctrls[k].inactive}
            if diff or problems:
                log.warning("restore: not identical to baseline: %s %s", diff, problems)
            else:
                log.info("camera controls restored to pre-calibration state (%d controls)", len(self.baseline))
            self.last_restore = diff
            return diff
        except OSError as e:  # camera unplugged etc.
            log.error("restore failed: %s", e)
            return {"error": str(e)}

    def _on_signal(self, signum, frame):
        self.restore()
        prev = self._prev_handlers.get(signum)
        if callable(prev):
            prev(signum, frame)
        raise SystemExit(128 + signum)

    def __exit__(self, *exc):
        self.restore()
        for sig, h in self._prev_handlers.items():
            try:
                signal.signal(sig, h)
            except (ValueError, OSError, TypeError):
                pass
        return False
