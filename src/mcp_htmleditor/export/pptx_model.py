"""Shared model of the PPTX exporter: constants, report, block types and the builder base class.

``to_pptx.py`` and the ``pptx_*`` builder modules import from here; nothing in this
module imports from ``to_pptx.py``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import Tag
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

from .pptx_style import (
    PX_IN,
    Box,
    StyleResolver,
    TextStyle,
    Theme,
    parse_pct,
    parse_px,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKIP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "template",
        "link",
        "meta",
        "svg",
        "select",
        "option",
        "button",
        "input",
        "iframe",
        "audio",
        "video",
    }
)
"""Tags never exported: code, decorations and interactive shell widgets."""

SHELL_CLASSES = frozenset({"toolbar", "shell-header", "status-bar", "nav-arrow", "stage", "slide-frame"})
"""Classes of the navigation shell, outside of any slide content."""

BLOCK_TAGS = frozenset(
    {
        "div",
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "table",
        "section",
        "article",
        "header",
        "footer",
        "figure",
        "blockquote",
        "pre",
        "hr",
    }
)

GRID_CLASSES = frozenset({"cds-grid", "stat-grid", "mention-wrap"})

TILE_CLASSES = frozenset({"cds-tile", "stat-card", "mention-pill"})

INLINE_BLOCK_CLASSES = frozenset({"arch-node-label", "gantt-sub"})
"""Inline classes the templates display as blocks (they get their own paragraph)."""

INLINE_BLOCK_TAGS = frozenset({"small"})
"""Inline tags used as sub-labels in the templates (``display: block``)."""

FILL_KEYS = ("background", "background-color")
BAR_KEYS = ("border-left-color", "border-left", "border-top-color", "border-top")

_PX_FLEX_BASIS_RE = re.compile(r"0\s+0\s+(\d+(?:\.\d+)?)px")
"""Matches the fixed-width shorthand (e.g. ``flex:0 0 116px``) of a custom Gantt label cell."""

_FLEX_SHORTHAND_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)(?:\s+(\d+(?:\.\d+)?))?(?:\s+(.+))?$")
"""Matches the ``flex: <grow> [<shrink>] [<basis>]`` shorthand, all parts optional-ish."""

_ALIGN = {
    "left": PP_ALIGN.LEFT,
    "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
    "justify": PP_ALIGN.JUSTIFY,
}

_SHAPES = {
    "box": MSO_SHAPE.ROUNDED_RECTANGLE,
    "rect": MSO_SHAPE.RECTANGLE,
    "circle": MSO_SHAPE.OVAL,
    "oval": MSO_SHAPE.OVAL,
    "diamond": MSO_SHAPE.DIAMOND,
    "cylinder": MSO_SHAPE.CAN,
    "cloud": MSO_SHAPE.CLOUD,
}

_NOTIF_VARIANTS = {
    "success": ("DEFBE6", "24A148", "0E6027"),
    "warning": ("FDF6DD", "F1C21B", "8E6A00"),
    "error": ("FFF1F1", "DA1E28", "A2191F"),
}
"""``class`` variant of ``.cds-notification`` mapped to (fill, bar, title)."""

_ANNOT_CLASS_COLORS = {
    "annot-blue": ("003A8D", "FFFFFF"),
    "annot-orange": ("FBAE40", "4A3000"),
    "annot-coral": ("EC6962", "FFFFFF"),
}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class ExportReport:
    """Outcome of an export: slide count plus every dropped or guessed item."""

    slide_count: int = 0
    warnings: list[str] = field(default_factory=list)
    charter: str | None = None

    def warn(self, message: str) -> None:
        """Record a dropped or approximated item.

        Callers are responsible for surfacing the list; the CLI prints it and
        exits non zero when no slide could be exported.
        """
        self.warnings.append(message)
        logger.debug("export pptx: %s", message)


# ---------------------------------------------------------------------------
# Internal model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Context:
    """Shared state of one export run."""

    res: StyleResolver
    theme: Theme
    base_dir: Path
    report: ExportReport


@dataclass
class _Block:
    """A laid out piece of slide content, with its measured natural height."""

    kind: str
    element: Tag
    height: float
    min_height: float = 0.0
    max_height: float = 0.0
    flexible: bool = False
    style: TextStyle | None = None
    columns: list[_Column] | None = None


@dataclass(frozen=True)
class _Column:
    """One side-by-side column of a flex row block: its own slot and content.

    ``left_offset`` and ``width`` are inches relative to the row box, fixed at
    measure time: a later height-only shrink of the row (see :meth:`_flow`)
    never changes them, only the row's rendered height.
    """

    left_offset: float
    width: float
    elements: list[Tag]


@dataclass(frozen=True)
class _Region:
    """A rectangle of the slide that hosts a vertical flow of blocks."""

    box: Box
    elements: list[Tag]
    anchor: str = "top"


@dataclass(frozen=True)
class _Para:
    """One paragraph: a style, a nesting level and a list of styled runs."""

    style: TextStyle
    runs: list[tuple[str, TextStyle]]
    level: int = 0


@dataclass(frozen=True)
class _ColumnBasis:
    """A column's parsed CSS width hint: either a fixed share, or a grow factor."""

    fraction: float | None = None
    """Explicit width as a fraction (0-1) of the row's available width."""

    pixels: float | None = None
    """Explicit width in CSS pixels, takes priority over ``fraction`` when set."""

    grow: float = 1.0
    """``flex-grow`` factor used to fair-share the leftover space."""

    @property
    def is_explicit(self) -> bool:
        """Tell whether this column carries a resolvable fixed width."""
        return self.fraction is not None or self.pixels is not None


def _column_basis(props: dict[str, str]) -> _ColumnBasis:
    """Parse a column's width hint from its CSS declarations.

    Reads, in order: the ``flex`` shorthand's basis part (``flex:0 0 58%`` /
    ``...58px``), then a bare ``flex-basis``, then a plain CSS ``width``. A
    bare ``flex:1`` (or no hint at all) carries no explicit width: the caller
    fair-shares the leftover space by ``grow``, mirroring the browser's own
    ``flex:1`` behaviour. This mirrors the CSS trend already used across the
    codebase's flex rows (see ``_is_inline_gantt_row``'s ``flex:0 0 158px``
    label cells) generalized to percentages, the shape real decks use for
    side-by-side content.
    """
    flex = props.get("flex", "").strip()
    grow = 1.0
    basis_text = ""
    if flex:
        match = _FLEX_SHORTHAND_RE.match(flex)
        if match:
            grow = float(match.group(1))
            basis_text = (match.group(3) or "").strip()
    if not basis_text:
        basis_text = props.get("flex-basis", "").strip() or props.get("width", "").strip()
    if "%" in basis_text:
        return _ColumnBasis(fraction=parse_pct(basis_text) / 100.0, grow=0.0)
    px = parse_px(basis_text)
    if px:
        return _ColumnBasis(pixels=px, grow=0.0)
    return _ColumnBasis(grow=grow)


def _column_widths(res: StyleResolver, columns: list[Tag], width: float, gap: float) -> list[float] | None:
    """Resolve each column's width in inches, fair-sharing the leftover space.

    Returns ``None`` when not a single column carries any explicit width hint
    (``flex``, ``flex-basis`` or ``width``): a flex row with zero sizing
    information on every child is indistinguishable from an ordinary block
    stack, so the caller falls back to the regular vertical flow instead of
    guessing equal columns for content that was never meant to be columnar.
    """
    total_gap = gap * max(len(columns) - 1, 0)
    available = max(width - total_gap, 0.01)
    bases = [_column_basis(res.props(column)) for column in columns]
    if not any(basis.is_explicit for basis in bases):
        return None
    fixed_total = sum(basis.pixels * PX_IN if basis.pixels else (basis.fraction or 0.0) * available for basis in bases)
    remaining = max(available - fixed_total, 0.0)
    grow_total = sum(basis.grow for basis in bases if not basis.is_explicit)
    widths: list[float] = []
    for basis in bases:
        if basis.pixels:
            widths.append(max(basis.pixels * PX_IN, 0.2))
        elif basis.fraction is not None:
            widths.append(max(basis.fraction * available, 0.2))
        elif grow_total > 0:
            widths.append(max(remaining * basis.grow / grow_total, 0.2))
        else:
            widths.append(0.2)
    return widths


# ---------------------------------------------------------------------------
# Builder base
# ---------------------------------------------------------------------------


class _BuilderBase:
    """State shared by the slide builder and its mixins."""

    ctx: _Context
    res: StyleResolver
    theme: Theme
    slide: Any
    article: Tag
    index: int
    handled: set[int]
