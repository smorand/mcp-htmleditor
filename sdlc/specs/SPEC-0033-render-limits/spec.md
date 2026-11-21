# Render limits found while reviewing SPEC-0008: functional specification

> Id: SPEC-0033
> Nature: FEAT
> Depth: M
> Depth evidence: 4 observable behaviors of one command (render), 1 module, 7 requirements, no persisted change
> Status: implemented
> Generated on: 2026-11-20
> Project: existing
> From backlog: BL-0031
> Depends on: SPEC-0008
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary
`mcp-htmleditor render` (and the `render` tool) has four rough edges found while building it: a first slide that starts below the visible window cannot be pictured, the font check reports the system font stack as missing, a script error that spans several lines is printed on several report lines, and an image that fails to load is reported once per use and, with an empty address, with a blank where the address should be.

## 2. Current State
### 2.1 What users can do today
- Render a slide to a picture and ask for a layout report (`--report`, `--report-only`, `--json`); problems are lines `<kind> <slide>: <message>` (SPEC-0008).
- A deck whose first slide starts below the first 900 pixels of the page (a tall block above it) makes the picture fail: `Rendering failed: Page.screenshot: Clipped area is either empty or outside the resulting image`.
- A deck that names the usual system font stack (`-apple-system, BlinkMacSystemFont, sans-serif`) gets `font slide-0: "-apple-system" is not available, fallback used`; so do `ui-sans-serif`, `cursive` and `emoji`.
- A script error whose text has line breaks is printed over several lines and breaks the one problem per line format.
- An image that does not load gives one `image slide-N: <address> did not load` line each time it is used, so the same missing picture used twice prints two identical lines; an image with an empty address prints `image slide-6:  did not load` (two spaces).
Evidence: Section 14.1.
### 2.2 Specs governing this area
SPEC-0008 (render; FR-NEW-003 lists the report checks, DEC-008 the picture clip). Where this spec adds to them it says so; SPEC-0008 is not modified.
### 2.3 What is verified today
Browser tests of the report in `tests/test_render_report.py` and of the picture in `tests/test_render_picture.py`; none uses a first slide below the window, a system font stack, a multi line script error, a repeated missing image or an empty address. Section 14.1.

## 3. Scope
### 3.1 In scope
The four behaviors above for the command line and the tool.
### 3.2 Out of scope, and why
New report checks; the picture size and scale rules; wording of other problem kinds (unchanged).
### 3.3 Constraints imposed by the context
None.

## 4. Actors
A person or an agent running `render`.

## 5. Usage scenarios
### SC-001: picture of a slide below the fold
**Actor:** an agent. **Preconditions:** a deck with a 1200 pixel block above its slides. **Flow:** the agent renders `slide-0` → a picture of the slide, 480 by 270 at the default scale. **Exceptions:** none.
### SC-002: font check on a system font stack
**Flow:** the agent runs `render --report` on a deck whose text uses `-apple-system, BlinkMacSystemFont, sans-serif` → no `font` line.
### SC-003: script error over several lines
**Flow:** the page script throws `Error: first line` then `second line` → one `script` line `Error: first line second line`.
### SC-004: the same missing image twice, an empty address
**Flow:** slide 0 uses `missing.png` twice and has an image with `src=""` → one line `image slide-0: missing.png did not load` and one line `image slide-0: (empty address) did not load`.

## 6. Functional requirements
### 6.1 New
#### FR-NEW-001 [EARS-E]: a slide below the visible window can be pictured
> WHEN the slide asked for starts below the visible window THE render SHALL bring it into view before taking its picture and SHALL give the same 960 by 540 slide, scaled as asked.
- **Scenario:** SC-001. **Priority:** Must.
#### FR-NEW-002 [EARS-S]: the font check ignores generic names
> WHILE the font check runs THE render SHALL treat as available, and never report, the CSS generic family names `serif`, `sans-serif`, `monospace`, `cursive`, `fantasy`, `system-ui`, `ui-serif`, `ui-sans-serif`, `ui-monospace`, `ui-rounded`, `emoji`, `math`, `fangsong` and the system font keywords `-apple-system` and `BlinkMacSystemFont`, whatever their letter case and whether written with quotes or without.
- **Business rules:** a font stack made only of such names gives no `font` line; a stack with an uninstalled named font after them is reported as today: one `font` line per stack, naming its first named font, and only when none of the stack's named fonts is installed.
- **Scenario:** SC-002. **Priority:** Must.
#### FR-NEW-003 [EARS-U]: one line per problem
> The render SHALL report a script error (an `Error` object thrown by the page) on one line: every run of white space (spaces, tabs, line breaks, non breaking spaces) in its text becomes one space and the ends are trimmed; two errors alike after that are one line per slide, as today.
- **Scenario:** SC-003. **Priority:** Must.
#### FR-NEW-004 [EARS-U]: one line per missing image address and slide
> The render SHALL report an image that did not load once per slide and address, in the order of first use, however many times the slide uses it. The address is compared as written in full: two different data addresses whose printed form is alike are two lines.
- **Scenario:** SC-004. **Priority:** Must.
#### FR-NEW-005 [EARS-O]: an image with an empty address
> IF an image of a slide has an empty address THEN THE render SHALL report `image <slide>: (empty address) did not load`.
- **User visible text:** `(empty address) did not load`.
- **Scenario:** SC-004. **Priority:** Must.
### 6.2 Modified
#### FR-MOD-001 [EARS-S]: the font check list (adds to SPEC-0008 FR-NEW-003)
> The list of names the font check never reports is the one of FR-NEW-002.
- **Before:** `serif`, `sans-serif`, `monospace`, `system-ui`. **After:** FR-NEW-002. **Reason:** this spec.
#### FR-MOD-002 [EARS-S]: the image lines (adds to SPEC-0008 FR-NEW-003)
> The image lines are the ones of FR-NEW-004 and FR-NEW-005.
- **Before:** one line per use; empty address with a blank. **After:** FR-NEW-004, FR-NEW-005. **Reason:** this spec.

## 7. Non functional requirements
Not applicable: same cost as today (the scroll adds one call).

## 8. Edge cases
| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Boundary | the slide starts exactly at the bottom edge of the window | pictured | E2E-008 |
| Empty | stack of generic names only | no `font` line | E2E-002 |
| Data | stack `-APPLE-SYSTEM, "Nope Sans", sans-serif` | `Nope Sans` reported, the others not | E2E-003 |
| Data | script error with `\r\n`, tabs, non breaking spaces | one line, single spaces | E2E-004 |
| Data | two different missing images, one used twice | two lines | E2E-005 |
| Ordering | the empty address image comes first | its line first | E2E-006 (case b) |
| Other slide | the same missing image on slide 1 and slide 2 | one line on each | E2E-005 |
| Concurrency, connectivity, access, navigation, exhaustion | not applicable | | |

## 9. Acceptance tests
### 9.1 Summary
| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | journey | SC-001 | FR-NEW-001 | Critical |
| E2E-002 | New | requirement | SC-002 | FR-NEW-002, FR-MOD-001 | High |
| E2E-003 | New | failure | SC-002 | FR-NEW-002 | High |
| E2E-004 | New | failure | SC-003 | FR-NEW-003 | High |
| E2E-005 | New | failure | SC-004 | FR-NEW-004, FR-MOD-002 | High |
| E2E-006 | New | failure | SC-004 | FR-NEW-005 | High |
| E2E-007 | New | side effect | SC-001 | FR-NEW-001 | Medium |
| E2E-008 | New | edge | SC-001 | FR-NEW-001 | Medium |
| E2E-009 | New | edge | SC-003 | FR-NEW-003 | Medium |
Coverage: happy 3, failure 4 (E2E-003 to E2E-006), edge 2. Ratio 1:1.3. Each requirement has at least 3 tests or cases.
### 9.2 New tests
Tests marked (cases) are run once per case. Fixtures: "red block" is `<div style="width:100px;height:100px;background:#FF0000"></div>` in slide 0's body; "tall block" is `<div style="height:1200px"></div>` as the first child of `<body>`, followed by the slides, with the body margin at 0.
#### E2E-001: a slide below the window
- **Given** a deck with the red block in slide 0 and the tall block above the slides
- **When** an agent runs `render <deck> --slide slide-0`
- **Then** it prints `Rendered slide-0 to <path> (480x270)`, exit status 0, and the picture (scale 0.5, so the block is 50 by 50 pixels) has at least 1 000 pixels of colour (255, 0, 0)
#### E2E-002: system font stack (cases)
- **Given** slide 0 text with `font-family:-apple-system, BlinkMacSystemFont, sans-serif` (case a), `ui-sans-serif, ui-serif, ui-monospace, ui-rounded` (b), `cursive, fantasy, emoji, math, fangsong, system-ui` (c)
- **When** the agent runs `render <deck> --slide slide-0 --report`
- **Then** no `font` line in any case
#### E2E-003: a named font after generic ones
- **Given** text with `font-family:-APPLE-SYSTEM, "Nope Sans", sans-serif`
- **Then** exactly one `font slide-0: "Nope Sans" is not available, fallback used`; and with `font-family:"Nope Sans", "Other Nope", "sans-serif", serif` also exactly one line, naming `Nope Sans` (quoted generic names are ignored)
#### E2E-004: multi line script error (cases)
- **Given** a page script that throws at page load `new Error("first line\r\nsecond line  ")` (a), `new Error("a\tb\n\nc")` (b), `new Error("x\u00a0y")` (c), each thrown at page load
- **When** the agent runs `render <deck> --slide slide-0 --report`
- **Then** exactly one `script` line each: `script -: Error: first line second line`, `script -: Error: a b c`, `script -: Error: x y`
#### E2E-005: missing image repeated (cases)
- **Given** slide 0 using `missing.png` twice and `other.png` once, slide 1 using `missing.png` (case a); two different `data:` addresses sharing their first 40 characters, both undecodable (case b); `missing.png` used on slides 0 and 1 and an undecodable data address used twice on slide 0 (case c)
- **When** the agent runs `render <deck> --report-only`
- **Then** (a) three `image` lines in this order: `image slide-0: missing.png did not load`, `image slide-0: other.png did not load`, `image slide-1: missing.png did not load`; (b) two lines (the two data addresses share their first 40 characters, then differ in undecodable tails, so the two printed lines are alike: the first 40 characters then `...`); (c) the same address `missing.png` on slide 0 and on slide 1 and a data address used twice on slide 0: one line per slide and address, in this order: `image slide-0: missing.png did not load`, then the line of the data address, then `image slide-1: missing.png did not load`
#### E2E-006: empty address (cases)
- **Given** slide 0 with `<img src="">` (case a); with `<img src="">` before `<img src="missing.png">` (case b); with `<img src="">` used twice (case c)
- **Then** (a) `image slide-0: (empty address) did not load`; (b) that line, then `image slide-0: missing.png did not load`; (c) the empty address line once
#### E2E-007: the picture is the slide
- **Given** the deck of E2E-001 and the same deck without the tall block, scale 1
- **Then** the two pictures of slide 0 are equal pixel for pixel (decoded pixels, not bytes of the PNG files)
#### E2E-008: the slide starts exactly at the bottom edge
- **Given** the deck of E2E-001 whose tall block has the height that puts the slide's top edge at 900 px, the window height (the test measures the slide's top without the block and subtracts it from 900)
- **Then** the picture is produced; the pass criterion is a picture with at least 1 000 pixels of (255, 0, 0)
#### E2E-009: the same script error twice
- **Given** a page script that throws at load the same error twice, once as `new Error("first line\nsecond line")` and once as `new Error("first line second line")` (thrown at page load, so the slide is `-`)
- **Then** one line `script -: Error: first line second line`

## 10. Traceability
| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001 | E2E-001 | | E2E-007, E2E-008 |
| SC-002 | FR-NEW-002, FR-MOD-001 | E2E-002 | E2E-003 | |
| SC-003 | FR-NEW-003 | | E2E-004 | E2E-009 |
| SC-004 | FR-NEW-004, FR-NEW-005, FR-MOD-002 | | E2E-005, E2E-006 | |

## 11. Open questions
None.

## 12. Glossary
| Term | Definition | Context |
|---|---|---|
| report | the list of layout problems `render --report` prints, one per line | SPEC-0008 |
| generic family name | a CSS font name that names a kind of font, not an installed font | CSS |
| below the window | the slide's top edge lies under the 900 pixel high page window | render |

## 13. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 6 | 0 | NOT-IMPLEMENTABLE |
| 2 | 9 | 0 | NOT-IMPLEMENTABLE |
| 3 | 7 | 0 | IMPLEMENTABLE (amended in place) |

## 14. Evidence appendix
### 14.1 Current State evidence
| Claim | Evidence |
|---|---|
| the picture clip is the slide's bounding box in the 900 pixel window | `src/mcp_htmleditor/render/service.py:_shoot` (`bounding_box`, `page.screenshot(clip=...)`) |
| the font check ignores four names | `src/mcp_htmleditor/render/scripts.py:75` (`const generic = ['sans-serif', 'serif', 'monospace', 'system-ui']`) |
| script errors are kept as `<name>: <message>` | `src/mcp_htmleditor/render/service.py:PageSignals.record` |
| one image line per use | `src/mcp_htmleditor/render/scripts.py:IMAGES_JS`, `service.py:_failed_images` |
| `<img src="">` is reported with the blank address | `scripts.py:IMAGES_JS` (`hasAttribute('src')`), `problems.py:shorten_source` |
Test commands: `make check`.
### 14.3 Design inputs
Scroll the target into view then recompute its box before the clip; extend the `generic` list; normalise white space in `PageSignals.record`; de duplicate `(slide, src)` in `_failed_images`; map `''` to `(empty address)` in the message.
