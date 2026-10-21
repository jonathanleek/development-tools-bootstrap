"""The camera dial: turn to pick a framing, press to switch the webcam to it.

Framings are Insta360 Link Controller global shortcuts; the dial's settings
(written by generate.py from config.json) list them as
{"modes": [{"name": "Meeting", "vk": 18, "mods": ["ctrl", "option", "cmd"]}, ...]}.
The keystroke is posted with CGEventPost, which macOS allows because the
Stream Deck app (our parent) has Device Control / Accessibility access.
"""

from __future__ import annotations

import ctypes
import ctypes.util

from sources import Source, View, source

FLAGS = {"shift": 0x20000, "ctrl": 0x40000, "option": 0x80000, "cmd": 0x100000}
_HID = 0  # kCGHIDEventTap

_cg = None


def post_key(vk: int, mods: list[str]) -> None:
    """Press and release virtual key `vk` with modifiers held."""
    global _cg
    if _cg is None:
        _cg = ctypes.CDLL(ctypes.util.find_library("ApplicationServices"))
        _cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
        _cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
        _cg.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        _cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        _cg.CFRelease.argtypes = [ctypes.c_void_p]
    flags = sum(FLAGS[m] for m in mods)
    for down in (True, False):
        ev = _cg.CGEventCreateKeyboardEvent(None, vk, down)
        _cg.CGEventSetFlags(ev, flags)
        _cg.CGEventPost(_HID, ev)
        _cg.CFRelease(ev)


@source("camera")
class CameraDial(Source):
    interval = 3600.0  # nothing changes on its own

    def modes(self, ctx) -> list[dict]:
        return ctx.settings.get("modes") or []

    def rotate(self, ctx, ticks):
        if self.modes(ctx):
            ctx.state["sel"] = (ctx.state.get("sel", 0) + ticks) % len(self.modes(ctx))

    def press(self, ctx):
        modes = self.modes(ctx)
        if not modes:
            return
        mode = modes[ctx.state.get("sel", 0) % len(modes)]
        post_key(int(mode["vk"]), list(mode.get("mods", [])))
        ctx.state["active"] = mode["name"]

    def view(self, ctx):
        modes = self.modes(ctx)
        if not modes:
            return View(layout="layouts/customer.json", feedback={"name": "Camera", "info": "no framings set"})
        name = modes[ctx.state.get("sel", 0) % len(modes)]["name"]
        info = "Camera · current" if ctx.state.get("active") == name else "Camera · press to switch"
        return View(layout="layouts/customer.json", feedback={"name": name, "info": info})
