"""SPEC-0009 US-0050: history snapshots before overwrites and the ``history`` / ``restore`` commands.

HTTP tests drive a real editor server (``served_deck``); CLI tests use ``CliRunner`` in the deck's folder;
unit tests cover ``HistoryStore`` and ``atomic_write`` with a reason. Ids come from ``FakeClock``.
"""

from __future__ import annotations

import errno
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result
from playwright.sync_api import Page, expect

from mcp_htmleditor import cli as cli_module
from mcp_htmleditor import fileio
from mcp_htmleditor.cli import main
from mcp_htmleditor.fileio import WriteError, atomic_write
from mcp_htmleditor.history import HISTORY_LIMIT, HistoryError, HistoryStore, default_store
from mcp_htmleditor.state import get_state
from tests.conftest import ServedDeck, needs_chromium
from tests.test_save_ui_e2e import (  # noqa: F401 - fast_poll is a fixture used by name
    AGENT_TITLE,
    WAIT_MS,
    _show_conflict,
    fast_poll,
)
from tests.test_state import T0, FakeClock

LINE = re.compile(r"^(\d{8}T\d{6}Z(?:-\d+)?)  (\d+) bytes  ([a-z-]+)$")
SMALL = "<html><head></head><body><p>x</p></body></html>"


@pytest.fixture(autouse=True)
def no_global_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI group would install the process wide tracer, which tests/test_tracing.py owns."""
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)


@pytest.fixture
def clock(served_deck: ServedDeck, monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """A fake clock driving the history ids, one second moved after each ``_save``."""
    fake = FakeClock(T0)
    monkeypatch.setattr(get_state(), "clock", fake)
    monkeypatch.chdir(served_deck.path.parent)
    return fake


def _save(deck: ServedDeck, clock: FakeClock, label: str) -> None:
    """A browser save of the deck with ``label`` in its title, then one second later."""
    html = deck.path.read_text(encoding="utf-8").replace("<title>", f"<title>{label} ", 1)
    reply = deck.save({"html": html, "base_mtime": deck.status()["mtime"]})
    assert reply.status == 200
    clock.advance(1)


def _run(*args: str) -> Result:
    return CliRunner().invoke(main, list(args))


def _history(file: str = "deck.html") -> list[tuple[str, int, str]]:
    result = _run("history", file)
    assert result.exit_code == 0
    rows = []
    for line in result.output.splitlines():
        found = LINE.match(line)
        assert found, line
        rows.append((found.group(1), int(found.group(2)), found.group(3)))
    return rows


# --- E2E ---------------------------------------------------------------------


def test_e2e_003_history_after_two_saves(served_deck: ServedDeck, clock: FakeClock) -> None:
    """E2E-003."""
    original = served_deck.path.stat().st_size
    _save(served_deck, clock, "un")
    _save(served_deck, clock, "deux")
    rows = _history()
    assert [row[2] for row in rows] == ["browser-save", "browser-save"]
    assert rows[0][0] > rows[1][0]
    assert rows[1][1] == original


def test_e2e_004_restore(served_deck: ServedDeck, clock: FakeClock) -> None:
    """E2E-004."""
    first = served_deck.path.read_bytes()
    _save(served_deck, clock, "un")
    _save(served_deck, clock, "deux")
    saved_copy = served_deck.path.read_bytes()
    oldest = _history()[1][0]
    result = _run("restore", "deck.html", oldest)
    assert (result.exit_code, result.output) == (0, f"Restored deck.html to {oldest}\n")
    assert served_deck.path.read_bytes() == first
    top = _history()[0]
    assert (top[2], top[1]) == ("restore", len(saved_copy))


def test_restore_same_content_changes_nothing(served_deck: ServedDeck, clock: FakeClock) -> None:
    """Restoring content equal to the current file adds no version and still reports success."""
    _save(served_deck, clock, "un")
    _save(served_deck, clock, "deux")
    newest = _history()[0][0]
    # the newest version is the content before the second save: restore it, then restore it again
    assert _run("restore", "deck.html", newest).exit_code == 0
    before = _history()
    again = _run("restore", "deck.html", newest)
    assert (again.exit_code, again.output) == (0, f"Restored deck.html to {newest}\n")
    assert _history() == before


@needs_chromium
@pytest.mark.usefixtures("fast_poll")
def test_e2e_009_keep_mine(page: Page, served_deck: ServedDeck, clock: FakeClock) -> None:
    """E2E-009."""
    _show_conflict(page, served_deck)
    page.locator("#save-conflict").get_by_role("button", name="Keep mine").click()
    expect(page.locator("#save-conflict")).to_be_hidden(timeout=WAIT_MS)
    assert "CouvertureX" in served_deck.path.read_text(encoding="utf-8")
    rows = _history()
    assert rows[0][2] == "keep-mine"
    assert AGENT_TITLE.encode() in default_store().read(served_deck.path, rows[0][0])


def test_e2e_015_unknown_id(served_deck: ServedDeck, clock: FakeClock) -> None:
    """E2E-015."""
    _save(served_deck, clock, "un")
    _save(served_deck, clock, "deux")
    ids = [row[0] for row in _history()]
    before = served_deck.path.read_bytes()
    result = _run("restore", "deck.html", "nope")
    assert result.exit_code == 1
    assert result.stderr == f'error: Unknown history id "nope". Valid ids: {ids[0]}, {ids[1]}\n'
    assert served_deck.path.read_bytes() == before


def test_e2e_016_no_history(served_deck: ServedDeck, clock: FakeClock) -> None:
    """E2E-016."""
    result = _run("history", "deck.html")
    assert (result.exit_code, result.output) == (0, "No history for deck.html\n")
    bad = _run("restore", "deck.html", "x")
    assert (bad.exit_code, bad.stderr) == (1, 'error: Unknown history id "x". Valid ids: none\n')


def test_e2e_019_missing_file_and_template(served_deck: ServedDeck, clock: FakeClock) -> None:
    """E2E-019."""
    for args in (("history", "ghost.html"), ("restore", "ghost.html", "x")):
        result = _run(*args)
        assert (result.exit_code, result.stderr) == (1, "error: File not found: ghost.html\n")
    template = _run("restore", "templates/bootstrap/x.html", "y")
    assert template.exit_code == 1
    assert template.stderr == "error: Refusing to modify a template: templates/bootstrap/x.html\n"


def test_history_on_existing_template_is_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``history`` only checks that the file exists, even for a template path."""
    folder = tmp_path / "templates" / "bootstrap"
    folder.mkdir(parents=True)
    (folder / "x.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = _run("history", "templates/bootstrap/x.html")
    assert (result.exit_code, result.output) == (0, "No history for templates/bootstrap/x.html\n")


def test_e2e_022_twenty_versions(served_deck: ServedDeck, clock: FakeClock) -> None:
    """E2E-022."""
    original = served_deck.path.read_bytes()
    for number in range(HISTORY_LIMIT + 1):
        _save(served_deck, clock, f"v{number}")
    rows = _history()
    assert len(rows) == HISTORY_LIMIT
    store = default_store()
    assert all(store.read(served_deck.path, row[0]) != original for row in rows)


def test_e2e_023_identical_save(served_deck: ServedDeck, clock: FakeClock) -> None:
    """E2E-023."""
    assert served_deck.save({"html": SMALL}).status == 200
    count = len(_history())
    on_disk = served_deck.path.read_text(encoding="utf-8")
    mtime = served_deck.path.stat().st_mtime
    reply = served_deck.save({"html": on_disk, "base_mtime": mtime})
    assert (reply.status, reply.body) == (200, {"ok": True, "mtime": mtime})
    assert len(_history()) == count


def test_e2e_031_failed_write_keeps_history(
    served_deck: ServedDeck, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E-031."""
    _save(served_deck, clock, "un")
    _save(served_deck, clock, "deux")
    before = _history()

    def failing(source: str, destination: str) -> None:
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(fileio, "replace_file", failing)
    html = served_deck.path.read_text(encoding="utf-8").replace("<title>", "<title>trois ", 1)
    reply = served_deck.save({"html": html})
    assert reply.status == 500
    assert _history() == before


def test_restore_write_failure_reports_the_os_message(
    served_deck: ServedDeck, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed restore write: ``error: <message>``, status 1, file and history unchanged."""
    _save(served_deck, clock, "un")
    before, content = _history(), served_deck.path.read_bytes()

    def failing(source: str, destination: str) -> None:
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(fileio, "replace_file", failing)
    result = _run("restore", "deck.html", before[0][0])
    assert (result.exit_code, result.stderr) == (1, "error: Permission denied\n")
    assert served_deck.path.read_bytes() == content
    assert _history() == before


def test_browser_save_reasons(served_deck: ServedDeck, clock: FakeClock) -> None:
    """A forced save is recorded ``keep-mine``, any other ``browser-save``."""
    _save(served_deck, clock, "un")
    html = served_deck.path.read_text(encoding="utf-8").replace("<title>", "<title>deux ", 1)
    assert served_deck.save({"html": html, "base_mtime": 1.0, "force": True}).status == 200
    assert [row[2] for row in _history()] == ["keep-mine", "browser-save"]


# --- unit: HistoryStore --------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / "state", FakeClock(T0))


def test_ids_take_a_decimal_suffix_and_order_numerically(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    staged = [store.stage(target, f"c{n}".encode(), "patch") for n in range(21)]
    base = "20231114T221320Z"
    assert [version.id for version in staged] == [base] + [f"{base}-{n}" for n in range(2, 22)]
    listed = [version.id for version in store.list_versions(target)]
    assert listed == [version.id for version in reversed(staged)]
    assert listed.index(f"{base}-10") < listed.index(f"{base}-9")


def test_version_fields_and_read(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    version = store.stage(target, "é".encode(), "browser-save")
    assert (version.bytes, version.reason) == (2, "browser-save")
    assert store.read(target, version.id) == "é".encode()
    with pytest.raises(HistoryError, match=f'Unknown history id "x". Valid ids: {version.id}'):
        store.read(target, "x")


def test_prune_drops_the_oldest_beyond_the_cap(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    staged = [store.stage(target, b"x", "restore") for _ in range(HISTORY_LIMIT + 3)]
    store.prune(target)
    assert [v.id for v in store.list_versions(target)] == [v.id for v in reversed(staged[3:])]


def test_discard_and_hidden_files_are_ignored(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    keep, drop = store.stage(target, b"a", "patch"), store.stage(target, b"b", "patch")
    (store.list_dir(target) / ".stray.tmp").write_bytes(b"zz")
    store.discard(target, drop)
    store.discard(target, drop)  # already gone: no error
    assert store.list_versions(target) == [keep]
    assert store.list_versions(tmp_path / "other.html") == []


# --- unit: atomic_write with a reason --------------------------------------------


def test_atomic_write_without_reason_keeps_no_snapshot(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    target.write_bytes(b"old")
    assert atomic_write(target, b"new", history=store) is True
    assert store.list_versions(target) == []


def test_atomic_write_snapshots_the_previous_content(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    target.write_bytes(b"old")
    assert atomic_write(target, b"new", reason="patch", history=store) is True
    [version] = store.list_versions(target)
    assert (version.reason, store.read(target, version.id)) == ("patch", b"old")


def test_atomic_write_equal_bytes_keeps_nothing(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    target.write_bytes(b"same")
    assert atomic_write(target, b"same", reason="patch", history=store) is False
    assert store.list_versions(target) == []


def test_atomic_write_new_file_has_nothing_to_keep(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    assert atomic_write(target, b"first", reason="patch", history=store) is True
    assert store.list_versions(target) == []


def test_failed_replace_discards_the_staged_version(
    store: HistoryStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "f.html"
    target.write_bytes(b"old")
    for _ in range(HISTORY_LIMIT):
        store.stage(target, b"x", "patch")
    before = store.list_versions(target)

    def failing(source: str, destination: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(fileio, "replace_file", failing)
    with pytest.raises(WriteError, match="No space left on device"):
        atomic_write(target, b"new", reason="patch", history=store)
    assert store.list_versions(target) == before
    assert sorted(p.name for p in store.list_dir(target).iterdir() if p.name.startswith(".")) == []
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in tmp_path.iterdir() if p.name != "state") == ["f.html"]


def test_state_directory_failure_surfaces_as_500(
    served_deck: ServedDeck, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-022: an unusable history folder fails the save, the file stays as it was."""
    before = served_deck.path.read_bytes()

    def broken(self: HistoryStore, path: Path, content: bytes, reason: str) -> Any:
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(HistoryStore, "stage", broken)
    html = before.decode().replace("<title>", "<title>x ", 1)
    reply = served_deck.save({"html": html})
    assert (reply.status, reply.body) == (500, {"error": "Permission denied"})
    assert served_deck.path.read_bytes() == before


def _stale(store: HistoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "list_versions", lambda path: [])


def _files(store: HistoryStore, target: Path) -> list[str]:
    return sorted(entry.name for entry in store.list_dir(target).iterdir())


def test_stale_listing_same_reason_keeps_both_versions(
    store: HistoryStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "f.html"
    first = store.stage(target, b"AAA", "patch")
    _stale(store, monkeypatch)
    second = store.stage(target, b"BBB", "patch")
    assert first.id != second.id
    monkeypatch.undo()
    assert store.read(target, first.id) == b"AAA"
    assert store.read(target, second.id) == b"BBB"


def test_stale_listing_other_reason_gets_another_id(
    store: HistoryStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "f.html"
    first = store.stage(target, b"AAA", "patch")
    _stale(store, monkeypatch)
    second = store.stage(target, b"BBB", "restore")
    assert first.id != second.id
    monkeypatch.undo()
    ids = [version.id for version in store.list_versions(target)]
    assert sorted(ids) == sorted({first.id, second.id})
    assert store.read(target, second.id) == b"BBB"


def test_no_temporary_file_remains(store: HistoryStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "f.html"
    store.stage(target, b"AAA", "patch")
    _stale(store, monkeypatch)
    store.stage(target, b"BBB", "patch")
    assert [name for name in _files(store, target) if name.endswith(".tmp")] == []


def test_stage_falls_back_when_hard_links_are_unsupported(
    store: HistoryStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "f.html"

    def no_link(*args: Any, **kwargs: Any) -> None:
        raise OSError(errno.EPERM, "no links")

    monkeypatch.setattr("mcp_htmleditor.history.os.link", no_link)
    first = store.stage(target, b"AAA", "patch")
    _stale(store, monkeypatch)
    second = store.stage(target, b"BBB", "patch")
    assert first.id != second.id
    monkeypatch.undo()
    assert store.read(target, first.id) == b"AAA"
    assert store.read(target, second.id) == b"BBB"
    assert [name for name in _files(store, target) if name.endswith(".tmp")] == []


def test_concurrent_threads_get_distinct_ids(store: HistoryStore, tmp_path: Path) -> None:
    target = tmp_path / "f.html"
    with ThreadPoolExecutor(max_workers=8) as pool:
        versions = list(pool.map(lambda n: store.stage(target, f"c{n}".encode(), "patch"), range(16)))
    assert len({version.id for version in versions}) == 16
    for number, version in enumerate(versions):
        assert store.read(target, version.id) == f"c{number}".encode()
