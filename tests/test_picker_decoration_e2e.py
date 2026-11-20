"""SPEC-0029 (US-0161): the layout picker brings the Breathe decoration of an inserted layout.

E2E-001 to E2E-007 and E2E-009 to E2E-015 (E2E-008 is the modified test of ``test_breathe_reference.py``). Real
Chromium on a deck served by a real editor server; the second channel is always the deck file on disk (its
decoration block), never only what the page shows.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Page

from mcp_htmleditor.breathe import inline as inline_module
from tests.breathe_support import BOOTSTRAP, REFERENCE
from tests.browser_wait import settle, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import run_cli
from tests.test_breathe_reference import CARBON, MEDICAL, READY, Serve, open_picker, slides_on_disk

BEGIN, END = "/* breathe:assets:begin */", "/* breathe:assets:end */"
RULE = re.compile(r"\.(med-(?:bg|ico)-[A-Za-z0-9_-]+)\s*\{([^}]*)\}")
NOTICE = (
    "() => { const e = document.getElementById('decoration-error'); return e && !e.hidden ? e.textContent : null; }"
)


def slide_background(index: int) -> str:
    return (
        "() => { const d = document.getElementById('content-frame').contentDocument;"
        f" const s = d.querySelectorAll('[data-type=\"slide\"]')[{index}];"
        " return s ? getComputedStyle(s).backgroundImage : null; }"
    )


def block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(BEGIN) : text.index(END) + len(END)]


def block_classes(path: Path) -> dict[str, str]:
    return dict(RULE.findall(block(path)))


def layout_classes(title: str) -> set[str]:
    """The decoration classes the reference slide ``title`` uses."""
    slide = next(s for s in slides_on_disk(REFERENCE) if s.get("data-title") == title)  # type: ignore[attr-defined]
    tokens = {c for el in [slide, *slide.find_all(True)] for c in el.get("class") or []}  # type: ignore[attr-defined]
    return {c for c in tokens if c.startswith(("med-bg-", "med-ico-"))}


def new_deck(tmp_path: Path) -> Path:
    deck = tmp_path / "talk.html"
    shutil.copyfile(BOOTSTRAP, deck)
    return deck


def open_editor(page: Page, served: ServedDeck) -> None:
    """Open the deck in the editor and switch edit mode on, without opening the picker."""
    page.goto(f"http://127.0.0.1:{served.port}/")
    wait_until(page, lambda: page.evaluate(READY), bool, what="the deck loaded in the editor")
    page.click("#edit-mode-btn")
    wait_for_js(
        page, "() => getComputedStyle(document.getElementById('undo-btn')).display !== 'none'", True, what="edit mode"
    )


def insert(page: Page, label: str, *, where: str = "after") -> None:
    """Open the picker from the toolbar and choose ``label``; the editor must already be open and in edit mode."""
    page.click(f"#btn-insert-{where}")
    page.wait_for_selector("#slide-picker .picker-card")
    page.click(f"#slide-picker .picker-card:has(.picker-card-label:text-is('{label}'))")


def count_loads(page: Page) -> list[str]:
    loads: list[str] = []
    page.on("request", lambda req: loads.append(req.url) if "/content-frame" in req.url else None)
    return loads


def wait_slides(page: Page, deck: Path, count: int) -> None:
    wait_until(page, lambda: len(slides_on_disk(deck)), lambda n: n == count, what=f"{count} slides saved")


def wait_rules(page: Page, deck: Path, classes: set[str]) -> None:
    wait_until(page, lambda: set(block_classes(deck)), lambda have: classes <= have, what="the decoration rules saved")


def style_text(path: Path) -> list[str]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    return [str(s) for s in soup.find_all("style")]


@needs_chromium
def test_e2e_001_an_inserted_layout_shows_its_decoration_at_once(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    open_editor(page, serve_deck(deck))
    loads = count_loads(page)
    wanted = layout_classes("Pathway")

    insert(page, "Pathway")

    wait_slides(page, deck, 2)
    wait_until(
        page,
        lambda: page.evaluate(slide_background(1)),
        lambda bg: bool(bg) and bg != "none",
        what="background",
        bound=3,
    )
    wait_rules(page, deck, wanted)
    assert all("url(data:image/" in block_classes(deck)[c] for c in wanted)
    assert loads == []


@needs_chromium
def test_e2e_002_linked_form(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    _, _, code = run_cli("breathe-inline", str(deck), "--link")
    assert code == 0
    open_editor(page, serve_deck(deck))
    wanted = layout_classes("Pathway")

    insert(page, "Pathway")

    wait_slides(page, deck, 2)
    wait_rules(page, deck, wanted)
    wait_until(
        page,
        lambda: page.evaluate(slide_background(1)),
        lambda bg: bool(bg) and bg != "none",
        what="background",
        bound=3,
    )
    for name in wanted:
        match = re.search(r"url\((assets/[^)]+)\)", block_classes(deck)[name])
        assert match, name
        assert (deck.parent / match.group(1)).is_file()


@needs_chromium
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores folder permissions")
def test_e2e_003_an_unwritable_assets_folder_shows_a_notice(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    run_cli("breathe-inline", str(deck), "--link")
    before = block(deck)
    assets = deck.parent / "assets"
    mode = stat.S_IMODE(assets.stat().st_mode)
    open_editor(page, serve_deck(deck))
    assets.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        insert(page, "Pathway")
        wait_slides(page, deck, 2)
        text = wait_until(page, lambda: page.evaluate(NOTICE), bool, what="the notice")
    finally:
        assets.chmod(mode)
    assert str(text).startswith("Decoration not added: Cannot write ")
    assert block(deck) == before


@needs_chromium
def test_e2e_004_a_file_missing_from_the_catalogue(
    tmp_path: Path, page: Page, serve_deck: Serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalogue = tmp_path / "catalogue"
    catalogue.mkdir()
    real = inline_module.catalogue_dir()
    missing = None
    for name in sorted(layout_classes("Pathway")):
        prefix, file_prefix = ("med-bg-", "bg-") if name.startswith("med-bg-") else ("med-ico-", "icon-")
        file_name = f"{file_prefix}{name[len(prefix) :]}.png"
        if name.startswith("med-bg-") and missing is None:
            missing = file_name
        elif file_name != missing:
            shutil.copyfile(real / file_name, catalogue / file_name)
    assert missing
    monkeypatch.setattr(inline_module, "catalogue_dir", lambda: catalogue)
    deck = new_deck(tmp_path)
    before = block(deck)
    open_editor(page, serve_deck(deck))

    insert(page, "Pathway")

    wait_slides(page, deck, 2)
    text = str(wait_until(page, lambda: page.evaluate(NOTICE), bool, what="the notice"))
    assert text.startswith(f"Decoration not added: asset {missing} not found in: ")
    assert block(deck) == before


@needs_chromium
def test_e2e_005_nothing_twice(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    open_editor(page, serve_deck(deck))
    insert(page, "Pathway")
    wait_slides(page, deck, 2)
    wait_rules(page, deck, layout_classes("Pathway"))
    after_first = block(deck)

    insert(page, "Pathway")

    wait_slides(page, deck, 3)
    settle(page)
    assert block(deck) == after_first
    assert page.evaluate(NOTICE) is None


@needs_chromium
@pytest.mark.parametrize("source", [MEDICAL, CARBON], ids=["medical", "carbon"])
def test_e2e_006_and_012_other_decks_keep_their_styles(
    tmp_path: Path, page: Page, serve_deck: Serve, source: Path
) -> None:
    deck = tmp_path / "other.html"
    shutil.copyfile(source, deck)
    before = style_text(deck)
    open_picker(page, serve_deck(deck))
    page.click("#slide-picker .picker-card")
    wait_slides(page, deck, 2)
    settle(page)
    assert style_text(deck) == before
    assert page.evaluate(NOTICE) is None


@needs_chromium
def test_e2e_007_picker_cancelled_keeps_the_file(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    before = deck.read_bytes()
    open_picker(page, serve_deck(deck))
    page.click("#slide-picker .picker-cancel")
    wait_for_js(page, "() => document.getElementById('slide-picker').style.display", "none", what="picker closed")
    settle(page)
    assert deck.read_bytes() == before


@needs_chromium
def test_e2e_009_a_server_that_does_not_answer_gives_a_notice(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    open_editor(page, serve_deck(deck))
    page.route("**/breathe-assets", lambda route: route.abort())

    insert(page, "Pathway")

    wait_slides(page, deck, 2)
    wait_until(
        page,
        lambda: page.evaluate(NOTICE),
        lambda t: t == "Decoration not added: the editor server did not answer",
        what="the notice",
    )


@needs_chromium
def test_e2e_010_undo_removes_the_slide_and_its_rules_and_redo_brings_them_back(
    tmp_path: Path, page: Page, serve_deck: Serve
) -> None:
    deck = new_deck(tmp_path)
    open_editor(page, serve_deck(deck))
    pathway_only = layout_classes("Pathway") - set(block_classes(deck))
    insert(page, "Pathway")
    wait_slides(page, deck, 2)
    wait_rules(page, deck, pathway_only)

    page.click("#undo-btn")
    wait_slides(page, deck, 1)
    wait_until(
        page, lambda: pathway_only & set(block_classes(deck)), lambda left: not left, what="rules removed by undo"
    )
    assert page.evaluate("() => document.getElementById('redo-btn').disabled") is False

    page.click("#redo-btn")
    wait_slides(page, deck, 2)
    wait_rules(page, deck, pathway_only)


@needs_chromium
def test_e2e_011_a_mixed_block_counts_as_linked(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    text = deck.read_text(encoding="utf-8")
    text = re.sub(r"(\.med-bg-cover-s0 \{ background-image:url\()data:[^)]*(\))", r"\1assets/bg-cover-s0.png\2", text)
    deck.write_text(text, encoding="utf-8")
    (deck.parent / "assets").mkdir()
    shutil.copyfile(inline_module.catalogue_dir() / "bg-cover-s0.png", deck.parent / "assets" / "bg-cover-s0.png")
    wanted = layout_classes("Pathway") - set(block_classes(deck))
    open_editor(page, serve_deck(deck))

    insert(page, "Pathway")

    wait_slides(page, deck, 2)
    wait_rules(page, deck, wanted)
    for name in wanted:
        match = re.search(r"url\((assets/[^)]+)\)", block_classes(deck)[name])
        assert match, name
        assert (deck.parent / match.group(1)).is_file()


@needs_chromium
def test_e2e_013_insertion_before_the_current_slide(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    open_editor(page, serve_deck(deck))

    insert(page, "Pathway", where="before")

    wait_slides(page, deck, 2)
    wait_rules(page, deck, layout_classes("Pathway"))
    wait_until(
        page,
        lambda: page.evaluate(slide_background(0)),
        lambda bg: bool(bg) and bg != "none",
        what="background",
        bound=3,
    )
    assert slides_on_disk(deck)[0].get("data-title") == "Pathway"  # type: ignore[attr-defined]


@needs_chromium
def test_e2e_014_nothing_twice_linked(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    run_cli("breathe-inline", str(deck), "--link")
    open_editor(page, serve_deck(deck))
    insert(page, "Pathway")
    wait_slides(page, deck, 2)
    wait_rules(page, deck, layout_classes("Pathway"))
    after_first, files = block(deck), sorted(p.name for p in (deck.parent / "assets").iterdir())

    insert(page, "Pathway")

    wait_slides(page, deck, 3)
    settle(page)
    assert block(deck) == after_first
    assert sorted(p.name for p in (deck.parent / "assets").iterdir()) == files
    assert page.evaluate(NOTICE) is None


@needs_chromium
def test_e2e_015_a_layout_that_needs_nothing_new(tmp_path: Path, page: Page, serve_deck: Serve) -> None:
    deck = new_deck(tmp_path)
    before = block(deck)
    open_editor(page, serve_deck(deck))

    insert(page, "Cover")

    wait_slides(page, deck, 2)
    settle(page)
    assert block(deck) == before
    assert page.evaluate(NOTICE) is None
