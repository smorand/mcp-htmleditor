"""US-0145: deleting a presentation from the folder page in Chromium (SPEC-0025).

Spec tests: E2E-033, E2E-036, E2E-040, E2E-053, E2E-079, E2E-080, E2E-081, E2E-083, E2E-181, E2E-SEC-014, E2E-SEC-017.
The second channel is the stored files and their history, the activity table, what the administrator lists and what a
hostile page or a deck script could observe or change.
"""

from __future__ import annotations

import html
import io
import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright
from pptx import Presentation as PptxPresentation

from mcp_htmleditor.request_store import RequestStore
from tests import library_support
from tests.browser_wait import settle, wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    EVIL_HOST,
    HEART_FAILURE,
    PNEUMO,
    STATINS,
    WCBIP,
    EditorLibrary,
    RecordingListener,
    deck_frame,
    deck_with_notes,
    frame_title,
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
evil_listener = library_support.evil_listener
library = library_support.library

DENIED = "Access denied."
NAMES = "() => [...document.querySelectorAll('ul.presentations li')].map(row => row.querySelector('.name').textContent)"
QUESTION = 'Delete "Statins Review"? This cannot be undone.'


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright, EVIL_HOST)
    yield browser
    browser.close()


def folder_page(library: EditorLibrary, email: str, folder: str = CARDIOLOGY) -> Page:
    person = signed_in(library.running, library.google, email)
    page = person_context(library.chromium, library.running, person.cookies["lib"]).new_page()
    page.goto(f"{library.running.origin}/f/{library.ids[folder]}")
    return page


def question(page: Page) -> str:
    return page.locator("#confirm-question").inner_text() if page.locator("#confirm-dialog").is_visible() else ""


def delete_button(page: Page, name: str):
    return page.locator("li", has=page.get_by_role("link", name=name, exact=True)).get_by_role("button", name="Delete")


def lines(library: EditorLibrary) -> list[str]:
    return [row[2] for row in signed_in(library.running, library.google, ADMIN).open("/admin").activity_lines()]


def admin_names(library: EditorLibrary, folder: str = CARDIOLOGY) -> list[str]:
    admin = signed_in(library.running, library.google, ADMIN)
    return [html.unescape(row[0]) for row in admin.open(f"/f/{library.ids[folder]}").presentation_rows()]


def test_e2e_079_a_rw_member_deletes_a_presentation(library: EditorLibrary) -> None:
    """E2E-079: the question first, Cancel next to Delete, then two rows, no history, one activity line."""
    deck = library.decks[STATINS]
    library.running.builder.records(deck)
    record_dir = RequestStore(library.running.state_dir).record_dir(deck.path).parent
    page = folder_page(library, DAN)

    delete_button(page, STATINS).click()
    wait_until(page, lambda: question(page), lambda text: text == QUESTION, what="the question")
    assert page.get_by_role("button", name="Cancel").is_visible()
    page.locator("#confirm-yes").click()

    wait_until(page, lambda: page.evaluate(NAMES), lambda names: STATINS not in names, what="the list")
    assert len(page.evaluate(NAMES)) == 2
    assert len(admin_names(library)) == 2
    assert not deck.path.exists()
    assert not record_dir.exists()
    assert lines(library) == [f'Deleted "{STATINS}" from "{CARDIOLOGY}"']


def test_e2e_080_cancel_keeps_the_presentation(library: EditorLibrary) -> None:
    deck = library.decks[STATINS]
    library.running.builder.records(deck)
    page = folder_page(library, DAN)
    versions = len(library.running.versions(deck))

    delete_button(page, STATINS).click()
    wait_until(page, lambda: question(page), lambda text: text == QUESTION, what="the question")
    page.get_by_role("button", name="Cancel").click()

    wait_until(page, lambda: page.locator("#confirm-dialog").is_visible(), lambda shown: not shown, what="closed")
    settle(page)
    assert STATINS in page.evaluate(NAMES)
    assert len(library.running.versions(deck)) == versions
    assert lines(library) == []


def test_e2e_081_confirming_the_deletion_of_an_already_deleted_presentation_is_refused(library: EditorLibrary) -> None:
    page = folder_page(library, DAN)
    delete_button(page, STATINS).click()
    wait_until(page, lambda: question(page), lambda text: text == QUESTION, what="the question")
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.delete_presentation(library.decks[STATINS].id).status == 200

    page.locator("#confirm-yes").click()

    wait_until(page, lambda: page.locator("#upload-status").inner_text(), lambda text: text == DENIED, what="denied")
    wait_until(page, lambda: page.evaluate(NAMES), lambda names: STATINS not in names, what="the refreshed list")
    assert len(page.evaluate(NAMES)) == 2
    assert lines(library) == [f'Deleted "{STATINS}" from "{CARDIOLOGY}"']


def test_e2e_083_the_question_shows_an_accented_name_with_an_apostrophe_as_written(library: EditorLibrary) -> None:
    folder = library.ids[PNEUMO]
    library.running.builder.presentation(
        folder, "L'été (v2)", size=4_096, modified=library.decks[STATINS].path.stat().st_mtime and _modified()
    )
    page = folder_page(library, ADMIN, PNEUMO)

    delete_button(page, "L'été (v2)").click()
    wait_until(
        page, lambda: question(page), lambda text: text == 'Delete "L\'été (v2)"? This cannot be undone.', what="q"
    )
    page.get_by_role("button", name="Cancel").click()
    delete_button(page, "L'été (v2)").click()
    wait_until(page, lambda: question(page), lambda text: text != "", what="the question again")
    page.locator("#confirm-yes").click()

    wait_until(
        page,
        lambda: page.locator("p").all_inner_texts(),
        lambda texts: "This folder has no presentations yet." in texts,
        what="empty",
    )


def _modified():
    from datetime import UTC, datetime

    return datetime(2026, 11, 10, 9, 15, tzinfo=UTC)


def test_e2e_036_a_rw_member_sees_the_upload_and_delete_controls_in_their_folder(library: EditorLibrary) -> None:
    page = folder_page(library, DAN)

    assert page.get_by_label("Upload").count() == 1
    assert page.get_by_role("button", name="Delete", exact=True).count() == 3
    page.get_by_role("link", name=HEART_FAILURE).click()
    page.wait_for_url(re.compile(r"/d/[0-9a-f]{32}/$"))
    wait_until(page, lambda: page.locator("#edit-mode-btn").is_visible(), bool, what="the edit control")


def test_e2e_033_roles_are_per_folder(library: EditorLibrary) -> None:
    """E2E-033: Carol is RO in Cardiology and RW in Pneumo: no Upload or Delete in the first, both in the second."""
    library.running.builder.member(library.ids[PNEUMO], CAROL, "RW")
    page = folder_page(library, CAROL)
    assert page.get_by_label("Upload").count() == 0
    assert page.get_by_role("button", name="Delete", exact=True).count() == 0

    page.goto(f"{library.running.origin}/f/{library.ids[PNEUMO]}")
    assert page.get_by_label("Upload").count() == 1
    page.set_input_files(
        "#upload-file", files=[{"name": "Spirometry Basics.html", "mimeType": "text/html", "buffer": valid_deck()}]
    )
    wait_until(
        page,
        lambda: page.locator("#upload-status").inner_text(),
        lambda t: t == "Uploaded Spirometry Basics.",
        what="m",
    )
    assert page.get_by_role("button", name="Delete", exact=True).count() == 1
    page.goto(f"{library.running.origin}/")
    labels = page.locator("ul.folders li").all_inner_texts()
    assert any(CARDIOLOGY in text and "Read only" in text for text in labels)
    assert any(PNEUMO in text and "Read and write" in text for text in labels)
    assert "Spirometry Basics" in admin_names(library, PNEUMO)
    assert "Spirometry Basics" not in admin_names(library, CARDIOLOGY)


def test_e2e_040_a_rw_member_does_everything_with_the_keyboard(library: EditorLibrary) -> None:
    """E2E-040: Tab to Upload, choose the file, Tab to Delete on that row, confirm with Enter, Tab to Sign out."""
    page = folder_page(library, DAN)
    page.get_by_label("Upload").focus()
    assert page.evaluate("document.activeElement.id") == "upload-file"
    page.set_input_files(
        "#upload-file", files=[{"name": "Quarterly Review.html", "mimeType": "text/html", "buffer": valid_deck()}]
    )
    wait_until(
        page, lambda: page.locator("#upload-status").inner_text(), lambda t: t == "Uploaded Quarterly Review.", what="m"
    )

    delete_button(page, "Quarterly Review").focus()
    page.keyboard.press("Enter")
    wait_until(page, lambda: question(page), lambda text: text.startswith('Delete "Quarterly Review"'), what="question")
    page.get_by_role("button", name="Delete", exact=True).last.focus()
    page.keyboard.press("Enter")
    wait_until(page, lambda: page.evaluate(NAMES), lambda names: "Quarterly Review" not in names, what="gone")
    page.get_by_role("button", name="Sign out").focus()
    page.keyboard.press("Enter")

    page.wait_for_url(f"{library.running.origin}/")
    assert "Sign in with Google" in page.locator("body").inner_text()


def test_e2e_053_saving_a_deleted_presentation_is_refused(library: EditorLibrary) -> None:
    deck = library.decks[STATINS]
    dan = library.open(DAN, STATINS, edit=True)
    type_in_title(dan, " B")
    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.delete_presentation(deck.id).status == 200

    leave_field(dan)

    wait_until(
        dan,
        lambda: dan.locator("#save-error .notice-text").inner_text() if notice_visible(dan, "save-error") else "",
        lambda text: text == DENIED,
        what="denied notice",
        bound=5.0,
    )
    assert frame_title(dan) == f"{STATINS} B"
    assert not deck.path.exists()
    assert len(admin_names(library)) == 2


def test_e2e_181_changes_from_the_librarys_own_pages_are_accepted(library: EditorLibrary) -> None:
    page = folder_page(library, DAN)
    page.set_input_files(
        "#upload-file", files=[{"name": "Quarterly Review.html", "mimeType": "text/html", "buffer": valid_deck()}]
    )
    wait_until(
        page, lambda: page.locator("#upload-status").inner_text(), lambda t: t == "Uploaded Quarterly Review.", what="m"
    )

    delete_button(page, "Quarterly Review").click()
    wait_until(page, lambda: question(page), lambda text: text != "", what="the question")
    page.locator("#confirm-yes").click()

    wait_until(page, lambda: page.evaluate(NAMES), lambda names: "Quarterly Review" not in names, what="gone")
    assert DENIED not in page.locator("body").inner_text()


def test_e2e_sec_017_a_page_of_another_site_deletes_with_the_visitors_session(
    library: EditorLibrary, evil_listener: RecordingListener
) -> None:
    """E2E-SEC-017. Red before the fix because: the deletion is accepted because the browser attached Dan's session;
    "Statins Review is still listed to the administrator" fails. The hostile page posts a form on load."""
    deck = library.decks[STATINS]
    library.running.builder.records(deck)
    person = signed_in(library.running, library.google, DAN)
    context = person_context(library.chromium, library.running, person.cookies["lib"])
    target = f"{library.running.origin}/api/presentations/{deck.id}/delete"
    evil_listener.page = (
        f'<!DOCTYPE html><html><body><form id="win" method="post" action="{target}"></form>'
        "<script>document.getElementById('win').submit();</script></body></html>"
    )
    page = context.new_page()

    page.goto(f"http://{EVIL_HOST}:{evil_listener.port}/win")

    wait_until(page, lambda: page.url, lambda url: url.startswith(library.running.origin), what="the form was posted")
    assert DENIED in page.locator("body").inner_text()
    assert STATINS in admin_names(library)
    assert deck.path.stat().st_size == 1_572_864
    assert library.running.versions(deck) != []
    assert lines(library) == []


def test_e2e_sec_014_a_presentations_script_cannot_act_as_the_viewer_or_reach_other_folders(
    library: EditorLibrary,
) -> None:
    """E2E-SEC-014. Red before the fix because: the script deletes "Statins Review" with Dan's rights. The script
    lists the WCBIP folder and sends DELETE for "Statins Review" with the real addresses of the library."""
    statins, heart = library.decks[STATINS], library.decks[HEART_FAILURE]
    library.running.builder.records(statins)
    origin = library.running.origin
    script = (
        f"fetch('{origin}/f/{library.ids[WCBIP]}', {{credentials: 'include'}}).then(r => r.text())"
        ".then(t => { probe.textContent += ' list: ' + t.slice(0, 200); })"
        ".catch(e => { probe.textContent += ' list: blocked'; });"
        f"fetch('{origin}/api/presentations/{statins.id}', {{method: 'DELETE', credentials: 'include'}})"
        ".then(r => { probe.textContent += ' delete: ' + r.status; })"
        ".catch(e => { probe.textContent += ' delete: blocked'; });"
    )
    heart.path.write_bytes(
        deck_with_notes((HEART_FAILURE, "Two"), "notes", script).replace(b'id="probe"', b'id="probe"')
    )
    texts = []
    for email in (CAROL, DAN):
        page = library.open(email, HEART_FAILURE)
        wait_until(
            page,
            lambda page=page: deck_frame(page).evaluate("document.getElementById('probe').textContent"),
            lambda t: "delete:" in t and "list:" in t,
            what="probe",
        )
        texts.append(deck_frame(page).evaluate("document.getElementById('probe').textContent"))
        settle(page)

    for text in texts:
        assert "Challenges to Change" not in text
        assert "Bridging" not in text
        assert "WCBIP" not in text
    assert STATINS in admin_names(library)
    assert library.running.versions(statins) != []
    assert lines(library) == []
    carol = signed_in(library.running, library.google, CAROL)
    carol.open_presentation(heart.id)
    pptx = carol.deck(heart.id, "export/pptx", x_editor="1")
    assert pptx.status == 200
    slides_text = " ".join(
        shape.text_frame.text
        for slide in PptxPresentation(io.BytesIO(pptx.body)).slides
        for shape in slide.shapes
        if shape.has_text_frame
    )
    assert "Challenges to Change" not in slides_text
    assert "Bridging" not in slides_text
