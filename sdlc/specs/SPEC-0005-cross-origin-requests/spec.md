# Any web page can read and overwrite the edited document: Bug Specification

> Generated on: 2026-10-10
> Id: SPEC-0005
> Nature: BUG
> Depth: M
> Depth evidence: 1 module (preview HTTP server) plus container configuration; 9 HTTP routes in the sweep, 7 vulnerable; 8 requirements; public HTTP contract changes (403 and 415 answers, CORS headers removed); no data model change
> Status: specified
> Verdict: no authority
> Defect class: absent
> Severity: High
> From backlog: BL-0005
> Security: internal finding
> CVSS: 8.1 CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:N (self assessed: a victim with the editor running opens a malicious page)
> Affected: every version up to 0c424f8 (main, 2026-10-10)
> Fixed in: unreleased

## 1. Defect

### BUG-001: The preview server answers requests from any web origin and any host name

- **Observed behavior:** reproduced on 2026-10-10 against a real server bound to `127.0.0.1`, serving
  a document containing `ORIGINAL-SECRET`:
  1. `POST /content` with `Origin: https://evil.example`, `Content-Type: text/plain`, body
     `<p>PWNED</p>` answered `200 {"ok": true}` and the file on disk then contained `PWNED`, not
     `ORIGINAL-SECRET`.
  2. `GET /content` with that origin answered `200` with the document and
     `Access-Control-Allow-Origin: *`, so a script on that origin can read the response.
  3. Preflight `OPTIONS /content` answered `204`, `Access-Control-Allow-Origin: *`,
     `Access-Control-Allow-Methods: GET, POST, OPTIONS`.
  4. `POST /arch-layout` with that origin answered `200` and rewrote the file.
  5. `GET /status` with `Host: attacker.example:<port>` answered `200` with the absolute file path.
  6. `GET /export/pptx` with that origin answered `200` with `Access-Control-Allow-Origin: *`.
- **Expected per authority:** none: no authority. SPEC-0001 section 7 only says "Local, single user:
  no authentication on the preview server; default bind is the loopback host".
- **Reproduction:** start the editor on a document, open in the same browser a page from another
  origin whose script sends `fetch("http://127.0.0.1:<port>/content", {method: "POST", body:
  "<p>PWNED</p>"})`. Expected: the request is refused and the document unchanged. Actual: the
  document on disk is replaced.
- **Root cause:** no request handler checks the `Origin` or `Host` request header before dispatching
  (`src/mcp_htmleditor/http_server.py:101` GET, `src/mcp_htmleditor/http_server.py:129` POST); every
  response carries `Access-Control-Allow-Origin: *` (`src/mcp_htmleditor/http_server.py:87`, emitted
  from `:94`, `:217`, `:246`, `:365`, `:374`, `:396`); and `POST /content` accepts a non JSON body as
  raw HTML (`src/mcp_htmleditor/http_server.py:286`), which browsers send cross origin without a
  preflight.
- **Contributing factors:** the threat model stopped at "bound to loopback"; a browser on the same
  machine is reachable by every site the user visits. The container image binds all interfaces
  (`Dockerfile:33`, `docker-compose.yml:16`). No test sends an `Origin` or `Host` header
  (`rg -n "Origin|Access-Control" tests` returns nothing).
- **Impact:** any user running the editor who opens a malicious or compromised page: silent
  overwrite of the edited document, theft of its content, its exported deck or document, and its
  absolute path. No workaround besides stopping the editor while browsing.
- **Rollback posture:** a revert of the fix restores today's behavior; no file format changes, so
  documents stay readable by every version.

## 1bis. Class Sweep

**Class:** requests issued by an untrusted browser origin, or addressed through an untrusted host
name, reach request handlers that read or modify the edited document without verifying who sent
them (CWE-352 cross site request forgery, CWE-942 permissive cross origin policy, CWE-346 origin
validation error; DNS rebinding through an unchecked host name).

**Searches run (whole repository, sources, templates, Docker and Makefile):**
- `rg -n 'path == "|path.startswith\(|path in \{' src/mcp_htmleditor/http_server.py`: every routed
  path of the HTTP handler (idiom: request dispatch).
- `rg -n 'Access-Control|headers.get\("(Origin|Host|Referer)' -g '!tests' .`: cross origin headers
  emitted and request identity headers read (idiom: CORS policy and origin checks). Only hits:
  `http_server.py:87` to `:89`; no read of `Origin`, `Host` or `Referer` anywhere.
- `rg -n 'HTTPServer|socketserver|\.listen\(|uvicorn|starlette|websocket|run_server|FastMCP\(|transport' src tools Dockerfile docker-compose*.yml Makefile`:
  every other network listener (idiom: a second server). Only `ThreadingHTTPServer`
  (`http_server.py:639`); the MCP server uses stdio (`src/mcp_htmleditor/mcp_server.py:206`), not
  reachable from a browser.
- Not searched: cookie or session handling (`rg -n -i cookie src` would only confirm none exists:
  the server has no session, so ambient credential theft is not part of this class).

| Occurrence | Verdict | Disposition |
|---|---|---|
| `POST /content` (`src/mcp_htmleditor/http_server.py:134`, handler `:267`) | vulnerable: overwrites the document | BR-001, BR-002, BR-004 |
| `POST /arch-layout` (`http_server.py:136`, handler `:317`) | vulnerable: rewrites the document | BR-001, BR-002 |
| `GET /content` (`http_server.py:110`, handler `:161`) | vulnerable: leaks the document | BR-001, BR-002, BR-003 |
| `GET /content-frame` (`http_server.py:112`, handler `:174`) | vulnerable: leaks the document | BR-001, BR-002, BR-003 |
| `GET /status` (`http_server.py:114`, handler `:255`) | vulnerable: leaks the absolute path | BR-001, BR-002, BR-003 |
| `GET /export/pptx` (`http_server.py:118`, handler `:194`) | vulnerable: leaks the exported deck | BR-001, BR-002, BR-003 |
| `GET /export/docx` (`http_server.py:120`, handler `:226`) | vulnerable: leaks the exported document | BR-001, BR-002, BR-003 |
| `GET /`, `GET /static/<name>` (`http_server.py:106`, `:108`) | safe for content: serves only files under the package static directory, basename only (`http_server.py:153`); still covered by BR-002 for DNS rebinding of the shell | BR-002 |
| `GET /health` (`http_server.py:116`) | safe: returns status, version, file path and port only for the healthcheck; path leak accepted by the user ("go", question 3) because the container healthcheck calls it (`Dockerfile:61`) | BR-006 |
| Network access to the published container port (`Dockerfile:33`) | vulnerable to any network client, not a browser origin issue | BL-0019 |

## 2. Expected Behavior

Casing: header names as sent on the wire (`Origin`, `Host`), JSON keys lowercase, as in
`src/mcp_htmleditor/http_server.py`. "Protected route" means every route above except `GET /health`.

#### BR-001 [EARS-O]: Foreign origins refused
> IF a request to a protected route carries an `Origin` header that is not the editor's own origin THEN THE preview server SHALL answer `403` with body `{"error": "forbidden origin"}` and SHALL NOT run the route.

- **Source:** decided here: user answer "go" to question 1 (default: reject foreign `Origin` with 403).
- **Inputs:** `Origin` header value; the editor's own origin is `http://<Host header value>` where the
  `Host` header passes BR-002.
- **Business Rules:** comparison is exact on scheme, host and port, case insensitive on the host.
  `Origin: null` is foreign. A request without an `Origin` header is not refused by this rule (CLI
  tools, the healthcheck, same origin navigations).
- **Exact names:** status `403`, `Content-Type: application/json`, body `{"error": "forbidden origin"}`.

#### BR-002 [EARS-O]: Foreign host names refused
> IF a request to a protected route carries a `Host` header whose name is not `localhost`, `127.0.0.1`, `[::1]` or the configured `HTMLEDITOR_HOST` THEN THE preview server SHALL answer `403` with body `{"error": "forbidden host"}` and SHALL NOT run the route.

- **Source:** decided here: user answer "go" to question 2.
- **Business Rules:** `HTMLEDITOR_HOST` counts only when it is not `0.0.0.0` and not `::`. A missing
  `Host` header is refused. The port part of `Host` is not checked: any port, or none, is
  accepted, so a published container port (`-p 7999:7842`) keeps working. BR-002 is evaluated
  before BR-001.
- **Amended:** 2026-10-10, port clause removed (user answer "go" to design issue
  `design-issues.md` 2026-10-10).
- **Exact names:** status `403`, body `{"error": "forbidden host"}`, setting `HTMLEDITOR_HOST`.

#### BR-003 [EARS-UB]: No cross origin read permission
> The preview server SHALL NOT send `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods` or `Access-Control-Allow-Headers` on any response.

- **Source:** decided here: user answer "go" to question 1 ("stop sending `Access-Control-Allow-Origin`").

#### BR-004 [EARS-O]: Save body must be JSON
> IF `POST /content` carries a `Content-Type` other than `application/json` (parameters such as `; charset=utf-8` allowed) THEN THE preview server SHALL answer `415` with body `{"error": "unsupported content type"}` and SHALL NOT write the document.

- **Source:** decided here: user answer "go" to question 4.

#### BR-005 [EARS-O]: Preflight refused
> IF an `OPTIONS` request reaches the preview server THEN THE preview server SHALL answer `405` with an empty body and an `Allow: GET, POST` header.

- **Source:** decided here: follows from BR-003 and question 1 (no cross origin access is offered,
  so no preflight is granted). ASSUMED status `405`.

#### BR-006 [EARS-U]: Health stays open
> The preview server SHALL answer `GET /health` with `200` and its current body whatever the `Origin` and `Host` headers.

- **Source:** decided here: user answer "go" to question 3 (every route except `/health`).

#### BR-007 [EARS-U]: The bundled editor keeps working
> The preview server SHALL serve, save, poll, export and lay out for the editor page it serves itself, opened at `http://localhost:<port>/` or `http://127.0.0.1:<port>/`.

- **Source:** decided here: user answer "go" to question 6 (the bundled editor is the only consumer).
- **Business Rules:** the editor's own requests are same origin (`src/mcp_htmleditor/static/editor.js:1418`
  sends `Content-Type: application/json`).

#### BR-008 [EARS-O]: Refusals are logged without content
> IF a request is refused by BR-001, BR-002 or BR-004 THEN THE preview server SHALL log one warning line naming the method, the path and the refused header value, and SHALL NOT log the request body.

- **Source:** decided here: ASSUMED, from `AGENTS.md` logging and tracing rules (never document
  content in logs or spans).

## 3. Edge Cases

| Case | Expected behavior | Requirement |
|---|---|---|
| `Origin: http://127.0.0.1:<port>` and `Host: 127.0.0.1:<port>` | served | BR-001, BR-007 |
| `Origin: http://localhost:<port>` and `Host: 127.0.0.1:<port>` | 403 forbidden origin (origin must match the host used) | BR-001 |
| `Origin: http://127.0.0.1:<other port>` | 403 forbidden origin | BR-001 |
| `Origin: null` (sandboxed page, file URL) | 403 forbidden origin | BR-001 |
| no `Origin`, `Host: 127.0.0.1:<port>` (curl, CLI) | served | BR-001, BR-002 |
| `Host: LOCALHOST:<port>` | served (host name case insensitive) | BR-002 |
| `Host: attacker.example:<port>` | 403 forbidden host | BR-002 |
| `Host: 127.0.0.1` with no port, server on 7842 | served (port not checked) | BR-002 |
| `Host: 127.0.0.1:Q`, Q not the bound port | served (port not checked) | BR-002 |
| `Content-Type: application/json; charset=utf-8` on save | accepted | BR-004 |
| `GET /health` with `Origin: https://evil.example` | 200, current body | BR-006 |
| container: `HTMLEDITOR_HOST=0.0.0.0`, browser on host opens `http://localhost:7999/` | served (`Host: localhost:7999` is a loopback name; the port is not checked) | BR-002, BL-0019 |

## 4. Tests

Driver unless stated: pytest, real `ThreadingHTTPServer` started on a free port on `127.0.0.1`, as in
`tests/test_undo_redo_e2e.py`, document `doc.html` in `tmp_path` containing `ORIGINAL-SECRET`. "File
unchanged" means `doc.html` read from disk equals its content before the request, byte for byte.

### 4.1 End to end reproduction (mandatory)
#### BT-001: A page from another origin cannot overwrite the document
- **Reproduces:** BUG-001
- **Driver:** Playwright Chromium; attacker page served by a second `http.server` on another free port
- **Fails today because:** the server accepts the cross origin `text/plain` POST and writes it (`http_server.py:286`).
- Given the editor server on port P serving `doc.html`, and an attacker page at `http://127.0.0.1:Q/`
- When the attacker page runs `fetch("http://127.0.0.1:P/content", {method: "POST", body: "<p>PWNED</p>"})` and waits 500 ms
- Then `doc.html` on disk still contains `ORIGINAL-SECRET` and does not contain `PWNED`

### 4.1bis Exploit tests
Each is red today (verified behavior in BUG-001, items 1 to 6). Driver: HTTP client (`urllib`) with
explicit headers, except BT-005 (browser).

#### BT-002: Cross origin JSON save refused
- **Covers:** `POST /content` (`http_server.py:134`)
- **Red before the fix because:** answers `200 {"ok": true}` and writes.
- When `POST /content`, `Origin: https://evil.example`, `Content-Type: application/json`, body `{"html": "<p>PWNED</p>"}`
- Then status `403`, body `{"error": "forbidden origin"}`
- And `doc.html` on disk unchanged

#### BT-003: Cross origin text save refused
- **Covers:** `POST /content`, simple request path (`http_server.py:286`)
- **Red before the fix because:** answers `200` and writes `PWNED`.
- When `POST /content`, `Origin: https://evil.example`, `Content-Type: text/plain`, body `<p>PWNED</p>`
- Then status `403`, body `{"error": "forbidden origin"}`
- And `doc.html` on disk unchanged

#### BT-004: Cross origin layout refused
- **Covers:** `POST /arch-layout` (`http_server.py:136`)
- **Red before the fix because:** answers `200 {"ok": true, ...}`.
- Given `doc.html` holds a declarative diagram (one `arch-row` with two `arch-node`, no positions)
- When `POST /arch-layout`, `Origin: https://evil.example`, empty body
- Then status `403`, body `{"error": "forbidden origin"}`
- And `doc.html` on disk unchanged (no `data-x` attribute appeared)

#### BT-005: A page from another origin cannot read the document
- **Covers:** `GET /content` (`http_server.py:110`)
- **Driver:** Playwright Chromium, attacker page as in BT-001
- **Red before the fix because:** `Access-Control-Allow-Origin: *` lets the script read the body.
- When the attacker page runs `fetch("http://127.0.0.1:P/content").then(r => r.text())` and stores the outcome in `window.__result` (text, or the error name)
- Then `window.__result` does not contain `ORIGINAL-SECRET`
- And a direct `GET /content` with `Origin: https://evil.example` answers `403 {"error": "forbidden origin"}`

#### BT-006: Cross origin reads refused on every content route
- **Covers:** `GET /content-frame` (`:112`), `GET /status` (`:114`), `GET /export/pptx` (`:118`), `GET /export/docx` (`:120`); one parametrized case per route
- **Red before the fix because:** each answers `200` with `Access-Control-Allow-Origin: *`.
- When the route is requested with `Origin: https://evil.example`
- Then status `403`, body `{"error": "forbidden origin"}`, no `Access-Control-Allow-Origin` header
- And the response body contains neither `ORIGINAL-SECRET` nor the absolute path of `doc.html`

#### BT-007: DNS rebinding host refused
- **Covers:** every protected route (`http_server.py:106` to `:136`); parametrized over `GET /`, `GET /content`, `GET /status`, `POST /content`
- **Red before the fix because:** `GET /status` with `Host: attacker.example:P` answers `200` with the path.
- When the route is requested with `Host: attacker.example:P` and no `Origin`; the POST carries `Content-Type: application/json`, body `{"html": "<p>PWNED</p>"}`
- Then status `403`, body `{"error": "forbidden host"}`
- And the body does not contain the absolute path of `doc.html`, and `doc.html` on disk is unchanged

### 4.2 New behavior
#### BT-010: Same origin requests served
- **Validates:** BR-001, BR-002, BR-007
- When `GET /content` with `Host: 127.0.0.1:P`, `Origin: http://127.0.0.1:P`; then with `Host: localhost:P`, `Origin: http://localhost:P`; then with `Host: LOCALHOST:P` and no `Origin`
- Then each answers `200` and the body contains `ORIGINAL-SECRET`

#### BT-011: Mismatched or null origins refused
- **Validates:** BR-001
- When `GET /content` with `Host: 127.0.0.1:P` and, in turn, `Origin: http://localhost:P`, `Origin: http://127.0.0.1:Q`, `Origin: null`
- Then each answers `403 {"error": "forbidden origin"}`

#### BT-012: Host port is not checked
- **Validates:** BR-002
- When `GET /content` with `Host: 127.0.0.1:Q` (Q not P), then `Host: 127.0.0.1`, then `Host: localhost:7999`, each with no `Origin`
- Then each answers `200` and the body contains `ORIGINAL-SECRET`

#### BT-013: No CORS headers on any response
- **Validates:** BR-003
- When `GET /`, `GET /content`, `GET /status`, `GET /health`, `POST /content` (same origin, JSON) are sent
- Then no response has an `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods` or `Access-Control-Allow-Headers` header

#### BT-014: Non JSON save refused even same origin
- **Validates:** BR-004
- When `POST /content`, `Host: 127.0.0.1:P`, no `Origin`, `Content-Type: text/plain`, body `<p>X</p>`
- Then status `415`, body `{"error": "unsupported content type"}`, `doc.html` on disk unchanged
- And with `Content-Type: application/json; charset=utf-8`, body `{"html": "<!DOCTYPE html><html><body><p>X</p></body></html>"}`: status `200`, `doc.html` contains `<p>X</p>`

#### BT-015: Preflight refused
- **Validates:** BR-005
- When `OPTIONS /content` with `Origin: https://evil.example`, `Access-Control-Request-Method: POST`
- Then status `405`, header `Allow: GET, POST`, empty body, no `Access-Control-Allow-Origin` header

#### BT-016: Health open to any origin
- **Validates:** BR-006
- When `GET /health` with `Origin: https://evil.example` and `Host: attacker.example:P`
- Then status `200`, body keys exactly `status`, `version`, `file`, `port`, `status` = `"ok"`

#### BT-017: Refusal logged without body
- **Validates:** BR-008
- Given log capture at WARNING on the `mcp_htmleditor.http_server` logger
- When BT-003's request is sent
- Then exactly one warning record contains `POST`, `/content` and `https://evil.example`, and no record contains `PWNED`

### 4.3 Non regression
#### BT-020: Browser editor still saves, polls, exports
- **Protects:** BR-007, SPEC-0002/FR-004, SPEC-0001/FR-003
- **Driver:** Playwright Chromium on `http://127.0.0.1:P/`
- Given `doc.html` is a copy of the `carbon` slide bootstrap with `ORIGINAL-SECRET` in its title
- When edit mode is on, the first editable zone is clicked, End pressed, `AAA` typed, 1500 ms waited, then the editor page runs `fetch('/export/pptx').then(r => r.status)`
- Then `doc.html` contains `AAA`, `#toolbar-status` color is `rgb(66, 190, 101)`, and the fetch result is `200`

#### BT-021: Existing suites unchanged
- **Protects:** all existing browser and HTTP behaviors
- When `make check` runs
- Then every test of `tests/test_autosave_focus_e2e.py`, `tests/test_undo_redo_e2e.py`, `tests/test_website_template_e2e.py`, `tests/test_tab_title_e2e.py`, `tests/test_fullscreen_e2e.py`, `tests/test_http_health.py`, `tests/test_http_caching.py`, `tests/test_http_export.py` passes unmodified

#### BT-022: Docker healthcheck request still answered
- **Protects:** container health (`Dockerfile:61`)
- When `GET http://127.0.0.1:P/health` is sent with Python `urllib` default headers (no `Origin`)
- Then status `200`

### 4.4 Existing tests asserting the current behavior
| Test file | Test name | Action | Reason |
|---|---|---|---|
| `tests/test_http_caching.py` | 3 tests | Kept | assert cache headers only; `rg -n "Access-Control" tests` returns nothing |
| `tests/test_http_health.py` | 3 tests | Kept | health unchanged (BR-006) |
| `tests/test_http_export.py` | 3 tests | Kept | call exporters directly, no headers |
| all browser e2e files | all | Kept | same origin, must stay green (BT-021) |

## 5. Existing Specs Affected

- SPEC-0001 section 3 Interfaces of its design ("CORS `*`", `sdlc/specs/SPEC-0001-mcp-htmleditor/design.md`)
  and the `OPTIONS 204` route become false after this fix. SPEC-0001 is as-built and not edited; this
  spec supersedes those two statements.
- SPEC-0001 section 7 "Local, single user: no authentication": unchanged, now complemented by origin
  and host checks.

## 6. Assumptions

- **Assumption:** `OPTIONS` answers `405` (BR-005); any non 2xx would deny the preflight.
- **Assumption:** refusal logging at WARNING with method, path, header value (BR-008).
- **Assumption:** the editor's own origin is derived from the `Host` header after BR-002 accepts it
  (BR-001); a user who opens `localhost` keeps `localhost` for all requests (browser behavior).
- **User decision:** network exposure of the container is deferred, not fixed here (question 5,
  default a, answered "go").
- **Backlog entries created by this run:** BL-0019 (container port reachable by any network client
  without authentication, deferred by user decision). Consumed: BL-0005.

## 7. Implementability Checklist

| # | Item | Result |
|---|---|---|
| 1 | No technical decision | PASS: root cause lines only; no mechanism chosen |
| 2 | No buried requirement | PASS: 405 preflight, logging, health each have their own BR |
| 3 | Names spelled | PASS: statuses, JSON bodies, headers, `HTMLEDITOR_HOST`, routes, logger name |
| 4 | No forced choice | PASS: missing Origin, missing Host, null, case, port (not checked, amended 2026-10-10), charset, check order stated |
| 5 | Tests specified | PASS: BT-001 to BT-007, BT-010 to BT-017, BT-020 to BT-022 with exact values; 4.4 lists every HTTP test file |
| 6 | Reproduction end to end | PASS: BT-001 drives a real cross origin page, asserts the file on disk |
| 7ante | Security classification | PASS: `Security: internal finding` |
| 7bis | Sweep real | PASS, fresh read only auditor (2026-10-10): (a) class is source and sink only, three idioms; (b) the three searches rerun, no omitted hit; (c) own sink searches (`write_text`, `.save(`, write mode `open`) found `http_server.py:308`, `arch_layout.py:1202` via `POST /arch-layout`, export temp files via `GET /export/*`, all in the table; `state.py:66` reached only from server start and stop, not from a route; (d) `http_server.py:153` and `Dockerfile:61` opened, controls hold; (e) every vulnerable route has its exploit test with literal payload and second channel; (f) BL-0019 opened: Nature BUG, Evidence, Decision; (g) no other listener (MCP is stdio) |
| 8 | No hidden prerequisite | PASS: server, file content and ports are in every Given |
| 9 | EARS clean | PASS |
| 10 | Right tool | PASS: behavior changes, no new capability (token auth deferred to BL-0019) |
| 11 | Length | PASS: within M budget |
| 12 | Claims cited | PASS: lines re-read on 0c424f8 |
| 13 | Round trip | PASS: writer of the editor request (`static/editor.js:1418`) and reader (`http_server.py:277`) read |
| 14 | Verdict consistent | PASS: no authority, class absent, every BR Source is the user answer or ASSUMED |

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | amended in place: 0; moved to backlog: none |
