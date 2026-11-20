# US-0167: actions set one declaration as text

> Spec: SPEC-0030 (sdlc/specs/SPEC-0030-style-writes-kept-as-text/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective
The Gantt resize, the positioning context of a diagram and the press and move of an arch node change only their own declarations; every other declaration of the style keeps its text, and a press without movement writes nothing.

## Requirements covered
- SPEC-0030/BR-001: WHEN the person chooses `Agrandir (+20%)` or `Réduire (-20%)` on a Gantt task THE editor SHALL set the task's `width` declaration to the new percentage with one decimal and SHALL keep every other declaration as written. Base: the number of the inline `width`, or 30 when none or not a number; at most 100 for grow (x 1.2), at least 5 for shrink (x 0.8).
- SPEC-0030/BR-002: WHEN the editor makes an arch diagram whose computed position is `static` a positioning context (edit mode entry, wiring a node, adding a node to a legacy diagram) THE editor SHALL set only `position:relative` and keep the others as written, and write nothing when it already is one.
- SPEC-0030/BR-003: a press and release on an arch node without movement leaves its style attribute text exactly as it was; the position declarations are written at the first movement only.
- SPEC-0030/BR-004: WHEN the person moves an arch node THE editor SHALL set its `position:absolute`, `left` and `top` (percent, one decimal), keep the other declarations as written, and keep writing `data-x`, `data-y`, `data-layout="manual"`.
- SPEC-0030/BR-006 (partial: these actions): no other element's attribute text changes.
- SPEC-0030/BR-007: Undo restores the exact style text, in the document shown and in the file saved after the Undo.
"Set a declaration": replace the first declaration of that name in place (later ones dropped) or append it; only a style actually written is rejoined with `; `; a style that needs no change is not written.

## Independent Test
`make test ARGS='tests/test_style_text_actions_e2e.py'` green, `make check` green; BT-002 reads `left: 0%; width: 30%; background: rgb(15, 98, 254);` before the change.

## Design excerpt
### Decisions
DEC-001 text level edits; DEC-002 one setter that writes nothing when nothing changes; DEC-003 position written at first movement.
### Contracts
`src/mcp_htmleditor/static/editor-width.js` (style text section, after `styleWithoutWidth`):
```
function styleWithDeclarations(text, values)   // values: {name: value}, names lower case
function setStyleDeclarations(el, values)
```
`styleWithDeclarations`: pieces = `splitStyleDeclarations(text || '')`; a piece whose `styleDeclarationName` is in `values` is replaced in place by `name:value` (first occurrence), later pieces of that name dropped; names not found appended in `values` order; `join('; ')`. `setStyleDeclarations`: return when each name of `values` has exactly one declaration whose value (text after the first `:` outside comments, trimmed) equals the wanted one; else `el.setAttribute('style', styleWithDeclarations(el.getAttribute('style') || '', values))`.
`editor-menus.js:195`: `el.style.width = Math.min(...)` becomes `setStyleDeclarations(el, {width: Math.min(100, (parseFloat(el.style.width) || 30) * 1.2).toFixed(1) + '%'})`; `:200` likewise with `Math.max(5, ... * 0.8)`. `:282`: `if (getComputedStyle(el).position === 'static') setStyleDeclarations(el, {position: 'relative'});`.
`editor-drag.js:159` and `:179`: `diagram.style.position = 'relative'` becomes `setStyleDeclarations(diagram, {position: 'relative'})` (same `static` condition). `:195` (`node.style.position = 'absolute'` in `onDown`): remove. `applyArchNodePosition` (`:233-239`): keep the three `dataset` writes, replace the three style writes by `setStyleDeclarations(node, {position: 'absolute', left: x.toFixed(1) + '%', top: y.toFixed(1) + '%'})`.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-width.js` | modify |
| `src/mcp_htmleditor/static/editor-menus.js` | modify |
| `src/mcp_htmleditor/static/editor-drag.js` | modify |
| `tests/style_text_support.py` | modify: Deck S2 |
| `tests/test_style_text_actions_e2e.py` | create |
### Existing patterns
`tests/style_text_support.py` (`deck_s`, `serve_deck_s`, `live_style`, `type_in_first_paragraph`), `tests/test_style_text_marks_e2e.py` (diagram on slide 3, context menu `#_editor_ctx_host div:text-is(...)`, `_open_slide_3`), `tests/test_undo_redo_e2e.py::test_undo_redo_arch_node_reposition` (node drag with the mouse, live `left`/`top`).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.
**Deck S2** = Deck S plus: slide 3's Gantt task `Cadrage` styled `left:0%; width:25%; background:#0F62FE`; the declarative diagram's node `n2` styled `position:absolute; left:10%; top:10%; width:20%; height:20%`; `<html>` style `color:#161616`; a second legacy diagram on slide 3, `<div data-type="arch-diagram" style="width:100%; height:200px;">` holding one legacy node (no `arch-row`; its menu has `＋ Ajouter nœud`). The declarative diagram has `position:relative`. Extend `deck_s` with a parameter or build `deck_s2()` in `tests/style_text_support.py`.
### SPEC-0030/BT-002: Gantt resize keeps the other declarations (reproduction)
- Given Deck S2 served, slide 3, edit mode on / When the person right clicks the task `Cadrage`, chooses `Agrandir (+20%)` and the autosave writes the file / Then the task's style in the file is `left:0%; width:30.0%; background:#0F62FE`
### SPEC-0030/BT-003: Gantt shrink
- `Réduire (-20%)` on `Cadrage` gives `left:0%; width:20.0%; background:#0F62FE`
### SPEC-0030/BT-004: press without moving
- Given Deck S2, slide 3, edit mode on / When the person presses `Base` (`n2`) with the left button and releases without moving, then types `X` in the slide title `Objets` and the autosave writes / Then `n2`'s style in the file is `position:absolute; left:10%; top:10%; width:20%; height:20%`, `n1`'s is `outline:1px dashed #8D8D8D;background:#EDF5FF`, and `n2`'s `contenteditable` attribute is as before the press
### SPEC-0030/BT-005: node move
- When the person drags `Serveur MCP` (`n1`) by 30 pixels and the autosave writes / Then `n1`'s style in the file begins `outline:1px dashed #8D8D8D; background:#EDF5FF; position:absolute; left:` and has `left` and `top` once each, both ending `%`; dragging `n2` likewise gives `position:absolute; left:<x>%; top:<y>%; width:20%; height:20%` (width and height as written)
### SPEC-0030/BT-006: positioning context at edit mode entry
- Given the legacy diagram of Deck S2 / When edit mode is entered and the autosave writes after a typed `X` / Then its style in the file is `width:100%; height:200px; position:relative`; a diagram already `position:relative; width:100%; height:200px;` is saved byte for byte
### SPEC-0030/BT-007: adding a node to a static legacy diagram
- Given Deck S2 served, slide 3, edit mode OFF (the context menus exist without edit mode; entering edit mode would already make the diagram relative) / When the person right clicks the legacy diagram, chooses `＋ Ajouter nœud`, accepts the label prompt and the autosave writes / Then the diagram's style in the file ends with `; position:relative` and its other declarations are as written
### SPEC-0030/BT-008: undo restores the exact text
- When the person resizes `Cadrage` (BT-002) then clicks `#undo-btn` / Then the task's style in the file is `left:0%; width:25%; background:#0F62FE` and its live attribute text is the same

## Constraints
- Files not to touch: `editor-save.js`, `editor.js`, templates, existing tests.
- Dependencies not to add: none.
- Scope boundary: the `<html>` style is US-0168.

## Definition of done
- [ ] RED evidence for BT-002, BT-004, BT-005, BT-006, BT-007 (and BT-003, BT-008) before the fix.
- [ ] Every test above green; `node --check src/mcp_htmleditor/static/*.js` clean; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_undo_redo_e2e.py`, `tests/test_style_text_*_e2e.py`, `tests/test_width_*` unchanged and green.
- [ ] One commit `US-0167: actions set one declaration as text`, body with `Summary:`, `Spec: SPEC-0030` and the requirement ids.
