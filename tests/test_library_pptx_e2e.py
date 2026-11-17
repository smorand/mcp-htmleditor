"""US-0140: the toolbar options, the downloads and the quiet screen of the library editor in Chromium (SPEC-0025).

Spec tests: E2E-042, E2E-119, E2E-173, E2E-177. A download is observed with Playwright's ``download`` event, a refused
one through the alert it shows. The 60 seconds of the spec are 12 seconds here: the poll runs every 100 ms, so 120
polls pass, far beyond the 3 failures that would show the lost connection notice.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright

from tests import library_support
from tests.browser_wait import settle, wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    DAN,
    HEART_FAILURE,
    STATINS,
    EditorLibrary,
    deck_frame,
    deck_with_notes,
    frame_title,
    launch_chromium,
    notice_visible,
    signed_in,
    stored_title,
    type_in_title,
)
from tests.test_library_access_e2e import DENIED, EXPIRED, end_sessions, stays_quiet

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
library = library_support.library

LABELS = {
    "edit-mode-btn": "Édition",
    "undo-btn": "Annuler",
    "redo-btn": "Rétablir",
    "present-btn": "Mode présentation plein écran",
    "pointer-btn": "Présenter avec le pointeur",
    "presenter-btn": "Vue présentateur",
    "notes-btn": "Notes",
    "requests-toggle": "Requests",
    "ask-ai-btn": "Ask AI",
    "export-pptx-btn": "Télécharger en PPTX",
    "download-btn": "Télécharger le fichier HTML",
    "help-btn": "Raccourcis clavier",
}
NOTE = "Mention the 2026 guideline"


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def watch(page: Page) -> tuple[list[object], list[str]]:
    """The downloads received and the alert messages shown by ``page`` (a dialog is dismissed)."""
    downloads: list[object] = []
    messages: list[str] = []
    page.on("download", lambda download: downloads.append(download))  # noqa: PLW0108 - Playwright wants a function
    page.on("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
    return downloads, messages


def test_e2e_042_every_option_of_the_local_editor_is_present(library: EditorLibrary) -> None:
    """E2E-042: the French labels of the local mode, the keys, a note typed for slide 1 shown by the presenter window
    and a DOCX requested by hand refused to a RW person."""
    library.decks[HEART_FAILURE].path.write_bytes(deck_with_notes(("Heart Failure Update", "Two"), "first"))
    viewing = library.open(DAN, HEART_FAILURE)
    wait_until(viewing, lambda: viewing.locator("#pointer-btn").is_visible(), bool, what="pointer control")
    page = library.open(DAN, HEART_FAILURE)
    page.click(
        "#edit-mode-btn"
    )  # the cover of this deck has no h1: the generic wait of ``turn_edit_on`` does not apply
    wait_until(page, lambda: page.get_attribute("#edit-mode-btn", "aria-pressed"), lambda v: v == "true", what="edit")

    for control, label in LABELS.items():
        shown = page.get_attribute(f"#{control}", "aria-label")
        assert shown == label or (control == "requests-toggle" and shown == "Requests (0)"), control  # the count
        if control != "pointer-btn":  # the pointer is a presenting option: hidden while editing, as in the local mode
            assert page.locator(f"#{control}").is_visible(), control
    page.click("#notes-btn")
    page.fill("#notes-text", NOTE)
    with page.context.expect_page(timeout=10_000) as opened:
        page.click("#presenter-btn")  # the key S would go to the notes field that holds the focus
    presenter = opened.value
    wait_until(presenter, lambda: presenter.inner_text("#p-notes"), lambda text: text == NOTE, what="note in presenter")
    page.locator("body").press("?")
    wait_until(page, lambda: page.locator("#help-panel").is_visible(), bool, what="help panel")
    docx = signed_in(library.running, library.google, DAN)
    docx.open_presentation(library.decks[HEART_FAILURE].id)
    reply = docx.deck(library.decks[HEART_FAILURE].id, "export/docx", x_editor="1")
    assert reply.status == 403
    assert reply.json()["error"] == DENIED
    assert not reply.body.startswith(b"PK")


def test_e2e_119_a_download_after_the_folder_was_deleted_is_refused(library: EditorLibrary) -> None:
    """E2E-119: "Access denied." alone (no "Export PPTX échoué :"), no file, the slide stays."""
    carol = library.open("carol.ro@example.org", HEART_FAILURE)
    downloads, messages = watch(carol)
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.post_json(f"/api/folders/{library.ids[CARDIOLOGY]}/delete", {"confirm": CARDIOLOGY}).status == 200

    carol.click("#export-pptx-btn")

    wait_until(carol, lambda: messages, bool, what="the alert")
    assert messages == [DENIED]
    assert downloads == []
    assert frame_title(carol) == HEART_FAILURE
    assert deck_frame(carol).locator(".slide").first.is_visible()


def test_e2e_173_a_session_that_ended_gives_a_quiet_screen_until_the_person_acts(library: EditorLibrary) -> None:
    """E2E-173: no notice at all while nothing is unstored; the HTML download then shows the sign in page; with "!"
    unstored the PPTX download shows the expiry notice and no file; with nothing unstored it shows the sign in page."""
    deck = library.decks[HEART_FAILURE]
    dan = library.open(DAN, HEART_FAILURE, edit=True)
    downloads, _messages = watch(dan)
    end_sessions(library)

    stays_quiet(dan, seconds=12)
    dan.click("#download-btn")

    wait_until(dan, lambda: dan.url, lambda url: url.startswith(library.running.origin), what="the sign in page")
    assert "Sign in with Google" in dan.locator("body").inner_text()
    assert downloads == []
    assert stored_title(deck) == HEART_FAILURE

    typing = library.open(DAN, HEART_FAILURE, edit=True)
    typed_downloads, _ = watch(typing)
    type_in_title(typing, "!")
    end_sessions(library, extra=2.0)
    typing.click("#export-pptx-btn")
    wait_until(typing, lambda: notice_visible(typing, "save-error"), bool, what="the expiry notice")
    assert typing.locator("#save-error .notice-text").inner_text() == EXPIRED
    assert typed_downloads == []

    quiet = library.open(DAN, HEART_FAILURE, edit=True)
    quiet_downloads, _ = watch(quiet)
    end_sessions(library, extra=3.0)
    quiet.click("#export-pptx-btn")
    wait_until(quiet, lambda: quiet.url, lambda url: url.startswith(library.running.origin), what="the sign in page")
    assert quiet_downloads == []


def test_e2e_177_a_removed_right_gives_a_quiet_screen_then_access_denied(library: EditorLibrary) -> None:
    """E2E-177: no notice while Dan waits, then the PPTX download shows "Access denied." and no file; the stored deck
    and Carol's view are unchanged."""
    deck = library.decks[STATINS]
    before = deck.path.read_bytes()
    dan = library.open(DAN, STATINS, edit=True)
    downloads, messages = watch(dan)
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.remove_member(library.ids[CARDIOLOGY], DAN).status == 200

    stays_quiet(dan, seconds=12)
    dan.click("#export-pptx-btn")

    wait_until(dan, lambda: messages, bool, what="the alert")
    assert messages == [DENIED]
    assert downloads == []
    assert deck.path.read_bytes() == before
    assert library.served_title("carol.ro@example.org", STATINS) == STATINS
    settle(dan)
