"""Render one slide of a presentation to a PNG picture with Playwright's Chromium (SPEC-0008).

The file is only read: ``load_deck`` parses it and the browser opens it through ``file://``. Playwright is
imported inside the functions that need it, so a missing extra gives the install message, not an import error.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

from bs4.element import Tag

from ..deck import load_deck, slide_id
from ..tracing import trace_span
from . import CANVAS_HEIGHT, CANVAS_WIDTH, RenderError, RenderResult
from .files import picture_path, remove_stale, write_picture
from .options import output_size, parse_scale

if TYPE_CHECKING:
    from playwright.sync_api import Browser, FloatRect, Playwright, ViewportSize

INSTALL_MESSAGE: Final = "Rendering needs Chromium. Install it with: make install-browser"
MISSING_EXECUTABLE: Final = "Executable doesn't exist"
VIEWPORT_WIDTH: Final = 1280
VIEWPORT_HEIGHT: Final = 900
LOAD_TIMEOUT_MS: Final = 15_000
REASON_MAX_CHARS: Final = 200
PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
IHDR_SIZE_OFFSET: Final = 16
SLIDE_SELECTOR: Final = '[data-type="slide"]'

# Shows the slide at index ``idx`` alone, in the live page; the file is never written.
SHOW_SLIDE_SCRIPT: Final = """async (idx) => {
  const slides = Array.from(document.querySelectorAll('[data-type="slide"]'));
  slides.forEach((slide, i) => {
    slide.classList.toggle('active', i === idx);
    if (i !== idx) slide.style.setProperty('display', 'none', 'important');
  });
  const target = slides[idx];
  if (getComputedStyle(target).display === 'none') target.style.setProperty('display', 'block');
  document.getAnimations().forEach((animation) => {
    try { animation.finish(); } catch (error) { animation.cancel(); }
  });
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}"""


@dataclass(frozen=True, slots=True)
class SlideRef:
    """A slide of the presentation: its position and its id."""

    index: int
    slide_id: str


def render_deck(file: str, *, slide: str | None = None, scale: str | float | None = None) -> RenderResult:
    """Write a PNG of ``slide`` (default the first) of ``file`` at ``scale`` and clean up its stale pictures.

    Checks run in this order: scale, file, presentation, browser, slide id.
    """
    factor = parse_scale(scale)
    size = output_size(factor)
    slides = _presentation_slides(file)
    with trace_span(
        "render.session", {"render.mode": "picture", "render.slides": len(slides), "render.scale": str(factor)}
    ):
        target, data = _capture(file, slides, slide, factor)
        path = picture_path(file, target.slide_id)
        write_picture(path, data)
        remove_stale(file, [ref.slide_id for ref in slides], path)
    return RenderResult(path, size[0], size[1], target.slide_id)


def _presentation_slides(file: str) -> tuple[SlideRef, ...]:
    deck = load_deck(file)
    tags = [tag for tag in deck.soup.find_all(attrs={"data-type": "slide"}) if isinstance(tag, Tag)]
    if deck.doc_type != "presentation" or not tags:
        raise RenderError(f"render needs a presentation: {file}")
    return tuple(SlideRef(i, slide_id(tag) or f"slide-{i}") for i, tag in enumerate(tags))


def _capture(file: str, slides: Sequence[SlideRef], slide: str | None, scale: Decimal) -> tuple[SlideRef, bytes]:
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        raise RenderError(INSTALL_MESSAGE) from None
    try:
        with sync_playwright() as driver:
            browser = _launch(driver, Error)
            try:
                target = _choose_slide(slides, slide)
                data = _shoot(browser, file, target, scale)
            finally:
                browser.close()
    except Error as exc:
        raise RenderError(f"Rendering failed: {_first_line(exc)}") from exc
    _check_size(data, output_size(scale))
    return target, data


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


def _shoot(browser: Browser, file: str, target: SlideRef, scale: Decimal) -> bytes:
    viewport: ViewportSize = {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    context = browser.new_context(viewport=viewport, device_scale_factor=float(scale), color_scheme="light")
    page = context.new_page()
    page.goto(Path(file).resolve().as_uri(), wait_until="load", timeout=LOAD_TIMEOUT_MS)
    page.evaluate(SHOW_SLIDE_SCRIPT, target.index)
    box = page.locator(SLIDE_SELECTOR).nth(target.index).bounding_box()
    if box is None:
        raise RenderError("Rendering failed: the slide has no box")
    clip: FloatRect = {"x": round(box["x"]), "y": round(box["y"]), "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT}
    return page.screenshot(clip=clip, animations="disabled")


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
