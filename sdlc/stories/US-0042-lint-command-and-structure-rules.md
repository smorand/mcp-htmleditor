# US-0042: `lint` command and structure rules

> Spec: SPEC-0007 (sdlc/specs/SPEC-0007-agent-editing-tools/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0038
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Gives `mcp-htmleditor lint <file> [--json]` with the six structure rules L001 to L006, the report format, the verdict and the exit status.

## Requirements covered

- SPEC-0007/FR-NEW-012 (partial: command line; the tool arrives in US-0046; only the structure rules exist here): WHEN an agent or a user runs `lint` on a file THE Editor SHALL report every problem found and a verdict, and exit with status 1 when at least one problem is an error.
- SPEC-0007/FR-NEW-013: WHEN `lint` runs on a presentation THE Editor SHALL apply these rules, all errors.

## Independent Test

`make test ARGS='-k deck_lint'`: `lint DECK-EI` prints exactly `lint: OK (0 errors, 0 warnings)` with exit 0; with the TOTAL constant set to 7 it prints `error L002 - TOTAL is 7 but the file has 8 slides` then `lint: FAIL (1 error, 0 warnings)` with exit 1. Fixtures come from the real bootstrap CSS; counters expected by the tests are computed by the test, not by the renumber code.

## Design excerpt

### Decisions
- DEC-008 (SPEC-0007): "Lint is a tuple of rule functions per scope (file, slide), ordered by code, producing `Problem` records; sorting is (whole file first, slide index, code), stable inside a code... The slide column falls back to `slide-<index>` when the slide has no id. L005 checks the eyebrow for all charters and only the counter kind of its charter (Carbon footer, EI and medical page element)." Handler tables keyed by code keep each function under the ruff complexity limits (no per file ignore).
- DEC-012 (SPEC-0007): slides enumerated with `find_slides` (lazy import).
- DEC-009 (SPEC-0007): service layer; `lint` exits 1 itself when `errors > 0`; `DeckError` (file not found) goes through `deck_command`.
- Interpretation chosen: L002 is not reported when the `TOTAL` constant is absent; L003 is not reported when the `slideNames` list is absent.

### Data model
Problem JSON: `{"code":"L002","severity":"error","slide":null,"message":"TOTAL is 8 but the file has 9 slides"}`. Result JSON: `{"problems":[...],"errors":1,"warnings":0}`. Internal frozen dataclass with `__slots__`: `Problem(code, severity, slide_index | None, slide | None, message)`.

### Contracts
```python
# deck/lint.py
def lint_deck(deck: Deck) -> list[Problem]
def lint_file(file: str) -> dict[str, Any]          # {"problems": [...], "errors": n, "warnings": n}
def format_report(problems: Sequence[Problem]) -> list[str]   # problem lines then the verdict line
```
Command: `mcp-htmleditor lint FILE [--json]`; text mode prints `format_report` lines with `click.echo`. `deck_command` decorator in `cli.py`: wraps a command body, catches `DeckError`, prints `error: <message>` on stderr (standard output empty), `raise SystemExit(1)`. Usage errors stay with click (status 2). The file argument is a plain `click.Path(dir_okay=False)` without `exists=True` (click's check gives exit 2 and another text). `lint` raises `SystemExit(1)` itself after printing when there is an error. Unknown file: `error: File not found: <file>` through `deck_command`.

Report format (FR-NEW-012 business rules):
- A problem line is `<severity> <code> <slide> <message>` where `<slide>` is the slide id or `-` for the whole file, for example `error L002 - TOTAL is 8 but the file has 9 slides`. The slide id is `data-id`, else `id`, else `slide-<index>`.
- Problems are ordered whole file first, then slide by slide in order, then by code (stable inside a code).
- Last line `lint: OK (0 errors, 2 warnings)` or `lint: FAIL (1 error, 2 warnings)`; `1 error` singular, `0 errors` and `2 errors` plural; same for `warning`/`warnings`. OK when there is no error, FAIL otherwise.
- JSON (`--json`, and the tool in US-0046): `{"problems":[{"code","severity","slide","message"}],"errors":<n>,"warnings":<n>}`, `slide` null for the whole file; compact, `ensure_ascii=False`; with `--json` only the JSON is printed.
- Exit status 1 when at least one problem is an error, else 0. Documents, mails and websites are checked only by L010 (US-0043).

Rules (all errors, presentations only; a non presentation returns no problem in this story). Slides are those of `find_slides`; N is the index plus 1; TT the number of slides:
| Code | Rule | Message |
|---|---|---|
| L001 | a slide lacks `data-type="slide"`, `data-id` or `data-title` (one problem per missing attribute, in this order) | `missing attribute data-title` (`missing attribute data-type`, `missing attribute data-id`) |
| L002 | the total constant `const TOTAL = <integer>;` differs from the number of slides | `TOTAL is 8 but the file has 9 slides` |
| L003 | the list `const slideNames = [ ... ];` has another length (the length is the number of top level string literals; the scan skips string contents with `\` escapes, handles `"`, `'` and backtick quotes and nested brackets) | `slideNames has 8 entries but the file has 9 slides` |
| L004 | two slides share an id, or ids are not `slide-0`, `slide-1`, ... in order (id is `data-id`, else `id`; a slide without id is skipped; a slide that is both duplicate and out of order gives the duplicate problem only; a duplicate is any slide whose id appeared on an earlier slide) | `duplicate id "slide-3"` or `expected id "slide-2" but found "slide-5"` |
| L005 | an existing counter differs from the FR-NEW-009 value: eyebrow (first `.slide-eyebrow`, pattern `Slide <n> / <total>`, expected `Slide 0N / TT` two digits each), page counter (`.slide-foot-page` text, expected `N`, for `ei` and `medical` decks), Carbon footer (`.slide-footer-right` pattern, expected `Slide N / TT`, for `carbon` decks) | `eyebrow counter says "Slide 05 / 09", expected "Slide 03 / 09"`, `page counter says "5", expected "3"` or `footer counter says "Slide 5 / 9", expected "Slide 3 / 9"` |
| L006 | template text left: `Contenu de la slide`, `Titre de la présentation` (substring of the slide's text, scripts and styles excluded), or the eyebrow text `Section · Slide 01 / 01` on a slide that is not the first slide of a one slide deck; one problem per distinct text per slide, in this order | `template text left: "Contenu de la slide"` |

L005 only checks a counter that exists: an eyebrow with no `Slide <n> / <total>` pattern, a slide with no eyebrow and a slide with no page element (cover, section) are not problems. Within a slide L005 reports the eyebrow first, then the page or footer counter.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/lint.py` | create: `Problem`, rules L001 to L006, `lint_deck`, `lint_file`, `format_report` |
| `src/mcp_htmleditor/cli.py` | modify: add the `lint` command |
| `tests/deck_support.py` | modify: add mutators `set_total`, `drop_attr`, `inject_html`, `set_names_len` |
| `tests/test_deck_lint.py` | create |

### Existing patterns
- `src/mcp_htmleditor/deck/__init__.py` (US-0035) `Deck`, charter; `deck/renumber.py` (US-0039) counter regexes may be reused for patterns only; expected values are recomputed independently in lint.
- `src/mcp_htmleditor/cli.py` `deck_command` (US-0035).
- `ruff` complexity limits (PLR0912, PLR0911) in `pyproject.toml`: table dispatch instead of long ifs.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures (generated by `tests/deck_support.py` from the real `templates/bootstrap/*.html`, never committed; no clock, `os.utime(path, (1_000_000_000, 1_000_000_000))` to force modification times):
- DECK-EI: an Euro-Information presentation (real EI bootstrap CSS and cover), no inline colour outside the Euro-Information palette, no remote image, no template text, consistent counters, 8 slides titled `Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`, ids `slide-0` to `slide-7`; slide 3 holds a 1 500 character `data:image/png;base64` image; slides 1 to 6 carry eyebrow `Cat · Slide 0N / 08` (N = index + 1) and page element N (`.slide-foot-page`, so slides 1 to 6 hold 2 to 7); slide 7 is a section slide without foot; `const TOTAL = 8;` and `const slideNames = [ ... ];` consistent.
- DECK-CARBON: a Carbon presentation of 5 slides titled `Intro`, `Offre`, `Chiffres`, `Plan`, `Fin`, eyebrow `Section · Slide 0N / 05`, footers `Slide 1 / 5` to `Slide 5 / 5` (`.slide-footer-right`), TOTAL 5, slideNames 5 entries.
- DECK-MED: a medical presentation of 6 slides: cover (`data-slide-type="title"`) then content slides with `.med-strip` children carrying `w-50`, a tiny PNG, a non empty `.med-source`, `.slide-foot-page`.
- DOC-PERSO: `document-perso-empty.html` with the article body replaced by `h1.doc-title` "Rapport", `h1.doc-h1` "Contexte", `h2.doc-h2` "Périmètre", `h1.doc-h1` "Risques".

Mutators added to `tests/deck_support.py` (pure string functions): `set_total(html, n)`, `drop_attr(html, slide_index, attr)`, `inject_html(html, slide_index, fragment)` (appends the fragment inside the slide's `.slide-body`), `set_names_len(html, n)`.

### SPEC-0007/E2E-009: Clean lint
- Level E2E; Driver CLI; Location `tests/test_deck_lint.py`
- Given DECK-EI
- When the user runs `mcp-htmleditor lint DECK-EI`
- Then the output is exactly `lint: OK (0 errors, 0 warnings)` and the exit status is 0

### SPEC-0007/E2E-020: Total wrong
- Level E2E; Driver CLI; Location `tests/test_deck_lint.py`
- Given DECK-EI where the total constant is set to 7
- When the user runs `lint`
- Then the output holds `error L002 - TOTAL is 7 but the file has 8 slides`, ends with `lint: FAIL (1 error, 0 warnings)`, exit status 1

### SPEC-0007/E2E-023: Template text left
- Level E2E; Driver CLI; Location `tests/test_deck_lint.py`
- Given DECK-EI where `slide-4` still holds `Contenu de la slide`
- When the user runs `lint`
- Then the output holds `error L006 slide-4 template text left: "Contenu de la slide"`

### SPEC-0007/E2E-024: Missing attributes
- Level E2E; Driver CLI; Location `tests/test_deck_lint.py`
- Given DECK-EI where `slide-5` has no `data-title`
- When the user runs `lint`
- Then the output holds `error L001 slide-5 missing attribute data-title`

### SPEC-0007/E2E-025: Wrong counters
- Level E2E; Driver CLI; Location `tests/test_deck_lint.py`
- Given DECK-EI where the eyebrow of `slide-2` reads `Slide 05 / 08` and its page element reads `5`
- When the user runs `lint`
- Then the output holds `error L005 slide-2 eyebrow counter says "Slide 05 / 08", expected "Slide 03 / 08"` then `error L005 slide-2 page counter says "5", expected "3"`

### SPEC-0007/E2E-038: Slide names list length
- Level E2E; Driver CLI; Location `tests/test_deck_lint.py`
- Given DECK-EI where the slide names list holds 7 entries
- When the user runs `lint`
- Then the output holds `error L003 - slideNames has 7 entries but the file has 8 slides`

### SPEC-0007/E2E-039: Ids out of order
- Level E2E; Driver CLI; Location `tests/test_deck_lint.py`
- Given DECK-EI where the id of the third slide is `slide-5` (its `data-id` too)
- When the user runs `lint`
- Then the output holds `error L004 slide-5 expected id "slide-2" but found "slide-5"`
- And with two slides both named `slide-3`, the output holds `error L004 slide-3 duplicate id "slide-3"`

### SPEC-0007/E2E-041: Slide operations on a document
- Level E2E; Driver CLI (patch, get-slide, lint); Location `tests/test_deck_lint.py`
- Given DOC-PERSO
- When the agent patches `[{"op":"delete_slide","id":"slide-0"}]` and calls `get_slide` with `id` `slide-0` (command `get-slide`)
- Then the patch fails with `patch failed at operation 1: operation "delete_slide" needs a presentation (nothing written)` and `get_slide` fails with `get_slide needs a presentation: DOC-PERSO`
- And `lint` on DOC-PERSO prints `lint: OK (0 errors, 0 warnings)`

### Additional tests (same file)
- `test_lint_clean_after_special_title_insert`: patch DECK-EI inserting after `slide-1` a valid slide with `data-title="Café &amp; &quot;Co&quot; &lt;1&gt;"` (helper `slide_html`), then `lint` prints `lint: OK (0 errors, 0 warnings)` (completes the clause of E2E-030 that US-0040 cannot assert).
- Report format table: `format_report` for 0, 1, 2 errors and 0, 1, 2 warnings gives `lint: OK (0 errors, 0 warnings)`, `lint: FAIL (1 error, 0 warnings)`, `lint: FAIL (2 errors, 1 warning)`, `lint: OK (0 errors, 2 warnings)`; a whole file problem prints `-` in the slide column.
- Ordering: a deck with an L006 on slide-4, an L001 on slide-1 and an L002 whole file problem prints L002 first, then slide-1, then slide-4; two problems on one slide order by code.
- L003 literal counter: `["a", 'b', `c`]` counts 3; `["a\"b", "c]"]` counts 2; `[["x","y"], "z"]` counts 2 top level literals; a list written on one line and one with trailing comma count the same.
- L002 and L003 are not reported for a deck whose script holds no `TOTAL` and no `slideNames`.
- L004: ids `slide-0, slide-1, slide-1` gives `error L004 slide-1 duplicate id "slide-1"` for the third slide only; a slide with neither `data-id` nor `id` gives L001 `missing attribute data-id` and no L004.
- L005 Carbon: footer `Slide 5 / 9` on slide index 2 of a 9 slide deck gives `footer counter says "Slide 5 / 9", expected "Slide 3 / 9"`; an eyebrow with no pattern (`Sommaire`) and a section slide without page element give no problem.
- L006: the eyebrow `Section · Slide 01 / 01` on slide-0 of a one slide deck gives no problem; on slide-0 of DECK-CARBON (5 slides) gives `template text left: "Section · Slide 01 / 01"`; `Titre de la présentation` gives `template text left: "Titre de la présentation"`.
- `lint ghost.html`: `error: File not found: ghost.html` on stderr, stdout empty, exit 1. `lint --json` on DECK-EI prints `{"problems":[],"errors":0,"warnings":0}`.
- `lint` on the real bootstrap files (`slides-ei-empty.html` etc.) never crashes (returns a report).

## Constraints

- Files not to touch: `src/mcp_htmleditor/deck/patch.py`, `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/static/*`.
- Dependencies not to add: none.
- Patterns to avoid: one giant function for all rules (ruff PLR0912); stdout in `deck/`; trusting the product renumber code to compute expected counters in tests.
- Scope boundary: charter rules L007 to L011 (US-0043); wiring into outline and patch (US-0044); tool (US-0046). DECK-EI must stay lint clean when later rules are added.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: US-0035 to US-0040 tests unchanged.
- [ ] Docs updated: none beyond code docstrings (docs are consolidated in `.agent_docs/agent-editing.md` by US-0046).
- [ ] Self review: full at tier 2.
- [ ] This story registers no MCP tool; `skill/core.md` is not touched.
- [ ] One commit `US-0042: `lint` command and structure rules`, body `Spec: SPEC-0007` and the requirement ids FR-NEW-012, FR-NEW-013.
