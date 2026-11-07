---
Id: BL-0035
Title: Decide the four open questions inherited from the legacy SPEC-0001
Nature: unknown
Source: analysis SPEC-0016
Created: 2026-11-08
---

## What

BL-0006 carried four open questions of the legacy retrospective spec. SPEC-0016 consumed BL-0006
for its FR rows only; these questions were not in its scope and move here unchanged:

- TBD-005: no size limit on images embedded in base64.
- TBD-006: no server guard for concurrent human and agent writes (SPEC-0009 serializes browser
  saves in one process, DEC-020; cross process writers are not locked).
- TBD-007: stale `server_pid` in a server record left by a process that exited.
- TBD-009: fullscreen behavior when no slide is active (empty deck or malformed HTML).

## Why

Each is a behavior nobody decided; a product owner reading the legacy spec may assume one.

## Evidence

Legacy text: `git show 5e22a15:sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md`, lines 764 to 768
(TBD-005 to TBD-009); EXC-008c at line 181. `src/mcp_htmleditor/state.py:203` to `:219`
reports the recorded `pid` without checking it is alive (TBD-007).
`sdlc/specs/SPEC-0009-reliable-saves/design.md:312` DEC-020 (TBD-006).

## Notes

SPEC-0016/BR-020 keeps reporting the recorded port and pid; TBD-007 decides whether a dead pid is
reported. Each question can become its own entry once triaged.
