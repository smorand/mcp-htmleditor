"""SPEC-0034 (US-0173): the agent operation ``add_pointer`` gives the results and errors of ``add-pointer``.

E2E-006 and E2E-009. The tool is called through an in process ``fastmcp.Client``; the command through ``run_cli`` for
parity. "Unchanged" is read on the bytes of the file.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import call_tool, run_cli
from tests.pointer_old_deck_support import CARBON, PRESENT_BUTTON, older_deck, older_text, parts_in
from tests.pointer_support import HEIGHT, WIDTH, leave_full_screen, pointer_file_page

__all__ = ["pointer_file_page"]

DECK_READY = (
    "() => { const f = document.getElementById('content-frame'); const d = f && f.contentDocument;"
    " return document.getElementById('toolbar-filename').textContent !== '\u2014'"
    " && !!d && d.readyState === 'complete' && !!d.querySelector('#btn-present'); }"
)
COMPLETE = {"code": 1, "control": 1, "key": 1}


def test_e2e_006_the_tool_writes_the_same_file_and_says_the_same(tmp_path: Path) -> None:
    (tmp_path / "tool").mkdir()
    (tmp_path / "command").mkdir()
    tool_deck = older_deck(CARBON, tmp_path / "tool")
    command_deck = older_deck(CARBON, tmp_path / "command")

    ok, result = call_tool("add_pointer", file=str(tool_deck))
    stdout, stderr, code = run_cli("add-pointer", str(command_deck))

    assert (ok, code, stderr) == (True, 0, "")
    assert result == {"ok": True, "summary": stdout.strip().replace(str(command_deck), str(tool_deck)), "added": True}
    assert tool_deck.read_bytes() == command_deck.read_bytes()
    assert parts_in(tool_deck.read_text(encoding="utf-8")) == COMPLETE

    ok, again = call_tool("add_pointer", file=str(tool_deck))
    assert ok and again == {"ok": True, "summary": f"{tool_deck}: already has the pointer", "added": False}


def test_e2e_006_the_refusals_read_as_the_commands_without_the_prefix(tmp_path: Path) -> None:
    doc = tmp_path / "doc.html"
    assert run_cli("new", "doc", str(doc))[2] == 0
    bare = tmp_path / "bare.html"
    bare.write_text(PRESENT_BUTTON.sub("", older_text(CARBON)), encoding="utf-8")
    cases = (tmp_path / "absent.html", CARBON, doc, bare)
    before = {path: path.read_bytes() for path in (CARBON, doc, bare)}

    for path in cases:
        ok, message = call_tool("add_pointer", file=str(path))
        _, stderr, code = run_cli("add-pointer", str(path))
        assert (ok, code) == (False, 1), path
        assert stderr == f"error: {message}\n", path

    assert {path: path.read_bytes() for path in before} == before


@needs_chromium
def test_e2e_009_an_older_deck_without_the_request_shows_no_pointer_control(
    tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], pointer_file_page: Page
) -> None:
    served = serve_deck(older_deck(CARBON, tmp_path))

    page = pointer_file_page
    leave_full_screen(page)
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    page.goto(f"http://127.0.0.1:{served.port}/")
    wait_until(page, lambda: page.evaluate(DECK_READY), bool, what="the editor and its deck ready")

    assert pointer_file_page.is_hidden("#pointer-btn")
    assert pointer_file_page.frame_locator("#content-frame").locator("#btn-pointer").count() == 0
