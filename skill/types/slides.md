# Skill — Types: Slides (IBM Carbon et Euro-Information)

## Vue d'ensemble

Deux chartes de présentation, **jamais mélangeables**:

| Charte | Bootstrap (`new <key>`) | Référence complète |
|---|---|---|
| IBM Carbon | `carbon` → `templates/bootstrap/slides-empty.html` | `templates/reference/slides/ibm-carbon.html` |
| Euro-Information | `ei` → `templates/bootstrap/slides-ei-empty.html` | `templates/reference/slides/euro-information.html`, exemple à 9 slides et tous composants: `templates/reference/slides/example-ei-complete.html` |

Les deux partagent le squelette de fichier, les `data-slide-type` et le script de
navigation. Tout le reste diffère: classes, tokens, mise en valeur du titre, pied de page.
**Avant d'écrire du markup, identifier la charte du document** (`--ei-blue` dans le CSS ou
`.slide-cover-logos` dans le corps = Euro-Information) et n'utiliser que ses classes.

### Table de correspondance des classes

| Rôle | IBM Carbon | Euro-Information |
|---|---|---|
| Cadre interne de la slide | (aucun, la slide est le cadre) | `.slide-inner` (`inset:10px`, arrondi 16px sur fond bleu) |
| Zone de titre | `.slide-header` (bordure basse bleue 4px) | pas de conteneur, enfants directs de `.slide-inner` |
| Sur-titre | `.slide-eyebrow` | `.slide-eyebrow` |
| Titre | `.slide-h1` + `<strong>` pour la partie bold | `.slide-h1` + `<span>` pour la partie orange |
| Filet sous le titre | (la bordure de `.slide-header`) | `.slide-title-rule` (3px orange, 64px) |
| Sous-titre | `.slide-subtitle` | `.slide-subtitle` |
| Corps | `.slide-body` | `.slide-body` |
| Pied de page | `.slide-footer` + `.slide-footer-left` / `.slide-footer-right` | `.slide-foot` + `.slide-foot-logo > .logo-disc > img`, `.slide-foot-page`, `.slide-foot-title` |
| Compteur de page | `.slide-footer-right` = `Slide N / TT` | `.slide-foot-page` = `N` seul |
| Tokens de couleur | `--ibm-*`, `--cds-*` | `--ei-blue`, `--ei-blue-2`, `--ei-orange`, `--ei-coral`, `--ei-gray-dark` |
| Police | IBM Plex Sans | `--ei-font` (Segoe UI, Calibri) |
| Couverture | `.slide-header` sans bordure | `.slide-cover-img`, `.slide-cover-body`, `.slide-cover-logos` |
| Coupure de section | `.slide-header` sur fond `#161616` | `.slide-section-body`, `.slide-section-num`, `.slide-section-title`, `.slide-section-sub`, `.slide-section-band` |

Pièges les plus fréquents:

- `.slide-header` / `.slide-footer` dans un document EI: aucun style ne s'applique, la
  slide perd son cadre et son pied.
- `<strong>` dans un `.slide-h1` EI: c'est `<span>` qui porte l'orange.
- Logo de pied EI sans `<span class="logo-disc">`: seule la règle
  `.slide-foot-logo .logo-disc img { height:16px }` existe, l'image sort sinon à sa taille
  naturelle (41x37px) et déborde de l'anneau bleu.

---

## Structure obligatoire d'un fichier de présentation

```html
<!DOCTYPE html>
<html lang="fr" data-doc-type="presentation">
<head>…</head>
<body>
  <header class="shell-header">…</header>   <!-- barre supérieure noire IBM -->
  <div class="toolbar">…</div>              <!-- navigation + dropdown -->
  <div class="stage">                       <!-- zone centrale -->
    <button class="nav-arrow" id="nav-prev">…</button>
    <div class="slide-frame">
      <article class="slide active" id="slide-0" data-type="slide"
               data-id="slide-0" data-title="Titre slide">
        <div class="slide-header">…</div>
        <div class="slide-body">…</div>
        <div class="slide-footer">…</div>
      </article>
      <!-- slides suivantes id="slide-1", "slide-2"… -->
    </div>
    <button class="nav-arrow" id="nav-next">…</button>
  </div>
  <div class="status-bar">…</div>
  <script>
    const TOTAL = N;           /* ← mettre à jour à chaque ajout */
    const slideNames = […];    /* ← un nom par slide */
    …
  </script>
</body>
</html>
```

**Attributs obligatoires sur chaque `<article class="slide">`:**
- `id="slide-N"` (0-indexé, séquentiel)
- `data-type="slide"` (active l'édition contextuelle)
- `data-id="slide-N"` (identifiant stable pour la navigation)
- `data-title="Titre lisible"` (affiché dans le dropdown)

**À mettre à jour dans le JS à chaque ajout/suppression de slide:**
- `const TOTAL = N;`
- `const slideNames = ["Slide 1", "Slide 2", …];`

---

## Anatomie d'une slide, charte IBM Carbon

```html
<article class="slide" id="slide-N" data-type="slide" data-id="slide-N" data-title="…">

  <!-- En-tête: eyebrow + titre + sous-titre -->
  <div class="slide-header">
    <div class="slide-eyebrow" data-editable="text">Catégorie · Slide 0N / TT</div>
    <h1 class="slide-h1" data-editable="text">Titre <strong>en gras partiel</strong></h1>
    <p class="slide-subtitle" data-editable="text">Sous-titre ou description.</p>
  </div>

  <!-- Corps: contenu libre -->
  <div class="slide-body" data-editable="text">
    <!-- composants Carbon ici -->
  </div>

  <!-- Pied de page -->
  <div class="slide-footer">
    <span class="slide-footer-left" data-editable="text">Nom produit · Présentation</span>
    <span class="slide-footer-right">Slide N / TOTAL</span>
  </div>

</article>
```

**Règle:** La bordure bleue `border-bottom: 4px solid var(--ibm-blue-60)` sur `.slide-header`
est la signature visuelle IBM Carbon. Ne jamais la supprimer.

**Typographie `.slide-h1`:** `font-weight: 300` (light) + `<strong>` pour la partie bold.
Exemple: `IBM <strong>Bob</strong>`, `Capacités <strong>clés</strong>`.

---

## Anatomie d'une slide, charte Euro-Information

```html
<article class="slide" id="slide-N" data-type="slide" data-id="slide-N"
         data-slide-type="content" data-title="…">

  <!-- Zone blanche arrondie à l'intérieur du cadre bleu -->
  <div class="slide-inner">
    <div class="slide-eyebrow" data-editable="text">Catégorie · Slide 0N / TT</div>
    <h1 class="slide-h1" data-editable="text">Titre de la <span>slide</span></h1>
    <div class="slide-title-rule"></div>
    <div class="slide-body" data-editable="text">
      <!-- composants: cds-grid, cds-tile, cds-structured-list, cds-notification, agenda-list -->
    </div>
  </div>

  <!-- Pied: anneau de logo au coin bas-gauche, numéro de page, titre de réunion -->
  <div class="slide-foot">
    <div class="slide-foot-logo"><span class="logo-disc"><img src="data:image/png;base64,…" alt="EI"></span></div>
    <span class="slide-foot-page">N</span>
    <span class="slide-foot-title" data-editable="text">Meeting Title · Mois Année</span>
  </div>

</article>
```

**Signature visuelle EI, à ne jamais altérer:** le bleu `--ei-blue` est porté par la slide
elle-même et forme un cadre à coins extérieurs carrés; `.slide-inner` pose la zone blanche
à `inset:10px` avec un arrondi intérieur de 16px; l'anneau de logo reprend exactement
l'épaisseur du cadre (bordure 10px, diamètre 50px) pour se fondre dans le coin bas-gauche.
Ce CSS vit dans le bootstrap `slides-ei-empty.html`, généré depuis la référence par
`tools/gen_ei_bootstrap.py`: ne pas le réécrire dans une slide.

**Assets de la charte EI:** le bootstrap `ei` porte les images en base64 (couverture,
logos CM / CIC / EI, chevrons du pied) et recopie le data URI des chevrons sur
`<html data-asset-chevrons="data:image/png;base64,…">`. C'est ce qui permet à l'éditeur de
poser le logo de pied sur une slide insérée dans un fichier qui n'a encore qu'une
couverture. Ne jamais supprimer cet attribut, et le conserver si le fichier est reconstruit.

Slides `title` et `section` en EI: pas de `.slide-inner`, pas de `.slide-foot`. La
couverture utilise `.slide-cover-img` + `.slide-cover-body` + `.slide-cover-logos`, la
coupure de section un fond bleu plein avec `.slide-section-*`.

### Convention EI du compteur de slide

Deux emplacements, tous deux obligatoires sur les slides à pied de page:

1. **eyebrow**: `Catégorie · Slide 0N / TT` (deux chiffres, séparateur ` / `).
2. **`.slide-foot-page`**: le numéro seul, `N`, sans total ni zéro de tête.

C'est la seule convention que la renumérotation automatique sait maintenir: l'éditeur
remplace le motif `Slide \d+ / \d+` dans l'eyebrow et réécrit entièrement
`.slide-foot-page`. Un eyebrow sans compteur (`Sommaire` seul) est laissé tel quel, et un
numéro de page écrit ailleurs que dans `.slide-foot-page` devient faux dès la première
insertion. Le numéro de page suit l'index de slide: la couverture est la page 1, donc la
première slide à pied porte `2`.

L'index est 0-based dans les `id` (`slide-0`) et 1-based dans les compteurs affichés:
pour la slide d'index `i`, l'eyebrow porte `Slide (i+1) / TT` et `.slide-foot-page` porte
`i+1`. La slide `slide-4` d'un jeu de 9 affiche donc `Slide 05 / 09` et `5`.

---

## Types de slides insérables (data-slide-type)

Deux jeux de layouts selon le template actif (détecté automatiquement par le picker):

### Template IBM Carbon (`ibm-carbon.html`)
Structure: shell-header noir + toolbar + `.slide` avec `.slide-header`/`.slide-body`/`.slide-footer`.

### Template Euro-Information (`euro-information.html`)
Structure: canvas 16:9, couleurs EI (bleu #003A8D, orange #FBAE40), Segoe UI, logos embarqués.
- `title`: couverture image tech + logos CM/CIC/EI, sans cadre ni pied
- `agenda`: sommaire dans `.slide-inner`, cadre bleu 10px, arrondi intérieur 16px, pied avec anneau de logo
- `section`: séparateur plein bleu, `.slide-section-*`, sans cadre ni pied
- `content`: titre + tuiles, même cadre et même pied que `agenda`
- `diagram`: zone de schéma, même cadre et même pied que `agenda`

Les deux templates exposent les mêmes 5 `data-slide-type`:

| `data-slide-type` | Usage | Fréquence typique |
|-------------------|-------|-------------------|
| `title` | Couverture de la présentation | 1 (première slide) |
| `agenda` | Plan / sommaire | 1 |
| `section` | Coupure de section | plusieurs |
| `content` | Titre + texte + tuiles (la plus fréquente) | beaucoup |
| `diagram` | Zone de schéma d'architecture | selon besoin |

Layouts définis dans `src/mcp_htmleditor/static/slide-layouts.js` (`LAYOUT_SETS.carbon`
et `LAYOUT_SETS.ei`). À l'insertion, les assets EI (couverture, logos) sont récupérés
depuis le document actif pour rester cohérents.

**Pour le LLM:** quand tu génères une nouvelle slide, choisis le `data-slide-type`
adapté et respecte la structure du template du document. Une présentation cohérente
suit généralement: `title` → `agenda` → (`section` → `content`×N)×M → `content` de clôture.

### Cohérence garantie à l'insertion (browser)

Quand l'humain insère/supprime une slide via le browser, le système renumérote
automatiquement tout le document:
- `id` et `data-id` séquentiels: `slide-0`, `slide-1`, …
- `const TOTAL` et `const slideNames[]` dans le `<script>` de navigation
- Le compteur eyebrow « Slide 0N / TT » (les deux chartes)
- Le pied Carbon `.slide-footer-right` « Slide N / TT »
- Le pied EI `.slide-foot-page` « N »
- Les `<option>` du dropdown (régénérées par `buildOptions()`)

**Pour le LLM:** quand tu ajoutes une slide manuellement (écriture directe du
fichier), tu dois toi-même maintenir cette cohérence: mettre à jour `TOTAL`,
`slideNames[]`, les `data-id`, l'eyebrow et le footer. Voir la section « Comment
ajouter une slide » ci-dessous.

---

## Composants Carbon disponibles

**Disponibles aussi en Euro-Information** (mêmes noms de classes, styles EI):
`cds-grid` + `cols-2`/`cols-3`, `cds-tile` (+ `tile-eyebrow`, `tile-title`),
`cds-structured-list`, `cds-notification` (+ `notif-title`, `notif-body`), `agenda-list`.

**Carbon uniquement**, absents du CSS EI: `stat-grid`/`stat-card`, `tag-blue` et les autres
`tag-*`, `cds-code`, `cw-bar`/`cw-seg`, `mention-wrap`/`mention-pill`, la variante dense
`cds-structured-list.compact`, la classe de slide `dense`, les helpers `gantt-*` et
`arch-*`, ainsi que les variantes `success`/`warning`/`error` de `cds-notification`. Les utiliser dans un document
EI donne du texte non stylé: soit ajouter la règle CSS dans la slide, soit s'en passer.
L'exemple `example-ei-complete.html` définit `tag-blue`, `tag-orange` et `tag-gray` en
version EI, réutilisables tels quels.

### Grid (mise en page)
```html
<div class="cds-grid cols-2">  <!-- ou cols-3, cols-4 -->
  <div>colonne 1</div>
  <div>colonne 2</div>
</div>
```

### Tile (carte contenu)
```html
<div class="cds-tile">
  <div class="tile-eyebrow">Catégorie</div>
  <div class="tile-title">Titre de la carte</div>
  <p>Description en 2-3 lignes max.</p>
</div>
```
Usage: feature lists, comparaisons, overview de modules.

### Structured list (tableau)
```html
<table class="cds-structured-list">
  <thead>
    <tr><th>Col A</th><th>Col B</th><th>Col C</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Valeur</strong></td>
      <td>Description</td>
      <td><span class="tag-blue">Tag</span></td>
    </tr>
  </tbody>
</table>
```
Usage: comparaisons de modes/options, tableaux de fonctionnalités, matrices.

### Notification / callout
```html
<!-- Info (défaut) -->
<div class="cds-notification">
  <div>
    <div class="notif-title">Titre</div>
    <div class="notif-body">Corps du message.</div>
  </div>
</div>

<!-- Variantes: ajouter class="success", "warning", "error" -->
<div class="cds-notification success">…</div>
<div class="cds-notification warning">…</div>
<div class="cds-notification error">…</div>
```
Usage: définitions officielles, points clés, warnings, best practices.

### Hero stats
```html
<div class="stat-grid">  <!-- 3 colonnes par défaut -->
  <div class="stat-card">
    <div class="stat-value">270k</div>
    <div class="stat-label">tokens — fenêtre de contexte</div>
  </div>
</div>
```
Usage: slide d'introduction, chiffres clés, KPIs.

### Tags inline
```html
<span class="tag-blue">Développeur</span>
<span class="tag-green">Tous profils</span>
<span class="tag-purple">Fonctionnel</span>
<span class="tag-gray">Optionnel</span>
<span class="tag-red">Critique</span>
```
Usage: dans les tableaux pour catégoriser, dans les tiles pour badger.

### Inline code
```html
<code class="cds-code">nom_de_fonction</code>
<span class="cds-code">commande --option</span>
```

### Context window bar (visualisation proportionnelle)
```html
<div class="cw-bar">
  <div class="cw-seg" style="width:20%;background:#3b82d4;">Segment A</div>
  <div class="cw-seg" style="flex:1;background:#1d4ed8;">Segment B (reste)</div>
  <div class="cw-seg" style="width:10%;background:#e0e0e0;color:#525252;">Réservé</div>
</div>
```
Usage: répartition de budget, allocation mémoire, proportion de coûts.

### Mention pills
```html
<div class="mention-wrap">
  <div class="mention-pill"><code>@fichier.ts</code><span>— description</span></div>
  <div class="mention-pill"><code>@dossier/</code><span>— description</span></div>
</div>
```
Usage: lister des commandes, mentions, raccourcis clavier.

### Liste d'agenda
```html
<table class="agenda-list">
  <tbody>
    <tr><td class="num">01</td><td>Première section</td></tr>
    <tr><td class="num">02</td><td>Deuxième section</td></tr>
  </tbody>
</table>
```
Usage: sommaire. Le numéro est en bleu Carbon (en orange dans la charte EI).

### Helpers Gantt et schéma d'architecture

Les deux fichiers Carbon (bootstrap et référence) embarquent aussi le CSS des composants
décrits dans `skill/types/gantt.md` et `skill/types/arch-diagram.md`, donc pas besoin de le
recopier dans une slide:

| Classes | Rôle |
|---|---|
| `gantt-scale` + `gantt-label-col` + `q` | ligne d'échelle des périodes, alignée sur les pistes |
| `gantt-row` + `gantt-label` + `gantt-track` + `gantt-bar` | une tâche par ligne, barre positionnée en % **de la piste** |
| `arch-node` (+ `arch-node-label`, `<small>`) | boîte de nœud, centrée, titre plus légende |
| `arch-box`, `arch-circle`, `arch-diamond`, `arch-cylinder`, `arch-cloud` | formes; le même rendu s'applique via `[data-shape="…"]`, donc `data-shape` suffit |
| `arch-edge` + `arch-line-h` / `arch-line-v` | segments de connecteur; `data-style="dashed"` et `"dotted"` ont un rendu réel |
| `arch-tip-r` / `-l` / `-d` / `-u` | pointes de flèche |
| `arch-edge-label` | libellé de liaison |

Un conteneur `data-type="arch-diagram"` doit porter une `height` explicite (pas seulement
un `min-height`): les nœuds sont en `top: Y%` et un conteneur à hauteur automatique fait
s'effondrer les pourcentages verticaux.

---

## Design tokens IBM Carbon (variables CSS)

| Token | Valeur | Usage |
|---|---|---|
| `--ibm-blue-60` | `#0f62fe` | Couleur principale, accents |
| `--ibm-blue-70` | `#0043ce` | Hover, liens dark |
| `--ibm-blue-10` | `#edf5ff` | Background notifications info |
| `--ibm-gray-100` | `#161616` | Shell header, table headers |
| `--ibm-gray-10` | `#f4f4f4` | Tiles, toolbar, footer |
| `--ibm-gray-20` | `#e0e0e0` | Bordures, séparateurs |
| `--cds-text-primary` | `#161616` | Texte principal |
| `--cds-text-secondary` | `#525252` | Texte secondaire, descriptions |
| `--cds-support-success` | `#198038` | Vert success |
| `--cds-support-error` | `#da1e28` | Rouge error, annotations |

Utiliser **toujours les variables CSS** plutôt que les valeurs hex directement dans le contenu.
Exception: les valeurs dans `.cw-seg` style inline (contexte visuel spécifique).

## Design tokens Euro-Information (variables CSS)

| Token | Valeur | Usage |
|---|---|---|
| `--ei-blue` | `#003A8D` | Cadre de slide, titres, fond de section |
| `--ei-blue-2` | `#284AAA` | Eyebrow, bandeau de section, connecteurs |
| `--ei-blue-light` | `#285C99` | Titre de pied de page |
| `--ei-orange` | `#FBAE40` | Accent du titre (`<span>`), filet, numéros d'agenda |
| `--ei-coral` | `#EC6962` | Alerte douce, dernière phase d'un planning |
| `--ei-gray-dark` | `#50565B` | Texte secondaire, sous-titres |
| `--ei-text` | `#262626` | Texte principal |
| `--ei-bg-light` | `#f4f6f9` | Fond des tuiles |
| `--ei-font` | Segoe UI, Calibri | Police de tout le document |

Les tokens `--ibm-*` et `--cds-*` n'existent pas dans un document EI, et inversement.

---

## Typographie IBM Plex

```css
font-family: var(--cds-font-family-sans);  /* IBM Plex Sans (fallback: system-ui) */
font-family: var(--cds-font-family-mono);  /* IBM Plex Mono (fallback: Consolas) */
```

Échelle recommandée:
- Eyebrow: `font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em`
- Titre H1: `font-size: 36px; font-weight: 300` + `<strong>` pour la partie bold
- Sous-titre: `font-size: 16px; color: var(--cds-text-secondary)`
- Tile title: `font-size: 14px; font-weight: 600`
- Body tile: `font-size: 12.5px`
- Table header: `font-size: 12px; font-weight: 600; text-transform: uppercase`
- Table body: `font-size: 13px`

---

## Layouts de slide typiques

### Cover / Titre
```html
<div class="slide-header">…titre + subtitle…</div>
<div class="slide-body">
  <div class="stat-grid">…3 stat-cards…</div>
  <div class="cds-notification">…définition officielle…</div>
  <div class="cds-grid cols-3">…3 tiles…</div>
</div>
```

### Feature overview (6 features)
```html
<div class="slide-body">
  <div class="cds-grid cols-2">
    <div class="cds-tile">…</div>  <!-- × 6 -->
  </div>
</div>
```

### Tableau comparatif
```html
<div class="slide-body">
  <table class="cds-structured-list">…</table>
  <div class="cds-notification">…note de bas de slide…</div>
</div>
```

### Slide avec visualisation SVG annotée
```html
<div class="slide-body" style="padding: 12px 20px 8px; display:flex; flex-direction:column; gap:10px;">
  <div style="position:relative; width:100%; max-width:860px; margin:0 auto;">
    <svg viewBox="0 0 860 430" …>…reconstitution fidèle…</svg>
  </div>
  <!-- Légende en cards Carbon sous le SVG -->
  <div style="display:flex; gap:12px; flex-wrap:wrap;">
    <div style="background:#f4f4f4; border-left:4px solid #da1e28; padding:8px 12px; flex:1; min-width:200px;">
      <div style="font-size:11px; font-weight:700; color:#da1e28;">① Label</div>
      <div style="font-size:11.5px; color:#525252;">Description.</div>
    </div>
  </div>
</div>
```
Usage: screenshots annotés, schémas d'interface, walk-throughs.

---

## Animations et transitions

Les slides IBM Carbon utilisent une animation CSS `fadein` intégrée:
```css
@keyframes fadein {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.slide.active { animation: fadein 200ms ease; }
```
Ne pas modifier cette animation. Elle est appliquée automatiquement à chaque navigation.

Pour des effets visuels dans le contenu d'une slide (pas la transition entre slides),
utiliser des classes CSS inline ou des animations CSS locales à la slide.

---

## Règles de construction

1. **Toujours partir du bootstrap**: `mcp-htmleditor new carbon|ei`, jamais créer de zéro,
   et ne jamais recopier le CSS d'une charte dans un document de l'autre.
2. **Mettre à jour `TOTAL` et `slideNames`** dans le JS après chaque ajout/suppression.
3. **`id="slide-N"` est 0-indexé**: première slide = `id="slide-0"`.
4. **Ne jamais supprimer les `data-type`, `data-id`, `data-title`** sur les articles.
5. **La navigation est dans le shell** (toolbar + nav-arrows + status-bar): ne jamais en déplacer les éléments dans le contenu des slides.
6. **Les annotations rouges** (comme slide 9 ibm-carbon.html) utilisent `stroke="#da1e28"` et des flèches SVG polygones. Voir ibm-carbon.html slide-8 pour le pattern complet.
7. **Images externes**: utiliser base64 pour la portabilité. Si chemin relatif, documenter la dépendance dans un commentaire HTML.
8. **Responsive**: les slides ont `max-width: 900px` et `overflow-y: auto`. Le contenu ne doit jamais nécessiter de scroll horizontal.
9. **Tenir dans la hauteur utile** (voir la section suivante): une slide plus haute scrolle
   en silence et son pied de page est coupé sans avertissement.

---

## Hauteur utile d'une slide (contrainte silencieuse)

Le shell est fixe et consomme 120 px (`shell-header` 48, `toolbar` 48, `status-bar` 24), et
le `.slide-frame` ajoute 64 px de padding vertical. Une slide dispose donc de:

```
hauteur_utile = window.innerHeight − 184
```

Soit **576 px pour un viewport de 760 px**. Au-delà, `.slide` a `overflow-y: auto`: le
contenu scrolle sans aucun message et le `.slide-footer` sort du cadre. À l'export PPTX le
débordement est tronqué.

**Cible: 540 px de hauteur de contenu, 576 px maximum, viewport minimal 760 px.**

Piège de mesure: en Chrome headless, `--window-size=1200,760` ne donne que 673 px de
`innerHeight` (87 px consommés par le cadre de fenêtre), donc 489 px utiles seulement.
Pour capturer dans les conditions cibles, utiliser `--window-size=1200,850` ou plus.

Hauteurs mesurées sur une présentation dense de 9 slides validée par capture:

| Type de slide | Contenu | Hauteur mesurée |
|---|---|---|
| `title` | eyebrow + h1 + filet + 3 `stat-card` + 1 notification | 474 px |
| `agenda` | `cds-structured-list` de 5 entrées + notification | 475 px |
| `section` | fond `#161616`, h1 48 px, corps vide | 429 px |
| `diagram` (schéma) | conteneur `height:296px`, 7 nœuds, 6 connecteurs, notification | 561 px |
| `diagram` (gantt) | échelle + 8 tâches + notification | 538 px |
| `content` (table) | table 5 lignes en `compact` + notification | 533 px |
| `content` (riche) | notification + `cw-bar` + 6 `mention-pill` | 421 px |
| `content` (image) | image 660 px de large + 3 annotations | 547 px |
| `content` (clôture) | 3 `cds-tile` + table de décisions | 484 px |

Budget pratique par slide: un `.slide-header` complet coûte environ 150 px, un
`.slide-footer` 40 px, il reste donc environ 350 px de corps. Ordres de grandeur: une ligne
de `cds-structured-list` 40 px (28 px en `compact`), une rangée de `cds-tile` de 3 lignes
de texte 110 px, une notification 60 à 80 px, une ligne de Gantt 32 px.

Deux leviers quand une slide déborde, dans cet ordre:

1. `class="slide dense"` sur l'article: paddings resserrés (`slide-header` 22/18 px,
   `slide-body` 18 px) au lieu de 32 px, environ 50 px regagnés.
2. `class="cds-structured-list compact"` sur la table: 8 px de padding vertical au lieu de
   12 px, environ 4 px par ligne.

Si cela ne suffit pas, **couper du contenu**: une slide qui déborde de plus de 80 px doit
être scindée en deux slides, jamais réduite en taille de police.

Vérification: capturer la slide et regarder si le pied de page est visible.

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --screenshot=/tmp/slide.png --window-size=1200,760 --hide-scrollbars "file:///chemin.html"
```

Attention: la référence `templates/reference/slides/ibm-carbon.html` est un catalogue de
composants, ses slides denses mesurent 624 à 773 px et scrollent dans une fenêtre de
760 px. Copier ses composants, pas sa densité.

---

## Comment ajouter une slide

1. Copier un bloc `<article class="slide" …>…</article>` existant.
2. Changer `id="slide-N"`, `data-id="slide-N"`, `data-title="…"` (N = prochain index).
3. Mettre à jour `TOTAL` et ajouter le nom dans `slideNames` dans le `<script>`.
4. Ne pas toucher au `<select id="slide-select">`: il est vide dans le fichier et
   `buildOptions()` régénère toutes les `<option>` depuis `slideNames` au chargement.
   Écrire des `<option>` en dur crée des doublons dès le premier rechargement.
   `data-title` de l'article et l'entrée de `slideNames` doivent être identiques.
5. Mettre à jour le texte `slide-eyebrow` ("Slide 0N / TT") puis, selon la charte,
   `.slide-footer-right` (Carbon, "Slide N / TT") ou `.slide-foot-page` (EI, "N").
6. Renuméroter les slides suivantes: les compteurs de toutes les slides décalent.

---

## Conversion vers PPTX

Voir `skill/workflow-export.md` pour les règles complètes.

Points critiques pour la compatibilité PPTX:
- Garder `data-type="slide"` sur chaque slide: c'est le seul marqueur de découpage
  (le repli `article.slide` existe, mais l'attribut est la règle).
- Utiliser `style="left: X%; top: Y%; width: W%; height: H%"` sur les éléments
  positionnés (nœuds de schéma, barres de Gantt, annotations): les pourcentages
  sont relus dans le repère du conteneur.
- Les `.cds-tile`, `.stat-card` et `.mention-pill` deviennent des formes avec fond,
  bordure et filet d'accent; les `.cds-structured-list` des tables natives;
  les `.cds-notification` des panneaux teintés à barre latérale.
- Renseigner les couleurs par classe CSS ou style inline: l'export relit la
  feuille de style du document (règles à une seule classe) et les `style=""`.
- Les SVG inline ne sont pas convertis; utiliser une image `<img>` PNG (base64)
  à la place si la conversion PPTX est prévue.
- Les fonds de `<span>` (`tag-blue`, `tag-green`) ne survivent pas: seule la
  couleur du texte est reprise.
