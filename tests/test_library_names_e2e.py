"""US-0142: a name carrying a script tag in Chromium (SPEC-0025, DEC-029).

Spec test: E2E-SEC-004. The second channel is the dialogs Chromium would open and the text of the folder page and the
activity list, read by the administrator and by Carol.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright

from tests import library_support
from tests.browser_wait import settle, wait_until
from tests.conftest import needs_chromium
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
START = Callable[..., RunningLibrary]

HOSTILE = "<script>alert(1)</script>"


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def page_of(chromium: Chromium, running: RunningLibrary, google: FakeGoogle, email: str, dialogs: list[str]) -> Page:
    person = signed_in(running, google, email)
    page = person_context(chromium, running, person.cookies["lib"]).new_page()
    page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    return page


def test_e2e_sec_004_a_name_carrying_a_script_tag_is_refused(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-SEC-004. Red before the fix because: the name is stored and shown without escaping; "no dialog appears on
    the administrator's folder page" fails."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    dialogs: list[str] = []
    dan = page_of(chromium, running, fake_google, DAN, dialogs)
    dan.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")

    dan.set_input_files(
        "#upload-file", files=[{"name": f"{HOSTILE}.html", "mimeType": "text/html", "buffer": valid_deck()}]
    )

    wait_until(
        dan,
        lambda: dan.locator("#upload-status").inner_text(),
        lambda t: t == "This file name is not allowed.",
        what="refusal",
    )
    for email in (ADMIN, CAROL):
        page = page_of(chromium, running, fake_google, email, dialogs)
        page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")
        wait_until(
            page, lambda page=page: page.locator("h1").inner_text(), lambda t: t == CARDIOLOGY, what="folder page"
        )
        settle(page)
        assert "alert(1)" not in page.locator("body").inner_text()
    admin = page_of(chromium, running, fake_google, ADMIN, dialogs)
    admin.goto(f"{running.origin}/admin")
    settle(admin)
    assert "alert(1)" not in admin.locator("body").inner_text()
    assert dialogs == []
    assert running.stored.activity() == []
