"""US-0138: the request loop, the suggestions and the diagram layout in the library (SPEC-0025, DEC-003, DEC-044).

Spec test: E2E-SEC-023. The second channel of every refusal is what Dan reads afterwards (the list of requests, the
size and the history of the stored file) and the files of the library, never only the status line.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mcp_htmleditor.request_service import RequestService
from mcp_htmleditor.request_store import RequestStore
from tests import library_support
from tests.library_support import (
    CARDIOLOGY,
    CAROL,
    DAN,
    HEART_FAILURE,
    Browser,
    FakeGoogle,
    Presentation,
    RunningLibrary,
    signed_in,
)
from tests.test_arch_layout import SIMPLE_DIAGRAM

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
HEART_FAILURE_BYTES = 2_097_152
GUIDELINE = "Check the 2026 guideline"
DENIED = {"error": "Access denied.", "code": "denied"}
ROUTES_DIR = Path(__file__).resolve().parents[1] / "src" / "mcp_htmleditor" / "library"


@dataclass(frozen=True)
class Asked:
    """Heart Failure Update (2 MiB) with Dan's request "Check the 2026 guideline" and one AI suggestion ``s1``."""

    running: RunningLibrary
    heart: Presentation
    dan: Browser
    carol: Browser


@pytest.fixture
def asked(library_server: START, fake_google: FakeGoogle) -> Asked:
    running = library_server(fake_google)
    ids = running.builder.standard()
    heart = running.builder.presentation(ids[CARDIOLOGY], HEART_FAILURE, size=HEART_FAILURE_BYTES, modified=MODIFIED)
    dan, carol = (signed_in(running, fake_google, email) for email in (DAN, CAROL))
    for person in (dan, carol):
        person.open_presentation(heart.id)
    service = RequestService(RequestStore(running.state_dir))
    service.queue(heart.path, GUIDELINE, None)  # what Dan's Requests panel queued before this test starts
    service.write_review(
        heart.path, [{"id": "s1", "slide": None, "title": "Fewer words", "why": "Dense", "change": "Cut a line"}]
    )
    return Asked(running, heart, dan, carol)


def listed(person: Browser, heart: Presentation) -> dict[str, object]:
    """What the Requests panel reads: ``GET /d/<pid>/requests`` with the editor's header."""
    reply = person.deck(heart.id, "requests", x_editor="1")
    assert reply.status == 200, reply.text
    body: dict[str, object] = reply.json()
    return body


def instructions(person: Browser, heart: Presentation) -> list[str]:
    return [item["instruction"] for item in listed(person, heart)["requests"]]  # type: ignore[index, union-attr]


def test_e2e_sec_023_a_ro_member_sends_the_other_changing_requests_by_hand(asked: Asked) -> None:
    """E2E-SEC-023. Red before the fix because: the requests are accepted and the lists are readable; the assertion
    "Carol's reading of the Requests list is refused" fails and returns "Check the 2026 guideline". Carol sends the six
    requests with her own grant and the headers of the editor's fetch."""
    heart, carol, dan = asked.heart, asked.carol, asked.dan
    before = heart.path.read_bytes()
    request_id = str(listed(dan, heart)["requests"][0]["id"])  # type: ignore[index]

    replies = {
        "layout": carol.post_deck(heart.id, "arch-layout", {}),
        "queue": carol.post_deck(heart.id, "requests", {"instruction": "Make the title shorter", "slide": None}),
        "delete": carol.post_deck(heart.id, "requests/delete", {"id": request_id}),
        "apply": carol.post_deck(heart.id, "review/apply", {"id": "s1"}),
        "read": carol.deck(heart.id, "requests", x_editor="1"),
        "docx": carol.deck(heart.id, "export/docx", x_editor="1"),
    }

    for name, reply in replies.items():
        assert reply.status == 403, name
        assert reply.json() == DENIED, name
        assert not reply.body.startswith(b"PK"), name
    assert "Check the 2026 guideline" not in replies["read"].text
    assert instructions(dan, heart) == [GUIDELINE]
    assert listed(dan, heart)["suggestions"] and len(listed(dan, heart)["suggestions"]) == 1  # type: ignore[arg-type]
    assert heart.path.read_bytes() == before
    assert heart.path.stat().st_size == HEART_FAILURE_BYTES
    assert asked.running.versions(heart) == []


def test_library_requests_nobody_gets_the_docx_export(asked: Asked) -> None:
    """DEC-044: ``/export/docx`` is ``Access denied.`` for a person who can edit too, with or without the header."""
    for header in ({"x_editor": "1"}, {}):
        reply = asked.dan.deck(asked.heart.id, "export/docx", **header)
        assert reply.status == 403
        assert reply.json() == DENIED


def test_library_requests_a_person_who_can_edit_runs_the_whole_request_loop(asked: Asked) -> None:
    """Dan queues, reads back (the revision grows), applies a suggestion, deletes; the record is the presentation's
    own (``<state_dir>/files/<key>/requests``)."""
    heart, dan = asked.heart, asked.dan
    first = listed(dan, heart)

    queued = dan.post_deck(heart.id, "requests", {"instruction": "Add a summary slide", "slide": None})
    applied = dan.post_deck(heart.id, "review/apply", {"id": "s1"})

    assert queued.status == 200
    assert queued.json()["ok"] is True
    assert applied.status == 200
    after = listed(dan, heart)
    assert after["revision"] > first["revision"]  # type: ignore[operator]
    assert instructions(dan, heart)[0] == GUIDELINE
    assert len(instructions(dan, heart)) == 3
    assert RequestStore(asked.running.state_dir).record_dir(heart.path).is_dir()
    carol_read = asked.carol.deck(heart.id, "requests", x_editor="1")
    assert carol_read.status == 403
    first_id = str(after["requests"][0]["id"])  # type: ignore[index]
    assert dan.post_deck(heart.id, "requests/delete", {"id": first_id}).status == 200
    assert GUIDELINE not in instructions(dan, heart)


def test_library_requests_the_status_carries_the_revision_for_an_editor_only(asked: Asked) -> None:
    """DEC-041: the poll's ``requests_revision`` is real for Dan and 0 for Carol."""
    dan = asked.dan.deck(asked.heart.id, "status", x_editor="1").json()
    carol = asked.carol.deck(asked.heart.id, "status", x_editor="1").json()
    assert dan["requests_revision"] > 0
    assert carol["requests_revision"] == 0


def test_library_requests_arch_layout_computes_positions_for_a_person_who_can_edit(asked: Asked) -> None:
    """Dan's ``POST /arch-layout`` rewrites the declarative diagram of the stored deck with computed positions."""
    heart = asked.heart
    heart.path.write_text(SIMPLE_DIAGRAM, encoding="utf-8")
    assert "data-x" not in SIMPLE_DIAGRAM

    reply = asked.dan.post_deck(heart.id, "arch-layout", {})

    assert reply.status == 200
    assert reply.json()["diagrams_updated"] == 1
    assert re.search(r'data-x="\d', heart.path.read_text(encoding="utf-8"))


def test_library_requests_no_route_module_imports_the_docx_export_the_tools_or_the_render() -> None:
    """DEC-044: a grep over ``library/routes_*.py`` and ``server.py`` finds none of the forbidden imports."""
    forbidden = re.compile(r"\b(to_docx|deck\.tools|render|new_file)\b")
    offenders = [
        f"{path.name}: {match}"
        for path in [*ROUTES_DIR.glob("routes_*.py"), ROUTES_DIR / "server.py"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith(("import ", "from "))
        for match in forbidden.findall(line)
    ]
    assert offenders == []
