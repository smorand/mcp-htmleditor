"""Painted PPTX export of every presentation (SPEC-0024 FR-1 to FR-5, FR-7, FR-10): charter agnostic, browser based."""

from __future__ import annotations

import io
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from mcp_htmleditor.export.to_pptx import to_pptx
from tests.conftest import needs_chromium

REPO = Path(__file__).resolve().parents[1]
PAINTER = REPO / "src" / "mcp_htmleditor" / "export"
CHARTER_KEYS = re.compile(r"\b(breathe|med-|ei-|ibm-|cds-)", re.IGNORECASE)
PX = 12700
SLIDES = REPO / "templates" / "reference" / "slides"

DECK = """<!DOCTYPE html><html lang="en" data-doc-type="presentation"><head><meta charset="utf-8"><title>t</title>
<style>
body{margin:0;font-family:Arial,sans-serif}
section[data-type="slide"]{width:960px;height:540px;position:relative;background:#fff;overflow:hidden}
.card{position:absolute;left:40px;top:40px;width:300px;height:120px;border-radius:16px;border:3px solid #0a5;
 background:linear-gradient(90deg,#fde,#def);box-shadow:0 6px 12px rgba(0,0,0,.3);opacity:.9;padding:10px;
 box-sizing:border-box}
.dot{position:absolute;left:380px;top:40px;width:80px;height:80px;border-radius:50%;background:#e33}
ul{position:absolute;left:40px;top:190px;width:300px;margin:0;padding-left:24px;font-size:16px}
ul li::marker{color:#c00}
ol{position:absolute;left:360px;top:190px;width:250px;margin:0;font-size:16px}
.dash{list-style:none;position:absolute;left:40px;top:290px;margin:0;padding-left:20px;font-size:16px}
.dash li{position:relative}
.dash li::before{content:"\\2014";position:absolute;left:-20px;color:#f60}
code{background:#eee;border-radius:4px;padding:1px 5px;font-family:monospace}
.chips{position:absolute;left:40px;top:340px;font-size:16px}
table{position:absolute;left:480px;top:40px;border-collapse:collapse;font-size:14px}
td,th{border:1px solid #333;padding:6px 10px}th{background:#123;color:#fff}
.photo{position:absolute;left:40px;top:400px;width:100px;height:100px;object-fit:cover}
svg{position:absolute;left:300px;top:400px}
.band{position:absolute;left:600px;top:300px;width:300px;height:150px;
 background:linear-gradient(135deg,#102030 0%,#304050 100%);color:#fff;padding:12px;box-sizing:border-box}
</style></head><body>
<section data-type="slide" data-id="s1" data-title="One">
<div class="card"><b>Card</b> with <i>style</i></div><div class="dot"></div>
<ul><li>First <b>bold</b> item</li><li>Second item that is long enough to wrap onto a second line for sure ok</li></ul>
<ol start="3"><li>Third</li><li>Fourth</li></ol>
<ul class="dash"><li>Dashed one</li></ul>
<p class="chips">Run <code>inline code</code> and <span style="color:#0a0">green</span> text</p>
<table><tr><th colspan="2">Head</th><th>H3</th></tr><tr><td rowspan="2">A</td><td>B</td><td>C</td></tr>
<tr><td>D</td><td>E</td></tr></table>
<img class="photo" src="wide.png" alt="">
<svg width="120" height="80" viewBox="0 0 120 80"><rect width="120" height="80" fill="#36f"/>
<text x="10" y="40" fill="#fff">vec</text></svg>
<div class="band">Dark band</div>
<aside data-role="speaker-notes">note text</aside>
</section></body></html>"""


@pytest.fixture(scope="module")
def painted(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Presentation]:
    """The generic deck (no charter at all) exported once with the browser."""
    folder = tmp_path_factory.mktemp("generic")
    buffer = io.BytesIO()
    Image.new("RGB", (200, 100), (200, 30, 30)).save(buffer, "PNG")
    (folder / "wide.png").write_bytes(buffer.getvalue())
    deck = folder / "g.html"
    deck.write_text(DECK, encoding="utf-8")
    report = to_pptx(str(deck), str(folder / "g.pptx"))
    assert report.warnings == []
    yield Presentation(str(folder / "g.pptx"))


def test_painter_modules_name_no_charter() -> None:
    """FR-1: the painter carries no per charter code, not even a charter class or token name."""
    for path in sorted(PAINTER.glob("pptx_paint*.py")):
        found = CHARTER_KEYS.findall(path.read_text(encoding="utf-8"))
        assert found == [], f"{path.name} names a charter: {found}"


def _shapes(presentation: Presentation) -> list[Any]:
    return list(presentation.slides[0].shapes)


def _texts(shapes: list[Any]) -> dict[str, Any]:
    return {s.text_frame.text: s for s in shapes if s.has_text_frame and s.text_frame.text}


@needs_chromium
def test_text_is_editable_with_runs(painted: Presentation) -> None:
    """FR-2: bold, italic and colour runs survive inside one editable text box per block."""
    texts = _texts(_shapes(painted))
    card = texts["Card with style"]
    runs = [(r.text, r.font.bold, r.font.italic) for r in card.text_frame.paragraphs[0].runs]
    assert ("Card", True, False) in runs
    assert any(text.strip() == "style" and italic for text, _, italic in runs)
    green = next(s for t, s in texts.items() if t.endswith("green text"))
    colours = {str(r.font.color.rgb) for p in green.text_frame.paragraphs for r in p.runs}
    assert "00AA00" in colours


@needs_chromium
def test_lists_have_real_markers(painted: Presentation) -> None:
    """FR-2: a hanging indent, the marker colour, numbers from ``start`` and a generated dash marker."""
    shapes = _shapes(painted)
    texts = _texts(shapes)
    first = texts["First bold item"].text_frame.paragraphs[0]._p.pPr
    assert first.find(qn("a:buChar")).get("char") == "\u2022"
    assert first.find(qn("a:buClr")).find(qn("a:srgbClr")).get("val") == "CC0000"
    assert int(first.get("marL")) > 0 > int(first.get("indent"))
    wrapped = next(s for t, s in texts.items() if t.startswith("Second item"))
    assert len(wrapped.text_frame.paragraphs) == 2
    second_line = wrapped.text_frame.paragraphs[1]._p.pPr
    assert second_line.find(qn("a:buNone")) is not None  # the wrapped line has no marker, same indent
    assert second_line.get("marL") == first.get("marL")
    third = texts["Third"].text_frame.paragraphs[0]._p.pPr.find(qn("a:buAutoNum"))
    assert (third.get("type"), third.get("startAt")) == ("arabicPeriod", "3")
    assert texts["Fourth"].text_frame.paragraphs[0]._p.pPr.find(qn("a:buAutoNum")).get("startAt") == "4"
    assert "\u2014" in texts  # the ::before dash is a text box of its own


@needs_chromium
def test_boxes_rounded_gradient_shadow_opacity(painted: Presentation) -> None:
    """FR-3: rounded rectangle with its adjustment, gradient fill, outer shadow, border, alpha, ellipse."""
    shapes = _shapes(painted)
    card = next(s for s in shapes if s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and "Rounded" in s.name)
    assert 0.1 < card.adjustments[0] < 0.2  # 16 px of a 120 px side
    properties = card._element.spPr
    gradient = properties.find(qn("a:gradFill"))
    assert gradient is not None
    assert len(gradient.find(qn("a:gsLst"))) == 2
    assert properties.find(qn("a:effectLst")).find(qn("a:outerShdw")) is not None
    assert properties.find(qn("a:ln")).get("w") == str(3 * PX)
    assert gradient.find(qn("a:gsLst"))[0].find(qn("a:srgbClr")).find(qn("a:alpha")).get("val") == "90000"
    assert any(s.name.startswith("Oval") for s in shapes)


@needs_chromium
def test_inline_code_becomes_a_rounded_chip(painted: Presentation) -> None:
    """FR-2: the code span background is a rounded rectangle under the text."""
    rounded = [s for s in _shapes(painted) if "Rounded" in s.name]
    assert len(rounded) >= 2  # the card and the chip
    chip = min(rounded, key=lambda s: s.width)
    assert chip.height / PX < 30


@needs_chromium
def test_table_is_native_with_spans(painted: Presentation) -> None:
    """FR-5: one native table, header cell spanning two columns, a cell spanning two rows, borders, fills."""
    tables = [s for s in _shapes(painted) if s.has_table]
    assert len(tables) == 1
    table = tables[0].table
    assert (len(table.rows), len(table.columns)) == (3, 3)
    assert table.cell(0, 0).is_merge_origin and table.cell(0, 0).span_width == 2
    assert table.cell(1, 0).is_merge_origin and table.cell(1, 0).span_height == 2
    assert [table.cell(0, 0).text, table.cell(0, 2).text, table.cell(2, 2).text] == ["Head", "H3", "E"]
    header = table.cell(0, 0)._tc.tcPr
    assert header.find(qn("a:solidFill")).find(qn("a:srgbClr")).get("val") == "112233"
    assert header.find(qn("a:lnL")).get("w") == str(PX)
    run = header.getparent().find(qn("a:txBody")).find(qn("a:p")).find(qn("a:r")).find(qn("a:rPr"))
    assert run.find(qn("a:solidFill")).find(qn("a:srgbClr")).get("val") == "FFFFFF"


@needs_chromium
def test_pictures_crop_and_rasterised_vectors(painted: Presentation) -> None:
    """FR-4: object-fit cover crops a 2:1 picture in a square; the svg is a picture with its words as alt text."""
    pictures = [s for s in _shapes(painted) if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pictures) == 2
    photo = next(p for p in pictures if round(p.width / PX) == 100)
    assert (round(photo.crop_left, 2), round(photo.crop_right, 2), photo.crop_top) == (0.25, 0.25, 0)
    figure = next(p for p in pictures if round(p.width / PX) == 120)
    assert figure._element.nvPicPr.cNvPr.get("descr") == "vec"


@needs_chromium
def test_gradient_box_and_notes(painted: Presentation) -> None:
    """FR-3 and FR-7: the dark band keeps its gradient and light text; the speaker notes reach the notes page."""
    shapes = _shapes(painted)
    band = next(s for s in shapes if s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and s.width / PX == 300)
    assert band._element.spPr.find(qn("a:gradFill")).find(qn("a:lin")).get("ang") == str(45 * 60000)
    assert painted.slides[0].notes_slide.notes_text_frame.text == "note text"
    assert (round(painted.slide_width / 914400, 3), round(painted.slide_height / 914400, 3)) == (13.333, 7.5)
    assert all(s.shape_type != MSO_SHAPE_TYPE.TEXT_BOX or "note" not in s.text_frame.text for s in shapes)


def _words(slide: Any) -> set[str]:
    found: set[str] = set()
    for shape in slide.shapes:
        if shape.has_text_frame:
            found |= set(re.findall(r"\w+", shape.text_frame.text.casefold()))
        if shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    found |= set(re.findall(r"\w+", cell.text.casefold()))
    return found


FAMILIES = [
    ("carbon", "ibm-carbon.html", 0.9),
    ("carbon-complete", "example-carbon-complete.html", 0.9),
    ("ei", "euro-information.html", 0.5),
    ("medical", "medical.html", 0.8),
    ("standard", "presentation-standard.html", 0.9),
]


@needs_chromium
@pytest.mark.parametrize(("family", "name", "ratio"), FAMILIES, ids=[f[0] for f in FAMILIES])
def test_every_charter_family_is_painted(tmp_path: Path, family: str, name: str, ratio: float) -> None:
    """FR-1: each template deck is painted: slides kept in order, text present and editable, shapes, fills."""
    source = SLIDES / name
    report = to_pptx(str(source), str(tmp_path / f"{family}.pptx"))
    assert [w for w in report.warnings if "finish" in w] == []
    soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
    articles = list(soup.find_all(attrs={"data-type": "slide"}))
    slides = list(Presentation(str(tmp_path / f"{family}.pptx")).slides)
    assert len(slides) == len(articles) == report.slide_count
    editable = shapes = 0
    for slide, article in zip(slides, articles, strict=True):
        for aside in article.select('[data-role="speaker-notes"]'):
            aside.decompose()
        title = article.find(["h1", "h2"])
        if title is not None:
            assert set(re.findall(r"\w+", title.get_text(" ").casefold())) <= _words(slide), title.get_text()
        frames = [s for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip()]
        assert frames, "a slide without any editable text"
        assert any(r.font.size for f in frames for p in f.text_frame.paragraphs for r in p.runs)
        shapes += len(slide.shapes)
        editable += sum(1 for s in slide.shapes if s.shape_type != MSO_SHAPE_TYPE.PICTURE)
    assert editable / shapes >= ratio, (editable, shapes)


@needs_chromium
def test_standard_cover_shows_its_gradient(tmp_path: Path) -> None:
    """FR-10: the cover and closing gradients of presentation-standard are in the slide (and in the HTML)."""
    html = (SLIDES / "presentation-standard.html").read_text(encoding="utf-8")
    assert re.search(r"section\[data-type=\"slide\"\]\s*\{[^}]*background-color:\s*white", html)
    assert not re.search(r"section\[data-type=\"slide\"\]\s*\{[^}]*[^-]background:\s*white", html)
    to_pptx(str(SLIDES / "presentation-standard.html"), str(tmp_path / "s.pptx"))
    cover, *_, closing = Presentation(str(tmp_path / "s.pptx")).slides
    for slide in (cover, closing):
        assert any(s._element.spPr.find(qn("a:gradFill")) is not None for s in slide.shapes if s.shape_type == 1)
        light = {
            str(r.font.color.rgb)
            for s in slide.shapes
            if s.has_text_frame
            for p in s.text_frame.paragraphs
            for r in p.runs
        }
        assert "FFFFFF" in light


@needs_chromium
def test_medical_lists_and_rounded_shapes(tmp_path: Path) -> None:
    """FR-2 and FR-3 on a real charter deck: the medical reference holds rounded shapes and list text boxes."""
    to_pptx(str(SLIDES / "medical.html"), str(tmp_path / "m.pptx"))
    names = [s.name for slide in Presentation(str(tmp_path / "m.pptx")).slides for s in slide.shapes]
    assert any(n.startswith("Rounded") for n in names)
    assert any(n.startswith("Oval") for n in names)


def test_degraded_flow_build_for_any_charter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-8: without the render extra every charter keeps the flow slides and one warning naming the reason."""
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    for name in ("slides-empty.html", "slides-medical-empty.html", "slides-ei-empty.html"):
        source = REPO / "templates" / "bootstrap" / name
        report = to_pptx(str(source), str(tmp_path / f"{name}.pptx"))
        assert report.warnings == [
            "Deck exported without the rendered finish (the render extra is not installed). "
            "Install the browser with: make install-browser"
        ]
        assert report.slide_count == 1
        slide = Presentation(str(tmp_path / f"{name}.pptx")).slides[0]
        assert any(s.has_text_frame and s.text_frame.text.strip() for s in slide.shapes)


def test_paint_false_is_the_flow_build(tmp_path: Path) -> None:
    """``paint=False`` never starts a browser and gives the flow build (the golden test relies on it)."""
    report = to_pptx(str(REPO / "templates" / "bootstrap" / "slides-empty.html"), str(tmp_path / "f.pptx"), paint=False)
    assert report.warnings == []
