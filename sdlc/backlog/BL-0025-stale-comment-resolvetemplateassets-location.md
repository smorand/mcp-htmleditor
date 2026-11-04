---
Id: BL-0025
Title: Fix the comment that places resolveTemplateAssets in editor.js
Nature: DEBT
Source: implement US-0020 (SPEC-0012)
Created: 2026-11-03
Severity: Low
Fingerprint: debt:src/mcp_htmleditor/static/slide-layouts.js:192
---

## What

`src/mcp_htmleditor/static/slide-layouts.js:192` says "voir editor.js resolveTemplateAssets"; the function now lives in `src/mcp_htmleditor/static/editor-slides.js:89`.

## Why

A comment pointing to the wrong script after the SPEC-0012 split. The story constraint of US-0020 forbade touching `slide-layouts.js`.

## Evidence

`rg -n resolveTemplateAssets src/mcp_htmleditor/static` : definition at `editor-slides.js:89`, call at `editor-slides.js:63`, comment at `slide-layouts.js:192`.

## Notes

Group with BL-0021 (other stale references to moved files). Next: `/sdlc-spec BL-0025`.
