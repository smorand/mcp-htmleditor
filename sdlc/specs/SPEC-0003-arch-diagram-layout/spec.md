# Architecture diagram layout and QA checklist: Specification (as-built)

> Id: SPEC-0003
> Nature: FEAT
> Status: as-built
> Area: architecture diagram layout and QA checklist
> Generated on: 2026-10-10 by /sdlc-retro-spec at 2521c331564328c9ca35fbfef372586cadbc12dd
> Confidence: high (see Confidence notes)

## 1. Summary

The agent describes an architecture diagram as a topology (rows of nodes, nested columns, spacers,
edges, lanes) and asks the tool to compute every position and connector route. The computed file
is then reviewed against a checklist the user can edit without reinstalling.

## 2. Current State

### 2.1 How it works today

The same layout run is reachable from the command line, the agent interface and the browser. It
rewrites positions in place, leaves hand placed nodes and old style diagrams alone, routes edges
around obstacles, and reports problems as warnings instead of failing. A separate command prints
the review checklist, taken from the user's copy when present.

### 2.2 Existing specifications governing this area

SPEC-0001/FR-009 (the agent operation exists). SPEC-0002/FR-017 (manual drag marks a node manual).

### 2.3 Existing test coverage

32 unit tests (28 layout, 4 checklist). Every requirement has at least one test.

## 3. Scope

### 3.1 Covered

Topology elements, layout run, scoping to one diagram, idempotency, manual lock, legacy diagrams,
edge routing and badges, warnings, checklist resolution.

### 3.2 Not covered

Deck export of diagrams (SPEC-0001/FR-013), QA protocol run by a review agent (documentation).

## 4. Actors

| Actor | Role |
|---|---|
| LLM agent | Authors topology, runs layout, spawns the QA review |
| Human editor | Drags nodes, edits the checklist |

## 5. Usage Scenarios

### SC-001: Lay out a declarative diagram
Agent writes rows, nodes and edges, runs layout on the file, gets the count of diagrams updated
and the warnings.

### SC-002: Review against the checklist
Agent prints the checklist and hands it to a review agent.

## 6. Functional Requirements

| ID | Requirement (EARS) | Scenario | Evidence |
|---|---|---|---|
| FR-001 | WHEN layout runs on a file THE system SHALL compute and write node boxes, connector routes and lane boxes for every diagram that has at least one row, and report how many diagrams were updated. | SC-001 | `src/mcp_htmleditor/arch_layout.py:1176`, `src/mcp_htmleditor/arch_layout.py:1101` |
| FR-002 | IF a diagram has no row THEN THE system SHALL leave it untouched. | SC-001 | `src/mcp_htmleditor/arch_layout.py:1113` |
| FR-003 | WHEN a diagram id is given THE system SHALL lay out only the diagram carrying that id. | SC-001 | `src/mcp_htmleditor/arch_layout.py:1191` |
| FR-004 | The system SHALL distribute rows vertically by their height weight (default equal) and nodes horizontally by their span (default 1). | SC-001 | `src/mcp_htmleditor/arch_layout.py:276`, `src/mcp_htmleditor/arch_layout.py:281` |
| FR-005 | The system SHALL stack the nodes of a nested column inside its row slot, writing their positions relative to that column, and reserve width for spacers without drawing anything. | SC-001 | `src/mcp_htmleditor/arch_layout.py:351`, `src/mcp_htmleditor/arch_layout.py:374` |
| FR-006 | The system SHALL NOT move a node marked as manually placed. | SC-001 | `src/mcp_htmleditor/arch_layout.py:436` |
| FR-007 | The system SHALL route edges within a row or between adjacent rows, exiting sideways when the horizontal offset dominates and detouring around nodes in the way. | SC-001 | `src/mcp_htmleditor/arch_layout.py:479`, `src/mcp_htmleditor/arch_layout.py:542`, `src/mcp_htmleditor/arch_layout.py:597`, `src/mcp_htmleditor/arch_layout.py:717` |
| FR-008 | WHEN an edge has a step number THE system SHALL place a numbered badge on the segment midpoint, pushed clear of narrow gutters; an edge color overrides the default accent. | SC-001 | `src/mcp_htmleditor/arch_layout.py:956`, `src/mcp_htmleditor/arch_layout.py:986` |
| FR-009 | IF a node has no id, an edge names an unknown node, an edge skips more than one row, or nodes overlap after layout THEN THE system SHALL add a warning; the unknown node edge is dropped, the others are still written. | SC-001 | `src/mcp_htmleditor/arch_layout.py:1135`, `src/mcp_htmleditor/arch_layout.py:1148`, `src/mcp_htmleditor/arch_layout.py:1154`, `src/mcp_htmleditor/arch_layout.py:1169` |
| FR-010 | WHEN layout runs twice on the same file THE system SHALL produce identical output. | SC-001 | `src/mcp_htmleditor/arch_layout.py:1176` |
| FR-011 | WHEN the checklist is requested THE system SHALL print the user's checklist if present, else the bundled one, re-read on every call; an operator setting moves the user location. | SC-002 | `src/mcp_htmleditor/arch_checks.py:39`, `src/mcp_htmleditor/arch_checks.py:57` |
| FR-012 | IF no checklist exists anywhere THEN THE system SHALL return empty content without failing. | SC-002 | `src/mcp_htmleditor/arch_checks.py:64` |

## 7. Non-Functional Requirements

None observed.

## 8. End-to-End Tests

| ID | Covers | Test | Level | State |
|---|---|---|---|---|
| E2E-001 | FR-001, FR-009 | `tests/test_arch_layout.py::test_layout_writes_no_collision` | unit | green |
| E2E-002 | FR-002 | `tests/test_arch_layout.py::test_legacy_diagram_without_rows_is_left_untouched` | unit | green |
| E2E-003 | FR-003 | `tests/test_arch_layout.py::test_diagram_id_filter_restricts_the_update` | unit | green |
| E2E-004 | FR-004 | `tests/test_arch_layout.py::test_same_row_nodes_share_mid_y` | unit | green |
| E2E-005 | FR-005 | `tests/test_arch_layout.py::test_nested_node_percentages_are_written_relative_to_its_col`, `tests/test_arch_layout.py::test_arch_spacer_aligns_a_node_above_a_specific_column` | unit | green |
| E2E-006 | FR-006 | `tests/test_arch_layout.py::test_manual_locked_node_keeps_its_position` | unit | green |
| E2E-007 | FR-007 | `tests/test_arch_layout.py::test_detour_avoids_an_intervening_column_in_the_same_row`, `tests/test_arch_layout.py::test_side_exit_used_when_target_is_more_horizontal_than_vertical_offset` | unit | green |
| E2E-008 | FR-008 | `tests/test_arch_layout.py::test_edge_step_badge_sits_on_the_true_segment_midpoint`, `tests/test_arch_layout.py::test_edge_data_color_overrides_the_default_accent` | unit | green |
| E2E-009 | FR-009 | `tests/test_arch_layout.py::test_row_skip_edge_is_flagged_out_of_scope` | unit | green |
| E2E-010 | FR-010 | `tests/test_arch_layout.py::test_idempotent_second_run_produces_identical_output` | unit | green |
| E2E-011 | FR-011 | `tests/test_arch_checks.py::test_env_override_wins_over_the_bundled_copy`, `tests/test_arch_checks.py::test_read_checklist_returns_the_bundled_content` | unit | green |
| E2E-012 | FR-012 | `tests/test_arch_checks.py::test_missing_file_at_every_location_returns_empty_string` | unit | green |

## 9. Glossary

| Term | Meaning |
|---|---|
| Declarative diagram | Diagram authored as topology, at least one row |
| Legacy diagram | Diagram with hand written positions, no row |
| Manual node | Node a human dragged, frozen by layout |

## 10. Confidence notes

- The legacy overlap checker returns nothing for declarative diagrams (`src/mcp_htmleditor/arch_layout.py:1060`);
  internal, not written.
- Lane with an invalid row range is skipped with a log line, not a report warning
  (`src/mcp_htmleditor/arch_layout.py:1027`); written nowhere, observable only in logs.
- Tests are unit level on the layout function; CLI, agent and browser entry points to layout are
  not exercised end to end (counted green on the function, noted here).
