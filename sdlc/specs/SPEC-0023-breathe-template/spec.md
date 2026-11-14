# Breathe presentation template: functional specification

> Id: SPEC-0023
> Nature: FEAT
> Depth: L
> Depth evidence: 6 areas touched (template catalogue, deck checking, PPTX export, editor page and its layout picker, editor server, agent skill), 36 requirements (25 new, 3 modified, 8 non functional), a new public command and a new kind of served file; no persisted concept
> Status: specified
> Generated on: 2026-11-14
> Project: existing
> From backlog: BL-0044
> Depends on: SPEC-0007 (templates, lint, export), SPEC-0017 (pointer), SPEC-0022 (speaker notes, presenter)
> Security: internal finding (new capability: the editor server reads files named by the request path; path traversal class swept, Section 14.2)
> CVSS: not scored
> Affected: n/a (the capability does not exist before this increment)
> Fixed in: unreleased

Nature: FEAT (Q1 yes: no `breathe` template is listed, `src/mcp_htmleditor/export/charters.py:26`; Q2 no
authority states a Breathe template exists, so nothing is violated). Work branch: `feat/breathe-template`,
imposed by the user for this run (instead of `feat/0044-breathe-template`).

Process note: the user asked for an unattended run on 2026-11-14 ("decide, record decisions and tradeoffs").
The interview rounds were answered from the user's brief and the repository; product choices are recorded as
scope and requirements, and the test plan approval of Phase 8.5 is taken under that standing instruction.

## 1. Summary

Dr Lamya CHRIF MORAND presents at congresses from a template called Breathe (direction B, "Editorial, airway
as a story line"): ice and navy panels, Georgia titles, circled line icons, and one airway line across the top
of every slide that shows where the audience is in the patient pathway. Today it lives outside the editor and
pretends to be the medical template; three hand run scripts embed its pictures, repaint the PPTX after every
export and verify it. This increment makes Breathe a template of the editor: listed, created with one command,
a reference deck with every layout, the layouts in the editor's picker, checked by `lint`, exported to a PPTX
that matches the rendered slides with the speaker notes, a command that embeds or links its pictures, a skill
topic for agents, and an editor server that shows pictures stored next to the deck. A second talk must be built
from it on 2026-11-15.

## 2. Current State (MANDATORY)

### 2.1 What users can do today

- `mcp-htmleditor templates` lists eight keys: `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`;
  `new <key> <file>` copies the starting point of a key; any other key is refused with `Unknown template "x".
  Valid templates: ei, carbon, medical, doc, doc-perso, doc-ei, mail, website` (E1, E2).
- A template file dropped in the user's templates folder under a new name is not listed and cannot be created
  with `new`; only an existing key can be overridden (E3).
- A presentation is recognised as medical when its styles name the medical colour token or its page declares
  `data-doc-template="medical"`; as Euro-Information on its own token or cover logos; as Carbon otherwise (E4).
  The PPTX export recognises medical from the token or the `med-rule` class only, not from the declaration (E5).
- The Breathe template and the talk built with it (WCBIP 2026, 14 slides) declare `data-doc-template="medical"`
  and keep the medical colour token on purpose, so that lint and export treat them as medical (E6).
- `lint` applies the structure rules L001 to L006 to every presentation and the charter rules L007 to L011 to
  the Carbon, Euro-Information and medical charters; L008 (width classes of flex rows) and L009 (source line
  under a picture) apply to medical only; the placeholder texts L006 knows are French (E7).
- The PPTX export rebuilds each slide from estimates: it draws the chrome of the charter, then stacks the
  content top to bottom. It cannot place absolute compositions such as the Breathe panes; it does not read
  background pictures set by a class; the speaker notes aside of a slide goes to its notes page (E8, E9).
- Breathe decks therefore go through a separate script after every export: it opens the deck in Chromium,
  measures every slide and repaints each PPTX slide from the measures (background picture, coloured boxes,
  icons and pictures at their rendered box, text boxes with the browser's line breaks and faces); it refuses a
  file it already finished (E10).
- The editor page shows the deck from the server; a picture referenced by a relative path (`assets/x.png`)
  is answered `Not found`, so Breathe decks inline every picture and decoration as text inside the file (2 MB
  for the WCBIP deck) through a second script (E11, E12).
- The layout picker of the editor offers three layout sets (Carbon, Euro-Information, medical) chosen from the
  open deck; a Breathe deck gets the medical set (E13).
- `mcp-htmleditor skill` lists 15 topics; none covers Breathe (E14).

### 2.2 Specs governing this area

- SPEC-0007/FR-NEW-013, FR-NEW-014, FR-NEW-015: lint rules, charter rules and the list of 8 template keys.
  This increment extends them (FR-MOD-001 to FR-MOD-003); SPEC-0007 is not modified.
- SPEC-0012: one registry holds every charter fact. Breathe is added to it, nothing else holds a charter list.
- SPEC-0016 and SPEC-0017: every presentation file under the templates carries fullscreen support and the
  pointer. The Breathe starting point and reference deck carry them.
- SPEC-0022/FR-6: speaker notes are an aside, direct child of the slide, written to the PPTX notes page with
  their text unchanged. The Breathe export keeps exactly that rule.
- SPEC-0005 and SPEC-0013: every request to the editor server passes the request gate (trusted host name,
  same origin, unambiguous headers). The new picture answers pass the same gate.

### 2.3 What is verified today

Template listing, starting points and the registry are tested; lint charter rules are tested for the three
slide charters; the PPTX export is pinned by recorded fingerprints of ten templates; speaker notes reach the
notes page; the editor server gate is attacked by raw requests; every presentation file under the templates is
checked for fullscreen and pointer support. Nothing exercises Breathe, relative pictures in the editor, or a
painted export (E15).

## 3. Scope

### 3.1 In scope

1. A `breathe` template key with its own charter: starting point (one cover slide), description, listing.
2. A reference deck with the 20 layouts and 3 variants of the Breathe template (23 slides).
3. The Breathe layouts in the editor's layout picker.
4. Recognition of the charter by lint, export and picker, from the page declaration or the Breathe marker.
5. Lint: Breathe palette, foreign classes, width classes, source lines, counters, an English placeholder.
6. PPTX export of a Breathe deck painted from the rendered slides, with the speaker notes; a degraded export
   with one warning when Chromium is unavailable.
7. A command that embeds the decoration and pictures a deck uses, as text (inline) or as files next to the
   deck (link).
8. The catalogue of decoration pictures (backgrounds, icons, logo disc, samples) shipped with the templates,
   and the maintainer's generator that redraws it.
9. The editor server answers the picture, media, font and style files stored next to the open deck.
10. A `breathe` skill topic, the template list of the skill core, README and agent documentation.

### 3.2 Out of scope, and why

- Renaming the Breathe class vocabulary (`med-*`): the 23 layouts and the WCBIP deck use it; a rename brings
  no user value before 2026-11-15 and would break the switch of existing decks by one attribute.
- An agent tool (MCP) for the embedding command: agents run the command line; BL-0045.
- Picker insertion that embeds pictures by itself: the person runs the embedding command after inserting
  layouts; BL-0046.
- Changes to the medical, Euro-Information or Carbon charters: their decks and exports stay byte for byte as
  today; their lint results change only by the English placeholder of FR-MOD-003.
- Pictures named by a deck outside its folder reach the PPTX export today, as author content; containing them
  is a separate change, BL-0047.
- Editing PPTX text boxes so they rewrap: the painted export keeps the browser's line breaks (known difference).
- Video embedding: the video layout keeps its poster picture; the video is inserted in PowerPoint.
- Moving Lamya's existing decks: they keep working as medical; switching one is a one attribute edit she
  decides (documented).

### 3.3 Constraints imposed by the context

- The user: Breathe is its own charter key and marker, never `medical`; existing decks declaring medical keep
  working exactly as today; pictures inlined as text keep working; the work is not merged, pushed or installed
  by the agent.
- The house rules: binary files are stored through large file storage; no dashes as punctuation in visible
  text of the Breathe slides; English slide text.
- Privacy: the WCBIP deck embeds clinical pictures and event photos; it is never copied into the product's
  repository. Tests using it read it from its fixed location and are skipped when it is absent; every behaviour
  they check is also checked on in repository fixtures.
- Public contracts kept verbatim: the HTTP answers and the deck markup named in Sections 5 to 9 (`Not found`
  answers, media types, the log line format, `data-asset`, `data-doc-template`, `--breathe-ice`, `<style>`) are
  the existing public contract of the editor server and of the deck format, named on purpose.

## 4. Actors

| Actor | Goal |
|---|---|
| Author | Lamya, or the person building a talk: creates, edits, checks and exports a Breathe deck |
| Agent | An AI agent that builds a deck through the command line and the skill |
| Maintainer | Changes the template, its pictures or its generator in the repository |
| Local process | Any other program on the machine talking to the editor server |

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Template catalogue | the keys, starting points, reference decks, decoration catalogue | template key, starting point, reference deck, layout, decoration |
| Deck checking | the rules a deck must satisfy, per charter | charter, problem, palette, foreign class |
| Export | the PPTX produced from a deck | painted export, degraded export, notes page |
| Editing | the editor page, its picker and its server | layout picker, served file, request gate |
| Agent guidance | the skill text | skill topic, core index |

## 5. Usage scenarios

### SC-001: Create a Breathe deck
**Actor:** Author or Agent
**Preconditions:** the editor is installed; `talk.html` does not exist.
**Flow:**
1. Types `mcp-htmleditor templates` → sees the line `breathe` with its description, after `medical`.
2. Types `mcp-htmleditor new breathe talk.html` → `talk.html` is created: one cover slide, ice and navy panes,
   the airway line, the botanical logo disc, placeholder texts, a speaker notes aside, the presentation keys.
3. Opens it in a browser or in the editor → the cover shows its background and icons with no other file.
**Postconditions:** the deck is a Breathe deck for lint, export and the picker.
**Exceptions:**
- EXC-001a: `talk.html` exists → `error: File already exists: talk.html`, nothing written.
- EXC-001b: unknown key `breath` → the error lists the 9 keys.

### SC-002: Build slides from the Breathe layouts
**Actor:** Agent or Author
**Preconditions:** a Breathe deck is open or on disk.
**Flow:**
1. The agent reads the reference deck (23 slides, one per layout or variant) and copies the slides it needs.
2. In the editor, the author opens the layout picker → it offers the 23 Breathe layouts, named like the
   reference slides, and inserts one → the slide is added and the counters follow.
**Postconditions:** the slide structure equals the reference slide.
**Exceptions:**
- EXC-002a: the inserted layout uses decoration or pictures the deck has not embedded yet → they show empty
  until the embedding command runs (SC-003).

### SC-003: Embed the decoration and pictures of a deck
**Actor:** Author or Agent
**Preconditions:** a Breathe deck with a decoration block; pictures named by file name on `<img>` elements.
**Flow:**
1. Types `mcp-htmleditor breathe-inline talk.html` → every background and icon the slides use, and every named
   picture, is written into the file as text; the command prints what it embedded and the file size.
2. Or types `mcp-htmleditor breathe-inline talk.html --link` → the deck refers to the files instead, and the
   decoration files missing from the deck's `assets` folder are copied there.
**Postconditions:** the deck renders the same in a browser, the editor, the render and the export.
**Exceptions:**
- EXC-003a: no decoration block → refused, file unchanged.
- EXC-003b: a picture or decoration file is found nowhere → refused, file unchanged, the name and the folders
  searched are printed.

### SC-004: Edit a deck whose pictures sit next to it
**Actor:** Author
**Preconditions:** `talk.html` links `assets/photo.jpg`, stored in the deck's folder.
**Flow:**
1. Types `mcp-htmleditor serve talk.html` → the editor shows the slide with its picture.
**Postconditions:** nothing outside the deck's folder can be read through the server.
**Exceptions:**
- EXC-004a: a request names a path climbing out of the folder, a hidden file, a file of another type, or a
  missing file → `Not found`, nothing read.
- EXC-004b: a request from an untrusted host or origin → refused by the gate as today.

### SC-005: Check a Breathe deck
**Actor:** Agent
**Flow:** types `mcp-htmleditor lint talk.html` → problems against the Breathe charter, then the verdict.
**Exceptions:** EXC-005a: a Carbon or medical only class on a Breathe slide → L007 error.

### SC-006: Export a Breathe deck to PPTX
**Actor:** Author or Agent
**Flow:**
1. Types `mcp-htmleditor export pptx talk.html talk.pptx` (or uses the editor's export or the agent tool) →
   one PPTX slide per HTML slide, each painted from the rendered slide, the notes on the notes pages.
**Postconditions:** the PPTX opens in PowerPoint and looks like the HTML render; text stays editable.
**Exceptions:**
- EXC-006a: Chromium is unavailable → the export still completes, each slide gets its background picture and
  its content flowed, and one warning says how to install the browser.

### SC-007: Redraw or list the decoration catalogue
**Actor:** Maintainer
**Flow:** types `make breathe-assets` → every background, icon, the logo disc and the sample pictures are
redrawn into the template catalogue; `make breathe-assets ARGS=--list` prints the catalogue and writes nothing.

### SC-008: Learn the Breathe rules
**Actor:** Agent
**Flow:** types `mcp-htmleditor skill` → the core lists the `breathe` topic and the 9 template keys; types
`mcp-htmleditor skill --type breathe` → layouts, airway stages, icons, sizing, notes, embedding and export.

### SC-009: Keep the medical decks, move one to Breathe
**Actor:** Author
**Preconditions:** a deck declaring `data-doc-template="medical"` with the medical colour token, built from the
Breathe template before this increment.
**Flow:**
1. Lints and exports it as before → same problems, same PPTX as before this increment.
2. Changes the declaration to `data-doc-template="breathe"` → it is a Breathe deck: Breathe lint, painted export.

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-U]: Breathe template key
> The Template catalogue SHALL offer the key `breathe`, listed right after `medical`, with the description
> `Breathe congress presentation: airway story line, ice and navy panels, Georgia titles, 1 cover slide`.

- **Business rules:** order of `templates`: `ei, carbon, medical, breathe, doc, doc-perso, doc-ei, mail, website`.
- **Scenario:** SC-001 · **Priority:** Must

#### FR-NEW-002 [EARS-E]: Breathe starting point
> WHEN the author types `mcp-htmleditor new breathe <file>` THE Template catalogue SHALL write a deck of one
> cover slide that declares the Breathe charter, carries the Breathe marker, shows its background, icons and
> logo disc with no other file, and holds the placeholder `Title of the presentation`, an empty speaker notes
> aside, fullscreen support, the pointer and the presenter.

- **Business rules:** canvas 960 x 540; slide id `slide-0`; page language English; `lint` on the new deck
  reports exactly one error, `error L006 slide-0 template text left: "Title of the presentation"`.
- **Scenario:** SC-001 · **Priority:** Must

#### FR-NEW-003 [EARS-U]: Charter recognition
> The Editor SHALL treat a presentation as Breathe, in lint, export and the layout picker alike, when its page
> declares `data-doc-template="breathe"`, or when its styles carry the Breathe marker `--breathe-ice` and its
> page does not declare `data-doc-template="medical"`.

- **Business rules:** a page declaring `medical` stays medical whatever it carries; recognition of the other
  charters is unchanged; the marker counts only when the text `--breathe-ice` appears in a `<style>` element
  outside CSS comments; the declaration is the `data-doc-template` value of the `<html>` element, compared case
  sensitively for `breathe` and `medical`.
- **Scenario:** SC-001, SC-009 · **Priority:** Must

#### FR-NEW-004 [EARS-U]: Reference deck
> The Template catalogue SHALL ship a Breathe reference deck of 23 slides whose slide names are, in this order:
> 1 `Cover`, 2 `Disclosure`, 3 `Pathway`, 4 `Part 2: Diagnose`, 5 `Key figures`, 6 `Key figures, deep`,
> 7 `Statement`, 8 `Content with picture`, 9 `Content with card`, 10 `Table`, 11 `Clinical image`, 12 `Compare`,
> 13 `Statement, deep`, 14 `Clinical case`, 15 `Annotated image`, 16 `Timeline`, 17 `Paper highlight`,
> 18 `Video poster`, 19 `Survey`, 20 `Priorities`, 21 `References`, 22 `Thanks, collage`, 23 `Thanks, message`.

- **Business rules:** the slide name is the name printed by `mcp-htmleditor outline` and shown by the
  presenter; `lint` gives 0 errors and 0 warnings; the render report gives no problem; every slide has a speaker
  notes aside; it presents full screen and carries the pointer and the presenter.
- **Scenario:** SC-002 · **Priority:** Must

#### FR-NEW-005 [EARS-S]: Breathe layouts in the picker
> WHILE a Breathe deck is open in the editor THE Editing context SHALL offer in the layout picker the 23
> layouts of the reference deck, in its order, each labelled with the reference slide name, each inserting
> the reference slide with its texts and an empty picture where the reference shows one.

- **Business rules:** a medical deck keeps the 16 medical layouts; a Carbon or Euro-Information deck keeps its
  set; the picker set stays identical to the reference deck (a stale set fails the repository gate); an empty
  picture keeps its asset name, so a later `breathe-inline` fills it with the reference sample.
- **Scenario:** SC-002 · **Priority:** Must

#### FR-NEW-006 [EARS-E]: Embed inline
> WHEN the author types `mcp-htmleditor breathe-inline <file>` THE Template catalogue SHALL write into the
> deck's decoration block one rule per background or icon class used by its slides, with the picture as text,
> fill every `<img data-asset="<name>">` with that picture as text, and print
> `<file>: <N> background and icon classes, <M> pictures embedded, <K> KB`.

- **Business rules:** files are searched in the deck's `assets` folder, then in the template catalogue, first
  found wins; only classes used by slides count (not those quoted in the styles); classes are written in
  alphabetical order; running it twice gives the same file; `<K>` is the size in bytes of the written file
  divided by 1024, rounded down; `<file>` is printed as typed; the previous version of the deck is kept in its
  history under the reason `breathe-inline` (restorable with `mcp-htmleditor restore`), and a run that leaves
  the file byte for byte unchanged adds no entry; a class `med-bg-<x>` needs the file `bg-<x>.png`, a class
  `med-ico-<x>` the file `icon-<x>.png`, and an asset name of a picture is the file name itself; `<N>` is the
  number of distinct background and icon classes, `<M>` the number of picture elements naming an asset, each
  element counted once even when two name the same file; the catalogue searched is the one shipped with the
  installed editor (a catalogue in the user's templates folder is never searched).
- **Scenario:** SC-003 · **Priority:** Must

#### FR-NEW-007 [EARS-E]: Embed by link
> WHEN the author types `mcp-htmleditor breathe-inline <file> --link` THE Template catalogue SHALL write the
> same rules and pictures as references to `assets/<name>` next to the deck, copy into the deck's `assets`
> folder every needed file found only in the template catalogue, and print
> `<file>: <N> background and icon classes, <M> pictures linked, <C> files copied to <folder>, <K> KB`.

- **Business rules:** a file already in the deck's `assets` folder is never overwritten; the folder is created
  when missing; switching back without `--link` embeds as text again; `<C>` counts the files copied;
  `<folder>` is the absolute path of the deck's folder followed by `/assets`; `<K>` and `<file>` as in
  FR-NEW-006.
- **Scenario:** SC-003 · **Priority:** Must

#### FR-NEW-008 [EARS-O]: Embedding refused
> IF the deck has no decoration block, or a needed file is found in no folder searched, THEN THE Template
> catalogue SHALL leave the deck and its folder unchanged, print one error line and exit with status 1.

- **Business rules:** checks run in this order and only the first failure is printed: deck file missing; deck is
  a template file (under a starting point or reference folder of the templates); deck not valid UTF-8; no
  decoration block; asset names (FR-NEW-023); assets leading outside (FR-NEW-025); files not found; write
  failure; in each case the exit status is 1 and the deck and its folder are unchanged; within one
  check, names are taken in the order of their first occurrence in the file text. A deck holding only one of
  the two markers of the decoration block, or the end marker before the begin marker, has no decoration block; `<folder 1>` is the absolute path of the deck's folder
  followed by `/assets`, `<folder 2>` the absolute path of the shipped catalogue, with no trailing `/`.
- **User visible text:** `error: <file> has no breathe:assets block in its <style>`;
  `error: asset <name> not found in: <folder 1>, <folder 2>`; `error: File not found: <file>`;
  `error: Refusing to modify a template: <file>`; `error: File is not valid UTF-8: <file>`;
  `error: Cannot write <file>: <operating system message>`. The shipped Breathe files are refreshed by the
  maintainer with `make sync-breathe-layouts`, never with `breathe-inline`.
- **Scenario:** SC-003 · **Priority:** Must

#### FR-NEW-009 [EARS-E]: Files next to the deck in the editor
> WHEN the editor page asks the server for a path that is not one of its own pages and names a file inside the
> folder of the open deck THE Editing context SHALL answer that file with its media type.

- **Business rules:** served types, suffix compared without regard to case, with their media type: `.png`
  image/png; `.jpg` `.jpeg` image/jpeg; `.gif` image/gif; `.webp` image/webp; `.avif` image/avif; `.bmp`
  image/bmp; `.ico` image/x-icon; `.svg` image/svg+xml; `.mp4` video/mp4; `.webm` video/webm; `.ogg`
  audio/ogg; `.mp3` audio/mpeg; `.wav` audio/wav; `.m4a` audio/mp4; `.woff` font/woff; `.woff2` font/woff2;
  `.ttf` font/ttf; `.otf` font/otf; `.css` text/css. A request path whose first segment is exactly `static`,
  `content`, `content-frame`, `status`, `export`, `requests`, `review`, `health` or `arch-layout`
  (case sensitive), or the path `/`, is never answered from the deck's folder; for such a path with no editor
  page, the answer is `404` `{"error": "Not found"}` even when the deck folder holds that file. Percent encoded
  names are decoded once. Answers are never cached by the browser, like the deck. The browser is told not to
  guess another type than the one stated, and an `.svg` served from the deck's folder never runs scripts. The
  query string is ignored when naming the file; a path ending with `/` names no file and is `Not found`.
- **Scenario:** SC-004 · **Priority:** Must

#### FR-NEW-010 [EARS-UB]: Nothing outside the deck's folder
> The Editing context SHALL NOT answer a file whose resolved location is outside the open deck's folder, whose
> path names a hidden file or folder (a segment starting with a dot, other than `.` and `..`), whose path holds
> a NUL character, whose type is not served, or that does not exist; it answers `404` with
> `{"error": "Not found"}`, the answer of an unknown path today.

- **Business rules:** after one percent decoding, `.` and `..` segments are resolved on the text of the path,
  before the file system is touched; a `..` that would climb above the deck's folder makes the path refused;
  then the resolved location follows links and must stay inside the folder, and the hidden segment rule also
  applies to the resolved location relative to the deck's folder; `<path as received>` is the request path
  before percent decoding, without the query string; a request refused by the request
  gate gets the gate's answer, before any file is looked at; with no deck open every such path is `Not found`;
  the server log line `Refused GET <path as received>: not served` is written at warning level for every GET
  this rule answers `Not found`, including the reserved first segments and paths with no served suffix; a
  request the gate refuses logs only the gate's line.
- **Scenario:** SC-004 · **Priority:** Must

#### FR-NEW-011 [EARS-E]: Breathe foreign classes
> WHEN `lint` checks a Breathe deck THE Deck checking context SHALL report L007 for every class starting
> `cds-`, `tag-`, `stat-`, `ei-`, or equal to `slide-inner`, `slide-header`, `slide-footer`, `slide-foot`,
> `slide-foot-logo`, `slide-foot-title`, `med-band`, `med-rule`, `med-head`, `med-foot`, `slide-body`,
> `slide-h1`, `slide-eyebrow`.

- **User visible text:** `class "med-rule" belongs to another charter than breathe`.
- **Scenario:** SC-005 · **Priority:** Must

#### FR-NEW-012 [EARS-E]: Breathe palette
> WHEN `lint` checks a Breathe deck THE Deck checking context SHALL warn L011 for every colour written in a
> slide's `style` outside `#0C7B70 #1D8379 #194757 #0E2B35 #E7F7FF #F3FDFF #A2EAF7 #83BBB5 #58A19A #CD8684
> #2F4C56 #587480 #9FC4CF #CFE3EA`, white, black and pure greys excepted.

- **User visible text:** `colour #123456 is not in the breathe palette`.
- **Scenario:** SC-005 · **Priority:** Must

#### FR-NEW-013 [EARS-E]: Breathe widths and sources
> WHEN `lint` checks a Breathe deck THE Deck checking context SHALL apply L008 to the children of the rows
> `.med-bleed`, `.med-figs-deep`, `.med-prio-row` and of the medical rows, and L009 to every slide other than
> `title` and `thanks`.

- **User visible text:** `child of .med-bleed has no w-* width class`; `slide has an image and no source line`.
- **Scenario:** SC-005 · **Priority:** Must

#### FR-NEW-014 [EARS-E]: Painted PPTX
> WHEN a Breathe deck is exported to PPTX and Chromium is available THE Export context SHALL paint each PPTX
> slide from the rendered HTML slide: the slide colour and background picture full bleed at the back, every
> coloured box and border as a shape, every icon and picture at its rendered box, every text as an editable
> text box at its rendered place with the browser's line breaks, face, size, weight, colour and letter spacing.

- **Business rules:** nothing from the flowed export stays on a painted slide; a picture shown with
  `object-fit: cover` is cropped like the browser; a remote picture or a vector picture is skipped with the
  existing warning; a linked picture that does not exist is skipped with the existing warning
  `Image introuvable, ignoree: <path>`; one CSS pixel is one point; the slide count equals the HTML slide count;
  each painted picture and coloured box has its left, top, width and height within 1 point of the rendered box
  of its HTML element; each text box starts within 1 point of the left and top of its rendered text and is at
  least as wide (it is widened so a line never wraps when the face is slightly wider).
- **Scenario:** SC-006 · **Priority:** Must

#### FR-NEW-015 [EARS-E]: Notes of a painted PPTX
> WHEN a Breathe deck is exported to PPTX THE Export context SHALL write each slide's speaker notes aside to the
> notes page of that slide with its text unchanged, and no notes page for a slide whose aside is empty or absent.

- **Scenario:** SC-006 · **Priority:** Must

#### FR-NEW-016 [EARS-O]: Degraded export
> IF Chromium is unavailable when a Breathe deck is exported to PPTX THEN THE Export context SHALL still write
> the PPTX, give each slide its colour and background picture full bleed with its texts and pictures flowed top
> to bottom over it, with no band, rule or footer of another charter, every text in the Breathe body face, and
> add the warning `Breathe deck exported without the rendered finish (<reason>). Install the browser with:
> make install-browser`.

- **Business rules:** `<reason>` is `Chromium is not installed`, `the render extra is not installed`,
  `Chromium could not start: <first line of the error>`, or, when Chromium starts but the render of any slide
  fails or exceeds 30 seconds, `the render failed: <first line of the error>` (the whole deck then takes the
  degraded export); the warning appears once per export; the command still ends with `Done. <N> slide(s)
  exportee(s).`; when the render extra is not installed the reason is `the render extra is not installed`,
  whether Chromium is installed or not; from the editor's export button the PPTX downloads with no warning shown, as for every export
  today.
- **Scenario:** SC-006 · **Priority:** Must

#### FR-NEW-017 [EARS-E]: Decoration catalogue
> WHEN the maintainer types `make breathe-assets` THE Template catalogue SHALL redraw the backgrounds of every
> preset and stage, the icons of every glyph in every variant, the logo disc and the sample pictures into the
> catalogue folder and print `<N> files written to <folder> (<K> KB)`.

- **Business rules:** presets and stages: cover s0; white, ice, deep, dark, side, split, image, compare s0 to
  s5; divider s1 to s4; track s0 and s5; thanks s5 (56 backgrounds); 16 glyphs (lungs, scope, microscope, coins,
  people, clock, map, cap, check, hospital, mail, pin, search, chart, doc, shield) in 6 variants (ring, solid,
  dark, done, now, todo) (96 icons); the logo disc `logo-disc.png`; the transparent partner logo
  `wiip-strong-logo-alpha.png`; the 4 samples `sample-clinical-b.jpg`, `sample-annotated-b.jpg`,
  `sample-photo-b.jpg`, `sample-video-b.jpg` (158 files written); `<K>` is the size in bytes of all the files
  written divided by 1024, rounded down; `<folder>` is printed as given; `ARGS=--list` prints one line per background
  `bg-<preset>-s<N>.png  class med-bg-<preset>-s<N>` and one per glyph
  `icon-<glyph>-<ring|solid|dark|done|now|todo>.png  class med-ico-<glyph>-<variant>` and writes nothing;
  `ARGS="--out <dir>"` writes elsewhere; `ARGS="--src <dir>"` reads the source pictures (watermark
  `filigrane-stethoscope-poumons.png`, botanical logo `logo-2026-botanical-transparent.png`, partner logo
  `wiip-strong-logo.png`) from another folder (default: the catalogue folder); the glyph line is exactly
  `icon-lungs-<ring|solid|dark|done|now|todo>.png  class med-ico-lungs-<variant>` for `lungs` (only the glyph name
  is replaced); with no `--out`, `<folder>` is the absolute path of the repository's catalogue folder with no
  trailing `/`; in `error: source picture <name> not found in <folder>`, `<folder>` is the `--src` value as given,
  else that absolute catalogue folder.
- **User visible text:** `error: source picture <name> not found in <folder>` (exit 1, checked before any file
  is written).
- **Scenario:** SC-007 · **Priority:** Should

#### FR-NEW-018 [EARS-U]: Skill topic
> The Agent guidance context SHALL offer the topic `breathe`, indexed in the core as `breathe: Rules for Breathe
> slides: layouts, airway stages, icons, sizing, notes, embedding, PPTX export. Load: mcp-htmleditor skill
> --type breathe`, and the core SHALL name the 9 template keys.

- **Business rules:** the topic fits the topic size budget; it names the commands of SC-001, SC-003, SC-005 and
  SC-006 exactly; `breathe` is indexed right after `medical-sources`.
- **Scenario:** SC-008 · **Priority:** Must

#### FR-NEW-019 [EARS-U]: Medical decks unchanged
> The Editor SHALL give a deck declaring `data-doc-template="medical"` the same PPTX slides and the same picker
> set as before this increment, and the same lint problems except the L006 problem `template text left: "Title
> of the presentation"` of FR-MOD-003, whatever Breathe classes or decoration block it holds.

- **Scenario:** SC-009 · **Priority:** Must

#### FR-NEW-020 [EARS-E]: Switching an existing deck
> WHEN the author changes the declaration of a deck built from the Breathe template from `medical` to `breathe`
> THE Editor SHALL treat it as Breathe with no other edit.

- **Business rules:** a copy of the WCBIP 2026 deck switched this way gets 0 lint errors; the declaration is
  compared case sensitively (`Breathe` is not `breathe`).
- **Scenario:** SC-009 · **Priority:** Must

#### FR-NEW-021 [EARS-U]: Fullscreen, pointer and presenter in Breathe files
> The Template catalogue SHALL ship the Breathe starting point and reference deck with the fullscreen support,
> the pointer and the presenter every presentation template carries.

- **Scenario:** SC-001, SC-002 · **Priority:** Must

#### FR-NEW-022 [EARS-UB]: Same painted export from every surface
> The Export context SHALL NOT give a different PPTX for the same Breathe deck depending on whether the export
> comes from the command line, the agent tool or the editor's export button.

- **Scenario:** SC-006 · **Priority:** Must

#### FR-NEW-023 [EARS-O]: Asset names are plain file names
> IF a `data-asset` value, or the text after `med-bg-` or `med-ico-` in a class used by a slide, is empty,
> starts with `.`, or holds a character other than ASCII letters, digits, `-`, `_` and `.`, THEN THE Template
> catalogue SHALL leave the deck and its folder unchanged, print `error: asset name <value> is not a plain file
> name` and exit with status 1, before any file is read or copied.

- **Scenario:** SC-003 · **Priority:** Must

#### FR-NEW-025 [EARS-O]: Assets stay in the deck's folder
> IF a file needed by `breathe-inline`, or the place it is copied to in link mode, lies in the deck's `assets` folder and,
> after following links, resolves outside that folder, THEN THE Template catalogue SHALL leave the deck and its
> folder unchanged, print `error: asset <name> leads outside <folder 1>` and exit with status 1, before any file
> is read or copied.

- **Scenario:** SC-003 · **Priority:** Must

#### FR-NEW-024 [EARS-U]: Files the reference deck uses are shipped
> The Template catalogue SHALL ship, besides the 158 generated files of FR-NEW-017, the files
> `collage-sample-b.jpg`, `wiip-strong-logo.png`, `filigrane-stethoscope-poumons.png` and
> `logo-2026-botanical-transparent.png`, so that `breathe-inline` on the reference deck finds every name it uses.

- **Scenario:** SC-003 · **Priority:** Must

### 6.2 Modified

#### FR-MOD-001 [EARS-E]: Nine template keys (modifies SPEC-0007/FR-NEW-015)
> WHEN an agent calls `list_templates`, `new_file` or `export` THE Editor SHALL give the results of the command
> line `templates`, `new` and `export`, over the 9 keys of FR-NEW-001.

- **Before:** 8 keys; `Unknown template "x". Valid templates: ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`.
- **After:** `Unknown template "x". Valid templates: ei, carbon, medical, breathe, doc, doc-perso, doc-ei, mail, website`.
- **Reason:** FR-NEW-001.

#### FR-MOD-002 [EARS-E]: Charter rules for four slide charters (modifies SPEC-0007/FR-NEW-014)
> WHEN `lint` runs on a presentation THE Editor SHALL apply L007 to L011 to the Carbon, Euro-Information,
> medical and Breathe charters, with the Breathe tables of FR-NEW-011 to FR-NEW-013.

- **Before:** L008 and L009 for medical only; three palettes.
- **After:** also Breathe; the medical, Carbon and Euro-Information tables unchanged.
- **Reason:** FR-NEW-011 to FR-NEW-013.

#### FR-MOD-003 [EARS-E]: English placeholder (modifies SPEC-0007/FR-NEW-013, L006)
> WHEN `lint` runs on a presentation THE Editor SHALL report L006 for the text `Title of the presentation` left
> on a slide, in addition to the texts of SPEC-0007.

- **Before:** French placeholders only.
- **After:** the three texts of SPEC-0007 plus `Title of the presentation`, for every charter (the only lint
  change a medical, Carbon or Euro-Information deck can see, FR-NEW-019).
- **Business rules:** `Title of the presentation` is checked after the texts of SPEC-0007.
- **Reason:** FR-NEW-002 (an English starting point needs an English placeholder).

### 6.3 Removed

None.

## 7. Non functional requirements (user observable)

### 7.1 Performance
- NFR-001: a painted export of the 23 slide reference deck completes within 60 seconds, measured by the test on
  the machine running the suite with Chromium installed.
- NFR-002: a picture request to the editor server is answered within the existing per request bounds.

### 7.2 Security and access
- NFR-003: the server reads no file outside the open deck's folder through any request (FR-NEW-010); the request
  gate of SPEC-0005 and SPEC-0013 applies before any file access.

### 7.3 Privacy and compliance
- NFR-004: the shipped sample pictures show no patient data (they are drawn placeholders).

### 7.4 Usability and accessibility
- NFR-005: the PPTX text stays editable (no slide is a single picture); faces are Georgia and Trebuchet MS,
  present on Windows and macOS.

### 7.5 Reliability
- NFR-006: an export with Chromium unavailable never fails because of it (FR-NEW-016).
- NFR-007: a refused embedding leaves the deck byte for byte unchanged (FR-NEW-008).

### 7.6 Operability
- NFR-008: the export and embedding results are printed on one line each; failures say what to install or which
  file is missing.

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty states | deck with no slide using a decoration class | embedding writes an empty block, prints `0 background and icon classes` | E2E-013 |
| Empty states | slide with an empty notes aside | no notes page | E2E-030 |
| Empty states | no deck open, picture path requested | `Not found` | E2E-024 |
| Boundary values | first and last of the 23 reference slides | painted, counted | E2E-027 |
| Boundary values | stage s0 and s5 classes | found in the catalogue | E2E-012 |
| Concurrent actions | embedding while the editor serves the deck | the editor reloads the new file like any write | not applicable: covered by the existing reload on file change |
| Slow or lost connectivity | not applicable: local tool, no network | n/a | n/a |
| Access states | request from an untrusted host or origin for a deck picture | gate refusal, file not read | E2E-SEC-006 |
| Data variations | picture name with a space, percent encoded | served | E2E-022 |
| Data variations | file name with accents in the deck folder | served | E2E-022 |
| Data variations | slide text with accents and `&` | painted with the same characters | E2E-028 |
| Navigation | relative path with `..` that stays inside the folder | served | E2E-023 |
| Partial operations | embedding fails on the third picture | deck unchanged | E2E-016 |
| Dependency failures | Chromium missing | degraded export with warning | E2E-032 |
| Dependency failures | render extra missing | degraded export, its reason | E2E-033 |
| Ordering and timing | `breathe-inline` run twice | identical file | E2E-014 |
| Exhaustion | not applicable: no quota or limit | n/a | n/a |

## 9. Acceptance tests (the contract)

> Behavioral and technology agnostic. /sdlc-design maps each test to a driver.

### 9.0 Fixtures

- **REF**: the Breathe reference deck as shipped.
- **NEW**: a deck created by `mcp-htmleditor new breathe talk.html` in an empty folder.
- **WCBIP**: a copy, in a temporary folder, of the WCBIP 2026 deck (14 slides, declaring `medical`) read from
  `~/projects/lamya/presentations/WABIP_2026-12_Melbourne/deck/wcbip2026-v1.html`; the tests using it are
  skipped when the file is absent (constraint 3.3).
- **REF-MED**: a copy of REF whose declaration is `medical` and whose styles lack `--breathe-ice` (the state of a
  deck built from the source template before this increment).
- **LEGACY**: a 3 slide deck declaring `data-doc-template="medical"`, with the medical colour token, Breathe
  classes (`med-bg-split-s1`, `med-ico-scope-ring`) and a decoration block; its second slide holds an element of
  class `cds-tile`.
- **SECRET**: a file `secret.txt` holding `TOP-SECRET-42` in the parent folder of the served deck's folder.
- **SECRET-PNG**: a file `secret.png` holding `TOP-SECRET-42` in the parent folder of the served deck's folder (a
  served type: only containment can refuse it).

### 9.1 Summary

| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | journey | SC-001 | FR-NEW-001, FR-MOD-001 | Critical |
| E2E-002 | New | failure | SC-001 | FR-MOD-001, FR-NEW-001 | High |
| E2E-003 | New | failure | SC-001 | FR-NEW-002 | High |
| E2E-004 | New | requirement | SC-001 | FR-NEW-002, FR-MOD-003 | Critical |
| E2E-005 | New | side effect | SC-001 | FR-NEW-002, FR-NEW-021 | High |
| E2E-006 | New | edge | SC-001 | FR-NEW-003 | High |
| E2E-007 | New | requirement | SC-002 | FR-NEW-004, FR-NEW-021 | Critical |
| E2E-008 | New | requirement | SC-002 | FR-NEW-005 | High |
| E2E-009 | New | failure | SC-002 | FR-NEW-005 | Medium |
| E2E-010 | New | edge | SC-002 | FR-NEW-005 | Medium |
| E2E-011 | New | journey | SC-003 | FR-NEW-006, NFR-008 | Critical |
| E2E-012 | New | edge | SC-003 | FR-NEW-006 | Medium |
| E2E-013 | New | edge | SC-003 | FR-NEW-006 | Low |
| E2E-014 | New | idempotency | SC-003 | FR-NEW-006 | Medium |
| E2E-015 | New | failure | SC-003 | FR-NEW-008, NFR-007 | High |
| E2E-016 | New | failure | SC-003 | FR-NEW-008 | High |
| E2E-017 | New | failure | SC-003 | FR-NEW-008, NFR-008 | Medium |
| E2E-018 | New | journey | SC-003 | FR-NEW-007 | High |
| E2E-019 | New | side effect | SC-003 | FR-NEW-007 | High |
| E2E-020 | New | state transition | SC-003 | FR-NEW-006, FR-NEW-007 | Medium |
| E2E-021 | New | journey | SC-004 | FR-NEW-009, NFR-002 | Critical |
| E2E-022 | New | edge | SC-004 | FR-NEW-009 | Medium |
| E2E-023 | New | edge | SC-004 | FR-NEW-009 | Medium |
| E2E-024 | New | failure | SC-004 | FR-NEW-010 | High |
| E2E-025 | New | failure | SC-004 | FR-NEW-009 | Medium |
| E2E-026 | New | journey | SC-006 | FR-NEW-014, FR-NEW-022, NFR-005 | Critical |
| E2E-027 | New | requirement | SC-006 | FR-NEW-014, NFR-001, FR-NEW-004, NFR-005 | Critical |
| E2E-028 | New | edge | SC-006 | FR-NEW-014 | Medium |
| E2E-029 | New | requirement | SC-006 | FR-NEW-015 | High |
| E2E-030 | New | edge | SC-006 | FR-NEW-015 | Medium |
| E2E-031 | New | failure | SC-006 | FR-NEW-014 | Medium |
| E2E-032 | New | failure | SC-006 | FR-NEW-016, NFR-008 | High |
| E2E-033 | New | failure | SC-006 | FR-NEW-016, NFR-006 | Medium |
| E2E-034 | New | requirement | SC-005 | FR-NEW-011, FR-MOD-002 | High |
| E2E-035 | New | failure | SC-005 | FR-NEW-012 | Medium |
| E2E-036 | New | failure | SC-005 | FR-NEW-013, FR-MOD-002 | Medium |
| E2E-037 | New | edge | SC-005 | FR-NEW-011, FR-NEW-012 | Medium |
| E2E-038 | New | requirement | SC-007 | FR-NEW-017, NFR-004 | Medium |
| E2E-039 | New | edge | SC-007 | FR-NEW-017 | Low |
| E2E-040 | New | failure | SC-007 | FR-NEW-017 | Low |
| E2E-041 | New | requirement | SC-008 | FR-NEW-018, FR-NEW-001, FR-MOD-001 | High |
| E2E-042 | New | failure | SC-008 | FR-NEW-018 | Medium |
| E2E-043 | New | edge | SC-008 | FR-NEW-018 | Low |
| E2E-044 | New | requirement | SC-009 | FR-NEW-019 | Critical |
| E2E-045 | New | failure | SC-009 | FR-NEW-019, FR-NEW-003 | High |
| E2E-046 | New | state transition | SC-009 | FR-NEW-020, FR-NEW-015 | Critical |
| E2E-047 | New | cross scenario | SC-002 | FR-NEW-021 | High |
| E2E-048 | New | failure | SC-005 | FR-MOD-002 | Medium |
| E2E-049 | New | failure | SC-001 | FR-MOD-003 | Medium |
| E2E-050 | New | failure | SC-006 | FR-NEW-022 | Medium |
| E2E-051 | New | failure | SC-002 | FR-NEW-005 | Medium |
| E2E-052 | New | failure | SC-002 | FR-NEW-005 | Medium |
| E2E-053 | New | failure | SC-002 | FR-NEW-005 | Low |
| E2E-054 | New | failure | SC-007 | FR-NEW-017 | Low |
| E2E-055 | New | failure | SC-008 | FR-NEW-018 | Low |
| E2E-056 | New | failure | SC-009 | FR-NEW-003, FR-NEW-020 | Medium |
| E2E-057 | New | failure | SC-009 | FR-NEW-019, FR-NEW-020 | High |
| E2E-058 | New | failure | SC-005 | FR-NEW-011 | Medium |
| E2E-059 | New | failure | SC-005 | FR-NEW-012 | Medium |
| E2E-060 | New | failure | SC-005 | FR-NEW-013 | Medium |
| E2E-061 | New | edge | SC-005 | FR-NEW-013 | Medium |
| E2E-062 | New | failure | SC-006 | FR-NEW-016, NFR-006 | Medium |
| E2E-063 | New | requirement | SC-003 | FR-NEW-024, FR-NEW-004 | High |
| E2E-064 | New | requirement | SC-003 | FR-NEW-024 | Medium |
| E2E-065 | New | side effect | SC-003 | FR-NEW-024 | Medium |
| E2E-066 | New | failure | SC-006 | FR-NEW-022 | Medium |
| E2E-067 | New | failure | SC-001 | FR-MOD-001 | Medium |
| E2E-068 | New | requirement | SC-001 | FR-MOD-001 | Medium |
| E2E-069 | New | edge | SC-003 | FR-NEW-025 | Medium |
| E2E-070 | New | failure | SC-005 | FR-MOD-003 | Medium |
| E2E-071 | New | failure | SC-004 | FR-NEW-009 | Medium |
| E2E-072 | New | side effect | SC-003 | FR-NEW-006 | Low |
| E2E-073 | New | failure | SC-009 | FR-NEW-003 | Medium |
| E2E-SEC-001 | New | security | SC-004 | FR-NEW-010, NFR-003 | Critical |
| E2E-SEC-002 | New | security | SC-004 | FR-NEW-010 | Critical |
| E2E-SEC-003 | New | security | SC-004 | FR-NEW-010 | Critical |
| E2E-SEC-004 | New | security | SC-004 | FR-NEW-010 | High |
| E2E-SEC-005 | New | security | SC-004 | FR-NEW-010 | High |
| E2E-SEC-006 | New | security | SC-004 | FR-NEW-010, NFR-003 | High |
| E2E-SEC-007 | New | security | SC-003 | FR-NEW-023 | Critical |
| E2E-SEC-008 | New | security | SC-003 | FR-NEW-023 | Critical |
| E2E-SEC-009 | New | security | SC-003 | FR-NEW-023 | High |
| E2E-SEC-010 | New | security | SC-004 | FR-NEW-009, NFR-003 | High |
| E2E-SEC-011 | New | security | SC-003 | FR-NEW-025 | Critical |
| E2E-SEC-012 | New | security | SC-003 | FR-NEW-025 | High |

Coverage: happy 17 (5 journey, 12 requirement), failure 35, side effect 4, edge 13, state transition 2,
idempotency 1, cross scenario 1, security 12 (85 tests). Happy to failure ratio 1:2.8 (35 failure and 12
security against 17 happy).

### 9.2 New tests

#### E2E-001: The catalogue lists Breathe
- **Category:** journey · **Scenario:** SC-001 · **Requirements:** FR-NEW-001, FR-MOD-001
- **Given** the editor as delivered **When** the author types `mcp-htmleditor templates` **Then** the keys
  appear in the order `ei, carbon, medical, breathe, doc, doc-perso, doc-ei, mail, website` **And** the line of
  `breathe` reads `Breathe congress presentation: airway story line, ice and navy panels, Georgia titles, 1 cover
  slide` **And** the agent tool `list_templates` returns the same 9 pairs in the same order.

#### E2E-002: Unknown key names the 9 keys
- **Category:** failure · **Requirements:** FR-MOD-001, FR-NEW-001
- **When** the author types `mcp-htmleditor new breath talk.html` **Then** the error line is `error: Unknown
  template "breath". Valid templates: ei, carbon, medical, breathe, doc, doc-perso, doc-ei, mail, website`, exit
  status 1 **And** `talk.html` does not exist.

#### E2E-003: Existing target refused
- **Category:** failure · **Requirements:** FR-NEW-002
- **Given** `talk.html` holding `keep me` **When** the author types `mcp-htmleditor new breathe talk.html`
  **Then** `error: File already exists: talk.html`, exit 1 **And** the file still holds `keep me`.

#### E2E-004: New Breathe deck content and its single lint error
- **Category:** requirement · **Requirements:** FR-NEW-002, FR-MOD-003
- **Given** an empty folder **When** the author types `mcp-htmleditor new breathe talk.html` then
  `mcp-htmleditor lint talk.html` **Then** the deck has exactly one slide `slide-0` of type `title`, declares
  `breathe`, holds `--breathe-ice` and `Title of the presentation` **And** lint prints exactly
  `error L006 slide-0 template text left: "Title of the presentation"` and `lint: FAIL (1 error, 0 warnings)`.

#### E2E-005: The new deck shows its decoration alone, presents and points
- **Category:** side effect · **Requirements:** FR-NEW-002, FR-NEW-021
- **Given** NEW, alone in its folder **When** it is opened from the file in Chromium **Then** the cover shows
  a background picture and the logo disc (every picture of the slide loaded, none missing) **And** F enters full
  screen, L shows the pointer, S opens the presenter **And** the render report of the deck gives no problem.

#### E2E-006: Declaration or marker
- **Category:** edge · **Requirements:** FR-NEW-003
- **Given** three one slide decks, each slide holding an element of class `cds-tile`: A declares `breathe` with
  no marker; B carries `--breathe-ice` and declares nothing; C carries both `--breathe-ice` and the medical token
  and declares `medical` **When** each is linted, exported and opened in the editor's picker **Then** A and B print
  `error L007 slide-0 class "cds-tile" belongs to another charter than breathe`, their PPTX is painted and the
  picker offers the 23 Breathe layouts **And** C prints the same line ending `than medical`, its PPTX has no full
  slide background picture and the picker offers the medical layouts.

#### E2E-007: Reference deck complete and clean
- **Category:** requirement · **Requirements:** FR-NEW-004, FR-NEW-021
- **Given** REF **When** linted and render checked **Then** 23 slides with the slide names of FR-NEW-004 in order,
  `lint: OK (0 errors, 0 warnings)`, `report: OK` **And** every slide holds a speaker notes aside.

#### E2E-008: Picker offers the Breathe layouts
- **Category:** requirement · **Requirements:** FR-NEW-005
- **Given** NEW open in the editor **When** the author opens the layout picker **Then** it lists 23 entries
  labelled with the FR-NEW-004 slide names in order **And** inserting `Key figures` adds a slide whose text equals the
  reference slide `Key figures`, and the deck then has 2 slides with counters `1` and `2`.

#### E2E-009: Picker of a medical deck unchanged
- **Category:** failure · **Requirements:** FR-NEW-005
- **Given** the medical starting point open in the editor **When** the picker opens **Then** it lists the 16
  medical layouts and no Breathe layout.

#### E2E-010: Picker set follows the reference deck
- **Category:** edge · **Requirements:** FR-NEW-005
- **Given** the reference deck title of slide 5 changed to `Key numbers` and the picker set not regenerated
  **When** the maintainer runs `make check-generated` **Then** it exits 1 and prints a line ending `; run: make
  sync-breathe-layouts` **And** after `make sync-breathe-layouts` it passes and the picker label reads `Key numbers`.

#### E2E-011: Embed inline
- **Category:** journey · **Requirements:** FR-NEW-006, NFR-008
- **Given** NEW with the reference slide `Key figures` added (classes `med-bg-split-s1`, `med-ico-scope-ring`
  among others) and `<img data-asset="sample-clinical-b.jpg" src="">` **When** the author types
  `mcp-htmleditor breathe-inline talk.html` **Then** the output reads `talk.html: <N> background and icon classes,
  <M> pictures embedded, <K> KB` with N equal to the number of distinct such classes on the slides and M the
  number of named pictures **And** opened in Chromium, every picture of both slides loads and the split slide
  shows its background.

#### E2E-012: Stage boundaries found
- **Category:** edge · **Requirements:** FR-NEW-006
- **Given** a deck using `med-bg-track-s0`, `med-bg-track-s5`, `med-bg-divider-s1`, `med-bg-divider-s4`
  **When** embedded **Then** 4 rules are written, each with a picture.

#### E2E-013: Nothing to embed
- **Category:** edge · **Requirements:** FR-NEW-006
- **Given** a Breathe deck whose only slide uses no decoration class and no named picture **When** embedded
  **Then** the output starts `talk.html: 0 background and icon classes, 0 pictures embedded` and the block is empty.

#### E2E-014: Embedding twice changes nothing
- **Category:** idempotency · **Requirements:** FR-NEW-006
- **Given** the deck of E2E-011 embedded once **When** embedded again **Then** the file is byte for byte the same.

#### E2E-015: No decoration block
- **Category:** failure · **Requirements:** FR-NEW-008, NFR-007
- **Given** the medical starting point copied to `med.html` **When** `mcp-htmleditor breathe-inline med.html`
  **Then** `error: med.html has no breathe:assets block in its <style>`, exit 1 **And** the file is unchanged.

#### E2E-016: Missing picture leaves the deck unchanged
- **Category:** failure · **Requirements:** FR-NEW-008, NFR-007
- **Given** NEW with three named pictures, the third `nowhere.jpg` existing in no folder **When** embedded
  **Then** `error: asset nowhere.jpg not found in: <deck folder>/assets, <catalogue folder>`, exit 1 **And** the
  file is byte for byte unchanged **And** no `assets` folder was created.

#### E2E-017: Missing deck file
- **Category:** failure · **Requirements:** FR-NEW-008, NFR-008
- **When** `mcp-htmleditor breathe-inline nothere.html` **Then** `error: File not found: nothere.html`, exit 1.

#### E2E-018: Link mode
- **Category:** journey · **Requirements:** FR-NEW-007
- **Given** the deck of E2E-011 before embedding, and `assets/photo.jpg` in its folder named by an `<img>`
  **When** `mcp-htmleditor breathe-inline talk.html --link` **Then** the output reads `talk.html: <N> background
  and icon classes, <M> pictures linked, <C> files copied to <deck folder>/assets, <K> KB` **And** the file holds
  no picture as text in its decoration block or its named pictures **And** opened from the file in Chromium every
  picture loads.

#### E2E-019: Link mode never overwrites
- **Category:** side effect · **Requirements:** FR-NEW-007
- **Given** the deck's `assets/icon-scope-ring.png` holding the bytes `custom` **When** linked **Then** that
  file still holds `custom` **And** C counts only the files copied.

#### E2E-020: Inline after link
- **Category:** state transition · **Requirements:** FR-NEW-006, FR-NEW-007
- **Given** the deck of E2E-018 **When** `breathe-inline talk.html` without `--link` **Then** the block and named
  pictures hold the pictures as text again **And** opened in Chromium after renaming its `assets` folder, every
  picture still loads.

#### E2E-021: The editor shows a linked picture
- **Category:** journey · **Requirements:** FR-NEW-009, NFR-002
- **Given** a deck `talk.html` with `<img src="assets/photo.png">` and that file next to it, served by
  `mcp-htmleditor serve talk.html` **When** the editor page shows the slide **Then** the picture is loaded (its
  natural width is the file's) **And** a request for `/assets/photo.png` answers the file's bytes with the media
  type `image/png` and the no cache header.

#### E2E-022: Encoded names
- **Category:** edge · **Requirements:** FR-NEW-009
- **Given** `assets/My Photo é.jpg` next to the deck **When** the editor asks `/assets/My%20Photo%20%C3%A9.jpg`
  **Then** the file's bytes come back with `image/jpeg` **And** `assets/IMG_01.JPG` asked as `/assets/IMG_01.JPG`
  comes back with `image/jpeg`.

#### E2E-023: Inner dot dot staying inside
- **Category:** edge · **Requirements:** FR-NEW-009
- **Given** `assets/a.png` next to the deck, and no folder `assets/sub` **When** asked `/assets/sub/../a.png`
  written as is **Then** the file's bytes come back.

#### E2E-024: Nothing open, wrong type, missing file
- **Category:** failure · **Requirements:** FR-NEW-010
- **Given** a deck with `notes.txt` and `script.js` next to it **When** asked `/notes.txt`, `/script.js` and
  `/missing.png` **Then** each answers `404` with `{"error": "Not found"}` **And** with no deck open,
  `/assets/photo.png` answers the same.

#### E2E-025: The editor's own pages win
- **Category:** failure · **Requirements:** FR-NEW-009
- **Given** a file `static/editor.js` in the deck's folder holding `DECK COPY` **When** asked `/static/editor.js`
  **Then** the editor's own script comes back, not `DECK COPY` **And** with `review/fig.png` in the deck folder,
  `/review/fig.png` answers `404` `{"error": "Not found"}`.

#### E2E-026: Painted export from the command line, the tool and the editor
- **Category:** journey · **Requirements:** FR-NEW-014, FR-NEW-022, NFR-005
- **Given** NEW with the `Key figures` slide added and embedded **When** exported with `mcp-htmleditor export
  pptx talk.html talk.pptx`, with the agent tool `export`, and with the editor's export **Then** each PPTX has 2
  slides **And** each slide's first shape is a picture covering the whole slide **And** the title of the
  reference slide, `The title states the message`, is held by editable text boxes in Georgia (lines joined by a
  space) **And** the three files have the same shapes, positions and texts.

#### E2E-027: Reference deck painted
- **Category:** requirement · **Requirements:** FR-NEW-014, NFR-001, FR-NEW-004, NFR-005
- **Given** REF **When** exported to PPTX **Then** within 60 seconds, 23 slides, each with a full slide
  background picture at the back, no slide made of a single picture, every visible text of each HTML slide
  present in a text box of the same slide, body texts in Trebuchet MS and titles in Georgia **And** for every
  picture of each HTML slide, a PPTX picture has left, top, width and height within 1 point of the picture's
  rendered box **And** the HTML and PPTX renders of every slide are kept as evidence pictures with the run.

#### E2E-028: Accents and ampersands
- **Category:** edge · **Requirements:** FR-NEW-014
- **Given** a Breathe slide title `Diagnostic précoce & accès` **When** exported **Then** a text box holds
  exactly `Diagnostic précoce & accès`.

#### E2E-029: Notes reach the notes pages
- **Category:** requirement · **Requirements:** FR-NEW-015
- **Given** a 2 slide Breathe deck whose first aside holds `Good morning.` then a blank line then `Second
  paragraph.` **When** exported **Then** slide 1's notes text equals the aside text **And** slide 2 (no aside) has
  no notes page.

#### E2E-030: Empty aside
- **Category:** edge · **Requirements:** FR-NEW-015
- **Given** a Breathe slide with an aside holding only spaces **When** exported **Then** that slide has no notes page.

#### E2E-031: Remote picture skipped
- **Category:** failure · **Requirements:** FR-NEW-014
- **Given** a Breathe slide with `<img src="https://example.org/x.png">` **When** exported **Then** the export
  completes, the slide has no picture for it **And** the warnings name the remote picture.

#### E2E-032: Degraded export without Chromium
- **Category:** failure · **Requirements:** FR-NEW-016, NFR-006, NFR-008
- **Given** NEW embedded, and Chromium not installed **When** exported **Then** the command ends with `Done. 1
  slide(s) exportee(s).` **And** exactly one warning reads `Breathe deck exported without the rendered finish
  (Chromium is not installed). Install the browser with: make install-browser` **And** the slide's first shape is
  a full slide picture.

#### E2E-033: Degraded export without the render extra
- **Category:** failure · **Requirements:** FR-NEW-016, NFR-006
- **Given** NEW and the render extra not installed **When** exported **Then** the warning reason reads
  `the render extra is not installed` and the PPTX is written.

#### E2E-034: Foreign classes on a Breathe slide
- **Category:** requirement · **Requirements:** FR-NEW-011, FR-MOD-002
- **Given** a Breathe slide holding `med-rule`, `cds-tile` and `slide-h1` **When** linted **Then** three errors:
  `class "med-rule" belongs to another charter than breathe`, the same for `cds-tile` and `slide-h1`, in order
  of first occurrence.

#### E2E-035: Colour outside the Breathe palette
- **Category:** failure · **Requirements:** FR-NEW-012
- **Given** a Breathe slide with `style="color:#EE5A02"` and another element `style="background:#0c7b70"`
  **When** linted **Then** one warning `colour #EE5A02 is not in the breathe palette` and none for `#0c7b70`.

#### E2E-036: Width and source on Breathe
- **Category:** failure · **Requirements:** FR-NEW-013, FR-MOD-002
- **Given** a Breathe content slide with a `.med-bleed` child lacking a width class and a picture with an empty
  source line **When** linted **Then** `child of .med-bleed has no w-* width class` and `slide has an image and
  no source line` **And** the same picture on a `title` slide gives no source error.

#### E2E-037: Greys, white and Breathe colours accepted
- **Category:** edge · **Requirements:** FR-NEW-011, FR-NEW-012
- **Given** a Breathe slide using `#FFFFFF`, `#333`, `#CD8684` and classes `med-bg-side-s4`, `med-ico-lungs-dark`
  **When** linted **Then** no L007 and no L011 problem.

#### E2E-038: Catalogue redrawn
- **Category:** requirement · **Requirements:** FR-NEW-017, NFR-004
- **Given** an empty folder `out` **When** the maintainer runs the generator with `--out out` **Then** it prints
  `<N> files written to out (<K> KB)` with N = 56 backgrounds + 96 icons + 1 logo disc + 1 transparent partner
  logo + 4 samples = 158 **And** `out/bg-cover-s0.png` is 1920 x 1080 and `out/icon-scope-now.png` is 176 x 176.

#### E2E-039: Catalogue listed only
- **Category:** edge · **Requirements:** FR-NEW-017
- **When** run with `--list` and `--out out` **Then** 56 background lines and 16 glyph lines print, the first
  `bg-cover-s0.png  class med-bg-cover-s0` **And** `out` stays empty.

#### E2E-040: Generator sources missing
- **Category:** failure · **Requirements:** FR-NEW-017
- **Given** a catalogue folder lacking the watermark source **When** the generator runs with `--src` pointing
  there **Then** it stops with `error: source picture filigrane-stethoscope-poumons.png not found in <folder>`,
  exit 1, before writing any file.

#### E2E-041: Skill topic and index
- **Category:** requirement · **Requirements:** FR-NEW-018, FR-NEW-001, FR-MOD-001
- **When** the agent types `mcp-htmleditor skill` **Then** the topics list holds the line of FR-NEW-018 and the
  core names `ei, carbon, medical, breathe, doc, doc-perso, doc-ei, mail, website` **And** `skill --type breathe`
  prints a text naming `mcp-htmleditor new breathe`, `mcp-htmleditor breathe-inline`, `--link`,
  `mcp-htmleditor lint`, `mcp-htmleditor export pptx` and `make install-browser`.

#### E2E-042: Unknown topic message lists breathe
- **Category:** failure · **Requirements:** FR-NEW-018
- **When** `mcp-htmleditor skill --type breath` **Then** the error lists the 16 topics including `breathe`, exit 2.

#### E2E-043: Topic within budget
- **Category:** edge · **Requirements:** FR-NEW-018
- **When** the maintainer runs `mcp-htmleditor skill-audit` **Then** it reports no problem and the `breathe`
  topic is under 8000 bytes.

#### E2E-044: Medical decks unchanged
- **Category:** requirement · **Requirements:** FR-NEW-019
- **Given** the ten recorded templates and LEGACY **When** exported and linted **Then** the ten fingerprints match
  the recorded ones **And** LEGACY is linted and exported as medical (its PPTX has the medical chrome and no full
  slide background picture; lint prints `error L007 slide-1 class "cds-tile" belongs to another charter than
  medical`).

#### E2E-045: Breathe marker on a medical declaration
- **Category:** failure · **Requirements:** FR-NEW-019, FR-NEW-003
- **Given** LEGACY with `--breathe-ice` added to its styles **When** linted, exported and opened in the picker
  **Then** it is medical in all three (lint prints `error L007 slide-1 class "cds-tile" belongs to another charter
  than medical`).

#### E2E-046: Switching the WCBIP deck
- **Category:** state transition · **Requirements:** FR-NEW-020, FR-NEW-015
- **Given** WCBIP **When** exported as is **Then** no slide's first shape is a full slide picture; **When** its declaration is changed to `breathe`
  and linted **Then** `lint: OK (0 errors, 0 warnings)` **And** its export is painted with 14 slides and 14
  notes pages **And** REF-MED (always present) is medical as is and, switched to `breathe`, gets
  `lint: OK (0 errors, 0 warnings)` and a painted export of 23 slides.

#### E2E-047: Templates guard covers Breathe
- **Category:** cross scenario · **Requirements:** FR-NEW-021
- **Given** the repository **When** the template guard runs **Then** the Breathe starting point and reference
  deck are among the presentation files and each carries the fullscreen markers, the pointer, the Pointeur
  control, the L key and the presenter.

#### E2E-048: Other charters keep their rules
- **Category:** failure · **Requirements:** FR-MOD-002
- **Given** a Carbon slide holding `med-bg-split-s1` **When** linted **Then** `class "med-bg-split-s1" belongs to
  another charter than carbon` **And** a medical slide with a `.med-bleed` child lacking a width gives no L008.

#### E2E-049: English placeholder in any charter
- **Category:** failure · **Requirements:** FR-MOD-003
- **Given** a Carbon deck of 2 slides whose second title is `Title of the presentation` **When** linted **Then**
  `error L006 slide-1 template text left: "Title of the presentation"`.

#### E2E-050: Editor export equals command line export
- **Category:** failure · **Requirements:** FR-NEW-022
- **Given** the deck of E2E-026 served by the editor with Chromium unavailable to both **When** exported from the
  editor and from the command line **Then** both carry the same degraded slides (shape count and texts equal).

#### E2E-051: Picker of a Carbon deck unchanged
- **Category:** failure · **Requirements:** FR-NEW-005
- **Given** the Carbon starting point open in the editor **When** the picker opens **Then** it lists the same 5
  entries as before this increment **And** none is labelled `Cover`, `Key figures, deep` or `Thanks, message`.

#### E2E-052: Inserted layout before embedding
- **Category:** failure · **Requirements:** FR-NEW-005 (EXC-002a)
- **Given** NEW open in the editor **When** the author inserts `Pathway` **Then** the deck has 2 slides **And** the
  new slide's background picture is not loaded **And** after `mcp-htmleditor breathe-inline talk.html` and the
  editor reload, it is loaded.

#### E2E-053: Picker cancelled
- **Category:** failure · **Requirements:** FR-NEW-005
- **Given** NEW open with the picker shown **When** the author presses the picker's cancel button **Then** the deck
  still has 1 slide and the file is byte for byte unchanged.

#### E2E-054: Logo source missing
- **Category:** failure · **Requirements:** FR-NEW-017
- **Given** a source folder lacking `logo-2026-botanical-transparent.png` **When** the generator runs with `--src`
  pointing there and `--out out` **Then** `error: source picture logo-2026-botanical-transparent.png not found in
  <folder>`, exit 1 **And** `out` does not exist.

#### E2E-055: Topic and all together
- **Category:** failure · **Requirements:** FR-NEW-018
- **When** `mcp-htmleditor skill --type breathe --all` **Then** stderr reads `Error: --type and --all cannot be
  used together`, exit 2, stdout empty.

#### E2E-056: Declaration case
- **Category:** failure · **Requirements:** FR-NEW-003, FR-NEW-020
- **Given** LEGACY with its declaration changed to `Breathe` (capital B) **When** linted and exported **Then** it is
  medical in both (lint prints `error L007 slide-1 class "cds-tile" belongs to another charter than medical`, the
  PPTX has no full slide background picture).

#### E2E-057: Back to medical
- **Category:** failure · **Requirements:** FR-NEW-019, FR-NEW-020
- **Given** WCBIP switched to `breathe`, then back to `medical` **When** linted and exported **Then** the lint
  output and the PPTX slide fingerprints equal those of WCBIP as is.

#### E2E-058: Breathe classes are not foreign
- **Category:** failure · **Requirements:** FR-NEW-011
- **Given** a Breathe slide holding `med-band`, `ei-logo`, `stat-big` and `med-bg-cover-s0` **When** linted
  **Then** exactly three L007 errors, for `med-band`, `ei-logo` and `stat-big` in that order, and none for
  `med-bg-cover-s0`.

#### E2E-059: Short hex and url text
- **Category:** failure · **Requirements:** FR-NEW-012
- **Given** a Breathe slide with `style="color:#0c7"` and another with `style="background:url(#EE5A02)"` **When**
  linted **Then** one warning `colour #0c7 is not in the breathe palette` and none for the `url()` text.

#### E2E-060: Breathe rows
- **Category:** failure · **Requirements:** FR-NEW-013
- **Given** a Breathe slide with a `.med-figs-deep` child and a `.med-prio-row` child, neither with a width class,
  and a third row whose children all carry `w-50` **When** linted **Then** exactly `child of .med-figs-deep has no
  w-* width class` and `child of .med-prio-row has no w-* width class`.

#### E2E-061: Source rule by slide type
- **Category:** edge · **Requirements:** FR-NEW-013
- **Given** a Breathe `thanks` slide with a picture and no source, and a `section` slide with a picture and a
  `.med-source` holding only spaces **When** linted **Then** exactly one `slide has an image and no source line`,
  on the `section` slide.

#### E2E-062: Render failure takes the degraded export
- **Category:** failure · **Requirements:** FR-NEW-016, NFR-006
- **Given** NEW with the `Key figures` slide added, and the render of the second slide failing **When** exported
  **Then** `Done. 2 slide(s) exportee(s).` **And** exactly one warning `Breathe deck exported without the rendered
  finish (the render failed: <first line>). Install the browser with: make install-browser` **And** both slides
  have their full slide background picture.

#### E2E-063: Reference deck embeds from the shipped catalogue alone
- **Category:** requirement · **Requirements:** FR-NEW-024, FR-NEW-004
- **Given** a copy of REF alone in an empty folder **When** `mcp-htmleditor breathe-inline ref.html` **Then** exit 0
  **And** the `<M>` of the output equals the number of `data-asset` pictures of REF.

#### E2E-064: The four shipped extra files embed
- **Category:** requirement · **Requirements:** FR-NEW-024
- **Given** a Breathe deck alone in an empty folder naming `collage-sample-b.jpg`, `wiip-strong-logo.png`,
  `filigrane-stethoscope-poumons.png` and `logo-2026-botanical-transparent.png` in four pictures **When**
  `breathe-inline` **Then** exit 0, the output says `4 pictures embedded` **And** each loads in Chromium.

#### E2E-065: The four shipped extra files copy
- **Category:** side effect · **Requirements:** FR-NEW-024
- **Given** the deck of E2E-064 **When** `breathe-inline --link` **Then** the output says `4 files copied` **And**
  the 4 copies are byte identical to the shipped files.

#### E2E-066: Degraded export equal on every surface
- **Category:** failure · **Requirements:** FR-NEW-022
- **Given** the deck of E2E-062 (the render of slide 2 fails) **When** it is exported from the agent tool `export`
  and from the editor **Then** both PPTX equal the command line PPTX in shape count, texts and positions.

#### E2E-067: Agent tool with an unknown key
- **Category:** failure · **Requirements:** FR-MOD-001
- **When** the agent tool `new_file` is called with `breath` **Then** it fails with `Unknown template "breath".
  Valid templates: ei, carbon, medical, breathe, doc, doc-perso, doc-ei, mail, website` **And** no file is written.

#### E2E-068: Agent tool creates a Breathe deck
- **Category:** requirement · **Requirements:** FR-MOD-001
- **When** the agent tool `new_file` is called with `breathe` **Then** it writes the same bytes as
  `mcp-htmleditor new breathe`.

#### E2E-069: Link staying inside the assets folder
- **Category:** edge · **Requirements:** FR-NEW-025
- **Given** `deck/assets/photo.png` a symbolic link to `deck/assets/real/photo.png` (a PNG), and `deck/talk.html`
  (Breathe, decoration block, no decoration class) holding `<img data-asset="photo.png" src="">` **When**
  `mcp-htmleditor breathe-inline deck/talk.html` **Then** exit 0 and the output starts `deck/talk.html: 0
  background and icon classes, 1 pictures embedded,` **And** the picture loads in Chromium.

#### E2E-070: French and English placeholders together
- **Category:** failure · **Requirements:** FR-MOD-003
- **Given** a medical deck of 2 slides whose second slide holds `Titre de la présentation` and `Title of the
  presentation` **When** linted **Then** exactly these two lines, in this order: `error L006 slide-1 template
  text left: "Titre de la présentation"`, `error L006 slide-1 template text left: "Title of the presentation"`.

#### E2E-071: Served file forbids type guessing
- **Category:** failure · **Requirements:** FR-NEW-009
- **Given** `assets/photo.png` next to the deck holding the bytes `<script>alert(1)</script>` **When** the editor
  asks `/assets/photo.png` **Then** the answer states `image/png` **And** tells the browser not to guess another
  type **And** opened at the editor's address, no script runs.

#### E2E-072: History of an embedding
- **Category:** side effect · **Requirements:** FR-NEW-006
- **Given** NEW **When** `breathe-inline talk.html` twice then `mcp-htmleditor history talk.html` **Then** exactly
  one entry has the reason `breathe-inline`.

#### E2E-073: Marker in a comment
- **Category:** failure · **Requirements:** FR-NEW-003
- **Given** LEGACY with its declaration removed, `--med-teal` kept, and `/* --breathe-ice */` as the only marker
  **When** linted, exported and opened in the picker **Then** medical in all three.

### 9.3 Exploit tests

Each request is sent as written (no client normalisation) to a server whose open deck sits in folder `deck/`,
with SECRET in its parent folder. The absence of effect is read on another channel: the bytes of the answer
are searched for `TOP-SECRET-42`, and the server log holds `Refused GET <path>: not served`. Today every such
request already answers 404; each exploit test runs in the same session as a served picture (E2E-021) that must
be green, so the 404 is evidence of containment and not of an absent route.

#### E2E-SEC-001: Dot dot climbing out
- **Covers:** class sweep occurrence #2 (Section 14.2)
- **Red before the fix because:** a join that checks only the served type answers `200` with `TOP-SECRET-42`.
- **Given** SECRET-PNG **When** the request line is `GET /../secret.png HTTP/1.1` **Then** `404`
  `{"error": "Not found"}` **And** the answer bytes do not contain `TOP-SECRET-42` **And** the log holds
  `Refused GET /../secret.png: not served`.

#### E2E-SEC-002: Encoded dot dot
- **Covers:** occurrence #2
- **Red before the fix because:** decoding after a check on the raw path, with a served suffix, answers the secret.
- **Given** SECRET-PNG **When** `GET /%2e%2e/secret.png` and `GET /assets/..%2f..%2fsecret.png` **Then** both
  `404` **And** neither answer contains `TOP-SECRET-42`.

#### E2E-SEC-003: Link escaping the folder
- **Covers:** occurrence #2
- **Red before the fix because:** a containment check on the unresolved path follows the link and answers the secret.
- **Given** SECRET-PNG and `deck/assets/leak.png` a symbolic link to `../../secret.png` **When** `GET /assets/leak.png`
  **Then** `404` **And** no `TOP-SECRET-42`.

#### E2E-SEC-004: Absolute path
- **Covers:** occurrence #2
- **Red before the fix because:** the decoded path `//<parent>/secret.png` is absolute, so joining it replaces the
  folder and the `.png` suffix passes the type check.
- **Given** SECRET-PNG and `<P>` the absolute path of its folder with every `/` written `%2F` **When**
  `GET /%2F<P>%2Fsecret.png` **Then** `404` `{"error": "Not found"}` **And** no `TOP-SECRET-42` in the answer
  **And** the log holds one `not served` line.

#### E2E-SEC-005: Hidden file and NUL byte
- **Covers:** occurrence #2
- **Red before the fix because:** a type check alone serves `.secret.png`; a served suffix after a NUL reaches
  the file system, which raises `embedded null byte`, answered `500`.
- **Given** `deck/.secret.png` holding `TOP-SECRET-42` **When** `GET /.secret.png`, `GET /assets/photo.png%00.png`
  and `GET /secret.txt%00.png` **Then** each answers `404` `{"error": "Not found"}` (not `500`) **And** no answer
  contains `TOP-SECRET-42` **And** the log holds three `not served` lines.

#### E2E-SEC-006: Untrusted host
- **Covers:** occurrence #2, gate order
- **Red before the fix because:** a file route placed before the gate answers any host.
- **Given** `deck/assets/photo.png` **When** `GET /assets/photo.png` with `Host: evil.example` **Then** the gate
  refuses (`403`) **And** the answer bytes do not contain the picture's bytes.

#### E2E-SEC-007: Embedded name climbing out
- **Covers:** occurrence #3
- **Red before the fix because:** joining the assets folder with the name reads `../secret.png`.
- **Given** `secret.png` holding `TOP-SECRET-42` in the parent folder of `deck/`, and `deck/talk.html` (a Breathe
  deck with a decoration block) holding `<img data-asset="../secret.png" src="">` **When** `mcp-htmleditor
  breathe-inline deck/talk.html` **Then** `error: asset name ../secret.png is not a plain file name`, exit 1
  **And** `deck/talk.html` is byte for byte unchanged and does not contain `VE9QLVNFQ1JFVC00Mg`.

#### E2E-SEC-008: Absolute name in link mode
- **Covers:** occurrence #3
- **Red before the fix because:** joining a folder with an absolute name gives that name, so the file is found
  and copied into `deck/assets`.
- **Given** `<img data-asset="<absolute path of secret.png>" src="">` **When** `breathe-inline deck/talk.html
  --link` **Then** the same error, exit 1 **And** the listing of `deck/` is unchanged (no `assets` folder) **And**
  the deck is byte for byte unchanged.

#### E2E-SEC-009: Class suffix climbing out
- **Covers:** occurrence #3
- **Red before the fix because:** `deck/assets/bg-x/../../../secret.png` passes through the existing folder
  `bg-x` and reaches the parent's `secret.png`.
- **Given** an empty folder `deck/assets/bg-x/` and a slide element with class `med-bg-x/../../../secret`
  **When** `breathe-inline deck/talk.html` **Then** `error: asset name x/../../../secret is not a plain file
  name`, exit 1 **And** the deck is unchanged and does not contain `VE9QLVNFQ1JFVC00Mg`.

#### E2E-SEC-010: Scripted SVG
- **Covers:** occurrence #2
- **Red before the fix because:** a same origin SVG document runs its script, and the gate accepts its same
  origin requests.
- **Given** `deck/assets/x.svg` holding a script that marks the document as run and queues the request `PWNED`
  in the editor **When** the editor's browser opens `/assets/x.svg` at the editor's address **Then** the SVG
  document is not marked as run **And** the editor's request list holds no `PWNED` request **And**
  `deck/talk.html` is byte for byte unchanged.

#### E2E-SEC-011: Linked asset leaving the folder
- **Covers:** occurrence #3
- **Red before the fix because:** the file check follows the link and embeds the parent's file.
- **Given** `secret.png` holding `TOP-SECRET-42` in the parent folder of `deck/`, `deck/assets/photo.png` a
  symbolic link to `../../secret.png`, and `deck/talk.html` (Breathe, with a decoration block) holding
  `<img data-asset="photo.png" src="">` **When** `mcp-htmleditor breathe-inline deck/talk.html` **Then** `error:
  asset photo.png leads outside <absolute path of deck>/assets`, exit 1 **And** `deck/talk.html` is byte for byte
  unchanged and does not contain `VE9QLVNFQ1JFVC00Mg`.

#### E2E-SEC-012: Dangling link in link mode
- **Covers:** occurrence #3
- **Red before the fix because:** "not already present" is true for a dangling link, so the copy creates the
  target outside.
- **Given** `deck/assets/icon-scope-ring.png` a symbolic link to `../../written.png` (absent), and a slide using
  `med-ico-scope-ring` **When** `breathe-inline deck/talk.html --link` **Then** `error: asset icon-scope-ring.png
  leads outside <absolute path of deck>/assets`, exit 1 **And** no `written.png` exists in the parent of `deck/`.

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-021, FR-MOD-001, FR-MOD-003 | E2E-001, E2E-004, E2E-068 | E2E-002, E2E-003, E2E-049, E2E-067 | E2E-006, E2E-005 |
| SC-002 | FR-NEW-004, FR-NEW-005, FR-NEW-021 | E2E-007, E2E-008, E2E-047 | E2E-009, E2E-051, E2E-052, E2E-053 | E2E-010 |
| SC-003 | FR-NEW-006, FR-NEW-007, FR-NEW-008, FR-NEW-023, FR-NEW-024, FR-NEW-025 | E2E-011, E2E-018, E2E-063, E2E-064 | E2E-015, E2E-016, E2E-017, E2E-SEC-007 to E2E-SEC-009, E2E-SEC-011, E2E-SEC-012 | E2E-012, E2E-013, E2E-014, E2E-019, E2E-020, E2E-069, E2E-072 |
| SC-004 | FR-NEW-009, FR-NEW-010 | E2E-021 | E2E-024, E2E-025, E2E-071, E2E-SEC-001 to E2E-SEC-006, E2E-SEC-010 | E2E-022, E2E-023 |
| SC-005 | FR-NEW-011, FR-NEW-012, FR-NEW-013, FR-MOD-002 | E2E-034 | E2E-035, E2E-036, E2E-048, E2E-058, E2E-059, E2E-060, E2E-070 | E2E-037, E2E-061 |
| SC-006 | FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-022 | E2E-026, E2E-027, E2E-029 | E2E-031, E2E-032, E2E-033, E2E-050, E2E-062, E2E-066 | E2E-028, E2E-030 |
| SC-007 | FR-NEW-017 | E2E-038 | E2E-040, E2E-054 | E2E-039 |
| SC-008 | FR-NEW-018 | E2E-041 | E2E-042, E2E-055 | E2E-043 |
| SC-009 | FR-NEW-019, FR-NEW-020, FR-NEW-003 | E2E-044, E2E-046 | E2E-045, E2E-056, E2E-057, E2E-073 | E2E-006 |

Requirements with fewer than three dedicated tests are covered across scenarios: FR-NEW-001 (E2E-001, E2E-002,
E2E-041), FR-NEW-003 (E2E-006, E2E-045, E2E-046), FR-NEW-004 (E2E-007, E2E-027, E2E-047), FR-NEW-011 (E2E-034, E2E-037, E2E-058),
FR-NEW-012 (E2E-035, E2E-037, E2E-059), FR-NEW-013 (E2E-036, E2E-060, E2E-061), FR-NEW-023 (E2E-SEC-007 to
E2E-SEC-009), FR-NEW-024 (E2E-063, E2E-064, E2E-065), FR-NEW-025 (E2E-SEC-011,
E2E-SEC-012, E2E-069), FR-NEW-019 (E2E-044, E2E-045, E2E-057), FR-NEW-020 (E2E-046, E2E-006, E2E-045), FR-NEW-021 (E2E-005, E2E-047, E2E-007),
FR-NEW-022 (E2E-026, E2E-050, E2E-066), FR-MOD-001 (E2E-001, E2E-002, E2E-067, E2E-068), FR-MOD-002 (E2E-048, E2E-034,
E2E-036), FR-MOD-003 (E2E-004, E2E-049, E2E-070), FR-NEW-002 (E2E-003, E2E-004, E2E-005), FR-NEW-015 (E2E-029,
E2E-030, E2E-046), FR-NEW-016 (E2E-032, E2E-033, E2E-050), FR-NEW-018 (E2E-041, E2E-042, E2E-043).

## 11. Open questions

None that changes observable behaviour. The visual faithfulness of the painted export (E2E-027, last clause) is
judged by a person on evidence pictures; it does not change behaviour.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Breathe | the congress template of Dr Lamya CHRIF MORAND, direction B | Template catalogue |
| charter | the set of colours, classes and rules a deck follows, named by a key | Deck checking |
| starting point | the one slide deck `new` copies for a key | Template catalogue |
| reference deck | a deck holding one slide per layout, copied by agents | Template catalogue |
| layout | one slide composition (cover, key figures, ...) | Template catalogue |
| decoration | backgrounds (panels, airway line, stations, watermark) and icons shown through classes | Template catalogue |
| decoration block | the text of a deck's `<style>` between the marker `/* breathe:assets:begin */` and the marker `/* breathe:assets:end */` (the markers the WCBIP deck and the source template already carry) | Template catalogue |
| asset name | a `data-asset` value, or the text after `med-bg-` or `med-ico-` in a class | Template catalogue |
| catalogue | the decoration pictures and sample pictures shipped with the templates | Template catalogue |
| airway line, stage | the line across the top of each slide and the step of the pathway it marks (s0 to s5) | Template catalogue |
| marker | the style token `--breathe-ice` that names the Breathe charter | Deck checking |
| declaration | the `data-doc-template` value of a deck's page | Deck checking |
| painted export | a PPTX whose slides are rebuilt from the measures of the rendered HTML | Export |
| degraded export | the PPTX written when Chromium is unavailable, flowed with background pictures | Export |
| notes page | the PPTX page holding the speaker notes of a slide | Export |
| layout picker | the editor's list of layouts to insert | Editing |
| served file | a file next to the open deck answered by the editor server | Editing |
| request gate | the checks every request to the editor server passes first | Editing |
| skill topic | one section of the agent guidance, loaded by `skill --type` | Agent guidance |
| WCBIP deck | the 14 slide talk of 2026-12-06 built from Breathe | Fixtures |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 16 | 6 | NOT-IMPLEMENTABLE |
| 2 | 18 | 3 | NOT-IMPLEMENTABLE |
| 3 | 11 | 4 | NOT-IMPLEMENTABLE, all amended (see below) |

**Amendments applied:** round 1: FR-NEW-017 counts, E2E-046, FR-NEW-019 exception, decoration block markers,
FR-NEW-023 and E2E-SEC-007 to E2E-SEC-009, widened class sweep (rows 4 to 6, BL-0047), log line and E2E-SEC-004,
E2E-051 to E2E-062, media types, reserved first segments, lexical `..`, size and folder formats, render failure
and missing linked picture, 1 point geometry, FR-NEW-024 and E2E-063, scripted SVG and E2E-SEC-010, 14.3
corrections. Round 2: sweep rows 7 and 8 and the write sink search, gate line, FR-NEW-025 and E2E-SEC-011 and
E2E-SEC-012, non circular NUL payload, check order, counting rules, class to file mapping, shipped catalogue,
asset name kept by the picker, numbered slide names, degraded slide content, topic position, list line format,
query string and trailing slash, E2E-064 to E2E-068, test machine for NFR-001, WCBIP fixture location and
REF-MED, contract and detector lines (14.3, 3.3). Round 2 findings were precision on areas already present, not
a missed area. Round 3: non circular exploit payloads (SECRET-PNG), DOCX export and degraded export rows (9, 10)
in the sweep and BL-0047, lint observable fixtures (`cds-tile`), E2E-069 to E2E-073, history reason, template
and UTF-8 and write refusals, marker outside comments, logged path form, reason precedence, folder forms, 14.3
lines.

**Cap deviation (recorded on purpose):** the three round cap was reached with every round 3 finding a precision
amendment (no scope or product choice, no new area). Under the user's instruction for this run (unattended,
"decide, record decisions"), the amendments were applied directly and checked inline against the 11.4 checklist
instead of a fourth audit; the run report lists this as a concern.
**No implementation detail outside Section 14:** PASS with the public contract exception recorded in 3.3.

## 14. Evidence appendix (for /sdlc-design and the auditor, not for the product owner)

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| E1 eight keys, listing order | `src/mcp_htmleditor/export/charters.py:26` to `:107`; `src/mcp_htmleditor/templates.py:40` |
| E2 unknown key message | `src/mcp_htmleditor/deck/tools.py:43` to `:45` |
| E3 only registry keys resolve | `src/mcp_htmleditor/templates.py:59` to `:61` |
| E4 deck charter detection | `src/mcp_htmleditor/deck/__init__.py:100` to `:107` |
| E5 export theme detection ignores the declaration | `src/mcp_htmleditor/export/pptx_style.py:380` to `:401` |
| E6 Breathe decks declare medical | `~/projects/lamya/presentations/_template/breathe/breathe-template.html:9`, `:16` to `:17`; `WABIP_2026-12_Melbourne/deck/wcbip2026-v1.html:9` |
| E7 lint tables, L008 and L009 medical only, French L006 | `src/mcp_htmleditor/deck/charter_rules.py:18` to `:71`, `:117` to `:143`; `src/mcp_htmleditor/deck/lint.py:28` to `:29` |
| E8 chrome per charter, then flow | `src/mcp_htmleditor/export/to_pptx.py:175` to `:191`; `src/mcp_htmleditor/export/pptx_chrome.py:189` |
| E9 notes aside to the notes page | `src/mcp_htmleditor/export/to_pptx.py:193` to `:200` |
| E10 repaint script | `~/projects/lamya/presentations/_template/breathe/tools/breathe_pptx.py:1` to `:30`, `:760` to `:806` |
| E11 unknown GET path answers Not found | `src/mcp_htmleditor/http_server.py:270` to `:298`, `:680` to `:681` |
| E12 inlining script | `~/projects/lamya/presentations/_template/breathe/tools/breathe_inline.py:1` to `:15` |
| E13 picker sets and detection | `src/mcp_htmleditor/static/slide-layouts.js:12` to `:22`, `:341` |
| E14 15 skill topics | `src/mcp_htmleditor/skill_content.py:23` to `:40` |
| E15 tests of the area | `tests/test_charters.py` (5), `tests/test_templates.py` (13), `tests/test_deck_lint_charter.py` (34), `tests/test_pptx_speaker_notes.py` (5), `tests/test_export_golden.py`, `tests/test_http_header_gate_e2e.py` (14), `tests/test_presentation_templates_fullscreen.py` (12) |

Test command: `make check` (gate), `make test ARGS='-k breathe'` for a subset.

### 14.2 Class sweep

**Class:** a value carried by an HTTP request (path, query, body) or by a deck's markup (`src`, `url()`,
`data-asset`, class names) reaching a file read, copy or write (CWE-22, path traversal), anywhere under the
product, plus the new embedding command and the painted export.
**Searches run:**
- `rg -n "self\.path|urlparse\(self" src/mcp_htmleditor/http_server.py`: every place the request path is read
  (idiom: request target parsing).
- `rg -n "Path\(|open\(|read_text|read_bytes" src/mcp_htmleditor/http_server.py`: every file read of the server
  (idiom: file system sink).
- `rg -n "send_file|_send_file" src/mcp_htmleditor`: every file answer (idiom: file to socket).
- `rg -n "base_dir /|Path\(src\)|shutil\.copy|data-asset|\.read_bytes\(\)" src/mcp_htmleditor --glob '*.py'`
  (idiom: markup value joined to a folder).
- `rg -n "goto|file://|as_uri" src/mcp_htmleditor/render` (idiom: the browser opening local files).
- `rg -n "resource-path|subprocess" src/mcp_htmleditor --glob '*.py'` (idiom: an external tool reading files
  named by markup).
- `rg -n "write_text|write_bytes|atomic_write\(|mkdir\(|shutil\.(copy|move)|os\.replace|\.unlink\(" src/mcp_htmleditor --glob '*.py'`
  (idiom: file system write sink).
- Not searched: the agent tool surface (its paths come from the agent, the trusted caller).

| # | Occurrence | Verdict | Disposition |
|---|---|---|---|
| 1 | `src/mcp_htmleditor/http_server.py:333` `_serve_static` | safe: `Path(filename).name` at `:336` keeps the last segment only, so no directory is climbed; `:337` joins it to the editor's static folder | none |
| 2 | the new answer of files next to the deck (FR-NEW-009) | to be built safe | FR-NEW-010, E2E-SEC-001 to E2E-SEC-006, E2E-SEC-010 |
| 3 | the embedding command (FR-NEW-006, FR-NEW-007): asset names joined to the assets and catalogue folders, read and copied | to be built safe | FR-NEW-023, E2E-SEC-007 to E2E-SEC-009 |
| 4 | `src/mcp_htmleditor/http_server.py:351`, `:371`, `:385`, `:411`, `:448`, `:529`, `:580`, `:621`, `:927` | safe: the path is the open deck, set only by `serve` or `open_file` (`src/mcp_htmleditor/state.py:179`), never taken from the request | none |
| 5 | `src/mcp_htmleditor/http_server.py:97`, `:331`, `:392`, `:418`, `:640` | safe: a constant folder or file (`:97`, `:331`), temporary files (`:392`, `:418`), the shared `_send_file` sink whose callers are rows 1 and 2 | none |
| 7 | `src/mcp_htmleditor/http_server.py:306` (POST dispatch, exact routes, no file), `:398` and `:424` (unlink of the export's own temporary file), `:685` (suffix of a static name, media type only), `:941` (regex over the open deck's `<html>` tag); `src/mcp_htmleditor/deck/__init__.py:53` and `src/mcp_htmleditor/deck/tools.py:48` (command line or agent argument, key checked at `deck/tools.py:44`); `src/mcp_htmleditor/fileio.py:71` (the write target itself); `src/mcp_htmleditor/history.py:140` (id matched against the listed versions at `:139`) | safe: none takes a request value or a markup value as a path | none |
| 8 | `src/mcp_htmleditor/http_server.py:795` (save of the open deck), `src/mcp_htmleditor/arch_layout.py:1203` reached from `http_server.py:621` (the open deck), `src/mcp_htmleditor/request_store.py:155` (state folder keyed by a hash of the open deck, `state.py:213`) | safe: the written path is the open deck or derived from it, never from the request | none |
| 3b | asset files inside the deck's `assets` folder that are links (FR-NEW-025) | to be built safe | FR-NEW-025, E2E-SEC-011, E2E-SEC-012 |
| 9 | `src/mcp_htmleditor/export/to_docx.py:143` to `:144`: pandoc resolves every local `<img src>` of the deck, relative or absolute, and embeds it in the DOCX; reached from `export docx`, the agent tool `export` and `src/mcp_htmleditor/http_server.py:411` | same rule as row 6: deck markup is author content | BL-0047, scope widened to the DOCX export |
| 10 | the degraded export (FR-NEW-016) reading the `url()` of a slide's background class, a new reader | same rule as row 6 | BL-0047, scope widened to the degraded export |
| 6 | `src/mcp_htmleditor/export/pptx_images.py:115` to `:121`, `src/mcp_htmleditor/render/service.py:211`, and the painted export reading linked pictures | safe for request sources (the deck is written through the server only after the gate, `src/mcp_htmleditor/http_server.py:309`); deck markup is author content and can name any local picture, which then reaches the PPTX | BL-0047 (Nature: BUG), deferred by the agent under the user's standing instruction of 2026-11-14 ("decide, record decisions"); the painted export follows the same rule as the flowed export |

### 14.3 Design inputs

- The editor page shows the deck from `/content-frame`, so a relative `assets/x.png` reaches the server as
  `/assets/x.png` (`src/mcp_htmleditor/static/editor.html:116`); the presenter previews use the deck's base
  address (`templates/bootstrap/slides-empty.html:755`). Signal: E2E-021.
- The flowed export reads no background picture today (no `background-image` reader under
  `src/mcp_htmleditor/export/` besides gantt gradients); the degraded export must resolve the slide's background
  class `url()` from the decoration block or the linked file. Signal: E2E-032.
- `_send_file` (`src/mcp_htmleditor/http_server.py:638` to `:648`) sends only type, length and no store; answers
  from the deck's folder need a no sniff instruction and a no script policy for SVG. Signal: E2E-SEC-010, E2E-071.
- L006 reads the notes aside text (`src/mcp_htmleditor/deck/lint.py:299`): no aside of the starting point or
  the reference deck may quote `Title of the presentation`. Signal: E2E-004, E2E-007.
- The three detectors read different things today (`src/mcp_htmleditor/deck/__init__.py:102`, style text;
  `src/mcp_htmleditor/export/pptx_style.py:388`, tokens and classes; `src/mcp_htmleditor/static/slide-layouts.js:14`,
  the whole page); they must agree on FR-NEW-003: add a `breathe` row to `tests/test_charter_detection.py:29` and
  `tests/testdata/detector_table.json`. Signal: E2E-006, E2E-045, E2E-056.
- The repaint script measures with Playwright and draws with python-pptx; both are already used by the product
  (`pyproject.toml`, render extra and dependency). Its measure only accepts pictures written as text; linked
  pictures need the file reading. Signal: E2E-018 then E2E-026.
- Pillow is locked through python-pptx (`uv.lock:1349`) and must be added to the dev group of `pyproject.toml`
  for the generator. The product gains no runtime dependency. Signal: `make breathe-assets` on a fresh `uv sync`.
- The repaint keeps the exporter's notes pages (it clears shapes only). Signal: E2E-029.
- The picker sets are hand written today; the Breathe set must follow the reference deck (E2E-010): a generated
  section with a freshness check, like the pointer block (`tools/sync_deck_pointer.py`).
- Large file storage is configured by this increment (`.gitattributes` routes picture types to it); no binary
  was tracked before, so the catalogue is the first stored content. Signal: `git lfs ls-files` lists the
  catalogue after the commit.
- The exact key or topic lists change with FR-MOD-001 and FR-NEW-018 (declared modification):
  `tests/test_charters.py:61`, `tests/test_deck_tools.py:24`, `tests/test_deck_tools_surface.py:22`,
  `tests/test_skill_shipped.py:40`, `:228`, `tests/test_skill_audit.py:165`, `:187`,
  `tests/test_skill_content.py:19`, `:66`, `tests/test_skill_tool.py:20`, the docstring at
  `tests/test_skill_shipped.py:266`, `tests/conftest.py:142`, and the skill core `skill/core.md:35`. Signal:
  `make test` fails on these alone before they are updated.
- The CLI and agent tool export through `src/mcp_htmleditor/deck/tools.py:91` and the editor through
  `src/mcp_htmleditor/http_server.py:391`; both call `to_pptx`, so the painting and its fallback happen inside
  it. The editor drops the returned warnings. Signal: E2E-026 and E2E-050.
- The Breathe template keeps a per deck `F` key line that SPEC-0022 moved into the presenter block; the guard
  test forbids it (`tests/test_presentation_templates_fullscreen.py:29`). Signal: E2E-047.
