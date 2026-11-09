"""Guard: the presentation markers are real code, and the skill says the Carbon catalogue presents (SPEC-0019).

DT-020 (DR-004): each presentation file under ``templates/`` holds the fullscreen rule in a ``<style>`` block, the
``#btn-present`` element and the three functions in ``<script>`` blocks, all outside HTML comments. DT-021 (DR-005):
the ``slides-carbon`` topic states that ``ibm-carbon.html`` presents. The substring guard of
``tests/test_presentation_templates_fullscreen.py`` stays as it is (DEC-004).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

from tests.test_presentation_templates_fullscreen import TEMPLATES_ROOT, presentation_files

SKILL_DIR = Path(__file__).resolve().parents[1] / "skill"
CARBON_SENTENCE = "Le catalogue `ibm-carbon.html` a le mode présentation (bouton Présenter)."

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
PRESENT_BUTTON = re.compile(r'<[a-zA-Z][^>]*\bid="btn-present"')
FUNCTION_LINE = re.compile(
    r"^\s*(?:async\s+)?function (enterPresentation|exitPresentation|updateFullscreenScale)\s*\(", re.MULTILINE
)
FUNCTION_NAMES = ("enterPresentation", "exitPresentation", "updateFullscreenScale")
ALL_MARKERS = [
    ":fullscreen rule",
    "#btn-present element",
    "function enterPresentation",
    "function exitPresentation",
    "function updateFullscreenScale",
]

DISCOVERED = presentation_files(TEMPLATES_ROOT)


def structural_missing(html: str) -> list[str]:
    """Markers of ALL_MARKERS absent as real code, in ALL_MARKERS order (HTML comments dropped first)."""
    code = HTML_COMMENT.sub("", html)
    missing = []
    styles = (CSS_COMMENT.sub("", block) for block in STYLE_BLOCK.findall(code))
    if not any(":fullscreen" in style for style in styles):
        missing.append(ALL_MARKERS[0])
    if not PRESENT_BUTTON.search(code):
        missing.append(ALL_MARKERS[1])
    declared = {name for block in SCRIPT_BLOCK.findall(code) for name in FUNCTION_LINE.findall(block)}
    missing.extend(f"function {name}" for name in FUNCTION_NAMES if name not in declared)
    return missing


def failure_lines(relative: str, html: str) -> Iterator[str]:
    for marker in structural_missing(html):
        yield f"{relative}: missing {marker}"


@pytest.mark.parametrize("path", DISCOVERED, ids=lambda path: path.relative_to(TEMPLATES_ROOT).as_posix())
def test_presentation_markers_are_real_code(path: Path) -> None:
    relative = path.relative_to(TEMPLATES_ROOT).as_posix()
    lines = list(failure_lines(relative, path.read_text(encoding="utf-8")))
    assert lines == [], "\n".join(lines)


def test_markers_inside_one_html_comment_are_all_missing() -> None:
    html = (
        '<html data-doc-type="presentation"><body><!-- <style>.a:fullscreen{}</style>'
        '<button id="btn-present"></button><script>function enterPresentation() {}\n'
        "function exitPresentation() {}\nfunction updateFullscreenScale() {}</script> --></body></html>"
    )
    assert structural_missing(html) == ALL_MARKERS


def test_a_longer_function_name_is_not_the_function() -> None:
    html = (
        '<style>.a:fullscreen{}</style><button id="btn-present"></button><script>\n'
        "function enterPresentationLater() {}\nfunction exitPresentation() {}\n"
        "async function updateFullscreenScale() {}</script>"
    )
    assert structural_missing(html) == ["function enterPresentation"]


def test_a_fullscreen_rule_only_inside_a_script_string_is_missing() -> None:
    html = (
        '<button id="btn-present"></button><script>const css = ":fullscreen { }";\n'
        "function enterPresentation() {}\nfunction exitPresentation() {}\n"
        "function updateFullscreenScale() {}</script>"
    )
    assert structural_missing(html) == [":fullscreen rule"]


def test_a_fullscreen_rule_only_inside_a_css_comment_is_missing() -> None:
    html = "<style>/* :fullscreen */ .a{}</style>"
    assert structural_missing(html)[0] == ":fullscreen rule"


def test_the_failure_line_names_the_file_and_the_marker() -> None:
    assert next(iter(failure_lines("x.html", "<p></p>"))) == "x.html: missing :fullscreen rule"


def test_slides_carbon_topic_says_the_carbon_catalogue_presents(monkeypatch: pytest.MonkeyPatch) -> None:
    from mcp_htmleditor import cli as cli_module
    from mcp_htmleditor import config as config_module

    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(SKILL_DIR))
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)
    config_module.reset_settings_cache()
    try:
        result = CliRunner().invoke(cli_module.main, ["skill", "--type", "slides-carbon"])
    finally:
        config_module.reset_settings_cache()

    assert result.exit_code == 0
    assert CARBON_SENTENCE in result.stdout
