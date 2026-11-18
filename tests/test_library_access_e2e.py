"""US-0137: the editor when the session or the right ends (SPEC-0025, DEC-037, DEC-040).

Spec tests: E2E-010, E2E-013, E2E-105, E2E-116, E2E-117, E2E-118, E2E-167, E2E-170, E2E-178, E2E-188. The clock of
the server is moved past the 30 days of a session (``FakeClock.advance``); a second window is a second sign in of the
same address over HTTP. Absence of a notice is observed with ``settle``; the second channel of every refusal is the
stored file (hash), its history and the served title.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright

from tests import library_support
from tests.browser_wait import settle, wait_for_js, wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    HEART_FAILURE,
    PNEUMO,
    STATINS,
    EditorLibrary,
    Presentation,
    deck_frame,
    deck_with_notes,
    frame_title,
    launch_chromium,
    leave_field,
    notice_visible,
    signed_in,
    stored_title,
    turn_edit_on,
    type_in_title,
    wait_stored,
    with_title,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
library = library_support.library

EXPIRED = "Your session has expired. Sign in again to save."
DENIED = "Access denied."
CONFLICT_TEXT = "The file changed on disk. Reload to see the changes, or keep your version."
SESSION_SECONDS = 30 * 24 * 3600
NOTICE_TEXT = "#save-error .notice-text"
CURRENT_SLIDE = "[...document.querySelectorAll('.slide')].findIndex(s => s.classList.contains('active'))"
SPIROMETRY = "Spirometry Basics"
MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def digest(presentation: Presentation) -> str:
    return hashlib.sha256(presentation.path.read_bytes()).hexdigest()


def end_sessions(library: EditorLibrary, extra: float = 1.0) -> None:
    """Move the clock of the server past the end of every session signed in so far."""
    library.running.clock.advance(SESSION_SECONDS + extra)


def notice_text(page: Page) -> str:
    return str(page.locator(NOTICE_TEXT).inner_text()) if notice_visible(page, "save-error") else ""


def stays_quiet(page: Page, seconds: int = 4) -> None:
    """No notice of any kind (failure, conflict, lost connection) during ``seconds`` seconds."""
    for _ in range(seconds):
        settle(page)
        for notice in ("save-error", "save-conflict", "connection-lost"):
            assert not notice_visible(page, notice), notice


def remove_dan_everywhere(library: EditorLibrary) -> None:
    admin = signed_in(library.running, library.google, ADMIN)
    library.running.builder.member(library.ids[PNEUMO], DAN, "RW")
    for name in (CARDIOLOGY, PNEUMO):
        assert admin.remove_member(library.ids[name], DAN).status == 200


def test_e2e_010_the_session_ends_in_the_middle_of_an_edit(library: EditorLibrary) -> None:
    """E2E-010: the expiry notice alone, no prefix, no lost connection; the title stays, nothing is stored."""
    deck = library.decks[HEART_FAILURE]
    before = digest(deck)
    dan = library.open(DAN, HEART_FAILURE, edit=True)
    type_in_title(dan, " 2027")
    end_sessions(library)

    leave_field(dan)

    wait_until(dan, lambda: notice_text(dan), lambda text: text == EXPIRED, what="the expiry notice", bound=2.0)
    stays_quiet_except_error(dan)
    assert frame_title(dan) == "Heart Failure Update 2027"
    assert digest(deck) == before
    assert library.running.versions(deck) == []
    assert library.served_title(CAROL, HEART_FAILURE) == HEART_FAILURE


def stays_quiet_except_error(page: Page, seconds: int = 5) -> None:
    """The lost connection notice and the conflict notice stay hidden, the error notice keeps its exact text."""
    for _ in range(seconds):
        settle(page)
        assert not notice_visible(page, "connection-lost")
        assert not notice_visible(page, "save-conflict")
        assert notice_text(page) == EXPIRED


def test_e2e_013_signing_in_again_in_another_window_lets_the_change_be_stored(library: EditorLibrary) -> None:
    """E2E-013: after a second sign in, "!" stores the whole title, the expiry notice goes, the history keeps the
    previous version."""
    deck = library.decks[HEART_FAILURE]
    dan = library.open(DAN, HEART_FAILURE, edit=True)
    type_in_title(dan, " 2027")
    end_sessions(library)
    leave_field(dan)
    wait_until(dan, lambda: notice_text(dan), lambda text: text == EXPIRED, what="the expiry notice", bound=2.0)

    signed_in(library.running, library.google, DAN)
    type_in_title(dan, "!")
    leave_field(dan)

    wait_stored(dan, deck, "Heart Failure Update 2027!")
    wait_until(dan, lambda: notice_visible(dan, "save-error"), lambda shown: not shown, what="notice gone")
    assert library.served_title(CAROL, HEART_FAILURE) == "Heart Failure Update 2027!"
    assert library.titles_in_history(HEART_FAILURE) == ["Heart Failure Update"]


def test_e2e_105_saving_into_a_deleted_folder_is_refused(library: EditorLibrary) -> None:
    """E2E-105: "Access denied." alone, the text stays, no folder and no file is recreated."""
    folder = library.ids[PNEUMO]
    library.running.builder.member(folder, DAN, "RW")
    deck = library.running.builder.presentation(folder, SPIROMETRY, size=4_096, modified=MODIFIED)
    library.decks[SPIROMETRY] = deck
    dan = library.open(DAN, SPIROMETRY, edit=True)
    type_in_title(dan, " 2027")
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.post_json(f"/api/folders/{folder}/delete", {"confirm": PNEUMO}).status == 200

    leave_field(dan)

    wait_until(dan, lambda: notice_text(dan), lambda text: text == DENIED, what="denied notice", bound=5.0)
    assert frame_title(dan) == f"{SPIROMETRY} 2027"
    assert PNEUMO not in library.running.stored.folder_names()
    assert not deck.path.exists()


def test_e2e_116_a_raised_role_applies_on_the_next_action(library: EditorLibrary) -> None:
    """E2E-116: Carol (RO) is raised to RW; after a reload the edit controls show and her change is stored."""
    deck = library.decks[STATINS]
    carol = library.open(CAROL, STATINS)
    assert not carol.locator("#edit-mode-btn").is_visible()
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.add_member(library.ids[CARDIOLOGY], CAROL, "RW").status == 200

    carol.reload()
    wait_until(carol, lambda: carol.locator("#edit-mode-btn").is_visible(), bool, what="edit control")
    turn_edit_on(carol)
    type_in_title(carol, " B")
    leave_field(carol)

    wait_stored(carol, deck, f"{STATINS} B")
    assert library.titles_in_history(STATINS) == [STATINS]


def test_e2e_117_a_removed_members_change_is_refused(library: EditorLibrary) -> None:
    """E2E-117: "Access denied." alone, the text stays, Carol still sees the old text."""
    deck = library.decks[STATINS]
    before = digest(deck)
    dan = library.open(DAN, STATINS, edit=True)
    type_in_title(dan, " B")
    remove_dan_everywhere(library)

    leave_field(dan)

    wait_until(dan, lambda: notice_text(dan), lambda text: text == DENIED, what="denied notice", bound=5.0)
    assert frame_title(dan) == f"{STATINS} B"
    assert digest(deck) == before
    assert library.served_title(CAROL, STATINS) == STATINS


def test_e2e_118_a_lowered_role_blocks_the_next_stored_change(library: EditorLibrary) -> None:
    """E2E-118: Dan lowered to RO is refused, then after a reload the editing controls are absent."""
    deck = library.decks[STATINS]
    before = digest(deck)
    dan = library.open(DAN, STATINS, edit=True)
    type_in_title(dan, " B")
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.add_member(library.ids[CARDIOLOGY], DAN, "RO").status == 200

    leave_field(dan)

    wait_until(dan, lambda: notice_text(dan), lambda text: text == DENIED, what="denied notice", bound=5.0)
    dan.reload()
    wait_for_js(deck_frame(dan), "document.querySelectorAll('.slide').length > 0", True, what="deck")
    assert not dan.locator("#edit-mode-btn").is_visible()
    assert digest(deck) == before


def test_e2e_167_an_ended_session_shows_one_notice_soon_and_no_connection_notice(library: EditorLibrary) -> None:
    """E2E-167: nothing typed, nothing shown (FR-NEW-074); after "!" the expiry notice alone, within 2 seconds."""
    deck = library.decks[HEART_FAILURE]
    dan = library.open(DAN, HEART_FAILURE, edit=True)
    end_sessions(library, extra=10.0)
    stays_quiet(dan, seconds=3)

    type_in_title(dan, "!")

    wait_until(dan, lambda: notice_text(dan), lambda text: text == EXPIRED, what="the expiry notice", bound=2.0)
    stays_quiet_except_error(dan, seconds=10)
    assert frame_title(dan) == "Heart Failure Update!"
    assert stored_title(deck) == HEART_FAILURE
    assert library.served_title(CAROL, HEART_FAILURE) == HEART_FAILURE


def test_e2e_170_a_notice_inside_the_editor_is_english_next_to_french_labels(library: EditorLibrary) -> None:
    """E2E-170."""
    dan = library.open(DAN, STATINS, edit=True)
    type_in_title(dan, " B")
    remove_dan_everywhere(library)

    leave_field(dan)

    wait_until(dan, lambda: notice_text(dan), lambda text: text == DENIED, what="denied notice", bound=5.0)
    labels = [dan.get_attribute(f"#{control}", "aria-label") for control in ("edit-mode-btn", "undo-btn", "redo-btn")]
    assert labels == ["Édition", "Annuler", "Rétablir"]


def test_e2e_178_moving_between_slides_is_not_an_action_that_needs_the_library(library: EditorLibrary) -> None:
    """E2E-178: slides change with no notice after the folder is deleted; the HTML download then shows "Access
    denied." and no file is received."""
    deck = library.decks[HEART_FAILURE]
    deck.path.write_bytes(deck_with_notes(("One", "Two", "Three", "Four"), "notes"))
    carol = library.open(CAROL, HEART_FAILURE)
    downloads: list[object] = []
    messages: list[str] = []
    carol.on("download", lambda download: downloads.append(download))  # noqa: PLW0108 - Playwright wants a function
    carol.on("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.post_json(f"/api/folders/{library.ids[CARDIOLOGY]}/delete", {"confirm": CARDIOLOGY}).status == 200

    deck_frame(carol).locator(".slide").first.click()
    for _ in range(2):
        carol.keyboard.press("ArrowRight")
    wait_for_js(deck_frame(carol), CURRENT_SLIDE, 2, what="slide 3")
    stays_quiet(carol, seconds=2)
    carol.click("#download-btn")

    wait_until(carol, lambda: messages, bool, what="the alert")
    assert messages == [DENIED]
    assert downloads == []
    assert frame_title(carol) != ""


def test_e2e_188_a_change_stored_after_signing_in_again_meets_the_conflict_notice(library: EditorLibrary) -> None:
    """E2E-188: Dan typed "Statins B", his session ended, the administrator stored "Statins A", Dan signed in again:
    leaving the field shows the conflict notice and stores nothing."""
    deck = library.decks[STATINS]
    dan = library.open(DAN, STATINS, edit=True)
    type_in_title(dan, "Statins B", replace=True)
    end_sessions(library)
    admin = signed_in(library.running, library.google, ADMIN)
    admin.open_presentation(deck.id)
    assert admin.save(deck.id, with_title(deck, "Statins A")).status == 200
    signed_in(library.running, library.google, DAN)

    leave_field(dan)

    wait_until(dan, lambda: notice_visible(dan, "save-conflict"), bool, what="the conflict notice")
    assert CONFLICT_TEXT in dan.locator("#save-conflict").inner_text()
    assert dan.locator("#save-conflict").get_by_role("button", name="Keep mine").is_visible()
    assert dan.locator("#save-conflict").get_by_role("button", name="Reload").is_visible()
    assert stored_title(deck) == "Statins A"
