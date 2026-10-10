"""Security tests for SPEC-0005: the preview server only answers its own origin.

Bug: no handler checked ``Origin`` or ``Host``, every response carried
``Access-Control-Allow-Origin: *`` and ``POST /content`` accepted a
``text/plain`` body, so any web page open in the user's browser could read
and overwrite the edited document, and DNS rebinding reached every route.

HTTP level tests use ``http.client`` so ``Host`` and ``Origin`` are sent
verbatim; browser tests serve an attacker page from a second server on
another port (a different origin) against a real editor server.
"""

from __future__ import annotations

import http.client
import http.server
import json
import logging
import platform
import socket
import threading
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor.http_server import start_http_server, stop_http_server

MARKER = "ORIGINAL-MARKER"
PAYLOAD = "<p>PWNED</p>"
EVIL_ORIGIN = "https://evil.example"
DOC = f'<!DOCTYPE html><html data-doc-type="document"><body><p>{MARKER}</p></body></html>'
DIAGRAM_DOC = (
    '<!DOCTYPE html><html><body><div data-type="arch-diagram"><div data-type="arch-row">'
    '<div data-type="arch-node" data-id="a">A</div><div data-type="arch-node" data-id="b">B</div>'
    "</div></div></body></html>"
)
CORS_HEADERS = ("Access-Control-Allow-Origin", "Access-Control-Allow-Methods", "Access-Control-Allow-Headers")


def _chromium_cache_dir() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library" / "Caches" / "ms-playwright"
    return home / ".cache" / "ms-playwright"


HAS_CHROMIUM = any(_chromium_cache_dir().glob("chromium-*"))
needs_chromium = pytest.mark.skipif(
    not HAS_CHROMIUM,
    reason="Playwright Chromium is not installed; run `make sync`",
)


@dataclass(frozen=True)
class Served:
    path: Path
    port: int

    @property
    def host(self) -> str:
        return f"127.0.0.1:{self.port}"


@dataclass(frozen=True)
class Reply:
    status: int
    headers: dict[str, str]
    body: str


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_listening(port: int) -> None:
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail(f"server on port {port} did not start in time")


def _serve(tmp_path: Path, content: str) -> Iterator[Served]:
    doc = tmp_path / "doc.html"
    doc.write_text(content, encoding="utf-8")
    port = _free_port()
    start_http_server(str(doc), port=port, host="127.0.0.1")
    _wait_listening(port)
    try:
        yield Served(path=doc, port=port)
    finally:
        stop_http_server()


@pytest.fixture
def served(tmp_path: Path, reset_state: None) -> Iterator[Served]:
    yield from _serve(tmp_path, DOC)


@pytest.fixture
def served_diagram(tmp_path: Path, reset_state: None) -> Iterator[Served]:
    yield from _serve(tmp_path, DIAGRAM_DOC)


@pytest.fixture
def attacker_url(tmp_path: Path) -> Iterator[str]:
    """A page on a different origin (another port), like a malicious site."""
    root = tmp_path / "attacker"
    root.mkdir()
    (root / "index.html").write_text("<html><body>attacker</body></html>", encoding="utf-8")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(root), **kwargs)  # type: ignore[arg-type]  # stdlib handler signature

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib name
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


def _request(
    served: Served,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: str | None = None,
) -> Reply:
    """Send a request with exactly the given headers (Host defaults to the server)."""
    sent = {"Host": served.host, **(headers or {})}
    conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=10)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        data = body.encode("utf-8") if body is not None else b""
        for name, value in sent.items():
            conn.putheader(name, value)
        conn.putheader("Content-Length", str(len(data)))
        conn.endheaders(data)
        response = conn.getresponse()
        return Reply(
            status=response.status,
            headers={k.lower(): v for k, v in response.getheaders()},
            body=response.read().decode("utf-8", errors="replace"),
        )
    finally:
        conn.close()


def _assert_refused(reply: Reply, error: str) -> None:
    assert reply.status == 403
    assert json.loads(reply.body) == {"error": error}


def _assert_no_cors(reply: Reply) -> None:
    for name in CORS_HEADERS:
        assert name.lower() not in reply.headers


# --- 4.1 reproduction and 4.1bis exploits ----------------------------------


@needs_chromium
def test_foreign_page_cannot_overwrite_the_document(page: Page, served: Served, attacker_url: str) -> None:
    """BT-001: reproduction of BUG-001."""
    page.goto(attacker_url)
    page.evaluate(
        f"""() => fetch("http://127.0.0.1:{served.port}/content", {{method: "POST", body: "{PAYLOAD}"}})
                 .catch(() => null)"""
    )
    page.wait_for_timeout(500)

    saved = served.path.read_text(encoding="utf-8")
    assert MARKER in saved
    assert "PWNED" not in saved


def test_cross_origin_json_save_refused(served: Served) -> None:
    """BT-002."""
    before = served.path.read_bytes()
    reply = _request(
        served,
        "POST",
        "/content",
        {"Origin": EVIL_ORIGIN, "Content-Type": "application/json"},
        json.dumps({"html": PAYLOAD}),
    )
    _assert_refused(reply, "forbidden origin")
    assert served.path.read_bytes() == before


def test_cross_origin_text_save_refused(served: Served) -> None:
    """BT-003."""
    before = served.path.read_bytes()
    reply = _request(served, "POST", "/content", {"Origin": EVIL_ORIGIN, "Content-Type": "text/plain"}, PAYLOAD)
    _assert_refused(reply, "forbidden origin")
    assert served.path.read_bytes() == before


def test_cross_origin_layout_refused(served_diagram: Served) -> None:
    """BT-004."""
    before = served_diagram.path.read_bytes()
    reply = _request(served_diagram, "POST", "/arch-layout", {"Origin": EVIL_ORIGIN}, "")
    _assert_refused(reply, "forbidden origin")
    assert served_diagram.path.read_bytes() == before
    assert "data-x" not in served_diagram.path.read_text(encoding="utf-8")


@needs_chromium
def test_foreign_page_cannot_read_the_document(page: Page, served: Served, attacker_url: str) -> None:
    """BT-005."""
    page.goto(attacker_url)
    page.evaluate(
        f"""() => fetch("http://127.0.0.1:{served.port}/content").then(r => r.text())
                 .then(t => {{ window.__result = t; }}, e => {{ window.__result = e.name; }})"""
    )
    page.wait_for_timeout(500)

    assert MARKER not in str(page.evaluate("() => window.__result"))
    _assert_refused(_request(served, "GET", "/content", {"Origin": EVIL_ORIGIN}), "forbidden origin")


@pytest.mark.parametrize("route", ["/content-frame", "/status", "/export/pptx", "/export/docx"])
def test_cross_origin_reads_refused(served: Served, route: str) -> None:
    """BT-006."""
    reply = _request(served, "GET", route, {"Origin": EVIL_ORIGIN})
    _assert_refused(reply, "forbidden origin")
    _assert_no_cors(reply)
    assert MARKER not in reply.body
    assert str(served.path) not in reply.body


@pytest.mark.parametrize(
    ("method", "route"),
    [("GET", "/"), ("GET", "/content"), ("GET", "/status"), ("POST", "/content")],
)
def test_rebinding_host_refused(served: Served, method: str, route: str) -> None:
    """BT-007."""
    before = served.path.read_bytes()
    headers = {"Host": f"attacker.example:{served.port}"}
    body = None
    if method == "POST":
        headers["Content-Type"] = "application/json"
        body = json.dumps({"html": PAYLOAD})
    reply = _request(served, method, route, headers, body)
    _assert_refused(reply, "forbidden host")
    assert str(served.path) not in reply.body
    assert served.path.read_bytes() == before


# --- 4.2 new behavior --------------------------------------------------------


def test_same_origin_requests_served(served: Served) -> None:
    """BT-010."""
    cases = [
        {"Host": served.host, "Origin": f"http://{served.host}"},
        {"Host": f"localhost:{served.port}", "Origin": f"http://localhost:{served.port}"},
        {"Host": f"LOCALHOST:{served.port}"},
    ]
    for headers in cases:
        reply = _request(served, "GET", "/content", headers)
        assert reply.status == 200, headers
        assert MARKER in reply.body


def test_mismatched_or_null_origins_refused(served: Served) -> None:
    """BT-011."""
    other_port = served.port + 1
    for origin in (f"http://localhost:{served.port}", f"http://127.0.0.1:{other_port}", "null"):
        _assert_refused(_request(served, "GET", "/content", {"Origin": origin}), "forbidden origin")


def test_host_port_is_not_checked(served: Served) -> None:
    """BT-012."""
    for host in (f"127.0.0.1:{served.port + 1}", "127.0.0.1", "localhost:7999"):
        reply = _request(served, "GET", "/content", {"Host": host})
        assert reply.status == 200, host
        assert MARKER in reply.body


def test_no_cors_headers_on_any_response(served: Served) -> None:
    """BT-013."""
    replies = [_request(served, "GET", route) for route in ("/", "/content", "/status", "/health")]
    replies.append(
        _request(served, "POST", "/content", {"Content-Type": "application/json"}, json.dumps({"html": DOC}))
    )
    for reply in replies:
        assert reply.status == 200
        _assert_no_cors(reply)


def test_health_open_to_any_origin(served: Served) -> None:
    """BT-016."""
    reply = _request(served, "GET", "/health", {"Origin": EVIL_ORIGIN, "Host": f"attacker.example:{served.port}"})
    assert reply.status == 200
    payload = json.loads(reply.body)
    assert set(payload) == {"status", "version", "file", "port"}
    assert payload["status"] == "ok"


def test_refusal_logged_without_body(served: Served, caplog: pytest.LogCaptureFixture) -> None:
    """BT-017."""
    caplog.set_level(logging.WARNING, logger="mcp_htmleditor.http_server")
    _request(served, "POST", "/content", {"Origin": EVIL_ORIGIN, "Content-Type": "text/plain"}, PAYLOAD)

    refusals = [r for r in caplog.records if r.levelno == logging.WARNING and "Refused" in r.getMessage()]
    assert len(refusals) == 1
    message = refusals[0].getMessage()
    assert "POST" in message
    assert "/content" in message
    assert EVIL_ORIGIN in message
    assert all("PWNED" not in r.getMessage() for r in caplog.records)


# --- 4.3 non regression ------------------------------------------------------


def test_healthcheck_request_still_answered(served: Served) -> None:
    """BT-022."""
    with urllib.request.urlopen(f"http://127.0.0.1:{served.port}/health", timeout=5) as response:
        assert response.status == 200
