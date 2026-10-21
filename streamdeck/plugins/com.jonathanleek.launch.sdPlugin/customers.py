"""Sources for the Customers profile: the active-customers dial and Recent.

generate.py writes the index on install (customers.json: each customer's
key, label, section, footer and page number in the Customers profile). A
customer page's Back key carries {"customer": key}; when it appears, the
plugin records the visit, newest first, in recent.json beside the index.
"""

from __future__ import annotations

import bisect
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import render
from sources import Source, View, source

STATE = Path.home() / ".local/state/streamdeck-generator"
KEEP = 20  # visits remembered; Recent shows the first seven

_index: tuple[float, dict] | None = None


def index() -> dict:
    """The generator's index, re-read when the file changes (a Rescan)."""
    global _index
    path = STATE / "customers.json"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {"profile": "Customers", "customers": []}
    if _index is None or _index[0] != mtime:
        _index = (mtime, json.loads(path.read_text()))
    return _index[1]


def by_key() -> dict[str, dict]:
    return {c["key"]: c for c in index()["customers"]}


def active() -> list[dict]:
    return sorted((c for c in index()["customers"] if c["section"] == "Active"), key=lambda c: c["label"].lower())


def recent() -> list[str]:
    try:
        keys = json.loads((STATE / "recent.json").read_text())
    except (OSError, ValueError):
        return []
    return [k for k in keys if isinstance(k, str)]


def visit(key: str) -> None:
    keys = [key] + [k for k in recent() if k != key]
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = STATE / "recent.json.tmp"
    tmp.write_text(json.dumps(keys[:KEEP]))
    os.replace(tmp, STATE / "recent.json")


ZONE_ALIASES = {
    "eastern": "America/New_York", "et": "America/New_York", "est": "America/New_York", "edt": "America/New_York",
    "central": "America/Chicago", "ct": "America/Chicago", "cst": "America/Chicago", "cdt": "America/Chicago",
    "mountain": "America/Denver", "mt": "America/Denver", "mst": "America/Denver", "mdt": "America/Denver",
    "pacific": "America/Los_Angeles", "pt": "America/Los_Angeles", "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
}


def local_time(tz: str, now: dt.datetime | None = None) -> str:
    """"10:42 AM CDT" for the Client Info "Time Zone" value (an IANA name like
    America/Chicago, or Eastern / Central / Mountain / Pacific); "" if unset,
    "time zone?" if it can't be read."""
    tz = tz.strip()
    if not tz:
        return ""
    try:
        zone = ZoneInfo(ZONE_ALIASES.get(tz.lower(), tz))
    except (ZoneInfoNotFoundError, ValueError):
        return "time zone?"
    t = (now or dt.datetime.now(dt.timezone.utc)).astimezone(zone)
    return t.strftime("%-I:%M %p %Z")


def open_page(ctx, c: dict) -> None:
    ctx.deck.switch_profile(ctx.device, index()["profile"], c["page"])


@source("customers")
class CustomersDial(Source):
    """Active customers, alphabetical. On Home it starts at the most recent
    one; turn to browse, press to open. On a customer page (settings carry
    "current") turning moves straight to the neighbouring customer's page.
    The strip shows the customer's local time when Client Info has one."""

    interval = 15.0  # keeps the local time within a quarter minute

    def appear(self, ctx):
        current = ctx.settings.get("current")
        if current:
            ctx.state["sel"] = current
            return
        keys = [c["key"] for c in active()]
        ctx.state["sel"] = next((k for k in recent() if k in keys), keys[0] if keys else None)

    def rotate(self, ctx, ticks):
        act = active()
        if not act or not ticks:
            return
        keys = [c["key"] for c in act]
        sel = ctx.state.get("sel")
        if sel in keys:
            i = (keys.index(sel) + ticks) % len(keys)
        else:
            # an inactive customer's page: step to the active neighbours by name
            label = by_key().get(sel, {}).get("label", "").lower()
            at = bisect.bisect_left([c["label"].lower() for c in act], label)
            i = (at + ticks - (1 if ticks > 0 else 0)) % len(keys)
        ctx.state["sel"] = keys[i]
        if ctx.settings.get("current"):
            open_page(ctx, act[i])

    def press(self, ctx):
        c = by_key().get(ctx.state.get("sel"))
        if c and c["key"] != ctx.settings.get("current"):
            open_page(ctx, c)

    def view(self, ctx):
        act = active()
        keys = [c["key"] for c in act]
        c = by_key().get(ctx.state.get("sel"))
        if c is None and keys:  # selection gone from the index: start over
            self.appear(ctx)
            c = by_key().get(ctx.state.get("sel"))
        if c is None:
            return View(layout="layouts/customer.json", feedback={"name": "No customers", "info": ""})
        info = f"{keys.index(c['key']) + 1} / {len(keys)}" if c["key"] in keys else "inactive"
        when = local_time(c.get("tz", ""))
        if when:
            info += f" · {when}"
        return View(layout="layouts/customer.json", feedback={"name": c["label"], "info": info})


@source("recent")
class RecentKey(Source):
    """Slot n of the Recent page: the nth most recently opened customer."""

    interval = 30.0

    def customer(self, ctx) -> dict | None:
        known = by_key()
        keys = [k for k in recent() if k in known]
        slot = int(ctx.settings.get("slot", 0))
        return known[keys[slot]] if slot < len(keys) else None

    def view(self, ctx):
        c = self.customer(ctx)
        if c is None:
            return View(image=render.tile([], render.C_BASE))
        bg = render.C_CUSTOMER if c["section"] == "Active" else render.C_INACTIVE
        return View(image=render.tile(render.wrap(c["label"]), bg, footer=c["footer"]))

    def press(self, ctx):
        c = self.customer(ctx)
        if c:
            open_page(ctx, c)
