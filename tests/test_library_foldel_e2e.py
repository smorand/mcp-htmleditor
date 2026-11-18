"""US-0131: the folder deletion prompt in Chromium (SPEC-0025).

Spec tests: E2E-157. The administrator signs in over HTTP through ``FakeGoogle``; the session cookie goes into a
Chromium context where ``library.js`` opens the ``<dialog>`` of ``Delete folder``, closes it on ``Cancel`` without a
request, and sends the retyped name with ``fetch``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright, Request

from tests import library_support
from tests.browser_wait import wait_until
from tests.conftest import needs_chromium
from tests.library_support import ADMIN, CARDIOLOGY, PNEUMO, WCBIP, FakeGoogle, RunningLibrary, person_context

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

PROMPT = "Type the folder name to confirm."
MISMATCH = "The name does not match. Nothing was deleted."
SPIROMETRY = "Spirometry Basics"
FOLDER_NAMES_SCRIPT = "() => [...document.querySelectorAll('ul.folders a')].map(link => link.textContent)"
FOCUS_SCRIPT = """() => {
  const active = document.activeElement;
  return {inDialog: Boolean(active && active.closest('dialog[open]')), text: active ? active.textContent : null,
          row: active && active.closest('li') ? active.closest('li').querySelector('a').textContent : null};
}"""


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = library_support.launch_chromium(playwright)
    yield browser
    browser.close()


def admin_page(running: RunningLibrary, google: FakeGoogle, chromium: Chromium) -> Page:
    person = running.browser()
    person.sign_in(google, ADMIN)
    page = person_context(chromium, running, person.cookies["lib"]).new_page()
    page.goto(f"{running.origin}/admin")
    return page


def pneumo_library(library_server: START, fake_google: FakeGoogle) -> tuple[RunningLibrary, str]:
    """The standard library with "Spirometry Basics" in "Pneumo Été"; returns the running library and its id."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.presentation(
        ids[PNEUMO], SPIROMETRY, size=4_096, modified=datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
    )
    return running, ids[PNEUMO]


def open_prompt(page: Page) -> None:
    """Press ``Delete folder`` in the row of "Pneumo Été"."""
    page.locator("ul.folders li", has_text=PNEUMO).get_by_role("button", name="Delete folder").click()


def listed(page: Page) -> list[str]:
    names: list[str] = page.evaluate(FOLDER_NAMES_SCRIPT)
    return names


def test_e2e_157_the_folder_deletion_prompt_can_be_cancelled(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-157: the prompt with ``Delete folder`` and ``Cancel`` shows, focus moves into it; ``Cancel`` closes it,
    focus returns to the row's button, no request is sent, the folder, its deck and the activity list are intact."""
    running, folder_id = pneumo_library(library_server, fake_google)
    page = admin_page(running, fake_google, chromium)
    sent: list[str] = []

    def keep_post(request: Request) -> None:
        if request.method == "POST":
            sent.append(request.url)

    page.on("request", keep_post)
    dialog = page.get_by_role("dialog")

    open_prompt(page)

    wait_until(page, dialog.is_visible, lambda shown: shown, what="the deletion prompt")
    assert dialog.get_by_text(PROMPT).is_visible()
    assert [dialog.get_by_role("button", name=name).is_visible() for name in ("Delete folder", "Cancel")] == [
        True,
        True,
    ]
    assert page.evaluate(FOCUS_SCRIPT)["inDialog"] is True

    dialog.get_by_role("button", name="Cancel").click()

    wait_until(page, lambda: page.locator("dialog[open]").count(), lambda count: count == 0, what="the prompt closed")
    assert page.evaluate(FOCUS_SCRIPT) == {"inDialog": False, "text": "Delete folder", "row": PNEUMO}
    assert sent == []
    assert listed(page) == [CARDIOLOGY, PNEUMO, WCBIP]
    assert running.stored.rows(f"SELECT name FROM presentations WHERE folder_id = '{folder_id}'") == [  # noqa: S608
        (SPIROMETRY,)
    ]
    assert running.stored.activity() == []


def test_a_wrong_name_is_shown_in_the_prompt_and_the_exact_name_deletes(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """FR-NEW-044 then FR-NEW-043 in the page: the mismatch text appears in the prompt and the folder stays; the exact
    name deletes it and the page reloads without it, the activity list showing ``Deleted folder "Pneumo Été"``."""
    running, _ = pneumo_library(library_server, fake_google)
    page = admin_page(running, fake_google, chromium)
    dialog = page.get_by_role("dialog")
    field = dialog.get_by_label(PROMPT)
    alert = dialog.get_by_role("alert")
    open_prompt(page)

    field.fill("pneumo été")
    dialog.get_by_role("button", name="Delete folder").click()
    wait_until(page, alert.text_content, lambda text: text == MISMATCH, what="the mismatch text in the prompt")
    assert listed(page) == [CARDIOLOGY, PNEUMO, WCBIP]

    field.fill(PNEUMO)
    with page.expect_navigation():
        dialog.get_by_role("button", name="Delete folder").click()

    assert listed(page) == [CARDIOLOGY, WCBIP]
    assert page.locator("ol.activity .text").first.text_content() == f'Deleted folder "{PNEUMO}"'
