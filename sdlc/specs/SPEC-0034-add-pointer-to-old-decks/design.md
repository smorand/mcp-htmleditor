# SPEC-0034: Bring the pointer to decks created before it existed, design

> Spec: sdlc/specs/SPEC-0034-add-pointer-to-old-decks/spec.md
> Nature: FEAT
> Depth: M
> Security: n/a
> Designed on: 2026-11-21
> Target tier: 2 (default)

## 1. Stack and skills
Existing stack (Python 3.13, click, FastMCP, Playwright for tests). No dependency. Skill python: `make` only, config untouched, `trace_span` around the operation, `DeckError` for refusals.

## 2. Approaches
### Chosen: text insertion of three parts into the deck file
A new module reads the deck as text, decides which of the three parts are present, and inserts the missing ones: the code block copied from the Carbon bootstrap between its markers, a control cloned from the deck's own `btn-present` (its class kept), a small key script. One module, no HTML parser (a parser would reserialize the author's file, SPEC-0020 spirit).
Rejected: the editor injecting the pointer at load (a deck must stay self contained, the file would not present on its own); an HTML parser rewrite (reserializes the file).

## 3. Architecture
`src/mcp_htmleditor/deck/pointer.py`: `add_pointer(file) -> PointerOutcome`. `cli.py` command `add-pointer` and `mcp_server.py` tool `add_pointer` call it. Refusal order, as `breathe/inline.py`: path encodable, file exists, not a template file, valid UTF-8, a presentation (`data-type="slide"` present), then the parts; the file is written only when something is added (`atomic_write(..., reason="add-pointer")`).

## 4. Data model
`PointerOutcome(file: str, added: bool)`; `summary()` is `<file>: pointer added` or `<file>: already has the pointer`.

## 5. Contracts and interfaces
- Text seen for detection: the file with HTML comments removed (`<!--.*?-->`, dotall).
- `_has_code`: `<script id="deck-pointer-script"` in that text. `_has_control`: `id="btn-pointer"`. `_has_key`: `\.key\s*===?\s*['"][lL]['"]` or `id="deck-pointer-key"`.
- Insert code: the source text between `<!-- deck-pointer:begin -->` and `<!-- deck-pointer:end -->` inclusive of both, read from `_repo_templates_dir()/"bootstrap"/"slides-empty.html"`, placed before the last `</body>` (any case; at the end of file when there is none), followed by the key script when the key is missing.
- Key script: `<script id="deck-pointer-key">` with one `keydown` listener: ignores when the focused element is editable or an INPUT, TEXTAREA, SELECT, or when ctrl, meta or alt is held, and calls `togglePointer()` on `l` or `L` (the same guards as the templates' handler).
- Insert control: after the `</button>` that closes the element `id="btn-present"`: the line ending and indentation of the `btn-present` line, then `<button class="<btn-present class>" id="btn-pointer" onclick="presentWithPointer()" title="Présenter avec le pointeur (L)" aria-label="Présenter avec le pointeur (L)" style="width:auto;padding:0 12px">Pointeur</button>` (no class attribute when `btn-present` has none). No `btn-present` and the control needed: `DeckError("<file> has no Présenter control, nothing to place the Pointeur control after")`.
- Line endings: if the file contains `\r\n` the inserted text is converted to it.
- Messages: `File not found: <file>`, `Refusing to modify a template: <file>`, `File is not valid UTF-8: <file>`, `<file> is not a presentation`.
- CLI: `@main.command("add-pointer")`, argument `file`, `@deck_command`, prints `summary()`.
- Tool: `add_pointer(file: str) -> dict` returning `{ok, summary, added}`; `ToolError(str(exc))` on `DeckError`; `trace_span("mcp.add_pointer", {"file.path": file})`.
- Skill: line `- add_pointer: Add the presentation pointer to an older deck.` in `skill/core.md` `## Tools`, after freeing bytes (cap 6000).

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/deck/pointer.py` | create | FR-NEW-001..005, 007 | US-0172 |
| `src/mcp_htmleditor/cli.py` | modify: `add-pointer` | FR-NEW-001 | US-0172 |
| `tests/pointer_old_deck_support.py` | create: build an older deck from a template | E2E tests | US-0172 |
| `tests/test_add_pointer.py` | create: E2E-001..005, 007 (file level and browser) | spec | US-0172 |
| `src/mcp_htmleditor/mcp_server.py` | modify: tool | FR-NEW-006, FR-MOD-001 | US-0173 |
| `skill/core.md` | modify: tool line, bytes freed | FR-NEW-008 | US-0173 |
| `tests/test_add_pointer_tool.py` | create: E2E-006 | spec | US-0173 |
| `tests/test_deck_tools_surface.py` | modify: twenty four | E2E-008 | US-0173 |
| `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/agent-editing.md`, `.agent_docs/html-conventions.md` | modify: command, tool, count | FR-NEW-008 | US-0173 |
Affected existing tests: the ones that pin the tool count and the skill text (`tests/test_deck_tools_surface.py`, `tests/test_http_header_gate_e2e.py`, `tests/test_skill_shipped.py` if it hashes the core).

## 7. Compatibility and risks
Inserted text only; a deck's existing content is never altered. Risk: a deck whose own fullscreen code does not mark the current slide (`.active` or `data-fs-current`) shows no dot on the right slide; the convention and template history make that unlikely. Rollback: revert; a deck is restorable from its history.

## 9. Test strategy
An older deck is built from a template by removing the three parts (`pointer_old_deck_support.py`: the block between its markers, the `btn-pointer` line, the `L` line). Browser checks use `serve_deck` and a fullscreen emulation as `tests/pointer_support.py` does (US-0102) to show the dot with `L`.

## 10. Decisions log
- **DEC-001:** insert text, no HTML parser. **Obliged by:** FR-NEW-001, FR-NEW-007. **Alternatives:** parse and reserialize (rewrites the author's file).
- **DEC-002:** the code comes from the Carbon bootstrap, the single source of the block (`tools/sync_deck_pointer.py`). **Obliged by:** FR-NEW-001.
- **DEC-003:** the key is a script of its own because an older deck's key handler cannot be edited safely. **Obliged by:** FR-NEW-001, FR-NEW-003.
- **DEC-004:** the control clones the `btn-present` class. **Obliged by:** FR-NEW-001, edge cases.
- **DEC-005:** written through `atomic_write` with the reason `add-pointer`, only when a part was added. **Obliged by:** FR-NEW-005, FR-NEW-007.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0172 | add the pointer to an older deck (module and command) | P1 | FR-NEW-001..005, FR-NEW-007 | main | 2 | no |
| US-0173 | the add_pointer agent operation, skill and documentation | P1 | FR-NEW-006, FR-NEW-008, FR-MOD-001 | US-0172 | 2 | yes |
