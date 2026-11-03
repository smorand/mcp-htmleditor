---
Id: BL-0022
Title: Close the listening socket when the HTTP server stops
Nature: BUG
Source: design SPEC-0009
Created: 2026-11-03
Severity: Low
Fingerprint: bug:src/mcp_htmleditor/http_server.py:stop_http_server-no-server_close
---

## What

`stop_http_server` calls `shutdown()` but never `server_close()`, so the port stays bound until the process exits.

## Why

`stop_server` followed by `start_server` on the same port in one process can fail to bind. The tool contract is "stops the HTTP server".

## Evidence

`src/mcp_htmleditor/http_server.py:722-724`: `_server_instance.shutdown()` then the references are dropped, no `server_close()`.

## Notes

Reproduce first with a test that stops then restarts on the same port. Next: `/sdlc-analysis BL-0022`.
