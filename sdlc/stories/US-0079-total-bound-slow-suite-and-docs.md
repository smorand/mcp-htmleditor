# US-0079: Total request bound, slow suite and documentation

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P2
> Depends on: US-0074, US-0077, US-0078
> min_tier: 2
> Files touched: 7
> Closes spec: yes

## Objective

The wait bound of US-0078 restarts at each byte, so a client sending one byte every 29 seconds still holds a
handler thread forever. This story adds the 5 minute total bound on receiving a request, adds the `slow` test
suite that checks the real 30 second and 5 minute values outside the default `make check`, documents the new
answers for users and agents, and runs the spec converge (full acceptance set and requirement audit).

Files touched is 7 against a tier 2 budget of 5: three of them are documentation paragraphs (low decision
density), kept here because the closing story documents the whole spec.

## Requirements covered

- SPEC-0013/BR-020: WHEN 5 minutes pass after the first byte of a connection without the request line, the headers and the declared body being received in full THE editor server SHALL answer `408` with body `{"error":"Request timeout"}`, close the connection, and leave no side effect.
- SPEC-0013/BR-008 (partial: the checks of the real 30 second value, slow): WHEN 30 seconds pass without any byte received while the editor server waits for a request line, a header line or a declared body THE editor server SHALL answer `408` with body `{"error":"Request timeout"}`, close the connection, and leave no side effect.
- SPEC-0013/BR-013 (partial: the BR-020 refusal): IF a request is refused by BR-001 to BR-004, BR-006 to BR-008 or BR-010 THEN THE editor server SHALL log exactly one warning line starting `Refused <METHOD> <path>: ` followed by the error text of the answer, and SHALL NOT log the request body or a traceback.
- SPEC-0013/BR-014 (partial: the converge check that every existing answer is kept): The editor server SHALL answer requests carrying at most one line of each header named in BR-001, no `Transfer-Encoding`, no folding and a body sent in full within the bounds of BR-008 and BR-020, exactly as it does today.
- SPEC-0013/BR-022 (partial: the total bound and the slow selection): The editor server SHALL let the test suite run it with shorter wait and total bounds than 30 seconds and 5 minutes, and SHALL then behave exactly as BR-008, BR-009, BR-013 and BR-020 state, with the shorter values in place of the real ones.

Business rules (spec): the total bound covers receiving the request only, not running it nor sending the
answer; logged as BR-013 states. 5 minutes is fixed for users like the wait bound (only the test suite may
shorten it): no option, no `--help` entry, no user documentation line names a way to change it. The slow tests
are not selected by the default `make check`.

## Independent Test

`make test ARGS='-k time_bounds'` (default run): with `W` = 1 s and `T` = 4 s, a `POST /content` declaring 100
bytes that then sends one byte `{` every 0.6 seconds receives, between 4 and 6 seconds after its first byte,
`408 {"error": "Request timeout"}` and exactly one warning `Refused POST /content: Request timeout` (red before:
the trickle is never cut). Then `make test ARGS='-m slow'` runs the five real value tests.

## Design excerpt

### Decisions
- DEC-013 (SPEC-0013): "`WAIT_SECONDS = 30.0` and `TOTAL_SECONDS = 300.0`, read through the module object at each use." Reader algorithm, step 1 added by this story: "`_arm()`: `timeout = http_deadline.WAIT_SECONDS`; when `started_at` is set, `remaining = started_at + http_deadline.TOTAL_SECONDS - clock()`; `remaining <= 0` raises `RequestTimeout(has_bytes=True)`; else `timeout = min(timeout, remaining)`. Then `sock.settimeout(timeout)`." `started_at` is the clock value when the first byte of the connection was received (the server answers HTTP/1.0 and closes, so one request per connection). The total never applies to writes (`DeadlineWriter` sets its own timeout per chunk).
- DEC-017 (SPEC-0013): "Real bound tests carry `@pytest.mark.slow`; `pyproject.toml` `[tool.pytest.ini_options]` gains `markers = ["slow: real 30 second and 5 minute time bounds, not run by make check"]` and `addopts = "-m 'not slow'"`. They run with `make test ARGS='-m slow'` (the last `-m` wins in pytest). No new Makefile target."
- DEC-015 (SPEC-0013, landed in US-0078): a `RequestTimeout` with bytes answers `408` and logs `Refused <M> <path>: Request timeout`.

### Contracts
- `src/mcp_htmleditor/http_deadline.py`: `DeadlineReader` records `started_at` at the first byte and `_arm()` applies `TOTAL_SECONDS` as above; nothing else changes.
- `pyproject.toml`: `markers` and `addopts` as DEC-017.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_deadline.py` | modify: total bound in `_arm`, `started_at` |
| `tests/test_http_time_bounds.py` | modify: add BT-044 and unit tests of the total bound with a fake clock |
| `tests/test_http_time_bounds_slow.py` | create: BT-003, BT-015, BT-022, BT-023, BT-040, each `@pytest.mark.slow` |
| `pyproject.toml` | modify: `markers`, `addopts` |
| `README.md` | modify: one paragraph on the editor server answers: duplicated or ambiguous headers `400`, `408 Request timeout` after 30 s of silence or 5 min per request, `413` on `/arch-layout` above 1 MiB, unencodable text and file names refused with one line; no mention of any way to change the bounds |
| `AGENTS.md` | modify: key commands, `make test ARGS='-m slow'` for the real time bound tests |
| `.agent_docs/testing.md` | modify: the `slow` marker, the short bound seam (`monkeypatch.setattr(http_deadline, ...)`), `tests/http_support.py`, `tests/trace_support.py` |

### Existing patterns
- US-0078 tests in `tests/test_http_time_bounds.py` (bound monkeypatching, raw socket timing); `tests/http_support.py`.
- `Makefile:83` `test` target (`ARGS` appended after the configured options).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc. The slow tests
> run through `make test ARGS='-m slow'`, once, before marking the story done.

Conventions (Spec section 4): real server on `127.0.0.1:P` serving `deck.html` (carbon bootstrap copy titled
`ORIGINAL-SECRET`); raw TCP sockets; `L` is `127.0.0.1:P`; log lines exact.

### SPEC-0013/BT-044: A trickling request is cut by the total bound, short bounds
- Validates BR-020, BR-013, BR-022 (default run counterpart of BT-040). Location `tests/test_http_time_bounds.py`.
- Given the server runs with the bounds shortened to `W` = 1 s and `T` = 4 s, and log capture at WARNING
- When `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n` is sent, then one byte `{` every 0.6 seconds (each gap shorter than `W`)
- Then between 4 and 6 seconds after the first byte the status is `408` and the body is `{"error": "Request timeout"}`, the server closes the connection, and exactly one warning record equals `Refused POST /content: Request timeout`
- And `deck.html` is unchanged and `os.listdir` of its folder is the same as before

### SPEC-0013/BT-003: A stalled body is answered and released (slow)
- Reproduces BUG-002. Location `tests/test_http_time_bounds_slow.py`, `@pytest.mark.slow`, real bounds.
- When the client sends `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{` and then nothing
- Then between 30 and 35 seconds after the last byte the status is `408` and the body is `{"error": "Request timeout"}`, and the server then closes the connection
- And `deck.html` is unchanged

### SPEC-0013/BT-015: Stalled connections do not block others (slow)
- Given 20 connections each sent `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{`
- When a normal `GET /content` with `Host: L` is sent while they stall, and again 35 seconds later
- Then both normal requests answer `200` with `ORIGINAL-SECRET`, and every stalled connection has received `408 {"error": "Request timeout"}` and been closed by the server at the second request
- And `deck.html` is unchanged

### SPEC-0013/BT-022: Progressing slow upload is not cut (slow)
- When a valid save body of 60 bytes is sent 10 bytes at a time, 10 seconds apart (50 seconds in total)
- Then the answer is `200 {"ok": true, "mtime": <number>}` and `deck.html` holds the new content

### SPEC-0013/BT-040: A trickling request is cut by the total bound (slow)
- When `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n` is sent, then one byte `{` every 20 seconds
- Then between 300 and 305 seconds after the first byte the status is `408` and the body is `{"error": "Request timeout"}`, the server closes the connection, and one warning line equals `Refused POST /content: Request timeout`
- And `deck.html` is unchanged

### SPEC-0013/BT-023: Idle connection closed (slow)
- When a connection is opened and nothing is sent
- Then between 30 and 35 seconds later the server closes it without sending any byte
- And no log line was added; a second connection that sent `GET /con` and then nothing receives `408 {"error": "Request timeout"}` 30 to 35 seconds later, and exactly one warning log line equals `Refused - -: Request timeout`

### Unit tests of this story
- `DeadlineReader` with a fake clock: after a first byte at t=0 and the clock at `TOTAL_SECONDS`, the next read raises `RequestTimeout(has_bytes=True)` even though bytes keep arriving; before the first byte only `WAIT_SECONDS` applies (an idle connection is never cut by the total).

## Constraints

- Files not to touch: `src/mcp_htmleditor/http_server.py` (the handler policy is US-0078), `src/mcp_htmleditor/config.py`, `src/mcp_htmleditor/cli.py`, the `Makefile` Python targets.
- Dependencies not to add: none.
- Patterns to avoid: documenting the module constants or the monkeypatch seam in `README.md` or `--help` (BR-022: only `.agent_docs/testing.md`, which is contributor documentation); a slow test without the marker; `time.sleep` loops longer than the stated bounds.
- Scope boundary: closing story; any requirement left uncovered is a converge failure, not new scope.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (BT-044 and the total bound unit test red until `_arm` applies `TOTAL_SECONDS`).
- [ ] Every acceptance test above green; `make check` green (slow tests not selected); `make test ARGS='-m slow'` green once, its output recorded in the story commit body; main stays green after the squash.
- [ ] Non regression: every test listed in Spec section 4.4 passes (kept tests unmodified; only the docstring of `test_length_checks_apply_to_the_save_endpoint_only` was changed, by US-0072).
- [ ] Docs updated: `README.md`, `AGENTS.md`, `.agent_docs/testing.md` as listed above.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] Closes spec: the spec's full acceptance set green: BT-001 to BT-048 (BT-003, BT-015, BT-022, BT-023, BT-040 through `make test ARGS='-m slow'`, every other through `make check`); and every requirement BR-001 to BR-022 of SPEC-0013 cited by at least one story of US-0071 to US-0079 with status done or landed (`rg -o 'SPEC-0013/BR-[0-9]{3}' sdlc/stories/ | sort -u` lists 22 ids).
- [ ] One commit `US-0079: Total request bound, slow suite and documentation`, body `Spec: SPEC-0013` and BR-008, BR-013, BR-014, BR-020, BR-022.
