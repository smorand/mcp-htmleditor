# Editor style writes that keep the author's other declarations: Bug Specification

> Generated on: 2026-11-20
> Id: SPEC-0030
> Nature: BUG
> Depth: M
> Depth evidence: 1 module (the editor scripts), 7 requirements, no public contract or data change; two backlog entries of one class
> Status: implemented
> Verdict: no authority
> Defect class: absent
> Severity: Low
> From backlog: BL-0042, BL-0043
> Security: n/a
> CVSS: n/a
> Affected: every release with the Gantt resize, the declarative diagram editing and the presenting scale
> Fixed in: unreleased

BUG / depth M: 1 module (editor scripts), 7 requirements. Security: n/a (checked: no authentication or authorization
bypass, injection, data exposure, traversal or advisory). The class (a lossy write of style text, SPEC-0020) is
swept in SPEC-0020 section 1bis; the occurrences this spec closes are the two entries it deferred.

## 1. Defect

### BUG-001: some editor actions rewrite the author's whole style text to set one declaration

- **Observed behavior:** these actions set one declaration through the element's style object, which makes
  Chromium reserialize the whole `style` attribute (hex colours to `rgb(...)`, spaces, a trailing `;`, comments
  dropped) in the document shown, and the next save writes that form:
  - Gantt task `Agrandir (+20%)` and `Réduire (-20%)` write `width` (`src/mcp_htmleditor/static/editor-menus.js:195`, `:200`);
  - adding an arch node writes `position` on the diagram (`editor-menus.js:282`, legacy diagram menu entry `＋ Ajouter nœud`, line 271);
  - entering edit mode and wiring a node write `position` on the diagram (`editor-drag.js:159`, `:179`);
  - pressing an arch node with the left button writes `position:absolute` on it even when it does not move
    (`editor-drag.js:195`), so an unrelated later save writes the node's reserialized style;
  - moving an arch node writes `position`, `left`, `top` (`editor-drag.js:236-238`).
  The presenting scale has the same effect on `<html>`: every presentation template sets it with
  `root.style.setProperty('--fs-scale', ...)` (24 hits in 13 files under `templates/`, recounted with `rg -c "setProperty\('--fs-scale'" templates`, e.g.
  `templates/bootstrap/slides-empty.html`, function `updateFullscreenScale`); while presenting, `<html>`'s style
  is reserialized by Chromium, and a save made during or after presenting keeps the reserialized text of every
  other declaration (the presenting strip, `stripPresentingState`, `editor-save.js:90-102`, removes `--fs-scale` only).
- **Expected per authority:** none. SPEC-0020/BR-001 (the saved attribute is the text the document shows) and
  SPEC-0015/FR-NEW-012 (a width action keeps the other declarations character for character) cover other paths;
  none states the form of the other declarations for these actions or for the presenting scale.
- **Reproduction (Chromium, 2026-11-20, `tests/width_support.py` D1 deck):** a Gantt task with
  `style="left:0%; width:25%; background:#0F62FE"`, `Agrandir (+20%)`, save: the file holds
  `style="left: 0%; width: 30%; background: rgb(15, 98, 254);"`. A deck with `<html style="color:#161616">`,
  edit mode, present, type, save, leave: the file holds `style="color: rgb(22, 22, 22);"`.
- **Root cause:** each site assigns through `el.style.<prop>` or `style.setProperty` on author content
  (listed above), a write that reserializes the attribute; the scale is written by the deck's own runtime, outside
  the editor, so only the save can restore the text.
- **Contributing factors:** SPEC-0020 fixed the saves, snapshots, width actions, connect mode and drop indicator
  and deferred these as BL-0043 and BL-0042; the scanner of SPEC-0020 (`splitStyleRaw`, `editor-width.js`) makes a
  text level edit possible.
- **Impact:** an author or agent who wrote style text by hand on a Gantt task, a diagram or `<html>` sees it
  rewritten in the file after an unrelated action; `lint` then flags `rgb(...)` colours outside the charter
  palette. Workaround: `restore` of an earlier version.
- **Rollback posture:** a revert restores today's behavior; files written in between stay valid HTML.

## 2. Expected Behavior

Terms: "the attribute text" is the exact character sequence of an element's `style` attribute; declarations are split
by `splitStyleRaw` (SPEC-0020: comments, parentheses and quotes read as such). "Set a declaration" means: replace the
first declaration of that name in place (later ones of the same name are dropped), or append it when absent; every
other declaration keeps its text; only a style that is actually written is rejoined, the separators between the kept
declarations then being `; ` and an empty trailing piece dropped (SPEC-0015/FR-NEW-005); a style left empty is removed.
A style that needs no change is not written at all.

#### BR-001 [EARS-E]: A Gantt task resize sets only its width
> WHEN the person chooses `Agrandir (+20%)` or `Réduire (-20%)` on a Gantt task THE editor SHALL set the task's `width`
> declaration to the new percentage with one decimal and SHALL keep every other declaration of its style as written.
- **Business Rules:** the base is the number of the task's current inline `width` declaration, or 30 when there is none
  or it is not a number; the result is at most 100 for `Agrandir` (x 1.2) and at least 5 for `Réduire` (x 0.8), as today
  (`editor-menus.js:195`, `:200`).
- **Source:** decided here: SPEC-0020 BR-001 restored to these actions, form of the others from SPEC-0015/FR-NEW-005.
- **Outputs:** a task with no `width` grown once gets `width:36.0%` appended; `left:0%; width:25%; background:#0F62FE` grown once gives `left:0%; width:30.0%; background:#0F62FE`;
  shrunk once gives `left:0%; width:20.0%; background:#0F62FE`.
- **Exact names:** menu entries `Agrandir (+20%)`, `Réduire (-20%)`.

#### BR-002 [EARS-E]: A diagram made a positioning context gets one declaration
> WHEN the editor makes an arch diagram whose computed position is `static` a positioning context (edit mode entry,
> wiring a node, adding a node to a legacy diagram with `＋ Ajouter nœud`) THE editor SHALL set only `position:relative`
> in the diagram's style and SHALL keep every other declaration as written, and SHALL write nothing when the diagram
> already is a positioning context (computed position other than `static`).
- **Source:** decided here, same rule as BR-001.
- **Outputs:** `width:100%; height:200px;` gives `width:100%; height:200px; position:relative`.

#### BR-003 [EARS-UB]: Pressing an arch node without moving it writes nothing
> WHEN the person presses an arch node with the left button and releases without moving THE editor SHALL leave the
> node's style attribute text exactly as it was; the position declarations are written at the first movement only.
- **Source:** decided here.

#### BR-004 [EARS-E]: Moving an arch node sets only its position
> WHEN the person moves an arch node THE editor SHALL set the node's `position` (`absolute`), `left` and `top`
> declarations (percent, one decimal) and SHALL keep every other declaration as written, and SHALL keep writing
> `data-x`, `data-y` and `data-layout="manual"` as today.
- **Source:** decided here.
- **Outputs:** `outline:1px dashed #8D8D8D;background:#EDF5FF` moved to 12.3 and 45.6 gives
  `outline:1px dashed #8D8D8D; background:#EDF5FF; position:absolute; left:12.3%; top:45.6%`;
  `position:absolute; left:10%; top:10%; width:20%; height:20%` gives
  `position:absolute; left:12.3%; top:45.6%; width:20%; height:20%`.

#### BR-005 [EARS-E]: The presenting scale does not change `<html>`'s style text
> WHEN the editor saves THE editor SHALL write `<html>`'s `style` attribute with the text it had when the document was
> loaded, never the form the deck's presenting scale left it in, minus a top level `--fs-scale` declaration as
> SPEC-0020/BR-004 says. The loaded text is kept by the editor outside the document, so it survives an Undo or Redo
> (which rewrite the document) and a save made while presenting.
- **Source:** decided here; restores SPEC-0016 R2 and SPEC-0020/BR-004 for the bytes of the other declarations.
- **Business Rules:** a document loaded with no `style` on `<html>` is saved with none. The text is the one of the
  last load of the document (initial load, external write, navigation); an Undo or Redo does not change it.
- **Outputs:** `<html style="color:#161616">`, presented, saved, left: saved as `style="color:#161616"`.

#### BR-006 [EARS-UB]: These writes add no editor mark and no rewrite elsewhere
> The editor SHALL NOT change the attribute text of any element other than the one the action is about, and SHALL NOT
> write the presenting scale into the saved file.
- **Source:** restored from SPEC-0001/FR-005 and SPEC-0020/BR-001.

#### BR-007 [EARS-U]: Undo restores the exact text
> WHEN the person undoes one of these actions THE editor SHALL restore the style text the element had before it,
> character for character, in the document shown and in the file saved after the Undo.
- **Source:** restored from SPEC-0015/FR-NEW-009 (Undo restores the inline style text exactly) and SPEC-0020/BR-002.

## 3. Edge Cases

| Case | Expected behavior | Requirement |
|------|-------------------|-------------|
| task with no `width` declaration | `width:36.0%` (base 30) appended after the others | BR-001 |
| task `width` in `px`, or in a class | the base is 30 when the inline declaration is not a number | BR-001 |
| task style holding a comment with `;` | comment kept inside its declaration | BR-001 |
| diagram already `position:relative` (any case, inline or class) | nothing written | BR-002 |
| diagram `position:absolute` (author's) | not changed (only a static diagram gets `relative`) | BR-002 |
| press and release on a node, then an unrelated save | node attribute text unchanged in the file | BR-003 |
| node dragged twice | `position`, `left`, `top` set each time, others unchanged | BR-004 |
| node style with `left` twice | first replaced, the other dropped | BR-004 |
| `<html>` without `style`, presented | file has no `style` on `<html>` | BR-005 |
| `<html style="--fs-scale:9;color:red">` loaded with it | saved as loaded minus the top level `--fs-scale` (SPEC-0020 BR-004) | BR-005 |
| external write to `<html>`'s style while open, then save | the new text | BR-005 |

## 4. Tests

**Fixture Deck S2:** Deck S of `tests/style_text_support.py` (SPEC-0020) with slide 3's Gantt task `Cadrage` styled
`left:0%; width:25%; background:#0F62FE`, the declarative diagram's node `n2` styled
`position:absolute; left:10%; top:10%; width:20%; height:20%`, `<html>` style `color:#161616`, and on slide 3 a second,
legacy diagram `<div data-type="arch-diagram" style="width:100%; height:200px;">` holding one legacy node (no `arch-row`,
so its menu has the entry `＋ Ajouter nœud`), used by BT-006 and BT-007. The declarative diagram already has
`position:relative`.

### 4.1 End to end reproduction (mandatory)

#### BT-001: Presenting then saving keeps `<html>`'s style text
- **Reproduces:** BUG-001 (presenting scale)
- **Driver:** Playwright Chromium against a real editor server, assertions on the file on disk
- **Fails today because:** the deck's runtime reserializes `<html>`'s style (`color: rgb(22, 22, 22);`) and the save keeps it.
- Given Deck S2 served, edit mode on, `#present-btn` pressed
- When the person types `X` in a text of the presented slide, the autosave writes the file, then leaves the presentation and types `Y`
- Then `<html>`'s style in the file is `color:#161616` after each save and no `--fs-scale` is in the file

#### BT-002: Gantt resize keeps the other declarations
- **Reproduces:** BUG-001 (Gantt)
- **Fails today because:** `editor-menus.js:193` reserializes the task's style.
- Given Deck S2 served, slide 3, edit mode on
- When the person right clicks the task `Cadrage`, chooses `Agrandir (+20%)`, and the autosave writes the file
- Then the task's style in the file is `left:0%; width:30.0%; background:#0F62FE`

### 4.2 New behavior

#### BT-003: Gantt shrink
- **Validates:** BR-001. When the person chooses `Réduire (-20%)` on `Cadrage` Then its style in the file is `left:0%; width:20.0%; background:#0F62FE`.

#### BT-004: Press without moving
- **Validates:** BR-003. Given Deck S2, slide 3 declarative diagram, edit mode on. When the person presses `Base` (`n2`) and releases without moving, then types `X` in the slide title and the autosave writes. Then `n2`'s style in the file is `position:absolute; left:10%; top:10%; width:20%; height:20%` and `n1`'s `outline:1px dashed #8D8D8D;background:#EDF5FF`, and `n2`'s `contenteditable` attribute is back to what it was before the press.

#### BT-005: Node move
- **Validates:** BR-004. When the person drags `Serveur MCP` (`n1`) by 30 pixels and the autosave writes. Then `n1`'s style in the file begins `outline:1px dashed #8D8D8D; background:#EDF5FF; position:absolute; left:` and ends `%` with `left` and `top` once each; and `n2`, dragged likewise, is `position:absolute; left:<x>%; top:<y>%; width:20%; height:20%`.

#### BT-006: Positioning context
- **Validates:** BR-002. Given the legacy diagram of Deck S2 (`style="width:100%; height:200px;"`). When edit mode is entered (wiring makes it a positioning context) and the autosave writes after a typed `X`. Then the diagram's style in the file is `width:100%; height:200px; position:relative`; a diagram already `position:relative; width:100%; height:200px;` is saved byte for byte.

#### BT-007: Adding a node to a static diagram
- **Validates:** BR-002. Given Deck S2 served, slide 3, edit mode OFF (the context menus exist without edit mode, and entering edit mode would already make the diagram relative, BT-006). When the person right clicks the legacy diagram, chooses `＋ Ajouter nœud`, accepts the label prompt and the autosave writes. Then the diagram's style in the file ends with `; position:relative` and its other declarations are as written.

#### BT-008: Undo restores the exact text
- **Validates:** BR-007. When the person resizes `Cadrage` (BT-002) then clicks `#undo-btn`. Then the task's style in the file is `left:0%; width:25%; background:#0F62FE`, and its live attribute text is the same.

### 4.3 Non regression

#### BT-009: No `style` on `<html>`
- **Protects:** BR-005. A deck without `style` on `<html>`, presented and saved, has none in the file.

#### BT-010: The scale still leaves the saved file
- **Protects:** SPEC-0016 R2, SPEC-0020 BT-021. The existing test `tests/test_reference_decks_present_e2e.py::test_save_while_presenting_writes_no_presenting_state` stays green, unmodified.

#### BT-011: The text level rules of SPEC-0020
- **Protects:** SPEC-0020. `tests/test_style_text_*_e2e.py` stay green, unmodified.

### 4.4 Existing tests asserting the current behavior
| Test file | Test name | Action | Reason |
|-----------|-----------|--------|--------|
| `tests/test_undo_redo_e2e.py` | `test_undo_redo_arch_node_reposition` | Kept | asserts live `left`/`top` values, unchanged by the form of the attribute |
| `tests/test_reference_decks_present_e2e.py` | all | Kept | BT-010 |
| `tests/test_style_text_*_e2e.py` | all | Kept | BT-011 |

Out of scope, stated: `editor-format.js:78` writes `fontSize` on the `<font>` element the editor itself creates, and
`editor-menus.js:93`, `:258`, `:278` set `cssText` on elements created on the previous line; neither holds author text.

## 5. Existing Specs Affected
SPEC-0020 (BR-004 stays; this spec adds the unchanged text of the other declarations on `<html>`), SPEC-0015 (the
join `; ` and the empty style rule are reused), SPEC-0016 R2. None is modified.

## 6. Assumptions
- **Assumption:** the declarations are joined with `; ` as for the width actions (SPEC-0015/FR-NEW-005); a set that
  finds nothing to change leaves the text as it was (BR-002, BR-003).
- **Assumption:** the presenting scale is not moved off `<html>` in the templates: the editor restores the text on
  save (BR-005), so decks opened outside the editor are unchanged.
- **Proposed backlog entries (not written):** none.

## 7. Implementability Checklist
Self checked at depth M by a fresh auditor (round below).

Round 1 (fresh auditor): 5 F (BT-007 fixture legacy diagram, Gantt base and clamp, loaded `<html>` text held outside the
document, undo text in the file, join rule), 3 A (hit count 24 in 13 files, line numbers, fixture), all amended. Round 2
(fresh auditor): 2 F (BT-007 isolation: edit mode off; the position write moves to the first movement, BR-003), amended
above; no A.

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | amended in place: 8; proposed: none |
