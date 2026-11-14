"""Text writers of the painted PPTX export (SPEC-0024 FR-2): editable text with the browser's own line breaks.

A mixin of ``Painter``: each measured text block becomes one text box, one paragraph per browser line, runs per
style (face, size, weight, italic, underline, colour, letter spacing). List items keep a real paragraph marker with a
hanging indent and the marker colour. ``write_lines`` is shared with the table cells.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from .pptx_paint_shapes import add_alpha, srgb_element
from .pptx_paint_style import EMU_PER_POINT, alpha_of, bullet_for, first_face, hanging_indent, rgb, to_emu

CENTER_ALIGN: Final = frozenset({"center", "-webkit-center"})
RIGHT_ALIGN: Final = frozenset({"right", "end"})
BOLD_WEIGHT: Final = 600
MIN_SLACK: Final = 6
SLACK_SHARE: Final = 0.08
ALIGNS: Final = {"center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT, "left": PP_ALIGN.LEFT}


def merge_runs(line: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Merge the words of one line into runs of the same style; spaces as measured, upper case applied."""
    runs: list[list[Any]] = []
    for word in line:
        text = (" " if word["sp"] else "") + (word["t"].upper() if word["s"]["upper"] else word["t"])
        if runs and runs[-1][1] == word["s"]:
            runs[-1][0] += text
        else:
            runs.append([text, word["s"]])
    return [(text, style) for text, style in runs]


def align_of(css_align: str) -> str:
    """``center``, ``right`` or ``left`` for a computed ``text-align``."""
    if css_align in CENTER_ALIGN:
        return "center"
    return "right" if css_align in RIGHT_ALIGN else "left"


class TextMixin:
    """Text boxes of a painted slide."""

    slide: Any

    def text(self, item: dict[str, Any]) -> None:
        """One editable text box for a measured block (wrap off: the lines are the browser's)."""
        bx, by, bw, bh = item["box"]
        cx, _cy, cw, _ch = item["content"]
        bullet = item.get("bullet")
        first = item["lines"][0][0]["s"]
        hang = hanging_indent(first["size"]) if bullet else 0.0
        slack = max(bw * SLACK_SHARE, MIN_SLACK)  # no wrap: a slightly wider face never breaks a line
        align = align_of(item["align"])
        if align == "center":
            bw = max(bw, cw) + 2 * slack
            bx = cx + cw / 2 - bw / 2
        elif align == "right":
            right = bx + bw
            bw += slack
            bx = right - bw
        else:
            bx -= hang
            bw += slack + hang
        frame = self.slide.shapes.add_textbox(*to_emu([bx, by, bw, bh])).text_frame
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.TOP
        write_lines(frame, item, align, hang if align == "left" else 0.0)


def write_lines(frame: Any, item: dict[str, Any], align: str, hang: float = 0.0) -> None:
    """Fill ``frame`` with the paragraphs of a measured text item (``lines``, ``lh``, ``op``, ``bullet``)."""
    frame.word_wrap = False
    frame.auto_size = MSO_AUTO_SIZE.NONE
    bullet = item.get("bullet")
    opacity = item.get("op", 1.0)
    for index, line in enumerate(item["lines"]):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = ALIGNS[align]
        paragraph.line_spacing = Pt(item["lh"])
        paragraph.space_before = paragraph.space_after = Pt(0)
        if hang:
            _indent(paragraph, hang, bullet if index == 0 else None, line[0]["s"], opacity)
        for text, style in merge_runs(line):
            write_run(paragraph, text, style, opacity)


def _indent(paragraph: Any, hang: float, bullet: dict[str, Any] | None, style: dict[str, Any], opacity: float) -> None:
    """Hanging indent of a list paragraph; the marker (colour, character or number) only on its first line."""
    properties = paragraph._p.get_or_add_pPr()
    properties.set("marL", str(round(hang * EMU_PER_POINT)))
    properties.set("indent", str(-round(hang * EMU_PER_POINT)) if bullet else "0")
    if not bullet:
        properties.append(properties.makeelement(qn("a:buNone"), {}))
        return
    marker = bullet_for(bullet["type"])
    colour = properties.makeelement(qn("a:buClr"), {})
    srgb_element(colour, bullet["color"] or style["color"] or (0, 0, 0, 1), opacity)
    properties.append(colour)
    if marker.numbering:
        properties.append(properties.makeelement(qn("a:buFont"), {"typeface": "+mj-lt"}))
        attributes = {"type": marker.numbering}
        if bullet["index"] != 1:
            attributes["startAt"] = str(bullet["index"])
        properties.append(properties.makeelement(qn("a:buAutoNum"), attributes))
    else:
        properties.append(properties.makeelement(qn("a:buFont"), {"typeface": "Arial"}))
        properties.append(properties.makeelement(qn("a:buChar"), {"char": marker.char or "\u2022"}))


def write_run(paragraph: Any, text: str, style: dict[str, Any], opacity: float = 1.0) -> None:
    """One run: face, size, weight, italic, underline, strike, colour (alpha), letter spacing."""
    run = paragraph.add_run()
    run.text = text
    face = first_face(style["font"])
    font = run.font
    font.name = face
    font.size = Pt(style["size"])
    font.bold = style["weight"] >= BOLD_WEIGHT
    font.italic = style["italic"]
    if style.get("under"):
        font.underline = True
    if style["color"]:
        font.color.rgb = rgb(style["color"])
        colour = run._r.get_or_add_rPr().find(qn("a:solidFill")).find(qn("a:srgbClr"))
        add_alpha(colour, alpha_of(style["color"], opacity))
    properties = run._r.get_or_add_rPr()
    if style["ls"]:
        properties.set("spc", str(round(style["ls"] * 100)))
    if style.get("strike"):
        properties.set("strike", "sngStrike")
    for tag in ("a:ea", "a:cs"):  # same face for every script
        node = properties.find(qn(tag))
        if node is None:
            node = properties.makeelement(qn(tag), {})
            properties.append(node)
        node.set("typeface", face)


def sizes(values: Sequence[float]) -> list[Emu]:
    """Point lengths as EMU lengths (column widths, row heights)."""
    return [Emu(max(round(v * EMU_PER_POINT), 1)) for v in values]
