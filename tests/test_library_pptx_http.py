"""US-0140: the PPTX and HTML downloads of the library (SPEC-0025, DEC-040, DEC-042, DEC-043, DEC-044).

Spec tests: E2E-031, E2E-SEC-012, E2E-SEC-022. The second channel of every exploit is a loopback listener that counts
connections, the media parts of the delivered PPTX and the bytes the visitor received.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation as PptxPresentation

from tests import library_support
from tests.library_support import (
    CARDIOLOGY,
    CAROL,
    DAN,
    HEART_FAILURE,
    Browser,
    FakeGoogle,
    Presentation,
    RecordingListener,
    RunningLibrary,
    signed_in,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
evil_listener = library_support.evil_listener
START = Callable[..., RunningLibrary]

MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
HEART_FAILURE_BYTES = 2_097_152
SECRET_SIZE = (7, 5)  # no picture of the library or of the exporter has this size
DENIED = {"error": "Access denied.", "code": "denied"}


@dataclass(frozen=True)
class Download:
    running: RunningLibrary
    ids: dict[str, str]
    heart: Presentation
    carol: Browser


@pytest.fixture
def download(library_server: START, fake_google: FakeGoogle) -> Download:
    running = library_server(fake_google)
    ids = running.builder.standard()
    heart = running.builder.presentation(
        ids[CARDIOLOGY], HEART_FAILURE, size=HEART_FAILURE_BYTES, modified=MODIFIED, slides=8
    )
    carol = signed_in(running, fake_google, CAROL)
    carol.open_presentation(heart.id)
    return Download(running, ids, heart, carol)


def secret_picture() -> bytes:
    """A real PNG of ``SECRET_SIZE`` pixels: re-encoding by the exporter keeps its size, not trailing bytes."""
    buffer = io.BytesIO()
    Image.new("RGB", SECRET_SIZE, (255, 0, 128)).save(buffer, "PNG")
    return buffer.getvalue()


def media_sizes(body: bytes) -> list[tuple[int, int]]:
    """The pixel size of every picture in the media parts of a PPTX."""
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        return [
            Image.open(io.BytesIO(archive.read(name))).size
            for name in archive.namelist()
            if name.startswith("ppt/media/")
        ]


def test_e2e_031_a_ro_member_downloads_the_html_and_the_pptx(download: Download) -> None:
    """E2E-031: the HTML is the stored file byte for byte under its own name; the PPTX has 8 slides; nothing changes."""
    heart = download.heart
    before = heart.path.read_bytes()

    html = download.carol.deck(heart.id, "download", x_editor="1")
    pptx = download.carol.deck(heart.id, "export/pptx", x_editor="1")

    assert html.status == 200
    assert html.body == before
    assert len(html.body) == HEART_FAILURE_BYTES
    assert "Heart%20Failure%20Update.html" in html.headers["content-disposition"]
    assert pptx.status == 200
    assert pptx.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.presentationml")
    assert "Heart%20Failure%20Update.pptx" in pptx.headers["content-disposition"]
    assert len(PptxPresentation(io.BytesIO(pptx.body)).slides) == 8
    assert heart.path.read_bytes() == before
    assert download.running.versions(heart) == []


def test_library_pptx_the_docx_export_is_refused_to_everyone(download: Download, fake_google: FakeGoogle) -> None:
    dan = signed_in(download.running, fake_google, DAN)
    dan.open_presentation(download.heart.id)
    for person in (download.carol, dan):
        reply = person.deck(download.heart.id, "export/docx", x_editor="1")
        assert reply.status == 403
        assert reply.json() == DENIED
        assert not reply.body.startswith(b"PK")


def test_e2e_sec_012_a_visitor_without_a_session_cannot_download(download: Download) -> None:
    """E2E-SEC-012. Red before the fix because: a naive build that serves the stored file to anyone knowing the
    address fails "the visitor's download folder holds no file": it holds Heart Failure Update.html."""
    visitor = download.running.browser()
    received = b""

    for route in ("download", "export/pptx"):
        reply = visitor.deck(download.heart.id, route)
        received += reply.body
        assert reply.status == 302, route
        assert reply.headers["location"] == f"{download.running.origin}/open/{download.heart.id}"
        assert "content-disposition" not in reply.headers
    for route in ("download", "export/pptx"):
        coded = visitor.deck(download.heart.id, route, x_editor="1")
        received += coded.body
        assert coded.status == 401
        assert "content-disposition" not in coded.headers

    assert b"Heart Failure Update" not in received
    assert not received.startswith(b"PK")
    assert len(download.running.stored.rows("SELECT id FROM presentations")) == 1


def test_e2e_sec_022_a_presentations_script_reaches_the_machine_while_its_pptx_is_built(
    download: Download, evil_listener: RecordingListener
) -> None:
    """E2E-SEC-022. Red before the fix because: the PPTX is built from files outside the folder; the assertion "the
    PPTX holds no picture equal to secret.png" fails because the delivered PPTX contains secret.png."""
    library_dir = download.running.library_dir
    secret = library_dir / "files" / "secret.png"  # what ``../secret.png`` reaches from a folder of the library
    secret.write_bytes(secret_picture())
    outside = download.running.state_dir.parent / "secret.png"
    outside.write_bytes(secret_picture())
    script = f"<script>new WebSocket('ws://127.0.0.1:{evil_listener.port}/probe');</script>"
    pictures = f'<img src="{outside.as_uri()}" alt="a"><img src="../secret.png" alt="b">'
    deck = (
        '<!DOCTYPE html><html data-doc-type="presentation"><body>'
        f'<section class="slide" data-type="slide" data-id="s1" data-title="One"><h1>Heart Failure Update</h1>'
        f"{pictures}{script}</section></body></html>"
    )
    download.heart.path.write_text(deck, encoding="utf-8")

    reply = download.carol.deck(download.heart.id, "export/pptx", x_editor="1")

    assert "secret.png" in deck  # the pictures are really in the stored deck
    assert reply.status == 200
    assert len(PptxPresentation(io.BytesIO(reply.body)).slides) >= 1
    assert evil_listener.visits == []
    assert SECRET_SIZE not in media_sizes(reply.body)


def test_library_pptx_a_failed_build_gives_the_reason_without_a_path(
    download: Download, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-042: the answer is the operating system reason, never the text of the exception, a path or a file name."""

    def broken(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError(2, "No such file or directory", str(download.heart.path))

    monkeypatch.setattr("mcp_htmleditor.export.to_pptx.to_pptx", broken)
    reply = download.carol.deck(download.heart.id, "export/pptx", x_editor="1")

    assert reply.status == 500
    assert reply.json() == {"error": "No such file or directory"}
    assert str(download.running.library_dir) not in reply.text
    assert Path(download.heart.path).name not in reply.text
