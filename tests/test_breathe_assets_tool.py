"""SPEC-0023 (US-0116): ``tools/breathe_assets.py`` redraws the Breathe decoration catalogue (E2E-038 to E2E-040).

The generator runs as a subprocess, the way ``make breathe-assets`` runs it, and always writes into ``tmp_path``.
The full catalogue takes about a minute: that run is marked ``slow``; ``make check`` runs a subset with ``--only``
and checks it against the shipped catalogue byte for byte, which also proves the catalogue is fresh.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "breathe_assets.py"
CATALOGUE = REPO_ROOT / "templates" / "assets" / "breathe"
SUBSET = ("bg-cover-s0.png", "bg-divider-s2.png", "icon-scope-now.png", "icon-lungs-dark.png", "logo-disc.png")


def run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and tool path
        [sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=240, check=False
    )


def test_subset_matches_the_shipped_catalogue(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = run_tool("--out", str(out), "--only", ",".join(SUBSET))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"{len(SUBSET)} files written to {out} (")
    assert sorted(p.name for p in out.iterdir()) == sorted(SUBSET)
    for name in SUBSET:
        assert (out / name).read_bytes() == (CATALOGUE / name).read_bytes(), f"{name}: run make breathe-assets"
    assert Image.open(out / "bg-cover-s0.png").size == (1920, 1080)
    assert Image.open(out / "icon-scope-now.png").size == (176, 176)


@pytest.mark.slow
def test_full_catalogue_is_redrawn(tmp_path: Path) -> None:
    """E2E-038: 56 backgrounds + 96 icons + logo disc + transparent partner logo + 4 samples."""
    out = tmp_path / "out"
    result = run_tool("--out", str(out))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"158 files written to {out} (")
    assert len(list(out.iterdir())) == 158
    for path in out.iterdir():
        assert path.read_bytes() == (CATALOGUE / path.name).read_bytes(), f"{path.name}: run make breathe-assets"


def test_list_prints_the_catalogue_and_writes_nothing(tmp_path: Path) -> None:
    """E2E-039."""
    out = tmp_path / "out"
    out.mkdir()
    result = run_tool("--list", "--out", str(out))

    lines = result.stdout.splitlines()
    assert result.returncode == 0
    assert lines[0] == "bg-cover-s0.png  class med-bg-cover-s0"
    assert sum(1 for line in lines if line.startswith("bg-")) == 56
    assert sum(1 for line in lines if line.startswith("icon-")) == 16
    assert "icon-scope-<ring|solid|dark|done|now|todo>.png  class med-ico-scope-<variant>" in lines
    assert list(out.iterdir()) == []


def test_missing_source_picture_stops_before_writing(tmp_path: Path) -> None:
    """E2E-040: the watermark source is absent from --src."""
    src = tmp_path / "src"
    src.mkdir()
    for name in ("logo-2026-botanical-transparent.png", "wiip-strong-logo.png"):
        shutil.copy(CATALOGUE / name, src / name)
    out = tmp_path / "out"
    result = run_tool("--src", str(src), "--out", str(out))

    assert result.returncode == 1
    assert result.stderr.strip() == f"error: source picture filigrane-stethoscope-poumons.png not found in {src}"
    assert not out.exists()


def test_unknown_subset_name_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = run_tool("--out", str(out), "--only", "bg-nowhere-s9.png")

    assert result.returncode == 2
    assert "unknown catalogue file bg-nowhere-s9.png" in result.stderr
    assert not out.exists()
