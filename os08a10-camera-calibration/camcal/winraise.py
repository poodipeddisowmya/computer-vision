"""Bring an OpenCV window to the front on X11 (GNOME ignores OpenCV's own raise / TOPMOST on GTK2).

Uses libX11 through ctypes (no extra packages): finds the window by its title and asks the
window manager, as a pager would, to activate it and keep it above other windows.
Silently does nothing on Wayland / without X11.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os

_CLIENT_MESSAGE = 33
_SUBSTRUCTURE_REDIRECT = 1 << 20
_SUBSTRUCTURE_NOTIFY = 1 << 19


class _XClientMessageEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                ("format", ctypes.c_int), ("data", ctypes.c_long * 5)]


class _XEvent(ctypes.Union):
    _fields_ = [("xclient", _XClientMessageEvent), ("pad", ctypes.c_long * 24)]


def _load():
    if not os.environ.get("DISPLAY"):
        return None
    path = ctypes.util.find_library("X11")
    if not path:
        return None
    x = ctypes.cdll.LoadLibrary(path)
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XDefaultRootWindow.restype = ctypes.c_ulong
    x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x.XInternAtom.restype = ctypes.c_ulong
    x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                             ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                             ctypes.POINTER(ctypes.c_uint)]
    x.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
    x.XFree.argtypes = [ctypes.c_void_p]
    x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.POINTER(_XEvent)]
    x.XFlush.argtypes = [ctypes.c_void_p]
    x.XCloseDisplay.argtypes = [ctypes.c_void_p]
    return x


def _find(x, dpy, win, title: bytes, depth=0):
    name = ctypes.c_char_p()
    if x.XFetchName(dpy, win, ctypes.byref(name)) and name.value:
        hit = name.value == title
        x.XFree(name)
        if hit:
            return win
    if depth > 4:
        return None
    root, parent = ctypes.c_ulong(), ctypes.c_ulong()
    kids, n = ctypes.POINTER(ctypes.c_ulong)(), ctypes.c_uint()
    if not x.XQueryTree(dpy, win, ctypes.byref(root), ctypes.byref(parent), ctypes.byref(kids), ctypes.byref(n)):
        return None
    try:
        for i in range(n.value):
            w = _find(x, dpy, kids[i], title, depth + 1)
            if w:
                return w
    finally:
        if kids:
            x.XFree(kids)
    return None


def _send(x, dpy, root, win, atom, data):
    ev = _XEvent()
    ev.xclient.type = _CLIENT_MESSAGE
    ev.xclient.send_event = 1
    ev.xclient.display = dpy
    ev.xclient.window = win
    ev.xclient.message_type = x.XInternAtom(dpy, atom, 0)
    ev.xclient.format = 32
    for i, v in enumerate(data):
        ev.xclient.data[i] = v
    x.XSendEvent(dpy, root, 0, _SUBSTRUCTURE_REDIRECT | _SUBSTRUCTURE_NOTIFY, ctypes.byref(ev))


def raise_window(title: str, above: bool = True) -> bool:
    """Activate the window titled `title` (and keep it above others). Returns True if found."""
    try:
        x = _load()
        if x is None:
            return False
        dpy = x.XOpenDisplay(None)
        if not dpy:
            return False
        try:
            root = x.XDefaultRootWindow(dpy)
            win = _find(x, dpy, root, title.encode())
            if not win:
                return False
            if above:   # _NET_WM_STATE: action 1 = add, property _NET_WM_STATE_ABOVE, source 2 = pager
                _send(x, dpy, root, win, b"_NET_WM_STATE", [1, x.XInternAtom(dpy, b"_NET_WM_STATE_ABOVE", 0), 0, 2, 0])
            _send(x, dpy, root, win, b"_NET_ACTIVE_WINDOW", [2, 0, 0, 0, 0])   # source 2 = pager: WMs honour it
            x.XFlush(dpy)
            return True
        finally:
            x.XCloseDisplay(dpy)
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    print(raise_window(sys.argv[1]))
