"""Minimal, dependency-free V4L2 access via ioctl (no v4l2-ctl needed).

Provides:
  * device identity (driver, card, bus_info, USB serial / VID:PID via sysfs)
  * enumeration of pixel formats, frame sizes and frame intervals
  * enumeration / get / set of all user controls
  * snapshot + exact restore of every writable control

Struct layouts follow <linux/videodev2.h> (64-bit ARM/x86 identical here).
"""
from __future__ import annotations

import ctypes
import fcntl
import os
import struct
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

_IOC_WRITE, _IOC_READ = 1, 2


def _IOC(d, t, nr, size):
    return (d << 30) | (size << 16) | (ord(t) << 8) | nr


def _IOR(t, nr, size):
    return _IOC(_IOC_READ, t, nr, size)


def _IOWR(t, nr, size):
    return _IOC(_IOC_READ | _IOC_WRITE, t, nr, size)


class v4l2_capability(ctypes.Structure):
    _fields_ = [("driver", ctypes.c_char * 16), ("card", ctypes.c_char * 32),
                ("bus_info", ctypes.c_char * 32), ("version", ctypes.c_uint32),
                ("capabilities", ctypes.c_uint32), ("device_caps", ctypes.c_uint32),
                ("reserved", ctypes.c_uint32 * 3)]


class v4l2_queryctrl(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("type", ctypes.c_uint32), ("name", ctypes.c_char * 32),
                ("minimum", ctypes.c_int32), ("maximum", ctypes.c_int32), ("step", ctypes.c_int32),
                ("default_value", ctypes.c_int32), ("flags", ctypes.c_uint32),
                ("reserved", ctypes.c_uint32 * 2)]


class v4l2_control(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("value", ctypes.c_int32)]


class _menu_union(ctypes.Union):
    _fields_ = [("name", ctypes.c_char * 32), ("value", ctypes.c_int64)]


class v4l2_querymenu(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("id", ctypes.c_uint32), ("index", ctypes.c_uint32), ("u", _menu_union),
                ("reserved", ctypes.c_uint32)]


class v4l2_fmtdesc(ctypes.Structure):
    _fields_ = [("index", ctypes.c_uint32), ("type", ctypes.c_uint32), ("flags", ctypes.c_uint32),
                ("description", ctypes.c_char * 32), ("pixelformat", ctypes.c_uint32),
                ("mbus_code", ctypes.c_uint32), ("reserved", ctypes.c_uint32 * 3)]


class v4l2_frmsizeenum(ctypes.Structure):
    _fields_ = [("index", ctypes.c_uint32), ("pixel_format", ctypes.c_uint32), ("type", ctypes.c_uint32),
                ("u", ctypes.c_uint32 * 6), ("reserved", ctypes.c_uint32 * 2)]


class v4l2_frmivalenum(ctypes.Structure):
    _fields_ = [("index", ctypes.c_uint32), ("pixel_format", ctypes.c_uint32), ("width", ctypes.c_uint32),
                ("height", ctypes.c_uint32), ("type", ctypes.c_uint32), ("u", ctypes.c_uint32 * 6),
                ("reserved", ctypes.c_uint32 * 2)]


VIDIOC_QUERYCAP = _IOR("V", 0, ctypes.sizeof(v4l2_capability))
VIDIOC_ENUM_FMT = _IOWR("V", 2, ctypes.sizeof(v4l2_fmtdesc))
VIDIOC_G_CTRL = _IOWR("V", 27, ctypes.sizeof(v4l2_control))
VIDIOC_S_CTRL = _IOWR("V", 28, ctypes.sizeof(v4l2_control))
VIDIOC_QUERYCTRL = _IOWR("V", 36, ctypes.sizeof(v4l2_queryctrl))
VIDIOC_QUERYMENU = _IOWR("V", 37, ctypes.sizeof(v4l2_querymenu))
VIDIOC_ENUM_FRAMESIZES = _IOWR("V", 74, ctypes.sizeof(v4l2_frmsizeenum))
VIDIOC_ENUM_FRAMEINTERVALS = _IOWR("V", 75, ctypes.sizeof(v4l2_frmivalenum))

V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
V4L2_CTRL_FLAG_NEXT_CTRL = 0x80000000
FLAG_DISABLED, FLAG_GRABBED, FLAG_READ_ONLY, FLAG_INACTIVE, FLAG_WRITE_ONLY = 0x1, 0x2, 0x4, 0x10, 0x40
TYPE_NAMES = {1: "int", 2: "bool", 3: "menu", 4: "button", 5: "int64", 6: "ctrl_class",
              7: "string", 8: "bitmask", 9: "intmenu"}

# Controls whose value changes image GEOMETRY (crop / scale / optics / orientation).
# These must be identical between calibration and production; the runtime refuses
# to proceed if they differ.
GEOMETRY_CONTROL_KEYWORDS = ("zoom", "pan", "tilt", "focus", "flip", "mirror", "rotate",
                             "roi", "crop", "dewarp", "lens", "stabiliz")
# Controls that change only photometry (brightness/colour). They do not change
# intrinsics, but the production project should keep them locked for repeatable
# feature detection.
AUTO_CONTROL_KEYWORDS = ("auto", "continuous")


def fourcc_str(v: int) -> str:
    return struct.pack("<I", v).decode("ascii", "replace")


def _key(name: str) -> str:
    k = name.lower()
    for ch in " ,()/-.":
        k = k.replace(ch, "_")
    while "__" in k:
        k = k.replace("__", "_")
    return k.strip("_")


@dataclass
class Control:
    id: int
    key: str
    name: str
    type: str
    minimum: int
    maximum: int
    step: int
    default: int
    flags: int
    value: Optional[int] = None
    menu: dict = field(default_factory=dict)

    @property
    def writable(self) -> bool:
        return not (self.flags & (FLAG_DISABLED | FLAG_READ_ONLY)) and self.type not in ("button", "ctrl_class")

    @property
    def inactive(self) -> bool:
        return bool(self.flags & FLAG_INACTIVE)

    @property
    def is_geometry(self) -> bool:
        return any(w in self.key for w in GEOMETRY_CONTROL_KEYWORDS) and "exposure" not in self.key

    @property
    def is_auto(self) -> bool:
        return any(w in self.key for w in AUTO_CONTROL_KEYWORDS)


class V4L2Device:
    def __init__(self, path: str | int = "/dev/video0"):
        if isinstance(path, int):
            path = f"/dev/video{path}"
        self.path = str(path)
        self.fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # ------------------------------------------------------------ identity
    def info(self) -> dict:
        cap = v4l2_capability()
        fcntl.ioctl(self.fd, VIDIOC_QUERYCAP, cap)
        d = {"path": self.path, "driver": cap.driver.decode(), "card": cap.card.decode(),
             "bus_info": cap.bus_info.decode(),
             "driver_version": f"{cap.version >> 16}.{(cap.version >> 8) & 0xff}.{cap.version & 0xff}"}
        d.update(usb_identity(self.path))
        return d

    # ------------------------------------------------------------ formats
    def formats(self) -> list[dict]:
        out = []
        i = 0
        while True:
            fd = v4l2_fmtdesc(index=i, type=V4L2_BUF_TYPE_VIDEO_CAPTURE)
            try:
                fcntl.ioctl(self.fd, VIDIOC_ENUM_FMT, fd)
            except OSError:
                break
            fmt = {"fourcc": fourcc_str(fd.pixelformat), "description": fd.description.decode(),
                   "compressed": bool(fd.flags & 1), "sizes": []}
            j = 0
            while True:
                fs = v4l2_frmsizeenum(index=j, pixel_format=fd.pixelformat)
                try:
                    fcntl.ioctl(self.fd, VIDIOC_ENUM_FRAMESIZES, fs)
                except OSError:
                    break
                if fs.type == 1:  # discrete
                    w, h = fs.u[0], fs.u[1]
                    fmt["sizes"].append({"width": w, "height": h,
                                         "fps": self._intervals(fd.pixelformat, w, h)})
                else:
                    fmt["sizes"].append({"stepwise": list(fs.u)})
                    break
                j += 1
            out.append(fmt)
            i += 1
        return out

    def _intervals(self, pixfmt, w, h) -> list[float]:
        fps, k = [], 0
        while True:
            fi = v4l2_frmivalenum(index=k, pixel_format=pixfmt, width=w, height=h)
            try:
                fcntl.ioctl(self.fd, VIDIOC_ENUM_FRAMEINTERVALS, fi)
            except OSError:
                break
            if fi.type == 1 and fi.u[0]:
                fps.append(round(fi.u[1] / fi.u[0], 3))
            k += 1
        return fps

    # ------------------------------------------------------------ controls
    def controls(self, with_values: bool = True) -> dict[str, Control]:
        out: dict[str, Control] = {}
        qid = V4L2_CTRL_FLAG_NEXT_CTRL
        while True:
            q = v4l2_queryctrl(id=qid)
            try:
                fcntl.ioctl(self.fd, VIDIOC_QUERYCTRL, q)
            except OSError:
                break
            qid = q.id | V4L2_CTRL_FLAG_NEXT_CTRL
            t = TYPE_NAMES.get(q.type, str(q.type))
            if t == "ctrl_class" or q.flags & FLAG_DISABLED:
                continue
            c = Control(id=q.id, key=_key(q.name.decode(errors="replace")), name=q.name.decode(errors="replace"),
                        type=t, minimum=q.minimum, maximum=q.maximum, step=q.step,
                        default=q.default_value, flags=q.flags)
            if t in ("menu", "intmenu"):
                for idx in range(q.minimum, q.maximum + 1):
                    m = v4l2_querymenu(id=q.id, index=idx)
                    try:
                        fcntl.ioctl(self.fd, VIDIOC_QUERYMENU, m)
                        c.menu[idx] = (m.u.name.decode(errors="replace") if t == "menu" else int(m.u.value))
                    except OSError:
                        pass
            if with_values and t not in ("button", "string") and not (q.flags & FLAG_WRITE_ONLY):
                try:
                    c.value = self.get(q.id)
                except OSError:
                    c.value = None
            out[c.key] = c
        return out

    def get(self, cid: int) -> int:
        c = v4l2_control(id=cid)
        fcntl.ioctl(self.fd, VIDIOC_G_CTRL, c)
        return int(c.value)

    def set(self, cid: int, value: int) -> None:
        c = v4l2_control(id=cid, value=int(value))
        fcntl.ioctl(self.fd, VIDIOC_S_CTRL, c)

    # ------------------------------------------------------------ snapshot / apply
    def snapshot(self) -> dict[str, int]:
        """All readable control values keyed by normalised name."""
        return {k: c.value for k, c in self.controls().items() if c.value is not None}

    def apply(self, values: dict[str, int], strict: bool = False) -> dict[str, str]:
        """Apply controls so that dependent values land correctly in every case.

        Order is "manual values first, then auto-mode switches", done in two
        passes. This covers both directions:
          * auto -> manual (lock):   pass 1 switches the mode, pass 2 sets the now-active value;
          * manual -> auto (restore): pass 1 restores the manual value while still writable,
                                      then switches the auto mode back on.
        Returns {key: problem} for anything that could not be applied / verified.
        Values of controls that end up *inactive* (governed by an auto mode) are not verified.
        """
        ctrls = self.controls()
        ordered = sorted(values.items(), key=lambda kv: (1 if ctrls.get(kv[0]) and ctrls[kv[0]].is_auto else 0))
        problems: dict[str, str] = {}
        for _pass in range(2):
            problems = {}
            for k, v in ordered:
                c = self.controls(with_values=True).get(k) if _pass else ctrls.get(k)
                if c is None:
                    problems[k] = "control not present on this device"
                    continue
                if not c.writable or c.value == v:
                    continue
                if not (c.minimum <= v <= c.maximum) and c.type in ("int", "menu", "bool"):
                    problems[k] = f"value {v} outside [{c.minimum}, {c.maximum}]"
                    continue
                try:
                    self.set(c.id, v)
                except OSError as e:
                    problems[k] = f"set failed: {e.strerror}"
            ctrls = self.controls()
        final = self.controls()
        for k, v in values.items():
            c = final.get(k)
            if c is None or not c.writable or c.value is None:
                continue
            if c.value == v:
                problems.pop(k, None)
            elif not c.inactive:
                problems.setdefault(k, f"readback {c.value} != requested {v}")
            else:
                problems.pop(k, None)
        if strict and problems:
            raise RuntimeError(f"could not apply camera controls: {problems}")
        return problems

    def describe_controls(self) -> str:
        lines = []
        for c in self.controls().values():
            extra = f" menu={c.menu}" if c.menu else ""
            tag = " [GEOMETRY]" if c.is_geometry else ""
            fl = []
            if c.inactive:
                fl.append("inactive")
            if not c.writable:
                fl.append("ro")
            lines.append(f"  {c.key:40s} {c.type:6s} min={c.minimum} max={c.maximum} step={c.step} "
                         f"default={c.default} value={c.value}{' (' + ','.join(fl) + ')' if fl else ''}{tag}{extra}")
        return "\n".join(lines)


def usb_identity(dev_path: str) -> dict:
    """VID/PID/serial/manufacturer/product/port from sysfs (stable camera identity)."""
    name = Path(dev_path).name
    try:
        p = Path(f"/sys/class/video4linux/{name}/device").resolve()
    except OSError:
        return {}
    out = {}
    # walk up to the USB device node (has idVendor)
    for node in [p, *p.parents]:
        if (node / "idVendor").exists():
            for attr in ("idVendor", "idProduct", "serial", "manufacturer", "product", "speed", "busnum", "devpath"):
                f = node / attr
                if f.exists():
                    try:
                        out["usb_" + attr] = f.read_text().strip()
                    except OSError:
                        pass
            out["usb_port_path"] = node.name
            break
    return out


def list_devices() -> list[dict]:
    out = []
    for p in sorted(Path("/dev").glob("video*"), key=lambda x: int(x.name[5:]) if x.name[5:].isdigit() else 0):
        try:
            with V4L2Device(str(p)) as d:
                inf = d.info()
                inf["has_formats"] = bool(d.formats())
                out.append(inf)
        except OSError:
            continue
    return out


def find_device(card_substr: Optional[str] = None, serial: Optional[str] = None,
                port_path: Optional[str] = None) -> Optional[str]:
    """Locate a capture node by USB serial, port, or card name (first node with formats)."""
    for d in list_devices():
        if not d.get("has_formats"):
            continue
        if serial and d.get("usb_serial") != serial:
            continue
        if port_path and d.get("usb_port_path") != port_path:
            continue
        if card_substr and card_substr.lower() not in d.get("card", "").lower():
            continue
        return d["path"]
    return None


def control_dump(ctrls: dict[str, Control]) -> dict:
    return {k: {kk: vv for kk, vv in asdict(c).items() if kk != "id"} | {"id": hex(c.id),
                "geometry": c.is_geometry} for k, c in ctrls.items()}
