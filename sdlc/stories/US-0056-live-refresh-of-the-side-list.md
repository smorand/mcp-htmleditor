# US-0056: Live refresh of the side list

> Spec: SPEC-0010 (sdlc/specs/SPEC-0010-request-loop/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0055
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

Make the side list follow the agent: the existing status poll carries the request revision and the editor refetches the list only when it changed.

## Requirements covered

- SPEC-0010/FR-NEW-003 (partial: the editor shows the new status and reason after the agent completes a request): WHEN an agent calls `complete_request` or a user runs `mcp-htmleditor request-done <file> <id>` or `request-skip <file> <id> --reason <text>` THE Editor SHALL set the request's status to `done` or `skipped`.
- SPEC-0010/FR-NEW-005 (partial: refresh within two poll intervals of a change made by the agent): WHILE the editor is open on a file THE Editor SHALL show the side list `Requests (n)`, with n the number of pending requests, each request as `<id> <status> <slide> <title>` with a `Delete` button, refreshed within two poll intervals of a change made by the agent.

## Independent Test

`make test ARGS='-k requests_refresh'` (needs Chromium): with the editor open, `complete_request` makes the side list show `R-0001 done slide-3 Shorten the title` and `Requests (0)` within two poll intervals, with no reload.

## Design excerpt

### Decisions
- DEC-004 (SPEC-0010): "Change marker is the record `revision`, exposed as `requests_revision` in `/status`; the editor fetches `GET /requests` only when it differs." An exact counter, unlike an `mtime`, cannot miss two quick changes.
- DEC-012 (SPEC-0010): "All strings from the record are inserted with `textContent`." Agent text (title, reason, why) is untrusted data, and the editor shell origin can save the document.

### Data model

The change marker is the record `revision` (integer, +1 on each write that changes the record, 0 when there is no record), served as `requests_revision` by `GET /status`. The module holds the last revision seen (an integer or none).

### Contracts

```js
// editor-requests.js: the only public global added by the script (inside the IIFE, assigned to window)
function requestsOnStatus(status) {}   // status = the parsed GET /status payload of a successful poll
```
- `editor.js` `pollStatus` calls `requestsOnStatus(status)` once per successful poll, after the existing handling (one line added; guard with `typeof requestsOnStatus === 'function'` is not needed because `editor-requests.js` is loaded before `editor.js`).
- `requestsOnStatus` compares `status.requests_revision` with the last revision the module holds. Equal: nothing. Different (or the module holds none yet): `GET /requests`, re render the heading `Requests (n)` and the list, and hold the answer's `revision`.
- After the user's own `POST /requests` or `POST /requests/delete` the module refetches `GET /requests` and holds that revision, so the next poll sees an equal revision and issues no extra `GET /requests`.
- `GET /status` already carries `requests_revision` (US-0052): `RequestStore.revision(file)`, 0 when the record is absent or unreadable.
- The poll interval is the one of the existing poll (`pollInterval`, `setInterval(pollStatus, pollInterval)`); the tests set it to 250 ms through the server `poll_interval` option. Refresh is therefore within two poll intervals of the agent's change.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor.js` | modify: one call to `requestsOnStatus(status)` in `pollStatus` |
| `src/mcp_htmleditor/static/editor-requests.js` | modify: add `requestsOnStatus` |
| `tests/test_requests_refresh_e2e.py` | create |

### Existing patterns
- `editor.js` `pollStatus` / `setInterval(pollStatus, pollInterval)` (poll owned by `editor.js`, SPEC-0012 keeps it there); `lastMtime` handling in the same function shows where per poll hooks sit.
- `editor-requests.js` (US-0055): list rendering, `requestsShowMessage`, own-action refetch.
- Playwright harness and request log pattern from `tests/test_autosave_focus_e2e.py` and `tests/test_requests_editor_e2e.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Preconditions: `@needs_chromium`; real server with poll interval 250 ms; `HTMLEDITOR_STATE_DIR` a `tmp_path`; DECK of 8 slides; the agent side is the in process `fastmcp.Client(mcp)`.

### SPEC-0010/E2E-003: Complete as done
- Level E2E; Driver Playwright plus MCP client; Location `tests/test_requests_refresh_e2e.py`
- Given the request of E2E-001 (`R-0001`, slide `slide-3`, `Shorten the title`) shown in the open editor
- When the agent calls `complete_request` with `id` `R-0001`, `status` `done`
- Then it receives `{"ok":true,"id":"R-0001","status":"done"}`
- And within two poll intervals the editor shows `R-0001 done slide-3 Shorten the title` and `Requests (0)`

### SPEC-0010/E2E-004: Complete as skipped
- Level E2E; Driver Playwright plus MCP client; Location `tests/test_requests_refresh_e2e.py`
- Given the request of E2E-001 shown in the open editor
- When the agent calls `complete_request` with `status` `skipped` and `reason` `Title is already short`
- Then the editor shows `R-0001 skipped slide-3 Shorten the title` followed by `Title is already short`

### SPEC-0010/E2E-027: Editor refresh
- Level E2E; Driver Playwright (poll 250 ms) plus MCP client; Location `tests/test_requests_refresh_e2e.py`
- Given DECK open with R-0001 pending
- When the agent completes it as `done` and nothing else touches the editor
- Then within two poll intervals (500 ms plus the request time, waited with `expect(...).to_have_text` and a 2 s timeout) the side list shows it as `done` without a manual reload (the page URL and a `window.__marker` set before the change are unchanged)

### SPEC-0010/UT-E01: No fetch while nothing changes
- Level UT; Driver Playwright request log (`page.on("request")`); Location `tests/test_requests_refresh_e2e.py`
- Given DECK open, settled after the first list fetch
- When ten polls pass (about 2.5 s) with no change
- Then the log holds ten or more `GET /status` and zero `GET /requests`

### SPEC-0010/UT-E02: No extra fetch after the user's own action
- Level UT; Driver Playwright request log; Location `tests/test_requests_refresh_e2e.py`
- When the user queues `Shorten the title` from the panel and three polls pass
- Then exactly one `GET /requests` follows the `POST /requests` (the refetch of the module) and no other `GET /requests` is issued by those polls

## Constraints

- Files not to touch: `http_server.py`, `request_service.py`, `editor.html`, `editor.css`.
- Dependencies not to add: none allowed.
- Patterns to avoid: a second timer (`setInterval`) in `editor-requests.js`; fetching the list on every poll; reloading the iframe for a list change; keeping `editor.js` above 500 lines (SPEC-0012 DT-011).
- Scope boundary: suggestions are not refreshed here (US-0058 reuses the same `GET /requests` answer).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_requests_editor_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_static_scripts.py` and `tests/test_size_caps.py` pass; the poll still drives reload and save state exactly as before.
- [ ] Docs updated: none in this story (the closing story documents the feature).
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0056: Live refresh of the side list`, body `Spec: SPEC-0010` and the requirement ids FR-NEW-003, FR-NEW-005.
