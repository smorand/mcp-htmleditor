# US-0045: Template, new and export services on the command line

> Spec: SPEC-0007 (sdlc/specs/SPEC-0007-agent-editing-tools/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0034
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

Moves the logic of `templates`, `new` and `export` into one service layer so the tool surface can reuse it, and gives their failures the English `error: <message>` form with exit status 1.

## Requirements covered

- SPEC-0007/FR-NEW-015 (partial: command line side and services; the tools arrive in US-0046): WHEN an agent calls `list_templates`, `new_file` or `export` THE Editor SHALL give the results of the command line `templates`, `new` and `export`.
- SPEC-0007/FR-NEW-016 (partial: command line error lines of `new` and `export`): The Editor SHALL give the same result for each of these operations through the command line and through the agent tool surface, the tool surface returning an error whose message is the command line error line without its `error: ` prefix.

## Independent Test

`make test ARGS='-k deck_tools'`: `mcp-htmleditor new x a.html` prints `error: Unknown template "x". Valid templates: ei, carbon, medical, doc, doc-perso, doc-ei, mail, website` on stderr with exit 1 and empty stdout; `new doc a.html` then `export docx a.html a.docx` creates a real `a.docx` (a zip with `word/document.xml`); success lines are the existing ones.

## Design excerpt

### Decisions
- DEC-009 (SPEC-0007): "`new` and `export` move to the same path, so their errors become the English FR-NEW-015 ones." No existing test asserts the French `new` messages or click's `Error:` prefix.
- DEC-016 (SPEC-0007): every failure path gives one `error:` line, never a traceback.
- Skill rule: `trace_span` on file mutations: `file.write` with `file.path`, `template.key`, `file.size`.
- Python skill: services return values, only `cli.py` echoes.

### Data model
`ExportOutcome` frozen dataclass with `__slots__`: `output: str`, `warnings: list[str]`, `slide_count: int`, `charter: str | None`, `reference_docx: str | None`. Listing: `[{"key":"ei","description":"..."}]` from `templates.list_templates()` in registry order.

### Contracts
```python
# deck/tools.py
def template_listing() -> list[dict[str, str]]
def create_file(template: str, file: str) -> Path
def export_file(file: str, fmt: str, output: str) -> ExportOutcome
```
Messages (English, `DeckError`): 
- `Unknown template "x". Valid templates: ei, carbon, medical, doc, doc-perso, doc-ei, mail, website` (keys from the registry, registry order);
- `File already exists: <file>` (checked after the template key; `create_file` never overwrites);
- `Template file is missing: <detail>` when the registered template file cannot be found;
- `Unknown export format "foo". Valid formats: pptx, docx` (checked before the input file);
- `File not found: <file>` (input of `export`);
- `No slide exported: check that the document has data-type="slide" elements.` (pptx with zero slides; the export warnings are logged with `logger.warning` before raising);
- `pandoc not found in PATH: install pandoc to export to DOCX.`; `pandoc failed: <stderr or "exit code N">`; `Cannot write <file>: <reason>` for a failed copy.
`create_file`: creates parent directories, copies the template under `trace_span("file.write", {"file.path", "template.key"})` setting `file.size`, logs `Created %s from template %s`, returns the path. The path guard of `patch` is not applied here.
`export_file`: dispatches to `export.to_pptx.to_pptx` or `export.to_docx.to_docx` (lazy imports), returns the outcome (`slide_count` is 0 for docx, `charter` and `reference_docx` from the docx result).

Commands (all use `deck_command`; file arguments are `click.Path(dir_okay=False)` without `exists=True`; `export` FORMAT is a plain string argument, no `click.Choice`):
- `templates`: prints the existing lines (`Templates disponibles (mcp-htmleditor new <key> <fichier>):`, blank line, `  <key:<8> <description>` per template), data from `template_listing()`.
- `new TEMPLATE OUTPUT_FILE [--serve] [--port] [--host] [--no-browser]`: calls `create_file`, then prints the existing success line `Créé: <dest>  (template: <template>)`; `--serve` behaves as before.
- `export FORMAT INPUT_FILE OUTPUT_FILE`: calls `export_file`, then prints after it returns: `Exporting <input> → <output> (PPTX)` (or `(DOCX via pandoc)`), the `Attention: <warning>` lines on stderr, then `Done. <n> slide(s) exportee(s).` (pptx) or the `Charte:` lines and `Done.` (docx), exactly the current texts. On error nothing is printed on stdout.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/tools.py` | create: `template_listing`, `create_file`, `export_file`, `ExportOutcome` |
| `src/mcp_htmleditor/cli.py` | modify: `templates`, `new` and `export` call the services, `deck_command` error path |
| `tests/test_deck_tools.py` | create |

### Existing patterns
- `src/mcp_htmleditor/cli.py` current `templates_cmd` (line 51), `new_cmd` (67), `export_cmd` (240), `_export_pptx`, `_export_docx` (the behavior to preserve).
- `src/mcp_htmleditor/templates.py` `list_templates`, `template_path`, `TEMPLATES`.
- `src/mcp_htmleditor/export/to_pptx.py` (`to_pptx` returns a report with `warnings`, `slide_count`), `export/to_docx.py` (`to_docx` result with `charter`, `reference_docx`, `warnings`).
- `tests/test_export_docx.py` (`skipif` when pandoc is absent), `tests/test_templates.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

This story has no spec E2E test; the cases below are its acceptance tests (integration level on the services, plus command line checks), in `tests/test_deck_tools.py`. Templates are read from the repo (`HTMLEDITOR_TEMPLATES_DIR` set to the repo `templates` directory by the test).

### SPEC-0007/US-0045 AT-1: Listing
- Given the registry
- When `template_listing()` is called and `mcp-htmleditor templates` is run
- Then the keys are exactly `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website` in that order (8 entries), every description is a non empty string equal to `templates.list_templates()`, and the command output keeps its first line `Templates disponibles (mcp-htmleditor new <key> <fichier>):` and one line per key

### SPEC-0007/US-0045 AT-2: Unknown template and existing target
- Given an empty directory
- When `new x a.html` is run, then `new doc a.html` twice
- Then the first prints `error: Unknown template "x". Valid templates: ei, carbon, medical, doc, doc-perso, doc-ei, mail, website` on stderr, exit 1, stdout empty and no `a.html`; the second creates `a.html` (equal bytes to `templates/bootstrap/document-empty.html`) and prints `Créé: a.html  (template: doc)`; the third prints `error: File already exists: a.html`, exit 1, `a.html` unchanged (mtime forced to 1_000_000_000 before, equal after)

### SPEC-0007/US-0045 AT-3: Export errors
- Given `a.html` created from template `doc` and DECK-EI
- When `export foo a.html out` and `export pptx ghost.html out.pptx` and `export docx ghost.html out.docx` are run
- Then the stderr lines are `error: Unknown export format "foo". Valid formats: pptx, docx` and (twice) `error: File not found: ghost.html`, exit 1, stdout empty, no output file created
- And `export pptx` of a document with no slide (`a.html`) prints `error: No slide exported: check that the document has data-type="slide" elements.` exit 1

### SPEC-0007/US-0045 AT-4: Export success paths
- Given DECK-EI and `a.html` (template `doc`)
- When `export pptx DECK-EI out.pptx` is run, and (if `pandoc` is on PATH, `skipif` otherwise) `export docx a.html a.docx`
- Then the pptx output starts with `Exporting ` and ends with `Done. 8 slide(s) exportee(s).`, `out.pptx` opens with `python-pptx` and has 8 slides; the docx command prints `Done.`, `a.docx` is a zip containing `word/document.xml`

### SPEC-0007/US-0045 AT-5: Service level
- `create_file("doc", "sub/dir/b.html")` creates the parent directories and returns `Path("sub/dir/b.html")`; a `file.write` span with `template.key` `doc` and `file.size` equal to the template size is recorded; `export_file("a.html", "docx", "x.docx")` with `pandoc` hidden (PATH emptied) raises `DeckError` with `pandoc not found in PATH: install pandoc to export to DOCX.`; `export_file` with format `PPTX` (upper case) raises the unknown format error (formats are exact lower case).
- Importing `mcp_htmleditor.deck.tools` does not import `pptx` or `docx` modules (lazy imports).

## Constraints

- Files not to touch: `src/mcp_htmleditor/templates.py`, `src/mcp_htmleditor/export/*`, `src/mcp_htmleditor/mcp_server.py`.
- Dependencies not to add: none.
- Patterns to avoid: stdout in `deck/tools.py`; keeping `click.Choice` or `exists=True` on these commands; changing the success line texts.
- Scope boundary: no tool registration (US-0046). Accepted change: when a pptx export yields zero slide, its warnings are logged instead of printed on stderr.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing `templates`, `new` and `export` success outputs and the `--serve` behavior are unchanged; `tests/test_templates.py`, `tests/test_export_pptx.py`, `tests/test_export_docx.py` pass unmodified; the French error texts of the old `new` and `export` are intentionally replaced (no existing test asserts them).
- [ ] Docs updated: none in this story (README final text lands in US-0046).
- [ ] Self review: full at tier 2.
- [ ] This story registers no MCP tool; `skill/core.md` is not touched.
- [ ] One commit `US-0045: Template, new and export services on the command line`, body `Spec: SPEC-0007` and the requirement ids FR-NEW-015, FR-NEW-016.
