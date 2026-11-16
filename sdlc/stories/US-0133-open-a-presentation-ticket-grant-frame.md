# US-0133: Open a presentation: ticket, grant, deck frame, status, HTML download

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0129, US-0131
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

A person with a role chooses a presentation and reaches it on the content origin through a one time ticket and a per presentation grant cookie: the deck frame, the status poll and the HTML download answer for that person only, every other request is redirected to the library sign in or refused with the identical `Access denied.`, and a session copied before sign out gets nothing.

## Requirements covered

- SPEC-0025/FR-NEW-022: WHILE a person holds RO in a folder THE web library mode SHALL let them open its presentations, show them full screen, open the presenter window with the speaker notes, and download each presentation as HTML and as PPTX.
  - Business rules: The downloaded HTML is the stored presentation unchanged, under its own name. Only the HTML and the PPTX downloads are offered; any other export format, DOCX included, is refused with "Access denied." for everyone.
- SPEC-0025/FR-NEW-001 (partial: download and status addresses of a presentation give the sign in page to a visitor and to a copied session): The web library mode SHALL show a visitor who is not signed in nothing but the sign in page, whose only action is "Sign in with Google", except the liveness answer of FR-NEW-073.
  - Business rules: No folder name, presentation name, member, activity line, presentation file, download or export is available without signing in. The rule holds for every other address of the web library mode, not only the home page, and for the presentations' own files; an address that names no page also gives the sign in page.
- SPEC-0025/FR-NEW-009 (partial: a signed out visitor who follows `/open/<id>` ends on the presentation after signing in when the account has a role, `Access denied.` otherwise): WHEN a signed out visitor opens a direct link to a folder or a presentation THE web library mode SHALL show the sign in page and, after a successful sign in, show the linked page when the account has a right on it and "Access denied." when it has none.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-010 (partial: a stale, missing or forbidden presentation link gives the identical `Access denied.` page): IF a link points to a folder or a presentation that does not exist, no longer exists, or belongs to a folder where the person holds no role THEN THE web library mode SHALL show exactly "Access denied." and nothing else.
  - Business rules: The page is identical in wording and content in the three cases; it shows the text "Access denied." and the "Sign out" button, nothing else: it never names the folder or the presentation and never says whether it exists. The same holds for an action refused for these reasons (storing a change, download, delete, upload). When the refusal reaches a presentation open for editing, the editor shows "Access denied." as its only notice (no "Save failed:" prefix) and keeps the unsaved changes on screen. An address of the product that names no page, asked by a signed in person, gives exactly "Access denied." with the "Sign out" button. A refused download or export shows "Access denied." as its only text, with no prefix such as "Export PPTX échoué :"; no file is received and the presentation stays on screen. When the session ended, the person gets the sign in page, unless they have unsaved text: then FR-NEW-007 applies and no download happens. Any other failure of a download or export shows the editor's usual failure notice with the operating system reason, without any file name or path, never the text of an exception.
- SPEC-0025/FR-NEW-020 (partial: no presentation of another folder is reachable by its address): The web library mode SHALL NOT reveal to a person the name, content, existence or member list of a folder where they hold no role, nor the email address of any other person.
  - Business rules: The administrator is excepted. The rule covers lists, messages, prompts and the activity list.
- SPEC-0025/FR-NEW-021 (partial: a role in one folder gives no right on a presentation of another): The web library mode SHALL NOT let a role held in one folder grant any right in another folder.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-023 (partial: read routes refuse a person with no role; write routes come with US-0136): The web library mode SHALL NOT let a person who holds only RO in a folder edit, upload or delete in it: the controls are absent and any attempt made outside the interface, including the storing of a change, is refused with "Access denied." and has no effect.
  - Business rules: Absent for RO: the Upload and Delete controls, edit mode, undo, redo, notes editing, requests, slide and block actions. The key E does nothing. Reading the queued requests and the AI suggestions of a presentation is refused with "Access denied." for a person who holds only RO.
- SPEC-0025/FR-NEW-025 (partial: the deck frame, status poll and HTML download work for a viewer): The web library mode SHALL give a person who can edit a presentation every option of the editor of the local mode, working as it does there.
  - Business rules: Options: edit mode, undo, redo, notes, presenter window, full screen, pointer, requests, Ask AI, HTML and PPTX download, keyboard shortcuts, help. A person who holds only RO gets the same screen without any control that changes the presentation (FR-NEW-023).
- SPEC-0025/FR-NEW-052 (partial: the deck is served on the content origin, which holds no library session): The web library mode SHALL NOT let a script contained in a presentation read what the browser keeps for the library, act with the identity of the person viewing it, or reach another folder.
  - Business rules: The scripts still run for the presentation itself (navigation, animations), as in the local mode.
- SPEC-0025/FR-NEW-072 (partial: grants die with the session at sign out): The web library mode SHALL NOT accept a session after its person signed out, and SHALL NOT let any library page be shown inside a page of another site.
  - Business rules: A copy of the credentials of a session made before "Sign out" is refused after it, as for a visitor who is not signed in. The refusal of framing applies to every page, including the sign in page.
- SPEC-0025/FR-NEW-073 (partial: the status of a presentation is shown only to a person with a right, without any storage location): The web library mode SHALL answer the check "is the product running" without sign in with only that fact and the product's version, and SHALL show the status of a presentation (its change marker) only to a person who has a right on it, without any storage location.
  - Business rules: The answer carries no file location, process number or presentation name. The operator's health check of the packaged product keeps working without sign in. A person with no right on a presentation, or a visitor, asking its status gets "Access denied." or the sign in page, never a status. The answer is the same whatever host name the request carries, loopback included.

## Independent Test

Run `make test ARGS='-k library_open'`. The tests sign in through the fake provider, follow `/open/<pid>` (a redirect to `/enter`, then to `/d/<pid>/`), and read `/d/<pid>/content-frame`, `/status`, `/download` with the cookies of different people. The assertion that is not a mock: the HTML downloaded through `/d/<pid>/download` equals the stored file byte for byte (`sha256`), and after `POST /auth/logout` the same download address with the copied cookies returns the sign in page and zero bytes of the deck.

## Design excerpt

### Decisions

- DEC-003 (SPEC-0025): Reuse the editor routes through five overridable methods of `_EditorHandler` (`_served_file`, `_served_name`, `_save_lock`, `_failure_reason`, `_pptx_options`; `_save_lock` returns a context manager, the local one is the existing `threading.Lock`), give `_EditorServer.__init__` a `handler` parameter defaulting to `_EditorHandler`, and implement the library as `LibraryHandler(_EditorHandler)` that overrides `do_GET`, `do_POST` and `_serve_status` only. The defaults reproduce the previous expressions byte for byte. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-055.
- DEC-007 (SPEC-0025): Serve two origins from one listener: the library origin (pages, API, session) and the content origin (the editor shell, the deck frame and the routes of one presentation); the `Host` header must equal the netloc of one of the two configured origins, otherwise `403 {"error": "forbidden host"}`. Obliged by: SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-059, SPEC-0025/FR-NEW-057.
- DEC-020 (SPEC-0025): Presentation and folder addresses carry random ids, never names: `/f/<folder id>`, `/open/<presentation id>`, `/d/<presentation id>/`; a "direct link" is one of these. Obliged by: SPEC-0025/FR-NEW-009, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-053.
- DEC-021 (SPEC-0025): `access.ROUTES` is a table `(origin, method, pattern, permission, handler)`; `LibraryHandler` finds the route, resolves the person (session, or grant on the content origin), computes the role for the route's target and calls `authorize(role, permission)` before any body is read and before the handler runs; a path in no row is "Access denied." for a signed in person and the sign in page for a visitor. A test walks the table and fails for a row without a permission. Obliged by: SPEC-0025/FR-NEW-001, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-020, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-023.
- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-025 (SPEC-0025): Metadata in one SQLite file (`<library_dir>/library.db`, WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one connection per thread, `BEGIN IMMEDIATE` for writes, migrations numbered by `PRAGMA user_version`); presentation bytes in files named by two random 32 hex ids (`files/<folder id>/<presentation id>.html`); ids validated against `^[0-9a-f]{32}$` before a path is built; names exist only as column values. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-063, SPEC-0025/FR-NEW-060.
- DEC-037 (SPEC-0025): Opening a presentation is a one time ticket then a grant: `GET /open/<pid>` (library origin, role >= RO) inserts a ticket (sha256 of a random token, 60 s, bound to the session and the presentation) and redirects to `<content origin>/enter?t=`; `/enter` deletes the ticket, inserts a grant (`token_hash`, `session_id_hash`, `presentation_id`) and sets the cookie `__Secure-d` (`d` on http) with `Path=/d/<pid>/` and no `Max-Age`. A grant is valid while its session is alive; when the session expired by time and the same address has a newer live session, the grant is rebound to it (only within 24 hours of expiry, rows purged after that); a grant whose session was ended by sign out is gone (cascade) and never revives. Answers: `Live(email)`, `Ended` (a cookie that no longer resolves: session expired, signed out, purged) and `Absent` (no cookie). Obliged by: SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-007, SPEC-0025/FR-NEW-072, SPEC-0025/FR-NEW-048.
- DEC-041 (SPEC-0025): The library `/d/<pid>/status` answers `{"mtime", "update_in_progress": false, "update_expires_in": null, "filename": "<name>.html", "poll_interval", "port": 0, "requests_revision"}`: no path, no process id, and only to a person with a right on the presentation; `requests_revision` is `0` for a role without `EDIT` so a read only editor never polls the refused request list. Obliged by: SPEC-0025/FR-NEW-073, SPEC-0025/FR-NEW-027.
- DEC-042 (SPEC-0025): Failures of a download or export in the library answer `{"error": <operating system reason>}` through `_failure_reason` (`exc.strerror`, else a fixed `Export failed`), never `str(exc)`. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-044 (SPEC-0025): Routes that must not exist in the library: DOCX export (`/d/<pid>/export/docx` is `Access denied.` for every role), the picture render, `new_file`, every MCP tool, `/arch-layout` on the library origin. Obliged by: SPEC-0025/FR-NEW-022, SPEC-0025/FR-NEW-052.

### Data model

Migration 4 (`store.py::MIGRATIONS[3]`):

```sql
CREATE TABLE tickets(ticket_hash TEXT PRIMARY KEY,
                     session_id_hash TEXT NOT NULL REFERENCES sessions(id_hash) ON DELETE CASCADE,
                     presentation_id TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE grants(token_hash TEXT PRIMARY KEY,
                    session_id_hash TEXT NOT NULL REFERENCES sessions(id_hash) ON DELETE CASCADE,
                    presentation_id TEXT NOT NULL, created_at REAL NOT NULL);
```

No foreign key from `grants` to `presentations`: a grant for a deleted presentation answers `Access denied.`. A ticket lives 60 seconds and is deleted when redeemed. A grant lives as long as its session; its cookie is a session cookie (no `Max-Age`), the server decides when it stops working.

### Contracts

**Hooks** in `_EditorHandler` (`http_server.py`), defaults reproduce the previous expressions exactly (DEC-003):

```python
def _served_file(self) -> str | None: return get_state().current_file
def _served_name(self) -> str: return Path(self._served_file() or "").name
def _save_lock(self) -> AbstractContextManager[object]: return get_state().save_lock
def _failure_reason(self, exc: Exception) -> str: return str(exc)
def _pptx_options(self) -> dict[str, bool]: return {}
```

Replace in `_serve_content` (`:376`), `_serve_content_frame` (`:389`), `_serve_download` (`:409`, name from `_served_name()`), `_export_pptx` (`:432`, `to_pptx(str(src), tmp_path, **self._pptx_options())`, stem from `_served_name()`), `_export_docx` (`:458`), `_loaded_file` (`:578`), `_receive_content` (`:625`, `with self._save_lock():`), `_run_arch_layout` (`:653`) every `get_state().current_file` and `state.current_file` by `self._served_file()`, every `state.save_lock` by `self._save_lock()`, and `str(exc)` in the three export and download failure answers by `self._failure_reason(exc)` (`:419-420`, `:448-450`, `:474-476`). The existing suites prove nothing changed.

**Accounts** (`library/signin.py`): `issue_ticket(session: Session, presentation_id: str) -> str` (inserts `sha256(token)`, returns the token); `redeem_ticket(ticket: str) -> NewGrant | None` (looks up, checks under 60 s, deletes the ticket, inserts a grant with a fresh 256 bit token, returns `(token, presentation_id, session_expires_at)`); `grant_for(presentation_id: str, token: str | None) -> GrantState` where `GrantState` is `Live(email)`, `Ended` (a cookie that no longer resolves) or `Absent` (no cookie); in this story a grant is `Live` while its session is alive, otherwise `Ended` (US-0137 adds the rebinding of a grant to a newer session). Cookie `d` (`__Secure-d` on https) with `Path=/d/<pid>/`, `HttpOnly`, `SameSite=Lax`, `Secure` on https, no `Max-Age`.

**Library origin route** `GET /open/<pid>` (`VIEW` on the presentation's folder, `Library.presentation(pid) -> PresentationRow | None`): allowed gives `302 <content origin>/enter?t=<ticket>`; anything else (malformed id, unknown id, no role) gives the `Access denied.` page; a visitor gets the sign in page with `next=/open/<pid>` (`safe_destination` accepts it).

**Content origin routes** (`library/routes_deck.py` exports `ROUTES` with these rows; the dispatcher resolves the cookie `d` of the request to `grant_for`, then `Library.presentation(pid)`, then `Library.role_in(email, folder_id)`, then `authorize(role, permission)`):

| Path | Permission | Behavior |
|---|---|---|
| `GET /enter?t=<ticket>` | `PUBLIC` | redeem; sets the grant cookie; `302 /d/<pid>/`; a bad ticket gives `302 <library origin>/` |
| `GET /d/<pid>/content-frame` | `VIEW` | `_serve_content_frame` with `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'` |
| `GET /d/<pid>/status` | `VIEW` | `{"mtime", "update_in_progress": false, "update_expires_in": null, "filename": "<name>.html", "poll_interval", "port": 0, "requests_revision"}` (`_serve_status` overridden, DEC-041); `requests_revision` is `0` for a role without `EDIT`, so the editor of a read only person never asks for the request list |
| `GET /d/<pid>/content`, `/download` | `VIEW` | inherited `_serve_content`, `_serve_download` (download name `<name>.html` from `_served_name()`, accents and apostrophes kept by `Content-Disposition` as `http_server.py:419-430` already encodes) |
| any other path under `/d/<pid>/` | | `403` `Access denied.` JSON |

Failures: a request that carries the header `X-Editor: 1` gets JSON, `403 {"error": "Access denied.", "code": "denied"}` when the person has no right or the presentation is unknown and `401 {"error": "Your session has expired. Sign in again to save.", "code": "session_expired"}` when the cookie is absent, ended or expired (what the editor shows for them is US-0137); a request without the header gets `403 {"error": "Access denied.", "code": "denied"}` when the grant is live and the role lacks the permission or the presentation is unknown (a hand made write or read), and `302 <library origin>/open/<pid>` when the grant is absent or ended or the route is a navigation route (`/d/<pid>/`, `/content-frame`, `/download`), which gives the sign in page to a visitor or a copied session and `Access denied.` to a person with no right. The status answer never contains a path, a process number or a folder name. The shell route `/d/<pid>/` comes with US-0134.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/http_server.py` | modify | the five hooks, nine call sites |
| `src/mcp_htmleditor/library/store.py` | modify | migration 4, `presentation(pid)` |
| `src/mcp_htmleditor/library/signin.py` | modify | tickets, grants, `grant_for` |
| `src/mcp_htmleditor/library/server.py` | modify | content origin dispatch, deck context, grant cookie |
| `src/mcp_htmleditor/library/routes_deck.py` | create | enter, frame, status, content, download |
| `src/mcp_htmleditor/library/routes_library.py` | modify | `/open/<pid>` |
| `tests/library_support.py` | modify | grant cookie helpers, `Person.open_presentation` |
| `tests/test_library_open_http.py` | create | functional tests and E2E-SEC-020, E2E-SEC-021 (`test_exploit_*`) |

### Existing patterns

`http_server.py:353-407` for how routes read and answer through `_send_bytes`, `_send_json`; `tests/conftest.py:245-270` for the server fixture; `tests/test_http_export.py` for download assertions.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-026: A direct link after signing in with an unauthorized account

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_open_http.py`
- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-003, FR-NEW-009, FR-NEW-010
- **Given** bob.nobody@gmail.com has no session and holds the link to "Heart Failure Update".
- **When** He opens the link and signs in with Google.
- **Then** "Access denied." is shown, with no slide and no folder name.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-035: A download keeps an accented name with an apostrophe

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_open_http.py`
- **Category:** edge
- **Scenario:** SC-005
- **Requirements:** FR-NEW-022, FR-NEW-053
- **Given** "Cardiology 2027" holds "L'été (v2)"; carol.ro@example.org is RO there.
- **When** She downloads its HTML.
- **Then** She receives a file named "L'été (v2).html".
- **Priority:** Low
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-102: A former member is refused after the folder is deleted

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_open_http.py`
- **Category:** failure (state transition)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-010, FR-NEW-043, FR-NEW-048
- **Given** "Pneumo Été" was deleted; dan.rw@example.org still had its folder page open.
- **When** He chooses a presentation of it.
- **Then** "Access denied." is shown.
- **And** His home page lists only "Cardiology 2027".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the folder id of the deleted folder no longer exists, so `/open/<presentation id>` of its former presentation is an unknown address and gives the identical `Access denied.` page (DEC-021, DEC-023).

### SPEC-0025/E2E-123: A presentation of another folder cannot be reached by typing its address

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_open_http.py`
- **Category:** failure
- **Scenario:** SC-018
- **Requirements:** FR-NEW-010, FR-NEW-020, FR-NEW-021
- **Given** dan.rw@example.org is RW in "Cardiology 2027" only; "Bridging the Gap" is in "WCBIP Melbourne Décembre 2026".
- **When** He types the address of "Bridging the Gap" in the folder "WCBIP Melbourne Décembre 2026", then the same presentation name under "Cardiology 2027".
- **Then** Both show "Access denied.", identical to each other.
- **And** No slide and no title of "Bridging the Gap" appears.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: a presentation address is `/open/<presentation id>`; the test types the id of the presentation of the other folder, not a name path (DEC-020).

### SPEC-0025/E2E-148: A plain direct link keeps its destination

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_open_http.py`
- **Category:** edge (state transition)
- **Scenario:** SC-023
- **Requirements:** FR-NEW-009, FR-NEW-058
- **Given** carol.ro@example.org has no session and opens the plain form of the link to "Heart Failure Update".
- **When** She follows it and signs in.
- **Then** She is sent to the secure form of the same link and, after signing in, sees "Heart Failure Update".
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-185: Signing out in one tab ends the session in the other tab

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_open_http.py`
- **Category:** edge (state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-008, FR-NEW-072
- **Given** carol.ro@example.org is signed in with two tabs of the folder page of "Cardiology 2027".
- **When** She chooses "Sign out" in the first tab, then chooses "Heart Failure Update" in the second.
- **Then** The second tab shows the sign in page, not the presentation.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-187: A presentation's status is shown only to a person with a right on it

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_open_http.py`
- **Category:** edge
- **Scenario:** SC-023
- **Requirements:** FR-NEW-010, FR-NEW-073
- **Given** carol.ro@example.org is RO in "Cardiology 2027" only.
- **When** She asks the status of "Heart Failure Update", then of "Bridging the Gap" in "WCBIP Melbourne Décembre 2026".
- **Then** The first status shows the change marker and no storage location; the second shows "Access denied."
- **And** A visitor with no session asking either gets the sign in page.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-020: A session copied before Sign out is used after it

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_open_http.py`
- **Category:** security
- **Covers:** Class G occurrence #8
- **Red before the fix because:** the copy is still accepted after Sign out; the assertion "the tool received no byte of Heart Failure Update" fails with 2 097 152 bytes.
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-008, FR-NEW-072
- **Given** carol.ro@example.org is signed in; the credentials of her session are copied by someone else; Carol then chooses "Sign out".
- **When** From a command line tool, the copy asks for "Heart Failure Update" and its HTML download.
- **Then** Each answer is the sign in page, never a file.
- **And** The tool received no byte of "Heart Failure Update".
- **And** Carol's browser still shows the sign in page; no session of hers appears anywhere.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-021: A visitor reads the liveness and status answers

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_open_http.py`
- **Category:** security
- **Covers:** Class B occurrences #3 and #7
- **Red before the fix because:** the liveness answer names the loaded file; the assertion "nothing received holds a file location or Heart Failure Update" fails and shows the path.
- **Scenario:** SC-023
- **Requirements:** FR-NEW-001, FR-NEW-010, FR-NEW-073
- **Given** A visitor with no session; the product holds "Heart Failure Update" in "Cardiology 2027".
- **When** He asks whether the product is running, then asks the status of "Heart Failure Update" in "Cardiology 2027".
- **Then** The first answer says the product is running and its version only; the second is the sign in page.
- **And** Nothing the visitor received holds a file location, a process number, "Heart Failure Update" or "Cardiology 2027".
- **And** The operator's health check, run afterwards, still succeeds.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

`tests/test_library_open_http.py` also holds a test that `LibraryHandler` never calls `_serve_deck_file`, and unit tests of `issue_ticket`, `redeem_ticket` (single use, 60 s) and `grant_for` with the `FakeClock`.

## Constraints

- Do not edit `editor.html`, any `editor*.js`, any template or `slide-layouts.js`.
- The grant cookie is `HttpOnly`; no response body, header or page contains a token other than `Set-Cookie`.
- Never call `_serve_deck_file` (SPEC-0023 does not apply to the library).
- Scope boundary: the editor shell (US-0134), read only controls (US-0135), storing changes (US-0136), notices for ended sessions (US-0137).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/architecture.md` (hooks), `.agent_docs/library.md` (ticket, grant, the two origins).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0133: Open a presentation: ticket, grant, deck frame, status, HTML download` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
