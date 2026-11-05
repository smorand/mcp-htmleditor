# BL-0030: Style the AI suggestions block in the requests side panel

Nature: FEAT
Origin: US-0058 (SPEC-0010); its constraints forbid editing editor.css.

## Evidence

`src/mcp_htmleditor/static/editor-requests.js` (suggestions heading and list) is unstyled: the `h2` is large with no margin against
the requests list, and `button.suggestion-apply` is a white default button on the dark aside (screenshot taken by the reviewer).

## Proposal

A small CSS story: heading size and spacing, list item layout (title, why, Apply), button colours matching the aside, disabled `Applied` look.
