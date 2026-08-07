# Workflow: créer et modifier un fichier HTML

## Deux acteurs, deux canaux distincts

| Acteur | Canal | Ce qu'il fait |
|--------|-------|---------------|
| **LLM agent** | Fichier sur disque + MCP tools | Écrit le HTML complet, appelle `update_start`/`update_end` |
| **Humain** | Navigateur (mode Édition) | Modifie texte, insère images/tableaux, formate via toolbar |

Ces deux acteurs ne travaillent **jamais en même temps** sur le même fichier.
Le flag `update_in_progress` (via `update_start`/`update_end`) signale au navigateur
qu'une modification LLM est en cours: le browser affiche un overlay et bloque le
rechargement automatique pendant ce temps.

## Ce que le serveur garantit (important pour l'agent)

Quand l'humain sauvegarde via le browser, le serveur **nettoie automatiquement** le HTML
avant d'écrire sur disque:
- Supprime les éléments UI de l'éditeur (`_mcp_format_bar`, `_mcp_insert_bar`, style tag `_mcp_editor_styles`)
- Supprime les attributs `contenteditable` et la classe `_mcp_editable`
- Supprime tout résidu de context menu (`_editor_ctx_host`)

**Le fichier sur disque est toujours propre.** L'agent n'a pas à se préoccuper des
artefacts d'édition humaine.

---

## Partir d'un template bootstrap

La méthode la plus rapide pour un nouveau fichier:

```bash
cp skill/templates/bootstrap/slides-empty.html mon-fichier.html
# ou document
cp skill/templates/bootstrap/document-empty.html mon-document.html
```

Ensuite ouvrir dans l'éditeur:
```
start_server(file="mon-fichier.html")
```

Le template IBM Carbon (`skill/templates/reference/slides/ibm-carbon.html`) est
la référence visuelle pour toutes les présentations. Voir `skill/types/slides.md`.

---

## Partir de zéro — structure minimale

### Présentation (IBM Carbon)

```html
<!DOCTYPE html>
<html lang="fr" data-doc-type="presentation">
<head>
  <meta charset="UTF-8">
  <title>Ma présentation</title>
  <!-- Copier le bloc <style> complet depuis slides-empty.html (tokens Carbon) -->
</head>
<body>
  <header class="shell-header">…</header>
  <div class="toolbar">…</div>
  <div class="stage">
    <button class="nav-arrow" id="nav-prev" disabled>…</button>
    <div class="slide-frame">
      <article class="slide active" id="slide-0"
               data-type="slide" data-id="slide-0" data-title="Titre">
        <div class="slide-header">
          <div class="slide-eyebrow" data-editable="text">Section · Slide 01 / 01</div>
          <h1 class="slide-h1" data-editable="text"><strong>Titre</strong></h1>
          <p class="slide-subtitle" data-editable="text">Sous-titre</p>
        </div>
        <div class="slide-body" data-editable="text">…</div>
        <div class="slide-footer">
          <span class="slide-footer-left" data-editable="text">Produit</span>
          <span class="slide-footer-right">Slide 1 / 1</span>
        </div>
      </article>
    </div>
    <button class="nav-arrow" id="nav-next">…</button>
  </div>
  <div class="status-bar">…</div>
  <script>
    const TOTAL = 1;
    const slideNames = ["Titre"];
    // … (copier le bloc JS complet depuis slides-empty.html)
  </script>
</body>
</html>
```

En pratique: **toujours copier `slides-empty.html`**, jamais construire de zéro.

### Document

```html
<!DOCTYPE html>
<html lang="fr" data-doc-type="document">
<head><meta charset="UTF-8"><title>Mon document</title></head>
<body>
  <article data-type="document">
    <h1 data-editable="text">Titre</h1>
    <p data-editable="text">Introduction…</p>
  </article>
</body>
</html>
```

---

## data-editable: quoi mettre sur quels éléments

| Valeur | Usage |
|--------|-------|
| `data-editable="text"` | Zone de texte riche: active `contenteditable` + toolbar format + barre d'insertion |
| `data-editable="resize,reposition"` | Image déplaçable/redimensionnable |
| `data-editable="expand,reorder,resize"` | Conteneur Gantt |

**Règle:** Tout contenu que l'humain doit pouvoir modifier visuellement doit
avoir un attribut `data-editable`. Les éléments sans cet attribut ne sont pas
éditables via le browser (mais le LLM peut toujours les modifier).

---

## Ce que l'humain peut faire dans le browser (mode Édition activé)

### Formatting texte (toolbar flottante sur sélection)
- **Gras**, *italique*, <u>souligné</u>, ~~barré~~
- Exposant, indice
- Alignement gauche / centre / droite
- Taille de police (10px → 48px)
- Couleur de texte, couleur de surlignage
- Supprimer tout formatage

### Insertion (toolbar au-dessus de la zone au focus)
- **Image**: URL externe ou chemin relatif
- **Tableau**: N colonnes × M lignes, style IBM Carbon automatique
- Ligne séparatrice HR
- Lien hypertexte

### Context menus (clic droit sur éléments typés)
- `data-type="table"`: ajouter/supprimer ligne, ajouter/supprimer colonne, supprimer tableau
- `data-type="gantt-task"`: agrandir, réduire, renommer, supprimer
- `data-type="gantt"`: ajouter une tâche
- `data-type="arch-node"`: renommer, changer forme, supprimer
- `data-type="arch-diagram"`: ajouter un nœud
- `data-type="annotation"`: éditer texte, supprimer

---

## Workflow LLM: modifier du texte

```
1. update_start()
2. Lire le fichier HTML (chemin absolu dans get_status().file)
3. Localiser l'élément via data-id, data-title, ou contenu textuel
4. Modifier le contenu de l'élément data-editable="text"
5. Réécrire le fichier HTML COMPLET (DOCTYPE + head + body)
   — Conserver: head entier, data-doc-type, structure de navigation
   — Ne jamais supprimer: data-type, data-id, data-title sur les slides
6. update_end()
7. git add <fichier> && git commit -m "edit: description"
```

## Workflow LLM: ajouter une slide

```
1. update_start()
2. Lire le fichier HTML
3. Ajouter un <article class="slide" id="slide-N" data-type="slide"
   data-id="slide-N" data-title="…"> dans .slide-frame
4. Mettre à jour TOTAL et slideNames dans le <script>
5. Mettre à jour le slide-eyebrow et le slide-footer-right de la nouvelle slide
6. Réécrire le fichier complet
7. update_end()
8. git commit
```

## Workflow LLM: insérer une image (portabilité maximale)

```python
import base64
with open("image.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
# Insérer dans le HTML:
img = f'<img src="data:image/png;base64,{b64}" data-editable="resize,reposition" style="max-width:100%;height:auto;" />'
```

Chemin relatif si l'image est dans le même dossier:
```html
<img src="./screenshot.png" data-editable="resize,reposition" style="max-width:100%;" />
```

---

## Règles de nommage des fichiers

- Kebab-case: `mon-rapport-q1-2025.html`
- Pas d'espaces ni d'accents dans le nom
- Préfixes suggérés: `slides-`, `doc-`, `report-`, `roadmap-`

## Format des commits git

`type: description courte` (max 72 caractères)

| Type | Quand |
|------|-------|
| `feat:` | Nouveau slide, nouvelle section, nouveau composant |
| `edit:` | Modification de contenu existant |
| `style:` | Changement de style sans modification de contenu |
| `fix:` | Correction d'un bug ou d'une erreur |
| `export:` | Génération d'un fichier PPTX/DOCX |

Exemples:
```
feat: ajout slide "Roadmap 2025"
edit: mise à jour chiffres Q3 dans tableau résultats
feat: ajout schéma architecture microservices slide 4
```

---

## Quand utiliser data-doc-type="presentation" vs "document"

| Critère | presentation | document |
|---------|-------------|----------|
| Slides multiples | oui | non |
| Navigation prev/next | oui | non |
| Export PPTX optimal | oui | médiocre |
| Export DOCX optimal | médiocre | oui |
| Scrolling continu | non | oui |
| Template de référence | ibm-carbon.html | report-standard.html |
