---
name: mcp-htmleditor
description: Créer, éditer et exporter des présentations et documents HTML WYSIWYG (templates Euro-Information, IBM Carbon). Déclencheurs: "html powerpoint", "html edition", "html doc", "html slides", éditer un slide deck ou un document en HTML, exporter en PPTX/DOCX.
---

# mcp-htmleditor

Le contenu réel de cette skill vit dans la commande CLI, pour rester toujours
synchronisé avec l'outil installé.

**Charge la skill complète en exécutant:**

```bash
mcp-htmleditor skill
```

Cette commande imprime l'intégralité de la skill (index + workflows + règles par
type de slide/document + conventions d'export et de templates). Lis entièrement
sa sortie avant d'agir, puis suis les instructions.

Résumé express en attendant:
- `mcp-htmleditor templates` — liste les templates (ei, carbon, doc)
- `mcp-htmleditor new <template> fichier.html --serve` — crée + ouvre l'éditeur
- `mcp-htmleditor serve fichier.html` — ouvre l'éditeur WYSIWYG (navigateur)
- `mcp-htmleditor mcp` — serveur MCP (stdio) pour piloter l'édition
- `mcp-htmleditor export pptx|docx in.html out.ext` — export
