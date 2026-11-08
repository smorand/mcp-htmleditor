# US-0096: Vector figures named in the PPTX warnings

> Spec: SPEC-0016 (sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

The PPTX export drops every vector figure, an inline `<svg>` without a word and a vector image with two warnings
carrying a Python object address. After this story each vector figure inside a slide gets exactly one warning that
names its slide and recommends PNG, the shell icons stay silent, and the exported slides are byte identical.

## Requirements covered

- SPEC-0016/BR-005: WHEN the PPTX export meets an inline `<svg>` vector figure in slide `N` THE exporter SHALL add the warning `Slide N: balise <svg> en ligne ignoree, l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG.`
- SPEC-0016/BR-006: WHEN the PPTX export meets an `<img>` vector figure in slide `N` THE exporter SHALL add exactly one warning for it, `Slide N: image SVG ignoree (<src>), l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG.`, and no other warning about that image.
- SPEC-0016/BR-007: The PPTX exporter SHALL NOT warn about an `<svg>` outside every slide, an `<svg>` inside another `<svg>`, or an `<svg>` or `<img>` inside a `<button>`, `<script>`, `<template>`, `<noscript>` or `<select>`.
- SPEC-0016/BR-008: The PPTX export of a deck holding vector figures SHALL produce the same slides, the same slide count and the same exit status as today.

Definitions and business rules (spec, verbatim): "A vector figure is, inside a slide: an `<svg>` element that is not
inside another `<svg>`; an `<img>` whose `src`, cut at the first `?` and lowercased, ends with `.svg`; an `<img>`
whose `src` lowercased starts with `data:image/svg`. A slide is an exported slide element, or the body when the
document has none and is exported as one slide. The slide number `N` is the 1 based position of the slide in the
export." One warning per occurrence, in document order; the CLI prints each as `Attention: <warning>` on stderr; the
agent tool returns it in its warnings. `<src>` is the attribute value cut to its first 60 characters. The two
warnings of today (`Image non decodable ignoree: ...`, `Image non inseree (...)`) are not emitted for a vector figure;
they stay for any other unreadable image. Only the warning list changes; the slide XML is byte identical.

## Independent Test

`make test ARGS='-k pptx_vectors'`: BT-002 red before (no inline warning, four Python object warnings), green after;
then `make test ARGS='-k "pptx or medical or docx"'` green with no edited existing test.

## Design excerpt

### Decisions
- DEC-003 (SPEC-0016): "Vector figures are found by a pure pre pass, `vector_figure_warnings(slide, number)` in a new module `export/pptx_vectors.py`, called by `to_pptx` once per slide before its build, warnings appended with `report.warn` in document order. The advice sentence is the DOCX constant `SVG_ADVICE` imported from `export/to_docx.py:51`."
- DEC-004 (SPEC-0016): "`pptx_images._image_source` returns `None` for a vector `src` before any decoding or path lookup, with no warning. Every caller passes an `<img>` `src`, so this silences exactly the vector images that the pre pass warns."
- DEC-005 (SPEC-0016): "BT-013's byte identity of `V`'s `ppt/slides/slide1.xml` is checked against a sha256 constant in `tests/test_export_pptx_vectors.py`, recorded during the RED run on the unfixed code and copied into the test."

### Contracts
`src/mcp_htmleditor/export/pptx_vectors.py` (new):

```python
from .to_docx import SVG_ADVICE

VECTOR_ADVICE = SVG_ADVICE
SILENT_ANCESTORS = frozenset({"button", "script", "template", "noscript", "select"})
SRC_PREVIEW_CHARS = 60


def is_vector_src(src: str) -> bool: ...
def vector_figure_warnings(slide: Tag, number: int) -> list[str]: ...
```

- inline text: `f"Slide {number}: balise <svg> en ligne ignoree, l'export PPTX ne convertit pas les vecteurs. {VECTOR_ADVICE}"`
- image text: `f"Slide {number}: image SVG ignoree ({src[:SRC_PREVIEW_CHARS]}), l'export PPTX ne convertit pas les vecteurs. {VECTOR_ADVICE}"`
- walk `slide.find_all(["svg", "img"])` in document order; an `<svg>` with an `<svg>` ancestor is skipped; any figure with an ancestor (strictly inside the slide) whose name is in `SILENT_ANCESTORS` is skipped.

`export/to_pptx.py` loop (`:111` to `:113`): `for warning in vector_figure_warnings(article, index + 1): report.warn(warning)` before `_SlideBuilder(...).build()`. The no slide branch (`:99` to `:105`) keeps its warning first; the body is then slide 1.

`export/pptx_images.py` `_image_source` (`:96`): first statement `if is_vector_src(src): return None`.

Unchanged and already forwarding: CLI `cli.py:531` (`Attention: <warning>` on stderr), MCP tool `export` (`mcp_server.py:379`, answer `{"ok": True, "output": ..., "warnings": ...}`).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/export/pptx_vectors.py` | create |
| `src/mcp_htmleditor/export/to_pptx.py` | modify: pre pass per slide |
| `src/mcp_htmleditor/export/pptx_images.py` | modify: silent vector `src` |
| `tests/test_export_pptx_vectors.py` | create |
| `.agent_docs/architecture.md` | modify: export pipeline, one line on the vector pre pass and its silence in `_image_source` |

### Existing patterns
- `ExportReport.warn` and `to_pptx` in process: `tests/test_export_pptx.py:351`.
- DOCX vector detection, the model to mirror: `export/to_docx.py:249` `svg_warnings`.
- CLI in a child process: `tests/test_skill_shipped.py` (`sys.executable -m mcp_htmleditor`).
- MCP stdio session: `tests/stdio_support.py` `run_session`, `tool_request`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Location `tests/test_export_pptx_vectors.py`. `SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="red"/></svg>'`.
`V`: `templates/bootstrap/slides-empty.html` copied to `tmp_path/svg.html`, its slide body starting with
`SVG + '<img src="fig.svg" alt="f"><img src="data:image/svg+xml;base64,' + base64(SVG) + '" alt="d">'`, and
`tmp_path/fig.svg` holding `SVG`. `ADVICE = "l'export PPTX ne convertit pas les vecteurs. Regle: figures en PNG, jamais en SVG."`

### SPEC-0016/BT-002: Vector figures named in the PPTX warnings
- Level / Driver: functional; child process `[sys.executable, "-m", "mcp_htmleditor", "export", "pptx", V, out.pptx]`
- Then exit status 0, stdout ends with `Done. 1 slide(s) exportee(s).`, and the stderr lines starting with `Attention: ` are exactly, in order:
  `Attention: Slide 1: balise <svg> en ligne ignoree, ` + ADVICE,
  `Attention: Slide 1: image SVG ignoree (fig.svg), ` + ADVICE,
  `Attention: Slide 1: image SVG ignoree (data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My), ` + ADVICE
- And stderr contains neither `Image non decodable` nor `Image non inseree`
- Red before the fix because: no inline warning, and four `Image non ...` warnings carrying `<_io.BytesIO object at 0x...>`.

### SPEC-0016/BT-013: Vector figures that are not content stay silent
- Given `C` the Carbon bootstrap unchanged (shell icons only); `B` a copy of `V` whose inline `<svg>` is wrapped in `<button>`; `N` a copy of `V` whose inline `<svg>` holds a second `<svg>`
- When the three are exported with `to_pptx` in process
- Then `C`'s `report.warnings` hold no string containing `SVG` or `svg`; `B`'s are exactly the two `image SVG ignoree` warnings of BT-002 (without `Attention: `); `N`'s are exactly the three warnings of BT-002
- And `V`'s export has 1 slide and the sha256 of its `ppt/slides/slide1.xml` equals the constant recorded on the unfixed exporter (DEC-005)

### SPEC-0016/BT-014: Numbering, order and case of vector warnings
- Given a three slide Carbon deck (the bootstrap's slide block repeated, `TOTAL` 3): slide 1 no figure, slide 2 `SVG` then `<img src="Fig.SVG?v=2">`, slide 3 `SVG`
- When exported with `to_pptx`
- Then `report.warnings` equal, in order: `Slide 2: balise <svg> en ligne ignoree, ` + ADVICE, `Slide 2: image SVG ignoree (Fig.SVG?v=2), ` + ADVICE, `Slide 3: balise <svg> en ligne ignoree, ` + ADVICE, and nothing else

### SPEC-0016/BT-015: Warnings through the agent tool
- Level / Driver: functional; MCP stdio session (`tests/stdio_support.py`)
- When the tool `export` is called with `{"file": V, "format": "pptx", "output": out.pptx}`
- Then the answer has `"ok": true` and its `warnings` list equals the three BT-002 warnings without the `Attention: ` prefix

### SPEC-0016/BT-034: Other unreadable images keep today's warnings
- Given a Carbon bootstrap copy whose slide holds `<img src="broken.png">` and `broken.png` holding the bytes `not an image`
- When exported with `to_pptx`
- Then the warnings are one starting with `Image non decodable ignoree: ` and one starting with `Image non inseree (`, as today, and none contains `SVG`

### SPEC-0016/BT-033: Decks without vector figures still warn nothing
- When `tests/test_medical_template.py::test_medical_decks_export_every_slide_without_warning` and the five `report.warnings == []` tests of `tests/test_export_pptx.py` (`:351`, `:368`, `:534`, `:807`, `:1075`) run
- Then they pass unchanged

### SPEC-0016/BT-035: DOCX vector diagnostics unchanged
- When `tests/test_export_docx.py::test_to_docx_warns_about_svg_figures` runs
- Then it passes unchanged

## Constraints

- Files not to touch: the seven `SKIP_TAGS` walkers (`pptx_flow.py`, `pptx_text.py`, `pptx_blocks.py`, `pptx_arch.py`), `to_docx.py` (only imported from), every existing test, `tests/testdata/pptx_slide_hashes.json`.
- Dependencies not to add: none.
- Patterns to avoid: deduplicating identical warnings (spec: one per occurrence); warning about elements outside the slide.
- Scope boundary: the export of `ibm-carbon.html` gains one BR-005 warning (it holds one inline `<svg>` in a slide); no test asserts its warnings, leave it so.

## Definition of done

- [ ] RED evidence recorded for BT-002, BT-013 (and the slide1.xml hash taken on the unfixed code), BT-014, BT-015 before the production code, in `.implement/US-0096-red.log`.
- [ ] Every acceptance test above green; `make check` green (typecheck strict on the new module); main stays green after the squash.
- [ ] Non regression: golden hashes (`tests/test_export_golden.py`) unchanged; BT-033, BT-034, BT-035.
- [ ] Docs updated: `.agent_docs/architecture.md`.
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0096: Vector figures named in the PPTX warnings`, body `Spec: SPEC-0016` and BR-005, BR-006, BR-007, BR-008.
