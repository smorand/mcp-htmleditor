# US-0048: Atomic, guarded, conflict aware browser save (server side)

> Spec: SPEC-0009 (sdlc/specs/SPEC-0009-reliable-saves/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0047, US-0038
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Make `POST /content` write through the shared `atomic_write`, refuse templates, bad lengths and oversize bodies,
and detect conflicts with `base_mtime`. The browser still sends no `base_mtime` after this story (not checked).
History snapshots come in US-0050.

## Requirements covered

- SPEC-0009/FR-NEW-001: WHEN the editor server writes a file THE Editor SHALL leave on disk either the complete old content or the complete new content, and no other file next to it.
- SPEC-0009/FR-NEW-002: WHEN the editor sends a save that carries `base_mtime` and the file's modification time differs from it THE Editor SHALL refuse the save and leave the file unchanged.
- SPEC-0009/FR-NEW-007 (partial: server side refusals 400, 413, 403, 500 and their order; the editor display `Save failed: ...` is US-0049): IF a save targets a template, has an invalid length, or is too large THEN THE Editor SHALL refuse it with a precise status and leave the file unchanged.

Business rules FR-NEW-001: the permission bits of the replaced file are preserved, and a read only file in a writable folder is replaced normally. This holds for browser saves, `patch` (SPEC-0007) and `restore`. On a write failure the response is status 500 with `{"error":"<operating system message>"}`.

Business rules FR-NEW-002: `base_mtime` is the `mtime` of the version of the file the page last loaded, or last wrote itself. The refusal is status 409 with `{"ok":false,"error":"File changed on disk","mtime":<current mtime>}`. A save with `"force": true` skips the check. A save without `base_mtime` is not checked. A successful save answers `{"ok":true,"mtime":<new mtime>}`.

Business rules FR-NEW-007: a path is a template if, with `\` read as `/`, it contains `/templates/bootstrap/` or `/templates/reference/`: status 403 `{"ok":false,"error":"Refusing to modify a template: <file>"}` where `<file>` is the absolute path as returned by the status `filename`. A valid `Content-Length` is a non empty string of ASCII digits only; anything else: status 400 `{"error":"Invalid Content-Length"}`. A body larger than 52 428 800 bytes: status 413 `{"error":"Request too large"}`, the body not read. A save with no `Content-Length` header is treated as length 0. These length and size checks apply to the save endpoint only. A `base_mtime` that is not a JSON number is treated as absent. Checks run in this order and the first failure answers: host and origin (SPEC-0005, unchanged); invalid `Content-Length` (400); too large (413); content type other than `application/json` (415, SPEC-0005 unchanged); invalid JSON (400 `{"error":"Invalid JSON body"}`); template (403); conflict (409); write.

## Independent Test

`make check`: `tests/test_save_safety_e2e.py` passes. By hand: `curl` a save with `Content-Length: abc` answers
`400 {"error":"Invalid Content-Length"}` and the deck is unchanged.

## Design excerpt

### Decisions

- DEC-003 (SPEC-0009): Order inside `atomic_write`: read old bytes, create the temp file, write and fsync, (stage the snapshot, added in US-0050), replace, then (prune); on any failure remove the temp file. A failed folder fails at temp creation; a failed replace leaves the folder clean.
- DEC-004 (SPEC-0009): The only failure seam is the module function `fileio.replace_file(source, destination)` wrapping `os.replace`, patched with `monkeypatch`. No settings flag, no environment variable.
- DEC-010 (SPEC-0009): The save pipeline is a sequence of pure checks raising `SaveRefusal(status, payload)` in the spec order, called from `_receive_content`; the 404 "No file loaded" stays first (not in the spec order). `_EditorHandler` is `# pragma: no cover`, so helpers carry the tests.
- DEC-011 (SPEC-0009): A valid length is `value.isascii() and value.isdigit()`; a digit string longer than 10 significant digits is already too large and is not passed to `int()`.
- DEC-012 (SPEC-0009): Conflict compares `base_mtime` with `target.stat().st_mtime` by float equality; the answer's `mtime` is a `stat` after the replace. A missing file reads as `0.0` like `get_mtime`.
- DEC-018 (SPEC-0009): `layout_file` writes through `atomic_write` with no reason (no snapshot); `shutil.copyfile` in `new` is untouched.
- DEC-020 (SPEC-0009): Browser saves are serialized in the process by `EditorState.save_lock` (created in US-0047); cross process writers are not locked.
- DEC-021 (SPEC-0009): Error text for the 500 answers is `exc.strerror or str(exc)`.
- DEC-022 (SPEC-0009): a state directory failure surfaces as a 500 at the first save (once history exists, US-0050).
- DEC-024 (SPEC-0009): A body that is not a JSON object, or whose `html` is not a string, is answered 400 `Invalid JSON body`.

### Data model

None new. `atomic_write` returns `True` when the file was replaced, `False` when the new bytes equal the current bytes (nothing touched: no temp file, mtime unchanged).

### Contracts

`POST /content`, `Content-Type: application/json`, body `{"html": "<string>", "base_mtime": <number, optional>, "force": <true, optional>}`. Only `force` equal to `true` counts as force.

| Case | Status | Body |
|---|---|---|
| invalid `Content-Length` (empty, non digits, `-5`, `abc`) | 400 | `{"error":"Invalid Content-Length"}` |
| declared length above 52 428 800, body not read | 413 | `{"error":"Request too large"}` |
| content type not JSON | 415 | `{"error":"unsupported content type"}` (unchanged) |
| body not a JSON object, or `html` not a string | 400 | `{"error":"Invalid JSON body"}` |
| template path | 403 | `{"ok":false,"error":"Refusing to modify a template: <absolute path>"}` |
| `base_mtime` stale, no `force` | 409 | `{"ok":false,"error":"File changed on disk","mtime":<current>}` |
| saved, or identical bytes | 200 | `{"ok":true,"mtime":<mtime after>}` (unchanged mtime when identical) |
| write or state failure | 500 | `{"error":"<strerror>"}` |

```python
# fileio.py (file created by SPEC-0007 with atomic_write(path: str | Path, data: bytes) -> None; this story widens it,
# every SPEC-0007 call stays valid; str data is encoded UTF-8; reason and history keywords arrive in US-0050)
def atomic_write(path: str | Path, data: bytes | str) -> bool
def replace_file(source: str, destination: str) -> None     # test seam, wraps os.replace
def is_template_path(path: str) -> bool                      # "\\" read as "/", contains /templates/bootstrap/ or /templates/reference/
# http_server.py
class SaveRefusal(Exception): status: int; payload: dict[str, Any]
def parse_content_length(raw: str | None) -> int             # None -> 0; raises SaveRefusal 400 or 413
```

Request flow in `_receive_content`: gate (SPEC-0005) then "No file loaded" 404; `parse_content_length`; read body; content type 415; JSON object with string `html`; `is_template_path(state.current_file)`; under `state.save_lock`: conflict check, clean the HTML, `atomic_write(target, html)`, answer `{"ok":true,"mtime":<stat after>}`; `OSError` anywhere answers 500. `atomic_write` keeps the mode of the replaced file (else `0o666 & ~umask`), also for a read only file in a writable folder. `layout_file` write (`arch_layout.py:1202`) becomes `atomic_write`.

Test support added to `tests/conftest.py`: `HAS_CHROMIUM`, `needs_chromium` (moved from `tests/test_autosave_focus_e2e.py:44-51`), `ServedDeck` and fixture `served_deck`, `FakeClock` (if absent after US-0047). Unit tests to add: `parse_content_length` table (None, "", "abc", "-5", "+5", " 5", non ASCII digits, 52428800, 52428801, very long digit string), `is_template_path`, `atomic_write` (mode preserved, read only target replaced, temp removed on failure, equal bytes returns False).

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/fileio.py` | edit: widen `atomic_write`, `replace_file`, `is_template_path` |
| `src/mcp_htmleditor/http_server.py` | edit `_receive_content`, helpers, `SaveRefusal` |
| `src/mcp_htmleditor/arch_layout.py` | edit `layout_file` write to `atomic_write` |
| `tests/conftest.py` | edit |
| `tests/test_save_safety_e2e.py` | create |

### Existing patterns

- Real server HTTP tests: `tests/test_http_origin_e2e.py` (`start_http_server`, raw `http.client` requests), the pattern of `tests/test_http_origin_e2e.py:93`.
- Skip pattern for Chromium: `tests/test_autosave_focus_e2e.py:44-51`.
- Current direct write to replace: `src/mcp_htmleditor/http_server.py:330-337`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures: DECK is an Euro-Information presentation `deck.html` of 8 slides, served by the editor. `mtime` is the value returned by the status for DECK. "Saved copy" means the exact bytes before the step. Tests of read only folders skip when `os.geteuid() == 0` and restore permissions in `finally`.

### SPEC-0009/E2E-001: A normal save
- Level HTTP; Driver real server, `http.client`; Location `tests/test_save_safety_e2e.py`
- Given DECK served, `mtime` read as M1
- When the browser sends a save with a changed title and `base_mtime` M1
- Then the answer is status 200 `{"ok":true,"mtime":M2}` with M2 greater than M1, and the file holds the new title
- And no other file exists in the folder of DECK

### SPEC-0009/E2E-002: Save after reload
- Level HTTP; Driver save with the reloaded mtime; Location `tests/test_save_safety_e2e.py`
- Given DECK served; the agent changes the file (mtime M2); the page reloads and reads M2
- When the browser saves with `base_mtime` M2
- Then the answer is `{"ok":true,"mtime":M3}`

### SPEC-0009/E2E-007: Conflict refused
- Level HTTP; Driver agent write between load and save; Location `tests/test_save_safety_e2e.py`
- Given DECK served, `mtime` M1; the agent then writes a new version (mtime M2); saved copy of that file kept
- When the browser sends a save with `base_mtime` M1
- Then the answer is status 409 `{"ok":false,"error":"File changed on disk","mtime":M2}` and the file equals the saved copy

### SPEC-0009/E2E-010: Template refused
- Level HTTP; Driver template copy under `templates/bootstrap/`; Location `tests/test_save_safety_e2e.py`
- Given the editor serving a copy of a bootstrap template under `templates/bootstrap/x.html`
- When the browser sends a save
- Then the answer is status 403 `{"ok":false,"error":"Refusing to modify a template: <absolute path of x.html>"}` and the file is unchanged

### SPEC-0009/E2E-011: Too large
- Level HTTP; Driver declared 52 428 801 and sent 52 428 800; Location `tests/test_save_safety_e2e.py` (generous timeout for the accepted case)
- Given DECK served
- When a request declares a length of 52 428 801 bytes, and another declares and sends 52 428 800 bytes of valid JSON
- Then the first is answered 413 `{"error":"Request too large"}` without reading the body, the file unchanged; the second is accepted

### SPEC-0009/E2E-012: Invalid length
- Level HTTP; Driver `abc` and `-5`; Location `tests/test_save_safety_e2e.py`
- Given DECK served
- When a request is sent with `Content-Length: abc`, and another with `Content-Length: -5`
- Then both are answered 400 `{"error":"Invalid Content-Length"}` and the file is unchanged

### SPEC-0009/E2E-013: Read only folder
- Level HTTP; Driver read only folder (`chmod 0o555`); Location `tests/test_save_safety_e2e.py`
- Given DECK in a folder where new files cannot be created
- When the browser saves
- Then the answer is status 500 with an `error` text, the file equals the saved copy and no other file exists in the folder

### SPEC-0009/E2E-014: Failure at the last step
- Level HTTP; Driver `monkeypatch.setattr(fileio, "replace_file", raiser)` with `OSError(errno.EIO, "Input/output error")`; Location `tests/test_save_safety_e2e.py`
- Given DECK, and the final replacement of the file made to fail
- When the browser saves
- Then the answer is status 500, the file equals the saved copy, and the folder holds no leftover temporary file

### SPEC-0009/E2E-029: Template with an oversize body
- Level HTTP; Driver template plus oversize; Location `tests/test_save_safety_e2e.py`
- Given the editor serving a copy of a bootstrap template under `templates/bootstrap/x.html`
- When a request declares a length of 52 428 801 bytes
- Then the answer is status 413 `{"error":"Request too large"}`

### SPEC-0009/E2E-030: Template with a stale base
- Level HTTP; Driver template plus stale base; Location `tests/test_save_safety_e2e.py`
- Given the template of E2E-029 and a save carrying a `base_mtime` different from the file's
- When the browser sends it
- Then the answer is status 403 (not 409) with the template message, file unchanged

## Constraints

- Files not to touch: `static/*` (the browser stays unchanged), `cli.py`, `mcp_server.py`.
- Dependencies not to add: none.
- Patterns to avoid: any test hook in shipped configuration (the only seam is `fileio.replace_file`); patching `os.replace` or `time.time` globally.
- Order of refusals and wording of 403 (origin) and 415 (content type) of SPEC-0005 stay unchanged.
- Scope boundary: no `reason`, no `history` here (US-0050); `new` command copy untouched.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_http_origin_e2e.py`, `tests/test_http_caching.py`, `tests/test_http_health.py`, `tests/test_settings.py`, `tests/test_config.py`, `tests/test_autosave_focus_e2e.py` (incl. `test_failed_save_keeps_focus`) unchanged and green; SPEC-0007 `atomic_write` unit tests (failure cleanup, mode, symlink) still green; no test asserts the removed silent template skip (none exists).
- [ ] Docs updated: none in this story (closing story US-0051 carries README, AGENTS.md and `.agent_docs`, DEC-019).
- [ ] Self review: full (requirements met, error paths, order of checks, leftover temp files, tests non flaky, no scope creep).
- [ ] If the story registers an MCP tool: not applicable.
- [ ] One commit `US-0048: Atomic, guarded, conflict aware browser save (server side)`, body `Spec: SPEC-0009` and `FR-NEW-001, FR-NEW-002, FR-NEW-007`.
