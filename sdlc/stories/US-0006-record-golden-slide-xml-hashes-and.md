# US-0006: Record golden slide XML hashes and detector table

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0005
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Records, on the unchanged code, the two characterization baselines that guard every later step of SPEC-0012: the SHA-256 of every slide XML part exported from ten templates and reference decks (DT-001), and the table of results of the two charter detectors on the eight bootstrap templates (DT-002). No production code changes.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-007 (partial: the exporter half: slide XML of ten templates and reference decks is byte identical to the recorded hashes. The invariance of the other observable outputs is carried by the unmodified suite and closed by US-0020): The Editor SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, and the XML of every exported slide of the ten templates and reference decks (DT-001) SHALL be byte identical.
- SPEC-0012/DR-001 (partial: characterization only: the detector table that the registry must reproduce is recorded here, the registry itself is US-0007): The Editor SHALL describe each of the eight charters once, in `src/mcp_htmleditor/export/charters.py`, as a record with the fields `key`, `kind` (`presentation`, `document`, `mail` or `website`), `template` (path under a templates directory), `description`, `css_tokens` (substrings searched in the style text), `css_classes` (class names searched in the markup), `layout_set` (`carbon`, `ei`, `medical` or none) and `docx_key` (key of a `reference_docx` charter, or none). Presentation values: medical (`--med-teal`; `med-rule`), ei (`--ei-blue`; `slide-inner`), carbon (`--ibm-blue`, `--cds-`; `slide-header`). Document, mail and website charters carry empty `css_tokens` and `css_classes`. `docx_key` is `perso` for `doc-perso`, `ei` for `doc-ei`, and none for all other charters, including `mail` and `website`. The record class is `CharterSpec` and the tuple is `REGISTRY` (not `Charter` or `CHARTERS`, which `reference_docx.py:196,291` already defines). `charters.py` imports nothing from `templates.py`.
- SPEC-0012/DR-003 (partial: characterization only: `detect_theme` results recorded here, the rewrite is US-0007): `detect_theme(soup)` SHALL keep returning `Theme` objects, reading only the presentation charters' `css_tokens` and `css_classes` from `REGISTRY`, evaluated in the order medical, ei, carbon, then generic, and SHALL return, for every input, what it returns today; `charter_for(key)` SHALL return the same result for every input (it resolves `perso` and `ei`, strips and lowercases the key, and returns none otherwise) using the `docx_key` fields: it returns the existing `reference_docx.PERSO` and `reference_docx.EI` objects (identity kept), `reference_docx.CHARTERS` stays a mapping of `Charter` and `charter_keys()` stays `("perso", "ei")`; `reference_docx.py` imports `charters.py` and `charters.py` imports nothing from `reference_docx.py`.

## Independent Test

`make test ARGS='tests/test_export_golden.py tests/test_charter_detection.py'`
- Observable: pytest exit code and test ids. Expected: 10 golden cases (one per file of DT-001), 8 `detect_theme` cases, 8 `detectTemplate` browser cases, all passed, on the code of `main` as it is when this story starts.
- Assertions that do not mock the story's own output: the hashes are SHA-256 of raw bytes read from the zip produced by the real `to_pptx` (not of the zip file); the browser half runs the real `slide-layouts.js` in Chromium.
- Determinism proof: the recording is made twice on the unchanged code and the two JSON files are byte identical (`diff` empty). If a part differs between runs, STOP: report BLOCKED, because design.md Section 7 would need a declared exception (the design file is not edited by this story).
- RED evidence (characterization tests pass on first run, so RED is shown by mutation): change one hex digit of one hash in `tests/testdata/pptx_slide_hashes.json` and one value in `tests/testdata/detector_table.json`; the matching cases fail; restore both.

## Design excerpt

### Decisions

- DEC-003 (SPEC-0012): keep the JavaScript detector and test parity, instead of generating it from the registry. Alternatives considered: generating `slide-layouts.js` fragments at build time (adds a generated file and a build step). Rationale: no build step exists. Implemented by: DR-001, DT-002.

### Data model

`tests/testdata/pptx_slide_hashes.json`: `{"<template path relative to the repo root>": {"ppt/slides/slide1.xml": "<64 hex sha256>", ...}}` for the ten files of DT-001 (`templates/bootstrap/slides-ei-empty.html`, `templates/bootstrap/slides-empty.html`, `templates/bootstrap/slides-medical-empty.html`, `templates/reference/slides/euro-information.html`, `ibm-carbon.html`, `medical.html`, `example-ei-complete.html`, `example-medical-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html`). One entry per slide part, key order sorted.

`tests/testdata/detector_table.json`: `{"<template key>": {"detect_theme": "<Theme.key>", "detectTemplate": "<template key>"}}` for the eight keys `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`. Values are recorded by running the unchanged code (a small recording run, see Contracts), then compared with the facts of DT-002 below; they are never typed by hand.

### Contracts

- Exporter entry point used by DT-001: `mcp_htmleditor.export.to_pptx.to_pptx(input_html: str, output_pptx: str) -> ExportReport`.
- Python detector: `mcp_htmleditor.export.pptx_style.detect_theme(soup: BeautifulSoup) -> Theme`, compared on `Theme.key`.
- Browser detector: `detectTemplate(doc)` of `src/mcp_htmleditor/static/slide-layouts.js:12`, run in Chromium after `page.add_script_tag(path=...)` and `page.set_content(<template html>)`, evaluated as `detectTemplate(document)`.
- Template files: `mcp_htmleditor.templates.template_path(key)` for the eight keys (as `tests/test_medical_template.py:23`).
- Regeneration of the two JSON files is an explicit, documented act: each test module docstring states the one line command (an `if __name__ == "__main__"` recorder inside the test module, run through `uv run python tests/test_export_golden.py --record`). The tests themselves never write the files.

### Paths

| Path | Action |
|---|---|
| `tests/test_export_golden.py` | create (DT-001; includes the `--record` entry point) |
| `tests/testdata/pptx_slide_hashes.json` | create (golden hashes) |
| `tests/test_charter_detection.py` | create (DT-002, Python and browser halves) |
| `tests/testdata/detector_table.json` | create (recorded detector table) |

### Existing patterns

- `tests/test_export_pptx.py:32-38` (imports of `to_pptx`, `find_slides`, `SLIDE_W_IN`, `SLIDE_H_IN`, `_column_widths`).
- `tests/test_medical_template.py:23-24, 202-204` (`template_path`, `detect_theme`, slicing `slide-layouts.js` between `function detectTemplate` and `function getLayouts`).
- `tests/test_website_template_e2e.py` (Playwright fixture pattern, Chromium installed by `make sync`).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0012/DT-001: Exported slide XML is identical

- Level: integration; Driver: pytest, `to_pptx` on 10 files; Location: `tests/test_export_golden.py`
- **Validates:** SPEC-0012/DR-007 on the exporter
- **Given** golden hashes, committed under `tests/testdata/`, of the raw bytes of the slide XML parts, read from the zip (not of the zip file), recorded from the code before the change and confirmed identical on a second run of the unchanged code (an attribute that differs between runs is listed in Section 7 as a declared exception), of the slide XML parts (`ppt/slides/slide*.xml`) of the PPTX exported from `templates/bootstrap/slides-ei-empty.html`, `slides-empty.html`, `slides-medical-empty.html` and `templates/reference/slides/euro-information.html`, `ibm-carbon.html`, `medical.html`, `example-ei-complete.html`, `example-medical-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html`
- **When** the test exports each file
- **Then** every part hash equals its golden hash

Read each part with `zipfile.ZipFile(out).read(name)` and hash the raw bytes with `hashlib.sha256`; compare the dict of part name to hash with the golden entry of that file (same set of part names, same hashes). Parametrize on the ten paths.

### SPEC-0012/DT-002: Detectors keep their results, and Python and JavaScript are compared

- Level: integration + E2E; Driver: pytest, Playwright for `detectTemplate`; Location: `tests/test_charter_detection.py`
- **Validates:** SPEC-0012/DR-001, SPEC-0012/DR-003
- **Given** the eight bootstrap templates, and a table of expected results recorded from the code before the change (step 1) for `detect_theme` (a `Theme` key) and for `detectTemplate` run in the browser (a template key)
- **When** both detectors are applied to each template after the change
- **Then** every result equals the recorded table
- **And** the table contains the facts known today: `detectTemplate` returns `ei` for `ei` and `doc-ei`, `medical` for `medical`, `carbon` for the five others; `detect_theme` returns the EI, Carbon and medical themes for the three presentations, the generic theme for `doc`, `doc-perso` and `mail`, the EI theme for `doc-ei` (its style holds `--ei-blue`) and the Carbon theme for `website`

Data (the facts the recorded table must contain, asserted explicitly in the test in addition to the equality with the JSON):

| key | `detect_theme` (`Theme.key`) | `detectTemplate` |
|---|---|---|
| ei | the EI theme | ei |
| carbon | the Carbon theme | carbon |
| medical | the medical theme | medical |
| doc | the generic theme | carbon |
| doc-perso | the generic theme | carbon |
| doc-ei | the EI theme (its style holds `--ei-blue`) | ei |
| mail | the generic theme | carbon |
| website | the Carbon theme | carbon |

`Theme.key` values are read from `THEME_EI`, `THEME_CARBON`, `THEME_MEDICAL`, `THEME_GENERIC` in `pptx_style.py` (l.316-361), not retyped. The test fails if the recorded table differs from this table.

## Constraints

- Files not to touch: everything under `src/`, every existing test file, `pyproject.toml`, `Makefile`.
- No new dependency; Playwright and Chromium are already installed by `make sync`.
- The golden files are recorded from `main` before any other SPEC-0012 change, never regenerated afterwards to make a later story pass.
- Scope boundary: the registry and the splits are US-0007 onwards.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing suite passes unmodified via `make test` (278 tests at the start of this work); tolerated exceptions: none.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none.
- [ ] Docs updated: none in this story (design assigns the documentation to US-0018, US-0019, US-0020).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0006: Record golden slide XML hashes and detector table`, body `Spec: SPEC-0012` and the requirement ids (DR-007, DR-001, DR-003).
