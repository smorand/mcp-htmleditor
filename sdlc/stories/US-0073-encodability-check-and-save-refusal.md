# US-0073: Shared encodability check and the save refusal

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P1
> Depends on: US-0072
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

JSON allows a lone surrogate escape (`"\ud800"`): `POST /content` with `{"html":"<html>\ud800"}` closes the
connection with no answer and logs a `UnicodeEncodeError` traceback (BUG-003). This story adds the one shared
"cannot be encoded" predicate and the three user messages every later story reuses, refuses such a save with
`400 {"error":"Text cannot be encoded as UTF-8"}`, and makes the atomic writer refuse unencodable text cleanly
instead of raising.

## Requirements covered

- SPEC-0013/BR-010: IF `POST /content` carries an `html` string that cannot be encoded as UTF-8 THEN THE editor server SHALL answer `400` with body `{"error":"Text cannot be encoded as UTF-8"}`, leave the file unchanged, and add no history version.
- SPEC-0013/BR-015: The editor server SHALL answer `POST /content` whose body is valid JSON but not an object with `400 {"error":"Invalid JSON body"}` and leave the file unchanged.
- SPEC-0013/BR-009 (partial: the save of unencodable text): The editor server SHALL NOT close a connection without an HTTP answer, or write a traceback to its log, because of the content of a request's line, headers or body.
- SPEC-0013/BR-013 (partial: the BR-010 refusal): IF a request is refused by BR-001 to BR-004, BR-006 to BR-008 or BR-010 THEN THE editor server SHALL log exactly one warning line starting `Refused <METHOD> <path>: ` followed by the error text of the answer, and SHALL NOT log the request body or a traceback.
- SPEC-0013/BR-016 (partial: the editor save and the atomic writer): The editor, the `patch` command and the agent tools SHALL NOT leave a temporary file next to the user's file, a new history version or a changed request revision after a refusal of this spec.
- SPEC-0013/BR-017 (partial: the editor save): The editor server, `patch` and the record writers SHALL write text holding valid surrogate pairs, U+0000 or any other encodable code point as its UTF-8 bytes, as today.

Business rules (spec): "cannot be encoded" means the string holds a code point between U+D800 and U+DFFF not part
of a valid pair (after JSON decoding a valid pair is one code point, so any remaining U+D800 to U+DFFF is
unencodable). A valid pair and U+0000 are accepted. Position in the SPEC-0009/FR-NEW-007 order: right after
`Invalid JSON body`, before the template check (`403 Refusing to modify a template`).

## Independent Test

`make test ARGS='-k unencodable_save or textcheck'`: `POST /content` with `Host: L`, `Content-Type: application/json`,
a correct `Content-Length` and the ASCII body bytes `{"html":"<html>\ud800"}` answers
`400 {"error": "Text cannot be encoded as UTF-8"}`, `deck.html` is unchanged and the log has no `Traceback`
(red today: `RemoteDisconnected`).

## Design excerpt

### Decisions
- DEC-001 (SPEC-0013): "One new module `src/mcp_htmleditor/textcheck.py` holds `is_utf8_encodable`, `replace_unencodable` and the three messages; it imports nothing from the package. Each surface raises its own native error with these messages." A module with no internal import can be used by `deck/__init__.py`, which `fileio.py` imports (`fileio.py:17`), so the helper cannot live in `fileio.py` without an import cycle. `_is_text` at `http_server.py:585` already implements the predicate inline; it becomes a call to `is_utf8_encodable`.
- DEC-002 (SPEC-0013): "The save refusal is raised in `parse_save_body` right after the `Invalid JSON body` checks as `SaveRefusal(400, {"error": UNENCODABLE_TEXT})`; the existing warning of `_receive_content` (`http_server.py:448`) logs it. `_is_text` delegates to `is_utf8_encodable`."
- DEC-003 (SPEC-0013): "`atomic_write` encodes a `str` inside its error handling and turns `UnicodeEncodeError` into `WriteError(path, UNENCODABLE_TEXT)` before any temporary file exists."

### Contracts
```python
# src/mcp_htmleditor/textcheck.py (new, no import from the package)
UNENCODABLE_TEXT = "Text cannot be encoded as UTF-8"
UNENCODABLE_FILE_NAME = "File name cannot be encoded"
UNENCODABLE_BIND_ADDRESS = "Bind address cannot be encoded"
REPLACEMENT_CHARACTER = "\ufffd"

def is_utf8_encodable(text: str) -> bool:
    """True when text.encode("utf-8") (strict) succeeds; False for U+D800..U+DFFF, U+DC80..U+DCFF included."""

def replace_unencodable(text: str) -> str:
    """Each code point U+D800..U+DFFF replaced by U+FFFD; encodable text returned unchanged."""
```
`parse_save_body` (`http_server.py:614`): after the existing `Invalid JSON body` checks, `if not is_utf8_encodable(data["html"]): raise SaveRefusal(400, {"error": UNENCODABLE_TEXT})`.
`atomic_write` (`fileio.py:48`): when `data` is a `str` that cannot be encoded, raise `WriteError(path, UNENCODABLE_TEXT)` (message `Cannot write <path>: Text cannot be encoded as UTF-8`), before `mkstemp`, inside no span change.
Log line (existing, `http_server.py:448`): `Refused POST /content: Text cannot be encoded as UTF-8`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/textcheck.py` | create |
| `src/mcp_htmleditor/http_server.py` | modify: `parse_save_body`, `_is_text` delegates |
| `src/mcp_htmleditor/fileio.py` | modify: `atomic_write` encode |
| `tests/test_textcheck.py` | create: unit tests of the two functions and of the `atomic_write` refusal |
| `tests/test_unencodable_save_e2e.py` | create |

### Existing patterns
- `src/mcp_htmleditor/http_server.py:436` `_receive_content` (catches `SaveRefusal` and logs it), `:614` `parse_save_body`, `:640` `refuse_template`.
- `src/mcp_htmleditor/fileio.py:48` `atomic_write`, `:29` `WriteError`; history check: `mcp-htmleditor history deck.html` prints `No history for deck.html`.
- Raw socket helper `tests/http_support.py` (US-0071); fixture `serve_deck` (`tests/conftest.py:233`); `tests/deck_support.py:244` `run_cli`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Test conventions (Spec section 4): real server on `127.0.0.1:P` serving `deck.html` (carbon bootstrap copy
titled `ORIGINAL-SECRET`); raw TCP socket with exact bytes; `L` is `127.0.0.1:P`; "unchanged" = same bytes, no
history, same request revision; JSON compared parsed; log lines exact. Bodies hold the escape as six ASCII
characters (backslash, `u`, `d`, `8`, `0`, `0`). Location `tests/test_unencodable_save_e2e.py`.

### SPEC-0013/BT-004: A save of a lone surrogate gets an answer
- Reproduces BUG-003 (also validates BR-009, BR-016: the folder of `deck.html` holds only `deck.html` afterwards). Red before because: the encode error escapes the save route.
- When the client sends `POST /content` with `Host: L`, `Content-Type: application/json`, a correct `Content-Length` and the body bytes `{"html":"<html>\ud800"}`
- Then the status is `400` and the body is `{"error": "Text cannot be encoded as UTF-8"}`
- And `deck.html` is unchanged and the captured log holds no `Traceback`

### SPEC-0013/BT-024: Unencodable save variants and order
- When saves are sent with bodies `{"html":"<html>\udc00"}` and `{"html":"<html>\ud83dX</html>"}`, then `{"html":"<html>\ud800"}` while the served file lies under a folder `templates/bootstrap/`
- Then each answers `400 {"error": "Text cannot be encoded as UTF-8"}` (the last not 403) and the file is unchanged

### SPEC-0013/BT-025: Refusal log lines
- Given log capture at WARNING on the editor server logger (`mcp_htmleditor.http_server`)
- When the requests of BT-001 (`POST /content` with `Host: L` then `Host: evil.example`, body `{"html":"<html><body>PWNED</body></html>"}`), BT-002 (`POST /arch-layout` with `Content-Length: abc`) and BT-004 are sent
- Then exactly three warning records were added, equal to `Refused POST /content: Duplicate Host header`, `Refused POST /arch-layout: Invalid Content-Length` and `Refused POST /content: Text cannot be encoded as UTF-8`, and no record contains `PWNED`, `\ud800` or `Traceback`

### SPEC-0013/BT-028: Non object save body (former BL-0015, non regression)
- When saves are sent with bodies `[]`, `"text"` and `{"html": 5}`
- Then each answers `400 {"error": "Invalid JSON body"}` and `deck.html` is unchanged

### Unit tests of this story (Location `tests/test_textcheck.py`, support BR-010, BR-017)
- `is_utf8_encodable` is True for `""`, `"abc"`, `"\x00"`, `"😀"`, `"été"`, and False for `"\ud800"`, `"x\udc00"`, `"a\udcff"`, `"\ud83dX"`.
- `replace_unencodable("a\ud800b\udcff")` equals `"a\ufffdb\ufffd"`; `replace_unencodable("été😀")` equals `"été😀"`.
- `atomic_write(tmp_path / "f.html", "x\ud800")` raises `WriteError` whose `reason` is `Text cannot be encoded as UTF-8`; `tmp_path` holds no file afterwards; `atomic_write(path, "<p>😀\x00</p>")` writes the bytes `<p>\xf0\x9f\x98\x80\x00</p>`.

## Constraints

- Files not to touch: `src/mcp_htmleditor/request_service.py`, `src/mcp_htmleditor/request_store.py`, `src/mcp_htmleditor/deck/*`, `src/mcp_htmleditor/tracing.py` (later stories).
- Dependencies not to add: none.
- Patterns to avoid: `textcheck.py` importing anything from `mcp_htmleditor` (it must stay importable by `deck/__init__.py`); catching `UnicodeEncodeError` in the save route instead of checking first; changing the message of the request routes (`Invalid request body` stays, BR-012).
- Scope boundary: patch, record, path, tracing and bind address refusals are US-0074 to US-0077.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_save_safety_e2e.py`, `tests/test_requests_core.py::test_ut_a06_text_the_record_cannot_hold_is_an_invalid_body`, US-0071 and US-0072 tests pass unmodified.
- [ ] Docs updated: none in this story.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0073: Shared encodability check and the save refusal`, body `Spec: SPEC-0013` and BR-009, BR-010, BR-013, BR-015, BR-016, BR-017.
