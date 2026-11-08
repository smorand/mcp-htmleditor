"""The presentation pointer in the other presentation templates (SPEC-0017, US-0107).

One module page at 1600 by 900 (DEC-017); each deck is made from a starting point, served by a real editor server
and presented with ``#present-btn``. E2E-036: the layout areas of the Euro-Information starting point are not boxes.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page

from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import build_deck, write_deck
from tests.pointer_support import (
    FRAME_DOC,
    deck_p_path,
    dispatch_key,
    next_frames,
    pointer_file_page,
    pointer_state,
    present_served,
    wait_ringed,
    wait_slide_settled,
    wait_state,
)

__all__ = ["deck_p_path", "pointer_file_page"]

EI_PARAGRAPH = "EI paragraph"
# The middle of the right half of the white inner frame, to the right of the one short paragraph.
INNER_EMPTY_SPOT = (
    f"() => {{ const r = ({FRAME_DOC}).querySelector('#slide-1 .slide-inner').getBoundingClientRect();"
    " return [r.left + r.width * 0.8, r.top + r.height * 0.6]; }"
)


def ei_deck() -> str:
    """A deck made from the ``ei`` starting point: a cover, one content slide holding a paragraph and no tile."""
    deck = build_deck("ei", ("Cover", "Content", "Closing"))
    return deck.replace("<p>Texte de Content.</p>", f"<p>{EI_PARAGRAPH}</p>", 1)


@pytest.fixture
def served_ei(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> ServedDeck:
    return serve_deck(Path(write_deck(tmp_path / "deck-ei.html", ei_deck())))


def click_and_read(page: Page, x: float, y: float) -> int:
    """Click the screen point, let the deck's frame loop see it, return the number of rings shown."""
    page.mouse.click(x, y)
    next_frames(page, FRAME_DOC)
    return int(pointer_state(page, FRAME_DOC)["rings"])


@needs_chromium
def test_pointer_ei_layout_areas_are_not_boxes(pointer_file_page: Page, served_ei: ServedDeck) -> None:
    """E2E-036."""
    page = pointer_file_page
    present_served(page, served_ei.port)
    dispatch_key(page, "ArrowRight")
    wait_state(page, lambda s: s["current"] == 1, "the content slide shown", FRAME_DOC)
    wait_slide_settled(page, FRAME_DOC)

    x, y = page.evaluate(INNER_EMPTY_SPOT)
    assert click_and_read(page, x, y) == 0, "the white inner frame was ringed"

    page_number = page.evaluate(
        f"() => {{ const r = ({FRAME_DOC}).querySelector('#slide-1 .slide-foot-page').getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + r.height / 2]; }"
    )
    assert click_and_read(page, *page_number) == 0, "the footer's page number was ringed"

    paragraph = page.evaluate(
        f"() => {{ const r = ({FRAME_DOC}).querySelector('#slide-1 .slide-body p').getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + r.height / 2]; }"
    )
    page.mouse.click(*paragraph)
    wait_ringed(page, "#slide-1 .slide-body p", FRAME_DOC)
