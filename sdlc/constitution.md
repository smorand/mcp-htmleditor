# Constitution (DRAFT, written by /sdlc-retro-spec on 2026-10-10, review before relying on it)

> Status: draft

| Rule | Source | Enforced by |
|---|---|---|
| `make check` (lint, format-check, typecheck, security, test-cov) passes before merge | `Makefile:139`, `AGENTS.md:15` | pre-commit runs ruff, ruff-format, mypy (`.pre-commit-config.yaml:16`, `:24`, `:32`); full gate by hand only (no CI, SPEC-0001 DEC-009). Red at 2521c33 (BL-0004) |
| Line coverage stays at or above 80 % | `pyproject.toml:174`, `AGENTS.md:15` | `make test-cov` |
| `make` is the only entry point for tooling | `AGENTS.md:11`, `.agent_docs/makefile.md` | nothing (convention only) |
| Configuration is read only through `Settings` | `AGENTS.md`, SPEC-0001 DEC-010 | nothing (convention only); one violation BL-0011 |
| Logs go to stderr or file, never stdout | `AGENTS.md:48`, `src/mcp_htmleditor/logging_config.py:97` | nothing (convention only) |
| Every slide template ships fullscreen support | `AGENTS.md:67`, `.agent_docs/html-conventions.md` | `tests/test_medical_template.py:86` for medical only; five reference decks violate it (BL-0007) |
| Static JS passes `node --check` | `AGENTS.md:83`, `.agent_docs/architecture.md:67` | nothing (not in `make check`) |
