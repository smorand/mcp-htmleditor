"""Results of the two charter detectors on the eight bootstrap templates (SPEC-0012/DT-002).

``detect_theme`` (Python, PPTX export) and ``detectTemplate`` (JavaScript, run in
Chromium) are compared with ``tests/testdata/detector_table.json``, recorded from the
code as it was before SPEC-0012, and with the facts asserted explicitly below. The
tests never write that file; regenerate it, on purpose only:

    uv run python tests/test_charter_detection.py --record
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright

from mcp_htmleditor import config as config_module
from mcp_htmleditor.export.pptx_style import THEME_CARBON, THEME_EI, THEME_GENERIC, THEME_MEDICAL, detect_theme
from mcp_htmleditor.templates import template_path

REPO_ROOT = Path(__file__).resolve().parents[1]
TABLE_FILE = REPO_ROOT / "tests" / "testdata" / "detector_table.json"
LAYOUTS_JS = REPO_ROOT / "src" / "mcp_htmleditor" / "static" / "slide-layouts.js"
KEYS = ("ei", "carbon", "medical", "doc", "doc-perso", "doc-ei", "mail", "website")

# The facts known before SPEC-0012: key -> (detect_theme Theme.key, detectTemplate).
FACTS = {
    "ei": (THEME_EI.key, "ei"),
    "carbon": (THEME_CARBON.key, "carbon"),
    "medical": (THEME_MEDICAL.key, "medical"),
    "doc": (THEME_GENERIC.key, "carbon"),
    "doc-perso": (THEME_GENERIC.key, "carbon"),
    "doc-ei": (THEME_EI.key, "ei"),
    "mail": (THEME_GENERIC.key, "carbon"),
    "website": (THEME_CARBON.key, "carbon"),
}


@pytest.fixture(autouse=True)
def repo_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the bootstrap templates of the repo, never an installed copy."""
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO_ROOT / "templates"))
    config_module.reset_settings_cache()


def template_html(key: str) -> str:
    return template_path(key).read_text(encoding="utf-8")


def python_theme(key: str) -> str:
    return detect_theme(BeautifulSoup(template_html(key), "html.parser")).key


def browser_template(page: Page, key: str) -> str:
    """Run the real slide-layouts.js ``detectTemplate`` on a template in Chromium."""
    page.set_content(template_html(key))
    page.add_script_tag(path=str(LAYOUTS_JS))
    # The injected script would itself match the markers (its source names them): drop the tag, keep the function.
    page.evaluate("document.querySelectorAll('script').forEach((s) => s.remove())")
    return str(page.evaluate("detectTemplate(document)"))


def _recorded() -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = json.loads(TABLE_FILE.read_text(encoding="utf-8"))
    return table


def test_recorded_table_holds_the_known_facts() -> None:
    """The recorded table equals the facts of DT-002, key for key."""
    expected = {key: {"detect_theme": theme, "detectTemplate": tpl} for key, (theme, tpl) in FACTS.items()}

    assert _recorded() == expected


@pytest.mark.parametrize("key", KEYS)
def test_detect_theme_matches_the_recorded_table(key: str) -> None:
    """detect_theme returns the recorded Theme key, and the known fact."""
    assert python_theme(key) == _recorded()[key]["detect_theme"]
    assert python_theme(key) == FACTS[key][0]


@pytest.mark.parametrize("key", KEYS)
def test_detect_template_matches_the_recorded_table(key: str, page: Page) -> None:
    """detectTemplate, run in Chromium, returns the recorded template key, and the known fact."""
    result = browser_template(page, key)

    assert result == _recorded()[key]["detectTemplate"]
    assert result == FACTS[key][1]


def record() -> None:
    """Write the detector table from the current detectors (explicit act, never run by pytest)."""
    os.environ["HTMLEDITOR_TEMPLATES_DIR"] = str(REPO_ROOT / "templates")
    config_module.reset_settings_cache()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        table = {
            key: {"detect_theme": python_theme(key), "detectTemplate": browser_template(page, key)} for key in KEYS
        }
        browser.close()
    TABLE_FILE.write_text(json.dumps(table, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] != ["--record"]:
        sys.exit("usage: uv run python tests/test_charter_detection.py --record")
    record()
