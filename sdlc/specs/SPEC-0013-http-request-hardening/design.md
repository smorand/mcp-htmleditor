# SPEC-0013: Malformed, ambiguous or stalled requests get no clean answer, design

> Spec: sdlc/specs/SPEC-0013-http-request-hardening/spec.md
> Nature: BUG
> Depth: M
> Security: internal finding
> Designed on: 2026-11-05
> Target tier: 2 (default: no `--tier`, no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

Run mode: unattended (the user said "go"). Every point where the command would ask was decided with the
recommended default and recorded below as a `DEC-`. No new dependency, no new setting, no data format change.

Project state: existing (`ls src/mcp_htmleditor` lists 25 modules; `git log --oneline -1` is `528474c`).

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| Language, packaging | Python, uv, `make` only | `requires-python >=3.13` (`pyproject.toml:8`) | existing |
| HTTP server | stdlib `ThreadingHTTPServer` + `BaseHTTPRequestHandler` (`src/mcp_htmleditor/http_server.py:97`, `:829`) | stdlib | existing, DEC-011, DEC-013 |
| CLI | Click (`src/mcp_htmleditor/cli.py:21`) | `click>=8.0` | existing |
| Tool protocol | FastMCP, `ToolError` (`src/mcp_htmleditor/mcp_server.py:17`) | `fastmcp>=2.0` (locked 3.4.6) | existing |
| Tracing | OpenTelemetry SDK, local JSONL exporter or OTLP/HTTP (`src/mcp_htmleditor/tracing.py:151`) | `opentelemetry-sdk` locked 1.44.0 (`uv.lock:1294`) | DEC-006, DEC-007 |
| Logging | stdlib `RotatingFileHandler` plus rich console on stderr (`src/mcp_htmleditor/logging_config.py:112`) | stdlib | DEC-008 |
| Tests | pytest, pytest-asyncio, pytest-playwright (existing), raw TCP sockets | as locked | DEC-016, DEC-017 |

Skills loaded: `python` (via `load_dynamic_context`, injected for this run). Effect: `make check` is the gate
(lint, format-check, typecheck strict, bandit, coverage 80 %); no `os.environ` read in `src`; `%` logging; no
`print`; frozen dataclasses for values; constants at the top of modules; tests through `make test` only.
Project conventions applied: `AGENTS.md` (Settings only, logs never on stdout, `trace_span` everywhere, never
document content in a span), `.agent_docs/architecture.md`, `.agent_docs/testing.md`, `.agent_docs/python.md`,
`tests/test_size_caps.py` (no cap on `http_server.py`; new modules kept small).

## 2. Approaches

BUG: fix strategies. The root causes are five separate sinks of three classes (Spec 1bis). The question for
each class is "fix at the sink, at the boundary, or both".

### Chosen: one gate per boundary, one shared helper per class, defense at the sink only where a write happens

- Class A (header ambiguity): one header gate in the request handler, run first inside the existing
  `_refuse_untrusted_request` (`http_server.py:107`), so it precedes the SPEC-0005 checks on every `GET` but
  `/health` and every `POST` (DEC-011). Root cause site: E1, E2 single value lookups; the gate reads every
  occurrence with `self.headers.get_all` and `self.headers.items()`.
- Class B (length and time): one shared body reader with a cap used by the request routes and `/arch-layout`
  (DEC-012); one new module `http_deadline.py` that wraps the handler's input and output streams so every read
  is bounded by a per wait bound and a per request total bound, and every write by the per wait bound (DEC-013,
  DEC-014). Root cause site: E11 and E12.
- Class C (unencodable text): one tiny module `textcheck.py` holding the encodability predicate, the U+FFFD
  replacement and the three user messages (DEC-001). Each surface refuses at its boundary with its own native
  error type (`SaveRefusal`, `DeckError`, `RequestError`, `ToolError`, `click.ClickException`), so every
  existing translation path prints the message unchanged. The atomic writer also converts an encoding failure
  into its `WriteError` (DEC-003) so no future caller can crash a write with a traceback. Tracing escapes at the
  exporter, never at the call site (DEC-006, DEC-007).

Pros: each refusal sits where the spec's message and status are known; no surface learns a new exception type;
one predicate for "cannot be encoded"; the gate is structurally first so a new route cannot bypass it.
Cons: path checks are spread over seven service entry points (listed in DEC-009). Risk: a future path taking
service forgets the check; mitigated by the parametrized surface test of US-0077 and the closing audit.
Affected scope: `http_server.py`, `http_deadline.py` (new), `textcheck.py` (new), `fileio.py`,
`deck/__init__.py`, `deck/patch.py`, `deck/tools.py`, `history.py`, `request_service.py`, `mcp_server.py`,
`cli.py`, `tracing.py`, `logging_config.py`, `pyproject.toml`.

### Rejected: fix only at the sinks (encode with `errors=...` everywhere, catch `UnicodeEncodeError` at the top)

Summary: let every write, hash and bind raise, and catch `UnicodeEncodeError` once per surface. Rejected
(DEC-001, DEC-009): the sinks are 20 sites (S7, S8, S11); a top level catch cannot tell a path problem from a
text problem, so the two different messages of BR-011/BR-012 and BR-018 would need inspection of the failing
value; the save route would still have reached the write (BR-010 orders the check before the template check).

### Rejected: replace the stdlib handler by a third party server (h11, uvicorn)

Summary: a strict HTTP/1.1 parser refuses duplicates, folding and stalls by itself. Rejected (DEC-010 scope):
new dependency (ASK category 2) and a new runtime model for a Low severity bug; the stdlib parser keeps every
field line (E8), which is all the gate needs.

### Rejected: socket timeout only (`timeout = 30` class attribute of the handler)

Summary: `StreamRequestHandler.setup` would call `settimeout(30)`. Rejected (DEC-013): the stdlib swallows a
request line timeout with no answer (stdlib `http/server.py:464`), a header or body timeout escapes as a
traceback, a client trickling one byte every 29 seconds is never cut (BR-020), and `sendall` treats the
timeout as a total for the whole answer (Python 3.5+), which would cut a large answer to a client that is
reading.

## 3. Architecture

```
 socket ──▶ _EditorHandler.setup(): rfile = DeadlineReader(rfile, sock)   wfile = DeadlineWriter(sock)
              │                         (http_deadline.py: WAIT_SECONDS, TOTAL_SECONDS, read at use time)
              ▼
 handle_one_request() override ─ catches RequestTimeout ─▶ 408 / silent close, one "Refused" line
              │                 ─ catches ResponseTimeout, BrokenPipe, ConnectionReset ─▶ close, no answer
              │                 ─ catches any other Exception ─▶ one error line, 500 if nothing sent yet
              ▼
 do_GET (/health first) / do_POST ─▶ _refuse_untrusted_request()
                                        1. _refuse_ambiguous_headers(): folding, duplicates, Transfer-Encoding, Host '@'  (400)
                                        2. existing SPEC-0005 host and origin checks (403)
              ▼
 routes: /content save ─ parse_content_length ─ parse_save_body (+ encodability, 400) ─ refuse_template ─ write_save ─ atomic_write
         /requests, /requests/delete, /review/apply ─ _read_request_body ─ _read_declared_body(BODY_MAX_BYTES)
         /arch-layout ─ _read_declared_body(LAYOUT_BODY_MAX_BYTES) ─ layout_file

 CLI command / agent tool ─▶ service entry (load_deck, check_target, create_file, export_file, list_versions,
                             restore_version, require_file) ─ textcheck.is_utf8_encodable(path) ─ DeckError / RequestError
                          ─▶ apply_patch (encodability of the new text) / RequestService.write_review, complete
 trace_span ─▶ provider ─▶ JsonlSpanExporter (bytes, backslashreplace)  |  EncodableSpanExporter(OTLPSpanExporter) (U+FFFD)
```

Components and responsibilities:

- `textcheck.py` (new, about 40 lines, no internal import): predicate, replacement, messages (DEC-001).
- `http_server.py`: header gate, shared body reader, save encodability, handler stream wrappers and the
  request level exception policy (DEC-002, DEC-011, DEC-012, DEC-014, DEC-015).
- `http_deadline.py` (new, about 150 lines, no `pragma: no cover`, unit tested with `socket.socketpair`):
  `DeadlineReader`, `DeadlineWriter`, `RequestTimeout`, `ResponseTimeout`, the two bound constants (DEC-013).
- Service entry points own the path refusal so the command and the tool give the same text (DEC-009).
- `tracing.py`: exporters never raise and never log a traceback (DEC-006, DEC-007).

Bounded contexts: editor HTTP server (class A, B, BR-010), deck services and commands (BR-011, BR-018),
request record (BR-012), tracing (BR-019), server start (BR-021).

## 4. Data model

No change. No file, record or state format changes (Spec BUG-001 to BUG-005 rollback posture). Two module
constants are added: `http_deadline.WAIT_SECONDS = 30.0`, `http_deadline.TOTAL_SECONDS = 300.0`, and
`http_server.LAYOUT_BODY_MAX_BYTES = BODY_MAX_BYTES` (1 048 576).

## 5. Contracts and interfaces

### 5.1 Python

```python
# src/mcp_htmleditor/textcheck.py (new)
UNENCODABLE_TEXT = "Text cannot be encoded as UTF-8"
UNENCODABLE_FILE_NAME = "File name cannot be encoded"
UNENCODABLE_BIND_ADDRESS = "Bind address cannot be encoded"
REPLACEMENT_CHARACTER = "\ufffd"

def is_utf8_encodable(text: str) -> bool: ...
    # True when text.encode("utf-8") (strict) succeeds: False for any code point U+D800..U+DFFF,
    # U+DC80..U+DCFF (an undecodable command line byte) included.
def replace_unencodable(text: str) -> str: ...
    # each code point U+D800..U+DFFF replaced by U+FFFD; any other text returned unchanged (same object when
    # encodable).
```

```python
# src/mcp_htmleditor/http_deadline.py (new)
WAIT_SECONDS: float = 30.0       # BR-008; read as http_deadline.WAIT_SECONDS at each use (test seam, BR-022)
TOTAL_SECONDS: float = 300.0     # BR-020; same
WRITE_CHUNK_BYTES = 65_536

class RequestTimeout(Exception):   # NOT a TimeoutError subclass: the stdlib swallows TimeoutError (http/server.py:464)
    has_bytes: bool                # False when the connection never sent a byte (silent close, no log)

class ResponseTimeout(Exception): ...

class DeadlineReader:
    def __init__(self, stream: io.BufferedIOBase, sock: socket.socket,
                 clock: Callable[[], float] = time.monotonic) -> None: ...
    bytes_received: int
    def readline(self, limit: int = -1) -> bytes: ...   # used by the stdlib request line and parse_headers
    def read(self, size: int = -1) -> bytes: ...        # used by the routes for the body; size >= 0 only
    def close(self) -> None: ...
    @property
    def closed(self) -> bool: ...

class DeadlineWriter:
    def __init__(self, sock: socket.socket) -> None: ...
    def write(self, data: bytes) -> int: ...            # chunks of WRITE_CHUNK_BYTES, settimeout(WAIT_SECONDS) before each
    def flush(self) -> None: ...                        # no op
    def close(self) -> None: ...
    @property
    def closed(self) -> bool: ...
```

Algorithm of `DeadlineReader` (DEC-013), stated so the implementer does not have to infer it:

1. `_arm()`: `timeout = http_deadline.WAIT_SECONDS`; when `started_at` is set,
   `remaining = started_at + http_deadline.TOTAL_SECONDS - clock()`; `remaining <= 0` raises
   `RequestTimeout(has_bytes=True)`; else `timeout = min(timeout, remaining)`. Then `sock.settimeout(timeout)`.
2. `_peek()`: `_arm()`, then `stream.peek(1)` (one `recv` at most when the buffer is empty); `TimeoutError` (or
   `OSError` raised after a timed out read) becomes `RequestTimeout(has_bytes=bytes_received > 0)`. `b""` is end of
   stream.
3. `readline(limit)`: loop `_peek()`; take up to the first `b"\n"` within the remaining limit; `stream.read(k)`
   (no blocking: the bytes are buffered); on the first byte ever set `started_at = clock()`; stop at newline,
   limit or end of stream.
4. `read(size)`: loop `_peek()` and `stream.read(min(len(peeked), size - len(out)))` until `size` bytes or end of
   stream.

A single `recv` returns as soon as any byte arrives, so the wait restarts at each byte (BR-008); the total is
measured from the first byte of the connection (BR-020); the total never applies to writes.

### 5.2 Handler changes (`src/mcp_htmleditor/http_server.py`)

```python
class _EditorHandler(BaseHTTPRequestHandler):
    def setup(self) -> None                      # super().setup(); wrap rfile and wfile (DEC-013)
    def handle_one_request(self) -> None         # exception policy of DEC-015
    def send_response(self, code: int, message: str | None = None) -> None   # sets self._answered = True, then super()
    def _refuse_ambiguous_headers(self) -> bool  # BR-004, BR-001, BR-002, BR-003 in that order (DEC-011)
    def _refuse_request(self, status: int, error: str) -> None
        # logger.warning("Refused %s %s: %s", self.command, urlparse(self.path).path, error); _send_json({"error": error}, status)
    def _read_declared_body(self, limit: int) -> bytes    # parse_content_length, > limit is 413 before reading (DEC-012)
```

The existing 403 refusals keep `_refuse` and its log format `Refused %s %s: %s %r` (SPEC-0005/BR-008,
unchanged). `_receive_content` keeps its existing warning line, which already has the BR-013 form.

### 5.3 HTTP answers (exact, from the spec)

| Condition | Status | Body | Log line (WARNING) |
|---|---|---|---|
| a field line folded (any header value holding `\r` or `\n`) | 400 | `{"error":"Invalid header folding"}` | `Refused <M> <path>: Invalid header folding` |
| more than one `Host`, `Origin`, `Content-Length`, `Content-Type` (first in that order named) | 400 | `{"error":"Duplicate <Name> header"}` | `Refused <M> <path>: Duplicate <Name> header` |
| any `Transfer-Encoding` | 400 | `{"error":"Transfer-Encoding not supported"}` | same form |
| single `Host` containing `@` | 400 | `{"error":"Invalid Host header"}` | same form |
| `/arch-layout` length not ASCII digits | 400 | `{"error":"Invalid Content-Length"}` | same form |
| `/arch-layout` length > 1 048 576 | 413 | `{"error":"Request too large"}` | same form |
| save `html` unencodable | 400 | `{"error":"Text cannot be encoded as UTF-8"}` | same form (existing line of `_receive_content`) |
| wait or total bound reached with bytes received | 408 | `{"error":"Request timeout"}` | `Refused <M> <path>: Request timeout`, or `Refused - -: Request timeout` when the request line is incomplete |
| wait bound reached, zero byte received | none, connection closed | none | none |
| client stops reading an answer for `WAIT_SECONDS` | none, connection closed | none | none (DEBUG only) |
| unexpected exception in a route, nothing sent yet | 500 | `{"error":"<str(exc)>"}` | one ERROR line `Request failed: <M> <path>: <ExcType>` without traceback |

`GET /health` keeps being answered before the gate (`http_server.py:147`); `OPTIONS` keeps `405`
(`do_OPTIONS`, `:132`); other methods keep the stdlib `501` (E30).

### 5.4 Command and tool answers (exact, from the spec)

| Surface | Condition | Answer |
|---|---|---|
| `patch` command (and `--dry-run`) | new text unencodable | stderr `error: Text cannot be encoded as UTF-8`, stdout empty, exit 1 |
| `patch` tool (and `dry_run`) | same | `ToolError("Text cannot be encoded as UTF-8")` |
| `review --write`, `request-skip --reason` | text unencodable | stderr `error: Text cannot be encoded as UTF-8`, exit 1 |
| `write_review`, `complete_request` tools | same | `ToolError("Text cannot be encoded as UTF-8")` |
| `new`, `outline`, `render`, `get-slide`, `lint`, `patch`, `history`, `restore`, `export`, `requests`, `request-done`, `request-skip`, `review` | a path argument unencodable | stderr `error: File name cannot be encoded`, exit 1 (`render` too) |
| `serve`, `arch-layout` | existing `FILE` with an unencodable name | stderr `Error: File name cannot be encoded`, exit 1 (click `ClickException`) |
| every tool with `file` or `output` | path unencodable | `ToolError("File name cannot be encoded")` |
| `serve --host`, `new --serve --host`, `HTMLEDITOR_HOST` | bind address unencodable | stderr ends `Error: Bind address cannot be encoded`, exit 1 |
| `start_server` tool | `HTMLEDITOR_HOST` unencodable | `ToolError("Bind address cannot be encoded")` |

### 5.5 Tracing contract

- JSONL: each span is one line of valid UTF-8; an unencodable code point inside a string appears as its JSON
  escape (`\ud800`, six ASCII characters); every other character as itself (DEC-006).
- OTLP: every string of the span (name, attributes, event attributes, status description) has each
  unencodable code point replaced by U+FFFD before the OTLP encoder sees it (DEC-007).
- Any export failure: one WARNING line `Span export failed (<destination>): <ExcType>: <message>` with the
  message passed through `replace_unencodable`, never `exc_info`.

### 5.6 Configuration

No new key. The two bounds are not `Settings` fields, not options, not environment variables and are named in
no user documentation (BR-022, DEC-013). `pyproject.toml` gains a `slow` marker and `addopts = "-m 'not slow'"`
(DEC-017).

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/http_server.py` | modify: gate, `_refuse_request` | BR-001 to BR-005, BR-013 | US-0071 |
| `tests/http_support.py` | create: raw socket exchange helper | BR-001 (test driver) | US-0071 |
| `tests/test_http_header_gate_e2e.py` | create | BR-001 to BR-005, BR-014 | US-0071 |
| `.agent_docs/architecture.md` | modify: request gate paragraph | BR-005 | US-0071 |
| `src/mcp_htmleditor/http_server.py` | modify: `_read_declared_body`, layout route | BR-006, BR-007, BR-009, BR-013 | US-0072 |
| `tests/test_http_layout_length_e2e.py` | create | BR-006, BR-007 | US-0072 |
| `tests/test_save_safety_e2e.py` | modify: docstring of `test_length_checks_apply_to_the_save_endpoint_only` only | Spec 4.4 | US-0072 |
| `src/mcp_htmleditor/textcheck.py` | create | BR-010, BR-011, BR-012, BR-018, BR-019, BR-021 | US-0073 |
| `src/mcp_htmleditor/http_server.py` | modify: `parse_save_body`, `_is_text` | BR-010, BR-015 | US-0073 |
| `src/mcp_htmleditor/fileio.py` | modify: `atomic_write` encode | BR-009, BR-016 | US-0073 |
| `tests/test_textcheck.py` | create | BR-010, BR-017 | US-0073 |
| `tests/test_unencodable_save_e2e.py` | create | BR-010, BR-013, BR-015, BR-016 | US-0073 |
| `src/mcp_htmleditor/deck/patch.py` | modify: encode of the new text | BR-011 | US-0074 |
| `src/mcp_htmleditor/request_service.py` | modify: `write_review`, `complete` | BR-012 | US-0074 |
| `tests/test_unencodable_text.py` | create | BR-011, BR-012, BR-016, BR-017 | US-0074 |
| `src/mcp_htmleditor/tracing.py` | modify: JSONL bytes, OTLP wrapper | BR-019 | US-0075 |
| `src/mcp_htmleditor/logging_config.py` | modify: file handler `errors` | BR-019 | US-0075 |
| `tests/trace_support.py` | create: subprocess runner with its own tracer | BR-019 (test driver) | US-0075 |
| `tests/test_tracing_unencodable.py` | create | BR-019 | US-0075 |
| `.agent_docs/observability.md` | modify | BR-019 | US-0075 |
| `src/mcp_htmleditor/deck/__init__.py` | modify: `load_deck` | BR-018 | US-0076 |
| `src/mcp_htmleditor/deck/patch.py` | modify: `check_target` | BR-018 | US-0076 |
| `src/mcp_htmleditor/deck/tools.py` | modify: `create_file`, `export_file` | BR-018 | US-0076 |
| `src/mcp_htmleditor/history.py` | modify: `list_versions`, `restore_version` | BR-018 | US-0076 |
| `tests/test_unencodable_paths.py` | create | BR-018 | US-0076 |
| `src/mcp_htmleditor/request_service.py` | modify: `require_file` | BR-018 | US-0077 |
| `src/mcp_htmleditor/mcp_server.py` | modify: span path helper, server tool checks, bind check | BR-018, BR-019, BR-021 | US-0077 |
| `src/mcp_htmleditor/cli.py` | modify: `serve`, `arch-layout`, `_serve_file` | BR-018, BR-021 | US-0077 |
| `tests/test_unencodable_surfaces.py` | create | BR-018, BR-019, BR-021 | US-0077 |
| `src/mcp_htmleditor/http_deadline.py` | create | BR-008, BR-009, BR-022 | US-0078 |
| `src/mcp_htmleditor/http_server.py` | modify: `setup`, `handle_one_request`, `send_response` | BR-008, BR-009, BR-013 | US-0078 |
| `tests/test_http_time_bounds.py` | create | BR-008, BR-009, BR-013, BR-022 | US-0078 |
| `src/mcp_htmleditor/http_deadline.py` | modify: total bound | BR-020 | US-0079 |
| `tests/test_http_time_bounds.py` | modify: BT-044, total bound unit tests | BR-020 | US-0079 |
| `tests/test_http_time_bounds_slow.py` | create (`slow`) | BR-008, BR-020 | US-0079 |
| `pyproject.toml` | modify: `markers`, `addopts` | BR-022 | US-0079 |
| `README.md`, `AGENTS.md`, `.agent_docs/testing.md` | modify | closing | US-0079 |

Affected existing tests (Spec 4.4): `tests/test_save_safety_e2e.py::test_length_checks_apply_to_the_save_endpoint_only`
docstring modified (assertion kept); every other listed test kept unmodified.
Affected documentation: `.agent_docs/architecture.md` (US-0071), `.agent_docs/observability.md` (US-0075),
`README.md`, `AGENTS.md`, `.agent_docs/testing.md` (US-0079). No skill text changes (no tool is added or
renamed; `skill-audit` must stay green).

## 7. Compatibility and risks

- Consumers: the bundled editor sends single headers, no `Transfer-Encoding` and `POST /arch-layout` with no
  body (E20): unchanged (BT-029, BT-031). Agents and scripts sending valid text and paths: unchanged (BT-030,
  BT-047).
- Declared breaks (spec): new 400, 408, 413 answers; layout route length checked; unencodable text and names
  refused instead of crashing.
- Ordering: US-0071 lands the gate first (the reproduction of BUG-001); US-0073 lands `textcheck.py`, which
  US-0074 to US-0077 import. US-0075 (tracing) lands before the path stories because their tests assert the
  tool span of a refused call is written.
- Risk R1, unread body at close: a refusal before the body is read closes a socket that may still hold body
  bytes; on Linux the kernel can answer with a reset and the client may lose the answer. Accepted as today's
  SPEC-0009 413 behavior; the stdlib buffered reader has usually already pulled a small body with the headers.
  Tests send bodies small enough to be read with the headers.
- Risk R2, stdlib internals: the request line timeout path, `request_version` defaulting to `HTTP/0.9` (which
  suppresses the status line) and the "timed out" state of `SocketIO` are handled explicitly (DEC-015). Story
  US-0078 is `min_tier` 1 for that reason.
- Risk R3, process global tracer: the provider can be set once per process, so trace assertions run in a
  subprocess (DEC-016).
- Rollback: `git revert` of the story commits; no data to migrate.
- Dependencies added or removed: none.

## 8. Security design

Threat surface: the loopback editor server (trust boundary: any local process, a page in the browser, a server
side request forgery or a proxy in front), the command line arguments and environment, the JSON operations and
review files, and the trace exporters.

| Occurrence (Spec 1bis) | Fix site | Mechanism | DEC | Exploit test, second channel |
|---|---|---|---|---|
| Host, Origin, Content-Length, Content-Type reads (E1 to E6) | `http_server.py:107` `_refuse_untrusted_request`, new first call `_refuse_ambiguous_headers` | count every occurrence with `self.headers.get_all(name)`; refuse before any route | DEC-011 | BT-001, BT-005 to BT-009, BT-035: disk bytes, folder listing, `requests` and `review` commands, response bytes |
| Transfer-Encoding (S2) | same | presence of the field refused | DEC-011 | BT-010, BT-035 |
| Folded lines (E8) | same | any field value holding `\r` or `\n` (the stdlib keeps the fold inside the value) | DEC-011 | BT-012, BT-020 |
| Host userinfo (E7) | same | single `Host` containing `@` refused before `_split_host` | DEC-011 | BT-011, BT-035 |
| Layout length (E11) | `http_server.py:481` replaced by `_read_declared_body(LAYOUT_BODY_MAX_BYTES)` | `parse_content_length`, cap before reading | DEC-012 | BT-002, BT-013, BT-014: disk has no `data-x`, log has no traceback |
| Every read and write on the socket (E12) | `http_deadline.py`, `_EditorHandler.setup` | per wait and per request bounds, chunked writes | DEC-013, DEC-014 | BT-042 to BT-046 (short bounds), BT-003, BT-015, BT-022, BT-023, BT-040 (slow) |
| Save `html` (E14 to E16) | `http_server.py:614` `parse_save_body`; `fileio.py:57` | predicate, 400; writer converts to `WriteError` | DEC-002, DEC-003 | BT-004, BT-024: disk bytes, folder listing, history |
| Patch new text (E17) | `deck/patch.py:206` | predicate before any write or dry run result | DEC-004 | BT-016, BT-017, BT-036: disk, history, listing |
| Record writer (E13b) | `request_service.py` `write_review`, `complete` | predicate on every stored string | DEC-005 | BT-018, BT-019: `review` and `GET /requests`, state listing |
| Path keys and file names (E15j, E29) | `load_deck`, `check_target`, `create_file`, `export_file`, `list_versions`, `restore_version`, `require_file`, server tools, `serve`, `arch-layout` | predicate on the path text first | DEC-009 | BT-033, BT-037: `tmp_path` and state listings, trace file |
| Trace exporters (E21, E21b, E22, E23) | `tracing.py:75` to `:80`, `_otlp_exporter` | escape at write, U+FFFD for OTLP, never raise | DEC-006, DEC-007 | BT-034, BT-038, BT-039: trace file, OTLP listener body, captured stderr |
| Log handlers (E30b) | `logging_config.py:112` | `errors="backslashreplace"` | DEC-008 | BT-034, BT-037 (`Logging error` absent) |
| Bind address (E36) | `cli.py` `_serve_file`, `mcp_server.py` `start_server` | predicate before any port probe or bind | DEC-010 | BT-041: `get_status`, port probe 7840 to 7849 |

Every exploit test carries the literal payload of the spec and is red before its story for the reason the
spec states. Secrets: unchanged (`otel_api_key` never traced). Never logged or traced: request bodies, header
values of refused requests (the new log lines carry only the method, the path and the error text), document
content, review and request text.

## 9. Test strategy

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| BT-001, BT-005 to BT-012, BT-020, BT-026, BT-027, BT-035 | exploit / functional e2e | raw TCP socket (`tests/http_support.py`) on `serve_deck` | `tests/test_http_header_gate_e2e.py` | US-0071 |
| BT-002, BT-013, BT-014, BT-021 | exploit / functional e2e | raw TCP socket | `tests/test_http_layout_length_e2e.py` | US-0072 |
| BT-029 | functional e2e | Playwright Chromium | `tests/test_http_layout_length_e2e.py` | US-0072 |
| BT-004, BT-024, BT-025, BT-028 | functional e2e | raw TCP socket, `caplog` | `tests/test_unencodable_save_e2e.py` | US-0073 |
| BT-016, BT-017, BT-018, BT-019, BT-030, BT-032, BT-036 | exploit / functional e2e | `run_cli`, `call_tool` (`tests/deck_support.py:244`, `:252`), `CliRunner` with bytes via `subprocess` for `\xff` | `tests/test_unencodable_text.py` | US-0074 |
| BT-034, BT-038, BT-039, BT-048 | functional e2e | subprocess with its own tracer (`tests/trace_support.py`), OTLP listener on `127.0.0.1` | `tests/test_tracing_unencodable.py` | US-0075 |
| BT-033 | functional e2e | `call_tool` | `tests/test_unencodable_paths.py` | US-0076 |
| BT-037, BT-041, BT-047 | exploit / functional e2e | `call_tool`, subprocess CLI with byte arguments, subprocess tracer | `tests/test_unencodable_surfaces.py` | US-0077 |
| BT-042, BT-043, BT-045, BT-046 | functional e2e, short bounds | raw TCP socket, `monkeypatch` of `http_deadline` bounds | `tests/test_http_time_bounds.py` | US-0078 |
| BT-044 | functional e2e, short bounds | same | `tests/test_http_time_bounds.py` | US-0079 |
| BT-003, BT-015, BT-022, BT-023, BT-040 | functional e2e, real bounds, `slow` | raw TCP socket | `tests/test_http_time_bounds_slow.py` | US-0079 |
| BT-031 | functional e2e | Playwright Chromium (as the SPEC-0005 non regression test in `tests/test_http_origin_e2e.py`) | `tests/test_http_header_gate_e2e.py` | US-0071 |

BUG reproduction tests (red before, green after): BT-001 (red: `200`, `PWNED` on disk), BT-002 (red: connection
closed, traceback), BT-004 (red: `RemoteDisconnected`), BT-033 (red: `UnicodeEncodeError` instead of a tool
error), BT-034 (red: trace line missing, `Exception while exporting Span.` logged), BT-003 (red: no answer after
35 seconds, slow) and its default run counterpart BT-042.

Test data: generated in each test (the carbon bootstrap copy titled `ORIGINAL-SECRET` of Spec section 4, the
declarative diagram of BT-013, the 16 MiB comment of BT-046). No user provided data. `make check` budget: the
short bound tests BT-042 to BT-046 under 25 seconds together (`pytest --durations=0`).

## 10. Decisions log

- **DEC-001:** One new module `src/mcp_htmleditor/textcheck.py` holds `is_utf8_encodable`, `replace_unencodable`
  and the three messages; it imports nothing from the package. Each surface raises its own native error with
  these messages. **Obliged by:** SPEC-0013/BR-010, BR-011, BR-012, BR-018, BR-019, BR-021. **Rationale:** one
  definition of "cannot be encoded" (strict UTF-8, which also refuses U+DC80 to U+DCFF that `os.fsencode` would
  accept); a module with no internal import can be used by `deck/__init__.py`, which `fileio.py` imports
  (`fileio.py:17`), so placing the helper in `fileio.py` as first suggested would create an import cycle
  `fileio -> deck -> fileio`. **Alternatives considered:** helper in `fileio.py` (cycle); a shared exception
  class (every surface would need a new translation). **Source:** design, existing code `fileio.py:17`,
  `http_server.py:585`. **Evidence:** `_is_text` at `http_server.py:585` already implements the predicate
  inline; it becomes a call to `is_utf8_encodable`.
- **DEC-002:** The save refusal is raised in `parse_save_body` right after the `Invalid JSON body` checks as
  `SaveRefusal(400, {"error": UNENCODABLE_TEXT})`; the existing warning of `_receive_content`
  (`http_server.py:448`) logs it. `_is_text` delegates to `is_utf8_encodable`. **Obliged by:** BR-010, BR-013,
  BR-015. **Rationale:** the spec places the check after `Invalid JSON body` and before the template check;
  `parse_save_body` runs before `refuse_template` (`http_server.py:442`, `:443`). **Alternatives considered:**
  check in `write_save` (after the template check: wrong order, BT-024 last case). **Source:** spec constraint
  (BR-010 order). **Evidence:** `http_server.py:614` to `:628`.
- **DEC-003:** `atomic_write` encodes a `str` inside its error handling and turns `UnicodeEncodeError` into
  `WriteError(path, UNENCODABLE_TEXT)` before any temporary file exists. **Obliged by:** BR-009, BR-016.
  **Rationale:** defense in depth at the single text writer (E15) so no future caller crashes a write; no
  temporary file because the encode precedes `mkstemp` (`fileio.py:57`, `:70`). **Alternatives considered:**
  leave the sink unprotected (one forgotten boundary would reopen BUG-003). **Source:** design.
  **Evidence:** `fileio.py:57` to `:63`.
- **DEC-004:** `apply_patch` checks `is_utf8_encodable(text)` on the assembled text before `encode` and before
  the dry run result, raising `DeckError(UNENCODABLE_TEXT)`; `deck_command` (`cli.py:34`) and the tool
  (`mcp_server.py` `patch`) already translate `DeckError`. **Obliged by:** BR-011, BR-016. **Rationale:** the
  check covers every operation (`set_text`, `replace_slide`, `insert_slide`, ...) at one point; nothing is
  written. **Alternatives considered:** check each operation's input (five sites, and renumbering could not
  introduce it anyway). **Source:** existing code `deck/patch.py:206`. **Evidence:** `deck/patch.py:203` to `:209`.
- **DEC-005:** `RequestService.write_review` checks every string field of every suggestion (`id`, `slide`,
  `title`, `why`, `change`) after the existing shape rules, and `RequestService.complete` checks `reason`, both
  raising `RequestError("invalid", UNENCODABLE_TEXT)` before `store.update`. The HTTP routes keep their
  `_is_text` check first, so they keep `Invalid request body`. **Obliged by:** BR-012, BR-016. **Rationale:**
  the service owns every rule and message of the record (SPEC-0010 DEC-005); the command and the tool then
  print the same text. Existing shape messages keep precedence (a non list is still `Review must be a list of
  suggestions`). **Alternatives considered:** check in `RequestStore._serialize` (a storage error kind and
  message, wrong text). **Source:** existing code `request_service.py:91`, `:109`. **Evidence:**
  `request_store.py:174`.
- **DEC-006:** `JsonlSpanExporter.export` builds the lines with `json.dumps(..., ensure_ascii=False)` as today,
  encodes them with `encode("utf-8", "backslashreplace")` and appends bytes (file opened `"ab"`); it catches
  `Exception` (not only `OSError`), logs one WARNING without `exc_info` and returns `FAILURE`. **Obliged by:**
  BR-019. **Rationale:** a lone surrogate can only sit inside a JSON string, where Python's backslash escape of
  U+D800 is exactly the JSON escape `\ud800`; valid characters stay unescaped as today; the SDK processor never
  sees an exception, so it never logs its traceback (E21b). **Alternatives considered:** `ensure_ascii=True`
  (changes every non ASCII path in the trace file, BT-048 requires it as is); sanitizing at `trace_span` (loses
  the escape the spec requires). **Source:** design. **Evidence:** `tracing.py:75` to `:81`; stdlib codec:
  `"\ud800".encode("utf-8", "backslashreplace") == b"\\ud800"` (checked on Python 3.14 during design).
- **DEC-007:** `_otlp_exporter` returns `EncodableSpanExporter(OTLPSpanExporter(...))`, a `SpanExporter` that
  maps each span to a copy whose name, attributes, event names, event attributes and status description pass
  through `replace_unencodable` (strings inside sequences too), then delegates; it catches `Exception` from the
  delegate, logs one WARNING without `exc_info`, returns `FAILURE`. `shutdown` and `force_flush` delegate.
  **Obliged by:** BR-019. **Rationale:** the OTLP encoder drops and tracebacks a bad key (E22); the spec wants
  the attribute kept with U+FFFD. The copy uses the SDK `ReadableSpan` constructor (opentelemetry-sdk 1.44.0,
  `uv.lock:1294`). **Alternatives considered:** monkeypatching the SDK encoder (private module); sanitizing at
  `trace_span` (would also change the JSONL form). **Source:** design. **Evidence:** E22.
- **DEC-008:** The rotating log file handler is created with `errors="backslashreplace"`. **Obliged by:**
  BR-019 ("never a traceback to standard error or to a log"; BT-034 and BT-037 assert no `Logging error`).
  **Rationale:** a log line formatting a tool error message that holds a lone surrogate would otherwise make
  the handler print `--- Logging error ---` (E30b); stderr already uses `backslashreplace` by Python default.
  **Alternatives considered:** filtering every log call site. **Source:** existing code
  `logging_config.py:112`. **Evidence:** `logging_config.py:112` to `:117`.
- **DEC-009:** The path refusal sits at the service entry points that every command and tool reach:
  `deck.load_deck` and `deck.patch.check_target` raise `DeckError(UNENCODABLE_FILE_NAME)`; `deck.tools.create_file`
  (after its template check) and `deck.tools.export_file` (after its format check, for `file` then `output`)
  raise the same; `history.list_versions` and `history.restore_version` raise `HistoryError(UNENCODABLE_FILE_NAME)`
  (a `DeckError`); `request_service.require_file` raises `RequestError("invalid", UNENCODABLE_FILE_NAME)`; the
  tools `start_server`, `open_file`, `layout_arch_diagram` check before resolving and raise `ToolError`; the
  commands `serve` and `arch-layout` raise `click.ClickException(UNENCODABLE_FILE_NAME)` first. Tools whose span
  attribute is `str(Path(file).resolve())` compute it with a private `_span_path(file)` that returns `file`
  unchanged when it is not encodable (resolving would raise `UnicodeEncodeError`). `render` gets status 1 because
  its refusal comes from `load_deck` inside `deck_command`, not from `RenderUsageError`. **Obliged by:** BR-018,
  BR-019. **Rationale:** one check per service gives the command and the tool the same text by construction
  (SPEC-0007 parity); existing messages for valid names are untouched; the existing order "unknown template,
  unknown format before the file" is kept (BT-039). **Alternatives considered:** a decorator on every tool and
  command (paths are positional arguments with different names; the request commands do not use
  `deck_command`). **Source:** existing code `deck/__init__.py:42`, `deck/patch.py:174`, `deck/tools.py:41`,
  `:72`, `history.py:149`, `:157`, `request_service.py:235`, `cli.py:181`, `:261`, `mcp_server.py:47`, `:122`,
  `:177`, `:439`, `:464`, `:493`, `:521`. **Evidence:** E29.
- **DEC-010:** The bind address is checked before any port probe, state save or bind: in `cli._serve_file` (it
  serves `serve` and `new --serve`) raising `click.ClickException(UNENCODABLE_BIND_ADDRESS)`, and in the tool
  `start_server` on `default_host()` raising `ToolError(UNENCODABLE_BIND_ADDRESS)`. `start_http_server` is not
  changed. **Obliged by:** BR-021. **Rationale:** `start_http_server` saves the state and probes ports before the
  bind (`http_server.py:950` to `:955`), so a check inside it would come too late or need a new exception type
  that `_serve_file` does not catch (it catches `OSError` and `RuntimeError`, `cli.py:221` to `:226`, in `_serve_file` at `cli.py:198`).
  **Alternatives considered:** a `Settings` validator (would make every command fail at start, not only the
  server ones). **Source:** existing code. **Evidence:** E35, E36.
- **DEC-011:** The header gate is a new handler method `_refuse_ambiguous_headers()` called as the first
  statement of `_refuse_untrusted_request()`. Checks, in this order, each answering through `_refuse_request`:
  (1) folding: any value of `self.headers.items()` containing `"\r"` or `"\n"` (the stdlib keeps a continuation
  line inside the value, checked during design: `('Host', 'L\r\n evil.example')`); (2) duplicates: for `Host`,
  `Origin`, `Content-Length`, `Content-Type` in that order, `len(self.headers.get_all(name) or []) > 1`
  (case insensitive by the stdlib); (3) `"Transfer-Encoding" in self.headers`; (4) the single `Host` value
  contains `"@"`. **Obliged by:** BR-001, BR-002, BR-003, BR-004, BR-005, BR-013. **Rationale:**
  `_refuse_untrusted_request` is already called for every `GET` except `/health` (`http_server.py:150`) and
  every `POST` (`:181`), unknown paths included, so the gate inherits exactly the protected route set and its
  position before the SPEC-0005 checks. `OPTIONS` and other methods never reach it. **Alternatives
  considered:** a check in `parse_request` (would also hit `OPTIONS` and `/health`). **Source:** existing code
  `http_server.py:107` to `:124`. **Evidence:** E1, E2, E8.
- **DEC-012:** A handler method `_read_declared_body(limit)` reads `parse_content_length(self.headers.get("Content-Length"))`,
  raises `SaveRefusal(413, {"error": "Request too large"})` above `limit` before reading, then reads exactly that
  many bytes. `_read_request_body` uses it with `BODY_MAX_BYTES` (keeping its rule that a wrong content type
  outranks a bad length); `_run_arch_layout` uses it with `LAYOUT_BODY_MAX_BYTES = BODY_MAX_BYTES`, after its
  existing `No file loaded` check, answering a `SaveRefusal` through `_refuse_request`. The save route keeps its
  own 50 MiB call. **Obliged by:** BR-006, BR-007, BR-009, BR-013. **Rationale:** one reader for every 1 MiB route;
  `parse_content_length` already implements "ASCII digits only, absent is 0" (`http_server.py:596`).
  **Alternatives considered:** a separate parser for the layout route (duplication). **Source:** existing code
  `http_server.py:415` to `:426`, `:481`. **Evidence:** E10, E10b, E11.
- **DEC-013:** The time bounds live in a new module `http_deadline.py` as module constants `WAIT_SECONDS = 30.0`
  and `TOTAL_SECONDS = 300.0`, read through the module object at each use (`http_deadline.WAIT_SECONDS`), so
  the test suite shortens them with `monkeypatch.setattr(http_deadline, "WAIT_SECONDS", 1.0)` on an in process
  server. `_EditorHandler.setup` wraps `self.rfile` in `DeadlineReader` and `self.wfile` in `DeadlineWriter`
  (algorithm in section 5.1). The class attribute `timeout` stays `None`. **Obliged by:** BR-008, BR-020,
  BR-022. **Rationale:** a module constant is not a `Settings` field, an option, an environment variable or a
  documented setting, so the bound stays fixed for users (BR-022) while `make check` runs the behaviors in
  seconds; wrapping the streams is the only way to bound the stdlib's own request line and header reads and to
  restart the wait at each byte; chunked writes make the send bound "30 seconds without progress" rather than
  `sendall`'s total. These are constants never reassigned by production code, not mutable globals. **Alternatives
  considered:** handler `timeout` attribute (section 2); a hidden environment variable (a user could set it,
  breaking "fixed for users"); a `Settings` field (user visible). **Source:** design, stdlib `socketserver.py:803`.
  **Evidence:** E12.
- **DEC-014:** The send side bound is enforced by `DeadlineWriter`: `sock.settimeout(WAIT_SECONDS)` then
  `sock.sendall(chunk)` per 64 KiB chunk; a `TimeoutError` becomes `ResponseTimeout`. **Obliged by:** BR-008
  (send side), BR-009. **Rationale:** Python 3.5+ `sendall` treats the timeout as a total for the call; chunking
  gives "30 seconds without the client reading". **Alternatives considered:** one `sendall` (cuts slow readers of
  large answers). **Source:** design. **Evidence:** BT-046.
- **DEC-015:** `_EditorHandler.handle_one_request` wraps `super().handle_one_request()`:
  `RequestTimeout` with `has_bytes` false closes silently; with bytes it sets `close_connection`, forces
  `self.request_version = "HTTP/1.0"` when it is still the stdlib default `HTTP/0.9` (otherwise
  `send_response` writes no status line, stdlib `http/server.py:292`, `:307`), logs
  `Refused <command or -> <path or ->: Request timeout` and sends `408 {"error":"Request timeout"}`, any
  `OSError` while sending ignored; `ResponseTimeout`, `BrokenPipeError`, `ConnectionResetError` close with a
  DEBUG line; any other `Exception` logs one ERROR line without traceback and, when `send_response` was never
  called for this request (flag `_answered` set by an override of `send_response`), answers
  `500 {"error": str(exc)}`. **Obliged by:** BR-008, BR-009, BR-013. **Rationale:** the stdlib swallows a request
  line timeout without an answer and lets header and body timeouts reach `handle_error`, which prints a
  traceback. `RequestTimeout` is deliberately not a `TimeoutError` so the stdlib does not swallow it.
  **Alternatives considered:** catching in each route (the stdlib reads the request line and headers before
  any route). **Source:** stdlib `http/server.py:442` to `:472`. **Evidence:** E12, E30.
- **DEC-016:** Trace assertions run in a subprocess (`tests/trace_support.py`: `sys.executable -c` with
  `PYTHONPATH=src`, `HTMLEDITOR_LOG_DIR`, `HTMLEDITOR_STATE_DIR`, `HTMLEDITOR_CACHE_DIR` under `tmp_path`, optional
  `HTMLEDITOR_OTEL_DESTINATION`), which calls `configure_tracing()`, runs the tool through an in process
  `fastmcp.Client`, flushes the provider and prints the tool outcome as JSON. **Obliged by:** BR-019 (test
  driver for BT-034, BT-037 span clause, BT-038, BT-039, BT-048). **Rationale:** the OpenTelemetry provider is
  process global and settable once; `tests/test_tracing.py:27` already owns the in process one and
  `tests/deck_support.py:246` disables tracing for `run_cli`. **Alternatives considered:** reading the session
  wide file of `tests/test_tracing.py` (not reachable from another module, shared state). **Source:** existing
  code `tests/test_requests_core.py` UT-A02 subprocess pattern. **Evidence:** `tests/test_tracing.py:27` to `:34`.
- **DEC-017:** Real bound tests carry `@pytest.mark.slow`; `pyproject.toml` `[tool.pytest.ini_options]` gains
  `markers = ["slow: real 30 second and 5 minute time bounds, not run by make check"]` and
  `addopts = "-m 'not slow'"`. They run with `make test ARGS='-m slow'` (the last `-m` wins in pytest). No new
  Makefile target. **Obliged by:** BR-022 (Spec section 4: slow tests not selected by the default run).
  **Rationale:** `make` stays the only entry point; the Python Makefile targets stay identical to the template.
  **Alternatives considered:** a `test-slow` target (a Python target outside the template). **Source:** spec
  constraint, `Makefile:83` to `:95`. **Evidence:** E31.
- **DEC-018:** `tests/http_support.py` provides `exchange(port: int, data: bytes, *, timeout: float = 5.0) -> RawReply`
  (send the exact bytes, read until the server closes, parse status line, headers, body; `RawReply` frozen with
  `status: int | None`, `headers: dict[str, str]`, `body: bytes`, `raw: bytes`, `elapsed: float`, `closed: bool`)
  and `json_body(reply) -> Any`. **Obliged by:** BR-001 (test driver: a standard HTTP client merges or rejects
  duplicated headers, Spec section 4). **Rationale:** one helper reused by US-0071, US-0072, US-0073, US-0078,
  US-0079. **Alternatives considered:** inline helpers per file (duplication). **Source:** design; pattern
  `tests/test_save_safety_e2e.py:51` `_post_raw`. **Evidence:** n/a.
- **DEC-019:** Story slicing: nine stories, one per boundary, `US-0078` (stream wrappers and exception policy)
  at `min_tier` 1 and every other at 2; the closing story carries the total bound, the slow suite and the user
  documentation. **Obliged by:** n/a (no code impact): partition of the work, every requirement covered in
  section 11. **Rationale:** the stdlib internals of DEC-015 hold several silent pitfalls (HTTP/0.9 default,
  swallowed `TimeoutError`, timed out `SocketIO`), which is decision density above tier 2; splitting the total
  bound out keeps US-0078 within budget. **Alternatives considered:** one time bound story at tier 1 (seven
  files). **Source:** design.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0071 | refuse ambiguous identity and framing headers | P1 | BR-001, BR-002, BR-003, BR-004, BR-005, BR-013 (partial), BR-014 (partial) | main | 2 | no |
| US-0072 | validate and cap the layout route length | P1 | BR-006, BR-007, BR-009 (partial), BR-013 (partial) | US-0071 | 2 | no |
| US-0073 | shared encodability check and the save refusal | P1 | BR-009 (partial), BR-010, BR-013 (partial), BR-015, BR-016 (partial), BR-017 (partial) | US-0072 | 2 | no |
| US-0074 | patch and record writers refuse unencodable text | P2 | BR-011, BR-012, BR-016 (partial), BR-017 (partial) | US-0073 | 2 | no |
| US-0075 | tracing and logging never break on unencodable text | P2 | BR-019 (partial) | US-0073 | 2 | no |
| US-0076 | deck services refuse unencodable path arguments | P2 | BR-018 (partial) | US-0075 | 2 | no |
| US-0077 | record, server and bind address arguments refused | P2 | BR-018 (partial), BR-019 (partial), BR-021 | US-0076 | 2 | no |
| US-0078 | wait bound, idle close and send side bound | P1 | BR-008, BR-009 (partial), BR-013 (partial), BR-022 (partial) | US-0072 | 1 | no |
| US-0079 | total request bound, slow suite and documentation | P2 | BR-008 (slow checks), BR-013 (partial), BR-014 (partial), BR-020, BR-022 (partial) | US-0074, US-0077, US-0078 | 2 | yes |
