"""US-0126: sign in with a Google account, stay signed in, sign out (SPEC-0025).

Spec tests: E2E-003, E2E-005, E2E-007, E2E-090, E2E-150, E2E-171, E2E-172, E2E-183, E2E-184 and the exploits
E2E-SEC-015, E2E-SEC-016, E2E-SEC-019. Google is ``FakeGoogle``; the second channel of every "nothing happened"
assertion is the operator view (``StoredLibrary``: sessions, login attempts, folders, activity read directly).
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import secrets
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from mcp_htmleditor import tracing
from mcp_htmleditor.library import pages
from mcp_htmleditor.library.server import cookie_header, cookie_name
from mcp_htmleditor.library.signin import GoogleClient, SignInUnavailable, safe_destination, validate_claims
from mcp_htmleditor.library.store import Database
from tests import library_support
from tests.library_support import (
    ADMIN,
    BOB,
    CARDIOLOGY,
    CAROL,
    DAN,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    LAMYA,
    PNEUMO,
    WCBIP,
    Browser,
    FakeGoogle,
    LibraryReply,
    RecordingListener,
    RunningLibrary,
    free_port,
    pkce_challenge,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
evil_listener = library_support.evil_listener
START = Callable[..., RunningLibrary]

UNAVAILABLE = "Sign-in is unavailable. Try again later."
DENIED = "Access denied."
LIBRARY_NAMES = (WCBIP, CARDIOLOGY, PNEUMO, "Heart Failure Update", "Arrhythmia Basics", "Statins Review")
SESSION_SECONDS = 2_592_000
HOSTILE_DESTINATIONS = (
    "https://evil.example/phish",
    "//evil.example/phish",
    "javascript:alert(1)",
    "https://slides.scm-platform.org@evil.example/x",
    "/\\evil.example",
)


def standard(library_server: START, google: FakeGoogle, **options: Any) -> tuple[RunningLibrary, dict[str, str]]:
    running = library_server(google, **options)
    return running, running.builder.standard()


def assert_unavailable(reply: LibraryReply) -> None:
    """The sign in page carrying the one failure message, and nothing of the library."""
    assert (reply.status, reply.body) == (200, pages.sign_in_page("/", UNAVAILABLE))
    assert DENIED not in reply.text


def assert_signed_out(browser: Browser, path: str = "/") -> None:
    """Opening ``path`` gives the sign in page, not a library page."""
    reply = browser.open(path)
    assert (reply.status, reply.body) == (200, pages.sign_in_page(path, None)), path


def assert_home_lists(reply: LibraryReply, *names: str) -> None:
    assert reply.status == 200
    assert UNAVAILABLE not in reply.text and DENIED not in reply.text
    assert [html.unescape(name) for _, name, _ in folder_rows(reply)] == list(names)


def folder_rows(reply: LibraryReply) -> list[tuple[str, str, str]]:
    """``(folder id, name as written, role label)`` of each row of the home page."""
    return reply.folder_rows()


def sign_in_link(reply: LibraryReply) -> str:
    """The address of the ``Sign in with Google`` link of a sign in page."""
    match = re.search(r'<a href="([^"]+)">Sign in with Google</a>', reply.text)
    assert match is not None, reply.text
    return html.unescape(match.group(1))


def cookie(browser: Browser, name: str) -> str:
    assert name in browser.cookies, f"no {name} cookie: {browser.cookies}"
    return browser.cookies[name]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Google failures (FR-NEW-004, DEC-016)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("failure", ["close", "unavailable", "bad_json"])
def test_e2e_003_google_cannot_be_reached(library_server: START, fake_google: FakeGoogle, failure: str) -> None:
    """E2E-003: no answer, a 503 or garbage from Google: the message, signed out; then Google answers again."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    fake_google.exchange_failure = failure

    reply = browser.sign_in(fake_google, LAMYA)

    assert_unavailable(reply)
    assert len(fake_google.requests_to("/token")) == 1
    assert running.stored.sessions() == []
    assert "lib" not in browser.cookies
    assert_signed_out(browser)
    fake_google.exchange_failure = None
    assert_home_lists(browser.sign_in(fake_google, LAMYA), WCBIP)
    assert [row[1] for row in running.stored.sessions()] == [LAMYA]


def test_e2e_003_a_refused_return_address_at_the_token_exchange_gives_the_same_message(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-003 (EXC-023c): Google answers ``400 redirect_uri_mismatch`` to the exchange."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    fake_google.choose(LAMYA)
    start = browser.open("/auth/start", follow=False)
    assert start.status == 302
    at_google = browser.open(start.headers["location"], follow=False)
    assert at_google.status == 302
    fake_google.registered_redirects.clear()

    reply = browser.open(at_google.headers["location"])

    assert_unavailable(reply)
    assert running.stored.sessions() == []
    assert_signed_out(browser)


def test_e2e_003_google_refusing_the_connection_is_sign_in_unavailable(tmp_path: Path) -> None:
    """The exchange with nothing listening at ``token_uri`` raises ``SignInUnavailable`` (no traceback, no hang)."""
    credentials = tmp_path / "google-oauth.json"
    web = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "http://127.0.0.1:9/authorize",
        "token_uri": f"http://127.0.0.1:{free_port()}/token",
        "redirect_uris": ["http://slides.test/auth/callback"],
    }
    credentials.write_text(json.dumps({"web": web}), encoding="utf-8")
    client = GoogleClient(credentials, "http://slides.test/auth/callback", timeout=5.0)

    with pytest.raises(SignInUnavailable):
        client.exchange("code", "verifier")


def test_e2e_150_an_unregistered_return_address_then_registered(
    library_server: START, fake_google: FakeGoogle, caplog: pytest.LogCaptureFixture
) -> None:
    """E2E-150: the console lacks the return address: the message; once the owner adds it, the same steps work."""
    caplog.set_level(logging.WARNING)
    running, _ = standard(library_server, fake_google, google_registered=False)
    redirect = f"{running.origin}/auth/callback"
    assert f"{redirect} is not listed in redirect_uris" in caplog.text
    browser = running.browser()

    reply = browser.sign_in(fake_google, LAMYA)

    assert_unavailable(reply)
    assert fake_google.requests_to("/token") == []
    assert running.stored.sessions() == []
    assert_signed_out(browser)
    fake_google.registered_redirects.add(redirect)
    assert_home_lists(browser.sign_in(fake_google, LAMYA), WCBIP)


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        json.dumps({"installed": {}}),
        json.dumps({"web": {"client_id": GOOGLE_CLIENT_ID, "auth_uri": "https://a", "token_uri": "https://t"}}),
        json.dumps(
            {"web": {"client_id": "c", "client_secret": "s", "auth_uri": "https://a", "token_uri": "file:///etc"}}
        ),
    ],
    ids=["not-json", "no-web-block", "no-secret", "file-scheme"],
)
def test_an_unusable_credentials_file_is_logged_and_every_sign_in_is_unavailable(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, content: str
) -> None:
    """DEC-015: one error line naming the file, never its content; no Google address is ever built."""
    caplog.set_level(logging.ERROR)
    credentials = tmp_path / "google-oauth.json"
    credentials.write_text(content, encoding="utf-8")

    client = GoogleClient(credentials, "http://slides.test/auth/callback")

    assert f"Google credentials file {credentials}" in caplog.text
    assert GOOGLE_CLIENT_ID not in caplog.text
    with pytest.raises(SignInUnavailable):
        client.authorization_url("state", "nonce", "challenge")
    with pytest.raises(SignInUnavailable):
        client.exchange("code", "verifier")


def test_sign_in_without_a_credentials_file_says_unavailable(
    library_server: START, caplog: pytest.LogCaptureFixture
) -> None:
    """DEC-015: the server starts without the file, logs an error, and every attempt gives the message."""
    caplog.set_level(logging.WARNING)
    running = library_server()
    assert "No Google credentials file" in caplog.text

    reply = running.client().get("/auth/start?next=/admin")

    assert (reply.status, reply.body) == (200, pages.sign_in_page("/admin", UNAVAILABLE))
    assert reply.set_cookies == ()
    assert running.stored.logins() == []


# ---------------------------------------------------------------------------
# Cancelled consent (FR-NEW-002, FR-NEW-009)
# ---------------------------------------------------------------------------


def test_e2e_005_the_visitor_cancels_the_google_consent(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-005: back on the sign in page, signed out, no message; a fresh sign in then succeeds."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()

    reply = browser.sign_in(fake_google, None)

    assert urlsplit(browser.url).path == "/auth/callback"
    assert (reply.status, reply.body) == (200, pages.sign_in_page("/", None))
    assert running.stored.sessions() == []
    assert_signed_out(browser)
    assert_home_lists(browser.sign_in(fake_google, LAMYA), WCBIP)


def test_e2e_007_a_cancelled_consent_gives_no_access_to_a_direct_link(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-007: Carol follows her link, cancels at Google, opens the link again: the sign in page, never a name."""
    running, _ = standard(library_server, fake_google)
    link = f"/open/{secrets.token_hex(16)}"
    browser = running.browser()

    first = browser.open(link)
    assert first.body == pages.sign_in_page(link, None)
    fake_google.cancel()
    cancelled = browser.open(sign_in_link(first))
    again = browser.open(link)

    assert cancelled.body == pages.sign_in_page("/", None)
    assert (again.status, again.body) == (200, pages.sign_in_page(link, None))
    assert running.stored.sessions() == []
    for reply in browser.replies:
        assert not any(name in reply.text for name in LIBRARY_NAMES)


# ---------------------------------------------------------------------------
# Accounts with no role, unverified addresses (FR-NEW-003, FR-NEW-068)
# ---------------------------------------------------------------------------


def test_e2e_090_an_address_that_looks_like_the_administrators_is_not_the_administrator(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-090: sebmorand@gmail.com and seb.morand@googlemail.com, in no folder, see only ``Access denied.``."""
    running, _ = standard(library_server, fake_google)

    for email in ("sebmorand@gmail.com", "seb.morand@googlemail.com"):
        browser = running.browser()
        reply = browser.sign_in(fake_google, email)
        assert (reply.status, reply.body) == (403, pages.access_denied()), email
        for path in ("/", "/admin"):
            page = browser.open(path)
            assert (page.status, page.body) == (403, pages.access_denied()), (email, path)
            assert "Administration" not in page.text
            assert not any(name in page.text for name in LIBRARY_NAMES)

    assert sorted(row[1] for row in running.stored.sessions()) == ["seb.morand@googlemail.com", "sebmorand@gmail.com"]
    assert running.stored.folder_names() == sorted((WCBIP, CARDIOLOGY, PNEUMO))
    assert running.stored.activity() == []


def test_an_account_given_a_role_later_sees_the_library_without_signing_in_again(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-003: Bob is refused, the administrator adds him RO, his next page lists the folder."""
    running, ids = standard(library_server, fake_google)
    browser = running.browser()
    refused = browser.sign_in(fake_google, BOB)
    assert (refused.status, refused.body) == (403, pages.access_denied())

    running.builder.member(ids[CARDIOLOGY], BOB, "RO")
    reply = browser.open("/")

    assert_home_lists(reply, CARDIOLOGY)
    assert folder_rows(reply) == [(ids[CARDIOLOGY], CARDIOLOGY, "Read only")]
    assert len(fake_google.requests_to("/authorize")) == 1


def test_e2e_171_an_unverified_address_gives_the_same_message_listed_or_not(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-171: Bob (in no list) and Lamya (listed), both unverified: the same message; verified, Lamya gets in."""
    running, _ = standard(library_server, fake_google)
    fake_google.accounts[BOB] = {"email_verified": False}
    fake_google.accounts[LAMYA] = {"email_verified": False}

    replies = {email: running.browser().sign_in(fake_google, email) for email in (BOB, LAMYA)}

    for reply in replies.values():
        assert_unavailable(reply)
    assert replies[BOB].body == replies[LAMYA].body
    assert running.stored.sessions() == []
    fake_google.accounts[LAMYA]["email_verified"] = True
    assert_home_lists(running.browser().sign_in(fake_google, LAMYA), WCBIP)


def test_a_verified_address_is_accepted_whatever_its_letter_case(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-002 and FR-NEW-068: ``Lamya.Chrif@Gmail.COM`` is lamya.chrif@gmail.com, stored lower case."""
    running, _ = standard(library_server, fake_google)

    reply = running.browser().sign_in(fake_google, "Lamya.Chrif@Gmail.COM")

    assert_home_lists(reply, WCBIP)
    assert [row[1] for row in running.stored.sessions()] == [LAMYA]


# ---------------------------------------------------------------------------
# Destinations (FR-NEW-069, FR-NEW-009)
# ---------------------------------------------------------------------------


def test_e2e_172_destinations_that_leave_the_product_are_ignored(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-172: each hostile ``next`` ends on the home page listing Cardiology 2027."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()

    for destination in (
        "//evil.example/x",
        "\\evil.example",
        "javascript:alert(1)",
        "https://slides.scm-platform.org@evil.example/x",
        "/\\evil.example",
        "slides.scm-platform.org.evil.example",
    ):
        reply = browser.sign_in(fake_google, CAROL, destination)
        assert browser.url == f"{running.origin}/", destination
        assert_home_lists(reply, CARDIOLOGY)
        browser.sign_out()


def test_a_local_destination_is_kept_and_a_page_without_right_is_access_denied(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-009 and FR-NEW-069: Carol asked for /admin: she lands there after Google, and is refused."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    page = browser.open("/admin")

    fake_google.choose(CAROL)
    reply = browser.open(sign_in_link(page))

    assert browser.url == f"{running.origin}/admin"
    assert (reply.status, reply.body) == (403, pages.access_denied())


@pytest.mark.parametrize("destination", HOSTILE_DESTINATIONS)
def test_exploit_e2e_sec_016_a_sign_in_link_carrying_a_destination_on_another_site(
    library_server: START, fake_google: FakeGoogle, evil_listener: RecordingListener, destination: str
) -> None:
    """E2E-SEC-016 (Class F#1). Red before the fix because the browser is sent to evil.example: the listener of
    evil.example records 1 visit instead of 0."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser({"evil.example": evil_listener.port})
    fake_google.choose(CAROL)

    start = browser.open(f"/auth/start?next={quote(destination, safe='')}", follow=False)
    assert start.status == 302
    assert [row[3] for row in running.stored.logins()] == ["/"]
    reply = browser.open(start.headers["location"])

    assert browser.url == f"{running.origin}/"
    assert_home_lists(reply, CARDIOLOGY)
    assert evil_listener.visits == []
    assert browser.hosts_visited() == {running.library_netloc, fake_google.netloc}


# ---------------------------------------------------------------------------
# Sign in answers: browser binding, single use, age (FR-NEW-071, DEC-013)
# ---------------------------------------------------------------------------


def test_e2e_183_two_sign_ins_started_in_two_tabs_each_complete(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-183: one browser, two attempts; the second tab completes first, then the first."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    fake_google.choose(CAROL)
    fake_google.choose(CAROL)

    first_tab = browser.open("/auth/start", follow=False)
    second_tab = browser.open("/auth/start", follow=False)
    assert (first_tab.status, second_tab.status) == (302, 302)
    assert second_tab.set_cookies == ()  # the browser id of the first tab is reused
    second = browser.open(second_tab.headers["location"])
    first = browser.open(first_tab.headers["location"])

    assert_home_lists(second, CARDIOLOGY)
    assert_home_lists(first, CARDIOLOGY)
    assert [row[1] for row in running.stored.sessions()] == [CAROL, CAROL]
    assert running.stored.logins() == []


def test_e2e_184_a_sign_in_answer_cannot_be_used_twice(library_server: START, fake_google: FakeGoogle) -> None:
    """E2E-184: the kept answer address, opened after sign out, gives the message and never reaches Google."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    assert_home_lists(browser.sign_in(fake_google, CAROL), CARDIOLOGY)
    kept = browser.callback_addresses()[-1]
    browser.sign_out()
    exchanges = len(fake_google.requests_to("/token"))

    reply = browser.open(kept)

    assert_unavailable(reply)
    assert len(fake_google.requests_to("/token")) == exchanges
    assert running.stored.sessions() == []
    assert_signed_out(browser)


@pytest.mark.parametrize("carol_started_her_own", [False, True], ids=["no-browser-id", "other-browser-id"])
def test_exploit_e2e_sec_019_a_sign_in_answer_made_for_someone_else_is_planted(
    library_server: START, fake_google: FakeGoogle, carol_started_her_own: bool
) -> None:
    """E2E-SEC-019 (Class G#7). Red before the fix because Carol's browser becomes signed in as dan.rw@example.org:
    her home page lists Cardiology 2027 instead of showing the sign in page."""
    running, ids = standard(library_server, fake_google)
    running.builder.member(ids[PNEUMO], DAN, "RO")
    third_party = running.browser()
    fake_google.choose(DAN)
    start = third_party.open("/auth/start", follow=False)
    assert start.status == 302
    at_google = third_party.open(start.headers["location"], follow=False)
    planted = at_google.headers.get("location", "")
    assert urlsplit(planted).path == "/auth/callback" and "code" in parse_qs(urlsplit(planted).query)
    carol = running.browser()
    if carol_started_her_own:
        assert carol.open("/auth/start", follow=False).status == 302  # her own browser id, a different one

    reply = carol.open(planted)

    assert_unavailable(reply)
    home = carol.open("/")
    assert (home.status, home.body) == (200, pages.sign_in_page("/", None))
    assert CARDIOLOGY not in home.text and PNEUMO not in home.text
    assert "lib" not in carol.cookies
    assert running.stored.sessions() == []
    assert running.stored.activity() == []


def test_a_sign_in_answer_older_than_ten_minutes_is_refused(library_server: START, fake_google: FakeGoogle) -> None:
    """DEC-013: an attempt is valid under 600 s; at 600 s the answer gives the message."""
    running, _ = standard(library_server, fake_google)

    def answer_after(seconds: float) -> LibraryReply:
        browser = running.browser()
        fake_google.choose(CAROL)
        start = browser.open("/auth/start", follow=False)
        assert start.status == 302
        at_google = browser.open(start.headers["location"], follow=False)
        running.clock.advance(seconds)
        return browser.open(at_google.headers["location"])

    assert_unavailable(answer_after(600))
    assert running.stored.sessions() == []
    assert_home_lists(answer_after(599), CARDIOLOGY)


def test_exploit_e2e_sec_015_an_unverified_claim_of_the_administrator_address(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """E2E-SEC-015 (Class E#1). Red before the fix because a build that trusts the claimed address signs the visitor
    in as seb.morand@gmail.com: the visitor's Administration and home addresses stop showing the sign in page."""
    running, _ = standard(library_server, fake_google)
    running.browser().sign_in(fake_google, ADMIN)  # the administrator's own session, in another browser
    before = running.stored.sessions()
    assert [row[1] for row in before] == [ADMIN]
    fake_google.accounts[ADMIN] = {"email_verified": False}
    visitor = running.browser()

    reply = visitor.sign_in(fake_google, ADMIN)

    assert_unavailable(reply)
    for path in ("/admin", "/"):
        page = visitor.open(path)
        assert (page.status, page.body) == (200, pages.sign_in_page(path, None)), path
        assert "Administration" not in page.text
    assert running.stored.sessions() == before
    assert running.stored.activity() == []
    assert running.stored.folder_names() == sorted((WCBIP, CARDIOLOGY, PNEUMO))


# ---------------------------------------------------------------------------
# Home page, sessions and sign out (FR-NEW-002, FR-NEW-008, FR-NEW-015, FR-NEW-072)
# ---------------------------------------------------------------------------


def test_the_home_page_lists_the_persons_folders_with_their_role(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-015 (partial): Dan's two folders with ``Read and write`` and ``Read only``, links by id, Sign out."""
    running, ids = standard(library_server, fake_google)
    running.builder.member(ids[PNEUMO], DAN, "RO")
    hostile = running.builder.folder("A <b>&amp; folder")
    running.builder.member(hostile, DAN, "RO")

    reply = running.browser().sign_in(fake_google, DAN)

    assert folder_rows(reply) == [
        (hostile, "A &lt;b&gt;&amp;amp; folder", "Read only"),
        (ids[CARDIOLOGY], CARDIOLOGY, "Read and write"),
        (ids[PNEUMO], PNEUMO, "Read only"),
    ]
    assert WCBIP not in reply.text and "<b>" not in reply.text
    assert '<form method="post" action="/auth/logout"><button type="submit">Sign out</button></form>' in reply.text
    assert reply.headers["content-security-policy"].endswith("frame-ancestors 'none'")
    assert reply.headers["x-frame-options"] == "DENY"


def test_a_sign_in_stores_a_hashed_thirty_day_session_and_sets_the_cookies(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """DEC-013 and DEC-017: the ``lib-b`` and ``lib`` cookies on http, and only their hashes in the tables."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    fake_google.choose(CAROL)

    start = browser.open("/auth/start", follow=False)
    browser_id = cookie(browser, "lib-b")
    assert start.set_cookies == (f"lib-b={browser_id}; Path=/; HttpOnly; SameSite=Lax",)
    assert [row[4] for row in running.stored.logins()] == [sha256(browser_id)]
    browser.open(start.headers["location"])
    token = cookie(browser, "lib")

    callback = browser.replies[-2]
    assert callback.status == 303 and callback.headers["location"] == "/"
    assert callback.set_cookies == (f"lib={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_SECONDS}",)
    assert len(token) >= 43  # 256 random bits, base64url
    assert running.stored.sessions() == [(sha256(token), CAROL, running.clock.now, running.clock.now + SESSION_SECONDS)]
    assert running.stored.logins() == []


def test_sign_in_asks_for_the_account_chooser_with_pkce_state_and_nonce(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """DEC-012: the authorization request and the code exchange, as Google received them."""
    running, _ = standard(library_server, fake_google)

    running.browser().sign_in(fake_google, CAROL)

    assert (len(fake_google.requests_to("/authorize")), len(fake_google.requests_to("/token"))) == (1, 1)
    [authorize], [token] = fake_google.requests_to("/authorize"), fake_google.requests_to("/token")
    redirect = f"{running.origin}/auth/callback"
    assert {key: authorize.params[key] for key in ("response_type", "client_id", "redirect_uri", "scope")} == {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect,
        "scope": "openid email",
    }
    assert authorize.params["prompt"] == "select_account"
    assert authorize.params["code_challenge_method"] == "S256"
    assert authorize.params["code_challenge"] == pkce_challenge(token.params["code_verifier"])
    assert len(token.params["code_verifier"]) >= 43
    assert len({authorize.params["state"], authorize.params["nonce"], token.params["code_verifier"]}) == 3
    assert token.params["grant_type"] == "authorization_code"
    assert token.params["redirect_uri"] == redirect
    assert token.params["client_secret"] == GOOGLE_CLIENT_SECRET


def test_sign_out_ends_this_browsers_session_only_and_a_copied_cookie_is_refused(
    library_server: START, fake_google: FakeGoogle
) -> None:
    """FR-NEW-008 and FR-NEW-072: the copied cookie gets the sign in page and the row is gone; the phone stays in."""
    running, _ = standard(library_server, fake_google)
    laptop, phone = running.browser(), running.browser()
    assert_home_lists(laptop.sign_in(fake_google, CAROL), CARDIOLOGY)
    assert_home_lists(phone.sign_in(fake_google, CAROL), CARDIOLOGY)
    copied = cookie(laptop, "lib")

    reply = laptop.sign_out()

    assert laptop.url == f"{running.origin}/"
    assert (reply.status, reply.body) == (200, pages.sign_in_page("/", None))
    assert laptop.cookies == {}
    replay = running.client().get("/", cookie=f"lib={copied}")
    assert (replay.status, replay.body) == (200, pages.sign_in_page("/", None))
    assert sha256(copied) not in [row[0] for row in running.stored.sessions()]
    assert_home_lists(phone.open("/"), CARDIOLOGY)
    phone.sign_out()
    assert running.stored.sessions() == []


def test_sign_out_clears_both_cookies(library_server: START, fake_google: FakeGoogle) -> None:
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    browser.sign_in(fake_google, CAROL)
    token = cookie(browser, "lib")

    reply = running.client().request(
        "POST", "/auth/logout", headers={"Cookie": f"lib={token}", "Origin": running.origin}
    )

    assert (reply.status, reply.headers["location"]) == (303, "/")
    assert reply.set_cookies == (
        "lib=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
        "lib-b=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "http://evil.example"},
        {"Origin": "null"},
        {"ORIGIN_IS_LIBRARY": "/"},
        {"ORIGIN_IS_LIBRARY": "", "Sec-Fetch-Site": "cross-site"},
        {"ORIGIN_IS_LIBRARY": "", "Sec-Fetch-Site": "same-site"},
    ],
    ids=["no-origin", "other-origin", "null-origin", "origin-with-slash", "cross-site", "same-site"],
)
def test_sign_out_from_another_origin_is_refused_and_changes_nothing(
    library_server: START, fake_google: FakeGoogle, headers: dict[str, str]
) -> None:
    """DEC-022: a POST whose ``Origin`` is not exactly the library origin gets ``Access denied.``; the session lives."""
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    browser.sign_in(fake_google, CAROL)
    if "ORIGIN_IS_LIBRARY" in headers:
        headers = {**headers, "Origin": running.origin + headers.pop("ORIGIN_IS_LIBRARY")}
    before = running.stored.sessions()

    reply = running.client().request(
        "POST", "/auth/logout", headers={"Cookie": "; ".join(f"{k}={v}" for k, v in browser.cookies.items()), **headers}
    )

    assert (reply.status, reply.body) == (403, pages.access_denied())
    assert reply.set_cookies == ()
    assert running.stored.sessions() == before and len(before) == 1
    assert_home_lists(browser.open("/"), CARDIOLOGY)


def test_sign_out_with_a_fetch_site_of_none_is_accepted(library_server: START, fake_google: FakeGoogle) -> None:
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    browser.sign_in(fake_google, CAROL)

    reply = running.client().request(
        "POST",
        "/auth/logout",
        headers={"Cookie": f"lib={cookie(browser, 'lib')}", "Origin": running.origin, "Sec-Fetch-Site": "none"},
    )

    assert reply.status == 303
    assert running.stored.sessions() == []


def test_the_https_origin_uses_host_prefixed_secure_cookies(library_server: START, fake_google: FakeGoogle) -> None:
    """DEC-017: behind nginx on https the browser id cookie is ``__Host-lib-b`` with ``Secure``."""
    origin = "https://slides.scm-platform.org"
    running = library_server(
        fake_google, library_origin=origin, library_content_origin="https://slides-content.scm-platform.org"
    )
    fake_google.choose(CAROL)

    reply = running.client("slides.scm-platform.org").get("/auth/start", x_forwarded_proto="https")

    assert reply.status == 302
    assert len(reply.set_cookies) == 1
    assert re.fullmatch(r"__Host-lib-b=[A-Za-z0-9_-]{22}; Path=/; HttpOnly; SameSite=Lax; Secure", reply.set_cookies[0])
    query = parse_qs(urlsplit(reply.headers["location"]).query)
    assert query["redirect_uri"] == [f"{origin}/auth/callback"]


def test_no_address_token_or_secret_reaches_the_log(
    library_server: START, fake_google: FakeGoogle, caplog: pytest.LogCaptureFixture
) -> None:
    """DEC-048: a full sign in, a refused one and a sign out log no address, token, state, nonce, code or secret."""
    caplog.set_level(logging.DEBUG)
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    browser.sign_in(fake_google, CAROL)
    token = cookie(browser, "lib")
    fake_google.accounts[BOB] = {"email_verified": False}
    running.browser().sign_in(fake_google, BOB)
    browser.sign_out()

    secrets_seen = [CAROL, BOB, token, GOOGLE_CLIENT_SECRET]
    for request in fake_google.received:
        secrets_seen += [
            request.params[k] for k in ("state", "nonce", "code", "code_verifier") if request.params.get(k)
        ]
    assert "Sign in refused" in caplog.text
    for value in secrets_seen:
        assert value not in caplog.text


def test_no_address_token_or_secret_reaches_a_span(
    library_server: START, fake_google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-048: the spans of a full sign in (auth.google_token, session.create ...) hold no address, token or secret."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing.trace, "get_tracer", lambda *args, **kwargs: provider.get_tracer("test"))
    running, _ = standard(library_server, fake_google)
    browser = running.browser()
    browser.sign_in(fake_google, CAROL)
    token = cookie(browser, "lib")
    browser.sign_out()

    spans = exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert "auth.google_token" in names
    dumped = json.dumps([[span.name, dict(span.attributes or {})] for span in spans])
    secrets_seen = [CAROL, token, GOOGLE_CLIENT_SECRET]
    for request in fake_google.received:
        secrets_seen += [
            request.params[k] for k in ("state", "nonce", "code", "code_verifier") if request.params.get(k)
        ]
    for value in secrets_seen:
        assert value not in dumped


def test_the_token_request_never_follows_a_redirect(library_server: START, fake_google: FakeGoogle) -> None:
    """The client secret goes to ``token_uri`` only: a 302 gives the one failure message, evil.example sees nothing."""
    hostile = library_support.RecordingListener()
    try:
        running, _ = standard(library_server, fake_google)
        fake_google.exchange_failure = "redirect"
        fake_google.redirect_target = f"http://127.0.0.1:{hostile.port}/steal"

        reply = running.browser().sign_in(fake_google, LAMYA)

        assert_unavailable(reply)
        assert len(fake_google.requests_to("/token")) == 1
        assert hostile.visits == []
        assert running.stored.sessions() == []
    finally:
        hostile.stop()


# ---------------------------------------------------------------------------
# Units: claims, destinations, cookies, database (story tests)
# ---------------------------------------------------------------------------

NOW = 1_000_000_000.0
MISSING = object()
GOOD_CLAIMS: dict[str, Any] = {
    "iss": "https://accounts.google.com",
    "aud": GOOGLE_CLIENT_ID,
    "exp": NOW + 60,
    "nonce": "nonce-1",
    "email_verified": True,
    "email": "Lamya.Chrif@gmail.com",
}


def claims_with(**changes: object) -> dict[str, Any]:
    claims = dict(GOOD_CLAIMS)
    for key, value in changes.items():
        if value is MISSING:
            claims.pop(key)
        else:
            claims[key] = value
    return claims


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://evil.example"},
        {"iss": "accounts.google.com.evil.example"},
        {"iss": MISSING},
        {"aud": "another-client.apps.googleusercontent.com"},
        {"aud": [GOOGLE_CLIENT_ID]},
        {"aud": MISSING},
        {"exp": NOW},
        {"exp": NOW - 1},
        {"exp": str(NOW + 60)},
        {"exp": True},
        {"exp": MISSING},
        {"nonce": "nonce-2"},
        {"nonce": MISSING},
        {"email_verified": False},
        {"email_verified": "false"},
        {"email_verified": 1},
        {"email_verified": MISSING},
        {"email": ""},
        {"email": 42},
        {"email": MISSING},
    ],
    ids=lambda changes: ",".join(f"{k}={'missing' if v is MISSING else v!r}" for k, v in changes.items()),
)
def test_validate_claims_rejects_each_wrong_or_missing_claim(changes: dict[str, object]) -> None:
    with pytest.raises(SignInUnavailable):
        validate_claims(claims_with(**changes), GOOGLE_CLIENT_ID, "nonce-1", NOW)


@pytest.mark.parametrize(
    "changes", [{}, {"iss": "accounts.google.com"}, {"email_verified": "true"}], ids=["https-iss", "bare-iss", "text"]
)
def test_validate_claims_returns_the_lower_case_address(changes: dict[str, object]) -> None:
    assert validate_claims(claims_with(**changes), GOOGLE_CLIENT_ID, "nonce-1", NOW) == "lamya.chrif@gmail.com"


def test_safe_destination_keeps_local_paths_and_refuses_the_hostile_ones() -> None:
    for local in ("/f/abc", "/", "/admin", "/open/0123456789abcdef0123456789abcdef"):
        assert safe_destination(local) == local
    for hostile in (*HOSTILE_DESTINATIONS, None, "", "\\evil.example", "slides.test", "/a\x00b", "/a\tb", "/a:b"):
        assert safe_destination(hostile) == "/", hostile


def test_cookie_names_and_headers_for_an_https_origin() -> None:
    origin = "https://slides.scm-platform.org"

    assert (cookie_name(origin, "lib"), cookie_name(origin, "lib-b")) == ("__Host-lib", "__Host-lib-b")
    assert (cookie_name("http://slides.test:8080", "lib"), cookie_name("http://slides.test", "lib-b")) == (
        "lib",
        "lib-b",
    )
    assert (
        cookie_header(origin, "lib", "t0k", max_age=SESSION_SECONDS)
        == "__Host-lib=t0k; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000; Secure"
    )
    assert (
        cookie_header(origin, "lib-b", "b1d", max_age=None)
        == "__Host-lib-b=b1d; Path=/; HttpOnly; SameSite=Lax; Secure"
    )


def test_the_database_is_private_and_migrated_once(library_server: START) -> None:
    """DEC-025: ``library.db`` is 0600 in a 0700 directory, at schema version 1; opening it again changes nothing."""
    running = library_server()
    path = running.library_dir / "library.db"

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(running.library_dir.stat().st_mode) == 0o700
    assert running.stored.rows("PRAGMA user_version") == [(1,)]
    tables = {row[0] for row in running.stored.rows("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"meta", "folders", "members", "logins", "sessions"}
    folder = running.builder.folder(CARDIOLOGY)
    again = Database(path)
    assert running.stored.rows("PRAGMA user_version") == [(1,)]
    assert running.stored.folder_names() == [CARDIOLOGY] and folder
    again.release()
