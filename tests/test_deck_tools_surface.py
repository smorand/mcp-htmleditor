"""The lint, list_templates, new_file and export tools match the CLI results and error text (SPEC-0007 FR-NEW-016).

Closes SPEC-0007: the last test checks that every acceptance id of the spec has a test in ``tests/test_deck_*.py``.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
from pathlib import Path

import pytest

from . import stdio_support
from .deck_support import call_tool, deck_ei, run_cli, set_total, write_deck
from .stdio_support import run_session

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "skill" / "core.md"
TEMPLATE_KEYS = ["ei", "carbon", "medical", "doc", "doc-perso", "doc-ei", "mail", "website"]
FINAL_TOOLS = {
    "start_server",
    "stop_server",
    "get_status",
    "open_file",
    "update_start",
    "update_end",
    "layout_arch_diagram",
    "get_skill",
    "outline",
    "get_slide",
    "patch",
    "lint",
    "list_templates",
    "new_file",
    "export",
    "history",
    "restore",
    "list_requests",
    "clear_requests",
    "complete_request",
    "write_review",
    "render",
}
SPEC_IDS = range(1, 42)
ID_PATTERN = re.compile(r"E2E[-_]0(\d\d)", re.IGNORECASE)
needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc is not installed")


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_e2e_010_list_templates_and_new_file(workdir: Path) -> None:
    """SPEC-0007/E2E-010 (templates and new file): the 8 keys in order, then ``a.html`` is created."""
    ok, listing = call_tool("list_templates")
    assert ok
    assert [entry["key"] for entry in listing] == TEMPLATE_KEYS
    assert all(entry["description"] for entry in listing)

    ok, result = call_tool("new_file", template="doc", file="a.html")
    assert ok
    assert result == {"ok": True, "file": "a.html"}
    assert (workdir / "a.html").is_file()


@needs_pandoc
def test_e2e_010_export_writes_a_real_docx(workdir: Path) -> None:
    """SPEC-0007/E2E-010 (export step): ``a.docx`` exists and is a zip archive."""
    ok, _ = call_tool("new_file", template="doc", file="a.html")
    assert ok

    ok, result = call_tool("export", file="a.html", format="docx", output="a.docx")

    assert ok, result
    assert result["ok"] is True
    assert result["output"] == "a.docx"
    assert isinstance(result["warnings"], list)
    assert (workdir / "a.docx").read_bytes()[:2] == b"PK"


def test_e2e_010_export_pptx_returns_the_warnings_of_the_outcome(workdir: Path) -> None:
    """SPEC-0007/E2E-010 (pptx): the tool reports the output path and a list of warnings."""
    write_deck(workdir / "d.html", deck_ei())

    ok, result = call_tool("export", file="d.html", format="pptx", output="d.pptx")

    assert ok, result
    assert result["ok"] is True
    assert (result["output"], type(result["warnings"])) == ("d.pptx", list)
    assert (workdir / "d.pptx").read_bytes()[:2] == b"PK"


def test_e2e_011_file_not_found_on_the_command_line_and_the_tool(workdir: Path) -> None:
    """SPEC-0007/E2E-011: four commands print the same error line, the tool carries it without its prefix."""
    commands = [
        ("outline", "ghost.html"),
        ("lint", "ghost.html"),
        ("patch", "ghost.html", "--ops", "ops.json"),
        ("export", "docx", "ghost.html", "out.docx"),
    ]
    for command in commands:
        stdout, stderr, status = run_cli(*command)
        assert (stdout, stderr, status) == ("", "error: File not found: ghost.html\n", 1), command

    ok, message = call_tool("outline", file="ghost.html")
    assert not ok
    assert message == "File not found: ghost.html"
    assert not (workdir / "out.docx").exists()


def test_e2e_028_tool_failures(workdir: Path) -> None:
    """SPEC-0007/E2E-028: three failures with their exact text; the existing file is not touched."""
    target = workdir / "a.html"
    write_deck(target, deck_ei())
    before = target.read_bytes()

    ok, message = call_tool("export", file="a.html", format="foo", output="a.out")
    assert not ok
    assert message == 'Unknown export format "foo". Valid formats: pptx, docx'

    ok, message = call_tool("new_file", template="x", file="b.html")
    assert not ok
    assert message == f'Unknown template "x". Valid templates: {", ".join(TEMPLATE_KEYS)}'

    ok, message = call_tool("new_file", template="doc", file="a.html")
    assert not ok
    assert message == "File already exists: a.html"

    assert target.read_bytes() == before
    assert not (workdir / "b.html").exists()


def test_lint_tool_equals_the_cli_json_for_a_clean_deck(workdir: Path) -> None:
    path = write_deck(workdir / "ei.html", deck_ei())
    stdout, _, status = run_cli("lint", path, "--json")
    ok, value = call_tool("lint", file=path)

    assert (status, ok) == (0, True)
    assert value == json.loads(stdout)
    assert value == {"problems": [], "errors": 0, "warnings": 0}


def test_lint_tool_equals_the_cli_json_for_a_wrong_total(workdir: Path) -> None:
    path = write_deck(workdir / "ei.html", set_total(deck_ei(), 7))
    stdout, _, status = run_cli("lint", path, "--json")
    ok, value = call_tool("lint", file=path)

    assert (status, ok) == (1, True)
    assert value == json.loads(stdout)
    assert (value["errors"], value["warnings"], len(value["problems"])) == (1, 0, 1)
    assert value["problems"][0]["slide"] is None


def test_templates_tool_matches_the_templates_command(workdir: Path) -> None:
    stdout, _, status = run_cli("templates")
    ok, listing = call_tool("list_templates")

    assert (status, ok) == (0, True)
    for entry in listing:
        assert entry["key"] in stdout
        assert entry["description"] in stdout


def test_error_text_of_the_tools_equals_the_command_lines(workdir: Path) -> None:
    write_deck(workdir / "a.html", deck_ei())
    cases = [
        (("export", "foo", "a.html", "o"), "export", {"file": "a.html", "format": "foo", "output": "o"}),
        (("new", "doc", "a.html"), "new_file", {"template": "doc", "file": "a.html"}),
        (("lint", "ghost.html"), "lint", {"file": "ghost.html"}),
    ]
    for command, tool, arguments in cases:
        _, stderr, status = run_cli(*command)
        ok, message = call_tool(tool, **arguments)
        assert status == 1
        assert not ok
        assert stderr == f"error: {message}\n", tool


def test_new_file_never_serves(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("new_file must not serve or open a browser")

    monkeypatch.setattr("mcp_htmleditor.mcp_server.start_http_server", refuse)
    monkeypatch.setattr("webbrowser.open", refuse)

    ok, result = call_tool("new_file", template="carbon", file="sub/dir/c.html")

    assert ok, result
    assert (workdir / "sub" / "dir" / "c.html").is_file()


def _core_tool_names() -> set[str]:
    section = CORE.read_text(encoding="utf-8").split("## Tools", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^- (\w+):", section, re.MULTILINE))


def test_the_server_core_and_audit_agree_on_the_final_tools() -> None:
    from mcp_htmleditor.mcp_server import registered_tool_names

    names = registered_tool_names()
    stdout, _, status = run_cli("skill-audit")

    assert len(names) == 22
    assert set(names) == FINAL_TOOLS
    assert _core_tool_names() == FINAL_TOOLS
    assert status == 0, stdout


def test_the_new_tools_write_only_protocol_lines_on_stdout(workdir: Path) -> None:
    requests = [*stdio_support.initialize_requests(), stdio_support.tool_request(2, "list_templates", {})]
    messages = run_session(requests, {1, 2}, cwd=REPO)

    assert all(m.get("jsonrpc") == "2.0" for m in messages)
    assert not messages[-1]["result"].get("isError")


def _ids_by_test() -> dict[int, list[str]]:
    """Map each acceptance number to the tests naming it: in the function name, its docstring or the comment above."""
    found: dict[int, list[str]] = {}
    for path in sorted((REPO / "tests").glob("test_deck_*.py")):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or not node.name.startswith("test"):
                continue
            if node.name == "test_spec_closure_every_acceptance_test_exists":
                continue
            text = [node.name, ast.get_docstring(node) or ""]
            above = min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 2
            while above >= 0 and lines[above].lstrip().startswith("#"):
                text.append(lines[above])
                above -= 1
            for number in {int(m) for m in ID_PATTERN.findall("\n".join(text))}:
                found.setdefault(number, []).append(f"{path.name}::{node.name}")
    return found


def test_spec_closure_every_acceptance_test_exists() -> None:
    found = _ids_by_test()

    missing = [f"E2E-{n:03d}" for n in SPEC_IDS if n not in found]

    assert not missing, f"no test carries these ids: {missing}"
    assert set(found) >= set(SPEC_IDS)
