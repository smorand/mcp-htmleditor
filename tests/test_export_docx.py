"""Tests for the DOCX export: title deduplication, charter, diagnostics.

The pure helpers (HTML preprocessing, SVG detection, styles patching) are tested
without pandoc. The end-to-end cases that really run pandoc are skipped when
pandoc is not installed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from mcp_htmleditor.export import reference_docx as ref
from mcp_htmleditor.export.to_docx import (
    pandoc_warnings,
    preprocess_html,
    svg_warnings,
    to_docx,
)

pytest_plugins: tuple[str, ...] = ()

HAS_PANDOC = shutil.which("pandoc") is not None
needs_pandoc = pytest.mark.skipif(not HAS_PANDOC, reason="pandoc is not installed")

W = ref.W_NS

CHARTER_HTML = """<!DOCTYPE html>
<html lang="fr" data-doc-type="document">
<head><meta charset="UTF-8" /><title>Titre de l'onglet</title></head>
<body>
  <article data-type="document" data-doc-template="perso">
    <h1 class="doc-title" data-editable="text">Bilan technique</h1>
    <p class="doc-subtitle" data-editable="text">Sebastien Morand, version 1.4</p>
    <h1 class="doc-h1">1. Contexte</h1>
    <p>Un paragraphe.</p>
    <h2 class="doc-h2">1.1 Detail</h2>
    <p>Un autre paragraphe.</p>
  </article>
</body>
</html>
"""

PLAIN_HTML = """<!DOCTYPE html>
<html data-doc-type="document">
<head><title>Rapport standard</title></head>
<body><article data-type="document"><h1>Titre du rapport</h1><p>Corps.</p></article></body>
</html>
"""

MINIMAL_STYLES = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    f'<w:styles xmlns:w="{W}">'
    "<w:docDefaults><w:rPrDefault><w:rPr>"
    '<w:rFonts w:asciiTheme="minorHAnsi" w:hAnsiTheme="minorHAnsi" w:cstheme="minorBidi" />'
    '<w:sz w:val="24" /><w:szCs w:val="24" />'
    '<w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA" />'
    "</w:rPr></w:rPrDefault></w:docDefaults>"
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title" />'
    '<w:pPr><w:spacing w:after="80" /><w:contextualSpacing /></w:pPr>'
    '<w:rPr><w:rFonts w:asciiTheme="majorHAnsi" /><w:i /><w:sz w:val="56" /></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle" />'
    '<w:basedOn w:val="Title" /><w:rPr><w:sz w:val="28" /></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1" />'
    '<w:pPr><w:keepNext /><w:spacing w:before="360" /><w:outlineLvl w:val="0" /></w:pPr>'
    '<w:rPr><w:color w:val="0F4761" w:themeColor="accent1" /><w:sz w:val="40" /></w:rPr></w:style>'
    '<w:style w:type="table" w:styleId="Table"><w:name w:val="Table" />'
    '<w:tblStylePr w:type="firstRow"><w:tcPr><w:vAlign w:val="bottom" /></w:tcPr></w:tblStylePr>'
    "</w:style>"
    "</w:styles>"
).encode()


def _paragraphs(docx: Path) -> list[tuple[str, str]]:
    """Return the (style, text) pairs of every paragraph of a DOCX."""
    with zipfile.ZipFile(docx) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    pairs: list[tuple[str, str]] = []
    for block in re.findall(r"<w:p>(.*?)</w:p>", document, re.S):
        style = re.search(r'w:pStyle w:val="([^"]+)"', block)
        text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", block, re.S))
        pairs.append((style.group(1) if style else "", text))
    return pairs


def _style(root: ET.Element, style_id: str) -> ET.Element:
    """Return the ``w:style`` element with the given id (must exist)."""
    for style in root.findall(f"{{{W}}}style"):
        if style.get(f"{{{W}}}styleId") == style_id:
            return style
    raise AssertionError(f"style {style_id} missing")


def _run_prop(root: ET.Element, style_id: str, tag: str) -> str | None:
    """Return the ``w:val`` of a run property of a style, or None."""
    node = _style(root, style_id).find(f"{{{W}}}rPr/{{{W}}}{tag}")
    return None if node is None else node.get(f"{{{W}}}val")


# ── HTML preprocessing: single title ──────────────────────────────────────────


def test_preprocess_lifts_title_and_subtitle_out_of_the_body() -> None:
    """.doc-title / .doc-subtitle become metadata and leave the body."""
    prepared = preprocess_html(CHARTER_HTML)

    assert prepared.title == "Bilan technique"
    assert prepared.subtitle == "Sebastien Morand, version 1.4"
    assert 'class="doc-title"' not in prepared.html
    assert 'class="doc-subtitle"' not in prepared.html
    assert "1. Contexte" in prepared.html


def test_preprocess_rewrites_the_head_title() -> None:
    """The browser tab title is realigned on the document title."""
    prepared = preprocess_html(CHARTER_HTML)

    assert "<title>Bilan technique</title>" in prepared.html
    assert "Titre de l'onglet" not in prepared.html


def test_preprocess_leaves_a_template_without_doc_title_untouched() -> None:
    """Templates without .doc-title keep their body h1 and get no metadata."""
    prepared = preprocess_html(PLAIN_HTML)

    assert prepared.title is None
    assert prepared.subtitle is None
    assert prepared.charter is None
    assert "<h1>Titre du rapport</h1>" in prepared.html


# ── charter detection ─────────────────────────────────────────────────────────


def test_preprocess_detects_the_charter_from_data_doc_template() -> None:
    """The charter key is read from data-doc-template on the article."""
    assert preprocess_html(CHARTER_HTML).charter == "perso"
    assert preprocess_html(CHARTER_HTML.replace('"perso"', '"ei"')).charter == "ei"


def test_charter_for_resolves_known_keys_only() -> None:
    """Unknown, empty and missing keys resolve to no charter."""
    assert ref.charter_for("perso") is ref.PERSO
    assert ref.charter_for("  EI  ") is ref.EI
    assert ref.charter_for("acme") is None
    assert ref.charter_for("") is None
    assert ref.charter_for(None) is None
    assert ref.charter_keys() == ("perso", "ei")


# ── SVG diagnostics ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ('<img src="figure.png" />', 0),
        ('<img src="schema.SVG" />', 1),
        ('<img src="schema.svg?v=2" />', 1),
        ('<img src="data:image/svg+xml;base64,AAAA" />', 1),
        ("<svg><rect /></svg>", 1),
        ('<img src="a.svg" /><img src="b.svg" />', 2),
    ],
)
def test_svg_warnings_flag_every_vector_figure(markup: str, expected: int) -> None:
    """Each SVG figure yields one warning recommending PNG."""
    prepared = preprocess_html(f"<html><body>{markup}</body></html>")

    assert len(prepared.warnings) == expected
    assert all("PNG" in warning for warning in prepared.warnings)


def test_svg_warnings_accepts_a_parsed_document() -> None:
    """svg_warnings works on an already parsed soup."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup('<img src="x.svg" />', "html.parser")

    assert len(svg_warnings(soup)) == 1


def test_pandoc_warnings_are_normalized_and_deduplicated() -> None:
    """Blank lines are dropped and repeated messages are reported once."""
    stderr = "[WARNING] Could not convert image\n\n[WARNING]   Could not convert image\n[INFO] ok\n"

    assert pandoc_warnings(stderr) == (
        "pandoc: [WARNING] Could not convert image",
        "pandoc: [INFO] ok",
    )


# ── reference.docx generation ─────────────────────────────────────────────────


def test_patch_styles_xml_applies_the_charter() -> None:
    """Fonts, sizes, colours, underline and alignment reach word/styles.xml."""
    root = ET.fromstring(ref.patch_styles_xml(MINIMAL_STYLES, ref.PERSO))

    defaults = root.find(f"{{{W}}}docDefaults/{{{W}}}rPrDefault/{{{W}}}rPr")
    assert defaults is not None
    fonts = defaults.find(f"{{{W}}}rFonts")
    assert fonts is not None
    assert fonts.get(f"{{{W}}}ascii") == "Arial"
    assert fonts.get(f"{{{W}}}asciiTheme") is None
    assert defaults.find(f"{{{W}}}sz") is not None

    assert _run_prop(root, "Title", "sz") == "44"
    assert _run_prop(root, "Title", "b") == "1"
    assert _run_prop(root, "Title", "u") == "single"
    assert _run_prop(root, "Title", "color") == "000000"
    assert _run_prop(root, "Heading1", "color") == "000000"
    # Styles the reference document does not declare are skipped, not created.
    declared = {style.get(f"{{{W}}}styleId") for style in root.findall(f"{{{W}}}style")}
    assert "Heading2" not in declared

    title_jc = _style(root, "Title").find(f"{{{W}}}pPr/{{{W}}}jc")
    assert title_jc is not None
    assert title_jc.get(f"{{{W}}}val") == "center"


def test_patch_styles_xml_cancels_inherited_traits() -> None:
    """Subtitle is based on Title, so bold and underline must be turned off."""
    root = ET.fromstring(ref.patch_styles_xml(MINIMAL_STYLES, ref.PERSO))

    assert _run_prop(root, "Subtitle", "b") == "0"
    assert _run_prop(root, "Subtitle", "u") == "none"
    assert _run_prop(root, "Subtitle", "color") == "666666"
    assert _run_prop(root, "Title", "i") == "0"  # pandoc italics dropped


def test_patch_styles_xml_keeps_the_document_language() -> None:
    """The language of the reference document is left untouched."""
    patched = ref.patch_styles_xml(MINIMAL_STYLES, ref.EI)

    assert b'w:lang w:val="en-US"' in patched


def test_patch_styles_xml_colours_the_table_header() -> None:
    """The table style gains the charter header fill, in schema order."""
    root = ET.fromstring(ref.patch_styles_xml(MINIMAL_STYLES, ref.EI))

    first_row = _style(root, "Table").find(f"{{{W}}}tblStylePr")
    assert first_row is not None
    shading = first_row.find(f"{{{W}}}tcPr/{{{W}}}shd")
    assert shading is not None
    assert shading.get(f"{{{W}}}fill") == "003A8D"
    cell_children = [child.tag.rsplit("}", 1)[-1] for child in first_row.find(f"{{{W}}}tcPr")]
    assert cell_children == ["shd", "vAlign"]
    assert [child.tag.rsplit("}", 1)[-1] for child in first_row] == ["rPr", "tcPr"]


def test_patch_styles_xml_inserts_alignment_in_schema_order() -> None:
    """w:jc must sit after w:spacing and before w:outlineLvl."""
    charter = ref.Charter(
        key="test", label="Test", font="Arial", body_size_pt=11,
        styles={"Heading1": ref.StyleSpec(18, align="center")},
    )
    root = ET.fromstring(ref.patch_styles_xml(MINIMAL_STYLES, charter))

    order = [child.tag.rsplit("}", 1)[-1] for child in _style(root, "Heading1").find(f"{{{W}}}pPr")]
    assert order == ["keepNext", "spacing", "jc", "outlineLvl"]


def test_patch_styles_xml_ignores_a_charter_without_table() -> None:
    """A charter with no table spec leaves the table style alone."""
    charter = ref.Charter(key="test", label="Test", font="Arial", body_size_pt=11)
    root = ET.fromstring(ref.patch_styles_xml(MINIMAL_STYLES, charter))

    assert _style(root, "Table").find(f"{{{W}}}tblStylePr/{{{W}}}rPr") is None


def test_reference_docx_for_returns_none_without_charter() -> None:
    """Standard and unknown charters export without a reference document."""
    assert ref.reference_docx_for(None) is None
    assert ref.reference_docx_for("acme") is None


def test_reference_docx_for_swallows_a_missing_pandoc(monkeypatch, tmp_path: Path) -> None:
    """A missing pandoc degrades to no reference document, not an exception."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))

    def boom(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("pandoc")

    monkeypatch.setattr(subprocess, "run", boom)

    assert ref.reference_docx_for("perso") is None


@needs_pandoc
def test_reference_docx_for_generates_and_caches(monkeypatch, tmp_path: Path) -> None:
    """The reference document is built once then served from the cache."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))

    first = ref.reference_docx_for("perso")
    assert first is not None
    assert first.parent == tmp_path / "reference"
    stamp = first.stat().st_mtime_ns

    second = ref.reference_docx_for("perso")
    assert second == first
    assert second is not None
    assert second.stat().st_mtime_ns == stamp

    with zipfile.ZipFile(first) as archive:
        styles = archive.read(ref.STYLES_PART)
    assert b'w:ascii="Arial"' in styles
    assert list(tmp_path.glob("reference/.*tmp")) == []


# ── end-to-end export ────────────────────────────────────────────────────────


@needs_pandoc
def test_to_docx_writes_the_title_once(monkeypatch, tmp_path: Path) -> None:
    """The document title is styled Title once and never duplicated as Heading1."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    source = tmp_path / "doc.html"
    source.write_text(CHARTER_HTML, encoding="utf-8")
    output = tmp_path / "doc.docx"

    result = to_docx(str(source), str(output))

    pairs = _paragraphs(output)
    titles = [text for style, text in pairs if style == "Title"]
    assert titles == ["Bilan technique"]
    assert [text for style, text in pairs if style == "Subtitle"] == ["Sebastien Morand, version 1.4"]
    assert all(text != "Bilan technique" for style, text in pairs if style == "Heading1")
    assert result.charter == "perso"
    assert result.reference_docx is not None


@needs_pandoc
def test_to_docx_carries_the_charter(monkeypatch, tmp_path: Path) -> None:
    """The exported DOCX embeds the charter styles, not the pandoc defaults."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    source = tmp_path / "doc.html"
    source.write_text(CHARTER_HTML, encoding="utf-8")
    output = tmp_path / "doc.docx"

    to_docx(str(source), str(output))

    with zipfile.ZipFile(output) as archive:
        styles = archive.read("word/styles.xml")
    root = ET.fromstring(styles)
    assert _run_prop(root, "Heading2", "color") == "1155CC"
    assert _run_prop(root, "Heading1", "u") == "single"
    assert b'w:ascii="Arial"' in styles


@needs_pandoc
def test_to_docx_without_charter_uses_pandoc_defaults(monkeypatch, tmp_path: Path) -> None:
    """A document with no data-doc-template exports without a reference."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    source = tmp_path / "plain.html"
    source.write_text(PLAIN_HTML, encoding="utf-8")
    output = tmp_path / "plain.docx"

    result = to_docx(str(source), str(output))

    assert result.charter is None
    assert result.reference_docx is None
    assert result.warnings == ()
    styles = {style for style, _ in _paragraphs(output)}
    assert "Heading1" in styles


@needs_pandoc
def test_to_docx_reports_an_unknown_charter(monkeypatch, tmp_path: Path) -> None:
    """An unknown charter falls back cleanly and says so."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    source = tmp_path / "doc.html"
    source.write_text(CHARTER_HTML.replace('"perso"', '"acme"'), encoding="utf-8")
    output = tmp_path / "doc.docx"

    result = to_docx(str(source), str(output))

    assert result.charter == "acme"
    assert result.reference_docx is None
    assert any("inconnue" in warning for warning in result.warnings)
    assert output.exists()


@needs_pandoc
def test_to_docx_reports_a_charter_that_could_not_be_built(monkeypatch, tmp_path: Path) -> None:
    """A known charter whose reference document cannot be built is reported."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("mcp_htmleditor.export.to_docx.reference_docx_for", lambda key: None)
    source = tmp_path / "doc.html"
    source.write_text(CHARTER_HTML, encoding="utf-8")
    output = tmp_path / "doc.docx"

    result = to_docx(str(source), str(output))

    assert result.reference_docx is None
    assert any("non appliquee" in warning for warning in result.warnings)


@needs_pandoc
def test_to_docx_warns_about_svg_figures(monkeypatch, tmp_path: Path) -> None:
    """An SVG figure is reported to the user with the PNG rule."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    source = tmp_path / "doc.html"
    source.write_text(
        '<html><head><title>t</title></head><body><article data-type="document">'
        '<p>Texte</p><img src="figure.svg" alt="f" /></article></body></html>',
        encoding="utf-8",
    )
    output = tmp_path / "doc.docx"

    result = to_docx(str(source), str(output))

    assert any("SVG" in warning and "PNG" in warning for warning in result.warnings)
