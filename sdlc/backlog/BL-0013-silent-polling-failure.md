---
Id: BL-0013
Title: Surface polling failures in the browser instead of swallowing them
Nature: DEBT
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Low
Fingerprint: debt:src/mcp_htmleditor/static/editor.js:catch (e) { return; }
---

## What

`pollStatus` drops every error without a log (`src/mcp_htmleditor/static/editor.js:301`).

## Why

When the server stops, the page looks alive and saved, and the user keeps editing into the void.

## Evidence

`src/mcp_htmleditor/static/editor.js:301`: `catch (e) { return; }`.

## Notes

Next: `/sdlc-spec BL-0013` (a visible offline state is a behavior change).
