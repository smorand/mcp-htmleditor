# Saved style text kept as written: Bug Specification

> Generated on: 2026-11-09
> Id: SPEC-0020
> Nature: BUG
> Depth: M
> Depth evidence: one module (the editor scripts, `src/mcp_htmleditor/static/`), 6 requirements, no public contract or data model change; several observable behaviors defective (save, undo snapshot, width action, presenting strip, connect mode, image drop), which rules out S
> Status: specified
> Verdict: authority exists
> Defect class: n/a (code violates a clear authority)
> Severity: Medium
> From backlog: BL-0034
> Security: n/a
> CVSS: n/a
> Affected: every release since the save clone strip (`git log -S"el.style.outline = ''"`: 8dea74e, b4cc332), up to e6d3a92
> Fixed in: unreleased

BUG / depth M: 1 module (static editor scripts), 6 requirements, no public contract touched, six code paths.

Security: n/a. Checked unconditionally: no authentication or authorization bypass, no injection, no exposure
of data or credentials, no deserialization or traversal, no advisory. The class sweep of section 1bis is run
because the same lossy write repeats, not because the entry is a vulnerability.

## 1. Defect

### BUG-001: An unrelated save rewrites or drops the author's inline style

- **Observed behavior:** before every save the editor takes the editor's look off a clone of the document by
  writing `el.style.outline = ''; el.style.cursor = ''` on every `[contenteditable]` element
  (`src/mcp_htmleditor/static/editor-save.js:65-68`, called from `editor-save.js:26-27`). The editor never
  writes an inline `outline` or `cursor` on those elements: its look is the class `_mcp_editable`
  (`editor-edit.js:44-45`) styled by an injected sheet (`editor-edit.js:86-87`). Writing through the style
  object deletes the author's own `cursor` or `outline` declaration and makes Chromium reserialize the whole
  attribute (hex colours to `rgb(...)`, spaces, a trailing `;`, comments dropped). The undo snapshot runs the
  same function on the live document and puts the values back through the style object
  (`editor-undo.js:27-34`, `editor-save.js:76-79`), so the live attribute is reserialized too and the next save
  writes it.
- **Expected per authority:** SPEC-0001/FR-005 (`sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:107`): "WHEN the
  browser saves THE system SHALL remove editor ids and classes, editable markers, drag handles, browser
  extension attributes and duplicated slide selector options before writing." An author's `cursor` or
  `outline` is none of these. SPEC-0015/FR-NEW-010 (`sdlc/specs/SPEC-0015-text-max-width-handle/spec.md:299-301`):
  "After any width action the only difference in the file is the text's style as stated in FR-NEW-005 or
  FR-NEW-007", and SPEC-0015/FR-NEW-012 (`spec.md:315`): "The editor SHALL NOT change, through a width action,
  [...] the written form of any other declaration of the text's style. [...] a colour written as `#0F62FE`
  stays `#0F62FE`."
- **Reproduction (run in Chromium on 2026-11-09, Playwright, the D1 deck of `tests/width_support.py:113`
  with paragraph J set to `style="cursor:pointer;color:#0F62FE"` and paragraph I to
  `style="color:red /* a;b */;outline:1px solid #FF0000"`):** edit mode on slide 2, type `X` at the end of
  `Chiffres clés du trimestre`, wait for the autosave. Expected: J saved as `style="cursor:pointer;color:#0F62FE"`.
  Actual: `<p data-editable="text" style="color: rgb(15, 98, 254);">Hors charte</p>` and
  `<p data-editable="text" style="color: red;">Mini</p>`. A width drag on paragraph A then saves the same two
  rewritten attributes.
- **Root cause:** `src/mcp_htmleditor/static/editor-save.js:67` assigns `''` to `style.outline` and
  `style.cursor` of every editable element, a write through the style object that removes the author's
  declaration and reserializes the attribute whenever it holds `outline` or `cursor`;
  `editor-save.js:78` writes them back the same way on the live document after an undo snapshot. Clearing a
  property that is absent leaves the text untouched (measured in SPEC-0015 design DEC-003,
  `sdlc/specs/SPEC-0015-text-max-width-handle/design.md:304-310`), which is why the defect needs one of the
  two properties in the attribute.
- **Contributing factors:** SPEC-0019/DR-003 (`sdlc/specs/SPEC-0019-code-and-test-debts/design.md:93`)
  wrote the two assignments into the shared strip's contract; SPEC-0015 DEC-003 measured only the absent case;
  no test fixture holds `cursor` or `outline` on an editable element (`rg -n "cursor|outline" tests/width_support.py`
  returns nothing).
- **Impact:** every author or agent who writes `cursor` or `outline` inline on an editable text. Each
  unrelated save (typing, blur, width, structural action, undo) deletes the declaration and rewrites the rest;
  `lint` then flags `rgb(...)` colours outside the charter palette. Workaround: none in the editor; `restore`
  of an earlier version brings the text back until the next save.
- **Rollback posture:** a revert of the fix restores today's behavior; files written in between stay valid
  HTML that every earlier version reads.

### Further occurrences of the same defect (section 1bis)

The same lossy write of style text is made by four more paths, all in the editor scripts; they are part of
BUG-001's class and are fixed by this specification:

1. The width action's splitter does not know CSS comments (`editor-width.js:34-58`): a `;` inside `/* */` splits
   a declaration and the rejoin with `; ` (`editor-width.js:79-81`) changes the comment's bytes; a `'` or `(`
   inside a comment opens a quote or a group that swallows the following declarations, so an existing
   `max-width` after it is not found and a second one is appended.
2. The presenting strip cuts `<html>`'s style on every `;` (`editor-save.js:95`), comments and parentheses
   included: `color:#161616 /* x;--fs-scale:9 */` is saved as `color:#161616 /* x`, an unclosed comment. It
   runs on every save (`editor-save.js:28`), presenting or not.
3. Connect mode of a declarative diagram writes the editor's marks through the style object on the author's
   elements: `outline` on the source node and `cursor:crosshair` on `<body>` (`editor-menus.js:122-123`),
   cleared the same way (`editor-menus.js:142-143`). A save or an undo snapshot taken in between writes the
   marks into the file: `finishArchConnect` takes the snapshot before cancelling the mode
   (`editor-menus.js:157`, `:165`). Clearing deletes an author's own `outline`/`cursor` and reserializes both
   attributes.
4. The image drop indicator writes `box-shadow` through the style object on the editable zone under a dragged
   file (`editor-format.js:270`) and clears it the same way (`editor-format.js:273`, `:275`): same three
   effects (mark saved if a save runs during the drag, author's `box-shadow` deleted, attribute reserialized).

## 1bis. Class Sweep

**Class:** inline style text written by a person or an agent reaches a style object write or a separator
split that does not preserve its text (a lossy CSS parse or reserialization). No CWE: not a security class.

**Searches run (repository root, 2026-11-09):**

- `rg -n "\.style\.[a-zA-Z]+\s*=[^=]|style\.(setProperty|removeProperty)|style\.cssText" src/mcp_htmleditor/static/*.js`:
  property writes through the style object.
- `rg -n "getAttribute\('style'\)|setAttribute\('style'|split\(';'\)|split\(\";\"\)" src/mcp_htmleditor/static/*.js`:
  style text read and split by hand.
- `rg -n "style\[" src/mcp_htmleditor/static/*.js`: bracket writes (no hit).
- `rg -n "setProperty\('--fs-scale'|removeProperty\('--fs-scale'" templates`: the deck runtime of the
  templates (33 hits in 11 files), outside the editor scripts.
- Not searched: `src/mcp_htmleditor/export/*` and the Python strippers (they read the saved text and never
  write it back to a document through a CSS parser: `http_server.py:795` serializes attributes as parsed).

| Occurrence | Verdict | Disposition |
|---|---|---|
| `editor-save.js:63`, `:67`, `:78` (save clone and undo snapshot) | defective: author's `cursor`/`outline` deleted, attribute reserialized | BR-001, BR-002 |
| `editor-save.js:93-97` (presenting strip) | defective on a top level `;` inside a comment, parentheses or quotes | BR-004 |
| `editor-width.js:34-64` (width splitter, name) | defective on comments | BR-003 |
| `editor-width.js:271`, `:370` (drag preview `setProperty`) | safe: taken out around every serialization by `withWidthPreviewSuspended` (`editor-save.js:26`, `editor-undo.js:31`) and the saved text rebuilt from the attribute read at the press (`editor-width.js:255`, `:283`) | n/a |
| `editor-width.js:234`, `:353`, `:314`, `:322` | safe: text level read and `setAttribute` | n/a |
| `editor-menus.js:122-123`, `:142-143` (connect mode) | defective: marks reach file and snapshot; author text rewritten | BR-005 |
| `editor-format.js:270`, `:273`, `:275` (drop indicator) | defective: same | BR-006 |
| `editor-save.js:71-72`, `:80` (format and insert bars) | safe: editor owned elements removed by id by the server (`http_server.py:52-56`) | n/a |
| `editor-format.js:78` (font size) | safe: the element is the `<font size="7">` the editor created at `editor-format.js:74-77` by `execCommand('fontSize')`, no author text | n/a |
| `editor-menus.js:93`, `:256`, `:276-277` (`cssText` of a new node or task) | safe: element created on the line before, no author text | n/a |
| `editor-menus.js:314`, `:327`; `editor-format.js:113-224`; `editor.js`, `editor-slides.js`, `editor-blocks.js`, `editor-undo.js:156-157`, `editor-requests.js:90`, `editor-width.js:122-124` | safe: elements of the editor page, never in the framed document | n/a |
| `editor-menus.js:193`, `:198` (task resize), `:280` (diagram `position`), `editor-drag.js:159`, `:179`, `:195`, `:236-238` (node drag, and `position` on a press without move) | same lossy write, but the editor writes the person's own change; no authority defines the other declarations' form for these actions | BL-0043 |
| `templates/**` deck runtime `setProperty('--fs-scale')` (33 hits, 11 files) | same lossy write on `<html>`'s style while presenting, deck code outside the editor | BL-0042 |

## 2. Expected Behavior

Terms: "the attribute text" is the exact character sequence of an element's `style` attribute. "Exactly" means
character for character, or absent when the attribute was absent. Declarations are split per the rule of
SPEC-0015/FR-NEW-005, extended by BR-003.

#### BR-001 [EARS-E]: A save keeps every author style as written
> WHEN the editor saves THE editor SHALL write the `style` attribute of every element of the document with
> the attribute text it has in the document shown, and SHALL NOT remove an `outline` or `cursor` declaration
> written by the author or an agent.

- **Source:** restored from SPEC-0001/FR-005 (only the editor's own artifacts are removed) and SPEC-0015/FR-NEW-010,
  FR-NEW-012.
- **Inputs:** any save: typing autosave (800 ms), blur, structural action (600 ms), width action, undo, redo,
  `Keep mine`.
- **Outputs:** `style="cursor:pointer;color:#0F62FE"` is saved as `style="cursor:pointer;color:#0F62FE"`.
- **Business Rules:** the editor's own look on editable zones, the format and insert bars, the drag handles and
  the presenting state are still removed (SPEC-0001/FR-005, SPEC-0016 R2, SPEC-0017 DEC-014). The server
  side cleaning is unchanged.
- **Exact names:** attribute `style`; declarations `cursor`, `outline`.

#### BR-002 [EARS-UB]: An undo snapshot changes no style text
> The editor SHALL NOT change the attribute text of any element of the live document when it records an undo
> or redo snapshot, and the snapshot SHALL hold every attribute text as it is in the live document.

- **Source:** restored from SPEC-0015/FR-NEW-009 ("Undo restores the inline style text exactly as it was
  before the change") and SPEC-0001/FR-005.
- **Business Rules:** an Undo or Redo then writes, through BR-001, the texts held by the snapshot.

#### BR-003 [EARS-E]: A width action reads comments as comments
> WHEN a width action rebuilds a text's inline style THE editor SHALL treat everything from `/*` to the next
> `*/` as part of the declaration that holds it, never as a separator, a quote or a parenthesis.

- **Source:** restored from SPEC-0015/FR-NEW-005 and FR-NEW-012 (other declarations kept "character for
  character"); the comment rule is decided here, as an edge case SPEC-0015 did not cover.
- **Business Rules:** a `/*` inside quotes or inside parentheses does not open a comment (those keep the rules
  of FR-NEW-005); inside a comment, quotes, parentheses and `;` are plain text. A comment never closed runs to
  the end of the text. A piece with no `:` outside a comment (a lone `/* c */`) is not a `max-width`
  declaration and is kept unchanged. A comment is kept, character for
  character, inside the declaration that holds it, and that declaration is kept or dropped whole. A
  declaration's name is its text before the first `:` outside a comment, comments removed, trimmed, lower case:
  `/* note */ max-width:600px` is a `max-width` declaration and is dropped with its comment. Every other rule of
  FR-NEW-005 and FR-NEW-007 is unchanged (join `; `, `max-width:Npx` appended, attribute removed when empty).
- **Outputs:** `color:red /* a;b */;font-weight:600` at 650 gives `color:red /* a;b */; font-weight:600; max-width:650px`;
  `color:red /* it's */;max-width:600px` at 650 gives `color:red /* it's */; max-width:650px`;
  `/* note */ max-width:600px;color:#525252` at 650 gives `color:#525252; max-width:650px`;
  `background:url(a/*b);max-width:600px` at 650 gives `background:url(a/*b); max-width:650px`.

#### BR-004 [EARS-E]: The presenting strip removes only the scale declaration
> WHEN the editor saves THE editor SHALL remove from `<html>`'s style attribute only the declarations named
> `--fs-scale` that stand at top level, outside any comment, parentheses or quotes.

- **Source:** restored from SPEC-0001/FR-005 (only artifacts are removed) and the presenting strip's contract
  (`editor-save.js:85-88`: "every other declaration keeps its bytes"); the comment case is decided here.
- **Business Rules:** the text is cut at each top level `;` (BR-003's rule for comments, SPEC-0015/FR-NEW-005's
  for parentheses and quotes); a piece whose name (BR-003) is `--fs-scale` is dropped with the `;` before it,
  or after it when it is first; the other pieces and separators are kept byte for byte. Here the name is
  compared case sensitively (CSS custom property names are): only `--fs-scale` is removed, `--FS-SCALE` and
  `--fs-scale-x` are kept; lower casing applies to BR-003 only. A style left empty or
  holding only `;` and whitespace is removed. For a text without comment, parenthesis or quote, the result is
  today's (`editor-save.js:95-97`).
- **Outputs:** `color:#161616 /* x;--fs-scale:9 */` is saved unchanged;
  `color:#161616;--fs-scale:1.5` is saved as `color:#161616`.

#### BR-005 [EARS-UB]: Connect mode leaves no mark and no rewrite
> The editor SHALL NOT write the connect mode marks of a declarative diagram into the saved file, into an undo
> snapshot, or into the attribute text of the source node and of `<body>`.

- **Source:** restored from SPEC-0001/FR-005 (editor artifacts never saved) and BR-001.
- **Business Rules:** while connect mode is active the source node still shows a 3 pixel `#0f62fe` outline and
  the pointer over the document is a crosshair (unchanged look, `editor-menus.js:122-123`). When the mode ends
  by Escape or by a click on the source, the two attribute texts are exactly as before the mode started. When
  it ends by an edge created, `<body>`'s attribute text is exactly as before the mode, and the source node's
  `style` holds the author's declarations as before the mode, with no declaration of the editor's mark, plus
  only the declarations the diagram layout run then writes (`position`, `left`, `top`, `width`, `height`,
  `arch_layout.py:444-447`, outside this specification). A save or an undo snapshot during the mode writes the
  two attribute texts as before the mode started.
- **Exact names:** menu entry `➜ Créer une arête depuis ce nœud`; key `Escape`.

#### BR-006 [EARS-UB]: The image drop indicator leaves no mark and no rewrite
> The editor SHALL NOT write the drop indicator of a dragged image file into the saved file, into an undo
> snapshot, or into the attribute text of the editable zone it is shown on.

- **Source:** restored from SPEC-0001/FR-005 and BR-001.
- **Business Rules:** while a file is dragged over an editable zone, the zone shows an inset 3 pixel `#0f62fe`
  line (computed `box-shadow` `rgb(15, 98, 254) 0px 0px 0px 3px inset`); on leave or drop the line goes and the
  attribute text is exactly as before the drag entered. The author's own `box-shadow` is shown again after the
  drag.

## 3. Edge Cases

| Case | Expected behavior | Requirement |
|------|-------------------|-------------|
| `style` absent on an editable | stays absent after every save and snapshot | BR-001, BR-002 |
| `style=""` (empty) on an editable | saved as `style=""` | BR-001 |
| author `outline` on a declarative node, then connect mode | `outline` text back exactly after the mode; never the editor's | BR-005 |
| connect mode ended by an edge created | source keeps the author's declarations, no mark, plus the layout's position declarations | BR-005 |
| `/*` inside `url(...)` or quotes | not a comment | BR-003 |
| author `box-shadow` on an editable, file dragged over | drag shows the indicator; after leave the author's text and look are back | BR-006 |
| comment never closed `color:red /* x` in a width action | kept in its declaration, `max-width` appended after `; ` | BR-003 |
| `;` inside `url(...)` or quotes | unchanged rule of SPEC-0015 (E2E-042) | BR-003, BR-004 |
| `<html>` style without `--fs-scale` | saved byte for byte | BR-004 |
| `<html>` style `color:#161616;--FS-SCALE:2` | saved byte for byte (case sensitive name) | BR-004 |
| save during a width drag holding a `cursor` declaration | writes the attribute as before the drag, `cursor` kept | BR-001 |

## 4. Tests

**Fixture Deck S:** the D1 deck of `tests/width_support.py:113` (Carbon bootstrap, slide 2 paragraphs A to Q)
with these replacements on slide 2: J `style="cursor:pointer;color:#0F62FE"` (`Hors charte`), I
`style="outline:1px solid #FF0000;font-weight:600"` (`Mini`), P `style="color:red /* a;b */;font-weight:600"`
(`Agent`), K `style="color:red /* it's */;max-width:600px"` (`Large`), H
`style="/* note */ max-width:600px;color:#525252"` (`Objectifs`); `<html ... style="color:#161616 /* x;--fs-scale:9 */">`;
slide 3's diagram replaced by a declarative one: `<div data-type="arch-diagram" style="position:relative; width:100%; height:200px;"><div data-type="arch-row">`
holding `<div data-type="arch-node" data-id="n1" data-label="Serveur MCP" style="outline:1px dashed #8D8D8D;background:#EDF5FF">Serveur MCP</div>`
and `<div data-type="arch-node" data-id="n2" data-label="Base">Base</div>`, `</div></div>`. "Served" means one
editor server per test (`serve_deck`), the editor page in Chromium at 1280 by 900, edit mode on. The
bootstrap's `<body>` carries no `style` attribute (`templates/bootstrap/slides-empty.html:262`).

**Drag distances:** A, H and K start at `max-width:600px`; 47 pixels right gives `650 px` as SPEC-0015 E2E-001
(`tests/test_width_drag_e2e.py:55-67`). P, like B, has no `max-width` and fills the 800 pixel container
(`tests/width_support.py:84-87`); 153 pixels left gives `650 px` as paragraph B in SPEC-0015 E2E-006 (`tests/test_width_drag_e2e.py:127`).

**Cost:** the tests of this spec share one Chromium page per module (as `width_page`, `tests/width_support.py:161`),
wait only through `tests/browser_wait.py`, and add at most 8 s together to `make check`.

### 4.1 End to end reproduction (mandatory)

#### BT-001: A typing save keeps an author's cursor and outline
- **Reproduces:** BUG-001
- **Driver:** Playwright Chromium against a real editor server, assertions on the file on disk
- **Fails today because:** `editor-save.js:67` deletes the two declarations and reserializes the attribute
  (observed: `style="color: rgb(15, 98, 254);"`).
- Given Deck S served, slide 2 shown, edit mode on
- When the person clicks at the end of `Chiffres clés du trimestre`, types `X`, and the autosave writes the file
- Then the file holds `<p data-editable="text" style="cursor:pointer;color:#0F62FE">Hors charte</p>` and
  `<p data-editable="text" style="outline:1px solid #FF0000;font-weight:600">Mini</p>`, and the string `rgb(`
  occurs nowhere in slide 2 of the file

### 4.2 New behavior

#### BT-010: A width action changes only its text's style
- **Validates:** BR-001, SPEC-0015/FR-NEW-010
- Given Deck S served, slide 2, edit mode on
- When the person drags A's width bar 47 pixels right and lets go
- Then A's style in the file is `max-width:650px`, J's is `cursor:pointer;color:#0F62FE` and I's is
  `outline:1px solid #FF0000;font-weight:600`

#### BT-011: Undo after a structural action restores the exact texts
- **Validates:** BR-002
- Given Deck S served, slide 2, edit mode on
- When the person drags A's width bar 47 pixels right, lets go, then clicks the Undo button `#undo-btn`
  (shown in edit mode, SPEC-0002/FR-012, and enabled once a step is recorded)
- Then right after the drag J's live attribute text is `cursor:pointer;color:#0F62FE`; after Undo the file
  holds A `style="max-width:600px"` and J `style="cursor:pointer;color:#0F62FE"`, and J's live attribute
  text is `cursor:pointer;color:#0F62FE`

#### BT-012: Width action on a comment holding a semicolon
- **Validates:** BR-003
- Given Deck S served, slide 2, edit mode on
- When the person drags P's width bar 153 pixels left and lets go
- Then P's style in the file is `color:red /* a;b */; font-weight:600; max-width:650px`

#### BT-013: A quote in a comment does not hide the width
- **Validates:** BR-003
- Given Deck S served, slide 2, edit mode on
- When the person drags K's width bar 47 pixels right and lets go
- Then K's style in the file is `color:red /* it's */; max-width:650px` (one `max-width` only)

#### BT-014: A width named after a comment is replaced
- **Validates:** BR-003
- Given Deck S served, slide 2, edit mode on
- When the person drags H's width bar 47 pixels right and lets go
- Then H's style in the file is `color:#525252; max-width:650px`

#### BT-023: A comment opener inside parentheses is not a comment
- **Validates:** BR-003
- Given Deck S served, slide 2, edit mode on, paragraph Q's style replaced in the fixture by
  `background:url(a/*b);max-width:600px`
- When the person drags Q's width bar 47 pixels right and lets go
- Then Q's style in the file is `background:url(a/*b); max-width:650px` (one `max-width` only)

#### BT-015: Reset keeps a comment
- **Validates:** BR-003 (with SPEC-0015/FR-NEW-007)
- Given Deck S served, slide 2, edit mode on
- When the person double clicks K's width bar
- Then K's style in the file is `color:red /* it's */`

#### BT-016: The presenting strip keeps a comment that names the scale
- **Validates:** BR-004
- Given Deck S served, edit mode on, never presented
- When the person types `X` at the end of `Chiffres clés du trimestre` and the autosave writes the file
- Then `<html>`'s style in the file is `color:#161616 /* x;--fs-scale:9 */`
- And, the same test run again on a copy of Deck S whose `<html>` style is `color:#161616;--FS-SCALE:2`, the
  file holds `style="color:#161616;--FS-SCALE:2"`

#### BT-017: Connect mode: save during the mode, then Escape
- **Validates:** BR-005
- Given Deck S served, slide 3, edit mode on
- When the person right clicks `Serveur MCP`, chooses `➜ Créer une arête depuis ce nœud`, clicks at the end of
  the slide title `Objets` (not a node, the mode stays active), types `X`, the autosave writes the file, then
  the person presses Escape
- Then during the mode `Serveur MCP` shows a computed outline `rgb(15, 98, 254) solid 3px`; the file holds
  `n1` with `style="outline:1px dashed #8D8D8D;background:#EDF5FF"`, a `<body>` with no `style` attribute, and
  `ObjetsX`; after Escape `n1`'s live attribute text is `outline:1px dashed #8D8D8D;background:#EDF5FF` and
  `<body>` has no `style` attribute

#### BT-018: Connect mode: the undo snapshot holds no mark
- **Validates:** BR-005, BR-002
- Given Deck S served, slide 3, edit mode on
- When the person right clicks `Serveur MCP`, chooses `➜ Créer une arête depuis ce nœud`, clicks `Base`,
  accepts the label prompt empty, waits for the save, then clicks `#undo-btn` and waits for the save
- Then (the layout run after the edge may add position declarations to `n1`'s style, `arch_layout.py:444`;
  only the outline is asserted) the file holds no `arch-edge` element, `n1`'s style holds `outline:1px dashed #8D8D8D` and no other
  `outline`, the file holds no `crosshair`, and `<body>` has no `style` attribute

#### BT-019: Drop indicator during a save, then leave
- **Validates:** BR-006
- Given Deck S served, slide 2, edit mode on, the person types `X` at the end of `Chiffres clés du trimestre`
- When within 800 ms a `dragover` carrying a `DataTransfer` with one `File` of type `image/png` is dispatched
  on J (the zone's drop listener, `editor-format.js:267-271`), the autosave writes the file while no
  `dragleave` has come, then a `dragleave` is dispatched on J
- Then while over J its computed `box-shadow` is `rgb(15, 98, 254) 0px 0px 0px 3px inset`; the file holds J
  as `style="cursor:pointer;color:#0F62FE"`; after leave J's computed `box-shadow` is `none` and its live
  attribute text is `cursor:pointer;color:#0F62FE`

### 4.3 Non regression

#### BT-020: The editor's own look is still not saved
- **Protects:** SPEC-0001/FR-005, SPEC-0015 NFR-003
- Given Deck S served, edit mode on
- When the person types `X` in `Chiffres clés du trimestre` and the autosave writes the file
- Then the file holds no `contenteditable`, no `_mcp` id, class or attribute (`markers_in`,
  `tests/width_support.py:306`), and no `outline: 2px dashed`

#### BT-021: The scale still leaves a save made while presenting
- **Protects:** SPEC-0016 R2, BR-004
- Given each reference deck of `tests/test_reference_decks_present_e2e.py::test_save_while_presenting_writes_no_presenting_state`
  served, presented with `#present-btn`
- When a save runs while presenting
- Then the file's `<html>` holds no `--fs-scale` and no `style=""`, and no element holds `data-fs-current`
  (the kept test's assertions)

#### BT-022: Typing focus survives the save
- **Protects:** SPEC-0004 (the live document is never stripped by the save)
- Given a served document, edit mode on (the fixtures of `tests/test_autosave_focus_e2e.py`)
- When the person types in a text and the autosave runs
- Then the focus, the caret offset and the selection stay in the text (the kept tests' assertions, all green)

### 4.4 Existing tests asserting the current behavior

| Test file | Test name | Action | Reason |
|-----------|-----------|--------|--------|
| `tests/test_editor_artifact_strip.py` | `test_artifact_strip_is_defined_once_in_editor_save`, `test_artifact_strip_is_used_by_snapshot_and_save`, `test_artifact_strip_contenteditable_removals` | Kept | structure of SPEC-0019 DR-003 (one strip, two callers); none asserts the two assignments |
| `tests/test_width_drag_e2e.py` | `test_width_drag_other_declarations_verbatim` (E2E-006, 007, 042) | Kept | fixture D1 holds no comment, `cursor` or `outline` |
| `tests/test_width_keys_undo_e2e.py`, `tests/test_width_failures_e2e.py` | all | Kept | same fixture |
| `tests/test_reference_decks_present_e2e.py` | `test_save_while_presenting_writes_no_presenting_state` | Kept | BT-021 |
| `tests/test_pointer_served_e2e.py` | `test_pointer_served_edit_mode_and_save_keep_no_pointer` | Kept | pointer layer strip untouched |
| `tests/test_autosave_focus_e2e.py` | all | Kept | BT-022 |
| `tests/test_undo_redo_e2e.py` | all | Kept | snapshots of decks without `cursor`/`outline` |
| `tests/test_http_helpers.py` | `test_strip_*` (7) | Kept | server cleaning unchanged |

No existing test drives connect mode (`editor-menus.js:119-145`) or the image drop indicator
(`editor-format.js:265-277`): `rg -n "Créer une arête|startArchConnect|dragover|crosshair" tests` finds nothing
in a test of the editor. BT-017, BT-018 and BT-019 are the first.

## 5. Existing Specs Affected

- SPEC-0019/DR-003 (`design.md:93`) states the shared strip "set[s] `style.outline` and `style.cursor` to
  `''`". This specification requires that no author `outline` or `cursor` be removed (BR-001) and that the
  live text not change (BR-002). SPEC-0019 is not modified.
- SPEC-0015 design DEC-003 (`design.md:307-309`) states the clone's clearing "leaves the text untouched": true
  only when neither property is present. SPEC-0015/FR-NEW-005 gains the comment rule of BR-003.

## 6. Assumptions

- **Assumption:** a comment is part of the declaration that holds it and goes with it (BR-003, BR-004); the
  alternative (keep a comment when its declaration is dropped) is not taken: nothing in the repository writes
  comments inside a `max-width` declaration (`rg -n "/\*" templates/bootstrap/*.html` hits only `<style>` and
  `<script>` blocks, ASSUMED for the reference decks, which this spec does not rely on).
- **Assumption:** the visual marks of connect mode and of the drop indicator keep their look (BR-005, BR-006).
- **Assumption:** the test plan is approved (instruction of 2026-11-09: take the recommended defaults, ask no
  question).
- **Backlog entries created by this run:** BL-0042 (deck runtime rewrites `<html>`'s style while presenting),
  BL-0043 (editor actions that write one declaration rewrite the others).

## 7. Implementability Checklist

Round 1 by a fresh `pi -p` auditor (path and Phase E checklist only): 3 F (BR-004 name case, missing 4.4
statement for connect mode and drop indicator, this section without per item results), 3 A (BT-018 layout,
drag distances, citations). All amended in place above.
Round 2 by a new fresh auditor: 2 F newly found (BR-005 against BT-018 when an edge is created; `/*` inside
quotes or parentheses), 4 A (a design sentence in section 5, `#undo-btn` named, the drop events named, the
fixture's `<body>`). All amended in place: BR-005 and BR-003 business rules, BT-023, section 3 rows.
Round 3 by a new fresh auditor: 0 F, 3 A (BT-021 and BT-022 data, a piece without `:`, P's width source), all
amended in place. Verdict IMPLEMENTABLE.

| # | Item | Result |
|---|---|---|
| 1 | No technical decision | PASS (root cause lines are facts; no fix design) |
| 2 | No buried requirement | PASS |
| 3 | Every observable name spelled | PASS (attribute texts, menu entry, key, computed values) |
| 4 | No forced choice | PASS after round 1 (BR-004 case rule) |
| 5 | Every test specified, blast radius verdicts | PASS after round 1 (4.4 note) |
| 6 | End to end reproduction | PASS (BT-001, Chromium, file on disk, red on `editor-save.js:67`) |
| 7ante | Security misclassification | PASS (no vulnerability described) |
| 7bis | Class sweep and exploit tests | n/a (not a security entry; the sweep of 1bis is kept) |
| 8 | No hidden prerequisite | PASS (Given states the served deck and edit mode) |
| 9 | EARS clean | PASS |
| 10 | Right tool | PASS (behavior restored; depth M, 6 BR) |
| 11 | Length | PASS (M budget 300 to 600) |
| 12 | Every claim cited | PASS |
| 13 | Writer and reader read | PASS (attribute text written by the save, read back by the server `http_server.py:795`) |
| 14 | Verdict consistent | PASS (every BR cites SPEC-0001/FR-005 or SPEC-0015; decided parts are edge cases) |

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | amended in place: 10 over 3 rounds; moved to backlog: none |
