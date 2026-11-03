# US-0007: Charter registry, templates and detectors read it

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0006
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Creates the single charter registry `export/charters.py` and makes `TEMPLATES`, `detect_theme` and `charter_for` read it, with no behavior change. DT-002 (US-0006) proves the detectors still give the recorded results.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-001: The Editor SHALL describe each of the eight charters once, in `src/mcp_htmleditor/export/charters.py`, as a record with the fields `key`, `kind` (`presentation`, `document`, `mail` or `website`), `template` (path under a templates directory), `description`, `css_tokens` (substrings searched in the style text), `css_classes` (class names searched in the markup), `layout_set` (`carbon`, `ei`, `medical` or none) and `docx_key` (key of a `reference_docx` charter, or none). Presentation values: medical (`--med-teal`; `med-rule`), ei (`--ei-blue`; `slide-inner`), carbon (`--ibm-blue`, `--cds-`; `slide-header`). Document, mail and website charters carry empty `css_tokens` and `css_classes`. `docx_key` is `perso` for `doc-perso`, `ei` for `doc-ei`, and none for all other charters, including `mail` and `website`. The record class is `CharterSpec` and the tuple is `REGISTRY` (not `Charter` or `CHARTERS`, which `reference_docx.py:196,291` already defines). `charters.py` imports nothing from `templates.py`.
- SPEC-0012/DR-002: `templates.TEMPLATES` SHALL remain a `dict[str, tuple[str, str]]` equal, key by key, in the same order, to the dict it is today, built as `{c.key: (c.template, c.description) for c in REGISTRY}`.
- SPEC-0012/DR-003: `detect_theme(soup)` SHALL keep returning `Theme` objects, reading only the presentation charters' `css_tokens` and `css_classes` from `REGISTRY`, evaluated in the order medical, ei, carbon, then generic, and SHALL return, for every input, what it returns today; `charter_for(key)` SHALL return the same result for every input (it resolves `perso` and `ei`, strips and lowercases the key, and returns none otherwise) using the `docx_key` fields: it returns the existing `reference_docx.PERSO` and `reference_docx.EI` objects (identity kept), `reference_docx.CHARTERS` stays a mapping of `Charter` and `charter_keys()` stays `("perso", "ei")`; `reference_docx.py` imports `charters.py` and `charters.py` imports nothing from `reference_docx.py`.

## Independent Test

`make test ARGS='tests/test_charters.py tests/test_charter_detection.py tests/test_templates.py tests/test_export_docx.py tests/test_medical_template.py tests/test_export_golden.py'`
- Observable: pytest result. Expected: all passed, including the DT-002 table and DT-001 hashes recorded by US-0006 (not edited), and DT-010 (new).
- Non mock assertions: `inspect.getsource` of the real `detect_theme` and `templates` module; `charter_for("perso") is reference_docx.PERSO` identity; `list(TEMPLATES.items())` equal to the literal list copied from `git show HEAD:src/mcp_htmleditor/templates.py` (key order and values).
- RED evidence: DT-010 fails on the current code (`--med-teal` is in the body of `detect_theme`; `TEMPLATES` is a literal dict).

## Design excerpt

### Decisions

- DEC-003 (SPEC-0012): keep the JavaScript detector and test parity, instead of generating it from the registry. Alternatives considered: generating `slide-layouts.js` fragments at build time (adds a generated file and a build step). Rationale: no build step exists. Implemented by: DR-001, DT-002.

### Data model

`CharterSpec` (frozen dataclass) in `src/mcp_htmleditor/export/charters.py`, fields in this order: `key: str`, `kind: str` (`presentation`, `document`, `mail` or `website`), `template: str`, `description: str`, `css_tokens: tuple[str, ...]`, `css_classes: tuple[str, ...]`, `layout_set: str | None`, `docx_key: str | None`. `REGISTRY: tuple[CharterSpec, ...]`, in this order:

| key | kind | template | css_tokens | css_classes | layout_set | docx_key |
|---|---|---|---|---|---|---|
| ei | presentation | bootstrap/slides-ei-empty.html | `--ei-blue` | `slide-inner` | ei | none |
| carbon | presentation | bootstrap/slides-empty.html | `--ibm-blue`, `--cds-` | `slide-header` | carbon | none |
| medical | presentation | bootstrap/slides-medical-empty.html | `--med-teal` | `med-rule` | medical | none |
| doc | document | bootstrap/document-empty.html | none | none | none | none |
| doc-perso | document | bootstrap/document-perso-empty.html | none | none | none | perso |
| doc-ei | document | bootstrap/document-ei-empty.html | none | none | none | ei |
| mail | mail | bootstrap/mail-empty.html | none | none | none | none |
| website | website | bootstrap/website-empty.html | none | none | none | none |

`description` of each record is the second element of the corresponding tuple of the current `TEMPLATES` literal (`templates.py:39-73`), copied verbatim (accents included). `layout_set` is `none` for the documents because it names a slide layout set; no detector reads it (the JavaScript detector stays, DEC-003).

### Contracts

- New: `mcp_htmleditor.export.charters.CharterSpec`, `mcp_htmleditor.export.charters.REGISTRY`. Not `Charter` or `CHARTERS` (already defined by `reference_docx.py:196,291`).
- `charters.py` imports nothing from `templates.py`, nor from `reference_docx.py` (stdlib only).
- Kept: `mcp_htmleditor.templates.TEMPLATES: dict[str, tuple[str, str]]` built as `{c.key: (c.template, c.description) for c in REGISTRY}`; `template_path`, `list_templates`, `template_search_path` unchanged (`cli.py:51`, `cli.py:67`).
- Kept: `pptx_style.detect_theme(soup) -> Theme` returning `THEME_MEDICAL`, `THEME_EI`, `THEME_CARBON`, `THEME_GENERIC` (same objects), evaluated medical, ei, carbon, generic, reading only presentation charters' `css_tokens` (substring of `stylesheet_text(soup)`) and `css_classes` (`soup.find(class_=...)`).
- Kept: `reference_docx.charter_for(key: str | None) -> Charter | None` (empty key gives none; strips and lowercases; returns `reference_docx.PERSO` / `EI` by identity), `reference_docx.CHARTERS` a mapping of `Charter`, `charter_keys() == ("perso", "ei")`. `reference_docx.py` imports `charters.py`.

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/export/charters.py` | create |
| `src/mcp_htmleditor/templates.py` | edit: `TEMPLATES` comprehension over `REGISTRY` (l.38-73) |
| `src/mcp_htmleditor/export/pptx_style.py` | edit: `detect_theme` (l.377-386) reads the registry |
| `src/mcp_htmleditor/export/reference_docx.py` | edit: `charter_for` (l.299-312) reads `docx_key` |
| `tests/test_charters.py` | create (DT-010) |

### Existing patterns

- `src/mcp_htmleditor/export/pptx_style.py:377-386` (current `detect_theme`, the priority order to keep).
- `src/mcp_htmleditor/export/reference_docx.py:291-312` (`CHARTERS`, `charter_keys`, `charter_for`).
- `tests/test_templates.py`, `tests/test_export_docx.py:207-213` (existing guards, unmodified).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0012/DT-010: Registry is the only source

- Level: unit (source inspection); Driver: pytest, `inspect.getsource`; Location: `tests/test_charters.py`
- **Asserts:** the three strings `--med-teal`, `--ei-blue`, `--ibm-blue` do not appear in the body of `detect_theme`; `TEMPLATES` is built by a comprehension, not a dict literal
- **Method:** source inspection of the two functions

Also assert (same file, same story): `[c.key for c in REGISTRY] == ['ei','carbon','medical','doc','doc-perso','doc-ei','mail','website']`; `charter_for('perso') is reference_docx.PERSO`; `charter_for(' EI ') is reference_docx.EI`; `charter_for('mail') is None`; `charter_for('website') is None`; `charter_for(None) is None`; `charter_keys() == ('perso', 'ei')`.

## Constraints

- Files not to touch: `to_docx.py`, `slide-layouts.js`, `cli.py`, every existing test.
- `detect_theme` returns, for every input, what it returns today; evaluation order medical, ei, carbon, generic.
- No import cycle: `charters.py` imports no project module.
- One commit per switched consumer is allowed inside the story branch (templates, then `detect_theme`, then `charter_for`, suite green after each), squashed at merge.
- Scope boundary: the JavaScript detector stays as is (DEC-003); documentation of the registry is added by US-0019.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing suite passes unmodified via `make test` (278 tests at the start of this work); tolerated exceptions: none.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none.
- [ ] Docs updated: none in this story (the `charters.py` entry of `.agent_docs/architecture.md` is written by US-0019).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0007: Charter registry, templates and detectors read it`, body `Spec: SPEC-0012` and the requirement ids (DR-001, DR-002, DR-003).
