# US-0132: Administration: members and roles of a folder

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0130
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

The administrator adds a member (trimmed, lower case, valid address) to a folder with `Read and write` or `Read only`, changes a role or removes a member; one entry per address and folder; the change applies to the person's next page request; the administrator can never be reduced by a member entry.

## Requirements covered

- SPEC-0025/FR-NEW-045: WHEN the administrator adds an email address with the role RW or RO to a folder THE web library mode SHALL give that person that role in that folder.
  - Business rules: The address is trimmed, stored and shown in lower case. The roles that can be chosen are "Read and write" and "Read only"; any other role is refused with "This is not a valid role." and nothing changes. An address already listed in the folder, without regard to case, is never added twice: with the same role nothing changes and no activity line is added; with the other role the entry is updated and the activity line reads Changed <email> to <role> in "<folder>". The role applies from the person's next action.
- SPEC-0025/FR-NEW-046: IF the text typed as an email address is not one valid address THEN THE web library mode SHALL show "This is not a valid email address." and change nothing.
  - Business rules: Valid means one address of the form local@domain: the local part has letters, digits and . _ % + - ; the domain has letters, digits and hyphens and at least one dot; no spaces or commas. Two addresses in one field are refused.
- SPEC-0025/FR-NEW-047: WHEN the administrator changes the role of a member or removes the member THE web library mode SHALL apply the change to that folder only.
  - Business rules: The same person's roles in other folders are untouched.
- SPEC-0025/FR-NEW-012 (partial: the roles that can be given are RW and RO only; a hand made role `Admin` is refused with `Access denied.` for a non administrator and `This is not a valid role.` for the administrator): The web library mode SHALL NOT give the Admin role to any account other than seb.morand@gmail.com, whatever the member lists contain.
  - Business rules: The roles that can be given to a member are RW and RO only.
- SPEC-0025/FR-NEW-048 (partial: a role change or a removal applies to the person's next page request without signing in again): WHEN the administrator removes a person, changes their role, or deletes the folder THE web library mode SHALL apply the change to that person's next action in that folder, refusing it with "Access denied." when it is no longer allowed, and storing nothing.
  - Business rules: Content already displayed stays on screen; no new content loads. A presentation open for editing keeps its unsaved changes on screen; the refusal appears at the next automatic store as the editor's only notice "Access denied." (no "Save failed:" prefix). An upload still being sent when the right is removed is refused at its end and stores nothing. A raised role (RO to RW) also applies from the next action. When the person has typed nothing that is not stored, FR-NEW-074 applies: no notice until the person acts.
- SPEC-0025/FR-NEW-049 (partial: the lines `Added <email> as RW to "<folder>"`, `Changed <email> to RO in "<folder>"`, `Removed <email> from "<folder>"`): WHEN an upload, a replacement or a deletion of a presentation, the creation or deletion of a folder, or the adding, changing or removing of a member succeeds THE web library mode SHALL add a line to the activity list with who did it, when, and what.
  - Business rules: Line texts: Uploaded "<name>" in "<folder>"; Replaced "<name>" in "<folder>"; Deleted "<name>" from "<folder>"; Created folder "<folder>"; Deleted folder "<folder>"; Added <email> as RW to "<folder>" (or RO); Changed <email> to RO in "<folder>" (or RW); Removed <email> from "<folder>". Who is the email address of the person; when is shown as on the folder page. Who is the email address of the person in lower case, whatever letter case Google returned.
- SPEC-0025/FR-NEW-067 (partial: the `Members` section, `Email address`, `Role`, `Add member`, `Remove` and the role chooser of each member): The web library mode SHALL name the controls and prompts it adds exactly as listed in the business rules.
  - Business rules: Folder page: "All folders" (back to the home page). Administration: sections "Folders" and "Activity"; the field "Folder name" with the button "Create folder"; per folder the button "Delete folder". Deleting a folder: the prompt "Type the folder name to confirm." with the buttons "Delete folder" and "Cancel". Per folder a section "Members": the field "Email address", the chooser "Role" offering "Read and write" and "Read only", the button "Add member"; per member a role chooser and the button "Remove". Upload progress text: "<file name> <percent>%", percent a whole number rounded down. The administration page shows "All folders" and "Sign out". Administration order: folders as on the home page (FR-NEW-015); the members of a folder alphabetical by email address, by character code.

## Independent Test

Run `make test ARGS='-k library_members'`. The assertion that is not a mock: Bob (no role) signs in and sees `Access denied.`, the administrator adds `Bob.Nobody@Gmail.com ` as RO, and Bob's next page request (no new sign in) lists the folder; the `members` table holds exactly one row `bob.nobody@gmail.com` with role `RO`.

## Design excerpt

### Decisions

- DEC-018 (SPEC-0025): Roles are never stored in a session or a grant: every request recomputes the role from `members` (and `ADMIN_EMAIL`), so a change applies to the next action. Obliged by: SPEC-0025/FR-NEW-048, SPEC-0025/FR-NEW-021.
- DEC-019 (SPEC-0025): Checks run in this order for a state changing API request: `Origin` (DEC-022), session, permission of the route (administrator first), then payload validation (role value, address, name). Obliged by: SPEC-0025/FR-NEW-013, SPEC-0025/FR-NEW-012, SPEC-0025/FR-NEW-014.
- DEC-022 (SPEC-0025): Every state changing request (any method other than `GET`, `HEAD` and `OPTIONS`: `POST` and `DELETE`) is refused with `Access denied.`, before the session is looked up, unless `Origin` is present and equals the origin of the receiving host exactly, and `Sec-Fetch-Site`, when present, is `same-origin` (or `none`); JSON routes also require `Content-Type: application/json`, the upload requires the header `X-File-Name`. The local rule that accepts a missing `Origin` is not used. Obliged by: SPEC-0025/FR-NEW-070, SPEC-0025/FR-NEW-023.
- DEC-023 (SPEC-0025): Every refusal for a missing or forbidden target is rendered by one function, `pages.access_denied()`, with the same status (`403`), headers and bytes whatever the cause; the page holds `Access denied.` and the `Sign out` form and nothing else. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-029 (SPEC-0025): Names go through `library/names.py`: `compose` (NFC), `name_key` (NFC of the lower cased composed text), `order_key` (accents removed by NFD and dropping `Mn`, lower case, then the exact name); file names are an allow list (Latin script letters by `unicodedata.name` starting with `LATIN`, `Mn` only after such a letter, ASCII digits, space, `. _ - ( ) '`), at most 100 composed characters before `.html`, no leading dot, no edge space, not only spaces; folder names are letters of any script (`L*`), `M*`, decimal digits (`Nd`), space and hyphen, 1 to 60 composed characters after trimming; addresses match `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` after trimming and are stored lower case. All pages build text through `pages.esc()` (`html.escape(quote=True)`), and JavaScript writes with `textContent`. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-042, SPEC-0025/FR-NEW-046, SPEC-0025/FR-NEW-053, SPEC-0025/FR-NEW-015, SPEC-0025/FR-NEW-033.
- DEC-030 (SPEC-0025): Activity is the table `activity`, one row per successful action written in the same transaction as the action, with the final line text and the actor's lower case address; after each insert rows older than the 500 newest are deleted; the page reads `ORDER BY id DESC LIMIT 500`. Refusals, sign ins and stored changes never write. Obliged by: SPEC-0025/FR-NEW-049, SPEC-0025/FR-NEW-050, SPEC-0025/FR-NEW-051.
- DEC-053 (SPEC-0025): Library pages use plain HTML controls (`a`, `button`, `form`, `label`, `input`, `select`, `<dialog>` for the questions) with a visible text or an `aria-label` on every control, no click handler on a non focusable element, and `library.js` moves focus into a dialog when it opens and back to the control when it closes. Obliged by: SPEC-0025/FR-NEW-064.

### Data model

No change (`members` exists since migration 1). `Library.set_member` is an upsert on the primary key.

### Contracts

**Routes** (library origin, `ADMINISTER`, origin rule, JSON):

| Method path | Body | Answers |
|---|---|---|
| `POST /api/folders/<fid>/members` | `{"email": str, "role": "RW" or "RO"}` | `200 {"ok": true}`; `400 {"ok": false, "error": "This is not a valid email address."}`; `400 {"ok": false, "error": "This is not a valid role."}` |
| `POST /api/folders/<fid>/members/remove` | `{"email": str}` | `200 {"ok": true}` |

Order of checks (DEC-019): session, origin, `ADMINISTER` (so a RW member who posts the role `Admin` gets `Access denied.`), folder exists, address valid, role valid. `names.check_email(raw) -> str`: `raw.strip()`, matches `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$` (one address, no spaces, no comma, a plus sign accepted, an apostrophe or a missing dot refused), returns `.lower()`.

`Library.set_member(folder_id, email, role, actor)`: `INSERT ... ON CONFLICT(folder_id, email) DO UPDATE SET role`; the activity line is written only when the row is new (`Added <email> as RW to "<folder>"`) or the role changed (`Changed <email> to RO in "<folder>"`); the same address with the same role changes nothing and writes no line. An address equal to `ADMIN_EMAIL` may be stored (nothing changes for the administrator, DEC-006). `remove_member` writes `Removed <email> from "<folder>"` and nothing when the row does not exist.

**Admin page** (per folder, section `Members`): members sorted by address by code point; a form with `Email address` (label), `Role` (`<select>` with `Read and write` and `Read only`), `Add member`; per member a `<select>` of the role (change on `change` posts the same route) and a `Remove` button.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/routes_admin.py` | modify | member routes |
| `src/mcp_htmleditor/library/store.py` | modify | `set_member`, `remove_member`, `members_of` |
| `src/mcp_htmleditor/library/names.py` | modify | `check_email` |
| `src/mcp_htmleditor/library/pages.py` | modify | members section |
| `src/mcp_htmleditor/static/library.js` | modify | member forms |
| `tests/library_support.py` | modify | `post_json` role helpers |
| `tests/test_library_members_http.py` | create | functional tests |
| `tests/test_library_members_e2e.py` | create | browser tests |

### Existing patterns

`library/routes_admin.py` from US-0130 for JSON routes; `tests/test_library_admin_http.py` for administrator sessions.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-002: An account with no right is refused after Google

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** failure (state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-008, FR-NEW-020, FR-NEW-065, FR-NEW-068
- **Given** bob.nobody@gmail.com is in no member list and is not the administrator.
- **When** He signs in with Google using bob.nobody@gmail.com.
- **Then** He sees "Access denied." and a "Sign out" button; no folder name and no presentation name appears anywhere.
- **And** After the administrator adds bob.nobody@gmail.com as RO in "Cardiology 2027", Bob opens a page without signing in again and sees the home page with "Cardiology 2027".
- **And** He chooses "Sign out" and the sign in page is shown; every text he saw was in English.
- **And** In a second run, Bob's browser is already signed in to lamya.chrif@gmail.com at Google; he signs in again: Google shows its account chooser, he picks bob.nobody@gmail.com and sees "Access denied."; picking lamya.chrif@gmail.com shows her folders.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-011: A person removed while their session was expired is refused after signing in again

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** failure (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-003, FR-NEW-006, FR-NEW-048
- **Given** dan.rw@example.org's session expired; the administrator then removed him from every folder where he was a member.
- **When** He signs in with Google again.
- **Then** "Access denied." is shown and no folder is listed.
- **And** The administrator's member list of "Cardiology 2027" shows only carol.ro@example.org.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-084: The administrator opens the administration

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_members_e2e.py`
- **Category:** happy
- **Scenario:** SC-013
- **Requirements:** FR-NEW-011, FR-NEW-014, FR-NEW-050, FR-NEW-067
- **Given** seb.morand@gmail.com is signed in.
- **When** He chooses "Administration".
- **Then** He sees the section "Folders", where each folder shows its "Members" and a "Delete folder" button, the field "Folder name" with the button "Create folder", and the section "Activity".
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-089: Only RW and RO can be given

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_members_e2e.py`
- **Category:** edge
- **Scenario:** SC-013
- **Requirements:** FR-NEW-012, FR-NEW-045, FR-NEW-067
- **Given** The administrator opens the add member form of "Pneumo Été".
- **When** He looks at the "Members" of "Pneumo Été", fills the field "Email address" with dan.rw@example.org, chooses "Read and write" in "Role" and presses "Add member".
- **Then** The chooser "Role" offers "Read and write" and "Read only" and nothing else; no "Admin".
- **And** Dan's home page labels the folder "Read and write" and shows no "Administration".
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-110: Invalid addresses are refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** failure
- **Scenario:** SC-016
- **Requirements:** FR-NEW-045, FR-NEW-046
- **Given** The administrator is adding a member to "Pneumo Été".
- **When** He types in turn "not-an-email", "carol@", an empty field.
- **Then** Each time "This is not a valid email address." is shown.
- **And** The member list of "Pneumo Été" is still empty.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-111: Two addresses in one field are refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** failure
- **Scenario:** SC-016
- **Requirements:** FR-NEW-046, FR-NEW-053
- **Given** The administrator.
- **When** He types "dan.rw@example.org, carol.ro@example.org" and, then, "<b>x</b>@example.org".
- **Then** Each time "This is not a valid email address." is shown; the second text is displayed as written, not in bold.
- **And** Neither address became a member.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-112: A RW member adds himself as Admin by hand

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-012, FR-NEW-013, FR-NEW-045
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; he sends by hand the adding of dan.rw@example.org with the role "Admin" to "Pneumo Été".
- **When** He sends it with his own session.
- **Then** "Access denied." is returned.
- **And** The member list of "Pneumo Été", seen by the administrator, is still empty and no "Administration" entry appears for Dan.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: a RW member gets `Access denied.` because the permission check runs before the role value is validated (DEC-019).

### SPEC-0025/E2E-113: An address already listed in other letter case with another role updates the entry

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-045, FR-NEW-047
- **Given** "Cardiology 2027" lists dan.rw@example.org RW.
- **When** The administrator adds "DAN.RW@Example.org" with the role "Read only".
- **Then** The list shows one entry, dan.rw@example.org in lower case, with the role RO.
- **And** Dan's next action in the folder is read only.
- **And** The activity list gains the line Changed dan.rw@example.org to RO in "Cardiology 2027".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-115: A trimmed address gives access without a new sign in

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** edge (state transition)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-003, FR-NEW-022, FR-NEW-045, FR-NEW-046
- **Given** bob.nobody@gmail.com is signed in and sees "Access denied."
- **When** The administrator adds " bob.nobody@gmail.com " (with spaces around) as RO to "Cardiology 2027".
- **Then** The next page Bob opens is the home page with "Cardiology 2027" labelled "Read only".
- **And** The spaces around the address did not make it invalid.
- **And** The address is shown in lower case, "bob.nobody@gmail.com", without the spaces.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-156: The controls the mode adds carry their exact names

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_members_e2e.py`
- **Category:** edge
- **Scenario:** SC-013
- **Requirements:** FR-NEW-011, FR-NEW-040, FR-NEW-045, FR-NEW-067
- **Given** seb.morand@gmail.com is signed in; carol.ro@example.org is RO in "Cardiology 2027".
- **When** He opens "Cardiology 2027" from the home page, then "Administration".
- **Then** The folder page offers "All folders". The administration shows "Folders" and "Activity"; the field "Folder name" with "Create folder"; for "Cardiology 2027" the button "Delete folder" and the "Members" with the field "Email address", the chooser "Role" ("Read and write", "Read only"), the button "Add member"; for the member carol.ro@example.org a role chooser showing "Read only" and the button "Remove".
- **And** Pressing "All folders" returns to the home page.
- **And** With members dan.rw@example.org, carol.ro@example.org and Alice.RO@example.org (stored as alice.ro@example.org) in "Cardiology 2027", the members are listed alice.ro@example.org, carol.ro@example.org, dan.rw@example.org; the folders are listed as on the home page.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: members of a folder are listed alphabetically by address, by character code; folders as on the home page.

### SPEC-0025/E2E-160: Adding the same address with the same role changes nothing

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-045
- **Given** "Pneumo Été" has no member.
- **When** The administrator adds "Dan.RW@Example.ORG" as "Read and write", then adds "dan.rw@example.org" as "Read and write" again.
- **Then** The list shows one entry, dan.rw@example.org in lower case, "Read and write".
- **And** The activity list holds one line, Added dan.rw@example.org as RW to "Pneumo Été"; the second addition adds no line.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-161: A role other than the two offered is refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-012, FR-NEW-045
- **Given** seb.morand@gmail.com is on the administration; "Pneumo Été" has no member; from a command line tool outside the editor he sends the addition of dan.rw@example.org with the role "Admin".
- **When** He sends it.
- **Then** "This is not a valid role." is returned.
- **And** The member list of "Pneumo Été" is still empty and the activity list has no new line; Dan's home page has no "Administration".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-176: Email address forms: plus sign accepted, apostrophe and missing dot refused

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_members_http.py`
- **Category:** failure (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-045, FR-NEW-046
- **Given** The administrator is adding members to "Pneumo Été".
- **When** He adds "dan+rw@example.org" (Read and write), then "o'brien@example.org", "dan@localhost" and "dan rw@example.org".
- **Then** The first is added; each of the other three shows "This is not a valid email address."
- **And** The member list holds only dan+rw@example.org.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

Unit tests in `tests/test_library_names.py` for `check_email` on the list of E2E-110, E2E-111, E2E-176.

## Constraints

- The member list is never read to decide who the administrator is.
- No role other than `RW` and `RO` is ever stored (the table CHECK is the last line of defence).
- Scope boundary: opening presentations with the new rights (US-0133).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (members, check order).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0132: Administration: members and roles of a folder` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
