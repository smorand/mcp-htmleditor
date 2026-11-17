"""US-0136: storing a change of a presentation through ``POST /d/<pid>/content`` (SPEC-0025, DEC-003, DEC-028).

Spec tests: E2E-124, E2E-141, E2E-SEC-008 and the 50 MiB boundary. People sign in over HTTP through ``FakeGoogle``;
the second channel of every refusal is the stored file, its size and its history, never only the status line.
"""

from __future__ import annotations

import errno
import json
import os
import re
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

import pytest

from mcp_htmleditor import fileio
from mcp_htmleditor.http_server import MAX_SAVE_BYTES, SaveRefusal
from tests import library_support
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    HEART_FAILURE,
    PNEUMO,
    STATINS,
    Browser,
    FakeGoogle,
    Presentation,
    RunningLibrary,
    signed_in,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
HEART_FAILURE_BYTES = 2_097_152
DENIED = {"error": "Access denied.", "code": "denied"}


@dataclass(frozen=True)
class Edit:
    """The standard folders, "Heart Failure Update" (2 MiB, 3 slides) in Cardiology and Dan and Carol with the
    presentation opened (the grant cookie of each is in its browser)."""

    running: RunningLibrary
    ids: dict[str, str]
    heart: Presentation
    dan: Browser
    carol: Browser


@pytest.fixture
def edit(library_server: START, fake_google: FakeGoogle) -> Edit:
    running = library_server(fake_google)
    ids = running.builder.standard()
    heart = running.builder.presentation(
        ids[CARDIOLOGY], HEART_FAILURE, size=HEART_FAILURE_BYTES, modified=MODIFIED, slides=3
    )
    people = []
    for email in (DAN, CAROL):
        person = signed_in(running, fake_google, email)
        person.open_presentation(heart.id)
        people.append(person)
    return Edit(running, ids, heart, people[0], people[1])


def titled(heart: Presentation, title: str) -> str:
    """The stored deck with the title of slide 1 replaced, as a whole document."""
    text = heart.path.read_text(encoding="utf-8")
    return re.sub(r"(<h1[^>]*>)[^<]*(</h1>)", lambda m: f"{m[1]}{escape(title)}{m[2]}", text, count=1)


def text_of(person: Browser, heart: Presentation) -> str:
    """What the person is served for the content of the presentation."""
    return person.deck(heart.id, "content", x_editor="1").text


def test_e2e_sec_008_a_ro_member_stores_a_change_by_hand(edit: Edit) -> None:
    """E2E-SEC-008. Red before the fix because: the change is stored; the assertion "the title seen by Dan is Heart
    Failure Update" fails and shows HACKED. Carol sends, with her own grant and the headers of the editor's fetch,
    the full text with the title replaced by HACKED."""
    before = edit.heart.path.read_bytes()
    mtime = edit.heart.path.stat().st_mtime

    reply = edit.carol.save(edit.heart.id, titled(edit.heart, "HACKED"), base_mtime=mtime)

    assert reply.status == 403
    assert reply.json() == DENIED
    assert edit.heart.path.read_bytes() == before
    assert edit.heart.path.stat().st_size == HEART_FAILURE_BYTES
    assert edit.running.versions(edit.heart) == []
    seen = text_of(edit.dan, edit.heart)
    assert f">{HEART_FAILURE}</h1>" in seen
    assert "HACKED" not in seen
    assert edit.dan.save(edit.heart.id, titled(edit.heart, "Stored by Dan"), base_mtime=mtime).status == 200


def test_library_edit_a_rw_member_stores_and_the_previous_version_goes_to_the_history(edit: Edit) -> None:
    """Dan's save answers ``{"ok": true, "mtime"}``; Carol is served the new title and the previous bytes are the
    one history version."""
    before = edit.heart.path.read_bytes()
    mtime = edit.heart.path.stat().st_mtime

    reply = edit.dan.save(edit.heart.id, titled(edit.heart, "Heart Failure Update 2027"), base_mtime=mtime)

    assert reply.status == 200
    assert reply.json() == {"ok": True, "mtime": edit.heart.path.stat().st_mtime}
    assert ">Heart Failure Update 2027</h1>" in text_of(edit.carol, edit.heart)
    (version,) = edit.running.versions(edit.heart)
    assert version.reason == "browser-save"
    assert edit.running.version_text(edit.heart, version).encode() == before


def test_library_edit_the_administrator_stores_too_and_a_visitor_cannot(edit: Edit, fake_google: FakeGoogle) -> None:
    """The administrator holds EDIT in every folder; a browser with no grant is sent to the library, nothing stored."""
    admin = signed_in(edit.running, fake_google, ADMIN)
    admin.open_presentation(edit.heart.id)
    stranger = edit.running.browser()
    before = edit.heart.path.read_bytes()

    refused = stranger.save(edit.heart.id, titled(edit.heart, "HACKED"))
    stored = admin.save(edit.heart.id, titled(edit.heart, "By the administrator"))

    assert refused.status == 401
    assert refused.json()["code"] == "session_expired"
    assert stored.status == 200
    assert edit.heart.path.read_bytes() != before
    assert edit.running.stored.activity() == []  # a stored change is not an activity (FR-NEW-051)


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://evil.test"},
        {"Origin": ""},
        {"Sec-Fetch-Site": "cross-site"},
        {"Content-Type": "text/plain"},
    ],
    ids=["other-origin", "no-origin", "cross-site", "not-json"],
)
def test_library_edit_a_save_from_another_page_is_refused_and_stores_nothing(
    edit: Edit, headers: dict[str, str]
) -> None:
    """DEC-022: the origin rule and the JSON content type hold on the content origin, whatever the role; the
    second channel is the file bytes and the empty history."""
    before = edit.heart.path.read_bytes()
    sent = {**edit.dan.save_headers(edit.heart.id), **headers}
    sent = {name: value for name, value in sent.items() if value != ""}
    body = json.dumps({"html": titled(edit.heart, "HACKED")}).encode()

    reply = edit.running.client(edit.running.content_netloc).request(
        "POST", f"/d/{edit.heart.id}/content", headers=sent, body=body
    )

    assert reply.status == 403
    assert reply.json() == DENIED
    assert edit.heart.path.read_bytes() == before
    assert edit.running.versions(edit.heart) == []


def test_library_edit_a_conflict_stores_nothing_and_force_keeps_the_other_in_the_history(edit: Edit) -> None:
    """A stale ``base_mtime`` is 409 with the stored mtime and the file untouched; ``force`` stores and the other
    person's version is the history (reason ``keep-mine``)."""
    loaded = edit.heart.path.stat().st_mtime
    assert edit.carol is not None
    assert edit.dan.save(edit.heart.id, titled(edit.heart, "Statins A"), base_mtime=loaded).status == 200
    stored = edit.heart.path.read_bytes()

    conflict = edit.dan.save(edit.heart.id, titled(edit.heart, "Statins B"), base_mtime=loaded)

    assert conflict.status == 409
    assert conflict.json() == {"ok": False, "error": "File changed on disk", "mtime": edit.heart.path.stat().st_mtime}
    assert edit.heart.path.read_bytes() == stored
    forced = edit.dan.save(edit.heart.id, titled(edit.heart, "Statins B"), base_mtime=loaded, force=True)
    assert forced.status == 200
    assert ">Statins B</h1>" in edit.heart.path.read_text(encoding="utf-8")
    newest = edit.running.versions(edit.heart)[0]
    assert newest.reason == "keep-mine"
    assert edit.running.version_text(edit.heart, newest).encode() == stored


def test_library_edit_the_disk_full_is_an_operating_system_reason_and_the_file_is_not_truncated(
    edit: Edit, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-032: ``fileio.replace_file`` raises ENOSPC; the answer is 500 with the reason, no path in it, and the
    stored file is the old one, whole."""
    before = edit.heart.path.read_bytes()

    def full(_source: object, _target: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(fileio, "replace_file", full)
    reply = edit.dan.save(edit.heart.id, titled(edit.heart, "Not stored"))

    assert reply.status == 500
    assert reply.json() == {"error": "No space left on device"}
    assert str(edit.running.library_dir) not in reply.text
    assert edit.heart.path.read_bytes() == before


def test_library_edit_the_50_mebibyte_boundary_is_the_one_of_the_local_mode(edit: Edit) -> None:
    """A body of exactly 52 428 800 bytes is stored; one declaring 52 428 801 is 413 before any byte is read."""
    document = titled(edit.heart, "Big").replace("</body>", "<!----></body>", 1)
    padding = MAX_SAVE_BYTES - len(json.dumps({"html": document}).encode())
    big = document.replace("<!---->", f"<!--{'x' * padding}-->", 1)
    assert len(json.dumps({"html": big}).encode()) == MAX_SAVE_BYTES

    accepted = edit.dan.save(edit.heart.id, big)
    refused = edit.dan.send_save_length(edit.heart.id, MAX_SAVE_BYTES + 1)

    assert accepted.status == 200
    assert edit.heart.path.stat().st_size > HEART_FAILURE_BYTES
    assert refused.status == 413
    assert b"Request too large" in refused.body


def test_e2e_141_saves_are_not_recorded(edit: Edit, fake_google: FakeGoogle) -> None:
    """E2E-141: Dan stores 3 changes; the administrator's activity list has no line about them."""
    admin = signed_in(edit.running, fake_google, ADMIN)
    before = admin.open("/admin").activity_lines()
    for number in range(3):
        mtime = edit.heart.path.stat().st_mtime
        title = f"Heart Failure Update {number}"
        assert edit.dan.save(edit.heart.id, titled(edit.heart, title), base_mtime=mtime).status == 200
        os.utime(edit.heart.path, (mtime + 10, mtime + 10))  # a distinct mtime for the next base_mtime

    assert admin.open("/admin").activity_lines() == before
    assert edit.running.stored.activity() == []
    assert len(edit.running.versions(edit.heart)) == 3


def test_e2e_124_two_folders_each_hold_a_statins_review(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-124: each "Statins Review" opens its own folder's content; saving one leaves the other unchanged."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.member(ids[PNEUMO], DAN, "RW")
    first = running.builder.presentation(ids[CARDIOLOGY], STATINS, size=4_096, modified=MODIFIED, title="Cardio")
    second = running.builder.presentation(ids[PNEUMO], STATINS, size=4_096, modified=MODIFIED, title="Pneumo")
    dan = signed_in(running, fake_google, DAN)
    for presentation in (first, second):
        dan.open_presentation(presentation.id)
    other = second.path.read_bytes()

    assert ">Cardio</h1>" in text_of(dan, first)
    assert ">Pneumo</h1>" in text_of(dan, second)
    reply = dan.save(first.id, first.path.read_text(encoding="utf-8").replace(">Cardio<", ">Cardio 2027<", 1))

    assert reply.status == 200
    assert second.path.read_bytes() == other
    assert running.versions(second) == []
    assert len(running.versions(first)) == 1
    admin = signed_in(running, fake_google, ADMIN)
    names = [row[0] for row in admin.open(f"/f/{ids[CARDIOLOGY]}").presentation_rows()]
    assert names.count(STATINS) == 1
    assert first.id != second.id


def test_library_edit_a_save_that_lost_the_race_with_a_deletion_creates_nothing(edit: Edit) -> None:
    """DEC-028: the lock re-checks the row once it holds the lock; a deleted presentation is ``Access denied.`` and
    the lock is free again."""
    with edit.running.database.transaction(immediate=True) as connection:
        connection.execute("DELETE FROM presentations WHERE id = ?", (edit.heart.id,))
    handler = edit.running.server.save_lock(edit.heart.id)

    with pytest.raises(SaveRefusal) as refusal, handler:
        pass

    assert refusal.value.status == 403
    assert refusal.value.payload == DENIED
    assert edit.running.server.lock_for(edit.heart.id).acquire(timeout=1)


def test_library_edit_one_lock_per_presentation_serializes_two_saves(edit: Edit) -> None:
    """DEC-028: two saves of the same presentation never overlap; a save of another presentation does not wait."""
    other = edit.running.builder.presentation(edit.ids[CARDIOLOGY], STATINS, size=4_096, modified=MODIFIED)
    entered = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with edit.running.server.save_lock(edit.heart.id):
            entered.set()
            release.wait(10)

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(10)
    assert not edit.running.server.lock_for(edit.heart.id).acquire(timeout=0.2)
    assert edit.running.server.lock_for(other.id).acquire(timeout=1)
    edit.running.server.lock_for(other.id).release()
    release.set()
    thread.join(10)
    assert edit.running.server.lock_for(edit.heart.id).acquire(timeout=1)


def test_library_edit_an_unreadable_library_refuses_the_save_and_frees_the_lock(
    edit: Edit, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row re-check inside the lock fails with a database error: the save is refused with 503 and the library
    message, and the lock is free again."""

    def unreadable(_presentation_id: str) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(edit.running.server.library, "presentation", unreadable)

    with pytest.raises(SaveRefusal) as refusal, edit.running.server.save_lock(edit.heart.id):
        pass

    assert refusal.value.status == 503
    assert refusal.value.payload == {"error": "The library is unavailable. Try again later."}
    assert edit.running.server.lock_for(edit.heart.id).acquire(timeout=1)
