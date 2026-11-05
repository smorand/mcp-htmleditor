"""Render one slide of a presentation to a PNG picture with Playwright's Chromium (SPEC-0008).

The file is only read: ``load_deck`` parses it and the browser opens it through ``file://``. Playwright is
imported inside the functions that need it, so a missing extra gives the install message, not an import error.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

from bs4.element import Tag

from ..deck import load_deck, slide_id
from ..tracing import trace_span
from . import CANVAS_HEIGHT, CANVAS_WIDTH, RenderError, RenderProblem, RenderResult
from .files import picture_path, remove_stale, write_picture
from .options import check_options, output_size, parse_scale
from .problems import NO_SLIDE, RawSlide, build_problems, shorten_source
from .scripts import IMAGES_JS, MEASURE_SLIDE_JS, SHOW_SLIDE_JS

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Error, FloatRect, Page, Playwright, ViewportSize

INSTALL_MESSAGE: Final = "Rendering needs Chromium. Install it with: make install-browser"
MISSING_EXECUTABLE: Final = "Executable doesn't exist"
VIEWPORT_WIDTH: Final = 1280
VIEWPORT_HEIGHT: Final = 900
LOAD_TIMEOUT_MS: Final = 15_000
REASON_MAX_CHARS: Final = 200
PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
IHDR_SIZE_OFFSET: Final = 16
SLIDE_SELECTOR: Final = '[data-type="slide"]'


@dataclass(frozen=True, slots=True)
class SlideRef:
    """A slide of the presentation: its position and its id."""

    index: int
    slide_id: str


class PageSignals:
    """Script errors of a page (DEC-012): each is kept once per (slide, text) with the slide shown when it came.

    ``current`` is ``-`` until a slide is shown, so a page load error is attributed to ``-``.
    """

    __slots__ = ("_seen", "current", "errors")

    def __init__(self) -> None:
        self.current = NO_SLIDE
        self.errors: list[RenderProblem] = []
        self._seen: set[tuple[str, str]] = set()

    def record(self, name: str, message: str) -> None:
        """Keep ``<name>: <message>`` for the slide being shown, unless the pair was already kept."""
        text = f"{name}: {message}"
        if (self.current, text) not in self._seen:
            self._seen.add((self.current, text))
            self.errors.append(RenderProblem("script", self.current, text))


@dataclass(frozen=True, slots=True)
class Measured:
    """What a run measured: the slides, the images that did not load and the script errors."""

    slides: list[RawSlide]
    images: list[RenderProblem]
    errors: list[RenderProblem]

    def problems(self) -> tuple[RenderProblem, ...]:
        return tuple(build_problems(self.slides, self.images, self.errors))


def render_deck(
    file: str,
    *,
    slide: str | None = None,
    scale: str | float | None = None,
    report: bool = False,
    report_only: bool = False,
) -> RenderResult:
    """Write a PNG of ``slide`` (default the first) of ``file`` at ``scale`` and clean up its stale pictures.

    With ``report`` the rendered slide is also measured and its layout problems are returned. With
    ``report_only`` every slide is measured, no picture is written and the output directory is not touched.

    Checks run in this order: option conflict, scale, file, presentation, browser, slide id.
    """
    check_options(slide=slide, scale=scale, report=report, report_only=report_only)
    factor = parse_scale(scale)
    size = output_size(factor)
    slides = _presentation_slides(file)
    if report_only:
        return _report_only(file, slides)
    with trace_span(
        "render.session",
        {"render.mode": "report" if report else "picture", "render.slides": len(slides), "render.scale": str(factor)},
    ):
        target, data, measured = _capture(file, slides, slide, factor, report)
        path = picture_path(file, target.slide_id)
        write_picture(path, data)
        remove_stale(file, [ref.slide_id for ref in slides], path)
    problems = measured.problems() if measured else ()
    return RenderResult(path, size[0], size[1], target.slide_id, problems)


def _report_only(file: str, slides: Sequence[SlideRef]) -> RenderResult:
    with trace_span("render.session", {"render.mode": "report_only", "render.slides": len(slides)}):
        measured = _in_browser(lambda browser: _measure_all(browser, file, slides))
    return RenderResult(None, None, None, None, measured.problems())


def _presentation_slides(file: str) -> tuple[SlideRef, ...]:
    deck = load_deck(file)
    tags = [tag for tag in deck.soup.find_all(attrs={"data-type": "slide"}) if isinstance(tag, Tag)]
    if deck.doc_type != "presentation" or not tags:
        raise RenderError(f"render needs a presentation: {file}")
    return tuple(SlideRef(i, slide_id(tag) or f"slide-{i}") for i, tag in enumerate(tags))


def _capture(
    file: str, slides: Sequence[SlideRef], slide: str | None, scale: Decimal, report: bool
) -> tuple[SlideRef, bytes, Measured | None]:
    def work(browser: Browser) -> tuple[SlideRef, bytes, Measured | None]:
        target = _choose_slide(slides, slide)
        data, measured = _shoot(browser, file, target, scale, report)
        return target, data, measured

    target, data, measured = _in_browser(work)
    _check_size(data, output_size(scale))
    return target, data, measured


def _in_browser[T](work: Callable[[Browser], T]) -> T:
    """Run ``work`` with a launched Chromium, closed afterwards; Playwright errors become ``RenderError``."""
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        raise RenderError(INSTALL_MESSAGE) from None
    try:
        with sync_playwright() as driver:
            browser = _launch(driver, Error)
            try:
                return work(browser)
            finally:
                browser.close()
    except Error as exc:
        raise RenderError(f"Rendering failed: {_first_line(exc)}") from exc


def _choose_slide(slides: Sequence[SlideRef], slide: str | None) -> SlideRef:
    if slide is None:
        return slides[0]
    for ref in slides:
        if ref.slide_id == slide:
            return ref
    valid = ", ".join(ref.slide_id for ref in slides)
    raise RenderError(f'Unknown slide id "{slide}". Valid ids: {valid}')


def _launch(driver: Playwright, error_type: type[Exception]) -> Browser:
    try:
        return driver.chromium.launch()
    except error_type as exc:
        if MISSING_EXECUTABLE in str(exc):
            raise RenderError(INSTALL_MESSAGE) from None
        raise RenderError(f"Chromium could not start: {_first_line(exc)}") from exc


def _shoot(
    browser: Browser, file: str, target: SlideRef, scale: Decimal, report: bool
) -> tuple[bytes, Measured | None]:
    page, signals = _open_page(browser, file, float(scale))
    raw = _measure(page, target, signals) if report else None
    if raw is None:
        page.evaluate(SHOW_SLIDE_JS, target.index)
    box = page.locator(SLIDE_SELECTOR).nth(target.index).bounding_box()
    if box is None:
        raise RenderError("Rendering failed: the slide has no box")
    clip: FloatRect = {"x": round(box["x"]), "y": round(box["y"]), "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT}
    data = page.screenshot(clip=clip, animations="disabled")
    if raw is None:
        return data, None
    return data, _only_rendered(Measured([raw], _failed_images(page, [target]), signals.errors), target)


def _only_rendered(measured: Measured, target: SlideRef) -> Measured:
    """Keep the images of the rendered slide and the script errors of the page load and of that slide."""
    images = [p for p in measured.images if p.slide == target.slide_id]
    errors = [p for p in measured.errors if p.slide in (NO_SLIDE, target.slide_id)]
    return Measured(measured.slides, images, errors)


def _open_page(browser: Browser, file: str, device_scale: float) -> tuple[Page, PageSignals]:
    viewport: ViewportSize = {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    context = browser.new_context(viewport=viewport, device_scale_factor=device_scale, color_scheme="light")
    page = context.new_page()
    signals = PageSignals()

    def on_error(error: Error) -> None:
        signals.record(error.name or "Error", error.message)

    page.on("pageerror", on_error)
    page.goto(Path(file).resolve().as_uri(), wait_until="load", timeout=LOAD_TIMEOUT_MS)
    return page, signals


def _measure_all(browser: Browser, file: str, slides: Sequence[SlideRef]) -> Measured:
    page, signals = _open_page(browser, file, 1.0)
    raws = [_measure(page, ref, signals) for ref in slides]
    return Measured(raws, _failed_images(page, slides), signals.errors)


def _measure(page: Page, target: SlideRef, signals: PageSignals) -> RawSlide:
    signals.current = target.slide_id
    measured = page.evaluate(MEASURE_SLIDE_JS, target.index)
    return RawSlide(
        target.slide_id, target.index, int(measured["content"]), tuple(measured["clipped"]), tuple(measured["fonts"])
    )


def _failed_images(page: Page, slides: Sequence[SlideRef]) -> list[RenderProblem]:
    ids = {ref.index: ref.slide_id for ref in slides}
    return [
        RenderProblem("image", ids[item["slide_index"]], f"{shorten_source(item['src'])} did not load")
        for item in page.evaluate(IMAGES_JS)
        if item["slide_index"] in ids
    ]


def _check_size(data: bytes, expected: tuple[int, int]) -> None:
    header = data[: IHDR_SIZE_OFFSET + 8]
    if not header.startswith(PNG_SIGNATURE) or len(header) < IHDR_SIZE_OFFSET + 8:
        raise RenderError("Rendering failed: the browser did not return a PNG picture")
    actual = struct.unpack(">II", header[IHDR_SIZE_OFFSET:])
    if actual != expected:
        raise RenderError(f"Rendering failed: picture is {actual[0]}x{actual[1]}, expected {expected[0]}x{expected[1]}")


def _first_line(exc: Exception) -> str:
    lines = str(exc).strip().splitlines()
    return (lines[0] if lines else type(exc).__name__)[:REASON_MAX_CHARS]
