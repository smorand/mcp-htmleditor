"""SPEC-0010 US-0059: the request loop end to end, nothing next to the user's file, and the documentation.

E2E-028 drives a real editor in Chromium plus the agent tool surface; the UT-H tests run in process.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from playwright.sync_api import Page

from mcp_htmleditor import cli as cli_module
from mcp_htmleditor import config
from mcp_htmleditor.cli import main
from mcp_htmleditor.request_service import RequestService
from mcp_htmleditor.request_store import RequestStore
from mcp_htmleditor.skill_content import build_library
from tests.conftest import ServedDeck, needs_chromium

from .deck_support import call_tool, run_cli
from .test_requests_core import expected_key, make_deck
from .test_requests_editor_e2e import _open, _open_panel, _queue

REPO = Path(__file__).resolve().parents[1]
CREATE = REPO / "skill" / "topics" / "create.md"
CORE = REPO / "skill" / "core.md"
# The story says 3 800 bytes for the shipped file; since SPEC-0006 it holds about 7 800 bytes (BL-0028).
# The real bounds are the audit budget for topic_output (8 000) and 7 900 for the file.
TOPIC_OUTPUT_BUDGET = 8000
SHIPPED_FILE_BUDGET = 7900
TWO_SUGGESTIONS = [
    {
        "id": "s1",
        "slide": "slide-2",
        "title": "Tighten the agenda",
        "why": "The agenda has 8 lines",
        "change": "Cut to 5 lines",
    },
    {
        "id": "s2",
        "slide": None,
        "title": "Add a closing slide",
        "why": "The deck ends abruptly",
        "change": "Add a thank you slide",
    },
]
STDOUT_SCRIPT = """
import asyncio, sys
from fastmcp import Client
from mcp_htmleditor.mcp_server import mcp

async def main():
    async with Client(mcp) as client:
        await client.call_tool("list_requests", {"file": sys.argv[1]})
        await client.call_tool("write_review", {"file": sys.argv[1], "suggestions": []})

asyncio.run(main())
"""


def _service() -> RequestService:
    return RequestService(RequestStore(config.state_dir()))


@needs_chromium
def test_e2e_028_nothing_next_to_the_file(page: Page, served_deck: ServedDeck) -> None:
    folder = served_deck.path.parent
    assert not config.state_dir().is_relative_to(folder)
    _open(page, served_deck)
    _open_panel(page)
    assert _queue(page, "Shorten the title") == "Request R-0001 queued"
    ok, result = call_tool("write_review", file=str(served_deck.path), suggestions=TWO_SUGGESTIONS)
    assert (ok, result) == (True, {"ok": True, "count": 2})
    assert sorted(entry.name for entry in folder.iterdir()) == ["deck.html"]
    requests_dir = config.state_dir() / "files" / expected_key(served_deck.path) / "requests"
    assert sorted(entry.name for entry in requests_dir.iterdir()) == ["record.json", "record.lock"]


def test_ut_h01_full_loop_in_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    deck = make_deck(tmp_path)
    service = _service()
    service.queue(deck, "Shorten the title", "slide-1")
    ok, listed = call_tool("list_requests", file=str(deck))
    assert ok
    assert [(r["id"], r["title"]) for r in listed["requests"]] == [("R-0001", "Shorten the title")]
    out, err, code = run_cli("requests", "deck.html")
    assert (out, err, code) == ("R-0001  pending  slide-1  Shorten the title\n", "", 0)
    assert call_tool("complete_request", file=str(deck), id="R-0001", status="done")[0]
    assert call_tool("write_review", file=str(deck), suggestions=TWO_SUGGESTIONS) == (True, {"ok": True, "count": 2})
    assert service.apply_suggestion(deck, "s1").id == "R-0002"
    found = service.list_requests(deck)
    assert [(r.id, r.status) for r in found] == [("R-0001", "done"), ("R-0002", "pending")]
    assert found[1].instruction == "Tighten the agenda. Cut to 5 lines"
    out, _, code = run_cli("review", "deck.html")
    assert code == 0
    assert out.splitlines() == ["s1  slide-2  Tighten the agenda", "s2  -  Add a closing slide"]


def test_ut_h02_state_directory_owns_the_data(tmp_path: Path) -> None:
    first = make_deck(tmp_path, "a.html")
    second = make_deck(tmp_path, "b.html")
    service = _service()
    store = RequestStore(config.state_dir())
    assert store.record_dir(first) != store.record_dir(second)
    service.queue(first, "one", None)
    assert call_tool("write_review", file=str(first), suggestions=TWO_SUGGESTIONS)[0]
    assert len(service.read_review(first)) == 2
    shutil.rmtree(config.state_dir())
    assert service.list_requests(first) == []
    assert service.read_review(first) == []
    assert service.queue(first, "again", None).id == "R-0001"


def test_ut_h03_skill_audit_and_topic_size() -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cli_module, "configure_tracing", lambda settings=None: None)
        result = CliRunner().invoke(main, ["skill-audit"])
    assert result.exit_code == 0, result.output
    assert result.stdout.rstrip("\n").splitlines()[-1] == "skill-audit: OK"
    assert len(build_library().topic_output("create").encode()) <= TOPIC_OUTPUT_BUDGET
    assert CREATE.stat().st_size <= SHIPPED_FILE_BUDGET
    tools = CORE.read_text(encoding="utf-8").split("## Tools", 1)[1].split("\n## ", 1)[0]
    for name in ("list_requests", "complete_request", "write_review"):
        assert f"- {name}:" in tools


def test_ut_h04_documentation_names_the_interfaces() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    for text in (readme, agents):
        for word in ("requests", "request-done", "request-skip", "review"):
            assert word in text
    for word in ("list_requests", "complete_request", "write_review"):
        assert word in readme


def test_ut_h05_tool_process_stdout_stays_clean(tmp_path: Path) -> None:
    deck = make_deck(tmp_path)
    env = {**os.environ, "HTMLEDITOR_STATE_DIR": str(config.state_dir()), "PYTHONPATH": str(REPO / "src")}
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", STDOUT_SCRIPT, str(deck)],
        env=env,
        cwd=REPO,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr.decode()
    assert done.stdout == b""
    assert json.loads((config.state_dir() / "files" / expected_key(deck) / "requests" / "record.json").read_text())
