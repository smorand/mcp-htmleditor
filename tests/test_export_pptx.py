"""Tests for the HTML → PPTX export."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from mcp_htmleditor.export.to_pptx import (
    _extract_position,
    _parse_pct,
    _parse_px,
    to_pptx,
)

_GOLDEN_HTML = """<!DOCTYPE html>
<html data-doc-type="presentation">
<head><meta charset="UTF-8"></head>
<body>
<section data-type="slide" data-id="s1" data-title="Intro">
  <h1>Title One</h1>
  <p>Some body text on the first slide.</p>
  <table>
    <tr><th>Name</th><th>Value</th></tr>
    <tr><td>alpha</td><td>1</td></tr>
    <tr><td>beta</td><td>2</td></tr>
  </table>
</section>
<section data-type="slide" data-id="s2" data-title="Second">
  <h2>Title Two</h2>
  <p>Second slide content.</p>
</section>
<section data-type="slide" data-id="s3" data-title="Charts">
  <div data-type="gantt">
    <div data-type="gantt-task" data-label="Design" data-start="2024-01" data-end="2024-02" data-color="#f00"></div>
    <div data-type="gantt-task" data-label="Build" data-start="2024-02" data-end="2024-04"></div>
  </div>
  <div data-type="arch-diagram">
    <div data-type="arch-node" data-label="API" data-x="10" data-y="10" data-width="20" data-height="10"></div>
    <div data-type="arch-node" data-label="DB" data-x="40" data-y="40"></div>
  </div>
</section>
<section data-type="slide" data-id="s4" data-title="Positioned">
  <p style="left:10%;top:20%;width:50%;height:15%">Positioned text</p>
  <div data-type="annotated-image">
    <img src="missing.png" style="left:5%;top:5%;width:40%;height:40%">
    <div data-type="annotation" data-x="30" data-y="30">note</div>
  </div>
</section>
</body>
</html>
"""


def test_to_pptx_creates_nonempty_file(tmp_path: Path) -> None:
    """to_pptx writes a real .pptx file that is non-empty."""
    src = tmp_path / "deck.html"
    src.write_text(_GOLDEN_HTML, encoding="utf-8")
    out = tmp_path / "out" / "deck.pptx"

    to_pptx(str(src), str(out))

    assert out.exists()
    assert out.stat().st_size > 0


def test_to_pptx_is_reopenable_with_expected_slides(tmp_path: Path) -> None:
    """The generated file reopens as a valid presentation with 2 slides."""
    src = tmp_path / "deck.html"
    src.write_text(_GOLDEN_HTML, encoding="utf-8")
    out = tmp_path / "deck.pptx"

    to_pptx(str(src), str(out))

    prs = Presentation(str(out))
    assert len(prs.slides) == 4

    # The first slide should contain a table shape and text.
    first = prs.slides[0]
    has_table = any(shape.has_table for shape in first.shapes)
    assert has_table

    all_text = " ".join(
        shape.text_frame.text
        for shape in first.shapes
        if shape.has_text_frame
    )
    assert "Title One" in all_text


def test_to_pptx_no_slide_sections_falls_back_to_body(tmp_path: Path) -> None:
    """HTML with no slide sections still produces a single-slide deck."""
    src = tmp_path / "plain.html"
    src.write_text(
        "<html><body><h1>Just a doc</h1><p>text</p></body></html>",
        encoding="utf-8",
    )
    out = tmp_path / "plain.pptx"

    to_pptx(str(src), str(out))

    prs = Presentation(str(out))
    assert len(prs.slides) == 1


def test_parse_pct() -> None:
    """Percentage strings parse to a 0-100 float; garbage is 0."""
    assert _parse_pct("25%") == 25.0
    assert _parse_pct(" 12.5% ") == 12.5
    assert _parse_pct("nope") == 0.0


def test_parse_px() -> None:
    """Pixel strings parse to a float; garbage is 0."""
    assert _parse_px("96px") == 96.0
    assert _parse_px(" 48.5px ") == 48.5
    assert _parse_px("auto") == 0.0


def test_extract_position_percent_and_px() -> None:
    """Inline style with %/px positions resolves to non-None EMU values."""
    style = "left:10%; top:20%; width:200px; height:100px"
    pos = _extract_position(style)
    assert pos["left"] is not None
    assert pos["top"] is not None
    assert pos["width"] is not None
    assert pos["height"] is not None


def test_extract_position_empty_style() -> None:
    """An empty style yields all-None positions."""
    pos = _extract_position("")
    assert all(v is None for v in pos.values())
