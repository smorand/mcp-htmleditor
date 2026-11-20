# US-0165: connect mode leaves no mark

> Spec: SPEC-0020 (sdlc/specs/SPEC-0020-saved-style-text-kept/)
> Nature: BUG
> Priority: P1
> Depends on: US-0163
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective
The connect mode of a declarative diagram shows its outline and crosshair without writing them into the author's style attributes, the saved file or an undo snapshot. Introduces the `data-mcp-mark` attribute and its removal by the one artifact strip.

## Requirements covered
- SPEC-0020/BR-005 [EARS-UB]: The editor SHALL NOT write the connect mode marks of a declarative diagram into the saved file, into an undo snapshot, or into the attribute text of the source node and of `<body>`. While the mode is active the source node still shows a 3 pixel `#0f62fe` outline and the pointer is a crosshair; when it ends by Escape or a click on the source, both attribute texts are exactly as before the mode; when it ends by an edge created, `<body>`'s attribute text is as before and the source's `style` holds the author's declarations with no mark, plus only what the layout run writes (`position`, `left`, `top`, `width`, `height`). Exact names: menu entry `➜ Créer une arête depuis ce nœud`; key `Escape`.

## Independent Test
`make test ARGS='tests/test_style_text_marks_e2e.py -k connect'` green, `make check` green.

## Design excerpt
### Decisions
DEC-004 transient marks are one attribute `data-mcp-mark` removed by `stripEditorArtifacts` for the clone and the live snapshot; DEC-005 the look lives in the injected sheet with `!important`.
### Contracts
`src/mcp_htmleditor/static/editor-menus.js` `startArchConnect` (line ~119): replace `sourceNode.style.outline = '3px solid #0f62fe'; doc.body.style.cursor = 'crosshair';` by `sourceNode.setAttribute('data-mcp-mark', 'connect-source'); doc.body.setAttribute('data-mcp-mark', 'connect-pointer');`; `cancelArchConnect` (line ~139) removes both attributes (`removeAttribute('data-mcp-mark')`).
`src/mcp_htmleditor/static/editor-edit.js` `injectEditorStyles` (line ~86): add `[data-mcp-mark="connect-source"] { outline: 3px solid #0f62fe !important; }` and `body[data-mcp-mark="connect-pointer"] { cursor: crosshair; }`.
`src/mcp_htmleditor/static/editor-save.js` `stripEditorArtifacts`: collect `[data-mcp-mark]` elements of `root` (and `root` itself when it carries the attribute) with their values, remove the attribute, and re-set each in `restore`. Update the doc comment.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-menus.js` | modify |
| `src/mcp_htmleditor/static/editor-edit.js` | modify |
| `src/mcp_htmleditor/static/editor-save.js` | modify |
| `tests/test_style_text_marks_e2e.py` | create |
### Existing patterns
`tests/style_text_support.py` (US-0163); `tests/width_support.py` helpers; the diagram context menu entry text `➜ Créer une arête depuis ce nœud` (`editor-menus.js`), the label prompt (`prompt('Libellé de l\'arête (optionnel) :', '')`: accept it with Playwright's dialog handler).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc. Deck S as in US-0163; slide 3 shown (title `Objets`).
### SPEC-0020/BT-017: connect mode, save during the mode, then Escape
- Given Deck S served, slide 3, edit mode on
- When the person right clicks `Serveur MCP`, chooses `➜ Créer une arête depuis ce nœud`, clicks at the end of the slide title `Objets` (not a node, the mode stays active), types `X`, the autosave writes the file, then presses Escape
- Then during the mode `Serveur MCP` shows a computed outline `rgb(15, 98, 254) solid 3px`; the file holds `n1` with `style="outline:1px dashed #8D8D8D;background:#EDF5FF"`, a `<body>` with no `style` attribute and no `data-mcp-mark`, and `ObjetsX`; after Escape `n1`'s live attribute text is `outline:1px dashed #8D8D8D;background:#EDF5FF` and `<body>` has no `style` attribute
### SPEC-0020/BT-018: connect mode, the undo snapshot holds no mark
- Given Deck S served, slide 3, edit mode on
- When the person right clicks `Serveur MCP`, chooses the entry, clicks `Base`, accepts the label prompt empty, waits for the save, then clicks `#undo-btn` and waits for the save
- Then the file holds no `arch-edge` element, `n1`'s style holds `outline:1px dashed #8D8D8D` and no other `outline` (the layout run may add position declarations, only the outline is asserted), the file holds no `crosshair` and no `data-mcp-mark`, and `<body>` has no `style` attribute

## Constraints
- Files not to touch: `editor-width.js`, `editor-format.js`, existing tests.
- Dependencies not to add: none.
- Scope boundary: the drop indicator and the docs are US-0166.

## Definition of done
- [ ] RED evidence for BT-017 and BT-018 before the fix.
- [ ] Every test above green; `node --check src/mcp_htmleditor/static/*.js` clean; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_editor_artifact_strip.py`, `tests/test_undo_redo_e2e.py` unchanged and green.
- [ ] One commit `US-0165: connect mode leaves no mark`, body with `Summary:`, `Spec: SPEC-0020` and the requirement ids.
