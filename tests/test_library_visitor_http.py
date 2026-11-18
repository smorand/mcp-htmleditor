"""US-0125: a visitor with no session sees only the sign in page (SPEC-0025 E2E-004, E2E-134, E2E-145)."""

from __future__ import annotations

import http.client
import importlib
import pkgutil
import re
import socket
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_htmleditor import library
from mcp_htmleditor.library import pages
from mcp_htmleditor.library.access import Permission, Role, authorize
from mcp_htmleditor.library.server import JSON_POLICY, PAGE_POLICY, LibraryHandler, load_routes, safe_destination
from tests import library_support
from tests.conftest import ServedDeck
from tests.library_support import RunningLibrary

library_server = library_support.library_server
START = Callable[..., RunningLibrary]

ADDRESSES = ("/", "/f/x", "/open/x", "/admin", "/static/editor.js", "/lib/anything", "/api/folders")
PRIVATE_WORDS = ("Cardiology 2027", "Heart Failure Update", "talk.html", "folder", "presentation", "member", "slide-")


def test_library_visitor_every_address_gives_exactly_the_sign_in_page(library_server: START) -> None:
    """E2E-004: the body equals ``pages.sign_in_page`` for that path, with the one action and no private word."""
    running = library_server()
    client = running.client()

    for path in ADDRESSES:
        reply = client.get(path)
        assert reply.status == 200, path
        assert reply.body == pages.sign_in_page(path, None), path
        assert reply.headers["content-type"] == "text/html; charset=utf-8"
        assert reply.text.count("Sign in with Google") == 1
        assert reply.text.count("<a ") == 1
        assert f'href="/auth/start?next={path}"' in reply.text
        visible = re.sub(r'href="[^"]*"', "", reply.text).lower()  # the link keeps the address the visitor typed
        assert not any(word.lower() in visible for word in PRIVATE_WORDS), path


def test_library_visitor_direct_links_to_a_folder_and_a_presentation_show_nothing(library_server: START) -> None:
    """E2E-004: a library holding "Cardiology 2027" and "Heart Failure Update" leaks neither name to a visitor."""
    running = library_server()
    folder = running.library_dir / "Cardiology 2027"
    folder.mkdir(parents=True)
    (folder / "Heart Failure Update.html").write_text("<html>Heart Failure Update</html>", encoding="utf-8")

    for path in ("/", f"/f/{'a' * 32}", f"/open/{'b' * 32}"):
        reply = running.client().get(path)
        assert reply.status == 200
        assert "Cardiology" not in reply.text and "Heart Failure" not in reply.text, path
        assert reply.text.count("Sign in with Google") == 1


def test_library_visitor_other_methods_and_odd_paths_give_the_page(library_server: START) -> None:
    """Every method and an address naming no page give the sign in page; a hostile ``next`` becomes ``/``."""
    running = library_server()
    client = running.client()

    for method in ("POST", "DELETE"):
        reply = client.request(method, "/f/x", headers={"Origin": running.origin}, body=b'{"a": 1}')
        assert (reply.status, reply.body) == (200, pages.sign_in_page("/f/x", None)), method
    for headers in ({}, {"Origin": "http://evil.example"}):  # DEC-022 comes before the route: no page, no route lookup
        reply = client.request("POST", "/no/such/path", headers=headers, body=b"{}")
        assert (reply.status, reply.body) == (403, pages.access_denied()), headers
    reply = client.get("/%3Cscript%3E")
    assert reply.body == pages.sign_in_page("/%3Cscript%3E", None)
    assert client.get("/a:b").body == pages.sign_in_page("/", None)


def test_library_visitor_the_content_origin_redirects_to_the_library(library_server: START) -> None:
    """DEC-011: every path of the content origin gives ``302`` to the library origin, with no body."""
    running = library_server()
    content = running.client(running.content_netloc)

    for path in ("/", "/d/x/", "/deck/frame"):
        reply = content.get(path)
        assert reply.status == 302, path
        assert reply.headers["location"] == f"{running.settings.library_origin}/"
        assert reply.body == b""
    request = f"POST /d/x HTTP/1.1\r\nHost: {running.content_netloc}\r\nContent-Length: 2\r\n\r\n{{}}".encode()
    with socket.create_connection(("127.0.0.1", running.port), timeout=10) as sock:
        sock.sendall(request)
        raw = b""
        while chunk := sock.recv(65536):  # the server closes the connection after the answer
            raw += chunk
    assert raw.startswith(b"HTTP/1.0 302")
    assert f"Location: {running.settings.library_origin}/".encode() in raw


def test_library_visitor_the_page_cannot_be_framed_and_is_never_cached(library_server: START) -> None:
    """FR-NEW-072 (partial) and DEC-009: the page policy and every protection header."""
    reply = library_server().client().get("/")

    assert reply.headers["content-security-policy"] == PAGE_POLICY
    assert "frame-ancestors 'none'" in PAGE_POLICY
    assert reply.headers["x-frame-options"] == "DENY"
    assert reply.headers["cache-control"] == "no-store, must-revalidate"
    assert reply.headers["pragma"] == "no-cache"
    assert reply.headers["x-content-type-options"] == "nosniff"
    assert reply.headers["referrer-policy"] == "same-origin"
    assert "set-cookie" not in reply.headers


def test_library_visitor_health_stays_public(library_server: START) -> None:
    """FR-NEW-073: the liveness answer is not the sign in page."""
    reply = library_server().client().get("/health")

    assert reply.status == 200
    assert reply.json()["status"] == "ok"


def test_library_visitor_e2e_145_the_secure_address_shows_the_english_page(library_server: START) -> None:
    """E2E-145: behind nginx (``X-Forwarded-Proto: https``, configured Host) the page answers, no redirect."""
    origin = "https://slides.scm-platform.org"
    running = library_server(library_origin=origin, library_content_origin="https://slides-content.scm-platform.org")

    reply = running.client("slides.scm-platform.org").get("/", x_forwarded_proto="https")

    assert reply.status == 200
    assert reply.body == pages.sign_in_page("/", None)
    assert reply.headers["strict-transport-security"] == "max-age=31536000"
    assert reply.text.count("Sign in with Google") == 1
    assert re.search(r"[^\x00-\x7f]", reply.text) is None


def _snapshot(folder: Path) -> dict[str, tuple[int, bytes]]:
    return {
        str(p.relative_to(folder)): (p.stat().st_size, p.read_bytes()) for p in sorted(folder.rglob("*")) if p.is_file()
    }


def test_library_visitor_e2e_134_talk_html_in_the_local_mode_is_invisible_to_the_library(
    library_server: START, served_deck: ServedDeck, tmp_path: Path
) -> None:
    """E2E-134: a deck edited in the local mode still answers there; the library shows only the sign in page."""
    running = library_server()
    (running.library_dir / "Cardiology 2027").mkdir(parents=True)
    (running.library_dir / "Cardiology 2027" / "keep.html").write_text("<html>keep</html>", encoding="utf-8")
    before = _snapshot(running.library_dir)
    assert before

    served_deck.path.write_text(served_deck.path.read_text(encoding="utf-8") + "<!-- edited -->", encoding="utf-8")
    local = http.client.HTTPConnection("127.0.0.1", served_deck.port, timeout=10)
    try:
        local.request("GET", "/")
        local_reply = local.getresponse()
        local_body = local_reply.read()
    finally:
        local.close()
    reply = running.client().get("/")

    assert local_reply.status == 200 and b"Sign in with Google" not in local_body
    assert reply.status == 200 and reply.body == pages.sign_in_page("/", None)
    assert b"deck.html" not in reply.body and b"Cardiology" not in reply.body
    assert _snapshot(running.library_dir) == before


def test_library_visitor_a_keep_alive_connection_carries_each_answers_own_policy(
    library_server: START, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One connection: the page policy of ``GET /`` does not leak onto the ``GET /health`` that follows."""
    monkeypatch.setattr(LibraryHandler, "protocol_version", "HTTP/1.1")  # the stdlib default closes every answer
    running = library_server()
    conn = http.client.HTTPConnection("127.0.0.1", running.port, timeout=10)
    try:
        conn.request("GET", "/", headers={"Host": running.library_netloc})
        first = conn.getresponse()
        first.read()
        conn.request("GET", "/health", headers={"Host": running.library_netloc})
        second = conn.getresponse()
        second.read()
    finally:
        conn.close()

    assert first.getheader("Content-Security-Policy") == PAGE_POLICY
    assert second.getheader("Content-Security-Policy") == JSON_POLICY


def test_library_visitor_esc_escapes_markup() -> None:
    assert pages.esc("<script>alert('x')</script>") == "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;"
    assert b"<script>" not in pages.sign_in_page('/"><script>', "<script>")
    assert b'<p role="alert">&lt;script&gt;</p>' in pages.sign_in_page("/", "<script>")


def test_library_visitor_access_denied_page_is_the_text_and_the_sign_out_form() -> None:
    text = pages.access_denied().decode()

    assert "<p>Access denied.</p>" in text
    assert 'action="/auth/logout"' in text and "Sign out" in text
    assert text.count("<form") == 1


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (None, {Permission.PUBLIC, Permission.SIGNED_IN}),
        (Role.RO, {Permission.PUBLIC, Permission.SIGNED_IN, Permission.VIEW}),
        (Role.RW, {Permission.PUBLIC, Permission.SIGNED_IN, Permission.VIEW, Permission.EDIT}),
        (Role.ADMIN, set(Permission)),
    ],
)
def test_library_visitor_authorize_permissions(role: Role | None, allowed: set[Permission]) -> None:
    assert {permission for permission in Permission if authorize(role, permission)} == allowed


def test_library_visitor_every_route_has_a_permission() -> None:
    """DEC-021: each ``routes_*`` module exports ``ROUTES`` and each row carries a ``Permission``."""
    for info in pkgutil.iter_modules(library.__path__):
        if info.name.startswith("routes_"):
            module = importlib.import_module(f"mcp_htmleditor.library.{info.name}")
            assert isinstance(module.ROUTES, tuple), info.name
    assert all(isinstance(route.permission, Permission) for route in load_routes())


def test_library_visitor_safe_destination_rules() -> None:
    assert safe_destination("/f/a%20b") == "/f/a%20b"
    for hostile in ("", "x", "//e.test", "/\\e.test", "/a\\b", "/a:b", "/a\nb", "/a?x=1", "http://e.test"):
        assert safe_destination(hostile) == "/", hostile


def test_library_visitor_a_double_slash_target_is_a_path_not_an_authority(library_server: START) -> None:
    """``GET //evil.test/x`` (the stdlib keeps one slash) gives a local ``next``, never ``//evil.test/x``."""
    running = library_server()
    request = f"GET //evil.test/x HTTP/1.0\r\nHost: {running.library_netloc}\r\n\r\n".encode()
    with socket.create_connection(("127.0.0.1", running.port), timeout=10) as sock:
        sock.sendall(request)
        chunks = []
        while chunk := sock.recv(65536):
            chunks.append(chunk)

    assert chunks[0].startswith(b"HTTP/1.0 200")
    assert b"".join(chunks).endswith(pages.sign_in_page("/evil.test/x", None))
