# Skill — Types: Slides (IBM Carbon)

## Vue d'ensemble

Le format de présentation standard est **IBM Carbon**. Tous les templates slides
utilisent les design tokens Carbon et la navigation JavaScript intégrée.

Template de référence complet: `templates/reference/slides/ibm-carbon.html`
Template bootstrap (point de départ vide): `templates/bootstrap/slides-empty.html`

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

## Anatomie d'une slide

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

## Types de slides insérables (data-slide-type)

Deux jeux de layouts selon le template actif (détecté automatiquement par le picker):

### Template IBM Carbon (`ibm-carbon.html`)
Structure: shell-header noir + toolbar + `.slide` avec `.slide-header`/`.slide-body`/`.slide-footer`.

### Template Euro-Information (`euro-information.html`)
Structure: canvas 16:9, couleurs EI (bleu #003A8D, orange #FBAE40), Segoe UI, logos embarqués.
- `title`: couverture image tech + logos CM/CIC/EI
- `agenda`: sommaire, cadre bleu arrondi + logo rond au coin
- `section`: séparateur plein bleu
- `content`: titre + tuiles, cadre bleu arrondi 10px + logo rond au coin bas-gauche
- `diagram`: zone de schéma, même cadre EI

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
- Le compteur eyebrow « Slide 0N / TT »
- Le footer « Slide N / TT »
- Les `<option>` du dropdown (régénérées par `buildOptions()`)

**Pour le LLM:** quand tu ajoutes une slide manuellement (écriture directe du
fichier), tu dois toi-même maintenir cette cohérence: mettre à jour `TOTAL`,
`slideNames[]`, les `data-id`, l'eyebrow et le footer. Voir la section « Comment
ajouter une slide » ci-dessous.

---

## Composants Carbon disponibles

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

1. **Toujours partir du bootstrap**: copier `slides-empty.html`, jamais créer de zéro.
2. **Mettre à jour `TOTAL` et `slideNames`** dans le JS après chaque ajout/suppression.
3. **`id="slide-N"` est 0-indexé**: première slide = `id="slide-0"`.
4. **Ne jamais supprimer les `data-type`, `data-id`, `data-title`** sur les articles.
5. **La navigation est dans le shell** (toolbar + nav-arrows + status-bar): ne jamais en déplacer les éléments dans le contenu des slides.
6. **Les annotations rouges** (comme slide 9 ibm-carbon.html) utilisent `stroke="#da1e28"` et des flèches SVG polygones. Voir ibm-carbon.html slide-8 pour le pattern complet.
7. **Images externes**: utiliser base64 pour la portabilité. Si chemin relatif, documenter la dépendance dans un commentaire HTML.
8. **Responsive**: les slides ont `max-width: 900px` et `overflow-y: auto`. Le contenu ne doit jamais nécessiter de scroll horizontal.

---

## Comment ajouter une slide

1. Copier un bloc `<article class="slide" …>…</article>` existant.
2. Changer `id="slide-N"`, `data-id="slide-N"`, `data-title="…"` (N = prochain index).
3. Mettre à jour `TOTAL` et ajouter le nom dans `slideNames` dans le `<script>`.
4. Ajouter l'`<option>` correspondant dans le `<select id="slide-select">`.
5. Mettre à jour le texte `slide-eyebrow` ("Slide 0N / TT") et `slide-footer-right`.

---

## Conversion vers PPTX

Voir `skill/workflow-export.md` pour les règles complètes.

Points critiques pour la compatibilité PPTX:
- Utiliser `style="left: X%; top: Y%; width: W%; height: H%"` sur les éléments
  positionnés pour que l'exporteur PPTX puisse calculer les coordonnées.
- Les `.cds-tile` deviennent des `TextBox` python-pptx (fond gris, bordure fine).
- Les `.cds-structured-list` deviennent des tables python-pptx.
- Les `.stat-card` deviennent des `TextBox` avec bordure gauche bleue.
- Les SVG inline ne sont pas convertis; utiliser une image `<img>` à la place
  si la conversion PPTX est prévue.
- Les `data-constraints` informent le positionnement lors de la conversion.
