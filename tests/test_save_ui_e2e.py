"""E2E tests for SPEC-0009 in the editor page: conflict choice, save failures, server loss (US-0049).

Real headless Chromium against a real editor server serving DECK (``served_deck``). The poll interval is
forced to 100 ms; server loss is simulated with ``page.route`` because the listening socket stays open.
"""

from __future__ import annotations

import os
import re
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect

from mcp_htmleditor import config as config_module
from tests.conftest import ServedDeck, needs_chromium

COVER = ".slide-cover-title"
AGENT_TITLE = "Titre de l agent"
CONFLICT_TEXT = "The file changed on disk. Reload to see the changes, or keep your version."
LOST_TEXT = "Connection to the editor server lost"
SAVED_DOT_COLOR = "rgb(66, 190, 101)"
PENDING_DOT_COLOR = "rgb(255, 131, 43)"
SAVE_WAIT_MS = 1500  # > the 800 ms typing debounce plus the POST round trip
WAIT_MS = 6000

needs_writable_check = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores folder permissions"
)


@pytest.fixture
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTMLEDITOR_POLL_INTERVAL", "100")
    config_module.reset_settings_cache()


def _open_in_edit_mode(page: Page, deck: ServedDeck) -> None:
    page.goto(f"http://127.0.0.1:{deck.port}/")
    page.wait_for_function(
        "() => { const d = document.getElementById('content-frame').contentDocument;"
        f" return d && d.querySelector('{COVER}'); }}"
    )
    page.click("#edit-mode-btn")
    page.wait_for_timeout(300)


def _type_in_cover(page: Page, text: str) -> None:
    page.frame_locator("#content-frame").locator(COVER).click()
    page.keyboard.press("End")
    page.keyboard.type(text)


def _agent_writes_title(deck: ServedDeck) -> None:
    """Rewrite the cover title on disk, as an agent would, with a different mtime."""
    source = deck.path.read_text(encoding="utf-8")
    assert "Couverture" in source
    deck.path.write_text(source.replace("Couverture", AGENT_TITLE), encoding="utf-8")
    later = time.time() + 10
    os.utime(deck.path, (later, later))


def _wait_dot(page: Page, color: str) -> None:
    """The dot fades between states (120 ms), so wait for the final colour."""
    page.wait_for_function(
        "(c) => getComputedStyle(document.getElementById('toolbar-status')).color === c", arg=color, timeout=WAIT_MS
    )


def _post_counter(page: Page) -> list[str]:
    posts: list[str] = []
    page.on(
        "request", lambda req: posts.append(req.url) if req.method == "POST" and req.url.endswith("/content") else None
    )
    return posts


def _show_conflict(page: Page, deck: ServedDeck) -> None:
    """Type (unsaved edit), let the agent write the file, and wait for the conflict message."""
    _open_in_edit_mode(page, deck)
    _type_in_cover(page, "X")
    _agent_writes_title(deck)
    expect(page.locator("#save-conflict")).to_contain_text(CONFLICT_TEXT, timeout=WAIT_MS)


@contextmanager
def _read_only(folder: Path) -> Iterator[None]:
    """New files cannot be created in the folder inside the block; permissions restored in finally."""
    mode = stat.S_IMODE(folder.stat().st_mode)
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        yield
    finally:
        folder.chmod(mode)


@needs_chromium
@pytest.mark.usefixtures("fast_poll")
def test_conflict_message_and_reload(page: Page, served_deck: ServedDeck) -> None:
    """E2E-008."""
    posts = _post_counter(page)
    _show_conflict(page, served_deck)
    conflict = page.locator("#save-conflict")
    expect(conflict.get_by_role("button", name="Reload")).to_be_visible()
    expect(conflict.get_by_role("button", name="Keep mine")).to_be_visible()
    assert page.locator("#notices").get_attribute("role") == "status"

    sent = len(posts)
    page.keyboard.type("YY")
    page.wait_for_timeout(SAVE_WAIT_MS)
    assert len(posts) == sent
    assert f"{AGENT_TITLE}X" not in served_deck.path.read_text(encoding="utf-8")

    conflict.get_by_role("button", name="Reload").click()
    expect(page.frame_locator("#content-frame").locator(COVER)).to_have_text(AGENT_TITLE, timeout=WAIT_MS)
    expect(conflict).to_be_hidden()
    assert len(posts) == sent
    _wait_dot(page, SAVED_DOT_COLOR)


@needs_chromium
@pytest.mark.usefixtures("fast_poll")
def test_keep_mine_saves_with_force(page: Page, served_deck: ServedDeck) -> None:
    """FR-NEW-003: Keep mine writes the browser version and removes the message."""
    _show_conflict(page, served_deck)
    page.locator("#save-conflict").get_by_role("button", name="Keep mine").click()
    expect(page.locator("#save-conflict")).to_be_hidden(timeout=WAIT_MS)
    saved = served_deck.path.read_text(encoding="utf-8")
    assert "CouvertureX" in saved  # Keep mine writes the browser's version
    assert AGENT_TITLE not in saved
    _wait_dot(page, SAVED_DOT_COLOR)


@needs_chromium
@pytest.mark.usefixtures("fast_poll")
def test_connection_lost_after_three_failed_polls_then_back(page: Page, served_deck: ServedDeck) -> None:
    """E2E-017 and E2E-018."""
    _open_in_edit_mode(page, served_deck)
    page.route("**/status", lambda route: route.abort())
    expect(page.locator("#connection-lost")).to_have_text(LOST_TEXT, timeout=WAIT_MS)
    page.unroute("**/status")
    expect(page.locator("#connection-lost")).to_be_hidden(timeout=WAIT_MS)


@needs_chromium
@pytest.mark.usefixtures("fast_poll")
def test_one_failed_poll_shows_nothing(page: Page, served_deck: ServedDeck) -> None:
    """E2E-027."""
    _open_in_edit_mode(page, served_deck)
    page.evaluate(
        "() => { window.__seen = false; const n = document.getElementById('connection-lost');"
        " new MutationObserver(() => { if (!n.hidden) window.__seen = true; })"
        ".observe(n, { attributes: true }); }"
    )
    failed: list[int] = []

    def abort_once(route: Route) -> None:
        if failed:
            route.continue_()
        else:
            failed.append(1)
            route.abort()

    page.route("**/status", abort_once)
    page.wait_for_timeout(1200)
    assert failed == [1]
    assert page.evaluate("() => window.__seen") is False
    expect(page.locator("#connection-lost")).to_be_hidden()


@needs_chromium
@pytest.mark.usefixtures("fast_poll")
@pytest.mark.parametrize("kind", ["status-500", "invalid-json"])
def test_non_200_and_invalid_json_polls_count_as_failures(page: Page, served_deck: ServedDeck, kind: str) -> None:
    """FR-NEW-009: every kind of failed poll counts."""
    _open_in_edit_mode(page, served_deck)
    if kind == "status-500":
        page.route("**/status", lambda route: route.fulfill(status=500, body='{"error":"x"}'))
    else:
        page.route("**/status", lambda route: route.fulfill(status=200, body="not json"))
    expect(page.locator("#connection-lost")).to_have_text(LOST_TEXT, timeout=WAIT_MS)


@needs_chromium
@needs_writable_check
@pytest.mark.usefixtures("fast_poll")
def test_keep_mine_failure_keeps_conflict_and_shows_error(page: Page, served_deck: ServedDeck) -> None:
    """E2E-028."""
    _show_conflict(page, served_deck)
    before = served_deck.path.read_text(encoding="utf-8")
    with _read_only(served_deck.path.parent):
        page.locator("#save-conflict").get_by_role("button", name="Keep mine").click()
        expect(page.locator("#save-error")).to_contain_text(re.compile(r"Save failed: \S+"), timeout=WAIT_MS)
        expect(page.locator("#save-conflict")).to_be_visible()
        _wait_dot(page, PENDING_DOT_COLOR)
    assert served_deck.path.read_text(encoding="utf-8") == before


@needs_chromium
@needs_writable_check
@pytest.mark.usefixtures("fast_poll")
def test_save_failure_is_shown_and_retried(page: Page, served_deck: ServedDeck) -> None:
    """E2E-032, plus: a notice never takes focus."""
    _open_in_edit_mode(page, served_deck)
    with _read_only(served_deck.path.parent):
        _type_in_cover(page, "Q")
        expect(page.locator("#save-error")).to_contain_text(re.compile(r"Save failed: \S+"), timeout=WAIT_MS)
        _wait_dot(page, PENDING_DOT_COLOR)
        focused_in_frame = page.evaluate(
            "() => { const d = document.getElementById('content-frame').contentDocument;"
            " return d.activeElement && d.activeElement.classList.contains('slide-cover-title'); }"
        )
        assert focused_in_frame is True
        assert page.evaluate("() => document.activeElement === document.getElementById('content-frame')") is True
    page.keyboard.type("R")
    expect(page.locator("#save-error")).to_be_hidden(timeout=WAIT_MS)
    page.wait_for_timeout(300)
    assert "CouvertureQR" in served_deck.path.read_text(encoding="utf-8")
    _wait_dot(page, SAVED_DOT_COLOR)


@needs_chromium
@pytest.mark.usefixtures("fast_poll")
def test_own_save_does_not_reload_and_poll_keeps_base(page: Page, served_deck: ServedDeck) -> None:
    """FR-NEW-002: a self save adopts the answer mtime, so the second save is not a conflict and no reload happens."""
    _open_in_edit_mode(page, served_deck)
    page.evaluate("() => { document.getElementById('content-frame').contentWindow.__probe = 1; }")
    _type_in_cover(page, "A")
    page.wait_for_timeout(SAVE_WAIT_MS)
    page.keyboard.type("B")
    page.wait_for_timeout(SAVE_WAIT_MS)
    assert "CouvertureAB" in served_deck.path.read_text(encoding="utf-8")
    expect(page.locator("#save-conflict")).to_be_hidden()
    assert page.evaluate("() => document.getElementById('content-frame').contentWindow.__probe") == 1
