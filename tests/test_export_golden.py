"""Golden SHA-256 of the slide XML parts exported from ten templates and reference decks (SPEC-0012/DT-001).

The hashes cover the raw bytes of every ``ppt/slides/slide*.xml`` part read from the
zip produced by the real ``to_pptx``, not the zip file itself. They live in
``tests/testdata/pptx_slide_hashes.json`` and are recorded from the code as it was
before SPEC-0012. The tests never write that file; regenerate it, on purpose only:

    uv run python tests/test_export_golden.py --record
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from mcp_htmleditor.export.to_pptx import to_pptx

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_FILE = REPO_ROOT / "tests" / "testdata" / "pptx_slide_hashes.json"
# Recorded from `git show c507194:templates/reference/slides/example-carbon-complete.html` (SPEC-0016/DEC-010).
EXAMPLE_CARBON_COMPLETE_FILE = REPO_ROOT / "tests" / "testdata" / "example_carbon_complete_slide_hashes.json"
EXAMPLE_CARBON_COMPLETE = "templates/reference/slides/example-carbon-complete.html"
TEMPLATES = (
    "templates/bootstrap/slides-ei-empty.html",
    "templates/bootstrap/slides-empty.html",
    "templates/bootstrap/slides-medical-empty.html",
    "templates/reference/slides/euro-information.html",
    "templates/reference/slides/ibm-carbon.html",
    "templates/reference/slides/medical.html",
    "templates/reference/slides/example-ei-complete.html",
    "templates/reference/slides/example-medical-complete.html",
    "templates/reference/slides/presentation-standard.html",
    "templates/reference/slides/roadmap-one-pager.html",
)


def slide_hashes(template: str, workdir: Path) -> dict[str, str]:
    """Export a template and return the SHA-256 of each slide XML part, keyed by part name."""
    output = workdir / "out.pptx"
    to_pptx(str(REPO_ROOT / template), str(output))
    with zipfile.ZipFile(output) as archive:
        names = sorted(n for n in archive.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
        return {name: hashlib.sha256(archive.read(name)).hexdigest() for name in names}


@pytest.mark.parametrize("template", TEMPLATES)
def test_exported_slide_xml_matches_golden_hashes(template: str, tmp_path: Path) -> None:
    """Every slide part of the exported PPTX hashes to its recorded value."""
    golden = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))

    assert slide_hashes(template, tmp_path) == golden[template]


def test_golden_file_covers_exactly_the_ten_templates() -> None:
    """The golden file holds the ten files of DT-001, nothing else."""
    golden = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))

    assert sorted(golden) == sorted(TEMPLATES)


def test_example_carbon_complete_export_is_unchanged(tmp_path: Path) -> None:
    """SPEC-0016/BT-032: 9 slides, each slide XML equal to its export at c507194."""
    reference = json.loads(EXAMPLE_CARBON_COMPLETE_FILE.read_text(encoding="utf-8"))

    hashes = slide_hashes(EXAMPLE_CARBON_COMPLETE, tmp_path)

    assert len(hashes) == 9
    assert hashes == reference


def record() -> None:
    """Write the golden file from the current exporter (explicit act, never run by pytest)."""
    with tempfile.TemporaryDirectory() as tmp:
        recorded = {template: slide_hashes(template, Path(tmp)) for template in TEMPLATES}
    GOLDEN_FILE.write_text(json.dumps(recorded, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] != ["--record"]:
        sys.exit("usage: uv run python tests/test_export_golden.py --record")
    record()
