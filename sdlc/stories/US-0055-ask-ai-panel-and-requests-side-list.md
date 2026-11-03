# US-0055: Ask AI panel and the requests side list

> Spec: SPEC-0010 (sdlc/specs/SPEC-0010-request-loop/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0053, US-0017
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Give the person the editor side of the loop: an `Ask AI` button and panel that queue a request for the current slide, and an always visible `Requests (n)` side list with a `Delete` button per request. The list is filled at page start and after the person's own actions; following the agent's changes live comes in the next story.

## Requirements covered

- SPEC-0010/FR-NEW-001 (partial: the `Ask AI` panel, the current slide rule and the visible messages): WHEN the user clicks `Queue request` in the `Ask AI` panel THE Editor SHALL store a pending request and confirm it.
- SPEC-0010/FR-NEW-005 (partial: the side list, its lines and `Delete`; the refresh on agent changes is US-0056): WHILE the editor is open on a file THE Editor SHALL show the side list `Requests (n)`, with n the number of pending requests, each request as `<id> <status> <slide> <title>` with a `Delete` button, refreshed within two poll intervals of a change made by the agent.

## Independent Test

`make test ARGS='-k requests_editor'` (needs Chromium): in the editor the user opens `Ask AI`, queues `Shorten the title` on `slide-3`, sees `Request R-0001 queued` and `Requests (1)` with `R-0001 pending slide-3 Shorten the title`.

## Design excerpt

### Decisions
- DEC-008 (SPEC-0010): "New classic script `editor-requests.js`, an IIFE, inserted after `editor-drag.js` and before `editor.js`, one global `requestsOnStatus`." It reads no top level `let` or `const` of `editor.js` at evaluation time and defines no top level function name twice (SPEC-0012 DR-006, DT-012).
- DEC-012 (SPEC-0010): "All strings from the record are inserted with `textContent`." Agent text (title, reason, why) is untrusted data, and the editor shell origin can save the document.
- DEC-013 (SPEC-0010): "Current slide = `data-id` of the slide of the last click or selection in the iframe, else the first slide, else null; tracked by listeners re attached on each iframe `load`." The remembered id is validated against the current document at use; the `.active` slide is not the spec's rule.
- DEC-004 (SPEC-0010): "Change marker is the record `revision`, exposed as `requests_revision` in `/status`; the editor fetches `GET /requests` only when it differs." An exact counter, unlike an `mtime`, cannot miss two quick changes.
- Script order (SPEC-0012 DR-006, DEC-008 of SPEC-0010): `slide-layouts.js, doc-blocks.js, editor-undo.js, editor-edit.js, editor-format.js, editor-menus.js, editor-save.js, editor-slides.js, editor-blocks.js, editor-drag.js, editor-requests.js, editor.js`.

### Data model

The requests come from `GET /requests` (US-0052): `{"revision":7,"pending":2,"requests":[{"id","slide","title","queued","instruction","status","reason"}],"suggestions":[...]}`; the pending count in the heading is `pending`. The editor keeps no state of its own besides the remembered slide id and the last revision.

### Contracts

Editor UI element ids (texts are normative):

| Id or selector | Element | Text or behaviour |
|---|---|---|
| `ask-ai-btn` | toolbar button, before `edit-mode-btn` | `Ask AI`; toggles `ask-ai-panel` |
| `ask-ai-panel` | popover under the toolbar (fixed, top 28px, right 12px) | hidden by default |
| `ask-ai-text` | `textarea` | label `Describe the change` (`<label for>`) |
| `ask-ai-slide` | line | `Slide: slide-3`, `Slide: none` when the file has no slide; refreshed at open and at queue |
| `ask-ai-queue` | button | `Queue request`; disabled while a request is in flight; clears the textarea on success, keeps it on failure |
| `ask-ai-message` | `role="status"` line | `Request R-0001 queued` or the server `error` text; set through `textContent`; `requestsShowMessage` opens the panel when closed |
| `requests-side` | `aside`, fixed right 300px under the toolbar, hidden in fullscreen | always visible while a file is open |
| `requests-heading` | heading | `Requests (n)`, n = pending count |
| `requests-list` | `ul` | one `li[data-request-id]` per request, text in `span.request-text`: `<id> <status> <slide or -> <title>` plus ` <reason>` when skipped; button `button.request-delete` `Delete` on every line, no confirmation |

The AI suggestions heading (`suggestions-heading`) and list (`suggestions-list`) are created by `editor-requests.js` in US-0058 and appended to `requests-side`; this story only provides the aside.

Behaviour of `editor-requests.js` (classic script, an IIFE, its only public global, `requestsOnStatus(status)`, is added by US-0056 (this story exposes none); every inner function name starts with `requests` or `askAi`; at most 500 lines; no top level `let` or `const` of `editor.js` read at evaluation time; the iframe is `document.getElementById('content-frame')`):
- On each iframe `load` it attaches `click` and `selectionchange` listeners to the iframe document and remembers `slideIdOf(target or selection anchor)` = `data-id` of the closest `[data-type="slide"]`. At open and at queue the slide is the remembered id if it still exists in the iframe document, else the first slide's `data-id`, else none (sent as `null`, shown as `Slide: none`).
- `Queue request` sends `POST /requests` `{"instruction": <textarea value as typed>, "slide": <id or null>}` with `Content-Type: application/json`; on `{"ok":true,"request":{...}}` it shows `Request <id> queued`, clears the textarea and refetches `GET /requests`; on `{"ok":false,"error":...}` or a network error it shows the `error` text (or the exception message) and keeps the text.
- `Delete` sends `POST /requests/delete` `{"id": ...}`; on failure it shows the server `error` (`Could not delete the request: <error>`) in `ask-ai-message` and the request stays.
- The side list is filled from `GET /requests` (at page start, after each own queue or delete); strings from the record go in through `textContent`, never `innerHTML` (DEC-012).
- `editor.css`: panel, aside, iframe narrowed by 300px (slides keep their 16:9 canvas), the aside hidden in fullscreen (also the fallback rule `body:has(#content-frame:fullscreen)`).
- `editor.html`: the two buttons and containers, and one `<script src="/static/editor-requests.js">` tag after `editor-drag.js` and before `editor.js` (the page then lists twelve scripts).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-requests.js` | create |
| `src/mcp_htmleditor/static/editor.html` | modify: `ask-ai-btn`, `ask-ai-panel`, `requests-side`, one script tag between `editor-drag.js` and `editor.js` |
| `src/mcp_htmleditor/static/editor.css` | modify: panel, aside, iframe width, fullscreen hiding |
| `tests/test_static_scripts.py` | modify: expected script list gains `editor-requests.js` (one line, SPEC-0012 DT-012) |
| `tests/test_requests_editor_e2e.py` | create |

### Existing patterns
- Editor scripts split by SPEC-0012: `editor-save.js`, `editor-slides.js`, `editor-drag.js` (classic scripts, one concern each); `slideIdOf`-style lookups in `editor-slides.js`.
- Playwright harness: `tests/test_autosave_focus_e2e.py:35-80` and the `needs_chromium` / `served_deck` helpers of `tests/conftest.py` (SPEC-0009); queueing helpers from `tests/test_requests_core.py` (US-0052).
- `tests/test_fullscreen_e2e.py` for the fullscreen layout rules; `tools/check_ei_insert.py` loads the editor scripts and needs no change (`editor-requests.js` is independent; check it still passes).
- `tests/test_static_scripts.py` (SPEC-0012 STORY-L): script order, `node --check`, no duplicated top level function name; `tests/test_size_caps.py`: each `static/editor*.js` at most 500 lines.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Preconditions of the Playwright tests: `@needs_chromium`; a real `start_http_server` on a free port; `HTMLEDITOR_STATE_DIR` a `tmp_path` outside the deck folder; DECK is `deck.html` built from `templates/bootstrap/slides-ei-empty.html` extended to 8 slides (`slide-0` to `slide-7`); edit mode is not required for the panel.

### SPEC-0010/E2E-001: Queue a request
- Level E2E; Driver Playwright; Location `tests/test_requests_editor_e2e.py`
- Given DECK open on `slide-3`
- When the user clicks `Ask AI`, types `Shorten the title` in `Describe the change`, clicks `Queue request`
- Then the panel shows `Slide: slide-3` before and `Request R-0001 queued` after; the side list reads `Requests (1)` and holds `R-0001 pending slide-3 Shorten the title`

### SPEC-0010/E2E-008: Empty request
- Level E2E; Driver Playwright plus MCP client; Location `tests/test_requests_editor_e2e.py`
- Given DECK open
- When the user clicks `Queue request` with nothing typed, or with only spaces
- Then the panel shows `Write a request first` and `list_requests` returns no request

### SPEC-0010/E2E-009: Too long
- Level E2E; Driver Playwright; Location `tests/test_requests_editor_e2e.py`
- Given DECK open
- When the user queues a request of 4 001 characters
- Then the panel shows `Request too long (max 4000 characters)` and nothing is stored

### SPEC-0010/E2E-010: Too many pending
- Level E2E; Driver Playwright, 49 requests seeded through `RequestService` then one queued from the UI to reach 50; Location `tests/test_requests_editor_e2e.py`
- Given DECK with 50 pending requests
- When the user queues one more
- Then the panel shows `Too many pending requests (max 50)` and the list still has 50

### SPEC-0010/E2E-020: Storage failure
- Level E2E; Driver Playwright plus the seam (a regular file created at `RequestStore.record_dir(deck)`); Location `tests/test_requests_editor_e2e.py`
- Given DECK open and the place where requests are stored made unwritable
- When the user queues a request
- Then the panel shows `Could not queue the request: ` followed by the error text (non empty, equal to the `OSError` text of `mkdir` on that path), and no request exists

### SPEC-0010/E2E-021: Ids never reused
- Level E2E; Driver Playwright; Location `tests/test_requests_editor_e2e.py`
- Given R-0001 and R-0002 queued, then R-0002 deleted with `Delete`
- When the user queues a new request
- Then its id is `R-0003`

### SPEC-0010/E2E-022: Accents and line breaks
- Level E2E; Driver Playwright plus MCP client; Location `tests/test_requests_editor_e2e.py`
- Given DECK open
- When the user queues the instruction `Mettre « Résumé » en gras` + line break + `puis centrer` and the agent lists requests
- Then `instruction` equals that text exactly, and `title` is `Mettre « Résumé » en gras puis centrer`

### SPEC-0010/E2E-026: Boundary sizes
- Level E2E; Driver Playwright, 49 requests seeded through `RequestService`; Location `tests/test_requests_editor_e2e.py`
- Given DECK with 49 pending requests
- When the user queues a request of exactly 4 000 characters, then another of 4 000 characters
- Then the first is accepted (`Request R-0050 queued`, the existing ids being R-0001 to R-0049) and the second is refused with `Too many pending requests (max 50)`

### SPEC-0010/UT-D01: Script syntax and size
- Level UT; Driver `subprocess` (`node --check`, skipped when `node` is absent) and line count; Location `tests/test_requests_editor_e2e.py`
- Then `node --check src/mcp_htmleditor/static/editor-requests.js` exits 0 and the file has at most 500 lines

### SPEC-0010/UT-D02: Agent text is data
- Level UT; Driver Playwright; Location `tests/test_requests_editor_e2e.py`
- Given a request whose instruction is `<img src=x onerror=window.__xss=1>`
- Then the side list shows that text literally and `window.__xss` is `undefined`

### SPEC-0010/UT-D03: Script order and fullscreen
- Level UT; Driver HTML parse of `editor.html`, and the existing fullscreen suite; Location `tests/test_requests_editor_e2e.py` and `tests/test_static_scripts.py`
- Then the `<script src>` tags of `editor.html` read, in order, `slide-layouts.js, doc-blocks.js, editor-undo.js, editor-edit.js, editor-format.js, editor-menus.js, editor-save.js, editor-slides.js, editor-blocks.js, editor-drag.js, editor-requests.js, editor.js` (the expected list in `tests/test_static_scripts.py` is updated by this story), `GET /static/editor-requests.js` is 200 with `Cache-Control: no-store`, and `tests/test_fullscreen_e2e.py` passes unmodified (`#requests-side` hidden in fullscreen, iframe 100vw)

## Constraints

- Files not to touch: `editor.js` (the poll hook is US-0056), `request_service.py`, `http_server.py`, other static scripts.
- Dependencies not to add: none allowed (vanilla JS, no module system).
- Patterns to avoid: `innerHTML` with record strings; reading `editor.js` top level bindings at evaluation time; a top level function name defined twice across scripts; the `.active` slide as the current slide (DEC-013); `alert` or `confirm` (`Delete` has no confirmation).
- Scope boundary: no `requestsOnStatus`, no AI suggestions list, no review.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_fullscreen_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_undo_redo_e2e.py`, `tests/test_static_scripts.py`, `tests/test_size_caps.py` and `tools/check_ei_insert.py` pass; the editor still saves and polls.
- [ ] Docs updated: none in this story (the closing story documents the feature).
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0055: Ask AI panel and the requests side list`, body `Spec: SPEC-0010` and the requirement ids FR-NEW-001, FR-NEW-005.
