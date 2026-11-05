# BL-0029: write_review with a non list argument answers a pydantic text on the tool

Nature: BUG
Origin: US-0057 (SPEC-0010), found by its reviewer.

## Evidence

`write_review(file, suggestions: list[Any])` (DEC-006). Through a `fastmcp.Client`, `suggestions={}` / `"x"` / `None` is rejected by
pydantic before the service runs: `1 validation error for call[write_review] suggestions Input should be a valid list [type=list_type ...]`.
The command `review <file> --write bad.json` with `{}` prints `error: Review must be a list of suggestions` (service message).
FR-NEW-004 asks for the same text on both surfaces. DEC-006's own rationale ("the service message wins over a schema error") does not hold for non lists.

## Proposal

Type the parameter `Any` (not `list[Any]`) so the service message `Review must be a list of suggestions` is returned; add a tool test for `{}`.
Needs a SPEC-0010 amendment of DEC-006 (implementation never edits the design).
