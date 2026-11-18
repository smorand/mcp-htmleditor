"""US-0139: ``to_pptx(..., embedded_pictures_only=True)`` reads a picture only from a ``data:`` address (SPEC-0025,
DEC-043). The second channel is the media parts of the PPTX: the bytes of the secret picture are searched for."""

from __future__ import annotations

import base64
import zipfile
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from mcp_htmleditor.export import pptx_paint
from mcp_htmleditor.export.pptx_model import ExportReport
from mcp_htmleditor.export.to_pptx import to_pptx
from tests.library_support import PNG_1X1

SECRET = PNG_1X1 + b"SECRET-PICTURE-MARKER"
DATA_URI = "data:image/png;base64," + base64.b64encode(PNG_1X1).decode()
WARNING = "Image non incluse dans le fichier, ignoree."


def deck(tmp_path: Path, sources: list[str]) -> Path:
    """A one slide deck in ``tmp_path/deck`` whose pictures are ``sources``; ``secret.png`` sits next to the folder."""
    folder = tmp_path / "deck"
    folder.mkdir()
    (tmp_path / "secret.png").write_bytes(SECRET)
    (folder / "local.png").write_bytes(SECRET)
    images = "".join(f'<img src="{source}" alt="x">' for source in sources)
    path = folder / "deck.html"
    path.write_text(
        '<!DOCTYPE html><html data-doc-type="presentation"><body>'
        f'<section class="slide" data-type="slide" data-id="s1" data-title="One"><h1>One</h1>{images}</section>'
        "</body></html>",
        encoding="utf-8",
    )
    return path


def media(output: Path) -> list[bytes]:
    with zipfile.ZipFile(output) as archive:
        return [archive.read(name) for name in archive.namelist() if name.startswith("ppt/media/")]


def hostile(tmp_path: Path) -> list[str]:
    return ["../secret.png", str(tmp_path / "secret.png"), (tmp_path / "secret.png").as_uri(), "https://x.test/a.png"]


def test_the_default_still_embeds_a_relative_picture(tmp_path: Path) -> None:
    """Unchanged local behavior: a picture next to the deck is embedded."""
    path = deck(tmp_path, ["local.png"])
    output = tmp_path / "out.pptx"

    to_pptx(str(path), str(output), paint=False)

    assert any(SECRET in part or PNG_1X1 in part for part in media(output))


def test_with_the_flag_no_address_but_a_data_uri_is_read(tmp_path: Path) -> None:
    sources = [*hostile(tmp_path), "local.png", DATA_URI]
    path = deck(tmp_path, sources)
    output = tmp_path / "out.pptx"

    report = to_pptx(str(path), str(output), paint=False, embedded_pictures_only=True)

    parts = media(output)
    assert not any(b"SECRET-PICTURE-MARKER" in part for part in parts)
    assert len(parts) == 1
    assert WARNING in report.warnings


@pytest.mark.parametrize("source", ["../secret.png", "/abs", "file:///etc/hosts", "local.png"])
def test_a_refused_address_gives_no_picture_and_the_warning(tmp_path: Path, source: str) -> None:
    path = deck(tmp_path, [source])
    output = tmp_path / "out.pptx"

    report = to_pptx(str(path), str(output), paint=False, embedded_pictures_only=True)

    assert media(output) == []
    assert set(report.warnings) == {
        WARNING
    }  # the flow reads a source for its ratio and again to place it, as for a missing file


def test_the_painted_path_refuses_the_same_addresses(tmp_path: Path) -> None:
    """The painter's ``_bytes`` honors the flag: nothing is read from disk, one warning per address."""
    folder = tmp_path / "deck"
    folder.mkdir()
    (folder / "local.png").write_bytes(SECRET)
    report = ExportReport()
    painter: Any = pptx_paint.Painter(mock.MagicMock(), report, folder, embedded_pictures_only=True)

    results = [painter._bytes(src) for src in ("local.png", "../secret.png", (folder / "local.png").as_uri())]

    assert results == [None, None, None]
    assert report.warnings.count(WARNING) == 3
    assert painter._bytes(DATA_URI) == PNG_1X1
    default: Any = pptx_paint.Painter(mock.MagicMock(), ExportReport(), folder)
    assert default._bytes("local.png") == SECRET
