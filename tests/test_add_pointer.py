"""SPEC-0034 (US-0172): ``mcp-htmleditor add-pointer`` gives an older deck the pointer of SPEC-0017.

E2E-001 to E2E-005 and E2E-007. Every deck lives in ``tmp_path``; "unchanged" is read on the bytes of the file.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor.history import list_versions
from tests.conftest import needs_chromium
from tests.deck_support import run_cli
from tests.pointer_old_deck_support import (
    CARBON,
    CHARTERS,
    PARTS,
    PRESENT_BUTTON,
    REFERENCE,
    older_deck,
    older_text,
    parts_in,
    without_inserted,
)
from tests.pointer_support import open_deck_p, pointer_file_page, wait_presenting, wait_state

__all__ = ["pointer_file_page"]

COMPLETE = {"code": 1, "control": 1, "key": 1}
COMBINATIONS = [keep for size in (1, 2) for keep in itertools.combinations(PARTS, size)]


def _history_reasons(deck: Path) -> list[str]:
    return [version.reason for version in list_versions(str(deck))[1]]


def _toggles_the_dot(page: Page, path: Path) -> None:
    """Present the deck full screen, then ``L`` shows the pointer and ``L`` again hides it."""
    open_deck_p(page, path)
    page.keyboard.press("f")
    wait_presenting(page)
    page.keyboard.press("l")
    wait_state(page, lambda s: s["on"], "the pointer on after L")
    page.keyboard.press("l")
    wait_state(page, lambda s: not s["on"], "the pointer off after a second L")


@needs_chromium
def test_e2e_001_an_older_carbon_deck_gets_the_pointer(tmp_path: Path, pointer_file_page: Page) -> None:
    deck = older_deck(CARBON, tmp_path, "Réunion talk.html")
    original = deck.read_bytes()
    assert parts_in(original.decode()) == {"code": 0, "control": 0, "key": 0}

    stdout, stderr, status = run_cli("add-pointer", str(deck))

    assert (stdout.strip(), stderr, status) == (f"{deck}: pointer added", "", 0)
    text = deck.read_text(encoding="utf-8")
    assert parts_in(text) == COMPLETE
    assert without_inserted(text).encode() == original
    present = PRESENT_BUTTON.search(text)
    assert present is not None
    after = text[present.end() :].lstrip()
    assert after.startswith('<button class="cds-btn-icon" id="btn-pointer"'), after[:80]
    assert _history_reasons(deck) == ["add-pointer"]
    _toggles_the_dot(pointer_file_page, deck)


def test_e2e_001_a_crlf_deck_keeps_its_line_endings(tmp_path: Path) -> None:
    deck = older_deck(CARBON, tmp_path)
    crlf = deck.read_bytes().replace(b"\n", b"\r\n")
    deck.write_bytes(crlf)

    _, _, status = run_cli("add-pointer", str(deck))

    data = deck.read_bytes()
    assert status == 0 and parts_in(data.decode()) == COMPLETE
    assert b"\n" not in data.replace(b"\r\n", b"")
    assert without_inserted(data.decode()).encode() == crlf


def test_e2e_002_a_complete_deck_is_left_alone(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh.html"
    fresh.write_bytes(CARBON.read_bytes())
    older = older_deck(CARBON, tmp_path, "older.html")
    assert run_cli("add-pointer", str(older))[2] == 0
    before = {path: path.read_bytes() for path in (fresh, older)}
    entries = len(_history_reasons(older))

    for path in (fresh, older):
        stdout, stderr, status = run_cli("add-pointer", str(path))
        assert (stdout.strip(), stderr, status) == (f"{path}: already has the pointer", "", 0)
        assert path.read_bytes() == before[path]
    assert len(_history_reasons(older)) == entries
    assert _history_reasons(fresh) == []


@pytest.mark.parametrize("keep", COMBINATIONS, ids=["+".join(keep) for keep in COMBINATIONS])
def test_e2e_003_only_the_missing_parts_are_added(tmp_path: Path, keep: tuple[str, ...]) -> None:
    deck = older_deck(CARBON, tmp_path, keep=keep)

    stdout, _, status = run_cli("add-pointer", str(deck))

    assert (stdout.strip(), status) == (f"{deck}: pointer added", 0)
    assert parts_in(deck.read_text(encoding="utf-8")) == COMPLETE


def test_e2e_003_a_control_before_present_is_not_doubled(tmp_path: Path) -> None:
    deck = older_deck(REFERENCE / "presentation-standard.html", tmp_path, keep=("control",))
    text = deck.read_text(encoding="utf-8")
    assert text.index('id="btn-pointer"') < text.index('id="btn-present"')

    assert run_cli("add-pointer", str(deck))[2] == 0

    assert parts_in(deck.read_text(encoding="utf-8")) == COMPLETE


def test_e2e_003_a_commented_script_does_not_count_as_the_code(tmp_path: Path) -> None:
    deck = older_deck(CARBON, tmp_path)
    text = deck.read_text(encoding="utf-8")
    deck.write_text(
        text.replace("</body>", '<!-- <script id="deck-pointer-script"></script> -->\n</body>'), encoding="utf-8"
    )

    assert run_cli("add-pointer", str(deck))[2] == 0

    assert parts_in(deck.read_text(encoding="utf-8")) == COMPLETE


def test_e2e_004_a_missing_file_and_a_template_file_are_refused(tmp_path: Path) -> None:
    template = CARBON
    before = template.read_bytes()
    absent = tmp_path / "absent.html"

    out_absent = run_cli("add-pointer", str(absent))
    out_template = run_cli("add-pointer", str(template))

    assert out_absent[1:] == (f"error: File not found: {absent}\n", 1)
    assert out_template[1:] == (f"error: Refusing to modify a template: {template}\n", 1)
    assert template.read_bytes() == before
    assert not absent.exists()


def test_e2e_005_a_document_a_deck_without_present_and_a_binary_file_are_refused(tmp_path: Path) -> None:
    doc = tmp_path / "doc.html"
    assert run_cli("new", "doc", str(doc))[2] == 0
    bare = tmp_path / "bare.html"
    bare.write_text(PRESENT_BUTTON.sub("", older_text(CARBON)), encoding="utf-8")
    binary = tmp_path / "binary.html"
    binary.write_bytes(older_deck(CARBON, tmp_path, "x.html").read_bytes() + b"\xff")
    before = {path: path.read_bytes() for path in (doc, bare, binary)}

    results = {path: run_cli("add-pointer", str(path)) for path in (doc, bare, binary)}

    assert results[doc][1:] == (f"error: {doc} is not a presentation\n", 1)
    assert results[bare][1:] == (
        f"error: {bare} has no Présenter control, nothing to place the Pointeur control after\n",
        1,
    )
    assert results[binary][1:] == (f"error: File is not valid UTF-8: {binary}\n", 1)
    assert {path: path.read_bytes() for path in before} == before


def test_e2e_005_a_deck_with_a_control_needs_no_present_button(tmp_path: Path) -> None:
    deck = tmp_path / "control-only.html"
    deck.write_text(PRESENT_BUTTON.sub("", older_text(CARBON, keep=("control",))), encoding="utf-8")

    stdout, _, status = run_cli("add-pointer", str(deck))

    assert (stdout.strip(), status) == (f"{deck}: pointer added", 0)
    assert parts_in(deck.read_text(encoding="utf-8")) == COMPLETE


@needs_chromium
@pytest.mark.parametrize("charter", sorted(CHARTERS))
def test_e2e_007_every_charter_works_after_the_command(tmp_path: Path, pointer_file_page: Page, charter: str) -> None:
    deck = older_deck(CHARTERS[charter], tmp_path)

    stdout, _, status = run_cli("add-pointer", str(deck))

    assert (stdout.strip(), status) == (f"{deck}: pointer added", 0)
    assert parts_in(deck.read_text(encoding="utf-8")) == COMPLETE
    assert re.search(r'id="btn-pointer"', deck.read_text(encoding="utf-8"))
    _toggles_the_dot(pointer_file_page, deck)


def test_e2e_003_a_data_id_is_not_the_present_control_and_a_commented_body_tag_is_skipped(tmp_path: Path) -> None:
    bare = tmp_path / "bare.html"
    bare.write_text(
        PRESENT_BUTTON.sub('<button data-id="btn-present">X</button>\n', older_text(CARBON)), encoding="utf-8"
    )
    assert run_cli("add-pointer", str(bare))[1:] == (
        f"error: {bare} has no Présenter control, nothing to place the Pointeur control after\n",
        1,
    )
    deck = older_deck(CARBON, tmp_path)
    deck.write_text(deck.read_text(encoding="utf-8") + "<!-- old </body> -->\n", encoding="utf-8")

    assert run_cli("add-pointer", str(deck))[2] == 0

    text = deck.read_text(encoding="utf-8")
    assert parts_in(text) == COMPLETE
    assert text.index('<script id="deck-pointer-key"') < text.index("<!-- old </body> -->")
