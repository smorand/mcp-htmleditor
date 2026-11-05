"""Visual render of a presentation slide through Chromium (SPEC-0008).

This package never prints; ``cli.py`` echoes. Playwright and python-pptx are imported on demand by
``render.service``, never here, so importing this package stays cheap and works without the ``render`` extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..deck import DeckError

CANVAS_WIDTH: Final = 960
CANVAS_HEIGHT: Final = 540


class RenderError(DeckError):
    """A render failed; the message is shown as is."""


class RenderUsageError(RenderError):
    """A render option is wrong (raised from US-0064 on)."""


@dataclass(frozen=True, slots=True)
class RenderProblem:
    """One layout problem found on a slide."""

    kind: str
    slide: str
    message: str


@dataclass(frozen=True, slots=True)
class RenderResult:
    """The picture written for ``slide`` and the problems found on it."""

    path: Path
    width: int
    height: int
    slide: str
    problems: tuple[RenderProblem, ...] = ()
