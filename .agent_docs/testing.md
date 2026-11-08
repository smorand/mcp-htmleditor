# Tests

```bash
make test                 # pytest -v
make test ARGS='-k pptx'  # subset
make test-cov             # coverage, gate 80 %
make test ARGS='-m slow'  # the slow marker, selected on request only (about 8 minutes)
```

### Time limits and the slow marker (2026-11, SPEC-0013, SPEC-0014)

`pyproject.toml` registers `slow` and sets `addopts = "-m 'not slow'"`: `make test`, `make test-cov` and `make check`
deselect it, `ARGS='-m slow'` wins (the last `-m` is kept). No Makefile target. Slow tests check the literal values:
`test_http_time_bounds_slow.py` (30 s, 50 s, 5 min HTTP bounds), `test_suite_time_limit.py` (BT-016, 60 s / 900 s) and
`test_stdio_support.py` (BT-003, BT-017, 30 s): `make test ARGS='-m slow -k "suite_time_limit or stdio_support"'`.
The default tests carry short counterparts so the gate stays under 330 s (DEC-009): `test_http_time_bounds.py`
shortens `http_deadline.WAIT_SECONDS` (1.0) and `TOTAL_SECONDS` (4.0) with `monkeypatch.setattr` (read through the module
at each use, a test seam, not a setting); `DeadlineReader` takes a fake `clock`. Under load such a test needs a margin
relative to the shortened bound, not an absolute one (`CLOSE_MARGIN`, 10 s: a 27 MB export took 5.5 s at load average 22).
Raw socket helpers: `http_support.py`; tracing capture helpers: `trace_support.py`.

Every test is bounded by `pytest-timeout`: `timeout = 60`, `timeout_method = "signal"` (the thread method would end the
whole process and name nothing). An overrun fails alone with `Timeout (>60.0s) from pytest-timeout.` and its node id.
`tests/conftest.py` adds `pytest.mark.timeout(900)` (`SLOW_TEST_TIMEOUT_SECONDS`) to each `slow` test through
`pytest_collection_modifyitems`. `test_suite_time_limit.py` runs child pytests on throwaway files: they need
`-c pyproject.toml --rootdir <repo> -p tests.conftest -p no:cacheprovider`, cwd at the repository root, a `timeout=`,
`--confcutdir` at the throwaway folder and an own `--basetemp` (without them collection walks `$TMPDIR`, 5 to 35 s).
Judge a timed out child on its JUnit call time, never on wall time. `pytest-timeout>=2.4.0`: 2.5.0 is yanked on PyPI.

### Browser waits and the pacing rule (2026-11, SPEC-0014 BR-008 to BR-011, BR-014, DEC-010 to DEC-014)

A browser test never asserts an asynchronous result (file after an autosave, status dot, DOM after an insert, a reload)
after a fixed delay. `tests/browser_wait.py`: `wait_until(page, observe, holds, what=...)` observes first, pauses
`page.wait_for_timeout(100)` between observations, up to 10 s from the call, and fails with `<what> not reached within
10 s, last value: <repr>`; `wait_for_file` and `wait_for_js` are the two shapes in use. Never `time.sleep` in it: in the
sync Playwright API route handlers and events run only inside a Playwright call. An absence is asserted after
`wait_until` on the step that could cause it, then `settle(page)` (1 s), then the assertion.

Pacing rule: a `wait_for_timeout(` left in a `tests/test_*_e2e.py` carries a trailing `# pacing: <reason>` (a spacing
between two user actions, no result asserted after it). `tests/test_no_fixed_waits.py` enforces it
(`unjustified_waits(path)` returns the line numbers, one parametrized case per browser file, no allow list); the settle
delay lives only in `browser_wait.py`. Check: `rg -n 'wait_for_timeout\(' tests | rg -v '# pacing:' | rg -v browser_wait.py`.

Late saves: `answer_saves_late(page, 2000)` is an init script holding every `POST /content` 2 s before it leaves; call it
before `page.goto`. `test_autosave_focus_e2e.py` has a `save_delay` fixture (`prompt`, `late`). Do NOT use a route
handler (measured 2026-11-06): a handler that waits blocks the sync dispatcher and stretches every `wait_for_timeout`
of the test, and one that does `route.fetch()` first has already written the file. Saves run one after the other
(`saveChain`), so a late answer delays the next save. `test_browser_wait.py` tests the loop with a stub page.

### Stdio sessions (2026-11-06, SPEC-0014 BR-014, DEC-010)

A test that talks to a child over stdio uses `tests/stdio_support.py` (`StdioSession`, `run_session`), never a
`readline()` on its stdout. A daemon reader thread feeds a queue; each line waits at most
`stdio_support.LINE_TIMEOUT_SECONDS` (30 s). A silent child is killed and reaped, the test fails with `the server did
not answer within 30 s`. Tests shorten it with `monkeypatch.setattr(stdio_support, "LINE_TIMEOUT_SECONDS", 1.0)`
(never `from ... import`). No `select`: a text pipe buffers ahead and can hide a line.

### Port range and lifecycle (2026-11-06, SPEC-0014 BR-001 to BR-007, BR-015, BR-016)

`test_port_range.py` binds the real ports 7839 to 7849 and counts a refused bind as taken, so another process holding
a port does not change its verdict. `test_port_range_foreign.py` proves it: a holder child listens (no `SO_REUSEADDR`)
on those ports, then `test_port_range.py` runs in a child pytest and must report `4 passed`. The stop sequence and the
connection registry are in `architecture.md` § Stop sequence; `test_server_lifecycle.py` (in process) and
`test_server_lifecycle_stdio.py` (real `mcp-htmleditor mcp` over stdio) test them. A test that needs a connection
accepted before the stop opens a later request first: connections are accepted in arrival order, and one still in the
listen backlog at the stop is reset by the kernel.

`make sync` also runs `playwright install chromium` (no-op if already cached) so the
browser E2E tests below can run without a manual step.

`pythonpath = ["src"]` makes the suite read the working tree. Without it a previously
installed non editable copy shadows `src/` and the suite silently measures old code.

## Files

| File | Covers |
|------|--------|
| `conftest.py` | `reset_settings` (autouse, drops the memoized `Settings`), `reset_state` / `fresh_state` (EditorState singleton), `html_file` |
| `browser_wait.py` | Bounded observation for browser tests: `wait_until`, `wait_for_file`, `wait_for_js`, `settle`, `answer_saves_late` and the constants (US-0084) |
| `test_browser_wait.py` | the observation loop with a stub page: first value that holds, last value in the failure, every wait at most 100 ms, settle delay (US-0084) |
| `test_no_fixed_waits.py` | Guard: every `wait_for_timeout(` of `tests/test_*_e2e.py` carries `# pacing: <reason>`; `unjustified_waits(path)`, parametrized per file, plus a throwaway file case (US-0088) |
| `test_suite_time_limit.py` | BR-012: the per test limit through child pytest runs; `slow` BT-016 at the literal 60 s / 900 s (US-0080) |
| `test_server_lifecycle.py`, `test_server_lifecycle_stdio.py` | stop releases the port, connection registry, `serve` on Ctrl+C; agent tools across a stop over real stdio (US-0082) |
| `test_port_range.py`, `test_port_range_foreign.py` | `find_free_port` over 7839 to 7849 independent of other processes; the holder child proof (US-0083) |
| `stdio_support.py` | `StdioSession` and `run_session`: JSON lines over a child's stdio, every line read bounded by `LINE_TIMEOUT_SECONDS`; `SILENT_CHILD`, `mcp_command()` (US-0081) |
| `test_stdio_support.py` | BR-014: short bound, closed stdout, partial line, real session, source check; `slow` BT-003 and BT-017 at the literal 30 s (US-0081) |
| `deck_support.py` | Deck fixtures (US-0035 to US-0040): `deck_ei`, `deck_carbon`, `deck_med`, `doc_perso` built from the real `templates/bootstrap` files (never committed); `slide_html(charter, title, ...)` returns one valid `ei` or `carbon` slide as an agent would send it; `write_deck` forces the modification time with `os.utime(path, (1_000_000_000, 1_000_000_000))` (no clock in tests); `assert_only_region_changed(before, after, marker)` proves byte identity outside an element found by plain substring search; `run_cli` and `call_tool` |
| `test_deck_patch.py` | `patch` with `set_text`, atomic write, path guard, check order, documents (US-0038) |
| `test_deck_patch_delete.py` | `delete_slide`, the one pass renumbering on the three fixtures, dry run (US-0039); counters checked with plain regexes |
| `test_deck_patch_structure.py` | `insert_slide`, `move_slide`, `replace_slide` (US-0040): E2E-005, 007, 008, 014, 017, 018, 029, 030, check order, byte exact splice against a literal `hand()` builder (LF and CRLF, comment between slides, tab indentation), image restore, idempotence, original ids after move and replace |
| `test_save_safety_e2e.py` | SPEC-0009: atomic save, 409 conflict check, no leftover file, update flag expiry (real server, `served_deck`, `FakeClock`) |
| `test_save_ui_e2e.py` | SPEC-0009: conflict notice (Reload, Keep mine), save error notice, in real Chromium (`needs_chromium`) |
| `test_history_e2e.py` | SPEC-0009: history snapshots, `history` / `restore` commands, limit of 20, concurrent ids |
| `test_history_tools.py` | SPEC-0009: tools `history` / `restore` through `fastmcp.Client` (E2E-006), patch snapshot (E2E-026), tool errors equal the CLI lines, core lines, stdout clean |
| `test_config.py` | Backward compatible accessors: XDG defaults, env overrides, invalid port |
| `test_settings.py` | The `Settings` model: defaults, memoization per environment signature, `HTMLEDITOR_LOG_DIR` over `HTMLEDITOR_LOGS`, `~` expansion, blank value means unset, OTel fields, unknown prefixed variable ignored |
| `test_logging_config.py` | Handler installation, stderr console, `omit_repeated_times=False` plus a rendering check that two consecutive lines both carry a timestamp, file output, idempotence, noisy loggers pinned, unwritable log dir degrades to console only |
| `test_tracing.py` | JSONL serialization, parent/child links, span without end, export failure, `configure_tracing` idempotence, exception recording |
| `test_state.py` | EditorState singleton, persistence, mtime |
| `test_http_helpers.py` | `_strip_editor_artifacts`, `_rebuild_full_html` |
| `test_http_assets.py` | `data-asset-*` preservation when rebuilding a document |
| `test_http_time_bounds.py` | SPEC-0013 wait bound, idle close, send side bound, total bound (short bounds, fake clock) |
| `test_http_time_bounds_slow.py` | `slow` marker: the real 30 s and 5 min bounds |
| `test_http_health.py` | `/health` payload (status, version, file, port) |
| `test_templates.py` | Registry and search path resolution |
| `test_skill_content.py` | `SkillLibrary` (rewritten for SPEC-0006): core, topic, `--all`, unknown topic, missing files, `arch-qa` checklist |
| `test_skill_tool.py` | The `get_skill` MCP tool and `registered_tool_names()` |
| `test_skill_audit.py` | `skill-audit` report: sizes, budgets, missing items, `--json`, exit status (on the `skill_tree` fixture) |
| `test_skill_audit_checks.py` | `skill-audit` tool list check and stale statement check (core, topics, routing skill) |
| `test_skill_shipped.py` | Gates on the real `skill/` tree (2026-11-04, US-0034): the 15 topic files must exist (no skipping), per topic budget, title, `Reference:` last line for the six reference topics, anchors; `--all` equals core plus topics; legacy files gone, `docs/skill-archive/` present; E2E-006 clean `skill-audit` (16 `OK` lines, `skill-audit: OK`). Mutation cases run the same gates on a tmp copy of `skill/` with a topic removed or a stale word added |
| `test_export_pptx.py` | Slide detection on all templates, no `<script>` or shell text in the output, base64 and relative images, table spans and column widths, Gantt geometry, arch node shapes, annotation placement, geometry and style helpers |
| `test_export_docx.py` | HTML preprocessing (single title), charter detection, `word/styles.xml` patching, header and footer parts, cache and fallbacks, end to end pandoc exports guarded by `skipif` when pandoc is absent |
| `test_fullscreen_e2e.py` | SC-008 / FR-026-028 (see retrospective spec): fullscreen presentation mode via a real `ThreadingHTTPServer` + real headless Chromium (`pytest-playwright`). Toolbar/nav-arrow hiding, slide filling the screen, keyboard navigation independent of focus, the parent-side fallback CSS safety net, exit-preserves-position, and (SPEC-0016) the editor relay of `Home`/`End`/arrows while presenting. Guarded by `skipif` when Chromium is not installed |
| `test_reference_decks_present_e2e.py` | SPEC-0016: each of the five reference decks presents from the file and inside the editor, leaving keeps slide three (real Chromium) |
| `test_presentation_templates_fullscreen.py` | SPEC-0016 guard: every presentation file under `templates/` ships the fullscreen markers; the five decks are listed |
| `test_export_pptx_vectors.py` | SPEC-0016: PPTX warnings name every vector figure (CLI and agent tool), numbering, silent shell icons, unreadable raster keeps its warning |
| `test_legacy_arbitrations.py` | SPEC-0016: DOCX without pandoc fails explicitly, a stale server record is not adopted |
| `test_export_golden.py` | also holds the BT-032 fixture: slide hashes of `example-carbon-complete.html` (`tests/testdata/example_carbon_complete_slide_hashes.json`) |
| `test_autosave_focus_e2e.py` | SPEC-0004 (2026-10-10): a background autosave never moves focus, caret or selection and never drops keystrokes; saved file still clean, no self reload, status dot back to saved. Same real server + Chromium harness, `skipif` without Chromium. Results awaited with `browser_wait`, each test run with prompt and 2 s late saves (US-0084), BT-014 (bound and last value) |
| `render_support.py` | Render fixtures (SPEC-0008): `ei_deck_html`, `med_deck_html` (adds `h-md` to the figures), string injectors (`inject_in_body`, `append_to_slide`, `set_slide_class`, `add_script`), `big_deck`, PNG helpers, `needs_chromium` (skips a browser test without Chromium) |
| `test_render_install.py` | SPEC-0008: Chromium install and missing browser message |
| `test_render_picture.py` | SPEC-0008: one slide PNG, output path, stale cleanup |
| `test_render_options.py` | SPEC-0008: `--slide`, `--scale`, size rounding, check order |
| `test_render_report.py` | SPEC-0008: `--report` for one slide, problem ordering and wording |
| `test_render_report_only.py` | SPEC-0008: `--report-only` over the deck, option conflict (status 2), no file written, DECK-EI and DECK-MED clean |
| `test_render_content.py` | SPEC-0008: picture holds the slide after its entrance animation and nothing else (no header bar, no neighbour slide), pixel checks |
| `test_render_scale.py` | SPEC-0008: 40 slide decks (`big_deck`) analysed in under 30 s (`time.monotonic`), and the doc checks for README, AGENTS.md, observability.md and the core `render` line |
| `test_requests_core.py` | SPEC-0010: `RequestStore` and `RequestService` (record shape, lock across threads and processes with the UT-A02 subprocess pattern, unreadable record never reset), HTTP queue and list, `requests` command; exports `make_deck`, `expected_key`, `queue_over_http` |
| `test_requests_tools.py` | SPEC-0010: tools `list_requests` and `complete_request` through `call_tool`, tool errors equal the command line text without `error: `, stdout clean |
| `test_requests_cli.py` | SPEC-0010: `request-done` and `request-skip`, the `create` topic workflow, skill audit gate (UT-C04) |
| `test_requests_editor_e2e.py` | SPEC-0010: Ask AI panel and `Requests (n)` side list in Chromium (queue, empty, too long, too many pending, storage failure, script order) |
| `test_requests_refresh_e2e.py` | SPEC-0010: the side list follows the agent through the `/status` poll and `requests_revision`; the list is refetched only when the revision moves |
| `test_review_write.py` | SPEC-0010: `write_review` tool and `review` command (`--write`), review rules (at most 6, unique ids, 60 character titles) |
| `test_review_apply_e2e.py` | SPEC-0010: Apply button and `POST /review/apply` in Chromium, apply twice, stale page |
| `test_request_loop_acceptance.py` | SPEC-0010 closing story (2026-11-05): E2E-028 (the folder holds only `deck.html`, the state directory holds `record.json` and `record.lock`), UT-H01 full loop, UT-H02 state directory owns the data, UT-H03 skill audit and topic bounds (`topic_output('create')` at most 8000, file at most 7900; the story's 3800 is stale since SPEC-0006, BL-0028), UT-H04 docs name the interfaces, UT-H05 tool process stdout is `b""` |

Shared fixtures (SPEC-0009): `isolate_state_dir` (autouse, `conftest.py`) points `HTMLEDITOR_STATE_DIR` at a temporary
folder so no test touches the real state; `served_deck` (`conftest.py`) is an 8 slide EI deck `deck.html` served by a
real editor; `FakeClock` (`test_state.py`, `advance(seconds)`) drives history ids and the update flag expiry through
`EditorState.clock`; `needs_chromium` (`conftest.py`) skips a browser test when Chromium is missing. The Chromium
e2e tests `test_autosave_focus_e2e.py`, `test_undo_redo_e2e.py` and the browser test of `test_http_origin_e2e.py`
can fail under load (BL-0024): rerun once.

Storage failure seam (SPEC-0010, DEC-010, 2026-11-05): to make a request write fail, create a regular file at
`RequestStore.record_dir(file)`. `mkdir` of that directory then raises `OSError` for every user, root included.
`chmod` is not used because the suite also runs as root in the container, where permission bits do not stop a write.

### Browser E2E (`test_fullscreen_e2e.py`)

`pytest-playwright`'s `page` fixture (headless) against a real `start_http_server()` / `stop_http_server()` on a free
port, serving a 3-slide deck built from the real `templates/bootstrap/slides-ei-empty.html` (the fixture forces
`HTMLEDITOR_TEMPLATES_DIR`, never the installed copy). Slide globals (`navigate()`, `goToSlide()`, `:fullscreen` CSS)
live in the content iframe: reach it through `document.getElementById('content-frame').contentDocument`.
Headless Chromium does not enforce a `sandbox` iframe lacking `allow-fullscreen`, so the original denial cannot be
forced; the test checks the parent-side safety net (`body:has(#content-frame:fullscreen) #toolbar` in `editor.css`).
`tools/check_ei_insert.py` stays a manual screenshot check. `test_tracing.py` shares one session scoped
`set_tracer_provider()` (one call per process) and uses a local `TracerProvider` for the exporter internals.

## Coverage

Gate 80 %, actual around 95 %. Omitted: `cli.py`, `mcp_server.py`, `__main__.py` (thin wrappers); `# pragma: no cover`
marks `_EditorHandler` and the server lifecycle functions of `http_server.py`.

## Validating an export change

Never trust the slide count alone, look at the pixels:

```bash
mcp-htmleditor export pptx pres.html /tmp/out.pptx
soffice --headless --convert-to pdf /tmp/out.pptx --outdir /tmp/
pdftoppm -jpeg -r 72 /tmp/out.pdf /tmp/slide   # then read /tmp/slide-N.jpg
```

Regression set (slide counts, files under `templates/reference/slides/`): `euro-information` 3, `example-ei-complete` 9,
`ibm-carbon` 9 (no `data-type`), `example-carbon-complete` 9, `presentation-standard` 4 (legacy `<section>`),
`roadmap-one-pager` 1 (gantt with `margin-left`).

To prove a refactor did not move a shape, export with the previous revision from a throwaway `git worktree` and compare
`(name, shape_type, left, top, width, height, text)` tuples per slide; for DOCX compare the `<w:t>` runs and the
`w:pStyle` sequence of `word/document.xml`.

### 2026-08-21, medical charter tests

`tests/test_medical_template.py` covers the three failure modes of the charter:

* the CSS is duplicated in the two reference decks, so their `<style>` block is compared
  byte for byte with the bootstrap (fix with `make sync-medical-css`). Anchor the regex at
  line start (`^<style>\n.*?^</style>`): a header comment mentioning the tag otherwise
  starts the match and the captured "CSS" swallows `<html>`/`<head>`, which killed the
  `:root` tokens once, silently, with a green test;
* the insertable layouts live in JavaScript, out of pytest's reach, so
  `LAYOUT_SETS.medical` is checked textually (16 keys, required `data-*`, page marker on
  every layout that has a footer band, medical detection before EI in `detectTemplate`);
* the exporter has its own chrome and theme, so both decks are exported for real and the
  result is inspected (one PPTX slide per HTML slide, zero warning, pictures, native
  tables, a bare page number), plus a unit check that a dark slide resolves its inverted
  palette through `StyleResolver.active_scope`.

Deck coherence (sequential ids, `TOTAL`, `slideNames` == `data-title`, a `.med-source` on
every slide that shows an image, no CSS grid row) is asserted on both decks too: those are
authoring invariants an agent breaks by editing HTML by hand.

### Skill fixtures and data (2026-11-04)

`skill_tree` (`tests/conftest.py`) builds a valid temporary skill tree (core, 15 topics, checklist),
sets `HTMLEDITOR_SKILL_DIR` and isolates `HTMLEDITOR_ARCH_CHECKS_DIR`; tests mutate it through
`SkillTree`. `tests/data/skill_anchors.json` lists, per topic, the strings that must stay in the
shipped text (every topic but `arch-qa`, whose anchors live in `tests/test_arch_checks.py`).

### Text width bar tests (2026-11-07, SPEC-0015, DEC-011)

* `tests/width_support.py`: shared module page (`width_page`, one Chromium page per module), decks D1 to W1, drag and
  key helpers, `window.__widthSaves` (POST `/content` counter). Five files hold E2E-001 to E2E-043:
  `test_width_drag_e2e.py` (001 to 007, 042), `test_width_keys_undo_e2e.py` (008 to 016, 020, 030, 037, 038, 040),
  `test_width_failures_e2e.py` (017 to 019, 026, 027, 032, 036, 039), `test_width_visibility_e2e.py`
  (021 to 025, 031, 033, 043), `test_width_agent_e2e.py` (028, 029, 034, 035, 041). Run them with `make test ARGS='-k width'`.
* The two guidance lines (`skill/topics/create.md`, `export.md`) are asserted verbatim in a child process; the
  core `skill/core.md` is pinned by sha256 in E2E-035.
* Audit fixes (2026-11-07, US-0093): undo shortcuts on the focused bar, NFR-001 synchronous reflow, a drag ending
  without a save still reloads an agent write. `lastMtime` no longer moves during a drag: observe polls with
  `count_polls` / `wait_polls` (window.__statusPolls), never `lastMtime`.

### SPEC-0016 closing run (2026-11-08, US-0101)

* `make check`: 1768 passed, 2 skipped, 8 deselected, test step 320.14 s (limit 330 s), load average 20 to 33.
  A first run at load 35 to 42 took 438.87 s and failed two unrelated tests (a width drag e2e, the Ctrl+C serve test);
  both pass alone. Treat a step above 330 s at load above 30 as machine noise, re-run before trimming.
* SPEC-0016 tests (decks, guard, vectors, arbitrations, relay): about 26 s, under the 40 s of DEC-014.

### Test step budget trims (2026-11-06, SPEC-0014 BT-022, <= 330 s)

* `save_delay` (autosave and undo/redo e2e files) is parametrized per test by `pytest_generate_tests`:
  the 2000 ms late variant runs only where the delay mattered (autosave: the four tests that failed
  RED late in `.implement/US-0084-red.log`; undo/redo: `arch_node_reposition` and `document_block_reorder`,
  late saves do not affect them per `US-0085-red.log`). Every other test runs prompt only. BT-002 keeps
  at least one late test per file. Saves about 22 s (42 to 24 tests).
* `test_bounded_observation_reports_the_last_value` waits with an explicit 2 s bound instead of the 10 s
  default (a default argument is fixed at import, so patching the module constant would not reach it);
  it still asserts the default is 10 s. Saves about 8 s.
* `test_restart_loop_on_the_same_port` stays at 20 restarts: BT-012 says 20.
