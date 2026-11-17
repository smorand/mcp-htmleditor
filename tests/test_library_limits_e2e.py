"""US-0143: the progress, the interruption and the double click of the Upload control in Chromium (SPEC-0025).

Spec tests: E2E-071, E2E-072, E2E-075, E2E-158. The 10 megabit per second link of E2E-071 is the network emulation of
Chromium (``Network.emulateNetworkConditions``); a lost connection is the same emulation turned offline at 40 percent.
The second channel is the folder as the administrator lists it, the library storage and the activity table.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import CDPSession, Page, Playwright

from tests import library_support
from tests.browser_wait import settle, wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
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

BIG = 26_214_400
TEN_MEGABIT = 1_250_000  # bytes per second
PROGRESS = re.compile(r"Big Deck\.html (\d{1,2})%")


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def folder_page(running: RunningLibrary, google: FakeGoogle, chromium: Chromium) -> tuple[Page, str]:
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    person = signed_in(running, google, DAN)
    page = person_context(chromium, running, person.cookies["lib"]).new_page()
    page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")
    return page, ids[CARDIOLOGY]


def link(page: Page, bytes_per_second: float | None, *, offline: bool = False) -> CDPSession:
    """Limit (or cut) the upload throughput of the page, as a link of that speed would."""
    session = page.context.new_cdp_session(page)
    session.send("Network.enable")
    session.send(
        "Network.emulateNetworkConditions",
        {
            "offline": offline,
            "latency": 0,
            "downloadThroughput": -1,
            "uploadThroughput": -1 if bytes_per_second is None else bytes_per_second,
        },
    )
    return session


def choose(page: Page, name: str, data: bytes) -> None:
    page.set_input_files("#upload-file", files=[{"name": name, "mimeType": "text/html", "buffer": data}])


def status(page: Page) -> str:
    return page.locator("#upload-status").inner_text()


def names(running: RunningLibrary, google: FakeGoogle, folder_id: str) -> list[str]:
    return [row[0] for row in signed_in(running, google, ADMIN).open(f"/f/{folder_id}").presentation_rows()]


def test_e2e_158_the_progress_percent_is_a_whole_number_rounded_down(
    library_server,
    fake_google: FakeGoogle,
    chromium: Chromium,
) -> None:
    """E2E-158: the pure function gives 33 and 99 for the two byte counts and never 100."""
    running = library_server(fake_google)
    page, _folder = folder_page(running, fake_google, chromium)

    texts = page.evaluate(
        """() => [progressText('Big Deck.html', 8880000, 26214400), progressText('Big Deck.html', 26214000, 26214400),
                  progressText('Big Deck.html', 26214400, 26214400), progressText('Big Deck.html', 0, 26214400)]"""
    )

    assert texts == ["Big Deck.html 33%", "Big Deck.html 99%", "Big Deck.html 99%", "Big Deck.html 0%"]


def test_e2e_071_a_25_mb_upload_shows_progress_and_completes(
    library_server,
    fake_google: FakeGoogle,
    chromium: Chromium,
) -> None:
    """E2E-071: on a 10 megabit per second link the percentage only grows, never reads 100 before the end and
    "Uploaded Big Deck." appears within 2 minutes."""
    running = library_server(fake_google)
    page, folder_id = folder_page(running, fake_google, chromium)
    link(page, TEN_MEGABIT)
    seen: list[int] = []

    choose(page, "Big Deck.html", valid_deck(3, BIG))
    wait_until(
        page,
        lambda: (seen.append(int(m[1])) if (m := PROGRESS.fullmatch(status(page))) else None) or status(page),
        lambda text: text == "Uploaded Big Deck.",
        what="the end of the upload",
        bound=100.0,
    )

    assert seen, "no progress text was ever shown"
    assert seen == sorted(seen)
    assert max(seen) <= 99
    assert "Big Deck" in names(running, fake_google, folder_id)


def test_e2e_072_an_interrupted_upload_leaves_no_partial_presentation(
    library_server,
    fake_google: FakeGoogle,
    chromium: Chromium,
) -> None:
    """E2E-072: the page is refreshed at 40 percent (one of the interruptions of FR-NEW-036; the cut of the connection
    itself is ``test_a_connection_cut_in_the_body_leaves_nothing``): no "Uploaded", no row, nothing in the storage."""
    running = library_server(fake_google)
    page, folder_id = folder_page(running, fake_google, chromium)
    link(page, TEN_MEGABIT)
    storage = running.stored.entries()
    lines = len(running.stored.activity())

    choose(page, "Big Deck.html", valid_deck(3, 8_000_000))
    reached = wait_until(
        page,
        lambda: int(m[1]) if (m := PROGRESS.fullmatch(status(page))) else -1,
        lambda percent: percent >= 40,
        what="40 percent",
    )
    assert 40 <= reached <= 99
    shown = status(page)
    page.reload()
    wait_until(page, lambda: page.locator("h1").inner_text(), lambda text: text == CARDIOLOGY, what="the page")
    settle(page)

    assert "Uploaded" not in shown
    assert "Uploaded" not in page.locator("body").inner_text()
    assert "Big Deck" not in names(running, fake_google, folder_id)
    assert "Big Deck" not in page.locator("ul.presentations").inner_text()
    assert running.stored.entries() == storage
    assert len(running.stored.activity()) == lines


def test_e2e_075_a_double_click_uploads_once(
    library_server,
    fake_google: FakeGoogle,
    chromium: Chromium,
) -> None:
    """E2E-075: a second choice made while the first upload is in progress is ignored: one row, one line."""
    running = library_server(fake_google)
    page, folder_id = folder_page(running, fake_google, chromium)
    link(page, 400_000)
    data = valid_deck(3, 1_000_000)

    choose(page, "Quarterly Review.html", data)
    choose(page, "Quarterly Review.html", data)

    wait_until(
        page, lambda: status(page), lambda text: text == "Uploaded Quarterly Review.", what="the message", bound=30.0
    )
    settle(page)
    assert names(running, fake_google, folder_id).count("Quarterly Review") == 1
    assert [row[2] for row in signed_in(running, fake_google, ADMIN).open("/admin").activity_lines()] == [
        'Uploaded "Quarterly Review" in "Cardiology 2027"'
    ]
    assert page.locator("ul.presentations li .name").all_inner_texts().count("Quarterly Review") == 1


def test_the_page_refuses_a_wrong_extension_and_a_file_over_25_mb_before_sending(
    library_server,
    fake_google: FakeGoogle,
    chromium: Chromium,
) -> None:
    running = library_server(fake_google)
    page, folder_id = folder_page(running, fake_google, chromium)
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url) if request.method == "POST" else None)

    choose(page, "Quarterly Review.pdf", valid_deck())
    wait_until(page, lambda: status(page), lambda text: text == "Only .html files are accepted.", what="extension")
    choose(page, "Huge.html", valid_deck(3, BIG + 1))
    wait_until(page, lambda: status(page), lambda text: text == "The file is larger than 25 MB.", what="size")

    assert requests == []
    assert "Huge" not in names(running, fake_google, folder_id)
