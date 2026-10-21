"""Stream Deck plugin: run commands, show live status, switch profiles.

The Stream Deck app launches run.sh with -port, -pluginUUID, -registerEvent
and -info. Keys and dials carry everything in their settings, written by
streamdeck/generate.py; there is no property inspector. Actions:

- run: run a command.
      {"argv": ["/usr/bin/open", "-a", "Ghostty", "/path/to/repo"],
       "cwd": "/optional/working/dir"}
  Nothing is interpreted: argv goes straight to Popen, no shell. The key
  shows the app's OK tick when the process started, an alert if it could not.
- status (key) / dial (encoder): live view of a source (sources.py, mac.py).
      {"source": "load", ...source settings..., "argv": [...optional, run on press]}
  The source redraws the key while it is on screen and handles presses,
  turns and taps; with argv, a press runs that instead of the source's
  press. Status keys act on release, so holding one for HOLD seconds goes to
  the source's hold instead.
- switch (key or dial press): show a page of one of our profiles.
      {"profile": "Customers", "page": 3}   or   {"back": true}
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

# run.sh starts us with -I (isolated), which drops this directory from sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import camera  # noqa: E402, F401 - registers its sources
import customers  # noqa: E402 - registers its sources
import mac  # noqa: E402, F401 - registers its sources
from deck import Ctx, Deck  # noqa: E402
from sdws import WebSocket  # noqa: E402

log = logging.getLogger("launch")
PLUGIN = "com.jonathanleek.launch"
RUN = f"{PLUGIN}.run"
STATUS = f"{PLUGIN}.status"
DIAL = f"{PLUGIN}.dial"
SWITCH = f"{PLUGIN}.switch"
HOLD = 1.0  # seconds a status key must be held to count as a hold
COMMAND_LOG = Path.home() / "Library/Logs" / f"{PLUGIN}.commands.log"


def start(settings: dict) -> None:
    argv = settings.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ValueError(f"bad argv in key settings: {argv!r}")
    cwd = settings.get("cwd") or None
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (settings.get("env") or {}).items()})
    log.info("run %s", argv)
    # The command's output must not go to our own stdout: that is a pipe to the
    # Stream Deck app, and a command that outlives the app (Rescan restarts it)
    # would die of a broken pipe on its next print. Log it instead.
    out = open(COMMAND_LOG, "ab")
    subprocess.Popen(
        argv, cwd=cwd, env=env, start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
    )
    out.close()


def switch(deck: Deck, device: str, settings: dict) -> None:
    if settings.get("back"):
        deck.switch_profile(device)
    elif settings.get("profile"):
        deck.switch_profile(device, settings["profile"], settings.get("page"))
    else:
        raise ValueError(f"switch key without profile or back: {settings!r}")


def press(deck: Deck, msg: dict, held: bool = False) -> None:
    """A press on any of our keys (status keys: on release) or dials."""
    action = msg.get("action")
    settings = msg.get("payload", {}).get("settings") or {}
    if held and (ctx := live(deck, msg)) and ctx.source.holds:
        ctx.source.hold(ctx)
        deck.send("showOk", ctx.context)
        deck.refresh(ctx)
    elif "argv" in settings and action in (RUN, STATUS, DIAL):
        start(settings)
        deck.send("showOk", msg.get("context"))
    elif action == SWITCH:
        switch(deck, msg.get("device", ""), settings)
    elif ctx := live(deck, msg):
        ctx.source.press(ctx)
        deck.refresh(ctx)


def live(deck: Deck, msg: dict) -> Ctx | None:
    """The on-screen key for msg, if it shows a source."""
    ctx = deck.get(msg.get("context", ""))
    return ctx if ctx is not None and ctx.source is not None else None


def handle(deck: Deck, msg: dict) -> None:
    event = msg.get("event")
    payload = msg.get("payload", {})
    if event == "willAppear":
        ctx = deck.appear(msg)
        if ctx.action == SWITCH and ctx.settings.get("customer"):
            customers.visit(ctx.settings["customer"])  # a customer page opened
        if ctx.source is not None:
            ctx.source.appear(ctx)
            deck.refresh(ctx)
    elif event == "willDisappear":
        deck.disappear(msg)
    elif event == "didReceiveSettings":
        if ctx := deck.get(msg.get("context", "")):
            ctx.settings = payload.get("settings") or {}
            deck.refresh(ctx)
    elif event == "keyDown" and msg.get("action") == STATUS:
        if ctx := deck.get(msg.get("context", "")):
            ctx.state["_down"] = time.monotonic()
    elif event == "keyUp" and msg.get("action") == STATUS:
        ctx = deck.get(msg.get("context", ""))
        down = ctx.state.pop("_down", None) if ctx else None
        press(deck, msg, held=down is not None and time.monotonic() - down >= HOLD)
    elif event in ("keyDown", "dialDown"):
        press(deck, msg)
    elif event == "dialRotate":
        if ctx := live(deck, msg):
            ctx.source.rotate(ctx, int(payload.get("ticks", 0)))
            deck.refresh(ctx)
    elif event == "touchTap":
        if ctx := live(deck, msg):
            ctx.source.tap(ctx, bool(payload.get("hold")))
            deck.refresh(ctx)


def serve(deck: Deck) -> None:
    while True:
        msg = json.loads(deck.ws.recv())
        try:
            handle(deck, msg)
        except ConnectionError:
            raise
        except Exception:
            log.exception("%s on %s", msg.get("event"), msg.get("context"))
            if msg.get("context"):
                deck.send("showAlert", msg["context"])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-port", type=int, required=True)
    parser.add_argument("-pluginUUID", required=True)
    parser.add_argument("-registerEvent", required=True)
    parser.add_argument("-info", default="{}")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(Path.home() / "Library/Logs" / f"{PLUGIN}.log")],
    )
    ws = WebSocket("127.0.0.1", args.port)
    ws.send(json.dumps({"event": args.registerEvent, "uuid": args.pluginUUID}))
    log.info("registered on port %s", args.port)
    deck = Deck(ws, args.pluginUUID)
    stop = threading.Event()
    threading.Thread(target=deck.run_refresher, args=(stop,), daemon=True).start()
    try:
        serve(deck)
    except ConnectionError as exc:
        log.info("%s; exiting", exc)
    finally:
        stop.set()


if __name__ == "__main__":
    main()
