"""Per charter chrome of the PPTX slide builder.

``ChromeMixin`` draws the Euro-Information, Carbon, medical and generic slide
chrome (backgrounds, frames, footers) and returns the content regions to flow.
"""

from __future__ import annotations

import re

from bs4 import Tag
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from .pptx_components import color_of, inches, is_light
from .pptx_model import _BuilderBase, _Region
from .pptx_style import PX_IN, SLIDE_H_IN, SLIDE_W_IN, Box, classes, has_class, parse_color, parse_px, style_props


class ChromeMixin(_BuilderBase):
    """Per charter chrome of the slide builder."""

    def _chrome_ei(self, kind: str) -> list[_Region]:
        """Draw the Euro-Information charter and return the content regions."""
        canvas = Box.slide()
        if kind == "section":
            self._rect(canvas, fill=self.theme.primary)
            band = self.article.find(class_="slide-section-band")
            if isinstance(band, Tag):
                self._consume(band)
            self._rect(canvas.pct(0, 72, 100, 6), fill=self.theme.primary_alt)
            body = self.article.find(class_="slide-section-body")
            host = body if isinstance(body, Tag) else self.article
            return [_Region(canvas.inset_px(72, 40), self._children(host), anchor="middle")]

        if kind == "title":
            return self._chrome_ei_title(canvas)

        # content / agenda / diagram: blue frame, white rounded inner area.
        self._rect(canvas, fill=self.theme.primary)
        inner = canvas.inset_px(10)
        self._rect(inner, fill="FFFFFF", radius_px=16)
        foot = self.article.find(class_="slide-foot")
        if isinstance(foot, Tag):
            self._render_ei_foot(foot)
        inner_host = self.article.find(class_="slide-inner")
        container = inner_host if isinstance(inner_host, Tag) else self.article
        if isinstance(inner_host, Tag):
            self._consume(inner_host, deep=False)
        content = inner.inset_px(40, 30, 40, 50)
        return [_Region(content, self._children(container))]

    def _chrome_ei_title(self, canvas: Box) -> list[_Region]:
        """Render the EI cover slide: full width image, centered title, logos."""
        cover = self.article.find(class_="slide-cover-img")
        if isinstance(cover, Tag):
            self._consume(cover)
            self._add_picture(canvas.pct(0, 0, 100, 66), str(cover.get("src") or ""), mode="cover")
        logos = self.article.find(class_="slide-cover-logos")
        if isinstance(logos, Tag):
            self._consume(logos)
            self._render_cover_logos(logos)
        body = self.article.find(class_="slide-cover-body")
        if isinstance(body, Tag):
            self._consume(body, deep=False)
            region = canvas.pct(0, 66, 100, 26).inset_px(48, 6)
            return [_Region(region, self._children(body), anchor="middle")]
        return [_Region(canvas.inset_px(48, 40), self._children(self.article), anchor="middle")]

    def _render_cover_logos(self, container: Tag) -> None:
        """Place the cover logo row: grouped logos left, single logo right."""
        baseline = (540.0 - 18.0) * PX_IN
        heights = {"logo-cm": 26.0, "logo-cic": 24.0, "logo-ei": 34.0}
        left_group = container.find(class_="logos-left")
        left_images = list(left_group.find_all("img")) if isinstance(left_group, Tag) else []
        right_images = [img for img in container.find_all("img") if img not in left_images and isinstance(img, Tag)]

        cursor = 48.0 * PX_IN
        for img in left_images:
            height = self._logo_height(img, heights) * PX_IN
            box = Box(cursor, baseline - height, 3.0, height)
            placed = self._add_picture(box, str(img.get("src") or ""), mode="fit-height")
            cursor += (inches(placed.width) if placed else 0.6) + 20.0 * PX_IN
        right_edge = SLIDE_W_IN - 48.0 * PX_IN
        for img in reversed(right_images):
            height = self._logo_height(img, heights) * PX_IN
            box = Box(right_edge - 1.2, baseline - height, 1.2, height)
            placed = self._add_picture(box, str(img.get("src") or ""), mode="fit-height")
            if placed:
                width = inches(placed.width)
                placed.left = Inches(right_edge - width)
                right_edge -= width + 20.0 * PX_IN

    @staticmethod
    def _logo_height(img: Tag, heights: dict[str, float]) -> float:
        """Return the CSS height of a cover logo from its class, default 24px."""
        for name in classes(img):
            if name in heights:
                return heights[name]
        return 24.0

    def _render_ei_foot(self, foot: Tag) -> None:
        """Render the EI footer: logo ring, page number and meeting title."""
        self._consume(foot)
        band = Box(0.0, SLIDE_H_IN - 40.0 * PX_IN, SLIDE_W_IN, 40.0 * PX_IN)
        ring = Box(2.0 * PX_IN, SLIDE_H_IN - 52.0 * PX_IN, 50.0 * PX_IN, 50.0 * PX_IN)
        oval = self._rect(ring, fill="FFFFFF", shape=MSO_SHAPE.OVAL)
        oval.line.color.rgb = RGBColor.from_string(self.theme.primary)
        oval.line.width = Pt(10)
        logo = foot.find("img")
        if isinstance(logo, Tag):
            inner = Box(ring.left, ring.top + (ring.height - 16.0 * PX_IN) / 2, ring.width, 16.0 * PX_IN)
            self._add_picture(inner, str(logo.get("src") or ""), mode="fit")

        page = foot.find(class_="slide-foot-page")
        if isinstance(page, Tag):
            box = Box(64.0 * PX_IN, band.top + 0.10, 0.8, 0.2)
            self._render_text(box, page, anchor="middle")
        title = foot.find(class_="slide-foot-title")
        if isinstance(title, Tag):
            box = Box(1.6, band.top + 0.10, SLIDE_W_IN - 3.2, 0.2)
            self._render_text(box, title, anchor="middle")

    def _chrome_carbon(self) -> list[_Region]:
        """Draw the IBM Carbon charter and return the content regions."""
        canvas = Box.slide()
        background = self._element_color(self.article) or "FFFFFF"
        self._rect(canvas, fill=background)
        regions: list[_Region] = []
        pad_x, pad_y = 40.0 * PX_IN, 30.0 * PX_IN
        content_w = SLIDE_W_IN - 2 * pad_x
        cursor = pad_y
        section = self._slide_kind() == "section"

        footer = self.article.find(class_="slide-footer")
        footer_top = SLIDE_H_IN
        if isinstance(footer, Tag):
            footer_top = SLIDE_H_IN - 40.0 * PX_IN
            self._rect(
                Box(0.0, footer_top, SLIDE_W_IN, 40.0 * PX_IN),
                fill=self._element_color(footer) or (self.theme.surface if is_light(background) else background),
                line=self.theme.border,
            )
            self._render_footer_texts(footer, footer_top)

        header = self.article.find(class_="slide-header")
        if isinstance(header, Tag):
            self._consume(header, deep=False)
            blocks = self._collect_all(self._children(header), content_w)
            height = sum(b.height for b in blocks)
            props = self.res.props(header)
            rule_h = parse_px(props.get("border-bottom", "")) * PX_IN or 4.0 * PX_IN
            rule_color = color_of(props, ("border-bottom-color", "border-bottom"), self.res)
            if section:
                # A section separator centers its title and rules off the footer.
                rule_y = footer_top - rule_h
                regions.append(
                    _Region(
                        Box(pad_x, pad_y, content_w, max(rule_y - 2 * pad_y, height)),
                        self._children(header),
                        anchor="middle",
                    )
                )
            else:
                rule_y = cursor + height + 14.0 * PX_IN
                regions.append(_Region(Box(pad_x, cursor, content_w, height), self._children(header)))
            self._rect(Box(0.0, rule_y, SLIDE_W_IN, rule_h), fill=rule_color or self.theme.primary)
            cursor = rule_y + rule_h + 22.0 * PX_IN

        body = self.article.find(class_="slide-body")
        host = body if isinstance(body, Tag) else self.article
        if isinstance(body, Tag):
            self._consume(body, deep=False)
        body_h = max(footer_top - 20.0 * PX_IN - cursor, 1.0)
        regions.append(_Region(Box(pad_x, cursor, content_w, body_h), self._children(host)))
        return regions

    def _render_footer_texts(self, footer: Tag, top: float) -> None:
        """Render the left and right texts of a Carbon style footer."""
        self._consume(footer)
        pad = 40.0 * PX_IN
        left = footer.find(class_="slide-footer-left")
        right = footer.find(class_="slide-footer-right")
        half = (SLIDE_W_IN - 2 * pad) / 2
        if isinstance(left, Tag):
            self._render_text(Box(pad, top + 0.09, half, 0.22), left, anchor="middle")
        if isinstance(right, Tag):
            self._render_text(Box(pad + half, top + 0.09, half, 0.22), right, anchor="middle")

    def _chrome_medical(self, kind: str) -> list[_Region]:
        """Draw the medical charter and return the content regions.

        Chrome of the charter: a grey top band, the title block with its
        teal/orange rule, then a bottom band holding the bibliographic source
        lines on the left and the bare page number on the right. Cover,
        section separator and closing slides replace the band/title block by
        their own full surface layout.
        """
        canvas = Box.slide()
        pad = 56.0 * PX_IN
        content_w = SLIDE_W_IN - 2 * pad
        dark = has_class(self.article, "dark")
        # The kind wins over the ``.slide { background:#fff }`` base rule: the
        # charter states the section and closing backgrounds with attribute
        # selectors (``.slide[data-slide-type="section"]``), which the class
        # based resolver cannot index. An inline background still wins over all.
        inline = parse_color(
            style_props(self.article).get("background") or style_props(self.article).get("background-color"),
            self.res.css_vars,
        )
        kind_bg = {"section": self.theme.surface, "thanks": "0F2E4C"}.get(kind) or ("0B0E11" if dark else None)
        self._rect(canvas, fill=inline or kind_bg or self._element_color(self.article) or "FFFFFF")

        band = self.article.find(class_="med-band")
        if isinstance(band, Tag):
            fill = self._element_color(band) or ("14181D" if dark else self.theme.surface)
            self._rect(canvas.slice_top(40.0 * PX_IN), fill=fill)
            self._consume(band)

        chip = self.article.find(class_="med-case-chip")
        if isinstance(chip, Tag):
            self._render_text(Box(SLIDE_W_IN - pad - 4.0, 9.0 * PX_IN, 4.0, 0.24), chip, anchor="middle")
            self._consume(chip)

        if kind == "title":
            return self._chrome_medical_cover(pad, content_w)
        if kind in {"section", "thanks"}:
            return self._chrome_medical_full(kind, pad, content_w)

        foot_top = self._render_medical_foot(pad, content_w)
        regions: list[_Region] = []
        cursor = 56.0 * PX_IN
        head = self.article.find(class_="med-head")
        if isinstance(head, Tag):
            children = self._children(head)
            height = sum(b.height for b in self._collect_all(children, content_w))
            regions.append(_Region(Box(pad, cursor, content_w, height), children))
            cursor += height + 12.0 * PX_IN
            self._consume(head, deep=False)

        body = self.article.find(class_="slide-body")
        host = body if isinstance(body, Tag) else self.article
        if isinstance(body, Tag):
            self._consume(body, deep=False)
        regions.append(_Region(Box(pad, cursor, content_w, max(foot_top - cursor - 0.05, 0.5)), self._children(host)))
        return regions

    def _chrome_medical_cover(self, pad: float, content_w: float) -> list[_Region]:
        """Render the medical cover: centered title block, date and logos row."""
        bottom = SLIDE_H_IN
        foot = self.article.find(class_="med-cover-foot")
        if isinstance(foot, Tag):
            bottom = SLIDE_H_IN - 56.0 * PX_IN
            date = foot.find(class_="med-cover-date")
            if isinstance(date, Tag):
                self._render_text(Box(pad, SLIDE_H_IN - 42.0 * PX_IN, 4.0, 0.24), date, anchor="middle")
            right_edge = SLIDE_W_IN - pad
            images = [img for img in foot.find_all("img") if isinstance(img, Tag)]
            for img in reversed(images):
                height = 38.0 * PX_IN
                box = Box(right_edge - 1.4, SLIDE_H_IN - 20.0 * PX_IN - height, 1.4, height)
                placed = self._add_picture(box, str(img.get("src") or ""), mode="fit-height")
                if placed:
                    width = inches(placed.width)
                    placed.left = Inches(right_edge - width)
                    right_edge -= width + 18.0 * PX_IN
            self._consume(foot)
        cover = self.article.find(class_="med-cover")
        host = cover if isinstance(cover, Tag) else self.article
        if isinstance(cover, Tag):
            self._consume(cover, deep=False)
        top = 40.0 * PX_IN
        return [_Region(Box(pad, top, content_w, max(bottom - top, 1.0)), self._children(host), anchor="middle")]

    def _chrome_medical_full(self, kind: str, pad: float, content_w: float) -> list[_Region]:
        """Render a full surface medical slide: section separator or closing."""
        container = self.article.find(class_="med-section" if kind == "section" else "med-thanks")
        host = container if isinstance(container, Tag) else self.article
        if isinstance(container, Tag):
            self._consume(container, deep=False)
        bottom = SLIDE_H_IN - 24.0 * PX_IN
        ack = self.article.find(class_="med-ack")
        if isinstance(ack, Tag):
            self._render_text(Box(pad, SLIDE_H_IN - 58.0 * PX_IN, content_w, 0.45), ack)
            self._consume(ack)
            bottom = SLIDE_H_IN - 62.0 * PX_IN
        top = 44.0 * PX_IN
        return [_Region(Box(pad, top, content_w, max(bottom - top, 1.0)), self._children(host), anchor="middle")]

    def _render_medical_foot(self, pad: float, content_w: float) -> float:
        """Render the source lines and the page number; return the band's top.

        The band grows with the number of citations (a slide legitimately
        carries up to four), so the body region is measured against the real
        top of the band rather than a fixed footer height.
        """
        foot = self.article.find(class_="med-foot")
        if not isinstance(foot, Tag):
            return SLIDE_H_IN - 12.0 * PX_IN
        sources = foot.find(class_="med-sources")
        sources_w = content_w - 0.6
        height = 0.0
        if isinstance(sources, Tag):
            height = sum(b.height for b in self._collect_all(self._children(sources), sources_w))
        band_h = max(height + 14.0 * PX_IN, 34.0 * PX_IN)
        top = SLIDE_H_IN - band_h
        if isinstance(sources, Tag) and height:
            self._flow(_Region(Box(pad, top + 6.0 * PX_IN, sources_w, height), self._children(sources)))
        page = foot.find(class_="slide-foot-page")
        if isinstance(page, Tag):
            self._render_text(Box(SLIDE_W_IN - pad - 0.9, SLIDE_H_IN - 26.0 * PX_IN, 0.9, 0.22), page, anchor="middle")
        self._consume(foot)
        return top

    def _chrome_breathe(self) -> list[_Region]:
        """Degraded Breathe slide (SPEC-0023 FR-NEW-016): colour and background picture full bleed, content flowed.

        The background picture is the ``url()`` of the slide's ``med-bg-*`` class in the decoration block, read
        with its own pattern: a data URI holds a ``;`` that the declaration parser would split on.
        """
        canvas = Box.slide()
        props = style_props(self.article)
        fill = parse_color(props.get("background-color") or props.get("background"), self.res.css_vars)
        background = self.slide.background.fill  # the slide's own fill: the picture stays the first shape
        background.solid()
        background.fore_color.rgb = RGBColor.from_string(fill or self._element_color(self.article) or "FFFFFF")
        for name in classes(self.article):
            if name.startswith("med-bg-"):
                rule = re.search(
                    rf"\.{re.escape(name)}\s*\{{\s*background-image:\s*url\(([^)]*)\)", self.res.stylesheet
                )
                if rule:
                    self._add_picture(canvas, rule.group(1).strip("'\""), mode="stretch")
                break
        return [_Region(canvas.inset_px(56, 48), self._children(self.article))]

    def _chrome_generic(self) -> list[_Region]:
        """Fallback layout for documents without a known charter."""
        canvas = Box.slide()
        self._rect(canvas, fill=self._element_color(self.article) or "FFFFFF")
        return [_Region(canvas.inset_px(48, 40), self._children(self.article))]
