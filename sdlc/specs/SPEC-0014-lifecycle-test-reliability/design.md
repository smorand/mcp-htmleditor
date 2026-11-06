# SPEC-0014: A stopped server keeps its port, and the test gate depends on timing and on the machine, design

> Spec: sdlc/specs/SPEC-0014-lifecycle-test-reliability/spec.md
> Nature: BUG
> Depth: M
> Security: n/a
> Designed on: 2026-11-06
> Target tier: 2 (user instruction for this run: tier 2 by default, stories with silent pitfalls at `min_tier` 1; no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

Run mode: unattended (the user asked for no questions and the recommended defaults). The one new dependency,
`pytest-timeout`, is a dev dependency the spec already requires (BR-012, BL-0004 named a plugin); it stays inside
the existing stack (pytest) and is recorded as DEC-007, version from context7. No new setting, no data format
change, no product behavior change other than the stop (BUG-001).

Project state: existing (`ls src/mcp_htmleditor` lists the package modules; `git log --oneline -1` is
`00f0d9e`).

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| Language, packaging | Python, uv, `make` only | `requires-python >=3.13` (`pyproject.toml:8`) | existing |
| HTTP server | stdlib `ThreadingHTTPServer` (`daemon_threads = True`, `allow_reuse_address = True`, stdlib `http/server.py:143`, `:155`) subclassed as `_EditorServer` (`src/mcp_htmleditor/http_server.py:927`) | stdlib | existing, DEC-001 to DEC-004 |
| Tool protocol | FastMCP (`src/mcp_htmleditor/mcp_server.py:102` `stop_server`) | locked 3.4.6 | existing |
| Tests | pytest 9.1.1 (`uv.lock:1646`), pytest-asyncio, pytest-cov, pytest-playwright (`pyproject.toml:36` to `:39`) | as locked | existing |
| Per test time limit | `pytest-timeout`, `signal` method | 2.4.0, locked (corrected from 2.5.0: 2.5.0 is yanked on PyPI, reason "accidental breaking change (probably)"; 2.4.0 requires `pytest>=7.0.0`) | DEC-007 |

Skills loaded: `python` (via `load_dynamic_context`, injected for this run). Effect: `make check` is the gate
(lint, format-check, typecheck strict, bandit, coverage 80 %); dependencies added with uv and locked
(`uv.lock` committed); tests run through `make test` only (`make test ARGS='...'`); `%` logging; no `print`;
constants at the top of modules; `__slots__` or frozen dataclasses for value objects. Project conventions applied:
`AGENTS.md`, `.agent_docs/testing.md` (slow marker, short bound counterparts pattern of SPEC-0013),
`.agent_docs/architecture.md`, `sdlc/constitution.md` (green gate before merge).

## 2. Approaches

BUG: fix strategies. Four root causes, each fixed at its own site.

### Chosen: fix each root cause where it lives

- BUG-001 (stop never closes the listening socket, E3 to E6): the stop closes the listener itself
  (`server_close`), then closes the idle connections through a small connection registry owned by the server;
  busy connections finish their answer and close (DEC-001 to DEC-004). Root cause site: `stop_http_server`
  (`http_server.py:1073` to `:1085`).
- BUG-002 (fixed delays before reading an asynchronous result, E10 to E14): one test helper module
  `tests/browser_wait.py` with a bounded observation (`wait_until`), a settle step for absences, and a late save
  route used to prove BR-011; each of the 68 waits is rewritten or marked as pacing (DEC-011 to DEC-014).
- BUG-003 (no per test bound, unbounded `readline`, E15, E16): `pytest-timeout` with a 60 second limit and 900
  for `slow` (DEC-007, DEC-008), and one shared bounded stdio session `tests/stdio_support.py` used by the three
  call sites (DEC-010).
- BUG-004 (tests bind the real range and treat a refused bind as an error, E18): the tests treat a refused bind
  as taken; the two tests that need a free part of the range run on a free block of ports (DEC-015).

Pros: no new runtime component; the product change is confined to the stop; the test helpers remove the
duplication that let the fixed waits spread (E14: copied from file to file). Cons: 68 waits must each be judged;
mitigated by the guard test of DEC-014 that makes a forgotten one fail the gate. Affected scope:
`http_server.py`, `http_connections.py` (new), `pyproject.toml`, `uv.lock`, `tests/conftest.py`, three new test
support modules, 14 test files, `README.md`, `.agent_docs/testing.md`, `.agent_docs/architecture.md`.

### Rejected: wait for every handler thread at the stop (`daemon_threads = False`, `block_on_close`)

Summary: let `server_close` join every handler. Rejected (DEC-001): an idle keep alive connection keeps its
handler up to 30 seconds (SPEC-0013 wait bound), so the stop would break BR-005 (2 seconds); joining does not
close the idle sockets either (BR-003).

### Rejected: retry the bind in `start_http_server` until the port frees

Summary: loop on `OSError` for a few seconds. Rejected (DEC-001): the port is never freed while a handler holds a
reference (E6), BR-001 still fails (connections accepted and never answered), and BR-002 forbids a delay.

### Rejected: Playwright `expect(...)` assertions for every observation

Summary: use `expect(locator).to_have_text(..., timeout=10000)`. Rejected (DEC-011): its default polling steps
are 100, 250, 500 and 1000 ms, above the 100 ms ceiling of BR-008, and it cannot observe the file on disk or a
computed colour in the same way; one helper covers file, DOM and style reads.

### Rejected: `timeout_method = "thread"` for the per test limit

Summary: the thread method works even when the main thread is stuck in C code. Rejected (DEC-007): it dumps the
stacks and ends the whole process with `os._exit`, so the remaining tests never run (BR-013).

## 3. Architecture

```
 stop_http_server()  (agent tool stop_server, serve on Ctrl+C, test fixtures)
   │ under _server_lock: take _server_instance, set _server_instance = _server_thread = None
   ├─ server.shutdown()            serve_forever loop ends (poll 0.5 s), no new accept
   ├─ server.server_close()        listening socket closed: new connect -> ECONNREFUSED  (BR-001, BR-002)
   └─ server.connections.close_idle()
          closing = True; every idle connection: shutdown(SHUT_RDWR)  -> its handler reads EOF, ends silently (BR-003)
          busy connections untouched: answer sent, then closed          (BR-004)
   state.server_pid = None; state.save()                                 (BR-007 through is_server_running)

 _EditorHandler (one thread per connection, http_server.py:110)
   setup()            server.connections.add(sock)        (closing already: shut at once)
   parse_request()    super() ok -> connections.begin_request(sock); False while closing -> close, no answer
   handle_one_request()  finally: connections.end_request(sock) -> True while closing -> close_connection = True
   finish()           server.connections.remove(sock)

 tests
   tests/stdio_support.py   StdioSession: bounded line reads (30 s), kill and reap   <- render_tool, deck_tools_mcp,
                                                                                       deck_tools_surface, lifecycle stdio
   tests/browser_wait.py    wait_until (100 ms, 10 s), settle (1 s), answer_saves_late (2000 ms)  <- 10 browser files
   tests/conftest.py        slow items get pytest.mark.timeout(900); pyproject: timeout = 60, signal method
```

Bounded contexts: editor HTTP server lifecycle (BUG-001), test suite and its configuration (BUG-002 to
BUG-004). No product module other than `http_server.py` and the new `http_connections.py` changes.

## 4. Data model

No change. No file, record or state format changes. New constants:
`tests/stdio_support.LINE_TIMEOUT_SECONDS = 30.0`, `tests/browser_wait.OBSERVE_INTERVAL_SECONDS = 0.1`,
`OBSERVE_BOUND_SECONDS = 10.0`, `SETTLE_SECONDS = 1.0`, `LATE_SAVE_MS = 2000`,
`tests/conftest.SLOW_TEST_TIMEOUT_SECONDS = 900`.

## 5. Contracts and interfaces

### 5.1 Product code

```python
# src/mcp_htmleditor/http_connections.py (new; no internal import; unit tested with socket.socketpair, no pragma)
class ConnectionRegistry:
    """Open connections of one editor server and whether each has a request in progress."""

    __slots__ = ("_busy", "_closing", "_lock")

    def __init__(self) -> None: ...
    def add(self, sock: socket.socket) -> None          # idle; when closing already: shutdown(SHUT_RDWR) at once
    def remove(self, sock: socket.socket) -> None       # forget it (missing is fine)
    def begin_request(self, sock: socket.socket) -> bool  # False when closing (caller closes without answer), else busy
    def end_request(self, sock: socket.socket) -> bool    # idle again; True when closing (caller closes the connection)
    def close_idle(self) -> int                          # closing = True; shutdown(SHUT_RDWR) every idle one; count
    @property
    def closing(self) -> bool: ...
```

`shutdown` errors (`OSError`, the peer already gone) are ignored and logged at DEBUG. All state changes happen under
one `threading.Lock`, so a request whose headers complete during the stop is either busy before `close_idle`
(answered, BR-004) or refused by `begin_request` (closed, BR-003), never both.

```python
# src/mcp_htmleditor/http_server.py
class _EditorServer(ThreadingHTTPServer):
    def __init__(self, bind_host: str, port: int) -> None   # + self.connections = ConnectionRegistry()

class _EditorHandler(BaseHTTPRequestHandler):
    def setup(self) -> None            # existing wrappers (SPEC-0013), then self.server.connections.add(self.connection)
    def parse_request(self) -> bool    # new override: ok = super().parse_request(); if ok and not begin_request: close_connection = True, return False
    def handle_one_request(self) -> None   # existing DEC-015 policy (SPEC-0013), plus finally: if a request began and end_request(): close_connection = True
    def finish(self) -> None           # new override: try super().finish() finally connections.remove(self.connection)

def stop_http_server() -> None         # no longer pragma: no cover; DEC-001 sequence
```

The agent tool answers are unchanged: `stop_server()` returns `{"ok": true}` (also with no server, BR-006);
`get_status()` returns `"running": false` after a stop (BR-007); `start_server` keeps its answer
`{"ok": true, "url": ..., "file": ..., "port": P, "started": true}` and its error text
`Port P is already in use (pass no --port to auto-pick a free one in 7840-7849, or choose another port explicitly): ...`
(`http_server.py:1052` to `:1057`). `serve` on Ctrl+C still prints `Stopping server.` and exits 0 (`cli.py:243`).

### 5.2 Test support

```python
# tests/stdio_support.py (new)
LINE_TIMEOUT_SECONDS: float = 30.0
SILENT_CHILD = [sys.executable, "-c", "import time; time.sleep(3600)"]

def mcp_command() -> list[str]                        # [sys.executable, "-m", "mcp_htmleditor", "mcp"]
def silence_message() -> str                          # f"the server did not answer within {LINE_TIMEOUT_SECONDS:g} s"

class StdioSession:                                   # context manager; kills and reaps the child on exit
    def __init__(self, command: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None) -> None: ...
    def send(self, message: dict[str, Any]) -> None: ...
    def read_message(self) -> dict[str, Any]: ...     # one line within LINE_TIMEOUT_SECONDS (read at call time), json
    def initialize(self) -> None: ...                 # initialize (id 1) + notifications/initialized
    def call_tool(self, request_id: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...  # the "result"
    @property
    def messages(self) -> list[dict[str, Any]]: ...   # every message read, in order

def run_session(requests: Sequence[dict[str, Any]], wanted_ids: set[int], *, command: Sequence[str] | None = None,
                cwd: Path, env: Mapping[str, str] | None = None) -> list[dict[str, Any]]: ...
```

A silent child: `read_message` kills the child, waits for it (`wait(timeout=10)`), then calls
`pytest.fail(silence_message())`. The child closing stdout keeps today's message
`the server closed stdout before answering`. A line that is not JSON fails in `json.loads`, as today.

```python
# tests/browser_wait.py (new)
OBSERVE_INTERVAL_SECONDS = 0.1
OBSERVE_BOUND_SECONDS = 10.0
SETTLE_SECONDS = 1.0
LATE_SAVE_MS = 2000


def wait_until(
    page: Page, observe: Callable[[], T], holds: Callable[[T], bool], *, what: str, bound: float = OBSERVE_BOUND_SECONDS
) -> T:
    ...
    # failure: AssertionError(f"{what} not reached within {bound:g} s, last value: {value!r}")


def wait_for_file(page: Page, path: Path, needle: str) -> str: ...  # wait_until on path.read_text(encoding="utf-8")
def wait_for_js(
    page: Page, expression: str, expected: object, *, what: str
) -> object: ...  # page.evaluate(expression) == expected
def settle(page: Page) -> None: ...  # page.wait_for_timeout(SETTLE_SECONDS * 1000)
def answer_saves_late(
    page: Page, delay_ms: int = LATE_SAVE_MS
) -> None: ...  # route "**/content": POST -> fetch, sleep, fulfill
```

### 5.3 Test configuration

`pyproject.toml` `[tool.pytest.ini_options]` gains `timeout = 60` and `timeout_method = "signal"`; the dev group
gains `"pytest-timeout>=2.4.0"`. `tests/conftest.py` gains `SLOW_TEST_TIMEOUT_SECONDS = 900` and a
`pytest_collection_modifyitems` hook adding `pytest.mark.timeout(SLOW_TEST_TIMEOUT_SECONDS)` to every item marked
`slow`. A timed out test fails with `Failed: Timeout (>60.0s) from pytest-timeout.` (pytest-timeout
`PYTEST_FAILURE_MESSAGE`), the run continues, and `make test` and `make check` exit non zero (BR-013).

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `pyproject.toml` | modify: dev dependency, `timeout`, `timeout_method` | BR-012, BR-013 | US-0080 |
| `uv.lock` | modify: `pytest-timeout` 2.4.0 | BR-012 | US-0080 |
| `tests/conftest.py` | modify: slow limit hook | BR-012 | US-0080 |
| `tests/test_suite_time_limit.py` | create: BT-016 (slow) and its short counterparts | BR-012, BR-013 | US-0080 |
| `tests/stdio_support.py` | create | BR-014 | US-0081 |
| `tests/test_stdio_support.py` | create: BT-003, BT-017 (slow) and short counterparts | BR-014 | US-0081 |
| `tests/test_render_tool.py`, `tests/test_deck_tools_mcp.py`, `tests/test_deck_tools_surface.py` | modify: use `stdio_support` | BR-014 | US-0081 |
| `src/mcp_htmleditor/http_connections.py` | create | BR-001, BR-003, BR-004 | US-0082 |
| `src/mcp_htmleditor/http_server.py` | modify: `_EditorServer`, `_EditorHandler` hooks, `stop_http_server` | BR-001 to BR-007 | US-0082 |
| `tests/test_server_lifecycle.py` | create: BT-010, BT-011, BT-012, registry unit tests, `serve` Ctrl+C | BR-001 to BR-005 | US-0082 |
| `tests/test_server_lifecycle_stdio.py` | create: BT-001, BT-013, BT-020, BT-021 | BR-002, BR-006, BR-007 | US-0082 |
| `tests/test_port_range.py` | modify | BR-015, BR-016 | US-0083 |
| `tests/test_port_range_foreign.py` | create: BT-004, BT-018 | BR-015, BR-016 | US-0083 |
| `tests/browser_wait.py` | create | BR-008, BR-010, BR-011 | US-0084 |
| `tests/test_browser_wait.py` | create: unit tests of the helper | BR-008 | US-0084 |
| `tests/test_autosave_focus_e2e.py` | modify: 13 waits, `save_delay`, BT-014, BT-015 | BR-008 to BR-011 | US-0084 |
| `tests/test_undo_redo_e2e.py` | modify: 23 waits, `save_delay` | BR-008, BR-009, BR-011 | US-0085 |
| `tests/test_fullscreen_e2e.py`, `tests/test_website_template_e2e.py`, `tests/test_review_apply_e2e.py`, `tests/test_requests_editor_e2e.py` | modify: 9 + 2 + 1 + 2 waits | BR-008 to BR-010 | US-0086 |
| `tests/test_save_ui_e2e.py`, `tests/test_requests_refresh_e2e.py`, `tests/test_http_origin_e2e.py`, `tests/test_http_header_gate_e2e.py` | modify: 6 + 6 + 4 + 2 waits | BR-008 to BR-010 | US-0087 |
| `tests/test_no_fixed_waits.py` | create: guard | BR-009 | US-0088 |
| `README.md` | modify: `stop_server()` row (`README.md:345`) | BR-001 | US-0082 |
| `.agent_docs/testing.md` | modify | BR-008, BR-012, BR-014 | US-0080, US-0081, US-0084, US-0088 |
| `.agent_docs/architecture.md` | modify: stop sequence | BR-001 | US-0082 |
| `AGENTS.md` | modify: test commands line on limits and helpers | BR-009, BR-012 | US-0088 |

Affected existing tests: as Spec section 4.4, with one deviation: `test_two_presentations_get_two_different_ports`
is modified, not kept (DEC-015). The 12 files starting a server in a fixture are kept (their teardown now
releases the port). `tests/test_http_time_bounds_slow.py` is kept and now runs under the 900 second limit.

Affected documentation: `README.md`, `AGENTS.md`, `.agent_docs/testing.md`, `.agent_docs/architecture.md`.

## 7. Compatibility and risks

- Consumers: agents calling `stop_server` then `start_server` on an explicit port now succeed; an open tab polling
  a stopped server gets a closed connection instead of a hang (its existing error path). No answer text changes.
- Risk R1, stdlib internals of the handler: `parse_request` returning `False` without an error answer ends the
  request with no bytes (stdlib `handle_one_request` returns when `parse_request` is false); a socket shut down with
  `SHUT_RDWR` makes the blocked `recv` of `DeadlineReader` return `b""` (end of stream, no `RequestTimeout`); a
  connection accepted before the stop whose handler has not reached `setup` yet must be shut when it registers
  (`add` while closing). These are why US-0082 is `min_tier` 1.
- Risk R2, the signal method: `SIGALRM` interrupts a blocking read in the main thread (PEP 475 runs the handler
  first, which raises); a test blocked in a non main thread is not interrupted, which is why the stdio bound
  (BR-014) does not rely on it and fires first (30 s < 60 s).
- Risk R3, route handlers in the sync Playwright API run only while the test thread is inside a Playwright call,
  so the observation helper waits with `page.wait_for_timeout`, never `time.sleep` (DEC-011).
- Risk R4, run time: the late variants and the new tests add time while the removed waits save time; the closing
  story measures BT-022 (330 s ceiling).
- Ordering: US-0080 before US-0081 (BT-003 needs both bounds); US-0081 before US-0082 (the stdio lifecycle tests
  use `StdioSession`); US-0084 before US-0085 to US-0087 (helper).
- Rollback: `git revert` of the story commits; nothing persisted changes.
- Dependencies added: `pytest-timeout` 2.4.0 (dev only). Removed: none.

## 8. Security design

n/a (`Security: n/a`, not a vulnerability).

## 9. Test strategy

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| BT-016 | functional e2e, `slow` (real 60 s and 900 s) | test runner as child process (`sys.executable -m pytest -c pyproject.toml -p tests.conftest`) | `tests/test_suite_time_limit.py` | US-0080 |
| BT-003, BT-017 | functional e2e, `slow` (real 30 s) | child runner (BT-003), direct helper call (BT-017) | `tests/test_stdio_support.py` | US-0081 |
| BT-001, BT-013, BT-020, BT-021 | functional e2e | `StdioSession` on `mcp-htmleditor mcp`, raw TCP socket | `tests/test_server_lifecycle_stdio.py` | US-0082 |
| BT-010, BT-011, BT-012 | functional e2e | in process `start_http_server` / `stop_http_server`, raw TCP sockets (`tests/http_support.py`) | `tests/test_server_lifecycle.py` | US-0082 |
| BT-004, BT-018 | functional e2e | child runner on `tests/test_port_range.py`, foreign holder process | `tests/test_port_range_foreign.py` | US-0083 |
| BT-014, BT-015 | functional e2e | Playwright Chromium, `browser_wait` | `tests/test_autosave_focus_e2e.py` | US-0084 |
| BT-002 | functional e2e | Playwright Chromium, `save_delay` = 2000 on every test of both files | `tests/test_autosave_focus_e2e.py`, `tests/test_undo_redo_e2e.py` | US-0085 |
| BT-022 | functional, measurement | `make check` with `--durations` reading | closing report of US-0088 | US-0088 |

BUG reproduction tests, red before and green after: BT-001 (red: `Port P is already in use`), BT-002 (red:
`assert 'Titre du document123' in '...Titre du document12...'` with the fixed waits), BT-003 (red: the run never
ends; its short counterpart is red: the helper blocks until the per test limit), BT-004 (red: `OSError` at
`tests/test_port_range.py:55`).

Default run counterparts of the `slow` tests (support tests, not spec ids): the per test limit with
`-o timeout=2` on a child run (a sleeper of 10 s fails with `Timeout`, a slow test sleeping 3 s passes); the
stdio bound with `stdio_support.LINE_TIMEOUT_SECONDS` monkeypatched to 1.0 (message `within 1 s`, child reaped).

Test data: generated in each test (the `doc` bootstrap copy of Spec section 4, throwaway test files under
`tmp_path`, holder processes). No user provided data.

## 10. Decisions log

- **DEC-001:** `stop_http_server` takes the instance under `_server_lock`, clears `_server_instance` and
  `_server_thread`, then calls `server.shutdown()`, `server.server_close()` and `server.connections.close_idle()`
  in that order, logs `HTTP server stopped`, and saves the state as today. The no server branch is unchanged.
  **Obliged by:** SPEC-0014/BR-001, BR-002, BR-005, BR-006, BR-007. **Rationale:** `shutdown` only ends the loop
  (stdlib `socketserver.py:247`); `server_close` closes the listening socket, so a new connect is refused and the
  port can be bound again at once (`allow_reuse_address = True`, stdlib `http/server.py:143`, tolerates the
  accepted sockets still open); `ThreadingHTTPServer.daemon_threads = True` makes `server_close` join nothing
  (stdlib `socketserver.py:705` to `:715`), so the stop returns after at most one poll interval (0.5 s).
  **Alternatives considered:** joining handler threads (breaks BR-005); retrying the bind (section 2).
  **Source:** design, existing code `http_server.py:1073` to `:1085`. **Evidence:** E3 to E6.
- **DEC-002:** A new module `src/mcp_htmleditor/http_connections.py` holds `ConnectionRegistry` (contract 5.1):
  one lock, a map socket to busy flag, a `closing` flag. `close_idle` sets `closing` and calls
  `shutdown(socket.SHUT_RDWR)` on every idle socket; `add` while closing shuts the new socket at once.
  **Obliged by:** BR-003, BR-004. **Rationale:** the stdlib keeps no list of open connections; shutting a socket
  down wakes the handler blocked in `recv` with end of stream, which the stdlib ends silently (no answer, no log,
  the SPEC-0013 zero byte path), while closing the file descriptor from another thread would not wake it on every
  platform. A separate module stays unit testable without the `pragma: no cover` handler.
  **Alternatives considered:** a set on the handler class (global mutable state shared across servers);
  `socket.close` from the stopping thread (does not reliably wake `recv`). **Source:** design.
  **Evidence:** stdlib `socketserver.py:763` (handler holds the server), E6.
- **DEC-003:** Wiring in `_EditorHandler`: `setup` registers `self.connection` after the SPEC-0013 wrappers;
  `parse_request` is overridden so that, once `super().parse_request()` returns `True` (request line and headers
  complete), `begin_request` is called, and `False` from it sets `close_connection` and returns `False` with no
  answer; `handle_one_request` calls `end_request` in a `finally` when a request began, and sets
  `close_connection` when it returns `True`; `finish` removes the socket in a `finally`. **Obliged by:** BR-003,
  BR-004. **Rationale:** `parse_request` returning is exactly the moment "line and headers fully received";
  ending in a `finally` covers the SPEC-0013 timeout and failure branches. **Alternatives considered:** marking
  busy in `do_GET`/`do_POST` (misses unknown methods, and the body read happens inside them).
  **Source:** existing code `http_server.py:121` to `:145`. **Evidence:** stdlib `http/server.py` `handle_one_request`.
- **DEC-004:** No change to `start_http_server` or to the bind: the restart works because the listener is closed
  and `allow_reuse_address` is already set by the stdlib. **Obliged by:** BR-002. **Rationale:** minimum change;
  the explicit port error text (FR-032, BT-021) stays identical. **Alternatives considered:** `SO_REUSEPORT`
  (would let two servers share a port, hiding FR-032 errors). **Source:** existing code `http_server.py:1050`.
  **Evidence:** stdlib `http/server.py:143`.
- **DEC-005:** `stop_http_server` loses its `# pragma: no cover` and is measured by the in process lifecycle tests;
  `http_connections.py` has no pragma. `_EditorHandler` keeps its class level pragma. **Obliged by:** BR-001 to
  BR-005 (the contributing factor of BUG-001: no coverage, no test). **Rationale:** the stop is now logic worth
  measuring; the handler is still covered only through sockets. **Alternatives considered:** keep the pragma
  (hides a regression). **Source:** design. **Evidence:** E3, E8.
- **DEC-006:** BR-004 text governs a stop arriving while a body is still being received: the request line and
  headers are complete, so the request is busy and gets its normal answer (`200` when the body completes; the
  SPEC-0013 `408` after the wait bound when it never does, file unchanged in that case). Spec section 3 row "mid
  body" cites BR-003 for a closed connection; that row conflicts with the EARS text of BR-003 and BR-004 and has no
  acceptance test. Recorded in `design-issues.md` as non blocking. **Obliged by:** BR-003, BR-004. **Rationale:**
  the EARS requirement is the normative statement, BT-011 tests only the two cases it defines, and the file stays
  unchanged in both readings. **Alternatives considered:** shut busy connections that have not read their whole
  body (contradicts BR-004 as written). **Source:** spec constraint (BR-004 wording). **Evidence:** spec BR-003,
  BR-004, section 3.
- **DEC-007:** Per test limit by `pytest-timeout` 2.4.0, dev dependency `"pytest-timeout>=2.4.0"` added with uv and
  locked; `[tool.pytest.ini_options]` gains `timeout = 60` and `timeout_method = "signal"`. **Obliged by:** BR-012,
  BR-013. **Rationale:** the signal method fails the test with `Timeout (>60.0s) from pytest-timeout.` (an
  `AssertionError`) and the run continues, which BR-013 requires; the thread method ends the process. The plugin is
  the maintained standard (pytest-dev), requires `pytest>=7.0.0` (locked 9.1.1) and supports Python 3.13 and 3.14.
  **Alternatives considered:** the thread method (section 2); a home made `SIGALRM` fixture (reimplements the
  plugin, no ini key); `session_timeout` (bounds the run, not the test). **Source:** spec constraint (BR-012),
  design. **Evidence:** PyPI JSON: 2.5.0 is yanked on PyPI, reason "accidental breaking change (probably)" (2026-08-16), 2.4.0 is the latest
  release, `Requires-Dist: pytest>=7.0.0`; context7 `/pytest-dev/pytest-timeout`: `timeout_sigalrm` raises `pytest.fail(PYTEST_FAILURE_MESSAGE % timeout)`.
- **DEC-008:** The 900 second limit of `slow` tests is applied by a `pytest_collection_modifyitems` hook in
  `tests/conftest.py` that adds `pytest.mark.timeout(SLOW_TEST_TIMEOUT_SECONDS)` to each item carrying the `slow`
  marker (an explicit `timeout` marker on a test is left as is). Child runner tests load the hook with
  `-p tests.conftest`, cwd at the repository root and `-c pyproject.toml`. **Obliged by:** BR-012. **Rationale:**
  pytest-timeout has no per marker setting; a marker on the item has precedence over the ini value. A file under
  `tmp_path` is outside `tests/`, so the conftest must be loaded explicitly. **Alternatives considered:** marking
  each slow test by hand (forgettable); a separate plugin module in `addopts` (loaded before `pythonpath` applies).
  **Source:** design. **Evidence:** pytest-timeout marker precedence (context7 configuration page).
- **DEC-009:** The literal value checks BT-003, BT-016 and BT-017 carry `@pytest.mark.slow` (they need 30 to 130
  seconds each); the default run carries short counterparts: a child run with `-o timeout=2` (sleeper of 10 s
  reported `Timeout`, one other test passing, exit 1; a `slow` test sleeping 3 s under `-m slow -o timeout=1`
  passing, which proves the 900 marker outranks the ini value) and the stdio bound with
  `stdio_support.LINE_TIMEOUT_SECONDS` monkeypatched to 1.0. **Obliged by:** BR-012, BR-013, BR-014; BT-022 (the
  default run stays under 330 s). **Rationale:** same pattern as SPEC-0013 DEC-017: the mechanism is proved in
  seconds on every gate, the literal values on request with `make test ARGS='-m slow'`. **Alternatives considered:**
  literal checks in the default run (about 4 minutes more, breaks BT-022). **Source:** existing code
  `pyproject.toml:178` (`addopts`), SPEC-0013 DEC-017. **Evidence:** E22.
- **DEC-010:** `tests/stdio_support.py` holds `StdioSession` and `run_session` (contract 5.2); a daemon reader
  thread pushes each stdout line into a `queue.Queue`, `read_message` waits `queue.get(timeout=...)` with
  `stdio_support.LINE_TIMEOUT_SECONDS` read at call time; on timeout it kills the child, waits for it, and calls
  `pytest.fail(silence_message())`. The three call sites (E15) and the new lifecycle stdio tests use it; no
  `readline()` on a child's stdout remains in a test. **Obliged by:** BR-014. **Rationale:** a text mode pipe
  buffers ahead, so `select` on the descriptor can miss a line already buffered; a reader thread bounds every line
  whatever the buffering. One helper removes the three copies (E15, zero duplication rule of the python skill).
  **Alternatives considered:** `selectors` on the file descriptor (buffering pitfall); `asyncio` subprocess
  (the three tests are synchronous). **Source:** design, existing code `tests/test_render_tool.py:59` to `:95`.
  **Evidence:** E15.
- **DEC-011:** `tests/browser_wait.wait_until` observes, checks, and waits `page.wait_for_timeout(100)` between
  observations, until the check holds or 10 seconds have passed since the call (the call is made right after the
  triggering action); the failure is an `AssertionError` naming what was awaited and the last observed value
  (`repr`). `wait_for_file` and `wait_for_js` are the two shapes used by the browser files. **Obliged by:** BR-008,
  BR-009. **Rationale:** in the sync Playwright API route handlers and events are dispatched only inside a
  Playwright call, so `time.sleep` would freeze the late save route and the page events; one helper serves file
  content, DOM text and computed styles. **Alternatives considered:** Playwright `expect` (section 2);
  `page.wait_for_function` (cannot read the file on disk, and reports no last value). **Source:** design.
  **Evidence:** E10 to E13, the observation variant of the BUG-002 reproduction (`/tmp/spec14/test_slow_save.py`).
- **DEC-012:** An absence is asserted after `wait_until` on the step that could cause it, then `settle(page)`
  (`page.wait_for_timeout(1000)`), then the assertion. **Obliged by:** BR-010. **Rationale:** the cause is proved
  done before the window starts; 1 second is the floor BR-010 sets. **Alternatives considered:** a longer fixed wait
  alone (today's E21, may pass before the cause). **Source:** spec constraint (BR-010). **Evidence:** E21.
- **DEC-013:** Late saves: `answer_saves_late(page, 2000)` routes `**/content`; a `POST` is sent on with
  `route.fetch()`, the handler sleeps 2 seconds, then `route.fulfill(response=...)`; other methods `continue_()`.
  In `tests/test_autosave_focus_e2e.py` and `tests/test_undo_redo_e2e.py`, a fixture `save_delay` parametrized
  `[0, 2000]` (ids `prompt`, `late`) is a parameter of every existing test and applies the route when not 0.
  **Obliged by:** BR-011. **Rationale:** the server receives and writes the save at once, only the answer reaches
  the browser late, which is exactly BR-011; keeping the `prompt` variant keeps today's path. A route registered
  later by a test (the abort of `test_failed_save_keeps_focus`) wins, as Playwright matches routes in reverse
  order. **Alternatives considered:** delaying on the server side (changes the product path); running only the late
  variant (loses the prompt path). **Source:** design. **Evidence:** the BUG-002 reproduction (800 ms route delay).
- **DEC-014:** A guard test `tests/test_no_fixed_waits.py` reads every `tests/test_*_e2e.py` and fails on each
  `wait_for_timeout(` line that does not carry a trailing comment `# pacing: <reason>` (a spacing between two user
  actions, not followed by an assertion of its result); the settle delay lives only in `tests/browser_wait.py`.
  Each wait story adds the comment to the waits it keeps. **Obliged by:** BR-009. **Rationale:** the 68 waits were
  copied from file to file (E14); the guard makes a new unjustified wait fail the gate. **Alternatives considered:**
  review only (no enforcement). **Source:** design. **Evidence:** E14.
- **DEC-015:** `tests/test_port_range.py`: the whole range test binds each port 7839 to 7849 of `127.0.0.1`
  without `SO_REUSEADDR`, counts a refused bind as taken, and asserts the exact BR-016 message; the fallback test
  and the two presentations test monkeypatch the module constants `mcp_htmleditor.http_server.PORT_RANGE_START`
  and `PORT_RANGE_END` to a block of 10 consecutive ports found free at run time in 30000 to 32000 (preferred port
  just below the block), keeping their assertions; the preferred port test is unchanged. The foreign holder tests
  BT-004 and BT-018 live in `tests/test_port_range_foreign.py` (a holder child binds without `SO_REUSEADDR`, a port
  it cannot bind is already held, which serves the same purpose) and run `tests/test_port_range.py` in a child
  runner. **Obliged by:** BR-015, BR-016. **Rationale:** with every port of the real range held by another process
  (BT-018), `find_free_port` on the real range must raise, so a test asserting a free port inside it cannot pass on
  that machine; the free block keeps the real bind logic and the assertions. The spec's section 4.4 lists the two
  presentations test as Kept; that row cannot hold together with BT-018 (`4 passed`), so BR-015 governs; recorded
  in `design-issues.md` as non blocking. 30000 to 32000 sits below the Linux (32768) and macOS (49152) ephemeral
  ranges. **Alternatives considered:** faking `_port_is_free` (stops testing the bind); skipping when held
  (forbidden by BR-015). **Source:** spec constraint (BR-015, BT-018). **Evidence:** E18, E19.
- **DEC-016:** Story slicing: nine stories. US-0082 (stop lifecycle) at `min_tier` 1, every other at 2. The 68
  waits are split by file group: autosave with the helper (13), undo and redo (23), fullscreen, website, review
  apply and request editor (14), save UI, request refresh, origin and header gate (18). The closing story carries
  the guard, the run time check and the documentation index. **Obliged by:** n/a (no code impact): partition of
  the work; every requirement is covered in section 11. **Rationale:** files touched is the binding budget (3 to 5
  at tier 2); the stop holds silent stdlib pitfalls (R1) above tier 2 density. **Alternatives considered:** one
  story for all browser files (14 files); one story per file (eight stories of one or two waits).
  **Source:** design, user instruction (tier 2, tier 1 for the stop and close lifecycle).
- **DEC-017:** The `serve` Ctrl+C path is checked by a subprocess test in US-0082: `mcp-htmleditor serve <D>
  --port P` with `BROWSER=true`, wait for `Serving on`, send `SIGINT`, expect exit 0, `Stopping server.` on stdout,
  and `ConnectionRefusedError` on `P`. **Obliged by:** BR-001 (the stop paths of Spec section 2 include `serve`).
  **Rationale:** the spec names three stop paths; the tool and fixture paths are covered by BT-001 and BT-010.
  **Alternatives considered:** none needed (same function). **Source:** existing code `cli.py:243` to `:249`.
  **Evidence:** E20.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0080 | per test time limit | P1 | BR-012, BR-013 | main | 2 | no |
| US-0081 | bounded stdio reads in tests | P1 | BR-014 | US-0080 | 2 | no |
| US-0082 | a stop releases the port | P1 | BR-001, BR-002, BR-003, BR-004, BR-005, BR-006, BR-007 | US-0081 | 1 | no |
| US-0083 | port range tests independent of the machine | P1 | BR-015, BR-016 | main | 2 | no |
| US-0084 | bounded observation and the autosave tests | P1 | BR-008 (partial), BR-009 (partial), BR-010 (partial), BR-011 (partial) | main | 2 | no |
| US-0085 | undo and redo tests observe and pass with late saves | P1 | BR-008 (partial), BR-009 (partial), BR-011 | US-0084 | 2 | no |
| US-0086 | fullscreen, website, review and request editor waits | P2 | BR-008 (partial), BR-009 (partial), BR-010 (partial) | US-0084 | 2 | no |
| US-0087 | save ui, refresh, origin and header gate waits | P2 | BR-008 (partial), BR-009 (partial), BR-010 (partial) | US-0084 | 2 | no |
| US-0088 | fixed wait guard, run time and documentation | P2 | BR-008 (partial), BR-009 | US-0082, US-0083, US-0085, US-0086, US-0087 | 2 | yes |
