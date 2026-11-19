"""E2E test of SPEC-0002 FR-019: export buttons by document type and their downloads (E2E-019, US-0155)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from tests.browser_wait import wait_for_js
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import deck_ei, doc_perso, write_deck

PPTX = "#export-pptx-btn"
DOCX = "#export-docx-btn"


def _open(page: Page, served: ServedDeck, shown: str, hidden: str) -> None:
    page.goto(f"http://127.0.0.1:{served.port}/")
    wait_for_js(
        page,
        f"() => getComputedStyle(document.querySelector('{shown}')).display !== 'none'",
        True,
        what="the export button of the document type shown",
    )
    assert page.is_visible(shown)
    assert not page.is_visible(hidden)


def _download(page: Page, button: str, suffix: str) -> None:
    with page.expect_download() as info:
        page.click(button)
    download = info.value
    assert download.suggested_filename.endswith(suffix)
    data = Path(download.path()).read_bytes()
    assert data[:2] == b"PK"
    assert len(data) > 2


def _serve(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], name: str, content: str) -> ServedDeck:
    folder = tmp_path / "work"
    folder.mkdir()
    return serve_deck(Path(write_deck(folder / name, content)))


@needs_chromium
def test_presentation_shows_the_pptx_button_and_downloads(
    page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-019: a presentation shows the pptx button only; it downloads a zip."""
    _open(page, _serve(tmp_path, serve_deck, "deck.html", deck_ei()), PPTX, DOCX)
    _download(page, PPTX, ".pptx")


@needs_chromium
def test_document_shows_the_docx_button_and_downloads(
    page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-019: a document shows the docx button only; it downloads a zip."""
    _open(page, _serve(tmp_path, serve_deck, "doc.html", doc_perso()), DOCX, PPTX)
    _download(page, DOCX, ".docx")
