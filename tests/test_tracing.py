"""Tests for OpenTelemetry wiring (mcp_htmleditor.tracing).

``trace.set_tracer_provider`` accepts a single call per process, so the tests that
need the global tracer share one session scoped configuration; the exporter and
the span serializer are exercised on their own local provider.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult

from mcp_htmleditor.config import Settings
from mcp_htmleditor.tracing import (
    JsonlSpanExporter,
    configure_tracing,
    span_to_dict,
    trace_span,
)


@pytest.fixture(scope="session")
def global_span_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Configure the process wide tracer once and return its JSONL file."""
    log_dir = tmp_path_factory.mktemp("otel-global")
    settings = Settings(log_dir_override=log_dir)
    configure_tracing(settings)
    configure_tracing(settings)  # idempotent: memoized on the destination
    return log_dir / "mcp-htmleditor-otel.log"


@pytest.fixture
def local_tracer(tmp_path: Path) -> Iterator[tuple[TracerProvider, Path]]:
    """Return an isolated provider exporting to a JSONL file in tmp_path."""
    target = tmp_path / "spans.jsonl"
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(target)))
    yield provider, target
    provider.shutdown()


def _spans(path: Path) -> list[dict]:
    """Read back every span written to a JSONL file."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_span_is_written_as_one_json_object(local_tracer: tuple[TracerProvider, Path]) -> None:
    """A finished span becomes one JSON line with its attributes."""
    provider, target = local_tracer
    with provider.get_tracer("test").start_as_current_span("export.pptx") as span:
        span.set_attribute("slide.count", 9)

    written = _spans(target)
    assert len(written) == 1
    assert written[0]["name"] == "export.pptx"
    assert written[0]["attributes"]["slide.count"] == 9
    assert written[0]["service"] == "mcp-htmleditor"
    assert written[0]["duration_ms"] >= 0
    assert written[0]["parent_id"] is None


def test_nested_spans_share_the_trace(local_tracer: tuple[TracerProvider, Path]) -> None:
    """A child span records its parent, so an export shows its pandoc call."""
    provider, target = local_tracer
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("export.docx"), tracer.start_as_current_span("tool.pandoc"):
        pass

    child, parent = _spans(target)
    assert child["name"] == "tool.pandoc"
    assert parent["name"] == "export.docx"
    assert child["parent_id"] == parent["span_id"]
    assert child["trace_id"] == parent["trace_id"]


def test_span_to_dict_handles_a_span_without_end(local_tracer: tuple[TracerProvider, Path]) -> None:
    """A span read before it ends reports a zero duration instead of failing."""
    provider, _ = local_tracer
    span = provider.get_tracer("test").start_span("file.write")
    try:
        payload = span_to_dict(span)
    finally:
        span.end()

    assert payload["name"] == "file.write"
    assert payload["duration_ms"] >= 0
    assert payload["start_time"].endswith("+00:00")


def test_exporter_reports_failure_on_unwritable_path(tmp_path: Path) -> None:
    """An unwritable target yields FAILURE instead of raising."""
    target = tmp_path / "spans.jsonl"
    exporter = JsonlSpanExporter(target)
    target.mkdir()  # a directory cannot be appended to

    assert exporter.export([]) is SpanExportResult.FAILURE
    assert exporter.force_flush() is True
    exporter.shutdown()


def test_configure_tracing_exports_spans(global_span_file: Path) -> None:
    """A traced block lands in the JSONL file with its attributes."""
    with trace_span("export.pptx", {"slide.count": 3}) as span:
        span.set_attribute("warning.count", 0)

    written = _spans(global_span_file)
    matching = [entry for entry in written if entry["attributes"].get("slide.count") == 3]
    assert matching
    assert matching[0]["name"] == "export.pptx"
    assert matching[0]["attributes"]["warning.count"] == 0
    assert matching[0]["status"] == "UNSET"


def test_configure_tracing_does_not_duplicate_processors(global_span_file: Path) -> None:
    """A second configure_tracing must not export each span twice."""
    configure_tracing(Settings(log_dir_override=global_span_file.parent))
    before = len(_spans(global_span_file))

    with trace_span("file.write", {"file.size": 12}):
        pass

    assert len(_spans(global_span_file)) == before + 1


def test_trace_span_records_exceptions(global_span_file: Path) -> None:
    """An exception is recorded on the span and re-raised untouched."""
    with pytest.raises(ValueError, match="boom"), trace_span("tool.pandoc", {"tool.operation": "boom-test"}):
        raise ValueError("boom")

    written = _spans(global_span_file)
    matching = [entry for entry in written if entry["attributes"].get("tool.operation") == "boom-test"]
    assert matching
    assert matching[0]["status"] == "ERROR"
