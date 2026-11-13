"""Speaker notes in the PPTX export and in the deck services (SPEC-0022 FR-6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pptx import Presentation

from mcp_htmleditor.export.to_pptx import to_pptx

from .deck_support import _slide_bounds, deck_ei, run_cli, write_deck

NOTES = '<aside data-role="speaker-notes">Say hello.\nThen the second line.</aside>'
SLIDE = (
    '<article class="slide" data-type="slide" data-id="s{n}" data-title="T{n}">'
    "<h1>Title {n}</h1><p>Body {n}</p>{extra}</article>"
)


def _add_notes(html: str, slide_index: int) -> str:
    """Append the notes aside as the last direct child of slide ``slide_index``."""
    _, end = _slide_bounds(html, slide_index)
    at = end - len("</article>")
    return html[:at] + NOTES + html[at:]


def _deck(*extras: str) -> str:
    slides = "".join(SLIDE.format(n=i + 1, extra=extra) for i, extra in enumerate(extras))
    return f"<!DOCTYPE html><html><head><title>t</title></head><body>{slides}</body></html>"


def _export(tmp_path: Path, html: str) -> Presentation:
    source = tmp_path / "in.html"
    source.write_text(html, encoding="utf-8")
    out = tmp_path / "out.pptx"
    to_pptx(str(source), str(out))
    return Presentation(str(out))


def _shape_texts(slide: Any) -> str:
    return " ".join(shape.text_frame.text for shape in slide.shapes if shape.has_text_frame)


def test_notes_land_on_the_notes_page_not_on_the_slide(tmp_path: Path) -> None:
    prs = _export(tmp_path, _deck(NOTES, ""))
    first, second = prs.slides
    assert first.has_notes_slide
    assert first.notes_slide.notes_text_frame.text == "Say hello.\nThen the second line."
    assert "Say hello" not in _shape_texts(first)
    assert "Body 1" in _shape_texts(first)
    assert not second.has_notes_slide


def test_deck_without_notes_has_no_notes_slide(tmp_path: Path) -> None:
    prs = _export(tmp_path, _deck("", ""))
    assert not any(slide.has_notes_slide for slide in prs.slides)


def test_nested_aside_is_not_the_notes_and_empty_aside_is_ignored(tmp_path: Path) -> None:
    empty = '<aside data-role="speaker-notes">  </aside>'
    prs = _export(tmp_path, _deck(empty))
    assert not prs.slides[0].has_notes_slide
    assert "Body 1" in _shape_texts(prs.slides[0])


def test_notes_in_a_reference_template_deck(tmp_path: Path) -> None:
    html = _add_notes(deck_ei(), 1)
    prs = _export(tmp_path, html)
    assert prs.slides[1].notes_slide.notes_text_frame.text.startswith("Say hello.")
    assert not any("Say hello" in _shape_texts(slide) for slide in prs.slides)
    assert [s.has_notes_slide for i, s in enumerate(prs.slides) if i != 1] == [False] * (len(prs.slides) - 1)


def test_notes_survive_deck_services(tmp_path: Path) -> None:
    path = write_deck(tmp_path / "ei.html", _add_notes(deck_ei(), 2))
    stdout, stderr, code = run_cli("outline", path)
    assert (stderr, code) == ("", 0)
    assert json.loads(stdout)["slides"]
    stdout, _, code = run_cli("lint", path, "--json")
    assert code == 0
    assert json.loads(stdout)["errors"] == 0
    stdout, _, _ = run_cli("get-slide", path, "slide-2")
    assert 'data-role="speaker-notes"' in stdout
    operation = {"op": "replace_slide", "id": "slide-2", "html": stdout}
    result, stderr, code = run_cli("patch", path, "--ops", "-", input=json.dumps([operation]))
    assert (stderr, code) == ("", 0)
    assert json.loads(result)["ok"] is True
    assert "Say hello.\nThen the second line." in Path(path).read_text(encoding="utf-8")
