# US-0136: Edit a presentation and store changes by themselves

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0135
> min_tier: 1
> Files touched: 5
> Closes spec: no

## Objective

A person with RW (or the administrator) edits a presentation in the same editor as the local mode: the change is stored 0.8 s after typing stops, at once when the field is left, 0.6 s after a slide action; the previous version goes to the history; a second person who changed the file meanwhile makes the conflict notice appear with `Keep mine` and `Reload`; there is no Save control.

## Requirements covered

- SPEC-0025/FR-NEW-026: WHEN a person with RW leaves a field they changed THE web library mode SHALL store the edited version in its folder at once and keep the previous version in the history of the presentation.
  - Business rules: The same storing happens 0.8 seconds after typing stops (FR-NEW-066). Stored changes are not recorded in the activity list (FR-NEW-051).
- SPEC-0025/FR-NEW-027: WHEN a person leaves a field in which they typed text not yet stored, and someone else changed the stored presentation after their screen last showed it, THE web library mode SHALL show the conflict notice with "Keep mine" and "Reload" and store nothing until they choose.
  - Business rules: Notice text, as in the local mode: "The file changed on disk. Reload to see the changes, or keep your version." "Keep mine" stores the person's version and keeps the other version in the history; "Reload" shows the stored version and drops the unsaved changes. The notice arises only for a person who has unsaved typed text. A person with no unsaved text sees the other person's stored version replace their screen within 2 seconds, with no notice, as in the local mode.
- SPEC-0025/FR-NEW-066: WHILE a person with RW has a presentation open for editing THE web library mode SHALL store each change 0.8 seconds after the person stops typing, and at once when the person leaves the edited field, and SHALL offer no Save control.
  - Business rules: As in the local mode there is no Save control and no Save key. A slide or block action (insert, delete, move) is stored 0.6 seconds after the action. When storing fails the editor shows its usual failure notice with the reason and keeps the change on screen. A stored change is accepted up to 52 428 800 bytes, as in the local mode; above that the editor's usual failure notice is shown.
- SPEC-0025/FR-NEW-023 (partial: a RO session posting a change by hand gets `Access denied.` and nothing is stored): The web library mode SHALL NOT let a person who holds only RO in a folder edit, upload or delete in it: the controls are absent and any attempt made outside the interface, including the storing of a change, is refused with "Access denied." and has no effect.
  - Business rules: Absent for RO: the Upload and Delete controls, edit mode, undo, redo, notes editing, requests, slide and block actions. The key E does nothing. Reading the queued requests and the AI suggestions of a presentation is refused with "Access denied." for a person who holds only RO.
- SPEC-0025/FR-NEW-024 (partial: a RW member or the administrator edits any presentation of the folder): WHILE a person holds RW in a folder, or is Admin, THE web library mode SHALL additionally let them edit its presentations with every editor option (changes are stored by themselves), upload and delete in that folder.
  - Business rules: The Upload control is on the folder page; Delete is on each presentation row. Any RW member can change, replace or delete any presentation of the folder, whoever uploaded it.
- SPEC-0025/FR-NEW-025 (partial: every editor option works for a person who can edit): The web library mode SHALL give a person who can edit a presentation every option of the editor of the local mode, working as it does there.
  - Business rules: Options: edit mode, undo, redo, notes, presenter window, full screen, pointer, requests, Ask AI, HTML and PPTX download, keyboard shortcuts, help. A person who holds only RO gets the same screen without any control that changes the presentation (FR-NEW-023).
- SPEC-0025/FR-NEW-063 (partial: a save shows the complete previous or complete new version, never a mix): The web library mode SHALL show a person, at any instant, either the complete previous or the complete new version of a presentation that is being saved or replaced, never a mix and never an empty file.
  - Business rules: none beyond the statement.

## Independent Test

Run `make test ARGS='-k "library_edit"'`. The assertion that is not a mock: after Dan changes the title of slide 1 in a browser, `HistoryStore.list_versions(path)` holds one version whose bytes are the old file, and Carol's `GET /d/<pid>/content` returns the new title and the file size changed; in the conflict case exactly one of the two titles is stored and the other is in the history.

## Design excerpt

### Decisions

- DEC-003 (SPEC-0025): Reuse the editor routes through five overridable methods of `_EditorHandler` (`_served_file`, `_served_name`, `_save_lock`, `_failure_reason`, `_pptx_options`; `_save_lock` returns a context manager, the local one is the existing `threading.Lock`), give `_EditorServer.__init__` a `handler` parameter defaulting to `_EditorHandler`, and implement the library as `LibraryHandler(_EditorHandler)` that overrides `do_GET`, `do_POST` and `_serve_status` only. The defaults reproduce the previous expressions byte for byte. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-055.
- DEC-022 (SPEC-0025): Every state changing request (any method other than `GET`, `HEAD` and `OPTIONS`: `POST` and `DELETE`) is refused with `Access denied.`, before the session is looked up, unless `Origin` is present and equals the origin of the receiving host exactly, and `Sec-Fetch-Site`, when present, is `same-origin` (or `none`); JSON routes also require `Content-Type: application/json`, the upload requires the header `X-File-Name`. The local rule that accepts a missing `Origin` is not used. Obliged by: SPEC-0025/FR-NEW-070, SPEC-0025/FR-NEW-023.
- DEC-026 (SPEC-0025): Writes of presentation bytes use `atomic_write(path, data, reason=...)` (reasons `browser-save`, `keep-mine`, `replace`); history and request records stay in the state directory keyed by the resolved path; `delete_presentation` and `delete_folder` remove the row first, then the file, then `<state_dir>/files/<key>/` (history, requests, update flag) of each presentation. Obliged by: SPEC-0025/FR-NEW-026, SPEC-0025/FR-NEW-034, SPEC-0025/FR-NEW-039, SPEC-0025/FR-NEW-043, SPEC-0025/FR-NEW-063.
- DEC-028 (SPEC-0025): One `threading.Lock` per presentation id, held by `_save_lock()`, by an upload replacement and by a deletion; `_save_lock()` returns a context manager that acquires the lock and then re-checks that the presentation row still exists, raising `SaveRefusal(403, {"error": "Access denied.", "code": "denied"})` when it does not, so a save that lost the race with a deletion creates nothing; the conflict check (`check_conflict`) runs inside it. Obliged by: SPEC-0025/FR-NEW-027, SPEC-0025/FR-NEW-063.
- DEC-032 (SPEC-0025): Time and faults are injected, not patched globally: `LibraryServer(clock=time.time)` hands the clock to every repository; the test seams are `Database.connect` (raise `sqlite3.OperationalError` to simulate an unreadable library), `fileio.replace_file` (`fileio.py:44-46`, already the documented failure seam, raise `OSError(errno.ENOSPC)`), and a socket wrapper in tests that cuts a connection at a byte count. Obliged by: SPEC-0025/FR-NEW-005, SPEC-0025/FR-NEW-006, SPEC-0025/FR-NEW-017, SPEC-0025/FR-NEW-038.

### Data model

No change. History records stay in `<state_dir>/files/<key>/history/` (`history.py:28`, `HISTORY_LIMIT = 20`).

### Contracts

**Routes** (content origin, `EDIT`, origin rule with the content origin, `Content-Type: application/json`): `POST /d/<pid>/content` is the inherited `_receive_content` (`http_server.py:625`) reached through `LibraryHandler`: resolution (`grant`, presentation, role) and `authorize(role, EDIT)` first, then `_read_save_request` (50 MiB cap, `MAX_SAVE_BYTES`, `http_server.py:85`), `check_conflict` (mtime), `write_save` with `atomic_write(..., reason="browser-save"|"keep-mine")`. `_save_lock()` returns a `PresentationLock` context manager (in `library/server.py`): it acquires the lock of that presentation id from `LibraryServer.locks: dict[str, threading.Lock]` (guarded by one `threading.Lock`) and then re-checks that the presentation row still exists, raising `SaveRefusal(403, {"error": "Access denied.", "code": "denied"})` when it does not (`_receive_content` already answers a `SaveRefusal`, `http_server.py:636-640`) (DEC-028). `refuse_template(file)` is harmless for library paths (no `/templates/bootstrap/` segment) and stays in the inherited code.

Answers are those of the local mode: `200 {"ok": true, "mtime": <float>}`, `409 {"ok": false, "error": "File changed on disk", "mtime": <float>}`, `413 {"error": "Request too large"}`, `500 {"error": <operating system reason>}` through `_failure_reason` (DEC-042). A role without `EDIT` gets `403 {"error": "Access denied.", "code": "denied"}` before the body is read.

**Disk full seam**: `fileio.replace_file` (`fileio.py:44-46`) patched to raise `OSError(errno.ENOSPC, "No space left on device")`; the editor then shows `Save failed: No space left on device` and keeps the text.

**Browser behavior** (nothing to code): the editor's own timers (`editor-save.js:4-6`, 800 ms, immediate on blur, 600 ms for slide actions) work through the fetch wrapper of US-0134.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/routes_deck.py` | modify | save route and lock |
| `src/mcp_htmleditor/library/server.py` | modify | `locks` registry |
| `tests/library_support.py` | modify | editor helpers: type in the frame, wait for save, `HistoryStore` view |
| `tests/test_library_edit_http.py` | create | E2E-124, E2E-141, E2E-SEC-008 (`test_exploit_*`), 50 MB boundary |
| `tests/test_library_edit_e2e.py` | create | browser tests |

### Existing patterns

`tests/test_save_safety_e2e.py` (conflict, Keep mine, Reload), `tests/test_autosave_focus_e2e.py` (timers), `tests/test_save_ui_e2e.py`, `tests/test_history_e2e.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-027: Presentations with equal times keep a stable order

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018, FR-NEW-026
- **Given** "Arrhythmia Basics" and "Statins Review" were both modified 12 Nov 2026 16:40.
- **When** dan.rw@example.org opens the folder page 5 times, refreshing each time; then he changes the title of "Statins Review" at 17:30 and leaves the field.
- **Then** The first 5 displays show "Arrhythmia Basics" before "Statins Review"; after the change "Statins Review" is first, with 12 Nov 2026 17:30.
- **And** Two other presentations modified in the same minute, "éclair" and "Eclair", are listed "Eclair" then "éclair": same sorting key, then exact name by character code.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the product clock for a saved file is the file system's `st_mtime`; the test performs the real save, then sets the saved file's modified time to 17:30 on 12 Nov 2026 with `os.utime`, and refreshes the folder page.

### SPEC-0025/E2E-034: A RO viewer sees a writer's saved change without gaining controls

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** edge
- **Scenario:** SC-005
- **Requirements:** FR-NEW-022, FR-NEW-025, FR-NEW-026
- **Given** carol.ro@example.org has "Heart Failure Update" open; dan.rw@example.org changes the title to "Heart Failure Update 2027" and leaves the field.
- **When** Carol's page follows the change, as the local mode follows a changed file.
- **Then** Carol sees the title "Heart Failure Update 2027".
- **And** Her screen still has no editing control.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-039: A RW member edits a presentation uploaded by someone else

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-006
- **Requirements:** FR-NEW-024, FR-NEW-026
- **Given** The administrator uploaded "Arrhythmia Basics" into "Cardiology 2027".
- **When** dan.rw@example.org changes the title of slide 1 and leaves the field.
- **Then** The change is stored.
- **And** The previous version is in the history of "Arrhythmia Basics".
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-041: A RW member edits and the change is stored by itself

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-007, FR-NEW-025, FR-NEW-026, FR-NEW-051, FR-NEW-066
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; "Heart Failure Update" has the title "Heart Failure Update" on slide 1.
- **When** He turns edit mode on, changes the title to "Heart Failure Update 2027" and leaves the field.
- **Then** No notice is shown and the editor offers no Save control. Carol opening the presentation sees "Heart Failure Update 2027".
- **And** The history of the presentation lists the previous version with the title "Heart Failure Update".
- **And** The administrator's activity list has no line for this stored change.
- **And** No session message was shown: the session was still valid.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-043: A change cannot be written

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026
- **Given** dan.rw@example.org edited the title of slide 1; the library has no space left.
- **When** He leaves the edited field.
- **Then** The editor's usual save failure notice is shown with the reason; his change stays on screen.
- **And** carol.ro@example.org opening the presentation sees the old title; the file is not truncated.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-044: Leaving a field stores the change at once

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026, FR-NEW-051, FR-NEW-066
- **Given** dan.rw@example.org has changed the text of slide 2 of "Statins Review" to "First line therapy" and is still in the field.
- **When** He clicks outside the field.
- **Then** The text is stored at once, without waiting for 0.8 seconds of silence.
- **And** carol.ro@example.org reloading sees "First line therapy".
- **And** The administrator's activity list has no line for it.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-046: Accents, Chinese characters and emoji survive a stored change

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026, FR-NEW-053
- **Given** dan.rw@example.org edits "Statins Review".
- **When** He types "Cœur, insuffisance 心臓 😀" in the title of slide 1, leaves the field, then reloads.
- **Then** The title reads "Cœur, insuffisance 心臓 😀" exactly.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-047: A change above the 50 MB limit is refused like in the local mode

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org inserted pictures that make "Statins Review" 60 MB.
- **When** He leaves the edited field.
- **Then** The editor's usual save failure notice is shown with the reason; his changes stay on screen.
- **And** "Statins Review" still opens as the stored version of 1 572 864 bytes.
- **And** A change of 52 428 800 bytes is accepted, 52 428 801 refused, as in the local mode.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-048: Two people editing one after the other meet no conflict

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-024, FR-NEW-026, FR-NEW-027
- **Given** dan.rw@example.org saved "Statins Review" with the title "Statins 2027"; the administrator opens the presentation afterwards.
- **When** The administrator changes the title to "Statins 2028" and leaves the field.
- **Then** The change is stored with no notice.
- **And** Both previous versions are in the history.
- **And** In another run Dan, who has typed nothing, has "Statins Review" open while the administrator's change is stored: within 2 seconds Dan's screen shows "Statins 2028" with no notice.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-049: Leaving a field after someone else's stored change shows the conflict notice

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** failure (side effect, state transition)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-026, FR-NEW-027
- **Given** dan.rw@example.org and seb.morand@gmail.com both have "Statins Review" open; Dan has typed the title "Statins B" and has not left its field; the administrator changes the title to "Statins A" and leaves his field, so "Statins A" is stored.
- **When** Dan leaves his field.
- **Then** The notice "The file changed on disk. Reload to see the changes, or keep your version." is shown with "Keep mine" and "Reload".
- **And** carol.ro@example.org opening the presentation sees "Statins A": Dan's change is not stored.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-050: Keep mine stores the person's version and keeps the other in history

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** failure (side effect, state transition)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-026, FR-NEW-027
- **Given** The conflict of the previous kind: dan.rw@example.org typed "Statins B", the administrator stored "Statins A" meanwhile, Dan left his field and the conflict notice is on his screen.
- **When** He chooses "Keep mine".
- **Then** His title "Statins B" is stored.
- **And** The history lists the version with the title "Statins A".
- **And** carol.ro@example.org sees "Statins B".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-051: Reload shows the stored version and drops the unsaved change

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** edge (state transition)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-027
- **Given** The same conflict notice is on the screen of dan.rw@example.org; his unsaved title is "Statins B" and the stored title is "Statins A".
- **When** He chooses "Reload".
- **Then** The editor shows the stored title "Statins A".
- **And** His text "Statins B" is nowhere in the stored presentation or its history.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-124: Two folders each hold a "Statins Review"

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_edit_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-018
- **Requirements:** FR-NEW-020, FR-NEW-021, FR-NEW-033
- **Given** "Cardiology 2027" and "Pneumo Été" each hold a "Statins Review" with different content; dan.rw@example.org is RW in both.
- **When** He opens each in turn.
- **Then** Each opens its own folder's content; saving one leaves the other unchanged.
- **And** The administrator sees two distinct presentations.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-141: Saves are not recorded

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_edit_http.py`
- **Category:** failure
- **Scenario:** SC-022
- **Requirements:** FR-NEW-026, FR-NEW-051
- **Given** dan.rw@example.org changes the title of "Statins Review" 3 times, leaving the field each time.
- **When** The administrator opens the activity list.
- **Then** The list has no line about these stored changes.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-151: A change is stored 0.8 seconds after typing stops

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-024, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org has "Heart Failure Update" open in edit mode, carol.ro@example.org has it open in view.
- **When** Dan types "Heart Failure Update 2027" as the title of slide 1, stays in the field and waits 1 second.
- **Then** The change is stored: Carol, reloading, sees "Heart Failure Update 2027".
- **And** The editor shows no Save control and no notice; the history holds the previous version titled "Heart Failure Update".
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-152: A change that cannot be stored shows the notice and is kept on screen

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** failure (side effect, state transition)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-017, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org is editing "Heart Failure Update"; at this moment the stored library cannot be written.
- **When** He types "Heart Failure Update 2027" and waits 1 second.
- **Then** The editor shows its usual failure notice with the reason; the typed title stays on screen.
- **And** Carol, reloading, still sees "Heart Failure Update".
- **And** When the library can be written again, Dan types "!" and waits 1 second: the title "Heart Failure Update 2027!" is stored, the notice disappears.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-153: Typing without a pause of 0.8 seconds is stored once at the end

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org is editing "Statins Review".
- **When** He types 40 characters over 5 seconds, never pausing more than 0.5 seconds, and then stops.
- **Then** While he types, a reload by carol.ro@example.org still shows the old text; 1 second after he stops, the whole text is stored.
- **And** The history of "Statins Review" gains exactly one version.
- **And** In another run he leaves the field 0.2 seconds after typing: the text is stored at once.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-189: Two people leaving their fields in the same second leave one stored version

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_edit_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-026, FR-NEW-027
- **Given** dan.rw@example.org and seb.morand@gmail.com have typed "Statins B" and "Statins A" in the title of "Statins Review" and are about to leave their fields.
- **When** Both leave their fields within the same second.
- **Then** One title is stored; the other person is shown the conflict notice.
- **And** The stored title is exactly one of "Statins A" or "Statins B", never a mix, and the history holds the earlier version.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-008: A RO member stores a change by hand

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_edit_http.py`
- **Category:** security
- **Covers:** Class B occurrences #1 and #6
- **Red before the fix because:** the change is stored; the assertion "the title seen by dan.rw@example.org is Heart Failure Update" fails and shows HACKED.
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-026
- **Given** carol.ro@example.org is signed in and RO in "Cardiology 2027"; with her own signed in session, from a command line tool outside the editor, she sends the request the editor sends when it stores a change to "Heart Failure Update" in "Cardiology 2027", the full text of the presentation having the title of slide 1 replaced by "HACKED".
- **When** She sends that request.
- **Then** "Access denied." is returned and nothing is saved.
- **And** dan.rw@example.org opens "Heart Failure Update" and sees the title "Heart Failure Update"; its size is still 2 097 152 bytes.
- **And** The history lists no new version.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

`tests/test_library_edit_http.py` also holds the boundary test of the 50 MiB limit: 52 428 800 bytes accepted, 52 428 801 refused with 413 (as in the local mode).

## Constraints

- Reuse `_receive_content`; do not copy the save pipeline.
- No change to `check_conflict`, `write_save`, `atomic_write`.
- Scope boundary: the editor notices for ended sessions or removed rights (US-0137), requests (US-0138).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (save path, locks), `.agent_docs/testing.md`.
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0136: Edit a presentation and store changes by themselves` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
