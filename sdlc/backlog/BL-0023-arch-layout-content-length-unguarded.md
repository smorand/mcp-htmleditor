---
Id: BL-0023
Title: Guard the Content-Length of the arch layout endpoint
Nature: BUG
Source: design SPEC-0009
Created: 2026-11-03
Severity: Low
Fingerprint: bug:src/mcp_htmleditor/http_server.py:358-int-Content-Length
---

## What

The `/arch-layout` handler reads `int(self.headers.get("Content-Length", 0))` with no validation and no size cap, like the save endpoint did before SPEC-0009.

## Why

A non numeric header raises an unhandled error; a huge value is read into memory.

## Evidence

`src/mcp_htmleditor/http_server.py:358-360`.

## Notes

SPEC-0009 FR-NEW-007 scopes its checks to the save endpoint only. Next: `/sdlc-analysis BL-0023`.
