# US-0124: webserve starts, accepts only its two host names, answers /health

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 1
> Files touched: 7
> Closes spec: no

## Objective

A new command `mcp-htmleditor webserve` starts one process that answers on the library host name and the content host name, refuses every other host name, redirects a request that reached nginx in plain http to the secure address, and answers `/health` with only `running` and the version, whatever the host name. The local mode is untouched and refuses library addresses as before.

## Requirements covered

- SPEC-0025/FR-NEW-055: The local mode SHALL keep every behavior it had before this increment.
  - Business rules: One local file at a time, the same editor, the same options, the same address rules. The web library mode running on the same machine changes nothing in it.
- SPEC-0025/FR-NEW-056: The local mode SHALL NOT ask for a sign in or show any library page.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-058: WHEN a person opens the address with a plain, unencrypted connection THE web library mode SHALL send them to the same page through the secure connection.
  - Business rules: The page asked for, including a direct link, is kept.
- SPEC-0025/FR-NEW-059: IF a request reaches the product through a host name other than the address of the mode in use THEN THE product SHALL refuse it and show nothing of the library, except the liveness answer of FR-NEW-073.
  - Business rules: In the local mode the accepted names stay the local ones; in the web library mode the accepted name is slides.scm-platform.org. The liveness answer is the only exception: it is given whatever host name the request carries, loopback included, and shows nothing of the library.
- SPEC-0025/FR-NEW-057 (partial: the process answers on the two configured host names and redirects a plain connection to the secure form; the sign in page itself is US-0125): The web library mode SHALL be reached at the address slides.scm-platform.org through a secure connection.
  - Business rules: The address is imposed by the owner (Section 3.3).
- SPEC-0025/FR-NEW-072 (partial: the frame protection headers are set on every response of the mode, the first of them here): The web library mode SHALL NOT accept a session after its person signed out, and SHALL NOT let any library page be shown inside a page of another site.
  - Business rules: A copy of the credentials of a session made before "Sign out" is refused after it, as for a visitor who is not signed in. The refusal of framing applies to every page, including the sign in page.
- SPEC-0025/FR-NEW-073 (partial: the liveness answer that reveals nothing; the status of a presentation comes with US-0133): The web library mode SHALL answer the check "is the product running" without sign in with only that fact and the product's version, and SHALL show the status of a presentation (its change marker) only to a person who has a right on it, without any storage location.
  - Business rules: The answer carries no file location, process number or presentation name. The operator's health check of the packaged product keeps working without sign in. A person with no right on a presentation, or a visitor, asking its status gets "Access denied." or the sign in page, never a status. The answer is the same whatever host name the request carries, loopback included.

## Independent Test

Run `make test ARGS='-k library_gate'`: the tests start an in process `LibraryServer` on a free port and send raw requests with chosen `Host` and `X-Forwarded-Proto` headers. By hand: `mcp-htmleditor webserve --port 7843`, then `curl -s http://127.0.0.1:7843/health` returns `{"ok": true, "status": "ok", "version": ...}`, `curl -s -H 'Host: evil.example' http://127.0.0.1:7843/` returns 403 with no library text and `curl -si -H 'Host: slides.scm-platform.org' -H 'X-Forwarded-Proto: http' http://127.0.0.1:7843/x` returns 308 with `Location: https://slides.scm-platform.org/x`. The assertion that is not a mock: the `/health` body of the library server and the body served by a local `serve` process differ exactly by the dropped `file`, `pid`, `port`, `page`, `started`, `uptime_seconds` keys (the local one is unchanged).

## Design excerpt

### Decisions

- DEC-001 (SPEC-0025): Launch the mode with a new click command `mcp-htmleditor webserve [--host] [--port]` and leave `serve` untouched. Obliged by: SPEC-0025/FR-NEW-055, SPEC-0025/FR-NEW-056.
- DEC-002 (SPEC-0025): One process serves every folder and presentation and resolves the presentation per request; no process per deck. Obliged by: SPEC-0025/FR-NEW-060, SPEC-0025/FR-NEW-025.
- DEC-003 (SPEC-0025): Reuse the editor routes through five overridable methods of `_EditorHandler` (`_served_file`, `_served_name`, `_save_lock`, `_failure_reason`, `_pptx_options`; `_save_lock` returns a context manager, the local one is the existing `threading.Lock`), give `_EditorServer.__init__` a `handler` parameter defaulting to `_EditorHandler`, and implement the library as `LibraryHandler(_EditorHandler)` that overrides `do_GET`, `do_POST` and `_serve_status` only. The defaults reproduce the previous expressions byte for byte. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-055.
- DEC-004 (SPEC-0025): Add no third party dependency and keep the project stack: stdlib `http.server`, `sqlite3`, `urllib`, `secrets`, `hashlib`, `unicodedata`; click, synchronous I/O. The skill MUST rules for FastAPI, Typer and async first are not applied. Obliged by: SPEC-0025/FR-NEW-055 (the local mode keeps its server and CLI), ASK ONLY FOR category 2.
- DEC-005 (SPEC-0025): Settings fields `library_origin`, `library_content_origin`, `library_dir_override` (property `library_dir`), `google_credentials_override` (property `google_credentials_file`), `library_seed_dir_override` (property `library_seed_dir`), env prefix `HTMLEDITOR_`, names added to `_SIGNIFICANT_ENV_VARS` and the path fields to `_PATH_FIELDS`. Obliged by: SPEC-0025/FR-NEW-057, SPEC-0025/FR-NEW-059, SPEC-0025/FR-NEW-062, spec section 3.3 (credentials supplied by the operator).
- DEC-007 (SPEC-0025): Serve two origins from one listener: the library origin (pages, API, session) and the content origin (the editor shell, the deck frame and the routes of one presentation); the `Host` header must equal the netloc of one of the two configured origins, otherwise `403 {"error": "forbidden host"}`. Obliged by: SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-059, SPEC-0025/FR-NEW-057.
- DEC-008 (SPEC-0025): Redirect `X-Forwarded-Proto: http` to the configured origin of the receiving host with `308`; nginx already redirects port 80 to 443 for every vhost. Obliged by: SPEC-0025/FR-NEW-058.
- DEC-009 (SPEC-0025): Every library and shell response carries `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, a `Content-Security-Policy` and, when the origin scheme is https, `Strict-Transport-Security: max-age=31536000`; library pages use `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`, JSON answers `default-src 'none'; frame-ancestors 'none'`, the editor shell `frame-ancestors 'none'`, and the deck frame answer `frame-ancestors 'self'` with `X-Frame-Options: SAMEORIGIN`. `library.js` handles `pageshow` with `persisted` by reloading. Obliged by: SPEC-0025/FR-NEW-072, SPEC-0025/FR-NEW-008, SPEC-0025/FR-NEW-001.
- DEC-010 (SPEC-0025): `GET /health` is answered before the host gate on any host name and returns `{"ok": true, "status": "ok", "version": <version>}` and nothing else. Obliged by: SPEC-0025/FR-NEW-073, SPEC-0025/FR-NEW-059.
- DEC-048 (SPEC-0025): Logging and tracing follow the project rules: `logger = logging.getLogger(__name__)`, `%` formatting, stderr console, `click.echo` only for the start line; spans `auth.google_token`, `library.upload`, `library.replace`, `library.delete_presentation`, `library.delete_folder`, `library.seed`, `session.create`, with sizes and status codes only; no email, name, token, cookie or credential in a log line or an attribute. Obliged by: SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-020 (nothing about members leaks), AGENTS.md observability rules.

### Data model

None in this story: there is no database yet.

### Contracts

**CLI** (`click`, in `cli.py` next to `serve_cmd`, `cli.py:170-201`):

```
@main.command("webserve")
@click.option("--host", default=None, help="Bind address (default HTMLEDITOR_HOST or localhost).")
@click.option("--port", default=None, type=int, help="HTTP port (default HTMLEDITOR_PORT or 7842).")
def webserve_cmd(host: str | None, port: int | None) -> None
```

It builds `LibraryServer` from `get_settings()` and the options, prints `Serving the library on http://<host>:<port>/ (library origin <origin>, content origin <origin>)` with `click.echo`, installs SIGINT and SIGTERM handlers that call `server.stop()`, and blocks. It exits 1 with `The library origin and the content origin must be two different host names.` when the two origins have the same host.

**Settings** (`config.py`, prefix `HTMLEDITOR_`, memoized by `_SIGNIFICANT_ENV_VARS`, `config.py:70-88`): `library_origin: str = "https://slides.scm-platform.org"`, `library_content_origin: str = "https://slides-content.scm-platform.org"`, `library_dir_override: Path | None` (variable `HTMLEDITOR_LIBRARY_DIR`, added to `_PATH_FIELDS`, `config.py:53-67`) with property `library_dir = library_dir_override or state_dir / "library"`. A value that is not `http(s)://host[:port]` without a path is a validation error naming the variable. The two origin variables and `HTMLEDITOR_LIBRARY_DIR` are appended to `_SIGNIFICANT_ENV_VARS`.

**Server** (`library/server.py`): `LibraryServer(_EditorServer)` with `__init__(self, settings: Settings, *, clock: Callable[[], float] = time.time)` binding `settings.host`, the port, and `LibraryHandler`; methods `start()` (thread, like `start_http_server`), `stop()` (shutdown, `server_close`, `connections.close_idle()`, as `http_server.py:1176-1198`), attribute `port`. `_EditorServer.__init__` (`http_server.py:1027-1032`) gains a third parameter `handler: type[BaseHTTPRequestHandler] = _EditorHandler`; nothing else of `http_server.py` changes in this story. `LibraryHandler(_EditorHandler)` overrides `do_GET`, `do_POST` and `do_DELETE` and reuses the inherited connection bounds, `do_OPTIONS` (405) and `_refuse_ambiguous_headers`.

**Gate order** in `LibraryHandler` (every method): `self._refuse_ambiguous_headers()` (existing, `http_server.py:215-238`); `GET /health` on any host name: `{"ok": true, "status": "ok", "version": __version__}`; host gate: the `Host` header must equal the netloc (host and port) of `library_origin` or `library_content_origin` (case insensitive), else `403 {"error": "forbidden host"}` with no library text; `X-Forwarded-Proto: http` gives `308` with `Location: <configured origin of the receiving host><request path and query>` (built from `Settings`, never from the request's `Host`); anything else answers `404 {"error": "Not found"}` in this story (US-0125 replaces it).

**Response headers** (one helper `LibraryHandler._send_common_headers()` used by every answer): `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` for JSON answers (the page policy of US-0125 widens it for pages), and `Strict-Transport-Security: max-age=31536000` when the scheme of the origin is `https`.

**Test support** (`tests/library_support.py`, new): fixture `library_server(settings_overrides)` starting `LibraryServer` on a free port with temporary `library_dir` and `state_dir` and origins `http://slides.test:<port>` and `http://slides-content.test:<port>`; `HttpClient` that connects to `127.0.0.1:<port>` and sets `Host`; `FakeClock`.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/config.py` | modify | three fields, three memo names, one path field |
| `src/mcp_htmleditor/cli.py` | modify | `webserve` command |
| `src/mcp_htmleditor/http_server.py` | modify | `_EditorServer` takes the handler class (one parameter) |
| `src/mcp_htmleditor/library/__init__.py` | create | package docstring |
| `src/mcp_htmleditor/library/server.py` | create | `LibraryServer`, `LibraryHandler` gate |
| `tests/library_support.py` | create | `library_server` fixture, `HttpClient`, `FakeClock` |
| `tests/test_library_gate_http.py` | create | gate tests |

### Existing patterns

`tests/conftest.py:245-270` (`serve_deck`, `_wait_listening`) for a server on a free port; `tests/http_support.py:1-45` (`exchange`, `RawReply`) for raw requests; `tests/test_http_origin_e2e.py` and `tests/test_http_header_gate_e2e.py` for the style of host and header tests; `http_server.py:117-340` for the handler being subclassed; `http_server.py:1027-1032` for the server class being parameterized.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-135: No library page exists in the local mode

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_gate_http.py`
- **Category:** failure
- **Scenario:** SC-021
- **Requirements:** FR-NEW-055, FR-NEW-056
- **Given** The local mode on talk.html.
- **When** The operator asks the local address for a folder page and for the home page of the library.
- **Then** The local mode shows its own editor for talk.html only; no sign in page, no folder list.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-136: The local mode keeps refusing other host names

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_gate_http.py`
- **Category:** edge
- **Scenario:** SC-021
- **Requirements:** FR-NEW-055, FR-NEW-056, FR-NEW-059
- **Given** The local mode on talk.html.
- **When** A request reaches it through the host name slides.scm-platform.org.
- **Then** It is refused and nothing of talk.html is shown, as before this increment.
- **And** No sign in page was shown either.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-146: The plain address is sent to the secure one

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_gate_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-023
- **Requirements:** FR-NEW-057, FR-NEW-058
- **Given** A visitor with no session.
- **When** He opens the plain, unencrypted form of slides.scm-platform.org.
- **Then** He lands on the sign in page through the secure connection, never served in the clear.
- **And** No library content was sent over the plain connection.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the redirect is produced by the product from `X-Forwarded-Proto: http` (DEC-008); nginx also redirects port 80.

### SPEC-0025/E2E-147: Another host name is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_gate_http.py`
- **Category:** failure
- **Scenario:** SC-023
- **Requirements:** FR-NEW-001, FR-NEW-057, FR-NEW-059
- **Given** The product answers on the same machine under the name evil.example.
- **When** A request reaches it through the host name evil.example.
- **Then** It is refused and nothing of the library, not even the sign in page, is shown, except the liveness answer, which stays available and shows nothing of the library.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-186: The health check works without sign in and shows little

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_gate_http.py`
- **Category:** happy
- **Scenario:** SC-023
- **Requirements:** FR-NEW-059, FR-NEW-073
- **Given** The product runs; the operator's health check has no session.
- **When** It asks whether the product is running.
- **Then** The answer says the product is running and gives its version, 1 field of each; it succeeds.
- **And** The answer holds no file location, process number or presentation name.
- **And** The answer is the same when the check reaches the product as 127.0.0.1 and as evil.example.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

`tests/test_library_gate_http.py` also holds: a settings test that `HTMLEDITOR_LIBRARY_ORIGIN=not-a-url` fails validation naming the variable, the `webserve` refusal when both origins share a host (through `click.testing.CliRunner`), and a test that `_EditorHandler` method bodies are unchanged (the existing local suites stay green).

## Constraints

- Do not change any method body of `_EditorHandler`; only subclass it and pass the class to `_EditorServer`.
- No database, no cookie, no Google code, no HTML page, no CSS or JavaScript in this story.
- No new dependency; no `os.environ` read (settings only).
- Scope boundary: the sign in page and the route table (US-0125), sign in itself (US-0126).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `AGENTS.md` (key commands: `webserve`; index line for `.agent_docs/library.md`), `.agent_docs/library.md` created with the module map and the gate order, `README.md` one paragraph under a new heading "Web library mode" (command and the three settings).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0124: webserve starts, accepts only its two host names, answers /health` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
