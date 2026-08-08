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

En mode document + edition, la toolbar affiche deux boutons **＋ Bloc avant** et
**Bloc après ＋** qui ouvrent un picker (meme modal que le picker de slides). Le bloc
choisi s'insere avant ou apres le bloc courant (base sur la position du curseur),
ou en tete/fin de l'article si aucun curseur n'est place. Les blocs disponibles
(definis dans `static/doc-blocks.js`, objet `DOC_BLOCKS`):

| Cle | Rendu |
|-----|-------|
| `title` | `<h1 class="doc-title">` titre du document |
| `subtitle` | `<p class="doc-subtitle">` sous-titre |
| `heading1`..`heading5` | `<h1>`..`<h5>` avec classes `doc-h1`..`doc-h5` |
| `paragraph` | `<p>` texte courant |
| `table` | tableau 3x3 `data-type="table"` |
| `list` | liste a puces `<ul>` de trois elements |

Les nouveaux blocs deviennent editables automatiquement quand le mode edition est
actif, et recoivent une poignee de drag (voir ci-dessous).

## Reordonner les blocs par glisser-deposer (drag handle)

En mode document + edition, chaque bloc de premier niveau de l'article (les enfants
directs: `<h1>`..`<h5>`, `<p>`, `<ul>`/`<ol>`, `<table>`, `<blockquote>`, etc.)
recoit une petite poignee (icone ⠿) a sa gauche, visible seulement en mode edition.
L'humain tire la poignee pour reordonner verticalement les blocs; une ligne bleue
indique la position de drop.

**Regle absolue de lisibilite:** apres le drop, l'ordre des blocs dans le DOM est
exactement l'ordre visuel. RIEN d'autre ne change: aucun attribut de position ajoute,
aucun style inline, aucune transform. Le HTML reste une sequence propre
`<h1>..</h1><p>..</p><table>..</table>` dans le nouvel ordre. La poignee est un
artefact d'edition (classe `_mcp_drag_handle`): elle n'est jamais ecrite dans le
fichier (retiree avant serialisation et strippee cote serveur). Le LLM peut donc
reordonner les blocs simplement en deplacant les balises dans le fichier.

Exemple: un article

```html
<article data-type="document" data-doc-template="perso">
  <h1 class="doc-title" data-editable="text">Rapport Q1</h1>
  <p data-editable="text">Introduction.</p>
  <h1 class="doc-h1" data-editable="text">Resultats</h1>
</article>
```

apres avoir remonte le paragraphe sous le titre reste tout aussi lisible, sans
aucun attribut supplementaire (seul l'ordre des balises change).


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
| `<figure>` + `<figcaption>` | Illustration avec legende (mappee en Word: CaptionedFigure + ImageCaption) |

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

## Export DOCX: styles Word reellement produits

L'export passe par pandoc (`export/to_docx.py`, `pandoc -f html ...`), avec deux
traitements maison: le HTML est pretraite pour ne produire qu'un seul titre, et un
`reference.docx` est genere a la volee pour transporter la charte. Mapping verifie
avec pandoc 3.10 (styles lus dans `word/document.xml`):

| Source HTML | Style Word produit |
|-------------|--------------------|
| `h1.doc-title` | **Title** (une seule fois, via metadonnee pandoc) |
| `p.doc-subtitle` | **Subtitle** (style Word natif) |
| `<h1>` du corps (hors `.doc-title`) | Heading1 |
| `<h2>` | Heading2 |
| `<h3>` | Heading3 |
| `<h4>` | Heading4 |
| `<h5>` | Heading5 |
| `<p>` | FirstParagraph (premier apres un titre) puis BodyText |
| `<ul>` / `<ol>` | Compact + numbering (puces / numeros conserves) |
| `<table>` + `<thead>` | tableau Word, ligne d'en-tete repetee (`tblHeader`) |
| `<colgroup><col style="width:X%">` | largeurs de colonnes proportionnelles, table a 100% |
| `<sup>` / `<sub>` | runs `vertAlign` superscript / subscript |
| `<b>` / `<i>` / `<u>` | gras / italique / souligne |
| `<figure>` + `<figcaption>` | CaptionedFigure + ImageCaption |
| `<blockquote>` | BlockText |
| `<pre><code>` | SourceCode |
| `<img src="data:image/png;base64,...">` | image PNG embarquee dans `word/media/` |
| `<hr>` | paragraphe vide avec filet horizontal |

**Titre unique (corrige).** Pandoc tire le style Word `Title` de la metadonnee lue
dans `<head><title>`, et le `<h1 class="doc-title">` du corps devenait en plus un
`Heading1`: le titre sortait deux fois. L'export extrait maintenant `.doc-title` et
`.doc-subtitle` du corps, les passe en metadonnee pandoc (`--metadata title=` /
`subtitle=`) et exporte le HTML restant. Resultat: `Title` puis `Subtitle`, une seule
fois, et le sous-titre gagne un vrai style Word au lieu d'un paragraphe ordinaire.
Rien a changer dans les templates: garder le `<title>` dans le `<head>` (onglet du
navigateur) et le `<h1 class="doc-title">` dans le corps (rendu HTML).

**La charte est transportee (corrige).** L'export lit `data-doc-template` sur
l'`<article>`, genere un `reference.docx` pour cette charte et le passe a pandoc via
`--reference-doc`. Sont reproduits dans Word: police, tailles, couleurs et
soulignements de `Title`, `Subtitle`, `Heading1`..`Heading5`, taille du corps, et fond
de la ligne d'en-tete des tableaux.

| `data-doc-template` | Charte appliquee |
|---|---|
| `perso` | Arial, Title 22pt noir gras souligne centre, H1 18pt noir gras souligne, H2 #1155cc, H3 #6d9eeb, H4 #b4a7d6, H5 #c27ba0, en-tete de tableau #1155cc |
| `ei` | Segoe UI, Title 24pt #003A8D gras, H1 18pt #003A8D, H2 #284AAA, H3 #285C99, H4/H5 #50565B (H5 en majuscules), en-tete de tableau #003A8D |
| absent | charte standard: styles pandoc par defaut, aucun `reference.docx` |

Les `reference.docx` sont mis en cache dans `~/.cache/mcp-htmleditor/reference/` et
regeneres si absents. Une charte inconnue ou une generation impossible (pandoc
indisponible) n'echoue pas: l'export continue avec les styles pandoc par defaut et
affiche un avertissement.

Non transporte, meme avec la charte: l'en-tete et le pied de page EI (blocs dans le
flux, donc du corps de texte dans Word, pas un en-tete de page repete), et le filet
`<hr>` qui devient un filet horizontal pleine largeur.

**Figures en PNG, jamais en SVG.** Pandoc ne sait pas dimensionner un SVG (il lui
faudrait `rsvg-convert`) et Word ancien ne l'affiche pas. L'export detecte les SVG
(fichier, base64, balise `<svg>` en ligne) et avertit; les avertissements de pandoc
sont eux aussi remontes a l'ecran.

Verification:

```bash
mcp-htmleditor new doc-perso /tmp/test-perso.html
mcp-htmleditor export docx /tmp/test-perso.html /tmp/test-perso.docx
pandoc /tmp/test-perso.docx -t markdown | grep -E '^#{1,6} '
python3 -c "import zipfile,re; d=zipfile.ZipFile('/tmp/test-perso.docx').read('word/document.xml').decode(); print(sorted(set(re.findall(r'w:pStyle w:val=\"([^\"]+)\"', d))))"
```

La hierarchie de headings (`#`, `##`, ..., `#####`) doit etre preservee, la liste de
styles doit contenir `Title`, `Subtitle`, `Heading1`..`Heading5`, et le texte du titre
ne doit apparaitre qu'une fois (jamais en `Heading1`).

Pour verifier la charte reellement embarquee:

```bash
python3 -c "import zipfile; print(zipfile.ZipFile('/tmp/test-perso.docx').read('word/styles.xml').decode()[:2000])" | grep -o 'w:ascii="[^\"]*"' | head -1
```

## Impression du HTML

Les templates document embarquent un bloc `@media print` (marges `@page 20mm 25mm`,
fond blanc, pas d'ombre, `break-after: avoid` sur les titres, `break-inside: avoid`
sur les figures et les lignes de tableau, `thead` repete via
`display: table-header-group`). Consequence a connaitre: **l'en-tete du template EI
(filet bleu, logo, filet orange) n'apparait que sur la premiere page**, en impression
comme a l'export DOCX. C'est un bloc dans le flux, pas un en-tete de page; il n'y a
pas de solution CSS fiable (les elements `position: fixed` ne sont plus repetes par
Chrome headless). Un vrai en-tete Word repete demanderait un `reference.docx` avec un
`headerReference`, ce que la generation de charte actuelle ne fait pas (elle ne patche
que `word/styles.xml`).

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
| Bouton toolbar (edition) | ＋ Slide avant / Slide après | ＋ Bloc avant / Bloc après |
| Export optimal | PPTX | DOCX |

## Quand exporter en DOCX vs garder en HTML

**Exporter en DOCX si:** partage avec des utilisateurs Word, modifications
ulterieures dans Word, impression avec mise en page precise.

**Garder en HTML si:** consultation navigateur, liens hypertextes essentiels,
mise en page CSS complexe, edition en cours via mcp-htmleditor.
