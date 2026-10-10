---
Id: BL-0017
Title: Cover the untested requirements of SPEC-0002
Nature: DEBT
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Medium
Fingerprint: untested-requirement:sdlc/specs/SPEC-0002-browser-editing/spec.md:E2E
---

## What

7 E2E rows of SPEC-0002 are `untested`: E2E-013 (format and insert bars), E2E-014 (autosave
timings), E2E-015 (status dot), E2E-016 (no reload on self save), E2E-017 (undo depth 50),
E2E-018 (navigation keys blocked while typing), E2E-019 (export download).

## Why

Autosave and reload are the paths a human hits on every keystroke (see BL-0008).

## Evidence

`sdlc/specs/SPEC-0002-browser-editing/spec.md` § 8.

## Notes

Next: `/sdlc-retro-tests SPEC-0002` when available.
