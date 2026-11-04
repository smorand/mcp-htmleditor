"""Block flow and flex row logic of the PPTX slide builder.

``FlowMixin`` walks the slide subtree into blocks, stacks them in their region
and holds the text block and height helpers the flow relies on.
"""

from __future__ import annotations

from bs4 import Tag

from .pptx_components import color_of
from .pptx_model import (
    BAR_KEYS,
    BLOCK_TAGS,
    FILL_KEYS,
    GRID_CLASSES,
    INLINE_BLOCK_CLASSES,
    INLINE_BLOCK_TAGS,
    SHELL_CLASSES,
    SKIP_TAGS,
    TILE_CLASSES,
    _Block,
    _BuilderBase,
    _Column,
    _column_widths,
    _Para,
    _Region,
)
from .pptx_style import PX_IN, Box, TextStyle, block_height, classes, has_class, parse_px, style_props


class FlowMixin(_BuilderBase):
    """Block flow and flex row logic of the slide builder."""

    def _flow(self, region: _Region) -> None:
        """Stack the blocks of a region, absorbing or shrinking extra space."""
        blocks = self._collect_all(region.elements, region.box.width)
        if not blocks:
            return
        available = region.box.height
        total = sum(b.height for b in blocks)
        flexible = [b for b in blocks if b.flexible]

        if total < available and flexible:
            free = available - total
            for index, block in enumerate(flexible):
                share = free / (len(flexible) - index)
                room = block.max_height - block.height if block.max_height else share
                grow = max(min(share, room), 0.0)
                block.height += grow
                free -= grow
        elif total > available:
            overflow = total - available
            for block in flexible:
                room = max(block.height - block.min_height, 0.0)
                take = min(room, overflow)
                block.height -= take
                overflow -= take
                if overflow <= 0.001:
                    break
            if overflow > 0.001:
                scale = available / (available + overflow)
                for block in blocks:
                    block.height *= scale

        cursor = region.box.top
        if region.anchor == "middle":
            used = sum(b.height for b in blocks)
            cursor += max((region.box.height - used) / 2.0, 0.0)
        for block in blocks:
            box = Box(region.box.left, cursor, region.box.width, block.height)
            self._render_block(block, box)
            cursor += block.height

    def _collect_all(self, elements: list[Tag], width: float) -> list[_Block]:
        """Collect the blocks of a list of sibling elements."""
        for element in elements:
            if isinstance(element, Tag) and self._is_inline_gantt(element):
                self._consume_inline_gantt_siblings(element)
        blocks: list[_Block] = []
        for element in elements:
            blocks.extend(self._collect(element, width))
        return blocks

    def _consume_inline_gantt_siblings(self, element: Tag) -> None:
        """Mark a custom inline Gantt's header/legend siblings as already rendered.

        Both live outside ``element`` (see :meth:`_inline_gantt_sibling`), so
        without this a sibling-order walk renders the header row as one huge
        text block (it comes first in the DOM) before ``_gantt_block`` ever
        gets a chance to claim it.
        """
        legend = self._inline_gantt_legend(element)
        if legend is not None:
            self._consume(legend)
        head = self._inline_gantt_sibling(element, lambda row: parse_px(style_props(row).get("margin-left", "")) > 0.0)
        if head is not None:
            self._consume(head)

    def _collect(self, element: Tag, width: float) -> list[_Block]:
        """Turn one element into zero, one or several layout blocks."""
        if not isinstance(element, Tag) or element.name in SKIP_TAGS:
            return []
        if id(element) in self.handled or has_class(element, *SHELL_CLASSES):
            return []
        if str(element.get("aria-hidden") or "") == "true":
            return []

        dtype = str(element.get("data-type") or "")
        if dtype == "gantt" or self._is_inline_gantt(element):
            return [self._gantt_block(element, width)]
        if dtype == "arch-diagram":
            return [self._arch_block(element, width)]
        if dtype == "annotated-image":
            return [self._annotated_block(element, width)]
        if dtype == "table" or element.name == "table":
            return [self._table_block(element, width)]
        if has_class(element, "cds-notification"):
            return [self._panel_block(element, width)]
        if has_class(element, *GRID_CLASSES):
            return [self._grid_block(element, width)]
        if has_class(element, "cw-bar"):
            return [_Block("hbar", element, 32.0 * PX_IN + 0.08)]
        if has_class(element, "med-rule"):
            return [_Block("med-rule", element, 16.0 * PX_IN)]
        if has_class(element, "slide-title-rule", "accent-line"):
            return [_Block("rule", element, 33.0 * PX_IN)]
        if element.name == "img":
            return [self._image_block(element, width)]
        if element.name == "hr":
            return [_Block("rule", element, 12.0 * PX_IN)]
        if self._is_panel(element):
            return [self._panel_block(element, width)]
        if element.name in {"ul", "ol"} or not self._has_block_children(element):
            return self._text_block(element, width)
        if self._is_flex_row(element):
            row = self._flex_row_block(element, width)
            if row is not None:
                return [row]
        return self._collect_all(self._children(element), width)

    def _is_flex_row(self, element: Tag) -> bool:
        """Structurally detect a ``display:flex`` row of 2+ side-by-side columns.

        A row is a flex container without an explicit ``flex-direction:
        column``/``column-reverse`` whose direct children are at least two
        block-level elements. This is deliberately the same structural,
        attribute-free detection style as :meth:`_is_inline_gantt`: any deck
        using a plain CSS flex row for side-by-side content is recognized,
        not just this one client slide.
        """
        props = self.res.props(element)
        if props.get("display") not in {"flex", "inline-flex"}:
            return False
        if props.get("flex-direction", "row").strip() in {"column", "column-reverse"}:
            return False
        columns = [child for child in self._children(element) if self._is_block_child(child)]
        return len(columns) >= 2

    def _flex_row_block(self, element: Tag, width: float) -> _Block | None:
        """Measure a flex row: each column gets its own width and vertical flow.

        Column widths come from whichever ``flex``/``flex-basis``/``width``
        the child already carries (see :func:`_column_width`); columns with no
        resolvable width share the leftover space equally, mirroring the
        browser's ``flex:1`` fair-share behaviour. Each column's natural
        height is measured with the *same* :meth:`_collect_all` used for a
        normal single-column region, so nested content (panels, tables,
        text) keeps behaving exactly as it does outside a row.
        """
        columns_el = [child for child in self._children(element) if self._is_block_child(child)]
        gap = parse_px(self.res.props(element).get("gap", "") or self.res.props(element).get("column-gap", ""))
        widths = _column_widths(self.res, columns_el, width, gap * PX_IN)
        if widths is None:
            return None
        columns: list[_Column] = []
        offset = 0.0
        heights: list[float] = []
        min_heights: list[float] = []
        for child, col_width in zip(columns_el, widths, strict=True):
            child_elements = self._children(child) if self._is_flex_row_column_wrapper(child) else [child]
            blocks = self._collect_all(child_elements, col_width)
            natural = sum(b.height for b in blocks)
            shrinkable = sum(max(b.height - b.min_height, 0.0) if b.flexible else 0.0 for b in blocks)
            columns.append(_Column(offset, col_width, child_elements))
            heights.append(natural)
            min_heights.append(max(natural - shrinkable, 0.02))
            offset += col_width + gap * PX_IN
        if not columns:
            return None
        natural_height = max(heights, default=0.02)
        min_height = max(min_heights, default=0.02)
        return _Block(
            "row",
            element,
            max(natural_height, 0.02),
            min_height=min(min_height, natural_height),
            flexible=True,
            columns=columns,
        )

    @staticmethod
    def _is_flex_row_column_wrapper(child: Tag) -> bool:
        """Tell whether a column's own children flow directly (no extra block).

        A column that is itself a plain flex/box layout wrapper (no visual
        decoration of its own: no fill, no border accent, no data-type) is
        transparent: its children flow as the column content, exactly like
        the direct children of ``.slide-body`` would. A decorated or typed
        column (a table, a panel, an arch-diagram, ...) is kept as a single
        child so its own dedicated renderer still gets to run.
        """
        if child.get("data-type"):
            return False
        return child.name == "div" and not classes(child)

    def _is_panel(self, element: Tag) -> bool:
        """Tell whether an element is a decorated panel (fill or accent bar)."""
        if has_class(element, *TILE_CLASSES):
            return True
        props = self.res.props(element)
        return bool(color_of(props, FILL_KEYS, self.res) or color_of(props, BAR_KEYS, self.res))

    def _has_block_children(self, element: Tag) -> bool:
        """Tell whether an element contains children that become their own block."""
        return any(isinstance(child, Tag) and self._is_block_child(child) for child in element.children)

    @staticmethod
    def _is_block_child(child: Tag) -> bool:
        """Tell whether a child element is laid out as a block of its own."""
        if child.name in SKIP_TAGS:
            return False
        return (
            child.name in BLOCK_TAGS
            or child.name in INLINE_BLOCK_TAGS
            or child.name == "img"
            or bool(child.get("data-type"))
            or has_class(child, *INLINE_BLOCK_CLASSES, *GRID_CLASSES, *TILE_CLASSES)
        )

    @staticmethod
    def _children(element: Tag) -> list[Tag]:
        """Return the direct element children of a node."""
        return [child for child in element.children if isinstance(child, Tag)]

    def _consume(self, element: Tag, deep: bool = True) -> None:
        """Mark an element (and optionally its subtree) as already rendered."""
        self.handled.add(id(element))
        if deep:
            for node in element.find_all(True):
                self.handled.add(id(node))

    # -- block measurement -------------------------------------------------

    def _text_block(self, element: Tag, width: float) -> list[_Block]:
        """Measure a text block, or drop it when it carries no text."""
        style = self.res.style(element)
        paras = self._paragraphs(element, style)
        if not paras:
            return []
        height = sum(self._para_height(p, width) for p in paras)
        return [_Block("text", element, height, style=style)]

    def _para_height(self, para: _Para, width: float) -> float:
        """Height of one paragraph, indentation included."""
        text = "".join(text for text, _ in para.runs)
        indent = para.level * 0.18
        return block_height(text, para.style, max(width - indent, 0.5))

    def _text_height(self, element: Tag, width: float, style: TextStyle) -> float:
        """Height of the whole text content of an element."""
        return sum(self._para_height(p, width) for p in self._paragraphs(element, style))
