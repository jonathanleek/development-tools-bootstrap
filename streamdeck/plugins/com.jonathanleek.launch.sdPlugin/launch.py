"""Stream Deck plugin: run a command with explicit arguments.

The Stream Deck app launches run.sh with -port, -pluginUUID, -registerEvent
and -info. Every key using this plugin carries its command in its settings,
written by streamdeck/generate.py:

    {"argv": ["/usr/bin/open", "-na", "Ghostty", "--args", "--working-directory=..."],
     "cwd": "/optional/working/dir"}

Nothing is interpreted: argv goes straight to Popen, no shell. The key shows
the app's OK tick when the process started, an alert if it could not.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# run.sh starts us with -I (isolated), which drops this directory from sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sdws import WebSocket  # noqa: E402

log = logging.getLogger("launch")
PLUGIN = "com.jonathanleek.launch"


def start(settings: dict) -> None:
    argv = settings.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ValueError(f"bad argv in key settings: {argv!r}")
    cwd = settings.get("cwd") or None
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (settings.get("env") or {}).items()})
    log.info("run %s", argv)
    subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True)


def serve(ws: WebSocket) -> None:
    while True:
        msg = json.loads(ws.recv())
        if msg.get("event") != "keyDown":
            continue
        context = msg.get("context")
        try:
            start(msg.get("payload", {}).get("settings", {}))
        except Exception:
            log.exception("key %s", context)
            ws.send(json.dumps({"event": "showAlert", "context": context}))
        else:
            ws.send(json.dumps({"event": "showOk", "context": context}))


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
    try:
        serve(ws)
    except ConnectionError as exc:
        log.info("%s; exiting", exc)


if __name__ == "__main__":
    main()
