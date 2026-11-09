"""Tests for the EditorState singleton and its persistence in the state directory (SPEC-0009)."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from mcp_htmleditor import config
from mcp_htmleditor.config import Settings
from mcp_htmleditor.http_server import start_http_server, stop_http_server
from mcp_htmleditor.state import EditorState, get_state

from .deck_support import call_tool, deck_ei, write_deck

REPO = Path(__file__).resolve().parents[1]
T0 = 1_700_000_000.0


class FakeClock:
    """A clock the tests move by hand; assigned to ``EditorState.clock``."""

    def __init__(self, now: float = T0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _file_dir(path: Path) -> Path:
    key = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:32]
    return config.state_dir() / "files" / key


@pytest.fixture
def clock(fresh_state: EditorState) -> FakeClock:
    fake = FakeClock()
    fresh_state.clock = fake
    return fake


@pytest.fixture
def deck(tmp_path: Path) -> Path:
    folder = tmp_path / "work"
    folder.mkdir()
    return Path(write_deck(folder / "deck.html", deck_ei()))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int) -> None:
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail("HTTP server did not start in time")


@pytest.fixture
def served(deck: Path, fresh_state: EditorState) -> Iterator[Path]:
    port = _free_port()
    start_http_server(str(deck), port=port)
    _wait_for_port(port)
    try:
        yield deck
    finally:
        stop_http_server()


# ----------------------------------------------------------------------
# Singleton, defaults and mtime: unchanged tests
# ----------------------------------------------------------------------


def test_singleton_identity(fresh_state: EditorState) -> None:
    """get_state() always returns the same instance."""
    assert get_state() is fresh_state
    assert EditorState() is fresh_state


def test_singleton_preserves_state_across_init(fresh_state: EditorState) -> None:
    """Re-instantiating does not reset already-populated fields."""
    fresh_state.port = 9999
    # A second construction must not wipe the field (init guard).
    again = EditorState()
    assert again.port == 9999


def test_defaults(fresh_state: EditorState) -> None:
    """A fresh state exposes the documented defaults."""
    assert fresh_state.current_file is None
    assert fresh_state.port == 7842
    assert fresh_state.server_pid is None
    assert fresh_state.update_in_progress is False
    assert isinstance(fresh_state.poll_interval, int)


def test_set_file_resolves_and_persists(fresh_state: EditorState, html_file: Path) -> None:
    """set_file stores an absolute path and writes server.json in the state dir, nothing next to the file."""
    fresh_state.set_file(str(html_file))
    assert fresh_state.current_file == str(html_file.resolve())

    data = json.loads((_file_dir(html_file) / "server.json").read_text(encoding="utf-8"))
    assert data["file"] == str(html_file.resolve())
    assert sorted(p.name for p in html_file.parent.iterdir()) == [html_file.name]


def test_set_update_flag_persists(fresh_state: EditorState, html_file: Path) -> None:
    """start_update writes update.json and raises the flag; end_update removes it."""
    fresh_state.set_file(str(html_file))
    assert fresh_state.start_update() == 120
    assert fresh_state.update_in_progress is True

    record = _file_dir(html_file) / "update.json"
    data = json.loads(record.read_text(encoding="utf-8"))
    assert data["file"] == str(html_file.resolve())
    assert isinstance(data["started_at"], float)

    fresh_state.end_update()
    assert not record.exists()
    assert fresh_state.update_in_progress is False


def test_get_mtime_without_file(fresh_state: EditorState) -> None:
    """No current file → mtime is 0.0."""
    assert fresh_state.get_mtime() == 0.0


def test_get_mtime_missing_file(fresh_state: EditorState, tmp_path: Path) -> None:
    """A current file that does not exist → mtime is 0.0."""
    fresh_state.current_file = str(tmp_path / "nope.html")
    assert fresh_state.get_mtime() == 0.0


def test_get_mtime_existing_file(fresh_state: EditorState, html_file: Path) -> None:
    """An existing current file returns its real mtime."""
    fresh_state.set_file(str(html_file))
    assert fresh_state.get_mtime() == html_file.stat().st_mtime


# ----------------------------------------------------------------------
# Acceptance tests (SPEC-0009)
# ----------------------------------------------------------------------


def test_status_with_expiry(fresh_state: EditorState, clock: FakeClock, deck: Path) -> None:
    """SPEC-0009/E2E-005."""
    fresh_state.set_file(str(deck))
    ok, started = call_tool("update_start")
    assert ok
    assert started == {"ok": True, "expires_in": 120}

    clock.advance(30)
    ok, status = call_tool("get_status")
    assert ok
    assert status["update_in_progress"] is True
    assert status["update_expires_in"] == 90


def test_expiry(fresh_state: EditorState, clock: FakeClock, deck: Path) -> None:
    """SPEC-0009/E2E-020."""
    fresh_state.set_file(str(deck))
    call_tool("update_start")

    clock.advance(121)
    ok, status = call_tool("get_status")
    assert ok
    assert status["update_in_progress"] is False
    assert status["update_expires_in"] is None


def test_renewal(fresh_state: EditorState, clock: FakeClock, deck: Path) -> None:
    """SPEC-0009/E2E-021."""
    fresh_state.set_file(str(deck))
    call_tool("update_start")
    clock.advance(100)
    call_tool("update_start")

    clock.advance(50)
    ok, status = call_tool("get_status")
    assert ok
    assert status["update_in_progress"] is True
    assert status["update_expires_in"] == 70

    ok, ended = call_tool("update_end")
    assert ok
    assert ended == {"ok": True}
    ok, status = call_tool("get_status")
    assert ok
    assert (status["update_in_progress"], status["update_expires_in"]) == (False, None)


def test_no_state_file_next_to_the_users_file(served: Path) -> None:
    """SPEC-0009/E2E-024."""
    ok, _ = call_tool("update_start")
    assert ok
    assert sorted(p.name for p in served.parent.iterdir()) == ["deck.html"]


def test_state_shared_between_processes(served: Path) -> None:
    """SPEC-0009/E2E-025."""
    script = (
        "import asyncio\n"
        "from fastmcp import Client\n"
        "from mcp_htmleditor.mcp_server import mcp\n"
        "async def main():\n"
        "    async with Client(mcp) as client:\n"
        "        await client.call_tool('update_start', {})\n"
        "asyncio.run(main())\n"
    )
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, check=False, timeout=60
    )
    assert result.returncode == 0, result.stderr

    ok, status = call_tool("get_status")
    assert ok
    assert status["update_in_progress"] is True
    assert 1 <= status["update_expires_in"] <= 120


def test_status_endpoint_reports_expiry(served: Path) -> None:
    """GET /status carries update_expires_in, null while no update runs."""
    port = get_state().port
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=5) as response:
        payload = json.loads(response.read())
    assert payload["update_in_progress"] is False
    assert payload["update_expires_in"] is None


# ----------------------------------------------------------------------
# Unit tests: expiry arithmetic, in memory fallback, records
# ----------------------------------------------------------------------


def test_expiry_boundaries(fresh_state: EditorState, clock: FakeClock, html_file: Path) -> None:
    """ceil(120 - elapsed) stays in 1..120; at exactly 120 s the flag is cleared."""
    fresh_state.set_file(str(html_file))
    fresh_state.start_update()
    assert fresh_state.update_expires_in == 120
    clock.advance(0.5)
    assert fresh_state.update_expires_in == 120
    clock.advance(119.4)
    assert fresh_state.update_expires_in == 1
    clock.advance(0.1)
    assert fresh_state.update_expires_in is None
    assert fresh_state.update_in_progress is False


def test_negative_elapsed_is_clamped(fresh_state: EditorState, clock: FakeClock, html_file: Path) -> None:
    """A clock that goes backwards keeps the flag in progress with 120 s left, never more."""
    fresh_state.set_file(str(html_file))
    fresh_state.start_update()
    clock.advance(-500)
    assert fresh_state.update_in_progress is True
    assert fresh_state.update_expires_in == 120


def test_update_end_after_expiry(fresh_state: EditorState, clock: FakeClock, html_file: Path) -> None:
    """An expired record is ignored and update_end still succeeds."""
    fresh_state.set_file(str(html_file))
    fresh_state.start_update()
    clock.advance(200)
    assert (_file_dir(html_file) / "update.json").exists()
    fresh_state.end_update()
    assert fresh_state.update_in_progress is False


def test_unbound_flag_is_kept_in_memory(fresh_state: EditorState, clock: FakeClock) -> None:
    """No file of its own and no last.json: the flag lives in memory, nothing is written."""
    assert fresh_state.start_update() == 120
    clock.advance(10)
    assert fresh_state.update_expires_in == 110
    assert not config.state_dir().exists() or not any(config.state_dir().iterdir())
    fresh_state.end_update()
    assert fresh_state.update_in_progress is False


def test_set_update_flag_is_a_compat_wrapper(fresh_state: EditorState, html_file: Path) -> None:
    """set_update_flag(True) starts an update, False ends it (SPEC-0007 patch caller)."""
    fresh_state.set_file(str(html_file))
    fresh_state.set_update_flag(True)
    assert fresh_state.update_expires_in == 120
    fresh_state.set_update_flag(False)
    assert fresh_state.update_expires_in is None


def test_record_round_trip_and_last_json(fresh_state: EditorState, html_file: Path, tmp_path: Path) -> None:
    """set_file writes last.json; a process with no file resolves the file and server record from it."""
    fresh_state.set_file(str(html_file))
    fresh_state.port = 6001
    fresh_state.server_pid = 77
    fresh_state.save()
    assert json.loads((config.state_dir() / "last.json").read_text(encoding="utf-8")) == {
        "file": str(html_file.resolve())
    }

    EditorState._instance = None
    other = EditorState()
    assert other is not fresh_state
    snapshot = other.snapshot()
    assert snapshot["file"] == str(html_file.resolve())
    assert (snapshot["port"], snapshot["pid"]) == (6001, 77)
    other.start_update()
    assert fresh_state.update_in_progress is True


def test_flag_belongs_to_its_file(fresh_state: EditorState, html_file: Path, tmp_path: Path) -> None:
    """open_file to another file leaves the previous flag as it was."""
    second = tmp_path / "second.html"
    second.write_text("<html></html>", encoding="utf-8")
    fresh_state.set_file(str(html_file))
    fresh_state.start_update()
    fresh_state.set_file(str(second))
    assert fresh_state.update_in_progress is False
    assert (_file_dir(html_file) / "update.json").exists()
    fresh_state.set_file(str(html_file))
    assert fresh_state.update_in_progress is True


def test_corrupt_records_are_ignored(fresh_state: EditorState, html_file: Path) -> None:
    """Corrupt last.json and update.json read as absent."""
    fresh_state.set_file(str(html_file))
    fresh_state.start_update()
    (_file_dir(html_file) / "update.json").write_text("[]", encoding="utf-8")
    assert fresh_state.update_in_progress is False
    (config.state_dir() / "last.json").write_text("nope", encoding="utf-8")
    EditorState._instance = None
    assert EditorState().snapshot()["file"] is None


def test_state_dir_failure_is_not_fatal(
    fresh_state: EditorState, html_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-022: a state dir that cannot be created is logged; the flag falls back to memory."""
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("HTMLEDITOR_STATE_DIR", str(blocker / "state"))
    fresh_state.set_file(str(html_file))
    assert fresh_state.current_file == str(html_file.resolve())
    fresh_state.start_update()
    assert fresh_state.update_in_progress is True
    fresh_state.end_update()
    assert fresh_state.update_in_progress is False


def _fail_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(path: Path, record: dict[str, object]) -> None:
        raise OSError("read-only")

    monkeypatch.setattr("mcp_htmleditor.state._atomic_write_json", refuse)


def test_failed_renewal_wins_over_an_older_record(
    fresh_state: EditorState, clock: FakeClock, html_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A renewal that cannot write update.json still renews the flag in this process."""
    fresh_state.set_file(str(html_file))
    fresh_state.start_update()
    clock.advance(130)
    _fail_writes(monkeypatch)
    fresh_state.start_update()
    assert fresh_state.update_in_progress is True
    assert fresh_state.update_expires_in == 120


def test_failed_renewal_is_not_shortened_by_a_recent_record(
    fresh_state: EditorState, clock: FakeClock, html_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a 10 s old record, a failed renewal still runs the full 120 s."""
    fresh_state.set_file(str(html_file))
    fresh_state.start_update()
    clock.advance(10)
    _fail_writes(monkeypatch)
    fresh_state.start_update()
    clock.advance(115)
    assert fresh_state.update_expires_in == 5


def test_failed_removal_still_ends_the_flag_here(
    fresh_state: EditorState, clock: FakeClock, html_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """end_update ends the flag for this process even when update.json cannot be removed."""
    fresh_state.set_file(str(html_file))
    fresh_state.start_update()
    record = _file_dir(html_file) / "update.json"

    def refuse(self: Path, missing_ok: bool = False) -> None:
        raise OSError("busy")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", refuse)
        fresh_state.end_update()
    assert record.exists()
    assert fresh_state.update_in_progress is False
    clock.advance(1)
    record.write_text(json.dumps({"file": str(html_file), "started_at": clock.now}), encoding="utf-8")
    assert fresh_state.update_in_progress is True, "a later start by another process is still read"


def test_directories_are_private(fresh_state: EditorState, html_file: Path) -> None:
    """State directories are created with mode 0700."""
    fresh_state.set_file(str(html_file))
    for folder in (config.state_dir(), config.state_dir() / "files", _file_dir(html_file)):
        assert folder.stat().st_mode & 0o777 == 0o700


# ----------------------------------------------------------------------
# State directory resolution (DEC-005)
# ----------------------------------------------------------------------


def test_state_dir_override_wins(tmp_path: Path) -> None:
    settings = Settings(state_dir_override=tmp_path / "s", xdg_state_home_override=tmp_path / "x")
    assert settings.state_dir == tmp_path / "s"


def test_state_dir_uses_xdg_state_home(tmp_path: Path) -> None:
    settings = Settings(state_dir_override=None, xdg_state_home_override=tmp_path / "x")
    assert settings.state_dir == tmp_path / "x" / "mcp-htmleditor"


def test_state_dir_defaults_under_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/tester")))
    settings = Settings(state_dir_override=None, xdg_state_home_override=None)
    assert settings.state_dir == Path("/home/tester/.local/state/mcp-htmleditor")


def test_state_dir_without_home(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_home(cls: type[Path]) -> Path:
        raise RuntimeError("no home")

    monkeypatch.setattr(Path, "home", classmethod(no_home))
    settings = Settings(state_dir_override=None, xdg_state_home_override=None)
    assert settings.state_dir == Path(tempfile.gettempdir()) / f"mcp-htmleditor-{os.getuid()}"


def test_state_dir_env_names_are_significant() -> None:
    """DEC-005: both names key the memoization and are validated path fields."""
    assert {"HTMLEDITOR_STATE_DIR", "XDG_STATE_HOME"} <= set(config._SIGNIFICANT_ENV_VARS)
    assert {"state_dir_override", "xdg_state_home_override"} <= set(config._PATH_FIELDS)


def test_autouse_fixture_isolates_the_state_dir() -> None:
    """No test writes into the real ~/.local/state."""
    assert config.state_dir() != Path.home() / ".local" / "state" / "mcp-htmleditor"
