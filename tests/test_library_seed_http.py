"""US-0146: the initial content of a new library (SPEC-0025, DEC-036).

Spec tests: E2E-129, E2E-130, E2E-131, E2E-132, E2E-143, E2E-159. The decks are the two real conference files copied
into ``library-seed/``; the second channel is the stored bytes (sha256 and mtime), the tables and the activity count.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_htmleditor.config import reset_settings_cache
from mcp_htmleditor.library.seed import SeedError, seed_if_new
from tests import library_support
from tests.library_support import (
    ADMIN,
    BOB,
    CAROL,
    LAMYA,
    PNEUMO,
    WCBIP,
    FakeGoogle,
    RunningLibrary,
    signed_in,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

SEED = Path(__file__).resolve().parents[1] / "library-seed"
CHALLENGES = "From Challenges to Change"
BRIDGING = "Bridging the Gap"
DECKS = {
    CHALLENGES: ("85dd0f464c068eb8fb784627d1f2f4beeaabf7162f7381e334007cb8a15155dd", 3_901_499, "2026-11-15T19:57:19Z"),
    BRIDGING: ("011a91e9d03995fb0efe30d5f794f77706ba42c76d18d388f89b2ddb1a5e4eb2", 3_278_888, "2026-11-15T19:57:18Z"),
}
DENIED = "Access denied."


def stored_decks(running: RunningLibrary) -> dict[str, Path]:
    rows = running.stored.rows("SELECT id, folder_id, name FROM presentations")
    return {name: running.library_dir / "files" / folder / f"{pid}.html" for pid, folder, name in rows}


def iso(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def seeded(library_server: START, fake_google: FakeGoogle) -> RunningLibrary:
    return library_server(fake_google, seed=True)


def test_the_first_start_creates_the_folder_the_two_decks_unchanged_and_the_member(seeded: RunningLibrary) -> None:
    """The independent test: the stored files hash to the supplied decks, their mtimes read back as 19:57:19 and
    19:57:18, the activity table is empty, Lamya is the one member (RW) and no one is an administrator by it."""
    decks = stored_decks(seeded)

    assert set(decks) == {CHALLENGES, BRIDGING}
    for name, (digest, size, modified) in DECKS.items():
        assert hashlib.sha256(decks[name].read_bytes()).hexdigest() == digest
        assert decks[name].stat().st_size == size
        assert iso(decks[name]) == modified
    assert seeded.stored.folder_names() == [WCBIP]
    assert [(row[1], row[2]) for row in seeded.stored.members()] == [(LAMYA, "RW")]
    assert seeded.stored.activity() == []
    assert seeded.stored.rows("SELECT key FROM meta WHERE key = 'seeded'") == [("seeded",)]


def test_a_restart_adds_and_resets_nothing(seeded: RunningLibrary) -> None:
    before = {name: path.read_bytes() for name, path in stored_decks(seeded).items()}
    stored_decks(seeded)[BRIDGING].write_bytes(b"changed by Lamya")

    seeded.restart()

    after = stored_decks(seeded)
    assert set(after) == {CHALLENGES, BRIDGING}
    assert after[BRIDGING].read_bytes() == b"changed by Lamya"
    assert after[CHALLENGES].read_bytes() == before[CHALLENGES]
    assert seeded.stored.folder_names() == [WCBIP]


def test_e2e_131_a_restart_does_not_reset_or_recreate_the_initial_content(
    seeded: RunningLibrary, fake_google: FakeGoogle
) -> None:
    lamya = signed_in(seeded, fake_google, LAMYA)
    folder = seeded.stored.rows("SELECT id FROM folders")[0][0]
    bridging = stored_decks(seeded)[BRIDGING].stem
    lamya.open_presentation(bridging)
    admin = signed_in(seeded, fake_google, ADMIN)
    assert lamya.delete_presentation(bridging).status == 200
    challenges = stored_decks(seeded)[CHALLENGES]
    changed = challenges.read_text(encoding="utf-8").replace(CHALLENGES, "Changed title", 1)
    challenges.write_text(changed, encoding="utf-8")

    seeded.restart()

    names = [html.unescape(row[0]) for row in lamya.open(f"{seeded.origin}/f/{folder}").presentation_rows()]
    assert names == [CHALLENGES]
    assert "Changed title" in challenges.read_text(encoding="utf-8")
    lines = [row[2] for row in admin.open("/admin").activity_lines()]
    assert lines == [f'Deleted "{BRIDGING}" from "{WCBIP}"']


def test_e2e_129_other_accounts_see_nothing_of_the_initial_content(
    seeded: RunningLibrary, fake_google: FakeGoogle
) -> None:
    bridging = stored_decks(seeded)[BRIDGING].stem
    bob = signed_in(seeded, fake_google, BOB)
    seeded.builder.member(seeded.builder.folder("Cardiology 2027"), CAROL, "RO")
    carol = signed_in(seeded, fake_google, CAROL)

    home = bob.open("/")
    link = carol.open(f"{seeded.origin}/open/{bridging}")

    for reply in (home, link):
        assert reply.status == 403
        assert DENIED in reply.text
        assert CHALLENGES not in reply.text
        assert BRIDGING not in reply.text
        assert WCBIP not in reply.text


def test_e2e_130_the_seeded_member_is_not_an_administrator(seeded: RunningLibrary, fake_google: FakeGoogle) -> None:
    lamya = signed_in(seeded, fake_google, LAMYA)

    reply = lamya.open("/admin")

    assert reply.status == 403
    assert DENIED in reply.text
    assert "Administration" not in lamya.open("/").text


def test_e2e_132_the_seeded_decks_are_unchanged_and_pass_the_upload_checks(
    seeded: RunningLibrary, fake_google: FakeGoogle
) -> None:
    lamya = signed_in(seeded, fake_google, LAMYA)
    decks = stored_decks(seeded)
    supplied = {CHALLENGES: (SEED / "from-challenges-to-change.html"), BRIDGING: SEED / "bridging-the-gap.html"}
    admin = signed_in(seeded, fake_google, ADMIN)
    pneumo = seeded.builder.folder(PNEUMO)
    downloads = {}
    for name, path in decks.items():
        lamya.open_presentation(path.stem)
        downloads[name] = lamya.deck(path.stem, "download", x_editor="1")

    for name, source in supplied.items():
        assert downloads[name].status == 200
        assert downloads[name].body == source.read_bytes()
        reply = admin.upload(pneumo, f"{name}.html", source.read_bytes())
        assert reply.status == 201, reply.text
        assert reply.json()["message"] == f"Uploaded {name}."
    assert {len(downloads[CHALLENGES].body), len(downloads[BRIDGING].body)} == {3_901_499, 3_278_888}


def test_e2e_143_an_empty_activity_list_says_so(seeded: RunningLibrary, fake_google: FakeGoogle) -> None:
    admin = signed_in(seeded, fake_google, ADMIN)
    page = admin.open("/admin")
    assert "No activity yet." in page.text
    assert page.activity_lines() == []


def test_e2e_159_a_library_whose_every_folder_was_deleted_is_not_seeded_again(
    seeded: RunningLibrary, fake_google: FakeGoogle
) -> None:
    admin = signed_in(seeded, fake_google, ADMIN)
    folder = seeded.stored.rows("SELECT id FROM folders")[0][0]
    assert admin.post_json(f"/api/folders/{folder}/delete", {"confirm": WCBIP}).status == 200

    seeded.restart()

    assert seeded.stored.folder_names() == []
    assert "You have no access to any folder yet." in signed_in(seeded, fake_google, ADMIN).open("/").text
    lamya = signed_in(seeded, fake_google, LAMYA).open("/")
    assert lamya.status == 403
    assert DENIED in lamya.text


def test_a_corrupted_seed_file_creates_nothing_and_a_later_start_retries(
    library_server: START, fake_google: FakeGoogle, tmp_path: Path
) -> None:
    broken = tmp_path / "seed"
    shutil.copytree(SEED, broken)
    (broken / "bridging-the-gap.html").write_bytes(b"corrupted")
    running = library_server(fake_google, seed=False, library_seed_dir_override=broken)

    with pytest.raises(SeedError):
        seed_if_new(running.server.library, broken, running.clock)

    assert running.stored.folder_names() == []
    assert not [entry for entry in running.stored.entries() if entry.endswith(".html")]
    assert running.stored.rows("SELECT key FROM meta WHERE key = 'seeded'") == []
    shutil.copyfile(SEED / "bridging-the-gap.html", broken / "bridging-the-gap.html")
    assert seed_if_new(running.server.library, broken, running.clock) is True
    assert seed_if_new(running.server.library, broken, running.clock) is False
    assert running.stored.folder_names() == [WCBIP]


def test_a_missing_manifest_or_file_is_a_seed_error_that_creates_nothing(
    library_server: START, fake_google: FakeGoogle, tmp_path: Path
) -> None:
    running = library_server(fake_google, seed=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    partial = tmp_path / "partial"
    shutil.copytree(SEED, partial)
    (partial / "from-challenges-to-change.html").unlink()

    for directory in (empty, partial):
        with pytest.raises(SeedError):
            seed_if_new(running.server.library, directory, running.clock)

    assert running.stored.folder_names() == []
    assert not [entry for entry in running.stored.entries() if entry.endswith(".html")]


def test_the_seed_directory_resolves_to_the_repository_one(seeded: RunningLibrary) -> None:
    reset_settings_cache()
    assert seeded.settings.library_seed_dir == SEED
