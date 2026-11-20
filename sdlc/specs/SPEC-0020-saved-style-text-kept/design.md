# SPEC-0020: Saved style text kept as written, design

> Spec: sdlc/specs/SPEC-0020-saved-style-text-kept/spec.md
> Nature: BUG
> Depth: M
> Security: n/a
> Designed on: 2026-11-20
> Target tier: 2 (default)

## 1. Stack and skills
Existing stack: vanilla JS editor scripts (`src/mcp_htmleditor/static/`, no build step, `node --check`), Playwright e2e tests (Python, pytest, `make check`). No dependency. Skill python: `make` only.

## 2. Approaches
### Chosen: stop writing through the style object; marks as an attribute removed by the one artifact strip; one comment aware scanner for style text
Root cause is the lossy write through `el.style` (reserialization). Fix at the sites the spec lists: remove the two clearing writes of the shared strip (BR-001, BR-002), make the existing text splitter understand comments and reuse its scanner for the presenting strip (BR-003, BR-004), carry the editor's transient marks in a `data-mcp-mark` attribute styled by the injected sheet and removed by the strip (BR-005, BR-006). Pros: no style attribute is ever rewritten by the editor; one strip, one scanner. Cons: three kinds of change in one script family.
### Rejected: save a clone with the editor's inline marks cleaned by `cssText`
Reserializes the attribute (the defect itself) (DEC-001).
### Rejected: marks as classes
`classList` rewrites the author's `class` text and the server strips `_mcp` classes only on save, not in the undo snapshot (DEC-004).

## 3. Architecture
`editor-save.js` `stripEditorArtifacts` (shared by `saveContent` on a clone and `captureDomSnapshot` on the live document, `editor-undo.js:27-34`) loses its `outline` and `cursor` writes and gains the removal and restoration of `[data-mcp-mark]` attributes. `editor-width.js` `splitStyleDeclarations`, `styleDeclarationName` become comment aware and expose one raw scanner `splitStyleRaw` that `editor-save.js` `stripPresentingState` reuses. `editor-menus.js` connect mode and `editor-format.js` drop indicator set and clear `data-mcp-mark` instead of style properties; `editor-edit.js` `injectEditorStyles` gets the three CSS rules.

## 4. Data model
None. The attribute `data-mcp-mark` exists only in the editor's live document.

## 5. Contracts and interfaces
- `splitStyleRaw(text) -> string[]`: the pieces of `text` cut at each top level `;` (outside comments, parentheses, quotes), untrimmed, empties kept, so `pieces.join(';') === text`. Comment rule: `/*` outside quotes and parentheses opens a comment that runs to the next `*/` (or to the end of the text); inside it quotes, parentheses and `;` are plain text.
- `splitStyleDeclarations(text)` = `splitStyleRaw(text)` trimmed, empties dropped.
- `styleDeclarationName(declaration)`: text before the first `:` outside a comment, comments removed, trimmed, lower case; a piece with no `:` outside a comment returns a name that is never `max-width` (the piece is kept).
- `stripPresentingState`: pieces whose name (comments removed, trimmed, case sensitive) is `--fs-scale` are dropped, the others rejoined with `;`; an empty or `;` only result removes the attribute; unchanged text is not rewritten.
- `data-mcp-mark` values: `connect-source` (on the source node), `connect-pointer` (on `<body>`), `drop` (on the editable zone). CSS in `injectEditorStyles`: `[data-mcp-mark="connect-source"] { outline: 3px solid #0f62fe !important; }`, `body[data-mcp-mark="connect-pointer"] { cursor: crosshair; }`, `[data-mcp-mark="drop"] { box-shadow: inset 0 0 0 3px #0f62fe !important; }`.
- `stripEditorArtifacts(root)` removes every `[data-mcp-mark]` attribute and its restore puts each back with its value.

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/static/editor-save.js` | modify: no style writes in the strip, `data-mcp-mark` removal and restore, `stripPresentingState` uses the scanner | BR-001, BR-002, BR-004, BR-005 | US-0163, US-0164, US-0165 |
| `src/mcp_htmleditor/static/editor-width.js` | modify: comment aware scanner | BR-003 | US-0164 |
| `src/mcp_htmleditor/static/editor-menus.js` | modify: connect mode marks | BR-005 | US-0165 |
| `src/mcp_htmleditor/static/editor-format.js` | modify: drop indicator mark | BR-006 | US-0166 |
| `src/mcp_htmleditor/static/editor-edit.js` | modify: the three CSS rules | BR-005, BR-006 | US-0165, US-0166 |
| `tests/style_text_support.py` | create: Deck S and helpers | tests | US-0163 |
| `tests/test_style_text_save_e2e.py`, `tests/test_style_text_width_e2e.py`, `tests/test_style_text_marks_e2e.py` | create | BT-001.. | US-0163, US-0164, US-0165/0166 |
| `.agent_docs/html-conventions.md`, `.agent_docs/testing.md` | modify: the rule "never write the style object of author content", file map | docs | US-0166 |
Affected existing tests: none modified (spec 4.4, all kept).

## 7. Compatibility and risks
Files saved before the fix may hold reserialized styles; they are valid and unchanged by the new code. Risk: Chromium treats `!important` in the injected sheet over inline author `outline` (needed for BT-017's computed outline); the author's inline value is untouched. Rollback: revert; no data.

## 9. Test strategy
| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| BT-001, BT-010, BT-011, BT-020, BT-022 | functional e2e | Chromium, real server, file on disk | `tests/test_style_text_save_e2e.py` (BT-022 runs the existing autosave tests) | US-0163 |
| BT-012, BT-013, BT-014, BT-023, BT-015, BT-016 | functional e2e | same | `tests/test_style_text_width_e2e.py` | US-0164 |
| BT-021 | non regression | existing test | `tests/test_reference_decks_present_e2e.py` | US-0164 |
| BT-017, BT-018 | functional e2e | same | `tests/test_style_text_marks_e2e.py` | US-0165 |
| BT-019 | functional e2e | same | `tests/test_style_text_marks_e2e.py` | US-0166 |
Fixture Deck S in `tests/style_text_support.py` built from `deck_d1()` (`tests/width_support.py:113`) as the spec section 4 describes.

## 10. Decisions log
- **DEC-001:** no write through `el.style` on author content; text level edits only. **Obliged by:** SPEC-0020/BR-001, BR-002, BR-005, BR-006. **Alternatives considered:** `cssText` rebuild. **Source:** spec root cause. **Evidence:** `editor-save.js:63-80`.
- **DEC-002:** one scanner `splitStyleRaw` shared by the width actions and the presenting strip. **Obliged by:** SPEC-0020/BR-003, BR-004. **Alternatives considered:** a second regex in `editor-save.js`. **Source:** design. **Evidence:** `editor-width.js:34-58`, `editor-save.js:93-97`.
- **DEC-003:** the strip drops `--fs-scale` pieces case sensitively, other names untouched. **Obliged by:** SPEC-0020/BR-004. **Source:** spec.
- **DEC-004:** transient marks are one attribute `data-mcp-mark`, removed by `stripEditorArtifacts` for the clone and the live snapshot. **Obliged by:** SPEC-0020/BR-005, BR-006. **Alternatives considered:** classes. **Source:** design.
- **DEC-005:** the mark look lives in the injected stylesheet with `!important` so the author's inline declaration stays untouched and still shows after the mode. **Obliged by:** SPEC-0020/BR-005 (look unchanged), BR-006.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0163 | a save and an undo snapshot keep every style text | P1 | BR-001, BR-002 | main | 2 | no |
| US-0164 | width actions and the presenting strip read comments | P1 | BR-003, BR-004 | US-0163 | 2 | no |
| US-0165 | connect mode leaves no mark | P1 | BR-005 | US-0163 | 2 | no |
| US-0166 | the drop indicator leaves no mark, documentation | P1 | BR-006 | US-0164, US-0165 | 2 | yes |
