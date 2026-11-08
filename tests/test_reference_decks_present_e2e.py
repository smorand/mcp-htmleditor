"""Presentation mode of the reference decks (SPEC-0016/BUG-003, BT-003, BT-017 to BT-020).

Each deck of ``DECKS`` gets two real Chromium tests at 1600x900 (DEC-009): ``file`` opens a copy of
the deck as a ``file://`` URL, ``editor`` shows the copy in the editor page and presents it through
``#present-btn``. Every measure is taken in the deck's own document by ``MEASURE``: ``w`` and ``h``
are the current slide's layout box at scale 1, ``s = min(innerWidth / w, innerHeight / h)``.
Slide heights are fractional (475.8 px) while ``offsetHeight`` is rounded, so while ``--fs-scale``
is set ``w`` and ``h`` are the visible box divided by it, the exact unscaled box.

Two families (DEC-008): a ``shell`` deck marks its current slide ``.slide.active``; a ``stacked``
deck shows every slide one under the other and marks the current one ``data-fs-current`` only while
presenting, its script's ``current`` holding it otherwise. ``current`` below is ``slide-<index>``.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium

REPO_ROOT = Path(__file__).resolve().parents[1]
SLIDES_DIR = REPO_ROOT / "templates" / "reference" / "slides"
WIDTH, HEIGHT = 1600, 900
NARROW_WIDTH = 1200

Deck = tuple[str, str, int]

# (file name, family, slide count).
DECKS: tuple[Deck, ...] = (
    ("ibm-carbon.html", "shell", 9),
    ("example-ei-complete.html", "shell", 9),
    ("example-carbon-complete.html", "shell", 9),
    ("presentation-standard.html", "stacked", 4),
    ("roadmap-one-pager.html", "stacked", 1),
)
# BT-018: one deck of each family, left while presenting slide 3.
LEAVING_DECKS: tuple[Deck, ...] = (DECKS[1], DECKS[3])
STACKED_MARKER = "data-fs-current"

# Evaluated with the deck's document as argument (the page's own, or the iframe's).
MEASURE = """
doc => {
  const win = doc.defaultView;
  const slides = [...doc.querySelectorAll('[data-type="slide"]')];
  const marked = doc.querySelector('.slide.active, [data-fs-current]');
  const slide = marked || slides[0];
  const raw = win.getComputedStyle(doc.documentElement).getPropertyValue('--fs-scale').trim();
  const scale = raw === '' ? null : parseFloat(raw);
  const box = slide.getBoundingClientRect();
  const w = scale ? box.width / scale : slide.offsetWidth, h = scale ? box.height / scale : slide.offsetHeight;
  const W = win.innerWidth, H = win.innerHeight;
  const s = Math.min(W / w, H / h);
  const outside = r => r.width === 0 || r.height === 0 || r.right <= 0 || r.bottom <= 0 || r.left >= W || r.top >= H;
  const hidden = el => win.getComputedStyle(el).display === 'none' || outside(el.getBoundingClientRect());
  const shown = [];
  const chrome = ['.toolbar', '.shell-header', '.nav-arrow', '.status-bar', '#btn-present'];
  for (const sel of chrome) doc.querySelectorAll(sel).forEach(el => { if (!hidden(el)) shown.push(sel); });
  slides.forEach((el, i) => { if (el !== marked && !hidden(el)) shown.push('slide-' + i); });
  const intersecting = slides.filter(el => !outside(el.getBoundingClientRect())).length;
  const toolbar = doc.querySelector('.toolbar');
  return {
    fullscreen: doc.fullscreenElement ? doc.fullscreenElement.tagName : null,
    scale, s, w, h, box: [box.width, box.height],
    center: [box.left + box.width / 2, box.top + box.height / 2], viewport: [W, H],
    shown, intersecting, current: marked ? 'slide-' + slides.indexOf(marked) : null,
    toolbar: toolbar ? win.getComputedStyle(toolbar).display : null,
    markers: doc.querySelectorAll('[data-fs-current]').length,
    displays: slides.map(el => win.getComputedStyle(el).display),
    tops: slides.map(el => el.getBoundingClientRect().top),
  };
}
"""

Measure = dict[str, Any]
Observe = Callable[[], Measure]


def _scaled(measure: Measure) -> bool:
    return measure["scale"] is not None and abs(measure["scale"] - measure["s"]) < 1e-6


def _centered(measure: Measure) -> bool:
    """The slide's `fadein` (translateY 6 px for 200 ms) shifts it right after each move."""
    width, height = measure["viewport"]
    return bool(measure["center"] == pytest.approx([width / 2, height / 2], abs=1))


def _assert_presenting(page: Page, observe: Observe, current: str) -> Measure:
    """BR-010 and BR-011: fullscreen, `--fs-scale` equal to s, box w*s by h*s, centered, nothing else shown."""
    measure = wait_until(
        page,
        observe,
        lambda m: m["fullscreen"] == "HTML" and m["current"] == current and _scaled(m) and _centered(m),
        what=f"{current} presenting at the fitted scale, centered",
    )
    assert measure["box"] == pytest.approx([measure["w"] * measure["s"], measure["h"] * measure["s"]], abs=1)
    width, height = measure["viewport"]
    assert min(width - measure["box"][0], height - measure["box"][1]) == pytest.approx(0, abs=1)
    assert measure["shown"] == []
    assert measure["intersecting"] == 1
    return measure


def _assert_left(page: Page, observe: Observe, family: str, index: int) -> None:
    """BR-013: `--fs-scale` gone, slide `index` still current, the layout of before entering."""
    left = wait_until(page, observe, lambda m: m["fullscreen"] is None and m["scale"] is None, what="presenting left")
    if family == "shell":
        assert left["current"] == f"slide-{index}"
        assert left["toolbar"] != "none"
        return
    assert left["markers"] == 0
    assert page.evaluate("current") == index
    assert "none" not in left["displays"]
    assert left["tops"] == sorted(set(left["tops"]))
    wait_until(
        page, observe, lambda m: 0 <= m["tops"][index] < m["viewport"][1], what=f"slide {index + 1} scrolled into view"
    )


def _resize_viewport(page: Page, width: int, height: int) -> None:
    """BT-019's resize. Chromium refuses `page.set_viewport_size` on a fullscreen window
    (`Browser.setWindowBounds`: restore it to normal state first), so the viewport is emulated."""
    session = page.context.new_cdp_session(page)
    session.send(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": height, "deviceScaleFactor": 0, "mobile": False},
    )


def _deck_copy(tmp_path: Path, name: str) -> Path:
    copy = tmp_path / name
    shutil.copyfile(SLIDES_DIR / name, copy)
    return copy


@needs_chromium
@pytest.mark.parametrize("deck", DECKS, ids=[deck[0] for deck in DECKS])
def test_reference_deck_presents_from_file(page: Page, tmp_path: Path, deck: Deck) -> None:
    """BT-003 (file half), BT-017, BT-019, and leaving: the deck opened as a file:// URL."""
    name, family, count = deck
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    page.goto(_deck_copy(tmp_path, name).as_uri())
    observe: Observe = lambda: page.evaluate(f"({MEASURE})(document)")  # noqa: E731
    assert page.locator("#btn-present").count() == 1, f"{name} has no #btn-present"
    last = f"slide-{count - 1}"

    page.click("#btn-present")
    _assert_presenting(page, observe, "slide-0")
    page.keyboard.press("Escape")
    wait_until(page, observe, lambda m: m["fullscreen"] is None, what="presenting left")

    page.evaluate("document.body.focus()")
    page.keyboard.press("f")
    _assert_presenting(page, observe, "slide-0")
    for key, expected in (
        ("End", last),
        ("ArrowLeft", f"slide-{max(count - 2, 0)}"),
        ("Home", "slide-0"),
        ("ArrowLeft", "slide-0"),
    ):
        page.keyboard.press(key)
        _assert_presenting(page, observe, expected)

    wide = _assert_presenting(page, observe, "slide-0")
    _resize_viewport(page, NARROW_WIDTH, HEIGHT)
    narrow = wait_until(
        page, observe, lambda m: m["viewport"] == [NARROW_WIDTH, HEIGHT] and _scaled(m), what="the scale refitted"
    )
    assert narrow["scale"] == pytest.approx(min(NARROW_WIDTH / narrow["w"], HEIGHT / narrow["h"]), abs=1e-6)
    assert narrow["scale"] < wide["scale"]
    _assert_presenting(page, observe, "slide-0")

    page.keyboard.press("End")
    _assert_presenting(page, observe, last)
    page.keyboard.press("Escape")
    _assert_left(page, observe, family, count - 1)


@needs_chromium
@pytest.mark.parametrize("deck", LEAVING_DECKS, ids=[deck[0] for deck in LEAVING_DECKS])
def test_leaving_presenting_keeps_slide_three(page: Page, tmp_path: Path, deck: Deck) -> None:
    """BT-018: presenting on slide 3 (`End`, then `ArrowLeft` until slide 3), `Escape` keeps slide 3."""
    name, family, count = deck
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    page.goto(_deck_copy(tmp_path, name).as_uri())
    observe: Observe = lambda: page.evaluate(f"({MEASURE})(document)")  # noqa: E731
    assert page.locator("#btn-present").count() == 1, f"{name} has no #btn-present"

    page.click("#btn-present")
    _assert_presenting(page, observe, "slide-0")
    page.keyboard.press("End")
    _assert_presenting(page, observe, f"slide-{count - 1}")
    for index in range(count - 2, 1, -1):
        page.keyboard.press("ArrowLeft")
        _assert_presenting(page, observe, f"slide-{index}")
    page.keyboard.press("Escape")
    _assert_left(page, observe, family, 2)


@needs_chromium
@pytest.mark.parametrize("deck", DECKS, ids=[deck[0] for deck in DECKS])
def test_reference_deck_presents_in_editor(
    page: Page,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    serve_deck: Callable[[Path], ServedDeck],
    deck: Deck,
) -> None:
    """BT-003 (editor half) and BT-020: `#present-btn` then `End` with focus in `#content-frame`."""
    name, family, count = deck
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO_ROOT / "templates"))
    config_module.reset_settings_cache()
    served = serve_deck(_deck_copy(tmp_path, name))
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    page.goto(f"http://127.0.0.1:{served.port}/", wait_until="networkidle")
    observe: Observe = lambda: page.evaluate(  # noqa: E731
        f"({MEASURE})(document.getElementById('content-frame').contentDocument)"
    )

    page.click("#present-btn")
    _assert_presenting(page, observe, "slide-0")
    assert page.evaluate("document.activeElement.id") == "content-frame"
    page.keyboard.press("End")
    _assert_presenting(page, observe, f"slide-{count - 1}")
    if family == "stacked":
        # R2: leave, then save the framed document as the editor does; the file keeps no runtime state.
        page.evaluate("document.getElementById('content-frame').contentDocument.exitFullscreen()")
        wait_until(page, observe, lambda m: m["fullscreen"] is None and m["markers"] == 0, what="presenting left")
        page.evaluate("() => saveContent()")
        saved = served.path.read_text(encoding="utf-8")
        assert saved.startswith("<!DOCTYPE html>"), "the editor's save did not land"  # the copy opens with a comment
        soup = BeautifulSoup(saved, "html.parser")
        assert soup.select_one("#btn-present") is not None
        assert soup.find_all(attrs={STACKED_MARKER: True}) == []
        assert soup.html is not None
        assert "--fs-scale" not in str(soup.html.get("style", ""))


STACKED_DECKS: tuple[Deck, ...] = tuple(deck for deck in DECKS if deck[1] == "stacked")
TYPED = "Zq7"
FRAME_EDITABLE = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    " const e = d && d.querySelector('[data-editable~=\"text\"]'); return !!e && e.isContentEditable; }"
)


def _assert_no_presenting_state(saved: str) -> None:
    """R2: a saved file carries no `data-fs-current`, no `--fs-scale` and no empty `style` on <html>."""
    soup = BeautifulSoup(saved, "html.parser")
    assert soup.find_all(attrs={STACKED_MARKER: True}) == []
    assert soup.html is not None
    assert "--fs-scale" not in str(soup.html.get("style", ""))
    assert "style" not in soup.html.attrs, f"<html> kept style={soup.html.get('style')!r}"


@needs_chromium
@pytest.mark.parametrize("deck", STACKED_DECKS, ids=[deck[0] for deck in STACKED_DECKS])
def test_save_while_presenting_writes_no_presenting_state(
    page: Page,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    serve_deck: Callable[[Path], ServedDeck],
    deck: Deck,
) -> None:
    """Design R2: typing while presenting in edit mode, the autosave and an explicit save, then leaving."""
    name, _family, _count = deck
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO_ROOT / "templates"))
    config_module.reset_settings_cache()
    served = serve_deck(_deck_copy(tmp_path, name))
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    page.goto(f"http://127.0.0.1:{served.port}/", wait_until="networkidle")
    observe: Observe = lambda: page.evaluate(  # noqa: E731
        f"({MEASURE})(document.getElementById('content-frame').contentDocument)"
    )
    wait_until(
        page,
        lambda: page.evaluate("document.getElementById('toolbar-filename').textContent"),
        lambda t: t != "\u2014",
        what="the edit button wired",
    )
    page.click("#edit-mode-btn")
    wait_until(page, lambda: page.evaluate(FRAME_EDITABLE), bool, what="edit mode on")

    page.click("#present-btn")
    _assert_presenting(page, observe, "slide-0")
    page.frame_locator("#content-frame").locator('[data-fs-current] [data-editable~="text"]').first.click()
    page.keyboard.type(TYPED)
    autosaved = wait_until(
        page, lambda: served.path.read_text(encoding="utf-8"), lambda text: TYPED in text, what="the autosave"
    )
    assert observe()["fullscreen"] == "HTML", "the autosave did not run while presenting"
    _assert_no_presenting_state(autosaved)

    page.evaluate("() => saveContent()")
    assert observe()["fullscreen"] == "HTML"
    _assert_no_presenting_state(served.path.read_text(encoding="utf-8"))

    page.evaluate("document.getElementById('content-frame').contentDocument.exitFullscreen()")
    wait_until(page, observe, lambda m: m["fullscreen"] is None and m["markers"] == 0, what="presenting left")
    page.evaluate("() => saveContent()")
    _assert_no_presenting_state(served.path.read_text(encoding="utf-8"))


FOCUS_DECKS: tuple[Deck, ...] = (DECKS[1], DECKS[3])


@needs_chromium
@pytest.mark.parametrize("deck", FOCUS_DECKS, ids=[deck[0] for deck in FOCUS_DECKS])
def test_keys_in_an_editable_zone_do_not_present_nor_move(page: Page, tmp_path: Path, deck: Deck) -> None:
    """BR-012 focus clause: with the caret in a contenteditable zone, `f`, `End` and `ArrowRight` are text keys."""
    name, family, _count = deck
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    page.goto(_deck_copy(tmp_path, name).as_uri())
    observe: Observe = lambda: page.evaluate(f"({MEASURE})(document)")  # noqa: E731
    before = observe()["current"]
    zone = page.locator('[data-editable~="text"]').first
    zone.evaluate("el => { el.contentEditable = 'true'; el.focus(); }")
    assert page.evaluate("document.activeElement.isContentEditable")
    for key in ("f", "End", "ArrowRight"):
        page.keyboard.press(key)
    measure = observe()
    assert measure["fullscreen"] is None
    assert measure["current"] == before
    if family == "stacked":
        assert page.evaluate("current") == 0
    assert "f" in zone.text_content()
