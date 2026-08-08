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

from mcp_htmleditor.export import docx_header_footer as hf
from mcp_htmleditor.export import reference_docx as ref
from mcp_htmleditor.export.to_docx import (
    detect_charter,
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

# The Euro-Information charter draws its letterhead in the page flow: those two
# blocks are what the Word header and footer replace.
EI_HTML = """<!DOCTYPE html>
<html lang="fr" data-doc-type="document">
<head><meta charset="UTF-8" /><title>Onglet</title></head>
<body>
  <article data-type="document" data-doc-template="ei">
    <div class="ei-doc-head">
      <div class="ei-doc-logo"><img src="data:image/png;base64,AAAA" alt="Euro Information" /></div>
      <div class="ei-doc-brand" data-editable="text">Euro-Information</div>
    </div>
    <div class="ei-doc-body">
      <h1 class="doc-title" data-editable="text">Note de cadrage</h1>
      <p class="doc-subtitle" data-editable="text">Secteur H, aout 2026</p>
      <h1 class="doc-h1">1. Objet</h1>
      <p>Un paragraphe.</p>
    </div>
    <div class="ei-doc-foot">
      <span data-editable="text">Euro-Information</span>
      <span data-editable="text">Confidentiel</span>
    </div>
  </article>
</body>
</html>
"""

MINIMAL_DOCUMENT = (
    '<?xml version="1.0" encoding="utf-8"?>'
    f'<w:document xmlns:w="{W}" xmlns:r="{ref.R_NS}"><w:body><w:p /><w:sectPr>'
    '<w:footnotePr><w:numRestart w:val="eachSect" /></w:footnotePr>'
    "</w:sectPr></w:body></w:document>"
).encode()

MINIMAL_RELS = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Type="x" Id="rId1" Target="styles.xml" /></Relationships>'
)

MINIMAL_CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="xml" ContentType="application/xml" /></Types>'
)

BARE = ref.Charter(key="bare", label="Bare", font="Arial", body_size_pt=11)

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


def _sectpr_tags(document_xml: bytes) -> list[str]:
    """Return the w:-tag names inside the w:sectPr, in document order.

    Nested tags are included; assertions therefore compare relative positions
    rather than the exact list.
    """
    block = re.search(r"<w:sectPr\b[^>]*>(.*)</w:sectPr>", document_xml.decode("utf-8"), re.S)
    assert block is not None
    return re.findall(r"<w:(\w+)", block.group(1))


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
        key="test",
        label="Test",
        font="Arial",
        body_size_pt=11,
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


# ── repeated Word header and footer ───────────────────────────────────────────


def test_charters_declare_the_letterhead_they_can_reproduce() -> None:
    """Only the charters that ship a Word header or footer say so."""
    assert ref.EI.has_page_furniture is True
    assert ref.PERSO.has_page_furniture is True
    assert BARE.has_page_furniture is False
    assert ref.has_page_furniture("ei") is True
    assert ref.has_page_furniture("EI") is True
    assert ref.has_page_furniture("perso") is True
    assert ref.has_page_furniture("acme") is False
    assert ref.has_page_furniture(None) is False


def test_ei_charter_builds_a_header_a_footer_and_a_logo() -> None:
    """The Euro-Information charter injects the four letterhead parts."""
    parts = ref.page_furniture_parts(ref.EI)

    assert set(parts) == {hf.HEADER_PART, hf.FOOTER_PART, hf.HEADER_RELS_PART, hf.LOGO_PART}
    assert parts[hf.LOGO_PART].startswith(b"\x89PNG\r\n")
    assert b"Euro-Information" in parts[hf.HEADER_PART]
    assert f'r:embed="{hf.LOGO_REL_ID}"'.encode() in parts[hf.HEADER_PART]
    assert b'w:color="003A8D"' in parts[hf.HEADER_PART]  # blue rule and brand
    assert b'w:color="FBAE40"' in parts[hf.HEADER_PART]  # orange rule
    assert b"media/header-logo.png" in parts[hf.HEADER_RELS_PART]


def test_perso_charter_builds_a_footer_only() -> None:
    """The Perso charter has no letterhead, so no header part is produced."""
    parts = ref.page_furniture_parts(ref.PERSO)

    assert set(parts) == {hf.FOOTER_PART}
    assert b'w:jc w:val="center"' in parts[hf.FOOTER_PART]


def test_a_charter_without_letterhead_builds_no_part() -> None:
    """A charter with neither header nor footer injects nothing."""
    assert ref.page_furniture_parts(BARE) == {}


def test_the_page_number_is_a_dynamic_word_field() -> None:
    """The footer holds a real PAGE field, not a frozen number."""
    footer = ref.page_furniture_parts(ref.EI)[hf.FOOTER_PART].decode()

    assert '<w:instrText xml:space="preserve"> PAGE </w:instrText>' in footer
    assert 'w:fldCharType="begin"' in footer
    assert 'w:fldCharType="separate"' in footer
    assert 'w:fldCharType="end"' in footer
    # The document title comes from a field too, so it follows the real title.
    assert '<w:instrText xml:space="preserve"> TITLE </w:instrText>' in footer


def test_the_ei_footer_splits_title_and_page_number_on_a_tab_stop() -> None:
    """The split layout aligns the page number on the right text edge."""
    footer = ref.page_furniture_parts(ref.EI)[hf.FOOTER_PART].decode()
    page = ref.EI.page
    assert page is not None

    assert f'<w:tab w:val="right" w:pos="{page.content_width}" />' in footer
    assert "<w:tab />" in footer
    assert 'w:jc w:val="center"' not in footer


def test_header_and_footer_parts_are_well_formed_xml() -> None:
    """Both parts parse, so Word will not reject the archive."""
    for content in ref.page_furniture_parts(ref.EI).values():
        if content.startswith(b"<?xml"):
            ET.fromstring(content)


def test_patch_document_xml_references_the_letterhead_in_schema_order() -> None:
    """References come first, page geometry last, footnotePr untouched between."""
    patched = ref.patch_document_xml(MINIMAL_DOCUMENT, ref.EI)
    tags = _sectpr_tags(patched)

    assert tags.index("headerReference") < tags.index("footerReference") < tags.index("footnotePr")
    assert tags.index("footnotePr") < tags.index("pgSz") < tags.index("pgMar")
    assert f'r:id="{hf.HEADER_REL_ID}"'.encode() in patched
    assert f'r:id="{hf.FOOTER_REL_ID}"'.encode() in patched
    assert b'w:w="11906"' in patched


def test_patch_document_xml_omits_the_header_reference_for_perso() -> None:
    """A charter without a header gets a footer reference only."""
    tags = _sectpr_tags(ref.patch_document_xml(MINIMAL_DOCUMENT, ref.PERSO))

    assert "headerReference" not in tags
    assert "footerReference" in tags


def test_patch_document_xml_expands_a_self_closing_sectpr() -> None:
    """A reference document with an empty w:sectPr is still usable."""
    document = MINIMAL_DOCUMENT.replace(
        b'<w:sectPr><w:footnotePr><w:numRestart w:val="eachSect" /></w:footnotePr></w:sectPr>',
        b"<w:sectPr />",
    )

    patched = ref.patch_document_xml(document, ref.EI)

    ET.fromstring(patched)
    assert _sectpr_tags(patched)[:2] == ["headerReference", "footerReference"]


def test_patch_document_xml_rejects_a_document_without_section_properties() -> None:
    """A missing w:sectPr is reported instead of producing a broken archive."""
    with pytest.raises(ValueError, match="w:sectPr"):
        ref.patch_document_xml(b"<w:document><w:body /></w:document>", ref.EI)


def test_patch_document_rels_declares_the_header_and_footer() -> None:
    """Both relationships are appended, keeping the existing ones."""
    patched = ref.patch_document_rels_xml(MINIMAL_RELS, ref.EI).decode()

    assert f'Id="{hf.HEADER_REL_ID}"' in patched
    assert f'Id="{hf.FOOTER_REL_ID}"' in patched
    assert 'Target="header1.xml"' in patched
    assert 'Target="styles.xml"' in patched
    ET.fromstring(patched)


def test_patch_content_types_declares_the_injected_parts() -> None:
    """Header, footer and PNG media get their content type."""
    patched = ref.patch_content_types_xml(MINIMAL_CONTENT_TYPES, ref.EI).decode()

    assert f'PartName="/{hf.HEADER_PART}"' in patched
    assert f'PartName="/{hf.FOOTER_PART}"' in patched
    assert 'Extension="png"' in patched
    ET.fromstring(patched)


def test_patch_content_types_leaves_a_bare_charter_alone() -> None:
    """A charter with no injected part does not touch the content types."""
    assert ref.patch_content_types_xml(MINIMAL_CONTENT_TYPES, BARE) == MINIMAL_CONTENT_TYPES
    assert ref.patch_document_rels_xml(MINIMAL_RELS, BARE) == MINIMAL_RELS


# ── letterhead blocks removed from the body ───────────────────────────────────


def test_preprocess_keeps_the_letterhead_blocks_by_default() -> None:
    """Without a Word letterhead the decorative blocks must stay in the body.

    This is the fallback path: if the reference document could not be built, the
    information is still exported, in the body, as before.
    """
    prepared = preprocess_html(EI_HTML)

    assert 'class="ei-doc-head"' in prepared.html
    assert 'class="ei-doc-foot"' in prepared.html
    assert prepared.stripped_furniture == 0


def test_preprocess_drops_the_letterhead_blocks_when_asked() -> None:
    """With a Word letterhead the decorative blocks leave the body."""
    prepared = preprocess_html(EI_HTML, strip_page_furniture=True)

    assert 'class="ei-doc-head"' not in prepared.html
    assert 'class="ei-doc-foot"' not in prepared.html
    assert "Confidentiel" not in prepared.html
    assert prepared.stripped_furniture == 2
    # The document itself is untouched.
    assert "1. Objet" in prepared.html
    assert prepared.title == "Note de cadrage"


def test_detect_charter_reads_the_key_without_preprocessing() -> None:
    """The charter is known before the HTML is rewritten."""
    assert detect_charter(EI_HTML) == "ei"
    assert detect_charter(CHARTER_HTML) == "perso"
    assert detect_charter(PLAIN_HTML) is None


# ── end-to-end letterhead ─────────────────────────────────────────────────────


@needs_pandoc
def test_reference_docx_carries_a_header_and_a_footer_for_ei(monkeypatch, tmp_path: Path) -> None:
    """The generated Euro-Information reference document holds the letterhead."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))

    reference = ref.reference_docx_for("ei")

    assert reference is not None
    with zipfile.ZipFile(reference) as archive:
        names = set(archive.namelist())
        document = archive.read(ref.DOCUMENT_PART).decode()
        footer = archive.read(hf.FOOTER_PART).decode()
    assert hf.HEADER_PART in names
    assert hf.FOOTER_PART in names
    assert hf.LOGO_PART in names
    assert hf.HEADER_RELS_PART in names
    assert "headerReference" in document
    assert "footerReference" in document
    assert " PAGE " in footer


@needs_pandoc
def test_reference_docx_carries_a_footer_only_for_perso(monkeypatch, tmp_path: Path) -> None:
    """The Perso reference document has a page number but no header."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))

    reference = ref.reference_docx_for("perso")

    assert reference is not None
    with zipfile.ZipFile(reference) as archive:
        names = set(archive.namelist())
        document = archive.read(ref.DOCUMENT_PART).decode()
    assert hf.HEADER_PART not in names
    assert hf.FOOTER_PART in names
    assert "headerReference" not in document
    assert "footerReference" in document


@needs_pandoc
def test_to_docx_repeats_the_ei_letterhead_and_drops_it_from_the_body(monkeypatch, tmp_path: Path) -> None:
    """Pandoc carries the header and footer over; the body loses the duplicates."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    source = tmp_path / "doc.html"
    source.write_text(EI_HTML, encoding="utf-8")
    output = tmp_path / "doc.docx"

    result = to_docx(str(source), str(output))

    assert result.charter == "ei"
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        document = archive.read("word/document.xml").decode()
    assert hf.HEADER_PART in names
    assert hf.FOOTER_PART in names
    assert hf.LOGO_PART in names
    assert "headerReference" in document
    assert "footerReference" in document
    # The letterhead is no longer body content.
    assert "Confidentiel" not in document
    assert "1. Objet" in document


@needs_pandoc
def test_to_docx_keeps_the_letterhead_in_the_body_without_a_reference(monkeypatch, tmp_path: Path) -> None:
    """A reference document that cannot be built must not cost information."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("mcp_htmleditor.export.to_docx.reference_docx_for", lambda key: None)
    source = tmp_path / "doc.html"
    source.write_text(EI_HTML, encoding="utf-8")
    output = tmp_path / "doc.docx"

    result = to_docx(str(source), str(output))

    assert result.reference_docx is None
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        document = archive.read("word/document.xml").decode()
    assert hf.HEADER_PART not in names
    assert "Confidentiel" in document


@needs_pandoc
def test_to_docx_without_charter_gains_no_letterhead(monkeypatch, tmp_path: Path) -> None:
    """Non-regression: the standard charter keeps the plain pandoc section."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", str(tmp_path))
    source = tmp_path / "plain.html"
    source.write_text(PLAIN_HTML, encoding="utf-8")
    output = tmp_path / "plain.docx"

    to_docx(str(source), str(output))

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        document = archive.read("word/document.xml").decode()
    assert hf.HEADER_PART not in names
    assert hf.FOOTER_PART not in names
    assert "headerReference" not in document
    assert "footerReference" not in document
    assert "pgSz" not in document
