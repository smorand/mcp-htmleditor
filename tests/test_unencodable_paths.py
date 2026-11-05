"""Exploit tests for SPEC-0013 US-0076 (BUG-004, BR-018): deck services given a path UTF-8 cannot hold.

A JSON ``"\\ud800"`` or an undecodable command line byte reached the file name encoder or a strict UTF-8 hash:
``new_file`` raised ``UnicodeEncodeError``, ``export`` printed an ``OSError`` traceback, ``history``, ``outline``,
``lint`` and ``render`` said ``File not found``. Every service now refuses the path and changes nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import config
from tests.deck_support import BOOTSTRAP, call_tool, run_cli

REPO = Path(__file__).resolve().parents[1]
REFUSED_TEXT = "File name cannot be encoded"
OPS_EMPTY = "[]"
SCRATCH = {"cache", "logs", "state"}  # written by the subprocess itself


@pytest.fixture
def deck(tmp_path: Path) -> Path:
    path = tmp_path / "deck.html"
    path.write_bytes((BOOTSTRAP / "slides-empty.html").read_bytes())
    return path


def tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def run_bytes(tmp_path: Path, *argv: bytes) -> subprocess.CompletedProcess[bytes]:
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO / "src"),
        "HTMLEDITOR_STATE_DIR": str(tmp_path / "state"),
        "HTMLEDITOR_LOG_DIR": str(tmp_path / "logs"),
        "HTMLEDITOR_CACHE_DIR": str(tmp_path / "cache"),
    }
    command = [sys.executable, "-m", "mcp_htmleditor", *argv]
    return subprocess.run(command, env=env, capture_output=True, timeout=120, cwd=REPO, check=False)  # type: ignore[call-overload]  # noqa: S603


def test_bt_033_new_file_under_an_unencodable_name_gets_a_tool_error(tmp_path: Path) -> None:
    before = sorted(p.name for p in tmp_path.iterdir())
    ok, text = call_tool("new_file", template="carbon", file=f"{tmp_path}/n\ud800.html")
    assert (ok, text) == (False, REFUSED_TEXT)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def command_cases(root: bytes) -> list[tuple[str, list[bytes]]]:
    bad = root + b"/x\xff.html"
    ops = root + b"/ops.json"
    return [
        ("outline", [b"outline", bad]),
        ("lint", [b"lint", bad]),
        ("get-slide", [b"get-slide", bad, b"slide-0"]),
        ("patch", [b"patch", bad, b"--ops", ops]),
        ("history", [b"history", bad]),
        ("restore", [b"restore", bad, b"20260101T000000Z"]),
        ("render", [b"render", bad]),
        ("new", [b"new", b"carbon", root + b"/n\xff.html"]),
        ("export", [b"export", b"pptx", root + b"/deck.html", root + b"/o\xff.pptx"]),
    ]


@pytest.mark.parametrize("name", [name for name, _ in command_cases(b"")])
def test_commands_refuse_an_undecodable_path(tmp_path: Path, deck: Path, name: str) -> None:
    (tmp_path / "ops.json").write_text(OPS_EMPTY, encoding="utf-8")
    argv = dict(command_cases(os.fsencode(tmp_path)))[name]
    folder, deck_bytes, state = tree(tmp_path), deck.read_bytes(), tree(tmp_path / "state")
    done = run_bytes(tmp_path, *argv)
    assert (done.stdout, done.stderr.decode(), done.returncode) == (b"", f"error: {REFUSED_TEXT}\n", 1)
    assert b"Traceback" not in done.stderr
    assert [p for p in tree(tmp_path) if p.split("/")[0] not in SCRATCH] == [
        p for p in folder if p.split("/")[0] not in SCRATCH
    ]
    assert deck.read_bytes() == deck_bytes
    assert tree(tmp_path / "state") == state


def tool_cases(tmp_path: Path, deck: Path) -> list[tuple[str, dict[str, Any]]]:
    bad = f"{tmp_path}/x\ud800.html"
    return [
        ("outline", {"file": bad}),
        ("get_slide", {"file": bad, "id": "slide-0"}),
        ("patch", {"file": bad, "ops": []}),
        ("lint", {"file": bad}),
        ("history", {"file": bad}),
        ("restore", {"file": bad, "id": "x"}),
        ("export", {"file": str(deck), "format": "pptx", "output": f"{tmp_path}/o\ud800.pptx"}),
    ]


@pytest.mark.parametrize("name", ["outline", "get_slide", "patch", "lint", "history", "restore", "export"])
def test_tools_refuse_an_unencodable_path(tmp_path: Path, deck: Path, name: str) -> None:
    arguments = dict(tool_cases(tmp_path, deck))[name]
    before, state = sorted(p.name for p in tmp_path.iterdir()), tree(config.state_dir())
    assert call_tool(name, **arguments) == (False, REFUSED_TEXT)
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert tree(config.state_dir()) == state


def test_the_order_of_checks_is_kept(tmp_path: Path, deck: Path) -> None:
    ok, text = call_tool("new_file", template="nope", file=f"{tmp_path}/n\ud800.html")
    assert not ok
    assert text.startswith('Unknown template "nope".')
    ok, text = call_tool("export", file=str(deck), format="nope", output=f"{tmp_path}/o\ud800.pptx")
    assert not ok
    assert text.startswith('Unknown export format "nope".')


def test_valid_non_ascii_names_still_work(tmp_path: Path) -> None:
    target = tmp_path / "n é😀.html"
    ok, _ = call_tool("new_file", template="carbon", file=str(target))
    assert ok
    assert target.is_file()
    assert call_tool("outline", file=str(target))[0]
    assert call_tool("history", file=str(target))[0]
    assert run_cli("outline", str(target))[2] == 0
