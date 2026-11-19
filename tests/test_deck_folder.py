"""SPEC-0026 (US-0150): the folder rule shared by the exports and the render."""

from __future__ import annotations

from pathlib import Path

from mcp_htmleditor.deck_folder import OUTSIDE_PREFIX, is_inside, outside_warning, url_to_path


def test_is_inside_accepts_the_folder_and_below(tmp_path: Path) -> None:
    assert is_inside(tmp_path, tmp_path / "a.png")
    assert is_inside(tmp_path, tmp_path / "media" / "a.png")
    assert is_inside(tmp_path, tmp_path / "media" / ".." / "a.png")


def test_is_inside_refuses_a_climb_an_absolute_path_and_a_missing_outside_file(tmp_path: Path) -> None:
    folder = tmp_path / "deck"
    folder.mkdir()
    assert not is_inside(folder, folder / ".." / "secret.png")
    assert not is_inside(folder, tmp_path / "secret.png")
    assert not is_inside(folder, Path("/etc/hosts"))


def test_is_inside_follows_symlinks(tmp_path: Path) -> None:
    folder = tmp_path / "deck"
    (folder / "real").mkdir(parents=True)
    (folder / "real" / "a.png").write_bytes(b"x")
    (tmp_path / "secret.png").write_bytes(b"x")
    (folder / "inner.png").symlink_to(folder / "real" / "a.png")
    (folder / "leak.png").symlink_to(tmp_path / "secret.png")
    assert is_inside(folder, folder / "inner.png")
    assert not is_inside(folder, folder / "leak.png")


def test_url_to_path_reads_file_urls_only(tmp_path: Path) -> None:
    assert url_to_path((tmp_path / "a b.png").as_uri()) == tmp_path / "a b.png"
    assert url_to_path("https://x.test/a.png") is None
    assert url_to_path("data:image/png;base64,AAAA") is None


def test_outside_warning_cuts_the_address_at_60_characters() -> None:
    assert outside_warning("../a.png") == f"{OUTSIDE_PREFIX}../a.png"
    assert outside_warning("x" * 90) == OUTSIDE_PREFIX + "x" * 60
    assert OUTSIDE_PREFIX == "Image hors du dossier du deck, ignoree: "
