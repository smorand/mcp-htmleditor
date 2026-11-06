"""Port range tests give the same verdict whatever other process listens (SPEC-0014 BR-015, BR-016, DEC-015).

A holder child process listens, without ``SO_REUSEADDR``, on ports of ``127.0.0.1``; ``tests/test_port_range.py``
then runs in a child pytest and must report ``4 passed``. A port the holder cannot bind is already held by someone
else, which serves the same purpose. Every child has a ``timeout=`` so a hang cannot hang the run that observes it.
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

HOLDER = """
import socket, sys
held = []
for port in map(int, sys.argv[1:]):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        continue
    sock.listen(1)
    held.append(sock)
print("ready", flush=True)
sys.stdin.read()
"""

READY_SECONDS = 10
CHILD_SECONDS = 60


def read_first_line(holder: subprocess.Popen[str]) -> str:
    """First stdout line of ``holder``, read by a thread so a silent holder fails after ``READY_SECONDS``."""
    lines: queue.Queue[str] = queue.Queue()
    stdout = holder.stdout
    assert stdout is not None
    threading.Thread(target=lambda: lines.put(stdout.readline()), daemon=True).start()
    return lines.get(timeout=READY_SECONDS)


@pytest.fixture
def hold_ports() -> Iterator[Callable[[list[int]], None]]:
    """Return a function that starts a holder on the given ports; every holder is stopped at teardown."""
    holders: list[subprocess.Popen[str]] = []

    def start(ports: list[int]) -> None:
        holder = subprocess.Popen(  # noqa: S603  fixed argument list, no shell, own interpreter
            [sys.executable, "-c", HOLDER, *map(str, ports)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        holders.append(holder)
        assert read_first_line(holder).strip() == "ready"

    yield start

    for holder in holders:
        assert holder.stdin is not None
        holder.stdin.close()
        try:
            holder.wait(timeout=10)
        except subprocess.TimeoutExpired:
            holder.kill()
            holder.wait()
        assert holder.stdout is not None
        holder.stdout.close()


def run_port_range_tests() -> subprocess.CompletedProcess[str]:
    """Run ``tests/test_port_range.py`` in a child pytest with the project configuration."""
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        str(REPO / "pyproject.toml"),
        "--rootdir",
        str(REPO),
        "-p",
        "no:cacheprovider",
        "tests/test_port_range.py",
    ]
    return subprocess.run(  # noqa: S603  fixed argument list, no shell, own interpreter
        command,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=CHILD_SECONDS,
        check=False,
    )


def test_port_range_tests_pass_with_an_editor_running(hold_ports: Callable[[list[int]], None]) -> None:
    """BT-004: another process listens on 7840 and 7842, the range tests still report 4 passed."""
    hold_ports([7840, 7842])

    done = run_port_range_tests()

    assert "4 passed" in done.stdout, done.stdout + done.stderr
    assert done.returncode == 0


def test_port_range_tests_pass_when_other_processes_hold_the_whole_range(
    hold_ports: Callable[[list[int]], None],
) -> None:
    """BT-018: another process holds 7839 to 7849, the range tests still report 4 passed."""
    hold_ports(list(range(7839, 7850)))

    done = run_port_range_tests()

    assert "4 passed" in done.stdout, done.stdout + done.stderr
    assert done.returncode == 0
