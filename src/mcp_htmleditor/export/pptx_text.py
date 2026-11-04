"""Text plumbing and drawing primitives of the PPTX slide builder.

``TextMixin`` turns HTML elements into styled paragraphs and runs, writes them into
text frames, and draws the rectangle and textbox primitives the other mixins use.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from bs4 import NavigableString, Tag
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_PATTERN_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Pt

from .pptx_components import color_of, drop_theme_style, split_runs
from .pptx_model import _ALIGN, FILL_KEYS, INLINE_BLOCK_TAGS, SKIP_TAGS, _BuilderBase, _Para
from .pptx_style import Box, TextStyle, classes, has_class, parse_color


class TextMixin(_BuilderBase):
    """Text, paragraph rendering and drawing primitives of the slide builder."""

    # -- text plumbing -----------------------------------------------------

    def _paragraphs(self, element: Tag, base: TextStyle, level: int = 0) -> list[_Para]:
        """Flatten an element into a list of styled paragraphs."""
        if element.name in SKIP_TAGS:
            return []
        if element.name in {"ul", "ol"}:
            paras: list[_Para] = []
            ordered = element.name == "ol"
            for position, item in enumerate(element.find_all("li", recursive=False), start=1):
                style = self.res.style(item, base)
                item_paras = self._paragraphs(item, style, level + 1)
                if item_paras:
                    marker = f"{position}. " if ordered else "\u2022 "
                    item_paras[0].runs.insert(0, (marker, replace(style, bold=True)))
                paras.extend(item_paras)
            return paras
        if self._has_block_children(element):
            blocks: list[_Para] = []
            inline: list[tuple[str, TextStyle]] = []

            def flush() -> None:
                """Emit the pending inline runs as one paragraph."""
                if any(text.strip() for text, _ in inline):
                    blocks.append(_Para(base, list(inline), level))
                inline.clear()

            for child in element.children:
                if isinstance(child, NavigableString):
                    # Inline text around a nested block (``<li>text<ul>…</ul></li>``)
                    # keeps flowing in the *same* paragraph as the neighbouring
                    # inline tags: one paragraph per text node would break a
                    # bullet in two right after its bold lead-in.
                    text = re.sub(r"\s+", " ", str(child))
                    if text.strip():
                        inline.append((text, base))
                elif isinstance(child, Tag) and child.name not in SKIP_TAGS:
                    if not self._is_block_child(child):
                        inline.extend(self._runs(child, self._inline_style(child, base)))
                        continue
                    flush()
                    style = self.res.style(child, base)
                    if child.name in INLINE_BLOCK_TAGS:
                        style = self._inline_style(child, base)
                    blocks.extend(self._paragraphs(child, style, level))
            flush()
            return blocks
        runs = self._runs(element, base)
        return [_Para(base, runs, level)] if runs else []

    def _runs(self, element: Tag, style: TextStyle) -> list[tuple[str, TextStyle]]:
        """Flatten the inline content of an element into styled runs.

        Adjacent inline elements are separated by a space: the templates lay
        them out with a flex ``gap`` that has no equivalent in a PPTX run.
        """
        runs: list[tuple[str, TextStyle]] = []
        previous_was_tag = False
        for node in element.children:
            if isinstance(node, NavigableString):
                text = re.sub(r"[ \t\r\n]+", " ", str(node))
                if text.strip():
                    runs.append((text, style))
                    previous_was_tag = False
            elif isinstance(node, Tag):
                if node.name == "br":
                    runs.append(("\n", style))
                    previous_was_tag = False
                elif node.name in SKIP_TAGS:
                    continue
                else:
                    if previous_was_tag and runs and not runs[-1][0].endswith(" "):
                        runs.append((" ", style))
                    runs.extend(self._runs(node, self._inline_style(node, style)))
                    previous_was_tag = True
        if not runs:
            text = element.get_text(" ", strip=True)
            if text:
                runs.append((text, style))
        return runs

    def _inline_style(self, node: Tag, parent: TextStyle) -> TextStyle:
        """Derive the style of an inline element from its parent style."""
        style = parent
        if node.name in {"strong", "b"}:
            style = replace(style, bold=True)
        if node.name in {"em", "i"}:
            style = replace(style, italic=True)
        if node.name in {"small"} or has_class(node, "arch-node-label", "gantt-sub"):
            style = replace(style, size=max(style.size * 0.78, 7.0), bold=False)
        if node.name in {"code", "kbd"} or has_class(node, "cds-code"):
            style = replace(style, mono=True, size=max(style.size * 0.92, 7.0))
        if node.name == "span" and has_class(node.parent, "slide-h1"):
            style = replace(style, color=self.theme.accent)
        if classes(node):
            style = self.res.style(node, style)
        return self.res.apply(style, self.res.props(node))

    def _write(self, frame: Any, paras: list[_Para]) -> None:
        """Write paragraphs into a text frame, honouring styles and breaks.

        Does not touch ``word_wrap``: the frame's own setting (``_textbox``'s
        default is wrapping on, callers needing a single-line label such as
        a Gantt bar pass ``wrap=False``) must survive writing the runs.
        """
        first = True
        for para in paras:
            chunks = split_runs(para.runs)
            for chunk in chunks:
                paragraph = frame.paragraphs[0] if first else frame.add_paragraph()
                first = False
                paragraph.alignment = _ALIGN.get(para.style.align, PP_ALIGN.LEFT)
                paragraph.line_spacing = para.style.line_spacing
                paragraph.space_after = Pt(para.style.space_after)
                if para.level > 1:
                    # Markers are written explicitly, so only nested lists indent.
                    paragraph.level = min(para.level - 1, 4)
                for text, style in chunk:
                    run = paragraph.add_run()
                    run.text = text.upper() if style.upper else text
                    font = run.font
                    font.name = self.theme.mono_font if style.mono else self.theme.font
                    font.size = Pt(style.size)
                    font.bold = style.bold
                    font.italic = style.italic
                    font.color.rgb = RGBColor.from_string(self.theme.color(style.color))

    def _textbox(self, box: Box, anchor: str = "top", wrap: bool = True) -> tuple[Any, Any]:
        """Create a margin free textbox and return ``(shape, text_frame)``.

        ``wrap=False`` also turns off ``spAutoFit``: python-pptx's default
        auto-size only resizes the *shape* to fit unwrapped text (an
        instruction PowerPoint applies live, but LibreOffice's headless
        renderer used for exports and screenshots does not), so a caller
        that pre-fits its text to the box (the Gantt bar labels) needs the
        frame to just clip at the box bounds instead, matching what it
        measured against.
        """
        shape = self.slide.shapes.add_textbox(*box.emu())
        frame = shape.text_frame
        frame.word_wrap = wrap
        if not wrap:
            frame.auto_size = MSO_AUTO_SIZE.NONE
        frame.margin_left = frame.margin_right = 0
        frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE if anchor == "middle" else MSO_ANCHOR.TOP
        return shape, frame

    # -- shapes and pictures ----------------------------------------------

    def _rect(  # noqa: PLR0913 - one flag per optional shape trait, all keyword-only
        self,
        box: Box,
        fill: str | None = None,
        line: str | None = None,
        *,
        shape: Any = MSO_SHAPE.RECTANGLE,
        radius_px: float | None = None,
        hatch: bool = False,
    ) -> Any:
        """Add an auto shape with a solid fill and no outline by default.

        ``hatch`` swaps the solid fill for a native PPTX diagonal pattern
        fill (foreground ``fill``, white background), the closest built-in
        equivalent of the CSS ``repeating-linear-gradient(45deg, ...)`` hatch
        the templates use to mark a task as done/in a different state: real
        pattern geometry survives the export instead of a flat color or a
        text workaround.
        """
        auto = self.slide.shapes.add_shape(shape, *box.emu())
        drop_theme_style(auto)
        if radius_px and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            smallest = max(min(box.width, box.height) * 72.0, 1.0)
            auto.adjustments[0] = min(max(radius_px / smallest, 0.0), 0.5)
        if hatch and fill:
            auto.fill.patterned()
            auto.fill.pattern = MSO_PATTERN_TYPE.WIDE_UPWARD_DIAGONAL
            auto.fill.fore_color.rgb = RGBColor.from_string(fill)
            auto.fill.back_color.rgb = RGBColor.from_string("FFFFFF")
        elif fill:
            auto.fill.solid()
            auto.fill.fore_color.rgb = RGBColor.from_string(fill)
        else:
            auto.fill.background()
        if line:
            auto.line.color.rgb = RGBColor.from_string(line)
            auto.line.width = Pt(0.75)
        else:
            auto.line.fill.background()
        auto.text_frame.word_wrap = True
        return auto

    def _element_color(self, element: Tag) -> str | None:
        """Resolve the background color of an element (CSS, inline, data-color)."""
        color = color_of(self.res.props(element), FILL_KEYS, self.res)
        return color or parse_color(str(element.get("data-color") or ""), self.res.css_vars)
