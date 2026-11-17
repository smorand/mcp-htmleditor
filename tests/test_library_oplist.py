"""US-0147: ``library-list`` gives an operator the stored file of every presentation (SPEC-0025, DEC-051).

The independent test: after the builder creates two folders and three presentations, the command prints one tab
separated line per presentation and the path of the first line given to ``list_versions`` returns the versions written
by a save through the library. The command is read only: the database and every file keep their modified time.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mcp_htmleditor.config import reset_settings_cache
from mcp_htmleditor.history import list_versions
from tests import library_support
from tests.deck_support import run_cli
from tests.library_support import CARDIOLOGY, DAN, HEART_FAILURE, PNEUMO, STATINS, FakeGoogle, RunningLibrary, signed_in

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
EXTRA = "Spirometry Basics"


@pytest.fixture
def library(library_server: START, fake_google: FakeGoogle, monkeypatch: pytest.MonkeyPatch) -> RunningLibrary:
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.presentation(ids[CARDIOLOGY], HEART_FAILURE, size=4_096, modified=MODIFIED)
    running.builder.presentation(ids[CARDIOLOGY], STATINS, size=8_192, modified=MODIFIED)
    running.builder.presentation(ids[PNEUMO], EXTRA, size=2_048, modified=MODIFIED)
    monkeypatch.setenv("HTMLEDITOR_LIBRARY_DIR", str(running.library_dir))
    reset_settings_cache()
    return running


def list_library() -> tuple[int, str]:
    """``(exit code, output)`` of the command, the standard output and the error stream together."""
    out, err, code = run_cli("library-list")
    return code, out + err


def test_it_prints_one_tab_separated_line_per_presentation_with_an_existing_path(library: RunningLibrary) -> None:
    code, output = list_library()

    assert code == 0
    lines = output.splitlines()
    assert len(lines) == 3
    rows = [line.split("\t") for line in lines]
    assert all(len(row) == 4 for row in rows)
    assert [(row[0], row[1]) for row in rows] == sorted((row[0], row[1]) for row in rows)  # folder, then name
    assert {(row[0], row[1]) for row in rows} == {
        (CARDIOLOGY, HEART_FAILURE),
        (CARDIOLOGY, STATINS),
        (PNEUMO, EXTRA),
    }
    for _folder, _name, path, size in rows:
        assert Path(path).is_file()
        assert Path(path).stat().st_size == int(size)


def test_the_path_of_a_line_is_the_file_whose_history_a_save_wrote(
    library: RunningLibrary, fake_google: FakeGoogle
) -> None:
    code, output = list_library()
    assert code == 0
    first = next(line.split("\t") for line in output.splitlines() if line.split("\t")[1] == HEART_FAILURE)
    presentation_id = Path(first[2]).stem
    dan = signed_in(library, fake_google, DAN)
    dan.open_presentation(presentation_id)
    document = Path(first[2]).read_text(encoding="utf-8").replace(HEART_FAILURE, "Changed title", 1)

    assert dan.save(presentation_id, document).status == 200

    _target, versions = list_versions(first[2])
    assert len(versions) == 1
    assert versions[0].bytes == 4_096


def test_an_empty_library_directory_is_an_error_naming_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "nothing-here"
    empty.mkdir()
    monkeypatch.setenv("HTMLEDITOR_LIBRARY_DIR", str(empty))
    reset_settings_cache()

    code, output = list_library()

    assert code == 1
    assert f"No library at {empty / 'library.db'}" in output
    assert not (empty / "library.db").exists()  # the command never creates a library


def test_a_library_with_no_presentation_prints_nothing_and_succeeds(
    library_server: START, fake_google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = library_server(fake_google)
    running.builder.standard()
    monkeypatch.setenv("HTMLEDITOR_LIBRARY_DIR", str(running.library_dir))
    reset_settings_cache()

    assert list_library() == (0, "")


def test_the_command_is_read_only(library: RunningLibrary) -> None:
    watched = [library.library_dir / "library.db", *(p for p in library.library_dir.rglob("*") if p.is_file())]
    before = {path: path.stat().st_mtime_ns for path in watched}
    entries = sorted(library.library_dir.rglob("*"))

    code, _output = list_library()

    assert code == 0
    assert {path: path.stat().st_mtime_ns for path in watched} == before
    assert sorted(library.library_dir.rglob("*")) == entries
    assert os.access(library.library_dir / "library.db", os.R_OK)


def test_a_stopped_library_is_read_without_creating_any_file(library: RunningLibrary) -> None:
    """With no server the WAL sidecar files are gone; a read only open must not bring them back."""
    library.server.stop()
    library.database.release()
    entries = sorted(library.library_dir.rglob("*"))
    assert not [entry for entry in entries if entry.name.endswith(("-wal", "-shm"))]

    code, output = list_library()

    assert code == 0
    assert len(output.splitlines()) == 3
    assert sorted(library.library_dir.rglob("*")) == entries
