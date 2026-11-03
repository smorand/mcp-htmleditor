# Human to agent request loop and AI review: functional specification

> Id: SPEC-0010
> Nature: FEAT
> Depth: M
> Depth evidence: 3 areas (editor panel, agent tools, stored requests), one new persisted concept (request), about 9 requirements
> Status: specified
> Generated on: 2026-11-03
> Project: existing
> From backlog: n/a
> Depends on: SPEC-0009 (state directory), SPEC-0007 (slide ids)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary

A person editing in the browser can only ask the agent for a change by writing to it in the conversation, and
the agent cannot see which slide the person was looking at nor tell the person that a change is done or
refused. This increment adds a request queue shared by the editor and the agent, and a short AI review list
that the person can turn into requests with one click.

## 2. Current State

### 2.1 What users can do today

- The editor has no way to send an instruction to the agent. The person types it in the agent's conversation.
- The agent tool surface has no tool that lists or completes requests, and no review list.
- The editor shows no per slide task list and no status of work asked of the agent.
- The state directory and the per file state of SPEC-0009 are the place where per file data now lives.

### 2.2 Specs governing this area

- SPEC-0009 FR-NEW-008: no file is created next to the user's file; requests and reviews follow that rule.
- SPEC-0007: slide ids used in `slide`.
- SPEC-0006: the skill topic `create` describes the workflow "apply the requests" (no new topic).
- SPEC-0001 FR-009 is contradicted again (more tools); the count is recorded in SPEC-0007.

### 2.3 What is verified today

Editor tests exist for autosave, undo, fullscreen and origin checks. Nothing covers requests or reviews.

## 3. Scope

### 3.1 In scope

The `Ask AI` panel; the requests side list; the AI suggestions list; the tools and commands to list and
complete requests and to write and read the review.

### 3.2 Out of scope, and why

- Starting the agent from the editor: the agent stays in charge of when it runs.
- Anchoring a request to a text selection or an element: the request carries the current slide only.
- Notifications outside the editor.
- Requests that target something other than the current slide.

### 3.3 Constraints imposed by the context

- No file is created next to the user's file (SPEC-0009).
- Standard output of the tool protocol process carries protocol messages only.

## 4. Actors

| Actor | Description |
|---|---|
| Editor user | A person editing in the browser |
| Agent | A language model that applies requests |

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Requests | instructions from the person to the agent and their outcome | request, status, reason |
| Review | the agent's suggestions | suggestion, applied |

## 5. Usage scenarios

### SC-001: Asking for a change
**Actor:** Editor user
**Flow:**
1. The user clicks `Ask AI`, types a description, clicks `Queue request` → the panel says `Request R-0001 queued` and the list `Requests (1)` shows it as `pending`.
**Exceptions:**
- EXC-001a: empty text → `Write a request first`. EXC-001b: more than 4 000 characters → `Request too long (max 4000 characters)`. EXC-001c: 50 pending already → `Too many pending requests (max 50)`. EXC-001d: the request cannot be stored → `Could not queue the request: <error>`.

### SC-002: Applying requests
**Actor:** Agent
**Flow:**
1. The agent calls `list_requests` → it receives the requests, oldest first.
2. It makes the change, then calls `complete_request` with `done`, or with `skipped` and a reason → the editor shows the status at its next refresh.
**Exceptions:**
- EXC-002a: unknown id; EXC-002b: skipped without reason; EXC-002c: status invalid; EXC-002d: already completed; EXC-002e: file not found.

### SC-003: Reviewing
**Actor:** Agent, then Editor user
**Flow:**
1. The agent calls `write_review` with up to 6 suggestions → the editor shows `AI suggestions (n)`.
2. The user clicks `Apply` on one → a pending request is created from it and the suggestion shows `Applied`.
**Exceptions:**
- EXC-003a: more than 6, bad title length, missing field; EXC-003b: applied twice.

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-E]: Queue a request
> WHEN the user clicks `Queue request` in the `Ask AI` panel THE Editor SHALL store a pending request and confirm it.

- **Business rules:** the panel opens with the button `Ask AI`; it has the field labelled `Describe the change`, the line `Slide: <id>` (`Slide: none` for a file that is not a presentation) and the button `Queue request`. The instruction is stored exactly as typed (accents and line breaks kept). Ids are `R-0001`, `R-0002`, ... per file, never reused, even after `Delete`. A request has `id`, `slide` (id or null), `title` (the instruction with line breaks replaced by spaces, cut to its first 60 characters), `queued` (UTC `YYYY-MM-DDTHH:MM:SSZ`), `instruction`, `status` (`pending`), `reason` (null). The limit is 4 000 characters inclusive and 50 pending requests. Only requests with status `pending` count toward the limit of 50; `done` and `skipped` requests do not. `Requests (n)` counts the same requests, while the list shows all non deleted requests. Each line break (`\r\n`, `\n` or `\r`) in the title is replaced by exactly one space and the title is not trimmed. A character is a Unicode code point, for the 4 000 limit, the 60 title cut and the 60 suggestion title limit. Checks run in this order: empty (the text is empty once all Unicode whitespace is removed; the stored text is not trimmed), too long, too many pending, storage. Ids are `R-` followed by the counter on at least 4 digits (`R-10000` after `R-9999`). `queued` is the UTC time at the moment of storage. The current slide is the slide holding the caret or the last click in the editor, else the first slide; for a file with no slides the panel shows `Slide: none` and the request has `slide` null; the list line shows the `slide` value or `-`. Each operation (queue, delete, apply, complete, write review) is atomic across the editor and the tool processes: no request is lost, no id is given twice, and when two operations conflict the later one sees the earlier one's result. Requests and the review belong to the absolute path of the file with symlinks resolved; a renamed or moved file starts with none, and removing the state directory removes them.
- **User visible text:** `Request R-0001 queued`; `Write a request first`; `Request too long (max 4000 characters)`; `Too many pending requests (max 50)`; `Could not queue the request: <error>`.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: List requests
> WHEN an agent calls `list_requests` or a user runs `mcp-htmleditor requests <file>` THE Editor SHALL list the requests of that file, oldest first.

- **Business rules:** the tool returns `{"file":<absolute path>,"requests":[{"id","slide","title","queued","instruction","status","reason"}]}` with all requests of all statuses that were not deleted. The command prints one line per request, `<id>  <status>  <slide or ->  <title>` (two spaces between columns), or `No requests for <file>`.
- **User visible text:** `error: File not found: <file>` (tool: error with that message without the prefix), exit status 1.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-003 [EARS-E]: Complete a request
> WHEN an agent calls `complete_request` or a user runs `mcp-htmleditor request-done <file> <id>` or `request-skip <file> <id> --reason <text>` THE Editor SHALL set the request's status to `done` or `skipped`.

- **Business rules:** tool `complete_request(file, id, status, reason=None)`, `status` is `done` or `skipped`, and `reason` is required for `skipped`; the tool answers `{"ok":true,"id","status"}`; the command prints `Request R-0001 marked done` or `Request R-0001 marked skipped`. Checks in this order: file, id, status, reason, already completed. A reason that is empty once Unicode whitespace is removed counts as absent; a valid reason is stored exactly as given, untrimmed, with no length limit; `request-skip` without `--reason` gives the same error as an empty reason; a reason given with `done` is ignored and stored as null.
- **User visible text:** `error: Unknown request id "R-9". Valid ids: R-0001, R-0002` (`Valid ids: none` when empty); `error: Status must be done or skipped`; `error: A reason is required to skip a request`; `error: Request R-0001 is already done` (or `skipped`).
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-004 [EARS-U]: Same results on both surfaces
> The Editor SHALL give the same results for requests and review through the command line and the agent tool surface, the tool returning an error whose message is the command line error line without its `error: ` prefix.

- **Business rules:** command line errors are one line on the error output, exit status 1, empty standard output.
- **Scenario:** SC-002, SC-003
- **Priority:** Must

#### FR-NEW-005 [EARS-S]: Requests list in the editor
> WHILE the editor is open on a file THE Editor SHALL show the side list `Requests (n)`, with n the number of pending requests, each request as `<id> <status> <slide> <title>` with a `Delete` button, refreshed within two poll intervals of a change made by the agent.

- **Business rules:** a skipped request line reads `<id> <status> <slide> <title> <reason>`, with one space before the reason. Deleting an id that does not exist is a no-op and the list is refreshed; a storage failure on `Delete` shows `Could not delete the request: <error>` and keeps the request. `Delete` is offered on every request whatever its status, with no confirmation; it removes the request for good, the id stays used, and it frees a slot if the request was pending.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

#### FR-NEW-006 [EARS-E]: Write the review
> WHEN an agent calls `write_review` with suggestions or a user runs `mcp-htmleditor review <file> --write <suggestions.json | ->` THE Editor SHALL replace the review of that file by those suggestions.

- **Business rules:** checks run in this order: file, count, then suggestions in position order; within one suggestion: missing field (in the order id, slide, title, why, change), title length, duplicate id; `slide` is a required key but may be null. Applied state belongs to the review: each written review starts with no suggestion applied, even when ids repeat a previous review. At most 6 suggestions; each is `{"id","slide","title","why","change"}` with `id` a non empty string unique in the list, `slide` a slide id or null, `title` at most 60 characters, `why` and `change` non empty strings. The tool answers `{"ok":true,"count":<n>}`; the command prints `Review written: <n> suggestions`. A new review replaces the previous one; requests created by `Apply` remain. `mcp-htmleditor review <file>` prints one line per suggestion, `<id>  <slide or ->  <title>`, or `No review for <file>`. The editor shows `AI suggestions (n)` with, for each, the title, the `why` text and a button `Apply` (`Applied` once applied).
- **User visible text:** `error: At most 6 suggestions`; `error: Suggestion 2: title is longer than 60 characters`; `error: Suggestion 3: missing field "change"`; `error: Suggestion 2: duplicate id "s1"`. The number is the 1 based position of the first faulty suggestion. A field that is absent, null (except `slide`), not a string, or empty or only whitespace counts as missing; `slide` must be null or a string, otherwise it counts as missing; `slide` is not checked against existing slides; unknown extra keys are ignored and not stored. Other errors: `error: Review must be a list of suggestions`; `error: Cannot read <path>: <reason>`; `error: Invalid JSON: <reason>`; `error: Could not write the review: <error>` (the previous review stays unchanged).
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-007 [EARS-E]: Apply a suggestion
> WHEN the user clicks `Apply` on a suggestion THE Editor SHALL create a pending request from it and mark the suggestion applied.

- **Business rules:** the request takes the suggestion's `slide` as is, even if that slide no longer exists; on any refusal (too long, too many pending, storage) the suggestion stays not applied and the panel shows the message of FR-NEW-001; the applied mark is stored together with the request. The instruction is `<title>. <change>`, the slide is the suggestion's slide, the confirmation is `Request <id> queued` with the id of the created request. Checks for Apply run in this order: suggestion exists, not already applied, then the checks of FR-NEW-001; an unknown suggestion gives `Suggestion <id> no longer exists` and creates nothing. Limits of FR-NEW-001 apply to the created request except the 4 000 characters check, which is applied to the built instruction.
- **User visible text:** `Suggestion s1 was already applied`.
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-008 [EARS-UB]: No file next to the user's file
> The Editor SHALL NOT create any file or folder next to the user's file for requests or the review, and SHALL NOT mix requests of different files.

- **Scenario:** SC-001, SC-002
- **Priority:** Must

## 7. Non functional requirements (user observable)

No requirement added. A request is stored before the confirmation is shown.

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Boundary values | 4 000 and 4 001 characters; 50th and 51st pending | accepted; refused | E2E-009, 010, 026 |
| Data variations | accents, line break | kept exactly | E2E-022 |
| Idempotency | id reuse after `Delete` | never reused | E2E-021 |
| Concurrent actions | agent completes a request the user just deleted | unknown id | E2E-025 |
| Partial operations | storage fails | message, nothing created | E2E-020 |
| Replacement | new review | replaces, applied requests stay | E2E-024 |
| Isolation | two files | separate lists | E2E-023 |

## 9. Acceptance tests (the contract)

### 9.0 Fixtures

DECK: an Euro-Information presentation `deck.html` of 8 slides open in the editor. DECK2: another presentation.

### 9.1 Summary

| Test | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|
| E2E-001 | journey | SC-001 | FR-NEW-001, 005 | Critical |
| E2E-002 | journey | SC-002 | FR-NEW-002 | Critical |
| E2E-003 | journey | SC-002 | FR-NEW-003, 005 | Critical |
| E2E-004 | journey | SC-002 | FR-NEW-003, 005 | High |
| E2E-005 | journey | SC-002 | FR-NEW-002, 003, 004 | High |
| E2E-006 | journey | SC-003 | FR-NEW-006 | High |
| E2E-007 | journey | SC-003 | FR-NEW-007 | High |
| E2E-008 | failure | SC-001 | FR-NEW-001 | High |
| E2E-009 | failure | SC-001 | FR-NEW-001 | High |
| E2E-010 | failure | SC-001 | FR-NEW-001 | High |
| E2E-011 | failure | SC-002 | FR-NEW-003, 004 | High |
| E2E-012 | failure | SC-002 | FR-NEW-003, 004 | High |
| E2E-013 | failure | SC-002 | FR-NEW-003 | Medium |
| E2E-014 | failure | SC-002 | FR-NEW-003 | Medium |
| E2E-015 | failure | SC-003 | FR-NEW-006, 004 | High |
| E2E-016 | failure | SC-003 | FR-NEW-006, 004 | Medium |
| E2E-017 | failure | SC-003 | FR-NEW-006, 004 | Medium |
| E2E-018 | failure | SC-002 | FR-NEW-002, 004 | High |
| E2E-019 | failure | SC-003 | FR-NEW-007 | High |
| E2E-020 | failure | SC-001 | FR-NEW-001, 008 | High |
| E2E-021 | edge | SC-001 | FR-NEW-001, 005 | Medium |
| E2E-022 | edge | SC-001 | FR-NEW-001 | Medium |
| E2E-023 | edge | SC-002 | FR-NEW-008, 002 | High |
| E2E-024 | edge | SC-003 | FR-NEW-006, 007 | Medium |
| E2E-025 | edge | SC-002 | FR-NEW-003, 005 | Medium |
| E2E-026 | edge | SC-001 | FR-NEW-001 | Medium |
| E2E-027 | side effect | SC-002 | FR-NEW-005 | High |
| E2E-028 | side effect | SC-001 | FR-NEW-008 | High |

Coverage: happy 7, failure 13, edge 6, side effect 2 (28 tests). Happy to failure ratio 1:1.9 (beats 1:1).

### 9.2 New tests

#### E2E-001: Queue a request
- **Given** DECK open on `slide-3`
- **When** the user clicks `Ask AI`, types `Shorten the title` in `Describe the change`, clicks `Queue request`
- **Then** the panel shows `Slide: slide-3` before and `Request R-0001 queued` after; the side list reads `Requests (1)` and holds `R-0001 pending slide-3 Shorten the title`
- **Priority:** Critical

#### E2E-002: List requests
- **Given** the request of E2E-001
- **When** the agent calls `list_requests` with `file` DECK
- **Then** it receives `{"file":"<absolute DECK path>","requests":[{"id":"R-0001","slide":"slide-3","title":"Shorten the title","queued":"<UTC time>","instruction":"Shorten the title","status":"pending","reason":null}]}`
- **Priority:** Critical

#### E2E-003: Complete as done
- **Given** the request of E2E-001
- **When** the agent calls `complete_request` with `id` `R-0001`, `status` `done`
- **Then** it receives `{"ok":true,"id":"R-0001","status":"done"}`
- **And** within two poll intervals the editor shows `R-0001 done slide-3 Shorten the title` and `Requests (0)`
- **Priority:** Critical

#### E2E-004: Complete as skipped
- **Given** the request of E2E-001
- **When** the agent calls `complete_request` with `status` `skipped` and `reason` `Title is already short`
- **Then** the editor shows `R-0001 skipped slide-3 Shorten the title` followed by `Title is already short`
- **Priority:** High

#### E2E-005: Command line parity
- **Given** DECK with request R-0001 pending
- **When** the user runs `mcp-htmleditor requests deck.html`, then `request-skip deck.html R-0001 --reason "Not needed"`, then `requests deck.html`
- **Then** the outputs are `R-0001  pending  slide-3  Shorten the title`, `Request R-0001 marked skipped`, `R-0001  skipped  slide-3  Shorten the title`
- **And** `request-done deck.html R-0002` after queuing a second request prints `Request R-0002 marked done`
- **Priority:** High

#### E2E-006: Write and show a review
- **Given** DECK open
- **When** the agent calls `write_review` with 2 valid suggestions (ids `s1`, `s2`)
- **Then** it receives `{"ok":true,"count":2}` and the editor shows `AI suggestions (2)` with their titles, `why` texts and a button `Apply` each
- **And** `mcp-htmleditor review deck.html` prints `s1  slide-2  <title>` and `s2  -  <title>`
- **Priority:** High

#### E2E-007: Apply a suggestion
- **Given** the review of E2E-006, `s1` having title `Tighten the agenda`, change `Cut to 5 lines`, slide `slide-1`
- **When** the user clicks `Apply` on `s1`
- **Then** the panel shows `Request R-0001 queued`, the side list holds a pending request for `slide-1` and `list_requests` returns its instruction `Tighten the agenda. Cut to 5 lines`
- **And** the suggestion shows `Applied`
- **Priority:** High

#### E2E-008: Empty request
- **Given** DECK open
- **When** the user clicks `Queue request` with nothing typed, or with only spaces
- **Then** the panel shows `Write a request first` and `list_requests` returns no request
- **Priority:** High

#### E2E-009: Too long
- **Given** DECK open
- **When** the user queues a request of 4 001 characters
- **Then** the panel shows `Request too long (max 4000 characters)` and nothing is stored
- **Priority:** High

#### E2E-010: Too many pending
- **Given** DECK with 50 pending requests
- **When** the user queues one more
- **Then** the panel shows `Too many pending requests (max 50)` and the list still has 50
- **Priority:** High

#### E2E-011: Unknown id
- **Given** DECK with R-0001 and R-0002
- **When** the user runs `mcp-htmleditor request-done deck.html R-9`
- **Then** the error output is `error: Unknown request id "R-9". Valid ids: R-0001, R-0002`, exit status 1, empty standard output
- **Priority:** High

#### E2E-012: Skip without reason
- **Given** the request R-0001 pending
- **When** the agent calls `complete_request` with `status` `skipped` and no `reason`, and the user runs `request-skip deck.html R-0001 --reason ""`
- **Then** both fail with `A reason is required to skip a request` and the request is still pending
- **Priority:** High

#### E2E-013: Invalid status
- **Given** R-0001 pending
- **When** the agent calls `complete_request` with `status` `finished`
- **Then** the error message is `Status must be done or skipped`
- **Priority:** Medium

#### E2E-014: Already completed
- **Given** R-0001 marked done
- **When** the agent completes it again, as `skipped` with a reason
- **Then** the error is `Request R-0001 is already done` and the status is still `done`
- **Priority:** Medium

#### E2E-015: Too many suggestions
- **Given** DECK
- **When** the agent calls `write_review` with 7 valid suggestions
- **Then** the error is `At most 6 suggestions` and the previous review is unchanged
- **Priority:** High

#### E2E-016: Title too long
- **Given** DECK
- **When** the agent writes a review whose second suggestion has a title of 61 characters
- **Then** the error is `Suggestion 2: title is longer than 60 characters` and nothing changes
- **Priority:** Medium

#### E2E-017: Missing field and duplicate id
- **Given** DECK
- **When** the agent writes a review whose third suggestion has no `change`, and another whose second suggestion repeats the id `s1`
- **Then** the errors are `Suggestion 3: missing field "change"` and `Suggestion 2: duplicate id "s1"`
- **And** the same writes through `mcp-htmleditor review deck.html --write <file>` print `error: ` followed by the same text, exit status 1
- **Priority:** Medium

#### E2E-018: File not found
- **Given** no file `ghost.html`
- **When** the user runs `requests ghost.html`, and the agent calls `list_requests`, `complete_request`, `write_review` for it
- **Then** each fails with `File not found: ghost.html` (command line: `error: File not found: ghost.html`, exit status 1)
- **Priority:** High

#### E2E-019: Apply twice
- **Given** the review of E2E-007 with `s1` applied
- **When** the user clicks `Apply` on `s1` again (button shown as `Applied`) or the apply is sent a second time
- **Then** the editor shows `Suggestion s1 was already applied` and no second request is created
- **Priority:** High

#### E2E-020: Storage failure
- **Given** DECK open and the place where requests are stored made unwritable
- **When** the user queues a request
- **Then** the panel shows `Could not queue the request: ` followed by the error text, and no request exists
- **Priority:** High

#### E2E-021: Ids never reused
- **Given** R-0001 and R-0002 queued, then R-0002 deleted with `Delete`
- **When** the user queues a new request
- **Then** its id is `R-0003`
- **Priority:** Medium

#### E2E-022: Accents and line breaks
- **Given** DECK open
- **When** the user queues the instruction `Mettre « Résumé » en gras` + line break + `puis centrer` and the agent lists requests
- **Then** `instruction` equals that text exactly, and `title` is `Mettre « Résumé » en gras puis centrer`
- **Priority:** Medium

#### E2E-023: Two files
- **Given** a request queued on DECK and none on DECK2
- **When** the agent calls `list_requests` for DECK2, then for DECK
- **Then** DECK2 returns an empty `requests` and DECK returns one request
- **And** `mcp-htmleditor requests deck2.html` prints `No requests for deck2.html`
- **Priority:** High

#### E2E-024: New review
- **Given** a review with `s1` applied (request R-0001 exists)
- **When** the agent writes a new review with one suggestion `n1`
- **Then** the editor shows `AI suggestions (1)` with `n1` only, and R-0001 is still in the list
- **Priority:** Medium

#### E2E-025: Completion after deletion
- **Given** R-0001 pending, then deleted by the user
- **When** the agent calls `complete_request` for `R-0001`
- **Then** the error is `Unknown request id "R-0001". Valid ids: none`
- **Priority:** Medium

#### E2E-026: Boundary sizes
- **Given** DECK with 49 pending requests
- **When** the user queues a request of exactly 4 000 characters, then another of 4 000 characters
- **Then** the first is accepted (`Request R-0050 queued`, the existing ids being R-0001 to R-0049) and the second is refused with `Too many pending requests (max 50)`
- **Priority:** Medium

#### E2E-027: Editor refresh
- **Given** DECK open with R-0001 pending
- **When** the agent completes it as `done` and nothing else touches the editor
- **Then** within two poll intervals the side list shows it as `done` without a manual reload
- **Priority:** High

#### E2E-028: No file next to the file
- **Given** an empty folder with DECK, the editor open
- **When** the user queues a request and the agent writes a review
- **Then** the folder holds only DECK
- **Priority:** High

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 005, 008 | E2E-001 | E2E-008, 009, 010, 020 | E2E-021, 022, 026 |
| SC-002 | FR-NEW-002, 003, 004, 005, 008 | E2E-002, 003, 004, 005 | E2E-011, 012, 013, 014, 018 | E2E-023, 025 |
| SC-003 | FR-NEW-006, 007 | E2E-006, 007 | E2E-015, 016, 017, 019 | E2E-024 |

Requirements to tests: FR-NEW-001 (001, 008, 009, 010, 020, 021, 022, 026); 002 (002, 005, 018, 023); 003 (003, 004, 005, 011, 012, 013, 014, 025); 004 (005, 011, 012, 015, 016, 017, 018); 005 (001, 003, 004, 021, 025, 027); 006 (006, 015, 016, 017, 024); 007 (007, 019, 024); 008 (020, 023, 028).

## 11. Open questions

None.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Request | An instruction from the person to the agent, with id, slide, status and reason | Requests |
| Pending | A request not yet completed | Requests |
| Suggestion | One item of the AI review | Review |
| Applied | A suggestion already turned into a request | Review |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 11 | 0 | NOT-IMPLEMENTABLE |
| 2 | 7 | 3 | NOT-IMPLEMENTABLE (amended after; cap of two rounds reached) |

**Amendments applied:** all F findings of rounds 1 and 2. **Concern (user waiver, 2026-11-03):** the two round cap was reached with F findings amended but not re audited.
**No implementation detail outside Section 14:** PASS

## 14. Evidence appendix

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| tool surface has no request or review tool | `src/mcp_htmleditor/mcp_server.py:30-31,80-81,92-93,111-112,132-133,149-150,165-166` (decorator and function lines) |
| editor toolbar and side panels | `src/mcp_htmleditor/static/editor.js`, `src/mcp_htmleditor/static/editor.html` |
| polling interval used for refresh | `src/mcp_htmleditor/static/editor.js:298-330` |

Test command: `make test`; gate `make check`.

### 14.3 Design inputs

- The editor needs new save style endpoints for queueing, deleting, applying and listing; they must keep the origin and JSON only rules of SPEC-0005. Detection signal: E2E-001, E2E-007.
- Requests and review live in the SPEC-0009 state directory, keyed by the file; the editor and the tool processes share them. Detection signal: E2E-023, E2E-028.
- The side list refresh uses the existing poll; the status must expose a change marker for requests or the editor must fetch the list on each poll. Detection signal: E2E-027.
- Documents to update: `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, skill topic `create` (SPEC-0006) with the "apply the requests" workflow.
