"""US-0145: deleting a presentation for good (SPEC-0025, DEC-022, DEC-023, DEC-026, DEC-028).

Spec tests: E2E-025, E2E-082, E2E-088, E2E-140, E2E-182, E2E-SEC-009. The second channel of every check is the library
storage (the file and ``<state_dir>/files/<key>/``: history, requests), the row, the activity table and what the
administrator lists.
"""

from __future__ import annotations

import html
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from mcp_htmleditor.request_service import RequestService
from mcp_htmleditor.request_store import RequestStore
from tests import library_support
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    STATINS,
    Browser,
    FakeGoogle,
    LibraryReply,
    Presentation,
    RunningLibrary,
    signed_in,
    valid_deck,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

DENIED = "Access denied."
STATINS_BYTES = 1_572_864
BOB = "bob.nobody@gmail.com"


@dataclass(frozen=True)
class Library:
    running: RunningLibrary
    google: FakeGoogle
    ids: dict[str, str]
    decks: dict[str, Presentation]
    dan: Browser
    carol: Browser

    @property
    def statins(self) -> Presentation:
        return self.decks[STATINS]

    def listed(self) -> list[str]:
        admin = signed_in(self.running, self.google, ADMIN)
        return [html.unescape(row[0]) for row in admin.open(f"/f/{self.ids[CARDIOLOGY]}").presentation_rows()]

    def lines(self) -> list[str]:
        return [row[2] for row in signed_in(self.running, self.google, ADMIN).open("/admin").activity_lines()]

    def storage(self) -> list[str]:
        return self.running.stored.entries()

    def rows(self) -> list[tuple[object, ...]]:
        return self.running.stored.rows("SELECT id, folder_id, name FROM presentations ORDER BY id")


@pytest.fixture
def library(library_server: START, fake_google: FakeGoogle) -> Library:
    running = library_server(fake_google)
    ids = running.builder.standard()
    decks = running.builder.standard_presentations(ids)
    return Library(
        running,
        fake_google,
        ids,
        decks,
        signed_in(running, fake_google, DAN),
        signed_in(running, fake_google, CAROL),
    )


def denied(reply: LibraryReply) -> None:
    assert reply.status == 403, reply.text
    assert DENIED in reply.text


def with_records(library: Library) -> None:
    """Two history versions, a queued request and an AI suggestion for "Statins Review"."""
    library.running.builder.records(library.statins)


def test_a_writer_deletes_for_good_and_a_name_uploaded_again_starts_clean(library: Library) -> None:
    """The independent test: neither the file nor ``<state_dir>/files/<key>/`` stays, the row is gone, and the same name
    uploaded again has no history, no request and no suggestion."""
    with_records(library)
    record_dir = RequestStore(library.running.state_dir).record_dir(library.statins.path).parent
    assert record_dir.is_dir()
    assert library.running.versions(library.statins) != []

    reply = library.dan.delete_presentation(library.statins.id)

    assert reply.status == 200
    assert reply.json() == {"ok": True}
    assert not library.statins.path.exists()
    assert not record_dir.exists()
    assert library.statins.id not in [row[0] for row in library.rows()]
    assert STATINS not in library.listed()
    assert library.lines()[0] == f'Deleted "{STATINS}" from "{CARDIOLOGY}"'
    assert library.running.stored.activity()[-1][2] == DAN
    again = library.dan.upload(library.ids[CARDIOLOGY], f"{STATINS}.html", valid_deck())  # no question: it is gone
    assert again.status == 201
    (fresh,) = [row for row in library.rows() if row[2] == STATINS]
    path = library.running.server.library.presentation_path(str(fresh[1]), str(fresh[0]))
    service = RequestService(RequestStore(library.running.state_dir))
    assert list(service.snapshot(path).requests) == []
    assert list(service.snapshot(path).suggestions) == []
    assert library.running.versions(Presentation(str(fresh[0]), str(fresh[1]), STATINS, path)) == []


def test_the_form_variant_does_the_same(library: Library) -> None:
    reply = library.dan.delete_presentation(library.statins.id, method="POST")
    assert reply.status == 200
    assert STATINS not in library.listed()


def test_e2e_sec_009_a_ro_member_deletes_by_hand(library: Library) -> None:
    """E2E-SEC-009. Red before the fix because: the presentation is removed; "Statins Review is still listed to the
    administrator" fails. Carol sends the request the library sends for a RW member, with her own session."""
    with_records(library)
    storage, lines = library.storage(), library.lines()

    for method in ("DELETE", "POST"):
        denied(library.carol.delete_presentation(library.statins.id, method=method))

    assert library.statins.path.stat().st_size == STATINS_BYTES
    assert STATINS in library.listed()
    assert library.running.versions(library.statins) != []
    assert library.storage() == storage
    assert library.lines() == lines


def test_e2e_025_a_link_to_a_deleted_presentation_is_refused(library: Library) -> None:
    link = library.carol.open_presentation(library.statins.id)
    assert link.status == 200

    assert library.dan.delete_presentation(library.statins.id).status == 200

    refusal = library.carol.open_presentation(library.statins.id)
    denied(refusal)
    assert len(library.listed()) == 2


@pytest.mark.parametrize("target", ["0" * 32, "../../etc/passwd", "ABCDEF" * 5 + "AB", "x"])
def test_an_unknown_or_malformed_id_is_the_same_refusal_for_a_writer_and_the_administrator(
    library: Library, target: str
) -> None:
    storage, lines = library.storage(), library.lines()
    admin = signed_in(library.running, library.google, ADMIN)

    for person in (library.dan, admin):
        reply = person.delete_presentation(target)
        assert reply.status in {403, 404}
        assert reply.status == 403 or "Access denied" not in reply.text
    assert library.storage() == storage
    assert library.lines() == lines


def test_a_second_delete_and_a_person_with_no_role_get_access_denied(library: Library, fake_google: FakeGoogle) -> None:
    other = signed_in(library.running, fake_google, BOB)
    denied(other.delete_presentation(library.statins.id))
    assert library.dan.delete_presentation(library.statins.id).status == 200
    lines = library.lines()

    denied(library.dan.delete_presentation(library.statins.id))

    assert library.lines() == lines  # the refused second deletion writes nothing


def test_e2e_088_a_member_entry_cannot_reduce_the_administrator(library: Library, fake_google: FakeGoogle) -> None:
    library.running.builder.member(library.ids[CARDIOLOGY], ADMIN, "RO")
    admin = signed_in(library.running, fake_google, ADMIN)
    arrhythmia = library.decks["Arrhythmia Basics"]

    assert admin.delete_presentation(arrhythmia.id).status == 200

    assert "Arrhythmia Basics" not in library.listed()
    home = admin.open("/").text
    assert "Admin" in home
    assert "Read only" not in home


def test_e2e_140_refused_attempts_are_not_recorded(library: Library, fake_google: FakeGoogle) -> None:
    library.carol.upload(library.ids[CARDIOLOGY], "Hand Made.html", valid_deck())
    denied(library.carol.delete_presentation(library.statins.id))
    bob = signed_in(library.running, fake_google, BOB)
    assert bob.open("/").status == 403

    assert library.dan.upload(library.ids[CARDIOLOGY], "Quarterly Review.html", valid_deck()).status == 201

    assert library.lines() == [f'Uploaded "Quarterly Review" in "{CARDIOLOGY}"']
    assert library.running.stored.activity()[-1][2] == DAN


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://slides.scm-platform.org.evil.example"},
        {"Origin": "http://evil.example"},
        {"Origin": "null"},
        {"Origin": ""},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
    ids=["look-alike", "other-site", "null-origin", "no-origin", "cross-site", "same-site"],
)
def test_e2e_182_a_look_alike_site_and_every_foreign_origin_is_another_site(
    library: Library, headers: dict[str, str]
) -> None:
    """E2E-182: the session is valid, the origin is not the library's: ``Access denied.`` and nothing is deleted."""
    storage, lines = library.storage(), library.lines()
    sent = {"Origin": library.running.origin, "Sec-Fetch-Site": "same-origin", **headers}
    sent = {name: value for name, value in sent.items() if value != ""}

    for method in ("DELETE", "POST"):
        denied(library.dan.delete_presentation(library.statins.id, method=method, headers=sent))

    assert STATINS in library.listed()
    assert library.storage() == storage
    assert library.lines() == lines


def test_a_save_that_lost_the_race_with_a_deletion_creates_nothing(library: Library) -> None:
    """DEC-028: Dan holds the grant, the presentation is deleted, his save is refused and no file comes back."""
    library.dan.open_presentation(library.statins.id)
    html_text = library.statins.path.read_text(encoding="utf-8")
    assert library.dan.delete_presentation(library.statins.id).status == 200
    storage = library.storage()

    reply = library.dan.save(library.statins.id, html_text)

    assert reply.status == 403
    assert reply.json() == {"error": DENIED, "code": "denied"}
    assert library.storage() == storage
    assert not library.statins.path.exists()
