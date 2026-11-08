"""The pointer dot, the L key and the deck's own Pointeur control, Deck P opened directly (SPEC-0017, US-0102).

Every test reloads Deck P as a ``file://`` URL in the module page (DEC-017) and reads the pointer through
``POINTER_STATE``. Pixels under the dot (E2E-023) come from a screenshot read with Pillow.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import Page

from tests.conftest import needs_chromium
from tests.pointer_support import (
    deck_p_path,
    open_deck_p,
    pointer_file_page,
    pointer_state,
    print_pdf_normalized,
    wait_presenting,
    wait_state,
)

__all__ = ["deck_p_path", "pointer_file_page"]

CENTRE = (800, 450)
DOT_DIAMETER = 30  # 18 slide pixels at the scale factor 1600 / 960
RED = (0xFA, 0x4D, 0x56)
WHITE = (0xFF, 0xFF, 0xFF)
HALO_RADIUS = 16.7  # mid halo: the disc ends at 15, the 2 slide pixel halo at 15 + 3.33
COLOUR_TOLERANCE = 8
NAME = "Présenter avec le pointeur (L)"
REFUSE_FULLSCREEN = "() => { Element.prototype.requestFullscreen = () => Promise.reject(new TypeError('refused')); }"
CURRENT_SLIDE_HTML = "document.querySelector('[data-type=\"slide\"].active').outerHTML"
CURSOR_AT = "([x, y]) => getComputedStyle(document.elementFromPoint(x, y)).cursor"
MOUSE_LEAVES = (
    "([x, y]) => document.elementFromPoint(x, y).dispatchEvent("
    "new MouseEvent('mouseout', {bubbles: true, relatedTarget: null, clientX: x, clientY: y}))"
)


def _dot_at(x: float, y: float) -> object:
    return lambda s: s["dot"] is not None and abs(s["dot"]["x"] - x) <= 1 and abs(s["dot"]["y"] - y) <= 1


def _present_with_f(page: Page) -> None:
    page.keyboard.press("f")
    wait_presenting(page)


def _pointer_on(page: Page) -> None:
    page.keyboard.press("l")
    wait_state(page, lambda s: s["on"], "pointer on")


def _close(pixel: tuple[int, ...], colour: tuple[int, int, int]) -> bool:
    return all(abs(pixel[i] - colour[i]) <= COLOUR_TOLERANCE for i in range(3))


def _assert_dot_pixels(page: Page) -> None:
    x, y = CENTRE
    shot = page.screenshot(clip={"x": x - 20, "y": y - 20, "width": 40, "height": 40})
    image = Image.open(io.BytesIO(shot)).convert("RGB")
    centre = image.getpixel((20, 20))
    assert isinstance(centre, tuple)
    assert _close(centre, RED), f"centre pixel {centre}"
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        px = image.getpixel((round(20 + dx * HALO_RADIUS), round(20 + dy * HALO_RADIUS)))
        assert isinstance(px, tuple)
        assert _close(px, WHITE), f"halo pixel {px} towards {(dx, dy)}"


@needs_chromium
def test_pointer_dot_l_in_a_deck_opened_directly(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-001."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path)
    page.mouse.move(*CENTRE)
    _present_with_f(page)
    page.mouse.move(801, 450)
    before = pointer_state(page)
    assert before["dot"] is None and not before["layer"]
    assert before["cursor"] != "none"

    page.keyboard.press("l")
    wait_state(page, _dot_at(801, 450), "a dot at (801, 450) right after L, no further move")

    page.mouse.move(400, 300)
    after = wait_state(page, _dot_at(400, 300), "the dot following the mouse to (400, 300)")
    assert after["dot"]["d"] == pytest.approx(DOT_DIAMETER, abs=1)
    assert after["cursor"] == "none"


@needs_chromium
def test_pointer_dot_deck_control_by_keyboard(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-005."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path)
    page.focus("#btn-present")
    page.keyboard.press("Tab")
    focused = page.evaluate(
        "(() => { const e = document.activeElement;"
        " return [e.id, e.textContent.trim(), e.getAttribute('aria-label'), e.title]; })()"
    )
    assert focused == ["btn-pointer", "Pointeur", NAME, NAME]

    page.keyboard.press("Enter")
    page.mouse.move(*CENTRE)
    state = wait_state(page, _dot_at(*CENTRE), "the deck presented with the dot shown")
    assert state["fullscreen"] == "HTML"


@needs_chromium
def test_pointer_dot_l_outside_a_presentation(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-017."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path)
    box = page.locator("#slide-0").bounding_box()
    assert box is not None
    over = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*over)
    slide = page.evaluate(CURRENT_SLIDE_HTML)

    page.keyboard.press("l")
    state = pointer_state(page)
    assert (state["on"], state["layer"], state["fullscreen"], state["current"]) == (False, False, None, 0)
    assert page.evaluate(CURRENT_SLIDE_HTML) == slide

    _present_with_f(page)
    page.mouse.move(*CENTRE)
    page.mouse.move(810, 460)
    presented = pointer_state(page)
    assert (presented["on"], presented["layer"], presented["dot"]) == (False, False, None)
    assert presented["cursor"] != "none"
    _pointer_on(page)  # control: the absences above come from the rules, not from a deck without pointer


@needs_chromium
def test_pointer_dot_modifier_keys_with_l(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-020."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path)
    page.mouse.move(*CENTRE)
    _present_with_f(page)
    slide = page.evaluate(CURRENT_SLIDE_HTML)
    for chord in ("Alt+l", "Control+l", "Meta+l"):
        page.keyboard.press(chord)
        state = pointer_state(page)
        assert (state["on"], state["layer"], state["dot"], state["current"]) == (False, False, None, 0), chord
        assert page.evaluate(CURRENT_SLIDE_HTML) == slide, chord
    _pointer_on(page)  # control: a bare L does toggle in the same state


@needs_chromium
def test_pointer_dot_over_the_black_margins(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-021: 1600 by 1000, black bands of 50 pixels above and below the slide."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path, height=1000)
    _present_with_f(page)
    _pointer_on(page)

    page.mouse.move(800, 20)
    page.mouse.move(800, 21)
    margin = pointer_state(page)
    assert margin["on"] and margin["dot"] is None
    assert page.evaluate(CURSOR_AT, [800, 20]) != "none"

    page.mouse.move(800, 500)
    wait_state(page, _dot_at(800, 500), "the dot at (800, 500) over the slide")


@needs_chromium
def test_pointer_dot_mouse_leaves_the_window(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-022."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path)
    _present_with_f(page)
    _pointer_on(page)
    page.mouse.move(*CENTRE)
    wait_state(page, _dot_at(*CENTRE), "the dot at the centre")

    page.evaluate(MOUSE_LEAVES, list(CENTRE))
    wait_state(page, lambda s: s["on"] and s["dot"] is None, "no dot once the mouse left the window")


@needs_chromium
def test_pointer_dot_visible_on_dark_and_light_slides(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-023."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path)
    page.mouse.move(*CENTRE)
    _present_with_f(page)
    _pointer_on(page)
    wait_state(page, _dot_at(*CENTRE), "the dot on slide 1")
    _assert_dot_pixels(page)

    page.keyboard.press("ArrowRight")
    wait_state(page, lambda s: s["current"] == 1 and _dot_at(*CENTRE)(s), "the dot on slide 2")
    _assert_dot_pixels(page)


@needs_chromium
def test_pointer_dot_control_when_full_screen_is_refused(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-039."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path)
    page.evaluate(REFUSE_FULLSCREEN)
    page.mouse.move(*CENTRE)
    baseline = print_pdf_normalized(page)
    assert print_pdf_normalized(page) == baseline, "two prints of the unchanged page differ"
    slide = page.evaluate(CURRENT_SLIDE_HTML)

    assert page.locator("#btn-pointer").count() == 1, "the deck has no #btn-pointer"
    page.click("#btn-pointer")
    page.keyboard.press("l")
    page.mouse.move(*CENTRE)
    page.mouse.move(801, 451)
    page.mouse.move(*CENTRE)
    state = pointer_state(page)
    assert (state["fullscreen"], state["on"], state["layer"], state["dot"]) == (None, False, False, None)
    assert page.evaluate(CURRENT_SLIDE_HTML) == slide
    assert print_pdf_normalized(page) == baseline
