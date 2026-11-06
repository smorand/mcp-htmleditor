# US-0082: A stop releases the port

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P1
> Depends on: US-0081
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective

`stop_http_server` ends the serving loop but never closes the listening socket; every handler thread keeps a
reference to the server, so with a tab open the port stays bound and accepting up to 30 seconds after the stop,
and `start_server` on the same port fails with `Port P is already in use` (BUG-001). This story makes a stop close
the listener, close the idle connections without an answer, let a request already received finish its answer,
and return within 2 seconds, so an immediate restart on the same port works.

`min_tier` 1: the work sits on stdlib internals with silent pitfalls: `shutdown()` alone keeps the socket;
`parse_request` returning `False` must end the request with no bytes; a socket shut with `SHUT_RDWR` must wake the
blocked `recv` of the SPEC-0013 `DeadlineReader` as end of stream (not as a timeout); a connection accepted just
before the stop whose handler has not registered yet must be shut when it registers; the lock must make "busy
before the stop" and "refused after it" exclusive.

## Requirements covered

- SPEC-0014/BR-001: WHEN a stop returns THE editor server SHALL refuse every new TCP connection to its port.
- SPEC-0014/BR-002: WHEN `start_server(file, port=P)` is called after a stop of a server bound to `P` in the same process THE agent tool SHALL answer `{"ok": true, "url": ..., "file": ..., "port": P, "started": true}` and `GET /health` on `P` SHALL answer `200`.
- SPEC-0014/BR-003: WHEN a stop returns THE editor server SHALL have closed, without an answer, every connection on which it had not yet received a complete request line and headers.
- SPEC-0014/BR-004: WHILE a request whose line and headers were fully received before the stop is being processed THE editor server SHALL send its normal answer.
- SPEC-0014/BR-005: The stop SHALL return within 2 seconds of being called, whatever connections are open.
- SPEC-0014/BR-006: IF `stop_server()` is called while no server runs in the process THEN THE agent tool SHALL answer `{"ok": true}` and change nothing.
- SPEC-0014/BR-007: WHEN a stop returns THE agent tool `get_status()` SHALL report `"running": false`.

Business rules (spec): BR-001 holds whatever connections were open at the stop; "refuse" means the connect fails
with `ECONNREFUSED`, not a connection left unanswered. BR-002 holds immediately after the stop returns, with or
without connections open at the stop time; no delay or retry on the caller's side. BR-004: the stop does not wait
for that answer to return. "Stop" means any of the three stop paths: the agent tool `stop_server`, the end of
`mcp-htmleditor serve` on Ctrl+C (prints `Stopping server.`), and the end of a test fixture that started a server.

## Independent Test

`make test ARGS='-k server_lifecycle'` (part of `make check`): in process, start on a free port `P`, open an idle
TCP connection, call `stop_http_server()`: it returns within 2 seconds, `socket.create_connection(("127.0.0.1", P),
timeout=1)` raises `ConnectionRefusedError`, the idle connection reads `b""`, and `start_http_server(D, port=P,
host="127.0.0.1")` returns `(True, P)` at once (red today: the connect is accepted and never answered, the restart
raises `OSError` while the idle connection lives).

## Design excerpt

### Decisions
- DEC-001 (SPEC-0014): "`stop_http_server` takes the instance under `_server_lock`, clears `_server_instance` and `_server_thread`, then calls `server.shutdown()`, `server.server_close()` and `server.connections.close_idle()` in that order, logs `HTTP server stopped`, and saves the state as today. The no server branch is unchanged." `ThreadingHTTPServer.daemon_threads = True` makes `server_close` join nothing (stdlib `socketserver.py:705` to `:715`), so the stop returns after at most one poll interval (0.5 s).
- DEC-002 (SPEC-0014): "A new module `src/mcp_htmleditor/http_connections.py` holds `ConnectionRegistry`: one lock, a map socket to busy flag, a `closing` flag. `close_idle` sets `closing` and calls `shutdown(socket.SHUT_RDWR)` on every idle socket; `add` while closing shuts the new socket at once." Shutting a socket wakes the handler blocked in `recv` with end of stream, which the stdlib ends silently.
- DEC-003 (SPEC-0014): "`setup` registers `self.connection` after the SPEC-0013 wrappers; `parse_request` is overridden so that, once `super().parse_request()` returns `True` (request line and headers complete), `begin_request` is called, and `False` from it sets `close_connection` and returns `False` with no answer; `handle_one_request` calls `end_request` in a `finally` when a request began, and sets `close_connection` when it returns `True`; `finish` removes the socket in a `finally`."
- DEC-004 (SPEC-0014): "No change to `start_http_server` or to the bind: the restart works because the listener is closed and `allow_reuse_address` is already set by the stdlib." (stdlib `http/server.py:143`).
- DEC-005 (SPEC-0014): "`stop_http_server` loses its `# pragma: no cover` and is measured by the in process lifecycle tests; `http_connections.py` has no pragma. `_EditorHandler` keeps its class level pragma."
- DEC-006 (SPEC-0014): "BR-004 text governs a stop arriving while a body is still being received: the request line and headers are complete, so the request is busy and gets its normal answer (`200` when the body completes; the SPEC-0013 `408` after the wait bound when it never does, file unchanged in that case)."
- DEC-017 (SPEC-0014): "The `serve` Ctrl+C path is checked by a subprocess test: `mcp-htmleditor serve <D> --port P` with `BROWSER=true`, wait for `Serving on`, send `SIGINT`, expect exit 0, `Stopping server.` on stdout, and `ConnectionRefusedError` on `P`."
- DEC-010 (SPEC-0014): the stdio tests use `tests/stdio_support.StdioSession` (US-0081); no `readline()` on a child's stdout.

### Contracts
```python
# src/mcp_htmleditor/http_connections.py (new; no internal import)
class ConnectionRegistry:
    __slots__ = ("_busy", "_closing", "_lock")

    def __init__(self) -> None: ...
    def add(self, sock: socket.socket) -> None: ...  # idle; when closing: shutdown(SHUT_RDWR) at once
    def remove(self, sock: socket.socket) -> None: ...  # missing is fine
    def begin_request(self, sock: socket.socket) -> bool: ...  # False when closing, else busy
    def end_request(self, sock: socket.socket) -> bool: ...  # idle again; True when closing
    def close_idle(self) -> int: ...  # closing = True; shut every idle socket; return the count
    @property
    def closing(self) -> bool: ...
```
`shutdown` raising `OSError` (peer already gone) is ignored with a DEBUG line `Connection already closed: <ExcType>`.

```python
# src/mcp_htmleditor/http_server.py
class _EditorServer(ThreadingHTTPServer):
    def __init__(self, bind_host: str, port: int) -> None: ...  # + self.connections = ConnectionRegistry()


class _EditorHandler(BaseHTTPRequestHandler):
    def setup(self) -> None: ...  # existing wrappers, then self.server.connections.add(self.connection)
    def parse_request(self) -> bool: ...  # new override (DEC-003)
    def handle_one_request(self) -> None: ...  # existing SPEC-0013 policy + finally end_request (DEC-003)
    def finish(self) -> None: ...  # new override: try super().finish() finally connections.remove(...)


def stop_http_server() -> None: ...  # DEC-001; pragma removed
```
Agent answers unchanged: `stop_server()` returns `{"ok": true}`; `get_status()` returns `"running": false` after a
stop; `start_server` returns `{"ok": true, "url": ..., "file": ..., "port": P, "started": true}`; the explicit port
error stays `Port P is already in use (pass no --port to auto-pick a free one in 7840-7849, or choose another port explicitly): ...`.
`self.server` is typed `socketserver.BaseServer` in the stdlib stubs: use `cast(_EditorServer, self.server)`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_connections.py` | create |
| `src/mcp_htmleditor/http_server.py` | modify: `_EditorServer.__init__`, `_EditorHandler.setup`, `parse_request` (new), `handle_one_request`, `finish` (new), `stop_http_server` |
| `tests/test_server_lifecycle.py` | create: BT-010, BT-011, BT-012, registry unit tests, `serve` Ctrl+C |
| `tests/test_server_lifecycle_stdio.py` | create: BT-001, BT-013, BT-020, BT-021 |
| `README.md` | modify: row `stop_server()` (`README.md:345`) to `Stop the HTTP server: its port is released at once, idle connections are closed, a request already received is answered.` |
| `.agent_docs/architecture.md` | modify: the stop sequence and the registry (dated entry) |

### Existing patterns
- Handler and SPEC-0013 policy: `src/mcp_htmleditor/http_server.py:110` to `:170` (`setup`, `handle_one_request`, `_answer_best_effort`); server `:927`; start and stop `:1009` to `:1091`.
- Stdlib to read before coding: `socketserver.py` `shutdown` (`:247`), `ThreadingMixIn.process_request` and `server_close` (`:683` to `:715`), `StreamRequestHandler.setup` and `finish`; `http/server.py` `handle_one_request` and `parse_request`.
- In process server fixture: `tests/conftest.py:233` `serve_deck` and `_wait_listening`; raw sockets: `tests/http_support.py` (`exchange`, `RawReply`, `json_body`).
- Stdio session: `tests/stdio_support.py` (US-0081).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Conventions (Spec section 4): `P` is a free port obtained by binding port 0 and closing; `D` is a copy of the `doc`
bootstrap under `tmp_path`; `HTMLEDITOR_STATE_DIR` set to `tmp_path`; `HTMLEDITOR_HOST=127.0.0.1`; `BROWSER=true`
(no browser opened). The stdio process gets the same three variables in its env. Every test of this story ends
with the server stopped.

### SPEC-0014/BT-001: Restart on the same port with a tab open
- Level / Driver / Location: functional e2e; a real `mcp-htmleditor mcp` process over stdio (`StdioSession`), plus a raw TCP socket; `tests/test_server_lifecycle_stdio.py`
- Red before the fix because: the stop never closes the listening socket and the idle connection's handler keeps it alive (E3 to E6): the second call answers `isError` with `Port P is already in use`.
- Given `start_server(file=D, port=P)` answered `"started": true` and a TCP connection to `127.0.0.1:P` is open and idle
- When `stop_server()` is called, then `start_server(file=D, port=P)`
- Then `stop_server` answers `{"ok": true}` and the second call answers without `isError`, with `"port": P` and `"started": true`
- And `GET /health` on `P` answers `200`, and the idle connection reads end of stream (`b""`) within 2 seconds of the stop

### SPEC-0014/BT-010: Stop refuses new connections
- Level / Driver / Location: functional e2e; in process; `tests/test_server_lifecycle.py`
- Given a server on `P` started in process, and an idle TCP connection to it
- When the stop is called
- Then it returns within 2 seconds and `socket.create_connection(("127.0.0.1", P), timeout=1)` raises `ConnectionRefusedError`

### SPEC-0014/BT-011: A received request is answered across the stop
- Level / Driver / Location: functional e2e; in process, raw TCP sockets; `tests/test_server_lifecycle.py`
- Given a server on `P` serving `D`, a connection that sent a full save `POST /content` (`Content-Type: application/json`, body `{"html":"<!DOCTYPE html><html><body><p>LAST</p></body></html>"}`, `Host: 127.0.0.1:P`, correct `Content-Length`) whose answer is not yet read, and a second connection that sent only `POST /content HTTP/1.1\r\n`
- How "received but not answered" is made deterministic: the test patches `mcp_htmleditor.http_server.write_save` (the route's write step) with a wrapper that sets a `threading.Event` then waits on a second event before calling the original; the test waits for the first event (headers and body received, request busy), calls the stop in the test thread, then releases the second event
- When the stop is called
- Then the first connection reads `200` with `{"ok": true, "mtime": <number>}` and `D` contains `<p>LAST</p>`
- And the second connection reads end of stream with no bytes
- And the stop returned within 2 seconds although the first request was still in progress (BR-005)

### SPEC-0014/BT-012: Restart loop
- Level / Driver / Location: functional e2e; in process; `tests/test_server_lifecycle.py`
- When start on `P`, an idle connection opened, stop, repeated 20 times
- Then every start answers `(True, P)` and `GET /health` answers `200` each time

### SPEC-0014/BT-013: Stop twice and status
- Level / Driver / Location: functional e2e; `StdioSession`; `tests/test_server_lifecycle_stdio.py`
- When `stop_server()` is called over stdio after a start, then again
- Then both answer `{"ok": true}` and `get_status()` answers `"running": false`

### SPEC-0014/BT-020: Stop and serve as today without connections
- Level / Driver / Location: functional e2e (non regression of SPEC-0001/FR-009, FR-031); `StdioSession`; `tests/test_server_lifecycle_stdio.py`
- When `start_server(file=D)` with no port, `start_server(file=other)` (a second `doc` copy; switches file, `"started": false`), `stop_server()`
- Then the answers are as today (`"ok": true`; the first `"started": true` with a port in 7840 to 7849 or the preferred one; the second `"started": false` with the same port) and `get_status()` reports `"running": false`

### SPEC-0014/BT-021: Explicit port taken still explained
- Level / Driver / Location: functional e2e (non regression of SPEC-0001/FR-032); `StdioSession`, a listener held by the test process; `tests/test_server_lifecycle_stdio.py`
- Given another process listens on `P` (the test process itself: a socket bound without `SO_REUSEADDR` and listening; the stdio child is another process)
- When `start_server(file=D, port=P)`
- Then the tool error starts with `Port P is already in use (pass no --port to auto-pick a free one in 7840-7849`

### Support tests of this story (not spec ids)
- `ConnectionRegistry` over `socket.socketpair()`: `close_idle` shuts idle sockets (the peer reads `b""`) and leaves busy ones open; `begin_request` returns `False` after `close_idle`; `end_request` returns `True` after `close_idle`; `add` after `close_idle` shuts the socket at once; `remove` of an unknown socket does nothing; `close_idle` on a socket whose peer already closed does not raise.
- `stop_http_server()` with no server: no exception, `is_server_running()` stays `False` (BR-006 in process).
- DEC-017: `serve` on Ctrl+C: subprocess `[sys.executable, "-m", "mcp_htmleditor", "serve", D, "--port", P]` with the conventions' env, read stdout until `Serving on` (bounded by `stdio_support.LINE_TIMEOUT_SECONDS`), send `signal.SIGINT`, `wait(timeout=10)` returns 0, stdout contains `Stopping server.`, then connecting to `P` raises `ConnectionRefusedError`.

## Constraints

- Files not to touch: `src/mcp_htmleditor/mcp_server.py` (answers unchanged), `src/mcp_htmleditor/cli.py`, `src/mcp_htmleditor/http_deadline.py`, existing tests.
- Dependencies not to add: none.
- Patterns to avoid: joining handler threads or turning `daemon_threads` off; `SO_REUSEPORT`; retrying the bind; closing a connection's descriptor from the stopping thread instead of `shutdown(SHUT_RDWR)`; a module level set of connections (the registry belongs to the server instance); `logger.exception`.
- Scope boundary: test reliability work (waits, port range tests) is in other stories.

## Definition of done

- [ ] RED evidence recorded for BT-001, BT-010, BT-011, BT-012 before the production code.
- [ ] Every acceptance test above green; `make check` green with coverage of `http_connections.py` and `stop_http_server` reported; main stays green after the squash.
- [ ] Non regression: the 12 files starting a server in a fixture (E23) pass unmodified; `tests/test_http_time_bounds.py` (SPEC-0013 zero byte, 408, send bound) passes unmodified; `get_status`, `stop_server`, `start_server` answers unchanged.
- [ ] Docs updated: `README.md` `stop_server()` row; `.agent_docs/architecture.md` stop sequence.
- [ ] Self review: full (tier 1), including a walk through of each path at the stop: idle keep alive connection, connection that sent part of a request line, request with headers complete and body in transit (DEC-006), request being answered, connection accepted but not yet registered, second stop, stop with no server.
- [ ] One commit `US-0082: A stop releases the port`, body `Spec: SPEC-0014` and BR-001 to BR-007.
