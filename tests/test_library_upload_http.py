"""US-0141: uploading a valid presentation into a folder (SPEC-0025, DEC-019, DEC-022, DEC-033, DEC-034).

Spec tests: E2E-055, E2E-057, E2E-058, E2E-059, E2E-064, E2E-144, E2E-154, E2E-155, E2E-169, E2E-174, E2E-179 and
E2E-SEC-010. The second channel of every refusal is the folder as the administrator lists it, the files of the library
and the activity table, never only the status line.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from mcp_htmleditor.library.uploads import UploadRefused, check_validity
from tests import library_support
from tests.deck_support import TINY_PNG, build_deck, deck_med, replace_in_slide
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    PNEUMO,
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

QUARTERLY = "Quarterly Review"
QUARTERLY_BYTES = 1_258_291
NOT_VALID = "This file is not a valid presentation: "
NOT_DECLARED = f"{NOT_VALID}the file is not declared as a presentation."
DENIED = "Access denied."


@dataclass(frozen=True)
class Folders:
    running: RunningLibrary
    google: FakeGoogle
    ids: dict[str, str]
    dan: Browser
    carol: Browser

    def listed(self, folder: str = CARDIOLOGY) -> list[str]:
        """The names the administrator's folder page lists."""
        admin = signed_in(self.running, self.google, ADMIN)
        return [row[0] for row in admin.open(f"/f/{self.ids[folder]}").presentation_rows()]

    def lines(self) -> list[str]:
        return [row[2] for row in signed_in(self.running, self.google, ADMIN).open("/admin").activity_lines()]

    def files(self) -> list[str]:
        return [entry for entry in self.running.stored.entries() if entry.endswith(".html") or ".tmp" in entry]


@pytest.fixture
def folders(library_server: START, fake_google: FakeGoogle) -> Folders:
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    return Folders(
        running, fake_google, ids, signed_in(running, fake_google, DAN), signed_in(running, fake_google, CAROL)
    )


def refused(reply: LibraryReply, message: str) -> None:
    assert reply.status == 400, reply.text
    assert reply.json() == {"ok": False, "error": message}


def unchanged(folders: Folders, before_files: list[str], before_lines: list[str]) -> None:
    assert folders.listed() == ["Arrhythmia Basics", "Statins Review", "Heart Failure Update"]
    assert folders.files() == before_files
    assert folders.lines() == before_lines


def test_a_valid_presentation_is_stored_listed_first_and_recorded(folders: Folders) -> None:
    """The independent test: one new file ``files/<fid>/<32 hex>.html`` equal to the bytes, one activity line."""
    data = valid_deck(3, QUARTERLY_BYTES)
    before = folders.files()

    reply = folders.dan.upload(folders.ids[CARDIOLOGY], f"{QUARTERLY}.HTML", data)

    assert reply.status == 201
    assert reply.json() == {"ok": True, "name": QUARTERLY, "message": f"Uploaded {QUARTERLY}."}
    (added,) = sorted(set(folders.files()) - set(before))
    assert re.fullmatch(rf"library/files/{folders.ids[CARDIOLOGY]}/[0-9a-f]{{32}}\.html", added)
    assert (folders.running.library_dir.parent / added).read_bytes() == data
    assert folders.listed()[0] == QUARTERLY
    assert folders.lines()[0] == f'Uploaded "{QUARTERLY}" in "{CARDIOLOGY}"'
    assert folders.running.stored.activity()[-1][2] == DAN


def test_e2e_055_a_file_that_is_not_html_is_refused(folders: Folders) -> None:
    before_files, before_lines = folders.files(), folders.lines()
    for name in (f"{QUARTERLY}.pdf", f"{QUARTERLY}.htm", "html", f"{QUARTERLY}.html.pdf"):
        refused(folders.dan.upload(folders.ids[CARDIOLOGY], name, valid_deck()), "Only .html files are accepted.")
    unchanged(folders, before_files, before_lines)


@pytest.mark.parametrize("extension", [".html", ".HTML", ".Html", ".hTmL"])
def test_the_extension_is_accepted_in_any_letter_case(folders: Folders, extension: str) -> None:
    assert folders.dan.upload(folders.ids[CARDIOLOGY], f"Case{extension}", valid_deck()).status == 201


def test_e2e_057_an_ordinary_web_page_and_an_undeclared_deck_are_not_presentations(folders: Folders) -> None:
    before_files, before_lines = folders.files(), folders.lines()
    page = b"<!DOCTYPE html><html><body><h1>Hello</h1></body></html>"
    undeclared = build_deck("ei", ("A", "B")).replace('data-doc-type="presentation"', "").encode()

    refused(folders.dan.upload(folders.ids[CARDIOLOGY], "About Us.html", page), NOT_DECLARED)
    refused(folders.dan.upload(folders.ids[CARDIOLOGY], "Undeclared Deck.html", undeclared), NOT_DECLARED)

    unchanged(folders, before_files, before_lines)


def test_e2e_179_an_empty_file_is_refused_as_not_declared(folders: Folders) -> None:
    before_files, before_lines = folders.files(), folders.lines()
    refused(folders.dan.upload(folders.ids[CARDIOLOGY], "Nothing.html", b""), NOT_DECLARED)
    unchanged(folders, before_files, before_lines)


def test_e2e_058_a_presentation_without_any_slide_is_refused(folders: Folders) -> None:
    before_files, before_lines = folders.files(), folders.lines()
    empty = b'<!DOCTYPE html><html data-doc-type="presentation"><body></body></html>'
    refused(folders.dan.upload(folders.ids[CARDIOLOGY], "Empty Deck.html", empty), f"{NOT_VALID}the file has no slide.")
    unchanged(folders, before_files, before_lines)


def test_e2e_059_a_blocking_structure_error_names_its_first_problem(folders: Folders) -> None:
    before_files, before_lines = folders.files(), folders.lines()
    broken = build_deck("ei", ("A", "B")).replace('data-title="B"', "", 1).encode()
    refused(
        folders.dan.upload(folders.ids[CARDIOLOGY], "Broken Deck.html", broken),
        f"{NOT_VALID}missing attribute data-title.",
    )
    unchanged(folders, before_files, before_lines)


def test_e2e_064_the_first_problem_is_the_whole_file_one_before_slide_ones(folders: Folders) -> None:
    mismatch = (
        build_deck("ei", ("A", "B", "C"))
        .replace("const TOTAL = 3;", "const TOTAL = 5;")
        .replace('data-title="B"', "", 1)
    )
    reply = folders.dan.upload(folders.ids[CARDIOLOGY], "Mismatch.html", mismatch.encode())
    refused(reply, f"{NOT_VALID}TOTAL is 5 but the file has 3 slides.")
    assert "missing attribute" not in reply.text


def test_e2e_155_a_warning_listed_first_is_never_the_first_problem(folders: Folders) -> None:
    deck = build_deck("ei", ("A", "B")).replace("</body>", '<img src="https://example.org/logo.png"></body>', 1)
    deck = deck.replace('data-title="B"', "", 1)

    reply = folders.dan.upload(folders.ids[CARDIOLOGY], "Logo Deck.html", deck.encode())

    refused(reply, f"{NOT_VALID}missing attribute data-title.")
    assert "logo" not in reply.text.lower()
    assert "slide-1" not in reply.text


def test_a_file_with_a_warning_only_is_accepted(folders: Folders) -> None:
    deck = build_deck("ei", ("A", "B")).replace("</body>", '<img src="https://example.org/logo.png"></body>', 1)
    assert folders.dan.upload(folders.ids[CARDIOLOGY], "Web Pictures.html", deck.encode()).status == 201


def test_e2e_154_an_error_of_the_charter_rules_blocks_an_upload(folders: Folders) -> None:
    before_files, before_lines = folders.files(), folders.lines()
    picture = f'<div class="med-logos"><img src="data:image/png;base64,{TINY_PNG}" alt="Logo"></div>'
    source = '<p class="med-source">'
    deck = replace_in_slide(deck_med(), 1, source, picture + source)
    deck = replace_in_slide(
        deck, 1, '<p class="med-source"><span class="src-title">', '<p class="med-source-x"><span class="src-title">'
    )

    reply = folders.dan.upload(folders.ids[CARDIOLOGY], "Medical Deck.html", deck.encode())

    refused(reply, f"{NOT_VALID}slide has an image and no source line.")
    unchanged(folders, before_files, before_lines)


def test_e2e_174_a_file_that_is_not_utf_8_text_is_refused_with_no_location(folders: Folders) -> None:
    before_files, before_lines = folders.files(), folders.lines()
    latin = valid_deck(3, QUARTERLY_BYTES).replace(b"Slide 1", "Slide é".encode("latin-1"), 1)

    reply = folders.dan.upload(folders.ids[CARDIOLOGY], "Latin Deck.html", latin)

    refused(reply, f"{NOT_VALID}the file is not valid UTF-8 text.")
    assert not re.search(r"position|line \d|byte \d|/", reply.json()["error"])
    unchanged(folders, before_files, before_lines)


def test_e2e_144_accented_names_with_apostrophes_are_recorded_as_written(folders: Folders) -> None:
    folders.running.builder.member(folders.ids[PNEUMO], DAN, "RW")

    reply = folders.dan.upload(folders.ids[PNEUMO], "L'été (v2).html", valid_deck())

    assert reply.status == 201
    assert folders.lines()[0] == 'Uploaded "L\'été (v2)" in "Pneumo Été"'
    assert folders.running.stored.activity()[-1][2] == DAN


def test_e2e_169_sign_ins_and_sign_outs_are_not_recorded(folders: Folders) -> None:
    for _ in range(3):
        person = signed_in(folders.running, folders.google, DAN)
        person.sign_out()

    assert folders.dan.upload(folders.ids[CARDIOLOGY], f"{QUARTERLY}.html", valid_deck()).status == 201

    assert folders.lines() == [f'Uploaded "{QUARTERLY}" in "{CARDIOLOGY}"']


def test_e2e_sec_010_a_ro_member_uploads_by_hand(folders: Folders) -> None:
    """E2E-SEC-010. Red before the fix because: the file is stored; the assertion "3 presentations are listed to the
    administrator" fails with 4. Carol sends the request the library sends for a RW member, 1 258 291 bytes."""
    before_files, before_lines = folders.files(), folders.lines()

    reply = folders.carol.upload(folders.ids[CARDIOLOGY], f"{QUARTERLY}.html", valid_deck(3, QUARTERLY_BYTES))

    assert reply.status == 403
    assert DENIED in reply.text
    assert len(folders.listed()) == 3
    assert QUARTERLY not in folders.listed()
    unchanged(folders, before_files, before_lines)


def test_a_person_with_no_role_and_a_visitor_get_access_denied_and_nothing_is_stored(folders: Folders) -> None:
    before_files, before_lines = folders.files(), folders.lines()
    other = signed_in(folders.running, folders.google, "bob.nobody@gmail.com")
    visitor = folders.running.browser()

    denied = other.upload(folders.ids[CARDIOLOGY], f"{QUARTERLY}.html", valid_deck())
    sign_in = visitor.upload(folders.ids[CARDIOLOGY], f"{QUARTERLY}.html", valid_deck())
    assert denied.status == 403
    assert "Sign in with Google" in sign_in.text  # a visitor is sent to sign in, as for every other page
    assert "Uploaded" not in sign_in.text
    unchanged(folders, before_files, before_lines)


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://evil.test"},
        {"Origin": ""},
        {"Sec-Fetch-Site": "cross-site"},
        {"X-File-Name": ""},
    ],
    ids=["other-origin", "no-origin", "cross-site", "no-file-name"],
)
def test_the_origin_rule_and_the_file_name_header_hold_for_a_writer_too(
    folders: Folders, headers: dict[str, str]
) -> None:
    """DEC-022: Dan's own session is not enough from another page or without the custom header."""
    before_files, before_lines = folders.files(), folders.lines()
    sent = {
        "Origin": folders.running.origin,
        "Sec-Fetch-Site": "same-origin",
        "X-File-Name": f"{QUARTERLY}.html",
        "Content-Type": "text/html",
        **headers,
    }
    sent = {name: value for name, value in sent.items() if value != ""}

    reply = folders.dan.upload(folders.ids[CARDIOLOGY], "", valid_deck(), headers=sent)

    assert reply.status == 403
    unchanged(folders, before_files, before_lines)


def test_a_folder_that_does_not_exist_is_access_denied_even_for_the_administrator(folders: Folders) -> None:
    admin = signed_in(folders.running, folders.google, ADMIN)
    before = folders.files()
    reply = admin.upload("0" * 32, f"{QUARTERLY}.html", valid_deck())
    assert reply.status == 403
    assert folders.files() == before


def test_check_validity_gives_the_six_messages_and_lets_a_warning_through() -> None:
    cases = {
        b"\xff\xfe": "the file is not valid UTF-8 text",
        b"": "the file is not declared as a presentation",
        b"<html><body>x</body></html>": "the file is not declared as a presentation",
        b'<html data-doc-type="presentation"><body></body></html>': "the file has no slide",
        build_deck("ei", ("A", "B")).replace('data-title="B"', "", 1).encode(): "missing attribute data-title",
        build_deck("ei", ("A",))
        .replace("const TOTAL = 1;", "const TOTAL = 4;")
        .encode(): "TOTAL is 4 but the file has 1 slides",
    }
    for data, problem in cases.items():
        with pytest.raises(UploadRefused) as caught:
            check_validity(data)
        assert str(caught.value) == f"{NOT_VALID}{problem}."
    remote = build_deck("ei", ("A",)).replace("</body>", '<img src="https://example.org/a.png"></body>', 1)
    check_validity(remote.encode())


def test_the_upload_control_is_on_the_folder_page_of_a_writer_and_the_administrator_only(folders: Folders) -> None:
    page = f"/f/{folders.ids[CARDIOLOGY]}"
    admin = signed_in(folders.running, folders.google, ADMIN)

    shown = {
        name: 'for="upload-file"' in person.open(page).text
        for name, person in (("dan", folders.dan), ("carol", folders.carol), ("admin", admin))
    }

    assert shown == {"dan": True, "carol": False, "admin": True}
