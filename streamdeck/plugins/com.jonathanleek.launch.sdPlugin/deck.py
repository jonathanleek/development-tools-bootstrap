"""Plugin runtime: the connection to the app, which of our keys are on
screen, and the loop that keeps live keys and dials current.

Two threads send: the main thread (answering presses) and the refresher;
sdws.WebSocket serialises their frames. Only keys on screen are refreshed;
the app tells us with willAppear / willDisappear.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field

import render
from sources import SOURCES, Source, View

log = logging.getLogger("launch.deck")

TICK = 0.5  # how often the refresher looks for due keys, seconds


@dataclass
class Ctx:
    """One of our keys or dials as the app reported it."""

    context: str
    action: str
    device: str
    controller: str  # "Keypad" or "Encoder"
    settings: dict
    state: dict = field(default_factory=dict)
    shown: View | None = None
    due: float = 0.0

    @property
    def source(self) -> Source | None:
        return SOURCES.get(self.settings.get("source", ""))


class Deck:
    def __init__(self, ws, plugin_uuid: str) -> None:
        self.ws = ws
        self.uuid = plugin_uuid
        self._lock = threading.Lock()  # guards visible
        self.visible: dict[str, Ctx] = {}
        # per-key memory that outlives a page change (context ids are stable
        # for a key while the app runs)
        self._state: dict[str, dict] = {}

    # ---- outgoing ----

    def send(self, event: str, context: str | None = None, payload: dict | None = None, **extra) -> None:
        msg: dict = {"event": event, **extra}
        if context is not None:
            msg["context"] = context
        if payload is not None:
            msg["payload"] = payload
        self.ws.send(json.dumps(msg))

    def switch_profile(self, device: str, profile: str | None = None, page: int | None = None) -> None:
        """Show a page of a profile tagged as ours (InstalledByPluginUUID +
        PreconfiguredName in its manifest); no profile goes back to the
        previous one."""
        payload: dict = {}
        if profile is not None:
            payload["profile"] = profile
            if page is not None:
                payload["page"] = int(page)
        log.info("switchToProfile %s", payload or "(back)")
        self.send("switchToProfile", self.uuid, payload, device=device)

    # ---- what's on screen ----

    def appear(self, msg: dict) -> Ctx:
        p = msg.get("payload", {})
        ctx = Ctx(
            context=msg["context"],
            action=msg.get("action", ""),
            device=msg.get("device", ""),
            controller=p.get("controller", "Keypad"),
            settings=p.get("settings") or {},
            state=self._state.setdefault(msg["context"], {}),
        )
        with self._lock:
            self.visible[ctx.context] = ctx
        return ctx

    def disappear(self, msg: dict) -> None:
        with self._lock:
            self.visible.pop(msg.get("context", ""), None)

    def get(self, context: str) -> Ctx | None:
        with self._lock:
            return self.visible.get(context)

    # ---- refreshing ----

    def refresh(self, ctx: Ctx, now: float | None = None) -> None:
        """Ask the key's source what to show and send whatever changed."""
        src = ctx.source
        if src is None:
            return
        now = time.monotonic() if now is None else now
        try:
            view = src.view(ctx)
        except Exception:
            log.exception("source %s", ctx.settings.get("source"))
            view = View(image=render.tile(["error"], render.C_ERR, footer=ctx.settings.get("source")))
        old = ctx.shown or View()
        if view.title != old.title and view.title is not None:
            self.send("setTitle", ctx.context, {"title": view.title, "target": 0})
        if view.image != old.image and view.image is not None:
            self.send("setImage", ctx.context, {"image": render.data_url(view.image), "target": 0})
        new_layout = view.layout != old.layout and view.layout is not None
        if new_layout:
            self.send("setFeedbackLayout", ctx.context, {"layout": view.layout})
        if (new_layout or view.feedback != old.feedback) and view.feedback is not None:
            self.send("setFeedback", ctx.context, view.feedback)
        ctx.shown = view
        ctx.due = now + src.interval

    def refresh_due(self, now: float) -> None:
        with self._lock:
            due = [c for c in self.visible.values() if c.source is not None and c.due <= now]
        for ctx in due:
            self.refresh(ctx, now)

    def run_refresher(self, stop: threading.Event) -> None:
        while not stop.wait(TICK):
            try:
                self.refresh_due(time.monotonic())
            except ConnectionError:
                return
            except Exception:
                log.exception("refresher")
