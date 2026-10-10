# mcp-htmleditor core: Specification (as-built)

> Id: SPEC-0001
> Nature: FEAT
> Status: as-built
> Area: core (templates, agent control, sync and save, export, configuration, observability, presentation mode)
> Generated on: 2026-10-10 by /sdlc-retro-spec at 2521c331564328c9ca35fbfef372586cadbc12dd
> Migrated from: specs/2026-08-07_16-31-00-mcp-htmleditor-retrospective.md on 2026-10-10
> Confidence: medium (see Confidence notes)

## 1. Summary

An HTML editor driven by an LLM agent. The agent creates a single HTML file from a named
template, writes it on disk inside a bracketed update window, and controls a local preview
server. A human sees the file rendered in the browser, edits it visually, and the saved file
stays free of editing artifacts. The document exports to a native slide deck or to a word
processing document carrying the chosen visual charter.

## 2. Current State

### 2.1 How it works today

The agent picks one of eight templates (three slide charters, three document charters, one mail,
one website) and gets a starter file. A local preview server shows the file in the browser and
reloads it when the file changes on disk. While the agent announces an update, the browser shows
a blocking overlay and does not reload until the update is closed. Browser saves are cleaned
before reaching disk. Export produces a 16:9 slide deck with native shapes, or a word document
through an external converter with charter letterhead. Several previews can run at once, each on
its own port.

### 2.2 Existing specifications governing this area

None before this one. This document replaces the free form retrospective spec of 2026-08-07.
Browser editing interactions are in SPEC-0002, architecture diagram layout in SPEC-0003.

### 2.3 Existing test coverage

46 E2E rows: 35 point to existing tests (5 browser e2e, the rest unit or integration), 11 are
`untested`. One existing test is `currently red` at baseline (E2E-044, depends on a free port
range on the machine).

## 3. Scope

### 3.1 Covered

Template catalog and file creation; agent control operations; preview, polling and save
cleaning; port selection; server state file; slide deck export; word document export;
configuration; logging and tracing; health; packaged skill; presentation (fullscreen) mode.

### 3.2 Not covered

In-browser editing interactions, autosave, undo/redo, tab title (SPEC-0002). Architecture
diagram layout and QA checklist (SPEC-0003). Visual fidelity of each charter, authoring rules
of the skill (documentation, not behavior).

## 4. Actors

| Actor | Role |
|---|---|
| LLM agent | Creates and rewrites the file, drives the preview server, triggers exports |
| Human editor | Reviews and edits in the browser, triggers exports from the toolbar |
| Operator | Installs, configures, runs the tool locally or in a container |

## 5. Usage Scenarios

### SC-001: Create a presentation from a template
Agent names a slide template and a destination. A starter deck is written. Optionally the
preview starts and the browser opens. Unknown template or existing destination: clear error,
nothing written.

### SC-002: Agent rewrites the file inside an update window
Agent opens the window, rewrites the file, closes the window. The browser shows an overlay during
the window and reloads once after it closes.

### SC-003: Human edits and saves from the browser
Browser saves are cleaned of editing artifacts, completed into a full document when partial,
and never written over a template shipped with the tool.

### SC-004: Export a deck
Agent or human exports a presentation. One native slide per slide element, warnings for
missing or remote images, never a hard failure while some content exists.

### SC-005: Export a document
Agent or human exports a document. Title appears once, the charter letterhead is applied when
the charter is known, otherwise default styles with a warning.

### SC-006: Create a document from a template
Same as SC-001 with a document, mail or website template.

### SC-007: Control the preview server
Agent starts, queries, switches file, stops the preview. Starting twice in one process switches
the file. Without an explicit port a free one is picked in a fixed range.

### SC-008: Present full screen
Human starts presentation mode. The slide alone fills the screen with uniform zoom, keyboard
navigation works wherever focus is, leaving keeps the current slide.

## 6. Functional Requirements

| ID | Requirement (EARS) | Scenario | Evidence |
|---|---|---|---|
| FR-001 | WHEN the agent creates a file from a template key THE system SHALL copy that template's starter file to the destination. | SC-001, SC-006 | `src/mcp_htmleditor/cli.py:84`, `src/mcp_htmleditor/templates.py:39` |
| FR-002 | IF the template key is unknown THEN THE system SHALL fail with a message listing the available keys and SHALL NOT create a file. | SC-001 | `src/mcp_htmleditor/cli.py:88` |
| FR-030 | IF the destination file already exists THEN THE system SHALL fail with a "file already exists" message and SHALL NOT overwrite it. | SC-001 | `src/mcp_htmleditor/cli.py:94` |
| FR-003 | WHILE a file is served THE system SHALL poll the server at the configured interval and reload the preview when the file changed on disk for a reason other than its own save. | SC-002 | `src/mcp_htmleditor/static/editor.js:298`, `src/mcp_htmleditor/static/editor.js:318` |
| FR-004 | WHEN the agent opens an update window THE system SHALL show a blocking overlay in the browser and suppress reloads until the window is closed, then reload once. | SC-002 | `src/mcp_htmleditor/mcp_server.py:145`, `src/mcp_htmleditor/static/editor.js:306`, `src/mcp_htmleditor/static/editor.js:319` |
| FR-005 | WHEN the browser saves THE system SHALL remove editor ids and classes, editable markers, drag handles, browser extension attributes and duplicated slide selector options before writing. | SC-003 | `src/mcp_htmleditor/http_server.py:294`, `src/mcp_htmleditor/http_server.py:443` |
| FR-006 | IF a saved payload is a fragment THEN THE system SHALL rebuild a full document keeping the existing head, language and document type, with a minimal UTF-8 head when none exists. | SC-003 | `src/mcp_htmleditor/http_server.py:291`, `src/mcp_htmleditor/http_server.py:499` |
| FR-007 | IF the served file is a starter or reference template shipped with the tool THEN THE system SHALL skip the write and answer success with a "read-only" skip marker. | SC-003 | `src/mcp_htmleditor/http_server.py:300` |
| FR-008 | WHEN a slide is inserted or deleted in the browser THE system SHALL renumber slide ids sequentially from 0, rewrite slide counters and the navigation list. | SC-003 | `src/mcp_htmleditor/static/editor.js:1580` |
| FR-009 | The agent interface SHALL expose exactly seven operations: start server, stop server, get status, open file, update start, update end, layout architecture diagram. | SC-007 | `src/mcp_htmleditor/mcp_server.py:31`, `src/mcp_htmleditor/mcp_server.py:166` |
| FR-031 | WHEN the agent starts the server while one already runs in the same process THE system SHALL switch the served file instead of starting a second server. | SC-007 | `src/mcp_htmleditor/http_server.py:599`, `src/mcp_htmleditor/http_server.py:628` |
| FR-029 | IF no port is requested THEN THE system SHALL bind the preferred port (default 7842) or else the first free port of 7840 to 7849, and report the bound port. | SC-007 | `src/mcp_htmleditor/http_server.py:561`, `src/mcp_htmleditor/config.py:287` |
| FR-032 | IF an explicitly requested port is taken, or all ten ports are taken THEN THE system SHALL fail with an explicit message instead of a raw error. | SC-007 | `src/mcp_htmleditor/http_server.py:588`, `src/mcp_htmleditor/http_server.py:643`, `src/mcp_htmleditor/cli.py:178` |
| FR-010 | WHEN server state changes THE system SHALL write the current file, port, process id, update flag and poll interval to a state file next to the edited file. | SC-007 | `src/mcp_htmleditor/state.py:63` |
| FR-011 | The system SHALL select its editing mode from the document type declared on the root element: presentation, document or website. | SC-003 | `src/mcp_htmleditor/static/editor.js:194` |
| FR-012 | The system SHALL ship exactly eight templates: ei, carbon, medical (slides); doc, doc-perso, doc-ei (documents); mail; website. | SC-001, SC-006 | `src/mcp_htmleditor/templates.py:39` |
| FR-013 | WHEN a deck is exported THE system SHALL produce a 16:9 deck with one slide per outermost slide element, ignoring nested slides. | SC-004 | `src/mcp_htmleditor/export/to_pptx.py:238`, `src/mcp_htmleditor/export/to_pptx.py:272` |
| FR-014 | IF an image is missing, remote, or unreadable THEN THE system SHALL add a warning and continue the deck export without it. | SC-004 | `src/mcp_htmleditor/export/to_pptx.py:2211` |
| FR-033 | IF no slide element exists THEN THE system SHALL warn and export the whole body as a single slide. | SC-004 | `src/mcp_htmleditor/export/to_pptx.py:244` |
| FR-015 | WHEN a document whose charter is known (perso, ei) is exported THE system SHALL build or reuse a cached reference document for that charter and apply it. | SC-005 | `src/mcp_htmleditor/export/reference_docx.py:330`, `src/mcp_htmleditor/export/reference_docx.py:291` |
| FR-016 | IF the charter is unknown or its reference document cannot be built THEN THE system SHALL export with default styles and a warning. | SC-005 | `src/mcp_htmleditor/export/reference_docx.py:357`, `src/mcp_htmleditor/export/to_docx.py:230` |
| FR-034 | IF the external converter is missing or fails THEN THE system SHALL fail the document export with an explicit message. | SC-005 | `src/mcp_htmleditor/cli.py:277`, `src/mcp_htmleditor/cli.py:282` |
| FR-017 | The system SHALL NOT output the document title twice in a word export: title and subtitle become document metadata and leave the body. | SC-005 | `src/mcp_htmleditor/export/to_docx.py:186` |
| FR-018 | IF a word export contains a vector figure (file, data URI or inline) THEN THE system SHALL add a warning recommending a bitmap format, without blocking. | SC-005 | `src/mcp_htmleditor/export/to_docx.py:249` |
| FR-020 | IF the port or poll interval setting is empty or not an integer THEN THE system SHALL use its default (7842, 1000 ms). | (transverse) | `src/mcp_htmleditor/config.py:45`, `src/mcp_htmleditor/config.py:113` |
| FR-019 | The operator SHALL be able to set host, preferred port, poll interval, template, log, cache, binary and checklist directories, and a tracing destination with key, through environment settings with XDG defaults. | (transverse) | `src/mcp_htmleditor/config.py:42`, `src/mcp_htmleditor/config.py:216` |
| FR-021 | The system SHALL log to the console error stream and to a rotating file (2 MB, 3 backups), keeping console only when the log directory is not writable. | (transverse) | `src/mcp_htmleditor/logging_config.py:58`, `src/mcp_htmleditor/logging_config.py:118` |
| FR-022 | The system SHALL record spans for agent, HTTP and export operations, as local JSON lines by default or to a remote collector with a bearer key when configured. | (transverse) | `src/mcp_htmleditor/tracing.py:119`, `src/mcp_htmleditor/tracing.py:174` |
| FR-023 | The system SHALL NOT put document content, prompts or credentials in span attributes. | (transverse) | `src/mcp_htmleditor/http_server.py:306` |
| FR-024 | WHEN health is requested THE system SHALL answer status ok, version, served file or null, and port, even with no file loaded. | SC-007 | `src/mcp_htmleditor/http_server.py:423` |
| FR-025 | WHEN the skill is requested THE system SHALL print the full authoring skill (index and every sub document); install SHALL place a light routing skill for the agent. | (transverse) | `src/mcp_htmleditor/cli.py:39`, `src/mcp_htmleditor/skill_content.py:45`, `Makefile:186` |
| FR-026 | WHEN the human starts presentation mode THE system SHALL put the slide document itself full screen, falling back to the preview frame when refused. | SC-008 | `src/mcp_htmleditor/static/editor.js:103` |
| FR-027 | WHILE presentation mode is active THE system SHALL hide navigation chrome and scale the slide uniformly to fill the screen on black, keeping 16:9. | SC-008 | `templates/bootstrap/slides-empty.html`, `templates/bootstrap/slides-ei-empty.html`, `templates/bootstrap/slides-medical-empty.html` |
| FR-028 | WHILE presentation mode is active THE system SHALL move to next slide on Right, Down or Space, previous on Left or Up, first on Home, and leave on Escape, whichever document holds focus. | SC-008 | `src/mcp_htmleditor/static/editor.js:141` |

## 7. Non-Functional Requirements

- Local, single user: no authentication on the preview server; default bind is the loopback
  host, the container image binds all interfaces (`Dockerfile:33`).
- Degraded environments warn instead of failing for: unwritable log dir, corrupt state file,
  unknown charter, missing image (FR-014, FR-016, FR-021).

## 8. End-to-End Tests

| ID | Covers | Test | Level | State |
|---|---|---|---|---|
| E2E-001 | FR-001, FR-012 | `tests/test_templates.py::test_all_templates_resolve_to_existing_files` | unit | green |
| E2E-002 | FR-002 | untested | | |
| E2E-003 | FR-002 | `tests/test_templates.py::test_unknown_key_raises_keyerror` | unit | green |
| E2E-004 | FR-004, FR-009, FR-010 | untested | | |
| E2E-005 | FR-004 | untested | | |
| E2E-006 | FR-010 | `tests/test_state.py::test_set_update_flag_persists` | unit | green |
| E2E-007 | FR-010 | `tests/test_state.py::test_load_corrupt_file_is_ignored` | unit | green |
| E2E-008 | FR-005 | `tests/test_http_helpers.py::test_strip_removes_injected_ids` (and 6 sibling `test_strip_*`) | unit | green |
| E2E-009 | FR-007 | untested | | |
| E2E-010 | FR-006 | `tests/test_http_helpers.py::test_rebuild_default_head_when_missing` | unit | green |
| E2E-011 | FR-008 | `tests/test_undo_redo_e2e.py::test_undo_redo_slide_insert_and_delete` (partial: no counter or list assertion) | e2e | green |
| E2E-012 | FR-013 | `tests/test_export_pptx.py::test_euro_information_template_exports_every_slide` | integration | green |
| E2E-013 | FR-014 | `tests/test_export_pptx.py::test_missing_and_remote_images_are_reported` | integration | green |
| E2E-014 | FR-033 | untested (CLI level) | | |
| E2E-015 | FR-033 | `tests/test_export_pptx.py::test_document_without_slides_warns_and_keeps_content` | integration | green |
| E2E-016 | FR-015 | `tests/test_export_docx.py::test_to_docx_carries_the_charter` | integration | green |
| E2E-017 | FR-016 | `tests/test_export_docx.py::test_reference_docx_for_swallows_a_missing_pandoc` | unit | green |
| E2E-018 | FR-016 | `tests/test_export_docx.py::test_to_docx_reports_an_unknown_charter` | integration | green |
| E2E-019 | FR-018 | `tests/test_export_docx.py::test_to_docx_warns_about_svg_figures` | integration | green |
| E2E-020 | FR-017 | `tests/test_export_docx.py::test_to_docx_writes_the_title_once` | integration | green |
| E2E-021 | FR-001, FR-011 | `tests/test_templates.py::test_doc_ei_template_is_document` | unit | green |
| E2E-022 | FR-012 | `tests/test_templates.py::test_list_templates_returns_all_keys` | unit | green |
| E2E-023 | FR-009, FR-024 | untested | | |
| E2E-024 | FR-031 | untested | | |
| E2E-025 | FR-032 | untested (agent level) | | |
| E2E-026 | FR-024 | `tests/test_http_health.py::test_health_reports_status_and_version` | unit | green |
| E2E-027 | FR-019 | `tests/test_settings.py::test_settings_defaults` | unit | green |
| E2E-028 | FR-020 | `tests/test_settings.py::test_invalid_poll_interval_falls_back` | unit | green |
| E2E-029 | FR-020 | `tests/test_config.py::test_invalid_port_falls_back` | unit | green |
| E2E-030 | FR-019 | `tests/test_settings.py::test_tilde_is_expanded_in_path_overrides` | unit | green |
| E2E-031 | FR-021 | `tests/test_logging_config.py::test_setup_logging_installs_both_handlers` | unit | green |
| E2E-032 | FR-021 | `tests/test_logging_config.py::test_unwritable_log_dir_keeps_the_console` | unit | green |
| E2E-033 | FR-021 | `tests/test_logging_config.py::test_setup_logging_is_idempotent` | unit | green |
| E2E-034 | FR-022 | `tests/test_tracing.py::test_configure_tracing_exports_spans` | unit | green |
| E2E-035 | FR-022 | `tests/test_tracing.py::test_exporter_reports_failure_on_unwritable_path` | unit | green |
| E2E-036 | FR-023 | untested | | |
| E2E-037 | FR-025 | `tests/test_skill_content.py::test_build_skill_content_includes_index_and_subdocs` | unit | green |
| E2E-038 | FR-026, FR-027 | `tests/test_fullscreen_e2e.py::test_fullscreen_hides_toolbar_and_fills_the_screen` | e2e | green |
| E2E-039 | FR-026 | `tests/test_fullscreen_e2e.py::test_fallback_shell_hides_toolbar_if_inner_fullscreen_is_unavailable` | e2e | green |
| E2E-040 | FR-028 | `tests/test_fullscreen_e2e.py::test_navigation_keys_work_even_if_focus_never_reaches_the_iframe` | e2e | green |
| E2E-041 | FR-028 | `tests/test_fullscreen_e2e.py::test_exiting_fullscreen_keeps_the_current_slide_and_restores_the_ui` | e2e | green |
| E2E-042 | FR-029 | `tests/test_port_range.py::test_two_presentations_get_two_different_ports` | integration | green |
| E2E-043 | FR-029 | `tests/test_port_range.py::test_falls_back_into_the_range_when_preferred_is_taken` | integration | green |
| E2E-044 | FR-032 | `tests/test_port_range.py::test_raises_a_clear_error_when_the_whole_range_is_taken` | integration | currently red |
| E2E-045 | FR-030 | untested | | |
| E2E-046 | FR-034 | untested | | |

## 9. Glossary

| Term | Meaning |
|---|---|
| Charter | A visual identity (EI, Carbon, medical, perso, generic), never mixed in one file |
| Starter template | Minimal file copied when creating a document |
| Reference template | Rich example of a charter, read only |
| Update window | Period opened and closed by the agent around a rewrite |
| Presentation mode | Full screen slide show from the browser |

## 10. Confidence notes

- Every legacy FR was re-read against code. Five legacy statements are contradicted and were
  rewritten as-built (FR-007, FR-009, FR-010, FR-012, FR-016); the old wording is kept in
  design.md and the contradiction is BL-0006. FR-028 legacy text promised End in the parent relay;
  the parent relay does not handle End (`src/mcp_htmleditor/static/editor.js:151`, Home is the last navigation key), so End is
  written only as handled by the slide document itself, not stated here.
- Legacy FR-018 claimed deck exports warn on vector figures; inline vector elements are dropped
  silently by the deck exporter (`src/mcp_htmleditor/export/to_pptx.py:95`) and no deck warning was
  found, so FR-018 is scoped to word export.
- Legacy FR-019 phrasing "no direct environment read elsewhere" is a coding convention, moved to
  design.md; one CLI path writes the environment (BL-0011).
- FR-023 evidence is sampled (one span site); not every span site was opened.
- FR-027 is implemented in the starter templates, not the editor; five reference decks lack it
  (BL-0007).
- New ids FR-030 to FR-034 and E2E-045, E2E-046 were added for behaviors the legacy spec missed or
  stated wrongly.
