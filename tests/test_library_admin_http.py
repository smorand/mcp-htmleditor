"""US-0130: administration, folder creation and the activity list over HTTP (SPEC-0025).

Spec tests: E2E-038, E2E-086, E2E-091 to E2E-095, E2E-098, E2E-139, E2E-142, E2E-163, E2E-SEC-011, E2E-SEC-018.
People sign in through ``FakeGoogle``; ``Browser.post_json`` sends what ``library.js`` sends. The second channel of
every refusal is the operator view (``folders`` and ``activity`` tables read directly) plus the administrator's own
home page.
"""

from __future__ import annotations

import html
import re
import socket
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from typing import Any

import pytest

from mcp_htmleditor.library import pages
from mcp_htmleditor.library.access import Role
from mcp_htmleditor.library.store import ActivityLine, FolderView
from tests import library_support
from tests.library_support import (
    ADMIN,
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

CREATE_PATH = "/api/folders"
ADMIN_PATH = "/admin"
ACTIVITY_LINK = "/admin#activity"  # the Activity section of the administration page
NAME_REFUSED = "Folder names use 1 to 60 letters, digits, spaces or hyphens."
NO_ACTIVITY = "No activity yet."
NO_PRESENTATION = "This folder has no presentations yet."
ONCOLOGY = "Oncology 2030"
STANDARD_NAMES = [CARDIOLOGY, PNEUMO, WCBIP]  # the home page order of the standard library
ACTIVITY_LIMIT = 500
CREATED_AT_CLOCK_START = "2001-09-09T01:46:40Z"  # library_support.CLOCK_START in UTC
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def signed_in(running: RunningLibrary, google: FakeGoogle, email: str) -> Browser:
    browser = running.browser()
    browser.sign_in(google, email)
    return browser


def create(browser: Browser, name: Any) -> LibraryReply:
    """What the ``Create folder`` button sends for the text typed in ``Folder name``."""
    return browser.post_json(CREATE_PATH, {"name": name})


def duplicate(name: str) -> str:
    return f'A folder named "{name}" already exists.'


def home_names(browser: Browser) -> list[str]:
    """The folder names of the person's home page, unescaped, in page order."""
    return [html.unescape(name) for _, name, _ in browser.open("/").folder_rows()]


def visible_texts(reply: LibraryReply) -> list[str]:
    """The text nodes of the page body, unescaped, in order."""
    body = reply.text.split("<body>", 1)[1]
    return [html.unescape(text).strip() for text in re.split(r"<[^>]*>", body) if text.strip()]


def assert_access_denied(reply: LibraryReply) -> None:
    """Exactly the one refusal page: the text and the Sign out button, nothing else (DEC-023)."""
    assert (reply.status, reply.body) == (403, pages.access_denied())
    assert visible_texts(reply) == ["Access denied.", "Sign out"]


def assert_refused(reply: LibraryReply, error: str) -> None:
    assert (reply.status, reply.headers.get("content-type")) == (400, "application/json"), reply.text
    assert reply.json() == {"ok": False, "error": error}


def stored_folders(running: RunningLibrary) -> list[tuple[Any, ...]]:
    """``(id, name, name_key)`` of every folder row, read directly."""
    return running.stored.rows("SELECT id, name, name_key FROM folders ORDER BY id")


def activity_count(running: RunningLibrary) -> int:
    return len(running.stored.activity())


# ---------------------------------------------------------------------------
# E2E-038, E2E-086, E2E-139: nobody but the administrator
# ---------------------------------------------------------------------------


def test_e2e_038_a_rw_member_has_no_administration(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-038: Dan's home page has no Administration entry; the link he was told about shows ``Access denied.``
    and no folder, member or activity line."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    assert create(admin, ONCOLOGY).status == 201  # an activity line exists that could leak
    dan = signed_in(running, fake_google, DAN)

    home = dan.open("/")
    administration = dan.open(ADMIN_PATH)

    assert "Administration" not in home.text and ADMIN_PATH not in home.text
    assert_access_denied(administration)
    for leak in (*STANDARD_NAMES, ONCOLOGY, "Created folder", "Activity", "Folders"):
        assert leak not in administration.text, leak
    assert not EMAIL.search(administration.text)


def test_e2e_086_rw_and_ro_members_are_refused_the_administration(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-086: Dan (RW) and Carol (RO) each get ``Access denied.`` for the administration and the activity links;
    neither home page shows Administration."""
    running = library_server(fake_google)
    running.builder.standard()

    for email in (DAN, CAROL):
        browser = signed_in(running, fake_google, email)
        for link in (ADMIN_PATH, ACTIVITY_LINK):
            assert_access_denied(browser.open(link))
        assert "Administration" not in browser.open("/").text, email


def test_e2e_139_a_member_cannot_read_the_activity_list(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-139: Dan asks for the activity list: ``Access denied.``, no line; the administrator still reads it."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    create(admin, ONCOLOGY)
    dan = signed_in(running, fake_google, DAN)

    reply = dan.open(ACTIVITY_LINK)

    assert_access_denied(reply)
    assert reply.activity_lines() == [] and "Created folder" not in reply.text
    assert [text for _, _, text in admin.open(ACTIVITY_LINK).activity_lines()] == [f'Created folder "{ONCOLOGY}"']


# ---------------------------------------------------------------------------
# E2E-091 to E2E-095, E2E-098, E2E-163: creating a folder
# ---------------------------------------------------------------------------


def test_e2e_091_the_administrator_creates_a_folder(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-091: "  Oncology 2030  " is trimmed and listed among 4 folders; it is empty, has no member, and the
    activity list gains ``Created folder "Oncology 2030"`` by the administrator, now."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)

    reply = create(admin, "  Oncology 2030  ")

    assert reply.status == 201 and reply.headers["content-type"] == "application/json"
    folder_id = reply.json()["id"]
    assert reply.json() == {"ok": True, "id": folder_id}
    assert home_names(admin) == [CARDIOLOGY, ONCOLOGY, PNEUMO, WCBIP]
    folder_page = admin.open(f"/f/{folder_id}")
    assert folder_page.status == 200 and NO_PRESENTATION in folder_page.text
    assert running.stored.rows(f"SELECT * FROM members WHERE folder_id = '{folder_id}'") == []  # noqa: S608
    assert running.stored.rows(f"SELECT name FROM folders WHERE id = '{folder_id}'") == [(ONCOLOGY,)]  # noqa: S608
    lines = admin.open(ADMIN_PATH).activity_lines()
    assert lines == [(CREATED_AT_CLOCK_START, ADMIN, f'Created folder "{ONCOLOGY}"')]
    assert NAME_REFUSED not in reply.text and "already exists" not in reply.text


def test_the_actor_of_a_line_is_the_lower_case_address_whatever_google_returned(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-049: Google returns ``Seb.Morand@Gmail.COM``; the line's actor is ``seb.morand@gmail.com``."""
    running = library_server(fake_google)
    admin = signed_in(running, fake_google, "Seb.Morand@Gmail.COM")

    assert create(admin, ONCOLOGY).status == 201

    assert running.stored.rows("SELECT at, actor, text FROM activity") == [
        (running.clock(), ADMIN, f'Created folder "{ONCOLOGY}"')
    ]


def test_e2e_092_a_folder_name_that_exists_without_regard_to_case_is_refused(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-092: "cardiology 2027" is refused with its own spelling in the message; still 3 folders."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    before = stored_folders(running)

    assert_refused(create(admin, "cardiology 2027"), duplicate("cardiology 2027"))

    assert home_names(admin) == STANDARD_NAMES
    assert stored_folders(running) == before and activity_count(running) == 0


@pytest.mark.parametrize("name", ["", "   "], ids=["empty", "three-spaces"])
def test_e2e_093_an_empty_or_blank_folder_name_is_refused(
    library_server: START, fake_google: FakeGoogle, name: str
) -> None:
    """E2E-093: an empty name and 3 spaces get the name rule; still 3 folders."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)

    assert_refused(create(admin, name), NAME_REFUSED)

    assert home_names(admin) == STANDARD_NAMES
    assert activity_count(running) == 0


def test_e2e_094_a_folder_name_of_61_characters_is_refused(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-094: 61 letters "A" get the name rule; no folder added."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    before = stored_folders(running)

    assert_refused(create(admin, "A" * 61), NAME_REFUSED)

    assert stored_folders(running) == before and activity_count(running) == 0


def test_e2e_095_emoji_and_symbols_in_a_folder_name_are_refused(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-095: each of the five names gets the name rule; still 3 folders, no activity line."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)

    for name in ("Pneumo \U0001fac1", "Cardio/Rhythm", "Cardio_2027", "R&D", "Study.2027"):
        assert_refused(create(admin, name), NAME_REFUSED)

    assert home_names(admin) == STANDARD_NAMES
    assert activity_count(running) == 0


def test_e2e_098_duplicate_checks_ignore_case_and_surrounding_spaces_but_not_accents(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-098: "  CARDIOLOGY 2027 " is a duplicate named as typed, trimmed; "Pneumo Ete" is a new folder."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)

    assert_refused(create(admin, "  CARDIOLOGY 2027 "), duplicate("CARDIOLOGY 2027"))
    assert create(admin, "Pneumo Ete").status == 201

    assert home_names(admin) == [CARDIOLOGY, "Pneumo Ete", PNEUMO, WCBIP]


def test_e2e_163_folder_names_are_composed_and_counted_after_composition(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-163: "Pneumo \u00c9t\u00e9" typed with separate marks is a duplicate; 60 "\u00e9" written as e plus a mark
    are created under the composed name; 61 such letters get the name rule."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    composed = "\u00e9" * 60

    assert_refused(create(admin, "Pneumo E\u0301te\u0301"), duplicate(PNEUMO))
    assert create(admin, "e\u0301" * 60).status == 201
    assert_refused(create(admin, "e\u0301" * 61), NAME_REFUSED)

    assert home_names(admin) == [CARDIOLOGY, composed, PNEUMO, WCBIP]
    added = [row for row in stored_folders(running) if row[1] not in STANDARD_NAMES]
    assert [(name, key) for _, name, key in added] == [(composed, composed)]


# ---------------------------------------------------------------------------
# E2E-142, FR-NEW-050, FR-NEW-051: the activity list
# ---------------------------------------------------------------------------


def test_e2e_142_only_the_500_latest_lines_are_shown(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-142: 500 stored lines then one creation: 500 lines newest first, "Folder 501" to "Folder 002"; the table
    keeps 500."""
    running = library_server(fake_google)
    admin = signed_in(running, fake_google, ADMIN)
    with closing(sqlite3.connect(running.stored.library_dir / "library.db")) as connection, connection:
        connection.executemany(
            "INSERT INTO activity(at, actor, text) VALUES (?, ?, ?)",
            [(running.clock(), ADMIN, f'Created folder "Folder {number:03d}"') for number in range(1, 501)],
        )

    assert create(admin, "Folder 501").status == 201

    texts = [text for _, _, text in admin.open(ADMIN_PATH).activity_lines()]
    assert len(texts) == ACTIVITY_LIMIT
    assert texts[0] == 'Created folder "Folder 501"' and texts[-1] == 'Created folder "Folder 002"'
    assert texts == [f'Created folder "Folder {number:03d}"' for number in range(501, 1, -1)]
    assert activity_count(running) == ACTIVITY_LIMIT
    assert not running.stored.rows("SELECT id FROM activity WHERE text LIKE '%Folder 001%'")


def test_two_administrators_creating_the_same_name_get_one_folder_and_one_line(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """DEC-030: two sessions create "Twin" at once; one 201, one 400, one row, one activity line."""
    running = library_server(fake_google)
    first = signed_in(running, fake_google, ADMIN)
    second = signed_in(running, fake_google, ADMIN)
    barrier = threading.Barrier(2)
    statuses: list[int] = []

    def attempt(browser: Browser) -> None:
        barrier.wait(timeout=10)
        statuses.append(create(browser, "Twin").status)

    threads = [threading.Thread(target=attempt, args=(browser,)) for browser in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(statuses) == [201, 400]
    assert running.stored.rows("SELECT name FROM folders") == [("Twin",)]
    assert [row[3] for row in running.stored.activity()] == ['Created folder "Twin"']


def test_a_refused_oversized_body_closes_the_connection(library_server: START, fake_google: FakeGoogle) -> None:
    """The 413 is sent without reading the body: the same connection must not parse it as a second request."""
    running = library_server(fake_google)
    admin = signed_in(running, fake_google, ADMIN)
    cookie = "; ".join(f"{name}={value}" for name, value in admin.cookies.items())
    smuggled = b"GET /admin HTTP/1.1\r\nHost: " + running.library_netloc.encode() + b"\r\n\r\n"
    head = (
        f"POST {CREATE_PATH} HTTP/1.1\r\nHost: {running.library_netloc}\r\nCookie: {cookie}\r\n"
        f"Origin: {running.origin}\r\nSec-Fetch-Site: same-origin\r\nContent-Type: application/json\r\n"
        f"Content-Length: {70_000 + len(smuggled)}\r\n\r\n"
    ).encode()

    with socket.create_connection(("127.0.0.1", running.port), timeout=10) as connection:
        connection.sendall(head + smuggled)
        received = b""
        while chunk := connection.recv(65_536):
            received += chunk

    assert received.startswith(b"HTTP/1.0 413") or received.startswith(b"HTTP/1.1 413")
    assert received.count(b"HTTP/1.") == 1  # one answer, then the server closed (recv returned b"")


def test_sign_ins_and_refusals_write_no_activity_line(library_server: START, fake_google: FakeGoogle) -> None:
    """FR-NEW-050, FR-NEW-051: signing in, a refused name, a duplicate and a member's attempt record nothing; the
    list reads ``No activity yet.``."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    dan = signed_in(running, fake_google, DAN)

    create(admin, "R&D")
    create(admin, CARDIOLOGY)
    create(dan, ONCOLOGY)

    page = admin.open(ADMIN_PATH)
    assert activity_count(running) == 0
    assert page.activity_lines() == [] and f"<p>{NO_ACTIVITY}</p>" in page.text


def test_the_administration_page_names_its_controls(library_server: START, fake_google: FakeGoogle) -> None:
    """FR-NEW-067: All folders, the Folders section with every folder in home page order, the field Folder name and
    its Create folder button, the Activity section, Sign out."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)

    page = admin.open(ADMIN_PATH)

    assert page.status == 200 and page.headers["content-security-policy"].startswith("default-src 'none'; script")
    assert visible_texts(page) == [
        "All folders",
        "Administration",
        "Folders",
        CARDIOLOGY,
        "Admin",
        PNEUMO,
        "Admin",
        WCBIP,
        "Admin",
        "Folder name",
        "Create folder",
        "Activity",
        NO_ACTIVITY,
        "Sign out",
    ]
    assert '<label for="folder-name">Folder name</label>' in page.text
    assert '<input id="folder-name" name="name" type="text" autocomplete="off">' in page.text
    assert '<a href="/">All folders</a>' in page.text and '<section id="activity">' in page.text


def test_the_administration_page_escapes_names_addresses_and_lines() -> None:
    """DEC-029: every dynamic value of the page goes through ``esc``."""
    folder = FolderView(id="a" * 32, name="<b>Bold</b>", role=Role.ADMIN)
    line = ActivityLine(at=0.0, actor="<i>@example.org", text='Created folder "<script>"')

    page = pages.admin_page([folder], [line]).decode()

    assert "<b>" not in page and "<i>" not in page and "<script>" not in page
    assert "&lt;b&gt;Bold&lt;/b&gt;" in page and "&lt;i&gt;@example.org" in page
    assert "Created folder &quot;&lt;script&gt;&quot;" in page
    assert '<time datetime="1970-01-01T00:00:00Z">1 Jan 1970 00:00</time>' in page


# ---------------------------------------------------------------------------
# DEC-019, DEC-022: order of the checks and the body
# ---------------------------------------------------------------------------


def test_the_permission_is_checked_before_the_body_is_read_or_the_name_checked(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """DEC-019: Dan gets ``Access denied.`` for an invalid name, a body that is not JSON and an oversized body,
    where the administrator gets the name rule, 400 and 413."""
    running = library_server(fake_google)
    running.builder.standard()
    dan = signed_in(running, fake_google, DAN)
    admin = signed_in(running, fake_google, ADMIN)
    oversized = b'{"name": "' + b"x" * 70_000 + b'"}'

    for payload in ({"name": ""}, b"not json", oversized):
        assert_access_denied(dan.post_json(CREATE_PATH, payload))

    assert_refused(admin.post_json(CREATE_PATH, {"name": ""}), NAME_REFUSED)
    assert admin.post_json(CREATE_PATH, oversized).status == 413
    assert len(stored_folders(running)) == 3 and activity_count(running) == 0


@pytest.mark.parametrize(
    "payload",
    [b"not json", b"[]", b'"Oncology 2030"', b'{"name": 2030}', b"{}", b"", b'{"name": "\xff"}'],
    ids=["not-json", "list", "string", "number-name", "no-name", "empty-body", "not-utf8"],
)
def test_a_body_that_is_not_a_name_object_is_refused_and_changes_nothing(
    library_server: START, fake_google: FakeGoogle, payload: bytes
) -> None:
    """The administrator's malformed bodies are ``400 Invalid request body``; no folder, no line."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    before = stored_folders(running)

    assert_refused(admin.post_json(CREATE_PATH, payload), "Invalid request body")

    assert stored_folders(running) == before and activity_count(running) == 0


@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x", None],
    ids=["text-plain", "form", "multipart", "none"],
)
def test_a_create_request_that_is_not_json_is_access_denied_before_the_session(
    library_server: START, fake_google: FakeGoogle, content_type: str | None
) -> None:
    """DEC-022: what a form of another page can send without a preflight is ``Access denied.`` even with the right
    ``Origin`` and the administrator's session, and for a visitor too (not the sign in page)."""
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    headers = {key: value for key, value in admin.page_post_headers().items() if key != "Content-Type"}
    if content_type is not None:
        headers["Content-Type"] = content_type
    before = stored_folders(running)

    assert_access_denied(admin.post_json(CREATE_PATH, {"name": "Backdoor"}, headers=headers))
    assert_access_denied(running.browser().post_json(CREATE_PATH, {"name": "Backdoor"}, headers=headers))

    assert stored_folders(running) == before and activity_count(running) == 0
    assert "Backdoor" not in home_names(admin)


def test_json_with_a_charset_is_json(library_server: START, fake_google: FakeGoogle) -> None:
    """``application/json; charset=utf-8`` is the JSON media type (parameters and case aside)."""
    running = library_server(fake_google)
    admin = signed_in(running, fake_google, ADMIN)
    headers = {**admin.page_post_headers(), "Content-Type": "Application/JSON; charset=utf-8"}

    assert admin.post_json(CREATE_PATH, {"name": ONCOLOGY}, headers=headers).status == 201


# ---------------------------------------------------------------------------
# E2E-SEC-011, E2E-SEC-018
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("email", [DAN, CAROL, LAMYA])
def test_exploit_e2e_sec_011_a_rw_member_creates_a_folder_by_hand(
    library_server: START, fake_google: FakeGoogle, email: str
) -> None:
    """E2E-SEC-011 (Class B #1). Red before the fix because: the folder is created; the assertion "the administrator
    sees 3 folders" fails with 4.

    Dan (RW in Cardiology), and Carol and Lamya too, send with their own session exactly what the administration
    sends for "Backdoor": ``Access denied.``; the ``folders`` table holds the same three rows, the ``activity``
    table the same count, and the administrator's home lists the same 3 folders.
    """
    running = library_server(fake_google)
    running.builder.standard()
    member = signed_in(running, fake_google, email)
    admin = signed_in(running, fake_google, ADMIN)
    before, lines = stored_folders(running), activity_count(running)

    reply = member.post_json(CREATE_PATH, {"name": "Backdoor"})

    assert_access_denied(reply)
    assert stored_folders(running) == before and activity_count(running) == lines
    assert home_names(admin) == STANDARD_NAMES


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Type": "application/json"},
        {"Origin": "http://evil.example", "Content-Type": "application/json"},
        {"Origin": "null", "Content-Type": "application/json"},
        {"ORIGIN_IS_LIBRARY": "", "Sec-Fetch-Site": "cross-site", "Content-Type": "application/json"},
        {"ORIGIN_IS_LIBRARY": "", "Sec-Fetch-Site": "same-site", "Content-Type": "application/json"},
        {"ORIGIN_IS_CONTENT": "", "Content-Type": "application/json"},
    ],
    ids=["no-origin", "other-origin", "null-origin", "cross-site", "same-site", "content-origin"],
)
def test_exploit_e2e_sec_018_the_copied_administrator_session_without_the_library_origin(
    library_server: START, fake_google: FakeGoogle, headers: dict[str, str]
) -> None:
    """E2E-SEC-018 (Class G #2, #3). Red before the fix because: the request is accepted since a request with no
    Origin evidence passes the gate; the assertion "the administrator lists 3 folders" fails with 4.

    The administrator's cookie replayed by a command line tool (no ``Origin``), or by another site, is ``Access
    denied.``; the tables are unchanged; the administrator's real browser lists the same 3 folders and no line.
    """
    running = library_server(fake_google)
    running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    copy = running.browser()
    copy.cookies = dict(admin.cookies)
    if headers.pop("ORIGIN_IS_LIBRARY", None) is not None:
        headers["Origin"] = running.origin
    if headers.pop("ORIGIN_IS_CONTENT", None) is not None:
        headers["Origin"] = running.settings.library_content_origin
    before = stored_folders(running)

    reply = copy.post_json(CREATE_PATH, {"name": "Backdoor"}, headers=headers)

    assert_access_denied(reply)
    assert stored_folders(running) == before and activity_count(running) == 0
    assert home_names(admin) == STANDARD_NAMES
    assert admin.open(ADMIN_PATH).activity_lines() == []
    assert create(admin, ONCOLOGY).status == 201  # the same session from the library's own page still works
