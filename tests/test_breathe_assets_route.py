"""SPEC-0029 (US-0160): ``POST /breathe-assets`` gives the decoration rules of Breathe classes.

The rules must be the ones ``breathe-inline`` writes for the same classes. Refusals carry the command's messages and
change nothing on disk (listing of the deck's folder and bytes of the deck are compared).
"""

from __future__ import annotations

import http.client
import json
import os
import re
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_htmleditor.breathe import inline as inline_module
from tests.breathe_support import BOOTSTRAP, breathe_slide, reference_slide
from tests.conftest import ServedDeck
from tests.deck_support import run_cli
from tests.test_breathe_inline import deck_with, listing

BG, ICON = "med-bg-cover-s0", "med-ico-lungs-dark"
ROUTE = "/breathe-assets"


def breathe_deck_copy(tmp_path: Path, folder: str = "deck") -> Path:
    path = tmp_path / folder / "talk.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BOOTSTRAP.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def post(deck: ServedDeck, classes: object, link: object = False) -> tuple[int, dict[str, object]]:
    reply = deck.request("POST", ROUTE, json.dumps({"classes": classes, "link": link}).encode("utf-8"))
    return reply.status, reply.body


def command_rule(tmp_path: Path, class_name: str, *, link: bool) -> str:
    """The rule line ``breathe-inline`` writes for ``class_name`` in a copy of the bootstrap deck."""
    copy = deck_with(tmp_path, reference_slide("Key figures"), breathe_slide("Pic"), folder="command")
    run_cli("breathe-inline", str(copy), *(["--link"] if link else []))
    match = re.search(rf"^  \.{re.escape(class_name)} \{{.*\}}$", copy.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, class_name
    return match.group(0)


def test_t1_embedded_rules_equal_the_commands(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    deck = serve_deck(breathe_deck_copy(tmp_path))

    status, body = post(deck, [BG, ICON])

    assert status == 200
    assert body["rules"] == [command_rule(tmp_path, BG, link=False), command_rule(tmp_path, ICON, link=False)]
    assert str(body["rules"][0]).startswith(f"  .{BG} {{ background-image:url(data:image/")  # type: ignore[index]
    assert body["copied"] == 0


def test_t2_linked_rules_copy_the_files(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    deck = serve_deck(breathe_deck_copy(tmp_path))

    status, body = post(deck, [BG, ICON], link=True)

    assert status == 200
    assert body["rules"] == [
        f"  .{BG} {{ background-image:url(assets/bg-cover-s0.png); }}",
        f"  .{ICON} {{ background-image:url(assets/icon-lungs-dark.png); }}",
    ]
    assert body["copied"] == 2
    assert (deck.path.parent / "assets" / "bg-cover-s0.png").is_file()
    assert (deck.path.parent / "assets" / "icon-lungs-dark.png").is_file()


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("med-bg-../../secret", "asset name ../../secret is not a plain file name"),
        ("med-bg-/etc/passwd", "asset name /etc/passwd is not a plain file name"),
        ("not-a-class", "class not-a-class is not a decoration class"),
    ],
)
def test_t3_refused_names_change_nothing(
    tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], name: str, message: str
) -> None:
    path = breathe_deck_copy(tmp_path)
    deck = serve_deck(path)
    before, files = path.read_bytes(), listing(tmp_path)

    status, body = post(deck, [name], link=True)

    assert (status, body) == (422, {"error": message})
    assert path.read_bytes() == before
    assert listing(tmp_path) == files


def test_t4_a_missing_catalogue_file(
    tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-catalogue"
    empty.mkdir()
    monkeypatch.setattr(inline_module, "catalogue_dir", lambda: empty)
    deck = serve_deck(breathe_deck_copy(tmp_path))

    status, body = post(deck, [BG])

    assert status == 422
    assert body == {"error": f"asset bg-cover-s0.png not found in: {deck.path.parent.resolve() / 'assets'}, {empty}"}


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores folder permissions")
def test_t5_an_unwritable_folder_linked(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    path = breathe_deck_copy(tmp_path)
    deck = serve_deck(path)
    mode = stat.S_IMODE(path.parent.stat().st_mode)
    path.parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        status, body = post(deck, [BG], link=True)
    finally:
        path.parent.chmod(mode)

    assert status == 422
    assert str(body["error"]).startswith("Cannot write ")
    assert not (path.parent / "assets").exists()


@pytest.mark.parametrize(
    ("classes", "link"),
    [("med-bg-cover-s0", False), ([1], False), ([BG] * 65, False), ([BG], "yes"), (None, False)],
)
def test_t6_the_request_shape_is_checked(
    tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], classes: object, link: object
) -> None:
    deck = serve_deck(breathe_deck_copy(tmp_path))

    status, body = post(deck, classes, link)

    assert (status, body) == (400, {"error": "Invalid request body"})


def test_t6_a_body_that_is_not_an_object_and_a_wrong_content_type(
    tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck(breathe_deck_copy(tmp_path))
    assert deck.request("POST", ROUTE, b"[1]").status == 400

    conn = http.client.HTTPConnection("127.0.0.1", deck.port, timeout=10)
    try:
        conn.request("POST", ROUTE, body=b"{}", headers={"Content-Type": "text/plain"})
        assert conn.getresponse().status == 415
    finally:
        conn.close()


def test_the_rules_come_sorted_by_class_name_whatever_the_order_asked(
    tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck(breathe_deck_copy(tmp_path))

    _, forward = post(deck, [BG, ICON])
    _, backward = post(deck, [ICON, BG, BG])

    assert forward["rules"] == backward["rules"]
