"""SPEC-0026 (US-0152): the DOCX export embeds no picture outside the deck's folder.

The effect is read in the media parts of the produced DOCX (the bytes of the secret picture are searched for),
never in the warning.
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from mcp_htmleditor.deck_folder import OUTSIDE_PREFIX
from tests.deck_support import run_cli

needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc is not installed")


def png_bytes(colour: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def media(output: Path) -> list[bytes]:
    with zipfile.ZipFile(output) as archive:
        return [archive.read(name) for name in archive.namelist() if name.startswith("word/media/")]


def make_document(tmp_path: Path, sources: list[str]) -> Path:
    folder = tmp_path / "deck"
    folder.mkdir(exist_ok=True)
    images = "".join(f'<p><img src="{source}" alt="pic"></p>' for source in sources)
    path = folder / "doc.html"
    path.write_text(
        f'<!DOCTYPE html><html data-doc-type="document"><body><h1>Title</h1><p>text</p>{images}</body></html>',
        encoding="utf-8",
    )
    return path


@needs_pandoc
def test_bt013_outside_pictures_are_not_embedded_and_each_is_named(tmp_path: Path) -> None:
    """BT-013: a climbing path, an absolute path and a file URL, the three ways pandoc reads a file."""
    secret = png_bytes((255, 0, 0))
    (tmp_path / "secret.png").write_bytes(secret)
    path = make_document(tmp_path, ["../secret.png", str(tmp_path / "secret.png"), (tmp_path / "secret.png").as_uri()])
    output = tmp_path / "out.docx"

    _, stderr, code = run_cli("export", "docx", str(path), str(output))

    assert code == 0
    assert secret not in media(output)
    assert sum(line.startswith(f"Attention: {OUTSIDE_PREFIX}") for line in stderr.splitlines()) == 3


@needs_pandoc
def test_an_inside_picture_keeps_its_img(tmp_path: Path) -> None:
    inside = png_bytes((0, 255, 0))
    path = make_document(tmp_path, ["a.png"])
    (tmp_path / "deck" / "a.png").write_bytes(inside)
    output = tmp_path / "out.docx"

    _, stderr, code = run_cli("export", "docx", str(path), str(output))

    assert code == 0
    assert inside in media(output)
    assert OUTSIDE_PREFIX not in stderr


@needs_pandoc
def test_bt013_percent_encoded_payloads_are_refused_too(tmp_path: Path) -> None:
    """Pandoc decodes percent escapes before opening a file: ``%2e%2e/`` and ``..%2F`` climb out as ``../`` does."""
    secret = png_bytes((255, 0, 0))
    (tmp_path / "secret.png").write_bytes(secret)
    path = make_document(tmp_path, ["%2e%2e/secret.png", "..%2Fsecret.png", "%2E%2E/%73ecret.png"])
    output = tmp_path / "out.docx"

    _, stderr, code = run_cli("export", "docx", str(path), str(output))

    assert code == 0
    assert secret not in media(output)
    assert sum(line.startswith(f"Attention: {OUTSIDE_PREFIX}") for line in stderr.splitlines()) == 3


@needs_pandoc
def test_bt021_a_symlink_is_judged_by_where_it_leads(tmp_path: Path) -> None:
    """BR-006 on the DOCX export: a link to an outside file is dropped, a link to an inside file is embedded."""
    secret = png_bytes((255, 0, 0))
    inside = png_bytes((0, 255, 0))
    (tmp_path / "secret.png").write_bytes(secret)
    path = make_document(tmp_path, ["leak.png", "inner.png"])
    (tmp_path / "deck" / "real.png").write_bytes(inside)
    (tmp_path / "deck" / "leak.png").symlink_to(tmp_path / "secret.png")
    (tmp_path / "deck" / "inner.png").symlink_to(tmp_path / "deck" / "real.png")
    output = tmp_path / "out.docx"

    _, stderr, code = run_cli("export", "docx", str(path), str(output))

    assert code == 0
    assert secret not in media(output)
    assert inside in media(output)
    assert f"Attention: {OUTSIDE_PREFIX}leak.png" in stderr
