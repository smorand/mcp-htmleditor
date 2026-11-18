"""US-0130: the administration page in Chromium (SPEC-0025).

Spec tests: E2E-096, E2E-097. The administrator signs in over HTTP through ``FakeGoogle``; the session cookie goes
into a Chromium context (``person_context``) where ``library.js`` sends the ``Create folder`` form with ``fetch``,
reloads the page on success and writes a refusal with ``textContent`` into the alert.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Page, Playwright, ViewportSize

from tests import library_support
from tests.browser_wait import wait_until
from tests.conftest import needs_chromium
from tests.library_support import ADMIN, CARDIOLOGY, PNEUMO, WCBIP, Browser, FakeGoogle, RunningLibrary, person_context

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

NAME_REFUSED = "Folder names use 1 to 60 letters, digits, spaces or hyphens."
PHONE: ViewportSize = {"width": 360, "height": 740}
CYRILLIC = "\u041a\u0430\u0440\u0434\u0438\u043e\u043b\u043e\u0433\u0438\u044f 2027"
ARABIC = "\u0623\u0645\u0631\u0627\u0636 \u0627\u0644\u0631\u0626\u0629"
CHINESE = "\u5fc3\u81d3\u75c5\u5b66"
FOLDER_NAMES_SCRIPT = "() => [...document.querySelectorAll('ul.folders a')].map(link => link.textContent)"
# The box of the folder link named ``name`` against the page and every other control (DEC-053: a, button, input),
# the controls of a closed deletion prompt (US-0131) aside.
LAYOUT_SCRIPT = """name => {
  const link = [...document.querySelectorAll('ul.folders a')].find(element => element.textContent === name);
  const box = link.getBoundingClientRect();
  const width = document.documentElement.clientWidth;
  const controls = [...document.querySelectorAll('a, button, input')]
    .filter(element => element !== link && !element.closest('dialog:not([open])'));
  const overlapping = controls.filter(element => {
    const other = element.getBoundingClientRect();
    return !(other.right <= box.left || other.left >= box.right || other.bottom <= box.top || other.top >= box.bottom);
  });
  const hidden = controls.filter(element => {
    const other = element.getBoundingClientRect();
    return other.width === 0 || other.height === 0 || other.left < 0 || other.right > width;
  });
  return {shown: link.innerText.replace(/\\s/g, ''), inside: box.left >= 0 && box.right <= width,
          scrolls: document.documentElement.scrollWidth > width,
          overlapping: overlapping.map(element => element.textContent || element.id),
          hidden: hidden.map(element => element.textContent || element.id)};
}"""
# The horizontal position of the first and the last character of the folder link named ``name``.
READING_SCRIPT = """name => {
  const link = [...document.querySelectorAll('ul.folders a')].find(element => element.textContent === name);
  const text = link.firstChild;
  const range = document.createRange();
  range.setStart(text, 0);
  range.setEnd(text, 1);
  const first = range.getBoundingClientRect().left;
  range.setStart(text, text.length - 1);
  range.setEnd(text, text.length);
  return {first: first, last: range.getBoundingClientRect().left};
}"""


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = library_support.launch_chromium(playwright)
    yield browser
    browser.close()


def admin_page(
    running: RunningLibrary, google: FakeGoogle, chromium: Chromium, viewport: ViewportSize | None = None
) -> Page:
    """The administrator's administration page in Chromium, in ``viewport`` when given."""
    person: Browser = running.browser()
    person.sign_in(google, ADMIN)
    page = person_context(chromium, running, person.cookies["lib"]).new_page()
    if viewport is not None:
        page.set_viewport_size(viewport)
    page.goto(f"{running.origin}/admin")
    return page


def create_folder(page: Page, name: str) -> None:
    """Type ``name`` in ``Folder name`` and press ``Create folder``; the page reloads on success."""
    page.get_by_label("Folder name", exact=True).fill(name)
    with page.expect_navigation():
        page.get_by_role("button", name="Create folder").click()


def listed(page: Page) -> list[str]:
    names: list[str] = page.evaluate(FOLDER_NAMES_SCRIPT)
    return names


def test_e2e_096_a_name_of_exactly_60_characters_or_a_single_hyphen_is_accepted(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-096: 60 letters "B" and "-" are created and listed; on a phone wide screen the long name is shown in full,
    inside the page, overlapping and hiding no control."""
    running = library_server(fake_google)
    running.builder.standard()
    page = admin_page(running, fake_google, chromium, viewport=PHONE)
    long_name = "B" * 60

    create_folder(page, long_name)
    create_folder(page, "-")

    assert listed(page) == ["-", long_name, CARDIOLOGY, PNEUMO, WCBIP]
    layout = page.evaluate(LAYOUT_SCRIPT, long_name)
    assert layout == {"shown": long_name, "inside": True, "scrolls": False, "overlapping": [], "hidden": []}
    page.goto(f"{running.origin}/")
    assert listed(page) == ["-", long_name, CARDIOLOGY, PNEUMO, WCBIP]
    assert page.evaluate(LAYOUT_SCRIPT, long_name)["inside"] is True
    assert sorted(running.stored.folder_names()) == sorted(["-", long_name, CARDIOLOGY, PNEUMO, WCBIP])


def test_e2e_097_names_in_other_alphabets_are_accepted(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-097: the Cyrillic, Arabic and Chinese names are listed as typed, after the Latin ones; the Arabic one
    reads right to left (its first letter is drawn to the right of its last), the Cyrillic one left to right."""
    running = library_server(fake_google)
    running.builder.standard()
    page = admin_page(running, fake_google, chromium)

    for name in (CYRILLIC, ARABIC, CHINESE):
        create_folder(page, name)

    expected = [CARDIOLOGY, PNEUMO, WCBIP, CYRILLIC, ARABIC, CHINESE]
    assert listed(page) == expected
    arabic = page.evaluate(READING_SCRIPT, ARABIC)
    cyrillic = page.evaluate(READING_SCRIPT, CYRILLIC)
    assert arabic["first"] > arabic["last"], arabic
    assert cyrillic["first"] < cyrillic["last"], cyrillic
    page.goto(f"{running.origin}/")
    assert listed(page) == expected


def test_a_refused_name_is_written_in_the_alert_and_nothing_is_created(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """FR-NEW-041, FR-NEW-042: the refusal text appears in the alert next to the field, the page stays."""
    running = library_server(fake_google)
    running.builder.standard()
    page = admin_page(running, fake_google, chromium)
    alert = page.locator("#create-folder-alert")

    page.get_by_label("Folder name", exact=True).fill("R&D")
    page.get_by_role("button", name="Create folder").click()
    wait_until(page, alert.text_content, lambda text: text == NAME_REFUSED, what="the name rule in the alert")
    page.get_by_label("Folder name", exact=True).fill("cardiology 2027")
    page.get_by_role("button", name="Create folder").click()
    wait_until(
        page,
        alert.text_content,
        lambda text: text == 'A folder named "cardiology 2027" already exists.',
        what="the duplicate message in the alert",
    )

    assert page.get_by_role("alert").text_content() == 'A folder named "cardiology 2027" already exists.'
    assert listed(page) == [CARDIOLOGY, PNEUMO, WCBIP]
    assert running.stored.activity() == []
