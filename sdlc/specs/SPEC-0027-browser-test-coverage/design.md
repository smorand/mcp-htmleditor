# Browser test coverage of SPEC-0001 and SPEC-0002: technical debt design

> Id: SPEC-0027
> Nature: DEBT
> Depth: M
> Depth evidence: 1 module (tests), 9 untested rows of 2 specs, 6 new test files, 1 doc file, no product code, no contract change
> Status: implemented
> Generated on: 2026-11-19
> Behavior change: none
> From backlog: BL-0017, BL-0010
> Depends on: none
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Debt

### DBT-001: nine rows of two specs have no test at any level
- **Current structure:** SPEC-0002 § 8 lists E2E-013 to E2E-019 as `untested` (`sdlc/specs/SPEC-0002-browser-editing/spec.md:120-126`); SPEC-0001 § 8 lists E2E-004 and E2E-005 as `untested` (`sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:151-152`). Recount on 2026-11-19: no test asserts the floating format bar (`rg -n "format-bar|insert-bar" tests/*_e2e.py` finds none), the 800 ms and 600 ms save delays, the yellow dot, "no reload while pending", the 50 step undo depth, keys typed in a zone staying out of slide navigation, the export buttons, or the reload after an agent update window (agent half only: `tests/test_state.py`).
- **Cost paid today:** autosave, reload and keyboard isolation are what a human hits on every keystroke; a regression there has no alarm (BL-0017 Why).
- **Target structure:** each of the nine rows has at least one browser test that asserts its requirement.
- **Observable behavior:** unchanged (tests only).

### DBT-002: the test step budget in the docs is not the measured one
- **Current structure:** `.agent_docs/testing.md:36-38` says the `make check` test step stays at or below 330 s. The last runs on a quiet machine took 574 to 600 s (US-0150, US-0151 of SPEC-0026, 2832 to 2838 tests; the library tests of SPEC-0025 added the difference).
- **Cost paid today:** a rule that is false is ignored, so it cannot guard the cost of the new tests (BL-0017 Notes).
- **Target structure:** the rule states the measured baseline and a cap of 650 s, with a budget of 60 s for this spec's tests.
- **Observable behavior:** unchanged.

## 2. Perimeter: the Current State

| File | Change | Occurrences |
|---|---|---|
| `tests/test_format_insert_bars_e2e.py` | create: format bar and insert bar (E2E-013) | 1 file |
| `tests/test_autosave_timing_e2e.py` | create: 800 ms and 600 ms delays, save on blur, status dots, no reload while pending (E2E-014, E2E-015, E2E-016) | 1 file |
| `tests/test_undo_depth_e2e.py` | create: depth of 50, redo cleared by a new action (E2E-017) | 1 file |
| `tests/test_typing_keys_e2e.py` | create: keys typed in a zone stay out of slide navigation (E2E-018) | 1 file |
| `tests/test_export_buttons_e2e.py` | create: export buttons and downloads, by document type (E2E-019) | 1 file |
| `tests/test_update_window_e2e.py` | create: overlay and one reload after an agent update window (SPEC-0001 E2E-004, E2E-005) | 1 file |
| `.agent_docs/testing.md` | modify: the budget rule (line 36-38), the file map (a row for the six files) | 2 places |

**Non source occurrences:** `rg -n "330 s" -g "*.md" -g Makefile -g "*.toml" -g "*.py" .` and a read of `.agent_docs/` find the test step rule only in `.agent_docs/testing.md` (heading line 36 and text line 38; the other `330` hits are `skill/topics/medical.md:71` and `docs/skill-archive/medical.md:483`, unrelated pixel heights); the old figure also sits in finished spec documents under `sdlc/specs/` (SPEC-0009, SPEC-0010, SPEC-0016, SPEC-0019), which are never edited.
**Contracts touched:** none (internal, tests only). The editor, the server and every other test are untouched.
**Guardrail coverage:** the existing suite, 2847 tests in `tests/` (`make check` of 2026-11-18), and the helper rules `tests/test_no_fixed_waits.py` (no fixed wait), `tests/test_browser_wait.py`. **Test command:** `make test` for the files, `make check` for the gate.
**Total:** 6 files created, 1 file modified, 0 production files.

The existing tests to read first (patterns to follow): `tests/test_save_ui_e2e.py:45-70` (`fast_poll`, `_open_in_edit_mode`, `_type_in_cover`, `_agent_writes_title`), `tests/test_autosave_focus_e2e.py` (the `save_delay` parametrization), `tests/test_undo_redo_e2e.py`, `tests/test_width_visibility_e2e.py:53,124` (`OVERLAY_SHOWN`, `wait_for_js`), `tests/test_toolbar_icons_e2e.py:162-171` (`expect_download` on the download button, which is not the export buttons), `tests/browser_wait.py` (`wait_until`, `wait_for_js`, `settle`).

## 3. Class sweep
Not applicable (`Security: n/a`).

## 4. Requirements (EARS)

### 4.1 Structural
#### DR-001 [EARS-U]: every untested row has a browser test
> The test suite SHALL contain, for each of E2E-013 to E2E-019 of SPEC-0002 and E2E-004 and E2E-005 of SPEC-0001, at least one browser test that drives the editor in Chromium and asserts the requirement the row covers.
- **Old form:** the nine rows read `untested`.
- **New form:** the nine tests of Section 8.2 (DT-001 to DT-009).
- **Applies to:** the six new files of Section 2.
- **Casing convention:** `test_<what>_e2e.py`, snake case, like the existing browser test files.

#### DR-002 [EARS-U]: tests follow the existing browser test rules
> Every new browser test SHALL observe asynchronous results with `wait_until`, `wait_for_js` or `wait_for_file` and SHALL carry a trailing `# pacing: <reason>` on any `wait_for_timeout(` it keeps.
- **Old form:** n/a (new files).
- **New form:** `tests/test_no_fixed_waits.py` passes unchanged on the new files.

#### DR-003 [EARS-U]: the test step budget states the measured figure
> `.agent_docs/testing.md` SHALL state that the `make check` test step is measured at about 575 s on a quiet machine, that its cap is 650 s, and that the tests of this spec cost at most 60 s together.
- **Old form:** `.agent_docs/testing.md:36-38` "at most 330 s".
- **Lines touched:** the heading at line 36 (`### Test step budget (at most 330 s)`) and the text at line 38; the SPEC-0016 and SPEC-0017 lines keep their place and a SPEC-0027 line is added after them.
- **New form:** "at most 650 s (measured 575 s on 2026-11-18 before this spec)", with the per spec budget line "SPEC-0027 browser tests at most 60 s together".

### 4.2 Invariance (MANDATORY)
#### DR-004 [EARS-U]: Behavior invariance
> The editor, the server and the exports SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change.
- No file under `src/`, `templates/`, `skill/` or `static/` is modified; the existing tests are not modified.

#### DR-005 [EARS-UB]: a revealed product bug does not change product code
> IF a new test shows that the product violates its row, THEN THE test SHALL be committed as `xfail(strict=True)` with the reason and the row, and the finding SHALL be reported as a proposed backlog entry; this change SHALL NOT edit product code.

### 4.3 Compatibility
None: no public contract is touched.

## 5. Compatibility plan
| Contract | Kind | Public | Plan | Deprecation window | Removal condition |
|---|---|---|---|---|---|
| none | | | | | |

**Dual maintenance semantics:** n/a.

## 6. Decisions
- **DEC-001:** one spec for BL-0017 and BL-0010. **Alternatives considered:** two specs (BL-0010 asks to be specified with BL-0017 because the test step trim is shared, `BL-0010` Notes). **Rationale:** one budget decision, one set of helpers. **Implemented by:** n/a, no code impact. **Evidence:** the two entries' Notes. **Source:** user answer 2026-11-19 ("defaults").
- **DEC-002:** cap of the test step is 650 s, measured baseline 575 s, tests of this spec at most 60 s together. **Alternatives considered:** trim 60 s elsewhere to keep 330 s (the 330 s rule is already exceeded by 245 s, so a 60 s trim would not restore it); no cap. **Rationale:** the rule must be true to guard anything. **Implemented by:** DR-003. **Evidence:** `.agent_docs/testing.md:36-38`, `.implement` logs of SPEC-0026 (574 s, 600 s). **Source:** user answer ("defaults", recommendation accepted).
- **DEC-003:** a test that reveals a product defect is committed `xfail(strict=True)` and the defect is proposed as a backlog entry. **Alternatives considered:** fix the product here (changes behavior, not a debt); skip the test. **Rationale:** coverage is kept, the defect is visible, strict xfail turns green only when the product is fixed and forces removal of the mark. **Implemented by:** DR-005. **Source:** user answer ("defaults").
- **DEC-004:** six files, one per area, each reusing the fixtures of the existing files by import where they are public and by copy of the small helpers where they are file private. **Alternatives considered:** extend the existing files (they are at or near the pacing review limits and would mix concerns). **Rationale:** the per spec time budget is easy to measure per file. **Implemented by:** DR-001.
- **Assumption:** the nine tests together run in at most 60 s (about 3 s per browser test; 9 to 15 tests plus an agent write and the 50 step depth test, which uses 51 quick structural actions in one page). Measured by `make test ARGS='tests/test_format_insert_bars_e2e.py ... --durations=0'` in the implementing story; over 60 s is a story failure.

## 7. Declared breaks
None.

## 8. Tests
### 8.1 Non regression: the success criterion
The existing test suite passes unmodified: `make check`. The new files add tests; no existing test changes.

### 8.2 Compatibility tests
None (no public contract).

### 8.3 Coverage tests, one per untested row
Driver for all: Chromium through the existing `page` and `served_deck` style fixtures; the server is the real editor server on a loopback port. Waits as DR-002.

#### DT-001: floating format bar and insert bar (E2E-013, SPEC-0002 FR-002, FR-003)
- **Validates:** DR-001
- Given a presentation open in edit mode
- When the human clicks into the cover title zone
- Then the insert bar is visible and offers exactly four buttons in `#_mcp_insert_bar` whose text contains `Image`, `Tableau`, `Ligne HR` and `Lien` (they carry no id; the labels are French with an emoji prefix, `src/mcp_htmleditor/static/editor-format.js:187-190`)
- When the human selects the text of the zone
- Then the floating format bar is visible
- When the selection is collapsed by a click inside the zone
- Then the floating format bar is hidden
- When the human selects text again, then clicks outside every editable zone (a non editable area of the slide)
- Then the floating format bar is hidden (FR-002 says "hidden on a click outside"). This last assertion is committed `xfail(strict=True)` with reason "SPEC-0002 FR-002: no hide on a click outside, `src/mcp_htmleditor/static/editor-format.js:162-173` handler is empty", per DR-005, and the finding is proposed as a backlog entry (Nature BUG). All earlier assertions of DT-001 are plain

#### DT-002: autosave delays and save on blur (E2E-014, FR-004 to FR-006)
- **Validates:** DR-001
- Given a presentation in edit mode, autosave delays patched to nothing else (the real 800 ms and 600 ms)
- When the human types one character in the cover title
- Then the status dot is orange (pending) and the file on disk still has the old title at that moment, and the file has the new title within 3 s (the delay is 800 ms, `src/mcp_htmleditor/static/editor-save.js:4`; no assertion on a lower time bound, it would be flaky under load)
- When the human types, then moves focus to another zone
- Then the file on disk has the new text and the status dot is green within 3 s of the blur (the save on blur is immediate, `src/mcp_htmleditor/static/editor-save.js:5`; the test does not try to tell "at once" from the 800 ms delay, which a time bound could not do without flakiness)
- When the human completes a structural action (insert a slide)
- Then the file on disk has the new slide within 3 s (the delay is 600 ms, `editor-save.js:6`)

#### DT-003: status dot colours including the agent update (E2E-015, FR-007)
- **Validates:** DR-001
- Given a presentation in edit mode
- Then the status dot (`#toolbar-status`, its colour read back as computed `rgb(...)`) is green `#42be65` = `rgb(66, 190, 101)` when saved, orange `#ff832b` = `rgb(255, 131, 43)` while a change is pending, and yellow `#f1c21b` = `rgb(241, 194, 27)` while an agent update is open (`update_start` through the server, then `update_end`), and green again after the update closes

#### DT-004: no reload for its own save or while changes are pending (E2E-016, FR-008)
- **Validates:** DR-001
- Given a presentation in edit mode with the frame's load count recorded
- When the human types and the page saves
- Then the frame is not reloaded (load count unchanged)
- When the human has a pending change and the file on disk is changed by an agent write with a new modification time before the save runs
- Then the frame is not reloaded while the change is pending

#### DT-005: undo depth and redo cleared by a new action (E2E-017, FR-011)
- **Validates:** DR-001
- Given a document in edit mode and 51 structural actions performed in a row (block inserts)
- When the human undoes as many times as the button stays enabled
- Then exactly 50 steps are undone and the undo button is then disabled
- When the human redoes one step, then performs a new structural action
- Then the redo button is disabled

#### DT-006: keys typed in a zone do not move the slide (E2E-018, FR-018)
- **Validates:** DR-001
- Given a presentation of three slides in edit mode, slide 1 shown, caret in the cover title
- When the human presses Space, ArrowRight, ArrowLeft, Home, End and the letter F
- Then the slide marked `.slide.active` in the frame is still slide 1, the page is not in full screen, and the characters F and Space are in the zone text

#### DT-007: export buttons by document type and downloads (E2E-019, FR-019)
- **Validates:** DR-001
- Given a presentation, a document and a website, each opened in the editor
- Then the presentation shows the PPTX export button and no DOCX one, the document shows the DOCX button and no PPTX one, the website shows neither (the existing test keeps covering the website; this one covers the two positive cases)
- When the human clicks the export button of the presentation and of the document
- Then a download starts whose file name ends in `.pptx` and `.docx` and the downloaded file is a non empty zip archive (starts with `PK`)

#### DT-008: overlay while an agent update window is open (SPEC-0001 E2E-004, FR-004)
- **Validates:** DR-001
- Given a presentation open in the browser with the frame's load count recorded
- When the agent opens an update window and writes the file with a new modification time
- Then the blocking overlay is shown and the frame's load count does not change while the window stays open

#### DT-009: exactly one reload after the update window closes (SPEC-0001 E2E-005, FR-004)
- **Validates:** DR-001
- Given the state of DT-008 (window open, file written)
- When the agent closes the update window
- Then the overlay is hidden and the frame reloads exactly once, showing the new title; no second reload follows within 2 s

### 8.4 Structural tests
#### DT-010: the rules hold on the new files
- **Asserts:** `tests/test_no_fixed_waits.py` and `tests/test_browser_wait.py` pass unchanged with the six new files present; `rg -n "wait_for_timeout\(" <six files>` hits all carry `# pacing:`.
- **Method:** `make test ARGS='tests/test_no_fixed_waits.py'`, then `make check`.

#### DT-011: the budget is stated and respected
- **Asserts:** `.agent_docs/testing.md` contains `650 s`, `575 s` and `SPEC-0027 browser tests at most 60 s together`, and not `at most 330 s`; the six files run in at most 60 s together.
- **Method:** `rg -n "330 s" .agent_docs/testing.md` returns nothing; `make test ARGS='<six files> --durations=0'` sum of the six files' durations at most 60 s, recorded in the commit body.

### 8.5 Existing tests to modify
| Test file | Test | Change | Justification |
|-----------|------|--------|---------------|
| none | | | |

## 9. Implementation order
1. Files for E2E-013, E2E-018, E2E-019 (no timing, no agent write): `tests/test_format_insert_bars_e2e.py`, `tests/test_typing_keys_e2e.py`, `tests/test_export_buttons_e2e.py`. Stays green: the existing suite is untouched.
2. Files for E2E-014 to E2E-016 and SPEC-0001 E2E-004, E2E-005: `tests/test_autosave_timing_e2e.py`, `tests/test_update_window_e2e.py` (timing and the agent write).
3. File for E2E-017 `tests/test_undo_depth_e2e.py`, then `.agent_docs/testing.md` (DR-003, the file map), measure the six files' time, record it.
`/sdlc-design` cuts the stories along these three steps.

## 10. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 3 | 3 | NOT-IMPLEMENTABLE |
| 2 | 2 | 1 | NOT-IMPLEMENTABLE |
| 3 | 2 | 0 | IMPLEMENTABLE (after the two amendments, applied) |

**Amendments applied:** DT-001 hide and button labels, DT-002 timing, DT-003 colours, DT-006 slide marker, DR-003 heading line, perimeter statement on 330 s
