# US-0002: Refuse foreign origins and host names, drop CORS

> Spec: SPEC-0005 (sdlc/specs/SPEC-0005-cross-origin-requests/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

Any web page open in the user's browser can today overwrite or read the document the editor serves,
because the preview server answers every origin and every host name and advertises
`Access-Control-Allow-Origin: *`. After this story, only the editor's own origin, reached through a
loopback host name, can use the protected routes; `/health` stays open.

## Requirements covered

- SPEC-0005/BR-001: IF a request to a protected route carries an `Origin` header that is not the editor's own origin THEN THE preview server SHALL answer `403` with body `{"error": "forbidden origin"}` and SHALL NOT run the route.
- SPEC-0005/BR-002: IF a request to a protected route carries a `Host` header whose name is not `localhost`, `127.0.0.1`, `[::1]` or the configured `HTMLEDITOR_HOST` THEN THE preview server SHALL answer `403` with body `{"error": "forbidden host"}` and SHALL NOT run the route.
- SPEC-0005/BR-003: The preview server SHALL NOT send `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods` or `Access-Control-Allow-Headers` on any response.
- SPEC-0005/BR-006: The preview server SHALL answer `GET /health` with `200` and its current body whatever the `Origin` and `Host` headers.
- SPEC-0005/BR-007 (partial: same origin reads and writes over HTTP; the browser editor flow is US-0003): The preview server SHALL serve, save, poll, export and lay out for the editor page it serves itself, opened at `http://localhost:<port>/` or `http://127.0.0.1:<port>/`.
- SPEC-0005/BR-008: IF a request is refused by BR-001, BR-002 or BR-004 THEN THE preview server SHALL log one warning line naming the method, the path and the refused header value, and SHALL NOT log the request body.

Business rules (from the spec): a protected route is every route except `GET /health`. Origin match is
exact on scheme, host and port, host case insensitive; `Origin: null` is foreign; no `Origin` passes.
`HTMLEDITOR_HOST` counts only when it is not `0.0.0.0` and not `::`; missing `Host` is refused; the
port of `Host` is not checked; BR-002 is evaluated before BR-001.

## Independent Test

`make test ARGS='tests/test_http_origin_e2e.py'`: a real attacker page on another port cannot change
`doc.html` on disk (BT-001), and `GET /status` with `Host: attacker.example:P` answers
`403 {"error": "forbidden host"}` without the file path.

## Design excerpt

### Decisions
- DEC-001: one gate `_refuse_untrusted_request()` first in `do_GET` and `do_POST`, after the `/health` exemption; sends the 403, returns `True` when refused.
- DEC-003: `urllib.parse.urlsplit` for `Origin` and for `"//" + Host`; compare scheme `http`, lower cased hostname, port (default 80); `ValueError` or `null` is foreign.
- DEC-004: allowed names `localhost`, `127.0.0.1`, `::1` (bracketed `[::1]` in `Host`), plus the effective bind host stored as `server.bind_host` in `start_http_server`, except `0.0.0.0` and `::`.
- DEC-006: `logger.warning("Refused %s %s: %s %r", method, path, reason, value)`, never the body.
- DEC-007: HTTP tests use `http.client.HTTPConnection` so `Host` and `Origin` go out verbatim.

### Root cause (facts)
- No handler reads `Origin` or `Host`: `src/mcp_htmleditor/http_server.py:101` (`do_GET`), `:129` (`do_POST`).
- `_send_cors_headers` (`http_server.py:86`) emits `Access-Control-Allow-Origin: *`, called at `:94`, `:217`, `:246`, `:365`, `:374`, `:396`.

### Contracts
- `403` JSON bodies: `{"error": "forbidden host"}`, `{"error": "forbidden origin"}`.
- No `Access-Control-*` header on any response. `do_OPTIONS` keeps working but without CORS headers (its 405 is US-0003).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_server.py` | modify: gate, remove `_send_cors_headers` and its 6 calls, set `server.bind_host` at `:639` |
| `tests/test_http_origin_e2e.py` | create |
| `.agent_docs/architecture.md` | line 25: add the export and arch-layout routes and "origin and host gate, no CORS" |

### Existing patterns
- Server start and teardown in tests: `tests/test_undo_redo_e2e.py:108` (`_start`), fixture `reset_state` (`tests/conftest.py:27`), `needs_chromium` (`tests/test_undo_redo_e2e.py:47`).
- JSON responses: `_send_json` (`http_server.py:391`).

## Acceptance tests

> 100% must pass, run through `make check` (or `make test ARGS=...`). Never run test files ad hoc.

Common preconditions: real server on free port P on `127.0.0.1`, `doc.html` in `tmp_path` =
`<!DOCTYPE html><html data-doc-type="document"><body><p>ORIGINAL-SECRET</p></body></html>`.
"Unchanged" = `doc.html` bytes equal to the bytes before the request. Default headers for
`http.client`: `Host: 127.0.0.1:P` unless stated.

### SPEC-0005/BT-001: A page from another origin cannot overwrite the document
- Level exploit e2e; Driver Playwright, attacker page `<html><body>attacker</body></html>` served by `http.server` on free port Q
- When the attacker page runs `fetch("http://127.0.0.1:P/content", {method: "POST", body: "<p>PWNED</p>"})` (errors caught) and 500 ms pass
- Then `doc.html` still contains `ORIGINAL-SECRET` and does not contain `PWNED`
- Red before the fix because: the file contains `PWNED`.

### SPEC-0005/BT-002: Cross origin JSON save refused
- When `POST /content`, `Origin: https://evil.example`, `Content-Type: application/json`, body `{"html": "<p>PWNED</p>"}`
- Then `403`, body `{"error": "forbidden origin"}`; And `doc.html` unchanged
- Red before the fix because: `200 {"ok": true}` and the file contains `PWNED`.

### SPEC-0005/BT-003: Cross origin text save refused
- When `POST /content`, `Origin: https://evil.example`, `Content-Type: text/plain`, body `<p>PWNED</p>`
- Then `403`, body `{"error": "forbidden origin"}`; And `doc.html` unchanged
- Red before the fix because: `200` and `PWNED` written.

### SPEC-0005/BT-004: Cross origin layout refused
- Given `doc.html` = `<!DOCTYPE html><html><body><div data-type="arch-diagram"><div data-type="arch-row"><div data-type="arch-node" data-id="a">A</div><div data-type="arch-node" data-id="b">B</div></div></div></body></html>`
- When `POST /arch-layout`, `Origin: https://evil.example`, empty body
- Then `403`, body `{"error": "forbidden origin"}`; And `doc.html` unchanged, contains no `data-x`
- Red before the fix because: `200 {"ok": true, ...}` and `data-x` written.

### SPEC-0005/BT-005: A page from another origin cannot read the document
- Level exploit e2e; Driver Playwright attacker page on port Q
- When the attacker page runs `fetch("http://127.0.0.1:P/content").then(r => r.text()).then(t => window.__result = t, e => window.__result = e.name)` and 500 ms pass
- Then `window.__result` does not contain `ORIGINAL-SECRET`
- And `GET /content` with `Origin: https://evil.example` answers `403 {"error": "forbidden origin"}`
- Red before the fix because: `window.__result` contains `ORIGINAL-SECRET`.

### SPEC-0005/BT-006: Cross origin reads refused on every content route
- Parametrized over `/content-frame`, `/status`, `/export/pptx`, `/export/docx`
- When `GET <route>` with `Origin: https://evil.example`
- Then `403`, body `{"error": "forbidden origin"}`, no `Access-Control-Allow-Origin` header; And the body contains neither `ORIGINAL-SECRET` nor `str(doc_path)`
- Red before the fix because: `200` with `Access-Control-Allow-Origin: *`.

### SPEC-0005/BT-007: DNS rebinding host refused
- Parametrized over `GET /`, `GET /content`, `GET /status`, `POST /content` (`Content-Type: application/json`, body `{"html": "<p>PWNED</p>"}`)
- When sent with `Host: attacker.example:P`, no `Origin`
- Then `403`, body `{"error": "forbidden host"}`; And the body does not contain `str(doc_path)`; And `doc.html` unchanged
- Red before the fix because: `GET /status` answers `200` with the path.

### SPEC-0005/BT-010: Same origin requests served
- When `GET /content` with (`Host: 127.0.0.1:P`, `Origin: http://127.0.0.1:P`), then (`Host: localhost:P`, `Origin: http://localhost:P`), then (`Host: LOCALHOST:P`, no `Origin`)
- Then each `200`, body contains `ORIGINAL-SECRET`

### SPEC-0005/BT-011: Mismatched or null origins refused
- When `GET /content`, `Host: 127.0.0.1:P` with `Origin: http://localhost:P`, then `Origin: http://127.0.0.1:Q`, then `Origin: null`
- Then each `403 {"error": "forbidden origin"}`

### SPEC-0005/BT-012: Host port is not checked
- When `GET /content` with `Host: 127.0.0.1:Q` (Q not P), then `Host: 127.0.0.1`, then `Host: localhost:7999`, no `Origin`
- Then each `200`, body contains `ORIGINAL-SECRET`

### SPEC-0005/BT-013: No CORS headers on any response
- When `GET /`, `GET /content`, `GET /status`, `GET /health`, and `POST /content` (`Content-Type: application/json`, body `{"html": "<!DOCTYPE html><html><body><p>ORIGINAL-SECRET</p></body></html>"}`) are sent same origin
- Then no response has `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods` or `Access-Control-Allow-Headers`

### SPEC-0005/BT-016: Health open to any origin
- When `GET /health` with `Origin: https://evil.example` and `Host: attacker.example:P`
- Then `200`, JSON keys exactly `{"status", "version", "file", "port"}`, `status == "ok"`

### SPEC-0005/BT-017: Refusal logged without body
- Given `caplog.set_level(logging.WARNING, logger="mcp_htmleditor.http_server")`
- When BT-003's request is sent
- Then exactly one WARNING record contains `POST`, `/content` and `https://evil.example`; no record contains `PWNED`

### SPEC-0005/BT-022: Docker healthcheck request still answered
- When `urllib.request.urlopen("http://127.0.0.1:P/health")` (default headers)
- Then status `200`

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, existing test files, `Dockerfile`, `docker-compose*.yml`.
- Dependencies not to add: none allowed.
- Patterns to avoid: per route checks; logging request bodies; reading `os.environ` (use the bind host argument).
- Scope boundary: the 415 rule (BR-004) and the 405 preflight (BR-005) are US-0003; keep the raw `text/plain` branch of `_receive_content` for now (BT-003 is refused by origin).

## Definition of done

- [ ] RED evidence recorded for BT-001 to BT-007 before the production change.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_http_caching.py`, `tests/test_http_health.py`, `tests/test_http_export.py`, every `tests/test_*_e2e.py` pass unmodified.
- [ ] Docs updated: `.agent_docs/architecture.md:25`.
- [ ] Self review: full; security rules (literal payloads, second channel, red before).
- [ ] One commit `US-0002: Refuse foreign origins and host names, drop CORS`, body `Spec: SPEC-0005` and `BR-001, BR-002, BR-003, BR-006, BR-007, BR-008`, plus one `Exploits:` line per occurrence.
