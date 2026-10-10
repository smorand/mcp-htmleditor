# US-0003: JSON only saves, refused preflight, editor non regression

> Spec: SPEC-0005 (sdlc/specs/SPEC-0005-cross-origin-requests/)
> Nature: BUG
> Priority: P1
> Depends on: US-0002
> min_tier: 2
> Files touched: 3
> Closes spec: yes

## Objective

Closes the last request shapes a browser sends without asking first: a non JSON save and a CORS
preflight. Proves the bundled editor still saves, polls and exports, and closes SPEC-0005.

## Requirements covered

- SPEC-0005/BR-004: IF `POST /content` carries a `Content-Type` other than `application/json` (parameters such as `; charset=utf-8` allowed) THEN THE preview server SHALL answer `415` with body `{"error": "unsupported content type"}` and SHALL NOT write the document.
- SPEC-0005/BR-005: IF an `OPTIONS` request reaches the preview server THEN THE preview server SHALL answer `405` with an empty body and an `Allow: GET, POST` header.
- SPEC-0005/BR-007: The preview server SHALL serve, save, poll, export and lay out for the editor page it serves itself, opened at `http://localhost:<port>/` or `http://127.0.0.1:<port>/`.

## Independent Test

`make test ARGS='tests/test_http_origin_e2e.py'`: a same origin `text/plain` save answers
`415 {"error": "unsupported content type"}` and `doc.html` on disk is unchanged; the browser editor
typing `AAA` writes it to disk.

## Design excerpt

### Decisions
- DEC-005: media type = `Content-Type` split at `;`, stripped, lower cased, must equal `application/json`; checked in `_receive_content` before reading JSON; the raw body branch (`http_server.py:286`) is removed.
- DEC-008: `do_OPTIONS` answers `405`, header `Allow: GET, POST`, `Content-Length: 0`.
- DEC-006: the 415 refusal logs `logger.warning("Refused %s %s: %s %r", ...)` with the refused `Content-Type`, never the body.

### Contracts
- `415 {"error": "unsupported content type"}`; `405`, empty body, `Allow: GET, POST`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_server.py` | modify `do_OPTIONS` (`:91`) and `_receive_content` (`:267`, content type at `:277`) |
| `tests/test_http_origin_e2e.py` | extend (file created by US-0002) |
| `README.md` | add a "Security model" paragraph: loopback host names and same origin only; any port; container network exposure not authenticated (BL-0019) |

### Existing patterns
- Harness and helpers in `tests/test_http_origin_e2e.py` (US-0002).
- Browser editing flow: `tests/test_autosave_focus_e2e.py` (`_open_in_edit_mode`, `_click_end`, `SAVED_DOT_COLOR`).

## Acceptance tests

> 100% must pass, run through `make check`. Never run test files ad hoc.

Same preconditions as US-0002.

### SPEC-0005/BT-014: Non JSON save refused even same origin
- When `POST /content`, `Host: 127.0.0.1:P`, no `Origin`, `Content-Type: text/plain`, body `<p>X</p>`
- Then `415`, body `{"error": "unsupported content type"}`; And `doc.html` unchanged
- And with `Content-Type: application/json; charset=utf-8`, body `{"html": "<!DOCTYPE html><html><body><p>X</p></body></html>"}`: `200`, `doc.html` contains `<p>X</p>`
- Red before the fix because: the `text/plain` save answers `200` and writes `<p>X</p>`.

### SPEC-0005/BT-015: Preflight refused
- When `OPTIONS /content`, `Origin: https://evil.example`, `Access-Control-Request-Method: POST`
- Then `405`, header `Allow: GET, POST`, empty body, no `Access-Control-Allow-Origin`

### SPEC-0005/BT-020: Browser editor still saves, polls, exports
- Level functional e2e; Driver Playwright on `http://127.0.0.1:P/`
- Given `doc.html` is a copy of the `carbon` slide bootstrap with `ORIGINAL-SECRET` in its title
- When edit mode is on, the first editable zone is clicked, End pressed, `AAA` typed, 1500 ms waited, then the editor page runs `fetch('/export/pptx').then(r => r.status)`
- Then `doc.html` contains `AAA`, `#toolbar-status` color is `rgb(66, 190, 101)`, and the fetch result is `200`

### SPEC-0005/BT-021: Existing suites unchanged
- When `make check` runs
- Then every test of `tests/test_autosave_focus_e2e.py`, `tests/test_undo_redo_e2e.py`, `tests/test_website_template_e2e.py`, `tests/test_tab_title_e2e.py`, `tests/test_fullscreen_e2e.py`, `tests/test_http_health.py`, `tests/test_http_caching.py`, `tests/test_http_export.py` passes unmodified

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, existing test files other than `tests/test_http_origin_e2e.py`.
- Dependencies not to add: none allowed.
- Patterns to avoid: accepting any non JSON media type; logging bodies.
- Scope boundary: authentication for the container port is BL-0019.

## Definition of done

- [ ] RED evidence recorded for BT-014 and BT-015 before the production change.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: BT-021 list, plus every US-0002 test.
- [ ] Docs updated: `README.md` Security model paragraph.
- [ ] Self review: full.
- [ ] Closes spec: BT-001 to BT-007, BT-010 to BT-017, BT-020 to BT-022 green; BR-001 to BR-008 each cited by US-0002 or US-0003, both done or landed.
- [ ] One commit `US-0003: JSON only saves, refused preflight, editor non regression`, body `Spec: SPEC-0005` and `BR-004, BR-005, BR-007`.
