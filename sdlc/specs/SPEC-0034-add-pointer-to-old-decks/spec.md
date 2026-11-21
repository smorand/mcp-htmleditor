# Bring the presentation pointer to decks created before it existed: functional specification

> Id: SPEC-0034
> Nature: FEAT
> Depth: M
> Depth evidence: 2 surfaces (a command and an agent tool) of one behavior, 1 module, 9 requirements, no persisted concept
> Status: implemented
> Generated on: 2026-11-21
> Project: existing
> From backlog: BL-0038
> Depends on: SPEC-0017, SPEC-0022
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary
A presentation created before the pointer (SPEC-0017) has no `Pointeur` control and ignores the `L` key. A person or an agent can now add the pointer to such a deck with one command or one agent operation, without recreating the deck.

## 2. Current State
### 2.1 What users can do today
- Every presentation created from a template since SPEC-0017 carries the pointer: a `Pointeur` control next to `Présenter`, the `L` key, and the red dot drawn on the slide while presenting.
- A deck created before that has none of the three: the editor shows no `Pointeur` control for it and `L` does nothing (SPEC-0017 E2E-035). The only way to get the pointer is to copy the code by hand.
- The agent interface offers twenty three operations; none adds the pointer.
Evidence: Section 14.1.
### 2.2 Specs governing this area
SPEC-0017 (the pointer; FR-NEW-002 and E2E-035 about older decks; section 3.2 defers this); SPEC-0007/FR-NEW-016 (a command has an agent operation with the same results and errors); SPEC-0022 (the presenter block, not part of this spec). None is modified.
### 2.3 What is verified today
The pointer in a new deck and the editor's behavior with an older deck. Section 14.1.

## 3. Scope
### 3.1 In scope
One command `mcp-htmleditor add-pointer <file>` and one agent operation `add_pointer(file)` giving a presentation the three parts of the pointer; the skill line and the documentation.
### 3.2 Out of scope, and why
- The presenter window and the speaker notes (SPEC-0022): another block, not requested.
- A button in the editor: the command and the operation reach it; the editor keeps hiding the control for a deck without the pointer.
- Decks that cannot go full screen at all (no `Présenter` control): they are refused with a message (the convention says such a file is to be patched first).
### 3.3 Constraints imposed by the context
SPEC-0007/FR-NEW-016: the agent operation gives the results and errors of the command. The deck stays one self contained file.

## 4. Actors
A person or an LLM agent with a presentation file; the person presenting it.

## 5. Usage scenarios
### SC-001: add the pointer to an older deck
**Actor:** an agent. **Preconditions:** `talk.html` is a presentation with a `Présenter` control and no pointer. **Flow:** 1. The agent runs the command (or the operation) on `talk.html` → the file gains the pointer's code, a `Pointeur` control right after `Présenter`, and the `L` key; the agent receives `talk.html: pointer added`. **Postconditions:** the deck, opened full screen with `L` or through `Pointeur`, shows the red dot; a previous version is kept in the file history.
**Exceptions:**
- EXC-001a: the file does not exist → `File not found: <file>`.
- EXC-001b: the file is a template file of the editor → `Refusing to modify a template: <file>`.
- EXC-001c: the file is not a presentation → `<file> is not a presentation`.
- EXC-001d: the deck has no `Présenter` control → `<file> has no Présenter control, nothing to place the Pointeur control after`.
### SC-002: a deck that already has the pointer
**Flow:** the agent runs it again (or on a new deck) → `talk.html: already has the pointer`, the file is untouched.
### SC-003: a deck with part of the pointer
**Flow:** a deck that has one or two of the three parts (the six combinations) → only the missing parts are added; the message is `talk.html: pointer added`.

## 6. Functional requirements
### 6.1 New
#### FR-NEW-001 [EARS-E]: add the pointer
> WHEN a person or an agent asks to add the pointer to a presentation that lacks it THE system SHALL add the pointer's code, a `Pointeur` control next to the `Présenter` control (after it), and the `L` key, as a new template carries them, and SHALL answer `<file>: pointer added`.
- **Business rules:** a part is present when: the code, a `<script id="deck-pointer-script">` outside HTML comments; the control, an element with `id="btn-pointer"`; the key, a test of the pressed key against `l` in the deck's own key handler, or the script `deck-pointer-key` this spec adds. The `Présenter` control is the element with `id="btn-present"`. A deck that already has a `btn-pointer` never gets a second one (in two reference decks it sits before `btn-present`). The three parts behave as in a new deck (SPEC-0017): the control starts a presentation with the pointer on, `L` turns the dot on and off while presenting. Nothing else of the file changes: its slides, texts, styles and scripts stay as they were.
- **Scenario:** SC-001. **Priority:** Must.
#### FR-NEW-002 [EARS-O]: nothing to do
> IF the presentation already has the three parts THEN THE system SHALL leave the file untouched and answer `<file>: already has the pointer`.
- **Scenario:** SC-002. **Priority:** Must.
#### FR-NEW-003 [EARS-O]: only what is missing
> IF the presentation has some of the three parts THEN THE system SHALL add only the missing ones and answer `<file>: pointer added`.
- **Scenario:** SC-003. **Priority:** Must.
#### FR-NEW-004 [EARS-O]: refusals
> IF the file does not exist, is a template file of the editor, is not a presentation, or lacks the control and has no `Présenter` control THEN THE system SHALL refuse with the message of the scenario (`File not found: <file>`, `Refusing to modify a template: <file>`, `<file> is not a presentation`, `<file> has no Présenter control, nothing to place the Pointeur control after`) and SHALL leave the file as it was.
- **Business rules:** a presentation is a file with at least one `data-type="slide"`. A deck lacking only the code or the key needs no `Présenter` control. A file that is not valid UTF-8 is refused with `File is not valid UTF-8: <file>`. A deck that has the three parts is answered `already has the pointer`.
- **Scenario:** SC-001 exceptions. **Priority:** Must.
#### FR-NEW-005 [EARS-U]: the previous version is kept
> The system SHALL keep the previous content in the file's version history when it adds the pointer, and SHALL write no history entry when it answers `already has the pointer`.
- **Priority:** Must.
#### FR-NEW-006 [EARS-E]: the same through the agent interface
> WHEN an agent asks the agent interface to add the pointer to a file THE agent interface SHALL give the same file and the same answer or refusal message as the command, the refusal message without `error: `.
- **Business rules:** the operation is named `add_pointer` and takes the file.
- **Priority:** Must.
#### FR-NEW-007 [EARS-U]: repeatable
> The system SHALL leave the file byte for byte unchanged when the same request is repeated.
- **Scenario:** SC-002. **Priority:** Must.
#### FR-NEW-008 [EARS-U]: skill and documentation
> The agent skill SHALL list the operation with one line, and the documentation SHALL describe the command, the operation and the twenty four agent operations.
- **Priority:** Must.
### 6.2 Modified
#### FR-MOD-001 [EARS-U]: the list of agent operations (modifies SPEC-0028/FR-MOD-001)
> The agent interface SHALL offer twenty four operations: the twenty three listed today and `add_pointer`.
- **Before:** twenty three. **After:** twenty four. **Reason:** this spec.

## 7. Non functional requirements
### 7.1 Performance
The command answers within 2 seconds for a deck of 5 MB.
### 7.5 Reliability
A failed write leaves the file as it was (the version history is written by the same atomic step as the file).

## 8. Edge cases
| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty | already complete | untouched, `already has the pointer` | E2E-002 |
| Partial | code present, control and key missing | the two missing parts added | E2E-003 |
| Partial | control present, code missing | code and key added | E2E-003 |
| Data | the deck's `Présenter` control has other attributes and a different class | the new control copies its class and sits right after it | E2E-001 |
| Data | accents and a file name with spaces | works | E2E-001 |
| Concurrency, connectivity, access, navigation, exhaustion | not applicable (a local file) | | |
| Data | CRLF line endings | the inserted text uses the file's line ending | E2E-001 |
| Data | the code's script appears only inside an HTML comment | the code counts as absent | E2E-003 |
| Other charters | Carbon, Euro-Information, medical, Breathe, standard decks | each works | E2E-007 |

## 9. Acceptance tests
### 9.1 Summary
| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | journey | SC-001 | FR-NEW-001, FR-NEW-005 | Critical |
| E2E-002 | New | edge | SC-002 | FR-NEW-002, FR-NEW-007 | High |
| E2E-003 | New | edge | SC-003 | FR-NEW-003 | High |
| E2E-004 | New | failure | SC-001 | FR-NEW-004 | High |
| E2E-005 | New | failure | SC-001 | FR-NEW-004 | High |
| E2E-006 | New | requirement | SC-001 | FR-NEW-006 | High |
| E2E-007 | New | edge | SC-001 | FR-NEW-001 | High |
| E2E-008 | Modified | side effect | | FR-NEW-008, FR-MOD-001 | High |
| E2E-009 | New | failure | SC-001 | FR-NEW-004 | Medium |
Coverage: happy 2 (E2E-001, E2E-006), failure 3, edge 3, side effect 1. Happy to failure ratio 1:1.5.
### 9.2 New tests
An "older deck" is a template deck of a charter with the three parts taken out (the code between its pointer markers, the `Pointeur` control, the `L` line); its other parts are those of its template.
#### E2E-001: add the pointer to an older Carbon deck
- **Given** an older Carbon deck `talk.html` (file name with a space and an accent: `Réunion talk.html`)
- **When** the agent runs `add-pointer` on it
- **Then** the answer is `Réunion talk.html: pointer added` (the path as given), exit status 0; for the CRLF deck the inserted lines end with CRLF; the file now has the pointer's code, a `Pointeur` control right after the `Présenter` control with the same class, and the `L` key; the file's other content is as before; opened in the editor and put full screen with `Pointeur`, pressing `L` while the deck is full screen shows the red dot, and `L` again hides it; the version history holds the previous content
#### E2E-002: complete deck, repeated request
- **Given** a deck created from a template today, and an older deck after one request
- **When** the request is made (again)
- **Then** `<file>: already has the pointer`, exit status 0, bytes unchanged, no new history entry
#### E2E-003: partial decks
- **Given** older decks with each of the six combinations of one or two parts present (only the code, only the control, only the key, code and control, code and key, control and key), one with the code's script only inside an HTML comment, and one with CRLF line endings
- **Then** after the request each has the three parts exactly once and the answer `pointer added`
#### E2E-004: file not found and template file
- **Given** no file `absent.html`, and the Carbon bootstrap template of the editor
- **Then** `File not found: absent.html` and `Refusing to modify a template: <that file>`, exit status 1, the template unchanged, no file created
#### E2E-005: not a presentation and no Présenter control
- **Given** a document file; an older deck without its `Présenter` control
- **Then** `<doc> is not a presentation` and `<deck> has no Présenter control, nothing to place the Pointeur control after`, exit status 1 each, files unchanged
#### E2E-006: the agent interface
- **Given** two copies of the same older deck
- **When** the agent interface adds the pointer to one and the command to the other
- **Then** the files are byte identical, the answer of the operation carries the same text, and the refusals of E2E-004 and E2E-005 read the same without `error: `
#### E2E-007: every charter
- **Given** an older deck of each charter: Carbon, Euro-Information, medical, Breathe, standard presentation
- **Then** each, after the request, has the three parts and works full screen (the dot shows with `L`)
#### E2E-008: the list of agent operations (modified test, was SPEC-0028 E2E-008)
- **Then** the operations are twenty four with `add_pointer`, the skill lists the same, and the skill audit reports no problem
#### E2E-009: a deck without the pointer still opens
- **Given** an older deck with no request made
- **Then** the editor shows no `Pointeur` control for it, as today (SPEC-0017 E2E-035), unchanged

## 10. Traceability
| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 004, 005, 006 | E2E-001, E2E-006 | E2E-004, E2E-005, E2E-009 | E2E-007 |
| SC-002 | FR-NEW-002, 007 | | | E2E-002 |
| SC-003 | FR-NEW-003 | | | E2E-003 |
| none | FR-NEW-008, FR-MOD-001 | E2E-008 | | |

## 11. Open questions
None.

## 12. Glossary
| Term | Definition | Context |
|---|---|---|
| older deck | a presentation created before the pointer existed | SPEC-0017 |
| the three parts | the pointer's code, the `Pointeur` control, the `L` key | SPEC-0017 |
| Présenter control | the deck's own button that starts the full screen presentation | SPEC-0001 |
| template file | a file shipped with the editor under its templates | SPEC-0023 |
| version history | the previous contents of a file kept by the editor | SPEC-0009 |

## 13. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 0 | 0 | IMPLEMENTABLE (round 1 findings fixed) |

## 14. Evidence appendix
### 14.1 Current State evidence
| Claim | Evidence |
|---|---|
| the three parts in a new deck | `templates/bootstrap/slides-empty.html:294` (control), `:404` (L line), `:423-649` (code between `deck-pointer:begin` and `deck-pointer:end`) |
| older decks are left alone | `sdlc/specs/SPEC-0017-*/spec.md` section 3.2, E2E-035; `src/mcp_htmleditor/static/editor.js` `deckCarriesPointer` |
| a command has an agent operation | SPEC-0007/FR-NEW-016; `src/mcp_htmleditor/mcp_server.py` (`breathe_inline`) |
| refusals of the same kind exist | `src/mcp_htmleditor/breathe/inline.py:92-103` |
Test command: `make check`.
### 14.3 Design inputs
Reuse `embed_assets`' pattern (template refusal, atomic write with a history reason, `DeckError` messages) in a new module under `src/mcp_htmleditor/deck/`; the code block comes from the Carbon bootstrap between its markers (source of truth, `tools/sync_deck_pointer.py`); the control is built from the deck's own `Présenter` control (class kept); the `L` key as a small script of its own marked with an id; the skill core file is at 5995 of its 6000 byte cap (`tests/test_skill_shipped.py`), so freeing bytes in `skill/core.md` is a task of the story that adds the skill line. The L key is a line of the deck's own key handler, not of the deck-presenter block (SPEC-0022).
