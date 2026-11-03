# US-0059: Documentation and no file next to the user's file

> Spec: SPEC-0010 (sdlc/specs/SPEC-0010-request-loop/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0058
> min_tier: 2
> Files touched: 5
> Closes spec: yes

## Objective

Close SPEC-0010: prove end to end that nothing is created next to the user's file and that the loop works across the editor, the tools and the commands, and document the feature.

## Requirements covered

- SPEC-0010/FR-NEW-004 (partial: end to end parity across the editor, the tools and the commands, and a clean tool process standard output): The Editor SHALL give the same results for requests and review through the command line and the agent tool surface, the tool returning an error whose message is the command line error line without its `error: ` prefix.
- SPEC-0010/FR-NEW-008: The Editor SHALL NOT create any file or folder next to the user's file for requests or the review, and SHALL NOT mix requests of different files.

## Independent Test

`make test ARGS='-k request_loop_acceptance'` (needs Chromium for E2E-028): after a UI queue and an agent review write, the deck folder holds only `deck.html`; `make check` is green with the whole SPEC-0010 acceptance set.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0010): "One JSON record per file, not one file per request and not SQLite." A single write holds the counter, the requests and the review, so id allocation, request creation and the applied mark cannot disagree after a crash.
- DEC-003 (SPEC-0010): "Record directory `<state_dir>/files/<sha256(realpath)[:32]>/requests/`, inside the SPEC-0009 per file directory." `realpath` implements the symlink rule; a renamed or moved file has another key and starts empty.
- DEC-005 (SPEC-0010): "Rules and messages live only in `RequestService`; surfaces translate (`RequestError.kind` to HTTP status, `ToolError`, `error: ` line)." One source of text makes parity structural (FR-NEW-004).
- DEC-010 (SPEC-0010): "Storage failure seam is a regular file created at `record_dir(file)`." `mkdir` fails with an `OSError` for every user including root; `chmod` does not (the suite also runs as root in the container).
- DEC-015 (SPEC-0010): "`fcntl` only (macOS, Linux, Docker)." A Windows run raises `ModuleNotFoundError` at import of `request_store`; accepted.
- DEC-016 (SPEC-0010): "An invalid record raises a storage error and is never reset." Resetting to an empty record would give `R-0001` again.

### Data model

No new data. Layout recap: `<state_dir>/files/<key>/requests/record.json` and `record.lock`; `<key>` = `sha256(realpath(file) as UTF 8).hexdigest()[:32]`.

### Contracts

No new code contract. Documentation to write:
- `README.md`: a section `Request loop`: the `Ask AI` button and panel, the side list `Requests (n)`, the commands `requests`, `request-done`, `request-skip`, `review` (with `--write`), the tools `list_requests`, `complete_request`, `write_review`, and where the state lives (`<state_dir>/files/<key>/requests/record.json`, `HTMLEDITOR_STATE_DIR`; nothing next to the user's file; removing the state directory removes the requests and the review).
- `AGENTS.md`: the four commands in the command list and an index entry for the request loop (detail stays in `.agent_docs/architecture.md`).
- `.agent_docs/architecture.md`: modules `request_store.py` and `request_service.py`, the routes `GET /requests`, `POST /requests`, `POST /requests/delete`, `POST /review/apply`, `requests_revision` in `/status`, the record layout and the lock rule, the script `editor-requests.js` and its place in the script order.
- `.agent_docs/testing.md`: the new test files (`test_requests_core.py`, `test_requests_tools.py`, `test_requests_cli.py`, `test_requests_editor_e2e.py`, `test_requests_refresh_e2e.py`, `test_review_write.py`, `test_review_apply_e2e.py`, `test_request_loop_acceptance.py`) and the storage failure seam (a regular file at `RequestStore.record_dir(file)`, why `chmod` is not used).
Entries in `.agent_docs/*.md` are timestamped and concise; no dashes of any kind in the added text.

### Paths
| Path | Action |
|---|---|
| `README.md` | modify: section `Request loop` |
| `AGENTS.md` | modify: commands and index entry |
| `.agent_docs/architecture.md` | modify: modules, routes, record layout |
| `.agent_docs/testing.md` | modify: new test files and the storage failure seam |
| `tests/test_request_loop_acceptance.py` | create |

### Existing patterns
- Documentation style: `README.md` sections of SPEC-0009 (state location, history and restore), `AGENTS.md` index of `.agent_docs/`.
- Acceptance and subprocess tests: `tests/test_requests_core.py` (UT-A02 subprocess pattern) and the Playwright harness of `tests/test_requests_editor_e2e.py`.
- Skill audit gate: `tests/test_requests_cli.py` (UT-C04).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0010/E2E-028: No file next to the file
- Level E2E; Driver Playwright plus MCP client; Location `tests/test_request_loop_acceptance.py`
- Given an empty folder with DECK, the editor open (`HTMLEDITOR_STATE_DIR` outside that folder)
- When the user queues a request and the agent writes a review
- Then the folder holds only DECK (`sorted(os.listdir(folder)) == ["deck.html"]`), and the state directory holds `files/<key>/requests/record.json` and `record.lock`

### SPEC-0010/UT-H01: Full loop in process
- Level UT; Driver `RequestService`, tools through `fastmcp.Client(mcp)` and `CliRunner`; Location `tests/test_request_loop_acceptance.py`
- When a request is queued by the service, listed by tool and command (same ids and titles), completed by the tool as `done`, a review of two suggestions is written by the tool, one is applied through the service, and the requests are listed again
- Then the list shows `R-0001` done and `R-0002` pending with instruction `Tighten the agenda. Cut to 5 lines`, and `review deck.html` shows both suggestions

### SPEC-0010/UT-H02: State directory owns the data
- Level UT; Driver `RequestService`; Location `tests/test_request_loop_acceptance.py`
- When the state directory is removed after a queue and a review write
- Then `list_requests` is empty and `read_review` is empty, and the next request is `R-0001`; two decks have two different `record_dir` values

### SPEC-0010/UT-H03: Skill audit and topic size
- Level UT; Driver `CliRunner` on `skill-audit`; Location `tests/test_request_loop_acceptance.py`
- Then `skill-audit` exits 0 with last line `skill-audit: OK`, the shipped `skill/topics/create.md` is at most 3800 bytes, and `skill/core.md` lists `list_requests`, `complete_request` and `write_review` under `## Tools`

### SPEC-0010/UT-H04: Documentation names the interfaces
- Level UT; Driver file read; Location `tests/test_request_loop_acceptance.py`
- Then `README.md` and `AGENTS.md` each contain the strings `requests`, `request-done`, `request-skip`, `review`, and `README.md` also contains `list_requests`, `complete_request`, `write_review`

### SPEC-0010/UT-H05: Tool process stdout stays clean
- Level UT; Driver `subprocess.run([sys.executable, "-c", script])` where the script imports `mcp_htmleditor.mcp_server` and calls `list_requests` and `write_review` through `fastmcp.Client(mcp)`; Location `tests/test_request_loop_acceptance.py`
- Then the captured standard output of the subprocess is empty (`b""`)

## Constraints

- Files not to touch: any file under `src/`, `skill/`, `Dockerfile`, `docker-compose.yml` (SPEC-0009 owns the deployment files).
- Dependencies not to add: none allowed.
- Patterns to avoid: dashes of any kind in generated prose; detail in `AGENTS.md` that belongs in `.agent_docs/`.
- Scope boundary: no behaviour change; a failing acceptance test here points to an earlier story and is fixed there.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: every earlier SPEC-0010 test file unchanged and green.
- [ ] Docs updated: `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md`.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] (Closing story) the spec's full acceptance set green: SPEC-0010/E2E-001 to E2E-028 (each in its story: 001, 008, 009, 010, 020, 021, 022, 026 in US-0055; 002, 013, 014, 023, 025 in US-0053; 003, 004, 027 in US-0056; 005, 011, 012 in US-0054; 006, 007, 019, 024 in US-0058; 015, 016, 017, 018 in US-0057; 028 here), and every requirement FR-NEW-001 to FR-NEW-008 of SPEC-0010 cited by at least one story with status done or landed.
- [ ] One commit `US-0059: Documentation and no file next to the user's file`, body `Spec: SPEC-0010` and the requirement ids FR-NEW-004, FR-NEW-008.
