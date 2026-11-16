# US-0128: Exact 30 day sessions, restarts, unavailable library, 200 folders

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0127
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective

Prove and finish the lifetime rules: a session is valid for exactly 30 days from sign in, never longer because of use, and survives a restart; when the stored library cannot be read every page says `The library is unavailable. Try again later.` with no partial list and recovers by itself; the home page with 200 folders answers within 2 seconds and every link is reachable by keyboard with a visible name.

## Requirements covered

- SPEC-0025/FR-NEW-005: WHILE less than 30 days have passed since the person signed in THE web library mode SHALL keep them signed in, including after the browser is closed and opened again.
  - Business rules: The 30 days are counted from the sign in and are never extended by use. Signing in again starts a new period of 30 days.
- SPEC-0025/FR-NEW-006: IF 30 days have passed since the person signed in THEN THE web library mode SHALL treat the person as signed out and show the sign in page on their next action.
  - Business rules: The day 30 limit is exact to the minute: 29 days 23 hours 59 minutes is still signed in, 30 days 1 minute is signed out.
- SPEC-0025/FR-NEW-017: IF the stored library cannot be read THEN THE web library mode SHALL show "The library is unavailable. Try again later." and no partial content.
  - Business rules: The library works again, with all its content, as soon as it can be read.
- SPEC-0025/FR-NEW-060 (partial: 200 folders on the home page within 2 seconds; 100 presentations come with US-0129): WHILE the library holds 200 folders, or a folder holds 100 presentations, THE web library mode SHALL display that list within 2 seconds on a 50 megabit per second connection.
  - Business rules: Every entry stays reachable. The 2 seconds are counted from the person's request until the whole list can be read and used.
- SPEC-0025/FR-NEW-062 (partial: sessions and folders survive a restart of the process; presentation content and activity come with later stories): The web library mode SHALL keep every folder, presentation, history, member, activity line and signed in session after the product is restarted.
  - Business rules: A person signed in before a restart is still signed in after it, for the rest of the 30 days counted from their sign in.
- SPEC-0025/FR-NEW-064 (partial: keyboard and labels of the home page): The web library mode SHALL make every action of the library pages reachable with the keyboard alone and give every control a visible label or an accessible name.
  - Business rules: none beyond the statement.

## Independent Test

Run `make test ARGS='-k library_sessions'`: a `FakeClock` moves by `29 days 23 hours 59 minutes` then `1 minute`, a second `LibraryServer` is started on the same directory, a corrupted database is swapped in and out. The assertion that is not a mock: the sessions table is read directly and `expires_at - created_at == 2_592_000` after ten requests.

## Design excerpt

### Decisions

- DEC-017 (SPEC-0025): A session is a row (`id_hash` = sha256 of a 256 bit token, `email`, `created_at`, `expires_at = created_at + 2 592 000 s`), the cookie is `__Host-lib` (`lib` on http) with `HttpOnly`, `SameSite=Lax`, `Secure` on https, `Max-Age=2592000`; `expires_at` is never updated; a request is signed in only while `now < expires_at`; sign out deletes the row. Obliged by: SPEC-0025/FR-NEW-005, SPEC-0025/FR-NEW-006, SPEC-0025/FR-NEW-008, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-072.
- DEC-024 (SPEC-0025): A `sqlite3.Error` or an `OSError` while a library page or the API reads the stored library gives `503` and `The library is unavailable. Try again later.` with no partial content; the next request after the library can be read again works with no restart. Obliged by: SPEC-0025/FR-NEW-017, SPEC-0025/FR-NEW-062.
- DEC-032 (SPEC-0025): Time and faults are injected, not patched globally: `LibraryServer(clock=time.time)` hands the clock to every repository; the test seams are `Database.connect` (raise `sqlite3.OperationalError` to simulate an unreadable library), `fileio.replace_file` (`fileio.py:44-46`, already the documented failure seam, raise `OSError(errno.ENOSPC)`), and a socket wrapper in tests that cuts a connection at a byte count. Obliged by: SPEC-0025/FR-NEW-005, SPEC-0025/FR-NEW-006, SPEC-0025/FR-NEW-017, SPEC-0025/FR-NEW-038.
- DEC-052 (SPEC-0025): Lists are one query each (folders with the person's role by one join; presentations of a folder with one `os.stat` per file), no pagination, no per row query; the 200 folder and 100 presentation cases are tested for the 2 second bound on loopback with a margin. Obliged by: SPEC-0025/FR-NEW-060.
- DEC-053 (SPEC-0025): Library pages use plain HTML controls (`a`, `button`, `form`, `label`, `input`, `select`, `<dialog>` for the questions) with a visible text or an `aria-label` on every control, no click handler on a non focusable element, and `library.js` moves focus into a dialog when it opens and back to the control when it closes. Obliged by: SPEC-0025/FR-NEW-064.

### Data model

No change.

### Contracts

**Clock**: `LibraryServer(settings, clock=...)` passes `clock` to `Accounts`, `Library` and the dispatcher; no module of `library/` calls `time.time` directly (grep test). `tests/library_support.py::FakeClock(start: float)` with `advance(seconds: float)`.

**Expiry rule** (`Accounts.session_for`): alive when `clock() < expires_at`; at exactly `expires_at` the session is over; rows are not deleted at expiry (US-0137 needs them for 24 hours) but are purged by `Accounts.purge()` (rows with `clock() > expires_at + 86_400`, unused `logins` older than 10 minutes, `tickets` older than 60 seconds), called at each `begin_login`, `finish_login` and ticket issue.

**Unavailable library**: `LibraryHandler` wraps the dispatch in `try/except (sqlite3.Error, OSError)` around library reads and answers `503` with `pages.library_unavailable()` (`The library is unavailable. Try again later.`, no folder name, no list, Sign out form not shown). The very next request after the database is readable again succeeds (connections are opened per thread and a failed `Database.connection()` is not cached). Test seam: `Database.connect_hook: Callable[[], None] | None` (in `store.py`), a module level attribute the tests set to raise `sqlite3.OperationalError("unable to open database file")`; production never sets it (`fileio.replace_file`, `fileio.py:44-46`, is the precedent for a documented test seam).

**Restart**: `LibraryServer.stop()` then a new `LibraryServer` on the same `library_dir` reads the same tables; no state is kept in memory.

**Home page scale**: `Library.folders_for` is one query (`SELECT f.id, f.name, m.role FROM folders f JOIN members m ...`, for the administrator `SELECT id, name FROM folders`), no query per row; the test creates 200 folders with a member row for Dan and reads the page in under 2 seconds with a 1 second margin on loopback.

**Keyboard and labels**: the home page uses only `a`, `button`, `form`; every control has visible text or `aria-label`; `Folder 200` is reachable by `Tab` and opens with `Enter` (the folder page itself is US-0129, so the test asserts the focus order and the link `href`).

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/server.py` | modify | unavailable handling around dispatch, clock plumbing |
| `src/mcp_htmleditor/library/signin.py` | modify | expiry check, `purge` |
| `src/mcp_htmleditor/library/store.py` | modify | `connect_hook` seam |
| `src/mcp_htmleditor/library/pages.py` | modify | `library_unavailable` |
| `tests/library_support.py` | modify | restart helper, corrupt/restore database helper |
| `tests/test_library_sessions_http.py` | create | functional tests |

### Existing patterns

`tests/test_http_time_bounds.py` for tests that shorten bounds through module attributes; `fileio.py:44-46` for the failure seam pattern.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-008: A session of 29 days 23 hours is still valid after closing the browser

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_sessions_http.py`
- **Category:** happy
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005, FR-NEW-006, FR-NEW-015
- **Given** lamya.chrif@gmail.com signed in 29 days 23 hours ago and closed her browser.
- **When** She opens slides.scm-platform.org in a new browser window.
- **Then** The home page with "WCBIP Melbourne Décembre 2026" is shown without any Google step.
- **And** Her 30 day period still ends 1 hour from now, not later.
- **And** One hour later the same action sends her to the sign in page.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-012: The 30 day limit is exact and never extended by use

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_sessions_http.py`
- **Category:** edge (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005, FR-NEW-006
- **Given** dan.rw@example.org signed in 29 days 23 hours 59 minutes ago and used the library every day; carol.ro@example.org signed in 30 days 1 minute ago and used it yesterday.
- **When** Both open the home page.
- **Then** Dan sees his folders; Carol sees the sign in page.
- **And** One minute later Dan opens the home page again and sees the sign in page.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-016: The stored library cannot be read

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_sessions_http.py`
- **Category:** failure (side effect, state transition)
- **Scenario:** SC-003
- **Requirements:** FR-NEW-017, FR-NEW-060, FR-NEW-062
- **Given** dan.rw@example.org is signed in; the library holds 200 folders; the stored library cannot be read at this moment.
- **When** He opens the home page.
- **Then** "The library is unavailable. Try again later." is shown; no folder name and no partial list.
- **And** When the library can be read again, the home page lists "Cardiology 2027" and "Pneumo Été" with all their presentations intact.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-166: A signed in person stays signed in after a restart

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_sessions_http.py`
- **Category:** edge (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005, FR-NEW-062
- **Given** lamya.chrif@gmail.com signed in 10 days ago; the product restarts.
- **When** She opens the home page.
- **Then** "WCBIP Melbourne Décembre 2026" is listed with no Google step.
- **And** Her session still ends 20 days from now, not 30.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

A grep test over `src/mcp_htmleditor/library/*.py` asserting no `time.time(` outside `server.py`'s default argument, and no `UPDATE sessions`.

## Constraints

- No production code path reads the wall clock except through the injected clock.
- Do not extend `expires_at` anywhere, ever (a test greps `UPDATE sessions` in `library/`).
- Scope boundary: the editor's session notices (US-0137), the folder page (US-0129).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (clock, restart, unavailable seam), `.agent_docs/testing.md` (library suite, seams).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0128: Exact 30 day sessions, restarts, unavailable library, 200 folders` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
