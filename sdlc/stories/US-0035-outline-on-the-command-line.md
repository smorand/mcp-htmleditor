# US-0035: `outline` on the command line

> Spec: SPEC-0007 (sdlc/specs/SPEC-0007-agent-editing-tools/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0034
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Gives an agent or a maintainer `mcp-htmleditor outline <file>`: charter, document type, slide total, per slide facts and document headings, never image data. Creates the `deck/` service package and the test fixtures every later story uses.

## Requirements covered

- SPEC-0007/FR-NEW-001 (partial: command line only; the `problems` count of every slide is 0 here, lint arrives in US-0041 to US-0043 and is wired in US-0044; the tool `outline(file)` arrives in US-0037): WHEN an agent or a user asks for the `outline` of a file THE Editor SHALL return a JSON object describing the file structure without any image data.

## Independent Test

`make test ARGS='-k deck_outline'`: `mcp-htmleditor outline DOC-PERSO` prints exactly `{"file":...,"charter":"doc-perso","doc_type":"document","total":0,"slides":[],"headings":[{"level":1,"text":"Contexte"},{"level":2,"text":"Périmètre"},{"level":1,"text":"Risques"}]}` with exit status 0, and `outline ghost.html` prints `error: File not found: ghost.html` on stderr, nothing on stdout, exit status 1. The headings are read from a real bootstrap based file, not from a mocked parser.

## Design excerpt

### Decisions
- DEC-006 (SPEC-0007): "Charter detection for `outline` and the rules is its own function in `deck/__init__.py`, following the spec rule; the registry maps a non presentation `data-doc-template` value to a charter key and gives the key list. The registry is not extended."
- DEC-007 (SPEC-0007): "`doc_type` and `headings` rules of Section 4": `doc_type` is the `<html data-doc-type>` value when it is `presentation`, `document` or `website`, otherwise `presentation` if slides exist, else `document`; `headings` are `h1` to `h5` inside the document article whose `class` does not contain `doc-title`, text whitespace collapsed.
- DEC-009 (SPEC-0007): "`deck/` is a service layer; `cli.py` and `mcp_server.py` only parse input, call it, and print or return. `DeckError` becomes `error: <msg>` plus exit 1 on the command line and `ToolError(<msg>)` on the tool surface."
- DEC-012 (SPEC-0007): "Slides are enumerated with `export.to_pptx.find_slides`, imported lazily" (import costs 0.29 s: never at module import).
- DEC-015 (SPEC-0007): "JSON output is compact with `ensure_ascii=False`; `file` echoes the caller's string."
- DEC-018 (SPEC-0007): "Words count: `NavigableString` nodes that are not comments, outside `script`, `style`, `svg`."
- DEC-016 (SPEC-0007): extra message `File is not valid UTF-8: <file>`.

### Data model
Outline JSON (presentation), keys in this order:
```json
{"file":"deck.html","charter":"ei","doc_type":"presentation","total":8,
 "slides":[{"index":0,"id":"slide-0","title":"Couverture","slide_type":"title","words":4,"images":3,"problems":0}],
 "headings":[]}
```
Outline JSON (document): `{"file":"doc.html","charter":"doc-perso","doc_type":"document","total":0,"slides":[],"headings":[{"level":1,"text":"Contexte"}]}`.
Internal frozen dataclasses with `__slots__`: `Deck(path, text, soup, slides, charter, doc_type)`.

### Contracts
```python
# deck/__init__.py
class DeckError(Exception): ...
def load_deck(file: str) -> Deck          # DeckError("File not found: <file>"); DeckError("File is not valid UTF-8: <file>")
def slide_id(tag: Tag) -> str | None      # data-id, else id, else None
# deck/read.py
def outline(file: str) -> dict[str, Any]
```
Command: `mcp-htmleditor outline FILE` prints the JSON on stdout. `deck_command` decorator in `cli.py`: wraps a command body, catches `DeckError`, prints `error: <message>` on stderr (standard output empty), `raise SystemExit(1)`. Usage errors stay with click (status 2). The file argument is a plain `click.Path(dir_okay=False)` without `exists=True` (click's check gives exit 2 and another text).

Business rules (from the spec):
- `charter`: presentations are `ei`, `carbon` or `medical`. A presentation is `medical` when its style contains `--med-teal` or `<html>` carries `data-doc-template="medical"`; otherwise `ei` when its style contains `--ei-blue` or the body contains `slide-cover-logos`; otherwise `carbon` (a presentation with no charter mark is `carbon`); medical is tested first. A non presentation takes the `data-doc-template` of its first `data-type="document"` article: `perso` gives `doc-perso`, `ei` gives `doc-ei`, `mail`, `website`, anything else or none gives `doc`. The registry `export/charters.py` `REGISTRY` maps the template value to the key (`docx_key` or `key`).
- `doc_type`: `presentation` or `document`; `website` files report `website`.
- A slide is an element with `data-type="slide"`, otherwise an `article.slide` or `section.slide` (outermost only), found with `find_slides`.
- Per slide: `index` from 0; `id` is `data-id` else `id` else `slide-<index>`; `title` is `data-title`; `slide_type` is `data-slide-type`, empty string if none; `words` counts whitespace separated tokens of the text nodes of the slide element, excluding `script`, `style` and `svg` content, comments and every attribute value, and including eyebrow and footer text; `images` counts `img` elements only; `problems` is 0 in this story.
- Non presentations: `slides` empty, `total` 0, `headings` as in DEC-007. Presentations: `headings` empty, `total` = number of slides.
- JSON output is compact (`json.dumps(obj, separators=(",", ":"), ensure_ascii=False)`), keys in the order shown, `file` echoes the caller's string.
- Errors: `File not found: <file>`, `File is not valid UTF-8: <file>`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/__init__.py` | create: `DeckError`, `Deck`, `load_deck`, `slide_id`, charter and doc_type detection |
| `src/mcp_htmleditor/deck/read.py` | create: `outline()` |
| `src/mcp_htmleditor/cli.py` | modify: add `deck_command` decorator and the `outline` command |
| `tests/deck_support.py` | create: fixture builders and `run_cli` |
| `tests/test_deck_outline.py` | create |

### Existing patterns
- `src/mcp_htmleditor/cli.py` (existing Click group, lazy imports inside commands, `click.echo`).
- `src/mcp_htmleditor/export/to_pptx.py:272` `find_slides`; `src/mcp_htmleditor/export/charters.py` `REGISTRY`.
- `src/mcp_htmleditor/static/slide-layouts.js:12-18` `detectTemplate` (charter signals).
- `tests/test_templates.py` (templates read from the repo path, never `~/.config`), `tests/conftest.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures (generated by `tests/deck_support.py` from the real `templates/bootstrap/*.html`, never committed; no clock, `os.utime(path, (1_000_000_000, 1_000_000_000))` to force modification times):
- DECK-EI: an Euro-Information presentation (real EI bootstrap CSS and cover), no inline colour outside the Euro-Information palette, no remote image, no template text, consistent counters, 8 slides titled `Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`, ids `slide-0` to `slide-7`; slide 3 holds a 1 500 character `data:image/png;base64` image; slides 1 to 6 carry eyebrow `Cat · Slide 0N / 08` (N = index + 1) and page element N (`.slide-foot-page`, so slides 1 to 6 hold 2 to 7); slide 7 is a section slide without foot; `const TOTAL = 8;` and `const slideNames = [ ... ];` consistent.
- DECK-CARBON: a Carbon presentation of 5 slides titled `Intro`, `Offre`, `Chiffres`, `Plan`, `Fin`, eyebrow `Section · Slide 0N / 05`, footers `Slide 1 / 5` to `Slide 5 / 5` (`.slide-footer-right`), TOTAL 5, slideNames 5 entries.
- DECK-MED: a medical presentation of 6 slides: cover (`data-slide-type="title"`) then content slides with `.med-strip` children carrying `w-50`, a tiny PNG, a non empty `.med-source`, `.slide-foot-page`.
- DOC-PERSO: `document-perso-empty.html` with the article body replaced by `h1.doc-title` "Rapport", `h1.doc-h1` "Contexte", `h2.doc-h2` "Périmètre", `h1.doc-h1` "Risques".

Helpers created in `tests/deck_support.py`: `build_deck(charter, titles, *, image_chars=None, image_slide=None, mutate=None) -> str` (cuts the bootstrap at the first `<article` and after the last `</article>`, keeps the retitled bootstrap cover, generates the other slides from small literal templates copying the real classes, writes counters, `TOTAL` and `slideNames` by plain string formatting independent of product code), `deck_ei()`, `deck_carbon()`, `deck_med()`, `doc_perso()`, `run_cli(*args, input=None) -> (stdout, stderr, exit_code)` using `CliRunner` with separate streams. Templates are read through an explicit repo path.

### SPEC-0007/E2E-002: Outline of a document
- Level E2E; Driver CLI; Location `tests/test_deck_outline.py`
- Given DOC-PERSO
- When the user runs `mcp-htmleditor outline DOC-PERSO`
- Then the JSON has `charter` `doc-perso`, `doc_type` `document`, `total` 0, `slides` empty
- And `headings` is `[{"level":1,"text":"Contexte"},{"level":2,"text":"Périmètre"},{"level":1,"text":"Risques"}]`

### Additional integration and unit tests (same file, `tests/test_deck_outline.py`)
- Outline of DECK-EI: `charter` `ei`, `doc_type` `presentation`, `total` 8, `headings` `[]`, 8 slides; index 2 has `id` `slide-2`, `title` `Contexte`, `images` 0; index 3 has `images` 1; the output string does not contain `base64`; every slide has `problems` 0.
- Outline of DECK-CARBON gives `charter` `carbon` and total 5; DECK-MED gives `medical` (medical tested before ei: a file with both `--med-teal` and `--ei-blue` is `medical`); a presentation with no mark gives `carbon`; a file with `slide-cover-logos` in the body and no `--ei-blue` gives `ei`; `data-doc-template="medical"` on `<html>` gives `medical`.
- A website bootstrap outline: `charter` `website`, `doc_type` `website`, `total` 0; a mail bootstrap: `charter` `mail`, `doc_type` `document`; a document with `data-doc-template="ei"` gives `doc-ei`; an unknown template value gives `doc`.
- Words unit: a slide whose HTML is `<article data-type="slide" data-title="a b c"><p>one two</p><script>x y z</script><svg><text>q r</text></svg><!-- c d --></article>` counts 2 words.
- Titles: slide with no `data-id` and `id="s"` reports id `s`; with neither, `slide-<index>`.
- `outline ghost.html`: stderr exactly `error: File not found: ghost.html\n`, stdout empty, exit 1. A file with bytes `b"\xff\xfe"` gives `error: File is not valid UTF-8: <file>`, exit 1.
- Importing `mcp_htmleditor.deck` does not import `pptx` (check `"pptx" not in sys.modules` in a subprocess).

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/export/*` (read only use), `src/mcp_htmleditor/mcp_server.py`.
- Dependencies not to add: none (beautifulsoup4 and soupsieve are present).
- Patterns to avoid: `print` or stdout use inside `deck/` (only `cli.py` echoes); `type: ignore`; importing python-pptx at module import; reading `~/.config` templates in tests.
- Scope boundary: no lint, no scanner, no `get-slide`, no tool.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: existing tests (`tests/test_templates.py`, `tests/test_skill_content.py`, `tests/test_export_pptx.py`) pass unmodified; the existing commands `serve`, `new`, `templates`, `export`, `arch-layout` behave as before.
- [ ] Docs updated: none required by this story (the surface documentation lands in US-0037 and US-0046).
- [ ] Self review: full at tier 2.
- [ ] This story registers no MCP tool; `skill/core.md` is not touched.
- [ ] One commit `US-0035: `outline` on the command line`, body `Spec: SPEC-0007` and the requirement ids FR-NEW-001.
