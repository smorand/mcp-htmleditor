"""The design system on the library pages in Chromium (SPEC-0025, app-design): theme, gallery, covers, page policy.

The page policy (``style-src 'self'``, ``img-src 'self' data:``, no font) is the real constraint: a violation is a
console message, so every page is loaded while the console is listened to.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright

from tests import library_support
from tests.browser_wait import wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    DAN,
    FakeGoogle,
    RunningLibrary,
    launch_chromium,
    signed_in,
)
from tests.test_library_design_http import deck_with, picture

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
THEME = "document.documentElement.getAttribute('data-theme')"
BACKGROUND = "getComputedStyle(document.body).backgroundColor"


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def page_for(
    chromium: Chromium, running: RunningLibrary, google: FakeGoogle, email: str, scheme: str = "light"
) -> Page:
    person = signed_in(running, google, email)
    context = chromium.new_context(color_scheme=scheme)  # type: ignore[arg-type]
    context.add_cookies([{"name": "lib", "value": person.cookies["lib"], "url": running.origin}])
    return context.new_page()


def library(running: RunningLibrary, with_cover: bool) -> tuple[dict[str, str], str]:
    ids = running.builder.standard()
    deck = running.builder.presentation(ids[CARDIOLOGY], "Deck", size=1, modified=MODIFIED, slides=1)
    _raw, uri = picture(4_000)
    deck.path.write_bytes(deck_with(uri) if with_cover else deck_with())
    return ids, deck.id


def test_every_page_loads_without_a_policy_violation_or_a_missing_file(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    running = library_server(fake_google)
    ids, _deck = library(running, with_cover=True)
    page = page_for(chromium, running, fake_google, ADMIN)
    problems: list[str] = []
    page.on("console", lambda message: problems.append(message.text) if message.type in {"error", "warning"} else None)
    failed: list[str] = []
    page.on("requestfailed", lambda request: failed.append(request.url))

    for address in ("/", f"/f/{ids[CARDIOLOGY]}", "/admin"):
        page.goto(f"{running.origin}{address}")
        page.wait_for_load_state("networkidle")

    assert problems == []
    assert failed == []


def test_the_theme_follows_the_system_then_the_choice_is_kept(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    running = library_server(fake_google)
    library(running, with_cover=False)
    dark = page_for(chromium, running, fake_google, ADMIN, "dark")
    dark.goto(f"{running.origin}/")
    light = page_for(chromium, running, fake_google, ADMIN, "light")
    light.goto(f"{running.origin}/")

    assert dark.evaluate(THEME) == "dark"
    assert light.evaluate(THEME) == "light"
    assert dark.evaluate(BACKGROUND) != light.evaluate(BACKGROUND)
    light.get_by_role("button", name="Switch theme").click()
    wait_until(light, lambda: light.evaluate(THEME), lambda theme: theme == "dark", what="the theme toggled")
    assert light.evaluate("localStorage.getItem('library-theme')") == "dark"
    light.reload()
    assert light.evaluate(THEME) == "dark"  # set by theme.js before the first paint, over the system's light
    light.get_by_role("button", name="Switch theme").click()
    assert light.evaluate(THEME) == "light"
    light.reload()
    assert light.evaluate(THEME) == "light"


def test_a_stored_value_that_is_neither_light_nor_dark_is_ignored(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    running = library_server(fake_google)
    library(running, with_cover=False)
    page = page_for(chromium, running, fake_google, ADMIN, "dark")
    page.goto(f"{running.origin}/")
    page.evaluate("localStorage.setItem('library-theme', 'green')")

    page.reload()

    assert page.evaluate(THEME) == "dark"  # the system's: no third theme exists


def test_the_gallery_shows_the_cover_and_the_ridge_when_there_is_none(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    running = library_server(fake_google)
    ids, deck = library(running, with_cover=True)
    plain = running.builder.presentation(ids[CARDIOLOGY], "Plain", size=1, modified=MODIFIED, slides=1)
    plain.path.write_bytes(deck_with())
    page = page_for(chromium, running, fake_google, DAN)

    page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")
    page.wait_for_load_state("networkidle")

    with_cover = page.locator("li.pres-card", has=page.get_by_role("link", name="Deck", exact=True))
    without = page.locator("li.pres-card", has=page.get_by_role("link", name="Plain", exact=True))
    wait_until(page, lambda: without.locator(".cover img").is_hidden(), bool, what="the missing cover hidden")
    assert with_cover.locator(".cover img").is_visible()
    assert with_cover.locator(".cover img").evaluate("image => image.naturalWidth > 0")
    assert without.locator(".cover svg.ridge").is_visible()  # what shows instead
    assert page.locator(f'a[href="/open/{deck}"]').count() == 1


def test_a_folder_card_is_one_link_with_its_role_and_count(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    running = library_server(fake_google)
    ids, _deck = library(running, with_cover=False)
    page = page_for(chromium, running, fake_google, DAN)

    page.goto(f"{running.origin}/")

    card = page.locator("li.folder-card", has=page.get_by_role("link", name=CARDIOLOGY))
    assert re.search(r"Read and write\s+1 presentation", card.inner_text())
    assert card.get_by_role("link").count() == 1  # the whole card is the link (a stretched one)
    box = card.bounding_box()
    link_box = card.get_by_role("link").evaluate(
        "link => { const r = getComputedStyle(link, '::after'); return r.position; }"
    )
    assert box is not None and link_box == "absolute"
    with page.expect_navigation():
        card.click(position={"x": box["width"] - 12, "y": box["height"] / 2})
    assert page.url == f"{running.origin}/f/{ids[CARDIOLOGY]}"


def test_a_dialog_stays_until_the_request_ends_so_a_second_click_opens_nothing(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """The deletion question: the first click on Delete disables the button and keeps the dialog; a second click on
    the same spot never reaches the card under it."""
    running = library_server(fake_google)
    ids, _deck = library(running, with_cover=False)
    page = page_for(chromium, running, fake_google, DAN)
    page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")

    page.get_by_role("button", name="Delete", exact=True).first.click()
    wait_until(page, lambda: page.locator("#confirm-dialog").is_visible(), bool, what="the question")
    page.locator("#confirm-yes").click(click_count=3)

    wait_until(page, lambda: page.locator("ul.presentations").count() == 0, bool, what="the deck is gone")
    assert page.url == f"{running.origin}/f/{ids[CARDIOLOGY]}"
