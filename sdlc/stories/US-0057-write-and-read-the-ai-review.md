# US-0057: Write and read the AI review (tool and command)

> Spec: SPEC-0010 (sdlc/specs/SPEC-0010-request-loop/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0053
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Let the agent publish up to six suggestions (`write_review`, or `review <file> --write`) and let anyone read them back (`review <file>`), with the exact validation messages of the spec on both surfaces.

## Requirements covered

- SPEC-0010/FR-NEW-004 (partial: the review rules and file errors give the same text on the command line and the tool): The Editor SHALL give the same results for requests and review through the command line and the agent tool surface, the tool returning an error whose message is the command line error line without its `error: ` prefix.
- SPEC-0010/FR-NEW-006 (partial: writing and reading the review through the tool and the command; the editor display and Apply are US-0058): WHEN an agent calls `write_review` with suggestions or a user runs `mcp-htmleditor review <file> --write <suggestions.json | ->` THE Editor SHALL replace the review of that file by those suggestions.

## Independent Test

`make test ARGS='-k review_write'`: `write_review` with two valid suggestions returns `{"ok":true,"count":2}` and `mcp-htmleditor review deck.html` prints `s1  slide-2  Tighten the agenda` and `s2  -  Add a closing slide`.

## Design excerpt

### Decisions
- DEC-005 (SPEC-0010): "Rules and messages live only in `RequestService`; surfaces translate (`RequestError.kind` to HTTP status, `ToolError`, `error: ` line)." One source of text makes parity structural (FR-NEW-004).
- DEC-006 (SPEC-0010): "`complete_request(status: str, ...)` and `write_review(suggestions: list[Any])`, not `Literal` or typed models." A schema type would make FastMCP answer a validation error with other text before the service runs.
- DEC-007 (SPEC-0010): "Whitespace" is the Unicode `White_Space` set via one compiled regex (`\t\n\v\f\r`, space, U+0085, U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029, U+202F, U+205F, U+3000), used for the empty request, the empty reason and the empty suggestion fields; `str.strip()` also strips U+001C to U+001F, which are not `White_Space`.
- DEC-017 (SPEC-0010): "An empty review prints `No review for <file>`, and a non dict suggestion item gives `Suggestion N: missing field \"id\"`."
- DEC-001 (SPEC-0010): "One JSON record per file, not one file per request and not SQLite." A single write holds the counter, the requests and the review, so id allocation, request creation and the applied mark cannot disagree after a crash.

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

Rules of `write_review(file, raw)` in order: `raw` not a list: `Review must be a list of suggestions`; `len(raw) > 6`: `At most 6 suggestions`; then per position (1 based, first faulty suggestion wins): a non dict item or a missing field in the order `id, slide, title, why, change` gives `Suggestion N: missing field "x"` (a field that is absent, null except `slide`, not a string, or empty or only whitespace counts as missing; `slide` must be null or a string; a non dict item reports `missing field "id"`, DEC-017), then `Suggestion N: title is longer than 60 characters` (code points), then `Suggestion N: duplicate id "s1"`. A storage error gives `Could not write the review: <error>`; the previous review is unchanged. Each stored suggestion has `applied=False`; keys other than the five are dropped; `slide` is not checked against the file. A new review replaces the previous one; requests created earlier by Apply stay.

### Contracts

```python
# request_service.py (extended)
def write_review(self, file: Path, raw: object) -> int          # returns the count; one RequestStore.update
def read_review(self, file: Path) -> list[Suggestion]           # [] when review is null or empty

# mcp_server.py
@mcp.tool()
def write_review(file: str, suggestions: list[Any]) -> dict[str, Any]   # {"ok": True, "count": n}; trace "mcp.write_review"; RequestError -> ToolError(message)

# cli.py
@main.command("review")  @click.argument("file")  @click.option("--write", "write_source", default=None)
```
- `review <file>` prints one line per suggestion, `<id>  <slide or ->  <title>` (two spaces), or `No review for <file>` (also for an empty review, DEC-017).
- `review <file> --write <path>` reads the JSON file (`-` reads standard input), then calls `write_review`; prints `Review written: <n> suggestions` (the word `suggestions` also for 1). Read failure: `Cannot read <path>: <reason>`; invalid JSON: `Invalid JSON: <reason>`; then the service rules. Order: file not found, read, JSON, rules. Errors: `error: <message>` on stderr, exit 1, empty stdout.
- `GET /requests` already returns `suggestions` (US-0052); it now returns the stored review.
- `skill/core.md` `## Tools`, one line appended in this story: `- write_review: Replace the AI suggestions shown in the editor (at most 6)`.

Fixtures used by the tests (valid suggestions): `s1` = `{"id":"s1","slide":"slide-2","title":"Tighten the agenda","why":"The agenda has 8 lines","change":"Cut to 5 lines"}`; `s2` = `{"id":"s2","slide":null,"title":"Add a closing slide","why":"The deck ends abruptly","change":"Add a thank you slide"}`; `s3` to `s7` are the same shape with ids `s3` to `s7`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/request_service.py` | modify: add `write_review`, `read_review` |
| `src/mcp_htmleditor/mcp_server.py` | modify: tool `write_review` |
| `src/mcp_htmleditor/cli.py` | modify: add `review` |
| `skill/core.md` | modify: one line at the end of `## Tools` |
| `tests/test_review_write.py` | create |

### Existing patterns
- `request_service.py` (US-0052, US-0053): `RequestError`, `is_blank`, `require_file`, the single `RequestStore.update` change function style.
- `mcp_server.py` tools of US-0053 (`list_requests`, `complete_request`) and the `ToolError` wrapper; `cli.py` `requests`, `request-done`, `request-skip` and `_request_fail` for the error pattern.
- `tests/test_requests_tools.py` and `tests/test_requests_cli.py` for the MCP client and `CliRunner` helpers.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0010/E2E-015: Too many suggestions
- Level E2E; Driver MCP client plus `CliRunner`; Location `tests/test_review_write.py`
- Given DECK with a previous review of `s1` and `s2`
- When the agent calls `write_review` with 7 valid suggestions (`s1` to `s7`)
- Then the error is `At most 6 suggestions` and the previous review is unchanged (`review deck.html` still prints `s1  slide-2  Tighten the agenda` and `s2  -  Add a closing slide`); `review deck.html --write seven.json` prints `error: At most 6 suggestions`

### SPEC-0010/E2E-016: Title too long
- Level E2E; Driver MCP client plus `CliRunner`; Location `tests/test_review_write.py`
- Given DECK
- When the agent writes a review whose second suggestion has a title of 61 characters
- Then the error is `Suggestion 2: title is longer than 60 characters` and nothing changes (and a title of exactly 60 characters is accepted)

### SPEC-0010/E2E-017: Missing field and duplicate id
- Level E2E; Driver MCP client plus `CliRunner`; Location `tests/test_review_write.py`
- Given DECK
- When the agent writes a review whose third suggestion has no `change`, and another whose second suggestion repeats the id `s1`
- Then the errors are `Suggestion 3: missing field "change"` and `Suggestion 2: duplicate id "s1"`
- And the same writes through `mcp-htmleditor review deck.html --write <file>` print `error: ` followed by the same text, exit status 1

### SPEC-0010/E2E-018: File not found
- Level E2E; Driver MCP client plus `CliRunner`; Location `tests/test_review_write.py`
- Given no file `ghost.html`
- When the user runs `requests ghost.html`, and the agent calls `list_requests`, `complete_request`, `write_review` for it
- Then each fails with `File not found: ghost.html` (command line: `error: File not found: ghost.html`, exit status 1); `review ghost.html` and `review ghost.html --write s.json` fail the same way

### SPEC-0010/UT-F01: Check order
- Level UT; Driver `RequestService`; Location `tests/test_review_write.py`
- Then seven suggestions that are also faulty report `At most 6 suggestions` (count before positions); a list whose position 2 lacks `why` and whose position 3 has a long title reports `Suggestion 2: missing field "why"`; within one suggestion lacking `why` and with a 61 character title the message is the missing field; with a long title and a duplicate id it is the title

### SPEC-0010/UT-F02: Field rules
- Level UT; Driver `RequestService`; Location `tests/test_review_write.py`
- Then `slide: null` is accepted; `slide: 3` gives `Suggestion 1: missing field "slide"`; a missing `slide` key gives the same; `why: "  \u3000 "` gives `missing field "why"`; `id: ""` gives `missing field "id"`; a non dict item (`"s1"`) gives `Suggestion 1: missing field "id"`; a dict with an extra key `extra` is stored without it; a non list (`{}`) gives `Review must be a list of suggestions`

### SPEC-0010/UT-F03: Applied state belongs to the review
- Level UT; Driver `RequestService` plus `RequestStore.update`; Location `tests/test_review_write.py`
- Given a review `s1` whose suggestion is set to `applied` in the record and a request `R-0001` created from it
- When a new review with the same id `s1` is written
- Then `read_review` returns `s1` with `applied` false and `R-0001` is still listed

### SPEC-0010/UT-F04: `review` output
- Level UT; Driver `CliRunner`; Location `tests/test_review_write.py`
- Then with `s1` and `s2` stored, stdout is `s1  slide-2  Tighten the agenda\ns2  -  Add a closing slide\n`; with no review, and with a stored empty review (`[]`), stdout is `No review for deck.html\n`

### SPEC-0010/UT-F05: `--write` sources and errors
- Level UT; Driver `CliRunner` with `input=`; Location `tests/test_review_write.py`
- Then `--write review.json` and `--write -` (JSON on standard input) both print `Review written: 2 suggestions`; one suggestion prints `Review written: 1 suggestions`; a missing path prints `error: Cannot read nope.json: ` followed by a non empty reason; `{` prints `error: Invalid JSON: ` followed by a non empty reason; `{}` prints `error: Review must be a list of suggestions`

### SPEC-0010/UT-F06: Storage failure keeps the old review
- Level UT; Driver `RequestService` plus the `record_dir` seam; Location `tests/test_review_write.py`
- Given a stored review `s1`, then the directory `record_dir(file)` renamed away and a regular file created at that path
- Then `write_review` raises kind `storage` with a message starting `Could not write the review: ` and, after the file is removed and the directory renamed back, `read_review` returns `s1` unchanged

### SPEC-0010/UT-F07: Skill audit with `write_review`
- Level UT; Driver `CliRunner` on `skill-audit`; Location `tests/test_review_write.py`
- Then exit 0, and `listed_tools(core)` contains `write_review`

## Constraints

- Files not to touch: `http_server.py` (the review comes back through the existing `GET /requests`), `static/*`, `skill/topics/*`.
- Dependencies not to add: none allowed.
- Patterns to avoid: `Literal` or pydantic item models for the suggestions (DEC-006); `str.strip()` for the blank test (DEC-007); keeping extra keys; checking `slide` against the file.
- Scope boundary: no Apply (US-0058), no editor display.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_requests_core.py`, `tests/test_requests_tools.py` and `tests/test_requests_cli.py` unchanged and green; the SPEC-0006 skill audit.
- [ ] Docs updated: the `## Tools` line in `skill/core.md`.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: the line `- <name>: <description>` is added to the `## Tools` section of `skill/core.md` in the same story and `mcp-htmleditor skill-audit` stays green. In this story: `write_review`.
- [ ] One commit `US-0057: Write and read the AI review (tool and command)`, body `Spec: SPEC-0010` and the requirement ids FR-NEW-004, FR-NEW-006.
