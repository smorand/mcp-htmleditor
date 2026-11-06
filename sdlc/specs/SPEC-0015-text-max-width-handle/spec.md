# Text width bar in the editor: functional specification

> Id: SPEC-0015
> Nature: FEAT
> Depth: M
> Depth evidence: depth M imposed by the requester (`--depth M`); counts: 2 areas (browser editing, agent guidance), 15 requirements, no persisted concept, no public contract change beyond one new inline declaration in the saved file
> Status: specified
> Generated on: 2026-11-06
> Project: existing
> From backlog: n/a
> Depends on: SPEC-0002 (edit mode, undo and redo), SPEC-0006 (skill topics and their size budget), SPEC-0009 (save, conflict and error notices)
> Ported from: the sibling product snxt-deck-builder, branch develop, CHANGELOG "Unreleased" entry on the text width bar (read only reference)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

Nature: FEAT (Q1 yes: the editor offers no way to set how wide a text runs, see 14.1 E1 and E2; Q2 no
authority describes such a control, so nothing is violated).

## 1. Summary

A person editing a slide or a document in the browser can change a text's words and formatting, but
not how wide the text runs: a headline that breaks badly or a paragraph that runs the full width of a
slide can only be fixed by asking the agent to edit the file. This increment adds a thin bar on the
right edge of the text under the pointer, in edit mode. Dragging it sets the text's maximum width in
the slide's own pixels, a double click gives the template's width back, and the result is one plain
inline declaration that the agent reads like any other markup and that the person can undo. It is a
port of the same control in the sibling product snxt-deck-builder, adapted to an editor that saves the
whole file at once and to presentations, documents, websites and mails alike.

## 2. Current State

### 2.1 What users can do today

- In edit mode every element marked as editable text becomes typeable at once, with a dashed outline
  (E1). The floating format bar offers bold, italic, underline, strike, superscript, subscript,
  alignment, font size, colours and clearing; nothing sets a width (E2).
- Images inserted from the editor carry an inline maximum width of 100 percent and are resized by the
  browser's own handles inside the text; there is no editor drawn resize handle (E3).
- In documents and websites every top level block gets a reorder handle on its left side, 26 pixels
  outside the block (E4). In presentations architecture nodes are moved with the mouse (E5).
- Slides are shown at their own size (at most 960 pixels wide, narrower when the window is narrower,
  never scaled) while editing; only the fullscreen presentation scales the slide (E6).
- Every change is saved by sending the whole document; editor markers are removed first in the
  browser and again by the server, so the saved file never holds them (E7, E8).
- Undo and redo cover structural actions only (insert, delete, move, reorder); typing keeps the
  browser's own undo (E9). At most 50 steps are kept (E10).
- The agent's lint reports, among others, colours written in inline styles that are outside the
  charter palette, and missing width classes on medical rows; nothing reads an inline width (E11). The agent reads a slide's markup as it is in the file
  (E12).
- The PPTX export applies an inline maximum width to images and annotated images only; text boxes
  ignore it (E13). The DOCX export does not read inline widths either (E20).
- The agent guidance topic on creating and editing lists what the person can do in the browser and
  is 7792 bytes of an 8000 byte budget; the export topic is 7238 bytes (E14, E15).

### 2.2 Specs governing this area

- SPEC-0002/FR-009, FR-010, FR-011: undo and redo of structural actions, the shortcut left to the
  browser while it has typing to revert, at most 50 steps. This increment adds the width change to
  the structural actions; it does not change those three rules.
- SPEC-0002/FR-014: an inserted or reordered block gets no attribute or inline style. Not affected: the
  width declaration is written only by an explicit width action on a text.
- SPEC-0009: save status, conflict notice, error notice. Reused unchanged for width saves.
- SPEC-0006: skill topics and their 8000 byte budget per topic, 7000 for the core. Kept.
- SPEC-0007: lint rules L001 to L011. None added, none changed.

### 2.3 What is verified today

Browser tests exercise undo and redo of eight structural actions, autosave while typing, save notices
and the removal of editor markers before saving (E16). No test sets a text's width, because no such
control exists.

## 3. Scope

### 3.1 In scope

- The width bar on the text under the pointer, in edit mode, in presentations, documents, websites and
  mails.
- Dragging, keyboard steps and the reset, saved as one inline declaration on that text.
- One undo step per width change; nothing of the bar ever saved.
- Agent guidance: one line in the creating and editing topic, one line in the export topic.

### 3.2 Out of scope, and why

- PPTX and DOCX exports honouring a text's width: the exporters lay text out from the block's width
  today, and changing that touches the layout engine of both. Deferred to BL-0033.
- Setting a width on images, table cells, diagram nodes, Gantt tasks and annotations: each already has
  its own sizing rule (browser handles, columns, computed layout, percentages).
- Setting a height, a minimum width or a width in another unit than pixels.
- A warning that some mail clients ignore an inline maximum width: the mail guidance already tells the
  author to check the render in a real client before sending.
- A new message, toast or confirmation: the existing save status and notices are enough.

### 3.3 Constraints imposed by the context

- The saved form is imposed by the requester: the width is the inline declaration `max-width:Npx` on
  the text itself, with N a whole number of pixels, so the file stays readable and editable by the
  agent. This markup is the product's output read by agents, so it is spelled exactly in this spec.
- Editing markers are never saved (README and the guidance promise a clean file, E8).
- Agent guidance topics stay within their byte budgets (SPEC-0006).

## 4. Actors

| Actor | Who | What they do here |
|---|---|---|
| Author | the person editing in the browser | sets, adjusts, resets and undoes a text's width |
| Agent | the LLM working on the same file through its tools | reads and keeps the width the author set |

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Browser editing | what the author changes in the open file and how it is saved and undone | edit mode, text block, width bar, undo step, save status |
| Agent guidance | what the agent is told about the file and the editor | guidance topic, lint problem, slide markup |

## 5. Usage scenarios

### SC-001: Set a text's width by dragging

**Actor:** Author
**Preconditions:** a file is open in the editor, edit mode is on.
**Flow:**
1. The author points at a text block → the width bar appears on its right edge, as tall as the block.
2. The author presses the bar and drags → the text's width follows the pointer live, in steps of 10
   slide pixels (1 pixel while Alt is held), and the bar shows the value, for example `650 px`.
3. The author lets go → the width is saved as `max-width:650px` in the text's inline style; the save
   status shows saved.
**Postconditions:** the file holds the declaration; reloading shows the text at that width.
**Exceptions:**
- EXC-001a: the drag is interrupted by the system (pointer lost) → the text returns to its previous
  width and nothing is saved.
- EXC-001b: the file changed on disk meanwhile → the existing conflict notice shows.
- EXC-001c: the server is unreachable → the existing error notice shows, the change stays pending.
- EXC-001d: the pointer is on an image, a table cell, a diagram node, a Gantt task or an annotation →
  no bar.
**Interactions:** SC-004 (each saved width is one undo step).

### SC-002: Adjust a width with the keyboard

**Actor:** Author
**Preconditions:** the bar is shown on a text and has the keyboard focus (the author clicked it).
**Flow:**
1. Right arrow → width plus 10 pixels, saved. Left arrow → minus 10. With Shift, 50.
**Postconditions:** each press is one saved change and one undo step.
**Exceptions:**
- EXC-002a: the width is already at a bound → the press saves nothing.

### SC-003: Give the template's width back

**Actor:** Author
**Preconditions:** the bar is shown on a text.
**Flow:**
1. The author double clicks the bar (or presses Delete or Backspace while it has the focus) → the
   inline width is removed and the text takes the width its template gives it; saved.
**Exceptions:**
- EXC-003a: the text has no inline width → nothing changes, nothing is saved.

### SC-004: Undo and redo a width change

**Actor:** Author
**Preconditions:** at least one width change was saved in this session.
**Flow:**
1. The author presses Undo (button, or the shortcut outside a text with typing to revert) → the text's
   inline style is back to what it was before the change; saved.
2. Redo → the change is back; saved.
**Exceptions:**
- EXC-004a: the caret is in a text whose typing the browser can still revert → the shortcut reverts
  typing first, as today (SPEC-0002/FR-010).

### SC-005: The agent reads and keeps a width

**Actor:** Agent
**Preconditions:** the author set a width.
**Flow:**
1. The agent reads the slide or the file → it sees `max-width:Npx` in the text's inline style.
2. The agent lints the file → the same problems as before the change.
3. The agent loads its guidance → it learns that the bar exists, what it writes, and that the export
   does not apply it.
**Postconditions:** the agent treats the width as a deliberate human choice (core rule 8).

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-S]: Width bar on the pointed text

> WHILE edit mode is on THE editor SHALL show the width bar on the right edge of the text block under
> the pointer.

- **Business rules:** the bar is as tall as the block and sits on its right edge, inside the window.
  It stays on that edge while the page scrolls or the window is resized. It hides when the pointer
  leaves both the block and the bar (except during a drag), when the slide changes, when edit mode is
  turned off and when the document reloads. It takes the keyboard focus when clicked.
- **User visible text:** accessible name `Largeur du texte`; tooltip
  `Glisser pour régler la largeur, double clic pour revenir à la largeur du modèle`.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-002 [EARS-U]: What a text block is

> The editor SHALL treat as a text block the innermost element under the pointer that is inside an
> editable text zone, is a paragraph, a heading of level 1 to 6, a list item, a quotation, a figure
> caption or the editable text zone itself, and is not laid out inline within a line of text.

- **Business rules:** when the pointer is on an inline piece of text (a word, a tag), the enclosing
  text block gets the bar. A list item inside a list inside a zone: the list item gets the bar.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-003 [EARS-UB]: Where the bar never shows

> The editor SHALL NOT show the width bar on an image, on a table or anything inside it, on a diagram
> node or edge, on a Gantt task, on an annotation, on the editor's own controls, outside edit mode,
> during the fullscreen presentation, or while an agent update is in progress.

- **Business rules:** a text block inside a table cell gets no bar. A text block with no width on
  screen (hidden) gets no bar.
- **Scenario:** SC-001 (EXC-001d)
- **Priority:** Must

#### FR-NEW-004 [EARS-E]: Dragging sets the width live

> WHEN the author drags the width bar THE editor SHALL set the text's maximum width to its width at
> the press plus the pointer's horizontal travel, both counted in the slide's own pixels.

- **Business rules:** the slide's own pixels are the document's, whatever size the slide is shown at:
  on a slide shown at half size, 50 pixels of pointer travel are 100 slide pixels. The value is
  rounded to the nearest multiple of 10, or to the nearest whole pixel while Alt is held, then kept
  between 80 and 1280 included. The text reflows live. While dragging, the bar shows the value as the
  number, a space and `px` (example `650 px`); the readout disappears when the drag ends.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-005 [EARS-E]: Letting go saves one declaration

> WHEN the author lets go of the width bar after moving it THE editor SHALL save the text's inline
> style with the declaration `max-width:Npx`, N being the last value shown.

- **Business rules:** the inline style is rebuilt as: its declarations split on `;`, each trimmed,
  empty ones and any existing `max-width` declaration (whatever its unit) dropped, the others kept in
  their order and with their exact text, then `max-width:Npx` appended, all joined with `; `. A text
  with no style gets `style="max-width:Npx"`. Example: `color:#0F62FE;font-weight:600` becomes
  `color:#0F62FE; font-weight:600; max-width:650px`. A `;` inside parentheses or inside a quoted
  string is part of its declaration and is not a separator; such a declaration is kept character for
  character. Example: `background:url(data:image/png;base64,AAA);color:#123456` becomes
  `background:url(data:image/png;base64,AAA); color:#123456; max-width:650px`.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-006 [EARS-E]: Keyboard steps

> WHEN the width bar has the keyboard focus and the author presses Right or Left THE editor SHALL save
> the text's width as its current width on the slide, rounded to a whole pixel, plus or minus 10
> pixels, kept between 80 and 1280.

- **Business rules:** with Shift held the step is 50. Each press is one saved change, written as in
  FR-NEW-005. Other keys keep their usual effect.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-007 [EARS-E]: Reset to the template's width

> WHEN the author double clicks the width bar, or presses Delete or Backspace while it has the focus,
> THE editor SHALL remove the `max-width` declaration from the text's inline style and save.

- **Business rules:** the other declarations are kept as in FR-NEW-005, the same separator rule
  included. When none is left the style
  attribute is removed entirely. The text then takes the width its template gives it.
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-008 [EARS-O]: No change, no save

> IF a width action leaves the text's inline style text identical THEN THE editor SHALL save nothing
> and record no undo step.

- **Business rules:** covers a press and release without movement, a drag ending on the value already
  written, a key press at a bound, and a reset on a text without inline width.
- **Scenario:** SC-001, SC-002, SC-003
- **Priority:** Must

#### FR-NEW-009 [EARS-E]: One undo step per width change

> WHEN a width change is saved THE editor SHALL record it as one structural undo step that Undo
> reverts and Redo reapplies, each saving the file.

- **Business rules:** SPEC-0002/FR-009, FR-010 and FR-011 apply unchanged (buttons, shortcuts, the
  shortcut left to the browser while it has typing to revert, at most 50 steps, a new change clears
  Redo). Undo restores the inline style text exactly as it was before the change.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-010 [EARS-UB]: Nothing of the bar is saved

> The editor SHALL NOT save the width bar, its readout, any marker of the pointed text, or a width
> still being dragged.

- **Business rules:** a save that happens during a drag (for example the autosave of typing done
  just before) writes the width the text had before the drag. After any width action the only
  difference in the file is the text's style as stated in FR-NEW-005 or FR-NEW-007.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-011 [EARS-O]: Interrupted drag

> IF a drag of the width bar is cancelled by the system THEN THE editor SHALL show the text at the
> width it had before the drag and save nothing.

- **Business rules:** a reload of the document during a drag (an agent update ending) cancels the
  drag the same way: the reloaded file is shown and the editor saves nothing.
- **Scenario:** SC-001 (EXC-001a)
- **Priority:** Must

#### FR-NEW-012 [EARS-UB]: Everything else untouched

> The editor SHALL NOT change, through a width action, any text, any other element, or the written
> form of any other declaration of the text's style.

- **Business rules:** a colour written as `#0F62FE` stays `#0F62FE`. Typing done before the drag is
  kept and saved.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-013 [EARS-U]: Saved like every other edit

> The editor SHALL save a width change through the same save as every other edit, with its status,
> conflict notice and error notice.

- **User visible text (existing, SPEC-0009):** conflict notice
  `The file changed on disk. Reload to see the changes, or keep your version.`; connection notice
  `Connection to the editor server lost`.
- **Scenario:** SC-001 (EXC-001b, EXC-001c)
- **Priority:** Must

#### FR-NEW-014 [EARS-U]: The agent sees a plain declaration

> The agent tools SHALL show a width set by the author as the `max-width:Npx` declaration in the
> text's inline style, and the lint SHALL report the same problems before and after a width change.

- **Scenario:** SC-005
- **Priority:** Must

#### FR-NEW-015 [EARS-U]: Agent guidance

> The agent guidance SHALL hold, in the creating and editing topic under "Ce que l'humain peut faire",
> line L1, and in the export topic under "Perdu", line L2, both spelled exactly as below.

```text
L1: - Largeur d'un texte: barre sur son bord droit (glisser par pas de 10px, Alt au pixel, flèches; double clic: largeur du modèle). Écrit `max-width:Npx` dans son `style`.
L2: - Le `max-width` d'un texte (barre de largeur de l'éditeur): la zone de texte garde la largeur de son bloc.
```

- **Business rules:** the `L1: ` and `L2: ` prefixes are labels of this spec, not part of the lines. Each topic stays within its 8000
  byte budget and the size audit reports no problem. The core is unchanged: its rule 8 already tells
  the agent that a human change found in the file is deliberate.
- **Scenario:** SC-005
- **Priority:** Must

### 6.2 Modified

None. SPEC-0002/FR-009 gains one more structural action through FR-NEW-009; its statement still holds
as written.

### 6.3 Removed

None.

## 7. Non functional requirements (user observable)

### 7.1 Performance

- NFR-001 [EARS-S]: WHILE the author drags the bar THE editor SHALL reflow the text with each pointer
  move, with no visible lag on a slide of 30 text blocks.

### 7.4 Usability and accessibility

- NFR-002 [EARS-U]: The bar SHALL be reachable by a click and usable with the keyboard alone once
  focused (FR-NEW-006, FR-NEW-007), and SHALL show a visible focus outline.

### 7.5 Reliability

- NFR-003 [EARS-UB]: The saved file SHALL NOT hold an editing marker after any sequence of width
  actions, undos, redos, reloads and conflicts (FR-NEW-010).

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty states | text with no style | `style="max-width:Npx"` added | E2E-023 (list item without style) |
| Empty states | reset on text without width | nothing saved | E2E-012 |
| Boundary values | drag below 80 or above 1280 | 80, 1280 | E2E-003, E2E-004 |
| Boundary values | key press at 80 | nothing saved | E2E-009 |
| Concurrent actions | agent changed the file during the drag | conflict notice | E2E-026 |
| Concurrent actions | autosave of typing during a drag | old width saved, then the new one | E2E-018 |
| Slow or lost connectivity | server down on release | error notice, pending | E2E-027 |
| Access states | edit mode off, presenting, agent update | no bar | E2E-022 |
| Data variations | existing width in em, other declarations, hex colour, `;` inside `url(...)` | replaced; kept verbatim | E2E-007, E2E-006, E2E-028, E2E-042 |
| Data variations | inline word, nested list item | enclosing block; the item | E2E-021, E2E-023 |
| Navigation | slide change, scroll, reload | bar hides or follows | E2E-024, E2E-025 |
| Partial operations | drag cancelled; click without move | nothing saved | E2E-019, E2E-020 |
| Dependency failures | server unreachable | E2E-027 | E2E-027 |
| Ordering and timing | undo while typing in another text | browser undoes typing first | E2E-015 |
| Exhaustion | more than 50 width changes | oldest step dropped (SPEC-0002/FR-011, already tested) | not retested |
| Display scale | slide shown at half size | value in slide pixels | E2E-005 |

## 9. Acceptance tests (the contract)

> Behavioral and technology agnostic. /sdlc-design maps each test to a driver.

### 9.0 Fixtures

- **Deck D1**: an IBM Carbon presentation open in edit mode, window 1280 by 900, slide shown at its
  full 960 pixels. Slide 2 body holds a column 800 pixels wide containing, in order: paragraph A
  `Chiffres clés du trimestre`, style `max-width:600px`; paragraph B `Note de synthèse`, style
  `color:#0F62FE;font-weight:600`, holding the inline tag word `Nouveau`; paragraph H `Objectifs`,
  style `max-width: 40em;color:#525252;font-size:10px`; paragraph I `Mini`, style `max-width:85px`; paragraph J
  `Hors charte`, style `color:#123456`; paragraph K `Large`, style `max-width:1250px`; paragraph P
`Agent`, style `max-width:50%`; paragraph Q `Fond`, style
`background:url(data:image/png;base64,AAA);color:#123456`; a bulleted list `Premier point`, `Second point`; a table with
  header `Indicateur` and cell `Valeur A1`; an image `logo`. Slide 3 holds an architecture node
  `Serveur MCP`, a Gantt task `Cadrage` and an annotation `Pic`. Every paragraph and the list are
  editable text.
- **Deck D3**: D1 whose template shows slide 2 at half size (480 pixels wide on screen).
- **Document D2**: a Perso document with title `Rapport Q1` and 40 paragraphs `Paragraphe 1` to
  `Paragraphe 40`, paragraph 1 with style `max-width:500px`.
- **Mail M1**: the mail bootstrap; its intro paragraph has a long inline style ending in
  `text-align:justify;`.
- **Website W1**: the website bootstrap, tab label `Vue d'ensemble`.

### 9.1 Summary

| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | journey | SC-001 | FR-NEW-001, 004, 005, 013 | Critical |
| E2E-002 | New | requirement | SC-001 | FR-NEW-004, 005 | High |
| E2E-003 | New | edge | SC-001 | FR-NEW-004 | High |
| E2E-004 | New | edge | SC-001 | FR-NEW-004 | High |
| E2E-005 | New | edge | SC-001 | FR-NEW-004 | Critical |
| E2E-006 | New | side effect | SC-001 | FR-NEW-005, 012, 014 | Critical |
| E2E-007 | New | side effect | SC-001 | FR-NEW-005, 012 | High |
| E2E-008 | New | journey | SC-002 | FR-NEW-006, 009 | High |
| E2E-009 | New | failure | SC-002 | FR-NEW-006, 008 | Medium |
| E2E-010 | New | journey | SC-003 | FR-NEW-007 | High |
| E2E-011 | New | side effect | SC-003 | FR-NEW-007, 012 | High |
| E2E-012 | New | failure | SC-003 | FR-NEW-007, 008 | Medium |
| E2E-013 | New | requirement | SC-003 | FR-NEW-007 | Medium |
| E2E-014 | New | state transition | SC-004 | FR-NEW-009 | Critical |
| E2E-015 | New | failure | SC-004 | FR-NEW-009 | High |
| E2E-016 | New | failure | SC-004 | FR-NEW-009, 008 | Medium |
| E2E-017 | New | side effect | SC-001 | FR-NEW-010, 012, 014 | Critical |
| E2E-018 | New | edge | SC-001 | FR-NEW-010, 012 | High |
| E2E-019 | New | failure | SC-001 | FR-NEW-010, 011 | High |
| E2E-020 | New | failure | SC-001 | FR-NEW-008, 011 | Medium |
| E2E-021 | New | failure | SC-001 | FR-NEW-002, 003 | Critical |
| E2E-022 | New | failure | SC-001 | FR-NEW-001, 003 | High |
| E2E-023 | New | edge | SC-001 | FR-NEW-001, 002 | High |
| E2E-024 | New | journey | SC-001 | FR-NEW-001, 005 | High |
| E2E-025 | New | state transition | SC-001 | FR-NEW-001 | Medium |
| E2E-026 | New | failure | SC-001 | FR-NEW-013 | High |
| E2E-027 | New | failure | SC-001 | FR-NEW-013 | Medium |
| E2E-028 | New | side effect | SC-005 | FR-NEW-012, 014 | High |
| E2E-029 | New | requirement | SC-005 | FR-NEW-015 | High |
| E2E-030 | New | requirement | SC-002 | FR-NEW-001, 006 | Medium |
| E2E-031 | New | journey | SC-001 | FR-NEW-002, 005 | Medium |
| E2E-032 | New | side effect | SC-001 | FR-NEW-012 | High |
| E2E-033 | New | failure | SC-001 | FR-NEW-002, 003 | Medium |
| E2E-034 | New | requirement | SC-005 | FR-NEW-015 | High |
| E2E-035 | New | requirement | SC-005 | FR-NEW-015 | Medium |
| E2E-036 | New | failure | SC-001 | FR-NEW-011, 010 | High |
| E2E-037 | New | failure | SC-002 | FR-NEW-006 | Medium |
| E2E-038 | New | edge | SC-002 | FR-NEW-006 | Medium |
| E2E-039 | New | failure | SC-003 | FR-NEW-007, 013 | Medium |
| E2E-040 | New | edge | SC-004 | FR-NEW-009 | Medium |
| E2E-041 | New | edge | SC-005 | FR-NEW-005, 014 | High |
| E2E-042 | New | edge | SC-001 | FR-NEW-005, 012 | High |
| E2E-043 | New | failure | SC-005 | FR-NEW-001, 010, 014 | High |

Coverage: happy 5 (journey), requirement 6, failure 15, side effect 6, edge 9, state transition 2,
security 0 (no new input reaches a dangerous place: the width is a bounded whole number written by the
editor itself). Happy to failure ratio 1:3.

### 9.2 New tests

#### E2E-001: Drag a paragraph's width and save it
- **Category:** journey · **Scenario:** SC-001 · **Requirements:** FR-NEW-001, 004, 005, 013
- **Given** D1 on slide 2, edit mode on
- **When** the author points at paragraph A, presses the bar on its right edge, moves the pointer 47
  pixels to the right and lets go
- **Then** while moving the bar reads `650 px`, after letting go the readout is gone
- **And** the file's paragraph A style reads `max-width:650px` and the save status shows saved
- **And** after a reload paragraph A is 650 pixels wide
- **Priority:** Critical

#### E2E-002: Alt gives single pixels
- **Category:** requirement · **Scenario:** SC-001 · **Requirements:** FR-NEW-004, 005
- **Given** D1 on slide 2 · **When** the author drags A's bar 47 pixels right with Alt held and lets go
- **Then** the readout showed `647 px` and A's style reads `max-width:647px`
- **Priority:** High

#### E2E-003: Lower bound
- **Category:** edge · **Scenario:** SC-001 · **Requirements:** FR-NEW-004
- **Given** D1 on slide 2 · **When** the author drags A's bar 600 pixels left and lets go
- **Then** the readout showed `80 px` and A's style reads `max-width:80px`
- **Priority:** High

#### E2E-004: Upper bound
- **Category:** edge · **Scenario:** SC-001 · **Requirements:** FR-NEW-004
- **Given** D1 on slide 2, window 2400 pixels wide · **When** the author drags A's bar 900 pixels
  right and lets go
- **Then** the readout showed `1280 px` and A's style reads `max-width:1280px`
- **Priority:** High

#### E2E-005: Slide pixels on a scaled slide
- **Category:** edge · **Scenario:** SC-001 · **Requirements:** FR-NEW-004
- **Given** D3 on slide 2 (shown at half size) · **When** the author drags A's bar 50 screen pixels
  right and lets go
- **Then** A's style reads `max-width:700px` (not `650px`)
- **Priority:** Critical

#### E2E-006: Other declarations and their colour kept verbatim
- **Category:** side effect · **Scenario:** SC-001 · **Requirements:** FR-NEW-005, 012, 014
- **Given** D1 on slide 2, B is 800 pixels wide · **When** the author drags B's bar 153 pixels left
  and lets go
- **Then** B's style reads exactly `color:#0F62FE; font-weight:600; max-width:650px`
- **And** no style in the file holds `rgb(`; the rest of the file is byte identical to before
- **Priority:** Critical

#### E2E-007: An existing width in another unit is replaced
- **Category:** side effect · **Scenario:** SC-001 · **Requirements:** FR-NEW-005, 012
- **Given** D1 on slide 2, H rendered 400 pixels wide (40em at 10 pixels) · **When** the
  author drags H's bar 200 pixels right and lets go
- **Then** H's style reads exactly `color:#525252; font-size:10px; max-width:600px`
- **Priority:** High

#### E2E-008: Keyboard steps
- **Category:** journey · **Scenario:** SC-002 · **Requirements:** FR-NEW-006, 009
- **Given** D1 on slide 2, the author clicked A's bar (A is 600 wide) · **When** they press Right,
  then Shift and Right, then Left
- **Then** A's style reads `max-width:610px`, then `max-width:660px`, then `max-width:650px`, each
  saved
- **And** three Undo presses bring A back to `max-width:600px`
- **Priority:** High

#### E2E-009: Key at the lower bound saves nothing
- **Category:** failure · **Scenario:** SC-002 · **Requirements:** FR-NEW-006, 008
- **Given** D1, the author clicked I's bar (I is 85 wide) · **When** they press Left, then Left
- **Then** after the first press I's style reads `max-width:80px`; the second press saves nothing
  and leaves the file unchanged; one Undo brings back `max-width:85px` and Undo is then disabled
- **Priority:** Medium

#### E2E-010: Double click gives the template's width back
- **Category:** journey · **Scenario:** SC-003 · **Requirements:** FR-NEW-007
- **Given** D1 on slide 2 · **When** the author double clicks A's bar
- **Then** paragraph A in the file has no style attribute at all, the save status shows saved, and A
  is 800 pixels wide
- **Priority:** High

#### E2E-011: Reset keeps the other declarations
- **Category:** side effect · **Scenario:** SC-003 · **Requirements:** FR-NEW-007, 012
- **Given** D1 · **When** the author double clicks H's bar
- **Then** H's style reads exactly `color:#525252; font-size:10px`
- **Priority:** High

#### E2E-012: Reset without an inline width does nothing
- **Category:** failure · **Scenario:** SC-003 · **Requirements:** FR-NEW-007, 008
- **Given** D1, Undo disabled · **When** the author double clicks B's bar twice
- **Then** the file is byte identical to before, no save happens, Undo stays disabled
- **Priority:** Medium

#### E2E-013: Delete and Backspace reset
- **Category:** requirement · **Scenario:** SC-003 · **Requirements:** FR-NEW-007
- **Given** D1, the author clicked A's bar · **When** they press Delete
- **Then** A has no style attribute in the file
- **And** with I's bar focused, Backspace leaves I without style attribute
- **Priority:** Medium

#### E2E-014: Undo then redo a drag
- **Category:** state transition · **Scenario:** SC-004 · **Requirements:** FR-NEW-009
- **Given** E2E-001 just done (A at 650) · **When** the author clicks Undo, then Redo
- **Then** after Undo the file's A style reads `max-width:600px` and A is 600 wide; after Redo
  `max-width:650px`; both saved
- **Priority:** Critical

#### E2E-015: The shortcut reverts typing first
- **Category:** failure · **Scenario:** SC-004 · **Requirements:** FR-NEW-009
- **Given** D1, the author drags A's bar until the readout shows `650 px`, then clicks at the end of paragraph J and types `!`
- **When** they press Ctrl or Cmd with Z once, caret still in J
- **Then** J reads `Hors charte` again and A's style still reads `max-width:650px`
- **Priority:** High

#### E2E-016: A new width change clears Redo
- **Category:** failure · **Scenario:** SC-004 · **Requirements:** FR-NEW-009, 008
- **Given** E2E-014's Undo done (A at 600, Redo enabled) · **When** the author presses Right on A's
  focused bar
- **Then** A reads `max-width:610px` and Redo is disabled
- **Priority:** Medium

#### E2E-017: Nothing of the editor in the file
- **Category:** side effect · **Scenario:** SC-001 · **Requirements:** FR-NEW-010, 012, 014
- **Given** D1 · **When** the author drags A to 650, presses Right on it, double clicks H, Undoes,
  Redoes and reloads
- **Then** compared with D1 on disk the file differs only in the style of A and H; it contains no
  element, class, id or attribute added by the editor, and the readout text `px` appears nowhere
  outside a style
- **Priority:** Critical

#### E2E-018: An autosave during the drag keeps the old width
- **Category:** edge · **Scenario:** SC-001 · **Requirements:** FR-NEW-010, 012
- **Given** D1, the author types `!` at the end of paragraph J
- **When** within half a second they press A's bar, move it 100 pixels right, hold still 2 seconds
  (the typing autosave fires), then move back 50 and let go
- **Then** read during the hold, the file has J `Hors charte!` and A `max-width:600px`; after letting
  go A reads `max-width:650px` and J still `Hors charte!`
- **Priority:** High

#### E2E-019: A cancelled drag changes nothing
- **Category:** failure · **Scenario:** SC-001 · **Requirements:** FR-NEW-010, 011
- **Given** D1 · **When** the author drags A's bar 100 pixels right and the system cancels the pointer
  (for example the window loses the pointer)
- **Then** A is 600 wide again, the file is unchanged, Undo stays disabled
- **Priority:** High

#### E2E-020: Press and release without moving
- **Category:** failure · **Scenario:** SC-001 · **Requirements:** FR-NEW-008, 011
- **Given** D1 · **When** the author presses A's bar and lets go without moving
- **Then** no save happens and Undo stays disabled
- **Priority:** Medium

#### E2E-021: No bar on sized or positioned things
- **Category:** failure · **Scenario:** SC-001 · **Requirements:** FR-NEW-002, 003
- **Given** D1 in edit mode · **When** the author points in turn at the cell `Valeur A1`, the header
  `Indicateur`, the image `logo`, then on slide 3 at `Serveur MCP`, `Cadrage` and `Pic`
- **Then** no width bar shows for any of them
- **And** pointing at the word `Nouveau` shows the bar on paragraph B's right edge, as tall as B
- **Priority:** Critical

#### E2E-022: No bar outside editing
- **Category:** failure · **Scenario:** SC-001 · **Requirements:** FR-NEW-001, 003
- **Given** D1 · **When** the author points at A with edit mode off; then in the fullscreen
  presentation; then in edit mode while the agent's update overlay shows
- **Then** no width bar shows in any of the three
- **Priority:** High

#### E2E-023: Nested list item
- **Category:** edge · **Scenario:** SC-001 · **Requirements:** FR-NEW-001, 002
- **Given** D1 · **When** the author points at `Second point` and drags its bar left until the readout
  shows `300 px` and lets go
- **Then** the bar was as tall as that item only; the item's style reads `max-width:300px`; the list
  and `Premier point` have no style
- **Priority:** High

#### E2E-024: Document, scrolled, with the reorder handle
- **Category:** journey · **Scenario:** SC-001 · **Requirements:** FR-NEW-001, 005
- **Given** D2 in edit mode, scrolled so `Paragraphe 30` is in view · **When** the author points at it,
  scrolls 200 pixels, then drags its bar until the readout shows `500 px`
  and lets go
- **Then** after the scroll the bar is still on that paragraph's right edge; its style reads
  `max-width:500px`
- **And** dragging `Paragraphe 30` by its reorder handle above `Paragraphe 29` still works and the
  moved paragraph keeps `max-width:500px`
- **Priority:** High

#### E2E-025: The bar hides
- **Category:** state transition · **Scenario:** SC-001 · **Requirements:** FR-NEW-001
- **Given** D1, the bar shown on A · **When** the author moves the pointer to an empty area of the
  page; then points at A again and goes to slide 3 with the next arrow
- **Then** the bar hides in both cases
- **Priority:** Medium

#### E2E-026: File changed on disk during a drag
- **Category:** failure · **Scenario:** SC-001 · **Requirements:** FR-NEW-013
- **Given** D1, the author is dragging A's bar · **When** the agent writes the file (paragraph J now
  `Changé`) and the author lets go at 650
- **Then** the notice `The file changed on disk. Reload to see the changes, or keep your version.`
  shows; the file still holds the agent's version
- **Priority:** High

#### E2E-027: Server unreachable
- **Category:** failure · **Scenario:** SC-001 · **Requirements:** FR-NEW-013
- **Given** D1, the editor server stopped · **When** the author drags A to 650 and lets go
- **Then** the save error notice shows (its text is the browser's network message, unchanged by this
  feature), the status stays pending, A stays 650 wide on screen; after three failed polls
  `Connection to the editor server lost` shows
- **Priority:** Medium

#### E2E-028: The agent reads it and lint is unchanged
- **Category:** side effect · **Scenario:** SC-005 · **Requirements:** FR-NEW-012, 014
- **Given** D1, the agent's lint lists `colour #123456 is not in the carbon palette` for slide 2
- **When** the author drags J's bar 150 pixels left and lets go; the agent reads slide 2 and lints the file
- **Then** slide 2's markup shows J with style `color:#123456; max-width:650px`; the lint lists
  exactly the same problems as before, `colour #123456 is not in the carbon palette` included
- **Priority:** High

#### E2E-029: Creating topic line
- **Category:** requirement · **Scenario:** SC-005 · **Requirements:** FR-NEW-015
- **Given** the product installed · **When** the agent runs `mcp-htmleditor skill --type create`
- **Then** the output holds the FR-NEW-015 creating line verbatim under "Ce que l'humain peut faire"
- **Priority:** High

#### E2E-030: Name, tooltip and focus
- **Category:** requirement · **Scenario:** SC-002 · **Requirements:** FR-NEW-001, 006
- **Given** D1, bar shown on A · **When** the author hovers it, then clicks it
- **Then** the tooltip reads `Glisser pour régler la largeur, double clic pour revenir à la largeur du modèle`,
  the accessible name is `Largeur du texte`, after the click it has the keyboard focus with a
  visible outline, and Right then works (A `max-width:610px`)
- **Priority:** Medium

#### E2E-031: Mail paragraph
- **Category:** journey · **Scenario:** SC-001 · **Requirements:** FR-NEW-002, 005
- **Given** M1 in edit mode · **When** the author drags the intro paragraph's bar until the
  readout shows `400 px` and lets go
- **Then** that paragraph's style holds all its previous declarations in order, each with its exact
  text, followed by `; max-width:400px`, and nothing after it
- **Priority:** Medium

#### E2E-032: Typing before the drag is kept
- **Category:** side effect · **Scenario:** SC-001 · **Requirements:** FR-NEW-012
- **Given** D1 · **When** the author types `!` at the end of A, then at once drags A's bar until the readout shows `650 px`
- **Then** the file's A reads `Chiffres clés du trimestre!` with style `max-width:650px`
- **Priority:** High

#### E2E-033: Inline label in a clickable control
- **Category:** failure · **Scenario:** SC-001 · **Requirements:** FR-NEW-002, 003
- **Given** W1 in edit mode · **When** the author points at the tab label `Vue d'ensemble`
- **Then** no width bar shows (the label is inline and its enclosing control is not a text block)
- **Priority:** Medium

#### E2E-034: Export topic line
- **Category:** requirement · **Scenario:** SC-005 · **Requirements:** FR-NEW-015
- **When** the agent runs `mcp-htmleditor skill --type export`
- **Then** the output holds the FR-NEW-015 export line verbatim under "Perdu"
- **Priority:** High

#### E2E-035: Budgets kept
- **Category:** requirement · **Scenario:** SC-005 · **Requirements:** FR-NEW-015
- **When** the agent runs `mcp-htmleditor skill-audit`
- **Then** it exits 0, the creating and export topics are each at most 8000 bytes, and the core is
  byte identical to before this increment
- **Priority:** Medium

#### E2E-036: A reload during the drag
- **Category:** failure · **Scenario:** SC-001 · **Requirements:** FR-NEW-011, 010
- **Given** D1, the author is dragging A's bar, readout `700 px` · **When** the agent ends an update
  that changed paragraph J to `Changé` and the editor reloads the document, then the author lets go
- **Then** the page shows J `Changé` and A at 600; the file holds A `max-width:600px`; no save by the
  editor happened and Undo is disabled
- **Priority:** High

#### E2E-037: Other keys do not change the width
- **Category:** failure · **Scenario:** SC-002 · **Requirements:** FR-NEW-006
- **Given** D1, the author clicked A's bar · **When** they press Up, Down, `a` and Enter
- **Then** the file is unchanged and Undo is disabled
- **Priority:** Medium

#### E2E-038: Keys start from the width on the slide
- **Category:** edge · **Scenario:** SC-002 · **Requirements:** FR-NEW-006
- **Given** D1, paragraph K (`max-width:1250px`) is 800 pixels wide in its column · **When** the
  author clicks K's bar and presses Right
- **Then** K's style reads `max-width:810px`
- **Priority:** Medium

#### E2E-039: Reset with the server unreachable
- **Category:** failure · **Scenario:** SC-003 · **Requirements:** FR-NEW-007, 013
- **Given** D1, the editor server stopped · **When** the author double clicks A's bar
- **Then** A is 800 wide on screen, the save error notice shows and the status stays pending
- **And** once the server is back, the next save writes A without style attribute
- **Priority:** Medium

#### E2E-040: A reload empties the history
- **Category:** edge · **Scenario:** SC-004 · **Requirements:** FR-NEW-009
- **Given** E2E-001 done (A at 650) · **When** the author reloads the editor page
- **Then** Undo is disabled and A stays `max-width:650px` in the file
- **Priority:** Medium

#### E2E-041: A width written by the agent in percent
- **Category:** edge · **Scenario:** SC-005 · **Requirements:** FR-NEW-005, 014
- **Given** D1, paragraph P written by the agent with `max-width:50%` (400 pixels in its column)
- **When** the author drags P's bar 47 pixels right and lets go
- **Then** P's style reads `max-width:450px`; reading slide 2 the agent sees exactly that
- **Priority:** High

#### E2E-042: A `;` inside a value is not a separator
- **Category:** edge · **Scenario:** SC-001 · **Requirements:** FR-NEW-005, 012
- **Given** D1, paragraph Q is 800 pixels wide · **When** the author drags Q's bar 153 pixels left and
  lets go
- **Then** Q's style reads exactly `background:url(data:image/png;base64,AAA); color:#123456; max-width:650px`
- **Priority:** High

#### E2E-043: The agent writes the file while the bar shows
- **Category:** failure · **Scenario:** SC-005 · **Requirements:** FR-NEW-001, 010, 014
- **Given** D1, the bar shown on A, no drag · **When** the agent writes the file with A's style
  `max-width:500px` and the editor reloads the document
- **Then** the bar is hidden until the pointer moves again; pointing at A shows it on A's new right
  edge (A 500 wide); the file holds the agent's `max-width:500px` and the editor saved nothing
- **Priority:** High

### 9.3 Exploit tests

Not applicable: not a security entry (Section 7.2 not changed, see 9.1 note).

### 9.4 Modified tests

None. The existing undo, autosave, save notice and marker removal tests stay as they are.

### 9.5 Removed tests

None.

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001 to 005, 008, 010 to 013 | E2E-001, 024, 031 | E2E-019, 020, 021, 022, 026, 027, 033, 036 | E2E-003, 004, 005, 018, 023, 042 |
| SC-002 | FR-NEW-006, 008 | E2E-008 | E2E-009, 037 | E2E-038 |
| SC-003 | FR-NEW-007, 008, 013 | E2E-010 | E2E-012, 039 | E2E-013 |
| SC-004 | FR-NEW-009 | E2E-014 | E2E-015, 016 | E2E-040 |
| SC-005 | FR-NEW-014, 015 | E2E-029 | E2E-043 | E2E-041 |

Side effect tests per scenario: SC-001 E2E-006, 007, 017, 032; SC-002 E2E-030 (focus outline) and
E2E-008 (each press saved); SC-003 E2E-011; SC-004 E2E-014 (each step saved); SC-005 E2E-028, 034.

Requirements to tests: FR-NEW-001 (001, 022, 023, 024, 025, 030, 043); 002 (021, 023, 031, 033);
003 (021, 022, 033); 004 (001, 002, 003, 004, 005); 005 (001, 002, 006, 007, 024, 031, 041, 042);
006 (008, 009, 030, 037, 038); 007 (010, 011, 012, 013, 039); 008 (009, 012, 016, 020); 009 (008, 014, 015, 016, 040);
010 (017, 018, 019, 036, 043); 011 (019, 020, 036); 012 (006, 007, 011, 017, 018,
028, 032, 042); 013 (001, 026, 027, 039); 014 (006, 017, 028, 041, 043); 015 (029, 034, 035).

## 11. Open questions

- The test designer, self consistency and auditor steps ran without an in session subagent tool: the
  test plan was written by the requirements author, the self consistency check ran inline, the
  implementability audit ran in a separate fresh agent process given only this file's path and the
  contract. Does not change observable behavior.
- Test plan approval: the requester ordered no questions and recommended defaults; the plan above is
  taken as approved on that instruction. Does not change observable behavior.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Width bar | the thin vertical control on the right edge of the pointed text block | Browser editing |
| Text block | an element the bar can size, defined in FR-NEW-002 | Browser editing |
| Editable text zone | an element the file marks as editable text, typeable in edit mode | Browser editing |
| Slide pixels | pixels of the document itself, independent of the size the slide is shown at | Browser editing |
| Template's width | the width a text has from its template's styles, with no inline width | Browser editing |
| Readout | the value shown on the bar while dragging, such as `650 px` | Browser editing |
| Undo step | one entry of the editor's structural undo history (SPEC-0002) | Browser editing |
| Guidance topic | one section of the agent guidance loaded on demand (SPEC-0006) | Agent guidance |
| Lint | the agent's check of a file's structure and charter (SPEC-0007) | Agent guidance |
| Inline style | the style written on the element itself in the file | Browser editing |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 1 | 2 | NOT-IMPLEMENTABLE |
| 2 | 0 | 2 | IMPLEMENTABLE |

**Amendments applied:** round 1: F-1 (separator rule in FR-NEW-005 and FR-NEW-007, fixture Q,
E2E-042); A-1 (Section 8 empty style row); A-2 (E2E-035 reclassified, E2E-043 added as the SC-005
failure test). Round 2: A-1 (E11 claim names L008), A-2 (DOCX claim cited, E20). Both rounds
audited by a fresh agent process given only the path and the contract.
**No implementation detail outside Section 14:** PASS (the saved declaration, the guidance lines and
the lint message are the product's output to agents, see 3.3)

## 14. Evidence appendix

### 14.1 Current State evidence

| Id | Claim (Section 2) | Evidence |
|---|---|---|
| E1 | edit mode makes every editable text typeable at once | `src/mcp_htmleditor/static/editor-edit.js:30-44` |
| E2 | format bar offers no width | `src/mcp_htmleditor/static/editor-format.js:57,74,90` (commands), `skill/topics/create.md:36` |
| E3 | inserted images get inline `max-width:100%`, native resize only | `src/mcp_htmleditor/static/editor-format.js:249`, `src/mcp_htmleditor/static/editor-undo.js:9-12` |
| E4 | document reorder handle 26 px left of each block | `src/mcp_htmleditor/static/editor-edit.js:133-134`, `src/mcp_htmleditor/static/editor-drag.js:28-30` |
| E5 | architecture nodes dragged in presentations | `src/mcp_htmleditor/static/editor-edit.js:43` |
| E6 | slide at most 960 px, no scale while editing, scale only in fullscreen | `templates/bootstrap/slides-empty.html:88-89,253-256` |
| E7 | browser strips markers on a clone before saving the whole file | `src/mcp_htmleditor/static/editor-save.js:20-34` |
| E8 | server strips editor ids, classes and attributes again | `src/mcp_htmleditor/http_server.py:52-71,854-890` |
| E9 | undo covers structural actions only | `src/mcp_htmleditor/static/editor-undo.js:1-24,61-69` |
| E10 | at most 50 undo steps | `src/mcp_htmleditor/static/editor.js:356` |
| E11 | lint reads inline style only for hex colours (L011); L008 checks `w-*` classes on medical flex rows, never inline widths | `src/mcp_htmleditor/deck/charter_rules.py:117-126,146-158` |
| E12 | agent reads a slide's markup | `src/mcp_htmleditor/deck/read.py:33` |
| E13 | PPTX applies `max-width` to images and annotated images only | `src/mcp_htmleditor/export/pptx_blocks.py:164,177-180`, `src/mcp_htmleditor/export/pptx_images.py:33`; search `rg -n -i 'max-width' --glob '*.py' src` returns only these and `export/pptx_style.py:38` |
| E14 | creating topic 7792 bytes; export topic 7238 bytes | `wc -c skill/topics/create.md skill/topics/export.md` |
| E15 | topic budget 8000, core 7000 | `src/mcp_htmleditor/skill_content.py:46-47` |
| E16 | existing tests: 8 undo and redo, 10 autosave, 8 save notices, 3 marker removal | `tests/test_undo_redo_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_save_ui_e2e.py`, `tests/test_strip_idempotent.py` (counts of `def test`) |
| E17 | existing notice texts | `src/mcp_htmleditor/static/editor.html:57,62` |
| E18 | agent update overlay | `src/mcp_htmleditor/static/editor.css:238`, `src/mcp_htmleditor/static/editor.js:44` |
| E20 | DOCX export has no width handling | `rg -i width src/mcp_htmleditor/export/to_docx.py` returns nothing |
| E19 | source behavior ported | snxt-deck-builder `tools/deck/editor/editor.js:468-560`, `tools/deck/lib/editable.mjs:122-145`, `tools/deck/lib/server.mjs:391-421` |

Test command: `make test` (subset `make test ARGS='-k width'`); gate `make check`.

### 14.3 Design inputs

- Setting the width through the element's style object makes the browser rewrite the whole style
  attribute in its normalized form (hex colours become `rgb(...)`, spacing changes), which breaks
  FR-NEW-005, FR-NEW-012 and L011 (E11). The written attribute needs a text level rebuild as in the
  source's `applyWidth` (E19), while the live preview during the drag may use the style object and be
  restored before any save. Detection signal: E2E-006, E2E-028.
- An autosave during a drag (E7 serializes the live document) would capture the preview width:
  the preview must be invisible to the serializer or reverted on the clone. Detection signal: E2E-018.
- Where the bar lives (parent page overlaid on the frame, or inside the frame) is open; inside the
  frame it must be added to both marker strippers (E7, E8) and to the undo snapshot cleanup
  (`editor-undo.js:27-56`). Detection signal: E2E-017.
- The undo step must be pushed before the inline style changes (pre mutation snapshot,
  `editor-undo.js:58-69`), and a cancelled or no change action must not push one. Detection signal:
  E2E-009, E2E-012, E2E-019, E2E-020.
- No new route is needed: the width rides the whole file save (`POST /content`, E7). The source's
  dedicated `/api/width` route and its hash check (E19) have no counterpart here; the SPEC-0009 base
  mtime conflict check covers E2E-026.
- Slide pixels: divide pointer travel by the ratio of the element's on screen width to its layout
  width, as the source does (E19). The current templates never scale while editing (E6); E2E-005
  needs a fixture whose template scales the slide.
- In edit mode every text is already typeable (E1), unlike the source where the bar hides on the text
  being edited: here the bar shows on the focused text too, and pressing it must not lose typing.
  Detection signal: E2E-018, E2E-032.
- The creating topic has 208 bytes left (E14, E15); the FR-NEW-015 line is 171 bytes plus a newline.
  Detection signal: E2E-035.
- Documents to update: `README.md` (browser editing list), `AGENTS.md` if a convention is added,
  `.agent_docs/html-conventions.md` (undo coverage, markers), `.agent_docs/architecture.md` (browser
  side), `CHANGELOG` if present.
- Deferred: BL-0033 (exports honour a text's width).
