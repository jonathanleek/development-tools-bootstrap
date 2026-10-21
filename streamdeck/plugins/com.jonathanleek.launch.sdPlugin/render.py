"""Key images as SVG, so the plugin needs nothing beyond the standard library.

The look follows generate.py's Pillow tiles (144px rounded square, centred
bold text, dim footer); the palette below is copied from there and should
change with it.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

TILE = 144

C_BASE = "#1e2227"
C_HOME = "#30343a"
C_ACCENT = "#c7781c"
C_TEXT = "#f2f2f2"
C_DIM = "#8a919a"
C_OK = "#2f6b3a"
C_WARN = "#8a6212"
C_ERR = "#8a2b22"

FONT = "'Hack Nerd Font', 'Arial', 'Helvetica', sans-serif"


def tile(lines: list[str], bg: str = C_BASE, footer: str | None = None, fg: str = C_TEXT) -> str:
    longest = max((len(ln) for ln in lines), default=1)
    size = 34 if longest <= 5 else 28 if longest <= 7 else 22 if longest <= 10 else 18
    gap = 4
    total = size * len(lines) + gap * (len(lines) - 1)
    bottom = TILE - (26 if footer else 0)
    y = (bottom - total) / 2 + size * 0.8  # first baseline
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{TILE}" height="{TILE}" viewBox="0 0 {TILE} {TILE}">',
        f'<rect x="0" y="0" width="{TILE}" height="{TILE}" rx="22" fill="{bg}"/>',
    ]
    for ln in lines:
        parts.append(_text(ln, y, size, fg))
        y += size + gap
    if footer:
        parts.append(_text(footer, TILE - 26 + 15 * 0.8 + 2, 15, C_DIM))
    parts.append("</svg>")
    return "".join(parts)


def _text(s: str, y: float, size: int, fill: str) -> str:
    return (
        f'<text x="{TILE / 2}" y="{y:.1f}" font-family="{FONT}" font-weight="bold" '
        f'font-size="{size}" fill="{fill}" text-anchor="middle">{escape(s)}</text>'
    )


def data_url(svg: str) -> str:
    """The form setImage takes for SVG (per the Stream Deck SDK docs)."""
    return "data:image/svg+xml;charset=utf8," + svg
