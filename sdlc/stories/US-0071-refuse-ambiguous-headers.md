# US-0071: Refuse ambiguous identity and framing headers

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Today the editor server reads only the first `Host`, `Origin`, `Content-Length` or `Content-Type` line, ignores
`Transfer-Encoding`, accepts `Host: evil@127.0.0.1:P` and judges a folded header with the fold inside: a local
non browser client can overwrite the document with a second `Host` line (BUG-001). This story adds one header
gate, run before the SPEC-0005 host and origin checks on every protected route, that answers `400` with a
precise message and touches nothing.

## Requirements covered

- SPEC-0013/BR-001: IF a request to a protected route carries more than one `Host`, `Origin`, `Content-Length` or `Content-Type` header field line THEN THE editor server SHALL answer `400` with body `{"error":"Duplicate <Name> header"}` and no side effect.
- SPEC-0013/BR-002: IF a request to a protected route carries a `Transfer-Encoding` header field, whatever its value THEN THE editor server SHALL answer `400` with body `{"error":"Transfer-Encoding not supported"}` and no side effect.
- SPEC-0013/BR-003: IF a request to a protected route carries a single `Host` header whose value contains `@` THEN THE editor server SHALL answer `400` with body `{"error":"Invalid Host header"}` and no side effect.
- SPEC-0013/BR-004: IF a request to a protected route carries a header field line folded onto a following line that starts with a space or a tab THEN THE editor server SHALL answer `400` with body `{"error":"Invalid header folding"}` and no side effect.
- SPEC-0013/BR-005: The editor server SHALL evaluate BR-004, then BR-001, then BR-002, then BR-003 on every request to a protected route, before the SPEC-0005 host and origin checks and before any other check of SPEC-0009/FR-NEW-007.
- SPEC-0013/BR-013 (partial: the log line of the BR-001 to BR-004 refusals): IF a request is refused by BR-001 to BR-004, BR-006 to BR-008 or BR-010 THEN THE editor server SHALL log exactly one warning line starting `Refused <METHOD> <path>: ` followed by the error text of the answer, and SHALL NOT log the request body or a traceback.
- SPEC-0013/BR-014 (partial: header shapes; time bounds are US-0078, US-0079): The editor server SHALL answer requests carrying at most one line of each header named in BR-001, no `Transfer-Encoding`, no folding and a body sent in full within the bounds of BR-008 and BR-020, exactly as it does today.

Business rules (spec, verbatim in substance): `<Name>` is the canonical name `Host`, `Origin`, `Content-Length`,
`Content-Type` whatever casing the client sent; repeated lines are refused even when their values are identical;
when several names repeat, the first in the order `Host`, `Origin`, `Content-Length`, `Content-Type` is named.
"Protected route" means every `GET` and `POST` request except `GET /health`, unknown paths included (answered
`404` after the gate). `GET /health` is answered before every check. `OPTIONS` keeps `405` with
`Allow: GET, POST`; other methods (`HEAD`, `PUT`, ...) keep the stdlib `501`. A missing `Host` keeps
`403 {"error":"forbidden host"}`; every other `Host` value keeps the SPEC-0005/BR-002 behavior. The body is not
read on a refusal. "No side effect": the served file, its history and its request record are byte for byte
unchanged and nothing is computed or written.

## Independent Test

`make test ARGS='-k header_gate'` (then `make check`): the raw request
`POST /content HTTP/1.1\r\nHost: L\r\nHost: evil.example\r\nContent-Type: application/json\r\nContent-Length: 42\r\n\r\n{"html":"<html><body>PWNED</body></html>"}`
answers `400 {"error": "Duplicate Host header"}` and `deck.html` read from disk still holds `ORIGINAL-SECRET`
and no `PWNED` (red today: `200` and `PWNED` written).

## Design excerpt

### Decisions
- DEC-011 (SPEC-0013): "The header gate is a new handler method `_refuse_ambiguous_headers()` called as the first statement of `_refuse_untrusted_request()`. Checks, in this order, each answering through `_refuse_request`: (1) folding: any value of `self.headers.items()` containing `"\r"` or `"\n"` (the stdlib keeps a continuation line inside the value: `('Host', 'L\r\n evil.example')`); (2) duplicates: for `Host`, `Origin`, `Content-Length`, `Content-Type` in that order, `len(self.headers.get_all(name) or []) > 1` (case insensitive by the stdlib); (3) `"Transfer-Encoding" in self.headers`; (4) the single `Host` value contains `"@"`." `_refuse_untrusted_request` is already called for every `GET` except `/health` and every `POST`, unknown paths included, so the gate inherits exactly the protected route set and its position before the SPEC-0005 checks.
- DEC-018 (SPEC-0013): "`tests/http_support.py` provides `exchange(port: int, data: bytes, *, timeout: float = 5.0) -> RawReply` (send the exact bytes, read until the server closes, parse status line, headers, body; `RawReply` frozen with `status: int | None`, `headers: dict[str, str]`, `body: bytes`, `raw: bytes`, `elapsed: float`, `closed: bool`) and `json_body(reply) -> Any`." A standard HTTP client merges or rejects duplicated headers and would neutralize the payload. Later stories (US-0072, US-0073, US-0078, US-0079) reuse it.

### Contracts
```python
# src/mcp_htmleditor/http_server.py, class _EditorHandler
def _refuse_ambiguous_headers(self) -> bool: ...  # True when it answered
def _refuse_request(self, status: int, error: str) -> None:
    logger.warning("Refused %s %s: %s", self.command, urlparse(self.path).path, error)
    self._send_json({"error": error}, status=status)
```
| Condition (checked in this order) | Answer |
|---|---|
| a header value holds `\r` or `\n` | 400 `{"error":"Invalid header folding"}` |
| `Host` repeated, then `Origin`, then `Content-Length`, then `Content-Type` | 400 `{"error":"Duplicate Host header"}` (resp. `Origin`, `Content-Length`, `Content-Type`) |
| `Transfer-Encoding` present | 400 `{"error":"Transfer-Encoding not supported"}` |
| the single `Host` contains `@` | 400 `{"error":"Invalid Host header"}` |
| then the existing SPEC-0005 checks | unchanged 403 answers and their existing `_refuse` log format |

Log line of the new refusals, exact: `Refused <METHOD> <path>: <error>` (for example
`Refused POST /content: Duplicate Host header`), WARNING, no header value, no body.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_server.py` | modify: `_refuse_ambiguous_headers`, `_refuse_request`, first call in `_refuse_untrusted_request` |
| `tests/http_support.py` | create: `RawReply`, `exchange`, `json_body` |
| `tests/test_http_header_gate_e2e.py` | create |
| `.agent_docs/architecture.md` | modify: one paragraph "Request gate" naming the order header checks, then host and origin, with SPEC-0013 |

### Existing patterns
- Gate: `src/mcp_htmleditor/http_server.py:107` (`_refuse_untrusted_request`), `:127` (`_refuse`), `:142` (`do_GET`, `/health` first), `:176` (`do_POST`), `:132` (`do_OPTIONS`).
- Real server fixture: `tests/conftest.py:233` `serve_deck(path) -> ServedDeck(path, port)`, started with `host="127.0.0.1"`.
- Raw request helper to imitate: `tests/test_save_safety_e2e.py:51` `_post_raw`; SPEC-0005 tests `tests/test_http_origin_e2e.py:139` `_request`, `:180` Playwright test (pattern for BT-031).
- Record and review commands for BT-035 setup: `tests/deck_support.py:244` `run_cli("review", str(deck), "--write", str(rev))`; queue through `POST /requests`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Test conventions (Spec section 4): pytest with a real editor server on a free port of `127.0.0.1`
(`serve_deck`), serving `deck.html` in `tmp_path`, a copy of the `carbon` slide bootstrap
(`templates/bootstrap/slides-empty.html`) whose title holds `ORIGINAL-SECRET`. The client is a raw TCP socket
sending the exact bytes. `P` is the port; `L` is `127.0.0.1:P`. "Unchanged" means: `deck.html` equals its bytes
before the request, `mcp-htmleditor history deck.html` prints `No history for deck.html`, and the `revision` of
`GET /requests` is unchanged. A JSON answer "is" a body when the parsed JSON equals the expected one; status
lines and log lines are compared as exact text. Level: exploit (BT-001, BT-005 to BT-012, BT-035) or functional
e2e; Location `tests/test_http_header_gate_e2e.py`.

### SPEC-0013/BT-001: A save with a local then a foreign Host does not overwrite the document
- Reproduces BUG-001. Red before the fix because: the gate reads only the first `Host` and the save runs (answers `200`, `PWNED` written).
- When the client sends `POST /content HTTP/1.1\r\nHost: L\r\nHost: evil.example\r\nContent-Type: application/json\r\nContent-Length: 42\r\n\r\n{"html":"<html><body>PWNED</body></html>"}`
- Then the status is `400` and the body is `{"error": "Duplicate Host header"}`
- And `deck.html` on disk is unchanged and does not contain `PWNED`, and `os.listdir` of the folder of `deck.html` is the same as before the request (no temporary file, BR-016)

### SPEC-0013/BT-005: Reverse Host order cannot read the document
- Red before: `GET /content` with local then foreign `Host` answers 200 with the document.
- When `GET /content HTTP/1.1\r\nHost: L\r\nHost: evil.example\r\n\r\n`
- Then status `400`, body `{"error": "Duplicate Host header"}`
- And the response bytes do not contain `ORIGINAL-SECRET`, and a following `GET /status` with `Host: L` reports the same `mtime` as before

### SPEC-0013/BT-006: Duplicated Origin refused
- Red before: answers 200.
- When `POST /content HTTP/1.1\r\nHost: L\r\nOrigin: http://L\r\nOrigin: https://evil.example\r\nContent-Type: application/json\r\nContent-Length: 42\r\n\r\n{"html":"<html><body>PWNED</body></html>"}`
- Then status `400`, body `{"error": "Duplicate Origin header"}`; and `deck.html` is unchanged

### SPEC-0013/BT-007: Duplicated Content-Length on the save refused
- Red before: first length wins, `PWNED` written.
- When `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 42\r\nContent-Length: 5\r\n\r\n{"html":"<html><body>PWNED</body></html>"}`
- Then status `400`, body `{"error": "Duplicate Content-Length header"}`; and `deck.html` is unchanged

### SPEC-0013/BT-008: Duplicated Content-Length on a request route refused
- Red before: first length wins and the request is queued.
- When `POST /requests HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 23\r\nContent-Length: 2\r\n\r\n{"instruction":"PWNED"}`
- Then status `400`, body `{"error": "Duplicate Content-Length header"}`
- And `GET /requests` with `Host: L` lists no request whose instruction is `PWNED`, and `mcp-htmleditor requests deck.html` prints no `PWNED`

### SPEC-0013/BT-009: Duplicated Content-Type refused on both body readers
- Parametrized over `POST /content` with `{"html":"<html><body>PWNED</body></html>"}` and `POST /requests` with `{"instruction":"PWNED"}`. Red before: the first `Content-Type` is checked, the write happens.
- When the route is sent with `Content-Type: application/json\r\nContent-Type: text/plain` and a correct single `Content-Length`
- Then status `400`, body `{"error": "Duplicate Content-Type header"}`; and `deck.html` and the request list are unchanged

### SPEC-0013/BT-010: Chunked body refused
- Red before: answers `400 Invalid JSON body`.
- When `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n2a\r\n{"html":"<html><body>PWNED</body></html>"}\r\n0\r\n\r\n`
- Then status `400`, body `{"error": "Transfer-Encoding not supported"}`; and `deck.html` is unchanged
- And the same request with `Content-Length: 42` added before `Transfer-Encoding` and the raw JSON body gets the same answer and leaves `deck.html` unchanged

### SPEC-0013/BT-011: Host with userinfo refused
- Red before: answers 200 with the document.
- When `GET /content HTTP/1.1\r\nHost: evil@L\r\n\r\n`
- Then status `400`, body `{"error": "Invalid Host header"}`; and the response bytes do not contain `ORIGINAL-SECRET`

### SPEC-0013/BT-012: Folded Host refused as folding
- Red before: answers `403 forbidden host`.
- When `GET /content HTTP/1.1\r\nHost: L\r\n evil.example\r\n\r\n`
- Then status `400`, body `{"error": "Invalid header folding"}`; and the response bytes do not contain `ORIGINAL-SECRET`

### SPEC-0013/BT-020: Header check details
- When, in turn: `GET /content` with `host: L` then `HOST: L`; `GET /content` with `Host: L`, `Host: L`, `Origin: https://evil.example`; `POST /content` with a folded `Origin` and two `Host` lines; `GET /health` with two `Host` lines; `OPTIONS /content` with two `Host` lines; `GET /content HTTP/1.1\r\n\r\n` (no `Host`); `PUT /content HTTP/1.1\r\nHost: L\r\nHost: evil.example\r\n\r\n`
- Then the answers are, in turn: `400 Duplicate Host header`; `400 Duplicate Host header` (not 403); `400 Invalid header folding`; `200` with keys exactly `status`, `version`, `file`, `port`; `405` with `Allow: GET, POST` and an empty body; `403 {"error": "forbidden host"}`; `501`
- And `deck.html` is unchanged

### SPEC-0013/BT-035: Every protected route refuses each ambiguous header
- Red before: each route reads the first value or ignores the field.
- Given `deck.html` holds a declarative diagram (one `arch-row` with two `arch-node`, no positions) in addition to the `ORIGINAL-SECRET` title, a pending request `R-0001` queued through `POST /requests` with instruction `keep`, and a review written with `mcp-htmleditor review deck.html --write rev.json` holding `[{"id":"a","slide":null,"title":"t","why":"w","change":"c"}]`
- And the routes, each with its literal body `B` and its correct length `N`: `POST /content` `{"html":"<html><body>PWNED</body></html>"}`; `POST /arch-layout` `{}`; `POST /requests` `{"instruction":"PWNED"}`; `POST /requests/delete` `{"id":"R-0001"}`; `POST /review/apply` `{"id":"a"}`; and, with no body, `GET /`, `GET /static/editor.js`, `GET /content`, `GET /content-frame`, `GET /status`, `GET /export/pptx`, `GET /export/docx`, `GET /requests`, `GET /nope`
- When, parametrized over every route and each of these six header blocks (POST routes add `Content-Type: application/json`, `Content-Length: N` and `B` unless the block replaces them; GET routes send no body): `Host: L\r\nHost: evil.example`; `Host: L\r\nOrigin: http://L\r\nOrigin: https://evil.example`; `Host: L\r\nContent-Length: N\r\nContent-Length: 0` (GET: `Content-Length: 0` twice); `Host: L\r\nContent-Type: application/json\r\nContent-Type: text/plain`; `Host: L\r\nTransfer-Encoding: chunked`; `Host: evil@L`
- Then the answers are, in that order, `400` with `{"error": "Duplicate Host header"}`, `{"error": "Duplicate Origin header"}`, `{"error": "Duplicate Content-Length header"}`, `{"error": "Duplicate Content-Type header"}`, `{"error": "Transfer-Encoding not supported"}`, `{"error": "Invalid Host header"}`
- And `deck.html` is unchanged (no `PWNED`, no `data-x`), `mcp-htmleditor requests deck.html` lists exactly `R-0001` pending with instruction `keep`, `mcp-htmleditor review deck.html` still lists suggestion `a`, the response bytes contain neither `ORIGINAL-SECRET` nor the bytes `PK`, and `tmp_path` holds no new file

### SPEC-0013/BT-026: Single headers served as today (non regression)
- When `GET /content` with `Host: L`; with `Host: localhost:P` and `Origin: http://localhost:P`; then a save with one of each header and body `{"html":"<!DOCTYPE html><html><body><p>X</p></body></html>"}`
- Then the reads answer `200` with `ORIGINAL-SECRET`, the save answers `200 {"ok": true, "mtime": <number>}` and `deck.html` contains `<p>X</p>`

### SPEC-0013/BT-027: Existing refusal messages unchanged (non regression)
- When the save route receives `Content-Length: abc`; `Content-Length: 52428801` with nothing sent; `Content-Type: text/plain` with a correct length; body `not json`; and `GET /content` with `Host: attacker.example:P`; and `Origin: https://evil.example`
- Then the answers are exactly `400 {"error":"Invalid Content-Length"}`, `413 {"error":"Request too large"}`, `415 {"error":"unsupported content type"}`, `400 {"error":"Invalid JSON body"}`, `403 {"error":"forbidden host"}`, `403 {"error":"forbidden origin"}`

### SPEC-0013/BT-031: Browser editor keeps saving (non regression)
- Driver: Playwright Chromium, as the existing SPEC-0005 non regression test (`tests/test_http_origin_e2e.py:180`)
- When edit mode is on, the first editable zone is clicked, End pressed, `AAA` typed, 1500 ms waited
- Then `deck.html` contains `AAA`

### Log line check (BR-013 partial, part of this story's own tests)
- Given `caplog` at WARNING on logger `mcp_htmleditor.http_server`, when BT-001 is sent, then exactly one new record equals `Refused POST /content: Duplicate Host header`, and no record contains `PWNED` or `Traceback`.

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `tests/test_http_origin_e2e.py`, `tests/test_save_safety_e2e.py`, any other `src` module.
- Dependencies not to add: none (stdlib `socket` in the helper).
- Patterns to avoid: reading a header with `self.headers.get` to decide a refusal of this story; logging header values of a refused request; reading the body before the gate; changing the existing `_refuse` 403 log format.
- Scope boundary: `/arch-layout` length (US-0072), unencodable text (US-0073), time bounds (US-0078, US-0079) are out. `GET /health`, `OPTIONS` and other methods must stay outside the gate.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_http_origin_e2e.py` (17 tests), `tests/test_save_safety_e2e.py`, `tests/test_requests_core.py`, `tests/test_http_health.py`, `tests/test_http_caching.py`, `tests/test_http_export.py` pass unmodified.
- [ ] Docs updated: `.agent_docs/architecture.md` request gate paragraph.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0071: Refuse ambiguous identity and framing headers`, body `Spec: SPEC-0013` and BR-001, BR-002, BR-003, BR-004, BR-005, BR-013, BR-014.
