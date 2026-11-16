"""US-0135: the read only editor, full screen, presenter window and hostile script isolation (SPEC-0025).

Spec tests: E2E-021, E2E-030, E2E-032, E2E-109, E2E-121, E2E-180, E2E-SEC-013. People sign in over HTTP through
``FakeGoogle`` and Chromium holds their session cookie; the presentations are real "ei" decks (presenter, pointer
and full screen scripts included) written into the library by the builder.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright

from tests import library_support
from tests.browser_wait import wait_for_js, wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    HEART_FAILURE,
    STATINS,
    FakeGoogle,
    Presentation,
    RunningLibrary,
    deck_frame,
    deck_with_notes,
    launch_chromium,
    open_presenter,
    person_context,
    signed_in,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
TITLES = (HEART_FAILURE, "Epidemiology", "Treatment", "Follow up")
NOTES = "Welcome and objectives"
PROBE_SCRIPT = (
    "document.getElementById('probe').textContent = 'stored: ' + document.cookie + ' | '"
    " + JSON.stringify(localStorage) + ' | ' + JSON.stringify(sessionStorage);"
)
HIDDEN_CONTROLS = (
    "edit-mode-btn",
    "undo-btn",
    "redo-btn",
    "requests-toggle",
    "ask-ai-btn",
    "notes-btn",
    "toolbar-slide-actions",
    "toolbar-doc-actions",
    "export-docx-btn",
)
KEPT_CONTROLS = ("present-btn", "download-btn", "help-btn")
VISIBLE_SCRIPT = (
    "id => { const e = document.getElementById(id); return !!e && getComputedStyle(e).display !== 'none'; }"
)
CURRENT_SLIDE = "[...document.querySelectorAll('.slide')].findIndex(s => s.classList.contains('active'))"


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def library_with_deck(running: RunningLibrary, script: str = "") -> tuple[dict[str, str], Presentation]:
    """The standard folders and the real deck "Heart Failure Update" (notes on slide 1) in Cardiology."""
    ids = running.builder.standard()
    heart = running.builder.presentation(ids[CARDIOLOGY], HEART_FAILURE, size=1, modified=MODIFIED, slides=1)
    heart.path.write_bytes(deck_with_notes(TITLES, NOTES, script))
    return ids, heart


def page_of(chromium: Chromium, running: RunningLibrary, google: FakeGoogle, email: str) -> Page:
    person = signed_in(running, google, email)
    return person_context(chromium, running, person.cookies["lib"]).new_page()


def open_deck(page: Page, running: RunningLibrary, presentation: Presentation) -> None:
    """Follow the folder page link style address ``/open/<pid>`` to the editor shell, deck loaded."""
    page.goto(f"{running.origin}/open/{presentation.id}")
    page.wait_for_url(f"{running.content_origin}/d/{presentation.id}/")
    wait_for_js(
        deck_frame(page), "document.querySelectorAll('section.slide, article.slide').length", len(TITLES), what="slides"
    )


def visible(page: Page, element_id: str) -> bool:
    return bool(page.evaluate(VISIBLE_SCRIPT, element_id))


def test_e2e_032_a_ro_member_has_no_control_that_changes_anything(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-032: Carol (RO) sees no edit mode, undo, redo, requests, Ask AI, notes or slide actions, keeps full
    screen, download and help, and the key E leaves ``aria-pressed`` false and the deck not editable."""
    running = library_server(fake_google)
    _ids, heart = library_with_deck(running)
    page = page_of(chromium, running, fake_google, CAROL)

    open_deck(page, running, heart)
    page.locator("body").press("e")

    for control in HIDDEN_CONTROLS:
        assert not visible(page, control), control
    for control in KEPT_CONTROLS:
        assert visible(page, control), control
    assert page.get_attribute("#edit-mode-btn", "aria-pressed") == "false"
    assert deck_frame(page).evaluate("document.querySelectorAll('[contenteditable=\"true\"]').length") == 0
    for control in KEPT_CONTROLS:
        assert page.get_attribute(f"#{control}", "aria-label"), control


def test_e2e_032_the_edit_message_of_the_deck_is_stopped_too(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """The key E typed inside the deck frame posts ``deck-key``; for RO it must not switch edit mode on."""
    running = library_server(fake_google)
    _ids, heart = library_with_deck(running)
    page = page_of(chromium, running, fake_google, CAROL)
    open_deck(page, running, heart)

    deck_frame(page).evaluate("window.parent.postMessage({type: 'deck-key', key: 'E'}, '*')")

    page.wait_for_timeout(300)  # pacing: a message that must NOT have an effect has nothing to wait for
    assert page.get_attribute("#edit-mode-btn", "aria-pressed") == "false"
    assert deck_frame(page).evaluate("document.querySelectorAll('[contenteditable=\"true\"]').length") == 0


def test_a_deck_edit_message_switches_edit_mode_on_for_rw(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """Positive control of the test above: the same message does switch edit mode on for Dan (RW)."""
    running = library_server(fake_google)
    _ids, heart = library_with_deck(running)
    page = page_of(chromium, running, fake_google, DAN)
    open_deck(page, running, heart)

    deck_frame(page).evaluate("window.parent.postMessage({type: 'deck-key', key: 'E'}, '*')")

    wait_until(page, lambda: page.get_attribute("#edit-mode-btn", "aria-pressed"), lambda v: v == "true", what="edit")


def test_a_rw_member_keeps_every_control_and_the_key_e_works(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """Dan (RW) is not restricted: the edit button shows and the key E turns edit mode on."""
    running = library_server(fake_google)
    _ids, heart = library_with_deck(running)
    page = page_of(chromium, running, fake_google, DAN)
    open_deck(page, running, heart)

    assert visible(page, "edit-mode-btn")
    page.locator("body").press("e")

    wait_until(page, lambda: page.get_attribute("#edit-mode-btn", "aria-pressed"), lambda v: v == "true", what="edit")


def test_e2e_030_a_ro_member_views_and_presents(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-030: full screen with F shows slide 1; the presenter window (S) shows the title, the next slide, the
    notes, the counter and the timer; the arrow keys move both windows."""
    running = library_server(fake_google)
    _ids, heart = library_with_deck(running)
    page = page_of(chromium, running, fake_google, CAROL)
    open_deck(page, running, heart)

    page.locator("body").press("f")
    wait_until(page, lambda: page.evaluate("!!document.fullscreenElement"), bool, what="full screen")
    assert deck_frame(page).evaluate(CURRENT_SLIDE) == 0
    page.locator("body").press("Escape")
    wait_until(page, lambda: page.evaluate("!!document.fullscreenElement"), lambda on: not on, what="left full screen")

    presenter = open_presenter(page)
    wait_until(presenter, lambda: presenter.inner_text("#p-notes"), lambda t: t == NOTES, what="notes")
    assert presenter.inner_text("#p-title") == HEART_FAILURE
    assert presenter.inner_text("#p-next-title") == "Epidemiology"
    assert presenter.inner_text("#p-count") == f"1 / {len(TITLES)}"
    assert re.fullmatch(r"\d\d:\d\d:\d\d", presenter.inner_text("#p-timer"))
    presenter.locator("body").press("ArrowRight")
    wait_until(
        presenter, lambda: presenter.inner_text("#p-count"), lambda t: t.startswith("2 /"), what="presenter moved"
    )
    wait_for_js(deck_frame(page), CURRENT_SLIDE, 1, what="deck moved with the presenter")
    assert not visible(page, "edit-mode-btn")


def test_e2e_121_an_open_presenter_window_keeps_what_it_loaded(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-121: Carol's presenter window is open when the administrator removes her; the slides it already holds
    still change. A reload of the editor itself then shows ``Access denied.``"""
    running = library_server(fake_google)
    ids, heart = library_with_deck(running)
    page = page_of(chromium, running, fake_google, CAROL)
    open_deck(page, running, heart)
    presenter = open_presenter(page)
    wait_until(presenter, lambda: presenter.inner_text("#p-notes"), lambda t: t == NOTES, what="notes")
    admin = signed_in(running, fake_google, ADMIN)

    assert admin.remove_member(ids[CARDIOLOGY], CAROL).status == 200
    for expected in ("2", "3", "4"):
        presenter.locator("body").press("ArrowRight")
        wait_until(
            presenter, lambda: presenter.inner_text("#p-count"), lambda t, e=expected: t.startswith(e), what="moves"
        )

    page.reload()
    wait_until(page, lambda: page.locator("body").inner_text(), lambda t: "Access denied." in t, what="denied")


def test_e2e_109_a_role_change_shows_the_controls_and_a_removal_refuses(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-109: Carol changed to RW has the edit controls on her next open; Dan removed is refused."""
    running = library_server(fake_google)
    ids, heart = library_with_deck(running)
    admin = signed_in(running, fake_google, ADMIN)
    carol = page_of(chromium, running, fake_google, CAROL)
    open_deck(carol, running, heart)
    assert not visible(carol, "edit-mode-btn")

    assert admin.add_member(ids[CARDIOLOGY], CAROL, "RW").status == 200
    assert admin.remove_member(ids[CARDIOLOGY], DAN).status == 200

    open_deck(carol, running, heart)
    assert visible(carol, "edit-mode-btn")
    dan = page_of(chromium, running, fake_google, DAN)
    dan.goto(f"{running.origin}/open/{heart.id}")
    assert "Access denied." in dan.locator("body").inner_text()
    lines = [" ".join(row) for row in admin.open("/admin").activity_lines()]
    assert any(f'Changed {CAROL} to RW in "{CARDIOLOGY}"' in line for line in lines), lines
    assert any(f'Removed {DAN} from "{CARDIOLOGY}"' in line for line in lines), lines


def test_e2e_021_a_direct_link_works_after_signing_in(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-021: Carol has no session, opens the link, signs in at Google and lands on the read only deck, never
    on the home page, and the page carries no ``Access denied.``"""
    running = library_server(fake_google)
    _ids, heart = library_with_deck(running)
    page = person_context(chromium, running, None).new_page()
    fake_google.choose(CAROL)

    page.goto(f"{running.origin}/open/{heart.id}")
    page.get_by_role("link", name="Sign in with Google").click()

    page.wait_for_url(f"{running.content_origin}/d/{heart.id}/")
    wait_for_js(
        deck_frame(page), "document.querySelectorAll('section.slide, article.slide').length", len(TITLES), what="deck"
    )
    assert "Access denied." not in page.content()
    assert not visible(page, "edit-mode-btn")
    assert visited_home_page(page) is False


def visited_home_page(page: Page) -> bool:
    """True when the page history holds the library home page (the person was sent through it)."""
    return page.evaluate("history.length") > 3 and page.url.endswith("/")


def test_e2e_180_the_library_controls_of_each_page(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-180: Sign out on home and folder pages, All folders on folder and administration pages, no library
    control on the presentation, Back returns to the folder page."""
    running = library_server(fake_google)
    ids, heart = library_with_deck(running)
    running.builder.presentation(ids[CARDIOLOGY], STATINS, size=1, modified=MODIFIED, slides=1)
    page = page_of(chromium, running, fake_google, ADMIN)
    names = {
        "sign-out": page.get_by_role("button", name="Sign out"),
        "all": page.get_by_role("link", name="All folders"),
    }

    page.goto(f"{running.origin}/")
    assert names["sign-out"].count() == 1
    assert names["all"].count() == 0
    page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")
    assert names["sign-out"].count() == 1
    assert names["all"].count() == 1
    page.goto(f"{running.origin}/admin")
    assert names["sign-out"].count() == 1
    assert names["all"].count() == 1
    page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")
    page.get_by_role("link", name=HEART_FAILURE).click()
    page.wait_for_url(f"{running.content_origin}/d/{heart.id}/")
    assert page.get_by_role("button", name="Sign out").count() == 0
    assert page.get_by_role("link", name="All folders").count() == 0

    page.go_back()
    wait_until(page, lambda: page.url, lambda url: url == f"{running.origin}/f/{ids[CARDIOLOGY]}", what="folder page")


def test_exploit_e2e_sec_013_a_presentations_script_cannot_read_what_the_browser_keeps_for_the_library(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-SEC-013. Red before the fix because: the script reads the identity data kept for the library; the
    assertion "the slide shows no email address" fails and shows carol.ro@example.org (the check was written
    against a library that kept the session in a cookie of the content origin)."""
    running = library_server(fake_google)
    _ids, heart = library_with_deck(running, PROBE_SCRIPT)
    seen: dict[str, str] = {}
    for email in (CAROL, ADMIN):
        page = page_of(chromium, running, fake_google, email)
        open_deck(page, running, heart)
        seen[email] = wait_until(
            page,
            lambda page=page: deck_frame(page).evaluate("document.getElementById('probe').textContent"),
            lambda text: text != "",
            what="probe",
        )
        slide_text = deck_frame(page).locator("body").inner_text()
        assert "carol.ro@example.org" not in slide_text
        assert "seb.morand@gmail.com" not in slide_text
        page.goto(f"{running.origin}/f/{_ids[CARDIOLOGY]}")
        assert "Access denied." not in page.locator("body").inner_text()
        assert page.get_by_role("button", name="Sign out").count() == 1
    assert seen == {CAROL: "stored:  | {} | {}", ADMIN: "stored:  | {} | {}"}
