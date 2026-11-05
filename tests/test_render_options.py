"""US-0062: choose a slide and a scale (SPEC-0008 E2E-002, E2E-008, E2E-009, E2E-020, E2E-021 and the unit tables)."""

from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from mcp_htmleditor.render import RenderError
from mcp_htmleditor.render.options import output_size, parse_scale
from tests import render_support as rs
from tests.deck_support import doc_perso, write_deck
from tests.deck_support import run_cli as _run_cli

NEEDS_CHROMIUM = rs.needs_chromium
SCALE_MESSAGE = "Scale must be between 0.1 and 1"
INSTALL_MESSAGE = "Rendering needs Chromium. Install it with: make install-browser"
ALL_IDS = ", ".join(f"slide-{i}" for i in range(8))


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses to start inside a running loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path / "htmleditor-render"


@pytest.fixture
def ei_file(tmp_path):
    return write_deck(tmp_path / "DECK-EI.html", rs.ei_deck_html())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0.1", "0.1"), ("1", "1"), (".5", "0.5"), ("1e-1", "0.1"), (" 0.5 ", "0.5"), ("0.50", "0.5"), (None, "0.5")],
)
def test_parse_scale_accepts(raw, expected):
    assert parse_scale(raw) == Decimal(expected)


def test_parse_scale_accepts_a_float_through_its_repr():
    assert parse_scale(0.1) == Decimal("0.1")
    assert parse_scale(1.0) == Decimal("1")


@pytest.mark.parametrize("raw", ["0.09", "1.01", "0", "-1", "", "abc", "nan", "inf", "-inf", "1,5"])
def test_parse_scale_refuses(raw):
    with pytest.raises(RenderError, match=SCALE_MESSAGE):
        parse_scale(raw)


@pytest.mark.parametrize("raw", [float("nan"), float("inf"), 1.5, 0.0])
def test_parse_scale_refuses_bad_floats(raw):
    with pytest.raises(RenderError, match=SCALE_MESSAGE):
        parse_scale(raw)


@pytest.mark.parametrize(
    ("scale", "size"),
    [
        ("0.1", (96, 54)),
        ("0.5", (480, 270)),
        ("1", (960, 540)),
        ("0.125", (120, 68)),
        ("0.123", (118, 66)),
        ("0.995", (955, 537)),
    ],
)
def test_output_size(scale, size):
    assert output_size(Decimal(scale)) == size


@NEEDS_CHROMIUM
def test_slide_and_scale(ei_file, out_dir):
    picture = out_dir / "DECK-EI-slide-3.png"
    stdout, stderr, status = run_cli("render", ei_file, "--slide", "slide-3", "--scale", "1")
    assert (stdout, stderr, status) == (f"Rendered slide-3 to {picture} (960x540)\n", "", 0)
    assert rs.png_size(picture) == (960, 540)
    stdout, stderr, status = run_cli("render", ei_file, "--slide", "slide-3", "--scale", "0.1")
    assert (stdout, stderr, status) == (f"Rendered slide-3 to {picture} (96x54)\n", "", 0)
    assert rs.png_size(picture) == (96, 54)


@NEEDS_CHROMIUM
def test_default_scale_text_is_the_same_as_no_option(ei_file, out_dir):
    plain = run_cli("render", ei_file)
    explicit = run_cli("render", ei_file, "--scale", "0.5")
    assert plain == explicit
    assert plain[0].endswith("(480x270)\n")


def test_unknown_slide(ei_file, out_dir):
    if not rs.HAS_CHROMIUM:
        pytest.skip("the browser is launched before the id is checked")
    stdout, stderr, status = run_cli("render", ei_file, "--slide", "slide-9")
    expected = f'error: Unknown slide id "slide-9". Valid ids: {ALL_IDS}\n'
    assert (stdout, stderr, status) == ("", expected, 1)
    assert not out_dir.exists()


@pytest.mark.parametrize("scale", ["1.5", "0", "abc"])
def test_scale_out_of_range(scale, ei_file, out_dir):
    stdout, stderr, status = run_cli("render", ei_file, "--scale", scale)
    assert (stdout, stderr, status) == ("", f"error: {SCALE_MESSAGE}\n", 1)
    assert not out_dir.exists()


def test_scale_is_checked_before_the_file(out_dir):
    assert run_cli("render", "ghost.html", "--scale", "abc") == ("", f"error: {SCALE_MESSAGE}\n", 1)


def test_file_is_checked_before_the_presentation(out_dir):
    assert run_cli("render", "ghost.html", "--slide", "slide-9") == ("", "error: File not found: ghost.html\n", 1)


def test_presentation_is_checked_before_the_slide(tmp_path, out_dir):
    file = write_deck(tmp_path / "DOC-PERSO.html", doc_perso())
    stdout, stderr, status = run_cli("render", file, "--slide", "slide-9")
    assert (stdout, stderr, status) == ("", f"error: render needs a presentation: {file}\n", 1)


def test_browser_is_checked_before_the_slide(ei_file, out_dir, tmp_path, monkeypatch):
    empty = tmp_path / "no-browsers"
    empty.mkdir()
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(empty))
    assert run_cli("render", ei_file, "--slide", "slide-9") == ("", f"error: {INSTALL_MESSAGE}\n", 1)


def _without_ids(html: str) -> str:
    return html.replace('id="slide-1"', "").replace('data-id="slide-1"', "")


@NEEDS_CHROMIUM
def test_slide_without_id_uses_the_index_fallback(tmp_path, out_dir):
    file = write_deck(tmp_path / "noid.html", _without_ids(rs.ei_deck_html()))
    stdout, _, status = run_cli("render", file, "--slide", "slide-1")
    assert (status, stdout) == (0, f"Rendered slide-1 to {out_dir / 'noid-slide-1.png'} (480x270)\n")
    unknown = run_cli("render", file, "--slide", "slide-9")
    assert unknown[1] == f'error: Unknown slide id "slide-9". Valid ids: {ALL_IDS}\n'


@NEEDS_CHROMIUM
def test_dark_surface(tmp_path, out_dir):
    file = write_deck(tmp_path / "DECK-MED.html", rs.med_deck_html("slide-2"))
    assert run_cli("render", file, "--slide", "slide-2", "--scale", "1")[2] == 0
    assert rs.png_pixel(out_dir / "DECK-MED-slide-2.png", 2, 300) == (0x0B, 0x0E, 0x11)


@NEEDS_CHROMIUM
def test_only_the_last_render_stays(ei_file, out_dir):
    out_dir.mkdir()
    other = out_dir / "other-slide-1.png"
    other.write_bytes(b"x")
    assert run_cli("render", ei_file, "--slide", "slide-1")[2] == 0
    assert run_cli("render", ei_file, "--slide", "slide-2")[2] == 0
    assert sorted(p.name for p in out_dir.iterdir()) == ["DECK-EI-slide-2.png", "other-slide-1.png"]
    assert other.read_bytes() == b"x"
