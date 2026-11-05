"""OpenTelemetry tracing for mcp-htmleditor.

By default spans are written as JSONL to ``<log_dir>/mcp-htmleditor-otel.log``,
one JSON object per finished span, which needs no collector and stays readable.
When ``HTMLEDITOR_OTEL_DESTINATION`` holds an OTLP/HTTP endpoint the spans go
there instead, with ``Authorization: Bearer <HTMLEDITOR_OTEL_API_KEY>`` when the
key is set.

Span names follow ``category.operation``:

    mcp.start_server, mcp.update_start, ...   MCP tool calls
    export.pptx, export.docx                 exports (slide count, charter, duration)
    file.write                               file mutations (path, size)
    tool.pandoc                              pandoc subprocess runs

Never put document content, prompts or credentials in an attribute: only paths,
counts, sizes, durations and charter keys.

:func:`configure_tracing` is idempotent for a given configuration.
:func:`trace_span` works with or without it: without an SDK provider the
OpenTelemetry API returns a no-op tracer, so instrumented code stays free.
"""

from __future__ import annotations

import atexit
import json
import logging
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Span, Status, StatusCode

from .config import APP_NAME, Settings, get_settings
from .textcheck import replace_unencodable
from .version import __version__

logger = logging.getLogger(__name__)

AttributeValue = str | bool | int | float


class JsonlSpanExporter(SpanExporter):
    """Append finished spans to a JSONL file, one JSON object per line."""

    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        """Store the target file and create its parent directory."""
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans: object) -> SpanExportResult:
        """Serialize and append the given spans.

        Args:
            spans: Sequence of finished :class:`ReadableSpan` objects.

        A code point UTF-8 cannot hold (a lone surrogate) is written as its JSON escape (``\\ud800``); every
        other character stays as is.

        Returns:
            SUCCESS, or FAILURE (one warning, no traceback) when the spans cannot be serialized or written.
        """
        try:
            readable: tuple[ReadableSpan, ...] = tuple(spans)  # type: ignore[arg-type] # SDK passes a Sequence
            lines = "".join(f"{json.dumps(span_to_dict(span), ensure_ascii=False)}\n" for span in readable)
            with self._path.open("ab") as stream:
                stream.write(lines.encode("utf-8", "backslashreplace"))
        except Exception as exc:
            _warn_export_failed(self._path, exc)
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30_000) -> bool:  # noqa: ARG002 - writes are synchronous
        """Return True: every export already hit the disk."""
        return True

    def shutdown(self) -> None:
        """No resource is held open between exports."""


class EncodableSpanExporter(SpanExporter):
    """Hand spans to a delegate with every unencodable code point replaced by U+FFFD.

    The OTLP encoder raises on a lone surrogate and drops the attribute; the copy it receives holds text it can
    encode. A failure of the delegate is one warning, never a traceback.
    """

    __slots__ = ("_delegate",)

    def __init__(self, delegate: SpanExporter) -> None:
        """Wrap ``delegate``."""
        self._delegate = delegate

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export encodable copies of ``spans`` through the delegate.

        Returns:
            The delegate's result, or FAILURE when anything raised.
        """
        try:
            return self._delegate.export([_encodable_copy(span) for span in spans])
        except Exception as exc:
            _warn_export_failed(type(self._delegate).__name__, exc)
            return SpanExportResult.FAILURE

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        """Flush the delegate."""
        return self._delegate.force_flush(timeout_millis)

    def shutdown(self) -> None:
        """Shut the delegate down."""
        self._delegate.shutdown()


def span_to_dict(span: ReadableSpan) -> dict[str, Any]:
    """Convert a finished span into a JSON serializable dict.

    Args:
        span: The finished span.

    Returns:
        A dict with the identifiers, timing, status and attributes of the span.
    """
    context = span.get_span_context()
    start = span.start_time or 0
    end = span.end_time or start
    return {
        "name": span.name,
        "trace_id": f"{context.trace_id:032x}" if context is not None else None,
        "span_id": f"{context.span_id:016x}" if context is not None else None,
        "parent_id": f"{span.parent.span_id:016x}" if span.parent is not None else None,
        "start_time": _isoformat(start),
        "end_time": _isoformat(end),
        "duration_ms": round((end - start) / 1_000_000, 3),
        "status": span.status.status_code.name,
        "service": APP_NAME,
        "version": __version__,
        "attributes": dict(span.attributes or {}),
    }


def configure_tracing(settings: Settings | None = None) -> None:
    """Install the tracer provider for the current configuration.

    Idempotent: a second call with the same destination does nothing.

    Args:
        settings: Injected settings; resolved from the environment when omitted.
    """
    resolved = settings if settings is not None else get_settings()
    _install_provider(resolved.otel_destination, resolved.otel_api_key, str(resolved.otel_log_file))


@contextmanager
def trace_span(name: str, attributes: Mapping[str, AttributeValue] | None = None) -> Iterator[Span]:
    """Run a block inside a span named ``category.operation``.

    Exceptions are recorded on the span and re-raised untouched.

    Args:
        name: Span name, ``category.operation`` (for example ``export.pptx``).
        attributes: Initial attributes; never credentials or document content.

    Yields:
        The active span, so the caller can add attributes once they are known.
    """
    tracer = trace.get_tracer(APP_NAME, __version__)
    with tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise


@lru_cache(maxsize=4)
def _install_provider(destination: str | None, api_key: str | None, jsonl_path: str) -> None:
    """Create and register the tracer provider (memoized on its arguments)."""
    resource = Resource.create({"service.name": APP_NAME, "service.version": __version__})
    provider = TracerProvider(resource=resource)
    if destination:
        provider.add_span_processor(BatchSpanProcessor(_otlp_exporter(destination, api_key)))
    else:
        provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(Path(jsonl_path))))
    trace.set_tracer_provider(provider)
    atexit.register(provider.shutdown)
    logger.debug("Tracing configured (destination=%s)", destination or jsonl_path)


def _otlp_exporter(destination: str, api_key: str | None) -> SpanExporter:
    """Return the OTLP/HTTP exporter, falling back to a no-op on import error."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    return EncodableSpanExporter(OTLPSpanExporter(endpoint=destination, headers=headers))


def _warn_export_failed(destination: object, exc: Exception) -> None:
    """Log one warning line for a failed export: no traceback, message made encodable."""
    logger.warning("Span export failed (%s): %s: %s", destination, type(exc).__name__, replace_unencodable(str(exc)))


def _encodable_copy(span: ReadableSpan) -> ReadableSpan:
    """Return a copy of ``span`` whose text fields pass through :func:`replace_unencodable`."""
    status = span.status
    return ReadableSpan(
        name=replace_unencodable(span.name),
        context=span.get_span_context(),
        parent=span.parent,
        resource=span.resource,
        attributes=_encodable_attributes(span.attributes),
        events=[
            Event(replace_unencodable(event.name), _encodable_attributes(event.attributes), event.timestamp)
            for event in span.events
        ],
        links=span.links,
        kind=span.kind,
        instrumentation_info=span.instrumentation_info,
        status=Status(
            status.status_code, replace_unencodable(status.description) if status.description else status.description
        ),
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


def _encodable_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return ``attributes`` with every string, and every string in a sequence, made encodable."""
    return {replace_unencodable(key): _encodable_value(value) for key, value in (attributes or {}).items()}


def _encodable_value(value: Any) -> Any:
    if isinstance(value, str):
        return replace_unencodable(value)
    if isinstance(value, tuple | list):
        return tuple(_encodable_value(item) for item in value)
    return value


def _isoformat(timestamp_ns: int) -> str:
    """Format an OpenTelemetry nanosecond timestamp as UTC ISO 8601."""
    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=UTC).isoformat()
