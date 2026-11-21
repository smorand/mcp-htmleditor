# SPEC-0032: AI suggestions block look, design

> Spec: sdlc/specs/SPEC-0032-suggestions-block-style/spec.md
> Nature: FEAT
> Depth: S
> Security: n/a
> Designed on: 2026-11-20
> Target tier: 2 (default)

## 1. Stack and skills
Existing stack (plain CSS in `src/mcp_htmleditor/static/editor.css`, Playwright e2e). No dependency.

## 2. Approaches
### Chosen: add rules next to the requests rules, same tokens
Pros: one place, same colours as the requests list (DEC-001). Rejected: inline styles set in `editor-requests.js` (mixes behavior and look).

## 3. Architecture
Stylesheet only. The block's markup (ids `#suggestions-heading`, `#suggestions-list`, classes `.suggestion-title`, `.suggestion-why`, `.suggestion-apply`) is unchanged.

## 5. Contracts and interfaces
In `editor.css`, after `#requests-list .request-text` (line 528):
```
#suggestions-heading { margin: 16px 0 8px; color: #f4f4f4; font-size: 12px; font-weight: 600; }
#suggestions-list { list-style: none; display: flex; flex-direction: column; gap: 6px; }
#suggestions-list li { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 6px 8px;
  background: #262626; border: 1px solid #393939; min-width: 0; }
#suggestions-list .suggestion-title { color: #f4f4f4; font-weight: 600; line-height: 1.4; overflow-wrap: anywhere; }
#suggestions-list .suggestion-why { color: #c6c6c6; line-height: 1.4; overflow-wrap: anywhere; }
#suggestions-list .suggestion-apply { padding: 4px 10px; border: 0; background: #0f62fe; color: #fff; font: inherit; cursor: pointer; }
#suggestions-list .suggestion-apply:hover:not(:disabled) { background: #0353e9; }
#suggestions-list .suggestion-apply:disabled { background: #393939; color: #8d8d8d; cursor: default; }
```
The `h2` default margin is overridden by the shorthand; `overflow-wrap: anywhere` and `min-width: 0` keep long text inside the card (E2E-003).

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/static/editor.css` | modify | FR-NEW-001..003 | US-0170 |
| `tests/test_suggestions_style_e2e.py` | create | E2E-001..005 | US-0170 |
| `.agent_docs/testing.md` | modify: file map | docs | US-0170 |
Affected existing tests: none.

## 9. Test strategy
Browser tests on computed styles, reusing the helpers of `tests/test_review_apply_e2e.py` (`_open`, `_write_review`, `_row`, `s1`, `s2`).

## 10. Decisions log
- **DEC-001:** the suggestions use the colours and spacing tokens of the requests list. **Obliged by:** SPEC-0032/FR-NEW-001, FR-NEW-002. **Source:** existing code. **Evidence:** `editor.css:517-528`.
- **DEC-002:** the Apply button colours are Carbon blue `#0f62fe` (already the editor's accent, `editor.css:` width bar) and gray `#393939` for the applied state. **Obliged by:** SPEC-0032/FR-NEW-003.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0170 | style the AI suggestions block | P1 | FR-NEW-001, FR-NEW-002, FR-NEW-003 | main | 2 | yes |
