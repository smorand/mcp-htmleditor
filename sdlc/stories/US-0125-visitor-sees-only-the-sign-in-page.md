# US-0125: A visitor sees only the sign in page

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0124
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

A visitor with no session sees nothing but the sign in page, whose only action is `Sign in with Google`, at every address of the library host name; the page is served through the secure address; the route table that authorizes every later route exists, with the roles and permissions.

## Requirements covered

- SPEC-0025/FR-NEW-001: The web library mode SHALL show a visitor who is not signed in nothing but the sign in page, whose only action is "Sign in with Google", except the liveness answer of FR-NEW-073.
  - Business rules: No folder name, presentation name, member, activity line, presentation file, download or export is available without signing in. The rule holds for every other address of the web library mode, not only the home page, and for the presentations' own files; an address that names no page also gives the sign in page.
- SPEC-0025/FR-NEW-057: The web library mode SHALL be reached at the address slides.scm-platform.org through a secure connection.
  - Business rules: The address is imposed by the owner (Section 3.3).
- SPEC-0025/FR-NEW-072 (partial: the sign in page cannot be shown inside a page of another site): The web library mode SHALL NOT accept a session after its person signed out, and SHALL NOT let any library page be shown inside a page of another site.
  - Business rules: A copy of the credentials of a session made before "Sign out" is refused after it, as for a visitor who is not signed in. The refusal of framing applies to every page, including the sign in page.

## Independent Test

Run `make test ARGS='-k library_visitor'`. The assertion that is not a mock: for each of the addresses `/`, `/f/x`, `/open/x`, `/admin`, `/static/editor.js`, `/lib/anything`, `/api/folders` the body equals the exact sign in page bytes built by `pages.sign_in_page` for that path (`==`), and contains no folder or presentation word.

## Design excerpt

### Decisions

- DEC-006 (SPEC-0025): The administrator address is the constant `ADMIN_EMAIL = "seb.morand@gmail.com"` in `library/access.py`, compared after lower casing; it is not a setting, not a table value and not read from the member lists. Obliged by: SPEC-0025/FR-NEW-011, SPEC-0025/FR-NEW-012.
- DEC-009 (SPEC-0025): Every library and shell response carries `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, a `Content-Security-Policy` and, when the origin scheme is https, `Strict-Transport-Security: max-age=31536000`; library pages use `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`, JSON answers `default-src 'none'; frame-ancestors 'none'`, the editor shell `frame-ancestors 'none'`, and the deck frame answer `frame-ancestors 'self'` with `X-Frame-Options: SAMEORIGIN`. `library.js` handles `pageshow` with `persisted` by reloading. Obliged by: SPEC-0025/FR-NEW-072, SPEC-0025/FR-NEW-008, SPEC-0025/FR-NEW-001.
- DEC-011 (SPEC-0025): A request with no valid session and no grant gets the sign in page (`200`, one link `Sign in with Google`, the requested path kept in the link as `next`) at every library origin address, and a `302` to the library origin on the content origin; the only public files are `/lib/library.css` and `/lib/library.js` on the library origin and the editor's `/static/*` files on the content origin (product code, no library content). Obliged by: SPEC-0025/FR-NEW-001, SPEC-0025/FR-NEW-009.
- DEC-014 (SPEC-0025): The post sign in destination is taken from `next`, stored server side in the attempt and accepted only when it matches `^/[A-Za-z0-9._~/%-]*$`, does not start with `//` or `/\`, and has no `\`, `:` or control character; any other value becomes `/`. Obliged by: SPEC-0025/FR-NEW-069.
- DEC-021 (SPEC-0025): `access.ROUTES` is a table `(origin, method, pattern, permission, handler)`; `LibraryHandler` finds the route, resolves the person (session, or grant on the content origin), computes the role for the route's target and calls `authorize(role, permission)` before any body is read and before the handler runs; a path in no row is "Access denied." for a signed in person and the sign in page for a visitor. A test walks the table and fails for a row without a permission. Obliged by: SPEC-0025/FR-NEW-001, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-020, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-023.
- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-029 (SPEC-0025): Names go through `library/names.py`: `compose` (NFC), `name_key` (NFC of the lower cased composed text), `order_key` (accents removed by NFD and dropping `Mn`, lower case, then the exact name); file names are an allow list (Latin script letters by `unicodedata.name` starting with `LATIN`, `Mn` only after such a letter, ASCII digits, space, `. _ - ( ) '`), at most 100 composed characters before `.html`, no leading dot, no edge space, not only spaces; folder names are letters of any script (`L*`), `M*`, decimal digits (`Nd`), space and hyphen, 1 to 60 composed characters after trimming; addresses match `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` after trimming and are stored lower case. All pages build text through `pages.esc()` (`html.escape(quote=True)`), and JavaScript writes with `textContent`. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-042, SPEC-0025/FR-NEW-046, SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-033.
- DEC-055 (SPEC-0025): Every page, message and control the mode adds is an English constant in `library/pages.py` (the exact texts are the ones quoted in the requirements and tests of each story); `static/editor-library.js` adds only `Access denied.` and `Your session has expired. Sign in again to save.`; the editor's own labels, notices and the presentations keep their texts, French ones included. Obliged by: SPEC-0025/FR-NEW-065.

### Data model

None in this story.

### Contracts

**Pages** (`library/pages.py`, new): `esc(text: str) -> str` is `html.escape(text, quote=True)`; every dynamic string of every page goes through it (FR-NEW-053). `sign_in_page(destination: str, message: str | None) -> bytes`: `200 text/html; charset=utf-8`, exactly one `<a href="/auth/start?next=<destination>">Sign in with Google</a>` (the link works from US-0126), a `<title>` and an `<h1>` that carry the product name only, no folder or presentation word; `message` is rendered in a `<p role="alert">` when given (used from US-0126). `access_denied() -> bytes` (`403`, `<p>Access denied.</p>` and the `Sign out` form posting to `/auth/logout`, nothing else; DEC-023) is defined here for the stories that need it. Every text is a constant in this module (DEC-055).

**Access control** (`library/access.py`, new): `ADMIN_EMAIL: Final = "seb.morand@gmail.com"` (DEC-006); `class Role(StrEnum): ADMIN = "Admin"; RW = "RW"; RO = "RO"`; `class Permission(Enum): PUBLIC, SIGNED_IN, VIEW, EDIT, ADMINISTER`; `authorize(role: Role | None, permission: Permission) -> bool` (`PUBLIC` always, `SIGNED_IN` for any session, `VIEW` for `RO`, `RW`, `ADMIN`, `EDIT` for `RW`, `ADMIN`, `ADMINISTER` for `ADMIN` only); `@dataclass(frozen=True, slots=True) class Route: origin: Literal["library", "content"]; method: str; pattern: re.Pattern[str]; permission: Permission; handler: str` (the handler is the name of a method of `LibraryHandler` or of a routes module function). Each routes module (`library/routes_*.py`) exports `ROUTES: tuple[Route, ...]`; `LibraryHandler` builds the table once by importing every module of the package whose name starts with `routes_` (`pkgutil.iter_modules`), so adding a routes module never edits `server.py` or `access.py` (DEC-021). A test fails when a `Route` has no `Permission`.

**Dispatcher** (`library/server.py`): after the gate of US-0124 the handler resolves the route; in this story there is no session, so every request of the library origin answers `pages.sign_in_page(destination=<request path, accepted by safe_destination or "/">, message=None)` with `200` (the requested path is an address, so the page is shown at that address and carries it as `next`; the content origin answers `302 <library origin>/` for every path, FR-NEW-001, DEC-011). The page response uses `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'` and every header of US-0124; library CSS and JavaScript files do not exist yet.

**Destination helper** (`library/signin.py` does not exist yet): in this story `server.py` holds `safe_destination(raw) -> str` (DEC-014: `^/[A-Za-z0-9._~/%-]*$`, not starting with `//` or `/\`, no `\`, `:` or control character, else `/`); US-0126 moves it into `signin.py` and re exports it.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/pages.py` | create | `esc`, `sign_in_page`, `access_denied`, text constants |
| `src/mcp_htmleditor/library/access.py` | create | `ADMIN_EMAIL`, `Role`, `Permission`, `Route`, `authorize` |
| `src/mcp_htmleditor/library/server.py` | modify | route table discovery, dispatcher, sign in page for every address, content origin redirect |
| `tests/library_support.py` | modify | page helpers |
| `tests/test_library_visitor_http.py` | create | functional tests |

### Existing patterns

`library/server.py` from US-0124 for the handler; `tests/test_library_gate_http.py` for the client helper; `tests/test_http_header_gate_e2e.py` for header assertions.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-004: A visitor who is signed out sees only the sign in action

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_visitor_http.py`
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-009, FR-NEW-020
- **Given** A visitor with no session.
- **When** The visitor opens the home page, the folder "Cardiology 2027" and the presentation "Heart Failure Update" by their direct links.
- **Then** Each time the sign in page is shown, with the single action "Sign in with Google".
- **And** None of the three pages shows a folder name, a presentation name, a member or a slide.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-134: The local mode and the web library mode run side by side

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_visitor_http.py`
- **Category:** failure
- **Scenario:** SC-021
- **Requirements:** FR-NEW-055, FR-NEW-056, FR-NEW-057
- **Given** The web library mode runs at slides.scm-platform.org; the local mode runs on talk.html at the machine's own address.
- **When** The operator edits talk.html in the local mode (the change is stored by itself), then opens the library.
- **Then** The library asks for a Google sign in and shows nothing of talk.html; the local mode never asked for a sign in.
- **And** The library's folders and presentations are unchanged.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-145: The address shows the sign in page securely

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_visitor_http.py`
- **Category:** happy
- **Scenario:** SC-023
- **Requirements:** FR-NEW-001, FR-NEW-057, FR-NEW-058, FR-NEW-059, FR-NEW-065
- **Given** A visitor with no session.
- **When** He opens slides.scm-platform.org through a secure connection.
- **Then** The sign in page is shown with the single action "Sign in with Google"; every text of the page is in English.
- **And** The browser shows no security warning.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the certificate and the secure connection are properties of nginx; the automated test proves the product side (the sign in page answers a request that carries `X-Forwarded-Proto: https` and the configured Host with no redirect); the runbook of US-0148 checks the browser's warning free connection.

### Story tests (not spec tests)

`tests/test_library_visitor_http.py` also holds: the route table test (every `Route` has a `Permission`, every routes module exports `ROUTES`), an `esc` unit test with a `<script>` string, and `authorize` unit tests for the five permissions against `None`, `RO`, `RW`, `ADMIN`.

## Constraints

- No cookie, no session, no database in this story.
- The sign in page is the only HTML the product serves to a visitor; assets of the page do not exist yet (the page is unstyled).
- Scope boundary: Google sign in (US-0126), the home page (US-0127).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (route table, visitor surface).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0125: A visitor sees only the sign in page` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
