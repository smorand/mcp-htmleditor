# mcp-htmleditor skill (core)

mcp-htmleditor is an LLM driven WYSIWYG HTML editor. You edit the HTML file on disk; the browser
follows by polling. Read this core, then load the topics your task needs (see Topics).

## Règles absolues

1. Toujours appeler `update_start` avant de modifier le fichier HTML et `update_end` après.
2. Ne jamais supprimer `data-type="slide"`, `data-id`, ni `data-title` sur les sections slides.
3. Utiliser `data-editable="text"` sur tous les éléments texte que l'utilisateur doit pouvoir éditer visuellement.
4. Toujours reconstruire le HTML complet (DOCTYPE + head + body) quand on écrit dans le fichier.
5. Les chemins d'images doivent être relatifs au fichier HTML ou en base64 pour la portabilité.
6. Ne jamais démarrer un second serveur si `get_status` indique déjà `running: true` sur le bon port.
7. Valider le rendu visuellement après chaque modification substantielle (`agent-browser` ou Playwright sur l'URL retournée par `start_server`; lire le `port` retourné, ne jamais supposer 7842). Vérifier débordements, fontes, alignements, artefacts du template.
8. Une modification trouvée dans le fichier est volontaire, jamais une erreur à corriger. Si l'humain a édité le document entre deux tâches, ne jamais revenir en arrière ni remettre la bonne valeur: traiter le contenu actuel comme la vérité et poser la question si un changement semble contradictoire avec la demande.

## Workflow

1. `start_server(file="path/to/file.html")`: démarrer le serveur et ouvrir le navigateur.
2. `get_status()`: vérifier que le serveur est actif.
3. `update_start()`: signaler que la modification commence.
4. Modifier le fichier HTML sur disque (relire le fichier avant d'écrire).
5. `update_end()`: signaler la fin, le navigateur recharge.
6. Optionnel: exporter avec `mcp-htmleditor export pptx|docx input.html output`.

## Create a file

Always start from a template, never from scratch:

```bash
mcp-htmleditor templates
mcp-htmleditor new <template> <file> [--serve]
```

`<template>` is one of `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`.

## Tools

- start_server: start the HTTP server for a file and open the browser; idempotent, without `port` a free port is chosen, read the returned `port`
- stop_server: stop the HTTP server
- get_status: report file, port, pid, update_in_progress, mtime and running
- open_file: switch the served file; the browser reloads
- update_start: set update_in_progress and show the browser overlay
- update_end: clear update_in_progress; the browser reloads the content
- layout_arch_diagram: compute the layout of declarative architecture diagrams in a file
- get_skill: return the skill core, or one topic with its type argument
- outline: Read the structure of a file (charter, slides, headings) without any image data.
- get_slide: Read the HTML of one slide, large images replaced by data:ref:img-N.
- patch: Apply validated, atomic, self renumbering slide operations (set_text, replace_slide, insert_slide, delete_slide, move_slide) to a presentation; dry_run validates only.
- lint: Check a file against the structure and charter rules; returns problems, errors and warnings.
- list_templates: List the 8 template keys with their description.
- new_file: Create a file from a template key; refuses an existing target.
- export: Export a presentation to pptx or a document to docx.
- history: list the saved previous versions of a file, newest first (id, bytes, reason).
- restore: put a previous version of a file back by id; the replaced content is kept in the history.
- list_requests: List the requests the person queued in the editor for a file, oldest first, with the slide position; optional slide and status filters
- clear_requests: Remove the done and skipped requests of a file, or every request with scope all; returns the count removed
- complete_request: Mark a request done, or skipped with a reason
- write_review: Replace the AI suggestions shown in the editor (at most 6)
- render: Picture of one slide plus a layout report (overflow, clipped, font, script, image); needs Chromium (make install-browser).

## Topics

create: Create and edit a file: workflows, rules for text, slides and images. Load: mcp-htmleditor skill --type create
export: Export to PPTX and DOCX: what is kept, approximated, lost. Load: mcp-htmleditor skill --type export
templates: Build a template from an existing PPTX or DOCX. Load: mcp-htmleditor skill --type templates
slides-carbon: Rules for IBM Carbon slides. Load: mcp-htmleditor skill --type slides-carbon
slides-ei: Rules for Euro-Information slides. Load: mcp-htmleditor skill --type slides-ei
medical: Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget. Load: mcp-htmleditor skill --type medical
medical-sources: Medical slides: citing sources and anonymising patient images. Load: mcp-htmleditor skill --type medical-sources
document: Rules for Word-like documents and their DOCX export. Load: mcp-htmleditor skill --type document
mail: Rules for HTML mails. Load: mcp-htmleditor skill --type mail
website: Rules for single page websites. Load: mcp-htmleditor skill --type website
gantt: Rules for Gantt charts. Load: mcp-htmleditor skill --type gantt
arch-diagram: Rules for architecture diagrams. Load: mcp-htmleditor skill --type arch-diagram
arch-qa: Visual quality review of architecture diagrams and its checklist. Load: mcp-htmleditor skill --type arch-qa
annotated-image: Rules for annotated images. Load: mcp-htmleditor skill --type annotated-image
tables: Rules for tables. Load: mcp-htmleditor skill --type tables
