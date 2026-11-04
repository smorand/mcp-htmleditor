# Types: Document (mode Word-like)

## Regles absolues

- `data-doc-type="document"` sur `<html>` active le mode document (pas de navigation slides, boutons "＋ Bloc" en edition).
- `data-doc-template` sur l'`<article data-type="document">` identifie la charte: `perso`, `ei`, ou absent pour le rapport standard.
- Toujours partir d'un bootstrap (`mcp-htmleditor new doc|doc-perso|doc-ei`), la charte vit dans son `<style>`.
- Tous les elements textuels portent `data-editable="text"` pour etre editables dans le navigateur.
- **Export DOCX: utiliser de vraies balises semantiques** (`<h1>`..`<h5>`, `<p>`, `<table>`, `<ul>`/`<ol>`, `<sup>`, `<sub>`), jamais des `<div>` styles. Pandoc mappe les balises vers les styles Word.
- Un seul `<h1 class="doc-title">` par document. Garder le `<title>` dans le `<head>` ET le `<h1 class="doc-title">` dans le corps.
- Figures en PNG, jamais en SVG (fichier, base64 ou balise `<svg>`): pandoc ne sait pas le dimensionner. Images en base64 pour la portabilite; un chemin relatif doit exister sur disque a l'export.
- Reordonner des blocs = deplacer les balises dans le fichier. Aucun attribut de position, aucun style inline, aucune transform ne s'ajoute: l'ordre du DOM est l'ordre visuel.
- Ne jamais ecrire la poignee de drag (classe `_mcp_drag_handle`, artefact d'edition retire avant serialisation et cote serveur).
- Tout tableau destine au DOCX porte un `<colgroup>` avec `style="width:X%"` sur chaque `<col>` (pandoc ignore `data-col-width`); `<thead>` obligatoire.
- Ne pas melanger les chartes: `doc-perso` et `doc-ei` ont leurs propres couleurs.

## Squelette

```html
<!DOCTYPE html>
<html lang="fr" data-doc-type="document">
<head><meta charset="UTF-8"><title>Mon document</title>
  <style>article[data-type="document"] { max-width:820px; margin:0 auto; padding:72px 80px;
    font-family:Arial,Helvetica,sans-serif; font-size:11pt; line-height:1.6; }</style>
</head>
<body>
  <article data-type="document" data-doc-template="perso">
    <h1 class="doc-title" data-editable="text">Rapport Q1</h1>
    <p class="doc-subtitle" data-editable="text">Sous-titre</p>
    <h1 class="doc-h1" data-editable="text">Resultats</h1>
    <p data-editable="text">Texte, H<sub>2</sub>O, note<sup>1</sup>.</p>
    <table data-type="table">
      <colgroup><col style="width:40%"><col style="width:60%"></colgroup>
      <thead><tr><th>Cle</th><th>Valeur</th></tr></thead>
      <tbody><tr><td>A</td><td>1</td></tr></tbody>
    </table>
    <figure><img src="data:image/png;base64,..." data-editable="resize,reposition"
      alt="Figure 1" style="max-width:100%; display:block;"><figcaption>Figure 1</figcaption></figure>
  </article>
</body>
</html>
```

## Chartes

| Cle `new` | Bootstrap | Charte |
|---|---|---|
| `doc` | `document-empty.html` | standard (Georgia, serif) |
| `doc-perso` | `document-perso-empty.html` | Arial, headings colores |
| `doc-ei` | `document-ei-empty.html` | bleu EI `#003A8D`, orange `#FBAE40`, Segoe UI, logo base64 |

Classes (memes noms dans `perso` et `ei`): `h1.doc-title`, `p.doc-subtitle`, `h1.doc-h1` a `h5.doc-h5`.
Perso: Title 22pt noir gras souligne centre; Subtitle 15pt `#666666`; H1 18pt noir gras souligne; H2 `#1155cc`; H3 `#6d9eeb`; H4 `#b4a7d6`; H5 `#c27ba0` (classes `doc-h2`..`doc-h5`, 16/14/12/11pt); texte 11pt `#000000`; en-tete de tableau Word `#1155cc`; A4, marges laterales 25 mm. EI: Subtitle 13pt `#50565B`, H5 en majuscules, en-tete de tableau `#003A8D`, marge haute 33 mm (loge l'en-tete).

## Blocs inserables (edition)

Boutons "＋ Bloc avant" / "Bloc après ＋" (`DOC_BLOCKS` de `doc-blocks.js`): `title`, `subtitle`, `heading1`..`heading5` (classes `doc-h1`..`doc-h5`), `paragraph`, `table` (3x3 `data-type="table"`), `list` (`<ul>` de 3 elements). Chaque bloc de premier niveau recoit une poignee de drag a sa gauche.

## Elements supportes

`<h1 class="doc-title">`, `<p class="doc-subtitle">`, `<h1>`..`<h5>`, `<p>`, `<ul>`/`<ol>`, `<sup>`/`<sub>` (boutons x² et x₂ de la barre de format), `<blockquote>`, `<pre><code>`, `<table data-type="table">` (voir `mcp-htmleditor skill --type tables`), `<img>`, `<figure>` + `<figcaption>`.

## Export DOCX (pandoc + reference.docx)

| Source HTML | Style Word |
|---|---|
| `h1.doc-title` | Title (une fois, via metadonnee pandoc) |
| `p.doc-subtitle` | Subtitle |
| `<h1>`..`<h5>` du corps | Heading1..Heading5 |
| `<p>` | FirstParagraph puis BodyText |
| `<ul>` / `<ol>` | Compact + numerotation |
| `<table>` + `<thead>` | tableau, en-tete repete |
| `<figure>` + `<figcaption>` | CaptionedFigure + ImageCaption |
| `<blockquote>` / `<pre><code>` | BlockText / SourceCode |
| `<img>` base64 PNG | embarque dans `word/media/` |

- `.doc-title` et `.doc-subtitle` sont extraits du corps (`--metadata title=` / `subtitle=`): le titre sort une seule fois, jamais en Heading1.
- La charte est lue sur `data-doc-template` et un `reference.docx` est genere (police, tailles, couleurs, en-tete de tableau), cache dans `~/.cache/mcp-htmleditor/reference/` (supprimer le dossier pour regenerer). Charte inconnue ou pandoc indisponible: styles pandoc par defaut et avertissement, sans echec.
- `ei`: en-tete Word repete (filet bleu, logo EI, EURO-INFORMATION) et pied (titre + `Page N`) sur chaque page, A4. `perso`: pied `Page N` centre, A4. Les blocs `.ei-doc-head` / `.ei-doc-foot` sont retires du corps. Le texte d'en-tete vient de la charte, pas du HTML.
- Charte `ei`: Segoe UI, Title 24pt `#003A8D` gras, H1 18pt `#003A8D`, H2 `#284AAA`, H3 `#285C99`, H4/H5 `#50565B`.
- Perdu ou approxime: `<hr>` devient un filet pleine largeur, styles inline de fond approximes.

Verifier: `pandoc doc.docx -t markdown | grep -E '^#{1,6} '` (hierarchie preservee, titre une seule fois).
Styles Word: `python3 -c "import zipfile,re; d=zipfile.ZipFile('doc.docx').read('word/document.xml').decode(); print(sorted(set(re.findall(r'w:pStyle w:val=\"([^\"]+)\"', d))))"` doit contenir `Title`, `Subtitle`, `Heading1`..`Heading5`. Autres mappings: `<colgroup>` largeurs proportionnelles (table a 100%), `<sup>`/`<sub>` runs vertAlign, `<b>`/`<i>`/`<u>` gras/italique/souligne, `<hr>` paragraphe vide avec filet. Exemples a cloner: `templates/reference/documents/perso.html`, `euro-information.html`, `report-standard.html`.

## Impression et mise en page

- Les templates embarquent `@media print` (`@page 20mm 25mm`, `break-after: avoid` sur les titres). A l'impression du HTML, l'en-tete EI n'apparait que sur la premiere page; pour un en-tete repete, passer par l'export DOCX.
- `data-layout="single-column"` par defaut; `data-layout="two-column"` (`columns:2`) deconseille pour les documents longs.
- Exporter en DOCX pour Word, impression precise; garder en HTML pour consultation, liens, CSS complexe.

Reference: templates/reference/documents/report-standard.html
