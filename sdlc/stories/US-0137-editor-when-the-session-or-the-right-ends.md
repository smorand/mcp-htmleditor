# US-0137: The editor when the session or the right ends

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0136
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

When a session ends, a right is removed or a role is lowered while a presentation is open, the editor keeps the presentation and any unsaved text on screen, shows exactly one English notice at the next store (`Your session has expired. Sign in again to save.` or `Access denied.`) with no `Save failed:` prefix and no connection lost notice, stays silent when nothing is unsaved, recovers after signing in again in another window, and a download shows the sign in page or `Access denied.`.

## Requirements covered

- SPEC-0025/FR-NEW-007: IF the session of a person ends while a presentation is open for editing THEN THE web library mode SHALL keep the presentation and the unsaved changes on screen and, at the next automatic store of a change, show "Your session has expired. Sign in again to save." and store nothing.
  - Business rules: The notice appears at the first automatic store after the session ended: 0.8 seconds after typing stops, or at once when the person leaves the edited field. It is the only notice: the text "Save failed:" is not put in front of it and "Connection to the editor server lost" is not shown for an ended session, however long the person waits. After the person signs in again in another window, the next automatic store in the first window stores the changes, subject to the conflict notice (FR-NEW-027). When the person has typed nothing that is not stored, FR-NEW-074 applies instead: no notice until the person acts.
- SPEC-0025/FR-NEW-074: IF the session of a person ended, or their right was removed, while a presentation is open and nothing they typed is unstored, THEN THE web library mode SHALL keep the presentation on screen and show no notice, including "Connection to the editor server lost", until the person acts.
  - Business rules: The next action that needs the library gives the sign in page, or "Access denied." when the right was removed. Moving between slides inside the presentation is not such an action.
- SPEC-0025/FR-NEW-010 (partial: the editor shows `Access denied.` alone (no prefix) as notice or alert; a refused HTML download shows `Access denied.` only): IF a link points to a folder or a presentation that does not exist, no longer exists, or belongs to a folder where the person holds no role THEN THE web library mode SHALL show exactly "Access denied." and nothing else.
  - Business rules: The page is identical in wording and content in the three cases; it shows the text "Access denied." and the "Sign out" button, nothing else: it never names the folder or the presentation and never says whether it exists. The same holds for an action refused for these reasons (storing a change, download, delete, upload). When the refusal reaches a presentation open for editing, the editor shows "Access denied." as its only notice (no "Save failed:" prefix) and keeps the unsaved changes on screen. An address of the product that names no page, asked by a signed in person, gives exactly "Access denied." with the "Sign out" button. A refused download or export shows "Access denied." as its only text, with no prefix such as "Export PPTX échoué :"; no file is received and the presentation stays on screen. When the session ended, the person gets the sign in page, unless they have unsaved text: then FR-NEW-007 applies and no download happens. Any other failure of a download or export shows the editor's usual failure notice with the operating system reason, without any file name or path, never the text of an exception.
- SPEC-0025/FR-NEW-048 (partial: a removed person, a lowered role or a deleted folder is refused at the next store or download, the text stays on screen): WHEN the administrator removes a person, changes their role, or deletes the folder THE web library mode SHALL apply the change to that person's next action in that folder, refusing it with "Access denied." when it is no longer allowed, and storing nothing.
  - Business rules: Content already displayed stays on screen; no new content loads. A presentation open for editing keeps its unsaved changes on screen; the refusal appears at the next automatic store as the editor's only notice "Access denied." (no "Save failed:" prefix). An upload still being sent when the right is removed is refused at its end and stores nothing. A raised role (RO to RW) also applies from the next action. When the person has typed nothing that is not stored, FR-NEW-074 applies: no notice until the person acts.
- SPEC-0025/FR-NEW-065 (partial: the notices added by the mode are English next to the editor's French labels): The web library mode SHALL show every page, message and control that it adds in English, and SHALL show the editor and the presentations with the texts they have in the local mode.
  - Business rules: Added by the mode, in English: the sign in page, the home page, the folder page, upload, delete, the administration, the activity list and every refusal. Kept as in the local mode, not translated: the editor's toolbar labels (for example "Édition", "Annuler", "Rétablir", "Mode présentation plein écran", "Présenter avec le pointeur", "Vue présentateur", "Télécharger en PPTX", "Télécharger le fichier HTML", "Raccourcis clavier", and in English "Requests", "Ask AI", "Notes"), the editor's own notices and the text of the presentations.

## Independent Test

Run `make test ARGS='-k library_access'`. The assertion that is not a mock: with the clock moved past the session end and Dan's typed `!` unsaved, Playwright reads `#save-error .notice-text` equal to `Your session has expired. Sign in again to save.` within 2 seconds and `#connection-lost` stays hidden for 10 seconds; the stored file is unchanged (`sha256`).

## Design excerpt

### Decisions

- DEC-037 (SPEC-0025): Opening a presentation is a one time ticket then a grant: `GET /open/<pid>` (library origin, role >= RO) inserts a ticket (sha256 of a random token, 60 s, bound to the session and the presentation) and redirects to `<content origin>/enter?t=`; `/enter` deletes the ticket, inserts a grant (`token_hash`, `session_id_hash`, `presentation_id`) and sets the cookie `__Secure-d` (`d` on http) with `Path=/d/<pid>/` and no `Max-Age`. A grant is valid while its session is alive; when the session expired by time and the same address has a newer live session, the grant is rebound to it (only within 24 hours of expiry, rows purged after that); a grant whose session was ended by sign out is gone (cascade) and never revives. Answers: `Live(email)`, `Ended` (a cookie that no longer resolves: session expired, signed out, purged) and `Absent` (no cookie). Obliged by: SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-007, SPEC-0025/FR-NEW-072, SPEC-0025/FR-NEW-048.
- DEC-040 (SPEC-0025): Deck route failures carry a `code` (`denied` or `session_expired`) only for requests that carry the header `X-Editor: 1`, which `editor-library.js` adds to every `fetch` it wraps; a request without it gets `403` `Access denied.` JSON when the grant is live and the role lacks the permission (so a hand made write or read by a RO person is refused with the text the tests expect), and `302 <library origin>/open/<pid>` when the grant is absent or ended or the route is a navigation route (`/d/<pid>/`, `/content-frame`, `/download`, `/export/pptx`), so a visitor or a copied session sees the sign in page and never a file. When a response has `code`, `editor-library.js` (which redefines the global functions `showSaveError`, `notePollFailure` and wraps `alert`, all plain global bindings the editor scripts call at run time) makes the editor show `answer.error` alone (no `Save failed:` prefix, no `Export <FORMAT> échoué :` prefix) as the notice or alert; `session_expired` with nothing unsaved is silent (no notice, no failure count) and the next download or export navigates to the library origin; the status poll treats such an answer as a quiet pause: it does not count toward the three failures of the lost connection notice; the click of `#download-btn` (an `<a href download>` in the editor) is intercepted and sent with `fetch`, so a download refused or cut by the end of the session shows a notice or leads to the sign in page instead of saving the sign in page as a file. A response without `code` takes the previous code path unchanged. Obliged by: SPEC-0025/FR-NEW-007, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-048, SPEC-0025/FR-NEW-074, SPEC-0025/FR-NEW-065.
- DEC-055 (SPEC-0025): Every page, message and control the mode adds is an English constant in `library/pages.py` (the exact texts are the ones quoted in the requirements and tests of each story); `static/editor-library.js` adds only `Access denied.` and `Your session has expired. Sign in again to save.`; the editor's own labels, notices and the presentations keep their texts, French ones included. Obliged by: SPEC-0025/FR-NEW-065.

### Data model

No change. Sessions are kept 24 hours after `expires_at` (purge in `Accounts.purge`, US-0128).

### Contracts

**Grant states** (`Accounts.grant_for`, DEC-037): `Live(email)` when the grant's session is alive; when the session is expired but still a row and the same address has a live session created after it (`created_at` greater) within 24 hours of the old `expires_at`, the grant is rebound (`UPDATE grants SET session_id_hash = ?`) and is `Live`; otherwise `Ended` (a cookie whose session expired, was ended by sign out, or was purged); `Absent` when there is no cookie.

**Deck route answers** for requests with `X-Editor: 1`: `Live` but no role or no presentation: `403 {"error": "Access denied.", "code": "denied"}`; `Ended` or `Absent`: `401 {"error": "Your session has expired. Sign in again to save.", "code": "session_expired"}`. Requests without the header keep the rule of US-0133: `403 Access denied.` JSON when the grant is `Live` and the role lacks the permission, `302 <library origin>/open/<pid>` when the grant is absent or ended and on the navigation routes.

**`static/editor-library.js`** additions, on `DOMContentLoaded`:
- a wrapper around `window.fetch` that records `window.__libraryCode = answer.code` of the last answer of an editor path (clone the response, read JSON when the status is 401 or 403 and the type is JSON);
- `showSaveError(text)` redefined: when `text` equals `Access denied.` or `Your session has expired. Sign in again to save.` call `showNotice('save-error', text)` (no prefix) else the original function (kept in a local variable);
- `notePollFailure()` redefined: when the last poll answer carried a `code` do nothing (no count, no `connection-lost`), else the original;
- `window.alert` wrapped: a message ending with `Access denied.` is alerted as `Access denied.` only (the export failure prefix `Export PPTX échoué : ` is dropped for coded answers);
- the click on `#download-btn` is intercepted: `fetch(base + '/download')`; `200` saves the blob under the toolbar filename; `401` with `session_expired` and no unsaved text navigates to `config.library`; with unsaved text shows `Your session has expired. Sign in again to save.`; `403` shows the alert `Access denied.`.

**Quiet screen**: a session end or a removed right with nothing unsaved produces no notice; the status poll keeps polling quietly; slide navigation inside the deck never calls the server (E2E-178).

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/static/editor-library.js` | modify | notices, quiet poll, download interception |
| `src/mcp_htmleditor/library/routes_deck.py` | modify | codes `denied`, `session_expired` |
| `src/mcp_htmleditor/library/signin.py` | modify | grant rebinding, `Ended` state |
| `tests/library_support.py` | modify | clock moves in browser tests, second window helper |
| `tests/test_library_access_e2e.py` | create | browser tests |

### Existing patterns

`tests/test_save_ui_e2e.py` for reading `#save-error`; `tests/browser_wait.py` (`wait_until`, `settle`) for absence checks; `editor-save.js:135-167` for the functions being redefined.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-010: The session ends in the middle of an edit

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-006, FR-NEW-007, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org is editing "Heart Failure Update"; he typed the title of slide 1 as "Heart Failure Update 2027" and has not left its field; his session reaches 30 days.
- **When** He leaves the edited field.
- **Then** "Your session has expired. Sign in again to save." is shown within 2 seconds of the field being left, as the only notice: "Save failed:" is not put in front of it and "Connection to the editor server lost" is not shown. The edited title and the whole presentation stay on screen.
- **And** carol.ro@example.org opens "Heart Failure Update" and sees the title "Heart Failure Update": nothing was saved.
- **And** The history of the presentation still has no new version.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-013: Signing in again in another window lets the change be stored

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** edge (side effect, state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-002, FR-NEW-007, FR-NEW-026
- **Given** dan.rw@example.org has "Heart Failure Update" open with the unsaved title "Heart Failure Update 2027" and the message "Your session has expired. Sign in again to save." on screen.
- **When** He signs in again in a second window, returns to the first window, types "!" at the end of the title and leaves the field.
- **Then** The change is stored with no notice and the expiry message disappears.
- **And** carol.ro@example.org opening the presentation sees the title "Heart Failure Update 2027!".
- **And** The history of the presentation holds the previous version with the title "Heart Failure Update".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-105: Saving into a deleted folder is refused

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** edge (side effect)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-026, FR-NEW-043, FR-NEW-048
- **Given** dan.rw@example.org is editing "Spirometry Basics" in "Pneumo Été" (he is RW there); the administrator deletes the folder.
- **When** Dan leaves the edited field.
- **Then** "Access denied." is shown as the editor's only notice; his edited text stays on screen.
- **And** No folder "Pneumo Été" and no presentation are recreated.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-116: A raised role applies on the next action

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** happy (side effect, state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-024, FR-NEW-047, FR-NEW-048
- **Given** carol.ro@example.org is viewing "Statins Review" as RO.
- **When** The administrator changes her to RW; Carol reloads.
- **Then** The edit controls appear and she changes a title and leaves the field: the change is stored.
- **And** The history of "Statins Review" lists the previous version.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-117: A removed member's change is refused

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** failure (side effect, state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-010, FR-NEW-026, FR-NEW-047, FR-NEW-048, FR-NEW-074
- **Given** dan.rw@example.org edits "Statins Review"; the administrator removes him from "Cardiology 2027" and from "Pneumo Été".
- **When** Dan leaves the edited field.
- **Then** "Access denied." is shown as the editor's only notice (no "Save failed:" in front); his edited text stays on screen.
- **And** carol.ro@example.org still sees the old text.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-118: A lowered role blocks the next stored change

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** failure (side effect, state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-023, FR-NEW-026, FR-NEW-047, FR-NEW-048
- **Given** dan.rw@example.org edits "Statins Review"; the administrator changes him to RO.
- **When** Dan leaves the edited field, then reloads.
- **Then** The first step shows "Access denied."; after the reload the editing controls are absent.
- **And** The stored text is unchanged.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-167: An ended session shows one notice, soon, and no connection notice

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** failure (side effect)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-006, FR-NEW-007
- **Given** dan.rw@example.org is editing "Heart Failure Update"; his session ended 10 seconds ago and he has typed nothing since.
- **When** He types "!" at the end of a title and waits.
- **Then** Within 2 seconds of the typing stopping, "Your session has expired. Sign in again to save." is shown; neither "Save failed:" nor "Connection to the editor server lost" appears in the following 10 seconds.
- **And** The typed "!" stays on screen; carol.ro@example.org's view is unchanged.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-170: A notice added inside the editor is in English next to French labels

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** failure
- **Scenario:** SC-007
- **Requirements:** FR-NEW-010, FR-NEW-048, FR-NEW-065
- **Given** dan.rw@example.org is editing "Statins Review"; the administrator removes him from "Cardiology 2027".
- **When** He leaves the edited field.
- **Then** The notice reads "Access denied." (English) while the toolbar still reads "Édition", "Annuler" and "Rétablir".
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-178: Moving between slides is not an action that needs the library

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** edge (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-074
- **Given** carol.ro@example.org has "Heart Failure Update" open; the administrator deletes "Cardiology 2027".
- **When** She moves from slide 1 to slide 3 with the arrow keys, then chooses the HTML download.
- **Then** The slides change with no notice; the download then shows "Access denied."
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-188: A change stored after signing in again meets the conflict notice when someone else changed the presentation

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_access_e2e.py`
- **Category:** edge (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-007, FR-NEW-027
- **Given** dan.rw@example.org has typed "Statins B" in "Statins Review" and his session ended; he signs in again in another window; meanwhile the administrator stored the title "Statins A".
- **When** Dan leaves the field in the first window.
- **Then** The notice "The file changed on disk. Reload to see the changes, or keep your version." is shown with "Keep mine" and "Reload".
- **And** Nothing of Dan's is stored until he chooses.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

## Constraints

- Local mode untouched: `editor-library.js` is not loaded there and no editor script is edited.
- The quiet screen means no notice at all, including `connection-lost`, until the person acts.
- Scope boundary: PPTX and export notices (US-0140), requests (US-0138).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (codes, notices, rebinding), `.agent_docs/html-conventions.md`.
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0137: The editor when the session or the right ends` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
