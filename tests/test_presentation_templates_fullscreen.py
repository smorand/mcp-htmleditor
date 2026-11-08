"""Guard: every presentation file under templates/ ships the fullscreen building blocks (SPEC-0016 BR-009, BR-016)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

TEMPLATES_ROOT = Path(__file__).resolve().parents[1] / "templates"
MARKERS = (":fullscreen", 'id="btn-present"', "enterPresentation", "exitPresentation", "updateFullscreenScale")
HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
PRESENTATION_ATTRIBUTE = re.compile(r"""data-doc-type\s*=\s*["']presentation["']""", re.IGNORECASE)

POINTER_PARTS = (
    ("pointer", "window.togglePointer = function"),
    ("Pointeur control", 'id="btn-pointer"'),
    ("L key", "e.key === 'l' || e.key === 'L'"),
)
POINTER_BLOCK = re.compile(r"<!-- deck-pointer:begin -->.*?<!-- deck-pointer:end -->", re.DOTALL)
ROADMAP = TEMPLATES_ROOT / "reference" / "slides" / "roadmap-one-pager.html"
POINTER_CONTROL = re.compile(r'<button id="btn-pointer"[^>]*>Pointeur</button>')
L_LINE = re.compile(r"^[ \t]*if \(\(e\.key === 'l'[^\n]*\n", re.MULTILINE)

EXPECTED_TODAY = (
    "bootstrap/slides-empty.html",
    "bootstrap/slides-ei-empty.html",
    "bootstrap/slides-medical-empty.html",
    "reference/slides/euro-information.html",
    "reference/slides/medical.html",
    "reference/slides/example-medical-complete.html",
    "reference/slides/ibm-carbon.html",
    "reference/slides/example-ei-complete.html",
    "reference/slides/example-carbon-complete.html",
    "reference/slides/presentation-standard.html",
    "reference/slides/roadmap-one-pager.html",
)
FIVE_DECKS = (
    "reference/slides/ibm-carbon.html",
    "reference/slides/example-ei-complete.html",
    "reference/slides/example-carbon-complete.html",
    "reference/slides/presentation-standard.html",
    "reference/slides/roadmap-one-pager.html",
)


def presentation_files(root: Path) -> list[Path]:
    """Every templates/**/*.html whose first <html ...> tag holds data-doc-type="presentation", sorted."""
    return sorted(path for path in root.rglob("*.html") if is_presentation(path.read_text(encoding="utf-8")))


def is_presentation(html: str) -> bool:
    # slides-ei-empty.html quotes a bare "<html>" in its banner comment, which is not the document's tag
    match = HTML_TAG.search(HTML_COMMENT.sub("", html))
    return match is not None and PRESENTATION_ATTRIBUTE.search(match.group(0)) is not None


def missing_markers(html: str) -> list[str]:
    """MARKERS absent from the text, in MARKERS order."""
    return [marker for marker in MARKERS if marker not in html]


def missing_pointer_lines(name: str, html: str) -> list[str]:
    """One ``<name>: missing <part>`` line per absent pointer part, in POINTER_PARTS order (comments dropped)."""
    code = HTML_COMMENT.sub("", html)
    return [f"{name}: missing {part}" for part, marker in POINTER_PARTS if marker not in code]


def failure_message(path: Path, root: Path, html: str) -> str:
    return f"{path.relative_to(root)}: missing {', '.join(missing_markers(html))}"


DISCOVERED = presentation_files(TEMPLATES_ROOT)


def relative_names(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in presentation_files(root)}


@pytest.mark.parametrize("path", DISCOVERED, ids=lambda path: path.relative_to(TEMPLATES_ROOT).as_posix())
def test_presentation_template_ships_fullscreen_blocks(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    assert not missing_markers(html), failure_message(path, TEMPLATES_ROOT, html)


@pytest.mark.parametrize("name", FIVE_DECKS)
def test_five_decks_present_button_calls_enter_presentation(name: str) -> None:
    soup = BeautifulSoup((TEMPLATES_ROOT / name).read_text(encoding="utf-8"), "html.parser")
    buttons = soup.find_all(id="btn-present")
    assert len(buttons) == 1, f"{name}: expected one #btn-present, found {len(buttons)}"
    assert buttons[0].get("onclick") == "enterPresentation()", name


def test_discovery_covers_the_eleven_presentation_files_and_only_presentations() -> None:
    names = relative_names(TEMPLATES_ROOT)
    assert set(EXPECTED_TODAY) <= names
    for path in TEMPLATES_ROOT.rglob("*.html"):
        if not is_presentation(path.read_text(encoding="utf-8")):
            assert path.relative_to(TEMPLATES_ROOT).as_posix() not in names


def test_guard_fails_on_a_new_template_without_markers(tmp_path: Path) -> None:
    root = tmp_path / "templates"
    shutil.copytree(TEMPLATES_ROOT, root)
    html = '<!DOCTYPE html><html data-doc-type="presentation"><body><section data-type="slide"></section></body></html>'
    new_file = root / "reference" / "slides" / "x.html"
    new_file.write_text(html, encoding="utf-8")

    assert "reference/slides/x.html" in relative_names(root)
    assert missing_markers(html) == list(MARKERS)
    assert failure_message(new_file, root, html) == (
        'reference/slides/x.html: missing :fullscreen, id="btn-present", enterPresentation, '
        "exitPresentation, updateFullscreenScale"
    )


@pytest.mark.parametrize("path", DISCOVERED, ids=lambda path: path.stem)
def test_presentation_template_ships_the_pointer(path: Path) -> None:
    assert missing_pointer_lines(path.stem, path.read_text(encoding="utf-8")) == []


def test_pointer_check_reports_every_part_of_a_template_without_markers() -> None:
    assert missing_pointer_lines("x", "<html></html>") == [
        "x: missing pointer",
        "x: missing Pointeur control",
        "x: missing L key",
    ]


def test_pointer_markers_in_a_comment_only_do_not_count() -> None:
    html = "<!-- window.togglePointer = function  id=\"btn-pointer\"  e.key === 'l' || e.key === 'L' -->"
    assert len(missing_pointer_lines("x", html)) == 3


def _roadmap_with_pointer() -> str:
    """roadmap-one-pager as US-0109 left it, carrying the three parts once each."""
    html = ROADMAP.read_text(encoding="utf-8")
    assert missing_pointer_lines(ROADMAP.stem, html) == []
    assert len(POINTER_CONTROL.findall(html)) == len(L_LINE.findall(html)) == 1
    return html


# SPEC-0017/E2E-033
def test_guard_names_the_reference_deck_that_lost_the_pointer() -> None:
    html = _roadmap_with_pointer()
    block = POINTER_BLOCK.search(html)
    assert block is not None

    assert missing_pointer_lines(ROADMAP.stem, html.replace(block.group(0), "")) == [
        "roadmap-one-pager: missing pointer"
    ]


def test_guard_names_the_reference_deck_that_lost_only_the_pointeur_control() -> None:
    html = _roadmap_with_pointer()

    assert missing_pointer_lines(ROADMAP.stem, POINTER_CONTROL.sub("", html)) == [
        "roadmap-one-pager: missing Pointeur control"
    ]


def test_guard_names_the_reference_deck_that_lost_only_the_l_key() -> None:
    html = _roadmap_with_pointer()

    assert missing_pointer_lines(ROADMAP.stem, L_LINE.sub("", html)) == ["roadmap-one-pager: missing L key"]
