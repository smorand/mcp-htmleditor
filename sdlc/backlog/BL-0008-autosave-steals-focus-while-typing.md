---
Id: BL-0008
Title: Background autosave must not take focus or caret away from the zone being typed in
Nature: BUG
Source: retro-spec 20261010-123424 (user report 2026-10-10)
Created: 2026-10-10
Severity: Medium
Fingerprint: suspected-defect:src/mcp_htmleditor/static/editor.js:el.removeAttribute('contenteditable')
---

## What

User report: "When I'm editing on a page and there is an auto save, I'm losing the focus on the
current widget I'm writing ... the auto save, happening background, must not have any effect on
the current work."

## Why

Every typing pause of 800 ms triggers a save, so the interruption repeats all the time while writing.

## Evidence

- Typing schedules `saveContent` 800 ms after the last input: `src/mcp_htmleditor/static/editor.js:1394`.
- `saveContent` removes the `contenteditable` attribute from every editable element, including the
  focused one: `src/mcp_htmleditor/static/editor.js:1410`, then sets `contentEditable` back:
  `src/mcp_htmleditor/static/editor.js:1429`.
- No `getSelection` / range save or restore inside `saveContent` (`src/mcp_htmleditor/static/editor.js:1398` to `:1452`).
- Same stripping pattern in `captureDomSnapshot` (`src/mcp_htmleditor/static/editor.js:370`), run before
  structural actions.
- No test covers focus or caret across a save (SPEC-0002/E2E-014 untested).

## Notes

Not reproduced by running the browser during the retro. Next: `/sdlc-analysis BL-0008`.
