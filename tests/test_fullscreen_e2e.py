"""E2E-038..041 — fullscreen presentation mode (SC-008, FR-026 to FR-028).

See specs/2026-08-07_16-31-00-mcp-htmleditor-retrospective.md.

These are real browser tests: a real ``ThreadingHTTPServer`` (the same one
``mcp-htmleditor serve`` starts) plus a real headless Chromium via
pytest-playwright. Unit tests cannot cover this: the fullscreen contract
(toolbar hidden, slide fills the screen, arrow-key navigation working no
matter which element holds keyboard focus) only exists once a real
Fullscreen API and a real nested browsing context (the content iframe) are
involved.

E2E-039 and E2E-040 are regression tests for the two real bugs found and
fixed after this spec was first written (DEC-011):

- E2E-039: the content iframe was ``sandbox``ed without ``allow-fullscreen``,
  so ``requestFullscreen()`` on the inner document was denied and the code
  fell back to fullscreening the ``<iframe>`` element itself in the parent
  document, where the slide template's own ``:fullscreen`` CSS never
  matches anything (wrong document).
- E2E-040: even once the right document is targeted, ``requestFullscreen()``
  never moves keyboard focus there on its own, so the arrow-key handler
  never fired unless something explicitly forwards the keys.
"""

from __future__ import annotations

import platform
import re
import socket
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from mcp_htmleditor import templates as templates_module
from mcp_htmleditor.http_server import start_http_server, stop_http_server
from tests.browser_wait import settle, wait_for_js, wait_until

REPO_ROOT = Path(__file__).resolve().parents[1]


def _chromium_cache_dir() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library" / "Caches" / "ms-playwright"
    return home / ".cache" / "ms-playwright"


HAS_CHROMIUM = any(_chromium_cache_dir().glob("chromium-*"))
needs_chromium = pytest.mark.skipif(
    not HAS_CHROMIUM,
    reason="Playwright Chromium is not installed; run `make sync`",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _three_slide_deck(tmp_path: Path) -> Path:
    """Grow the real 'ei' bootstrap (1 slide) into a 3-slide deck.

    Mirrors what a deck looks like after an agent adds slides: duplicate the
    <article data-type="slide"> block and bump TOTAL/slideNames, so there is
    something to navigate through.
    """
    src = templates_module.template_path("ei")
    html = src.read_text(encoding="utf-8")
    html = html.replace("const TOTAL = 1;", "const TOTAL = 3;")
    html = html.replace(
        'const slideNames = [\n    "Titre de la présentation",\n  ];',
        'const slideNames = [\n    "Titre de la présentation",\n    "Deuxieme slide",\n    "Troisieme slide",\n  ];',
    )
    match = re.search(r'(<article[^>]*id="slide-0"[^>]*>.*?</article>)', html, re.S)
    if not match:
        pytest.fail("templates/bootstrap/slides-ei-empty.html shape changed, update this fixture")
    block = match.group(1)
    slide_1 = block.replace('id="slide-0"', 'id="slide-1"')
    slide_2 = block.replace('id="slide-0"', 'id="slide-2"')
    html = html.replace(block, block + "\n" + slide_1 + "\n" + slide_2, 1)
    out = tmp_path / "deck.html"
    out.write_text(html, encoding="utf-8")
    return out


@pytest.fixture
def deck_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_state: None) -> Iterator[str]:
    """Serve a real 3-slide EI deck over HTTP and yield its base URL.

    Forces HTMLEDITOR_TEMPLATES_DIR to the repo's templates/ so the deck is
    built from the working tree, never a stale `make install` copy.
    """
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO_ROOT / "templates"))
    config_module.reset_settings_cache()

    deck = _three_slide_deck(tmp_path)
    port = _free_port()
    start_http_server(str(deck), port=port)
    base_url = f"http://127.0.0.1:{port}/"

    for _ in range(50):  # wait for the ThreadingHTTPServer thread to accept
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail("HTTP server did not start in time")

    try:
        yield base_url
    finally:
        stop_http_server()


def _inner(page: Page, js_expression: str) -> object:
    """Evaluate a JS expression with `doc` bound to the iframe's contentDocument."""
    return page.evaluate(
        f"() => {{ const doc = document.getElementById('content-frame').contentDocument; return ({js_expression}); }}"
    )


def _progress(page: Page) -> str:
    return str(_inner(page, "doc.getElementById('progress-tag').textContent"))


def _wait_inner(page: Page, js_expression: str, expected: object, *, what: str) -> object:
    """Observe `_inner(page, js_expression)` until it equals `expected` (BR-008)."""
    return wait_until(page, lambda: _inner(page, js_expression), lambda value: value == expected, what=what)


def _wait_slide_fullscreen(page: Page) -> None:
    """Wait until the slide document itself (its <html>) is the fullscreen element."""
    _wait_inner(
        page,
        "doc.fullscreenElement ? doc.fullscreenElement.tagName : null",
        "HTML",
        what="the slide document in fullscreen",
    )


def _wait_progress(page: Page, expected: str) -> None:
    _wait_inner(page, "doc.getElementById('progress-tag').textContent", expected, what=f"progress {expected}")


def _visual_rect(page: Page, selector: str = ".slide.active") -> list[float]:
    """Return [width, height] of `selector`'s getBoundingClientRect (reflects CSS transforms)."""
    return list(
        _inner(
            page,
            f"(() => {{ const r = doc.querySelector('{selector}').getBoundingClientRect();"
            " return [r.width, r.height]; })()",
        )
    )  # type: ignore[arg-type]


@needs_chromium
def test_fullscreen_hides_toolbar_and_fills_the_screen(page: Page, deck_server: str) -> None:
    """E2E-038: entering fullscreen masks the nav bar and zooms the slide to fill the screen.

    The slide keeps its native 960x540 design box (no stretching, which would
    grow the container without growing fonts/cards - the exact "no zoom"
    regression a real user hit) and is scaled uniformly via a CSS custom
    property (--fs-scale) computed by updateFullscreenScale(), the same way
    PowerPoint/Keynote zoom their slide to fit the display.
    """
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(deck_server, wait_until="networkidle")
    page.wait_for_selector("#present-btn")

    assert _inner(page, "getComputedStyle(doc.querySelector('.toolbar')).display") != "none"
    assert _visual_rect(page) == [960, 540]

    page.click("#present-btn")
    _wait_slide_fullscreen(page)
    wait_until(
        page,
        lambda: _inner(page, "getComputedStyle(doc.documentElement).getPropertyValue('--fs-scale')"),
        lambda value: abs(float(str(value) or 0) - 1600 / 960) < 1e-6,
        what="--fs-scale fitted to the 1600x900 screen",
    )

    assert _inner(page, "doc.fullscreenElement ? doc.fullscreenElement.tagName : null") == "HTML"
    assert _inner(page, "getComputedStyle(doc.querySelector('.toolbar')).display") == "none"
    assert _inner(page, "getComputedStyle(doc.querySelector('.nav-arrow')).display") == "none"
    assert _inner(page, "getComputedStyle(doc.body).backgroundColor") == "rgb(0, 0, 0)"

    # The design box itself never changes size (still 960x540 in layout
    # terms); the VISUAL box (getBoundingClientRect, which reflects the
    # transform) must now fill the 1600x900 viewport exactly, uniformly on
    # both axes since 1600/960 == 900/540 == 5/3 here (no distortion).
    scale = float(_inner(page, "getComputedStyle(doc.documentElement).getPropertyValue('--fs-scale')"))
    assert scale == pytest.approx(1600 / 960)
    assert _visual_rect(page) == pytest.approx([1600, 900])


@needs_chromium
def test_fallback_shell_hides_toolbar_if_inner_fullscreen_is_unavailable(page: Page, deck_server: str) -> None:
    """E2E-039 (regression): parent-side safety net for the exact failure mode this bug caused.

    The real bug (DEC-011) was: the content iframe was sandboxed without
    allow-fullscreen, so requestFullscreen() on the inner document was
    denied, and editor.js's documented fallback fullscreened the <iframe>
    element itself in the PARENT document instead - where the slide
    template's own :fullscreen CSS never applies (wrong document).

    Headless Chromium under Playwright/CDP automation does not reliably
    enforce the missing allow-fullscreen sandbox token the way a real,
    interactively-driven browser does (verified: reproducing the exact
    permission denial here made requestFullscreen() succeed anyway), so
    this test cannot force the original failure end to end. What IS
    deterministic and worth guarding is editor.css's parent-side safety
    net (`body:has(#content-frame:fullscreen) #toolbar`): if the fallback
    path is ever taken for any reason, the outer shell toolbar must still
    disappear instead of leaving a broken half-fullscreen page.
    """
    page.goto(deck_server, wait_until="networkidle")
    page.wait_for_selector("#toolbar")
    assert page.evaluate("() => getComputedStyle(document.getElementById('toolbar')).display") != "none"

    # Simulate editor.js's fallback branch directly: fullscreen the
    # <iframe> element itself (not its inner document) in the PARENT
    # document, exactly what happens when the inner request is denied.
    page.evaluate("() => document.getElementById('content-frame').requestFullscreen()")
    wait_for_js(
        page,
        "() => document.fullscreenElement ? document.fullscreenElement.id : null",
        "content-frame",
        what="the content iframe element in fullscreen",
    )

    assert page.evaluate("() => document.fullscreenElement ? document.fullscreenElement.id : null") == "content-frame"
    assert page.evaluate("() => getComputedStyle(document.getElementById('toolbar')).display") == "none"


@needs_chromium
def test_navigation_keys_work_even_if_focus_never_reaches_the_iframe(page: Page, deck_server: str) -> None:
    """E2E-040 (regression): arrow keys must navigate even when focus stays on the parent document.

    requestFullscreen() does not move keyboard focus into the fullscreened
    document, and browsers are not consistent about it. This is exactly
    what broke navigation for the user in the field.
    """
    page.goto(deck_server, wait_until="networkidle")
    page.click("#present-btn")
    _wait_slide_fullscreen(page)

    # Force focus back onto the parent document, simulating a browser where
    # focus never follows fullscreen into the iframe.
    page.evaluate("() => document.body.focus()")

    assert _progress(page) == "1 / 3"
    page.keyboard.press("ArrowRight")
    _wait_progress(page, "2 / 3")
    assert _progress(page) == "2 / 3"
    page.keyboard.press("ArrowRight")
    _wait_progress(page, "3 / 3")
    assert _progress(page) == "3 / 3"
    page.keyboard.press("ArrowLeft")
    _wait_progress(page, "2 / 3")
    assert _progress(page) == "2 / 3"


@needs_chromium
def test_exiting_fullscreen_keeps_the_current_slide_and_restores_the_ui(page: Page, deck_server: str) -> None:
    """E2E-041: leaving fullscreen (Escape) restores the UI without resetting navigation."""
    page.goto(deck_server, wait_until="networkidle")
    page.click("#present-btn")
    _wait_slide_fullscreen(page)

    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    _wait_progress(page, "3 / 3")
    assert _progress(page) == "3 / 3"

    page.keyboard.press("Escape")
    wait_for_js(page, "() => document.fullscreenElement", None, what="fullscreen left")

    assert page.evaluate("() => document.fullscreenElement") is None
    assert _inner(page, "doc.fullscreenElement") is None
    assert _progress(page) == "3 / 3"
    assert _inner(page, "getComputedStyle(doc.querySelector('.toolbar')).display") != "none"


# SPEC-0016 relay tests (BUG-001, DEC-002). Headless Chromium keeps the keyboard focus in the
# iframe whatever the test focuses (E4), so `page.keyboard.press` reaches the deck's own handler
# and never the editor page's relay. These tests dispatch the keydown on the editor page's
# own `document` and return `defaultPrevented`.

DISPATCH_KEY = (
    "k => { const e = new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true});"
    " document.dispatchEvent(e); return e.defaultPrevented; }"
)


def _dispatch(page: Page, key: str) -> bool:
    return bool(page.evaluate(DISPATCH_KEY, key))


def _present(page: Page, deck_server: str) -> None:
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(deck_server, wait_until="networkidle")
    page.click("#present-btn")
    _wait_slide_fullscreen(page)
    assert _progress(page) == "1 / 3"


@needs_chromium
def test_end_is_relayed_by_the_editor_page(page: Page, deck_server: str) -> None:
    """SPEC-0016/BT-001: End dispatched on the editor page shows the deck's last slide."""
    _present(page, deck_server)

    _dispatch(page, "End")

    _wait_progress(page, "3 / 3")


@needs_chromium
def test_full_key_table_through_the_relay(page: Page, deck_server: str) -> None:
    """SPEC-0016/BT-010: every navigation key works through the relay, once per key press."""
    _present(page, deck_server)
    steps = [
        ("End", "3 / 3"),
        ("End", "3 / 3"),
        ("ArrowLeft", "2 / 3"),
        ("Home", "1 / 3"),
        (" ", "2 / 3"),
        ("ArrowDown", "3 / 3"),
        ("ArrowUp", "2 / 3"),
        ("ArrowRight", "3 / 3"),
        ("ArrowRight", "3 / 3"),
    ]
    for key, expected in steps:
        prevented = _dispatch(page, key)
        # The relay calls the deck synchronously, so the progress is final when dispatch returns.
        assert _progress(page) == expected, f"after {key!r}"
        if key != "Home":
            assert prevented, f"{key!r} default action not prevented"

    _dispatch(page, "Escape")
    wait_for_js(page, "() => document.fullscreenElement", None, what="fullscreen left", bound=2.0)


@needs_chromium
def test_one_move_per_key_whichever_document_gets_it(page: Page, deck_server: str) -> None:
    """SPEC-0016/BT-011: a key reaching the deck is not also relayed (one move, never two)."""
    _present(page, deck_server)
    assert page.evaluate("() => document.activeElement.id") == "content-frame"

    page.keyboard.press("End")
    _wait_progress(page, "3 / 3")
    page.keyboard.press("ArrowLeft")
    _wait_progress(page, "2 / 3")


@needs_chromium
def test_relay_tolerates_a_deck_without_navigation(page: Page, deck_server: str, tmp_path: Path) -> None:
    """SPEC-0016/BT-012: no page error without goToSlide; nothing relayed while not presenting."""
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    # Second half first, on D3: edit mode on, not presenting, caret inside the slide title.
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(deck_server, wait_until="networkidle")
    page.click("#edit-mode-btn")
    _wait_inner(
        page,
        "doc.querySelector('.slide.active .slide-cover-title').isContentEditable",
        True,
        what="slide title editable",
    )
    _inner(
        page,
        "(() => { const h = doc.querySelector('.slide.active .slide-cover-title'); h.focus();"
        " const r = doc.createRange(); r.selectNodeContents(h); r.collapse(true);"
        " const s = doc.defaultView.getSelection(); s.removeAllRanges(); s.addRange(r); return true; })()",
    )
    assert _inner(page, "doc.activeElement === doc.querySelector('.slide.active .slide-cover-title')") is True
    _dispatch(page, "End")
    settle(page)
    assert _progress(page) == "1 / 3"

    # First half: the doc bootstrap has no navigate()/goToSlide() globals.
    doc_file = tmp_path / "doc.html"
    doc_file.write_text(templates_module.template_path("doc").read_text(encoding="utf-8"), encoding="utf-8")
    stop_http_server()
    port = _free_port()
    start_http_server(str(doc_file), port=port)
    page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
    page.click("body")
    page.evaluate("() => document.getElementById('content-frame').contentDocument.documentElement.requestFullscreen()")
    _wait_slide_fullscreen(page)
    assert _inner(page, "typeof doc.defaultView.goToSlide") == "undefined"
    before = _inner(page, "doc.body.innerText")

    _dispatch(page, "End")
    _dispatch(page, "Home")
    settle(page)

    assert errors == []
    assert _inner(page, "doc.body.innerText") == before
