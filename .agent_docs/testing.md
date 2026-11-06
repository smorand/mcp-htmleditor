# Tests

```bash
make test                 # pytest -v
make test ARGS='-k pptx'  # subset
make test-cov             # coverage, gate 80 %
make test ARGS='-m slow'  # the slow marker, selected on request only
```

### Slow marker and short time bounds (2026-11-05, SPEC-0013)

`pyproject.toml` registers the marker `slow` and sets `addopts = "-m 'not slow'"`, so `make test`,
`make test-cov` and `make check` deselect it; `ARGS='-m slow'` wins because the last `-m` is the one pytest keeps.
No Makefile target exists for it. `tests/test_http_time_bounds_slow.py` (marked at module level) checks the real
values: BT-003, BT-015, BT-023 (30 s), BT-022 (50 s), BT-040 (5 min); the whole module takes about 8 minutes.
The default tests of `tests/test_http_time_bounds.py` shorten the bounds with
`monkeypatch.setattr(http_deadline, "WAIT_SECONDS", 1.0)` and `"TOTAL_SECONDS"` (4.0): the constants are read
through the module at each use, which is the only seam; they are not a setting and no setting, option or help text names them.
`DeadlineReader` takes a `clock` argument, tests pass a hand moved fake clock for the total bound.
Raw socket helpers live in `tests/http_support.py` (`exchange`, `RawReply`, `json_body`); `tests/trace_support.py`
holds the tracing capture helpers.

### Per test time limit (2026-11, SPEC-0014)

Every test is bounded by `pytest-timeout`: `timeout = 60` and `timeout_method = "signal"` in
`[tool.pytest.ini_options]`. A test over its limit fails alone with `Timeout (>60.0s) from pytest-timeout.` and its node
id, the run goes on and `make test` / `make check` exit non zero. The signal method is required: the thread method
would end the whole process and name nothing. `tests/conftest.py` holds `SLOW_TEST_TIMEOUT_SECONDS = 900` and a
`pytest_collection_modifyitems` hook that adds `pytest.mark.timeout(900)` to each test carrying `slow` (an explicit
`timeout` marker is left as is), so slow tests are never marked one by one.
`tests/test_suite_time_limit.py` checks it with child pytest runs on throwaway files under `tmp_path`. A child run
needs `-c pyproject.toml --rootdir <repo> -p tests.conftest -p no:cacheprovider`, cwd at the repository root, and a
`timeout=` on `subprocess.run`, plus `--confcutdir` at the throwaway folder and its own `--basetemp` under it.
Without `--confcutdir` pytest collects every ancestor of a file outside the rootdir, and `$TMPDIR` held 75k entries
(5 to 12 s of collection); without `--basetemp` the child shares `$TMPDIR/pytest-of-<user>/` and deletes any stale
`pytest-N` (a finished full run is about 80k files). Together they made a child with a 2 s limit run 7 to 35 s while
its alarm fired on time (measured 2026-11-06). Judge a timed out test on its JUnit call time (`--junitxml`), never on
the child's wall time. The literal 60 / 900 check (BT-016) is `slow`:
`make test ARGS='-m slow -k suite_time_limit'`. The dependency is `pytest-timeout>=2.4.0`: 2.5.0 is yanked on PyPI
(accidental breaking change), so uv cannot lock it; move to a later release once one is not yanked.

### Browser waits (2026-11, SPEC-0014 BR-008 to BR-011, DEC-011 to DEC-014)

A browser test never asserts an asynchronous result (file after an autosave, status dot, DOM after an insert, a reload)
after a fixed delay. It uses `tests/browser_wait.py`: `wait_until(page, observe, holds, what=...)` observes first, then
pauses `page.wait_for_timeout(100)` between observations (`OBSERVE_INTERVAL_SECONDS`), up to 10 s
(`OBSERVE_BOUND_SECONDS`) from the call, and fails with `AssertionError("<what> not reached within 10 s, last value:
<repr>")`. `wait_for_file(page, path, needle)` and `wait_for_js(page, expression, expected, what=...)` are the two shapes
used by the files. Never `time.sleep` in an observation: in the sync Playwright API route handlers and events run only
inside a Playwright call. An absence ("the preview was not reloaded") is asserted after `wait_until` on the step that
could cause it, then `settle(page)` (1 s, `SETTLE_SECONDS`), then the assertion. A `wait_for_timeout(` that stays in a
browser test carries a trailing `# pacing: <reason>` (a spacing between two user actions, no result asserted after it).

Late saves: `answer_saves_late(page, 2000)` (`LATE_SAVE_MS`) is an init script that holds every `POST /content` for
2 s before it leaves, so the file and the answer both come 2 s late; call it before `page.goto`.
`test_autosave_focus_e2e.py` has a `save_delay` fixture (`prompt`, `late`) on every test. Do NOT build it with a route
handler (measured 2026-11-06): in the sync API a handler that waits (`time.sleep` or a nested
`page.wait_for_timeout`) blocks the dispatcher, so each `wait_for_timeout` of the test returns only after the handler,
the test timeline stretches by the delay and the old fixed waits pass; and a handler that does `route.fetch()` first has
already written the file. The editor runs saves one after the other (`saveChain`), so a late answer delays the next
save: the old `SAVE_WAIT_MS` tests fail in the `late` variant (4 of 9). `tests/test_browser_wait.py` tests the loop with
a stub page (no browser).

### Bounded stdio reads (2026-11-06, SPEC-0014 BR-014, DEC-010)

A test that talks to a child process over stdio uses `tests/stdio_support.py` (`StdioSession`, `run_session`), never a
`readline()` on the child's stdout. A daemon reader thread feeds a queue and each line read waits at most
`stdio_support.LINE_TIMEOUT_SECONDS` (30 s). A silent child is killed and reaped, and the test fails with
`the server did not answer within 30 s`. The constant is read through the module at each call: tests shorten it with
`monkeypatch.setattr(stdio_support, "LINE_TIMEOUT_SECONDS", 1.0)` (never `from ... import LINE_TIMEOUT_SECONDS`).
`select` is not used: a text mode pipe buffers ahead and can hide a buffered line. The literal 30 s cases (BT-003,
BT-017) are `slow`: `make test ARGS='-m slow -k stdio_support'`.

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
| `test_fullscreen_e2e.py` | SC-008 / FR-026-028 (see retrospective spec): fullscreen presentation mode via a real `ThreadingHTTPServer` + real headless Chromium (`pytest-playwright`). Toolbar/nav-arrow hiding, slide filling the screen, keyboard navigation independent of focus, the parent-side fallback CSS safety net, and exit-preserves-position. Guarded by `skipif` when Chromium is not installed |
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

Uses `pytest-playwright`'s `page` fixture (headless by default) against a real
`start_http_server()`/`stop_http_server()` instance on a free port, serving a 3-slide
deck built from the real `templates/bootstrap/slides-ei-empty.html` (never the
`~/.config` installed copy: the fixture forces `HTMLEDITOR_TEMPLATES_DIR`). Reaches into
the content iframe's own document via `document.getElementById('content-frame').
contentDocument` since the slide template's `:fullscreen` CSS and `navigate()`/
`goToSlide()` globals live there, not in the parent shell.

One known Playwright/CDP limitation: headless Chromium under automation does not
reliably enforce a `sandbox` iframe missing `allow-fullscreen` the way a real,
interactively-driven browser does (verified empirically), so the exact permission
denial that caused the original bug cannot be forced end to end in this suite. The test
instead exercises the deterministic part of the contract: the parent-side CSS safety net
(`body:has(#content-frame:fullscreen) #toolbar` in `editor.css`) that must hide the shell
toolbar if the fallback (fullscreening the `<iframe>` element itself) is ever taken, for
whatever reason.

This differs from `tools/check_ei_insert.py`, which stays a manual, screenshot-based
visual check (its own docstring explains why it is not a unit test): the fullscreen
contract is fully assertable (computed styles, `fullscreenElement`, counters), so it
belongs in the automated suite and in `make check` instead.

`trace.set_tracer_provider()` accepts one call per process, so `test_tracing.py` shares a
single session scoped configuration for the tests that need the global tracer and uses a
local `TracerProvider` for the exporter internals.

## Coverage

Gate 80 %, actual around 95 %. Omitted: `cli.py`, `mcp_server.py`, `__main__.py` (thin
wrappers). `# pragma: no cover` marks the `_EditorHandler` network class and the server
lifecycle functions in `http_server.py`.

## Validating an export change

Never trust the slide count alone, look at the pixels:

```bash
mcp-htmleditor export pptx pres.html /tmp/out.pptx
soffice --headless --convert-to pdf /tmp/out.pptx --outdir /tmp/
pdftoppm -jpeg -r 72 /tmp/out.pdf /tmp/slide   # then read /tmp/slide-N.jpg
```

Regression set (expected slide counts):

| File | Slides |
|------|--------|
| `templates/reference/slides/euro-information.html` | 3 |
| `templates/reference/slides/example-ei-complete.html` | 9 |
| `templates/reference/slides/ibm-carbon.html` | 9 (no `data-type`) |
| `templates/reference/slides/example-carbon-complete.html` | 9 |
| `templates/reference/slides/presentation-standard.html` | 4 (legacy `<section>`) |
| `templates/reference/slides/roadmap-one-pager.html` | 1 (gantt with `margin-left`) |

To prove an internal refactor did not move a single shape, export with the previous
revision in a throwaway worktree and compare the shape fingerprints:

```bash
git worktree add /tmp/ht-baseline HEAD
# export with /tmp/ht-baseline/src on sys.path, then compare
# (name, shape_type, left, top, width, height, text) tuples slide by slide
git worktree remove /tmp/ht-baseline --force
```

For DOCX, compare the `<w:t>` runs and the `w:pStyle` sequence of `word/document.xml`
between the two exports.

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
