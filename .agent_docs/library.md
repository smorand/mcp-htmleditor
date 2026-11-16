# Web library mode (SPEC-0025)

`mcp-htmleditor webserve [--host] [--port]`: one process for every folder and presentation of a private library,
behind nginx at `slides.scm-platform.org`. Spec and design: `sdlc/specs/SPEC-0025-web-library-mode/`. Stories
US-0124 to US-0149 land on `feat/0049-web-library-mode`; this file grows with each.

## Module map (`src/mcp_htmleditor/library/`)

| Module | Holds |
|---|---|
| `__init__.py` | package docstring |
| `server.py` | `LibraryServer(_EditorServer)` (`start`, `stop`, `port`, `origin_for`, `is_secure`, `clock`), `LibraryHandler(_EditorHandler)` (gate, `_send_common_headers`), `health_answer`, `LibraryConfigError`, `SAME_HOST_MESSAGE` |

`_EditorServer.__init__(bind_host, port, handler=_EditorHandler)` is the only change to `http_server.py` (DEC-003);
`_EditorHandler` is subclassed, never edited (`test_the_editor_handler_is_unchanged...` pins its source hash; the
story that adds the DEC-003 hooks updates the hash in its own diff).

## Settings (DEC-005)

`library_origin` (`HTMLEDITOR_LIBRARY_ORIGIN`), `library_content_origin` (`HTMLEDITOR_LIBRARY_CONTENT_ORIGIN`),
`library_dir_override` (`HTMLEDITOR_LIBRARY_DIR`, property `library_dir`, default `<state_dir>/library`). An origin
must be exactly `http(s)://host[:port]` (`config.is_origin`: no user, path, `/`, query or fragment, port in range,
no empty or default port, no trailing dot: the netloc is compared with `Host` as is); otherwise `Settings()` fails
with a message naming the variable, for every command since the click group builds the settings. The three names
are in `_SIGNIFICANT_ENV_VARS`. HSTS follows the library origin's scheme only (both origins are expected to share it).

## Gate order (every method, `LibraryHandler._dispatch`)

1. `_refuse_ambiguous_headers` (inherited): 400.
2. `GET /health` (also `/health/`), any host name, no host at all: `{"ok": true, "status": "ok", "version"}`.
3. Host gate: `Host` lower cased must equal the netloc of one origin (host and port), else
   `403 {"error": "forbidden host"}` and one `Refused <METHOD> <path>: forbidden host '<host>'` warning.
4. `X-Forwarded-Proto: http` (any case) while that origin is https: `308`, `Location` = configured origin + request
   path + query (never the request's `Host`, an absolute form target keeps only its path), empty body.
5. Anything else: `404 {"error": "Not found"}` (US-0125 puts the route table here).

Unknown methods (`PATCH`, `PUT`) get the stdlib 501, `OPTIONS` the inherited 405.

## Headers (DEC-009)

`LibraryHandler.end_headers` calls `_send_common_headers`, so every answer (the inherited 400, 405 and 501
included) carries `Cache-Control: no-store, must-revalidate`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none';
frame-ancestors 'none'`, plus `Strict-Transport-Security: max-age=31536000` when the library origin is https.
Pages (US-0125) and the deck frame (US-0133) need another policy: make the helper take it per answer then.

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
`tests/test_library_gate_http.py`: E2E-135, 136, 146, 147, 186, headers, settings, CLI refusal, a real `webserve`
child stopped by SIGTERM.

## Gotchas

- 2026-11-16 (US-0124): `make format` also formats Python blocks inside `sdlc/**/*.md`; `make format-check` fails on a
  story whose code block is not ruff formatted.
