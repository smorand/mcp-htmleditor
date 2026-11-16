"""Test support for the web library mode (SPEC-0025, DEC-049).

``library_server`` starts an in process ``LibraryServer`` on a free port with a temporary ``library_dir`` and
``state_dir`` and the origins ``http://slides.test:<port>`` and ``http://slides-content.test:<port>``; overrides
replace any setting. ``HttpClient`` connects to ``127.0.0.1:<port>`` and sends the ``Host`` it is given, so one
listener is reached under any host name. ``FakeClock`` moves time by seconds.
"""

from __future__ import annotations

import http.client
import json
import socket
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor.config import Settings
from mcp_htmleditor.library.server import LibraryServer

LIBRARY_HOST = "slides.test"
CONTENT_HOST = "slides-content.test"
CLOCK_START = 1_000_000_000.0


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
    """One answer: status, headers (lower case names) and body bytes."""

    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

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
            conn.endheaders(body or None)
            response = conn.getresponse()
            data = response.read()
            return LibraryReply(
                status=response.status, headers={k.lower(): v for k, v in response.getheaders()}, body=data
            )
        finally:
            conn.close()

    def get(self, path: str, **headers: str) -> LibraryReply:
        return self.request("GET", path, headers=_header_names(headers))


@dataclass
class RunningLibrary:
    """A started library server, its settings and directories."""

    server: LibraryServer
    settings: Settings
    clock: FakeClock
    library_dir: Path
    state_dir: Path

    @property
    def port(self) -> int:
        return self.server.port

    @property
    def library_netloc(self) -> str:
        return f"{LIBRARY_HOST}:{self.port}"

    @property
    def content_netloc(self) -> str:
        return f"{CONTENT_HOST}:{self.port}"

    def client(self, host: str | None = None) -> HttpClient:
        """A client whose requests carry ``Host: host`` (default the library origin's host and port)."""
        return HttpClient(self.port, host if host is not None else self.library_netloc)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def library_server(tmp_path: Path) -> Iterator[Callable[..., RunningLibrary]]:
    """Return ``start(**settings_overrides)``; every server it started is stopped at teardown."""
    started: list[LibraryServer] = []

    def start(**settings_overrides: Any) -> RunningLibrary:
        port = free_port()
        library_dir = tmp_path / "library"
        state_dir = tmp_path / "state"
        values: dict[str, Any] = {
            "host": "127.0.0.1",
            "port": port,
            "library_origin": f"http://{LIBRARY_HOST}:{port}",
            "library_content_origin": f"http://{CONTENT_HOST}:{port}",
            "library_dir_override": library_dir,
            "state_dir_override": state_dir,
        }
        values.update(settings_overrides)
        settings = Settings(**values)
        clock = FakeClock()
        server = LibraryServer(settings, clock=clock)
        started.append(server)
        server.start()
        return RunningLibrary(
            server=server, settings=settings, clock=clock, library_dir=library_dir, state_dir=state_dir
        )

    yield start
    for server in started:
        server.stop()


def _header_names(headers: dict[str, str]) -> dict[str, str]:
    """``x_forwarded_proto`` keyword to ``X-Forwarded-Proto``."""
    return {"-".join(part.capitalize() for part in name.split("_")): value for name, value in headers.items()}
