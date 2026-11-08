# US-0113: State loader and serve poll cleanup

> Spec: SPEC-0019 (sdlc/specs/SPEC-0019-code-and-test-debts/)
> Nature: DEBT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

`EditorState.load()` has no caller and offers a restore that SPEC-0016 forbids; `serve --poll` writes `os.environ`, a second configuration channel that changes nothing observable. This story removes both, replaces the dead loader tests by one test on the live reader, and pins the `--poll` contract with its first tests.

## Requirements covered

- SPEC-0019/DR-001: `src/mcp_htmleditor/state.py` SHALL NOT define a method `load` on `EditorState`.
- SPEC-0019/DR-002: No module under `src/mcp_htmleditor/` other than `config.py` SHALL contain `os.environ`, `os.putenv` or `os.getenv`.
- SPEC-0019/DR-007: WHEN `serve FILE --poll N` starts THE CLI SHALL serve `/status` with `poll_interval` equal to `N`, and SHALL leave `os.environ` without `HTMLEDITOR_POLL_INTERVAL` when it was absent before.
- SPEC-0019/DR-006 (partial: this story's edits): The system SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, the undo snapshot string and the HTML posted by a save included; the only text change is the sentence of DR-005 in the `slides-carbon` topic output.

## Independent Test

`make test ARGS='-k "state_record or serve_poll or test_state"'`: DT-002, DT-003, DT-010 red before, green after; DT-001, DT-011 green before and after; the remaining `tests/test_state.py` tests green. `rg -n "environ|getenv|putenv" src/mcp_htmleditor --glob '!config.py'` returns only docstring words (no `os.` access). `make check` green.

## Design excerpt

### Decisions

- DEC-001 (SPEC-0019): Remove `load()` rather than wire it: no caller, and calling it at server start would reverse the SPEC-0016 arbitration locked by `tests/test_legacy_arbitrations.py:146`.
- DEC-002 (SPEC-0019): Replace the four `load()` tests by one `snapshot()` test (DT-001): keep what they proved about live code (a corrupt `server.json` never raises, SPEC-0001 E2E-007), add no behavior.
- DEC-010 (SPEC-0019): new test files follow SPEC-0018 DT-010 and DT-012 (no removed skill paths; comment pointers name the defining script).

### Contracts

- `_serve_file(file, port, poll, host, open_browser=...)` in `src/mcp_htmleditor/cli.py` (internal; called by `serve` at `cli.py:191` and by `new --serve`): keeps `state.poll_interval = poll` (`cli.py:224-226`), loses the `os.environ` write.
- `serve --poll N` (public): `/status` `poll_interval` (`http_server.py:446`) equals `N`.
- `HTMLEDITOR_POLL_INTERVAL`: read only through `Settings` (`config.default_poll_interval()`, `config.py:357-359`).

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/state.py` | remove `load()` (`:165-173`) |
| `src/mcp_htmleditor/cli.py` | remove `:220-221`; remove `import os` (`:14`) when `rg -n "\bos\." src/mcp_htmleditor/cli.py` is empty after it |
| `tests/test_state.py` | remove `test_save_then_load_roundtrip` (`:160`), `test_load_missing_file_is_noop` (`:179`), `test_load_corrupt_file_is_ignored` (`:187`), `test_load_ignores_wrongly_typed_values` (`:459`) |
| `tests/test_state_record.py` | create: DT-001, DT-002 |
| `tests/test_serve_poll.py` | create: DT-003, DT-010, DT-011 |

### Existing patterns

- State fixtures: `tests/conftest.py:101` (`fresh_state`), `html_file`; round trip test `tests/test_state.py:346`; corrupt records through `snapshot()` `tests/test_state.py:379` (`test_corrupt_records_are_ignored`).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0019/DT-001: A corrupt server record never raises (live reader)
- Level / Driver / Location: integration / in process / `tests/test_state_record.py`
- Given `fresh_state.set_file(html_file)`, `port = 6001` saved, then `server.json` overwritten with `{ not valid json`, then `EditorState._instance = None` and a new `EditorState()`
- When `snapshot()` is called
- Then it returns `file == str(html_file.resolve())`, `port == config.default_port()`, `pid is None`, without raising. Green before and after.

### SPEC-0019/DT-002: No `load` method
- Then `not hasattr(EditorState, "load")`. Location `tests/test_state_record.py`.
- Red before the fix because: `EditorState.load` exists.

### SPEC-0019/DT-003: No environment access outside config
- Level / Location: structural / `tests/test_serve_poll.py`
- Then no file `src/mcp_htmleditor/**/*.py` other than `config.py` contains `os.environ`, `os.putenv` or `os.getenv`.
- Red before the fix because: `cli.py:221`.

### SPEC-0019/DT-010: `serve --poll` sets the served interval without the environment
- Level / Driver / Location: integration / `_serve_file` with doubles / `tests/test_serve_poll.py`
- Given `HTMLEDITOR_POLL_INTERVAL` absent (`monkeypatch.delenv(..., raising=False)`), the `fresh_state` fixture, `mcp_htmleditor.http_server.start_http_server` replaced by a function returning `(True, 7999)`, `mcp_htmleditor.http_server.stop_http_server` by a no op, `time.sleep` by a function raising `KeyboardInterrupt`
- When `_serve_file(str(html_file), None, 250, "127.0.0.1", open_browser=False)` runs
- Then `get_state().poll_interval == 250`, `"HTMLEDITOR_POLL_INTERVAL" not in os.environ`, `config.get_settings().poll_interval == 1000`
- Red before the fix because: `os.environ["HTMLEDITOR_POLL_INTERVAL"] == "250"` after the call.

### SPEC-0019/DT-011: Without `--poll` the interval comes from Settings
- Given `HTMLEDITOR_POLL_INTERVAL=400` (`monkeypatch.setenv`), then `EditorState._instance = None` after the variable is set, the same doubles
- When `_serve_file(..., None, None, ...)`
- Then `get_state().poll_interval == 400` and the variable still reads `"400"`. Green before and after.

## Constraints

- Files not to touch: `tests/test_legacy_arbitrations.py`, any test other than the four removals, `.agent_docs/testing.md` (rows belong to US-0115, DEC-009).
- No new `os.environ` access in tests outside `monkeypatch`.
- Patch the doubles where `_serve_file` looks them up (read `cli.py` imports first).
- Dependencies not to add: any. Scope boundary: the editor strip is US-0114.

## Definition of done

- [ ] RED evidence recorded for DT-002, DT-003, DT-010 before the production change.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_legacy_arbitrations.py`, the rest of `tests/test_state.py` green; `serve` help text unchanged.
- [ ] DEBT: the existing suite passes unmodified, exceptions: 4 removed tests of `tests/test_state.py` (`:160`, `:179`, `:187`, `:459`).
- [ ] Docs updated: none in this story (test file map in US-0115).
- [ ] Self review: full.
- [ ] One commit `US-0113: State loader and serve poll cleanup`, body `Spec: SPEC-0019` and `DR-001, DR-002, DR-006, DR-007`.
