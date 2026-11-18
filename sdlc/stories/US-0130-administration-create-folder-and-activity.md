# US-0130: Administration: create folders and read the activity list

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0127, US-0129
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

The administrator opens `Administration`, creates a folder (trimmed, composed, 1 to 60 letters of any alphabet, digits, spaces, hyphens, unique without regard to case) and reads the activity list (the 500 newest successful actions, newest first). Nobody else can reach the page or the API, and every state changing request must come from the library's own pages.

## Requirements covered

- SPEC-0025/FR-NEW-013: IF a person who is not Admin opens the administration panel or attempts any of its actions, including reading the activity list, THEN THE web library mode SHALL show "Access denied." and change nothing.
  - Business rules: The entry "Administration" is not shown to anyone but the administrator.
- SPEC-0025/FR-NEW-040: WHEN the administrator creates a folder with a valid name THE web library mode SHALL add an empty folder without any member and list it on the home page.
  - Business rules: The name is trimmed of leading and trailing spaces before it is checked and kept. The name has 1 to 60 characters: letters of any alphabet, digits, spaces, hyphens.
- SPEC-0025/FR-NEW-041: IF the trimmed folder name is empty, longer than 60 characters, or contains anything other than letters of any alphabet, digits, spaces and hyphens THEN THE web library mode SHALL show "Folder names use 1 to 60 letters, digits, spaces or hyphens." and create nothing.
  - Business rules: Letters are the letters of any alphabet, with their combining marks; digits are the decimal digits; the hyphen is the plain hyphen. Emoji, dots, slashes, underscores and other symbols are refused. The name is brought to its composed form first; the length of 1 to 60 is counted on that form.
- SPEC-0025/FR-NEW-042: IF a folder with the same name, without regard to case, already exists THEN THE web library mode SHALL show A folder named "<name>" already exists. and create nothing.
  - Business rules: <name> is the trimmed name the administrator typed. Names are compared without regard to case and on their composed form; names that differ by an accent are different names.
- SPEC-0025/FR-NEW-050: WHEN the administrator opens the activity list THE web library mode SHALL show the 500 latest lines, the newest first.
  - Business rules: The 501st and older lines are no longer shown. The initial content (FR-NEW-054) is not recorded. When there is no line the list shows "No activity yet."
- SPEC-0025/FR-NEW-051: The web library mode SHALL NOT record in the activity list an attempt that was refused, a sign in, or a stored change.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-070: IF a request that changes the library comes from a page of another site, or carries no sign that it comes from the library's own pages, THEN THE web library mode SHALL refuse it with "Access denied." and change nothing, even when it carries a valid session.
  - Business rules: The rule covers every change: storing a change, upload, delete, folder, member and request actions. A request made by the library's own pages, on slides.scm-platform.org, is never affected.
- SPEC-0025/FR-NEW-049 (partial: the line `Created folder "<folder>"`; the other lines come with US-0131, US-0132, US-0141, US-0144, US-0145): WHEN an upload, a replacement or a deletion of a presentation, the creation or deletion of a folder, or the adding, changing or removing of a member succeeds THE web library mode SHALL add a line to the activity list with who did it, when, and what.
  - Business rules: Line texts: Uploaded "<name>" in "<folder>"; Replaced "<name>" in "<folder>"; Deleted "<name>" from "<folder>"; Created folder "<folder>"; Deleted folder "<folder>"; Added <email> as RW to "<folder>" (or RO); Changed <email> to RO in "<folder>" (or RW); Removed <email> from "<folder>". Who is the email address of the person; when is shown as on the folder page. Who is the email address of the person in lower case, whatever letter case Google returned.
- SPEC-0025/FR-NEW-067 (partial: the control names Administration, All folders, Folders, Activity, Folder name, Create folder, Sign out): The web library mode SHALL name the controls and prompts it adds exactly as listed in the business rules.
  - Business rules: Folder page: "All folders" (back to the home page). Administration: sections "Folders" and "Activity"; the field "Folder name" with the button "Create folder"; per folder the button "Delete folder". Deleting a folder: the prompt "Type the folder name to confirm." with the buttons "Delete folder" and "Cancel". Per folder a section "Members": the field "Email address", the chooser "Role" offering "Read and write" and "Read only", the button "Add member"; per member a role chooser and the button "Remove". Upload progress text: "<file name> <percent>%", percent a whole number rounded down. The administration page shows "All folders" and "Sign out". Administration order: folders as on the home page (FR-NEW-015); the members of a folder alphabetical by email address, by character code.

## Independent Test

Run `make test ARGS='-k "library_admin"'`. The assertion that is not a mock: after a RW member posts `{"name": "Backdoor"}` by hand, the `folders` table (direct query) holds the same three rows and the `activity` table the same count; after the administrator's cookie is replayed with no `Origin` header the answer is `Access denied.` and the tables are unchanged.

## Design excerpt

### Decisions

- DEC-019 (SPEC-0025): Checks run in this order for a state changing API request: `Origin` (DEC-022), session, permission of the route (administrator first), then payload validation (role value, address, name). Obliged by: SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-012, SPEC-0025/FR-NEW-014.
- DEC-021 (SPEC-0025): `access.ROUTES` is a table `(origin, method, pattern, permission, handler)`; `LibraryHandler` finds the route, resolves the person (session, or grant on the content origin), computes the role for the route's target and calls `authorize(role, permission)` before any body is read and before the handler runs; a path in no row is "Access denied." for a signed in person and the sign in page for a visitor. A test walks the table and fails for a row without a permission. Obliged by: SPEC-0025/FR-NEW-001, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-020, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-023.
- DEC-022 (SPEC-0025): Every state changing request (any method other than `GET`, `HEAD` and `OPTIONS`: `POST` and `DELETE`) is refused with `Access denied.`, before the session is looked up, unless `Origin` is present and equals the origin of the receiving host exactly, and `Sec-Fetch-Site`, when present, is `same-origin` (or `none`); JSON routes also require `Content-Type: application/json`, the upload requires the header `X-File-Name`. The local rule that accepts a missing `Origin` is not used. Obliged by: SPEC-0025/FR-NEW-070, SPEC-0025/FR-NEW-023.
- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-029 (SPEC-0025): Names go through `library/names.py`: `compose` (NFC), `name_key` (NFC of the lower cased composed text), `order_key` (accents removed by NFD and dropping `Mn`, lower case, then the exact name); file names are an allow list (Latin script letters by `unicodedata.name` starting with `LATIN`, `Mn` only after such a letter, ASCII digits, space, `. _ - ( ) '`), at most 100 composed characters before `.html`, no leading dot, no edge space, not only spaces; folder names are letters of any script (`L*`), `M*`, decimal digits (`Nd`), space and hyphen, 1 to 60 composed characters after trimming; addresses match `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` after trimming and are stored lower case. All pages build text through `pages.esc()` (`html.escape(quote=True)`), and JavaScript writes with `textContent`. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-042, SPEC-0025/FR-NEW-046, SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-033.
- DEC-030 (SPEC-0025): Activity is the table `activity`, one row per successful action written in the same transaction as the action, with the final line text and the actor's lower case address; after each insert rows older than the 500 newest are deleted; the page reads `ORDER BY id DESC LIMIT 500`. Refusals, sign ins and stored changes never write. Obliged by: SPEC-0025/FR-NEW-049, SPEC-0025/FR-NEW-050, SPEC-0025/FR-NEW-051.
- DEC-053 (SPEC-0025): Library pages use plain HTML controls (`a`, `button`, `form`, `label`, `input`, `select`, `<dialog>` for the questions) with a visible text or an `aria-label` on every control, no click handler on a non focusable element, and `library.js` moves focus into a dialog when it opens and back to the control when it closes. Obliged by: SPEC-0025/FR-NEW-064.

### Data model

Migration 3 (`MIGRATIONS[2]`):

```sql
CREATE TABLE activity(id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, actor TEXT NOT NULL, text TEXT NOT NULL);
```

Each insert is followed in the same transaction by `DELETE FROM activity WHERE id <= (SELECT MAX(id) FROM activity) - 500`. `text` is the final line (`Created folder "Oncology 2030"`), `actor` the lower case address, `at` the injected clock. The page shows `ORDER BY id DESC LIMIT 500`.

### Contracts

**Routes** (library origin):

| Method path | Permission | Behavior |
|---|---|---|
| `GET /admin` | `ADMINISTER` | `pages.admin_page(folders, activity)` |
| `POST /api/folders` | `ADMINISTER` | body `{"name": str}`; `names.check_folder_name`; `Library.create_folder`; `201 {"ok": true, "id": "<folder id>"}` |

Errors are `400 {"ok": false, "error": "<exact text>"}`: `Folder names use 1 to 60 letters, digits, spaces or hyphens.` and `A folder named "<name>" already exists.` (with the trimmed name as typed, escaped by the client with `textContent`). A person who is not the administrator gets `403` `Access denied.` for the page and the API before the body is read or the name is checked (DEC-019).

**Names** (`names.check_folder_name(raw) -> str`): `compose(raw.strip())`; length 1 to 60 after composition; every character of category `L*`, `M*`, `Nd`, space `U+0020` or hyphen `U+002D`; `NameRefused` otherwise (emoji, dots, slashes, underscores, `..`). Uniqueness is the `name_key` unique constraint; a violation maps to the duplicate message.

**Activity page**: section `Activity` lists lines newest first as `<time datetime>` (formatted by `library.js`), the actor, the text (all escaped); empty shows `No activity yet.`. Sections of the admin page: `Folders` (the folders as on the home page, each with its `Delete folder` and `Members` parts arriving in US-0131 and US-0132), the field labelled `Folder name` and the button `Create folder`, and `Activity`; the page shows `All folders` and `Sign out`.

**library.js**: submits the create form with `fetch(POST, JSON)`, shows `ok` by reloading the page and an error by writing `error` with `textContent` into a `role="alert"` element.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/routes_admin.py` | create | admin page and folder creation |
| `src/mcp_htmleditor/library/store.py` | modify | `create_folder`, `activity`, `record` |
| `src/mcp_htmleditor/library/names.py` | modify | `check_folder_name`, `NameRefused` |
| `src/mcp_htmleditor/library/pages.py` | modify | `admin_page` |
| `src/mcp_htmleditor/static/library.js` | modify | admin forms |
| `tests/library_support.py` | modify | `activity_lines()` and `post_json` helpers |
| `tests/test_library_admin_http.py` | create | functional tests and E2E-SEC-011, E2E-SEC-018 (`test_exploit_*`) |
| `tests/test_library_admin_e2e.py` | create | E2E-096, E2E-097 |

### Existing patterns

`library/routes_library.py` (US-0126) for the route and context idiom; `http_server.py:586-624` (`_read_json_object`, `_read_request_body`) for JSON reading with content type then length checks; `tests/test_http_origin_e2e.py` for origin tests.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-038: A RW member has no administration

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** failure
- **Scenario:** SC-006
- **Requirements:** FR-NEW-013, FR-NEW-024
- **Given** dan.rw@example.org is signed in.
- **When** He looks at the home page and opens the administration link he was told about.
- **Then** The home page has no "Administration" entry; the link shows "Access denied."
- **And** No folder, member or activity line was shown to him.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-086: RW and RO members are refused the administration

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** failure
- **Scenario:** SC-013
- **Requirements:** FR-NEW-013
- **Given** dan.rw@example.org (RW) and carol.ro@example.org (RO) are signed in.
- **When** Each opens the administration link and the activity list link.
- **Then** Each time "Access denied." is shown.
- **And** No home page of either shows "Administration".
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-091: The administrator creates a folder

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** happy (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-015, FR-NEW-019, FR-NEW-040, FR-NEW-041, FR-NEW-042, FR-NEW-049
- **Given** seb.morand@gmail.com is signed in; the standard library.
- **When** He types "  Oncology 2030  " (two spaces on each side) and creates the folder.
- **Then** The home page lists 4 folders, "Cardiology 2027", "Oncology 2030", "Pneumo Été", "WCBIP Melbourne Décembre 2026"; opening "Oncology 2030" shows "This folder has no presentations yet."
- **And** The member list of "Oncology 2030" is empty.
- **And** The activity list gains "Created folder "Oncology 2030"".
- **And** No "Folder names use 1 to 60 letters, digits, spaces or hyphens." and no duplicate message appeared.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-092: A folder name that exists without regard to case is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** failure
- **Scenario:** SC-014
- **Requirements:** FR-NEW-015, FR-NEW-042
- **Given** The standard library.
- **When** The administrator creates a folder named "cardiology 2027".
- **Then** A folder named "cardiology 2027" already exists. is shown.
- **And** The home page still lists 3 folders.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-093: An empty or blank folder name is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** failure
- **Scenario:** SC-014
- **Requirements:** FR-NEW-040, FR-NEW-041
- **Given** The administrator.
- **When** He creates a folder with an empty name, then with 3 spaces.
- **Then** Each time "Folder names use 1 to 60 letters, digits, spaces or hyphens." is shown.
- **And** The home page still lists 3 folders.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-094: A folder name of 61 characters is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** failure
- **Scenario:** SC-014
- **Requirements:** FR-NEW-041
- **Given** The administrator.
- **When** He creates a folder named with 61 letters "A".
- **Then** "Folder names use 1 to 60 letters, digits, spaces or hyphens." is shown.
- **And** No folder was added.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-095: Emoji and symbols in a folder name are refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** failure
- **Scenario:** SC-014
- **Requirements:** FR-NEW-041, FR-NEW-053
- **Given** The administrator.
- **When** He creates in turn "Pneumo 🫁", "Cardio/Rhythm", "Cardio_2027", "R&D" and "Study.2027".
- **Then** Each time "Folder names use 1 to 60 letters, digits, spaces or hyphens." is shown.
- **And** The home page still lists 3 folders.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-096: A name of exactly 60 characters or a single hyphen is accepted

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_admin_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-040, FR-NEW-041
- **Given** The administrator.
- **When** He creates a folder named with 60 letters "B" and a folder named "-".
- **Then** Both are created and listed; the 60 letter name is shown in full without hiding any control.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-097: Names in other alphabets are accepted

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_admin_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-015, FR-NEW-040, FR-NEW-053
- **Given** The administrator.
- **When** He creates "Кардиология 2027", "أمراض الرئة" and "心臓病学".
- **Then** The three folders are listed with their names displayed correctly, the Arabic one reading right to left.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-098: Duplicate checks ignore case and surrounding spaces but not accents

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-040, FR-NEW-042
- **Given** The standard library.
- **When** The administrator creates "  CARDIOLOGY 2027 " (spaces around), then "Pneumo Ete" (no accent).
- **Then** The first shows A folder named "CARDIOLOGY 2027" already exists.; the second is created.
- **And** The home page lists 4 folders, with "Pneumo Ete" and "Pneumo Été" as two different folders.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-139: A member cannot read the activity list

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** failure
- **Scenario:** SC-022
- **Requirements:** FR-NEW-013, FR-NEW-020, FR-NEW-050
- **Given** dan.rw@example.org is signed in.
- **When** He asks for the activity list.
- **Then** "Access denied." is shown; no line is displayed.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-142: Only the 500 latest lines are shown

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** edge
- **Scenario:** SC-022
- **Requirements:** FR-NEW-049, FR-NEW-050
- **Given** 501 successful actions were done, the first being the creation of the folder "Folder 001" and the last the creation of "Folder 501".
- **When** The administrator opens the activity list.
- **Then** 500 lines are shown, the first being "Created folder "Folder 501"" and the last "Created folder "Folder 002""; no line about "Folder 001".
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-163: Folder names: composed form and length counted after it

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_admin_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-040, FR-NEW-041, FR-NEW-042
- **Given** The administrator; "Pneumo Été" exists.
- **When** He creates "Pneumo Été" (accents as separate marks), then a name of 60 letters "é" each written as e plus a mark, then 61 such letters.
- **Then** The first shows A folder named "Pneumo Été" already exists.; the second is created; the third shows "Folder names use 1 to 60 letters, digits, spaces or hyphens."
- **And** The home page lists the folders with the composed names.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-011: A RW member creates a folder by hand

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_admin_http.py`
- **Category:** security
- **Covers:** Class B occurrence #1
- **Red before the fix because:** the folder is created; the assertion "the administrator sees 3 folders" fails with 4.
- **Scenario:** SC-013
- **Requirements:** FR-NEW-013, FR-NEW-040
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; with his own signed in session, from a command line tool outside the editor, he sends the request the administration sends when the administrator creates a folder named "Backdoor".
- **When** He sends it.
- **Then** "Access denied." is returned.
- **And** The administrator's home page lists the same 3 folders and no "Backdoor".
- **And** The activity list has no folder creation line.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-018: A request with the administrator's copied session and no sign of coming from the library

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_admin_http.py`
- **Category:** security
- **Covers:** Class G occurrences #2 and #3
- **Red before the fix because:** the request is accepted since a request with no Origin evidence passes the gate; the assertion "the administrator lists 3 folders" fails with 4.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-013, FR-NEW-040, FR-NEW-070
- **Given** The administrator's session credentials were copied; from a command line tool, with no sign of coming from the library's pages, the copy requests the creation of a folder named "Backdoor".
- **When** The tool sends the request.
- **Then** "Access denied." is returned.
- **And** The administrator's home page, in his real browser, lists the same 3 folders and no "Backdoor".
- **And** The activity list has no folder creation line.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

Unit tests in `tests/test_library_names.py` for `check_folder_name` on the boundary list of E2E-094 to E2E-097 and E2E-163.

## Constraints

- The permission check runs before the body is read and before the name is validated.
- Never interpolate a folder name into HTML or into a path; `esc` and `textContent` only.
- Scope boundary: deleting a folder (US-0131), members (US-0132), upload lines (US-0141).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (origin rule, activity), `.agent_docs/observability.md` (no new span here).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0130: Administration: create folders and read the activity list` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
