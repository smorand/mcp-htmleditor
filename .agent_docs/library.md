# Web library mode (SPEC-0025)

`mcp-htmleditor webserve [--host] [--port]`: one process for every folder and presentation of a private library,
behind nginx at `slides.scm-platform.org`. Spec and design: `sdlc/specs/SPEC-0025-web-library-mode/`. Stories
US-0124 to US-0149 land on `feat/0049-web-library-mode`; this file grows with each.

## Module map (`src/mcp_htmleditor/library/`)

| Module | Holds |
|---|---|
| `__init__.py` | package docstring |
| `pages.py` | `esc`, `sign_in_page(destination, message)`, `access_denied()`, `library_unavailable()`, `home_page(folders, is_admin=)`, every English text constant (DEC-055: `SIGN_IN_UNAVAILABLE`, `LIBRARY_UNAVAILABLE`, `ADMIN_LABEL`, `ADMINISTRATION_LABEL`, `NO_FOLDER_YET`, `ROLE_LABELS` keyed by `Role` value); every page links `/lib/library.css` |
| `names.py` | `compose` (NFC), `name_key` (NFC of lower of NFC, the unique `folders.name_key`), `order_key` (DEC-029) |
| `access.py` | `ADMIN_EMAIL`, `Role`, `Permission`, `authorize(role, permission)`, frozen `Route`, `Context`, `Answer`, `SetCookie` (DEC-021) |
| `store.py` | `Database(path)` (per thread connection, `transaction(immediate=)`, `release()`, `connect()`, test seam `Database.connect_hook`, `MIGRATIONS`), `Library` (`folders_for(email)`, `is_admin(email)`, `role_in(email, folder_id)`), `normalize_email`, `FolderView` |
| `signin.py` | `GoogleClient` (`authorization_url`, `exchange`), `read_credentials`, `validate_claims`, `safe_destination`, `Accounts` (`begin_login`, `finish_login`, `purge`, `session_for`, `end_session`), `Session`, `NewSession`, `SignInUnavailable`, cookie base names |
| `routes_library.py` | `ROUTES`: `GET /lib/library.css`, `GET /lib/library.js` (PUBLIC, `static_file`, `STATIC_DIR`), `GET /auth/start`, `GET /auth/callback` (PUBLIC), `POST /auth/logout`, `GET /` (SIGNED_IN) |
| `server.py` | `load_routes`, `cookie_name`, `cookie_header`, `parse_cookies`, `PAGE_POLICY`, `LibraryServer(_EditorServer)` (`start`, `stop`, `port`, `origin_for`, `find_route`, `is_secure`, `clock`, `database`, `library`, `accounts`), `LibraryHandler(_EditorHandler)` (gate, `_serve_library`, `_origin_ok`, `_send_answer`, `_send_common_headers`), `health_answer`, `LibraryConfigError`, `SAME_HOST_MESSAGE`; re-exports `safe_destination` |

A route handler is a plain function `(Context) -> Answer` (not a `LibraryHandler` method, so a `routes_*` module never
imports `server.py`: `server` loads the routes while it is itself being imported). The dispatcher writes the `Answer`
(status, `Location`, cookies turned into the origin's names, body; an HTML body gets `PAGE_POLICY`).

`_EditorServer.__init__(bind_host, port, handler=_EditorHandler)` is the only change to `http_server.py` (DEC-003);
`_EditorHandler` is subclassed, never edited (`test_the_editor_handler_is_unchanged...` pins its source hash; the
story that adds the DEC-003 hooks updates the hash in its own diff).

## Settings (DEC-005)

`library_origin` (`HTMLEDITOR_LIBRARY_ORIGIN`), `library_content_origin` (`HTMLEDITOR_LIBRARY_CONTENT_ORIGIN`),
`library_dir_override` (`HTMLEDITOR_LIBRARY_DIR`, property `library_dir`, default `<state_dir>/library`),
`google_credentials_override` (`HTMLEDITOR_GOOGLE_CREDENTIALS_FILE`, property `google_credentials_file`, default None). An origin
must be exactly `http(s)://host[:port]` (`config.is_origin`: no user, path, `/`, query or fragment, port in range,
no empty or default port, no trailing dot: the netloc is compared with `Host` as is); otherwise `Settings()` fails
with a message naming the variable, for every command since the click group builds the settings. The three names
are in `_SIGNIFICANT_ENV_VARS` (the credentials variable too). HSTS follows the library origin's scheme only (both origins are expected to share it).

## Gate order (every method, `LibraryHandler._dispatch`)

1. `_refuse_ambiguous_headers` (inherited): 400.
2. `GET /health` (also `/health/`), any host name, no host at all: `{"ok": true, "status": "ok", "version"}`.
3. Host gate: `Host` lower cased must equal the netloc of one origin (host and port), else
   `403 {"error": "forbidden host"}` and one `Refused <METHOD> <path>: forbidden host '<host>'` warning.
4. `X-Forwarded-Proto: http` (any case) while that origin is https: `308`, `Location` = configured origin + request
   path + query (never the request's `Host`, an absolute form target keeps only its path), empty body.
5. Content origin: `302` to `<library origin>/`. An unread body of a non GET closes the connection. Python's
   `BaseHTTPRequestHandler` already turns `//x` into `/x` in `self.path`.
6. Library origin, `_serve_library`: find the route (origin, method, `pattern.fullmatch(path)`); a matched route
   whose method is not `GET`/`HEAD`/`OPTIONS` needs `Origin` exactly equal to the library origin and
   `Sec-Fetch-Site` absent, `same-origin` or `none`, else `403` `Access denied.` page before the session is looked
   up (DEC-022). Then the session (cookie `lib`/`__Host-lib`, `Accounts.session_for`). No route, or a non PUBLIC route
   without a session: a visitor gets the sign in page (`200`, `next` = `safe_destination(path)`), a signed in person
   `403` `Access denied.`. Then the handler (the role check joins with the first route that names a target).
   The Origin rule applies to every non GET/HEAD/OPTIONS request before the route lookup (2026-11-16): a POST to a
   path in no row without the library `Origin` gets `Access denied.`; with it, the sign in page for a visitor.
   The token call uses an opener with no proxy and no redirect (`signin.py`).
   The JSON `Content-Type` part of DEC-022 arrives with the first JSON route (US-0130).
7. `_library_answer` (route, session, handler) runs inside `except (sqlite3.Error, OSError)`: `503`
   `pages.library_unavailable()` (`The library is unavailable. Try again later.`, no name, no list, no Sign out form),
   one ERROR line naming the exception type. Writing the answer is outside the guard (a closed socket is not the
   library). Nothing is cached: the next request opens a new connection and works as soon as the file is readable.

## Lifetime (US-0128, DEC-017, DEC-024, DEC-032)

- Clock: `LibraryServer(settings, clock=time.time)` hands `clock` to `Accounts`; no `library/` module reads the wall
  clock or contains `UPDATE sessions` (grep test). `Library` reads no time yet, so it takes no clock.
- A session is alive while `clock() < expires_at`; at `expires_at` exactly it is over. `expires_at` is written once.
  `Accounts.purge()` (called by `begin_login` and by `finish_login` after it took the attempt) deletes session rows
  ended more than 86 400 s ago (kept a day for US-0137) and attempts of 600 s or more. Tickets join it with US-0133.
- Restart: no state in memory; a new `LibraryServer` on the same `library_dir` serves the same sessions and folders.
- Unreadable library: tests set `Database.connect_hook` (class attribute, called before each new connection) to
  raise `sqlite3.OperationalError`, or swap a junk `library.db` in (`running.unreadable_database()`). A connection
  whose PRAGMAs fail (junk file) is closed before the error goes up.
- Home page scale: `folders_for` is one statement (checked with `set_trace_callback`); 200 rows answer in under 1 s on
  loopback (bound 2 s). Keyboard: only `a` and `button`, each with visible text; Tab reaches `Folder 200` in page order.

## Sign in (US-0126, DEC-012 to DEC-017)

- `GET /auth/start?next=`: `begin_login` stores a `logins` row (`sha256(state)`, `nonce`, `verifier`,
  `safe_destination(next)`, `sha256(browser id)`, `created_at`; rows of 10 minutes or more are purged here), sets
  `lib-b` (random browser id, session cookie) when the browser had none, `302` to `auth_uri` with `response_type=code`,
  `client_id`, `redirect_uri=<library origin>/auth/callback`, `scope=openid email`, `state`, `nonce`, `code_challenge`
  (`S256`), `prompt=select_account`. No credentials: the sign in page with `Sign-in is unavailable. Try again later.`
- `GET /auth/callback`: `error=access_denied` is the sign in page with no message; any other `error`, a missing
  `code`/`state`, an unknown or used `state` (the row is deleted first, `DELETE ... RETURNING`), an attempt aged 600 s
  or more, a browser id whose hash differs, any exchange failure (network, non 200, over 1 MiB, not JSON, no
  `id_token`) or a failed claim (`iss` Google, `aud` client id, `exp` number in the future, `nonce`, `email_verified`
  `true` or `"true"`, non empty `email`) is the sign in page with the message and no session. Success: a `sessions` row
  (`sha256(token)`, lower case email, `created_at`, `expires_at = created_at + 2592000`, never updated), cookie `lib`
  (`Max-Age=2592000`), `303` to the stored destination.
- `POST /auth/logout`: deletes the row, clears `lib` and `lib-b` (`Max-Age=0`), `303 /`. Other browsers stay signed in.
- `GET /`: see Home page and roles below.
- Cookies: `cookie_name` gives `lib`/`lib-b` on http, `__Host-lib`/`__Host-lib-b` on https; attributes
  `Path=/; HttpOnly; SameSite=Lax`, `Max-Age` for `lib` only, `Secure` on https.
- The credentials file is read once at `LibraryServer` construction: missing or unreadable is one ERROR line, a return
  address absent from `redirect_uris` one WARNING line; the server starts either way.

## Home page and roles (US-0127, DEC-018, DEC-029, DEC-023)

- The administrator is decided in `store.py` only: `Library.is_admin(email)` compares `normalize_email(email)`
  (`strip().lower()`, nothing else: no dot removal, no `googlemail.com` rewriting) with `access.ADMIN_EMAIL`;
  `role_in` returns `Role.ADMIN` before reading `members`, so a member row (even RO for the administrator) never
  changes it (FR-NEW-014), and `members.role` is `CHECK (role IN ('RW','RO'))` (FR-NEW-012). Roles are read at every
  request, so a role given later shows at the next page.
- `folders_for(email)`: every folder with `Role.ADMIN` for the administrator, the member rows otherwise, sorted in
  Python by `names.order_key(name)`: NFD, drop `Mn`, `lower()`, NFC, compared by code point (digits, Latin letters,
  other alphabets), then the exact name (`Cafe` before `Café`). Never `casefold`: `ß` is not `ss`. O(n log n) per page.
- `GET /`: `home_page(folders, is_admin=)`: `<nav><a href="/admin">Administration</a></nav>` for the administrator
  only; rows `<li><a href="/f/<id>">name</a> <span>role label</span></li>` in a `ul.folders`; no folder: the
  administrator gets `<p>You have no access to any folder yet.</p>` (200), anyone else `403` `Access denied.`
  (FR-NEW-003). `/admin` has no row yet (US-0130): it is `Access denied.` even for the administrator until then.
- Any path in no row: `Access denied.` for a signed in person, the sign in page for a visitor (`next` = the path).
- `/lib/library.css` (`text/css`) and `/lib/library.js` (`application/javascript`) are the two public rows; a missing
  file is `404 {"error": "Not found"}` (`library.js` arrives in US-0129); any other `/lib/...` is no row.
  `static/library.css` uses logical properties only (RTL names) and `unicode-bidi: plaintext` on folder links.

## Database (DEC-025)

`<library_dir>/library.db` (file `0600`, directory `0700`), WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one
connection per thread (`LibraryHandler.finish` releases it when the connection's thread ends; `stop()` releases the
main thread's). Migration 1 (US-0126): `meta`, `folders`, `members` (+ index on `email`), `logins`, `sessions`.
`migrate()` splits each script on `;` and runs it inside one `BEGIN IMMEDIATE` with `PRAGMA user_version = N`
(`executescript` would commit first). Only hashes of tokens, states and browser ids are stored.

Unknown methods (`PATCH`, `PUT`) get the stdlib 501, `OPTIONS` the inherited 405.

## Headers (DEC-009)

`LibraryHandler.end_headers` calls `_send_common_headers`, so every answer (the inherited 400, 405 and 501
included) carries `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none';
frame-ancestors 'none'`, plus `Strict-Transport-Security: max-age=31536000` when the library origin is https.
The handler attribute `policy` (default JSON) is set to `PAGE_POLICY` by the page answers; the deck frame (US-0133) will set its own.

## Process

`webserve` copies the settings with `--host`/`--port`, builds `LibraryServer` (same host on both origins: stderr
`The library origin and the content origin must be two different host names.`, exit 1, nothing bound), installs
SIGINT and SIGTERM handlers that only set an event, starts the serving thread, prints `Serving the library on
http://<host>:<port>/ (library origin <o>, content origin <o>)`, waits for the event, then calls `server.stop()`
(never inside the handler). `stop()` = `shutdown` (only if started: it waits for a loop otherwise), `server_close`,
`connections.close_idle()`. `HEAD /health` gets the stdlib 501: health checks use GET.

## Tests

`tests/library_support.py`: `library_server(**overrides)` fixture (free port, origins `http://slides.test:<port>`
and `http://slides-content.test:<port>`, temporary `library_dir` and `state_dir`, stopped at teardown),
`HttpClient(port, host)` (sets `Host`, keyword headers `x_forwarded_proto=` become `X-Forwarded-Proto`),
`FakeClock`. Use it in a test module with `library_server = library_support.library_server`.
Sign in support (US-0126): `start(google=fake, google_registered=True)` writes a credentials file pointing at the
`FakeGoogle` (fixture `fake_google`: `choose(email)`, `cancel()`, `accounts[email]` claim overrides,
`registered_redirects` = the console, `exchange_failure` `close`/`unavailable`/`bad_json`, `received`);
`running.browser(resolver)` is a `Browser` (cookies, redirects across hosts, `visited`, `replies`, `sign_in`,
`sign_out` with `Origin`); `LibraryReply.folder_rows()` (id, escaped name, role label of each home row);
`running.builder` (`folder` with `names.name_key`, `folders(*names)`, `member`, `standard()`) and `running.stored` (`sessions`,
`logins`, `folder_names`, `activity`, `rows`); fixture `evil_listener` counts visits to evil.example.
`tests/test_library_visitor_http.py`: E2E-004, 134 (library side), 145, route table, `esc`, `authorize`, `safe_destination`.
`tests/test_library_auth_http.py`: E2E-003, 005, 007, 090, 150, 171, 172, 183, 184, SEC-015, 016, 019, sign out,
cookies, claims, PKCE, database.
`tests/test_library_home_http.py`: E2E-014, 018, 087, 149, 165, `role_in`, empty home, escaping, `/lib/*`.
`tests/test_library_names.py`: `order_key`, `name_key`, 100 random names.
`tests/test_library_sessions_http.py`: E2E-008, 012, 016, 166, new period on a new sign in, corrupted file, 200 folders
(time and one query), keyboard in Chromium, purge, the clock and `UPDATE sessions` grep. Support: `running.restart()`,
`running.unreadable_database()`, `Browser.reopened()` (only cookies set with `Max-Age` survive),
`builder.numbered_folders(count, email, role)`.
`tests/test_library_gate_http.py`: E2E-135, 136, 146, 147, 186, headers, settings, CLI refusal, a real `webserve`
child stopped by SIGTERM.

## Gotchas

- 2026-11-16 (US-0124): `make format` also formats Python blocks inside `sdlc/**/*.md`; `make format-check` fails on a
  story whose code block is not ruff formatted.
