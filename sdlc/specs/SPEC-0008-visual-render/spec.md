# Visual render and layout report: functional specification

> Id: SPEC-0008
> Nature: FEAT
> Depth: L
> Depth evidence: a browser rendering capability, 2 surfaces (command line, agent tool), new install step, more than 10 requirements
> Status: designed
> Generated on: 2026-11-03
> Project: existing
> From backlog: n/a
> Depends on: SPEC-0006 (core lists the tool), SPEC-0007 (slide ids, presentation detection)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary

The skill makes a visual check mandatory after each substantial change, but the product gives no way to do it:
the agent must set up its own browser tool, and a slide whose content exceeds its 540 pixel height is cut off
without any message. This increment adds a `render` operation that produces a small picture of one slide and a
text report of what is wrong with the layout, so an agent can check its work cheaply and without vision.

## 2. Current State

### 2.1 What users can do today

- Open the file in the editor, or use an external browser tool, to look at a slide.
- Nothing in the product reports that a slide overflows, that an element is outside the slide frame, that a
  font is missing, that a script fails or that an image does not load.
- The skill documents the 540 pixel budget and says content beyond it is cut off silently
  (`skill/types/slides.md`, section "Hauteur utile d'une slide").
- A Chromium browser is installed for the project's own tests by `make` (`Makefile:51`) but is not a feature
  of the product.

### 2.2 Specs governing this area

- SPEC-0007 FR-NEW-014 and its scope exclusion: height overflow is left to this spec.
- SPEC-0006: the skill core lists every tool; `render` must be listed there.
- SPEC-0001 FR-009 ("exactly seven operations") is contradicted again; the count is recorded in SPEC-0007.

### 2.3 What is verified today

Tests drive a real Chromium for editing behavior (autosave, fullscreen, undo, website). Nothing renders a slide
to a picture or measures layout for the agent.

## 3. Scope

### 3.1 In scope

`render` on the command line and the agent tool surface; the layout report; a `make install-browser` command.

### 3.2 Out of scope, and why

- Rendering documents, mails and websites: the 960 x 540 slide canvas is the measurable unit; later if asked.
- Pixel comparison against a reference picture: a separate decision.
- Rendering in dark or light mode variants, or in the print layout.
- Adding render problems to `lint`: kept separate so `lint` stays instant and needs no browser.

### 3.3 Constraints imposed by the context

- The standard output of the tool protocol process carries protocol messages only.
- A browser is a heavy dependency: the product must keep working without it, and say how to install it.

## 4. Actors

| Actor | Description |
|---|---|
| Agent | A language model that edits a presentation and wants to check its work |
| Maintainer | A person who runs the same command |

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Rendering | pictures of slides and layout measurements | render, canvas, report, problem |

## 5. Usage scenarios

### SC-001: Checking one slide
**Actor:** Agent
**Preconditions:** a presentation exists and the browser is installed.
**Flow:**
1. The agent runs `mcp-htmleditor render deck.html --slide slide-3` → a picture file is written and its path printed.
2. The agent looks at the picture.
**Postconditions:** the file is unchanged.
**Exceptions:**
- EXC-001a: unknown slide → error listing valid ids.
- EXC-001b: scale out of range → error.
- EXC-001c: the file is a document → error.
- EXC-001d: the browser is not installed → error saying how to install it.
**Interactions:** SC-002.

### SC-002: Finding layout problems across a deck
**Actor:** Agent or Maintainer
**Flow:**
1. The actor runs `mcp-htmleditor render deck.html --report-only` → every slide is analysed and problems are listed, one per line.
2. The actor fixes the slides and runs it again until the report is clean.
**Exceptions:**
- EXC-002a: problems found → exit status 1.
- EXC-002b: `--report-only` combined with `--slide`, `--scale` or `--report` → usage error.

### SC-003: Using the tool surface
**Actor:** Agent
**Flow:**
1. The agent calls `render` with `file`, optional `slide`, `scale` and `report` → it receives the path, the size and the problems.

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-E]: Render a slide
> WHEN a user runs `mcp-htmleditor render <file>` THE Editor SHALL write a PNG picture of one slide of the presentation and print one line giving its slide, path and size.

- **Business rules:** the picture is exactly the 960 x 540 slide element at device scale equal to the scale, with no border or shadow, captured after the slide's entrance animation has finished; nothing else of the page appears (no top bar, toolbar, side arrows, status bar or neighbouring slide); the slide's own markup and styles are not altered, except that only the target slide is displayed. Slides are the elements `data-type="slide"` in document order, identified by `data-id`; a presentation with no slide is refused as not a presentation. Checks are made in this order and the first failure alone is reported: option conflict (exit status 2), scale, file not found, not a presentation, browser missing, unknown slide id (exit status 1 each). Sizes are rounded half up. The default slide is the first. The default scale is 0.5, so the picture is `round(960 x scale)` by `round(540 x scale)` pixels. The picture is written to `<system temporary directory>/htmleditor-render/<file name without extension>-<slide id>.png`, and, only after a successful render, every file in that directory other than the picture just written, named `<file name without extension>-<id>.png` where `<id>` is a slide id of the presentation, is deleted (errors and `--report-only` delete nothing); the name keeps the file's own characters. The file given is a presentation; a document, mail or website is refused. Without the browser installed the command prints the error below. The command never prompts.
- **User visible text:** `Rendered slide-3 to /tmp/htmleditor-render/deck-slide-3.png (480x270)`; `error: File not found: <file>`; `error: render needs a presentation: <file>`; `error: Rendering needs Chromium. Install it with: make install-browser` (exit status 1 for all three).
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: Slide and scale
> WHEN a user passes `--slide <id>` or `--scale <number>` THE Editor SHALL render that slide at that scale.

- **Business rules:** the scale is a finite decimal number from 0.1 to 1 inclusive; 0.1 gives 96 x 54; anything else (including `nan`, `inf`) is refused with the message below.
- **User visible text:** `error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, ...` (all ids, in order, exit status 1); `error: Scale must be between 0.1 and 1` (exit status 1; also for a value that is not a number).
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-003 [EARS-E]: Layout report
> WHEN a user passes `--report` THE Editor SHALL also print the layout problems of the rendered slide, then a final line, and exit with status 1 when at least one problem is found.

- **Business rules:** a problem line is `<kind> <slide>: <message>`. Kinds and messages:
  - `overflow`: the content height of the slide, rounded to the nearest pixel, is greater than 540: `content is 612px tall, the slide is 540px` (that rounded value). The content height is the largest of the scroll height of the slide element and, for every rendered descendant of the slide (not `display:none`) whose computed `overflow-y` is `hidden`, `clip` or `auto`, the unrounded distance from the top of the slide to the top of that descendant (difference of their bounding box tops) plus its scroll height; the value is rounded once, at the end; this makes content cut off by a slide body count, not only content cut off by the slide itself.
  - `clipped`: a rendered element (not `display:none`, not of zero size) inside the slide, which is not a descendant of an element already reported, has a box beyond the frame by more than 1 pixel on the left, right or top, or on the bottom when the slide does not already report `overflow`; at most one line per element: `<selector> is outside the slide frame`, the selector being the lower case tag name followed by `.` and each class in attribute order joined by `.` (the tag alone when there is no class), for example `span.slide-foot-page`.
  - `font`: for a font family list used by text of the slide, none of its non generic families is installed on this machine (`sans-serif`, `serif`, `monospace`, `system-ui` are ignored): `"NoSuchFont" is not available, fallback used`, naming the first non generic family; one line per name per slide.
  - `script`: an uncaught script error, written `<name>: <message>` (for example `Error: boom`); an error raised while the page loads is reported once per run with the slide `-`; an error raised while a slide is displayed is reported with that slide's id.
  - `image`: an image did not load: `<source> did not load`; a data address is shortened to its first 40 characters followed by `...`.
  - With `--report`, only problems of the rendered slide and `script` problems with the slide `-` are listed and counted; problems of other slides are not.
  - Order: problems with the slide `-` first, then by slide, then kind in the order `script`, `image`, `font`, `overflow`, `clipped`, then document order. Final line `report: OK` or `report: 3 problems` (`1 problem` singular).
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-004 [EARS-E]: Report only
> WHEN a user passes `--report-only` THE Editor SHALL analyse every slide of the presentation, write no picture, print the problem lines and the final line, and exit with status 1 when at least one problem is found.

- **Business rules:** `--report-only` together with `--slide`, `--scale` or `--report` is a usage error: `Error: --report-only cannot be used with --slide, --scale or --report` (exit status 2, no other output). The analysis of a slide uses the same measures as FR-NEW-003.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-005 [EARS-E]: Tool surface and JSON
> WHEN an agent calls the tool `render` or a user passes `--json` THE Editor SHALL return a JSON object with the result.

- **Business rules:** tool `render(file, slide=None, scale=0.5, report=False, report_only=False)`. The object is `{"ok":true,"path":<path or null>,"width":<n or null>,"height":<n or null>,"problems":[{"kind","slide","message"}]}`; `path`, `width` and `height` are null for `report_only`; `problems` is empty unless `report` or `report_only` is set. With `--json` the command prints that object alone on the standard output and no other line; the exit status follows FR-NEW-003. Problems are collected only with `--report` or `--report-only` (the tool arguments `report`, `report_only`); otherwise the exit status is 0 after a successful picture. With `--json` the `Rendered ...` and `report: ...` lines are not printed; `--json --report-only` prints the object with null `path`, `width` and `height`. On any error, the command with `--json` prints the error line to the error output exactly as without `--json`, prints nothing on the standard output and keeps the same exit status. The tool applies the same checks in the same order, including the conflict of `report_only` with `slide`, a `scale` other than the default, or `report`, and returns errors with the message of the command line line without its `error: ` prefix.
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-006 [EARS-UB]: No side effect on the file or the editor
> The Editor SHALL NOT modify the presentation file or the state of a running editor server when rendering.

- **Business rules:** the file bytes and modification time, and the answer of `get_status`, are the same before and after.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

## 7. Non functional requirements (user observable)

- FR-NEW-007 [EARS-U]: A `--report-only` analysis of a presentation of 40 slides SHALL finish in less than 30 seconds on a typical workstation.

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Data variations | file path with spaces and accents | works, path printed as written | E2E-022 |
| Boundary values | scale 0.1, 1, 0, 1.5, `abc` | 0.1 and 1 accepted; others refused | E2E-002, E2E-009 |
| Data variations | dark medical slide | dark surface kept in the picture | E2E-020 |
| Repetition | two renders of the same file | only the last picture stays | E2E-021 |
| Exhaustion | 40 slides | under 30 seconds | E2E-023 |
| Dependency failures | browser missing | install message | E2E-011 |
| Concurrent actions, access states, navigation | not applicable here | none | none |

## 9. Acceptance tests (the contract)

### 9.0 Fixtures

DECK-EI: an Euro-Information presentation of 8 slides `slide-0` to `slide-7` with no layout problem. DECK-MED: a
medical presentation of 6 slides whose `slide-2` has class `slide dark`. DOC-PERSO: a document. The machine running the tests has Segoe UI or Calibri installed, so DECK-EI and DECK-MED report no font problem. Where a test needs a defect, it states the defect.

### 9.1 Summary

| Test | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|
| E2E-001 | journey | SC-001 | FR-NEW-001 | Critical |
| E2E-002 | journey | SC-001 | FR-NEW-002 | High |
| E2E-003 | journey | SC-001 | FR-NEW-003 | Critical |
| E2E-004 | journey | SC-002 | FR-NEW-004 | Critical |
| E2E-005 | journey | SC-003 | FR-NEW-005 | High |
| E2E-006 | journey | SC-003 | FR-NEW-005 | Medium |
| E2E-007 | failure | SC-001 | FR-NEW-001, 005 | High |
| E2E-008 | failure | SC-001 | FR-NEW-002 | High |
| E2E-009 | failure | SC-001 | FR-NEW-002 | High |
| E2E-010 | failure | SC-001 | FR-NEW-001 | High |
| E2E-011 | failure | SC-001 | FR-NEW-001 | High |
| E2E-012 | failure | SC-002 | FR-NEW-003, 006 | Critical |
| E2E-013 | failure | SC-002 | FR-NEW-003 | High |
| E2E-014 | failure | SC-002 | FR-NEW-003 | High |
| E2E-015 | failure | SC-002 | FR-NEW-003 | Medium |
| E2E-016 | failure | SC-002 | FR-NEW-003 | High |
| E2E-017 | failure | SC-002 | FR-NEW-003 | High |
| E2E-018 | failure | SC-002 | FR-NEW-004 | Medium |
| E2E-019 | failure | SC-002 | FR-NEW-004 | High |
| E2E-020 | edge | SC-001 | FR-NEW-001 | Medium |
| E2E-021 | edge | SC-001 | FR-NEW-001 | Medium |
| E2E-022 | edge | SC-001 | FR-NEW-001 | Medium |
| E2E-023 | edge | SC-002 | FR-NEW-004, 007 | Medium |
| E2E-024 | side effect | SC-001 | FR-NEW-006 | High |
| E2E-025 | side effect | SC-001 | FR-NEW-006 | High |
| E2E-026 | failure | SC-003 | FR-NEW-005, 004 | High |
| E2E-027 | edge | SC-002 | FR-NEW-007, 003 | Medium |
| E2E-028 | failure | SC-003 | FR-NEW-005, 002, 004 | Medium |
| E2E-029 | edge | SC-002 | FR-NEW-007, 004 | Medium |

Coverage: happy 6, failure 15, edge 6, side effect 2 (29 tests). Happy to failure ratio 1:2.5 (beats 1:1).

### 9.2 New tests

#### E2E-001: Default render
- **Given** DECK-EI and the browser installed
- **When** the user runs `mcp-htmleditor render DECK-EI`
- **Then** the output is `Rendered slide-0 to <path> (480x270)` where `<path>` ends with `htmleditor-render/DECK-EI-slide-0.png`, the exit status is 0
- **And** the file at `<path>` is a PNG picture of 480 x 270 pixels
- **Priority:** Critical

#### E2E-002: Slide and scale
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --slide slide-3 --scale 1`, checks the picture, then runs it with `--scale 0.1`
- **Then** the outputs end with `(960x540)` and `(96x54)` and the pictures, checked after each run, have those sizes; the path ends with `DECK-EI-slide-3.png`
- **Priority:** High

#### E2E-003: Clean report
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --slide slide-2 --report`
- **Then** the output is two lines: `Rendered slide-2 to <path> (480x270)` and `report: OK`, exit status 0
- **Priority:** Critical

#### E2E-004: Clean report only
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --report-only`
- **Then** the output is the single line `report: OK`, exit status 0, and no picture file is created for DECK-EI
- **Priority:** Critical

#### E2E-005: Tool call
- **Given** DECK-EI
- **When** the agent calls `render` with `file` DECK-EI, `slide` `slide-1`, `report` true
- **Then** it receives `{"ok":true,"path":"<path ending DECK-EI-slide-1.png>","width":480,"height":270,"problems":[]}`
- **Priority:** High

#### E2E-006: JSON on the command line
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --json`
- **Then** the standard output is one JSON object equal to the one of E2E-005 with `slide-0` and nothing else
- **Priority:** Medium

#### E2E-007: File not found
- **Given** no file `ghost.html`
- **When** the user runs `render ghost.html`, and the agent calls `render` with `file` `ghost.html`
- **Then** the command prints `error: File not found: ghost.html` on the error output with exit status 1 and an empty standard output
- **And** the tool returns an error whose message is `File not found: ghost.html`
- **Priority:** High

#### E2E-008: Unknown slide
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --slide slide-9`
- **Then** the error output is `error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2, slide-3, slide-4, slide-5, slide-6, slide-7`, exit status 1
- **Priority:** High

#### E2E-009: Scale out of range
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --scale 1.5`, `--scale 0`, `--scale abc`
- **Then** each prints `error: Scale must be between 0.1 and 1` and exits with status 1, and no picture is written
- **Priority:** High

#### E2E-010: Not a presentation
- **Given** DOC-PERSO
- **When** the user runs `render DOC-PERSO` and `render DOC-PERSO --report-only`
- **Then** each prints `error: render needs a presentation: DOC-PERSO`, exit status 1
- **Priority:** High

#### E2E-011: Browser missing
- **Given** DECK-EI (a valid presentation) and no browser installed for the product
- **When** the user runs `render DECK-EI`, and the agent calls `render`
- **Then** the command prints `error: Rendering needs Chromium. Install it with: make install-browser`, exit status 1, no picture
- **And** the tool returns an error with the same message without `error: `
- **Priority:** High

#### E2E-012: Overflow
- **Given** DECK-EI where the body of `slide-4` holds a block with the style `height:700px`
- **When** the user runs `render DECK-EI --report-only`
- **Then** the output holds one line `overflow slide-4: content is <N>px tall, the slide is 540px` where `<N>` is an integer of at least 700, then `report: 1 problem`; no `clipped` line appears; the exit status is 1
- **And** the block of `height:700px` placed instead as a direct child of the slide element, after the inner frame, not absolutely positioned, gives the same line with `<N>` at least 700
- **And** `slide-4` whose body content is replaced by `<div style="height:300px"></div>` gives no `overflow` line
- **And** the file DECK-EI is byte for byte unchanged
- **Priority:** Critical

#### E2E-013: Clipped element
- **Given** DECK-EI where the slide element of `slide-5` is made `position:relative` and its body holds `<div class="probe" style="position:absolute; left:940px; top:10px; width:100px; height:20px">x</div>`
- **When** the user runs `render DECK-EI --slide slide-5 --report`
- **Then** the output holds `clipped slide-5: div.probe is outside the slide frame` and ends with `report: 1 problem`, exit status 1
- **Priority:** High

#### E2E-014: Page number outside the frame
- **Given** DECK-EI where the page number element `<span class="slide-foot-page">` of `slide-3` gets the style `position:relative; left:920px`
- **When** the user runs `render DECK-EI --slide slide-3 --report`
- **Then** the output holds `clipped slide-3: span.slide-foot-page is outside the slide frame`, no `overflow` line, and ends with `report: 1 problem`, exit status 1
- **Priority:** High

#### E2E-015: Missing font
- **Given** DECK-EI where `slide-1` holds two text blocks using the font family `NoSuchFont, sans-serif`
- **When** the user runs `render DECK-EI --report-only`
- **Then** the output holds exactly one line `font slide-1: "NoSuchFont" is not available, fallback used`
- **Priority:** Medium

#### E2E-016: Script error
- **Given** DECK-EI where a script of `slide-2` runs `throw new Error("boom")` when the page loads
- **When** the user runs `render DECK-EI --slide slide-2 --report`
- **Then** the output holds `script -: Error: boom` and ends with `report: 1 problem`, exit status 1
- **Priority:** High

#### E2E-017: Image that does not load
- **Given** DECK-EI where `slide-6` holds `<img src="pics/missing.png">` and the file `pics/missing.png` does not exist
- **When** the user runs `render DECK-EI --report-only`
- **Then** the output holds `image slide-6: pics/missing.png did not load`, exit status 1
- **Priority:** High

#### E2E-018: Incompatible options
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --report-only --slide slide-1`
- **Then** the error output is exactly `Error: --report-only cannot be used with --slide, --scale or --report`, exit status 2, nothing on the standard output
- **Priority:** Medium

#### E2E-019: Several problems counted
- **Given** DECK-EI with the defects of E2E-012, E2E-015 and E2E-017
- **When** the user runs `render DECK-EI --report-only`
- **Then** the lines appear in this order: `font slide-1: "NoSuchFont" is not available, fallback used`, `overflow slide-4: ...`, `image slide-6: pics/missing.png did not load`, then the last line `report: 3 problems`; exit status 1
- **Priority:** High

#### E2E-020: Dark surface
- **Given** DECK-MED
- **When** the user runs `render DECK-MED --slide slide-2 --scale 1`
- **Then** the pixel at x 2, y 300 of the picture is the colour `#0B0E11`
- **Priority:** Medium

#### E2E-021: Only the last render stays
- **Given** DECK-EI
- **When** the user renders `slide-1`, then `slide-2`
- **Then** the directory `htmleditor-render` holds `DECK-EI-slide-2.png` and no `DECK-EI-slide-1.png`
- **And** a picture of another file in that directory is untouched
- **Priority:** Medium

#### E2E-022: Path with spaces and accents
- **Given** the file `Présentation été.html` (a copy of DECK-EI)
- **When** the user runs `render "Présentation été.html"`
- **Then** the output is `Rendered slide-0 to <path> (480x270)` where `<path>` ends with `Présentation été-slide-0.png`, and the picture exists
- **Priority:** Medium

#### E2E-023: Large deck speed
- **Given** a presentation of 40 slides without layout problem
- **When** the user runs `render <file> --report-only`
- **Then** the command ends in less than 30 seconds with `report: OK`
- **Priority:** Medium

#### E2E-024: File untouched
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --report`
- **Then** the file bytes and modification time are the same as before
- **Priority:** High

#### E2E-025: Server state untouched
- **Given** the editor server running on DECK-EI
- **When** the agent calls `render` with `report_only` true
- **Then** the answer of `get_status` after is equal to the one before, field by field
- **Priority:** High

#### E2E-026: Problems as JSON
- **Given** DECK-EI with the overflow defect of E2E-012
- **When** the user runs `render DECK-EI --report-only --json`
- **Then** the standard output is one JSON object with `ok` true, `path`, `width` and `height` null, and `problems` holding one element with `kind` `overflow`, `slide` `slide-4` and a `message` starting `content is `; nothing else is printed; the exit status is 1
- **Priority:** High

#### E2E-027: Report on one slide of a large deck
- **Given** a presentation of 40 slides without layout problem
- **When** the user runs `render <file> --slide slide-39 --report`
- **Then** the command ends in less than 30 seconds with the lines `Rendered slide-39 to <path> (480x270)` and `report: OK`
- **Priority:** Medium

#### E2E-028: JSON with an error
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --slide slide-9 --json`
- **Then** the error output is the `error: Unknown slide id "slide-9". Valid ids: ...` line of E2E-008, the standard output is empty and the exit status is 1
- **And** the tool `render` called with `report_only` true and `slide` `slide-1` returns an error whose message is `--report-only cannot be used with --slide, --scale or --report`
- **Priority:** Medium

#### E2E-029: Large deck full analysis
- **Given** a presentation of 40 slides, each holding an image that loads, without layout problem
- **When** the user runs `render <file> --report-only`
- **Then** the command ends in less than 30 seconds with the single line `report: OK`
- **Priority:** Medium

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 002, 003, 006 | E2E-001, 002, 003 | E2E-007 to 011 | E2E-020, 021, 022 |
| SC-002 | FR-NEW-003, 004, 006, 007 | E2E-004 | E2E-012 to 019 | E2E-023, 027, 029 |
| SC-003 | FR-NEW-005 | E2E-005, 006 | E2E-026, 028 | none |

Requirements to tests: FR-NEW-001 (001, 007, 010, 011, 020, 021, 022); 002 (002, 008, 009, 028); 003 (003, 012 to 017, 027); 004 (004, 018, 019, 023, 026, 028, 029); 005 (005, 006, 007, 026, 028); 006 (012, 024, 025); 007 (023, 027, 029).

## 11. Open questions

None.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Canvas | The 960 x 540 pixel area of a slide | Rendering |
| Render | A picture of one slide | Rendering |
| Report | The list of layout problems of one or all slides | Rendering |
| Problem | One line `<kind> <slide>: <message>` | Rendering |
| Frame | The rectangle of the slide canvas | Rendering |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 9 | 3 | NOT-IMPLEMENTABLE |
| 2 | 4 | 3 | final line IMPLEMENTABLE although F findings were listed; all amended, no round 3 (cap) |
| 3 | 4 | 0 | IMPLEMENTABLE after amendment 2026-11-03 (FR-NEW-003 `overflow` content height, from design ISSUE-001) |

**Amendments applied:** all F findings of rounds 1 and 2. **Concern:** the round 2 verdict line contradicted its own F list; the amendments were not re audited.
**No implementation detail outside Section 14:** PASS

## 14. Evidence appendix

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| browser installed for tests only | `Makefile:51`, `pyproject.toml:35` (pytest-playwright, dev group); tests `tests/test_fullscreen_e2e.py`, `tests/test_website_template_e2e.py` |
| the 540 pixel budget is prose | `skill/types/slides.md` section "Hauteur utile d'une slide" |
| playwright treated as optional, tool only | `pyproject.toml:125` |
| 7 tools today | `src/mcp_htmleditor/mcp_server.py:31,81,93,112,133,150,166` |

Test command: `make test`; gate `make check`.

### 14.3 Design inputs

- Playwright is a development dependency (`pyproject.toml:35`); the product needs it as an optional runtime extra, plus a `make install-browser` target. Detection signal: E2E-011.
- The slides are shown by the template script (`current`, `render()`, class `active`); showing one slide alone on the canvas without the editor chrome needs a generic way, since third party decks differ (`templates/bootstrap/slides-empty.html`). Detection signal: E2E-001, E2E-020.
- Font availability and selector shapes depend on the browser; the measurements must be deterministic for the tests (fixed viewport and device scale). Detection signal: E2E-012, E2E-013.
- E2E-019 expectation order (`font slide-1`, `overflow slide-4`, `image slide-6`) follows slide order first.
