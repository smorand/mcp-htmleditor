"""US-0066: JSON output and the render tool (SPEC-0008 E2E-005, E2E-006, E2E-007, E2E-011, E2E-025, E2E-026, E2E-028).

The in process ``fastmcp.Client`` runs the sync tool in a worker thread without an event loop, which the
Playwright sync API needs; ``call_tool`` and ``run_cli`` here both use their own thread for the same reason.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from tests import render_support as rs
from tests.deck_support import call_tool, doc_perso, write_deck
from tests.deck_support import run_cli as _run_cli

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "skill" / "core.md"
INSTALL_MESSAGE = "Rendering needs Chromium. Install it with: make install-browser"
CONFLICT = "--report-only cannot be used with --slide, --scale or --report"
BLOCK = '<div style="height:700px">x</div>'
RENDER_LINE = (
    "- render: Picture of one slide plus a layout report (overflow, clipped, font, script, image); "
    "needs Chromium (make install-browser)."
)


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture(autouse=True)
def out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    return tmp_path / "tmp" / "htmleditor-render"


@pytest.fixture
def ei_file(tmp_path: Path) -> str:
    return write_deck(tmp_path / "DECK-EI.html", rs.ei_deck_html())


@pytest.fixture
def empty_browsers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "no-browsers"
    empty.mkdir()
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(empty))


def _stdio_call(name: str, arguments: dict[str, Any], tmpdir: Path) -> dict[str, Any]:
    """Call one tool of a real ``mcp-htmleditor mcp`` process over stdio and return its structured result."""
    init = {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "t", "version": "0"},
    }
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": init},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    ]
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_htmleditor", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd=ROOT,
        env={**os.environ, "TMPDIR": str(tmpdir)},
    )
    assert process.stdin is not None
    assert process.stdout is not None
    messages: list[dict[str, Any]] = []
    try:
        process.stdin.write("".join(json.dumps(r) + "\n" for r in requests))
        process.stdin.flush()
        while not {1, 2} <= {m.get("id") for m in messages}:
            line = process.stdout.readline()
            assert line, "the server closed stdout before answering"
            messages.append(json.loads(line))  # a stray text line fails here
    finally:
        process.kill()
        process.wait(timeout=10)
    result = messages[-1]["result"]
    assert not result.get("isError")
    structured: dict[str, Any] = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    return structured


# E2E-005


@rs.needs_chromium
def test_e2e_005_tool_call_over_stdio(ei_file: str, tmp_path: Path) -> None:
    value = _stdio_call("render", {"file": ei_file, "slide": "slide-1", "report": True}, tmp_path)
    assert list(value) == ["ok", "path", "width", "height", "problems"]
    assert value["ok"] is True
    assert value["path"].endswith("DECK-EI-slide-1.png")
    assert (value["width"], value["height"], value["problems"]) == (480, 270, [])
    assert rs.png_size(Path(value["path"])) == (480, 270)


@rs.needs_chromium
def test_tool_in_process_returns_the_object(ei_file: str, out_dir: Path) -> None:
    ok, value = call_tool("render", file=ei_file, slide="slide-1", report=True)
    assert ok
    assert value == {
        "ok": True,
        "path": str(out_dir / "DECK-EI-slide-1.png"),
        "width": 480,
        "height": 270,
        "problems": [],
    }


# E2E-006


@rs.needs_chromium
def test_e2e_006_json_on_the_command_line(ei_file: str, out_dir: Path) -> None:
    stdout, stderr, status = run_cli("render", ei_file, "--json")
    path = out_dir / "DECK-EI-slide-0.png"
    expected = {"ok": True, "path": str(path), "width": 480, "height": 270, "problems": []}
    assert (stderr, status) == ("", 0)
    assert stdout == json.dumps(expected, separators=(",", ":"), ensure_ascii=False) + "\n"


@rs.needs_chromium
def test_tool_and_json_command_give_equal_objects(ei_file: str) -> None:
    stdout, _, status = run_cli("render", ei_file, "--slide", "slide-1", "--json")
    ok, value = call_tool("render", file=ei_file, slide="slide-1")
    assert status == 0
    assert ok
    assert value == json.loads(stdout)


@rs.needs_chromium
def test_json_with_report_prints_no_text_line(ei_file: str) -> None:
    stdout, stderr, status = run_cli("render", ei_file, "--report", "--json")
    assert (stderr, status) == ("", 0)
    assert json.loads(stdout)["problems"] == []
    assert stdout.count("\n") == 1


# E2E-007


def test_e2e_007_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    stdout, stderr, status = run_cli("render", "ghost.html")
    assert (stdout, stderr, status) == ("", "error: File not found: ghost.html\n", 1)
    ok, message = call_tool("render", file="ghost.html")
    assert (ok, message) == (False, "File not found: ghost.html")


# E2E-011


def test_e2e_011_browser_missing(ei_file: str, empty_browsers: None, out_dir: Path) -> None:
    stdout, stderr, status = run_cli("render", ei_file)
    assert (stdout, stderr, status) == ("", f"error: {INSTALL_MESSAGE}\n", 1)
    ok, message = call_tool("render", file=ei_file)
    assert (ok, message) == (False, INSTALL_MESSAGE)
    assert not out_dir.exists()


def test_missing_playwright_package_command_and_tool(ei_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    stdout, stderr, status = run_cli("render", ei_file, "--json")
    assert (stdout, stderr, status) == ("", f"error: {INSTALL_MESSAGE}\n", 1)
    ok, message = call_tool("render", file=ei_file)
    assert (ok, message) == (False, INSTALL_MESSAGE)


# E2E-025


@rs.needs_chromium
def test_e2e_025_server_state_untouched(served_deck: Any) -> None:
    before_bytes = served_deck.path.read_bytes()
    before_mtime = served_deck.path.stat().st_mtime_ns
    ok_before, before = call_tool("get_status")
    ok, value = call_tool("render", file=str(served_deck.path), report_only=True)
    ok_after, after = call_tool("get_status")
    assert ok_before and ok and ok_after
    assert value["path"] is None
    assert before["running"] is True
    assert before == after
    assert served_deck.path.read_bytes() == before_bytes
    assert served_deck.path.stat().st_mtime_ns == before_mtime


def test_tool_never_reads_the_editor_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import mcp_htmleditor.mcp_server as server

    def forbidden() -> None:
        raise AssertionError("render must not call get_state")

    monkeypatch.setattr(server, "get_state", forbidden)
    ok, message = call_tool("render", file=str(tmp_path / "ghost.html"))
    assert (ok, message) == (False, f"File not found: {tmp_path / 'ghost.html'}")


# E2E-026


@rs.needs_chromium
def test_e2e_026_problems_as_json(tmp_path: Path, out_dir: Path) -> None:
    file = write_deck(tmp_path / "DECK-EI.html", rs.inject_in_body(rs.ei_deck_html(), "slide-4", BLOCK))
    stdout, stderr, status = run_cli("render", file, "--report-only", "--json")
    value = json.loads(stdout)
    assert (stderr, status) == ("", 1)
    assert stdout.count("\n") == 1
    assert (value["ok"], value["path"], value["width"], value["height"]) == (True, None, None, None)
    assert len(value["problems"]) == 1
    problem = value["problems"][0]
    assert list(problem) == ["kind", "slide", "message"]
    assert (problem["kind"], problem["slide"]) == ("overflow", "slide-4")
    assert problem["message"].startswith("content is ")
    assert not out_dir.exists()


@rs.needs_chromium
def test_report_only_through_the_tool(tmp_path: Path) -> None:
    file = write_deck(tmp_path / "DECK-EI.html", rs.inject_in_body(rs.ei_deck_html(), "slide-4", BLOCK))
    ok, value = call_tool("render", file=file, report_only=True)
    assert ok
    assert (value["ok"], value["path"], value["width"], value["height"]) == (True, None, None, None)
    assert [(p["kind"], p["slide"]) for p in value["problems"]] == [("overflow", "slide-4")]
    assert set(value["problems"][0]) == {"kind", "slide", "message"}


# E2E-028


def test_e2e_028_json_with_an_error(ei_file: str) -> None:
    if rs.HAS_CHROMIUM:
        stdout, stderr, status = run_cli("render", ei_file, "--slide", "slide-9", "--json")
        assert stdout == ""
        assert stderr.startswith('error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1')
        assert status == 1
    ok, message = call_tool("render", file=ei_file, report_only=True, slide="slide-1")
    assert (ok, message) == (False, CONFLICT)


def test_json_keeps_the_usage_error_and_status(ei_file: str) -> None:
    stdout, stderr, status = run_cli("render", ei_file, "--report-only", "--report", "--json")
    assert (stdout, stderr, status) == ("", f"Error: {CONFLICT}\n", 2)


def test_json_with_a_document_keeps_the_error(tmp_path: Path) -> None:
    file = write_deck(tmp_path / "DOC-PERSO.html", doc_perso())
    stdout, stderr, status = run_cli("render", file, "--json")
    assert (stdout, stderr, status) == ("", f"error: render needs a presentation: {file}\n", 1)
    ok, message = call_tool("render", file=file)
    assert (ok, message) == (False, f"render needs a presentation: {file}")


# tool conflict messages


@pytest.mark.parametrize("extra", [{"slide": "slide-1"}, {"scale": 0.7}, {"report": True}])
def test_tool_conflicts(ei_file: str, extra: dict[str, Any]) -> None:
    ok, message = call_tool("render", file=ei_file, report_only=True, **extra)
    assert (ok, message) == (False, CONFLICT)


@rs.needs_chromium
def test_tool_default_scale_with_report_only_is_accepted(ei_file: str) -> None:
    ok, value = call_tool("render", file=ei_file, report_only=True, scale=0.5)
    assert ok
    assert value["path"] is None


# result_to_dict


def test_result_to_dict_keeps_the_key_order_and_the_nulls() -> None:
    from mcp_htmleditor.render import RenderProblem, RenderResult
    from mcp_htmleditor.render.problems import result_to_dict

    only = RenderResult(None, None, None, None, (RenderProblem("font", "slide-2", "caf\u00e9"),))
    assert list(result_to_dict(only)) == ["ok", "path", "width", "height", "problems"]
    assert result_to_dict(only) == {
        "ok": True,
        "path": None,
        "width": None,
        "height": None,
        "problems": [{"kind": "font", "slide": "slide-2", "message": "caf\u00e9"}],
    }
    picture = RenderResult(Path("/pics/a.png"), 480, 270, "slide-0")
    assert result_to_dict(picture) == {"ok": True, "path": "/pics/a.png", "width": 480, "height": 270, "problems": []}


# skill


def test_skill_audit_lists_render_in_the_core() -> None:
    from mcp_htmleditor.mcp_server import registered_tool_names

    section = CORE.read_text(encoding="utf-8").split("## Tools", 1)[1].split("\n## ", 1)[0]
    lines = [line for line in section.splitlines() if line.startswith("- ")]
    assert lines[-1] == RENDER_LINE
    assert "render" in registered_tool_names()
    stdout, _, status = run_cli("skill-audit")
    assert status == 0, stdout
