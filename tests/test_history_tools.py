"""SPEC-0009 US-0051: the ``history`` and ``restore`` tools and the ``patch`` snapshot.

Tools run through an in process ``fastmcp.Client`` (``call_tool``); versions are created with the shared
writer and a ``FakeClock`` so ids are distinct seconds apart. Tool errors must equal the command line line
without its ``error: `` prefix.
"""

from __future__ import annotations

import errno
import re
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import fileio
from mcp_htmleditor.fileio import atomic_write
from mcp_htmleditor.mcp_server import registered_tool_names
from mcp_htmleditor.state import EditorState

from .deck_support import call_tool, deck_ei, run_cli, write_deck
from .test_state import T0, FakeClock

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "skill" / "core.md"
SET_TITLE = {"op": "set_text", "id": "slide-2", "selector": ".slide-h1", "text": "Contexte et enjeux"}
SAME_TITLE = {"op": "set_text", "id": "slide-2", "selector": ".slide-h1", "text": "Contexte"}
LINE = re.compile(r"^(\d{8}T\d{6}Z(?:-\d+)?)  (\d+) bytes  ([a-z-]+)$")


@pytest.fixture
def clock(fresh_state: EditorState) -> FakeClock:
    fake = FakeClock(T0)
    fresh_state.clock = fake
    return fake


@pytest.fixture
def deck(tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "work"
    folder.mkdir()
    monkeypatch.chdir(folder)
    return Path(write_deck(folder / "deck.html", deck_ei()))


def _save_twice(deck: Path, clock: FakeClock) -> None:
    """Two browser style saves one second apart: the history then holds the two previous contents."""
    for label in ("one", "two"):
        html = deck.read_text(encoding="utf-8").replace("<title>", f"<title>{label} ", 1)
        atomic_write(deck, html, reason="browser-save")
        clock.advance(1)


def _core_tools() -> set[str]:
    text = CORE.read_text(encoding="utf-8")
    section = text.split("## Tools", 1)[1].split("\n## ", 1)[0]
    return {m.group(1) for m in re.finditer(r"^- ([a-z_]+):", section, re.MULTILINE)}


# --- E2E ---------------------------------------------------------------------


def test_e2e_006_history_then_restore(deck: Path, clock: FakeClock) -> None:
    """SPEC-0009/E2E-006."""
    original = deck.read_bytes()
    _save_twice(deck, clock)

    ok, listing = call_tool("history", file="deck.html")
    assert ok, listing
    assert listing["file"] == str(deck.resolve())
    versions = listing["versions"]
    assert len(versions) == 2
    for version in versions:
        assert set(version) == {"id", "bytes", "reason"}
        assert version["reason"] == "browser-save"
    assert versions[0]["bytes"] > versions[1]["bytes"] == len(original)

    oldest = versions[-1]["id"]
    ok, restored = call_tool("restore", file="deck.html", id=oldest)
    assert ok, restored
    assert restored == {"ok": True, "file": str(deck.resolve()), "id": oldest}
    assert deck.read_bytes() == original

    ok, after = call_tool("history", file="deck.html")
    assert ok
    assert after["versions"][0]["reason"] == "restore"
    assert len(after["versions"]) == 3


def test_e2e_026_patch_snapshots_the_previous_content(deck: Path) -> None:
    """SPEC-0009/E2E-026."""
    before = deck.stat().st_size

    ok, result = call_tool("patch", file=str(deck), ops=[SET_TITLE])
    assert ok, result
    assert result["changed"] is True

    stdout, _, status = run_cli("history", "deck.html")
    assert status == 0
    first = LINE.match(stdout.splitlines()[0])
    assert first, stdout
    assert first.group(3) == "patch"
    assert int(first.group(2)) == before


def test_patch_that_changes_nothing_keeps_no_version(deck: Path) -> None:
    ok, result = call_tool("patch", file=str(deck), ops=[SAME_TITLE])
    assert ok, result
    assert result["changed"] is False

    ok, listing = call_tool("history", file="deck.html")
    assert ok
    assert listing["versions"] == []


def test_dry_run_patch_keeps_no_version_and_the_file(deck: Path) -> None:
    before = deck.read_bytes()
    ok, result = call_tool("patch", file=str(deck), ops=[SET_TITLE], dry_run=True)
    assert ok, result
    assert result["changed"] is True
    assert result["dry_run"] is True

    assert deck.read_bytes() == before
    ok, listing = call_tool("history", file="deck.html")
    assert ok
    assert listing["versions"] == []


def test_patch_whose_replace_fails_keeps_history_file_and_folder(deck: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = deck.read_bytes()
    entries = sorted(entry.name for entry in deck.parent.iterdir())

    def failing(*_args: Any, **_kwargs: Any) -> None:
        raise OSError(errno.EIO, "Input/output error")

    with monkeypatch.context() as patched:
        patched.setattr(fileio, "replace_file", failing)
        ok, message = call_tool("patch", file=str(deck), ops=[SET_TITLE])
    assert not ok
    assert "Input/output error" in message

    assert deck.read_bytes() == before
    assert sorted(entry.name for entry in deck.parent.iterdir()) == entries
    ok, listing = call_tool("history", file="deck.html")
    assert ok
    assert listing["versions"] == []


# --- errors equal the command line line ---------------------------------------


def _cli_error(*args: str) -> str:
    _, stderr, status = run_cli(*args)
    assert status == 1
    assert stderr.startswith("error: ")
    return stderr.removeprefix("error: ").rstrip("\n")


def test_missing_file_error_matches_the_cli(deck: Path) -> None:
    for tool, args in (("history", {"file": "ghost.html"}), ("restore", {"file": "ghost.html", "id": "x"})):
        ok, message = call_tool(tool, **args)
        assert not ok
        assert message == "File not found: ghost.html"
    assert message == _cli_error("restore", "ghost.html", "x")


def test_unknown_id_error_matches_the_cli(deck: Path, clock: FakeClock) -> None:
    ok, message = call_tool("restore", file="deck.html", id="nope")
    assert not ok
    assert message == 'Unknown history id "nope". Valid ids: none'
    assert message == _cli_error("restore", "deck.html", "nope")

    _save_twice(deck, clock)
    ok, listing = call_tool("history", file="deck.html")
    ids = ", ".join(v["id"] for v in listing["versions"])
    ok, message = call_tool("restore", file="deck.html", id="nope")
    assert not ok
    assert message == f'Unknown history id "nope". Valid ids: {ids}'
    assert message == _cli_error("restore", "deck.html", "nope")


def test_template_error_matches_the_cli(deck: Path) -> None:
    template = "templates/bootstrap/x.html"
    ok, message = call_tool("restore", file=template, id="y")
    assert not ok
    assert message == f"Refusing to modify a template: {template}"
    assert message == _cli_error("restore", template, "y")


def test_write_failure_error_matches_the_cli(deck: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch) -> None:
    _save_twice(deck, clock)
    ok, listing = call_tool("history", file="deck.html")
    oldest = listing["versions"][-1]["id"]

    def failing(*_args: Any, **_kwargs: Any) -> None:
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(fileio, "replace_file", failing)
    ok, message = call_tool("restore", file="deck.html", id=oldest)
    assert not ok
    assert message == "Permission denied"
    assert message == _cli_error("restore", "deck.html", oldest)


# --- registration --------------------------------------------------------------


def test_tools_are_registered_and_listed_in_the_core() -> None:
    names = set(registered_tool_names())
    assert {"history", "restore"} <= names
    assert _core_tools() == names
    core = CORE.read_text(encoding="utf-8")
    assert "- history: list the saved previous versions of a file, newest first (id, bytes, reason)." in core
    assert (
        "- restore: put a previous version of a file back by id; the replaced content is kept in the history." in core
    )


def test_tools_write_nothing_on_stdout(deck: Path, clock: FakeClock, capfd: pytest.CaptureFixture[str]) -> None:
    _save_twice(deck, clock)
    capfd.readouterr()
    ok, listing = call_tool("history", file="deck.html")
    assert ok
    ok, _ = call_tool("restore", file="deck.html", id=listing["versions"][-1]["id"])
    assert ok
    assert capfd.readouterr().out == ""
