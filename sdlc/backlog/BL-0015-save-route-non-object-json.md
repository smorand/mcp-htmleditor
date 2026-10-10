---
Id: BL-0015
Title: Answer 400 when the save body is valid JSON but not an object
Nature: BUG
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Low
Fingerprint: suspected-defect:src/mcp_htmleditor/http_server.py:html: str = data.get("html", "")
---

## What

`POST /content` with a JSON array or string body reaches `data.get` on a non dict; the
`AttributeError` is not in the caught tuple `(json.JSONDecodeError, KeyError)`.

## Why

Unhandled exception in the request handler instead of the documented 400 `Invalid JSON body`.

## Evidence

`src/mcp_htmleditor/http_server.py:281` to `:283`.

## Notes

Not reproduced by running the server. Next: `/sdlc-analysis BL-0015`.
