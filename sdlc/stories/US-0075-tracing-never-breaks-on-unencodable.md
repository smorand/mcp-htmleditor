# US-0075: Tracing and logging never break on unencodable text

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P2
> Depends on: US-0073
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

A tool argument holding a lone surrogate (`get_slide(id="\ud800")`) gives the right tool error, but its span is
lost and `Exception while exporting Span.` plus a `--- Logging error ---` block are written with a traceback;
with an OTLP destination the encoder logs `Failed to encode key ...` and drops the attribute (BUG-005). This
story makes the trace exporters and the log file handler never raise: the span is written with the code point
escaped (local file) or replaced by U+FFFD (OTLP), and no traceback is printed.

## Requirements covered

- SPEC-0013/BR-019 (partial: the exporters, the log file and the editor server spans; the path argument spans are checked in US-0077): The agent tools, the commands and the editor server SHALL NOT change their answer, drop a span, or write a traceback to standard error or to a log, because a span attribute holds text that cannot be encoded.

Business rules (spec): in the local trace file the span is written as one line of valid UTF-8 JSON where each
unencodable code point appears as its JSON escape (`\ud800`, six ASCII characters). With an OTLP destination the
span is sent with that attribute's value holding U+FFFD in place of each unencodable code point. A trace export
failure of any kind is at most one warning line, never a traceback. In the editor server the only text attribute
is the served file path (spans `file.write`, `export.pptx`, `export.docx`, `mcp.layout_arch_diagram`,
`history.restore`); any valid Unicode of the path is kept as is.

## Independent Test

`make test ARGS='-k tracing_unencodable'`: a subprocess with the local trace file under `tmp_path` calls
`get_slide(file=<deck.html>, id="\ud800")`; the tool error is `Unknown slide id "\ud800". Valid ids: slide-0`, the
trace file read as strict UTF-8 gains one `mcp.get_slide` line whose raw text contains the six characters
`\ud800`, and stderr holds no `Traceback` and no `Logging error` (red today: line missing, traceback).

## Design excerpt

### Decisions
- DEC-006 (SPEC-0013): "`JsonlSpanExporter.export` builds the lines with `json.dumps(..., ensure_ascii=False)` as today, encodes them with `encode("utf-8", "backslashreplace")` and appends bytes (file opened `"ab"`); it catches `Exception` (not only `OSError`), logs one WARNING without `exc_info` and returns `FAILURE`." A lone surrogate can only sit inside a JSON string, where Python's backslash escape of U+D800 is exactly the JSON escape `\ud800` (`"\ud800".encode("utf-8", "backslashreplace") == b"\\ud800"`); valid characters stay unescaped as today.
- DEC-007 (SPEC-0013): "`_otlp_exporter` returns `EncodableSpanExporter(OTLPSpanExporter(...))`, a `SpanExporter` that maps each span to a copy whose name, attributes, event names, event attributes and status description pass through `replace_unencodable` (strings inside sequences too), then delegates; it catches `Exception` from the delegate, logs one WARNING without `exc_info`, returns `FAILURE`. `shutdown` and `force_flush` delegate." The copy uses the SDK `ReadableSpan` constructor (opentelemetry-sdk 1.44.0, `uv.lock:1294`).
- DEC-008 (SPEC-0013): "The rotating log file handler is created with `errors="backslashreplace"`." A log line formatting a tool error message that holds a lone surrogate would otherwise print `--- Logging error ---`; stderr already uses `backslashreplace` by Python default.
- DEC-016 (SPEC-0013): "Trace assertions run in a subprocess (`tests/trace_support.py`: `sys.executable -c` with `PYTHONPATH=src`, `HTMLEDITOR_LOG_DIR`, `HTMLEDITOR_STATE_DIR`, `HTMLEDITOR_CACHE_DIR` under `tmp_path`, optional `HTMLEDITOR_OTEL_DESTINATION`), which calls `configure_tracing()`, runs the tool through an in process `fastmcp.Client`, flushes the provider and prints the tool outcome as JSON." The OpenTelemetry provider is process global and settable once; `tests/test_tracing.py:27` owns the in process one.

### Contracts
```python
# src/mcp_htmleditor/tracing.py
class JsonlSpanExporter(SpanExporter):          # export(): bytes with backslashreplace, any Exception -> one WARNING, FAILURE
class EncodableSpanExporter(SpanExporter):       # new; wraps the OTLP exporter
    def __init__(self, delegate: SpanExporter) -> None: ...
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult: ...
    def shutdown(self) -> None: ...
    def force_flush(self, timeout_millis: int = 30_000) -> bool: ...
def _otlp_exporter(destination: str, api_key: str | None) -> SpanExporter   # returns EncodableSpanExporter(OTLPSpanExporter(...))
```
Warning line of an export failure, exact form: `Span export failed (<destination>): <ExcType>: <message>` with the
message passed through `replace_unencodable`, never `exc_info`.
`replace_unencodable` comes from `src/mcp_htmleditor/textcheck.py` (US-0073).

```python
# tests/trace_support.py (new)
@dataclass(frozen=True)
class TracedRun:
    ok: bool  # tool outcome: True with data, False with the tool error text
    data: Any
    stdout: str
    stderr: str
    trace_lines: list[str]  # the local trace file read as strict UTF-8, split in lines ([] with OTLP)


def run_traced_tool(
    tmp_path: Path, tool: str, arguments: dict[str, Any], *, env: dict[str, str] | None = None
) -> TracedRun: ...
def run_traced_server(
    tmp_path: Path, served: Path, raw_requests: list[bytes]
) -> TracedRun: ...  # starts the editor server in the subprocess (BT-048)
```
Arguments holding lone surrogates are passed to the subprocess as JSON with `ensure_ascii=True` (escapes survive).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/tracing.py` | modify: `JsonlSpanExporter.export`, `EncodableSpanExporter`, `_otlp_exporter` |
| `src/mcp_htmleditor/logging_config.py` | modify: `RotatingFileHandler(..., errors="backslashreplace")` (`logging_config.py:112`) |
| `tests/trace_support.py` | create |
| `tests/test_tracing_unencodable.py` | create |
| `.agent_docs/observability.md` | modify: how unencodable attribute text is written (escape in JSONL, U+FFFD in OTLP), export failures are one warning |

### Existing patterns
- `src/mcp_htmleditor/tracing.py:55` `JsonlSpanExporter`, `:92` `span_to_dict`, `:157` `_install_provider`, `:170` `_otlp_exporter`.
- `tests/test_tracing.py:37` `local_tracer` (in process exporter tests, for the unit tests of the two exporters); `tests/test_tracing.py:97` failure test pattern.
- Subprocess with its own environment: `tests/test_requests_core.py` UT-A02 (`subprocess.run([sys.executable, "-c", script])`, `PYTHONPATH=src`).
- Tool call through `fastmcp.Client`: `tests/deck_support.py:252` `call_tool`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Conventions: `deck.html` is a copy of the `carbon` slide bootstrap (one slide, id `slide-0`). Agent tool tests
set `HTMLEDITOR_STATE_DIR`, the log and cache folders to `tmp_path`. Location `tests/test_tracing_unencodable.py`.

### SPEC-0013/BT-034: An unencodable tool argument keeps its span and logs no traceback
- Reproduces BUG-005 (also validates BR-019). Driver: the agent tool `get_slide` through the in process client, local trace file under `tmp_path` (no `HTMLEDITOR_OTEL_DESTINATION`). Red before because: the trace file writer raises on the attribute and the processor logs the traceback.
- When `get_slide(file="<deck.html>", id="\ud800")`
- Then a tool error is raised whose message equals `Unknown slide id "\ud800". Valid ids: slide-0`
- And the trace file read as strict UTF-8 holds one more line, a JSON object with `name` `mcp.get_slide` whose raw text contains the six characters `\ud800`, and captured standard error and logs hold no `Traceback` and no `Logging error`

### SPEC-0013/BT-038: OTLP export keeps the span and logs no traceback
- Driver: agent tool `get_slide` in the subprocess; `HTMLEDITOR_OTEL_DESTINATION` set to a test HTTP listener on `127.0.0.1` that records every request body and answers `200`. Red before because: the encoder logs `Failed to encode key slide.id` with a traceback and drops the attribute.
- When `get_slide(file="<deck.html>", id="\ud800")` and the tracer provider is flushed
- Then the tool error message equals `Unknown slide id "\ud800". Valid ids: slide-0`
- And the listener received a span named `mcp.get_slide` whose `slide.id` attribute is the string U+FFFD (decode the body with `opentelemetry.proto.collector.trace.v1.trace_service_pb2.ExportTraceServiceRequest`, already installed with the OTLP exporter), and the captured logs hold no `Traceback`

### SPEC-0013/BT-039: Every argument that becomes a span attribute keeps its span
- Driver: agent tools in the subprocess, local trace file under `tmp_path`. Red before: each span is lost and a traceback logged.
- When, parametrized: `get_skill(type="\ud800")` (`skill.topic`); `new_file(template="\ud800", file="<tmp_path>/n.html")` (`template.key`); `export(file="<deck.html>", format="\ud800", output="<tmp_path>/o.pptx")` (`export.format`); `restore(file="<deck.html>", id="\ud800")` (`history.id`)
- Then each raises its usual tool error, whose message starts, in turn, `Unknown skill topic "`, `Unknown template "`, `Unknown export format "`, `Unknown history id "`
- And the trace file read as strict UTF-8 gains one line per call whose raw text contains the six characters `\ud800`, captured logs hold no `Traceback`, and `tmp_path` holds no `n.html` nor `o.pptx`

### SPEC-0013/BT-048: The editor server writes its spans for a non ASCII served path
- Protects BR-019 (editor server), BR-018. Driver: real editor server serving `<tmp_path>/Présentation été 😀.html` (a copy of `deck.html`), local trace file under `tmp_path`; raw TCP socket.
- When a valid save `{"html":"<!DOCTYPE html><html><body><p>X</p></body></html>"}` and then `GET /export/pptx` are sent with `Host: L`
- Then both answer `200`
- And the trace file, read as strict UTF-8, gains one line for the span `file.write` and one for `export.pptx`, each a JSON object whose `file.path` attribute equals the served path, and the captured standard error and logs hold no `Traceback` and no `Logging error`

### Unit tests of this story (Location `tests/test_tracing_unencodable.py`)
- `JsonlSpanExporter` on a span with attribute `"x\ud800é"` writes one line whose bytes contain `\\ud800` and the UTF-8 bytes of `é`, and returns `SUCCESS`; when the delegate write raises `ValueError`, it returns `FAILURE` and logs exactly one WARNING without `exc_info`.
- `EncodableSpanExporter` with a recording fake delegate passes a span whose attribute `"a\ud800"` became `"a�"` and an event attribute likewise; a delegate raising `RuntimeError` gives `FAILURE` and one WARNING without `exc_info`.
- A log record formatted with `"\ud800"` written through the file handler of `setup_logging` produces no `--- Logging error ---` on stderr (`capfd`).

## Constraints

- Files not to touch: `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/cli.py`, `src/mcp_htmleditor/textcheck.py`, `tests/test_tracing.py` (its tests must pass unmodified).
- Dependencies not to add: none (`opentelemetry-proto` is already installed with `opentelemetry-exporter-otlp-proto-http`).
- Patterns to avoid: `ensure_ascii=True` in the JSONL line (would escape every valid non ASCII path, BT-048); sanitizing in `trace_span` (would lose the JSONL escape); `logger.exception` or `exc_info=True` anywhere in the exporters; document content in an attribute.
- Scope boundary: path refusals (US-0076, US-0077) are out; the span of a refused path is asserted in US-0077 (BT-037).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_tracing.py`, `tests/test_logging_config.py`, `tests/test_http_export.py` pass unmodified.
- [ ] Docs updated: `.agent_docs/observability.md`.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0075: Tracing and logging never break on unencodable text`, body `Spec: SPEC-0013` and BR-019.
