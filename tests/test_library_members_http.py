"""US-0132: members and roles of a folder over HTTP (SPEC-0025).

Spec tests: E2E-002, E2E-011, E2E-110, E2E-111, E2E-112, E2E-113, E2E-115, E2E-160, E2E-161, E2E-176. People sign
in through ``FakeGoogle``; ``Browser.add_member`` and ``Browser.remove_member`` send what the ``Members`` controls of
the administration page send. The second channel is the operator view (``members`` and ``activity`` read directly),
the administrator's member list on the administration page and the member's own next page.
"""

from __future__ import annotations

import html
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from mcp_htmleditor.library import pages
from mcp_htmleditor.library.access import Role
from mcp_htmleditor.library.store import FolderView, MemberView
from tests import library_support
from tests.library_support import (
    ADMIN,
    BOB,
    CARDIOLOGY,
    CAROL,
    DAN,
    HEART_FAILURE,
    LAMYA,
    PNEUMO,
    WCBIP,
    Browser,
    FakeGoogle,
    LibraryReply,
    RunningLibrary,
    signed_in,
    visible_texts,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

INVALID_ADDRESS = "This is not a valid email address."
INVALID_ROLE = "This is not a valid role."
ADMIN_PATH = "/admin"
READ_WRITE = "Read and write"
READ_ONLY = "Read only"
SESSION_SECONDS = 2_592_000
MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)


def assert_access_denied(reply: LibraryReply) -> None:
    """Exactly the one refusal page: the text and the Sign out button, nothing else (DEC-023)."""
    assert (reply.status, reply.body) == (403, pages.access_denied())
    assert visible_texts(reply) == ["Access denied.", "Sign out"]


def assert_refused(reply: LibraryReply, error: str) -> None:
    assert (reply.status, reply.headers.get("content-type")) == (400, "application/json"), reply.text
    assert reply.json() == {"ok": False, "error": error}


def assert_done(reply: LibraryReply) -> None:
    assert (reply.status, reply.headers.get("content-type")) == (200, "application/json"), reply.text
    assert reply.json() == {"ok": True}


def home_rows(browser: Browser) -> list[tuple[str, str]]:
    """``(folder name, role label)`` of each row of the person's home page."""
    return [(html.unescape(name), role) for _, name, role in browser.open("/").folder_rows()]


def members_shown(admin: Browser, folder_id: str) -> list[tuple[str, str]]:
    """The member list of a folder as the administrator sees it."""
    return admin.open(ADMIN_PATH).member_rows(folder_id)


def stored_members(running: RunningLibrary, folder_id: str) -> list[tuple[str, str]]:
    return [(email, role) for folder, email, role in running.stored.members() if folder == folder_id]


def activity_texts(running: RunningLibrary) -> list[str]:
    return [row[3] for row in running.stored.activity()]


def standard(library_server: START, google: FakeGoogle) -> tuple[RunningLibrary, dict[str, str], Browser]:
    """The standard library and the administrator signed in."""
    running = library_server(google)
    ids = running.builder.standard()
    return running, ids, signed_in(running, google, ADMIN)


# ---------------------------------------------------------------------------
# E2E-002, E2E-011, E2E-115: a role given or taken applies to the next page
# ---------------------------------------------------------------------------


def test_e2e_002_an_account_with_no_right_is_let_in_at_its_next_page_once_added(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-002: Bob sees only ``Access denied.`` and ``Sign out``; the administrator adds ``Bob.Nobody@Gmail.com ``
    as RO to "Cardiology 2027"; Bob's next page, with no new sign in, is the home page with that folder; the members
    table holds one row ``bob.nobody@gmail.com`` RO; Sign out shows the sign in page; every text was English."""
    running, ids, admin = standard(library_server, fake_google)
    running.builder.presentation(ids[CARDIOLOGY], HEART_FAILURE, size=4_096, modified=MODIFIED)
    bob = signed_in(running, fake_google, BOB)
    refused = bob.replies[-1]

    assert_access_denied(refused)
    for name in (CARDIOLOGY, PNEUMO, WCBIP, html.escape(PNEUMO), HEART_FAILURE):
        assert name not in refused.text, name

    assert_done(admin.add_member(ids[CARDIOLOGY], "Bob.Nobody@Gmail.com ", "RO"))

    home = bob.open("/")
    assert home.status == 200
    assert home_rows(bob) == [(CARDIOLOGY, READ_ONLY)]
    assert [row for row in running.stored.members() if row[1] not in {DAN, CAROL, LAMYA}] == [
        (ids[CARDIOLOGY], BOB, "RO")
    ]
    assert len(fake_google.requests_to("/authorize")) == 2  # the administrator's and Bob's only sign in
    signed_out = bob.sign_out()
    assert visible_texts(signed_out) == ["Slides", "Sign in with Google"]
    seen = {text for reply in (refused, home, signed_out) for text in visible_texts(reply)}
    assert seen == {
        "Access denied.",
        "Sign out",
        "Slides",
        CARDIOLOGY,
        READ_ONLY,
        "1 presentation",
        "Sign in with Google",
    }


def test_e2e_002_the_account_chooser_lets_the_same_browser_pick_another_account(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-002 second run: each sign in asks Google for its account chooser; picking Bob shows ``Access denied.``,
    picking Lamya in the same browser shows her folder."""
    running = library_server(fake_google)
    running.builder.standard()
    browser = running.browser()

    assert_access_denied(browser.sign_in(fake_google, BOB))
    lamya = browser.sign_in(fake_google, LAMYA)

    assert lamya.status == 200 and home_rows(browser) == [(WCBIP, READ_WRITE)]
    prompts = [request.params.get("prompt") for request in fake_google.requests_to("/authorize")]
    assert prompts == ["select_account", "select_account"]


def test_e2e_011_a_person_removed_while_signed_out_is_refused_after_signing_in_again(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-011: Dan's session expired, then the administrator removed him from "Cardiology 2027", his only folder;
    signing in again shows ``Access denied.`` and no folder; the member list shows only Carol."""
    running = library_server(fake_google)
    ids = running.builder.standard()
    dan = signed_in(running, fake_google, DAN)
    running.clock.advance(SESSION_SECONDS)
    admin = signed_in(running, fake_google, ADMIN)

    assert_done(admin.remove_member(ids[CARDIOLOGY], DAN))

    assert "Sign in with Google" in dan.open("/").text  # the expired session is a visitor's view
    again = dan.sign_in(fake_google, DAN)
    assert_access_denied(again)
    for name in (CARDIOLOGY, PNEUMO, WCBIP):
        assert name not in again.text
    assert members_shown(admin, ids[CARDIOLOGY]) == [(CAROL, READ_ONLY)]
    assert activity_texts(running) == [f'Removed {DAN} from "{CARDIOLOGY}"']


def test_e2e_115_a_trimmed_address_gives_access_without_a_new_sign_in(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-115: " bob.nobody@gmail.com " is accepted, stored and shown without the spaces; Bob's next page lists
    "Cardiology 2027" labelled "Read only"."""
    running, ids, admin = standard(library_server, fake_google)
    bob = signed_in(running, fake_google, BOB)
    assert_access_denied(bob.replies[-1])

    assert_done(admin.add_member(ids[CARDIOLOGY], " bob.nobody@gmail.com ", "RO"))

    assert home_rows(bob) == [(CARDIOLOGY, READ_ONLY)]
    assert members_shown(admin, ids[CARDIOLOGY]) == [(BOB, READ_ONLY), (CAROL, READ_ONLY), (DAN, READ_WRITE)]
    assert f'<span class="email">{BOB}</span>' in admin.open(ADMIN_PATH).text
    assert activity_texts(running) == [f'Added {BOB} as RO to "{CARDIOLOGY}"']


# ---------------------------------------------------------------------------
# E2E-113, E2E-160, FR-NEW-047: one entry per address and folder, changes stay in their folder
# ---------------------------------------------------------------------------


def test_e2e_113_an_address_in_other_letter_case_with_another_role_updates_the_entry(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-113: "DAN.RW@Example.org" as "Read only" leaves one entry, ``dan.rw@example.org`` RO; Dan's next page
    labels the folder "Read only"; the line ``Changed dan.rw@example.org to RO in "Cardiology 2027"`` is added."""
    running, ids, admin = standard(library_server, fake_google)
    dan = signed_in(running, fake_google, DAN)
    assert home_rows(dan) == [(CARDIOLOGY, READ_WRITE)]

    assert_done(admin.add_member(ids[CARDIOLOGY], "DAN.RW@Example.org", "RO"))

    assert stored_members(running, ids[CARDIOLOGY]) == [(CAROL, "RO"), (DAN, "RO")]
    assert members_shown(admin, ids[CARDIOLOGY]) == [(CAROL, READ_ONLY), (DAN, READ_ONLY)]
    assert home_rows(dan) == [(CARDIOLOGY, READ_ONLY)]
    assert running.server.library.role_in(DAN, ids[CARDIOLOGY]) is Role.RO
    lines = admin.open(ADMIN_PATH).activity_lines()
    assert [(actor, text) for _, actor, text in lines] == [(ADMIN, f'Changed {DAN} to RO in "{CARDIOLOGY}"')]


def test_e2e_160_adding_the_same_address_with_the_same_role_changes_nothing(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-160: "Dan.RW@Example.ORG" then "dan.rw@example.org", both "Read and write", to "Pneumo Été": one entry,
    one line ``Added dan.rw@example.org as RW to "Pneumo Été"``."""
    running, ids, admin = standard(library_server, fake_google)

    assert_done(admin.add_member(ids[PNEUMO], "Dan.RW@Example.ORG", "RW"))
    assert_done(admin.add_member(ids[PNEUMO], DAN, "RW"))

    assert members_shown(admin, ids[PNEUMO]) == [(DAN, READ_WRITE)]
    assert stored_members(running, ids[PNEUMO]) == [(DAN, "RW")]
    assert activity_texts(running) == [f'Added {DAN} as RW to "{PNEUMO}"']


def test_a_change_or_a_removal_applies_to_that_folder_only_and_at_the_next_request(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-047, FR-NEW-048: Dan is RW in two folders; RO in "Cardiology 2027" leaves "Pneumo Été" RW; removed from
    "Pneumo Été" he keeps "Cardiology 2027" RO and his next request to "Pneumo Été" is ``Access denied.``; removing an
    address that is not listed answers ok and writes nothing."""
    running, ids, admin = standard(library_server, fake_google)
    assert_done(admin.add_member(ids[PNEUMO], DAN, "RW"))
    dan = signed_in(running, fake_google, DAN)
    assert dan.open(f"/f/{ids[PNEUMO]}").status == 200

    assert_done(admin.add_member(ids[CARDIOLOGY], DAN, "RO"))
    assert home_rows(dan) == [(CARDIOLOGY, READ_ONLY), (PNEUMO, READ_WRITE)]
    assert_done(admin.remove_member(ids[PNEUMO], " Dan.RW@example.org"))
    assert_done(admin.remove_member(ids[PNEUMO], DAN))

    assert_access_denied(dan.open(f"/f/{ids[PNEUMO]}"))
    assert home_rows(dan) == [(CARDIOLOGY, READ_ONLY)]
    assert members_shown(admin, ids[PNEUMO]) == []
    assert members_shown(admin, ids[CARDIOLOGY]) == [(CAROL, READ_ONLY), (DAN, READ_ONLY)]
    assert activity_texts(running) == [
        f'Added {DAN} as RW to "{PNEUMO}"',
        f'Changed {DAN} to RO in "{CARDIOLOGY}"',
        f'Removed {DAN} from "{PNEUMO}"',
    ]


def test_a_raised_role_applies_from_the_next_request(library_server: START, fake_google: FakeGoogle) -> None:
    """FR-NEW-048: Carol RO to RW shows "Read and write" at her next page; the line reads ``Changed ... to RW``."""
    running, ids, admin = standard(library_server, fake_google)
    carol = signed_in(running, fake_google, CAROL)

    assert_done(admin.add_member(ids[CARDIOLOGY], CAROL, "RW"))

    assert home_rows(carol) == [(CARDIOLOGY, READ_WRITE)]
    assert activity_texts(running) == [f'Changed {CAROL} to RW in "{CARDIOLOGY}"']


def test_the_administrator_address_stored_as_a_member_changes_nothing_for_him(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """DEC-006, FR-NEW-014: the administrator's own address added as RO is stored, he stays Admin everywhere."""
    running, ids, admin = standard(library_server, fake_google)

    assert_done(admin.add_member(ids[PNEUMO], "Seb.Morand@gmail.com", "RO"))

    assert stored_members(running, ids[PNEUMO]) == [(ADMIN, "RO")]
    assert home_rows(admin) == [(CARDIOLOGY, "Admin"), (PNEUMO, "Admin"), (WCBIP, "Admin")]
    assert admin.open(ADMIN_PATH).status == 200


# ---------------------------------------------------------------------------
# E2E-110, E2E-111, E2E-176: the address rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("typed", ["not-an-email", "carol@", ""], ids=["no-at", "no-domain", "empty"])
def test_e2e_110_invalid_addresses_are_refused(library_server: START, fake_google: FakeGoogle, typed: str) -> None:
    """E2E-110: each is "This is not a valid email address."; "Pneumo Été" still has no member, no line."""
    running, ids, admin = standard(library_server, fake_google)

    assert_refused(admin.add_member(ids[PNEUMO], typed, "RW"), INVALID_ADDRESS)

    assert members_shown(admin, ids[PNEUMO]) == []
    assert stored_members(running, ids[PNEUMO]) == [] and activity_texts(running) == []


@pytest.mark.parametrize(
    "typed", ["dan.rw@example.org, carol.ro@example.org", "<b>x</b>@example.org"], ids=["two-addresses", "markup"]
)
def test_e2e_111_two_addresses_or_markup_in_one_field_are_refused(
    library_server: START, fake_google: FakeGoogle, typed: str
) -> None:
    """E2E-111: "This is not a valid email address."; neither address became a member; the markup is in no page."""
    running, ids, admin = standard(library_server, fake_google)

    assert_refused(admin.add_member(ids[PNEUMO], typed, "RW"), INVALID_ADDRESS)

    page = admin.open(ADMIN_PATH)
    assert page.member_rows(ids[PNEUMO]) == [] and "<b>x</b>" not in page.text
    assert stored_members(running, ids[PNEUMO]) == [] and activity_texts(running) == []


def test_e2e_176_a_plus_sign_is_accepted_an_apostrophe_a_missing_dot_and_a_space_are_refused(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-176: "dan+rw@example.org" is added; "o'brien@example.org", "dan@localhost", "dan rw@example.org" are each
    refused; the list holds only dan+rw@example.org."""
    running, ids, admin = standard(library_server, fake_google)

    assert_done(admin.add_member(ids[PNEUMO], "dan+rw@example.org", "RW"))
    for typed in ("o'brien@example.org", "dan@localhost", "dan rw@example.org"):
        assert_refused(admin.add_member(ids[PNEUMO], typed, "RW"), INVALID_ADDRESS)

    assert members_shown(admin, ids[PNEUMO]) == [("dan+rw@example.org", READ_WRITE)]
    assert stored_members(running, ids[PNEUMO]) == [("dan+rw@example.org", "RW")]


@pytest.mark.parametrize("email", [None, 7, ["dan.rw@example.org"]], ids=["null", "number", "list"])
def test_an_address_that_is_not_text_is_not_a_valid_address(
    library_server: START, fake_google: FakeGoogle, email: Any
) -> None:
    """The two routes refuse an address that is not a string with the address text and change nothing."""
    running, ids, admin = standard(library_server, fake_google)

    assert_refused(admin.add_member(ids[PNEUMO], email, "RW"), INVALID_ADDRESS)
    assert_refused(admin.remove_member(ids[CARDIOLOGY], email), INVALID_ADDRESS)

    assert len(running.stored.members()) == 3 and activity_texts(running) == []


# ---------------------------------------------------------------------------
# E2E-112, E2E-161, DEC-019: only RW and RO, only by the administrator, checks in order
# ---------------------------------------------------------------------------


def test_e2e_112_a_rw_member_adding_himself_as_admin_by_hand_is_access_denied(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-112: Dan (RW in "Cardiology 2027") posts himself as "Admin" (and as RW) to "Pneumo Été", and the removal of
    Carol: each is ``Access denied.``; the administrator's list of "Pneumo Été" is still empty, Carol is still listed,
    Dan has no Administration."""
    running, ids, admin = standard(library_server, fake_google)
    dan = signed_in(running, fake_google, DAN)

    for role in ("Admin", "RW"):
        assert_access_denied(dan.add_member(ids[PNEUMO], DAN, role))
    assert_access_denied(dan.add_member(ids[CARDIOLOGY], DAN, "Admin"))
    assert_access_denied(dan.remove_member(ids[CARDIOLOGY], CAROL))

    assert members_shown(admin, ids[PNEUMO]) == []
    assert members_shown(admin, ids[CARDIOLOGY]) == [(CAROL, READ_ONLY), (DAN, READ_WRITE)]
    assert "Administration" not in dan.open("/").text and activity_texts(running) == []


@pytest.mark.parametrize("role", ["Admin", "rw", "Read and write", "", None, 1, ["RW"]])
def test_e2e_161_a_role_other_than_the_two_offered_is_refused(
    library_server: START, fake_google: FakeGoogle, role: Any
) -> None:
    """E2E-161: the administrator sends Dan with the role "Admin" (or any other value): "This is not a valid role.";
    "Pneumo Été" has no member, no line; Dan's home page has no Administration."""
    running, ids, admin = standard(library_server, fake_google)

    assert_refused(admin.add_member(ids[PNEUMO], DAN, role), INVALID_ROLE)

    assert members_shown(admin, ids[PNEUMO]) == []
    assert stored_members(running, ids[PNEUMO]) == [] and activity_texts(running) == []
    dan = signed_in(running, fake_google, DAN)
    assert "Administration" not in dan.open("/").text and home_rows(dan) == [(CARDIOLOGY, READ_WRITE)]


def test_the_checks_run_folder_then_address_then_role(library_server: START, fake_google: FakeGoogle) -> None:
    """DEC-019: an unknown folder id is ``Access denied.`` whatever the payload; then the address before the role."""
    running, _, admin = standard(library_server, fake_google)
    unknown = "0" * 32

    assert_access_denied(admin.add_member(unknown, "not-an-email", "Admin"))
    assert_access_denied(admin.add_member(unknown, DAN, "RW"))
    assert_access_denied(admin.remove_member(unknown, DAN))
    folder_id = running.builder.folder("Oncology 2030")
    assert_refused(admin.add_member(folder_id, "not-an-email", "Admin"), INVALID_ADDRESS)
    assert_refused(admin.add_member(folder_id, DAN, "Admin"), INVALID_ROLE)

    assert stored_members(running, folder_id) == [] and activity_texts(running) == []


def test_a_member_change_without_the_library_origin_is_refused_before_the_session(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """DEC-022: the administrator's own cookie with no ``Origin`` (a form of another site, a copied request) or a
    cross site fetch is ``Access denied.`` and nothing is stored."""
    running, ids, admin = standard(library_server, fake_google)
    cross_site = {**admin.page_post_headers(), "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}

    for headers in ({"Content-Type": "application/json"}, cross_site):
        assert_access_denied(
            admin.post_json(f"/api/folders/{ids[PNEUMO]}/members", {"email": DAN, "role": "RW"}, headers=headers)
        )
        assert_access_denied(
            admin.post_json(f"/api/folders/{ids[CARDIOLOGY]}/members/remove", {"email": CAROL}, headers=headers)
        )

    assert len(running.stored.members()) == 3 and activity_texts(running) == []


def test_the_member_rows_escape_every_address() -> None:
    """DEC-029: an address that holds markup (only possible by hand in the table) is escaped in the page."""
    folder = FolderView(id="a" * 32, name="Cardiology 2027", role=Role.ADMIN)
    member = MemberView(email="<b>x</b>@example.org", role=Role.RO)

    page = pages.admin_page([folder], [], members={folder.id: [member]}).decode()

    assert "<b>" not in page and '<span class="email">&lt;b&gt;x&lt;/b&gt;@example.org</span>' in page
