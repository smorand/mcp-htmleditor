"""SPEC-0009 US-0048: atomic, guarded, conflict aware ``POST /content`` and ``fileio`` writers.

HTTP tests drive a real editor server with raw ``http.client`` requests (see ``ServedDeck`` in conftest);
unit tests cover the helpers the request handler delegates to (the handler itself is not measured).
"""

from __future__ import annotations

import errno
import http.client
import json
import os
import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import fileio, http_server
from mcp_htmleditor.deck import DeckError
from tests.conftest import ServedDeck
from tests.deck_support import FIXED_TIME

MAX_BODY = 52_428_800
NEW_TITLE = "Titre modifie par le navigateur"
EXPECTED_MODE = 0o640
RAW_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "bootstrap" / "slides-ei-empty.html"

Serve = Callable[[Path], ServedDeck]


def _full_document(deck: ServedDeck, title: str = NEW_TITLE) -> str:
    """The deck on disk with a marker added to its first ``<title>``, as a complete document."""
    return deck.path.read_text(encoding="utf-8").replace("<title>", f"<title>{title} ", 1)


def _folder_names(deck: ServedDeck) -> list[str]:
    return sorted(entry.name for entry in deck.path.parent.iterdir())


def _template_deck(tmp_path: Path, serve_deck: Serve) -> ServedDeck:
    folder = tmp_path / "work" / "templates" / "bootstrap"
    folder.mkdir(parents=True)
    copy = folder / "x.html"
    shutil.copyfile(RAW_TEMPLATE, copy)
    return serve_deck(copy)


def _post_raw(deck: ServedDeck, headers: dict[str, str], body: bytes = b"") -> tuple[int, bytes]:
    """POST /content with exactly these headers (no Content-Length unless given)."""
    conn = http.client.HTTPConnection("127.0.0.1", deck.port, timeout=10)
    try:
        conn.putrequest("POST", "/content", skip_accept_encoding=True)
        for name, value in headers.items():
            conn.putheader(name, value)
        conn.endheaders(body or None)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


# --- E2E: HTTP -------------------------------------------------------------


def test_e2e_001_normal_save(served_deck: ServedDeck) -> None:
    """E2E-001: 200 with the new mtime, new content on disk, nothing else in the folder."""
    first = served_deck.status()["mtime"]
    reply = served_deck.save({"html": _full_document(served_deck), "base_mtime": first})
    assert reply.status == 200
    assert reply.body["ok"] is True
    assert reply.body["mtime"] > first
    assert reply.body["mtime"] == served_deck.path.stat().st_mtime
    assert NEW_TITLE in served_deck.path.read_text(encoding="utf-8")
    assert _folder_names(served_deck) == ["deck.html"]


def test_e2e_002_save_after_reload(served_deck: ServedDeck) -> None:
    """E2E-002: after an agent write, a save carrying the reloaded mtime is accepted."""
    served_deck.path.write_text(_full_document(served_deck, "Agent"), encoding="utf-8")
    os.utime(served_deck.path, (FIXED_TIME + 100, FIXED_TIME + 100))
    reloaded = served_deck.status()["mtime"]
    assert reloaded == FIXED_TIME + 100
    reply = served_deck.save({"html": _full_document(served_deck), "base_mtime": reloaded})
    assert reply.status == 200
    assert reply.body["ok"] is True
    assert reply.body["mtime"] > reloaded


def test_e2e_007_conflict_refused(served_deck: ServedDeck) -> None:
    """E2E-007: a stale base_mtime is answered 409 with the current mtime and the file is untouched."""
    loaded = served_deck.status()["mtime"]
    served_deck.path.write_text(_full_document(served_deck, "Agent"), encoding="utf-8")
    os.utime(served_deck.path, (FIXED_TIME + 50, FIXED_TIME + 50))
    saved_copy = served_deck.path.read_bytes()
    reply = served_deck.save({"html": _full_document(served_deck), "base_mtime": loaded})
    assert reply.status == 409
    assert reply.body == {"ok": False, "error": "File changed on disk", "mtime": FIXED_TIME + 50}
    assert served_deck.path.read_bytes() == saved_copy


def test_conflict_is_skipped_with_force_true(served_deck: ServedDeck) -> None:
    """``force`` equal to true skips the check."""
    reply = served_deck.save({"html": _full_document(served_deck), "base_mtime": 1.0, "force": True})
    assert reply.status == 200
    assert NEW_TITLE in served_deck.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("force", [1, "true", "yes", [True], None, False])
def test_conflict_ignores_force_other_than_true(served_deck: ServedDeck, force: Any) -> None:
    """Only the JSON value true counts as force."""
    before = served_deck.path.read_bytes()
    reply = served_deck.save({"html": _full_document(served_deck), "base_mtime": 1.0, "force": force})
    assert reply.status == 409
    assert served_deck.path.read_bytes() == before


def test_save_without_base_mtime_is_not_checked(served_deck: ServedDeck) -> None:
    """No base_mtime: no conflict check."""
    assert served_deck.save({"html": _full_document(served_deck)}).status == 200


@pytest.mark.parametrize("base", [True, False, "123", None, [1], {"a": 1}])
def test_non_number_base_mtime_is_treated_as_absent(served_deck: ServedDeck, base: Any) -> None:
    """Decision: a base_mtime that is not a JSON number (a bool included) is ignored, the save proceeds."""
    reply = served_deck.save({"html": _full_document(served_deck), "base_mtime": base})
    assert reply.status == 200
    assert reply.body["ok"] is True


def test_identical_bytes_answer_ok_with_unchanged_mtime(served_deck: ServedDeck) -> None:
    """Saving the bytes already on disk touches nothing and answers the unchanged mtime."""
    small = "<html><head></head><body><p>x</p></body></html>"
    assert served_deck.save({"html": small}).status == 200
    on_disk = served_deck.path.read_text(encoding="utf-8")
    os.utime(served_deck.path, (FIXED_TIME, FIXED_TIME))
    again = served_deck.save({"html": on_disk, "base_mtime": FIXED_TIME})
    assert again.status == 200
    assert again.body == {"ok": True, "mtime": FIXED_TIME}
    assert served_deck.path.stat().st_mtime == FIXED_TIME
    assert _folder_names(served_deck) == ["deck.html"]


def test_e2e_010_template_refused(tmp_path: Path, serve_deck: Serve) -> None:
    """E2E-010: a template path is answered 403 with its absolute path, the file unchanged."""
    deck = _template_deck(tmp_path, serve_deck)
    before = deck.path.read_bytes()
    reply = deck.save({"html": "<html><body>x</body></html>"})
    assert reply.status == 403
    assert reply.body == {"ok": False, "error": f"Refusing to modify a template: {deck.status()['filename']}"}
    assert reply.body["error"].endswith(str(deck.path.resolve()))
    assert deck.path.read_bytes() == before


def test_e2e_011_too_large(served_deck: ServedDeck) -> None:
    """E2E-011: 52 428 801 declared is 413 without reading the body; 52 428 800 sent is accepted."""
    before = served_deck.path.read_bytes()
    refused = served_deck.request("POST", "/content", content_length=str(MAX_BODY + 1), send_body=False)
    assert refused.status == 413
    assert refused.body == {"error": "Request too large"}
    assert served_deck.path.read_bytes() == before

    # Valid JSON padded with trailing whitespace: fast to parse, exactly at the cap.
    prefix = json.dumps({"html": _full_document(served_deck)}).encode("utf-8")[:-1]
    body = prefix + b" " * (MAX_BODY - len(prefix) - 1) + b"}"
    assert len(body) == MAX_BODY
    accepted = served_deck.request("POST", "/content", body)
    assert accepted.status == 200
    assert NEW_TITLE in served_deck.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("declared", ["abc", "-5", "", "+5", "1.5", "0x10"])
def test_e2e_012_invalid_length(served_deck: ServedDeck, declared: str) -> None:
    """E2E-012: a Content-Length that is not ASCII digits is answered 400, the file unchanged."""
    before = served_deck.path.read_bytes()
    reply = served_deck.request("POST", "/content", content_length=declared, send_body=False)
    assert reply.status == 400
    assert reply.body == {"error": "Invalid Content-Length"}
    assert served_deck.path.read_bytes() == before


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_e2e_013_read_only_folder(served_deck: ServedDeck) -> None:
    """E2E-013: a folder that refuses new files gives 500 with an error text; file and folder unchanged."""
    saved_copy = served_deck.path.read_bytes()
    folder = served_deck.path.parent
    folder.chmod(0o555)
    try:
        reply = served_deck.save({"html": _full_document(served_deck)})
    finally:
        folder.chmod(0o755)
    assert reply.status == 500
    assert isinstance(reply.body["error"], str)
    assert reply.body["error"]
    assert "Cannot write" not in reply.body["error"]
    assert served_deck.path.read_bytes() == saved_copy
    assert _folder_names(served_deck) == ["deck.html"]


def test_e2e_014_failure_at_the_last_step(served_deck: ServedDeck, monkeypatch: pytest.MonkeyPatch) -> None:
    """E2E-014: a failing final replace answers 500 with the system message, leaves no temp file."""

    def raiser(source: str, destination: str) -> None:
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(fileio, "replace_file", raiser)
    saved_copy = served_deck.path.read_bytes()
    reply = served_deck.save({"html": _full_document(served_deck)})
    assert reply.status == 500
    assert reply.body == {"error": "Input/output error"}
    assert served_deck.path.read_bytes() == saved_copy
    assert _folder_names(served_deck) == ["deck.html"]


def test_e2e_029_template_with_an_oversize_body(tmp_path: Path, serve_deck: Serve) -> None:
    """E2E-029: the length is checked before the template: 413."""
    deck = _template_deck(tmp_path, serve_deck)
    reply = deck.request("POST", "/content", content_length=str(MAX_BODY + 1), send_body=False)
    assert reply.status == 413
    assert reply.body == {"error": "Request too large"}


def test_e2e_030_template_with_a_stale_base(tmp_path: Path, serve_deck: Serve) -> None:
    """E2E-030: a template with a stale base_mtime is 403, not 409."""
    deck = _template_deck(tmp_path, serve_deck)
    before = deck.path.read_bytes()
    reply = deck.save({"html": "<html><body>x</body></html>", "base_mtime": 1.0})
    assert reply.status == 403
    assert reply.body["error"].startswith("Refusing to modify a template: ")
    assert deck.path.read_bytes() == before


def test_invalid_json_on_a_template_is_400(tmp_path: Path, serve_deck: Serve) -> None:
    """Order: the JSON body is checked before the template."""
    deck = _template_deck(tmp_path, serve_deck)
    reply = deck.request("POST", "/content", b"not json")
    assert reply.status == 400
    assert reply.body == {"error": "Invalid JSON body"}


@pytest.mark.parametrize("body", [b"not json", b"[]", b'"x"', b"null", b"{}", b'{"html": 5}', b'{"html": null}'])
def test_invalid_json_bodies_are_400(served_deck: ServedDeck, body: bytes) -> None:
    """DEC-024: not a JSON object, or html missing or not a string: 400 Invalid JSON body."""
    before = served_deck.path.read_bytes()
    reply = served_deck.request("POST", "/content", body)
    assert reply.status == 400
    assert reply.body == {"error": "Invalid JSON body"}
    assert served_deck.path.read_bytes() == before


def test_missing_content_length_is_length_zero(served_deck: ServedDeck) -> None:
    """A save with no Content-Length header reads no body and is an invalid JSON body (400)."""
    status, raw = _post_raw(served_deck, {"Content-Type": "application/json"})
    assert status == 400
    assert json.loads(raw) == {"error": "Invalid JSON body"}


def test_length_is_checked_before_the_content_type(served_deck: ServedDeck) -> None:
    """Order: a bad length is 400 even with a foreign content type; a good length then gives 415."""
    bad, _ = _post_raw(served_deck, {"Content-Type": "text/plain", "Content-Length": "abc"})
    assert bad == 400
    good, raw = _post_raw(served_deck, {"Content-Type": "text/plain", "Content-Length": "2"}, b"{}")
    assert good == 415
    assert json.loads(raw) == {"error": "unsupported content type"}


def test_length_checks_apply_to_the_save_endpoint_only(served_deck: ServedDeck) -> None:
    """The arch-layout endpoint validates its own length (US-0072) and ignores the body and its content type."""
    assert served_deck.request("POST", "/arch-layout", b"{}").status == 200


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_read_only_deck_in_a_writable_folder_is_replaced_and_keeps_its_mode(served_deck: ServedDeck) -> None:
    """A 0o444 file in a writable folder is replaced and stays 0o444."""
    served_deck.path.chmod(0o444)
    reply = served_deck.save({"html": _full_document(served_deck)})
    assert reply.status == 200
    assert NEW_TITLE in served_deck.path.read_text(encoding="utf-8")
    assert stat.S_IMODE(served_deck.path.stat().st_mode) == 0o444
    assert _folder_names(served_deck) == ["deck.html"]


def test_browser_save_keeps_the_file_mode(served_deck: ServedDeck) -> None:
    """The permission bits of the replaced file are preserved by a browser save."""
    served_deck.path.chmod(EXPECTED_MODE)
    assert served_deck.save({"html": _full_document(served_deck)}).status == 200
    assert stat.S_IMODE(served_deck.path.stat().st_mode) == EXPECTED_MODE


def test_vanished_file_reads_mtime_zero_for_the_conflict(served_deck: ServedDeck) -> None:
    """A file deleted after load has mtime 0.0: another base_mtime is a conflict; 0.0 saves."""
    served_deck.path.unlink()
    stale = served_deck.save({"html": "<html><body>x</body></html>", "base_mtime": 5.0})
    assert stale.status == 409
    assert stale.body == {"ok": False, "error": "File changed on disk", "mtime": 0.0}
    fresh = served_deck.save({"html": "<html><body>x</body></html>", "base_mtime": 0.0})
    assert fresh.status == 200


# --- unit: parse_content_length --------------------------------------------


def test_parse_content_length_none_is_zero() -> None:
    assert http_server.parse_content_length(None) == 0


@pytest.mark.parametrize("raw", ["", "abc", "-5", "+5", " 5", "5 ", "\u0661\u0662\u0663", "\u00b2", "1_0", "1.0"])
def test_parse_content_length_invalid(raw: str) -> None:
    with pytest.raises(http_server.SaveRefusal) as info:
        http_server.parse_content_length(raw)
    assert info.value.status == 400
    assert info.value.payload == {"error": "Invalid Content-Length"}


@pytest.mark.parametrize(
    ("raw", "expected"), [("0", 0), ("7", 7), ("007", 7), ("52428800", MAX_BODY), ("0000052428800", MAX_BODY)]
)
def test_parse_content_length_valid(raw: str, expected: int) -> None:
    assert http_server.parse_content_length(raw) == expected


@pytest.mark.parametrize("raw", ["52428801", "99999999999", "9" * 5000, "1" + "0" * 4300])
def test_parse_content_length_too_large(raw: str) -> None:
    """Above the cap: 413; a very long digit string is refused without being converted to int."""
    with pytest.raises(http_server.SaveRefusal) as info:
        http_server.parse_content_length(raw)
    assert info.value.status == 413
    assert info.value.payload == {"error": "Request too large"}


# --- unit: save pipeline helpers -------------------------------------------


def test_save_refusal_carries_status_and_payload() -> None:
    refusal = http_server.SaveRefusal(418, {"error": "teapot"})
    assert (refusal.status, refusal.payload) == (418, {"error": "teapot"})


def test_parse_save_body_reads_html_base_and_force() -> None:
    request = http_server.parse_save_body(b'{"html": "<p>x</p>", "base_mtime": 12, "force": true}')
    assert (request.html, request.base_mtime, request.force) == ("<p>x</p>", 12.0, True)


@pytest.mark.parametrize("fragment", ['"base_mtime": true', '"base_mtime": "1"', '"base_mtime": null', '"force": 1'])
def test_parse_save_body_ignores_what_is_not_a_number_or_true(fragment: str) -> None:
    request = http_server.parse_save_body(('{"html": "x", ' + fragment + "}").encode("utf-8"))
    assert request.base_mtime is None
    assert request.force is False


@pytest.mark.parametrize("body", [b"", b"nope", b"[1]", b'{"html": 1}', b'{"x": 1}', b"\xff\xfe"])
def test_parse_save_body_refuses_what_is_not_an_object_with_a_string_html(body: bytes) -> None:
    with pytest.raises(http_server.SaveRefusal) as info:
        http_server.parse_save_body(body)
    assert (info.value.status, info.value.payload) == (400, {"error": "Invalid JSON body"})


@pytest.mark.parametrize("value", ["application/json", "Application/JSON; charset=utf-8", " application/json "])
def test_check_content_type_accepts_json(value: str) -> None:
    http_server.check_content_type(value)


@pytest.mark.parametrize("value", ["", "text/plain", "application/x-www-form-urlencoded", "application/jsonp"])
def test_check_content_type_refuses_the_rest(value: str) -> None:
    with pytest.raises(http_server.SaveRefusal) as info:
        http_server.check_content_type(value)
    assert (info.value.status, info.value.payload) == (415, {"error": "unsupported content type"})


def test_refuse_template_names_the_path() -> None:
    with pytest.raises(http_server.SaveRefusal) as info:
        http_server.refuse_template("/a/templates/reference/x.html")
    assert info.value.status == 403
    assert info.value.payload == {"ok": False, "error": "Refusing to modify a template: /a/templates/reference/x.html"}
    http_server.refuse_template("/a/templates-copy/x.html")


def test_check_conflict_rules(tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    target.write_text("x", encoding="utf-8")
    os.utime(target, (100.0, 100.0))
    http_server.check_conflict(target, None, False)
    http_server.check_conflict(target, 100.0, False)
    http_server.check_conflict(target, 1.0, True)
    with pytest.raises(http_server.SaveRefusal) as info:
        http_server.check_conflict(target, 99.5, False)
    assert info.value.status == 409
    assert info.value.payload == {"ok": False, "error": "File changed on disk", "mtime": 100.0}
    target.unlink()
    http_server.check_conflict(target, 0.0, False)
    with pytest.raises(http_server.SaveRefusal) as missing:
        http_server.check_conflict(target, 3.0, False)
    assert missing.value.payload["mtime"] == 0.0


# --- unit: fileio ----------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/x/templates/bootstrap/a.html", True),
        ("/x/templates/reference/slides/a.html", True),
        ("C:\\x\\templates\\bootstrap\\a.html", True),
        ("C:\\x\\templates\\reference\\a.html", True),
        ("/x/templates/other/a.html", False),
        ("/x/templates/bootstrap", False),
        ("/x/mytemplates/bootstrap/a.html", False),
        ("/x/deck.html", False),
    ],
)
def test_is_template_path(path: str, expected: bool) -> None:
    assert fileio.is_template_path(path) is expected


def test_atomic_write_returns_true_and_accepts_str(tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    target.write_bytes(b"old")
    assert fileio.atomic_write(target, "nouveau \u00e9t\u00e9") is True
    assert target.read_bytes() == "nouveau \u00e9t\u00e9".encode()
    assert fileio.atomic_write(tmp_path / "new.html", b"x") is True


def test_atomic_write_equal_bytes_touches_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "f.html"
    target.write_bytes(b"same")
    os.utime(target, (100.0, 100.0))
    calls: list[str] = []
    monkeypatch.setattr(fileio, "replace_file", lambda source, destination: calls.append(source))
    assert fileio.atomic_write(target, "same") is False
    assert calls == []
    assert target.stat().st_mtime == 100.0
    assert [p.name for p in tmp_path.iterdir()] == ["f.html"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_atomic_write_replaces_a_read_only_file_and_keeps_its_mode(tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    target.write_bytes(b"old")
    target.chmod(0o444)
    assert fileio.atomic_write(target, b"new") is True
    assert target.read_bytes() == b"new"
    assert stat.S_IMODE(target.stat().st_mode) == 0o444
    assert [p.name for p in tmp_path.iterdir()] == ["f.html"]


def test_atomic_write_removes_the_temp_file_when_the_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "f.html"
    target.write_bytes(b"old")

    def raiser(source: str, destination: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(fileio, "replace_file", raiser)
    with pytest.raises(DeckError, match=r"^Cannot write .*f\.html: No space left on device$") as info:
        fileio.atomic_write(target, b"new")
    assert isinstance(info.value, fileio.WriteError)
    assert info.value.reason == "No space left on device"
    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["f.html"]


def test_replace_file_moves_a_file(tmp_path: Path) -> None:
    source = tmp_path / "a"
    source.write_bytes(b"1")
    fileio.replace_file(str(source), str(tmp_path / "b"))
    assert (tmp_path / "b").read_bytes() == b"1"
    assert not source.exists()


def test_layout_file_writes_through_atomic_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """DEC-018: the arch layout write goes through atomic_write, with no snapshot."""
    from mcp_htmleditor import arch_layout

    target = tmp_path / "d.html"
    target.write_text(
        '<html><body><div data-type="arch-diagram"><div data-type="arch-row" data-row="0">'
        '<div data-type="arch-node" data-id="a" data-label="A"></div>'
        '<div data-type="arch-node" data-id="b" data-label="B"></div></div></div></body></html>',
        encoding="utf-8",
    )
    written: list[Path] = []
    real = fileio.atomic_write

    def spy(path: str | Path, data: bytes | str) -> bool:
        written.append(Path(path))
        return real(path, data)

    monkeypatch.setattr(arch_layout, "atomic_write", spy)
    report = arch_layout.layout_file(target)
    assert report.diagrams_updated == 1
    assert written == [target]
    assert [p.name for p in tmp_path.iterdir()] == ["d.html"]
