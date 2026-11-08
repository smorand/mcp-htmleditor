# SPEC-0016: Reference decks without presentation mode, End ignored by the editor, vector figures dropped silently from PPTX, design

> Spec: sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/spec.md
> Nature: BUG
> Depth: L
> Security: n/a
> Designed on: 2026-11-08
> Target tier: 2 (user instruction for this run: tier 2 by default, stories with silent pitfalls at `min_tier` 1; no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

Run mode: unattended (the user asked for no questions and the recommended defaults). No new dependency, no new
route, no new setting, no data format change.

Project state: existing (`ls src/mcp_htmleditor` lists the product package; `git log --oneline -1` is `2f3b72b`).

Counts (by command on `spec.md`): 21 requirements (`BR-001` to `BR-021`; the `FR-0xx` ids in the text are
SPEC-0001 references, not requirements of this spec), 26 acceptance tests (`BT-001` to `BT-004`, `BT-010` to
`BT-024`, `BT-030` to `BT-036`; the `E2E-038` to `E2E-041` ids are SPEC-0001 references), 0 scenarios.

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| Editor (browser) | classic scripts, no build step, `static/editor.js` holds the key relay (`editor.js:152` to `:167`) | n/a | existing, DEC-001 |
| PPTX exporter | `export/to_pptx.py` loop over slides, `_SlideBuilder` mixins, `ExportReport.warn` | python-pptx as locked | existing, DEC-003 |
| Reference decks | self contained HTML under `templates/reference/slides/`, inline CSS and JS | n/a | existing, DEC-006, DEC-008 |
| Browser tests | pytest, pytest-playwright (Chromium), `tests/browser_wait.py` (SPEC-0014) | as locked | existing, DEC-009 |
| Child process tests | `sys.executable -m mcp_htmleditor`, `tests/stdio_support.py` for the MCP stdio session | n/a | existing, DEC-012 |
| Skill size audit | `skill_content.TOPIC_BUDGET_BYTES = 8000` (`skill_content.py:47`) | n/a | existing, DEC-013 |

Skills loaded: `python` (via `load_dynamic_context`, injected for this run). Effect: `make check` is the gate
(check-generated, lint, format-check, typecheck strict, bandit, coverage 80 %); tests run through `make test` only
(`make test ARGS='-k pptx_vectors'`); constants at the top of modules, `%` logging, no `print`. Project conventions
applied: `AGENTS.md` (fullscreen rule, browser waits and pacing rule, `node --check`), `.agent_docs/html-conventions.md`
§ Fullscreen, `.agent_docs/testing.md` (330 s test step, `browser_wait`, `stdio_support`), `sdlc/constitution.md`.

## 2. Approaches

Depth L asks for the fix strategies per defect. The root cause named by the spec decides each one.

### BUG-001, chosen: one `End` branch in the editor's relay

Add `End` beside `Home` in the parent page listener (`editor.js:162`), guarded by `typeof win.goToSlide ===
'function'`, calling `win.goToSlide(n - 1)` with `n` counted in the framed document. Pros: fix at the root cause
site, one line family, every deck that defines `goToSlide` works. Cons: the slide count must come from the DOM, since
`const TOTAL` is not a property of `window`. Rejected: dispatching a synthetic `KeyboardEvent` into the framed
document (the deck's focus exception may drop it, and it would bypass the guard of BR-003); calling `win.goToLast`
(only `ibm-carbon.html` defines it). See DEC-001.

### BUG-002, chosen: one pre pass per slide that warns, the picture path stays silent on vectors

Before each slide is built, a pure function walks the slide element and returns the vector warnings in document
order; `_image_source` returns `None` without a warning for a vector `src`. Pros: one place decides what a vector
figure is (BR-005 to BR-007), the slide XML cannot change (BR-008: the picture failed anyway and left no shape), the
seven walkers that skip `SKIP_TAGS` stay untouched. Cons: vector warnings of a slide come before its other warnings
(acceptable: BT-002 and BT-014 assert only vector warnings, in document order). Rejected: report in each walker at the
skip site (seven sites, `pptx_flow.py:102`, `:231`, `pptx_text.py:32`, `:64`, `:96`, `pptx_blocks.py:314`,
`pptx_arch.py:47`; some elements are visited twice, so counts would drift); reading the warnings out of the picture
library exception (no slide number, two warnings per image). See DEC-003, DEC-004.

### BUG-003, chosen: ship the bootstrap building blocks in each deck, by family, then a discovery guard

Shell decks (`ibm-carbon.html`, `example-ei-complete.html`, `example-carbon-complete.html`) already have `render`,
`navigate`, `goToSlide` and a `keydown` handler (E14): they receive the bootstrap CSS block, button and functions.
Stacked decks (`presentation-standard.html`, `roadmap-one-pager.html`) have no script (E15): they receive a small
navigation script plus the same building blocks, keeping their stacked layout outside presenting. A test discovers
every presentation file under `templates/` at run time and checks the five markers. Pros: each family follows its
existing structure; the PPTX export cannot change because every added selector is rejected by the style resolver and
every added element is skipped by the exporter (DEC-007). Cons: five hand edited files; the stacked script is new
code inside a template. Rejected: converting the stacked decks to shell decks (changes their layout outside
presenting and their PPTX export, against BR-015); a shared external script (decks must stay single file and work
from `file://`, BR-017). See DEC-006 to DEC-011.

### Arbitrations BR-018 to BR-020, chosen: lock today's behavior with tests

The spec decides the code is right. The work is tests that fail if a later change reloads a stale record or
swallows a missing pandoc. Rejected: deleting `EditorState.load()` (that is BL-0009, a DEBT entry outside this spec).
See DEC-012.

## 3. Architecture

```
 editor page (static/editor.js)                    framed deck (#content-frame)
 keydown on parent document ── WHILE fullscreen ──► win.navigate(+1 / -1)
   ArrowRight/Down/space, ArrowLeft/Up             win.goToSlide(0)              Home
   End (new, DEC-001)                              win.goToSlide(n - 1)          n = [data-type="slide"] count
   Escape                                          document.exitFullscreen()

 export/to_pptx.py  for index, article in slides:
                       report.warn(*vector_figure_warnings(article, index + 1))   new, export/pptx_vectors.py
                       _SlideBuilder(...).build()  ── pptx_images._image_source(src): vector src -> None, silent

 reference decks    shell family: toolbar + render() ──► updateFullscreenScale() on render, fullscreenchange, resize
                    stacked family: new script: slides[], current, render(), navigate(), goToSlide(),
                                    data-fs-current marker while presenting only
 tests              test_presentation_templates_fullscreen.py: discovers templates/**/*.html with
                    data-doc-type="presentation", asserts the five markers
```

Bounded contexts: browser editing (relay), PPTX export (warnings), templates (decks), test gate (guard), agent
guidance (one skill sentence). No HTTP, CLI, MCP or state change.

## 4. Data model

No persisted data change. Two runtime only values in the stacked decks, never present in a saved file outside
presenting: the inline custom property `--fs-scale` on `<html>` (already the bootstraps' contract, E28) and the
attribute `data-fs-current` on the current slide (DEC-008). Test data: one new fixture file
`tests/testdata/example_carbon_complete_slide_hashes.json`, `{"ppt/slides/slide1.xml": "<sha256>", ...}` for 9
slides, recorded from the file at c507194 (DEC-010).

## 5. Contracts and interfaces

### 5.1 Editor relay (`static/editor.js`, inside the existing `keydown` listener)

```js
} else if (e.key === 'End' && typeof win.goToSlide === 'function') {
  const count = win.document.querySelectorAll('[data-type="slide"]').length;
  if (count > 0) { e.preventDefault(); win.goToSlide(count - 1); }
}
```

Placed after the `Home` branch, before `Escape`. Nothing else in the listener changes (BR-004: the first line still
returns when `!document.fullscreenElement`).

### 5.2 Vector figures (`src/mcp_htmleditor/export/pptx_vectors.py`, new)

```python
VECTOR_ADVICE = SVG_ADVICE  # imported from .to_docx: "Regle: figures en PNG, jamais en SVG."
SILENT_ANCESTORS = frozenset({"button", "script", "template", "noscript", "select"})
SRC_PREVIEW_CHARS = 60


def is_vector_src(src: str) -> bool:
    """True when src cut at its first '?' and lowercased ends with '.svg', or lowercased starts with 'data:image/svg'."""


def vector_figure_warnings(slide: Tag, number: int) -> list[str]:
    """Warnings for every vector figure of one slide, in document order (BR-005 to BR-007)."""
```

Texts (spec BR-005, BR-006, verbatim):

- inline: `f"Slide {number}: balise <svg> en ligne ignoree, l'export PPTX ne convertit pas les vecteurs. {VECTOR_ADVICE}"`
- image: `f"Slide {number}: image SVG ignoree ({src[:60]}), l'export PPTX ne convertit pas les vecteurs. {VECTOR_ADVICE}"`

An inline figure is a `<svg>` with no `<svg>` ancestor; an image figure is an `<img>` whose `src` passes
`is_vector_src`. Either is skipped when an ancestor (up to and excluding the slide element) is in
`SILENT_ANCESTORS`. Elements outside the slide are never visited (BR-007). `to_pptx` calls it once per slide, the body
included when the document has no slide (E34), and passes each string to `report.warn`. The CLI (`cli.py:531`) and the
MCP `export` tool (`mcp_server.py:400`) already forward `report.warnings` unchanged.

`pptx_images._image_source(src)`: first statement `if is_vector_src(src): return None` (no warning; BR-006).

### 5.3 Deck building blocks (both families)

Markers (BR-009, checked literally by the guard): `:fullscreen`, `id="btn-present"`, `enterPresentation`,
`exitPresentation`, `updateFullscreenScale`. Contract of the functions, as `templates/bootstrap/slides-empty.html:373`
to `:410`:

- `updateFullscreenScale()`: when `document.fullscreenElement` is null or there is no current slide, remove
  `--fs-scale` from `<html>`; else set it to `'1'`, measure the current slide's `getBoundingClientRect()`, set it to
  `String(Math.min(innerWidth / rect.width, innerHeight / rect.height))`.
- `enterPresentation()`: `document.documentElement.requestFullscreen()` (webkit fallback).
- `exitPresentation()`: `document.exitFullscreen()` when fullscreen.
- listeners: `fullscreenchange` and `resize` call `updateFullscreenScale`; `render` calls it last.
- `keydown`: return when the active element is content editable, `INPUT`, `TEXTAREA` or `SELECT`; `ArrowRight`,
  `ArrowDown`, space (with `preventDefault`) forward; `ArrowLeft`, `ArrowUp` back; `Home` first; `End` last; `f`, `F`
  enter; `Escape` exit.

Stacked family additions (DEC-008): `const slides = Array.from(document.querySelectorAll('[data-type="slide"]'))`,
`let current = 0`, `render()` (sets `data-fs-current` on `slides[current]` and removes it from the others only while
`document.fullscreenElement`; outside presenting removes every marker and calls
`slides[current].scrollIntoView({block: 'start'})`), `navigate(dir)` and `goToSlide(idx)` with the shell decks'
semantics (`navigate` bounded, no move past the ends).

### 5.4 Guard (`tests/test_presentation_templates_fullscreen.py`, new)

```python
MARKERS = (":fullscreen", 'id="btn-present"', "enterPresentation", "exitPresentation", "updateFullscreenScale")
def presentation_files(root: Path) -> list[Path]   # templates/**/*.html whose opening <html ...> tag holds data-doc-type="presentation"
def missing_markers(html: str) -> list[str]        # MARKERS absent from the text, in MARKERS order
```

Failure message per file: `f"{relative_path}: missing {', '.join(missing)}"` with `relative_path` relative to the
templates root (for example `reference/slides/x.html: missing :fullscreen, id="btn-present", ...`).

### 5.5 Skill sentence (`skill/topics/slides-carbon.md:96`, BR-021)

Before: ``La référence `ibm-carbon.html` est un catalogue autonome, sans CSS `:fullscreen`, dont les slides dépassent 540 px: copier ses composants en respectant le budget 540 px, jamais sa densité ni son modèle de hauteur variable.``

After: ``La référence `ibm-carbon.html` est un catalogue autonome dont les slides dépassent 540 px: copier ses composants en respectant le budget 540 px, jamais sa densité ni son modèle de hauteur variable.``

The topic shrinks (7558 bytes on disk today), so the 8000 byte budget holds.

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/static/editor.js` | modify: `End` branch in the relay (5.1) | BR-001 to BR-004 | US-0095 |
| `tests/test_fullscreen_e2e.py` | modify: add the relay tests BT-001, BT-010 to BT-012 (existing four unchanged) | BR-001 to BR-004 | US-0095 |
| `src/mcp_htmleditor/export/pptx_vectors.py` | create (5.2) | BR-005 to BR-007 | US-0096 |
| `src/mcp_htmleditor/export/to_pptx.py` | modify: call `vector_figure_warnings` per slide | BR-005, BR-006, BR-008 | US-0096 |
| `src/mcp_htmleditor/export/pptx_images.py` | modify: silent `None` for a vector `src` | BR-006 | US-0096 |
| `tests/test_export_pptx_vectors.py` | create: BT-002, BT-013, BT-014, BT-015, BT-034 | BR-005 to BR-008 | US-0096 |
| `.agent_docs/architecture.md` | modify: export pipeline, vector pre pass | n/a (docs) | US-0096 |
| `templates/reference/slides/ibm-carbon.html` | modify: shell building blocks | BR-009 to BR-015, BR-017 | US-0097 |
| `templates/reference/slides/example-ei-complete.html` | modify: same | same | US-0097 |
| `templates/reference/slides/example-carbon-complete.html` | modify: same | same | US-0097 |
| `tests/test_reference_decks_present_e2e.py` | create: deck browser tests, shell decks first | BR-010 to BR-014, BR-017 | US-0097, US-0098 |
| `tests/testdata/example_carbon_complete_slide_hashes.json` | create from c507194 | BR-015 | US-0097 |
| `tests/test_export_golden.py` | modify: add the BT-032 test (golden file untouched) | BR-015 | US-0097 |
| `templates/reference/slides/presentation-standard.html` | modify: stacked building blocks and script | BR-009 to BR-015, BR-017 | US-0098 |
| `templates/reference/slides/roadmap-one-pager.html` | modify: same | same | US-0098 |
| `tests/test_presentation_templates_fullscreen.py` | create: the guard (5.4), BT-016, BT-021 | BR-009, BR-016 | US-0099 |
| `sdlc/constitution.md` | modify: "Enforced by" of the fullscreen rule | BR-016 | US-0099 |
| `tests/test_legacy_arbitrations.py` | create: BT-022, BT-023 | BR-018 to BR-020 | US-0100 |
| `skill/topics/slides-carbon.md` | modify: one sentence (5.5) | BR-021 | US-0101 |
| `tests/test_skill_shipped.py` | modify: add BT-024 | BR-021 | US-0101 |
| `AGENTS.md`, `.agent_docs/html-conventions.md`, `.agent_docs/testing.md` | modify: fullscreen guard, stacked variant, relay `End`, new test files | n/a (docs) | US-0101 |

Affected existing tests: all kept unchanged (spec 4.4). `tests/test_fullscreen_e2e.py` gains tests, its four
existing tests keep their assertions (BT-030). `tests/testdata/pptx_slide_hashes.json` is never regenerated (BT-031).

Affected documentation: `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/html-conventions.md`,
`.agent_docs/testing.md`, `sdlc/constitution.md`, `skill/topics/slides-carbon.md`. No `CHANGELOG` in this repository.

## 7. Compatibility and risks

- R1, PPTX hashes of the decks (BR-015): a CSS rule whose selector the resolver indexes, or a class added to an
  element inside a slide, changes the slide XML. Mitigation DEC-007; detection BT-031 (four decks in the golden set)
  and BT-032 (`example-carbon-complete.html`).
- R2, saved runtime state: the editor serializes the live framed document on save, so anything a deck script adds to
  its DOM can reach the file. `--fs-scale` and `data-fs-current` exist only while presenting (DEC-008); the shell
  decks' `active` class already behaves this way today.
- R3, relay test that tests nothing: `document.body.focus()` leaves the focus in the iframe (E4). The relay tests
  dispatch the event on the parent `document` (DEC-002); BT-001 is red before the fix for the stated reason.
- R4, `ibm-carbon.html` holds one inline `<svg>` inside a slide (E31): its export gains one BR-005 warning. No test
  asserts its warnings (`test_ibm_carbon_template_exports_nine_slides` asserts `slide_count` only,
  `tests/test_export_pptx.py:280`); the golden hashes cover XML, not warnings.
- R5, run time: the gate's test step is about 235 s against the 330 s cap of SPEC-0014/BT-022. The new browser tests
  get 40 s in total (DEC-014); each story reports its file's durations, the closing story the whole step.
- R6, guard order: the guard fails on main until the five decks comply, so it lands after US-0097 and US-0098
  (BT-004 is recorded as evidence against the unfixed decks, DEC-011).
- Ordering: US-0095, US-0096, US-0100 independent; US-0097 then US-0098 (same test file); US-0099 after both;
  US-0101 last.
- Rollback: `git revert` of a story commit; nothing persisted changes.
- Dependencies added or removed: none.

## 8. Security design

n/a (`Security: n/a`).

## 9. Test strategy

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| BT-001, BT-010, BT-011, BT-012 | functional e2e | Playwright on the editor page, events dispatched on the parent `document` | `tests/test_fullscreen_e2e.py` | US-0095 |
| BT-030 | functional e2e (non regression) | existing four tests | `tests/test_fullscreen_e2e.py` | US-0095 |
| BT-002 | functional | CLI child process `sys.executable -m mcp_htmleditor export pptx` | `tests/test_export_pptx_vectors.py` | US-0096 |
| BT-013, BT-014, BT-034 | integration | `to_pptx` in process, `report.warnings`, zip read | `tests/test_export_pptx_vectors.py` | US-0096 |
| BT-015 | functional | MCP stdio session `tests/stdio_support.py`, tool `export` | `tests/test_export_pptx_vectors.py` | US-0096 |
| BT-033, BT-035 | integration (non regression) | existing tests unchanged | `tests/test_export_pptx.py`, `tests/test_medical_template.py`, `tests/test_export_docx.py` | US-0096 |
| BT-003, BT-017, BT-019, BT-020 | functional e2e | Playwright, `file://` copy and editor page, parametrized over the decks | `tests/test_reference_decks_present_e2e.py` | US-0097 (shell decks; US-0098 extends the parameters) |
| BT-031, BT-032 | integration | golden hashes, fixture hashes | `tests/test_export_golden.py` | US-0097 |
| BT-018 | functional e2e | Playwright, `file://` | `tests/test_reference_decks_present_e2e.py` | US-0098 |
| BT-004 | gate evidence | the guard run against the c507194 decks (recorded log) | `.implement/US-0099-red.log` | US-0099 |
| BT-016, BT-021 | integration | file scan, BeautifulSoup, `tmp_path` copy | `tests/test_presentation_templates_fullscreen.py` | US-0099 |
| BT-022 | functional | CLI child process, `PATH` without pandoc | `tests/test_legacy_arbitrations.py` | US-0100 |
| BT-023 | functional | `serve` child process, `GET /status`, MCP stdio `get_status` | `tests/test_legacy_arbitrations.py` | US-0100 |
| BT-024 | functional | child process `skill --type slides-carbon` and file scan of `skill/topics/` | `tests/test_skill_shipped.py` | US-0101 |
| BT-036 | integration (non regression) | existing template scans | `tests/test_strip_idempotent.py`, `tests/test_deck_get_slide.py` | US-0101 |

Test data: generated (the `V` deck of BT-002 from the Carbon bootstrap, `D3` from `_three_slide_deck`, the guard's
`tmp_path` copy of `templates/`), plus the fixture of DEC-010. Nothing user provided. Waits through
`tests/browser_wait.py` only, no `wait_for_timeout` without `# pacing:`.

Measurement rule for BR-010 in tests: `w = slide.offsetWidth`, `h = slide.offsetHeight` (the CSS `scale` property
does not change offset sizes), `s = Math.min(innerWidth / w, innerHeight / h)`, `--fs-scale` read with
`getComputedStyle(document.documentElement).getPropertyValue('--fs-scale')`, visible box from
`getBoundingClientRect()`.

## 10. Decisions log

- **DEC-001:** The relay gains an `End` branch (5.1): guarded by `typeof win.goToSlide === 'function'`, slide count
  `win.document.querySelectorAll('[data-type="slide"]').length`, `preventDefault` then `win.goToSlide(count - 1)`,
  nothing when the count is 0. **Obliged by:** SPEC-0016/BR-001, BR-002, BR-003. **Rationale:** the deck's own `End`
  calls `goToSlide(TOTAL - 1)` (E28) and `TOTAL` is a `const`, absent from `window`; the spec defines a slide as an
  element with `data-type="slide"`, which every deck uses. **Alternatives considered:** `win.TOTAL` (undefined);
  `win.goToLast` (one deck); a synthetic event in the frame. **Source:** existing code `editor.js:162`.
  **Evidence:** `templates/bootstrap/slides-empty.html:402`.
- **DEC-002:** Relay tests dispatch `new KeyboardEvent('keydown', {key, bubbles: true, cancelable: true})` on the
  editor page's `document` with `page.evaluate` and read `defaultPrevented` from the returned event; they live in
  `tests/test_fullscreen_e2e.py` and reuse its `deck_server` fixture and `_three_slide_deck`. **Obliged by:** BR-001
  to BR-004. **Rationale:** headless Chromium keeps the focus in the iframe whatever the test focuses (E4), so a
  pressed key never reaches the relay. **Alternatives considered:** a new test module importing the fixture (pytest
  would also collect imported names). **Source:** spec BT-010, E4. **Evidence:** `tests/test_fullscreen_e2e.py:243`.
- **DEC-003:** Vector figures are found by a pure pre pass, `vector_figure_warnings(slide, number)` in a new module
  `export/pptx_vectors.py` (5.2), called by `to_pptx` once per slide before its build, warnings appended with
  `report.warn` in document order. The advice sentence is the DOCX constant `SVG_ADVICE` imported from
  `export/to_docx.py:51`. **Obliged by:** BR-005, BR-007, BR-008. **Rationale:** one definition of a vector figure;
  no walker changes, so the slide XML is untouched. **Alternatives considered:** a report at each `SKIP_TAGS` site
  (seven sites, double visits). **Source:** design. **Evidence:** `export/to_pptx.py:99` to `:113`,
  `export/pptx_model.py:37` to `:54`.
- **DEC-004:** `pptx_images._image_source` returns `None` for a vector `src` before any decoding or path lookup, with
  no warning. Every caller passes an `<img>` `src` (`pptx_chrome.py:57`, `:81`, `:87`, `:112`, `:261`,
  `pptx_blocks.py:161`, `:170`, `pptx_images.py:36`, `:88`), so this silences exactly the vector images that the pre
  pass warns. **Obliged by:** BR-006, BR-008. **Rationale:** removes the two Python object warnings; non vector
  unreadable images keep both (BT-034). **Alternatives considered:** catching the library exception by message.
  **Source:** existing code `pptx_images.py:96` to `:151`. **Evidence:** `rg -n "_add_picture\(|_image_aspect\(" src/mcp_htmleditor/export`.
- **DEC-005:** BT-013's byte identity of `V`'s `ppt/slides/slide1.xml` is checked against a sha256 constant in
  `tests/test_export_pptx_vectors.py`, recorded during the RED run on the unfixed code (c507194 exporter) and copied
  into the test. **Obliged by:** BR-008. **Rationale:** the export is deterministic (the golden test relies on it);
  a hash recorded before the fix is the c507194 reference. **Alternatives considered:** comparing with the export of
  `V` stripped of its figures (not the same input). **Source:** spec BT-013. **Evidence:** `tests/test_export_golden.py:41`.
- **DEC-006:** Shell decks get the bootstrap's building blocks unchanged in behavior (5.3): the `:fullscreen` CSS
  block of `slides-empty.html:243` to `:259` adapted to each deck's classes (`.shell-header`, `.toolbar`,
  `.nav-arrow`, `.status-bar` hidden, `.stage` and `body` black, `.slide-frame` without padding, `.slide` scaled by
  `var(--fs-scale, 1)` from its center), a `<button id="btn-present" onclick="enterPresentation()">` inside
  `.toolbar`, `updateFullscreenScale()` as the last statement of `render()`, the two listeners, and the keydown
  table with the focus exception (adds space, `f`, `F`, `Escape` and the exception to today's handler, E14).
  **Obliged by:** BR-009 to BR-014, BR-017. **Rationale:** parity with the bootstraps (spec BUG-003 item 3).
  **Alternatives considered:** a fresh implementation per deck. **Source:** existing code
  `templates/bootstrap/slides-empty.html:373` to `:410`. **Evidence:** E28.
- **DEC-007:** Export invariance rule for every deck edit: each added CSS selector contains `:` (all start with
  `:fullscreen`) or `[`, so `_selector_target` rejects it (`pptx_style.py:558` `_SELECTOR_REJECT`); no class or
  attribute is added in the file to any element inside a slide; added elements are `<button>` and `<script>`, both in
  `SKIP_TAGS`, and lie outside every slide. **Obliged by:** BR-015. **Rationale:** the resolver indexes class
  selectors only, so such rules cannot reach the exported styles. **Alternatives considered:** none that keeps the
  hashes by construction. **Source:** existing code `export/pptx_style.py:558` to `:596`, `export/pptx_model.py:37`.
  **Evidence:** golden test `tests/test_export_golden.py:50`.
- **DEC-008:** Stacked decks: `#btn-present` is the first child of `<body>`, outside every slide,
  `position:fixed; top:16px; right:16px`; a script at the end of `<body>` holds `slides`, `current = 0`, `render`,
  `navigate`, `goToSlide` (5.3) and the building blocks. While presenting, only the slide carrying
  `data-fs-current` shows: `:fullscreen section[data-type="slide"]:not([data-fs-current]) { display:none }`,
  `:fullscreen section[data-type="slide"][data-fs-current] { margin:0; box-shadow:none; flex:none; scale:var(--fs-scale, 1); transform-origin:center center }`,
  `:fullscreen body { margin:0; height:100vh; overflow:hidden; display:flex; align-items:center; justify-content:center; background:#000 }`,
  `:fullscreen #btn-present { display:none }`. The marker exists only while presenting (set in `render` and on
  `fullscreenchange` entering, removed on leaving), then the current slide is scrolled into view
  (`scrollIntoView({block:'start'})`). The current slide starts at the first one; moves outside presenting change it
  (BR-012 business rule) and entering shows it (BR-010). **Obliged by:** BR-009 to BR-015, BR-017. **Rationale:**
  stacked layout untouched outside presenting; the marker never reaches a file saved outside presenting (R2).
  **Alternatives considered:** a class marker (would be indexed by the resolver if a class rule ever matched it, and
  saved); inline `display:none` on the other slides (saved by any save during presenting, more DOM writes).
  **Source:** design, spec BR-010, BR-012, BR-013. **Evidence:** `presentation-standard.html:21` to `:27`.
- **DEC-009:** Deck browser tests live in one module `tests/test_reference_decks_present_e2e.py`, parametrized over a
  `DECKS` tuple of `(file name, family, slide count)`; per deck two tests: `file` (copy to `tmp_path`, `page.goto`
  of its `file://` URL; click `#btn-present` and check BT-003, `Escape`, then `f` and the BT-017 key sequence, then
  BT-019's resize, then `Escape` and BT-018) and `editor` (one server per test as `deck_server`, `#present-btn`,
  then `End` with focus in the frame, BT-003's editor half and BT-020). Viewport 1600x900; asynchronous results
  through `wait_for_js`. **Obliged by:** BR-010 to BR-014, BR-017. **Rationale:** one page load serves several
  assertions, ten tests for the five decks keep the run time inside DEC-014. **Alternatives considered:** one test
  per BT and deck (about 30 browser tests). **Source:** design, user instruction (economical e2e). **Evidence:**
  `tests/test_fullscreen_e2e.py` `deck_server`.
- **DEC-010:** The c507194 reference of `example-carbon-complete.html` is a fixture
  `tests/testdata/example_carbon_complete_slide_hashes.json`, written with `slide_hashes()` of
  `tests/test_export_golden.py:41` from `git show c507194:templates/reference/slides/example-carbon-complete.html`
  before the deck is edited; the BT-032 test sits in `tests/test_export_golden.py` and reads that fixture, never
  `pptx_slide_hashes.json`. **Obliged by:** BR-015. **Rationale:** the golden file is pinned to exactly ten templates
  (`test_golden_file_covers_exactly_the_ten_templates`), and BT-031 forbids regenerating it. **Alternatives
  considered:** adding an eleventh golden entry (breaks the pinned set). **Source:** existing code
  `tests/test_export_golden.py:57`. **Evidence:** spec BT-032.
- **DEC-011:** The guard (5.4) is a parametrized test over `presentation_files(TEMPLATES_ROOT)` collected at import
  (one case per file, id = path relative to `templates/`), plus a test of the two pure functions on a `tmp_path`
  copy of `templates/` holding one more marker less file (BT-021), plus a BeautifulSoup check that each of the five
  decks' `#btn-present` has `onclick="enterPresentation()"` (BT-016). The discovered set is asserted to contain the
  eleven files of E17, not to equal it, so a later template needs no test edit. BT-004 is gate evidence: the guard
  run in a worktree of c507194 (`git worktree add`), its failing output kept in `.implement/US-0099-red.log`.
  **Obliged by:** BR-009, BR-016. **Rationale:** BR-016 business rule (discovery at run time); the guard can only
  land once the five decks comply (R6). **Alternatives considered:** a fixed file list (misses future files).
  **Source:** spec BR-016. **Evidence:** `tests/test_medical_template.py:86`.
- **DEC-012:** BR-018 to BR-020 are locked by tests only, no product change: BT-022 runs
  `[sys.executable, "-m", "mcp_htmleditor", "export", "docx", ...]` with `PATH` set to an empty `tmp_path` directory;
  BT-023 writes `<state_dir>/files/<key>/server.json` with `key = sha256(resolved path).hexdigest()[:32]`
  (`state.py:9`), starts `serve D --no-browser` as a child with `HTMLEDITOR_PORT=P`, polls `GET /status` through
  `wait_until`, then runs an MCP stdio session (`tests/stdio_support.py` `run_session`) calling `get_status`. RED
  evidence is a temporary mutation (a `EditorState.load()` call at server start, or the pandoc check bypassed), run
  once, logged, reverted. **Obliged by:** BR-018, BR-019, BR-020. **Rationale:** the spec keeps the code; a lock test
  is red only when the behavior regresses. **Alternatives considered:** deleting `load()` (BL-0009). **Source:**
  spec section 1.4. **Evidence:** E24, E25, E27.
- **DEC-013:** BR-021 is one sentence edit (5.5) and a test in `tests/test_skill_shipped.py` that reads every
  `skill/topics/*.md`, splits sentences on `. `, `: ` and line ends, and asserts no sentence holding `ibm-carbon`
  contains `:fullscreen` or `plein écran`, and that `skill --type slides-carbon` output still holds `dépassent 540 px`.
  **Obliged by:** BR-021. **Rationale:** the stronger check (no mention at all next to the deck name) is simple and
  holds today after the edit. **Alternatives considered:** a negation parser. **Source:** spec BT-024.
  **Evidence:** `rg -n "fullscreen|plein écran" skill/` (one hit, `slides-carbon.md:96`).
- **DEC-014:** Run time budget: the SPEC-0016 browser tests (relay tests and deck tests) take at most 40 s in total;
  each story reports `make test ARGS='-k <file> --durations=0'`; the closing story proves the `make check` test step
  stays at most 330 s (SPEC-0014/BT-022). **Obliged by:** n/a (no code impact): keeps SPEC-0014/BT-022 true.
  **Rationale:** about 95 s of headroom today. **Alternatives considered:** marking deck tests slow (would leave
  BR-017 out of the gate). **Source:** user instruction. **Evidence:** `.agent_docs/testing.md:218`.
- **DEC-015:** Slicing: seven stories. US-0095 relay `End` (`min_tier` 1: the focus pitfall makes a passing test
  prove nothing); US-0096 PPTX vector warnings (`min_tier` 2); US-0097 shell decks (`min_tier` 1: scaling and the
  export invariance of DEC-007); US-0098 stacked decks (`min_tier` 1: new script, marker lifetime, scaling of a
  `min-height` slide); US-0099 discovery guard (`min_tier` 2); US-0100 arbitration locks (`min_tier` 2); US-0101
  skill sentence, documentation and converge (closing, `min_tier` 2). **Obliged by:** n/a (no code impact):
  partition; every requirement is covered in section 11. **Rationale:** files touched is the binding budget; one
  story per defect site, the decks split by family as the user asked. **Alternatives considered:** one story for the
  five decks (8 files plus tests, past the tier 1 budget). **Source:** design, user instruction.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0095 | End relayed by the editor page | P2 | BR-001, BR-002, BR-003, BR-004 | main | 1 | no |
| US-0096 | vector figures named in the PPTX warnings | P1 | BR-005, BR-006, BR-007, BR-008 | main | 2 | no |
| US-0097 | presentation mode of the shell decks | P1 | BR-009 (partial), BR-010, BR-011, BR-012, BR-013 (partial), BR-014, BR-015, BR-017 | main | 1 | no |
| US-0098 | presentation mode of the stacked decks | P1 | BR-009 (partial), BR-010, BR-011, BR-012, BR-013, BR-014, BR-015, BR-017 | US-0097 | 1 | no |
| US-0099 | guard over every presentation template | P2 | BR-009, BR-016 | US-0098 | 2 | no |
| US-0100 | lock the pandoc and server record arbitrations | P3 | BR-018, BR-019, BR-020 | main | 2 | no |
| US-0101 | skill sentence, documentation and converge | P2 | BR-021 | US-0095, US-0096, US-0099, US-0100 | 2 | yes |
