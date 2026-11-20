# SPEC-0030: Editor style writes that keep the author's other declarations, design

> Spec: sdlc/specs/SPEC-0030-style-writes-kept-as-text/spec.md
> Nature: BUG
> Depth: M
> Security: n/a
> Designed on: 2026-11-20
> Target tier: 2 (default)

## 1. Stack and skills
Existing stack: vanilla JS editor scripts, Playwright e2e (Python, pytest, `make check`). No dependency. Skill python: `make` only.

## 2. Approaches
### Chosen: a text level setter on top of the SPEC-0020 scanner; the loaded `<html>` text kept by the editor and restored on save
BL-0043: replace each `el.style.x = v` on author content by `setStyleDeclarations(el, {x: v})`, which edits the attribute text through `splitStyleDeclarations` (comment aware) and writes nothing when no change is needed. BL-0042: the deck's runtime owns the presenting scale and runs outside the editor, so the editor remembers `<html>`'s style text at each real load and the save writes that text (minus a top level `--fs-scale`, SPEC-0020/BR-004). Pros: no template change (24 hits in 13 files), no other deck changes; one setter for five sites. Cons: the editor holds one extra variable.
### Rejected: move the scale to a deck node (`--fs-scale` on `.slide-frame`) in the 13 templates
13 files, the pointer sync tooling and the fullscreen guard test to change, and the same strip still needed for older decks (DEC-004).
### Rejected: the setter rewrites the whole text through a CSS parser
Reserializes (the defect itself) (DEC-001).

## 3. Architecture
`editor-width.js` (style text section): `styleWithDeclarations(text, values)` and `setStyleDeclarations(el, values)`. Callers: `editor-menus.js` (Gantt resize, legacy diagram node add), `editor-drag.js` (`enableArchNodeDrag`, `makeArchNodeDraggable`, the press handler, `applyArchNodePosition`). `editor.js` `onFrameLoad` stores `loadedHtmlStyle`; `editor-save.js` `stripPresentingState` restores it before removing `--fs-scale`.

## 4. Data model
None.

## 5. Contracts and interfaces
- `styleWithDeclarations(text, values) -> string`: `values` maps a lower case property name to its value text; the pieces of `text` come from `splitStyleDeclarations`; a piece whose name (`styleDeclarationName`) is in `values` is replaced in place by `name:value` (no space after the colon), later pieces of the same name are dropped; names not found are appended in the order of `values`; joined with `'; '`.
- `setStyleDeclarations(el, values)`: does nothing when every name of `values` already has exactly one declaration whose value (text after the first `:` outside comments, trimmed) equals the wanted one; otherwise `el.setAttribute('style', styleWithDeclarations(el.getAttribute('style') || '', values))`.
- `loadedHtmlStyle` (module variable of `editor-save.js`, `undefined` until the first load): the `style` attribute text of `<html>` (`null` when absent) at the last load that is not an Undo or Redo restore (`restoringFromUndo` false).
- `stripPresentingState(root)`: first, when `loadedHtmlStyle !== undefined`, `root` gets that text (`removeAttribute('style')` when `null`); then the existing top level `--fs-scale` removal (SPEC-0020/BR-004).
- Arch node press: `makeArchNodeDraggable`'s `onDown` no longer writes `position`; the write happens in `applyArchNodePosition` at the first movement.

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/static/editor-width.js` | modify: the two functions | BR-001..BR-004 | US-0167 |
| `src/mcp_htmleditor/static/editor-menus.js` | modify: Gantt resize (195, 200), legacy node add (282) | BR-001, BR-002 | US-0167 |
| `src/mcp_htmleditor/static/editor-drag.js` | modify: 159, 179, 195, 236-238 | BR-002, BR-003, BR-004 | US-0167 |
| `tests/style_text_support.py` | modify: fixture Deck S2 | tests | US-0167 |
| `tests/test_style_text_actions_e2e.py` | create | BT-002..BT-008 | US-0167 |
| `src/mcp_htmleditor/static/editor.js` | modify: capture in `onFrameLoad` | BR-005 | US-0168 |
| `src/mcp_htmleditor/static/editor-save.js` | modify: `loadedHtmlStyle`, restore | BR-005 | US-0168 |
| `tests/test_style_text_presenting_e2e.py` | create | BT-001, BT-009 | US-0168 |
| `AGENTS.md`, `.agent_docs/testing.md` | modify | docs | US-0168 |
Affected existing tests: none modified (spec 4.4).

## 7. Compatibility and risks
Additive for the file text: authors keep their declarations. A diagram or Gantt task written by hand gets `; ` separators when an action writes it (SPEC-0015 form). Risk: the press no longer sets `position:absolute` before the first movement; the rectangle is read at the press, unchanged. Rollback: revert.

## 9. Test strategy
| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| BT-002..BT-008 | functional e2e | Chromium, real server, file on disk | `tests/test_style_text_actions_e2e.py` | US-0167 |
| BT-001, BT-009 | functional e2e | same | `tests/test_style_text_presenting_e2e.py` | US-0168 |
| BT-010, BT-011 | non regression | existing tests | `tests/test_reference_decks_present_e2e.py`, `tests/test_style_text_*_e2e.py` | US-0168 |

## 10. Decisions log
- **DEC-001:** edit style text, never write through `el.style` on author content. **Obliged by:** SPEC-0030/BR-001..BR-004, BR-006. **Alternatives considered:** a CSS parser rewrite. **Source:** SPEC-0020 DEC-001. **Evidence:** `editor-menus.js:195,200,282`, `editor-drag.js:159,179,195,236-238`.
- **DEC-002:** one setter `setStyleDeclarations` that writes nothing when nothing changes. **Obliged by:** SPEC-0030/BR-002, BR-003. **Source:** design.
- **DEC-003:** the position of a pressed node is written at the first movement only. **Obliged by:** SPEC-0030/BR-003. **Evidence:** `editor-drag.js:195,236`.
- **DEC-004:** the editor restores `<html>`'s loaded text on save instead of changing the 13 templates. **Obliged by:** SPEC-0030/BR-005, BR-006. **Alternatives considered:** move the scale to a deck node. **Source:** design. **Evidence:** `rg -c "setProperty\('--fs-scale'" templates`: 24 hits in 13 files; `templates/bootstrap/slides-empty.html:374-385`.
- **DEC-005:** `loadedHtmlStyle` is captured at the top of `onFrameLoad`, skipped while `restoringFromUndo`. **Obliged by:** SPEC-0030/BR-005 (survives Undo and Redo). **Evidence:** `editor.js:322-347`.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0167 | actions set one declaration as text | P1 | BR-001, BR-002, BR-003, BR-004, BR-006, BR-007 | main | 2 | no |
| US-0168 | the loaded html style text survives presenting | P1 | BR-005, BR-006 | US-0167 | 2 | yes |
