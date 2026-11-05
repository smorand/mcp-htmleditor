"""SPEC-0013 US-0075 (BUG-005, BR-019): tracing and logging never break on text UTF-8 cannot hold.

A tool argument such as ``"\\ud800"`` becomes a span attribute. The local trace file must keep the span with the
code point written as its JSON escape; an OTLP destination receives U+FFFD in its place; an export failure is one
warning line, never a traceback. The end to end tests run in a child interpreter (``tests/trace_support.py``).
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from collections.abc import Iterator, Sequence
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

from mcp_htmleditor import tracing
from mcp_htmleditor.config import Settings
from mcp_htmleditor.logging_config import setup_logging
from mcp_htmleditor.tracing import EncodableSpanExporter, JsonlSpanExporter
from tests.deck_support import BOOTSTRAP
from tests.trace_support import run_traced_server, run_traced_tool

LONE = "\ud800"
ESCAPE = "\\ud800"
FORBIDDEN = ("Traceback", "Logging error", "Exception while exporting")


@pytest.fixture(name="deck")
def _deck(tmp_path: Path) -> Path:
    path = tmp_path / "deck.html"
    shutil.copy(BOOTSTRAP / "slides-empty.html", path)
    return path


def _assert_quiet(*texts: str) -> None:
    for text in texts:
        for word in FORBIDDEN:
            assert word not in text


def test_bt034_unencodable_tool_argument_keeps_its_span_and_logs_no_traceback(tmp_path: Path, deck: Path) -> None:
    run = run_traced_tool(tmp_path, "get_slide", {"file": str(deck), "id": LONE})

    assert run.ok is False
    assert run.data == f'Unknown slide id "{LONE}". Valid ids: slide-0'
    lines = [line for line in run.trace_lines if json.loads(line)["name"] == "mcp.get_slide"]
    assert len(lines) == 1
    assert ESCAPE in lines[0]
    assert json.loads(lines[0])["attributes"]["slide.id"] == LONE
    _assert_quiet(run.stderr, run.log_text)


class _Collector(BaseHTTPRequestHandler):
    bodies: list[bytes]

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.server.bodies.append(self.rfile.read(length))  # type: ignore[attr-defined] # recorded on our server
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - signature of the base class
        """Keep the test output quiet."""


@pytest.fixture
def collector() -> Iterator[HTTPServer]:
    server = HTTPServer(("127.0.0.1", 0), _Collector)
    server.bodies = []  # type: ignore[attr-defined] # read back by the test
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def test_bt038_otlp_export_keeps_the_span_with_the_replacement_character(
    tmp_path: Path, deck: Path, collector: HTTPServer
) -> None:
    destination = f"http://127.0.0.1:{collector.server_port}/v1/traces"
    run = run_traced_tool(
        tmp_path,
        "get_slide",
        {"file": str(deck), "id": LONE},
        env={"HTMLEDITOR_OTEL_DESTINATION": destination},
    )

    assert run.ok is False
    assert run.data == f'Unknown slide id "{LONE}". Valid ids: slide-0'
    spans = []
    for body in collector.bodies:  # type: ignore[attr-defined]
        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        spans += [s for rs in request.resource_spans for ss in rs.scope_spans for s in ss.spans]
    slide = [s for s in spans if s.name == "mcp.get_slide"]
    assert len(slide) == 1
    values = {a.key: a.value.string_value for a in slide[0].attributes}
    assert values["slide.id"] == "\ufffd"
    _assert_quiet(run.stderr, run.log_text)


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("get_skill", {"type": LONE}, 'Unknown skill topic "'),
        ("new_file", {"template": LONE, "file": "{tmp}/n.html"}, 'Unknown template "'),
        ("export", {"file": "{deck}", "format": LONE, "output": "{tmp}/o.pptx"}, 'Unknown export format "'),
        ("restore", {"file": "{deck}", "id": LONE}, 'Unknown history id "'),
    ],
)
def test_bt039_every_argument_that_becomes_an_attribute_keeps_its_span(
    tmp_path: Path, deck: Path, tool: str, arguments: dict[str, str], message: str
) -> None:
    resolved = {key: value.format(tmp=tmp_path, deck=deck) for key, value in arguments.items()}
    run = run_traced_tool(tmp_path, tool, resolved)

    assert run.ok is False
    assert str(run.data).startswith(message)
    assert [line for line in run.trace_lines if f'"name": "mcp.{tool}"' in line and ESCAPE in line]
    _assert_quiet(run.stderr, run.log_text)
    assert not (tmp_path / "n.html").exists()
    assert not (tmp_path / "o.pptx").exists()


def test_bt048_editor_server_writes_its_spans_for_a_non_ascii_served_path(tmp_path: Path, deck: Path) -> None:
    served = tmp_path / "Présentation été 😀.html"
    shutil.copy(deck, served)
    body = b'{"html":"<!DOCTYPE html><html><body><p>X</p></body></html>"}'
    save = (
        b"POST /content HTTP/1.1\r\nHost: 127.0.0.1:%PORT%\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )
    export = b"GET /export/pptx HTTP/1.1\r\nHost: 127.0.0.1:%PORT%\r\n\r\n"

    run = run_traced_server(tmp_path, served, [save, export])

    assert run.data == [200, 200]
    spans = [json.loads(line) for line in run.trace_lines]
    for name in ("file.write", "export.pptx"):
        # a save also writes history files, whose spans carry other paths: look for the served one
        matching = [s for s in spans if s["name"] == name and s["attributes"].get("file.path") == str(served)]
        assert matching, name  # export.pptx also opens an inner span in export/to_pptx
    _assert_quiet(run.stderr, run.log_text)


# ---------------------------------------------------------------------------
# Unit tests of the two exporters and of the log file handler
# ---------------------------------------------------------------------------


class _RecordingExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.spans += spans
        return SpanExportResult.SUCCESS


class _RaisingExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        raise RuntimeError("collector down \ud800")


def _provider_with(exporter: SpanExporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider


def test_jsonl_exporter_escapes_the_lone_surrogate_and_keeps_valid_text(tmp_path: Path) -> None:
    target = tmp_path / "spans.jsonl"
    provider = _provider_with(JsonlSpanExporter(target))
    with provider.get_tracer("t").start_as_current_span("mcp.x") as span:
        span.set_attribute("x", "x\ud800é")

    raw = target.read_bytes()
    assert b"\\ud800" in raw
    assert "é".encode() in raw
    assert json.loads(raw.decode("utf-8"))["attributes"]["x"] == "x\ud800é"


def test_jsonl_exporter_failure_is_one_warning_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(span: ReadableSpan) -> dict[str, object]:
        raise ValueError("cannot write")

    span = _finished_span()
    monkeypatch.setattr(tracing, "span_to_dict", boom)
    exporter = JsonlSpanExporter(tmp_path / "spans.jsonl")

    with caplog.at_level(logging.DEBUG, logger="mcp_htmleditor.tracing"):
        result = exporter.export([span])

    assert result is SpanExportResult.FAILURE
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].exc_info is None


def _finished_span() -> ReadableSpan:
    recorder = _RecordingExporter()
    provider = _provider_with(recorder)
    with provider.get_tracer("t").start_as_current_span("mcp.z"):
        pass
    return recorder.spans[0]


def test_encodable_exporter_replaces_unencodable_text_before_the_delegate() -> None:
    recorder = _RecordingExporter()
    provider = _provider_with(EncodableSpanExporter(recorder))
    with provider.get_tracer("t").start_as_current_span("mcp.n\ud800") as span:
        span.set_attribute("a", "a\ud800")
        span.set_attribute("seq", ["ok", "b\ud800"])
        span.add_event("ev\ud800", {"k": "v\ud800"})
        span.set_status(Status(StatusCode.ERROR, "d\ud800"))

    (sent,) = recorder.spans
    assert sent.name == "mcp.n\ufffd"
    assert sent.attributes is not None
    assert sent.attributes["a"] == "a\ufffd"
    assert tuple(sent.attributes["seq"]) == ("ok", "b\ufffd")  # type: ignore[arg-type] # a sequence attribute
    assert sent.events[0].name == "ev\ufffd"
    assert sent.events[0].attributes is not None
    assert sent.events[0].attributes["k"] == "v\ufffd"
    assert sent.status.description == "d\ufffd"


def test_encodable_exporter_turns_a_delegate_error_into_one_warning(caplog: pytest.LogCaptureFixture) -> None:
    exporter = EncodableSpanExporter(_RaisingExporter())
    span = _finished_span()

    with caplog.at_level(logging.DEBUG, logger="mcp_htmleditor.tracing"):
        result = exporter.export([span])

    assert result is SpanExportResult.FAILURE
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].exc_info is None
    assert warnings[0].getMessage().startswith("Span export failed (")
    assert "RuntimeError: collector down \ufffd" in warnings[0].getMessage()


def test_encodable_exporter_delegates_shutdown_and_flush() -> None:
    class Delegate(_RecordingExporter):
        closed = False

        def shutdown(self) -> None:
            self.closed = True

        def force_flush(self, timeout_millis: int = 30_000) -> bool:
            return False

    delegate = Delegate()
    exporter = EncodableSpanExporter(delegate)

    assert exporter.force_flush() is False
    exporter.shutdown()
    assert delegate.closed is True


def test_log_file_handler_survives_a_lone_surrogate(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    root = logging.getLogger()
    saved, level = root.handlers[:], root.level
    root.handlers = []
    try:
        log_file = setup_logging(settings=Settings(log_dir_override=tmp_path))
        logging.getLogger("mcp_htmleditor.test").warning("bad id %s", LONE)
        for handler in root.handlers:
            handler.flush()
        assert log_file is not None
        assert "bad id \\ud800" in log_file.read_bytes().decode("utf-8")
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = saved
        root.setLevel(level)

    assert "Logging error" not in capfd.readouterr().err
