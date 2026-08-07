# Types: Document (mode Word-like)

## Structure du conteneur

```html
<!DOCTYPE html>
<html data-doc-type="document">
<head>
  <meta charset="UTF-8">
  <title>Mon document</title>
  <style>
    article[data-type="document"] {
      max-width: 820px;
      margin: 0 auto;
      padding: 72px 80px;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 11pt;
      line-height: 1.6;
      color: #000;
    }
  </style>
</head>
<body>
  <article data-type="document" data-doc-template="perso">
    <!-- contenu -->
  </article>
</body>
</html>
```

- `data-doc-type="document"` sur `<html>` active le mode document (pas de navigation slides, bouton "＋ Bloc" en mode edition).
- `data-doc-template` sur l'`<article>` identifie la charte: `perso`, `ei`, ou absent pour le rapport standard.

## Les trois templates document

| Cle `new` | Fichier bootstrap | Charte |
|-----------|-------------------|--------|
| `doc` | `document-empty.html` | Rapport standard generique (Georgia, serif) |
| `doc-perso` | `document-perso-empty.html` | Charte Perso: Arial, headings colores |
| `doc-ei` | `document-ei-empty.html` | Euro-Information: bleu EI, orange, Segoe UI, logo embarque |

```bash
mcp-htmleditor new doc-perso mon-doc.html --serve
mcp-htmleditor new doc-ei    note-ei.html --serve
mcp-htmleditor new doc       rapport.html
```

Exemples riches a cloner: `templates/reference/documents/perso.html`,
`templates/reference/documents/euro-information.html`,
`templates/reference/documents/report-standard.html`.

### Charte Perso (doc-perso)

Police par defaut Arial. Chaque niveau porte une classe pour heriter du style:

| Element | Classe | Taille | Couleur | Style |
|---------|--------|--------|---------|-------|
| Titre | `h1.doc-title` | 22pt | `#000000` | gras, souligne, centre |
| Sous-titre | `p.doc-subtitle` | 15pt | `#666666` | normal |
| Heading 1 | `h1.doc-h1` | 18pt | `#000000` | gras, souligne |
| Heading 2 | `h2.doc-h2` | 16pt | `#1155cc` | normal |
| Heading 3 | `h3.doc-h3` | 14pt | `#6d9eeb` | normal |
| Heading 4 | `h4.doc-h4` | 12pt | `#b4a7d6` | normal |
| Heading 5 | `h5.doc-h5` | 11pt | `#c27ba0` | normal |
| Texte | `p` | 11pt | `#000000` | normal |

### Charte Euro-Information (doc-ei)

Bleu EI `#003A8D`, orange `#FBAE40`, police Segoe UI. En-tete avec filet bleu +
logo EI embarque en base64, headings en degrade de bleus, pied de page discret.
Meme systeme de classes (`doc-title`, `doc-subtitle`, `doc-h1`..`doc-h5`).

## Blocs inserables (mode edition)

En mode document + edition, la toolbar affiche un bouton **＋ Bloc** qui ouvre un
picker (meme modal que le picker de slides). Les blocs disponibles (definis dans
`static/doc-blocks.js`, objet `DOC_BLOCKS`):

| Cle | Rendu |
|-----|-------|
| `title` | `<h1 class="doc-title">` titre du document |
| `subtitle` | `<p class="doc-subtitle">` sous-titre |
| `heading1`..`heading5` | `<h1>`..`<h5>` avec classes `doc-h1`..`doc-h5` |
| `paragraph` | `<p>` texte courant |
| `table` | tableau 3x3 `data-type="table"` |
| `list` | liste a puces `<ul>` de trois elements |

Le bloc s'insere a la position du curseur (a la suite du bloc courant) ou a la fin
de l'article si aucun curseur n'est place. Les nouveaux blocs deviennent editables
automatiquement quand le mode edition est actif.

## Elements supportes

| Element | Usage |
|---------|-------|
| `<h1 class="doc-title">` | Titre principal du document (une occurrence) |
| `<p class="doc-subtitle">` | Sous-titre |
| `<h1>`..`<h5>` | Titres de niveaux 1 a 5 (classes `doc-h1`..`doc-h5`) |
| `<p>` | Paragraphe |
| `<ul>` / `<ol>` | Listes |
| `<sup>` / `<sub>` | Exposant / indice (notes, formules) |
| `<blockquote>` | Citation |
| `<pre><code>` | Bloc de code |
| `<table data-type="table">` | Tableau (voir `types/tables.md`) |
| `<img>` | Image inline (base64 pour la portabilite) |

Tous les elements textuels doivent porter `data-editable="text"` pour etre
editables via le navigateur.

**Regle absolue pour l'export DOCX:** utiliser de vraies balises semantiques
(`<h1>`..`<h5>`, `<p>`, `<table>`, `<ul>`/`<ol>`, `<sup>`, `<sub>`), jamais des
`<div>` styles. Pandoc s'appuie sur les balises pour mapper vers les styles Word.

## Superscript / subscript

La toolbar de format flottante (sur selection) inclut les boutons **x²** (exposant,
`document.execCommand('superscript')`) et **x₂** (indice, `subscript`). Utiles pour
les references de bas de page (`texte<sup>1</sup>`) et les formules
(`H<sub>2</sub>O`). Pandoc les convertit en runs superscript/subscript Word.

## Images inline

```html
<img src="data:image/png;base64,..."
     data-editable="resize,reposition"
     alt="Figure 1: Architecture"
     style="max-width:100%; margin:20px 0; display:block;" />
```

En mode edition, le bouton "Image" et le glisser-deposer embarquent l'image en
base64 (single-page, document autonome).

## Export DOCX: styles de heading preserves

L'export passe par pandoc (`export/to_docx.py`, `pandoc -f html ... --standalone`).
Pandoc mappe nativement:

| Balise HTML | Style Word |
|-------------|-----------|
| premier `<h1>` (titre) | Title |
| `<h1>` | Heading 1 |
| `<h2>` | Heading 2 |
| `<h3>` | Heading 3 |
| `<h4>` | Heading 4 |
| `<h5>` | Heading 5 |
| `<p>` | corps de texte |
| `<table>` | tableau Word |
| `<ul>`/`<ol>` | liste |
| `<sup>`/`<sub>` | exposant / indice |

Verification:

```bash
mcp-htmleditor new doc-perso /tmp/test-perso.html
mcp-htmleditor export docx /tmp/test-perso.html /tmp/test-perso.docx
pandoc /tmp/test-perso.docx -t markdown | grep -E '^#{1,6} '
```

La hierarchie de headings (`#`, `##`, ..., `#####`) doit etre preservee.

## Mise en page

### Single-column (defaut)
```html
<article data-type="document" data-layout="single-column">
```

### Two-column
```html
<article data-type="document" data-layout="two-column"
         style="columns:2; column-gap:40px;">
```

Note: le mode deux colonnes est deconseille pour les documents longs (coupures de
page imprevisibles a l'impression et a l'export).

## Differences avec le mode slides

| Critere | presentation | document |
|---------|-------------|----------|
| Navigation entre sections | prev/next | scroll continu |
| Structure | `<article data-type="slide">` | `<article data-type="document">` |
| Taille fixe | oui (16:9) | non (max-width) |
| Bouton toolbar (edition) | ＋ Slide | ＋ Bloc |
| Export optimal | PPTX | DOCX |

## Quand exporter en DOCX vs garder en HTML

**Exporter en DOCX si:** partage avec des utilisateurs Word, modifications
ulterieures dans Word, impression avec mise en page precise.

**Garder en HTML si:** consultation navigateur, liens hypertextes essentiels,
mise en page CSS complexe, edition en cours via mcp-htmleditor.
