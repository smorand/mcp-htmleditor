Exporter en PPTX ou DOCX. **Règle**: `data-doc-type="presentation"` s'exporte en PPTX, `data-doc-type="document"` en DOCX.

## Deux voies

- Navigateur (recommandé): la toolbar affiche le bouton **PPTX** ou **DOCX** selon le type; le clic télécharge le fichier. Le navigateur doit être ouvert sur l'éditeur (sinon `agent-browser` ouvre l'éditeur, clique et récupère le fichier).
- CLI, sans navigateur:

```bash
mcp-htmleditor export pptx input.html output.pptx
mcp-htmleditor export docx input.html output.docx
```

| Critère | PPTX | DOCX |
|---|---|---|
| Fichier de slides | oui | non |
| Texte long | non | oui |
| Gantt, schémas | formes natives éditables | perte de structure |

## Export PPTX

Une slide de sortie par élément `data-type="slide"` (`<article>` ou `<section>`; repli sur `article.slide` / `section.slide`). Rien hors des slides n'est exporté (barre d'outils, `shell-header`, `status-bar`, `<script>`, `<style>`). Format 16:9, 13,333 x 7,5 pouces, canevas de référence 960 x 540 px: un pixel CSS vaut un point, `font-size: 28px` devient 28 pt.

La charte est détectée (tokens `--med-*` médicale, `--ei-*` Euro-Information, `--ibm-*` / `--cds-*` Carbon, sinon générique); couleurs et tailles sont relues dans la feuille de style puis dans les `style=""` inline. Formes de règles CSS indexées: `.classe`, `.classe.variante`, `.slide.dark .classe`. Les sélecteurs à combinateur (`>`), d'attribut ou qualifiés par une balise (`ul.med-list li`) ne sont pas relus.

### Converti fidèlement

| Élément | Résultat |
|---|---|
| slides EI `content` / `agenda` / `diagram` / `section` / `title` | cadre bleu, zone arrondie, pied, fond plein, couverture |
| charte médicale | bandeau gris, filet teal puis orange, bande de sources en bas à gauche, numéro de page à droite; `image` / `grid` / `compare` en `class="slide dark"` en fond `#0B0E11` |
| slides Carbon | fond, filet bleu sous l'en-tête, pied gris |
| titres, eyebrow, tuiles, encadrés | zones de texte à l'échelle de la charte |
| `cds-grid` / `stat-grid` / `mention-wrap` | grille de tuiles |
| `cds-notification` (+ `success` / `warning` / `error`) | panneau teinté à barre latérale |
| `<table>` / `cds-structured-list` | table PPTX: en-tête à la couleur de charte, largeurs du `colgroup` ou `data-col-width`, `colspan` et `rowspan` fusionnés |
| `data-type="gantt"` | barres positionnées (`left`/`width` inline, sinon `data-start`/`data-end`), échelle, légende |
| `data-type="arch-node"` | forme native (`data-shape`: box, circle, diamond, cylinder, cloud) |
| `data-type="arch-edge"` | segments, pointes, libellés |
| `data-type="annotated-image"` | image + annotations dans le repère de l'image |
| images | base64 décodé et embarqué; chemin relatif résolu par rapport au fichier HTML |
| `cw-bar`, `<ul>` / `<ol>` | barre proportionnelle, puces et numéros |

### Approximé

- Mise en page en flux vertical de blocs: hauteurs estimées, un contenu dense est réduit au lieu de déborder. Un conteneur `display:flex` en ligne avec 2 colonnes ou plus est reconnu si au moins un enfant porte une largeur (`flex`, `flex-basis` ou `width`); sans indice de largeur il reste une pile verticale.
- Colonnes de `cds-grid` égales (`grid-template-columns` non lu); dégradés ramenés à leur première couleur; rayons et ombres simplifiés.
- Polices non embarquées (Segoe UI pour EI, IBM Plex Sans pour Carbon, repli système).
- Sélecteurs descendants indexés sur leur dernière classe.

### Notes du présentateur

L'`<aside data-role="speaker-notes">` enfant direct d'une slide n'est jamais une forme: son texte (retours à la ligne gardés) va dans la page de notes de la slide. Sans `aside`, pas de page de notes.

### Perdu

- Animations et transitions CSS; compteurs CSS et pseudo-éléments (`::before`, `::after`).
- SVG inline (aucune conversion vectorielle): utiliser un `<img>` PNG.
- Fonds de `<span>` (`tag-blue`, `tag-green`, `.med-badge`): seule la couleur du texte reste.
- Images distantes (`http://`, `https://`): signalées et ignorées, les télécharger ou passer en base64.
- Le `max-width` d'un texte (barre de largeur de l'éditeur): la zone de texte garde la largeur de son bloc.

### Diagnostics et vérification

La commande affiche le nombre de slides produites, liste sur stderr chaque élément ignoré, et sort en code non nul si aucune slide n'est écrite. Un document sans `data-type="slide"` est refusé : `error: No slide exported: check that the document has data-type="slide" elements.`

```bash
mcp-htmleditor export pptx pres.html /tmp/pres.pptx
python3 -c "from pptx import Presentation; p=Presentation('/tmp/pres.pptx'); print('slides:', len(p.slides))"
soffice --headless --convert-to pdf /tmp/pres.pptx --outdir /tmp/ && pdftoppm -jpeg -r 72 /tmp/pres.pdf /tmp/slide
```

Après export: relire les slides denses dans PowerPoint ou LibreOffice, vérifier les avertissements; toutes les formes sont natives et éditables.

## Export DOCX

`export/to_docx.py` prétraite le HTML (BeautifulSoup), génère un `reference.docx` à la charte, puis appelle pandoc.

- Structure fidèle: h1 à h5, listes, tableaux avec en-tête répété, sup/sub, gras/italique/souligné, `figure`/`figcaption`, `blockquote`, `pre/code`.
- Titre unique: `.doc-title` et `.doc-subtitle` sortent du corps vers les métadonnées pandoc (styles Word `Title` et `Subtitle`), jamais en `Heading1`. Garder `<title>` dans le `<head>` et `<h1 class="doc-title">` dans le corps.
- Charte lue sur `data-doc-template` de l'`<article>` (`perso`, `ei`), `reference.docx` passé à pandoc par `--reference-doc`; absent: styles pandoc par défaut. Repli sans échec avec avertissement si la charte est inconnue ou la génération impossible.
- En charte `ei`, en-tête (filet bleu, logo, EURO-INFORMATION) et pied (titre, `Page N`) sont de vrais en-tête et pied Word répétés; les blocs `.ei-doc-head` / `.ei-doc-foot` sont retirés du corps. En `perso`, pied `Page N` centré. Le texte de l'en-tête vient de la charte, pas du HTML.
- Figures en PNG, **jamais en SVG**: pandoc ne dimensionne pas un SVG; l'export avertit sur tout SVG (fichier, base64, balise `<svg>`). Les PNG base64 sont embarqués dans `word/media/`.
- Gantt et `arch-diagram` peuvent être mal rendus; styles CSS inline (fonds de bloc, filets) approximés.
- Les images en chemin relatif doivent exister sur disque (résolues depuis le dossier du HTML, `--resource-path`).
- Tableau destiné au DOCX: toujours un `<colgroup>` avec `style="width:X%"` (pandoc ignore `data-col-width`).

| `data-doc-template` | Charte |
|---|---|
| `perso` | Arial; Title 22pt gras souligné centré; H1 18pt; H2 #1155cc; H3 #6d9eeb; H4 #b4a7d6; H5 #c27ba0; corps 11pt; A4 |
| `ei` | Segoe UI; Title 24pt #003A8D; H1 18pt #003A8D; H2 #284AAA; H3 #285C99; H4/H5 #50565B; corps 11pt; A4 |
| absent | styles pandoc par défaut, aucun en-tête |

Les `reference.docx` sont en cache dans `~/.cache/mcp-htmleditor/reference/` (supprimer le dossier pour régénérer).

```bash
mcp-htmleditor export docx doc.html doc.docx
pandoc doc.docx -t markdown | grep -E '^#{1,6} '
```

La liste des styles doit contenir `Title`, `Subtitle`, `Heading1` à `Heading5`, et le titre ne doit apparaître qu'une fois. Après export: vérifier la charte dans Word ou LibreOffice.

## Images

Base64: recommandé, embarqué en PPTX comme en DOCX. Chemin relatif: résolu par rapport au fichier HTML, pas au CWD. Chemin absolu: sûr. URL externe: non supportée (ignorée avec avertissement, télécharger d'abord).
