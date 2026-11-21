# US-0172: add the pointer to an older deck

> Spec: SPEC-0034 (sdlc/specs/SPEC-0034-add-pointer-to-old-decks/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective
`mcp-htmleditor add-pointer <file>` adds the pointer's code, the `Pointeur` control and the `L` key to a presentation that lacks them, only what is missing, and refuses what it cannot do.

## Requirements covered
- SPEC-0034/FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-005, FR-NEW-007 (see the spec; the design section 5 gives the detection and insertion rules).

## Independent Test
`make test ARGS='tests/test_add_pointer.py'` green, `make check` green.

## Design excerpt
### Decisions
DEC-001 text insertion; DEC-002 block from the Carbon bootstrap; DEC-003 key script of its own; DEC-004 control clones `btn-present` class; DEC-005 `atomic_write` with reason `add-pointer`.
### Contracts
`src/mcp_htmleditor/deck/pointer.py`: `add_pointer(file: str) -> PointerOutcome` (`file`, `added`, `summary()`), raising `DeckError` with the messages of the spec; refusal order: `require_encodable_path`, `File not found: <file>`, `Refusing to modify a template: <file>` (same test as `breathe/inline.py:_is_template`, reuse it), `File is not valid UTF-8: <file>`, `<file> is not a presentation` (no `data-type="slide"`), then detection on the text without HTML comments (`_has_code`, `_has_control`, `_has_key` as in the design), then `<file> has no Présenter control, nothing to place the Pointeur control after` when the control is needed and `id="btn-present"` is absent. Nothing written when no part is missing; otherwise one `atomic_write(deck, text, reason="add-pointer")`; `CRLF` kept; trace span `deck.add_pointer`.
`src/mcp_htmleditor/cli.py`: `add-pointer` command next to `breathe-inline` (same `@deck_command`).
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/pointer.py` | create |
| `src/mcp_htmleditor/cli.py` | modify |
| `tests/pointer_old_deck_support.py` | create |
| `tests/test_add_pointer.py` | create |
### Existing patterns
`src/mcp_htmleditor/breathe/inline.py` (`_embed`, `_is_template`, `HISTORY_REASON`, `InlineOutcome.summary`), `tests/test_breathe_inline.py` (CLI via `run_cli`), `tests/pointer_support.py` (fullscreen and dot checks), `tests/conftest.py` (`serve_deck`).

## Acceptance tests
> 100% must pass, run through `make check`. In `tests/test_add_pointer.py`; "older deck" = the template's file with the block between `<!-- deck-pointer:begin -->` and `<!-- deck-pointer:end -->`, the line holding `id="btn-pointer"` and the line holding `e.key === 'l'` removed (`pointer_old_deck_support.older_deck(template_path)`).
### SPEC-0034/E2E-001: add the pointer to an older Carbon deck
- Given the older deck `Réunion talk.html` of the Carbon bootstrap and a CRLF copy of it / When `add-pointer` / Then stdout `<path as given>: pointer added`, status 0; the file has one `deck-pointer-script`, one `btn-pointer` right after the `btn-present` element with its class, a `deck-pointer-key`; with the original text otherwise unchanged (removing the inserted parts gives the original bytes); CRLF copy: every inserted line ends with CRLF and the file has no lone LF; the history lists the previous content with reason `add-pointer`; in Chromium full screen (as `pointer_support`), `L` shows `#deck-pointer-dot`, `L` again removes it
### SPEC-0034/E2E-002: complete deck, repeated request
- Given a fresh template deck and an older deck after one request / When `add-pointer` / Then `<path>: already has the pointer`, status 0, bytes equal before and after, no new history entry
### SPEC-0034/E2E-003: partial decks
- Given the older deck with each of the six combinations of one or two parts present; with the code's script only inside `<!-- -->`; with a `btn-pointer` before `btn-present` (standard presentation reference deck) / When `add-pointer` / Then each has exactly one code, one control and one key (a deck whose key line exists gets no `deck-pointer-key`), answer `pointer added`; the commented one gets the real code; the deck with the control before is not given a second control
### SPEC-0034/E2E-004: file not found and template file
- `absent.html`, and `templates/bootstrap/slides-empty.html` / Then `error: File not found: absent.html` and `error: Refusing to modify a template: <path>` on stderr, status 1, template bytes unchanged, no file created
### SPEC-0034/E2E-005: not a presentation, no Présenter, not UTF-8
- A document file (`mcp-htmleditor new doc`); an older deck without its `btn-present` element; a deck with a `0xFF` byte / Then `error: <doc> is not a presentation`, `error: <deck> has no Présenter control, nothing to place the Pointeur control after`, `error: File is not valid UTF-8: <deck>`, status 1 each, bytes unchanged; an older deck lacking `btn-present` but having the control already gets only the missing code and key
### SPEC-0034/E2E-007: every charter
- An older deck of Carbon, Euro-Information, medical, Breathe (bootstrap templates) and the standard presentation reference deck / When `add-pointer` / Then three parts present; in Chromium full screen `L` shows the dot
