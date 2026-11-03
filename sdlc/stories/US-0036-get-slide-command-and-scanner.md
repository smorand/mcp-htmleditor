# US-0036: `get-slide` on the command line and the scanner

> Spec: SPEC-0007 (sdlc/specs/SPEC-0007-agent-editing-tools/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0035
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Gives `mcp-htmleditor get-slide <file> <id>`: the raw HTML of one slide with large images replaced by `data:ref:img-N`. Introduces the byte offset scanner every later patch story relies on.

## Requirements covered

- SPEC-0007/FR-NEW-002 (partial: command line; the tool `get_slide` arrives in US-0037): WHEN an agent asks for `get_slide` with a slide id THE Editor SHALL return the HTML of that slide only, with every image whose source is a data address longer than 1 000 characters replaced by the reference `data:ref:img-N`.

## Independent Test

`make test ARGS='-k deck_get_slide'`: `get-slide DECK-EI slide-3` prints an `<article ... id="slide-3"` that contains `data:ref:img-1` and no `base64`; `get-slide DECK-CARBON slide-9` prints `error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2, slide-3, slide-4` on stderr with exit 1. A scanner invariant test loops over every `templates/**/*.html` and checks the scanner against BeautifulSoup (independent parser).

## Design excerpt

### Decisions
- DEC-002 (SPEC-0007): "Elements are located by a `HTMLParser` subclass; BeautifulSoup tags are mapped to its nodes by `(sourceline, sourcepos)`." Measured: bs4 4.15.0 gives `sourceline=2, sourcepos=1` for the tag in `"<div>\n <article>…"`, equal to `getpos()`.
- DEC-001 (SPEC-0007): "The patch engine is a text splice on offsets from a scanner (Approach 2.1 A)": no parse and serialize with BeautifulSoup (it reformats the whole file).
- DEC-019 (SPEC-0007): "`get_slide` returns the slide's raw text from the scanner with large image sources replaced in place by `data:ref:img-N`; `replace_slide` restores by the same ordering on the replaced slide's current text."
- DEC-012 (SPEC-0007): slides enumerated with `find_slides`, lazy import.
- DEC-009 / DEC-016 (SPEC-0007): errors are `DeckError`; `get_slide needs a presentation: <file>`.

### Data model
No JSON shape. Internal frozen dataclasses with `__slots__`: `Node(tag, start, start_end, end_start, end_end, line, col)` where `start` is the offset of `<`, `start_end` the offset after the start tag `>`, `end_start` the offset of `</`, `end_end` the offset after the end tag `>`; void elements and `<x/>` have no end (`end_start == end_end == start_end`); `Edit(start, end, text)` is declared in US-0039.

### Contracts
```python
# deck/scan.py
def scan(text: str) -> list[Node]                       # document order
def slide_range(nodes: list[Node], node: Node) -> tuple[int, int]
def large_images(slide_text: str) -> list[tuple[int, int]]   # (start, end) of each src value longer than 1000 chars, document order
def hide_images(slide_text: str) -> str                  # replaces the Nth large src by data:ref:img-N (N from 1)
# deck/read.py
def get_slide(file: str, slide_id: str) -> str
```
Command: `mcp-htmleditor get-slide FILE ID` prints the slide HTML (`click.echo`). Same `deck_command` decorator and file argument rule as `outline` (US-0035).

Scanner contract:
- `scan(text)` returns nodes in document order. Start tag offsets come from `HTMLParser.getpos()` converted through a line start table (`\n` only, as `HTMLParser` counts); the end tag end offset comes from the next `>`. `convert_charrefs=False`.
- An end tag pops the stack to the nearest open element of the same name (ignored if none), so an unclosed `<p>` inside a slide does not move the slide end.
- Content of `<script>` and `<style>` is raw text (`</article>` inside a script string is not an end tag; comments are skipped).
- A slide's range is `[start, end_end)` of its element node. Bridge: a BeautifulSoup `Tag` maps to the node with `(line, col) == (tag.sourceline, tag.sourcepos)`.
- Large image: an `img` element whose `src` is a `data:` address longer than 1 000 characters. N counts from 1, in document order, within that slide. Only the `src` value is replaced; the rest of the slide text is byte identical to the file.

Messages: `Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2` (all ids, in order, slide ids as in the outline, comma space separated); `get_slide needs a presentation: <file>` (any file with no slide); `File not found: <file>`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/scan.py` | create: `Scanner`, `Node`, `scan()`, large image listing and `data:ref:img-N` substitution |
| `src/mcp_htmleditor/deck/read.py` | modify: add `get_slide()` |
| `src/mcp_htmleditor/cli.py` | modify: add the `get-slide` command |
| `tests/test_deck_get_slide.py` | create |
| `.agent_docs/agent-editing.md` | create: formats, scanner rules, gotchas |

### Existing patterns
- `src/mcp_htmleditor/deck/__init__.py` (US-0035): `load_deck`, `Deck.slides`, `slide_id`.
- `src/mcp_htmleditor/export/to_pptx.py:272` `find_slides`.
- `src/mcp_htmleditor/http_server.py:464-476` `_strip_editor_artifacts` shows the serializing parse this story deliberately avoids.
- Fixtures and `run_cli`: `tests/deck_support.py` (US-0035).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures (generated by `tests/deck_support.py` from the real `templates/bootstrap/*.html`, never committed; no clock, `os.utime(path, (1_000_000_000, 1_000_000_000))` to force modification times):
- DECK-EI: an Euro-Information presentation (real EI bootstrap CSS and cover), no inline colour outside the Euro-Information palette, no remote image, no template text, consistent counters, 8 slides titled `Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`, ids `slide-0` to `slide-7`; slide 3 holds a 1 500 character `data:image/png;base64` image; slides 1 to 6 carry eyebrow `Cat · Slide 0N / 08` (N = index + 1) and page element N (`.slide-foot-page`, so slides 1 to 6 hold 2 to 7); slide 7 is a section slide without foot; `const TOTAL = 8;` and `const slideNames = [ ... ];` consistent.
- DECK-CARBON: a Carbon presentation of 5 slides titled `Intro`, `Offre`, `Chiffres`, `Plan`, `Fin`, eyebrow `Section · Slide 0N / 05`, footers `Slide 1 / 5` to `Slide 5 / 5` (`.slide-footer-right`), TOTAL 5, slideNames 5 entries.
- DECK-MED: a medical presentation of 6 slides: cover (`data-slide-type="title"`) then content slides with `.med-strip` children carrying `w-50`, a tiny PNG, a non empty `.med-source`, `.slide-foot-page`.
- DOC-PERSO: `document-perso-empty.html` with the article body replaced by `h1.doc-title` "Rapport", `h1.doc-h1` "Contexte", `h2.doc-h2` "Périmètre", `h1.doc-h1` "Risques".

Large image helper: DECK-EI with `image_chars=2_000_000` is the "2 MB" variant.

### SPEC-0007/E2E-012: Unknown slide for get_slide
- Level E2E; Driver CLI; Location `tests/test_deck_get_slide.py`
- Given DECK-CARBON
- When the user runs `get-slide DECK-CARBON slide-9`
- Then the error output is `error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2, slide-3, slide-4` and the exit status is 1 (standard output empty)

### SPEC-0007/E2E-031: Large image
- Level E2E; Driver CLI; Location `tests/test_deck_get_slide.py`
- Given DECK-EI where slide 3 holds an image of 2 MB
- When the user runs `outline` and `get-slide DECK-EI slide-3`
- Then the outline is under 20 000 bytes and the slide HTML under 5 000 bytes

### Additional tests (same file)
- `get-slide DECK-EI slide-3` (normal 1 500 character image): output starts with `<article`, contains `id="slide-3"`, contains `data:ref:img-1`, contains no `base64`, does not contain `Contexte` (the title of slide 2); the output equals the file slice of the slide with only the `src` value changed (compare against a plain substring slice computed in the test).
- Two large images in one slide give `data:ref:img-1` then `data:ref:img-2` in document order; an image whose data address is exactly 1 000 characters is not replaced; 1 001 is.
- Scanner invariants: for every `templates/**/*.html` (bootstrap and reference), every BeautifulSoup tag has a scanner node at `(sourceline, sourcepos)` with the same tag name; unclosed `<p>` inside a slide does not move the slide end; a `<script>` containing the text `</article>` does not end the slide; a CRLF file keeps its `\r\n` inside the returned slide text; a comment between slides is not part of any slide range.
- `get-slide DOC-PERSO slide-0`: stderr `error: get_slide needs a presentation: <DOC-PERSO path as given>`, exit 1. `get-slide ghost.html slide-0`: `error: File not found: ghost.html`, exit 1.

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/http_server.py`, `src/mcp_htmleditor/export/*`.
- Dependencies not to add: none.
- Patterns to avoid: `str(tag)` or any BeautifulSoup serialization for output (reformats); regular expressions over raw HTML to find slide ends; stdout inside `deck/`.
- Scope boundary: no write path, no tool.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: US-0035 tests unchanged; existing suites unchanged.
- [ ] Docs updated: `.agent_docs/agent-editing.md` created (formats of outline and get-slide, scanner rules, closing rule for unclosed tags, bridge key, gotchas).
- [ ] Self review: full at tier 2.
- [ ] This story registers no MCP tool; `skill/core.md` is not touched.
- [ ] One commit `US-0036: `get-slide` on the command line and the scanner`, body `Spec: SPEC-0007` and the requirement ids FR-NEW-002.
