"""Block measurement and renderers of the PPTX slide builder.

``BlocksMixin`` measures and draws panels, grids, tables, rules, bars and the block dispatcher.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import Any

from bs4 import Tag
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches

from .pptx_components import (
    TableGrid,
    color_of,
    set_cell_border,
)
from .pptx_model import (
    _NOTIF_VARIANTS,
    FILL_KEYS,
    SKIP_TAGS,
    TILE_CLASSES,
    _Block,
    _BuilderBase,
    _Para,
    _Region,
)
from .pptx_style import (
    PX_IN,
    SLIDE_H_IN,
    Box,
    TextStyle,
    classes,
    has_class,
    parse_length,
    parse_pct,
    parse_px,
    style_props,
)


class BlocksMixin(_BuilderBase):
    """Block measurement and rendering of the slide builder."""

    def _panel_block(self, element: Tag, width: float) -> _Block:
        """Measure a decorated panel: text plus its padding and accent bar."""
        style = self.res.style(element)
        height = self._text_height(element, width - 0.32, style) + 0.3
        return _Block("panel", element, max(height, 0.4))

    def _grid_block(self, element: Tag, width: float) -> _Block:
        """Measure a tile grid: rows of equal height cells."""
        cells = self._children(element)
        if not cells:
            return _Block("grid", element, 0.05)
        cols = self._grid_columns(element, len(cells))
        gap = 14.0 * PX_IN
        cell_w = max((width - gap * (cols - 1)) / cols, 0.4)
        cell_h = 0.0
        for cell in cells:
            style = self.res.style(cell)
            cell_h = max(cell_h, self._text_height(cell, cell_w - 0.28, style) + 0.24)
        rows = math.ceil(len(cells) / cols)
        natural = rows * cell_h + (rows - 1) * gap + 0.1
        return _Block(
            "grid",
            element,
            natural,
            min_height=natural * 0.85,
            max_height=natural * 1.7,
            flexible=True,
        )

    @staticmethod
    def _grid_columns(element: Tag, count: int) -> int:
        """Number of columns of a grid, from its ``cols-N`` class."""
        for name in classes(element):
            match = re.fullmatch(r"cols-(\d)", name)
            if match:
                return int(match.group(1))
        if has_class(element, "stat-grid"):
            return 3
        if has_class(element, "mention-wrap"):
            return min(3, max(count, 1))
        return min(count, 3) or 1

    def _table_block(self, element: Tag, width: float) -> _Block:
        """Measure a table from its own cell contents."""
        grid = TableGrid(element)
        if not grid.rows:
            return _Block("text", element, 0.05)
        widths = grid.column_widths(width)
        height = 0.0
        for row_index, row in enumerate(grid.rows):
            # PPTX rows never shrink below their text, so keep a safety margin.
            row_h = 0.3 if row_index in grid.header_rows else 0.34
            for cell in row:
                if cell is None or cell.origin != row_index:
                    continue
                style = self.res.style(cell.element)
                cell_w = sum(widths[cell.column : cell.column + cell.colspan]) - 0.18
                row_h = max(row_h, self._text_height(cell.element, max(cell_w, 0.3), style) + 0.16)
            grid.row_heights.append(row_h)
            height += row_h
        natural = height + 0.06
        return _Block(
            "table",
            element,
            natural,
            min_height=natural,
            max_height=natural * 1.6,
            flexible=True,
        )

    def _gantt_block(self, element: Tag, width: float) -> _Block:
        """Measure a Gantt chart: one line per task, plus scale and legend."""
        rows = self._gantt_rows(element)
        row_h_px = sum((row.track_h_px or 30.0) for row in rows) or 30.0 * max(len(rows), 1)
        height = row_h_px * PX_IN + 24.0 * PX_IN
        legend = element.find(class_="gantt-legend") or self._inline_gantt_legend(element)
        if isinstance(legend, Tag):
            height += self._gantt_legend_height(legend, width)
            self._consume(legend)
        inline_head = self._inline_gantt_sibling(
            element, lambda row: parse_px(style_props(row).get("margin-left", "")) > 0.0
        )
        if inline_head is not None:
            self._consume(inline_head)
        return _Block("gantt", element, height, min_height=height * 0.6)

    def _gantt_legend_height(self, legend: Tag, width: float) -> float:
        """Measure the legend band height, counting wrapped lines on a busy legend."""
        entries = [entry for entry in self._children(legend) if entry.get_text(strip=True)]
        if not entries:
            return 26.0 * PX_IN
        style = TextStyle(size=9.0, color="secondary", space_after=0)
        swatch_entries = [entry for entry in entries if not self._is_marker_legend_entry(entry)]
        marker_entries = [entry for entry in entries if self._is_marker_legend_entry(entry)]
        groups = [group for group in (swatch_entries, marker_entries) if group]
        line_count = sum(len(self._wrap_legend_entries(group, width, style)) for group in groups) or 1
        return line_count * 20.0 * PX_IN

    def _arch_block(self, element: Tag, width: float) -> _Block:
        """Measure a diagram: fixed when the CSS gives a height, else flexible."""
        props = style_props(element)
        explicit = parse_length(props.get("height"), 0.0)
        if explicit and explicit > 0.2:
            return _Block("arch", element, explicit, min_height=explicit * 0.7)
        return _Block("arch", element, 2.6, min_height=1.6, flexible=True)

    def _annotated_block(self, element: Tag, width: float) -> _Block:
        """Measure an annotated image from the aspect ratio of its picture."""
        img = element.find("img")
        aspect = 16.0 / 9.0
        if isinstance(img, Tag):
            measured = self._image_aspect(str(img.get("src") or ""))
            if measured:
                aspect = measured
        img_w = min(width, self._max_width(element, width))
        return _Block("annotated-image", element, img_w / aspect, min_height=1.0)

    def _image_block(self, element: Tag, width: float) -> _Block:
        """Measure a standalone image."""
        props = style_props(element)
        aspect = self._image_aspect(str(element.get("src") or "")) or 16.0 / 9.0
        height = parse_length(props.get("height"), SLIDE_H_IN)
        img_w = parse_length(props.get("width"), width) or width
        img_w = min(img_w, width)
        return _Block("image", element, height or img_w / aspect)

    @staticmethod
    def _max_width(element: Tag, width: float) -> float:
        """Resolve the ``max-width`` of an element, defaulting to ``width``."""
        value = parse_length(style_props(element).get("max-width"), width)
        return value if value else width

    # -- block rendering ---------------------------------------------------

    def _render_block(self, block: _Block, box: Box) -> None:
        """Dispatch a measured block to its renderer."""
        if block.kind == "text":
            self._render_text(box, block.element, style=block.style)
        elif block.kind == "rule":
            self._render_rule(box, block.element)
        elif block.kind == "med-rule":
            self._render_med_rule(box, block.element)
        elif block.kind == "panel":
            self._render_panel(box, block.element)
        elif block.kind == "hbar":
            self._render_hbar(box, block.element)
        elif block.kind == "grid":
            self._render_grid(box, block.element)
        elif block.kind == "table":
            self._render_table(box, block.element)
        elif block.kind == "gantt":
            self._render_gantt(box, block.element)
        elif block.kind == "arch":
            self._render_arch(box, block.element)
        elif block.kind == "annotated-image":
            self._render_annotated_image(box, block.element)
        elif block.kind == "image":
            self._render_image(box, block.element)
        elif block.kind == "row":
            self._render_row(box, block)
        else:  # pragma: no cover - defensive, every kind is handled above
            self.ctx.report.warn(f"Composant non supporte ignore: {block.kind}")

    def _render_row(self, box: Box, block: _Block) -> None:
        """Render a flex row: flow each column independently in its own slot.

        The row's own height may have been grown or shrunk by the parent
        :meth:`_flow` (flexible blocks absorb free space or give theirs back
        on overflow); each column reuses that *same* final height as its own
        available space and runs the regular :meth:`_flow` recursively, so a
        column whose content still overflows its narrower width shrinks on
        its own instead of the whole row shrinking uniformly.
        """
        for column in block.columns or []:
            column_box = Box(box.left + column.left_offset, box.top, column.width, box.height)
            self._flow(_Region(column_box, column.elements))

    def _render_text(
        self,
        box: Box,
        element: Tag,
        style: TextStyle | None = None,
        anchor: str = "top",
    ) -> None:
        """Render the text content of an element inside ``box``."""
        base = style or self.res.style(element)
        paras = self._paragraphs(element, base)
        if not paras:
            return
        _, frame = self._textbox(box, anchor=anchor)
        self._write(frame, paras)

    def _render_rule(self, box: Box, element: Tag) -> None:
        """Render the short accent rule found under EI slide titles."""
        props = self.res.props(element)
        width = parse_length(props.get("width"), box.width) or 64.0 * PX_IN
        height = parse_length(props.get("height"), 0.0) or 3.0 * PX_IN
        color = color_of(props, FILL_KEYS, self.res)
        rule = Box(box.left, box.top + 12.0 * PX_IN, min(width, box.width), height)
        self._rect(rule, fill=color or self.theme.accent)

    def _render_med_rule(self, box: Box, element: Tag) -> None:
        """Render the two segment teal/orange rule of the medical charter.

        Geometry is fixed here rather than read from the CSS: the charter
        states it with tag selectors (``.med-rule i``) that the class based
        resolver does not index, and the rule is a charter signature, not a
        per slide decision.
        """
        segments = self._children(element)
        widths = (44.0, 34.0)
        # `.med-rule.light` is the variant used on the navy closing slide, where
        # the charter teal would be too dark to read (the CSS states it on the
        # `i` child, a tag selector the resolver does not index).
        teal = "7FD8C8" if has_class(element, "light") else self.theme.primary_alt
        colors = (teal, self.theme.accent)
        cursor = box.left
        top = box.top + 5.0 * PX_IN
        for index, segment in enumerate(segments[:2] or []):
            props = self.res.props(segment)
            width = parse_length(props.get("width"), box.width) or widths[index] * PX_IN
            height = parse_length(props.get("height"), 0.0) or 5.0 * PX_IN
            fill = color_of(props, FILL_KEYS, self.res) or colors[index]
            self._rect(Box(cursor, top, width, height), fill=fill)
            cursor += width + 4.0 * PX_IN

    def _render_panel(self, box: Box, element: Tag) -> None:
        """Render a callout or card: tinted panel, accent bar, then its text."""
        fill, bar, vertical = self._panel_colors(element)
        panel = Box(box.left, box.top, box.width, max(box.height - 0.06, 0.2))
        self._rect(panel, fill=fill, line=None if fill else self.theme.border)
        if bar and vertical:
            self._rect(Box(panel.left, panel.top, 4.0 * PX_IN, panel.height), fill=bar)
        elif bar:
            self._rect(Box(panel.left, panel.top, panel.width, 3.0 * PX_IN), fill=bar)
        inner = Box(panel.left + 0.17, panel.top + 0.08, panel.width - 0.3, panel.height - 0.14)
        if self._has_block_children(element) and any(
            self._is_panel(child) or child.name == "table" for child in self._children(element)
        ):
            self._flow(_Region(inner, self._children(element)))
        else:
            self._render_text(inner, element)

    def _panel_colors(self, element: Tag) -> tuple[str | None, str | None, bool]:
        """Resolve the (fill, accent bar, bar is vertical) look of a panel."""
        props = self.res.props(element)
        fill = color_of(props, FILL_KEYS, self.res)
        left_bar = color_of(props, ("border-left-color", "border-left"), self.res)
        top_bar = color_of(props, ("border-top-color", "border-top"), self.res)
        for variant, colors in _NOTIF_VARIANTS.items():
            if has_class(element, "cds-notification") and has_class(element, variant):
                return colors[0], colors[1], True
        if has_class(element, "cds-notification"):
            default_fill = "FFF6E6" if self.theme.key == "ei" else "EDF5FF"
            accent = self.theme.accent if self.theme.key == "ei" else self.theme.primary
            return fill or default_fill, left_bar or accent, True
        if left_bar:
            return fill or self.theme.surface, left_bar, True
        if top_bar:
            return fill or self.theme.surface, top_bar, False
        return fill or self.theme.surface, None, True

    def _render_hbar(self, box: Box, element: Tag) -> None:
        """Render a proportional horizontal bar such as a context window chart."""
        segments = [seg for seg in self._children(element) if seg.name not in SKIP_TAGS]
        if not segments:
            return
        weights: list[float] = []
        for segment in segments:
            declared = parse_pct(style_props(segment).get("width", ""))
            weights.append(declared if declared > 0 else 0.0)
        known = sum(weights)
        unknown = [i for i, w in enumerate(weights) if w == 0.0]
        for index in unknown:
            weights[index] = max((100.0 - known) / len(unknown), 2.0)
        total = sum(weights) or 100.0
        cursor = box.left
        bar = Box(box.left, box.top, box.width, max(box.height - 0.08, 0.16))
        for segment, weight in zip(segments, weights, strict=True):
            width = bar.width * weight / total
            fill = self._element_color(segment) or self.theme.primary
            cell = Box(cursor, bar.top, max(width, 0.04), bar.height)
            self._rect(cell, fill=fill)
            text = segment.get_text(" ", strip=True)
            if text and width > 0.3:
                style = replace(self.res.style(segment), size=9.0, bold=True, align="center", space_after=0)
                _, frame = self._textbox(cell, anchor="middle")
                self._write(frame, [_Para(style, [(text, style)])])
            cursor += width

    def _render_grid(self, box: Box, element: Tag) -> None:
        """Render a grid of tiles, stat cards or pills."""
        cells = self._children(element)
        if not cells:
            return
        cols = self._grid_columns(element, len(cells))
        gap = 14.0 * PX_IN
        rows = math.ceil(len(cells) / cols)
        cell_w = max((box.width - gap * (cols - 1)) / cols, 0.4)
        cell_h = max((box.height - gap * (rows - 1) - 0.1) / rows, 0.3)
        for position, cell in enumerate(cells):
            row, col = divmod(position, cols)
            cell_box = Box(
                box.left + col * (cell_w + gap),
                box.top + row * (cell_h + gap),
                cell_w,
                cell_h,
            )
            self._render_cell(cell_box, cell)

    def _render_cell(self, box: Box, cell: Tag) -> None:
        """Render one grid cell: decorated tile, nested blocks or plain text."""
        if has_class(cell, *TILE_CLASSES) or self._is_panel(cell):
            self._render_panel(box, cell)
            return
        if self._has_block_children(cell):
            self._flow(_Region(box, self._children(cell)))
            return
        self._render_text(box, cell)

    def _render_table(self, box: Box, element: Tag) -> None:
        """Render an HTML table as a native PPTX table with merges and styling."""
        grid = TableGrid(element)
        if not grid.rows:
            return
        widths = grid.column_widths(box.width)
        shape = self.slide.shapes.add_table(
            len(grid.rows), grid.column_count, *Box(box.left, box.top, box.width, box.height).emu()
        )
        table = shape.table
        table.first_row = bool(grid.header_rows)
        table.horz_banding = False
        for index, width in enumerate(widths):
            table.columns[index].width = Inches(width)
        heights = grid.row_heights or [box.height / len(grid.rows)] * len(grid.rows)
        scale = box.height / max(sum(heights), 0.01)
        for index, height in enumerate(heights):
            table.rows[index].height = Inches(height * scale)

        striped = str(element.get("data-style") or "") == "striped"
        for r_index, row in enumerate(grid.rows):
            is_header = r_index in grid.header_rows
            for c_index, cell in enumerate(row):
                if cell is None or cell.origin != r_index or cell.column != c_index:
                    continue
                target = table.cell(r_index, c_index)
                if cell.colspan > 1 or cell.rowspan > 1:
                    end_row = min(r_index + cell.rowspan - 1, len(grid.rows) - 1)
                    end_col = min(c_index + cell.colspan - 1, grid.column_count - 1)
                    target.merge(table.cell(end_row, end_col))
                self._fill_table_cell(target, cell.element, is_header, striped and r_index % 2 == 0)
                if not is_header and r_index < len(grid.rows) - 1:
                    set_cell_border(target, "B", self.theme.border)

    def _fill_table_cell(self, target: Any, element: Tag, header: bool, striped: bool) -> None:
        """Write and style one table cell."""
        target.margin_left = Inches(0.07)
        target.margin_right = Inches(0.07)
        target.margin_top = Inches(0.03)
        target.margin_bottom = Inches(0.03)
        target.vertical_anchor = MSO_ANCHOR.MIDDLE
        if header:
            target.fill.solid()
            target.fill.fore_color.rgb = RGBColor.from_string(self.theme.table_header_bg)
        elif striped:
            target.fill.solid()
            target.fill.fore_color.rgb = RGBColor.from_string(self.theme.surface)
        else:
            target.fill.background()
        default = self.res.style(element)
        if header:
            default = replace(default, color=self.theme.table_header_fg, bold=True)
        paras = self._paragraphs(element, default)
        frame = target.text_frame
        frame.word_wrap = True
        self._write(frame, paras or [_Para(default, [("", default)])])
