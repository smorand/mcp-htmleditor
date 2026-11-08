# US-0100: Lock the pandoc and server record arbitrations

> Spec: SPEC-0016 (sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/)
> Nature: BUG
> Priority: P3
> Depends on: main
> min_tier: 2
> Files touched: 1
> Closes spec: no

## Objective

The spec withdraws two legacy promises (a DOCX export without pandoc falling back to default styles; a server
reloading its earlier record) and keeps today's code. This story locks that behavior with end to end tests, so a later
change cannot silently swallow a missing pandoc or adopt a dead process's port. No product code changes.

## Requirements covered

- SPEC-0016/BR-018: IF `pandoc` is not found on `PATH` THEN `mcp-htmleditor export docx <in> <out>` SHALL print `error: pandoc not found in PATH: install pandoc to export to DOCX.` on stderr, exit with status 1, and leave no file at `<out>`.
- SPEC-0016/BR-019: The editor SHALL NOT take the port, process id or poll interval of a server it starts from a server record written by another process.
- SPEC-0016/BR-020: WHILE a process serves no file THE agent tool `get_status()` SHALL report the `port` and `pid` recorded for the file named by the state directory's `last.json`, when that record is readable.

Business rules (spec, verbatim, BR-019): "the port is the explicit `--port` or `port`, else the first free one of
SPEC-0001/FR-029 from `HTMLEDITOR_PORT`; the poll interval is `--poll`, else `HTMLEDITOR_POLL_INTERVAL`, else 1000."

## Independent Test

`make test ARGS='-k legacy_arbitrations'`: both tests green on today's code; each red under its recorded mutation.

## Design excerpt

### Decisions
- DEC-012 (SPEC-0016): "BR-018 to BR-020 are locked by tests only, no product change: BT-022 runs `[sys.executable, \"-m\", \"mcp_htmleditor\", \"export\", \"docx\", ...]` with `PATH` set to an empty `tmp_path` directory; BT-023 writes `<state_dir>/files/<key>/server.json` with `key = sha256(resolved path).hexdigest()[:32]` (`state.py:9`), starts `serve D --no-browser` as a child with `HTMLEDITOR_PORT=P`, polls `GET /status` through `wait_until`, then runs an MCP stdio session (`tests/stdio_support.py` `run_session`) calling `get_status`. RED evidence is a temporary mutation (a `EditorState.load()` call at server start, or the pandoc check bypassed), run once, logged, reverted."

### Contracts (existing, read only)
- `src/mcp_htmleditor/deck/tools.py:22` `PANDOC_MISSING_MESSAGE`; CLI prints `error: <message>` and exits 1.
- `src/mcp_htmleditor/state.py:4` to `:8` layout: `<state_dir>/last.json` `{"file"}`, `<state_dir>/files/<key>/server.json` `{"file","port","pid","poll_interval"}`; `:203` to `:219` `snapshot` reads the recorded port and pid when nothing is served.
- `src/mcp_htmleditor/http_server.py:438` to `:450` `GET /status` returns `port` and `poll_interval`.
- Environment for every child: `HTMLEDITOR_STATE_DIR` under `tmp_path`, `HTMLEDITOR_TEMPLATES_DIR` the repository's `templates/`, `HTMLEDITOR_HOST=127.0.0.1`.

### Paths
| Path | Action |
|---|---|
| `tests/test_legacy_arbitrations.py` | create: BT-022, BT-023 |

### Existing patterns
- Child process CLI: `tests/test_skill_shipped.py`; MCP stdio: `tests/stdio_support.py` (`mcp_command`, `tool_request`, `run_session`).
- Free port and server child lifecycle with cleanup: `tests/test_server_lifecycle.py`.
- Bounded polling: `tests/browser_wait.py` `wait_until` (no `time.sleep` loop without bound).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Location `tests/test_legacy_arbitrations.py`.

### SPEC-0016/BT-022: DOCX export without pandoc
- Level / Driver: functional; child process, `PATH` an empty directory
- Given the `doc` bootstrap (`templates/bootstrap/document-empty.html`) copied to `tmp_path/doc.html`
- When `[sys.executable, "-m", "mcp_htmleditor", "export", "docx", doc.html, doc.docx]` runs with `PATH=<empty dir>`
- Then exit status 1, stderr (stripped) is `error: pandoc not found in PATH: install pandoc to export to DOCX.`, and `doc.docx` does not exist
- RED evidence: with the pandoc lookup temporarily bypassed the test fails (status not 1); mutation reverted.

### SPEC-0016/BT-023: A stale server record is not adopted
- Level / Driver: functional; `serve` child process, HTTP `GET /status`, MCP stdio `get_status`
- Given `HTMLEDITOR_PORT=P` (a free port), a deck `D` (Carbon bootstrap copy), and `<state_dir>/files/<key of D>/server.json` holding `{"file": "<D>", "port": 7845, "pid": 999999, "poll_interval": 5000}` written before any process starts
- When `[sys.executable, "-m", "mcp_htmleditor", "serve", D, "--no-browser"]` runs (no `--port`, no `--poll`)
- Then `GET /status` on `P` answers `"port": P` and `"poll_interval": 1000`
- Given a new `mcp-htmleditor mcp` process serving nothing, and `last.json` naming `D` while the `serve` above runs
- When `get_status()` is called
- Then it reports `"running": false`, `"port": P` and the `serve` process's `pid` (`Popen.pid`)
- Cleanup: terminate the `serve` child, wait with a bound
- RED evidence: with `EditorState.load()` temporarily called at server start the first half fails (`poll_interval` 5000 or port 7845); mutation reverted.

## Constraints

- Files not to touch: every file under `src/` (lock tests only), `tests/test_state.py` (its `load()` tests stay, BL-0009).
- Dependencies not to add: none.
- Patterns to avoid: an unbounded wait for the server; a hard coded port.
- Scope boundary: deleting `EditorState.load()` is BL-0009, not this story.

## Definition of done

- [ ] RED evidence by mutation recorded for BT-022 and BT-023 in `.implement/US-0100-red.log`, mutations reverted (diff limited to the test file).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_deck_tools.py` pandoc test and `tests/test_export_docx.py::test_reference_docx_for_swallows_a_missing_pandoc` unchanged.
- [ ] Durations reported (two child process tests, a few seconds).
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0100: Lock the pandoc and server record arbitrations`, body `Spec: SPEC-0016` and BR-018, BR-019, BR-020.
