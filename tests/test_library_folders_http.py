"""US-0129: the folder page lists presentations (SPEC-0025).

Spec tests: E2E-009, E2E-019, E2E-022, E2E-023, E2E-024, E2E-028, E2E-037, E2E-122, E2E-168. Presentations are
generated decks of exact byte counts with exact modified times (``LibraryBuilder.presentation``); people sign in
through ``FakeGoogle``; pages are read over HTTP. The refusal test that is not a mock: the bytes of the page for a
missing folder and for a folder of another team are identical.
"""

from __future__ import annotations

import html
import re
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from mcp_htmleditor.library import pages
from mcp_htmleditor.library.access import Role
from mcp_htmleditor.library.store import PresentationView
from tests import library_support
from tests.library_support import (
    ADMIN,
    ARRHYTHMIA,
    BOB,
    BRIDGING,
    CARDIOLOGY,
    CAROL,
    CHALLENGES,
    DAN,
    HEART_FAILURE,
    LAMYA,
    PNEUMO,
    STATINS,
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
DAY = 86_400
SESSION_SECONDS = 2_592_000  # 30 days, DEC-017
READY_SECONDS = 2.0  # FR-NEW-060
LINK_BYTES_PER_SECOND = 50_000_000 / 8  # the 50 megabit per second connection of FR-NEW-060
EMPTY_FOLDER = "This folder has no presentations yet."
LIBRARY_UNAVAILABLE = "The library is unavailable. Try again later."
BACK_LINK = '<a href="/">All folders</a>'
SIGN_OUT_FORM = '<form method="post" action="/auth/logout"><button type="submit">Sign out</button></form>'
CARDIOLOGY_ROWS = [
    (ARRHYTHMIA, "2026-11-12T16:40:00Z", "12 Nov 2026 16:40", "512.0 KB"),
    (STATINS, "2026-11-12T16:40:00Z", "12 Nov 2026 16:40", "1.5 MB"),
    (HEART_FAILURE, "2026-11-10T09:15:00Z", "10 Nov 2026 09:15", "2.0 MB"),
]
FOLDER_NAMES = (WCBIP, CARDIOLOGY, PNEUMO)
PRESENTATION_NAMES = (CHALLENGES, BRIDGING, HEART_FAILURE, ARRHYTHMIA, STATINS)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
ADDRESS = re.compile(r'(?:href|action|src)="([^"]*)"')


def signed_in(running: RunningLibrary, google: FakeGoogle, email: str) -> tuple[Browser, LibraryReply]:
    browser = running.browser()
    return browser, browser.sign_in(google, email)


def standard_library(running: RunningLibrary) -> dict[str, str]:
    """The standard library of spec section 9, its five presentations included; returns folder name to id."""
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    return ids


def visible_texts(reply: LibraryReply) -> list[str]:
    """The text nodes of the page body, unescaped, in order."""
    body = reply.text.split("<body>", 1)[1]
    return [html.unescape(text).strip() for text in re.split(r"<[^>]*>", body) if text.strip()]


def rows(reply: LibraryReply) -> list[tuple[str, str, str, str]]:
    """The presentation rows, names unescaped."""
    return [(html.unescape(name), *rest) for name, *rest in reply.presentation_rows()]


def missing_folder() -> str:
    """The link to a folder that does not exist ("Oncology 2030"): a well formed id no row holds."""
    return f"/f/{secrets.token_hex(16)}"


def assert_access_denied(reply: LibraryReply) -> None:
    """Exactly the one refusal page: the text and the Sign out button, nothing else (DEC-023)."""
    assert (reply.status, reply.body) == (403, pages.access_denied())
    assert visible_texts(reply) == ["Access denied.", "Sign out"]


def assert_folder_page(reply: LibraryReply, name: str) -> None:
    assert reply.status == 200, reply.status
    assert f"<h1>{html.escape(name)}</h1>" in reply.text
    assert BACK_LINK in reply.text and SIGN_OUT_FORM in reply.text


# ---------------------------------------------------------------------------
# E2E-009 and FR-NEW-009: a direct link followed while signed out
# ---------------------------------------------------------------------------


def test_e2e_009_a_session_older_than_30_days_sends_the_person_to_the_sign_in_page(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-009: 30 days 1 minute after Lamya signed in, her folder link is the sign in page; signing in again opens
    the folder, with a new session of exactly 30 days from now."""
    running = library_server(fake_google)
    ids = standard_library(running)
    browser, _ = signed_in(running, fake_google, LAMYA)
    link = f"/f/{ids[WCBIP]}"
    running.clock.advance(SESSION_SECONDS + MINUTE)

    refused = browser.open(link)

    assert (refused.status, refused.body) == (200, pages.sign_in_page(link, None))
    assert WCBIP not in refused.text and CHALLENGES not in refused.text
    fake_google.choose(LAMYA)
    start = re.search(r'href="(/auth/start\?[^"]*)"', refused.text)
    assert start is not None
    folder = browser.open(html.unescape(start.group(1)))
    assert urlsplit(browser.url).path == link
    assert_folder_page(folder, WCBIP)
    assert [row[0] for row in rows(folder)] == [BRIDGING, CHALLENGES]
    new_sessions = [row for row in running.stored.sessions() if row[2] == running.clock()]
    assert [(email, expires - created) for _, email, created, expires in new_sessions] == [(LAMYA, SESSION_SECONDS)]


def test_a_direct_link_followed_while_signed_out_gives_access_denied_to_an_account_without_a_role(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-009: Bob follows the Cardiology link, signs in, lands on the link and gets only ``Access denied.``."""
    running = library_server(fake_google)
    ids = standard_library(running)
    link = f"/f/{ids[CARDIOLOGY]}"
    browser = running.browser()

    reply = browser.sign_in(fake_google, BOB, destination=link)

    assert urlsplit(browser.url).path == link
    assert_access_denied(reply)


# ---------------------------------------------------------------------------
# E2E-019: the library cannot be read while a folder page is open
# ---------------------------------------------------------------------------


def test_e2e_019_an_unreadable_library_on_a_folder_page_shows_no_partial_list(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-019: the refresh says the library is unavailable, with none of the three names; once readable, the same
    three rows with their sizes."""
    running = library_server(fake_google)
    ids = standard_library(running)
    dan, _ = signed_in(running, fake_google, DAN)
    before = dan.open(f"/f/{ids[CARDIOLOGY]}")
    assert rows(before) == CARDIOLOGY_ROWS

    with running.unreadable_database():
        during = dan.open(f"/f/{ids[CARDIOLOGY]}")

    assert during.status == 503
    assert visible_texts(during) == ["Slides", LIBRARY_UNAVAILABLE]
    assert not any(name in during.text for name in (CARDIOLOGY, HEART_FAILURE, ARRHYTHMIA, STATINS))
    after = dan.open(f"/f/{ids[CARDIOLOGY]}")
    assert (after.status, rows(after)) == (200, CARDIOLOGY_ROWS)


def test_a_presentation_file_that_cannot_be_read_gives_the_unavailable_page(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-062: a row whose file is gone is not a partial list: the whole page is the unavailable message."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    decks = running.builder.standard_presentations(ids)
    dan, _ = signed_in(running, fake_google, DAN)
    aside = decks[STATINS].path.with_suffix(".aside")
    decks[STATINS].path.replace(aside)
    try:
        reply = dan.open(f"/f/{ids[CARDIOLOGY]}")
    finally:
        aside.replace(decks[STATINS].path)

    assert reply.status == 503
    assert visible_texts(reply) == ["Slides", LIBRARY_UNAVAILABLE]
    assert rows(dan.open(f"/f/{ids[CARDIOLOGY]}")) == CARDIOLOGY_ROWS


def test_a_presentation_row_with_a_malformed_id_gives_the_unavailable_page(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-062: a damaged row (an id that is not 32 hex digits) is an unreadable library, not a crash."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    with running.database.transaction(immediate=True) as connection:
        connection.execute(
            "INSERT INTO presentations(id, folder_id, name, name_key, created_at) VALUES (?, ?, ?, ?, ?)",
            ("../../etc/passwd", ids[CARDIOLOGY], "Damaged", "damaged", 0.0),
        )
    dan, _ = signed_in(running, fake_google, DAN)

    reply = dan.open(f"/f/{ids[CARDIOLOGY]}")

    assert reply.status == 503
    assert visible_texts(reply) == ["Slides", LIBRARY_UNAVAILABLE]


# ---------------------------------------------------------------------------
# E2E-022: an empty folder
# ---------------------------------------------------------------------------


def test_e2e_022_an_empty_folder_says_so(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-022: the administrator opens "Pneumo Été": the message and the way back, no list nor table."""
    running = library_server(fake_google)
    ids = standard_library(running)
    admin, _ = signed_in(running, fake_google, ADMIN)

    reply = admin.open(f"/f/{ids[PNEUMO]}")

    assert_folder_page(reply, PNEUMO)
    assert f"<p>{EMPTY_FOLDER}</p>" in reply.text
    assert visible_texts(reply) == ["All folders", PNEUMO, EMPTY_FOLDER, "Sign out"]
    assert not re.search(r"<(?:ul|ol|li|table|thead|th|tr|time)[\s>]", reply.text)


# ---------------------------------------------------------------------------
# E2E-023, E2E-024, E2E-037: refusals
# ---------------------------------------------------------------------------


def test_e2e_023_a_folder_that_does_not_exist_is_refused(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-023: Dan, and the administrator too, get only ``Access denied.`` and ``Sign out`` for a missing folder."""
    running = library_server(fake_google)
    standard_library(running)
    dan, _ = signed_in(running, fake_google, DAN)
    admin, _ = signed_in(running, fake_google, ADMIN)

    for browser in (dan, admin):
        reply = browser.open(missing_folder())
        assert_access_denied(reply)


def test_e2e_024_a_folder_the_person_cannot_enter_gives_the_same_page_as_a_missing_one(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-024: Carol's answers for WCBIP, for a missing folder and for a malformed id are identical on the wire:
    status, headers except the date, body; none names a folder, a presentation or a member."""
    running = library_server(fake_google)
    ids = standard_library(running)
    carol, _ = signed_in(running, fake_google, CAROL)

    forbidden = carol.open(f"/f/{ids[WCBIP]}")
    missing = carol.open(missing_folder())
    malformed = carol.open("/f/Oncology%202030")

    for reply in (forbidden, missing, malformed):
        assert_access_denied(reply)
        assert {name: value for name, value in reply.headers.items() if name != "date"} == {
            name: value for name, value in forbidden.headers.items() if name != "date"
        }
        assert reply.body == forbidden.body
        assert not any(name in reply.text for name in (*FOLDER_NAMES, *PRESENTATION_NAMES))
        assert not EMAIL.search(reply.text)
    assert carol.open(f"/f/{ids[CARDIOLOGY]}").status == 200


def test_e2e_037_a_rw_member_cannot_enter_a_folder_where_they_hold_no_role(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-037, FR-NEW-021: Dan, RW in Cardiology and RO in Pneumo Été, is refused WCBIP; no name of it shows."""
    running = library_server(fake_google)
    ids = standard_library(running)
    running.builder.member(ids[PNEUMO], DAN, "RO")
    dan, _ = signed_in(running, fake_google, DAN)

    reply = dan.open(f"/f/{ids[WCBIP]}")

    assert_access_denied(reply)
    assert not any(name in reply.text for name in (WCBIP, CHALLENGES, BRIDGING))
    assert running.server.library.role_in(DAN, ids[WCBIP]) is None
    assert running.server.library.role_in(DAN, ids[CARDIOLOGY]) is Role.RW


# ---------------------------------------------------------------------------
# E2E-122: each member sees only their own folders
# ---------------------------------------------------------------------------


def reachable_pages(browser: Browser) -> dict[str, LibraryReply]:
    """Every library page reachable by following the links of the home page, by address."""
    seen: dict[str, LibraryReply] = {}
    queue = ["/"]
    while queue:
        address = queue.pop(0)
        if address in seen:
            continue
        reply = seen[address] = browser.open(address)
        queue.extend(
            link
            for link in ADDRESS.findall(reply.text)
            if link.startswith("/") and not link.startswith(("/lib/", "/open/"))  # /open/ leaves the library pages
        )
    return seen


def test_e2e_122_each_member_sees_only_their_own_folders(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-122: Dan sees Cardiology and Pneumo Été, Carol Cardiology, Lamya WCBIP; no page they reach shows a folder
    or presentation of another, nor any email address."""
    running = library_server(fake_google)
    ids = standard_library(running)
    running.builder.member(ids[PNEUMO], DAN, "RO")
    expected = {
        DAN: ({CARDIOLOGY, PNEUMO}, {HEART_FAILURE, ARRHYTHMIA, STATINS}),
        CAROL: ({CARDIOLOGY}, {HEART_FAILURE, ARRHYTHMIA, STATINS}),
        LAMYA: ({WCBIP}, {CHALLENGES, BRIDGING}),
    }

    for email, (own_folders, own_presentations) in expected.items():
        browser, home = signed_in(running, fake_google, email)
        assert {html.unescape(name) for _, name, _ in home.folder_rows()} == own_folders, email
        visited = reachable_pages(browser)
        assert set(visited) == {"/", "/auth/logout", *(f"/f/{ids[name]}" for name in own_folders)}, email
        shown = {name for reply in visited.values() for name, *_ in rows(reply)}
        assert shown == own_presentations, email
        for address, reply in visited.items():
            text = html.unescape(reply.text)
            assert not EMAIL.search(text), (email, address)
            for name in (*FOLDER_NAMES, *PRESENTATION_NAMES):
                if name not in own_folders | own_presentations:
                    assert name not in text, (email, address, name)
            for name in set(FOLDER_NAMES) - own_folders:
                assert ids[name] not in reply.text, (email, address, name)


# ---------------------------------------------------------------------------
# E2E-028, E2E-168 and the order rule: sizes, many rows, same minute
# ---------------------------------------------------------------------------


def test_e2e_028_sizes_are_shown_in_bytes_kb_and_mb(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-028: 1, 900, 1 023, 1 024, 1 048 576 and 26 214 400 bytes; the files hold exactly those counts."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    sizes = {1: "1 byte", 900: "900 bytes", 1_023: "1023 bytes", 1_024: "1.0 KB", 1_048_576: "1.0 MB"}
    sizes[26_214_400] = "25.0 MB"
    start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
    for rank, size in enumerate(sizes):  # one minute apart, the smallest newest
        deck = running.builder.presentation(
            ids[CARDIOLOGY], f"Size {size}", size=size, modified=start - timedelta(minutes=rank)
        )
        assert deck.path.stat().st_size == size
    dan, _ = signed_in(running, fake_google, DAN)

    reply = dan.open(f"/f/{ids[CARDIOLOGY]}")

    assert [(name, size) for name, _, _, size in rows(reply)] == [
        (f"Size {count}", text) for count, text in sizes.items()
    ]


def test_e2e_168_a_folder_of_100_presentations_lists_within_2_seconds(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-168: Deck 001 to Deck 100, newest first, each with its name, date and size; the answer plus its transfer
    on a 50 megabit per second link stays under 2 seconds."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
    for number in range(1, 101):
        running.builder.presentation(
            ids[CARDIOLOGY], f"Deck {number:03d}", size=2_048, modified=start + timedelta(minutes=number)
        )
    carol, _ = signed_in(running, fake_google, CAROL)

    started = time.monotonic()
    reply = carol.open(f"/f/{ids[CARDIOLOGY]}")
    elapsed = time.monotonic() - started + len(reply.body) / LINK_BYTES_PER_SECOND

    assert elapsed < READY_SECONDS, elapsed
    expected = [
        (
            f"Deck {number:03d}",
            (start + timedelta(minutes=number)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            f"1 Nov 2026 {8 + number // 60:02d}:{number % 60:02d}",
            "2.0 KB",
        )
        for number in range(100, 0, -1)
    ]
    assert rows(reply) == expected


def test_rows_of_the_same_minute_follow_the_name_order_and_stay_stable(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-018: the minute decides first (seconds ignored), then accents and case ignored, then the exact name;
    the order is the same at every display."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    minute = datetime(2026, 11, 12, 16, 40, tzinfo=UTC)
    for name, offset in (
        ("beta", 59),
        ("aardvark", -1),
        ("Éclair", 30),
        ("Zulu", 60),
        ("Alpha", 0),
        ("Eclair", 10),
    ):
        running.builder.presentation(ids[CARDIOLOGY], name, size=500, modified=minute + timedelta(seconds=offset))
    dan, _ = signed_in(running, fake_google, DAN)

    first = rows(dan.open(f"/f/{ids[CARDIOLOGY]}"))
    second = rows(dan.open(f"/f/{ids[CARDIOLOGY]}"))

    assert [name for name, *_ in first] == ["Zulu", "Alpha", "beta", "Eclair", "Éclair", "aardvark"]
    assert second == first
    assert [fallback for _, _, fallback, _ in first[1:5]] == ["12 Nov 2026 16:40"] * 4


def test_the_minute_of_a_time_before_1970_is_rounded_down(library_server: START, fake_google: FakeGoogle) -> None:
    """FR-NEW-018: 61 s and 60.5 s before the epoch are the same minute (from 120 s before), so the name decides;
    truncating toward zero would put the second in the next minute."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    running.builder.presentation(ids[CARDIOLOGY], "Alpha", size=500, modified=epoch - timedelta(seconds=61))
    running.builder.presentation(ids[CARDIOLOGY], "Beta", size=500, modified=epoch - timedelta(seconds=60.5))
    dan, _ = signed_in(running, fake_google, DAN)

    shown = rows(dan.open(f"/f/{ids[CARDIOLOGY]}"))

    assert [name for name, *_ in shown] == ["Alpha", "Beta"]


# ---------------------------------------------------------------------------
# Story tests: the page itself, escaping, the storage paths
# ---------------------------------------------------------------------------


def test_the_folder_page_escapes_every_name_and_loads_the_library_script() -> None:
    """DEC-029: names through ``esc``; DEC-031: ``<time datetime>`` in UTC with the UTC text as fallback."""
    hostile = '"><script>alert(1)</script>'
    row = PresentationView(id="a" * 32, name=hostile, modified=1_794_501_659.9, size=1_076)

    page = pages.folder_page(hostile, [row]).decode()

    assert "<script>alert" not in page
    assert page.count("&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;") == 2
    assert '<time datetime="2026-11-12T16:40:59Z">12 Nov 2026 16:40</time>' in page
    assert '<span class="size">1.1 KB</span>' in page
    assert '<script src="/lib/library.js" defer></script>' in page
    assert pages.access_denied().count(b'<script src="/lib/library.js" defer></script>') == 1


def test_a_presentation_path_is_built_only_from_two_ids(library_server: START) -> None:
    """DEC-025: ``files/<folder id>/<presentation id>.html``; any other value is refused before a path exists."""
    running = library_server()
    library = running.server.library
    folder_id, presentation_id = "0" * 32, "f" * 32

    assert library.presentation_path(folder_id, presentation_id) == (
        running.library_dir / "files" / folder_id / f"{presentation_id}.html"
    )
    for bad in ("../" + "0" * 29, "A" * 32, "0" * 31, "0" * 33, "0" * 32 + "\n", ""):
        for arguments in ((bad, presentation_id), (folder_id, bad)):
            try:
                library.presentation_path(*arguments)
            except ValueError:
                continue
            raise AssertionError(f"accepted {arguments!r}")
