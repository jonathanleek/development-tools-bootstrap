"""Status sources: what a live key or dial shows, and what pressing it does.

A key or dial names its source in its settings ({"source": "load", ...},
written by generate.py). Each source is a Source subclass registered with
@source("name"); the runtime calls view() every `interval` seconds while one
of its keys is on screen, and the input hooks when the key is used. Sources
get the Ctx of the key, so per-key settings live in ctx.settings and anything
to remember between calls (a dial's selection, say) in ctx.state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deck import Ctx


@dataclass(frozen=True)
class View:
    title: str | None = None
    image: str | None = None  # SVG markup (render.py)
    feedback: dict | None = None  # dial touch strip: layout item -> value


class Source:
    interval: float = 5.0

    def view(self, ctx: Ctx) -> View:
        raise NotImplementedError

    def press(self, ctx: Ctx) -> None:
        """Key press, or dial press."""

    def rotate(self, ctx: Ctx, ticks: int) -> None:
        """Dial turned; ticks is negative for counter-clockwise."""

    def tap(self, ctx: Ctx, hold: bool) -> None:
        """Touch strip tapped (hold: long tap)."""


SOURCES: dict[str, Source] = {}


def source(name: str):
    def register(cls: type[Source]) -> type[Source]:
        SOURCES[name] = cls()
        return cls

    return register
