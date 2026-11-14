# BL-0045: Agent tool for the Breathe embedding command

Nature: FEAT
Origin: deferred from SPEC-0023 (scope 3.2).

## What

Expose `mcp-htmleditor breathe-inline <file> [--link]` as an MCP tool (`breathe_inline(file, link=false)`), with
the same results and errors as the command line (SPEC-0007/FR-NEW-016 rule).

## Why

Agents reach the command line today; a tool saves a shell round trip and keeps the error surface uniform.

## Evidence

- `src/mcp_htmleditor/cli.py` (the `breathe-inline` command added by SPEC-0023).
- `skill/core.md` `## Tools` (a new tool needs its line, `skill-audit` enforces it).
