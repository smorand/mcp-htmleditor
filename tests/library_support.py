"""Test support for the web library mode (SPEC-0025, DEC-049).

``library_server`` starts an in process ``LibraryServer`` on a free port with a temporary ``library_dir`` and
``state_dir`` and the origins ``http://slides.test:<port>`` and ``http://slides-content.test:<port>``; overrides
replace any setting. ``HttpClient`` connects to ``127.0.0.1:<port>`` and sends the ``Host`` it is given, so one
listener is reached under any host name. ``FakeClock`` moves time by seconds.

Sign in (US-0126): ``FakeGoogle`` plays Google on a loopback port (``/authorize`` answers for the next scripted
choice, ``/token`` checks PKCE and returns an unsigned ID token); ``Browser`` keeps the library cookies, follows
redirects across the library, Google and any host given to its resolver (like ``--host-resolver-rules``), and records
every address it visited; ``RecordingListener`` counts visits to a hostile site; ``StoredLibrary`` is the operator view
(tables read directly); ``LibraryBuilder`` writes folders and members.

Lifetime (US-0128): ``RunningLibrary.restart()`` stops the server and starts a new one on the same port, directory
and clock; ``RunningLibrary.unreadable_database()`` swaps a corrupted ``library.db`` in and the real one back out;
``Browser.reopened()`` is the same browser closed and opened again (only cookies with a ``Max-Age`` survive).

Folder page (US-0129): ``LibraryBuilder.presentation`` writes a generated deck of an exact byte count at
``Library.presentation_path`` with an exact modified time (``os.utime``) and its row; ``standard_presentations`` the
five decks of the standard library; ``LibraryReply.presentation_rows()`` reads the rows of a folder page;
``launch_chromium`` maps both library host names to loopback and ``person_context`` is a context holding one session
cookie in a fixed time zone.

Administration (US-0130): ``Browser.post_json`` sends what ``library.js`` sends (``Origin``, ``Sec-Fetch-Site:
same-origin``, ``Content-Type: application/json``), or the headers a test gives instead;
``LibraryReply.activity_lines()`` reads the activity rows of the administration page.

Folder deletion (US-0131): ``StoredLibrary.entries()`` walks ``library_dir`` and ``state_dir``;
``LibraryBuilder.records(presentation)`` gives a presentation history versions, requests and AI suggestions and
returns its state directory ``<state_dir>/files/<key>``.

Members (US-0132): ``Browser.add_member`` and ``Browser.remove_member`` send what the ``Members`` controls send;
``LibraryReply.member_rows(folder_id)`` reads the members of one folder on the administration page;
``StoredLibrary.members()`` the table; ``signed_in`` and ``visible_texts`` are shared by the member modules.

Opening a presentation (US-0133): the ``Browser`` also keeps the grant cookies of the content origin by path
(``deck_cookies``) and sends ``X-Forwarded-Proto`` as nginx does when the origins are https (``start(scheme=
"https")``); ``Browser.open_presentation(pid)`` chooses a presentation, ``Browser.deck(pid, route)`` asks one route of
it without following redirects, ``Browser.copied()`` is a tool holding a copy of every cookie;
``StoredLibrary.tickets()`` and ``grants()`` read the two tables.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import re
import secrets
import socket
import sqlite3
import threading
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape as html_escape
from html import unescape as html_unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit

import pytest
from playwright.sync_api import Browser as Chromium
from playwright.sync_api import BrowserContext, Frame, Page, Playwright
from playwright.sync_api import Error as PlaywrightError

from mcp_htmleditor.config import Settings, reset_settings_cache
from mcp_htmleditor.history import HistoryStore, Version
from mcp_htmleditor.library.names import name_key
from mcp_htmleditor.library.server import LibraryServer
from mcp_htmleditor.library.store import Database, Library
from mcp_htmleditor.request_service import RequestService
from mcp_htmleditor.request_store import RequestStore
from tests.browser_wait import wait_for_js, wait_until
from tests.deck_support import build_deck

LIBRARY_HOST = "slides.test"
CONTENT_HOST = "slides-content.test"
CLOCK_START = 1_000_000_000.0
GOOGLE_CLIENT_ID = "slides-test.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "test-client-secret-7d1c"  # noqa: S105 - a fake client of the fake provider
EVIL_HOST = "evil.example"
UNREGISTERED_REDIRECT = "https://elsewhere.example/auth/callback"
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
MAX_REDIRECTS = 10
CARDIOLOGY = "Cardiology 2027"
PNEUMO = "Pneumo Été"
WCBIP = "WCBIP Melbourne Décembre 2026"
LAMYA = "lamya.chrif@gmail.com"
DAN = "dan.rw@example.org"
CAROL = "carol.ro@example.org"
BOB = "bob.nobody@gmail.com"
ADMIN = "seb.morand@gmail.com"
FOLDER_ROW = re.compile(r'<li><a href="/f/([0-9a-f]{32})">([^<]*)</a> <span>([^<]*)</span></li>')
PRESENTATION_ROW = re.compile(
    r'<li><span class="name"><a href="/open/[0-9a-f]{32}">([^<]*)</a></span> '
    r'<time datetime="([^"]*)">([^<]*)</time> <span class="size">([^<]*)</span>'
    r"</li>"
)
ACTIVITY_ROW = re.compile(
    r'<li><time datetime="([^"]*)">[^<]*</time> <span class="actor">([^<]*)</span> <span class="text">([^<]*)</span>'
    r"</li>"
)
MEMBER_ROW = re.compile(
    r'<li><span class="email">([^<]*)</span> <select[^>]*>.*?<option value="R[WO]" selected>([^<]*)<'
)
HEART_FAILURE = "Heart Failure Update"
ARRHYTHMIA = "Arrhythmia Basics"
STATINS = "Statins Review"
CHALLENGES = "From Challenges to Change"
BRIDGING = "Bridging the Gap"
# The presentations of the standard library (spec section 9): folder, name, bytes, slides, modified (UTC).
STANDARD_PRESENTATIONS = (
    (WCBIP, CHALLENGES, 3_901_499, 18, datetime(2026, 11, 15, 19, 57, tzinfo=UTC)),
    (WCBIP, BRIDGING, 3_278_888, 15, datetime(2026, 11, 15, 19, 57, tzinfo=UTC)),
    (CARDIOLOGY, HEART_FAILURE, 2_097_152, 8, datetime(2026, 11, 10, 9, 15, tzinfo=UTC)),
    (CARDIOLOGY, ARRHYTHMIA, 524_288, 5, datetime(2026, 11, 12, 16, 40, tzinfo=UTC)),
    (CARDIOLOGY, STATINS, 1_572_864, 6, datetime(2026, 11, 12, 16, 40, tzinfo=UTC)),
)
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PADDING_OPEN = b"<!--"
PADDING_CLOSE = b"-->"


@dataclass
class FakeClock:
    """A clock the test moves: ``clock()`` returns ``now``, ``advance(seconds)`` moves it forward."""

    now: float = CLOCK_START

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass(frozen=True)
class LibraryReply:
    """One answer: status, headers (lower case names, last value kept), body bytes, every ``Set-Cookie`` value."""

    status: int
    headers: dict[str, str]
    body: bytes
    set_cookies: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def folder_rows(self) -> list[tuple[str, str, str]]:
        """``(folder id, name as written in the HTML, role label)`` of each row of a home page, in page order."""
        return FOLDER_ROW.findall(self.text)

    def presentation_rows(self) -> list[tuple[str, str, str, str]]:
        """``(name as written in the HTML, UTC ISO date, fallback date text, size)`` of each row of a folder page."""
        return PRESENTATION_ROW.findall(self.text)

    def activity_lines(self) -> list[tuple[str, str, str]]:
        """``(UTC ISO date, actor, line text)`` of each activity row of the administration page, in page order,
        unescaped."""
        return [
            (when, html_unescape(actor), html_unescape(text)) for when, actor, text in ACTIVITY_ROW.findall(self.text)
        ]

    def member_rows(self, folder_id: str) -> list[tuple[str, str]]:
        """``(address, role label shown by its chooser)`` of each member of a folder on the administration page, in
        page order, unescaped; an ``AssertionError`` when the page has no ``Members`` section for that folder."""
        section = re.search(f'<section class="members" id="members-{folder_id}">(.*?)</section>', self.text)
        assert section is not None, f"no Members section for {folder_id}"
        listing = re.search(r'<ul class="members">(.*?)</ul>', section.group(1))
        rows = MEMBER_ROW.findall(listing.group(1)) if listing is not None else []
        return [(html_unescape(email), html_unescape(role)) for email, role in rows]

    def json(self) -> Any:
        return json.loads(self.body)


@dataclass(frozen=True)
class HttpClient:
    """Requests to ``127.0.0.1:<port>`` carrying ``Host: <host>``."""

    port: int
    host: str

    def request(
        self, method: str, path: str, *, headers: dict[str, str] | None = None, body: bytes = b""
    ) -> LibraryReply:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", self.host)
            for name, value in (headers or {}).items():
                conn.putheader(name, value)
            if body or method in {"POST", "PUT", "DELETE"}:
                conn.putheader("Content-Length", str(len(body)))
            with suppress(BrokenPipeError, ConnectionResetError):  # a refusal is answered before the body is read
                conn.endheaders(body or None)
            response = conn.getresponse()
            data = response.read()
            return LibraryReply(
                status=response.status,
                headers={k.lower(): v for k, v in response.getheaders()},
                body=data,
                set_cookies=tuple(response.headers.get_all("Set-Cookie") or ()),
            )
        finally:
            conn.close()

    def get(self, path: str, **headers: str) -> LibraryReply:
        return self.request("GET", path, headers=_header_names(headers))


# ---------------------------------------------------------------------------
# Fake Google (design section 9, spec design input 13)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoogleRequest:
    """One request the fake received: method, path, and the query (GET) or form (POST) parameters."""

    method: str
    path: str
    params: dict[str, str]


@dataclass(frozen=True)
class _IssuedCode:
    claims: dict[str, Any]
    challenge: str
    redirect_uri: str


class _FakeGoogleHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        pass

    def do_GET(self) -> None:
        cast(_FakeGoogleServer, self.server).fake.answer_authorize(self)

    def do_POST(self) -> None:
        cast(_FakeGoogleServer, self.server).fake.answer_token(self)


class _FakeGoogleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, fake: FakeGoogle) -> None:
        self.fake = fake
        super().__init__(("127.0.0.1", 0), _FakeGoogleHandler)


class FakeGoogle:
    """Google's ``/authorize`` and ``/token`` on a loopback port, scripted by the test.

    ``accounts`` maps an address to claims that replace the defaults (``{"email_verified": False}``).
    ``choose(email)`` queues the account the person picks at the next ``/authorize``; ``cancel()`` queues a cancelled
    consent (``error=access_denied``). A ``redirect_uri`` missing from ``registered_redirects`` (the owner's console)
    comes back with ``error=redirect_uri_mismatch``.
    ``exchange_failure`` scripts ``/token``: ``"redirect"`` (302 to
    ``redirect_target``), ``"unavailable"`` (503), ``"close"`` (connection closed, no answer), ``"bad_json"``.
    ``received`` lists every request.
    """

    def __init__(self, accounts: dict[str, dict[str, Any]] | None = None) -> None:
        self.accounts: dict[str, dict[str, Any]] = dict(accounts or {})
        self.registered_redirects: set[str] = set()
        self.exchange_failure: str | None = None
        self.redirect_target: str = ""  # where ``exchange_failure == "redirect"`` sends the token request
        self.received: list[GoogleRequest] = []
        self.clock: Callable[[], float] = FakeClock()
        self._choices: deque[str | None] = deque()
        self._codes: dict[str, _IssuedCode] = {}
        self._lock = threading.Lock()
        self._server = _FakeGoogleServer(self)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()

    @property
    def netloc(self) -> str:
        return f"127.0.0.1:{self.port}"

    def choose(self, email: str) -> None:
        self._choices.append(email)

    def cancel(self) -> None:
        self._choices.append(None)

    def credentials(self, redirect_uris: list[str]) -> dict[str, Any]:
        """The operator's file, as Google's console exports it."""
        return {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": f"http://{self.netloc}/authorize",
                "token_uri": f"http://{self.netloc}/token",
                "redirect_uris": redirect_uris,
            }
        }

    def requests_to(self, path: str) -> list[GoogleRequest]:
        return [request for request in self.received if request.path == path]

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def answer_authorize(self, handler: BaseHTTPRequestHandler) -> None:
        target = urlsplit(handler.path)
        query = dict(parse_qsl(target.query, keep_blank_values=True))
        self.received.append(GoogleRequest("GET", target.path, query))
        redirect = query.get("redirect_uri", "")
        if target.path != "/authorize" or query.get("client_id") != GOOGLE_CLIENT_ID or not redirect:
            _answer(handler, 400, b'{"error": "invalid_request"}')
            return
        if not self._choices:
            _answer(handler, 400, b'{"error": "the test scripted no choice"}')
            return
        email = self._choices.popleft()  # the person picks the account before Google reports a problem
        answer: dict[str, str] = {"state": query.get("state", "")}
        if redirect not in self.registered_redirects:
            answer["error"] = "redirect_uri_mismatch"
        elif email is None:
            answer["error"] = "access_denied"
        else:
            code = secrets.token_urlsafe(16)
            with self._lock:
                self._codes[code] = _IssuedCode(self._claims(email, query), query.get("code_challenge", ""), redirect)
            answer["code"] = code
        _answer(handler, 302, b"", location=f"{redirect}?{urlencode(answer)}")

    def answer_token(self, handler: BaseHTTPRequestHandler) -> None:
        body = handler.rfile.read(int(handler.headers.get("Content-Length", "0")))
        form = dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
        self.received.append(GoogleRequest("POST", urlsplit(handler.path).path, form))
        if self.exchange_failure == "close":
            handler.close_connection = True  # nothing written: the client sees the connection end
            return
        if self.exchange_failure == "redirect":
            _answer(handler, 302, b"", location=self.redirect_target)
            return
        if self.exchange_failure == "unavailable":
            _answer(handler, 503, b'{"error": "temporarily_unavailable"}')
            return
        with self._lock:
            issued = self._codes.pop(form.get("code", ""), None)
        error = self._token_error(form, issued)
        if error is not None:
            _answer(handler, 400, json.dumps({"error": error}).encode())
            return
        if self.exchange_failure == "bad_json":
            _answer(handler, 200, b"<html>not json</html>")
            return
        assert issued is not None
        payload = {"access_token": "ya29.fake", "id_token": unsigned_jwt(issued.claims), "token_type": "Bearer"}
        _answer(handler, 200, json.dumps(payload).encode())

    def _claims(self, email: str, query: dict[str, str]) -> dict[str, Any]:
        now = self.clock()
        claims: dict[str, Any] = {
            "iss": "https://accounts.google.com",
            "aud": GOOGLE_CLIENT_ID,
            "sub": hashlib.sha256(email.lower().encode()).hexdigest()[:21],
            "email": email,
            "email_verified": True,
            "nonce": query.get("nonce", ""),
            "iat": int(now),
            "exp": int(now) + 3600,
        }
        return claims | self.accounts.get(email, {})

    def _token_error(self, form: dict[str, str], issued: _IssuedCode | None) -> str | None:
        if form.get("client_id") != GOOGLE_CLIENT_ID or form.get("client_secret") != GOOGLE_CLIENT_SECRET:
            return "invalid_client"
        if form.get("grant_type") != "authorization_code" or issued is None:
            return "invalid_grant"
        if form.get("redirect_uri") != issued.redirect_uri or issued.redirect_uri not in self.registered_redirects:
            return "redirect_uri_mismatch"
        if pkce_challenge(form.get("code_verifier", "")) != issued.challenge:
            return "invalid_grant"
        return None


def pkce_challenge(verifier: str) -> str:
    """RFC 7636 ``S256``: base64url of the SHA-256 of the verifier, without padding."""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def unsigned_jwt(claims: dict[str, Any]) -> str:
    """header.payload.signature with a junk signature: the product does not verify it (DEC-012)."""
    parts = ({"alg": "RS256", "typ": "JWT"}, claims)
    encoded = [base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode() for part in parts]
    return ".".join([*encoded, "c2lnbmF0dXJl"])


def _answer(
    handler: BaseHTTPRequestHandler,
    status: int,
    body: bytes,
    *,
    location: str | None = None,
    content_type: str = "application/json",
) -> None:
    handler.send_response(status)
    if location is not None:
        handler.send_header("Location", location)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class _RecordingHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        pass

    def do_GET(self) -> None:
        listener = cast(RecordingListener, self.server)
        listener.visits.append(f"{self.headers.get('Host')}{self.path}")
        if listener.page is not None:
            _answer(self, 200, listener.page.encode(), content_type="text/html; charset=utf-8")
            return
        _answer(self, 200, b'{"phished": true}')


class RecordingListener(ThreadingHTTPServer):
    """A hostile site on a loopback port: ``visits`` lists every request it received; with ``page`` set every GET
    answers that HTML (a page Chromium reaches through ``launch_chromium(..., EVIL_HOST)``)."""

    daemon_threads = True

    def __init__(self) -> None:
        self.visits: list[str] = []
        self.page: str | None = None
        super().__init__(("127.0.0.1", 0), _RecordingHandler)
        self.port = int(self.server_address[1])
        threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def stop(self) -> None:
        self.shutdown()
        self.server_close()


# ---------------------------------------------------------------------------
# The library: running server, operator view, builder, browser
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StoredLibrary:
    """The operator view: tables of ``library.db`` read directly, never through the product; ``entries()`` walks
    the library and state directories."""

    library_dir: Path
    state_dir: Path

    def entries(self) -> list[str]:
        """Every file and directory under ``library_dir`` and ``state_dir``, as ``library/<relative path>`` and
        ``state/<relative path>`` (POSIX separators), sorted."""
        return sorted(
            f"{label}/{entry.relative_to(root).as_posix()}"
            for label, root in (("library", self.library_dir), ("state", self.state_dir))
            for entry in root.rglob("*")
        )

    def rows(self, sql: str) -> list[tuple[Any, ...]]:
        with closing(sqlite3.connect(self.library_dir / "library.db")) as connection:
            return connection.execute(sql).fetchall()

    def sessions(self) -> list[tuple[Any, ...]]:
        """``(id_hash, email, created_at, expires_at)`` of every session row."""
        return self.rows("SELECT id_hash, email, created_at, expires_at FROM sessions ORDER BY created_at")

    def logins(self) -> list[tuple[Any, ...]]:
        """``(state_hash, nonce, verifier, destination, browser_hash, created_at)`` of every attempt row."""
        return self.rows("SELECT state_hash, nonce, verifier, destination, browser_hash, created_at FROM logins")

    def folder_names(self) -> list[str]:
        return [row[0] for row in self.rows("SELECT name FROM folders ORDER BY name")]

    def members(self) -> list[tuple[Any, ...]]:
        """``(folder_id, email, role)`` of every member row."""
        return self.rows("SELECT folder_id, email, role FROM members ORDER BY folder_id, email")

    def tickets(self) -> list[tuple[Any, ...]]:
        """``(ticket_hash, session_id_hash, presentation_id, created_at)`` of every ticket row (none before the
        table exists)."""
        if not self._has_table("tickets"):
            return []
        return self.rows("SELECT ticket_hash, session_id_hash, presentation_id, created_at FROM tickets")

    def grants(self) -> list[tuple[Any, ...]]:
        """``(token_hash, session_id_hash, presentation_id, created_at)`` of every grant row (none before the
        table exists)."""
        if not self._has_table("grants"):
            return []
        return self.rows("SELECT token_hash, session_id_hash, presentation_id, created_at FROM grants")

    def activity(self) -> list[tuple[Any, ...]]:
        """The activity lines, empty while the table does not exist (it arrives with US-0130)."""
        if not self._has_table("activity"):
            return []
        return self.rows("SELECT * FROM activity ORDER BY id")

    def _has_table(self, name: str) -> bool:
        with closing(sqlite3.connect(self.library_dir / "library.db")) as connection:
            found = connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
            return found.fetchone() is not None


@dataclass(frozen=True)
class Presentation:
    """A presentation the builder wrote: ids, name and the file at ``Library.presentation_path``."""

    id: str
    folder_id: str
    name: str
    path: Path


@dataclass(frozen=True)
class LibraryBuilder:
    """Folders, members and presentations written straight into the library database and its files."""

    database: Database
    clock: Callable[[], float]
    state_dir: Path

    def folder(self, name: str) -> str:
        folder_id = secrets.token_hex(16)
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO folders(id, name, name_key, created_at) VALUES (?, ?, ?, ?)",
                (folder_id, name, name_key(name), self.clock()),
            )
        return folder_id

    def folders(self, *names: str) -> dict[str, str]:
        """One folder per name, written in the given order; returns name to id."""
        return {name: self.folder(name) for name in names}

    def member(self, folder_id: str, email: str, role: str) -> None:
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO members(folder_id, email, role) VALUES (?, ?, ?)", (folder_id, email, role)
            )

    def numbered_folders(self, count: int, email: str | None = None, role: str = "RW") -> dict[str, str]:
        """``Folder 001`` to ``Folder <count>`` in one transaction, ``email`` (when given) a member of each; returns
        name to id."""
        ids = {f"Folder {number:03d}": secrets.token_hex(16) for number in range(1, count + 1)}
        with self.database.transaction(immediate=True) as connection:
            connection.executemany(
                "INSERT INTO folders(id, name, name_key, created_at) VALUES (?, ?, ?, ?)",
                [(folder_id, name, name_key(name), self.clock()) for name, folder_id in ids.items()],
            )
            if email is not None:
                connection.executemany(
                    "INSERT INTO members(folder_id, email, role) VALUES (?, ?, ?)",
                    [(folder_id, email, role) for folder_id in ids.values()],
                )
        return ids

    def presentation(  # noqa: PLR0913 - signature set by the design contract
        self, folder_id: str, name: str, *, size: int, modified: datetime, slides: int = 1, title: str | None = None
    ) -> Presentation:
        """A deck of ``slides`` slides padded to exactly ``size`` bytes, modified at ``modified``, and its row."""
        presentation_id = secrets.token_hex(16)
        path = Library(self.database, self.clock, state_dir=self.state_dir).presentation_path(
            folder_id, presentation_id
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(deck_bytes(title if title is not None else name, slides, size))
        os.utime(path, (modified.timestamp(), modified.timestamp()))
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO presentations(id, folder_id, name, name_key, created_at) VALUES (?, ?, ?, ?, ?)",
                (presentation_id, folder_id, name, name_key(name), self.clock()),
            )
        return Presentation(presentation_id, folder_id, name, path)

    def records(self, presentation: Presentation) -> Path:
        """Two history versions, two queued requests and one AI suggestion for ``presentation``, through the
        editor's own stores; returns their directory ``<state_dir>/files/<key>``."""
        history = HistoryStore(self.state_dir, self.clock)
        for reason in ("browser-save", "replace"):
            history.stage(presentation.path, presentation.path.read_bytes(), reason)
        store = RequestStore(self.state_dir)
        service = RequestService(store)
        service.queue(presentation.path, f"Shorten the title of {presentation.name}", None)
        service.queue(presentation.path, "Add a summary slide", None)
        service.write_review(
            presentation.path,
            [{"id": "s1", "slide": None, "title": "Fewer words", "why": "Dense", "change": "Cut the second line"}],
        )
        return store.record_dir(presentation.path).parent

    def standard_presentations(self, ids: dict[str, str]) -> dict[str, Presentation]:
        """The five presentations of the standard library in the folders of ``ids``; returns name to presentation."""
        return {
            name: self.presentation(ids[folder], name, size=size, slides=slides, modified=modified)
            for folder, name, size, slides, modified in STANDARD_PRESENTATIONS
        }

    def standard(self) -> dict[str, str]:
        """The folders and members of the spec's standard library (section 9); returns name to id."""
        ids = {name: self.folder(name) for name in (WCBIP, CARDIOLOGY, PNEUMO)}
        self.member(ids[WCBIP], LAMYA, "RW")
        self.member(ids[CARDIOLOGY], DAN, "RW")
        self.member(ids[CARDIOLOGY], CAROL, "RO")
        return ids


@dataclass
class RunningLibrary:
    """A started library server, its settings and directories."""

    server: LibraryServer
    settings: Settings
    clock: FakeClock
    library_dir: Path
    state_dir: Path
    database: Database

    @property
    def port(self) -> int:
        return self.server.port

    @property
    def library_netloc(self) -> str:
        return f"{LIBRARY_HOST}:{self.port}"

    @property
    def content_netloc(self) -> str:
        return f"{CONTENT_HOST}:{self.port}"

    @property
    def origin(self) -> str:
        return self.settings.library_origin

    @property
    def content_origin(self) -> str:
        return self.settings.library_content_origin

    @property
    def is_secure(self) -> bool:
        return self.origin.startswith("https://")

    @property
    def stored(self) -> StoredLibrary:
        return StoredLibrary(self.library_dir, self.state_dir)

    @property
    def builder(self) -> LibraryBuilder:
        return LibraryBuilder(self.database, self.clock, self.state_dir)

    def versions(self, presentation: Presentation) -> list[Version]:
        """The history versions of ``presentation``, newest first, from the state directory."""
        return HistoryStore(self.state_dir, self.clock).list_versions(presentation.path.resolve())

    def version_text(self, presentation: Presentation, version: Version) -> str:
        """The stored text of one history version."""
        store = HistoryStore(self.state_dir, self.clock)
        return store.read(presentation.path.resolve(), version.id).decode("utf-8")

    def client(self, host: str | None = None) -> HttpClient:
        """A client whose requests carry ``Host: host`` (default the library origin's host and port)."""
        return HttpClient(self.port, host if host is not None else self.library_netloc)

    def browser(self, resolver: dict[str, int] | None = None) -> Browser:
        """A fresh browser (no cookie); ``resolver`` maps other host names to loopback ports."""
        return Browser(self, dict(resolver or {}))

    def restart(self) -> LibraryServer:
        """Stop the server and start a new ``LibraryServer`` on the same settings (port, directory) and clock."""
        self.server.stop()
        self.server = LibraryServer(self.settings, clock=self.clock)
        self.server.start()
        return self.server

    @contextmanager
    def unreadable_database(self) -> Iterator[None]:
        """Inside the block ``library.db`` is a file of junk; the real file, untouched, is put back at the end.

        No server connection to the real file survives the swap: ``HttpClient`` sends each request on its own TCP
        connection (``Connection: close`` semantics, the handler closes after each answer), so each request runs on a
        new handler thread that opens a new SQLite connection (released by ``LibraryHandler.finish``) and meets the
        junk. Only this process's own connection is released here.
        """
        self.database.release()
        path = self.library_dir / "library.db"
        aside = path.with_name("library.db.aside")
        with closing(sqlite3.connect(path)) as connection:  # every committed page into the main file
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        path.replace(aside)
        path.write_bytes(b"this is not a database " * 512)
        try:
            yield
        finally:
            aside.replace(path)


@dataclass
class Browser:
    """One browser: library cookies, redirects followed across hosts, every visited address recorded."""

    running: RunningLibrary
    resolver: dict[str, int]
    cookies: dict[str, str] = field(default_factory=dict)
    persistent: set[str] = field(default_factory=set)  # names of the cookies set with a Max-Age
    deck_cookies: dict[tuple[str, str], str] = field(default_factory=dict)  # content origin, (path, name) to value
    visited: list[str] = field(default_factory=list)
    replies: list[LibraryReply] = field(default_factory=list)
    url: str = ""

    def open(self, address: str, *, follow: bool = True) -> LibraryReply:
        """GET ``address`` (absolute, or a path of the library origin) and follow redirects when ``follow``."""
        return self._navigate("GET", address, {}, follow=follow)

    def sign_in(self, google: FakeGoogle, email: str | None, destination: str | None = None) -> LibraryReply:
        """Choose ``Sign in with Google`` (``next=destination``) and pick ``email`` at Google, or cancel (None)."""
        if email is None:
            google.cancel()
        else:
            google.choose(email)
        query = "" if destination is None else f"?next={quote(destination, safe='')}"
        return self.open(f"/auth/start{query}")

    def sign_out(self) -> LibraryReply:
        """The ``Sign out`` form: a same origin POST, with the ``Origin`` a browser sends under ``same-origin``."""
        headers = {"Origin": self.running.origin, "Sec-Fetch-Site": "same-origin"}
        return self._navigate("POST", f"{self.running.origin}/auth/logout", headers, follow=True)

    def post_json(self, path: str, payload: Any, *, headers: dict[str, str] | None = None) -> LibraryReply:
        """POST ``payload`` (JSON encoded unless already bytes) with this browser's cookies and the headers of the
        library's own ``fetch``, or ``headers`` instead of them; redirects are not followed."""
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        sent = headers if headers is not None else self.page_post_headers()
        if self.cookies:
            sent = {**sent, "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
        reply = self.running.client().request("POST", path, headers=sent, body=body)
        self._keep_cookies(reply)
        self.replies.append(reply)
        return reply

    def add_member(self, folder_id: str, email: Any, role: Any) -> LibraryReply:
        """What ``Add member`` (or a member's role chooser) sends for the typed address and the chosen role."""
        return self.post_json(f"/api/folders/{folder_id}/members", {"email": email, "role": role})

    def remove_member(self, folder_id: str, email: Any) -> LibraryReply:
        """What a member's ``Remove`` button sends."""
        return self.post_json(f"/api/folders/{folder_id}/members/remove", {"email": email})

    def page_post_headers(self) -> dict[str, str]:
        """What Chromium sends with a ``fetch`` POST of JSON from a library page."""
        return {"Origin": self.running.origin, "Sec-Fetch-Site": "same-origin", "Content-Type": "application/json"}

    def open_presentation(self, presentation_id: str) -> LibraryReply:
        """Choose a presentation on a folder page: ``/open/<pid>`` of the library origin, redirects followed."""
        return self.open(f"{self.running.origin}/open/{presentation_id}")

    def deck(self, presentation_id: str, route: str, *, follow: bool = False, **headers: str) -> LibraryReply:
        """GET ``/d/<pid>/<route>`` on the content origin with this browser's cookies (``x_editor="1"`` sends
        ``X-Editor: 1``); redirects followed only when ``follow``."""
        address = f"{self.running.content_origin}/d/{presentation_id}/{route}"
        return self._navigate("GET", address, _header_names(headers), follow=follow)

    def upload(self, folder_id: str, name: str, data: bytes, *, headers: dict[str, str] | None = None) -> LibraryReply:
        """What the Upload control sends: ``POST /api/folders/<fid>/presentations`` with the raw bytes, the percent
        encoded name in ``X-File-Name`` and the headers of a same origin ``XMLHttpRequest`` (``headers`` replaces
        them)."""
        sent = (
            headers
            if headers is not None
            else {
                "Origin": self.running.origin,
                "Sec-Fetch-Site": "same-origin",
                "X-File-Name": quote(name, safe=""),
                "Content-Type": "text/html",
            }
        )
        if self.cookies:
            sent = {**sent, "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
        reply = self.running.client().request(
            "POST", f"/api/folders/{folder_id}/presentations", headers=sent, body=data
        )
        self._keep_cookies(reply)
        self.replies.append(reply)
        return reply

    def upload_declaring(self, folder_id: str, name: str, length: int) -> LibraryReply:
        """An upload that declares ``length`` bytes and sends none: the server must answer from the headers alone
        (the order of the checks is observable without sending 30 MB)."""
        headers = {
            "Host": self.running.library_netloc,
            "Origin": self.running.origin,
            "Sec-Fetch-Site": "same-origin",
            "X-File-Name": quote(name, safe=""),
            "Content-Type": "text/html",
            "Content-Length": str(length),
            "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items()),
        }
        return _raw_post(self.running.port, f"/api/folders/{folder_id}/presentations", headers)

    def save_headers(self, presentation_id: str) -> dict[str, str]:
        """What Chromium sends with the editor's own ``fetch`` of ``POST /d/<pid>/content``, grant cookie included."""
        path = f"/d/{presentation_id}/"
        cookie = "; ".join(f"{name}={value}" for (where, name), value in self.deck_cookies.items() if where == path)
        headers = {
            "Origin": self.running.content_origin,
            "Sec-Fetch-Site": "same-origin",
            "Content-Type": "application/json",
            "X-Editor": "1",
        }
        return {**headers, "Cookie": cookie} if cookie else headers

    def post_deck(self, presentation_id: str, route: str, payload: Any) -> LibraryReply:
        """What the editor sends with ``fetch`` to ``POST /d/<pid>/<route>`` (JSON, its headers and grant cookie)."""
        client = self.running.client(self.running.content_netloc)
        return client.request(
            "POST",
            f"/d/{presentation_id}/{route}",
            headers=self.save_headers(presentation_id),
            body=json.dumps(payload).encode(),
        )

    def save(
        self, presentation_id: str, html: str, *, base_mtime: float | None = None, force: bool = False
    ) -> LibraryReply:
        """What the editor sends to store ``html`` (a whole document) for a presentation this browser opened."""
        payload: dict[str, Any] = {"html": html}
        if base_mtime is not None:
            payload["base_mtime"] = base_mtime
        if force:
            payload["force"] = True
        return self.post_deck(presentation_id, "content", payload)

    def send_save_length(self, presentation_id: str, length: int) -> LibraryReply:
        """A save declaring ``Content-Length: length`` and sending no body: the server must refuse by the header."""
        headers = {**self.save_headers(presentation_id), "Host": self.running.content_netloc}
        headers["Content-Length"] = str(length)
        return _raw_post(self.running.port, f"/d/{presentation_id}/content", headers)

    def grant(self, presentation_id: str) -> str | None:
        """The value of the grant cookie of a presentation, None when the browser holds none."""
        path = f"/d/{presentation_id}/"
        return next((value for (where, _), value in self.deck_cookies.items() if where == path), None)

    def copied(self) -> Browser:
        """A command line tool holding a copy of every cookie of this browser, no history."""
        return Browser(
            self.running,
            dict(self.resolver),
            cookies=dict(self.cookies),
            persistent=set(self.persistent),
            deck_cookies=dict(self.deck_cookies),
        )

    def reopened(self) -> Browser:
        """The browser closed and opened again: the cookies without ``Max-Age`` are gone, the others kept."""
        kept = {name: value for name, value in self.cookies.items() if name in self.persistent}
        return Browser(self.running, dict(self.resolver), cookies=kept, persistent=set(kept))

    def callback_addresses(self) -> list[str]:
        return [address for address in self.visited if urlsplit(address).path == "/auth/callback"]

    def hosts_visited(self) -> set[str]:
        return {urlsplit(address).netloc for address in self.visited}

    def _navigate(self, method: str, address: str, headers: dict[str, str], *, follow: bool) -> LibraryReply:
        url = urljoin(self.url or f"{self.running.origin}/", address)
        reply = self._send(method, url, headers)
        for _ in range(MAX_REDIRECTS):
            if not follow or reply.status not in REDIRECT_STATUSES:
                return reply
            url = urljoin(url, reply.headers["location"])
            reply = self._send("GET", url, {})
        raise AssertionError(f"more than {MAX_REDIRECTS} redirects, last {url}")

    def _send(self, method: str, url: str, headers: dict[str, str]) -> LibraryReply:
        parts = urlsplit(url)
        self.visited.append(url)
        self.url = url
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        if self.running.is_secure and parts.netloc in {self.running.library_netloc, self.running.content_netloc}:
            headers = {**headers, "X-Forwarded-Proto": parts.scheme}  # nginx in front of the https origins
        if parts.scheme in {"http", "https"} and parts.netloc == self.running.library_netloc:
            if self.cookies:
                headers = {**headers, "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
            reply = self.running.client().request(method, path, headers=headers)
            self._keep_cookies(reply)
        elif parts.scheme in {"http", "https"} and parts.netloc == self.running.content_netloc:
            sent = [f"{name}={value}" for (where, name), value in self.deck_cookies.items() if path.startswith(where)]
            if sent:
                headers = {**headers, "Cookie": "; ".join(sent)}
            reply = self.running.client(self.running.content_netloc).request(method, path, headers=headers)
            self._keep_deck_cookies(reply)
        elif parts.hostname in self.resolver:
            reply = HttpClient(self.resolver[str(parts.hostname)], parts.netloc).request(method, path, headers=headers)
        elif parts.hostname == "127.0.0.1" and parts.port is not None:
            reply = HttpClient(parts.port, parts.netloc).request(method, path, headers=headers)
        else:
            raise AssertionError(f"the browser cannot reach {url!r}")
        self.replies.append(reply)
        return reply

    def _keep_deck_cookies(self, reply: LibraryReply) -> None:
        for header in reply.set_cookies:
            pair, *attributes = (part.strip() for part in header.split(";"))
            name, _, value = pair.partition("=")
            path = next((item[len("Path=") :] for item in attributes if item.startswith("Path=")), "/")
            if "Max-Age=0" in attributes:
                self.deck_cookies.pop((path, name), None)
            else:
                self.deck_cookies[(path, name)] = value

    def _keep_cookies(self, reply: LibraryReply) -> None:
        for header in reply.set_cookies:
            pair, _, attributes = header.partition(";")
            name, _, value = pair.strip().partition("=")
            attribute_names = attributes.replace(" ", "").lower().split(";")
            if "max-age=0" in attribute_names:
                self.cookies.pop(name, None)
                self.persistent.discard(name)
                continue
            self.cookies[name] = value
            if any(attribute.startswith("max-age=") for attribute in attribute_names):
                self.persistent.add(name)
            else:
                self.persistent.discard(name)


def _raw_post(port: int, path: str, headers: dict[str, str]) -> LibraryReply:
    """A POST of these headers and no body, read to the end (the server closes the connection after a refusal)."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
        head = f"POST {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        sock.sendall((head + "\r\n").encode())
        raw = b""
        while chunk := sock.recv(65536):
            raw += chunk
    status = int(raw.split(b" ", 2)[1])
    return LibraryReply(status=status, headers={}, body=raw.split(b"\r\n\r\n", 1)[-1], set_cookies=())


def deck_bytes(title: str, slides: int, size: int) -> bytes:
    """A presentation (``data-doc-type="presentation"``, ``slides`` slides) padded by an HTML comment to ``size``
    bytes; a size below the smallest deck is the start of one, only its size matters then."""
    sections = "".join(
        f'<section class="slide" data-type="slide" data-id="slide-{number}" data-title="Slide {number}">'
        f'<h1 data-editable="text">{html_escape(title) if number == 1 else f"Slide {number}"}</h1></section>'
        for number in range(1, slides + 1)
    )
    head = (
        f'<!DOCTYPE html><html lang="en" data-doc-type="presentation"><head><meta charset="utf-8">'
        f"<title>{html_escape(title)}</title></head><body>{sections}"
    ).encode()
    tail = b"</body></html>\n"
    padding = size - len(head) - len(tail) - len(PADDING_OPEN) - len(PADDING_CLOSE)
    if padding < 0:
        return (head + tail + b" " * size)[:size]
    return head + PADDING_OPEN + b"x" * padding + PADDING_CLOSE + tail


def signed_in(running: RunningLibrary, google: FakeGoogle, email: str) -> Browser:
    """A fresh browser signed in as ``email`` through ``google``."""
    browser = running.browser()
    browser.sign_in(google, email)
    return browser


def visible_texts(reply: LibraryReply) -> list[str]:
    """The text nodes of the page body, unescaped, in order."""
    body = reply.text.split("<body>", 1)[1]
    return [html_unescape(text).strip() for text in re.split(r"<[^>]*>", body) if text.strip()]


def launch_chromium(playwright: Playwright, *other_hosts: str) -> Chromium:
    """Chromium resolving both library host names and ``other_hosts`` to loopback (``--host-resolver-rules``,
    DEC-049). A hostile page must be served from loopback too: Chromium refuses a public page that frames or fetches
    a loopback address (Private Network Access), which would hide what the library itself does."""
    rules = ", ".join(f"MAP {host} 127.0.0.1" for host in (LIBRARY_HOST, CONTENT_HOST, *other_hosts))
    return playwright.chromium.launch(args=[f"--host-resolver-rules={rules}"])


def person_context(
    chromium: Chromium, running: RunningLibrary, session: str | None, *, zone: str = "UTC"
) -> BrowserContext:
    """A browser context in the time zone ``zone`` holding the library session cookie ``session`` (None: none)."""
    context = chromium.new_context(timezone_id=zone)
    if session is not None:
        context.add_cookies([{"name": "lib", "value": session, "url": running.origin}])
    return context


def deck_frame(page: Page) -> Frame:
    """The deck frame of an editor shell (the frame that loaded ``.../content-frame``)."""
    frame = page.frame(url=re.compile(r"/content-frame"))
    assert frame is not None, "no deck frame"
    return frame


def deck_with_pictures(title: str, slides: int) -> bytes:
    """A presentation of ``slides`` slides, each holding one embedded picture (a 1 by 1 PNG data address)."""
    picture = "data:image/png;base64," + base64.b64encode(PNG_1X1).decode()
    sections = "".join(
        f'<section class="slide" data-type="slide" data-id="slide-{number}" data-title="Slide {number}">'
        f'<h1 data-editable="text">{html_escape(title) if number == 1 else f"Slide {number}"}</h1>'
        f'<img src="{picture}" alt="picture {number}"></section>'
        for number in range(1, slides + 1)
    )
    return (
        f'<!DOCTYPE html><html lang="en" data-doc-type="presentation"><head><meta charset="utf-8">'
        f"<title>{html_escape(title)}</title></head><body>{sections}</body></html>\n"
    ).encode()


def deck_with_notes(titles: tuple[str, ...], notes: str, script: str = "") -> bytes:
    """A real "ei" deck of ``titles`` whose slide 1 carries the speaker notes ``notes`` and, when ``script`` is not
    empty, the element ``probe`` and that script (the presentation's own script, as a hostile one would be)."""
    extra = f'<aside data-role="speaker-notes">{html_escape(notes)}</aside>'
    if script:
        extra += f'<p id="probe"></p><script>{script}</script>'

    def put_in_first_slide(deck: str) -> str:
        end = deck.index("</article>")
        return deck[:end] + extra + deck[end:]

    return build_deck("ei", titles, mutate=put_in_first_slide).encode()


TITLE_FIELD = "h1[data-editable~='text']"


def turn_edit_on(page: Page) -> None:
    """Click the edit button of the editor shell and wait for the first title of the deck to be editable."""
    page.click("#edit-mode-btn")
    frame = deck_frame(page)
    wait_for_js(frame, f'document.querySelector("{TITLE_FIELD}").isContentEditable', True, what="editable")


def type_in_title(page: Page, text: str, *, replace: bool = False, index: int = 0, insert: bool = False) -> None:
    """Type ``text`` at the end of the title ``index`` of the deck (the whole title replaced when ``replace``); the
    focus stays in the field. ``insert`` pastes the text in one step (characters the keyboard has no key for)."""
    field = deck_frame(page).locator(TITLE_FIELD).nth(index)
    field.click()
    page.keyboard.press("ControlOrMeta+A" if replace else "End")
    if insert:
        page.keyboard.insert_text(text)
    else:
        page.keyboard.type(text)


def leave_field(page: Page) -> None:
    """Click the file name of the toolbar: the edited field loses the focus."""
    page.click("#toolbar-filename")


def with_title(presentation: Presentation, title: str) -> str:
    """The stored deck of ``presentation`` with the first title replaced, as a whole document."""
    text = presentation.path.read_text(encoding="utf-8")
    return re.sub(r"(<h1[^>]*>)[^<]*(</h1>)", lambda m: f"{m[1]}{html_escape(title)}{m[2]}", text, count=1)


def stored_title(presentation: Presentation) -> str:
    """The first ``<h1>`` of the file stored for ``presentation``."""
    match = re.search(r"<h1[^>]*>([^<]*)</h1>", presentation.path.read_text(encoding="utf-8"))
    assert match is not None, "no title in the stored file"
    return html_unescape(match.group(1))


POLL_MILLISECONDS = 100
FRAME_TITLE = "document.querySelector('h1').textContent"


@dataclass
class EditorLibrary:
    """The running library with the standard folders and presentations, and the pages opened so far."""

    running: RunningLibrary
    google: FakeGoogle
    chromium: Chromium
    ids: dict[str, str]
    decks: dict[str, Presentation]
    pages: dict[str, Page] = field(default_factory=dict)

    def page(self, email: str) -> Page:
        """A new page of ``email``, signed in (one per call: two people, or one person twice)."""
        person = signed_in(self.running, self.google, email)
        return person_context(self.chromium, self.running, person.cookies["lib"]).new_page()

    def open(self, email: str, name: str, *, edit: bool = False) -> Page:
        """The page of ``email`` on the presentation ``name``, deck shown, in edit mode when ``edit``."""
        page = self.page(email)
        deck = self.decks[name]
        page.goto(f"{self.running.origin}/open/{deck.id}")
        page.wait_for_url(f"{self.running.content_origin}/d/{deck.id}/")
        wait_for_js(deck_frame(page), "document.querySelectorAll('.slide').length > 0", True, what="deck")
        if edit:
            turn_edit_on(page)
        return page

    def served_title(self, email: str, name: str) -> str:
        """The title of slide 1 served to ``email`` for the content of ``name`` (a fresh browser, as a reload)."""
        person = signed_in(self.running, self.google, email)
        deck = self.decks[name]
        person.open_presentation(deck.id)
        match = re.search(r"<h1[^>]*>([^<]*)</h1>", person.deck(deck.id, "content", x_editor="1").text)
        assert match is not None
        return match.group(1)

    def titles_in_history(self, name: str) -> list[str]:
        """The first title of each history version of ``name``, newest first."""
        deck = self.decks[name]
        found = []
        for version in self.running.versions(deck):
            match = re.search(r"<h1[^>]*>([^<]*)</h1>", self.running.version_text(deck, version))
            found.append(match[1] if match else "")
        return found


@pytest.fixture
def library(
    library_server: Callable[..., RunningLibrary], fake_google: FakeGoogle, chromium: Chromium
) -> EditorLibrary:
    running = library_server(fake_google, poll_interval=POLL_MILLISECONDS)
    ids = running.builder.standard()
    return EditorLibrary(running, fake_google, chromium, ids, running.builder.standard_presentations(ids))


def notice_visible(page: Page, notice: str) -> bool:
    return page.evaluate(f"!document.getElementById('{notice}').hidden")


def frame_title(page: Page) -> str:
    """The title shown in the deck frame; empty while the frame navigates (a reload, a new content)."""
    try:
        return str(deck_frame(page).evaluate(FRAME_TITLE))
    except PlaywrightError:
        return ""


def wait_stored(page: Page, deck: Presentation, title: str) -> None:
    wait_until(page, lambda: stored_title(deck), lambda found: found == title, what=f"stored title {title}")


def valid_deck(slides: int = 3, size: int | None = None) -> bytes:
    """A real "ei" presentation of ``slides`` slides that the editor's checks accept; padded to ``size`` bytes with an
    HTML comment when given (never smaller than the deck itself)."""
    deck = build_deck("ei", tuple(f"Slide {number}" for number in range(1, slides + 1))).encode()
    if size is None or size <= len(deck) + len(PADDING_OPEN) + len(PADDING_CLOSE):
        return deck
    padding = size - len(deck) - len(PADDING_OPEN) - len(PADDING_CLOSE)
    return deck.replace(b"</body>", PADDING_OPEN + b"x" * padding + PADDING_CLOSE + b"</body>", 1)


def open_presenter(page: Page) -> Page:
    """Press the key S in the editor shell: the deck's presenter window, once the notes reached it."""
    with page.context.expect_page(timeout=10_000) as opened:
        page.locator("body").press("s")
    return opened.value


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def library_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., RunningLibrary]]:
    """Return ``start(google=None, google_registered=True, scheme="http", **settings_overrides)``; all stopped at
    teardown; ``scheme="https"`` gives two https origins on the same loopback port (nginx's view).

    With ``google`` the credentials file points at that ``FakeGoogle`` and the sign in return address
    ``<library origin>/auth/callback`` is registered in its console and listed in the file, unless
    ``google_registered`` is False (then neither lists it).
    """
    started: list[RunningLibrary] = []

    def start(
        google: FakeGoogle | None = None,
        *,
        google_registered: bool = True,
        scheme: str = "http",
        **settings_overrides: Any,
    ) -> RunningLibrary:
        port = free_port()
        library_dir = tmp_path / "library"
        state_dir = tmp_path / "state"
        values: dict[str, Any] = {
            "host": "127.0.0.1",
            "port": port,
            "library_origin": f"{scheme}://{LIBRARY_HOST}:{port}",
            "library_content_origin": f"{scheme}://{CONTENT_HOST}:{port}",
            "library_dir_override": library_dir,
            "state_dir_override": state_dir,
        }
        clock = FakeClock()
        if google is not None:
            redirect = f"{values['library_origin']}/auth/callback"
            registered = [redirect] if google_registered else [UNREGISTERED_REDIRECT]
            google.registered_redirects.update(registered)
            google.clock = clock
            credentials = tmp_path / "google-oauth.json"
            credentials.write_text(json.dumps(google.credentials(registered)), encoding="utf-8")
            values["google_credentials_override"] = credentials
        values.update(settings_overrides)
        settings = Settings(**values)
        # ``webserve`` runs with one state directory: the editor's history writer reads it from the environment.
        monkeypatch.setenv("HTMLEDITOR_STATE_DIR", str(settings.state_dir))
        reset_settings_cache()
        database = Database(library_dir / "library.db")
        server = LibraryServer(settings, clock=clock)
        running = RunningLibrary(
            server=server,
            settings=settings,
            clock=clock,
            library_dir=library_dir,
            state_dir=state_dir,
            database=database,
        )
        started.append(running)
        server.start()
        return running

    yield start
    for running in started:  # ``running.server`` is the last one a restart started
        running.server.stop()
        running.database.release()


@pytest.fixture
def fake_google() -> Iterator[FakeGoogle]:
    google = FakeGoogle()
    yield google
    google.stop()


@pytest.fixture
def evil_listener() -> Iterator[RecordingListener]:
    listener = RecordingListener()
    yield listener
    listener.stop()


def _header_names(headers: dict[str, str]) -> dict[str, str]:
    """``x_forwarded_proto`` keyword to ``X-Forwarded-Proto``."""
    return {"-".join(part.capitalize() for part in name.split("_")): value for name, value in headers.items()}
