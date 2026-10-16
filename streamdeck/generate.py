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
  client notes; a customer page adds an Obsidian key for its Client Info note.
- Meeting and Gridfinity are fixed layouts (see pages_fixed()).

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
    words = re.split(r"[-_ ]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text))
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


def vault_clients() -> dict[str, str]:
    """slug -> note folder name under the vault's Active clients dir."""
    v = CONFIG["vault"]
    active = expand(v["path"]) / v["clients_dir"]
    if not active.is_dir():
        return {}
    return {slug(c.name): c.name for c in subdirs(active)}


def match_client(folder: str, clients: dict[str, str]) -> str | None:
    override = CONFIG.get("customer_notes", {}).get(folder)
    if override:
        return override
    s = slug(folder)
    for cs, name in clients.items():
        if cs == s or cs.startswith(s + "-") or s.startswith(cs + "-"):
            return name
    return None


def customer_page(profile: Profile, path: Path, note_folder: str | None) -> Page:
    v = CONFIG["vault"]
    page = profile.page(f"customer:{path}", path.name)
    entries: list[Key] = []
    if note_folder:
        note = f"{v['clients_dir']}/{note_folder}/{v['client_note']}"
        entries.append(obsidian_key(v["name"], note, ["Notes"]))
    entries.append(finder_key(path))
    entries += [entry_key(profile, c) for c in subdirs(path)]
    place(profile, page, entries, f"customer:{path}")
    return page


def customers_page(profile: Profile, path: Path) -> Page:
    v = CONFIG["vault"]
    page = profile.page(f"customers:{path}", "Customers")
    clients = vault_clients()
    entries: list[tuple[str, Key]] = []
    seen: set[str] = set()
    for c in subdirs(path):
        note = match_client(c.name, clients)
        if note:
            seen.add(slug(note))
        entries.append((c.name, folder_key(customer_page(profile, c, note), tile(wrap(c.name), C_CUSTOMER, footer="notes + repos" if note else "repos"))))
    for cs, name in clients.items():
        if cs in seen:
            continue
        note = f"{v['clients_dir']}/{name}/{v['client_note']}"
        entries.append((name, obsidian_key(v["name"], note, wrap(name))))
    entries.sort(key=lambda e: e[0].lower())
    place(profile, page, [k for _, k in entries], f"customers:{path}")
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


def meeting_page(profile: Profile) -> Page:
    page = profile.page("meeting", "Meeting")
    page.keys[(0, 0)] = back()
    return page


def home_page(profile: Profile) -> Page:
    home = profile.page("home", "Home")
    home.keys[(0, 0)] = folder_key(astronomer_page(profile), tile(["Astro-", "nomer"], C_HOME))
    home.keys[(1, 0)] = folder_key(meeting_page(profile), tile(["Meeting"], C_HOME, app_icon("zoom.us")))
    home.keys[(2, 0)] = folder_key(gridfinity_page(profile), tile(["Gridfinity"], C_ACCENT))
    home.keys[(3, 0)] = launch_key(
        ["/opt/homebrew/bin/uv", "run", "--quiet", str(HERE / "generate.py"), "--install"],
        tile(["Rescan"], C_HOME, footer="navigator"),
        cwd=str(REPO),
    )
    return home


# ---- emit --------------------------------------------------------------------


def device() -> tuple[str, str]:
    """(device UUID, model) for the configured device, from the app's prefs."""
    raw = subprocess.run(["defaults", "export", "com.elgato.StreamDeck", "-"], check=True, capture_output=True).stdout
    prefs = plistlib.loads(raw)
    for dev_uuid, info in prefs.get("Devices", {}).items():
        if isinstance(info, dict) and info.get("DeviceName") == CONFIG["device_name"]:
            return dev_uuid, CONFIG["device_model"]
    raise SystemExit(f"no device named {CONFIG['device_name']!r} in the Stream Deck app's preferences")


def key_json(page: Page, pos: tuple[int, int], k: Key, images_dir: Path) -> dict:
    entry: dict = {
        "ActionID": page_uuid(f"{page.id}:{pos}:{k.action}"),
        "LinkedTitle": True,
        "Name": k.name or k.action.rsplit(".", 1)[-1],
        "Resources": None,
        "Settings": k.settings,
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


def emit(profile: Profile, home: Page, out: Path, dev_uuid: str, model: str) -> None:
    out.mkdir(parents=True)
    (out / "Images").mkdir()
    # "Default" is the app's blank template page, distinct from the real pages
    # (it warns "duplicate" if it is one of them), so emit an empty one.
    blank = page_uuid("blank")
    manifest = {
        "Device": {"Model": model, "UUID": dev_uuid},
        "Name": CONFIG["profile_name"],
        "Pages": {"Current": home.id, "Default": blank, "Pages": [home.id]},
        "Version": "3.0",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    bdir = out / "Profiles" / blank.upper()
    (bdir / "Images").mkdir(parents=True)
    (bdir / "manifest.json").write_text(json.dumps({"Controllers": [], "Icon": "", "Name": ""}))
    for page in profile.pages.values():
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


def build(out: Path) -> tuple[Profile, Page, str]:
    profile = Profile()
    home = home_page(profile)
    dev_uuid, model = device()
    if out.exists():
        shutil.rmtree(out)
    emit(profile, home, out, dev_uuid, model)
    return profile, home, dev_uuid


def install(built: Path, dev_uuid: str, set_default: bool) -> Path:
    target = PROFILES_DIR / f"{page_uuid('profile').upper()}.sdProfile"
    if target.exists():
        BACKUPS.mkdir(parents=True, exist_ok=True)
        dest = BACKUPS / time.strftime("%Y%m%d%H%M%S") / target.name
        dest.parent.mkdir(parents=True)
        shutil.move(str(target), str(dest))
        print(f"moved previous profile to {dest}")
    shutil.copytree(built, target)
    print(f"installed {target}")
    if set_default:
        raw = subprocess.run(["defaults", "export", "com.elgato.StreamDeck", "-"], check=True, capture_output=True).stdout
        prefs = plistlib.loads(raw)
        info = prefs["Devices"].setdefault(dev_uuid, {})
        info.setdefault("ESDProfilesInfo", {})["ESDProfilesPreferred"] = page_uuid("profile")
        subprocess.run(["defaults", "import", "com.elgato.StreamDeck", "-"], check=True, input=plistlib.dumps(prefs))
        print("set as the device's default profile")
    return target


def restart_app() -> None:
    subprocess.run(["osascript", "-e", 'tell application "Elgato Stream Deck" to quit'], check=False, capture_output=True)
    for _ in range(50):
        if subprocess.run(["pgrep", "-x", "Stream Deck"], capture_output=True).returncode != 0:
            break
        time.sleep(0.2)
    subprocess.run(["open", "-a", "Elgato Stream Deck"], check=True)
    print("restarted the Stream Deck app")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--install", action="store_true", help="copy the built profile into the Stream Deck app")
    ap.add_argument("--restart", action="store_true", help="quit and relaunch the app around the install")
    ap.add_argument("--set-default", action="store_true", help="make it the device's default profile")
    args = ap.parse_args()

    profile, home, dev_uuid = build(BUILD)
    print(f"built {len(profile.pages)} pages into {BUILD}")
    if not args.install:
        return
    if args.restart:
        subprocess.run(["osascript", "-e", 'tell application "Elgato Stream Deck" to quit'], check=False, capture_output=True)
        time.sleep(1.5)
    install(BUILD, dev_uuid, args.set_default)
    if args.restart:
        restart_app()


if __name__ == "__main__":
    main()
