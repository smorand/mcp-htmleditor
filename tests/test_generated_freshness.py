"""SPEC-0011 (US-0004): ``--check`` mode of the two template generators.

The tools are stdlib scripts, so they run as subprocesses on a copy of the tools and
of the five template files in ``tmp_path``. Stale data is produced by editing the copy,
never the repository; every check also asserts that nothing was written.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

EI_SOURCE = "templates/reference/slides/euro-information.html"
EI_OUT = "templates/bootstrap/slides-ei-empty.html"
MEDICAL_SOURCE = "templates/bootstrap/slides-medical-empty.html"
MEDICAL_CATALOGUE = "templates/reference/slides/medical.html"
MEDICAL_EXAMPLE = "templates/reference/slides/example-medical-complete.html"
TEMPLATE_FILES = [EI_SOURCE, EI_OUT, MEDICAL_SOURCE, MEDICAL_CATALOGUE, MEDICAL_EXAMPLE]

EI_TOOL = "tools/gen_ei_bootstrap.py"
MEDICAL_TOOL = "tools/sync_medical_css.py"

EI_EDIT_LINE = 120
MEDICAL_EDIT_LINE = 40  # inside the style block, which starts at line 31


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """Copy tools/ and the five template files with the same relative layout."""
    for tool in (EI_TOOL, MEDICAL_TOOL, "tools/freshness.py"):
        _copy(REPO_ROOT / tool, tmp_path / tool)
    for rel in TEMPLATE_FILES:
        _copy(REPO_ROOT / rel, tmp_path / rel)
    return tmp_path


def _copy(src: Path, dst: Path) -> None:
    if not src.exists():  # freshness.py does not exist during the RED run
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def _run(root: Path, tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # fixed argv: this interpreter and a repo tool
        [sys.executable, tool, *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _edit_line(path: Path, number: int, old: str, new: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    assert old in lines[number - 1], f"{old!r} not on line {number} of {path.name}"
    lines[number - 1] = lines[number - 1].replace(old, new, 1)
    path.write_text("".join(lines), encoding="utf-8")


def _word_on_line(path: Path, number: int) -> str:
    return path.read_text(encoding="utf-8").splitlines()[number - 1].split()[-1]


def _make_medical_stale(root: Path) -> None:
    target = root / MEDICAL_CATALOGUE
    _edit_line(target, MEDICAL_EDIT_LINE, "#0B0E11", "#0B0E12")


# SPEC-0011/E2E-001
def test_ei_check_reports_fresh_on_committed_files(repo_copy: Path) -> None:
    result = _run(repo_copy, EI_TOOL, "--check")
    assert result.stdout == f"{EI_OUT}: fresh\n"
    assert result.stderr == ""
    assert result.returncode == 0


# SPEC-0011/E2E-002
def test_medical_check_reports_two_fresh_lines(repo_copy: Path) -> None:
    result = _run(repo_copy, MEDICAL_TOOL, "--check")
    assert result.stdout == f"{MEDICAL_CATALOGUE}: fresh\n{MEDICAL_EXAMPLE}: fresh\n"
    assert result.returncode == 0


# SPEC-0011/E2E-004
def test_ei_check_reports_first_differing_line_and_writes_nothing(repo_copy: Path) -> None:
    out = repo_copy / EI_OUT
    word = _word_on_line(out, EI_EDIT_LINE)
    _edit_line(out, EI_EDIT_LINE, word, word + "X")
    before = out.read_bytes()

    result = _run(repo_copy, EI_TOOL, "--check")

    assert result.stdout == f"{EI_OUT}: stale (first difference at line {EI_EDIT_LINE}); run: make bootstrap-ei\n"
    assert result.returncode == 1
    assert out.read_bytes() == before


def test_ei_check_prefix_case_counts_remaining_lines_plus_one(repo_copy: Path) -> None:
    out = repo_copy / EI_OUT
    lines = out.read_text(encoding="utf-8").splitlines(keepends=True)
    out.write_text("".join(lines[:-1]), encoding="utf-8")
    before = out.read_bytes()

    result = _run(repo_copy, EI_TOOL, "--check")

    assert result.stdout == f"{EI_OUT}: stale (first difference at line {len(lines)}); run: make bootstrap-ei\n"
    assert result.returncode == 1
    assert out.read_bytes() == before


def test_ei_check_trailing_newline_only_difference_is_stale(repo_copy: Path) -> None:
    out = repo_copy / EI_OUT
    text = out.read_text(encoding="utf-8")
    out.write_text(text.rstrip("\n"), encoding="utf-8")

    result = _run(repo_copy, EI_TOOL, "--check")

    count = len(text.splitlines())
    assert result.stdout == f"{EI_OUT}: stale (first difference at line {count}); run: make bootstrap-ei\n"
    assert result.returncode == 1


# SPEC-0011/E2E-005
def test_medical_check_reports_one_stale_copy_in_file_coordinates(repo_copy: Path) -> None:
    _make_medical_stale(repo_copy)
    before = {rel: (repo_copy / rel).read_bytes() for rel in (MEDICAL_CATALOGUE, MEDICAL_EXAMPLE)}

    result = _run(repo_copy, MEDICAL_TOOL, "--check")

    assert result.stdout == (
        f"{MEDICAL_CATALOGUE}: stale (first difference at line {MEDICAL_EDIT_LINE}); run: make sync-medical-css\n"
        f"{MEDICAL_EXAMPLE}: fresh\n"
    )
    assert result.returncode == 1
    assert {rel: (repo_copy / rel).read_bytes() for rel in before} == before


# SPEC-0011/E2E-007
def test_ei_check_missing_source_is_an_error_on_stderr(repo_copy: Path) -> None:
    (repo_copy / EI_SOURCE).unlink()
    before = (repo_copy / EI_OUT).read_bytes()

    result = _run(repo_copy, EI_TOOL, "--check")

    assert result.stderr == f"error: source not found: {EI_SOURCE}\n"
    assert result.stdout == ""
    assert result.returncode == 1
    assert (repo_copy / EI_OUT).read_bytes() == before


def test_medical_check_missing_source_is_an_error_on_stderr(repo_copy: Path) -> None:
    (repo_copy / MEDICAL_SOURCE).unlink()

    result = _run(repo_copy, MEDICAL_TOOL, "--check")

    assert result.stderr == f"error: source not found: {MEDICAL_SOURCE}\n"
    assert result.stdout == ""
    assert result.returncode == 1


# SPEC-0011/E2E-008
def test_ei_check_missing_output_is_reported_and_not_created(repo_copy: Path) -> None:
    (repo_copy / EI_OUT).unlink()

    result = _run(repo_copy, EI_TOOL, "--check")

    assert result.stdout == f"{EI_OUT}: missing; run: make bootstrap-ei\n"
    assert result.returncode == 1
    assert not (repo_copy / EI_OUT).exists()


def test_medical_check_missing_copy_is_reported_and_not_created(repo_copy: Path) -> None:
    (repo_copy / MEDICAL_CATALOGUE).unlink()

    result = _run(repo_copy, MEDICAL_TOOL, "--check")

    assert result.stdout == (f"{MEDICAL_CATALOGUE}: missing; run: make sync-medical-css\n{MEDICAL_EXAMPLE}: fresh\n")
    assert result.returncode == 1
    assert not (repo_copy / MEDICAL_CATALOGUE).exists()


# SPEC-0011/E2E-011
def test_medical_normal_mode_still_rewrites_and_prints_legacy_lines(repo_copy: Path) -> None:
    _make_medical_stale(repo_copy)

    result = _run(repo_copy, MEDICAL_TOOL)

    assert result.stdout == f"updated: {MEDICAL_CATALOGUE}\nok: {MEDICAL_EXAMPLE}\n"
    assert result.returncode == 0
    assert (repo_copy / MEDICAL_CATALOGUE).read_bytes() == (REPO_ROOT / MEDICAL_CATALOGUE).read_bytes()


def test_ei_normal_mode_still_writes_and_prints_ecrit(repo_copy: Path) -> None:
    (repo_copy / EI_OUT).unlink()

    result = _run(repo_copy, EI_TOOL)

    assert result.stdout.startswith(f"ecrit {EI_OUT} (")
    assert result.returncode == 0
    assert (repo_copy / EI_OUT).read_bytes() == (REPO_ROOT / EI_OUT).read_bytes()
