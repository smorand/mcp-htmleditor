---
Id: BL-0019
Title: Authenticate the preview server when it listens beyond loopback
Nature: BUG
Source: analysis SPEC-0005 (class sweep)
Created: 2026-10-10
Severity: High
Fingerprint: security:Dockerfile:HTMLEDITOR_HOST=0.0.0.0
Decision: left exploitable by user decision on 2026-10-10 (answer "go" to SPEC-0005 question 5, default a: defer token authentication to its own spec)
---

## What

Class: network clients reach request handlers that read or modify the edited document without
authentication (CWE-306). The container binds all interfaces and publishes the port.

## Why

Origin and host checks (SPEC-0005) stop browsers, not a direct network client.

## Evidence

`Dockerfile:33` (`HTMLEDITOR_HOST=0.0.0.0`), `docker-compose.yml:16`, routes `src/mcp_htmleditor/http_server.py:106` to `:136`.

## Notes

Terse on purpose: public repository. Next: `/sdlc-spec BL-0019` (token auth is a new capability).
