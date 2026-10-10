---
Id: BL-0006
Title: Arbitrate legacy spec statements the code contradicts
Nature: BUG
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Medium
Fingerprint: legacy-spec-contradicts-code:sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:legacy FR-007
---

## What

The legacy retrospective spec (now SPEC-0001, rewritten as-built) promised behaviors the code
does not have. As-built follows the code; someone must decide whether the code or the old promise
is right.

| Legacy statement | Code |
|---|---|
| FR-007 / E2E-009: save to a template path is refused (non 2xx, e.g. 403) | skipped with 200 `{"ok": true, "skipped": ...}` `src/mcp_htmleditor/http_server.py:302` |
| FR-010: state reloaded at init | `EditorState.load()` has no production caller (`src/mcp_htmleditor/state.py:68`) |
| FR-016 / EXC-005a: pandoc absent gives default styles, no exception | export fails explicitly `src/mcp_htmleditor/cli.py:277` |
| FR-018: deck export warns on vector figures | inline vectors dropped silently `src/mcp_htmleditor/export/to_pptx.py:95` |
| FR-028: End goes to last slide whatever the focus | parent relay has no End branch `src/mcp_htmleditor/static/editor.js:151` |
| FR-009: exactly 6 tools; FR-012: exactly 5 charters | 7 tools, 8 templates (growth, likely fine) |

Open questions kept from the legacy spec: TBD-005 (no size limit on embedded images), TBD-006 (no
server guard for concurrent human and agent writes), TBD-007 (stale `server_pid`), TBD-009
(fullscreen with no active slide).

## Why

A product owner may rely on the old statements (silent template skip looks like a successful save).

## Evidence

Legacy text: `git show 5e22a15:sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md`, mapping table in
`sdlc/specs/SPEC-0001-mcp-htmleditor/design.md` § Legacy mapping.

## Notes

Next: `/sdlc-analysis` per row worth restoring (FR-007 and FR-028 first).
