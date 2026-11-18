# US-0141: Upload a valid presentation into a folder

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0137
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

A person with RW (or the administrator) chooses `Upload` on the folder page and picks a `.html` file; the server checks right, extension, name, size, then validity as a presentation with the editor's own checks, stores it, shows `Uploaded <name>.` and lists it first, and records the action. Only valid presentations are stored; the first problem is shown without any location.

## Requirements covered

- SPEC-0025/FR-NEW-028: WHEN a person with RW uploads a file that passes every upload check THE web library mode SHALL add it to the folder as a presentation and show "Uploaded <name>."
  - Business rules: <name> is the file name without ".html". The new presentation is listed first, with the current date and time. Checks run in this order and the first failure is the only message: right to upload, extension, file name, size, validity as a presentation, name collision.
- SPEC-0025/FR-NEW-029: IF the chosen file name does not end with ".html", whatever the case of the letters, THEN THE web library mode SHALL show "Only .html files are accepted." and store nothing.
  - Business rules: ".HTML" and ".Html" are accepted.
- SPEC-0025/FR-NEW-031: IF the chosen file is not a valid presentation THEN THE web library mode SHALL show "This file is not a valid presentation: <first problem>." and store nothing.
  - Business rules: Valid means: valid UTF-8 text, declared as a presentation, at least 1 slide, and no error of any kind reported by the editor's own checks (its structure rules and its charter rules). Warnings of those checks (for example a picture loaded from another site) never block and are never the first problem. <first problem> is the first error in the order the editor lists its findings (whole file first, then slide by slide, then by check code), its message only, without the slide identifier. Verbatim editor examples: "missing attribute data-title"; "TOTAL is 5 but the file has 2 slides"; "expected id \"slide-0\" but found \"a\""; "slide has an image and no source line". A file that is not valid UTF-8 text reads "the file is not valid UTF-8 text" (checked first); an empty file, or a file that is not declared as a presentation, reads "the file is not declared as a presentation"; a declared presentation without slide reads "the file has no slide". No message carries a location: no byte position, line number or server path.
- SPEC-0025/FR-NEW-023 (partial: a RO person or a person with no role posting an upload by hand gets `Access denied.`; no byte of the body is read): The web library mode SHALL NOT let a person who holds only RO in a folder edit, upload or delete in it: the controls are absent and any attempt made outside the interface, including the storing of a change, is refused with "Access denied." and has no effect.
  - Business rules: Absent for RO: the Upload and Delete controls, edit mode, undo, redo, notes editing, requests, slide and block actions. The key E does nothing. Reading the queued requests and the AI suggestions of a presentation is refused with "Access denied." for a person who holds only RO.
- SPEC-0025/FR-NEW-024 (partial: a RW member or the administrator sees the `Upload` control and uploads): WHILE a person holds RW in a folder, or is Admin, THE web library mode SHALL additionally let them edit its presentations with every editor option (changes are stored by themselves), upload and delete in that folder.
  - Business rules: The Upload control is on the folder page; Delete is on each presentation row. Any RW member can change, replace or delete any presentation of the folder, whoever uploaded it.
- SPEC-0025/FR-NEW-049 (partial: the line `Uploaded "<name>" in "<folder>"`): WHEN an upload, a replacement or a deletion of a presentation, the creation or deletion of a folder, or the adding, changing or removing of a member succeeds THE web library mode SHALL add a line to the activity list with who did it, when, and what.
  - Business rules: Line texts: Uploaded "<name>" in "<folder>"; Replaced "<name>" in "<folder>"; Deleted "<name>" from "<folder>"; Created folder "<folder>"; Deleted folder "<folder>"; Added <email> as RW to "<folder>" (or RO); Changed <email> to RO in "<folder>" (or RW); Removed <email> from "<folder>". Who is the email address of the person; when is shown as on the folder page. Who is the email address of the person in lower case, whatever letter case Google returned.
- SPEC-0025/FR-NEW-067 (partial: the `Upload` control name): The web library mode SHALL name the controls and prompts it adds exactly as listed in the business rules.
  - Business rules: Folder page: "All folders" (back to the home page). Administration: sections "Folders" and "Activity"; the field "Folder name" with the button "Create folder"; per folder the button "Delete folder". Deleting a folder: the prompt "Type the folder name to confirm." with the buttons "Delete folder" and "Cancel". Per folder a section "Members": the field "Email address", the chooser "Role" offering "Read and write" and "Read only", the button "Add member"; per member a role chooser and the button "Remove". Upload progress text: "<file name> <percent>%", percent a whole number rounded down. The administration page shows "All folders" and "Sign out". Administration order: folders as on the home page (FR-NEW-015); the members of a folder alphabetical by email address, by character code.

## Independent Test

Run `make test ARGS='-k library_upload'`. The assertion that is not a mock: after uploading the `Quarterly Review` fixture, `StoredLibrary.entries()` holds one new file `files/<fid>/<32 hex>.html` equal to the uploaded bytes and the `activity` table holds the line `Uploaded "Quarterly Review" in "Cardiology 2027"`; after a refusal both are unchanged.

## Design excerpt

### Decisions

- DEC-019 (SPEC-0025): Checks run in this order for a state changing API request: `Origin` (DEC-022), session, permission of the route (administrator first), then payload validation (role value, address, name). Obliged by: SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-012, SPEC-0025/FR-NEW-014.
- DEC-022 (SPEC-0025): Every state changing request (any method other than `GET`, `HEAD` and `OPTIONS`: `POST` and `DELETE`) is refused with `Access denied.`, before the session is looked up, unless `Origin` is present and equals the origin of the receiving host exactly, and `Sec-Fetch-Site`, when present, is `same-origin` (or `none`); JSON routes also require `Content-Type: application/json`, the upload requires the header `X-File-Name`. The local rule that accepts a missing `Origin` is not used. Obliged by: SPEC-0025/FR-NEW-070, SPEC-0025/FR-NEW-023.
- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-025 (SPEC-0025): Metadata in one SQLite file (`<library_dir>/library.db`, WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one connection per thread, `BEGIN IMMEDIATE` for writes, migrations numbered by `PRAGMA user_version`); presentation bytes in files named by two random 32 hex ids (`files/<folder id>/<presentation id>.html`); ids validated against `^[0-9a-f]{32}$` before a path is built; names exist only as column values. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-063, SPEC-0025/FR-NEW-060.
- DEC-027 (SPEC-0025): A presentation row is unique on (`folder_id`, `name_key`). A new presentation: the bytes are first written to `files/<fid>/<new id>.html` with `atomic_write` (outside any transaction, so the slow write never holds the database), then `BEGIN IMMEDIATE` checks the key and inserts the row and the activity line; if the key exists the transaction rolls back, the unused file is removed and the outcome is `collision` (the existing name is returned for the question); a unique violation is treated the same. A replacement: under the presentation lock, `SELECT` the row, `atomic_write(..., reason="replace")`, then a short transaction for the activity line. Lock order is always the presentation lock first, then the database transaction; a save holds only the presentation lock and reads the database. Obliged by: SPEC-0025/FR-NEW-033, SPEC-0025/FR-NEW-037, SPEC-0025/FR-NEW-034.
- DEC-030 (SPEC-0025): Activity is the table `activity`, one row per successful action written in the same transaction as the action, with the final line text and the actor's lower case address; after each insert rows older than the 500 newest are deleted; the page reads `ORDER BY id DESC LIMIT 500`. Refusals, sign ins and stored changes never write. Obliged by: SPEC-0025/FR-NEW-049, SPEC-0025/FR-NEW-050, SPEC-0025/FR-NEW-051.
- DEC-033 (SPEC-0025): The upload is `POST /api/folders/<fid>/presentations` with the raw body, `X-File-Name` (percent encoded UTF-8) and `Content-Length`; checks run in the order right, extension, name, size (declared length against 26 214 400), then the body is read as exactly the declared count (at most 26 214 400) and checked for validity, then the collision; a `Transfer-Encoding: chunked` body is accepted on this route only and decoded with a hard stop at 26 214 401 bytes; extra bytes beyond the declared length are never read; an answer given before the body was read (refusal, oversize) is followed by `shutdown(SHUT_WR)`, a bounded discard of at most 1 MiB or 2 seconds of the client's input with `socket.recv` (not through `rfile`, so the byte counter of the hostile length test stays at the declared length) and then the close, because closing a socket that still holds unread input sends a TCP reset that can destroy the answer before the client reads it (the server is HTTP/1.0 and closes after each answer); at most 4 uploads are received at once (a fifth gets `503` with `The upload failed. Nothing was changed.`). Obliged by: SPEC-0025/FR-NEW-028, SPEC-0025/FR-NEW-029, SPEC-0025/FR-NEW-030, SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038.
- DEC-034 (SPEC-0025): Validity is: decode UTF-8 (failure: `the file is not valid UTF-8 text`); `deck_from_text`; the root `<html data-doc-type="presentation">` must be present, else `the file is not declared as a presentation` (an empty file included); at least one slide, else `the file has no slide`; then the first problem is the first item of `lint_deck(deck)` whose severity is `error`, its `message` only. Obliged by: SPEC-0025/FR-NEW-031.
- DEC-048 (SPEC-0025): Logging and tracing follow the project rules: `logger = logging.getLogger(__name__)`, `%` formatting, stderr console, `click.echo` only for the start line; spans `auth.google_token`, `library.upload`, `library.replace`, `library.delete_presentation`, `library.delete_folder`, `library.seed`, `session.create`, with sizes and status codes only; no email, name, token, cookie or credential in a log line or an attribute. Obliged by: SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-020 (nothing about members leaks), AGENTS.md observability rules.
- DEC-054 (SPEC-0025): A failed or interrupted upload leaves nothing: the bytes are held in memory until the checks pass, written by `atomic_write` (temporary file in the target directory, `os.replace`), and the row is inserted in a short transaction after the file exists (DEC-027); any exception removes the temporary file and the new file, and the answer is `The upload failed. Nothing was changed.` for storage errors. Obliged by: SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038, SPEC-0025/FR-NEW-063.

### Data model

No change.

### Contracts

**Route**: `POST /api/folders/<fid>/presentations` (library origin, `EDIT` on the folder, origin rule; no JSON content type: the custom header `X-File-Name` is the cross site guard). Request: raw body, headers `Content-Length`, `X-File-Name` (percent encoded UTF-8 file name including `.html`), optional `X-Replace: 1` (US-0144). Answers: `201 {"ok": true, "name": "<name>", "message": "Uploaded <name>."}`; `400 {"ok": false, "error": "<exact message>"}`; `403` `Access denied.`.

**Order of checks** (DEC-033): (1) right (`authorize`, before any body byte), (2) extension (`.html` in any letter case else `Only .html files are accepted.`), (3) name (in this story the stem is only passed through `names.compose`; the allow list `names.check_file_name` and `This file name is not allowed.` arrive in US-0142, where the traversal and markup name tests are red before the fix and green after), (4) size (US-0143), (5) validity, (6) collision (US-0144; a duplicate name in this story is refused with `409 {"ok": false, "collision": "<existing name>"}` and nothing is stored).

**Validity** (`library/uploads.py::check_validity(data: bytes) -> None`, raises `UploadRefused(message)`): decode UTF-8 else `This file is not a valid presentation: the file is not valid UTF-8 text.`; `deck_from_text(name, text)` (`deck/__init__.py:61`); root `<html>` must carry `data-doc-type="presentation"` else `...: the file is not declared as a presentation.` (an empty file included); `len(deck.slides) == 0` gives `...: the file has no slide.`; then the first item of `lint_deck(deck)` (`deck/lint.py:51`) with `severity == "error"`: `This file is not a valid presentation: <message>.` using `Problem.message` only (no slide id). Warnings never block and are never first. No message holds a byte position, a line number or a path.

**Store**: `Library.add_presentation(folder_id, name, data, actor, *, replace=False) -> Outcome` (`Added(id, name)` or `Collision(existing_name)`): writes the file first with `atomic_write(presentation_path(fid, new_id), data)` (no history for a new file; outside any transaction, DEC-027), then `BEGIN IMMEDIATE`; looks up `(folder_id, name_key)`; if absent inserts the row and the activity line and commits; if present rolls back, removes the new file and returns `Collision`; any exception removes the new file and rolls back; wrapped in `trace_span("library.upload", {"file.size": len(data)})`.

**Page** (`pages.folder_page`): for RW or Admin an `Upload` control (`<input type="file" accept=".html,text/html">` labelled `Upload` and a button) and a `role="status"` area; `library.js` reads the file, sends it with `XMLHttpRequest` (US-0143 adds progress), shows `message` or `error` with `textContent`, then reloads the list.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/uploads.py` | create | `check_validity`, `UploadRefused`, `read_exact` |
| `src/mcp_htmleditor/library/store.py` | modify | `add_presentation`, `Outcome` |
| `src/mcp_htmleditor/library/routes_library.py` | modify | upload route |
| `src/mcp_htmleditor/library/pages.py` | modify | Upload control |
| `src/mcp_htmleditor/static/library.js` | modify | upload with XHR |
| `tests/library_support.py` | modify | valid and invalid deck generators, `upload()` helper |
| `tests/test_library_upload_http.py` | create | functional tests and E2E-SEC-010 (`test_exploit_*`) |
| `tests/test_library_upload_e2e.py` | create | browser tests |

### Existing patterns

`deck/lint.py:51-67` and `tests/test_deck_lint.py` for generating files with chosen errors and warnings; `deck_support.py` for deck generators; `fileio.py:49-98` for `atomic_write`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-054: A valid presentation is uploaded

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_upload_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-024, FR-NEW-028, FR-NEW-029, FR-NEW-030, FR-NEW-031, FR-NEW-032, FR-NEW-037, FR-NEW-038, FR-NEW-049
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the file "Quarterly Review.HTML" is a valid presentation of 3 slides, 1 258 291 bytes.
- **When** He chooses Upload and picks the file.
- **Then** "Uploaded Quarterly Review." is shown; the folder page lists "Quarterly Review" first, with the current date and time and the size "1.2 MB".
- **And** carol.ro@example.org opens "Quarterly Review" and sees its 3 slides.
- **And** The administrator's activity list gains the line "Uploaded "Quarterly Review" in "Cardiology 2027"" attributed to dan.rw@example.org.
- **And** A single Upload action produced one presentation and one activity line; no "The upload failed. Nothing was changed." appeared.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-055: A file that is not .html is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-029
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the file "Quarterly Review.pdf" exists.
- **When** He uploads it.
- **Then** "Only .html files are accepted." is shown.
- **And** The folder still lists 3 presentations.
- **And** The activity list has no new line.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-057: An ordinary web page is not a presentation

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031
- **Given** dan.rw@example.org; "About Us.html" is a web page with a heading "Hello" and no declaration as a presentation.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file is not declared as a presentation." is shown.
- **And** Nothing is added to the folder.
- **And** In another run "Undeclared Deck.html", which has 2 well formed slides but no declaration as a presentation, shows the same message "the file is not declared as a presentation" and is refused.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-058: A presentation without any slide is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031
- **Given** dan.rw@example.org; "Empty Deck.html" is declared as a presentation and has 0 slides.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file has no slide." is shown.
- **And** Nothing is added to the folder.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-059: A blocking structure error names its first problem

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031, FR-NEW-053
- **Given** dan.rw@example.org; "Broken Deck.html" is declared as a presentation, has 2 slides, and the second slide has no title attribute.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: missing attribute data-title." is shown.
- **And** Nothing is added to the folder.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-063: Warnings do not block an upload

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_upload_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-031
- **Given** dan.rw@example.org; "Web Pictures.html" is a valid presentation of 2 slides with a picture loaded from another site, which the editor's checks report as a warning only.
- **When** He uploads it.
- **Then** "Uploaded Web Pictures." is shown.
- **And** carol.ro@example.org opens it and sees both slides.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-064: The first problem is the whole file one, before slide ones

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** edge
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031
- **Given** dan.rw@example.org; "Mismatch.html" declares a slide total of 5 while it has 3 slides, and its second slide also lacks its title attribute.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: TOTAL is 5 but the file has 3 slides." is shown.
- **And** Only that one problem is shown.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-126: Markup inside a check message is shown as written

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_upload_e2e.py`
- **Category:** failure
- **Scenario:** SC-019
- **Requirements:** FR-NEW-031, FR-NEW-053
- **Given** dan.rw@example.org; "Markup Deck.html" is declared as a presentation; its slides 1 and 2 both carry the identifier <b>x</b>.
- **When** He uploads it.
- **Then** The message This file is not a valid presentation: expected id "slide-0" but found "<b>x</b>". is shown with the characters <b>x</b> visible, not in bold.
- **And** No dialog and no formatting appears.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-144: Accented names with apostrophes are shown as written

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** edge
- **Scenario:** SC-022
- **Requirements:** FR-NEW-032, FR-NEW-049, FR-NEW-053
- **Given** dan.rw@example.org uploads "L'été (v2).html" into "Pneumo Été".
- **When** The administrator opens the activity list.
- **Then** The line reads Uploaded "L'été (v2)" in "Pneumo Été" exactly, attributed to dan.rw@example.org.
- **Priority:** Low
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-154: An error of the editor's charter rules blocks an upload

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-031
- **Given** dan.rw@example.org; "Medical Deck.html" is declared as a presentation of the medical charter with 1 slide that holds a picture and no source line.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: slide has an image and no source line." is shown.
- **And** Nothing is added to the folder; the activity list has no new line.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-155: A warning listed first is never the first problem

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** edge
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031
- **Given** dan.rw@example.org; "Logo Deck.html" has a picture loaded from https://example.org/logo.png outside every slide (the editor lists that warning first) and 2 slides, the second lacking its title attribute.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: missing attribute data-title." is shown.
- **And** The message does not mention the picture and does not name the slide.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-169: Sign ins and sign outs are not recorded

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** edge
- **Scenario:** SC-022
- **Requirements:** FR-NEW-049, FR-NEW-051
- **Given** A library with the initial content; dan.rw@example.org signs in and out 3 times and uploads "Quarterly Review" once.
- **When** The administrator opens the activity list.
- **Then** Exactly one line is shown, Uploaded "Quarterly Review" in "Cardiology 2027".
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-174: A file that is not valid UTF-8 text is refused with no location

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-031, FR-NEW-053
- **Given** dan.rw@example.org; "Latin Deck.html" is an otherwise valid presentation saved in a Western single byte encoding, with the letter é written as the single byte E9, 1 258 291 bytes.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file is not valid UTF-8 text." is shown.
- **And** The message carries no byte position, line number or server path.
- **And** Nothing is added to the folder.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-179: An empty file is refused as not declared

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_upload_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-031
- **Given** dan.rw@example.org; "Nothing.html" has 0 bytes.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file is not declared as a presentation." is shown.
- **And** Nothing is added to the folder.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-010: A RO member uploads by hand

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_upload_http.py`
- **Category:** security
- **Covers:** Class B occurrence #1
- **Red before the fix because:** the file is stored; the assertion "3 presentations are listed to the administrator" fails with 4.
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-028
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; with her own signed in session, from a command line tool outside the editor, she sends the request the library sends when a RW member uploads the valid file "Quarterly Review.html" (3 slides, 1 258 291 bytes) into "Cardiology 2027".
- **When** She sends it.
- **Then** "Access denied." is returned.
- **And** The administrator's view of "Cardiology 2027" still lists 3 presentations and no "Quarterly Review".
- **And** The activity list has no upload line.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

`tests/test_library_upload_http.py` also holds unit tests of `check_validity` for each of the six messages and for a warning only file (L010 remote image).

## Constraints

- Check order is fixed by FR-NEW-028; do not reorder for convenience.
- Never pass an uploaded name to the file system; the target path comes from `presentation_path` with a new random id.
- No `lint_file` on a temporary file: use `deck_from_text` and `lint_deck` on the bytes in memory.
- Scope boundary: name rules (US-0142), size and robustness (US-0143), replace (US-0144).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (upload pipeline), `.agent_docs/observability.md` (`library.upload`).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0141: Upload a valid presentation into a folder` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
