"""Web library server (SPEC-0025): one listener answering the library origin and the content origin.

Gate order of every request (DEC-007, DEC-008, DEC-010): a header block readable two ways is refused (400,
inherited ``_refuse_ambiguous_headers``); ``GET /health`` answers on any host name with ``running`` and the version
only; a ``Host`` other than the netloc of one of the two configured origins gets ``403 {"error": "forbidden host"}``;
``X-Forwarded-Proto: http`` gets ``308`` to the configured origin of that host; anything else is ``Not found`` until
the route table exists. Every answer carries the protection headers of DEC-009 (``end_headers``).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any, cast, override
from urllib.parse import urlsplit

from ..config import Settings, is_origin
from ..http_server import _EditorHandler, _EditorServer
from ..version import __version__

logger = logging.getLogger(__name__)

SAME_HOST_MESSAGE = "The library origin and the content origin must be two different host names."
FORBIDDEN_HOST = "forbidden host"
HEALTH_PATH = "/health"
JSON_POLICY = "default-src 'none'; frame-ancestors 'none'"
STRICT_TRANSPORT = "max-age=31536000"
POLL_INTERVAL_SECONDS = 0.05
PLAIN_SCHEME = "http"
SECURE_SCHEME = "https"


class LibraryConfigError(Exception):
    """The settings cannot run the library (the message is the user text)."""


def health_answer() -> dict[str, Any]:
    """The liveness answer: running and the version, nothing about files, process or presentations (DEC-010)."""
    return {"ok": True, "status": "ok", "version": __version__}


class LibraryHandler(_EditorHandler):
    """The library gate in front of every method; the connection bounds and ``do_OPTIONS`` are inherited."""

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

    def _dispatch(self) -> None:
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
        self._not_found()

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

    def _send_common_headers(self) -> None:
        """DEC-009 headers of every answer of this story (JSON or empty bodies)."""
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", JSON_POLICY)
        if self._library_server().is_secure:
            self.send_header("Strict-Transport-Security", STRICT_TRANSPORT)

    def _library_server(self) -> LibraryServer:
        return cast(LibraryServer, self.server)


class LibraryServer(_EditorServer):
    """One process for every folder and presentation (DEC-002), bound to ``settings.host`` and ``settings.port``.

    ``port`` is the port actually bound (``settings.port`` 0 picks a free one).
    """

    def __init__(self, settings: Settings, *, clock: Callable[[], float] = time.time) -> None:
        self.settings = settings
        self.clock = clock
        self._origins = _origins_by_host(settings)  # refused before the bind
        self.is_secure = urlsplit(settings.library_origin).scheme == SECURE_SCHEME
        self._thread: threading.Thread | None = None
        super().__init__(settings.host, settings.port, LibraryHandler)
        self.port = int(self.server_address[1])

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
