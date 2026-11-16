"""US-0134: the editor shell on the content origin, and the local mode guards (SPEC-0025).

Spec tests: E2E-045, E2E-133, E2E-137. People sign in over HTTP through ``FakeGoogle`` and Chromium holds their
session cookie (``person_context``). The second channel of the shell tests is the served bytes compared with
``static/editor.html`` (``difflib``); the local guards run the unmodified local server (``serve_deck``).
"""

from __future__ import annotations

import difflib
import html
import json
import os
import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import FrameLocator, Page, Playwright

from mcp_htmleditor.history import list_versions
from mcp_htmleditor.http_server import _static_dir
from tests import library_support
from tests.browser_wait import wait_for_file, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import deck_ei, write_deck
from tests.library_support import (
    CARDIOLOGY,
    CAROL,
    CHALLENGES,
    DAN,
    HEART_FAILURE,
    LAMYA,
    WCBIP,
    FakeGoogle,
    Presentation,
    RunningLibrary,
    deck_frame,
    deck_with_pictures,
    launch_chromium,
    person_context,
    signed_in,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

FRAME_TITLE = "document.querySelector('h1') ? document.querySelector('h1').textContent : ''"
MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
CONFIG_PATTERN = re.compile(r"<meta name=\"editor-config\" content='([^']*)'>")


def heart_library(running: RunningLibrary) -> tuple[dict[str, str], Presentation]:
    """The standard folders and "Heart Failure Update" (3 slides) in Cardiology."""
    ids = running.builder.standard()
    return ids, running.builder.presentation(ids[CARDIOLOGY], HEART_FAILURE, size=8_192, modified=MODIFIED, slides=3)


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


def editor_page(chromium: Chromium, running: RunningLibrary, google: FakeGoogle, email: str) -> Page:
    """A page of ``email``, signed in, on the library home page."""
    person = signed_in(running, google, email)
    return person_context(chromium, running, person.cookies["lib"]).new_page()


def open_from_folder(page: Page, running: RunningLibrary, folder_id: str, name: str) -> None:
    """Click the presentation ``name`` of the folder page; the editor shell loads on the content origin."""
    page.goto(f"{running.origin}/f/{folder_id}")
    page.get_by_role("link", name=name).click()
    page.wait_for_url(re.compile(r"/d/[0-9a-f]{32}/$"))


# ---------------------------------------------------------------------------
# The shell: three differences, a link from the folder page, pictures, reload
# ---------------------------------------------------------------------------


def test_library_shell_the_served_shell_differs_from_editor_html_in_three_places(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """DEC-038: replacing the three edits in the served bytes gives ``static/editor.html`` back, and a line diff
    shows exactly the frame, the download link and the inserted meta and script."""
    running = library_server(fake_google)
    _ids, heart = heart_library(running)
    dan = signed_in(running, fake_google, DAN)
    dan.open_presentation(heart.id)
    reply = dan.deck(heart.id, "")
    original = (_static_dir() / "editor.html").read_text(encoding="utf-8")

    assert reply.status == 200
    assert reply.headers["content-type"].startswith("text/html")
    assert reply.headers["content-security-policy"] == "frame-ancestors 'none'"
    assert reply.headers["x-frame-options"] == "DENY"
    assert "no-store" in reply.headers["cache-control"]
    changed = [
        line
        for line in difflib.unified_diff(original.splitlines(), reply.text.splitlines(), lineterm="", n=0)
        if line[:1] in "+-" and line[:3] not in {"+++", "---"}
    ]
    assert len(changed) == 6, changed  # three lines removed, their three replacements added
    pid = heart.id
    assert f'src="/d/{pid}/content-frame"' in reply.text
    assert f'href="/d/{pid}/download"' in reply.text
    config = json.loads(html.unescape(CONFIG_PATTERN.search(reply.text).group(1)))  # type: ignore[union-attr]
    assert config == {"base": f"/d/{pid}", "readOnly": False, "library": running.origin}
    restored = (
        reply.text.replace(f'src="/d/{pid}/content-frame"', 'src="/content-frame"')
        .replace(f'href="/d/{pid}/download"', 'href="/download"')
        .replace(CONFIG_PATTERN.search(reply.text).group(0) + '<script src="/static/editor-library.js"></script>', "")  # type: ignore[union-attr]
    )
    assert restored == original


def test_library_shell_the_library_script_is_served_to_anyone_and_the_shell_is_not(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """``/static/<name>`` is product code (no grant needed); the shell of a presentation needs the grant."""
    running = library_server(fake_google)
    _ids, heart = heart_library(running)
    content = running.client(running.content_netloc)

    script = content.get("/static/editor-library.js")
    shell = content.get(f"/d/{heart.id}/")

    assert script.status == 200
    assert script.headers["content-type"].startswith("application/javascript")
    assert b"__libraryCode" in script.body
    assert shell.status == 302
    assert shell.headers["location"] == f"{running.origin}/open/{heart.id}"
    assert heart.name.encode() not in shell.body


def test_e2e_045_a_deck_with_embedded_pictures_displays_them(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """E2E-045 and the independent test: Lamya opens "From Challenges to Change" (18 slides, pictures embedded) from
    the folder page; the frame shows slide 1 under the toolbar name, and every picture has a width."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    deck = running.builder.standard_presentations(ids)[CHALLENGES]
    deck.path.write_bytes(deck_with_pictures(CHALLENGES, 18))
    page = editor_page(chromium, running, fake_google, LAMYA)

    open_from_folder(page, running, ids[WCBIP], CHALLENGES)

    wait_until(page, lambda: page.inner_text("#toolbar-filename"), lambda t: t == f"{CHALLENGES}.html", what="name")
    frame = deck_frame(page)
    wait_for_js(frame, "document.querySelectorAll('section.slide').length", 18, what="slides")
    widths = wait_until(
        page,
        lambda: frame.evaluate("[...document.images].map(image => image.naturalWidth)"),
        lambda found: len(found) == 18 and all(width > 0 for width in found),
        what="pictures",
    )
    assert widths == [1] * 18
    assert frame.evaluate(FRAME_TITLE) == CHALLENGES
    assert page.url == f"{running.content_origin}/d/{deck.id}/"


def test_library_shell_the_folder_page_link_reaches_the_shell_through_the_redirects(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """Carol (RO) clicks "Heart Failure Update": ``/open/<pid>``, ``/enter``, then the shell; the folder page link
    is ``/open/<pid>`` and the editor shell reads the base of its presentation."""
    running = library_server(fake_google)
    ids, heart = heart_library(running)
    page = editor_page(chromium, running, fake_google, CAROL)
    page.goto(f"{running.origin}/f/{ids[CARDIOLOGY]}")
    assert page.get_attribute("a:text('Heart Failure Update')", "href") == f"/open/{heart.id}"

    page.get_by_role("link", name=HEART_FAILURE).click()
    page.wait_for_url(f"{running.content_origin}/d/{heart.id}/")

    wait_until(page, lambda: page.inner_text("#toolbar-filename"), lambda t: t == f"{HEART_FAILURE}.html", what="name")
    assert deck_frame(page).evaluate(FRAME_TITLE) == HEART_FAILURE
    assert page.get_attribute("#download-btn", "href") == f"/d/{heart.id}/download"


def test_library_shell_another_writer_saves_and_the_open_editor_reloads_the_frame(
    library_server: START, fake_google: FakeGoogle, chromium: Chromium
) -> None:
    """Dan's open editor sees a change written by someone else: ``reloadFrame`` loads ``<base>/content-frame`` (the
    editor's own absolute path would blank the deck on the content origin) and the new title shows."""
    running = library_server(fake_google, poll_interval=1)
    ids, heart = heart_library(running)
    page = editor_page(chromium, running, fake_google, DAN)
    open_from_folder(page, running, ids[CARDIOLOGY], HEART_FAILURE)
    frame = deck_frame(page)
    wait_for_js(frame, FRAME_TITLE, HEART_FAILURE, what="first title")

    heart.path.write_text(heart.path.read_text(encoding="utf-8").replace(HEART_FAILURE, "Changed elsewhere"))
    os.utime(heart.path, (heart.path.stat().st_mtime + 60, heart.path.stat().st_mtime + 60))

    reloaded = wait_until(
        page,
        lambda: deck_frame(page).evaluate(FRAME_TITLE),
        lambda title: title == "Changed elsewhere",
        what="reloaded title",
    )
    assert reloaded == "Changed elsewhere"
    assert re.fullmatch(rf"{re.escape(running.content_origin)}/d/{heart.id}/content-frame\?\d+", deck_frame(page).url)


# ---------------------------------------------------------------------------
# The local mode guards, written against the unmodified local server
# ---------------------------------------------------------------------------


def test_e2e_133_the_local_mode_edits_one_file_with_no_sign_in(
    tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], page: Page
) -> None:
    """E2E-133: no sign in, the shell is the one of ``editor.html`` (no library script), the title typed in the frame
    is stored in talk.html, its history holds the previous version, the PPTX downloads."""
    talk = Path(write_deck(tmp_path / "talk.html", deck_ei()))
    before = talk.read_text(encoding="utf-8")
    deck = serve_deck(talk)

    page.goto(f"http://127.0.0.1:{deck.port}/")
    wait_until(page, lambda: page.inner_text("#toolbar-filename"), lambda t: t == "talk.html", what="name")
    assert page.url == f"http://127.0.0.1:{deck.port}/"
    assert "editor-library.js" not in page.content()
    assert page.evaluate("typeof window.__libraryCode") == "undefined"
    page.click("#edit-mode-btn")
    deck_frame_local(page).locator('h1[data-editable~="text"]').first.evaluate(
        "element => { element.focus(); element.textContent = 'Hello';"
        " element.dispatchEvent(new Event('input', {bubbles: true})); }"
    )

    text = wait_for_file(page, talk, "Hello")
    assert text != before
    assert list_versions(str(talk))[1], "no history version"
    pptx = page.request.get(f"http://127.0.0.1:{deck.port}/export/pptx")
    assert pptx.status == 200
    assert pptx.body()[:2] == b"PK"


def deck_frame_local(page: Page) -> FrameLocator:
    return page.frame_locator("#content-frame")


def test_e2e_137_a_local_decks_script_reads_the_storage_of_the_local_address(
    tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], page: Page
) -> None:
    """E2E-137: talk.html's script reads what the browser keeps for the local address and shows it."""
    marker = (
        "<script>try { localStorage.setItem('talk-key', 'kept'); document.title = localStorage.getItem('talk-key'); }"
        " catch (e) { document.title = 'blocked'; }</script>"
    )
    source = deck_ei().replace("</body>", marker + "</body>", 1)
    talk = Path(write_deck(tmp_path / "talk.html", source))
    deck = serve_deck(talk)

    page.goto(f"http://127.0.0.1:{deck.port}/")

    frame = wait_until(
        page, lambda: page.frame(url=re.compile(r"/content-frame")), lambda f: f is not None, what="frame"
    )
    assert frame is not None
    assert wait_until(page, frame.title, lambda t: t != "", what="title") == "kept"
    assert frame.evaluate("localStorage.getItem('talk-key')") == "kept"
