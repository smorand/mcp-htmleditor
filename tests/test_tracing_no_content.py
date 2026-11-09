"""SPEC-0019 DT-030 (DR-008, SPEC-0001 FR-023, E2E-036): spans carry no document content.

One child traced editor server saves a document holding a marker text and exports it; the marker must not appear in
any line of the local trace file (span names and attributes). The application log is out of FR-023's scope.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tests.deck_support import deck_ei, inject_html, write_deck
from tests.trace_support import run_traced_server

MARKER_TEXT = "SECRET-7f3a9c"
MARKER_TITLE = "SECRET-TITLE-7f3a9c"


def test_a_traced_save_and_export_write_none_of_the_document_text_into_spans(tmp_path: Path) -> None:
    served = tmp_path / "deck.html"
    write_deck(served, deck_ei())
    html = inject_html(deck_ei(), 2, f"<p>{MARKER_TEXT}</p>")
    html = re.sub(r"<title>.*?</title>", f"<title>{MARKER_TITLE}</title>", html, count=1, flags=re.DOTALL)
    assert MARKER_TEXT in html and MARKER_TITLE in html
    body = json.dumps({"html": html}).encode()
    save = (
        b"POST /content HTTP/1.1\r\nHost: 127.0.0.1:%PORT%\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )
    export = b"GET /export/pptx HTTP/1.1\r\nHost: 127.0.0.1:%PORT%\r\n\r\n"

    run = run_traced_server(tmp_path, served, [save, export])

    assert run.data == [200, 200]
    assert run.trace_lines, "no span was written: the guard would pass for nothing"
    leaking = [line for line in run.trace_lines if MARKER_TEXT in line or MARKER_TITLE in line]
    assert leaking == []
