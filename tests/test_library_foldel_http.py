"""US-0131: deleting a folder after retyping its name, over HTTP (SPEC-0025).

Spec tests: E2E-015, E2E-099, E2E-100, E2E-101, E2E-103, E2E-104, E2E-106, E2E-107. ``Browser.post_json`` sends what
the dialog's ``Delete folder`` button sends. The second channel is the operator view: ``StoredLibrary.entries()``
(a walk of ``library_dir`` and ``state_dir``) and the tables read directly; history versions, requests and AI
suggestions are written by the editor's own stores (``LibraryBuilder.records``).
"""

from __future__ import annotations

import html
import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor.library import pages
from tests import library_support
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    DAN,
    PNEUMO,
    WCBIP,
    Browser,
    FakeGoogle,
    LibraryReply,
    Presentation,
    RunningLibrary,
    visible_texts,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MISMATCH = "The name does not match. Nothing was deleted."
NO_FOLDER = "You have no access to any folder yet."
NO_PRESENTATION = "This folder has no presentations yet."
SPIROMETRY = "Spirometry Basics"
ONCOLOGY = "Oncology 2030"
MODIFIED = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
LIST_BOUND_SECONDS = 2.0  # FR-NEW-060


@pytest.fixture
def pneumo(library_server: START, fake_google: FakeGoogle) -> Iterator[Pneumo]:
    """The standard library; "Pneumo Été" holds "Spirometry Basics" (with history, requests and a suggestion) and
    has Dan as RW; the administrator is signed in."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.member(ids[PNEUMO], DAN, "RW")
    deck = running.builder.presentation(ids[PNEUMO], SPIROMETRY, size=4_096, modified=MODIFIED)
    records = running.builder.records(deck)
    yield Pneumo(running, ids, deck, records, signed_in(running, fake_google, ADMIN))


@dataclass(frozen=True)
class Pneumo:
    """What the ``pneumo`` fixture built."""

    running: RunningLibrary
    ids: dict[str, str]
    deck: Presentation
    records: Path
    admin: Browser

    @property
    def folder_id(self) -> str:
        return self.ids[PNEUMO]


def signed_in(running: RunningLibrary, google: FakeGoogle, email: str) -> Browser:
    browser = running.browser()
    browser.sign_in(google, email)
    return browser


def delete(browser: Browser, folder_id: str, confirm: Any) -> LibraryReply:
    """What the dialog's ``Delete folder`` button sends for the text typed in its field."""
    return browser.post_json(f"/api/folders/{folder_id}/delete", {"confirm": confirm})


def home_names(browser: Browser) -> list[str]:
    return [html.unescape(name) for _, name, _ in browser.open("/").folder_rows()]


def assert_access_denied(reply: LibraryReply) -> None:
    assert (reply.status, reply.body) == (403, pages.access_denied())


def assert_mismatch(reply: LibraryReply) -> None:
    assert (reply.status, reply.headers.get("content-type")) == (400, "application/json"), reply.text
    assert reply.json() == {"ok": False, "error": MISMATCH}


def assert_deleted(reply: LibraryReply) -> None:
    assert reply.status == 200, reply.status
    assert reply.json() == {"ok": True}


def relative(running: RunningLibrary, path: Path) -> str:
    """``path`` as ``StoredLibrary.entries()`` names it."""
    if path.is_relative_to(running.state_dir):
        return f"state/{path.relative_to(running.state_dir).as_posix()}"
    return f"library/{path.relative_to(running.library_dir).as_posix()}"


def traces_of(running: RunningLibrary, folder_id: str, record_dirs: list[Path]) -> list[str]:
    """Every stored path naming the folder or under the state directory of one of its presentations."""
    prefixes = tuple(relative(running, directory) for directory in record_dirs)
    return [entry for entry in running.stored.entries() if folder_id in entry or entry.startswith(prefixes)]


def members_of(running: RunningLibrary, folder_id: str) -> list[tuple[Any, ...]]:
    return [row for row in running.stored.rows("SELECT folder_id, email, role FROM members") if row[0] == folder_id]


def assert_pneumo_intact(scenario: Pneumo, activity_before: list[tuple[Any, ...]]) -> None:
    """The folder, its presentation file and row, its member, its history and requests, and no new activity line."""
    running = scenario.running
    assert PNEUMO in home_names(scenario.admin)
    rows = scenario.admin.open(f"/f/{scenario.folder_id}").presentation_rows()
    assert [html.unescape(row[0]) for row in rows] == [SPIROMETRY]
    assert scenario.deck.path.is_file()
    assert members_of(running, scenario.folder_id) == [(scenario.folder_id, DAN, "RW")]
    entries = running.stored.entries()
    for name in ("history", "requests"):
        assert f"{relative(running, scenario.records)}/{name}" in entries, name
    assert running.stored.activity() == activity_before


# ---------------------------------------------------------------------------
# E2E-099, E2E-103, E2E-106: deleting with the exact name
# ---------------------------------------------------------------------------


def test_e2e_099_the_administrator_deletes_a_folder_after_retyping_its_name(pneumo: Pneumo) -> None:
    """E2E-099: the home page lists 2 folders; no file, history, request, presentation row or member of "Pneumo Été"
    is left; the activity list gains ``Deleted folder "Pneumo Été"``; no mismatch message."""
    running = pneumo.running
    assert traces_of(running, pneumo.folder_id, [pneumo.records])  # the traces exist before the deletion

    reply = delete(pneumo.admin, pneumo.folder_id, PNEUMO)

    assert_deleted(reply)
    assert MISMATCH not in reply.text
    assert home_names(pneumo.admin) == [CARDIOLOGY, WCBIP]
    assert traces_of(running, pneumo.folder_id, [pneumo.records]) == []
    assert running.stored.rows("SELECT name FROM presentations") == []
    assert members_of(running, pneumo.folder_id) == []
    lines = pneumo.admin.open("/admin").activity_lines()
    assert [(actor, text) for _, actor, text in lines] == [(ADMIN, f'Deleted folder "{PNEUMO}"')]


def test_a_former_member_gets_access_denied_at_the_next_page(pneumo: Pneumo, fake_google: FakeGoogle) -> None:
    """FR-NEW-048 (folder deleted): Dan, who had the folder open, gets ``Access denied.`` at his next request for it,
    and his home page no longer lists it."""
    dan = signed_in(pneumo.running, fake_google, DAN)
    assert dan.open(f"/f/{pneumo.folder_id}").status == 200

    assert delete(pneumo.admin, pneumo.folder_id, PNEUMO).status == 200

    assert_access_denied(dan.open(f"/f/{pneumo.folder_id}"))
    assert home_names(dan) == [CARDIOLOGY]


def test_e2e_103_a_recreated_folder_is_empty_and_has_no_member(pneumo: Pneumo, fake_google: FakeGoogle) -> None:
    """E2E-103: "Pneumo Été" created again is listed, opens with ``This folder has no presentations yet.``, has no
    member (Dan gets ``Access denied.``) and no request or suggestion of the old deck exists anywhere."""
    running = pneumo.running
    assert delete(pneumo.admin, pneumo.folder_id, PNEUMO).status == 200

    created = pneumo.admin.post_json("/api/folders", {"name": PNEUMO})

    assert created.status == 201
    new_id = created.json()["id"]
    assert PNEUMO in home_names(pneumo.admin)
    page = pneumo.admin.open(f"/f/{new_id}")
    assert page.status == 200 and NO_PRESENTATION in page.text and page.presentation_rows() == []
    assert members_of(running, new_id) == []
    assert_access_denied(signed_in(running, fake_google, DAN).open(f"/f/{new_id}"))
    assert [entry for entry in running.stored.entries() if entry.startswith("state/files/")] == []


def test_e2e_106_deleting_the_last_folder_leaves_the_empty_home_page(pneumo: Pneumo) -> None:
    """E2E-106: with "Pneumo Été" the only folder left, deleting it shows ``You have no access to any folder yet.``;
    its line is the newest of the activity list."""
    for name in (WCBIP, CARDIOLOGY):
        assert delete(pneumo.admin, pneumo.ids[name], name).status == 200
    assert home_names(pneumo.admin) == [PNEUMO]

    assert delete(pneumo.admin, pneumo.folder_id, PNEUMO).status == 200

    home = pneumo.admin.open("/")
    assert home.status == 200 and NO_FOLDER in visible_texts(home)
    newest = pneumo.admin.open("/admin").activity_lines()[0]
    assert newest[1:] == (ADMIN, f'Deleted folder "{PNEUMO}"')


def test_e2e_015_the_administrator_with_no_folder_sees_the_empty_message(pneumo: Pneumo) -> None:
    """E2E-015: after the three folders are deleted the home page shows the message, Administration and Sign out;
    once "Oncology 2030" is created it is listed and the message is gone."""
    for name in (WCBIP, CARDIOLOGY, PNEUMO):
        assert delete(pneumo.admin, pneumo.ids[name], name).status == 200

    empty = pneumo.admin.open("/")
    assert empty.status == 200
    assert visible_texts(empty) == ["Slides", NO_FOLDER, "Administration", "Sign out"]

    assert pneumo.admin.post_json("/api/folders", {"name": ONCOLOGY}).status == 201
    listed = pneumo.admin.open("/")
    assert [html.unescape(name) for _, name, _ in listed.folder_rows()] == [ONCOLOGY]
    assert NO_FOLDER not in listed.text


# ---------------------------------------------------------------------------
# E2E-100, E2E-101, E2E-107: a name that differs deletes nothing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    ["pneumo été", "", "Pneumo Ete", f"{PNEUMO} ", " " + PNEUMO, "PNEUMO ÉTÉ"],
    ids=[
        "e2e-100-lower-case",
        "e2e-101-empty",
        "e2e-107-no-accent",
        "e2e-107-trailing-space",
        "leading-space",
        "upper",
    ],
)
def test_a_retyped_name_that_differs_deletes_nothing(pneumo: Pneumo, typed: str) -> None:
    """E2E-100, E2E-101, E2E-107: ``The name does not match. Nothing was deleted.``; the folder, its deck, its member,
    its history and requests are intact and no activity line is added."""
    before = pneumo.running.stored.activity()

    assert_mismatch(delete(pneumo.admin, pneumo.folder_id, typed))

    assert_pneumo_intact(pneumo, before)


def test_e2e_107_a_name_typed_with_separate_accent_marks_is_accepted(pneumo: Pneumo) -> None:
    """E2E-107: "Pneumo E\\u0301te\\u0301" (decomposed) is brought to its composed form, so it matches and deletes."""
    decomposed = "Pneumo E\u0301te\u0301"
    assert decomposed != PNEUMO

    reply = delete(pneumo.admin, pneumo.folder_id, decomposed)

    assert_deleted(reply)
    assert home_names(pneumo.admin) == [CARDIOLOGY, WCBIP]
    assert traces_of(pneumo.running, pneumo.folder_id, [pneumo.records]) == []


# ---------------------------------------------------------------------------
# E2E-104: 100 presentations
# ---------------------------------------------------------------------------


def test_e2e_104_a_folder_of_100_presentations_is_deleted_entirely(pneumo: Pneumo) -> None:
    """E2E-104: the folder page lists the 100 decks within 2 seconds; after the deletion no file, history or request
    of any of them is left, and "Pneumo Été" created again is empty."""
    running = pneumo.running
    decks = [
        running.builder.presentation(pneumo.folder_id, f"Deck {number:03d}", size=2_048, modified=MODIFIED)
        for number in range(1, 101)
    ]
    record_dirs = [pneumo.records, *(running.builder.records(deck) for deck in decks)]

    started = time.monotonic()
    page = pneumo.admin.open(f"/f/{pneumo.folder_id}")
    elapsed = time.monotonic() - started
    assert page.status == 200 and len(page.presentation_rows()) == 101
    assert elapsed < LIST_BOUND_SECONDS, elapsed

    assert delete(pneumo.admin, pneumo.folder_id, PNEUMO).status == 200

    assert PNEUMO not in home_names(pneumo.admin)
    assert traces_of(running, pneumo.folder_id, record_dirs) == []
    assert running.stored.rows("SELECT name FROM presentations") == []
    new_id = pneumo.admin.post_json("/api/folders", {"name": PNEUMO}).json()["id"]
    recreated = pneumo.admin.open(f"/f/{new_id}")
    assert NO_PRESENTATION in recreated.text and recreated.presentation_rows() == []
    assert [entry for entry in running.stored.entries() if entry.startswith("state/files/")] == []


# ---------------------------------------------------------------------------
# Refusals and failure modes
# ---------------------------------------------------------------------------


def test_a_member_cannot_delete_a_folder(pneumo: Pneumo, fake_google: FakeGoogle) -> None:
    """FR-NEW-013: Dan (RW in "Pneumo Été") sending the exact name gets ``Access denied.``; nothing changes."""
    before = pneumo.running.stored.activity()
    dan = signed_in(pneumo.running, fake_google, DAN)

    assert_access_denied(delete(dan, pneumo.folder_id, PNEUMO))

    assert_pneumo_intact(pneumo, before)


def test_an_unknown_folder_is_access_denied(pneumo: Pneumo) -> None:
    """DEC-023: an id of no folder is the same ``Access denied.`` as a forbidden one; nothing changes."""
    before = pneumo.running.stored.activity()

    assert_access_denied(delete(pneumo.admin, "0" * 32, PNEUMO))

    assert_pneumo_intact(pneumo, before)


@pytest.mark.parametrize("payload", [{"confirm": None}, {"confirm": ["Pneumo Été"]}, {}], ids=["null", "list", "none"])
def test_a_confirmation_that_is_not_a_string_is_an_invalid_body(pneumo: Pneumo, payload: dict[str, Any]) -> None:
    before = pneumo.running.stored.activity()

    reply = pneumo.admin.post_json(f"/api/folders/{pneumo.folder_id}/delete", payload)

    assert reply.status == 400, reply.status
    assert reply.json() == {"ok": False, "error": pages.INVALID_REQUEST_BODY}
    assert_pneumo_intact(pneumo, before)


def test_a_directory_that_cannot_be_removed_is_logged_and_the_folder_is_still_gone(
    pneumo: Pneumo, caplog: pytest.LogCaptureFixture
) -> None:
    """DEC-026: the rows go first; a state directory that cannot be removed is one warning, never an error answer."""
    history = pneumo.records / "history"
    history.chmod(0o500)  # its versions cannot be unlinked
    try:
        with caplog.at_level(logging.WARNING, logger="mcp_htmleditor.library.store"):
            reply = delete(pneumo.admin, pneumo.folder_id, PNEUMO)
    finally:
        history.chmod(0o700)

    assert_deleted(reply)
    assert home_names(pneumo.admin) == [CARDIOLOGY, WCBIP]
    assert not pneumo.deck.path.exists()
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert [record.getMessage() for record in warnings] == [
        "Could not remove a directory of a deleted folder: PermissionError"
    ]
