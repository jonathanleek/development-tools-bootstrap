"""Whiteboard snap: photograph the whiteboard into today's call note.

    whiteboard.py <client folder> <images folder> --device "Insta360 Link"
        --board VK --meeting VK --mods ctrl,option,cmd [--settle 2.5]

Switches the webcam to its Whiteboard framing (Link Controller shortcut),
waits for it to settle, takes a still (Whiteboard Snap.app), switches back to
Meeting framing, then saves the photo as `Whiteboard - <Client> - <date
time>.png` in the images folder, copies it to the clipboard and embeds it at
the end of the Notes section of today's call note (creating
`YYYY.MM.DD - Sync.md` if there is none). Run by a deck key as its own
process; failures show as a macOS notification.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

# run with -I (isolated), which drops this directory from sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import notes  # noqa: E402
from camera import post_key  # noqa: E402

# Built by streamdeck/snap-app/build.sh. The still is taken by this app, not
# by us: macOS refuses the camera to a process the plugin starts, without
# asking, but asks once for an app started via LaunchServices.
SNAP_APP = Path.home() / ".local/share/streamdeck/Whiteboard Snap.app"


def capture(device: str, out: Path) -> None:
    if not SNAP_APP.exists():
        raise RuntimeError("Whiteboard Snap.app missing; run streamdeck/snap-app/build.sh")
    err = Path(str(out) + ".err")
    subprocess.run(["/usr/bin/open", "-W", "-n", str(SNAP_APP), "--args", device, str(out)], timeout=60, check=False)
    if err.exists():
        reason = err.read_text().strip()
        err.unlink()
        raise RuntimeError(reason)
    if not out.exists():
        raise RuntimeError("no photo was taken")


def embed(note: Path, image_name: str) -> None:
    """Add ![[image]] at the end of the note's Notes section (before its
    next heading), or at the end of the note if it has no such section."""
    lines = note.read_text().split("\n")
    at = len(lines)
    in_notes = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            if in_notes:
                at = i
                break
            in_notes = line.strip().lower() == "## notes"
    while at > 0 and lines[at - 1].strip() == "":  # after the section's last text, not its spacing
        at -= 1
    lines[at:at] = ["", f"![[{image_name}]]"]
    note.write_text("\n".join(lines))


def to_clipboard(image: Path) -> None:
    subprocess.run(["osascript", "-e", f'set the clipboard to (read (POSIX file "{image}") as «class PNGf»)'],
                   check=False, capture_output=True)


def notify(message: str) -> None:
    subprocess.run(["osascript", "-e", "on run argv\ndisplay notification (item 1 of argv) with title \"Whiteboard\"\nend run",
                    message], check=False, capture_output=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("client", type=Path)
    ap.add_argument("images", type=Path)
    ap.add_argument("--device", required=True)
    ap.add_argument("--board", type=int, required=True, help="virtual key code of the Whiteboard framing shortcut")
    ap.add_argument("--meeting", type=int, required=True, help="virtual key code of the Meeting framing shortcut")
    ap.add_argument("--mods", default="ctrl,option,cmd")
    ap.add_argument("--settle", type=float, default=2.5, help="seconds for the camera to reach the framing")
    args = ap.parse_args(argv)
    mods = [m for m in args.mods.split(",") if m]
    now = dt.datetime.now()
    name = notes.clean_title(f"Whiteboard - {args.client.name} - {now:%Y.%m.%d %H.%M.%S}") + ".png"
    image = args.images / name
    try:
        args.images.mkdir(parents=True, exist_ok=True)
        post_key(args.board, mods)
        time.sleep(args.settle)
        try:
            capture(args.device, image)
        finally:
            post_key(args.meeting, mods)  # back on camera even if the still failed
        note = notes.today_note(args.client) or notes.create(args.client, notes.DEFAULT_TITLE)
        embed(note, name)
        to_clipboard(image)
    except Exception as exc:  # noqa: BLE001 - surface anything to the user
        notify(f"Snap failed: {exc}")
        print(exc, file=sys.stderr)
        return 1
    notify(f"Saved to {note.stem}")
    print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
