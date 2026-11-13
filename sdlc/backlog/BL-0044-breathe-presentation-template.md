# BL-0044: Breathe as a first class presentation template

Nature: FEAT
Origin: user request 2026-11-14 (second talk to build from it on 2026-11-15).

## What

Ship the Breathe congress template of Dr Lamya CHRIF MORAND (direction B, "Editorial, airway as a story line")
as a template of the editor: listed, created with `new`, reference deck with every layout, layout picker,
lint charter, faithful PPTX export (repainted from the rendered HTML, notes), asset generator and embedder,
skill topic. Serve the files next to the edited deck so decks can link pictures instead of inlining them.

## Why

Today the template lives outside the product (`~/projects/lamya/presentations/_template/breathe/`) and works
by pretending to be the `medical` charter (`--med-teal`), with three side scripts (`breathe_inline.py`,
`breathe_pptx.py`, `verify.sh`) run by hand after every export. A bootstrap dropped in the templates folder
is not listed and is detected as Carbon.

## Evidence

- Technical brief: `~/projects/lamya/presentations/WABIP_2026-12_Melbourne/research/produit/PRODUIT.md`
  (13 integration points).
- Source of truth: `~/projects/lamya/presentations/_template/breathe/` (template, assets, tools, README).
- Real deck: `~/projects/lamya/presentations/WABIP_2026-12_Melbourne/deck/wcbip2026-v1.html`.
- `src/mcp_htmleditor/http_server.py:295`: any other GET path answers 404, so relative pictures never load in
  the editor (gotcha recorded in the deck's `.agent_docs/deck.md`).
