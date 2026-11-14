"""SPEC-0023 (US-0119): the Breathe reference deck and the Breathe layouts of the editor's picker.

E2E-007 to E2E-010, E2E-047, E2E-051 to E2E-053. The picker tests drive the real editor page in Chromium on a
deck served by a real editor server; the deck on disk is the observable of every insertion.
"""

from __future__ import annotations

import importlib
import shutil
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Page

from mcp_htmleditor.deck import load_deck
from tests.breathe_support import BOOTSTRAP, REFERENCE, REFERENCE_NAMES
from tests.browser_wait import wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import run_cli
from tests.test_presentation_templates_fullscreen import TEMPLATES_ROOT, presentation_files

REPO = Path(__file__).resolve().parents[1]
MEDICAL = REPO / "templates" / "bootstrap" / "slides-medical-empty.html"
CARBON = REPO / "templates" / "bootstrap" / "slides-empty.html"
READY = (
    "() => { const f = document.getElementById('content-frame'); const d = f && f.contentDocument;"
    " return !!d && d.readyState === 'complete' && !!d.querySelector('[data-type=\"slide\"]'); }"
)
LABELS = "() => Array.from(document.querySelectorAll('#slide-picker .picker-card-label'), (e) => e.textContent)"
Serve = Callable[[Path], ServedDeck]


def slide_text(article: object) -> str:
    """Visible text of a slide, notes and page number left out, whitespace collapsed."""
    soup = BeautifulSoup(str(article), "html.parser")
    for hidden in soup.select('[data-role="speaker-notes"], .slide-foot-page'):
        hidden.decompose()
    return " ".join(soup.get_text(" ").split())


def open_picker(page: Page, served: ServedDeck, edit: bool = True) -> list[str]:
    page.goto(f"http://127.0.0.1:{served.port}/")
    wait_until(page, lambda: page.evaluate(READY), bool, what="the deck loaded in the editor")
    if edit:
        page.click("#edit-mode-btn")
        wait_for_js(
            page,
            "() => getComputedStyle(document.getElementById('undo-btn')).display !== 'none'",
            True,
            what="edit mode",
        )
    page.click("#btn-insert-after")
    page.wait_for_selector("#slide-picker .picker-card")
    return list(page.evaluate(LABELS))


def slides_on_disk(path: Path) -> list[object]:
    return list(BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").find_all(attrs={"data-type": "slide"}))


# -- E2E-007, E2E-047: the reference deck --------------------------------------------------------------------


def test_reference_deck_complete_and_clean() -> None:
    deck = load_deck(str(REFERENCE))
    assert deck.charter == "breathe"
    assert tuple(str(slide.get("data-title")) for slide in deck.slides) == REFERENCE_NAMES
    assert all(slide.find("aside", attrs={"data-role": "speaker-notes"}, recursive=False) for slide in deck.slides)
    stdout, _, code = run_cli("lint", str(REFERENCE))
    assert (stdout.strip(), code) == ("lint: OK (0 errors, 0 warnings)", 0)
    stdout, _, code = run_cli("outline", str(REFERENCE))
    assert code == 0
    for name in REFERENCE_NAMES:
        assert name in stdout


@needs_chromium
def test_reference_render_report_is_clean() -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        stdout, stderr, code = pool.submit(run_cli, "render", str(REFERENCE), "--report-only").result()
    assert (stdout.strip(), stderr, code) == ("report: OK", "", 0)


def test_template_guard_covers_the_breathe_files() -> None:
    """E2E-047: both Breathe files are presentation files the fullscreen, pointer and presenter guards check."""
    names = {path.relative_to(TEMPLATES_ROOT).as_posix() for path in presentation_files(TEMPLATES_ROOT)}
    assert {"bootstrap/slides-breathe-empty.html", "reference/slides/breathe.html"} <= names
    for path in (BOOTSTRAP, REFERENCE):
        text = path.read_text(encoding="utf-8")
        for marker in ("window.togglePointer = function", 'id="btn-pointer"', "window.togglePresenter = function"):
            assert marker in text, f"{path.name}: {marker}"


# -- E2E-008, E2E-009, E2E-051 to E2E-053: the picker -------------------------------------------------------


@needs_chromium
def test_picker_offers_the_breathe_layouts(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    """E2E-008."""
    deck = tmp_path / "talk.html"
    shutil.copyfile(BOOTSTRAP, deck)
    assert tuple(open_picker(page, serve_deck(deck))) == REFERENCE_NAMES
    page.click("#slide-picker .picker-card:has(.picker-card-label:text-is('Key figures'))")
    wait_until(page, lambda: len(slides_on_disk(deck)), lambda n: n == 2, what="the inserted slide saved")
    slides = slides_on_disk(deck)
    reference = next(s for s in slides_on_disk(REFERENCE) if s.get("data-title") == "Key figures")  # type: ignore[attr-defined]
    assert slide_text(slides[1]) == slide_text(reference)
    assert [s.get("data-id") for s in slides] == ["slide-0", "slide-1"]  # type: ignore[attr-defined]
    assert slides[1].select_one(".slide-foot-page").get_text() == "2"  # type: ignore[attr-defined]


@needs_chromium
def test_picker_of_a_medical_deck_unchanged(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    """E2E-009."""
    deck = tmp_path / "med.html"
    shutil.copyfile(MEDICAL, deck)
    labels = open_picker(page, serve_deck(deck))
    assert len(labels) == 16
    assert not set(labels) & set(REFERENCE_NAMES)


@needs_chromium
def test_picker_of_a_carbon_deck_unchanged(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    """E2E-051."""
    deck = tmp_path / "carbon.html"
    shutil.copyfile(CARBON, deck)
    labels = open_picker(page, serve_deck(deck))
    assert len(labels) == 5
    assert not {"Cover", "Key figures, deep", "Thanks, message"} & set(labels)


BACKGROUND = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    " const s = d.querySelectorAll('[data-type=\"slide\"]')[1];"
    " return s ? getComputedStyle(s).backgroundImage : null; }"
)


@needs_chromium
def test_inserted_layout_before_and_after_embedding(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    """E2E-052."""
    deck = tmp_path / "talk.html"
    shutil.copyfile(BOOTSTRAP, deck)
    open_picker(page, serve_deck(deck))
    page.click("#slide-picker .picker-card:has(.picker-card-label:text-is('Pathway'))")
    wait_until(page, lambda: len(slides_on_disk(deck)), lambda n: n == 2, what="the inserted slide saved")
    assert page.evaluate(BACKGROUND) == "none"
    stdout, _, code = run_cli("breathe-inline", str(deck))
    assert code == 0, stdout
    wait_until(page, lambda: page.evaluate(BACKGROUND), lambda bg: bool(bg) and bg != "none", what="background loaded")


@needs_chromium
def test_picker_cancelled(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    """E2E-053."""
    deck = tmp_path / "talk.html"
    shutil.copyfile(BOOTSTRAP, deck)
    before = deck.read_bytes()
    open_picker(page, serve_deck(deck))
    page.click("#slide-picker .picker-cancel")
    wait_for_js(page, "() => document.getElementById('slide-picker').style.display", "none", what="picker closed")
    assert len(slides_on_disk(deck)) == 1
    assert deck.read_bytes() == before


# -- E2E-010: the picker set follows the reference deck ---------------------------------------------------


@pytest.fixture
def tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    """The sync tool working on copies of the reference deck, the starting point and slide-layouts.js."""
    monkeypatch.syspath_prepend(str(REPO / "tools"))
    sys.modules.pop("sync_breathe_layouts", None)
    module = importlib.import_module("sync_breathe_layouts")
    root = tmp_path / "repo"
    for path in (module.REFERENCE, module.BOOTSTRAP, module.LAYOUTS_JS):
        target = root / path.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        monkeypatch.setattr(
            module, {module.REFERENCE: "REFERENCE", module.BOOTSTRAP: "BOOTSTRAP"}.get(path, "LAYOUTS_JS"), target
        )
    monkeypatch.setattr(module, "REPO", root)
    return module


def test_picker_set_follows_the_reference_deck(tool: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    reference = tool.REFERENCE.read_text(encoding="utf-8")
    tool.REFERENCE.write_text(
        reference.replace('data-title="Key figures"', 'data-title="Key numbers"', 1), encoding="utf-8"
    )
    assert tool.sync(check=True) == 1
    stale = [line for line in capsys.readouterr().out.splitlines() if "slide-layouts.js" in line]
    assert len(stale) == 1
    assert stale[0].endswith("; run: make sync-breathe-layouts")
    assert tool.sync(check=False) == 0
    capsys.readouterr()
    assert tool.sync(check=True) == 0
    assert 'label: "Key numbers"' in tool.LAYOUTS_JS.read_text(encoding="utf-8")


def test_repository_is_fresh() -> None:
    """The shipped files and the picker set are fresh (the same check as make check-generated)."""
    sys.path.insert(0, str(REPO / "tools"))
    try:
        sys.modules.pop("sync_breathe_layouts", None)
        module = importlib.import_module("sync_breathe_layouts")
        assert module.sync(check=True) == 0
    finally:
        sys.path.remove(str(REPO / "tools"))
