"""US-0142: the file name allow list, the composed form and the hostile names (SPEC-0025, DEC-029, DEC-033).

Spec tests: E2E-060, E2E-061, E2E-065, E2E-125, E2E-127, E2E-175, E2E-SEC-001, E2E-SEC-002, E2E-SEC-003, E2E-SEC-005.
The second channel of every refusal is the operator's listing of the library storage (no entry named passwd, nothing
outside ``files/<folder id>/``), a dump of the three tables and the number of activity lines.
"""

from __future__ import annotations

import html
import re
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass

import pytest

from tests import library_support
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    LAMYA,
    WCBIP,
    Browser,
    FakeGoogle,
    LibraryReply,
    RunningLibrary,
    signed_in,
    valid_deck,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

NOT_ALLOWED = "This file name is not allowed."
ONLY_HTML = "Only .html files are accepted."
LARGE = "The file is larger than 25 MB."
THIRTY_MB = 31_457_280


@dataclass(frozen=True)
class Library:
    running: RunningLibrary
    google: FakeGoogle
    ids: dict[str, str]
    dan: Browser
    carol: Browser

    def upload(self, name: str, who: Browser | None = None, folder: str = CARDIOLOGY) -> LibraryReply:
        return (who or self.dan).upload(self.ids[folder], name, valid_deck())

    def listed(self, folder: str = CARDIOLOGY) -> list[str]:
        admin = signed_in(self.running, self.google, ADMIN)
        return [html.unescape(row[0]) for row in admin.open(f"/f/{self.ids[folder]}").presentation_rows()]

    def storage(self) -> list[str]:
        return self.running.stored.entries()

    def tables(self) -> list[tuple[str, list[tuple[object, ...]]]]:
        """A dump of ``members``, ``folders`` and ``presentations`` without the generated ids and times."""
        queries = {
            "members": "SELECT * FROM members ORDER BY 1, 2",
            "folders": "SELECT * FROM folders ORDER BY 1, 2",
            "presentations": "SELECT folder_id, name FROM presentations ORDER BY 1, 2",
        }
        with closing(sqlite3.connect(self.running.library_dir / "library.db")) as connection:
            return [(table, connection.execute(query).fetchall()) for table, query in queries.items()]

    def activity_count(self) -> int:
        return len(self.running.stored.activity())


@pytest.fixture
def library(library_server: START, fake_google: FakeGoogle) -> Library:
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    return Library(
        running, fake_google, ids, signed_in(running, fake_google, DAN), signed_in(running, fake_google, CAROL)
    )


def refused(reply: LibraryReply, text: str = NOT_ALLOWED) -> None:
    assert reply.status == 400, reply.text
    assert reply.json() == {"ok": False, "error": text}


def nothing_changed(
    library: Library, storage: list[str], tables: list[tuple[str, list[tuple[object, ...]]]], lines: int
) -> None:
    assert library.storage() == storage
    assert library.tables() == tables
    assert library.activity_count() == lines
    assert len(library.listed()) == 3


def test_e2e_060_a_file_name_that_carries_a_folder_path_is_refused(library: Library) -> None:
    storage, tables, lines = library.storage(), library.tables(), library.activity_count()

    refused(library.upload("2026/Quarterly Review.html"))

    assert not any("Quarterly" in name for folder in library.ids for name in library.listed(folder))
    nothing_changed(library, storage, tables, lines)


@pytest.mark.parametrize("name", [".hidden.html", "Report #1.html", "Rapport@2026.html"])
def test_e2e_061_names_starting_with_a_dot_or_using_other_characters_are_refused(library: Library, name: str) -> None:
    storage, tables, lines = library.storage(), library.tables(), library.activity_count()
    refused(library.upload(name))
    nothing_changed(library, storage, tables, lines)


def test_e2e_065_the_extension_is_checked_before_the_name_and_the_size(library: Library) -> None:
    first = library.dan.upload_declaring(library.ids[CARDIOLOGY], "notes.txt", THIRTY_MB)
    second = library.dan.upload_declaring(library.ids[CARDIOLOGY], "a/b.html", THIRTY_MB)

    assert first.status == 400
    assert first.json() == {"ok": False, "error": ONLY_HTML}
    assert second.status == 400
    assert second.json() == {"ok": False, "error": NOT_ALLOWED}
    assert LARGE not in first.text + second.text
    assert library.dan.upload_declaring(library.ids[CARDIOLOGY], "ok.html", THIRTY_MB).json()["error"] == LARGE


def test_e2e_125_dots_parentheses_and_apostrophes_inside_a_name_are_accepted(library: Library) -> None:
    first = library.upload("Report.v2.final.html")
    second = library.upload("L'été (v2).html")

    assert first.json()["message"] == "Uploaded Report.v2.final."
    assert second.json()["message"] == "Uploaded L'été (v2)."
    assert {"Report.v2.final", "L'été (v2)"} <= set(library.listed())


@pytest.mark.parametrize(
    "name",
    ["%2e%2e%2fsecret.html", "..\\..\\secret.html", "Report\u202etxt.html", "Report\x00.html", "Report\n.html"],
    ids=["encoded-slash", "backslash", "right-to-left", "nul", "newline"],
)
def test_e2e_127_encoded_and_look_alike_names_are_refused(library: Library, name: str) -> None:
    storage, tables, lines = library.storage(), library.tables(), library.activity_count()
    refused(library.upload(name))
    nothing_changed(library, storage, tables, lines)


def test_e2e_127_a_broken_percent_sequence_or_invalid_utf_8_is_not_a_name(library: Library) -> None:
    for raw in ("%FF%FE.html", "%E0%A4%A.html", "%.html"):
        sent = {
            "Origin": library.running.origin,
            "Sec-Fetch-Site": "same-origin",
            "X-File-Name": raw,
            "Content-Type": "text/html",
        }
        reply = library.dan.upload(library.ids[CARDIOLOGY], "", valid_deck(), headers=sent)
        refused(reply)


def test_e2e_175_file_names_accept_latin_script_letters_and_the_straight_apostrophe_only(library: Library) -> None:
    accepted = ["Łódź Study", "Øresund Plan", "Cœur Étude", "Straße Report"]

    replies = [library.upload(f"{name}.html") for name in accepted]
    curly = library.upload("Dan\u2019s Deck.html")

    assert [reply.json()["message"] for reply in replies] == [f"Uploaded {name}." for name in accepted]
    refused(curly)
    assert set(accepted) <= set(library.listed())
    assert "Dan\u2019s Deck" not in library.listed()


def test_e2e_sec_001_a_ro_member_uploads_a_path_traversal_name(library: Library) -> None:
    """E2E-SEC-001. Red before the fix because: the file is written one level above the folder; the assertion "no
    entry named passwd anywhere in the library storage" fails. Carol is refused by her role, before any name check."""
    storage, tables, lines = library.storage(), library.tables(), library.activity_count()

    reply = library.upload("../../etc/passwd.html", library.carol)

    assert reply.status == 403
    assert "Access denied." in reply.text
    assert not [entry for entry in library.storage() if "passwd" in entry]
    nothing_changed(library, storage, tables, lines)


def test_e2e_sec_002_a_rw_member_uploads_a_path_traversal_name(library: Library, fake_google: FakeGoogle) -> None:
    """E2E-SEC-002. Red before the fix because: the name is cleaned to "passwd.html" and stored; "no entry named
    passwd" fails. Lamya still sees her 2 presentations."""
    storage, tables, lines = library.storage(), library.tables(), library.activity_count()

    for name in ("../../etc/passwd.html", "..%2F..%2Fetc%2Fpasswd.html", "/etc/passwd.html"):
        refused(library.upload(name))

    assert not [entry for entry in library.storage() if "passwd" in entry]
    nothing_changed(library, storage, tables, lines)
    lamya = signed_in(library.running, fake_google, LAMYA)
    assert len(lamya.open(f"/f/{library.ids[WCBIP]}").presentation_rows()) == 2


def test_e2e_sec_003_a_name_that_looks_like_a_data_erasing_command_is_refused(
    library: Library, fake_google: FakeGoogle
) -> None:
    """E2E-SEC-003. Red before the fix because: a build that accepts any name stores "a'; DROP TABLE users;--"."""
    storage, tables, lines = library.storage(), library.tables(), library.activity_count()

    refused(library.upload("a'; DROP TABLE users;--.html"))

    assert not any("DROP" in name for folder in library.ids for name in library.listed(folder))
    nothing_changed(library, storage, tables, lines)
    for email in (LAMYA, CAROL):
        assert signed_in(library.running, fake_google, email).open("/").status == 200


def test_e2e_sec_005_a_folder_named_two_dots_is_refused_and_an_upload_lands_in_its_own_folder(
    library: Library, fake_google: FakeGoogle
) -> None:
    """E2E-SEC-005. Red before the fix because: a folder named ".." is created and later uploads land one level up."""
    admin = signed_in(library.running, fake_google, ADMIN)
    before = library.storage()

    reply = admin.post_json("/api/folders", {"name": ".."})

    assert reply.status == 400
    assert reply.json()["error"] == "Folder names use 1 to 60 letters, digits, spaces or hyphens."
    assert len(admin.open("/").text.split('<li><a href="/f/')) - 1 == 3
    assert library.storage() == before
    assert library.upload("Quarterly Review.html").status == 201
    added = sorted(set(library.storage()) - set(before))
    assert [
        re.fullmatch(rf"library/files/{library.ids[CARDIOLOGY]}/[0-9a-f]{{32}}\.html", entry) for entry in added
    ] != [None]
    assert all(
        entry.startswith(f"library/files/{library.ids[CARDIOLOGY]}/") for entry in added if entry.endswith(".html")
    )
