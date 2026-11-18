# US-0135: Read only editor, presenter window, full screen, hostile script isolation

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0134, US-0132
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

A person who holds only RO gets the editor screen without any control that changes the presentation (edit mode, undo, redo, notes editing, requests, Ask AI, slide and block actions; the key E does nothing) while full screen, the pointer and the presenter window with speaker notes work. A script inside a deck reads an empty cookie string and empty storage.

## Requirements covered

- SPEC-0025/FR-NEW-023: The web library mode SHALL NOT let a person who holds only RO in a folder edit, upload or delete in it: the controls are absent and any attempt made outside the interface, including the storing of a change, is refused with "Access denied." and has no effect.
  - Business rules: Absent for RO: the Upload and Delete controls, edit mode, undo, redo, notes editing, requests, slide and block actions. The key E does nothing. Reading the queued requests and the AI suggestions of a presentation is refused with "Access denied." for a person who holds only RO.
- SPEC-0025/FR-NEW-009 (partial: a direct link to a presentation followed while signed out opens it read only after sign in): WHEN a signed out visitor opens a direct link to a folder or a presentation THE web library mode SHALL show the sign in page and, after a successful sign in, show the linked page when the account has a right on it and "Access denied." when it has none.
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-022 (partial: view, full screen, presenter window with notes for a read only person): WHILE a person holds RO in a folder THE web library mode SHALL let them open its presentations, show them full screen, open the presenter window with the speaker notes, and download each presentation as HTML and as PPTX.
  - Business rules: The downloaded HTML is the stored presentation unchanged, under its own name. Only the HTML and the PPTX downloads are offered; any other export format, DOCX included, is refused with "Access denied." for everyone.
- SPEC-0025/FR-NEW-025 (partial: the same screen as the local mode without any control that changes the presentation): The web library mode SHALL give a person who can edit a presentation every option of the editor of the local mode, working as it does there.
  - Business rules: Options: edit mode, undo, redo, notes, presenter window, full screen, pointer, requests, Ask AI, HTML and PPTX download, keyboard shortcuts, help. A person who holds only RO gets the same screen without any control that changes the presentation (FR-NEW-023).
- SPEC-0025/FR-NEW-052 (partial: a deck script reads no cookie or storage entry of the library and cannot reach the library): The web library mode SHALL NOT let a script contained in a presentation read what the browser keeps for the library, act with the identity of the person viewing it, or reach another folder.
  - Business rules: The scripts still run for the presentation itself (navigation, animations), as in the local mode.
- SPEC-0025/FR-NEW-064 (partial: keyboard and labels of the read only editor): The web library mode SHALL make every action of the library pages reachable with the keyboard alone and give every control a visible label or an accessible name.
  - Business rules: none beyond the statement.

## Independent Test

Run `make test ARGS='-k "library_viewer"'`. The assertion that is not a mock: Playwright opens the deck as Carol (RO), `page.locator('#edit-mode-btn').count() == 0` visible and pressing `e` leaves `aria-pressed=false`; a probe script placed in slide 1 by the builder writes `stored:  | {} | {}` into its own element.

## Design excerpt

### Decisions

- DEC-039 (SPEC-0025): The read only form is both server and page: the server refuses every write route to a role without `EDIT` (DEC-021) and the shell route inserts, for a role without `EDIT`, a `<style>` block with `display: none !important` rules for `#edit-mode-btn`, `#undo-btn`, `#redo-btn`, `#requests-toggle`, `#ask-ai-btn`, `#notes-btn`, `#toolbar-slide-actions`, `#toolbar-doc-actions`, `#export-docx-btn`, `#requests-side`, `#ask-ai-panel`, `#notes-panel` (the editor's own CSS gives some of them `display: inline-flex`, `editor.css:620-624`, and its scripts rewrite `style.display`, so the `hidden` attribute would not hold, and no node is removed because `editor-requests.js:93` reads `#requests-side`), while `editor-library.js` registers at evaluation (it loads first) a capture phase `keydown` guard and a capture phase `message` guard that stop the key E and the deck's edit toggle message before the editor's own listeners; the editor scripts are not edited. Obliged by: SPEC-0025/FR-NEW-023, SPEC-0025/FR-NEW-025.
- DEC-045 (SPEC-0025): The deck frame keeps its sandbox attribute as is (`allow-scripts allow-same-origin allow-forms allow-fullscreen allow-popups allow-popups-to-escape-sandbox`, no `allow-top-navigation`), because on the content origin it is the editor's own contract. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-052.
- DEC-053 (SPEC-0025): Library pages use plain HTML controls (`a`, `button`, `form`, `label`, `input`, `select`, `<dialog>` for the questions) with a visible text or an `aria-label` on every control, no click handler on a non focusable element, and `library.js` moves focus into a dialog when it opens and back to the control when it closes. Obliged by: SPEC-0025/FR-NEW-064.
- DEC-055 (SPEC-0025): Every page, message and control the mode adds is an English constant in `library/pages.py` (the exact texts are the ones quoted in the requirements and tests of each story); `static/editor-library.js` adds only `Access denied.` and `Your session has expired. Sign in again to save.`; the editor's own labels, notices and the presentations keep their texts, French ones included. Obliged by: SPEC-0025/FR-NEW-065.

### Data model

No change.

### Contracts

**Shell config**: the meta of US-0133 gets `"readOnly": true` when `Library.role_in(...)` is `RO` (false for `RW` and `Admin`).

**Server side** (`routes_deck.py`, shell route of US-0134): when the role is `RO` the shell gets `"readOnly": true` in the meta and, inserted before the first `<script>`, `<style>#edit-mode-btn,#undo-btn,#redo-btn,#requests-toggle,#ask-ai-btn,#notes-btn,#toolbar-slide-actions,#toolbar-doc-actions,#export-docx-btn,#requests-side,#ask-ai-panel,#notes-panel{display:none !important}</style>`. The editor's own CSS gives some of these ids `display: inline-flex` (`editor.css:620-624`) and its scripts rewrite `style.display` (`editor.js:374-396`, `editor-undo.js:154-156`), so neither the `hidden` attribute nor an inline style holds, and no node may be removed because `editor-requests.js:93` reads `#requests-side`.

**`static/editor-library.js`** (modified): when `readOnly` is true it registers at evaluation (it loads before every editor script): a capture phase `keydown` listener on `document` that calls `preventDefault()` and `stopImmediatePropagation()` for the key `e` or `E` with no modifier, and a capture phase `message` listener on `window` that calls `stopImmediatePropagation()` for a message whose `data.type` is `deck-key` and whose `data.key` lower cased is `e` (the editor's `onShellKey` and `onDeckMessage`, `editor.js:204-240`, then never run for it). Full screen, pointer and presenter buttons stay (`#present-btn`, `#pointer-btn`, `#presenter-btn`, `#export-pptx-btn`, `#download-btn`, `#help-btn`). The labels stay as in `editor.html` (French and English mixed, FR-NEW-065); the script adds no label.

**Hostile script isolation**: nothing new on the server; the test proves it. The probe slide of the spec: `<script>document.getElementById('probe').textContent = 'stored: ' + document.cookie + ' | ' + JSON.stringify(localStorage) + ' | ' + JSON.stringify(sessionStorage);</script>` plus an element `probe`; the expected text is exactly `stored:  | {} | {}`.

**Presenter window**: opened by the deck's own `togglePresenter`; it replays the deck HTML on the content origin; the test opens it with `page.expect_popup()` and reads the current slide, next slide and notes `Welcome and objectives`.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/static/editor-library.js` | modify | read only key and message guards |
| `src/mcp_htmleditor/library/routes_deck.py` | modify | `readOnly` in the meta and the hiding style block |
| `tests/library_support.py` | modify | presenter and full screen helpers |
| `tests/test_library_viewer_e2e.py` | create | browser tests and E2E-SEC-013 (`test_exploit_*`) |

### Existing patterns

`tests/test_help_shortcuts_e2e.py` for keys in the shell and the frame; `tests/test_fullscreen_e2e.py` for full screen; `tests/test_pointer_templates_e2e.py` for the presenter; `static/editor.js:231-256` for the edit toggle message.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-021: A direct link works after signing in

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_viewer_e2e.py`
- **Category:** happy (state transition)
- **Scenario:** SC-004
- **Requirements:** FR-NEW-002, FR-NEW-009, FR-NEW-010, FR-NEW-022, FR-NEW-069
- **Given** carol.ro@example.org has no session and holds the link to "Heart Failure Update" in "Cardiology 2027".
- **When** She opens the link and completes the Google sign in.
- **Then** "Heart Failure Update" is shown to her, in the read only form.
- **And** She is not asked to go through the home page first.
- **And** The page shown for an allowed target carries no "Access denied."
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the direct link of a presentation is `/open/<presentation id>` on the library origin (DEC-020).

### SPEC-0025/E2E-030: A RO member views and presents

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_viewer_e2e.py`
- **Category:** happy
- **Scenario:** SC-005
- **Requirements:** FR-NEW-022, FR-NEW-023, FR-NEW-025, FR-NEW-052, FR-NEW-064
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; slide 1 of "Heart Failure Update" is titled "Heart Failure Update" and carries the speaker notes "Welcome and objectives"; slide 2 is titled "Epidemiology".
- **When** She opens "Heart Failure Update", enters full screen with the key F, then opens the presenter window with the key S.
- **Then** Full screen shows slide 1. The presenter window shows slide 1 with its title "Heart Failure Update", slide 2 "Epidemiology" as the next slide preview, the notes "Welcome and objectives", the slide counter and the timer; the arrow keys move both windows.
- **And** Every control she used is reachable and named for the keyboard.
- **And** The presentation's own navigation and animations work as in the local mode.
- **And** No Upload, Delete or edit mode control was shown.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-032: A RO member has no control that changes anything

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_viewer_e2e.py`
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-023, FR-NEW-025, FR-NEW-064
- **Given** carol.ro@example.org is RO in "Cardiology 2027".
- **When** She opens the folder page, then "Statins Review", and presses the key E.
- **Then** The folder page has no Upload and no Delete; the presentation shows no edit mode, undo, redo, notes editing, requests or slide actions; the key E does nothing.
- **And** The controls that exist are: navigation, full screen, pointer, presenter window, HTML and PPTX download, help.
- **And** Each control that exists is reachable with the keyboard and has a label.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-109: The administrator changes a role and removes a member

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_viewer_e2e.py`
- **Category:** happy (side effect, state transition)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-047, FR-NEW-048, FR-NEW-049
- **Given** "Cardiology 2027" has dan.rw@example.org RW and carol.ro@example.org RO.
- **When** The administrator changes Carol to RW, then removes Dan.
- **Then** Carol's next action shows the edit controls; Dan's next action is refused with "Access denied."
- **And** The activity list gains "Changed carol.ro@example.org to RW in "Cardiology 2027"" and "Removed dan.rw@example.org from "Cardiology 2027"".
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-121: An open presenter window keeps what it loaded

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_viewer_e2e.py`
- **Category:** edge (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-022, FR-NEW-048
- **Given** carol.ro@example.org has the presenter window open on "Heart Failure Update"; the administrator removes her.
- **When** She moves through the 8 slides, then reloads the window.
- **Then** The slides already loaded still change; the reload shows "Access denied."
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-180: Library controls per page

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_viewer_e2e.py`
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-008, FR-NEW-067
- **Given** seb.morand@gmail.com is signed in.
- **When** He opens the home page, the folder page of "Cardiology 2027", "Administration", a presentation, then presses the Back button of the browser.
- **Then** The home page and the folder page show "Sign out"; the folder page also shows "All folders"; the administration shows "All folders" and "Sign out"; the presentation shows no library control of its own; Back returns to the folder page.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-013: A presentation's script cannot read what the browser keeps for the library

- Level / Driver / Location: exploit / Playwright / `tests/test_library_viewer_e2e.py`
- **Category:** security
- **Covers:** Class C occurrences #1, #2, #5
- **Red before the fix because:** the script reads the identity data kept for the library; the assertion "the slide shows no email address" fails and shows carol.ro@example.org.
- **Scenario:** SC-018
- **Requirements:** FR-NEW-021, FR-NEW-052, FR-NEW-053
- **Given** "Cardiology 2027" holds the presentation "Heart Failure Update" whose slide 1 carries this script: <script>document.getElementById('probe').textContent = 'stored: ' + document.cookie + ' | ' + JSON.stringify(localStorage) + ' | ' + JSON.stringify(sessionStorage);</script> and an element with the identifier "probe"; carol.ro@example.org is signed in.
- **When** Carol opens "Heart Failure Update" and shows slide 1.
- **Then** The element "probe" reads "stored:  | {} | {}": nothing about her, no email address, no sign in information, no folder name.
- **And** The administrator, who also opens the slide, sees the same: the text "carol.ro@example.org" and "seb.morand@gmail.com" appear nowhere on the slide.
- **And** Carol is still signed in as herself and her pages work normally.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

## Constraints

- Do not edit `editor.js` or `editor.html`; the read only form is applied by the library script.
- The server check (US-0136) is the control; hiding is usability only.
- Scope boundary: notices (US-0137), saving (US-0136).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (read only form), `.agent_docs/html-conventions.md`.
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0135: Read only editor, presenter window, full screen, hostile script isolation` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
