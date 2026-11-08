"""Presentation mode of the reference decks (SPEC-0016/BUG-003, BT-003, BT-017, BT-019, BT-020).

Each deck of ``DECKS`` gets two real Chromium tests at 1600x900 (DEC-009): ``file`` opens a copy of
the deck as a ``file://`` URL, ``editor`` shows the copy in the editor page and presents it through
``#present-btn``. Every measure is taken in the deck's own document by ``MEASURE``: ``w`` and ``h``
are the current slide's layout box at scale 1, ``s = min(innerWidth / w, innerHeight / h)``.
Slide heights are fractional (475.8 px) while ``offsetHeight`` is rounded, so while ``--fs-scale``
is set ``w`` and ``h`` are the visible box divided by it, the exact unscaled box.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium

REPO_ROOT = Path(__file__).resolve().parents[1]
SLIDES_DIR = REPO_ROOT / "templates" / "reference" / "slides"
WIDTH, HEIGHT = 1600, 900
NARROW_WIDTH = 1200

Deck = tuple[str, str, int]

# (file name, family, slide count). US-0098 appends the stacked decks.
DECKS: tuple[Deck, ...] = (
    ("ibm-carbon.html", "shell", 9),
    ("example-ei-complete.html", "shell", 9),
    ("example-carbon-complete.html", "shell", 9),
)

# Evaluated with the deck's document as argument (the page's own, or the iframe's).
MEASURE = """
doc => {
  const win = doc.defaultView;
  const slide = doc.querySelector('.slide.active');
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
  doc.querySelectorAll('.slide:not(.active)').forEach(el => { if (!hidden(el)) shown.push(el.id); });
  const intersecting = [...doc.querySelectorAll('.slide')].filter(el => !outside(el.getBoundingClientRect())).length;
  return {
    fullscreen: doc.fullscreenElement ? doc.fullscreenElement.tagName : null,
    scale, s, w, h, box: [box.width, box.height],
    center: [box.left + box.width / 2, box.top + box.height / 2], viewport: [W, H],
    shown, intersecting, current: slide.id, toolbar: win.getComputedStyle(doc.querySelector('.toolbar')).display,
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
    name, _family, count = deck
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    page.goto(_deck_copy(tmp_path, name).as_uri())
    observe: Observe = lambda: page.evaluate(f"({MEASURE})(document)")  # noqa: E731
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
        ("ArrowLeft", f"slide-{count - 2}"),
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
    left = wait_until(page, observe, lambda m: m["fullscreen"] is None and m["scale"] is None, what="presenting left")
    assert left["current"] == last
    assert left["toolbar"] != "none"


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
    name, _family, count = deck
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
