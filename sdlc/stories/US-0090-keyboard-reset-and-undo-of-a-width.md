# US-0090: Keyboard steps, reset and undo of a width

> Spec: SPEC-0015 (sdlc/specs/SPEC-0015-text-max-width-handle/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0089
> min_tier: 1
> Files touched: 5
> Closes spec: no

## Objective

Once the bar has the keyboard focus the author adjusts a width with the arrows, gives the template's width back with
a double click or Delete, and undoes or redoes any width change like a structural action. The silent pitfalls are the
undo order (the snapshot must be the text before the change, pushed only when something changes) and the no change
rule: a reset on a text without `max-width` must not rebuild the attribute, which would rewrite its separators.

## Requirements covered

- SPEC-0015/FR-NEW-006: WHEN the width bar has the keyboard focus and the author presses Right or Left THE editor SHALL save the text's width as its current width on the slide, rounded to a whole pixel, plus or minus 10 pixels, kept between 80 and 1280.
- SPEC-0015/FR-NEW-007: WHEN the author double clicks the width bar, or presses Delete or Backspace while it has the focus, THE editor SHALL remove the `max-width` declaration from the text's inline style and save.
- SPEC-0015/FR-NEW-008: IF a width action leaves the text's inline style text identical THEN THE editor SHALL save nothing and record no undo step.
- SPEC-0015/FR-NEW-009: WHEN a width change is saved THE editor SHALL record it as one structural undo step that Undo reverts and Redo reapplies, each saving the file.
- SPEC-0015/NFR-002: The bar SHALL be reachable by a click and usable with the keyboard alone once focused (FR-NEW-006, FR-NEW-007), and SHALL show a visible focus outline.

Business rules (spec, verbatim): "with Shift held the step is 50. Each press is one saved change, written as in
FR-NEW-005. Other keys keep their usual effect." Reset: "the other declarations are kept as in FR-NEW-005, the same
separator rule included. When none is left the style attribute is removed entirely." FR-NEW-008 "covers a press and
release without movement, a drag ending on the value already written, a key press at a bound, and a reset on a text
without inline width." FR-NEW-009: "SPEC-0002/FR-009, FR-010 and FR-011 apply unchanged (buttons, shortcuts, the
shortcut left to the browser while it has typing to revert, at most 50 steps, a new change clears Redo). Undo
restores the inline style text exactly as it was before the change."

## Independent Test

`make test ARGS='-k width_keys_undo'`: the fourteen tests below pass, reading the file on disk and the
`#undo-btn` / `#redo-btn` `disabled` state; for example after Right, Shift+Right, Left the file holds
`max-width:650px` and three Undo clicks bring back `max-width:600px`.

## Design excerpt

### Decisions
- DEC-003 (SPEC-0015): the saved style is rebuilt as text and written with `setAttribute('style', text)`, or `removeAttribute('style')` when the reset leaves nothing; never through the style object.
- DEC-004 (SPEC-0015): "`captureDomSnapshot` wraps its `outerHTML`" in `withWidthPreviewSuspended` (this story; `editor-undo.js:46`).
- DEC-007 (SPEC-0015): "Commit: original text back, `snapshotForUndo()`, new text set, `markPending()`, `saveContent()`. Keyboard and reset use the same commit; a reset on a text where `styleHasWidth` is false does nothing (no rebuild, so the separators of the other declarations are never rewritten, E2E-012). `dblclick` on the bar resets."
- Keyboard (design 5.3): "`Math.round(parseFloat(getComputedStyle(block).width))` plus or minus 10 (50 with Shift), clamped. Keys handled on the bar: `ArrowRight`, `ArrowLeft` (with or without Shift), `Delete`, `Backspace`; each is `preventDefault`ed; every other key keeps its default."
- Focus outline (design 5.1): the CSS rule is `#width-bar:focus` (not `:focus-visible`, which Chromium does not apply after a mouse click).
- DEC-011 (SPEC-0015): shared module page, one server per test, no late save variant.

### Contracts
`styleWithoutWidth(text)` (US-0089) returns `null` when nothing is left: then `removeAttribute('style')`.
Existing undo API (`editor-undo.js`): `snapshotForUndo()` (pushes the current document, clears redo, caps at 50),
`performUndo()`, `performRedo()` (restore through `doc.write`, then `saveContent()`), `undoBtn`, `redoBtn`.
After Undo or Redo the frame reloads (`onFrameLoad`), so the bar is hidden and the block reference stale: tests
point at the block and click the bar again before the next key.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-width.js` | modify: `keydown` and `dblclick` on the bar, `commitWidthStyle`, reset |
| `src/mcp_htmleditor/static/editor-undo.js` | modify: `const html = withWidthPreviewSuspended(() => doc.documentElement.outerHTML);` |
| `src/mcp_htmleditor/static/editor.css` | modify: `#width-bar:focus { outline: 2px solid ...; outline-offset: 1px }` |
| `tests/width_support.py` | modify: `focus_bar(page, block_selector)`, `undo_disabled(page)` |
| `tests/test_width_keys_undo_e2e.py` | create |

### Existing patterns
- `tests/test_undo_redo_e2e.py` for the Undo and Redo buttons and the `MOD` key (`Meta` on Darwin, else `Control`).
- Absence (no save): `wait_until` on the cause, `settle(page)`, then `window.__widthSaves` unchanged and the file byte identical (SPEC-0014/BR-010).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

All: functional e2e, Playwright Chromium, shared module page, `tests/test_width_keys_undo_e2e.py`, fixture D1 on
slide 2, edit mode on. "clicked X's bar" = point at X, click the bar (it takes the focus).

### SPEC-0015/E2E-008: Keyboard steps
- Given D1 on slide 2, the author clicked A's bar (A is 600 wide) / When they press Right, then Shift and Right, then Left
- Then A's style reads `max-width:610px`, then `max-width:660px`, then `max-width:650px`, each saved
- And three Undo presses bring A back to `max-width:600px`

### SPEC-0015/E2E-009: Key at the lower bound saves nothing
- Given D1, the author clicked I's bar (I is 85 wide) / When they press Left, then Left
- Then after the first press I's style reads `max-width:80px`; the second press saves nothing and leaves the file unchanged; one Undo brings back `max-width:85px` and Undo is then disabled

### SPEC-0015/E2E-010: Double click gives the template's width back
- Given D1 on slide 2 / When the author double clicks A's bar
- Then paragraph A in the file has no style attribute at all, the save status shows saved, and A is 800 pixels wide

### SPEC-0015/E2E-011: Reset keeps the other declarations
- Given D1 / When the author double clicks H's bar
- Then H's style reads exactly `color:#525252; font-size:10px`

### SPEC-0015/E2E-012: Reset without an inline width does nothing
- Given D1, Undo disabled / When the author double clicks B's bar twice
- Then the file is byte identical to before, no save happens, Undo stays disabled

### SPEC-0015/E2E-013: Delete and Backspace reset
- Given D1, the author clicked A's bar / When they press Delete
- Then A has no style attribute in the file
- And with I's bar focused, Backspace leaves I without style attribute

### SPEC-0015/E2E-014: Undo then redo a drag
- Given E2E-001 just done (A dragged 47 pixels right, file holds `max-width:650px`) / When the author clicks Undo, then Redo
- Then after Undo the file's A style reads `max-width:600px` and A is 600 wide; after Redo `max-width:650px`; both saved

### SPEC-0015/E2E-015: The shortcut reverts typing first
- Given D1, the author drags A's bar until the readout shows `650 px`, then clicks at the end of paragraph J and types `!`
- When they press Ctrl or Cmd with Z once, caret still in J
- Then J reads `Hors charte` again and A's style still reads `max-width:650px`

### SPEC-0015/E2E-016: A new width change clears Redo
- Given E2E-014's Undo done (A at 600, Redo enabled) / When the author presses Right on A's focused bar
- Then A reads `max-width:610px` and Redo is disabled

### SPEC-0015/E2E-020: Press and release without moving
- Given D1 / When the author presses A's bar and lets go without moving
- Then no save happens and Undo stays disabled

### SPEC-0015/E2E-030: Name, tooltip and focus
- Given D1, bar shown on A / When the author hovers it, then clicks it
- Then the tooltip reads `Glisser pour régler la largeur, double clic pour revenir à la largeur du modèle`, the accessible name is `Largeur du texte`, after the click it has the keyboard focus with a visible outline (`document.activeElement.id == "width-bar"` and computed `outline-style` not `none`), and Right then works (A `max-width:610px`)

### SPEC-0015/E2E-037: Other keys do not change the width
- Given D1, the author clicked A's bar / When they press Up, Down, `a` and Enter
- Then the file is unchanged and Undo is disabled

### SPEC-0015/E2E-038: Keys start from the width on the slide
- Given D1, paragraph K (`max-width:1250px`) is 800 pixels wide in its column / When the author clicks K's bar and presses Right
- Then K's style reads `max-width:810px`

### SPEC-0015/E2E-040: A reload empties the history
- Given E2E-001 done (A at 650) / When the author reloads the editor page
- Then Undo is disabled and A stays `max-width:650px` in the file

## Constraints

- Files not to touch: `editor-save.js` beyond US-0089, `http_server.py`, Python product modules.
- Dependencies not to add: none.
- Patterns to avoid: snapshot at `pointerdown` or before knowing the text changes; rebuilding the style for a reset when `styleHasWidth` is false; handling keys other than the six listed.
- Scope boundary: visibility rules are US-0091; cancel and failures are US-0092.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_undo_redo_e2e.py` (8 tests, both save variants) and `tests/test_width_drag_e2e.py` unchanged and green.
- [ ] Run time: `make test ARGS='-k width_keys_undo --durations=0'` recorded; the file takes at most 10 s.
- [ ] Docs updated: none in this story (US-0093).
- [ ] Self review: full (tier 1), including what Undo restores when the typing autosave landed between the snapshot and the commit.
- [ ] One commit `US-0090: Keyboard steps, reset and undo of a width`, body `Spec: SPEC-0015` and FR-NEW-006, FR-NEW-007, FR-NEW-008, FR-NEW-009, NFR-002.
