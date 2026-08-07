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

La méthode recommandée: la commande `new` copie le bon bootstrap.

```bash
mcp-htmleditor templates                        # lister les templates
mcp-htmleditor new ei     ma-presentation.html  # Euro-Information (slides)
mcp-htmleditor new carbon ma-presentation.html  # IBM Carbon (slides)
mcp-htmleditor new doc    mon-document.html      # Document standard
mcp-htmleditor new doc-perso mon-doc.html        # Document charte Perso
mcp-htmleditor new doc-ei    note-ei.html        # Document Euro-Information
mcp-htmleditor new ei ma-presentation.html --serve   # + ouvre l'éditeur
```

Équivalent manuel:
```bash
cp templates/bootstrap/slides-ei-empty.html mon-fichier.html
```

Ensuite ouvrir dans l'éditeur:
```
start_server(file="mon-fichier.html")   # via MCP
# ou: mcp-htmleditor serve mon-fichier.html
```

Templates de référence (exemples riches à consulter/cloner, en lecture seule):
`templates/reference/slides/euro-information.html`,
`templates/reference/slides/ibm-carbon.html`. Voir `skill/types/slides.md`.

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
  <article data-type="document" data-doc-template="perso">
    <h1 class="doc-title" data-editable="text">Titre</h1>
    <p class="doc-subtitle" data-editable="text">Sous-titre</p>
    <p data-editable="text">Introduction…</p>
  </article>
</body>
</html>
```

En pratique: **toujours copier un bootstrap document** (`doc`, `doc-perso`,
`doc-ei`) plutôt que construire de zéro; les chartes (Arial/EI) vivent dans le
`<style>` du template. Voir `skill/types/document.md`.

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
- **Image**: sélecteur de fichier local ou glisser-déposer, embarquée en base64 (single-page)
- **Tableau**: N colonnes × M lignes, style IBM Carbon automatique
- Ligne séparatrice HR
- Lien hypertexte

### Slides (mode présentation + édition)
Boutons dans la toolbar du serveur:
- **＋ Slide avant** / **Slide après ＋**: ouvre un sélecteur de type de slide (title, agenda, section, content, diagram)
- **🗑 Slide**: supprime la slide courante

L'insertion et la suppression renumérotent automatiquement tout le document
(ids, TOTAL, slideNames, eyebrow, footer, dropdown). Voir `skill/types/slides.md`.

### Blocs document (mode document + édition)
Bouton dans la toolbar du serveur:
- **＋ Bloc**: ouvre un sélecteur de blocs (titre, sous-titre, h1-h5, paragraphe,
  tableau, liste). Le bloc s'insère à la position du curseur, ou à la fin de
  l'article si aucun curseur n'est placé. Les blocs héritent de la charte du
  template actif (perso, ei, standard). Voir `skill/types/document.md`.

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

## Workflow LLM: créer et exporter un document

```
1. mcp-htmleditor new doc-perso mon-doc.html   (ou doc / doc-ei)
2. start_server(file="mon-doc.html")
3. update_start()
4. Lire le fichier, ajouter des <h1 class="doc-h1">…<h5 class="doc-h5">,
   <p>, <ul>/<ol>, <table data-type="table">, avec data-editable="text"
   — balises sémantiques uniquement (pas de <div> stylés)
5. Réécrire le fichier complet (DOCTYPE + head + body), conserver le <style>
6. update_end()
7. mcp-htmleditor export docx mon-doc.html mon-doc.docx
8. Vérifier: pandoc mon-doc.docx -t markdown | grep -E '^#{1,6} '
9. git commit
```

Règles document détaillées (chartes, blocs, headings, export DOCX):
`skill/types/document.md`.

## Workflow LLM: insérer une image (portabilité maximale)

**Le document est single-page: toutes les images doivent être embarquées en base64.**
Jamais de chemin externe ni de fichier séparé, le HTML doit rester autonome et envoyable tel quel.

### Côté humain (browser)
En mode édition, deux façons d'insérer une image locale, toutes deux embarquées automatiquement en base64:
- **Bouton « Image »** dans la barre d'insertion: ouvre le sélecteur de fichier du PC
- **Glisser-déposer** un fichier image depuis le Finder/Explorateur sur une zone éditable

Rien n'est uploadé sur un serveur; l'image est lue localement et insérée comme `data:image/...;base64,...`.

### Côté LLM (écriture directe)
```python
import base64, mimetypes
path = "image.png"
mime = mimetypes.guess_type(path)[0] or "image/png"
b64  = base64.b64encode(open(path, "rb").read()).decode()
img  = f'<img src="data:{mime};base64,{b64}" data-editable="resize,reposition" style="max-width:100%;height:auto;" />'
```

**Règle absolue:** ne jamais référencer une image par chemin relatif ou URL externe si le document doit être partagé. Toujours base64.

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
