"""US-0127: the home page, the Admin role, the folder order, the empty home and the uniform refusal (SPEC-0025).

Spec tests: E2E-014, E2E-018, E2E-087, E2E-149, E2E-165. People sign in through ``FakeGoogle``; folders and members are
written by ``LibraryBuilder``; pages are read over HTTP. ``Library.role_in`` is also read directly, since no route
names a folder before US-0129.
"""

from __future__ import annotations

import html
import re
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_htmleditor.library import pages, routes_library
from mcp_htmleditor.library.access import ADMIN_EMAIL, Role
from mcp_htmleditor.library.server import safe_destination
from mcp_htmleditor.library.store import FolderView, Library
from tests import library_support
from tests.library_support import (
    ADMIN,
    BOB,
    CARDIOLOGY,
    CAROL,
    DAN,
    LAMYA,
    PNEUMO,
    WCBIP,
    FakeGoogle,
    LibraryReply,
    RunningLibrary,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

ADMIN_LABEL = "Admin"
ADMINISTRATION_LINK = '<a href="/admin">Administration</a>'
SIGN_OUT_FORM = '<form method="post" action="/auth/logout"><button type="submit">Sign out</button></form>'
EMPTY_HOME = "You have no access to any folder yet."
LIBRARY_UNAVAILABLE = "The library is unavailable. Try again later."
READY_SECONDS = 2.0
STYLESHEET = '<link rel="stylesheet" href="/lib/library.css">'
# Every text the mode itself may put on a home page (FR-NEW-065): the rest of the visible text is folder names.
ENGLISH_HOME_TEXTS = {"Slides", "Administration", "Admin", "Read and write", "Read only", "Sign out", EMPTY_HOME}


def signed_in(running: RunningLibrary, google: FakeGoogle, email: str) -> tuple[library_support.Browser, LibraryReply]:
    browser = running.browser()
    return browser, browser.sign_in(google, email)


def names_and_roles(reply: LibraryReply) -> list[tuple[str, str]]:
    """``(folder name, role label)`` of each row, in page order, unescaped."""
    return [(html.unescape(name), role) for _, name, role in reply.folder_rows()]


def visible_texts(reply: LibraryReply) -> list[str]:
    """The text nodes of the page body, unescaped, in order."""
    body = reply.text.split("<body>", 1)[1]
    return [html.unescape(text).strip() for text in re.split(r"<[^>]*>", body) if text.strip()]


def assert_access_denied(reply: LibraryReply) -> None:
    """Exactly the one refusal page: the text and the Sign out button, nothing else (DEC-023)."""
    assert (reply.status, reply.body) == (403, pages.access_denied())
    assert visible_texts(reply) == ["Access denied.", "Sign out"]


# ---------------------------------------------------------------------------
# E2E-014, E2E-087: the administrator
# ---------------------------------------------------------------------------


def test_e2e_014_the_administrator_sees_every_folder_and_the_administration_entry(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-014: no member row for him, three folders labelled Admin in order; Carol sees only her folder."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    assert ADMIN not in {row[0] for row in running.stored.rows("SELECT email FROM members")}
    admin, _ = signed_in(running, fake_google, ADMIN)
    carol, _ = signed_in(running, fake_google, CAROL)

    started = time.monotonic()
    reply = admin.open("/")
    elapsed = time.monotonic() - started

    assert reply.status == 200
    assert elapsed < READY_SECONDS
    assert [(folder_id, html.unescape(name), role) for folder_id, name, role in reply.folder_rows()] == [
        (ids[CARDIOLOGY], CARDIOLOGY, ADMIN_LABEL),
        (ids[PNEUMO], PNEUMO, ADMIN_LABEL),
        (ids[WCBIP], WCBIP, ADMIN_LABEL),
    ]
    assert reply.text.count(ADMINISTRATION_LINK) == 1
    assert SIGN_OUT_FORM in reply.text
    assert LIBRARY_UNAVAILABLE not in reply.text and EMPTY_HOME not in reply.text
    carol_home = carol.open("/")
    assert names_and_roles(carol_home) == [(CARDIOLOGY, "Read only")]
    assert "Administration" not in carol_home.text and "/admin" not in carol_home.text


def test_e2e_087_the_administrator_address_is_compared_without_regard_to_case(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-087: Google returns ``Seb.Morand@Gmail.com``: Administration and the 3 folders labelled Admin."""
    running = library_server(fake_google)
    running.builder.standard()

    _, reply = signed_in(running, fake_google, "Seb.Morand@Gmail.com")

    assert reply.status == 200
    assert reply.text.count(ADMINISTRATION_LINK) == 1
    assert names_and_roles(reply) == [(CARDIOLOGY, ADMIN_LABEL), (PNEUMO, ADMIN_LABEL), (WCBIP, ADMIN_LABEL)]


def test_a_member_row_cannot_reduce_the_administrator_and_gives_no_one_else_admin(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-012, FR-NEW-014: the administrator listed RO stays Admin; Dan stays RW and never sees Administration."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.member(ids[CARDIOLOGY], ADMIN, "RO")
    running.builder.member(ids[PNEUMO], DAN, "RW")

    _, admin_home = signed_in(running, fake_google, ADMIN)
    _, dan_home = signed_in(running, fake_google, DAN)

    assert names_and_roles(admin_home) == [(CARDIOLOGY, ADMIN_LABEL), (PNEUMO, ADMIN_LABEL), (WCBIP, ADMIN_LABEL)]
    assert names_and_roles(dan_home) == [(CARDIOLOGY, "Read and write"), (PNEUMO, "Read and write")]
    assert ADMIN_LABEL not in visible_texts(dan_home) and "Administration" not in dan_home.text
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint"):  # a member role is RW or RO, never Admin
        running.builder.member(ids[WCBIP], DAN, "Admin")


def test_role_in_puts_the_administrator_first_and_reads_members_otherwise(library_server: START) -> None:
    """``Library.role_in``: Admin for the address in any case and any folder; the member row else; None else."""
    running = library_server()
    ids = running.builder.standard()
    running.builder.member(ids[CARDIOLOGY], ADMIN, "RO")
    library = Library(running.database)
    unknown_folder = "0" * 32

    for folder_id in (ids[CARDIOLOGY], ids[WCBIP], unknown_folder):
        assert library.role_in(ADMIN, folder_id) is Role.ADMIN
        assert library.role_in("SEB.MORAND@GMAIL.COM", folder_id) is Role.ADMIN
    assert library.role_in(DAN, ids[CARDIOLOGY]) is Role.RW
    assert library.role_in("Dan.RW@Example.org", ids[CARDIOLOGY]) is Role.RW
    assert library.role_in(CAROL, ids[CARDIOLOGY]) is Role.RO
    assert library.role_in(LAMYA, ids[CARDIOLOGY]) is None
    assert library.role_in(DAN, unknown_folder) is None
    for look_alike in ("sebmorand@gmail.com", "seb.morand@googlemail.com", "seb.morand@gmail.com.evil.example"):
        assert library.role_in(look_alike, ids[CARDIOLOGY]) is None, look_alike
        assert not library.is_admin(look_alike)
    assert library.is_admin(ADMIN_EMAIL.upper())


def test_a_look_alike_address_sees_access_denied_and_no_folder(library_server: START, fake_google: FakeGoogle) -> None:
    """Independent test: the administrator without member rows sees all three, ``sebmorand@gmail.com`` nothing."""
    running = library_server(fake_google)
    running.builder.standard()

    _, admin_home = signed_in(running, fake_google, ADMIN)
    _, look_alike = signed_in(running, fake_google, "sebmorand@gmail.com")

    assert len(admin_home.folder_rows()) == 3
    assert_access_denied(look_alike)
    assert not any(name in look_alike.text for name in (CARDIOLOGY, PNEUMO, WCBIP))


# ---------------------------------------------------------------------------
# E2E-018, E2E-165: the order; FR-NEW-065: English
# ---------------------------------------------------------------------------


def test_e2e_018_folders_are_ordered_without_regard_to_case_or_accents(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-018: the five folders in order; every text the mode adds is one of its English constants."""
    running = library_server(fake_google)
    folders = ("zeta", "Éclair Study", CARDIOLOGY, "alpha trial", PNEUMO)
    running.builder.folders(*folders)

    _, reply = signed_in(running, fake_google, ADMIN)

    expected = ["alpha trial", CARDIOLOGY, "Éclair Study", PNEUMO, "zeta"]
    assert [name for name, _ in names_and_roles(reply)] == expected
    added = [text for text in visible_texts(reply) if text not in folders]
    assert added, reply.text
    assert set(added) <= ENGLISH_HOME_TEXTS, added
    assert '<html lang="en">' in reply.text


def test_e2e_165_folders_are_ordered_digits_latin_letters_other_alphabets(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-165: digits, then Latin letters (accents ignored), then the Cyrillic name."""
    running = library_server(fake_google)
    running.builder.folders("Кардиология", "Zeta", "Éclair", "2027 Review", "alpha", "Été")

    _, reply = signed_in(running, fake_google, ADMIN)

    expected = ["2027 Review", "alpha", "Éclair", "Été", "Zeta", "Кардиология"]
    assert [name for name, _ in names_and_roles(reply)] == expected


def test_a_member_sees_the_same_order_rule(library_server: START, fake_google: FakeGoogle) -> None:
    """FR-NEW-015 for a member: Dan's folders follow ``order_key`` too, not the stored byte order."""
    running = library_server(fake_google)
    ids = running.builder.folders("zeta", "Éclair", "alpha", "Кардиология", "Beta")
    for folder_id in ids.values():
        running.builder.member(folder_id, DAN, "RO")

    _, reply = signed_in(running, fake_google, DAN)

    assert [name for name, _ in names_and_roles(reply)] == ["alpha", "Beta", "Éclair", "zeta", "Кардиология"]


# ---------------------------------------------------------------------------
# FR-NEW-016: the empty home; FR-NEW-053: escaping
# ---------------------------------------------------------------------------


def test_the_administrator_with_no_folder_sees_the_empty_message(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-016: no folder at all: the message, Administration and Sign out, no list; the first folder replaces it."""
    running = library_server(fake_google)
    admin, reply = signed_in(running, fake_google, ADMIN)

    assert reply.status == 200
    assert visible_texts(reply) == ["Slides", "Administration", EMPTY_HOME, "Sign out"]
    assert reply.folder_rows() == [] and "<li>" not in reply.text

    running.builder.folder("Oncology 2030")
    after = admin.open("/")
    assert names_and_roles(after) == [("Oncology 2030", ADMIN_LABEL)]
    assert EMPTY_HOME not in after.text


def test_a_person_with_no_role_never_sees_the_empty_message(library_server: START, fake_google: FakeGoogle) -> None:
    """FR-NEW-016 business rule: an account with no role anywhere gets ``Access denied.``, with or without folders."""
    running = library_server(fake_google)
    browser, empty_library = signed_in(running, fake_google, BOB)
    assert_access_denied(empty_library)

    running.builder.standard()
    running.builder.member(running.builder.folder("Other"), LAMYA, "RW")
    assert_access_denied(browser.open("/"))


def test_names_with_markup_are_shown_as_written_to_the_administrator(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-053: a stored name holding markup reaches the page escaped, never as an element."""
    running = library_server(fake_google)
    hostile = '<img src=x onerror="alert(1)"> & <b>bold</b>'
    folder_id = running.builder.folder(hostile)

    _, reply = signed_in(running, fake_google, ADMIN)

    assert reply.folder_rows() == [(folder_id, html.escape(hostile, quote=True), ADMIN_LABEL)]
    assert names_and_roles(reply) == [(hostile, ADMIN_LABEL)]
    assert "<img" not in reply.text and "<b>" not in reply.text


def test_home_page_escapes_every_folder_name_and_marks_administration_only_for_admins() -> None:
    """``pages.home_page`` as a unit: escaping, the role label of each view, the link only with ``is_admin``."""
    folder = FolderView(id="a" * 32, name='"><script>x</script>', role=Role.RW)

    member_page = pages.home_page([folder], is_admin=False).decode()
    admin_page = pages.home_page([], is_admin=True).decode()

    assert "&quot;&gt;&lt;script&gt;x&lt;/script&gt;" in member_page and "<script>" not in member_page
    assert "Read and write" in member_page and ADMINISTRATION_LINK not in member_page
    assert EMPTY_HOME not in member_page
    assert ADMINISTRATION_LINK in admin_page and EMPTY_HOME in admin_page


# ---------------------------------------------------------------------------
# E2E-149: any other page
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/made-up/page", "/admin"])
def test_e2e_149_any_other_page_is_the_sign_in_page_signed_out_and_access_denied_signed_in(
    library_server: START, fake_google: FakeGoogle, path: str
) -> None:
    """E2E-149: a visitor gets the home address's sign in page (only ``next`` differs); Dan gets ``Access denied.``."""
    running = library_server(fake_google)
    running.builder.standard()
    visitor = running.browser()

    home, other = visitor.open("/"), visitor.open(path)

    assert (other.status, other.body) == (200, pages.sign_in_page(path, None))
    assert other.text.replace(f"next={path}", "next=/") == home.text
    browser, _ = signed_in(running, fake_google, DAN)
    assert_access_denied(browser.open(path))
    assert browser.open("/").folder_rows()  # the same session still reaches its home page


# ---------------------------------------------------------------------------
# The two public files (DEC-011)
# ---------------------------------------------------------------------------


def test_every_page_links_the_library_stylesheet_which_anyone_can_fetch(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """``/lib/library.css`` is public, ``text/css``, the file of ``static/``; every page links it."""
    running = library_server(fake_google)
    running.builder.standard()
    css = Path(routes_library.STATIC_DIR / "library.css").read_bytes()

    reply = running.client().get("/lib/library.css")

    assert (reply.status, reply.body) == (200, css)
    assert reply.headers["content-type"] == "text/css"
    assert reply.headers["x-content-type-options"] == "nosniff"
    _, home = signed_in(running, fake_google, ADMIN)
    for page in (running.client().get("/"), home, running.client().get("/f/x")):
        assert page.text.count(STYLESHEET) == 1
    assert pages.access_denied().decode().count(STYLESHEET) == 1


def test_the_library_script_is_served_when_present_and_nothing_else_under_lib(
    library_server: START, fake_google: FakeGoogle, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``/lib/library.js``: ``application/javascript`` when the file exists, ``404`` JSON when not; other names under
    ``/lib/`` are no page (the sign in page, or ``Access denied.``), and never a file of ``static/``."""
    static = tmp_path / "static"
    static.mkdir()
    (static / "library.css").write_text("body{}", encoding="utf-8")
    (static / "editor.js").write_text("secret()", encoding="utf-8")
    monkeypatch.setattr(routes_library, "STATIC_DIR", static)
    running = library_server(fake_google)
    running.builder.standard()
    client = running.client()

    missing = client.get("/lib/library.js")
    (static / "library.js").write_text("ok()", encoding="utf-8")
    present = client.get("/lib/library.js")

    assert (missing.status, missing.json()) == (404, {"error": "Not found"})
    assert (present.status, present.body, present.headers["content-type"]) == (200, b"ok()", "application/javascript")
    for path in ("/lib/editor.js", "/lib/../static/editor.js", "/lib/library.css/x", "/lib/"):
        reply = client.get(path)
        assert (reply.status, reply.body) == (200, pages.sign_in_page(safe_destination(path), None)), path
    browser, _ = signed_in(running, fake_google, DAN)
    assert_access_denied(browser.open("/lib/editor.js"))
