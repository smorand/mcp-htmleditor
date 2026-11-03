---
Id: BL-0021
Title: Update code comments and docstrings that point to skill files SPEC-0006 moves
Nature: DEBT
Source: design SPEC-0006
Created: 2026-11-03
Severity: Low
Fingerprint: debt:comments-naming-skill-types-files
---

## What

Comments and docstrings name `skill/types/*.md` and `skill/workflow-*.md` files that SPEC-0006 moves to `docs/skill-archive/` and replaces with `skill/topics/*.md`.

## Why

After SPEC-0006 lands the references point to files that no longer exist.

## Evidence

`src/mcp_htmleditor/mcp_server.py:170`, `arch_layout.py:12,101,390`, `cli.py:223`, `export/to_pptx.py:21`, `static/editor.js:259,1023,1283`, `static/slide-layouts.js:159,306,339`, `tests/test_templates.py:78`, `tests/test_arch_layout.py:524,708,771`, `tests/test_undo_redo_e2e.py:63`, `tests/test_tab_title_e2e.py:103`. Also `README.md:414` names `.pi/skills/mcp-htmleditor/` while the routing skill installs under `dynamic-skills/`.

## Notes

Run after SPEC-0006 and SPEC-0012 land (line numbers shift). Next: `/sdlc-spec BL-0021`.
