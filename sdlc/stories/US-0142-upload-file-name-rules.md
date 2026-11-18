# US-0142: Upload file names: allow list, composed form, hostile names

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0141
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

A file name is accepted only when it is composed (NFC), at most 100 characters before `.html`, has no path, no leading dot, no edge space, is not only spaces, and holds only Latin script letters, ASCII digits, spaces and `. _ - ( ) '`; anything else gives `This file name is not allowed.` and stores nothing. Hostile names (`../../etc/passwd.html`, `a'; DROP TABLE users;--.html`, `<script>alert(1)</script>.html`) change nothing.

## Requirements covered

- SPEC-0025/FR-NEW-032: IF the name of the chosen file contains a path, starts with a dot, starts or ends with a space, is made only of spaces, exceeds 100 characters before ".html", or contains a character other than letters, digits, spaces, accented letters and . _ - ( ) ' THEN THE web library mode SHALL show "This file name is not allowed." and store nothing.
  - Business rules: Letters are the Latin-script letters, with or without accents, including ł, ø, œ and ß; the apostrophe is the straight one (') only. Dots inside the name are allowed ("Report.v2.final.html"). The name is first brought to its composed form (an "e" followed by an accent mark counts as the single letter "é") before it is checked, compared or stored. The 100 characters are counted on that composed form, without ".html": 100 are allowed, 101 are refused.
- SPEC-0025/FR-NEW-021 (partial: an uploaded name can never place a file outside its folder or in another folder): The web library mode SHALL NOT let a role held in one folder grant any right in another folder.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-053 (partial: names, check messages and addresses are shown as written and never interpreted): The web library mode SHALL NOT interpret as markup any text a person or a file supplies (names, email addresses, check messages): it is shown exactly as written.
  - Business rules: none beyond the statement.

## Independent Test

Run `make test ARGS='-k "library_names"'`. The assertion that is not a mock: after each hostile upload `StoredLibrary.entries()` holds no entry named `passwd`, nothing outside `files/<folder id>/`, the `members`, `folders` and `presentations` tables are identical (row dump compared) and the activity table has the same count.

## Design excerpt

### Decisions

- DEC-019 (SPEC-0025): Checks run in this order for a state changing API request: `Origin` (DEC-022), session, permission of the route (administrator first), then payload validation (role value, address, name). Obliged by: SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-012, SPEC-0025/FR-NEW-014.
- DEC-025 (SPEC-0025): Metadata in one SQLite file (`<library_dir>/library.db`, WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one connection per thread, `BEGIN IMMEDIATE` for writes, migrations numbered by `PRAGMA user_version`); presentation bytes in files named by two random 32 hex ids (`files/<folder id>/<presentation id>.html`); ids validated against `^[0-9a-f]{32}$` before a path is built; names exist only as column values. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-063, SPEC-0025/FR-NEW-060.
- DEC-029 (SPEC-0025): Names go through `library/names.py`: `compose` (NFC), `name_key` (NFC of the lower cased composed text), `order_key` (accents removed by NFD and dropping `Mn`, lower case, then the exact name); file names are an allow list (Latin script letters by `unicodedata.name` starting with `LATIN`, `Mn` only after such a letter, ASCII digits, space, `. _ - ( ) '`), at most 100 composed characters before `.html`, no leading dot, no edge space, not only spaces; folder names are letters of any script (`L*`), `M*`, decimal digits (`Nd`), space and hyphen, 1 to 60 composed characters after trimming; addresses match `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` after trimming and are stored lower case. All pages build text through `pages.esc()` (`html.escape(quote=True)`), and JavaScript writes with `textContent`. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-042, SPEC-0025/FR-NEW-046, SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-033.
- DEC-033 (SPEC-0025): The upload is `POST /api/folders/<fid>/presentations` with the raw body, `X-File-Name` (percent encoded UTF-8) and `Content-Length`; checks run in the order right, extension, name, size (declared length against 26 214 400), then the body is read as exactly the declared count (at most 26 214 400) and checked for validity, then the collision; a `Transfer-Encoding: chunked` body is accepted on this route only and decoded with a hard stop at 26 214 401 bytes; extra bytes beyond the declared length are never read; an answer given before the body was read (refusal, oversize) is followed by `shutdown(SHUT_WR)`, a bounded discard of at most 1 MiB or 2 seconds of the client's input with `socket.recv` (not through `rfile`, so the byte counter of the hostile length test stays at the declared length) and then the close, because closing a socket that still holds unread input sends a TCP reset that can destroy the answer before the client reads it (the server is HTTP/1.0 and closes after each answer); at most 4 uploads are received at once (a fifth gets `503` with `The upload failed. Nothing was changed.`). Obliged by: SPEC-0025/FR-NEW-028, SPEC-0025/FR-NEW-029, SPEC-0025/FR-NEW-030, SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038.
- DEC-055 (SPEC-0025): Every page, message and control the mode adds is an English constant in `library/pages.py` (the exact texts are the ones quoted in the requirements and tests of each story); `static/editor-library.js` adds only `Access denied.` and `Your session has expired. Sign in again to save.`; the editor's own labels, notices and the presentations keep their texts, French ones included. Obliged by: SPEC-0025/FR-NEW-065.

### Data model

No change.

### Contracts

**`names.check_file_name(raw: str) -> str`** (returns the composed stem without `.html`, raises `NameRefused("This file name is not allowed.")`), applied after the extension check and before the size check (DEC-033). `raw` is the percent decoded `X-File-Name` (`urllib.parse.unquote(value, errors="strict")`; an invalid percent sequence or invalid UTF-8 means the name is not allowed). Steps: `name = compose(raw)`; `stem = name[:-5]` (the extension was already checked, `.html` in any case); refuse when: `stem` is empty or only spaces; starts or ends with a space; starts with `.`; `len(stem) > 100`; contains `/`, `\` or any control character; any character is not allowed. Allowed characters: a letter whose `unicodedata.name(ch, "")` starts with `LATIN` (this includes `ł ø œ ß` and every precomposed accented Latin letter), an ASCII digit, `U+0020`, and `. _ - ( ) '` with the straight apostrophe `U+0027` only (the curly apostrophe `U+2019` is refused); a combining mark (category `Mn`) is allowed only right after such a letter. Dots inside the name are allowed (`Report.v2.final`). 100 characters are counted on the composed form: `e` plus U+0301 counts as one.

**Tests rely on** the generators of US-0141 for valid decks and on `StoredLibrary` for the second channel. E2E-SEC-005 first posts the folder name `..` to `POST /api/folders` (refused since US-0130) and then uploads `Quarterly Review.html` and checks it lands only under its own `files/<fid>/`.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/names.py` | modify | `check_file_name` |
| `src/mcp_htmleditor/library/uploads.py` | modify | call it in the check order |
| `tests/test_library_names.py` | modify | unit tests of `check_file_name` |
| `tests/test_library_names_http.py` | create | functional tests and E2E-SEC-001, 002, 003, 005 (`test_exploit_*`) |
| `tests/test_library_names_e2e.py` | create | E2E-SEC-004 (`test_exploit_*`, browser) |

### Existing patterns

`tests/test_http_deck_files_e2e.py` for hostile path payload tests; `library/names.py` from US-0128 and US-0130 for `NameRefused` and `compose`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-060: A file name that carries a folder path is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_names_http.py`
- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-032
- **Given** dan.rw@example.org; the valid file is named "2026/Quarterly Review.html".
- **When** He uploads it.
- **Then** "This file name is not allowed." is shown.
- **And** No "Quarterly Review" appears in any folder, seen by the administrator.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-061: Names starting with a dot or using other characters are refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_names_http.py`
- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-032
- **Given** dan.rw@example.org; valid files named ".hidden.html", "Report #1.html" and "Rapport@2026.html".
- **When** He uploads each in turn.
- **Then** Each time "This file name is not allowed." is shown.
- **And** The folder still lists 3 presentations.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-065: The extension is checked before the name and the size

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_names_http.py`
- **Category:** edge
- **Scenario:** SC-009
- **Requirements:** FR-NEW-029, FR-NEW-030, FR-NEW-032
- **Given** dan.rw@example.org; "notes.txt" is 30 MB; "a/b.html" is 30 MB.
- **When** He uploads each in turn.
- **Then** The first shows "Only .html files are accepted."; the second shows "This file name is not allowed."
- **And** Neither shows "The file is larger than 25 MB."
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-125: Dots, parentheses and apostrophes inside a name are accepted

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_names_http.py`
- **Category:** happy (side effect)
- **Scenario:** SC-019
- **Requirements:** FR-NEW-028, FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; valid files "Report.v2.final.html" and "L'été (v2).html".
- **When** He uploads both.
- **Then** "Uploaded Report.v2.final." and "Uploaded L'été (v2)." are shown; the folder lists both names exactly as written.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-127: Encoded and look alike names are refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_names_http.py`
- **Category:** edge
- **Scenario:** SC-019
- **Requirements:** FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org; valid files named "%2e%2e%2fsecret.html", "..\..\secret.html", "Report‮txt.html" (right to left override character) and a name containing a NUL character.
- **When** He uploads each in turn.
- **Then** Each time "This file name is not allowed." is shown.
- **And** The folder still lists 3 presentations.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-175: File names accept Latin-script letters and the straight apostrophe only

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_names_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-032
- **Given** dan.rw@example.org; valid files named "Łódź Study.html", "Øresund Plan.html", "Cœur Étude.html", "Straße Report.html" and "Dan’s Deck.html" (curly apostrophe).
- **When** He uploads each in turn.
- **Then** The first four end with "Uploaded <name>."; the last shows "This file name is not allowed."
- **And** The folder lists the four accepted names exactly as written.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-001: A RO member uploads a path traversal name

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_names_http.py`
- **Category:** security
- **Covers:** Class A occurrences #3 and #5
- **Red before the fix because:** the file is written one level above the folder; the assertion "no entry named passwd anywhere in the library storage" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-010, FR-NEW-021, FR-NEW-023, FR-NEW-032
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; she sends by hand the upload of a valid presentation named "../../etc/passwd.html" with her own session.
- **When** She sends it.
- **Then** "Access denied." is returned.
- **And** The operator's listing of everything the library stores, every folder and every history, contains no entry named "passwd" and nothing outside the folders.
- **And** The administrator's view of "Cardiology 2027" is unchanged: 3 presentations; the activity list has no new line.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-002: A RW member uploads a path traversal name

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_names_http.py`
- **Category:** security
- **Covers:** Class A occurrences #3 and #5
- **Red before the fix because:** the name is cleaned to "passwd.html" and stored; the assertion "no entry named passwd" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-021, FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the file named "../../etc/passwd.html" is a valid presentation.
- **When** He uploads it.
- **Then** "This file name is not allowed." is shown.
- **And** The operator's listing of everything the library stores contains no entry named "passwd" and nothing outside the folders.
- **And** The administrator's view lists the same 3 presentations in "Cardiology 2027" and the same folders; lamya.chrif@gmail.com still sees her 2 presentations.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-003: A name that looks like a data erasing command is refused

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_names_http.py`
- **Category:** security
- **Covers:** Class A occurrence #3
- **Red before the fix because:** a build that accepts any name stores "a'; DROP TABLE users;--"; the assertion "no presentation with that name in any folder, seen by the administrator" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the valid file is named "a'; DROP TABLE users;--.html".
- **When** He uploads it.
- **Then** "This file name is not allowed." is shown.
- **And** The administrator's view of every folder is unchanged, with the same members and roles; no presentation with that name exists.
- **And** lamya.chrif@gmail.com and carol.ro@example.org can still sign in and see their folders.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-004: A name carrying a script tag is refused

- Level / Driver / Location: exploit / Playwright / `tests/test_library_names_e2e.py`
- **Category:** security
- **Covers:** Class A occurrence #3
- **Red before the fix because:** the name is stored and shown without escaping; the assertion "no dialog appears on the administrator's folder page" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the valid file is named "<script>alert(1)</script>.html".
- **When** He uploads it, then opens the folder page.
- **Then** "This file name is not allowed." is shown.
- **And** The administrator's folder page and activity list show no such name and display no alert dialog.
- **And** carol.ro@example.org's folder page shows no dialog either.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-005: A folder named two dots is refused

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_names_http.py`
- **Category:** security
- **Covers:** Class A occurrence #3
- **Red before the fix because:** a folder named ".." is created and later uploads land one level up; the assertion "3 folders listed and nothing outside the folders" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-021, FR-NEW-041, FR-NEW-053
- **Given** seb.morand@gmail.com is signed in.
- **When** He creates a folder named "..".
- **Then** "Folder names use 1 to 60 letters, digits, spaces or hyphens." is shown.
- **And** The home page still lists 3 folders.
- **And** The operator's listing of everything the library stores shows no new area and nothing outside the folders; uploading "Quarterly Review.html" by dan.rw@example.org into "Cardiology 2027" afterwards still lands only there.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the folder name `..` is refused by US-0130; the last And checks that an upload by Dan lands only under its own folder (needs the upload of US-0141).

### Story tests (not spec tests)

Parametrized unit tests in `tests/test_library_names.py`: 100 characters accepted, 101 refused, composed and decomposed `é`, `ł ø œ ß`, curly apostrophe refused, Cyrillic refused, trailing space refused, `Report.v2.final.html` accepted.

## Constraints

- The allow list is closed: no regular expression that accepts `\w`; classify characters with `unicodedata`.
- Never normalize with `casefold` or `strip` beyond what the spec says; names are compared by `name_key` only.
- Scope boundary: size and robustness (US-0143), collisions (US-0144).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (name rules).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0142: Upload file names: allow list, composed form, hostile names` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
