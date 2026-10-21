"""Call notes in a client's vault folder, following the vault's convention:
`YYYY.MM.DD - <Title>.md` in the client's notes/ folder (or the client folder
itself when it keeps dated notes at the top, as some do).

    notes.py new <client folder>     ask for a title, create the note, open it
    notes.py today <client folder>   print today's newest call note, if any

Run by a deck key as its own process (the title dialog waits for input, which
must not hold up the plugin). Standard library only, like the plugin.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

DEFAULT_TITLE = "Sync"  # the vault's most common call-note title
SKELETON = "## Notes\n\n\n\n## Actions\n\n- [ ] \n"


def notes_dir(client: Path) -> Path:
    return client / "notes" if (client / "notes").is_dir() else client


def stamp(day: dt.date) -> str:
    return day.strftime("%Y.%m.%d")


def today_note(client: Path, day: dt.date | None = None) -> Path | None:
    """The newest note dated `day` (default today) in the client's folder."""
    prefix = stamp(day or dt.date.today())
    found = [p for p in notes_dir(client).glob(f"{prefix}*.md") if p.is_file()]
    return max(found, key=lambda p: p.stat().st_mtime, default=None)


def clean_title(title: str) -> str:
    """Strip what a file name can't hold; Obsidian also rejects # ^ [ ] |."""
    title = re.sub(r"[\\/:#^\[\]|]+", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def note_path(client: Path, title: str, day: dt.date | None = None) -> Path:
    return notes_dir(client) / f"{stamp(day or dt.date.today())} - {clean_title(title)}.md"


def create(client: Path, title: str, day: dt.date | None = None) -> Path:
    """The note for this title and day, created with the skeleton if new.
    An existing note is left as it is (pressing twice opens, never clobbers)."""
    path = note_path(client, title, day)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SKELETON)
    return path


def ask_title(client: Path) -> str | None:
    """A macOS dialog for the title; None if cancelled or left blank."""
    script = (
        "on run argv\n"
        "  activate\n"
        '  set r to display dialog ("New call note for " & item 1 of argv) '
        'default answer (item 2 of argv) with title "Call note" '
        'buttons {"Cancel", "Create"} default button "Create" cancel button "Cancel"\n'
        "  return text returned of r\n"
        "end run"
    )
    r = subprocess.run(["osascript", "-e", script, client.name, DEFAULT_TITLE], capture_output=True, text=True)
    title = clean_title(r.stdout) if r.returncode == 0 else ""
    return title or None


REVEAL = "file-explorer:reveal-active-file"  # "Reveal current file in navigation"


def vault_of(path: Path) -> Path | None:
    """The vault folder (the one holding .obsidian) above path."""
    return next((p for p in path.parents if (p / ".obsidian").is_dir()), None)


def open_in_obsidian(path: Path) -> None:
    """Open the note, then reveal it in the file explorer. Two steps: the
    plain path link copes with a note Obsidian hasn't indexed yet; the
    reveal is a command, which only the Advanced URI plugin can run from a
    link, on whatever note is then active."""
    subprocess.run(["/usr/bin/open", f"obsidian://open?path={quote(str(path))}"], check=False)
    vault = vault_of(path)
    if vault is None:
        return
    time.sleep(1.0)  # let the note become the active file first
    subprocess.run(["/usr/bin/open", f"obsidian://adv-uri?vault={quote(vault.name)}&commandid={quote(REVEAL, safe='')}"],
                   check=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["new", "today"])
    ap.add_argument("client", type=Path, help="the client's folder in the vault")
    args = ap.parse_args(argv)
    if not args.client.is_dir():
        print(f"no such client folder: {args.client}", file=sys.stderr)
        return 1
    if args.command == "today":
        note = today_note(args.client)
        if note is None:
            return 1
        print(note)
        return 0
    title = ask_title(args.client)
    if title is None:
        return 0
    path = create(args.client, title)
    print(path)
    open_in_obsidian(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
