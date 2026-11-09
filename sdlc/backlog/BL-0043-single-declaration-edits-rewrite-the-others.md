# BL-0043: Editor actions that set one declaration rewrite the others

Nature: BUG (hint; no authority states the form of the other declarations for these actions, so it may route FEAT)
Origin: deferred from SPEC-0020 (class sweep, section 1bis).
Decision: deferred by the 2026-11-09 run under the instruction "take recommended defaults"; not a security
finding.

## Evidence

Class: inline style text written by a person or an agent reaches a style object write that does not preserve
its text. These actions write the person's own change through the element's style object, which reserializes
the element's whole `style` attribute (hex colours to `rgb(...)`, spaces, comments dropped):

- Gantt task `Agrandir (+20%)` and `Réduire (-20%)`: `src/mcp_htmleditor/static/editor-menus.js:193`, `:198`.
- New arch node container: `editor-menus.js:280` (`position:relative` on the diagram).
- Arch diagram made a positioning context on edit mode entry and on wiring: `editor-drag.js:159`, `:179`.
- Arch node press: `editor-drag.js:195` writes `position:absolute` on every left press, even one that does not
  move, so an unrelated later save writes the node's reserialized style.
- Arch node move: `editor-drag.js:236-238` (`position`, `left`, `top`).

## Proposal

Rebuild the attribute as text (SPEC-0015 DEC-003, SPEC-0020/BR-003 splitter): replace or append only the
declarations the action owns and keep the others verbatim; a press without movement writes nothing. Test a
gantt task `style="left:0%; width:25%; background:#0F62FE"` grown once: `left:0%; width:30.0%; background:#0F62FE`.
