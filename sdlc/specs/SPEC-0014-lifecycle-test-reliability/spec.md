# A stopped server keeps its port, and the test gate depends on timing and on the machine: Bug Specification

> Generated on: 2026-11-05
> Id: SPEC-0014
> Nature: BUG
> Depth: M
> Depth evidence: 2 modules (editor HTTP server lifecycle, test suite and its configuration); 16 requirements; no public HTTP contract change; no data model change
> Status: designed
> Verdict: authority exists (BUG-001, BUG-004); no authority (BUG-002, BUG-003)
> Defect class: n/a for BUG-001 and BUG-004; absent for BUG-002 and BUG-003
> Severity: Low (BUG-001, BUG-002, BUG-003), Medium (BUG-004: makes the only quality gate machine dependent)
> From backlog: BL-0004, BL-0022, BL-0024
> Security: n/a
> CVSS: n/a
> Affected: every version up to 7486981 (main, 2026-11-05)
> Fixed in: unreleased

Four defects of one family: a lifecycle step or a test outcome depends on something other than
the code under test (a lingering reference, the machine's speed, a silent child, another process
holding a port). File and line citations are in the Evidence appendix (E ids). Every reproduction
below was run on 7486981 through `make test` with throwaway test files kept outside the
repository (`/tmp/spec14/`).

## 1. Defect

### BUG-001: Stopping the editor server leaves its port bound and accepting connections

- **Observed behavior:** reproduced on 2026-11-05.
  1. Over stdio (`mcp-htmleditor mcp`, `HTMLEDITOR_HOST=127.0.0.1`): `start_server(file, port=P)`
     answers `"started":true`; a TCP connection to `127.0.0.1:P` is opened and left idle (what an
     open editor tab does); `stop_server()` answers `{"ok":true}`; `start_server(file, port=P)`
     then returns the tool error `Port P is already in use (pass no --port to auto-pick a free one
     in 7840-7849, or choose another port explicitly): [Errno 48] Address already in use`.
  2. In process, same sequence: after `stop_http_server()` a new TCP connect to `P` is accepted by
     the kernel and never answered.
  3. With no idle connection and no other reference to the server, 100 start and stop cycles on
     one port all succeed: the socket is then closed by garbage collection, not by the stop.
- **Expected per authority:** README `stop_server()`: "Stop the HTTP server." (E1); the tool
  docstring "Stop the WYSIWYG HTTP server." (E2); SPEC-0001/FR-009 lists "stop server" as an agent
  operation. A stopped server neither accepts connections nor holds its port. The restart on the
  same port and the treatment of open connections are decided here.
- **Reproduction:** item 1. Expected: second `start_server` answers `"started":true`, `"port":P`.
  Actual: tool error `Port P is already in use`.
- **Root cause:** `stop_http_server` ends the serving loop with `shutdown()` and drops its
  references (E3), but never closes the listening socket (E4: no `server_close` anywhere in `src`);
  `shutdown()` only stops the loop (E5). The socket lives as long as any object references the
  server, and every handler thread holds one (E6); with the SPEC-0013 idle bound of 30 seconds
  (E7), an idle connection keeps the port bound up to 30 seconds after the stop.
- **Contributing factors:** `stop_http_server` and `start_http_server` are excluded from coverage
  (`# pragma: no cover`, E3, E8) and no test stops then restarts on one port.
- **Impact:** an agent that stops and restarts on an explicit port while a tab is open gets a
  failure; a tab polling a stopped server hangs instead of failing. Workaround: no `port`, or wait
  30 seconds. Low.
- **Rollback posture:** a revert restores today's behavior; nothing persisted changes.

### BUG-002: Browser tests assert asynchronous results after a fixed delay

- **Observed behavior:** `make check` on US-0018 failed once with
  `tests/test_autosave_focus_e2e.py::test_several_saves_lose_nothing[chromium]`
  (`assert 'Titre du document123' in ''`) and `::test_status_dot_returns_to_saved[chromium]`
  (`rgb(194, 150, 62) == rgb(66, 190, 101)`), then passed unchanged (BL-0024); a third,
  `tests/test_undo_redo_e2e.py::test_undo_redo_document_block_insert[chromium]`, did the same in
  US-0026. Reproduced deterministically on 2026-11-05 by answering every `POST /content` 800 ms
  late from the browser side: `test_several_saves_lose_nothing` reads `Titre du document12` while
  the editor goes on to save `123`; the same scenario waiting on the file content passes. CPU load
  alone (30 busy processes on 10 cores, 3 runs) did not reproduce it on this machine.
- **Expected per authority:** none: no requirement states that a test result must not depend on
  the machine's speed. The constitution requires `make check` to pass before merge (E9), which a
  random verdict defeats. The behavior is decided here.
- **Reproduction:** as above. Expected: pass. Actual: `assert 'Titre du document123' in '...Titre du document12...'`.
- **Root cause:** the autosave tests wait a fixed `SAVE_WAIT_MS = 1500` (E10), sized as "800 ms
  typing debounce plus the POST round trip" (E11), then read the file or the status dot once (E12);
  the undo and redo tests wait a fixed 300 ms after each insert, undo and redo before reading the
  DOM once (E13). Any round trip longer than the margin fails the assertion while the editor is
  correct.
- **Contributing factors:** 68 fixed waits across 10 browser test files (E14), copied from one
  file to the next.
- **Impact:** a red gate trains people to rerun it, hiding real failures. Low.
- **Rollback posture:** a revert restores today's tests; no product behavior changes.

### BUG-003: A test can block the whole run forever

- **Observed behavior:** reproduced on 2026-11-05: the stdio helper of
  `tests/test_render_tool.py` fed by a child that starts and never writes stays blocked; the run
  ended only when the outer `timeout 30` killed `make` (exit 124), with no test reported.
- **Expected per authority:** none: nothing bounds a test's duration. Decided here.
- **Reproduction:** as above. Expected: that test fails within a bound, the run goes on and ends.
  Actual: the run never ends.
- **Root cause:** three helpers read the child's output with a `readline()` that has no time
  bound (E15), and the suite has no per test time limit: no plugin or option bounds a test (E16).
- **Contributing factors:** the child is killed only in a `finally` reached after the read (E15).
- **Impact:** a hang in the agent server turns `make check` into a process that never ends,
  rather than a failure naming the test. Low.
- **Rollback posture:** a revert restores today's tests.

### BUG-004: The port range tests fail when another process holds a port of 7840 to 7849

- **Observed behavior:** reproduced on 2026-11-05: with a listener on `127.0.0.1:7842` opened
  without `SO_REUSEADDR` (what a running editor holds),
  `tests/test_port_range.py::test_raises_a_clear_error_when_the_whole_range_is_taken` fails with
  `OSError: [Errno 48] Address already in use` at `tests/test_port_range.py:55`; with the listener
  on `7840`, `test_falls_back_into_the_range_when_preferred_is_taken` also fails at `:25`. The
  format check half of BL-0004 is already fixed: `make format-check` prints `323 files already
  formatted`.
- **Expected per authority:** SPEC-0001/FR-032 ("IF an explicitly requested port is taken, or all
  ten ports are taken THEN THE system SHALL fail with an explicit message instead of a raw error")
  and its test E2E-044, recorded `currently red` because it "depends on a free port range on the
  machine" (E17); the constitution's green gate (E9).
- **Reproduction:** first case above. Expected: `1 passed`. Actual: `OSError` at `:55`.
- **Root cause:** the tests bind every port of the range themselves and treat a refused bind as an
  error (E18), whereas a port held by another process is, for `find_free_port`, simply taken (E19).
- **Contributing factors:** a developer usually has an editor open while running the gate.
- **Impact:** `make check` red on a developer machine with an editor open. Medium.
- **Rollback posture:** a revert restores today's tests.

## 2. Expected Behavior

Casing: tool names and JSON keys lowercase as in the existing answers (`start_server`,
`stop_server`, `get_status`, `ok`, `port`, `started`, `running`). "Stop" means any of the three
stop paths: the agent tool `stop_server`, the end of `mcp-htmleditor serve` on Ctrl+C (prints
`Stopping server.`, E20), and the end of a test fixture that started a server. "Asynchronous
result" means a state the editor reaches after a timer or a network round trip: file content
after an autosave, status dot colour, DOM after an insert, undo or redo, a reload of the preview.

### Server lifecycle (BUG-001)

#### BR-001 [EARS-E]: Stopped port refuses connections
> WHEN a stop returns THE editor server SHALL refuse every new TCP connection to its port.

- **Source:** restored from README `stop_server()` (E1) and SPEC-0001/FR-009.
- **Business Rules:** holds whatever connections were open at the stop. "Refuse" means the
  connect fails with connection refused (`ECONNREFUSED`), not a connection left unanswered.

#### BR-002 [EARS-E]: Same port restartable at once
> WHEN `start_server(file, port=P)` is called after a stop of a server bound to `P` in the same process THE agent tool SHALL answer `{"ok": true, "url": ..., "file": ..., "port": P, "started": true}` and `GET /health` on `P` SHALL answer `200`.

- **Source:** decided here; follows from BR-001 (BL-0022: "`stop_server` followed by
  `start_server` on the same port in one process can fail to bind").
- **Business Rules:** holds immediately after the stop returns, with or without connections open
  at the stop time; no delay or retry on the caller's side.

#### BR-003 [EARS-E]: Open idle connections closed by the stop
> WHEN a stop returns THE editor server SHALL have closed, without an answer, every connection on which it had not yet received a complete request line and headers.

- **Source:** decided here (an open tab must see the server gone, not hang up to 30 seconds).

#### BR-004 [EARS-S]: A request already received is answered
> WHILE a request whose line and headers were fully received before the stop is being processed THE editor server SHALL send its normal answer.

- **Source:** decided here.
- **Business Rules:** the stop does not wait for that answer to return (BR-005).

#### BR-005 [EARS-U]: Stop returns promptly
> The stop SHALL return within 2 seconds of being called, whatever connections are open.

- **Source:** decided here.

#### BR-006 [EARS-O]: Stop without a server unchanged
> IF `stop_server()` is called while no server runs in the process THEN THE agent tool SHALL answer `{"ok": true}` and change nothing.

- **Source:** restored from today's behavior (E3: the branch is skipped when no server runs).

#### BR-007 [EARS-E]: Status after stop
> WHEN a stop returns THE agent tool `get_status()` SHALL report `"running": false`.

- **Source:** restored from today's behavior (E8).

### Timing independent browser tests (BUG-002)

#### BR-008 [EARS-U]: Asynchronous results are awaited, bounded
> The browser test suite SHALL assert every asynchronous result by observing it repeatedly, at most 100 ms apart, until it holds or 10 seconds have passed since the action that triggers it.

- **Source:** decided here.
- **Business Rules:** on failure the assertion reports the last observed value (for example the
  file text or the colour string), as today's single read does.

#### BR-009 [EARS-UB]: No presence assertion after a fixed delay only
> The browser test suite SHALL NOT assert that an asynchronous result is present after a fixed delay without the observation of BR-008.

- **Source:** decided here.

#### BR-010 [EARS-O]: Absence asserted after the cause completed
> IF a browser test asserts that something did not happen (for example the preview was not reloaded) THEN it SHALL first await, per BR-008, the asynchronous step that could have caused it, then observe for a fixed settle delay of at least 1 second before asserting the absence.

- **Source:** decided here (today's `test_self_save_does_not_reload_the_preview` can pass before
  the save it checks has even landed, E21).

#### BR-011 [EARS-U]: Verdicts independent of save latency
> The tests of `tests/test_autosave_focus_e2e.py` and `tests/test_undo_redo_e2e.py` SHALL pass when every `POST /content` answer reaches the browser 2000 ms late.

- **Source:** decided here; 2000 ms is more than twice the latency that reproduces the failure.

### Bounded test duration (BUG-003)

#### BR-012 [EARS-U]: Per test time limit
> The test suite SHALL limit each test to 60 seconds, and each test marked `slow` to 900 seconds.

- **Source:** decided here. The slowest test of the default run takes 6.04 s (E22); the `slow`
  tests exercise the 300 second total bound of SPEC-0013 (E7).

#### BR-013 [EARS-O]: A test over its limit fails alone
> IF a test exceeds its limit THEN THE test run SHALL report that test as failed with its node id and the word `Timeout` in its failure, SHALL run the remaining tests, and `make test` and `make check` SHALL exit with a non zero status.

- **Source:** decided here.

#### BR-014 [EARS-O]: Silent child process fails its test
> IF a child process started by a test writes no complete line on its standard output within 30 seconds of being waited for THEN the test SHALL fail with the message `the server did not answer within 30 s`, and the child SHALL be killed and reaped.

- **Source:** decided here.
- **Business Rules:** applies to the three stdio helpers of E15, and to any test reading a child's
  output line by line.

### Machine independent port range tests (BUG-004)

#### BR-015 [EARS-U]: Same verdict whatever holds the range
> `tests/test_port_range.py` SHALL give the same verdict whatever other process listens, with or without `SO_REUSEADDR`, on any of the ports 7839 to 7849 of any local interface.

- **Source:** restored from SPEC-0001/FR-032 and E2E-044 (E17), and the constitution (E9).
- **Business Rules:** a port held by another process counts as taken; the tests never skip
  because of it.

#### BR-016 [EARS-E]: Whole range taken still asserted
> WHEN every port 7839 to 7849 of `127.0.0.1` is unavailable, whether held by the test or by another process THE test SHALL assert that `find_free_port("127.0.0.1", 7839)` raises `RuntimeError` with the message `No free port available (tried 7839 and 7840-7849): 10 presentations already running? Stop one or pass an explicit --port.`

- **Source:** restored from SPEC-0001/FR-032; message as written today (E19).

## 3. Edge Cases

| Case | Expected behavior | Requirement |
|------|-------------------|-------------|
| Stop called twice | second call answers `{"ok": true}`, no error | BR-006 |
| Stop while a save `POST /content` is mid body | connection closed without answer, file unchanged (SPEC-0009 atomic write) | BR-003 |
| Stop while a save was fully received and is writing | save answered `200`, file written | BR-004 |
| Restart with `port` absent after a stop | the preferred port (7842 when free) is chosen again (SPEC-0001/FR-029) | BR-002 |
| `serve` stopped by Ctrl+C | prints `Stopping server.`, exits 0, port refused afterwards | BR-001 |
| Asynchronous result reached after 9.9 s | assertion passes | BR-008 |
| Asynchronous result never reached | test fails after 10 s with the last value | BR-008 |
| A `slow` test at 400 s | not cut | BR-012 |
| A child that writes a partial line then stops | test fails with the BR-014 message | BR-014 |
| Every port of the range held by other processes | whole range test passes; fallback test passes | BR-015 |

## 4. Tests

Let `P` be a free port obtained by binding port 0 and closing; `D` a copy of the `doc` bootstrap
under `tmp_path`; `HTMLEDITOR_STATE_DIR` set to `tmp_path`; `HTMLEDITOR_HOST=127.0.0.1`;
`BROWSER=true` (no browser opened).

### 4.1 End to end reproduction (mandatory)

#### BT-001: Restart on the same port with a tab open
- **Reproduces:** BUG-001
- **Driver:** a real `mcp-htmleditor mcp` process over stdio (JSON lines), plus a raw TCP socket
- **Fails today because:** the stop never closes the listening socket and the idle connection's handler keeps it alive (E3 to E6)
- Given `start_server(file=D, port=P)` answered `"started": true` and a TCP connection to `127.0.0.1:P` is open and idle
- When `stop_server()` is called, then `start_server(file=D, port=P)`
- Then `stop_server` answers `{"ok": true}` and the second call answers without `isError`, with `"port": P` and `"started": true`
- And `GET /health` on `P` answers `200`, and the idle connection reads end of stream (`b""`) within 2 seconds of the stop

#### BT-002: Autosave and undo tests pass with late saves
- **Reproduces:** BUG-002
- **Driver:** `make test` on Playwright Chromium tests that answer every `POST /content` 2000 ms late (browser side route delay) and run the scenarios of every test of `tests/test_autosave_focus_e2e.py` and `tests/test_undo_redo_e2e.py`
- **Fails today because:** the fixed 1500 ms and 300 ms waits read the result before the round trip ends (E10 to E13)
- Given the delay above
- When the scenario of `test_several_saves_lose_nothing` runs (type `1`, wait 1000 ms, type `2`, wait 1000 ms, type `3`)
- Then `D` contains `Titre du document123`, and every other scenario passes with its existing assertion (for example the status dot colour equals `rgb(66, 190, 101)`)

#### BT-003: A silent stdio server fails its test, the run ends
- **Reproduces:** BUG-003
- **Driver:** the project's test runner started as a child process on a file under `tmp_path`, with the project's test configuration
- **Fails today because:** `readline()` has no bound and no per test limit exists (E15, E16)
- Given that file holds `test_silent`, which calls the stdio helper of `tests/test_render_tool.py` with a child `python -c "import time; time.sleep(3600)"`, and `test_ok`, which asserts `True`
- When the runner is started
- Then it exits with status 1 within 45 seconds, its output contains `test_silent` and `the server did not answer within 30 s`, and `1 passed`
- And no `python -c "import time; time.sleep(3600)"` process remains

#### BT-004: Port range tests with an editor running
- **Reproduces:** BUG-004
- **Driver:** `make test` on `tests/test_port_range.py` run with listeners held by another process
- **Fails today because:** the test binds every port itself and treats `Errno 48` as an error (E18)
- Given a separate process listens without `SO_REUSEADDR` on `127.0.0.1:7840` and `127.0.0.1:7842`
- When `tests/test_port_range.py` runs
- Then `4 passed`, and `test_raises_a_clear_error_when_the_whole_range_is_taken` asserted the exact BR-016 message

### 4.2 New behavior

#### BT-010: Stop refuses new connections
- **Validates:** BR-001, BR-005
- Given a server on `P` started in process, and an idle TCP connection to it
- When the stop is called
- Then it returns within 2 seconds and `socket.create_connection(("127.0.0.1", P), timeout=1)` raises `ConnectionRefusedError`

#### BT-011: A received request is answered across the stop
- **Validates:** BR-004, BR-003
- Given a server on `P` serving `D`, a connection that sent a full save `POST /content` (`Content-Type: application/json`, body `{"html":"<!DOCTYPE html><html><body><p>LAST</p></body></html>"}`) whose answer is not yet read, and a second connection that sent only `POST /content HTTP/1.1\r\n`
- When the stop is called
- Then the first connection reads `200` with `{"ok": true, "mtime": <number>}` and `D` contains `<p>LAST</p>`
- And the second connection reads end of stream with no bytes

#### BT-012: Restart loop
- **Validates:** BR-002
- Given in process
- When start on `P`, an idle connection opened, stop, repeated 20 times
- Then every start answers `(True, P)` and `GET /health` answers `200` each time

#### BT-013: Stop twice and status
- **Validates:** BR-006, BR-007
- When `stop_server()` is called over stdio after a start, then again
- Then both answer `{"ok": true}` and `get_status()` answers `"running": false`

#### BT-014: Bounded observation reports the last value
- **Validates:** BR-008
- Given the autosave scenario of BT-002 with every `POST /content` aborted (as `test_failed_save_keeps_focus` does)
- When a test asserts that `D` contains `Titre du documentQ`
- Then it fails between 10 and 12 seconds after typing, and its failure text includes the current content of `D` (which holds `Titre du document` without `Q`)

#### BT-015: Absence awaited after its cause
- **Validates:** BR-010
- Given every `POST /content` answered 2000 ms late
- When the scenario of `test_self_save_does_not_reload_the_preview` runs
- Then it observes `D` containing `Titre du documentAAA` before asserting the probe, and the probe equals `1`

#### BT-016: A test over its limit fails, the run continues
- **Validates:** BR-012, BR-013
- **Driver:** the test runner as a child process on a file under `tmp_path`, with the project's test configuration
- Given the file holds `test_sleeper` (`time.sleep(120)`), `test_ok` (asserts `True`) and `test_slow_sleeper`, marked `slow`, sleeping 70 seconds, selected with `-m slow`
- When the runner runs `test_sleeper` and `test_ok`
- Then it exits with status 1 in less than 90 seconds, its output names `test_sleeper` with `Timeout`, and shows `1 passed`
- When the runner runs `-m slow` on `test_slow_sleeper`
- Then it reports `1 passed`

#### BT-017: Every stdio helper is bounded
- **Validates:** BR-014
- Given each of the three helpers of E15 fed by the silent child of BT-003
- Then each fails within 35 seconds with `the server did not answer within 30 s`, and the child is gone

#### BT-018: Whole range held by other processes
- **Validates:** BR-015, BR-016
- Given a separate process holds `127.0.0.1` ports 7839 to 7849, without `SO_REUSEADDR`
- When `tests/test_port_range.py` runs
- Then `4 passed`

### 4.3 Non regression

#### BT-020: Stop and serve as today without connections
- **Protects:** SPEC-0001/FR-009, FR-031
- When `start_server(file=D)` with no port, `start_server(file=other)` (switches file, `"started": false`), `stop_server()`
- Then the answers are as today and `get_status()` reports `"running": false`

#### BT-021: Explicit port taken still explained
- **Protects:** SPEC-0001/FR-032
- Given another process listens on `P`
- When `start_server(file=D, port=P)`
- Then the tool error starts with `Port P is already in use (pass no --port to auto-pick a free one in 7840-7849`

#### BT-022: Default run time
- **Protects:** the gate's cost
- When `make check` runs on an unloaded machine
- Then the test step lasts no more than 330 seconds (today 279.55 s, E22) and every test passes

### 4.4 Existing tests asserting the current behavior

| Test file | Test name | Action | Reason |
|-----------|-----------|--------|--------|
| `tests/test_autosave_focus_e2e.py` | all 9 | Modified | each fixed `SAVE_WAIT_MS` or 1000 ms wait before a presence assertion becomes the BR-008 observation; `test_self_save_does_not_reload_the_preview` follows BR-010; assertions unchanged |
| `tests/test_undo_redo_e2e.py` | all 8 | Modified | each 300 ms wait before reading the DOM becomes the BR-008 observation; assertions unchanged |
| `tests/test_fullscreen_e2e.py`, `tests/test_http_header_gate_e2e.py`, `tests/test_http_origin_e2e.py`, `tests/test_requests_editor_e2e.py`, `tests/test_requests_refresh_e2e.py`, `tests/test_review_apply_e2e.py`, `tests/test_save_ui_e2e.py`, `tests/test_website_template_e2e.py` | tests with a fixed wait (E14) | Modified where the wait precedes an asynchronous result, else Kept | BR-008 to BR-010 decide each wait; assertions unchanged |
| `tests/test_render_tool.py` | `test_e2e_005_tool_call_over_stdio` | Modified | its helper gains the BR-014 bound |
| `tests/test_deck_tools_mcp.py` | `test_mcp_process_writes_only_protocol_lines_on_stdout` | Modified | same |
| `tests/test_deck_tools_surface.py` | `test_the_new_tools_write_only_protocol_lines_on_stdout` | Modified | same |
| `tests/test_port_range.py` | `test_falls_back_into_the_range_when_preferred_is_taken`, `test_raises_a_clear_error_when_the_whole_range_is_taken` | Modified | BR-015: a port held by another process counts as taken; assertions unchanged, the second also asserts the BR-016 message |
| `tests/test_port_range.py` | `test_returns_the_preferred_port_when_free`, `test_two_presentations_get_two_different_ports` | Kept | already machine independent (E18) |
| the 12 files starting a server in a fixture (E23) | all | Kept | their teardown now releases the port (BR-001) |
| `tests/test_http_time_bounds.py`, `tests/test_http_time_bounds_slow.py` | all | Kept | socket reads already bounded by the server under test; the slow file is covered by the 900 s limit |

## 5. Existing Specs Affected

Existing specs are not modified; this spec supersedes the statements below.

- SPEC-0001/E2E-044: recorded `currently red`; once BR-015 holds it is green on any machine.
  FR-032 is unchanged.
- SPEC-0001/FR-009: unchanged; "stop server" now also releases the port (BR-001 to BR-005).
- SPEC-0004/BT-001, BT-010 to BT-014, BT-020 to BT-022: their "1500 ms waited" steps become the
  BR-008 observation; their Then clauses are unchanged.
- SPEC-0013/BT-031 ("1500 ms waited"): same.

## 6. Assumptions

Decisions taken without asking (the user asked for recommended defaults and no questions):

- **Decision:** a request fully received before the stop is answered; anything else is closed
  without an answer (BR-003, BR-004); the stop returns within 2 seconds (BR-005).
- **Decision:** observation every 100 ms at most, bound 10 seconds (BR-008); settle delay at least
  1 second for absences (BR-010); latency target 2000 ms (BR-011).
- **Decision:** per test limits 60 seconds and 900 seconds for `slow` (BR-012); a timed out test
  fails alone and the run continues (BR-013); the stdio read bound is 30 seconds with the exact
  message of BR-014.
- **Decision:** a port held by another process counts as taken, never a skip (BR-015).
- **Assumption:** BL-0024's failures came from round trip latency; CPU load alone did not
  reproduce them here, injected latency did (BUG-002). BR-011 covers latency of any origin.
- **Not in scope:** the format check half of BL-0004 (already fixed, `make format-check` green);
  the backlog's naming of a plugin for BR-012 is left to `/sdlc-design`.
- **Overshoot:** none.
- **Backlog entries:** consumed BL-0004, BL-0022, BL-0024. None created.

## 7. Implementability Checklist

| # | Item | Result |
|---|---|---|
| 1 | No technical decision | PASS: no mechanism, plugin, file list or order; root causes point to Evidence lines |
| 2 | No buried requirement | PASS: refusal, restart, idle close, in flight answer, stop delay, status, observation, absence, latency, limits, timeout reporting, child bound, range verdict each have a BR |
| 3 | Names spelled | PASS: tools, JSON answers, messages (`the server did not answer within 30 s`, BR-016 message, `Timeout`), marker `slow`, ports, files |
| 4 | No forced choice | PASS: open connections at stop, in flight requests, stop delay, poll period, bounds, timed out test outcome, held ports stated |
| 5 | Tests specified | PASS: BT-001 to BT-004, BT-010 to BT-018, BT-020 to BT-022 with concrete data; 4.4 covers every file in the radius (E14, E15, E18, E23) |
| 6 | Reproduction end to end | PASS: BT-001 drives the stdio agent server; BT-002 the browser; BT-003 the test runner as a user runs it; BT-004 `make test` with a foreign listener; each fails today for its root cause (reproduced, section 1) |
| 7ante | Security classification | PASS: no bypass, injection, exposure or traversal; `Security: n/a` |
| 7bis | Sweep | n/a (not a vulnerability) |
| 8 | No hidden prerequisite | PASS: state dir, host, browser setting, ports and listeners in every Given |
| 9 | EARS clean | PASS |
| 10 | Right tool | PASS: behavior changes (stop releases the port, test verdicts), no new capability |
| 11 | Length | PASS: within the M budget |
| 12 | Claims cited | PASS: Evidence appendix, counts recounted on 7486981 |
| 13 | Round trip | PASS: start and stop read together (E3, E8), handler reference (E6), helper writer and reader (E15), `find_free_port` and its test (E18, E19) |
| 14 | Verdict consistent | PASS: BUG-001 and BUG-004 restore README, FR-009, FR-032; BUG-002 and BUG-003 named `absent` and decided |

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | amended in place: 2 (BL-0022 cited `http_server.py:722-724`, now `:1078` to `:1081`, E3; BL-0004 cited the bind at `:52`, the failing line is `:55`, and the fallback test at `:25` is also affected); moved to backlog: none |

## Evidence

All lines read on commit 7486981 (2026-11-05), Python 3.14.2, macOS, 10 cores.

- E1 `README.md:345` `| stop_server() | Stop the HTTP server. |`
- E2 `src/mcp_htmleditor/mcp_server.py:102` to `:110` tool `stop_server`, docstring "Stop the WYSIWYG HTTP server.", answers `{"ok": True}`
- E3 `src/mcp_htmleditor/http_server.py:1073` to `:1085` `stop_http_server`: `_server_instance.shutdown()` at `:1079`, references set to `None` at `:1080`, `:1081`; `# pragma: no cover` at `:1073`
- E4 `rg -n 'server_close|\.join\(' src`: no `server_close` and no thread join in `src` (the hits are string joins)
- E5 standard library `socketserver.py:247` `shutdown` "Stops the serve_forever loop"; `:489` `server_close` closes the socket; `http/server.py:154` to `:155` `ThreadingHTTPServer` with `daemon_threads = True`
- E6 standard library `socketserver.py:763` `self.server = server` in every request handler
- E7 `src/mcp_htmleditor/http_deadline.py:22` `WAIT_SECONDS = 30.0`, `:23` `TOTAL_SECONDS = 300.0`
- E8 `src/mcp_htmleditor/http_server.py:1009` to `:1070` `start_http_server` (`# pragma: no cover`), thread started at `:1066`; `:1089` to `:1091` `is_server_running` returns whether `_server_instance` is set
- E9 `sdlc/constitution.md:7` "`make check` ... passes before merge"
- E10 `tests/test_autosave_focus_e2e.py:31` `SAVE_WAIT_MS = 1500  # > the 800 ms typing debounce plus the POST round trip`
- E11 `src/mcp_htmleditor/static/editor-save.js:4` debounce `setTimeout(saveContent, 800)`
- E12 `tests/test_autosave_focus_e2e.py:167` to `:179` (`test_several_saves_lose_nothing`), `:231` to `:242` (`test_status_dot_returns_to_saved`): fixed waits then one read
- E13 `tests/test_undo_redo_e2e.py:270` to `:290` `test_undo_redo_document_block_insert`: `wait_for_timeout(300)` then one DOM read, three times
- E14 `rg -c 'wait_for_timeout\(' tests`: 68 in 10 files: autosave 13, undo and redo 23, fullscreen 9, save UI 6, requests refresh 6, origin 4, header gate 2, requests editor 2, website 2, review apply 1
- E15 `tests/test_render_tool.py:87`, `tests/test_deck_tools_mcp.py:143`, `tests/test_deck_tools_surface.py:243`: `process.stdout.readline()` with no bound, kill only in the `finally` that follows
- E16 `pyproject.toml:171` to `:178` `[tool.pytest.ini_options]`: no time limit option; `pyproject.toml:36` to `:39` dev test dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-playwright`, no time limit plugin
- E17 `sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:114` FR-032; `:39` and `:191` E2E-044 `currently red`
- E18 `tests/test_port_range.py:21` to `:31` binds `PORT_RANGE_START` at `:25`; `:48` to `:61` binds 7839 to 7849 at `:55`, each with `SO_REUSEADDR`
- E19 `src/mcp_htmleditor/http_server.py:967` to `:975` `_port_is_free` (refused bind means taken); `:978` to `:1006` `find_free_port` and its message at `:1003` to `:1006`; `src/mcp_htmleditor/config.py:353` to `:354` range 7840 to 7849
- E20 `src/mcp_htmleditor/cli.py:243` to `:249` `serve` prints `Stopping server.` then calls `stop_http_server`
- E21 `tests/test_autosave_focus_e2e.py:219` to `:228` (`test_self_save_does_not_reload_the_preview`) fixed 2500 ms wait then the probe, without awaiting the save
- E22 `make test ARGS="-p no:cacheprovider -q --durations=8"`: `1609 passed, 2 skipped, 5 deselected in 279.55s`; slowest `6.04s` (`tests/test_http_time_bounds.py::test_time_bounds_bt_044_trickling_request_is_cut_by_the_total_bound`)
- E23 `rg -ln stop_http_server tests`: 12 files, 16 calls
- Reproductions (`make test ARGS="-c pyproject.toml -p no:cacheprovider ..."`, files in `/tmp/spec14/`): `test_stdio_stop.py` (BUG-001 item 1), `test_idle.py` and `test_restart.py` (items 2, 3), `test_slow_save.py` (BUG-002: `1 failed` with fixed wait, observation variant passed), `test_hang.py` (BUG-003: exit 124 after 30 s), `test_hold.py` (BUG-004: failures at `:55`, then `:25` and `:55`)
