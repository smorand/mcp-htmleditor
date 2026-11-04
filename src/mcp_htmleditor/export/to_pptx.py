"""Export an mcp-htmleditor HTML presentation to PPTX with python-pptx.

Design
------
Every element carrying ``data-type="slide"`` becomes one 16:9 slide
(13.333 x 7.5 inches), which is the reference canvas of the templates
(960 x 540 CSS pixels, so one CSS pixel is one point). Nothing outside the
slides is exported: the navigation shell, ``<script>`` and ``<style>`` blocks
are skipped, which is what kept the previous version from being usable.

Inside a slide the exporter runs a small block flow engine:

1. the template chrome is drawn first (backgrounds, frames, footers) from
   ``data-slide-type`` and from the charter detected on the document;
2. the slide subtree is walked recursively and turned into an ordered list of
   blocks (text, tile grid, notification, table, gantt, arch diagram,
   annotated image, image, accent rule);
3. blocks are stacked vertically in their region, flexible blocks absorb the
   remaining space, and everything is scaled down when the content overflows.

Fidelity notes live in ``skill/workflow-export.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from ..tracing import trace_span
from .pptx_arch import ArchMixin
from .pptx_blocks import BlocksMixin
from .pptx_components import (
    color_of,
    inches,
    is_light,
)
from .pptx_gantt import GanttMixin
from .pptx_images import ImagesMixin
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
    ExportReport,
    _Block,
    _BuilderBase,
    _Column,
    _column_widths,
    _Context,
    _Para,
    _Region,
)
from .pptx_style import (
    PX_IN,
    SLIDE_H_IN,
    SLIDE_W_IN,
    Box,
    StyleResolver,
    TextStyle,
    block_height,
    classes,
    has_class,
    parse_color,
    parse_px,
    style_props,
)
from .pptx_text import TextMixin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def to_pptx(input_html: str, output_pptx: str) -> ExportReport:
    """Convert an HTML presentation to a PPTX file.

    Args:
        input_html: Path to the source HTML file.
        output_pptx: Destination path of the generated ``.pptx``.

    Returns:
        An :class:`ExportReport` with the number of slides written and the list
        of warnings (missing images, unsupported components, empty documents).
    """
    with trace_span("export.pptx", {"file.path": str(Path(input_html).resolve())}) as span:
        report = _build_pptx(input_html, output_pptx)
        span.set_attribute("slide.count", report.slide_count)
        span.set_attribute("warning.count", len(report.warnings))
        logger.info(
            "PPTX export: %s -> %s (%d slide(s), %d warning(s))",
            input_html,
            output_pptx,
            report.slide_count,
            len(report.warnings),
        )
        return report


def _build_pptx(input_html: str, output_pptx: str) -> ExportReport:
    """Do the actual HTML to PPTX conversion (see :func:`to_pptx`)."""
    source = Path(input_html)
    soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
    report = ExportReport()

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W_IN)
    prs.slide_height = Inches(SLIDE_H_IN)
    blank_layout = prs.slide_layouts[6]

    articles = find_slides(soup)
    if not articles:
        report.warn(
            'Aucun element data-type="slide" ni article.slide trouve: '
            "le corps du document est exporte comme une slide unique."
        )
        body = soup.body or soup
        articles = [body] if isinstance(body, Tag) else []

    resolver = StyleResolver.from_soup(soup)
    context = _Context(
        res=resolver,
        theme=resolver.theme,
        base_dir=source.resolve().parent,
        report=report,
    )
    for index, article in enumerate(articles):
        slide = prs.slides.add_slide(blank_layout)
        _SlideBuilder(context, slide, article, index).build()

    report.slide_count = len(prs.slides)
    report.charter = resolver.theme.key
    out = Path(output_pptx)
    out.parent.mkdir(parents=True, exist_ok=True)
    with trace_span("file.write", {"file.path": str(out), "export.format": "pptx"}):
        prs.save(str(out))
    return report


def find_slides(soup: BeautifulSoup) -> list[Tag]:
    """Return the slide elements of a document, outermost ones only.

    Detection is attribute based (``data-type="slide"``, any tag name), with a
    fallback on ``article.slide`` / ``section.slide`` for templates that do not
    carry the attribute.
    """
    tagged = [el for el in soup.find_all(attrs={"data-type": "slide"}) if isinstance(el, Tag)]
    if not tagged:
        tagged = [el for el in soup.find_all(["article", "section"]) if isinstance(el, Tag) and has_class(el, "slide")]
    return [el for el in tagged if not _has_slide_ancestor(el, tagged)]


def _has_slide_ancestor(element: Tag, slides: list[Tag]) -> bool:
    """Tell whether ``element`` is nested inside another detected slide."""
    known = {id(s) for s in slides}
    parent = element.parent
    while parent is not None:
        if id(parent) in known:
            return True
        parent = parent.parent
    return False


# ---------------------------------------------------------------------------
# Slide builder
# ---------------------------------------------------------------------------


class _SlideBuilder(ArchMixin, BlocksMixin, GanttMixin, ImagesMixin, TextMixin, _BuilderBase):
    """Render one HTML slide element onto one python-pptx slide."""

    def __init__(self, context: _Context, slide: Any, article: Tag, index: int) -> None:
        self.ctx = context
        self.res = context.res
        self.theme = context.theme
        self.slide = slide
        self.article = article
        self.index = index
        self.handled: set[int] = set()

    # -- entry point -------------------------------------------------------

    def build(self) -> None:
        """Draw the chrome then flow the content of the slide."""
        kind = self._slide_kind()
        # Slide level CSS variants (``.slide.dark`` ...) only apply to this
        # slide: publish its classes as the active scope of the resolver.
        self.res.active_scope = frozenset(classes(self.article))
        if self.theme.key == "ei":
            regions = self._chrome_ei(kind)
        elif self.theme.key == "carbon":
            regions = self._chrome_carbon()
        elif self.theme.key == "medical":
            regions = self._chrome_medical(kind)
        else:
            regions = self._chrome_generic()
        for region in regions:
            self._flow(region)

    def _slide_kind(self) -> str:
        """Return the ``data-slide-type`` of the slide, inferred when absent."""
        kind = str(self.article.get("data-slide-type") or "").strip()
        if kind:
            return kind
        if self.article.find(class_="slide-section-body") is not None:
            return "section"
        if self.article.find(class_="slide-cover-img") is not None:
            return "title"
        if self.article.find(class_="slide-inner") is not None:
            return "content"
        return ""

    # -- chrome ------------------------------------------------------------

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

    def _chrome_generic(self) -> list[_Region]:
        """Fallback layout for documents without a known charter."""
        canvas = Box.slide()
        self._rect(canvas, fill=self._element_color(self.article) or "FFFFFF")
        return [_Region(canvas.inset_px(48, 40), self._children(self.article))]

    # -- block flow --------------------------------------------------------

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


__all__ = ["ExportReport", "find_slides", "to_pptx"]
