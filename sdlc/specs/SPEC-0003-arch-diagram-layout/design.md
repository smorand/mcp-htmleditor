# Architecture diagram layout and QA checklist: Design (as-built)

> Spec: SPEC-0003
> Status: as-built
> Generated on: 2026-10-10 at 2521c331564328c9ca35fbfef372586cadbc12dd

## 1. Components

| Component | Responsibility | Location |
|---|---|---|
| Layout engine | Parse topology, compute `PctBox`es, route edges, write attributes | `src/mcp_htmleditor/arch_layout.py` |
| Checklist resolver | Search path and read | `src/mcp_htmleditor/arch_checks.py` |
| Entry points | CLI `arch-layout`, `arch-checklist`; MCP `layout_arch_diagram`; HTTP `POST /arch-layout` | `cli.py:217`, `mcp_server.py:166`, `http_server.py:136` |

## 2. Flows

`layout_file` (`arch_layout.py:1176`) parses the file, filters by `data-diagram-id` (`:1191`), runs `_layout_diagram` (`:1101`) per diagram: row geometry by `data-height-weight` (`:276`), slots by `data-span` (`:281`) via `_row_slots` (`:374`) and `_compute_col_boxes` (`:351`), `_write_node_box` (`:430`) skips `data-layout="manual"` (`:436`), edges (`:479`, `:542`, `:597`, `:717`), lanes (`:1014`), collision self check, then writes the file once.

## 3. Interfaces

Elements: `data-type` = `arch-diagram`, `arch-row`, `arch-node`, `arch-col`, `arch-spacer`, `arch-edge` (`data-from`, `data-to`, `data-step`, `data-color`), `arch-lane` (`data-rows`). Outputs: `data-x`, `data-y`, `data-width`, `data-height` in percent plus inline styles. CLI prints warnings on stderr and a count on stdout (`cli.py:228`).

## 4. Data and state

Edits the HTML file in place. Checklist file `arch-diagram-checklist.md`.

## 5. Configuration

| Name | Source | Default | Evidence |
|---|---|---|---|
| `HTMLEDITOR_ARCH_CHECKS_DIR` | env | `~/.config/mcp-htmleditor/arch-checks` | `arch_checks.py:41` |
| bundled checklist | repo | `skill/checks/arch-diagram-checklist.md` | `arch_checks.py:27` |

## 6. Observability

Lane errors logged with `logger.warning` (`arch_layout.py:1027`). No dedicated span observed.

## 7. Decisions (observed)

| ID | Decision | Evidence | Rationale |
|---|---|---|---|
| DEC-001 | Agent authors topology only, positions are computed | `arch_layout.py:3` | module docstring |
| DEC-002 | Edges skipping more than one row are out of scope V1, routed without check | `arch_layout.py:1154` | `skill/types/arch-diagram.md` |
| DEC-003 | Checklist lives in user config, never in code, no cache | `arch_checks.py:57` | function docstring |

## 8. Requirement to code map

| Requirement | Files |
|---|---|
| SPEC-0003/FR-001..FR-003, FR-010 | `arch_layout.py:1101`, `:1113`, `:1176`, `:1191` |
| SPEC-0003/FR-004..FR-006 | `arch_layout.py:276`, `:281`, `:351`, `:374`, `:436` |
| SPEC-0003/FR-007..FR-009 | `arch_layout.py:479`, `:542`, `:597`, `:717`, `:956`, `:986`, `:1135`, `:1148`, `:1154`, `:1169` |
| SPEC-0003/FR-011, FR-012 | `arch_checks.py:39`, `:57`, `:64` |
