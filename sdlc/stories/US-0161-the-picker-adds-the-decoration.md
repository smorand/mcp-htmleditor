# US-0161: the picker adds the decoration

> Spec: SPEC-0029 (sdlc/specs/SPEC-0029-picker-embeds-decoration/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0160
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective
Inserting a Breathe layout from the picker shows its background and icons at once, in the deck's form, without reload and with Undo removing them; failures show a notice.

## Requirements covered
- SPEC-0029/FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-005, FR-NEW-006, FR-MOD-001 (texts as in the spec, Section 6).

## Independent Test
`make test ARGS='tests/test_picker_decoration_e2e.py tests/test_breathe_reference.py'` green (Chromium), `make check` green.

## Design excerpt
### Decisions
DEC-001 live insertion, no reload. DEC-003 form decided by the page: linked when any existing rule contains `url(assets/`. DEC-004 missing classes computed by the page (tokens starting `med-bg-` or `med-ico-` on the new slide and its descendants, minus classes with a rule). DEC-005 rules inserted just before `/* breathe:assets:end */` in the `<style>` holding it, then `saveContent()`. DEC-006 a new notice `#decoration-error`.
### Contracts
`src/mcp_htmleditor/static/editor-slides.js`:
- at the start of `insertSlide`: `hideNotice('decoration-error');`
- after its final `saveContent();`: `addBreatheDecoration(doc, newSlide);` (not awaited).
- new `async function addBreatheDecoration(doc, slide)`: find the `<style>` whose text contains `/* breathe:assets:begin */` (none: return, FR-NEW-006); `existing` = the class names matched by `/\.(med-(?:bg|ico)-[A-Za-z0-9_-]+)\s*\{/g` in that style; `needed` = tokens of `slide` and its descendants starting `med-bg-` or `med-ico-`, unique, not in `existing`; none needed: return; `link = /url\(\s*assets\//.test(styleText)`; `POST /breathe-assets` with `{classes: needed, link}` (JSON content type); on `res.ok` insert `rules.join('\n') + '\n  '` before the end marker in that style's `textContent` and call `saveContent()`; otherwise `showNotice('decoration-error', 'Decoration not added: ' + reason)` with reason = the `error` of a JSON answer, else `the editor server did not answer` (network error, non 2xx without a message). Wrap in try/catch: any exception gives the same notice.
- `src/mcp_htmleditor/static/editor.html`: in `#notices`, `<div id="decoration-error" class="notice" hidden><span class="notice-text"></span></div>`.
Undo: the undo snapshot is taken at the top of `insertSlide` before the slide and the rules exist, so Undo restores the document without both; Redo takes its snapshot from the current DOM (with the rules).
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-slides.js` | modify |
| `src/mcp_htmleditor/static/editor.html` | modify |
| `tests/test_picker_decoration_e2e.py` | create |
| `tests/test_breathe_reference.py` | modify `test_inserted_layout_before_and_after_embedding` (declared by the spec: E2E-008) |
### Existing patterns
`tests/test_breathe_reference.py`: `open_picker`, `slides_on_disk`, `Serve`, `serve_deck`, `BACKGROUND` (computed background of slide 2 in the live frame), `needs_chromium`; waits `wait_until`, `wait_for_js`; `node --check src/mcp_htmleditor/static/*.js` (no build step).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.
All Chromium tests in `tests/test_picker_decoration_e2e.py` except E2E-008. Start from the Breathe bootstrap copied to `tmp_path/talk.html` (as the existing picker tests) unless stated.
### SPEC-0029/E2E-001: inserted layout shows its decoration at once
- When `Pathway` is inserted / Then 2 slides on disk; within 3 s the second slide's `getComputedStyle(...).backgroundImage` is not `none`; the file's block holds `.med-bg-` rules for the classes of `Pathway` (second channel: the file); the frame was not reloaded (count of `/content-frame` requests unchanged)
### SPEC-0029/E2E-002: linked form
- Given `breathe-inline --link talk.html` run first, deck open / When `Pathway` inserted / Then background loaded, new rules read `url(assets/<file>)`, each named file exists in `assets` next to the deck
### SPEC-0029/E2E-003: folder cannot be written, linked
- Given the linked deck with its folder made read only (skip as root) / When `Pathway` inserted / Then 2 slides, `#decoration-error` visible with text starting `Decoration not added: Cannot write `, the file's block unchanged
### SPEC-0029/E2E-004: a file missing from the catalogue
- Given `catalogue_dir` monkeypatched to a copy of the catalogue without one `bg-` file used by `Pathway` / When inserted / Then 2 slides, `#decoration-error` text starts `Decoration not added: asset bg-` and contains `not found in: `, the file's block unchanged
### SPEC-0029/E2E-005: nothing twice
- Insert `Pathway` twice / Then 3 slides, the block after the second equals the block after the first, `#decoration-error` hidden
### SPEC-0029/E2E-006: medical deck
- Medical deck copy / insert a layout / Then one more slide, the `<style>` blocks of the file are identical to before
### SPEC-0029/E2E-007: picker cancelled
- Breathe deck, picker shown, cancel / Then 1 slide and the file byte identical (exists as `test_picker_cancelled`, kept, listed here)
### SPEC-0029/E2E-009: the server does not answer
- `page.route("**/breathe-assets", lambda r: r.abort())` / insert `Pathway` / Then 2 slides, notice text `Decoration not added: the editor server did not answer`
### SPEC-0029/E2E-010: undo history kept
- After inserting `Pathway`: press Undo / Then 1 slide, the file saved after the Undo holds no `Pathway` rule (a `.med-bg-` class that only `Pathway` uses), Redo available, Redo brings slide and rules back (file read)
### SPEC-0029/E2E-011: mixed form
- Deck whose block has one embedded rule and one rule `url(assets/<file>)` (written by the test) / insert `Pathway` / Then the new rules refer to `assets/` and the files are in `assets`
### SPEC-0029/E2E-012: Carbon deck
- Carbon deck copy / insert a layout / Then one more slide, `<style>` blocks identical
### SPEC-0029/E2E-013: insertion before the current slide
- `Pathway` inserted `before` / Then the new slide is first, its background loaded within 3 s, the file holds the rules
### SPEC-0029/E2E-014: nothing twice, linked
- Linked deck, insert twice / Then 3 slides, block unchanged after the second, no new file in `assets`, no notice
### SPEC-0029/E2E-015: a layout that needs nothing new
- Bootstrap deck (cover) / insert the cover layout (`Cover`) / Then 2 slides, block unchanged, no notice
### SPEC-0029/E2E-008: modified existing test (was E2E-052)
- `test_inserted_layout_before_and_after_embedding`: insert `Pathway`; Then the background is loaded within 3 s without the command; then run `breathe-inline`, reload, the background is still loaded

## Constraints
- Files not to touch: `http_server.py`, `breathe/inline.py`, the library modules, other tests. Modified existing test: E2E-008 only.
- Dependencies not to add: none.
- Scope boundary: docs are US-0162.

## Definition of done
- [ ] RED evidence for every new test before the production code.
- [ ] Every test above green; `node --check src/mcp_htmleditor/static/*.js` clean; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_breathe_reference.py` (other tests), `tests/test_undo_redo_e2e.py`, `tests/test_breathe_inline.py` green.
- [ ] One commit `US-0161: the picker adds the decoration`, body with `Summary:`, `Spec: SPEC-0029` and the requirement ids.
