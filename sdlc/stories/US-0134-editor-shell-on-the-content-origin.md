# US-0134: The editor shell opens on the content origin

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0133
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

The content origin serves the editor shell of the local mode, scoped to one presentation: `static/editor.html` with its frame and download address prefixed by `/d/<pid>`, plus one new classic script that prefixes the editor's own requests, so the full editor opens on a library presentation without any edit of the editor scripts. The local mode still edits one file with no sign in.

## Requirements covered

- SPEC-0025/FR-NEW-025 (partial: the editor screen, toolbar, status poll and deck frame of the local mode work for a viewer): The web library mode SHALL give a person who can edit a presentation every option of the editor of the local mode, working as it does there.
  - Business rules: Options: edit mode, undo, redo, notes, presenter window, full screen, pointer, requests, Ask AI, HTML and PPTX download, keyboard shortcuts, help. A person who holds only RO gets the same screen without any control that changes the presentation (FR-NEW-023).
- SPEC-0025/FR-NEW-052 (partial: the shell and the deck run on the content origin that holds no library session): The web library mode SHALL NOT let a script contained in a presentation read what the browser keeps for the library, act with the identity of the person viewing it, or reach another folder.
  - Business rules: The scripts still run for the presentation itself (navigation, animations), as in the local mode.
- SPEC-0025/FR-NEW-055 (partial: the local mode guards (one local file, no sign in, scripts as before) stay green after the library editor shell exists): The local mode SHALL keep every behavior it had before this increment.
  - Business rules: One local file at a time, the same editor, the same options, the same address rules. The web library mode running on the same machine changes nothing in it.
- SPEC-0025/FR-NEW-056 (partial: the local mode never shows a sign in or a library page): The local mode SHALL NOT ask for a sign in or show any library page.
  - Business rules: none beyond the statement.

## Independent Test

Run `make test ARGS='-k "library_shell"'`. Playwright signs in as Carol (RO), clicks the presentation, and `#content-frame` shows slide 1 with the toolbar filename `Heart Failure Update.html`; the deck's embedded pictures are displayed (`naturalWidth > 0`). The assertion that is not a mock: a `difflib` comparison of the served shell and `static/editor.html` shows exactly three differences (frame `src`, download `href`, the inserted meta and script).

## Design excerpt

### Decisions

- DEC-007 (SPEC-0025): Serve two origins from one listener: the library origin (pages, API, session) and the content origin (the editor shell, the deck frame and the routes of one presentation); the `Host` header must equal the netloc of one of the two configured origins, otherwise `403 {"error": "forbidden host"}`. Obliged by: SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-059, SPEC-0025/FR-NEW-057.
- DEC-038 (SPEC-0025): The library shell is `static/editor.html` served with three server side edits (the frame `src` and the download `href` get the base `/d/<pid>`; a `<meta name="editor-config">` and `<script src="/static/editor-library.js">` are inserted before the first script) and one new classic script, `static/editor-library.js`, which wraps `window.fetch` to prefix the base on the eight editor paths and redefines `reloadFrame` (the one editor function that assigns an absolute path to the frame, `editor.js:475-477`); no existing editor script, template or the file `editor.html` itself is edited. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-055.
- DEC-045 (SPEC-0025): The deck frame keeps its sandbox attribute as is (`allow-scripts allow-same-origin allow-forms allow-fullscreen allow-popups allow-popups-to-escape-sandbox`, no `allow-top-navigation`), because on the content origin it is the editor's own contract. Obliged by: SPEC-0025/FR-NEW-025, SPEC-0025/FR-NEW-052.
- DEC-055 (SPEC-0025): Every page, message and control the mode adds is an English constant in `library/pages.py` (the exact texts are the ones quoted in the requirements and tests of each story); `static/editor-library.js` adds only `Access denied.` and `Your session has expired. Sign in again to save.`; the editor's own labels, notices and the presentations keep their texts, French ones included. Obliged by: SPEC-0025/FR-NEW-065.

### Data model

No change.

### Contracts

**Shell route** `GET /d/<pid>/` (`VIEW`, content origin; failure is `302 <library origin>/open/<pid>`): the bytes of `static/editor.html` (`http_server.py:_static_dir()`) with exactly these edits applied by string replacement: `src="/content-frame"` becomes `src="/d/<pid>/content-frame"`; `href="/download"` becomes `href="/d/<pid>/download"`; and the text `<meta name="editor-config" content='<json>'><script src="/static/editor-library.js"></script>` is inserted right before the first `<script src=` (the JSON is `{"base":"/d/<pid>","readOnly":false,"library":"<library origin>"}` passed through `html.escape(..., quote=True)`). Headers: `Content-Security-Policy: frame-ancestors 'none'`, `X-Frame-Options: DENY`, no store. `GET /static/<name>` on the content origin serves `static/` files by base name (inherited `_serve_static`, `http_server.py:341-351`) to anyone: they are product code, no library content; `GET /static/editor-library.js` is one of them.

**`static/editor-library.js`** (new, classic script, no module, loaded only by this shell, first of the scripts, the whole file inside an immediately invoked function so it adds no global name): reads the meta `editor-config`; wraps `window.fetch` as an async function so a string URL equal to one of `/content`, `/status`, `/requests`, `/requests/delete`, `/review/apply`, `/arch-layout`, `/export/pptx`, `/download` (query string allowed) is requested as `base + url` with the extra request header `X-Editor: 1`, and, for a 401 or 403 answer, awaits `response.clone().json()` and stores its `code` in `window.__libraryCode` before returning the response (US-0137 uses it); every other `fetch` is untouched; on `DOMContentLoaded` redefines `window.reloadFrame = function () { document.getElementById('content-frame').src = base + '/content-frame?' + Date.now(); }` (`editor.js:475-477` assigns the absolute path `/content-frame?...` to the frame, so without this every reload after another writer's save, `Reload` of the conflict notice or an undo would blank the deck). The folder page link to a presentation is `/open/<pid>` (US-0129 already lists names; this story makes the name a link `<a href="/open/<pid>">`).

**Local mode**: nothing of `editor.html`, `editor*.js` or the templates changes; `editor-library.js` is never referenced by them. E2E-133 and E2E-137 (the local mode edits one file; a local deck's script reads storage as before) are the guards, written here against the unmodified local server and kept green.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/static/editor-library.js` | create | fetch wrapper |
| `src/mcp_htmleditor/library/routes_deck.py` | modify | shell route, static assets |
| `src/mcp_htmleditor/library/pages.py` | modify | presentation names are links in the folder page |
| `tests/library_support.py` | modify | browser helpers: sign in, open, frame access |
| `tests/test_library_shell_e2e.py` | create | E2E-045 and the two local mode guards E2E-133, E2E-137 |

### Existing patterns

`tests/test_toolbar_icons_e2e.py` and `tests/test_save_safety_e2e.py` for Playwright against the editor shell; `tests/conftest.py:245-270` for serving a local deck (the local guards).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-045: A deck with embedded pictures displays them

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_shell_e2e.py`
- **Category:** edge
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-054
- **Given** "From Challenges to Change" (3 901 499 bytes, 18 slides, pictures embedded) is in "WCBIP Melbourne Décembre 2026".
- **When** lamya.chrif@gmail.com opens it and goes through the 18 slides.
- **Then** Every picture is displayed; no slide shows a broken picture.
- **Priority:** Medium
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-133: The local mode edits one file with no sign in

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_shell_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-021
- **Requirements:** FR-NEW-025, FR-NEW-055, FR-NEW-056
- **Given** An operator runs the local mode on talk.html, a presentation of 3 slides on their machine.
- **When** They open the editor, change the title of slide 1 to "Hello" (stored by itself), undo, open the presenter window and download the PPTX.
- **Then** No sign in is asked; everything works as in the previous version; the file talk.html holds "Hello".
- **And** The history of talk.html holds the previous version.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: regression guard written first and green from the first story; it must stay green and unmodified after every later story that touches `http_server.py`.

### SPEC-0025/E2E-137: A local deck's script behaves as before

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_shell_e2e.py`
- **Category:** edge
- **Scenario:** SC-021
- **Requirements:** FR-NEW-052, FR-NEW-055
- **Given** talk.html carries a script that reads what the browser keeps for the local address.
- **When** The operator opens it in the local mode.
- **Then** The script works exactly as in the previous version.
- **Priority:** Low
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: regression guard written first and green from the first story; it must stay green and unmodified after every later story that touches `http_server.py` or the editor shell.

### Story tests (not spec tests)

`tests/test_library_shell_e2e.py` also holds the `difflib` test of the three differences, a test that the folder page link reaches the shell through the redirects, and a browser test where a second person saves a change and the first person's open editor reloads the frame (the new title is visible: `reloadFrame` works through the redefinition).

## Constraints

- Do not edit `editor.html`, any `editor*.js` or any template; the shell text is derived at serve time.
- `editor-library.js` wraps `fetch` and redefines `reloadFrame` only; it reads no cookie and stores nothing in `localStorage` or `sessionStorage`.
- Scope boundary: read only controls (US-0135), notices (US-0137), PPTX download behavior (US-0140).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (the shell and its script), `.agent_docs/html-conventions.md` (the library shell derivation).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0134: The editor shell opens on the content origin` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
