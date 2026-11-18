# US-0138: Requests, Ask AI and arch layout work for editors and are refused to read only people

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0136
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

The Requests panel, Ask AI, request deletion, suggestion application and the diagram layout work in the library for a person who can edit, using the existing request loop of the local mode on the presentation's own record; a RO person is refused every one of them, including the read, and nobody can export a DOCX.

## Requirements covered

- SPEC-0025/FR-NEW-023 (partial: reading the Requests list and AI suggestions, queueing, deleting, applying and computing the diagram layout are refused to a RO person with `Access denied.`; the DOCX export is refused to everyone): The web library mode SHALL NOT let a person who holds only RO in a folder edit, upload or delete in it: the controls are absent and any attempt made outside the interface, including the storing of a change, is refused with "Access denied." and has no effect.
  - Business rules: Absent for RO: the Upload and Delete controls, edit mode, undo, redo, notes editing, requests, slide and block actions. The key E does nothing. Reading the queued requests and the AI suggestions of a presentation is refused with "Access denied." for a person who holds only RO.
- SPEC-0025/FR-NEW-025 (partial: the Requests panel, Ask AI and every other editor option work for a person who can edit): The web library mode SHALL give a person who can edit a presentation every option of the editor of the local mode, working as it does there.
  - Business rules: Options: edit mode, undo, redo, notes, presenter window, full screen, pointer, requests, Ask AI, HTML and PPTX download, keyboard shortcuts, help. A person who holds only RO gets the same screen without any control that changes the presentation (FR-NEW-023).

## Independent Test

Run `make test ARGS='-k library_requests'`. The assertion that is not a mock: Carol (RO) sends in turn the six requests of the spec; each answer is `403 Access denied.`; Dan's `GET /d/<pid>/requests` still holds exactly one request and the stored file did not change.

## Design excerpt

### Decisions

- DEC-003 (SPEC-0025): Reuse the editor routes through five overridable methods of `_EditorHandler` (`_served_file`, `_served_name`, `_save_lock`, `_failure_reason`, `_pptx_options`; `_save_lock` returns a context manager, the local one is the existing `threading.Lock`), give `_EditorServer.__init__` a `handler` parameter defaulting to `_EditorHandler`, and implement the library as `LibraryHandler(_EditorHandler)` that overrides `do_GET`, `do_POST` and `_serve_status` only. The defaults reproduce the previous expressions byte for byte. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-055.
- DEC-022 (SPEC-0025): Every state changing request (any method other than `GET`, `HEAD` and `OPTIONS`: `POST` and `DELETE`) is refused with `Access denied.`, before the session is looked up, unless `Origin` is present and equals the origin of the receiving host exactly, and `Sec-Fetch-Site`, when present, is `same-origin` (or `none`); JSON routes also require `Content-Type: application/json`, the upload requires the header `X-File-Name`. The local rule that accepts a missing `Origin` is not used. Obliged by: SPEC-0025/FR-NEW-070, SPEC-0025/FR-NEW-023.
- DEC-026 (SPEC-0025): Writes of presentation bytes use `atomic_write(path, data, reason=...)` (reasons `browser-save`, `keep-mine`, `replace`); history and request records stay in the state directory keyed by the resolved path; `delete_presentation` and `delete_folder` remove the row first, then the file, then `<state_dir>/files/<key>/` (history, requests, update flag) of each presentation. Obliged by: SPEC-0025/FR-NEW-026, SPEC-0025/FR-NEW-034, SPEC-0025/FR-NEW-039, SPEC-0025/FR-NEW-043, SPEC-0025/FR-NEW-063.
- DEC-044 (SPEC-0025): Routes that must not exist in the library: DOCX export (`/d/<pid>/export/docx` is `Access denied.` for every role), the picture render, `new_file`, every MCP tool, `/arch-layout` on the library origin. Obliged by: SPEC-0025/FR-NEW-022, SPEC-0025/FR-NEW-052.

### Data model

No change. Request records live in `<state_dir>/files/<key>/requests/` keyed by the presentation file path (`request_store.py:87-90`).

### Contracts

**Routes** (content origin, `EDIT`, origin rule for POST): `GET /d/<pid>/requests` (`_list_requests`, `http_server.py:509`), `POST /d/<pid>/requests` (`_queue_request`, `:521`), `POST /d/<pid>/requests/delete` (`_delete_request`, `:535`), `POST /d/<pid>/review/apply` (`_apply_suggestion`, `:552`), `POST /d/<pid>/arch-layout` (`_run_arch_layout`, `:653`). All are the inherited methods reached through the hooks; `_loaded_file()` returns `Path(self._served_file())`. `GET /d/<pid>/export/docx` and every other path give `403` `Access denied.` (DEC-044). A RO role gets `403 {"error": "Access denied.", "code": "denied"}` for each, including the GET.

The record is the presentation's own: a deletion of the presentation (US-0145) and a deletion of the folder (US-0131) remove it with the state directory; a replacement (US-0144) keeps it.

**Editor**: the Requests panel and Ask AI call `/requests` and friends through the fetch wrapper of US-0134; nothing to change in the editor.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/routes_deck.py` | modify | request routes rows |
| `tests/library_support.py` | modify | request queue helpers |
| `tests/test_library_requests_http.py` | create | E2E-SEC-023 (`test_exploit_*`) and the import grep test |

### Existing patterns

`tests/test_requests_editor_e2e.py` and `tests/test_requests_refresh_e2e.py` for the panel; `tests/test_review_apply_e2e.py` for suggestions; `request_service.py:67-180` for the service.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-SEC-023: A RO member sends the other changing requests by hand

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_requests_http.py`
- **Category:** security
- **Covers:** Class B occurrence #1 and Class G occurrence #3
- **Red before the fix because:** the requests are accepted and the lists are readable; the assertion "Carol's reading of the Requests list is refused" fails and returns "Check the 2026 guideline".
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-070
- **Given** dan.rw@example.org queued the request "Check the 2026 guideline" on "Heart Failure Update"; carol.ro@example.org is RO in "Cardiology 2027"; with her own signed in session, from a command line tool outside the editor, she sends in turn: the request that recomputes the layout of the diagrams of "Heart Failure Update", the request that adds a request "Make the title shorter" to its Requests list, the request that deletes a request of that list, the request that applies an AI suggestion to it, the request that reads the Requests list and the AI suggestions, and the request for its DOCX export.
- **When** She sends the six requests.
- **Then** Each answer is "Access denied.", the reading of the Requests list included; no file is received for the DOCX request.
- **And** dan.rw@example.org opens "Heart Failure Update": its size is still 2 097 152 bytes and its Requests list holds exactly the request "Check the 2026 guideline".
- **And** The history lists no new version.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

`tests/test_library_requests_http.py` also holds the grep test over `library/routes_*.py` forbidding `deck.tools`, `to_docx`, `render` imports (DEC-044), and the functional tests of the routes for a person who can edit: Dan queues a request (`POST /d/<pid>/requests`) and reads it back (`GET /d/<pid>/requests`, revision grows), deletes it (`POST /d/<pid>/requests/delete`), applies a suggestion written with `RequestService.write_review` (`POST /d/<pid>/review/apply`), and computes a diagram layout (`POST /d/<pid>/arch-layout`) on a deck that holds one declarative diagram; the editor panels themselves are exercised by the full option test of the PPTX story.

## Constraints

- Reuse the inherited methods; do not reimplement the request loop.
- No `to_docx` import in any `library/routes_*.py` (a test greps).
- Scope boundary: PPTX (US-0140).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (request routes).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0138: Requests, Ask AI and arch layout work for editors and are refused to read only people` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
