"""SPEC-0022 deck side: keys F P S E, hidden speaker notes and the presenter window (FR-2, FR-3, FR-5a, FR-6, FR-7).

Real headless Chromium. The deck is opened as a ``file://`` page (no server) or through the editor server
(``serve_deck``, deck inside the editor iframe). Every observation goes through ``wait_until`` (no fixed sleeps).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import deck_ei, write_deck

pytestmark = needs_chromium

NOTES = ("Opening words\nsecond line", "Middle notes", "")
SLIDE_TAG = re.compile(r'<(?:article|section)\b[^>]*data-type="slide"[^>]*>')
SPY = """
() => {
  window.__calls = {pointer: 0};
  window.togglePointer = () => { window.__calls.pointer += 1; };
}
"""


def deck_with_notes() -> str:
    """The 8 slide EI deck, the first two slides carrying a speaker note."""
    text = deck_ei()
    matches = list(SLIDE_TAG.finditer(text))
    for index in (1, 0):
        end = matches[index].end()
        note = NOTES[index].replace("\n", "&#10;")
        text = text[:end] + f'<aside data-role="speaker-notes">{note}</aside>' + text[end:]
    return text


@pytest.fixture
def deck_file(tmp_path: Path) -> Path:
    return Path(write_deck(tmp_path / "deck.html", deck_with_notes()))


@pytest.fixture
def file_page(page: Page, deck_file: Path) -> Page:
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(deck_file.as_uri())
    wait_until(page, lambda: page.evaluate("typeof window.togglePresenter"), lambda v: v == "function", what="block")
    return page


def press(page: Page, key: str) -> None:
    page.keyboard.press(key)


def pointer_calls(page: Page) -> int:
    return int(page.evaluate("window.__calls.pointer"))


def fullscreen(page: Page) -> bool:
    return bool(page.evaluate("!!document.fullscreenElement"))


def active_title(page: Page) -> str:
    return str(page.evaluate("document.querySelector('[data-type=\"slide\"].active').getAttribute('data-title')"))


@pytest.mark.parametrize("key", ["p", "P"])
def test_p_toggles_the_pointer_in_a_file_deck(file_page: Page, key: str) -> None:
    file_page.evaluate(SPY)
    press(file_page, key)
    wait_until(file_page, lambda: pointer_calls(file_page), lambda n: n == 1, what="one togglePointer call")
    press(file_page, key)
    wait_until(file_page, lambda: pointer_calls(file_page), lambda n: n == 2, what="two togglePointer calls")


@pytest.mark.parametrize("key", ["f", "F"])
def test_f_enters_and_leaves_fullscreen(file_page: Page, key: str) -> None:
    press(file_page, key)
    wait_until(file_page, lambda: fullscreen(file_page), bool, what="fullscreen entered")
    press(file_page, key)
    wait_until(file_page, lambda: fullscreen(file_page), lambda v: not v, what="fullscreen left")


def test_keys_are_ignored_in_a_textarea_and_with_ctrl(file_page: Page) -> None:
    file_page.evaluate(SPY)
    file_page.evaluate(
        "() => { const t = document.createElement('textarea'); t.id = 'probe';"
        " document.body.appendChild(t); t.focus(); }"
    )
    press(file_page, "p")
    press(file_page, "f")
    press(file_page, "s")
    file_page.evaluate("() => document.getElementById('probe').blur()")
    press(file_page, "Control+p")
    press(file_page, "Control+s")
    press(file_page, "Meta+f")
    press(file_page, "Alt+s")
    press(file_page, "p")  # control sentinel: the handler is alive, so the earlier presses were really ignored
    wait_until(file_page, lambda: pointer_calls(file_page), lambda n: n >= 1, what="the sentinel P")
    assert pointer_calls(file_page) == 1
    assert not fullscreen(file_page)
    assert not file_page.evaluate("window.isPresenterOpen()")
    assert file_page.evaluate("document.getElementById('probe').value") == "pfs"  # typed, not acted on


def test_e_does_nothing_in_a_standalone_deck(file_page: Page) -> None:
    file_page.evaluate("() => { window.__msgs = []; addEventListener('message', e => window.__msgs.push(e.data)); }")
    press(file_page, "e")
    file_page.evaluate("postMessage({type: 'sentinel'}, '*')")
    wait_until(file_page, lambda: file_page.evaluate("window.__msgs.length"), lambda n: n >= 1, what="sentinel")
    assert file_page.evaluate("window.__msgs.map(m => m.type)") == ["sentinel"]


def test_notes_are_hidden_on_screen_and_in_print(file_page: Page) -> None:
    assert file_page.evaluate("document.querySelectorAll('[data-role=\"speaker-notes\"]').length") == 2
    probe = "[...document.querySelectorAll('[data-role=\"speaker-notes\"]')].map(n => getComputedStyle(n).display)"
    assert file_page.evaluate(probe) == ["none", "none"]
    file_page.emulate_media(media="print")
    assert file_page.evaluate(probe) == ["none", "none"]


def open_presenter(page: Page) -> Page:
    with page.expect_popup() as info:
        press(page, "s")
    popup = info.value
    wait_until(popup, lambda: popup.evaluate("!!document.getElementById('p-notes')"), bool, what="presenter page")
    return popup


def popup_text(popup: Page, ident: str) -> str:
    return str(popup.evaluate("(i) => document.getElementById(i).textContent", ident))


def test_presenter_shows_notes_and_next_title_and_navigates_both_ways(file_page: Page) -> None:
    titles = file_page.evaluate("[...document.querySelectorAll('[data-type=\"slide\"]')].map(s => s.dataset.title)")
    popup = open_presenter(file_page)
    wait_until(popup, lambda: popup_text(popup, "p-notes"), lambda t: t == NOTES[0], what="notes of slide 1")
    assert popup_text(popup, "p-next-title") == titles[1]
    assert popup_text(popup, "p-count") == f"1 / {len(titles)}"
    popup.click("#p-next")
    wait_until(popup, lambda: popup_text(popup, "p-notes"), lambda t: t == NOTES[1], what="notes of slide 2")
    assert wait_until(file_page, lambda: active_title(file_page), lambda t: t == titles[1], what="deck follows")
    popup.click("#p-prev")
    wait_until(file_page, lambda: active_title(file_page), lambda t: t == titles[0], what="deck back")
    popup.keyboard.press("ArrowRight")
    wait_until(file_page, lambda: active_title(file_page), lambda t: t == titles[1], what="key next")
    popup.keyboard.press("End")
    wait_until(file_page, lambda: active_title(file_page), lambda t: t == titles[-1], what="End")
    wait_until(
        popup,
        lambda: popup.evaluate("getComputedStyle(document.getElementById('p-end')).display"),
        lambda d: d == "flex",
        what="end marker on the last slide",
    )
    popup.keyboard.press("Home")
    wait_until(file_page, lambda: active_title(file_page), lambda t: t == titles[0], what="Home")
    file_page.evaluate("() => navigate(1)")  # the reverse direction: the deck leads, the presenter follows
    wait_until(popup, lambda: popup_text(popup, "p-count"), lambda t: t.startswith("2 /"), what="presenter follows")


def test_presenter_previews_show_one_slide_each(file_page: Page) -> None:
    popup = open_presenter(file_page)
    visible = (
        "() => [...document.querySelectorAll('[data-type=\"slide\"]')]"
        ".filter(s => getComputedStyle(s).display !== 'none' && !s.closest('[data-pv-hide]'))"
        ".map(s => s.dataset.title)"
    )

    def previews() -> list[Any]:
        frames = [f for f in popup.frames if f != popup.main_frame and f.url == "about:srcdoc"]
        return [f.evaluate(visible) for f in frames if f.evaluate("!!document.querySelector('[data-pv-hide]')")]

    titles = file_page.evaluate("[...document.querySelectorAll('[data-type=\"slide\"]')].map(s => s.dataset.title)")
    wait_until(popup, previews, lambda v: v == [[titles[0]], [titles[1]]], what="current and next previews")


def test_presenter_shows_notes_edits_live(file_page: Page) -> None:
    popup = open_presenter(file_page)
    wait_until(popup, lambda: popup_text(popup, "p-notes"), lambda t: t == NOTES[0], what="first notes")
    file_page.evaluate(
        "() => { document.querySelector('[data-role=\"speaker-notes\"]').textContent = 'Changed live'; }"
    )
    wait_until(popup, lambda: popup_text(popup, "p-notes"), lambda t: t == "Changed live", what="live notes")


def test_presenter_font_buttons_timer_and_s_closes(file_page: Page) -> None:
    popup = open_presenter(file_page)
    before = popup.evaluate("parseFloat(getComputedStyle(document.getElementById('p-notes')).fontSize)")
    popup.click("#p-fplus")
    wait_until(
        popup,
        lambda: popup.evaluate("parseFloat(getComputedStyle(document.getElementById('p-notes')).fontSize)"),
        lambda v: v > before,
        what="bigger notes",
    )
    popup.click("#p-fminus")
    popup.click("#p-reset")
    assert popup_text(popup, "p-timer") == "00:00:00"
    assert file_page.evaluate("window.isPresenterOpen()")
    popup.keyboard.press("s")
    wait_until(file_page, lambda: file_page.evaluate("window.isPresenterOpen()"), lambda v: not v, what="closed")
    wait_until(file_page, popup.is_closed, bool, what="popup closed")


def test_s_in_the_deck_closes_the_presenter(file_page: Page) -> None:
    popup = open_presenter(file_page)
    file_page.bring_to_front()
    press(file_page, "s")
    wait_until(file_page, popup.is_closed, bool, what="popup closed by S in the deck")
    assert not file_page.evaluate("window.isPresenterOpen()")


def test_preview_window_installs_nothing(file_page: Page) -> None:
    popup = open_presenter(file_page)
    wait_until(popup, lambda: len(popup.frames), lambda n: n >= 3, what="preview frames")
    frame = next(f for f in popup.frames if f.url == "about:srcdoc")
    wait_until(popup, lambda: frame.evaluate("window.name"), lambda n: n == "deck-preview", what="preview name")
    assert frame.evaluate("typeof window.togglePresenter") == "undefined"


@pytest.fixture
def served_frame_page(page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> Page:
    served = serve_deck(Path(write_deck(tmp_path / "deck.html", deck_with_notes())))
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(f"http://127.0.0.1:{served.port}/")
    wait_until(
        page,
        lambda: page.evaluate("(document.getElementById('content-frame').contentWindow || {}).togglePresenter ? 1 : 0"),
        bool,
        what="deck block in the editor frame",
    )
    return page


def dispatch_in_frame(page: Page, key: str) -> None:
    page.evaluate(
        "(k) => document.getElementById('content-frame').contentDocument.dispatchEvent("
        "new KeyboardEvent('keydown', {key: k, bubbles: true}))",
        key,
    )


def test_served_deck_p_and_e_keys(served_frame_page: Page) -> None:
    page = served_frame_page
    page.evaluate(
        "() => { const w = document.getElementById('content-frame').contentWindow;"
        " w.__calls = {pointer: 0}; w.togglePointer = () => { w.__calls.pointer += 1; };"
        " window.__keys = []; addEventListener('message', e => {"
        " if (e.data && e.data.type === 'deck-key' && e.source === w) window.__keys.push(e.data.key); }); }"
    )
    dispatch_in_frame(page, "P")
    wait_until(
        page,
        lambda: page.evaluate("document.getElementById('content-frame').contentWindow.__calls.pointer"),
        lambda n: n == 1,
        what="P in the served deck",
    )
    dispatch_in_frame(page, "e")
    wait_until(page, lambda: page.evaluate("window.__keys"), lambda k: k == ["e"], what="deck-key message")


def test_served_deck_s_opens_the_presenter_through_the_sandboxed_frame(served_frame_page: Page) -> None:
    page = served_frame_page
    with page.expect_popup() as info:
        dispatch_in_frame(page, "s")
    popup = info.value
    wait_until(popup, lambda: popup_text(popup, "p-notes"), lambda t: t == NOTES[0], what="notes in the popup")
    dispatch_in_frame(page, "s")
    wait_until(page, popup.is_closed, bool, what="popup closed")
