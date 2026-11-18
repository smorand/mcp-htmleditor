"""US-0129: the folder page in Chromium (SPEC-0025).

Spec tests: E2E-006, E2E-017, E2E-020, E2E-029, E2E-164, E2E-SEC-024. People sign in over HTTP through ``FakeGoogle``;
their session cookie is put in a Chromium context with a fixed time zone (``person_context``), Chromium resolving
``slides.test`` to loopback (``launch_chromium``). Dates are written by ``library.js`` in the browser's zone.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Frame, Page, Playwright

from tests import library_support
from tests.browser_wait import wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    ARRHYTHMIA,
    CARDIOLOGY,
    CAROL,
    DAN,
    EVIL_HOST,
    HEART_FAILURE,
    PNEUMO,
    STATINS,
    WCBIP,
    Browser,
    FakeGoogle,
    RecordingListener,
    RunningLibrary,
    launch_chromium,
    person_context,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
evil_listener = library_support.evil_listener
START = Callable[..., RunningLibrary]

READY_SECONDS = 2.0  # FR-NEW-060
LINK_BYTES_PER_SECOND = 50_000_000 // 8  # the 50 megabit per second connection
MELBOURNE = "Australia/Melbourne"
SIGN_IN = "Sign in with Google"
EMPTY_FOLDER = "This folder has no presentations yet."
ROWS_SCRIPT = (
    "() => [...document.querySelectorAll('ul.presentations li')].map(row =>"
    " [row.querySelector('.name').textContent, row.querySelector('time').textContent,"
    " row.querySelector('.size').textContent])"
)
CONTROLS_SCRIPT = (
    "() => [...document.querySelectorAll('a, button, input, select, textarea, [onclick], [tabindex]')].map(element =>"
    " ({tag: element.tagName, href: element.getAttribute('href'),"
    " name: element.innerText.trim() || element.getAttribute('aria-label') || '',"
    " handler: element.hasAttribute('onclick'), tabindex: element.getAttribute('tabindex')}))"
)
FOCUSED_SCRIPT = "document.activeElement.getAttribute('href') || document.activeElement.innerText"
UTC_ROWS = [
    [ARRHYTHMIA, "12 Nov 2026 16:40", "512.0 KB"],
    [STATINS, "12 Nov 2026 16:40", "1.5 MB"],
    [HEART_FAILURE, "10 Nov 2026 09:15", "2.0 MB"],
]
LIBRARY_TEXTS = (CARDIOLOGY, HEART_FAILURE, ARRHYTHMIA, STATINS, SIGN_IN, "Sign out", "Access denied.", "Slides")


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright, EVIL_HOST)
    yield browser
    browser.close()


def signed_in(running: RunningLibrary, google: FakeGoogle, email: str) -> Browser:
    browser = running.browser()
    browser.sign_in(google, email)
    return browser


def standard_library(running: RunningLibrary) -> dict[str, str]:
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    return ids


def open_page(chromium: Chromium, running: RunningLibrary, person: Browser, *, zone: str = "UTC") -> Page:
    return person_context(chromium, running, person.cookies["lib"], zone=zone).new_page()


def shown_rows(page: Page) -> list[list[str]]:
    """``[name, date text, size]`` of each row, as displayed."""
    rows: list[list[str]] = page.evaluate(ROWS_SCRIPT)
    return rows


def assert_controls_are_named_links_and_buttons(page: Page) -> list[str]:
    """FR-NEW-064, DEC-053: only ``a`` and ``button``, each with a visible name, no handler on another element;
    returns each control's address (or its name) in page order."""
    controls = page.evaluate(CONTROLS_SCRIPT)
    assert {control["tag"] for control in controls} <= {"A", "BUTTON", "INPUT"}  # INPUT: the Upload field (US-0141)
    assert all(control["name"] and not control["handler"] and control["tabindex"] is None for control in controls)
    return [control["href"] or control["name"] for control in controls]


def tab_until(page: Page, target: str, order: list[str]) -> list[str]:
    """Press Tab until ``target`` (an address or a name) has the focus; returns what was focused, in order."""
    focused: list[str] = []
    while not focused or (focused[-1] != target and len(focused) < len(order)):
        page.keyboard.press("Tab")
        focused.append(page.evaluate(FOCUSED_SCRIPT))
    return focused


def frame_text(frame: Frame) -> str:
    """Everything a frame displays, links and buttons included, or an empty string for a frame with no body."""
    text: str = frame.evaluate("document.body ? document.body.innerText : ''")
    return text


# ---------------------------------------------------------------------------
# E2E-020, E2E-029, E2E-164: rows, dates and sizes
# ---------------------------------------------------------------------------


def test_e2e_020_a_folder_lists_its_presentations_newest_first(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-020: Dan opens Cardiology from the home page: three rows, the two of 16:40 in name order; ``All folders``
    is reached with Tab and opens the home page with Enter."""
    running = library_server(fake_google)
    ids = standard_library(running)
    page = open_page(chromium, running, signed_in(running, fake_google, DAN))
    page.goto(f"{running.origin}/")

    page.get_by_role("link", name=CARDIOLOGY).click()
    page.wait_for_url(f"{running.origin}/f/{ids[CARDIOLOGY]}")

    assert page.locator("h1").inner_text() == CARDIOLOGY
    assert shown_rows(page) == UTC_ROWS
    order = assert_controls_are_named_links_and_buttons(page)
    assert order.count("Upload") == 1  # Dan is RW: the Upload field is the one control that is not a link (US-0141)
    for control in ("Upload", "Replace", "Cancel"):  # Replace and Cancel: the closed question (US-0144)
        order.remove(control)
    assert order.count("Delete") == len(UTC_ROWS)  # one Delete button on each row of a writer (US-0145)
    order = [control for control in order if control != "Delete"]
    assert order[:2] == ["Switch theme", "Sign out"]  # the bar of the page comes first (design system)
    assert order[2] == "/"  # then "All folders"; the presentation names after it are links (US-0134)
    assert [link.rsplit("/", 1)[0] for link in order[3:]] == ["/open"] * len(UTC_ROWS)
    assert page.get_by_role("link", name="All folders").count() == 1
    assert tab_until(page, "/", order) == ["", "Sign out", "/"]  # the bar first: the theme button (no text), Sign out
    page.keyboard.press("Enter")
    page.wait_for_url(f"{running.origin}/")
    assert page.get_by_role("link", name=CARDIOLOGY).count() == 1


def test_e2e_029_dates_follow_the_persons_time_zone(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-029: the same instant reads 12 Nov 2026 16:40 for Dan in UTC and 13 Nov 2026 03:40 for Carol in
    Melbourne (UTC plus 11 in November); the order is the same for both."""
    running = library_server(fake_google)
    ids = standard_library(running)
    address = f"{running.origin}/f/{ids[CARDIOLOGY]}"
    dan = open_page(chromium, running, signed_in(running, fake_google, DAN))
    carol = open_page(chromium, running, signed_in(running, fake_google, CAROL), zone=MELBOURNE)

    dan.goto(address)
    carol.goto(address)

    assert shown_rows(dan) == UTC_ROWS
    assert shown_rows(carol) == [
        [ARRHYTHMIA, "13 Nov 2026 03:40", "512.0 KB"],
        [STATINS, "13 Nov 2026 03:40", "1.5 MB"],
        [HEART_FAILURE, "10 Nov 2026 20:15", "2.0 MB"],
    ]


def test_e2e_164_rounding_of_sizes_and_display_of_times(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-164: sizes rounded half up from the exact value; times on a 24 hour clock, no leading zero on the day,
    seconds dropped (09:05:59 reads 09:05, 23:59:59 reads 23:59)."""
    running = library_server(fake_google)
    folder = running.builder.folder(CARDIOLOGY)
    running.builder.member(folder, DAN, "RW")
    for name, size, modified in (
        ("Five", 1_075, datetime(2026, 11, 5, 9, 5, 59, tzinfo=UTC)),
        ("Twelve", 1_076, datetime(2026, 11, 12, 23, 59, 59, tzinfo=UTC)),
        ("December", 1_048_575, datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)),
        ("September", 1_572_864, datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)),
    ):
        running.builder.presentation(folder, name, size=size, modified=modified)
    page = open_page(chromium, running, signed_in(running, fake_google, DAN))

    page.goto(f"{running.origin}/f/{folder}")

    assert shown_rows(page) == [
        ["December", "1 Dec 2026 00:00", "1024.0 KB"],
        ["Twelve", "12 Nov 2026 23:59", "1.1 KB"],
        ["Five", "5 Nov 2026 09:05", "1.0 KB"],
        ["September", "30 Sep 2026 12:00", "1.5 MB"],
    ]


# ---------------------------------------------------------------------------
# E2E-017: 200 folders
# ---------------------------------------------------------------------------


def test_e2e_017_a_library_of_200_folders_stays_usable(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-017: on a 50 megabit per second link the administrator's home lists Folder 001 to Folder 200 within 2
    seconds, each link announced by its name; Tab walks the page in order to Folder 200 and Enter opens it."""
    running = library_server(fake_google)
    ids = running.builder.numbered_folders(200)
    target = f"/f/{ids['Folder 200']}"
    page = open_page(chromium, running, signed_in(running, fake_google, ADMIN))
    network = page.context.new_cdp_session(page)
    network.send("Network.enable")
    network.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "latency": 0,
            "downloadThroughput": LINK_BYTES_PER_SECOND,
            "uploadThroughput": LINK_BYTES_PER_SECOND,
        },
    )

    started = time.monotonic()
    page.goto(f"{running.origin}/")
    names = page.locator("ul.folders a").all_inner_texts()
    elapsed = time.monotonic() - started

    assert elapsed < READY_SECONDS, elapsed
    assert names == [f"Folder {number:03d}" for number in range(1, 201)]
    announced = re.findall(r'- link "([^"]*)"', page.locator("ul.folders").aria_snapshot())
    assert announced == names
    order = assert_controls_are_named_links_and_buttons(page)
    assert len(order) == 203  # Administration, the theme button, Sign out and the 200 folders
    focused = tab_until(page, target, order)
    # the theme button has no text, only its accessible name: the focus probe reads its text
    assert focused == ["" if name == "Switch theme" else name for name in order[: order.index(target) + 1]]
    page.keyboard.press("Enter")
    page.wait_for_url(f"{running.origin}{target}")
    assert page.locator("h1").inner_text() == "Folder 200"
    assert page.get_by_text(EMPTY_FOLDER).count() == 1


# ---------------------------------------------------------------------------
# E2E-006: Back after sign out
# ---------------------------------------------------------------------------


def test_e2e_006_the_back_button_after_signing_out_shows_no_library_content(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-006: after Sign out, Back shows the sign in page and no name; Dan's other browser is still signed in."""
    running = library_server(fake_google)
    ids = standard_library(running)
    address = f"{running.origin}/f/{ids[CARDIOLOGY]}"
    page = open_page(chromium, running, signed_in(running, fake_google, DAN))
    other = open_page(chromium, running, signed_in(running, fake_google, DAN))
    page.goto(address)
    assert shown_rows(page) == UTC_ROWS

    page.get_by_role("button", name="Sign out").click()
    page.wait_for_url(f"{running.origin}/")
    page.go_back()

    text = wait_until(
        page,
        lambda: page.locator("body").inner_text(),
        lambda body: SIGN_IN in body,
        what="the sign in page after Back",
    )
    for name in (CARDIOLOGY, HEART_FAILURE, ARRHYTHMIA, STATINS):
        assert name not in text
    other.goto(address)
    assert shown_rows(other) == UTC_ROWS


# ---------------------------------------------------------------------------
# E2E-SEC-024: a page of another site frames the library
# ---------------------------------------------------------------------------


def test_exploit_e2e_sec_024_a_page_of_another_site_shows_a_library_page_inside_a_frame(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium, evil_listener: RecordingListener
) -> None:
    """E2E-SEC-024 (Class G #5). Red before the fix because: the library pages are displayed in the frames; the
    assertion "the frame shows no library text" fails and shows the library's own ``Sign in with Google`` link (the
    session cookie is ``SameSite=Lax``, so a cross site frame is a visitor's view) under the other site's button.

    Both frames stay empty; the click on the other site's button does nothing in the library; Carol's own tab and
    the administrator's view list Cardiology's presentations; no session changed.
    """
    running = library_server(fake_google)
    ids = standard_library(running)
    address = f"{running.origin}/f/{ids[CARDIOLOGY]}"
    carol = person_context(chromium, running, signed_in(running, fake_google, CAROL).cookies["lib"])
    admin = open_page(chromium, running, signed_in(running, fake_google, ADMIN))
    sessions = running.stored.sessions()
    evil_listener.page = (
        "<!DOCTYPE html><html><body>"
        f'<iframe id="folder" src="{address}" width="800" height="300"></iframe>'
        f'<iframe id="signin" src="{running.origin}/" width="800" height="300"></iframe>'
        '<button id="prize" style="position:absolute;top:60px;left:60px">Win a prize</button>'
        "</body></html>"
    )
    page = carol.new_page()

    page.goto(f"http://{EVIL_HOST}:{evil_listener.port}/frame")
    page.click("#prize")

    frames = [frame for frame in page.frames if frame is not page.main_frame]
    assert len(frames) == 2
    assert f"{EVIL_HOST}:{evil_listener.port}/frame" in evil_listener.visits
    for frame in frames:
        text = frame_text(frame)
        assert not any(library_text in text for library_text in LIBRARY_TEXTS), text
        assert frame.evaluate("document.querySelectorAll('a, button, form').length") == 0
    own_tab = carol.new_page()
    own_tab.goto(address)
    assert own_tab.locator("h1").inner_text() == CARDIOLOGY
    admin.goto(address)
    assert shown_rows(admin) == UTC_ROWS
    assert running.stored.sessions() == sessions
    assert running.stored.activity() == []
    assert running.stored.folder_names() == sorted([CARDIOLOGY, PNEUMO, WCBIP])
