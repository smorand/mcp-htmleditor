"""SPEC-0026 (US-0151): the painted PPTX export reads no picture outside the deck's folder.

Reads the effect through the output artifact (media bytes, decoded pixels, slide XML), never through the warning.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any
from unittest import mock

from PIL import Image

from mcp_htmleditor.deck_folder import OUTSIDE_PREFIX
from mcp_htmleditor.export import pptx_paint
from mcp_htmleditor.export.pptx_model import ExportReport
from tests.deck_support import run_cli
from tests.render_support import needs_chromium

COLOR = (1, 2, 3)


def png_bytes(colour: tuple[int, int, int], size: int = 4) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (size, size), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def make_deck(tmp_path: Path, body: str, head: str = "") -> Path:
    """A one slide deck in ``tmp_path/deck``; whatever the test writes next to it sits outside the folder."""
    folder = tmp_path / "deck"
    folder.mkdir(exist_ok=True)
    path = folder / "deck.html"
    path.write_text(
        f'<!DOCTYPE html><html data-doc-type="presentation"><head>{head}</head><body>'
        f'<section class="slide" data-type="slide" data-id="s1" data-title="One"><h1>One</h1>{body}</section>'
        "</body></html>",
        encoding="utf-8",
    )
    return path


def archive_parts(output: Path, prefix: str) -> list[bytes]:
    with zipfile.ZipFile(output) as archive:
        return [archive.read(name) for name in archive.namelist() if name.startswith(prefix)]


def colours(png: bytes) -> set[tuple[int, int, int]]:
    with Image.open(io.BytesIO(png)) as image:
        return {pixel[:3] for pixel in image.convert("RGB").getdata()}


def test_bt001_the_command_line_export_embeds_nothing_from_outside(tmp_path: Path) -> None:
    """BT-001: the reproduction, through the command line (painted when Chromium is there, flowed otherwise)."""
    secret = png_bytes((255, 0, 0), 2)
    (tmp_path / "secret.png").write_bytes(secret)
    deck = make_deck(tmp_path, '<img src="../secret.png" alt="x">')
    output = tmp_path / "out.pptx"

    _, stderr, code = run_cli("export", "pptx", str(deck), str(output))

    assert code == 0
    assert secret not in archive_parts(output, "ppt/media/")
    assert f"Attention: {OUTSIDE_PREFIX}" in stderr


def test_bt011_the_painter_refuses_every_outside_address(tmp_path: Path) -> None:
    folder = tmp_path / "deck"
    folder.mkdir()
    secret = png_bytes((255, 0, 0), 2)
    (tmp_path / "secret.png").write_bytes(secret)
    (folder / "local.png").write_bytes(secret)
    report = ExportReport()
    painter: Any = pptx_paint.Painter(mock.MagicMock(), report, folder)

    results = [
        painter._bytes(src)
        for src in ("../secret.png", str(tmp_path / "secret.png"), (tmp_path / "secret.png").as_uri())
    ]

    assert results == [None, None, None]
    assert len([w for w in report.warnings if w.startswith(OUTSIDE_PREFIX)]) == 3
    assert painter._bytes("local.png") == secret
    assert painter._bytes((folder / "local.png").as_uri()) == secret


@needs_chromium
def test_bt012_chromium_draws_no_outside_picture_into_a_figure(tmp_path: Path) -> None:
    """BT-012: an inline svg names the secret by file URL; the browser would draw it into the raster of the figure."""
    (tmp_path / "secret.png").write_bytes(png_bytes(COLOR))
    figure = (
        f'<svg width="80" height="80"><image href="{(tmp_path / "secret.png").as_uri()}" width="80" height="80"/></svg>'
    )
    deck = make_deck(tmp_path, figure)
    output = tmp_path / "out.pptx"

    _, stderr, code = run_cli("export", "pptx", str(deck), str(output))

    assert code == 0
    assert "without the rendered finish" not in stderr
    assert not any(COLOR in colours(part) for part in archive_parts(output, "ppt/media/"))


@needs_chromium
def test_bt016_an_outside_style_sheet_is_not_applied_by_the_measure(tmp_path: Path) -> None:
    (tmp_path / "out.css").write_text(".slide{background:#0000FF}", encoding="utf-8")
    deck = make_deck(tmp_path, "<p>text</p>", head='<link rel="stylesheet" href="../out.css">')
    output = tmp_path / "out.pptx"

    _, stderr, code = run_cli("export", "pptx", str(deck), str(output))

    assert code == 0
    assert "without the rendered finish" not in stderr
    assert not any(b"0000FF" in part for part in archive_parts(output, "ppt/slides/slide"))


def test_bt021_the_painter_judges_a_symlink_by_where_it_leads(tmp_path: Path) -> None:
    """BR-006 on the painted export: a link to an outside file is refused, a link to an inside file is read."""
    folder = tmp_path / "deck"
    folder.mkdir()
    secret = png_bytes((255, 0, 0), 2)
    (tmp_path / "secret.png").write_bytes(secret)
    (folder / "real.png").write_bytes(secret)
    (folder / "leak.png").symlink_to(tmp_path / "secret.png")
    (folder / "inner.png").symlink_to(folder / "real.png")
    report = ExportReport()
    painter: Any = pptx_paint.Painter(mock.MagicMock(), report, folder)

    assert painter._bytes("leak.png") is None
    assert painter._bytes("inner.png") == secret
    assert [w for w in report.warnings if w.startswith(OUTSIDE_PREFIX)] == [f"{OUTSIDE_PREFIX}leak.png"]
