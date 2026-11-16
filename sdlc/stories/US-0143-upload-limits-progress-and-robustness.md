# US-0143: Upload limits, progress, interruption and storage failure

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0142
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

Uploads obey the 25 MB limit by declared length before any byte is read, bound a lying or missing length, show a growing percentage (a whole number rounded down, never 100 before the end), leave nothing when the connection is cut or the disk is full, re check the right when the body has arrived, and keep the library responsive to others.

## Requirements covered

- SPEC-0025/FR-NEW-030: IF the chosen file is larger than 26 214 400 bytes (25 MB) THEN THE web library mode SHALL show "The file is larger than 25 MB." and store nothing.
  - Business rules: Exactly 26 214 400 bytes is accepted, 26 214 401 bytes is refused.
- SPEC-0025/FR-NEW-035: WHILE a file is being sent THE web library mode SHALL show the file name and the progress of the upload.
  - Business rules: The progress text is "<file name> <percent>%", for example "Big Deck.html 42%", where the percent is a whole number rounded down; it grows until the upload ends and never reads 100% before the upload is complete.
- SPEC-0025/FR-NEW-036: IF an upload is interrupted before it completes THEN THE web library mode SHALL leave no partial presentation and leave every existing presentation as it was.
  - Business rules: Interruptions: connection lost, page closed or refreshed, browser closed.
- SPEC-0025/FR-NEW-038: IF the library cannot store an uploaded file THEN THE web library mode SHALL show "The upload failed. Nothing was changed." and change nothing.
  - Business rules: Example causes: storage full.
- SPEC-0025/FR-NEW-061: WHEN a person uploads a valid file of 25 MB THE web library mode SHALL complete the upload within 2 minutes on a 10 megabit per second connection and finish with "Uploaded <name>."
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-037 (partial: a second submission made while the first is in progress is ignored by the page): WHEN the same upload is submitted twice in a row THE web library mode SHALL create one presentation.
  - Business rules: A second submission made while the first is still in progress is ignored. Two people uploading the same new name at the same moment leave one presentation, never two: the upload that finishes second is treated as a name collision and meets the question of FR-NEW-033.
- SPEC-0025/FR-NEW-063 (partial: an interrupted or failed upload leaves no partial presentation): The web library mode SHALL show a person, at any instant, either the complete previous or the complete new version of a presentation that is being saved or replaced, never a mix and never an empty file.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-067 (partial: the progress text `<file name> <percent>%`): The web library mode SHALL name the controls and prompts it adds exactly as listed in the business rules.
  - Business rules: Folder page: "All folders" (back to the home page). Administration: sections "Folders" and "Activity"; the field "Folder name" with the button "Create folder"; per folder the button "Delete folder". Deleting a folder: the prompt "Type the folder name to confirm." with the buttons "Delete folder" and "Cancel". Per folder a section "Members": the field "Email address", the chooser "Role" offering "Read and write" and "Read only", the button "Add member"; per member a role chooser and the button "Remove". Upload progress text: "<file name> <percent>%", percent a whole number rounded down. The administration page shows "All folders" and "Sign out". Administration order: folders as on the home page (FR-NEW-015); the members of a folder alphabetical by email address, by character code.

## Independent Test

Run `make test ARGS='-k "library_limits"'` and, for the slow bound, `make test ARGS='-m slow -k library_limits_slow'`. The assertion that is not a mock: a socket that declares 100 bytes and then sends 31 457 280 makes the server read exactly 100 bytes (a counter around `rfile`), answer `This file is not a valid presentation: the file is not declared as a presentation.` and close the connection; a 26 214 401 byte body gets `The file is larger than 25 MB.` and `free space of library_dir` is unchanged.

## Design excerpt

### Decisions

- DEC-019 (SPEC-0025): Checks run in this order for a state changing API request: `Origin` (DEC-022), session, permission of the route (administrator first), then payload validation (role value, address, name). Obliged by: SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-012, SPEC-0025/FR-NEW-014.
- DEC-032 (SPEC-0025): Time and faults are injected, not patched globally: `LibraryServer(clock=time.time)` hands the clock to every repository; the test seams are `Database.connect` (raise `sqlite3.OperationalError` to simulate an unreadable library), `fileio.replace_file` (`fileio.py:44-46`, already the documented failure seam, raise `OSError(errno.ENOSPC)`), and a socket wrapper in tests that cuts a connection at a byte count. Obliged by: SPEC-0025/FR-NEW-005, SPEC-0025/FR-NEW-006, SPEC-0025/FR-NEW-017, SPEC-0025/FR-NEW-038.
- DEC-033 (SPEC-0025): The upload is `POST /api/folders/<fid>/presentations` with the raw body, `X-File-Name` (percent encoded UTF-8) and `Content-Length`; checks run in the order right, extension, name, size (declared length against 26 214 400), then the body is read as exactly the declared count (at most 26 214 400) and checked for validity, then the collision; a `Transfer-Encoding: chunked` body is accepted on this route only and decoded with a hard stop at 26 214 401 bytes; extra bytes beyond the declared length are never read; an answer given before the body was read (refusal, oversize) is followed by `shutdown(SHUT_WR)`, a bounded discard of at most 1 MiB or 2 seconds of the client's input with `socket.recv` (not through `rfile`, so the byte counter of the hostile length test stays at the declared length) and then the close, because closing a socket that still holds unread input sends a TCP reset that can destroy the answer before the client reads it (the server is HTTP/1.0 and closes after each answer); at most 4 uploads are received at once (a fifth gets `503` with `The upload failed. Nothing was changed.`). Obliged by: SPEC-0025/FR-NEW-028, SPEC-0025/FR-NEW-029, SPEC-0025/FR-NEW-030, SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038.
- DEC-054 (SPEC-0025): A failed or interrupted upload leaves nothing: the bytes are held in memory until the checks pass, written by `atomic_write` (temporary file in the target directory, `os.replace`), and the row is inserted in a short transaction after the file exists (DEC-027); any exception removes the temporary file and the new file, and the answer is `The upload failed. Nothing was changed.` for storage errors. Obliged by: SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038, SPEC-0025/FR-NEW-063.
- DEC-055 (SPEC-0025): Every page, message and control the mode adds is an English constant in `library/pages.py` (the exact texts are the ones quoted in the requirements and tests of each story); `static/editor-library.js` adds only `Access denied.` and `Your session has expired. Sign in again to save.`; the editor's own labels, notices and the presentations keep their texts, French ones included. Obliged by: SPEC-0025/FR-NEW-065.

### Data model

No change.

### Contracts

**Declared length** (`uploads.read_upload_body(handler, limit=26_214_400)`): `Content-Length` must be ASCII digits (else `400 {"ok": false, "error": "The upload failed. Nothing was changed."}`); a value above 26 214 400 answers `413 {"ok": false, "error": "The file is larger than 25 MB."}` after the right, extension and name checks and before reading any byte, sets `handler.close_connection = True`; otherwise exactly that many bytes are read with `rfile.read` (a short read or a reset is a lost connection: nothing is written, no answer is needed). Bytes beyond the declared length are never read through `rfile`. Early answer protocol (an answer sent while the client is still sending, or with declared bytes unread): write the full response, then `connection.shutdown(socket.SHUT_WR)`, then discard at most 1 MiB or 2 seconds of the client's input with `connection.recv(65536)` calls, then close; closing at once would reset the TCP connection and could destroy the answer before the client reads it (the server answers HTTP/1.0 and closes after each answer). The page pre checks the extension and `file.size > 26 214 400` before sending anything, so a browser rarely reaches this path; the test helpers (`tests/library_support.py`) read the response in a thread while sending and treat a reset after a complete response as normal.

**Chunked** (`Transfer-Encoding: chunked`): the gate (`_refuse_ambiguous_headers`, `http_server.py:215-238`) refuses any `Transfer-Encoding`; `LibraryHandler` overrides it so the refusal is skipped only for `POST /api/folders/<fid>/presentations` when the value is exactly `chunked`; `uploads.read_chunked(rfile, limit=26_214_400)` decodes chunks, refuses a chunk size line above 32 bytes and trailers above 8 KiB, and stops at 26 214 401 bytes with the same `413` answer under the early answer protocol. The override of `_refuse_ambiguous_headers` also refuses `Transfer-Encoding` together with `Content-Length` and any value other than exactly `chunked` (400, as the inherited gate). nginx always forwards `Content-Length` (request buffering is on), so the chunked path is reachable only by tests and direct clients, which is what E2E-SEC-025 needs. No `Content-Length` and no `Transfer-Encoding` is a zero length body.

**Concurrency and failure**: `LibraryServer.upload_slots = threading.BoundedSemaphore(4)`, acquired without blocking before the body is read, released in `finally`; a fifth concurrent upload gets `503 {"ok": false, "error": "The upload failed. Nothing was changed."}`. A `WriteError` or `OSError` from `atomic_write` (the `fileio.replace_file` seam, `fileio.py:44-46`) gives `500 {"ok": false, "error": "The upload failed. Nothing was changed."}`, no row, no file, no activity line. After the body is read and before the write the right is checked again (`Library.role_in` then `authorize(role, EDIT)`): a person removed or lowered meanwhile gets `403` `Access denied.` and nothing is stored.

**Progress UI** (`static/library.js`): `XMLHttpRequest` with `upload.onprogress` writing `<file name> <percent>%` into the `role="status"` area built by a pure function `progressText(name, loaded, total)` exposed on `window` that returns `<name> <percent>%` with `percent = Math.min(99, Math.floor(100 * loaded / total))`, so the browser test checks `progressText('Big Deck.html', 8880000, 26214400) == 'Big Deck.html 33%'` and `progressText('Big Deck.html', 26214000, 26214400) == 'Big Deck.html 99%'` through `page.evaluate`; the `load` event shows the server message; `error` and `abort` show `The upload failed. Nothing was changed.`; while a request is in flight the button is disabled and a second click is ignored.

**Test seams** (`tests/library_support.py`): `CutSocket(port, cut_at)` sends a request and closes the socket after `cut_at` body bytes; `ThrottledSocket(port, bytes_per_second)`; `disk_full()` context manager patching `fileio.replace_file` to raise `OSError(errno.ENOSPC, ...)`; `pause_at(percent)` for E2E-120 holds the sender at a byte count with an event.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/uploads.py` | modify | `read_upload_body`, `read_chunked`, slots |
| `src/mcp_htmleditor/library/routes_library.py` | modify | re check of the right, answers |
| `src/mcp_htmleditor/library/server.py` | modify | chunked exception, `upload_slots` |
| `src/mcp_htmleditor/static/library.js` | modify | progress, double submit |
| `tests/library_support.py` | modify | cut, throttle, pause, disk full helpers |
| `tests/test_library_limits_http.py` | create | functional tests and E2E-SEC-006, 007, 025 (`test_exploit_*`) |
| `tests/test_library_limits_e2e.py` | create | browser tests |
| `tests/test_library_limits_slow.py` | create | E2E-076 (slow marker) |

### Existing patterns

`tests/test_http_time_bounds_slow.py` for a `slow` test; `tests/http_support.py:33-60` (`exchange`) for raw requests; `tests/stdio_support.py` and `tests/browser_wait.py` for waiting without fixed delays; `http_server.py:615-620` for a declared length refused before reading.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-056: A file one byte over 25 MB is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_limits_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-030, FR-NEW-061
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; "Big Deck.html" is a valid presentation of 26 214 401 bytes.
- **When** He uploads it.
- **Then** "The file is larger than 25 MB." is shown.
- **And** The folder still lists 3 presentations; no "Big Deck" exists.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-062: A file of exactly 25 MB is accepted

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_limits_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-030, FR-NEW-061
- **Given** dan.rw@example.org; "Big Deck.html" is a valid presentation of exactly 26 214 400 bytes.
- **When** He uploads it.
- **Then** "Uploaded Big Deck." is shown; the folder page lists it with the size "25.0 MB".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-071: A 25 MB upload shows progress and completes

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_limits_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-028, FR-NEW-030, FR-NEW-035, FR-NEW-036, FR-NEW-061, FR-NEW-067
- **Given** dan.rw@example.org uploads "Big Deck.html", a valid presentation of 26 214 400 bytes, on a 10 megabit per second connection.
- **When** He starts the upload.
- **Then** The text "Big Deck.html <percent>%" is shown with a whole number growing from 0 (for example "Big Deck.html 37%"); within 2 minutes "Uploaded Big Deck." appears.
- **And** The percentage never goes down and never reads 100% before the upload is complete.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-072: A lost connection leaves no partial presentation

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_limits_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-035, FR-NEW-036, FR-NEW-063
- **Given** dan.rw@example.org uploads "Big Deck.html"; his connection drops at 40 percent.
- **When** The upload stops.
- **Then** No "Big Deck" is listed once the page is reloaded.
- **And** The administrator's view of "Cardiology 2027" lists 3 presentations; the library holds no fragment of "Big Deck".
- **And** The progress stopped at 40 percent and no "Uploaded Big Deck." message appeared.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-074: A library that cannot store the file says so

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_limits_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-038
- **Given** dan.rw@example.org; the library has no space left; "Quarterly Review.html" is valid.
- **When** He uploads it.
- **Then** "The upload failed. Nothing was changed." is shown.
- **And** No "Quarterly Review" is listed; the activity list has no new line.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-075: A double click uploads once

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_limits_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-037, FR-NEW-049
- **Given** dan.rw@example.org; "Quarterly Review.html" is valid.
- **When** He presses Upload twice within half a second.
- **Then** One "Uploaded Quarterly Review." is shown.
- **And** The folder lists one "Quarterly Review".
- **And** The activity list has one upload line.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-076: A slow link still completes within 2 minutes

- Level / Driver / Location: functional e2e / HTTP client + raw socket / `tests/test_library_limits_slow.py`
- **Category:** edge
- **Scenario:** SC-011
- **Requirements:** FR-NEW-035, FR-NEW-061
- **Given** dan.rw@example.org on a link limited to 10 megabits per second uploads a valid file of 26 214 400 bytes.
- **When** He starts the upload and waits.
- **Then** "Uploaded <name>." appears no later than 2 minutes after the start.
- **And** Meanwhile lamya.chrif@gmail.com browses her folder without noticeable delay.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: carries the `slow` marker (about 25 s); it runs with `make test ARGS='-m slow -k library_limits_slow'`, not in `make check`.

### SPEC-0025/E2E-120: A right removed during an upload stops it

- Level / Driver / Location: functional e2e / HTTP client + raw socket / `tests/test_library_limits_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-028, FR-NEW-036, FR-NEW-048
- **Given** dan.rw@example.org is uploading a valid 25 MB "Big Deck.html"; at 50 percent the administrator removes him from "Cardiology 2027".
- **When** The upload ends.
- **Then** "Access denied." is shown.
- **And** No "Big Deck" is listed to the administrator; the activity list has no upload line.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the test needs the seam `pause_at(percent)` of `tests/library_support.py` to hold the sender while the administrator removes the member; the server re checks the right after the body arrived (DEC-033).

### SPEC-0025/E2E-158: The progress percent is a whole number rounded down

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_limits_e2e.py`
- **Category:** edge
- **Scenario:** SC-011
- **Requirements:** FR-NEW-035, FR-NEW-067
- **Given** dan.rw@example.org uploads "Big Deck.html" (26 214 400 bytes) on a slow connection.
- **When** He watches the progress when 8 880 000 bytes (33.87 percent) and when 26 214 000 bytes (99.998 percent) have been sent.
- **Then** The texts read "Big Deck.html 33%" and "Big Deck.html 99%".
- **And** "Big Deck.html 100%" is shown only together with, or after, "Uploaded Big Deck."
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the server cannot be held at an exact byte count from a browser; the test checks the pure function `progressText(name, loaded, total)` of `library.js` for the two byte counts through `page.evaluate`, and drives one real upload to read the final text.

### SPEC-0025/E2E-SEC-006: A RO member sends a 30 MB file

- Level / Driver / Location: exploit / HTTP client + raw socket / `tests/test_library_limits_http.py`
- **Category:** security
- **Covers:** Classes B occurrence #1 and D occurrence #1
- **Red before the fix because:** the whole 30 MB is received and stored; the assertion "the administrator lists 3 presentations" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-030, FR-NEW-060
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; she sends by hand the upload of "Huge.html" of 31 457 280 bytes (30 MB) with her own session.
- **When** She sends it.
- **Then** "Access denied." is returned, without waiting for the whole file to be sent.
- **And** The library stores nothing: the administrator's view lists 3 presentations; the free space of the library is unchanged.
- **And** lamya.chrif@gmail.com browses her folder without delay during the attempt.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-007: A RW member sends a 30 MB file

- Level / Driver / Location: exploit / HTTP client + raw socket / `tests/test_library_limits_http.py`
- **Category:** security
- **Covers:** Class D occurrence #1
- **Red before the fix because:** the 30 MB presentation is stored; the assertion "no Huge listed to the administrator" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-030, FR-NEW-038
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; "Huge.html" is a valid presentation of 31 457 280 bytes (30 MB).
- **When** He uploads it.
- **Then** "The file is larger than 25 MB." is shown.
- **And** The administrator's view lists 3 presentations and no "Huge"; the free space of the library is unchanged.
- **And** lamya.chrif@gmail.com browses her folder without delay during the attempt.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-025: An upload that announces 100 bytes and sends 30 MB

- Level / Driver / Location: exploit / raw socket / `tests/test_library_limits_http.py`
- **Category:** security
- **Covers:** Class D occurrence #1
- **Red before the fix because:** the extra bytes are read and stored; the assertion "only the declared 100 bytes are read and the connection is closed" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-030, FR-NEW-038, FR-NEW-063
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; from a command line tool he sends, with his own session, the upload of "Huge.html" announcing a length of 100 bytes and then sending 31 457 280 bytes (30 MB).
- **When** He sends it.
- **Then** Only the declared 100 bytes are read, the upload is refused with "This file is not a valid presentation: the file is not declared as a presentation." and the connection is closed.
- **And** The administrator's view lists 3 presentations and no "Huge".
- **And** The free space of the library is unchanged and lamya.chrif@gmail.com browses her folder without delay.
- **And** In a second run with no declared length, the sending is cut at 26 214 401 bytes and "The file is larger than 25 MB." is returned.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

## Constraints

- Never read a body before the right is known and the extension and name are checked.
- The 4 slot semaphore is non blocking; do not queue uploads.
- Scope boundary: replacing an existing presentation (US-0144).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (limits, chunked rule), `.agent_docs/testing.md` (the `slow` library test).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0143: Upload limits, progress, interruption and storage failure` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
