"""US-0144: a same name upload asks, and Replace replaces (SPEC-0025, DEC-027, DEC-028, DEC-035).

Spec tests: E2E-068, E2E-069, E2E-070, E2E-073, E2E-078, E2E-162. The second channel of every check is the stored file
(bytes and ``sha256``), its history, its request record and the activity table, read from disk.
"""

from __future__ import annotations

import hashlib
import html
import threading
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from mcp_htmleditor.request_service import RequestService
from mcp_htmleditor.request_store import RequestStore
from tests import library_support
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    DAN,
    STATINS,
    Browser,
    FakeGoogle,
    LibraryReply,
    Presentation,
    RunningLibrary,
    UploadPlan,
    disk_full,
    signed_in,
    valid_deck,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

STATINS_BYTES = 1_572_864
QUESTION = 'A presentation named "Statins Review" already exists. Replace it?'
UPLOAD_FAILED = "The upload failed. Nothing was changed."
NOT_ALLOWED = "This file name is not allowed."
NO_SLIDE = "This file is not a valid presentation: the file has no slide."


@dataclass(frozen=True)
class Library:
    running: RunningLibrary
    google: FakeGoogle
    ids: dict[str, str]
    statins: Presentation
    dan: Browser

    @property
    def folder(self) -> str:
        return self.ids[CARDIOLOGY]

    def listed(self) -> list[str]:
        admin = signed_in(self.running, self.google, ADMIN)
        return [html.unescape(row[0]) for row in admin.open(f"/f/{self.folder}").presentation_rows()]

    def lines(self) -> list[str]:
        return [row[2] for row in signed_in(self.running, self.google, ADMIN).open("/admin").activity_lines()]

    def digest(self) -> str:
        return hashlib.sha256(self.statins.path.read_bytes()).hexdigest()

    def requests(self) -> list[str]:
        snapshot = RequestService(RequestStore(self.running.state_dir)).snapshot(self.statins.path)
        return [request.instruction for request in snapshot.requests]


@pytest.fixture
def library(library_server: START, fake_google: FakeGoogle) -> Library:
    running = library_server(fake_google)
    ids = running.builder.standard()
    decks = running.builder.standard_presentations(ids)
    return Library(running, fake_google, ids, decks[STATINS], signed_in(running, fake_google, DAN))


def answered(reply: LibraryReply, status: int, **fields: object) -> None:
    assert reply.status == status, reply.text
    assert {key: reply.json()[key] for key in fields} == fields


def test_a_same_name_upload_asks_and_stores_nothing(library: Library) -> None:
    digest, lines = library.digest(), library.lines()

    reply = library.dan.upload(library.folder, "statins review.HTML", valid_deck(2, 307_200))

    answered(reply, 409, ok=False, collision=STATINS)
    assert library.digest() == digest
    assert library.running.versions(library.statins) == []
    assert library.lines() == lines
    assert library.listed().count(STATINS) == 1


def test_replace_swaps_the_content_keeps_the_name_the_history_and_the_requests(library: Library) -> None:
    """The independent test: the stored bytes are the new file, one history version equals the old bytes with reason
    ``replace``, the request record is unchanged, and the line is ``Replaced``."""
    old = library.statins.path.read_bytes()
    new = valid_deck(2, 307_200)
    service = RequestService(RequestStore(library.running.state_dir))
    service.queue(library.statins.path, "Shorten the title", None)
    service.write_review(
        library.statins.path, [{"id": "s1", "slide": None, "title": "Fewer words", "why": "Dense", "change": "Cut"}]
    )

    reply = library.dan.upload(library.folder, "statins review.HTML", new, replace=True)

    answered(reply, 201, ok=True, name=STATINS, message=f"Uploaded {STATINS}.")
    assert library.statins.path.read_bytes() == new
    (version,) = library.running.versions(library.statins)
    assert (version.reason, version.bytes) == ("replace", STATINS_BYTES)
    assert library.running.version_text(library.statins, version).encode() == old
    assert library.requests() == ["Shorten the title"]
    assert [item.id for item in service.snapshot(library.statins.path).suggestions] == ["s1"]
    assert library.lines()[0] == f'Replaced "{STATINS}" in "{CARDIOLOGY}"'
    assert library.listed().count(STATINS) == 1
    assert len(library.listed()) == 3


def test_a_second_identical_replace_makes_no_second_version_and_no_second_line(library: Library) -> None:
    new = valid_deck(2, 307_200)
    library.dan.upload(library.folder, "Statins Review.html", new, replace=True)
    lines = library.lines()

    again = library.dan.upload(library.folder, "Statins Review.html", new, replace=True)

    answered(again, 201, message=f"Uploaded {STATINS}.")
    assert len(library.running.versions(library.statins)) == 1
    assert library.lines() == lines


def test_replace_with_a_name_that_no_longer_exists_adds_it_as_new(library: Library) -> None:
    reply = library.dan.upload(library.folder, "Brand New.html", valid_deck(), replace=True)
    answered(reply, 201, name="Brand New")
    assert library.lines()[0] == f'Uploaded "Brand New" in "{CARDIOLOGY}"'


def test_e2e_068_a_validation_message_wins_over_the_question(library: Library) -> None:
    digest = library.digest()
    empty = b'<!DOCTYPE html><html data-doc-type="presentation"><body></body></html>'

    reply = library.dan.upload(library.folder, "Statins Review.html", empty)

    answered(reply, 400, ok=False, error=NO_SLIDE)
    assert "collision" not in reply.json()
    assert library.digest() == digest


def test_e2e_069_names_that_differ_by_an_accent_are_different(library: Library) -> None:
    first = library.dan.upload(library.folder, "Cafe Study.html", valid_deck())
    second = library.dan.upload(library.folder, "Café Study.html", valid_deck())

    answered(first, 201, message="Uploaded Cafe Study.")
    answered(second, 201, message="Uploaded Café Study.")
    assert {"Cafe Study", "Café Study"} <= set(library.listed())


def test_e2e_070_two_uploads_of_the_same_new_name_leave_one_presentation(
    library: Library, fake_google: FakeGoogle
) -> None:
    admin = signed_in(library.running, fake_google, ADMIN)
    replies: list[LibraryReply] = []
    start = threading.Barrier(2)
    first_deck, second_deck = valid_deck(3, 400_000), valid_deck(2, 300_000)

    def send(person: Browser, data: bytes) -> None:
        start.wait(10)
        replies.append(person.upload(library.folder, "Lipids Update.html", data))

    threads = [
        threading.Thread(target=send, args=(library.dan, first_deck)),
        threading.Thread(target=send, args=(admin, second_deck)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)

    assert sorted(reply.status for reply in replies) == [201, 409]
    (collision,) = [reply for reply in replies if reply.status == 409]
    assert collision.json() == {"ok": False, "collision": "Lipids Update"}
    assert library.listed().count("Lipids Update") == 1
    stored = [e for e in library.running.stored.entries() if e.endswith(".html")]
    assert len(stored) == 5 + 1  # the five standard presentations plus one new file, never two
    assert not [e for e in library.running.stored.entries() if ".tmp" in e]


def test_e2e_073_an_interrupted_replacement_keeps_the_previous_version(library: Library) -> None:
    digest, lines = library.digest(), library.lines()
    body = valid_deck(2, 1_000_000)

    library.dan.upload_streaming(
        library.folder, "Statins Review.html", body, UploadPlan(len(body), cut_at=700_000, replace=True)
    )

    assert library.statins.path.stat().st_size == STATINS_BYTES
    assert library.digest() == digest
    assert library.running.versions(library.statins) == []
    assert library.lines() == lines
    assert not [e for e in library.running.stored.entries() if ".tmp" in e]


def test_e2e_078_a_replacement_that_cannot_be_stored_keeps_the_previous_version(library: Library) -> None:
    digest, lines = library.digest(), library.lines()

    with disk_full():
        reply = library.dan.upload(library.folder, "Statins Review.html", valid_deck(2), replace=True)

    answered(reply, 500, ok=False, error=UPLOAD_FAILED)
    assert library.digest() == digest
    assert library.running.versions(library.statins) == []
    assert library.lines() == lines


def test_a_reader_only_ever_sees_the_complete_old_or_the_complete_new_file(library: Library) -> None:
    """FR-NEW-063: while the replacement runs, every sample of the stored file hashes to the old or the new bytes."""
    old, new = library.statins.path.read_bytes(), valid_deck(3, 3_000_000)
    allowed = {hashlib.sha256(old).hexdigest(), hashlib.sha256(new).hexdigest()}
    seen: set[str] = set()
    stop = threading.Event()

    def read() -> None:
        while not stop.is_set():
            seen.add(hashlib.sha256(library.statins.path.read_bytes()).hexdigest())

    reader = threading.Thread(target=read)
    reader.start()
    try:
        reply = library.dan.upload(library.folder, "Statins Review.html", new, replace=True)
    finally:
        stop.set()
        reader.join(10)

    assert reply.status == 201
    assert seen <= allowed
    assert hashlib.sha256(new).hexdigest() in {library.digest()}


def test_e2e_162_file_names_composed_form_100_characters_and_edge_spaces(library: Library) -> None:
    library.dan.upload(library.folder, "Café Study.html", valid_deck())  # the é as one letter
    hundred, hundred_one = "A" * 100, "A" * 101

    decomposed = library.dan.upload(library.folder, "Cafe\u0301 Study.html", valid_deck())
    long_name = library.dan.upload(library.folder, f"{hundred}.html", valid_deck())

    answered(decomposed, 409, collision="Café Study")
    answered(long_name, 201, message=f"Uploaded {hundred}.")
    for name in (f"{hundred_one}.html", " Lead.html", "Tail .html", "   .html"):
        answered(library.dan.upload(library.folder, name, valid_deck()), 400, error=NOT_ALLOWED)
    listed = library.listed()
    assert listed.count("Café Study") == 1
    assert hundred in listed
    assert len(listed) == 3 + 2
