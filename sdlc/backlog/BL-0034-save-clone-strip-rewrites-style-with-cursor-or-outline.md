# BL-0034: A save rewrites a style that holds `cursor` or `outline`

Nature: BUG (hint)
Origin: independent audit of SPEC-0015 (US-0093). Pre-existing, not introduced by SPEC-0015.

## Evidence

The save clone strips the editor's look with `el.style.outline = ''; el.style.cursor = '';` on every
`[contenteditable]` element (`src/mcp_htmleditor/static/editor-save.js:29`). Writing through the style object
reserializes the whole attribute when it held one of those properties: an editable element with
`style="cursor:pointer;color:#0F62FE"` is saved as `style="color: rgb(15, 98, 254);"` after an unrelated save.
The same splitter case is open for a `;` inside a CSS comment in a style attribute (`splitStyleDeclarations` in
`editor-width.js` does not know comments).

## Proposal

Strip `outline` and `cursor` as text, the way SPEC-0015 DEC-003 rebuilds a style: split the attribute text into
declarations, drop only the ones the editor added, and write the rest back verbatim with
`setAttribute('style', text)` (or remove the attribute when nothing is left). Teach the splitter `/* ... */`.
Needs a story with a browser test on a fixture holding `cursor:pointer;color:#0F62FE`.
