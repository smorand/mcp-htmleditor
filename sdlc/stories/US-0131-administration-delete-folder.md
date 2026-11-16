# US-0131: Administration: delete a folder after retyping its name

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0130
> min_tier: 1
> Files touched: 7
> Closes spec: no

## Objective

The administrator deletes a folder by retyping its exact name (composed form, case and accents matter); the folder, all its presentations with their history and requests, and its members disappear for good, a folder created later with the same name is empty and has no member, and a wrong name deletes nothing.

## Requirements covered

- SPEC-0025/FR-NEW-043: WHEN the administrator deletes a folder after retyping its exact name THE web library mode SHALL remove the folder, all its presentations with their history, and all its members.
  - Business rules: The retyped name is first brought to its composed form, then compared with the folder name character by character, case sensitive. A folder created later with the same name is empty and has no member. Deleting a folder removes the requests and AI suggestions of all its presentations too: none returns when a folder of the same name is created again.
- SPEC-0025/FR-NEW-044: IF the retyped name differs from the folder name in any character, including case, THEN THE web library mode SHALL show "The name does not match. Nothing was deleted." and delete nothing.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-048 (partial: after a folder is deleted its former members get `Access denied.` on their next page request): WHEN the administrator removes a person, changes their role, or deletes the folder THE web library mode SHALL apply the change to that person's next action in that folder, refusing it with "Access denied." when it is no longer allowed, and storing nothing.
  - Business rules: Content already displayed stays on screen; no new content loads. A presentation open for editing keeps its unsaved changes on screen; the refusal appears at the next automatic store as the editor's only notice "Access denied." (no "Save failed:" prefix). An upload still being sent when the right is removed is refused at its end and stores nothing. A raised role (RO to RW) also applies from the next action. When the person has typed nothing that is not stored, FR-NEW-074 applies: no notice until the person acts.
- SPEC-0025/FR-NEW-049 (partial: the line `Deleted folder "<folder>"`): WHEN an upload, a replacement or a deletion of a presentation, the creation or deletion of a folder, or the adding, changing or removing of a member succeeds THE web library mode SHALL add a line to the activity list with who did it, when, and what.
  - Business rules: Line texts: Uploaded "<name>" in "<folder>"; Replaced "<name>" in "<folder>"; Deleted "<name>" from "<folder>"; Created folder "<folder>"; Deleted folder "<folder>"; Added <email> as RW to "<folder>" (or RO); Changed <email> to RO in "<folder>" (or RW); Removed <email> from "<folder>". Who is the email address of the person; when is shown as on the folder page. Who is the email address of the person in lower case, whatever letter case Google returned.
- SPEC-0025/FR-NEW-067 (partial: the `Delete folder` button and the prompt `Type the folder name to confirm.` with `Delete folder` and `Cancel`): The web library mode SHALL name the controls and prompts it adds exactly as listed in the business rules.
  - Business rules: Folder page: "All folders" (back to the home page). Administration: sections "Folders" and "Activity"; the field "Folder name" with the button "Create folder"; per folder the button "Delete folder". Deleting a folder: the prompt "Type the folder name to confirm." with the buttons "Delete folder" and "Cancel". Per folder a section "Members": the field "Email address", the chooser "Role" offering "Read and write" and "Read only", the button "Add member"; per member a role chooser and the button "Remove". Upload progress text: "<file name> <percent>%", percent a whole number rounded down. The administration page shows "All folders" and "Sign out". Administration order: folders as on the home page (FR-NEW-015); the members of a folder alphabetical by email address, by character code.

## Independent Test

Run `make test ARGS='-k library_foldel'`. The assertion that is not a mock: after deleting a folder of 100 presentations, `StoredLibrary.entries()` (a walk of `library_dir` and `state_dir`) holds no path of that folder and no history or request directory of its presentations, and recreating the name gives a folder whose member and presentation queries return nothing.

## Design excerpt

### Decisions

- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-026 (SPEC-0025): Writes of presentation bytes use `atomic_write(path, data, reason=...)` (reasons `browser-save`, `keep-mine`, `replace`); history and request records stay in the state directory keyed by the resolved path; `delete_presentation` and `delete_folder` remove the row first, then the file, then `<state_dir>/files/<key>/` (history, requests, update flag) of each presentation. Obliged by: SPEC-0025/FR-NEW-026, SPEC-0025/FR-NEW-034, SPEC-0025/FR-NEW-039, SPEC-0025/FR-NEW-043, SPEC-0025/FR-NEW-063.
- DEC-029 (SPEC-0025): Names go through `library/names.py`: `compose` (NFC), `name_key` (NFC of the lower cased composed text), `order_key` (accents removed by NFD and dropping `Mn`, lower case, then the exact name); file names are an allow list (Latin script letters by `unicodedata.name` starting with `LATIN`, `Mn` only after such a letter, ASCII digits, space, `. _ - ( ) '`), at most 100 composed characters before `.html`, no leading dot, no edge space, not only spaces; folder names are letters of any script (`L*`), `M*`, decimal digits (`Nd`), space and hyphen, 1 to 60 composed characters after trimming; addresses match `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` after trimming and are stored lower case. All pages build text through `pages.esc()` (`html.escape(quote=True)`), and JavaScript writes with `textContent`. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-042, SPEC-0025/FR-NEW-046, SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-033.
- DEC-030 (SPEC-0025): Activity is the table `activity`, one row per successful action written in the same transaction as the action, with the final line text and the actor's lower case address; after each insert rows older than the 500 newest are deleted; the page reads `ORDER BY id DESC LIMIT 500`. Refusals, sign ins and stored changes never write. Obliged by: SPEC-0025/FR-NEW-049, SPEC-0025/FR-NEW-050, SPEC-0025/FR-NEW-051.
- DEC-048 (SPEC-0025): Logging and tracing follow the project rules: `logger = logging.getLogger(__name__)`, `%` formatting, stderr console, `click.echo` only for the start line; spans `auth.google_token`, `library.upload`, `library.replace`, `library.delete_presentation`, `library.delete_folder`, `library.seed`, `session.create`, with sizes and status codes only; no email, name, token, cookie or credential in a log line or an attribute. Obliged by: SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-020 (nothing about members leaks), AGENTS.md observability rules.

### Data model

No change. `ON DELETE CASCADE` removes `members` and `presentations` rows; files and state directories are removed by `Library.delete_folder`.

### Contracts

**Route**: `POST /api/folders/<fid>/delete` (library origin, `ADMINISTER`, origin rule of US-0126) with `{"confirm": str}`: `names.compose(confirm) == folder.name` (character by character, case sensitive); on mismatch `400 {"ok": false, "error": "The name does not match. Nothing was deleted."}` and nothing changes; on a match `200 {"ok": true}`.

`Library.delete_folder(folder_id: str, confirm: str, actor: str) -> None`: one `BEGIN IMMEDIATE` transaction that checks the name, collects the presentation ids, inserts the activity line `Deleted folder "<name>"`, deletes the folder row (cascade); then, outside the transaction, `shutil.rmtree(files/<fid>)` and for each presentation id the state directory `<state_dir>/files/<key>/` where `key = sha256(str(path.resolve())).hexdigest()[:32]` (`state.py:211-214`, `request_store.py:87-90`); filesystem failures are logged with `logger.warning` and never raised (the rows are already gone and ids are never reused). Wrapped in `trace_span("library.delete_folder", {"presentations": count})`.

**UI** (`pages.admin_page`, `library.js`): per folder a button `Delete folder` that opens a `<dialog>` with the text `Type the folder name to confirm.`, an `<input>` labelled `Folder name`, buttons `Delete folder` and `Cancel`; `Cancel` closes it with no request; focus moves into the dialog on open and back to the button on close.

**After deletion**: the folder id is unknown, so `/f/<fid>` gives `Access denied.` to its former members (US-0129 behavior), and the home page no longer lists it (an administrator with no folder left sees `You have no access to any folder yet.`).

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/store.py` | modify | `delete_folder`, state directory cleanup |
| `src/mcp_htmleditor/library/routes_admin.py` | modify | delete route |
| `src/mcp_htmleditor/library/pages.py` | modify | `<dialog>` and button |
| `src/mcp_htmleditor/static/library.js` | modify | dialog handling |
| `tests/library_support.py` | modify | `StoredLibrary.entries()`, request record helper |
| `tests/test_library_foldel_http.py` | create | functional tests |
| `tests/test_library_foldel_e2e.py` | create | E2E-157 |

### Existing patterns

`history.py:108-115` (`discard`, `prune`) and `request_store.py:87-150` for the per file record directories; `tests/test_history_e2e.py` for creating history versions in a test.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-015: The administrator with no folder sees the empty message

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_foldel_http.py`
- **Category:** failure (state transition, side effect)
- **Scenario:** SC-003
- **Requirements:** FR-NEW-014, FR-NEW-015, FR-NEW-016
- **Given** The administrator deleted the three folders of the standard library.
- **When** seb.morand@gmail.com opens the home page.
- **Then** "You have no access to any folder yet." is shown, with "Administration" and "Sign out".
- **And** After he creates the folder "Oncology 2030" the home page lists it and the message is gone.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-099: The administrator deletes a folder after retyping its name

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_foldel_http.py`
- **Category:** happy (side effect, state transition)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-044, FR-NEW-049, FR-NEW-062
- **Given** "Pneumo Été" holds "Spirometry Basics" and has dan.rw@example.org as RW.
- **When** The administrator chooses to delete "Pneumo Été" and retypes "Pneumo Été".
- **Then** The home page lists 2 folders.
- **And** The operator's view of the library holds no trace of "Spirometry Basics" nor of its history, and no member of the deleted folder.
- **And** The activity list gains "Deleted folder "Pneumo Été"".
- **And** The exact retyped name was accepted: no "The name does not match. Nothing was deleted." appeared.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-100: A retyped name with a different case is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_foldel_http.py`
- **Category:** failure
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-044
- **Given** "Pneumo Été" holds "Spirometry Basics" and has dan.rw@example.org as RW; the administrator has chosen to delete "Pneumo Été" and is asked to retype its name.
- **When** He retypes "pneumo été".
- **Then** "The name does not match. Nothing was deleted." is shown.
- **And** "Pneumo Été" and "Spirometry Basics" are still there.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-101: An empty retyped name is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_foldel_http.py`
- **Category:** failure
- **Scenario:** SC-015
- **Requirements:** FR-NEW-044
- **Given** "Pneumo Été" holds "Spirometry Basics" and has dan.rw@example.org as RW; the administrator has chosen to delete "Pneumo Été" and is asked to retype its name.
- **When** He confirms with nothing typed.
- **Then** "The name does not match. Nothing was deleted." is shown.
- **And** The folder is intact.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-103: A recreated folder is empty and has no member

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_foldel_http.py`
- **Category:** edge (state transition)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-040, FR-NEW-043, FR-NEW-048
- **Given** "Pneumo Été", which held "Spirometry Basics" and had dan.rw@example.org as RW, was deleted by the administrator.
- **When** The administrator creates a folder named "Pneumo Été" again.
- **Then** The folder is listed and opens with "This folder has no presentations yet."
- **And** Its member list is empty; dan.rw@example.org opening it sees "Access denied."
- **And** No request or AI suggestion of the 'Spirometry Basics' deck returns: its Requests list does not exist anywhere in the new folder.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-104: A folder of 100 presentations is deleted entirely

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_foldel_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-060
- **Given** "Pneumo Été" holds 100 presentations "Deck 001" to "Deck 100".
- **When** The administrator opens it, then deletes it with the exact name.
- **Then** The folder page lists the 100 presentations within 2 seconds; after the deletion the folder is gone.
- **And** Recreating "Pneumo Été" shows an empty folder: none of the 100 decks returns.
- **And** None of the requests queued on the 100 presentations returns after the folder is created again.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-106: Deleting the last folder leaves the empty home page

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_foldel_http.py`
- **Category:** edge (side effect, state transition)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-016, FR-NEW-043, FR-NEW-049
- **Given** The administrator, and the only folder "Pneumo Été" (the two others were deleted before).
- **When** He deletes "Pneumo Été" by retyping its exact name and opens the home page.
- **Then** "You have no access to any folder yet." is shown.
- **And** The activity list holds "Deleted folder "Pneumo Été"" as its newest line.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-107: A retyped name without its accent is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_foldel_http.py`
- **Category:** edge
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-044
- **Given** "Pneumo Été" holds "Spirometry Basics".
- **When** The administrator retypes "Pneumo Ete", then "Pneumo Été " (a space at the end).
- **Then** Each time "The name does not match. Nothing was deleted." is shown (for "Pneumo Ete" and for the name with a trailing space).
- **And** "Pneumo Été" and "Spirometry Basics" are intact.
- **And** In a further run, retyping "Pneumo Été" (accents as separate marks) is accepted and deletes the folder, because the retyped name is brought to its composed form first.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-157: The folder deletion prompt can be cancelled

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_foldel_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-044, FR-NEW-067
- **Given** seb.morand@gmail.com is on the administration; "Pneumo Été" holds "Spirometry Basics".
- **When** He presses "Delete folder" next to "Pneumo Été", then "Cancel".
- **Then** The prompt "Type the folder name to confirm." with the buttons "Delete folder" and "Cancel" is shown first; after "Cancel" the prompt is gone.
- **And** "Pneumo Été" and "Spirometry Basics" are intact; the activity list has no new line.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

## Constraints

- Delete the row first, the files after; never the reverse.
- No `rm`; the code uses `shutil.rmtree` on paths built from validated ids and keys only.
- Scope boundary: deleting a single presentation (US-0145).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (deletion order).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0131: Administration: delete a folder after retyping its name` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
