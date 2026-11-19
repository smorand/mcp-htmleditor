"""SPEC-0028 (US-0158): the agent operation ``breathe_inline`` gives the results and errors of ``breathe-inline``.

E2E-001 to E2E-007. The tool is called through an in process ``fastmcp.Client``; the command through ``run_cli`` for
parity. "Unchanged" is read on the bytes of the deck.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.breathe_support import BOOTSTRAP, breathe_slide, reference_slide
from tests.deck_support import call_tool
from tests.test_breathe_inline import deck_with, inline, listing, picture


def two_copies(tmp_path: Path) -> tuple[Path, Path]:
    """The same Breathe deck twice, one folder each: ``tool/talk.html`` and ``command/talk.html``."""
    slides = (reference_slide("Key figures"), breathe_slide("Pic", picture("sample-clinical-b.jpg")))
    return deck_with(tmp_path, *slides, folder="tool"), deck_with(tmp_path, *slides, folder="command")


def test_e2e_001_embed_returns_the_commands_line_and_writes_the_same_file(tmp_path: Path) -> None:
    tool_deck, command_deck = two_copies(tmp_path)

    ok, result = call_tool("breathe_inline", file=str(tool_deck))
    stdout, stderr, code = inline(str(command_deck))

    assert (ok, code, stderr) == (True, 0, "")
    assert result["summary"] == stdout.replace(str(command_deck), str(tool_deck))
    assert result["ok"] is True
    assert result["classes"] >= 1
    assert result["pictures"] >= 1
    assert tool_deck.read_bytes() == command_deck.read_bytes()


def test_e2e_002_the_linked_form_copies_the_files_and_matches_the_command(tmp_path: Path) -> None:
    tool_deck, command_deck = two_copies(tmp_path)

    ok, result = call_tool("breathe_inline", file=str(tool_deck), link=True)
    stdout, _, code = inline(str(command_deck), "--link")

    assert (ok, code) == (True, 0)
    assert result["summary"] == stdout.replace(str(command_deck.parent), str(tool_deck.parent))
    assert " linked, " in result["summary"]
    assert result["copied"] >= 1
    assert listing(tool_deck.parent) == [p.replace("command", "tool") for p in listing(command_deck.parent)]
    assert tool_deck.read_bytes() == command_deck.read_bytes()


def test_e2e_003_a_missing_file_is_refused_with_the_commands_message(tmp_path: Path) -> None:
    missing = tmp_path / "absent.html"

    ok, message = call_tool("breathe_inline", file=str(missing))

    assert (ok, message) == (False, f"File not found: {missing}")
    assert not missing.exists()


def test_e2e_004_a_template_file_is_refused_and_unchanged() -> None:
    before = BOOTSTRAP.read_bytes()

    ok, message = call_tool("breathe_inline", file=str(BOOTSTRAP))

    assert (ok, message) == (False, f"Refusing to modify a template: {BOOTSTRAP}")
    assert BOOTSTRAP.read_bytes() == before


def test_e2e_005_a_repeated_call_changes_nothing(tmp_path: Path) -> None:
    tool_deck, _ = two_copies(tmp_path)

    ok, first = call_tool("breathe_inline", file=str(tool_deck))
    after_first = tool_deck.read_bytes()
    ok_again, second = call_tool("breathe_inline", file=str(tool_deck))

    assert (ok, ok_again) == (True, True)
    assert tool_deck.read_bytes() == after_first
    assert (second["classes"], second["pictures"]) == (first["classes"], first["pictures"])


def test_e2e_006_nothing_to_embed_reports_zero(tmp_path: Path) -> None:
    path = tmp_path / "talk.html"
    html = BOOTSTRAP.read_text(encoding="utf-8")
    html = html.replace("med-bg-cover-s0", "plain-bg").replace(" med-ico-", " x-ico-").replace("data-asset=", "data-x=")
    path.write_text(html, encoding="utf-8")

    ok, result = call_tool("breathe_inline", file=str(path))

    assert ok is True
    assert (result["classes"], result["pictures"]) == (0, 0)
    assert result["summary"].startswith(f"{path}: 0 background and icon classes, 0 pictures embedded, ")


def test_e2e_007_a_deck_without_the_decoration_block_is_refused_and_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "med.html"
    shutil.copyfile(BOOTSTRAP.parent / "slides-medical-empty.html", path)
    before = path.read_bytes()

    ok, message = call_tool("breathe_inline", file=str(path))

    assert (ok, message) == (False, f"{path} has no breathe:assets block in its <style>")
    assert path.read_bytes() == before


def test_e2e_003_the_other_refusals_carry_the_commands_messages(tmp_path: Path) -> None:
    """FR-NEW-003: not found asset, a name that is not a plain file name, a file that is not UTF-8."""
    missing = deck_with(tmp_path, breathe_slide("P", picture("nowhere.jpg")), folder="missing")
    escaping = deck_with(tmp_path, breathe_slide("P", picture("../secret.png")), folder="escaping")
    binary = tmp_path / "bin" / "talk.html"
    binary.parent.mkdir()
    binary.write_bytes(b"\xff\xfe\x00bad")
    for deck in (missing, escaping, binary):
        before = deck.read_bytes()

        ok, message = call_tool("breathe_inline", file=str(deck))
        _, stderr, code = inline(str(deck))

        assert (ok, code) == (False, 1)
        assert stderr == f"error: {message}"
        assert deck.read_bytes() == before
