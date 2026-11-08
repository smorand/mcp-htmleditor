"""The ring a click draws around its box, Deck P opened directly (SPEC-0017, US-0103).

Every test reloads Deck P as a ``file://`` URL in a module page (DEC-017): the shared 1600 by 900 page, a page
taking touch (E2E-026) and a page asking for reduced motion (E2E-027). "X ringed" is ``is_ringed``: one ring
whose outer edge lies 6 slide pixels (10 screen pixels at 1600 by 900) +-1 outside X's rect on every side.
Absences that follow a frame of the deck's loop are read after ``next_frames``; those that could follow a
navigation or a script are read after one ``settle`` per test.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page

from tests.browser_wait import settle, wait_until
from tests.conftest import needs_chromium
from tests.pointer_support import (
    RING_LINE,
    SCALE,
    click_centre,
    deck_p_path,
    is_ringed,
    next_frames,
    open_deck_p,
    pointer_file_page,
    pointer_reduced_page,
    pointer_state,
    pointer_touch_page,
    print_pdf_normalized,
    ring_around,
    wait_presenting,
    wait_ringed,
    wait_slide_settled,
    wait_state,
)

__all__ = ["deck_p_path", "pointer_file_page", "pointer_reduced_page", "pointer_touch_page"]

CENTRE = (800, 450)  # slide 1's empty middle (pointer_support.SLIDE_1_BODY)
RED = (0xDA, 0x1E, 0x28)
COLOUR_TOLERANCE = 40
FIRST_FRAME_AFTER_CLICK = """
() => { window.ringFirstFrame = 'unset'; window.addEventListener('click', () => requestAnimationFrame(() => {
  const ring = document.getElementById('deck-pointer-ring');
  const tile = document.getElementById('tile-a').getBoundingClientRect();
  if (!ring) { window.ringFirstFrame = null; return; }
  const r = ring.getBoundingClientRect();
  window.ringFirstFrame = ({animations: ring.getAnimations().length, opacity: getComputedStyle(ring).opacity,
           box: {left: tile.left, top: tile.top, width: tile.width, height: tile.height},
           ring: {left: r.left, top: r.top, width: r.width, height: r.height}, rings: 1});
}), {once: true}); }
"""


def _presented_pointer_on(page: Page, path: Path, width: int = 1600, height: int = 900) -> None:
    open_deck_p(page, path, width, height)
    page.keyboard.press("f")
    wait_presenting(page)
    page.keyboard.press("l")
    wait_state(page, lambda s: s["on"], "pointer on")
    wait_slide_settled(page)


def _no_ring(page: Page) -> bool:
    state = pointer_state(page)
    return state["ring"] is None and state["rings"] == 0


def _ring_a(page: Page) -> None:
    click_centre(page, "#tile-a")
    wait_ringed(page, "#tile-a")


@needs_chromium
def test_pointer_ring_headline_and_paragraph(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-007."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    click_centre(page, "#slide-0 strong")
    check = wait_ringed(page, "#slide-0 .slide-body p")
    assert not is_ringed({**check, "box": ring_around(page, "#slide-0 strong")["box"]})

    click_centre(page, "#slide-0 .slide-h1")
    wait_ringed(page, "#slide-0 .slide-h1")
    assert not is_ringed(ring_around(page, "#slide-0 .slide-header"))

    page.keyboard.press("End")
    wait_state(page, lambda s: s["current"] == 2 and s["ring"] is None, "slide 3 shown, no ring")
    wait_slide_settled(page)
    click_centre(page, "#panel p")
    wait_ringed(page, "#panel p")
    assert not is_ringed(ring_around(page, "#panel"))


@needs_chromium
def test_pointer_ring_click_ringed_box_again(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-009."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    _ring_a(page)
    click_centre(page, "#tile-a")
    next_frames(page)
    assert _no_ring(page)
    _ring_a(page)


@needs_chromium
def test_pointer_ring_click_outside_any_box(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-010."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    click_centre(page, "#tile-b")
    wait_ringed(page, "#tile-b")
    for _ in range(2):
        page.mouse.click(*CENTRE)
        next_frames(page)
        assert _no_ring(page)
        assert not is_ringed(ring_around(page, "#slide-0"))


@needs_chromium
def test_pointer_ring_only_one(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-011."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    _ring_a(page)
    click_centre(page, "#tile-b")
    check = wait_ringed(page, "#tile-b")
    assert check["rings"] == 1


@needs_chromium
def test_pointer_ring_removed_by_slide_change(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-012."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    _ring_a(page)

    page.keyboard.press("ArrowLeft")
    next_frames(page)
    assert pointer_state(page)["current"] == 0
    assert is_ringed(ring_around(page, "#tile-a"))

    page.keyboard.press("ArrowRight")
    wait_state(page, lambda s: s["current"] == 1 and s["ring"] is None and s["rings"] == 0, "slide 2, no ring")
    page.mouse.move(400, 300)
    state = wait_state(page, lambda s: s["dot"] is not None and abs(s["dot"]["x"] - 400) <= 1, "the dot on slide 2")
    assert abs(state["dot"]["y"] - 300) <= 1

    page.keyboard.press("ArrowLeft")
    wait_state(page, lambda s: s["current"] == 0, "slide 1 again")
    next_frames(page)
    assert _no_ring(page)

    # A click landing before the deck's next frame after a slide change rings on the new slide.
    page.evaluate("navigate(1); document.getElementById('edge-tile').click()")
    wait_ringed(page, "#edge-tile")


@needs_chromium
def test_pointer_ring_link_followed_ring_kept(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-013."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    _ring_a(page)
    click_centre(page, "#link-docs")
    settle(page)
    assert page.url.endswith("#docs")
    assert is_ringed(ring_around(page, "#tile-a"))


@needs_chromium
def test_pointer_ring_l_turns_off_and_on_without_ring(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-015."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    _ring_a(page)
    page.mouse.move(*CENTRE)

    page.keyboard.press("l")
    off = pointer_state(page)
    assert (off["on"], off["layer"], off["dot"], off["ring"], off["rings"]) == (False, False, None, None, 0)
    assert off["cursor"] != "none"

    page.keyboard.press("l")
    page.mouse.move(810, 460)
    on = wait_state(page, lambda s: s["dot"] is not None, "the dot back after the second L")
    next_frames(page)
    assert on["on"] and _no_ring(page)


@needs_chromium
def test_pointer_ring_leaving_ends_the_pointer(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-016."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    _ring_a(page)

    page.keyboard.press("Escape")
    wait_state(
        page,
        lambda s: (s["fullscreen"], s["on"], s["layer"], s["dot"], s["ring"]) == (None, False, False, None, None),
        "presenting left with no dot and no ring",
    )

    page.keyboard.press("f")
    wait_presenting(page)
    page.mouse.move(*CENTRE)
    next_frames(page)
    again = pointer_state(page)
    assert (again["on"], again["layer"], again["dot"], again["ring"], again["rings"]) == (False, False, None, None, 0)


@needs_chromium
def test_pointer_ring_l_typed_in_a_text_field(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-019."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    _ring_a(page)
    click_centre(page, "#note")
    page.keyboard.type("L")
    settle(page)
    assert page.input_value("#note") == "L"
    assert pointer_state(page)["on"]
    assert is_ringed(ring_around(page, "#tile-a"))


@needs_chromium
def test_pointer_ring_drawing_is_one_box(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-025."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path)
    click_centre(page, "#drawing circle")
    wait_ringed(page, "#drawing")


@needs_chromium
def test_pointer_ring_printing_while_pointing(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-030."""
    page = pointer_file_page
    open_deck_p(page, deck_p_path)
    page.keyboard.press("f")
    wait_presenting(page)
    wait_slide_settled(page)
    reference = print_pdf_normalized(page)
    assert print_pdf_normalized(page) == reference, "two prints of the unchanged page differ"

    page.keyboard.press("l")
    page.mouse.move(*CENTRE)
    wait_state(page, lambda s: s["dot"] is not None, "the dot shown")
    wait_slide_settled(page)
    _ring_a(page)
    assert print_pdf_normalized(page) == reference


@needs_chromium
def test_pointer_ring_clipped_at_the_slide_edge(pointer_file_page: Page, deck_p_path: Path) -> None:
    """E2E-037: at 1800 by 900 the slide (1600 by 900) has black bands of 100 pixels on each side."""
    page = pointer_file_page
    _presented_pointer_on(page, deck_p_path, width=1800)
    page.keyboard.press("ArrowRight")
    wait_state(page, lambda s: s["current"] == 1, "slide 2 shown")
    wait_slide_settled(page)
    click_centre(page, "#edge-tile")
    check = wait_ringed(page, "#edge-tile")
    box = check["box"]
    assert abs(box["left"] - 100) <= 1, f"Edge tile does not touch the slide's left edge: {box}"

    shot = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    line = RING_LINE * SCALE / 2  # the middle of the ring's line, 4.5 + 2.5 screen pixels outside the box
    outside = 6 * SCALE - line
    mid_x, mid_y = box["left"] + box["width"] / 2, box["top"] + box["height"] / 2
    for name, (x, y) in {
        "top": (mid_x, box["top"] - outside),
        "right": (box["left"] + box["width"] + outside, mid_y),
        "bottom": (mid_x, box["top"] + box["height"] + outside),
    }.items():
        pixel = shot.getpixel((round(x), round(y)))
        assert isinstance(pixel, tuple)
        assert _red(pixel), f"no red on the {name} side at {(x, y)}: {pixel}"
    left_column = [
        shot.getpixel((99, y)) for y in range(round(box["top"] - 20), round(box["top"] + box["height"] + 20))
    ]
    assert not any(isinstance(p, tuple) and _red(p) for p in left_column), "red left of the slide's left edge"


def _red(pixel: tuple[int, ...]) -> bool:
    return all(abs(pixel[i] - RED[i]) <= COLOUR_TOLERANCE for i in range(3))


@needs_chromium
def test_pointer_ring_touch_then_mouse(pointer_touch_page: Page, deck_p_path: Path) -> None:
    """E2E-026."""
    page = pointer_touch_page
    _presented_pointer_on(page, deck_p_path)
    page.mouse.move(*CENTRE)
    wait_state(page, lambda s: s["dot"] is not None, "the dot at the centre")

    box = page.evaluate(
        "(() => { const r = document.getElementById('tile-b').getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + r.height / 2]; })()"
    )
    page.touchscreen.tap(box[0], box[1])
    wait_ringed(page, "#tile-b")
    assert pointer_state(page)["dot"] is None

    page.touchscreen.tap(box[0], box[1])
    next_frames(page)
    state = pointer_state(page)
    assert (state["dot"], state["ring"], state["rings"]) == (None, None, 0)

    page.mouse.move(400, 300)
    wait_state(
        page,
        lambda s: s["dot"] is not None and abs(s["dot"]["x"] - 400) <= 1 and abs(s["dot"]["y"] - 300) <= 1,
        "the dot back at (400, 300)",
    )


@needs_chromium
def test_pointer_ring_reduced_motion(pointer_reduced_page: Page, deck_p_path: Path) -> None:
    """E2E-027: read in the first animation frame after the click."""
    page = pointer_reduced_page
    _presented_pointer_on(page, deck_p_path)
    page.evaluate(FIRST_FRAME_AFTER_CLICK)
    click_centre(page, "#tile-a")
    frame = wait_until(
        page, lambda: page.evaluate("window.ringFirstFrame"), lambda v: v != "unset", what="the first frame read"
    )
    assert frame is not None, "no ring on the first frame after the click"
    assert frame["animations"] == 0
    assert frame["opacity"] == "1"
    assert is_ringed(frame)
