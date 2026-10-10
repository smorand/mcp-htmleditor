---
Id: BL-0010
Title: Cover the untested requirements of SPEC-0001
Nature: DEBT
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Medium
Fingerprint: untested-requirement:sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:E2E
---

## What

11 E2E rows of SPEC-0001 are `untested`: E2E-002 (FR-002 at CLI level), E2E-004 and E2E-005
(update window through a real MCP client), E2E-009 (template save), E2E-014 (CLI deck export with
no slide), E2E-023, E2E-024, E2E-025 (agent status, double start, busy explicit port), E2E-036 (no
document content in spans), E2E-045 (FR-030), E2E-046 (FR-034).

## Why

The agent interface has no end to end test at all (legacy TBD-002); HTTP export routes are only
checked by source text (`tests/test_http_export.py::test_export_routes_registered`).

## Evidence

`sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md` § 8. Legacy 12.2 holds Given/When/Then for most rows.

## Notes

Next: `/sdlc-retro-tests SPEC-0001` when available.
