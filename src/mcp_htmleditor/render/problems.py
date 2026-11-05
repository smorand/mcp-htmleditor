"""Layout problems of a render: ordering and wording only (SPEC-0008 DEC-010, DEC-015).

The measures themselves are the page scripts of ``scripts.py``; this module never touches the browser.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from . import CANVAS_HEIGHT, RenderProblem

KIND_ORDER: Final = ("script", "image", "font", "overflow", "clipped")
NO_SLIDE: Final = "-"


@dataclass(frozen=True, slots=True)
class RawSlide:
    """What the measure script returned for one slide."""

    slide: str
    index: int
    content: int
    clipped: tuple[str, ...]
    fonts: tuple[str, ...]


def build_problems(
    slides: Sequence[RawSlide],
    images: Sequence[RenderProblem] = (),
    errors: Sequence[RenderProblem] = (),
) -> list[RenderProblem]:
    """Every problem, ordered: slide ``-`` first, then slide order, then ``KIND_ORDER``, then collection order."""
    found = [*errors, *images]
    for raw in slides:
        found.extend(_slide_problems(raw))
    rank = {raw.slide: raw.index for raw in slides}
    return sorted(found, key=lambda p: (_slide_rank(p.slide, rank), KIND_ORDER.index(p.kind)))


def format_line(problem: RenderProblem) -> str:
    """``<kind> <slide>: <message>``."""
    return f"{problem.kind} {problem.slide}: {problem.message}"


def final_line(count: int) -> str:
    """``report: OK``, ``report: 1 problem`` or ``report: N problems``."""
    if count == 0:
        return "report: OK"
    return f"report: {count} problem{'' if count == 1 else 's'}"


def _slide_problems(raw: RawSlide) -> list[RenderProblem]:
    problems: list[RenderProblem] = []
    if raw.content > CANVAS_HEIGHT:
        message = f"content is {raw.content}px tall, the slide is {CANVAS_HEIGHT}px"
        problems.append(RenderProblem("overflow", raw.slide, message))
    problems.extend(RenderProblem("clipped", raw.slide, f"{s} is outside the slide frame") for s in raw.clipped)
    return problems


def _slide_rank(slide: str, rank: dict[str, int]) -> int:
    if slide == NO_SLIDE:
        return -1
    return rank.get(slide, len(rank))
