---
Id: BL-0012
Title: Update documentation that no longer matches the code or the sdlc layout
Nature: DEBT
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Low
Fingerprint: stale-doc:AGENTS.md:Specifications live in `specs/*.md`
---

## What

- `AGENTS.md:104` and `:106` point to `specs/*.md` and `specs/BACKLOG.md`; both moved to `sdlc/`
  in this retro.
- `.agent_docs/architecture.md:25` lists routes without `/export/pptx`, `/export/docx`,
  `POST /arch-layout` (present at `src/mcp_htmleditor/http_server.py:118`, `:120`, `:136`).
- `skill/types/arch-diagram.md:121` says the step badge is not exported to decks; it is
  (`tests/test_export_pptx.py::test_arch_edge_badge_exports_as_a_numbered_circle`).
- `skill/types/medical.md:542` lists deck export defects "not fixed" (white background on dark
  slides); code now computes kind backgrounds (`src/mcp_htmleditor/export/to_pptx.py:667`). No test
  asserts the fill color, so the fix is unconfirmed.

## Why

Agents read these files as instructions.

## Evidence

Lines quoted above.

## Notes

Next: `/sdlc-retro-doc` when available.
