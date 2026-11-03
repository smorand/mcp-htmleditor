# US-0038: `patch` with `set_text`, atomic write, path guard

> Spec: SPEC-0007 (sdlc/specs/SPEC-0007-agent-editing-tools/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0036
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Gives `mcp-htmleditor patch <file> --ops <ops.json | -> [--dry-run]` with the `set_text` operation: validation of every operation before any write, one atomic byte preserving write, template path refusal, idempotency.

## Requirements covered

- SPEC-0007/FR-NEW-003 (partial: validation order, atomic write, no write when unchanged, template path guard, operation parsing for the five operation names, `--dry-run` option and `dry_run` result key; update flag exposed as an optional callback; the tool arrives in US-0041): WHEN an agent or a user applies `patch` with a list of operations THE Editor SHALL validate all operations before writing, then write the file once, atomically, so that either every operation is applied or none.
- SPEC-0007/FR-NEW-004: WHEN a patch holds `{"op":"set_text","id":<id>,"selector":<css selector>,"text":<text>}` THE Editor SHALL replace the whole inner content of the first element matching the selector inside that slide by the text, escaped as plain text.

## Independent Test

`make test ARGS='-k deck_patch'`: `patch DECK-EI --ops -` with one `set_text` on `slide-2` `.slide-h1` prints `{"ok":true,"changed":true,"slides":8,"problems":[]}`; the file before and after share an identical prefix and suffix and the differing region lies inside the title element (found by plain substring search, not by the scanner); the second identical run prints `"changed":false` and the forced modification time is unchanged.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0007): text splice on scanner offsets; bytes outside the edit are identical by construction.
- DEC-003 (SPEC-0007): "The working copy is an ordered list of raw strings and slide atoms; an atom's `pre` (optional line break plus leading spaces and tabs) travels with it. Operations edit, remove or reorder atoms; a reference by id uses a map from original id to atom." (This story builds the list and edits atoms of `set_text`; moves and structure arrive in US-0039 and US-0040.)
- DEC-010 (SPEC-0007): "`atomic_write(path, data)` in `fileio.py` is the only writer of `patch`."
- DEC-011 (SPEC-0007): "The update flag is toggled through an injected callback `set_update_flag`... It is true only around the real write." The command line passes none.
- DEC-013 (SPEC-0007): operations validated by hand (a table of required string fields per op), not Pydantic.
- DEC-014 (SPEC-0007): "Check order of `patch` is as in 5.4: template guard, file exists, ops."
- DEC-016 (SPEC-0007): extra messages listed under Contracts.
- DEC-017 (SPEC-0007): tests force modification times with `os.utime` and assert byte identity with a prefix and suffix diff against the element found by plain search.

### Data model
Operations input (all five names are parsed and validated in this story; only `set_text` is executed here):
```json
[{"op":"set_text","id":"slide-2","selector":".slide-h1","text":"x"},
 {"op":"replace_slide","id":"slide-3","html":"<article ...>"},
 {"op":"insert_slide","after":"slide-4","html":"..."},
 {"op":"delete_slide","id":"slide-1"},
 {"op":"move_slide","id":"slide-4","after":"slide-0"}]
```
Patch result, keys in this order: `{"ok":true,"changed":true,"slides":8,"problems":[]}`, plus a last key `"dry_run":true` when a dry run. `problems` is always `[]` in this story (lint arrives in US-0041 to US-0043, wired in US-0044).
Internal frozen dataclasses with `__slots__`: `Operation(op, fields)`, `Atom(text, orig_id, touched)`.

### Contracts
```python
# fileio.py
def atomic_write(path: str | Path, data: bytes) -> None
# deck/patch.py
def parse_operations(raw: object) -> list[Operation]
def apply_patch(file: str, ops: object, *, dry_run: bool = False,
                set_update_flag: Callable[[bool], None] | None = None) -> dict[str, Any]
```
`atomic_write`: resolve symlinks, `mkstemp` in the same directory, write, `fsync`, copy the mode of the existing file (else `0o666 & ~umask`), `os.replace`, remove the temp file on any failure, wrapped in `trace_span("file.write", {"file.path": ..., "file.size": ...})`. A failure raises `DeckError("Cannot write <file>: <reason>")`.

Command: `mcp-htmleditor patch FILE --ops PATH_OR_DASH [--dry-run]`; `-` reads standard input; prints the result JSON compact. `deck_command` decorator in `cli.py`: wraps a command body, catches `DeckError`, prints `error: <message>` on stderr (standard output empty), `raise SystemExit(1)`. Usage errors stay with click (status 2). The file argument is a plain `click.Path(dir_okay=False)` without `exists=True` (click's check gives exit 2 and another text).

`apply_patch` flow and validation order: (1) template path guard: if the absolute, symlink resolved path contains the consecutive components `templates/bootstrap` or `templates/reference`, `DeckError("Refusing to modify a template: <file>")` with `<file>` as the caller gave it, before any other check and before the dry run; (2) file exists (`File not found: <file>`); (3) ops shape: not a list gives `Invalid operations JSON: expected a list`; non JSON text on the command line gives `Invalid operations JSON: <json decoder reason>`; (4) per operation in order: unknown operation, missing or non string field, needs a presentation, semantic checks (unknown id, selector). Every operation failure is `patch failed at operation N: <reason> (nothing written)`, N from 1. Reasons:
- `unknown operation "frobnicate"`; `operation must be an object`; `missing field "<name>"` (required fields: set_text: id, selector, text; replace_slide: id, html; insert_slide: after, html; delete_slide: id; move_slide: id, after); `field "<name>" must be a string`;
- `operation "<op>" needs a presentation` for any of the five operations when the file has no slide (documents, mails, websites);
- `unknown slide id "<id>"`; `selector "<selector>" matches no element in slide "<id>"`; `invalid selector "<selector>"`; `element matched by selector "<selector>" has no content` (void element).
- A valid operation among replace_slide, insert_slide, delete_slide, move_slide fails in this story with `operation "<op>" is not supported yet`; US-0039 and US-0040 remove this reason for their operations.

`set_text` semantics: the selector is CSS level 3 evaluated with soupsieve inside the slide element, the slide element itself being a candidate (test the slide first with `soupsieve.match`, then `select_one` on the descendants); first means document order; the children of the element are replaced by a single text node, i.e. the byte range `[start_end, end_start)` of the matched scanner node is replaced by the text escaped as `&` to `&amp;`, `<` to `&lt;`, `>` to `&gt;`, quotes and non ASCII characters left as they are. Scanner node found by the bridge key (`sourceline`, `sourcepos`).
Idempotency: when the assembled result equals the original bytes, nothing is written (the modification time does not change) and `changed` is false. `slides` is the slide count after the patch. An empty list gives `{"ok":true,"changed":false,"slides":<n>,"problems":[]}`.
Write: the callback (when given) is called with `True` just before the write and `False` in a `finally` after; with `dry_run` nothing is written and the callback is not called; the result gains `"dry_run":true`.
Read bytes are decoded as UTF-8 (a BOM and CRLF are kept as they are; the splice works on the decoded text and re-encodes UTF-8).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/fileio.py` | create: `atomic_write` |
| `src/mcp_htmleditor/deck/patch.py` | create: `parse_operations`, `Working`, `apply_patch`, `set_text` |
| `src/mcp_htmleditor/cli.py` | modify: add the `patch` command |
| `tests/test_deck_patch.py` | create |
| `tests/deck_support.py` | modify: add `assert_only_region_changed` |

### Existing patterns
- `src/mcp_htmleditor/http_server.py:332` browser save (`write_text`, left unchanged here; SPEC-0009 extends `atomic_write` later).
- `src/mcp_htmleditor/state.py:92-95` `set_update_flag` persistence (reason the callback is injected).
- `src/mcp_htmleditor/tracing.py` `trace_span`.
- `src/mcp_htmleditor/deck/scan.py` (US-0036) `scan`, bridge key.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures (generated by `tests/deck_support.py` from the real `templates/bootstrap/*.html`, never committed; no clock, `os.utime(path, (1_000_000_000, 1_000_000_000))` to force modification times):
- DECK-EI: an Euro-Information presentation (real EI bootstrap CSS and cover), no inline colour outside the Euro-Information palette, no remote image, no template text, consistent counters, 8 slides titled `Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`, ids `slide-0` to `slide-7`; slide 3 holds a 1 500 character `data:image/png;base64` image; slides 1 to 6 carry eyebrow `Cat · Slide 0N / 08` (N = index + 1) and page element N (`.slide-foot-page`, so slides 1 to 6 hold 2 to 7); slide 7 is a section slide without foot; `const TOTAL = 8;` and `const slideNames = [ ... ];` consistent.
- DECK-CARBON: a Carbon presentation of 5 slides titled `Intro`, `Offre`, `Chiffres`, `Plan`, `Fin`, eyebrow `Section · Slide 0N / 05`, footers `Slide 1 / 5` to `Slide 5 / 5` (`.slide-footer-right`), TOTAL 5, slideNames 5 entries.
- DECK-MED: a medical presentation of 6 slides: cover (`data-slide-type="title"`) then content slides with `.med-strip` children carrying `w-50`, a tiny PNG, a non empty `.med-source`, `.slide-foot-page`.
- DOC-PERSO: `document-perso-empty.html` with the article body replaced by `h1.doc-title` "Rapport", `h1.doc-h1` "Contexte", `h2.doc-h2` "Périmètre", `h1.doc-h1` "Risques".

Helper added to `tests/deck_support.py`: `assert_only_region_changed(before, after, inner_marker)` takes the common prefix and suffix of the two byte strings and asserts the differing region lies inside the inner content of the element located by plain substring search of `inner_marker` in `before` (independent of the scanner).

### SPEC-0007/E2E-004: Change a title
- Level E2E; Driver CLI; Location `tests/test_deck_patch.py`
- Given DECK-EI
- When the agent calls `patch` with `[{"op":"set_text","id":"slide-2","selector":".slide-h1","text":"Contexte et enjeux"}]`
- Then the result is `{"ok":true,"changed":true,"slides":8,"problems":[]}`
- And the file differs from the original only in the content of that title element

### SPEC-0007/E2E-015: Unknown operation
- Level E2E; Driver CLI; Location `tests/test_deck_patch.py`
- Given DECK-CARBON
- When the agent patches `[{"op":"frobnicate"}]`
- Then it fails with `patch failed at operation 1: unknown operation "frobnicate" (nothing written)`

### SPEC-0007/E2E-016: Template path refused
- Level E2E; Driver CLI; Location `tests/test_deck_patch.py`
- Given a copy of a bootstrap template saved under `templates/bootstrap/x.html` (inside `tmp_path`)
- When the agent patches it with a valid `set_text`, with and without `--dry-run`
- Then both fail with `Refusing to modify a template: templates/bootstrap/x.html` and the exit status is 1 (the path shown is the one given, relative to the working directory the test sets)

### SPEC-0007/E2E-033: Escaping and idempotency
- Level E2E; Driver CLI; Location `tests/test_deck_patch.py`
- Given DECK-EI
- When the agent runs `set_text` on `slide-2` `.slide-h1` with the text `R&D <b>x</b>` twice
- Then after the first run the title element contains the text `R&D <b>x</b>` as plain text (`R&amp;D &lt;b&gt;x&lt;/b&gt;` in the file) and `changed` is true
- And the second run gives `changed` false, and the modification time of the file did not change (file forced to `os.utime(path, (1_000_000_000, 1_000_000_000))` before the second run; mtime compared for equality)

### SPEC-0007/E2E-040: Missing field in an operation
- Level E2E; Driver CLI; Location `tests/test_deck_patch.py`
- Given DECK-EI
- When the agent patches `[{"op":"set_text","id":"slide-1","selector":".slide-h1"}]`, and runs the command `patch` with the content `not json`
- Then the first fails with `patch failed at operation 1: missing field "text" (nothing written)`
- And the second prints `error: Invalid operations JSON: ` followed by a reason and exits with status 1

### Additional tests (same file)
- `atomic_write` units: replaces the content and keeps the file mode (0o640 stays 0o640); follows a symlink (the target is replaced, the link stays a link); in a read only directory it raises `DeckError` starting `Cannot write ` and leaves no `tmp` file in the directory; a new file gets `0o666 & ~umask`; a `file.write` span with `file.size` is recorded.
- `set_text` escaping table: `a&b` gives `a&amp;b`; `<i>` gives `&lt;i&gt;`; `"q"` and `é` stay literal; text `` (empty) leaves an empty element.
- `set_text` selector hits the slide element itself (`article`) and the first match in document order; `.nope` gives `patch failed at operation 1: selector ".nope" matches no element in slide "slide-1" (nothing written)`; `:::` gives `invalid selector ":::"`; a `br` selector gives `element matched by selector "br" has no content`.
- Validation: non list JSON `{}` gives `Invalid operations JSON: expected a list`; `[3]` gives `operation must be an object`; `{"op":"set_text","id":5,"selector":"p","text":"x"}` gives `field "id" must be a string`; `delete_slide` on DOC-PERSO gives `operation "delete_slide" needs a presentation`; `delete_slide` on DECK-CARBON gives `operation "delete_slide" is not supported yet`; empty list gives `{"ok":true,"changed":false,"slides":8,"problems":[]}` and the file is untouched.
- Check order: `patch ghost.html --ops ops.json` (neither exists) gives `error: File not found: ghost.html`; `--dry-run` of a valid set_text on DECK-EI gives `"dry_run":true` with the file equal to the saved copy and mtime unchanged.
- The callback is called `True` then `False` around a real write, never on a dry run, and never when nothing changed.
- `--ops -` reads standard input; a CRLF copy of DECK-EI keeps every `\r\n` outside the title.

## Constraints

- Files not to touch: `src/mcp_htmleditor/http_server.py` (browser save stays `write_text`), `src/mcp_htmleditor/state.py`, `src/mcp_htmleditor/mcp_server.py`.
- Dependencies not to add: none (soupsieve comes with beautifulsoup4).
- Patterns to avoid: BeautifulSoup serialization for output; `Path.write_text` for the patch; calling `get_state()` inside `apply_patch`; stdout inside `deck/`; Pydantic models for operations.
- Scope boundary: no renumbering, no lint, no tool.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: US-0035 and US-0036 tests unchanged; browser save behavior (`tests/test_autosave_focus_e2e.py`) unchanged.
- [ ] Docs updated: none beyond code docstrings (the format notes land in `.agent_docs/agent-editing.md` with US-0036 and US-0039).
- [ ] Self review: full at tier 2.
- [ ] This story registers no MCP tool; `skill/core.md` is not touched.
- [ ] One commit `US-0038: `patch` with `set_text`, atomic write, path guard`, body `Spec: SPEC-0007` and the requirement ids FR-NEW-003, FR-NEW-004.
