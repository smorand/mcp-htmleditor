"""Install step of the optional ``render`` extra and the fixtures every render test shares (US-0060)."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest
from _pytest.mark.structures import MarkDecorator

from tests import render_support as rs

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = re.compile(r"<article\b[^>]*>.*?</article>", re.S)


def _make(*args: str) -> str:
    result = subprocess.run(["make", *args], cwd=ROOT, capture_output=True, text=True, check=True)  # noqa: S603, S607
    return result.stdout


def _article(html: str, slide_id: str) -> str:
    matches = [m for m in ARTICLE.findall(html) if f'id="{slide_id}"' in m.split(">", 1)[0]]
    assert len(matches) == 1
    return matches[0]


def test_render_extra_declared_and_playwright_not_core():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["optional-dependencies"]["render"] == ["playwright>=1.62,<2"]
    assert not [d for d in data["project"]["dependencies"] if d.lower().startswith("playwright")]


def test_lock_records_render_extra():
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    package = next(p for p in lock["package"] if p["name"] == "mcp-htmleditor")
    assert any(dep["name"] == "playwright" for dep in package["optional-dependencies"]["render"])


def test_install_browser_dry_run_shows_both_branches():
    out = _make("-n", "install-browser")
    assert "-m playwright install chromium" in out
    assert "uv run --extra render python -m playwright install chromium" in out


def test_install_dry_run_ships_the_extra():
    assert ".[render]" in _make("-n", "install")


def test_install_browser_in_phony_and_help():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    phony = re.search(r"^\.PHONY:(?:[^\n]*\\\n)*[^\n]*", makefile, re.M).group(0)
    assert re.search(r"\binstall-browser\b", phony)
    assert "install-browser" in _make("help")


def test_ei_deck_has_eight_slides():
    html = rs.ei_deck_html()
    assert re.findall(r'data-type="slide" data-id="(slide-\d)"', html) == [f"slide-{i}" for i in range(8)]
    assert len(rs.EI_TITLES) == 8


def test_inject_in_body_changes_only_the_target_slide():
    html = rs.ei_deck_html()
    out = rs.inject_in_body(html, "slide-3", "<p>MARK</p>")
    target = _article(out, "slide-3")
    assert re.search(r'<div class="slide-body"[^>]*><p>MARK</p>', target)
    assert out.replace("<p>MARK</p>", "", 1) == html


def test_append_to_slide_puts_snippet_after_inner_frame():
    out = rs.append_to_slide(rs.ei_deck_html(), "slide-3", "<i>MARK</i>")
    target = _article(out, "slide-3")
    assert target.endswith("<i>MARK</i></article>")
    assert target.index("slide-inner") < target.index("<i>MARK</i>")
    assert out.count("<i>MARK</i>") == 1


def test_set_slide_class_marks_only_that_article():
    out = rs.set_slide_class(rs.med_deck_html(), "slide-4", "dark")
    assert 'class="slide dark"' in _article(out, "slide-4")
    assert out.count("slide dark") == out.count('class="slide dark"') == 2  # slide-2 from med_deck_html


def test_med_deck_marks_slide_two_dark():
    html = rs.med_deck_html()
    assert 'class="slide dark"' in _article(html, "slide-2")
    assert html.count('class="slide dark"') == 1
    assert len(re.findall(r'data-type="slide"', html)) == 6


def test_add_script_before_body_end():
    out = rs.add_script(rs.ei_deck_html(), "window.MARK = 1;")
    assert "<script>window.MARK = 1;</script>\n</body>" in out


def test_big_deck_counts_slides_and_images():
    assert rs.big_deck(40).count('data-type="slide"') == 40
    with_images = rs.big_deck(40, with_images=True)
    assert all("<img" in a for a in ARTICLE.findall(with_images))
    assert with_images.count('src="pics/ok.png"') == 20


def test_tiny_png_is_a_valid_one_pixel_picture(tmp_path):
    path = tmp_path / "t.png"
    path.write_bytes(rs.tiny_png_bytes())
    assert rs.png_size(path) == (1, 1)
    assert rs.png_pixel(path, 0, 0) == (255, 255, 255)


def test_needs_chromium_is_a_skipif_mark():
    assert isinstance(rs.needs_chromium, MarkDecorator)
    assert rs.needs_chromium.name == "skipif"


@pytest.mark.parametrize("name", ["ei_deck_html", "med_deck_html"])
def test_deck_builders_are_deterministic(name):
    assert getattr(rs, name)() == getattr(rs, name)()
