# Agent editing tools: outline, get_slide, patch, lint, templates and export: functional specification

> Id: SPEC-0007
> Nature: FEAT
> Depth: L
> Depth evidence: 4 areas touched (command line, agent tool surface, slide structure rules, quality rules), new persisted-file edit operations, more than 15 anticipated requirements
> Status: specified
> Generated on: 2026-11-03
> Project: existing
> From backlog: n/a
> Depends on: SPEC-0006 (the core lists the new tools)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary

An agent that edits a presentation today reads the whole HTML file, base64 images included, and rewrites it
whole. It must renumber slide ids, the slide total, the slide names, the page counters and the footers by
hand, and nothing checks the result. This increment gives the agent seven operations: read the structure
(`outline`), read one slide (`get_slide`), change the file through validated, atomic, self renumbering
operations (`patch`), check quality (`lint`), and the three operations an agent needs to start and finish a
job without the command line (`list_templates`, `new_file`, `export`).

## 2. Current State

### 2.1 What users can do today

- An agent reads and writes the HTML file directly, bracketing its work with `update_start` and `update_end`.
- The agent tool surface has 7 tools (start_server, stop_server, get_status, open_file, update_start,
  update_end, layout_arch_diagram) and none reads or edits slide content.
- Creating a file (`new`), listing templates (`templates`) and exporting (`export`) exist only on the command
  line.
- Slide insertion and deletion with automatic renumbering exist only in the browser editor.
- Nothing checks a presentation against the rules of its charter. The rules exist only as prose in the skill.
- The browser editor silently ignores a save aimed at a path under `templates/bootstrap` or `templates/reference`; the command line has no such guard.

### 2.2 Specs governing this area

- SPEC-0001 FR-009 ("exactly seven operations") is contradicted: this increment adds seven tools, so
  there are fifteen once SPEC-0006 has added `get_skill`. SPEC-0001 is not modified; the new count is
  recorded here.
- SPEC-0002 (browser editing) owns the renumbering behavior in the browser; the same observable rules are
  restated here for the agent.
- SPEC-0006 FR-NEW-008: the audit compares the skill's tool list with the tools provided, so the core of the
  skill must list the seven new tools.

### 2.3 What is verified today

The export, the arch layout and the browser editing have tests. No test covers reading a slide, patching, or
checking a charter's rules, because none of these exist.

## 3. Scope

### 3.1 In scope

The seven operations of the summary, on the command line and on the agent tool surface, with identical
results; the rules listed in Section 6.

### 3.2 Out of scope, and why

- Height overflow detection: needs a browser rendering; SPEC-0008.
- A lock or token for `update_start`, history snapshots, refusing to overwrite a concurrent browser edit:
  SPEC-0009.
- Inserting a slide from a layout name (`insert_slide` takes the slide HTML): the layouts live in the browser
  code and porting them is a separate decision.
- Editing documents, mails and websites with `patch`: slide operations apply to presentations only; a
  document gives `outline` and `lint` only.
- Fixing lint problems automatically.

### 3.3 Constraints imposed by the context

- The standard output of the tool protocol process carries protocol messages only; the command line prints
  results, the tool surface returns them.
- Specs already written are not edited.

## 4. Actors

| Actor | Description |
|---|---|
| Agent | A language model driving the editor through the command line or the tool protocol |
| Maintainer | A person who runs the same commands to check a file |

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Deck structure | slides, their order, ids, titles, counters | slide, id, total, counter, charter |
| Quality rules | what a correct file is for each charter | lint rule, problem, severity |
| Agent tools | the operations an agent can call | tool, operation |

## 5. Usage scenarios

### SC-001: An agent reads the structure of a file
**Actor:** Agent
**Preconditions:** a presentation or a document exists.
**Flow:**
1. The agent calls `outline` → it receives the charter, the total, and per slide (or per heading) a few facts, never image data.
2. The agent chooses which slide to read.
**Postconditions:** the agent knows what the file holds without having read it.
**Exceptions:**
- EXC-001a: the file does not exist → error.

### SC-002: An agent reads one slide
**Actor:** Agent
**Flow:**
1. The agent calls `get_slide` with an id → it receives the slide HTML, with large images replaced by references.
**Exceptions:**
- EXC-002a: the id does not exist → error listing the valid ids.

### SC-003: An agent edits a text
**Actor:** Agent
**Flow:**
1. The agent calls `patch` with one `set_text` operation → the text changes, nothing else in the file changes.
**Exceptions:**
- EXC-003a: unknown id or no element matches the selector → nothing is written.

### SC-004: An agent restructures a deck
**Actor:** Agent
**Flow:**
1. The agent calls `patch` with insert, delete and move operations → the file is rewritten once, with every id, total, name, counter and footer renumbered.
**Exceptions:**
- EXC-004a: any operation is invalid → nothing is written, the error names the operation.
- EXC-004b: the deck would have no slide left → refused.

### SC-005: An agent replaces a slide
**Actor:** Agent
**Flow:**
1. The agent calls `get_slide`, edits the HTML keeping the image references, then calls `patch` with `replace_slide` → the slide is replaced and images are restored.
**Exceptions:**
- EXC-005a: the HTML lacks `data-type="slide"` or `data-id` → refused.
- EXC-005b: an image reference does not exist in that slide → refused.

### SC-006: Checking quality
**Actor:** Agent or Maintainer
**Flow:**
1. The actor calls `lint` → it receives the problems, each with a code, a severity, a slide and a message, and a verdict.
**Exceptions:**
- EXC-006a: errors found → exit status 1.

### SC-007: Starting and finishing a job without the command line
**Actor:** Agent
**Flow:**
1. The agent calls `list_templates`, then `new_file`, edits, then `export`.
**Exceptions:**
- EXC-007a: unknown template or format → error listing valid values.
- EXC-007b: `new_file` target exists → refused.

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-E]: Outline
> WHEN an agent or a user asks for the `outline` of a file THE Editor SHALL return a JSON object describing the file structure without any image data.

- **Business rules:** the object is `{"file","charter","doc_type","total","slides","headings"}`. `charter` is one of `ei`, `carbon`, `medical` (presentations; a presentation with no charter mark is `carbon`) or `doc`, `doc-perso`, `doc-ei`, `mail`, `website` (non presentations, from the document template mark; none means `doc`). A presentation is `medical` when its style contains `--med-teal` or `<html>` carries `data-doc-template="medical"`; otherwise `ei` when its style contains `--ei-blue` or the body contains `slide-cover-logos`; otherwise `carbon`; medical is tested first. A non presentation takes the `data-doc-template` of its first `data-type="document"` article (`perso` gives `doc-perso`, `ei` gives `doc-ei`, `mail`, `website`, anything else `doc`). `doc_type` is `presentation` or `document` (`website` files report `website`). For a presentation, `slides` holds, in order, `{"index","id","title","slide_type","words","images","problems"}` (index from 0; `slide_type` is the slide's `data-slide-type`, empty string if none; `words` counts the whitespace separated tokens of the text nodes of the slide element, excluding `script`, `style` and `svg` content and every attribute value, and including eyebrow and footer text; `images` counts `img` elements only; `problems` counts the lint problems of that slide, warnings included) and `headings` is empty. For other files `slides` is empty and `headings` holds `{"level","text"}` in order. `total` is the number of slides, 0 for non presentations. Command line: `mcp-htmleditor outline <file>`; tool: `outline(file)`.
- **User visible text:** error `File not found: <file>`, exit status 1.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: Read one slide
> WHEN an agent asks for `get_slide` with a slide id THE Editor SHALL return the HTML of that slide only, with every image whose source is a data address longer than 1 000 characters replaced by the reference `data:ref:img-N`.

- **Business rules:** N counts from 1, in document order, within that slide. Command line: `mcp-htmleditor get-slide <file> <id>` prints the HTML; tool: `get_slide(file, id)`.
- **User visible text:** `Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2` (all ids, in order); `get_slide needs a presentation: <file>`; `File not found: <file>`.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-003 [EARS-E]: Patch
> WHEN an agent or a user applies `patch` with a list of operations THE Editor SHALL validate all operations before writing, then write the file once, atomically, so that either every operation is applied or none.

- **Business rules:** operations are JSON objects with an `op` field among `set_text`, `replace_slide`, `insert_slide`, `delete_slide`, `move_slide`. Operations apply in order to a working copy. Each id (`id`, `after`) designates a slide of the original file, and that id stays valid for as long as the slide is in the working copy, including after it is moved or replaced. An operation that designates a slide deleted by an earlier operation of the same patch fails with `unknown slide id "<id>"`. A `data-id` inside `html` is ignored for designation and an inserted slide cannot be designated by later operations of the same patch. `move_slide` with `after` equal to its own `id` leaves the slide unchanged. A slide's byte range runs from its opening `<article` tag to its closing tag. The `html` of `replace_slide` and `insert_slide` is written verbatim (only the renumbering of FR-NEW-009 edits it afterwards). `replace_slide` substitutes exactly that range. `insert_slide` writes, after the closing tag of the preceding slide (or before the first slide for `start`), a newline, the leading whitespace of the reference slide, then the HTML. `delete_slide` removes the range together with its line break and leading whitespace. `move_slide` moves the range with its leading whitespace; comments between slides stay where they are. Bytes outside the slides touched by the operations, and outside the counters renumbered by FR-NEW-009, are unchanged. A patch whose result equals the file writes nothing (the modification time does not change). Command line: `mcp-htmleditor patch <file> --ops <ops.json | ->  [--dry-run]` (`-` reads standard input); tool: `patch(file, ops, dry_run=false)`. While writing, the editor flag `update_in_progress` is true and it is false afterwards; the modification time changes only when the file changed. The result is the JSON object of FR-NEW-011. A file whose absolute, symlink resolved path contains the components `templates/bootstrap` or `templates/reference` is refused, before any other check and before the dry run, and the message shows the path as the caller gave it.
- **User visible text:** `patch failed at operation 2: unknown slide id "slide-9" (nothing written)` (the reason differs per operation, see below); `Invalid operations JSON: <reason>`; `patch failed at operation N: missing field "<name>" (nothing written)`; `patch failed at operation N: operation "<op>" needs a presentation (nothing written)`; an empty list gives `{"ok":true,"changed":false,"slides":<n>,"problems":[]}`; `Refusing to modify a template: <file>`; `patch failed at operation 1: unknown operation "frobnicate" (nothing written)`.
- **Scenario:** SC-003, SC-004
- **Priority:** Must

#### FR-NEW-004 [EARS-E]: Change a text
> WHEN a patch holds `{"op":"set_text","id":<id>,"selector":<css selector>,"text":<text>}` THE Editor SHALL replace the whole inner content of the first element matching the selector inside that slide by the text, escaped as plain text.

- **Business rules:** the selector is a CSS selector level 3 evaluated inside the slide element, the slide element itself being a candidate; first means document order; the children of the element are replaced by a single text node; the text is escaped exactly as `&` to `&amp;`, `<` to `&lt;`, `>` to `&gt;`, quotes and non ASCII characters being left as they are.

- **User visible text:** reasons `unknown slide id "<id>"`, `selector "<selector>" matches no element in slide "<id>"` and `invalid selector "<selector>"`.
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-005 [EARS-E]: Replace a slide
> WHEN a patch holds `{"op":"replace_slide","id":<id>,"html":<html>}` THE Editor SHALL replace that slide by the given HTML after restoring each `data:ref:img-N` to the Nth large image of the replaced slide.

- **Business rules:** the HTML is one slide element carrying `data-type="slide"` and a `data-id`.
- **User visible text:** reasons `slide html must have data-type="slide" and a data-id` and `unknown image reference "data:ref:img-3"`.
- **Scenario:** SC-005
- **Priority:** Must

#### FR-NEW-006 [EARS-E]: Insert a slide
> WHEN a patch holds `{"op":"insert_slide","after":<id or "start">,"html":<html>}` THE Editor SHALL insert the given slide after that slide, or first when `after` is `"start"`.

- **Business rules:** same HTML rule as FR-NEW-005; `data:ref:img-N` is not allowed in an inserted slide.
- **User visible text:** reasons `unknown slide id "<id>"` (for `after`), `slide html must have data-type="slide" and a data-id`, `unknown image reference "data:ref:img-1"`.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-007 [EARS-E]: Delete a slide
> WHEN a patch holds `{"op":"delete_slide","id":<id>}` THE Editor SHALL remove that slide.

- **User visible text:** reasons `unknown slide id "<id>"` and `cannot delete the last slide`.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-008 [EARS-E]: Move a slide
> WHEN a patch holds `{"op":"move_slide","id":<id>,"after":<id or "start">}` THE Editor SHALL move that slide after the given slide, or first when `after` is `"start"`.

- **User visible text:** reasons `unknown slide id "<id>"`; moving a slide after itself changes nothing.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-009 [EARS-E]: Renumbering
> WHEN a patch inserts, deletes, moves or replaces a slide THE Editor SHALL renumber the whole presentation once, after all operations.

- **Business rules:** slide ids and `data-id` become `slide-0`, `slide-1`, ... in order; the slide total constant and the list of slide names in the file's script become the number of slides and the `data-title` of each slide in order (written as double quoted strings, quotes and backslashes escaped, accents kept); in every slide eyebrow the pattern `Slide <n> / <total>` becomes `Slide 0N / TT` (two digits each); in a Carbon deck the footer pattern becomes `Slide N / TT` (no zero padding); in an Euro-Information or medical deck the page element holds N; N is the 1 based position. Only the numeric literal of the total constant is replaced; the slide names list is rewritten with one entry per line, indented like the first existing entry, with a trailing comma after each entry; the class `active` is removed from every slide and added once to the first slide, keeping the other classes and their order; if the script holds no total constant or no slide names list, nothing is created. A slide is an element with `data-type="slide"`, otherwise an `article.slide` or `section.slide` (outermost only). The eyebrow is the first `.slide-eyebrow` of the slide, the Carbon footer counter is `.slide-footer-right`, the page element is `.slide-foot-page`; only these elements are read or rewritten. The total constant is `const TOTAL = <integer>;` and the slide names list is `const slideNames = [ ... ];` in a script. A `set_text` alone triggers no renumbering.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-010 [EARS-E]: Dry run
> WHEN a patch is run with `--dry-run` (or `dry_run` true) THE Editor SHALL validate and compute the result and SHALL write nothing.

- **Business rules:** the result and the errors are the ones a real run gives, plus `"dry_run": true`.
- **Scenario:** SC-003, SC-004
- **Priority:** Must

#### FR-NEW-011 [EARS-E]: Patch result
> WHEN a patch succeeds THE Editor SHALL return `{"ok":true,"changed":<bool>,"slides":<count after>,"problems":[...]}` where `problems` holds the lint problems of the slides touched by the patch.

- **Business rules:** problems have the shape of FR-NEW-012; slides touched are the slides set, replaced or inserted; the slide ids are the ones after renumbering.
- **Scenario:** SC-003, SC-005
- **Priority:** Must

#### FR-NEW-012 [EARS-E]: Lint report
> WHEN an agent or a user runs `lint` on a file THE Editor SHALL report every problem found and a verdict, and exit with status 1 when at least one problem is an error.

- **Business rules:** command line `mcp-htmleditor lint <file> [--json]`; tool `lint(file)` returns the JSON form. A problem line is `<severity> <code> <slide> <message>` where `<slide>` is the slide id or `-` for the whole file, for example `error L002 - TOTAL is 8 but the file has 9 slides`. Problems are ordered whole file first, then slide by slide in order, then by code. Last line `lint: OK (0 errors, 2 warnings)` or `lint: FAIL (1 error, 2 warnings)` (`1 error` singular, `0 errors` and `2 errors` plural; same for warnings). JSON: `{"problems":[{"code","severity","slide","message"}],"errors":<n>,"warnings":<n>}` with `slide` null for the whole file. Documents, mails and websites are checked only by L010.
- **Scenario:** SC-006
- **Priority:** Must

#### FR-NEW-013 [EARS-E]: Structure rules
> WHEN `lint` runs on a presentation THE Editor SHALL apply these rules, all errors.

| Code | Rule | Message |
|---|---|---|
| L001 | a slide lacks `data-type="slide"`, `data-id` or `data-title` (one problem per missing attribute, in this order) | `missing attribute data-title` |
| L002 | the total constant differs from the number of slides | `TOTAL is 8 but the file has 9 slides` |
| L003 | the list of slide names has another length (L002 and L003 are not reported when the constant is absent; the length is the number of top level string literals) | `slideNames has 8 entries but the file has 9 slides` |
| L004 | two slides share an id, or ids are not `slide-0`, `slide-1`, ... in order (a slide that is both duplicate and out of order gives the duplicate problem only) | `duplicate id "slide-3"` or `expected id "slide-2" but found "slide-5"` |
| L005 | an existing counter differs from FR-NEW-009 | `eyebrow counter says "Slide 05 / 09", expected "Slide 03 / 09"`, `page counter says "5", expected "3"` or `footer counter says "Slide 5 / 9", expected "Slide 3 / 9"` |
| L006 | template text left: `Contenu de la slide`, `Titre de la présentation`, or the eyebrow `Section · Slide 01 / 01` on a slide that is not first of a one slide deck | `template text left: "Contenu de la slide"` |

- **Business rules:** L005 only checks a counter that exists: an eyebrow with no `Slide <n> / <total>` pattern, a slide with no eyebrow and a slide with no page element (cover, section) are not problems. N is the index plus 1. A Carbon footer `Slide N / TT` is checked too.
- **Scenario:** SC-006
- **Priority:** Must

#### FR-NEW-014 [EARS-E]: Charter rules
> WHEN `lint` runs on a presentation THE Editor SHALL apply these charter rules.

| Code | Severity | Rule | Message |
|---|---|---|---|
| L007 | error | a class belongs to another charter | `class "cds-tile" belongs to another charter than medical` |
| L008 | error | a child of a medical flex row has no width class | `child of .med-strip has no w-* width class` |
| L009 | error | a medical slide other than `title` and `thanks` has an image and no non empty `.med-source` | `slide has an image and no source line` |
| L010 | warning | an image source starts with `http://` or `https://` (all file types) | `remote image <url> is not exported` |
| L011 | warning | a colour in a `style` attribute is outside the charter palette, white, black and pure greys excepted | `colour #123456 is not in the medical palette` (colour written as in the file; one problem per distinct colour per slide) |

- **Business rules:** foreign classes: in a medical deck, any class starting `cds-`, `tag-`, `stat-`, `ei-`, or equal to `slide-inner`, `slide-header`, `slide-footer`, `slide-foot`, `slide-foot-logo`, `slide-foot-title`; in an Euro-Information deck, any class starting `med-`, `stat-`, `cw-`, `mention-`, or equal to `slide-header`, `slide-footer`; in a Carbon deck, any class starting `med-`, or equal to `slide-inner`, `slide-foot`, `slide-foot-logo`, `slide-foot-title`, `slide-foot-page`, `slide-title-rule`. Medical flex rows: `.med-strip`, `.med-split`, `.med-cols`, `.med-compare`, `.med-steps`, `.med-stats`, `.med-timeline`, `.med-section-figs`; accepted width classes `w-25`, `w-30`, `w-33`, `w-40`, `w-50`, `w-60`, `w-70`. Palettes: Euro-Information `#003A8D #284AAA #285C99 #FBAE40 #EC6962 #50565B #262626 #F4F6F9`; Carbon `#0F62FE #0043CE #EDF5FF #161616 #F4F4F4 #E0E0E0 #525252 #198038 #DA1E28`; medical `#159984 #0F6F60 #EE5A02 #E9EDEE #F5F7F8 #D7DEE2 #252525 #3A3A3A #5D5D5D #3D85C6 #C81E3A #0F2E4C #0B0E11 #14181D #2A323B #E8EDF2 #9AA7B4 #4FC3D9 #F2A33C`; comparison ignores letter case; a 3 digit hex colour is expanded before comparison; `rgb()`, `var(...)` and colour names are ignored; the check covers the `style` attribute of any element of a slide (not `<style>` blocks). L010 applies to the `src` of `img` elements only, in every file type; for a file that is not a presentation its slide column is `-` and lint emits no other code.
- **Scenario:** SC-006
- **Priority:** Must

#### FR-NEW-015 [EARS-E]: Templates, new file, export
> WHEN an agent calls `list_templates`, `new_file` or `export` THE Editor SHALL give the results of the command line `templates`, `new` and `export`.

- **Business rules:** `list_templates()` returns `[{"key","description"}]` for the 8 keys `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`; `new_file(template, file)` creates the file from the template and returns `{"ok":true,"file":<file>}`; `export(file, format, output)` returns `{"ok":true,"output":<output>,"warnings":[...]}` with format `pptx` or `docx`.
- **User visible text:** `Unknown template "x". Valid templates: ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`; `Unknown export format "foo". Valid formats: pptx, docx`; `File already exists: <file>`; `File not found: <file>`.
- **Scenario:** SC-007
- **Priority:** Must

#### FR-NEW-016 [EARS-U]: Same text on both surfaces
> The Editor SHALL give the same result for each of these operations through the command line and through the agent tool surface, the tool surface returning an error whose message is the command line error line without its `error: ` prefix.

- **Business rules:** command line errors are one line `error: <message>` on the error output, exit status 1 (2 for a usage error), empty standard output.
- **Scenario:** all
- **Priority:** Must

## 7. Non functional requirements (user observable)

No requirement beyond the above: reading is read only; `patch` is atomic (FR-NEW-003); access and privacy rules are unchanged.

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty states | the deck has one slide and it is deleted | refused | E2E-019 |
| Boundary values | insert at start, at end | renumbered | E2E-029 |
| Data variations | accented title with `&`, `<` | escaped correctly | E2E-030, E2E-033 |
| Exhaustion | image of 2 MB | short outputs | E2E-031 |
| Idempotency | same `set_text` twice | second `changed` false, file untouched | E2E-033 |
| Partial operations | valid and invalid operations mixed | nothing written | E2E-014 |
| Dry run | any patch | no write | E2E-032 |
| Concurrent actions, connectivity, access states, navigation | not applicable here (SPEC-0009) | none | none |

## 9. Acceptance tests (the contract)

### 9.0 Fixtures

- **DECK-EI**: an Euro-Information presentation, containing no inline colour outside the Euro-Information palette, no remote image, no template text and consistent counters, of 8 slides titled `Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`, ids `slide-0` to `slide-7`, slide 3 holding a 1 500 character image, slides 1 to 6 having page counters 2 to 7.
- **DECK-CARBON**: a Carbon presentation of 5 slides titled `Intro`, `Offre`, `Chiffres`, `Plan`, `Fin`, footers `Slide 1 / 5` to `Slide 5 / 5`.
- **DECK-MED**: a medical presentation of 6 slides with a slide of type `content` holding one image and a source line.
- **DOC-PERSO**: a document with a title, `h1` "Contexte", `h2` "Périmètre", `h1` "Risques".

### 9.1 Summary

| Test | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|
| E2E-001 | journey | SC-001 | FR-NEW-001, 016 | Critical |
| E2E-002 | journey | SC-001 | FR-NEW-001 | High |
| E2E-003 | journey | SC-002 | FR-NEW-002 | Critical |
| E2E-004 | journey | SC-003 | FR-NEW-003, 004, 011 | Critical |
| E2E-005 | journey | SC-004 | FR-NEW-006, 009, 011 | Critical |
| E2E-006 | journey | SC-004 | FR-NEW-007, 009 | Critical |
| E2E-007 | journey | SC-004 | FR-NEW-008, 009 | High |
| E2E-008 | journey | SC-005 | FR-NEW-005 | High |
| E2E-009 | journey | SC-006 | FR-NEW-012, 013 | Critical |
| E2E-010 | journey | SC-007 | FR-NEW-015 | High |
| E2E-011 | failure | SC-001 | FR-NEW-001, 015, 016 | High |
| E2E-012 | failure | SC-002 | FR-NEW-002, 016 | High |
| E2E-013 | failure | SC-003 | FR-NEW-003, 004, 007, 010 | Critical |
| E2E-014 | failure | SC-004 | FR-NEW-003, 008 | Critical |
| E2E-015 | failure | SC-003 | FR-NEW-003 | High |
| E2E-016 | failure | SC-003 | FR-NEW-003, 010 | High |
| E2E-017 | failure | SC-005 | FR-NEW-005, 006 | Critical |
| E2E-018 | failure | SC-005 | FR-NEW-005, 006 | High |
| E2E-019 | failure | SC-004 | FR-NEW-007 | High |
| E2E-020 | failure | SC-006 | FR-NEW-013 | High |
| E2E-021 | failure | SC-006 | FR-NEW-014 | High |
| E2E-022 | failure | SC-006 | FR-NEW-014 | High |
| E2E-023 | failure | SC-006 | FR-NEW-013 | High |
| E2E-024 | failure | SC-006 | FR-NEW-013 | High |
| E2E-025 | failure | SC-006 | FR-NEW-013 | Medium |
| E2E-026 | failure | SC-006 | FR-NEW-012 | High |
| E2E-027 | failure | SC-005 | FR-NEW-011 | High |
| E2E-028 | failure | SC-007 | FR-NEW-015, 016 | Medium |
| E2E-029 | edge | SC-004 | FR-NEW-006, 008, 009 | High |
| E2E-030 | edge | SC-004 | FR-NEW-009 | Medium |
| E2E-031 | edge | SC-001 | FR-NEW-001, 002 | Medium |
| E2E-032 | edge | SC-003 | FR-NEW-010 | High |
| E2E-033 | edge | SC-003 | FR-NEW-004, 003 | Medium |
| E2E-034 | side effect | SC-003 | FR-NEW-003 | High |
| E2E-035 | failure | SC-006 | FR-NEW-014 | High |
| E2E-036 | edge | SC-006 | FR-NEW-012, 014 | Medium |
| E2E-037 | edge | SC-006 | FR-NEW-014 | Medium |
| E2E-038 | failure | SC-006 | FR-NEW-013 | Medium |
| E2E-039 | failure | SC-006 | FR-NEW-013 | Medium |
| E2E-040 | failure | SC-003 | FR-NEW-003 | Medium |
| E2E-041 | failure | SC-003 | FR-NEW-003, 002, 012 | Medium |

Coverage: happy 10, failure 23, side effect 1, edge 7 (41 tests). Happy to failure ratio 1:2.3 (beats 1:1).

### 9.2 New tests

#### E2E-001: Outline of a deck
- **Given** DECK-EI
- **When** the user runs `mcp-htmleditor outline DECK-EI`
- **Then** the JSON has `charter` `ei`, `doc_type` `presentation`, `total` 8, `headings` empty and 8 `slides` entries; the entry at index 2 has `id` `slide-2`, `title` `Contexte`, `images` 0
- **And** the entry at index 3 has `images` 1; no entry or other field contains `base64`
- **And** the tool `outline` called with the same file returns an object equal to that JSON
- **Priority:** Critical

#### E2E-002: Outline of a document
- **Given** DOC-PERSO
- **When** the user runs `mcp-htmleditor outline DOC-PERSO`
- **Then** the JSON has `charter` `doc-perso`, `doc_type` `document`, `total` 0, `slides` empty
- **And** `headings` is `[{"level":1,"text":"Contexte"},{"level":2,"text":"Périmètre"},{"level":1,"text":"Risques"}]`
- **Priority:** High

#### E2E-003: Read one slide
- **Given** DECK-EI
- **When** the agent calls `get_slide` with `id` `slide-3`
- **Then** the HTML starts with `<article` and has `id="slide-3"`, contains no `base64` and contains `data:ref:img-1`
- **And** it does not contain the title `Contexte`
- **Priority:** Critical

#### E2E-004: Change a title
- **Given** DECK-EI
- **When** the agent calls `patch` with `[{"op":"set_text","id":"slide-2","selector":".slide-h1","text":"Contexte et enjeux"}]`
- **Then** the result is `{"ok":true,"changed":true,"slides":8,"problems":[]}`
- **And** the file differs from the original only in the content of that title element
- **Priority:** Critical

#### E2E-005: Insert in the middle
- **Given** DECK-EI and an HTML slide with `data-type="slide"`, `data-id="x"`, `data-title="Budget"`, eyebrow `Slide 01 / 01` and a page element holding `1`
- **When** the agent patches `[{"op":"insert_slide","after":"slide-4","html":<that slide>}]`
- **Then** the file has 9 slides; the new slide has id and `data-id` `slide-5`, eyebrow `Slide 06 / 09` and page element `6`
- **And** the former `Planning` is `slide-6` with page element `7`; the total constant is 9; the slide names list has 9 entries with `"Budget"` at index 5
- **And** the result `slides` is 9
- **Priority:** Critical

#### E2E-006: Delete on a Carbon deck
- **Given** DECK-CARBON
- **When** the agent patches `[{"op":"delete_slide","id":"slide-1"}]`
- **Then** the file has 4 slides titled `Intro`, `Chiffres`, `Plan`, `Fin` with ids `slide-0` to `slide-3`
- **And** the footers read `Slide 1 / 4` to `Slide 4 / 4` and eyebrow counters use `Slide 0N / 04`
- **Priority:** Critical

#### E2E-007: Move
- **Given** DECK-CARBON
- **When** the agent patches `[{"op":"move_slide","id":"slide-4","after":"slide-0"}]`
- **Then** the order is `Intro`, `Fin`, `Offre`, `Chiffres`, `Plan` with ids `slide-0` to `slide-4` and footers `Slide 1 / 5` to `Slide 5 / 5`
- **Priority:** High

#### E2E-008: Replace keeping the image
- **Given** DECK-EI and the HTML returned by `get_slide` for `slide-3`, where the title is changed to `Architecture cible`
- **When** the agent patches `[{"op":"replace_slide","id":"slide-3","html":<that html>}]`
- **Then** slide 3 shows `Architecture cible` and still holds the original 1 500 character image, byte for byte
- **Priority:** High

#### E2E-009: Clean lint
- **Given** DECK-EI
- **When** the user runs `mcp-htmleditor lint DECK-EI`
- **Then** the output is exactly `lint: OK (0 errors, 0 warnings)` and the exit status is 0
- **Priority:** Critical

#### E2E-010: Templates, new file, export
- **Given** an empty directory
- **When** the agent calls `list_templates`, `new_file` with `template` `doc` and `file` `a.html`, then `export` with `file` `a.html`, `format` `docx`, `output` `a.docx`
- **Then** `list_templates` returns 8 entries with the keys of FR-NEW-015 in that order
- **And** `new_file` returns `{"ok":true,"file":"a.html"}` and the file exists; `export` returns `ok` true and `a.docx` exists
- **Priority:** High

#### E2E-011: File not found
- **Given** no file `ghost.html`
- **When** the user runs `outline ghost.html`, `lint ghost.html`, `patch ghost.html --ops ops.json`, `export` on `ghost.html`
- **Then** each prints `error: File not found: ghost.html` on the error output, exits with status 1, prints nothing on the standard output
- **And** the tool `outline` returns an error whose message is `File not found: ghost.html`
- **Priority:** High

#### E2E-012: Unknown slide for get_slide
- **Given** DECK-CARBON
- **When** the user runs `get-slide DECK-CARBON slide-9`
- **Then** the error output is `error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2, slide-3, slide-4` and the exit status is 1
- **Priority:** High

#### E2E-013: Unknown id writes nothing
- **Given** DECK-EI, saved copy kept
- **When** the agent patches `[{"op":"set_text","id":"slide-1","selector":".slide-h1","text":"A"},{"op":"delete_slide","id":"slide-9"}]`, and again with `dry_run` true
- **Then** both calls fail with `patch failed at operation 2: unknown slide id "slide-9" (nothing written)`
- **And** the file equals the saved copy, and `set_text` with the selector `.nope` on `slide-1` fails with `patch failed at operation 1: selector ".nope" matches no element in slide "slide-1" (nothing written)`
- **Priority:** Critical

#### E2E-014: Mixed operations are atomic
- **Given** DECK-CARBON, saved copy kept
- **When** the agent patches `[{"op":"delete_slide","id":"slide-1"},{"op":"move_slide","id":"slide-2","after":"slide-7"}]`
- **Then** it fails with `patch failed at operation 2: unknown slide id "slide-7" (nothing written)` and the file equals the saved copy
- **Priority:** Critical

#### E2E-015: Unknown operation
- **Given** DECK-CARBON
- **When** the agent patches `[{"op":"frobnicate"}]`
- **Then** it fails with `patch failed at operation 1: unknown operation "frobnicate" (nothing written)`
- **Priority:** High

#### E2E-016: Template path refused
- **Given** a copy of a bootstrap template saved under `templates/bootstrap/x.html`
- **When** the agent patches it with a valid `set_text`, with and without `--dry-run`
- **Then** both fail with `Refusing to modify a template: templates/bootstrap/x.html` and the exit status is 1
- **Priority:** High

#### E2E-017: Replacement without required attributes
- **Given** DECK-EI
- **When** the agent patches `replace_slide` on `slide-2` with `<article><h1>x</h1></article>`, and `insert_slide` after `slide-2` with the same HTML
- **Then** each fails with `patch failed at operation 1: slide html must have data-type="slide" and a data-id (nothing written)`
- **Priority:** Critical

#### E2E-018: Unknown image reference
- **Given** DECK-EI (slide 3 has one large image)
- **When** the agent patches `replace_slide` on `slide-3` with a valid slide holding `data:ref:img-3`, and `insert_slide` with a valid slide holding `data:ref:img-1`
- **Then** the first fails with `patch failed at operation 1: unknown image reference "data:ref:img-3" (nothing written)` and the second with `... unknown image reference "data:ref:img-1" (nothing written)`
- **Priority:** High

#### E2E-019: Last slide
- **Given** a presentation of one slide
- **When** the agent patches `delete_slide` on `slide-0`
- **Then** it fails with `patch failed at operation 1: cannot delete the last slide (nothing written)`
- **Priority:** High

#### E2E-020: Total wrong
- **Given** DECK-EI where the total constant is set to 7
- **When** the user runs `lint`
- **Then** the output holds `error L002 - TOTAL is 7 but the file has 8 slides`, ends with `lint: FAIL (1 error, 0 warnings)`, exit status 1
- **Priority:** High

#### E2E-021: Foreign class
- **Given** DECK-MED where slide `slide-2` holds `<div class="cds-tile">`
- **When** the user runs `lint`
- **Then** the output holds `error L007 slide-2 class "cds-tile" belongs to another charter than medical`
- **Priority:** High

#### E2E-022: Missing width class
- **Given** DECK-MED where `slide-3` has a `.med-strip` whose second child has no `w-*` class
- **When** the user runs `lint`
- **Then** the output holds `error L008 slide-3 child of .med-strip has no w-* width class`
- **Priority:** High

#### E2E-023: Template text left
- **Given** DECK-EI where `slide-4` still holds `Contenu de la slide`
- **When** the user runs `lint`
- **Then** the output holds `error L006 slide-4 template text left: "Contenu de la slide"`
- **Priority:** High

#### E2E-024: Missing attributes
- **Given** DECK-EI where `slide-5` has no `data-title`
- **When** the user runs `lint`
- **Then** the output holds `error L001 slide-5 missing attribute data-title`
- **Priority:** High

#### E2E-025: Wrong counters
- **Given** DECK-EI where the eyebrow of `slide-2` reads `Slide 05 / 08` and its page element reads `5`
- **When** the user runs `lint`
- **Then** the output holds `error L005 slide-2 eyebrow counter says "Slide 05 / 08", expected "Slide 03 / 08"` then `error L005 slide-2 page counter says "5", expected "3"`
- **Priority:** Medium

#### E2E-026: Exit status
- **Given** DECK-EI with one warning only (a remote image) and DECK-EI with one error
- **When** the user runs `lint` on each
- **Then** the first prints `lint: OK (0 errors, 1 warning)` and exits 0; the second ends with `lint: FAIL (1 error, 0 warnings)` and exits 1
- **And** `lint --json` on the second prints `{"problems":[...],"errors":1,"warnings":0}` with `slide` null for a whole file problem
- **Priority:** High

#### E2E-027: Lint problems in the patch result
- **Given** DECK-MED
- **When** the agent patches `replace_slide` on `slide-1` with a valid slide holding an image and no source line, with `data-slide-type="content"`
- **Then** the result `problems` is `[{"code":"L009","severity":"error","slide":"slide-1","message":"slide has an image and no source line"}]`, `ok` is true and the file is written
- **And** problems of other slides are not listed
- **Priority:** High

#### E2E-028: Tool failures
- **Given** DECK-EI and `a.html` existing
- **When** the agent calls `export` with format `foo`, `new_file` with template `x`, and `new_file` with `template` `doc` and `file` `a.html`
- **Then** the errors are `Unknown export format "foo". Valid formats: pptx, docx`, `Unknown template "x". Valid templates: ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`, and `File already exists: a.html`; `a.html` is unchanged
- **Priority:** Medium

#### E2E-029: Insert at both ends and move to the ends
- **Given** DECK-CARBON
- **When** the agent, each time on a fresh copy of DECK-CARBON, inserts a valid slide titled `Début` with `after` `"start"`, then inserts `Fin 2` after `slide-4`, then moves `slide-2` with `after` `"start"`
- **Then** after the first run the order starts `Début`, `Intro` with footers `Slide 1 / 6`, `Slide 2 / 6`; after the second the last slide is `Fin 2` with footer `Slide 6 / 6`; after the third `Chiffres` is first
- **Priority:** High

#### E2E-030: Titles with special characters
- **Given** DECK-EI and a valid slide whose attribute is `data-title="Café &amp; &quot;Co&quot; &lt;1&gt;"`
- **When** the agent inserts it after `slide-1`
- **Then** the slide names list holds the entry `"Café & \"Co\" <1>"`, the attribute in the HTML is unchanged, and `lint` reports no problem
- **Priority:** Medium

#### E2E-031: Large image
- **Given** DECK-EI where slide 3 holds an image of 2 MB
- **When** the user runs `outline` and `get-slide DECK-EI slide-3`
- **Then** the outline is under 20 000 bytes and the slide HTML under 5 000 bytes
- **Priority:** Medium

#### E2E-032: Dry run
- **Given** DECK-CARBON, saved copy kept
- **When** the agent patches `[{"op":"delete_slide","id":"slide-1"}]` with `dry_run` true
- **Then** the result is `{"ok":true,"changed":true,"slides":4,"problems":[],"dry_run":true}` and the file equals the saved copy, modification time unchanged
- **Priority:** High

#### E2E-033: Escaping and idempotency
- **Given** DECK-EI
- **When** the agent runs `set_text` on `slide-2` `.slide-h1` with the text `R&D <b>x</b>` twice
- **Then** after the first run the title element contains the text `R&D <b>x</b>` as plain text (`R&amp;D &lt;b&gt;x&lt;/b&gt;` in the file) and `changed` is true
- **And** the second run gives `changed` false, and the modification time of the file did not change
- **Priority:** Medium

#### E2E-034: Editor state around a patch
- **Given** the editor server running on DECK-EI
- **When** the agent runs a `set_text` patch
- **Then** `get_status` afterwards shows `update_in_progress` false and a later modification time than before
- **And** a no change patch leaves the modification time unchanged
- **Priority:** High

#### E2E-035: Image without source
- **Given** DECK-MED where `slide-1` of type `content` holds an image and an empty source element, and `slide-0` (type `title`) holds a logo image and no source
- **When** the user runs `lint`
- **Then** the output holds `error L009 slide-1 slide has an image and no source line` and no problem for `slide-0`
- **Priority:** High

#### E2E-036: Remote image and report form
- **Given** DECK-EI where `slide-2` holds `<img src="https://example.com/a.png">`
- **When** the user runs `lint`, then `lint --json`
- **Then** the text output holds `warning L010 slide-2 remote image https://example.com/a.png is not exported` and ends with `lint: OK (0 errors, 1 warning)`
- **And** `outline` reports `problems` 1 for `slide-2`
- **Priority:** Medium

#### E2E-037: Palette warning
- **Given** DECK-MED where `slide-2` holds `style="color:#123456"` and another element `style="color:#159984; background:#FFFFFF; border-color:#777777"`
- **When** the user runs `lint`
- **Then** the output holds exactly one palette warning: `warning L011 slide-2 colour #123456 is not in the medical palette`
- **Priority:** Medium

#### E2E-038: Slide names list length
- **Given** DECK-EI where the slide names list holds 7 entries
- **When** the user runs `lint`
- **Then** the output holds `error L003 - slideNames has 7 entries but the file has 8 slides`
- **Priority:** Medium

#### E2E-039: Ids out of order
- **Given** DECK-EI where the id of the third slide is `slide-5` (its `data-id` too)
- **When** the user runs `lint`
- **Then** the output holds `error L004 slide-5 expected id "slide-2" but found "slide-5"`
- **And** with two slides both named `slide-3`, the output holds `error L004 slide-3 duplicate id "slide-3"`
- **Priority:** Medium

#### E2E-040: Missing field in an operation
- **Given** DECK-EI
- **When** the agent patches `[{"op":"set_text","id":"slide-1","selector":".slide-h1"}]`, and runs the command `patch` with the content `not json`
- **Then** the first fails with `patch failed at operation 1: missing field "text" (nothing written)`
- **And** the second prints `error: Invalid operations JSON: ` followed by a reason and exits with status 1
- **Priority:** Medium

#### E2E-041: Slide operations on a document
- **Given** DOC-PERSO
- **When** the agent patches `[{"op":"delete_slide","id":"slide-0"}]` and calls `get_slide` with `id` `slide-0`
- **Then** the patch fails with `patch failed at operation 1: operation "delete_slide" needs a presentation (nothing written)` and `get_slide` fails with `get_slide needs a presentation: DOC-PERSO`
- **And** `lint` on DOC-PERSO prints `lint: OK (0 errors, 0 warnings)`
- **Priority:** Medium

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 016 | E2E-001, 002 | E2E-011 | E2E-031 |
| SC-002 | FR-NEW-002 | E2E-003 | E2E-012 | E2E-031 |
| SC-003 | FR-NEW-003, 004, 010, 011 | E2E-004 | E2E-013, 015, 016, 040, 041 | E2E-032, 033, 034 |
| SC-004 | FR-NEW-006 to 009 | E2E-005, 006, 007 | E2E-014, 019 | E2E-029, 030 |
| SC-005 | FR-NEW-005, 011 | E2E-008 | E2E-017, 018, 027 | E2E-008 |
| SC-006 | FR-NEW-012 to 014 | E2E-009 | E2E-020 to 026, 035, 038, 039 | E2E-036, 037 |
| SC-007 | FR-NEW-015 | E2E-010 | E2E-028 | E2E-010 |

Requirements to tests: FR-NEW-001 (001, 002, 011, 031); 002 (003, 012, 031, 041); 003 (004, 013, 014, 015, 016, 033, 034, 040, 041); 004 (004, 013, 033); 005 (008, 017, 018); 006 (005, 017, 018, 029); 007 (006, 013, 019); 008 (007, 014, 029); 009 (005, 006, 007, 029, 030); 010 (013, 016, 032); 011 (004, 005, 027); 012 (009, 026, 036, 041); 013 (009, 020, 023, 024, 025, 038, 039); 014 (021, 022, 035, 036, 037); 015 (010, 011, 028); 016 (001, 011, 012, 028).

## 11. Open questions

None.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Charter | The visual identity of a file: `ei`, `carbon`, `medical`, `doc`, `doc-perso`, `doc-ei`, `mail`, `website` | Deck structure |
| Slide id | `slide-N`, N from 0 in order | Deck structure |
| Counter | The text `Slide 0N / TT` in an eyebrow, `Slide N / TT` in a Carbon footer, or the page number element | Deck structure |
| Total constant | The number of slides stored in the file's script | Deck structure |
| Slide names list | The list of slide titles stored in the file's script | Deck structure |
| Operation | One element of a patch | Agent tools |
| Problem | One lint finding with code, severity, slide and message | Quality rules |
| Image reference | `data:ref:img-N`, a stand in for a large image in `get_slide` output | Agent tools |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 8 | 4 | NOT-IMPLEMENTABLE |
| 2 | 10 | 3 | NOT-IMPLEMENTABLE (amended after; cap of two rounds reached, waiver requested) |

**Amendments applied:** all F findings of rounds 1 and 2. **Concern (user waiver, 2026-11-03):** the two round cap was reached with F findings amended but not re audited; byte level and message details may still surface at design or implementation.
**No implementation detail outside Section 14:** PASS

## 14. Evidence appendix

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| 7 tools, none reads or edits content | `src/mcp_htmleditor/mcp_server.py:31,81,93,112,133,150,166` |
| `new`, `templates`, `export` only on the command line | `src/mcp_htmleditor/cli.py:51,67,240` |
| renumbering only in the browser | `src/mcp_htmleditor/static/editor.js:1490-1603` |
| browser save to a template silently skipped | `src/mcp_htmleditor/http_server.py:325` |
| charter detection | `src/mcp_htmleditor/static/slide-layouts.js:12-18`, `src/mcp_htmleditor/export/pptx_style.py:377-386` |

Test command: `make test`; gate `make check`.

### 14.3 Design inputs
- Existing commands `export` and `arch-layout` use click's own existence check (`src/mcp_htmleditor/cli.py:125,216,238`, exit status 2); FR-NEW-016 and E2E-011 require `error: File not found: <file>` with exit status 1 for the new commands and for `export`. Detection signal: E2E-011.

- No Python code renumbers a deck, parses the `TOTAL` and `slideNames` constants, or detects a charter for the lint and outline rules; `find_slides` (`src/mcp_htmleditor/export/to_pptx.py:272`) and `detect_theme` are the closest helpers. Detection signal: E2E-005, E2E-001.
- `patch` must change bytes outside the touched slides only where FR-NEW-009 requires; a parse and re-serialize round trip (as in `_strip_editor_artifacts`, `src/mcp_htmleditor/http_server.py:464-476`) would reformat the file. Detection signal: E2E-004 (byte identity).
- The update flag lives in `state.py` and is per process; a patch run from the command line cannot reach the flag of a separately running server. Detection signal: E2E-034.
- Palettes and the foreign class lists above come from the skill (`skill/types/slides.md`, `skill/types/medical.md`); they are product rules now, no code holds them.
- `list_templates` descriptions come from `src/mcp_htmleditor/templates.py`.
- Documents to update: `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md`, `.agent_docs/observability.md`, `skill/SKILL.md` core tool list (SPEC-0006).
