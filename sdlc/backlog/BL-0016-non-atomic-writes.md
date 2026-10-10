---
Id: BL-0016
Title: Write the edited file and the state file atomically
Nature: DEBT
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Low
Fingerprint: debt:src/mcp_htmleditor/http_server.py:target.write_text(html, encoding="utf-8")
---

## What

Saves write in place with `write_text`: `src/mcp_htmleditor/http_server.py:308`,
`src/mcp_htmleditor/state.py:66`.

## Why

A crash mid write truncates the user's document; the agent may also read a half written file.

## Evidence

Lines above; no temp file plus rename anywhere in `src/`.

## Notes

Next: `/sdlc-spec --debt BL-0016`.
