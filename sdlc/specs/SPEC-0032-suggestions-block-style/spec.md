# AI suggestions block of the requests panel looks like the rest of the panel: functional specification

> Id: SPEC-0032
> Nature: FEAT
> Depth: S
> Depth evidence: 1 observable behavior (the look of one block), 1 module (the editor stylesheet), 3 requirements, no persisted change
> Status: implemented
> Generated on: 2026-11-20
> Project: existing
> From backlog: BL-0030
> Depends on: SPEC-0010
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary
The AI suggestions listed in the requests side panel (SPEC-0010, US-0058) are unstyled: a large heading glued to the list above, plain text lines and a white default button on the dark panel. They should look like the requests above them.

## 2. Current State
### 2.1 What users can do today
- With suggestions written by an agent, the panel shows `AI suggestions (N)` and, per suggestion, its title, the reason (`why`) and a button `Apply` (`Applied`, disabled, once used). The block works (SPEC-0010 E2E-006 to E2E-010) but its look is the browser default: a heading much larger than `Requests (N)`, no space between it and the requests list, no frame around a suggestion, and a white button on the dark panel. Evidence: Section 14.1.
### 2.2 Specs governing this area
SPEC-0010 (request loop, FR of the suggestions); no requirement of it states a look. This spec adds one and modifies none.
### 2.3 What is verified today
The behavior of the block (listing, apply, applied state) is covered by browser tests; none looks at the look. Section 14.1.

## 3. Scope
### 3.1 In scope
The look of the suggestions heading, of one suggestion (title, reason, button) and of the `Apply` and `Applied` states.
### 3.2 Out of scope, and why
Wording, order, behavior and position of the block (unchanged); the light theme (the panel has one, dark).
### 3.3 Constraints imposed by the context
None.

## 4. Actors
The person editing a deck with the requests panel open.

## 5. Usage scenarios
### SC-001: read the suggestions
**Actor:** the person. **Preconditions:** an agent wrote 2 suggestions, one already applied. **Flow:** 1. The person opens the requests panel → the block shows a heading like `Requests (N)` set apart from the list above, and each suggestion as a framed card with its title, its reason and a button. **Postconditions:** the applied suggestion is visibly inactive.

## 6. Functional requirements
### 6.1 New
#### FR-NEW-001 [EARS-S]: heading
> WHILE the requests panel is open THE Requests context SHALL show the heading `AI suggestions (N)` in the same size, weight and colour as the heading `Requests (N)`, with a clear space above it separating it from the requests list.
- **Business rules:** same size 12 px, weight 600, colour `#f4f4f4`; at least 16 px of space above.
- **Scenario:** SC-001. **Priority:** Should.
#### FR-NEW-002 [EARS-S]: a suggestion as a card
> WHILE the requests panel is open THE Requests context SHALL show each suggestion as a card like a request: dark background `#262626`, 1 px border `#393939`, padding 6 px by 8 px, with the title in `#f4f4f4` and weight 600, the reason in `#c6c6c6`, and the button under them aligned left, a 6 px gap between cards.
- **Scenario:** SC-001. **Priority:** Should.
#### FR-NEW-003 [EARS-S]: the Apply button
> WHILE a suggestion is not applied THE Requests context SHALL show its button `Apply` with background `#0f62fe` and white text; WHILE it is applied THE button reads `Applied`, has background `#393939`, text `#8d8d8d` and the default pointer.
- **Business rules:** no white button on the dark panel; the focus ring stays visible.
- **Scenario:** SC-001. **Priority:** Should.

## 7. Non functional requirements
Not applicable: no behavior, text or data changes.

## 8. Edge cases
| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty | no suggestion | heading `AI suggestions (0)` styled as in FR-NEW-001, no card | E2E-001 |
| Boundary | a long title or reason | wraps inside the 300 px panel, never overflows horizontally | E2E-003 |
| Data | markup looking text in a title | shown as text, same look (SPEC-0010 E2E safeguards unchanged) | E2E-002 |
| Concurrency, connectivity, access, navigation, ordering, exhaustion | not applicable | | |

## 9. Acceptance tests
### 9.1 Summary
| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | requirement | SC-001 | FR-NEW-001 | High |
| E2E-002 | New | requirement | SC-001 | FR-NEW-002 | High |
| E2E-003 | New | edge | SC-001 | FR-NEW-002 | Medium |
| E2E-004 | New | requirement | SC-001 | FR-NEW-003 | High |
| E2E-005 | New | state transition | SC-001 | FR-NEW-003 | High |
Coverage: requirement 3, edge 1, state transition 1. No behavior changes, so no failure scenario exists; the SPEC-0010 tests stay green.
### 9.2 New tests
#### E2E-001: heading
- **Given** the editor open with 2 suggestions written and the requests panel open
- **When** the person looks at the headings
- **Then** `AI suggestions (2)` has font size 12 px, weight 600, colour `rgb(244, 244, 244)`, and at least 16 px between it and the requests list above; `Requests (N)` has the same size, weight and colour
#### E2E-002: card
- **Given** the same
- **When** the person looks at a suggestion
- **Then** it has background `rgb(38, 38, 38)`, a 1 px border `rgb(57, 57, 57)`, padding 6 px 8 px; its title is `rgb(244, 244, 244)` weight 600; its reason `rgb(198, 198, 198)`; its button sits under them with the same left edge; the gap between two cards is 6 px
#### E2E-003: long text
- **Given** a suggestion whose title is 60 characters (the maximum) without space and whose reason is 300 characters
- **When** the panel shows it
- **Then** the card's width does not exceed the panel's inner width and the panel has no horizontal scroll
#### E2E-004: Apply button
- **Given** a suggestion not applied
- **Then** its `Apply` button has background `rgb(15, 98, 254)` and text `rgb(255, 255, 255)`
#### E2E-005: Applied state
- **Given** the same suggestion
- **When** the person presses `Apply`
- **Then** its button reads `Applied`, is disabled, has background `rgb(57, 57, 57)` and text `rgb(141, 141, 141)`, and its cursor is `default`

## 10. Traceability
| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 002, 003 | E2E-001, E2E-002, E2E-004, E2E-005 | none (no behavior) | E2E-003 |

## 11. Open questions
None.

## 12. Glossary
| Term | Definition | Context |
|---|---|---|
| suggestion | a proposed change an agent wrote for the deck, with a title, a reason and an Apply button | SPEC-0010 |
| requests panel | the dark side panel listing the requests and the suggestions | SPEC-0010 |

## 13. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 0 | 0 | IMPLEMENTABLE |

**Amendments applied:** none. **No implementation detail outside Section 14:** PASS (colours and sizes are the look requested).

## 14. Evidence appendix
### 14.1 Current State evidence
| Claim (Section 2) | Evidence |
|---|---|
| the suggestions block is built with an `h2`, a `ul`, per item a title, a why and a button | `src/mcp_htmleditor/static/editor-requests.js:25-26,187-205` |
| no rule styles the block; the requests have rules | `rg -n "suggestion" src/mcp_htmleditor/static/editor.css` finds nothing; requests rules at `editor.css:506-528` |
| behavior tests exist | `tests/test_review_apply_e2e.py` (E2E-006 to E2E-010) |
Test command: `make check`.
### 14.3 Design inputs
The look follows the existing rules of the requests list (`#requests-heading`, `#requests-list li`, `editor.css:517-528`); the browser tests reuse `_open`, `_write_review`, `_row` of `tests/test_review_apply_e2e.py`.
