"""The committed EI bootstrap equals what tools/gen_ei_bootstrap.py generates from its reference."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REFERENCE = "templates/reference/slides/euro-information.html"
BOOTSTRAP = "templates/bootstrap/slides-ei-empty.html"


def test_committed_bootstrap_equals_its_generation(tmp_path: Path) -> None:
    """Regenerating in a temporary copy reproduces the committed bootstrap byte for byte."""
    (tmp_path / "tools").mkdir()
    shutil.copy(REPO / "tools" / "gen_ei_bootstrap.py", tmp_path / "tools" / "gen_ei_bootstrap.py")
    for relative in (REFERENCE, BOOTSTRAP):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / relative, target)

    subprocess.run(
        [sys.executable, "tools/gen_ei_bootstrap.py"], cwd=tmp_path, check=True, capture_output=True, timeout=60
    )

    assert (tmp_path / BOOTSTRAP).read_bytes() == (REPO / BOOTSTRAP).read_bytes()


def test_reference_keeps_single_anchor_rules() -> None:
    """The reference deck has one agenda number rule and one presentation mode comment."""
    reference = (REPO / REFERENCE).read_text(encoding="utf-8")

    assert reference.count(".agenda-list td.num") == 1
    assert reference.count("/* ── Mode présentation") == 1
