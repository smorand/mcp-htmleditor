---
Id: BL-0009
Title: Remove or wire EditorState.load, which nothing calls
Nature: DEBT
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Low
Fingerprint: dead-code:src/mcp_htmleditor/state.py:def load(self) -> None:
---

## What

`EditorState.load()` (`src/mcp_htmleditor/state.py:68`) is only called by tests.

## Why

Legacy DEC-003 justified the state file by "survive an agent restart"; without a reader the file is
write only.

## Evidence

`rg -n "state\.load|\.load\(" src` returns no match.

## Notes

Linked to BL-0006 (FR-010 row). Next: `/sdlc-spec --debt BL-0009` after BL-0006 decides.
