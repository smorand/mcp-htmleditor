"""Web library server (SPEC-0025): one listener answering the library origin and the content origin.

Gate order of every request (DEC-007, DEC-008, DEC-010): a header block readable two ways is refused (400,
inherited ``_refuse_ambiguous_headers``); ``GET /health`` answers on any host name with ``running`` and the version
only; a ``Host`` other than the netloc of one of the two configured origins gets ``403 {"error": "forbidden host"}``;
``X-Forwarded-Proto: http`` gets ``308`` to the configured origin of that host; on the content origin a path in no
row gets a ``302`` to the library origin (DEC-011) and a ``/d/<pid>/`` row needs a live grant, the presentation and a
role allowing the route before the inherited editor method answers through the DEC-003 hooks (DEC-037, DEC-040,
DEC-041); on the library origin the route table decides (DEC-021):
a state changing request needs its ``Origin`` (DEC-022) before the route or the session is looked up, and a JSON route
its ``Content-Type: application/json`` before the session; a path in no row or a non public route gives the sign in
page to a visitor and ``Access denied.`` to a signed in person; the role and the permission come before the body; a
``sqlite3.Error`` or ``OSError`` while reading the library gives ``503`` and the unavailable page (DEC-024). Every
answer carries the protection headers of DEC-009 (``end_headers``).
"""

from __future__ import annotations

import importlib
import json
import logging
import pkgutil
import re
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from types import TracebackType
from typing import Any, cast, override
from urllib.parse import parse_qsl, urlsplit

from ..config import Settings, is_origin
from ..http_server import (
    SaveRefusal,
    _EditorHandler,
    _EditorServer,
    _static_dir,
    check_content_type,
    parse_content_length,
)
from ..request_service import RequestService
from ..request_store import RequestStore
from ..version import __version__
from . import pages
from .access import Answer, Context, EditorAnswer, Permission, Role, Route, authorize, json_answer
from .routes_deck import DENIED_PAYLOAD, deck_path, denied, library_shell
from .signin import (
    BROWSER_COOKIE,
    GRANT_COOKIE,
    SESSION_COOKIE,
    Accounts,
    GoogleClient,
    Live,
    safe_destination,
)
from .store import Database, Library

logger = logging.getLogger(__name__)

SAME_HOST_MESSAGE = "The library origin and the content origin must be two different host names."
FORBIDDEN_HOST = "forbidden host"
HEALTH_PATH = "/health"
JSON_POLICY = "default-src 'none'; frame-ancestors 'none'"
PAGE_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)
FRAME_POLICY = "frame-ancestors 'self'"  # the deck frame: framed by the editor shell of its own origin only
SHELL_POLICY = "frame-ancestors 'none'"  # the editor shell runs the editor's own inline styles and scripts
FRAME_DENIED = "DENY"
FRAME_SAME_ORIGIN = "SAMEORIGIN"
EDITOR_HEADER = "X-Editor"  # every fetch of the editor in the library carries it (DEC-040)
ROUTES_MODULE_PREFIX = "routes_"
STRICT_TRANSPORT = "max-age=31536000"
POLL_INTERVAL_SECONDS = 0.05
PLAIN_SCHEME = "http"
SECURE_SCHEME = "https"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
FETCH_SITES_ALLOWED = frozenset({"same-origin", "none"})
FOLDER_GROUP = "fid"
PRESENTATION_GROUP = "pid"
HOST_PREFIX = "__Host-"
SECURE_PREFIX = "__Secure-"
DATABASE_NAME = "library.db"
CALLBACK_PATH = "/auth/callback"
JSON_BODY_MAX_BYTES = 65_536  # a JSON route carries a name, an address, a role: far below this


class LibraryConfigError(Exception):
    """The settings cannot run the library (the message is the user text)."""


@dataclass(frozen=True, slots=True)
class DeckTarget:
    """The presentation a content origin request is about, once its grant and role hold: the stored file, the
    name (without ``.html``) and the person's role."""

    path: Path
    name: str
    role: Role
    presentation_id: str = ""


def health_answer() -> dict[str, Any]:
    """The liveness answer: running and the version, nothing about files, process or presentations (DEC-010)."""
    return {"ok": True, "status": "ok", "version": __version__}


def cookie_name(origin: str, base: str, path: str = "/") -> str:
    """``lib`` on http, ``__Host-lib`` on https: the prefix forbids a parent domain or another path from setting it.
    A cookie of a narrower path (a grant, ``/d/<pid>/``) takes ``__Secure-``, since ``__Host-`` requires ``Path=/``."""
    if urlsplit(origin).scheme != SECURE_SCHEME:
        return base
    return f"{HOST_PREFIX if path == '/' else SECURE_PREFIX}{base}"


def cookie_header(origin: str, base: str, value: str, *, max_age: int | None, path: str = "/") -> str:
    """The ``Set-Cookie`` value (DEC-017, DEC-037); ``max_age`` None is a browser session cookie, 0 clears it."""
    parts = [f"{cookie_name(origin, base, path)}={value}", f"Path={path}", "HttpOnly", "SameSite=Lax"]
    if max_age is not None:
        parts.append(f"Max-Age={max_age}")
    if urlsplit(origin).scheme == SECURE_SCHEME:
        parts.append("Secure")
    return "; ".join(parts)


def parse_cookies(headers: list[str]) -> dict[str, str]:
    """Name to value of every ``Cookie`` header; the first of a repeated name wins."""
    cookies: dict[str, str] = {}
    for header in headers:
        for pair in header.split(";"):
            name, separator, value = pair.strip().partition("=")
            if separator and name not in cookies:
                cookies[name] = value
    return cookies


def load_routes() -> tuple[Route, ...]:
    """The rows of every ``routes_*`` module of the package; adding a module never edits this file (DEC-021)."""
    rows: list[Route] = []
    for module_info in pkgutil.iter_modules([str(Path(__file__).parent)]):
        if module_info.name.startswith(ROUTES_MODULE_PREFIX):
            module = importlib.import_module(f"{__package__}.{module_info.name}")
            rows.extend(module.ROUTES)
    return tuple(rows)


ROUTES = load_routes()


class LibraryHandler(_EditorHandler):
    """The library gate in front of every method; the connection bounds and ``do_OPTIONS`` are inherited."""

    policy = JSON_POLICY
    frame_options = FRAME_DENIED
    _deck: DeckTarget | None = None

    @override
    def do_GET(self) -> None:
        self._dispatch()

    @override
    def do_POST(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:  # noqa: N802 - http.server dispatches to do_<METHOD>
        self._dispatch()

    @override
    def end_headers(self) -> None:
        self._send_common_headers()
        super().end_headers()

    @override
    def finish(self) -> None:
        """The thread of this connection ends with it: so does its database connection."""
        try:
            super().finish()
        finally:
            self._library_server().database.release()

    def _dispatch(self) -> None:
        self.policy = JSON_POLICY  # one handler serves several requests of a keep alive connection
        self.frame_options = FRAME_DENIED
        self._deck = None
        if self.command != "GET":  # a body is never read: it must not desynchronize the next request
            self.close_connection = True
        if self._refuse_ambiguous_headers():
            return
        target = urlsplit(self.path)
        if self.command == "GET" and (target.path.rstrip("/") or "/") == HEALTH_PATH:
            self._send_json(health_answer())
            return
        origin = self._library_server().origin_for(self.headers.get("Host", ""))
        if origin is None:
            self._refuse(FORBIDDEN_HOST, self.headers.get("Host", ""))
            return
        if self._arrived_in_plain(origin):
            self._redirect_secure(origin, target.path, target.query)
            return
        if self._library_server().is_content_host(self.headers.get("Host", "")):
            self._serve_content_origin(origin, self._request_path(target.path), target.query)
            return
        self._serve_library(origin, self._request_path(target.path), target.query)

    def _serve_content_origin(self, origin: str, path: str, query: str) -> None:
        """A path in no row goes to the library origin (DEC-011); a row is answered once the grant, the presentation
        and the role hold, reads guarded like the library's (DEC-024)."""
        route = self._library_server().find_route("content", self.command, path)
        if route is None:
            self._redirect_to_library()
            return
        if self._refused_by_origin_rule(origin, route):
            logger.warning("Refused %s %s: origin or content type", self.command, path)
            self._respond(origin, denied())
            return
        try:
            answer = self._deck_answer(route, path, query)
        except (sqlite3.Error, OSError) as exc:
            logger.error("Library unavailable for %s %s: %s", self.command, path, type(exc).__name__)
            answer = Answer(503, pages.library_unavailable())
        self._respond(origin, answer)

    def _refused_by_origin_rule(self, origin: str, route: Route) -> bool:
        """DEC-022 on the content origin: a state changing request carries this origin's ``Origin`` and a JSON route
        the JSON content type, before any grant is looked up."""
        if self.command in SAFE_METHODS:
            return False
        return not self._origin_ok(origin) or (route.is_json and not self._is_json())

    def _deck_answer(self, route: Route, path: str, query: str) -> Answer | EditorAnswer:
        """Grant (DEC-037), then presentation, then role and permission (DEC-021), recomputed at every request; a
        refusal depends on who asked (DEC-040). On success the hooks serve ``DeckTarget`` (DEC-003)."""
        server = self._library_server()
        context = self._context(query)
        match = route.pattern.fullmatch(path)
        presentation_id = match.groupdict().get(PRESENTATION_GROUP) if match is not None else None
        if route.permission is Permission.PUBLIC:
            return route.handler(context)
        if presentation_id is None:  # fail closed: every other content row names its presentation
            return denied()
        cookies = parse_cookies(self.headers.get_all("Cookie") or [])
        token = cookies.get(
            cookie_name(server.settings.library_content_origin, GRANT_COOKIE, deck_path(presentation_id))
        )
        grant = server.accounts.grant_for(presentation_id, token)
        if not isinstance(grant, Live):
            return self._grant_missing(presentation_id)
        presentation = server.library.presentation(presentation_id)
        role = server.library.role_in(grant.email, presentation.folder_id) if presentation is not None else None
        if presentation is None or role is None or not authorize(role, route.permission):
            logger.warning("Refused %s %s: no right", self.command, path)
            return self._deck_refusal(route, presentation_id)
        self._deck = DeckTarget(
            server.library.presentation_path(presentation.folder_id, presentation_id),
            presentation.name,
            role,
            presentation_id,
        )
        return route.handler(replace(context, folder_id=presentation.folder_id, role=role))

    def _grant_missing(self, presentation_id: str) -> Answer:
        """No grant, or one that no longer resolves: the editor's fetch learns the session ended; anything else goes
        to ``/open/<pid>`` (the sign in page for a visitor or a copied session)."""
        if self.headers.get(EDITOR_HEADER) == "1":
            return json_answer(401, {"error": pages.SESSION_EXPIRED, "code": "session_expired"})
        return self._to_open(presentation_id)

    def _deck_refusal(self, route: Route, presentation_id: str) -> Answer:
        """A live grant without the right (or a presentation gone): JSON, except a navigation of the browser, sent to
        ``/open/<pid>``, which answers ``Access denied.``."""
        if route.is_navigation and self.headers.get(EDITOR_HEADER) != "1":
            return self._to_open(presentation_id)
        return denied()

    def _to_open(self, presentation_id: str) -> Answer:
        return Answer(302, location=f"{self._library_server().settings.library_origin}/open/{presentation_id}")

    def _context(self, query: str) -> Context:
        """The context of a content origin request: no session, the person comes from a grant."""
        server = self._library_server()
        return Context(
            person_email=None,
            query=dict(reversed(parse_qsl(query, keep_blank_values=True))),
            session_token=None,
            browser_id=None,
            accounts=server.accounts,
            library=server.library,
            library_origin=server.settings.library_origin,
            content_origin=server.settings.library_content_origin,
        )

    def _respond(self, origin: str, answer: Answer | EditorAnswer) -> None:
        """An editor answer is written by the inherited method of its route, the others by ``_send_answer``."""
        if not isinstance(answer, EditorAnswer):
            self._send_answer(origin, answer)
            return
        if answer.route == "shell":
            self.policy = SHELL_POLICY
        if answer.is_framed:
            self.policy = FRAME_POLICY
            self.frame_options = FRAME_SAME_ORIGIN
        editor_methods = {
            "content": self._serve_content,
            "content-frame": self._serve_content_frame,
            "arch-layout": self._run_arch_layout,
            "download": self._serve_download,
            "export-pptx": self._export_pptx,
            "request-delete": self._delete_request,
            "request-queue": self._queue_request,
            "requests": self._list_requests,
            "review-apply": self._apply_suggestion,
            "save": self._receive_content,
            "shell": self._serve_editor_html,
            "static": self._serve_library_static,
            "status": self._serve_status,
        }
        editor_methods[answer.route]()

    @override
    def _serve_status(self) -> None:
        """DEC-041: the change marker and the name, never a path, a process number or a folder; the request
        revision only for a role that may read the requests."""
        deck = self._deck
        if deck is None:  # every route answering the status sets the deck first
            self._not_found()
            return
        try:
            mtime = deck.path.stat().st_mtime
        except OSError:
            mtime = 0.0
        settings = self._library_server().settings
        is_editor = authorize(deck.role, Permission.EDIT)
        payload: dict[str, Any] = {
            "mtime": mtime,
            "update_in_progress": False,
            "update_expires_in": None,
            "filename": self._served_name(),
            "poll_interval": settings.poll_interval,
            "port": 0,
            "requests_revision": RequestService(RequestStore(settings.state_dir)).revision(deck.path)
            if is_editor
            else 0,
        }
        self._send_json(payload)

    @override
    def _serve_editor_html(self) -> None:
        """DEC-038: the shell of the presentation of this request, derived from ``static/editor.html``."""
        deck = self._deck
        if deck is None:  # the shell row sets the deck first
            self._not_found()
            return
        try:
            source = (_static_dir() / "editor.html").read_text(encoding="utf-8")
        except OSError:
            self._not_found()
            return
        body = library_shell(
            source, deck.presentation_id, self._library_server().settings.library_origin, deck.role
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", pages.HTML_CONTENT_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_library_static(self) -> None:
        """A product file (script, style, picture of the editor): no library content, so no grant (DEC-007)."""
        self._serve_static(urlsplit(self.path).path[len("/static/") :])

    @override
    def _served_file(self) -> str | None:
        return str(self._deck.path) if self._deck is not None else None

    @override
    def _served_name(self) -> str:
        return f"{self._deck.name}.html" if self._deck is not None else ""

    @override
    def _save_lock(self) -> PresentationLock:
        """DEC-028: the lock of this presentation, taken before the conflict check, then the row re-checked."""
        deck = self._deck
        presentation_id = deck.presentation_id if deck is not None else ""
        return self._library_server().save_lock(presentation_id)

    @override
    def _pptx_options(self) -> dict[str, bool]:
        """DEC-043: the flow engine only (no Chromium, no script of the deck run here) and data URI pictures only."""
        return {"paint": False, "embedded_pictures_only": True}

    @override
    def _failure_reason(self, exc: Exception) -> str:
        """The operating system reason, never ``str(exc)``, which names the stored path (DEC-042)."""
        reason = exc.strerror if isinstance(exc, OSError) else None
        return reason or pages.EXPORT_FAILED

    @override
    def _send_no_store_headers(self) -> None:
        """``end_headers`` already sends them with every answer (DEC-009)."""

    def _serve_library(self, origin: str, path: str, query: str) -> None:
        """``Origin`` rule, then the answer; a library that cannot be read is the unavailable page (DEC-024).

        Only the reads are guarded: an error while writing the answer is the connection's, not the library's.
        """
        if self.command not in SAFE_METHODS and not self._origin_ok(origin):
            logger.warning("Refused %s %s: origin", self.command, path)
            self._send_answer(origin, Answer(403, pages.access_denied()))
            return
        route = self._library_server().find_route("library", self.command, path)
        if route is not None and route.is_json and not self._is_json():
            logger.warning("Refused %s %s: content type", self.command, path)
            self._send_answer(origin, Answer(403, pages.access_denied()))
            return
        try:
            answer = self._library_answer(origin, route, path, query)
        except (sqlite3.Error, OSError) as exc:
            logger.error("Library unavailable for %s %s: %s", self.command, path, type(exc).__name__)
            answer = Answer(503, pages.library_unavailable())
        self._respond(origin, answer)

    def _library_answer(self, origin: str, route: Route | None, path: str, query: str) -> Answer | EditorAnswer:
        """Session, role and permission (DEC-021), then the JSON body of a JSON route (DEC-019), then the handler; no
        body is read before the permission holds."""
        server = self._library_server()
        cookies = parse_cookies(self.headers.get_all("Cookie") or [])
        token = cookies.get(cookie_name(origin, SESSION_COOKIE))
        session = server.accounts.session_for(token)
        if route is None or (route.permission is not Permission.PUBLIC and session is None):
            return self._refusal(path, signed_in=session is not None)
        folder_id, presentation_id = self._target(route, path)
        role = server.library.role_in(session.email, folder_id) if session is not None else None
        if not authorize(role, route.permission):
            return Answer(403, pages.access_denied())
        payload = self._read_library_json() if route.is_json else {}
        if isinstance(payload, Answer):
            return payload
        context = Context(
            person_email=session.email if session is not None else None,
            query=dict(reversed(parse_qsl(query, keep_blank_values=True))),
            session_token=token if session is not None else None,
            browser_id=cookies.get(cookie_name(origin, BROWSER_COOKIE)),
            accounts=server.accounts,
            library=server.library,
            folder_id=folder_id,
            role=role,
            payload=payload,
            session=session,
            presentation_id=presentation_id,
            library_origin=server.settings.library_origin,
            content_origin=server.settings.library_content_origin,
        )
        return route.handler(context)

    def _target(self, route: Route, path: str) -> tuple[str | None, str | None]:
        """The folder whose role decides (the ``fid`` of the path, or the folder of its presentation ``pid``) and the
        presentation id; an unknown presentation names no folder, so only the administrator's role holds there."""
        match = route.pattern.fullmatch(path)
        groups = match.groupdict() if match is not None else {}
        presentation_id = groups.get(PRESENTATION_GROUP)
        if presentation_id is None:
            return groups.get(FOLDER_GROUP), None
        presentation = self._library_server().library.presentation(presentation_id)
        return (presentation.folder_id if presentation is not None else None), presentation_id

    def _is_json(self) -> bool:
        """``Content-Type`` is ``application/json`` (parameters and case aside): what a form of another page cannot
        send without a preflight (DEC-022)."""
        try:
            check_content_type(self.headers.get("Content-Type", ""))
        except SaveRefusal:
            return False
        return True

    def _read_library_json(self) -> dict[str, Any] | Answer:
        """The body as a JSON object, or the refusal to answer: 400 for a malformed length or body, 413 above
        ``JSON_BODY_MAX_BYTES`` before a byte is read. Only called once the permission holds."""
        try:
            length = parse_content_length(self.headers.get("Content-Length"))
        except SaveRefusal as refusal:
            self.close_connection = True  # the body is not read: it must not be parsed as the next request
            return json_answer(refusal.status, {"ok": False, "error": refusal.payload["error"]})
        if length > JSON_BODY_MAX_BYTES:
            self.close_connection = True
            return json_answer(413, {"ok": False, "error": pages.REQUEST_TOO_LARGE})
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, RecursionError):  # UnicodeDecodeError is a ValueError
            data = None
        if not isinstance(data, dict):
            return json_answer(400, {"ok": False, "error": pages.INVALID_REQUEST_BODY})
        return data

    def _origin_ok(self, origin: str) -> bool:
        """DEC-022: ``Origin`` exactly the receiving origin, ``Sec-Fetch-Site`` absent, ``same-origin`` or ``none``."""
        fetch_site = self.headers.get("Sec-Fetch-Site")
        return self.headers.get("Origin") == origin and (fetch_site is None or fetch_site in FETCH_SITES_ALLOWED)

    @staticmethod
    def _refusal(path: str, *, signed_in: bool) -> Answer:
        """``Access denied.`` for a signed in person, the sign in page keeping ``path`` for a visitor."""
        if signed_in:
            return Answer(403, pages.access_denied())
        return Answer(200, pages.sign_in_page(safe_destination(path), None))

    def _send_answer(self, origin: str, answer: Answer) -> None:
        """Status, ``Location``, cookies of the origin, body; a page body carries the page policy."""
        if answer.body and answer.content_type == pages.HTML_CONTENT_TYPE:
            self.policy = PAGE_POLICY
        self.send_response(answer.status)
        if answer.location is not None:
            self.send_header("Location", answer.location)
        for cookie in answer.cookies:
            self.send_header(
                "Set-Cookie", cookie_header(origin, cookie.base, cookie.value, max_age=cookie.max_age, path=cookie.path)
            )
        if answer.body:
            self.send_header("Content-Type", answer.content_type)
        self.send_header("Content-Length", str(len(answer.body)))
        self.end_headers()
        self.wfile.write(answer.body)

    def _request_path(self, parsed_path: str) -> str:
        """The path as written in the request line: ``//host/x`` is a path here, not an authority."""
        return re.split(r"[?#]", self.path, maxsplit=1)[0] if self.path.startswith("/") else parsed_path

    def _arrived_in_plain(self, origin: str) -> bool:
        """nginx says the browser used plain http while the configured origin is https (DEC-008)."""
        forwarded = self.headers.get("X-Forwarded-Proto", "").strip().lower()
        return forwarded == PLAIN_SCHEME and urlsplit(origin).scheme == SECURE_SCHEME

    def _redirect_secure(self, origin: str, path: str, query: str) -> None:
        """308 to the same path and query on the configured origin; the request's own host is never echoed."""
        location = origin + (path if path.startswith("/") else f"/{path}") + (f"?{query}" if query else "")
        self.send_response(308)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _redirect_to_library(self) -> None:
        """A visitor on the content origin is sent to the library origin's home page (DEC-011)."""
        self.send_response(302)
        self.send_header("Location", self._library_server().settings.library_origin + "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_common_headers(self) -> None:
        """DEC-009 headers of every answer of this story (JSON or empty bodies)."""
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", self.frame_options)
        self.send_header("Content-Security-Policy", self.policy)
        if self._library_server().is_secure:
            self.send_header("Strict-Transport-Security", STRICT_TRANSPORT)

    def _library_server(self) -> LibraryServer:
        return cast(LibraryServer, self.server)


class PresentationLock:
    """A context manager holding the lock of one presentation (DEC-028) and refusing, once it holds it, when the row
    is gone: a save that lost the race with a deletion creates nothing."""

    __slots__ = ("_exists", "_lock")

    def __init__(self, lock: threading.Lock, exists: Callable[[], bool]) -> None:
        self._lock = lock
        self._exists = exists

    def __enter__(self) -> PresentationLock:
        self._lock.acquire()
        try:
            if not self._exists():
                raise SaveRefusal(403, dict(DENIED_PAYLOAD))
        except sqlite3.Error as exc:  # an unreadable library: nothing is written, the editor shows the reason
            self._lock.release()
            logger.error("Library unavailable for a save: %s", type(exc).__name__)
            raise SaveRefusal(503, {"error": pages.LIBRARY_UNAVAILABLE}) from exc
        except BaseException:
            self._lock.release()
            raise
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self._lock.release()


class LibraryServer(_EditorServer):
    """One process for every folder and presentation (DEC-002), bound to ``settings.host`` and ``settings.port``.

    ``port`` is the port actually bound (``settings.port`` 0 picks a free one). The database
    ``<library_dir>/library.db`` is created and migrated before the bind; the Google credentials file is read once
    here (a missing file or an unlisted return address is logged, the server still starts, DEC-015).
    """

    def __init__(self, settings: Settings, *, clock: Callable[[], float] = time.time) -> None:
        self.settings = settings
        self.clock = clock
        self._origins = _origins_by_host(settings)  # refused before the bind
        self.is_secure = urlsplit(settings.library_origin).scheme == SECURE_SCHEME
        self._thread: threading.Thread | None = None
        self.routes = ROUTES
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self.database = Database(settings.library_dir / DATABASE_NAME)
        self.library = Library(self.database, clock, state_dir=settings.state_dir)
        google = GoogleClient(settings.google_credentials_file, settings.library_origin + CALLBACK_PATH)
        self.accounts = Accounts(self.database, google, clock)
        super().__init__(settings.host, settings.port, LibraryHandler)
        self.port = int(self.server_address[1])

    def lock_for(self, presentation_id: str) -> threading.Lock:
        """The one lock of a presentation (created on first use): saves, replacements and deletions take it."""
        with self._locks_guard:
            return self._locks.setdefault(presentation_id, threading.Lock())

    def save_lock(self, presentation_id: str) -> PresentationLock:
        """The context manager a save (or an upload replacement, or a deletion) holds while it writes."""
        return PresentationLock(
            self.lock_for(presentation_id), lambda: self.library.presentation(presentation_id) is not None
        )

    def find_route(self, origin: str, method: str, path: str) -> Route | None:
        """The first row of the table for this origin, method and whole path, else None."""
        return next(
            (
                route
                for route in self.routes
                if route.origin == origin and route.method == method and route.pattern.fullmatch(path)
            ),
            None,
        )

    def is_content_host(self, host: str) -> bool:
        """True when ``Host`` is the netloc of the content origin."""
        return self._origins.get(host.lower()) == self.settings.library_content_origin

    def origin_for(self, host: str) -> str | None:
        """The configured origin whose netloc equals the ``Host`` header (case insensitive), else None."""
        return self._origins.get(host.lower())

    def start(self) -> None:
        """Serve on a daemon thread, like ``start_http_server``."""
        self._thread = threading.Thread(
            target=self.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_SECONDS}, daemon=True
        )
        self._thread.start()
        logger.info("Library server listening on http://%s:%d/", self.settings.host, self.port)

    def stop(self) -> None:
        """End the loop, release the port, shut idle connections (the stop sequence of ``stop_http_server``)."""
        if self._thread is not None:  # shutdown waits for a loop that never started otherwise
            self.shutdown()
            self._thread = None
        self.server_close()
        self.connections.close_idle()
        self.database.release()
        logger.info("Library server stopped")


def _origins_by_host(settings: Settings) -> dict[str, str]:
    """Lower case netloc to origin for the two origins; LibraryConfigError when they share a host name."""
    for variable, value in (
        ("HTMLEDITOR_LIBRARY_ORIGIN", settings.library_origin),
        ("HTMLEDITOR_LIBRARY_CONTENT_ORIGIN", settings.library_content_origin),
    ):
        if not is_origin(value):  # only the library fails on it: the local commands never read these two
            raise LibraryConfigError(f"{variable} must be http(s)://host[:port] without a path, got {value!r}")
    library = urlsplit(settings.library_origin)
    content = urlsplit(settings.library_content_origin)
    if library.hostname == content.hostname:
        raise LibraryConfigError(SAME_HOST_MESSAGE)
    return {
        library.netloc.lower(): settings.library_origin,
        content.netloc.lower(): settings.library_content_origin,
    }
