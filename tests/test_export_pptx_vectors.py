"""PPTX export: vector figures are named in the warnings and the slides stay as they were (SPEC-0016, US-0096).

SPEC-0024: with Chromium the figures are rasterised by the browser and no warning remains; the warnings below are the
ones of the flow build, the degraded result (Chromium missing, or ``paint=False``).
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from mcp_htmleditor.export.to_pptx import to_pptx

from .conftest import needs_chromium
from .stdio_support import initialize_requests, run_session, tool_request

REPO = Path(__file__).resolve().parent.parent
BOOTSTRAP = REPO / "templates" / "bootstrap" / "slides-empty.html"
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="red"/></svg>'
DATA_SRC = "data:image/svg+xml;base64," + base64.b64encode(SVG.encode()).decode()
ADVICE = "l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG."
INLINE = f"Slide 1: balise <svg> en ligne ignoree, {ADVICE}"
FILE_IMAGE = f"Slide 1: image SVG ignoree (fig.svg), {ADVICE}"
DATA_IMAGE = f"Slide 1: image SVG ignoree ({DATA_SRC[:60]}), {ADVICE}"
PLACEHOLDER = '<p style="color:var(--cds-text-secondary); font-style:italic;">Contenu de la slide…</p>'
DEGRADED = (
    "Deck exported without the rendered finish (Chromium is not installed). "
    "Install the browser with: make install-browser"
)
SLIDE_BLOCK = re.compile(r"<article class=\"slide active\".*?</article>", re.DOTALL)
# sha256 of ppt/slides/slide1.xml of deck V, recorded on the exporter before US-0096 (DEC-005)
V_SLIDE_XML_SHA256 = "9ea97a2be72b53ebad2706f832d884e91e1136828490e22ab3031b592bffc5b8"


def _vector_deck(tmp_path: Path, *, inline: str = SVG, name: str = "svg.html") -> Path:
    """Deck V: the Carbon bootstrap whose slide starts with an inline svg and two vector images."""
    body = f'{inline}<img src="fig.svg" alt="f"><img src="{DATA_SRC}" alt="d">'
    source = BOOTSTRAP.read_text(encoding="utf-8").replace(PLACEHOLDER, body, 1)
    (tmp_path / "fig.svg").write_text(SVG, encoding="utf-8")
    deck = tmp_path / name
    deck.write_text(source, encoding="utf-8")
    return deck


def _export(deck: Path, tmp_path: Path) -> list[str]:
    return to_pptx(str(deck), str(tmp_path / "out.pptx"), paint=False).warnings


def _no_browser_env(tmp_path: Path) -> dict[str, str]:
    """The environment of a machine without Chromium: the render of the painted export degrades to the flow build."""
    return {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(tmp_path / "no-browsers")}


def test_bt002_cli_names_every_vector_figure(tmp_path: Path) -> None:
    """BT-002: one stderr line per vector figure (degraded export), exit 0, no object address."""
    deck = _vector_deck(tmp_path)
    out = tmp_path / "out.pptx"

    result = subprocess.run(  # noqa: S603 - fixed argument list
        [sys.executable, "-m", "mcp_htmleditor", "export", "pptx", str(deck), str(out)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=_no_browser_env(tmp_path),
    )

    assert result.returncode == 0
    assert result.stdout.rstrip().endswith("Done. 1 slide(s) exportee(s).")
    lines = [line for line in result.stderr.splitlines() if line.startswith("Attention: ")]
    assert lines == [f"Attention: {w}" for w in (INLINE, FILE_IMAGE, DATA_IMAGE, DEGRADED)]
    assert "Image non decodable" not in result.stderr
    assert "Image non inseree" not in result.stderr


def test_bt013_shell_icons_and_silent_ancestors(tmp_path: Path) -> None:
    """BT-013: shell icons, svg in a button and nested svg do not add warnings."""
    carbon = _export(BOOTSTRAP, tmp_path)
    assert not [w for w in carbon if "svg" in w.lower()]

    in_button = _export(_vector_deck(tmp_path, inline=f"<button>{SVG}</button>", name="b.html"), tmp_path)
    assert in_button == [FILE_IMAGE, DATA_IMAGE]

    nested = SVG.replace("<rect", f"{SVG}<rect", 1)
    in_svg = _export(_vector_deck(tmp_path, inline=nested, name="n.html"), tmp_path)
    assert in_svg == [INLINE, FILE_IMAGE, DATA_IMAGE]


def test_bt013_vector_deck_slide_is_byte_identical(tmp_path: Path) -> None:
    """BT-013: the slide XML of V equals the one recorded before the fix (DEC-005)."""
    deck = _vector_deck(tmp_path)
    out = tmp_path / "out.pptx"

    report = to_pptx(str(deck), str(out), paint=False)

    assert report.slide_count == 1
    with zipfile.ZipFile(out) as archive:
        digest = hashlib.sha256(archive.read("ppt/slides/slide1.xml")).hexdigest()
    assert digest == V_SLIDE_XML_SHA256


def test_bt014_numbering_order_and_case(tmp_path: Path) -> None:
    """BT-014: slide numbers, document order, upper case extension and query string."""
    block = SLIDE_BLOCK.search(BOOTSTRAP.read_text(encoding="utf-8"))
    assert block
    bodies = ["", f'{SVG}<img src="Fig.SVG?v=2">', SVG]
    slides = [
        block.group(0).replace("slide-0", f"slide-{i}").replace(PLACEHOLDER, body) for i, body in enumerate(bodies)
    ]
    source = SLIDE_BLOCK.sub(lambda _: "\n".join(slides), BOOTSTRAP.read_text(encoding="utf-8"), count=1)
    deck = tmp_path / "three.html"
    deck.write_text(source.replace("const TOTAL = 1;", "const TOTAL = 3;"), encoding="utf-8")
    (tmp_path / "Fig.SVG").write_text(SVG, encoding="utf-8")

    assert _export(deck, tmp_path) == [
        f"Slide 2: balise <svg> en ligne ignoree, {ADVICE}",
        f"Slide 2: image SVG ignoree (Fig.SVG?v=2), {ADVICE}",
        f"Slide 3: balise <svg> en ligne ignoree, {ADVICE}",
    ]


def test_bt015_agent_tool_returns_the_warnings(tmp_path: Path) -> None:
    """BT-015: the MCP tool export carries the three warnings (degraded export) then the degraded warning."""
    deck = _vector_deck(tmp_path)
    out = tmp_path / "out.pptx"
    arguments = {"file": str(deck), "format": "pptx", "output": str(out)}

    messages = run_session(
        [
            *initialize_requests(),
            tool_request(2, "export", arguments),
        ],
        {2},
        cwd=tmp_path,
        env=_no_browser_env(tmp_path),
    )

    result = next(m for m in messages if m.get("id") == 2)["result"]
    payload = result["structuredContent"]
    assert payload["ok"] is True
    assert payload["warnings"] == [INLINE, FILE_IMAGE, DATA_IMAGE, DEGRADED]


def test_bt034_other_unreadable_images_keep_their_warnings(tmp_path: Path) -> None:
    """BT-034: a broken png still gets today's two warnings, none about SVG."""
    (tmp_path / "broken.png").write_bytes(b"not an image")
    source = BOOTSTRAP.read_text(encoding="utf-8").replace(PLACEHOLDER, '<img src="broken.png">', 1)
    deck = tmp_path / "broken.html"
    deck.write_text(source, encoding="utf-8")

    warnings = _export(deck, tmp_path)

    assert len(warnings) == 2
    assert warnings[0].startswith("Image non decodable ignoree: ")
    assert warnings[1].startswith("Image non inseree (")
    assert not [w for w in warnings if "SVG" in w]


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("a.svg", True),
        ("A.SVG?v=1", True),
        ("a.svg#frag", False),
        ("data:image/svg+xml;base64,AAA", True),
        ("DATA:IMAGE/SVG+XML,x", True),
        ("a.png", False),
        ("a.svgz", False),
        ("", False),
    ],
)
def test_is_vector_src(src: str, expected: bool) -> None:
    from mcp_htmleditor.export.pptx_vectors import is_vector_src

    assert is_vector_src(src) is expected


def test_silent_ancestors_inside_the_slide() -> None:
    """BR-007: any listed ancestor silences an svg or an img, and a plain div does not."""
    from mcp_htmleditor.export.pptx_vectors import vector_figure_warnings

    html = "".join(f"<{tag}>{SVG}<img src='x.svg'></{tag}>" for tag in ("button", "script", "template", "noscript"))
    html += f"<select>{SVG}</select><div>{SVG}</div>"
    slide = BeautifulSoup(f"<section>{html}</section>", "html.parser").section
    assert slide is not None

    assert vector_figure_warnings(slide, 4) == [f"Slide 4: balise <svg> en ligne ignoree, {ADVICE}"]


@needs_chromium
def test_painted_export_rasterises_every_vector_figure(tmp_path: Path) -> None:
    """SPEC-0024 FR-4: the inline svg and both vector images become pictures, no vector warning remains."""
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    deck = _vector_deck(tmp_path)
    out = tmp_path / "painted.pptx"

    report = to_pptx(str(deck), str(out))

    assert [w for w in report.warnings if "SVG" in w or "svg" in w] == []
    pictures = [s for s in Presentation(str(out)).slides[0].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pictures) == 3
    assert all(p.width > 0 and p.height > 0 for p in pictures)
