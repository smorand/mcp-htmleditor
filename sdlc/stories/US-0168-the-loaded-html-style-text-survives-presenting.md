# US-0168: the loaded html style text survives presenting

> Spec: SPEC-0030 (sdlc/specs/SPEC-0030-style-writes-kept-as-text/)
> Nature: BUG
> Priority: P1
> Depends on: US-0167
> min_tier: 2
> Files touched: 5
> Closes spec: yes

## Objective
Presenting a deck and saving no longer leaves `<html>`'s style reserialized in the file: the editor saves the text the style had when the document loaded. Closes SPEC-0030: its full acceptance set must be green.

## Requirements covered
- SPEC-0030/BR-005: WHEN the editor saves THE editor SHALL write `<html>`'s `style` attribute with the text it had when the document was loaded, never the form the deck's presenting scale left it in, minus a top level `--fs-scale` declaration as SPEC-0020/BR-004 says. The loaded text is kept outside the document, so it survives an Undo or Redo and a save made while presenting. A document loaded without `style` on `<html>` is saved without.
- SPEC-0030/BR-006 (partial: the scale): the presenting scale is never written into the saved file.

## Independent Test
`make test ARGS='tests/test_style_text_presenting_e2e.py tests/test_reference_decks_present_e2e.py'` green, `make check` green and every SPEC-0030 test (BT-001 to BT-011) green.

## Design excerpt
### Decisions
DEC-004 restore the loaded text on save, no template change; DEC-005 capture at the top of `onFrameLoad`, skipped while `restoringFromUndo`.
### Contracts
`src/mcp_htmleditor/static/editor-save.js`: module variable `let loadedHtmlStyle;` (`undefined` until the first load). In `stripPresentingState(root)` (line ~90), before the existing `--fs-scale` removal: `if (loadedHtmlStyle !== undefined) { if (loadedHtmlStyle === null) root.removeAttribute('style'); else root.setAttribute('style', loadedHtmlStyle); }`, then re read `root.getAttribute('style')` for the existing removal. Update the doc comment (the scale left by the deck's runtime is never saved, the loaded text is).
`src/mcp_htmleditor/static/editor.js` `onFrameLoad` (line 322): right after `const doc = frame.contentDocument; if (!doc) return;` add `if (!restoringFromUndo) loadedHtmlStyle = doc.documentElement.getAttribute('style');`.
Docs: `AGENTS.md` (the SPEC-0020 rule bullet: add that the presenting scale is not saved because `<html>`'s loaded style text is restored on save, `editor-save.js` `loadedHtmlStyle`), `.agent_docs/testing.md` (file map row for `test_style_text_actions_e2e.py` and `test_style_text_presenting_e2e.py`; keep it within 220 lines).
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor.js` | modify |
| `src/mcp_htmleditor/static/editor-save.js` | modify |
| `tests/test_style_text_presenting_e2e.py` | create |
| `AGENTS.md` | modify |
| `.agent_docs/testing.md` | modify |
### Existing patterns
`tests/test_reference_decks_present_e2e.py::test_save_while_presenting_writes_no_presenting_state` (lines 267-310: `#edit-mode-btn`, `#present-btn`, type in `[data-fs-current] [data-editable~="text"]`, autosave, leave with Escape), fixtures `tests/style_text_support.py`.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc. Deck S2 as in US-0167 (`<html>` style `color:#161616`).
### SPEC-0030/BT-001: presenting then saving keeps `<html>`'s style text (reproduction)
- Fails today because the deck's runtime reserializes `<html>`'s style (`color: rgb(22, 22, 22);`) and the save keeps it.
- Given Deck S2 served, edit mode on, `#present-btn` pressed / When the person types `X` in a text of the presented slide, the autosave writes the file, then leaves the presentation (Escape) and types `Y` / Then `<html>`'s style in the file is `color:#161616` after each save and `--fs-scale` is nowhere in the file
### SPEC-0030/BT-009: no style on `<html>`
- Given a deck whose `<html>` has no `style`, presented and saved / Then the file's `<html>` has no `style` attribute
### SPEC-0030/BT-010: the scale still leaves the saved file (non regression)
- Existing test `tests/test_reference_decks_present_e2e.py::test_save_while_presenting_writes_no_presenting_state` stays green, unmodified.
### SPEC-0030/BT-011: SPEC-0020 text level rules (non regression)
- `tests/test_style_text_*_e2e.py` stay green, unmodified (BT-016 of SPEC-0020 keeps `color:#161616 /* x;--fs-scale:9 */` unchanged: its loaded text is its saved text).

## Constraints
- Files not to touch: `editor-width.js`, `editor-menus.js`, `editor-drag.js`, templates, existing tests.
- Dependencies not to add: none.

## Definition of done
- [ ] RED evidence for BT-001 before the fix.
- [ ] Every test above green; `node --check src/mcp_htmleditor/static/*.js` clean; `make check` green on the work branch after this commit.
- [ ] Spec converge: every test of SPEC-0030 green (BT-001 to BT-011), every requirement BR-001 to BR-007 cited by a story with status done or landed.
- [ ] Docs updated: `AGENTS.md`, `.agent_docs/testing.md`.
- [ ] One commit `US-0168: the loaded html style text survives presenting`, body with `Summary:`, `Spec: SPEC-0030` and the requirement ids.
