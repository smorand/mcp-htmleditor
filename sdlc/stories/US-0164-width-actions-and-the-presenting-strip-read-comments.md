# US-0164: width actions and the presenting strip read comments

> Spec: SPEC-0020 (sdlc/specs/SPEC-0020-saved-style-text-kept/)
> Nature: BUG
> Priority: P1
> Depends on: US-0163
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective
A width action and the presenting strip treat CSS comments as comments: a `;`, quote or parenthesis inside a comment never splits or swallows a declaration, and the comment stays with its declaration.

## Requirements covered
- SPEC-0020/BR-003 [EARS-E]: WHEN a width action rebuilds a text's inline style THE editor SHALL treat everything from `/*` to the next `*/` as part of the declaration that holds it, never as a separator, a quote or a parenthesis. A `/*` inside quotes or parentheses does not open a comment; a comment never closed runs to the end of the text; a piece with no `:` outside a comment is not a `max-width` declaration and is kept; a declaration's name is its text before the first `:` outside a comment, comments removed, trimmed, lower case. Join `; `, `max-width:Npx` appended, attribute removed when empty (SPEC-0015).
- SPEC-0020/BR-004 [EARS-E]: WHEN the editor saves THE editor SHALL remove from `<html>`'s style attribute only the declarations named `--fs-scale` at top level, outside comments, parentheses and quotes; the other pieces and separators are kept byte for byte; the name is compared case sensitively; a style left empty or holding only `;` and whitespace is removed. `color:#161616 /* x;--fs-scale:9 */` is saved unchanged, `color:#161616;--fs-scale:1.5` as `color:#161616`.

## Independent Test
`make test ARGS='tests/test_style_text_width_e2e.py tests/test_reference_decks_present_e2e.py'` green, `make check` green.

## Design excerpt
### Decisions
DEC-002 one scanner shared; DEC-003 case sensitive `--fs-scale`.
### Contracts
`src/mcp_htmleditor/static/editor-width.js` (lines 31-82): replace `splitStyleDeclarations` by
`splitStyleRaw(text) -> string[]` (pieces cut at each top level `;` outside comments, parentheses and quotes, untrimmed, empty pieces kept, `pieces.join(';') === text`; scanner states: in quote (backslash escapes honoured), in comment (`/*` outside quotes and parentheses, to the next `*/` or the end), parenthesis depth) and
`splitStyleDeclarations(text) = splitStyleRaw(text).map(trim).filter(non empty)`.
`styleDeclarationName(declaration)`: remove comments (with the same scanner rules: not inside quotes or parentheses), then the text before the first `:`, trimmed, lower case; a piece with no `:` returns `''`-like name never equal to `max-width`. `styleOtherDeclarations`, `styleHasWidth`, `styleWithWidth`, `styleWithoutWidth` keep their contracts (join `'; '`).
`src/mcp_htmleditor/static/editor-save.js` `stripPresentingState` (lines 91-102): replace `style.split(';').filter(...).join(';')` by `splitStyleRaw(style)` filtered on the case sensitive name `--fs-scale` (name computed like `styleDeclarationName` but without lower casing: add a parameter or a sibling `styleDeclarationNameExact`), rejoined with `';'`; empty or `;` only result removes the attribute; unchanged text is not rewritten.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-width.js` | modify |
| `src/mcp_htmleditor/static/editor-save.js` | modify |
| `tests/test_style_text_width_e2e.py` | create |
### Existing patterns
Fixture and helpers of US-0163 (`tests/style_text_support.py`); `tests/test_width_drag_e2e.py` for drags; `tests/test_reference_decks_present_e2e.py::test_save_while_presenting_writes_no_presenting_state`.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc. Deck S as in US-0163 (same fixture module).
### SPEC-0020/BT-012: a width action on a comment holding a semicolon
- Given Deck S, slide 2, edit mode on / When the person drags P's width bar 153 pixels left and lets go / Then P's style in the file is `color:red /* a;b */; font-weight:600; max-width:650px`
### SPEC-0020/BT-013: a quote in a comment does not hide the width
- When the person drags K's width bar 47 pixels right and lets go / Then K's style in the file is `color:red /* it's */; max-width:650px` (one `max-width` only)
### SPEC-0020/BT-014: a width named after a comment is replaced
- When the person drags H's width bar 47 pixels right and lets go / Then H's style in the file is `color:#525252; max-width:650px`
### SPEC-0020/BT-023: a comment opener inside parentheses is not a comment
- Given Deck S with paragraph Q's style replaced by `background:url(a/*b);max-width:600px` / When the person drags Q's width bar 47 pixels right and lets go / Then Q's style in the file is `background:url(a/*b); max-width:650px` (one `max-width` only)
### SPEC-0020/BT-015: reset keeps a comment
- When the person double clicks K's width bar / Then K's style in the file is `color:red /* it's */`
### SPEC-0020/BT-016: the presenting strip keeps a comment that names the scale
- Given Deck S, edit mode on, never presented / When the person types `X` at the end of `Chiffres clés du trimestre` and the autosave writes the file / Then `<html>`'s style in the file is `color:#161616 /* x;--fs-scale:9 */`; and on a copy of Deck S whose `<html>` style is `color:#161616;--FS-SCALE:2` the file holds `style="color:#161616;--FS-SCALE:2"`
### SPEC-0020/BT-021: the scale still leaves a save made while presenting (non regression)
- Existing test `tests/test_reference_decks_present_e2e.py::test_save_while_presenting_writes_no_presenting_state` stays green, unmodified (file's `<html>` holds no `--fs-scale` and no `style=""`, no `data-fs-current`).

## Constraints
- Files not to touch: `editor-menus.js`, `editor-format.js`, `editor-edit.js`, existing tests.
- Dependencies not to add: none.
- Scope boundary: connect mode and drop indicator are later stories.

## Definition of done
- [ ] RED evidence for BT-012, BT-013, BT-014, BT-023, BT-015, BT-016 before the fix.
- [ ] Every test above green; `node --check src/mcp_htmleditor/static/*.js` clean; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_width_drag_e2e.py` (E2E-006, 007, 042), `tests/test_width_keys_undo_e2e.py`, `tests/test_width_failures_e2e.py`, the reference decks presenting test, unchanged and green.
- [ ] One commit `US-0164: width actions and the presenting strip read comments`, body with `Summary:`, `Spec: SPEC-0020` and the requirement ids.
