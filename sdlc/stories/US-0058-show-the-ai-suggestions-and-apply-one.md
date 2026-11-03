# US-0058: Show the AI suggestions and apply one

> Spec: SPEC-0010 (sdlc/specs/SPEC-0010-request-loop/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0056, US-0057
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Show the agent's review in the side panel and let the person turn one suggestion into a pending request with `Apply`, atomically with the applied mark.

## Requirements covered

- SPEC-0010/FR-NEW-006 (partial: the editor shows `AI suggestions (n)` with the title, the `why` text and `Apply` or `Applied`): WHEN an agent calls `write_review` with suggestions or a user runs `mcp-htmleditor review <file> --write <suggestions.json | ->` THE Editor SHALL replace the review of that file by those suggestions.
- SPEC-0010/FR-NEW-007: WHEN the user clicks `Apply` on a suggestion THE Editor SHALL create a pending request from it and mark the suggestion applied.

## Independent Test

`make test ARGS='-k review_apply'` (needs Chromium): after `write_review`, the editor lists the suggestions; `Apply` on `s1` shows `Request R-0001 queued`, `Applied` on the suggestion, and `list_requests` returns the instruction `Tighten the agenda. Cut to 5 lines`.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0010): "One JSON record per file, not one file per request and not SQLite." A single write holds the counter, the requests and the review, so id allocation, request creation and the applied mark cannot disagree after a crash.
- DEC-002 (SPEC-0010): "Exclusive `fcntl.flock` on a sibling `record.lock` around read, change, atomic rename; readers lock free." `flock` belongs to the open file description, so it excludes other processes and other threads of the threaded editor server (each `update` opens its own descriptor).
- DEC-005 (SPEC-0010): "Rules and messages live only in `RequestService`; surfaces translate (`RequestError.kind` to HTTP status, `ToolError`, `error: ` line)." One source of text makes parity structural (FR-NEW-004).
- DEC-008 (SPEC-0010): "New classic script `editor-requests.js`, an IIFE, inserted after `editor-drag.js` and before `editor.js`, one global `requestsOnStatus`." It reads no top level `let` or `const` of `editor.js` at evaluation time and defines no top level function name twice (SPEC-0012 DR-006, DT-012).
- DEC-009 (SPEC-0010): "The four editor endpoints are GET and POST only, inside the existing dispatch." The SPEC-0005 gate runs before dispatch, so a new route cannot bypass it; deletion is a POST because `do_OPTIONS` advertises `Allow: GET, POST`.
- DEC-012 (SPEC-0010): "All strings from the record are inserted with `textContent`." Agent text (title, reason, why) is untrusted data, and the editor shell origin can save the document.
- DEC-014 (SPEC-0010): "The new POST routes cap the body at 1 MiB and check `Content-Length`." The header goes through SPEC-0009's `parse_content_length`; the 50 MiB cap of the save route is not used here.

### Data model

Suggestion: `{"id","slide","title","why","change","applied"}` inside `record.review`. Apply replaces the suggestion by its `applied=True` copy and appends the request in the same record write (one `RequestStore.update`, one `revision` bump), so the applied mark and the request cannot disagree. The created request: `slide` = the suggestion's `slide` as is, `instruction` = `<title>. <change>`, `title` derived by the usual rule, `status` `pending`, `reason` null.

Rules of `apply_suggestion(file, suggestion_id)` (one `RequestStore.update`): unknown id: `Suggestion <id> no longer exists` (`not_found`; also when the review is null); already applied: `Suggestion <id> was already applied` (`conflict`); then the queue checks on `instruction = f"{title}. {change}"` with `slide` as is, even if that slide no longer exists (too long uses the built instruction, 4000 code points inclusive; too many pending: `Too many pending requests (max 50)`; storage: `Could not queue the request: <error>`). On success the request is appended and the suggestion replaced by its `applied=True` copy in the same record write; on any refusal the suggestion stays not applied and no request is created. Returns the created `Request`; the confirmation is `Request <id> queued` with the id of the created request.

### Contracts

```python
# request_service.py (extended)
def apply_suggestion(self, file: Path, suggestion_id: str) -> Request
```
| Method, path | Body | Success | Errors |
|---|---|---|---|
| `POST /review/apply` | `{"id":str}` | 200 `{"ok":true,"request":{...7 keys}}` | 400 `{"ok":false,"error":"Invalid request body"}` (not an object, `id` not a string), `Request too long (max 4000 characters)`; 404 `Suggestion s1 no longer exists`; 409 `Suggestion s1 was already applied`, `Too many pending requests (max 50)`; 500 `Could not queue the request: <error>` |

Same JSON only, length, size, gate and 404 `{"error":"No file loaded"}` rules as `POST /requests` (helper `_read_json_object`, US-0052). `do_OPTIONS` stays 405.

Editor additions in `editor-requests.js` (the aside `requests-side` of US-0055):

| Id or selector | Element | Text or behaviour |
|---|---|---|
| `suggestions-heading` | heading created by the script and appended to `requests-side` | `AI suggestions (n)`, n = number of suggestions in the last `GET /requests` answer (`AI suggestions (0)` when none) |
| `suggestions-list` | `ul` | one `li[data-suggestion-id]` per suggestion: `.suggestion-title` (the title), `.suggestion-why` (the `why` text), `button.suggestion-apply` with text `Apply`, or `Applied` and disabled when `applied` |

`Apply` sends `POST /review/apply` `{"id": <suggestion id>}`; success shows `Request <id> queued` in `ask-ai-message` (the panel opens if closed) and refetches `GET /requests`; failure shows the server `error` text there. The suggestions list refreshes with the same revision check as the requests list (a review write bumps the record `revision`). All strings go in through `textContent` (DEC-012).

Skill topic `skill/topics/create.md`: in the section `Apply the requests` add a short paragraph: after the requests, optionally call `write_review` with at most 6 suggestions (`id`, `slide`, `title` of at most 60 characters, `why`, `change`); the person turns one into a pending request with `Apply`. The shipped file stays at or below 3 800 bytes.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/request_service.py` | modify: add `apply_suggestion` |
| `src/mcp_htmleditor/http_server.py` | modify: route `POST /review/apply` |
| `src/mcp_htmleditor/static/editor-requests.js` | modify: suggestions heading and list, `Apply` |
| `skill/topics/create.md` | modify: add the review paragraph to `Apply the requests` |
| `tests/test_review_apply_e2e.py` | create |

### Existing patterns
- `request_service.py` `queue` rules (US-0052) are reused in the same `update` as the applied mark; `write_review` and `read_review` (US-0057) produce the review.
- `http_server.py` routes and `_read_json_object` (US-0052); status mapping from `RequestError.kind`.
- `editor-requests.js` list rendering and `requestsShowMessage` (US-0055, US-0056); `tests/test_requests_refresh_e2e.py` for the poll-speed Playwright setup.
- `skill/topics/create.md` section `Apply the requests` (US-0054).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Preconditions: `@needs_chromium`; real server with poll interval 250 ms; `HTMLEDITOR_STATE_DIR` a `tmp_path`; DECK of 8 slides; the agent side is `fastmcp.Client(mcp)`. Review fixtures: `s1` = `{"id":"s1","slide":"slide-1","title":"Tighten the agenda","why":"The agenda has 8 lines","change":"Cut to 5 lines"}`; `s2` = `{"id":"s2","slide":null,"title":"Add a closing slide","why":"The deck ends abruptly","change":"Add a thank you slide"}`.

### SPEC-0010/E2E-006: Write and show a review
- Level E2E; Driver Playwright plus MCP client plus `CliRunner`; Location `tests/test_review_apply_e2e.py`
- Given DECK open
- When the agent calls `write_review` with 2 valid suggestions (ids `s1`, `s2`; `s1` with slide `slide-2` and `s2` with slide null)
- Then it receives `{"ok":true,"count":2}` and the editor shows `AI suggestions (2)` with their titles, `why` texts and a button `Apply` each
- And `mcp-htmleditor review deck.html` prints `s1  slide-2  <title>` and `s2  -  <title>`

### SPEC-0010/E2E-007: Apply a suggestion
- Level E2E; Driver Playwright plus MCP client; Location `tests/test_review_apply_e2e.py`
- Given the review of E2E-006, `s1` having title `Tighten the agenda`, change `Cut to 5 lines`, slide `slide-1`
- When the user clicks `Apply` on `s1`
- Then the panel shows `Request R-0001 queued`, the side list holds a pending request for `slide-1` and `list_requests` returns its instruction `Tighten the agenda. Cut to 5 lines`
- And the suggestion shows `Applied`

### SPEC-0010/E2E-019: Apply twice
- Level E2E; Driver two Playwright pages on the same editor, the stale one with its `GET /requests` blocked by `page.route`; Location `tests/test_review_apply_e2e.py`
- Given the review of E2E-007 with `s1` applied (on the first page)
- When the user clicks `Apply` on `s1` again (button shown as `Applied`) or the apply is sent a second time (the stale page, still showing `Apply`)
- Then the editor shows `Suggestion s1 was already applied` and no second request is created (`list_requests` has one request)

### SPEC-0010/E2E-024: New review
- Level E2E; Driver Playwright plus MCP client; Location `tests/test_review_apply_e2e.py`
- Given a review with `s1` applied (request R-0001 exists)
- When the agent writes a new review with one suggestion `n1`
- Then the editor shows `AI suggestions (1)` with `n1` only, and R-0001 is still in the list

### SPEC-0010/UT-G01: Apply check order
- Level UT; Driver `RequestService`; Location `tests/test_review_apply_e2e.py`
- Then an unknown id gives `Suggestion x9 no longer exists` (also with no review); an applied one gives `Suggestion s1 was already applied` even when 50 requests are pending; a suggestion with `title` of 30 characters and `change` of 3980 characters (built instruction 4012) gives `Request too long (max 4000 characters)`; a fresh suggestion with 50 pending gives `Too many pending requests (max 50)`; a built instruction of exactly 4000 characters is accepted

### SPEC-0010/UT-G02: Refusal leaves no trace
- Level UT; Driver `RequestService` plus the `record_dir` seam; Location `tests/test_review_apply_e2e.py`
- Then after each refusal of UT-G01 `read_review` shows `applied` false and `list_requests` is unchanged; with the seam (directory renamed away, regular file at `record_dir`) the apply raises kind `storage` with a message starting `Could not queue the request: `

### SPEC-0010/UT-G03: Slide kept as is
- Level UT; Driver `RequestService`; Location `tests/test_review_apply_e2e.py`
- Then a suggestion with slide `slide-99` (absent from the deck) creates a request with `slide` `slide-99`, and one with slide null creates a request with `slide` null

### SPEC-0010/UT-G04: HTTP mapping of `POST /review/apply`
- Level UT; Driver `http.client`; Location `tests/test_review_apply_e2e.py`
- Then 200 `{"ok":true,"request":{...}}` on success; 404 `{"ok":false,"error":"Suggestion s9 no longer exists"}`; 409 `{"ok":false,"error":"Suggestion s1 was already applied"}` and `Too many pending requests (max 50)`; 400 `Request too long (max 4000 characters)` and `{"ok":false,"error":"Invalid request body"}` for body `[]` or `{"id":5}`; 415 for `text/plain`; 403 for a foreign `Origin` or `Host` with no request created; 500 with prefix `Could not queue the request: ` under the seam

### SPEC-0010/UT-G05: Suggestion text is data
- Level UT; Driver Playwright; Location `tests/test_review_apply_e2e.py`
- Given a suggestion whose `why` is `<img src=x onerror=window.__xss=1>`
- Then the list shows that text literally and `window.__xss` is `undefined`

## Constraints

- Files not to touch: `editor.html`, `editor.css`, `editor.js`, `cli.py`, `mcp_server.py`.
- Dependencies not to add: none allowed.
- Patterns to avoid: two writes for the request and the applied mark; `innerHTML` with `why` or `title`; changing the review rules of US-0057; a new top level function name that exists in another static script.
- Scope boundary: no new tool; no documentation outside `skill/topics/create.md` (US-0059).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_review_write.py`, `tests/test_requests_editor_e2e.py`, `tests/test_requests_refresh_e2e.py` and `tests/test_size_caps.py` (`editor-requests.js` at most 500 lines) unchanged and green; the SPEC-0006 skill audit.
- [ ] Docs updated: `skill/topics/create.md` review paragraph.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0058: Show the AI suggestions and apply one`, body `Spec: SPEC-0010` and the requirement ids FR-NEW-006, FR-NEW-007.
