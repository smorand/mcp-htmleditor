"""Pure helpers shared by the PPTX exporter.

Everything here is independent from the slide builder: Gantt period maths,
the HTML table occupancy grid (``colspan`` / ``rowspan``), CSS transform
composition and the few low level python-pptx utilities that the library does
not expose (table cell borders, EMU conversion).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bs4 import Tag
from pptx.oxml.ns import qn

from .pptx_style import (
    PX_IN,
    Box,
    StyleResolver,
    TextStyle,
    has_class,
    parse_color,
    parse_pct,
    parse_px,
    style_props,
)

_MONTH_RE = re.compile(r"(\d{4})-(\d{1,2})")

GANTT_LABEL_PX = 165.0
"""Width of the task label column of a Gantt chart, in CSS pixels."""

GANTT_DATES_PX = 112.0
"""Width of the optional trailing date column of a Gantt chart, in pixels."""


# ---------------------------------------------------------------------------
# Gantt helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GanttRow:
    """One Gantt line: its label, its optional date column and its bars."""

    label: Tag | None
    dates: Tag | None
    tasks: list[Tag]


def month_index(value: str | None) -> int | None:
    """Convert a ``YYYY-MM`` string to an absolute month index."""
    match = _MONTH_RE.search(str(value or ""))
    if not match:
        return None
    return int(match.group(1)) * 12 + int(match.group(2)) - 1


def gantt_period(element: Tag, rows: list[GanttRow]) -> tuple[int, int]:
    """Return the (first month, month count) range covered by a chart."""
    start = month_index(element.get("data-period-start"))
    end = month_index(element.get("data-period-end"))
    starts = [m for m in (month_index(t.get("data-start")) for row in rows for t in row.tasks) if m]
    ends = [m for m in (month_index(t.get("data-end")) for row in rows for t in row.tasks) if m]
    first = start if start is not None else (min(starts) if starts else 0)
    last = end if end is not None else (max(ends) if ends else first + 11)
    return first, max(last - first + 1, 1)


def gantt_geometry(task: Tag, period: tuple[int, int]) -> tuple[float, float]:
    """Return the (left %, width %) of a task bar inside its track.

    Inline ``left`` / ``margin-left`` and ``width`` win, because they are what
    the browser actually renders; ``data-start`` / ``data-end`` are the
    fallback for markup written without positioning.
    """
    props = style_props(task)
    left = props.get("left") or props.get("margin-left")
    if left and "%" in left and "width" in props and "%" in props["width"]:
        return parse_pct(left), parse_pct(props["width"])
    first, span = period
    start = month_index(task.get("data-start"))
    end = month_index(task.get("data-end"))
    if start is None:
        return 0.0, 100.0
    end = end if end is not None else start
    return (start - first) / span * 100.0, max((end - start + 1) / span * 100.0, 2.0)


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableCell:
    """A table cell projected on the occupancy grid."""

    element: Tag
    origin: int
    column: int
    colspan: int
    rowspan: int


class TableGrid:
    """Occupancy grid of an HTML table, resolving ``colspan`` and ``rowspan``."""

    def __init__(self, element: Tag) -> None:
        self.element = element
        self.rows: list[list[TableCell | None]] = []
        self.header_rows: set[int] = set()
        self.row_heights: list[float] = []
        self._build()
        self.column_count = max((len(row) for row in self.rows), default=0)
        for row in self.rows:
            row.extend([None] * (self.column_count - len(row)))

    def _build(self) -> None:
        """Fill the grid, expanding spans over the cells they cover."""
        html_rows = [row for row in self.element.find_all("tr") if isinstance(row, Tag)]
        for r_index, row in enumerate(html_rows):
            cells = [c for c in row.find_all(["td", "th"], recursive=False) if isinstance(c, Tag)]
            if cells and all(c.name == "th" for c in cells):
                self.header_rows.add(r_index)
            while len(self.rows) <= r_index:
                self.rows.append([])
            grid_row = self.rows[r_index]
            column = 0
            for cell in cells:
                while column < len(grid_row) and grid_row[column] is not None:
                    column += 1
                colspan = positive_int(cell.get("colspan"))
                rowspan = positive_int(cell.get("rowspan"))
                entry = TableCell(cell, r_index, column, colspan, rowspan)
                for dr in range(rowspan):
                    while len(self.rows) <= r_index + dr:
                        self.rows.append([])
                    target = self.rows[r_index + dr]
                    for dc in range(colspan):
                        index = column + dc
                        while len(target) <= index:
                            target.append(None)
                        target[index] = entry
                column += colspan

    def column_widths(self, total: float) -> list[float]:
        """Resolve column widths from ``colgroup``, else split the free space.

        Numbering columns (``td.num``, used by the agenda lists) keep the fixed
        width of the templates instead of taking an even share.
        """
        if self.column_count == 0:
            return []
        declared = self._declared_weights()
        if declared:
            scale = total / sum(declared)
            return [weight * scale for weight in declared]
        fixed = [self._fixed_width(index) for index in range(self.column_count)]
        free = max(total - sum(w for w in fixed if w), 0.5)
        flexible = max(sum(1 for w in fixed if w is None), 1)
        return [width if width else free / flexible for width in fixed]

    def _fixed_width(self, index: int) -> float | None:
        """Return the pixel width declared on a column, or ``None``.

        Narrow numbering columns (``td.num`` or an inline ``width`` in pixels on
        the first row) keep the width of the template instead of an even share.
        """
        for row in self.rows:
            cell = row[index] if index < len(row) else None
            if cell is None or cell.column != index:
                continue
            if has_class(cell.element, "num"):
                return 56.0 * PX_IN
            declared = parse_px(style_props(cell.element).get("width", ""))
            if declared:
                return declared * PX_IN
        return None

    def _declared_weights(self) -> list[float]:
        """Return the ``colgroup`` widths of the table, empty when unusable."""
        weights: list[float] = []
        colgroup = self.element.find("colgroup")
        if isinstance(colgroup, Tag):
            for col in colgroup.find_all("col"):
                weights.append(
                    parse_pct(style_props(col).get("width", ""))
                    or to_float(col.get("data-col-width"))
                )
        if len(weights) != self.column_count or sum(weights) <= 0 or min(weights) <= 0:
            return []
        return weights


def positive_int(value: Any) -> int:
    """Parse a span attribute, clamped to at least 1."""
    try:
        return max(int(str(value)), 1)
    except (TypeError, ValueError):
        return 1


def to_float(value: Any) -> float:
    """Parse a numeric attribute, 0.0 when absent or invalid."""
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def first_pct(*values: Any, default: float = 0.0) -> float:
    """Return the first parsable percentage among ``values``."""
    for value in values:
        if value is None:
            continue
        text = str(value)
        if "%" in text:
            return parse_pct(text)
        try:
            return float(text)
        except ValueError:
            continue
    return default


def apply_transform(box: Box, props: dict[str, str]) -> Box:
    """Apply CSS ``translate`` percentages of the element own size to a box."""
    transform = props.get("transform", "")
    if not transform:
        return box
    dx = dy = 0.0
    for axis, values in re.findall(r"translate([XY]?)\(([^)]*)\)", transform):
        parts = [p.strip() for p in values.split(",")]
        if axis == "X":
            dx = parse_pct(parts[0]) / 100.0 * box.width
        elif axis == "Y":
            dy = parse_pct(parts[0]) / 100.0 * box.height
        else:
            dx = parse_pct(parts[0]) / 100.0 * box.width
            if len(parts) > 1:
                dy = parse_pct(parts[1]) / 100.0 * box.height
    return box.offset(dx, dy)


def color_of(props: dict[str, str], keys: tuple[str, ...], res: StyleResolver) -> str | None:
    """Return the first resolvable color among ``keys`` of a declaration dict."""
    for key in keys:
        color = parse_color(props.get(key), res.css_vars)
        if color:
            return color
    return None


def is_light(color: str) -> bool:
    """Tell whether an ``RRGGBB`` color is light (perceived luminance)."""
    red, green, blue = (int(color[index : index + 2], 16) for index in (0, 2, 4))
    return (0.299 * red + 0.587 * green + 0.114 * blue) > 140.0


def inches(emu: int) -> float:
    """Convert an EMU length to inches."""
    return float(emu) / 914400.0


def drop_theme_style(shape: Any) -> None:
    """Detach an auto shape from the theme style of the default template.

    python-pptx adds a ``<p:style>`` reference that pulls the theme accent fill,
    outline and drop shadow. Every shape of the export sets its own fill and
    line, so the reference is removed to avoid unwanted shadows.
    """
    shape.shadow.inherit = False
    element = shape._element
    style = element.find(qn("p:style"))
    if style is not None:
        element.remove(style)


def set_cell_border(cell: Any, edge: str, color: str, width_pt: float = 0.75) -> None:
    """Draw one border of a table cell.

    python-pptx exposes no border API, so the ``a:lnB`` / ``a:lnT`` elements are
    written directly. They must precede the fill element of ``a:tcPr``.
    """
    properties = cell._tc.get_or_add_tcPr()
    tag = qn(f"a:ln{edge}")
    for existing in properties.findall(tag):
        properties.remove(existing)
    line = properties.makeelement(
        tag, {"w": str(int(width_pt * 12700)), "cap": "flat", "cmpd": "sng", "algn": "ctr"}
    )
    solid = line.makeelement(qn("a:solidFill"), {})
    solid.append(solid.makeelement(qn("a:srgbClr"), {"val": color}))
    line.append(solid)
    properties.insert(0, line)


def split_runs(
    runs: list[tuple[str, TextStyle]],
) -> list[list[tuple[str, TextStyle]]]:
    """Split runs on hard line breaks so each chunk is one PPTX paragraph."""
    chunks: list[list[tuple[str, TextStyle]]] = [[]]
    for text, style in runs:
        pieces = text.split("\n")
        for index, piece in enumerate(pieces):
            if index:
                chunks.append([])
            if piece:
                chunks[-1].append((piece, style))
    return [chunk for chunk in chunks if chunk] or [[]]
