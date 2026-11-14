"""SPEC-0023 (US-0120): the PPTX export of a Breathe deck, painted from the rendered slides, and its fallback.

E2E-026 to E2E-033, E2E-046 and E2E-057 (export halves), E2E-050, E2E-062, E2E-066. The painted geometry is checked
against boxes measured independently in Chromium, never against the painter's own measures.
"""

from __future__ import annotations

import http.client
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from mcp_htmleditor.export import pptx_paint
from mcp_htmleditor.export.to_pptx import to_pptx
from mcp_htmleditor.render.scripts import SHOW_SLIDE_JS
from tests.breathe_support import (
    BOOTSTRAP,
    REFERENCE,
    as_medical,
    breathe_deck,
    breathe_slide,
    reference_slide,
    wcbip_or_skip,
)
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import call_tool, run_cli

REPO = Path(__file__).resolve().parents[1]
PX = 12700
DEGRADED = "Deck exported without the rendered finish ({}). Install the browser with: make install-browser"
Shape = tuple[str, int, int, int, int, str]


def write(path: Path, html: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def key_figures_deck(tmp_path: Path) -> Path:
    """NEW with the reference slide `Key figures` added, decoration embedded."""
    deck = write(tmp_path / "talk.html", breathe_deck(reference_slide("Key figures")))
    _, stderr, code = run_cli("breathe-inline", str(deck))
    assert code == 0, stderr
    return deck


def shapes_of(pptx: Path) -> list[list[Shape]]:
    """Per slide: (type, left, top, width, height, text) of every shape, positions in points."""
    return [
        [
            (
                str(shape.shape_type),
                round(shape.left / PX),
                round(shape.top / PX),
                round(shape.width / PX),
                round(shape.height / PX),
                shape.text_frame.text if shape.has_text_frame else "",
            )
            for shape in slide.shapes
        ]
        for slide in Presentation(str(pptx)).slides
    ]


def is_full_slide_picture(shape: Any) -> bool:
    return shape.shape_type == MSO_SHAPE_TYPE.PICTURE and shape.width >= 959 * PX and shape.height >= 539 * PX


def words(text: str) -> list[str]:
    return [w.casefold() for w in re.findall(r"[^\s]+", text)]


def editor_export(served: ServedDeck) -> bytes:
    conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=120)
    try:
        conn.request("GET", "/export/pptx")
        response = conn.getresponse()
        assert response.status == 200
        return response.read()
    finally:
        conn.close()


# -- painted ------------------------------------------------------------------------------------------------


@needs_chromium
def test_painted_from_every_surface(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    """E2E-026: command line, agent tool and editor give the same painted PPTX."""
    deck = key_figures_deck(tmp_path)
    cli_out, tool_out, editor_out = tmp_path / "cli.pptx", tmp_path / "tool.pptx", tmp_path / "editor.pptx"
    stdout, _, code = run_cli("export", "pptx", str(deck), str(cli_out))
    assert code == 0
    assert stdout.splitlines()[-1] == "Done. 2 slide(s) exportee(s)."
    ok, data = call_tool("export", file=str(deck), format="pptx", output=str(tool_out))
    assert ok, data
    assert data["warnings"] == []
    editor_out.write_bytes(editor_export(serve_deck(deck)))
    slides = Presentation(str(cli_out)).slides
    assert len(slides) == 2
    for slide in slides:
        assert is_full_slide_picture(next(iter(slide.shapes)))
    title_runs = [
        run
        for shape in slides[1].shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
        if run.text.strip() in {"The title states", "the message", "The title states the", "message"}
    ]
    assert title_runs
    assert {run.font.name for run in title_runs} == {"Georgia"}
    title_text = " ".join(" ".join(words(s.text_frame.text)) for s in slides[1].shapes if s.has_text_frame)
    assert "the title states the message" in title_text
    assert shapes_of(cli_out) == shapes_of(tool_out) == shapes_of(editor_out)


IMG_BOXES = """(index) => {
  const slide = document.querySelectorAll('[data-type="slide"]')[index];
  const S = slide.getBoundingClientRect();
  return Array.from(slide.querySelectorAll('img')).filter((i) => i.getClientRects().length).map((i) => {
    const r = i.getBoundingClientRect();  // the picture's content box: its border is painted as rectangles
    const c = getComputedStyle(i), n = (v) => parseFloat(v) || 0;
    const left = n(c.borderLeftWidth) + n(c.paddingLeft), top = n(c.borderTopWidth) + n(c.paddingTop);
    const right = n(c.borderRightWidth) + n(c.paddingRight), bottom = n(c.borderBottomWidth) + n(c.paddingBottom);
    return [r.left - S.left + left, r.top - S.top + top, r.width - left - right, r.height - top - bottom];
  });
}"""


def rendered_picture_boxes(deck: Path, count: int) -> list[list[list[float]]]:
    """Picture boxes of every slide, measured in a separate Chromium page (the independent channel)."""
    with ThreadPoolExecutor(max_workers=1) as pool:  # a page fixture of the session may hold this thread's loop
        return pool.submit(_picture_boxes, deck, count).result()


def _picture_boxes(deck: Path, count: int) -> list[list[list[float]]]:
    with sync_playwright() as driver:
        browser = driver.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(deck.resolve().as_uri(), wait_until="load")
        page.add_style_tag(content=".slide{scale:1!important}*{animation:none!important;transition:none!important}")
        boxes = []
        for index in range(count):
            page.evaluate(pptx_paint.UNHIDE_JS)
            page.evaluate(SHOW_SLIDE_JS, index)
            boxes.append(page.evaluate(IMG_BOXES, index))
        browser.close()
    return boxes


@needs_chromium
def test_reference_deck_painted(tmp_path: Path) -> None:
    """E2E-027: 23 painted slides within 60 s, every text present, faces, pictures within 1 point."""
    deck = write(tmp_path / "ref.html", REFERENCE.read_text(encoding="utf-8"))
    out = tmp_path / "ref.pptx"
    started = time.monotonic()
    report = to_pptx(str(deck), str(out))
    assert time.monotonic() - started < 60
    assert report.warnings == []
    slides = list(Presentation(str(out)).slides)
    assert len(slides) == 23
    articles = BeautifulSoup(deck.read_text(encoding="utf-8"), "html.parser").find_all(attrs={"data-type": "slide"})
    expected_boxes = rendered_picture_boxes(deck, 23)
    faces: set[str] = set()
    tables = 0
    for index, (slide, article) in enumerate(zip(slides, articles, strict=True)):
        shapes = list(slide.shapes)
        assert is_full_slide_picture(shapes[0]), index
        assert len(shapes) > 1, index
        for aside in article.select('[data-role="speaker-notes"]'):
            aside.decompose()
        painted = "".join(w for s in shapes if s.has_text_frame for w in words(s.text_frame.text))
        painted += "".join(  # native tables (SPEC-0024 FR-5) hold their words in cells
            w for s in shapes if s.has_table for row in s.table.rows for c in row.cells for w in words(c.text)
        )
        tables += sum(1 for s in shapes if s.has_table)
        missing = [w for w in words(article.get_text(" ")) if w not in painted]  # tags split words: "clinical", "."
        assert missing == [], (index, missing)
        faces |= {r.font.name for s in shapes if s.has_text_frame for p in s.text_frame.paragraphs for r in p.runs}
        pictures = [
            [s.left / PX, s.top / PX, s.width / PX, s.height / PX]
            for s in shapes[1:]
            if s.shape_type == MSO_SHAPE_TYPE.PICTURE
        ]
        for box in expected_boxes[index]:
            assert any(all(abs(a - b) <= 1 for a, b in zip(box, pic, strict=True)) for pic in pictures), (index, box)
    assert tables >= 1
    assert faces == {"Georgia", "Trebuchet MS"}


@needs_chromium
def test_accents_and_ampersand(tmp_path: Path) -> None:
    """E2E-028."""
    deck = write(tmp_path / "t.html", breathe_deck(breathe_slide("Diagnostic précoce &amp; accès")))
    to_pptx(str(deck), str(tmp_path / "t.pptx"))
    texts = [s.text_frame.text for s in Presentation(str(tmp_path / "t.pptx")).slides[1].shapes if s.has_text_frame]
    assert "Diagnostic précoce & accès" in texts


NOTES = "Good morning.\n\nSecond paragraph."


@needs_chromium
def test_notes_reach_the_notes_pages(tmp_path: Path) -> None:
    """E2E-029 and E2E-030: the aside text unchanged; no notes page without an aside or with a blank one."""
    second = breathe_slide("Two").replace('      <aside data-role="speaker-notes"></aside>\n', "")
    third = breathe_slide("Three", notes="   ")
    html = breathe_deck(second, third).replace(
        '<aside data-role="speaker-notes"></aside>', f'<aside data-role="speaker-notes">{NOTES}</aside>', 1
    )
    deck = write(tmp_path / "n.html", html)
    to_pptx(str(deck), str(tmp_path / "n.pptx"))
    slides = Presentation(str(tmp_path / "n.pptx")).slides
    assert slides[0].notes_slide.notes_text_frame.text == NOTES
    assert not slides[1].has_notes_slide
    assert not slides[2].has_notes_slide


@needs_chromium
def test_remote_picture_skipped(tmp_path: Path) -> None:
    """E2E-031."""
    remote = "https://example.org/x.png"
    deck = write(tmp_path / "r.html", breathe_deck(breathe_slide("R", f'<img src="{remote}" alt="r">')))
    assert run_cli("breathe-inline", str(deck))[2] == 0
    report = to_pptx(str(deck), str(tmp_path / "r.pptx"))
    slide = Presentation(str(tmp_path / "r.pptx")).slides[1]
    assert sum(1 for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE) == 1  # the background only
    assert any(remote[:40] in warning for warning in report.warnings)
    assert not any(w.startswith("Deck exported without") for w in report.warnings)


# -- degraded -----------------------------------------------------------------------------------------------


def test_degraded_without_chromium(tmp_path: Path) -> None:
    """E2E-032: the real command, with Playwright pointed at an empty browser folder."""
    deck = BOOTSTRAP.read_text(encoding="utf-8")
    source = write(tmp_path / "talk.html", deck)
    out = tmp_path / "talk.pptx"
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(tmp_path / "no-browsers"), "HTMLEDITOR_LOG_LEVEL": "WARNING"}
    result = subprocess.run(  # noqa: S603 - fixed interpreter and module
        [sys.executable, "-m", "mcp_htmleditor", "export", "pptx", str(source), str(out)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == "Done. 1 slide(s) exportee(s)."
    lines = [line for line in result.stderr.splitlines() if line.startswith("Attention: ")]
    assert lines == [f"Attention: {DEGRADED.format('Chromium is not installed')}"]
    shapes = list(Presentation(str(out)).slides[0].shapes)
    assert is_full_slide_picture(shapes[0])
    assert not any(s.width >= 959 * PX for s in shapes[1:])  # no band or footer of another charter
    faces = {r.font.name for s in shapes if s.has_text_frame for p in s.text_frame.paragraphs for r in p.runs}
    assert faces == {"Trebuchet MS"}


def test_degraded_without_the_render_extra(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """E2E-033."""
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    source = write(tmp_path / "talk.html", BOOTSTRAP.read_text(encoding="utf-8"))
    report = to_pptx(str(source), str(tmp_path / "talk.pptx"))
    assert report.warnings == [DEGRADED.format("the render extra is not installed")]
    assert report.slide_count == 1


def failing_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chromium starts but the render of a slide fails (E2E-062)."""

    def boom(browser: Any, html_path: Path, count: int, events: Any) -> list[list[dict[str, Any]]]:
        raise RuntimeError("slide 2 could not be rendered\nsecond line")

    monkeypatch.setattr(pptx_paint, "_measure_pages", boom)


@needs_chromium
def test_render_failure_takes_the_degraded_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """E2E-062."""
    failing_render(monkeypatch)
    deck = key_figures_deck(tmp_path)
    stdout, stderr, code = run_cli("export", "pptx", str(deck), str(tmp_path / "f.pptx"))
    assert code == 0
    assert stdout.splitlines()[-1] == "Done. 2 slide(s) exportee(s)."
    reason = "the render failed: slide 2 could not be rendered"
    assert [line for line in stderr.splitlines() if line.startswith("Attention: ")] == [
        f"Attention: {DEGRADED.format(reason)}"
    ]
    for slide in Presentation(str(tmp_path / "f.pptx")).slides:
        assert any(is_full_slide_picture(s) for s in slide.shapes)


@needs_chromium
def test_degraded_export_equal_on_every_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-050 and E2E-066: with the finish unavailable, the editor and the tool equal the command line."""
    failing_render(monkeypatch)
    deck = key_figures_deck(tmp_path)
    cli_out, tool_out, editor_out = tmp_path / "cli.pptx", tmp_path / "tool.pptx", tmp_path / "editor.pptx"
    run_cli("export", "pptx", str(deck), str(cli_out))
    ok, data = call_tool("export", file=str(deck), format="pptx", output=str(tool_out))
    assert ok
    assert data["warnings"] == [DEGRADED.format("the render failed: slide 2 could not be rendered")]
    editor_out.write_bytes(editor_export(serve_deck(deck)))
    assert shapes_of(cli_out) == shapes_of(tool_out) == shapes_of(editor_out)


def test_measure_reasons(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The launch failures map to their reasons (FR-NEW-016)."""
    from playwright.sync_api import Error

    class Driver:
        def __init__(self, message: str) -> None:
            self.message = message
            self.chromium = self

        def launch(self) -> None:
            raise Error(self.message)

        def __enter__(self) -> Driver:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    for message, reason in (
        ("Executable doesn't exist at /x/chrome", "Chromium is not installed"),
        ("sandbox refused\nmore", "Chromium could not start: sandbox refused"),
    ):
        monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda m=message: Driver(m))
        with pytest.raises(pptx_paint.PaintUnavailable) as caught:
            pptx_paint.measure(tmp_path / "x.html", 1)
        assert caught.value.reason == reason


# -- switching decks (export halves of E2E-046 and E2E-057) --------------------------------------------------


@needs_chromium
def test_reference_declared_medical_then_switched(tmp_path: Path) -> None:
    ref_med = as_medical(REFERENCE.read_text(encoding="utf-8"))
    medical = write(tmp_path / "ref-med.html", ref_med)
    # SPEC-0024: the painted export draws what the HTML shows; the charter dispatch is the flow build (degraded result)
    assert to_pptx(str(medical), str(tmp_path / "ref-med-painted.pptx")).charter == "medical"
    to_pptx(str(medical), str(tmp_path / "ref-med.pptx"), paint=False)
    assert not any(
        is_full_slide_picture(next(iter(s.shapes))) for s in Presentation(str(tmp_path / "ref-med.pptx")).slides
    )
    switched = write(
        tmp_path / "switched.html", ref_med.replace('data-doc-template="medical"', 'data-doc-template="breathe"', 1)
    )
    report = to_pptx(str(switched), str(tmp_path / "switched.pptx"))
    assert report.warnings == []
    slides = Presentation(str(tmp_path / "switched.pptx")).slides
    assert len(slides) == 23
    assert all(is_full_slide_picture(next(iter(s.shapes))) for s in slides)


@needs_chromium
def test_wcbip_switched_is_painted_with_its_notes(tmp_path: Path) -> None:
    original = wcbip_or_skip()
    as_is = write(tmp_path / "wcbip.html", original)
    to_pptx(str(as_is), str(tmp_path / "wcbip.pptx"), paint=False)  # the flow build keys on the declared charter
    assert not any(
        is_full_slide_picture(next(iter(s.shapes))) for s in Presentation(str(tmp_path / "wcbip.pptx")).slides
    )
    switched = write(
        tmp_path / "switched.html", original.replace('data-doc-template="medical"', 'data-doc-template="breathe"', 1)
    )
    to_pptx(str(switched), str(tmp_path / "switched.pptx"))
    slides = Presentation(str(tmp_path / "switched.pptx")).slides
    assert len(slides) == 14
    assert all(is_full_slide_picture(next(iter(s.shapes))) for s in slides)
    assert sum(1 for s in slides if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip()) == 14


@needs_chromium
def test_a_slide_over_the_bound_takes_the_degraded_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-NEW-016: a slide whose render exceeds the bound (30 s, 1 s here) degrades the whole export."""
    monkeypatch.setattr(pptx_paint, "SLIDE_TIMEOUT_S", 1, raising=False)
    measure_slide = pptx_paint._measure_slide

    def slow(page: Any, index: int) -> list[dict[str, Any]]:
        if index == 1:
            time.sleep(3)
        return measure_slide(page, index)

    monkeypatch.setattr(pptx_paint, "_measure_slide", slow)
    deck = key_figures_deck(tmp_path)
    started = time.monotonic()
    report = to_pptx(str(deck), str(tmp_path / "slow.pptx"))
    assert report.warnings == [DEGRADED.format("the render failed: slide 2 did not render within 1 seconds")]
    assert time.monotonic() - started < 30
    for slide in Presentation(str(tmp_path / "slow.pptx")).slides:
        assert any(is_full_slide_picture(s) for s in slide.shapes)


BOXES_AND_TEXTS = """(index) => {
  const slide = document.querySelectorAll('[data-type="slide"]')[index];
  const S = slide.getBoundingClientRect();
  const n = (v) => parseFloat(v) || 0;
  const boxes = Array.from(slide.querySelectorAll('*')).filter((el) => {
    const c = getComputedStyle(el), m = c.backgroundColor.match(/rgba?\\(([^)]+)\\)/);
    const alpha = m ? (m[1].split(/[\\s,\\/]+/).filter(Boolean)[3] ?? '1') : '0';
    return el.getClientRects().length && parseFloat(alpha) > 0 && c.display !== 'inline';
  }).map((el) => {
    const r = el.getBoundingClientRect(), c = getComputedStyle(el);
    const bl = n(c.borderLeftWidth), bt = n(c.borderTopWidth);
    const br = n(c.borderRightWidth), bb = n(c.borderBottomWidth);
    return [r.left - S.left + bl, r.top - S.top + bt, r.width - bl - br, r.height - bt - bb];
  });
  const texts = Array.from(slide.querySelectorAll('.med-title, .med-kicker')).filter((el) => el.getClientRects().length
    && getComputedStyle(el).textAlign !== 'center').map((el) => {
    const range = document.createRange(); range.selectNodeContents(el);
    const t = range.getBoundingClientRect(), r = el.getBoundingClientRect(), c = getComputedStyle(el);
    return {text: el.textContent.trim().split(/\\s+/).join(' '), left: t.left - S.left, width: t.width,
            top: r.top - S.top + n(c.borderTopWidth) + n(c.paddingTop)};
  });
  return {boxes, texts};
}"""


def _boxes_and_texts(deck: Path, count: int) -> list[dict[str, Any]]:
    def work() -> list[dict[str, Any]]:
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(deck.resolve().as_uri(), wait_until="load")
            page.add_style_tag(content=".slide{scale:1!important}*{animation:none!important;transition:none!important}")
            found = []
            for index in range(count):
                page.evaluate(pptx_paint.UNHIDE_JS)
                page.evaluate(SHOW_SLIDE_JS, index)
                found.append(page.evaluate(BOXES_AND_TEXTS, index))
            browser.close()
            return found

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(work).result()


@needs_chromium
def test_painted_boxes_text_crop_and_spacing(tmp_path: Path) -> None:
    """FR-NEW-014: coloured boxes within 1 point, left aligned text boxes start at their text and are wide enough,
    cover pictures cropped like the browser, letter spacing kept."""
    deck = write(tmp_path / "ref.html", REFERENCE.read_text(encoding="utf-8"))
    to_pptx(str(deck), str(tmp_path / "ref.pptx"))
    slides = list(Presentation(str(tmp_path / "ref.pptx")).slides)
    expected = _boxes_and_texts(deck, len(slides))
    checked_boxes = checked_texts = 0
    for index, (slide, wanted) in enumerate(zip(slides, expected, strict=True)):
        shapes = list(slide.shapes)
        rects = [
            [s.left / PX, s.top / PX, s.width / PX, s.height / PX]
            for s in shapes
            if s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
        ]
        tables = [[s.left / PX, s.top / PX, s.width / PX, s.height / PX] for s in shapes if s.has_table]
        for box in wanted["boxes"]:
            if any(  # a cell fill of a native table lives in the table frame, not in a rectangle
                t[0] - 1 <= box[0]
                and t[1] - 1 <= box[1]
                and box[0] + box[2] <= t[0] + t[2] + 1
                and box[1] + box[3] <= t[1] + t[3] + 1
                for t in tables
            ):
                checked_boxes += 1
                continue
            assert any(all(abs(a - b) <= 1 for a, b in zip(box, rect, strict=True)) for rect in rects), (index, box)
            checked_boxes += 1
        frames = [s for s in shapes if s.shape_type == MSO_SHAPE_TYPE.TEXT_BOX]
        for text in wanted["texts"]:
            matches = [f for f in frames if " ".join(f.text_frame.text.split()).casefold() == text["text"].casefold()]
            assert matches, (index, text, [f.text_frame.text for f in frames])
            frame = matches[0]
            assert abs(frame.left / PX - text["left"]) <= 1, (index, text)
            assert abs(frame.top / PX - text["top"]) <= 1, (index, text)
            assert frame.width / PX >= text["width"] - 1, (index, text)
            checked_texts += 1
    assert checked_boxes > 20
    assert checked_texts > 20
    # framed photo: 300 x 300 with a 6 px border, a 288 x 288 content box: the 1200 x 900 sample loses its sides
    photo = next(s for s in slides[22].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE and round(s.width / PX) == 288)
    assert (round(photo.crop_left, 3), round(photo.crop_right, 3), photo.crop_top) == (0.125, 0.125, 0)
    kicker_runs = [
        r
        for s in slides[0].shapes
        if s.has_text_frame
        for p in s.text_frame.paragraphs
        for r in p.runs
        if r.text.isupper()
    ]
    assert kicker_runs
    assert all(int(r._r.get_or_add_rPr().get("spc")) > 0 for r in kicker_runs)


@needs_chromium
def test_missing_and_vector_pictures_skipped(tmp_path: Path) -> None:
    """FR-NEW-014, SPEC-0024 FR-4: a missing linked picture is skipped with a warning, a vector picture rasterised."""
    svg = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnLz4="
    body = f'<img src="assets/missing.png" alt="m"><img src="{svg}" alt="v" style="width:40px;height:40px">'
    deck = write(tmp_path / "p.html", breathe_deck(breathe_slide("P", body)))
    assert run_cli("breathe-inline", str(deck))[2] == 0
    report = to_pptx(str(deck), str(tmp_path / "p.pptx"))
    slide = Presentation(str(tmp_path / "p.pptx")).slides[1]
    # the background and the vector image, which the browser rasterises (SPEC-0024 FR-4); the missing file is skipped
    assert sum(1 for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE) == 2
    assert any(w.startswith("Image introuvable, ignoree: ") and w.endswith("missing.png") for w in report.warnings)
    assert not any("SVG" in w or "svg" in w for w in report.warnings)
