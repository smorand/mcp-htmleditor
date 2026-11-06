"""Per test time limit (SPEC-0014 BR-012, BR-013, DEC-007, DEC-008, DEC-009).

The limits are checked by child pytest runs on throwaway files under ``tmp_path``: a hung test must not hang the
run that observes it, so every child has a ``timeout=`` on ``subprocess.run``.

Two options keep the child fast whatever lives in ``$TMPDIR``. ``--confcutdir`` at the throwaway folder: the file is
outside the rootdir, so pytest otherwise collects every ancestor directory of it, and ``$TMPDIR`` held 75k entries
(10 s of collection under load). ``--basetemp`` of its own: otherwise the child shares ``$TMPDIR/pytest-of-<user>/``
with every pytest run on the machine and deletes whichever old ``pytest-N`` became stale (a finished full run holds
about 80k files). The sleeper is judged on its own call duration from the child's JUnit report, never on the child's
wall time, which also counts interpreter start up and plugin imports.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import pytest

from tests import conftest

REPO = Path(__file__).resolve().parents[1]

SLEEPER_FILE = """
import time

import pytest


def test_sleeper():
    time.sleep({sleeper_seconds})


def test_ok():
    assert True


@pytest.mark.slow
def test_slow_sleeper():
    time.sleep({slow_seconds})
"""


@dataclass(frozen=True)
class ChildRun:
    """Outcome of one child pytest run."""

    returncode: int
    output: str
    call_seconds: dict[str, float]


def write_sleepers(folder: Path, sleeper_seconds: int, slow_seconds: int) -> Path:
    """A throwaway test file holding a sleeper, a passing test and a ``slow`` sleeper."""
    path = folder / "test_throwaway.py"
    path.write_text(SLEEPER_FILE.format(sleeper_seconds=sleeper_seconds, slow_seconds=slow_seconds), encoding="utf-8")
    return path


def run_child(test_file: Path, extra: list[str], wall_seconds: float) -> ChildRun:
    """Run pytest on ``test_file`` with the project configuration and the conftest hook, within ``wall_seconds``."""
    report = test_file.parent / "report.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        str(REPO / "pyproject.toml"),
        "--rootdir",
        str(REPO),
        "-p",
        "tests.conftest",
        "-p",
        "no:cacheprovider",
        "--confcutdir",
        str(test_file.parent),
        "--basetemp",
        str(test_file.parent / "basetemp"),
        "--junitxml",
        str(report),
        *extra,
        str(test_file),
    ]
    done = subprocess.run(  # noqa: S603  fixed argument list, no shell, own interpreter
        command,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=wall_seconds,
        check=False,
    )
    return ChildRun(done.returncode, done.stdout + done.stderr, read_call_seconds(report))


def read_call_seconds(report: Path) -> dict[str, float]:
    """Duration of every test of a child run, by test name, from its JUnit report."""
    cases = ElementTree.parse(report).getroot().iter("testcase")
    return {case.attrib["name"]: float(case.attrib["time"]) for case in cases}


def test_the_configured_limit_is_60_seconds() -> None:
    options = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert options["timeout"] == 60
    assert options["timeout_method"] == "signal"
    assert conftest.SLOW_TEST_TIMEOUT_SECONDS == 900


def test_short_limit_fails_the_sleeper_and_runs_the_rest(tmp_path: Path) -> None:
    # The 120 s sleep is cut at 2 s; the 60 s wall guard alone proves it, the call duration proves it was the limit.
    test_file = write_sleepers(tmp_path, sleeper_seconds=120, slow_seconds=1)
    run = run_child(test_file, ["-o", "timeout=2", "-k", "test_sleeper or test_ok"], wall_seconds=60)
    assert run.returncode == 1, run.output
    assert 2 <= run.call_seconds["test_sleeper"] < 30, run.output
    assert "Timeout" in run.output
    assert "1 passed" in run.output


def test_slow_tests_get_their_own_limit(tmp_path: Path) -> None:
    test_file = write_sleepers(tmp_path, sleeper_seconds=1, slow_seconds=3)
    run = run_child(test_file, ["-m", "slow", "-o", "timeout=1"], wall_seconds=60)
    assert run.returncode == 0, run.output
    assert "1 passed" in run.output


@pytest.mark.slow
def test_a_test_over_its_limit_fails_and_the_run_continues(tmp_path: Path) -> None:
    """SPEC-0014/BT-016, with the literal 60 and 900 second values."""
    test_file = write_sleepers(tmp_path, sleeper_seconds=120, slow_seconds=70)
    default_run = run_child(test_file, ["-k", "test_sleeper or test_ok"], wall_seconds=150)
    assert default_run.returncode == 1, default_run.output
    assert 60 <= default_run.call_seconds["test_sleeper"] < 90, default_run.output
    assert "Timeout" in default_run.output
    assert "1 passed" in default_run.output
    slow_run = run_child(test_file, ["-m", "slow"], wall_seconds=150)
    assert "1 passed" in slow_run.output, slow_run.output
    assert slow_run.call_seconds["test_slow_sleeper"] >= 70, slow_run.output
