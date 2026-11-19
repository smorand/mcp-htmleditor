"""SPEC-0026 (US-0150): the PPTX flow export reads no picture outside the deck's folder.

The second channel is the media parts of the PPTX (the bytes of the secret picture are searched for), never the
warning.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from mcp_htmleditor.deck_folder import OUTSIDE_PREFIX
from mcp_htmleditor.export.to_pptx import to_pptx
from tests.library_support import PNG_1X1

SECRET = PNG_1X1 + b"SECRET-PICTURE-MARKER"
LIBRARY_WARNING = "Image non incluse dans le fichier, ignoree."


def media(output: Path) -> list[bytes]:
    with zipfile.ZipFile(output) as archive:
        return [archive.read(name) for name in archive.namelist() if name.startswith("ppt/media/")]


def make_deck(tmp_path: Path, sources: list[str], head: str = "", attrs: str = "", slide_class: str = "slide") -> Path:
    """A one slide deck in ``tmp_path/deck``; ``secret.png`` sits next to the folder, outside it."""
    folder = tmp_path / "deck"
    folder.mkdir(exist_ok=True)
    (tmp_path / "secret.png").write_bytes(SECRET)
    images = "".join(f'<img src="{source}" alt="x">' for source in sources)
    path = folder / "deck.html"
    path.write_text(
        f'<!DOCTYPE html><html data-doc-type="presentation"{attrs}><head>{head}</head><body>'
        f'<section class="{slide_class}" data-type="slide" data-id="s1" data-title="One"><h1>One</h1>{images}'
        "</section></body></html>",
        encoding="utf-8",
    )
    return path


def outside_warnings(report_warnings: list[str]) -> list[str]:
    return [w for w in report_warnings if w.startswith(OUTSIDE_PREFIX)]


def test_bt010_absolute_climbing_and_symlinked_pictures_are_refused(tmp_path: Path) -> None:
    """BT-010: three payloads, one per way out of the folder."""
    path = make_deck(tmp_path, ["../secret.png", str(tmp_path / "secret.png"), "link.png"])
    (tmp_path / "deck" / "link.png").symlink_to(tmp_path / "secret.png")
    output = tmp_path / "out.pptx"

    report = to_pptx(str(path), str(output), paint=False)

    assert SECRET not in media(output)
    refused = {w.removeprefix(OUTSIDE_PREFIX) for w in outside_warnings(report.warnings)}
    assert refused == {"../secret.png", str(tmp_path / "secret.png")[:60], "link.png"}


def test_bt015_background_class_url_outside_the_folder_is_refused(tmp_path: Path) -> None:
    """BT-015: the url() of a Breathe med-bg-* class goes through the same read."""
    head = "<style>.med-bg-x{background-image:url(../secret.png)}</style>"
    path = make_deck(tmp_path, [], head=head, attrs=' data-doc-template="breathe"', slide_class="slide med-bg-x")
    output = tmp_path / "out.pptx"

    report = to_pptx(str(path), str(output), paint=False)

    assert SECRET not in media(output)
    assert f"{OUTSIDE_PREFIX}../secret.png" in report.warnings


def test_bt020_the_warning_cuts_the_address_at_60_characters(tmp_path: Path) -> None:
    address = "../" + "a" * 70 + ".png"
    path = make_deck(tmp_path, [address])

    report = to_pptx(str(path), str(tmp_path / "out.pptx"), paint=False)

    assert f"{OUTSIDE_PREFIX}{address[:60]}" in report.warnings


def test_bt021_a_symlink_that_stays_inside_is_read(tmp_path: Path) -> None:
    path = make_deck(tmp_path, ["link.png"])
    (tmp_path / "deck" / "real").mkdir()
    (tmp_path / "deck" / "real" / "a.png").write_bytes(SECRET)
    (tmp_path / "deck" / "link.png").symlink_to(tmp_path / "deck" / "real" / "a.png")
    output = tmp_path / "out.pptx"

    report = to_pptx(str(path), str(output), paint=False)

    assert SECRET in media(output)
    assert outside_warnings(report.warnings) == []


def test_bt023_the_library_mode_keeps_its_own_text(tmp_path: Path) -> None:
    path = make_deck(tmp_path, ["../secret.png"])

    report = to_pptx(str(path), str(tmp_path / "out.pptx"), paint=False, embedded_pictures_only=True)

    assert LIBRARY_WARNING in report.warnings
    assert outside_warnings(report.warnings) == []
