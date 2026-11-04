# Reliable saves and agent/browser coordination: functional specification

> Id: SPEC-0009
> Nature: FEAT
> Depth: M
> Depth evidence: 3 areas (save path, history, update flag and status), one new persisted concept (history), about 10 requirements
> Status: implemented
> Generated on: 2026-11-03
> Project: existing
> From backlog: n/a (resolves the intent of BL-0013, BL-0016; answers BL-0006 on template saves)
> Depends on: SPEC-0007 (patch writes the file)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary

A person editing in the browser and an agent editing the same file can overwrite each other, a crash during a
save can leave a half written file, a crashed agent can leave the editor locked behind its "update in
progress" screen, and nothing keeps a previous version. This increment makes saves safe, detects conflicts,
keeps a short history with a restore command, makes the update flag expire, and makes server failures visible.

## 2. Current State

### 2.1 What users can do today

- The browser saves by sending the whole document; the server writes it straight onto the file, so a failure in the middle can leave a truncated file.
- The browser polls the server every second for the file's modification time and reloads when it changed,
  unless it holds unsaved edits; in that case the next autosave overwrites the agent's changes without a word.
- `update_start` sets a flag that never expires; if the agent stops before `update_end`, the editor stays
  locked.
- A save aimed at a path under `templates/bootstrap` or `templates/reference` is answered `ok` and ignored.
- A request body with an invalid length header raises an unhandled error; there is no size limit.
- A failed poll is swallowed silently.
- The state is written to `.mcp_state.json` next to the user's HTML file.
- There is no history and no way to go back to a previous version.

### 2.2 Specs governing this area

- SPEC-0001, SPEC-0002 (browser editing, autosave), SPEC-0004 (autosave on focus loss), SPEC-0005 (origin and
  JSON only saves): this increment keeps all their observable behavior except the points above.
- BL-0006 (legacy FR-007: a save to a template should be refused with a non success status): answered here.
- SPEC-0001 FR-009 is contradicted again (more tools); the count is recorded in SPEC-0007.

### 2.3 What is verified today

Autosave, undo, origin checks and JSON only saves have tests (`tests/test_autosave_e2e.py`,
`tests/test_origin_e2e.py`). Nothing covers conflicts, atomicity, history, flag expiry or oversize bodies.

## 3. Scope

### 3.1 In scope

Atomic writes; conflict detection with a visible choice; history with `history` and `restore`; flag expiry;
explicit refusals; state outside the user's folder; a visible banner on server loss.

### 3.2 Out of scope, and why

- Authentication when the server listens beyond the local machine: BL-0019, its own decision.
- Merging two versions: the choice is reload or keep.
- Reformatting avoidance on browser saves: the browser sends a re-serialized document and that is unchanged.
- History for edits made by writing the file directly: only writes through the product are captured.

### 3.3 Constraints imposed by the context

- Existing clients that send a save without the new field keep working (no conflict check for them).
- The standard output of the tool protocol process carries protocol messages only.

## 4. Actors

| Actor | Description |
|---|---|
| Editor user | A person editing in the browser |
| Agent | A language model editing the file through the tools |

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Saving | how a version reaches the disk | save, conflict, atomic write |
| History | previous versions | snapshot, version id |
| Coordination | the update flag and server status | update flag, expiry, status |

## 5. Usage scenarios

### SC-001: A normal save
**Actor:** Editor user
**Flow:**
1. The user edits and the browser saves → the file on disk holds the new version and the previous version is kept in the history.
**Exceptions:**
- EXC-001a: the disk write fails → the old file is intact and an error is shown.

### SC-002: A conflicting save
**Actor:** Editor user
**Preconditions:** an agent wrote the file after the browser loaded it; the editor may or may not hold unsaved edits.
**Flow:**
1. The browser saves → the save is refused and the editor shows a message with `Reload` and `Keep mine`.
2. The user chooses `Reload` → the editor shows the agent's version; or `Keep mine` → the browser's version is written and the agent's version goes to the history.

### SC-003: Going back
**Actor:** Agent or user
**Flow:**
1. The actor runs `mcp-htmleditor history deck.html` → versions are listed, newest first.
2. The actor runs `mcp-htmleditor restore deck.html <id>` → the file holds that version; the version it replaced is in the history.
**Exceptions:**
- EXC-003a: unknown id; EXC-003b: file not found.

### SC-004: A stuck update
**Actor:** Agent
**Flow:**
1. The agent calls `update_start`, then stops without `update_end` → after 120 seconds the editor is released by itself.

### SC-005: Server lost
**Actor:** Editor user
**Flow:**
1. The server stops → after three failed polls the editor shows `Connection to the editor server lost`; when the server answers again the message disappears.

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-E]: Atomic save
> WHEN the editor server writes a file THE Editor SHALL leave on disk either the complete old content or the complete new content, and no other file next to it.

- **Business rules:** the permission bits of the replaced file are preserved, and a read only file in a writable folder is replaced normally. This holds for browser saves, `patch` (SPEC-0007) and `restore`. On a write failure the response is status 500 with `{"error":"<operating system message>"}`.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: Conflict detection
> WHEN the editor sends a save that carries `base_mtime` and the file's modification time differs from it THE Editor SHALL refuse the save and leave the file unchanged.

- **Business rules:** `base_mtime` is the `mtime` of the version of the file the page last loaded, or last wrote itself. A status poll showing a different `mtime` while the page holds unsaved edits does not change it. It changes only when the page loads or reloads the file, after the page's own successful save (the `mtime` of the save answer, not of a later poll), after `Reload`, and after a successful `Keep mine` (the `mtime` of that answer). The first save after a page load uses the `mtime` read at load. If the page read no `mtime`, it sends no `base_mtime`. The refusal is status 409 with `{"ok":false,"error":"File changed on disk","mtime":<current mtime>}`. A save with `"force": true` skips the check. A save without `base_mtime` is not checked. A successful save answers `{"ok":true,"mtime":<new mtime>}`.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-003 [EARS-E]: Conflict choice in the editor
> WHEN a save is refused for a conflict THE Editor SHALL show the message `The file changed on disk. Reload to see the changes, or keep your version.` with the buttons `Reload` and `Keep mine`.

- **Business rules:** `Reload` shows the file as it is on disk and drops the unsaved edits. `Keep mine` saves the browser's version with `force` true. No autosave is attempted while the message is shown.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-004 [EARS-E]: Snapshot before overwrite
> WHEN a browser save, a `patch` or a `restore` is about to change a file's bytes THE Editor SHALL first keep the previous content in the history.

- **Business rules:** nothing is kept when the new bytes equal the current bytes. At most the 20 newest versions of a file are kept. Identical content: when `base_mtime` is current the answer is `{"ok":true,"mtime":<unchanged mtime>}`, the file is not rewritten and no version is added; with a stale `base_mtime` the save is a 409 conflict whatever the content; equal bytes means the bytes the server would write after its HTML cleaning. A browser save carrying `force` true is recorded with reason `keep-mine`, whether or not a conflict existed; any other browser save is `browser-save`. A version is `{id, bytes, reason}` with `reason` one of `browser-save`, `keep-mine`, `patch`, `restore`. The id is the server's UTC time `YYYYMMDDTHHMMSS` followed by `Z`; when the id already exists for that file the suffix `-2`, `-3`, ... (decimal, no padding) is added. The version is kept only if the write then succeeds, so a failed write leaves the history unchanged. `bytes` is the UTF-8 byte count of the stored content. The cap of 20 is per absolute file path and drops the oldest by creation order. The history is stored in the state directory of FR-NEW-008, not next to the file.
- **Scenario:** SC-001, SC-002, SC-003
- **Priority:** Must

#### FR-NEW-005 [EARS-E]: History and restore
> WHEN a user runs `mcp-htmleditor history <file>` or `mcp-htmleditor restore <file> <id>` THE Editor SHALL list the versions or put the chosen version back.

- **Business rules:** the commands and tools resolve `<file>` to an absolute path (the current directory for the command line) and need no running server. Newest first means reverse order of creation. `history` prints one line per version, newest first: `<id>  <bytes> bytes  <reason>` (two spaces between columns), or `No history for <file>` with exit status 0. `restore` checks, in this order, template, file not found, unknown id (each an error); `history` on a template path is allowed and checks only that the file exists. `restore` keeps the current content in the history first (reason `restore`), writes the chosen content, and prints `Restored <file> to <id>`. `restore` to content equal to the current file changes nothing, adds no version, prints the same line and exits 0. `restore` skips the conflict check; an open browser sees the new `mtime` as an external change. `restore` on a template path fails with `error: Refusing to modify a template: <file>` (exit status 1). The tools `history(file)` and `restore(file, id)` return `{"file","versions":[{"id","bytes","reason"}]}` and `{"ok":true,"file","id"}`, `file` is the absolute path; a `restore` write failure prints `error: <operating system message>` (exit status 1), leaving file and history unchanged; the tools return, for an unknown id, a missing file, a template or a write failure, an error whose message is the command line line without its `error: ` prefix; `<file>` in messages is as typed.
- **User visible text:** `error: Unknown history id "x". Valid ids: 20261103T101500Z, 20261103T101200Z` (`Valid ids: none` when empty); `error: File not found: <file>` (exit status 1 each).
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-006 [EARS-E]: Update flag expiry
> WHEN 120 seconds have elapsed after `update_start` without another `update_start` or `update_end` THE Editor SHALL consider the update finished.

- **Business rules:** the flag is in progress while less than 120 seconds have elapsed since the last `update_start`; at exactly 120 seconds it is cleared. `update_expires_in` is the whole number `ceil(120 - elapsed)`, from 1 to 120. `update_end` after expiry answers `{"ok":true}` as before. `update_start` answers `{"ok":true,"expires_in":120}`. `get_status` and the editor status add `update_expires_in`, the remaining whole seconds rounded up while an update is in progress, otherwise null. After expiry `update_in_progress` is false in every answer. A second `update_start` restarts the 120 seconds. `update_end` clears the flag at once.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-007 [EARS-O]: Explicit refusals
> IF a save targets a template, has an invalid length, or is too large THEN THE Editor SHALL refuse it with a precise status and leave the file unchanged.

- **Business rules:** a path is a template if, with `\` read as `/`, it contains `/templates/bootstrap/` or `/templates/reference/`: status 403 `{"ok":false,"error":"Refusing to modify a template: <file>"}` where `<file>` is the absolute path as returned by the status `filename`. A valid `Content-Length` is a non empty string of ASCII digits only; anything else: status 400 `{"error":"Invalid Content-Length"}`. A body larger than 52 428 800 bytes: status 413 `{"error":"Request too large"}`, the body not read. A save with no `Content-Length` header is treated as length 0. These length and size checks apply to the save endpoint only. A `base_mtime` that is not a JSON number is treated as absent. A save request that fails at network level shows `Save failed: ` followed by the browser's error text and keeps the unsaved state. Checks run in this order and the first failure answers: host and origin (SPEC-0005, unchanged); invalid `Content-Length` (400); too large (413); content type other than `application/json` (415, SPEC-0005 unchanged); invalid JSON (400 `{"error":"Invalid JSON body"}`); template (403); conflict (409); write. When a save is answered with a non success status other than 409, the editor shows `Save failed: <error text of the answer>`, keeps the unsaved state, and tries again at the next autosave.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-008 [EARS-U]: State outside the user's folder
> The Editor SHALL NOT create any file next to the user's file for its own state, and SHALL share the state of a file between the processes working on that file.

- **Business rules:** the state (current file, port, pid, update flag with its expiry) is kept in the state directory, keyed by the file's absolute path. The state directory is `HTMLEDITOR_STATE_DIR` if set, else `$XDG_STATE_HOME/mcp-htmleditor`, else `~/.local/state/mcp-htmleditor`; with no home directory, `<system temporary directory>/mcp-htmleditor-<user id>`. A state directory that cannot be created makes a save answer 500 with the operating system message and leaves the file unchanged. The update flag and its expiry belong to a file: the status reports the flag of the file currently served; `open_file` leaves the previous file's flag as it was (it still expires by itself); `update_start` and `update_end` act on the file currently served. The state directory also holds one record naming the file most recently served or opened by any process; a process that has served no file itself uses that record's file for `update_start`, `update_end` and `get_status`, and a process that has served a file uses its own.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-009 [EARS-S]: Visible server loss
> WHILE three or more consecutive status polls have failed (a poll fails when the request fails, the answer status is not 200, or the body is not valid JSON) THE Editor SHALL show `Connection to the editor server lost`, and SHALL remove it at the next successful poll.

- **Scenario:** SC-005
- **Priority:** Must

## 7. Non functional requirements (user observable)

No other requirement: response times and logging are unchanged.

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Boundary values | 21st version | oldest dropped | E2E-022 |
| Boundary values | body of exactly 52 428 800 bytes and 52 428 801 | accepted, refused | E2E-011 |
| Empty states | history of a file never saved through the product | `No history for <file>` | E2E-016 |
| Idempotency | save with identical content | current base: ok, file not rewritten, no version; stale base: 409 | E2E-023 |
| Ordering and timing | flag renewal; flag expiry | restarts; clears at 120 s | E2E-020, 021 |
| Concurrent actions | agent write between browser load and save | conflict | E2E-007 |
| Partial operations | final replacement fails | old file intact, no temporary file | E2E-014 |
| Connectivity | one failed poll only | no banner | E2E-027 |
| Dependency failures | read only folder | error, old file intact | E2E-013 |

## 9. Acceptance tests (the contract)

### 9.0 Fixtures

DECK: an Euro-Information presentation `deck.html` of 8 slides, served by the editor. `mtime` is the value
returned by the status for DECK. "Saved copy" means the exact bytes before the step.

### 9.1 Summary

| Test | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|
| E2E-001 | journey | SC-001 | FR-NEW-001, 002 | Critical |
| E2E-002 | journey | SC-002 | FR-NEW-002 | High |
| E2E-003 | journey | SC-003 | FR-NEW-004, 005 | Critical |
| E2E-004 | journey | SC-003 | FR-NEW-005 | Critical |
| E2E-005 | journey | SC-004 | FR-NEW-006, 008 | High |
| E2E-006 | journey | SC-003 | FR-NEW-005 | High |
| E2E-007 | failure | SC-002 | FR-NEW-002 | Critical |
| E2E-008 | failure | SC-002 | FR-NEW-003 | Critical |
| E2E-009 | failure | SC-002 | FR-NEW-003, 004, 002 | High |
| E2E-010 | failure | SC-001 | FR-NEW-007 | High |
| E2E-011 | failure | SC-001 | FR-NEW-007 | High |
| E2E-012 | failure | SC-001 | FR-NEW-007 | High |
| E2E-013 | failure | SC-001 | FR-NEW-001 | Critical |
| E2E-014 | failure | SC-001 | FR-NEW-001 | Critical |
| E2E-015 | failure | SC-003 | FR-NEW-005 | High |
| E2E-016 | failure | SC-003 | FR-NEW-005 | Medium |
| E2E-017 | failure | SC-005 | FR-NEW-009 | High |
| E2E-018 | failure | SC-005 | FR-NEW-009 | High |
| E2E-019 | failure | SC-003 | FR-NEW-005 | Medium |
| E2E-020 | edge | SC-004 | FR-NEW-006 | High |
| E2E-021 | edge | SC-004 | FR-NEW-006 | Medium |
| E2E-022 | edge | SC-001 | FR-NEW-004 | Medium |
| E2E-023 | edge | SC-001 | FR-NEW-004, 002 | Medium |
| E2E-024 | edge | SC-004 | FR-NEW-008 | High |
| E2E-025 | edge | SC-004 | FR-NEW-008, 006 | Medium |
| E2E-026 | side effect | SC-003 | FR-NEW-004, 001 | High |
| E2E-027 | edge | SC-005 | FR-NEW-009 | Medium |
| E2E-028 | failure | SC-002 | FR-NEW-003, 001 | High |
| E2E-029 | failure | SC-001 | FR-NEW-007 | Medium |
| E2E-030 | failure | SC-001 | FR-NEW-007, 002 | Medium |
| E2E-031 | failure | SC-001 | FR-NEW-004, 001 | High |
| E2E-032 | failure | SC-001 | FR-NEW-001, 007 | High |

Coverage: happy 6, failure 18, edge 7, side effect 1 (32 tests). Happy to failure ratio 1:3 (beats 1:1).

### 9.2 New tests

#### E2E-001: A normal save
- **Given** DECK served, `mtime` read as M1
- **When** the browser sends a save with a changed title and `base_mtime` M1
- **Then** the answer is status 200 `{"ok":true,"mtime":M2}` with M2 greater than M1, and the file holds the new title
- **And** no other file exists in the folder of DECK
- **Priority:** Critical

#### E2E-002: Save after reload
- **Given** DECK served; the agent changes the file (mtime M2); the page reloads and reads M2
- **When** the browser saves with `base_mtime` M2
- **Then** the answer is `{"ok":true,"mtime":M3}`
- **Priority:** High

#### E2E-003: History after two saves
- **Given** DECK, two browser saves at different seconds
- **When** the user runs `mcp-htmleditor history deck.html`
- **Then** the output has two lines of the shape `<id>  <bytes> bytes  browser-save`, newest first, and the bytes of the older line equal the size of DECK before the first save
- **Priority:** Critical

#### E2E-004: Restore
- **Given** DECK saved twice (history ids A newest, B oldest), saved copy of the current file kept
- **When** the user runs `mcp-htmleditor restore deck.html B`
- **Then** the output is `Restored deck.html to B` and the file equals the content kept as version B
- **And** `history` now lists a first line with reason `restore` whose bytes equal the saved copy size
- **Priority:** Critical

#### E2E-005: Status with expiry
- **Given** DECK, `update_start` called at time T
- **When** `get_status` is called 30 seconds after T
- **Then** `update_in_progress` is true and `update_expires_in` is 90
- **And** `update_start` had answered `{"ok":true,"expires_in":120}`
- **Priority:** High

#### E2E-006: Tools history and restore
- **Given** DECK saved twice
- **When** an agent calls `history` with `file` DECK, then `restore` with the oldest id
- **Then** `history` returns `{"file":"<DECK>","versions":[...]}` with 2 versions each holding `id`, `bytes`, `reason`; `restore` returns `{"ok":true,"file":"<DECK>","id":"<id>"}`
- **Priority:** High

#### E2E-007: Conflict refused
- **Given** DECK served, `mtime` M1; the agent then writes a new version (mtime M2); saved copy of that file kept
- **When** the browser sends a save with `base_mtime` M1
- **Then** the answer is status 409 `{"ok":false,"error":"File changed on disk","mtime":M2}` and the file equals the saved copy
- **Priority:** Critical

#### E2E-008: Conflict message and Reload
- **Given** the editor open on DECK in a browser; the agent writes a new title; the user types an edit
- **When** the autosave fires
- **Then** the page shows `The file changed on disk. Reload to see the changes, or keep your version.` with the buttons `Reload` and `Keep mine`, and no further save is sent while it is shown
- **And** clicking `Reload` shows the agent's title and removes the message
- **Priority:** Critical

#### E2E-009: Keep mine
- **Given** the situation of E2E-008
- **When** the user clicks `Keep mine`
- **Then** the file holds the browser's version and the agent's version is in the history with reason `keep-mine`
- **And** the message disappears
- **Priority:** High

#### E2E-010: Template refused
- **Given** the editor serving a copy of a bootstrap template under `templates/bootstrap/x.html`
- **When** the browser sends a save
- **Then** the answer is status 403 `{"ok":false,"error":"Refusing to modify a template: <absolute path of x.html>"}` and the file is unchanged
- **Priority:** High

#### E2E-011: Too large
- **Given** DECK served
- **When** a request declares a length of 52 428 801 bytes, and another declares and sends 52 428 800 bytes of valid JSON
- **Then** the first is answered 413 `{"error":"Request too large"}` without reading the body, the file unchanged; the second is accepted
- **Priority:** High

#### E2E-012: Invalid length
- **Given** DECK served
- **When** a request is sent with `Content-Length: abc`, and another with `Content-Length: -5`
- **Then** both are answered 400 `{"error":"Invalid Content-Length"}` and the file is unchanged
- **Priority:** High

#### E2E-013: Read only folder
- **Given** DECK in a folder where new files cannot be created
- **When** the browser saves
- **Then** the answer is status 500 with an `error` text, the file equals the saved copy and no other file exists in the folder
- **Priority:** Critical

#### E2E-014: Failure at the last step
- **Given** DECK, and the final replacement of the file made to fail
- **When** the browser saves
- **Then** the answer is status 500, the file equals the saved copy, and the folder holds no leftover temporary file
- **Priority:** Critical

#### E2E-015: Unknown history id
- **Given** DECK saved twice (ids A newest and B oldest)
- **When** the user runs `restore deck.html nope`
- **Then** the error output is `error: Unknown history id "nope". Valid ids: A, B` (with the real ids), exit status 1, the file unchanged
- **Priority:** High

#### E2E-016: No history
- **Given** DECK never saved through the product
- **When** the user runs `history deck.html`
- **Then** the output is `No history for deck.html` and the exit status is 0
- **And** `restore deck.html x` prints `error: Unknown history id "x". Valid ids: none`
- **Priority:** Medium

#### E2E-017: Connection lost
- **Given** the editor open on DECK
- **When** the server stops and three consecutive polls fail
- **Then** the page shows `Connection to the editor server lost`
- **Priority:** High

#### E2E-018: Connection back
- **Given** the state of E2E-017
- **When** the server answers again
- **Then** the message disappears at the next successful poll
- **Priority:** High

#### E2E-019: Missing file for history
- **Given** no file `ghost.html`
- **When** the user runs `history ghost.html` and `restore ghost.html x`
- **Then** both print `error: File not found: ghost.html`, exit status 1
- **And** `restore templates/bootstrap/x.html y` prints `error: Refusing to modify a template: templates/bootstrap/x.html`, exit status 1
- **Priority:** Medium

#### E2E-020: Expiry
- **Given** `update_start` called at time T and nothing else
- **When** `get_status` is called at T + 121 seconds
- **Then** `update_in_progress` is false and `update_expires_in` is null
- **Priority:** High

#### E2E-021: Renewal
- **Given** `update_start` at T and again at T + 100 seconds
- **When** `get_status` is called at T + 150 seconds
- **Then** `update_in_progress` is true and `update_expires_in` is 70
- **And** after `update_end`, `get_status` shows false and null
- **Priority:** Medium

#### E2E-022: Twenty versions
- **Given** DECK saved 21 times with different content
- **When** the user runs `history deck.html`
- **Then** the output has exactly 20 lines and the first save's previous content is not among them
- **Priority:** Medium

#### E2E-023: Identical save
- **Given** DECK, a save of the file's exact current content with `base_mtime` current
- **When** the browser sends it
- **Then** the answer is `{"ok":true,"mtime":<mtime>}` and `history` lists no new version
- **Priority:** Medium

#### E2E-024: No state file next to the user's file
- **Given** an empty folder with DECK
- **When** the server starts on DECK and the agent calls `update_start`
- **Then** the folder holds only DECK
- **Priority:** High

#### E2E-025: State shared between processes
- **Given** a server process on DECK and `update_start` called through a separate tool process
- **When** `get_status` is called through the server process
- **Then** it reports `update_in_progress` true and an `update_expires_in` between 1 and 120
- **Priority:** Medium

#### E2E-026: Patch snapshots
- **Given** DECK and a `set_text` patch (SPEC-0007) changing a title
- **When** it is applied, then `history deck.html` is run
- **Then** the first line has reason `patch` and its bytes equal the size of DECK before the patch
- **Priority:** High

#### E2E-027: One failed poll
- **Given** the editor open on DECK
- **When** one poll fails then the next two succeed
- **Then** the message `Connection to the editor server lost` never appears
- **Priority:** Medium

#### E2E-028: Keep mine fails
- **Given** the conflict message shown (E2E-008) and the folder made read only (new files cannot be created)
- **When** the user clicks `Keep mine`
- **Then** the message stays and the page also shows `Save failed: ` followed by the error text of the answer, and the page is not marked saved
- **Priority:** High

#### E2E-029: Template with an oversize body
- **Given** the editor serving a copy of a bootstrap template under `templates/bootstrap/x.html`
- **When** a request declares a length of 52 428 801 bytes
- **Then** the answer is status 413 `{"error":"Request too large"}`
- **Priority:** Medium

#### E2E-030: Template with a stale base
- **Given** the template of E2E-029 and a save carrying a `base_mtime` different from the file's
- **When** the browser sends it
- **Then** the answer is status 403 (not 409) with the template message, file unchanged
- **Priority:** Medium

#### E2E-031: Failed write keeps the history unchanged
- **Given** DECK with 2 versions in the history and the write made to fail
- **When** the browser saves different content
- **Then** the answer is status 500 and `history deck.html` still lists exactly the same 2 versions
- **Priority:** High

#### E2E-032: Save failure shown in the editor
- **Given** the editor open on DECK and the folder made read only (new files cannot be created)
- **When** the autosave fires after an edit
- **Then** the page shows `Save failed: ` followed by the error text of the answer, stays in the unsaved state, and sends the save again at the next autosave once the file is writable again, after which the page is marked saved
- **Priority:** High

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 002, 004, 007 | E2E-001 | E2E-010 to 014, 029 to 032 | E2E-022, 023 |
| SC-002 | FR-NEW-002, 003, 004 | E2E-002 | E2E-007, 008, 009, 028 | none |
| SC-003 | FR-NEW-004, 005 | E2E-003, 004, 006 | E2E-015, 016, 019 | E2E-026 (side effect) |
| SC-004 | FR-NEW-006, 008 | E2E-005 | none | E2E-020, 021, 024, 025 |
| SC-005 | FR-NEW-009 | none | E2E-017, 018 | E2E-027 |

Requirements to tests: FR-NEW-001 (001, 013, 014, 026, 028, 031, 032); 002 (001, 002, 007, 009, 023, 030); 003 (008, 009, 028); 004 (003, 009, 022, 023, 026, 031); 005 (003, 004, 006, 015, 016, 019); 006 (005, 020, 021, 025); 007 (010, 011, 012, 029, 030, 032); 008 (005, 024, 025); 009 (017, 018, 027).

## 11. Open questions

None.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Conflict | A save whose `base_mtime` differs from the file's current modification time | Saving |
| Version | A kept previous content with id, size and reason | History |
| Update flag | The state that says an agent is changing the file | Coordination |
| Expiry | The 120 seconds after which the update flag clears itself | Coordination |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 12 | 5 | NOT-IMPLEMENTABLE |
| 2 | 8 | 3 | NOT-IMPLEMENTABLE (amended after; cap of two rounds reached) |

**Amendments applied:** all F findings of rounds 1 and 2. **Concern (user waiver, 2026-11-03):** the two round cap was reached with F findings amended but not re audited.
**No implementation detail outside Section 14:** PASS

## 14. Evidence appendix

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| direct write, no temporary file | `src/mcp_htmleditor/http_server.py:331-338` |
| template save answered ok and ignored | `src/mcp_htmleditor/http_server.py:325-327` |
| invalid `Content-Length` unhandled, no limit | `src/mcp_htmleditor/http_server.py:296-298` (the arch layout endpoint at `:358` has the same flaw and is out of scope) |
| status fields `mtime`, `update_in_progress`, ... | `src/mcp_htmleditor/http_server.py:278-286` |
| flag never expires, written to the state file | `src/mcp_htmleditor/state.py:61-95` |
| poll reload logic; the poll adopts the polled mtime in every case (`editor.js:326`); the save ignores the response status | `src/mcp_htmleditor/static/editor.js:298-330`, save at `1418-1429` |
| swallowed poll failure | BL-0013 (`sdlc/backlog/BL-0013-silent-polling-failure.md`) |
| non atomic writes | BL-0016 |

Test command: `make test`; gate `make check`.

### 14.3 Design inputs

- `EditorState` is a per process singleton persisted next to the file (`state.py`); sharing between processes by key needs a new store. Detection signal: E2E-024, E2E-025.
- The modification time resolution of the file system limits conflict detection for two writes in the same instant; the status already uses `st_mtime` float. Detection signal: E2E-007.
- E2E-014 and E2E-013 need a way to inject a failure at the last write step; a test seam is required. Detection signal: those tests cannot be written without it.
- The editor page must keep `lastMtime` from the status and include it as `base_mtime`, and replace the swallowed poll failure (`editor.js:301`, BL-0013); the post-save status read at `editor.js:1425-1429` also swallows. Detection signal: E2E-008, E2E-017.
- `patch` (SPEC-0007) and `restore` must share the atomic writer and the snapshot step with the browser save.
- `HTMLEDITOR_STATE_DIR` is a new setting in `src/mcp_htmleditor/config.py`.
- Clock control for E2E-005, 020, 021 needs an injectable clock.
- Documents to update: `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md`, skill core tool list (SPEC-0006).
