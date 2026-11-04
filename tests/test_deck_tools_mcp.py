"""The outline and get_slide tools give the CLI results and the CLI error text (SPEC-0007 FR-NEW-016)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from .deck_support import call_tool, deck_carbon, deck_ei, doc_perso, run_cli, write_deck

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "skill" / "core.md"


@pytest.fixture
def ei_file(tmp_path: Path) -> str:
    return write_deck(tmp_path / "ei.html", deck_ei())


@pytest.fixture
def carbon_file(tmp_path: Path) -> str:
    return write_deck(tmp_path / "carbon.html", deck_carbon())


def test_outline_tool_equals_the_cli_json(ei_file: str) -> None:
    """SPEC-0007/E2E-001: the outline of DECK-EI, CLI and tool."""
    stdout, _, status = run_cli("outline", ei_file)
    ok, value = call_tool("outline", file=ei_file)

    assert status == 0
    assert ok
    assert value == json.loads(stdout)
    assert (value["charter"], value["doc_type"], value["total"], value["headings"]) == ("ei", "presentation", 8, [])
    assert len(value["slides"]) == 8
    assert (value["slides"][2]["id"], value["slides"][2]["title"], value["slides"][2]["images"]) == (
        "slide-2",
        "Contexte",
        0,
    )
    assert value["slides"][3]["images"] == 1
    assert "base64" not in json.dumps(value)


def test_get_slide_tool_returns_the_cli_html_with_a_reference(ei_file: str) -> None:
    """SPEC-0007/E2E-003: one slide through the tool, large image replaced by a reference."""
    stdout, _, status = run_cli("get-slide", ei_file, "slide-3")
    ok, html = call_tool("get_slide", file=ei_file, id="slide-3")

    assert status == 0
    assert ok
    assert html.strip() == stdout.strip()
    assert html.startswith("<article")
    assert 'id="slide-3"' in html
    assert "base64" not in html
    assert "data:ref:img-1" in html
    assert "Contexte" not in html


def test_get_slide_unknown_id_error_equals_the_cli_line(carbon_file: str) -> None:
    _, stderr, status = run_cli("get-slide", carbon_file, "slide-9")
    ok, message = call_tool("get_slide", file=carbon_file, id="slide-9")

    assert status == 1
    assert not ok
    assert message == 'Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2, slide-3, slide-4'
    assert stderr.strip() == f"error: {message}"


def test_outline_missing_file_error_equals_the_cli_line() -> None:
    _, stderr, status = run_cli("outline", "ghost.html")
    ok, message = call_tool("outline", file="ghost.html")

    assert status == 1
    assert not ok
    assert message == "File not found: ghost.html"
    assert stderr.strip() == f"error: {message}"


def test_get_slide_on_a_document_error_equals_the_cli_line(tmp_path: Path) -> None:
    path = write_deck(tmp_path / "doc.html", doc_perso())
    _, stderr, status = run_cli("get-slide", path, "slide-0")
    ok, message = call_tool("get_slide", file=path, id="slide-0")

    assert status == 1
    assert not ok
    assert message == f"get_slide needs a presentation: {path}"
    assert stderr.strip() == f"error: {message}"


def test_both_tools_are_registered() -> None:
    from mcp_htmleditor.mcp_server import registered_tool_names

    assert {"outline", "get_slide"} <= set(registered_tool_names())


def test_core_lists_both_tools_and_the_audit_passes() -> None:
    lines = CORE.read_text(encoding="utf-8").split("## Tools", 1)[1].split("## ", 1)[0].splitlines()
    stdout, _, status = run_cli("skill-audit")

    assert any(line.startswith("- outline:") for line in lines)
    assert any(line.startswith("- get_slide:") for line in lines)
    assert status == 0, stdout


def test_mcp_process_writes_only_protocol_lines_on_stdout(ei_file: str) -> None:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "outline", "arguments": {"file": ei_file}},
        },
    ]
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_htmleditor", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd=REPO,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    messages = []
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

    assert all(m.get("jsonrpc") == "2.0" for m in messages)
    assert "isError" not in messages[-1]["result"] or not messages[-1]["result"]["isError"]
