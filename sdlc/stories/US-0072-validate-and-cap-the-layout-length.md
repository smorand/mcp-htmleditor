# US-0072: Validate and cap the layout route length

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P1
> Depends on: US-0071
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

`POST /arch-layout` converts its `Content-Length` with `int()` and reads that many bytes: `abc`, `-5` or a
20 digit value close the connection with a traceback, and a declared 2 000 000 bytes that never come hold the
handler forever (BUG-002). This story gives the layout route the same length rules as the request routes, with
the 1 MiB cap, through one shared body reader, so every such request gets a prompt `400` or `413`.

## Requirements covered

- SPEC-0013/BR-006: IF `POST /arch-layout` carries a `Content-Length` that is not a non empty string of ASCII digits THEN THE editor server SHALL answer `400` with body `{"error":"Invalid Content-Length"}` and no side effect.
- SPEC-0013/BR-007: IF `POST /arch-layout` declares a `Content-Length` greater than 1 048 576 THEN THE editor server SHALL answer `413` with body `{"error":"Request too large"}` without reading the body and with no side effect.
- SPEC-0013/BR-009 (partial: the layout route length cases): The editor server SHALL NOT close a connection without an HTTP answer, or write a traceback to its log, because of the content of a request's line, headers or body.
- SPEC-0013/BR-013 (partial: the BR-006 and BR-007 refusals): IF a request is refused by BR-001 to BR-004, BR-006 to BR-008 or BR-010 THEN THE editor server SHALL log exactly one warning line starting `Refused <METHOD> <path>: ` followed by the error text of the answer, and SHALL NOT log the request body or a traceback.

Business rules (spec): an absent `Content-Length` is length 0 and is served, as today (the bundled editor sends
`POST /arch-layout` with no body and no `Content-Type`). The route still ignores its body and still does not
check `Content-Type`. A declared length up to 1 048 576 is read and discarded, then the layout runs. Leading
zeros are allowed (`007` with 7 bytes is served).

## Independent Test

`make test ARGS='-k layout_length'`: `POST /arch-layout HTTP/1.1\r\nHost: L\r\nContent-Length: abc\r\n\r\n` answers
within 2 seconds `400 {"error": "Invalid Content-Length"}`, `deck.html` is unchanged and the captured log has no
`Traceback` (red today: no answer, traceback).

## Design excerpt

### Decisions
- DEC-012 (SPEC-0013): "A handler method `_read_declared_body(limit)` reads `parse_content_length(self.headers.get("Content-Length"))`, raises `SaveRefusal(413, {"error": "Request too large"})` above `limit` before reading, then reads exactly that many bytes. `_read_request_body` uses it with `BODY_MAX_BYTES` (keeping its rule that a wrong content type outranks a bad length); `_run_arch_layout` uses it with `LAYOUT_BODY_MAX_BYTES = BODY_MAX_BYTES`, after its existing `No file loaded` check, answering a `SaveRefusal` through `_refuse_request`. The save route keeps its own 50 MiB call."
- DEC-011 (SPEC-0013, landed in US-0071): the header gate guarantees a single `Content-Length` line before any route, so `self.headers.get` is safe here.

### Contracts
```python
# src/mcp_htmleditor/http_server.py
LAYOUT_BODY_MAX_BYTES = BODY_MAX_BYTES   # 1_048_576, module constant next to MAX_SAVE_BYTES

class _EditorHandler:
    def _read_declared_body(self, limit: int) -> bytes:
        """Raise SaveRefusal 400 (not ASCII digits) or 413 (above limit, before reading); else read the body."""
```
`_run_arch_layout` order: `No file loaded` (404, unchanged) then `_read_declared_body(LAYOUT_BODY_MAX_BYTES)`; a
`SaveRefusal` answers `self._refuse_request(refusal.status, refusal.payload["error"])` (log
`Refused POST /arch-layout: <error>`), then the layout runs as today. `parse_content_length`
(`http_server.py:596`) already returns 0 for an absent header, refuses non digit text with 400 and anything above
10 significant digits with 413.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_server.py` | modify: `LAYOUT_BODY_MAX_BYTES`, `_read_declared_body`, `_read_request_body` uses it, `_run_arch_layout` uses it |
| `tests/test_http_layout_length_e2e.py` | create |
| `tests/test_save_safety_e2e.py` | modify the docstring of `test_length_checks_apply_to_the_save_endpoint_only` only: the layout route now validates its length; its assertion (`POST /arch-layout` with `{}` answers 200) is kept |

### Existing patterns
- `src/mcp_htmleditor/http_server.py:415` `_read_request_body`, `:481` the layout route length, `:596` `parse_content_length`, `:565` `SaveRefusal`; `_refuse_request` from US-0071.
- Raw socket helper `tests/http_support.py` (`exchange`, `json_body`, US-0071); fixture `tests/conftest.py:233` `serve_deck`.
- Playwright pattern: `tests/test_http_origin_e2e.py:180`; the editor calls `fetch('/arch-layout', {method: 'POST'})` (`src/mcp_htmleditor/static/editor-menus.js:39`).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Test conventions (Spec section 4): real server on `127.0.0.1:P` serving `deck.html` (carbon bootstrap copy titled
`ORIGINAL-SECRET`); raw TCP socket; `L` is `127.0.0.1:P`; JSON compared parsed. The diagram of BT-013:
`deck.html` holds one `data-type="arch-diagram"` with one `arch-row` holding two `arch-node` and no positions.
Location `tests/test_http_layout_length_e2e.py`.

### SPEC-0013/BT-002: An invalid layout length gets an answer
- Reproduces BUG-002 (also validates BR-009). Red before because: the layout route converts the header with no validation and the error closes the connection.
- When the client sends `POST /arch-layout HTTP/1.1\r\nHost: L\r\nContent-Length: abc\r\n\r\n`
- Then within 2 seconds the status is `400` and the body is `{"error": "Invalid Content-Length"}`
- And `deck.html` is unchanged, and the captured server log holds no line containing `Traceback`

### SPEC-0013/BT-013: Negative and huge layout lengths answered
- Parametrized over `-5` and `99999999999999999999`. Red before: each closes the connection with a traceback.
- Given `deck.html` holds the declarative diagram
- When `POST /arch-layout HTTP/1.1\r\nHost: L\r\nContent-Length: <value>\r\n\r\n`
- Then `-5` answers `400 {"error": "Invalid Content-Length"}` and `99999999999999999999` answers `413 {"error": "Request too large"}`, each within 2 seconds
- And `deck.html` is unchanged (no `data-x` attribute appeared) and the log holds no `Traceback`

### SPEC-0013/BT-014: Declared large layout body refused without waiting
- Red before: the handler waits for 2 000 000 bytes that never come.
- When `POST /arch-layout HTTP/1.1\r\nHost: L\r\nContent-Length: 2000000\r\n\r\n` and nothing else
- Then within 2 seconds the status is `413`, body `{"error": "Request too large"}`; and `deck.html` is unchanged

### SPEC-0013/BT-021: Layout length boundaries
- Given the diagram of BT-013
- When `POST /arch-layout` with no `Content-Length`; with `Content-Length: 0`; with `007` and 7 bytes `{"a":1}`; with `1048576` and that many `x`; with `1048577` and nothing sent
- Then the first four answer `200` with keys `ok` (true), `diagrams_updated`, `warnings`; the last answers `413 {"error": "Request too large"}` within 2 seconds

### SPEC-0013/BT-029: Bundled editor layout call still works (non regression)
- Driver: Playwright Chromium on `http://127.0.0.1:P/`, diagram of BT-013
- When the editor page runs `fetch('/arch-layout', {method: 'POST'}).then(r => r.status)`
- Then the result is `200` and `deck.html` now holds `data-x` attributes on both nodes

### Log line check (BR-013 partial)
- With `caplog` at WARNING on `mcp_htmleditor.http_server`, BT-002 adds exactly one record equal to `Refused POST /arch-layout: Invalid Content-Length`.

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/arch_layout.py`, the assertions of existing tests.
- Dependencies not to add: none.
- Patterns to avoid: a second length parser; `int(self.headers.get(...))`; checking `Content-Type` on the layout route (the editor sends none); changing the request routes' messages or their content type precedence (`_read_request_body`: a wrong content type outranks a bad length).
- Scope boundary: the 50 MiB save route reader is unchanged; time bounds are US-0078.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_save_safety_e2e.py` (assertions unchanged), `tests/test_requests_core.py` UT-A06, `tests/test_arch_layout.py`, US-0071 tests pass.
- [ ] Docs updated: none in this story (US-0079 documents the feature).
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0072: Validate and cap the layout route length`, body `Spec: SPEC-0013` and BR-006, BR-007, BR-009, BR-013.
