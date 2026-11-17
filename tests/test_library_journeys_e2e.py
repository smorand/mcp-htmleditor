"""US-0149: the closing browser journeys of the web library mode (SPEC-0025).

Spec tests: E2E-085, E2E-128. The person's time zone is UTC in the browser context; the slide counts are read from the
stored files and from what the editor frame shows.
"""

from __future__ import annotations

import html
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright

from mcp_htmleditor.deck import deck_from_text
from tests import library_support
from tests.browser_wait import wait_for_js, wait_until
from tests.conftest import needs_chromium
from tests.deck_support import build_deck
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    DAN,
    LAMYA,
    PNEUMO,
    STATINS,
    WCBIP,
    FakeGoogle,
    RunningLibrary,
    deck_frame,
    launch_chromium,
    person_context,
    signed_in,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

SPIROMETRY = "Spirometry Basics"
CHALLENGES = "From Challenges to Change"
BRIDGING = "Bridging the Gap"
COVER = ".slide-cover-title"
NAMES = "() => [...document.querySelectorAll('ul.presentations li')].map(row => row.querySelector('.name').textContent)"
ROWS = (
    "() => [...document.querySelectorAll('ul.presentations li')].map(row =>"
    " [row.querySelector('.name').textContent, row.querySelector('time').textContent,"
    " row.querySelector('.size').textContent])"
)


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def page_of(chromium: Chromium, running: RunningLibrary, google: FakeGoogle, email: str) -> Page:
    person = signed_in(running, google, email)
    return person_context(chromium, running, person.cookies["lib"], zone="UTC").new_page()


def test_e2e_085_the_administrator_acts_in_a_folder_where_they_have_no_member_entry(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    page = page_of(chromium, running, fake_google, ADMIN)
    page.goto(f"{running.origin}/f/{ids[PNEUMO]}")

    page.set_input_files(
        "#upload-file",
        files=[
            {
                "name": f"{SPIROMETRY}.html",
                "mimeType": "text/html",
                "buffer": build_deck("ei", ("Cover", "Two")).encode(),
            }
        ],
    )
    wait_until(
        page, lambda: page.locator("#upload-status").inner_text(), lambda t: t == f"Uploaded {SPIROMETRY}.", what="m"
    )
    page.get_by_role("link", name=SPIROMETRY).click()
    page.wait_for_url(f"{running.content_origin}/d/**")
    wait_for_js(deck_frame(page), "document.querySelectorAll('.slide').length", 2, what="deck")
    page.click("#edit-mode-btn")
    wait_for_js(deck_frame(page), f"document.querySelector('{COVER}').isContentEditable", True, what="editable")
    deck_frame(page).locator(COVER).click()
    page.keyboard.press("End")
    page.keyboard.type(" edited")
    page.click("#toolbar-filename")
    stored = next(running.library_dir.joinpath("files", ids[PNEUMO]).glob("*.html"))
    wait_until(page, lambda: stored.read_text(encoding="utf-8"), lambda text: "edited" in text, what="the stored edit")
    page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")
    page.get_by_role("button", name="Delete").nth(2).click()
    wait_until(page, lambda: page.locator("#confirm-dialog").is_visible(), bool, what="the question")
    name = page.locator("#confirm-question").inner_text().split('"')[1]
    page.locator("#confirm-yes").click()

    wait_until(page, lambda: page.evaluate(NAMES), lambda names: name not in names, what="the deletion")
    dan = signed_in(running, fake_google, DAN)
    assert len(dan.open(f"/f/{ids[CARDIOLOGY]}").presentation_rows()) == 2
    assert name in {STATINS, "Heart Failure Update", "Arrhythmia Basics"}
    assert [row[2] for row in signed_in(running, fake_google, ADMIN).open("/admin").activity_lines()][:2] == [
        f'Deleted "{name}" from "{CARDIOLOGY}"',
        f'Uploaded "{SPIROMETRY}" in "{PNEUMO}"',
    ]


def test_e2e_128_the_initial_content_is_there(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    running = library_server(fake_google, seed=True)
    folder = running.stored.rows("SELECT id FROM folders")[0][0]

    for email, label in ((ADMIN, "Admin"), (LAMYA, "Read and write")):
        page = page_of(chromium, running, fake_google, email)
        page.goto(f"{running.origin}/")
        assert page.get_by_role("link", name=WCBIP).count() == 1
        assert label in page.locator("ul.folders li").first.inner_text()
        page.goto(f"{running.origin}/f/{folder}")
        wait_until(page, lambda page=page: page.evaluate(ROWS), lambda rows: len(rows) == 2, what="rows")
        assert page.evaluate(ROWS) == [
            [BRIDGING, "15 Nov 2026 19:57", "3.1 MB"],
            [CHALLENGES, "15 Nov 2026 19:57", "3.7 MB"],
        ]
    admin = signed_in(running, fake_google, ADMIN)
    assert "No activity yet." in admin.open("/admin").text
    counts = {}
    for name, count in ((CHALLENGES, 18), (BRIDGING, 15)):
        page.get_by_role("link", name=name).click()
        page.wait_for_url(f"{running.content_origin}/d/**")
        wait_for_js(deck_frame(page), "document.querySelectorAll('[data-type=\"slide\"]').length", count, what=name)
        page.go_back()
        counts[name] = count
    stored = {
        html.unescape(name): deck_from_text(
            "x.html", Path(running.library_dir / "files" / fid / f"{pid}.html").read_text(encoding="utf-8")
        )
        for pid, fid, name in running.stored.rows("SELECT id, folder_id, name FROM presentations")
    }
    assert {name: len(deck.slides) for name, deck in stored.items()} == counts
