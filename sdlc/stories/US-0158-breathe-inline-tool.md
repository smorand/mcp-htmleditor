# US-0158: the breathe_inline tool, its skill line and tests

> Spec: SPEC-0028 (sdlc/specs/SPEC-0028-breathe-inline-tool/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective
An agent can embed or link the Breathe assets of a deck through the agent interface with the same result line and errors as the command `breathe-inline`; the skill lists the new operation.

## Requirements covered
- SPEC-0028/FR-NEW-001: WHEN an agent asks to embed the Breathe assets of a deck THE agent interface SHALL write the decoration and pictures into the deck exactly as the command `breathe-inline` does and SHALL return the summary line the command prints.
- SPEC-0028/FR-NEW-002: WHEN an agent asks for the linked form THE agent interface SHALL refer to the files in `assets` next to the deck, copy them there, and return the summary line of the linked form.
- SPEC-0028/FR-NEW-003: IF the command `breathe-inline` would refuse the call THEN THE agent interface SHALL refuse it with the same message, without `error: `, and leave the file as it was.
- SPEC-0028/FR-NEW-004: The agent interface SHALL leave the deck unchanged when the same call is repeated.
- SPEC-0028/FR-NEW-005 (partial: the skill line): the agent skill SHALL list the operation with one line.
- SPEC-0028/FR-MOD-001: the agent interface SHALL offer twenty three operations, the twenty two listed today and `breathe_inline`.

## Independent Test
`make test ARGS='tests/test_breathe_inline_tool.py tests/test_deck_tools_surface.py'` green, `make check` green (`skill-audit` is part of the tests).

## Design excerpt
### Decisions
DEC-001 call `embed_assets` in process, return the summary line and counts. DEC-002 `DeckError` to `ToolError(str(exc))`. DEC-003 no update window. DEC-004 span `mcp.breathe_inline` (`file.path`, `breathe.link`).
### Contracts
In `src/mcp_htmleditor/mcp_server.py`, after `export` (line ~400), same pattern as `lint` and `export`:
```python
@mcp.tool()
def breathe_inline(file: str, link: bool = False) -> dict[str, Any]:
    """Embed (or link) the Breathe decoration and pictures a deck uses; same as ``mcp-htmleditor breathe-inline``. ..."""
    with trace_span("mcp.breathe_inline", {"file.path": file, "breathe.link": link}):
        try:
            outcome = embed_assets(file, link=link)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc
        return {
            "ok": True,
            "summary": outcome.summary(),
            "classes": outcome.classes,
            "pictures": outcome.pictures,
            "copied": outcome.copied,
            "size_kb": outcome.size_kb,
            "folder": str(outcome.folder),
        }
```
Import `embed_assets` from `.breathe.inline`. Module docstring count 22 to 23 (`mcp_server.py:3`). `skill/core.md` `## Tools`, one line after `render`: `- breathe_inline: Embed (or with link, link to assets/) the decoration and pictures a Breathe deck uses; same result line and errors as the command breathe-inline.`
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/mcp_server.py` | modify |
| `skill/core.md` | modify |
| `tests/test_deck_tools_surface.py` | modify: `FINAL_TOOLS` gets `"breathe_inline"`, `assert len(names) == 23` (declared by the spec, E2E-008) |
| `tests/test_breathe_inline_tool.py` | create |
### Existing patterns
Tool tests with a real client: `tests/test_deck_tools.py` (`fastmcp.Client`), Breathe fixtures `tests/breathe_support.py` (`breathe_deck`, `legacy_deck`) and the command tests `tests/test_breathe_inline.py`; CLI `run_cli` in `tests/deck_support.py:244`.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.
All in `tests/test_breathe_inline_tool.py` except E2E-008. Driver: the tool called through a real client on the server; the command through `run_cli("breathe-inline", ...)` for parity.
### SPEC-0028/E2E-001: embed returns the command's line and writes the same file
- Given `talk.html`, a Breathe deck with decoration classes and named pictures, and `talk-cmd.html`, a copy
- When the tool is called on `talk.html` and `breathe-inline talk-cmd.html` is run
- Then the tool's `summary` equals the command's output line with `talk-cmd.html` replaced by `talk.html`, and `talk.html` is byte identical to `talk-cmd.html`
### SPEC-0028/E2E-002: linked form
- Given the same deck (two copies)
- When the tool is called with `link=true` and `breathe-inline --link` is run on the copy
- Then the summary reads `... pictures linked, <K> files copied to <folder>, <N> KB` as the command's, the folder `assets` next to the deck holds the copied files, and the decks are byte identical
### SPEC-0028/E2E-003: file not found
- Given no file `absent.html` / When the tool is called on it / Then a `ToolError` with the text `File not found: absent.html`, and no file is created
### SPEC-0028/E2E-004: a template file is refused
- Given the Breathe template shipped with the editor / When the tool is called on it / Then `ToolError` `Refusing to modify a template: <that file>` and the file is unchanged (bytes compared)
### SPEC-0028/E2E-005: repeated call
- Given a deck embedded by one call / When the tool is called again / Then the file is byte identical to after the first call and the counts are the same
### SPEC-0028/E2E-006: nothing to embed
- Given a Breathe deck with its decoration block and no decoration class and no named picture / When the tool is called / Then `classes` is 0, `pictures` is 0, and the `summary` starts with `<file>: 0 background and icon classes, 0 pictures embedded,`
### SPEC-0028/E2E-007: no decoration block
- Given a presentation with no `breathe:assets` block in its style / When the tool is called / Then `ToolError` `<file> has no breathe:assets block in its <style>` and the file is unchanged
### SPEC-0028/E2E-008: the list of agent operations (modified test)
- Level / Location: `tests/test_deck_tools_surface.py::test_the_server_core_and_audit_agree_on_the_final_tools`
- Then `registered_tool_names()` has 23 names equal to `FINAL_TOOLS` (which now includes `breathe_inline`), the `## Tools` section of `skill/core.md` lists the same 23, and `skill-audit` exits 0

## Constraints
- Files not to touch: `breathe/inline.py`, `cli.py`, the other tests.
- Dependencies not to add: none.
- Scope boundary: README, AGENTS.md and the architecture doc are US-0159.

## Definition of done
- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_breathe_inline.py`, `tests/test_deck_tools.py` unchanged and green. Modified existing test: E2E-008 only.
- [ ] One commit `US-0158: the breathe_inline tool, its skill line and tests`, body with `Summary:`, `Spec: SPEC-0028` and the requirement ids.
