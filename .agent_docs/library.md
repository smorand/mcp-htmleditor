# Web library mode (SPEC-0025)

`mcp-htmleditor webserve [--host] [--port]`: one process for every folder and presentation of a private library,
behind nginx at `slides.scm-platform.org`. Spec and design: `sdlc/specs/SPEC-0025-web-library-mode/`. Stories
US-0124 to US-0149 land on `feat/0049-web-library-mode`; this file grows with each.

## Module map (`src/mcp_htmleditor/library/`)

| Module | Holds |
|---|---|
| `__init__.py` | package docstring |
| `pages.py` | `esc`, `sign_in_page`, `access_denied()`, `library_unavailable()`, `home_page(folders, is_admin=)`, `folder_page`, `admin_page(folders, activity)` (with the `Delete folder` buttons and the `<dialog>`), `folder_exists(name)`,
`created_folder_line(name)`, `deleted_folder_line(name)`, every English text constant (DEC-055, `ROLE_LABELS` keyed by `Role` value); every page links `/lib/library.css` and loads `/lib/library.js` (`defer`) |
| `names.py` | `compose` (NFC), `name_key` (NFC of lower of NFC, the unique `folders.name_key`), `order_key` (DEC-029), `check_folder_name`, `check_email` / `NameRefused`, `format_size` (DEC-031) |
| `access.py` | `ADMIN_EMAIL`, `Role`, `Permission`, `authorize(role, permission)`, frozen `Route` (`is_json`, `is_navigation`), `Context` (`folder_id`, `role`, `payload`, `session`, `presentation_id`, both origins, filled by the dispatcher), `Answer`, `EditorAnswer` (a deck route answered by the inherited editor method), `json_answer`, `JSON_CONTENT_TYPE`, `SetCookie` (`path`) (DEC-021) |
| `store.py` | `Database(path)` (per thread connection, `transaction(immediate=)`, `release()`, `connect()`, test seam `Database.connect_hook`, `MIGRATIONS`), `Library(database, clock, *, state_dir)` (`folders_for`, `is_admin`, `role_in(email, folder_id or None)`, `folder_name`, `presentation(pid)` (`PresentationRow` or None), `presentation_path`, `presentations_in`, `create_folder(name, actor)`, `delete_folder(folder_id, confirm, actor)`, `set_member(folder_id, email, role, actor)`, `remove_member(folder_id, email, actor)`, `members_by_folder()`, `activity()`, `record(connection, actor, text)`), `NameTaken`, `NameMismatch`, `FolderMissing`, `normalize_email`, `FolderView`, `MemberView`, `PresentationView`, `ActivityLine` |
| `routes_admin.py` | `GET /admin` (ADMINISTER, `administration`), `POST /api/folders` (ADMINISTER, JSON, `create_folder`), `POST /api/folders/<fid>/delete` (`delete_folder`), `POST /api/folders/<fid>/members` (`set_member`), `POST /api/folders/<fid>/members/remove` (`remove_member`), all ADMINISTER and JSON |
| `signin.py` | `GoogleClient` (`authorization_url`, `exchange`), `read_credentials`, `validate_claims`, `safe_destination`, `Accounts` (`begin_login`, `finish_login`, `purge`, `session_for`, `end_session`, `issue_ticket`, `redeem_ticket`, `grant_for`), `Session`, `NewSession`, `NewGrant`, `Live`, `NoGrant` (`ENDED`, `ABSENT`), `GrantState`, `SignInUnavailable`, cookie base names (`lib`, `lib-b`, `d`) |
| `routes_library.py` | `ROUTES`: `GET /lib/library.css`, `GET /lib/library.js` (PUBLIC, `static_file`, `STATIC_DIR`), `GET /auth/start`, `GET /auth/callback` (PUBLIC), `POST /auth/logout`, `GET /` (SIGNED_IN), `GET /f/(?P<fid>[0-9a-f]{32})` (VIEW, `folder`), `GET /open/(?P<pid>[0-9a-f]{32})` (VIEW on the presentation's folder, `open_presentation`) |
| `routes_deck.py` | content origin `ROUTES`: `GET /enter` (PUBLIC), `GET /d/<pid>/content-frame` (framed, navigation), `/status`, `/content`, `/download` (navigation), then `GET` and `POST /d/<pid>/.*` (`refuse`); `deck_path`, `denied()` |
| `static/library.js` | every page: `time[datetime]` rewritten in the browser's zone, `pageshow` with `persisted` reloads (DEC-009, DEC-031); administration: `sendJson` (fetch, reload on success, refusal into an alert), `Create folder`, the deletion `<dialog>`, the `Members` controls |
| `server.py` | `load_routes`, `cookie_name(origin, base, path)`, `cookie_header`, `parse_cookies`, `PAGE_POLICY`, `FRAME_POLICY`, `DeckTarget`, `LibraryServer(_EditorServer)` (`start`, `stop`, `port`, `origin_for`, `find_route`, `is_secure`, `clock`, `database`, `library`, `accounts`), `LibraryHandler(_EditorHandler)` (gate, `_serve_library`, `_serve_content_origin`, `_deck_answer`, `_respond`, the DEC-003 hook overrides, `_serve_status`, `_send_common_headers`), `health_answer`, `LibraryConfigError`, `SAME_HOST_MESSAGE`; re-exports `safe_destination` |

A route handler is a plain function `(Context) -> Answer` (a `routes_*` module never imports `server.py`, which loads
the routes while being imported). The dispatcher writes the `Answer` (an HTML body gets `PAGE_POLICY`).

`_EditorServer.__init__(bind_host, port, handler=_EditorHandler)` and the five hooks (US-0133) are the only changes to
`http_server.py` (DEC-003; `.agent_docs/architecture.md`); `test_the_editor_handler_is_unchanged...` pins the source
hash of `_EditorHandler`: a story editing it updates the hash in its own diff.

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
5. Content origin, `_serve_content_origin`: a path in no `content` row is `302` to `<library origin>/`; otherwise
   § Opening a presentation. An unread body of a non GET closes the connection. Python's `BaseHTTPRequestHandler`
   already turns `//x` into `/x` in `self.path`.
6. Library origin, `_serve_library` (DEC-019, DEC-021, DEC-022), in this order: a non GET/HEAD/OPTIONS request needs
   `Origin` exactly the library origin and `Sec-Fetch-Site` absent, `same-origin` or `none` (before the route lookup:
   a POST to no row gets `Access denied.` too); the route (origin, method, `pattern.fullmatch(path)`); a route with
   `is_json` needs `Content-Type: application/json` (`check_content_type`, parameters and case aside: what a form of
   another page sends without a preflight); every refusal so far is `403` `Access denied.` before the session. Then
   the session (`lib`/`__Host-lib`, `Accounts.session_for`): no route, or a non PUBLIC route without a session, is the
   sign in page for a visitor (`200`, `next` = `safe_destination(path)`), `Access denied.` for a signed in person.
   Then `role_in(email, fid or None)` (Admin for the administrator on any route) and `authorize`; false is `Access
   denied.`. Only then the JSON body (`_read_library_json`: `parse_content_length`, 413 above 65 536 bytes before
   reading, 400 `Invalid request body` unless a JSON object) into `Context.payload`, then the handler, which
   validates the payload (members: the folder exists, then the address, then the role; US-0132).
7. `_library_answer` (route, session, handler) runs inside `except (sqlite3.Error, OSError)`: `503`
   `pages.library_unavailable()` (`The library is unavailable. Try again later.`, no name, no list, no Sign out form),
   one ERROR line naming the exception type. Writing the answer is outside the guard (a closed socket is not the
   library). Nothing is cached: the next request opens a new connection and works as soon as the file is readable.
   The Google token call uses an opener with no proxy and no redirect (`signin.py`).

## Lifetime (US-0128, DEC-017, DEC-024, DEC-032)

- Clock: `LibraryServer(settings, clock=time.time)` hands `clock` to `Accounts` and `Library`; no `library/` module
  reads the wall clock or contains `UPDATE sessions` (grep test).
- A session is alive while `clock() < expires_at`; at `expires_at` exactly it is over. `expires_at` is written once.
  `Accounts.purge()` (called by `begin_login` and by `finish_login` after it took the attempt) deletes session rows
  ended more than 86 400 s ago (kept a day for US-0137; their grants cascade), attempts of 600 s or more and tickets
  of 60 s or more (`issue_ticket` purges tickets too).
- Restart: no state in memory; a new `LibraryServer` on the same `library_dir` serves the same sessions and folders.
- Unreadable library: tests set `Database.connect_hook` (class attribute, called before each new connection) to
  raise `sqlite3.OperationalError`, or swap a junk `library.db` in (`running.unreadable_database()`). A connection
  whose PRAGMAs fail (junk file) is closed before the error goes up.
- Home page scale: `folders_for` is one statement (checked with `set_trace_callback`); 200 rows answer within the 2 s
  bound (a 1 s margin flaked under load). Keyboard (E2E-017): only `a` and `button`, each with visible text; Tab
  reaches `Folder 200` in page order.

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
- Cookies: `cookie_name` gives `lib`/`lib-b` on http, `__Host-lib`/`__Host-lib-b` on https; attributes
  `Path=/; HttpOnly; SameSite=Lax`, `Max-Age` for `lib` only, `Secure` on https.
- The credentials file is read once at `LibraryServer` construction: missing or unreadable is one ERROR line, a return
  address absent from `redirect_uris` one WARNING line; the server starts either way.

## Opening a presentation (US-0133, DEC-037, DEC-040, DEC-041)

- `GET /open/<pid>` (library): the dispatcher's `_target` reads `presentation(pid)` and takes the role in its folder
  (unknown id: no folder, only the administrator passes, then the handler answers `Access denied.`); success is a
  ticket row (`sha256`, session hash, pid, `created_at`) and `302 <content origin>/enter?t=<43 char ticket>`.
- `GET /enter?t=` (content): `redeem_ticket` deletes the ticket first (`DELETE ... RETURNING`), refuses 60 s or more
  or a session no longer alive, inserts a grant (fresh 256 bit token, hash only); cookie `d` (`__Secure-d` on https,
  `__Host-` needs `Path=/`) `Path=/d/<pid>/; HttpOnly; SameSite=Lax`, no `Max-Age`; `302 /d/<pid>/`. A bad ticket:
  `302 <library origin>/`, no cookie. Migration 4: `tickets`, `grants`, both `ON DELETE CASCADE` from `sessions`
  (sign out kills them), no foreign key to `presentations`.
- `/d/<pid>/` rows (`_deck_answer`, every request): `grant_for(pid, cookie)` (one join, the grant must name this pid
  and its session be alive): not `Live` is `401 {"error": SESSION_EXPIRED, "code": "session_expired"}` with
  `X-Editor: 1`, else `302 <library origin>/open/<pid>`. Then `presentation(pid)`, `role_in`, `authorize`: refused
  is `302 /open/<pid>` for a navigation route without `X-Editor`, else `403 {"error": "Access denied.", "code":
  "denied"}`. Then `DeckTarget(path, name, role)` feeds the hooks: `_served_file`, `_served_name` (`<name>.html`),
  `_failure_reason` (`strerror`, else `Export failed`); `_save_lock` and `_pptx_options` keep the defaults until
  US-0136 and US-0140. `_serve_status`: `mtime`, `false`, `null`, `<name>.html`, `poll_interval`, `port` 0,
  `requests_revision` (0 without EDIT). `_serve_deck_file` is never reached (catch all rows). Cost: four primary key
  reads per request.
- The deck frame answer sets `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'`
  (handler attributes `frame_options`, `policy`, reset per request); `_send_no_store_headers` is a no op
  (`end_headers` already sends them).
- The shell `GET /d/<pid>/` (US-0134, DEC-038, `library_shell`): `editor.html` with `src`/`href` under `/d/<pid>`, the
  meta `editor-config` (`base`, `readOnly`, `library`) and `static/editor-library.js` before the first script; policy
  `frame-ancestors 'none'` only (the editor has inline styles), `X-Frame-Options: DENY`. The script wraps `fetch`
  for the eight editor paths (prefix `base`, header `X-Editor: 1`, `window.__libraryCode` on 401/403) and redefines
  `reloadFrame`. `GET /static/<name>` on the content origin is public (product files). Folder page names link `/open/<pid>`.

## Pages

Home page, folder page, administration, folder deletion and members (US-0127, US-0129 to US-0132): `.agent_docs/library-pages.md`.

## Storage (DEC-025)

`<library_dir>/files/<folder id>/<presentation id>.html`; `Library.presentation_path` builds it only after both ids
match `^[0-9a-f]{32}$` (`ValueError` otherwise), from `database.path.parent`. Migration 2 (US-0129): `presentations(id,
folder_id → folders ON DELETE CASCADE, name, name_key, created_at, UNIQUE (folder_id, name_key))`; `name` is the
composed stem without `.html`. Nothing writes presentations yet except the test builder (upload: US-0141).

## Database (DEC-025)

`<library_dir>/library.db` (file `0600`, directory `0700`), WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one
connection per thread (`LibraryHandler.finish` releases it when the connection's thread ends; `stop()` releases the
main thread's). Migration 1 (US-0126): `meta`, `folders`, `members` (+ index on `email`), `logins`, `sessions`.
`migrate()` splits each script on `;` and runs it inside one `BEGIN IMMEDIATE` with `PRAGMA user_version = N`
(`executescript` would commit first). Only hashes of tokens, states and browser ids are stored. Unknown methods
(`PATCH`, `PUT`) get the stdlib 501, `OPTIONS` the inherited 405.

## Headers (DEC-009)

`LibraryHandler.end_headers` calls `_send_common_headers`, so every answer (the inherited 400, 405 and 501
included) carries `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none';
frame-ancestors 'none'`, plus `Strict-Transport-Security: max-age=31536000` when the library origin is https.
The handler attribute `policy` (default JSON) is set to `PAGE_POLICY` by the page answers; the deck frame sets its own.

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
`logins`, `folder_names`, `activity`, `rows`); fixture `evil_listener` counts visits to evil.example; US-0128:
`running.restart()`, `running.unreadable_database()`, `Browser.reopened()` (only cookies with `Max-Age` survive).
Folder page (US-0129): `builder.presentation(folder_id, name, *, size, modified, slides=1, title=None)` (a generated
deck padded with an HTML comment to exactly `size` bytes, below the smallest deck the start of one; `os.utime`),
`builder.standard_presentations(ids)` (the five decks of spec section 9, about 11 MB: only where a test needs them),
`builder.numbered_folders(count, email=None, role="RW")` (`Folder 001`...), `LibraryReply.presentation_rows()`,
`launch_chromium(playwright, *other_hosts)`, `person_context(chromium, running, session, zone=)`, `EVIL_HOST` and
`RecordingListener.page` (a hostile HTML page served from loopback).
US-0131: `StoredLibrary(library_dir, state_dir).entries()` (every path under both directories as `library/...` and
`state/...`), `LibraryBuilder(database, clock, state_dir).records(presentation)` (two history versions, two requests, one
AI suggestion through `HistoryStore`, `RequestService`; returns `<state_dir>/files/<key>`).
US-0132: `Browser.add_member(fid, email, role)`, `Browser.remove_member(fid, email)`, `LibraryReply.member_rows(fid)`
(address, role label; asserts the folder's `Members` section exists), `StoredLibrary.members()`, `signed_in`, `visible_texts`.
US-0130: `Browser.post_json(path, payload, headers=None)` (default `page_post_headers()`: `Origin`, `Sec-Fetch-Site:
same-origin`, JSON type), `LibraryReply.activity_lines()` (unescaped `(UTC ISO, actor, text)`).
US-0133: `start(scheme="https")`, `Browser.deck_cookies` (content origin, by path; `X-Forwarded-Proto` sent when the
origins are https), `open_presentation(pid)`, `deck(pid, route, follow=, x_editor="1")`, `grant(pid)`, `copied()`;
`sign_out` posts to the library origin wherever the browser is; `StoredLibrary.tickets()`, `grants()`.
Modules: `tests/test_library_<area>_http.py` (HTTP) and `_e2e.py` (Chromium) for the areas `visitor`, `auth`, `home`,
`sessions`, `gate`, `folders`, `admin`, `foldel`, `members`, `open`, plus `test_library_names.py` (units); each module docstring lists its spec ids.

## Gotchas

- 2026-11-16 (US-0124): `make format` also formats Python blocks inside `sdlc/**/*.md`; `make format-check` fails on a
  story whose code block is not ruff formatted.
- 2026-11-16 (US-0129): a hostile page given to Chromium by `route.fulfill` counts as public, and Chromium (Private
  Network Access) refuses its frames to the loopback library whatever the headers: the framing test passed with
  `X-Frame-Options` removed. Serve the hostile page from a loopback listener (`RecordingListener.page`, `EVIL_HOST`
  in `launch_chromium`); then removing the headers makes the frame show `Sign in with Google` (a cross site frame has
  no `SameSite=Lax` cookie, so it is a visitor's view).
