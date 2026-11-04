"""Tests for ``mcp-htmleditor outline`` (SPEC-0007 FR-NEW-001, US-0035)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .deck_support import (
    BOOTSTRAP,
    deck_carbon,
    deck_ei,
    deck_med,
    doc_perso,
    run_cli,
    write_deck,
)


def outline_of(tmp_path: Path, content: str, name: str = "f.html") -> dict[str, Any]:
    """Write ``content``, run ``outline`` and return the parsed JSON."""
    stdout, stderr, code = run_cli("outline", write_deck(tmp_path / name, content))
    assert (stderr, code) == ("", 0)
    parsed: dict[str, Any] = json.loads(stdout)
    return parsed


def test_deck_outline_document_is_exact(tmp_path: Path) -> None:
    """E2E-002: the document outline is the exact compact JSON."""
    path = write_deck(tmp_path / "doc.html", doc_perso())
    stdout, stderr, code = run_cli("outline", path)
    expected = (
        f'{{"file":{json.dumps(path)},"charter":"doc-perso","doc_type":"document","total":0,"slides":[],'
        '"headings":[{"level":1,"text":"Contexte"},{"level":2,"text":"Périmètre"},{"level":1,"text":"Risques"}]}\n'
    )
    assert (stdout, stderr, code) == (expected, "", 0)


def test_deck_outline_ei(tmp_path: Path) -> None:
    """The EI deck reports 8 slides and no image data."""
    path = write_deck(tmp_path / "ei.html", deck_ei())
    stdout, _, code = run_cli("outline", path)
    assert code == 0
    assert "base64" not in stdout
    data = json.loads(stdout)
    assert (data["charter"], data["doc_type"], data["total"], data["headings"]) == ("ei", "presentation", 8, [])
    assert len(data["slides"]) == 8
    assert list(data) == ["file", "charter", "doc_type", "total", "slides", "headings"]
    assert list(data["slides"][0]) == ["index", "id", "title", "slide_type", "words", "images", "problems"]
    slide = data["slides"][2]
    assert (slide["id"], slide["title"], slide["images"]) == ("slide-2", "Contexte", 0)
    assert data["slides"][3]["images"] == 1
    assert data["slides"][7]["slide_type"] == "section"
    assert {s["problems"] for s in data["slides"]} == {0}


def test_deck_outline_carbon_and_medical(tmp_path: Path) -> None:
    """Carbon and medical decks are told apart."""
    carbon = outline_of(tmp_path, deck_carbon())
    assert (carbon["charter"], carbon["total"]) == ("carbon", 5)
    medical = outline_of(tmp_path, deck_med())
    assert (medical["charter"], medical["total"], medical["slides"][0]["slide_type"]) == ("medical", 6, "title")


def test_deck_outline_medical_wins_over_ei(tmp_path: Path) -> None:
    """A file holding both --med-teal and --ei-blue is medical."""
    page = '<html data-doc-type="presentation"><style>:root{--med-teal:#159984;--ei-blue:#003A8D}</style>'
    page += '<body><article class="slide" data-type="slide"></article></body></html>'
    assert outline_of(tmp_path, page)["charter"] == "medical"


def test_deck_outline_charter_marks(tmp_path: Path) -> None:
    """No mark is carbon, slide-cover-logos is ei, the html template mark is medical."""
    body = '<body><article class="slide" data-type="slide"></article></body></html>'
    bare = f'<html data-doc-type="presentation">{body}'
    assert outline_of(tmp_path, bare)["charter"] == "carbon"
    logos = f'<html data-doc-type="presentation"><body><div class="slide-cover-logos"></div>{body[6:]}'
    assert outline_of(tmp_path, logos)["charter"] == "ei"
    marked = f'<html data-doc-type="presentation" data-doc-template="medical">{body}'
    assert outline_of(tmp_path, marked)["charter"] == "medical"


def test_deck_outline_non_presentation_charters(tmp_path: Path) -> None:
    """Website, mail, doc-ei and unknown templates map to their keys."""
    site = outline_of(tmp_path, (BOOTSTRAP / "website-empty.html").read_text(encoding="utf-8"))
    assert (site["charter"], site["doc_type"], site["total"]) == ("website", "website", 0)
    mail = outline_of(tmp_path, (BOOTSTRAP / "mail-empty.html").read_text(encoding="utf-8"))
    assert (mail["charter"], mail["doc_type"]) == ("mail", "document")
    ei = doc_perso().replace('data-doc-template="perso"', 'data-doc-template="ei"')
    assert outline_of(tmp_path, ei)["charter"] == "doc-ei"
    odd = doc_perso().replace('data-doc-template="perso"', 'data-doc-template="zzz"')
    assert outline_of(tmp_path, odd)["charter"] == "doc"


def test_deck_outline_doc_type_without_attribute(tmp_path: Path) -> None:
    """Without a usable data-doc-type, slides decide."""
    slide = '<article class="slide" data-type="slide" data-title="T"></article>'
    assert outline_of(tmp_path, f"<html><body>{slide}</body></html>")["doc_type"] == "presentation"
    assert outline_of(tmp_path, "<html><body><p>x</p></body></html>")["doc_type"] == "document"


def test_deck_outline_words_exclude_script_svg_comments_attributes(tmp_path: Path) -> None:
    """Only visible text nodes count."""
    slide = (
        '<article data-type="slide" data-title="a b c"><p>one two</p><script>x y z</script>'
        "<svg><text>q r</text></svg><!-- c d --></article>"
    )
    data = outline_of(tmp_path, f'<html data-doc-type="presentation"><body>{slide}</body></html>')
    assert data["slides"][0]["words"] == 2


def test_deck_outline_slide_ids(tmp_path: Path) -> None:
    """The id is data-id, else id, else slide-<index>."""
    slides = '<article data-type="slide" data-id="d" id="x"></article>'
    slides += '<article data-type="slide" id="s"></article><article data-type="slide"></article>'
    data = outline_of(tmp_path, f'<html data-doc-type="presentation"><body>{slides}</body></html>')
    assert [s["id"] for s in data["slides"]] == ["d", "s", "slide-2"]
    assert [s["slide_type"] for s in data["slides"]] == ["", "", ""]


def test_deck_outline_file_not_found() -> None:
    """A missing file is one line on stderr, nothing on stdout, status 1."""
    assert run_cli("outline", "ghost.html") == ("", "error: File not found: ghost.html\n", 1)


def test_deck_outline_not_utf8(tmp_path: Path) -> None:
    """Invalid UTF-8 is reported by name."""
    bad = tmp_path / "bad.html"
    bad.write_bytes(b"\xff\xfe")
    assert run_cli("outline", str(bad)) == ("", f"error: File is not valid UTF-8: {bad}\n", 1)


def test_deck_import_does_not_load_pptx() -> None:
    """Importing the deck package stays cheap."""
    code = "import sys, mcp_htmleditor.deck; sys.exit(1 if 'pptx' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0  # noqa: S603
