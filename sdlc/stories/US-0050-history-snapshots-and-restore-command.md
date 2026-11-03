# US-0050: History snapshots, `history` and `restore` commands

> Spec: SPEC-0009 (sdlc/specs/SPEC-0009-reliable-saves/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0048, US-0049
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Keep the previous content of a file in a history before a browser save overwrites it, and add the CLI commands
`history` and `restore`. The `reason` and `history` keywords of `atomic_write` arrive here.

## Requirements covered

- SPEC-0009/FR-NEW-004 (partial: browser save and restore; `patch` is US-0051): WHEN a browser save, a `patch` or a `restore` is about to change a file's bytes THE Editor SHALL first keep the previous content in the history.
- SPEC-0009/FR-NEW-005 (partial: the command line; the tools are US-0051): WHEN a user runs `mcp-htmleditor history <file>` or `mcp-htmleditor restore <file> <id>` THE Editor SHALL list the versions or put the chosen version back.

Business rules FR-NEW-004: nothing is kept when the new bytes equal the current bytes. At most the 20 newest versions of a file are kept. Identical content: when `base_mtime` is current the answer is `{"ok":true,"mtime":<unchanged mtime>}`, the file is not rewritten and no version is added; with a stale `base_mtime` the save is a 409 conflict whatever the content; equal bytes means the bytes the server would write after its HTML cleaning. A browser save carrying `force` true is recorded with reason `keep-mine`, whether or not a conflict existed; any other browser save is `browser-save`. A version is `{id, bytes, reason}` with `reason` one of `browser-save`, `keep-mine`, `patch`, `restore`. The id is the server's UTC time `YYYYMMDDTHHMMSS` followed by `Z`; when the id already exists for that file the suffix `-2`, `-3`, ... (decimal, no padding) is added. The version is kept only if the write then succeeds, so a failed write leaves the history unchanged. `bytes` is the UTF-8 byte count of the stored content. The cap of 20 is per absolute file path and drops the oldest by creation order. The history is stored in the state directory, not next to the file.

Business rules FR-NEW-005 (command line part): the commands resolve `<file>` to an absolute path (the current directory for the command line) and need no running server. Newest first means reverse order of creation. `history` prints one line per version, newest first: `<id>  <bytes> bytes  <reason>` (two spaces between columns), or `No history for <file>` with exit status 0. `restore` checks, in this order, template, file not found, unknown id (each an error); `history` on a template path is allowed and checks only that the file exists. `restore` keeps the current content in the history first (reason `restore`), writes the chosen content, and prints `Restored <file> to <id>`. `restore` to content equal to the current file changes nothing, adds no version, prints the same line and exits 0. `restore` skips the conflict check; an open browser sees the new `mtime` as an external change. `restore` on a template path fails with `error: Refusing to modify a template: <file>` (exit status 1). A `restore` write failure prints `error: <operating system message>` (exit status 1), leaving file and history unchanged; `<file>` in messages is as typed. User visible text: `error: Unknown history id "x". Valid ids: 20261103T101500Z, 20261103T101200Z` (`Valid ids: none` when empty); `error: File not found: <file>` (exit status 1 each).

## Independent Test

`make check`: `tests/test_history_e2e.py` passes. By hand: save twice from the browser, run
`mcp-htmleditor history deck.html` (two lines), then `mcp-htmleditor restore deck.html <oldest id>`.

## Design excerpt

### Decisions

- DEC-001 (SPEC-0009): `atomic_write` takes `reason` and an optional `history`; with a reason it stages the snapshot inside the write transaction and returns `False` without writing on equal bytes. One place enforces "kept only if the write succeeds" and "nothing kept when equal".
- DEC-002 (SPEC-0009): Versions are files named `<id>.<reason>.html`, no index; `bytes` is the file size; order by (timestamp, numeric suffix), so `-10` sorts after `-9`.
- DEC-003 (SPEC-0009): Order inside `atomic_write`: read old bytes, create the temp file, write and fsync, stage the snapshot, replace, then prune; on any failure after staging, discard the staged version and remove the temp file. Pruning only after success keeps a full history intact when a write fails at the cap.
- DEC-016 (SPEC-0009): CLI errors are printed by `click.echo("error: ...", err=True)` followed by `ctx.exit(1)` (`ClickException` prints `Error:`).
- DEC-021 (SPEC-0009): Error text is `exc.strerror or str(exc)`.
- Clock: `HistoryStore(root, clock)` drives ids; tests assign `FakeClock` to `get_state().clock`.

### Data model

```
<state_dir>/files/<key>/history/<id>.<reason>.html     the previous content, bytes verbatim
```

Version id: `strftime("%Y%m%dT%H%M%S", gmtime(clock()))` plus `Z`; suffix `-2`, `-3`, ... when taken. Reasons: `browser-save`, `keep-mine`, `patch`, `restore`. `Version(id: str, bytes: int, reason: str)` frozen, `slots=True`. Retention `HISTORY_LIMIT = 20`, deleted after a successful write. Versions are staged by writing a hidden temp file in `history/` then `os.replace` onto the final name; hidden temp files are ignored by listing.

### Contracts

```python
# fileio.py
def atomic_write(path: str | Path, data: bytes | str, *, reason: str | None = None,
                 history: HistoryStore | None = None) -> bool
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
```

- `http_server._receive_content`: `atomic_write(target, html, reason="keep-mine" if force else "browser-save")`.
- `reason=None` keeps the story US-0048 behaviour exactly (no snapshot).
- `history <file>`: lines `f"{v.id}  {v.bytes} bytes  {v.reason}"` newest first, or `No history for <file>`; exit 0. Only the file's existence is checked (templates allowed).
- `restore <file> <id>`: prints `Restored <file> to <id>`. Errors to stderr as `error: <message>`, exit 1. Messages, `<file>` as typed: `File not found: <file>`; `Unknown history id "<id>". Valid ids: <id1>, <id2>` (`Valid ids: none`); `Refusing to modify a template: <file>`; write failure: the strerror.
- Both resolve with `Path(file).resolve()`.
- Unit tests to add: `HistoryStore` ids with suffixes (`-2` to `-21`, order `-10` after `-9`), prune, discard; `atomic_write` with reason (equal bytes returns False and adds nothing, failed replace discards the staged version).

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/history.py` | create |
| `src/mcp_htmleditor/fileio.py` | edit: `reason`, `history`, snapshot inside the transaction, span `history.snapshot` |
| `src/mcp_htmleditor/http_server.py` | edit: pass the reason on browser save |
| `src/mcp_htmleditor/cli.py` | edit: `history`, `restore` |
| `tests/test_history_e2e.py` | create |

### Existing patterns

- CLI tests with `click.testing.CliRunner` (stderr separate in Click 8.2+); CLI errors elsewhere in `src/mcp_htmleditor/cli.py` (`:88`, `ClickException`, which is not reused).
- Real server and raw HTTP, `served_deck`, `FakeClock`, `needs_chromium` from `tests/conftest.py` (US-0048); seam `monkeypatch.setattr(fileio, "replace_file", raiser)`.
- `trace_span` on mutations (`history.snapshot`, `history.restore`), logs `%` style, nothing on stdout in the MCP process.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures: DECK is an Euro-Information presentation `deck.html` of 8 slides, served by the editor. "Saved copy" means the exact bytes before the step. Saves at different seconds use `FakeClock`.

### SPEC-0009/E2E-003: History after two saves
- Level CLI; Driver two saves then `history`; Location `tests/test_history_e2e.py`
- Given DECK, two browser saves at different seconds
- When the user runs `mcp-htmleditor history deck.html`
- Then the output has two lines of the shape `<id>  <bytes> bytes  browser-save`, newest first, and the bytes of the older line equal the size of DECK before the first save

### SPEC-0009/E2E-004: Restore
- Level CLI; Driver `restore` then `history`; Location `tests/test_history_e2e.py`
- Given DECK saved twice (history ids A newest, B oldest), saved copy of the current file kept
- When the user runs `mcp-htmleditor restore deck.html B`
- Then the output is `Restored deck.html to B` and the file equals the content kept as version B
- And `history` now lists a first line with reason `restore` whose bytes equal the saved copy size

### SPEC-0009/E2E-009: Keep mine
- Level browser + CLI; Driver Playwright Keep mine, then `history`; Location `tests/test_history_e2e.py`
- Given the situation of E2E-008 (the editor open on DECK; the agent writes a new title; the user types an edit; the autosave shows the conflict message)
- When the user clicks `Keep mine`
- Then the file holds the browser's version and the agent's version is in the history with reason `keep-mine`
- And the message disappears

### SPEC-0009/E2E-015: Unknown history id
- Level CLI; Driver unknown id; Location `tests/test_history_e2e.py`
- Given DECK saved twice (ids A newest and B oldest)
- When the user runs `restore deck.html nope`
- Then the error output is `error: Unknown history id "nope". Valid ids: A, B` (with the real ids), exit status 1, the file unchanged

### SPEC-0009/E2E-016: No history
- Level CLI; Driver never saved file; Location `tests/test_history_e2e.py`
- Given DECK never saved through the product
- When the user runs `history deck.html`
- Then the output is `No history for deck.html` and the exit status is 0
- And `restore deck.html x` prints `error: Unknown history id "x". Valid ids: none`

### SPEC-0009/E2E-019: Missing file for history
- Level CLI; Driver ghost file, template restore; Location `tests/test_history_e2e.py`
- Given no file `ghost.html`
- When the user runs `history ghost.html` and `restore ghost.html x`
- Then both print `error: File not found: ghost.html`, exit status 1
- And `restore templates/bootstrap/x.html y` prints `error: Refusing to modify a template: templates/bootstrap/x.html`, exit status 1

### SPEC-0009/E2E-022: Twenty versions
- Level HTTP + CLI; Driver 21 saves then `history`; Location `tests/test_history_e2e.py`
- Given DECK saved 21 times with different content
- When the user runs `history deck.html`
- Then the output has exactly 20 lines and the first save's previous content is not among them

### SPEC-0009/E2E-023: Identical save
- Level HTTP + CLI; Driver identical save; Location `tests/test_history_e2e.py`
- Given DECK, a save of the file's exact current content with `base_mtime` current
- When the browser sends it
- Then the answer is `{"ok":true,"mtime":<mtime>}` and `history` lists no new version

### SPEC-0009/E2E-031: Failed write keeps the history unchanged
- Level HTTP + CLI; Driver `replace_file` seam, history unchanged; Location `tests/test_history_e2e.py`
- Given DECK with 2 versions in the history and the write made to fail
- When the browser saves different content
- Then the answer is status 500 and `history deck.html` still lists exactly the same 2 versions

## Constraints

- Files not to touch: `static/*` (E2E-009 uses the UI from US-0049), `mcp_server.py`, `state.py`.
- Dependencies not to add: none.
- Patterns to avoid: a history index file; snapshotting after the replace; printing `Error:` through `ClickException`.
- `patch` snapshots and the tools are US-0051; no change to SPEC-0007's `patch.py` here.
- Scope boundary: nothing is cleaned for deleted files.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: all of `tests/test_save_safety_e2e.py` (US-0048), `tests/test_save_ui_e2e.py` (US-0049), `tests/test_state.py` (state files `server.json`, `update.json`), `tests/test_autosave_focus_e2e.py`, `tests/test_http_origin_e2e.py`; SPEC-0007 `atomic_write` callers with no `reason` keep writing without a snapshot.
- [ ] Docs updated: none in this story (US-0051 carries them, DEC-019).
- [ ] Self review: full (snapshot only after a successful write, ids and order, cap of 20, error wording and exit codes, no scope creep).
- [ ] If the story registers an MCP tool: not applicable (the tools are US-0051).
- [ ] One commit `US-0050: History snapshots, history and restore commands`, body `Spec: SPEC-0009` and `FR-NEW-004, FR-NEW-005`.
