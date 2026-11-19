"""SPEC-0027 (US-0157): the undo history keeps at most 50 steps and a new action clears redo (E2E-017, FR-011).

Real headless Chromium against a real editor server (``serve_deck`` on a copy of the plain document bootstrap).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from mcp_htmleditor import templates as templates_module
from tests.browser_wait import wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium

BLOCK_COUNT = "() => document.getElementById('content-frame').contentDocument.querySelector('article').children.length"
BUTTON_DISABLED = "(id) => document.getElementById(id).disabled"
UNDO_LIMIT = 50
ACTIONS = UNDO_LIMIT + 1


def _blocks(page: Page) -> int:
    return int(page.evaluate(BLOCK_COUNT))


def _insert_block(page: Page) -> None:
    """One structural action: a block inserted after the caret; waits for the block to exist."""
    before = _blocks(page)
    page.click("#btn-insert-block-after")
    page.wait_for_selector("#block-picker .picker-card")
    page.click("#block-picker .picker-card")
    wait_until(page, lambda: _blocks(page), lambda count: count == before + 1, what="a block inserted")


def _click_and_wait_restored(page: Page, button: str) -> None:
    """Click undo or redo, then wait until the restored document is rewired (``restoringFromUndo`` is false again)."""
    page.click(button)
    wait_until(
        page,
        lambda: page.evaluate("() => restoringFromUndo"),
        lambda restoring: restoring is False,
        what="restored document rewired",
    )


def _disabled(page: Page, button: str) -> bool:
    return bool(page.evaluate(BUTTON_DISABLED, button.removeprefix("#")))


@needs_chromium
def test_e2e_017_the_history_holds_fifty_steps_and_a_new_action_clears_redo(
    page: Page, serve_deck: Callable[[Path], ServedDeck], tmp_path: Path
) -> None:
    document = tmp_path / "doc.html"
    document.write_text(templates_module.template_path("doc").read_text(encoding="utf-8"), encoding="utf-8")
    deck = serve_deck(document)
    page.goto(f"http://127.0.0.1:{deck.port}/", wait_until="networkidle")
    page.click("#edit-mode-btn")
    wait_for_js(
        page, "() => getComputedStyle(document.getElementById('undo-btn')).display !== 'none'", True, what="undo"
    )
    initial = _blocks(page)

    for _ in range(ACTIONS):
        _insert_block(page)
    assert _blocks(page) == initial + ACTIONS

    undone = 0
    while not _disabled(page, "#undo-btn") and undone <= ACTIONS:
        _click_and_wait_restored(page, "#undo-btn")
        undone += 1
    assert undone == UNDO_LIMIT
    assert _blocks(page) == initial + 1, "the oldest action is out of the history, the 50 others are undone"

    assert not _disabled(page, "#redo-btn")
    _click_and_wait_restored(page, "#redo-btn")
    assert _blocks(page) == initial + 2
    _insert_block(page)
    assert _disabled(page, "#redo-btn"), "a new structural action clears redo"
