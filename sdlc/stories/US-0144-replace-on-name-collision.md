# US-0144: Replace an existing presentation after a collision question

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0143, US-0138
> min_tier: 1
> Files touched: 7
> Closes spec: no

## Objective

Uploading a valid file whose name equals an existing presentation (without regard to case, on the composed form, accents making names different) asks `A presentation named "<name>" already exists. Replace it?` with `Replace` and `Cancel`; `Replace` swaps the content in one step, keeps the previous version in the history, keeps the requests and suggestions, and never leaves a mix; a validation message always wins over the question; two uploads of the same new name leave one presentation.

## Requirements covered

- SPEC-0025/FR-NEW-033: IF a presentation with the same name already exists in the folder and the file passed every other check THEN THE web library mode SHALL ask: A presentation named "<name>" already exists. Replace it?
  - Business rules: Names are compared without regard to case and without the ".html" ending, on their composed form; accents make names different. <name> is the name of the existing presentation. The buttons are "Replace" and "Cancel". A validation message always wins over this question. Choosing "Cancel" changes nothing: not the presentation, not its history, not the list, not the activity list.
- SPEC-0025/FR-NEW-034: WHEN the person confirms "Replace" THE web library mode SHALL replace the presentation by the uploaded file in one step, keep the previous version in its history and show "Uploaded <name>."
  - Business rules: The existing presentation keeps its name. A replacement keeps the requests queued for the presentation and its AI suggestions.
- SPEC-0025/FR-NEW-037: WHEN the same upload is submitted twice in a row THE web library mode SHALL create one presentation.
  - Business rules: A second submission made while the first is still in progress is ignored. Two people uploading the same new name at the same moment leave one presentation, never two: the upload that finishes second is treated as a name collision and meets the question of FR-NEW-033.
- SPEC-0025/FR-NEW-063: The web library mode SHALL show a person, at any instant, either the complete previous or the complete new version of a presentation that is being saved or replaced, never a mix and never an empty file.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-036 (partial: an interrupted replacement leaves the previous version intact): IF an upload is interrupted before it completes THEN THE web library mode SHALL leave no partial presentation and leave every existing presentation as it was.
  - Business rules: Interruptions: connection lost, page closed or refreshed, browser closed.
- SPEC-0025/FR-NEW-038 (partial: a replacement that cannot be stored keeps the previous version and says `The upload failed. Nothing was changed.`): IF the library cannot store an uploaded file THEN THE web library mode SHALL show "The upload failed. Nothing was changed." and change nothing.
  - Business rules: Example causes: storage full.
- SPEC-0025/FR-NEW-049 (partial: the line `Replaced "<name>" in "<folder>"`): WHEN an upload, a replacement or a deletion of a presentation, the creation or deletion of a folder, or the adding, changing or removing of a member succeeds THE web library mode SHALL add a line to the activity list with who did it, when, and what.
  - Business rules: Line texts: Uploaded "<name>" in "<folder>"; Replaced "<name>" in "<folder>"; Deleted "<name>" from "<folder>"; Created folder "<folder>"; Deleted folder "<folder>"; Added <email> as RW to "<folder>" (or RO); Changed <email> to RO in "<folder>" (or RW); Removed <email> from "<folder>". Who is the email address of the person; when is shown as on the folder page. Who is the email address of the person in lower case, whatever letter case Google returned.

## Independent Test

Run `make test ARGS='-k library_replace'`. The assertion that is not a mock: after `Replace` the stored bytes equal the new file, `HistoryStore.list_versions` holds one version equal to the old bytes with reason `replace`, the request record of the presentation is unchanged, and a reader polling the file during the replacement only ever sees complete old or complete new bytes (`sha256` of each sample).

## Design excerpt

### Decisions

- DEC-027 (SPEC-0025): A presentation row is unique on (`folder_id`, `name_key`). A new presentation: the bytes are first written to `files/<fid>/<new id>.html` with `atomic_write` (outside any transaction, so the slow write never holds the database), then `BEGIN IMMEDIATE` checks the key and inserts the row and the activity line; if the key exists the transaction rolls back, the unused file is removed and the outcome is `collision` (the existing name is returned for the question); a unique violation is treated the same. A replacement: under the presentation lock, `SELECT` the row, `atomic_write(..., reason="replace")`, then a short transaction for the activity line. Lock order is always the presentation lock first, then the database transaction; a save holds only the presentation lock and reads the database. Obliged by: SPEC-0025/FR-NEW-033, SPEC-0025/FR-NEW-037, SPEC-0025/FR-NEW-034.
- DEC-028 (SPEC-0025): One `threading.Lock` per presentation id, held by `_save_lock()`, by an upload replacement and by a deletion; `_save_lock()` returns a context manager that acquires the lock and then re-checks that the presentation row still exists, raising `SaveRefusal(403, {"error": "Access denied.", "code": "denied"})` when it does not, so a save that lost the race with a deletion creates nothing; the conflict check (`check_conflict`) runs inside it. Obliged by: SPEC-0025/FR-NEW-027, SPEC-0025/FR-NEW-063.
- DEC-033 (SPEC-0025): The upload is `POST /api/folders/<fid>/presentations` with the raw body, `X-File-Name` (percent encoded UTF-8) and `Content-Length`; checks run in the order right, extension, name, size (declared length against 26 214 400), then the body is read as exactly the declared count (at most 26 214 400) and checked for validity, then the collision; a `Transfer-Encoding: chunked` body is accepted on this route only and decoded with a hard stop at 26 214 401 bytes; extra bytes beyond the declared length are never read; an answer given before the body was read (refusal, oversize) is followed by `shutdown(SHUT_WR)`, a bounded discard of at most 1 MiB or 2 seconds of the client's input with `socket.recv` (not through `rfile`, so the byte counter of the hostile length test stays at the declared length) and then the close, because closing a socket that still holds unread input sends a TCP reset that can destroy the answer before the client reads it (the server is HTTP/1.0 and closes after each answer); at most 4 uploads are received at once (a fifth gets `503` with `The upload failed. Nothing was changed.`). Obliged by: SPEC-0025/FR-NEW-028, SPEC-0025/FR-NEW-029, SPEC-0025/FR-NEW-030, SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038.
- DEC-035 (SPEC-0025): "Replace" repeats the whole upload with the header `X-Replace: 1`; the server runs every check again and replaces under DEC-027 and DEC-028 with `atomic_write(..., reason="replace")` (previous bytes kept in history), keeping the presentation's name, id, requests and suggestions. Obliged by: SPEC-0025/FR-NEW-033, SPEC-0025/FR-NEW-034.
- DEC-054 (SPEC-0025): A failed or interrupted upload leaves nothing: the bytes are held in memory until the checks pass, written by `atomic_write` (temporary file in the target directory, `os.replace`), and the row is inserted in a short transaction after the file exists (DEC-027); any exception removes the temporary file and the new file, and the answer is `The upload failed. Nothing was changed.` for storage errors. Obliged by: SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038, SPEC-0025/FR-NEW-063.

### Data model

No change. The presentation keeps its id, its name and its row; only the file content and `st_mtime` change.

### Contracts

**Flow**: the first upload of a name whose `name_key` exists answers `409 {"ok": false, "collision": "<existing name>"}` after every other check passed (validation first, DEC-033) and stores nothing. The page shows a `<dialog>` with `A presentation named "<existing name>" already exists. Replace it?` (the name written with `textContent`) and the buttons `Replace` and `Cancel`; `Cancel` closes it and changes nothing (not the list, history, activity); `Replace` re sends the same file with `X-Replace: 1` (the bytes are re sent, DEC-035).

**Server** (`Library.add_presentation(..., replace=True)`, `uploads.py`): `SELECT` the row by (`folder_id`, `name_key`); if the key does not exist any more the file is added as new (US-0141 path); otherwise under `LibraryServer.lock_for(pid)` (lock order: presentation lock, then database, DEC-027): `atomic_write(path, data, reason="replace")` (`fileio.py:49-67`: temporary file in the same directory, `fsync`, `os.replace`, the previous bytes staged to the history first and kept only on success); the existing name stays; activity line `Replaced "<name>" in "<folder>"` written in a short transaction after the write, only when `atomic_write` returned `True` (a second identical `Replace` returns `False`: no new history version, no second line, still `Uploaded <name>.`). Requests and suggestions are untouched (they live beside the history). On failure the previous file and history are intact (`atomic_write` guarantees it, `fileio.py:86-92`). Wrapped in `trace_span("library.replace", {"file.size": len(data)})`.

**Concurrency**: two uploads of the same new name: both write their own new file, the second `BEGIN IMMEDIATE` sees the row, removes its file and answers the collision (E2E-070); a replacement while a person edits makes the person's next save meet `check_conflict` (the `st_mtime` changed) and show the conflict notice (E2E-052).

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/uploads.py` | modify | collision and replace outcomes |
| `src/mcp_htmleditor/library/store.py` | modify | `add_presentation(replace=True)` |
| `src/mcp_htmleditor/library/routes_library.py` | modify | `X-Replace` header, `409` answer |
| `src/mcp_htmleditor/library/pages.py` | modify | collision dialog |
| `src/mcp_htmleditor/static/library.js` | modify | dialog, re send |
| `tests/test_library_replace_http.py` | create | functional tests |
| `tests/test_library_replace_e2e.py` | create | browser tests |

### Existing patterns

`tests/test_history_e2e.py` and `tests/test_history_tools.py` for history assertions; `tests/test_save_safety_e2e.py` for the conflict notice; `tests/test_requests_core.py` for building request records.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-052: An upload replacement during an edit triggers the notice

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_replace_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-027, FR-NEW-034
- **Given** dan.rw@example.org has typed "Statins C" in the title of slide 2 of "Statins Review" and has not left the field; the administrator uploads a valid "Statins Review.html" and confirms "Replace".
- **When** Dan leaves the field.
- **Then** The conflict notice is shown; nothing is stored until he chooses.
- **And** The replaced content is the one carol.ro@example.org sees.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-066: A same name upload asks, and Replace replaces

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_replace_e2e.py`
- **Category:** happy (side effect, state transition)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-033, FR-NEW-034, FR-NEW-049, FR-NEW-063
- **Given** dan.rw@example.org; "Statins Review" (1 572 864 bytes) exists in "Cardiology 2027"; he holds "statins review.HTML", a valid presentation of 2 slides, 307 200 bytes.
- **When** He uploads it and, on the question, chooses "Replace".
- **Then** The question A presentation named "Statins Review" already exists. Replace it? is shown first; then "Uploaded Statins Review." and the row "Statins Review" shows 300.0 KB.
- **And** The history of "Statins Review" lists the previous version of 1 572 864 bytes.
- **And** The folder still lists 3 presentations; the name keeps its capital letters.
- **And** The activity list gains one line "Replaced "Statins Review" in "Cardiology 2027"".
- **And** "Cancel" was offered next to "Replace".
- **And** A request queued on "Statins Review" before the replacement is still in its Requests list afterwards.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-067: Cancel changes nothing

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_replace_e2e.py`
- **Category:** failure (side effect, state transition)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-033, FR-NEW-051
- **Given** dan.rw@example.org uploaded a valid "statins review.HTML" of 307 200 bytes and the question A presentation named "Statins Review" already exists. Replace it? is shown to him; "Statins Review" is 1 572 864 bytes.
- **When** He chooses "Cancel".
- **Then** The folder page is shown again; "Statins Review" still has 1.5 MB.
- **And** The history has no new version.
- **And** The activity list has no new line.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-068: A validation message wins over the question

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_replace_http.py`
- **Category:** failure
- **Scenario:** SC-010
- **Requirements:** FR-NEW-031, FR-NEW-033
- **Given** dan.rw@example.org; "Statins Review.html" is declared as a presentation and has 0 slides.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file has no slide." is shown and no question is asked.
- **And** "Statins Review" is unchanged, 1.5 MB.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-069: Names that differ by an accent are different

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_replace_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-028, FR-NEW-033
- **Given** dan.rw@example.org uploaded a valid "Cafe Study.html" into "Cardiology 2027".
- **When** He uploads a valid "Café Study.html".
- **Then** No question is asked; "Uploaded Café Study." is shown.
- **And** The folder lists "Cafe Study" and "Café Study" as two presentations.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-070: Two uploads of the same new name leave one presentation

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_replace_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-033, FR-NEW-037, FR-NEW-063
- **Given** dan.rw@example.org and seb.morand@gmail.com each upload a valid "Lipids Update.html" to "Cardiology 2027" at the same moment; no such presentation exists.
- **When** Both submit within the same second.
- **Then** One upload ends with "Uploaded Lipids Update."; the other, which finishes second, is treated as a name collision and shows A presentation named "Lipids Update" already exists. Replace it?
- **And** Whatever the second person chooses, the folder lists exactly one "Lipids Update" and it opens as a complete presentation.
- **And** If the second person chooses "Cancel", the first upload's content is the one that opens.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-073: An interrupted replacement keeps the previous version

- Level / Driver / Location: functional e2e / HTTP client + raw socket / `tests/test_library_replace_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-034, FR-NEW-036, FR-NEW-063
- **Given** dan.rw@example.org replaces "Statins Review" and confirms "Replace"; his connection drops at 70 percent.
- **When** The upload stops.
- **Then** "Statins Review" opens as the complete previous version of 1 572 864 bytes.
- **And** The history has no new version and the activity list no new line.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-077: Confirming Replace twice replaces once

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_replace_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-034, FR-NEW-037, FR-NEW-049
- **Given** dan.rw@example.org uploaded a valid "Statins Review.html" and the question A presentation named "Statins Review" already exists. Replace it? is shown.
- **When** He presses "Replace" twice within half a second.
- **Then** One "Uploaded Statins Review." is shown.
- **And** The history of "Statins Review" gains one version, the 1 572 864 byte one; the activity list gains one "Replaced" line.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-078: A replacement that cannot be stored keeps the previous version

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_replace_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-034, FR-NEW-038, FR-NEW-063
- **Given** dan.rw@example.org confirms "Replace" on "Statins Review"; the library has no space left.
- **When** The upload ends.
- **Then** "The upload failed. Nothing was changed." is shown.
- **And** "Statins Review" opens as the complete previous version of 1 572 864 bytes; its history and the activity list are unchanged.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-162: File names: composed form, 100 characters, edge spaces

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_replace_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-032, FR-NEW-033
- **Given** dan.rw@example.org; "Café Study" (the é as one letter) exists in "Cardiology 2027"; valid files exist named with the e followed by an accent mark ("Café Study.html"), with 100 letters "A" before ".html", with 101, " Lead.html" (space first), "Tail .html" (space before the dot) and "   .html" (only spaces).
- **When** He uploads each in turn.
- **Then** The first meets the question A presentation named "Café Study" already exists. Replace it?; the 100 letter name is accepted ("Uploaded <name>."); the 101 letter name, " Lead.html", "Tail .html" and "   .html" each show "This file name is not allowed."
- **And** The folder holds one "Café Study" and the 100 letter presentation, nothing else added.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

## Constraints

- Replacement is `atomic_write` with a reason; no delete then create.
- The existing presentation keeps its name and id; a replacement never renames it.
- Scope boundary: deleting (US-0145).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (collision and replace).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0144: Replace an existing presentation after a collision question` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
