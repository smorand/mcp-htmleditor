# US-0078: Wait bound, idle close and send side bound

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P1
> Depends on: US-0072
> min_tier: 1
> Files touched: 3
> Closes spec: no

## Objective

The editor server has no socket timeout: a client declaring 100 bytes and sending one holds a handler thread
forever, and so does a client that never sends its request line or never reads an answer (BUG-002). This story
bounds every wait on the connection: 30 seconds without a byte while receiving answers `408` (or closes silently
when the connection never sent a byte), 30 seconds without the client reading an answer closes the connection,
and no request ever ends with a traceback. The bound is fixed for users and shortened only by the test suite.
The total per request bound (BR-020) is the next story.

`min_tier` 1: the work sits on stdlib internals with silent pitfalls (the stdlib swallows a request line
`TimeoutError` without an answer, `request_version` defaults to `HTTP/0.9` which suppresses the status line,
`SocketIO` refuses any read after a timeout, `sendall` treats its timeout as a total).

## Requirements covered

- SPEC-0013/BR-008: WHEN 30 seconds pass without any byte received while the editor server waits for a request line, a header line or a declared body THE editor server SHALL answer `408` with body `{"error":"Request timeout"}`, close the connection, and leave no side effect.
- SPEC-0013/BR-009 (partial: timeouts and the catch all for unexpected failures): The editor server SHALL NOT close a connection without an HTTP answer, or write a traceback to its log, because of the content of a request's line, headers or body.
- SPEC-0013/BR-013 (partial: the BR-008 refusal): IF a request is refused by BR-001 to BR-004, BR-006 to BR-008 or BR-010 THEN THE editor server SHALL log exactly one warning line starting `Refused <METHOD> <path>: ` followed by the error text of the answer, and SHALL NOT log the request body or a traceback.
- SPEC-0013/BR-022 (partial: the wait bound): The editor server SHALL let the test suite run it with shorter wait and total bounds than 30 seconds and 5 minutes, and SHALL then behave exactly as BR-008, BR-009, BR-013 and BR-020 state, with the shorter values in place of the real ones.

Business rules (spec): the 30 seconds restart at each byte received (a slow but progressing upload is not cut).
The answer is best effort: when the client already closed, nothing is sent. Other connections are served
normally during and after the wait. A connection that sent zero bytes (an idle or speculative browser
connection) is closed with no answer and no log line. The same 30 seconds apply to sending an answer: a client
that reads nothing of an answer for 30 seconds has its connection closed, with no further answer possible and no
traceback. BR-009: an unexpected failure while handling a request answers `500` with `{"error":"<message>"}`; the
two closes without answer (zero byte connection, client not reading) are the only exceptions. BR-013: a timeout on
a connection that sent part of a request line but not all of it logs `Refused - -: Request timeout`; a connection
that sent zero bytes logs nothing. BR-022: shortening the bounds never changes any other behavior; it is not a
user visible setting: no command option, no entry of `--help`, no line of the user documentation or of the
configuration listing names it.

## Independent Test

`make test ARGS='-k time_bounds'` (part of `make check`): with `http_deadline.WAIT_SECONDS` monkeypatched to 1.0,
a connection sending
`POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{` and nothing
else receives, between 1 and 3 seconds after its last byte, `408 {"error": "Request timeout"}` and is closed;
`deck.html` is unchanged (red today: no answer, ever).

## Design excerpt

### Decisions
- DEC-013 (SPEC-0013): "The time bounds live in a new module `http_deadline.py` as module constants `WAIT_SECONDS = 30.0` and `TOTAL_SECONDS = 300.0`, read through the module object at each use (`http_deadline.WAIT_SECONDS`), so the test suite shortens them with `monkeypatch.setattr(http_deadline, "WAIT_SECONDS", 1.0)` on an in process server. `_EditorHandler.setup` wraps `self.rfile` in `DeadlineReader` and `self.wfile` in `DeadlineWriter`. The class attribute `timeout` stays `None`." A module constant is not a `Settings` field, an option, an environment variable or a documented setting, so the bound stays fixed for users. These are constants never reassigned by production code. In this story `TOTAL_SECONDS` exists but `_arm` does not apply it yet (US-0079).
- DEC-014 (SPEC-0013): "The send side bound is enforced by `DeadlineWriter`: `sock.settimeout(WAIT_SECONDS)` then `sock.sendall(chunk)` per 64 KiB chunk; a `TimeoutError` becomes `ResponseTimeout`." Python 3.5+ `sendall` treats the timeout as a total for the call; chunking gives "30 seconds without the client reading".
- DEC-015 (SPEC-0013): "`_EditorHandler.handle_one_request` wraps `super().handle_one_request()`: `RequestTimeout` with `has_bytes` false closes silently; with bytes it sets `close_connection`, forces `self.request_version = "HTTP/1.0"` when it is still the stdlib default `HTTP/0.9` (otherwise `send_response` writes no status line, stdlib `http/server.py:292`, `:307`), logs `Refused <command or -> <path or ->: Request timeout` and sends `408 {"error":"Request timeout"}`, any `OSError` while sending ignored; `ResponseTimeout`, `BrokenPipeError`, `ConnectionResetError` close with a DEBUG line; any other `Exception` logs one ERROR line without traceback and, when `send_response` was never called for this request (flag `_answered` set by an override of `send_response`), answers `500 {"error": str(exc)}`." `RequestTimeout` is deliberately not a `TimeoutError`, so the stdlib (`http/server.py:464`) does not swallow it.

### Contracts
```python
# src/mcp_htmleditor/http_deadline.py (new; unit tested, no pragma: no cover)
WAIT_SECONDS: float = 30.0
TOTAL_SECONDS: float = 300.0  # used by US-0079
WRITE_CHUNK_BYTES = 65_536


class RequestTimeout(Exception):
    def __init__(self, *, has_bytes: bool) -> None: ...

    has_bytes: bool


class ResponseTimeout(Exception): ...


class DeadlineReader:
    def __init__(
        self, stream: io.BufferedIOBase, sock: socket.socket, clock: Callable[[], float] = time.monotonic
    ) -> None: ...

    bytes_received: int

    def readline(self, limit: int = -1) -> bytes: ...
    def read(self, size: int = -1) -> bytes: ...
    def close(self) -> None: ...
    @property
    def closed(self) -> bool: ...


class DeadlineWriter:
    def __init__(self, sock: socket.socket) -> None: ...
    def write(self, data: bytes) -> int: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
    @property
    def closed(self) -> bool: ...
```
Reader algorithm (design section 5.1): `_arm()` sets `sock.settimeout(http_deadline.WAIT_SECONDS)` (US-0079 adds
the total); `_peek()` calls `_arm()` then `stream.peek(1)` (one `recv` at most when the buffer is empty);
`TimeoutError`, or the `OSError` a timed out `SocketIO` raises afterwards, becomes
`RequestTimeout(has_bytes=self.bytes_received > 0)`; `b""` is end of stream. `readline(limit)` loops `_peek()`,
takes up to the first `b"\n"` within the remaining limit with `stream.read(k)` (buffered, no blocking), counts
bytes, stops at newline, limit or end of stream. `read(size)` loops `_peek()` and `stream.read(min(len(peeked),
size - len(out)))` until `size` bytes or end of stream. The stdlib calls `rfile.readline(65537)` for the request
line and `http.client.parse_headers(rfile)` (which calls `readline`) for the headers; the routes call `read(n)`.

```python
# src/mcp_htmleditor/http_server.py, class _EditorHandler (still pragma: no cover)
def setup(self) -> None                   # super().setup(); self.rfile = DeadlineReader(self.rfile, self.connection); self.wfile = DeadlineWriter(self.connection)
def handle_one_request(self) -> None      # DEC-015 policy around super().handle_one_request(); reset self._answered = False first
def send_response(self, code: int, message: str | None = None) -> None   # self._answered = True; super()
```
Answers and log lines (exact): `408` body `{"error":"Request timeout"}`; WARNING `Refused POST /content: Request timeout`
(method and path of the request when its line was read), `Refused - -: Request timeout` (request line incomplete);
zero byte connection: no answer, no record; unexpected failure: `500 {"error":"<str(exc)>"}` and one ERROR record
`Request failed: <M> <path>: <ExcType>` without `exc_info`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_deadline.py` | create |
| `src/mcp_htmleditor/http_server.py` | modify: `setup`, `handle_one_request`, `send_response` of `_EditorHandler` |
| `tests/test_http_time_bounds.py` | create: unit tests of the reader and writer (`socket.socketpair()`, fake clock) and the short bound e2e tests |

### Existing patterns
- Handler: `src/mcp_htmleditor/http_server.py:97` `_EditorHandler`, `:536` `_send_json`, `:515` `_send_bytes`; server `:829` `_EditorServer(ThreadingHTTPServer)`.
- Stdlib to read before coding: `http/server.py` `handle_one_request` (`:438` to `:472`), `parse_request` (`:292`, `:306`, `:368`, `:384`); `socketserver.py` `StreamRequestHandler.setup` (`:803` to `:815`) and `finish`.
- Raw socket helper `tests/http_support.py` (US-0071); fixture `serve_deck` (`tests/conftest.py:233`); `monkeypatch.setattr(http_deadline, "WAIT_SECONDS", 1.0)` before the requests (the handler reads the constant at use time, so the order relative to `serve_deck` does not matter).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Conventions (Spec section 4): real server on `127.0.0.1:P` serving `deck.html` (carbon bootstrap copy titled
`ORIGINAL-SECRET`); raw TCP sockets; `L` is `127.0.0.1:P`. Short bounds: wait bound `W` = 1 second
(`http_deadline.WAIT_SECONDS = 1.0`), total bound `T` = 4 seconds (`http_deadline.TOTAL_SECONDS = 4.0`, set even
though only US-0079 applies it). Budget: each of these tests takes less than 7 seconds, together less than 25
seconds (`pytest --durations=0`). Location `tests/test_http_time_bounds.py`.

### SPEC-0013/BT-042: A stalled body is answered and released, short bounds
- Validates BR-008, BR-009, BR-022 (default run counterpart of BT-003 and BT-015). Red before: stalled connections are never answered.
- Given the server runs with the bounds shortened to `W` and `T`
- When 5 connections each send `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{` and then nothing, and a normal `GET /content` with `Host: L` is sent 0.2 seconds later
- Then the normal request answers `200` with `ORIGINAL-SECRET` before any stalled connection is answered
- And each stalled connection receives, between 1 and 3 seconds after its last byte, status `408` with body `{"error": "Request timeout"}`, then the server closes it
- And `deck.html` is unchanged, `os.listdir` of its folder is the same as before, and the log holds no `Traceback`
- And `mcp-htmleditor serve --help` and `mcp-htmleditor new --help` contain no option naming a time bound (no `timeout`, case insensitive)

### SPEC-0013/BT-043: Idle and partial connections, short bounds
- Validates BR-008, BR-013, BR-022 (default run counterpart of BT-023).
- Given the server runs with the bounds shortened to `W` and `T`, and log capture at WARNING on the editor server logger
- When a connection is opened and nothing is sent; and a second connection sends `GET /con` and then nothing
- Then the first is closed by the server between 1 and 3 seconds later without any byte received, and adds no log record
- And the second receives `408 {"error": "Request timeout"}` between 1 and 3 seconds after its last byte, and exactly one warning record was added, equal to `Refused - -: Request timeout`

### SPEC-0013/BT-045: A progressing upload is not cut, short bounds
- Validates BR-008, BR-020, BR-022 (default run counterpart of BT-022).
- Given the server runs with the bounds shortened to `W` and `T`
- When a valid save body of 60 bytes, `{"html":"<!DOCTYPE html><html><body><p>SLOW</p></body></html>"}` padded with spaces after the closing brace to 60 bytes, is sent 10 bytes at a time, 0.5 seconds apart (2.5 seconds in total, under `T`), with the headers sent first and a correct `Content-Length`
- Then the answer is `200 {"ok": true, "mtime": <number>}` and `deck.html` contains `<p>SLOW</p>`

### SPEC-0013/BT-046: A client that stops reading an answer is released, short bounds
- Validates BR-008 (send side), BR-009, BR-022.
- Given the server runs with the bounds shortened to `W` and `T`, and `deck.html` holds, after its body, an HTML comment of 16 MiB of `x` (larger than any socket buffer)
- When a client sends `GET /content HTTP/1.1\r\nHost: L\r\n\r\n`, reads nothing for 4 seconds, then reads until the end of the stream
- Then the bytes read are fewer than the full answer and the stream ends (the server closed the connection)
- And a following `GET /health` answers `200`, `deck.html` is unchanged, and the log holds no `Traceback`

### Unit tests of this story (support coverage of `http_deadline.py`)
- `DeadlineReader` over one end of `socket.socketpair()`: `readline` returns a full line sent in two parts; `read(5)` returns 5 bytes sent one at a time; with `WAIT_SECONDS = 0.2` and nothing sent, `readline` raises `RequestTimeout` with `has_bytes` False; after one byte and silence, `has_bytes` True; end of stream returns `b""`.
- `DeadlineWriter.write` of 200 000 bytes to a reading peer returns 200 000 and the peer receives them in order; with `WAIT_SECONDS = 0.2` and a peer that never reads, writing 16 MiB raises `ResponseTimeout`.
- `RequestTimeout` is not an instance of `TimeoutError`.

## Constraints

- Files not to touch: `src/mcp_htmleditor/config.py` (no setting), `src/mcp_htmleditor/cli.py` (no option), `README.md` and user documentation (no mention of a way to change the bound), existing tests.
- Dependencies not to add: none.
- Patterns to avoid: the handler class attribute `timeout`; a `TimeoutError` subclass for `RequestTimeout`; a single `sendall` for the whole answer; `logger.exception` or `exc_info=True`; reading the constants with `from .http_deadline import WAIT_SECONDS` (the test seam needs the module attribute at use time); an environment variable for the bound.
- Scope boundary: the total bound (BR-020), the slow real value tests and the documentation are US-0079.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green, coverage of `http_deadline.py` reported; main stays green after the squash; the four e2e tests together under 25 seconds in `pytest --durations=0`.
- [ ] Non regression: every HTTP test file (`tests/test_http_*.py`, `tests/test_save_safety_e2e.py`, `tests/test_requests_*e2e.py`, `tests/test_autosave_focus_e2e.py`) and the browser e2e files pass unmodified.
- [ ] Docs updated: none in this story (US-0079).
- [ ] Self review: full (tier 1), including a walk through of each stdlib path: request line timeout, header timeout, body timeout, send timeout, client close.
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0078: Wait bound, idle close and send side bound`, body `Spec: SPEC-0013` and BR-008, BR-009, BR-013, BR-022.
