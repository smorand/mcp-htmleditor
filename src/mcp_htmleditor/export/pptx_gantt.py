"""Gantt rendering of the PPTX slide builder.

``GanttMixin`` draws a Gantt chart: head, task bars, legend, and inline gantt detection.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from bs4 import Tag
from pptx.enum.shapes import MSO_SHAPE

from .pptx_components import (
    GANTT_DATES_PX,
    GANTT_LABEL_PX,
    GanttRow,
    gantt_geometry,
    gantt_period,
    gantt_task_band,
)
from .pptx_model import (
    _PX_FLEX_BASIS_RE,
    _BuilderBase,
    _Para,
)
from .pptx_style import (
    PX_IN,
    Box,
    TextStyle,
    has_class,
    parse_pct,
    parse_px,
    style_props,
)


class GanttMixin(_BuilderBase):
    """Gantt rendering of the slide builder."""

    def _render_gantt(self, box: Box, element: Tag) -> None:
        """Render a Gantt chart as real bars on a quarter ruled track."""
        rows = self._gantt_rows(element)
        legend = element.find(class_="gantt-legend") or self._inline_gantt_legend(element)
        legend_h = self._gantt_legend_height(legend, box.width) if isinstance(legend, Tag) else 0.0
        head_h = 24.0 * PX_IN
        label_w = min(GANTT_LABEL_PX * PX_IN, box.width * 0.3)
        dates_w = (
            min(GANTT_DATES_PX * PX_IN, box.width * 0.16) if element.find(class_="gantt-dates") is not None else 0.0
        )
        track_x = box.left + label_w
        track_w = max(box.width - label_w - dates_w, 0.5)
        rows_h = max(box.height - head_h - legend_h, 0.3)
        natural_h = [row.track_h_px or 30.0 for row in rows] or [30.0]
        scale = rows_h / (sum(natural_h) * PX_IN)
        row_heights = [h * PX_IN * scale for h in natural_h]

        self._render_gantt_head(element, Box(track_x, box.top, track_w, head_h))
        track_top = box.top + head_h
        self._rect(
            Box(track_x, track_top, track_w, rows_h),
            fill=self.theme.surface,
            line=self.theme.border,
        )
        for index in (25.0, 50.0, 75.0):
            x = track_x + track_w * index / 100.0
            self._rect(Box(x, track_top, 1.0 * PX_IN, rows_h), fill=self.theme.border)

        period = gantt_period(element, rows)
        top = track_top
        for row, row_h in zip(rows, row_heights, strict=True):
            if row.label is not None:
                self._render_text(Box(box.left, top, label_w - 0.08, row_h), row.label, anchor="middle")
            for marker in row.markers:
                marker_left_pct = parse_pct(style_props(marker).get("left", ""))
                marker_color = self._element_color(marker) or self.theme.border
                self._rect(
                    Box(track_x + track_w * marker_left_pct / 100.0, top, 1.2 * PX_IN, row_h),
                    fill=marker_color,
                )
            for task in row.tasks:
                left_pct, width_pct = gantt_geometry(task, period)
                top_pct, height_pct = gantt_task_band(task, row.track_h_px)
                bar = Box(
                    track_x + track_w * left_pct / 100.0,
                    top + row_h * top_pct / 100.0,
                    max(track_w * width_pct / 100.0, 0.12),
                    max(row_h * height_pct / 100.0, 0.06),
                )
                color = self._element_color(task) or self.theme.primary
                hatched = "repeating-linear-gradient" in style_props(task).get("background-image", "")
                self._rect(bar, fill=color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius_px=3, hatch=hatched)
                text = task.get_text(" ", strip=True) or str(task.get("data-label") or "")
                if text:
                    label, style = self._fit_bar_label(text, bar)
                    _, frame = self._textbox(bar.inset(0.06, 0.0), anchor="middle", wrap=False)
                    self._write(frame, [_Para(style, [(label, style)])])
            if row.dates is not None:
                self._render_text(
                    Box(track_x + track_w + 0.06, top, max(dates_w - 0.06, 0.3), row_h),
                    row.dates,
                    anchor="middle",
                )
            top += row_h
        if isinstance(legend, Tag):
            self._render_gantt_legend(Box(box.left, box.bottom - legend_h, box.width, legend_h), legend)

    @staticmethod
    def _fit_bar_label(text: str, bar: Box) -> tuple[str, TextStyle]:
        """Pick a font size (then truncate) so a bar label stays on one line.

        A short sub-lane bar in a dense roadmap is often narrower than its
        full label at any readable size (the source CSS relies on the
        browser's own text overflow clipping, which PPTX has no equivalent
        of): shrink down to a 5.5pt floor first, matching the template's own
        ``font-size:5.5px`` convention for these bars, then truncate with an
        ellipsis rather than let python-pptx's ``word_wrap`` push the
        overflow outside the shape, which renders as illegible ghost text
        over the neighbouring rows.
        """
        usable_w_pt = max((bar.width - 0.12) * 72.0, 4.0)
        for size in (9.5, 8.0, 6.5, 5.5):
            if len(text) * size * 0.5 <= usable_w_pt:
                return text, TextStyle(size=size, bold=True, color="FFFFFF", space_after=0)
        size = 5.5
        max_chars = max(int(usable_w_pt / (size * 0.5)), 1)
        if max_chars >= len(text):
            return text, TextStyle(size=size, bold=True, color="FFFFFF", space_after=0)
        truncated = text[: max(max_chars - 1, 1)].rstrip() + "…"
        return truncated, TextStyle(size=size, bold=True, color="FFFFFF", space_after=0)

    def _render_gantt_head(self, element: Tag, box: Box) -> None:
        """Render the period scale of a Gantt chart above the track."""
        head = element.find(class_="gantt-head") or element.find(class_="gantt-scale")
        if isinstance(head, Tag):
            track = head.find(class_="gantt-track")
            cells = (
                self._children(track)
                if isinstance(track, Tag)
                else [cell for cell in self._children(head) if not has_class(cell, "gantt-label-col")]
            )
            self._render_gantt_head_cells(box, [cell for cell in cells if cell.get_text(strip=True)])
            return
        inline_head = self._inline_gantt_sibling(
            element, lambda row: parse_px(style_props(row).get("margin-left", "")) > 0.0
        )
        if isinstance(inline_head, Tag):
            cells = [cell for cell in self._children(inline_head) if cell.get_text(strip=True)]
            self._render_gantt_head_cells(box, cells)

    def _render_gantt_head_cells(self, box: Box, cells: list[Tag]) -> None:
        """Lay out the period cells of a Gantt head at equal width across ``box``."""
        if not cells:
            return
        cell_w = box.width / len(cells)
        for index, cell in enumerate(cells):
            style = replace(
                self.res.style(cell),
                align="center",
                size=10.5,
                bold=True,
                color="secondary",
            )
            self._render_text(
                Box(box.left + index * cell_w, box.top, cell_w, box.height),
                cell,
                style=style,
                anchor="middle",
            )

    @staticmethod
    def _inline_gantt_sibling(element: Tag, predicate: Callable[[Tag], bool]) -> Tag | None:
        """Find the sibling of a custom inline Gantt's row stack matching ``predicate``.

        The header row (month cells) and the legend row sit as siblings of the
        row-stack container inside their common parent (e.g. ``.slide-body``),
        not as children of it: the row stack is only ``flex:1;overflow-y:auto``
        wrapping the lanes, so both must be looked up on the parent.
        """
        parent = element.parent
        if not isinstance(parent, Tag):
            return None
        for sibling in parent.find_all(True, recursive=False):
            if isinstance(sibling, Tag) and sibling is not element and predicate(sibling):
                return sibling
        return None

    def _render_gantt_legend(self, box: Box, legend: Tag) -> None:
        """Render the color legend of a Gantt chart: swatches, then marker keys.

        Two entry kinds coexist in both the documented ``gantt-legend`` shape
        and the custom inline one: a color-swatch entry (lane category) and a
        marker-key entry (a thin vertical bar, matching a milestone line drawn
        in the track). The HTML visually separates the marker-key group with a
        leading border; entries are laid out in two left-aligned rows so that
        separation survives the export instead of forcing every entry into one
        equal-width row (which would also make a long label collide with the
        next swatch on a busy legend such as the client's 15-entry one).
        """
        entries = [entry for entry in self._children(legend) if entry.get_text(strip=True)]
        if not entries:
            return
        swatch_entries = [entry for entry in entries if not self._is_marker_legend_entry(entry)]
        marker_entries = [entry for entry in entries if self._is_marker_legend_entry(entry)]
        groups = [group for group in (swatch_entries, marker_entries) if group]
        style = TextStyle(size=9.0, color="secondary", space_after=0)
        wrapped = [self._wrap_legend_entries(group, box.width, style) for group in groups]
        line_count = sum(len(lines) for lines in wrapped) or 1
        line_h = box.height / line_count
        top = box.top
        for lines in wrapped:
            for line in lines:
                self._render_gantt_legend_row(Box(box.left, top, box.width, line_h), line, style)
                top += line_h

    def _wrap_legend_entries(self, entries: list[Tag], width: float, style: TextStyle) -> list[list[Tag]]:
        """Split legend entries into lines that fit ``width``, greedy left to right."""
        lines: list[list[Tag]] = [[]]
        cursor = 0.0
        for entry in entries:
            entry_w = self._legend_entry_width(entry, style)
            if cursor + entry_w > width and lines[-1]:
                lines.append([])
                cursor = 0.0
            lines[-1].append(entry)
            cursor += entry_w
        return [line for line in lines if line]

    def _legend_entry_width(self, entry: Tag, style: TextStyle) -> float:
        """Estimate the rendered width of one legend entry (swatch plus label)."""
        swatch_w = 0.0
        if self._legend_swatch(entry) is not None:
            swatch_w = (3.0 if self._is_marker_legend_entry(entry) else 11.0) * PX_IN + 0.06
        text = entry.get_text(" ", strip=True)
        text_w = len(text) * style.size * PX_IN * 1.05
        return swatch_w + text_w + 0.2

    def _render_gantt_legend_row(self, box: Box, entries: list[Tag], style: TextStyle) -> None:
        """Render one line of legend entries at their natural (unequal) width."""
        cursor = box.left
        gap = 0.16
        for entry in entries:
            swatch = self._legend_swatch(entry)
            text = entry.get_text(" ", strip=True)
            if isinstance(swatch, Tag):
                color = self._element_color(swatch) or self.theme.primary
                marker = self._is_marker_legend_entry(entry)
                swatch_w = 3.0 * PX_IN if marker else 11.0 * PX_IN
                hatched = "repeating-linear-gradient" in style_props(swatch).get("background-image", "")
                self._rect(
                    Box(cursor, box.top + (box.height - 11.0 * PX_IN) / 2.0, swatch_w, 11.0 * PX_IN),
                    fill=color,
                    hatch=hatched,
                )
                swatch.extract()
                cursor += swatch_w + 0.06
            text_w = max(len(text) * style.size * PX_IN * 1.05, 0.3)
            self._render_text(Box(cursor, box.top, text_w, box.height), entry, style=style, anchor="middle")
            cursor += text_w + gap

    @staticmethod
    def _legend_swatch(entry: Tag) -> Tag | None:
        """Return the swatch element of a legend entry: ``<i>`` or a swatch ``<span>``."""
        swatch = entry.find("i")
        if isinstance(swatch, Tag):
            return swatch
        for span in entry.find_all("span", recursive=False):
            if isinstance(span, Tag) and not span.get_text(strip=True):
                return span
        return None

    def _is_marker_legend_entry(self, entry: Tag) -> bool:
        """Tell a milestone marker-key entry (thin vertical bar) from a color swatch.

        The HTML draws a marker key as a 1-2px wide, taller bar instead of the
        wider, shorter rounded rectangle used for lane categories; a leading
        ``border-left`` on the entry itself is the other tell used in the
        client deck, kept as a secondary signal since a future author could
        drop it.
        """
        swatch = self._legend_swatch(entry)
        if isinstance(swatch, Tag):
            props = style_props(swatch)
            width_px = parse_px(props.get("width", ""))
            height_px = parse_px(props.get("height", ""))
            if width_px and height_px:
                return width_px <= 3.0 and height_px > width_px
        return "border-left" in style_props(entry)

    def _inline_gantt_legend(self, element: Tag) -> Tag | None:
        """Find the legend row of a custom inline Gantt, if any.

        The legend is not marked with ``gantt-legend``: it is the sibling flex
        row after the row stack (see :meth:`_inline_gantt_sibling`), wrapping
        (``flex-wrap:wrap``) entries that are themselves flex rows with a
        swatch ``<span>`` plus a label.
        """

        def _is_legend(candidate: Tag) -> bool:
            if style_props(candidate).get("flex-wrap") != "wrap":
                return False
            entries = self._children(candidate)
            return bool(entries) and all(self._legend_swatch(entry) is not None for entry in entries)

        return self._inline_gantt_sibling(element, _is_legend)

    def _is_inline_gantt(self, element: Tag) -> bool:
        """Structurally detect a custom inline-styled Gantt (no CSS classes).

        Recognizes a container whose direct children are at least two row-like
        divs (see :meth:`_is_inline_gantt_row`): a fixed-width label cell
        followed by a ``position:relative`` track sibling holding absolutely
        positioned bars and/or milestone marker lines. Structural, not
        attribute-based, so it generalizes to any hand-authored deck sharing
        the shape without per-file markup changes.
        """
        if str(element.get("data-type") or "") or element.find(class_="gantt-row") is not None:
            return False
        rows = [child for child in self._children(element) if self._is_inline_gantt_row(child)]
        return len(rows) >= 2

    @staticmethod
    def _is_inline_gantt_row(row: Tag) -> bool:
        """Tell whether a div is one lane of a custom inline Gantt.

        Shape: a flex row (``display:flex``) whose first element child has a
        fixed ``flex-basis``/width (the label cell) and whose second element
        child is ``position:relative`` with ``flex:1`` (the track) and
        contains at least one absolutely positioned descendant (a bar or a
        marker line).
        """
        if row.name != "div":
            return False
        row_props = style_props(row)
        if row_props.get("display") != "flex":
            return False
        cells = [c for c in row.children if isinstance(c, Tag)]
        if len(cells) < 2:
            return False
        label_cell, track = cells[0], cells[1]
        label_props = style_props(label_cell)
        has_fixed_label = bool(_PX_FLEX_BASIS_RE.search(label_props.get("flex", ""))) or bool(
            parse_px(label_props.get("width", ""))
        )
        track_props = style_props(track)
        is_track = track_props.get("position") == "relative" and "1" in track_props.get("flex", "")
        if not (has_fixed_label and is_track):
            return False
        return any(style_props(c).get("position") == "absolute" for c in track.children if isinstance(c, Tag))

    def _inline_gantt_rows(self, element: Tag) -> list[GanttRow]:
        """Extract rows, tasks and milestone markers of a custom inline Gantt."""
        rows: list[GanttRow] = []
        for row in self._children(element):
            if not self._is_inline_gantt_row(row):
                continue
            cells = [c for c in row.children if isinstance(c, Tag)]
            label_cell, track = cells[0], cells[1]
            track_h_px = parse_px(style_props(row).get("min-height", "")) or parse_px(
                style_props(track).get("min-height", "")
            )
            tasks: list[Tag] = []
            markers: list[Tag] = []
            for child in track.children:
                if not isinstance(child, Tag) or style_props(child).get("position") != "absolute":
                    continue
                if child.get_text(strip=True):
                    tasks.append(child)
                else:
                    markers.append(child)
            rows.append(GanttRow(label=label_cell, dates=None, tasks=tasks, markers=markers, track_h_px=track_h_px))
        return rows

    def _gantt_rows(self, element: Tag) -> list[GanttRow]:
        """Extract the rows of a Gantt chart, with a flat task fallback."""
        rows: list[GanttRow] = []
        for row in element.find_all(class_="gantt-row"):
            tasks = [task for task in row.find_all(attrs={"data-type": "gantt-task"}) if isinstance(task, Tag)]
            label = row.find(class_="gantt-label")
            dates = row.find(class_="gantt-dates")
            rows.append(
                GanttRow(
                    label=label if isinstance(label, Tag) else None,
                    dates=dates if isinstance(dates, Tag) else None,
                    tasks=tasks,
                )
            )
        if rows:
            return rows
        rows = self._inline_gantt_rows(element)
        if rows:
            return rows
        for task in element.find_all(attrs={"data-type": "gantt-task"}):
            if isinstance(task, Tag):
                rows.append(GanttRow(label=None, dates=None, tasks=[task]))
        if not rows:
            self.ctx.report.warn('Gantt sans tache data-type="gantt-task": bloc ignore.')
        return rows
