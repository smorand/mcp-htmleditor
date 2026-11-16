"""US-0133: opening a presentation through a ticket and a grant, over HTTP (SPEC-0025).

Spec tests: E2E-026, E2E-035, E2E-102, E2E-123, E2E-148, E2E-185, E2E-187, E2E-SEC-020, E2E-SEC-021. A person
follows ``/open/<pid>`` (library origin, a ``302`` to ``/enter?t=`` on the content origin, then ``/d/<pid>/``) and
reads ``/d/<pid>/content-frame``, ``/status`` and ``/download`` with the grant cookie the ``Browser`` keeps by path.
The second channel is the stored library: the presentation file (``sha256``) and the ``sessions``, ``tickets`` and
``grants`` tables read directly. The editor shell ``/d/<pid>/`` arrives with US-0134: here it is still a path under
``/d/<pid>/`` that no row serves.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

import pytest

from mcp_htmleditor.http_server import _EditorHandler
from mcp_htmleditor.library import pages
from mcp_htmleditor.library.signin import Live, NoGrant
from mcp_htmleditor.version import __version__
from tests import library_support
from tests.library_support import (
    ADMIN,
    BOB,
    BRIDGING,
    CARDIOLOGY,
    CAROL,
    DAN,
    HEART_FAILURE,
    PNEUMO,
    WCBIP,
    Browser,
    FakeGoogle,
    LibraryReply,
    Presentation,
    RunningLibrary,
    signed_in,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
HEART_FAILURE_BYTES = 2_097_152
DENIED = {"error": "Access denied.", "code": "denied"}
EXPIRED = {"error": "Your session has expired. Sign in again to save.", "code": "session_expired"}
STATUS_KEYS = {
    "mtime",
    "update_in_progress",
    "update_expires_in",
    "filename",
    "poll_interval",
    "port",
    "requests_revision",
}
HEALTH = {"ok": True, "status": "ok", "version": __version__}
TICKET_SECONDS = 60
SESSION_SECONDS = 2_592_000
DECK_MARKER = b"<!--xxxxxxxx"  # the padding of every generated deck: a received deck byte run holds it


@dataclass(frozen=True)
class Standard:
    """The standard folders and members, "Heart Failure Update" (2 MiB) in "Cardiology 2027" and "Bridging the
    Gap" in "WCBIP Melbourne Décembre 2026"."""

    running: RunningLibrary
    google: FakeGoogle
    ids: dict[str, str]
    heart: Presentation
    bridging: Presentation

    def person(self, email: str) -> Browser:
        return signed_in(self.running, self.google, email)


@pytest.fixture
def standard(library_server: START, fake_google: FakeGoogle) -> Iterator[Standard]:
    running = library_server(fake_google)
    yield build_standard(running, fake_google)


def build_standard(running: RunningLibrary, google: FakeGoogle) -> Standard:
    ids = running.builder.standard()
    heart = running.builder.presentation(
        ids[CARDIOLOGY], HEART_FAILURE, size=HEART_FAILURE_BYTES, modified=MODIFIED, slides=8
    )
    bridging = running.builder.presentation(ids[WCBIP], BRIDGING, size=8_192, modified=MODIFIED, slides=3)
    return Standard(running, google, ids, heart, bridging)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def follow_sign_in_link(browser: Browser, page: LibraryReply, google: FakeGoogle, email: str) -> LibraryReply:
    """Choose ``Sign in with Google`` on the sign in page shown, then ``email`` at Google."""
    link = re.search(r'<a href="([^"]*)">Sign in with Google</a>', page.text)
    assert link is not None, page.text[:300]
    google.choose(email)
    return browser.open(html.unescape(link.group(1)))


def answer_of(reply: LibraryReply) -> Any:
    """The JSON of an answer that must be JSON (an assertion failure otherwise, with the status and the start)."""
    assert reply.headers.get("content-type") == "application/json", (reply.status, reply.text[:200])
    return reply.json()


def location_of(reply: LibraryReply) -> str:
    """The ``Location`` of an answer that must be a redirect."""
    assert reply.status in {302, 303, 308}, (reply.status, reply.text[:200])
    return reply.headers["location"]


def assert_is_deck(reply: LibraryReply, presentation: Presentation) -> None:
    assert reply.status == 200
    assert reply.body == presentation.path.read_bytes()


# ---------------------------------------------------------------------------
# The way in: ticket, grant, deck frame, download, status
# ---------------------------------------------------------------------------


def test_library_open_a_viewer_reads_the_frame_status_and_download(standard: Standard) -> None:
    """FR-NEW-022, FR-NEW-025, DEC-037: Carol (RO) reaches the deck through a ticket and a grant; the downloaded
    HTML is the stored file byte for byte."""
    carol = standard.person(CAROL)
    before = len(carol.visited)

    carol.open_presentation(standard.heart.id)
    path = [address.split("?")[0] for address in carol.visited[before:]]
    frame = carol.deck(standard.heart.id, "content-frame")
    download = carol.deck(standard.heart.id, "download")
    content = carol.deck(standard.heart.id, "content")

    content_origin = standard.running.content_origin
    assert path == [
        f"{standard.running.origin}/open/{standard.heart.id}",
        f"{content_origin}/enter",
        f"{content_origin}/d/{standard.heart.id}/",
    ]
    assert carol.grant(standard.heart.id) is not None
    assert_is_deck(frame, standard.heart)
    assert_is_deck(content, standard.heart)
    assert download.status == 200
    assert sha256(download.body) == sha256(standard.heart.path.read_bytes())
    assert len(download.body) == HEART_FAILURE_BYTES


def test_library_open_the_ticket_redirects_and_the_grant_cookie(standard: Standard) -> None:
    """DEC-037: ``/open`` gives ``302 <content origin>/enter?t=``, ``/enter`` sets the grant cookie scoped to the
    presentation (HttpOnly, SameSite Lax, no Max-Age) and ``302 /d/<pid>/``; no token in any body or address."""
    carol = standard.person(CAROL)
    pid = standard.heart.id

    opened = carol.open(f"{standard.running.origin}/open/{pid}", follow=False)
    location = location_of(opened)
    entered = carol.open(location, follow=False)

    assert opened.status == 302
    assert re.fullmatch(rf"{re.escape(standard.running.content_origin)}/enter\?t=[A-Za-z0-9_-]{{43}}", location)
    assert entered.status == 302
    assert location_of(entered) == f"/d/{pid}/"
    assert len(entered.set_cookies) == 1
    token = carol.grant(pid)
    assert token is not None and len(token) == 43
    assert entered.set_cookies[0] == f"d={token}; Path=/d/{pid}/; HttpOnly; SameSite=Lax"
    for reply in (opened, entered):
        assert token not in reply.text
        assert token not in reply.headers.get("location", "")
    assert [row[2] for row in standard.running.stored.grants()] == [pid]
    assert standard.running.stored.tickets() == []  # the ticket was deleted when redeemed


def test_library_open_tickets_are_single_use_and_live_60_seconds(standard: Standard) -> None:
    """DEC-037 with the FakeClock: a redeemed ticket gives nothing the second time; a ticket redeemed at 60 s or
    later gives ``302`` to the library home page and no grant."""
    carol = standard.person(CAROL)
    pid = standard.heart.id

    first = location_of(carol.open(f"{standard.running.origin}/open/{pid}", follow=False))
    assert carol.open(first, follow=False).status == 302
    replayed = carol.copied()
    replayed.deck_cookies.clear()
    again = replayed.open(first, follow=False)
    late = location_of(carol.open(f"{standard.running.origin}/open/{pid}", follow=False))
    standard.running.clock.advance(TICKET_SECONDS)
    expired = replayed.open(late, follow=False)

    for reply in (again, expired):
        assert (reply.status, location_of(reply)) == (302, f"{standard.running.origin}/")
        assert reply.set_cookies == ()
    assert replayed.grant(pid) is None
    assert len(standard.running.stored.grants()) == 1


def test_library_open_ticket_and_grant_units(standard: Standard) -> None:
    """``issue_ticket``, ``redeem_ticket`` and ``grant_for`` with the FakeClock: single use, 60 s, Live while the
    session lives, Ended after its end or for another presentation, Absent without a cookie."""
    accounts = standard.running.server.accounts
    carol = standard.person(CAROL)
    session = accounts.session_for(carol.cookies["lib"])
    assert session is not None
    pid, other = standard.heart.id, standard.bridging.id

    ticket = accounts.issue_ticket(session, pid)
    grant = accounts.redeem_ticket(ticket)
    stale = accounts.issue_ticket(session, pid)
    standard.running.clock.advance(TICKET_SECONDS - 0.5)
    fresh = accounts.redeem_ticket(stale)
    late = accounts.issue_ticket(session, pid)
    standard.running.clock.advance(TICKET_SECONDS)

    assert grant is not None
    assert (grant.presentation_id, grant.session_expires_at) == (pid, session.expires_at)
    assert accounts.redeem_ticket(ticket) is None
    assert fresh is not None
    assert accounts.redeem_ticket(late) is None
    assert accounts.redeem_ticket("not-a-ticket") is None
    assert accounts.grant_for(pid, grant.token) == Live(CAROL)
    assert accounts.grant_for(other, grant.token) is NoGrant.ENDED
    assert accounts.grant_for(pid, "forged") is NoGrant.ENDED
    assert accounts.grant_for(pid, None) is NoGrant.ABSENT
    assert accounts.grant_for(pid, "") is NoGrant.ABSENT
    standard.running.clock.now = session.expires_at
    assert accounts.grant_for(pid, grant.token) is NoGrant.ENDED


def test_library_open_frame_headers_and_unserved_paths(standard: Standard, monkeypatch: pytest.MonkeyPatch) -> None:
    """The deck frame may be framed by its own origin only; DOCX export and any other path under ``/d/<pid>/``
    are ``Access denied.`` for every role, and the library never serves a file next to the deck (SPEC-0023)."""
    served: list[str] = []
    monkeypatch.setattr(_EditorHandler, "_serve_deck_file", lambda _self, raw: served.append(raw))
    pid = standard.heart.id
    frames = []
    for email in (CAROL, DAN, ADMIN):
        person = standard.person(email)
        person.open_presentation(pid)
        frames.append(person.deck(pid, "content-frame"))
        for route in ("export/docx", "picture.png", "", "content-frame/x", "assets/a.css"):
            reply = person.deck(pid, route)
            assert (reply.status, answer_of(reply)) == (403, DENIED), (email, route)
            assert answer_of(person.deck(pid, route, x_editor="1")) == DENIED

    for frame in frames:
        assert frame.headers["x-frame-options"] == "SAMEORIGIN"
        assert frame.headers["content-security-policy"] == "frame-ancestors 'self'"
        assert frame.headers["content-type"] == "text/html"
    status = person.deck(pid, "status")
    assert status.headers["x-frame-options"] == "DENY"
    assert status.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert served == []


def test_library_open_status_revision_follows_the_edit_permission(standard: Standard) -> None:
    """DEC-041: Dan (RW) reads the request revision; Carol (RO) reads 0 so her editor never asks for the list."""
    standard.running.builder.records(standard.heart)
    carol, dan = standard.person(CAROL), standard.person(DAN)
    for person in (carol, dan):
        person.open_presentation(standard.heart.id)

    carol_status = answer_of(carol.deck(standard.heart.id, "status"))
    dan_status = answer_of(dan.deck(standard.heart.id, "status"))

    assert carol_status["requests_revision"] == 0
    assert dan_status["requests_revision"] > 0
    assert {key: value for key, value in dan_status.items() if key != "requests_revision"} == {
        key: value for key, value in carol_status.items() if key != "requests_revision"
    }


def test_library_open_a_removed_member_with_a_live_grant_is_refused(standard: Standard) -> None:
    """DEC-018, DEC-040: the role is read at every request; a navigation route sends the person back to ``/open``
    (``Access denied.``), a fetch route answers the denied JSON."""
    carol = standard.person(CAROL)
    carol.open_presentation(standard.heart.id)
    with standard.running.database.transaction(immediate=True) as connection:
        connection.execute("DELETE FROM members WHERE email = ?", (CAROL,))

    status = carol.deck(standard.heart.id, "status")
    status_editor = carol.deck(standard.heart.id, "status", x_editor="1")
    download = carol.deck(standard.heart.id, "download")
    frame = carol.deck(standard.heart.id, "content-frame", follow=True)

    assert (status.status, answer_of(status)) == (403, DENIED)
    assert (status_editor.status, answer_of(status_editor)) == (403, DENIED)
    assert (download.status, location_of(download)) == (302, f"{standard.running.origin}/open/{standard.heart.id}")
    assert (frame.status, frame.body) == (403, pages.access_denied())


def test_library_open_an_unreadable_library_gives_the_unavailable_page(standard: Standard) -> None:
    """DEC-024 on the content origin: the grant cannot be read, so no deck byte and the unavailable page."""
    carol = standard.person(CAROL)
    carol.open_presentation(standard.heart.id)

    with standard.running.unreadable_database():
        replies = [carol.deck(standard.heart.id, route) for route in ("content-frame", "download", "status")]
    after = carol.deck(standard.heart.id, "download")

    for reply in replies:
        assert (reply.status, reply.body) == (503, pages.library_unavailable())
    assert after.body == standard.heart.path.read_bytes()


# ---------------------------------------------------------------------------
# Spec tests
# ---------------------------------------------------------------------------


def test_e2e_026_a_direct_link_signed_in_with_an_unauthorized_account(standard: Standard) -> None:
    """E2E-026: Bob follows the link to "Heart Failure Update", signs in: ``Access denied.``, no slide, no folder."""
    bob = standard.running.browser()

    page = bob.open(f"/open/{standard.heart.id}")
    arrived = follow_sign_in_link(bob, page, standard.google, BOB)

    assert page.body == pages.sign_in_page(f"/open/{standard.heart.id}", None)
    assert (arrived.status, arrived.body) == (403, pages.access_denied())
    assert bob.url == f"{standard.running.origin}/open/{standard.heart.id}"
    for text in (HEART_FAILURE, CARDIOLOGY, "Slide 2"):
        assert text not in arrived.text
    assert all(standard.running.content_netloc not in address for address in bob.visited)
    assert standard.running.stored.tickets() == []


def test_e2e_035_a_download_keeps_an_accented_name_with_an_apostrophe(standard: Standard) -> None:
    """E2E-035: Carol downloads "L'été (v2)": the file is named "L'été (v2).html" and is the stored file."""
    summer = standard.running.builder.presentation(
        standard.ids[CARDIOLOGY], "L'été (v2)", size=4_096, modified=MODIFIED
    )
    carol = standard.person(CAROL)
    carol.open_presentation(summer.id)

    download = carol.deck(summer.id, "download")

    assert "content-disposition" in download.headers, (download.status, download.text[:200])
    disposition = download.headers["content-disposition"]
    encoded = re.search(r"filename\*=UTF-8''(\S+)$", disposition)
    assert encoded is not None, disposition
    assert unquote(encoded.group(1)) == "L'été (v2).html"
    assert disposition.startswith('attachment; filename="')
    assert download.body == summer.path.read_bytes()
    assert summer.id not in disposition


def test_e2e_102_a_former_member_is_refused_after_the_folder_is_deleted(standard: Standard) -> None:
    """E2E-102: "Pneumo Été" deleted while Dan had its folder page open: choosing its presentation gives
    ``Access denied.`` and his home page lists only "Cardiology 2027"."""
    running = standard.running
    running.builder.member(standard.ids[PNEUMO], DAN, "RW")
    spirometry = running.builder.presentation(standard.ids[PNEUMO], "Spirometry Basics", size=4_096, modified=MODIFIED)
    dan = standard.person(DAN)
    folder_page = dan.open(f"/f/{standard.ids[PNEUMO]}")
    dan.open_presentation(spirometry.id)
    assert "Spirometry Basics" in folder_page.text
    admin = standard.person(ADMIN)
    assert admin.post_json(f"/api/folders/{standard.ids[PNEUMO]}/delete", {"confirm": PNEUMO}).status == 200

    chosen = dan.open_presentation(spirometry.id)
    status = dan.deck(spirometry.id, "status")
    home = dan.open(f"{running.origin}/")

    assert (chosen.status, chosen.body) == (403, pages.access_denied())
    assert (status.status, answer_of(status)) == (403, DENIED)  # a live grant on a gone presentation: never sign in
    assert [html.unescape(name) for _, name, _ in home.folder_rows()] == [CARDIOLOGY]


def test_e2e_123_a_presentation_of_another_folder_cannot_be_reached_by_its_address(standard: Standard) -> None:
    """E2E-123: Dan (RW in "Cardiology 2027" only) types the address of "Bridging the Gap", then the same name
    under "Cardiology 2027": both are the same ``Access denied.``; no slide, no title of it appears anywhere."""
    dan = standard.person(DAN)
    dan.open_presentation(standard.heart.id)
    heart_grant = dan.grant(standard.heart.id)
    bridging = standard.bridging.id

    typed = dan.open_presentation(bridging)
    under_cardiology = dan.open(f"{standard.running.origin}/f/{standard.ids[CARDIOLOGY]}/Bridging%20the%20Gap")
    frame = dan.deck(bridging, "content-frame", follow=True)
    tool = standard.running.client(standard.running.content_netloc)
    borrowed = [
        tool.get(f"/d/{bridging}/{route}", cookie=f"d={heart_grant}", **extra)
        for route in ("content-frame", "download", "status", "content")
        for extra in ({}, {"x_editor": "1"})
    ]

    assert (typed.status, typed.body) == (403, pages.access_denied())
    assert (under_cardiology.status, under_cardiology.body) == (typed.status, typed.body)
    assert (frame.status, frame.body) == (typed.status, typed.body)
    for reply in borrowed:
        assert reply.status in {302, 401}
        assert reply.status == 401 or location_of(reply) == f"{standard.running.origin}/open/{bridging}"
    for reply in [typed, under_cardiology, frame, *borrowed, *dan.replies]:
        assert BRIDGING not in reply.text
        assert DECK_MARKER not in reply.body or reply.body == standard.heart.path.read_bytes()
    assert dan.grant(bridging) is None


def test_e2e_148_a_plain_direct_link_keeps_its_destination(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-148: Carol opens the plain form of the link: the secure form of the same link, then after signing in
    the presentation."""
    running = library_server(fake_google, scheme="https")
    standard = build_standard(running, fake_google)
    carol = running.browser()
    pid = standard.heart.id
    secure_link = f"https://{running.library_netloc}/open/{pid}"

    page = carol.open(f"http://{running.library_netloc}/open/{pid}")
    follow_sign_in_link(carol, page, fake_google, CAROL)
    frame = carol.deck(pid, "content-frame")

    assert carol.visited[:2] == [f"http://{running.library_netloc}/open/{pid}", secure_link]
    assert page.body == pages.sign_in_page(f"/open/{pid}", None)
    assert secure_link in carol.visited[2:]
    assert carol.deck_cookies.keys() == {(f"/d/{pid}/", "__Secure-d")}
    assert_is_deck(frame, standard.heart)
    assert f"<title>{HEART_FAILURE}</title>" in frame.text
    entered = next(reply for reply in carol.replies if reply.set_cookies and "__Secure-d" in reply.set_cookies[0])
    assert entered.set_cookies[0].endswith(f"; Path=/d/{pid}/; HttpOnly; SameSite=Lax; Secure")


def test_e2e_185_signing_out_in_one_tab_ends_the_session_in_the_other(standard: Standard) -> None:
    """E2E-185: two tabs of the folder page; Sign out in the first; choosing "Heart Failure Update" in the second
    shows the sign in page, not the presentation."""
    carol = standard.person(CAROL)
    first_tab = carol.open(f"/f/{standard.ids[CARDIOLOGY]}")
    second_tab = carol.open(f"/f/{standard.ids[CARDIOLOGY]}")
    assert HEART_FAILURE in first_tab.text and HEART_FAILURE in second_tab.text
    carol.sign_out()
    visited_before = len(carol.visited)

    chosen = carol.open_presentation(standard.heart.id)

    assert (chosen.status, chosen.body) == (200, pages.sign_in_page(f"/open/{standard.heart.id}", None))
    assert all(standard.running.content_netloc not in address for address in carol.visited[visited_before:])
    assert standard.running.stored.tickets() == []


def test_e2e_187_a_status_is_shown_only_to_a_person_with_a_right(standard: Standard) -> None:
    """E2E-187: Carol (RO in "Cardiology 2027") reads the status of "Heart Failure Update" (the change marker, no
    storage location) and gets ``Access denied.`` for "Bridging the Gap"; a visitor gets the sign in page."""
    carol = standard.person(CAROL)
    carol.open_presentation(standard.heart.id)
    visitor = standard.running.browser()

    status = carol.deck(standard.heart.id, "status")
    other = carol.deck(standard.bridging.id, "status", follow=True)
    visitor_replies = [visitor.deck(pid, "status", follow=True) for pid in (standard.heart.id, standard.bridging.id)]

    answer = answer_of(status)
    assert status.status == 200
    assert answer.keys() == STATUS_KEYS
    assert answer["mtime"] == standard.heart.path.stat().st_mtime == MODIFIED.timestamp()
    assert answer["filename"] == f"{HEART_FAILURE}.html"
    assert (answer["update_in_progress"], answer["update_expires_in"], answer["port"]) == (False, None, 0)
    assert answer["requests_revision"] == 0
    assert answer["poll_interval"] == standard.running.settings.poll_interval
    for location in (str(standard.running.library_dir), str(standard.running.state_dir), standard.heart.id, CARDIOLOGY):
        assert location not in status.text
    assert (other.status, other.body) == (403, pages.access_denied())
    for reply, pid in zip(visitor_replies, (standard.heart.id, standard.bridging.id), strict=True):
        assert (reply.status, reply.body) == (200, pages.sign_in_page(f"/open/{pid}", None))


def test_e2e_sec_020_a_session_copied_before_sign_out_is_used_after_it(standard: Standard) -> None:
    """E2E-SEC-020. Red before the fix because: the copy is still accepted after Sign out; the assertion "the tool
    received no byte of Heart Failure Update" fails with 2 097 152 bytes."""
    carol = standard.person(CAROL)
    carol.open_presentation(standard.heart.id)
    assert carol.deck(standard.heart.id, "download").body == standard.heart.path.read_bytes()
    tool = carol.copied()
    carol.sign_out()
    pid = standard.heart.id

    answers = [
        tool.open_presentation(pid),
        tool.deck(pid, "download", follow=True),
        tool.deck(pid, "content-frame", follow=True),
        tool.deck(pid, "content", follow=True),
        tool.deck(pid, "status", follow=True),
    ]
    editor_status = tool.deck(pid, "status", x_editor="1")
    carol_view = carol.deck(pid, "download", follow=True)

    for answer in [*answers, carol_view]:
        assert (answer.status, answer.body) == (200, pages.sign_in_page(f"/open/{pid}", None))
    assert (editor_status.status, answer_of(editor_status)) == (401, EXPIRED)
    received = sum(len(reply.body) for reply in tool.replies if DECK_MARKER in reply.body)
    assert received == 0, f"the tool received {received} bytes of {HEART_FAILURE}"
    assert all("content-disposition" not in reply.headers for reply in tool.replies)
    stored = standard.running.stored
    assert [row for row in stored.sessions() if row[1] == CAROL] == []
    assert (stored.grants(), stored.tickets()) == ([], [])


def test_e2e_sec_021_a_visitor_reads_the_liveness_and_status_answers(standard: Standard) -> None:
    """E2E-SEC-021. Red before the fix because: the liveness answer names the loaded file; the assertion "nothing
    received holds a file location or Heart Failure Update" fails and shows the path."""
    running = standard.running
    visitor = running.browser()
    pid = standard.heart.id

    liveness = running.client().get("/health")
    status = visitor.deck(pid, "status", follow=True)
    editor_status = visitor.deck(pid, "status", x_editor="1")
    operator = running.client(f"127.0.0.1:{running.port}").get("/health")

    assert answer_of(liveness) == HEALTH
    assert (status.status, status.body) == (200, pages.sign_in_page(f"/open/{pid}", None))
    assert (editor_status.status, answer_of(editor_status)) == (401, EXPIRED)
    process = re.compile(rf"(?<![0-9a-f]){os.getpid()}(?![0-9a-f])")
    for reply in [liveness, *visitor.replies, editor_status]:
        for secret in (str(running.library_dir), str(running.state_dir), str(standard.heart.path), HEART_FAILURE):
            assert secret not in reply.text
        assert CARDIOLOGY not in reply.text
        assert process.search(reply.text) is None
    assert (operator.status, answer_of(operator)) == (200, HEALTH)
