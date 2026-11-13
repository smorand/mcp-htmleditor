"""SPEC-0022 FR-4, FR-5(b), FR-7 (shell side), FR-8: shell shortcuts and the speaker notes panel.

Keys are dispatched on the editor page's own document or elements (headless Chromium keeps the
keyboard focus in the iframe, see test_fullscreen_e2e.py). The deck side of presenter and pointer is
stubbed on the framed window, so these tests do not depend on the deck block.
"""

from __future__ import annotations

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from tests.browser_wait import settle, wait_for_file, wait_until
from tests.conftest import ServedDeck, needs_chromium

KEY_JS = (
    "([sel, key, mods]) => { const t = sel ? document.querySelector(sel) : document.body;"
    " const e = new KeyboardEvent('keydown', Object.assign({key, bubbles: true, cancelable: true}, mods));"
    " t.dispatchEvent(e); return e.defaultPrevented; }"
)
STUB_JS = (
    "() => { const w = document.getElementById('content-frame').contentWindow; w.__calls = [];"
    " w.togglePresenter = () => w.__calls.push('presenter');"
    " w.togglePointer = () => w.__calls.push('pointer');"
    " w.armPointer = () => {}; w.presentWithPointer = () => {}; w.setPointerAllowed = () => {}; }"
)


def _open(page: Page, deck: ServedDeck) -> None:
    page.goto(f"http://127.0.0.1:{deck.port}/")
    page.wait_for_function(
        "() => { const d = document.getElementById('content-frame').contentDocument;"
        " return d && d.querySelector('[data-type=\"slide\"]') && document.getElementById('edit-mode-btn'); }"
    )


def _key(page: Page, key: str, selector: str | None = None, **mods: bool) -> bool:
    return bool(page.evaluate(KEY_JS, [selector, key, mods]))


def _pressed(page: Page) -> str | None:
    return page.get_attribute("#edit-mode-btn", "aria-pressed")


def _calls(page: Page) -> list[str]:
    return list(page.evaluate("() => document.getElementById('content-frame').contentWindow.__calls"))


@needs_chromium
def test_e_toggles_edit_mode_both_cases_and_is_ignored_in_inputs(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    assert _pressed(page) == "false"
    _key(page, "e")
    assert _pressed(page) == "true"
    _key(page, "E")
    assert _pressed(page) == "false"
    _key(page, "e", "#ask-ai-text")  # a textarea of the shell
    _key(page, "e", "#edit-mode-btn", ctrlKey=True)
    _key(page, "e", None, metaKey=True)
    _key(page, "e", None, altKey=True)
    assert _pressed(page) == "false"


@needs_chromium
def test_e_message_from_the_iframe_toggles_edit_mode_only_from_the_frame(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    page.evaluate(
        "() => document.getElementById('content-frame').contentWindow"
        ".eval(\"parent.postMessage({type:'deck-key',key:'e'}, '*')\")"
    )
    wait_until(page, lambda: _pressed(page), lambda v: v == "true", what="edit mode on by deck-key")
    # A message whose source is the shell itself is not believed.
    page.evaluate("() => window.postMessage({type:'deck-key',key:'e'}, '*')")
    settle(page)
    assert _pressed(page) == "true"


@needs_chromium
def test_p_and_s_reach_the_deck_and_p_is_off_in_edit_mode(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    page.evaluate(STUB_JS)
    _key(page, "p")
    _key(page, "P")
    _key(page, "s")
    _key(page, "S")
    assert _calls(page) == ["pointer", "pointer", "presenter", "presenter"]
    _key(page, "p", "#ask-ai-text")
    _key(page, "s", None, ctrlKey=True)
    assert len(_calls(page)) == 4
    _key(page, "e")
    _key(page, "p")
    assert len(_calls(page)) == 4


@needs_chromium
def test_presenter_button_calls_the_deck(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    page.evaluate(STUB_JS)
    page.evaluate("() => { updateSlideActionsVisibility(); }")
    assert page.is_visible("#presenter-btn")
    page.click("#presenter-btn")
    assert _calls(page) == ["presenter"]
    assert page.get_attribute("#content-frame", "sandbox") is not None
    sandbox = page.get_attribute("#content-frame", "sandbox") or ""
    assert "allow-popups" in sandbox
    assert "allow-popups-to-escape-sandbox" in sandbox


@needs_chromium
def test_f_toggles_fullscreen(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    _key(page, "f")
    wait_until(
        page,
        lambda: page.evaluate("() => !!document.fullscreenElement"),
        lambda v: v is True,
        what="fullscreen entered by F",
    )
    _key(page, "F")
    wait_until(
        page,
        lambda: page.evaluate("() => !!document.fullscreenElement"),
        lambda v: v is False,
        what="fullscreen left by F",
    )


@needs_chromium
def test_notes_button_only_in_edit_mode_and_edits_the_bound_slide(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    assert not page.is_visible("#notes-btn")
    assert not page.is_visible("#notes-panel")
    _key(page, "e")
    assert page.is_visible("#notes-btn")
    assert not page.is_visible("#notes-panel")
    page.click("#notes-btn")
    assert page.is_visible("#notes-panel")
    assert page.get_attribute("#notes-btn", "aria-expanded") == "true"

    page.fill("#notes-text", "first line\nsecond line")
    text = wait_for_file(page, served_deck.path, '<aside data-role="speaker-notes"')
    soup = BeautifulSoup(text, "html.parser")
    slide0 = soup.select_one('[data-type="slide"][data-id="slide-0"]')
    assert slide0 is not None
    aside = slide0.find("aside", attrs={"data-role": "speaker-notes"}, recursive=False)
    assert aside is not None
    assert aside.get_text() == "first line\nsecond line"
    assert aside.attrs == {"data-role": "speaker-notes"}
    assert "contenteditable" not in str(aside)

    page.evaluate("() => document.getElementById('content-frame').contentWindow.goToSlide(2)")
    wait_until(page, lambda: page.input_value("#notes-text"), lambda v: v == "", what="textarea rebound to slide 2")
    page.fill("#notes-text", "for slide two")
    text = wait_for_file(page, served_deck.path, "for slide two")
    soup = BeautifulSoup(text, "html.parser")
    slide2 = soup.select_one('[data-type="slide"][data-id="slide-2"]')
    assert slide2 is not None and slide2.find("aside", recursive=False).get_text() == "for slide two"  # type: ignore[union-attr]
    slide0 = soup.select_one('[data-type="slide"][data-id="slide-0"]')
    assert slide0 is not None and slide0.find("aside", recursive=False).get_text() == "first line\nsecond line"  # type: ignore[union-attr]

    page.evaluate("() => document.getElementById('content-frame').contentWindow.goToSlide(0)")
    wait_until(
        page,
        lambda: page.input_value("#notes-text"),
        lambda v: v == "first line\nsecond line",
        what="rebound to slide 0",
    )
    page.fill("#notes-text", "")
    wait_until(
        page,
        lambda: "first line" in served_deck.path.read_text(encoding="utf-8"),
        lambda present: present is False,
        what="slide 0 aside removed on disk",
    )

    _key(page, "e")  # edit mode off hides button and panel
    assert not page.is_visible("#notes-btn")
    assert not page.is_visible("#notes-panel")
