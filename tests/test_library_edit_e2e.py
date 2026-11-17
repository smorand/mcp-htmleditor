"""US-0136: editing a presentation of the library in Chromium (SPEC-0025).

Spec tests: E2E-027, E2E-034, E2E-039, E2E-041, E2E-043, E2E-044, E2E-046, E2E-047, E2E-048, E2E-049, E2E-050,
E2E-051, E2E-151, E2E-152, E2E-153, E2E-189. People sign in over HTTP through ``FakeGoogle`` and Chromium holds their
session cookie; the editor's own timers (800 ms, at once on blur) do the storing. The second channel of every check
is the stored file, its history and the activity table, read from disk.
"""

from __future__ import annotations

import errno
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Playwright

from mcp_htmleditor import fileio
from tests import library_support
from tests.browser_wait import settle, wait_for_js, wait_until
from tests.conftest import needs_chromium
from tests.library_support import (
    ADMIN,
    ARRHYTHMIA,
    CARDIOLOGY,
    CAROL,
    DAN,
    HEART_FAILURE,
    STATINS,
    FakeGoogle,
    Presentation,
    RunningLibrary,
    deck_frame,
    launch_chromium,
    leave_field,
    person_context,
    signed_in,
    stored_title,
    turn_edit_on,
    type_in_title,
)

pytestmark = needs_chromium

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

CONFLICT_TEXT = "The file changed on disk. Reload to see the changes, or keep your version."
FRAME_TITLE = "document.querySelector('h1').textContent"
HIDDEN_CONTROLS = ("edit-mode-btn", "undo-btn", "redo-btn", "requests-toggle", "ask-ai-btn", "notes-btn")
POLL_MILLISECONDS = 100
MODIFIED = datetime(2026, 11, 12, 16, 40, tzinfo=UTC)


@pytest.fixture
def chromium(playwright: Playwright) -> Iterator[Chromium]:
    browser = launch_chromium(playwright)
    yield browser
    browser.close()


@dataclass
class Library:
    """The running library with the standard folders and presentations, and the pages opened so far."""

    running: RunningLibrary
    google: FakeGoogle
    chromium: Chromium
    ids: dict[str, str]
    decks: dict[str, Presentation]
    pages: dict[str, Page] = field(default_factory=dict)

    def page(self, email: str) -> Page:
        """A new page of ``email``, signed in (one per call: two people, or one person twice)."""
        person = signed_in(self.running, self.google, email)
        return person_context(self.chromium, self.running, person.cookies["lib"]).new_page()

    def open(self, email: str, name: str, *, edit: bool = False) -> Page:
        """The page of ``email`` on the presentation ``name``, deck shown, in edit mode when ``edit``."""
        page = self.page(email)
        deck = self.decks[name]
        page.goto(f"{self.running.origin}/open/{deck.id}")
        page.wait_for_url(f"{self.running.content_origin}/d/{deck.id}/")
        wait_for_js(deck_frame(page), "document.querySelectorAll('section.slide').length > 0", True, what="deck")
        if edit:
            turn_edit_on(page)
        return page

    def served_title(self, email: str, name: str) -> str:
        """The title of slide 1 served to ``email`` for the content of ``name`` (a fresh browser, as a reload)."""
        person = signed_in(self.running, self.google, email)
        deck = self.decks[name]
        person.open_presentation(deck.id)
        match = re.search(r"<h1[^>]*>([^<]*)</h1>", person.deck(deck.id, "content", x_editor="1").text)
        assert match is not None
        return match.group(1)

    def titles_in_history(self, name: str) -> list[str]:
        """The first title of each history version of ``name``, newest first."""
        deck = self.decks[name]
        found = []
        for version in self.running.versions(deck):
            match = re.search(r"<h1[^>]*>([^<]*)</h1>", self.running.version_text(deck, version))
            found.append(match[1] if match else "")
        return found


@pytest.fixture
def library(library_server: START, fake_google: FakeGoogle, chromium: Chromium) -> Library:
    running = library_server(fake_google, poll_interval=POLL_MILLISECONDS)
    ids = running.builder.standard()
    return Library(running, fake_google, chromium, ids, running.builder.standard_presentations(ids))


def notice_visible(page: Page, notice: str) -> bool:
    return page.evaluate(f"!document.getElementById('{notice}').hidden")


def frame_title(page: Page) -> str:
    """The title shown in the deck frame; empty while the frame navigates (a reload, a new content)."""
    try:
        return str(deck_frame(page).evaluate(FRAME_TITLE))
    except PlaywrightError:
        return ""


def wait_stored(page: Page, deck: Presentation, title: str) -> None:
    wait_until(page, lambda: stored_title(deck), lambda found: found == title, what=f"stored title {title}")


def assert_no_save_control_or_notice(page: Page) -> None:
    assert page.get_by_role("button", name=re.compile("^save$", re.IGNORECASE)).count() == 0
    assert not notice_visible(page, "save-error")
    assert not notice_visible(page, "save-conflict")
    assert not page.get_by_text("session").is_visible()


def test_e2e_041_a_rw_member_edits_and_the_change_is_stored_by_itself(library: Library) -> None:
    """E2E-041: Dan turns edit mode on, changes the title, leaves the field; Carol is served the new title, the
    history holds the old one, the activity table gains nothing, no notice, no Save control."""
    deck = library.decks[HEART_FAILURE]
    before = library.running.stored.activity()
    page = library.open(DAN, HEART_FAILURE, edit=True)

    type_in_title(page, " 2027")
    leave_field(page)

    wait_stored(page, deck, "Heart Failure Update 2027")
    assert library.served_title(CAROL, HEART_FAILURE) == "Heart Failure Update 2027"
    assert library.titles_in_history(HEART_FAILURE) == ["Heart Failure Update"]
    assert library.running.stored.activity() == before
    assert_no_save_control_or_notice(page)


def test_e2e_151_a_change_is_stored_0_8_seconds_after_typing_stops(library: Library) -> None:
    """E2E-151: Dan types and stays in the field; once the 0.8 s of silence passed the title is stored."""
    deck = library.decks[HEART_FAILURE]
    page = library.open(DAN, HEART_FAILURE, edit=True)

    type_in_title(page, " 2027")

    wait_stored(page, deck, "Heart Failure Update 2027")
    assert library.served_title(CAROL, HEART_FAILURE) == "Heart Failure Update 2027"
    assert library.titles_in_history(HEART_FAILURE) == ["Heart Failure Update"]
    assert_no_save_control_or_notice(page)
    assert page.evaluate("document.activeElement === document.getElementById('content-frame')")  # still in the field


def test_e2e_153_typing_without_a_pause_is_stored_once_at_the_end(library: Library) -> None:
    """E2E-153: 40 characters over 5 seconds with 0.125 s between keys store nothing meanwhile and one version at
    the end; leaving the field 0.2 s after typing stores at once."""
    deck = library.decks[STATINS]
    page = library.open(DAN, STATINS, edit=True)
    type_in_title(page, "", replace=True)

    page.keyboard.type("a" * 20, delay=125)
    assert stored_title(deck) == STATINS
    page.keyboard.type("b" * 20, delay=125)

    wait_stored(page, deck, "a" * 20 + "b" * 20)
    assert len(library.running.versions(deck)) == 1
    type_in_title(page, "c", replace=True)
    leave_field(page)
    wait_stored(page, deck, "c")
    assert len(library.running.versions(deck)) == 2


def test_e2e_044_leaving_a_field_stores_the_change_at_once(library: Library) -> None:
    """E2E-044: the text of slide 2 is stored when Dan clicks outside; no 0.8 s wait is needed and nothing is
    written to the activity table."""
    deck = library.decks[STATINS]
    before = library.running.stored.activity()
    page = library.open(DAN, STATINS, edit=True)

    type_in_title(page, "First line therapy", replace=True, index=1)
    leave_field(page)

    wait_until(
        page,
        lambda: deck.path.read_text(encoding="utf-8"),
        lambda text: ">First line therapy</h1>" in text,
        what="slide 2 text stored",
    )
    assert library.running.stored.activity() == before


def test_e2e_046_accents_chinese_and_emoji_survive_a_stored_change(library: Library) -> None:
    """E2E-046: the title typed with accents, ideograms and an emoji reads the same after a reload."""
    text = "Cœur, insuffisance 心臓 😀"
    deck = library.decks[STATINS]
    page = library.open(DAN, STATINS, edit=True)

    type_in_title(page, text, replace=True, insert=True)
    leave_field(page)
    wait_stored(page, deck, text)
    page.reload()

    wait_until(page, lambda: frame_title(page), lambda found: found == text, what="reloaded title")
    assert library.served_title(CAROL, STATINS) == text


def test_e2e_039_a_rw_member_edits_a_presentation_of_someone_else(library: Library) -> None:
    """E2E-039: the administrator uploaded "Arrhythmia Basics"; Dan changes it, the previous version is kept."""
    deck = library.decks[ARRHYTHMIA]
    page = library.open(DAN, ARRHYTHMIA, edit=True)

    type_in_title(page, " v2")
    leave_field(page)

    wait_stored(page, deck, f"{ARRHYTHMIA} v2")
    assert library.titles_in_history(ARRHYTHMIA) == [ARRHYTHMIA]


def test_e2e_034_a_ro_viewer_sees_a_writers_change_without_gaining_controls(library: Library) -> None:
    """E2E-034: Carol's open page follows Dan's stored change and keeps no editing control."""
    carol = library.open(CAROL, HEART_FAILURE)
    dan = library.open(DAN, HEART_FAILURE, edit=True)

    type_in_title(dan, " 2027")
    leave_field(dan)

    wait_until(carol, lambda: frame_title(carol), lambda found: found == "Heart Failure Update 2027", what="Carol")
    for control in HIDDEN_CONTROLS:
        assert not carol.locator(f"#{control}").is_visible(), control


def test_e2e_027_equal_times_keep_a_stable_order_and_a_save_moves_the_row_first(library: Library) -> None:
    """E2E-027: Arrhythmia Basics before Statins Review on 5 displays; after Dan's change (modified 17:30) Statins
    Review is first. "Eclair" is listed before "éclair" (same key, then character code)."""
    folder = library.ids[CARDIOLOGY]
    for name in ("éclair", "Eclair"):
        library.running.builder.presentation(folder, name, size=2_048, modified=MODIFIED)
    page = library.page(DAN)
    names = (
        "() => [...document.querySelectorAll('ul.presentations li')].map(row => row.querySelector('.name').textContent)"
    )
    first_five = []
    for _ in range(5):
        page.goto(f"{library.running.origin}/f/{folder}")
        first_five.append(page.evaluate(names))

    deck = library.decks[STATINS]
    editor = library.open(DAN, STATINS, edit=True)
    type_in_title(editor, " B")
    leave_field(editor)
    wait_stored(editor, deck, f"{STATINS} B")
    moment = datetime(2026, 11, 12, 17, 30, tzinfo=UTC).timestamp()
    os.utime(deck.path, (moment, moment))
    page.goto(f"{library.running.origin}/f/{folder}")

    assert all(found.index(ARRHYTHMIA) < found.index(STATINS) for found in first_five)
    assert all(found.index("Eclair") < found.index("éclair") for found in first_five)
    rows = page.evaluate(names)
    assert rows[0] == STATINS
    assert page.locator("ul.presentations li time").first.inner_text() == "12 Nov 2026 17:30"


def test_e2e_043_a_change_that_cannot_be_written_shows_the_notice_and_stays_on_screen(
    library: Library, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E-043: no space left: the usual notice with the reason, the typed title stays, the stored file is the old
    one, whole."""
    deck = library.decks[HEART_FAILURE]
    before = deck.path.read_bytes()
    page = library.open(DAN, HEART_FAILURE, edit=True)

    def full(_source: object, _target: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(fileio, "replace_file", full)
    type_in_title(page, " 2027")
    leave_field(page)

    wait_until(page, lambda: notice_visible(page, "save-error"), bool, what="the failure notice")
    assert "No space left on device" in page.locator("#save-error").inner_text()
    assert frame_title(page) == "Heart Failure Update 2027"
    assert deck.path.read_bytes() == before
    assert library.served_title(CAROL, HEART_FAILURE) == HEART_FAILURE


def test_e2e_152_a_failed_store_is_retried_with_the_next_change_and_the_notice_goes(
    library: Library, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E-152: while the library cannot be written the title stays on screen with the notice; once it can, one more
    character stores the whole title and the notice disappears."""
    deck = library.decks[HEART_FAILURE]
    page = library.open(DAN, HEART_FAILURE, edit=True)
    with monkeypatch.context() as broken:

        def full(_source: object, _target: object) -> None:
            raise OSError(errno.ENOSPC, "No space left on device")

        broken.setattr(fileio, "replace_file", full)
        type_in_title(page, " 2027")
        wait_until(page, lambda: notice_visible(page, "save-error"), bool, what="the failure notice")
        assert frame_title(page) == "Heart Failure Update 2027"
        assert library.served_title(CAROL, HEART_FAILURE) == HEART_FAILURE

    type_in_title(page, "!")

    wait_stored(page, deck, "Heart Failure Update 2027!")
    wait_until(page, lambda: notice_visible(page, "save-error"), lambda shown: not shown, what="notice gone")


def test_e2e_047_a_change_above_the_limit_is_refused_and_the_stored_version_stays(library: Library) -> None:
    """E2E-047: pictures that make the file 60 MB: the failure notice shows, the changes stay on screen and the file
    is still the stored version of 1 572 864 bytes. The exact boundary is in test_library_edit_http.py."""
    deck = library.decks[STATINS]
    page = library.open(DAN, STATINS, edit=True)
    deck_frame(page).evaluate(
        "() => { const image = document.createElement('img');"
        " image.src = 'data:image/png;base64,' + 'A'.repeat(60 * 1024 * 1024);"
        " document.body.appendChild(image); }"
    )

    type_in_title(page, " big")
    leave_field(page)

    wait_until(page, lambda: notice_visible(page, "save-error"), bool, what="the failure notice")
    assert page.locator("#save-error").inner_text() == "Save failed: Request too large"
    assert frame_title(page) == f"{STATINS} big"
    assert deck.path.stat().st_size == 1_572_864


def test_e2e_048_one_after_the_other_meets_no_conflict_and_an_idle_screen_follows(library: Library) -> None:
    """E2E-048: Dan stores "Statins 2027", the administrator then stores "Statins 2028" with no notice and both
    previous versions are kept; Dan, who typed nothing, sees "Statins 2028" within 2 seconds with no notice."""
    deck = library.decks[STATINS]
    dan = library.open(DAN, STATINS, edit=True)
    type_in_title(dan, "Statins 2027", replace=True)
    leave_field(dan)
    wait_stored(dan, deck, "Statins 2027")
    admin = library.open(ADMIN, STATINS, edit=True)

    type_in_title(admin, "Statins 2028", replace=True)
    leave_field(admin)

    wait_stored(admin, deck, "Statins 2028")
    assert not notice_visible(admin, "save-conflict")
    assert library.titles_in_history(STATINS) == ["Statins 2027", STATINS]
    wait_until(dan, lambda: frame_title(dan), lambda found: found == "Statins 2028", what="Dan follows", bound=2.0)
    assert not notice_visible(dan, "save-conflict")


def conflict(library: Library) -> tuple[Page, Page]:
    """Dan has typed "Statins B" in the title and has not left the field; the administrator stored "Statins A"."""
    deck = library.decks[STATINS]
    dan = library.open(DAN, STATINS, edit=True)
    admin = library.open(ADMIN, STATINS, edit=True)
    type_in_title(dan, "Statins B", replace=True)
    type_in_title(admin, "Statins A", replace=True)
    leave_field(admin)
    wait_stored(admin, deck, "Statins A")
    return dan, admin


def test_e2e_049_leaving_a_field_after_someone_elses_stored_change_shows_the_conflict(library: Library) -> None:
    """E2E-049: the notice with the exact text and the two buttons; Carol is served "Statins A": Dan's text is not
    stored."""
    dan, _admin = conflict(library)

    leave_field(dan)

    wait_until(dan, lambda: notice_visible(dan, "save-conflict"), bool, what="the conflict notice")
    notice = dan.locator("#save-conflict")
    assert CONFLICT_TEXT in notice.inner_text()
    assert notice.get_by_role("button", name="Keep mine").is_visible()
    assert notice.get_by_role("button", name="Reload").is_visible()
    assert library.served_title(CAROL, STATINS) == "Statins A"


def test_e2e_050_keep_mine_stores_the_version_and_keeps_the_other_in_the_history(library: Library) -> None:
    """E2E-050."""
    dan, _admin = conflict(library)
    leave_field(dan)
    wait_until(dan, lambda: notice_visible(dan, "save-conflict"), bool, what="the conflict notice")

    dan.locator("#save-conflict").get_by_role("button", name="Keep mine").click()

    wait_stored(dan, library.decks[STATINS], "Statins B")
    assert library.titles_in_history(STATINS)[0] == "Statins A"
    assert library.served_title(CAROL, STATINS) == "Statins B"


def test_e2e_051_reload_shows_the_stored_version_and_drops_the_unsaved_change(library: Library) -> None:
    """E2E-051: "Statins B" is nowhere in the stored file or its history afterwards."""
    dan, _admin = conflict(library)
    leave_field(dan)
    wait_until(dan, lambda: notice_visible(dan, "save-conflict"), bool, what="the conflict notice")

    dan.locator("#save-conflict").get_by_role("button", name="Reload").click()

    wait_until(dan, lambda: frame_title(dan), lambda found: found == "Statins A", what="stored title")
    deck = library.decks[STATINS]
    assert "Statins B" not in deck.path.read_text(encoding="utf-8")
    assert all("Statins B" not in library.running.version_text(deck, v) for v in library.running.versions(deck))
    settle(dan)
    assert stored_title(deck) == "Statins A"


def test_e2e_189_two_people_leaving_their_fields_in_the_same_second_leave_one_stored_version(
    library: Library,
) -> None:
    """E2E-189: both typed, both leave: one title is stored whole, the other person sees the conflict notice, and the
    earlier version is in the history."""
    deck = library.decks[STATINS]
    dan = library.open(DAN, STATINS, edit=True)
    admin = library.open(ADMIN, STATINS, edit=True)
    type_in_title(dan, "Statins B", replace=True)
    type_in_title(admin, "Statins A", replace=True)

    leave_field(dan)
    leave_field(admin)

    wait_until(
        dan,
        lambda: notice_visible(dan, "save-conflict") + notice_visible(admin, "save-conflict"),
        lambda shown: shown == 1,
        what="exactly one conflict notice",
    )
    assert stored_title(deck) in {"Statins A", "Statins B"}
    assert library.titles_in_history(STATINS) == [STATINS]
