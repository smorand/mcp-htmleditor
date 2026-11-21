# US-0170: style the AI suggestions block

> Spec: SPEC-0032 (sdlc/specs/SPEC-0032-suggestions-block-style/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 3
> Closes spec: yes

## Objective
The AI suggestions block of the requests panel looks like the requests above it. Closes SPEC-0032.

## Requirements covered
- SPEC-0032/FR-NEW-001: WHILE the requests panel is open THE Requests context SHALL show the heading `AI suggestions (N)` in the same size (12 px), weight (600) and colour (`#f4f4f4`) as the heading `Requests (N)`, with at least 16 px of space above it separating it from the requests list.
- SPEC-0032/FR-NEW-002: each suggestion is a card like a request: background `#262626`, 1 px border `#393939`, padding 6 px by 8 px, title `#f4f4f4` weight 600, reason `#c6c6c6`, the button under them aligned left, a 6 px gap between cards.
- SPEC-0032/FR-NEW-003: `Apply` has background `#0f62fe` and white text; `Applied` is disabled with background `#393939`, text `#8d8d8d`, cursor `default`; no white button on the dark panel; the focus ring stays visible.

## Independent Test
`make test ARGS='tests/test_suggestions_style_e2e.py tests/test_review_apply_e2e.py'` green, `make check` green.

## Design excerpt
### Decisions
DEC-001 the colours and spacing of the requests list; DEC-002 Carbon blue for Apply, gray for Applied.
### Contracts
In `src/mcp_htmleditor/static/editor.css` after the rule `#requests-list .request-text` (line ~528), add exactly:
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
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor.css` | modify |
| `tests/test_suggestions_style_e2e.py` | create |
| `.agent_docs/testing.md` | modify (file map row; keep within 220 lines) |
### Existing patterns
`tests/test_review_apply_e2e.py`: `_open(page, deck, heading)`, `_write_review(deck, items)`, `_row(page, id)`, `s1()`, `s2()`, `POLL_MS`, `served_deck`, `suggestion(...)` from `tests/test_review_write.py`.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc. In `tests/test_suggestions_style_e2e.py`, read computed styles with `page.evaluate`.
### SPEC-0032/E2E-001: heading
- Given 2 suggestions written, panel open / Then `#suggestions-heading` has font size `12px`, weight `600`, colour `rgb(244, 244, 244)`, the same three values as `#requests-heading`, and its top edge is at least 16 px below the bottom of `#requests-list`
### SPEC-0032/E2E-002: card
- Given the same / Then a suggestion `li` has background `rgb(38, 38, 38)`, border `1px` `rgb(57, 57, 57)`, padding `6px 8px`; its `.suggestion-title` is `rgb(244, 244, 244)` weight 600; `.suggestion-why` is `rgb(198, 198, 198)`; its button's left edge equals the title's left edge; the vertical gap between two cards is 6 px
### SPEC-0032/E2E-003: long text
- Given a suggestion with a 60 character title without space and a 300 character reason / Then the card's right edge does not pass the panel's inner right edge and `#requests-side` has `scrollWidth <= clientWidth`
### SPEC-0032/E2E-004: Apply button
- A suggestion not applied has an `Apply` button with background `rgb(15, 98, 254)` and colour `rgb(255, 255, 255)`
### SPEC-0032/E2E-005: Applied state
- When the person presses `Apply` / Then the button reads `Applied`, is disabled, has background `rgb(57, 57, 57)`, colour `rgb(141, 141, 141)`, cursor `default`

## Constraints
- Files not to touch: `editor-requests.js`, other CSS rules, existing tests.
- Dependencies not to add: none.

## Definition of done
- [ ] RED evidence for E2E-001, E2E-002, E2E-004, E2E-005 before the CSS (E2E-003 may already pass if the default wraps).
- [ ] Every test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_review_apply_e2e.py`, `tests/test_request_loop_acceptance.py` unchanged and green.
- [ ] Docs updated: `.agent_docs/testing.md`.
- [ ] One commit `US-0170: style the AI suggestions block`, body with `Summary:`, `Spec: SPEC-0032` and the requirement ids.
