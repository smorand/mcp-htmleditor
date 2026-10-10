---
Id: BL-0014
Title: Share one DOM serialization between autosave and undo snapshots
Nature: DEBT
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Low
Fingerprint: debt:src/mcp_htmleditor/static/editor.js:function captureDomSnapshot(doc)
---

## What

`captureDomSnapshot` (`src/mcp_htmleditor/static/editor.js:370`) duplicates the stripping half of
`saveContent` (`src/mcp_htmleditor/static/editor.js:1398`), minus the doctype.

## Why

A fix to one (for example BL-0008) silently misses the other.

## Evidence

Both blocks back up `contentEditable`, `outline`, `cursor`, hide the two bars, detach drag artifacts.

## Notes

Handle with BL-0008. Next: `/sdlc-spec --debt BL-0014`.
