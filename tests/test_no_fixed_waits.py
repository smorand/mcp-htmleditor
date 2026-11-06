"""Guard against unjustified fixed waits in browser tests (SPEC-0014, BR-008, BR-009, DEC-014).

A ``wait_for_timeout(`` line in a ``tests/test_*_e2e.py`` file must end with a comment ``# pacing: <reason>``
(a spacing between two user actions, no result asserted after it). The observation loop and the settle delay
live in ``tests/browser_wait.py``, which is not scanned.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BROWSER_FILES = sorted((REPO / "tests").glob("test_*_e2e.py"))
WAIT_CALL = re.compile(r"wait_for_timeout\(")
PACING_COMMENT = re.compile(r"#\s*pacing:\s*\S")


def unjustified_waits(path: Path) -> list[int]:
    """Return the 1-based line numbers of ``wait_for_timeout(`` calls without a ``# pacing:`` comment."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        number
        for number, line in enumerate(lines, start=1)
        if WAIT_CALL.search(line) and not PACING_COMMENT.search(line)
    ]


@pytest.mark.parametrize("path", BROWSER_FILES, ids=lambda path: path.name)
def test_browser_files_have_no_unjustified_fixed_wait(path: Path) -> None:
    lines = unjustified_waits(path)
    assert lines == [], f"{path.name}: wait_for_timeout without '# pacing: <reason>' at lines {lines}"


def test_the_guard_reports_an_uncommented_wait(tmp_path: Path) -> None:
    sample = tmp_path / "test_sample_e2e.py"
    sample.write_text(
        "def test_x(page):\n"
        "    page.keyboard.press('a')\n"
        "    page.wait_for_timeout(500)\n"
        "    page.wait_for_timeout(1000)  # pacing: between two keys\n",
        encoding="utf-8",
    )
    assert unjustified_waits(sample) == [3]


def test_the_guard_scans_browser_files() -> None:
    assert BROWSER_FILES, "no tests/test_*_e2e.py found: the guard would pass on nothing"
