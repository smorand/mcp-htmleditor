# US-0126: Sign in with a Google account, stay signed in, sign out

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0125
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

A visitor chooses `Sign in with Google`, completes the sign in at a fake or real Google, and lands on a home page that lists the folders where their address holds a role; an account with no role sees `Access denied.` and `Sign out`. The sign in is the OpenID Connect code flow with state, nonce, PKCE, a browser binding and a verified address check; sessions are server side rows; sign out ends the session.

## Requirements covered

- SPEC-0025/FR-NEW-002: WHEN a visitor chooses "Sign in with Google" and completes the Google sign in with an account that is the administrator or holds a role in at least one folder THE web library mode SHALL show the home page of that account.
  - Business rules: The account is identified by its email address, compared without regard to upper or lower case. The product never asks for a password of its own. When the visitor cancels the consent asked by Google, the sign in page is shown again, still signed out, with no message. Every sign in asks Google to show its account chooser, so that a browser already signed in to one Google account can pick another.
- SPEC-0025/FR-NEW-003: IF the Google account that completed the sign in is not the administrator and holds no role in any folder THEN THE web library mode SHALL show "Access denied." and no library content.
  - Business rules: The page offers "Sign out". When the administrator later gives that account a role, the person sees the library on the next page they open, without signing in again.
- SPEC-0025/FR-NEW-004: IF Google cannot be reached or reports a failure during the sign in THEN THE web library mode SHALL show "Sign-in is unavailable. Try again later." on the sign in page and keep the visitor signed out.
  - Business rules: The visitor can try again as soon as Google answers.
- SPEC-0025/FR-NEW-008: WHEN a person chooses "Sign out" THE web library mode SHALL end their session in that browser and show the sign in page.
  - Business rules: The "Sign out" button is on the home page, the folder page and the refusal page; the administration page shows "All folders" and "Sign out"; the presentation page adds no control of its own, the person returns with the Back button of the browser. After signing out no library content is shown again in that browser until a new sign in, including through the Back button of the browser. Other browsers where the person is signed in stay signed in.
- SPEC-0025/FR-NEW-068: IF Google does not state that the email address of the account is verified THEN THE web library mode SHALL show "Sign-in is unavailable. Try again later." and keep the visitor signed out.
  - Business rules: The message is the same whether or not the address is listed anywhere, so that it reveals nothing about members. A verified address is accepted whatever its letter case.
- SPEC-0025/FR-NEW-069: WHEN a visitor signs in through a link that carries a destination THE web library mode SHALL send them to that destination only when it is a page of slides.scm-platform.org, and to the home page otherwise.
  - Business rules: A destination naming another site, written with another scheme, or starting with two slashes or a backslash is ignored. A destination of the product on which the account has no right gives "Access denied." (FR-NEW-009).
- SPEC-0025/FR-NEW-071: IF a sign in answer does not belong to a sign in that this browser started, or was already used, THEN THE web library mode SHALL show "Sign-in is unavailable. Try again later." and keep the visitor signed out.
  - Business rules: The visitor can start a new sign in at once.
- SPEC-0025/FR-NEW-009 (partial: a signed out visitor who follows a link ends on the linked page after signing in; the home page and the sign in page are covered here, folder and presentation links come with US-0129 and US-0133): WHEN a signed out visitor opens a direct link to a folder or a presentation THE web library mode SHALL show the sign in page and, after a successful sign in, show the linked page when the account has a right on it and "Access denied." when it has none.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-015 (partial: a minimal home page that lists the person's folders with `Read and write` or `Read only`; the order rule, the Admin label and the empty message come in US-0127): WHEN a signed in person opens the home page THE web library mode SHALL list the folders that person can access, all folders for the administrator, in alphabetical order without regard to case or accents, each with the person's role.
  - Business rules: Role labels: "Admin", "Read and write" (RW), "Read only" (RO). Order: accents removed, case ignored, compared by character code; so digits come before Latin letters, and Latin letters before other alphabets. Folder names are unique, so the order is never ambiguous.
- SPEC-0025/FR-NEW-072 (partial: a session is refused after sign out (session rows deleted); framing of folder pages is US-0129): The web library mode SHALL NOT accept a session after its person signed out, and SHALL NOT let any library page be shown inside a page of another site.
  - Business rules: A copy of the credentials of a session made before "Sign out" is refused after it, as for a visitor who is not signed in. The refusal of framing applies to every page, including the sign in page.

## Independent Test

Run `make test ARGS='-k "library_auth"'`. The tests start `FakeGoogle` (a loopback server with `/authorize` and `/token`) and point a temporary credentials file at it; a person signs in, sees the folder list, signs out, and the old cookie is refused. The assertion that is not a mock: after sign out a request that replays the copied session cookie gets the sign in page and the sessions table (read directly) holds no row.

## Design excerpt

### Decisions

- DEC-012 (SPEC-0025): Sign in is the OpenID Connect authorization code flow with PKCE (`S256`), scopes `openid email`, `prompt=select_account`, `state` and `nonce`, the code exchanged by `urllib.request` at `token_uri` with the client secret; the ID token received from that exchange is decoded (no signature verification) and accepted only when `iss` is `accounts.google.com` or `https://accounts.google.com`, `aud` equals the client id, `exp` is in the future, `nonce` equals the attempt's, `email_verified` is true and `email` is present; the address is lower cased once. Obliged by: SPEC-0025/FR-NEW-002, SPEC-0025/FR-NEW-068, SPEC-0025/FR-NEW-071.
- DEC-013 (SPEC-0025): A login attempt is a row (`state_hash`, `nonce`, `verifier`, `destination`, `browser_hash`, `created_at`); `/auth/start` sets the cookie `lib-b` (a random browser id) when absent and stores `sha256(browser id)`; the callback accepts an answer only when the `state` hash exists, the attempt is under 10 minutes old and its `browser_hash` equals the hash of the cookie, and deletes the row first (single use). Obliged by: SPEC-0025/FR-NEW-071, SPEC-0025/FR-NEW-002.
- DEC-014 (SPEC-0025): The post sign in destination is taken from `next`, stored server side in the attempt and accepted only when it matches `^/[A-Za-z0-9._~/%-]*$`, does not start with `//` or `/\`, and has no `\`, `:` or control character; any other value becomes `/`. Obliged by: SPEC-0025/FR-NEW-069.
- DEC-015 (SPEC-0025): `library/signin.py` reads the operator's credentials file named by `Settings.google_credentials_file` (`{"web": {"client_id", "client_secret", "auth_uri", "token_uri", "redirect_uris"}}`), nowhere else; the redirect URI sent to Google is `<library origin>/auth/callback`; at start `webserve` logs a warning when that address is not in `redirect_uris` and an error when the file is missing, and still starts. Obliged by: SPEC-0025/FR-NEW-004, spec section 3.3 (dependency, EXC-023c).
- DEC-016 (SPEC-0025): Any failure of the exchange (network, non 200, bad JSON, failed validation, unverified address, unknown or reused `state`, wrong browser id) shows `Sign-in is unavailable. Try again later.` on the sign in page and creates no session; `error=access_denied` (consent cancelled) shows the sign in page with no message; the token request timeout is 10 seconds. Obliged by: SPEC-0025/FR-NEW-004, SPEC-0025/FR-NEW-002, SPEC-0025/FR-NEW-068, SPEC-0025/FR-NEW-071.
- DEC-017 (SPEC-0025): A session is a row (`id_hash` = sha256 of a 256 bit token, `email`, `created_at`, `expires_at = created_at + 2 592 000 s`), the cookie is `__Host-lib` (`lib` on http) with `HttpOnly`, `SameSite=Lax`, `Secure` on https, `Max-Age=2592000`; `expires_at` is never updated; a request is signed in only while `now < expires_at`; sign out deletes the row. Obliged by: SPEC-0025/FR-NEW-005, SPEC-0025/FR-NEW-006, SPEC-0025/FR-NEW-008, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-072.
- DEC-020 (SPEC-0025): Presentation and folder addresses carry random ids, never names: `/f/<folder id>`, `/open/<presentation id>`, `/d/<presentation id>/`; a "direct link" is one of these. Obliged by: SPEC-0025/FR-NEW-009, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-053.
- DEC-021 (SPEC-0025): `access.ROUTES` is a table `(origin, method, pattern, permission, handler)`; `LibraryHandler` finds the route, resolves the person (session, or grant on the content origin), computes the role for the route's target and calls `authorize(role, permission)` before any body is read and before the handler runs; a path in no row is "Access denied." for a signed in person and the sign in page for a visitor. A test walks the table and fails for a row without a permission. Obliged by: SPEC-0025/FR-NEW-001, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-020, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-023.
- DEC-022 (SPEC-0025): Every state changing request (any method other than `GET`, `HEAD` and `OPTIONS`: `POST` and `DELETE`) is refused with `Access denied.`, before the session is looked up, unless `Origin` is present and equals the origin of the receiving host exactly, and `Sec-Fetch-Site`, when present, is `same-origin` (or `none`); JSON routes also require `Content-Type: application/json`, the upload requires the header `X-File-Name`. The local rule that accepts a missing `Origin` is not used. Obliged by: SPEC-0025/FR-NEW-070, SPEC-0025/FR-NEW-023.
- DEC-025 (SPEC-0025): Metadata in one SQLite file (`<library_dir>/library.db`, WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one connection per thread, `BEGIN IMMEDIATE` for writes, migrations numbered by `PRAGMA user_version`); presentation bytes in files named by two random 32 hex ids (`files/<folder id>/<presentation id>.html`); ids validated against `^[0-9a-f]{32}$` before a path is built; names exist only as column values. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-063, SPEC-0025/FR-NEW-060.
- DEC-032 (SPEC-0025): Time and faults are injected, not patched globally: `LibraryServer(clock=time.time)` hands the clock to every repository; the test seams are `Database.connect` (raise `sqlite3.OperationalError` to simulate an unreadable library), `fileio.replace_file` (`fileio.py:44-46`, already the documented failure seam, raise `OSError(errno.ENOSPC)`), and a socket wrapper in tests that cuts a connection at a byte count. Obliged by: SPEC-0025/FR-NEW-005, SPEC-0025/FR-NEW-006, SPEC-0025/FR-NEW-017, SPEC-0025/FR-NEW-038.
- DEC-048 (SPEC-0025): Logging and tracing follow the project rules: `logger = logging.getLogger(__name__)`, `%` formatting, stderr console, `click.echo` only for the start line; spans `auth.google_token`, `library.upload`, `library.replace`, `library.delete_presentation`, `library.delete_folder`, `library.seed`, `session.create`, with sizes and status codes only; no email, name, token, cookie or credential in a log line or an attribute. Obliged by: SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-020 (nothing about members leaks), AGENTS.md observability rules.

### Data model

Migration 1 (`library/store.py::MIGRATIONS[0]`, applied when `PRAGMA user_version` is 0, then `user_version = 1`):

```sql
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE folders(id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE, created_at REAL NOT NULL);
CREATE TABLE members(folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE, email TEXT NOT NULL,
                     role TEXT NOT NULL CHECK (role IN ('RW','RO')), PRIMARY KEY (folder_id, email));
CREATE INDEX members_email ON members(email);
CREATE TABLE logins(state_hash TEXT PRIMARY KEY, nonce TEXT NOT NULL, verifier TEXT NOT NULL, destination TEXT NOT NULL,
                    browser_hash TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE sessions(id_hash TEXT PRIMARY KEY, email TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL);
```

`expires_at = created_at + 2_592_000` (30 days exactly), written once, never updated. Hashes are `hashlib.sha256(token.encode()).hexdigest()`.

### Contracts

**Settings** (`config.py`): `google_credentials_override: Path | None = Field(default=None, validation_alias="HTMLEDITOR_GOOGLE_CREDENTIALS_FILE")` (added to `_PATH_FIELDS` and `_SIGNIFICANT_ENV_VARS`) and property `google_credentials_file -> Path | None`. The file is `{"web": {"client_id", "client_secret", "auth_uri", "token_uri", "redirect_uris"}}`; only `library/signin.py` opens it.

**Database** (`library/store.py`, the same module as the `Library` repository): `Database(path: Path)`; `connection() -> sqlite3.Connection` (one per thread via `threading.local`, `isolation_level=None`, `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=30000`, file created `0600`, directory `0700`); `@contextmanager transaction(*, immediate: bool = False)` (`BEGIN IMMEDIATE` when asked, commit or rollback); `MIGRATIONS: tuple[str, ...]` applied in order by `migrate()` at construction.

**Accounts** (`library/signin.py`): `GoogleClient(credentials_file: Path | None, redirect_uri: str, timeout: float = 10.0)` with `authorization_url(state, nonce, challenge) -> str` (`response_type=code`, `client_id`, `redirect_uri`, `scope=openid email`, `state`, `nonce`, `code_challenge`, `code_challenge_method=S256`, `prompt=select_account`) and `exchange(code, verifier) -> dict` (POST form to `token_uri` with `grant_type=authorization_code`, `code`, `client_id`, `client_secret`, `redirect_uri`, `code_verifier`, inside `trace_span("auth.google_token", {...})`, returns the decoded claims of `id_token`; raises `SignInUnavailable` on any network error, non 200, bad JSON). `validate_claims(claims, client_id, nonce, now) -> str` returns the lower case address or raises `SignInUnavailable` (`iss` in `{"accounts.google.com", "https://accounts.google.com"}`, `aud == client_id`, `exp > now`, `nonce` equal, `email_verified is True` (the string `"true"` also counts as true), `email` non empty). `safe_destination(raw: str | None) -> str` (DEC-014; the helper of US-0125 moves here from `server.py` and stays importable from there).

`Accounts(database, google, clock)`: `begin_login(browser_id: str | None, destination: str) -> tuple[str, str]` returns `(google_url, browser_id)` (creates `browser_id` with `secrets.token_urlsafe(16)` when `None`; stores the row; `state = secrets.token_urlsafe(24)`, `nonce = secrets.token_urlsafe(24)`, `verifier = secrets.token_urlsafe(48)`, `challenge = base64url(sha256(verifier))` without padding); `finish_login(state, code, browser_id) -> Session` (deletes the attempt row first, then checks age under 600 s and `sha256(browser_id) == browser_hash`, then `exchange` and `validate_claims`, then `INSERT` a session with a fresh 256 bit token) raising `SignInUnavailable`; `session_for(token) -> Session | None` (alive only: `now < expires_at`); `end_session(token) -> None`. `Session` is a frozen dataclass `(email, token_hash, created_at, expires_at)`; the raw token is returned only by `finish_login` through `NewSession(token, session)`.

**Cookies** (`library/server.py::cookie_name(origin, base)` and `cookie_header(...)`): `lib` and `lib-b` on http, `__Host-lib` and `__Host-lib-b` on https; attributes: `Path=/; HttpOnly; SameSite=Lax`, `Max-Age=2592000` for `lib`, no `Max-Age` (session cookie) for `lib-b`, and `Secure` when the origin scheme is https; a unit test builds the headers for an https origin.

**Routes** (`library/routes_library.py` exports `ROUTES: tuple[Route, ...]` (the `Route` type is `access.Route`) which `server.py` concatenates with the other route modules into the table; every handler receives a `Context(person_email | None, ...)` built by the dispatcher):

| Method path | Permission | Behavior |
|---|---|---|
| `GET /auth/start?next=` | `PUBLIC` | `begin_login`; `Set-Cookie lib-b` when new; `302` to the Google URL |
| `GET /auth/callback?code&state` | `PUBLIC` | `finish_login`; success sets the `lib` cookie, `303` to the stored destination; `?error=access_denied` gives the sign in page with no message; any other failure gives the sign in page with `Sign-in is unavailable. Try again later.` |
| `POST /auth/logout` | `SIGNED_IN` | needs the origin rule of DEC-022 (`LibraryHandler._origin_ok()`, defined below); deletes the session row, clears both cookies, `303 /` |
| `GET /` | `SIGNED_IN` | home page; an account with no role anywhere gets the `Access denied.` page |

**Origin rule** (`LibraryHandler._origin_ok()` in `server.py`, DEC-022), applied by the dispatcher to every request whose method is not `GET`, `HEAD` or `OPTIONS` (`POST`, `DELETE`), before the session lookup and before the handler runs: `Origin` present and equal to the origin of the receiving host (exact string compare of `scheme://host[:port]`), `Sec-Fetch-Site` absent or `same-origin` or `none`; routes that take JSON also need `Content-Type: application/json` (reuse `check_content_type`, `http_server.py:793-796`). Failure: `403` with the `Access denied.` page (HTML routes) or `403 {"ok": false, "error": "Access denied."}` (JSON routes) and nothing changes. The rule is written here because sign out is the first state changing route; later stories only add routes.

**Home page** (`pages.home_page(folders: list[FolderView]) -> bytes`): a list `<ul>` of links `<a href="/f/<id>">Name</a>` with the role text `Read and write` or `Read only`, a `Sign out` form (`<form method="post" action="/auth/logout"><button>Sign out</button></form>`). `Library.folders_for(email) -> list[FolderView]` returns folders where `members.email = ?`, ordered by name for now (the order rule arrives in US-0127). **Access denied page** `pages.access_denied()`: `403`, `<p>Access denied.</p>` and the `Sign out` form, nothing else (DEC-023).

**FakeGoogle** (`tests/library_support.py`): `FakeGoogle(accounts: dict)`; `GET /authorize` records the query, answers `302 <redirect_uri>?code=<c>&state=<state>` for the next scripted account, or `?error=access_denied` for a scripted cancel; `POST /token` verifies the PKCE verifier against the recorded challenge and answers `{"id_token": <unsigned JWT with the claims>}` or a scripted failure (HTTP 503, closed connection, `email_verified: false`); `received` lists every request for assertions such as `prompt=select_account`.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/config.py` | modify | credentials file field and property |
| `src/mcp_htmleditor/library/server.py` | modify | cookies, session lookup in the dispatcher, `Context` |
| `src/mcp_htmleditor/library/pages.py` | modify | home page, access denied page, message on the sign in page |
| `src/mcp_htmleditor/library/signin.py` | create | `GoogleClient`, `Accounts`, `validate_claims`, `safe_destination` |
| `src/mcp_htmleditor/library/store.py` | create | `Database`, `MIGRATIONS`, migration 1, `Library.folders_for`, `FolderView` |
| `src/mcp_htmleditor/library/routes_library.py` | create | auth routes and home |
| `tests/library_support.py` | modify | `FakeGoogle`, `LibraryBuilder.folder/member`, `StoredLibrary` |
| `tests/test_library_auth_http.py` | create | functional tests and E2E-SEC-015, 016, 019 (functions named `test_exploit_*`) |

### Existing patterns

`state.py:211-245` for atomic small file writes and private directory creation (mode 0700); `request_store.py:81-150` for a store class that takes its root in the constructor and keeps `trace_span` around mutations; `tracing.py:170` for `trace_span`; `http_server.py:215-262` for refusal helpers (`_refuse_request`, `_refuse`).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-003: Google cannot be reached

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002, FR-NEW-004
- **Given** A visitor with a Google account; Google does not answer.
- **When** The visitor chooses "Sign in with Google".
- **Then** The sign in page shows "Sign-in is unavailable. Try again later." and the visitor stays signed out.
- **And** When Google answers again, choosing "Sign in with Google" again signs lamya.chrif@gmail.com in.
- **And** The same message is shown when the Google console does not know the return address of slides.scm-platform.org (EXC-023c).
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-005: The visitor cancels the Google consent

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002
- **Given** A visitor on the Google consent screen for lamya.chrif@gmail.com.
- **When** The visitor cancels the consent.
- **Then** The sign in page is shown, signed out, without any message.
- **And** Choosing "Sign in with Google" again starts a fresh sign in that can succeed.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-007: A cancelled consent gives no access to a direct link

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-002, FR-NEW-009
- **Given** carol.ro@example.org holds the link to "Heart Failure Update" and has no session; she cancels the Google consent.
- **When** She then opens the link again.
- **Then** The sign in page is shown, not the presentation.
- **And** No folder name and no presentation name was shown at any step.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-090: An address that looks like the administrator's is not the administrator

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** failure
- **Scenario:** SC-013
- **Requirements:** FR-NEW-003, FR-NEW-011, FR-NEW-012
- **Given** Google accounts "sebmorand@gmail.com" and "seb.morand@googlemail.com", listed in no folder.
- **When** Each signs in.
- **Then** Each sees "Access denied."; neither sees "Administration" nor any folder.
- **And** The administrator's activity list and folder list are unchanged.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-150: Google reports a failure after the person chose an account

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** edge (state transition)
- **Scenario:** SC-023
- **Requirements:** FR-NEW-002, FR-NEW-004, FR-NEW-057
- **Given** The sign in return address of slides.scm-platform.org is not registered in the owner's Google console; a visitor has no session.
- **When** He chooses "Sign in with Google" and picks lamya.chrif@gmail.com.
- **Then** The sign in page is shown with "Sign-in is unavailable. Try again later." and he stays signed out.
- **And** After the owner registers the return address, the same steps sign him in and show "WCBIP Melbourne Décembre 2026".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-171: An unverified address of an unlisted account gives the same message

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-003, FR-NEW-068
- **Given** Google returns the account bob.nobody@gmail.com, who is in no list, with the address marked not verified; and lamya.chrif@gmail.com, who is listed, also marked not verified.
- **When** Each signs in.
- **Then** Both see "Sign-in is unavailable. Try again later." and stay signed out; neither sees "Access denied.".
- **And** After Google marks lamya.chrif@gmail.com verified she signs in normally.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-172: Destinations that leave the product are ignored

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-009, FR-NEW-069
- **Given** carol.ro@example.org has no session.
- **When** She opens the sign in link with the destinations //evil.example/x, \evil.example, javascript:alert(1), https://slides.scm-platform.org@evil.example/x, /\evil.example and "slides.scm-platform.org.evil.example" in turn, and signs in each time.
- **Then** Each time she arrives on the home page of slides.scm-platform.org with "Cardiology 2027" listed.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-183: Two sign ins started in two tabs each complete

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** happy (state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002, FR-NEW-071
- **Given** carol.ro@example.org has no session and starts a sign in in two tabs of the same browser.
- **When** She completes the sign in in the second tab, then in the first.
- **Then** Each tab ends on the home page listing "Cardiology 2027" with no "Sign-in is unavailable. Try again later."
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-184: A sign in answer cannot be used twice

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_auth_http.py`
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-071
- **Given** carol.ro@example.org signed in once; a copy of the address that carried the answer of that sign in is kept; she then signed out.
- **When** The copy is opened in her browser.
- **Then** "Sign-in is unavailable. Try again later." is shown and she stays signed out.
- **And** Opening the home page shows the sign in page.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-015: A Google account claiming the administrator address without verifying it

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_auth_http.py`
- **Category:** security
- **Covers:** Class E occurrence #1
- **Red before the fix because:** a build that trusts the claimed address signs the visitor in as the administrator; the assertion "the visitor sees the sign in page when opening Administration" fails and shows the administration with 3 folders.
- **Scenario:** SC-001
- **Requirements:** FR-NEW-011, FR-NEW-012, FR-NEW-068
- **Given** A Google account whose address reads seb.morand@gmail.com but which Google marks as not verified (the identity provider fixture returns that claim).
- **When** The visitor signs in with it.
- **Then** "Sign-in is unavailable. Try again later." is shown and the visitor stays signed out.
- **And** From the same browser, opening "Administration" and the home page shows the sign in page: no "Administration" entry, no folder.
- **And** The administrator's own session and activity list show no new line; the folder list is unchanged (3 folders).
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-016: A sign in link carrying a destination on another site

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_auth_http.py`
- **Category:** security
- **Covers:** Class F occurrence #1
- **Red before the fix because:** the browser is sent to https://evil.example/phish; the assertion "the listener of evil.example recorded 0 visits" fails with 1.
- **Scenario:** SC-001
- **Requirements:** FR-NEW-009, FR-NEW-069
- **Given** carol.ro@example.org has no session; a link to the sign in carries the destination https://evil.example/phish; the fixture runs a listener that records every visit to evil.example.
- **When** She follows the link and signs in with Google.
- **Then** She arrives on the home page of slides.scm-platform.org, listing "Cardiology 2027".
- **And** The listener of evil.example recorded 0 visits and the browser never left slides.scm-platform.org.
- **And** The same result with the destination //evil.example/phish.
- **And** The same result with the destinations javascript:alert(1), https://slides.scm-platform.org@evil.example/x and /\evil.example.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-019: A sign in answer made for someone else is planted in a visitor's browser

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_auth_http.py`
- **Category:** security
- **Covers:** Class G occurrence #7
- **Red before the fix because:** Carol's browser becomes signed in as dan.rw@example.org; the assertion "the home page shows the sign in page" fails and lists "Cardiology 2027".
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002, FR-NEW-020, FR-NEW-071
- **Given** A third party completed a Google sign in as dan.rw@example.org and kept the address carrying the answer; carol.ro@example.org's browser never started a sign in.
- **When** The third party makes Carol's browser open that address.
- **Then** "Sign-in is unavailable. Try again later." is shown and Carol stays signed out.
- **And** Carol's browser opening the home page shows the sign in page, not Dan's folders "Cardiology 2027" and "Pneumo Été".
- **And** The activity list shows no line.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

Unit tests in `tests/test_library_auth_http.py`: `validate_claims` rejects each missing or wrong claim (one parametrized case per claim), `safe_destination` accepts `/f/abc` and refuses the five payloads of E2E-SEC-016, `cookie_name` and `cookie_header` for an https origin, and a PKCE check (`challenge == base64url(sha256(verifier))`). The tests read the activity list through `StoredLibrary.activity()`, which returns an empty list while the `activity` table does not exist yet (it arrives with US-0130), and a browser Sign out click is proven by the folder page story; here the logout form is posted with the `Origin` header a browser sends under `Referrer-Policy: same-origin`.

## Constraints

- Reuse `urllib.request`; no `requests`, no `authlib`, no `google-auth`; the id token signature is not verified (DEC-012).
- Never log or trace an address, a token, the state, the nonce, the verifier or the client secret.
- The administrator concept (Admin label, all folders) is US-0127; here only members rows decide.
- Scope boundary: session lifetime tests with a moved clock (US-0128), the Administration page (US-0130), opening a presentation (US-0133).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (sign in flow, cookies, tables), `.agent_docs/observability.md` (span `auth.google_token`, `session.create`), `README.md` (credentials setting).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0126: Sign in with a Google account, stay signed in, sign out` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
