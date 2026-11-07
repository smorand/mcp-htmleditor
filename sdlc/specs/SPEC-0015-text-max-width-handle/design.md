# SPEC-0015: Text width bar in the editor, design

> Spec: sdlc/specs/SPEC-0015-text-max-width-handle/spec.md
> Nature: FEAT
> Depth: M
> Security: n/a
> Designed on: 2026-11-07
> Target tier: 2 (user instruction for this run: tier 2 by default, stories with silent pitfalls at `min_tier` 1; no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

Run mode: unattended (the user asked for no questions and the recommended defaults). No new dependency, no new
route, no new setting, no data format change: the only new output is the inline declaration the spec imposes
(`max-width:Npx`, spec 3.3).

Project state: existing (`ls src/mcp_htmleditor/static` lists the twelve editor scripts; `git log --oneline -1` is
`32653e0`).

Counts (by command on `spec.md`): 15 functional requirements (`FR-NEW-001` to `FR-NEW-015`), 3 non functional
(`NFR-001` to `NFR-003`), 43 acceptance tests (`E2E-001` to `E2E-043`), 5 scenarios (`SC-001` to `SC-005`).

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| Editor (browser) | classic scripts without build step, loaded in the order of `static/editor.html` (`editor.html:108` to `:119`) | n/a | existing, DEC-001 |
| Server save | `POST /content`, whole file, base mtime conflict check (SPEC-0009), stripping by `_strip_editor_artifacts` (`http_server.py:52`, `:854`) | n/a | existing, DEC-009 |
| Browser tests | pytest 9.1.1, pytest-playwright (Chromium), `tests/browser_wait.py` (SPEC-0014) | as locked | existing, DEC-011 |
| Agent read and lint | `deck.read.get_slide` (`deck/read.py:33`), `deck.lint.lint_file` (`deck/lint.py:96`) | n/a | existing, unchanged |
| Skill size audit | `skill_content.TOPIC_BUDGET_BYTES = 8000`, `CORE_BUDGET_BYTES = 7000` (`skill_content.py:46`) | n/a | existing |

Skills loaded: `python` (via `load_dynamic_context`, injected for this run). Effect: `make check` is the gate
(check-generated, lint, format-check, typecheck strict, bandit, coverage 80 %); tests run through `make test` only
(`make test ARGS='-k width'`); no `print`, `%` logging, constants at the top of modules. Project conventions applied:
`AGENTS.md` (JS checked with `node --check`, browser waits rule, editor script order), `.agent_docs/html-conventions.md`
(editor artifacts, undo), `.agent_docs/architecture.md` (browser side), `.agent_docs/testing.md` (pacing rule,
`browser_wait`, 330 s run time), `sdlc/constitution.md`.

## 2. Approaches

### Chosen: the bar lives in the editor shell, over the frame; the width is written as attribute text

The bar is one element of the parent page (`static/editor.html`), positioned over the iframe at the right edge of the
pointed text block. Pointer and keyboard events are handled in the shell; hovering is detected by a `pointermove`
listener on the framed document. During a drag the text is previewed through `el.style` and that preview is taken
out around every serialization of the framed document (save clone, undo snapshot). The saved value is rebuilt as
text from the attribute as it was before the drag and written with `setAttribute('style', ...)`.

- Pros: nothing of the bar can ever reach the file (it is not in the framed document), so the two strippers and the
  undo snapshot need no new entry (FR-NEW-010, NFR-003); the slide template's own arrow key navigation never sees
  the bar's keys (they are typed in the shell); the fullscreen presentation hides the shell by construction
  (FR-NEW-003); colours and spacing of the other declarations are never normalized (FR-NEW-012, E2E-006).
- Cons and risks: coordinates must be translated from the frame to the shell (frame rect plus block rect); hover
  leaves the frame when the pointer reaches the bar (handled by the bar's own pointer events). Risk R1 (section 7):
  any new code path that serializes the framed document must go through the preview suspension.
- Affected scope: `static/editor-width.js` (new), `static/editor.html`, `static/editor.css`, `static/editor-edit.js`,
  `static/editor-save.js`, `static/editor-undo.js`, `static/editor.js`; tests; skill topics `create` and `export`;
  documentation.
- Best suited when: the control is editor chrome over arbitrary documents, as here.

### Rejected: the bar inside the framed document (as the source product and the drag handles do)

Summary: inject the bar node into the iframe next to the drag handles. Rejected (DEC-001): it adds an artifact to the
browser clone strip (`editor-save.js:24` to `:31`), the server strip (`_EDITOR_ARTIFACTS`, `http_server.py:52`) and
the undo snapshot cleanup (`editor-undo.js:27` to `:56`); the slide template's keydown handlers on the framed
document would turn Right and Left into slide changes; any forgotten path writes the bar into the file (spec 14.3,
E2E-017).

### Rejected: preview and save through the element's style object

Summary: `el.style.maxWidth = '650px'` and let the normal save serialize it. Rejected (DEC-003): measured in Chromium
(`/tmp/spec15/probe.py`, this run), setting one property rewrites the whole attribute:
`color:#0F62FE;font-weight:600` becomes `color: rgb(15, 98, 254); font-weight: 600; max-width: 650px;` and
`background:url(data:image/png;base64,AAA)` becomes `background: url("data:image/png;base64,AAA")`. That breaks
FR-NEW-005, FR-NEW-012 and the lint palette check (E2E-006, E2E-028, E2E-042).

### Rejected: a dedicated width route on the server (as the source's `/api/width`)

Summary: post the text's identity and width to a new route that edits the file. Rejected (DEC-009): the editor saves
the whole file; a second write path would race the autosave and bypass the SPEC-0009 base mtime check that E2E-026
relies on (spec 14.3).

## 3. Architecture

```
 shell page (editor.html)                                   framed document (iframe, the user's file)
 ┌──────────────────────────────────────────────┐          ┌────────────────────────────────────────────┐
 │ #width-bar  role=separator tabindex=0         │          │ [data-editable~="text"] zones, typeable     │
 │   #width-readout  "650 px" while dragging     │◄─hover───│ pointermove listener (attached in           │
 │ pointerdown/move/up/cancel, dblclick, keydown │          │ injectEditMode, removed in removeEditMode)  │
 └───────────────┬──────────────────────────────┘          └────────────────────────────────────────────┘
                 │ editor-width.js
                 ├─ widthBlockAt(target)          FR-NEW-002, FR-NEW-003: text block or null
                 ├─ widthBarShow/Hide/Reposition  FR-NEW-001: right edge, frame rect + block rect, clamped in window
                 ├─ drag: preview el.style.setProperty('max-width', v+'px')   FR-NEW-004
                 ├─ commit(newText):  restore original attribute text
                 │                    -> snapshotForUndo()            (editor-undo.js, pre mutation, FR-NEW-009)
                 │                    -> setAttribute/removeAttribute('style')     FR-NEW-005, FR-NEW-007
                 │                    -> markPending(); saveContent() (editor-save.js, FR-NEW-013)
                 ├─ cancel():         restore original attribute text, nothing saved   FR-NEW-011
                 └─ withWidthPreviewSuspended(fn)  original text back during fn, preview after (FR-NEW-010)
                        used by runSave (clone) and captureDomSnapshot (outerHTML)

 editor.js   onFrameLoad -> widthBarOnFrameLoad(): cancel the drag, hide (reload, undo restore, agent write)
             pollStatus  -> update overlay shown: cancel and hide; an active drag counts as a local change,
                            so an external write does not reload the frame (the release save gets the 409)
 server      unchanged: POST /content, strip, base mtime conflict
```

Bounded contexts: browser editing (the bar, its save and undo) and agent guidance (two topic lines). No Python
product module changes. The agent read and lint paths are unchanged and proved by tests (FR-NEW-014).

## 4. Data model

No persisted data change. The saved file gains, on a text the author sized, the inline declaration `max-width:Npx`
(spec 3.3), N a whole number between 80 and 1280. In memory (shell page, `editor-width.js`):

| Name | Type | Meaning |
|---|---|---|
| `widthBlock` | `Element \| null` | text block the bar is shown on |
| `widthDrag` | `null \| {block, originalStyle, startWidth, startX, ratio, value, moved, pointerId}` | the drag in progress; `originalStyle` is the attribute text or `null` when absent |
| constants | `WIDTH_MIN = 80`, `WIDTH_MAX = 1280`, `WIDTH_STEP = 10`, `WIDTH_KEY_STEP = 10`, `WIDTH_KEY_STEP_LARGE = 50` | FR-NEW-004, FR-NEW-006 |

Undo snapshots are the existing whole document strings (`editor-undo.js:27`); a width change adds one, no new field.

## 5. Contracts and interfaces

### 5.1 Shell markup (`static/editor.html`, inside `<body>`, after the frame)

```html
<div id="width-bar" role="separator" aria-orientation="vertical" aria-label="Largeur du texte"
     title="Glisser pour régler la largeur, double clic pour revenir à la largeur du modèle" tabindex="0" hidden>
  <span id="width-readout" hidden></span>
</div>
```

The readout reads `${N} px` (number, one space, `px`) while a drag is in progress and is hidden otherwise
(FR-NEW-004). The bar shows a visible outline whenever it has the focus, mouse click included: the CSS rule is
`#width-bar:focus` (not `:focus-visible`, which Chromium does not apply after a mouse click) (NFR-002).

### 5.2 Style text functions (`static/editor-width.js`, pure, no DOM)

```js
/** Trimmed non empty declarations; a ';' inside (...), '...' or "..." (backslash escapes honoured) is not a separator. */
function splitStyleDeclarations(text)            // (string|null) -> string[]
/** Property name of one declaration: text before its first ':', trimmed, lower case. */
function styleDeclarationName(declaration)       // string -> string
/** True when the text holds a max-width declaration, whatever its unit. */
function styleHasWidth(text)                     // (string|null) -> boolean
/** Others kept verbatim and in order, every max-width dropped, `max-width:${px}px` appended, joined with '; '. */
function styleWithWidth(text, px)                // (string|null, integer) -> string
/** Others kept verbatim and in order, every max-width dropped, joined with '; '; null when none is left. */
function styleWithoutWidth(text)                 // (string|null) -> string|null
```

Examples (spec FR-NEW-005): `styleWithWidth('color:#0F62FE;font-weight:600', 650)` is
`color:#0F62FE; font-weight:600; max-width:650px`; `styleWithWidth('background:url(data:image/png;base64,AAA);color:#123456', 650)`
is `background:url(data:image/png;base64,AAA); color:#123456; max-width:650px`;
`styleWithoutWidth('max-width: 40em;color:#525252;font-size:10px')` is `color:#525252; font-size:10px`;
`styleWithoutWidth('max-width:600px')` is `null`.

### 5.3 Bar and hooks (`static/editor-width.js`, globals called by the other scripts)

```js
function widthBlockAt(doc, target)       // Element|null: FR-NEW-002 walk, FR-NEW-003 exclusions (DEC-005)
function widthBarAttach(doc)             // called at the end of injectEditMode(doc): pointermove, scroll (capture), click, keyup on doc
function widthBarDetach(doc)             // called in removeEditMode(doc): listeners removed, drag cancelled, bar hidden
function widthBarOnFrameLoad()           // called first in onFrameLoad(): drag cancelled without restore (old document gone), bar hidden
function widthBarOnAgentUpdate()         // called by pollStatus when the update overlay shows: drag cancelled, bar hidden
function widthDragActive()               // boolean, read by pollStatus
function withWidthPreviewSuspended(fn)   // runs fn with the original attribute text in place, re-applies the preview after; returns fn()
```

Values: drag value `v = startWidth + (clientX - startX) / ratio`, `startWidth = parseFloat(getComputedStyle(block).width)`
at the press, `ratio = block.getBoundingClientRect().width / block.offsetWidth` (1 when `offsetWidth` is 0); rounded
to the nearest multiple of 10 (`Math.round(v / 10) * 10`), or to the nearest integer while `event.altKey`, then
clamped to `[80, 1280]` (FR-NEW-004). Keyboard: `Math.round(parseFloat(getComputedStyle(block).width))` plus or minus
10 (50 with Shift), clamped (FR-NEW-006). Keys handled on the bar: `ArrowRight`, `ArrowLeft` (with or without Shift),
`Delete`, `Backspace`; each is `preventDefault`ed; every other key keeps its default (E2E-037).

No change: no HTTP route, no CLI flag, no tool, no setting. Notices reused verbatim (spec FR-NEW-013, `editor.html:57`,
`:62`): `The file changed on disk. Reload to see the changes, or keep your version.`, `Connection to the editor server lost`,
and the save error notice `Save failed: <browser message>` (`editor-save.js` `showSaveError`).

### 5.4 Skill topic lines (FR-NEW-015, spelled exactly)

- `skill/topics/create.md`, last item of the list under `## Ce que l'humain peut faire`:
  `- Largeur d'un texte: barre sur son bord droit (glisser par pas de 10px, Alt au pixel, flèches; double clic: largeur du modèle). Écrit \`max-width:Npx\` dans son \`style\`.`
- `skill/topics/export.md`, last item of the list under `### Perdu`:
  `- Le \`max-width\` d'un texte (barre de largeur de l'éditeur): la zone de texte garde la largeur de son bloc.`

Measured this run (`mcp-htmleditor skill-audit --json`, rendered topic with its `# Skill topic:` line): `create` 7815
bytes, the line adds 172 (UTF-8, newline included): 7987 of 8000. `export` 7261, the line adds 109: 7370. Core
`skill/core.md` sha256 `171b191f41e9b11f0d608caf0255b6f37d07f89e7025a450f61839106660d4dd`, unchanged (E2E-035).

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/static/editor-width.js` | create: style text functions, bar, drag, preview suspension | FR-NEW-001 to FR-NEW-012 | US-0089, US-0090, US-0091, US-0092 |
| `src/mcp_htmleditor/static/editor.html` | modify: bar markup, script tag after `editor-drag.js` | FR-NEW-001 | US-0089 |
| `src/mcp_htmleditor/static/editor.css` | modify: bar, readout, focus outline | FR-NEW-001, NFR-002 | US-0089, US-0090 |
| `src/mcp_htmleditor/static/editor-edit.js` | modify: `widthBarAttach` in `injectEditMode`, `widthBarDetach` in `removeEditMode` | FR-NEW-001 | US-0089 |
| `src/mcp_htmleditor/static/editor-save.js` | modify: clone inside `withWidthPreviewSuspended` | FR-NEW-010 | US-0089 |
| `src/mcp_htmleditor/static/editor-undo.js` | modify: `captureDomSnapshot` outerHTML inside `withWidthPreviewSuspended` | FR-NEW-009, FR-NEW-010 | US-0090 |
| `src/mcp_htmleditor/static/editor.js` | modify: `onFrameLoad` and `pollStatus` hooks | FR-NEW-001, FR-NEW-003, FR-NEW-011, FR-NEW-013 | US-0091, US-0092 |
| `tests/test_static_scripts.py` | modify: `editor-width.js` in `EXPECTED_SCRIPT_ORDER` after `editor-drag.js` | DT-004 of SPEC-0012 (script order) | US-0089 |
| `tests/width_support.py` | create: fixtures D1, D2, D3, M1, W1 writers, shared page fixture, drag and read helpers | all E2E | US-0089 (then extended) |
| `tests/test_width_drag_e2e.py` | create | FR-NEW-001 to FR-NEW-005, FR-NEW-012 | US-0089 |
| `tests/test_width_keys_undo_e2e.py` | create | FR-NEW-006 to FR-NEW-009 | US-0090 |
| `tests/test_width_visibility_e2e.py` | create | FR-NEW-001 to FR-NEW-003 | US-0091 |
| `tests/test_width_failures_e2e.py` | create | FR-NEW-010, FR-NEW-011, FR-NEW-013 | US-0092 |
| `tests/test_width_agent_e2e.py` | create | FR-NEW-014, FR-NEW-015 | US-0093 |
| `skill/topics/create.md`, `skill/topics/export.md` | modify: one line each | FR-NEW-015 | US-0093 |
| `README.md` | modify: "Visual editor" list | FR-NEW-001 | US-0093 |
| `AGENTS.md` | modify: "twelve classic scripts" becomes thirteen | n/a (docs) | US-0093 |
| `.agent_docs/html-conventions.md` | modify: editor artifacts (the bar lives in the shell), undo coverage (width change) | FR-NEW-009, FR-NEW-010 | US-0093 |
| `.agent_docs/architecture.md` | modify: browser side, `editor-width.js`, preview suspension | FR-NEW-010 | US-0093 |
| `.agent_docs/testing.md` | modify: width test files, shared page pattern | n/a (docs) | US-0093 |

Affected existing tests: `tests/test_static_scripts.py` modified (one name added to the order list; its uniqueness of
function names check covers the new file). Kept unchanged: `test_undo_redo_e2e.py`, `test_autosave_focus_e2e.py`,
`test_save_ui_e2e.py`, `test_strip_idempotent.py` (spec 9.4), `test_skill_*` (anchors untouched).

Affected documentation: `README.md`, `AGENTS.md`, `.agent_docs/html-conventions.md`, `.agent_docs/architecture.md`,
`.agent_docs/testing.md`. No `CHANGELOG` exists in this repository (`ls CHANGELOG*` returns nothing).

## 7. Compatibility and risks

- Consumers: agents read the declaration like any inline style (no tool change); PPTX and DOCX ignore it (spec 3.2,
  BL-0033); files written before this feature are unchanged until the author uses the bar.
- R1, preview leak: any serialization of the framed document during a drag captures the normalized preview unless it
  runs inside `withWidthPreviewSuspended`. Today there are exactly two (`rg -n "outerHTML|cloneNode\(true\)" static`:
  `editor-save.js:24`, `editor-undo.js:46`); both are wrapped (DEC-004). Detection: E2E-018, E2E-032.
- R2, focus moves to the shell: pressing the bar moves the focus out of the frame, so the edited zone fires `blur`
  and `onEditableBlur` saves at once, during the drag. Correct only with R1 handled (E2E-032).
- R3, undo order: `snapshotForUndo()` must run after the original text is restored and before the new text is set;
  a no change action must call neither (FR-NEW-008). Detection: E2E-009, E2E-012, E2E-020.
- R4, the poll: an external write during a drag must not reload the frame (else E2E-026 sees a reload, not the
  conflict); an agent update must cancel the drag (E2E-036). DEC-008.
- R5, run time: the gate's test step is about 301 s against the 330 s ceiling of SPEC-0014/BT-022; the 43 tests get
  a budget of 25 s in total (DEC-011), each story reports the durations of its file.
- Ordering: US-0089 first (the bar and the text rebuild); US-0090 needs the commit path; US-0091 and US-0092 change
  `editor.js`; the closing story US-0093 last. Linear chain because every story touches `editor-width.js`.
- Rollback: `git revert` of the story commits; files already saved keep a plain declaration that stays valid HTML.
- Dependencies added or removed: none.

## 8. Security design

n/a (`Security: n/a`; the width is a bounded integer written by the editor itself, spec 9.1).

## 9. Test strategy

All 43 tests are functional e2e (Playwright Chromium on a real in process editor server) except E2E-029, E2E-034 and
E2E-035, which run the command line in a child process, `sys.executable -m mcp_htmleditor`, with `HTMLEDITOR_SKILL_DIR`
pointing at the repository `skill/` (`config.py:119`, as `tests/test_skill_shipped.py:95`), and the agent half of E2E-028 and E2E-041, which calls
`deck.read.get_slide` and `deck.lint.lint_file` in process after the browser drag.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| E2E-001, 002, 003, 004, 005, 006, 007, 042 | functional e2e | Playwright, shared page (DEC-011) | `tests/test_width_drag_e2e.py` | US-0089 |
| E2E-008, 009, 010, 011, 012, 013, 014, 015, 016, 020, 030, 037, 038, 040 | functional e2e | Playwright, shared page | `tests/test_width_keys_undo_e2e.py` | US-0090 |
| E2E-021, 022, 023, 024, 025, 031, 033, 043 | functional e2e | Playwright, shared page | `tests/test_width_visibility_e2e.py` | US-0091 |
| E2E-017, 018, 019, 026, 027, 032, 036, 039 | functional e2e | Playwright, shared page, `HTMLEDITOR_POLL_INTERVAL=100` | `tests/test_width_failures_e2e.py` | US-0092 |
| E2E-028, 041 | functional e2e | Playwright drag, then `get_slide` and `lint_file` in process | `tests/test_width_agent_e2e.py` | US-0093 |
| E2E-029, 034, 035 | functional | `sys.executable -m mcp_htmleditor skill --type create|export`, `skill-audit` | `tests/test_width_agent_e2e.py` | US-0093 |

Fixtures (test data, generated by `tests/width_support.py` from the bootstraps, nothing user provided):

- D1: `templates/bootstrap/slides-empty.html` (Carbon) grown to three slides; slide 2 body holds
  `<div style="width:800px">` with paragraphs A, B (inline `<span class="tag-blue">Nouveau</span>`), H, I, J, K, P,
  Q exactly as spec 9.0, a `<ul data-editable="text">` of `Premier point`, `Second point`, a `data-type="table"`
  with `Indicateur` / `Valeur A1`, an image `alt="logo"` (1x1 PNG base64); slide 3 holds an arch node
  `Serveur MCP`, a Gantt task `Cadrage`, an annotation `Pic`. Every paragraph carries `data-editable="text"`.
  Window 1280 by 900.
- D3: D1 plus `<style>.slide{transform:scale(0.5);transform-origin:top left}</style>` in the head, so slide 2 shows
  480 pixels wide (spec 14.3: the current templates never scale while editing).
- D2: `templates/bootstrap/document-perso-empty.html` with title `Rapport Q1` and paragraphs `Paragraphe 1` to
  `Paragraphe 40`, paragraph 1 `style="max-width:500px"`.
- M1: `templates/bootstrap/mail-empty.html` as is (intro paragraph `mail-empty.html:41`).
- W1: `templates/bootstrap/website-empty.html` as is (tab label `Vue d'ensemble`).

Waits: every asynchronous result through `tests/browser_wait.py` (`wait_for_file`, `wait_for_js`, `wait_until`); an
absence (no save, no reload) after `wait_until` on its cause, then `settle(page)` (SPEC-0014/BR-010). Saves are
counted by an init script that wraps `window.fetch` and increments `window.__widthSaves` on each `POST /content`
(test side, same technique as `LATE_SAVE_SCRIPT`, `browser_wait.py`). Bar visibility is set synchronously in the
pointer handler (DEC-006), so "no bar" is read right after `page.mouse.move` without a settle.

## 10. Decisions log

- **DEC-001:** The bar is one element of the shell page (`#width-bar` with its `#width-readout`, markup 5.1), placed
  with `position: fixed` over the frame at `frameRect.left + blockRect.right` and `frameRect.top + blockRect.top`,
  height `blockRect.height`, its left clamped to `window.innerWidth - barWidth`. It is never inserted into the framed
  document. **Obliged by:** SPEC-0015/FR-NEW-001, FR-NEW-003, FR-NEW-010, NFR-003. **Rationale:** nothing of the
  bar can reach the file or the undo snapshot; the template's key navigation never sees the bar's arrows; the
  fullscreen presentation (inner document fullscreen, `editor.js:114`) covers the shell. **Alternatives
  considered:** bar inside the frame (section 2). **Source:** design. **Evidence:** `editor-save.js:24` to `:31`,
  `http_server.py:52`, `editor-undo.js:27` to `:56`.
- **DEC-002:** A new classic script `static/editor-width.js`, loaded right after `editor-drag.js` (thirteen editor
  scripts), holds the style text functions (5.2) and the bar (5.3). Its function names are unique across the editor
  scripts (checked by `tests/test_static_scripts.py`). **Obliged by:** FR-NEW-001 to FR-NEW-012. **Rationale:** one
  file per editor concern, as the existing split; globals called at run time only, never at evaluation time
  (`.agent_docs/architecture.md`). **Alternatives considered:** adding to `editor-drag.js` (239 lines, another
  concern). **Source:** existing code `editor.html:108` to `:119`. **Evidence:** `tests/test_static_scripts.py`
  `EXPECTED_SCRIPT_ORDER`.
- **DEC-003:** The saved style is rebuilt as text (5.2) from the attribute text read before the action and written
  with `setAttribute('style', text)`, or `removeAttribute('style')` when the reset leaves nothing. The element's style
  object is used only for the live preview. **Obliged by:** FR-NEW-005, FR-NEW-007, FR-NEW-012, FR-NEW-014.
  **Rationale:** measured in Chromium this run, `el.style.maxWidth` rewrites the whole attribute (hex to `rgb(...)`,
  spaces, quotes in `url(...)`), while clearing a property that is absent (`el.style.outline = ''`, the existing save
  clone) leaves the text untouched, so the existing clone code needs no change for this. **Alternatives considered:**
  saving through the style object (section 2). **Source:** design, spec 14.3. **Evidence:** `/tmp/spec15/probe.py`
  output `['color:#0F62FE;font-weight:600', 'color: rgb(15, 98, 254); font-weight: 600; max-width: 650px;', ...]`.
- **DEC-004:** `withWidthPreviewSuspended(fn)`: while a drag preview is applied, it sets the original attribute text
  back (or removes the attribute when it was absent), runs `fn` synchronously, then re-applies the preview with
  `style.setProperty('max-width', v + 'px')`. `runSave` wraps its `cloneNode(true)`; `captureDomSnapshot` wraps its
  `outerHTML`. No repaint can occur inside the synchronous call, so nothing flickers. **Obliged by:** FR-NEW-010,
  FR-NEW-012, NFR-003. **Rationale:** the autosave of typing and the blur save (R2) serialize the live document during
  the drag; the clone must hold the width before the drag (E2E-018). **Alternatives considered:** fixing the clone
  afterwards by locating the node (needs a marker or a path, fragile); a preview through an injected stylesheet
  (needs a marker attribute to target the node, which would have to be stripped everywhere). **Source:** design,
  spec 14.3. **Evidence:** `editor-save.js:24`, `editor-undo.js:46` (the only two serializations,
  `rg -n "outerHTML|cloneNode\(true\)" src/mcp_htmleditor/static/*.js`).
- **DEC-005:** `widthBlockAt(doc, target)`: return `null` when `target.closest(EXCLUDED)` matches, with
  `EXCLUDED = 'img, picture, svg, video, canvas, table, [data-type="arch-node"], [data-type="arch-edge"],
  [data-type="gantt-task"], [data-type="annotation"], #_mcp_format_bar, #_mcp_insert_bar, ._mcp_drag_handle,
  #_editor_ctx_host'`; else walk from `target` (its parent when it is a text node) up through ancestors while the
  element is inside a zone (`el.closest('[data-editable~="text"]')`), and return the first element that matches
  `p, h1, h2, h3, h4, h5, h6, li, blockquote, figcaption, [data-editable~="text"]` and whose computed `display` does
  not start with `inline` and is not `contents`; `null` when the walk leaves the zone, when the result has a zero
  width rectangle, when edit mode is off, when `document.fullscreenElement` or `doc.fullscreenElement` is set, or
  when the update overlay shows (`overlay.style.display === 'flex'`). **Obliged by:** FR-NEW-002, FR-NEW-003.
  **Rationale:** literal transcription of the two requirements; the inline zone of the website tab (`<span
  data-editable>` inside a `<button>`) is inline and the walk leaves the zone at the button (E2E-033).
  **Alternatives considered:** a fixed tag list without the display check (would size inline zones).
  **Source:** spec FR-NEW-002, FR-NEW-003. **Evidence:** `templates/bootstrap/website-empty.html:66` to `:68`.
- **DEC-006:** Show, hide and position are synchronous in the event handlers: `pointermove` on the framed document
  (attached by `widthBarAttach`), `pointerleave` of the bar and of the frame's root (hide unless the pointer goes to
  the block or the bar), `scroll` on the framed document in the capture phase and `resize` on the shell window
  (reposition; hide when the block is disconnected or has a zero width), `click` and `keyup` on the framed document
  (same check, which hides the bar after a slide change). No `requestAnimationFrame` throttling. **Obliged by:**
  FR-NEW-001, NFR-001. **Rationale:** a test can read the bar's state right after the pointer action without a fixed
  wait; one `getBoundingClientRect` per move stays far below a frame on 30 blocks. **Alternatives considered:** an
  `IntersectionObserver` or a rAF loop (asynchronous, needs waits in tests). **Source:** design. **Evidence:** n/a.
- **DEC-007:** Drag: `pointerdown` on the bar (primary button) calls `preventDefault`, `focus()` and
  `setPointerCapture`, and records `widthDrag` (5.3) with the original attribute text; `pointermove` computes the
  value (5.3), applies the preview and shows the readout; `pointerup` hides the readout and, when the pointer moved
  and `styleWithWidth(original, value)` differs from the original text, commits; `pointercancel` and a
  `lostpointercapture` not preceded by `pointerup` cancel: original text back, readout hidden, nothing saved.
  Commit: original text back, `snapshotForUndo()`, new text set, `markPending()`, `saveContent()`. Keyboard and reset
  use the same commit; a reset on a text where `styleHasWidth` is false does nothing (no rebuild, so the separators
  of the other declarations are never rewritten, E2E-012). `dblclick` on the bar resets. **Obliged by:** FR-NEW-004
  to FR-NEW-009, FR-NEW-011. **Rationale:** one commit path gives one undo step per change and keeps the pre
  mutation snapshot rule of `editor-undo.js:58` to `:69`; FR-NEW-008 is the text comparison. **Alternatives
  considered:** snapshot at press (would push a step for a no change drag). **Source:** spec 14.3, existing code
  `editor-undo.js:58`. **Evidence:** spec 14.3 fourth bullet.
- **DEC-008:** `pollStatus` (`editor.js:309`): when the update overlay is shown it calls `widthBarOnAgentUpdate()`
  (cancel, hide); the external change test becomes `mtimeChanged && !selfSaving && !hasPendingChanges &&
  !widthDragActive()`, so an agent write during a drag does not reload the frame and the release save meets the
  SPEC-0009 conflict (409, notice). `onFrameLoad` (`editor.js:199`) calls `widthBarOnFrameLoad()` first: the drag is
  dropped without touching the new document and the bar hides until the pointer moves. **Obliged by:** FR-NEW-011,
  FR-NEW-013, FR-NEW-001 (hide on reload), FR-NEW-003 (agent update). **Rationale:** E2E-026 expects the conflict
  notice and the agent's version on disk; E2E-036 and E2E-043 expect the reloaded file shown and no save.
  **Alternatives considered:** marking the drag as a pending change (`markPending` at press): the typing autosave
  during the drag calls `markSaved()` and would re-enable the reload. **Source:** existing code `editor.js:334` to
  `:345`. **Evidence:** spec 14.3, E2E-026, E2E-036.
- **DEC-009:** No new route: a width change rides `saveContent()` (`POST /content` with `base_mtime`), its status
  dot, conflict notice and error notice. **Obliged by:** FR-NEW-013. **Rationale:** spec 14.3; a pending change after
  a failed save stays pending and is written by the next successful save (E2E-039). **Alternatives considered:** a
  width route (section 2). **Source:** spec 14.3. **Evidence:** `editor-save.js` `runSave`.
- **DEC-010:** The two guidance lines are added as the last item of their lists (5.4); no other topic text changes.
  **Obliged by:** FR-NEW-015. **Rationale:** measured budgets leave 13 bytes in `create` after the line, so nothing
  else may grow that topic in the same story. **Alternatives considered:** trimming another line of `create` to make
  room (not needed by the measurement). **Source:** spec FR-NEW-015. **Evidence:** `mcp-htmleditor skill-audit --json`
  (`create` 7815, `export` 7261), `printf ... | wc -c` (172 and 109).
- **DEC-011:** Economical browser tests: each test file starts one server per test (the existing `_start` pattern,
  fresh state, `reset_state`), but shares one Chromium page per module (`browser.new_context(viewport={"width": 1280,
  "height": 900})` in a module scoped fixture of `tests/width_support.py`); each test writes its fixture, does
  `page.goto(base_url)`, waits with `wait_for_js` for the frame document's `readyState` `complete`, then clicks
  `#edit-mode-btn`. No late save variant (the spec asks none). Budget: the 43 tests take at most 25 s together, each
  story reports `make test ARGS='-k width --durations=0'` for its file; the closing story proves the gate's test
  step stays at most 330 s (SPEC-0014/BT-022). **Obliged by:** n/a (no code impact): keeps SPEC-0014/BT-022 true while
  adding the spec's 43 tests. **Rationale:** a new browser context per test costs more than the server start; one
  server per test keeps the per test state directory of `tests/conftest.py:76` coherent with the server's
  `EditorState` singleton (`reset_state`). **Alternatives considered:** one server per module (the autouse per test
  state directory would split the server's records across directories); the default function scoped `page` (slower).
  **Source:** design, user instruction (gate about 301 s against a 330 s cap). **Evidence:** `tests/conftest.py:76`,
  `tests/test_undo_redo_e2e.py` `_start`.
- **DEC-012:** Story slicing: five stories in a linear chain. US-0089 the bar and the drag with the exact text rebuild
  and the preview suspension (`min_tier` 1: the style object pitfall of DEC-003 and the suspension of DEC-004);
  US-0090 keyboard, reset and undo (`min_tier` 1: undo order R3 and the no change rule); US-0091 where the bar shows
  and hides (`min_tier` 2); US-0092 interrupted drags, saves during a drag, conflicts and a stopped server
  (`min_tier` 1: save and reload interplay, DEC-004, DEC-008); US-0093 the agent side, the guidance lines, the
  documentation and the run time (closing, `min_tier` 2). **Obliged by:** n/a (no code impact): partition; every
  requirement is covered in section 11. **Rationale:** files touched is the binding budget; the three pitfalls named
  by the user (style written as text, undo and save interplay, marker stripping) sit in the three tier 1 stories.
  **Alternatives considered:** one story per scenario (SC-001 alone holds 25 tests). **Source:** design, user
  instruction.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0089 | width bar and drag saved as one declaration | P1 | FR-NEW-001 (partial), FR-NEW-002 (partial), FR-NEW-004, FR-NEW-005, FR-NEW-010 (partial), FR-NEW-012 (partial), FR-NEW-013 (partial), NFR-001 | main | 1 | no |
| US-0090 | keyboard steps, reset and undo of a width | P1 | FR-NEW-006, FR-NEW-007, FR-NEW-008, FR-NEW-009, NFR-002 | US-0089 | 1 | no |
| US-0091 | where the width bar shows and hides | P2 | FR-NEW-001, FR-NEW-002, FR-NEW-003 | US-0090 | 2 | no |
| US-0092 | interrupted drags, saves during a drag, conflicts | P2 | FR-NEW-010, FR-NEW-011, FR-NEW-012, FR-NEW-013, NFR-003 | US-0091 | 1 | no |
| US-0093 | agent side, guidance lines and documentation | P2 | FR-NEW-014, FR-NEW-015 | US-0092 | 2 | yes |
