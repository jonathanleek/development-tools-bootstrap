# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""Generate the Stream Deck + profile from what's on disk.

    uv run streamdeck/generate.py            # build into streamdeck/build/, don't touch the app
    uv run streamdeck/generate.py --install  # write it into the Stream Deck app's profiles
    uv run streamdeck/generate.py --install --restart --set-default

Pages are derived, not hand-placed:

- Home: Astronomer, Meeting, Gridfinity, Rescan.
- Astronomer: walks ~/Documents/git/astronomer one page per folder. A folder
  that is a git repo gets a repo page (Ghostty here, PyCharm, Finder). The
  customers folder is the union of customer folders and the vault's Active
  client notes; a customer page adds an Obsidian key for its Client Info note
  and Slack keys for the channel links kept in that note.
- Meeting and Gridfinity are fixed layouts.

Every page gets a deterministic UUID from its path, so re-running rewrites the
same profile in place instead of creating a duplicate. The previous profile
directory is moved aside, never deleted (see BACKUPS). Nothing here needs
secrets. Key images are rendered with Pillow; app icons come from the .app
bundles via sips.
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG = json.loads((HERE / "config.json").read_text())
SD_SUPPORT = Path.home() / "Library/Application Support/com.elgato.StreamDeck"
PROFILES_DIR = SD_SUPPORT / "ProfilesV3"
BACKUPS = Path.home() / ".local/state/streamdeck-generator/backups"
BUILD = HERE / "build"
NAMESPACE = uuid.UUID("5c2f0d6e-1b7a-4a4e-9c3e-7a1e6b2c9d41")

LAUNCH_PLUGIN = {"Name": "Launch", "UUID": "com.jonathanleek.launch", "Version": "0.1.0"}
LAUNCH_ACTION = "com.jonathanleek.launch.run"
GRIDFINITY_PLUGIN = {"Name": "Gridfinity", "UUID": "com.westboundworkshop.gridfinity", "Version": "0.1.0"}
GF = "com.westboundworkshop.gridfinity"

TILE = 144
SLOTS = [(1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1)]  # after Back at (0,0)

# Palette: dark slate base, one accent per kind so a page reads at a glance.
C_BASE = "#1e2227"
C_FOLDER = "#2b3340"
C_REPO = "#1f4f4a"
C_CUSTOMER = "#5a3d14"
C_INACTIVE = "#3b3228"
C_HOME = "#30343a"
C_ACCENT = "#c7781c"
C_TEXT = "#f2f2f2"
C_DIM = "#8a919a"


def expand(p: str) -> Path:
    return Path(p).expanduser()


def page_uuid(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, key))


def slug(text: str) -> str:
    text = re.sub(r"['’]", "", text.lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


# ---- images ------------------------------------------------------------------

_FONTS = [
    Path.home() / "Library/Fonts/HackNerdFont-Bold.ttf",
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Helvetica.ttc"),
]


def font(size: int):
    for p in _FONTS:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                continue
    return ImageFont.load_default()


def wrap(text: str, max_lines: int = 3) -> list[str]:
    """Break a folder/repo name into short lines on -, _, space, camelCase."""
    # split camelCase only for long names; "McDonald's" fits a tile as it is
    if len(text) > 12:
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    words = re.split(r"[-_ ]+", text)
    lines: list[str] = []
    for w in words:
        if lines and len(lines[-1]) + 1 + len(w) <= 10:
            lines[-1] += " " + w
        else:
            lines.append(w)
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1 :])]
    return lines


def tile(lines: list[str], bg: str, icon: Image.Image | None = None, footer: str | None = None) -> Image.Image:
    img = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, TILE - 1, TILE - 1), 22, fill=bg)
    top = 0
    if icon is not None:
        ic = icon.convert("RGBA").resize((66, 66))
        img.alpha_composite(ic, ((TILE - 66) // 2, 12))
        top = 80
    longest = max((len(ln) for ln in lines), default=1)
    size = 34 if longest <= 5 else 28 if longest <= 7 else 22 if longest <= 10 else 18
    if icon is not None:
        size = min(size, 22)
    f = font(size)
    heights = [d.textbbox((0, 0), ln, font=f)[3] for ln in lines]
    gap = 4
    total = sum(heights) + gap * (len(lines) - 1)
    avail_top, avail_bottom = top, TILE - (26 if footer else 0)
    y = avail_top + (avail_bottom - avail_top - total) / 2
    for ln, h in zip(lines, heights, strict=True):
        w = d.textlength(ln, font=f)
        d.text(((TILE - w) / 2, y), ln, font=f, fill=C_TEXT)
        y += h + gap
    if footer:
        f2 = font(15)
        w = d.textlength(footer, font=f2)
        d.text(((TILE - w) / 2, TILE - 26), footer, font=f2, fill=C_DIM)
    return img


_ICON_CACHE: dict[str, Image.Image | None] = {}


def app_path(name: str) -> Path | None:
    for base in (Path.home() / "Applications", Path("/Applications"), Path("/System/Library/CoreServices")):
        p = base / f"{name}.app"
        if p.exists():
            return p
    return None


def app_icon(name: str) -> Image.Image | None:
    """The app's icon as a PIL image, via its Info.plist and sips. None if unknown."""
    if name in _ICON_CACHE:
        return _ICON_CACHE[name]
    img = None
    app = app_path(name)
    if app:
        try:
            info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
            icns = app / "Contents/Resources" / (str(info.get("CFBundleIconFile", "")).removesuffix(".icns") + ".icns")
            if icns.exists():
                with tempfile.TemporaryDirectory() as td:
                    out = Path(td) / "icon.png"
                    subprocess.run(
                        ["sips", "-s", "format", "png", "-z", "144", "144", str(icns), "--out", str(out)],
                        check=True,
                        capture_output=True,
                    )
                    img = Image.open(out).convert("RGBA")
                    img.load()
        except Exception as exc:  # noqa: BLE001 - an icon is cosmetic
            print(f"warning: no icon for {name}: {exc}", file=sys.stderr)
    _ICON_CACHE[name] = img
    return img


# ---- model -------------------------------------------------------------------


@dataclass
class Key:
    action: str
    settings: dict = field(default_factory=dict)
    image: Image.Image | None = None
    plugin: dict | None = None
    name: str = ""
    states: int = 1
    title: str = ""  # only used when image is None


@dataclass
class Dial:
    action: str
    plugin: dict | None = None
    settings: dict = field(default_factory=dict)


@dataclass
class Page:
    id: str
    name: str
    keys: dict[tuple[int, int], Key] = field(default_factory=dict)
    dials: dict[int, Dial] = field(default_factory=dict)


class Profile:
    def __init__(self) -> None:
        self.pages: dict[str, Page] = {}

    def page(self, key: str, name: str) -> Page:
        p = Page(page_uuid(key), name)
        assert p.id not in self.pages, f"duplicate page {key}"
        self.pages[p.id] = p
        return p


def back() -> Key:
    return Key("com.elgato.streamdeck.profile.backtoparent", name="Parent Folder")


def folder_key(page: Page, image: Image.Image) -> Key:
    return Key(
        "com.elgato.streamdeck.profile.openchild",
        {"ProfileUUID": page.id},
        image,
        {"Name": "Create Folder", "UUID": "com.elgato.streamdeck.profile.openchild", "Version": "1.0"},
        "Create Folder",
    )


def launch_key(argv: list[str], image: Image.Image, cwd: str | None = None) -> Key:
    settings = {"argv": argv}
    if cwd:
        settings["cwd"] = cwd
    return Key(LAUNCH_ACTION, settings, image, LAUNCH_PLUGIN, "Run command")


def open_in(app: str, target: str, label: str, extra: list[str] | None = None) -> Key:
    argv = ["/usr/bin/open", "-a", app, target] if not extra else ["/usr/bin/open", *extra]
    return launch_key(argv, tile([label], C_BASE, app_icon(app)))


def ghostty_key(path: Path) -> Key:
    app = CONFIG["apps"]["terminal"]
    argv = ["/usr/bin/open", "-na", f"{app}.app", "--args", f"--working-directory={path}"]
    return launch_key(argv, tile([app], C_BASE, app_icon(app)))


def ide_key(path: Path) -> Key:
    app = CONFIG["apps"]["ide"]
    return launch_key(["/usr/bin/open", "-a", app, str(path)], tile([app], C_BASE, app_icon(app)))


def finder_key(path: Path) -> Key:
    return launch_key(["/usr/bin/open", str(path)], tile(["Finder"], C_BASE, app_icon("Finder")))


def obsidian_key(vault: str, note: str | None, label: list[str]) -> Key:
    url = f"obsidian://open?vault={quote(vault)}"
    if note:
        url += f"&file={quote(note)}"
    return launch_key(["/usr/bin/open", url], tile(label, C_BASE, app_icon(CONFIG["apps"]["obsidian"])))


def slack_key(channel_id: str, label: str) -> Key:
    team = CONFIG["slack"]["team"]
    url = f"slack://channel?team={team}&id={channel_id}"
    return launch_key(["/usr/bin/open", url], tile([label], C_BASE, app_icon("Slack")))


def logo_tile(name: str, bg: str) -> Image.Image:
    """A key showing streamdeck/icons/<name>.png scaled to fit, no text."""
    img = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, TILE - 1, TILE - 1), 22, fill=bg)
    mark = Image.open(HERE / "icons" / f"{name}.png").convert("RGBA")
    mark = mark.crop(mark.getbbox() or (0, 0, *mark.size))
    s = min(104 / mark.width, 104 / mark.height)
    mark = mark.resize((max(1, int(mark.width * s)), max(1, int(mark.height * s))))
    img.alpha_composite(mark, ((TILE - mark.width) // 2, (TILE - mark.height) // 2))
    return img


# ---- navigator ---------------------------------------------------------------


def is_repo(p: Path) -> bool:
    return (p / ".git").exists()


def subdirs(p: Path) -> list[Path]:
    return sorted((c for c in p.iterdir() if c.is_dir() and not c.name.startswith(".")), key=lambda c: c.name.lower())


def has_repo_below(p: Path) -> bool:
    """True if any git repo sits somewhere under p (p itself excluded)."""
    return any(is_repo(c) or has_repo_below(c) for c in subdirs(p))


def place(profile: Profile, page: Page, entries: list[Key], key: str) -> None:
    """Back at (0,0), then entries; more than seven spill into a More ▸ page."""
    page.keys[(0, 0)] = back()
    if len(entries) <= len(SLOTS):
        for slot, k in zip(SLOTS, entries, strict=False):
            page.keys[slot] = k
        return
    head, tail = entries[: len(SLOTS) - 1], entries[len(SLOTS) - 1 :]
    for slot, k in zip(SLOTS, head, strict=False):
        page.keys[slot] = k
    more = profile.page(key + "/more", page.name + " (more)")
    page.keys[SLOTS[-1]] = folder_key(more, tile(["More ▸"], C_FOLDER))
    place(profile, more, tail, key + "/more")


def repo_page(profile: Profile, path: Path) -> Page:
    """Leaf: a git repo, or a plain working folder with no repos below it."""
    page = profile.page(f"repo:{path}", path.name)
    place(profile, page, [ghostty_key(path), ide_key(path), finder_key(path)], f"repo:{path}")
    return page


def entry_key(profile: Profile, child: Path) -> Key:
    """Walk down only while there are repos to find; everything else is a leaf."""
    if is_repo(child):
        return folder_key(repo_page(profile, child), tile(wrap(child.name), C_REPO, footer="repo"))
    if has_repo_below(child):
        return folder_key(folder_page(profile, child), tile(wrap(child.name), C_FOLDER))
    return folder_key(repo_page(profile, child), tile(wrap(child.name), C_FOLDER, footer="folder"))


def folder_page(profile: Profile, path: Path) -> Page:
    page = profile.page(f"dir:{path}", path.name)
    place(profile, page, [entry_key(profile, c) for c in subdirs(path)], f"dir:{path}")
    return page


def vault_clients(section: str) -> dict[str, str]:
    """slug -> note folder name under the vault's clients root for one section
    ("Active" / "Inactive"). Obsidian's folder is the source of truth."""
    v = CONFIG["vault"]
    root = expand(v["path"]) / v["clients_root"] / section
    if not root.is_dir():
        return {}
    return {slug(c.name): c.name for c in subdirs(root)}


def match_client(folder: str, clients: dict[str, str]) -> str | None:
    override = CONFIG.get("customer_notes", {}).get(folder)
    if override:
        return override
    s = slug(folder)
    for cs, name in clients.items():
        if cs == s or cs.startswith(s + "-") or s.startswith(cs + "-"):
            return name
    return None


@dataclass
class Customer:
    """One customer as the deck sees it: a folder, a vault note folder, or both.
    `section` is the vault folder the note sits in (Active / Inactive); a
    folder with no note counts as active, since it has live work."""

    label: str
    folder: Path | None
    note_folder: str | None
    section: str = "Active"

    @property
    def key(self) -> str:
        return slug(self.note_folder or self.folder.name)

    @property
    def footer(self) -> str:
        parts = (["notes"] if self.note_folder else []) + (["repos"] if self.folder else [])
        return " + ".join(parts)

    @property
    def note(self) -> str | None:
        """Vault-relative path of the Client Info note, without .md."""
        if not self.note_folder:
            return None
        v = CONFIG["vault"]
        return f"{v['clients_root']}/{self.section}/{self.note_folder}/{v['client_note']}"


def slack_channels(c: Customer) -> dict[str, str]:
    """Channel IDs from the client's Client Info note: table rows named
    "Slack (internal)" / "Slack (external)" holding a #channel-name or a
    channel link (https://<workspace>.slack.com/archives/C...). Missing or
    blank = no key."""
    if not c.note:
        return {}
    note = expand(CONFIG["vault"]["path"]) / f"{c.note}.md"
    if not note.is_file():
        return {}
    out: dict[str, str] = {}
    for line in note.read_text(errors="replace").splitlines():
        m = re.match(r"\|\s*Slack\s*\((internal|external)\)\s*\|(.*)", line, re.I)
        if not m:
            continue
        cid = resolve_channel(m.group(2), note)
        if cid:
            out[m.group(1).lower()] = cid
    return out


_CHANNELS: dict[str, str] | None = None


def resolve_channel(cell: str, note: Path) -> str | None:
    """A table cell holding either a channel link (…/archives/C…) or a
    #channel-name, looked up in streamdeck/slack-channels.json."""
    global _CHANNELS
    link = re.search(r"/archives/(C[A-Z0-9]+)", cell)
    if link:
        return link.group(1)
    name = re.search(r"#([a-z0-9][a-z0-9._-]*)", cell, re.I)
    if not name:
        return None
    if _CHANNELS is None:
        _CHANNELS = {k: v for k, v in json.loads((HERE / "slack-channels.json").read_text()).items() if not k.startswith("_")}
    cid = _CHANNELS.get(name.group(1).lower())
    if not cid:
        print(f"warning: #{name.group(1)} in {note.name} ({note.parent.name}) is not in slack-channels.json; no key", file=sys.stderr)
    return cid


def customer_page(profile: Profile, c: Customer) -> Page:
    page = profile.page(f"customer:{c.key}", c.label)
    entries: list[Key] = []
    if c.note:
        entries.append(obsidian_key(CONFIG["vault"]["name"], c.note, ["Notes"]))
    if c.folder:
        entries.append(finder_key(c.folder))
    channels = slack_channels(c)
    if channels.get("internal"):
        entries.append(slack_key(channels["internal"], "Internal"))
    if channels.get("external"):
        entries.append(slack_key(channels["external"], "External"))
    if c.folder:
        entries += [entry_key(profile, d) for d in subdirs(c.folder)]
    place(profile, page, entries, f"customer:{c.key}")
    return page


def customers(path: Path) -> tuple[list[Customer], list[Customer]]:
    """(active, inactive): the union of customer folders and the vault's client
    notes, split by which vault section the note is in."""
    active_notes, inactive_notes = vault_clients("Active"), vault_clients("Inactive")
    out: list[Customer] = []
    seen: set[str] = set()
    for c in subdirs(path):
        note = match_client(c.name, active_notes)
        section = "Active"
        if not note:
            note = match_client(c.name, inactive_notes)
            section = "Inactive" if note else "Active"
        if note:
            seen.add(slug(note))
        out.append(Customer(note or c.name, c, note, section))
    for section, notes in (("Active", active_notes), ("Inactive", inactive_notes)):
        for cs, name in notes.items():
            if cs not in seen:
                out.append(Customer(name, None, name, section))
    out.sort(key=lambda c: c.label.lower())
    return [c for c in out if c.section == "Active"], [c for c in out if c.section == "Inactive"]


def customer_key(profile: Profile, c: Customer) -> Key:
    bg = C_CUSTOMER if c.section == "Active" else C_INACTIVE
    return folder_key(customer_page(profile, c), tile(wrap(c.label), bg, footer=c.footer))


def customers_page(profile: Profile, path: Path) -> Page:
    """Active customers, then Inactive ▸ as the very last entry so it lands on
    the last page rather than spending a key up front."""
    page = profile.page(f"customers:{path}", "Customers")
    active, inactive = customers(path)
    entries = [customer_key(profile, c) for c in active]
    if inactive:
        inactive_page = profile.page(f"customers-inactive:{path}", "Inactive customers")
        place(profile, inactive_page, [customer_key(profile, c) for c in inactive], f"customers-inactive:{path}")
        entries.append(folder_key(inactive_page, tile(["Inactive ▸"], C_FOLDER, footer=f"{len(inactive)} customers")))
    place(profile, page, entries, f"customers:{path}")
    return page


def astronomer_page(profile: Profile) -> Page:
    root = expand(CONFIG["git_root"])
    vault_path = expand(CONFIG["vault"]["path"])
    page = profile.page(f"astronomer:{root}", "Astronomer")
    entries: list[Key] = []
    for c in subdirs(root):
        if c.name == CONFIG["customers_dir"]:
            entries.append(folder_key(customers_page(profile, c), tile(["Customers"], C_CUSTOMER)))
        elif c == vault_path:
            entries.append(obsidian_key(CONFIG["vault"]["name"], None, ["Vault"]))
        else:
            entries.append(entry_key(profile, c))
    place(profile, page, entries, f"astronomer:{root}")
    return page


# ---- fixed pages -------------------------------------------------------------


def gridfinity_page(profile: Profile) -> Page:
    """Mirrors the kiosk's layout v1 as far as a Back key allows."""
    page = profile.page("gridfinity", "Gridfinity")
    gf_key = lambda a, states=1: Key(f"{GF}.{a}", {}, None, GRIDFINITY_PLUGIN, a, states)  # noqa: E731
    page.keys[(0, 0)] = back()
    page.keys[(1, 0)] = gf_key("label", 2)
    page.keys[(1, 1)] = gf_key("scoop", 2)
    page.keys[(3, 0)] = gf_key("plate")
    page.keys[(3, 1)] = gf_key("bin")
    page.keys[(2, 1)] = gf_key("folder")
    page.dials[0] = Dial(f"{GF}.x", GRIDFINITY_PLUGIN)
    page.dials[1] = Dial(f"{GF}.y", GRIDFINITY_PLUGIN)
    page.dials[2] = Dial(f"{GF}.height", GRIDFINITY_PLUGIN)
    return page


# ---- meeting: Zoom plugin + Insta360 Link Controller global shortcuts --------

ZOOM_PLUGIN = {"Name": "Zoom", "UUID": "com.elgato.zoom", "Version": "1.0"}
STICKY_PREFIXES = ("com.elgato.zoom.",)  # settings edited in the app's UI survive a rescan
STICKY: dict[tuple[str, str, str], dict] = {}
STICKY_BY_ACTION: dict[str, dict] = {}

# macOS virtual key codes / Qt key codes the hotkey action stores.
# Arrow keys are deliberately absent: ctrl+arrows are Mission Control shortcuts on
# macOS and the extra modifiers do not stop them firing. Letters are safe.
VK = {"0": 29, "1": 18, "2": 19, "3": 20, "=": 24, "-": 27, "i": 34, "j": 38, "k": 40, "l": 37}
QT = {"0": 48, "1": 49, "2": 50, "3": 51, "=": 61, "-": 45, "i": 73, "j": 74, "k": 75, "l": 76}
MOD = {"shift": 1, "ctrl": 2, "option": 4, "cmd": 8}
NO_KEY = {"KeyCmd": False, "KeyCtrl": False, "KeyModifiers": 0, "KeyOption": False, "KeyShift": False, "NativeCode": -1, "QTKeyCode": 33554431, "VKeyCode": -1}


def chord(key: str, *mods: str) -> dict:
    return {
        "KeyCmd": "cmd" in mods,
        "KeyCtrl": "ctrl" in mods,
        "KeyModifiers": sum(MOD[m] for m in mods),
        "KeyOption": "option" in mods,
        "KeyShift": "shift" in mods,
        "NativeCode": VK[key],
        "QTKeyCode": QT[key],
        "VKeyCode": VK[key],
    }


def camera_chord(key: str) -> dict:
    """The shortcuts assigned in Link Controller: ctrl+option+cmd+<key>."""
    return chord(key, *CONFIG["camera"]["modifiers"])


def hotkey_key(hk: dict, label: list[str], icon: str | None = None) -> Key:
    settings = {"Coalesce": True, "Hotkeys": [hk, dict(NO_KEY), dict(NO_KEY), dict(NO_KEY)]}
    return Key("com.elgato.streamdeck.system.hotkey", settings, tile(label, C_BASE, app_icon(icon) if icon else None), None, "Hotkey")


def hotkey_dial(ccw: dict, cw: dict, press: dict | None = None) -> Dial:
    """Hotkey action on a dial: [rotate left, rotate right, press, touch]."""
    return Dial("com.elgato.streamdeck.system.hotkey", None, {"Coalesce": True, "Hotkeys": [ccw, cw, press or dict(NO_KEY), dict(NO_KEY)]})


def zoom_key(action: str, states: int) -> Key:
    settings: dict = {}
    if action == "screenshare":
        settings = {"monitor": json.dumps(CONFIG["zoom"]["share_monitor"]), "optimizeVideo": False, "shareSound": False}
    return Key(f"com.elgato.zoom.{action}", settings, None, ZOOM_PLUGIN, action, states)


def meeting_keys(profile: Profile, page: Page, key: str) -> None:
    cam = CONFIG["camera"]["keys"]
    icon = CONFIG["camera"]["app"]
    page.keys[(1, 0)] = zoom_key("mute", 2)
    page.keys[(2, 0)] = zoom_key("video", 2)
    page.keys[(3, 0)] = zoom_key("screenshare", 2)
    page.keys[(0, 1)] = hotkey_key(camera_chord(cam["face"]), ["Meeting"], icon)
    page.keys[(1, 1)] = hotkey_key(camera_chord(cam["whiteboard"]), ["White-", "board"], icon)
    page.keys[(2, 1)] = hotkey_key(camera_chord(cam["desk"]), ["Desk"], icon)
    page.keys[(3, 1)] = zoom_key("leavemeeting", 1)
    page.dials[0] = Dial("com.elgato.streamdeck.system.multimedia", None, {"actionIdx": 18})  # system volume
    page.dials[1] = hotkey_dial(camera_chord(cam["zoom_out"]), camera_chord(cam["zoom_in"]), camera_chord(cam["center"]))
    page.dials[2] = hotkey_dial(camera_chord(cam["left"]), camera_chord(cam["right"]))
    page.dials[3] = hotkey_dial(camera_chord(cam["down"]), camera_chord(cam["up"]))


def meeting_page(profile: Profile) -> Page:
    """Opened from Home like every other page; (0,0) is Back. The rarer Zoom
    actions (raise hand, react, record, share mode, mute all) are not on the
    deck: an app-triggered Zoom profile was tried and dropped, since the
    Astronomer pages are needed during calls."""
    page = profile.page("meeting", "Meeting")
    page.keys[(0, 0)] = back()
    meeting_keys(profile, page, "meeting")
    return page


def home_page(profile: Profile) -> Page:
    home = profile.page("home", "Home")
    try:
        astro_tile = logo_tile("astronomer-mark", C_HOME)
    except FileNotFoundError:
        astro_tile = tile(["Astro-", "nomer"], C_HOME)
    home.keys[(0, 0)] = folder_key(astronomer_page(profile), astro_tile)
    home.keys[(1, 0)] = folder_key(meeting_page(profile), tile(["Meeting"], C_HOME, app_icon("zoom.us")))
    home.keys[(2, 0)] = folder_key(gridfinity_page(profile), tile(["Gridfinity"], C_ACCENT))
    home.keys[(3, 0)] = launch_key(
        ["/opt/homebrew/bin/uv", "run", "--quiet", str(HERE / "generate.py"), "--install", "--restart"],
        tile(["Rescan"], C_HOME, footer="navigator"),
        cwd=str(REPO),
    )
    return home


# ---- emit --------------------------------------------------------------------


APP_LOG = Path.home() / "Library/Logs/ElgatoStreamDeck/StreamDeck.log"


def device() -> tuple[str, str]:
    """(device UUID, model) for the deck to target, from the app's prefs.

    Profiles are bound to a device's serial, so a replacement deck is a new
    device. Candidates are the devices whose name starts with the configured
    one (the app names a second unit "Stream Deck + 2"); among them, the one
    the app most recently reported attached wins, else the app's preferred
    device, else the first."""
    raw = subprocess.run(["defaults", "export", "com.elgato.StreamDeck", "-"], check=True, capture_output=True).stdout
    prefs = plistlib.loads(raw)
    devices = prefs.get("Devices", {})
    candidates = [
        u for u, info in devices.items()
        if isinstance(info, dict) and str(info.get("DeviceName", "")).startswith(CONFIG["device_name"])
    ]
    if not candidates:
        raise SystemExit(f"no device named {CONFIG['device_name']!r} in the Stream Deck app's preferences")
    if len(candidates) > 1 and APP_LOG.exists():
        attached = re.findall(r"device attached (@\(\d+\)\[[^\]]+\])", APP_LOG.read_text(errors="replace"))
        for u in reversed(attached):
            if u in candidates:
                return u, CONFIG["device_model"]
    preferred = str(devices.get("PreferredDevice", "")).lstrip("@")
    for u in candidates:
        if u.lstrip("@") == preferred:
            return u, CONFIG["device_model"]
    return candidates[0], CONFIG["device_model"]


def key_json(page: Page, pos: tuple[int, int], k: Key, images_dir: Path) -> dict:
    pos_str = f"{pos[0]},{pos[1]}"
    settings = k.settings
    if k.action.startswith(STICKY_PREFIXES):
        # exact key first, else the same action configured anywhere (the Share
        # key on the folder page and on the Zoom profile should agree)
        settings = STICKY.get((page.id, pos_str, k.action)) or STICKY_BY_ACTION.get(k.action) or settings
    entry: dict = {
        "ActionID": page_uuid(f"{page.id}:{pos}:{k.action}"),
        "LinkedTitle": True,
        "Name": k.name or k.action.rsplit(".", 1)[-1],
        "Resources": None,
        "Settings": settings,
        "State": 0,
        "UUID": k.action,
    }
    if k.plugin:
        entry["Plugin"] = k.plugin
    if k.image is not None:
        fname = f"{pos[0]}-{pos[1]}.png"
        k.image.save(images_dir / fname)
        state = {"Image": f"Images/{fname}", "ShowTitle": False, "Title": ""}
    elif k.title:
        state = {"Title": k.title, "ShowTitle": True, "TitleAlignment": "bottom", "FontSize": 12, "TitleColor": "#ffffff"}
    else:
        state = {}
    entry["States"] = [dict(state) for _ in range(k.states)]
    return entry


def dial_json(page: Page, col: int, d: Dial) -> dict:
    entry: dict = {
        "ActionID": page_uuid(f"{page.id}:dial{col}:{d.action}"),
        "LinkedTitle": True,
        "Name": d.action.rsplit(".", 1)[-1],
        "Resources": None,
        "Settings": d.settings,
        "State": 0,
        "States": [{}],
        "UUID": d.action,
    }
    if d.plugin:
        entry["Plugin"] = d.plugin
    return entry


@dataclass
class Target:
    """One .sdProfile to write: the main profile, or the Zoom-triggered one."""

    key: str  # page_uuid(key) is the profile UUID
    name: str
    profile: Profile
    home: Page
    app_identifier: str | None = None

    @property
    def uuid(self) -> str:
        return page_uuid(self.key)

    @property
    def installed(self) -> Path:
        return PROFILES_DIR / f"{self.uuid.upper()}.sdProfile"

    @property
    def built(self) -> Path:
        return BUILD / f"{self.uuid.upper()}.sdProfile"


def emit(t: Target, dev_uuid: str, model: str) -> None:
    out = t.built
    out.mkdir(parents=True)
    (out / "Images").mkdir()
    # "Default" is the app's blank template page, distinct from the real pages
    # (it warns "duplicate" if it is one of them), so emit an empty one.
    blank = page_uuid(t.key + ":blank")
    manifest: dict = {
        "Device": {"Model": model, "UUID": dev_uuid},
        "Name": t.name,
        "Pages": {"Current": t.home.id, "Default": blank, "Pages": [t.home.id]},
        "Version": "3.0",
    }
    if t.app_identifier:
        manifest["AppIdentifier"] = t.app_identifier
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    bdir = out / "Profiles" / blank.upper()
    (bdir / "Images").mkdir(parents=True)
    (bdir / "manifest.json").write_text(json.dumps({"Controllers": [], "Icon": "", "Name": ""}))
    for page in t.profile.pages.values():
        pdir = out / "Profiles" / page.id.upper()
        (pdir / "Images").mkdir(parents=True)
        keypad = {f"{c},{r}": key_json(page, (c, r), k, pdir / "Images") for (c, r), k in sorted(page.keys.items())}
        encoder = {f"{c},0": dial_json(page, c, d) for c, d in sorted(page.dials.items())}
        doc = {
            "Controllers": [
                {"Actions": keypad, "Type": "Keypad"},
                {"Actions": encoder, "Type": "Encoder"},
            ],
            "Icon": "",
            "Name": page.name,
        }
        (pdir / "manifest.json").write_text(json.dumps(doc, indent=1))


def load_sticky(targets: list[Target]) -> None:
    """Remember settings the user edited in the app's UI for sticky actions
    (Zoom's share-screen monitor choice, for one) so a rescan keeps them."""
    for t in targets:
        for m in (t.installed / "Profiles").glob("*/manifest.json"):
            page_id = m.parent.name.lower()
            try:
                doc = json.loads(m.read_text())
            except (OSError, ValueError):
                continue
            for ctl in doc.get("Controllers") or []:
                for pos, a in (ctl.get("Actions") or {}).items():
                    if str(a.get("UUID", "")).startswith(STICKY_PREFIXES) and a.get("Settings"):
                        STICKY[(page_id, pos, a["UUID"])] = a["Settings"]
                        STICKY_BY_ACTION.setdefault(a["UUID"], a["Settings"])


def build() -> tuple[list[Target], str]:
    main = Profile()
    home = home_page(main)
    targets = [Target("profile", CONFIG["profile_name"], main, home)]
    load_sticky(targets)
    dev_uuid, model = device()
    if BUILD.exists():
        shutil.rmtree(BUILD)
    for t in targets:
        emit(t, dev_uuid, model)
    return targets, dev_uuid


RETIRED = ["profile-zoom"]  # profiles this generator used to emit; moved aside on install


def install(targets: list[Target], dev_uuid: str, set_default: bool) -> None:
    stamp = time.strftime("%Y%m%d%H%M%S")
    for key in RETIRED:
        old = PROFILES_DIR / f"{page_uuid(key).upper()}.sdProfile"
        if old.exists():
            dest = BACKUPS / stamp / old.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(dest))
            print(f"retired {old.name} -> {dest}")
    for t in targets:
        if t.installed.exists():
            dest = BACKUPS / stamp / t.installed.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(t.installed), str(dest))
            print(f"moved previous profile to {dest}")
        shutil.copytree(t.built, t.installed)
        print(f"installed {t.installed.name} ({t.name})")
    if set_default:
        raw = subprocess.run(["defaults", "export", "com.elgato.StreamDeck", "-"], check=True, capture_output=True).stdout
        prefs = plistlib.loads(raw)
        info = prefs["Devices"].setdefault(dev_uuid, {})
        info.setdefault("ESDProfilesInfo", {})["ESDProfilesPreferred"] = targets[0].uuid
        prefs["Devices"]["PreferredDevice"] = "@" + dev_uuid
        subprocess.run(["defaults", "import", "com.elgato.StreamDeck", "-"], check=True, input=plistlib.dumps(prefs))
        print("set as the device's default profile")


def app_running() -> bool:
    return subprocess.run(["pgrep", "-x", "Stream Deck"], capture_output=True).returncode == 0


def quit_app() -> None:
    subprocess.run(["osascript", "-e", 'tell application "Elgato Stream Deck" to quit'], check=False, capture_output=True)
    for _ in range(50):
        if not app_running():
            break
        time.sleep(0.2)
    else:
        subprocess.run(["pkill", "-x", "Stream Deck"], check=False)  # stuck on a modal dialog
        time.sleep(1)
    # Launched from the deck, the quit is still finishing when the process
    # disappears from pgrep; an `open` that arrives then is handed to the dying
    # instance and nothing starts. Give it a moment.
    time.sleep(2)
    reset_session_report()


def relaunch_app() -> None:
    for attempt in range(5):
        subprocess.run(["open", "-a", "Elgato Stream Deck"], check=False)
        for _ in range(25):
            time.sleep(0.2)
            if app_running():
                print("restarted the Stream Deck app" + (f" (attempt {attempt + 1})" if attempt else ""))
                return
    print("could not relaunch the Stream Deck app; open it by hand", file=sys.stderr)


def reset_session_report() -> None:
    """The app remembers how many actions the last session had and, if the
    next launch loads fewer, offers to restore its daily backup ("data loss
    detected"). A rescan that drops a page would trigger that every time, so
    zero the remembered count while the app is quit."""
    raw = subprocess.run(["defaults", "export", "com.elgato.StreamDeck", "-"], check=True, capture_output=True).stdout
    prefs = plistlib.loads(raw)
    report = prefs.get("last_app_session_report")
    if isinstance(report, dict) and report.get("action_count"):
        report["action_count"] = 0
        subprocess.run(["defaults", "import", "com.elgato.StreamDeck", "-"], check=True, input=plistlib.dumps(prefs))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--install", action="store_true", help="copy the built profiles into the Stream Deck app")
    ap.add_argument("--restart", action="store_true", help="quit and relaunch the app around the install")
    ap.add_argument("--set-default", action="store_true", help="make the main profile the device's default")
    args = ap.parse_args()

    targets, dev_uuid = build()
    pages = sum(len(t.profile.pages) for t in targets)
    print(f"built {len(targets)} profiles, {pages} pages, into {BUILD}")
    if not args.install:
        return
    if args.restart:
        quit_app()
    install(targets, dev_uuid, args.set_default)
    if args.restart:
        relaunch_app()


if __name__ == "__main__":
    main()
