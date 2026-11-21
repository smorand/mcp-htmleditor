"""SPEC-0033 (US-0171): the four render limits.

E2E-001 to E2E-009. A slide below the window is pictured, the system font stack is not reported, a script error is
one line, a missing image is one line per slide and address (an empty address is named). Real headless Chromium,
through the command line in a worker thread as in ``tests/test_render_report.py``.
"""

from __future__ import annotations

import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests import render_support as rs
from tests.deck_support import run_cli as _run_cli
from tests.deck_support import write_deck

pytestmark = rs.needs_chromium

RED = (255, 0, 0)
RED_BLOCK = '<div style="width:100px;height:100px;background:#FF0000"></div>'
FONT_LINE = "font slide-0: "


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture(autouse=True)
def out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path / "htmleditor-render"


def mini_deck(slide_0: str = "", slide_1: str | None = None, script: str = "") -> str:
    """A minimal presentation of one or two 960 by 540 slides ``slide-0``, ``slide-1`` holding the given markup."""
    slides = [slide_0] if slide_1 is None else [slide_0, slide_1]
    articles = "".join(
        f'<article class="slide{" active" if i == 0 else ""}" id="slide-{i}" data-type="slide" data-id="slide-{i}"'
        f' data-title="S{i}" style="width:960px;height:540px;position:relative">{body}</article>'
        for i, body in enumerate(slides)
    )
    return (
        '<!DOCTYPE html><html data-doc-type="presentation"><head><meta charset="utf-8"><title>t</title>'
        "<style>.slide{display:none}.slide.active{display:block}</style></head>"
        f"<body>{articles}{'<script>' + script + '</script>' if script else ''}</body></html>"
    )


def deck(tmp_path: Path, html: str) -> str:
    return write_deck(tmp_path / "DECK.html", html)


def with_tall_block(html: str, height: int) -> str:
    html = html.replace("</head>", "<style>body{margin:0}</style></head>", 1)
    return re.sub(r"(<body[^>]*>)", rf'\1<div style="height:{height}px"></div>', html, count=1)


def lines(stdout: str, kind: str) -> list[str]:
    return [line for line in stdout.splitlines() if line.startswith(f"{kind} ")]


def red_pixels(path: Path) -> int:
    from PIL import Image

    with Image.open(path) as image:
        return sum(1 for pixel in image.convert("RGB").getdata() if pixel == RED)


def render_picture(tmp_path: Path, html: str, *flags: str) -> tuple[Path, str]:
    stdout, stderr, status = run_cli("render", deck(tmp_path, html), "--slide", "slide-0", *flags)
    assert (stderr, status) == ("", 0), stdout
    match = re.match(r"Rendered slide-0 to (.+) \((\d+)x(\d+)\)\n$", stdout)
    assert match, stdout
    return Path(match.group(1)), stdout


def test_e2e_001_a_slide_below_the_window_is_pictured(tmp_path: Path) -> None:
    html = mini_deck(RED_BLOCK)

    picture, stdout = render_picture(tmp_path, with_tall_block(html, 1200))

    assert stdout.endswith("(480x270)\n")
    assert red_pixels(picture) >= 1000


def test_e2e_007_the_picture_is_the_slide(tmp_path: Path) -> None:
    from PIL import Image, ImageChops

    html = mini_deck(RED_BLOCK)
    below, _ = render_picture(tmp_path, with_tall_block(html, 1200), "--scale", "1")
    copy = tmp_path / "below.png"
    copy.write_bytes(below.read_bytes())
    plain, _ = render_picture(tmp_path, html, "--scale", "1")

    with Image.open(copy) as first, Image.open(plain) as second:
        assert first.size == second.size == (960, 540)
        assert ImageChops.difference(first.convert("RGB"), second.convert("RGB")).getbbox() is None


def test_e2e_008_the_slide_starts_exactly_at_the_bottom_edge(tmp_path: Path) -> None:
    html = mini_deck(RED_BLOCK)
    top = _slide_top(tmp_path, html)

    picture, _ = render_picture(tmp_path, with_tall_block(html, 900 - top))

    assert red_pixels(picture) >= 1000


def _slide_top(tmp_path: Path, html: str) -> int:
    """The top edge of slide 0 in the 900 pixel window without the tall block (body margin 0)."""
    from playwright.sync_api import sync_playwright

    page_file = tmp_path / "measure.html"
    page_file.write_text(with_tall_block(html, 0), encoding="utf-8")

    def measure() -> int:
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(page_file.as_uri())
            page.evaluate("document.querySelectorAll('[data-type=\"slide\"]')[0].style.display='block'")
            top = page.locator('[data-type="slide"]').first.bounding_box()["y"]  # type: ignore[index]
            browser.close()
            return round(top)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(measure).result()


@pytest.mark.parametrize(
    "family",
    [
        "-apple-system, BlinkMacSystemFont, sans-serif",
        "ui-sans-serif, ui-serif, ui-monospace, ui-rounded",
        "cursive, fantasy, emoji, math, fangsong, system-ui",
    ],
    ids=["system stack", "ui families", "other generics"],
)
def test_e2e_002_generic_and_system_font_names_are_not_reported(tmp_path: Path, family: str) -> None:
    html = mini_deck(f'<p style="font-family:{family}">Texte</p>')

    stdout, _, _ = run_cli("render", deck(tmp_path, html), "--slide", "slide-0", "--report")

    assert lines(stdout, "font") == []


def test_e2e_003_a_named_font_after_generic_ones_is_reported_once(tmp_path: Path) -> None:
    first = mini_deck("<p style=\"font-family:-APPLE-SYSTEM, 'Nope Sans', sans-serif\">Texte</p>")
    second = mini_deck("<p style=\"font-family:'Nope Sans', 'Other Nope', 'sans-serif', serif\">Texte</p>")

    one, _, _ = run_cli("render", deck(tmp_path, first), "--slide", "slide-0", "--report")
    two, _, _ = run_cli("render", deck(tmp_path, second), "--slide", "slide-0", "--report")

    assert lines(one, "font") == [f'{FONT_LINE}"Nope Sans" is not available, fallback used']
    assert lines(two, "font") == [f'{FONT_LINE}"Nope Sans" is not available, fallback used']


@pytest.mark.parametrize(
    ("throw", "expected"),
    [
        ('new Error("first line\\r\\nsecond line  ")', "Error: first line second line"),
        ('new Error("a\\tb\\n\\nc")', "Error: a b c"),
        ('new Error("x\\u00a0y")', "Error: x y"),
    ],
    ids=["crlf and trailing spaces", "tabs and blank lines", "non breaking space"],
)
def test_e2e_004_a_script_error_is_one_line(tmp_path: Path, throw: str, expected: str) -> None:
    html = mini_deck("", None, f"throw {throw};")

    stdout, _, _ = run_cli("render", deck(tmp_path, html), "--slide", "slide-0", "--report")

    assert lines(stdout, "script") == [f"script -: {expected}"]


def test_e2e_009_the_same_script_error_twice_is_one_line(tmp_path: Path) -> None:
    two_scripts = (
        "throw new Error('first line\\nsecond line');</script><script>throw new Error('first line second line');"
    )
    html = mini_deck("", None, two_scripts)

    stdout, _, _ = run_cli("render", deck(tmp_path, html), "--slide", "slide-0", "--report")

    assert lines(stdout, "script") == ["script -: Error: first line second line"]


def _img(src: str) -> str:
    return f'<img src="{src}" alt="x">'


def test_e2e_005_a_missing_image_is_one_line_per_slide_and_address(tmp_path: Path) -> None:
    html = mini_deck(_img("missing.png") + _img("other.png") + _img("missing.png"), _img("missing.png"))

    stdout, _, _ = run_cli("render", deck(tmp_path, html), "--report-only")

    assert lines(stdout, "image") == [
        "image slide-0: missing.png did not load",
        "image slide-0: other.png did not load",
        "image slide-1: missing.png did not load",
    ]


def test_e2e_005_two_data_addresses_that_print_alike_are_two_lines(tmp_path: Path) -> None:
    head = "data:image/png;base64," + "A" * 18  # 40 characters: the printed form keeps exactly these
    html = mini_deck(_img(head + "xx11") + _img(head + "yy22"))

    stdout, _, _ = run_cli("render", deck(tmp_path, html), "--report-only")

    assert lines(stdout, "image") == [f"image slide-0: {head}... did not load"] * 2


def test_e2e_005_mixed_repeats_keep_the_order_of_first_use(tmp_path: Path) -> None:
    data = "data:image/png;base64,AAAA"
    html = mini_deck(_img("missing.png") + _img(data) + _img(data), _img("missing.png"))

    stdout, _, _ = run_cli("render", deck(tmp_path, html), "--report-only")

    assert lines(stdout, "image") == [
        "image slide-0: missing.png did not load",
        f"image slide-0: {data} did not load",
        "image slide-1: missing.png did not load",
    ]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (_img(""), ["image slide-0: (empty address) did not load"]),
        (
            _img("") + _img("missing.png"),
            ["image slide-0: (empty address) did not load", "image slide-0: missing.png did not load"],
        ),
        (_img("") + _img(""), ["image slide-0: (empty address) did not load"]),
    ],
    ids=["alone", "before a missing image", "twice"],
)
def test_e2e_006_an_empty_address_is_named(tmp_path: Path, body: str, expected: list[str]) -> None:
    html = mini_deck(body)

    stdout, _, _ = run_cli("render", deck(tmp_path, html), "--report-only")

    assert lines(stdout, "image") == expected
