# US-0070: write_review answers the product message for a non list on the tool

> Spec: SPEC-0010 (sdlc/specs/SPEC-0010-request-loop/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0059
> min_tier: 2
> Files touched: 2
> Closes spec: yes

## Objective

Make the `write_review` tool return `Review must be a list of suggestions` for a non list argument, exactly like the command line, instead of a pydantic validation text.

## Requirements covered

- SPEC-0010/FR-NEW-004 (partial: parity of the review rules on the tool for a non list): The Editor SHALL give the same results for requests and review through the command line and the agent tool surface, the tool returning an error whose message is the command line error line without its `error: ` prefix.

## Evidence (drift found by the SPEC-0010 converge audit)

- `src/mcp_htmleditor/mcp_server.py:491`: `def write_review(file: str, suggestions: list[Any])`. Through `fastmcp.Client`, `suggestions={}`, `"x"` or `None` is rejected by pydantic: `1 validation error for call[write_review] suggestions Input should be a valid list [type=list_type ...]`; the command `review deck.html --write bad.json` with `{}` prints `error: Review must be a list of suggestions`.
- DEC-006 (SPEC-0010) says the service message must win over a schema validation error; for a non list it does not (BL-0029).

## Acceptance tests

- Given DECK, when the agent calls `write_review` with `suggestions` = `{}`, `"x"` and `5`, then the error is exactly `Review must be a list of suggestions` and the previous review is unchanged. `None` also gives that message.
- The valid path is unchanged: `write_review` with 2 valid suggestions returns `{"ok":true,"count":2}`.
- `mcp-htmleditor skill-audit` stays green.

## Constraints

- Files not to touch: `request_service.py` (the rule lives there), `cli.py`, `http_server.py`, `skill/*`.
- The parameter becomes `Any` (the service validates); no other tool changes; no new dependency.

## Definition of done

- [ ] RED evidence before the change; `make check` green.
- [ ] One commit `US-0070: write_review answers the product message for a non list on the tool`, body `Spec: SPEC-0010` and `FR-NEW-004`.
