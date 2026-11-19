# Breathe embedding as an agent tool: functional specification

> Id: SPEC-0028
> Nature: FEAT
> Depth: S
> Depth evidence: 1 behavior (the agent interface gains the operation the command line already has), 1 module, 5 requirements, no persisted change, no existing contract changed
> Status: implemented
> Generated on: 2026-11-19
> Project: existing
> From backlog: BL-0045
> Depends on: SPEC-0023
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary
An agent that edits a Breathe presentation can embed (or link) the decoration and pictures the deck uses without
going through a shell: the agent interface gets the same operation as the command `breathe-inline`, with the same
result line and the same error messages. Today it must run the command line (BL-0045).

## 2. Current State
### 2.1 What users can do today
- A person or an agent runs `mcp-htmleditor breathe-inline <file> [--link]`: the decoration classes and the named
  pictures of a Breathe deck are written into the deck (or, with `--link`, referred to as files next to the deck), and
  one summary line is printed, for example `deck.html: 3 background and icon classes, 2 pictures embedded, 214 KB`.
- The agent interface offers twenty two operations; none of them embeds Breathe assets.
- Errors of the command are single lines on the error stream, for example `error: File not found: deck.html`.
### 2.2 Specs governing this area
SPEC-0023 (Breathe template, the command `breathe-inline`); SPEC-0007/FR-NEW-016 (every command has an agent
operation with the same results and errors). This spec adds no deviation.
### 2.3 What is verified today
The command is covered by tests of SPEC-0023; the list of agent operations is asserted by a test that names all
twenty two. Commands and files: Section 14.1.

## 3. Scope
### 3.1 In scope
One new agent operation equivalent to `breathe-inline`, with the skill text and the documentation that list the agent
operations updated.
### 3.2 Out of scope, and why
- Changing what the command embeds or its messages: this spec only exposes it.
- Opening an update window around the write: the command does not, so the operation behaves the same.
### 3.3 Constraints imposed by the context
SPEC-0007/FR-NEW-016 says the agent operation returns the same results and errors as the command.

## 4. Actors
An LLM agent using the agent interface; a person reading the result line.

## 5. Usage scenarios
### SC-001: embed the decoration of a Breathe deck
**Actor:** an agent.
**Preconditions:** `talk.html` is a Breathe deck whose decoration block is empty and which uses 3 decoration classes and 2 named pictures available in the catalogue.
**Flow:**
1. The agent asks the interface to embed the assets of `talk.html` → the deck is rewritten with the decoration and pictures embedded, and the agent receives the summary line.
**Postconditions:** the file holds the embedded decoration and pictures; a second identical call leaves it unchanged.
**Exceptions:**
- EXC-001a: the file does not exist → the agent receives the error `File not found: <file>`.
- EXC-001b: the file is a template file shipped with the editor → `Refusing to modify a template: <file>`.
- EXC-001c: the deck has no Breathe decoration block → `<file> has no breathe:assets block in its <style>`.
### SC-002: link instead of embed
**Actor:** an agent. **Preconditions:** as SC-001. **Flow:** the agent asks for the linked form → the deck refers to `assets/<file>` next to the deck, the files are copied there, and the agent receives the summary line of the linked form. **Postconditions:** the folder `assets` next to the deck holds the copied files.

## 6. Functional requirements
### 6.1 New
#### FR-NEW-001 [EARS-E]: embed through the agent interface
> WHEN an agent asks to embed the Breathe assets of a deck THE agent interface SHALL write the decoration and pictures into the deck exactly as the command `breathe-inline` does and SHALL return the summary line the command prints.
- **Business rules:** the file written is byte identical to the one the command writes for the same deck.
- **Scenario:** SC-001. **Priority:** Must.

#### FR-NEW-002 [EARS-E]: linked form
> WHEN an agent asks for the linked form THE agent interface SHALL refer to the files in `assets` next to the deck, copy them there, and return the summary line of the linked form, as `breathe-inline --link` does.
- **Scenario:** SC-002. **Priority:** Must.

#### FR-NEW-003 [EARS-O]: same errors
> IF the command `breathe-inline` would refuse the call THEN THE agent interface SHALL refuse it with the same message, without `error: `, and SHALL leave the file as it was.
- **User visible text:** `File not found: <file>`; `Refusing to modify a template: <file>`; `<file> has no breathe:assets block in its <style>`; `File is not valid UTF-8: <file>`; `asset <name> is not a plain file name`; `asset <name> not found in: <folders>`.
- **Scenario:** SC-001 exceptions. **Priority:** Must.

#### FR-NEW-004 [EARS-U]: repeatable
> The agent interface SHALL leave the deck unchanged when the same call is repeated.
- **Scenario:** SC-001. **Priority:** Should.

#### FR-NEW-005 [EARS-U]: the skill lists it
> The agent skill SHALL list the operation among the agent operations with one line describing it, and the documentation SHALL state the new number of operations.
- **Business rules:** the skill audit command reports no problem; the number is twenty three.
- **Priority:** Must.

### 6.2 Modified
#### FR-MOD-001 [EARS-U]: the list of agent operations (modifies SPEC-0007/FR-NEW-016 list, SPEC-0016 final list)
> The agent interface SHALL offer twenty three operations: the twenty two listed today and `breathe_inline`.
- **Before:** twenty two operations. **After:** twenty three. **Reason:** this spec.

## 7. Non functional requirements
Not applicable: same cost as the command.

## 8. Edge cases
| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty | deck with no decoration class and no named picture | the line reports 0 classes and 0 pictures, file unchanged in content | E2E-006 |
| Repetition | the same call twice | second call leaves the file unchanged | E2E-005 |
| Bad input | missing file, template file, no block | the messages of FR-NEW-003, file untouched | E2E-003, E2E-004 |
| Concurrency, connectivity, access, navigation, exhaustion | not applicable | | |

## 9. Acceptance tests
### 9.1 Summary
| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | happy | SC-001 | FR-NEW-001 | Critical |
| E2E-002 | New | happy | SC-002 | FR-NEW-002 | High |
| E2E-003 | New | failure | SC-001 | FR-NEW-003 | High |
| E2E-004 | New | failure | SC-001 | FR-NEW-003 | High |
| E2E-005 | New | edge | SC-001 | FR-NEW-004 | Medium |
| E2E-006 | New | edge | SC-001 | FR-NEW-001 | Medium |
| E2E-007 | New | failure | SC-001 | FR-NEW-003 | Medium |
| E2E-008 | Modified | side effect | | FR-NEW-005, FR-MOD-001 | High |
Coverage: happy 2, failure 3, edge 2, side effect 1. Happy to failure ratio 1:1.5.

### 9.2 New tests
#### E2E-001: embed returns the command's line and writes the same file
- **Given** `talk.html`, a Breathe deck with 3 decoration classes and 2 named pictures, and `talk-cmd.html`, a copy of it
- **When** the agent asks to embed the assets of `talk.html` and the command `breathe-inline talk-cmd.html` is run on the copy
- **Then** the agent receives the line `talk.html: 3 background and icon classes, 2 pictures embedded, <N> KB` (the command prints the same line with the file name it was given, `talk-cmd.html`), and `talk.html` is byte identical to `talk-cmd.html`
#### E2E-002: linked form
- **Given** the same deck
- **When** the agent asks for the linked form
- **Then** the received line reads `talk.html: 3 background and icon classes, 2 pictures linked, <K> files copied to <folder>/assets, <N> KB`, the folder `assets` next to the deck holds the copied files, and the deck is byte identical to the one `breathe-inline --link` writes
#### E2E-003: file not found
- **Given** no file `absent.html`
- **When** the agent asks to embed `absent.html`
- **Then** the agent receives the error `File not found: absent.html` and no file is created
#### E2E-004: a template file is refused
- **Given** the Breathe template shipped with the editor
- **When** the agent asks to embed it
- **Then** the agent receives `Refusing to modify a template: <that file>` and the template is unchanged
#### E2E-005: repeated call
- **Given** `talk.html` already embedded by one call
- **When** the agent repeats the call
- **Then** the file is byte identical to after the first call and the line reports the same counts
#### E2E-006: nothing to embed
- **Given** a Breathe deck with its decoration block and no decoration class, no named picture
- **When** the agent asks to embed
- **Then** the received line reads `deck.html: 0 background and icon classes, 0 pictures embedded, <N> KB`
#### E2E-007: no decoration block
- **Given** a presentation without the `breathe:assets` block in its style
- **When** the agent asks to embed
- **Then** the agent receives `deck.html has no breathe:assets block in its <style>` and the file is unchanged

### 9.3 Modified tests
#### E2E-008: the list of agent operations (was the test naming the twenty two operations)
- **Validated before:** the interface offers exactly twenty two operations and the skill lists them
- **Validates now:** twenty three operations, `breathe_inline` among them with a line in the skill, and the skill audit reports no problem
- **Given** the editor installed **When** the operations and the skill are read **Then** twenty three names agree between the interface and the skill, and `skill-audit` exits 0

## 10. Traceability
| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 003, 004 | E2E-001 | E2E-003, 004, 007 | E2E-005, 006 |
| SC-002 | FR-NEW-002 | E2E-002 | E2E-003 | E2E-005 |
| none | FR-NEW-005, FR-MOD-001 | E2E-008 | | |

## 11. Open questions
None.

## 12. Glossary
| Term | Definition | Context |
|---|---|---|
| Breathe deck | a presentation of the Breathe charter | SPEC-0023 |
| decoration | background and icon classes of the Breathe catalogue | SPEC-0023 |
| linked form | the decoration and pictures kept as files in `assets` next to the deck | SPEC-0023 |
| agent interface | the operations an LLM agent calls | SPEC-0007 |

## 13. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 0 | 0 | IMPLEMENTABLE |

**Amendments applied:** none. **No implementation detail outside Section 14:** PASS (command and operation names are product vocabulary of the agent interface).

## 14. Evidence appendix
### 14.1 Current State evidence
| Claim (Section 2) | Evidence |
|---|---|
| the command exists with `--link` and prints one summary line | `src/mcp_htmleditor/cli.py:595-602`, `src/mcp_htmleditor/breathe/inline.py:54-61` |
| errors are single DeckError lines | `src/mcp_htmleditor/breathe/inline.py:95-105,151,162,179`, `src/mcp_htmleditor/cli.py:34-47` |
| twenty two operations asserted by a test | `tests/test_deck_tools_surface.py:204-211` |
| the skill lists the tools | `skill/core.md` `## Tools` (`rg -n "^- (render|export):" skill/core.md`) |
Test command: `make check`.
### 14.3 Design inputs
- Every agent operation maps `DeckError` to `ToolError` (`mcp_server.py:340-344`); the new one follows. Counts "22" sit in `AGENTS.md:167`, `README.md:766`, `mcp_server.py:3`, `.agent_docs/architecture.md` and `tests/test_deck_tools_surface.py`.
