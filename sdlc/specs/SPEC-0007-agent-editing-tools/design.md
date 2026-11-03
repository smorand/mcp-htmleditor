# SPEC-0007: Agent editing tools, design

> Spec: SPEC-0007 (`sdlc/specs/SPEC-0007-agent-editing-tools/spec.md`)
> Nature: FEAT
> Depth: L
> Security: n/a
> Designed on 2026-11-03
> Target tier: 2 (default)

## 1. Stack and skills

| Item | Value (source) |
|---|---|
| Language, tooling | Python >= 3.13, uv, hatchling; `make` is the only entry point; gate `make check` (ruff, ruff format, mypy strict, bandit, pytest with coverage >= 80%) (`pyproject.toml`, `Makefile`) |
| CLI | Click >= 8.0 (installed 8.4.2), already the CLI framework: kept; the python skill says Typer, the existing project rule wins, no migration in this spec |
| Tool protocol | fastmcp >= 2.0 (installed 3.4.6); tool errors raised as `fastmcp.exceptions.ToolError` |
| HTML | beautifulsoup4 >= 4.12 (installed 4.15.0) with `html.parser`; selectors by soupsieve 2.9.2, which beautifulsoup4 already requires (not a new dependency); stdlib `html.parser.HTMLParser` for byte offsets |
| New dependency | none. Nothing is flagged NEEDS DECISION |
| Skill rules applied | make only; no `os.environ` (no new setting is needed); no stdout in the MCP process (services return values, only `cli.py` echoes); `trace_span` on tool operations and file mutations (`category.operation` names); mypy strict without `type: ignore`; ruff line length 120; `%` formatting in logs; frozen dataclasses with `__slots__` for value objects; the state flag is injected as a callback, no instance built inside a class |
| Library research | no library added or upgraded, so context7 is not required; soupsieve and `HTMLParser.getpos()` behavior was verified on the installed versions (`sourceline` and `sourcepos` of a `Tag` equal `getpos()` of its start tag) |

## 2. Approaches

### 2.1 Byte preserving patch engine (the load bearing choice)

FR-NEW-003 forbids touching bytes outside the touched slides (E2E-004 byte identity, E2E-033 mtime unchanged).

**Approach A: text splice on offsets from a lightweight scanner (chosen).** A `HTMLParser` subclass records, for every element, the offsets of its start tag, inner content and end tag. The file is cut into an ordered list of items: raw segments and slide atoms. Operations edit atoms (or move and insert them); the result is the concatenation. Renumbering is a list of `(start, end, replacement)` edits applied to the final text from the end backwards.
- Pros: bytes outside the edits are identical by construction; the diff of every operation is explainable; no serializer risk; CRLF, BOM, entities, attribute order and quote style survive.
- Cons: a small scanner must be written and tested (about 120 lines); it must agree with BeautifulSoup on element identity (solved with the position key, DEC-002); malformed HTML (unclosed tags) needs a defined closing rule.

**Approach B: parse with BeautifulSoup, mutate, serialize.** This is what `_strip_editor_artifacts` does (`src/mcp_htmleditor/http_server.py:464`).
- Pros: least code; selectors and edits on one tree.
- Cons: `str(soup)` rewrites quotes, self closing tags, entities and whitespace of the whole file, including 235 KB of base64 and CSS. It fails E2E-004 and E2E-033 on any real template. Rejected.

**Approach C: regular expressions on the raw text.**
- Pros: no scanner.
- Cons: `<article` and `</article>` appear inside comments, script strings and skill examples; nested slide like markup; selector support impossible. Rejected.

**Approach D (variant of A): use `sourcepos` of BeautifulSoup alone.** `html.parser` gives only start positions, no end offsets, so end tags would still need a scan. Rejected as incomplete; its `sourceline`/`sourcepos` are used as the bridge key instead (DEC-002).

### 2.2 Renumbering

**Approach A: edit list computed on the assembled text with one scan (chosen).** After all operations, scan once, enumerate slides with `find_slides`, compute every counter edit, apply once. Gives "renumber once, after all operations" (FR-NEW-009) and idempotence (an edit equal to the current bytes is dropped, so an already consistent file stays byte identical).
**Approach B: renumber after each operation.** More scans, intermediate states, and operations designate original ids (FR-NEW-003), which a renumbered intermediate state would break. Rejected.
**Approach C: reuse `editor.js` through a JS runtime.** No JS runtime in the Python stack. Rejected.

### 2.3 Where the logic lives

**Approach A: service layer `deck/` called by thin `cli.py` and `mcp_server.py` (chosen).** `cli.py` and `mcp_server.py` are excluded from coverage (`.agent_docs/testing.md`, omit list), so logic there is untested by the gate. One implementation gives FR-NEW-016 by construction.
**Approach B: logic in the tool functions, the CLI calling the tools.** Imports the protocol layer into the CLI. Rejected.
**Approach C: the CLI shells out to itself.** Slow and pointless. Rejected.

## 3. Architecture

```
 agent ──stdio──▶ mcp_server.py ─┐ (ToolError(msg))        click ◀── user / agent shell
                                  ├──▶ deck/ services ◀──┤  cli.py (prints, "error: msg", exit 1)
                                  │
 deck/__init__.py   DeckError, Deck (parsed file), load_deck, charter + doc_type detection
 deck/scan.py       Scanner(HTMLParser): element offsets; slide atoms; attribute splice helpers;
                    large image listing and data:ref:img-N substitution
 deck/read.py       outline(), get_slide()
 deck/patch.py      parse_operations(), Working (items list), apply_patch()
 deck/renumber.py   renumber_edits(text) -> list[Edit]
 deck/lint.py       Problem, lint_deck(), format_report(), structure rules L001..L006, L010
 deck/charter_rules.py   foreign classes, flex rows, palettes, rules L007..L009, L011
 deck/tools.py      create_file(), export_file(), template_listing()  (FR-NEW-015)
 fileio.py          atomic_write(path, data)   single writer for patch (SPEC-0009 extends it)
 state.py           existing EditorState.set_update_flag (reached through a callback)
 export/charters.py REGISTRY (SPEC-0012): doc charter keys and descriptions
 export/to_pptx.py  find_slides (lazy import, same slide definition as the exporter)

 patch flow: path guard → read bytes → parse ops → load_deck → Working(items) → ops in order
             → renumber_edits(assembled) → splice → lint touched slides → atomic_write (flag around)
```

Module responsibilities and rules:
- `deck/__init__.py` holds the parsed file model because outline, lint and patch all start from it and `read.py` imports `lint.py` (problem counts): putting the model in `read.py` would make a cycle. It exposes `Deck(path, text, soup, slides, charter, doc_type)`, `load_deck(file)`, `DeckError`, `slide_id(tag)`.
- `deck/scan.py` is pure text: no I/O; the only BeautifulSoup use is the position bridge.
- Charter detection: the presentation rule is the spec's own (`--med-teal` in style or `data-doc-template="medical"` on `<html>`, then `--ei-blue` or body `slide-cover-logos`, else carbon), so the registry tokens (`med-rule`, `slide-inner`, `--ibm-blue`) are not used for it and the registry is not extended (DEC-006). The registry supplies the non presentation mapping (the `data-doc-template` value to the charter key through `docx_key` or `key`) and the key list.
- Rule groups key on the presentation charters `ei`, `carbon`, `medical`.

## 4. Data model

All JSON compact (`separators=(",",":")`, `ensure_ascii=False`), keys in the order shown.

```json
// outline (presentation)
{"file":"deck.html","charter":"ei","doc_type":"presentation","total":8,
 "slides":[{"index":0,"id":"slide-0","title":"Couverture","slide_type":"title","words":4,"images":3,"problems":0}],
 "headings":[]}
// outline (document)
{"file":"doc.html","charter":"doc-perso","doc_type":"document","total":0,"slides":[],
 "headings":[{"level":1,"text":"Contexte"}]}
// patch operations (input)
[{"op":"set_text","id":"slide-2","selector":".slide-h1","text":"x"},
 {"op":"replace_slide","id":"slide-3","html":"<article ...>"},
 {"op":"insert_slide","after":"slide-4"|"start","html":"..."},
 {"op":"delete_slide","id":"slide-1"},
 {"op":"move_slide","id":"slide-4","after":"slide-0"|"start"}]
// patch result (+ "dry_run":true when dry run)
{"ok":true,"changed":true,"slides":9,"problems":[{"code":"L009","severity":"error","slide":"slide-1","message":"..."}]}
// lint --json
{"problems":[{"code":"L002","severity":"error","slide":null,"message":"TOTAL is 8 but the file has 9 slides"}],"errors":1,"warnings":0}
// list_templates, new_file, export
[{"key":"ei","description":"..."}]   {"ok":true,"file":"a.html"}   {"ok":true,"output":"a.docx","warnings":[]}
```

Internal types (frozen, slots): `Node(tag, start, start_end, end_start, end_end, line, col)`; `Atom(text, orig_id, touched)`; `Item = str | Atom`; `Edit(start, end, text)`; `Problem(code, severity, slide_index|None, slide, message)`; `Operation(op, fields)`.

Rules fixed by this design where the spec leaves room (all in Section 10):
- Slide id of a slide = `data-id`, else `id`, else absent; lint and outline show `slide-<index>` when absent.
- `words`: whitespace tokens of `NavigableString` nodes, comments excluded, inside `script`, `style`, `svg` skipped.
- `headings`: `h1` to `h5` inside the document article, `class` not containing `doc-title`, text whitespace collapsed.
- `doc_type`: the `<html data-doc-type>` value when it is `presentation`, `document` or `website`; otherwise `presentation` if slides exist, else `document`.

## 5. Contracts and interfaces

### 5.1 Command line (Click)

| Command | Arguments and options | stdout | Errors |
|---|---|---|---|
| `outline` | `FILE` | outline JSON | `error: File not found: <file>` |
| `get-slide` | `FILE ID` | slide HTML | spec messages |
| `patch` | `FILE --ops <path or -> [--dry-run]` | result JSON | spec messages |
| `lint` | `FILE [--json]` | report lines and verdict, or JSON | exit 1 when errors |
| `templates`, `new`, `export` | unchanged arguments (`export FORMAT INPUT OUTPUT`) | unchanged success lines | English FR-NEW-015 messages in `error: ` form |

The file argument is a plain `click.Path(dir_okay=False)` without `exists=True` for the new commands and for `export` (click's check gives exit 2 and another text, `src/mcp_htmleditor/cli.py:125,216,238`). A decorator `deck_command` in `cli.py` wraps the body: it catches `DeckError`, prints `error: <message>` on stderr, `raise SystemExit(1)`. `lint` prints, then exits 1 itself when `errors > 0`. Usage errors stay with click (status 2).

### 5.2 Tool signatures (`mcp_server.py`, each wrapped in `trace_span("mcp.<tool>")`, errors as `ToolError(str(exc))`)

```python
@mcp.tool() def outline(file: str) -> dict[str, Any]
@mcp.tool() def get_slide(file: str, id: str) -> str            # noqa: A002 (spec name)
@mcp.tool() def patch(file: str, ops: list[Any], dry_run: bool = False) -> dict[str, Any]
@mcp.tool() def lint(file: str) -> dict[str, Any]
@mcp.tool() def list_templates() -> list[dict[str, str]]
@mcp.tool() def new_file(template: str, file: str) -> dict[str, Any]
@mcp.tool() def export(file: str, format: str, output: str) -> dict[str, Any]   # noqa: A002
```
`ops` is `list[Any]` so that the spec's own messages (not the framework's) report a malformed operation. Every story that registers a tool adds its line `- <name>: <description>` to the `## Tools` section of the SPEC-0006 skill core (`skill/core.md`, one line `- <name>: <description>` per tool). Seven existing tools plus `get_skill` plus the seven new ones make 15 (SPEC-0001 FR-009 is not edited).

### 5.3 Function signatures

```python
# deck/__init__.py
class DeckError(Exception): ...
def load_deck(file: str) -> Deck                       # DeckError("File not found: <file>"), UTF 8 check
# deck/read.py
def outline(file: str) -> dict[str, Any]
def get_slide(file: str, slide_id: str) -> str
# deck/patch.py
def apply_patch(file: str, ops: object, *, dry_run: bool = False,
                set_update_flag: Callable[[bool], None] | None = None) -> dict[str, Any]
def parse_operations(raw: object) -> list[Operation]
# deck/renumber.py
def renumber_edits(text: str) -> list[Edit]
# deck/lint.py
def lint_deck(deck: Deck) -> list[Problem]
def lint_file(file: str) -> dict[str, Any]
def format_report(problems: Sequence[Problem]) -> list[str]
# deck/tools.py
def template_listing() -> list[dict[str, str]]
def create_file(template: str, file: str) -> Path
def export_file(file: str, fmt: str, output: str) -> ExportOutcome   # output, warnings, slide_count, charter
# fileio.py
def atomic_write(path: str | Path, data: bytes) -> None
```
`atomic_write`: resolve symlinks, `mkstemp` in the same directory, write, `fsync`, copy the mode of the existing file (else `0o666 & ~umask`), `os.replace`, remove the temp file on any failure, span `file.write` with `file.path` and `file.size`.

### 5.4 Exact messages

All strings of spec Sections 6 and 9 are used verbatim. Additions where the spec is silent (DEC-016): `File is not valid UTF-8: <file>`; `patch failed at operation N: operation must be an object (nothing written)`; `patch failed at operation N: field "<name>" must be a string (nothing written)`; `patch failed at operation N: element matched by selector "<s>" has no content (nothing written)`; `patch failed at operation N: the presentation has no slide (nothing written)` for an insert into a file with no slide; `Invalid operations JSON: expected a list`; `Cannot write <file>: <reason>`.

Validation order inside `apply_patch`: template path guard, file exists, ops shape (`Invalid operations JSON`), then per operation in order: unknown operation, missing or non string field, needs a presentation, semantic checks (unknown id, selector, html, image reference, last slide).

### 5.5 Scanner contract (`deck/scan.py`)

`scan(text) -> list[Node]` in document order. Start tag offsets come from `getpos()` converted through a line start table (`\n` only, as `HTMLParser` counts), the end tag end offset from the next `>`. Void elements and `<x/>` have no end. An end tag pops the stack to the nearest open element of the same name (ignored if none), so an unclosed `<p>` inside a slide does not move the slide end. `convert_charrefs=False`. A slide's range is `[start, end_end)` of its element node; its `pre` (the optional line break plus spaces and tabs just before `start`) is split off when cutting items.

Bridge: `Tag.sourceline` and `Tag.sourcepos` equal the scanner node `(line, col)`; the key maps a BeautifulSoup tag to a node (DEC-002).

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/deck/__init__.py` | create | FR-NEW-001 | STORY-A |
| `src/mcp_htmleditor/deck/read.py` | create / edit | FR-NEW-001, 002 | STORY-A (outline), STORY-B (get_slide), STORY-J (problems) |
| `src/mcp_htmleditor/deck/scan.py` | create | FR-NEW-002, 003 | STORY-B |
| `src/mcp_htmleditor/deck/patch.py` | create / edit | FR-NEW-003..008, 010, 011 | STORY-D, E, F, J |
| `src/mcp_htmleditor/deck/renumber.py` | create | FR-NEW-009 | STORY-E |
| `src/mcp_htmleditor/deck/lint.py` | create / edit | FR-NEW-012..014 | STORY-H, I |
| `src/mcp_htmleditor/deck/charter_rules.py` | create | FR-NEW-014 | STORY-I |
| `src/mcp_htmleditor/deck/tools.py` | create | FR-NEW-015, 016 | STORY-K |
| `src/mcp_htmleditor/fileio.py` | create | FR-NEW-003 | STORY-D |
| `src/mcp_htmleditor/cli.py` | edit | FR-NEW-001..003, 010, 012, 015, 016 | A, B, D, E, H, K |
| `src/mcp_htmleditor/mcp_server.py` | edit | FR-NEW-001, 002, 003, 012, 015 | C, G, L |
| `skill/core.md` (SPEC-0006 core, section `## Tools`) | edit | SPEC-0006 FR-NEW-008 | C, G, L |
| `tests/deck_support.py` | create / edit | fixtures, byte identity helper | A, C, D, F, H, I |
| `tests/test_deck_*.py` (outline, get_slide, tools_mcp, patch, patch_delete, patch_structure, patch_tool, lint, lint_charter, lint_wiring, tools, tools_surface) | create | all | per story |
| `README.md` | edit | usage of the seven operations | C |
| `AGENTS.md`, `.agent_docs/testing.md` | edit | index, fixtures and helper | F |
| `.agent_docs/agent-editing.md` | create / edit | formats, engine rules, gotchas (one topic file) | B, E, L |
| `.agent_docs/observability.md` | edit | spans `deck.*`, `file.write` from `atomic_write` | G |
| `.agent_docs/architecture.md` | edit | `deck/` package, `fileio.py` | J |

Affected existing tests: none edited. `tests/test_templates.py` and `tests/test_skill_content.py` keep passing (templates registry unchanged; the SPEC-0006 tool list check is satisfied in the same story that registers a tool). No existing test asserts the French `new` messages or click's `Error:` prefix (searched `tests/`). User visible change: the `new` and `export` command errors become the English `error: ...` lines of FR-NEW-015/016 (DEC-009); `README.md` says so (STORY-C documents the surface, STORY-L the final text).
Documentation not touched: skill topic files other than the core tool list (SPEC-0006 owns the skill text; the topic that teaches the agent to prefer `patch` is a SPEC-0006 follow up, see Section 7).

## 7. Compatibility and risks

| Risk | Detection | Handling |
|---|---|---|
| Scanner and BeautifulSoup disagree on positions or nesting for a real template | invariant test over every `templates/**/*.html`: each BS tag has a node at `(sourceline, sourcepos)` with the same name | fails the build; closing rule of 5.5 |
| `find_slides` import pulls python-pptx (0.29 s measured) | measured | lazy import inside the function, on first use only |
| `outline`'s own charter rule drifts from `detectTemplate` in `slide-layouts.js:12-18` and from `detect_theme` | none today; SPEC-0012 DT-002 compares those two | add the new function to that parity test (backlog) |
| `patch` while the user types in the browser | out of scope (SPEC-0009: locks, snapshots) | the flag is set around the write only |
| SPEC-0009 extends `atomic_write` and adopts it in the browser save (`src/mcp_htmleditor/http_server.py:332` stays `write_text` here) | n/a | signature kept stable: `atomic_write(path, data)` |
| Very large files | E2E-031 (2 MB image) | one scan, offsets only; atoms are slices, no copy per operation |
| `ruff` complexity limits (PLR0912, PLR0911) on rule and op dispatch code | `make lint` | handler tables keyed by op and rule code; no per file ignore added |
| No skill topic tells agents to prefer `patch` | n/a | SPEC-0006 text change, reported as backlog |

Public contracts: 7 added tools, 4 added commands, `new`/`export` error text changes (intended by FR-NEW-016). No removal.

## 8. Security

Not applicable (`Security: n/a`). The template path guard is a functional rule of FR-NEW-003.

## 9. Test strategy

Levels: **E2E** drives the Click command with `CliRunner` (stdout and stderr separate) or the tool through an in process `fastmcp.Client(mcp)`; **Integration** calls a service function on files in `tmp_path`; **Unit** tests a pure function. The browser is not involved. Clock free: no `sleep`, no `time.time()` assertion; modification times are forced with `os.utime(path, (T0, T0))` (T0 a constant such as 1_000_000_000) before an action and compared for equality or inequality after.

Fixtures are generated, never committed, by `tests/deck_support.py` from the real `templates/bootstrap/*.html` read through an explicit repo path (never `~/.config`, as `.agent_docs/testing.md` requires):
- `build_deck(charter, titles, *, image_chars=None, image_slide=None, mutate=None) -> str`: cuts the bootstrap at the first `<article` and after the last `</article>`, keeps the bootstrap cover (retitled), generates the other slides from small literal templates that copy the real classes of the references (`reference/slides/euro-information.html` content slide for EI, `slides-empty.html` slide for Carbon, `reference/slides/medical.html` content slide for medical), writes counters, `TOTAL` and `slideNames` by plain string formatting (independent of product code).
- `deck_ei()` 8 slides (`Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`; slide 3 with a 1 500 character `data:image/png;base64` source; slides 1 to 6 with eyebrow `Cat · Slide 0N / 08` and page element N+1; slide 7 a section slide without foot). No inline colour, no remote image, no template text. The real `example-ei-complete.html` cannot be used as is: it has `#8a5b00`, `#e6ecf7`, `#fff6e6` outside the palette. E2E-009 holds on the generated deck with the real EI bootstrap CSS and cover (checked: the EI bootstrap slide has no inline hex colour and no foreign class).
- `deck_carbon()` 5 slides with eyebrow `Section · Slide 0N / 05` and footer `Slide N / 5` (the bootstrap texts `Contenu de la slide…` and `Titre de la présentation` are replaced, otherwise L006 fires).
- `deck_med()` 6 slides: cover (type `title`), then content slides with `.med-strip` children carrying `w-50`, a tiny PNG, a non empty `.med-source`, `.slide-foot-page`.
- `doc_perso()`: bootstrap `document-perso-empty.html` with the article body replaced by `h1.doc-title` "Rapport", `h1.doc-h1` Contexte, `h2.doc-h2` Périmètre, `h1.doc-h1` Risques.
- Mutators (`set_total`, `drop_attr`, `inject_html`, `set_names_len`) are pure string functions.
- `assert_only_region_changed(before, after, inner_marker)`: common prefix and suffix of the two byte strings, then asserts the differing region lies inside the inner content of the element found by plain substring search of `inner_marker` in `before` (independent of the scanner). Used for E2E-004 and E2E-033.
- `call_tool(name, **args)` opens `fastmcp.Client(mcp)` and returns the data or the `ToolError` text. `run_cli(*args, input=None)` returns stdout, stderr, exit code.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| SPEC-0007/E2E-001 | E2E | CLI + tool | `tests/test_deck_tools_mcp.py` | STORY-C |
| SPEC-0007/E2E-002 | E2E | CLI | `tests/test_deck_outline.py` | STORY-A |
| SPEC-0007/E2E-003 | E2E | tool | `tests/test_deck_tools_mcp.py` | STORY-C |
| SPEC-0007/E2E-004 | E2E | CLI | `tests/test_deck_patch.py` | STORY-D |
| SPEC-0007/E2E-005 | E2E | CLI | `tests/test_deck_patch_structure.py` | STORY-F |
| SPEC-0007/E2E-006 | E2E | CLI | `tests/test_deck_patch_delete.py` | STORY-E |
| SPEC-0007/E2E-007 | E2E | CLI | `tests/test_deck_patch_structure.py` | STORY-F |
| SPEC-0007/E2E-008 | E2E | CLI | `tests/test_deck_patch_structure.py` | STORY-F |
| SPEC-0007/E2E-009 | E2E | CLI | `tests/test_deck_lint.py` | STORY-H |
| SPEC-0007/E2E-010 | E2E | tool | `tests/test_deck_tools_surface.py` | STORY-L |
| SPEC-0007/E2E-011 | E2E | CLI + tool | `tests/test_deck_tools_surface.py` | STORY-L |
| SPEC-0007/E2E-012 | E2E | CLI | `tests/test_deck_get_slide.py` | STORY-B |
| SPEC-0007/E2E-013 | E2E | service + CLI | `tests/test_deck_patch_delete.py` | STORY-E |
| SPEC-0007/E2E-014 | E2E | CLI | `tests/test_deck_patch_structure.py` | STORY-F |
| SPEC-0007/E2E-015 | E2E | CLI | `tests/test_deck_patch.py` | STORY-D |
| SPEC-0007/E2E-016 | E2E | CLI | `tests/test_deck_patch.py` | STORY-D |
| SPEC-0007/E2E-017 | E2E | CLI | `tests/test_deck_patch_structure.py` | STORY-F |
| SPEC-0007/E2E-018 | E2E | CLI | `tests/test_deck_patch_structure.py` | STORY-F |
| SPEC-0007/E2E-019 | E2E | CLI | `tests/test_deck_patch_delete.py` | STORY-E |
| SPEC-0007/E2E-020 | E2E | CLI | `tests/test_deck_lint.py` | STORY-H |
| SPEC-0007/E2E-021 | E2E | CLI | `tests/test_deck_lint_charter.py` | STORY-I |
| SPEC-0007/E2E-022 | E2E | CLI | `tests/test_deck_lint_charter.py` | STORY-I |
| SPEC-0007/E2E-023 | E2E | CLI | `tests/test_deck_lint.py` | STORY-H |
| SPEC-0007/E2E-024 | E2E | CLI | `tests/test_deck_lint.py` | STORY-H |
| SPEC-0007/E2E-025 | E2E | CLI | `tests/test_deck_lint.py` | STORY-H |
| SPEC-0007/E2E-026 | E2E | CLI | `tests/test_deck_lint_charter.py` | STORY-I |
| SPEC-0007/E2E-027 | E2E | CLI | `tests/test_deck_lint_wiring.py` | STORY-J |
| SPEC-0007/E2E-028 | E2E | tool | `tests/test_deck_tools_surface.py` | STORY-L |
| SPEC-0007/E2E-029 | E2E | CLI | `tests/test_deck_patch_structure.py` | STORY-F |
| SPEC-0007/E2E-030 | E2E | CLI | `tests/test_deck_patch_structure.py` | STORY-F |
| SPEC-0007/E2E-031 | E2E | CLI | `tests/test_deck_get_slide.py` | STORY-B |
| SPEC-0007/E2E-032 | E2E | CLI | `tests/test_deck_patch_delete.py` | STORY-E |
| SPEC-0007/E2E-033 | E2E | CLI | `tests/test_deck_patch.py` | STORY-D |
| SPEC-0007/E2E-034 | E2E | tool + in process server | `tests/test_deck_patch_tool.py` | STORY-G |
| SPEC-0007/E2E-035 | E2E | CLI | `tests/test_deck_lint_charter.py` | STORY-I |
| SPEC-0007/E2E-036 | E2E | CLI | `tests/test_deck_lint_wiring.py` | STORY-J |
| SPEC-0007/E2E-037 | E2E | CLI | `tests/test_deck_lint_charter.py` | STORY-I |
| SPEC-0007/E2E-038 | E2E | CLI | `tests/test_deck_lint.py` | STORY-H |
| SPEC-0007/E2E-039 | E2E | CLI | `tests/test_deck_lint.py` | STORY-H |
| SPEC-0007/E2E-040 | E2E | CLI | `tests/test_deck_patch.py` | STORY-D |
| SPEC-0007/E2E-041 | E2E | CLI (patch, get-slide, lint) | `tests/test_deck_lint.py` | STORY-H |

41 E2E tests, each exactly once. E2E-013 uses `delete_slide`, so it sits in STORY-E; E2E-014 uses `move_slide`, so it sits in STORY-F; E2E-026 needs the L010 warning and sits with the charter rules; E2E-036 needs the outline problem count and sits with the wiring story; E2E-041 needs lint and the two other commands.

Non E2E tests (integration and unit, listed per story in Section 11): `atomic_write` (temp removed on failure in a read only directory, mode kept, symlink target replaced, no leftover temp), scanner invariants (every template: scanner and BeautifulSoup agree on every tag; unclosed `<p>`; `<script>` containing `</article>` text; CRLF file; comment between slides), renumber table tests, rule tables for L001..L011, a splice byte test per operation, tool listing equals the `## Tools` section (SPEC-0006 audit).

## 10. Decisions log

- **DEC-001:** The patch engine is a text splice on offsets from a scanner (Approach 2.1 A). **Obliged by:** SPEC-0007/FR-NEW-003. **Rationale:** bytes outside the touched slides must be identical (E2E-004, E2E-033). **Alternatives considered:** parse and serialize with BeautifulSoup (reformats the whole file), regular expressions (comments, scripts). **Source:** spec constraint. **Evidence:** spec 14.3 names the round trip risk; `src/mcp_htmleditor/http_server.py:464-476` is a serializing parse.
- **DEC-002:** Elements are located by a `HTMLParser` subclass; BeautifulSoup tags are mapped to its nodes by `(sourceline, sourcepos)`. **Obliged by:** SPEC-0007/FR-NEW-004. **Rationale:** the selector (soupsieve) needs the BeautifulSoup tree, the edit needs offsets; both parsers share `html.parser` and the same position source. **Alternatives considered:** match by document order index (breaks when BeautifulSoup nests differently from the scanner); write a CSS engine (not needed). **Source:** design. **Evidence:** installed bs4 4.15.0 gives `sourceline=2, sourcepos=1` for the tag in `"<div>\n <article>…"` (measured), equal to `getpos()`; an invariant test over all templates guards it.
- **DEC-003:** The working copy is an ordered list of raw strings and slide atoms; an atom's `pre` (optional line break plus leading spaces and tabs) travels with it. Operations edit, remove or reorder atoms; a reference by id uses a map from original id to atom. **Obliged by:** SPEC-0007/FR-NEW-003, 006, 007, 008. **Rationale:** gives "ids of the original file stay valid after move or replace", "comments between slides stay where they are" and unchanged gaps for free. **Alternatives considered:** recompute offsets after each edit and re-find slides by index (loses identity after moves). **Source:** spec constraint.
- **DEC-004:** Placement details the spec leaves open: delete removes `pre` and the slide (the preceding line break goes, so after deleting the last slide `…</article>\n  </div>` is intact); insert after writes `"\n" + lead + html` right after the reference atom (CRLF if the reference's `pre` is CRLF); insert at `start` writes `html + "\n" + lead` before the first atom, reusing the first atom's `pre` for the new slide (symmetric result, no blank line); move to `start` does the same. **Obliged by:** SPEC-0007/FR-NEW-003. **Rationale:** produces the layout the file already had; the spec text for `start` ("before the first slide: a newline, the lead, then the html") would glue the html to the next tag. **Alternatives considered:** literal reading for `start` (output `\n    NEW<article`). **Source:** design. **Evidence:** `templates/bootstrap/slides-empty.html:305-318` (one slide per indented block).
- **DEC-005:** Renumbering is one pass: scan the assembled text, enumerate slides with `find_slides`, compute an edit list, drop edits whose replacement equals the current bytes, apply from the end. `id` and `data-id` are always set (added when missing), the `active` class is toggled as `editor.js` does, counters follow the charter (Carbon: `.slide-footer-right` pattern `Slide N / TT`; EI and medical: `.slide-foot-page` content replaced by N), the eyebrow keeps its text and only the pattern `Slide <n> / <total>` is replaced, `TOTAL` only changes its digits, `slideNames` is rewritten one entry per line with the first entry's indentation and a trailing comma, titles escaped for quotes, backslashes and newlines. **Obliged by:** SPEC-0007/FR-NEW-009. **Rationale:** mirrors the browser behavior and the spec wording; the inserted slide of E2E-005 must end with an id. **Alternatives considered:** rewrite only attributes that exist. **Source:** existing code `src/mcp_htmleditor/static/editor.js:1562-1603` (sets `slide.id` and `data-id` unconditionally, toggles `active`). **Evidence:** same lines; slideNames layout `templates/bootstrap/slides-empty.html:336-338`.
- **DEC-006:** Charter detection for `outline` and the rules is its own function in `deck/__init__.py`, following the spec rule; the registry maps a non presentation `data-doc-template` value to a charter key and gives the key list. The registry is not extended. **Obliged by:** SPEC-0007/FR-NEW-001. **Rationale:** the spec rule equals `detectTemplate` minus its `Euro.Information` alternative, not the registry tokens (`med-rule`, `slide-inner`, `--ibm-blue`). **Alternatives considered:** reuse `detect_theme` (different signals), add fields to the registry (a second, divergent signal set). **Source:** spec constraint. **Evidence:** `src/mcp_htmleditor/static/slide-layouts.js:12-18`, `src/mcp_htmleditor/export/pptx_style.py:377-386`, SPEC-0012 DR-001.
- **DEC-007:** `doc_type` and `headings` rules of Section 4. **Obliged by:** SPEC-0007/FR-NEW-001. **Rationale:** E2E-002 expects the headings `Contexte`, `Périmètre`, `Risques` for a document that also has a title, so the title element (`class doc-title`) is excluded; every bootstrap carries `<html data-doc-type>`. **Alternatives considered:** include all `h1` (contradicts E2E-002 if the title is an `h1`). **Source:** design. **Evidence:** `templates/bootstrap/*.html` (`data-doc-type="presentation|document|website"`), `skill/types/document.md` (`h1.doc-title`).
- **DEC-008:** Lint is a tuple of rule functions per scope (file, slide), ordered by code, producing `Problem` records; sorting is (whole file first, slide index, code), stable inside a code. L007: one problem per distinct foreign class per slide, first occurrence order. L008: one per offending child. L010: one per remote `img`. The slide column falls back to `slide-<index>` when the slide has no id. L005 checks the eyebrow for all charters and only the counter kind of its charter (Carbon footer, EI and medical page element). **Obliged by:** SPEC-0007/FR-NEW-012, 013, 014. **Rationale:** deterministic output; keeps each rule under the ruff complexity limits. **Alternatives considered:** one big function (PLR0912). **Source:** design.
- **DEC-009:** `deck/` is a service layer; `cli.py` and `mcp_server.py` only parse input, call it, and print or return. `DeckError` becomes `error: <msg>` plus exit 1 on the command line and `ToolError(<msg>)` on the tool surface. `new` and `export` move to the same path, so their errors become the English FR-NEW-015 ones. **Obliged by:** SPEC-0007/FR-NEW-016. **Rationale:** one implementation, identical text; the coverage gate omits both wrappers. **Alternatives considered:** keep `click.ClickException` (prints `Error:`; `exists=True` gives exit 2). **Source:** existing code. **Evidence:** `src/mcp_htmleditor/cli.py:88-94,125,216,238`; `.agent_docs/testing.md` coverage omit list.
- **DEC-010:** `atomic_write(path, data)` in `fileio.py` is the only writer of `patch`. **Obliged by:** SPEC-0007/FR-NEW-003. **Rationale:** "either every operation is applied or none"; SPEC-0009 later extends it. **Alternatives considered:** `Path.write_text` as in the browser save (truncates then writes, not atomic). **Source:** spec constraint. **Evidence:** `src/mcp_htmleditor/http_server.py:332`.
- **DEC-011:** The update flag is toggled through an injected callback `set_update_flag`; `mcp_server.patch` passes `get_state().set_update_flag`, the command line passes none. It is true only around the real write. **Obliged by:** SPEC-0007/FR-NEW-003. **Rationale:** the flag is per process (spec 14.3); in the command line process `set_update_flag` would write a `.mcp_state.json` in the current directory for nothing. **Alternatives considered:** call `get_state()` inside `apply_patch` (hidden singleton, test coupling, stray file). **Source:** design. **Evidence:** `src/mcp_htmleditor/state.py:92-95` (persists on every set), `:57-66`.
- **DEC-012:** Slides are enumerated with `export.to_pptx.find_slides`, imported lazily; scanner nodes are found through the DEC-002 key. **Obliged by:** SPEC-0007/FR-NEW-009. **Rationale:** the slide definition of FR-NEW-009 (`data-type="slide"`, else `article.slide` or `section.slide`, outermost only) is the exporter's; one definition, no duplicate. **Alternatives considered:** a second implementation (duplicated rule), moving `find_slides` (SPEC-0012 keeps it in place). **Source:** existing code. **Evidence:** `src/mcp_htmleditor/export/to_pptx.py:272-282`; import cost 0.29 s measured, hence lazy.
- **DEC-013:** Operations are validated by hand (a table of required string fields per op), not by Pydantic models; the tool parameter `ops` is `list[Any]`. **Obliged by:** SPEC-0007/FR-NEW-003. **Rationale:** the spec messages (`missing field "text"`, `unknown operation "frobnicate"`) are exact and ordered; Pydantic errors would need translation. **Alternatives considered:** Pydantic discriminated union (python skill preference). **Source:** spec constraint.
- **DEC-014:** Check order of `patch` is as in 5.4: template guard, file exists, ops, so `patch ghost.html --ops ops.json` gives `File not found`. **Obliged by:** SPEC-0007/FR-NEW-003. **Rationale:** E2E-011 and E2E-016 fix the first two. **Alternatives considered:** read ops first (breaks E2E-011 when `ops.json` is absent). **Source:** spec constraint.
- **DEC-015:** JSON output is compact with `ensure_ascii=False`; `file` echoes the caller's string. **Obliged by:** SPEC-0007/FR-NEW-001, 012. **Rationale:** the spec examples are compact; tool and command give equal objects (E2E-001). **Alternatives considered:** indented JSON. **Source:** spec constraint.
- **DEC-016:** Messages the spec does not list (Section 5.4) are added for invalid UTF 8, non object operation, non string field, selector hitting an element without content, insert into a file with no slide. **Obliged by:** SPEC-0007/FR-NEW-003, 004. **Rationale:** every failure path must give one `error:` line, never a traceback. **Alternatives considered:** let exceptions escape. **Source:** design.
- **DEC-017:** Tests build fixtures from the real bootstrap files with a helper, force modification times with `os.utime`, and assert byte identity with a prefix and suffix diff against the element found by plain search. **Obliged by:** SPEC-0007/FR-NEW-003 (E2E-004, 033, 034). **Rationale:** deterministic, no clock, no committed megabyte fixture; keeps E2E-009 true on the real EI CSS. **Alternatives considered:** committed golden decks (stale when SPEC-0011/0012 regenerate templates), using `example-ei-complete.html` (out of palette inline colours). **Source:** design. **Evidence:** scan of the slides of `templates/reference/slides/example-ei-complete.html` (colours `#8a5b00`, `#e6ecf7`, `#fff6e6`) and of the bootstrap slides (no inline hex, no foreign class).
- **DEC-018:** Words count: `NavigableString` nodes that are not comments, outside `script`, `style`, `svg`. **Obliged by:** SPEC-0007/FR-NEW-001. **Rationale:** matches the spec text. **Alternatives considered:** `get_text()` (includes comments). **Source:** spec constraint.
- **DEC-019:** `get_slide` returns the slide's raw text from the scanner with large image sources replaced in place by `data:ref:img-N`; `replace_slide` restores by the same ordering on the replaced slide's current text. **Obliged by:** SPEC-0007/FR-NEW-002, 005. **Rationale:** the agent sees the real markup and the round trip of E2E-008 is byte exact for the image. **Alternatives considered:** `str(tag)` (reformats). **Source:** spec constraint.

## 11. Stories

Slicing check: each story is a vertical increment (a user visible command or tool with its tests), keeps `make check` green on main, touches 3 to 5 files (code, tests, skill core and docs counted), has 1 to 4 requirements and at least 5 tests (E2E plus the integration and unit tests listed). Every E2E appears once; every FR-NEW is cited; STORY-L closes the spec. STORY-A has a single requirement because FR-NEW-001 is the only requirement that can be observed before the scanner exists; it still leaves `make check` green.

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| STORY-A | `outline` on the command line | P1 | FR-NEW-001 | main | 2 | no |
| STORY-B | `get-slide` on the command line, scanner | P1 | FR-NEW-002 | STORY-A | 2 | no |
| STORY-C | `outline` and `get_slide` tools | P1 | FR-NEW-001, 002, 016 | STORY-B, SPEC-0006 | 2 | no |
| STORY-D | `patch` with `set_text`, atomic write, path guard | P1 | FR-NEW-003, 004 | STORY-B | 2 | no |
| STORY-E | `delete_slide`, renumbering, dry run | P1 | FR-NEW-007, 009, 010 | STORY-D | 2 | no |
| STORY-F | `insert_slide`, `move_slide`, `replace_slide` | P1 | FR-NEW-005, 006, 008 | STORY-E | 2 | no |
| STORY-G | `patch` tool and editor flag | P1 | FR-NEW-003, 011, 016 | STORY-F, SPEC-0006 | 2 | no |
| STORY-H | `lint` command and structure rules | P1 | FR-NEW-012, 013 | STORY-D | 2 | no |
| STORY-I | Charter rules L007 to L011 | P2 | FR-NEW-012, 014 | STORY-H | 2 | no |
| STORY-J | Lint problems in `outline` and `patch` | P2 | FR-NEW-001, 011 | STORY-F, STORY-I | 2 | no |
| STORY-K | Template, new and export services on the command line | P2 | FR-NEW-015, 016 | main | 2 | no |
| STORY-L | `lint`, `list_templates`, `new_file`, `export` tools | P2 | FR-NEW-012, 015, 016 | STORY-I, STORY-K, STORY-G, SPEC-0006 | 2 | yes |

Files, tests and observable check per story:

- **STORY-A:** `src/mcp_htmleditor/deck/__init__.py`, `src/mcp_htmleditor/deck/read.py`, `src/mcp_htmleditor/cli.py`, `tests/deck_support.py`, `tests/test_deck_outline.py`. Tests: E2E-002; integration outlines of `deck_ei` (charter `ei`, total 8, images, no base64), `deck_carbon`, `deck_med` (medical tested first), a presentation with no mark (carbon), a website and a mail; unit words count (script, svg, attribute excluded); file not found. Check: `make test ARGS='-k deck_outline'`; `outline` prints the JSON of Section 4.
- **STORY-B:** `src/mcp_htmleditor/deck/scan.py`, `src/mcp_htmleditor/deck/read.py`, `src/mcp_htmleditor/cli.py`, `tests/test_deck_get_slide.py`, `.agent_docs/agent-editing.md`. Tests: E2E-012, E2E-031; scanner invariants over all templates; unclosed tag; script containing `</article>`; CRLF; reference numbering; `get_slide needs a presentation`. Check: `get-slide FILE slide-3` shows `data:ref:img-1` and no base64.
- **STORY-C:** `src/mcp_htmleditor/mcp_server.py`, `skill/core.md`, `tests/test_deck_tools_mcp.py`, `tests/deck_support.py`, `README.md`. Tests: E2E-001, E2E-003; tool error text equals the command error text for both tools; the skill audit lists both tools; the tools print nothing on stdout. Check: Client calls return the objects.
- **STORY-D:** `src/mcp_htmleditor/fileio.py`, `src/mcp_htmleditor/deck/patch.py`, `src/mcp_htmleditor/cli.py`, `tests/test_deck_patch.py`, `tests/deck_support.py`. Tests: E2E-004, 015, 016, 033, 040; `atomic_write` units (failure cleanup, mode, symlink); set_text escaping table; invalid selector; empty ops result. Check: `patch FILE --ops -` changes one title and the diff is limited to it.
- **STORY-E:** `src/mcp_htmleditor/deck/renumber.py`, `src/mcp_htmleditor/deck/patch.py`, `src/mcp_htmleditor/cli.py`, `tests/test_deck_patch_delete.py`, `.agent_docs/agent-editing.md`. Tests: E2E-006, 013, 019, 032; renumber table (Carbon footer, EI page, medical page, eyebrow pattern, `active`, TOTAL digits, slideNames layout, no script constants); idempotence (a consistent file stays byte identical). Check: delete on the Carbon deck gives `Slide 1 / 4` footers.
- **STORY-F:** `src/mcp_htmleditor/deck/patch.py`, `tests/deck_support.py`, `tests/test_deck_patch_structure.py`, `AGENTS.md`, `.agent_docs/testing.md`. Tests: E2E-005, 007, 008, 014, 017, 018, 029, 030; byte splice tests per operation (indentation, comments between slides stay, CRLF); move onto itself; an operation naming a slide deleted earlier. Check: insert in the middle of the EI deck renumbers 9 slides.
- **STORY-G:** `src/mcp_htmleditor/mcp_server.py`, `skill/core.md`, `tests/test_deck_patch_tool.py`, `.agent_docs/observability.md`. Tests: E2E-034; tool result shape and `dry_run` key; error text without prefix; flag false after a failing patch; template refusal through the tool; the skill audit lists `patch`. Check: with the server running, `get_status` shows flag false and a newer mtime (forced with `os.utime`).
- **STORY-H:** `src/mcp_htmleditor/deck/lint.py`, `src/mcp_htmleditor/cli.py`, `tests/deck_support.py`, `tests/test_deck_lint.py`. Tests: E2E-009, 020, 023, 024, 025, 038, 039, 041; report format and plural table; ordering; L003 literal counter (quotes, escapes, nested brackets). Check: `lint DECK-EI` prints `lint: OK (0 errors, 0 warnings)`.
- **STORY-I:** `src/mcp_htmleditor/deck/charter_rules.py`, `src/mcp_htmleditor/deck/lint.py`, `tests/deck_support.py`, `tests/test_deck_lint_charter.py`. Tests: E2E-021, 022, 026, 035, 037; foreign class tables per charter; 3 digit colour expansion; `rgb()` and `var()` ignored; L010 on a document. Check: lint reports the L007 to L011 lines.
- **STORY-J:** `src/mcp_htmleditor/deck/read.py`, `src/mcp_htmleditor/deck/patch.py`, `tests/test_deck_lint_wiring.py`, `.agent_docs/architecture.md`. Tests: E2E-027, 036; outline problem counts include warnings; patch problems restricted to touched slides with ids after renumber; an unchanged `set_text` still lints its slide. Check: outline shows `problems` 1 for the remote image slide.
- **STORY-K:** `src/mcp_htmleditor/deck/tools.py`, `src/mcp_htmleditor/cli.py`, `tests/test_deck_tools.py`. Tests (integration, no E2E): unknown template, existing target, unknown format, missing input, pptx and docx error paths, success lines unchanged, `templates` order equals the registry (8 keys), zero slide export error text, `file.write` span. Check: `new x a.html` prints `error: Unknown template "x". Valid templates: ...`.
- **STORY-L:** `src/mcp_htmleditor/mcp_server.py`, `skill/core.md`, `tests/test_deck_tools_surface.py`, `.agent_docs/agent-editing.md`. Tests: E2E-010, 011, 028; the `lint` tool equals `lint --json`; the tool list equals the 15 names of the skill core (audit green). Check: `make check`, the Client lists the seven new tools and the SPEC-0006 audit passes.

Stories as machine readable JSON are returned in the final message of the design run.
