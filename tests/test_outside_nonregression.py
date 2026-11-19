"""SPEC-0026 (US-0154): no way to allow an outside read, and the pictures inside the folder export as before."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

from mcp_htmleditor.config import Settings
from mcp_htmleditor.deck_folder import OUTSIDE_PREFIX
from mcp_htmleditor.export.to_pptx import to_pptx
from tests.deck_support import run_cli as _run_cli
from tests.render_support import needs_chromium

RED = (255, 0, 0)
BLUE = (0, 0, 255)
needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc is not installed")
# Written from the ``--help`` output of the three commands before SPEC-0026 (BR-008): nothing about pictures or folders.
EXPECTED_OPTIONS = {
    ("export", "pptx"): {"--help"},
    ("export", "docx"): {"--help"},
    ("render",): {"--help", "--json", "--report", "--report-only", "--scale", "--slide"},
}


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture(autouse=True)
def out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path / "htmleditor-render"


def solid_png(colour: tuple[int, int, int], size: int = 200) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (size, size), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def inside_deck(tmp_path: Path, kind: str = "presentation") -> Path:
    """``tmp/deck`` with ``local.png`` and ``media/a.png``, and one picture per address form (all inside)."""
    folder = tmp_path / "deck"
    (folder / "media").mkdir(parents=True)
    (folder / "local.png").write_bytes(solid_png((0, 128, 0)))
    (folder / "media" / "a.png").write_bytes(solid_png(RED))
    sources = ["local.png", "media/a.png", str(folder / "local.png"), (folder / "media" / "a.png").as_uri()]
    images = "".join(f'<img src="{source}" alt="x" style="width:40px;height:40px">' for source in sources)
    path = folder / "deck.html"
    if kind == "presentation":
        attributes = 'class="slide active" data-type="slide" data-id="slide-1" data-title="One"'
        body = f"<section {attributes}><h1>One</h1>{images}</section>"
    else:
        body = f"<h1>One</h1>{images}"
    path.write_text(f'<!DOCTYPE html><html data-doc-type="{kind}"><body>{body}</body></html>', encoding="utf-8")
    return path


def count_in(archive_path: Path, member: str, needle: str) -> int:
    with zipfile.ZipFile(archive_path) as archive:
        return archive.read(member).decode("utf-8").count(needle)


def test_bt022_no_option_or_setting_lets_a_picture_outside_be_read() -> None:
    for command, expected in EXPECTED_OPTIONS.items():
        stdout, _, code = run_cli(*command, "--help")
        options = {token.rstrip(",") for token in stdout.split() if token.startswith("--")}
        assert code == 0
        assert options == expected, command
    assert not [name for name in Settings.model_fields if "picture" in name or "outside" in name]


def test_bt030_pptx_flow_embeds_the_pictures_inside_the_folder(tmp_path: Path) -> None:
    """The flow export does not understand a file:// address (as before): 3 of 4 pictures, no outside warning."""
    deck = inside_deck(tmp_path)
    output = tmp_path / "out.pptx"

    report = to_pptx(str(deck), str(output), paint=False)

    assert count_in(output, "ppt/slides/slide1.xml", "<p:pic>") == 3
    assert not [w for w in report.warnings if w.startswith(OUTSIDE_PREFIX)]
    assert any(w.startswith("Image introuvable, ignoree: ") for w in report.warnings)


@needs_chromium
def test_bt030_pptx_painted_embeds_the_four_pictures(tmp_path: Path) -> None:
    deck = inside_deck(tmp_path)
    output = tmp_path / "out.pptx"

    _, stderr, code = run_cli("export", "pptx", str(deck), str(output))

    assert code == 0
    assert OUTSIDE_PREFIX not in stderr
    assert count_in(output, "ppt/slides/slide1.xml", "<p:pic>") == 4


@needs_pandoc
def test_bt030_docx_embeds_the_four_pictures(tmp_path: Path) -> None:
    deck = inside_deck(tmp_path, kind="document")
    output = tmp_path / "out.docx"

    _, stderr, code = run_cli("export", "docx", str(deck), str(output))

    assert code == 0
    assert OUTSIDE_PREFIX not in stderr
    assert count_in(output, "word/document.xml", "<pic:pic") == 4


@needs_chromium
def test_bt030_render_reports_no_picture_problem_for_pictures_inside(tmp_path: Path) -> None:
    deck = inside_deck(tmp_path)

    stdout, stderr, _ = run_cli("render", str(deck), "--slide", "slide-1", "--json", "--report")

    assert stdout, stderr
    assert json.loads(stdout)["problems"] == []


@needs_chromium
def test_bt031_render_still_loads_a_style_sheet_and_a_picture_inside_the_folder(tmp_path: Path) -> None:
    folder = tmp_path / "deck"
    folder.mkdir()
    (folder / "theme.css").write_text(".slide{background:#0000FF}", encoding="utf-8")
    (folder / "a.png").write_bytes(solid_png(RED))
    (folder / "deck.html").write_text(
        '<!DOCTYPE html><html data-doc-type="presentation"><head><link rel="stylesheet" href="theme.css"></head><body>'
        '<section class="slide active" data-type="slide" data-id="slide-1" data-title="One">'
        '<img src="a.png" style="width:200px;height:200px"></section></body></html>',
        encoding="utf-8",
    )

    stdout, stderr, _ = run_cli("render", str(folder / "deck.html"), "--slide", "slide-1", "--json")

    assert stdout, stderr
    with Image.open(str(json.loads(stdout)["path"])) as image:
        colours = {colour for _, colour in image.convert("RGB").getcolors(maxcolors=1_000_000)}
    assert RED in colours
    assert BLUE in colours
