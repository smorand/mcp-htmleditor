"""Architecture diagram rendering of the PPTX slide builder.

``ArchMixin`` draws an ``arch-diagram`` container: nodes as native shapes, edges as
line segments, arrow tips, step badges and edge labels.
"""

from __future__ import annotations

from bs4 import Tag
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches, Pt

from .pptx_components import apply_transform, color_of, first_pct
from .pptx_model import _SHAPES, SKIP_TAGS, _BuilderBase, _Para
from .pptx_style import PX_IN, Box, TextStyle, has_class, parse_color, parse_pct, parse_px, style_props


class ArchMixin(_BuilderBase):
    """Architecture diagram rendering of the slide builder."""

    def _render_arch(self, box: Box, element: Tag) -> None:
        """Render an architecture diagram: nodes as shapes, edges as lines."""
        background = self._element_color(element)
        if background:
            self._rect(box, fill=background, line=self.theme.border)
        nodes = self._render_arch_children(box, element)
        if not nodes:
            self.ctx.report.warn('Schema sans noeud data-type="arch-node": seul le cadre est exporte.')

    def _render_arch_children(self, container: Box, element: Tag) -> int:
        """Recursively render arch-node/-line/-tip/-label descendants of ``element``.

        Switches ``container`` when descending into an ``arch-col``: in the browser
        an arch-col is itself ``position:absolute``, which per CSS makes it the
        containing block for its OWN children's percentages (see
        ``arch_layout.py``'s ``_to_local`` and ``.agent_docs/html-conventions.md``).
        Reading a nested node's ``data-x``/``data-y`` against the outer diagram box
        instead of its col's box would shrink and misplace it exactly like the CSS
        bug that ``_to_local`` exists to prevent, just in the exported deck instead
        of the browser. Every other wrapper (``arch-row``, plain decorative divs)
        stays inert and keeps the same container, matching the browser exactly.
        """
        nodes = 0
        for child in element.find_all(True, recursive=False):
            if not isinstance(child, Tag) or child.name in SKIP_TAGS:
                continue
            dtype = str(child.get("data-type") or "")
            if dtype == "arch-node":
                self._render_arch_node(container, child)
                nodes += 1
            elif dtype == "arch-col":
                col_box = self._node_box(container, child, default_w=20.0, default_h=12.0)
                nodes += self._render_arch_children(col_box, child)
            elif has_class(child, "arch-line-h", "arch-line-v"):
                self._render_arch_line(container, child)
            elif has_class(child, "arch-tip"):
                self._render_arch_tip(container, child)
            elif has_class(child, "arch-edge-label") or dtype == "arch-edge":
                self._render_arch_label(container, child)
            elif has_class(child, "arch-edge-badge"):
                self._render_arch_badge(container, child)
            else:
                nodes += self._render_arch_children(container, child)
        return nodes

    def _node_box(self, container: Box, element: Tag, default_w: float, default_h: float) -> Box:
        """Resolve the box of a positioned child, in the container reference.

        Percentages are relative to the container, as documented for
        ``data-x`` / ``data-y``, never to the slide.
        """
        props = style_props(element)
        x = first_pct(element.get("data-x"), props.get("left"))
        y = first_pct(element.get("data-y"), props.get("top"))
        w = first_pct(element.get("data-width"), props.get("width"), default=default_w)
        h = first_pct(element.get("data-height"), props.get("height"), default=default_h)
        box = container.pct(x, y, w, h)
        return apply_transform(box, props)

    def _render_arch_node(self, container: Box, node: Tag) -> None:
        """Render one diagram node as a filled, outlined and labelled shape."""
        box = self._node_box(container, node, default_w=20.0, default_h=12.0)
        props = style_props(node)
        shape_name = str(node.get("data-shape") or "box").lower()
        shape = self._rect(
            box,
            fill=self._element_color(node) or "FFFFFF",
            shape=_SHAPES.get(shape_name, MSO_SHAPE.ROUNDED_RECTANGLE),
            radius_px=parse_px(props.get("border-radius", "")) or 4.0,
        )
        merged = self.res.props(node)
        line = color_of(merged, ("border", "border-color"), self.res)
        shape.line.color.rgb = RGBColor.from_string(line or self.theme.primary)
        shape.line.width = Pt(1.25)
        frame = shape.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        frame.margin_left = frame.margin_right = Inches(0.04)
        frame.margin_top = frame.margin_bottom = Inches(0.02)
        color = parse_color(merged.get("color"), self.res.css_vars) or self.theme.text
        base = TextStyle(size=11, bold=True, color=color, align="center", space_after=0)
        self._write(frame, self._paragraphs(node, base) or [_Para(base, [(str(node.get("data-label") or ""), base)])])

    def _render_arch_line(self, container: Box, edge: Tag) -> None:
        """Render an edge segment as a thin filled rectangle."""
        props = style_props(edge)
        thickness = 1.5 * PX_IN
        horizontal = has_class(edge, "arch-line-h")
        x = parse_pct(props.get("left", "0%"))
        y = parse_pct(props.get("top", "0%"))
        length = parse_pct(props.get("width" if horizontal else "height", "0%"))
        if length <= 0:
            return
        if horizontal:
            box = container.pct(x, y, length, 0.1)
            box = Box(box.left, box.top - thickness / 2, box.width, thickness)
        else:
            box = container.pct(x, y, 0.1, length)
            box = Box(box.left - thickness / 2, box.top, thickness, box.height)
        self._rect(box, fill=self._edge_color(edge))

    def _render_arch_tip(self, container: Box, tip: Tag) -> None:
        """Render an arrow head as a small rotated triangle."""
        props = style_props(tip)
        size = 8.0 * PX_IN
        x = parse_pct(props.get("left", "0%"))
        y = parse_pct(props.get("top", "0%"))
        anchor = container.pct(x, y, 0.1, 0.1)
        rotations = {"arch-tip-r": 90, "arch-tip-l": 270, "arch-tip-d": 180, "arch-tip-u": 0}
        rotation = next(
            (deg for name, deg in rotations.items() if has_class(tip, name)),
            90,
        )
        box = Box(anchor.left - size / 2, anchor.top - size / 2, size, size)
        shape = self._rect(box, fill=self._edge_color(tip), shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
        shape.rotation = rotation

    def _render_arch_badge(self, container: Box, badge: Tag) -> None:
        """Render a numbered step badge (``data-step``) as a small filled circle.

        Mirrors the browser's ``.arch-edge-badge`` (14px circle, centered white
        bold number, background from the edge's own color): closes the PPTX
        fidelity gap documented in ``.agent_docs/html-conventions.md`` and the
        arch-diagram QA checklist.
        """
        text = badge.get_text(strip=True)
        if not text:
            return
        props = style_props(badge)
        x = parse_pct(props.get("left", "0%"))
        y = parse_pct(props.get("top", "0%"))
        size = 14.0 * PX_IN
        anchor = container.pct(x, y, 0.1, 0.1)
        box = Box(anchor.left - size / 2, anchor.top - size / 2, size, size)
        fill = color_of(self.res.props(badge), ("background", "background-color"), self.res) or self.theme.primary
        shape = self._rect(box, fill=fill, shape=MSO_SHAPE.OVAL)
        frame = shape.text_frame
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        style = TextStyle(size=8, bold=True, color="FFFFFF", align="center", space_after=0)
        self._write(frame, [_Para(style, [(text, style)])])

    def _render_arch_label(self, container: Box, label: Tag) -> None:
        """Render an edge label, or a text based arrow, inside the diagram."""
        text = label.get_text(" ", strip=True)
        if not text:
            return
        props = style_props(label)
        x = parse_pct(props.get("left", "0%"))
        y = parse_pct(props.get("top", "0%"))
        width_pct = parse_pct(props.get("width", "0%")) or 18.0
        box = container.pct(x, y, width_pct, 0.1)
        box = Box(box.left, box.top - 0.09, max(box.width, 0.5), 0.2)
        box = apply_transform(box, props)
        style = self.res.apply(
            TextStyle(size=9.5, color="secondary", space_after=0, align="center"),
            self.res.props(label),
        )
        _, frame = self._textbox(box, anchor="middle")
        self._write(frame, [_Para(style, [(text, style)])])

    def _edge_color(self, edge: Tag) -> str:
        """Resolve the stroke color of an edge element."""
        color = color_of(
            self.res.props(edge),
            ("background", "background-color", "border-top-color", "border-color", "color"),
            self.res,
        )
        return color or self.theme.primary
