"""SPEC-0024 phase 1: ``tools/pptx_fidelity.py`` scores the PPTX export against the HTML render.

The pure functions (score, text recall, overflow, PPTX facts, reports) run in the default gate. The end to end run
needs soffice, pdftoppm and Chromium, takes seconds, and is marked ``slow``: ``make test ARGS='-m slow -k fidelity'``.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from bs4 import BeautifulSoup
from bs4.element import Tag
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches

from tests.conftest import needs_chromium

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "pptx_fidelity.py"


@pytest.fixture
def fid(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "tools"))
    sys.modules.pop("pptx_fidelity", None)
    return importlib.import_module("pptx_fidelity")


def picture(color: tuple[int, int, int], box: tuple[int, int, int, int] | None = None) -> Image.Image:
    image = Image.new("RGB", (960, 540), color)
    if box:
        ImageDraw.Draw(image).rectangle(box, fill=(200, 30, 30))
    return image


def test_identical_pictures_score_one(fid: ModuleType) -> None:
    image = picture((255, 255, 255), (100, 100, 500, 300))
    score, structure, colour = fid.visual_score(image, image.copy())
    assert score == pytest.approx(1.0)
    assert structure == pytest.approx(1.0)
    assert colour == pytest.approx(1.0)


def test_different_pictures_score_below_one_and_in_range(fid: ModuleType) -> None:
    score, _, colour = fid.visual_score(picture((255, 255, 255)), picture((20, 20, 40), (100, 100, 500, 300)))
    assert 0 <= score < 0.5
    assert colour < 0.5


def test_small_change_scores_between(fid: ModuleType) -> None:
    base = picture((255, 255, 255), (100, 100, 500, 300))
    moved = picture((255, 255, 255), (130, 100, 530, 300))
    near = fid.visual_score(base, moved)[0]
    far = fid.visual_score(base, picture((0, 0, 0)))[0]
    assert far < near < 1


def test_other_size_and_transparency_are_normalised(fid: ModuleType) -> None:
    small = Image.new("RGBA", (480, 270), (255, 255, 255, 0))
    assert fid.to_reference(small).size == (960, 540)
    assert fid.visual_score(small, picture((255, 255, 255)))[0] == pytest.approx(1.0)


def test_histogram_distance_bounds(fid: ModuleType) -> None:
    assert fid.histogram_distance(picture((0, 0, 0)), picture((0, 0, 0))) == 0
    assert fid.histogram_distance(picture((0, 0, 0)), picture((255, 255, 255))) == pytest.approx(1.0)


def test_text_recall(fid: ModuleType) -> None:
    html = fid.words_of("Titre de la Présentation, titre 2024")
    assert html == {"titre", "de", "la", "présentation", "2024"}
    recall, missing = fid.text_recall(html, {"titre", "de", "la"})
    assert recall == pytest.approx(0.6)
    assert missing == ["2024", "présentation"]
    assert fid.text_recall(set(), {"x"}) == (1.0, [])


def test_slide_text_skips_notes_scripts_and_hidden(fid: ModuleType) -> None:
    html = (
        '<section data-type="slide"><h1>Visible</h1><script>var secret=1</script><style>.a{}</style>'
        '<aside data-role="speaker-notes">notes only</aside><p hidden>hidden one</p>'
        '<p style="display: none">hidden two</p><p>Also seen</p></section>'
    )
    tag = BeautifulSoup(html, "html.parser").section
    assert isinstance(tag, Tag)
    assert fid.words_of(fid.slide_text(tag)) == {"visible", "also", "seen"}


def test_overflow_tolerance(fid: ModuleType) -> None:
    assert not fid.is_overflowing((0, 0, 100, 100), (1000, 500))
    assert not fid.is_overflowing((0, 0, 1005, 500), (1000, 500))
    assert fid.is_overflowing((0, 450, 100, 100), (1000, 500))
    assert fid.is_overflowing((-50, 0, 100, 100), (1000, 500))


def build_pptx(path: Path, empty_slide: bool = True) -> None:
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    layout = deck.slide_layouts[6]
    slide = deck.slides.add_slide(layout)
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame.text = "Hello world"
    low = slide.shapes.add_textbox(Inches(1), Inches(7), Inches(4), Inches(1.5))
    low.text_frame.text = "Falls off"
    slide.shapes.add_table(1, 2, Inches(1), Inches(3), Inches(4), Inches(1)).table.cell(0, 0).text = "cell words"
    image = path.parent / "p.png"
    picture((10, 10, 10)).save(image)
    slide.shapes.add_picture(str(image), 0, 0, Inches(2), Inches(2))
    if empty_slide:
        deck.slides.add_slide(layout)
    deck.save(str(path))


def test_inspect_pptx_counts(fid: ModuleType, tmp_path: Path) -> None:
    target = tmp_path / "d.pptx"
    build_pptx(target)
    full, empty = fid.inspect_pptx(target)
    assert (full.shapes, full.pictures, full.tables, full.text_boxes) == (4, 1, 1, 3)
    assert full.words == {"hello", "world", "falls", "off", "cell", "words"}
    assert full.overflow
    assert not full.flattened
    assert fid.editable_ratio(full) == pytest.approx(0.75)
    assert empty.shapes == 0
    assert fid.editable_ratio(empty) == 0


def test_flattened_slide_is_flagged(fid: ModuleType, tmp_path: Path) -> None:
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(10), Inches(5.625)
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    image = tmp_path / "p.png"
    picture((10, 10, 10)).save(image)
    slide.shapes.add_picture(str(image), 0, 0, deck.slide_width, deck.slide_height)
    target = tmp_path / "f.pptx"
    deck.save(str(target))
    (facts,) = fid.inspect_pptx(target)
    assert facts.flattened
    assert fid.editable_ratio(facts) == 0


def test_find_presentations_only_lists_presentations(fid: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "a.html").write_text('<html data-doc-type="presentation"><body></body></html>', encoding="utf-8")
    (tmp_path / "b.html").write_text('<html data-doc-type="document"><body></body></html>', encoding="utf-8")
    assert list(fid.find_presentations(tmp_path)) == ["a"]
    assert {"breathe", "medical", "slides-empty", "presentation-standard"} <= set(fid.find_presentations())


def test_reports_and_table(fid: ModuleType, tmp_path: Path) -> None:
    good = fid.SlideResult("s1", score=0.9, text_recall=1.0, shapes=3, pictures=1)
    bad = fid.SlideResult("s2", score=0.3, text_recall=0.5, empty=True)
    ok = fid.TemplateResult("deck", "templates/x.html", [good, bad], warnings=["empty: s2"])
    failed = fid.TemplateResult("broken", "templates/y.html", error="boom")
    assert ok.mean_score == pytest.approx(0.6)
    assert ok.worst is bad
    table = fid.summary_table([ok, failed])
    assert "deck" in table
    assert "s2 0.30" in table
    assert "ERROR boom" in table
    fid.write_reports([ok, failed], tmp_path)
    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert data[0]["mean_score"] == pytest.approx(0.6)
    assert data[0]["slides"][1]["empty"] is True
    assert "## deck" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_fontconfig_gives_soffice_real_fonts(fid: ModuleType, tmp_path: Path) -> None:
    """H1: a private fontconfig (font dirs, cache and substitutions under the work dir) instead of the empty one."""
    text = fid.fontconfig_text(tmp_path / "cache")
    assert "<dir>/System/Library/Fonts</dir>" in text
    assert f"<cachedir>{tmp_path / 'cache'}</cachedir>" in text
    assert "<family>IBM Plex Sans</family><accept><family>Helvetica Neue</family>" in text  # only when it is missing
    env = fid.soffice_environment(tmp_path)
    assert env["FONTCONFIG_FILE"] == str(tmp_path / "fonts.conf")
    assert (tmp_path / "fonts.conf").read_text(encoding="utf-8") == text.replace(
        str(tmp_path / "cache"), str(tmp_path / "fontcache")
    )


def test_unknown_template_is_a_tool_error(fid: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    if fid.missing_tools():
        pytest.skip("soffice or pdftoppm missing")
    assert fid.main(["--only", "nope", "--out", "/nonexistent-never-created"]) == 2
    assert "unknown template" in capsys.readouterr().err


def test_missing_tools_exit_two(
    fid: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(fid.shutil, "which", lambda _name: None)
    assert fid.main([]) == 2
    assert "needs soffice, pdftoppm" in capsys.readouterr().err


@pytest.mark.slow
@needs_chromium
@pytest.mark.skipif(
    shutil.which("soffice") is None or shutil.which("pdftoppm") is None, reason="soffice or pdftoppm missing"
)
def test_end_to_end_one_template(tmp_path: Path) -> None:
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(TOOL), "--only", "slides-empty", "--out", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert data[0]["template"] == "slides-empty"
    assert 0 < data[0]["mean_score"] <= 1
    assert list((tmp_path / "slides-empty").glob("*-side.png"))
