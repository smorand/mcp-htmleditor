# BL-0026: Stale pointers to removed skill files

Nature: DEBT
Origin: US-0034 (SPEC-0006), reported by its implementer; US-0033 reported the same for config.py.

## Evidence

Comments, docstrings and docs still name files moved to `docs/skill-archive/`:
- `src/mcp_htmleditor/config.py:178` (skill/workflow-arch-qa.md)
- `src/mcp_htmleditor/arch_layout.py:12`, `:101`, `:390`
- `src/mcp_htmleditor/cli.py:260`
- `src/mcp_htmleditor/static/editor.js:259`
- `.agent_docs/html-conventions.md:44` (skill/types/medical.md)

## Proposal

One DEBT story: replace each by `mcp-htmleditor skill --type <topic>`, add a structural test (`rg` for `skill/types` and `skill/workflow-` outside `docs/skill-archive/` and `sdlc/`). Supersedes BL-0021 and BL-0025 in part.
