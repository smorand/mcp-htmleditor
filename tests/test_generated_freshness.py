"""SPEC-0011 (US-0004): ``--check`` mode of the two template generators.

The tools are stdlib scripts, so they run as subprocesses on a copy of the tools and
of the five template files in ``tmp_path``. Stale data is produced by editing the copy,
never the repository; every check also asserts that nothing was written.
"""

from __future__ import annotations

import hashlib
import os
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
POINTER_SOURCE = "templates/bootstrap/slides-empty.html"  # `make check-generated` also runs the pointer sync
TEMPLATE_FILES = [EI_SOURCE, EI_OUT, MEDICAL_SOURCE, MEDICAL_CATALOGUE, MEDICAL_EXAMPLE, POINTER_SOURCE]

EI_TOOL = "tools/gen_ei_bootstrap.py"
MEDICAL_TOOL = "tools/sync_medical_css.py"

EI_EDIT_LINE = 120
MEDICAL_EDIT_LINE = 40  # inside the style block, which starts at line 31


# SPEC-0023: make check-generated also checks the Breathe shipped files and the Breathe picker set.
BREATHE_FILES = (
    "templates/reference/slides/breathe.html",
    "templates/bootstrap/slides-breathe-empty.html",
    "src/mcp_htmleditor/static/slide-layouts.js",
)


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """Copy tools/ and the five template files with the same relative layout."""
    for tool in (
        EI_TOOL,
        MEDICAL_TOOL,
        "tools/sync_deck_pointer.py",
        "tools/freshness.py",
        "tools/sync_breathe_layouts.py",
    ):
        _copy(REPO_ROOT / tool, tmp_path / tool)
    for rel in (*TEMPLATE_FILES, *BREATHE_FILES):
        _copy(REPO_ROOT / rel, tmp_path / rel)
    for rel in ("Makefile", "pyproject.toml"):
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


def _run_make(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run make in the copy, reusing the repository virtual environment (DEC-004)."""
    env = {**os.environ, "UV_NO_SYNC": "1", "UV_PROJECT_ENVIRONMENT": str(REPO_ROOT / ".venv")}
    return subprocess.run(  # noqa: S603  # fixed argv: make with repo targets
        ["make", *args],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )


def _checksums(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in ("templates", "tools")
        for path in sorted((root / folder).rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts  # interpreter bytecode, not a tool output
    }


# SPEC-0011/E2E-003
def test_make_check_generated_reports_three_fresh_lines(repo_copy: Path) -> None:
    result = _run_make(repo_copy, "check-generated")

    for line in (f"{EI_OUT}: fresh", f"{MEDICAL_CATALOGUE}: fresh", f"{MEDICAL_EXAMPLE}: fresh"):
        assert line in result.stdout.splitlines()
    assert result.returncode == 0


# SPEC-0011/E2E-006
def test_make_check_generated_runs_both_tools_when_both_medical_copies_are_stale(repo_copy: Path) -> None:
    _make_medical_stale(repo_copy)
    _edit_line(repo_copy / MEDICAL_EXAMPLE, MEDICAL_EDIT_LINE, "#0B0E11", "#0B0E12")
    before = _checksums(repo_copy)

    result = _run_make(repo_copy, "check-generated")

    lines = result.stdout.splitlines()
    stale = f"stale (first difference at line {MEDICAL_EDIT_LINE}); run: make sync-medical-css"
    assert f"{EI_OUT}: fresh" in lines
    assert f"{MEDICAL_CATALOGUE}: {stale}" in lines
    assert f"{MEDICAL_EXAMPLE}: {stale}" in lines
    assert result.returncode != 0
    assert _checksums(repo_copy) == before


# SPEC-0011/E2E-009
def test_check_mode_never_writes_with_stale_and_missing_files(repo_copy: Path) -> None:
    out = repo_copy / EI_OUT
    word = _word_on_line(out, EI_EDIT_LINE)
    _edit_line(out, EI_EDIT_LINE, word, word + "X")
    _make_medical_stale(repo_copy)
    (repo_copy / MEDICAL_EXAMPLE).unlink()
    before = _checksums(repo_copy)

    ei = _run(repo_copy, EI_TOOL, "--check")
    medical = _run(repo_copy, MEDICAL_TOOL, "--check")

    assert ei.returncode == 1
    assert medical.returncode == 1
    assert _checksums(repo_copy) == before


# SPEC-0011/E2E-010
def test_make_check_stops_at_check_generated_on_a_stale_bootstrap(repo_copy: Path) -> None:
    out = repo_copy / EI_OUT
    word = _word_on_line(out, EI_EDIT_LINE)
    _edit_line(out, EI_EDIT_LINE, word, word + "X")

    result = _run_make(repo_copy, "check")

    assert f"{EI_OUT}: stale (first difference at line {EI_EDIT_LINE}); run: make bootstrap-ei" in result.stdout
    assert result.returncode != 0
    assert "Running tests with coverage" not in result.stdout


def test_make_check_prints_the_fresh_lines_among_its_steps(repo_copy: Path) -> None:
    """On fresh files `make check` runs check-generated; the heavy steps are taken as up to date (-o)."""
    skipped = [flag for step in ("lint", "format-check", "typecheck", "security", "test-cov") for flag in ("-o", step)]

    result = _run_make(repo_copy, *skipped, "check")

    assert f"{EI_OUT}: fresh" in result.stdout
    assert result.returncode == 0


def test_make_check_lists_check_generated_before_lint(repo_copy: Path) -> None:
    result = _run_make(repo_copy, "-n", "check")

    assert result.returncode == 0
    assert 0 <= result.stdout.index("gen_ei_bootstrap.py --check") < result.stdout.index("ruff check")
