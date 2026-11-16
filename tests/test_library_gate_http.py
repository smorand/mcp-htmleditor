"""SPEC-0025 US-0124: ``webserve`` starts, accepts only its two host names, answers ``/health``.

The library tests run an in process ``LibraryServer`` (``tests/library_support.py``) and choose the ``Host`` and
``X-Forwarded-Proto`` of each request; the local mode tests run the unchanged ``serve`` server (``serve_deck``).
"""

from __future__ import annotations

import hashlib
import http.client
import inspect
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_htmleditor.config import Settings
from mcp_htmleditor.http_server import _EditorHandler, _EditorServer, health_payload
from mcp_htmleditor.library.server import LibraryConfigError, LibraryServer
from mcp_htmleditor.version import __version__
from tests import library_support
from tests.conftest import ServedDeck
from tests.deck_support import run_cli
from tests.http_support import exchange, json_body
from tests.library_support import RunningLibrary, free_port

library_server = library_support.library_server

REPO = Path(__file__).resolve().parents[1]
SERVE = Callable[[Path], ServedDeck]
START = Callable[..., RunningLibrary]

TALK_MARKER = "TALK-MARKER-0124"
TALK = (
    '<!DOCTYPE html><html data-doc-type="presentation"><head><title>talk</title></head><body>'
    f'<section data-type="slide" data-id="s1" data-title="One"><p>{TALK_MARKER}</p></section></body></html>'
)
LIBRARY_WORDS = ("Sign in", "Google", "Folders", "Access denied", "library")
SECURE_LIBRARY = "https://slides.scm-platform.org"
SECURE_CONTENT = "https://slides-content.scm-platform.org"
HEALTH = {"ok": True, "status": "ok", "version": __version__}
LOCAL_ONLY_HEALTH_KEYS = {"file", "pid", "port", "page", "started", "uptime_seconds"}
JSON_POLICY = "default-src 'none'; frame-ancestors 'none'"
COMMON_HEADERS = {
    "cache-control": "no-store, must-revalidate",
    "pragma": "no-cache",
    "x-content-type-options": "nosniff",
    "referrer-policy": "same-origin",
    "x-frame-options": "DENY",
    "content-security-policy": JSON_POLICY,
}
SAME_HOST_MESSAGE = "The library origin and the content origin must be two different host names."
# sha256 of inspect.getsource(_EditorHandler) at main (bf60b21): the library subclasses it, never edits it (DEC-003).
# A later story that adds the DEC-003 hooks updates this value in its own diff.
EDITOR_HANDLER_SOURCE_SHA256 = "361aeb9186297461e3621fd10e503d7c12c2128fcbe3dbb75adb7c551995d011"
CHILD_START_SECONDS = 30.0


@pytest.fixture
def talk(tmp_path: Path) -> Path:
    path = tmp_path / "local" / "talk.html"
    path.parent.mkdir()
    path.write_text(TALK, encoding="utf-8")
    return path


def local_get(port: int, path: str, host: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", host)
        conn.endheaders()
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def assert_no_library_text(body: bytes) -> None:
    text = body.decode("utf-8", "replace")
    for word in LIBRARY_WORDS:
        assert word not in text, f"{word!r} shown: {text[:200]!r}"


# ---------------------------------------------------------------------------
# Local mode (FR-NEW-055, FR-NEW-056)
# ---------------------------------------------------------------------------


def test_e2e_135_no_library_page_exists_in_the_local_mode(serve_deck: SERVE, talk: Path) -> None:
    """E2E-135: the library home page and a folder page give the local editor and its own answers only."""
    deck = serve_deck(talk)
    host = f"127.0.0.1:{deck.port}"
    editor_shell = (REPO / "src" / "mcp_htmleditor" / "static" / "editor.html").read_bytes()

    home_status, home_body = local_get(deck.port, "/", host)
    folder_status, folder_body = local_get(deck.port, f"/f/{'a' * 32}", host)
    content_status, content_body = local_get(deck.port, "/content", host)

    assert (home_status, home_body) == (200, editor_shell)
    assert (folder_status, json.loads(folder_body)) == (404, {"error": "Not found"})
    assert (content_status, content_body.decode("utf-8")) == (200, TALK)
    for path in ("/admin", "/auth/start", "/lib/library.css"):
        status, body = local_get(deck.port, path, host)
        assert (status, json.loads(body)) == (404, {"error": "Not found"}), path
    assert_no_library_text(folder_body)


def test_e2e_136_the_local_mode_keeps_refusing_other_host_names(serve_deck: SERVE, talk: Path) -> None:
    """E2E-136: a request through slides.scm-platform.org is refused, nothing of talk.html nor a sign in page."""
    deck = serve_deck(talk)

    for path in ("/", "/content", "/content-frame", "/download", f"/f/{'a' * 32}"):
        status, body = local_get(deck.port, path, "slides.scm-platform.org")
        assert (status, json.loads(body)) == (403, {"error": "forbidden host"}), path
        assert TALK_MARKER not in body.decode("utf-8", "replace")
        assert_no_library_text(body)


# ---------------------------------------------------------------------------
# Library gate (FR-NEW-057, FR-NEW-058, FR-NEW-059)
# ---------------------------------------------------------------------------


def test_e2e_146_the_plain_address_is_sent_to_the_secure_one(library_server: START) -> None:
    """E2E-146: ``X-Forwarded-Proto: http`` gives 308 to the configured secure origin, path and query kept, no body."""
    running = library_server(library_origin=SECURE_LIBRARY, library_content_origin=SECURE_CONTENT)
    library = running.client("slides.scm-platform.org")
    content = running.client("slides-content.scm-platform.org")

    for method in ("GET", "POST", "DELETE"):
        reply = library.request(method, "/f/abc?view=1&x=%20", headers={"X-Forwarded-Proto": "http"})
        assert reply.status == 308, method
        assert reply.headers["location"] == f"{SECURE_LIBRARY}/f/abc?view=1&x=%20"
        assert reply.body == b""
        assert reply.headers["content-length"] == "0"
        assert reply.headers["strict-transport-security"] == "max-age=31536000"
    assert library.get("/", x_forwarded_proto="http").headers["location"] == f"{SECURE_LIBRARY}/"
    assert content.get("/d/x/", x_forwarded_proto="HTTP").headers["location"] == f"{SECURE_CONTENT}/d/x/"
    assert library.get("/x", x_forwarded_proto="https").status == 404


def test_e2e_146_the_redirect_is_built_from_the_settings_never_from_the_request(library_server: START) -> None:
    """E2E-146: an absolute form target naming another host keeps the configured origin and only its path."""
    running = library_server(library_origin=SECURE_LIBRARY, library_content_origin=SECURE_CONTENT)
    request = (
        b"GET http://evil.example/steal?q=1 HTTP/1.1\r\nHost: slides.scm-platform.org\r\n"
        b"X-Forwarded-Proto: http\r\nConnection: close\r\n\r\n"
    )

    reply = exchange(running.port, request)

    assert reply.status == 308
    assert reply.headers["location"] == f"{SECURE_LIBRARY}/steal?q=1"
    assert reply.body == b""


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
def test_e2e_147_another_host_name_is_refused(
    library_server: START, method: str, caplog: pytest.LogCaptureFixture
) -> None:
    """E2E-147: evil.example, a loopback name or a wrong port get 403 ``forbidden host`` and nothing else."""
    running = library_server()
    caplog.set_level("WARNING")
    hosts = (
        "evil.example",
        f"evil.example:{running.port}",
        f"127.0.0.1:{running.port}",
        "slides.test",
        "slides.test:1",
    )

    for host in hosts:
        for proto in ({}, {"X-Forwarded-Proto": "http"}):
            reply = running.client(host).request(method, "/", headers=proto)
            assert (reply.status, reply.json()) == (403, {"error": "forbidden host"}), (host, proto)
            assert "location" not in reply.headers
            assert_no_library_text(reply.body)
    assert f"Refused {method} /: forbidden host 'evil.example'" in caplog.text
    assert running.client("evil.example").get("/health").json() == HEALTH


def test_e2e_147_a_request_without_host_is_refused(library_server: START) -> None:
    running = library_server()

    reply = exchange(running.port, b"GET / HTTP/1.0\r\n\r\n")

    assert (reply.status, json_body(reply)) == (403, {"error": "forbidden host"})


def test_the_two_configured_host_names_are_accepted_in_any_case(library_server: START) -> None:
    """The gate compares host and port case insensitively; this story answers ``Not found`` behind it."""
    running = library_server()

    for host in (running.library_netloc, running.content_netloc, running.library_netloc.upper()):
        reply = running.client(host).get("/")
        assert (reply.status, reply.json()) == (404, {"error": "Not found"}), host


# ---------------------------------------------------------------------------
# Health (FR-NEW-073)
# ---------------------------------------------------------------------------


def test_e2e_186_the_health_check_works_without_sign_in_and_shows_little(library_server: START) -> None:
    """E2E-186: ``running`` and the version only, the same through 127.0.0.1, evil.example and the two origins."""
    running = library_server()
    hosts = (f"127.0.0.1:{running.port}", "evil.example", running.library_netloc, running.content_netloc)

    replies = [running.client(host).get("/health") for host in hosts]
    no_host = exchange(running.port, b"GET /health HTTP/1.0\r\n\r\n")

    assert {reply.status for reply in replies} == {200}
    assert [reply.json() for reply in replies] == [HEALTH] * len(hosts)
    assert len({reply.body for reply in replies} | {no_host.body}) == 1
    text = replies[0].text
    for leak in (str(os.getpid()), str(running.library_dir), str(running.state_dir), str(running.port)):
        assert leak not in text
    assert running.client("evil.example").get("/health", x_forwarded_proto="http").json() == HEALTH


def test_health_differs_from_the_local_one_by_the_dropped_keys(
    serve_deck: SERVE, talk: Path, library_server: START
) -> None:
    """The library body is the local body without file, pid, port, page, started and uptime_seconds."""
    deck = serve_deck(talk)
    running = library_server()

    local_status, local_body = local_get(deck.port, "/health", f"127.0.0.1:{deck.port}")
    local = json.loads(local_body)
    library = running.client().get("/health").json()

    assert local_status == 200
    assert set(local) == set(health_payload())
    assert set(local) - set(library) == LOCAL_ONLY_HEALTH_KEYS
    assert library == {key: local[key] for key in set(local) - LOCAL_ONLY_HEALTH_KEYS}
    assert local["page"] == "talk.html"


# ---------------------------------------------------------------------------
# Response headers (FR-NEW-072, DEC-009)
# ---------------------------------------------------------------------------


def test_every_answer_carries_the_protection_headers(library_server: START) -> None:
    running = library_server()
    library = running.client()
    replies = {
        "health": library.get("/health"),
        "not found": library.get("/"),
        "forbidden host": running.client("evil.example").get("/"),
        "redirect": library.get("/x", x_forwarded_proto="http"),
        "options": library.request("OPTIONS", "/"),
        "unknown method": library.request("PATCH", "/"),
    }
    raw_duplicate_host = exchange(
        running.port, f"GET / HTTP/1.1\r\nHost: {running.library_netloc}\r\nHost: evil.example\r\n\r\n".encode()
    )

    for name, reply in replies.items():
        for header, value in COMMON_HEADERS.items():
            assert reply.headers.get(header) == value, (name, header)
        assert "strict-transport-security" not in reply.headers, name
    assert replies["options"].status == 405
    for header, value in COMMON_HEADERS.items():
        assert raw_duplicate_host.headers.get(header) == value, header


def test_https_origins_add_strict_transport_security(library_server: START) -> None:
    running = library_server(library_origin=SECURE_LIBRARY, library_content_origin=SECURE_CONTENT)

    for host in ("slides.scm-platform.org", "evil.example"):
        for path in ("/health", "/"):
            reply = running.client(host).get(path)
            assert reply.headers["strict-transport-security"] == "max-age=31536000", (host, path)


def test_ambiguous_headers_are_refused_before_the_health_answer(library_server: START) -> None:
    running = library_server()

    reply = exchange(running.port, b"GET /health HTTP/1.1\r\nHost: a\r\nHost: b\r\nConnection: close\r\n\r\n")

    assert (reply.status, json_body(reply)) == (400, {"error": "Duplicate Host header"})


# ---------------------------------------------------------------------------
# Settings, CLI and the untouched local handler (story tests)
# ---------------------------------------------------------------------------


def test_library_settings_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("HTMLEDITOR_LIBRARY_ORIGIN", "HTMLEDITOR_LIBRARY_CONTENT_ORIGIN", "HTMLEDITOR_LIBRARY_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HTMLEDITOR_STATE_DIR", str(tmp_path / "state"))

    settings = Settings()

    assert settings.library_origin == SECURE_LIBRARY
    assert settings.library_content_origin == SECURE_CONTENT
    assert settings.library_dir == tmp_path / "state" / "library"
    monkeypatch.setenv("HTMLEDITOR_LIBRARY_DIR", str(tmp_path / "lib"))
    assert Settings().library_dir == tmp_path / "lib"


@pytest.mark.parametrize(
    "value",
    [
        "not-a-url",
        "ftp://slides.test",
        "https://slides.test/path",
        "https://slides.test/",
        "https://slides.test?q=1",
        "https://slides.test#top",
        "https://user@slides.test",
        "https://slides.test:99999",
        "https://slides.test:",
        "https://slides.test:443",
        "http://slides.test:80",
        "https://slides.test.",
        "https://",
    ],
)
@pytest.mark.parametrize("variable", ["HTMLEDITOR_LIBRARY_ORIGIN", "HTMLEDITOR_LIBRARY_CONTENT_ORIGIN"])
def test_an_origin_that_is_not_scheme_host_port_fails_naming_the_variable(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(LibraryConfigError, match=variable):
        LibraryServer(Settings(host="127.0.0.1", port=0))


def test_a_malformed_origin_leaves_local_commands_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """FR-NEW-055: local mode is unchanged; webserve alone refuses, with a click error and no traceback."""
    monkeypatch.setenv("HTMLEDITOR_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HTMLEDITOR_LIBRARY_ORIGIN", "https://slides.test/path")

    stdout, _, code = run_cli("templates")
    assert code == 0
    assert "breathe" in stdout
    _, help_err, help_code = run_cli("serve", "--help")
    assert help_code == 0
    assert help_err == ""

    _, stderr, code = run_cli("webserve", "--host", "127.0.0.1", "--port", str(free_port()))
    assert code == 1
    assert "HTMLEDITOR_LIBRARY_ORIGIN must be http(s)://host[:port]" in stderr
    assert "Traceback" not in stderr


def test_an_origin_with_a_port_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTMLEDITOR_LIBRARY_ORIGIN", "http://slides.test:8080")

    assert Settings().library_origin == "http://slides.test:8080"


def test_webserve_refuses_two_origins_on_one_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HTMLEDITOR_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HTMLEDITOR_LIBRARY_ORIGIN", "https://same.example")
    monkeypatch.setenv("HTMLEDITOR_LIBRARY_CONTENT_ORIGIN", "https://SAME.example:8443")

    stdout, stderr, code = run_cli("webserve", "--host", "127.0.0.1", "--port", str(free_port()))

    assert code == 1
    assert stderr.strip().splitlines()[-1] == SAME_HOST_MESSAGE
    assert stdout == ""


def test_webserve_serves_until_sigterm(tmp_path: Path) -> None:
    """The real command: start line, health on any host, the library gate, clean stop on SIGTERM."""
    port = free_port()
    env = {
        **os.environ,
        "HTMLEDITOR_LOG_DIR": str(tmp_path / "logs"),
        "HTMLEDITOR_STATE_DIR": str(tmp_path / "state"),
        "HTMLEDITOR_LIBRARY_ORIGIN": f"http://slides.test:{port}",
        "HTMLEDITOR_LIBRARY_CONTENT_ORIGIN": f"http://slides-content.test:{port}",
    }
    command = [sys.executable, "-m", "mcp_htmleditor", "webserve", "--host", "127.0.0.1", "--port", str(port)]
    process = subprocess.Popen(  # noqa: S603  command built by the test, no shell
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=REPO, env=env
    )
    try:
        health = wait_for_health(process, port)
        refused = library_support.HttpClient(port, "evil.example").get("/")
        process.send_signal(signal.SIGTERM)
        stdout, _ = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)

    assert health == HEALTH
    assert refused.status == 403
    assert process.returncode == 0
    assert stdout.splitlines() == [
        f"Serving the library on http://127.0.0.1:{port}/ (library origin http://slides.test:{port},"
        f" content origin http://slides-content.test:{port})"
    ]


def wait_for_health(process: subprocess.Popen[str], port: int) -> object:
    deadline = time.monotonic() + CHILD_START_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _, stderr = process.communicate(timeout=10)
            pytest.fail(f"webserve exited with {process.returncode}: {stderr[-2000:]}")
        try:
            return library_support.HttpClient(port, "evil.example").get("/health").json()
        except OSError:
            time.sleep(0.05)
    pytest.fail(f"webserve did not answer on port {port} within {CHILD_START_SECONDS:g} s")


def test_the_editor_handler_is_unchanged_and_the_server_takes_the_handler_class() -> None:
    """DEC-003: the library subclasses ``_EditorHandler``; ``_EditorServer`` only gained the handler parameter."""
    source = inspect.getsource(_EditorHandler).encode("utf-8")

    assert hashlib.sha256(source).hexdigest() == EDITOR_HANDLER_SOURCE_SHA256
    parameters = inspect.signature(_EditorServer.__init__).parameters
    assert list(parameters) == ["self", "bind_host", "port", "handler"]
    assert parameters["handler"].default is _EditorHandler
