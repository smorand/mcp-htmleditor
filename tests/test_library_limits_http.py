"""US-0143: upload limits, interruption, storage failure and slots (SPEC-0025, DEC-033, DEC-054).

Spec tests: E2E-056, E2E-062, E2E-074, E2E-120, E2E-SEC-006, E2E-SEC-007, E2E-SEC-025. Bodies go over a raw socket read
by the main thread while a thread sends, as a browser does. The second channel is the library storage, the
administrator's list, the activity table and the free space of the library directory.
"""

from __future__ import annotations

import io
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from mcp_htmleditor.library import server as library_server_module
from tests import library_support
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    LAMYA,
    WCBIP,
    Browser,
    CountingReader,
    FakeGoogle,
    RunningLibrary,
    UploadPlan,
    disk_full,
    signed_in,
    valid_deck,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

LIMIT = 26_214_400
THIRTY_MB = 31_457_280
UPLOAD_FAILED = "The upload failed. Nothing was changed."
TOO_LARGE = "The file is larger than 25 MB."
NOT_DECLARED = "This file is not a valid presentation: the file is not declared as a presentation."
DENIED = "Access denied."


@dataclass(frozen=True)
class Library:
    running: RunningLibrary
    google: FakeGoogle
    ids: dict[str, str]
    dan: Browser
    carol: Browser

    @property
    def folder(self) -> str:
        return self.ids[CARDIOLOGY]

    def listed(self) -> list[str]:
        admin = signed_in(self.running, self.google, ADMIN)
        return [row[0] for row in admin.open(f"/f/{self.folder}").presentation_rows()]

    def storage(self) -> list[str]:
        return self.running.stored.entries()

    def stored_bytes(self) -> int:
        """Every byte of the stored presentations and their records: what an upload would take from the disk (the free
        space of a shared disk moves with other processes, and ``library.db`` grows with every sign in)."""
        return sum(
            entry.stat().st_size
            for root in (self.running.library_dir / "files", self.running.state_dir)
            for entry in root.rglob("*")
            if entry.is_file()
        )

    def lamya_is_quick(self) -> bool:
        """Lamya's folder page answers while an upload is in progress."""
        page = signed_in(self.running, self.google, LAMYA).open(f"/f/{self.ids[WCBIP]}")
        return page.status == 200


@pytest.fixture
def library(library_server: START, fake_google: FakeGoogle) -> Library:
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    return Library(
        running, fake_google, ids, signed_in(running, fake_google, DAN), signed_in(running, fake_google, CAROL)
    )


def padded(size: int) -> bytes:
    return valid_deck(3, size)


def test_e2e_056_a_file_one_byte_over_25_mb_is_refused(library: Library) -> None:
    storage, space = library.storage(), library.stored_bytes()

    streamed = library.dan.upload_streaming(library.folder, "Big Deck.html", padded(LIMIT + 1), UploadPlan(LIMIT + 1))

    assert streamed.reply is not None
    assert streamed.reply.status == 413
    assert streamed.reply.json() == {"ok": False, "error": TOO_LARGE}
    assert streamed.sent_when_answered < LIMIT  # the answer did not wait for the whole file
    assert "Big Deck" not in library.listed()
    assert library.storage() == storage
    assert library.stored_bytes() == space  # nothing of the 25 MB was kept


def test_e2e_062_a_file_of_exactly_25_mb_is_accepted(library: Library) -> None:
    streamed = library.dan.upload_streaming(library.folder, "Big Deck.html", padded(LIMIT), UploadPlan(LIMIT))

    assert streamed.reply is not None
    assert streamed.reply.status == 201
    assert streamed.reply.json()["message"] == "Uploaded Big Deck."
    admin = signed_in(library.running, library.google, ADMIN)
    rows = {row[0]: row[3] for row in admin.open(f"/f/{library.folder}").presentation_rows()}
    assert rows["Big Deck"] == "25.0 MB"


def test_e2e_074_a_library_that_cannot_store_the_file_says_so(library: Library) -> None:
    storage, lines = library.storage(), len(library.running.stored.activity())

    with disk_full():
        reply = library.dan.upload(library.folder, "Quarterly Review.html", valid_deck())

    assert reply.status == 500
    assert reply.json() == {"ok": False, "error": UPLOAD_FAILED}
    assert "Quarterly Review" not in library.listed()
    assert library.storage() == storage
    assert len(library.running.stored.activity()) == lines


def test_e2e_sec_006_a_ro_member_sends_a_30_mb_file(library: Library) -> None:
    """E2E-SEC-006. Red before the fix because: the whole 30 MB is received and stored; "the administrator lists 3
    presentations" fails. Carol is answered from the headers, before the sender is done."""
    storage = library.storage()

    streamed = library.carol.upload_streaming(library.folder, "Huge.html", padded(THIRTY_MB), UploadPlan(THIRTY_MB))

    assert streamed.reply is not None
    assert streamed.reply.status == 403
    assert DENIED in streamed.reply.body.decode()
    assert streamed.sent_when_answered < THIRTY_MB
    assert len(library.listed()) == 3
    assert library.storage() == storage
    assert library.lamya_is_quick()


def test_e2e_sec_007_a_rw_member_sends_a_30_mb_file(library: Library) -> None:
    """E2E-SEC-007. Red before the fix because: the 30 MB presentation is stored; "no Huge listed" fails."""
    storage, space = library.storage(), library.stored_bytes()

    streamed = library.dan.upload_streaming(library.folder, "Huge.html", padded(THIRTY_MB), UploadPlan(THIRTY_MB))

    assert streamed.reply is not None
    assert streamed.reply.status == 413
    assert streamed.reply.json()["error"] == TOO_LARGE
    assert len(library.listed()) == 3
    assert "Huge" not in library.listed()
    assert library.storage() == storage
    assert library.stored_bytes() == space
    assert library.lamya_is_quick()


def test_e2e_sec_025_an_upload_that_announces_100_bytes_and_sends_30_mb(
    library: Library, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E-SEC-025. Red before the fix because: the extra bytes are read and stored; "only the declared 100 bytes are
    read and the connection is closed" fails. The counter wraps ``rfile``: head bytes plus exactly 100."""
    counts: list[int] = []
    original = library_server_module.LibraryHandler.setup

    def counting_setup(self: library_server_module.LibraryHandler) -> None:
        original(self)
        counts.clear()
        self.rfile = CountingReader(self.rfile, counts)  # type: ignore[assignment] - a reader that counts

    monkeypatch.setattr(library_server_module.LibraryHandler, "setup", counting_setup)
    storage = library.storage()

    streamed = library.dan.upload_streaming(library.folder, "Huge.html", b"x" * THIRTY_MB, UploadPlan(100))

    assert streamed.reply is not None
    assert streamed.reply.status == 400
    assert streamed.reply.json() == {"ok": False, "error": NOT_DECLARED}
    request_head = 600  # an upper bound of the request line and the headers sent by the helper
    assert 100 <= sum(counts) <= request_head + 100, sum(counts)
    assert len(library.listed()) == 3
    assert library.storage() == storage
    assert library.lamya_is_quick()


def test_e2e_sec_025_without_a_declared_length_the_chunked_body_is_cut_at_26214401_bytes(library: Library) -> None:
    storage = library.storage()

    streamed = library.dan.upload_streaming(library.folder, "Huge.html", b"x" * THIRTY_MB, UploadPlan(chunked=True))

    assert streamed.reply is not None
    assert streamed.reply.status == 413
    assert streamed.reply.json()["error"] == TOO_LARGE
    assert streamed.sent_when_answered < THIRTY_MB
    assert library.storage() == storage


def test_a_chunked_body_is_stored_when_it_is_valid_and_refused_with_a_length_or_elsewhere(library: Library) -> None:
    ok = library.dan.upload_streaming(library.folder, "Chunked.html", valid_deck(), UploadPlan(chunked=True))
    assert ok.reply is not None
    assert ok.reply.status == 201
    assert "Chunked" in library.listed()
    # every other route and any other value still gets the inherited refusal of Transfer-Encoding
    refused = library.running.client().request(
        "POST",
        "/api/folders",
        headers={"Origin": library.running.origin, "Transfer-Encoding": "chunked", "Content-Type": "application/json"},
        body=b"0\r\n\r\n",
    )
    assert refused.status in {400, 403}
    assert (
        library.dan.upload_streaming(
            library.folder, "Both.html", valid_deck(), UploadPlan(declared=5, chunked=True)
        ).reply
        is not None
    )
    assert "Both" not in library.listed()


def test_no_length_and_no_encoding_is_an_empty_body(library: Library) -> None:
    streamed = library.dan.upload_streaming(library.folder, "Nothing.html", b"", UploadPlan())
    assert streamed.reply is not None
    assert streamed.reply.json() == {"ok": False, "error": NOT_DECLARED}


def test_a_connection_cut_in_the_body_leaves_nothing(library: Library) -> None:
    storage, lines = library.storage(), len(library.running.stored.activity())
    body = padded(2_000_000)

    library.dan.upload_streaming(library.folder, "Cut Deck.html", body, UploadPlan(len(body), cut_at=800_000))

    assert "Cut Deck" not in library.listed()
    assert library.storage() == storage
    assert len(library.running.stored.activity()) == lines


def test_e2e_120_a_right_removed_during_an_upload_stops_it(library: Library) -> None:
    """E2E-120: the administrator removes Dan at 50 percent; at the end of the body "Access denied." and nothing."""
    storage, lines = library.storage(), len(library.running.stored.activity())
    body = padded(2_000_000)
    paused, resume = threading.Event(), threading.Event()
    results: list[library_support.Streamed] = []
    plan = UploadPlan(len(body), pause_at=len(body) // 2, paused=paused, resume=resume)
    sender = threading.Thread(
        target=lambda: results.append(library.dan.upload_streaming(library.folder, "Big Deck.html", body, plan))
    )
    sender.start()
    assert paused.wait(20)

    admin = signed_in(library.running, library.google, ADMIN)
    assert admin.remove_member(library.folder, DAN).status == 200
    resume.set()
    sender.join(30)

    (streamed,) = results
    assert streamed.reply is not None
    assert streamed.reply.status == 403
    assert DENIED in streamed.reply.body.decode()
    assert "Big Deck" not in library.listed()
    assert library.storage() == storage
    assert len(library.running.stored.activity()) == lines + 1  # only the removal of the member


def test_a_fifth_concurrent_upload_is_refused_without_waiting(library: Library) -> None:
    """DEC-033: four uploads are received at once; the fifth gets 503 at once and the four complete afterwards."""
    body = padded(500_000)
    held = [(threading.Event(), threading.Event()) for _ in range(4)]
    results: list[library_support.Streamed] = []

    def send(name: str, pause: tuple[threading.Event, threading.Event]) -> None:
        plan = UploadPlan(len(body), pause_at=100_000, paused=pause[0], resume=pause[1])
        results.append(library.dan.upload_streaming(library.folder, name, body, plan))

    threads = [threading.Thread(target=send, args=(f"Held {n}.html", pause)) for n, pause in enumerate(held)]
    for thread in threads:
        thread.start()
    for paused, _ in held:
        assert paused.wait(20)
    slots = library.running.server.upload_slots
    deadline = time.monotonic() + 20  # the sender paused after sending: wait until the server holds the four slots
    while slots._value > 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert slots._value == 0

    fifth = library.dan.upload_streaming(library.folder, "Fifth.html", body, UploadPlan(len(body)))
    for _, resume in held:
        resume.set()
    for thread in threads:
        thread.join(30)

    assert fifth.reply is not None
    assert fifth.reply.status == 503
    assert fifth.reply.json() == {"ok": False, "error": UPLOAD_FAILED}
    assert sorted(r.reply.status for r in results if r.reply is not None) == [201, 201, 201, 201]
    assert "Fifth" not in library.listed()
    assert library.running.server.upload_slots.acquire(blocking=False)  # every slot was given back
    library.running.server.upload_slots.release()


def test_the_length_header_is_checked_before_anything_is_read(library: Library) -> None:
    for bad in ("-5", "1e3", "abc", "99999999999999999999"):
        reply = library.dan.upload(
            library.folder,
            "",
            b"",
            headers={
                "Origin": library.running.origin,
                "Sec-Fetch-Site": "same-origin",
                "X-File-Name": "Bad.html",
                "Content-Length": bad,
            },
        )
        assert reply.status in {400, 413}, bad
    assert "Bad" not in library.listed()


def decode(raw: bytes, limit: int = 1_000) -> bytes:
    from mcp_htmleditor.library.uploads import read_chunked

    stream = io.BytesIO(raw)
    return read_chunked(stream.readline, stream.read, limit)


def test_read_chunked_decodes_chunks_extensions_and_trailers() -> None:
    assert decode(b"5\r\nhello\r\n6;ext=1\r\n world\r\n0\r\nX-Trailer: 1\r\n\r\n") == b"hello world"
    assert decode(b"0\r\n\r\n") == b""


def test_read_chunked_stops_at_the_limit_without_reading_further() -> None:
    assert decode(b"a\r\n0123456789\r\na\r\n0123456789\r\n0\r\n\r\n", limit=15) == b"012345678901234"


@pytest.mark.parametrize(
    "raw",
    [
        b"zz\r\nhello\r\n0\r\n\r\n",  # not hexadecimal
        b"-5\r\nhello\r\n0\r\n\r\n",  # negative size
        b"5" + b"0" * 40 + b"\r\nhello\r\n",  # a size line above 32 bytes
        b"5\r\nhelloXX0\r\n\r\n",  # no line end after the chunk
        b"5\r\nhello\r\n0\r\n" + b"X: " + b"a" * 9_000 + b"\r\n\r\n",  # trailers above 8 KiB
        b"5\r\nhel",  # the body ends inside a chunk
    ],
    ids=["hex", "negative", "long-line", "no-crlf", "trailers", "short"],
)
def test_read_chunked_refuses_a_body_it_cannot_read(raw: bytes) -> None:
    from mcp_htmleditor.library.uploads import UploadRefused

    with pytest.raises(UploadRefused):
        decode(raw)
