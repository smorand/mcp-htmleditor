# Logging and tracing

## Where the files land

| File | Content |
|------|---------|
| `<log dir>/mcp-htmleditor.log` | Application log, rotating (2 MB, 3 backups) |
| `<log dir>/mcp-htmleditor-otel.log` | One JSON object per finished span (JSONL) |

`<log dir>` is `~/.cache/mcp-htmleditor/logs` by default, moved by
`HTMLEDITOR_LOG_DIR` or its alias `HTMLEDITOR_LOGS`, or by `HTMLEDITOR_CACHE_DIR` /
`XDG_CACHE_HOME` since the log dir hangs under the cache dir.

## Console output

`-v` raises the level to DEBUG, `-q` drops it to ERROR, the default is INFO. The console
handler is a `RichHandler` on **stderr** with `omit_repeated_times=False`: every line
carries its own timestamp, a timestamp is never inherited from the line above. stdout
belongs to `click.echo` (user output) and to the MCP stdio protocol.

`PIL`, `urllib3`, `httpx`, `httpcore`, `asyncio` and `opentelemetry` never go below INFO,
otherwise a single exported PNG floods the console with chunk traces.

## Span inventory

Names follow `category.operation`.

| Span | Emitted by | Attributes |
|------|-----------|------------|
| `mcp.start_server` | `mcp_server.start_server` | `file.path`, `server.port`, `server.started` |
| `mcp.stop_server` | `mcp_server.stop_server` | none |
| `mcp.get_status` | `mcp_server.get_status` | `server.running` |
| `mcp.open_file` | `mcp_server.open_file` | `file.path` |
| `mcp.update_start` / `mcp.update_end` | `mcp_server` | `file.path` |
| `export.pptx` | `export/to_pptx.to_pptx` | `file.path`, `slide.count`, `warning.count` |
| `export.docx` | `export/to_docx.to_docx` | `file.path`, `export.charter`, `warning.count` |
| `export.reference_docx` | `export/reference_docx` | `export.charter`, `file.path` |
| `tool.pandoc` | DOCX export, reference generation, version probe | `tool.operation`, `file.path` or `file.size` |
| `file.write` | editor save, `new` from a template, PPTX save | `file.path`, `file.size`, `export.format`, `template.key` |

Durations come for free (`duration_ms` in the JSONL record). An exception inside a span
is recorded and the span status becomes `ERROR`; the exception is re-raised untouched.

Never trace document content, prompts, HTML fragments or credentials. Paths, counts,
sizes, charter keys and durations only.

## Exporting somewhere else

```bash
export HTMLEDITOR_OTEL_DESTINATION=http://collector:4318/v1/traces
export HTMLEDITOR_OTEL_API_KEY=your-token
```

With a destination set, spans go to that OTLP/HTTP endpoint through a
`BatchSpanProcessor` and the key travels as `Authorization: Bearer <key>`. Without one,
a `SimpleSpanProcessor` writes the JSONL file immediately, which is what makes a local
export inspectable right after it ran. Both variables are read through `Settings`, typed
`str | None`, default `None`.

## Reading the JSONL quickly

```bash
tail -5 ~/.cache/mcp-htmleditor/logs/mcp-htmleditor-otel.log | python3 -m json.tool
# slowest spans
python3 -c "
import json, pathlib, os
p = pathlib.Path(os.path.expanduser('~/.cache/mcp-htmleditor/logs/mcp-htmleditor-otel.log'))
rows = [json.loads(l) for l in p.read_text().splitlines() if l]
for r in sorted(rows, key=lambda r: -r['duration_ms'])[:10]:
    print(f\"{r['duration_ms']:9.1f} ms  {r['name']}  {r['attributes']}\")
"
```

## Adding an instrumented call

```python
from .tracing import trace_span

with trace_span("export.pdf", {"file.path": str(path)}) as span:
    result = do_the_work()
    span.set_attribute("page.count", result.pages)
```

`trace_span` is safe without `configure_tracing()`: the OpenTelemetry API hands back a
no-op tracer, so a library user pays nothing.
