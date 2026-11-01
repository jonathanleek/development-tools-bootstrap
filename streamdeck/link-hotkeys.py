"""Merge link-controller-hotkeys.ini into Insta360 Link Controller's startup.ini.

    /usr/bin/python3 streamdeck/link-hotkeys.py [--check] [startup.ini]

Sets each key of the repo file's sections and leaves everything else in
startup.ini (window sizes, login tokens) as it is. The app rewrites the file
when it quits, so run this while it isn't running. --check changes nothing
and exits 1 if the file needs updating. Standard library only.
"""

from __future__ import annotations

import configparser
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WANTED = HERE / "link-controller-hotkeys.ini"
STARTUP = Path.home() / "Library/Application Support/Insta360 Link Controller/startup.ini"


def ini() -> configparser.ConfigParser:
    c = configparser.ConfigParser(interpolation=None, delimiters=("=",), comment_prefixes=(";",))
    c.optionxform = str  # Qt keys are case-sensitive
    return c


def merge(startup: Path, write: bool = True) -> bool:
    """True if startup.ini changed (or, with write=False, would change)."""
    wanted, have = ini(), ini()
    wanted.read(WANTED)
    if startup.exists():
        have.read(startup)
    changed = False
    for section in wanted.sections():
        if not have.has_section(section):
            have.add_section(section)
        for key, value in wanted[section].items():
            if have[section].get(key) != value:
                have[section][key] = value
                changed = True
    if changed and write:
        startup.parent.mkdir(parents=True, exist_ok=True)
        with startup.open("w") as f:
            have.write(f, space_around_delimiters=False)
    return changed


if __name__ == "__main__":
    args = sys.argv[1:]
    check = "--check" in args
    paths = [a for a in args if a != "--check"]
    target = Path(paths[0]) if paths else STARTUP
    changed = merge(target, write=not check)
    if check:
        sys.exit(1 if changed else 0)
    print("updated" if changed else "ok", target)
