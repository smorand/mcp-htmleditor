# US-0140: Download the presentation as PPTX without running its scripts

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0137, US-0138, US-0139
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

A person with a right downloads the presentation as PPTX built by the flow engine from the stored file: no Chromium, no script of the deck is executed on the machine, and a picture is taken only from a data URI of the presentation; a refused or failed download shows the right text and no file.

## Requirements covered

- SPEC-0025/FR-NEW-010 (partial: a refused or failed download or export shows `Access denied.` alone or the operating system reason without path or file name; a lost session gives the sign in page): IF a link points to a folder or a presentation that does not exist, no longer exists, or belongs to a folder where the person holds no role THEN THE web library mode SHALL show exactly "Access denied." and nothing else.
  - Business rules: The page is identical in wording and content in the three cases; it shows the text "Access denied." and the "Sign out" button, nothing else: it never names the folder or the presentation and never says whether it exists. The same holds for an action refused for these reasons (storing a change, download, delete, upload). When the refusal reaches a presentation open for editing, the editor shows "Access denied." as its only notice (no "Save failed:" prefix) and keeps the unsaved changes on screen. An address of the product that names no page, asked by a signed in person, gives exactly "Access denied." with the "Sign out" button. A refused download or export shows "Access denied." as its only text, with no prefix such as "Export PPTX échoué :"; no file is received and the presentation stays on screen. When the session ended, the person gets the sign in page, unless they have unsaved text: then FR-NEW-007 applies and no download happens. Any other failure of a download or export shows the editor's usual failure notice with the operating system reason, without any file name or path, never the text of an exception.
- SPEC-0025/FR-NEW-022 (partial: a person with RO downloads the presentation as PPTX): WHILE a person holds RO in a folder THE web library mode SHALL let them open its presentations, show them full screen, open the presenter window with the speaker notes, and download each presentation as HTML and as PPTX.
  - Business rules: The downloaded HTML is the stored presentation unchanged, under its own name. Only the HTML and the PPTX downloads are offered; any other export format, DOCX included, is refused with "Access denied." for everyone.
- SPEC-0025/FR-NEW-052 (partial: the PPTX build runs no script and reads no file outside the presentation): The web library mode SHALL NOT let a script contained in a presentation read what the browser keeps for the library, act with the identity of the person viewing it, or reach another folder.
  - Business rules: The scripts still run for the presentation itself (navigation, animations), as in the local mode.

## Independent Test

Run `make test ARGS='-k library_pptx'`. The assertion that is not a mock: for the deck carrying `new WebSocket(ws://127.0.0.1:9/probe)`, `<img src="file:///.../secret.png">` and `<img src="../secret.png">`, a socket listening on loopback port 9 counts 0 connections and the media parts of the downloaded PPTX contain no byte sequence equal to `secret.png`.

## Design excerpt

### Decisions

- DEC-003 (SPEC-0025): Reuse the editor routes through five overridable methods of `_EditorHandler` (`_served_file`, `_served_name`, `_save_lock`, `_failure_reason`, `_pptx_options`; `_save_lock` returns a context manager, the local one is the existing `threading.Lock`), give `_EditorServer.__init__` a `handler` parameter defaulting to `_EditorHandler`, and implement the library as `LibraryHandler(_EditorHandler)` that overrides `do_GET`, `do_POST` and `_serve_status` only. The defaults reproduce the previous expressions byte for byte. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-055.
- DEC-040 (SPEC-0025): Deck route failures carry a `code` (`denied` or `session_expired`) only for requests that carry the header `X-Editor: 1`, which `editor-library.js` adds to every `fetch` it wraps; a request without it gets `403` `Access denied.` JSON when the grant is live and the role lacks the permission (so a hand made write or read by a RO person is refused with the text the tests expect), and `302 <library origin>/open/<pid>` when the grant is absent or ended or the route is a navigation route (`/d/<pid>/`, `/content-frame`, `/download`, `/export/pptx`), so a visitor or a copied session sees the sign in page and never a file. When a response has `code`, `editor-library.js` (which redefines the global functions `showSaveError`, `notePollFailure` and wraps `alert`, all plain global bindings the editor scripts call at run time) makes the editor show `answer.error` alone (no `Save failed:` prefix, no `Export <FORMAT> échoué :` prefix) as the notice or alert; `session_expired` with nothing unsaved is silent (no notice, no failure count) and the next download or export navigates to the library origin; the status poll treats such an answer as a quiet pause: it does not count toward the three failures of the lost connection notice; the click of `#download-btn` (an `<a href download>` in the editor) is intercepted and sent with `fetch`, so a download refused or cut by the end of the session shows a notice or leads to the sign in page instead of saving the sign in page as a file. A response without `code` takes the previous code path unchanged. Obliged by: SPEC-0025/FR-NEW-007, SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-048, SPEC-0025/FR-NEW-074, SPEC-0025/FR-NEW-065.
- DEC-042 (SPEC-0025): Failures of a download or export in the library answer `{"error": <operating system reason>}` through `_failure_reason` (`exc.strerror`, else a fixed `Export failed`), never `str(exc)`. Obliged by: SPEC-0025/FR-NEW-010, SPEC-0025/FR-NEW-020.
- DEC-043 (SPEC-0025): The library PPTX download calls `to_pptx(path, out, paint=False, embedded_pictures_only=True)`: the flow engine only (no Chromium in the image, no script of the deck ever executed on the machine) and a picture is read only from a `data:` URI; any other `src` is skipped with a report warning. The painted path gets the same flag. Obliged by: SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-022.
- DEC-044 (SPEC-0025): Routes that must not exist in the library: DOCX export (`/d/<pid>/export/docx` is `Access denied.` for every role), the picture render, `new_file`, every MCP tool, `/arch-layout` on the library origin. Obliged by: SPEC-0025/FR-NEW-022, SPEC-0025/FR-NEW-052.
- DEC-045 (SPEC-0025): The deck frame keeps its sandbox attribute as is (`allow-scripts allow-same-origin allow-forms allow-fullscreen allow-popups allow-popups-to-escape-sandbox`, no `allow-top-navigation`), because on the content origin it is the editor's own contract. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-052.

### Data model

No change.

### Contracts

**Route**: `GET /d/<pid>/export/pptx` (`VIEW`, content origin): the inherited `_export_pptx` (`http_server.py:432`) with `self._pptx_options()` returning `{"paint": False, "embedded_pictures_only": True}` in `LibraryHandler` (the flag exists since US-0139); the attachment name is `<name>.pptx` from `_served_name()`; failures answer `{"error": self._failure_reason(exc)}` (`exc.strerror` or `Export failed`, never a path). `GET /d/<pid>/export/docx` stays `403` `Access denied.` for every role (DEC-044).

**`static/editor-library.js`** additions: the PPTX button (`triggerExport`, `editor.js:405-430`) already uses `fetch('/export/pptx')`, which the wrapper prefixes and marks with `X-Editor: 1`; a coded answer (`denied`, `session_expired`) shows `Access denied.` alone for `denied` (the wrapper of `window.alert` drops the prefix `Export PPTX échoué : ` when the message ends with a library text); for `session_expired` with nothing unsaved the page navigates to `config.library`; with unsaved text the notice `Your session has expired. Sign in again to save.` is shown and no download happens. The HTML download button is intercepted the same way: a click runs `fetch(base + '/download')`; `200` saves the blob under the toolbar filename; the coded answers are handled as for the export.

**Failure texts**: a PPTX build failure for an unreadable stored file answers `500 {"error": "<operating system reason>"}` (for example `No such file or directory`), never a path or a file name.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/routes_deck.py` | modify | `export/pptx` row, options, docx refusal |
| `src/mcp_htmleditor/static/editor-library.js` | modify | download and export interception |
| `tests/library_support.py` | modify | hostile deck builders, loopback listener |
| `tests/test_library_pptx_http.py` | create | E2E-031 and E2E-SEC-012, E2E-SEC-022 (`test_exploit_*`) |
| `tests/test_library_pptx_e2e.py` | create | E2E-119, E2E-173, E2E-177 |

### Existing patterns

`tests/test_http_export.py` for the route; `tests/test_toolbar_icons_e2e.py:75-163` for the download button in a browser; `tests/test_library_open_http.py` (US-0133) for the library client.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-031: A RO member downloads the HTML and the PPTX

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_pptx_http.py`
- **Category:** happy (side effect)
- **Scenario:** SC-005
- **Requirements:** FR-NEW-022, FR-NEW-025
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; "Heart Failure Update" has 8 slides and is 2 097 152 bytes.
- **When** She chooses the HTML download, then the PPTX download.
- **Then** She receives "Heart Failure Update.html" of 2 097 152 bytes identical to the stored presentation, and a PPTX of 8 slides.
- **And** The stored presentation and its history are unchanged.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-042: Every option of the local editor is present

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_pptx_e2e.py`
- **Category:** happy
- **Scenario:** SC-007
- **Requirements:** FR-NEW-024, FR-NEW-025
- **Given** dan.rw@example.org has "Heart Failure Update" open.
- **When** He looks at the toolbar and tries each option.
- **Then** The toolbar shows, with the labels of the local mode: "Édition", "Annuler", "Rétablir", "Mode présentation plein écran", "Présenter avec le pointeur", "Vue présentateur", "Notes", "Requests", "Ask AI", "Télécharger en PPTX", "Télécharger le fichier HTML" and "Raccourcis clavier"; the keys F, P, S, E and ? work as in the local mode.
- **And** The notes panel for slide 1 accepts "Mention the 2026 guideline" and the open presenter window shows that text.
- **And** The labels are not translated into English; every notice that the library mode adds in the editor is in English.
- **And** A DOCX export requested by hand by dan.rw@example.org (RW) is refused with "Access denied." and no file is received, as for everyone.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-119: A download after the folder was deleted is refused

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_pptx_e2e.py`
- **Category:** failure (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-010, FR-NEW-022, FR-NEW-048
- **Given** carol.ro@example.org views "Heart Failure Update"; the administrator deletes "Cardiology 2027".
- **When** She chooses the PPTX download.
- **Then** "Access denied." is shown as the only text, with no "Export PPTX échoué :" in front of it, and no file is received.
- **And** The slide on her screen is still displayed.
- **And** The presentation stays on screen.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-173: A session that ended gives a quiet screen until the person acts

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_pptx_e2e.py`
- **Category:** happy (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-007, FR-NEW-048, FR-NEW-074
- **Given** dan.rw@example.org has "Heart Failure Update" open in edit mode and has typed nothing; his session reaches 30 days.
- **When** He waits 60 seconds without touching anything.
- **Then** The presentation stays on screen with no notice at all: neither "Your session has expired. Sign in again to save." nor "Connection to the editor server lost".
- **And** He chooses the HTML download: the sign in page is shown, and nothing was stored.
- **And** In a variant where he has typed "!" unstored, the PPTX download is not made and "Your session has expired. Sign in again to save." is shown; with nothing unstored, choosing the PPTX download shows the sign in page and no file is received.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the HTML download of the editor is intercepted by `editor-library.js` and sent with `fetch`, so a refusal can be shown as a notice or a navigation (DEC-040); the PPTX variant needs US-0140, which is why this test sits there.

### SPEC-0025/E2E-177: A removed right gives a quiet screen, then Access denied on the next action

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_pptx_e2e.py`
- **Category:** failure (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-010, FR-NEW-048, FR-NEW-074
- **Given** dan.rw@example.org has "Statins Review" open in edit mode and has typed nothing; the administrator removes him from "Cardiology 2027".
- **When** He waits 60 seconds, then chooses the PPTX download.
- **Then** The screen stays quiet for the 60 seconds (no notice); the download then shows "Access denied." and no file is received.
- **And** The presentation was never altered and carol.ro@example.org still sees it unchanged.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: same mechanism as the quiet screen test; the final PPTX step needs US-0140.

### SPEC-0025/E2E-SEC-012: A visitor without a session cannot download a presentation

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_pptx_http.py`
- **Category:** security
- **Covers:** Class B occurrences #2 and #5
- **Red before the fix because:** a naive build that serves the stored file to anyone knowing the address fails the assertion "the visitor's download folder holds no file": it holds Heart Failure Update.html of 2 097 152 bytes.
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-020, FR-NEW-022
- **Given** A visitor with no session who knows the exact download addresses of "Heart Failure Update" in "Cardiology 2027", HTML and PPTX, copied from carol.ro@example.org's earlier session.
- **When** The visitor requests the HTML download address, then the PPTX download address, with no sign in.
- **Then** Each answer is the sign in page, never a file.
- **And** The visitor's download folder holds no file, and the text "Heart Failure Update" appears in nothing the visitor received.
- **And** The administrator's view of "Cardiology 2027" is unchanged: 3 presentations.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-SEC-022: A presentation's script reaches the machine while its PPTX is built

- Level / Driver / Location: exploit / HTTP client / `tests/test_library_pptx_http.py`
- **Category:** security
- **Covers:** Class C occurrence #6 and Class A occurrences #8 and #9
- **Red before the fix because:** the PPTX is built from files outside the folder and the WebSocket is not aborted; the assertion "the PPTX holds no picture equal to secret.png" fails because the delivered PPTX contains secret.png.
- **Scenario:** SC-018
- **Requirements:** FR-NEW-020, FR-NEW-022, FR-NEW-052
- **Given** "Cardiology 2027" holds the presentation "Heart Failure Update" whose slide 1 carries <script>new WebSocket('ws://127.0.0.1:9/probe');</script>, <img src="file:///<fixture dir>/secret.png"> and <img src="../secret.png">; secret.png is a real PNG picture stored in the fixture directory, outside every folder of the library; a listener on the machine's loopback port 9 records every connection; carol.ro@example.org is RO.
- **When** Carol chooses the PPTX download.
- **Then** The PPTX is delivered with its slides.
- **And** The listener recorded 0 connections.
- **And** The PPTX holds no picture equal to secret.png.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

## Constraints

- No Chromium or Playwright import in `library/`.
- DOCX is never offered.
- Scope boundary: the exporter flag itself (US-0139).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (PPTX in the library), `.agent_docs/pptx-fidelity.md` (the library uses the flow output).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0140: Download the presentation as PPTX without running its scripts` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
