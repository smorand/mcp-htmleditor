"""Bounded stdio reads (SPEC-0014 BR-014, BT-003, BT-017, DEC-009, DEC-010).

The default run proves the mechanism with ``LINE_TIMEOUT_SECONDS`` shortened to 1 s; the two ``slow`` tests use the
literal 30 s. The child runner of BT-003 follows ``tests/test_suite_time_limit.py`` (own confcutdir and basetemp).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, ClassVar

import pytest

from tests import stdio_support
from tests.stdio_support import SILENT_CHILD, StdioSession, mcp_command, run_session

REPO = Path(__file__).resolve().parents[1]
SILENT_TEXT = "import time; time.sleep(3600)"
HELPER_USERS = ["test_render_tool.py", "test_deck_tools_mcp.py", "test_deck_tools_surface.py"]
CHILD_FILE = """
from pathlib import Path

from tests.stdio_support import SILENT_CHILD, run_session


def test_silent():
    run_session([], {1}, command=SILENT_CHILD, cwd=Path.cwd())


def test_ok():
    assert True
"""


class RecordingPopen(subprocess.Popen[str]):
    started: ClassVar[list[subprocess.Popen[str]]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        RecordingPopen.started.append(self)


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.Popen[str]]:
    RecordingPopen.started = []
    monkeypatch.setattr(stdio_support.subprocess, "Popen", RecordingPopen)
    return RecordingPopen.started


def silent_processes() -> list[str]:
    done = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True, check=True)  # noqa: S607
    return [line for line in done.stdout.splitlines() if SILENT_TEXT in line and "ps -axo" not in line]


def test_silent_child_short_bound(monkeypatch: pytest.MonkeyPatch, recorded: list[subprocess.Popen[str]]) -> None:
    monkeypatch.setattr(stdio_support, "LINE_TIMEOUT_SECONDS", 1.0)
    started = time.monotonic()
    with pytest.raises(pytest.fail.Exception, match="the server did not answer within 1 s"):
        run_session([], {1}, command=SILENT_CHILD, cwd=REPO)
    assert time.monotonic() - started < 3
    assert recorded[0].poll() is not None


def test_read_message_short_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stdio_support, "LINE_TIMEOUT_SECONDS", 1.0)
    session = StdioSession(SILENT_CHILD, cwd=REPO)
    with session, pytest.raises(pytest.fail.Exception, match="the server did not answer within 1 s"):
        session.read_message()
    assert session.process.poll() is not None


def test_partial_line_then_silence_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stdio_support, "LINE_TIMEOUT_SECONDS", 1.0)
    partial = [
        sys.executable,
        "-c",
        "import sys, time; sys.stdout.write('{\"id\"'); sys.stdout.flush(); time.sleep(3600)",
    ]
    with pytest.raises(pytest.fail.Exception, match="the server did not answer within 1 s"):
        run_session([], {1}, command=partial, cwd=REPO)


def test_closed_stdout_keeps_its_message() -> None:
    with pytest.raises(AssertionError, match="the server closed stdout before answering"):
        run_session([], {1}, command=[sys.executable, "-c", "pass"], cwd=REPO)


def test_a_stray_text_line_fails() -> None:
    chatty = [sys.executable, "-c", "print('not json')"]
    with pytest.raises(ValueError):
        run_session([], {1}, command=chatty, cwd=REPO)


def test_a_real_session_answers() -> None:
    with StdioSession(mcp_command(), cwd=REPO) as session:
        session.initialize()
        result = session.call_tool(2, "list_templates", {})
    assert not result.get("isError")


def test_the_three_stdio_tests_use_the_shared_session() -> None:
    for name in HELPER_USERS:
        source = (REPO / "tests" / name).read_text(encoding="utf-8")
        assert "stdio_support" in source, name
        assert ".readline()" not in source, name


@pytest.mark.slow
def test_bt_017_every_stdio_helper_is_bounded(recorded: list[subprocess.Popen[str]]) -> None:
    started = time.monotonic()
    with pytest.raises(pytest.fail.Exception, match="the server did not answer within 30 s"):
        run_session([], {1}, command=SILENT_CHILD, cwd=REPO)
    assert time.monotonic() - started < 35
    session = StdioSession(SILENT_CHILD, cwd=REPO)
    started = time.monotonic()
    with session, pytest.raises(pytest.fail.Exception, match="the server did not answer within 30 s"):
        session.read_message()
    assert time.monotonic() - started < 35
    assert session.process.poll() is not None
    assert all(child.poll() is not None for child in recorded)


@pytest.mark.slow
def test_bt_003_a_silent_stdio_server_fails_its_test_and_the_run_ends(tmp_path: Path) -> None:
    test_file = tmp_path / "test_throwaway.py"
    test_file.write_text(CHILD_FILE, encoding="utf-8")
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
        str(tmp_path),
        "--basetemp",
        str(tmp_path / "basetemp"),
        str(test_file),
    ]
    started = time.monotonic()
    done = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=120, check=False)  # noqa: S603
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert time.monotonic() - started < 45, output
    assert "test_silent" in output
    assert "the server did not answer within 30 s" in output
    assert "1 passed" in output
    assert silent_processes() == []
