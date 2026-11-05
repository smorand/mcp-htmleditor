"""US-0061: render the first slide to a picture (SPEC-0008 E2E-001, E2E-022 and the checks before the browser)."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mcp_htmleditor.render import files
from tests import render_support as rs
from tests.deck_support import BOOTSTRAP, doc_perso, write_deck
from tests.deck_support import run_cli as _run_cli

NEEDS_CHROMIUM = rs.needs_chromium
INSTALL_MESSAGE = "Rendering needs Chromium. Install it with: make install-browser"
ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread: the e2e suite can leave an event loop alive in the caller's, and the
    Playwright sync API refuses to start inside one (the command itself runs in a plain process)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    """Redirect the system temporary directory so pictures land under ``tmp_path``."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path / "htmleditor-render"


@pytest.fixture
def ei_file(tmp_path):
    return write_deck(tmp_path / "DECK-EI.html", rs.ei_deck_html())


@NEEDS_CHROMIUM
def test_default_render_prints_one_line_and_writes_a_480x270_png(ei_file, out_dir):
    stdout, stderr, status = run_cli("render", ei_file)
    picture = out_dir / "DECK-EI-slide-0.png"
    assert (stdout, stderr, status) == (f"Rendered slide-0 to {picture} (480x270)\n", "", 0)
    assert stdout.split(" to ")[1].split(" (")[0].endswith("htmleditor-render/DECK-EI-slide-0.png")
    assert rs.png_size(picture) == (480, 270)


@NEEDS_CHROMIUM
def test_path_with_spaces_and_accents(tmp_path, out_dir):
    file = write_deck(tmp_path / "Présentation été.html", rs.ei_deck_html())
    stdout, _, status = run_cli("render", file)
    assert status == 0
    assert stdout == f"Rendered slide-0 to {out_dir / 'Présentation été-slide-0.png'} (480x270)\n"
    assert (out_dir / "Présentation été-slide-0.png").is_file()


@NEEDS_CHROMIUM
def test_render_leaves_the_file_untouched(ei_file, out_dir):
    os.utime(ei_file, (1_000_000_000, 1_000_000_000))
    before = (Path(ei_file).read_bytes(), Path(ei_file).stat().st_mtime_ns)
    assert run_cli("render", ei_file)[2] == 0
    assert (Path(ei_file).read_bytes(), Path(ei_file).stat().st_mtime_ns) == before


@NEEDS_CHROMIUM
def test_stale_pictures_of_the_deck_are_removed_after_success(ei_file, out_dir):
    out_dir.mkdir()
    for name in ("DECK-EI-slide-5.png", "DECK-EI-slide-7.png", "other-slide-1.png", "DECK-EI-extra.png"):
        (out_dir / name).write_bytes(b"x")
    assert run_cli("render", ei_file)[2] == 0
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "DECK-EI-extra.png",
        "DECK-EI-slide-0.png",
        "other-slide-1.png",
    ]


@NEEDS_CHROMIUM
def test_picture_is_written_through_atomic_write(ei_file, out_dir, monkeypatch):
    calls: list[tuple[Path, bytes]] = []

    def record(path: Path, data: bytes, **_: object) -> bool:
        calls.append((Path(path), data))
        return True

    monkeypatch.setattr(files, "atomic_write", record)
    assert run_cli("render", ei_file)[2] == 0
    assert [c[0] for c in calls] == [out_dir / "DECK-EI-slide-0.png"]
    assert calls[0][1].startswith(b"\x89PNG")


def test_write_picture_creates_the_directory_and_uses_atomic_write(out_dir, monkeypatch):
    calls: list[tuple[Path, bytes]] = []
    monkeypatch.setattr(files, "atomic_write", lambda path, data, **_: calls.append((Path(path), data)))
    target = out_dir / "deck-slide-0.png"
    files.write_picture(target, b"png")
    assert out_dir.is_dir()
    assert calls == [(target, b"png")]


def test_missing_file(tmp_path, out_dir):
    stdout, stderr, status = run_cli("render", "ghost.html")
    assert (stdout, stderr, status) == ("", "error: File not found: ghost.html\n", 1)


def _not_presentations(tmp_path):
    article_only = rs.ei_deck_html().replace('data-type="slide"', "")
    return {
        "DOC-PERSO": doc_perso(),
        "mail": (BOOTSTRAP / "mail-empty.html").read_text(encoding="utf-8"),
        "website": (BOOTSTRAP / "website-empty.html").read_text(encoding="utf-8"),
        "article-only": article_only,
    }


@pytest.mark.parametrize("kind", ["DOC-PERSO", "mail", "website", "article-only"])
def test_not_a_presentation(kind, tmp_path, out_dir):
    file = write_deck(tmp_path / f"{kind}.html", _not_presentations(tmp_path)[kind])
    stdout, stderr, status = run_cli("render", file)
    assert (stdout, stderr, status) == ("", f"error: render needs a presentation: {file}\n", 1)


def test_article_only_presentation_declares_the_type():
    html = _not_presentations(None)["article-only"]
    assert 'data-doc-type="presentation"' in html
    assert 'class="slide' in html


def test_picture_path_replaces_separators_and_keeps_the_stem(out_dir):
    path = files.picture_path("deck.html", "a/b\\c\x00d")
    assert path.name == "deck-a_b_c_d.png"
    assert path.parent.name == "htmleditor-render"
    assert files.picture_path("a/[x]*é.html", "s").name == "[x]*é-s.png"


def test_render_dir_is_under_the_system_temporary_directory(out_dir, tmp_path):
    assert files.render_dir() == tmp_path / "htmleditor-render"


def test_remove_stale(out_dir):
    out_dir.mkdir()
    for name in ("deck-slide-1.png", "deck-slide-2.png", "deck-slide-3.png", "other-slide-1.png", "deck-extra.png"):
        (out_dir / name).write_bytes(b"x")
    keep = out_dir / "deck-slide-3.png"
    removed = files.remove_stale("deck.html", ["slide-1", "slide-2", "slide-3"], keep)
    assert removed == 2
    assert sorted(p.name for p in out_dir.iterdir()) == ["deck-extra.png", "deck-slide-3.png", "other-slide-1.png"]


def test_remove_stale_ignores_an_unlink_failure(out_dir, monkeypatch, caplog):
    out_dir.mkdir()
    (out_dir / "deck-slide-1.png").write_bytes(b"x")
    keep = out_dir / "deck-slide-3.png"

    def fail(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "unlink", fail)
    with caplog.at_level("WARNING"):
        assert files.remove_stale("deck.html", ["slide-1"], keep) == 0
    assert "could not remove" in caplog.text


def test_browser_missing_gives_the_install_message_and_deletes_nothing(ei_file, out_dir, tmp_path, monkeypatch):
    empty = tmp_path / "no-browsers"
    empty.mkdir()
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(empty))
    out_dir.mkdir()
    stale = out_dir / "DECK-EI-slide-5.png"
    stale.write_bytes(b"x")
    stdout, stderr, status = run_cli("render", ei_file)
    assert (stdout, stderr, status) == ("", f"error: {INSTALL_MESSAGE}\n", 1)
    assert stale.is_file()


def test_missing_playwright_package_gives_the_install_message(ei_file, out_dir, monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    stdout, stderr, status = run_cli("render", ei_file)
    assert (stdout, stderr, status) == ("", f"error: {INSTALL_MESSAGE}\n", 1)


def test_import_purity():
    code = "import sys, mcp_htmleditor.render;print('playwright' in sys.modules, 'pptx' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=ROOT)  # noqa: S603
    assert result.stdout.strip() == "False False"
