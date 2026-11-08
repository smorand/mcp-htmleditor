# Reference decks without presentation mode, End ignored by the editor, vector figures dropped silently from PPTX: Bug Specification

> Generated on: 2026-11-08
> Id: SPEC-0016
> Nature: BUG
> Depth: L
> Depth evidence: 4 modules (reference slide templates, browser editor script, PPTX exporter, test suite guard) plus two arbitrations on the state store and the DOCX exporter; 21 requirements; no HTTP contract change; no data model change
> Status: implemented
> Verdict: authority exists (BUG-001, BUG-002, BUG-003); no authority for the two arbitrations of section 1.4 (defect class: wrong)
> Defect class: n/a for BUG-001 to BUG-003; wrong for legacy FR-010 (reload clause) and legacy FR-016 (pandoc clause)
> Severity: Medium (BUG-003), Low (BUG-001, BUG-002)
> From backlog: BL-0006, BL-0007
> Security: n/a
> CVSS: n/a
> Affected: every version up to c507194 (main, 2026-11-08)
> Fixed in: unreleased

Three defects and two arbitrations left over from the retrospective of SPEC-0001. File and line
citations are in the Evidence appendix (E ids). Every reproduction below was run on c507194, in
real headless Chromium through `make test` and through `make run`, with throwaway files kept
outside the repository (`/tmp/spec16/`). SPEC-0001 is not modified: where this spec restores or
withdraws one of its statements, section 5 says which.

Terms. **Deck**: an HTML file whose `<html>` carries `data-doc-type="presentation"`. **The five
decks**: `templates/reference/slides/ibm-carbon.html`, `example-ei-complete.html`,
`example-carbon-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html`. **Shell
decks**: the first three, which have a navigation toolbar and show one slide at a time (E14).
**Stacked decks**: the last two, which have no toolbar, no script, and show every slide one under
the other (E15). **Slide**: an element carrying `data-type="slide"`. **Editor page**: the page
served by `mcp-htmleditor serve` at `/`, which shows the deck in the iframe `#content-frame` and
has the button `#present-btn` (E5). **Presenting**: the deck's own document (its `<html>`) is the
fullscreen element.

## 1. Defects

### BUG-001: End does not go to the last slide when the editor page holds the keyboard

- **Observed behavior:** reproduced on 2026-11-08 with a three slide EI deck served by the
  editor, `#present-btn` clicked, then `keydown` events dispatched on the editor page's
  `document` (what a browser that leaves focus on the editor page delivers): `ArrowRight` moves
  `#progress-tag` from `1 / 3` to `2 / 3`, `Home` to `1 / 3`, `End` leaves `1 / 3`; after another
  `ArrowRight`, `End` leaves `2 / 3`. When focus is inside the iframe, `End` reaches `3 / 3`
  through the deck's own handler.
- **Expected per authority:** legacy SPEC-0001/FR-028 (E1): the system routes "`Home`/`End`
  (première/dernière slide)" to the slide's navigation "quel que soit l'élément DOM qui détient
  effectivement le focus clavier". The as built SPEC-0001/FR-028 dropped End because the code
  lacks it (E2), it did not decide against it.
- **Reproduction:** as above. Expected: `3 / 3`. Actual: unchanged (`1 / 3`, then `2 / 3`).
- **Root cause:** the editor page's relay of navigation keys handles `ArrowRight`, `ArrowDown`,
  space, `ArrowLeft`, `ArrowUp`, `Home` and `Escape`, and has no branch for `End`
  (`src/mcp_htmleditor/static/editor.js:152` to `:167`, E3).
- **Contributing factors:** the regression test of the relay
  (`tests/test_fullscreen_e2e.py:243`, E4) calls `document.body.focus()`, which does not take
  focus from the iframe in headless Chromium (measured: `document.activeElement` stays
  `content-frame`), so it exercises the deck's own handler and never the relay.
- **Impact:** in a browser that leaves focus on the editor page, a presenter cannot jump to the
  last slide. Workaround: click into the slide once. Low.
- **Rollback posture:** a revert restores today's behavior; nothing persisted changes.

### BUG-002: The PPTX export drops vector figures without saying so

- **Observed behavior:** reproduced on 2026-11-08 with the Carbon bootstrap whose slide body
  holds `<svg>` inline, `<img src="fig.svg">` and `<img src="data:image/svg+xml;base64,...">`:
  `make run ARGS='export pptx svg.html svg.pptx'` exits 0, prints `Done. 1 slide(s) exportee(s).`
  and four warnings: two `Image non decodable ignoree: cannot identify image file <_io.BytesIO
  object at 0x...>` and two `Image non inseree (cannot identify image file <_io.BytesIO object at
  0x...>): fig.svg` (and the data URI). Nothing names the inline `<svg>`, which is absent from
  the slide. Every vector image gets two warnings, neither says "SVG" or what to do.
- **Expected per authority:** legacy SPEC-0001/FR-018 (E6): "IF une figure au format SVG
  (fichier, data URI, ou balise inline) est détectée dans un export (PPTX ou DOCX) THEN THE
  système SHALL ajouter un warning recommandant un format PNG, SANS bloquer l'export." The as
  built FR-018 scoped it to DOCX because the deck warning was not found (E2), not by decision.
  The documentation also promises the diagnostic (E7).
- **Reproduction:** as above. Expected: one warning per figure recommending PNG. Actual: inline
  vector silent; each vector image two warnings with a Python object address.
- **Root cause:** the PPTX model lists `svg` among the tags never exported
  (`src/mcp_htmleditor/export/pptx_model.py:45`, E8), and every walker skips those tags without a
  report (E9). Vector images reach the picture library, which cannot read SVG; the failure is
  reported once when measuring and once when inserting (E10).
- **Contributing factors:** the DOCX exporter has a vector diagnostic (E11) that the PPTX
  exporter never got.
- **Impact:** a deck author learns that a diagram is missing only by opening the PPTX. Low.
- **Rollback posture:** a revert restores today's warnings; the PPTX file itself is unchanged.

### BUG-003: Five reference decks have no presentation mode, and nothing guards it

- **Observed behavior:** reproduced on 2026-11-08 in Chromium at 1600x900, each of the five decks
  copied out of the repository:
  1. Opened directly (`file://`): `#btn-present` count is 0; pressing `f` leaves
     `document.fullscreenElement` `null`.
  2. Served by the editor, `#present-btn` clicked: the deck's `<html>` becomes fullscreen, but
     `--fs-scale` is empty and nothing is scaled. Shell decks keep their toolbar
     (`display: flex`) and show the slide at its design size (`ibm-carbon` 900x626,
     `example-ei-complete` 960x540, `example-carbon-complete` 900x476) in a 1600x900 screen.
     Stacked decks show two slides at once (`presentation-standard`) or a 1280x720 slide
     (`roadmap-one-pager`), and `ArrowRight` changes nothing (no `.slide.active`, no script).
  3. The same two steps on `templates/bootstrap/slides-empty.html` and `slides-ei-empty.html`:
     `#btn-present` present with `onclick="enterPresentation()"`, `f` gives fullscreen,
     `--fs-scale` is `1.6666666666666667`, the active slide measures 1600x900, the toolbar is
     `display: none`.
- **Expected per authority:** `AGENTS.md:79` to `:82` (E12): "Every slide template (current and
  future) must ship fullscreen support (`:fullscreen` CSS, `#btn-present` button,
  `enterPresentation`/`exitPresentation`/`updateFullscreenScale` JS) ... A presentation file
  missing it ... is a bug to patch, not a valid variant." The three building blocks and their
  behavior are in `.agent_docs/html-conventions.md:53` to `:82` (E13); the constitution records
  the rule and its violation (E16).
- **Reproduction:** items 1 and 2. Expected: as item 3. Actual: as items 1 and 2.
- **Root cause:** the five files contain none of the five markers: `rg -c` gives 0 for
  `:fullscreen`, `btn-present`, `enterPresentation`, `exitPresentation` and
  `updateFullscreenScale` in each (E17); the stacked decks contain no `<script>` and no
  `keydown` handler at all (E15). The only automated check covers the medical bootstrap
  (`tests/test_medical_template.py:86` to `:91`, E18).
- **Contributing factors:** the rule was added after these files existed (legacy TBD-011, E19)
  and was propagated by hand to the bootstraps only; `skill/topics/slides-carbon.md:96` (E20)
  documents the gap instead of closing it.
- **Impact:** a deck started by copying one of the five (the skill points authors to
  `ibm-carbon.html` and `example-ei-complete.html` as references, E21) never gets presentation
  mode; the editor's present button yields an unscaled page with its toolbar. Medium.
- **Rollback posture:** a revert restores today's files; the PPTX export of the five decks does
  not change (BR-015), so no exported artifact depends on the fix.

### 1.4 Arbitrations of BL-0006 (no defect reproduced, legacy promise withdrawn)

BL-0006 listed legacy statements the code contradicts. FR-007 was settled by SPEC-0009; FR-018
and FR-028 are BUG-002 and BUG-001 above. FR-009 (exactly 6 tools) and FR-012 (exactly 5
charters) are growth already recorded as built in SPEC-0001 (E2); nothing to decide. Two remain:

- **Legacy FR-010, "et le recharger à l'initialisation"** (E22). Code: the server record moved
  to the state directory (`src/mcp_htmleditor/state.py:4` to `:8`, E23); `EditorState.load()`
  exists (`state.py:165`) and has no caller in `src` (E24). A new process therefore never adopts
  a port, process id or poll interval recorded by an earlier one, while `get_status` in a
  process that serves nothing does report the port and process id recorded for the last served
  file (`state.py:203` to `:219`, E25). **Decision (recommended default, applied):** the code is
  right, the legacy clause is wrong (class `wrong`): reloading would make a restarted server
  claim a port and a process id that belong to a process that has perhaps exited (legacy TBD-007).
  BR-019 and BR-020 lock today's behavior. The unused `load()` stays the DEBT entry BL-0009.
- **Legacy FR-016, "IF pandoc est absent ... THEN ... styles pandoc par défaut ... SANS lever
  d'exception"** (E26). Code: reproduced on 2026-11-08 with `PATH` lacking pandoc,
  `make run ARGS='export docx doc.html doc.docx'` prints
  `error: pandoc not found in PATH: install pandoc to export to DOCX.`, exits 1 and writes no file
  (E27). **Decision (recommended default, applied):** the code is right, the legacy clause is
  wrong (class `wrong`): without pandoc no DOCX can be produced at all, so "default styles" is not
  a reachable outcome; an explicit failure is the as built SPEC-0001/FR-034. BR-018 locks it.
  The two other clauses of legacy FR-016 (unknown charter, reference document not built) are
  implemented and stay governed by as built FR-016.

## 2. Expected Behavior

Casing and names follow the code: key names as `KeyboardEvent.key` values (`ArrowRight`, `End`,
`Escape`, `f`); element ids and attributes as written in the templates (`#btn-present`,
`#present-btn`, `#content-frame`, `--fs-scale`, `data-doc-type`); warning texts in the
exporter's language and spelling (French without accents, as every existing PPTX warning, E10).

### Editor key relay (BUG-001)

#### BR-001 [EARS-S]: End goes to the last slide
> WHILE the deck shown in `#content-frame` is presenting THE editor page SHALL show the deck's last slide when a `keydown` whose `key` is `End` reaches the editor page's `document`.

- **Source:** restored from legacy SPEC-0001/FR-028 (E1).
- **Business Rules:** "show the last slide" means the deck's `goToSlide(n - 1)` with `n` the
  number of slides, the same call the deck's own `End` handler makes (E28); its default action
  (page scroll) is prevented.

#### BR-002 [EARS-S]: The whole key table, once per key press
> WHILE the deck shown in `#content-frame` is presenting THE editor page and the deck together SHALL move exactly one slide forward on `ArrowRight`, `ArrowDown` or ` ` (space), one slide back on `ArrowLeft` or `ArrowUp`, to the first slide on `Home`, to the last slide on `End`, and leave presenting on `Escape`, whichever of the two documents receives the `keydown`.

- **Source:** restored from legacy SPEC-0001/FR-028 (E1); as built FR-028 for every key but
  `End` (E2).
- **Business Rules:** forward on the last slide and back on the first change nothing; one key
  press never moves two slides.

#### BR-003 [EARS-O]: Deck without navigation globals
> IF the deck shown in `#content-frame` defines no `goToSlide` function THEN THE editor page SHALL ignore `End` and `Home` without raising a page error.

- **Source:** decided here; mirrors today's guard for `Home` (E3).

#### BR-004 [EARS-UB]: No relay outside presenting
> The editor page SHALL NOT act on `End`, `Home`, arrows, space or `Escape` while the deck is not presenting.

- **Source:** restored from today's behavior (E3: the relay returns when nothing is fullscreen).

### Vector figures in the PPTX export (BUG-002)

A vector figure is, inside a slide: an `<svg>` element that is not inside another `<svg>`; an
`<img>` whose `src`, cut at the first `?` and lowercased, ends with `.svg`; an `<img>` whose
`src` lowercased starts with `data:image/svg`. A slide is an exported slide element, or the body
when the document has none and is exported as one slide (E34). The slide number `N` is the 1
based position of the slide in the export, as counted by `Done. N slide(s) exportee(s).`

#### BR-005 [EARS-E]: Inline vector warned
> WHEN the PPTX export meets an inline `<svg>` vector figure in slide `N` THE exporter SHALL add the warning `Slide N: balise <svg> en ligne ignoree, l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG.`

- **Source:** restored from legacy SPEC-0001/FR-018 (E6); advice sentence as the DOCX exporter
  writes it (E11).
- **Business Rules:** one warning per occurrence, in document order; the CLI prints each as
  `Attention: <warning>` on stderr (E29); the agent tool returns it in its warnings (E29).

#### BR-006 [EARS-E]: Vector image warned once
> WHEN the PPTX export meets an `<img>` vector figure in slide `N` THE exporter SHALL add exactly one warning for it, `Slide N: image SVG ignoree (<src>), l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG.`, and no other warning about that image.

- **Source:** restored from legacy SPEC-0001/FR-018 (E6); the "exactly one" decided here.
- **Business Rules:** `<src>` is the attribute value cut to its first 60 characters, the length
  the remote image warning already uses (E10). The two warnings of today (`Image non decodable
  ignoree: ...`, `Image non inseree (...)`) are not emitted for a vector figure; they stay for
  any other unreadable image.

#### BR-007 [EARS-UB]: No warning for vectors that were never content
> The PPTX exporter SHALL NOT warn about an `<svg>` outside every slide, an `<svg>` inside another `<svg>`, or an `<svg>` or `<img>` inside a `<button>`, `<script>`, `<template>`, `<noscript>` or `<select>`.

- **Source:** decided here: those are the navigation shell's icons and interactive widgets, never
  exported (E8, E30). The Carbon and EI bootstraps carry shell icons outside their slides (E31).

#### BR-008 [EARS-U]: The export is not blocked
> The PPTX export of a deck holding vector figures SHALL produce the same slides, the same slide count and the same exit status as today.

- **Source:** restored from legacy SPEC-0001/FR-018 ("SANS bloquer l'export", E6).
- **Business Rules:** only the warning list changes; the slide XML is byte identical.

### Presentation mode of the five decks (BUG-003)

Let `w` and `h` be the width and height of the current slide's box at scale 1, `W` and `H` the
viewport's inner width and height, and `s = min(W / w, H / h)`.

#### BR-009 [EARS-U]: The five building blocks are present
> Each of the five decks SHALL contain a `:fullscreen` CSS rule, one element with `id="btn-present"` whose activation calls `enterPresentation()`, and script functions named `enterPresentation`, `exitPresentation` and `updateFullscreenScale`.

- **Source:** restored from `AGENTS.md:79` to `:82` (E12) and `.agent_docs/html-conventions.md`
  (E13).

#### BR-010 [EARS-E]: Entering presents one slide, uniformly scaled
> WHEN a deck among the five enters presenting, by activating `#btn-present`, by the key `f` or `F`, or by the editor page's `#present-btn` THE deck SHALL show exactly one slide, the current one, centered, with `--fs-scale` set on `<html>` to `s` and its visible box measuring `w * s` by `h * s` within 1 pixel.

- **Source:** restored from E13 (point 3 and the `--fs-scale` paragraph) and SPEC-0001/FR-027
  (E2); parity with the bootstraps (section 1, BUG-003 item 3).
- **Business Rules:** the current slide of a shell deck is the one shown before entering; of a
  stacked deck, the first slide. The page background behind the slide is `rgb(0, 0, 0)`.

#### BR-011 [EARS-S]: Nothing but the slide while presenting
> WHILE a deck among the five is presenting THE deck SHALL display no element outside the current slide: its `.toolbar`, `.shell-header`, `.nav-arrow`, `.status-bar`, `#btn-present` and every other slide have computed `display: none` or lie entirely outside the viewport.

- **Source:** restored from E13 point 1.

#### BR-012 [EARS-S]: Keys of the deck
> WHILE a deck among the five is open and its focused element is none of editable text, an `<input>`, a `<textarea>` or a `<select>` THE deck SHALL move one slide forward on `ArrowRight`, `ArrowDown` or space, one slide back on `ArrowLeft` or `ArrowUp`, to the first slide on `Home`, to the last on `End`, enter presenting on `f` or `F`, and leave presenting on `Escape`.

- **Source:** restored from E13 point 3 (`f`, `F`, `Escape`) and legacy SPEC-0001/FR-028 (E1);
  focus exception as in the bootstraps (E28).
- **Business Rules:** forward on the last slide and back on the first change nothing. In a
  stacked deck outside presenting, the moves change which slide is current (used on entering,
  BR-010, and on leaving, BR-013) and scroll it into view.

#### BR-013 [EARS-E]: Leaving keeps the current slide
> WHEN a deck among the five leaves presenting THE deck SHALL remove `--fs-scale` from `<html>`, keep the current slide current, and show its layout of before entering: the shell deck with its toolbar and the current slide, the stacked deck with every slide one under the other and the current slide's top edge inside the viewport.

- **Source:** restored from SPEC-0001/E2E-041 (E4) for shell decks; stacked decks decided here.

#### BR-014 [EARS-E]: Window resized while presenting
> WHEN the viewport changes size while a deck among the five is presenting THE deck SHALL set `--fs-scale` to the `s` of the new size.

- **Source:** restored from E13 point 3 (`resize` listener).

#### BR-015 [EARS-UB]: Exports and layout outside presenting unchanged
> The five decks SHALL NOT change their PPTX export: the slide XML hashes recorded for `ibm-carbon.html`, `example-ei-complete.html`, `presentation-standard.html` and `roadmap-one-pager.html` stay equal to their golden values, and `example-carbon-complete.html` exports 9 slides whose slide XML is byte identical to its export at c507194.

- **Source:** decided here; the golden hashes are the existing contract of the exporter (E32).
- **Business Rules:** outside presenting, a shell deck shows what it shows today; a stacked deck
  shows every slide one under the other as today, plus `#btn-present`, which is not inside any
  slide.

#### BR-016 [EARS-O]: Missing building block fails the test suite
> IF an HTML file under `templates/` has `data-doc-type="presentation"` on its `<html>` and lacks one of the five markers of BR-009 THEN `make test` and `make check` SHALL fail with a message naming the file's path and the missing marker.

- **Source:** restored from `AGENTS.md:79` ("current and future", E12) and the constitution's
  rule (E16), whose "Enforced by" column covers only the medical bootstrap (E18).
- **Business Rules:** the set of files is discovered when the tests run, so a file added later is
  checked without editing the test; installed copies outside the repository are not checked.

#### BR-017 [EARS-U]: Same behavior opened directly or served
> Each of the five decks SHALL behave per BR-010 to BR-014 both when opened as a `file://` URL and when shown in the editor page.

- **Source:** decided here; the editor shows the deck's own document (E5), and SPEC-0001/FR-027
  requires presentation mode from the file itself (E2).

### Arbitrations (BL-0006)

#### BR-018 [EARS-O]: DOCX export without pandoc fails explicitly
> IF `pandoc` is not found on `PATH` THEN `mcp-htmleditor export docx <in> <out>` SHALL print `error: pandoc not found in PATH: install pandoc to export to DOCX.` on stderr, exit with status 1, and leave no file at `<out>`.

- **Source:** restored from as built SPEC-0001/FR-034 (E2) and today's behavior (E27); legacy
  FR-016's pandoc clause withdrawn (section 1.4).

#### BR-019 [EARS-UB]: No adoption of an earlier process's record
> The editor SHALL NOT take the port, process id or poll interval of a server it starts from a server record written by another process.

- **Source:** restored from today's behavior (E24); legacy FR-010's reload clause withdrawn
  (section 1.4).
- **Business Rules:** the port is the explicit `--port` or `port`, else the first free one of
  SPEC-0001/FR-029 from `HTMLEDITOR_PORT`; the poll interval is `--poll`, else
  `HTMLEDITOR_POLL_INTERVAL`, else 1000.

#### BR-020 [EARS-S]: Status of a process that serves nothing
> WHILE a process serves no file THE agent tool `get_status()` SHALL report the `port` and `pid` recorded for the file named by the state directory's `last.json`, when that record is readable.

- **Source:** restored from today's behavior (E25); the part of legacy FR-010 that the code keeps.

#### BR-021 [EARS-U]: Documentation matches the fixed decks
> The shipped skill text SHALL NOT state that `ibm-carbon.html` or any of the five decks lacks fullscreen support or `:fullscreen` CSS.

- **Source:** decided here: `skill/topics/slides-carbon.md:96` (E20) becomes false once BR-009
  holds, and the skill is what agents read before copying a deck.
- **Business Rules:** the statement about the 540 px height budget of `ibm-carbon.html` in the
  same sentence is true and stays.

## 3. Edge Cases

| Case | Expected behavior | Requirement |
|------|-------------------|-------------|
| `End` relayed while already on the last slide | stays on the last slide, no error | BR-001, BR-002 |
| `End` pressed with focus inside the iframe | handled once by the deck, last slide | BR-002 |
| `End` while editing text in edit mode, not presenting | the caret moves; no slide change | BR-004, BR-012 |
| Deck in the editor without `goToSlide` (document mode, website) | `End`, `Home` ignored, no page error | BR-003 |
| `<svg>` holding an `<svg>` inside a slide | one warning | BR-005, BR-007 |
| Two identical inline `<svg>` in two slides | two warnings, `Slide 1: ...` and `Slide 2: ...` | BR-005 |
| `<img src="Fig.SVG?v=2">` | one BR-006 warning with `src` `Fig.SVG?v=2` | BR-006 |
| `<img src="fig.svgz">` | not a vector figure here; today's warnings unchanged | BR-006 |
| Shell icon `<svg>` in `.toolbar` or a `<button>` | no warning | BR-007 |
| Document without any slide holding an `<svg>` in its body | today's single slide and its warning, plus the `<svg>` warned as `Slide 1: ...` unless inside an element of BR-007 | BR-005, BR-007 |
| `ibm-carbon.html` slide taller than 540 px (626 px) presented at 1600x900 | `s = 900 / 626`, whole slide visible, letterboxed horizontally | BR-010 |
| Viewport not 16:9 (1600x1000) | `s = min(...)`, no distortion | BR-010 |
| Stacked deck presenting, `ArrowRight` on the last slide | stays | BR-012 |
| Stacked deck, `Escape` after reaching slide 3 | stacked layout, slide 3 top edge in the viewport | BR-013 |
| `f` typed in an editable text of a deck in edit mode | text gets `f`, no fullscreen | BR-012 |
| New file `templates/reference/slides/x.html` without the markers | `make test` fails naming `x.html` | BR-016 |
| File under `templates/` with `data-doc-type="document"` | not checked | BR-016 |
| Server record left with `port` 7845 by a dead process | a new `serve` without `--port` ignores it | BR-019 |

## 4. Tests

Let `D3` be the three slide EI deck built from the `ei` bootstrap by the existing fixture of
`tests/test_fullscreen_e2e.py` (E4); `P` a free port; `HTMLEDITOR_TEMPLATES_DIR` the repository's
`templates/`; `HTMLEDITOR_STATE_DIR` under `tmp_path`; `HTMLEDITOR_HOST=127.0.0.1`. Browser tests
run Playwright Chromium at a 1600x900 viewport unless stated, and observe asynchronous results
per SPEC-0014/BR-008. `DECK` ranges over the five decks, each copied to `tmp_path`.

### 4.1 End to end reproduction (mandatory)

#### BT-001: End relayed by the editor page
- **Reproduces:** BUG-001
- **Driver:** Playwright Chromium on the editor page of `mcp-htmleditor` serving `D3`
- **Fails today because:** the relay has no `End` branch (E3)
- Given `D3` served on `P`, the editor page loaded, `#present-btn` clicked and the deck's `<html>` fullscreen
- When `document.dispatchEvent(new KeyboardEvent('keydown', {key: 'End', bubbles: true, cancelable: true}))` runs in the editor page
- Then the deck's `#progress-tag` reads `3 / 3`

#### BT-002: Vector figures named in the PPTX warnings
- **Reproduces:** BUG-002
- **Driver:** CLI `mcp-htmleditor export pptx`
- **Fails today because:** `svg` is skipped without a report and vector images fail twice in the picture library (E8 to E10)
- Given `V`, the Carbon bootstrap whose slide body starts with `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="red"/></svg><img src="fig.svg" alt="f"><img src="data:image/svg+xml;base64,<base64 of that svg>" alt="d">`, and `fig.svg` holding that svg next to it
- When `mcp-htmleditor export pptx V out.pptx`
- Then exit status 0, stdout ends with `Done. 1 slide(s) exportee(s).`, and stderr holds exactly these three lines, in this order:
  `Attention: Slide 1: balise <svg> en ligne ignoree, l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG.`,
  `Attention: Slide 1: image SVG ignoree (fig.svg), l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG.`,
  `Attention: Slide 1: image SVG ignoree (data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My), l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG.`
- And stderr contains neither `Image non decodable` nor `Image non inseree`

#### BT-003: Each reference deck presents like a bootstrap
- **Reproduces:** BUG-003
- **Driver:** Playwright Chromium, parametrized over `DECK`, on the `file://` URL of the copy
- **Fails today because:** the decks have no `#btn-present`, no `:fullscreen` rule and no scale function (E17)
- Given `DECK` opened
- When `#btn-present` is clicked
- Then the deck's `<html>` is `document.fullscreenElement`, `--fs-scale` on `<html>` equals `s` within `1e-6`, the current slide's bounding box measures `w * s` by `h * s` within 1 pixel, and BR-011 holds
- And for the editor path: with `DECK` served on `P` and `#present-btn` clicked, the same three assertions hold inside `#content-frame`

#### BT-004: The guard catches a deck without the building blocks
- **Reproduces:** BUG-003 (the "nothing guards them" half)
- **Driver:** `make test` on the repository
- **Fails today because:** no such guard exists; the only check reads the medical bootstrap (E18), so `make test` passes with the five decks unfixed
- Given the repository at c507194 plus the BR-016 guard, the five decks left as they are
- When `make test` runs
- Then it fails, and its output names each of `reference/slides/ibm-carbon.html`, `example-ei-complete.html`, `example-carbon-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html` with the marker `:fullscreen`

### 4.2 New behavior

#### BT-010: Full key table through the relay
- **Validates:** BR-001, BR-002
- Given `D3` presenting in the editor page, on slide 1
- When keydowns are dispatched on the editor page's `document` in the order `End`, `End`, `ArrowLeft`, `Home`, ` `, `ArrowDown`, `ArrowUp`, `ArrowRight`, `ArrowRight`
- Then `#progress-tag` reads, after each, `3 / 3`, `3 / 3`, `2 / 3`, `1 / 3`, `2 / 3`, `3 / 3`, `2 / 3`, `3 / 3`, `3 / 3`
- And each dispatched `End`, ` ` and arrow event has `defaultPrevented` `true`
- When `Escape` is dispatched the same way
- Then `document.fullscreenElement` is `null` within 2 seconds

#### BT-011: One move per key whichever document gets it
- **Validates:** BR-002
- Given `D3` presenting in the editor page, on slide 1, focus in `#content-frame` (`document.activeElement.id` is `content-frame`)
- When `page.keyboard.press("End")`, then `page.keyboard.press("ArrowLeft")`
- Then `#progress-tag` reads `3 / 3`, then `2 / 3`

#### BT-012: Relay tolerates a deck without navigation
- **Validates:** BR-003, BR-004
- Given the editor page serving the `doc` bootstrap with its `<html>` fullscreen (`document.getElementById('content-frame').contentDocument.documentElement.requestFullscreen()`)
- When `End` and `Home` keydowns are dispatched on the editor page's `document`
- Then no `pageerror` event fires and the document's text is unchanged
- Given `D3` in the editor page, edit mode on, not presenting, caret inside the title
- When `End` is dispatched on the editor page's `document`
- Then `#progress-tag` still reads `1 / 3`

#### BT-013: Vector figures that are not content stay silent
- **Validates:** BR-007, BR-008
- Given `C`, the Carbon bootstrap unchanged (shell icons only, E31); `B`, a copy of `V` (BT-002) whose inline `<svg>` is wrapped in `<button>`; `N`, a copy of `V` whose inline `<svg>` holds a second `<svg>`
- When the three are exported to PPTX
- Then `C` gives no warning containing `SVG` or `svg`; `B` gives exactly the two `image SVG ignoree` warnings of BT-002; `N` gives exactly the three warnings of BT-002
- And `out.pptx` of `V` has 1 slide and its `ppt/slides/slide1.xml` is byte identical to the export of `V` at c507194

#### BT-014: Numbering, order and case of vector warnings
- **Validates:** BR-005, BR-006
- Given a three slide Carbon deck: slide 1 none, slide 2 an inline `<svg>` then `<img src="Fig.SVG?v=2">`, slide 3 an inline `<svg>` identical to slide 2's
- When exported to PPTX
- Then the warnings are, in order: `Slide 2: balise <svg> en ligne ignoree, ...`, `Slide 2: image SVG ignoree (Fig.SVG?v=2), ...`, `Slide 3: balise <svg> en ligne ignoree, ...` (each ending with `Regle: figures en PNG, jamais en SVG.`), and nothing else

#### BT-015: Warnings through the agent tool
- **Validates:** BR-005
- Given `V`
- When the agent tool `export(file=V, format="pptx", output=out.pptx)` is called over stdio
- Then it answers `"ok": true` and its `warnings` list equals the three BT-002 warnings without the `Attention: ` prefix

#### BT-016: Building blocks of the five decks
- **Validates:** BR-009
- Given each of the five files
- Then it contains `:fullscreen`, `id="btn-present"`, `enterPresentation`, `exitPresentation` and `updateFullscreenScale`, and the element `#btn-present` has `onclick="enterPresentation()"` or an equivalent listener (clicking it in Chromium makes `<html>` fullscreen, BT-003)

#### BT-017: Presenting hides everything else, keys work
- **Validates:** BR-010, BR-011, BR-012
- Given `DECK` presenting from `file://`, entered by the key `f`
- Then BR-010's measures hold, every element of BR-011 has `display: none` or a bounding box outside the viewport, and the number of slides intersecting the viewport is 1
- When `End`, then `ArrowLeft`, then `Home`, then `ArrowLeft` are pressed
- Then the current slide is, after each, the last, the one before the last (or the last for `roadmap-one-pager.html`, which has one slide), the first, the first
- And the scale assertions of BR-010 hold after each move

#### BT-018: Leaving presenting
- **Validates:** BR-013
- Given a shell deck presenting on slide 3 (`End`, then `ArrowLeft` until slide 3)
- When `Escape`
- Then `document.fullscreenElement` is `null`, `--fs-scale` is absent from `<html>`'s inline style, slide 3 is current and the `.toolbar` is displayed
- Given `presentation-standard.html` presenting on slide 3
- When `Escape`
- Then the four slides are displayed one under the other, `--fs-scale` is absent, and slide 3's top edge lies between 0 and the viewport height

#### BT-019: Resize while presenting
- **Validates:** BR-014
- Given `DECK` presenting at 1600x900
- When the viewport becomes 1200x900
- Then `--fs-scale` equals the new `s` within `1e-6`

#### BT-020: Editor and file paths agree
- **Validates:** BR-017
- Given `DECK` served on `P` and shown in the editor page
- When `#present-btn` is clicked, then `End` pressed with focus in `#content-frame`
- Then BR-010's measures hold in `#content-frame` and the last slide is current

#### BT-021: Guard over every presentation template
- **Validates:** BR-016
- Given the repository's `templates/`
- Then the guard passes on every file with `data-doc-type="presentation"` (11 today: 3 bootstraps and 8 reference decks, E17) and skips the others
- Given a copy of `templates/` under `tmp_path` with one more file `reference/slides/x.html` holding `<html data-doc-type="presentation">` and a single slide, no marker
- Then the guard fails naming `reference/slides/x.html` and each of the five markers

#### BT-022: DOCX export without pandoc
- **Validates:** BR-018
- Given the `doc` bootstrap copied to `tmp_path`, and `PATH` holding no `pandoc`
- When `mcp-htmleditor export docx doc.html doc.docx`
- Then exit status 1, stderr is `error: pandoc not found in PATH: install pandoc to export to DOCX.`, and `doc.docx` does not exist

#### BT-023: A stale server record is not adopted
- **Validates:** BR-019, BR-020
- Given `HTMLEDITOR_PORT=P`, a deck `D`, and `<state_dir>/files/<key of D>/server.json` holding `{"file": "<D>", "port": 7845, "pid": 999999, "poll_interval": 5000}` written before any process starts
- When `mcp-htmleditor serve D` runs (no `--port`, no `--poll`)
- Then `GET /status` on `P` answers `"port": P` and `"poll_interval": 1000`
- Given a new `mcp-htmleditor mcp` process serving nothing, and `last.json` naming `D` while the `serve` above runs
- When `get_status()` is called
- Then it reports `"running": false`, `"port": P` and the `serve` process's `pid`

#### BT-024: Skill text no longer states the gap
- **Validates:** BR-021
- When the shipped skill topics are searched for `ibm-carbon` together with `:fullscreen` or `plein écran` in one sentence
- Then no sentence says the deck lacks them, and `skill/topics/slides-carbon.md` still states the 540 px budget of `ibm-carbon.html`

### 4.3 Non regression

#### BT-030: Existing fullscreen tests unchanged
- **Protects:** SPEC-0001/FR-026 to FR-028, E2E-038 to E2E-041
- When the four tests of `tests/test_fullscreen_e2e.py` run
- Then they pass with their current assertions

#### BT-031: Golden PPTX hashes unchanged
- **Protects:** BR-015, the exporter's golden contract (E32)
- When `tests/test_export_golden.py` runs
- Then every template, the four decks among the five included, matches `tests/testdata/pptx_slide_hashes.json` without regenerating it

#### BT-032: `example-carbon-complete.html` export unchanged
- **Protects:** BR-015
- Given the file's export at c507194 kept as a fixture (slide XML of its 9 slides)
- When the fixed file is exported
- Then 9 slides, each `ppt/slides/slideK.xml` byte identical

#### BT-033: Decks without vector figures still warn nothing
- **Protects:** BR-007
- When `tests/test_medical_template.py::test_medical_decks_export_every_slide_without_warning` and the five `report.warnings == []` tests of `tests/test_export_pptx.py` run (E33)
- Then they pass unchanged

#### BT-034: Other unreadable images keep today's warnings
- **Protects:** BR-006 business rule
- Given a slide with `<img src="broken.png">` where `broken.png` holds the bytes `not an image`
- When exported to PPTX
- Then the warnings are `Image non decodable ignoree: ...` and `Image non inseree (...)` as today, and none says `SVG`

#### BT-035: DOCX vector diagnostics unchanged
- **Protects:** SPEC-0001/FR-018 as built
- When `tests/test_export_docx.py::test_to_docx_warns_about_svg_figures` runs
- Then it passes unchanged

#### BT-036: Clean save and template scans
- **Protects:** saved files carry no editor residue; scanner parity
- When `tests/test_strip_idempotent.py` and `tests/test_deck_get_slide.py::test_deck_scan_agrees_with_beautifulsoup_on_every_template` run over the fixed templates
- Then they pass unchanged

### 4.4 Existing tests asserting the current behavior

| Test file | Test name | Action | Reason |
|-----------|-----------|--------|--------|
| `tests/test_fullscreen_e2e.py` | `test_navigation_keys_work_even_if_focus_never_reaches_the_iframe` | Kept | still valid for the deck's own handler; its docstring claim of covering the relay is false in headless Chromium (BUG-001 contributing factor), BT-010 covers the relay |
| `tests/test_fullscreen_e2e.py` | the other three | Kept | BT-030 |
| `tests/test_medical_template.py` | `test_medical_bootstrap_ships_fullscreen_support` | Kept | subsumed by BR-016, harmless |
| `tests/test_export_golden.py` | `test_exported_slide_xml_matches_golden_hashes` | Kept | BR-015, BT-031; hashes not regenerated |
| `tests/test_export_pptx.py` | `test_ibm_carbon_template_exports_nine_slides`, `test_script_and_shell_are_never_exported` | Kept | `report.slide_count` stays 9; `#btn-present` is a `<button>`, never exported (E8) |
| `tests/test_export_pptx.py` | the five tests asserting `report.warnings == []` (E33) | Kept | their inputs have no vector figure inside a slide |
| `tests/test_medical_template.py` | `test_medical_decks_export_every_slide_without_warning` | Kept | 0 vector figure inside the medical slides (E31) |
| `tests/test_export_docx.py` | SVG diagnostics tests | Kept | DOCX untouched |
| `tests/test_skill_shipped.py` | reference mapping tests | Kept | the mapped files stay; content anchors are in skill text, not in the decks |
| `tests/test_strip_idempotent.py`, `tests/test_deck_get_slide.py` | template parametrized tests | Kept | they read every template, the fixed ones included |
| `tests/test_state.py` | `load()` tests | Kept | BL-0009 decides the fate of the unused `load()` |
| `tests/test_export_docx.py` | `test_reference_docx_for_swallows_a_missing_pandoc` | Kept | reference document fallback stays (as built FR-016) |

## 5. Existing Specs Affected

Existing specs are not modified; this spec supersedes the statements below.

- SPEC-0001/FR-028: gains `End` (BR-001, BR-002), as its legacy text had; its confidence note
  (E2) that End is "written only as handled by the slide document itself" no longer holds.
- SPEC-0001/FR-018: no longer scoped to word export; the PPTX export warns too (BR-005 to
  BR-007). The legacy "dédupliqué si identique" is replaced by one warning per occurrence carrying
  its slide number (BR-005).
- SPEC-0001/FR-027 and its confidence note "five reference decks lack it (BL-0007)": the five
  decks comply (BR-009 to BR-017).
- SPEC-0001/FR-010 (as built) and FR-016, FR-034 (as built): confirmed; the legacy reload and
  pandoc clauses are withdrawn (section 1.4, BR-018 to BR-020).
- SPEC-0001/E2E-040: still green, but it tests the deck's handler, not the relay (section 4.4).

## 6. Assumptions

Decisions taken without asking (the user asked for recommended defaults and no questions):

- **Decision:** End is restored in the relay, with `preventDefault` like the other keys
  (BR-001, BR-002).
- **Decision:** PPTX vector warnings carry the slide number, one per occurrence, in French
  without accents like the other PPTX warnings, ending with the DOCX advice sentence; a vector
  image gets one specific warning instead of today's two (BR-005, BR-006).
- **Decision:** stacked decks keep their stacked layout outside presenting, start presenting at
  slide 1 and scroll back to the current slide on leaving (BR-010, BR-013, BR-015).
- **Decision:** the guard discovers presentation files at run time, so future templates are
  covered (BR-016).
- **Decision:** legacy FR-010 reload and legacy FR-016 pandoc fallback withdrawn; the code is
  kept (section 1.4).
- **Not in scope:** `ibm-carbon.html` keeps its variable height model (slides up to 773 px, legacy
  DEC-015); BR-010 scales whatever the slide's size, and the 540 px budget stays documented
  (E20). Legacy TBD-005, TBD-006, TBD-007 and TBD-009, carried by BL-0006, move to BL-0035.
- **Overshoot:** none.
- **Backlog entries:** consumed BL-0006, BL-0007. Created BL-0035 (open questions inherited from
  the legacy SPEC-0001, `Nature: unknown`).

## 7. Implementability Checklist

| # | Item | Result |
|---|---|---|
| 1 | No technical decision | PASS: no mechanism, file list or order; markers and globals named are the observable contract of AGENTS.md and of the editor (E3, E12) |
| 2 | No buried requirement | PASS: End relay, key table, no globals, no relay outside, inline warning, image warning, silent shell, not blocked, markers, entering, hiding, keys, leaving, resize, exports, guard, both paths, pandoc, no adoption, status, docs each have a BR |
| 3 | Names spelled | PASS: keys, ids, CSS property, attribute, function names, warning texts, CLI message, `GET /status` fields, tool fields |
| 4 | No forced choice | PASS: current slide on entering and leaving, scale formula and tolerance, warning order, numbering, truncation, focus exceptions, stacked layout stated |
| 5 | Tests specified | PASS: BT-001 to BT-004, BT-010 to BT-024, BT-030 to BT-036 with data and exact assertions; 4.4 covers every test reading the five decks, the relay or the PPTX warnings (E4, E18, E32, E33) |
| 6 | Reproduction end to end | PASS: BT-001 browser on the editor page, BT-002 CLI, BT-003 browser on the deck, BT-004 the test gate; each reproduced failing on c507194 (section 1) |
| 7ante | Security classification | PASS: no bypass, injection, exposure or traversal; `Security: n/a` |
| 7bis | Sweep | n/a |
| 8 | No hidden prerequisite | PASS: Chromium, viewport, state dir, templates dir, PATH and records in every Given |
| 9 | EARS clean | PASS |
| 10 | Right tool | PASS: behavior changes (End, warnings, presentation mode, test gate); the guard and BR-021 enforce an existing rule, no new capability |
| 11 | Length | PASS: depth L, length follows three defects and two arbitrations |
| 12 | Claims cited | PASS: Evidence appendix; counts recounted on c507194 |
| 13 | Round trip | PASS: relay caller and deck callee read together (E3, E28); vector detection read on the DOCX writer (E11) and the PPTX walkers (E9); state writer and readers (E23 to E25) |
| 14 | Verdict consistent | PASS: BUG-001 to BUG-003 restore E1, E6, E12; the arbitrations are named `wrong`, decided in section 1.4 |

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | amended in place: 3 (BL-0006 cited the relay at `editor.js:151`, it is `:152` to `:167` after the split of the editor, E3; BL-0006 cited the PPTX drop at `to_pptx.py:95`, the skip list is `pptx_model.py:45`, E8; BL-0006 cited `EditorState.load` at `state.py:68` and a state file next to the edited file, it is `state.py:165` in the state directory, E23, E24); moved to backlog: none |

## Evidence

All lines read on commit c507194 (2026-11-08), Python 3.14.2, macOS, Playwright Chromium.

- E1 `git show 5e22a15:sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md`, lines 413 to 414: legacy FR-028, "`Home`/`End` (première/dernière slide) ... quel que soit l'élément DOM qui détient effectivement le focus clavier"
- E2 `sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:115` FR-010, `:122` FR-016, `:123` FR-034, `:125` FR-018 (word export), `:135` FR-028 (no End), `:187` E2E-040; `:207` to `:219` confidence notes on FR-010, FR-016 (`:207`), FR-028 (`:209`), FR-018 (`:212`), FR-027 (`:218`)
- E3 `src/mcp_htmleditor/static/editor.js:152` to `:167`: relay `keydown`, returns when `!document.fullscreenElement` (`:153`), branches for arrows and space (`:156`, `:159`), `Home` with a `typeof win.goToSlide === 'function'` guard (`:162`), `Escape` (`:164`); no `End`
- E4 `tests/test_fullscreen_e2e.py:243` `test_navigation_keys_work_even_if_focus_never_reaches_the_iframe` (calls `document.body.focus()`), `:271` `test_exiting_fullscreen_keeps_the_current_slide_and_restores_the_ui`, `:66` `_three_slide_deck`; measured: after `document.getElementById('present-btn').focus()` or `document.body.focus()` while presenting, `document.activeElement.id` is `content-frame`
- E5 `src/mcp_htmleditor/static/editor.html:41` `#present-btn`; `src/mcp_htmleditor/static/editor.js:114` to `:135` requests fullscreen on the iframe's document
- E6 `git show 5e22a15:sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md`, lines 332 to 338: legacy FR-018
- E7 `skill/topics/slides-carbon.md:107` "Les SVG inline ne sont pas convertis: utiliser un `<img>` PNG base64."
- E8 `src/mcp_htmleditor/export/pptx_model.py:37` to `:54` `SKIP_TAGS`, with `svg` at `:45`, `button` at `:48`, `script` `:39`, `noscript` `:41`, `template` `:42`, `select` `:46`
- E9 `rg -n SKIP_TAGS src/mcp_htmleditor/export`: `pptx_flow.py:102`, `:231`; `pptx_text.py:32`, `:64`, `:96`; `pptx_blocks.py:314`; `pptx_arch.py:47`; none reports
- E10 `src/mcp_htmleditor/export/pptx_images.py:124` to `:131` (`Image non decodable ignoree`), `:145` to `:151` (`Image non inseree (...)`, `src[:40]`), `:111` remote image warning with `src[:60]`; reproduction `make run ARGS='export pptx /tmp/spec16/svg.html /tmp/spec16/svg.pptx'`: exit 0, 4 warnings, none for the inline `<svg>`
- E11 `src/mcp_htmleditor/export/to_docx.py:51` `SVG_ADVICE = "Regle: figures en PNG, jamais en SVG."`; `:249` to `:277` `svg_warnings` (file, data URI, inline)
- E12 `AGENTS.md:79` to `:82`
- E13 `.agent_docs/html-conventions.md:53` to `:82` § Fullscreen presentation mode: CSS block (`:60` to `:68`), `#btn-present` (`:72`), JS and keys (`:74` to `:77`), `--fs-scale` (`:79`)
- E14 shell decks: `ibm-carbon.html:507` `.toolbar`, `:1252` `render`, `:1295` `keydown`, `:1299` `End`; `example-ei-complete.html:271`, `:754`, `:773`, `:779`; `example-carbon-complete.html:182`, `:719`, `:740`, `:744`
- E15 stacked decks: `presentation-standard.html:21` to `:27` (`section[data-type="slide"]`, `width: 1280px`, `margin: 40px auto`), four `<section data-type="slide">` at `:195`, `:204`, `:241`, `:255`; `roadmap-one-pager.html:21`, one slide at `:94`; `rg -c '<script|keydown'` 0 in both
- E16 `sdlc/constitution.md:12` "Every slide template ships fullscreen support ... five reference decks violate it (BL-0007)"
- E17 `rg -c` on `:fullscreen` / `btn-present` / `enterPresentation` / `exitPresentation` / `updateFullscreenScale`: 0/0/0/0/0 for the five decks; 6 to 8/1/3/2/5 for `slides-empty.html`, `slides-ei-empty.html`, `slides-medical-empty.html`, `euro-information.html`, `medical.html`, `example-medical-complete.html`; 11 presentation files under `templates/` (3 bootstraps, 8 reference decks)
- E18 `tests/test_medical_template.py:86` to `:91` `test_medical_bootstrap_ships_fullscreen_support`; `rg -n 'btn-present|enterPresentation' tests`: no other check
- E19 `git show 5e22a15:sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md`, line 770, TBD-011
- E20 `skill/topics/slides-carbon.md:96` "La référence `ibm-carbon.html` est un catalogue autonome, sans CSS `:fullscreen`, dont les slides dépassent 540 px"
- E21 `tests/test_skill_shipped.py:52` to `:59` reference map (`slides-carbon` → `ibm-carbon.html`, `slides-ei` → `example-ei-complete.html`)
- E22 `git show 5e22a15:...spec.md`, lines 268 to 269, legacy FR-010
- E23 `src/mcp_htmleditor/state.py:4` to `:8` state layout (`<state_dir>/last.json`, `<state_dir>/files/<key>/server.json`); `:221` to `:224` `_file_dir`
- E24 `src/mcp_htmleditor/state.py:165` `def load`; `rg -n '\.load\(\)' src`: no match; `src/mcp_htmleditor/http_server.py:1083` port from argument or `find_free_port(bind_host, default_port())`; `src/mcp_htmleditor/cli.py:221` to `:226` poll from `--poll`; `src/mcp_htmleditor/config.py:357` to `:359` default poll 1000
- E25 `src/mcp_htmleditor/state.py:203` to `:219` `snapshot` reads the recorded port and pid when this process serves nothing; `src/mcp_htmleditor/http_server.py:438` to `:450` `/status` returns `port` and `poll_interval`
- E26 `git show 5e22a15:...spec.md`, lines 316 to 317, legacy FR-016
- E27 `src/mcp_htmleditor/deck/tools.py:22` `PANDOC_MISSING_MESSAGE`, `:106` to `:107`; reproduction `PATH="/Users/sebastien/.local/bin:/usr/bin:/bin" make run ARGS='export docx /tmp/spec16/doc.html /tmp/spec16/doc.docx'`: `error: pandoc not found in PATH: install pandoc to export to DOCX.`, `make` reports the command failed (status 1), no file
- E28 `templates/bootstrap/slides-empty.html:389` to `:405`: `navigate`, `goToSlide`, `keydown` with the focus exception (`:398`) and `End` → `goToSlide(TOTAL - 1)` (`:402`); `:373` to `:387` `updateFullscreenScale`, `fullscreenchange` and `resize` listeners; `:244` to `:259` `:fullscreen` rules; `:291` `#btn-present`
- E29 `src/mcp_htmleditor/cli.py:531` to `:532` prints each warning as `Attention: <warning>` on stderr; the export tool returns the same list (`src/mcp_htmleditor/deck/tools.py:26` to `:30` `ExportOutcome.warnings`; `src/mcp_htmleditor/mcp_server.py:379` tool `export`, answer `{"ok": True, "output": ..., "warnings": ...}` at `:400`)
- E34 `src/mcp_htmleditor/export/to_pptx.py:99` to `:105`: no slide element, warning `Aucun element data-type="slide" ni article.slide trouve: ...`, the body exported as one slide
- E30 `src/mcp_htmleditor/export/pptx_model.py:56` `SHELL_CLASSES` (`toolbar`, `shell-header`, `status-bar`, `nav-arrow`, `stage`, `slide-frame`)
- E31 BeautifulSoup count of outermost `<svg>` inside `[data-type="slide"]`: `ibm-carbon.html` 1, every other template 0; the Carbon bootstrap holds 6 shell `<svg>` outside its slide (`/tmp/spec16/svg.html:266` to `:323`)
- E32 `tests/test_export_golden.py:26` to `:37` template list (includes `ibm-carbon.html`, `example-ei-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html`), `:50` to `:54` assertion; `tests/testdata/pptx_slide_hashes.json`
- E33 `tests/test_export_pptx.py:364`, `:385`, `:540`, `:811`, `:1082` and `tests/test_medical_template.py:247` assert `report.warnings == []`
- Reproductions: `/tmp/spec16/test_repro.py` run with `make test ARGS="-c pyproject.toml --rootdir=. -p no:cacheprovider -s -q --no-cov -o pythonpath=. /tmp/spec16/test_repro.py"`: `test_end_key_parent_focus` (BUG-001), `test_deck_fullscreen[<five>]` (BUG-003 items 1, 2), `test_bootstrap_baseline[slides-empty, slides-ei-empty]` (item 3); `/tmp/spec16/svg.html` (BUG-002); `/tmp/spec16/doc.html` (E27)
