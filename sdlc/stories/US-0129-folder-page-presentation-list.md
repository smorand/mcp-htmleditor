# US-0129: The folder page lists presentations

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0127
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

A person opens a folder where they hold a role and sees its presentations with name, last modified date in their own time zone and size, newest first with a stable order; an empty folder says so; a folder they cannot enter or that does not exist gives exactly the same `Access denied.` page; no page leaks another folder or another person's address; the Back button after sign out shows nothing.

## Requirements covered

- SPEC-0025/FR-NEW-018: WHEN a person opens a folder they can access THE web library mode SHALL list its presentations, each with its name, its last modified date and its size, the most recently modified first, and offer a way back to the home page.
  - Business rules: Presentations with the same last modified time (compared to the minute) are ordered by the rule of FR-NEW-015 (accents removed, case ignored, by character code), then by exact name by character code; the order is the same each time it is displayed while nothing changes. Date and time are shown in the person's time zone, on a 24 hour clock, day without a leading zero, minutes truncated (seconds dropped), months written with their first three letters (Jan to Dec): "16 Nov 2026 14:32", "5 Nov 2026 09:05". Size: the unit is chosen from the exact number of bytes: 1 byte reads "1 byte", below 1 024 bytes "N bytes", from 1 024 to 1 048 575 bytes in KB (1 KB is 1 024 bytes), from 1 048 576 bytes in MB (1 MB is 1 048 576 bytes). KB and MB show one decimal, rounded half up from the exact value, so 1 048 575 bytes reads "1024.0 KB". The name is shown without the ".html" ending.
- SPEC-0025/FR-NEW-019: IF the folder has no presentation THEN THE web library mode SHALL show "This folder has no presentations yet."
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-020: The web library mode SHALL NOT reveal to a person the name, content, existence or member list of a folder where they hold no role, nor the email address of any other person.
  - Business rules: The administrator is excepted. The rule covers lists, messages, prompts and the activity list.
- SPEC-0025/FR-NEW-021: The web library mode SHALL NOT let a role held in one folder grant any right in another folder.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-009 (partial: a direct link to a folder, followed while signed out, shows the folder after sign in when the account has a role and `Access denied.` otherwise): WHEN a signed out visitor opens a direct link to a folder or a presentation THE web library mode SHALL show the sign in page and, after a successful sign in, show the linked page when the account has a right on it and "Access denied." when it has none.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-010 (partial: a missing folder and a forbidden folder give the identical `Access denied.` page): IF a link points to a folder or a presentation that does not exist, no longer exists, or belongs to a folder where the person holds no role THEN THE web library mode SHALL show exactly "Access denied." and nothing else.
  - Business rules: The page is identical in wording and content in the three cases; it shows the text "Access denied." and the "Sign out" button, nothing else: it never names the folder or the presentation and never says whether it exists. The same holds for an action refused for these reasons (storing a change, download, delete, upload). When the refusal reaches a presentation open for editing, the editor shows "Access denied." as its only notice (no "Save failed:" prefix) and keeps the unsaved changes on screen. An address of the product that names no page, asked by a signed in person, gives exactly "Access denied." with the "Sign out" button. A refused download or export shows "Access denied." as its only text, with no prefix such as "Export PPTX échoué :"; no file is received and the presentation stays on screen. When the session ended, the person gets the sign in page, unless they have unsaved text: then FR-NEW-007 applies and no download happens. Any other failure of a download or export shows the editor's usual failure notice with the operating system reason, without any file name or path, never the text of an exception.
- SPEC-0025/FR-NEW-060 (partial: 100 presentations listed within 2 seconds): WHILE the library holds 200 folders, or a folder holds 100 presentations, THE web library mode SHALL display that list within 2 seconds on a 50 megabit per second connection.
  - Business rules: Every entry stays reachable. The 2 seconds are counted from the person's request until the whole list can be read and used.
- SPEC-0025/FR-NEW-064 (partial: keyboard and labels of the folder page): The web library mode SHALL make every action of the library pages reachable with the keyboard alone and give every control a visible label or an accessible name.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-072 (partial: a folder page cannot be shown inside a page of another site): The web library mode SHALL NOT accept a session after its person signed out, and SHALL NOT let any library page be shown inside a page of another site.
  - Business rules: A copy of the credentials of a session made before "Sign out" is refused after it, as for a visitor who is not signed in. The refusal of framing applies to every page, including the sign in page.

## Independent Test

Run `make test ARGS='-k "library_folders"'`: the builder creates `Cardiology 2027` with three presentations of exact sizes and modified times (`os.utime`), people sign in, the pages are fetched and a browser opens them with a fixed time zone. The assertion that is not a mock: the page bytes for a missing folder id and for a folder of another team are identical (`==`).

## Design excerpt

### Decisions

- DEC-009 (SPEC-0025): Every library and shell response carries `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, a `Content-Security-Policy` and, when the origin scheme is https, `Strict-Transport-Security: max-age=31536000`; library pages use `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`, JSON answers `default-src 'none'; frame-ancestors 'none'`, the editor shell `frame-ancestors 'none'`, and the deck frame answer `frame-ancestors 'self'` with `X-Frame-Options: SAMEORIGIN`. `library.js` handles `pageshow` with `persisted` by reloading. Obliged by: SPEC-0025/FR-NEW-072, SPEC-0025/FR-NEW-008, SPEC-0025/FR-NEW-001.
- DEC-020 (SPEC-0025): Presentation and folder addresses carry random ids, never names: `/f/<folder id>`, `/open/<presentation id>`, `/d/<presentation id>/`; a "direct link" is one of these. Obliged by: SPEC-0025/FR-NEW-009, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-053.
- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-025 (SPEC-0025): Metadata in one SQLite file (`<library_dir>/library.db`, WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one connection per thread, `BEGIN IMMEDIATE` for writes, migrations numbered by `PRAGMA user_version`); presentation bytes in files named by two random 32 hex ids (`files/<folder id>/<presentation id>.html`); ids validated against `^[0-9a-f]{32}$` before a path is built; names exist only as column values. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-063, SPEC-0025/FR-NEW-060.
- DEC-029 (SPEC-0025): Names go through `library/names.py`: `compose` (NFC), `name_key` (NFC of the lower cased composed text), `order_key` (accents removed by NFD and dropping `Mn`, lower case, then the exact name); file names are an allow list (Latin script letters by `unicodedata.name` starting with `LATIN`, `Mn` only after such a letter, ASCII digits, space, `. _ - ( ) '`), at most 100 composed characters before `.html`, no leading dot, no edge space, not only spaces; folder names are letters of any script (`L*`), `M*`, decimal digits (`Nd`), space and hyphen, 1 to 60 composed characters after trimming; addresses match `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` after trimming and are stored lower case. All pages build text through `pages.esc()` (`html.escape(quote=True)`), and JavaScript writes with `textContent`. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-042, SPEC-0025/FR-NEW-046, SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-033.
- DEC-031 (SPEC-0025): Folder order is `order_key(name)`; presentation order is newest `st_mtime` truncated to the minute first, then `order_key(name)`, then the exact name; the date is sent as `<time datetime="<UTC ISO>">` and formatted by `library.js` from `Date` getters in the browser's zone as `D Mon YYYY HH:MM` (24 hour, no leading zero on the day, English month abbreviations, no seconds); the size is formatted server side by `format_size` from the exact byte count (KB and MB with one decimal rounded half up). Obliged by: SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-018.
- DEC-052 (SPEC-0025): Lists are one query each (folders with the person's role by one join; presentations of a folder with one `os.stat` per file), no pagination, no per row query; the 200 folder and 100 presentation cases are tested for the 2 second bound on loopback with a margin. Obliged by: SPEC-0025/FR-NEW-060.
- DEC-053 (SPEC-0025): Library pages use plain HTML controls (`a`, `button`, `form`, `label`, `input`, `select`, `<dialog>` for the questions) with a visible text or an `aria-label` on every control, no click handler on a non focusable element, and `library.js` moves focus into a dialog when it opens and back to the control when it closes. Obliged by: SPEC-0025/FR-NEW-064.

### Data model

Migration 2 (`MIGRATIONS[1]`):

```sql
CREATE TABLE presentations(id TEXT PRIMARY KEY,
                           folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                           name TEXT NOT NULL, name_key TEXT NOT NULL, created_at REAL NOT NULL,
                           UNIQUE (folder_id, name_key));
```

Files: `<library_dir>/files/<folder id>/<presentation id>.html`, ids `secrets.token_hex(16)` matched by `^[0-9a-f]{32}$` before any path is built (`Library.presentation_path(folder_id, presentation_id) -> Path` raises `ValueError` otherwise). The listed modified time and size come from `os.stat` of that file.

### Contracts

**Route** `GET /f/<fid>` (library origin, `VIEW` on the folder): `403` `pages.access_denied()` when the folder is unknown, the person has no role, or the id is malformed; otherwise `pages.folder_page(folder_name, rows, role, base)` with `rows` ordered by (minute of `st_mtime` descending, `names.order_key(name)`, exact name). Each row: the name without `.html` (escaped), `<time datetime="<UTC ISO 8601 Z>">` with the UTC text `D Mon YYYY HH:MM` as fallback content, the size from `names.format_size(bytes)`. A link `<a href="/">All folders</a>`; the `Sign out` form. An empty folder shows `This folder has no presentations yet.`.

`names.format_size(count: int) -> str`: `1` gives `1 byte`; below 1024 `N bytes`; from 1024 to 1 048 575 KB with one decimal from the exact value rounded half up using integer arithmetic (`1 075 -> 1.0 KB`, `1 076 -> 1.1 KB`, `1 048 575 -> 1024.0 KB`); from 1 048 576 MB the same way (`1 048 576 -> 1.0 MB`).

**JavaScript** (`static/library.js`, public path `/lib/library.js`, loaded by every page with `<script src="/lib/library.js" defer>`): on `DOMContentLoaded` replaces the text of each `time[datetime]` by the date in the browser's zone formatted `D Mon YYYY HH:MM` from `Date` getters (24 hour clock, day without leading zero, English month abbreviations `Jan` to `Dec`, minutes truncated, seconds dropped), and on `pageshow` with `event.persisted` reloads the page (Back after sign out, DEC-009).

**Builder** (`tests/library_support.py::LibraryBuilder`): `folder(name) -> Folder`, `member(folder, email, role)`, `presentation(folder, name, *, size: int, slides: int, modified: datetime, title: str = ...) -> Presentation` writes a valid generated deck padded with an HTML comment to the exact byte count, with a `data-doc-type="presentation"` html tag and `slides` slides, then `os.utime`.

**Framing** (E2E-SEC-024): `X-Frame-Options: DENY` and `frame-ancestors 'none'` already on every response; the test proves it in a browser.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/store.py` | modify | presentations, `presentation_path`, `presentations_in` |
| `src/mcp_htmleditor/library/names.py` | modify | `format_size` |
| `src/mcp_htmleditor/library/pages.py` | modify | `folder_page` |
| `src/mcp_htmleditor/library/routes_library.py` | modify | `/f/<fid>` row and handler |
| `src/mcp_htmleditor/static/library.js` | create | date formatting, `pageshow` reload |
| `tests/library_support.py` | modify | `LibraryBuilder.presentation`, Playwright launch args and time zone helper |
| `tests/test_library_folders_http.py` | create | functional tests |
| `tests/test_library_folders_e2e.py` | create | browser tests and E2E-SEC-024 (`test_exploit_*`) |

### Existing patterns

`tests/test_http_deck_files_e2e.py` for building files and asserting listings; `tests/browser_wait.py` (`wait_until`) and `tests/test_save_safety_e2e.py` for Playwright tests; `deck_support.py` for generating decks.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-006: The Back button after signing out shows no library content

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_folders_e2e.py`
- **Category:** edge (state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-008, FR-NEW-072
- **Given** dan.rw@example.org is signed in and looking at the folder page of "Cardiology 2027".
- **When** He chooses "Sign out" and then presses the Back button of the browser.
- **Then** The sign in page is shown; "Cardiology 2027", "Heart Failure Update", "Arrhythmia Basics" and "Statins Review" are not visible.
- **And** Dan's session in a second browser, where he did not sign out, is still signed in.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-009: A session older than 30 days sends the person to the sign in page

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** failure (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001, FR-NEW-005, FR-NEW-006, FR-NEW-009
- **Given** lamya.chrif@gmail.com signed in 30 days 1 minute ago.
- **When** She opens the link to the folder "WCBIP Melbourne Décembre 2026".
- **Then** The sign in page is shown, not the folder.
- **And** After she signs in again the folder page opens, and her new session lasts 30 days from now.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-017: A library of 200 folders stays usable

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_folders_e2e.py`
- **Category:** edge
- **Scenario:** SC-003
- **Requirements:** FR-NEW-015, FR-NEW-060, FR-NEW-064
- **Given** The administrator, and 200 folders named "Folder 001" to "Folder 200".
- **When** seb.morand@gmail.com opens the home page on a 50 megabit per second connection, then reaches "Folder 200" using the keyboard only.
- **Then** All 200 folders are listed within 2 seconds of the request, "Folder 001" first and "Folder 200" last, and "Folder 200" opens with the Enter key.
- **And** Every folder entry has a visible name that a screen reader announces.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-019: An unreadable library on a folder page shows no partial list

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-003
- **Requirements:** FR-NEW-017, FR-NEW-018, FR-NEW-062
- **Given** dan.rw@example.org has the folder page of "Cardiology 2027" open; the stored library then cannot be read.
- **When** He refreshes the page.
- **Then** "The library is unavailable. Try again later." is shown and none of the 3 presentations is listed.
- **And** When the library can be read again the refresh lists the same 3 presentations with their sizes.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-020: A folder lists its presentations newest first

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_folders_e2e.py`
- **Category:** happy
- **Scenario:** SC-004
- **Requirements:** FR-NEW-015, FR-NEW-018, FR-NEW-024
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; time zone UTC.
- **When** He opens "Cardiology 2027" from the home page.
- **Then** Three rows in this order: "Arrhythmia Basics", 12 Nov 2026 16:40, 512.0 KB; "Statins Review", 12 Nov 2026 16:40, 1.5 MB; "Heart Failure Update", 10 Nov 2026 09:15, 2.0 MB.
- **And** A way back to the home page is shown and works.
- **And** The two rows with the same time are in alphabetical order.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-022: An empty folder says so

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018, FR-NEW-019
- **Given** The administrator; "Pneumo Été" holds no presentation.
- **When** He opens "Pneumo Été".
- **Then** "This folder has no presentations yet." is shown, with the way back to the home page.
- **And** No list header or empty table is shown instead of the message.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-023: A folder that does not exist is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-010, FR-NEW-020
- **Given** dan.rw@example.org is signed in; no folder "Oncology 2030" exists.
- **When** He opens the link to the folder "Oncology 2030".
- **Then** The text "Access denied." and the "Sign out" button are shown, nothing else.
- **And** A screenshot of this page is the reference for the next test.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-024: A folder the person cannot enter gives the same page as a missing one

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-010, FR-NEW-020, FR-NEW-021
- **Given** carol.ro@example.org holds a role only in "Cardiology 2027".
- **When** She opens the link to the folder "WCBIP Melbourne Décembre 2026", then the link to the missing folder "Oncology 2030".
- **Then** Both pages show the text "Access denied." and the "Sign out" button and nothing else; the two pages are identical in wording and content.
- **And** Neither page names a folder, a presentation or a member.
- **And** The two answers are identical on the wire: same status, same headers except the date, same body.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-028: Sizes are shown in bytes, KB and MB

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018, FR-NEW-030
- **Given** Presentations of 1 byte, 900 bytes, 1 023 bytes, 1 024 bytes, 1 048 576 bytes and 26 214 400 bytes in one folder.
- **When** A member opens the folder.
- **Then** The sizes read "1 byte", "900 bytes", "1023 bytes", "1.0 KB", "1.0 MB" and "25.0 MB".
- **Priority:** Low
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-029: Dates follow the person's time zone

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_folders_e2e.py`
- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018
- **Given** carol.ro@example.org's browser is set to the Melbourne time zone (UTC plus 11 hours in November); dan.rw@example.org's browser is set to UTC.
- **When** Each opens the folder page of "Cardiology 2027".
- **Then** Dan sees "Arrhythmia Basics" modified 12 Nov 2026 16:40; Carol sees the same instant as 13 Nov 2026 03:40.
- **And** The order of the rows is the same for both.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-037: A RW member cannot enter a folder where they hold no role

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** failure
- **Scenario:** SC-006
- **Requirements:** FR-NEW-010, FR-NEW-020, FR-NEW-021
- **Given** dan.rw@example.org holds roles in "Cardiology 2027" and "Pneumo Été" only.
- **When** He opens the link to "WCBIP Melbourne Décembre 2026".
- **Then** "Access denied." is shown; no presentation name of that folder appears.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-122: Each member sees only their own folders

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** happy
- **Scenario:** SC-018
- **Requirements:** FR-NEW-015, FR-NEW-020, FR-NEW-021
- **Given** The library holds "WCBIP Melbourne Décembre 2026" (lamya.chrif@gmail.com RW), "Cardiology 2027" (dan.rw@example.org RW, carol.ro@example.org RO) and "Pneumo Été" (dan.rw@example.org RO).
- **When** dan.rw@example.org, carol.ro@example.org and lamya.chrif@gmail.com each open the home page and every page they can reach.
- **Then** Dan sees exactly "Cardiology 2027" and "Pneumo Été"; Carol sees only "Cardiology 2027"; Lamya sees only "WCBIP Melbourne Décembre 2026". No page of one shows a name of a folder or presentation of another, nor an email address of another person.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-164: Rounding of sizes and display of times

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_folders_e2e.py`
- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018
- **Given** A folder holds presentations of 1 075, 1 076, 1 048 575 and 1 572 864 bytes; they were modified 5 Nov 2026 09:05:59 UTC, 12 Nov 2026 23:59:59 UTC, 1 Dec 2026 00:00:00 UTC and 30 Sep 2026 12:00:00 UTC respectively; person in UTC.
- **When** A member opens the folder.
- **Then** The sizes read "1.0 KB" (1 075 bytes, exact value 1.0498), "1.1 KB" (1 076), "1024.0 KB" (1 048 575) and "1.5 MB"; the times read "5 Nov 2026 09:05", "12 Nov 2026 23:59", "1 Dec 2026 00:00" and "30 Sep 2026 12:00" (24 hour clock, no leading zero on the day, seconds dropped).
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-168: A folder of 100 presentations lists within 2 seconds

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_folders_http.py`
- **Category:** happy
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018, FR-NEW-060
- **Given** "Cardiology 2027" holds 100 presentations "Deck 001" to "Deck 100"; carol.ro@example.org on a 50 megabit per second connection.
- **When** She opens the folder.
- **Then** All 100 presentations are listed, within 2 seconds, newest first, each with its name, date and size.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-024: A page of another site shows a library page inside a frame

- Level / Driver / Location: exploit / Playwright / `tests/test_library_folders_e2e.py`
- **Category:** security
- **Covers:** Class G occurrence #5
- **Red before the fix because:** the library page is displayed in the frame; the assertion "the frame shows no presentation name" fails and shows "Heart Failure Update".
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-020, FR-NEW-072
- **Given** carol.ro@example.org is signed in; she opens https://evil.example/frame, which shows the folder page of "Cardiology 2027" and the sign in page of the library each inside a frame, under a button of its own.
- **When** The page loads.
- **Then** Both frames stay empty: no folder name, no presentation name, no button of the library.
- **And** Opened on its own in a tab, the same folder page still shows "Cardiology 2027" to Carol.
- **And** No library action was done by the click on the button of the other site.
- **And** The administrator's own view of the folder page, opened in a tab at the same moment, lists the same presentations of "Cardiology 2027" and shows no click made on his behalf.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

Unit tests in `tests/test_library_names.py` for `format_size` at 0, 1, 900, 1023, 1024, 1075, 1076, 1048575, 1048576 and 26214400 bytes.

## Constraints

- No path is ever built from a name; only from the two validated ids.
- The time zone is the browser's: the server never formats a date for display (a UTC fallback text is only the no JavaScript fallback).
- Scope boundary: opening a presentation (US-0133), upload (US-0141), delete (US-0145).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (storage layout, folder page), `.agent_docs/testing.md` (builder).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0129: The folder page lists presentations` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
