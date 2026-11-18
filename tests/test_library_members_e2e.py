"""US-0132: the ``Members`` controls of the administration page in Chromium (SPEC-0025).

Spec tests: E2E-084, E2E-089, E2E-156. The administrator signs in over HTTP through ``FakeGoogle``; the session
cookie goes into a Chromium context where ``library.js`` sends ``Add member``, a member's role chooser and ``Remove``
with ``fetch``, reloads the page on success and writes a refusal with ``textContent`` into the folder's alert.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Locator, Page, Playwright

from tests import library_support
from tests.browser_wait import wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    PNEUMO,
    WCBIP,
    FakeGoogle,
    RunningLibrary,
    person_context,
    signed_in,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

READ_WRITE = "Read and write"
READ_ONLY = "Read only"
ALICE = "alice.ro@example.org"
INVALID_ADDRESS = "This is not a valid email address."
FOLDER_NAMES_SCRIPT = (
    "() => [...document.querySelectorAll('ul.folders a[href^=\"/f/\"]')].map(link => link.textContent)"
)
SELECTED_SCRIPT = "chooser => chooser.selectedOptions[0].textContent"


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = library_support.launch_chromium(playwright)
    yield browser
    browser.close()


def admin_home(running: RunningLibrary, google: FakeGoogle, chromium: Chromium) -> Page:
    """The administrator's home page in Chromium."""
    person = signed_in(running, google, ADMIN)
    page = person_context(chromium, running, person.cookies["lib"]).new_page()
    page.goto(f"{running.origin}/")
    return page


def open_administration(page: Page) -> None:
    with page.expect_navigation():
        page.get_by_role("link", name="Administration").click()


def members(page: Page, folder_id: str) -> Locator:
    """The ``Members`` section of one folder."""
    return page.locator(f"#members-{folder_id}")


def listed_members(page: Page, folder_id: str) -> list[tuple[str, str]]:
    """``(address, role shown by its chooser)`` of each member row, in page order."""
    rows = members(page, folder_id).locator("ul.members > li")
    return [
        (row.locator(".email").inner_text(), row.get_by_role("combobox").evaluate(SELECTED_SCRIPT))
        for row in rows.all()
    ]


def add_member(page: Page, folder_id: str, email: str, role: str) -> None:
    """Type ``email``, choose ``role`` in ``Role`` and press ``Add member``; the page reloads on success."""
    section = members(page, folder_id)
    section.get_by_label("Email address", exact=True).fill(email)
    section.get_by_label("Role", exact=True).select_option(label=role)
    with page.expect_navigation():
        section.get_by_role("button", name="Add member").click()


def listed_folders(page: Page) -> list[str]:
    names: list[str] = page.evaluate(FOLDER_NAMES_SCRIPT)
    return names


def test_e2e_084_the_administrator_opens_the_administration(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-084: from the home page, "Administration" shows the section "Folders" where every folder has its "Members"
    and a "Delete folder" button, the field "Folder name" with "Create folder", and the section "Activity"."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    page = admin_home(running, fake_google, chromium)

    open_administration(page)

    folders = page.locator("section#folders")
    assert folders.get_by_role("heading", name="Folders", exact=True).is_visible()
    for name in (CARDIOLOGY, PNEUMO, WCBIP):
        row = page.locator("ul.folders > li", has=page.locator(f'a[href="/f/{ids[name]}"]'))
        assert row.get_by_role("button", name="Delete folder").is_visible(), name
        assert members(page, ids[name]).get_by_role("heading", name="Members", exact=True).is_visible(), name
    assert folders.get_by_label("Folder name", exact=True).is_visible()
    assert folders.get_by_role("button", name="Create folder").is_visible()
    assert page.get_by_role("heading", name="Activity", exact=True).is_visible()


def test_e2e_089_only_rw_and_ro_can_be_given(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-089: the "Role" chooser of "Pneumo Été" offers "Read and write" and "Read only" and nothing else; Dan
    added as "Read and write" sees the folder labelled so on his home page, without "Administration"."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    page = admin_home(running, fake_google, chromium)
    open_administration(page)

    chooser = members(page, ids[PNEUMO]).get_by_label("Role", exact=True)
    assert chooser.locator("option").all_text_contents() == [READ_WRITE, READ_ONLY]
    assert chooser.locator("option").evaluate_all("options => options.map(option => option.value)") == ["RW", "RO"]
    add_member(page, ids[PNEUMO], DAN, READ_WRITE)

    assert listed_members(page, ids[PNEUMO]) == [(DAN, READ_WRITE)]
    dan = signed_in(running, fake_google, DAN)
    home = dan.open("/")
    assert [(name, role) for _, name, role in home.folder_rows()] == [(CARDIOLOGY, READ_WRITE), (PNEUMO, READ_WRITE)]
    assert "Administration" not in home.text


def test_e2e_156_the_controls_carry_their_exact_names(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-156: the folder page offers "All folders"; the administration names "Folders", "Activity", "Folder name",
    "Create folder", "Delete folder", "Members", "Email address", "Role" ("Read and write", "Read only"), "Add
    member", Carol's chooser showing "Read only" and "Remove"; "All folders" goes home; members are listed by address,
    folders as on the home page."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    page = admin_home(running, fake_google, chromium)
    home_order = listed_folders(page)

    with page.expect_navigation():
        page.get_by_role("link", name=CARDIOLOGY).click()
    with page.expect_navigation():
        page.get_by_role("link", name="All folders").click()
    assert page.url == f"{running.origin}/"
    open_administration(page)

    for heading in ("Folders", "Activity"):
        assert page.get_by_role("heading", name=heading, exact=True).is_visible()
    assert page.get_by_label("Folder name", exact=True).is_visible()
    assert page.get_by_role("button", name="Create folder").is_visible()
    section = members(page, ids[CARDIOLOGY])
    assert section.get_by_role("heading", name="Members", exact=True).is_visible()
    assert section.get_by_label("Email address", exact=True).is_visible()
    assert section.get_by_label("Role", exact=True).locator("option").all_text_contents() == [READ_WRITE, READ_ONLY]
    assert section.get_by_role("button", name="Add member").is_visible()
    carol = section.locator("ul.members > li", has_text=CAROL)
    assert carol.get_by_role("combobox").evaluate(SELECTED_SCRIPT) == READ_ONLY
    assert carol.get_by_role("button", name="Remove", exact=True).is_visible()
    row = page.locator("ul.folders > li", has=page.locator(f'a[href="/f/{ids[CARDIOLOGY]}"]'))
    assert row.get_by_role("button", name="Delete folder").is_visible()

    add_member(page, ids[CARDIOLOGY], "Alice.RO@example.org", READ_ONLY)

    assert listed_members(page, ids[CARDIOLOGY]) == [(ALICE, READ_ONLY), (CAROL, READ_ONLY), (DAN, READ_WRITE)]
    assert listed_folders(page) == home_order == [CARDIOLOGY, PNEUMO, WCBIP]
    with page.expect_navigation():
        page.get_by_role("link", name="All folders").click()
    assert page.url == f"{running.origin}/"


def test_a_role_chooser_changes_the_role_remove_removes_and_a_refusal_shows_in_the_alert(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """FR-NEW-047 in the page: Carol's chooser set to "Read and write" stores RW, "Remove" on Dan removes him, both
    lines are listed; "carol@" typed in "Pneumo Été" shows the address text in that folder's alert, nothing added."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    page = admin_home(running, fake_google, chromium)
    open_administration(page)
    section = members(page, ids[CARDIOLOGY])

    with page.expect_navigation():
        section.locator("ul.members > li", has_text=CAROL).get_by_role("combobox").select_option(label=READ_WRITE)
    assert listed_members(page, ids[CARDIOLOGY]) == [(CAROL, READ_WRITE), (DAN, READ_WRITE)]
    with page.expect_navigation():
        section.locator("ul.members > li", has_text=DAN).get_by_role("button", name="Remove").click()
    assert listed_members(page, ids[CARDIOLOGY]) == [(CAROL, READ_WRITE)]
    lines = page.locator("ol.activity .text").all_text_contents()
    assert lines == [f'Removed {DAN} from "{CARDIOLOGY}"', f'Changed {CAROL} to RW in "{CARDIOLOGY}"']

    pneumo = members(page, ids[PNEUMO])
    pneumo.get_by_label("Email address", exact=True).fill("carol@")
    pneumo.get_by_role("button", name="Add member").click()
    alert = pneumo.get_by_role("alert")
    wait_until(page, alert.text_content, lambda text: text == INVALID_ADDRESS, what="the address text in the alert")
    assert listed_members(page, ids[PNEUMO]) == []
    assert [row for row in running.stored.members() if row[0] == ids[PNEUMO]] == []
