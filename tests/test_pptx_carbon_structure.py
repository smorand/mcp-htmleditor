"""Structural validity of the painted PPTX of the three Carbon files (SPEC-0024 phase 2b): fit for PowerPoint, not
only for LibreOffice. Reopened with python-pptx, geometry, duplicates, empty runs, XML child order, fonts."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from pptx import Presentation
from pptx.oxml.ns import qn

from mcp_htmleditor.export.to_pptx import to_pptx
from tests.conftest import needs_chromium

REPO = Path(__file__).resolve().parents[1]
CARBON = (
    REPO / "templates" / "bootstrap" / "slides-empty.html",
    REPO / "templates" / "reference" / "slides" / "ibm-carbon.html",
    REPO / "templates" / "reference" / "slides" / "example-carbon-complete.html",
)
PX = 12700
TOLERANCE = 1.0  # points
RPR_ORDER = ["ln", "noFill", "solidFill", "gradFill", "effectLst", "highlight", "uLnTx", "uLn", "uFillTx", "uFill",
             "latin", "ea", "cs", "sym", "hlinkClick"]  # fmt: skip
PPR_ORDER = ["lnSpc", "spcBef", "spcAft", "buClrTx", "buClr", "buSzTx", "buSzPct", "buFontTx", "buFont", "buNone",
             "buAutoNum", "buChar", "buBlip", "tabLst", "defRPr"]  # fmt: skip
TCPR_ORDER = ["lnL", "lnR", "lnT", "lnB", "lnTlToBr", "lnBlToTr", "cell3D", "noFill", "solidFill", "gradFill"]


def _names(element: Any) -> list[str]:
    return [child.tag.rsplit("}", 1)[1] for child in element]


def _assert_in_order(element: Any, order: list[str], where: str) -> None:
    names = _names(element)
    assert all(n in order for n in names), (where, names)
    assert names == sorted(names, key=order.index), (where, names)


@pytest.fixture(scope="module", params=CARBON, ids=lambda p: p.stem)
def exported(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Presentation]:
    source: Path = request.param
    out = tmp_path_factory.mktemp("carbon") / f"{source.stem}.pptx"
    report = to_pptx(str(source), str(out))
    assert [w for w in report.warnings if "finish" in w] == []
    return source, Presentation(str(out))


@needs_chromium
def test_round_trip_and_geometry(exported: tuple[Path, Presentation]) -> None:
    """python-pptx reopens the saved file; every shape has a size and every text box sits inside the slide."""
    _, deck = exported
    buffer = io.BytesIO()
    deck.save(buffer)
    again = Presentation(io.BytesIO(buffer.getvalue()))
    assert len(again.slides) == len(deck.slides)
    width, height = deck.slide_width, deck.slide_height
    for number, slide in enumerate(deck.slides, 1):
        seen: set[tuple[Any, ...]] = set()
        for shape in slide.shapes:
            assert shape.width > 0 and shape.height > 0, (number, shape.name)
            if shape.has_text_frame and shape.text_frame.text.strip():
                assert shape.left >= -TOLERANCE * PX and shape.top >= -TOLERANCE * PX, (number, shape.name)
                assert shape.left + shape.width <= width + TOLERANCE * PX, (number, shape.name, shape.text_frame.text)
                assert shape.top + shape.height <= height + TOLERANCE * PX, (number, shape.name, shape.text_frame.text)
            key = (
                shape.shape_type,
                shape.left,
                shape.top,
                shape.width,
                shape.height,
                shape.has_text_frame and shape.text_frame.text,
            )
            assert key not in seen, (number, "duplicate shape", shape.name)
            seen.add(key)


@needs_chromium
def test_text_xml_is_ordered_and_without_empty_runs(exported: tuple[Path, Presentation]) -> None:
    """No empty run; child order of rPr, pPr and tcPr follows the schema (PowerPoint refuses a misordered file)."""
    _, deck = exported
    runs = 0
    for slide in deck.slides:
        root = slide._element
        for run in root.iter(qn("a:r")):
            assert (run.find(qn("a:t")).text or "") != "", "empty run"
            properties = run.find(qn("a:rPr"))
            if properties is not None:
                _assert_in_order(properties, RPR_ORDER, "rPr")
            runs += 1
        for properties in root.iter(qn("a:pPr")):
            _assert_in_order(properties, PPR_ORDER, "pPr")
        for properties in root.iter(qn("a:tcPr")):
            _assert_in_order(properties, TCPR_ORDER, "tcPr")
    assert runs > 5


@needs_chromium
def test_text_boxes_do_not_autofit_nor_surprise(exported: tuple[Path, Presentation]) -> None:
    """No autofit shrink, no wrap surprise: every text box is ``wrap="none"`` with ``noAutofit``, zero insets, and an
    exact line spacing in points (one paragraph per browser line)."""
    _, deck = exported
    boxes = 0
    for slide in deck.slides:
        for shape in slide.shapes:
            if shape.shape_type != 17 or not shape.text_frame.text.strip():  # TEXT_BOX
                continue
            body = shape.text_frame._txBody.find(qn("a:bodyPr"))
            assert body.get("wrap") == "none"
            assert body.find(qn("a:noAutofit")) is not None
            assert [body.get(k) for k in ("lIns", "tIns", "rIns", "bIns")] == ["0"] * 4
            for paragraph in shape.text_frame.paragraphs:
                spacing = paragraph._p.pPr.find(qn("a:lnSpc"))
                assert spacing.find(qn("a:spcPts")) is not None
            boxes += 1
    assert boxes > 0


@needs_chromium
def test_fonts_name_the_first_family_of_the_stack(exported: tuple[Path, Presentation]) -> None:
    """Carbon text is written as ``IBM Plex Sans`` (code as ``IBM Plex Mono``), never the machine's fallback."""
    _, deck = exported
    faces = {
        run.font.name
        for slide in deck.slides
        for shape in slide.shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
    }
    assert "IBM Plex Sans" in faces
    assert faces <= {"IBM Plex Sans", "IBM Plex Mono", "Courier New", "Arial", "Georgia"}, faces


@needs_chromium
@pytest.mark.parametrize("source", CARBON[1:], ids=lambda p: p.stem)
def test_reference_decks_have_native_tables_with_pills(source: Path, tmp_path: Path) -> None:
    """FR-5: the structured lists are native tables; their pills are drawn shapes or run highlights, never lost."""
    target = tmp_path / f"{source.stem}.pptx"
    to_pptx(str(source), str(target))
    slides = Presentation(str(target)).slides
    tables = [s for slide in slides for s in slide.shapes if s.has_table]
    assert len(tables) >= 2, source.stem
    highlights = sum(len(list(slide._element.iter(qn("a:highlight")))) for slide in slides)
    rounded = sum(1 for slide in slides for s in slide.shapes if s.name.startswith("Rounded"))
    assert highlights + rounded > 0
