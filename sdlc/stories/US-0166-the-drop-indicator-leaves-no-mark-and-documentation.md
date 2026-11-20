# US-0166: the drop indicator leaves no mark, documentation

> Spec: SPEC-0020 (sdlc/specs/SPEC-0020-saved-style-text-kept/)
> Nature: BUG
> Priority: P1
> Depends on: US-0164, US-0165
> min_tier: 2
> Files touched: 5
> Closes spec: yes

## Objective
The blue line shown on an editable zone while an image file is dragged over it no longer writes `box-shadow` into the author's style, the file or a snapshot. Closes SPEC-0020: its full acceptance set must be green, and the docs state the rule.

## Requirements covered
- SPEC-0020/BR-006 [EARS-UB]: The editor SHALL NOT write the drop indicator of a dragged image file into the saved file, into an undo snapshot, or into the attribute text of the editable zone it is shown on. While a file is dragged over an editable zone the zone shows an inset 3 pixel `#0f62fe` line (computed `box-shadow` `rgb(15, 98, 254) 0px 0px 0px 3px inset`); on leave or drop the line goes and the attribute text is exactly as before the drag entered; the author's own `box-shadow` is shown again.

## Independent Test
`make test ARGS='tests/test_style_text_marks_e2e.py'` green, then `make check` green and every SPEC-0020 test (BT-001, BT-010 to BT-023) green.

## Design excerpt
### Decisions
DEC-004, DEC-005: the mark is `data-mcp-mark="drop"`, removed by the strip (US-0165).
### Contracts
`src/mcp_htmleditor/static/editor-format.js` `enableImageDrop` (lines 265-277): replace `el.style.boxShadow = 'inset 0 0 0 3px #0f62fe'` by `el.setAttribute('data-mcp-mark', 'drop')` and both `el.style.boxShadow = ''` (dragleave, drop) by `el.removeAttribute('data-mcp-mark')`.
`src/mcp_htmleditor/static/editor-edit.js` `injectEditorStyles`: add `[data-mcp-mark="drop"] { box-shadow: inset 0 0 0 3px #0f62fe !important; }`.
Docs: `.agent_docs/html-conventions.md` (a short section: the editor never writes the style object of author content; its transient marks are the attribute `data-mcp-mark` removed by `stripEditorArtifacts`; style text edits use `splitStyleRaw`), `.agent_docs/testing.md` (file map row for the three `test_style_text_*_e2e.py` files and `style_text_support.py`). Keep every `.agent_docs/*.md` within 220 lines (`tests/test_agent_docs_size.py`).
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-format.js` | modify |
| `src/mcp_htmleditor/static/editor-edit.js` | modify |
| `tests/test_style_text_marks_e2e.py` | modify (add BT-019) |
| `.agent_docs/html-conventions.md` | modify |
| `.agent_docs/testing.md` | modify |

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc. Deck S as in US-0163.
### SPEC-0020/BT-019: drop indicator during a save, then leave
- Given Deck S served, slide 2, edit mode on, the person types `X` at the end of `Chiffres clés du trimestre`
- When within 800 ms a `dragover` carrying a `DataTransfer` with one `File` of type `image/png` is dispatched on J (the zone's drop listener), the autosave writes the file while no `dragleave` has come, then a `dragleave` is dispatched on J
- Then while over J its computed `box-shadow` is `rgb(15, 98, 254) 0px 0px 0px 3px inset`; the file holds J as `style="cursor:pointer;color:#0F62FE"` and no `data-mcp-mark`; after leave J's computed `box-shadow` is `none` and its live attribute text is `cursor:pointer;color:#0F62FE`
(Also assert the author's own `box-shadow` case: J with `style="box-shadow:0 0 4px #FF0000"` shows its own shadow again after the drag.)

## Constraints
- Files not to touch: `editor-width.js`, `editor-menus.js`, existing tests.
- Dependencies not to add: none.

## Definition of done
- [ ] RED evidence for BT-019 before the fix.
- [ ] Every test above green; `node --check src/mcp_htmleditor/static/*.js` clean; `make check` green on the work branch after this commit.
- [ ] Spec converge: every test of SPEC-0020 green (BT-001, BT-010 to BT-023), every requirement BR-001 to BR-006 cited by a story with status done or landed.
- [ ] Docs updated: `.agent_docs/html-conventions.md`, `.agent_docs/testing.md`.
- [ ] One commit `US-0166: the drop indicator leaves no mark, documentation`, body with `Summary:`, `Spec: SPEC-0020` and the requirement ids.
