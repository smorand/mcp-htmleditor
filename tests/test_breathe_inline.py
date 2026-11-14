"""SPEC-0023 (US-0118): ``mcp-htmleditor breathe-inline`` embeds or links the Breathe decoration and pictures.

E2E-011 to E2E-020, E2E-063 to E2E-065, E2E-069, E2E-072 and the exploit tests E2E-SEC-007, E2E-SEC-008,
E2E-SEC-009, E2E-SEC-011, E2E-SEC-012. Every deck lives in ``tmp_path``; "unchanged" is read on the bytes of the
deck and on the listing of its folder, never on the command's own answer.
"""

from __future__ import annotations

import base64
import shutil
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Page

from mcp_htmleditor.breathe import inline as inline_module
from mcp_htmleditor.breathe.inline import catalogue_dir
from mcp_htmleditor.fileio import WriteError
from tests.breathe_support import (
    BOOTSTRAP,
    CATALOGUE,
    REFERENCE,
    breathe_deck,
    breathe_slide,
    reference_slide,
)
from tests.conftest import needs_chromium
from tests.deck_support import run_cli

SECRET = b"TOP-SECRET-42"
SECRET_B64 = base64.b64encode(SECRET).decode()[:18]  # "VE9QLVNFQ1JFVC00Mg"
EXTRA_FILES = (
    "collage-sample-b.jpg",
    "wiip-strong-logo.png",
    "filigrane-stethoscope-poumons.png",
    "logo-2026-botanical-transparent.png",
)
ALL_LOADED = """() => {
  const slides = Array.from(document.querySelectorAll('[data-type="slide"]'));
  const imgs = slides.flatMap((s) => Array.from(s.querySelectorAll('img')));
  const decorated = slides.flatMap((s) => [s, ...s.querySelectorAll('.med-ico')]);
  return {imgs: imgs.length, loaded: imgs.every((i) => i.complete && i.naturalWidth > 0),
          backgrounds: decorated.every((el) => getComputedStyle(el).backgroundImage !== 'none')};
}"""


def picture(name: str) -> str:
    return f'<img class="med-pic" data-asset="{name}" src="" alt="x">'


def deck_with(tmp_path: Path, *slides: str, folder: str = "deck") -> Path:
    path = tmp_path / folder / "talk.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(breathe_deck(*slides), encoding="utf-8")
    return path


def inline(*args: str) -> tuple[str, str, int]:
    stdout, stderr, code = run_cli("breathe-inline", *args)
    return stdout.strip(), stderr.strip(), code


def decoration_classes(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    return {
        cls
        for slide in soup.find_all(attrs={"data-type": "slide"})
        for element in [slide, *slide.find_all(True)]
        for cls in element.get("class") or []
        if cls.startswith(("med-bg-", "med-ico-"))
    }


def listing(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*"))


def check_loaded(page: Page, path: Path) -> dict[str, object]:
    page.goto(path.as_uri(), wait_until="load")
    return dict(page.evaluate(ALL_LOADED))


# -- journeys ---------------------------------------------------------------------------------------------


@needs_chromium
def test_embed_inline(tmp_path: Path, page: Page) -> None:
    """E2E-011."""
    deck = deck_with(tmp_path, reference_slide("Key figures"), breathe_slide("Pic", picture("sample-clinical-b.jpg")))
    stdout, stderr, code = inline(str(deck))
    html = deck.read_text(encoding="utf-8")
    classes = decoration_classes(html)
    size = len(html.encode()) // 1024
    assert (code, stderr) == (0, "")
    assert stdout == f"{deck}: {len(classes)} background and icon classes, 2 pictures embedded, {size} KB"
    assert {"med-bg-split-s1", "med-ico-lungs-dark", "med-bg-cover-s0"} <= classes
    assert check_loaded(page, deck) == {"imgs": 2, "loaded": True, "backgrounds": True}


def test_stage_boundaries_found(tmp_path: Path) -> None:
    """E2E-012."""
    slides = [
        breathe_slide(f"S{i}", background=bg)
        for i, bg in enumerate(("track-s0", "track-s5", "divider-s1", "divider-s4"))
    ]
    deck = deck_with(tmp_path, *slides)
    _, _, code = inline(str(deck))
    html = deck.read_text(encoding="utf-8")
    assert code == 0
    for bg in ("track-s0", "track-s5", "divider-s1", "divider-s4"):
        assert f"  .med-bg-{bg} {{ background-image:url(data:image/png;base64," in html


def test_nothing_to_embed(tmp_path: Path) -> None:
    """E2E-013: a deck whose only slide uses no decoration class and no named picture."""
    path = tmp_path / "talk.html"
    html = BOOTSTRAP.read_text(encoding="utf-8")
    html = html.replace("med-bg-cover-s0", "plain-bg").replace(" med-ico-", " x-ico-").replace("data-asset=", "data-x=")
    path.write_text(html, encoding="utf-8")
    stdout, _, code = inline(str(path))
    assert code == 0
    assert stdout.startswith(f"{path}: 0 background and icon classes, 0 pictures embedded, ")
    written = path.read_text(encoding="utf-8")
    assert "/* breathe:assets:begin */\n\n  /* breathe:assets:end */" in written


def test_embedding_twice_changes_nothing_and_keeps_one_history_entry(tmp_path: Path) -> None:
    """E2E-014 and E2E-072."""
    deck = deck_with(tmp_path, reference_slide("Key figures"))
    inline(str(deck))
    once = deck.read_bytes()
    inline(str(deck))
    assert deck.read_bytes() == once
    stdout, _, code = run_cli("history", str(deck))
    assert code == 0
    assert [line.split()[-1] for line in stdout.splitlines() if line.strip()].count("breathe-inline") == 1


def test_shipped_files_are_fresh(tmp_path: Path) -> None:
    """The shipped starting point and reference deck equal their own embedding (DEC-016)."""
    for source in (BOOTSTRAP, REFERENCE):
        copy = tmp_path / source.name
        shutil.copyfile(source, copy)
        _, _, code = inline(str(copy))
        assert code == 0
        assert copy.read_bytes() == source.read_bytes(), f"{source.name}: run make sync-breathe-layouts"


def test_reference_alone_embeds_from_the_catalogue(tmp_path: Path) -> None:
    """E2E-063."""
    copy = tmp_path / "ref.html"
    shutil.copyfile(REFERENCE, copy)
    stdout, _, code = inline(str(copy))
    count = len(BeautifulSoup(REFERENCE.read_text(encoding="utf-8"), "html.parser").select("img[data-asset]"))
    assert code == 0
    assert f", {count} pictures embedded, " in stdout


@needs_chromium
def test_the_four_shipped_extra_files_embed_and_copy(tmp_path: Path, page: Page) -> None:
    """E2E-064 and E2E-065."""
    slides = "".join(picture(name) for name in EXTRA_FILES)
    deck = deck_with(tmp_path, breathe_slide("Extras", slides, kind="thanks"))
    stdout, _, code = inline(str(deck))
    assert code == 0
    assert ", 5 pictures embedded, " in stdout  # the cover's logo disc and the four files
    assert check_loaded(page, deck)["loaded"] is True
    stdout, _, code = inline(str(deck), "--link")
    folder = deck.parent / "assets"
    assert code == 0
    # 5 class files (cover background, 3 cover icons, the slide background) and 5 pictures
    assert f", 5 pictures linked, 10 files copied to {folder.resolve()}, " in stdout
    for name in EXTRA_FILES:
        assert (folder / name).read_bytes() == (CATALOGUE / name).read_bytes()


# -- refusals ----------------------------------------------------------------------------------------------


def test_no_decoration_block(tmp_path: Path) -> None:
    """E2E-015."""
    path = tmp_path / "med.html"
    shutil.copyfile(BOOTSTRAP.parent / "slides-medical-empty.html", path)
    before = path.read_bytes()
    _, stderr, code = inline(str(path))
    assert (stderr, code) == (f"error: {path} has no breathe:assets block in its <style>", 1)
    assert path.read_bytes() == before


def test_missing_picture_leaves_the_deck_unchanged(tmp_path: Path) -> None:
    """E2E-016."""
    deck = deck_with(tmp_path, breathe_slide("P", picture("sample-photo-b.jpg") + picture("nowhere.jpg")))
    before = deck.read_bytes()
    _, stderr, code = inline(str(deck))
    folder = deck.resolve().parent / "assets"
    assert (stderr, code) == (f"error: asset nowhere.jpg not found in: {folder}, {catalogue_dir()}", 1)
    assert deck.read_bytes() == before
    assert not folder.exists()
    _, stderr, code = inline(str(deck), "--link")
    assert code == 1
    assert not folder.exists()


def test_missing_deck_file(tmp_path: Path) -> None:
    """E2E-017."""
    _, stderr, code = inline(str(tmp_path / "nothere.html"))
    assert (stderr, code) == (f"error: File not found: {tmp_path / 'nothere.html'}", 1)


def test_template_and_encoding_refusals(tmp_path: Path) -> None:
    """FR-NEW-008 order: a template file, then a file that is not UTF-8."""
    before = REFERENCE.read_bytes()
    _, stderr, code = inline(str(REFERENCE))
    assert (stderr, code) == (f"error: Refusing to modify a template: {REFERENCE}", 1)
    assert REFERENCE.read_bytes() == before
    bad = tmp_path / "bad.html"
    bad.write_bytes(b"\xff\xfe<html>")
    _, stderr, code = inline(str(bad))
    assert (stderr, code) == (f"error: File is not valid UTF-8: {bad}", 1)


# -- link mode ----------------------------------------------------------------------------------------------


@needs_chromium
def test_link_mode(tmp_path: Path, page: Page) -> None:
    """E2E-018."""
    deck = deck_with(tmp_path, reference_slide("Key figures"), breathe_slide("Photo", picture("photo.jpg")))
    (deck.parent / "assets").mkdir()
    shutil.copyfile(CATALOGUE / "sample-photo-b.jpg", deck.parent / "assets" / "photo.jpg")
    stdout, _, code = inline(str(deck), "--link")
    html = deck.read_text(encoding="utf-8")
    classes = decoration_classes(html)
    folder = deck.resolve().parent / "assets"
    copied = len(classes) + 1  # every class file and the cover's logo disc; photo.jpg is already there
    assert code == 0
    assert stdout == (
        f"{deck}: {len(classes)} background and icon classes, 2 pictures linked, {copied} files copied to {folder}, "
        f"{len(html.encode()) // 1024} KB"
    )
    block = html[html.index("/* breathe:assets:begin */") : html.index("/* breathe:assets:end */")]
    assert "data:image" not in block
    assert 'src="assets/photo.jpg"' in html
    assert check_loaded(page, deck) == {"imgs": 2, "loaded": True, "backgrounds": True}


def test_link_mode_never_overwrites(tmp_path: Path) -> None:
    """E2E-019."""
    deck = deck_with(tmp_path, breathe_slide("A", '<i class="med-ico med-ico-scope-ring"></i>'))
    folder = deck.parent / "assets"
    folder.mkdir()
    (folder / "icon-scope-ring.png").write_bytes(b"custom")
    stdout, _, code = inline(str(deck), "--link")
    assert code == 0
    assert (folder / "icon-scope-ring.png").read_bytes() == b"custom"
    # copied: the cover background, its three icons, the slide background and the logo disc; not the custom icon
    assert ", 6 files copied to " in stdout


@needs_chromium
def test_inline_after_link(tmp_path: Path, page: Page) -> None:
    """E2E-020."""
    deck = deck_with(tmp_path, reference_slide("Key figures"))
    inline(str(deck), "--link")
    _, _, code = inline(str(deck))
    assert code == 0
    (deck.parent / "assets").rename(deck.parent / "moved")
    html = deck.read_text(encoding="utf-8")
    assert "url(assets/" not in html
    assert 'src="assets/' not in html
    assert check_loaded(page, deck) == {"imgs": 1, "loaded": True, "backgrounds": True}


@needs_chromium
def test_link_staying_inside_the_assets_folder(tmp_path: Path, page: Page) -> None:
    """E2E-069."""
    path = tmp_path / "deck" / "talk.html"
    path.parent.mkdir()
    html = BOOTSTRAP.read_text(encoding="utf-8")
    html = html.replace("med-bg-cover-s0", "plain-bg").replace(" med-ico-", " x-ico-")
    html = html.replace('data-asset="logo-disc.png"', 'data-asset="photo.png"')
    path.write_text(html, encoding="utf-8")
    real = path.parent / "assets" / "real"
    real.mkdir(parents=True)
    shutil.copyfile(CATALOGUE / "logo-disc.png", real / "photo.png")
    (path.parent / "assets" / "photo.png").symlink_to(real / "photo.png")
    stdout, _, code = inline(str(path))
    assert code == 0
    assert stdout.startswith(f"{path}: 0 background and icon classes, 1 pictures embedded,")
    assert check_loaded(page, path)["loaded"] is True


# -- exploits (occurrence #3 of the class sweep) ------------------------------------------------------------


@pytest.fixture
def secret_deck(tmp_path: Path) -> Path:
    (tmp_path / "secret.png").write_bytes(SECRET)
    return tmp_path / "deck" / "talk.html"


def write(path: Path, html: str) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path.read_bytes()


def test_sec_007_embedded_name_climbing_out(secret_deck: Path) -> None:
    before = write(secret_deck, breathe_deck(breathe_slide("A", picture("../secret.png"))))
    _, stderr, code = inline(str(secret_deck))
    assert (stderr, code) == ("error: asset name ../secret.png is not a plain file name", 1)
    assert secret_deck.read_bytes() == before
    assert SECRET_B64 not in secret_deck.read_text(encoding="utf-8")


def test_sec_008_absolute_name_in_link_mode(secret_deck: Path) -> None:
    absolute = str(secret_deck.parent.parent / "secret.png")
    before = write(secret_deck, breathe_deck(breathe_slide("A", picture(absolute))))
    listed = listing(secret_deck.parent)
    _, stderr, code = inline(str(secret_deck), "--link")
    assert (stderr, code) == (f"error: asset name {absolute} is not a plain file name", 1)
    assert listing(secret_deck.parent) == listed
    assert secret_deck.read_bytes() == before


def test_sec_009_class_suffix_climbing_out(secret_deck: Path) -> None:
    before = write(secret_deck, breathe_deck(breathe_slide("A", '<div class="med-bg-x/../../../secret">x</div>')))
    (secret_deck.parent / "assets" / "bg-x").mkdir(parents=True)
    _, stderr, code = inline(str(secret_deck))
    assert (stderr, code) == ("error: asset name x/../../../secret is not a plain file name", 1)
    assert secret_deck.read_bytes() == before
    assert SECRET_B64 not in secret_deck.read_text(encoding="utf-8")


def test_sec_011_linked_asset_leaving_the_folder(secret_deck: Path) -> None:
    before = write(secret_deck, breathe_deck(breathe_slide("A", picture("photo.png"))))
    assets = secret_deck.parent / "assets"
    assets.mkdir()
    (assets / "photo.png").symlink_to("../../secret.png")
    _, stderr, code = inline(str(secret_deck))
    assert (stderr, code) == (f"error: asset photo.png leads outside {secret_deck.resolve().parent / 'assets'}", 1)
    assert secret_deck.read_bytes() == before
    assert SECRET_B64 not in secret_deck.read_text(encoding="utf-8")


def test_sec_012_dangling_link_in_link_mode(secret_deck: Path) -> None:
    write(secret_deck, breathe_deck(breathe_slide("A", '<i class="med-ico med-ico-scope-ring"></i>')))
    assets = secret_deck.parent / "assets"
    assets.mkdir()
    (assets / "icon-scope-ring.png").symlink_to("../../written.png")
    _, stderr, code = inline(str(secret_deck), "--link")
    assert (stderr, code) == (
        f"error: asset icon-scope-ring.png leads outside {secret_deck.resolve().parent / 'assets'}",
        1,
    )
    assert not (secret_deck.parent.parent / "written.png").exists()


# -- US-0123 (converge): write failures and marker cases ------------------------------------------------------


def test_write_failure_leaves_the_deck_and_its_folder_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-NEW-008, NFR-007: the copies of link mode and the assets folder they needed are removed."""
    deck = deck_with(tmp_path, reference_slide("Key figures"))
    before = deck.read_bytes()
    listed = listing(deck.parent)

    def refuse(path: object, data: object, **kwargs: object) -> bool:
        raise WriteError(path, "No space left on device")  # type: ignore[arg-type]

    monkeypatch.setattr(inline_module, "atomic_write", refuse)
    for args in ((str(deck),), (str(deck), "--link")):
        _, stderr, code = inline(*args)
        assert (stderr, code) == (f"error: Cannot write {deck.resolve()}: No space left on device", 1)
        assert deck.read_bytes() == before
        assert listing(deck.parent) == listed


def test_one_marker_or_markers_reversed_is_no_block(tmp_path: Path) -> None:
    """FR-NEW-008: a deck holding only one marker, or the end marker before the begin marker, has no block."""
    html = BOOTSTRAP.read_text(encoding="utf-8")
    begin, end = "/* breathe:assets:begin */", "/* breathe:assets:end */"
    only_begin = html.replace(end, "/* end */", 1)
    start = html.index(begin)
    stop = html.index(end) + len(end)
    block = html[start:stop]
    reversed_markers = html[:start] + block.replace(begin, "@@").replace(end, begin).replace("@@", end) + html[stop:]
    for name, text in (("only.html", only_begin), ("reversed.html", reversed_markers)):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        _, stderr, code = inline(str(path))
        assert (stderr, code) == (f"error: {path} has no breathe:assets block in its <style>", 1), name
        assert path.read_text(encoding="utf-8") == text


def test_assets_folder_leading_outside_is_refused(tmp_path: Path) -> None:
    """FR-NEW-025: an assets folder that is a link to another folder is outside the deck's folder."""
    outside = tmp_path / "outside"
    outside.mkdir()
    deck = deck_with(tmp_path, reference_slide("Key figures"))
    (deck.parent / "assets").symlink_to(outside)
    before = deck.read_bytes()
    _, stderr, code = inline(str(deck), "--link")
    assert code == 1
    assert stderr.startswith("error: asset ") and stderr.endswith(f"leads outside {deck.resolve().parent / 'assets'}")
    assert deck.read_bytes() == before
    assert list(outside.iterdir()) == []
