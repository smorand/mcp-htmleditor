"""Native table writer of the painted PPTX export (SPEC-0024 FR-5).

A mixin of ``Painter``: a measured ``table`` item (column widths, row heights, cells with spans, fill, borders per
side, padding, vertical alignment and text) becomes a real PowerPoint table. The grid comes from the browser's cell
geometry, so ``colspan`` and ``rowspan`` need no markup reading. A table the measure cannot map (cells holding blocks,
pictures or chips) never reaches this module: it is painted as boxes and text.
"""

from __future__ import annotations

from typing import Any, Final

from pptx.enum.text import MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Emu

from .pptx_paint_shapes import add_alpha, srgb_element
from .pptx_paint_style import EMU_PER_POINT, alpha_of, line_dash, rgb, table_span, to_emu
from .pptx_paint_text import align_of, sizes, write_lines

ANCHORS: Final = {"middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}
SIDE_TAGS: Final = ("a:lnT", "a:lnR", "a:lnB", "a:lnL")  # the order of the measure: top, right, bottom, left
PROPERTY_ORDER: Final = ("a:lnL", "a:lnR", "a:lnT", "a:lnB")


class TablesMixin:
    """Tables of a painted slide."""

    slide: Any

    def table(self, item: dict[str, Any]) -> None:
        """A native table at the measured box; every cell styled from its computed style."""
        columns, rows = item["cols"], item["rows"]
        frame = self.slide.shapes.add_table(len(rows), len(columns), *to_emu(item["box"]))
        grid = frame.table
        properties = grid._tbl.tblPr
        for attribute in ("firstRow", "bandRow"):
            properties.set(attribute, "0")
        style_id = properties.find(qn("a:tableStyleId"))
        if style_id is not None:
            properties.remove(style_id)
        for index, width in enumerate(sizes(columns)):
            grid.columns[index].width = width
        for index, height in enumerate(sizes(rows)):
            grid.rows[index].height = height
        for cell in item["cells"]:
            first_row, first_col, last_row, last_col = table_span(cell)
            target = grid.cell(first_row, first_col)
            if last_row > first_row or last_col > first_col:
                target.merge(grid.cell(last_row, last_col))
            self._style_cell(target, cell, item.get("op", 1.0))

    @staticmethod
    def _style_cell(target: Any, cell: dict[str, Any], opacity: float) -> None:
        left, top, right, bottom = cell["pad"]
        target.margin_left, target.margin_top = Emu(round(left * EMU_PER_POINT)), Emu(round(top * EMU_PER_POINT))
        target.margin_right, target.margin_bottom = (
            Emu(round(right * EMU_PER_POINT)),
            Emu(round(bottom * EMU_PER_POINT)),
        )
        target.vertical_anchor = ANCHORS.get(cell["valign"], MSO_ANCHOR.TOP)
        if cell.get("fill"):
            target.fill.solid()
            target.fill.fore_color.rgb = rgb(cell["fill"])
            add_alpha(target._tc.tcPr.find(qn("a:solidFill")).find(qn("a:srgbClr")), alpha_of(cell["fill"], opacity))
        else:
            target.fill.background()
        _borders(target._tc.get_or_add_tcPr(), cell["borders"], opacity)
        text = cell.get("text")
        if text:
            write_lines(target.text_frame, text, align_of(text["align"]))
        else:  # an empty cell must not stretch its row with the default 18 pt paragraph
            target.text_frame.paragraphs[0]._p.get_or_add_endParaRPr().set("sz", "100")


def _borders(properties: Any, borders: list[dict[str, Any] | None], opacity: float) -> None:
    """The four ``a:ln*`` children, put before the fill as the schema wants (left, right, top, bottom)."""
    by_tag = dict(zip(SIDE_TAGS, borders, strict=True))
    for position, tag in enumerate(PROPERTY_ORDER):
        side = by_tag[tag]
        if side is None:
            line = properties.makeelement(qn(tag), {"w": "0"})
            line.append(line.makeelement(qn("a:noFill"), {}))
        else:
            line = properties.makeelement(
                qn(tag), {"w": str(round(side["w"] * EMU_PER_POINT)), "cap": "flat", "cmpd": "sng"}
            )
            fill = line.makeelement(qn("a:solidFill"), {})
            line.append(fill)
            srgb_element(fill, side["color"], opacity)
            dash = line_dash(side.get("style"))
            if dash:
                line.append(line.makeelement(qn("a:prstDash"), {"val": dash}))
        properties.insert(position, line)
