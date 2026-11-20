# Layout picker brings the Breathe decoration: functional specification

> Id: SPEC-0029
> Nature: FEAT
> Depth: M
> Depth evidence: 2 modules (editor page, editor server), 7 requirements, no persisted concept, SPEC-0023 E2E-052 modified
> Status: implemented
> Generated on: 2026-11-19
> Project: existing
> From backlog: BL-0046
> Depends on: SPEC-0023
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary
When the author inserts a Breathe layout from the picker, the new slide shows its background and icons at once. Today it shows none of them until the author runs `mcp-htmleditor breathe-inline` and reloads (SPEC-0023 E2E-052).

## 2. Current State
### 2.1 What users can do today
- In the editor a Breathe deck offers 23 layouts in the picker; choosing one inserts the reference slide with its texts and an empty picture where the reference shows one.
- The inserted slide uses background and icon classes. The deck's decoration block holds the picture of each class the deck already uses. A class with no rule in the block draws nothing: the new slide has no background and no icons.
- The author gets them by running `mcp-htmleditor breathe-inline <file>` (or `--link`), then the editor reloads. (Section 14.1.)
### 2.2 Specs governing this area
SPEC-0023 (Breathe template; FR-NEW-005 picker, EXC-002a, E2E-052 "Inserted layout before embedding"). This spec modifies E2E-052. SPEC-0025: the web library keeps its own editor pages; unchanged here.
### 2.3 What is verified today
E2E-052 asserts `backgroundImage == "none"` after the insertion and a loaded background after the command; E2E-008 replaces the first assertion. Files: Section 14.1.

## 3. Scope
### 3.1 In scope
Background and icon classes of an inserted Breathe layout, embedded or linked like the rest of the deck, with a notice when it cannot be done.
### 3.2 Out of scope, and why
- Pictures of a layout: a layout inserts an empty picture on purpose (SPEC-0023 FR-NEW-005); the author chooses it.
- Duplicating a slide, pasting, agent edits: they do not use the picker; the command remains the way.
- The web library mode: its presentations are single files managed there.
### 3.3 Constraints imposed by the context
None.

## 4. Actors
The author editing a Breathe deck in the editor.

## 4.5 Bounded contexts
| Context | What it owns | Key concepts |
|---|---|---|
| Editing | the editor page and the layout picker | layout, slide, notice |
| Breathe assets | the catalogue of decoration, the deck's decoration block | decoration class, embedded form, linked form |

## 5. Usage scenarios
### SC-001: insert a layout in a deck that embeds its decoration
**Actor:** the author. **Preconditions:** `talk.html` is a Breathe deck open in edit mode whose decoration block embeds the classes of its cover. **Flow:** 1. The author opens the picker and chooses `Pathway` → the deck gets a second slide that shows its background and icons at once. **Postconditions:** the file holds the new slide and the rules of the classes `Pathway` uses; the editor was not reloaded and Undo removes the slide and the rules added for it.
**Exceptions:** EXC-001a: a decoration file is missing from the catalogue → the slide is inserted and the author sees `Decoration not added: asset <name> not found in: <folders>`.
### SC-002: insert a layout in a deck that links its decoration
**Actor:** the author. **Preconditions:** the deck's block refers to `assets/<file>` (linked form). **Flow:** the author inserts `Pathway` → the slide shows its decoration; the files it needs are copied into `assets` next to the deck and the new rules refer to them.
**Exceptions:** EXC-002a: the folder next to the deck cannot be written → the slide is inserted and the author sees `Decoration not added: Cannot write <file>: <reason>`.
### SC-003: a layout whose decoration the deck already has
**Actor:** the author. **Flow:** the author inserts the same layout twice → no rule is added twice; nothing is asked of the files.
### SC-004: other decks
**Actor:** the author with a medical or Carbon deck. **Flow:** inserting a layout changes nothing about decoration.

## 6. Functional requirements
### 6.1 New
#### FR-NEW-001 [EARS-E]: the inserted slide shows its decoration
> WHEN the author inserts a layout in a Breathe deck THE Editing context SHALL, for every background and icon class of the new slide that has no rule in the deck's decoration block, add its rule to the block so that the slide shows its decoration at once.
- **Business rules:** the rules are those `breathe-inline` writes for the same classes (same picture, same form). Classes already in the block are left as they are.
- **Scenario:** SC-001. **Priority:** Must.
#### FR-NEW-002 [EARS-U]: no reload, no loss
> The Editing context SHALL add the decoration without reloading the editor and without removing anything from the undo history.
- **Business rules:** one Undo removes the inserted slide together with the rules added for it; one Redo brings both back. The result is the same for an insertion before and after the current slide.
- **Scenario:** SC-001. **Priority:** Must.
#### FR-NEW-003 [EARS-S]: the form of the deck
> WHILE the deck's decoration rules refer to files in `assets` next to the deck THE Editing context SHALL add rules that refer to `assets/<file>` and SHALL copy the missing files there; otherwise it SHALL embed the pictures in the rules.
- **Business rules:** the deck is linked when at least one rule of its block refers to `assets/`, otherwise it is embedded; an empty block is embedded.
- **Scenario:** SC-002. **Priority:** Must.
#### FR-NEW-004 [EARS-O]: failure keeps the slide
> IF the decoration cannot be added THEN THE Editing context SHALL keep the inserted slide, leave the deck's decoration block as it was, and show the notice `Decoration not added: <reason>` where `<reason>` is the message `breathe-inline` gives for the same failure.
- **Display:** the notice appears in the editor's notice area and stays until the author's next insertion (the save that follows the insertion does not clear it); the inserted slide stays the current slide.
- **User visible text:** `Decoration not added: asset <name> not found in: <folders>`; `Decoration not added: Cannot write <file>: <reason>`; when the editor server cannot be reached, `Decoration not added: the editor server did not answer`.
- **Scenario:** EXC-001a, EXC-002a. **Priority:** Must.
#### FR-NEW-005 [EARS-U]: nothing twice
> The Editing context SHALL NOT add a rule for a class that already has one, and SHALL ask nothing when the new slide needs no new rule.
- **Scenario:** SC-003. **Priority:** Must.
#### FR-NEW-006 [EARS-UB]: other decks untouched
> The Editing context SHALL NOT change the decoration of a deck that is not a Breathe deck.
- **Scenario:** SC-004. **Priority:** Must.
### 6.2 Modified
#### FR-MOD-001 [EARS-E]: inserted layout, decoration (modifies SPEC-0023 EXC-002a and E2E-052)
> WHEN the author inserts a Breathe layout THE inserted slide SHALL show its decoration without running `mcp-htmleditor breathe-inline`.
- **Before:** the slide shows no background until the command runs and the editor reloads. **After:** FR-NEW-001. **Reason:** this spec.

## 7. Non functional requirements
### 7.1 Performance
WHEN the author chooses a layout in the picker THE decoration SHALL show within 3 seconds, on a deck of 20 slides.
### 7.5 Reliability
An interrupted request leaves the deck as it was before the decoration step (FR-NEW-004).
### 7.6 Operability
A failure is visible to the author as a notice (FR-NEW-004); the command remains available.

## 8. Edge cases
| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty | layout needs no new rule | nothing added, no notice | E2E-005 |
| Boundary | the same layout inserted twice | rules once | E2E-005 |
| Access | read only folder, linked form | notice, slide kept | E2E-003 |
| Partial | one needed file missing from the catalogue | notice, block unchanged | E2E-004 |
| Dependency | the editor server does not answer | notice, slide kept | E2E-009 |
| Navigation | picker cancelled | file unchanged | E2E-007 |
| Concurrency, connectivity, exhaustion, ordering | not applicable | | |

## 9. Acceptance tests
### 9.1 Summary
| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | happy | SC-001 | FR-NEW-001, FR-NEW-002 | Critical |
| E2E-002 | New | happy | SC-002 | FR-NEW-003 | High |
| E2E-003 | New | failure | SC-002 | FR-NEW-004 | High |
| E2E-004 | New | failure | SC-001 | FR-NEW-004 | High |
| E2E-005 | New | edge | SC-003 | FR-NEW-005 | High |
| E2E-006 | New | edge | SC-004 | FR-NEW-006 | High |
| E2E-007 | New | edge | SC-001 | FR-NEW-004 (cancel) | Medium |
| E2E-008 | Modified | requirement | SC-001 | FR-MOD-001 | High |
| E2E-009 | New | failure | SC-001 | FR-NEW-004 | Medium |
| E2E-010 | New | side effect | SC-001 | FR-NEW-002 | High |
| E2E-011 | New | edge | SC-002 | FR-NEW-003 | High |
| E2E-012 | New | edge | SC-004 | FR-NEW-006 | High |
| E2E-013 | New | requirement | SC-001 | FR-NEW-001, FR-MOD-001 | High |
| E2E-014 | New | edge | SC-003 | FR-NEW-003, FR-NEW-005 | High |
| E2E-015 | New | edge | SC-003 | FR-NEW-005 | Medium |
Coverage: happy 2, failure 3, side effect 1, requirement 2, edge 7 (the tests of SC-001 to SC-004 above). Happy to failure ratio 1:1.5.

### 9.2 New tests
#### E2E-001: inserted layout shows its decoration at once
- **Given** `talk.html`, the Breathe bootstrap deck (one slide), open in edit mode
- **When** the author inserts `Pathway` from the picker
- **Then** the deck has 2 slides; within 3 s the second slide's background picture is loaded in the editor; the file holds one rule per background and icon class of `Pathway` (read in the file); the editor page was not reloaded
#### E2E-002: linked form
- **Given** `talk.html` made linked (`breathe-inline --link` run on it) and open
- **When** the author inserts `Pathway`
- **Then** the slide shows its background; the new rules read `url(assets/<file>)`; every file they name exists in `assets` next to the deck
#### E2E-003: folder cannot be written, linked form
- **Given** the linked deck of E2E-002 whose folder is read only
- **When** the author inserts `Pathway`
- **Then** the deck has 2 slides, the notice starts `Decoration not added: Cannot write `, and the file's decoration block is unchanged
#### E2E-004: a file missing from the catalogue
- **Given** the Breathe deck open and a catalogue that lacks the file `bg-<x>.png` of one background class `Pathway` uses (the test points the editor at a copy of the catalogue without that file)
- **When** the author inserts `Pathway`
- **Then** the deck has 2 slides, the notice starts `Decoration not added: asset bg-<x>.png not found in: ` and names the deck's `assets` folder then the catalogue folder, and the file's decoration block is unchanged
#### E2E-005: nothing twice
- **Given** the deck of E2E-001 after inserting `Pathway`
- **When** the author inserts `Pathway` again
- **Then** the deck has 3 slides and the file's decoration block is unchanged since the first insertion, with no notice
#### E2E-006: medical deck untouched
- **Given** a medical deck open
- **When** the author inserts a layout
- **Then** the deck has one more slide and its `<style>` blocks are byte identical to before
#### E2E-007: picker cancelled
- **Given** the Breathe deck with the picker shown / **When** the author presses cancel / **Then** one slide and the file byte for byte unchanged (as SPEC-0023 E2E-053)
#### E2E-009: the editor server does not answer
- **Given** the deck open and the browser's request to the editor server for the decoration aborted (the test aborts it)
- **When** the author inserts `Pathway`
- **Then** the deck has 2 slides and the notice reads `Decoration not added: the editor server did not answer`
#### E2E-011: mixed form
- **Given** a deck whose block has one rule embedded and one rule referring to `assets/<file>`
- **When** the author inserts `Pathway`
- **Then** the new rules refer to `assets/<file>` and the files are in `assets` next to the deck (the deck counts as linked)
#### E2E-012: Carbon deck untouched
- **Given** a Carbon deck open **When** the author inserts a layout **Then** one more slide and its `<style>` blocks are unchanged
#### E2E-013: insertion before the current slide
- **Given** the Breathe deck open **When** the author inserts `Pathway` before the current slide **Then** the new slide is first, shows its background within 3 s, and the file holds the rules of its classes
#### E2E-014: nothing twice, linked form
- **Given** the linked deck of E2E-002 after one insertion of `Pathway` **When** the author inserts it again **Then** 3 slides, the decoration block unchanged since the first insertion, no file copied, no notice
#### E2E-015: a layout that needs nothing new
- **Given** the deck of E2E-001 whose block already holds every class of the cover layout **When** the author inserts the cover layout **Then** 2 slides, the decoration block unchanged, no notice
#### E2E-010: undo history kept
- **Given** the author inserted `Pathway` (decoration added)
- **When** the author presses Undo
- **Then** the deck is back to 1 slide, the decoration block of the file saved after the Undo no longer holds the rules of `Pathway`, Redo is available, and pressing Redo brings the slide and the rules back

### 9.3 Modified tests
#### E2E-008: inserted layout and the command (was SPEC-0023 E2E-052 "Inserted layout before embedding")
- **Validated before:** the inserted slide has no background until the command runs
- **Validates now:** the inserted slide has its background without the command, and running `breathe-inline` afterwards keeps the slide showing its background
- **Given** `talk.html`, the Breathe bootstrap deck (one slide), open **When** the author inserts `Pathway` **Then** the background loads within 3 s **And** after `mcp-htmleditor breathe-inline talk.html` is run and the deck shown again, the background is still loaded

## 10. Traceability
| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 002, 004 | E2E-001, E2E-010, E2E-013 | E2E-004, E2E-009 | E2E-007 |
| SC-002 | FR-NEW-003, 004 | E2E-002 | E2E-003 | E2E-011, E2E-014 |
| SC-003 | FR-NEW-005 | | | E2E-005, E2E-014, E2E-015 |
| SC-004 | FR-NEW-006 | | | E2E-006, E2E-012 |
| none | FR-MOD-001 | E2E-008 | | |

## 11. Open questions
None.

## 12. Glossary
| Term | Definition | Context |
|---|---|---|
| decoration class | a class of the new slide named `med-bg-<x>` or `med-ico-<x>`, the classes `breathe-inline` handles | SPEC-0023 |
| decoration block | the part of the deck's style that holds one rule per decoration class | SPEC-0023 |
| embedded form | the rules carry the pictures themselves | SPEC-0023 |
| linked form | the rules refer to files in `assets` next to the deck | SPEC-0023 |
| notice | a message the editor shows to the author | Editing |
| picker | the window offering the layouts | SPEC-0023 |

## 13. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 3 | 6 | NOT-IMPLEMENTABLE |
| 2 | 1 | 2 | amended (library test dropped, snapshot, notice, observables) |

## 14. Evidence appendix
### 14.1 Current State evidence
| Claim (Section 2) | Evidence |
|---|---|
| a layout is inserted as HTML only, no decoration step | `src/mcp_htmleditor/static/editor-slides.js:50-80` (`insertSlide`) |
| the decoration block is written by the command, per class, embedded or linked | `src/mcp_htmleditor/breathe/inline.py:76-120,194-206` (`embed_assets`, `_rule`, `_uri`) |
| E2E-052 asserts no background until the command | `tests/test_breathe_reference.py:146-158` |
| the library mode routes are their own table | `src/mcp_htmleditor/library/routes_deck.py:100-110`, `library/access.py:99` |
Test command: `make check`.
### 14.3 Design inputs
- The server step takes the class list from the page (the new slide is in the page and reaches the file only at save), it does not rescan the file. The browser cannot read the catalogue: the server must supply the rules (a new POST route on the editor server next to `/arch-layout`, `http_server.py:322-336`), through a function of `breathe/inline.py` that reuses `_check_names`, `_locate`, `_rule`, `_copy_missing`.
- Library mode has a route table with permissions where every unregistered POST under a deck is refused (`routes_deck.py:108-109`): the page must not call the route there (E2E-016), and a refusal elsewhere is the "did not answer" notice.
- A network error, a timeout or a non 2xx answer carrying no `breathe-inline` message gives the notice "the editor server did not answer". Undo must restore the decoration block too (the undo snapshot must cover the style block). The page adds the rules to the live style block, then saves through the normal save, keeping the undo history (`restoringFromUndo` is untouched).
