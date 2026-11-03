# US-0047: State per file in the state directory, expiring update flag

> Spec: SPEC-0009 (sdlc/specs/SPEC-0009-reliable-saves/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0046
> min_tier: 3
> Files touched: 6
> Closes spec: no

## Objective

Move the editor state out of the user's folder into a state directory keyed by file path, shared between
processes, and make the "update in progress" flag expire after 120 seconds. The save path is not touched.

## Requirements covered

- SPEC-0009/FR-NEW-006: WHEN 120 seconds have elapsed after `update_start` without another `update_start` or `update_end` THE Editor SHALL consider the update finished.
- SPEC-0009/FR-NEW-008: The Editor SHALL NOT create any file next to the user's file for its own state, and SHALL share the state of a file between the processes working on that file.

Business rules, FR-NEW-006: the flag is in progress while less than 120 seconds have elapsed since the last `update_start`; at exactly 120 seconds it is cleared. `update_expires_in` is the whole number `ceil(120 - elapsed)`, from 1 to 120. `update_end` after expiry answers `{"ok":true}` as before. `update_start` answers `{"ok":true,"expires_in":120}`. `get_status` and the editor status add `update_expires_in`, the remaining whole seconds rounded up while an update is in progress, otherwise null. After expiry `update_in_progress` is false in every answer. A second `update_start` restarts the 120 seconds. `update_end` clears the flag at once.

Business rules, FR-NEW-008: the state (current file, port, pid, update flag with its expiry) is kept in the state directory, keyed by the file's absolute path. The state directory is `HTMLEDITOR_STATE_DIR` if set, else `$XDG_STATE_HOME/mcp-htmleditor`, else `~/.local/state/mcp-htmleditor`; with no home directory, `<system temporary directory>/mcp-htmleditor-<user id>`. A state directory that cannot be created makes a save answer 500 with the operating system message and leaves the file unchanged. The update flag and its expiry belong to a file: the status reports the flag of the file currently served; `open_file` leaves the previous file's flag as it was (it still expires by itself); `update_start` and `update_end` act on the file currently served. The state directory also holds one record naming the file most recently served or opened by any process; a process that has served no file itself uses that record's file for `update_start`, `update_end` and `get_status`, and a process that has served a file uses its own.

## Independent Test

`make check`: `tests/test_state.py` passes, including E2E-005, 020, 021, 024, 025. By hand: start the server on a
copy of a deck in an empty folder, call `update_start`; the folder holds only the deck.

## Design excerpt

### Decisions

- DEC-005 (SPEC-0009): `state_dir` is a `Settings` property fed by two new override fields (`HTMLEDITOR_STATE_DIR`, `XDG_STATE_HOME`), both added to `_PATH_FIELDS` and to `_SIGNIFICANT_ENV_VARS`; no home falls back to `<tmp>/mcp-htmleditor-<uid>`. Rationale: the memoization keys on the listed variables, so a missing name would serve a stale state dir. No `os.environ` reads (constitution).
- DEC-006 (SPEC-0009): State is one directory per file keyed by `sha256(resolved absolute path)[:32]`, with `server.json` and `update.json` as separate files and a `last.json` record. Each writer owns whole files written atomically, so processes never clobber each other's fields.
- DEC-007 (SPEC-0009): The update flag stores `started_at`; `update_in_progress` and `update_expires_in` are computed on read from the injected `EditorState.clock`; elapsed is clamped to at least 0.
- DEC-008 (SPEC-0009): A process with no file of its own resolves the file from `last.json` for `update_start`, `update_end` and `get_status`, and reads port and pid from that file's `server.json`; `open_file` and `set_file` write `last.json`.
- DEC-009 (SPEC-0009): `set_update_flag(value)` stays as a thin wrapper over `start_update` / `end_update` (SPEC-0007's `patch` may call it).
- DEC-022 (SPEC-0009): A failure to write the state records in `set_file` or `save` is logged and does not stop the server; it surfaces at the first save as a 500 (later story).
- DEC-023 (SPEC-0009): this story keeps FR-NEW-006 and FR-NEW-008 together, 6 files, min_tier 3.
- Clock: injected callable `EditorState.clock: Callable[[], float]` (default `time.time`); tests assign a `FakeClock` to `get_state().clock`. No global patch of `time.time`.

### Data model

```
<state_dir>/
  last.json                        {"file": "<absolute path>"}                  file most recently served or opened by any process
  files/<key>/                     key = sha256(absolute resolved path, UTF-8).hexdigest()[:32]
    server.json                    {"file","port","pid","poll_interval"}         written by serve / start_server / stop
    update.json                    {"file","started_at": <epoch seconds float>}  written by update_start; removed by update_end
```

State directory resolution: `HTMLEDITOR_STATE_DIR`, else `$XDG_STATE_HOME/mcp-htmleditor`, else
`~/.local/state/mcp-htmleditor`, else (`Path.home()` raises `RuntimeError`) `<tempfile.gettempdir()>/mcp-htmleditor-<os.getuid()>`.
Directories are created with mode 0700 on first write. `update.json`: in progress means `0 <= now - started_at < 120`;
`update_expires_in = ceil(120 - max(0, now - started_at))` (1 to 120); at 120 seconds exactly the flag is cleared; an
expired record is left in place and ignored. Constant at module level: `UPDATE_TTL_SECONDS = 120.0`. A process with
neither its own file nor `last.json` holds the flag in memory.

### Contracts

```python
# state.py (EditorState, same singleton, same file name)
clock: Callable[[], float]
def start_update(self) -> int                                # returns 120
def end_update(self) -> None
def set_update_flag(self, value: bool) -> None               # compat wrapper, calls the two above
update_in_progress: property[bool]; update_expires_in: property[int | None]
def snapshot(self) -> dict[str, Any]                         # file, port, pid, update_in_progress, update_expires_in, mtime
save_lock: threading.Lock                                    # serializes browser saves (used by a later story)
```

- `update_start` tool returns `{"ok": true, "expires_in": 120}`; `update_end` returns `{"ok": true}`.
- `get_status` returns `file, port, pid, update_in_progress, update_expires_in, mtime, running`.
- `GET /status` gains `update_expires_in` (int or `null`).
- `config.py`: fields `state_dir_override`, `xdg_state_home_override`, property `state_dir`, accessor `state_dir()`; `HTMLEDITOR_STATE_DIR` and `XDG_STATE_HOME` added to `_SIGNIFICANT_ENV_VARS` and `_PATH_FIELDS` entries; docstring `config.py:12` (says state is next to the file) corrected.
- `tests/conftest.py`: autouse fixture `isolate_state_dir` pointing `HTMLEDITOR_STATE_DIR` at a per test temporary directory.
- Unit tests to add (not E2E): state dir resolution (override, XDG, home, no home); record round trip; expiry clamp (negative elapsed); unbound in memory flag.

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/config.py` | edit |
| `src/mcp_htmleditor/state.py` | edit (rewrite persistence) |
| `src/mcp_htmleditor/mcp_server.py` | edit `update_start`, `update_end`, `get_status` |
| `src/mcp_htmleditor/http_server.py` | edit `_serve_status` |
| `tests/conftest.py` | edit (autouse `isolate_state_dir`) |
| `tests/test_state.py` | edit three tests, add new tests |

Existing tests: modify `test_set_file_resolves_and_persists` (assert `server.json` under the state dir and no file next to the HTML), `test_set_update_flag_persists` (use `start_update` / `end_update`, assert `update.json` and the property), `test_load_corrupt_file_is_ignored` (corrupt `server.json` instead). Keep `test_save_then_load_roundtrip`, `test_load_missing_file_is_noop`, `test_defaults`, `test_singleton_*`, `test_get_mtime_*`.

### Existing patterns

- Settings path fields (`src/mcp_htmleditor/config.py:45-55`), literal:
```python
_PATH_FIELDS = (
    "templates_dir_override",
    "arch_checks_dir_override",
    "logs_override",
    "log_dir_override",
    "cache_dir_override",
    "bin_dir_override",
    "xdg_config_home_override",
    "xdg_cache_home_override",
)
```
- Tool with span (`src/mcp_htmleditor/mcp_server.py`, `get_status`), literal:
```python
@mcp.tool()
def get_status() -> dict[str, Any]:
    state = get_state()
    with trace_span("mcp.get_status", {"server.running": is_server_running()}):
        return {
            "file": state.current_file,
            "port": state.port,
            "pid": state.server_pid,
            "update_in_progress": state.update_in_progress,
            "mtime": state.get_mtime(),
            "running": is_server_running(),
        }
```
- Status payload (`src/mcp_htmleditor/http_server.py`, `_serve_status`), literal:
```python
payload: dict[str, Any] = {
    "mtime": state.get_mtime(),
    "update_in_progress": state.update_in_progress,
    "filename": state.current_file,
    "poll_interval": state.poll_interval,
    "port": state.port,
}
self._send_json(payload)
```
- Test fixtures (`tests/conftest.py`), literal: `fresh_state(reset_state)` returns `state_module.get_state()`; `html_file(tmp_path)` writes `tmp_path / "doc.html"`; `reset_settings` is autouse and calls `config_module.reset_settings_cache()` around each test.
- Test style (`tests/test_state.py`), literal:
```python
def test_set_file_resolves_and_persists(fresh_state: EditorState, html_file: Path) -> None:
    fresh_state.set_file(str(html_file))
    assert fresh_state.current_file == str(html_file.resolve())
```

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures: DECK is an Euro-Information presentation `deck.html` of 8 slides, served by the editor. `mtime` is the value returned by the status for DECK. `FakeClock` has `advance(seconds)` and is assigned to `get_state().clock`.

### SPEC-0009/E2E-005: Status with expiry
- Level tool; Driver `fastmcp.Client` in process, `FakeClock`; Location `tests/test_state.py`
- Given DECK, `update_start` called at time T
- When `get_status` is called 30 seconds after T
- Then `update_in_progress` is true and `update_expires_in` is 90
- And `update_start` had answered `{"ok":true,"expires_in":120}`

### SPEC-0009/E2E-020: Expiry
- Level tool; Driver `fastmcp.Client`, `FakeClock` at 121 s; Location `tests/test_state.py`
- Given `update_start` called at time T and nothing else
- When `get_status` is called at T + 121 seconds
- Then `update_in_progress` is false and `update_expires_in` is null

### SPEC-0009/E2E-021: Renewal
- Level tool; Driver `fastmcp.Client`, `FakeClock`, restart at 100 s; Location `tests/test_state.py`
- Given `update_start` at T and again at T + 100 seconds
- When `get_status` is called at T + 150 seconds
- Then `update_in_progress` is true and `update_expires_in` is 70
- And after `update_end`, `get_status` shows false and null

### SPEC-0009/E2E-024: No state file next to the user's file
- Level HTTP + tool; Driver real server plus folder listing; Location `tests/test_state.py`
- Given an empty folder with DECK
- When the server starts on DECK and the agent calls `update_start`
- Then the folder holds only DECK

### SPEC-0009/E2E-025: State shared between processes
- Level tool, two processes; Driver `subprocess.run([sys.executable, "-c", script])` with `HTMLEDITOR_STATE_DIR` and `PYTHONPATH=src`, the script calls `update_start` through `fastmcp.Client`; Location `tests/test_state.py`
- Given a server process on DECK and `update_start` called through a separate tool process
- When `get_status` is called through the server process
- Then it reports `update_in_progress` true and an `update_expires_in` between 1 and 120

## Constraints

- Files not to touch: `src/mcp_htmleditor/fileio.py`, the save path in `http_server.py` (`_receive_content`), `static/*`.
- Dependencies not to add: none.
- No `os.environ` reads; configuration only through `Settings`.
- No test may write into the real `~/.local/state` (the autouse fixture enforces it).
- Scope boundary: no deployment file or README change here (closing story).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_state.py` unchanged tests (`test_save_then_load_roundtrip`, `test_load_missing_file_is_noop`, `test_defaults`, `test_singleton_*`, `test_get_mtime_*`), `tests/test_settings.py`, `tests/test_config.py`, `tests/test_http_health.py`, `tests/test_autosave_focus_e2e.py`; the three modified tests assert the new state files (`server.json`, `update.json`) instead of `.mcp_state.json`, per design section 6.
- [ ] Docs updated: none in this story (README, AGENTS.md, `.agent_docs/*`, Dockerfile, `.env.example` are updated by US-0051, design DEC-019).
- [ ] Self review (tier 3): (1) Does any code path still create `.mcp_state.json` or any file next to the user's file? (2) Is `update_expires_in` always in 1 to 120 while in progress, including under a negative elapsed? (3) Does every new env name appear in both `_PATH_FIELDS` and `_SIGNIFICANT_ENV_VARS`? (4) Does `set_update_flag` still work for a caller that has not been changed? (5) Does the autouse fixture keep every other test off the real state directory?
- [ ] If the story registers an MCP tool: not applicable (no new tool).
- [ ] One commit `US-0047: State per file in the state directory, expiring update flag`, body `Spec: SPEC-0009` and `FR-NEW-006, FR-NEW-008`.
