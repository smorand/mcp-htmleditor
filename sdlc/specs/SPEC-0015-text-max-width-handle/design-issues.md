# SPEC-0015 design issues

## 2026-11-07 21:17: FR-003 and DEC-005 exclude `table`, the code excludes data tables only

Found by: independent audit of SPEC-0015 during US-0093.

- Spec: FR-003 and DEC-005 list `table` among the elements that never get a width bar.
- Code: `WIDTH_EXCLUDED` in `src/mcp_htmleditor/static/editor-width.js` uses `table:not([role="presentation"])`,
  so the layout tables of a mail (`role="presentation"`) are not excluded and their text gets a bar. E2E-031
  (tests/test_width_visibility_e2e.py) relies on that: the mail bootstrap's text sits in layout tables.
- Recommendation: amend FR-003 and DEC-005 through `/sdlc-spec` to state the rule the code applies (data tables
  excluded, layout tables marked `role="presentation"` allowed), with E2E-031 as its acceptance.
- Residual risk: a data table wrongly marked `role="presentation"` gets a bar on its cells' text blocks.
