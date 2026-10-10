---
Id: BL-0005
Title: Protect the preview server write endpoints when reachable beyond loopback
Nature: BUG
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: High
Fingerprint: security:src/mcp_htmleditor/http_server.py:Access-Control-Allow-Origin
---

## What

Class: missing authentication and permissive cross origin policy on state changing HTTP routes
(CWE-306, CWE-942). Locations: CORS header `src/mcp_htmleditor/http_server.py:87`, save route
`src/mcp_htmleditor/http_server.py:129`, container bind `Dockerfile:33`, `docker-compose.yml:16`.

## Why

The default local bind limits exposure; the container image binds all interfaces.

## Evidence

See locations above. Legacy TBD-008 already flagged the container bind.

## Notes

Kept terse: the repository is public. Next: `/sdlc-analysis --security BL-0005`.
