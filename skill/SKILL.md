# mcp-htmleditor — Skill

## Description

`mcp-htmleditor` est un éditeur WYSIWYG HTML piloté par LLM. Il combine:
- Un serveur HTTP local (port 7842 par défaut) servant GrapesJS dans le navigateur
- Un serveur MCP exposant 6 outils pour que l'agent LLM contrôle le fichier HTML
- Des templates de référence et bootstrap pour démarrer rapidement
- Un export vers PPTX (python-pptx) et DOCX (pandoc)

L'agent modifie le fichier HTML sur disque; le navigateur se synchronise automatiquement via polling.

---

## Choisir et créer depuis un template

**Le template se choisit à la création du fichier**, via `mcp-htmleditor new <key>`.
Il n'y a pas d'option `--template` sur `serve`: on crée d'abord, on édite ensuite.

```bash
mcp-htmleditor templates                          # liste les templates
mcp-htmleditor new ei     ma-pres.html   --serve  # Euro-Information
mcp-htmleditor new carbon ma-pres.html   --serve  # IBM Carbon
mcp-htmleditor new doc    mon-rapport.html        # Document
```

### Où sont stockés les templates

```
skill/templates/
├── bootstrap/                    ← points de départ (copiés par `new`)
│   ├── slides-ei-empty.html      ← key: ei     (Euro-Information)
│   ├── slides-empty.html         ← key: carbon (IBM Carbon)
│   └── document-empty.html       ← key: doc    (document Word-like)
└── reference/                    ← exemples complets (à consulter/cloner)
    ├── slides/
    │   ├── euro-information.html  ← EI: titre + agenda + contenu, logos embarqués
    │   ├── ibm-carbon.html        ← IBM Carbon: 9 slides, tous les composants
    │   ├── presentation-standard.html
    │   └── roadmap-one-pager.html
    └── documents/
        └── report-standard.html
```

Les fichiers `bootstrap/` sont le point de départ minimal. Les fichiers `reference/`
sont des exemples riches: le LLM peut s'en inspirer pour cloner des layouts.
**Ces fichiers sont en lecture seule via le serveur** (une sauvegarde vers un chemin
contenant `skill/templates/` est ignorée).

### Le template par défaut

- **Euro-Information** (`ei`): présentations EI. Bleu `#003A8D`, orange `#FBAE40`,
  police Segoe UI, logos Crédit Mutuel / CIC / Euro Information embarqués en base64.
- **IBM Carbon** (`carbon`): présentations génériques. Tokens Carbon.
- **Document** (`doc`): documents Word-like (export DOCX optimal).

Le serveur détecte automatiquement le template du fichier ouvert et adapte le picker
« Insérer slide » (5 layouts adaptés au template: title, agenda, section, content, diagram).
Règles détaillées: `skill/types/slides.md`.

---

## Règles absolues

1. **Toujours appeler `update_start` avant de modifier le fichier HTML** et `update_end` après.
2. **Ne jamais supprimer `data-type="slide"`, `data-id`, ni `data-title`** sur les sections slides.
3. **Utiliser `data-editable="text"` sur tous les éléments texte** que l'utilisateur doit pouvoir éditer visuellement.
4. **Toujours reconstruire le HTML complet** (DOCTYPE + head + body) quand on écrit dans le fichier.
5. **Les chemins d'images doivent être relatifs au fichier HTML** ou en base64 pour la portabilité.
6. **Ne jamais démarrer un second serveur** si `get_status` indique déjà `running: true` sur le bon port.

---

## Workflow LLM type

1. `start_server(file="path/to/file.html")` — démarrer le serveur et ouvrir le navigateur
2. `get_status()` — vérifier que le serveur est actif
3. `update_start()` — signaler que la modification commence
4. *Modifier le fichier HTML* sur disque (écriture directe du fichier)
5. `update_end()` — signaler que la modification est terminée, le browser recharge
6. *(Optionnel)* `export pptx` ou `export docx` via CLI

---

## Commandes CLI

```bash
# Lister les templates disponibles
mcp-htmleditor templates

# Créer un fichier à partir d'un template (le moyen recommandé de démarrer)
mcp-htmleditor new <template> mon-fichier.html
#   <template> = ei | carbon | doc
#   ei     → Euro-Information (Crédit Mutuel / CIC)
#   carbon → IBM Carbon
#   doc    → document Word-like
# Option --serve pour ouvrir l'éditeur immédiatement:
mcp-htmleditor new ei ma-presentation.html --serve

# Démarrer l'éditeur visuel sur un fichier existant
mcp-htmleditor serve path/to/file.html [--port 7842] [--poll 1000]

# Démarrer le serveur MCP (stdio)
mcp-htmleditor mcp

# Exporter en PPTX ou DOCX
mcp-htmleditor export pptx input.html output.pptx
mcp-htmleditor export docx input.html output.docx
```

---

## MCP Tools (6 outils)

| Outil | Description |
|-------|-------------|
| `start_server(file, port=7842)` | Démarre le serveur HTTP + ouvre le navigateur. Idempotent. |
| `stop_server()` | Arrête le serveur HTTP. |
| `get_status()` | Retourne l'état: fichier, port, pid, update_in_progress, mtime, running. |
| `open_file(file)` | Change le fichier servi; le browser recharge automatiquement. |
| `update_start()` | Positionne le flag `update_in_progress=true`; affiche l'overlay browser. |
| `update_end()` | Positionne le flag `update_in_progress=false`; le browser recharge le contenu. |

---

## Format HTML — data-types disponibles

| `data-type` | Description |
|-------------|-------------|
| `slide` | Section d'une présentation. Nécessite aussi `data-id` et `data-title`. |
| `gantt` | Conteneur d'un diagramme de Gantt (barres de tâches). |
| `gantt-task` | Une tâche dans un Gantt. Attributs: `data-label`, `data-start` (YYYY-MM), `data-end`, `data-color`. |
| `arch-diagram` | Conteneur d'un schéma d'architecture. |
| `arch-node` | Un nœud dans un schéma d'archi. Attributs: `data-label`, `data-shape`, `data-x`, `data-y`. |
| `annotation` | Annotation sur une image. Attributs: `data-x`, `data-y` (% relatifs à l'image). |
| `annotated-image` | Conteneur image + annotations. |
| `table` | Tableau HTML standard avec `<thead>` obligatoire. |
| `document` | Article mode document (Word-like), contenu avec h1-h4, p, ul, etc. |
| `document-section` | Section d'un document. |

### data-doc-type (attribut sur `<html>`)

| Valeur | Mode |
|--------|------|
| `presentation` | Active la navigation slides dans GrapesJS |
| `document` | Mode document (Word-like), pas de navigation slides |

---

## Index des sous-docs

| Fichier | Description |
|---------|-------------|
| `skill/workflow-create.md` | Créer et modifier un fichier HTML (from scratch ou template) |
| `skill/workflow-export.md` | Exporter en PPTX ou DOCX, limitations, post-processing |
| `skill/workflow-templates.md` | Créer un template depuis un PPTX/DOCX existant |
| `skill/types/slides.md` | Règles détaillées pour les slides |
| `skill/types/gantt.md` | Règles pour les diagrammes Gantt |
| `skill/types/arch-diagram.md` | Règles pour les schémas d'architecture |
| `skill/types/annotated-image.md` | Règles pour les images annotées |
| `skill/types/tables.md` | Règles pour les tableaux |
| `skill/types/document.md` | Règles pour le mode document |
| `skill/templates/bootstrap/slides-empty.html` | Template minimal présentation |
| `skill/templates/bootstrap/document-empty.html` | Template minimal document |
| `skill/templates/reference/slides/ibm-carbon.html` | **Template de référence IBM Carbon** (9 slides complètes, tous composants) |
| `skill/templates/reference/slides/euro-information.html` | **Template de référence Euro-Information** (3 slides: titre, agenda, contenu; logos CM/CIC/EI embarqués) |
| `skill/templates/reference/slides/presentation-standard.html` | Template 4 slides standard |
| `skill/templates/reference/slides/roadmap-one-pager.html` | Template roadmap one-pager |
| `skill/templates/reference/documents/report-standard.html` | Template rapport standard |
