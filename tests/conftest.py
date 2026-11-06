"""Shared pytest fixtures for mcp-htmleditor tests."""

from __future__ import annotations

import http.client
import json
import platform
import socket
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import config as config_module
from mcp_htmleditor import state as state_module
from mcp_htmleditor.http_server import start_http_server, stop_http_server
from tests.deck_support import deck_ei, write_deck


def _chromium_cache_dir() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library" / "Caches" / "ms-playwright"
    return home / ".cache" / "ms-playwright"


SLOW_TEST_TIMEOUT_SECONDS = 900

HAS_CHROMIUM = any(_chromium_cache_dir().glob("chromium-*"))
needs_chromium = pytest.mark.skipif(
    not HAS_CHROMIUM,
    reason="Playwright Chromium is not installed; run `make sync`",
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Give every test marked slow its own 900 second limit (SPEC-0014/BR-012)."""
    for item in items:
        if item.get_closest_marker("slow") is not None and item.get_closest_marker("timeout") is None:
            item.add_marker(pytest.mark.timeout(SLOW_TEST_TIMEOUT_SECONDS))


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    """Drop the memoized Settings around each test.

    Settings are memoized on an environment signature, so a test that sets
    HTMLEDITOR_* variables must not hand its instance over to the next one.
    """
    config_module.reset_settings_cache()
    yield
    config_module.reset_settings_cache()


REAL_STATE_DIR = Path.home() / ".local" / "state" / "mcp-htmleditor"


def _listing(root: Path) -> dict[str, tuple[int, int]]:
    """Every path under ``root`` with its mtime (ns) and size, empty when ``root`` does not exist."""
    if not root.exists():
        return {}
    return {str(p): (p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(root.rglob("*"))}


@pytest.fixture(autouse=True, scope="session")
def real_state_dir_untouched() -> Iterator[None]:
    """Fail the session if any test wrote into the user's real ~/.local/state/mcp-htmleditor."""
    before = _listing(REAL_STATE_DIR)
    yield
    assert _listing(REAL_STATE_DIR) == before, f"a test wrote into the real state dir {REAL_STATE_DIR}"


@pytest.fixture(autouse=True)
def isolate_state_dir(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HTMLEDITOR_STATE_DIR at a per test directory, so no test touches the real ~/.local/state."""
    state_dir = tmp_path_factory.mktemp("state") / "mcp-htmleditor"
    monkeypatch.setenv("HTMLEDITOR_STATE_DIR", str(state_dir))
    config_module.reset_settings_cache()
    return state_dir


@pytest.fixture
def reset_state() -> Iterator[None]:
    """Reset the EditorState singleton around each test.

    EditorState is a process-wide singleton keyed on a class attribute.
    Tests must start from a clean instance so state does not leak between
    cases.
    """
    state_module.EditorState._instance = None
    state_module.EditorState._initialized = False
    yield
    state_module.EditorState._instance = None
    state_module.EditorState._initialized = False


@pytest.fixture
def fresh_state(reset_state: None) -> state_module.EditorState:
    """Return a freshly initialized EditorState singleton."""
    return state_module.get_state()


@pytest.fixture
def html_file(tmp_path: Path) -> Path:
    """Write a minimal HTML file into tmp_path and return its path."""
    path = tmp_path / "doc.html"
    path.write_text(
        "<!DOCTYPE html>\n<html><head><title>t</title></head><body><p>hello</p></body></html>",
        encoding="utf-8",
    )
    return path


SKILL_TOPICS: tuple[tuple[str, str], ...] = (
    ("create", "Create and edit a file: workflows, rules for text, slides and images"),
    ("export", "Export to PPTX and DOCX: what is kept, approximated, lost"),
    ("templates", "Build a template from an existing PPTX or DOCX"),
    ("slides-carbon", "Rules for IBM Carbon slides"),
    ("slides-ei", "Rules for Euro-Information slides"),
    (
        "medical",
        "Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget",
    ),
    ("medical-sources", "Medical slides: citing sources and anonymising patient images"),
    ("document", "Rules for Word-like documents and their DOCX export"),
    ("mail", "Rules for HTML mails"),
    ("website", "Rules for single page websites"),
    ("gantt", "Rules for Gantt charts"),
    ("arch-diagram", "Rules for architecture diagrams"),
    ("arch-qa", "Visual quality review of architecture diagrams and its checklist"),
    ("annotated-image", "Rules for annotated images"),
    ("tables", "Rules for tables"),
)

SKILL_CORE_TITLE = "# mcp-htmleditor skill (core)"


class SkillTree:
    """A generated skill tree (core, 15 topics, checklist) rooted in a temporary directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.core_path = root / "core.md"
        self.checklist_path = root / "checks" / "arch-diagram-checklist.md"

    def topic_path(self, name: str) -> Path:
        return self.root / "topics" / f"{name}.md"

    def write_core(self, text: str) -> None:
        self.core_path.write_text(text, encoding="utf-8")

    def remove(self, name: str) -> None:
        """Remove a topic file, or the core when name is 'core'."""
        path = self.core_path if name == "core" else self.topic_path(name)
        path.unlink()

    def grow(self, path: Path, to_bytes: int) -> None:
        """Append ASCII text until the file holds to_bytes bytes."""
        missing = to_bytes - path.stat().st_size
        if missing > 0:
            with path.open("a", encoding="ascii") as handle:
                handle.write("x" * missing)


@pytest.fixture
def skill_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SkillTree:
    """Build a valid temporary skill tree and point the settings at it."""

    def build(tools: str = "") -> SkillTree:
        tree = SkillTree(tmp_path / "skill")
        (tree.root / "topics").mkdir(parents=True)
        tree.checklist_path.parent.mkdir(parents=True)
        index = "\n".join(
            f"{name}: {description}. Load: mcp-htmleditor skill --type {name}" for name, description in SKILL_TOPICS
        )
        tree.write_core(f"{SKILL_CORE_TITLE}\n\n## Index\n\n{index}\n\n## Tools\n\n{tools}\n\n")
        for name, _ in SKILL_TOPICS:
            tree.topic_path(name).write_text(f"## Rules for {name}\n\nBody of {name}.\n\n\n", encoding="utf-8")
        tree.checklist_path.write_text("- [ ] checklist item\n\n", encoding="utf-8")
        return tree

    tree = build()
    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(tree.root))
    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(tmp_path / "empty-checks"))
    config_module.reset_settings_cache()
    return tree


@dataclass(frozen=True)
class DeckReply:
    """One answer of the editor server: status and decoded JSON body."""

    status: int
    body: dict[str, Any]


@dataclass(frozen=True)
class ServedDeck:
    """A file served by a real editor server, with raw HTTP helpers."""

    path: Path
    port: int

    def request(
        self, method: str, route: str, body: bytes = b"", content_length: str | None = None, send_body: bool = True
    ) -> DeckReply:
        """Send a request with exactly the given Content-Length (default: the body size)."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        try:
            conn.putrequest(method, route, skip_accept_encoding=True)
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(len(body)) if content_length is None else content_length)
            conn.endheaders(body if send_body else None)
            response = conn.getresponse()
            raw = response.read()
            return DeckReply(status=response.status, body=json.loads(raw) if raw else {})
        finally:
            conn.close()

    def status(self) -> dict[str, Any]:
        """Return the JSON of ``GET /status``."""
        return self.request("GET", "/status").body

    def save(self, payload: dict[str, Any]) -> DeckReply:
        """POST ``payload`` as JSON to ``/content``."""
        return self.request("POST", "/content", json.dumps(payload).encode("utf-8"))


def _wait_listening(port: int) -> None:
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail(f"server on port {port} did not start in time")


@pytest.fixture
def serve_deck(reset_state: None) -> Iterator[Callable[[Path], ServedDeck]]:
    """Return a function serving a file with a real editor server, stopped at teardown."""
    started: list[int] = []

    def serve(path: Path) -> ServedDeck:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        start_http_server(str(path), port=port, host="127.0.0.1")
        started.append(port)
        _wait_listening(port)
        return ServedDeck(path=path, port=port)

    yield serve
    if started:
        stop_http_server()


@pytest.fixture
def served_deck(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> ServedDeck:
    """DECK: an 8 slide Euro-Information deck ``deck.html`` in its own folder, served by the editor."""
    folder = tmp_path / "work"
    folder.mkdir()
    return serve_deck(Path(write_deck(folder / "deck.html", deck_ei())))
