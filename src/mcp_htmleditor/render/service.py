"""Render one slide of a presentation to a PNG picture with Playwright's Chromium (SPEC-0008).

The file is only read: ``load_deck`` parses it and the browser opens it through ``file://``. Playwright is
imported inside the functions that need it, so a missing extra gives the install message, not an import error.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

from bs4.element import Tag

from ..deck import load_deck, slide_id
from ..tracing import trace_span
from . import CANVAS_HEIGHT, CANVAS_WIDTH, DEFAULT_SCALE, RenderError, RenderResult
from .files import picture_path, remove_stale, write_picture

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


def render_deck(file: str) -> RenderResult:
    """Write a PNG of the first slide of ``file`` at the default scale and clean up its stale pictures."""
    slides = _presentation_slides(file)
    target = slides[0]
    width, height = expected_size(str(DEFAULT_SCALE))
    with trace_span(
        "render.session", {"render.mode": "picture", "render.slides": len(slides), "render.scale": str(DEFAULT_SCALE)}
    ):
        data = _capture(file, target, (width, height))
        path = picture_path(file, target.slide_id)
        write_picture(path, data)
        remove_stale(file, [ref.slide_id for ref in slides], path)
    return RenderResult(path, width, height, target.slide_id)


def expected_size(scale_text: str) -> tuple[int, int]:
    """``round(960 x scale)`` by ``round(540 x scale)``, half up, from the text of the scale."""
    scale = Decimal(scale_text)
    return _round_half_up(CANVAS_WIDTH * scale), _round_half_up(CANVAS_HEIGHT * scale)


def _round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _presentation_slides(file: str) -> tuple[SlideRef, ...]:
    deck = load_deck(file)
    tags = [tag for tag in deck.soup.find_all(attrs={"data-type": "slide"}) if isinstance(tag, Tag)]
    if deck.doc_type != "presentation" or not tags:
        raise RenderError(f"render needs a presentation: {file}")
    return tuple(SlideRef(i, slide_id(tag) or f"slide-{i}") for i, tag in enumerate(tags))


def _capture(file: str, target: SlideRef, size: tuple[int, int]) -> bytes:
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        raise RenderError(INSTALL_MESSAGE) from None
    try:
        with sync_playwright() as driver:
            browser = _launch(driver, Error)
            try:
                data = _shoot(browser, file, target)
            finally:
                browser.close()
    except Error as exc:
        raise RenderError(f"Rendering failed: {_first_line(exc)}") from exc
    _check_size(data, size)
    return data


def _launch(driver: Playwright, error_type: type[Exception]) -> Browser:
    try:
        return driver.chromium.launch()
    except error_type as exc:
        if MISSING_EXECUTABLE in str(exc):
            raise RenderError(INSTALL_MESSAGE) from None
        raise RenderError(f"Chromium could not start: {_first_line(exc)}") from exc


def _shoot(browser: Browser, file: str, target: SlideRef) -> bytes:
    viewport: ViewportSize = {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    context = browser.new_context(viewport=viewport, device_scale_factor=DEFAULT_SCALE, color_scheme="light")
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
