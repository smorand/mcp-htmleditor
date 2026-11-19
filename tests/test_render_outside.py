"""SPEC-0026 (US-0153): ``render`` aborts every file request outside the deck's folder.

The effect is read in the pixels of the rendered PNG (a second channel: the report only says an image did not load).
"""

from __future__ import annotations

import io
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

from tests.deck_support import run_cli as _run_cli
from tests.render_support import needs_chromium


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture(autouse=True)
def out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path / "htmleditor-render"


RED = (255, 0, 0)
BLUE = (0, 0, 255)


def solid_png(colour: tuple[int, int, int], size: int = 200) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (size, size), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def make_deck(tmp_path: Path, body: str, head: str = "") -> Path:
    folder = tmp_path / "deck"
    folder.mkdir(exist_ok=True)
    path = folder / "deck.html"
    path.write_text(
        f'<!DOCTYPE html><html data-doc-type="presentation"><head>{head}</head><body>'
        f'<section class="slide active" data-type="slide" data-id="slide-1" data-title="One"><h1>One</h1>{body}'
        "</section></body></html>",
        encoding="utf-8",
    )
    return path


def render(deck: Path, *flags: str) -> tuple[dict[str, object], set[tuple[int, int, int]]]:
    stdout, stderr, code = run_cli("render", str(deck), "--slide", "slide-1", "--json", *flags)
    assert stdout, f"render exited {code}: {stderr}"
    result = json.loads(stdout)
    assert result["path"], stderr
    with Image.open(str(result["path"])) as image:
        return result, {colour for _, colour in image.convert("RGB").getcolors(maxcolors=1_000_000)}


@needs_chromium
def test_bt014_an_outside_picture_is_not_painted_and_is_reported_as_not_loaded(tmp_path: Path) -> None:
    (tmp_path / "secret.png").write_bytes(solid_png(RED))
    deck = make_deck(tmp_path, '<img src="../secret.png" style="width:200px;height:200px">')

    result, colours = render(deck, "--report")

    assert RED not in colours
    assert {"kind": "image", "slide": "slide-1", "message": "../secret.png did not load"} in result["problems"]  # type: ignore[operator]


@needs_chromium
def test_bt017_an_outside_style_sheet_and_an_outside_frame_are_not_loaded(tmp_path: Path) -> None:
    (tmp_path / "out.css").write_text(".slide{background:#0000FF}", encoding="utf-8")
    (tmp_path / "frame.html").write_text('<body style="background:#FF0000">frame</body>', encoding="utf-8")
    deck = make_deck(
        tmp_path,
        '<iframe src="../frame.html" style="width:200px;height:200px"></iframe>',
        head='<link rel="stylesheet" href="../out.css">',
    )

    _, colours = render(deck)

    assert BLUE not in colours
    assert RED not in colours


@needs_chromium
def test_an_inside_picture_still_renders(tmp_path: Path) -> None:
    deck = make_deck(tmp_path, '<img src="a.png" style="width:200px;height:200px">')
    (tmp_path / "deck" / "a.png").write_bytes(solid_png(RED))

    result, colours = render(deck, "--report")

    assert RED in colours
    assert result["problems"] == []


@needs_chromium
def test_bt021_a_symlink_is_judged_by_where_it_leads(tmp_path: Path) -> None:
    """BR-006 on the render: a link to an outside picture is not painted, a link to an inside one is."""
    (tmp_path / "secret.png").write_bytes(solid_png(RED))
    deck = make_deck(tmp_path, '<img src="leak.png" style="width:200px;height:200px">')
    (tmp_path / "deck" / "leak.png").symlink_to(tmp_path / "secret.png")

    result, colours = render(deck, "--report")

    assert RED not in colours
    assert {"kind": "image", "slide": "slide-1", "message": "leak.png did not load"} in result["problems"]  # type: ignore[operator]
