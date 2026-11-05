# US-0074: Patch and record writers refuse unencodable text

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P2
> Depends on: US-0073
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

`patch` with a lone surrogate in the new text prints a Python traceback (command) or raises
`UnicodeEncodeError` (tool); `write_review`, `review --write`, `complete_request` and `request-skip --reason` do
the same with an unencodable text (BUG-003). This story turns each of them into the one line refusal
`Text cannot be encoded as UTF-8`, with the file, its history and the request record untouched.

## Requirements covered

- SPEC-0013/BR-011: IF the operations given to `patch` put text that cannot be encoded as UTF-8 into the document THEN THE `patch` command SHALL print `error: Text cannot be encoded as UTF-8` on standard error with exit status 1, and THE `patch` agent tool SHALL raise a tool error with message `Text cannot be encoded as UTF-8`, both leaving the file and its history unchanged.
- SPEC-0013/BR-012: IF the command `review --write`, the command `request-skip --reason`, the agent tool `write_review` or the agent tool `complete_request` receives text that cannot be encoded as UTF-8 THEN THE command SHALL print `error: Text cannot be encoded as UTF-8` with exit status 1, and THE agent tool SHALL raise a tool error with message `Text cannot be encoded as UTF-8`, both leaving the request record unchanged.
- SPEC-0013/BR-016 (partial: patch and the record writers): The editor, the `patch` command and the agent tools SHALL NOT leave a temporary file next to the user's file, a new history version or a changed request revision after a refusal of this spec.
- SPEC-0013/BR-017 (partial: patch and the record writers): The editor server, `patch` and the record writers SHALL write text holding valid surrogate pairs, U+0000 or any other encodable code point as its UTF-8 bytes, as today.

Business rules (spec): same answer with `--dry-run` (tool `dry_run: true`); standard output stays empty on the
command line. The HTTP request routes keep their existing answer `400 {"ok":false,"error":"Invalid request body"}`.
On the command line an undecodable argument byte (`$'bad \xff'`) arrives as `\udcff` and is refused the same way.

## Independent Test

`make test ARGS='-k unencodable_text'`: with `ops.json` holding the bytes
`[{"op":"set_text","id":"slide-0","selector":"h1","text":"T\ud800"}]`, `mcp-htmleditor patch deck.html --ops ops.json`
prints exactly `error: Text cannot be encoded as UTF-8` on stderr, nothing on stdout, exit 1, and `deck.html` is
byte for byte unchanged (red today: traceback).

## Design excerpt

### Decisions
- DEC-004 (SPEC-0013): "`apply_patch` checks `is_utf8_encodable(text)` on the assembled text before `encode` and before the dry run result, raising `DeckError(UNENCODABLE_TEXT)`; `deck_command` (`cli.py:34`) and the tool (`mcp_server.py` `patch`) already translate `DeckError`." The check covers every operation (`set_text`, `replace_slide`, `insert_slide`, ...) at one point; nothing is written.
- DEC-005 (SPEC-0013): "`RequestService.write_review` checks every string field of every suggestion (`id`, `slide`, `title`, `why`, `change`) after the existing shape rules, and `RequestService.complete` checks `reason`, both raising `RequestError("invalid", UNENCODABLE_TEXT)` before `store.update`. The HTTP routes keep their `_is_text` check first, so they keep `Invalid request body`." Existing shape messages keep precedence (a non list is still `Review must be a list of suggestions`). In `complete`, the reason check runs first, before the store is read.
- DEC-001 (SPEC-0013): the predicate and message come from `src/mcp_htmleditor/textcheck.py` (landed in US-0073): `is_utf8_encodable(text) -> bool`, `UNENCODABLE_TEXT = "Text cannot be encoded as UTF-8"`.

### Contracts
- `src/mcp_htmleditor/deck/patch.py:206` `data = text.encode("utf-8")` is preceded by `if not is_utf8_encodable(text): raise DeckError(UNENCODABLE_TEXT)` (before `is_changed`, the write and the dry run result).
- `RequestService.write_review(file, raw)` (`request_service.py:109`): after `_check_review(raw)`, refuse when any string field of any suggestion is not encodable.
- `RequestService.complete(file, request_id, status, reason)` (`request_service.py:91`): `reason is not None and not is_utf8_encodable(reason)` raises `RequestError("invalid", UNENCODABLE_TEXT)` first.
- Surfaces unchanged: `cli.py` `review` and `_complete_request` print `error: <RequestError.message>` and exit 1 (`cli.py:451`, `:485`, `_request_fail`); the tools raise `ToolError(exc.message)` (`mcp_server.py:464`, `:493`).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/patch.py` | modify: encodability before the encode |
| `src/mcp_htmleditor/request_service.py` | modify: `write_review`, `complete` |
| `tests/test_unencodable_text.py` | create |

### Existing patterns
- `tests/deck_support.py:244` `run_cli(*args)` (separate stdout and stderr, tracing disabled), `:252` `call_tool(name, **arguments)` (`(False, message)` on a tool error); `tests/test_deck_patch_tool.py:28` for non string arguments.
- Raw byte command line argument (`$'bad \xff'`): run `subprocess.run([sys.executable, "-m", "mcp_htmleditor", "request-skip", str(deck), "R-0002", "--reason", b"bad \xff"], env={..., "PYTHONPATH": "src", "HTMLEDITOR_STATE_DIR": ...})` with the argument as bytes (POSIX), as `tests/test_requests_core.py` UT-A02 uses `subprocess`.
- Request queueing for BT-019: a served deck (`tests/conftest.py:233` `serve_deck`) and `POST /requests`, or `build_request_service().queue(...)` directly.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Conventions: `deck.html` in `tmp_path` is a copy of the `carbon` slide bootstrap titled `ORIGINAL-SECRET`;
"unchanged" = same bytes, `mcp-htmleditor history deck.html` prints `No history for deck.html`, same request
revision; JSON files hold escapes as six ASCII characters. Agent tool tests set `HTMLEDITOR_STATE_DIR` and the log
and cache folders to `tmp_path`. Location `tests/test_unencodable_text.py`.

### SPEC-0013/BT-016: Patch command refuses a lone surrogate
- Level exploit; Driver CLI. Red before because: prints a Python traceback.
- Given `ops.json` holding the bytes `[{"op":"set_text","id":"slide-0","selector":"h1","text":"T\ud800"}]`
- When `mcp-htmleditor patch deck.html --ops ops.json`, then the same with `--dry-run`
- Then each prints exactly `error: Text cannot be encoded as UTF-8` on standard error, nothing on standard output, exit status 1, and standard error contains no `Traceback`
- And `deck.html` is unchanged, `mcp-htmleditor history deck.html` prints `No history for deck.html`, and `os.listdir` of the folder of `deck.html` is the same as before (BR-016)

### SPEC-0013/BT-017: Patch tool refuses a lone surrogate
- Level exploit; Driver the agent tool `patch` through the in process client. Red before: raises `UnicodeEncodeError`.
- When `patch(file="<deck.html>", ops=[{"op":"set_text","id":"slide-0","selector":"h1","text":"T\ud800"}])`
- Then a tool error is raised with message exactly `Text cannot be encoded as UTF-8`
- And `deck.html` read from disk is unchanged, `mcp-htmleditor history deck.html` prints `No history for deck.html`, and `os.listdir` of the folder of `deck.html` is the same as before (BR-016)

### SPEC-0013/BT-036: Slide replacement and insertion refuse a lone surrogate
- Level exploit; Driver CLI and agent tool. Red before: both raise `UnicodeEncodeError`.
- Given `A` is `<article class="slide" data-type="slide" data-id="slide-9" data-title="T\ud800"><h1>X\ud800</h1></article>` written in the JSON with the escapes as six ASCII characters each
- When, parametrized over `[{"op":"replace_slide","id":"slide-0","html":"A"}]` and `[{"op":"insert_slide","after":"slide-0","html":"A"}]`: `mcp-htmleditor patch deck.html --ops ops.json`, then `patch(file="<deck.html>", ops=<the same list decoded>)`
- Then the command prints exactly `error: Text cannot be encoded as UTF-8`, nothing on standard output, exit status 1, no `Traceback`; the tool raises a tool error `Text cannot be encoded as UTF-8`
- And `deck.html` is unchanged, `mcp-htmleditor history deck.html` prints `No history for deck.html`, and `os.listdir` of the folder of `deck.html` is the same as before (BR-016)

### SPEC-0013/BT-018: Review writes refuse a lone surrogate
- Level exploit; Driver agent tool in process client; CLI. Red before: both raise `UnicodeEncodeError`.
- Given `rev.json` holding `[{"id":"a","slide":null,"title":"t\ud800","why":"w","change":"c"}]`
- When `write_review(file="<deck.html>", suggestions=<the same list decoded>)`, then `mcp-htmleditor review deck.html --write rev.json`
- Then the tool raises a tool error with message `Text cannot be encoded as UTF-8`; the command prints `error: Text cannot be encoded as UTF-8`, exit status 1, no `Traceback`
- And `mcp-htmleditor review deck.html` then prints `No review for deck.html`, and the listings of the folder of `deck.html` and of the state folder (recursive) are the same as before (no temporary record file, BR-016)

### SPEC-0013/BT-019: Request completion refuses unencodable reason
- Level exploit; Driver agent tool in process client; CLI subprocess with a raw byte argument. Red before: both raise `UnicodeEncodeError`.
- Given two requests queued through `POST /requests` with instructions `one` and `two` (ids `R-0001`, `R-0002`)
- When `complete_request(file="<deck.html>", id="R-0001", status="skipped", reason="because \ud800")`, then `mcp-htmleditor request-skip deck.html R-0002 --reason` followed by the byte argument `bad \xff`
- Then the tool raises a tool error `Text cannot be encoded as UTF-8`; the command prints `error: Text cannot be encoded as UTF-8`, exit status 1, no `Traceback`
- And `GET /requests` lists both requests with `status` `"pending"` and the same revision as before, and the recursive listing of the state folder is the same as before the two calls (BR-016)

### SPEC-0013/BT-030: Valid Unicode written (non regression)
- When a save with body `{"html":"<html>\ud83d\ude00\u0000</html>"}` is sent; and `patch` sets the title to `T\ud83d\ude00`
- Then the save answers `200` and the file bytes contain `F0 9F 98 80`; the patch prints its usual JSON result with `"changed":true`

### SPEC-0013/BT-032: HTTP request routes keep their message (non regression)
- When `POST /requests` with `{"instruction":"\ud800"}`, `POST /requests/delete` with `{"id":"\ud800"}`, `POST /review/apply` with `{"id":"\ud800"}`
- Then each answers `400 {"ok": false, "error": "Invalid request body"}` and the request list is unchanged

## Constraints

- Files not to touch: `src/mcp_htmleditor/cli.py`, `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/http_server.py`, `src/mcp_htmleditor/request_store.py`, `src/mcp_htmleditor/textcheck.py`.
- Dependencies not to add: none.
- Patterns to avoid: catching `UnicodeEncodeError` around the write; a new exception type; checking operation inputs one by one in `patch` (one check on the assembled text).
- Scope boundary: path arguments (US-0076, US-0077) and tracing (US-0075) are out. The HTTP routes are not changed.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_deck_patch*.py`, `tests/test_deck_patch_tool.py`, `tests/test_review_write.py`, `tests/test_requests_cli.py`, `tests/test_requests_tools.py`, `tests/test_requests_core.py` pass unmodified.
- [ ] Docs updated: none in this story.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0074: Patch and record writers refuse unencodable text`, body `Spec: SPEC-0013` and BR-011, BR-012, BR-016, BR-017.
