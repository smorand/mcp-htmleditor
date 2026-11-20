# US-0163: a save and an undo snapshot keep every style text

> Spec: SPEC-0020 (sdlc/specs/SPEC-0020-saved-style-text-kept/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective
A save, a width action and an undo snapshot stop deleting or reserializing an author's `cursor`, `outline` and the rest of an editable element's inline style. Creates the shared fixture Deck S.

## Requirements covered
- SPEC-0020/BR-001 [EARS-E]: WHEN the editor saves THE editor SHALL write the `style` attribute of every element of the document with the attribute text it has in the document shown, and SHALL NOT remove an `outline` or `cursor` declaration written by the author or an agent. (`style` absent stays absent, `style=""` is saved as `style=""`, a save during a width drag holding `cursor` writes the attribute as before the drag.)
- SPEC-0020/BR-002 [EARS-UB]: an undo snapshot SHALL NOT change the live attribute text of any style; an Undo or Redo writes, through BR-001, the texts the snapshot holds.

## Independent Test
`make test ARGS='tests/test_style_text_save_e2e.py'` green; before the change BT-001 reads `style="color: rgb(15, 98, 254);"` for J.

## Design excerpt
### Decisions
DEC-001 no write through `el.style` on author content. The look of an editable zone is the class `_mcp_editable` styled by the injected sheet (`editor-edit.js:86-88`), never an inline style.
### Contracts
In `src/mcp_htmleditor/static/editor-save.js` `stripEditorArtifacts` (lines 60-84): remove `outline` and `cursor` from the `backup` objects, from the `editables.forEach` writes (`el.style.outline = ''; el.style.cursor = '';`) and from `restore`; keep `contenteditable` removal and its restoration, the bars and the drag artifacts. Update the function's doc comment (it no longer touches an outline or cursor). Nothing else changes.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-save.js` | modify |
| `tests/style_text_support.py` | create (Deck S, helpers shared by the three test files of this spec) |
| `tests/test_style_text_save_e2e.py` | create |
### Existing patterns
`tests/test_width_drag_e2e.py:55-67` (drag 47 px right gives 650 px), `tests/width_support.py` (`width_page` one Chromium page per module, `open_editor`, `show_slide_2`, `drag_bar`, `markers_in`, `PARAGRAPH`), `tests/test_editor_artifact_strip.py` (structure of the strip, kept).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc. Budget: the three test files of this spec add at most 8 s together to `make check`; share one Chromium page per module like `width_page`.
**Deck S** (built in `tests/style_text_support.py` from `deck_d1()`, `tests/width_support.py:113`; the paragraphs are the `PARAGRAPHS` tuples, selectors in `PARAGRAPH`): on slide 2 replace the styles and texts: J `style="cursor:pointer;color:#0F62FE"` text `Hors charte`; I `style="outline:1px solid #FF0000;font-weight:600"` text `Mini`; P `style="color:red /* a;b */;font-weight:600"` text `Agent`; K `style="color:red /* it's */;max-width:600px"` text `Large`; H `style="/* note */ max-width:600px;color:#525252"` text `Objectifs`; `<html ... style="color:#161616 /* x;--fs-scale:9 */">`; slide 3: its diagram replaced by `<div data-type="arch-diagram" style="position:relative; width:100%; height:200px;"><div data-type="arch-row"><div data-type="arch-node" data-id="n1" data-label="Serveur MCP" style="outline:1px dashed #8D8D8D;background:#EDF5FF">Serveur MCP</div><div data-type="arch-node" data-id="n2" data-label="Base">Base</div></div></div>`. The bootstrap `<body>` has no `style` attribute. Served = one editor server per test (`serve_deck`), editor page in Chromium 1280 by 900, edit mode on (`open_editor`, `show_slide_2` of `tests/width_support.py`), assertions on the file on disk through `tests/browser_wait.py`.
### SPEC-0020/BT-001: a typing save keeps an author's cursor and outline (reproduction)
- Fails today because: `editor-save.js:67` deletes the two declarations and reserializes the attribute (observed `style="color: rgb(15, 98, 254);"`).
- Given Deck S served, slide 2 shown, edit mode on
- When the person clicks at the end of `Chiffres clés du trimestre`, types `X`, and the autosave writes the file
- Then the file holds `<p data-editable="text" style="cursor:pointer;color:#0F62FE">Hors charte</p>` and `<p data-editable="text" style="outline:1px solid #FF0000;font-weight:600">Mini</p>`, and the string `rgb(` occurs nowhere in slide 2 of the file
### SPEC-0020/BT-010: a width action changes only its text's style
- Given Deck S served, slide 2, edit mode on / When the person drags A's width bar 47 pixels right and lets go / Then A's style in the file is `max-width:650px`, J's is `cursor:pointer;color:#0F62FE` and I's is `outline:1px solid #FF0000;font-weight:600`
### SPEC-0020/BT-011: undo after a structural action restores the exact texts
- Given Deck S served, slide 2, edit mode on / When the person drags A's width bar 47 pixels right, lets go, then clicks `#undo-btn` / Then right after the drag J's live attribute text is `cursor:pointer;color:#0F62FE`; after Undo the file holds A `style="max-width:600px"` and J `style="cursor:pointer;color:#0F62FE"`, and J's live attribute text is `cursor:pointer;color:#0F62FE`
### SPEC-0020/BT-020: the editor's own look is still not saved (non regression)
- Given Deck S served, edit mode on / When the person types `X` in `Chiffres clés du trimestre` and the autosave writes the file / Then the file holds no `contenteditable`, no `_mcp` id, class or attribute (`markers_in`, `tests/width_support.py:306`), and no `outline: 2px dashed`
### SPEC-0020/BT-022: typing focus survives the save (non regression)
- Existing tests: `tests/test_autosave_focus_e2e.py` (all) stay green, unmodified.

## Constraints
- Files not to touch: other editor scripts, existing tests.
- Dependencies not to add: none.
- Scope boundary: comments, the presenting strip, connect mode, drop indicator are the next stories.

## Definition of done
- [ ] RED evidence for BT-001, BT-010 and BT-011 before the fix.
- [ ] Every test above green; `node --check src/mcp_htmleditor/static/*.js` clean; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_editor_artifact_strip.py`, `tests/test_width_*`, `tests/test_undo_redo_e2e.py`, `tests/test_autosave_focus_e2e.py` unchanged and green.
- [ ] One commit `US-0163: a save and an undo snapshot keep every style text`, body with `Summary:`, `Spec: SPEC-0020` and the requirement ids.
