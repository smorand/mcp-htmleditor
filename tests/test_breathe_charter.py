"""SPEC-0023 (US-0117): the Breathe charter key, its recognition, its starting point and its lint rules.

E2E-001 to E2E-006, E2E-034 to E2E-037, E2E-044, E2E-045, E2E-048, E2E-049, E2E-056, E2E-058 to E2E-061,
E2E-067, E2E-068, and the lint half of E2E-046 and E2E-057. The painted export half lives in
``test_breathe_pptx.py``.
"""

from __future__ import annotations

import hashlib
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from mcp_htmleditor.deck import load_deck
from mcp_htmleditor.export.pptx_style import detect_theme
from mcp_htmleditor.export.to_pptx import to_pptx
from tests.breathe_support import (
    BOOTSTRAP,
    MARKER_LINE,
    REFERENCE,
    as_medical,
    breathe_deck,
    breathe_slide,
    legacy_deck,
    wcbip_or_skip,
)
from tests.conftest import needs_chromium
from tests.deck_support import TINY_PNG, build_deck, call_tool, deck_carbon, run_cli, write_deck

REPO = Path(__file__).resolve().parents[1]
LAYOUTS_JS = REPO / "src" / "mcp_htmleditor" / "static" / "slide-layouts.js"
KEYS = ["ei", "carbon", "medical", "breathe", "doc", "doc-perso", "doc-ei", "mail", "website"]
DESCRIPTION = "Breathe congress presentation: airway story line, ice and navy panels, Georgia titles, 1 cover slide"
UNKNOWN = f'Unknown template "breath". Valid templates: {", ".join(KEYS)}'
OK = "lint: OK (0 errors, 0 warnings)"
IMG = f'<img src="data:image/png;base64,{TINY_PNG}" alt="x">'


@pytest.fixture(autouse=True)
def repo_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the templates of the repository, never an installed copy."""
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO / "templates"))
    config_module.reset_settings_cache()


def lint_lines(tmp_path: Path, html: str, name: str = "deck.html") -> list[str]:
    stdout, _, _ = run_cli("lint", write_deck(tmp_path / name, html))
    return stdout.splitlines()


def charter_seen_by_lint(tmp_path: Path, html: str) -> str:
    """The charter lint applies, read from the L007 message of a Carbon only class added to the last slide."""
    marked = html.replace(
        '<aside data-role="speaker-notes">', '<i class="cds-probe"></i><aside data-role="speaker-notes">'
    )
    found = [line for line in lint_lines(tmp_path, marked, "probe.html") if '"cds-probe"' in line]
    assert found, "the probe class must be foreign to the charter"
    return found[0].rsplit(" ", 1)[1]


def export_charter(tmp_path: Path, html: str) -> str:
    source = write_deck(tmp_path / "export.html", html)
    return to_pptx(source, str(tmp_path / "export.pptx")).charter or ""


def picker_set(page: Page, html: str) -> str:
    """Run the real ``detectTemplate`` of the editor in Chromium on ``html``."""
    page.set_content(html)
    page.add_script_tag(path=str(LAYOUTS_JS))
    page.evaluate("document.querySelectorAll('script').forEach((s) => s.remove())")
    return str(page.evaluate("detectTemplate(document)"))


# -- E2E-001 to E2E-004, E2E-067, E2E-068: the catalogue -----------------------------------------------------


def test_catalogue_lists_breathe_after_medical() -> None:
    stdout, _, code = run_cli("templates")
    keys = [line.split()[0] for line in stdout.splitlines()[2:] if line.strip()]
    assert code == 0
    assert keys == KEYS
    assert any(
        line.split(maxsplit=1)[1] == DESCRIPTION for line in stdout.splitlines()[2:] if line.startswith("  breathe")
    )
    ok, data = call_tool("list_templates")
    assert ok
    assert [(item["key"], item["description"]) for item in data][3] == ("breathe", DESCRIPTION)
    assert [item["key"] for item in data] == KEYS


def test_unknown_key_names_the_nine_keys(tmp_path: Path) -> None:
    target = tmp_path / "talk.html"
    _, stderr, code = run_cli("new", "breath", str(target))
    assert (stderr.strip(), code) == (f"error: {UNKNOWN}", 1)
    assert not target.exists()
    ok, message = call_tool("new_file", template="breath", file=str(target))
    assert not ok
    assert UNKNOWN in message
    assert not target.exists()


def test_existing_target_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "talk.html"
    target.write_text("keep me", encoding="utf-8")
    _, stderr, code = run_cli("new", "breathe", str(target))
    assert (stderr.strip(), code) == (f"error: File already exists: {target}", 1)
    assert target.read_text(encoding="utf-8") == "keep me"


def test_new_breathe_deck_and_its_single_lint_error(tmp_path: Path) -> None:
    target = tmp_path / "talk.html"
    _, _, code = run_cli("new", "breathe", str(target))
    assert code == 0
    deck = load_deck(str(target))
    assert deck.charter == "breathe"
    assert [(slide.get("data-id"), slide.get("data-slide-type")) for slide in deck.slides] == [("slide-0", "title")]
    text = target.read_text(encoding="utf-8")
    assert 'data-doc-template="breathe"' in text
    assert "--breathe-ice" in text
    assert "Title of the presentation" in text
    stdout, _, code = run_cli("lint", str(target))
    assert stdout.splitlines() == [
        'error L006 slide-0 template text left: "Title of the presentation"',
        "lint: FAIL (1 error, 0 warnings)",
    ]
    assert code == 1
    tool_target = tmp_path / "tool.html"
    ok, data = call_tool("new_file", template="breathe", file=str(tool_target))
    assert ok
    assert data == {"ok": True, "file": str(tool_target)}
    assert tool_target.read_bytes() == target.read_bytes() == BOOTSTRAP.read_bytes()


@needs_chromium
def test_new_deck_shows_its_decoration_alone_and_presents(tmp_path: Path, page: Page) -> None:
    """E2E-005: alone in its folder, every picture loads; S opens the presenter; the render report is clean."""
    target = tmp_path / "talk.html"
    run_cli("new", "breathe", str(target))
    page.goto(target.as_uri(), wait_until="load")
    state = page.evaluate(
        """() => {
          const slide = document.getElementById('slide-0');
          const imgs = Array.from(slide.querySelectorAll('img'));
          const icons = Array.from(slide.querySelectorAll('.med-ico'));
          return {background: getComputedStyle(slide).backgroundImage.startsWith('url("data:image/png'),
                  loaded: imgs.length > 0 && imgs.every((i) => i.complete && i.naturalWidth > 0),
                  icons: icons.length > 0 && icons.every((i) => getComputedStyle(i).backgroundImage.startsWith('url(')),
                  pointer: typeof window.togglePointer, presenter: typeof window.togglePresenter};
        }"""
    )
    assert state == {"background": True, "loaded": True, "icons": True, "pointer": "function", "presenter": "function"}
    with page.expect_popup() as popup:
        page.keyboard.press("s")
    assert popup.value is not None
    with ThreadPoolExecutor(max_workers=1) as pool:  # the page fixture keeps an event loop in this thread
        stdout, stderr, code = pool.submit(run_cli, "render", str(target), "--report-only").result()
    assert (stdout.strip(), stderr, code) == ("report: OK", "", 0)


# -- E2E-006, E2E-044, E2E-045, E2E-056: recognition ---------------------------------------------------------


@needs_chromium
def test_declaration_or_marker_and_medical_wins(tmp_path: Path, page: Page) -> None:
    breathe = breathe_deck()
    declared_only = breathe.replace(MARKER_LINE, "", 1)
    marker_only = breathe.replace(' data-doc-template="breathe"', "", 1)
    both_medical = as_medical(breathe, keep_marker=True)
    for html in (declared_only, marker_only):
        assert charter_seen_by_lint(tmp_path, html) == "breathe"
        assert export_charter(tmp_path, html) == "breathe"
        assert picker_set(page, html) == "breathe"
    assert charter_seen_by_lint(tmp_path, both_medical) == "medical"
    assert export_charter(tmp_path, both_medical) == "medical"
    assert picker_set(page, both_medical) == "medical"


def _slide_parts(pptx: Path) -> dict[str, str]:
    with zipfile.ZipFile(pptx) as archive:
        names = sorted(n for n in archive.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
        return {name: hashlib.sha256(archive.read(name)).hexdigest() for name in names}


def test_legacy_medical_deck_stays_medical(tmp_path: Path) -> None:
    """E2E-044 (LEGACY half; the ten recorded fingerprints are test_export_golden.py)."""
    html = legacy_deck()
    assert charter_seen_by_lint(tmp_path, html) == "medical"
    assert lint_lines(tmp_path, html) == [
        'error L007 slide-1 class "cds-tile" belongs to another charter than medical',
        "lint: FAIL (1 error, 0 warnings)",
    ]
    source = write_deck(tmp_path / "legacy.html", html)
    # SPEC-0024: the painted export draws what the HTML shows (the Breathe looking background included); the charter
    # decision lives in the flow build, which is the degraded result, so it is asserted with the paint off.
    assert to_pptx(source, str(tmp_path / "painted.pptx")).charter == "medical"
    report = to_pptx(source, str(tmp_path / "legacy.pptx"), paint=False)
    assert report.charter == "medical"
    from pptx import Presentation

    for slide in Presentation(str(tmp_path / "legacy.pptx")).slides:
        assert not any(shape.shape_type == 13 and shape.width >= 960 * 12700 * 0.95 for shape in slide.shapes)


@needs_chromium
def test_marker_on_a_medical_declaration_stays_medical(tmp_path: Path, page: Page) -> None:
    """E2E-045."""
    html = legacy_deck().replace("    --med-teal:", MARKER_LINE + "    --med-teal:", 1)
    assert "--breathe-ice" in html
    assert charter_seen_by_lint(tmp_path, html) == "medical"
    assert export_charter(tmp_path, html) == "medical"
    assert picker_set(page, html) == "medical"


@needs_chromium
def test_marker_in_a_comment_does_not_count(tmp_path: Path, page: Page) -> None:
    """E2E-073: no declaration, the medical token, and the marker only inside a CSS comment."""
    html = (
        legacy_deck()
        .replace(' data-doc-template="medical"', "", 1)
        .replace("    --med-teal:", "    /* --breathe-ice */\n    --med-teal:", 1)
    )
    assert charter_seen_by_lint(tmp_path, html) == "medical"
    assert export_charter(tmp_path, html) == "medical"
    assert picker_set(page, html) == "medical"


def test_declaration_is_case_sensitive(tmp_path: Path) -> None:
    """E2E-056: ``Breathe`` is not ``breathe``; without the marker the medical token decides."""
    html = legacy_deck().replace('data-doc-template="medical"', 'data-doc-template="Breathe"', 1)
    assert charter_seen_by_lint(tmp_path, html) == "medical"
    assert export_charter(tmp_path, html) == "medical"


def test_detect_theme_of_the_shipped_breathe_files() -> None:
    for path in (BOOTSTRAP, REFERENCE):
        assert detect_theme(BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")).key == "breathe"


# -- E2E-034 to E2E-037, E2E-048, E2E-049, E2E-058 to E2E-061: lint ------------------------------------------


def test_foreign_classes_on_a_breathe_slide(tmp_path: Path) -> None:
    html = breathe_deck(
        breathe_slide("A", '<div class="med-rule"></div><div class="cds-tile"></div><p class="slide-h1">x</p>')
    )
    assert lint_lines(tmp_path, html) == [
        'error L007 slide-1 class "med-rule" belongs to another charter than breathe',
        'error L007 slide-1 class "cds-tile" belongs to another charter than breathe',
        'error L007 slide-1 class "slide-h1" belongs to another charter than breathe',
        "lint: FAIL (3 errors, 0 warnings)",
    ]


def test_breathe_classes_are_not_foreign(tmp_path: Path) -> None:
    """E2E-058."""
    body = '<div class="med-band"></div><span class="ei-logo">x</span><span class="stat-big">1</span>'
    html = breathe_deck(breathe_slide("A", body, background="cover-s0"))
    assert lint_lines(tmp_path, html) == [
        'error L007 slide-1 class "med-band" belongs to another charter than breathe',
        'error L007 slide-1 class "ei-logo" belongs to another charter than breathe',
        'error L007 slide-1 class "stat-big" belongs to another charter than breathe',
        "lint: FAIL (3 errors, 0 warnings)",
    ]


def test_colour_outside_the_breathe_palette(tmp_path: Path) -> None:
    """E2E-035."""
    body = '<span style="color:#EE5A02">a</span><span style="background:#0c7b70">b</span>'
    assert lint_lines(tmp_path, breathe_deck(breathe_slide("A", body))) == [
        "warning L011 slide-1 colour #EE5A02 is not in the breathe palette",
        "lint: OK (0 errors, 1 warning)",
    ]


def test_short_hex_and_url_text(tmp_path: Path) -> None:
    """E2E-059."""
    html = breathe_deck(
        breathe_slide("A", '<span style="color:#0c7">a</span>'),
        breathe_slide("B", '<span style="background:url(#EE5A02)">b</span>'),
    )
    assert lint_lines(tmp_path, html) == [
        "warning L011 slide-1 colour #0c7 is not in the breathe palette",
        "lint: OK (0 errors, 1 warning)",
    ]


def test_width_and_source_on_breathe(tmp_path: Path) -> None:
    """E2E-036: a .med-bleed child without width, a picture with an empty source; none on a title slide."""
    body = f'<div class="med-sources"><p class="med-source"> </p></div>{IMG}'
    content = breathe_slide("A", body).replace(
        '<div class="med-pane w-40 med-px-360">', '<div class="med-pane med-px-360">'
    )
    title = breathe_slide("B", IMG, kind="title")
    assert lint_lines(tmp_path, breathe_deck(content, title)) == [
        "error L008 slide-1 child of .med-bleed has no w-* width class",
        "error L009 slide-1 slide has an image and no source line",
        "lint: FAIL (2 errors, 0 warnings)",
    ]


def test_breathe_rows(tmp_path: Path) -> None:
    """E2E-060."""
    body = (
        '<div class="med-figs-deep"><div class="med-fig-col">a</div></div>'
        '<div class="med-prio-row"><div class="med-prio">b</div></div>'
        '<div class="med-prio-row"><div class="med-prio w-50">c</div><div class="med-prio w-50">d</div></div>'
    )
    assert lint_lines(tmp_path, breathe_deck(breathe_slide("A", body))) == [
        "error L008 slide-1 child of .med-figs-deep has no w-* width class",
        "error L008 slide-1 child of .med-prio-row has no w-* width class",
        "lint: FAIL (2 errors, 0 warnings)",
    ]


def test_source_rule_by_slide_type(tmp_path: Path) -> None:
    """E2E-061."""
    thanks = breathe_slide("A", IMG, kind="thanks", background="thanks-s5")
    section = breathe_slide("B", f'{IMG}<div class="med-sources"><p class="med-source">   </p></div>', kind="section")
    assert lint_lines(tmp_path, breathe_deck(thanks, section)) == [
        "error L009 slide-2 slide has an image and no source line",
        "lint: FAIL (1 error, 0 warnings)",
    ]


def test_greys_white_and_breathe_colours_accepted(tmp_path: Path) -> None:
    """E2E-037."""
    body = (
        '<span style="color:#FFFFFF">a</span><span style="color:#333">b</span><span style="color:#CD8684">c</span>'
        '<i class="med-ico med-ico-lungs-dark"></i>'
    )
    assert lint_lines(tmp_path, breathe_deck(breathe_slide("A", body, background="side-s4"))) == [OK]


def test_other_charters_keep_their_rules(tmp_path: Path) -> None:
    """E2E-048."""
    carbon = deck_carbon().replace("<p>Texte de", '<p class="med-bg-split-s1">Texte de', 1)
    lines = lint_lines(tmp_path, carbon, "carbon.html")
    assert any('class "med-bg-split-s1" belongs to another charter than carbon' in line for line in lines)
    medical = build_deck("medical", ("Cover", "B")).replace(
        '<div class="med-comment w-50">', '<div class="med-comment w-50"><div class="med-bleed"><div>x</div></div>', 1
    )
    assert not [line for line in lint_lines(tmp_path, medical, "medical.html") if "L008" in line]


def test_english_placeholder_in_any_charter(tmp_path: Path) -> None:
    """E2E-049."""
    html = build_deck("carbon", ("Cover", "Title of the presentation"))
    assert 'error L006 slide-1 template text left: "Title of the presentation"' in lint_lines(tmp_path, html)


# -- E2E-046, E2E-057 (lint half): switching decks -----------------------------------------------------------


def test_reference_declared_medical_switches_to_breathe(tmp_path: Path) -> None:
    """REF-MED is medical as is and Breathe once switched, with a clean lint."""
    ref_med = as_medical(REFERENCE.read_text(encoding="utf-8"))
    assert load_deck(write_deck(tmp_path / "ref-med.html", ref_med)).charter == "medical"
    switched = ref_med.replace('data-doc-template="medical"', 'data-doc-template="breathe"', 1)
    assert load_deck(write_deck(tmp_path / "switched.html", switched)).charter == "breathe"
    assert lint_lines(tmp_path, switched, "switched.html") == [OK]


def test_wcbip_switches_and_switches_back(tmp_path: Path) -> None:
    """E2E-046 and E2E-057, lint half (the private deck is read in place, never committed)."""
    original = wcbip_or_skip()
    assert load_deck(write_deck(tmp_path / "wcbip.html", original)).charter == "medical"
    before = lint_lines(tmp_path, original, "wcbip.html")
    switched = original.replace('data-doc-template="medical"', 'data-doc-template="breathe"', 1)
    assert load_deck(write_deck(tmp_path / "switched.html", switched)).charter == "breathe"
    assert lint_lines(tmp_path, switched, "switched.html") == [OK]
    back = switched.replace('data-doc-template="breathe"', 'data-doc-template="medical"', 1)
    assert lint_lines(tmp_path, back, "back.html") == before
    write_deck(tmp_path / "a.html", original)
    write_deck(tmp_path / "b.html", back)
    to_pptx(str(tmp_path / "a.html"), str(tmp_path / "a.pptx"))
    to_pptx(str(tmp_path / "b.html"), str(tmp_path / "b.pptx"))
    assert _slide_parts(tmp_path / "a.pptx") == _slide_parts(tmp_path / "b.pptx")


def test_french_then_english_placeholder(tmp_path: Path) -> None:
    """E2E-070: both placeholders on one medical slide, the English one checked after the French texts."""
    html = build_deck("medical", ("Cover", "Second")).replace(
        '<h1 class="slide-h1" data-editable="text">Second</h1>',
        '<h1 class="slide-h1" data-editable="text">Titre de la présentation</h1><p>Title of the presentation</p>',
        1,
    )
    lines = [line for line in lint_lines(tmp_path, html) if "L006" in line]
    assert lines == [
        'error L006 slide-1 template text left: "Titre de la présentation"',
        'error L006 slide-1 template text left: "Title of the presentation"',
    ]
