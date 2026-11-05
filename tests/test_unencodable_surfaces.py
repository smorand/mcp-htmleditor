"""Exploit tests for SPEC-0013 US-0077 (BUG-004 and E36, BR-018, BR-019, BR-021).

The record tools and commands, ``render``, the server tools and ``serve`` / ``arch-layout`` took a path the file
name encoder cannot hold (a JSON ``"\\ud800"`` or an undecodable command line byte), and ``serve --host`` took an
address the socket layer cannot encode (``TypeError: encoding of hostname failed`` and a traceback). Every
surface now answers one line, starts no server, changes nothing, and the span of a refused call is still written.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import config
from tests import render_support as rs
from tests.deck_support import BOOTSTRAP, call_tool, run_cli
from tests.trace_support import run_traced_tool

REPO = Path(__file__).resolve().parents[1]
FILE_REFUSED = "File name cannot be encoded"
HOST_REFUSED = "Bind address cannot be encoded"
PORTS = range(7840, 7850)
ESCAPE = "\\ud800"
TIMEOUT = 10


@pytest.fixture
def deck(tmp_path: Path) -> Path:
    path = tmp_path / "deck.html"
    shutil.copy(BOOTSTRAP / "slides-empty.html", path)
    return path


def listening_ports() -> set[int]:
    found = set()
    for port in PORTS:
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                found.add(port)
    return found


@pytest.fixture
def ports_before() -> Iterator[set[int]]:
    yield listening_ports()


def tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def run_bytes(
    tmp_path: Path, *argv: bytes, extra: dict[str, bytes] | None = None
) -> subprocess.CompletedProcess[bytes]:
    env: dict[Any, Any] = {key: value for key, value in os.environ.items() if not key.startswith("HTMLEDITOR_")}
    env.update(
        PYTHONPATH=str(REPO / "src"),
        HTMLEDITOR_STATE_DIR=str(tmp_path / "state"),
        HTMLEDITOR_LOG_DIR=str(tmp_path / "logs"),
        HTMLEDITOR_CACHE_DIR=str(tmp_path / "cache"),
    )
    for key, value in (extra or {}).items():
        env[os.fsencode(key)] = value
    command = [sys.executable, "-m", "mcp_htmleditor", *argv]
    return subprocess.run(command, env=env, capture_output=True, timeout=TIMEOUT, cwd=REPO, check=False)  # type: ignore[call-overload]  # noqa: S603


def written(tmp_path: Path) -> list[str]:
    return [p for p in tree(tmp_path) if p.split("/")[0] not in {"cache", "logs", "state"}]


# --- BT-037: every path argument refuses an unencodable name -------------------------------------------------


def tool_cases(tmp_path: Path, deck: Path) -> list[tuple[str, dict[str, Any]]]:
    bad = f"{tmp_path}/x\ud800.html"
    return [
        ("export", {"file": str(deck), "format": "pptx", "output": f"{tmp_path}/o\ud800.pptx"}),
        ("new_file", {"template": "carbon", "file": f"{tmp_path}/n\ud800.html"}),
        ("patch", {"file": bad, "ops": []}),
        ("get_slide", {"file": bad, "id": "slide-0"}),
        ("write_review", {"file": bad, "suggestions": []}),
        ("complete_request", {"file": bad, "id": "R-0001", "status": "skipped"}),
        ("render", {"file": bad}),
        ("list_requests", {"file": bad}),
        ("open_file", {"file": bad}),
        ("layout_arch_diagram", {"file": bad}),
        ("start_server", {"file": bad}),
    ]


TOOL_NAMES = [name for name, _ in tool_cases(Path("/t"), Path("/t/deck.html"))]
SPAN_TOOLS = [
    "write_review",
    "complete_request",
    "render",
    "list_requests",
    "open_file",
    "layout_arch_diagram",
    "start_server",
]


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_bt037_tools_refuse_an_unencodable_name(tmp_path: Path, deck: Path, name: str, ports_before: set[int]) -> None:
    arguments = dict(tool_cases(tmp_path, deck))[name]
    folder, deck_bytes, state = tree(tmp_path), deck.read_bytes(), tree(config.state_dir())
    assert call_tool(name, **arguments) == (False, FILE_REFUSED)
    assert tree(tmp_path) == folder
    assert deck.read_bytes() == deck_bytes
    assert tree(config.state_dir()) == state
    assert listening_ports() == ports_before


@pytest.mark.parametrize("name", SPAN_TOOLS)
def test_bt037_the_span_of_a_refused_call_is_kept(tmp_path: Path, deck: Path, name: str) -> None:
    arguments = dict(tool_cases(tmp_path, deck))[name]
    run = run_traced_tool(tmp_path, name, arguments)
    assert (run.ok, run.data) == (False, FILE_REFUSED)
    lines = [line for line in run.trace_lines if json.loads(line)["name"] == f"mcp.{name}"]
    assert len(lines) == 1
    assert ESCAPE in lines[0]
    for text in (run.stderr, run.log_text):
        assert "Traceback" not in text
        assert "Logging error" not in text


def command_cases(root: bytes) -> list[tuple[str, list[bytes]]]:
    bad = root + b"/x\xff.html"
    return [
        ("export", [b"export", b"pptx", root + b"/deck.html", root + b"/o\xff.pptx"]),
        ("new", [b"new", b"carbon", root + b"/n\xff.html"]),
        ("request-skip", [b"request-skip", bad, b"R-0001"]),
        ("render", [b"render", bad]),
        ("outline", [b"outline", bad]),
        ("requests", [b"requests", bad]),
        ("request-done", [b"request-done", bad, b"R-0001"]),
        ("review", [b"review", bad]),
    ]


@pytest.mark.parametrize("name", [name for name, _ in command_cases(b"")])
def test_bt037_commands_refuse_an_unencodable_name(tmp_path: Path, deck: Path, name: str) -> None:
    argv = dict(command_cases(os.fsencode(tmp_path)))[name]
    folder, deck_bytes, state = written(tmp_path), deck.read_bytes(), tree(tmp_path / "state")
    done = run_bytes(tmp_path, *argv)
    assert (done.stdout, done.stderr.decode(), done.returncode) == (b"", f"error: {FILE_REFUSED}\n", 1)
    assert written(tmp_path) == folder
    assert deck.read_bytes() == deck_bytes
    assert tree(tmp_path / "state") == state


def make_bad_file(tmp_path: Path) -> bool:
    """Create ``x\\xff.html`` with the bytes of the bootstrap; False where the file system refuses the name."""
    try:
        descriptor = os.open(os.fsencode(tmp_path) + b"/x\xff.html", os.O_WRONLY | os.O_CREAT, 0o644)
    except OSError as exc:
        if exc.errno in {errno.EILSEQ, errno.EINVAL}:
            return False
        raise
    os.close(descriptor)
    return True


@pytest.mark.parametrize("command", [b"serve", b"arch-layout"])
def test_serve_and_arch_layout_refuse_an_existing_unencodable_name(tmp_path: Path, command: bytes) -> None:
    if not make_bad_file(tmp_path):
        pytest.skip("this file system refuses undecodable names")
    done = run_bytes(tmp_path, command, os.fsencode(tmp_path) + b"/x\xff.html")
    assert (done.stdout, done.stderr.decode(), done.returncode) == (b"", f"Error: {FILE_REFUSED}\n", 1)


@pytest.mark.parametrize("command", [b"serve", b"arch-layout"])
def test_serve_and_arch_layout_keep_the_usage_answer_for_a_missing_name(tmp_path: Path, command: bytes) -> None:
    done = run_bytes(tmp_path, command, os.fsencode(tmp_path) + b"/y\xff.html")
    assert done.returncode == 2
    assert done.stderr.decode().splitlines()[-1].startswith("Error: Invalid value for 'FILE':")
    assert b"Traceback" not in done.stderr


# --- BT-041: a bind address that cannot be encoded is refused ------------------------------------------------


def host_cases(tmp_path: Path) -> list[tuple[str, list[bytes], dict[str, bytes]]]:
    root = os.fsencode(tmp_path)
    return [
        ("option", [b"serve", root + b"/deck.html", b"--no-browser", b"--host", b"a\xff"], {}),
        ("environment", [b"serve", root + b"/deck.html", b"--no-browser"], {"HTMLEDITOR_HOST": b"a\xff"}),
        (
            "new",
            [b"new", b"carbon", root + b"/n.html", b"--serve", b"--no-browser", b"--host", b"a\xff"],
            {},
        ),
    ]


@pytest.mark.parametrize("index", [0, 1, 2])
def test_bt041_commands_refuse_an_unencodable_bind_address(
    tmp_path: Path, deck: Path, index: int, ports_before: set[int]
) -> None:
    _, argv, extra = host_cases(tmp_path)[index]
    deck_bytes = deck.read_bytes()
    done = run_bytes(tmp_path, *argv, extra=extra)
    assert done.returncode == 1
    assert done.stderr.decode().splitlines()[-1] == f"Error: {HOST_REFUSED}"
    assert b"Traceback" not in done.stderr
    assert listening_ports() == ports_before
    assert deck.read_bytes() == deck_bytes
    assert (tmp_path / "n.html").exists() == (index == 2)


def test_bt041_start_server_refuses_an_unencodable_bind_address(
    tmp_path: Path, deck: Path, monkeypatch: pytest.MonkeyPatch, ports_before: set[int]
) -> None:
    monkeypatch.setenv("HTMLEDITOR_HOST", "a\udcff")
    state = tree(config.state_dir())
    assert call_tool("start_server", file=str(deck)) == (False, HOST_REFUSED)
    ok, status = call_tool("get_status")
    assert ok
    assert status["running"] is False
    assert tree(config.state_dir()) == state
    assert listening_ports() == ports_before


def test_the_file_check_comes_before_the_bind_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTMLEDITOR_HOST", "a\udcff")
    assert call_tool("start_server", file=f"{tmp_path}/x\ud800.html") == (False, FILE_REFUSED)


# --- BT-047: valid non ASCII names still work ------------------------------------------------------------------


def test_bt047_valid_non_ascii_names_still_work(tmp_path: Path, deck: Path) -> None:
    name = "Présentation été 😀.html"
    target = tmp_path / name
    shutil.copy(deck, target)
    output = tmp_path / "sortie été 😀.pptx"
    new_target = tmp_path / "n é😀.html"
    review = [{"id": "a", "slide": None, "title": "t", "why": "w", "change": "c"}]
    assert call_tool("new_file", template="carbon", file=str(new_target))[0]
    assert new_target.is_file()
    assert call_tool("get_slide", file=str(target), id="slide-0")[0]
    ops = [{"op": "set_text", "id": "slide-0", "selector": "h1", "text": "T"}]
    assert call_tool("patch", file=str(target), ops=ops)[0]  # type: ignore[arg-type]
    assert call_tool("write_review", file=str(target), suggestions=review) == (True, {"ok": True, "count": 1})  # type: ignore[arg-type]
    assert call_tool("list_requests", file=str(target))[0]
    assert call_tool("export", file=str(target), format="pptx", output=str(output))[0]
    assert output.is_file()
    assert ">T<" in target.read_text(encoding="utf-8")
    stdout, stderr, status = run_cli("outline", str(target))
    assert (status, json.loads(stdout)["file"]) == (0, str(target))
    assert run_cli("history", str(target))[2] == 0
    out, err, status = run_cli("review", str(target))
    assert status == 0
    assert out.startswith("a  ")
    for text in (stdout, stderr, out, err):
        assert FILE_REFUSED not in text
        assert "Traceback" not in text


@rs.needs_chromium
def test_bt047_render_keeps_a_valid_non_ascii_name(tmp_path: Path, deck: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    target = tmp_path / "Présentation été 😀.html"
    shutil.copy(deck, target)
    ok, data = call_tool("render", file=str(target))
    assert ok
    assert Path(data["path"]).name == "Présentation été 😀-slide-0.png"


@pytest.mark.parametrize("command", ["serve_cmd", "arch_layout_cmd"])
def test_the_callbacks_refuse_an_unencodable_name_where_the_file_system_cannot_hold_one(command: str) -> None:
    import click

    from mcp_htmleditor import cli

    callback = getattr(cli, command).callback
    arguments = {"serve_cmd": {"port": None, "host": None, "poll": None, "no_browser": True}}.get(
        command, {"diagram_id": None}
    )
    with pytest.raises(click.ClickException) as raised:
        callback(file="x\udcff.html", **arguments)
    assert raised.value.message == FILE_REFUSED
