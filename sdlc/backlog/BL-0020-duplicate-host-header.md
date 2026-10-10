---
Id: BL-0020
Title: Answer 400 to a request carrying several Host headers
Nature: BUG
Source: US-0002 review (SPEC-0005), /sdlc-implement 2026-10-10
Created: 2026-10-10
Severity: Low
Fingerprint: hardening:src/mcp_htmleditor/http_server.py:host = self.headers.get("Host", "")
---

## What

With two `Host` headers, the request gate reads the first one (`self.headers.get("Host")` in
`_refuse_untrusted_request`, `src/mcp_htmleditor/http_server.py`) and serves the request. RFC 9112
section 3.2 says a server must answer 400 to a request with more than one `Host` header.

## Why

Not an exploitable bypass here (single hop, no proxy in front), but a proxy that reads the other
header would disagree with the gate.

## Evidence

US-0002 review: both header orders tested live, first header wins.

## Notes

Next: `/sdlc-analysis BL-0020`.
