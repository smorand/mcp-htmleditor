"""US-0141: the Upload control of the folder page in Chromium (SPEC-0025).

Spec tests: E2E-054, E2E-063, E2E-126. Dan's session cookie goes into a Chromium context; ``library.js`` sends the
chosen file with ``XMLHttpRequest`` and writes the answer with ``textContent`` into the status area. The second channel
is the folder as the administrator lists it, the activity table and what Carol is served.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright

from tests import library_support
from tests.browser_wait import settle, wait_until
from tests.conftest import needs_chromium
from tests.deck_support import build_deck
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    FakeGoogle,
    RunningLibrary,
    launch_chromium,
    person_context,
    signed_in,
    valid_deck,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google

QUARTERLY = "Quarterly Review"
QUARTERLY_BYTES = 1_258_291
NAMES_SCRIPT = (
    "() => [...document.querySelectorAll('ul.presentations li')].map(row => row.querySelector('.name').textContent)"
)


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def folder_page(running: RunningLibrary, google: FakeGoogle, chromium: Chromium, email: str) -> tuple[Page, str]:
    """The folder page of Cardiology for ``email``, in Chromium; returns the page and the folder id."""
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    person = signed_in(running, google, email)
    page = person_context(chromium, running, person.cookies["lib"]).new_page()
    page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")
    return page, ids[CARDIOLOGY]


def choose(page: Page, name: str, data: bytes) -> None:
    page.set_input_files("#upload-file", files=[{"name": name, "mimeType": "text/html", "buffer": data}])


def status(page: Page) -> str:
    return page.locator("#upload-status").inner_text()


def activity(running: RunningLibrary, google: FakeGoogle) -> list[str]:
    return [row[2] for row in signed_in(running, google, ADMIN).open("/admin").activity_lines()]


def test_e2e_054_a_valid_presentation_is_uploaded(
    library_server,
    fake_google: FakeGoogle,
    chromium: Chromium,
) -> None:
    """E2E-054: "Quarterly Review.HTML" of 3 slides, 1 258 291 bytes: the message, the row first with the current time
    and "1.2 MB", Carol sees 3 slides, one activity line by Dan, one presentation, no failure text."""
    running = library_server(fake_google)
    page, folder_id = folder_page(running, fake_google, chromium, DAN)
    assert page.get_by_label("Upload").count() == 1

    choose(page, f"{QUARTERLY}.HTML", valid_deck(3, QUARTERLY_BYTES))

    wait_until(page, lambda: status(page), lambda text: text == f"Uploaded {QUARTERLY}.", what="the message")
    wait_until(page, lambda: page.evaluate(NAMES_SCRIPT), lambda names: names[:1] == [QUARTERLY], what="listed first")
    first = page.locator("ul.presentations li").first
    assert re.fullmatch(r"\d{1,2} [A-Z][a-z]{2} 20\d\d \d\d:\d\d", first.locator("time").inner_text())
    assert first.locator(".size").inner_text() == "1.2 MB"
    assert page.evaluate(NAMES_SCRIPT).count(QUARTERLY) == 1
    assert "The upload failed" not in page.locator("body").inner_text()
    admin = signed_in(running, fake_google, ADMIN)
    link = admin.open(f"/f/{folder_id}").presentation_rows()
    assert [row[0] for row in link].count(QUARTERLY) == 1
    carol = signed_in(running, fake_google, CAROL)
    presentation_id = re.search(r'href="/open/([0-9a-f]{32})">Quarterly Review<', admin.open(f"/f/{folder_id}").text)
    assert presentation_id is not None
    carol.open_presentation(presentation_id[1])
    served = BeautifulSoup(carol.deck(presentation_id[1], "content", x_editor="1").text, "html.parser")
    assert len(served.select("article[data-type='slide']")) == 3
    assert activity(running, fake_google) == [f'Uploaded "{QUARTERLY}" in "{CARDIOLOGY}"']
    assert [row[1] for row in admin.open("/admin").activity_lines()] == [DAN]


def test_e2e_063_warnings_do_not_block_an_upload(
    library_server,
    fake_google: FakeGoogle,
    chromium: Chromium,
) -> None:
    """E2E-063: a picture from another site is a warning only."""
    running = library_server(fake_google)
    page, folder_id = folder_page(running, fake_google, chromium, DAN)
    deck = build_deck("ei", ("One", "Two")).replace("</body>", '<img src="https://example.org/p.png"></body>', 1)

    choose(page, "Web Pictures.html", deck.encode())

    wait_until(page, lambda: status(page), lambda text: text == "Uploaded Web Pictures.", what="the message")
    admin = signed_in(running, fake_google, ADMIN)
    assert "Web Pictures" in [row[0] for row in admin.open(f"/f/{folder_id}").presentation_rows()]


def test_e2e_126_markup_inside_a_check_message_is_shown_as_written(
    library_server,
    fake_google: FakeGoogle,
    chromium: Chromium,
) -> None:
    """E2E-126: the characters <b>x</b> are visible, not bold; no dialog opens."""
    running = library_server(fake_google)
    page, _folder_id = folder_page(running, fake_google, chromium, DAN)
    dialogs: list[str] = []
    page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    deck = build_deck("ei", ("One", "Two"))
    deck = deck.replace('data-id="slide-0"', 'data-id="<b>x</b>"', 1).replace(
        'data-id="slide-1"', 'data-id="<b>x</b>"', 1
    )
    deck = deck.replace('data-id="&lt;b&gt;x&lt;/b&gt;"', 'data-id="x"')

    choose(page, "Markup Deck.html", deck.encode())

    expected = 'This file is not a valid presentation: expected id "slide-0" but found "<b>x</b>".'
    wait_until(page, lambda: status(page), lambda text: text == expected, what="the message")
    assert page.locator("#upload-status b").count() == 0
    settle(page)
    assert dialogs == []
