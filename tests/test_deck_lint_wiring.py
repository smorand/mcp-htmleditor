"""Tests for lint wired into ``outline`` and ``patch`` (SPEC-0007 FR-NEW-001, FR-NEW-011, US-0044)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deck_support import (
    TINY_PNG,
    deck_ei,
    deck_med,
    inject_html,
    run_cli,
    set_total,
    slide_html,
    write_deck,
)

REMOTE = '<img src="https://example.com/a.png">'
TEMPLATE_TEXT = "<p>Contenu de la slide</p>"
L009 = {"code": "L009", "severity": "error", "slide": "slide-1", "message": "slide has an image and no source line"}
NO_SOURCE_SLIDE = (
    '<article class="slide" data-type="slide" data-id="x" data-slide-type="content" data-title="T">'
    '<div class="med-band"></div><div class="med-head">'
    '<div class="slide-eyebrow">Cat · Slide 01 / 01</div><h1 class="slide-h1">T</h1>'
    '<div class="med-rule"><i></i><b></b></div></div>'
    f'<div class="slide-body"><img src="data:image/png;base64,{TINY_PNG}" alt="a"></div>'
    '<div class="med-foot"><span class="slide-foot-page">1</span></div></article>'
)


def outline_problems(tmp_path: Path, content: str) -> list[int]:
    """Return the per slide ``problems`` counts of ``outline``."""
    stdout, stderr, code = run_cli("outline", write_deck(tmp_path / "f.html", content))
    assert (stderr, code) == ("", 0)
    slides: list[dict[str, Any]] = json.loads(stdout)["slides"]
    return [slide["problems"] for slide in slides]


def patch(path: str, ops: list[dict[str, str]], *flags: str) -> dict[str, Any]:
    """Run ``patch`` and return the parsed result."""
    stdout, stderr, code = run_cli("patch", path, "--ops", "-", *flags, input=json.dumps(ops))
    assert (stderr, code) == ("", 0)
    result: dict[str, Any] = json.loads(stdout)
    return result


def test_deck_lint_wiring_replace_lists_l009(tmp_path: Path) -> None:
    """E2E-027: the replaced slide lints, other slides are not listed, the file is written."""
    path = write_deck(tmp_path / "med.html", deck_med())
    before = Path(path).read_bytes()
    result = patch(path, [{"op": "replace_slide", "id": "slide-1", "html": NO_SOURCE_SLIDE}])
    assert result["ok"] is True
    assert result["problems"] == [L009]
    assert Path(path).read_bytes() != before


def test_deck_lint_wiring_remote_image_report(tmp_path: Path) -> None:
    """E2E-036: lint text and JSON, and outline reports 1 for slide-2 only."""
    content = inject_html(deck_ei(), 2, REMOTE)
    path = write_deck(tmp_path / "ei.html", content)
    message = "remote image https://example.com/a.png is not exported"
    stdout, _, code = run_cli("lint", path)
    lines = stdout.splitlines()
    assert code == 0
    assert lines == [f"warning L010 slide-2 {message}", "lint: OK (0 errors, 1 warning)"]
    stdout, _, _ = run_cli("lint", path, "--json")
    expected = {
        "problems": [{"code": "L010", "severity": "warning", "slide": "slide-2", "message": message}],
        "errors": 0,
        "warnings": 1,
    }
    assert json.loads(stdout) == expected
    assert outline_problems(tmp_path, content) == [0, 0, 1, 0, 0, 0, 0, 0]


def test_deck_lint_wiring_outline_counts_warnings_and_errors(tmp_path: Path) -> None:
    """A slide with one L010 and one L006 counts 2; a whole file L002 counts nowhere."""
    content = set_total(inject_html(deck_ei(), 3, REMOTE + TEMPLATE_TEXT), 7)
    assert outline_problems(tmp_path, content) == [0, 0, 0, 2, 0, 0, 0, 0]


def test_deck_lint_wiring_outline_clean_decks(tmp_path: Path) -> None:
    """A clean deck has 0 problems on every slide."""
    assert outline_problems(tmp_path, deck_ei()) == [0] * 8


def test_deck_lint_wiring_patch_ignores_untouched_slides(tmp_path: Path) -> None:
    """A problem of slide-5 is not listed when only slide-2 is touched."""
    path = write_deck(tmp_path / "ei.html", inject_html(deck_ei(), 5, TEMPLATE_TEXT))
    result = patch(path, [{"op": "set_text", "id": "slide-2", "selector": ".slide-h1", "text": "Autre"}])
    assert result["problems"] == []


def test_deck_lint_wiring_set_text_unchanged_still_lints(tmp_path: Path) -> None:
    """A set_text that changes nothing lints its slide."""
    path = write_deck(tmp_path / "ei.html", inject_html(deck_ei(), 5, TEMPLATE_TEXT))
    ops = [{"op": "set_text", "id": "slide-5", "selector": ".slide-h1", "text": "Planning"}]
    result = patch(path, ops)
    assert result["changed"] is False
    assert [(p["code"], p["slide"]) for p in result["problems"]] == [("L006", "slide-5")]


def test_deck_lint_wiring_insert_uses_renumbered_id(tmp_path: Path) -> None:
    """The inserted slide is lint with its id after renumbering."""
    path = write_deck(tmp_path / "ei.html", deck_ei())
    html = slide_html("ei", "Nouveau", extra=TEMPLATE_TEXT)
    result = patch(path, [{"op": "insert_slide", "after": "slide-4", "html": html}])
    assert [(p["code"], p["slide"]) for p in result["problems"]] == [("L006", "slide-5")]


def test_deck_lint_wiring_follows_a_moved_slide(tmp_path: Path) -> None:
    """A touched slide that is then moved keeps its flag at its final index."""
    path = write_deck(tmp_path / "ei.html", inject_html(deck_ei(), 5, TEMPLATE_TEXT))
    ops = [
        {"op": "set_text", "id": "slide-5", "selector": ".slide-h1", "text": "Planning"},
        {"op": "move_slide", "id": "slide-5", "after": "slide-1"},
    ]
    result = patch(path, ops)
    assert [(p["code"], p["slide"]) for p in result["problems"]] == [("L006", "slide-2")]


def test_deck_lint_wiring_dry_run_same_problems(tmp_path: Path) -> None:
    """A dry run lists the same problems as the real run and writes nothing."""
    path = write_deck(tmp_path / "med.html", deck_med())
    before = Path(path).read_bytes()
    ops = [{"op": "replace_slide", "id": "slide-1", "html": NO_SOURCE_SLIDE}]
    dry = patch(path, ops, "--dry-run")
    assert Path(path).read_bytes() == before
    real = patch(path, ops)
    assert dry["problems"] == real["problems"] == [L009]
    assert dry["dry_run"] is True
