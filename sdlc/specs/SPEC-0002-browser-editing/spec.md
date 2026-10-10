# Browser editing: Specification (as-built)

> Id: SPEC-0002
> Nature: FEAT
> Status: as-built
> Area: browser editing (edit mode, autosave, undo/redo, structural edits, export buttons, tab title)
> Generated on: 2026-10-10 by /sdlc-retro-spec at 2521c331564328c9ca35fbfef372586cadbc12dd
> Confidence: medium (see Confidence notes)

## 1. Summary

A human reviews the agent's file in the browser and edits it in place: text with a format bar,
images, tables, slides, document blocks, architecture node positions. Changes save automatically
in the background. Structural changes can be undone and redone. The browser tab shows the
document title. Exports are one click from the toolbar.

## 2. Current State

### 2.1 How it works today

Editing is off until the human turns it on. With it on, text zones marked editable accept typing
and show a floating format bar; focusing a zone shows an insert bar. Typing saves after a short
pause, leaving a zone saves at once, structural actions save after a shorter pause. A colored dot
shows saved, pending, or agent update. Undo and redo cover structural actions only; plain typing
keeps the browser's own undo.

### 2.2 Existing specifications governing this area

SPEC-0001 (FR-003 reload policy, FR-005 save cleaning, FR-008 slide renumbering, FR-026 to FR-028
presentation mode). This spec does not restate them.

### 2.3 Existing test coverage

17 browser e2e tests in 4 files (12 rows cite them). 9 of 20 requirements (FR-002 to FR-008, FR-011, FR-018) have no test at any level; FR-019 download is untested.

## 3. Scope

### 3.1 Covered

Edit mode toggle, text editing aids, autosave and status dot, self save versus external change,
undo/redo, slide insert and delete, document block insert and reorder, tables, images, arch node
drag, keyboard isolation while typing, export buttons per mode, tab title.

### 3.2 Not covered

Save cleaning and reload (SPEC-0001), arch layout engine (SPEC-0003), slide layout and block
catalogs content (data, not behavior).

## 4. Actors

| Actor | Role |
|---|---|
| Human editor | Edits in the browser |
| LLM agent | Writes the file; its writes trigger reloads |

## 5. Usage Scenarios

### SC-001: Edit text
Human turns on editing, clicks a text zone, types, formats. The change is saved in the background.

### SC-002: Change structure
Human inserts or deletes a slide, inserts or drags a document block, adds a table row, drops an
image, drags an architecture node. Each action saves and can be undone.

### SC-003: Undo and redo
Human presses the undo or redo shortcut or button; the last structural action is reverted or
reapplied and saved.

### SC-004: Export from the toolbar
Human clicks an export button; the file downloads.

### SC-005: Recognize the tab
Human has several editors open; each tab shows its document title.

## 6. Functional Requirements

| ID | Requirement (EARS) | Scenario | Evidence |
|---|---|---|---|
| FR-001 | WHEN the human toggles the edit mode button THE system SHALL make every zone marked as editable text editable, or make them read only again. | SC-001 | `src/mcp_htmleditor/static/editor.js:84`, `src/mcp_htmleditor/static/editor.js:568`, `src/mcp_htmleditor/static/editor.js:586` |
| FR-002 | WHEN the human selects or types in an editable zone THE system SHALL show a floating format bar, hidden on a click outside. | SC-001 | `src/mcp_htmleditor/static/editor.js:803` |
| FR-003 | WHEN an editable zone gains focus THE system SHALL show an insert bar offering image, table, rule and link. | SC-001 | `src/mcp_htmleditor/static/editor.js:897` |
| FR-004 | WHEN the human types in an editable zone THE system SHALL mark the document pending and save it 800 ms after the last keystroke. | SC-001 | `src/mcp_htmleditor/static/editor.js:1394` |
| FR-005 | WHEN an editable zone loses focus THE system SHALL save at once. | SC-001 | `src/mcp_htmleditor/static/editor.js:1395` |
| FR-006 | WHEN a structural action completes THE system SHALL save 600 ms later. | SC-002 | `src/mcp_htmleditor/static/editor.js:1396` |
| FR-007 | The system SHALL show a status dot: green saved, orange pending, yellow agent update in progress. | SC-001 | `src/mcp_htmleditor/static/editor.js:46`, `src/mcp_htmleditor/static/editor.js:55`, `src/mcp_htmleditor/static/editor.js:306` |
| FR-008 | The system SHALL NOT reload the preview because of its own save or while local changes are pending. | SC-001 | `src/mcp_htmleditor/static/editor.js:318` |
| FR-009 | WHEN the human presses Ctrl or Cmd with Z, or the undo button, THE system SHALL revert the last structural action and save; Ctrl or Cmd with Shift Z, Ctrl Y, or the redo button reapplies it. | SC-003 | `src/mcp_htmleditor/static/editor.js:93`, `src/mcp_htmleditor/static/editor.js:451` |
| FR-010 | WHILE the browser's own undo still has typing to revert in the focused zone THE system SHALL leave the shortcut to the browser. | SC-003 | `src/mcp_htmleditor/static/editor.js:467` |
| FR-011 | The system SHALL keep at most 50 undo steps and clear redo on any new structural action. | SC-003 | `src/mcp_htmleditor/static/editor.js:357`, `src/mcp_htmleditor/static/editor.js:404` |
| FR-012 | WHILE edit mode is off THE system SHALL hide the undo and redo buttons. | SC-003 | `src/mcp_htmleditor/static/editor.js:521` |
| FR-013 | WHEN the human inserts a slide before or after the current one, picking a layout of the detected charter, THE system SHALL insert it; delete removes the current slide. | SC-002 | `src/mcp_htmleditor/static/editor.js:1484`, `src/mcp_htmleditor/static/editor.js:1508`, `src/mcp_htmleditor/static/editor.js:1563` |
| FR-014 | WHEN the human inserts a block before or after the caret or drags a block by its handle in a document or website THE system SHALL insert or move it without adding any attribute or inline style to it. | SC-002 | `src/mcp_htmleditor/static/editor.js:1702`, `src/mcp_htmleditor/static/editor.js:1834` |
| FR-015 | WHEN the human uses a table's context menu THE system SHALL add or remove the last row or column. | SC-002 | `src/mcp_htmleditor/static/editor.js:1307`, `src/mcp_htmleditor/static/editor.js:1359` |
| FR-016 | WHEN the human drops an image file on an editable zone or picks one from the insert bar THE system SHALL embed it inline as base64. | SC-002 | `src/mcp_htmleditor/static/editor.js:938`, `src/mcp_htmleditor/static/editor.js:959` |
| FR-017 | WHEN the human drags an architecture node in a presentation THE system SHALL store its new position in percent and mark it manually placed once it actually moved. | SC-002 | `src/mcp_htmleditor/static/editor.js:1953`, `src/mcp_htmleditor/static/editor.js:1993` |
| FR-018 | WHILE the human types in an editable zone THE system SHALL NOT let Space, arrows, Home, End or F reach slide navigation. | SC-001 | `src/mcp_htmleditor/static/editor.js:549` |
| FR-019 | The system SHALL offer the deck export button for presentations, the document export button for documents, and no export button for websites; a click downloads the file. | SC-004 | `src/mcp_htmleditor/static/editor.js:255`, `src/mcp_htmleditor/static/editor.js:276` |
| FR-020 | WHEN the preview loads THE system SHALL set the browser tab title to the document's own title, or to the file name when the document has none. | SC-005 | `src/mcp_htmleditor/static/editor.js:232` |

## 7. Non-Functional Requirements

None observed beyond the timings in FR-004 to FR-006.

## 8. End-to-End Tests

| ID | Covers | Test | Level | State |
|---|---|---|---|---|
| E2E-001 | FR-012 | `tests/test_undo_redo_e2e.py::test_undo_redo_buttons_hidden_outside_edit_mode` | e2e | green |
| E2E-002 | FR-009, FR-017 | `tests/test_undo_redo_e2e.py::test_undo_redo_arch_node_reposition` | e2e | green |
| E2E-003 | FR-009, FR-013 | `tests/test_undo_redo_e2e.py::test_undo_redo_slide_insert_and_delete` | e2e | green |
| E2E-004 | FR-010 | `tests/test_undo_redo_e2e.py::test_undo_does_not_fire_inside_active_text_editing` | e2e | green |
| E2E-005 | FR-009, FR-014 | `tests/test_undo_redo_e2e.py::test_undo_redo_document_block_insert` | e2e | green |
| E2E-006 | FR-009, FR-016 | `tests/test_undo_redo_e2e.py::test_undo_redo_image_insert_via_drop` | e2e | green |
| E2E-007 | FR-009, FR-015 | `tests/test_undo_redo_e2e.py::test_undo_redo_table_row_add_via_context_menu` | e2e | green |
| E2E-008 | FR-014 | `tests/test_undo_redo_e2e.py::test_undo_redo_document_block_reorder` | e2e | green |
| E2E-009 | FR-019 | `tests/test_website_template_e2e.py::test_website_has_no_export_buttons_but_keeps_doc_block_ui` | e2e | green |
| E2E-010 | FR-001 | `tests/test_website_template_e2e.py::test_website_tabs_switch_on_click_in_and_out_of_edit_mode` | e2e | green |
| E2E-011 | FR-020 | `tests/test_tab_title_e2e.py::test_tab_title_reflects_document_title_not_filename` | e2e | green |
| E2E-012 | FR-020 | `tests/test_tab_title_e2e.py::test_tab_title_falls_back_to_filename_when_document_has_no_title` | e2e | green |
| E2E-013 | FR-002, FR-003 | untested | | |
| E2E-014 | FR-004, FR-005, FR-006 | untested | | |
| E2E-015 | FR-007 | untested | | |
| E2E-016 | FR-008 | untested | | |
| E2E-017 | FR-011 | untested | | |
| E2E-018 | FR-018 | untested | | |
| E2E-019 | FR-019 (download) | untested | | |

## 9. Glossary

| Term | Meaning |
|---|---|
| Editable zone | Element the file marks as editable text |
| Structural action | Any edit other than typing: slides, blocks, tables, images, node moves |
| Self save | A save sent by this browser, as opposed to an agent write |

## 10. Confidence notes

- Autosave serializes the page by temporarily removing the editable state of every editable zone,
  including the one being typed in (`src/mcp_htmleditor/static/editor.js:1410`), with no caret or
  selection restore in that function. A user reports losing focus during autosave. Not written as a
  requirement (cannot be stated as intended behavior); filed as BL-0008.
- The parent keyboard relay and fullscreen belong to SPEC-0001 and are not repeated.
- Tab title test on file switch (`tests/test_tab_title_e2e.py::test_tab_title_differs_after_switching_to_a_different_file`) also covers FR-020.
- Context menus for gantt tasks, annotations and diagrams exist (`src/mcp_htmleditor/static/editor.js:1185`)
  but their actions were not traced one by one; not written.
