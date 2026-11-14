"""SPEC-0022 amendment 2026-11-14: the keyboard shortcuts help (icon button, ``?`` key, standalone deck overlay).

Real headless Chromium. Every observation goes through ``wait_until`` (no fixed sleeps).
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from tests.browser_wait import settle, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import deck_ei, write_deck

KEY_JS = (
    "([sel, key, mods]) => { const t = sel ? document.querySelector(sel) : document.body;"
    " t.dispatchEvent(new KeyboardEvent('keydown', Object.assign({key, bubbles: true, cancelable: true}, mods))); }"
)
FRAME_KEY_JS = (
    "([key, mods]) => document.getElementById('content-frame').contentDocument.dispatchEvent("
    "new KeyboardEvent('keydown', Object.assign({key, bubbles: true, cancelable: true}, mods)))"
)


def _open(page: Page, deck: ServedDeck) -> None:
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(f"http://127.0.0.1:{deck.port}/")
    wait_until(
        page,
        lambda: page.evaluate("(document.getElementById('content-frame').contentWindow || {}).togglePresenter ? 1 : 0"),
        bool,
        what="deck block in the editor frame",
    )


def _open_state(page: Page) -> bool:
    return bool(page.evaluate("!document.getElementById('help-panel').hidden"))


def _expanded(page: Page) -> str | None:
    return page.get_attribute("#help-btn", "aria-expanded")


@needs_chromium
def test_icon_button_is_last_visible_control_at_the_right_edge(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    info = page.evaluate(
        """() => {
          const bar = document.getElementById('toolbar').getBoundingClientRect();
          const btn = document.getElementById('help-btn');
          const visible = [...document.querySelectorAll('#toolbar button')].filter(b => b.offsetParent !== null);
          const r = btn.getBoundingClientRect();
          return {last: visible[visible.length - 1].id, gap: bar.right - r.right, text: btn.textContent.trim(),
                  svg: !!btn.querySelector('svg'), title: btn.title, label: btn.getAttribute('aria-label')};
        }"""
    )
    assert info["last"] == "help-btn"
    assert 0 <= info["gap"] <= 20
    assert info["text"] == "" and info["svg"]
    assert info["title"] == info["label"] == "Raccourcis clavier"


@needs_chromium
def test_click_opens_and_closes_with_aria(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    assert _expanded(page) == "false" and page.get_attribute("#help-btn", "aria-controls") == "help-panel"
    assert page.get_attribute("#help-panel", "role") == "dialog"
    page.click("#help-btn")
    assert _open_state(page) and _expanded(page) == "true"
    page.click("#help-btn")
    assert not _open_state(page) and _expanded(page) == "false"
    page.click("#help-btn")
    page.click("#toolbar-filename")  # outside click
    assert not _open_state(page) and _expanded(page) == "false"


@needs_chromium
def test_question_mark_from_shell_and_escape(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    page.evaluate(KEY_JS, [None, "?", {}])
    assert _open_state(page) and _expanded(page) == "true"
    page.evaluate(KEY_JS, [None, "?", {}])
    assert not _open_state(page)
    page.evaluate(KEY_JS, [None, "?", {}])
    page.evaluate(KEY_JS, [None, "Escape", {}])
    assert not _open_state(page) and _expanded(page) == "false"


@needs_chromium
def test_question_mark_from_the_iframe_deck(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    page.evaluate(FRAME_KEY_JS, ["?", {}])
    wait_until(page, lambda: _open_state(page), bool, what="help opened by the deck")
    page.evaluate(FRAME_KEY_JS, ["?", {}])
    wait_until(page, lambda: _open_state(page), lambda v: not v, what="help closed by the deck")
    # Framed: the deck shows no overlay of its own.
    assert page.evaluate("!document.getElementById('content-frame').contentDocument.getElementById('deck-help')")


@needs_chromium
def test_question_mark_ignored_in_textarea_and_with_ctrl(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    page.evaluate(KEY_JS, ["#ask-ai-text", "?", {}])
    page.evaluate(KEY_JS, [None, "?", {"ctrlKey": True}])
    page.evaluate(KEY_JS, [None, "?", {"metaKey": True}])
    page.evaluate(FRAME_KEY_JS, ["?", {"ctrlKey": True}])
    settle(page)
    assert not _open_state(page)


@needs_chromium
def test_table_lists_the_keys(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    keys = set(page.eval_on_selector_all("#help-panel kbd", "els => els.map(e => e.textContent.trim())"))
    assert {"F", "P", "S", "E", "L", "N", "?", "Esc", "Home", "End"} <= keys
    groups = page.eval_on_selector_all("#help-panel th", "els => els.map(e => e.textContent.trim())")
    assert groups == ["Deck", "Editor", "Presenter window", "Buttons (no key)"]


@needs_chromium
def test_standalone_deck_overlay_opens_and_closes(page: Page, tmp_path: Path) -> None:
    deck = Path(write_deck(tmp_path / "deck.html", deck_ei()))
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(deck.as_uri())
    wait_until(page, lambda: page.evaluate("typeof window.togglePresenter"), lambda v: v == "function", what="block")
    hidden = "(() => { const h = document.getElementById('deck-help'); return !h || h.hidden; })()"
    assert page.evaluate(hidden)
    page.keyboard.press("?")
    wait_until(page, lambda: page.evaluate(hidden), lambda v: not v, what="overlay open")
    assert page.evaluate("document.querySelectorAll('#deck-help kbd').length") >= 8
    page.keyboard.press("Escape")
    wait_until(page, lambda: page.evaluate(hidden), bool, what="overlay closed by Escape")
    page.keyboard.press("?")
    wait_until(page, lambda: page.evaluate(hidden), lambda v: not v, what="overlay reopened")
    page.keyboard.press("?")
    wait_until(page, lambda: page.evaluate(hidden), bool, what="overlay closed by ?")
    page.keyboard.press("Control+?")
    settle(page)
    assert page.evaluate(hidden)
