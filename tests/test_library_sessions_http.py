"""US-0128: exact 30 day sessions, restarts, the unavailable library, 200 folders (SPEC-0025).

Spec tests: E2E-008, E2E-012, E2E-016, E2E-166. Time is a ``FakeClock`` handed to the server (DEC-032); the
unreadable library is ``Database.connect_hook`` raising ``sqlite3.OperationalError`` and, without any seam, a
corrupted ``library.db`` swapped in and out; the restart is a second ``LibraryServer`` on the same directory and port.
The session rows are read directly from ``library.db``, never through the product.
"""

from __future__ import annotations

import html
import re
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_htmleditor.library import pages, server
from mcp_htmleditor.library.store import Database, Library
from tests import library_support
from tests.library_support import (
    BOB,
    CARDIOLOGY,
    CAROL,
    DAN,
    LAMYA,
    PNEUMO,
    WCBIP,
    Browser,
    FakeGoogle,
    LibraryReply,
    RunningLibrary,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MINUTE = 60
HOUR = 3_600
DAY = 86_400
SESSION_SECONDS = 2_592_000  # 30 days, DEC-017
LIBRARY_UNAVAILABLE = "The library is unavailable. Try again later."
READY_SECONDS = 2.0  # FR-NEW-060
SIGN_OUT = "Sign out"
LIBRARY_DIR = Path(server.__file__).parent
# Every way a module could read the wall clock itself instead of the injected one.
WALL_CLOCK_CALL = re.compile(r"\b(?:time\.(?:time|time_ns|monotonic)|datetime\.(?:now|utcnow|today)|date\.today)\(")


def signed_in(running: RunningLibrary, google: FakeGoogle, email: str) -> tuple[Browser, LibraryReply]:
    browser = running.browser()
    return browser, browser.sign_in(google, email)


def folder_names(reply: LibraryReply) -> list[str]:
    return [html.unescape(name) for _, name, _ in reply.folder_rows()]


def is_sign_in_page(reply: LibraryReply) -> bool:
    """The page a visitor gets for the home address: the person is treated as signed out."""
    return (reply.status, reply.body) == (200, pages.sign_in_page("/", None))


def session_of(running: RunningLibrary, email: str) -> tuple[float, float]:
    """``(created_at, expires_at)`` of the one session row of ``email``, read from the table."""
    rows = [(created, expires) for _, owner, created, expires in running.stored.sessions() if owner == email]
    assert len(rows) == 1, rows
    return rows[0]


def assert_library_unavailable(reply: LibraryReply, *hidden: str) -> None:
    """The one unavailable page: 503, the message, no list, no Sign out form, none of the ``hidden`` names."""
    assert reply.status == 503, reply.status
    assert LIBRARY_UNAVAILABLE in reply.text
    assert not re.search(r"<(?:li|ul)[\s>]", reply.text)
    assert SIGN_OUT not in reply.text and "<form" not in reply.text
    for name in hidden:
        assert html.escape(name) not in reply.text and name not in reply.text, name


# ---------------------------------------------------------------------------
# E2E-008, E2E-012: exactly 30 days from the sign in
# ---------------------------------------------------------------------------


def test_e2e_008_a_session_of_29_days_23_hours_is_still_valid_after_closing_the_browser(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-008: the reopened browser reaches the home page with no Google step; the period still ends at 30 days."""
    running = library_server(fake_google)
    running.builder.standard()
    browser, first_home = signed_in(running, fake_google, LAMYA)
    assert WCBIP in folder_names(first_home)
    signed_in_at = running.clock()
    authorize_calls = len(fake_google.requests_to("/authorize"))

    running.clock.advance(29 * DAY + 23 * HOUR)
    reopened = browser.reopened()
    reply = reopened.open("/")

    assert set(reopened.cookies) == {"lib"}  # the browser id cookie lived only as long as the window
    assert reply.status == 200
    assert folder_names(reply) == [WCBIP]
    assert reopened.hosts_visited() == {running.library_netloc}
    assert len(fake_google.requests_to("/authorize")) == authorize_calls
    assert reply.set_cookies == ()  # the cookie is not issued again: nothing moves the end
    created_at, expires_at = session_of(running, LAMYA)
    assert (created_at, expires_at - running.clock()) == (signed_in_at, HOUR)

    running.clock.advance(HOUR)
    assert is_sign_in_page(reopened.open("/"))


def test_e2e_012_the_30_day_limit_is_exact_and_never_extended_by_use(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-012: Dan at 29 d 23 h 59 min still in, Carol at 30 d 1 min out; one minute later Dan is out too."""
    running = library_server(fake_google)
    running.builder.standard()
    carol, _ = signed_in(running, fake_google, CAROL)
    carol_signed_in_at = running.clock()
    running.clock.advance(2 * MINUTE)
    dan, _ = signed_in(running, fake_google, DAN)
    dan_signed_in_at = running.clock()

    for day in range(1, 30):  # both use the library every day; Carol's last use is yesterday
        running.clock.advance(DAY)
        assert folder_names(dan.open("/")) == [CARDIOLOGY], day
        assert folder_names(carol.open("/")) == [CARDIOLOGY], day
    running.clock.advance(DAY - MINUTE)

    assert running.clock() - dan_signed_in_at == 30 * DAY - MINUTE
    assert running.clock() - carol_signed_in_at == 30 * DAY + MINUTE
    dan_home, carol_home = dan.open("/"), carol.open("/")
    assert (dan_home.status, folder_names(dan_home)) == (200, [CARDIOLOGY])
    assert is_sign_in_page(carol_home)
    for email, signed_in_at in ((DAN, dan_signed_in_at), (CAROL, carol_signed_in_at)):
        assert session_of(running, email) == (signed_in_at, signed_in_at + SESSION_SECONDS), email

    running.clock.advance(MINUTE)
    assert is_sign_in_page(dan.open("/"))


def test_signing_in_again_starts_a_new_period_of_30_days(library_server: START, fake_google: FakeGoogle) -> None:
    """FR-NEW-005 business rule: a new sign in is a new row ending 30 days after it; the old row keeps its end."""
    running = library_server(fake_google)
    running.builder.standard()
    first, _ = signed_in(running, fake_google, LAMYA)
    first_start = running.clock()
    running.clock.advance(20 * DAY)
    second, _ = signed_in(running, fake_google, LAMYA)
    second_start = running.clock()

    ends = sorted(expires for _, owner, _, expires in running.stored.sessions() if owner == LAMYA)

    assert ends == [first_start + SESSION_SECONDS, second_start + SESSION_SECONDS]
    running.clock.advance(10 * DAY)
    assert is_sign_in_page(first.open("/"))
    assert folder_names(second.open("/")) == [WCBIP]


# ---------------------------------------------------------------------------
# E2E-166: a restart keeps sessions and folders
# ---------------------------------------------------------------------------


def test_e2e_166_a_signed_in_person_stays_signed_in_after_a_restart(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-166: ten days after the sign in the product restarts; the session ends 20 days later, not 30."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    browser, before = signed_in(running, fake_google, LAMYA)
    signed_in_at = running.clock()
    authorize_calls = len(fake_google.requests_to("/authorize"))
    running.clock.advance(10 * DAY)
    old_server, port = running.server, running.port

    running.restart()
    reply = browser.reopened().open("/")

    assert running.server is not old_server and running.port == port
    assert reply.status == 200
    assert reply.folder_rows() == before.folder_rows() and reply.folder_rows()[0][0] == ids[WCBIP]
    assert len(fake_google.requests_to("/authorize")) == authorize_calls
    _, expires_at = session_of(running, LAMYA)
    assert expires_at - running.clock() == 20 * DAY
    assert expires_at == signed_in_at + SESSION_SECONDS
    running.clock.advance(20 * DAY - MINUTE)
    assert folder_names(browser.open("/")) == [WCBIP]
    running.clock.advance(MINUTE)
    assert is_sign_in_page(browser.open("/"))


# ---------------------------------------------------------------------------
# E2E-016: the stored library cannot be read
# ---------------------------------------------------------------------------


def test_e2e_016_the_stored_library_cannot_be_read(
    library_server: START, fake_google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E-016: 200 folders; while the library is unreadable the one message, no name; then everything is back."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    dan, _ = signed_in(running, fake_google, DAN)
    running.builder.member(ids[PNEUMO], DAN, "RW")
    running.builder.numbered_folders(197, DAN, "RO")
    assert running.stored.rows("SELECT count(*) FROM folders") == [(200,)]
    before = dan.open("/")
    assert len(before.folder_rows()) == 199
    stored_before = (running.stored.sessions(), running.stored.rows("SELECT * FROM members ORDER BY folder_id"))
    attempts: list[int] = []

    def unreadable() -> None:
        attempts.append(1)
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(Database, "connect_hook", unreadable, raising=False)
    during = dan.open("/")

    assert attempts, "the request never opened the library"
    assert_library_unavailable(during, CARDIOLOGY, PNEUMO, "Folder 001", "Folder 197")

    monkeypatch.setattr(Database, "connect_hook", None, raising=False)
    after = dan.open("/")

    assert after.status == 200
    assert after.folder_rows() == before.folder_rows()
    assert {CARDIOLOGY, PNEUMO} <= set(folder_names(after))
    assert (running.stored.sessions(), running.stored.rows("SELECT * FROM members ORDER BY folder_id")) == stored_before


def test_a_corrupted_library_file_gives_the_message_and_its_return_restores_everything(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """No seam: ``library.db`` replaced by junk then put back; home and sign in both say unavailable, no restart."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    dan, before = signed_in(running, fake_google, DAN)
    visitor = running.browser()
    authorize_calls = len(fake_google.requests_to("/authorize"))

    with running.unreadable_database():
        home = dan.open("/")
        sign_in = visitor.open("/auth/start", follow=False)

    assert_library_unavailable(home, CARDIOLOGY, ids[CARDIOLOGY])
    assert_library_unavailable(sign_in)
    assert "location" not in sign_in.headers
    assert len(fake_google.requests_to("/authorize")) == authorize_calls
    after = dan.open("/")
    assert (after.status, after.folder_rows()) == (200, before.folder_rows())
    assert running.stored.folder_names() == sorted([CARDIOLOGY, PNEUMO, WCBIP])


def test_the_unavailable_page_holds_only_the_message() -> None:
    """``pages.library_unavailable``: the title, the alert and the stylesheet; no list, form or link."""
    page = pages.library_unavailable().decode()

    assert f'<p role="alert">{LIBRARY_UNAVAILABLE}</p>' in page
    assert re.sub(r"<[^>]*>", " ", page.split("<body>", 1)[1]).split() == ["Slides", *LIBRARY_UNAVAILABLE.split()]
    assert "<a " not in page and "<form" not in page


# ---------------------------------------------------------------------------
# FR-NEW-060: 200 folders (keyboard and names: E2E-017 in test_library_folders_e2e.py)
# ---------------------------------------------------------------------------


def test_the_home_page_with_200_folders_answers_within_2_seconds_from_one_query(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-060, DEC-052: every row present within the bound; ``folders_for`` runs one statement, not one per row."""
    running = library_server(fake_google)
    ids = running.builder.numbered_folders(200, DAN, "RW")
    dan, _ = signed_in(running, fake_google, DAN)

    started = time.monotonic()
    reply = dan.open("/")
    elapsed = time.monotonic() - started

    assert elapsed < READY_SECONDS, elapsed  # the spec bound: a tighter one flaked at high load (US-0128 review)
    assert {folder_id for folder_id, _, _ in reply.folder_rows()} == set(ids.values())
    statements: list[str] = []
    running.database.connection().set_trace_callback(statements.append)
    try:
        assert len(Library(running.database, running.clock, state_dir=running.state_dir).folders_for(DAN)) == 200
        assert (
            len(
                Library(running.database, running.clock, state_dir=running.state_dir).folders_for(
                    "seb.morand@gmail.com"
                )
            )
            == 200
        )
    finally:
        running.database.connection().set_trace_callback(None)
    assert len(statements) == 2, statements


# ---------------------------------------------------------------------------
# Purge (design: rows kept one day after their end) and the clock rule
# ---------------------------------------------------------------------------


def test_an_ended_session_row_is_purged_one_day_after_its_end_at_the_next_sign_in(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """``Accounts.purge`` at ``begin_login`` and ``finish_login``: a row is kept until exactly one day after its end;
    a live session (Bob, signed in two days before) is never touched and still opens the library."""
    running = library_server(fake_google)
    running.builder.standard()
    signed_in(running, fake_google, CAROL)
    running.clock.advance(1)
    signed_in(running, fake_google, LAMYA)
    _, lamya_end = session_of(running, LAMYA)
    running.clock.advance(lamya_end - DAY - running.clock())  # nobody has ended yet: Bob's sign in purges nothing
    bob, _ = signed_in(running, fake_google, BOB)
    running.clock.advance(lamya_end + DAY - running.clock())  # Carol ended a day and a second ago, Lamya a day ago

    fake_google.choose(DAN)
    dan = running.browser()
    to_google = dan.open("/auth/start", follow=False)
    after_begin = {owner for _, owner, _, _ in running.stored.sessions()}
    running.clock.advance(1)
    dan.open(to_google.headers["location"])

    assert after_begin == {LAMYA, BOB}
    assert {owner for _, owner, _, _ in running.stored.sessions()} == {BOB, DAN}
    assert bob.open("/").body == pages.access_denied()  # signed in (no role), not sent to the sign in page


def test_no_library_module_reads_the_wall_clock_or_updates_a_session() -> None:
    """DEC-017, DEC-032: the clock is injected (only ``server.py``'s default names ``time.time``); no ``UPDATE
    sessions`` anywhere, so nothing can move an end."""
    sources = {path.name: path.read_text(encoding="utf-8") for path in sorted(LIBRARY_DIR.glob("*.py"))}
    assert "server.py" in sources and "signin.py" in sources

    for name, source in sources.items():
        assert not WALL_CLOCK_CALL.search(source), name
        assert not re.search(r"\bfrom\s+(?:time|datetime)\s+import\b", source), name
        assert not re.search(r"UPDATE\s+sessions", source, re.IGNORECASE), name
    mentions = [
        (name, line.strip()) for name, source in sources.items() for line in source.splitlines() if "time.time" in line
    ]
    assert mentions == [
        ("server.py", "def __init__(self, settings: Settings, *, clock: Callable[[], float] = time.time) -> None:")
    ]
