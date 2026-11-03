# US-0053: Agent lists and completes requests (tools)

> Spec: SPEC-0010 (sdlc/specs/SPEC-0010-request-loop/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0052
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Let the agent read the queue and answer it: tools `list_requests` and `complete_request`, backed by the rules of `RequestService.complete`, with the two lines in the core skill tool list.

## Requirements covered

- SPEC-0010/FR-NEW-002 (partial: the `list_requests` tool): WHEN an agent calls `list_requests` or a user runs `mcp-htmleditor requests <file>` THE Editor SHALL list the requests of that file, oldest first.
- SPEC-0010/FR-NEW-003 (partial: the `complete_request` tool): WHEN an agent calls `complete_request` or a user runs `mcp-htmleditor request-done <file> <id>` or `request-skip <file> <id> --reason <text>` THE Editor SHALL set the request's status to `done` or `skipped`.
- SPEC-0010/FR-NEW-004 (partial: the tool side: a tool error message is the service message without the `error: ` prefix): The Editor SHALL give the same results for requests and review through the command line and the agent tool surface, the tool returning an error whose message is the command line error line without its `error: ` prefix.

## Independent Test

`make test ARGS='-k requests_tools'`: after a request is queued over HTTP, `list_requests` returns it and `complete_request` marks it `done`; the invalid status, the repeated completion and the deleted id each give the exact message of the spec.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0010): "One JSON record per file, not one file per request and not SQLite." A single write holds the counter, the requests and the review, so id allocation, request creation and the applied mark cannot disagree after a crash.
- DEC-002 (SPEC-0010): "Exclusive `fcntl.flock` on a sibling `record.lock` around read, change, atomic rename; readers lock free." `flock` belongs to the open file description, so it excludes other processes and other threads of the threaded editor server (each `update` opens its own descriptor).
- DEC-005 (SPEC-0010): "Rules and messages live only in `RequestService`; surfaces translate (`RequestError.kind` to HTTP status, `ToolError`, `error: ` line)." One source of text makes parity structural (FR-NEW-004).
- DEC-006 (SPEC-0010): "`complete_request(status: str, ...)` and `write_review(suggestions: list[Any])`, not `Literal` or typed models." A schema type would make FastMCP answer a validation error with other text before the service runs.
- DEC-007 (SPEC-0010): "Whitespace" is the Unicode `White_Space` set via one compiled regex (`\t\n\v\f\r`, space, U+0085, U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029, U+202F, U+205F, U+3000), used for the empty request, the empty reason and the empty suggestion fields; `str.strip()` also strips U+001C to U+001F, which are not `White_Space`.

### Data model

Request (JSON object, exactly these keys, in this order): `id` (`R-` plus the counter on at least 4 digits, `f"R-{n:04d}"`), `slide` (string or null, never checked against the file), `title` (instruction with each `\r\n`, `\n` or `\r` replaced by one space, then the first 60 code points, not trimmed), `queued` (`datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` taken inside the lock), `instruction` (exactly as typed), `status` (`pending`, `done`, `skipped`), `reason` (null unless `skipped`, stored as given).

Suggestion: `{"id","slide","title","why","change","applied"}`; the five input keys are the only ones kept, `applied` is stored.

Record file `<state_dir>/files/<key>/requests/record.json` (lock file `record.lock` beside it, empty, only locked); `<state_dir>` is `get_settings().state_dir`; `<key>` is `hashlib.sha256(os.path.realpath(file).encode("utf-8")).hexdigest()[:32]`, the key SPEC-0009 uses for `server.json`, `update.json` and `history/`:

```json
{"version":1,"file":"/abs/path/deck.html","revision":7,"next_id":4,
 "requests":[{"id":"R-0001","slide":"slide-3","title":"Shorten the title","queued":"2026-11-03T10:15:00Z","instruction":"Shorten the title","status":"pending","reason":null}],
 "review":[{"id":"s1","slide":"slide-1","title":"Tighten the agenda","why":"...","change":"Cut to 5 lines","applied":false}]}
```

`next_id` only increases (incremented on creation, never on deletion). `revision` increases by 1 on every write that changes the record; a change that leaves the serialized record identical writes nothing and does not bump it. `review` is null when never written (distinct from `[]`). A missing record file is an empty record (`next_id` 1, `revision` 0); read only operations never create the state directory. A record that exists but is unreadable or invalid JSON raises `RequestError(kind="storage")` with `Requests record of <file> is unreadable: <reason>` and is never reset. Limits: `INSTRUCTION_MAX = 4000`, `PENDING_MAX = 50`, `TITLE_MAX = 60`, `REVIEW_MAX = 6`, `BODY_MAX_BYTES = 1_048_576`.

Rules of `complete(file, request_id, status, reason)` in order: file (surface), id, status, reason, already completed. Unknown id: `Unknown request id "R-9". Valid ids: R-0001, R-0002` (every non deleted id, oldest first; `Valid ids: none` when empty; kind `not_found`); status not `done` or `skipped`: `Status must be done or skipped` (`invalid`); `skipped` with `reason is None or is_blank(reason)`: `A reason is required to skip a request` (`invalid`); already `done` or `skipped`: `Request R-0001 is already done` or `... is already skipped`, with the current status word (`conflict`). `done` stores `reason=None` (a reason given with `done` is ignored); `skipped` stores the reason untrimmed, no length limit. A storage error gives `Could not update the request: <error>` (`storage`; text not in the spec, decided in the design). The change runs in one `RequestStore.update`, so the check and the write are atomic.

### Contracts

```python
# request_service.py (extended)
def complete(self, file: Path, request_id: str, status: str, reason: str | None) -> Request

# mcp_server.py (each: trace_span("mcp.<name>", {"file.path": abs}); except RequestError as exc: raise ToolError(exc.message) from exc)
@mcp.tool()
def list_requests(file: str) -> dict[str, Any]
    # {"file": str(Path(file).resolve()), "requests": [request_to_dict, ...]}   oldest first, all statuses, none deleted
@mcp.tool()
def complete_request(file: str, id: str, status: str, reason: str | None = None) -> dict[str, Any]
    # {"ok": True, "id": "R-0001", "status": "done"}
```
`status` is `str`, not `Literal`, so the product message wins over a schema validation error (DEC-006). `require_file(file)` raises `File not found: <file>` (as typed, no prefix) before anything else. Tool errors are `fastmcp.exceptions.ToolError` (its message is always sent to the client).

Skill core (`skill/core.md`, section `## Tools`, appended at the end of the section in this story, each line `- <name>: <description>`):
- `- list_requests: List the requests the person queued in the editor for a file, oldest first`
- `- complete_request: Mark a request done, or skipped with a reason`

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/request_service.py` | modify: add `complete` |
| `src/mcp_htmleditor/mcp_server.py` | modify: tools `list_requests` and `complete_request`, module docstring |
| `skill/core.md` | modify: two lines at the end of `## Tools` |
| `tests/test_requests_tools.py` | create |

### Existing patterns
- `mcp_server.py`: plain typed `@mcp.tool()` functions with `trace_span("mcp.<name>", ...)`; SPEC-0007 and SPEC-0009 tools (`history`, `restore`) raise `ToolError(message)` with the command line message without its prefix.
- `tests/` helper `call_tool(name, **args)` (opens `fastmcp.Client(mcp)`, returns the data or the `ToolError` text) and `run_cli(*args, input=None)` from SPEC-0007 (`tests/conftest.py` or its helper module); `asyncio_mode = "auto"`.
- `skill/core.md` `## Tools` format `- <name>: <description>` (SPEC-0006 DEC-010); `mcp-htmleditor skill-audit` compares it with `registered_tool_names()`.
- Queueing in tests: `POST /requests` against a real `start_http_server`, as in `tests/test_requests_core.py` (US-0052).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0010/E2E-002: List requests
- Level E2E; Driver MCP client (`fastmcp.Client(mcp)`) plus HTTP queue; Location `tests/test_requests_tools.py`
- Given the request of E2E-001: `deck.html` has `R-0001`, slide `slide-3`, instruction `Shorten the title`, queued through `POST /requests`
- When the agent calls `list_requests` with `file` DECK
- Then it receives `{"file":"<absolute DECK path>","requests":[{"id":"R-0001","slide":"slide-3","title":"Shorten the title","queued":"<UTC time>","instruction":"Shorten the title","status":"pending","reason":null}]}`

### SPEC-0010/E2E-013: Invalid status
- Level E2E; Driver MCP client; Location `tests/test_requests_tools.py`
- Given R-0001 pending
- When the agent calls `complete_request` with `status` `finished`
- Then the error message is `Status must be done or skipped` (not a schema validation text) and R-0001 is still pending

### SPEC-0010/E2E-014: Already completed
- Level E2E; Driver MCP client; Location `tests/test_requests_tools.py`
- Given R-0001 marked done
- When the agent completes it again, as `skipped` with a reason
- Then the error is `Request R-0001 is already done` and the status is still `done`

### SPEC-0010/E2E-023: Two files
- Level E2E; Driver MCP client plus `CliRunner`; Location `tests/test_requests_tools.py`
- Given a request queued on DECK and none on DECK2
- When the agent calls `list_requests` for DECK2, then for DECK
- Then DECK2 returns an empty `requests` and DECK returns one request
- And `mcp-htmleditor requests deck2.html` prints `No requests for deck2.html`

### SPEC-0010/E2E-025: Completion after deletion
- Level E2E; Driver `POST /requests/delete` plus MCP client; Location `tests/test_requests_tools.py`
- Given R-0001 pending, then deleted by the user
- When the agent calls `complete_request` for `R-0001`
- Then the error is `Unknown request id "R-0001". Valid ids: none`

### SPEC-0010/UT-B01: Done ignores a reason; skipped keeps it untrimmed
- Level UT; Driver `RequestService`; Location `tests/test_requests_tools.py`
- Then `complete(file, "R-0001", "done", "ignored")` stores `reason` null; `complete(file, "R-0002", "skipped", "  Title is already short  ")` stores the reason with its spaces; `skipped` with `"   "`, `"\u3000"` or `None` raises `A reason is required to skip a request` and the request stays pending

### SPEC-0010/UT-B02: Check order
- Level UT; Driver `RequestService` and MCP client; Location `tests/test_requests_tools.py`
- Then each input that fails several checks reports the first in the order file, id, status, reason, already completed: `ghost.html` with id `R-9` gives `File not found: ghost.html`; unknown id with status `finished` gives the unknown id message; id known with status `finished` and no reason gives `Status must be done or skipped`; `skipped` without reason on an already done request gives `A reason is required to skip a request`

### SPEC-0010/UT-B03: Valid ids
- Level UT; Driver `RequestService`; Location `tests/test_requests_tools.py`
- Given R-0001, R-0002, R-0003 with R-0002 deleted
- Then `complete(file, "R-9", "done", None)` raises `Unknown request id "R-9". Valid ids: R-0001, R-0003`

### SPEC-0010/UT-B04: Tool errors
- Level UT; Driver MCP client; Location `tests/test_requests_tools.py`
- Then `list_requests` with `ghost.html` raises `ToolError` with the message exactly `File not found: ghost.html`; a non existing path given as `./ghost.html` reports `File not found: ./ghost.html`

### SPEC-0010/UT-B05: Skill audit sees the two tools
- Level UT; Driver `CliRunner` on `skill-audit`; Location `tests/test_requests_tools.py`
- Then exit 0 with no `PROBLEM` line about a tool missing from, or extra in, the core `## Tools` list, and `listed_tools(core)` contains `list_requests` and `complete_request`

## Constraints

- Files not to touch: `cli.py` (commands come in US-0054), `http_server.py`, `static/*`, `skill/topics/*`.
- Dependencies not to add: none allowed.
- Patterns to avoid: `Literal` or pydantic models for `status` (DEC-006); validating in the tool (all rules live in `RequestService`); the shipped core staying above 6 000 bytes (two lines add about 220 bytes) or containing a stale statement flagged by the audit (`N tools`).
- Scope boundary: no `write_review` yet (US-0057).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_requests_core.py` unchanged and green; every existing tool test and the SPEC-0006 skill audit tests.
- [ ] Docs updated: the `## Tools` lines in `skill/core.md`; module docstring of `mcp_server.py`.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: the line `- <name>: <description>` is added to the `## Tools` section of `skill/core.md` in the same story and `mcp-htmleditor skill-audit` stays green. In this story: `list_requests` and `complete_request`.
- [ ] One commit `US-0053: Agent lists and completes requests (tools)`, body `Spec: SPEC-0010` and the requirement ids FR-NEW-002, FR-NEW-003, FR-NEW-004.
