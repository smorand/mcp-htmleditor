# SPEC-0025: Web library mode, design

> Spec: sdlc/specs/SPEC-0025-web-library-mode/spec.md
> Nature: FEAT
> Depth: L
> Security: internal finding
> Designed on: 2026-11-16
> Target tier: 2 (default: no `--tier`, no `Tier:` in `sdlc/constitution.md`, no `.spec.json`), state source. Stories whose files, tests or decision density exceed the tier 2 band carry `min_tier: 1`.

Project state: existing (`ls src/mcp_htmleditor` lists 23 modules and 4 packages, 6342 lines of top level Python, `git log` shows SPEC-0001 to SPEC-0024 landed). Counts taken by command on `spec.md`: 74 requirements (`FR-NEW-001` to `FR-NEW-074`, no `BR-` or `DR-`), 214 acceptance tests (189 `E2E-`, 25 `E2E-SEC-`), 23 scenarios (`SC-001` to `SC-023`).

Library versions: this design introduces no library. Everything new is Python 3.13 standard library (`sqlite3`, `http.server`, `urllib`, `secrets`, `hashlib`, `unicodedata`, `html`, `json`, `threading`) on top of the manifest of `pyproject.toml:12-22`. context7 is therefore not consulted; the one external text relied on, OpenID Connect Core 1.0 section 3.1.3.7 item 6, was read in full on 2026-11-16 (DEC-012).

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| Language, build, gate | Python 3.13, `uv`, `make check` (unchanged) | `requires-python >= 3.13` (`pyproject.toml:6`) | DEC-004 |
| Web server | stdlib `ThreadingHTTPServer`, the existing `_EditorHandler` extended by a subclass | stdlib | DEC-003, DEC-004 |
| Metadata store | stdlib `sqlite3`, one file, WAL, one connection per thread | SQLite bundled with CPython 3.13 | DEC-025 |
| Presentation bytes | files named by random ids, written by the existing `atomic_write` | n/a | DEC-025, DEC-026 |
| Sign in | OpenID Connect authorization code flow with PKCE against Google, `urllib.request` | stdlib | DEC-012 |
| Sessions and grants | server side rows, 256 bit random tokens stored as SHA 256 | stdlib `secrets`, `hashlib` | DEC-017, DEC-037 |
| CLI | `click` (existing), new command `webserve` | `click>=8.0` | DEC-001 |
| Config | `pydantic-settings` `Settings` (existing), new `HTMLEDITOR_LIBRARY_*` fields | `pydantic-settings>=2.7` | DEC-005 |
| Tests | `pytest`, `pytest-playwright` (existing dev group), in process `LibraryServer`, a fake Google in `tests/library_support.py` | existing | DEC-049 |
| New third party packages | none | n/a | DEC-004 |

Skills loaded with `load_dynamic_context`: `python`, `docker` (both returned content, none returned `ECHEC`). Effect: `make` is the only entry point and `make check` the gate (lint, format, mypy strict, bandit, coverage 80 %); every new module follows the file order and naming rules of the python skill (frozen dataclasses for value objects, `%` formatting in log calls, `logger = logging.getLogger(__name__)`, config only through `Settings`, `trace_span("category.operation")` on external calls); the docker skill adds the container rules applied in DEC-046 and DEC-047 (non root numeric `USER` already present, exec form `ENTRYPOINT` already present, `HEALTHCHECK` kept, secrets never in a layer, a `.dockerignore` file). Skill MUST rules that the project already deviates from (Typer, FastAPI, async first, `CONTAINER_ENGINE`) are not applied: `.agent_docs/python.md` records click and synchronous I/O as documented deviations, and DEC-004 keeps them because the spec forbids no new stack but the project stack is not re-decided here.

## 2. Approaches

### Chosen: one `webserve` process, two origins, server side sessions

One new command starts one process that serves every folder and presentation. It answers on two host names that reach the same listener: the library origin (sign in, library pages, administration, upload, delete, JSON API, session cookie) and the content origin (the editor shell, the deck frame, status, save, download, export and request routes of ONE presentation, reached through a one time ticket that sets a per presentation grant cookie). Metadata lives in SQLite, presentation bytes in files named by random ids. The existing `_EditorHandler` machinery (header gate, time bounds, connection registry, save pipeline, request loop routes) is reused through five small hooks, so the editor behaves as in the local mode.

Pros: one deployable, one port (7842 as the image already declares), per request resolution so 200 folders and 100 presentations need no process each (FR-NEW-060, E2E-017), a hostile deck script runs on an origin that holds no library session and no library API (FR-NEW-052, E2E-SEC-013, E2E-SEC-014), every authorization decision in one dispatcher (Class B), revocation applies to the next request because roles are recomputed per request (FR-NEW-048), sessions survive restarts and die at sign out (FR-NEW-062, FR-NEW-072).

Cons and risks: a second host name (DNS exists through the wildcard record, but a certificate and a reverse proxy route are a deployment prerequisite, DEC-046); the library shell loads one extra classic script that rewrites the editor's URLs and notices, the editor scripts themselves are not edited (DEC-038); PPTX downloads are the flow engine result, not the Chromium painted one (DEC-043); SQLite is a single writer (acceptable for a private library, DEC-025).

Affected scope: new package `src/mcp_htmleditor/library/`, `config.py`, `cli.py`, `http_server.py` (hooks only), `export/to_pptx.py` and two exporter modules (picture confinement), `static/editor*.js` (base URL, notices, read only), `Dockerfile`, `docker-compose.prod.yml`, `Makefile`, docs.

Best suited when: the library is private, small (tens of folders, hundreds of presentations), operated by one person, and the editor must stay the product's own editor.

### Rejected: one process per deck behind a router

Summary: reuse `serve` unchanged, start one process per presentation (`start_http_server`, `http_server.py:1111-1160`) and route requests by path. Why rejected (DEC-002): the port scan is bounded to 10 slots (`config.py:353-354`, `http_server.py:1101`) and `state.py:177-181` keeps one `current_file` per process, so 200 folders cannot be served and E2E-017 fails; a router process would also have to authenticate, which is the new code anyway.

### Rejected: one origin, deck in a sandboxed frame without `allow-same-origin`

Summary: serve decks from the library origin inside `<iframe sandbox="allow-scripts">`. Why rejected (DEC-007): the editor reads and rewrites the framed document directly (`editor-save.js:18` `frame.contentDocument`, `editor-edit.js`, `editor-format.js`, `editor-undo.js`), which an opaque origin forbids, so FR-NEW-025 (every editor option) fails; and `document.cookie` or `localStorage` would throw instead of reading empty, which E2E-SEC-013 forbids.

### Rejected: one origin with the existing frame (`allow-scripts allow-same-origin`)

Summary: keep `editor.html:145` as is. Why rejected (DEC-007): a deck script then calls the library API with the viewer's session (`fetch(DELETE_ADDRESS)` of E2E-SEC-014); no token held by the page can hide from a same origin script (`window.parent` is readable).

### Rejected: stateless signed cookies (HMAC) and JWT sessions

Why rejected (DEC-017): FR-NEW-072 requires a copied credential to stop working after sign out, which needs server state anyway; a signing key would be one more secret to protect and rotate.

### Rejected: `google-auth` or `authlib`

Why rejected (DEC-012): a new third party dependency (category 2 of ASK ONLY FOR) for a 120 line flow; OIDC Core 1.0 section 3.1.3.7 item 6 lets a client that received the ID token directly from the token endpoint over TLS skip the signature check.

## 3. Architecture

### 3.1 Process and components

```
 browser (library origin  https://slides.scm-platform.org)        browser (content origin  https://slides-content.scm-platform.org)
        |  cookie __Host-lib (HttpOnly)                                 |  cookie __Secure-d, Path=/d/<id>/ (HttpOnly)
        v                                                               v
   nginx (TLS, Host kept, X-Forwarded-Proto)  ---- both names, one upstream  ---->  mcp-htmleditor webserve :7842
                                                                          |
   LibraryServer(ThreadingHTTPServer, ConnectionRegistry)                 |
     LibraryHandler(_EditorHandler)                                       |
       gate        host gate, X-Forwarded-Proto redirect, headers, /health
       dispatcher  route table: (origin, method, pattern) -> (permission, handler)
          main origin    /  /lib/*  /auth/*  /f/<fid>  /admin  /open/<pid>  /api/*
          content origin /enter  /d/<pid>/...  /static/*
       authorize   session or grant -> person -> role (recomputed) -> permission
     Library (store.py)      folders, members, presentations, activity   (sqlite3)
     Accounts (signin.py)    logins, sessions, grants, tickets            (sqlite3)
     GoogleClient            auth url, token exchange, claims
     inherited editor routes content, content-frame, download, export/pptx, requests, arch-layout (hooks)
```

Bounded contexts of the spec map to modules: sign in and sessions to `library/signin.py` (+ `google.py`), access control to `library/access.py`, library to `library/store.py`, upload and removal to `library/uploads.py` and the upload and delete routes, administration to `library/routes_admin.py`, activity to `store.py`, presentation editing to the inherited `_EditorHandler` routes plus `library/routes_deck.py`, local mode to nothing (untouched), deployment address to `library/server.py` (gate) and the compose file.

### 3.2 Module map (new package `src/mcp_htmleditor/library/`)

| Module | Responsibility |
|---|---|
| `__init__.py` | package docstring only |
| `server.py` | `LibraryServer`, `LibraryHandler` (gate, dispatcher, cookies, headers), `serve_library()` |
| `pages.py` | every HTML page and message, `esc()` single escaping function, the exact user texts |
| `signin.py` | `GoogleClient`, login attempts, sessions, grants, tickets |
| `store.py` | `Database` (per thread connection, `transaction()`, ordered `MIGRATIONS` appended by stories) and the `Library` repository: folders, members, presentations, activity, flags, roles |
| `names.py` | composed form, keys, order key, name and email rules, size and number formats |
| `access.py` | `Role`, `Permission`, `ROUTES`, `authorize()` |
| `routes_library.py` | home, folder page, open (ticket), sign out, upload and delete routes |
| `routes_admin.py` | administration page and folder, member routes |
| `routes_deck.py` | content origin routes: enter, shell, status, deck routes through the hooks |
| `uploads.py` | upload check pipeline, chunked cap, replace |
| `seed.py` | initial content |
| `assets` | `static/library.css`, `static/library.js` (served as `/lib/library.css`, `/lib/library.js`) |

Existing code reused as is: `http_deadline.py` (time bounds, `http_deadline.py:22-23`), `http_connections.py:20-49` (graceful stop), `fileio.atomic_write` (`fileio.py:49-67`), `history.py` (`HISTORY_LIMIT = 20` at `history.py:28`, key per resolved path), `request_store.py:81-100` and `request_service.py` (request loop), `deck/__init__.py:61` `deck_from_text` and `deck/lint.py:51` `lint_deck` (upload validity), `http_server.py:781-799` `parse_content_length`, `check_content_type`, `write_save` (`:842`), `check_conflict` (`:833`), `_refuse_ambiguous_headers` (`:215`).

### 3.3 Existing structure that the design relies on

- One process holds one file: `state.py:177-181` `set_file`, `http_server.py:1144-1152` (a second start only switches the file). The editor routes read it through `get_state().current_file` in `_serve_content` (`http_server.py:376`), `_serve_content_frame` (`:389`), `_serve_download` (`:409`), `_export_pptx` (`:432`), `_export_docx` (`:458`), `_serve_status` (`:493`), `_loaded_file` (`:578`), `_receive_content` (`:625`) and `_run_arch_layout` (`:653`). DEC-003 turns those reads into five overridable methods.
- The trust gate accepts loopback names and the bind host only (`http_server.py:1045-1050`), accepts a request with no `Origin` header (`:255-259`) and requires the scheme `http` (`:1060`). The library handler does not use `_refuse_untrusted_request` (DEC-007, DEC-022); it reuses `_refuse_ambiguous_headers` (`:215-238`).
- The editor posts to absolute paths: `fetch('/content')` `editor-save.js:35`, `fetch('/status')` `editor.js:84`, `:432`, `fetch('/export/' + format)` `editor.js:411`, `fetch('/arch-layout')` `editor-menus.js:39`, `fetch(path)` `editor-requests.js:109`, `fetch('/requests')` `:221`, `<a id="download-btn" href="/download">` `editor.html:50`, `<iframe src="/content-frame">` `editor.html:145`, and `frame.src = '/content-frame?' + Date.now()` in `reloadFrame` (`editor.js:475-477`). DEC-038 leaves all of them as they are and rewrites them from one library only script.
- The editor shows `Save failed: <reason>` (`editor-save.js:135-138`), counts three failed polls into `Connection to the editor server lost` (`editor-save.js:161`, `editor.js:432-436`), and alerts `Export <FORMAT> échoué : <text>` (`editor.js:425`). DEC-040.
- The PPTX exporter reads picture addresses from disk: `export/pptx_images.py:112-117` (flow) and `export/pptx_paint_shapes.py:196-200` (painted). DEC-043.
- Settings: `config.py:91-117`, memoized by `_env_signature()` over `_SIGNIFICANT_ENV_VARS` (`config.py:70-88`); every new variable name is added to that tuple or a test that changes it would read stale settings.

### 3.4 Request flow

Library origin, a person opens a presentation: `GET /open/<pid>` (session cookie) resolves session, then presentation, then folder, then role; allowed means a one time ticket row and `302 <content origin>/enter?t=<ticket>`. Content origin `GET /enter?t=` consumes the ticket, inserts a grant bound to the session and the presentation, sets the cookie `__Secure-d` (HttpOnly, Secure when https, SameSite Lax, `Path=/d/<pid>/`, session cookie) and `302 /d/<pid>/`. From then on `/d/<pid>/*` requests, and only they, carry the grant cookie; every request recomputes: grant, session alive or revivable (DEC-037), presentation exists, role from the member table, permission of the route (DEC-021). The deck script in the frame runs on the content origin: it holds no library cookie (the cookie is HttpOnly and its path is the presentation's own), the library API does not exist on that origin, and the library origin refuses state changes whose `Origin` is not its own (DEC-022).

### 3.5 Why the content origin does not weaken the rest

A script on the content origin can call the routes of its own presentation with the viewer's grant: read it, and, for a RW viewer, store a change to it. The spec allows exactly that: "the scripts act only on the presentation itself" (SC-018 flow step 2). It cannot list folders, read another presentation (the grant is per presentation and the id is 128 random bits), delete anything (no delete route on that origin), read the session (HttpOnly, other origin), or call the library API with a cookie (the cookie is host only on the library origin and the API checks `Origin`). Residual risk recorded in section 7.

### 3.6 Concurrency

`ThreadingHTTPServer` runs one thread per connection. SQLite is opened per thread (`threading.local`) with `busy_timeout`, `journal_mode=WAL`, `foreign_keys=ON`. Writes use `BEGIN IMMEDIATE`, so two uploads of the same new name serialize and the second meets the collision (DEC-027). A presentation file is replaced only under a per presentation `threading.Lock` (DEC-028) so a save, an upload replacement and a deletion never interleave.

## 4. Data model

Database file `<library_dir>/library.db`; presentation bytes `<library_dir>/files/<folder id>/<presentation id>.html`; history, request records and update flags stay where `history.py` and `request_store.py` put them, under `<state_dir>/files/<key>/` with `key = sha256(resolved path)[:32]` (`state.py:211-214`, `request_store.py:87-90`). Ids are `secrets.token_hex(16)` and are validated against `^[0-9a-f]{32}$` before any path is built (DEC-025).

Schema is created by ordered migrations (`PRAGMA user_version`), each story appends one:

| Version | Added by | SQL |
|---|---|---|
| 1 | US-0126 | `meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)`; `folders(id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE, created_at REAL NOT NULL)`; `members(folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE, email TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('RW','RO')), PRIMARY KEY (folder_id, email))`; `logins(state_hash TEXT PRIMARY KEY, nonce TEXT NOT NULL, verifier TEXT NOT NULL, destination TEXT NOT NULL, browser_hash TEXT NOT NULL, created_at REAL NOT NULL)`; `sessions(id_hash TEXT PRIMARY KEY, email TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL)` |
| 2 | US-0129 | `presentations(id TEXT PRIMARY KEY, folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE, name TEXT NOT NULL, name_key TEXT NOT NULL, created_at REAL NOT NULL, UNIQUE (folder_id, name_key))` |
| 3 | US-0130 | `activity(id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, actor TEXT NOT NULL, text TEXT NOT NULL)` |
| 4 | US-0133 | `tickets(ticket_hash TEXT PRIMARY KEY, session_id_hash TEXT NOT NULL REFERENCES sessions(id_hash) ON DELETE CASCADE, presentation_id TEXT NOT NULL, created_at REAL NOT NULL)`; `grants(token_hash TEXT PRIMARY KEY, session_id_hash TEXT NOT NULL REFERENCES sessions(id_hash) ON DELETE CASCADE, presentation_id TEXT NOT NULL, created_at REAL NOT NULL)` |

Meaning and invariants:

- `folders.name` is the trimmed composed name as typed; `name_key = NFC(lower(NFC(name)))` is unique, so `Cardiology 2027` and `cardiology 2027` collide and `Café` (precomposed) equals `Café` (decomposed) while `Cafe` differs (FR-NEW-042, DEC-029).
- `members.email` is lower case, trimmed; one row per (folder, address) (FR-NEW-045). The administrator is never read from this table (DEC-006).
- `presentations.name` is the composed stem without `.html`; `name_key` as for folders; the pair (`folder_id`, `name_key`) is unique, which is what makes two simultaneous uploads of one new name end with one row (FR-NEW-037). `created_at` is informational; the listed modified time is the file `st_mtime` (FR-NEW-018, and the marker the conflict check compares, `http_server.py:833-839`).
- `activity.text` holds the final line text (`Uploaded "Quarterly Review" in "Cardiology 2027"`); only the 500 newest rows are kept: after each insert rows with `id <= max(id) - 500` are deleted (FR-NEW-050).
- `meta('seeded')` records that the initial content was created (FR-NEW-054). `meta('schema')` is not used; `PRAGMA user_version` is.
- `sessions.expires_at = created_at + 30 * 86400` exactly, set once, never updated (FR-NEW-005). Rows are purged 24 hours after `expires_at` (DEC-037).
- A login attempt row is deleted when used or after 10 minutes. A ticket row is deleted when consumed or after 60 seconds. Grants die with their session (cascade) or are rebound (DEC-037).
- Deleting a presentation row does not touch `grants` (no foreign key): a grant for a vanished presentation answers `Access denied.`, never a sign in page (FR-NEW-048).
- No person row exists: the identity is the lower case email of the session; roles are recomputed from `members` on every request (FR-NEW-048).

Changes to existing schemas: none. Rollback: delete `<library_dir>`; the local mode is unaffected.

Filesystem rules: a presentation path is `files/<fid>/<pid>.html` built from validated ids only; `atomic_write` writes the temporary file in the same directory (`fileio.py:70-98`); a deleted folder removes `files/<fid>/` and, for each of its presentations, `<state_dir>/files/<key>/` (history, requests, update flag); a recreated presentation has a new id, so a history can never come back (Class A occurrence A#7).

## 5. Contracts and interfaces

### 5.1 CLI

```
mcp-htmleditor webserve [--host TEXT] [--port INTEGER]     # DEC-001
mcp-htmleditor library-list                                # DEC-051, operator view of the stored library
```

`webserve` reads `Settings`, creates `library_dir`, applies the migrations, seeds the initial content once (DEC-036), prints `Serving the library on http://<host>:<port>/ (library origin <origin>, content origin <origin>)` on stdout (user output, `click.echo`) and blocks until SIGINT or SIGTERM, then stops like `stop_http_server` (shutdown, close, `connections.close_idle()`, `http_server.py:1176-1198`). It exits 1 with `The library origin and the content origin must be two different host names.` when both origins have the same host. A missing or unreadable credentials file does not stop the start: it logs an error and every sign in ends with "Sign-in is unavailable. Try again later." (EXC-023c). `serve`, `new`, `mcp`, `export` and every other command are unchanged.

`library-list` prints one line per presentation, `<folder name>\t<presentation name>\t<stored path>\t<bytes>`, so an operator can pass the path to `mcp-htmleditor history` (SPEC-0009, spec 7.6). It reads the database only.

### 5.2 Settings (`config.py`), prefix `HTMLEDITOR_` (DEC-005)

Precedence is the existing one (`config.py:91-117`): field default, then `.env` of the working directory, then real environment; the CLI options `--host` and `--port` win. There is no YAML layer in this project and none is added.

| Field | Variable | Default | Meaning |
|---|---|---|---|
| `library_origin: str` | `HTMLEDITOR_LIBRARY_ORIGIN` | `https://slides.scm-platform.org` | scheme, host and optional port of the library origin; no path |
| `library_content_origin: str` | `HTMLEDITOR_LIBRARY_CONTENT_ORIGIN` | `https://slides-content.scm-platform.org` | same for the content origin; its host must differ |
| `library_dir_override: Path or None` | `HTMLEDITOR_LIBRARY_DIR` | property `library_dir` = `state_dir / "library"` | database and presentation files |
| `google_credentials_override: Path or None` | `HTMLEDITOR_GOOGLE_CREDENTIALS_FILE` | property `google_credentials_file` = `None` | the operator's file `{"web": {"client_id", "client_secret", "auth_uri", "token_uri", "redirect_uris"}}`; read only by `library/signin.py` |
| `library_seed_dir_override: Path or None` | `HTMLEDITOR_LIBRARY_SEED_DIR` | property `library_seed_dir` = repo `library-seed/`, else package `library_seed/` (same rule as `skill_dir`, `config.py:192-201`) | initial content |

All five variable names are appended to `_SIGNIFICANT_ENV_VARS` (`config.py:70-88`); the three path fields are appended to `_PATH_FIELDS` (`config.py:53-67`). A value that is not `http(s)://host[:port]` is a validation error naming the variable.

### 5.3 Routes

Gate order for every request, both origins (DEC-007, DEC-008, DEC-009, DEC-010): `_refuse_ambiguous_headers` (400, `http_server.py:215`), `GET /health` (any host), host gate (the `Host` header must equal the netloc of one of the two configured origins, else `403 {"error": "forbidden host"}` and nothing of the library), `X-Forwarded-Proto: http` gives `308` to the same path on the configured origin of that host, then the route table.

Library origin (`Host` = library origin):

| Method and path | Who | Answer |
|---|---|---|
| `GET /lib/library.css`, `GET /lib/library.js` | anyone (the only public files) | the two files of `static/` |
| `GET /` and any path not in this table | visitor: the sign in page (200, DEC-011); signed in: `403` "Access denied." page | |
| `GET /auth/start?next=<path>` | visitor | `302` to Google (DEC-012, DEC-013) |
| `GET /auth/callback?code&state` or `?error` | visitor | `303 /` or the destination, or the sign in page with the message |
| `POST /auth/logout` | session, Origin | `303 /`, cookies cleared, session row deleted |
| `GET /` | session | home page (account without right: "Access denied." page, `403`) |
| `GET /f/<fid>` | role >= RO | folder page |
| `GET /admin` | Admin | administration page |
| `GET /open/<pid>` | role >= RO | `302 <content origin>/enter?t=<ticket>` |
| `POST /api/folders` `{"name"}` | Admin, Origin | `201 {"ok": true, "id"}` or `400 {"ok": false, "error"}` |
| `POST /api/folders/<fid>/delete` `{"confirm"}` | Admin, Origin | `200 {"ok": true}` or `400` "The name does not match. Nothing was deleted." |
| `POST /api/folders/<fid>/members` `{"email","role"}` | Admin, Origin | `200 {"ok": true}` upsert, or `400` |
| `POST /api/folders/<fid>/members/remove` `{"email"}` | Admin, Origin | `200 {"ok": true}` |
| `POST /api/folders/<fid>/presentations` raw body | RW or Admin, Origin | `201 {"ok": true, "name"}`, `409 {"ok": false, "collision": "<name>"}`, `400`, `413`, `503` |
| `DELETE /api/presentations/<pid>` and `POST /api/presentations/<pid>/delete` (same handler; the first is what the page sends, the second is what a plain form can send) | RW or Admin, Origin | `200 {"ok": true}` |

Content origin (`Host` = content origin):

| Method and path | Who | Answer |
|---|---|---|
| `GET /enter?t=<ticket>` | ticket | sets the grant cookie (`Path=/d/<pid>/`), `302 /d/<pid>/` |
| `GET /d/<pid>/`, `GET /d/<pid>/content-frame` | grant, role >= RO | editor shell (rewritten, DEC-038), deck HTML; failure is `302 <library origin>/open/<pid>` |
| `GET /d/<pid>/status`, `/content`, `/download`, `/export/pptx` | grant, role >= RO | the inherited handlers through the hooks |
| `GET /d/<pid>/requests` | grant, role RW or Admin | inherited `_list_requests` |
| `POST /d/<pid>/content`, `/arch-layout`, `/requests`, `/requests/delete`, `/review/apply` | grant, RW or Admin, Origin | inherited handlers |
| `GET /d/<pid>/export/docx` and any other path under `/d/<pid>/` | grant | `403` "Access denied." |
| `GET /static/<name>` | anyone (product code, no library content) | editor assets (`_serve_static`) |
| everything else | | `302 <library origin>/` |

Deck route failures depend on who asked (DEC-040). A request that carries the header `X-Editor: 1` (every `fetch` of the editor, added by `editor-library.js`) gets JSON: denied `403 {"error": "Access denied.", "code": "denied"}`; grant missing, ended or expired `401 {"error": "Your session has expired. Sign in again to save.", "code": "session_expired"}`. A request without that header gets `403` `Access denied.` JSON when the grant is live and the role lacks the permission (a hand made write, a hand made read of the requests), and `302 <library origin>/open/<pid>` otherwise (grant absent or ended, and the navigation routes `/d/<pid>/`, `/content-frame`, `/download`, `/export/pptx`), which shows the sign in page to a visitor or a copied session and `Access denied.` to a person with no right. Other failures keep the inherited bodies (`{"error": <reason>}` with the operating system reason through `_failure_reason`, DEC-042).

### 5.4 Hooks added to `_EditorHandler` and the server (`http_server.py`, DEC-003)

```python
def _served_file(self) -> str | None          # default get_state().current_file
def _served_name(self) -> str                 # default Path(file).name, the download and export name
def _save_lock(self) -> AbstractContextManager[object]   # default get_state().save_lock; the library returns a lock that re-checks the presentation still exists
def _failure_reason(self, exc: Exception) -> str   # default str(exc)
def _pptx_options(self) -> dict[str, bool]    # default {}; the library returns {"paint": False, "embedded_pictures_only": True}

class _EditorServer(ThreadingHTTPServer):
    def __init__(self, bind_host: str, port: int, handler: type[BaseHTTPRequestHandler] = _EditorHandler) -> None
```

Exporter: `to_pptx(input_html, output_pptx, *, paint=True, embedded_pictures_only=False)` (`export/to_pptx.py:66`); `_Context.embedded_pictures_only` (`export/pptx_model.py:177`) and the painted context carry the flag; with it set, any picture address that does not start with `data:` is skipped with a report warning (DEC-043).

### 5.5 Editor page configuration

The content origin shell is `static/editor.html` with three server side edits and nothing else: `src="/content-frame"` and `href="/download"` get the base `/d/<pid>`, and the line `<meta name="editor-config" content='{"base":"/d/<pid>","readOnly":true,"library":"<library origin>"}'><script src="/static/editor-library.js"></script>` is inserted before the first `<script>` (the JSON goes through `html.escape(..., quote=True)`). `static/editor-library.js` is the only new editor script and the editor scripts are not edited: it reads the meta, is wrapped in an immediately invoked function (no new global name), wraps `window.fetch` (an async wrapper that, for a 401 or 403 answer, awaits `response.clone().json()` and records `code` before returning the response) so the eight editor paths (`/content`, `/status`, `/requests`, `/requests/delete`, `/review/apply`, `/arch-layout`, `/export/pptx`, `/download`) get the base (the `#download-btn` anchor is intercepted and fetched, DEC-040), registers the read only key and message guards at once (it loads first), and on `DOMContentLoaded` (after every classic script ran) redefines `reloadFrame`, `showSaveError`, `notePollFailure`, the export alert and the click of `#download-btn` so an answer carrying `code` shows its text alone and a download can end on the sign in page (DEC-038, DEC-039, DEC-040). In the local mode the file is never loaded.

### 5.6 Cookies and headers (DEC-009, DEC-017, DEC-037)

| Cookie | Origin | Value | Attributes |
|---|---|---|---|
| `__Host-lib` (`lib` when the scheme is http) | library | 256 bit token | `Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000`, `Secure` when https |
| `__Host-lib-b` (`lib-b`) | library | browser id (128 bit), set by `/auth/start` | `Path=/; HttpOnly; SameSite=Lax`, session cookie |
| `__Secure-d` (`d` when the scheme is http) | content | 256 bit grant token | `Path=/d/<pid>/; HttpOnly; SameSite=Lax`, `Secure` when https, session cookie (no `Max-Age`: the server enforces the session end and the 24 hour revival, a cookie that expired with the session could not be rebound) |

Every response: `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`; `Strict-Transport-Security: max-age=31536000` when the scheme of the origin is https. `Content-Security-Policy`: library pages `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`; JSON `default-src 'none'; frame-ancestors 'none'`; content shell `frame-ancestors 'none'`; the deck frame `frame-ancestors 'self'` with `X-Frame-Options: SAMEORIGIN`.

### 5.7 Exact texts (single source `library/pages.py`)

`Sign in with Google`, `Sign-in is unavailable. Try again later.`, `Access denied.`, `Sign out`, `Admin`, `Administration`, `Read and write`, `Read only`, `You have no access to any folder yet.`, `The library is unavailable. Try again later.`, `This folder has no presentations yet.`, `All folders`, `Upload`, `Delete`, `Uploaded <name>.`, `Only .html files are accepted.`, `This file name is not allowed.`, `The file is larger than 25 MB.`, `This file is not a valid presentation: <first problem>.`, `A presentation named "<name>" already exists. Replace it?`, `Replace`, `Cancel`, `<file name> <percent>%`, `The upload failed. Nothing was changed.`, `Delete "<name>"? This cannot be undone.`, `Folders`, `Activity`, `Folder name`, `Create folder`, `Delete folder`, `Type the folder name to confirm.`, `Members`, `Email address`, `Role`, `Add member`, `Remove`, `Folder names use 1 to 60 letters, digits, spaces or hyphens.`, `A folder named "<name>" already exists.`, `The name does not match. Nothing was deleted.`, `This is not a valid role.`, `This is not a valid email address.`, `No activity yet.`, `Your session has expired. Sign in again to save.`, and the three problem texts `the file is not declared as a presentation`, `the file has no slide`, `the file is not valid UTF-8 text`. Every dynamic value goes through `esc()` (DEC-029, FR-NEW-053).

### 5.8 Main signatures

```python
# names.py
def compose(text: str) -> str                      # NFC
def name_key(name: str) -> str                     # NFC(lower(NFC(name)))
def order_key(name: str) -> tuple[str, str]        # (accents removed, lower, then exact name)
def check_file_name(raw: str) -> str               # composed stem, or NameRefused
def check_folder_name(raw: str) -> str             # trimmed composed name, or NameRefused
def check_email(raw: str) -> str                   # trimmed lower case address, or NameRefused
def format_size(count: int) -> str                 # "1 byte", "900 bytes", "1.0 KB", "1024.0 KB", "1.0 MB"
# access.py
class Role(StrEnum): ADMIN = "Admin"; RW = "RW"; RO = "RO"
class Permission(Enum): VIEW, EDIT, ADMINISTER
ADMIN_EMAIL: Final = "seb.morand@gmail.com"
def authorize(role: Role | None, permission: Permission) -> bool
# store.py
class Library:
    def role_in(self, email: str, folder_id: str) -> Role | None            # Admin first, then members
    def folders_for(self, email: str) -> list[FolderView]
    def presentation_path(self, folder_id: str, presentation_id: str) -> Path   # validated ids only
    def create_folder(self, name: str, actor: str) -> str
    def delete_folder(self, folder_id: str, confirm: str, actor: str) -> None
    def set_member(self, folder_id: str, email: str, role: str, actor: str) -> None
    def remove_member(self, folder_id: str, email: str, actor: str) -> None
    def add_presentation(self, folder_id: str, name: str, data: bytes, actor: str, *, replace: bool) -> Outcome
    def delete_presentation(self, presentation_id: str, actor: str) -> None
    def activity(self) -> list[ActivityLine]
# signin.py
class Accounts:
    def begin_login(self, browser_id: str, destination: str) -> str            # returns the Google URL
    def finish_login(self, state: str, code: str, browser_id: str) -> Session | LoginRefused
    def session_for(self, token: str | None) -> Session | None                 # alive only
    def end_session(self, token: str) -> None
    def issue_ticket(self, session: Session, presentation_id: str) -> str
    def redeem_ticket(self, ticket: str) -> Grant | None
    def grant_for(self, presentation_id: str, token: str | None) -> GrantState  # Live(email), Ended (a cookie that no longer resolves), Absent (no cookie)
# uploads.py
def check_upload(name_header: str | None, declared: int | None, read: Callable[[int], bytes]) -> CheckedUpload | UploadRefused
```

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/config.py` | modify | FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-008, FR-NEW-054, FR-NEW-055, ... | US-0124, US-0126, US-0146 |
| `src/mcp_htmleditor/cli.py` | modify | FR-NEW-026, FR-NEW-055, FR-NEW-056, FR-NEW-058, FR-NEW-059 | US-0124, US-0147 |
| `src/mcp_htmleditor/http_server.py` | modify | FR-NEW-022, FR-NEW-055, FR-NEW-056, FR-NEW-058, FR-NEW-059 | US-0124, US-0133 |
| `src/mcp_htmleditor/library/__init__.py` | create | FR-NEW-055, FR-NEW-056, FR-NEW-058, FR-NEW-059 | US-0124 |
| `src/mcp_htmleditor/library/server.py` | create | FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-005, FR-NEW-006, ... | US-0124, US-0125, US-0126, US-0128, US-0133, US-0136, US-0143, US-0146 |
| `tests/library_support.py` | create | FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-005, FR-NEW-006, ... | US-0124, US-0125, US-0126, US-0127, US-0128, US-0129, US-0130, US-0131, US-0132, US-0133, US-0134, US-0135, US-0136, US-0137, US-0138, US-0140, US-0141, US-0143 |
| `tests/test_library_gate_http.py` | create | FR-NEW-055, FR-NEW-056, FR-NEW-058, FR-NEW-059 | US-0124 |
| `src/mcp_htmleditor/library/pages.py` | create | FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-005, FR-NEW-006, ... | US-0125, US-0126, US-0127, US-0128, US-0129, US-0130, US-0131, US-0132, US-0134, US-0141, US-0144, US-0145 |
| `src/mcp_htmleditor/library/access.py` | create | FR-NEW-001, FR-NEW-057 | US-0125 |
| `tests/test_library_visitor_http.py` | create | FR-NEW-001, FR-NEW-057 | US-0125 |
| `src/mcp_htmleditor/library/signin.py` | create | FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-005, FR-NEW-006, FR-NEW-007, ... | US-0126, US-0128, US-0133, US-0137 |
| `src/mcp_htmleditor/library/store.py` | create | FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-005, FR-NEW-006, FR-NEW-008, ... | US-0126, US-0127, US-0128, US-0129, US-0130, US-0131, US-0132, US-0133, US-0141, US-0144, US-0145, US-0147 |
| `src/mcp_htmleditor/library/routes_library.py` | create | FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-008, FR-NEW-011, FR-NEW-012, ... | US-0126, US-0127, US-0129, US-0133, US-0141, US-0143, US-0144, US-0145 |
| `tests/test_library_auth_http.py` | create | FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-008, FR-NEW-068, FR-NEW-069, ... | US-0126 |
| `src/mcp_htmleditor/library/names.py` | create | FR-NEW-011, FR-NEW-012, FR-NEW-013, FR-NEW-014, FR-NEW-015, FR-NEW-016, ... | US-0127, US-0129, US-0130, US-0132, US-0142 |
| `src/mcp_htmleditor/static/library.css` | create | FR-NEW-011, FR-NEW-012, FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-053, ... | US-0127 |
| `tests/test_library_home_http.py` | create | FR-NEW-011, FR-NEW-012, FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-053, ... | US-0127 |
| `tests/test_library_names.py` | create | FR-NEW-011, FR-NEW-012, FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-032, ... | US-0127, US-0142 |
| `tests/test_library_sessions_http.py` | create | FR-NEW-005, FR-NEW-006, FR-NEW-017 | US-0128 |
| `src/mcp_htmleditor/static/library.js` | create | FR-NEW-013, FR-NEW-018, FR-NEW-019, FR-NEW-020, FR-NEW-021, FR-NEW-028, ... | US-0129, US-0130, US-0131, US-0132, US-0141, US-0143, US-0144, US-0145 |
| `tests/test_library_folders_http.py` | create | FR-NEW-018, FR-NEW-019, FR-NEW-020, FR-NEW-021 | US-0129 |
| `tests/test_library_folders_e2e.py` | create | FR-NEW-018, FR-NEW-019, FR-NEW-020, FR-NEW-021 | US-0129 |
| `src/mcp_htmleditor/library/routes_admin.py` | create | FR-NEW-013, FR-NEW-040, FR-NEW-041, FR-NEW-042, FR-NEW-043, FR-NEW-044, ... | US-0130, US-0131, US-0132 |
| `tests/test_library_admin_http.py` | create | FR-NEW-013, FR-NEW-040, FR-NEW-041, FR-NEW-042, FR-NEW-050, FR-NEW-051, ... | US-0130 |
| `tests/test_library_admin_e2e.py` | create | FR-NEW-013, FR-NEW-040, FR-NEW-041, FR-NEW-042, FR-NEW-050, FR-NEW-051, ... | US-0130 |
| `tests/test_library_foldel_http.py` | create | FR-NEW-043, FR-NEW-044 | US-0131 |
| `tests/test_library_foldel_e2e.py` | create | FR-NEW-043, FR-NEW-044 | US-0131 |
| `tests/test_library_members_http.py` | create | FR-NEW-045, FR-NEW-046, FR-NEW-047 | US-0132 |
| `tests/test_library_members_e2e.py` | create | FR-NEW-045, FR-NEW-046, FR-NEW-047 | US-0132 |
| `src/mcp_htmleditor/library/routes_deck.py` | create | FR-NEW-007, FR-NEW-010, FR-NEW-022, FR-NEW-023, FR-NEW-025, FR-NEW-026, ... | US-0133, US-0134, US-0135, US-0136, US-0137, US-0138, US-0140 |
| `tests/test_library_open_http.py` | create | FR-NEW-022 | US-0133 |
| `src/mcp_htmleditor/static/editor-library.js` | create | FR-NEW-007, FR-NEW-010, FR-NEW-022, FR-NEW-023, FR-NEW-025, FR-NEW-052, ... | US-0134, US-0135, US-0137, US-0140 |
| `tests/test_library_shell_e2e.py` | create | FR-NEW-025, FR-NEW-052, FR-NEW-055, FR-NEW-056 | US-0134 |
| `tests/test_library_viewer_e2e.py` | create | FR-NEW-023 | US-0135 |
| `tests/test_library_edit_http.py` | create | FR-NEW-026, FR-NEW-027, FR-NEW-066 | US-0136 |
| `tests/test_library_edit_e2e.py` | create | FR-NEW-026, FR-NEW-027, FR-NEW-066 | US-0136 |
| `tests/test_library_access_e2e.py` | create | FR-NEW-007, FR-NEW-074 | US-0137 |
| `tests/test_library_requests_http.py` | create | FR-NEW-023, FR-NEW-025 | US-0138 |
| `src/mcp_htmleditor/export/to_pptx.py` | modify | FR-NEW-052 | US-0139 |
| `src/mcp_htmleditor/export/pptx_model.py` | modify | FR-NEW-052 | US-0139 |
| `src/mcp_htmleditor/export/pptx_images.py` | modify | FR-NEW-052 | US-0139 |
| `src/mcp_htmleditor/export/pptx_paint_shapes.py` | modify | FR-NEW-052 | US-0139 |
| `tests/test_export_pptx_library.py` | create | FR-NEW-052 | US-0139 |
| `tests/test_library_pptx_http.py` | create | FR-NEW-010, FR-NEW-022, FR-NEW-052 | US-0140 |
| `tests/test_library_pptx_e2e.py` | create | FR-NEW-010, FR-NEW-022, FR-NEW-052 | US-0140 |
| `src/mcp_htmleditor/library/uploads.py` | create | FR-NEW-028, FR-NEW-029, FR-NEW-030, FR-NEW-031, FR-NEW-032, FR-NEW-033, ... | US-0141, US-0142, US-0143, US-0144 |
| `tests/test_library_upload_http.py` | create | FR-NEW-028, FR-NEW-029, FR-NEW-031 | US-0141 |
| `tests/test_library_upload_e2e.py` | create | FR-NEW-028, FR-NEW-029, FR-NEW-031 | US-0141 |
| `tests/test_library_names_http.py` | create | FR-NEW-032 | US-0142 |
| `tests/test_library_names_e2e.py` | create | FR-NEW-032 | US-0142 |
| `tests/test_library_limits_http.py` | create | FR-NEW-030, FR-NEW-035, FR-NEW-036, FR-NEW-038, FR-NEW-061 | US-0143 |
| `tests/test_library_limits_e2e.py` | create | FR-NEW-030, FR-NEW-035, FR-NEW-036, FR-NEW-038, FR-NEW-061 | US-0143 |
| `tests/test_library_limits_slow.py` | create | FR-NEW-030, FR-NEW-035, FR-NEW-036, FR-NEW-038, FR-NEW-061 | US-0143 |
| `tests/test_library_replace_http.py` | create | FR-NEW-033, FR-NEW-034, FR-NEW-037, FR-NEW-063 | US-0144 |
| `tests/test_library_replace_e2e.py` | create | FR-NEW-033, FR-NEW-034, FR-NEW-037, FR-NEW-063 | US-0144 |
| `tests/test_library_delete_http.py` | create | FR-NEW-039 | US-0145 |
| `tests/test_library_delete_e2e.py` | create | FR-NEW-039 | US-0145 |
| `src/mcp_htmleditor/library/seed.py` | create | FR-NEW-054 | US-0146 |
| `library-seed/manifest.json` | create | FR-NEW-054 | US-0146 |
| `library-seed/from-challenges-to-change.html` | create | FR-NEW-054 | US-0146 |
| `library-seed/bridging-the-gap.html` | create | FR-NEW-054 | US-0146 |
| `pyproject.toml` | modify | FR-NEW-054 | US-0146 |
| `tests/test_library_seed_http.py` | create | FR-NEW-054 | US-0146 |
| `tests/test_library_oplist.py` | create | FR-NEW-026 | US-0147 |
| `Dockerfile` | modify | FR-NEW-057, FR-NEW-062 | US-0148 |
| `docker-compose.prod.yml` | modify | FR-NEW-057, FR-NEW-062 | US-0148 |
| `environments/prod/.env.example` | create | FR-NEW-057, FR-NEW-062 | US-0148 |
| `.dockerignore` | create | FR-NEW-057, FR-NEW-062 | US-0148 |
| `Makefile` | modify | FR-NEW-057, FR-NEW-062 | US-0148 |
| `tests/test_library_deploy.py` | create | FR-NEW-057, FR-NEW-062 | US-0148 |
| `tests/test_library_journeys_http.py` | create | FR-NEW-060, FR-NEW-061, FR-NEW-062 | US-0149 |
| `tests/test_library_journeys_e2e.py` | create | FR-NEW-060, FR-NEW-061, FR-NEW-062 | US-0149 |
| `README.md` | modify | FR-NEW-057, FR-NEW-062 (documentation rule of AGENTS.md) | US-0124, US-0148 |
| `AGENTS.md` | modify | FR-NEW-057 (documentation rule of AGENTS.md) | US-0124, US-0148 |
| `.agent_docs/library.md` | create | FR-NEW-057, FR-NEW-062 (documentation rule of AGENTS.md) | US-0124 then every story |
| `.agent_docs/architecture.md` | modify | FR-NEW-025, FR-NEW-055 (documentation rule of AGENTS.md) | US-0133, US-0140, US-0148 |
| `.agent_docs/testing.md` | modify | FR-NEW-060, FR-NEW-061 (documentation rule of AGENTS.md) | US-0128, US-0148 |
| `.agent_docs/docker.md` | modify | FR-NEW-057 (documentation rule of AGENTS.md) | US-0148 |
| `.agent_docs/observability.md` | modify | FR-NEW-062 (documentation rule of AGENTS.md) | US-0126, US-0145, US-0146 |
| `.agent_docs/html-conventions.md` | modify | FR-NEW-025 (documentation rule of AGENTS.md) | US-0133, US-0137 |
| `.agent_docs/makefile.md` | modify | FR-NEW-057 (documentation rule of AGENTS.md) | US-0148 |
| `skill/topics/editor.md` | modify | FR-NEW-025 (documentation rule of AGENTS.md) | US-0148 |

Counts: 72 code, test and data files (61 created, 11 modified) plus 10 documentation files.

Affected existing tests: none modified, none removed. The local mode suites listed in section 7 are the non regression evidence and stay unmodified. `tests/test_presentation_templates_fullscreen.py` scans `templates/` only, which this design does not touch. `tests/test_agent_docs_size.py` limits `.agent_docs/*.md`; `library.md` stays under it.

Affected documentation: the ten files of the table above; each story updates the ones it touches and US-0148 audits them all.

## 7. Compatibility and risks

Consumers of the local mode see nothing: the five hooks default to the previous expressions, `_EditorServer`'s new parameter has a default, `to_pptx`'s new keyword defaults to `False`, no existing editor script, template or `editor.html` is edited (the library shell text is derived at serve time), `static/editor-library.js` is loaded only by the library shell. Guard: the existing local suites stay unmodified and green (`test_save_safety_e2e.py`, `test_http_deck_files_e2e.py`, `test_http_origin_e2e.py`, `test_http_header_gate_e2e.py`, `test_toolbar_icons_e2e.py`, `test_help_shortcuts_e2e.py`) plus the five local mode tests of the spec (E2E-133 to E2E-137), in `tests/test_library_gate_http.py`, `tests/test_library_visitor_http.py` and `tests/test_library_shell_e2e.py`.

Breaking change declared: `docker-compose.prod.yml` stops being an overlay on `docker-compose.yml` and becomes the standalone VPS file of the owner's convention (DEC-046). The old overlay command in `.agent_docs/docker.md:42-47` is replaced in the same story; `make run-up` and `docker-compose.yml` are untouched.

Ordering constraints: the migrations are append only and numbered by story; the hooks land in US-0133 and `editor-library.js` in US-0134, both before any story that edits through the library; the exporter flag lands in US-0139 before the library offers PPTX in US-0140; the content host route and certificate must exist before the first deployment (US-0148 runbook), and the redirect address `https://slides.scm-platform.org/auth/callback` must be added by the owner in the Google console first (Section 3.3 of the spec, EXC-023c).

Rollback: the work lands as one squash commit; reverting it removes `webserve`; `<library_dir>` and the two nginx routes are removed by the operator, `make undeploy-vps` keeps the data.

Risks, each with its handling:

1. **Second host name (decision for the owner).** FR-NEW-057 and FR-NEW-059 name one address. The content origin is the only way to keep the editor (which reads the framed document) and FR-NEW-052 (E2E-SEC-014 deletion by a deck script) both true (DEC-007). It is not an address a person types: a request that reaches it with no grant is redirected to the library address, and every other host name is refused (E2E-147 uses a third name). Default applied: two names, `slides.scm-platform.org` and `slides-content.scm-platform.org` (covered by the wildcard DNS record, `*.scm-platform.org -> 31.97.54.67`). If the owner refuses a second name, the design degrades to the single origin option, which fails E2E-SEC-014; there is no third choice that passes the tests.
2. **PPTX fidelity.** The image has no Chromium; the library PPTX is the flow engine result (DEC-043). A deck such as the two seeded ones will export with less visual fidelity than the local mode's painted export. Adding Chromium to the image is a separate decision (new dependency, 300 MB). Proposed backlog entry, not written.
3. **A deck script on the content origin can store a change to its own presentation** when a RW viewer has it open (3.5). Accepted by SC-018. Mitigation: history keeps the previous version, 20 versions (`history.py:28`).
4. **Grant revival window.** A grant whose session expired by time is rebound to a newer session of the same address for 24 hours (DEC-037); a stolen expired cookie could be revived in that window. Sign out never revives.
5. **SQLite single writer.** Uploads are read fully before the short write transaction; at most 4 uploads are received at once (DEC-033), the fifth gets `503`. Fine for the stated scale (hundreds of presentations, tens of members).
6. **Test time.** The library suite budget is 90 s inside `make check` (DEC-049); E2E-076 (25 MB at 10 Mbit/s, 21 s plus overhead) carries the `slow` marker.
7. **`__Host-` cookies need https.** Tests run on http loopback with the unprefixed names; the prefix and `Secure` rule is one function (`cookie_name`, `cookie_attributes`) covered by a unit test with an https origin.
8. **The content origin shares the registrable domain `scm-platform.org` with the owner's other services.** A hostile deck script on `slides-content.scm-platform.org` can set cookies with `Domain=scm-platform.org`, which every sibling subdomain would receive; `__Host-` and `__Secure-` names protect the library's own cookies only. Mitigation if a sibling application relies on cookies: serve the content origin from another registrable domain (a setting change, `HTMLEDITOR_LIBRARY_CONTENT_ORIGIN`, plus a certificate). Default applied: the wildcard domain already owned. Decision for the owner.
9. **Not part of this design, noticed**: no `.dockerignore` exists (docker skill: required); the Makefile names `docker` directly instead of a `CONTAINER_ENGINE` variable; the base image is not pinned by digest. Reported, not fixed, except the `.dockerignore` which US-0148 adds because the new image content (the seed decks, 7 MB) makes the build context matter.

Dependencies added: none. Removed: none.

## 8. Security design

### 8.1 Threat surface

Trust boundaries: (1) the network between the browser and nginx (TLS ends at nginx, `X-Forwarded-Proto` and `Host` come from it); (2) Google, reached by the server over TLS (`token_uri`); (3) the browser, which carries cookies and can be driven by another site; (4) a signed in person with bad intent (hand made requests with their own session); (5) uploaded bytes (a presentation is HTML with scripts and pictures); (6) the content origin, where hostile scripts run; (7) names (file, folder, address) typed or uploaded; (8) the machine itself (exporters reading files, the deck rendered by a browser on the server).

Dangerous sinks: file system paths, SQL, HTML output, the redirect after sign in, the exporter's picture reader, the browser that paints a PPTX, request bodies read into memory, cookies and tokens in logs.

### 8.2 Class sweep occurrences: fix site, mechanism, DEC

Fix sites in new modules are planned `file::function` names; the stories name them in their contracts.

**Class A: names reach storage (CWE-22)**

| # | Occurrence | Fix site and mechanism | DEC |
|---|---|---|---|
| A#1, A#2, A#6 | `deck_files.py:54-76`, `http_server.py:355-362` | safe, unchanged; the library handler never calls `_serve_deck_file` (SPEC-0023 does not apply, spec 2.2) | none |
| A#3 | `fileio.py:62` `atomic_write` resolves any path | `library/store.py::Library.presentation_path` builds `files/<fid>/<pid>.html` from two ids matched against `^[0-9a-f]{32}$`; no person's text reaches `atomic_write`; names live only in `presentations.name`. Defence in depth: `names.py::check_file_name` is an allow list (FR-NEW-032) | DEC-025, DEC-029 |
| A#4 | `deck/tools.py:62` `create_file` | not reachable: `access.py::ROUTES` has no route calling `deck.tools`; `tests/test_library_routes_unit.py` fails when a route handler module imports it | DEC-044 |
| A#5 | `state.py:179` `set_file` | never called by the library: `LibraryHandler._served_file` returns the validated path of the current request | DEC-003 |
| A#7 | `history.py:159`, `:170` history keyed by resolved path | a presentation id is never reused, so a recreated name has a new path and an empty history; `Library.delete_presentation` and `delete_folder` remove `<state_dir>/files/<key>/` | DEC-026 |
| A#8 | `export/pptx_images.py:112-117` | `embedded_pictures_only`: an address that is not `data:` is skipped with a warning | DEC-043 |
| A#9 | `export/pptx_paint_shapes.py:196-200` | same flag on the painted context; the library does not paint anyway | DEC-043 |
| A#10 | `export/to_docx.py:135-154` | no route reaches `to_docx` in the library; `/d/<pid>/export/docx` is `Access denied.` for every role | DEC-044 |
| search 2 hits | `http_server.py:383`, `:403`, `:417`, `:993`, `fileio.py:46`, `:71`, `deck/__init__.py:53`, `request_store.py`, `history.py:110` | same mechanisms as A#3, A#5, A#7; request records are deleted with the presentation (DEC-026) | DEC-025, DEC-026 |

**Class B: missing authentication and authorization (CWE-306, CWE-862)**

| # | Occurrence | Fix site and mechanism | DEC |
|---|---|---|---|
| B#1 | `http_server.py:312-330` `do_POST` | `library/server.py::LibraryHandler.do_POST` dispatches only through `access.ROUTES`; each route declares its `Permission`; `authorize` runs before any body read; unknown path is "Access denied." (signed in) or the sign in page (visitor) | DEC-021 |
| B#2 | `http_server.py:276-308` `do_GET` | same dispatcher; deck GET routes need a grant and role >= RO | DEC-021, DEC-037 |
| B#3 | `http_server.py:281-283`, `:873-890` `/health` | `library/server.py::library_health` returns `{"ok": true, "status": "ok", "version": ...}` only, any host | DEC-010 |
| B#4 | `http_server.py:265-271` | safe, inherited | none |
| B#5 | `http_server.py:240-262` gate | not used by the library: host gate for two names, sessions, grants, roles | DEC-007, DEC-021 |
| B#6 | `http_server.py:625-640`, `:842-851` save | `routes_deck.py` authorizes (RW or Admin on the presentation's folder) before calling the inherited `_receive_content`, which reads the body | DEC-021 |
| B#7 | `http_server.py:493-508` `/status` | `routes_deck.py::status` overrides `_serve_status`: `{"mtime", "update_in_progress": false, "update_expires_in": null, "filename": "<name>.html", "poll_interval", "port": 0, "requests_revision"}`, no path, only with a right | DEC-041 |
| B#8 | `http_server.py:419-420`, `:448-450`, `:474-476` `str(exc)` | `_failure_reason` hook; the library returns `exc.strerror` or a fixed text, never a path | DEC-042 |

**Class C: stored script runs with the viewer's identity (CWE-79)**

| # | Occurrence | Fix site and mechanism | DEC |
|---|---|---|---|
| C#1, C#2, C#5 | `editor.html:145`, `http_server.py:376-407` | the shell, the frame and `/content` are answered only on the content origin; the frame keeps `allow-same-origin` because the editor needs it, but that origin holds no library cookie and no library API | DEC-007, DEC-045 |
| C#3, C#11 | SVG policy, a comment | safe | none |
| C#4, C#8, C#9, C#10 | presenter window, `document.write`, `srcdoc`, `postMessage` of the deck templates | they replay the deck on the content origin; receivers check `event.source` (SPEC-0022) unchanged; framing refused by headers | DEC-007, DEC-009 |
| C#6 | `export/pptx_paint.py:136`, `:157` Chromium opens the deck | the library never calls the painted export (`_pptx_options` gives `paint=False`), so no script runs on the machine | DEC-043 |
| C#7 | `render/service.py:170`, `:211` | no route; `render` stays a CLI and MCP tool | DEC-044 |

**Class D: oversized bodies (CWE-770)**

| # | Occurrence | Fix site and mechanism | DEC |
|---|---|---|---|
| D#1 | `http_server.py:85`, `:649-650`, `:788` | `uploads.py::read_upload_body`: right and name checked first, then `Content-Length` against 26 214 400 before reading, exactly that many bytes read, extra bytes ignored and the connection closed, chunked bodies decoded with a hard cap of 26 214 401 bytes, at most 4 uploads in flight | DEC-033 |
| D#2 | `http_server.py:615-620` | safe, inherited by the deck routes (saves keep 50 MiB after authorization) | none |

**Class E: unverified identity claims (CWE-287)**

| # | Occurrence | Fix site and mechanism | DEC |
|---|---|---|---|
| E#1 | new | `library/signin.py::validate_claims`: `iss` is Google, `aud` equals the client id, `exp` in the future, `nonce` equals the attempt's, `email_verified` is true, `email` present; the address is lower cased once; the token comes straight from the token endpoint over TLS | DEC-012 |
| E#2, E#3 | `tracing.py:6`, `:212`; French "principal" | safe | none |

**Class F: open redirect (CWE-601)**

| # | Occurrence | Fix site and mechanism | DEC |
|---|---|---|---|
| F#1 | new | `library/signin.py::safe_destination`: the destination is stored server side in the login attempt (it never travels through Google); accepted only when it matches `^/[A-Za-z0-9._~/%-]*$`, does not start with `//` or `/\`, and contains no `\`, `:` or control character; anything else becomes `/` | DEC-014 |

**Class G: cross site requests and framing (CWE-352, CWE-1021)**

| # | Occurrence | Fix site and mechanism | DEC |
|---|---|---|---|
| G#1, G#4, G#6 | header parsing, JSON only, OPTIONS | safe, inherited | none |
| G#2, G#3 | `http_server.py:245`, `:255`, `:312-330` a missing `Origin` passes | `library/server.py::LibraryHandler._origin_ok`: every request whose method is not `GET`, `HEAD` or `OPTIONS` (`POST`, `DELETE`) needs `Origin` equal to the origin of the receiving host, checked before the session is looked up (exact string compare) and `Sec-Fetch-Site` absent or `same-origin`; JSON routes also need `application/json` and the upload needs the custom `X-File-Name` header (a cross site form cannot send either without a preflight, which `do_OPTIONS` refuses) | DEC-022 |
| G#5 | `http_server.py:276-308` no frame protection | `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'` on every library and shell response | DEC-009 |
| G#7 | new, sign in answer handling | `signin.py::Accounts.finish_login`: `state` is looked up by hash, single use, bound to the browser id cookie hash, expires in 10 minutes | DEC-013 |
| G#8 | new, sign out | `Accounts.end_session` deletes the session row, grants cascade; every later request with the old token finds nothing | DEC-017 |

The occurrence that triggered the spec (the missing authentication of the single file server in front of the network, BL-0019) stays as recorded for the local mode and its image; the web library mode fixes it for itself by DEC-007, DEC-017 and DEC-021.

### 8.3 Where each exploit test runs and what proves the absence of effect

Drivers: `HTTP` is `http.client` against an in process `LibraryServer` with the `Host` header set per request and cookies kept by `tests/library_support.py`; `socket` is `tests/http_support.exchange`; `browser` is Playwright with `--host-resolver-rules` mapping the two test host names to 127.0.0.1. Second channels: `StoredLibrary` (an operator view in `tests/library_support.py`: walks `library_dir` and `state_dir`, reads every table directly), the administrator's session (second principal), `HistoryStore.list_versions` (file history), an evil listener socket (`evil.example` and the loopback port 9 of E2E-SEC-022), the client's download directory (bytes received). Every exploit test is written before the fix and is red for the reason its occurrence names; the story records the RED evidence.

| Test | Class and occurrence | Runs in | Literal payload | Second channel read |
|---|---|---|---|---|
| E2E-SEC-001 | A#3, A#5 | HTTP, `tests/test_library_names_http.py` | `X-File-Name: ..%2F..%2Fetc%2Fpasswd.html` by a RO session | `StoredLibrary.entries()` has no `passwd`, 3 presentations for the administrator, activity table row count |
| E2E-SEC-002 | A#3, A#5 | HTTP, same file | the same name by a RW session | same, plus Lamya's two presentations |
| E2E-SEC-003 | A#3 | HTTP, same file | `a'; DROP TABLE users;--.html` | tables `members`, `folders` row counts and content unchanged (direct query), Lamya and Carol still sign in |
| E2E-SEC-004 | A#3 | browser, `tests/test_library_names_e2e.py` | `<script>alert(1)</script>.html` | no `dialog` event on the administrator's and Carol's folder pages, activity table |
| E2E-SEC-005 | A#3 | HTTP, same file as 001 | folder name `..` then an upload by Dan | `StoredLibrary.entries()` shows nothing outside `files/<fid>/`, 3 folders |
| E2E-SEC-006 | B#1, D#1 | socket, `tests/test_library_limits_http.py` | RO upload, `Content-Length: 31457280` | answer arrives before the body is sent (sent byte counter below 1 MiB), presentation count, free space of `library_dir` |
| E2E-SEC-007 | D#1 | socket, same file | RW upload of 31 457 280 bytes | presentation count, free space, a parallel Lamya request time |
| E2E-SEC-008 | B#1, B#6 | HTTP, `tests/test_library_edit_http.py` | RO grant, `POST /d/<pid>/content` with title `HACKED` | Dan's `GET /content` title, file size 2 097 152, `list_versions` unchanged |
| E2E-SEC-009 | B#1 | HTTP, `tests/test_library_delete_http.py` | RO session `DELETE /api/presentations/<pid>` | administrator folder view, `list_versions`, activity table |
| E2E-SEC-010 | B#1 | HTTP, `tests/test_library_upload_http.py` | RO session upload of `Quarterly Review.html` | administrator view (3 presentations), activity table |
| E2E-SEC-011 | B#1 | HTTP, `tests/test_library_admin_http.py` | RW session `POST /api/folders {"name": "Backdoor"}` | administrator home (3 folders), activity table |
| E2E-SEC-012 | B#2, B#5 | HTTP, `tests/test_library_pptx_http.py` | visitor with the download addresses copied from Carol | bytes received (zero bytes of the deck), the answer is the sign in page |
| E2E-SEC-013 | C#1, C#2, C#5 | browser, `tests/test_library_viewer_e2e.py` | the probe script of the spec | the `probe` element text equals `stored:  \| {} \| {}`; the slide text holds neither address |
| E2E-SEC-014 | C#1, C#2, C#4, C#6, C#7 | browser, `tests/test_library_delete_e2e.py` | the fetch of the list and the `DELETE` of the spec with the real addresses | `probe` text, administrator folder view, activity table, PPTX text scan |
| E2E-SEC-015 | E#1 | HTTP, `tests/test_library_auth_http.py` | fake Google returns `seb.morand@gmail.com` with `email_verified: false` | sessions table row count 0, activity table, administrator view |
| E2E-SEC-016 | F#1 | HTTP with a redirect following client, same file | `next=https://evil.example/phish`, `//evil.example/phish`, `javascript:alert(1)`, `https://slides.scm-platform.org@evil.example/x`, `/\evil.example` | the evil listener visit counter stays 0, the final URL is the home page |
| E2E-SEC-017 | G#2, G#3 | browser, `tests/test_library_delete_e2e.py` | a page on `evil.example` that auto submits a form to the delete route with Dan's cookie | administrator folder view, history, activity table |
| E2E-SEC-018 | G#2, G#3 | HTTP, `tests/test_library_admin_http.py` | the administrator's copied cookie, `POST /api/folders` with no `Origin` | administrator home (3 folders), activity table |
| E2E-SEC-019 | G#7 | HTTP, `tests/test_library_auth_http.py` | the callback address of a login made by another browser id | Carol's home is the sign in page, sessions table, activity table |
| E2E-SEC-020 | G#8 | HTTP, `tests/test_library_open_http.py` | the copied `lib` cookie and the grant cookie after `POST /auth/logout` | bytes received by the tool (none), sessions and grants tables |
| E2E-SEC-021 | B#3, B#7 | HTTP, same file | visitor `GET /health` then the status address | body of both answers scanned for a path, a pid, `Heart Failure Update`, `Cardiology 2027` |
| E2E-SEC-022 | A#8, A#9, C#6 | HTTP, `tests/test_library_pptx_http.py` | the deck with `new WebSocket(...)`, `<img src="file://...">`, `<img src="../secret.png">` | the loopback listener on port 9 counts 0 connections, the PPTX media parts are scanned for the bytes of `secret.png` |
| E2E-SEC-023 | B#1, G#3, A#10 | HTTP, `tests/test_library_requests_http.py` | the six requests of the spec with Carol's grant, in turn | each answer is 403 `Access denied.`, Dan's `GET /requests` holds one request, file size, `list_versions` |
| E2E-SEC-024 | G#5 | browser, `tests/test_library_folders_e2e.py` | an `evil.example` page with two frames | both frames empty (`frame.content()` holds no library text), administrator view of the folder |
| E2E-SEC-025 | D#1 | socket, `tests/test_library_limits_http.py` | `Content-Length: 100` then 31 457 280 bytes; and a chunked body | bytes read by the server (`rfile` counter), connection closed, presentation count, free space |

### 8.4 Secrets, least privilege, never logged

- The Google client secret exists only in the operator's file named by `HTMLEDITOR_GOOGLE_CREDENTIALS_FILE`; `signin.py` is the only reader; it is never logged, traced, echoed or put in a page; the repository carries no credential; the image carries none; the compose file mounts it read only (`/app/data/mcp-htmleditor/google-oauth.json:/data/google-oauth.json:ro`).
- Cookie tokens, tickets, `state`, `nonce`, PKCE verifier and ID tokens are never logged or put in a span attribute. The database stores only SHA 256 digests of tokens (the verifier and nonce are stored because they are needed once, in a row deleted at use).
- Emails and names are not span attributes and not log arguments: logs say `sign in refused: unverified address`, `refused POST /api/folders: origin`, with route and reason only. The activity table holds emails by design (FR-NEW-049) and is readable by the administrator only.
- Least privilege: the container runs as uid 10001 (`Dockerfile:59`), `<library_dir>` is created `0700`, presentation files `0600`, the database `0600`; the credentials file is mounted read only; the process opens no listening socket besides the HTTP port.
- Spans (DEC-048): `auth.google_token` (`http.status_code`), `library.upload` (`file.size`), `library.replace`, `library.delete_presentation`, `library.delete_folder`, `library.seed`, `session.create`; none carries a name, an address or a token.

## 9. Test strategy

Levels: `functional e2e` is the product served by an in process `LibraryServer` (real sockets, real HTTP) driven by an HTTP client or a Playwright browser; `exploit` is a hostile request or script with a second channel proving the absence of effect (section 8.3). Drivers: `HTTP client` (`http.client`, `Host` set per request, cookies per person), `raw socket` (`tests/http_support.py`), `Playwright` (Chromium with `--host-resolver-rules` mapping `slides.test` and `slides-content.test` to 127.0.0.1, the person's time zone fixed per context). Every spec test is at least a functional e2e; the extra unit tests (names, sizes, claims, exporter flag, cookies) are listed in the stories under `Story tests (not spec tests)` and never replace a mapped test.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| E2E-001 | functional e2e | HTTP client | `tests/test_library_journeys_http.py` | US-0149 |
| E2E-002 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-003 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-004 | functional e2e | HTTP client | `tests/test_library_visitor_http.py` | US-0125 |
| E2E-005 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-006 | functional e2e | Playwright | `tests/test_library_folders_e2e.py` | US-0129 |
| E2E-007 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-008 | functional e2e | HTTP client | `tests/test_library_sessions_http.py` | US-0128 |
| E2E-009 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-010 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-011 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-012 | functional e2e | HTTP client | `tests/test_library_sessions_http.py` | US-0128 |
| E2E-013 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-014 | functional e2e | HTTP client | `tests/test_library_home_http.py` | US-0127 |
| E2E-015 | functional e2e | HTTP client | `tests/test_library_foldel_http.py` | US-0131 |
| E2E-016 | functional e2e | HTTP client | `tests/test_library_sessions_http.py` | US-0128 |
| E2E-017 | functional e2e | Playwright | `tests/test_library_folders_e2e.py` | US-0129 |
| E2E-018 | functional e2e | HTTP client | `tests/test_library_home_http.py` | US-0127 |
| E2E-019 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-020 | functional e2e | Playwright | `tests/test_library_folders_e2e.py` | US-0129 |
| E2E-021 | functional e2e | Playwright | `tests/test_library_viewer_e2e.py` | US-0135 |
| E2E-022 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-023 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-024 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-025 | functional e2e | HTTP client | `tests/test_library_delete_http.py` | US-0145 |
| E2E-026 | functional e2e | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-027 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-028 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-029 | functional e2e | Playwright | `tests/test_library_folders_e2e.py` | US-0129 |
| E2E-030 | functional e2e | Playwright | `tests/test_library_viewer_e2e.py` | US-0135 |
| E2E-031 | functional e2e | HTTP client | `tests/test_library_pptx_http.py` | US-0140 |
| E2E-032 | functional e2e | Playwright | `tests/test_library_viewer_e2e.py` | US-0135 |
| E2E-033 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-034 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-035 | functional e2e | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-036 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-037 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-038 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-039 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-040 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-041 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-042 | functional e2e | Playwright | `tests/test_library_pptx_e2e.py` | US-0140 |
| E2E-043 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-044 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-045 | functional e2e | Playwright | `tests/test_library_shell_e2e.py` | US-0134 |
| E2E-046 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-047 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-048 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-049 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-050 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-051 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-052 | functional e2e | Playwright | `tests/test_library_replace_e2e.py` | US-0144 |
| E2E-053 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-054 | functional e2e | Playwright | `tests/test_library_upload_e2e.py` | US-0141 |
| E2E-055 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-056 | functional e2e | HTTP client | `tests/test_library_limits_http.py` | US-0143 |
| E2E-057 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-058 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-059 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-060 | functional e2e | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-061 | functional e2e | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-062 | functional e2e | HTTP client | `tests/test_library_limits_http.py` | US-0143 |
| E2E-063 | functional e2e | Playwright | `tests/test_library_upload_e2e.py` | US-0141 |
| E2E-064 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-065 | functional e2e | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-066 | functional e2e | Playwright | `tests/test_library_replace_e2e.py` | US-0144 |
| E2E-067 | functional e2e | Playwright | `tests/test_library_replace_e2e.py` | US-0144 |
| E2E-068 | functional e2e | HTTP client | `tests/test_library_replace_http.py` | US-0144 |
| E2E-069 | functional e2e | HTTP client | `tests/test_library_replace_http.py` | US-0144 |
| E2E-070 | functional e2e | HTTP client | `tests/test_library_replace_http.py` | US-0144 |
| E2E-071 | functional e2e | Playwright | `tests/test_library_limits_e2e.py` | US-0143 |
| E2E-072 | functional e2e | Playwright | `tests/test_library_limits_e2e.py` | US-0143 |
| E2E-073 | functional e2e | HTTP client + raw socket | `tests/test_library_replace_http.py` | US-0144 |
| E2E-074 | functional e2e | HTTP client | `tests/test_library_limits_http.py` | US-0143 |
| E2E-075 | functional e2e | Playwright | `tests/test_library_limits_e2e.py` | US-0143 |
| E2E-076 | functional e2e | HTTP client + raw socket | `tests/test_library_limits_slow.py` | US-0143 |
| E2E-077 | functional e2e | Playwright | `tests/test_library_replace_e2e.py` | US-0144 |
| E2E-078 | functional e2e | HTTP client | `tests/test_library_replace_http.py` | US-0144 |
| E2E-079 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-080 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-081 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-082 | functional e2e | HTTP client | `tests/test_library_delete_http.py` | US-0145 |
| E2E-083 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-084 | functional e2e | Playwright | `tests/test_library_members_e2e.py` | US-0132 |
| E2E-085 | functional e2e | Playwright | `tests/test_library_journeys_e2e.py` | US-0149 |
| E2E-086 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-087 | functional e2e | HTTP client | `tests/test_library_home_http.py` | US-0127 |
| E2E-088 | functional e2e | HTTP client | `tests/test_library_delete_http.py` | US-0145 |
| E2E-089 | functional e2e | Playwright | `tests/test_library_members_e2e.py` | US-0132 |
| E2E-090 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-091 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-092 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-093 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-094 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-095 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-096 | functional e2e | Playwright | `tests/test_library_admin_e2e.py` | US-0130 |
| E2E-097 | functional e2e | Playwright | `tests/test_library_admin_e2e.py` | US-0130 |
| E2E-098 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-099 | functional e2e | HTTP client | `tests/test_library_foldel_http.py` | US-0131 |
| E2E-100 | functional e2e | HTTP client | `tests/test_library_foldel_http.py` | US-0131 |
| E2E-101 | functional e2e | HTTP client | `tests/test_library_foldel_http.py` | US-0131 |
| E2E-102 | functional e2e | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-103 | functional e2e | HTTP client | `tests/test_library_foldel_http.py` | US-0131 |
| E2E-104 | functional e2e | HTTP client | `tests/test_library_foldel_http.py` | US-0131 |
| E2E-105 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-106 | functional e2e | HTTP client | `tests/test_library_foldel_http.py` | US-0131 |
| E2E-107 | functional e2e | HTTP client | `tests/test_library_foldel_http.py` | US-0131 |
| E2E-108 | functional e2e | HTTP client | `tests/test_library_journeys_http.py` | US-0149 |
| E2E-109 | functional e2e | Playwright | `tests/test_library_viewer_e2e.py` | US-0135 |
| E2E-110 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-111 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-112 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-113 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-114 | functional e2e | HTTP client | `tests/test_library_journeys_http.py` | US-0149 |
| E2E-115 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-116 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-117 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-118 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-119 | functional e2e | Playwright | `tests/test_library_pptx_e2e.py` | US-0140 |
| E2E-120 | functional e2e | HTTP client + raw socket | `tests/test_library_limits_http.py` | US-0143 |
| E2E-121 | functional e2e | Playwright | `tests/test_library_viewer_e2e.py` | US-0135 |
| E2E-122 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-123 | functional e2e | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-124 | functional e2e | HTTP client | `tests/test_library_edit_http.py` | US-0136 |
| E2E-125 | functional e2e | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-126 | functional e2e | Playwright | `tests/test_library_upload_e2e.py` | US-0141 |
| E2E-127 | functional e2e | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-128 | functional e2e | Playwright | `tests/test_library_journeys_e2e.py` | US-0149 |
| E2E-129 | functional e2e | HTTP client | `tests/test_library_seed_http.py` | US-0146 |
| E2E-130 | functional e2e | HTTP client | `tests/test_library_seed_http.py` | US-0146 |
| E2E-131 | functional e2e | HTTP client | `tests/test_library_seed_http.py` | US-0146 |
| E2E-132 | functional e2e | HTTP client | `tests/test_library_seed_http.py` | US-0146 |
| E2E-133 | functional e2e | Playwright | `tests/test_library_shell_e2e.py` | US-0134 |
| E2E-134 | functional e2e | HTTP client | `tests/test_library_visitor_http.py` | US-0125 |
| E2E-135 | functional e2e | HTTP client | `tests/test_library_gate_http.py` | US-0124 |
| E2E-136 | functional e2e | HTTP client | `tests/test_library_gate_http.py` | US-0124 |
| E2E-137 | functional e2e | Playwright | `tests/test_library_shell_e2e.py` | US-0134 |
| E2E-138 | functional e2e | HTTP client | `tests/test_library_journeys_http.py` | US-0149 |
| E2E-139 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-140 | functional e2e | HTTP client | `tests/test_library_delete_http.py` | US-0145 |
| E2E-141 | functional e2e | HTTP client | `tests/test_library_edit_http.py` | US-0136 |
| E2E-142 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-143 | functional e2e | HTTP client | `tests/test_library_seed_http.py` | US-0146 |
| E2E-144 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-145 | functional e2e | HTTP client | `tests/test_library_visitor_http.py` | US-0125 |
| E2E-146 | functional e2e | HTTP client | `tests/test_library_gate_http.py` | US-0124 |
| E2E-147 | functional e2e | HTTP client | `tests/test_library_gate_http.py` | US-0124 |
| E2E-148 | functional e2e | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-149 | functional e2e | HTTP client | `tests/test_library_home_http.py` | US-0127 |
| E2E-150 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-151 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-152 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-153 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-154 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-155 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-156 | functional e2e | Playwright | `tests/test_library_members_e2e.py` | US-0132 |
| E2E-157 | functional e2e | Playwright | `tests/test_library_foldel_e2e.py` | US-0131 |
| E2E-158 | functional e2e | Playwright | `tests/test_library_limits_e2e.py` | US-0143 |
| E2E-159 | functional e2e | HTTP client | `tests/test_library_seed_http.py` | US-0146 |
| E2E-160 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-161 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-162 | functional e2e | HTTP client | `tests/test_library_replace_http.py` | US-0144 |
| E2E-163 | functional e2e | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-164 | functional e2e | Playwright | `tests/test_library_folders_e2e.py` | US-0129 |
| E2E-165 | functional e2e | HTTP client | `tests/test_library_home_http.py` | US-0127 |
| E2E-166 | functional e2e | HTTP client | `tests/test_library_sessions_http.py` | US-0128 |
| E2E-167 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-168 | functional e2e | HTTP client | `tests/test_library_folders_http.py` | US-0129 |
| E2E-169 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-170 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-171 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-172 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-173 | functional e2e | Playwright | `tests/test_library_pptx_e2e.py` | US-0140 |
| E2E-174 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-175 | functional e2e | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-176 | functional e2e | HTTP client | `tests/test_library_members_http.py` | US-0132 |
| E2E-177 | functional e2e | Playwright | `tests/test_library_pptx_e2e.py` | US-0140 |
| E2E-178 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-179 | functional e2e | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-180 | functional e2e | Playwright | `tests/test_library_viewer_e2e.py` | US-0135 |
| E2E-181 | functional e2e | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-182 | functional e2e | HTTP client | `tests/test_library_delete_http.py` | US-0145 |
| E2E-183 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-184 | functional e2e | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-185 | functional e2e | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-186 | functional e2e | HTTP client | `tests/test_library_gate_http.py` | US-0124 |
| E2E-187 | functional e2e | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-188 | functional e2e | Playwright | `tests/test_library_access_e2e.py` | US-0137 |
| E2E-189 | functional e2e | Playwright | `tests/test_library_edit_e2e.py` | US-0136 |
| E2E-SEC-001 | exploit | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-SEC-002 | exploit | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-SEC-003 | exploit | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-SEC-004 | exploit | Playwright | `tests/test_library_names_e2e.py` | US-0142 |
| E2E-SEC-005 | exploit | HTTP client | `tests/test_library_names_http.py` | US-0142 |
| E2E-SEC-006 | exploit | HTTP client + raw socket | `tests/test_library_limits_http.py` | US-0143 |
| E2E-SEC-007 | exploit | HTTP client + raw socket | `tests/test_library_limits_http.py` | US-0143 |
| E2E-SEC-008 | exploit | HTTP client | `tests/test_library_edit_http.py` | US-0136 |
| E2E-SEC-009 | exploit | HTTP client | `tests/test_library_delete_http.py` | US-0145 |
| E2E-SEC-010 | exploit | HTTP client | `tests/test_library_upload_http.py` | US-0141 |
| E2E-SEC-011 | exploit | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-SEC-012 | exploit | HTTP client | `tests/test_library_pptx_http.py` | US-0140 |
| E2E-SEC-013 | exploit | Playwright | `tests/test_library_viewer_e2e.py` | US-0135 |
| E2E-SEC-014 | exploit | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-SEC-015 | exploit | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-SEC-016 | exploit | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-SEC-017 | exploit | Playwright | `tests/test_library_delete_e2e.py` | US-0145 |
| E2E-SEC-018 | exploit | HTTP client | `tests/test_library_admin_http.py` | US-0130 |
| E2E-SEC-019 | exploit | HTTP client | `tests/test_library_auth_http.py` | US-0126 |
| E2E-SEC-020 | exploit | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-SEC-021 | exploit | HTTP client | `tests/test_library_open_http.py` | US-0133 |
| E2E-SEC-022 | exploit | HTTP client | `tests/test_library_pptx_http.py` | US-0140 |
| E2E-SEC-023 | exploit | HTTP client | `tests/test_library_requests_http.py` | US-0138 |
| E2E-SEC-024 | exploit | Playwright | `tests/test_library_folders_e2e.py` | US-0129 |
| E2E-SEC-025 | exploit | raw socket | `tests/test_library_limits_http.py` | US-0143 |

Test data: generated. `LibraryBuilder` creates folders, members and presentations of exact byte sizes and modified times (valid decks padded with an HTML comment, `data-doc-type="presentation"`, the requested number of slides); files that must be invalid are generated by named functions (`deck_without_declaration`, `deck_without_slide`, `deck_missing_title`, `deck_remote_image`, `deck_total_mismatch`). The one exception is the initial content: the two real decks are user provided data, present today at the paths of spec design input 10 and copied into `library-seed/` by US-0146 (status: available, sizes and hashes verified on 2026-11-16, DEC-036).

Time and faults: `FakeClock` moves time by seconds; `Database.connect_hook` simulates an unreadable library; `fileio.replace_file` simulates a full disk; `CutSocket`, `ThrottledSocket` and `pause_at` shape uploads; `FakeGoogle` plays Google. Budget: the library tests together stay under 90 s inside `make check` (DEC-049); `test_library_limits_slow.py` is the only `slow` file.

## 10. Decisions log

Test levels: every `E2E-` is at least a functional e2e (the product served over real HTTP, driven by an HTTP client or a browser) or an exploit test; pure function checks (names, sizes, order keys) are extra unit tests inside the stories, never a replacement of the mapped test (section 9).

- **DEC-001:** Launch the mode with a new click command `mcp-htmleditor webserve [--host] [--port]` and leave `serve` untouched. **Obliged by:** SPEC-0025/FR-NEW-055, SPEC-0025/FR-NEW-056. **Rationale:** `serve` takes one file and its tests are the evidence that the local mode is unchanged (FR-NEW-055); a flag on `serve` would change its signature, its help and the image `CMD`. **Alternatives considered:** `serve --library`; a second console script `mcp-htmleditor-web`. **Source:** design. **Evidence:** `cli.py:170-201` (`serve`, one `FILE` argument).

- **DEC-002:** One process serves every folder and presentation and resolves the presentation per request; no process per deck. **Obliged by:** SPEC-0025/FR-NEW-060, SPEC-0025/FR-NEW-025. **Rationale:** a process per deck needs a port per presentation and the scan is bounded to ten (`PORT_RANGE_START = 7840`, `PORT_RANGE_END = 7849`), so 200 folders cannot be served and E2E-017 fails; E2E-124 (two folders, one name) needs per request resolution anyway. **Alternatives considered:** a router in front of N `serve` processes; per person processes. **Source:** spec design input 1 (`spec.md:4440`), existing code. **Evidence:** `config.py:353-354`, `http_server.py:1101`, `state.py:177-181`, `http_server.py:1144-1152`.

- **DEC-003:** Reuse the editor routes through five overridable methods of `_EditorHandler` (`_served_file`, `_served_name`, `_save_lock`, `_failure_reason`, `_pptx_options`; `_save_lock` returns a context manager, the local one is the existing `threading.Lock`), give `_EditorServer.__init__` a `handler` parameter defaulting to `_EditorHandler`, and implement the library as `LibraryHandler(_EditorHandler)` that overrides `do_GET`, `do_POST` and `_serve_status` only. The defaults reproduce the previous expressions byte for byte. **Obliged by:** SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-055. **Rationale:** the save pipeline (conflict, history, time bounds, 50 MiB cap, request loop routes) is the editor's own behavior and must not be duplicated (zero duplication rule); a handler per presentation object would change every method signature. **Alternatives considered:** copy the handler methods into the library; a `DeckContext` object threaded through every method; monkeypatching `get_state()` per thread. **Source:** design. **Evidence:** `http_server.py:376`, `:389`, `:409`, `:432`, `:458`, `:493`, `:578`, `:625`, `:653` (the nine readers of `current_file`), `:1027-1032` (`_EditorServer`).

- **DEC-004:** Add no third party dependency and keep the project stack: stdlib `http.server`, `sqlite3`, `urllib`, `secrets`, `hashlib`, `unicodedata`; click, synchronous I/O. The skill MUST rules for FastAPI, Typer and async first are not applied. **Obliged by:** SPEC-0025/FR-NEW-055 (the local mode keeps its server and CLI), ASK ONLY FOR category 2. **Rationale:** `.agent_docs/python.md` records click and synchronous I/O as documented deviations; moving the editor to FastAPI would rewrite `http_server.py` and break FR-NEW-055. A proposal for a future async server is a backlog idea, not written. **Alternatives considered:** FastAPI + uvicorn + aiosqlite + authlib (four new dependencies). **Source:** existing code and constitution. **Evidence:** `pyproject.toml:12-22`, `.agent_docs/python.md` (Deviations), `http_server.py:117`.

- **DEC-005:** Settings fields `library_origin`, `library_content_origin`, `library_dir_override` (property `library_dir`), `google_credentials_override` (property `google_credentials_file`), `library_seed_dir_override` (property `library_seed_dir`), env prefix `HTMLEDITOR_`, names added to `_SIGNIFICANT_ENV_VARS` and the path fields to `_PATH_FIELDS`. **Obliged by:** SPEC-0025/FR-NEW-057, SPEC-0025/FR-NEW-059, SPEC-0025/FR-NEW-062, spec section 3.3 (credentials supplied by the operator). **Rationale:** AGENTS.md: configuration only through `Settings`, no `os.environ` elsewhere; the memoization key must include the new names or tests changing them read stale settings. **Alternatives considered:** reading the credentials path from a CLI option only; hard coding the origins. **Source:** AGENTS.md, existing code. **Evidence:** `config.py:53-88`, `:91-117`, `:256-272`.

- **DEC-006:** The administrator address is the constant `ADMIN_EMAIL = "seb.morand@gmail.com"` in `library/access.py`, compared after lower casing; it is not a setting, not a table value and not read from the member lists. **Obliged by:** SPEC-0025/FR-NEW-011, SPEC-0025/FR-NEW-012. **Rationale:** the spec says fixed, not configurable by the interface; a setting could be changed by a misconfigured `.env`; a constant also makes "no other administrator" a one line invariant. **Alternatives considered:** `Settings.library_admin_email`. **Source:** spec 3.3. **Evidence:** n/a (new).

- **DEC-007:** Serve two origins from one listener: the library origin (pages, API, session) and the content origin (the editor shell, the deck frame and the routes of one presentation); the `Host` header must equal the netloc of one of the two configured origins, otherwise `403 {"error": "forbidden host"}`. **Obliged by:** SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-059, SPEC-0025/FR-NEW-057. **Rationale:** the editor reads and rewrites the framed deck through `frame.contentDocument`, so the deck must be same origin with the shell; a script of that deck is therefore as powerful as the shell, so the shell and deck must live on an origin that has no session and no library API. A sandbox without `allow-same-origin` breaks the editor and makes `document.cookie` throw instead of reading empty (E2E-SEC-013). **Alternatives considered:** one origin with the current frame (E2E-SEC-014 fails: the script deletes with the viewer's cookie); sandboxed frame, opaque origin (editor breaks); a subdomain per presentation (wildcard certificate, DNS); process per deck. **Source:** spec design input 4 (`spec.md:4443`), existing code. **Evidence:** `editor.html:145`, `editor-save.js:18`, `editor-edit.js:21`, `editor-undo.js:41`, `http_server.py:376-407`.

- **DEC-008:** Redirect `X-Forwarded-Proto: http` to the configured origin of the receiving host with `308`; nginx already redirects port 80 to 443 for every vhost. **Obliged by:** SPEC-0025/FR-NEW-058. **Rationale:** the product sees plain connections behind TLS termination (spec design input 8); the redirect target is built from `Settings`, never from the request, so it cannot be turned into an open redirect; testable without nginx. **Alternatives considered:** rely on nginx only (untestable here); trust `X-Forwarded-Host`. **Source:** spec design input 8, deployment convention. **Evidence:** `docker-my-services/services/nginx/templates/site.conf.tpl` (`return 301 https://$host$request_uri;`, `proxy_set_header X-Forwarded-Proto $scheme`).

- **DEC-009:** Every library and shell response carries `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, a `Content-Security-Policy` and, when the origin scheme is https, `Strict-Transport-Security: max-age=31536000`; library pages use `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`, JSON answers `default-src 'none'; frame-ancestors 'none'`, the editor shell `frame-ancestors 'none'`, and the deck frame answer `frame-ancestors 'self'` with `X-Frame-Options: SAMEORIGIN`. `library.js` handles `pageshow` with `persisted` by reloading. **Obliged by:** SPEC-0025/FR-NEW-072, SPEC-0025/FR-NEW-008, SPEC-0025/FR-NEW-001. **Rationale:** `same-origin`, not `no-referrer`: under `no-referrer` a browser form post (the Sign out button) sends `Origin: null` (Fetch spec, serializing a request origin), which the exact `Origin` rule of DEC-022 would refuse; `same-origin` sends the real origin on same origin posts and no Referer to other sites. Frame protection is the whole mechanism for E2E-SEC-024 (G#5); `no-store` plus the `pageshow` handler is what keeps library content out of the Back button after sign out (E2E-006). **Alternatives considered:** `Clear-Site-Data` on sign out (https only, not testable on http loopback). **Source:** design. **Evidence:** `http_server.py:714-725` (`_send_no_store_headers`, the existing header idiom).

- **DEC-010:** `GET /health` is answered before the host gate on any host name and returns `{"ok": true, "status": "ok", "version": <version>}` and nothing else. **Obliged by:** SPEC-0025/FR-NEW-073, SPEC-0025/FR-NEW-059. **Rationale:** the image `HEALTHCHECK` calls `http://127.0.0.1:7842/health` (`Dockerfile:63-64`) and must keep working; the local payload names the file, pid and port (`http_server.py:873-890`), which B#3 forbids. **Alternatives considered:** reuse `health_payload()` with null fields. **Source:** spec FR-NEW-073. **Evidence:** `http_server.py:281-283`, `:873-890`, `Dockerfile:63-64`.

- **DEC-011:** A request with no valid session and no grant gets the sign in page (`200`, one link `Sign in with Google`, the requested path kept in the link as `next`) at every library origin address, and a `302` to the library origin on the content origin; the only public files are `/lib/library.css` and `/lib/library.js` on the library origin and the editor's `/static/*` files on the content origin (product code, no library content). **Obliged by:** SPEC-0025/FR-NEW-001, SPEC-0025/FR-NEW-009. **Rationale:** FR-NEW-001 says "an address that names no page also gives the sign in page" and FR-NEW-009 says a direct link ends on the linked page after sign in, so the page is rendered at the address itself and carries the destination; the two assets are the sign in page's own style and script (E2E-149 probes other paths). **Alternatives considered:** `302 /` (loses the destination); `401`. **Source:** spec FR-NEW-001 business rules. **Evidence:** n/a (new).

- **DEC-012:** Sign in is the OpenID Connect authorization code flow with PKCE (`S256`), scopes `openid email`, `prompt=select_account`, `state` and `nonce`, the code exchanged by `urllib.request` at `token_uri` with the client secret; the ID token received from that exchange is decoded (no signature verification) and accepted only when `iss` is `accounts.google.com` or `https://accounts.google.com`, `aud` equals the client id, `exp` is in the future, `nonce` equals the attempt's, `email_verified` is true and `email` is present; the address is lower cased once. **Obliged by:** SPEC-0025/FR-NEW-002, SPEC-0025/FR-NEW-068, SPEC-0025/FR-NEW-071. **Rationale:** OIDC Core 1.0 section 3.1.3.7 item 6: "If the ID Token is received via direct communication between the Client and the Token Endpoint (which it is in this flow), the TLS server validation MAY be used to validate the issuer in place of checking the token signature." (read 2026-11-16); this avoids a JWT and RSA dependency. **Alternatives considered:** `google-auth` (new dependency); Google's `tokeninfo` endpoint (documented for debugging, adds a call); the userinfo endpoint. **Source:** spec design input 22, OIDC Core 1.0. **Evidence:** `https://openid.net/specs/openid-connect-core-1_0.html` section 3.1.3.7.

- **DEC-013:** A login attempt is a row (`state_hash`, `nonce`, `verifier`, `destination`, `browser_hash`, `created_at`); `/auth/start` sets the cookie `lib-b` (a random browser id) when absent and stores `sha256(browser id)`; the callback accepts an answer only when the `state` hash exists, the attempt is under 10 minutes old and its `browser_hash` equals the hash of the cookie, and deletes the row first (single use). **Obliged by:** SPEC-0025/FR-NEW-071, SPEC-0025/FR-NEW-002. **Rationale:** the browser id (not one cookie per attempt) lets two tabs each complete a sign in (E2E-183); deleting before the exchange makes a replay find nothing (E2E-184); the binding is what stops E2E-SEC-019 (an answer made for someone else). **Alternatives considered:** the `state` in a cookie only (two tabs overwrite each other); signed `state`. **Source:** design. **Evidence:** n/a (new).

- **DEC-014:** The post sign in destination is taken from `next`, stored server side in the attempt and accepted only when it matches `^/[A-Za-z0-9._~/%-]*$`, does not start with `//` or `/\`, and has no `\`, `:` or control character; any other value becomes `/`. **Obliged by:** SPEC-0025/FR-NEW-069. **Rationale:** the value never travels through Google, so there is nothing to tamper with after the check; an allow list is shorter than a deny list. **Alternatives considered:** parse with `urlsplit` and compare the host (accepts `/\evil.example` in some browsers). **Source:** spec FR-NEW-069. **Evidence:** n/a (new).

- **DEC-015:** `library/signin.py` reads the operator's credentials file named by `Settings.google_credentials_file` (`{"web": {"client_id", "client_secret", "auth_uri", "token_uri", "redirect_uris"}}`), nowhere else; the redirect URI sent to Google is `<library origin>/auth/callback`; at start `webserve` logs a warning when that address is not in `redirect_uris` and an error when the file is missing, and still starts. **Obliged by:** SPEC-0025/FR-NEW-004, spec section 3.3 (dependency, EXC-023c). **Rationale:** AGENTS.md rule that settings are read only through `Settings`; starting without the file keeps tests and the sign in page working and gives the stated message at the first attempt. **Alternatives considered:** refuse to start (blocks `make check` style tests of the gate story). **Source:** spec 3.3, user's file format. **Evidence:** the format of `~/.credentials/scm-pwd-web.json` as given in the request.

- **DEC-016:** Any failure of the exchange (network, non 200, bad JSON, failed validation, unverified address, unknown or reused `state`, wrong browser id) shows `Sign-in is unavailable. Try again later.` on the sign in page and creates no session; `error=access_denied` (consent cancelled) shows the sign in page with no message; the token request timeout is 10 seconds. **Obliged by:** SPEC-0025/FR-NEW-004, SPEC-0025/FR-NEW-002, SPEC-0025/FR-NEW-068, SPEC-0025/FR-NEW-071. **Rationale:** one text for every cause reveals nothing about members (FR-NEW-068). **Alternatives considered:** a message per cause. **Source:** spec. **Evidence:** n/a.

- **DEC-017:** A session is a row (`id_hash` = sha256 of a 256 bit token, `email`, `created_at`, `expires_at = created_at + 2 592 000 s`), the cookie is `__Host-lib` (`lib` on http) with `HttpOnly`, `SameSite=Lax`, `Secure` on https, `Max-Age=2592000`; `expires_at` is never updated; a request is signed in only while `now < expires_at`; sign out deletes the row. **Obliged by:** SPEC-0025/FR-NEW-005, SPEC-0025/FR-NEW-006, SPEC-0025/FR-NEW-008, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-072. **Rationale:** server side rows make sign out effective for a copied credential (E2E-SEC-020) and survive restarts (E2E-166); the `__Host-` prefix stops a sibling subdomain (the content origin hosts hostile scripts) from planting a session cookie on the library origin. **Alternatives considered:** HMAC signed cookie (cannot be revoked); JWT. **Source:** design. **Evidence:** n/a (new).

- **DEC-018:** Roles are never stored in a session or a grant: every request recomputes the role from `members` (and `ADMIN_EMAIL`), so a change applies to the next action. **Obliged by:** SPEC-0025/FR-NEW-048, SPEC-0025/FR-NEW-021. **Rationale:** the simplest rule that makes E2E-116 to E2E-118 true. **Alternatives considered:** a role cache with invalidation. **Source:** spec design input 2. **Evidence:** n/a.

- **DEC-019:** Checks run in this order for a state changing API request: `Origin` (DEC-022), session, permission of the route (administrator first), then payload validation (role value, address, name). **Obliged by:** SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-012, SPEC-0025/FR-NEW-014. **Rationale:** E2E-112 (a RW member posts the role "Admin") must get `Access denied.` and E2E-161 (the administrator posts it) must get `This is not a valid role.`; the administrator is never refused whatever the member rows hold (FR-NEW-014), because `role_in` returns Admin before it reads `members`. **Alternatives considered:** validate payload first. **Source:** spec agent notes on E2E-112 and E2E-161. **Evidence:** n/a.

- **DEC-020:** Presentation and folder addresses carry random ids, never names: `/f/<folder id>`, `/open/<presentation id>`, `/d/<presentation id>/`; a "direct link" is one of these. **Obliged by:** SPEC-0025/FR-NEW-009, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-053. **Rationale:** names may hold accents, apostrophes, markup and 100 characters; ids never need escaping in a URL and never reveal a name; a stale id is simply unknown (E2E-025). **Alternatives considered:** names in paths. **Source:** design. **Evidence:** n/a.

- **DEC-021:** `access.ROUTES` is a table `(origin, method, pattern, permission, handler)`; `LibraryHandler` finds the route, resolves the person (session, or grant on the content origin), computes the role for the route's target and calls `authorize(role, permission)` before any body is read and before the handler runs; a path in no row is "Access denied." for a signed in person and the sign in page for a visitor. A test walks the table and fails for a row without a permission. **Obliged by:** SPEC-0025/FR-NEW-001, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-020, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-023. **Rationale:** Class B is "an action reachable without the check"; one table and one place that calls the check removes the possibility by construction and makes the permission matrix testable. **Alternatives considered:** a decorator per handler (can be forgotten); checks inside each handler. **Source:** spec 14.2 class B. **Evidence:** `http_server.py:276-308`, `:312-330` (the dispatch being replaced).

- **DEC-022:** Every state changing request (any method other than `GET`, `HEAD` and `OPTIONS`: `POST` and `DELETE`) is refused with `Access denied.`, before the session is looked up, unless `Origin` is present and equals the origin of the receiving host exactly, and `Sec-Fetch-Site`, when present, is `same-origin` (or `none`); JSON routes also require `Content-Type: application/json`, the upload requires the header `X-File-Name`. The local rule that accepts a missing `Origin` is not used. **Obliged by:** SPEC-0025/FR-NEW-070, SPEC-0025/FR-NEW-023. **Rationale:** a request with no `Origin` is what a command line tool copying a cookie sends (E2E-SEC-018) and a page of another site sends `Origin: https://evil.example` (E2E-SEC-017); the content origin is same site but not same origin, so its scripts fail the exact compare, and a cross origin `DELETE` is preflighted and refused by `do_OPTIONS` (E2E-SEC-014). The check precedes the session lookup because a cross site form post carries no `SameSite=Lax` cookie, so the person would otherwise get the sign in page where FR-NEW-070 asks for `Access denied.`. **Alternatives considered:** a synchronizer token (adds state and pages; a script of the content origin cannot read the library origin anyway); `SameSite=Strict` (breaks the return from Google). **Source:** spec 14.2 class G. **Evidence:** `http_server.py:255-259` (the missing `Origin` that passes), `:793-796` (`check_content_type`).

- **DEC-023:** Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. **Obliged by:** SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020. **Rationale:** identical bytes make the missing and forbidden cases indistinguishable (E2E-023, E2E-024 compare on the wire). **Alternatives considered:** per route messages. **Source:** spec FR-NEW-010. **Evidence:** n/a.

- **DEC-024:** A `sqlite3.Error` or an `OSError` while a library page or the API reads the stored library gives `503` and `The library is unavailable. Try again later.` with no partial content; the next request after the library can be read again works with no restart. **Obliged by:** SPEC-0025/FR-NEW-017, SPEC-0025/FR-NEW-062. **Rationale:** the connection is opened per thread and per request transaction, so a recovered database is read again at once. **Alternatives considered:** a global "degraded" flag. **Source:** spec FR-NEW-017. **Evidence:** n/a.

- **DEC-025:** Metadata in one SQLite file (`<library_dir>/library.db`, WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one connection per thread, `BEGIN IMMEDIATE` for writes, migrations numbered by `PRAGMA user_version`); presentation bytes in files named by two random 32 hex ids (`files/<folder id>/<presentation id>.html`); ids validated against `^[0-9a-f]{32}$` before a path is built; names exist only as column values. **Obliged by:** SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-063, SPEC-0025/FR-NEW-060. **Rationale:** unique keys give case insensitive uniqueness on any file system (spec design input 3) and the race of FR-NEW-037; an id built path cannot be traversed (A#3, A#5, A#7). Files, not blobs, because `atomic_write`, the history, the exporters and the conflict check already work on paths and `st_mtime`. **Alternatives considered:** files named after presentations with sidecar JSON (case and traversal problems); blobs in SQLite (rewrites the whole save pipeline); folders as directories named after the folder. **Source:** spec design input 3. **Evidence:** `fileio.py:49-98`, `history.py:117-182`, `state.py:211-214`.

- **DEC-026:** Writes of presentation bytes use `atomic_write(path, data, reason=...)` (reasons `browser-save`, `keep-mine`, `replace`); history and request records stay in the state directory keyed by the resolved path; `delete_presentation` and `delete_folder` remove the row first, then the file, then `<state_dir>/files/<key>/` (history, requests, update flag) of each presentation. **Obliged by:** SPEC-0025/FR-NEW-026, SPEC-0025/FR-NEW-034, SPEC-0025/FR-NEW-039, SPEC-0025/FR-NEW-043, SPEC-0025/FR-NEW-063. **Rationale:** reuse, not rewrite; removing the row first makes the presentation unreachable at once; a leftover directory after a crash is unreachable because a new presentation has a new id and so a new key. **Alternatives considered:** a history table; keeping history after deletion. **Source:** spec design input 3. **Evidence:** `fileio.py:49-67`, `history.py:28`, `:108-115`, `request_store.py:87-90`.

- **DEC-027:** A presentation row is unique on (`folder_id`, `name_key`). A new presentation: the bytes are first written to `files/<fid>/<new id>.html` with `atomic_write` (outside any transaction, so the slow write never holds the database), then `BEGIN IMMEDIATE` checks the key and inserts the row and the activity line; if the key exists the transaction rolls back, the unused file is removed and the outcome is `collision` (the existing name is returned for the question); a unique violation is treated the same. A replacement: under the presentation lock, `SELECT` the row, `atomic_write(..., reason="replace")`, then a short transaction for the activity line. Lock order is always the presentation lock first, then the database transaction; a save holds only the presentation lock and reads the database. **Obliged by:** SPEC-0025/FR-NEW-033, SPEC-0025/FR-NEW-037, SPEC-0025/FR-NEW-034. **Rationale:** serialization by the database makes "the upload that finishes second meets the question" true (E2E-070). **Alternatives considered:** a lock in Python (not shared by a restart race); checking the file system. **Source:** spec FR-NEW-037. **Evidence:** n/a.

- **DEC-028:** One `threading.Lock` per presentation id, held by `_save_lock()`, by an upload replacement and by a deletion; `_save_lock()` returns a context manager that acquires the lock and then re-checks that the presentation row still exists, raising `SaveRefusal(403, {"error": "Access denied.", "code": "denied"})` when it does not, so a save that lost the race with a deletion creates nothing; the conflict check (`check_conflict`) runs inside it. **Obliged by:** SPEC-0025/FR-NEW-027, SPEC-0025/FR-NEW-063. **Rationale:** E2E-189 (two saves in the same second): one stored, the other gets the conflict notice, no mix. Locks live in a dict guarded by one lock. **Alternatives considered:** the global `state.save_lock` (serializes unrelated presentations). **Source:** design. **Evidence:** `http_server.py:633-635`, `:833-839`, `state.py:66`.

- **DEC-029:** Names go through `library/names.py`: `compose` (NFC), `name_key` (NFC of the lower cased composed text), `order_key` (accents removed by NFD and dropping `Mn`, lower case, then the exact name); file names are an allow list (Latin script letters by `unicodedata.name` starting with `LATIN`, `Mn` only after such a letter, ASCII digits, space, `. _ - ( ) '`), at most 100 composed characters before `.html`, no leading dot, no edge space, not only spaces; folder names are letters of any script (`L*`), `M*`, decimal digits (`Nd`), space and hyphen, 1 to 60 composed characters after trimming; addresses match `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` after trimming and are stored lower case. All pages build text through `pages.esc()` (`html.escape(quote=True)`), and JavaScript writes with `textContent`. **Obliged by:** SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-042, SPEC-0025/FR-NEW-046, SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-033. **Rationale:** one module owns the closed lists so a hostile name cannot be accepted by one route and refused by another; `lower()` rather than `casefold()` keeps `ß` and `SS` different names as the spec's "without regard to case" says. **Alternatives considered:** regex only; `casefold`. **Source:** spec design input 15. **Evidence:** n/a (new).

- **DEC-030:** Activity is the table `activity`, one row per successful action written in the same transaction as the action, with the final line text and the actor's lower case address; after each insert rows older than the 500 newest are deleted; the page reads `ORDER BY id DESC LIMIT 500`. Refusals, sign ins and stored changes never write. **Obliged by:** SPEC-0025/FR-NEW-049, SPEC-0025/FR-NEW-050, SPEC-0025/FR-NEW-051. **Rationale:** a line is either committed with its action or not at all; bounding at insert keeps the table small. **Alternatives considered:** a log file; counting on read. **Source:** spec FR-NEW-050. **Evidence:** n/a.

- **DEC-031:** Folder order is `order_key(name)`; presentation order is newest `st_mtime` truncated to the minute first, then `order_key(name)`, then the exact name; the date is sent as `<time datetime="<UTC ISO>">` and formatted by `library.js` from `Date` getters in the browser's zone as `D Mon YYYY HH:MM` (24 hour, no leading zero on the day, English month abbreviations, no seconds); the size is formatted server side by `format_size` from the exact byte count (KB and MB with one decimal rounded half up). **Obliged by:** SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-018. **Rationale:** the server must not guess the person's time zone (spec design input 14); rounding half up needs `Decimal` or integer arithmetic, not `round()` (banker's). **Alternatives considered:** formatting the date on the server in UTC. **Source:** spec FR-NEW-018. **Evidence:** n/a.

- **DEC-032:** Time and faults are injected, not patched globally: `LibraryServer(clock=time.time)` hands the clock to every repository; the test seams are `Database.connect` (raise `sqlite3.OperationalError` to simulate an unreadable library), `fileio.replace_file` (`fileio.py:44-46`, already the documented failure seam, raise `OSError(errno.ENOSPC)`), and a socket wrapper in tests that cuts a connection at a byte count. **Obliged by:** SPEC-0025/FR-NEW-005, SPEC-0025/FR-NEW-006, SPEC-0025/FR-NEW-017, SPEC-0025/FR-NEW-038. **Rationale:** the 30 day boundary tests need to move a clock by minutes; no production code reads `time.time` directly. **Alternatives considered:** `freezegun` (new dependency). **Source:** spec design input 13. **Evidence:** `state.py:65` (`self.clock`), `fileio.py:44`.

- **DEC-033:** The upload is `POST /api/folders/<fid>/presentations` with the raw body, `X-File-Name` (percent encoded UTF-8) and `Content-Length`; checks run in the order right, extension, name, size (declared length against 26 214 400), then the body is read as exactly the declared count (at most 26 214 400) and checked for validity, then the collision; a `Transfer-Encoding: chunked` body is accepted on this route only and decoded with a hard stop at 26 214 401 bytes; extra bytes beyond the declared length are never read; an answer given before the body was read (refusal, oversize) is followed by `shutdown(SHUT_WR)`, a bounded discard of at most 1 MiB or 2 seconds of the client's input with `socket.recv` (not through `rfile`, so the byte counter of the hostile length test stays at the declared length) and then the close, because closing a socket that still holds unread input sends a TCP reset that can destroy the answer before the client reads it (the server is HTTP/1.0 and closes after each answer); at most 4 uploads are received at once (a fifth gets `503` with `The upload failed. Nothing was changed.`). **Obliged by:** SPEC-0025/FR-NEW-028, SPEC-0025/FR-NEW-029, SPEC-0025/FR-NEW-030, SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038. **Rationale:** D#1 and E2E-SEC-025; the role is known before one byte is read (E2E-SEC-006); bytes are held in memory only after the checks that need no body, and the write transaction is short. **Alternatives considered:** multipart (parser dependency, no gain); streaming to a temp file (lint needs the whole text). **Source:** spec 14.2 class D, FR-NEW-028. **Evidence:** `http_server.py:615-620`, `:781-790`, `http_server.py:215-238` (the gate refuses `Transfer-Encoding` elsewhere).

- **DEC-034:** Validity is: decode UTF-8 (failure: `the file is not valid UTF-8 text`); `deck_from_text`; the root `<html data-doc-type="presentation">` must be present, else `the file is not declared as a presentation` (an empty file included); at least one slide, else `the file has no slide`; then the first problem is the first item of `lint_deck(deck)` whose severity is `error`, its `message` only. **Obliged by:** SPEC-0025/FR-NEW-031. **Rationale:** `detect_doc_type` reads a file with slides and no declaration as a presentation (`deck/__init__.py:76-83`), so the explicit declaration check is new; warnings (L010) are never first. **Alternatives considered:** `lint_file` on a temp file (writes the upload first). **Source:** spec design inputs 5 and 19. **Evidence:** `deck/__init__.py:61-83`, `deck/lint.py:51-57`, `:78-95`.

- **DEC-035:** "Replace" repeats the whole upload with the header `X-Replace: 1`; the server runs every check again and replaces under DEC-027 and DEC-028 with `atomic_write(..., reason="replace")` (previous bytes kept in history), keeping the presentation's name, id, requests and suggestions. **Obliged by:** SPEC-0025/FR-NEW-033, SPEC-0025/FR-NEW-034. **Rationale:** stateless server, no staged upload to expire; validation always wins over the question (E2E-068); the cost is one more transfer after a "Replace" click. **Alternatives considered:** staging the validated upload under a token. **Source:** design. **Evidence:** `fileio.py:49-67`.

- **DEC-036:** The initial content is a manifest `library-seed/manifest.json` (folder name, members, per presentation: name, file, byte count, sha256, UTC modified time) and the two decks copied unchanged from the paths in the spec into `library-seed/`; `seed.py` runs in the first start inside one transaction guarded by `meta('seeded')`: it verifies each sha256, creates the folder and the member, copies the files and sets their `st_mtime` with `os.utime`, then writes the flag; it records no activity line; packaging uses `[tool.hatch.build.targets.wheel.force-include]` and `COPY library-seed/` in the Dockerfile. **Obliged by:** SPEC-0025/FR-NEW-054, SPEC-0025/FR-NEW-062. **Rationale:** the flag in the same transaction makes "never again, even when every folder was deleted" true (E2E-159); the sha256 check makes "unchanged" testable (E2E-132). **Alternatives considered:** seeding by shell script at deploy time (not tied to "first start"); copying into `templates/` (every presentation there is scanned by `test_presentation_templates_fullscreen.py`). **Source:** spec design input 10. **Evidence:** the two files exist: `wiip2026.html` 3 901 499 bytes sha256 `85dd0f464c068eb8fb784627d1f2f4beeaabf7162f7381e334007cb8a15155dd`; `wcbip2026-v1.html` 3 278 888 bytes sha256 `011a91e9d03995fb0efe30d5f794f77706ba42c76d18d388f89b2ddb1a5e4eb2`, modified 2026-11-15 19:57:19 and 19:57:18 UTC.

- **DEC-037:** Opening a presentation is a one time ticket then a grant: `GET /open/<pid>` (library origin, role >= RO) inserts a ticket (sha256 of a random token, 60 s, bound to the session and the presentation) and redirects to `<content origin>/enter?t=`; `/enter` deletes the ticket, inserts a grant (`token_hash`, `session_id_hash`, `presentation_id`) and sets the cookie `__Secure-d` (`d` on http) with `Path=/d/<pid>/` and no `Max-Age`. A grant is valid while its session is alive; when the session expired by time and the same address has a newer live session, the grant is rebound to it (only within 24 hours of expiry, rows purged after that); a grant whose session was ended by sign out is gone (cascade) and never revives. Answers: `Live(email)`, `Ended` (a cookie that no longer resolves: session expired, signed out, purged) and `Absent` (no cookie). **Obliged by:** SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-007, SPEC-0025/FR-NEW-072, SPEC-0025/FR-NEW-048. **Rationale:** a per presentation HttpOnly credential on the content origin gives the editor routes an authority limited to one presentation; the path scope means the browser sends only the matching grant, so cookie count per request stays at one (a `__Host-` name per presentation would put every opened presentation's cookie in every request and overflow nginx's 8 KB header limit after about 75 presentations); the prefix `__Host-` cannot be used because it forces `Path=/`; the rebinding is what lets E2E-013 and E2E-188 store after signing in again in another window. **Alternatives considered:** a capability token in the URL (a copied address would work without a session, E2E-SEC-012 fails); one grant for all presentations (a hostile script could reach another). **Source:** design. **Evidence:** n/a (new).

- **DEC-038:** The library shell is `static/editor.html` served with three server side edits (the frame `src` and the download `href` get the base `/d/<pid>`; a `<meta name="editor-config">` and `<script src="/static/editor-library.js">` are inserted before the first script) and one new classic script, `static/editor-library.js`, which wraps `window.fetch` to prefix the base on the eight editor paths and redefines `reloadFrame` (the one editor function that assigns an absolute path to the frame, `editor.js:475-477`); no existing editor script, template or the file `editor.html` itself is edited. **Obliged by:** SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-055. **Rationale:** several presentations open at once on one origin need the presentation in the path; the editor scripts fetch absolute paths at seven sites, and editing them would touch four shared files for a mode the local user never sees, whereas a script that exists only in the library shell leaves the local mode byte identical (FR-NEW-055) by construction. **Alternatives considered:** an `editorUrl()` helper edited into `editor-save.js`, `editor.js`, `editor-menus.js`, `editor-requests.js`; a `<base href>` (does not affect absolute paths); a cookie naming the current presentation (two tabs collide). **Source:** design. **Evidence:** `editor-save.js:35`, `editor.js:84`, `:411`, `:432`, `editor-menus.js:39`, `editor-requests.js:109`, `:221`, `editor.html:50`, `:145`.

- **DEC-039:** The read only form is both server and page: the server refuses every write route to a role without `EDIT` (DEC-021) and the shell route inserts, for a role without `EDIT`, a `<style>` block with `display: none !important` rules for `#edit-mode-btn`, `#undo-btn`, `#redo-btn`, `#requests-toggle`, `#ask-ai-btn`, `#notes-btn`, `#toolbar-slide-actions`, `#toolbar-doc-actions`, `#export-docx-btn`, `#requests-side`, `#ask-ai-panel`, `#notes-panel` (the editor's own CSS gives some of them `display: inline-flex`, `editor.css:620-624`, and its scripts rewrite `style.display`, so the `hidden` attribute would not hold, and no node is removed because `editor-requests.js:93` reads `#requests-side`), while `editor-library.js` registers at evaluation (it loads first) a capture phase `keydown` guard and a capture phase `message` guard that stop the key E and the deck's edit toggle message before the editor's own listeners; the editor scripts are not edited. **Obliged by:** SPEC-0025/FR-NEW-023, SPEC-0025/FR-NEW-025. **Rationale:** hiding controls is usability, the server check is the control (E2E-SEC-008). **Alternatives considered:** a separate read only shell file. **Source:** spec FR-NEW-023. **Evidence:** `editor.html:27-29`, `:36`, `:47`, `editor.js:234` (the shell believes only the frame's own window for the edit toggle).

- **DEC-040:** Deck route failures carry a `code` (`denied` or `session_expired`) only for requests that carry the header `X-Editor: 1`, which `editor-library.js` adds to every `fetch` it wraps; a request without it gets `403` `Access denied.` JSON when the grant is live and the role lacks the permission (so a hand made write or read by a RO person is refused with the text the tests expect), and `302 <library origin>/open/<pid>` when the grant is absent or ended or the route is a navigation route (`/d/<pid>/`, `/content-frame`, `/download`, `/export/pptx`), so a visitor or a copied session sees the sign in page and never a file. When a response has `code`, `editor-library.js` (which redefines the global functions `showSaveError`, `notePollFailure` and wraps `alert`, all plain global bindings the editor scripts call at run time) makes the editor show `answer.error` alone (no `Save failed:` prefix, no `Export <FORMAT> échoué :` prefix) as the notice or alert; `session_expired` with nothing unsaved is silent (no notice, no failure count) and the next download or export navigates to the library origin; the status poll treats such an answer as a quiet pause: it does not count toward the three failures of the lost connection notice; the click of `#download-btn` (an `<a href download>` in the editor) is intercepted and sent with `fetch`, so a download refused or cut by the end of the session shows a notice or leads to the sign in page instead of saving the sign in page as a file. A response without `code` takes the previous code path unchanged. **Obliged by:** SPEC-0025/FR-NEW-007, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-048, SPEC-0025/FR-NEW-074, SPEC-0025/FR-NEW-065. **Rationale:** spec design input 16: the editor must tell "session ended" and "refused" from a failure; local mode never emits `code`. **Alternatives considered:** matching on the text. **Source:** spec design input 16. **Evidence:** `editor-save.js:135-138`, `:157-167`, `editor.js:425`, `:432-436`.

- **DEC-041:** The library `/d/<pid>/status` answers `{"mtime", "update_in_progress": false, "update_expires_in": null, "filename": "<name>.html", "poll_interval", "port": 0, "requests_revision"}`: no path, no process id, and only to a person with a right on the presentation; `requests_revision` is `0` for a role without `EDIT` so a read only editor never polls the refused request list. **Obliged by:** SPEC-0025/FR-NEW-073, SPEC-0025/FR-NEW-027. **Rationale:** the editor poll reads `mtime` (the change marker, `editor.js:442-471`) and `filename`; the local payload carries the absolute path (`http_server.py:493-508`). **Alternatives considered:** the local payload with the name masked. **Source:** spec design input 11. **Evidence:** `http_server.py:493-508`, `editor.js:84-90`.

- **DEC-042:** Failures of a download or export in the library answer `{"error": <operating system reason>}` through `_failure_reason` (`exc.strerror`, else a fixed `Export failed`), never `str(exc)`. **Obliged by:** SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020. **Rationale:** `str(exc)` carries file names and paths (B#8). **Alternatives considered:** scrubbing the path out of the text. **Source:** spec design input 23. **Evidence:** `http_server.py:419-420`, `:448-450`, `:474-476`.

- **DEC-043:** The library PPTX download calls `to_pptx(path, out, paint=False, embedded_pictures_only=True)`: the flow engine only (no Chromium in the image, no script of the deck ever executed on the machine) and a picture is read only from a `data:` URI; any other `src` is skipped with a report warning. The painted path gets the same flag. **Obliged by:** SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-022. **Rationale:** closes A#8, A#9 and C#6 at their sites and makes E2E-SEC-022 true by construction; the seeded decks embed their pictures (spec 14.1 row 15). **Alternatives considered:** adding Chromium to the image with network and file access removed (new dependency, 300 MB, flags to maintain); keeping the painted export with `file:` and WebSocket blocked. **Source:** spec design input 21. **Evidence:** `export/to_pptx.py:66-80`, `export/pptx_images.py:112-117`, `export/pptx_paint_shapes.py:196-200`, `export/pptx_paint.py:136`, `:156`.

- **DEC-044:** Routes that must not exist in the library: DOCX export (`/d/<pid>/export/docx` is `Access denied.` for every role), the picture render, `new_file`, every MCP tool, `/arch-layout` on the library origin. **Obliged by:** SPEC-0025/FR-NEW-022, SPEC-0025/FR-NEW-052. **Rationale:** A#4, A#10, C#7; the spec offers only HTML and PPTX. A test imports every `routes_*` module and fails if one imports `deck.tools` or `render`. **Alternatives considered:** none. **Source:** spec FR-NEW-022. **Evidence:** `deck/tools.py:62`, `export/to_docx.py:135-154`, `render/service.py:170`.

- **DEC-045:** The deck frame keeps its sandbox attribute as is (`allow-scripts allow-same-origin allow-forms allow-fullscreen allow-popups allow-popups-to-escape-sandbox`, no `allow-top-navigation`), because on the content origin it is the editor's own contract. **Obliged by:** SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-052. **Rationale:** the confinement is the origin (DEC-007), not the attribute; no top navigation means a script cannot send the shell away. **Alternatives considered:** dropping `allow-popups` (the presenter window needs it). **Source:** existing code. **Evidence:** `editor.html:145`.

- **DEC-046:** Deployment follows the owner's VPS convention: `docker-compose.prod.yml` becomes the standalone file (service `mcp-htmleditor`, `container_name: mcp-htmleditor`, `expose: ["7842"]`, `command: ["webserve"]`, `env_file: /app/data/mcp-htmleditor/.env`, volume `/app/data/mcp-htmleditor:/data`, network `proxy-network` external, build arg `APP_VERSION`, json-file logs); `environments/prod/.env.example` documents the variables (the operator copies it once to `/app/data/mcp-htmleditor/.env`, because `vps-deploy.sh` copies `environments/<env>/*` and a glob skips dotfiles) (`HTMLEDITOR_HOST=0.0.0.0`, the origins, `HTMLEDITOR_LIBRARY_DIR=/data/library`, `HTMLEDITOR_STATE_DIR=/data/state`, `HTMLEDITOR_GOOGLE_CREDENTIALS_FILE=/data/google-oauth.json`); `make deploy-vps TAG=vX.Y.Z` follows the sibling projects and adds two idempotent steps (the content host route `proxy.sh add slides-content.scm-platform.org 7842 mcp-htmleditor` with its certificate, and `chown -R 10001:10001 /app/data/mcp-htmleditor`). **Obliged by:** SPEC-0025/FR-NEW-057, SPEC-0025/FR-NEW-058, SPEC-0025/FR-NEW-062. **Rationale:** `vps-deploy.sh` takes one `<dns>:<port>`, so the second name is added by `proxy.sh`; the container user is uid 10001 and the data directory is created by root. **Alternatives considered:** a new `docker-compose.vps.yml` (the owner's convention names `prod`, and the old overlay is only documented in `.agent_docs/docker.md:42-47`, with no test). **Source:** the owner's VPS convention in the request, `notes-mcp/docker-compose.prod.yml`, `notes-mcp/Makefile:422-439`. **Evidence:** `docker-my-services/services/nginx/scripts/vps-deploy.sh` (usage block), `scripts/proxy.sh`, `templates/site.conf.tpl`.

- **DEC-047:** The image runs `webserve` through compose (`command`), keeps `ENTRYPOINT ["mcp-htmleditor"]`, the uid 10001 user, the exec form and the `/health` `HEALTHCHECK`; the builder stage adds `COPY library-seed/ ./library-seed/` before `uv sync` (the wheel force-includes it); no Chromium is added; a `.dockerignore` is added. **Obliged by:** SPEC-0025/FR-NEW-054, SPEC-0025/FR-NEW-062. **Rationale:** docker skill (non root numeric `USER`, exec form, `HEALTHCHECK`, `.dockerignore` required, no secret in a layer); the seed is packaged, the credentials are not. **Alternatives considered:** a second Dockerfile. **Source:** docker skill, existing Dockerfile. **Evidence:** `Dockerfile:16-19`, `:52-68`.

- **DEC-048:** Logging and tracing follow the project rules: `logger = logging.getLogger(__name__)`, `%` formatting, stderr console, `click.echo` only for the start line; spans `auth.google_token`, `library.upload`, `library.replace`, `library.delete_presentation`, `library.delete_folder`, `library.seed`, `session.create`, with sizes and status codes only; no email, name, token, cookie or credential in a log line or an attribute. **Obliged by:** SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-020 (nothing about members leaks), AGENTS.md observability rules. **Rationale:** the activity table is the only place addresses are stored by design. **Alternatives considered:** logging the actor of each refusal (PII in logs). **Source:** AGENTS.md. **Evidence:** `tracing.py:170`, `.agent_docs/observability.md`.

- **DEC-049:** Test infrastructure is one module `tests/library_support.py`: an in process `LibraryServer` on a free port with a temporary `library_dir` and `state_dir`, a `FakeClock`, a `FakeGoogle` (a loopback HTTP server with `/authorize` and `/token`, scripted accounts and failures, a record of the requests it received), an HTTP client that sets `Host` and keeps cookies per person, a `LibraryBuilder` that creates folders, members and presentations of exact sizes through the repository, a `StoredLibrary` operator view, and Playwright launch arguments mapping `slides.test` and `slides-content.test` to 127.0.0.1. Browser tests are named `test_*_e2e.py` and use `tests/browser_wait.py`; an exploit test is a function named `test_exploit_<id>` inside the `_http.py` or `_e2e.py` file of its area, so `-k exploit` selects them all. The library suite stays under 90 s in `make check`; the test of 25 MB at 10 Mbit/s is marked `slow`. **Obliged by:** SPEC-0025/FR-NEW-060, SPEC-0025/FR-NEW-061, AGENTS.md testing rules. **Rationale:** spec design input 13; the gate keeps its 330 s test budget (`.agent_docs/testing.md`). **Alternatives considered:** a real Google test account (not repeatable). **Source:** spec design input 13, `.agent_docs/testing.md`. **Evidence:** `tests/conftest.py:245-270`, `tests/browser_wait.py:1-40`, `tests/http_support.py:1-45`.

- **DEC-050:** Documentation: `.agent_docs/library.md` (new, the module map, flows, cookies, seams, gotchas), `AGENTS.md` (commands and index line), `README.md` (a "Web library mode" section and the VPS runbook), `.agent_docs/architecture.md` and `.agent_docs/testing.md` (pointers, counts), `.agent_docs/docker.md` (the new compose file), `.agent_docs/observability.md` (the new spans), `.agent_docs/html-conventions.md` (the editor seam); the skill `topics/editor.md` gets one paragraph (the editor in the web mode), `skill-audit` stays green. **Obliged by:** SPEC-0025/FR-NEW-057, SPEC-0025/FR-NEW-062 (operability), AGENTS.md documentation pattern. **Rationale:** every story updates the docs it touches; the closing story audits them. **Alternatives considered:** one big docs story at the end (the rule says keep up to date on every implementation). **Source:** AGENTS.md. **Evidence:** `AGENTS.md` documentation index.

- **DEC-051:** `mcp-htmleditor library-list` prints one tab separated line per presentation (folder, presentation, stored path, bytes) so an operator can use `history` and `restore` on a library file. **Obliged by:** SPEC-0025/FR-NEW-026 (the previous version is kept in the history of the presentation), spec section 7.6 (an operator can list and restore through SPEC-0009). **Rationale:** stored files have opaque names (DEC-025), so without a way to map a name to a path the history capability could not be used. **Alternatives considered:** history commands that take a folder and a name. **Source:** spec 7.6. **Evidence:** `history.py:156-182`.

- **DEC-052:** Lists are one query each (folders with the person's role by one join; presentations of a folder with one `os.stat` per file), no pagination, no per row query; the 200 folder and 100 presentation cases are tested for the 2 second bound on loopback with a margin. **Obliged by:** SPEC-0025/FR-NEW-060. **Rationale:** FR-NEW-060 is a bound on a list of 200 or 100 entries, not a scale target; pagination would add a control the spec does not name. **Alternatives considered:** pagination; caching. **Source:** spec FR-NEW-060. **Evidence:** n/a.

- **DEC-053:** Library pages use plain HTML controls (`a`, `button`, `form`, `label`, `input`, `select`, `<dialog>` for the questions) with a visible text or an `aria-label` on every control, no click handler on a non focusable element, and `library.js` moves focus into a dialog when it opens and back to the control when it closes. **Obliged by:** SPEC-0025/FR-NEW-064. **Rationale:** native elements are keyboard reachable without code. **Alternatives considered:** a component library (no). **Source:** spec FR-NEW-064. **Evidence:** n/a.

- **DEC-054:** A failed or interrupted upload leaves nothing: the bytes are held in memory until the checks pass, written by `atomic_write` (temporary file in the target directory, `os.replace`), and the row is inserted in a short transaction after the file exists (DEC-027); any exception removes the temporary file and the new file, and the answer is `The upload failed. Nothing was changed.` for storage errors. **Obliged by:** SPEC-0025/FR-NEW-036, SPEC-0025/FR-NEW-038, SPEC-0025/FR-NEW-063. **Rationale:** a lost connection means `rfile.read` raises before any write; a full disk means `replace_file` raises (`fileio.py:44`), which `atomic_write` already cleans up (`fileio.py:86-92`). **Alternatives considered:** a staging directory with a sweeper. **Source:** design. **Evidence:** `fileio.py:70-98`.

- **DEC-055:** Every page, message and control the mode adds is an English constant in `library/pages.py` (the exact texts are the ones quoted in the requirements and tests of each story); `static/editor-library.js` adds only `Access denied.` and `Your session has expired. Sign in again to save.`; the editor's own labels, notices and the presentations keep their texts, French ones included. **Obliged by:** SPEC-0025/FR-NEW-065. **Rationale:** one file holds every text, so a translation of a French label by accident cannot happen in the library code, and a test greps the toolbar labels of the shell. **Alternatives considered:** a message catalogue (no second language is asked). **Source:** spec FR-NEW-065. **Evidence:** `editor.html:27-50` (the French and English labels kept).

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0124 | webserve starts, accepts only its two host names, answers /health | P1 | FR-NEW-055, FR-NEW-056, FR-NEW-057, FR-NEW-058, FR-NEW-059, FR-NEW-072, FR-NEW-073 | main | 1 | no |
| US-0125 | A visitor sees only the sign in page | P1 | FR-NEW-001, FR-NEW-057, FR-NEW-072 | US-0124 | 2 | no |
| US-0126 | Sign in with a Google account, stay signed in, sign out | P1 | FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-008, FR-NEW-009, FR-NEW-015, FR-NEW-068, FR-NEW-069, FR-NEW-071, FR-NEW-072 | US-0125 | 1 | no |
| US-0127 | The home page: Admin role, order, empty states, uniform refusal | P1 | FR-NEW-010, FR-NEW-011, FR-NEW-012, FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-053, FR-NEW-065 | US-0126 | 1 | no |
| US-0128 | Exact 30 day sessions, restarts, unavailable library, 200 folders | P2 | FR-NEW-005, FR-NEW-006, FR-NEW-017, FR-NEW-060, FR-NEW-062, FR-NEW-064 | US-0127 | 1 | no |
| US-0129 | The folder page lists presentations | P1 | FR-NEW-009, FR-NEW-010, FR-NEW-018, FR-NEW-019, FR-NEW-020, FR-NEW-021, FR-NEW-060, FR-NEW-064, FR-NEW-072 | US-0127 | 1 | no |
| US-0130 | Administration: create folders and read the activity list | P2 | FR-NEW-013, FR-NEW-040, FR-NEW-041, FR-NEW-042, FR-NEW-049, FR-NEW-050, FR-NEW-051, FR-NEW-067, FR-NEW-070 | US-0127, US-0129 | 1 | no |
| US-0131 | Administration: delete a folder after retyping its name | P2 | FR-NEW-043, FR-NEW-044, FR-NEW-048, FR-NEW-049, FR-NEW-067 | US-0130 | 1 | no |
| US-0132 | Administration: members and roles of a folder | P2 | FR-NEW-012, FR-NEW-045, FR-NEW-046, FR-NEW-047, FR-NEW-048, FR-NEW-049, FR-NEW-067 | US-0130 | 1 | no |
| US-0133 | Open a presentation: ticket, grant, deck frame, status, HTML download | P1 | FR-NEW-001, FR-NEW-009, FR-NEW-010, FR-NEW-020, FR-NEW-021, FR-NEW-022, FR-NEW-023, FR-NEW-025, FR-NEW-052, FR-NEW-072, FR-NEW-073 | US-0129, US-0131 | 1 | no |
| US-0134 | The editor shell opens on the content origin | P1 | FR-NEW-025, FR-NEW-052, FR-NEW-055, FR-NEW-056 | US-0133 | 2 | no |
| US-0135 | Read only editor, presenter window, full screen, hostile script isolation | P1 | FR-NEW-009, FR-NEW-022, FR-NEW-023, FR-NEW-025, FR-NEW-052, FR-NEW-064 | US-0134, US-0132 | 2 | no |
| US-0136 | Edit a presentation and store changes by themselves | P1 | FR-NEW-023, FR-NEW-024, FR-NEW-025, FR-NEW-026, FR-NEW-027, FR-NEW-063, FR-NEW-066 | US-0135 | 1 | no |
| US-0137 | The editor when the session or the right ends | P2 | FR-NEW-007, FR-NEW-010, FR-NEW-048, FR-NEW-065, FR-NEW-074 | US-0136 | 2 | no |
| US-0138 | Requests, Ask AI and arch layout work for editors and are refused to read only people | P2 | FR-NEW-023, FR-NEW-025 | US-0136 | 2 | no |
| US-0139 | The PPTX exporter can be confined to pictures held in the presentation | P2 | FR-NEW-052 | main | 2 | no |
| US-0140 | Download the presentation as PPTX without running its scripts | P2 | FR-NEW-010, FR-NEW-022, FR-NEW-052 | US-0137, US-0138, US-0139 | 2 | no |
| US-0141 | Upload a valid presentation into a folder | P1 | FR-NEW-023, FR-NEW-024, FR-NEW-028, FR-NEW-029, FR-NEW-031, FR-NEW-049, FR-NEW-067 | US-0137 | 1 | no |
| US-0142 | Upload file names: allow list, composed form, hostile names | P1 | FR-NEW-021, FR-NEW-032, FR-NEW-053 | US-0141 | 2 | no |
| US-0143 | Upload limits, progress, interruption and storage failure | P2 | FR-NEW-030, FR-NEW-035, FR-NEW-036, FR-NEW-037, FR-NEW-038, FR-NEW-061, FR-NEW-063, FR-NEW-067 | US-0142 | 1 | no |
| US-0144 | Replace an existing presentation after a collision question | P2 | FR-NEW-033, FR-NEW-034, FR-NEW-036, FR-NEW-037, FR-NEW-038, FR-NEW-049, FR-NEW-063 | US-0143, US-0138 | 1 | no |
| US-0145 | Delete a presentation for good | P2 | FR-NEW-023, FR-NEW-039, FR-NEW-048, FR-NEW-049, FR-NEW-052, FR-NEW-070 | US-0144, US-0138, US-0140 | 1 | no |
| US-0146 | Create the initial content on the first start | P1 | FR-NEW-054, FR-NEW-062 | US-0145 | 1 | no |
| US-0147 | The operator can list the stored library and find a file's history | P3 | FR-NEW-026 | US-0146 | 2 | no |
| US-0148 | Deployment files and the VPS runbook | P1 | FR-NEW-057, FR-NEW-062 | US-0147, US-0146 | 1 | no |
| US-0149 | Closing journeys, documentation audit and acceptance of the whole spec | P1 | FR-NEW-060, FR-NEW-061, FR-NEW-062 | US-0148 | 1 | yes |

Stories at `min_tier: 1` exceed the tier 2 band (files touched above 5 or tests above 15) because the pieces they change cannot be cut without leaving a story nobody can verify alone (floor check); none is cut thinner. US-0149 is `min_tier: 1` by decision density, not size: it is the audit that reveals cross feature defects and must fix them in the owning module with a regression test.
