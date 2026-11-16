# US-0127: The home page: Admin role, order, empty states, uniform refusal

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0126
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

The home page becomes complete: the administrator address (any letter case) is Admin everywhere, sees every folder with the label `Admin` and the `Administration` entry, folders are ordered without regard to case or accents with digits before Latin letters before other alphabets, an empty home says so, any unknown address gives the same `Access denied.` page to a signed in person, and every dynamic text is escaped.

## Requirements covered

- SPEC-0025/FR-NEW-011: WHILE the signed in account is seb.morand@gmail.com (compared without regard to case) THE web library mode SHALL treat the person as Admin: every folder is accessible with every right of RW and the administration panel is available.
  - Business rules: The role label shown for the administrator is "Admin". The administration panel is reached by an entry labelled "Administration" on the home page.
- SPEC-0025/FR-NEW-012: The web library mode SHALL NOT give the Admin role to any account other than seb.morand@gmail.com, whatever the member lists contain.
  - Business rules: The roles that can be given to a member are RW and RO only.
- SPEC-0025/FR-NEW-014: The web library mode SHALL NOT refuse the administrator any action in any folder because of the content of the member lists.
  - Business rules: This holds even when the administrator's own address is listed in a folder with the role RO.
- SPEC-0025/FR-NEW-015: WHEN a signed in person opens the home page THE web library mode SHALL list the folders that person can access, all folders for the administrator, in alphabetical order without regard to case or accents, each with the person's role.
  - Business rules: Role labels: "Admin", "Read and write" (RW), "Read only" (RO). Order: accents removed, case ignored, compared by character code; so digits come before Latin letters, and Latin letters before other alphabets. Folder names are unique, so the order is never ambiguous.
- SPEC-0025/FR-NEW-016: IF the home page has no folder to list THEN THE web library mode SHALL show "You have no access to any folder yet."
  - Business rules: This happens to the administrator when no folder exists. A person who holds no role anywhere never reaches the home page: they see "Access denied." (FR-NEW-003).
- SPEC-0025/FR-NEW-053: The web library mode SHALL NOT interpret as markup any text a person or a file supplies (names, email addresses, check messages): it is shown exactly as written.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-065: The web library mode SHALL show every page, message and control that it adds in English, and SHALL show the editor and the presentations with the texts they have in the local mode.
  - Business rules: Added by the mode, in English: the sign in page, the home page, the folder page, upload, delete, the administration, the activity list and every refusal. Kept as in the local mode, not translated: the editor's toolbar labels (for example "Édition", "Annuler", "Rétablir", "Mode présentation plein écran", "Présenter avec le pointeur", "Vue présentateur", "Télécharger en PPTX", "Télécharger le fichier HTML", "Raccourcis clavier", and in English "Requests", "Ask AI", "Notes"), the editor's own notices and the text of the presentations.
- SPEC-0025/FR-NEW-010 (partial: an address that names no page, asked by a signed in person, gives exactly `Access denied.`; folders and presentations come with US-0129 and US-0133): IF a link points to a folder or a presentation that does not exist, no longer exists, or belongs to a folder where the person holds no role THEN THE web library mode SHALL show exactly "Access denied." and nothing else.
  - Business rules: The page is identical in wording and content in the three cases; it shows the text "Access denied." and the "Sign out" button, nothing else: it never names the folder or the presentation and never says whether it exists. The same holds for an action refused for these reasons (storing a change, download, delete, upload). When the refusal reaches a presentation open for editing, the editor shows "Access denied." as its only notice (no "Save failed:" prefix) and keeps the unsaved changes on screen. An address of the product that names no page, asked by a signed in person, gives exactly "Access denied." with the "Sign out" button. A refused download or export shows "Access denied." as its only text, with no prefix such as "Export PPTX échoué :"; no file is received and the presentation stays on screen. When the session ended, the person gets the sign in page, unless they have unsaved text: then FR-NEW-007 applies and no download happens. Any other failure of a download or export shows the editor's usual failure notice with the operating system reason, without any file name or path, never the text of an exception.

## Independent Test

Run `make test ARGS='-k "library_home or library_names"'`: a builder creates three folders and members, people sign in through `FakeGoogle`, and the pages are read. The assertion that is not a mock: the administrator who has no member row anywhere sees all three folders, a look alike address (`sebmorand@gmail.com`) sees `Access denied.` and no folder.

## Design excerpt

### Decisions

- DEC-018 (SPEC-0025): Roles are never stored in a session or a grant: every request recomputes the role from `members` (and `ADMIN_EMAIL`), so a change applies to the next action. Obliged by: SPEC-0025/FR-NEW-048, SPEC-0025/FR-NEW-021.
- DEC-019 (SPEC-0025): Checks run in this order for a state changing API request: `Origin` (DEC-022), session, permission of the route (administrator first), then payload validation (role value, address, name). Obliged by: SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-012, SPEC-0025/FR-NEW-014.
- DEC-021 (SPEC-0025): `access.ROUTES` is a table `(origin, method, pattern, permission, handler)`; `LibraryHandler` finds the route, resolves the person (session, or grant on the content origin), computes the role for the route's target and calls `authorize(role, permission)` before any body is read and before the handler runs; a path in no row is "Access denied." for a signed in person and the sign in page for a visitor. A test walks the table and fails for a row without a permission. Obliged by: SPEC-0025/FR-NEW-001, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-020, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-023.
- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-029 (SPEC-0025): Names go through `library/names.py`: `compose` (NFC), `name_key` (NFC of the lower cased composed text), `order_key` (accents removed by NFD and dropping `Mn`, lower case, then the exact name); file names are an allow list (Latin script letters by `unicodedata.name` starting with `LATIN`, `Mn` only after such a letter, ASCII digits, space, `. _ - ( ) '`), at most 100 composed characters before `.html`, no leading dot, no edge space, not only spaces; folder names are letters of any script (`L*`), `M*`, decimal digits (`Nd`), space and hyphen, 1 to 60 composed characters after trimming; addresses match `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` after trimming and are stored lower case. All pages build text through `pages.esc()` (`html.escape(quote=True)`), and JavaScript writes with `textContent`. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-042, SPEC-0025/FR-NEW-046, SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-033.
- DEC-053 (SPEC-0025): Library pages use plain HTML controls (`a`, `button`, `form`, `label`, `input`, `select`, `<dialog>` for the questions) with a visible text or an `aria-label` on every control, no click handler on a non focusable element, and `library.js` moves focus into a dialog when it opens and back to the control when it closes. Obliged by: SPEC-0025/FR-NEW-064.
- DEC-055 (SPEC-0025): Every page, message and control the mode adds is an English constant in `library/pages.py` (the exact texts are the ones quoted in the requirements and tests of each story); `static/editor-library.js` adds only `Access denied.` and `Your session has expired. Sign in again to save.`; the editor's own labels, notices and the presentations keep their texts, French ones included. Obliged by: SPEC-0025/FR-NEW-065.

### Data model

No change (migration 1 holds `folders` and `members`).

### Contracts

**Roles** (`library/access.py` already holds `ADMIN_EMAIL`, `Role`, `Permission` and `authorize` since US-0125): `Library.role_in(email: str, folder_id: str) -> Role | None` in `store.py` lower cases `email`, returns `Role.ADMIN` first when it equals `ADMIN_EMAIL` (whatever the member rows hold), else the member row, else `None`. A look alike address is a different address: no `strip` beyond normalization, no `googlemail.com` rewriting, no dot removal.

**Home page** (`pages.home_page(folders, is_admin)`): the folders of `Library.folders_for(email)` (all folders for the administrator, each with role text `Admin`; other people only their member rows with `Read and write` or `Read only`) ordered by `names.order_key(name)`; the `Administration` link `<a href="/admin">Administration</a>` only when `is_admin`; the `Sign out` form; an empty list shows `You have no access to any folder yet.` (reachable only by the administrator, since a person with no role gets the `Access denied.` page, FR-NEW-016). `/admin` has no route yet (the catch all gives `Access denied.`); US-0130 adds it.

**Unknown address** for a signed in person: `403`, `pages.access_denied()` (the same bytes as every refusal, DEC-023). For a visitor: the sign in page (US-0124).

**Names** (`library/names.py`, new): `compose(text) -> str` (`unicodedata.normalize("NFC", text)`); `name_key(name) -> str` (`compose(compose(name).lower())`); `order_key(name) -> tuple[str, str]` (`(compose of accent stripped lower name, name)` where accents are removed by NFD and dropping category `Mn`, compared by code point so digits sort before Latin letters before other alphabets); `esc` stays in `pages.py`.

**CSS** (`static/library.css`, served only from US-0129 on the public path `/lib/library.css`; in this story the file is created and linked from the pages with `<link rel="stylesheet" href="/lib/library.css">`; the route row `GET /lib/library.css` and `GET /lib/library.js` (library origin, `PUBLIC`) is added here and serves the two files of `static/` by base name with the media types `text/css` and `application/javascript`, 404 JSON for anything else). A visitor requesting `/lib/anything-else` gets the sign in page (FR-NEW-001).

Text is English only (FR-NEW-065): every string of the pages is a constant in `pages.py`.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/names.py` | create | `compose`, `name_key`, `order_key` |
| `src/mcp_htmleditor/library/store.py` | modify | `role_in`, administrator sees all folders |
| `src/mcp_htmleditor/library/pages.py` | modify | home page complete, constants |
| `src/mcp_htmleditor/library/routes_library.py` | modify | `/lib/*` assets row, catch all |
| `src/mcp_htmleditor/static/library.css` | create | page style (plain, readable, RTL safe: no fixed left or right alignment of names) |
| `tests/library_support.py` | modify | builder helpers for several folders |
| `tests/test_library_home_http.py` | create | functional tests |
| `tests/test_library_names.py` | create | unit tests of `names.py` |

### Existing patterns

`library/pages.py` from US-0126 for page construction and `esc`; `tests/test_library_auth_http.py` for the sign in helper of `library_support.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-014: The administrator sees every folder and the Administration entry

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_home_http.py`
- **Category:** happy
- **Scenario:** SC-003
- **Requirements:** FR-NEW-011, FR-NEW-012, FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-017, FR-NEW-020, FR-NEW-060
- **Given** The standard library; seb.morand@gmail.com has no member entry anywhere.
- **When** He signs in and opens the home page.
- **Then** Three folders are listed in this order: "Cardiology 2027", "Pneumo Été", "WCBIP Melbourne Décembre 2026", each labelled "Admin"; "Administration" and "Sign out" are shown.
- **And** carol.ro@example.org, on the same moment, sees only "Cardiology 2027" labelled "Read only".
- **And** The page is ready within 2 seconds, with no "The library is unavailable. Try again later." and no "You have no access to any folder yet."
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-018: Folders are ordered without regard to case or accents

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_home_http.py`
- **Category:** edge
- **Scenario:** SC-003
- **Requirements:** FR-NEW-015, FR-NEW-065
- **Given** The administrator, and folders "zeta", "Éclair Study", "Cardiology 2027", "alpha trial", "Pneumo Été".
- **When** He opens the home page.
- **Then** The order is "alpha trial", "Cardiology 2027", "Éclair Study", "Pneumo Été", "zeta".
- **And** Every label and message that the mode adds on the page is in English.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-087: The administrator address is compared without regard to case

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_home_http.py`
- **Category:** edge
- **Scenario:** SC-013
- **Requirements:** FR-NEW-002, FR-NEW-011
- **Given** Google returns the account as "Seb.Morand@Gmail.com".
- **When** He signs in.
- **Then** He is the administrator: "Administration" is shown and all 3 folders are listed with "Admin".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-149: Any other page gives the sign in page when signed out and Access denied when signed in

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_home_http.py`
- **Category:** edge
- **Scenario:** SC-023
- **Requirements:** FR-NEW-001, FR-NEW-010, FR-NEW-013, FR-NEW-057
- **Given** A visitor with no session.
- **When** He opens two addresses of the site that name no page: one made up, and one reading "admin".
- **Then** Each shows the sign in page, no different from the home address.
- **And** After dan.rw@example.org signs in, the same two addresses each show exactly "Access denied." with the "Sign out" button and nothing else.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-165: Folders are ordered digits, Latin letters, other alphabets

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_home_http.py`
- **Category:** edge
- **Scenario:** SC-003
- **Requirements:** FR-NEW-015
- **Given** The administrator, and folders "Кардиология", "Zeta", "Éclair", "2027 Review", "alpha", "Été".
- **When** He opens the home page.
- **Then** The order is "2027 Review", "alpha", "Éclair", "Été", "Zeta", "Кардиология".
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

`tests/test_library_names.py`: `order_key` on digits, Latin, accents, Cyrillic, Arabic, Chinese; `name_key` of composed and decomposed `Café`; a property style loop of 100 random names checking `name_key(name) == name_key(compose(name))`.

## Constraints

- The administrator is decided by `role_in` only; no other module compares against the address.
- No `casefold`, no `strip` on the address beyond the `.strip().lower()` of normalization.
- Scope boundary: Administration page (US-0130), folder page (US-0129).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (roles, order rule, the constant).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0127: The home page: Admin role, order, empty states, uniform refusal` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
