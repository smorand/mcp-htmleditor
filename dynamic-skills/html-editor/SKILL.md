---
name: html-editor
description: "Édition WYSIWYG de présentations et documents HTML (templates Euro-Information, IBM Carbon), pilotée par le serveur mcp-htmleditor. Déclencheurs: 'html powerpoint', 'html slides', 'html doc', 'html edition', éditeur html, présentation/document en HTML, export HTML vers PPTX/DOCX."
---

# html-editor (mcp-htmleditor)

Le contenu réel et à jour de cette skill vit dans la commande CLI, pour rester
synchronisé avec l'outil installé.

**Charge le cœur de la skill maintenant en exécutant:**

```bash
mcp-htmleditor skill
```

Lis le cœur (règles absolues, workflow, outils, index des sujets), puis charge les
sujets utiles à la tâche, un par un, avec `mcp-htmleditor skill --type <sujet>`:
`create`, `export`, `templates`, `slides-carbon`, `slides-ei`, `medical`,
`medical-sources`, `breathe`, `document`, `mail`, `website`, `gantt`, `arch-diagram`, `arch-qa`,
`annotated-image`, `tables`. Ne charge pas tout: l'index du cœur dit quel sujet
correspond à quelle tâche.

## Résumé express (en attendant le cœur)

```bash
mcp-htmleditor templates                            # liste les templates
mcp-htmleditor new ei ma-presentation.html --serve  # créer + ouvrir l'éditeur
mcp-htmleditor serve fichier.html                   # éditeur WYSIWYG (navigateur)
mcp-htmleditor mcp                                  # serveur MCP (stdio)
mcp-htmleditor export pptx in.html out.pptx         # export PPTX
mcp-htmleditor export docx in.html out.docx         # export DOCX (pandoc)
```

Workflow LLM: `update_start()` → écrire le HTML → `update_end()`.
Le navigateur se synchronise par polling. Source de vérité = HTML single-page.

Distinction avec la skill `pptx`: `pptx` produit/édite des fichiers `.pptx` natifs
(OOXML, pptxgenjs). `html-editor` édite en HTML et exporte en bout de chaîne. Si le
prompt parle de HTML, c'est cette skill; sinon c'est `pptx`.
