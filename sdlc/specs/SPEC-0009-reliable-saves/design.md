# SPEC-0009: Reliable saves and agent/browser coordination, design

> Spec: sdlc/specs/SPEC-0009-reliable-saves/spec.md
> Nature: FEAT
> Depth: M
> Security: n/a
> Designed on: 2026-11-03
> Target tier: 2 (default: no `--tier`, no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

## 1. Stack and skills

| Element | Choice | Version | Note |
|---|---|---|---|
| Language, tooling | Python, uv, hatchling | `requires-python >=3.13` (`pyproject.toml:8`) | unchanged |
| CLI | Click, kept (documented deviation from the Typer rule, `.agent_docs/python.md`) | `click>=8.0` (`pyproject.toml:17`, lock 8.4.2) | two new subcommands `history`, `restore` |
| Tool protocol | FastMCP | `fastmcp>=2.0` (`pyproject.toml:14`, installed 3.4.6) | two new tools; errors raised as `fastmcp.exceptions.ToolError` (import verified in the venv) |
| Config | pydantic-settings | `>=2.7` (`pyproject.toml:18`) | new setting `HTMLEDITOR_STATE_DIR` plus read only `XDG_STATE_HOME` |
| HTTP | stdlib `ThreadingHTTPServer` | stdlib | unchanged |
| Browser | classic scripts, no build | n/a | `editor-save.js` (save), `editor.js` (state, start up, polling) after SPEC-0012 |
| Tests | pytest, pytest-asyncio, pytest-playwright | `pytest>=8.0`, `pytest-playwright>=0.6` (`pyproject.toml:32-35`) | unchanged |

No new dependency (nothing to flag NEEDS DECISION). Rules applied from the python skill: `make` is the only entry point (`make check` = lint, format-check, typecheck, security, test-cov >= 80); configuration only through `Settings` (layers in use today: environment and local `.env`, `config.py:86-96`; no yaml source exists and none is added); nothing on stdout in the MCP process (logs to stderr and file; `click.echo` only in `cli.py`); `trace_span` on every file mutation (`file.write` in `atomic_write`, `history.snapshot`, `history.restore`); mypy strict, ruff, `%` logging, `__slots__` and frozen dataclasses for the value objects; dependency injection by parameter (clock, store, history) with the process singleton `EditorState` as the single composition point; no sync/async rework (the handler is a thread per request, existing).

## 2. Approaches

### 2.1 Where the snapshot happens

**Chosen: a `reason` keyword on the shared `atomic_write` (hook inside the writer).** The writer reads the old bytes, writes the temporary file, stages the snapshot, replaces, then prunes. Because the snapshot sits inside the same transaction as the replace, "kept only if the write succeeds" (FR-NEW-004) and "nothing kept when bytes are equal" are enforced once for the browser save, `patch` and `restore`. SPEC-0007's call changes by one line (`atomic_write(path, data)` becomes `atomic_write(path, data, reason="patch")`). Cons: `fileio` knows the history module.

Rejected: callers snapshot before calling `atomic_write` (three copies of read, compare, stage, undo-on-failure; the failed-write rule cannot be guaranteed by the caller without re implementing the transaction).

### 2.2 How state is stored

**Chosen: one directory per file under the state directory, keyed by a hash of the absolute path, with one small JSON per concern (`server.json`, `update.json`) plus `last.json`.** A process updating the flag never rewrites the server record and vice versa, so two processes cannot clobber each other's fields (read, modify, write races disappear because each writer owns a whole file written atomically).

Rejected: a single `state.json` for everything with a lock file (needs cross process locking, stale lock handling, and a read modify write of the whole record on every flag change).

### 2.3 How history versions are indexed

**Chosen: no index; a version is a file `<id>.<reason>.html` in the file's `history/` directory.** Listing is a directory scan; `bytes` is `st_size`; creation order is the order of the id (UTC time, then numeric suffix). Nothing to corrupt or keep in sync.

Rejected: `index.json` (second file to update atomically with every snapshot, and to repair when it disagrees with the version files).

### 2.4 Clock

**Chosen: injected callable.** `EditorState.clock: Callable[[], float]` (default `time.time`) drives the update flag; `HistoryStore(root, clock)` drives ids. Tests set `get_state().clock` to a `FakeClock` (E2E-005, 020, 021). Rejected: patching `time.time` globally (breaks logging, tracing and the HTTP server in the same process).

## 3. Architecture

```
browser (editor-save.js, editor.js)           agent / user
  POST /content {html, base_mtime, force}       MCP tools history/restore/update_*   CLI history/restore
        |                                                  |                              |
  http_server._receive_content                  mcp_server.py                          cli.py
   gate > length > size > type > JSON > template > conflict > write                         |
        |                                                  |                              |
        +-------------> fileio.atomic_write(path, data, reason=...) <---- history.restore_version
                         |  read old, equal? stop (False)          (patch also, SPEC-0007)
                         |  mkstemp in same dir, write, fsync, chmod
                         |  history.stage (reason given)
                         |  replace_file(tmp, path)   <== failure seam
                         |  on failure: discard staged, remove tmp, raise OSError
                         |  on success: history.prune (keep 20)
                         v
                   state directory (HTMLEDITOR_STATE_DIR)
                     last.json   files/<key>/{server.json, update.json, history/<id>.<reason>.html}
EditorState (state.py): reads and writes the records, owns clock, computes update expiry
```

New or changed modules: `fileio.py` (extend: `reason`, `history`, `replace_file`, `is_template_path`), `history.py` (new: store, `Version`, `HistoryError`, `list_versions`, `restore_version`), `state.py` (store backed, expiry), `config.py` (state dir), `http_server.py` (save pipeline, status fields), `mcp_server.py` (update tools, two new tools), `cli.py` (two commands), `arch_layout.py` (atomic write), `editor-save.js`, `editor.js`, `editor.html`, `editor.css`.

Request flow of a browser save (all in `_receive_content`, helpers are pure and tested without sockets):

1. gate (SPEC-0005, unchanged) then "No file loaded" 404 (unchanged);
2. `parse_content_length(header)`: absent is 0; otherwise a non empty ASCII digit string, else `SaveRefusal(400, {"error":"Invalid Content-Length"})`; more than 52 428 800 raises `SaveRefusal(413, {"error":"Request too large"})` before any read;
3. read the body; content type other than `application/json` is 415 (unchanged `_refuse`);
4. JSON object with a string `html`, else 400 `{"error":"Invalid JSON body"}`;
5. `is_template_path(state.current_file)` then 403 `{"ok":false,"error":"Refusing to modify a template: <path>"}`;
6. under `state.save_lock`: conflict check (`base_mtime` numeric, not `force` true, differs from the file mtime: 409 `{"ok":false,"error":"File changed on disk","mtime":<current>}`); clean the HTML; `atomic_write(target, html, reason="keep-mine" if force else "browser-save")`; answer 200 `{"ok":true,"mtime":<stat after>}`;
7. `OSError` anywhere in 6 answers 500 `{"error":"<strerror>"}`.

## 4. Data model

### 4.1 State directory

Resolved by `Settings.state_dir`: `HTMLEDITOR_STATE_DIR`, else `$XDG_STATE_HOME/mcp-htmleditor`, else `~/.local/state/mcp-htmleditor`, else (home not resolvable, `Path.home()` raises `RuntimeError`) `<tempfile.gettempdir()>/mcp-htmleditor-<os.getuid()>`. Directories are created with mode 0700 on first write (history holds copies of the user's documents).

```
<state_dir>/
  last.json                        {"file": "<absolute path>"}                  file most recently served or opened by any process
  files/<key>/                     key = sha256(absolute resolved path, UTF-8).hexdigest()[:32]
    server.json                    {"file","port","pid","poll_interval"}         written by serve / start_server / stop
    update.json                    {"file","started_at": <epoch seconds float>}  written by update_start; removed by update_end
    history/<id>.<reason>.html     the previous content, bytes verbatim
```

### 4.2 Records

- `update.json` stores the start instant, never a boolean. In progress means `0 <= now - started_at < 120`; `update_expires_in = ceil(120 - max(0, now - started_at))` (1 to 120); at 120 seconds exactly the flag is cleared. An expired record is left in place and ignored.
- Constants (module level, not settings, fixed by the spec): `UPDATE_TTL_SECONDS = 120.0`, `HISTORY_LIMIT = 20`, `MAX_BODY_BYTES = 52_428_800`.
- A process that has served or opened no file (`EditorState.current_file is None`) resolves its file from `last.json` for `update_start`, `update_end` and `get_status`; a process that has one uses its own. With neither, the flag is held in memory for the process (keeps the tools working before any file exists, as today).

### 4.3 History

- Version id: `strftime("%Y%m%dT%H%M%S", gmtime(clock()))` plus `Z`; when any version of that file already has the id, suffix `-2`, `-3`, ... (decimal). Order key: `(timestamp, suffix or 1)`, so `-10` sorts after `-9`. Newest first is the reverse.
- Reasons: `browser-save`, `keep-mine`, `patch`, `restore` (no dot, no slash, safe in a file name).
- `Version(id: str, bytes: int, reason: str)` frozen, `slots=True`.
- Retention: after a successful write, delete the oldest versions beyond 20 for that file. Versions are staged by writing a hidden temp file in `history/` then `os.replace` onto the final name; hidden temp files are ignored by listing.
- Equal bytes: `atomic_write` compares old and new bytes first and returns `False` without touching anything (no temp file, no version, mtime unchanged).

## 5. Contracts and interfaces

### 5.1 HTTP

`POST /content`, `Content-Type: application/json`, body `{"html": "<string>", "base_mtime": <number, optional>, "force": <true, optional>}`. `base_mtime` not a JSON number (booleans excluded) is treated as absent; only `force` equal to `true` counts as force.

| Case | Status | Body |
|---|---|---|
| invalid `Content-Length` (empty, non digits, `-5`, `abc`) | 400 | `{"error":"Invalid Content-Length"}` |
| declared length above 52 428 800, body not read | 413 | `{"error":"Request too large"}` |
| content type not JSON | 415 | `{"error":"unsupported content type"}` (unchanged) |
| body not a JSON object, or `html` not a string | 400 | `{"error":"Invalid JSON body"}` |
| template path | 403 | `{"ok":false,"error":"Refusing to modify a template: <absolute path>"}` |
| `base_mtime` stale, no `force` | 409 | `{"ok":false,"error":"File changed on disk","mtime":<current>}` |
| saved, or identical bytes | 200 | `{"ok":true,"mtime":<mtime after>}` (unchanged mtime when identical) |
| write, snapshot or state directory failure | 500 | `{"error":"<strerror>"}` |

`GET /status` gains `update_expires_in` (int or `null`); `update_in_progress` is false after expiry. `POST /arch-layout` is unchanged on the wire.

### 5.2 Python signatures

```python
# fileio.py (extends SPEC-0007's `atomic_write(path: str | Path, data: bytes) -> None`; every SPEC-0007 call stays valid, the return value is new; str data is encoded UTF-8; reason=None keeps today's behaviour exactly)
def atomic_write(path: str | Path, data: bytes | str, *, reason: str | None = None,
                 history: HistoryStore | None = None) -> bool:
    """True if the file was replaced, False if data equals the current bytes."""
def replace_file(source: str, destination: str) -> None:   # test seam, wraps os.replace
def is_template_path(path: str) -> bool:                    # "\\" read as "/", contains /templates/bootstrap/ or /templates/reference/

# history.py
HISTORY_LIMIT: int = 20
@dataclass(frozen=True, slots=True)
class Version: id: str; bytes: int; reason: str
class HistoryError(Exception): ...                          # str(exc) is the message after "error: "
class HistoryStore:
    def __init__(self, root: Path, clock: Callable[[], float] = time.time) -> None
    def stage(self, path: Path, content: bytes, reason: str) -> Version
    def discard(self, path: Path, version: Version) -> None
    def prune(self, path: Path) -> None
    def list_versions(self, path: Path) -> list[Version]     # newest first
    def read(self, path: Path, version_id: str) -> bytes
def default_store() -> HistoryStore                          # HistoryStore(config.state_dir())
def list_versions(file: str, store: HistoryStore | None = None) -> tuple[Path, list[Version]]
def restore_version(file: str, version_id: str, store: HistoryStore | None = None) -> Path

# state.py (EditorState, same singleton, same file name)
clock: Callable[[], float]
def start_update(self) -> int                                # returns 120
def end_update(self) -> None
def set_update_flag(self, value: bool) -> None               # compat wrapper for SPEC-0007, calls the two above
update_in_progress: property[bool]; update_expires_in: property[int | None]
def snapshot(self) -> dict[str, Any]                         # file, port, pid, update_in_progress, update_expires_in, mtime
save_lock: threading.Lock                                    # serializes browser saves

# http_server.py
class SaveRefusal(Exception): status: int; payload: dict[str, Any]
def parse_content_length(raw: str | None) -> int
```

### 5.3 Command line

- `mcp-htmleditor history <file>`: lines `f"{v.id}  {v.bytes} bytes  {v.reason}"` newest first, or `No history for <file>`; exit 0. Only the file's existence is checked (templates allowed).
- `mcp-htmleditor restore <file> <id>`: checks in order template, file not found, unknown id; prints `Restored <file> to <id>`; equal content: same line, nothing written.
- Errors go to stderr as `error: <message>` and exit 1 (`click.echo(..., err=True)` then `ctx.exit(1)`; `ClickException` is not used because it prints `Error:`). Messages, `<file>` as typed: `File not found: <file>`; `Unknown history id "<id>". Valid ids: <id1>, <id2>` (`Valid ids: none`); `Refusing to modify a template: <file>`; write failure: the strerror.
- Both resolve `<file>` with `Path(file).resolve()` (current directory for relative names) and need no server.

### 5.4 MCP tools

`history(file: str) -> {"file": <abs>, "versions": [{"id","bytes","reason"}]}` and `restore(file: str, id: str) -> {"ok": true, "file": <abs>, "id": <id>}`, traced `mcp.history`, `mcp.restore`. Errors raise `ToolError(message)` with the CLI message without its `error: ` prefix. `update_start` returns `{"ok":true,"expires_in":120}`; `get_status` adds `update_expires_in`.

### 5.5 Browser

New state in `editor.js`: `baseMtime` (null until read), `conflictActive`, `conflictMtime`, `pollFailures`. Top level declarations are read only inside functions (SPEC-0012 rule). `editor.html` gets one container `#notices` (`role="status"`, never focusable, no autofocus) holding `#save-conflict` (text `The file changed on disk. Reload to see the changes, or keep your version.`, buttons `Reload`, `Keep mine`), `#save-error` (`Save failed: <text>`) and `#connection-lost` (`Connection to the editor server lost`). `baseMtime` is set: at start up and from the first poll that finds it null; to the answer's `mtime` after the page's own successful save; to `status.mtime` where the poll calls `reloadFrame`; to `conflictMtime` after `Reload`. A poll with unsaved edits never changes it. `saveContent(options)`: returns early when `conflictActive` and not `options.force`; sends `base_mtime` only when `baseMtime !== null`, `force: true` only for Keep mine; 200 updates `baseMtime` and `lastMtime` from the answer (the post save `/status` read is removed), hides the three notices, `markSaved`; 409 sets `conflictActive`, stores `conflictMtime`, shows the conflict notice, keeps the unsaved state; any other status or a network error shows `Save failed: <error text or message>` and keeps the unsaved state; the next autosave trigger sends again.

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/config.py` | edit: `state_dir_override`, `xdg_state_home_override`, `state_dir` property, `state_dir()` accessor, two names added to `_SIGNIFICANT_ENV_VARS`, `_PATH_FIELDS`, docstring (`config.py:12` says state is next to the file) | FR-NEW-008 | STORY-A |
| `src/mcp_htmleditor/state.py` | rewrite persistence: records in the state dir, expiry, clock, `snapshot()`, `save_lock` | FR-NEW-006, 008 | STORY-A |
| `src/mcp_htmleditor/mcp_server.py` | edit `update_start`, `update_end`, `get_status` | FR-NEW-006 | STORY-A |
| `src/mcp_htmleditor/http_server.py` | edit `_serve_status` | FR-NEW-006 | STORY-A |
| `tests/conftest.py` | edit: autouse `isolate_state_dir` | FR-NEW-008 | STORY-A |
| `tests/test_state.py` | edit (see below) plus new tests | FR-NEW-006, 008 | STORY-A |
| `src/mcp_htmleditor/fileio.py` | edit (file created by SPEC-0007): `reason`, `history`, `replace_file`, `is_template_path`, `file.write` span | FR-NEW-001, 004 | STORY-B, STORY-D |
| `src/mcp_htmleditor/http_server.py` | edit `_receive_content`, helpers, `SaveRefusal` | FR-NEW-001, 002, 007 | STORY-B |
| `src/mcp_htmleditor/arch_layout.py` | edit `layout_file` write (`arch_layout.py:1202`) to `atomic_write` | FR-NEW-001 | STORY-B |
| `tests/conftest.py` | edit: `HAS_CHROMIUM`, `needs_chromium`, `ServedDeck`, `served_deck` fixture, `FakeClock` | E2E support | STORY-B |
| `tests/test_save_safety_e2e.py` | create | E2E-001, 002, 007, 010 to 014, 029, 030 | STORY-B |
| `src/mcp_htmleditor/static/editor-save.js`, `editor.js`, `editor.html`, `editor.css` | edit | FR-NEW-002, 003, 007, 009 | STORY-C |
| `tests/test_save_ui_e2e.py` | create | E2E-008, 017, 018, 027, 028, 032 | STORY-C |
| `src/mcp_htmleditor/history.py` | create | FR-NEW-004, 005 | STORY-D |
| `src/mcp_htmleditor/fileio.py`, `http_server.py` | edit: snapshot reasons on browser save | FR-NEW-004 | STORY-D |
| `src/mcp_htmleditor/cli.py` | edit: `history`, `restore` | FR-NEW-005 | STORY-D |
| `tests/test_history_e2e.py` | create | E2E-003, 004, 009, 015, 016, 019, 022, 023, 031 | STORY-D |
| `src/mcp_htmleditor/mcp_server.py` | edit: tools `history`, `restore` (and the "Exposes N tools" docstring, `mcp_server.py:3`) | FR-NEW-005 | STORY-E |
| `src/mcp_htmleditor/deck/patch.py` (SPEC-0007 STORY-D, the only caller of `atomic_write` there) | edit: one line, add `reason="patch"` | FR-NEW-004, 001 | STORY-E |
| `skill/core.md` | edit: two lines at the end of `## Tools` (`- history: ...`, `- restore: ...`), SPEC-0006 design section 3 | FR-NEW-005 | STORY-E |
| `tests/test_history_tools.py` | create | E2E-006, 026 | STORY-E |

Deployment and documentation (closing story, listed apart from the 3 to 5 file count, DEC-019): `Dockerfile` (`ENV HTMLEDITOR_STATE_DIR=/var/lib/mcp-htmleditor`, `mkdir` and `chown` for `appuser`, because the image has no home directory, `Dockerfile:51-53`), `docker-compose.yml` (volume for the state dir), `.env.example` (`HTMLEDITOR_STATE_DIR`), `README.md` (conflict behaviour, history and restore usage, update expiry, state location; `README.md:361` still says `.mcp_state.json`), `AGENTS.md` (line 82 `.mcp_state.json`), `.agent_docs/architecture.md` (diagram line 11, `state.py` row line 24, new modules `fileio.py`, `history.py`, save path section), `.agent_docs/testing.md` (new test files), `.agent_docs/observability.md` (spans `history.snapshot`, `history.restore`, `mcp.history`, `mcp.restore`). `.gitignore` keeps `.mcp_state.json` (files left by older versions).

### Affected existing tests

| Test | Decision | Reason |
|---|---|---|
| `tests/test_state.py::test_set_file_resolves_and_persists` (asserts `.mcp_state.json` at `:39`) | modify: assert `server.json` under the state dir and no file next to the HTML | FR-NEW-008 removes the file next to the user's file |
| `test_set_update_flag_persists` (`:51`) | modify: use `start_update` / `end_update`, assert `update.json` and the property | FR-NEW-008, FR-NEW-006 |
| `test_load_corrupt_file_is_ignored` (`:107`) | modify: corrupt `server.json` instead | FR-NEW-008 |
| `test_save_then_load_roundtrip`, `test_load_missing_file_is_noop`, `test_defaults`, `test_singleton_*`, `test_get_mtime_*` | keep | path agnostic; pass with the isolated state dir |
| `tests/conftest.py` | modify (autouse state dir isolation) | without it every test writes into the real `~/.local/state` |
| `tests/test_autosave_focus_e2e.py` (incl. `test_failed_save_keeps_focus`, `:196`) | keep | the new notices never take focus; the self save no reload behaviour is preserved by adopting the answer's mtime |
| `tests/test_http_origin_e2e.py`, `test_http_caching.py`, `test_http_health.py`, `test_settings.py`, `test_config.py` | keep | order and wording of refusals 403/415 unchanged; `test_settings.clean_env` iterates the tuple, so the new names are cleared too |
| tests asserting the ignored template save (`skipped`) | none exist (searched `tests/`) | n/a |

## 7. Compatibility and risks

- Older clients that send no `base_mtime` are not checked (spec constraint). The response gains `mtime`; nothing removed.
- `.mcp_state.json` files from older versions stay on disk, ignored. A running old server and a new tool process do not see each other's flag.
- Container: without `HTMLEDITOR_STATE_DIR` the image would answer 500 on every save (no writable home). Fixed by the deployment files above; do not release STORY-A to STORY-D images before STORY-E.
- Race: the check and the replace are serialized per process by `save_lock`, not against an agent writing the file directly or another process (`restore` CLI). The window is microseconds; a lost agent write in that window is still recoverable only if it came through the product. Accepted, stated in the README.
- Clock: ids come from `clock`; a backwards clock can order a new version before an older one. `restore` and listing use the id order, as the spec defines the id as the time.
- Id collision across two processes writing the same file in the same second and suffix is possible (check then rename). Not guarded; improbable.
- `base_mtime` is read at load or at poll time, not from the bytes served; an agent write between the content fetch and that read can hide a conflict for the first save. The window is one poll; the safe direction (older base) is used when a reload follows a poll.
- The `stop_http_server` function shuts down but never closes the listening socket (`http_server.py:723`); the browser tests therefore simulate server loss with `page.route` instead of stopping the server.
- Failure tests that use a read only folder cannot fail when the suite runs as root; they skip with `os.geteuid() == 0`.
- State is not cleaned for deleted files (history of removed files stays). Out of scope.
- Case insensitive file systems: the same file typed with another case gets another key and another history.
- A 50 MB body costs a full BeautifulSoup parse in `_strip_editor_artifacts`; E2E-011's accepted case is slow (seconds). Marked with a generous timeout.

## 8. omit

## 9. Test strategy

Layers: pure unit tests for helpers (no sockets); HTTP level tests against a real `start_http_server` (pattern of `tests/test_http_origin_e2e.py:93`); CLI tests with `click.testing.CliRunner` (stderr is separate in Click 8.2+); tool tests with `fastmcp.Client(mcp)` in process (`asyncio_mode = auto`); Playwright tests with the existing skip pattern, moved to `tests/conftest.py` as `needs_chromium` (`tests/test_autosave_focus_e2e.py:44-51` shows the original). Every failure seam is a plain attribute, never a global patch of the standard library.

Seams:
- Last step failure (E2E-014, 031): `monkeypatch.setattr(fileio, "replace_file", raiser)` where `raiser` raises `OSError(errno.EIO, "Input/output error")`; the server runs in the same process on a thread, so the patch applies.
- Read only folder (E2E-013, 028, 032): `chmod 0o555` on the deck folder, restored in a `finally`; skipped as root.
- Clock (E2E-005, 020, 021): `FakeClock` with `advance(seconds)` assigned to `get_state().clock`.
- Two processes (E2E-025): `subprocess.run([sys.executable, "-c", script])` with `HTMLEDITOR_STATE_DIR` and `PYTHONPATH=src`; the script calls `update_start` through `fastmcp.Client`.
- Server loss (E2E-017, 018, 027): `page.route("**/status", handler)` aborting a counted number of requests; poll interval forced with `HTMLEDITOR_POLL_INTERVAL=100` to keep the tests fast.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| E2E-001 | HTTP | real server, `http.client` | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-002 | HTTP | save with the reloaded mtime | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-003 | CLI | two saves then `history` | `tests/test_history_e2e.py` | STORY-D |
| E2E-004 | CLI | `restore` then `history` | `tests/test_history_e2e.py` | STORY-D |
| E2E-005 | tool | `fastmcp.Client`, `FakeClock` | `tests/test_state.py` | STORY-A |
| E2E-006 | tool | `fastmcp.Client` | `tests/test_history_tools.py` | STORY-E |
| E2E-007 | HTTP | agent write between load and save | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-008 | browser | Playwright, agent write then typing | `tests/test_save_ui_e2e.py` | STORY-C |
| E2E-009 | browser + CLI | Playwright Keep mine, then `history` | `tests/test_history_e2e.py` | STORY-D |
| E2E-010 | HTTP | template copy under `templates/bootstrap/` | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-011 | HTTP | declared 52 428 801 and sent 52 428 800 | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-012 | HTTP | `abc` and `-5` | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-013 | HTTP | read only folder | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-014 | HTTP | `replace_file` seam | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-015 | CLI | unknown id | `tests/test_history_e2e.py` | STORY-D |
| E2E-016 | CLI | never saved file | `tests/test_history_e2e.py` | STORY-D |
| E2E-017 | browser | `page.route` abort | `tests/test_save_ui_e2e.py` | STORY-C |
| E2E-018 | browser | unroute | `tests/test_save_ui_e2e.py` | STORY-C |
| E2E-019 | CLI | ghost file, template restore | `tests/test_history_e2e.py` | STORY-D |
| E2E-020 | tool | `FakeClock` at 121 s | `tests/test_state.py` | STORY-A |
| E2E-021 | tool | `FakeClock`, restart at 100 s | `tests/test_state.py` | STORY-A |
| E2E-022 | HTTP + CLI | 21 saves then `history` | `tests/test_history_e2e.py` | STORY-D |
| E2E-023 | HTTP + CLI | identical save | `tests/test_history_e2e.py` | STORY-D |
| E2E-024 | HTTP + tool | folder listing | `tests/test_state.py` | STORY-A |
| E2E-025 | tool, two processes | subprocess | `tests/test_state.py` | STORY-A |
| E2E-026 | tool + CLI | `patch` then `history` | `tests/test_history_tools.py` | STORY-E |
| E2E-027 | browser | one aborted poll | `tests/test_save_ui_e2e.py` | STORY-C |
| E2E-028 | browser | Keep mine on a read only folder | `tests/test_save_ui_e2e.py` | STORY-C |
| E2E-029 | HTTP | template plus oversize | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-030 | HTTP | template plus stale base | `tests/test_save_safety_e2e.py` | STORY-B |
| E2E-031 | HTTP + CLI | `replace_file` seam, history unchanged | `tests/test_history_e2e.py` | STORY-D |
| E2E-032 | browser | read only folder, then writable | `tests/test_save_ui_e2e.py` | STORY-C |

Unit tests added with the stories (not E2E): STORY-A: state dir resolution (override, XDG, home, no home), record round trip, expiry clamp (negative elapsed), unbound in memory flag; STORY-B: `parse_content_length` table, `is_template_path`, `atomic_write` (mode preserved, read only target replaced, temp removed on failure, equal bytes returns False); STORY-D: `HistoryStore` ids with suffixes (`-2` to `-21`, order `-10` after `-9`), prune, discard; STORY-E: tool errors (unknown id, missing file, template, write failure) carry the CLI message.

## 10. Decisions log

- **DEC-001:** `atomic_write` takes `reason` and an optional `history`; with a reason it stages the snapshot inside the write transaction and returns `False` without writing on equal bytes. **Obliged by:** SPEC-0009/FR-NEW-004, SPEC-0009/FR-NEW-001. **Rationale:** one place enforces "kept only if the write succeeds" and "nothing kept when equal" for browser save, patch and restore; SPEC-0007's patch needs a one line change. **Alternatives considered:** caller side snapshot (three copies, no transaction). **Source:** spec FR-NEW-004 business rules; cross spec context (c). **Evidence:** `src/mcp_htmleditor/http_server.py:332` (the direct write to replace).
- **DEC-002:** Versions are files named `<id>.<reason>.html`, no index; `bytes` is the file size; order by (timestamp, numeric suffix). **Obliged by:** SPEC-0009/FR-NEW-004. **Rationale:** nothing to keep consistent, listing is a scan, `bytes` is by construction the stored byte count. **Alternatives considered:** `index.json`. **Source:** spec FR-NEW-004 (id shape with `-2`, `-3`, decimal no padding). **Evidence:** spec FR-NEW-004; no existing store in `src/`.
- **DEC-003:** Order inside `atomic_write`: read old bytes, create the temp file, write and fsync, stage the snapshot, replace, then prune; on any failure after staging, discard the staged version and remove the temp file. **Obliged by:** SPEC-0009/FR-NEW-004, SPEC-0009/FR-NEW-001. **Rationale:** a failed folder (E2E-013) fails at temp creation before anything is staged; a failed replace (E2E-014, 031) leaves history unchanged; pruning only after success keeps a full history intact when a write fails at the cap. **Alternatives considered:** snapshot after the replace (a crash between the two loses the only copy of the old content). **Source:** spec E2E-013, 014, 031. **Evidence:** `http_server.py:330-337` (current write has no ordering).
- **DEC-004:** The only failure seam is the module function `fileio.replace_file(source, destination)` wrapping `os.replace`. **Obliged by:** SPEC-0009/FR-NEW-001. **Rationale:** spec 14.3 requires a seam for the last step; a named function patched by `monkeypatch` is the smallest one and applies to a server thread of the same process. **Alternatives considered:** a settings flag or environment variable that injects failure into production code (rejected: test hooks in shipped config). **Source:** spec 14.3. **Evidence:** spec E2E-014.
- **DEC-005:** `state_dir` is a `Settings` property fed by two new override fields (`HTMLEDITOR_STATE_DIR`, `XDG_STATE_HOME`), both added to `_PATH_FIELDS` and to `_SIGNIFICANT_ENV_VARS`; no home falls back to `<tmp>/mcp-htmleditor-<uid>`. **Obliged by:** SPEC-0009/FR-NEW-008. **Rationale:** the memoization keys on the listed variables (`config.py:61-75`), so a missing name would serve a stale state dir after a test or an environment change. **Alternatives considered:** reading the variable with `os.environ` (forbidden by the constitution, `sdlc/constitution.md`). **Source:** spec FR-NEW-008. **Evidence:** `src/mcp_htmleditor/config.py:48,61,149`.
- **DEC-006:** State is one directory per file keyed by `sha256(resolved absolute path)[:32]`, with `server.json` and `update.json` as separate files and a `last.json` record. **Obliged by:** SPEC-0009/FR-NEW-008. **Rationale:** each writer owns whole files written atomically, so processes never clobber each other's fields; the key is stable across processes. **Alternatives considered:** one `state.json` with a lock file. **Source:** spec FR-NEW-008 ("keyed by the file's absolute path", "share the state between processes"). **Evidence:** `state.py:48-52` (today the path derives from the file's folder).
- **DEC-007:** The update flag stores `started_at`; `update_in_progress` and `update_expires_in` are computed on read from the injected `EditorState.clock`; elapsed is clamped to at least 0. **Obliged by:** SPEC-0009/FR-NEW-006. **Rationale:** a stored start instant is shared across processes and expires without a timer thread; the clamp keeps `update_expires_in` in 1 to 120 under clock skew between processes. **Alternatives considered:** in memory timer (not shared, E2E-025), storing a deadline (same effect, start instant is easier to debug). **Source:** spec FR-NEW-006 business rules. **Evidence:** `state.py:41` (boolean flag), `state.py:92` (setter).
- **DEC-008:** A process with no file of its own resolves the file from `last.json` for `update_start`, `update_end` and `get_status`, and reads port and pid from that file's `server.json`; `open_file` and `set_file` write `last.json`. **Obliged by:** SPEC-0009/FR-NEW-008. **Rationale:** spec rule "a process that has served no file itself uses that record's file". **Alternatives considered:** none that satisfy E2E-025. **Source:** spec FR-NEW-008. **Evidence:** `mcp_server.py:93-107` (status read from the process singleton only).
- **DEC-009:** `set_update_flag(value)` stays as a thin wrapper over `start_update` / `end_update`. **Obliged by:** SPEC-0009/FR-NEW-006. **Rationale:** SPEC-0007 states that `patch` sets the flag while writing (`sdlc/specs/SPEC-0007-agent-editing-tools/spec.md:173`) and is likely to call this method; removing it would break landed code. **Alternatives considered:** delete it (breaks SPEC-0007). **Source:** cross spec context. **Evidence:** `mcp_server.py:145,161` (current callers).
- **DEC-010:** The save pipeline is a sequence of pure checks raising `SaveRefusal(status, payload)` in the spec order, called from `_receive_content`; the 404 "No file loaded" stays first because it is not in the spec order. **Obliged by:** SPEC-0009/FR-NEW-007. **Rationale:** `_EditorHandler` is `# pragma: no cover` (`http_server.py:75`); pure helpers keep the order unit testable and the handler thin. **Alternatives considered:** inline `if` ladder in the handler (untested ordering). **Source:** spec FR-NEW-007 order list. **Evidence:** `http_server.py:290-340`.
- **DEC-011:** A valid length is `value.isascii() and value.isdigit()`; a digit string longer than 10 significant digits is already too large and is not passed to `int()`. **Obliged by:** SPEC-0009/FR-NEW-007. **Rationale:** `str.isdigit` accepts non ASCII digits (so ASCII is checked), and `int()` raises on very long digit strings (Python's integer string limit), which would be an unhandled error again. **Alternatives considered:** `try int()` only (accepts `+5`, ` 5`, `٥`). **Source:** spec FR-NEW-007 ("non empty string of ASCII digits only"). **Evidence:** `http_server.py:297`.
- **DEC-012:** Conflict compares `base_mtime` with `target.stat().st_mtime` by float equality; the answer's `mtime` is a `stat` after the replace. A missing file reads as `0.0` like `get_mtime`. **Obliged by:** SPEC-0009/FR-NEW-002. **Rationale:** JSON round trips a float64 exactly and `/status` already serves `st_mtime` (`state.py:99-106`), so the browser compares the same number it was given. **Alternatives considered:** integer nanoseconds (changes the existing status contract). **Source:** spec FR-NEW-002, 14.3. **Evidence:** `http_server.py:281`.
- **DEC-013:** The browser keeps `baseMtime` apart from `lastMtime` (the poll's reload detector), adopting the save answer's `mtime` instead of the old extra `/status` read. **Obliged by:** SPEC-0009/FR-NEW-002. **Rationale:** today the poll overwrites `lastMtime` even with unsaved edits (`editor.js:326`), which the spec forbids for the conflict base; the answer's mtime is also exact where the old post save read could race an agent write. **Alternatives considered:** reuse `lastMtime` (violates the "poll does not change it" rule). **Source:** spec FR-NEW-002 business rules. **Evidence:** `editor.js:298-330` and `editor.js:1425-1429` before SPEC-0012.
- **DEC-014:** Notices live in `#notices` in the shell page, with no focusable element except the two conflict buttons and no autofocus. **Obliged by:** SPEC-0009/FR-NEW-003, SPEC-0009/FR-NEW-007, SPEC-0009/FR-NEW-009. **Rationale:** the autosave must never move focus away from the edited zone (SPEC-0004); the shell is outside the iframe. **Alternatives considered:** `alert()` or `confirm()` (steals focus, blocks the poll). **Source:** SPEC-0004 design. **Evidence:** `tests/test_autosave_focus_e2e.py:196`.
- **DEC-015:** Poll failures are counted in the browser (`!ok`, non 200, or invalid JSON each count); three consecutive failures show the notice, the next success clears it. **Obliged by:** SPEC-0009/FR-NEW-009. **Rationale:** exact spec wording; server loss is simulated in tests with `page.route`. **Alternatives considered:** stop and restart the server in the test (the listening socket stays open, see risks). **Source:** spec FR-NEW-009, BL-0013. **Evidence:** `editor.js:300-301` (swallowed failure), `http_server.py:723`.
- **DEC-016:** CLI errors are printed by `click.echo("error: ...", err=True)` followed by `ctx.exit(1)`. **Obliged by:** SPEC-0009/FR-NEW-005. **Rationale:** spec text is lower case `error:` on the error output with exit 1; `click.ClickException` prints `Error:` and exits 1 with a different prefix. **Alternatives considered:** `ClickException` subclass overriding `show` (more code for the same output). **Source:** spec FR-NEW-005. **Evidence:** `cli.py:88` (existing `ClickException` use prints the other prefix).
- **DEC-017:** Tool errors raise `ToolError(message)` where the message is the CLI message without `error: `. **Obliged by:** SPEC-0009/FR-NEW-005. **Rationale:** spec requires "an error whose message is the command line line without its prefix"; `ToolError` is the FastMCP type that reaches the client with its message. **Alternatives considered:** returning `{"ok":false,"error":...}` (not an error for the client). **Source:** spec FR-NEW-005. **Evidence:** import checked in the venv (fastmcp 3.4.6).
- **DEC-018:** `layout_file` writes through `atomic_write` with no reason (no snapshot); `shutil.copyfile` in `new` is untouched. **Obliged by:** SPEC-0009/FR-NEW-001. **Rationale:** FR-NEW-001 states "WHEN the editor server writes a file", and `/arch-layout` is such a write; FR-NEW-004 lists only browser save, patch and restore for history. **Alternatives considered:** leave `layout_file` non atomic (a truncated file after a crash during a diagram edit, the exact failure this spec removes). **Source:** spec FR-NEW-001. **Evidence:** `arch_layout.py:1202`, `http_server.py:365`.
- **DEC-019:** Deployment files and documentation are updated in the closing story and are not counted in the 3 to 5 file rule. **Obliged by:** SPEC-0009/FR-NEW-008. **Rationale:** the image needs `HTMLEDITOR_STATE_DIR` or every save answers 500; documentation is part of the finished product but not code; splitting a docs only story would be a horizontal layer. **Alternatives considered:** a separate docs story (horizontal slice). **Source:** user rules (docs with every implementation). **Evidence:** `Dockerfile:51-53` (`--no-create-home`), `README.md:361`, `AGENTS.md:82`.
- **DEC-020:** Browser saves are serialized in the process by `EditorState.save_lock`; cross process writers are not locked. **Obliged by:** SPEC-0009/FR-NEW-002. **Rationale:** `ThreadingHTTPServer` handles two saves concurrently; the conflict check and the replace must not interleave. **Alternatives considered:** advisory file lock (`fcntl`, not portable, stale lock handling). **Source:** spec 14.3. **Evidence:** `http_server.py` uses `ThreadingHTTPServer` (import at `http_server.py:19`).
- **DEC-021:** Error text for the 500 answers, the CLI and the tools is `exc.strerror or str(exc)`. **Obliged by:** SPEC-0009/FR-NEW-001, SPEC-0009/FR-NEW-005. **Rationale:** spec says "operating system message"; `strerror` is exactly that and does not leak the temporary file name. **Alternatives considered:** `str(exc)` (used today, `http_server.py:335`). **Source:** spec FR-NEW-001. **Evidence:** `http_server.py:335`.
- **DEC-022:** A failure to write the state records in `set_file` or `save` is logged and does not stop the server; the failure surfaces at the first save (history stage) as a 500. **Obliged by:** SPEC-0009/FR-NEW-008. **Rationale:** spec: "a state directory that cannot be created makes a save answer 500"; refusing to start would be a second, unspecified behaviour. **Alternatives considered:** raise at start. **Source:** spec FR-NEW-008. **Evidence:** `http_server.py:696-697` (state saved at start).
- **DEC-023:** STORY-A keeps FR-NEW-006 and FR-NEW-008 together and is marked `min_tier` 3 with 6 files. **Obliged by:** SPEC-0009/FR-NEW-006, SPEC-0009/FR-NEW-008. **Rationale:** the expiry lives in the shared record, E2E-025 needs both, and the isolation fixture touches every test; two single requirement stories would break the 2 to 4 requirement rule. **Alternatives considered:** split into relocation then expiry (one requirement each). **Source:** slicing rules. **Evidence:** spec E2E-025 (FR-NEW-008, 006).
- **DEC-024:** A body that is not a JSON object, or whose `html` is not a string, is answered 400 `Invalid JSON body`. **Obliged by:** SPEC-0009/FR-NEW-007. **Rationale:** `data.get` on a list or `_strip_editor_artifacts` on a non string raises today (`http_server.py:309`); the spec's order has one invalid JSON slot. **Alternatives considered:** leave as is (unhandled error). **Source:** spec FR-NEW-007. **Evidence:** `http_server.py:306-312`.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| STORY-A | State per file in the state directory, expiring update flag | P1 | FR-NEW-006, FR-NEW-008 | main | 3 | no |
| STORY-B | Atomic, guarded, conflict aware browser save (server side) | P1 | FR-NEW-001, FR-NEW-002, FR-NEW-007 | STORY-A, SPEC-0007 | 2 | no |
| STORY-C | Conflict choice, save failures and server loss in the editor | P1 | FR-NEW-003, FR-NEW-007, FR-NEW-009 | STORY-B | 2 | no |
| STORY-D | History snapshots, `history` and `restore` commands | P1 | FR-NEW-004, FR-NEW-005 | STORY-B, STORY-C | 2 | no |
| STORY-E | `history` and `restore` tools, patch snapshots, docs and deployment | P1 | FR-NEW-005, FR-NEW-004, FR-NEW-001 | STORY-D, SPEC-0006, SPEC-0007 | 2 | yes |

Each story leaves `make check` green on main: STORY-A does not change the save path; STORY-B refuses and writes through the new writer with the browser still sending no `base_mtime` yet (unchecked, spec constraint); STORY-C only edits the shell; STORY-D adds `reason` values to calls that already exist; STORY-E adds the two tools and the one line patch change.

Requirement coverage: FR-NEW-001 (B, E), 002 (B), 003 (C), 004 (D, E), 005 (D, E), 006 (A), 007 (B, C), 008 (A), 009 (C). All nine cited; every E2E appears once in section 9; STORY-E is the only story with `closes_spec`.

Validation: checked that DEC-001 to DEC-024 each name an obliging requirement; code claims re read at the cited lines (`http_server.py:290-340`, `state.py:48-106`, `config.py:48,61,149`, `mcp_server.py:93-161`, `arch_layout.py:1202`, `Dockerfile:51-53`). Counts from the spec by command: 9 `FR-NEW`, 32 `E2E`, 5 `SC`.
