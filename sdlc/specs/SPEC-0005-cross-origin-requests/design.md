# SPEC-0005: Any web page can read and overwrite the edited document, design

> Spec: sdlc/specs/SPEC-0005-cross-origin-requests/spec.md
> Nature: BUG
> Depth: M
> Security: internal finding
> Designed on: 2026-10-10
> Target tier: 2 (default: no `--tier`, no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| HTTP server | stdlib `http.server.ThreadingHTTPServer` (existing) | Python >=3.13 | existing code `src/mcp_htmleditor/http_server.py:19` |
| URL parsing | stdlib `urllib.parse.urlsplit` (existing import family, `http_server.py` already uses `urlparse`) | stdlib | DEC-003 |
| Tests | pytest, pytest-playwright (existing, `pyproject.toml:35`) | as locked | DEC-007 |

Skills loaded: python. Effect: `make check` gate, logging with `%` formatting on the module logger,
no new dependency, tests through `make test`.

## 2. Approaches

### Chosen: one request gate before dispatch, at the root cause sites
A single check runs first in `do_GET` and `do_POST` (`http_server.py:101`, `:129`): exempt
`GET /health`, then validate `Host` (BR-002), then `Origin` (BR-001); a refusal answers 403 and
returns before the route runs. The CORS helper (`http_server.py:86`) and its six call sites go away
(BR-003); `do_OPTIONS` answers 405 (BR-005); `POST /content` refuses non JSON bodies (BR-004).
Pros: every route, current and future, passes through the same gate; fixes exactly the three root
cause lines. Cons: a new route added outside `do_GET`/`do_POST` dispatch would bypass it (none exists:
the class sweep found only these two). Scope: `http_server.py` only.

### Rejected: per route checks
Call the check inside each of the 9 handlers. Rejected (DEC-001): 9 call sites, the same mistake
(forgetting one) that caused this bug.

### Rejected: token or cookie based CSRF protection
Rejected (DEC-002): needs a secret handed to the page, changes the editor, and the spec asks for
origin and host rules, not authentication (token auth is BL-0019).

## 3. Architecture

```
browser / curl ──► ThreadingHTTPServer (bind host, port)
                     └─ _EditorHandler.do_GET / do_POST
                          ├─ path == /health ─────────────► health (no gate, BR-006)
                          ├─ _refuse_untrusted_request() ─► 403 forbidden host | forbidden origin (+ WARNING log)
                          └─ existing dispatch (unchanged routes)
                        do_OPTIONS ───────────────────────► 405, Allow: GET, POST
                        _receive_content ─ Content-Type ≠ application/json ─► 415
```

The bind host is stored on the server instance at start (`start_http_server`, `http_server.py:639`)
so the handler can read it as `self.server.bind_host` (DEC-004).

## 4. Data model

None. No file or state format changes.

## 5. Contracts and interfaces

- Refusal body, `Content-Type: application/json`:
  - `403 {"error": "forbidden host"}` (BR-002), `403 {"error": "forbidden origin"}` (BR-001),
  - `415 {"error": "unsupported content type"}` (BR-004),
  - `405`, empty body, header `Allow: GET, POST` (BR-005).
- Allowed host names (BR-002, DEC-004): `localhost`, `127.0.0.1`, `[::1]` (and `::1` once brackets are
  stripped), plus the server's bind host when it is not `0.0.0.0` and not `::`. Comparison on the
  name part of `Host`, lower cased, port ignored. Missing or empty `Host` refused.
- Origin rule (BR-001, DEC-003): absent `Origin` passes; otherwise `urlsplit(origin)` must have scheme
  `http`, hostname equal (lower case) to the `Host` name, and port equal to the `Host` port (default
  80 on both sides when absent). `null` and any parse failure are foreign.
- Content type rule (BR-004, DEC-005): the media type before `;`, stripped and lower cased, must be
  `application/json`.
- Logging (BR-008, DEC-006): `logger.warning("Refused %s %s: %s %r", method, path, reason, value)` on
  the module logger `mcp_htmleditor.http_server`, never the body.
- Removed: `Access-Control-Allow-Origin`, `-Methods`, `-Headers` on every response (BR-003).

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/http_server.py` | modify: gate in `do_GET`/`do_POST`, remove CORS helper and 6 calls, store bind host | BR-001, BR-002, BR-003, BR-006, BR-008 | US-0002 |
| `src/mcp_htmleditor/http_server.py` | modify: `do_OPTIONS` 405, `_receive_content` media type | BR-004, BR-005 | US-0003 |
| `tests/test_http_origin_e2e.py` | create | BT-001 to BT-007, BT-010 to BT-013, BT-016, BT-017, BT-022 | US-0002 |
| `tests/test_http_origin_e2e.py` | extend | BT-014, BT-015, BT-020, BT-021 | US-0003 |
| `.agent_docs/architecture.md` | modify line 25: routes, origin and host gate | BR-001, BR-002 | US-0002 |
| `README.md` | add a "Security model" paragraph: loopback names only, same origin only, container network exposure not authenticated (BL-0019) | BR-001, BR-002 | US-0003 |

Affected existing tests: all kept (`tests/test_http_caching.py`, `tests/test_http_health.py`,
`tests/test_http_export.py`, browser e2e files). `rg -n "Access-Control|Origin" tests` returns nothing.

## 7. Compatibility and risks

- Breaking, declared by the spec: cross origin clients and `text/plain` saves stop working. The only
  known consumer is the bundled editor (spec, question 6).
- Container: `docker run -p 7999:7842` keeps working (port not checked). Opening the container via a
  LAN IP or a host name other than the loopback names is refused unless `HTMLEDITOR_HOST` names it;
  the image sets `0.0.0.0`, which never counts. Stated in README (US-0003).
- Ordering: US-0002 first (reproduction and gate); US-0003 adds the 415 and 405 rules. Each leaves
  `make check` green.
- Rollback: revert the story commits. No dependency added or removed.

## 8. Security design

- **Threat surface:** trust boundary between any browser origin (and any DNS name pointing at
  loopback) and the preview server; sinks are the document file (write: `http_server.py:308`,
  `arch_layout.py:1202` through `POST /arch-layout`) and every response carrying document content,
  path or exports.
- **Per occurrence:**

| Occurrence | Fix site | Mechanism | DEC | Exploit test, second channel |
|---|---|---|---|---|
| `POST /content` | gate at `http_server.py:129`, media type at `:277` | host allow list, origin match, JSON only | DEC-001, DEC-005 | BT-001, BT-002, BT-003: file on disk read back |
| `POST /arch-layout` | gate at `http_server.py:129` | same | DEC-001 | BT-004: file on disk, no `data-x` |
| `GET /content` | gate at `http_server.py:101` | same, no CORS | DEC-001 | BT-005: browser script result plus direct 403 |
| `GET /content-frame`, `/status`, `/export/pptx`, `/export/docx` | gate at `http_server.py:101` | same | DEC-001 | BT-006: body has no secret, no path |
| DNS rebinding, all protected routes | gate at `:101` and `:129` | host allow list | DEC-004 | BT-007: body has no path, file unchanged |

- **Never logged or traced:** request bodies and document content (BR-008). The refused header value
  is logged with `%r` so control characters cannot forge log lines.
- **Secrets:** none involved.
- All exploit tests are red on main `0082153` (observed behaviors 1 to 6 of BUG-001).

## 9. Test strategy

All in `tests/test_http_origin_e2e.py`. HTTP client tests use `http.client.HTTPConnection` so `Host`
can be set explicitly (DEC-007); browser tests use the pytest-playwright `page` fixture with a second
stdlib `http.server` serving the attacker page on another free port.

| Test | Level | Driver | Story |
|---|---|---|---|
| BT-001 | exploit e2e (reproduction) | Playwright, attacker page on port Q | US-0002 |
| BT-002, BT-003, BT-004, BT-006, BT-007 | exploit | `http.client` with literal headers and payloads | US-0002 |
| BT-005 | exploit e2e | Playwright attacker page plus `http.client` | US-0002 |
| BT-010, BT-011, BT-012, BT-013, BT-016, BT-022 | functional | `http.client` | US-0002 |
| BT-017 | functional | `http.client` plus `caplog` | US-0002 |
| BT-014, BT-015 | functional | `http.client` | US-0003 |
| BT-020 | functional e2e | Playwright on the editor page | US-0003 |
| BT-021 | regression suite | `make check` | US-0003 |

Test data: generated in `tmp_path` (`doc.html` with `ORIGINAL-SECRET`; a declarative diagram for
BT-004; a copy of the `carbon` bootstrap for BT-020). BT-001 is red today because the `text/plain`
cross origin POST writes `PWNED`.

## 10. Decisions log

- **DEC-001:** One gate method `_refuse_untrusted_request()` called first in `do_GET` and `do_POST`,
  after the `/health` exemption; it sends the 403 and returns `True` when refused. **Obliged by:**
  SPEC-0005/BR-001, BR-002, BR-006. **Rationale:** the two dispatchers are the only entry points
  (class sweep); one call site cannot be forgotten per route. **Alternatives considered:** per route
  checks; token CSRF (DEC-002). **Source:** design. **Evidence:** `http_server.py:101`, `:129`.
- **DEC-002:** No token or cookie CSRF scheme. **Obliged by:** SPEC-0005/BR-007 (bundled editor
  unchanged). **Rationale:** origin and host checks satisfy every BR without touching the page; auth is
  BL-0019. **Alternatives considered:** synchronizer token, double submit cookie. **Source:** design.
  **Evidence:** n/a.
- **DEC-003:** Origin parsed with `urllib.parse.urlsplit`; scheme, lower cased hostname and port
  (default 80) compared to the `Host` header parsed the same way (`urlsplit("//" + host)`); any
  `ValueError` means foreign. **Obliged by:** SPEC-0005/BR-001. **Rationale:** stdlib, handles IPv6
  brackets. **Alternatives considered:** string equality on `"http://" + Host` (fails on case).
  **Source:** design. **Evidence:** `http_server.py` imports `urlparse` already.
- **DEC-004:** Allowed host names are the three loopback names plus the actual bind host
  (`start_http_server` argument, defaulting to `HTMLEDITOR_HOST`), stored as `server.bind_host`;
  `0.0.0.0` and `::` never count. **Obliged by:** SPEC-0005/BR-002. **Rationale:** the CLI `--host`
  and `HTMLEDITOR_HOST` are the same setting (`http_server.py:622`); using the effective value keeps
  `serve --host myname` working. **Alternatives considered:** read `default_host()` in the handler
  (misses `--host`). **Source:** existing code. **Evidence:** `http_server.py:622`, `config.py:271`.
- **DEC-005:** Media type check on `Content-Type` split at `;`, stripped, lower cased, equal to
  `application/json`; done in `_receive_content` before reading JSON; the raw body branch
  (`http_server.py:286`) is removed. **Obliged by:** SPEC-0005/BR-004. **Rationale:** removes the
  preflight free path. **Alternatives considered:** keep the raw branch for same origin (rejected by
  the spec). **Source:** spec constraint. **Evidence:** `http_server.py:277`, `:286`.
- **DEC-006:** Refusals log one WARNING with method, path, reason and the refused header value via
  `%r`. **Obliged by:** SPEC-0005/BR-008. **Rationale:** AGENTS.md logging rule, no content.
  **Alternatives considered:** a trace span per refusal (no span exists for routing today).
  **Source:** design. **Evidence:** `http_server.py:31`.
- **DEC-007:** HTTP level tests use `http.client.HTTPConnection` (stdlib) so `Host` and `Origin` are
  sent verbatim; browser tests follow `tests/test_undo_redo_e2e.py`. **Obliged by:** SPEC-0005/BT-007,
  BT-012. **Rationale:** `urllib` rewrites `Host` from the URL. **Alternatives considered:** `urllib`
  with `Request.add_unredirected_header`. **Source:** design. **Evidence:** `tests/test_undo_redo_e2e.py:108`.
- **DEC-008:** `do_OPTIONS` answers `405` with `Allow: GET, POST`, `Content-Length: 0`. **Obliged by:**
  SPEC-0005/BR-005. **Rationale:** exact spec contract. **Alternatives considered:** remove `do_OPTIONS`
  (stdlib then answers 501). **Source:** spec constraint. **Evidence:** `http_server.py:91`.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0002 | Refuse foreign origins and host names, drop CORS | P1 | BR-001, BR-002, BR-003, BR-006, BR-007 (partial), BR-008 | main | 2 | no |
| US-0003 | JSON only saves, refused preflight, editor non regression | P1 | BR-004, BR-005, BR-007 | US-0002 | 2 | yes |
