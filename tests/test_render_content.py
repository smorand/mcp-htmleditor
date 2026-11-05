"""US-0067: what a picture contains (SPEC-0008 FR-NEW-001: entrance animation finished, nothing but the slide)."""

from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from tests import render_support as rs
from tests.deck_support import run_cli as _run_cli
from tests.deck_support import write_deck

BLUE = (0, 0, 255)
GREEN = (0, 200, 0)
MAGENTA = (255, 0, 255)
INSET = 2
WIDTH, HEIGHT = 480, 270


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture(autouse=True)
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path / "htmleditor-render"


def _cover(colour: str) -> str:
    return f'<div style="position:absolute;inset:0;z-index:99;background:{colour}"></div>'


def _pixels(path) -> list[tuple[int, int, int]]:
    with Image.open(path) as image:
        raw = image.convert("RGB").tobytes()
    return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]


def _sample_points() -> list[tuple[int, int]]:
    right, bottom = WIDTH - 1 - INSET, HEIGHT - 1 - INSET
    return [(INSET, INSET), (right, INSET), (INSET, bottom), (right, bottom), (WIDTH // 2, HEIGHT // 2)]


@rs.needs_chromium
def test_picture_is_taken_after_the_entrance_animation(tmp_path, out_dir):
    html = rs.ei_deck_html().replace(
        "</head>",
        "<style>@keyframes ent{from{opacity:0}to{opacity:1}}"
        "#slide-2{position:relative;animation:ent 700ms}</style></head>",
        1,
    )
    html = rs.append_to_slide(html, "slide-2", _cover("rgb(0,0,255)"))
    file = write_deck(tmp_path / "ANIM.html", html)
    stdout, stderr, status = run_cli("render", file, "--slide", "slide-2", "--scale", "0.5")
    assert (stderr, status) == ("", 0), stdout
    picture = out_dir / "ANIM-slide-2.png"
    for x, y in _sample_points():
        assert rs.png_pixel(picture, x, y) == BLUE, (x, y)


@rs.needs_chromium
def test_picture_holds_nothing_but_the_slide(tmp_path, out_dir):
    html = rs.ei_deck_html().replace(
        '<div class="slide-frame">',
        f'<div style="height:60px;background:rgb{MAGENTA}"></div><div class="slide-frame">',
        1,
    )
    html = html.replace("</head>", "<style>#slide-0,#slide-1{position:relative}</style></head>", 1)
    html = rs.append_to_slide(html, "slide-0", _cover("rgb(0,0,255)"))
    html = rs.append_to_slide(html, "slide-1", _cover("rgb(0,200,0)"))
    file = write_deck(tmp_path / "ONLY.html", html)

    for slide_id, colour in (("slide-0", BLUE), ("slide-1", GREEN)):
        stdout, stderr, status = run_cli("render", file, "--slide", slide_id, "--scale", "0.5")
        assert (stderr, status) == ("", 0), stdout
        picture = out_dir / f"ONLY-{slide_id}.png"
        assert rs.png_size(picture) == (WIDTH, HEIGHT)
        for x, y in _sample_points():
            assert rs.png_pixel(picture, x, y) == colour, (slide_id, x, y)
        assert MAGENTA not in _pixels(picture), slide_id
