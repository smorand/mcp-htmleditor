# US-0145: Delete a presentation for good

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0144, US-0138, US-0140
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective

A person with RW (or the administrator) deletes a presentation after the question `Delete "<name>"? This cannot be undone.`; the presentation, its history and its requests are removed for good, a name uploaded again starts clean, a stale link or a save into it gives `Access denied.` and recreates nothing, and a hostile page or script cannot delete.

## Requirements covered

- SPEC-0025/FR-NEW-039: WHEN a person with RW chooses to delete a presentation THE web library mode SHALL ask: Delete "<name>"? This cannot be undone. and, on confirmation, remove the presentation and its history for good.
  - Business rules: There is no trash and no way back. The buttons are "Delete" and "Cancel"; "Cancel" changes nothing. The requests queued for the presentation and the AI suggestions shown for it are removed with it: a presentation uploaded again under the same name starts with an empty Requests list and no suggestion.
- SPEC-0025/FR-NEW-023 (partial: a RO person deleting by hand gets `Access denied.` and nothing changes): The web library mode SHALL NOT let a person who holds only RO in a folder edit, upload or delete in it: the controls are absent and any attempt made outside the interface, including the storing of a change, is refused with "Access denied." and has no effect.
  - Business rules: Absent for RO: the Upload and Delete controls, edit mode, undo, redo, notes editing, requests, slide and block actions. The key E does nothing. Reading the queued requests and the AI suggestions of a presentation is refused with "Access denied." for a person who holds only RO.
- SPEC-0025/FR-NEW-048 (partial: a deletion applies to the next action of a person editing or following a stale link): WHEN the administrator removes a person, changes their role, or deletes the folder THE web library mode SHALL apply the change to that person's next action in that folder, refusing it with "Access denied." when it is no longer allowed, and storing nothing.
  - Business rules: Content already displayed stays on screen; no new content loads. A presentation open for editing keeps its unsaved changes on screen; the refusal appears at the next automatic store as the editor's only notice "Access denied." (no "Save failed:" prefix). An upload still being sent when the right is removed is refused at its end and stores nothing. A raised role (RO to RW) also applies from the next action. When the person has typed nothing that is not stored, FR-NEW-074 applies: no notice until the person acts.
- SPEC-0025/FR-NEW-049 (partial: the line `Deleted "<name>" from "<folder>"`): WHEN an upload, a replacement or a deletion of a presentation, the creation or deletion of a folder, or the adding, changing or removing of a member succeeds THE web library mode SHALL add a line to the activity list with who did it, when, and what.
  - Business rules: Line texts: Uploaded "<name>" in "<folder>"; Replaced "<name>" in "<folder>"; Deleted "<name>" from "<folder>"; Created folder "<folder>"; Deleted folder "<folder>"; Added <email> as RW to "<folder>" (or RO); Changed <email> to RO in "<folder>" (or RW); Removed <email> from "<folder>". Who is the email address of the person; when is shown as on the folder page. Who is the email address of the person in lower case, whatever letter case Google returned.
- SPEC-0025/FR-NEW-052 (partial: a deck script cannot delete as the viewer or reach another folder): The web library mode SHALL NOT let a script contained in a presentation read what the browser keeps for the library, act with the identity of the person viewing it, or reach another folder.
  - Business rules: The scripts still run for the presentation itself (navigation, animations), as in the local mode.
- SPEC-0025/FR-NEW-070 (partial: a page of another site, a look alike site or a request with no sign of coming from the library cannot delete): IF a request that changes the library comes from a page of another site, or carries no sign that it comes from the library's own pages, THEN THE web library mode SHALL refuse it with "Access denied." and change nothing, even when it carries a valid session.
  - Business rules: The rule covers every change: storing a change, upload, delete, folder, member and request actions. A request made by the library's own pages, on slides.scm-platform.org, is never affected.

## Independent Test

Run `make test ARGS='-k library_delete'`. The assertion that is not a mock: after deletion `StoredLibrary.entries()` holds neither the file nor `<state_dir>/files/<key>/` (history, requests), the row is gone, and uploading the same name again lists one presentation with `list_versions == []` and an empty request record.

## Design excerpt

### Decisions

- DEC-022 (SPEC-0025): Every state changing request (any method other than `GET`, `HEAD` and `OPTIONS`: `POST` and `DELETE`) is refused with `Access denied.`, before the session is looked up, unless `Origin` is present and equals the origin of the receiving host exactly, and `Sec-Fetch-Site`, when present, is `same-origin` (or `none`); JSON routes also require `Content-Type: application/json`, the upload requires the header `X-File-Name`. The local rule that accepts a missing `Origin` is not used. Obliged by: SPEC-0025/FR-NEW-070, SPEC-0025/FR-NEW-023.
- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-026 (SPEC-0025): Writes of presentation bytes use `atomic_write(path, data, reason=...)` (reasons `browser-save`, `keep-mine`, `replace`); history and request records stay in the state directory keyed by the resolved path; `delete_presentation` and `delete_folder` remove the row first, then the file, then `<state_dir>/files/<key>/` (history, requests, update flag) of each presentation. Obliged by: SPEC-0025/FR-NEW-026, SPEC-0025/FR-NEW-034, SPEC-0025/FR-NEW-039, SPEC-0025/FR-NEW-043, SPEC-0025/FR-NEW-063.
- DEC-028 (SPEC-0025): One `threading.Lock` per presentation id, held by `_save_lock()`, by an upload replacement and by a deletion; `_save_lock()` returns a context manager that acquires the lock and then re-checks that the presentation row still exists, raising `SaveRefusal(403, {"error": "Access denied.", "code": "denied"})` when it does not, so a save that lost the race with a deletion creates nothing; the conflict check (`check_conflict`) runs inside it. Obliged by: SPEC-0025/FR-NEW-027, SPEC-0025/FR-NEW-063.
- DEC-030 (SPEC-0025): Activity is the table `activity`, one row per successful action written in the same transaction as the action, with the final line text and the actor's lower case address; after each insert rows older than the 500 newest are deleted; the page reads `ORDER BY id DESC LIMIT 500`. Refusals, sign ins and stored changes never write. Obliged by: SPEC-0025/FR-NEW-049, SPEC-0025/FR-NEW-050, SPEC-0025/FR-NEW-051.
- DEC-048 (SPEC-0025): Logging and tracing follow the project rules: `logger = logging.getLogger(__name__)`, `%` formatting, stderr console, `click.echo` only for the start line; spans `auth.google_token`, `library.upload`, `library.replace`, `library.delete_presentation`, `library.delete_folder`, `library.seed`, `session.create`, with sizes and status codes only; no email, name, token, cookie or credential in a log line or an attribute. Obliged by: SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-020 (nothing about members leaks), AGENTS.md observability rules.

### Data model

No change.

### Contracts

**Route**: `DELETE /api/presentations/<pid>` (what the page sends) and `POST /api/presentations/<pid>/delete` (what a plain form can send; same handler) (library origin, `EDIT` on the presentation's folder resolved from `Library.presentation(pid)`, origin rule). Unknown id, malformed id, no role: the same `403` `Access denied.` page bytes as every refusal (DEC-023) before anything else. Success: `200 {"ok": true}`.

`Library.delete_presentation(pid: str, actor: str) -> None`: takes `lock_for(pid)`; one `BEGIN IMMEDIATE` transaction deletes the row and inserts the activity line `Deleted "<name>" from "<folder>"`; after commit unlinks the file and removes `<state_dir>/files/<key>/` (history, requests, update flag) ignoring `FileNotFoundError`, logging other `OSError` with `logger.warning`; wrapped in `trace_span("library.delete_presentation", {})`. A deletion never creates a file; the `PresentationLock` of US-0136 makes a save that lost the race answer `Access denied.` without writing.

**UI**: each row of the folder page shows a `Delete` button for RW and Admin only; it opens a `<dialog>` with `Delete "<name>"? This cannot be undone.` (name via `textContent`, accents and apostrophes as written) and the buttons `Delete` and `Cancel`; a confirmation for an already deleted presentation shows `Access denied.` and refreshes the list; deleting the last presentation shows `This folder has no presentations yet.`.

**Cross site and script**: the origin rule (DEC-022) refuses the form post of E2E-SEC-017 and the look alike origin of E2E-182; the deck script of E2E-SEC-014 runs on the content origin where no delete route exists and no library cookie is sent, so its `DELETE` is a cross origin request that is preflighted and refused by `do_OPTIONS` (`http_server.py:265-271`).

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/store.py` | modify | `delete_presentation` |
| `src/mcp_htmleditor/library/routes_library.py` | modify | delete route |
| `src/mcp_htmleditor/library/pages.py` | modify | Delete control and dialog |
| `src/mcp_htmleditor/static/library.js` | modify | dialog and request |
| `tests/test_library_delete_http.py` | create | functional tests and E2E-SEC-009 (`test_exploit_*`) |
| `tests/test_library_delete_e2e.py` | create | browser tests and E2E-SEC-014, E2E-SEC-017 (`test_exploit_*`) |

### Existing patterns

`tests/test_http_origin_e2e.py` for foreign origin tests; `tests/test_library_foldel_http.py` (US-0131) for the state directory assertions; `tests/test_save_safety_e2e.py` for editing while a file changes.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-025: A link to a deleted presentation is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_delete_http.py`
- **Category:** failure (state transition, side effect)
- **Scenario:** SC-004
- **Requirements:** FR-NEW-010, FR-NEW-039
- **Given** carol.ro@example.org kept the link to "Statins Review"; dan.rw@example.org then deleted "Statins Review".
- **When** Carol opens her link.
- **Then** "Access denied." is shown.
- **And** The folder page of "Cardiology 2027" now lists two presentations.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-033: Roles are per folder: RO in one, RW in another

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-005
- **Requirements:** FR-NEW-015, FR-NEW-021, FR-NEW-023, FR-NEW-024
- **Given** carol.ro@example.org is RO in "Cardiology 2027" and RW in "Pneumo Été".
- **When** She opens each folder, then uploads the valid file "Spirometry Basics.html" in "Pneumo Été".
- **Then** In "Cardiology 2027" there is no Upload and no Delete; in "Pneumo Été" both exist and "Uploaded Spirometry Basics." is shown. The home page labels the two folders "Read only" and "Read and write".
- **And** The administrator sees "Spirometry Basics" in "Pneumo Été" only.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-036: A RW member sees the upload and delete controls in their folder

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** happy
- **Scenario:** SC-006
- **Requirements:** FR-NEW-024, FR-NEW-025, FR-NEW-028, FR-NEW-039
- **Given** dan.rw@example.org is RW in "Cardiology 2027".
- **When** He opens the folder page and then "Heart Failure Update".
- **Then** "Upload" is shown on the folder page and "Delete" on each of the three rows; the presentation opens in the full editor with edit mode available.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-040: A RW member does everything with the keyboard

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** edge
- **Scenario:** SC-006
- **Requirements:** FR-NEW-024, FR-NEW-028, FR-NEW-064
- **Given** dan.rw@example.org uses the keyboard only; the valid file "Quarterly Review.html" is ready.
- **When** He tabs to "Upload", chooses the file and confirms, then tabs to "Delete" on that row, confirms, and leaves with "Sign out".
- **Then** "Uploaded Quarterly Review." is shown, then the presentation is gone, then the sign in page is shown.
- **And** Every control he used has a visible label.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-053: Saving a deleted presentation is refused

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-010, FR-NEW-026, FR-NEW-039
- **Given** dan.rw@example.org is editing "Statins Review"; the administrator deletes it.
- **When** Dan leaves the edited field.
- **Then** "Access denied." is shown as the editor's only notice; his text stays on screen.
- **And** "Statins Review" is not recreated: the folder lists 2 presentations.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-079: A RW member deletes a presentation

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** happy (side effect, state transition)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-024, FR-NEW-039, FR-NEW-049
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; "Statins Review" has 2 versions in its history.
- **When** He chooses Delete on "Statins Review" and confirms with "Delete".
- **Then** The question Delete "Statins Review"? This cannot be undone. is shown first; then the list shows 2 presentations.
- **And** carol.ro@example.org's list shows 2 presentations.
- **And** The history of "Statins Review" is gone: the operator's listing of its history shows nothing.
- **And** The activity list gains "Deleted "Statins Review" from "Cardiology 2027"".
- **And** "Cancel" was offered next to "Delete".
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-080: Cancel keeps the presentation

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-039
- **Given** The question Delete "Statins Review"? This cannot be undone. is shown to dan.rw@example.org.
- **When** He chooses "Cancel".
- **Then** The folder page still lists "Statins Review".
- **And** Its history is intact; no activity line was added.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-081: Confirming the deletion of an already deleted presentation is refused

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-010, FR-NEW-039
- **Given** dan.rw@example.org shows the delete question for "Statins Review"; the administrator deletes it first.
- **When** Dan confirms.
- **Then** "Access denied." is shown and the refreshed list has 2 presentations.
- **And** The activity list holds one deletion line, the administrator's.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-082: A deleted name can be uploaded again without a question

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_delete_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-028, FR-NEW-033, FR-NEW-039
- **Given** "Statins Review" was deleted by dan.rw@example.org.
- **When** He uploads a valid "Statins Review.html".
- **Then** "Uploaded Statins Review." is shown with no question.
- **And** The history of the new presentation is empty: no version of the deleted one comes back.
- **And** Before the deletion "Statins Review" had a queued request "Make the title shorter" and an AI suggestion; after the new upload its Requests list is empty and no suggestion is shown.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-083: The question shows an accented name with an apostrophe as written

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-019, FR-NEW-039, FR-NEW-053
- **Given** "Pneumo Été" holds only "L'été (v2)"; the administrator is signed in.
- **When** He chooses Delete on it, chooses "Cancel", chooses Delete again and confirms.
- **Then** The question reads Delete "L'été (v2)"? This cannot be undone. exactly; afterwards "This folder has no presentations yet." is shown.
- **Priority:** Low
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-088: A member entry cannot reduce the administrator

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_delete_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-013
- **Requirements:** FR-NEW-012, FR-NEW-014, FR-NEW-045
- **Given** The administrator is listed RO in "Cardiology 2027".
- **When** He deletes "Arrhythmia Basics" there.
- **Then** The deletion succeeds.
- **And** His label on the home page is still "Admin".
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-140: Refused attempts are not recorded

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_delete_http.py`
- **Category:** failure
- **Scenario:** SC-022
- **Requirements:** FR-NEW-003, FR-NEW-023, FR-NEW-049, FR-NEW-051
- **Given** carol.ro@example.org attempts by hand an upload and a deletion; bob.nobody@gmail.com signs in and is refused; then dan.rw@example.org successfully uploads "Quarterly Review" into "Cardiology 2027".
- **When** The administrator opens the activity list.
- **Then** The list holds exactly one line, Uploaded "Quarterly Review" in "Cardiology 2027", attributed to dan.rw@example.org; no line about Carol's attempts nor Bob's sign in.
- **And** The list does not show "No activity yet."
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-181: Changes made from the library's own pages are accepted

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-019
- **Requirements:** FR-NEW-024, FR-NEW-028, FR-NEW-070
- **Given** dan.rw@example.org is signed in on slides.scm-platform.org.
- **When** He uploads "Quarterly Review.html" and then deletes it, both from the library's pages.
- **Then** "Uploaded Quarterly Review." is shown, then the presentation is gone.
- **And** No "Access denied." appeared.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-182: A look alike site is another site

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_delete_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-019
- **Requirements:** FR-NEW-070
- **Given** dan.rw@example.org is signed in; a page at https://slides.scm-platform.org.evil.example submits the deletion of "Statins Review" in his browser.
- **When** The page loads.
- **Then** "Access denied." is returned to the page.
- **And** The administrator's view of "Cardiology 2027" still lists "Statins Review".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-009: A RO member deletes by hand

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_delete_http.py`
- **Category:** security
- **Covers:** Class B occurrence #1
- **Red before the fix because:** the presentation is removed; the assertion "Statins Review is still listed to the administrator" fails.
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-039
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; with her own signed in session, from a command line tool outside the editor, she sends the request the library sends when a RW member deletes "Statins Review" from "Cardiology 2027".
- **When** She sends it.
- **Then** "Access denied." is returned.
- **And** The administrator's view of "Cardiology 2027" still lists "Statins Review" (1.5 MB) and its history.
- **And** The activity list has no deletion line.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-014: A presentation's script cannot act as the viewer or reach other folders

- Level / Driver / Location: exploit / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** security
- **Covers:** Class C occurrences #1, #2, #4, #6 and #7
- **Red before the fix because:** the script deletes "Statins Review" with Dan's rights; the assertion "Statins Review is still listed to the administrator" fails.
- **Scenario:** SC-018
- **Requirements:** FR-NEW-020, FR-NEW-023, FR-NEW-052
- **Given** The presentation "Heart Failure Update" carries this script on slide 1: <script>fetch(LIST_OF_WCBIP_ADDRESS).then(r => r.text()).then(t => { probe.textContent = 'list: ' + t.slice(0, 200); }); fetch(DELETE_STATINS_REVIEW_ADDRESS, {method: 'DELETE'}).then(r => { probe.textContent += ' delete: ' + r.status; });</script> where the two addresses are the real ones of the library, filled in by the test, and an element "probe"; carol.ro@example.org (RO) opens it, then dan.rw@example.org (RW) opens it.
- **When** Each shows slide 1.
- **Then** The element "probe" shows no name from "WCBIP Melbourne Décembre 2026" and no deletion happens for either of them.
- **And** The administrator's view of "Cardiology 2027" still lists "Statins Review" and its history.
- **And** The activity list has no deletion line.
- **And** Carol then downloads the PPTX of the presentation: it is delivered and its text holds no name from "WCBIP Melbourne Décembre 2026" (the product opening the presentation to build it gives the script no more power).
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the PPTX facet needs US-0140 (earlier in the queue than this story).

### SPEC-0025/E2E-SEC-017: A page of another site deletes with the visitor's session

- Level / Driver / Location: exploit / Playwright / `tests/test_library_delete_e2e.py`
- **Category:** security
- **Covers:** Class G occurrences #2 and #3
- **Red before the fix because:** the deletion is accepted because the browser attached Dan's session; the assertion "Statins Review is still listed to the administrator" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-023, FR-NEW-039, FR-NEW-070
- **Given** dan.rw@example.org is signed in (RW in "Cardiology 2027"); in the same browser he opens the page https://evil.example/win that, on load, submits a form to the library's deletion of "Statins Review" from "Cardiology 2027".
- **When** The page loads.
- **Then** The library answers "Access denied.".
- **And** The administrator's view of "Cardiology 2027" still lists "Statins Review" (1.5 MB) and its history.
- **And** The activity list has no deletion line.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

## Constraints

- Row first, then file, then state directory; failures after the commit are logged, not raised.
- No trash, no soft delete.
- Scope boundary: nothing else is deleted here (folders: US-0131).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (deletion).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0145: Delete a presentation for good` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
