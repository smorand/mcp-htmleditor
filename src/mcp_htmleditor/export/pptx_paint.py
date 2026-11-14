"""Painted PPTX export of every presentation (SPEC-0023, SPEC-0024 FR-1, FR-7, FR-8).

After the flowed build (kept as the degraded result), this module opens the deck in Playwright's Chromium, measures
every slide with the generic script of ``pptx_paint_js.py`` (slide pixels scaled to the 960 x 540 point slide) and
repaints each PPTX slide from the measures: slide colour, gradient and picture, boxes (fill, gradient, per side
borders, radius, opacity, shadow), pictures with their ``object-fit`` crop, ``<svg>`` and ``<canvas>`` rasterised
by the browser, native tables, and text as editable text boxes with the browser's own line breaks, runs and list
markers. Nothing here knows a charter: the browser computes, this module writes. The shape writers live in
``pptx_paint_shapes.py``, ``pptx_paint_text.py`` and ``pptx_paint_tables.py``; the pure CSS mappings in
``pptx_paint_style.py``. The notes page written by the flow build is kept: only the shapes are cleared.

Ported from the post export script of the first painted charter (2026-11-13), then generalised (2026-11-14): the
slide shown by the render's ``SHOW_SLIDE_JS``, remote requests aborted, remote and missing pictures skipped with the
exporter's warnings.
"""

from __future__ import annotations

import base64
import logging
import queue
import re
import threading
from pathlib import Path
from typing import Any, Final

from ..render.scripts import SHOW_SLIDE_JS
from ..tracing import trace_span
from .pptx_model import ExportReport
from .pptx_paint_js import MEASURE_JS
from .pptx_paint_shapes import ShapesMixin
from .pptx_paint_tables import TablesMixin
from .pptx_paint_text import TextMixin

logger = logging.getLogger(__name__)

VIEWPORT: Final = {"width": 1280, "height": 900}  # the viewport of the product render
RASTER_SCALE: Final = 2
TIMEOUT_MS: Final = 30_000
SLIDE_TIMEOUT_S = 30  # FR-8: a slide rendering longer degrades the export (module level for the tests)
READY_TIMEOUT_S = 90  # launch plus the deck load (its own 30 s bound)
MISSING_EXECUTABLE: Final = "Executable doesn't exist"
REASON_MAX_CHARS: Final = 200
DEGRADED: Final = "Deck exported without the rendered finish ({reason}). Install the browser with: make install-browser"
NO_EXTRA: Final = "the render extra is not installed"
NO_CHROMIUM: Final = "Chromium is not installed"
UNHIDE_JS: Final = (
    "() => document.querySelectorAll('[data-type=\"slide\"]').forEach((s) => s.style.removeProperty('display'))"
)
FREEZE_CSS: Final = "*{animation:none!important;transition:none!important}.slide{scale:1!important}"
REMOTE: Final = re.compile(r"^https?://")


class PaintUnavailable(Exception):  # noqa: N818 - a reason, not an error the caller reports as such
    """The rendered finish cannot run; ``reason`` is the text of the degraded export warning."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def paint_presentation(prs: Any, html_path: Path, report: ExportReport) -> bool:
    """Repaint every slide of ``prs`` from the deck at ``html_path``; on failure keep the flowed slides and warn once.

    Returns True when the slides were painted. Time O(e) for e measured elements; the pictures are decoded once
    per item (python-pptx stores each distinct picture once).
    """
    count = len(prs.slides)
    with trace_span("export.pptx.paint", {"slide.count": count}) as span:
        try:
            pages = measure(html_path, count)
        except PaintUnavailable as exc:
            span.set_attribute("paint.degraded", True)
            report.warn(DEGRADED.format(reason=exc.reason))
            logger.warning("PPTX export degraded: %s", exc.reason)
            return False
        painter_base = html_path.resolve().parent
        items = 0
        for slide, page in zip(prs.slides, pages, strict=True):
            items += Painter(slide, report, painter_base).paint(page)
        span.set_attribute("paint.items", items)
    return True


def measure(html_path: Path, count: int) -> list[list[dict[str, Any]]]:
    """The paint list of the first ``count`` slides, measured in Chromium; ``PaintUnavailable`` when it cannot run.

    Runs in a daemon thread of its own: Playwright's sync API refuses a thread that already holds an asyncio loop
    (an embedding application, a test session), and a slide that renders for longer than ``SLIDE_TIMEOUT_S`` must
    degrade the export instead of blocking it (FR-8). The worker reports each measured slide on a queue; the
    caller stops waiting at the first missed deadline (a hung worker is left to die with the process).
    """
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    worker = threading.Thread(target=_measure_worker, args=(html_path, count, events), name="pptx-paint", daemon=True)
    worker.start()
    measured = 0
    bound = READY_TIMEOUT_S
    while True:
        try:
            kind, value = events.get(timeout=bound)
        except queue.Empty:
            if measured == 0 and bound == READY_TIMEOUT_S:
                raise PaintUnavailable(
                    f"the render failed: the deck did not load within {READY_TIMEOUT_S} seconds"
                ) from None
            raise PaintUnavailable(
                f"the render failed: slide {measured + 1} did not render within {SLIDE_TIMEOUT_S} seconds"
            ) from None
        if kind == "error":
            raise value
        if kind == "done":
            return list(value)
        if kind == "slide":
            measured += 1
        bound = SLIDE_TIMEOUT_S


def _measure_worker(html_path: Path, count: int, events: queue.Queue[tuple[str, Any]]) -> None:
    """Thread body: the pages measured, or the reason they could not be."""
    try:
        events.put(("done", _measure_in_browser(html_path, count, events)))
    except PaintUnavailable as exc:
        events.put(("error", exc))


def _measure_in_browser(
    html_path: Path, count: int, events: queue.Queue[tuple[str, Any]]
) -> list[list[dict[str, Any]]]:
    try:
        from playwright.sync_api import Error, sync_playwright  # noqa: PLC0415 - optional render extra
    except ImportError:
        raise PaintUnavailable(NO_EXTRA) from None
    try:
        with sync_playwright() as driver:
            try:
                browser = driver.chromium.launch()
            except Error as exc:
                if MISSING_EXECUTABLE in str(exc):
                    raise PaintUnavailable(NO_CHROMIUM) from None
                raise PaintUnavailable(f"Chromium could not start: {_first_line(exc)}") from None
            try:
                return _measure_pages(browser, html_path, count, events)
            finally:
                browser.close()
    except PaintUnavailable:
        raise
    except Exception as exc:
        raise PaintUnavailable(f"the render failed: {_first_line(exc)}") from None


def _measure_pages(
    browser: Any, html_path: Path, count: int, events: queue.Queue[tuple[str, Any]]
) -> list[list[dict[str, Any]]]:
    page = browser.new_page(viewport=VIEWPORT, device_scale_factor=RASTER_SCALE, color_scheme="light")
    page.set_default_timeout(TIMEOUT_MS)
    page.route(REMOTE, lambda route: route.abort())
    page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=TIMEOUT_MS)
    page.add_style_tag(content=FREEZE_CSS)
    page.evaluate("document.fonts.ready")
    found = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-type=\"slide\"]'))"
        ".filter((s) => !s.parentElement.closest('[data-type=\"slide\"]')).length"
    )
    if found != count:
        raise PaintUnavailable(f"the render failed: {found} slides rendered for {count} exported")
    events.put(("ready", None))
    pages = []
    for index in range(count):
        pages.append(_measure_slide(page, index))
        events.put(("slide", index))
    return pages


def _measure_slide(page: Any, index: int) -> list[dict[str, Any]]:
    """Show slide ``index`` alone and return its paint list."""
    # SHOW_SLIDE_JS hides the other slides with an inline display: clear it first, or the next slide shown
    # keeps an inline "block" instead of its own (flex) display and its pushed or centred content moves.
    page.evaluate(UNHIDE_JS)
    page.evaluate(SHOW_SLIDE_JS, index)
    items: list[dict[str, Any]] = page.evaluate(MEASURE_JS, index)
    return _rasterise(page, items)


def _first_line(exc: BaseException) -> str:
    lines = str(exc).strip().splitlines()
    return (lines[0] if lines else type(exc).__name__)[:REASON_MAX_CHARS]


def _rasterise(page: Any, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace each ``raster`` item (svg, canvas, vector image) by the picture the browser draws of it, at 2x."""
    from playwright.sync_api import Error  # noqa: PLC0415 - optional render extra, already loaded by the caller

    result = []
    for item in items:
        if item["kind"] != "raster":
            result.append(item)
            continue
        try:
            png = page.locator(f'[data-pptx-raster="{item["rid"]}"]').first.screenshot(type="png", timeout=TIMEOUT_MS)
        except Error as exc:
            logger.warning("Figure not rasterised: %s", _first_line(exc))
            result.append({"kind": "lost"})
            continue
        source = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        result.append(
            {
                "kind": "pic",
                "box": item["box"],
                "src": source,
                "fit": "fill",
                "op": item.get("op", 1.0),
                "alt": item.get("alt", ""),
            }
        )
    return result


class Painter(ShapesMixin, TextMixin, TablesMixin):
    """Repaints one PPTX slide from the measured HTML slide."""

    def __init__(self, slide: Any, report: ExportReport, base_dir: Path) -> None:
        self.slide = slide
        self.report = report
        self.base_dir = base_dir

    def paint(self, items: list[dict[str, Any]]) -> int:
        """Clear the slide's shapes, then draw the items in order; return how many were drawn."""
        tree = self.slide.shapes._spTree
        for shape in list(self.slide.shapes):
            tree.remove(shape._element)
        drawers = {
            "slide": self.background,
            "rect": self.rect,
            "pic": self.picture,
            "text": self.text,
            "table": self.table,
            "lost": self.lost,
        }
        for item in items:
            drawers[item["kind"]](item)
        return len(items)

    def lost(self, item: dict[str, Any]) -> None:
        self.report.warn("Figure (svg, canvas) non rasterisee, ignoree.")
