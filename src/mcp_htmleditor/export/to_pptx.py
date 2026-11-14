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

Fidelity notes live in ``skill/topics/export.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag
from pptx import Presentation
from pptx.util import Inches

from ..tracing import trace_span
from .pptx_arch import ArchMixin
from .pptx_blocks import BlocksMixin
from .pptx_chrome import ChromeMixin
from .pptx_flow import FlowMixin
from .pptx_gantt import GanttMixin
from .pptx_images import ImagesMixin
from .pptx_model import (
    NOTES_ROLE,
    ExportReport,
    _BuilderBase,
    _column_widths,  # noqa: F401 - re-exported, imported from here by the tests
    _Context,
)
from .pptx_paint import paint_presentation
from .pptx_style import (
    SLIDE_H_IN,
    SLIDE_W_IN,
    StyleResolver,
    classes,
    has_class,
)
from .pptx_text import TextMixin
from .pptx_vectors import vector_figure_warnings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def to_pptx(input_html: str, output_pptx: str, *, paint: bool = True) -> ExportReport:
    """Convert an HTML presentation to a PPTX file.

    Args:
        input_html: Path to the source HTML file.
        output_pptx: Destination path of the generated ``.pptx``.
        paint: Repaint the slides from the rendered HTML (needs Chromium). ``False`` keeps the flow build, which is
            also the degraded result when the render is unavailable.

    Returns:
        An :class:`ExportReport` with the number of slides written and the list
        of warnings (missing images, unsupported components, empty documents).
    """
    with trace_span("export.pptx", {"file.path": str(Path(input_html).resolve())}) as span:
        report = _build_pptx(input_html, output_pptx, paint)
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


def _build_pptx(input_html: str, output_pptx: str, paint: bool = True) -> ExportReport:
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
    vector_warnings: list[str] = []
    for index, article in enumerate(articles):
        for warning in vector_figure_warnings(article, index + 1):
            report.warn(warning)
            vector_warnings.append(warning)
        slide = prs.slides.add_slide(blank_layout)
        _SlideBuilder(context, slide, article, index).build()

    if paint and articles and articles[0] is not soup.body and paint_presentation(prs, source, report):
        # SPEC-0024: every presentation is repainted from the rendered HTML; the flowed slides stay when Chromium is
        # unavailable (degraded export, one warning). The notes pages are kept either way. The painted slides carry
        # the vector figures as pictures, so their "ignored" warnings no longer apply.
        report.warnings[:] = [w for w in report.warnings if w not in vector_warnings]

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


class _SlideBuilder(ArchMixin, BlocksMixin, ChromeMixin, FlowMixin, GanttMixin, ImagesMixin, TextMixin, _BuilderBase):
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
        elif self.theme.key == "breathe":
            regions = self._chrome_breathe()
        else:
            regions = self._chrome_generic()
        for region in regions:
            self._flow(region)
        self._write_notes()

    def _write_notes(self) -> None:
        """Copy the speaker notes aside (direct child) onto the notes page; no aside, no notes slide."""
        for child in self.article.children:
            if isinstance(child, Tag) and child.get("data-role") == NOTES_ROLE:
                text = child.get_text()
                if text.strip():
                    self.slide.notes_slide.notes_text_frame.text = text.strip("\n")
                return

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


__all__ = ["ExportReport", "find_slides", "to_pptx"]
