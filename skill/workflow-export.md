# Workflow: exporter en PPTX ou DOCX

## Deux voies d'export

### Via le navigateur (recommandé)

Quand l'éditeur est ouvert (`mcp-htmleditor serve` ou `start_server`), la toolbar
affiche un bouton **PPTX** (orange) ou **DOCX** (bleu) selon le type de document.
Cliquer déclenche le téléchargement directement — aucun agent, aucune CLI.

> **Prérequis**: le navigateur doit être ouvert sur l'éditeur.
> Utiliser `agent-browser` si l'utilisateur demande un export sans avoir
> le navigateur sous la main: l'agent ouvre l'éditeur, clique le bouton,
> récupère le fichier téléchargé.

### Via la CLI (sans navigateur)

```bash
# Export PPTX
mcp-htmleditor export pptx input.html output.pptx

# Export DOCX
mcp-htmleditor export docx input.html output.docx
```

## Choisir le format

| Critère | PPTX | DOCX |
|---------|------|------|
| Fichier de type présentation (slides) | **oui** | non |
| Fichier de type document (texte long) | non | **oui** |
| Partage avec équipe Office | oui | oui |
| Rendu fidèle des layouts CSS | bon (charte reproduite) | bon (via pandoc) |
| Gantt, schémas archi | formes natives éditables | perte de structure |

**Règle**: `data-doc-type="presentation"` → exporter en PPTX. `data-doc-type="document"` → exporter en DOCX.

## Ce que fait l'export PPTX

Une slide de sortie par élément `data-type="slide"` (n'importe quelle balise:
`<article>` comme `<section>`). À défaut d'attribut, l'export retombe sur
`article.slide` / `section.slide`. Rien en dehors des slides n'est exporté: la
barre d'outils, le `shell-header`, la `status-bar`, les `<script>` et les
`<style>` sont ignorés.

Format: 16:9, 13,333 x 7,5 pouces, c'est-à-dire le canvas de référence des
templates (960 x 540 px CSS). Un pixel CSS vaut donc exactement un point, et une
taille `font-size: 28px` devient 28 pt.

La charte est détectée sur le document (tokens `--ei-*` → Euro-Information,
`--ibm-*` / `--cds-*` → IBM Carbon, sinon charte générique) et les couleurs et
tailles sont relues dans la feuille de style du document (règles à une seule
classe) puis dans les `style=""` inline.

### Converti fidèlement

| Élément | Résultat dans le PPTX |
|---|---|
| `data-slide-type` EI `content` / `agenda` / `diagram` | cadre bleu, zone blanche arrondie, anneau de logo, pied de page |
| `data-slide-type` EI `section` | fond bleu plein + bandeau, titre centré |
| `data-slide-type` EI `title` | image de couverture (recadrée comme `object-fit: cover`), titre, sous-titre, logos alignés |
| Slides Carbon | fond, filet bleu sous l'en-tête, pied de page gris, séparateurs centrés |
| Titres, eyebrow, sous-titres, tuiles, encadrés | zones de texte à l'échelle typographique de la charte, police et couleurs comprises |
| `cds-grid` / `stat-grid` / `mention-wrap` | grille de tuiles avec fond, bordure et filet d'accent |
| `cds-notification` (+ `success` / `warning` / `error`) | panneau teinté avec barre latérale colorée |
| `<table>` / `cds-structured-list` | table PPTX: en-tête à la couleur de charte, largeurs du `colgroup` ou `data-col-width`, `colspan` et `rowspan` fusionnés, filets de ligne |
| `data-type="gantt"` | vraies barres positionnées (`left`/`width` inline, sinon `data-start`/`data-end`), échelle de trimestres, légende |
| `data-type="arch-node"` | forme native (`data-shape`: box, circle, diamond, cylinder, cloud), fond et bordure du style, libellé et sous-libellé |
| `data-type="arch-edge"` | segments et pointes de flèche pour les connecteurs CSS, textbox pour les flèches texte, libellés positionnés |
| `data-type="annotated-image"` | image + annotations positionnées **dans le repère de l'image** |
| Images | base64 décodé et embarqué, chemin relatif résolu par rapport au fichier HTML |
| `cw-bar` | barre horizontale proportionnelle |
| `<ul>` / `<ol>` | puces et numéros explicites |

### Approximé

- La mise en page est un flux vertical de blocs, pas un moteur CSS: les hauteurs
  sont estimées à partir du texte, puis les blocs souples (grilles, schémas,
  tables) absorbent l'espace libre. Un contenu très dense est réduit
  proportionnellement au lieu de déborder.
- Les colonnes d'une `cds-grid` sont de largeur égale (le `grid-template-columns`
  personnalisé n'est pas lu).
- Les dégradés sont ramenés à leur première couleur.
- Les polices ne sont pas embarquées: le PPTX demande Segoe UI (EI) ou IBM Plex
  Sans (Carbon), avec le repli système si la police est absente du poste.
- Les sélecteurs CSS descendants sont indexés sur leur dernière classe:
  `.carte .nom` s'applique à toute classe `nom` du document. Sur un document de
  slides cohérent, l'écart est invisible.
- Les rayons d'arrondi et les ombres sont simplifiés.

### Perdu

- Les animations et transitions CSS.
- Les SVG inline (aucune conversion vectorielle): utiliser un `<img>` PNG.
- Les fonds de `<span>` inline (`tag-blue`, `tag-green`...): seule la couleur du
  texte est conservée.
- Les compteurs CSS (`counter-increment`) et les pseudo-éléments
  (`::before`, `::after`).
- Les images distantes (`http://`, `https://`): elles sont signalées et ignorées,
  il faut les télécharger ou les passer en base64.

### Diagnostics

`mcp-htmleditor export pptx` affiche le nombre de slides produites, liste chaque
élément ignoré (image introuvable, image distante, Gantt sans tâche, schéma sans
nœud) sur la sortie d'erreur, et sort en code non nul si aucune slide n'a pu être
écrite. Un document sans élément `data-type="slide"` produit une slide unique
avec un avertissement explicite.

## Limitations connues de la conversion

### HTML → DOCX

Ce que fait l'export (`export/to_docx.py`): il prétraite le HTML (BeautifulSoup),
génère un `reference.docx` à la charte, puis appelle pandoc.

- **Structure fidèle**: titres h1-h5, listes à puces et numérotées, tableaux avec
  en-tête répété, sup/sub, gras/italique/souligné, `figure`/`figcaption`,
  `blockquote`, `pre/code`.
- **Titre unique**: `.doc-title` et `.doc-subtitle` sont retirés du corps et passés en
  métadonnées pandoc, donc le titre sort une seule fois en style Word `Title`, suivi du
  sous-titre en style `Subtitle`. Plus de doublon `Heading1`.
- **Charte transportée**: la charte est lue sur `data-doc-template` de l'`<article>`
  (`perso`, `ei`) et un `reference.docx` est généré puis passé en `--reference-doc`.
  Police, tailles, couleurs, soulignements des titres, taille du corps et fond de
  l'en-tête des tableaux sont reproduits dans Word. Sans cet attribut (charte standard),
  l'export garde les styles pandoc par défaut.
- **Figures en PNG, jamais en SVG**: pandoc ne peut pas dimensionner un SVG (il lui
  faudrait `rsvg-convert`) et Word ancien ne l'affiche pas. L'export avertit dès qu'il
  voit un SVG (fichier, base64 ou balise `<svg>`) et remonte aussi les avertissements de
  pandoc à l'écran. Les images **base64 PNG sont bien embarquées** dans `word/media/`,
  comme dans l'export PPTX.
- **En-tête et pied de page Word répétés**: le `reference.docx` embarque
  `word/header1.xml` et `word/footer1.xml`, référencés depuis le `w:sectPr`
  (`w:headerReference` / `w:footerReference`) que pandoc réutilise. Résultat: en charte
  `ei`, filet bleu + logo EI + mention EURO-INFORMATION en en-tête et titre du document
  + `Page N` en pied, sur **chaque page**; en charte `perso`, `Page N` centré. Les blocs
  décoratifs `.ei-doc-head` / `.ei-doc-foot` sont retirés du corps pour éviter le
  doublon, sauf si la génération du `reference.docx` a échoué (dans ce cas ils restent
  dans le corps, comme avant). Le numéro de page est un vrai champ Word `PAGE`, le titre
  un champ `TITLE`: ils se recalculent. Le texte de l'en-tête vient de la charte, pas du
  HTML édité.
- Les styles CSS inline (couleurs de fond de bloc, filets décoratifs) sont approximés.
- Les éléments `data-type="gantt"` et `data-type="arch-diagram"` peuvent être mal rendus.
- Les images avec chemin relatif doivent exister sur disque au moment de l'export; elles
  sont résolues relativement au dossier du fichier HTML (`--resource-path`).

### Chartes DOCX disponibles

| `data-doc-template` | Charte |
|---|---|
| `perso` | Arial; Title 22pt noir gras souligné centré; Subtitle 15pt #666666; H1 18pt noir gras souligné; H2 #1155cc; H3 #6d9eeb; H4 #b4a7d6; H5 #c27ba0; corps 11pt; en-tête de tableau #1155cc; A4, pied de page `Page N` centré |
| `ei` | Segoe UI; Title 24pt #003A8D gras; Subtitle 13pt #50565B; H1 18pt #003A8D; H2 #284AAA; H3 #285C99; H4 #50565B; H5 #50565B majuscules; corps 11pt; en-tête de tableau #003A8D; A4, en-tête logo EI + EURO-INFORMATION, pied titre + `Page N` |
| absent | standard: styles pandoc par défaut, aucun en-tête, géométrie de page inchangée |

Les `reference.docx` sont générés à partir de celui de pandoc
(`pandoc --print-default-data-file reference.docx`), patchés dans `word/styles.xml`
pour la charte et dans `word/document.xml` + `word/_rels/document.xml.rels` +
`[Content_Types].xml` pour l'en-tête et le pied (modules `export/reference_docx.py` et
`export/docx_header_footer.py`), puis mis en cache dans
`~/.cache/mcp-htmleditor/reference/`. Pour forcer une régénération: supprimer ce dossier.
Ajouter une charte = ajouter un `Charter` dans `export/reference_docx.py` et bumper
`GENERATOR_VERSION` si la logique de patch change.

Repli sans échec: charte inconnue, pandoc trop ancien ou cache non inscriptible, l'export
continue avec les styles pandoc par défaut et affiche un avertissement.

La police EI est Segoe UI: sur une machine sans cette police (macOS, Linux), Word ou
LibreOffice substituent une police, alors que le fichier reste correct pour un poste
Windows.

### Vérifier un export PPTX

```bash
mcp-htmleditor export pptx pres.html /tmp/pres.pptx

# structure réellement produite
python3 -c "from pptx import Presentation; p=Presentation('/tmp/pres.pptx'); print('slides:', len(p.slides)); print('images:', sum(1 for s in p.slides for sh in s.shapes if sh.shape_type == 13))"

# rendu visuel final, une image par slide, à relire
soffice --headless --convert-to pdf /tmp/pres.pptx --outdir /tmp/ && pdftoppm -jpeg -r 72 /tmp/pres.pdf /tmp/slide
```

### Vérifier un export DOCX

```bash
mcp-htmleditor export docx doc.html doc.docx

# styles Word réellement produits (doit contenir Title, Subtitle, Heading1..Heading5)
python3 -c "import zipfile,re; d=zipfile.ZipFile('doc.docx').read('word/document.xml').decode(); print(sorted(set(re.findall(r'w:pStyle w:val=\"([^\"]+)\"', d))))"

# rendu visuel final
soffice --headless --convert-to pdf doc.docx --outdir /tmp/ && pdftoppm -jpeg -r 90 /tmp/doc.pdf /tmp/doc
```

## Post-processing recommandé

### Après export PPTX
1. Ouvrir dans PowerPoint / LibreOffice Impress
2. Relire les slides les plus denses: les hauteurs sont estimées, un texte très
   long peut demander un ajustement
3. Vérifier les avertissements affichés par la commande (images ignorées)
4. Toutes les formes sont natives et éditables: corriger directement dans Office

### Après export DOCX
1. Ouvrir dans Word / LibreOffice Writer
2. Vérifier que le titre n'apparaît qu'une fois et que la charte est bien appliquée
3. Ajouter un en-tête / pied de page Word si le document en a besoin (le décor EI du
   HTML n'est pas un en-tête de page)
4. Vérifier la table des matières si présente

## Règles sur les images

- **Chemin absolu**: toujours sûr pour l'export
- **Chemin relatif**: résolu par rapport à l'emplacement du fichier HTML (pas du
  CWD), en PPTX comme en DOCX
- **base64**: portable et embarqué dans le PPTX comme dans le DOCX; c'est le
  format recommandé
- **URL externe**: non supporté (l'export l'ignore avec un avertissement,
  télécharger l'image d'abord)

## Exemple complet

```bash
# Préparer le fichier
cp templates/reference/slides/presentation-standard.html /tmp/ma-pres.html

# Exporter
mcp-htmleditor export pptx /tmp/ma-pres.html /tmp/ma-pres.pptx

# Ouvrir
open /tmp/ma-pres.pptx
```
