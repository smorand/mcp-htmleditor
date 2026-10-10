---
Id: BL-0011
Title: Pass the serve poll interval to Settings instead of writing the environment
Nature: DEBT
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Low
Fingerprint: doc-contradicts-code:src/mcp_htmleditor/cli.py:os.environ["HTMLEDITOR_POLL_INTERVAL"] = str(poll)
---

## What

`serve --poll` sets `os.environ["HTMLEDITOR_POLL_INTERVAL"]` (`src/mcp_htmleditor/cli.py:165`).

## Why

`AGENTS.md` and SPEC-0001 DEC-010: configuration only through `Settings`, no `os.environ` elsewhere.

## Evidence

`src/mcp_htmleditor/cli.py:165`.

## Notes

Next: `/sdlc-spec --debt BL-0011`.
