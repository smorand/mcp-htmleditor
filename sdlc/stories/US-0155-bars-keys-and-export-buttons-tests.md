# US-0155: browser tests for the bars, the typing keys and the export buttons

> Spec: SPEC-0027 (sdlc/specs/SPEC-0027-browser-test-coverage/)
> Nature: DEBT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective
Add the browser tests of three untested rows of SPEC-0002 that need no timing and no agent write: the floating format bar and insert bar, keys typed in an editable zone, and the export buttons. No product code changes.

## Requirements covered
- SPEC-0027/DR-001 (partial: E2E-013, E2E-018, E2E-019 of SPEC-0002): the test suite SHALL contain, for each untested row, at least one browser test that drives the editor in Chromium and asserts the requirement the row covers.
- SPEC-0027/DR-002: every new browser test SHALL observe asynchronous results with `wait_until`, `wait_for_js` or `wait_for_file` and SHALL carry a trailing `# pacing: <reason>` on any `wait_for_timeout(` it keeps.
- SPEC-0027/DR-004: behavior invariance, the existing suite passes unmodified.
- SPEC-0027/DR-005: a test that shows a product defect is committed `xfail(strict=True)` with the reason and the row; no product code edit; the defect goes to the report as a proposal.

## Independent Test
`make test ARGS='tests/test_format_insert_bars_e2e.py tests/test_typing_keys_e2e.py tests/test_export_buttons_e2e.py tests/test_no_fixed_waits.py'` is green, then `make check`. The sum of the three files' durations (`--durations=0`) is recorded in the commit body.

## Design excerpt
### Decisions
- DEC-003: a test that reveals a product defect is `xfail(strict=True)`. DEC-004: one file per area, helpers imported where public, copied where file private.
### Paths
| Path | Action |
|---|---|
| `tests/test_format_insert_bars_e2e.py` | create |
| `tests/test_typing_keys_e2e.py` | create |
| `tests/test_export_buttons_e2e.py` | create |
### Existing patterns
`tests/test_save_ui_e2e.py:45-70` (`fast_poll`, `_open_in_edit_mode`, `_type_in_cover`), `tests/browser_wait.py` (`wait_until`, `wait_for_js`, `settle`), `tests/test_toolbar_icons_e2e.py:162-171` (`expect_download`, on the download button, not the export buttons), `tests/test_website_template_e2e.py` (website without export buttons), `needs_chromium` from `tests/render_support.py`. Editor selectors: format bar `_mcp_format_bar`, insert bar `#_mcp_insert_bar` (`src/mcp_htmleditor/static/editor-format.js:162-191`), export buttons `#export-pptx-btn`, `#export-docx-btn` (`editor.html:48-49`), slide marker `.slide.active` in the frame.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.

### SPEC-0027/DT-001: floating format bar and insert bar (E2E-013, FR-002, FR-003)
- Level / Driver / Location: browser / Chromium / `tests/test_format_insert_bars_e2e.py`
- Given a presentation open in edit mode
- When the human clicks into the cover title zone
- Then exactly four buttons in `#_mcp_insert_bar` are visible, whose text contains `Image`, `Tableau`, `Ligne HR` and `Lien` (French labels with an emoji prefix, `editor-format.js:187-190`)
- When the human selects the text of the zone
- Then the floating format bar is visible
- When the selection is collapsed by a click inside the zone
- Then the floating format bar is hidden
- When the human selects text again, then clicks outside every editable zone (a non editable area of the slide)
- Then the floating format bar is hidden. This last assertion is committed `xfail(strict=True)` with reason "SPEC-0002 FR-002: no hide on a click outside, editor-format.js:162-173 handler is empty"; the finding is proposed as a backlog entry (Nature BUG). All earlier assertions are plain.

### SPEC-0027/DT-006: keys typed in a zone do not move the slide (E2E-018, FR-018)
- Level / Driver / Location: browser / Chromium / `tests/test_typing_keys_e2e.py`
- Given a presentation of three slides in edit mode, slide 1 shown, caret in the cover title
- When the human presses Space, ArrowRight, ArrowLeft, Home, End and the letter F
- Then the slide marked `.slide.active` in the frame is still slide 1, the page is not in full screen, and the characters F and Space are in the zone text

### SPEC-0027/DT-007: export buttons by document type and downloads (E2E-019, FR-019)
- Level / Driver / Location: browser / Chromium with `expect_download` / `tests/test_export_buttons_e2e.py`
- Given a presentation and a document, each opened in the editor
- Then the presentation shows `#export-pptx-btn` and not `#export-docx-btn`, the document shows `#export-docx-btn` and not `#export-pptx-btn` (the website case is covered by `tests/test_website_template_e2e.py`)
- When the human clicks the export button of the presentation and of the document
- Then a download starts whose file name ends in `.pptx` and `.docx` and the downloaded file is a non empty zip archive (its first two bytes are `PK`)

## Constraints
- Files not to touch: everything under `src/`, `templates/`, `skill/`, and every existing test.
- Dependencies not to add: none.
- Patterns to avoid: a fixed wait without `# pacing:`; a lower time bound on a delay.
- Scope boundary: autosave timing, status dots, update window, undo depth and the doc budget belong to US-0156 and US-0157.

## Definition of done
- [ ] RED evidence: a test that shows a product defect is red before it is marked `xfail`; record the failing assertion.
- [ ] Every acceptance test above green (or strict xfail as stated); `make check` green on the work branch after this commit.
- [ ] DEBT: the existing suite passes unmodified; exceptions: none.
- [ ] Self review: no product file touched, every wait observed, durations recorded.
- [ ] One commit `US-0155: browser tests for the bars, the typing keys and the export buttons`, body with `Summary:`, `Spec: SPEC-0027` and the requirement ids.
