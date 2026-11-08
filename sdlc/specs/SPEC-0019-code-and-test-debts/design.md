# Code and test debts: technical debt design

> Id: SPEC-0019
> Nature: DEBT
> Depth: M
> Depth evidence: 4 debt items in 3 modules (state, cli, editor scripts) plus test hardening, 12 files (7 edited, 5 created), 1 internal method removed, one skill sentence added, no other public contract change
> Status: specified
> Generated on: 2026-11-08
> Behavior change: none in program behavior; one skill text addition (DR-005), declared in Section 7
> From backlog: BL-0009, BL-0011, BL-0014, BL-0036, BL-0010 (part: E2E-036)
> Depends on: none (ordering note with SPEC-0018 in Section 9, story C)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Debt

### DBT-001: `EditorState.load()` has no caller
- **Current structure:** `src/mcp_htmleditor/state.py:165-173` defines `load()`, which reads the file's `server.json` into `port`, `server_pid`, `poll_interval` with type checks. `rg -n "\.load\(\)" src` returns nothing; only `tests/test_state.py:172`, `:183`, `:193`, `:465`, `:468` call it. The live reader of `server.json` is `snapshot()` (`state.py:208-209`, process with no file of its own). SPEC-0016 locked that a stale record is never loaded at server start (`sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/design.md:76`, `tests/test_legacy_arbitrations.py:146`).
- **Cost paid today:** four tests keep dead code alive and suggest a restore path that the product deliberately does not have; a reader may wire it and break the SPEC-0016 arbitration.
- **Target structure:** `load()` removed; its four tests removed; the corrupt record case it covered is asserted through `snapshot()` (DT-001).
- **Observable behavior:** unchanged (no caller).

### DBT-002: `serve --poll` writes the process environment
- **Current structure:** `src/mcp_htmleditor/cli.py:220-221` sets `os.environ["HTMLEDITOR_POLL_INTERVAL"] = str(poll)`, then `cli.py:224-226` sets `state.poll_interval = poll` on the singleton. `AGENTS.md` (Essential conventions) says configuration goes only through `Settings`, no `os.environ` elsewhere; `cli.py:221` is the only `os.environ` in `src/` outside `config.py:258` (`rg -n "environ" src`).
- **Behavior analysis (why this is DEBT):** the environment value has one reader in the process, `config.default_poll_interval()` (`config.py:357-359`), called only by `EditorState.__init__` (`state.py:64`). `get_state()` at `cli.py:223` builds the singleton (or returns it), and `cli.py:226` then assigns `poll` explicitly, so the served interval (`/status` `poll_interval`, `http_server.py:446`) is `poll` with or without the write. The children of `serve` (browser via `webbrowser.open`, pandoc via `subprocess.run` in `export/to_docx.py:154`) do not read the variable (`rg -n "HTMLEDITOR_POLL_INTERVAL" src` returns `cli.py:179`, `cli.py:221`, `config.py:20`, `config.py:73`). Removing the write therefore changes no observable output.
- **Cost paid today:** a second configuration channel that contradicts the convention, and a settings memo keyed on a variable the program itself mutates (`config.py:256-268`).
- **Target structure:** `_serve_file` passes `poll` to the state only; `import os` leaves `cli.py` when unused.
- **Observable behavior:** unchanged.

### DBT-003: Two copies of the editor artifact stripping
- **Current structure:** `captureDomSnapshot(doc)` (`src/mcp_htmleditor/static/editor-undo.js:27-56`) and `runSave` (`src/mcp_htmleditor/static/editor-save.js:14`, strip at `:26-33`) each list the same four steps: remove `contenteditable` and clear `outline` and `cursor` on `[contenteditable]`; hide `#_mcp_format_bar` and `#_mcp_insert_bar` (`display:none`); take out `._mcp_drag_handle` and `._mcp_drop_indicator`; remove the class `_mcp_drag_host`. The undo copy mutates the live document and restores it (`detachDragArtifacts` and `reattachDragArtifacts`, `editor-drag.js:129-144`); the save copy works on a clone and then also calls `stripPresentingState(clone)` (`editor-save.js:34`).
- **Cost paid today:** a fix to one list silently misses the other (BL-0014; BL-0034 is such a fix waiting).
- **Target structure:** one function `stripEditorArtifacts(root)` in `editor-save.js` applies the four steps to `root` (a document or an element) and returns a function that undoes them; `runSave` calls it on the clone and ignores the returned function; `captureDomSnapshot` calls it on the live document, serializes, then calls the returned function. `stripPresentingState` stays in `runSave` only.
- **Observable behavior:** unchanged: the undo snapshot string and the saved HTML are byte identical (DR-005).

### DBT-004: The presentation guard and BR-021 check are substring checks
- **Current structure:** `tests/test_presentation_templates_fullscreen.py:13` and `:60-62` (`missing_markers`) look for `:fullscreen`, `id="btn-present"`, `enterPresentation`, `exitPresentation`, `updateFullscreenScale` anywhere in the raw text, comments included. `tests/test_skill_shipped.py:330-343` (SPEC-0016 BT-024, BR-021) fails only on a sentence holding `ibm-carbon` with `:fullscreen` or `plein écran`; a reworded false claim passes, and no positive statement is required.
- **Cost paid today:** a deck whose only markers sit in a comment passes the guard; the skill can lose the fact that the Carbon catalogue presents without any test noticing.
- **Target structure:** a new structural guard (DT-020) and a positive statement test (DT-021) beside the existing tests, which stay unchanged (DEC-004).
- **Observable behavior:** unchanged, except one added sentence in the `slides-carbon` skill topic (DEC-005).

### DBT-005: No test asserts that spans carry no document content
- **Current structure:** SPEC-0001 FR-023 (`sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:130`) forbids document content, prompts or credentials in span attributes; its row E2E-036 (`spec.md:183`) is `untested`. `tests/test_tracing.py:63` and `tests/test_tracing_unencodable.py:57` assert attributes that are present, never an absence. `tests/trace_support.py:115` (`run_traced_server`) runs a traced editor server in a child interpreter.
- **Cost paid today:** a span attribute holding the saved HTML would ship unnoticed.
- **Target structure:** one child run asserting the absence (DT-030).
- **Observable behavior:** unchanged.

## 2. Perimeter: the Current State

| File | Change | Occurrences |
|---|---|---|
| `src/mcp_htmleditor/state.py` | remove `load()` (`:165-173`) | 1 method, 9 lines |
| `src/mcp_htmleditor/cli.py` | remove `:220-221`; remove `import os` (`:14`) when `rg -n "\bos\." src/mcp_htmleditor/cli.py` is empty after it | 2 lines plus 1 import |
| `src/mcp_htmleditor/static/editor-save.js` | add `stripEditorArtifacts(root)`; `runSave` `:27-33` calls it | 7 lines replaced |
| `src/mcp_htmleditor/static/editor-drag.js` | none (`detachDragArtifacts`, `reattachDragArtifacts` reused, `:129-144`) | 0 |
| `src/mcp_htmleditor/static/editor-undo.js` | `captureDomSnapshot` `:28-53` calls it | 26 lines replaced |
| `skill/topics/slides-carbon.md` | `:96`: one positive sentence (DR-007) | 1 line |
| `tests/test_state.py` | remove 4 tests (Section 8.4) | 4 tests |
| `tests/test_state_record.py` | new: DT-001 | 0 now |
| `tests/test_serve_poll.py` | new: DT-010, DT-011 | 0 now |
| `tests/test_editor_artifact_strip.py` | new: DT-012 | 0 now |
| `tests/test_presentation_markers_structural.py` | new: DT-020, DT-021 | 0 now |
| `tests/test_tracing_no_content.py` | new: DT-030 | 0 now |
| `.agent_docs/testing.md` | file map: the five new files, one line each | 5 lines |

**Backlog entries closed in this commit without code (verified 2026-11-08):** BL-0013 (silent polling failure) is resolved by SPEC-0009: `pollStatus` counts failures through `notePollFailure()` (`src/mcp_htmleditor/static/editor.js:356`), DEC-015 of `sdlc/specs/SPEC-0009-reliable-saves/design.md:307`. BL-0016 (non atomic writes) is resolved by SPEC-0009: saves go through `fileio.atomic_write` (`src/mcp_htmleditor/http_server.py:33`, `:788`), the state records through `_atomic_write_json` (`src/mcp_htmleditor/state.py:256`); the remaining `write_text` in `src/` is the pandoc staging file (`export/to_docx.py:134`), not a user document. BL-0029 (write_review with a non list) is resolved: the parameter is typed `Any` (`src/mcp_htmleditor/mcp_server.py:510`) and `tests/test_review_write.py:166-167` assert `Review must be a list of suggestions` for `{}` and `None`. BL-0010 and BL-0017 are rewritten in place with the gaps re-verified on 2026-11-08 (DEC-006).
**Non source occurrences:** `rg -n "EditorState.load|\.load\(\)" README.md AGENTS.md .agent_docs Makefile Dockerfile skill` returns nothing; sdlc history (`sdlc/stories/US-0100-*.md:80`, SPEC-0016) names `load()` as BL-0009 and stays as history. `HTMLEDITOR_POLL_INTERVAL` in `README.md`, `config.py:20` (docstring) and `cli.py:179` (help: the flag overrides the variable) stays true. No CI file, container file or Makefile line names `captureDomSnapshot`, `runSave` or the guard markers.
**Contracts touched:** `EditorState.load` (internal, no caller); `_serve_file` (internal, called by `serve` `cli.py:191` and `new --serve`); the `serve --poll` flag (public CLI, semantics unchanged: the interval served by `/status`); `stripEditorArtifacts` (new, internal to the classic scripts loaded by `editor.html:115-127`, all global). The `slides-carbon` skill topic (public text, DEC-005). No public contract is removed or changed.
**Guardrail coverage:** `tests/test_state.py` (state record and flag), `tests/test_legacy_arbitrations.py` (stale record never loaded), `tests/test_undo_redo_e2e.py` (undo and redo snapshots in a browser), `tests/test_save_ui_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_save_safety_e2e.py` (saved HTML), `tests/test_presentation_templates_fullscreen.py`, `tests/test_skill_shipped.py`. `serve --poll` has no test today (`rg -n "\-\-poll|poll=" tests` returns nothing): DT-010 comes first. **Test command:** `make check`.
**Total:** 12 files touched: 7 edited (`state.py`, `cli.py`, `editor-save.js`, `editor-undo.js`, `slides-carbon.md`, `tests/test_state.py`, `.agent_docs/testing.md`) and 5 created tests; the table has 13 rows (`editor-drag.js` listed, unchanged); 1 method, 1 environment write, 2 duplicated blocks, 2 substring checks, 1 untested requirement.

## 3. Class sweep

Not a security lot (DBT-005 adds a privacy test on existing behavior; no flaw is known).

## 4. Requirements (EARS)

### 4.1 Structural

#### DR-001 [EARS-UB]: No dead state loader
> `src/mcp_htmleditor/state.py` SHALL NOT define a method `load` on `EditorState`.
- **Old form:** `def load(self) -> None:` (`state.py:165`)
- **New form:** absent; `snapshot()` stays the only reader of `server.json`.

#### DR-002 [EARS-UB]: No environment write outside configuration
> No module under `src/mcp_htmleditor/` other than `config.py` SHALL contain `os.environ`, `os.putenv` or `os.getenv`.
- **Old form:** `os.environ["HTMLEDITOR_POLL_INTERVAL"] = str(poll)` (`cli.py:221`)
- **New form:** absent; `state.poll_interval = poll` (`cli.py:226`) stays.

#### DR-003 [EARS-U]: One definition of the editor artifact strip
> The editor scripts SHALL define the strip of editor artifacts once, as `function stripEditorArtifacts(root)` in `src/mcp_htmleditor/static/editor-save.js`, applying in this order: for each `[contenteditable]` under `root`, remove the attribute and set `style.outline` and `style.cursor` to `''`; set `style.display = 'none'` on `#_mcp_format_bar` and `#_mcp_insert_bar` found under `root`; `detachDragArtifacts(root)`; and SHALL return a function that restores each `contentEditable`, `outline`, `cursor`, each bar `display` and calls `reattachDragArtifacts` with the detached state.
- **Old form:** the inline steps of `editor-undo.js:28-53` and `editor-save.js:27-33`
- **New form:** `const restore = stripEditorArtifacts(doc); const html = withWidthPreviewSuspended(() => doc.documentElement.outerHTML); restore(); return html;` in `captureDomSnapshot`; in `runSave`: `const clone = withWidthPreviewSuspended(() => doc.documentElement.cloneNode(true)); stripEditorArtifacts(clone); stripPresentingState(clone);`
- **Selector rule:** bars are found with `root.querySelectorAll('#_mcp_format_bar, #_mcp_insert_bar')` (works on a document and on a detached element; `getElementById` does not exist on an element).
- **Casing convention:** camelCase JavaScript functions, as the rest of `static/`.

#### DR-004 [EARS-U]: Structural presentation guard
> The test suite SHALL check, for every presentation file found by `presentation_files(TEMPLATES_ROOT)` (`tests/test_presentation_templates_fullscreen.py:51`), after removing HTML comments: a `<style>` block whose text, CSS comments removed, contains `:fullscreen`; an element start tag carrying `id="btn-present"`; and, inside `<script>` blocks, a line matching `^\s*(?:async\s+)?function (enterPresentation|exitPresentation|updateFullscreenScale)\s*\(` for each of the three names.

#### DR-005 [EARS-U]: Positive Carbon presenting statement
> The `slides-carbon` skill topic SHALL contain the sentence `Le catalogue \`ibm-carbon.html\` a le mode présentation (bouton Présenter).`

#### DR-008 [EARS-U]: Span privacy is tested
> The test suite SHALL assert that a traced save and export of a deck write none of the deck's text into span names or attributes (SPEC-0001 FR-023, E2E-036), through DT-030.

### 4.2 Invariance (MANDATORY)

#### DR-006 [EARS-U]: Behavior invariance
> The system SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, the undo snapshot string and the HTML posted by a save included; the only text change is the sentence of DR-005 in the `slides-carbon` topic output.

### 4.3 Compatibility

#### DR-007 [EARS-E]: `serve --poll` keeps its effect
> WHEN `serve FILE --poll N` starts THE CLI SHALL serve `/status` with `poll_interval` equal to `N`, and SHALL leave `os.environ` without `HTMLEDITOR_POLL_INTERVAL` when it was absent before.

## 5. Compatibility plan

| Contract | Kind | Public | Plan | Deprecation window | Removal condition |
|---|---|---|---|---|---|
| `serve --poll N` | CLI flag | yes | kept, same effect (DR-007) | n/a | n/a |
| `HTMLEDITOR_POLL_INTERVAL` | environment variable | yes | read only through `Settings`, unchanged | n/a | n/a |
| `EditorState.load` | Python method | no | removed (no caller) | none | this spec |
| `slides-carbon` topic text | skill | yes (agents) | one sentence added (DEC-005) | n/a | n/a |

**Dual maintenance semantics:** none needed: no public contract changes form.

## 6. Decisions

- **DEC-001:** Remove `load()` rather than wire it. **Alternatives considered:** call it at server start (reverses the SPEC-0016 arbitration locked by `tests/test_legacy_arbitrations.py:146`, a behavior change, and SPEC-0016 rejected it, design `:76`); keep it (dead code with tests). **Rationale:** no caller, and the product forbids the restore it offers. **Implemented by:** DR-001. **Evidence:** `state.py:165`, `rg -n "\.load\(\)" src` empty.
- **DEC-002:** Replace the four `load()` tests by one `snapshot()` test, not by four. **Alternatives considered:** port each (the round trip is already `tests/test_state.py:346` `test_record_round_trip_and_last_json`; the missing file case is `test_state.py:380` corrupt `last.json` plus `_read_record`'s empty answer; wrongly typed values have no live reader that type checks, `state.py:209`, so a port would assert new behavior). **Rationale:** keep what the dead tests proved about live code (a corrupt `server.json` never raises, SPEC-0001 E2E-007) and nothing that would add behavior. **Implemented by:** DT-001.
- **DEC-003:** The shared strip returns a restore function instead of always cloning. **Alternatives considered:** clone in `captureDomSnapshot` too (no live mutation, so focus and `blur` events during a snapshot would differ from today: a behavior change); keep two copies with a parity test (the duplication stays). **Rationale:** one list of artifacts, each caller keeps its mechanism, byte identical strings. **Implemented by:** DR-003. **Evidence:** `editor-undo.js:27-56`, `editor-save.js:26-34`.
- **DEC-004:** Harden with new tests beside the existing ones, never by editing them. **Alternatives considered:** rewrite `missing_markers` (edits an existing test, and its exact message is asserted at `test_presentation_templates_fullscreen.py:113-116`); replace BT-024 (it guards a different fact, the absence of the old false claim). **Rationale:** the existing suite stays unmodified, coverage only grows. **Implemented by:** DR-004, DR-005.
- **DEC-005:** The positive statement is one sentence in `slides-carbon` (202 bytes of budget left: `skill-audit` 7798 of 8000; the sentence is 75 bytes plus a separating space). **Alternatives considered:** `create` topic (13 bytes left, 7987 of 8000); `core` (pinned by sha256 in SPEC-0015 E2E-035, `.agent_docs/testing.md:217`). **Rationale:** the topic that already names `ibm-carbon.html` (`slides-carbon.md:96`). **Implemented by:** DR-005. **Evidence:** `templates/reference/slides/ibm-carbon.html` ships the three functions and `#btn-present` (DT-020 is green on it).
- **DEC-006:** Only E2E-036 of BL-0010 is taken here; the browser rows of BL-0010 (E2E-004, E2E-005 reload half) and all of BL-0017 stay in the backlog, rewritten with the gaps verified on 2026-11-08. **Alternatives considered:** add the 8 browser tests now (the test step measured 320 to 325 s against a hard cap of 330 s, `.agent_docs/testing.md:225`, `:240`; about 3 s per browser test would break the cap); mark them `slow` (`make check` would not run them, so they would gate nothing). **Rationale:** a budget trim is a decision of its own, not a side effect of this debt lot. **Implemented by:** n/a, no code impact.
- **DEC-007:** Test time budget for this spec: the new tests at most 6 s together (`make test ARGS='--durations=0 -k "state_record or serve_poll or artifact_strip or markers_structural or no_content"'`), DT-030 being the only child process. **Rationale:** the gate has about 5 s of margin.
- **Assumption:** the test plan is approved without a review round (batch run, user instruction); no question was asked.

## 7. Declared breaks

No program behavior changes. One documentation text change is declared for transparency (not a break of any program contract):

- **BRK-001: `slides-carbon` topic text.** Who: agents and users running `mcp-htmleditor skill --type slides-carbon` or calling `get_skill` with that topic. Change: one sentence appended to line 96 (75 bytes plus a space; `skill-audit` 7798 to about 7874 of 8000). Migration: none, the text is additive; no existing test changes (`tests/test_skill_shipped.py:331-343` stays green: the sentence holds neither `:fullscreen` nor `plein écran`). Authorized by DEC-005.

## 8. Tests

### 8.1 Non regression: the success criterion
The existing test suite passes **unmodified**, except the removals of Section 8.4:

    make check

Test step at or below 330 s; a run above 330 s at load average above 30 is re run once before any trim.

### 8.2 Compatibility tests

#### DT-010: `serve --poll` sets the served interval without the environment
- **Validates:** DR-007, DR-002 on the `serve --poll` contract.
- **Given** `HTMLEDITOR_POLL_INTERVAL` absent (`monkeypatch.delenv(..., raising=False)`), the state singleton reset (`fresh_state` fixture, `tests/conftest.py:101`), `mcp_htmleditor.http_server.start_http_server` replaced by a function returning `(True, 7999)`, `mcp_htmleditor.http_server.stop_http_server` by a no op, `time.sleep` by a function raising `KeyboardInterrupt`;
- **When** `_serve_file(str(html_file), None, 250, "127.0.0.1", open_browser=False)` runs (imported from `mcp_htmleditor.cli`);
- **Then** `get_state().poll_interval == 250`, `"HTMLEDITOR_POLL_INTERVAL" not in os.environ`, and `config.get_settings().poll_interval == 1000`.
- **Red before the fix because:** `os.environ["HTMLEDITOR_POLL_INTERVAL"] == "250"` after the call.

#### DT-011: Without `--poll` the interval comes from Settings
- **Given** `HTMLEDITOR_POLL_INTERVAL=400` (`monkeypatch.setenv`), then the singleton reset (`EditorState._instance = None`, after the variable is set, so `get_state()` builds a state that reads it), the same doubles, **When** `_serve_file(..., None, None, ...)`, **Then** `get_state().poll_interval == 400` and the variable still reads `"400"`. Green before and after.

### 8.3 Structural tests

#### DT-001: A corrupt server record never raises (live reader)
- **Asserts:** with `fresh_state.set_file(html_file)`, `port = 6001` saved, then `server.json` overwritten with `{ not valid json`, then `EditorState._instance = None` and a new `EditorState()`: `snapshot()` returns `file == str(html_file.resolve())` and `port == config.default_port()`, `pid is None`, without raising. Covers what SPEC-0001 E2E-007 cited (`tests/test_state.py::test_load_corrupt_file_is_ignored`, removed).
- **Method:** in process, `tests/test_state_record.py`. Green before and after.

#### DT-002: No `load` method
- **Asserts:** DR-001: `not hasattr(EditorState, "load")`. In `tests/test_state_record.py`. **Red before the fix because:** `EditorState.load` exists.

#### DT-003: No environment access outside config
- **Asserts:** DR-002: no file `src/mcp_htmleditor/**/*.py` other than `config.py` contains `os.environ`, `os.putenv` or `os.getenv`. In `tests/test_serve_poll.py`. **Red before the fix because:** `cli.py:221`.

#### DT-012: One strip definition
- **Asserts:** DR-003, reading `src/mcp_htmleditor/static/*.js`: `function stripEditorArtifacts(` appears exactly once, in `editor-save.js`; the bodies of `function captureDomSnapshot(` and `async function runSave(` (text from the declaration to the next line starting with `function ` or `async function ` at column 0) each contain `stripEditorArtifacts(` and neither contains `removeAttribute('contenteditable')`; across all static scripts `removeAttribute('contenteditable')` appears exactly twice: once in `editor-save.js` (inside `stripEditorArtifacts`) and once in `editor-drag.js` (unchanged). Today (`rg -c "removeAttribute\('contenteditable'\)" src/mcp_htmleditor/static`): `editor-save.js` 1, `editor-undo.js` 1, `editor-drag.js` 1.
- **Method:** text assertions, no browser. **Red before the fix because:** `stripEditorArtifacts` is absent.
- **Behavior parity:** carried by the existing browser suites (undo, redo, autosave, save safety), unmodified.

#### DT-020: Presentation markers are real code
- **Asserts:** DR-004 on each of the 11 discovered files (parametrized by relative path); failure message `<relative path>: missing <marker>` per absent structural marker (`:fullscreen rule`, `#btn-present element`, `function enterPresentation`, `function exitPresentation`, `function updateFullscreenScale`).
- **Method:** regular expressions on the text with `<!--.*?-->` removed: `<style\b[^>]*>(.*?)</style>` (CSS `/\*.*?\*/` removed), `<[a-zA-Z][^>]*\bid="btn-present"`, `<script\b[^>]*>(.*?)</script>` then the line pattern of DR-004 (all `re.DOTALL` except the line pattern, `re.MULTILINE`). No BeautifulSoup (speed).
- **Negative cases in the same file:** a deck whose five markers appear only inside one HTML comment reports all five missing; a deck with `function enterPresentationLater(` and no `enterPresentation(` reports `function enterPresentation`; a deck with `:fullscreen` only in a `<script>` string reports `:fullscreen rule`.
- **Note:** green on today's 11 files (recounted: 3 declarations and 1 `#btn-present` start tag each, `rg -c`).

#### DT-021: The skill states that the Carbon catalogue presents
- **Asserts:** DR-005: with `HTMLEDITOR_SKILL_DIR` set to the repository `skill/` folder, `CliRunner().invoke(main, ["skill", "--type", "slides-carbon"])` exits 0 and its stdout contains `Le catalogue \`ibm-carbon.html\` a le mode présentation (bouton Présenter).`, and `make run ARGS='skill-audit'` stays OK (`slides-carbon` at most 8000 bytes, checked by the existing `tests/test_skill_shipped.py` budget test). **Red before the fix because:** the sentence is absent.

#### DT-030: Spans carry no document content
- **Asserts:** DR-008, FR-023 of SPEC-0001 (E2E-036): `run_traced_server(tmp_path, served, [save, export])` (`tests/trace_support.py:115`), the two raw requests built as in `tests/test_tracing_unencodable.py:134-150` (`POST /content` with `Host: 127.0.0.1:%PORT%`, `Content-Type: application/json`, `Content-Length`, then `GET /export/pptx`), with `served` a copy of the EI deck of `tests/deck_support.py` and a `POST /content` body whose HTML holds `<p>SECRET-7f3a9c</p>` and the title `SECRET-TITLE-7f3a9c`; then `run.data == [200, 200]`, and neither `SECRET-7f3a9c` nor `SECRET-TITLE-7f3a9c` appears in any line of `run.trace_lines` (span names and attributes). The application log is out of FR-023's scope and is not asserted.
- **Method:** one child run (as `tests/test_tracing_unencodable.py:134`). Expected green before and after (a guard, not a fix): `rg -n "trace_span\(|set_attribute" src` shows only paths, ids, keys, flags, counts and sizes as attributes (for example `fileio.py:63` `file.path`, `file.size`), not verified by a run at design time. If it is red on its first run, the leak is a real finding: stop, write a `Nature: BUG` backlog entry with the leaking attribute, and never weaken the assertion.

### 8.4 Existing tests to modify
| Test file | Test | Change | Justification |
|---|---|---|---|
| `tests/test_state.py` | `test_save_then_load_roundtrip` (`:160`) | removed | calls only `load()` (DR-001); the save and read round trip stays covered by `test_record_round_trip_and_last_json` (`:346`) |
| `tests/test_state.py` | `test_load_missing_file_is_noop` (`:179`) | removed | calls only `load()`; a missing record reads as `{}` in `_read_record` (`state.py:241-244`), exercised by `snapshot()` in `test_corrupt_records_are_ignored` (`:380`) |
| `tests/test_state.py` | `test_load_corrupt_file_is_ignored` (`:187`) | removed | calls only `load()`; replaced by DT-001 on the live reader; cited by SPEC-0001 E2E-007 (`spec.md:154`), which is not edited (history): DT-001 is its current test |
| `tests/test_state.py` | `test_load_ignores_wrongly_typed_values` (`:459`) | removed | type checks exist only in `load()`; `snapshot()` does not type check (`state.py:209`), so no live behavior is lost and none is added |

No other existing test changes.

## 9. Implementation order

1. Story A (state and CLI): add DT-001, DT-002, DT-003, DT-010, DT-011 (DT-002, DT-003, DT-010 red). Remove `cli.py:220-221` and the unused `import os`: DT-003, DT-010 green. Remove `load()` and the four tests of Section 8.4: DT-002 green. `make check`.
2. Story B (editor strip): add DT-012 (red), add `stripEditorArtifacts` and switch both callers (DR-003): DT-012 green; `node --check src/mcp_htmleditor/static/*.js`; `make test ARGS='-k "undo or save or autosave"'` green unmodified; `make check`.
3. Story C (guards and privacy). Ordering note: if `tests/test_agent_docs_size.py` (SPEC-0018 DT-013) exists when story C runs, the five lines keep `.agent_docs/testing.md` within its limit (220 lines), merging an older dated entry of the same section if needed; if it does not exist, the five lines are added as is and SPEC-0018 story B consolidates them later: add DT-020, DT-030 (green), DT-021 (red), append the DR-005 sentence at the end of `slides-carbon.md:96`, after one space: DT-021 green; `make run ARGS='skill-audit'` OK; add the five new test files to `.agent_docs/testing.md` § Files (one line each); measure DEC-007 and paste the durations; `make check`.

Stories A, B and C are independent of each other and of SPEC-0018; each leaves the suite green.

## 10. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 2 | 2 | NOT-IMPLEMENTABLE |
| 2 | 0 | 0 | IMPLEMENTABLE |

**Amendments applied:** round 1: F1 (file counts: 12 files, 7 edited and 5 created), F2 (skill sentence declared in the header and Section 7 as BRK-001, documentation only), A1 (story C precondition on SPEC-0018 story B), A2 (DT-030 raw requests spelled, red first run handled as a BUG entry, log out of scope). After round 2: the dependency on SPEC-0018 is replaced by the ordering note of Section 9 story C (SPEC-0018 escalated at its own three round cap), no test changed; Phase 10 re-run inline found DBT-005 and DT-030 without a requirement, DR-008 added to trace them (no new behavior, DT-030 unchanged); then PASS.

## 11. Open questions

- The test plan (Section 8) is treated as approved per the batch instruction; no interview round was held. Does not change observable behavior.
