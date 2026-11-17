"""US-0144: the Replace question of the Upload control in Chromium (SPEC-0025).

Spec tests: E2E-052, E2E-066, E2E-067, E2E-077. The second channel is the stored file, its history, its request record
and the activity table. A conflict with an open edit is the editor's own notice (``check_conflict`` sees the new mtime).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright

from mcp_htmleditor.request_service import RequestService
from mcp_htmleditor.request_store import RequestStore
from tests import library_support
from tests.browser_wait import settle, wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    CAROL,
    DAN,
    STATINS,
    EditorLibrary,
    launch_chromium,
    leave_field,
    notice_visible,
    person_context,
    signed_in,
    type_in_title,
    valid_deck,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
library = library_support.library

QUESTION = 'A presentation named "Statins Review" already exists. Replace it?'
STATINS_BYTES = 1_572_864
NEW_BYTES = 307_200
CONFLICT_TEXT = "The file changed on disk. Reload to see the changes, or keep your version."
NAMES = "() => [...document.querySelectorAll('ul.presentations li')].map(row => row.querySelector('.name').textContent)"


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def folder_page(library: EditorLibrary, email: str = DAN) -> Page:
    person = signed_in(library.running, library.google, email)
    page = person_context(library.chromium, library.running, person.cookies["lib"]).new_page()
    page.goto(f"{library.running.origin}/f/{library.ids['Cardiology 2027']}")
    return page


def choose(page: Page, name: str, data: bytes) -> None:
    page.set_input_files("#upload-file", files=[{"name": name, "mimeType": "text/html", "buffer": data}])


def question(page: Page) -> str:
    return page.locator("#replace-question").inner_text() if page.locator("#replace-upload").is_visible() else ""


def lines(library: EditorLibrary) -> list[str]:
    return [row[2] for row in signed_in(library.running, library.google, ADMIN).open("/admin").activity_lines()]


def test_e2e_066_a_same_name_upload_asks_and_replace_replaces(library: EditorLibrary) -> None:
    """E2E-066: the question first, then "Uploaded Statins Review." and 300.0 KB, one history version of 1 572 864
    bytes, the capital letters kept, one "Replaced" line, the request still queued."""
    deck = library.decks[STATINS]
    old = deck.path.read_bytes()
    RequestService(RequestStore(library.running.state_dir)).queue(deck.path, "Shorten the title", None)
    page = folder_page(library)

    choose(page, "statins review.HTML", valid_deck(2, NEW_BYTES))

    wait_until(page, lambda: question(page), lambda text: text == QUESTION, what="the question")
    assert page.get_by_role("button", name="Replace").is_visible()
    assert page.get_by_role("button", name="Cancel").is_visible()
    page.get_by_role("button", name="Replace").click()
    wait_until(
        page,
        lambda: page.locator("#upload-status").inner_text(),
        lambda t: t == "Uploaded Statins Review.",
        what="message",
    )
    wait_until(
        page,
        lambda: page.locator("ul.presentations li .size").all_inner_texts(),
        lambda sizes: "300.0 KB" in sizes,
        what="size",
    )
    assert page.evaluate(NAMES).count(STATINS) == 1
    assert len(page.evaluate(NAMES)) == 3
    (version,) = library.running.versions(deck)
    assert version.bytes == STATINS_BYTES
    assert library.running.version_text(deck, version).encode() == old
    assert lines(library) == ['Replaced "Statins Review" in "Cardiology 2027"']
    snapshot = RequestService(RequestStore(library.running.state_dir)).snapshot(deck.path)
    assert [request.instruction for request in snapshot.requests] == ["Shorten the title"]


def test_e2e_067_cancel_changes_nothing(library: EditorLibrary) -> None:
    deck = library.decks[STATINS]
    digest = hashlib.sha256(deck.path.read_bytes()).hexdigest()
    page = folder_page(library)
    before = page.evaluate(NAMES)

    choose(page, "statins review.HTML", valid_deck(2, NEW_BYTES))
    wait_until(page, lambda: question(page), lambda text: text == QUESTION, what="the question")
    page.get_by_role("button", name="Cancel").click()

    wait_until(
        page, lambda: page.locator("#replace-upload").is_visible(), lambda shown: not shown, what="dialog closed"
    )
    settle(page)
    assert page.evaluate(NAMES) == before
    assert "1.5 MB" in page.locator("ul.presentations li .size").all_inner_texts()
    assert hashlib.sha256(deck.path.read_bytes()).hexdigest() == digest
    assert library.running.versions(deck) == []
    assert lines(library) == []
    assert page.locator("#upload-file").evaluate("element => document.activeElement === element")  # focus came back


def test_e2e_077_confirming_replace_twice_replaces_once(library: EditorLibrary) -> None:
    deck = library.decks[STATINS]
    page = folder_page(library)
    choose(page, "Statins Review.html", valid_deck(2, NEW_BYTES))
    wait_until(page, lambda: question(page), lambda text: text == QUESTION, what="the question")

    page.get_by_role("button", name="Replace").click(click_count=2)

    wait_until(
        page,
        lambda: page.locator("#upload-status").inner_text(),
        lambda t: t == "Uploaded Statins Review.",
        what="message",
    )
    settle(page)
    (version,) = library.running.versions(deck)
    assert version.bytes == STATINS_BYTES
    assert lines(library) == ['Replaced "Statins Review" in "Cardiology 2027"']


def test_e2e_052_a_replacement_during_an_edit_triggers_the_notice(library: EditorLibrary) -> None:
    """E2E-052: Dan has typed in slide 2 and has not left the field; the administrator replaces the file; leaving the
    field shows the conflict notice, nothing of Dan's is stored, and Carol is served the replaced content."""
    deck = library.decks[STATINS]
    dan = library.open(DAN, STATINS, edit=True)
    type_in_title(dan, "Statins C", replace=True, index=1)
    replacement = valid_deck(2, NEW_BYTES)
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.upload(library.ids["Cardiology 2027"], "Statins Review.html", replacement, replace=True).status == 201

    leave_field(dan)

    wait_until(dan, lambda: notice_visible(dan, "save-conflict"), bool, what="the conflict notice")
    assert CONFLICT_TEXT in dan.locator("#save-conflict").inner_text()
    assert deck.path.read_bytes() == replacement
    assert b"Statins C" not in deck.path.read_bytes()
    carol = signed_in(library.running, library.google, CAROL)
    carol.open_presentation(deck.id)
    assert b"Slide 1" in carol.deck(deck.id, "content", x_editor="1").body
