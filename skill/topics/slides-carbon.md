Charte IBM Carbon, **jamais mélangeable** avec Euro-Information (`slides-ei`). Toujours partir du bootstrap: `mcp-htmleditor new carbon ma-pres.html`, jamais créer de zéro, et ne jamais recopier le CSS d'une charte dans un document de l'autre. Identifier la charte avant d'écrire du markup et n'utiliser que ses classes.

## Structure obligatoire d'un fichier

```html
<html lang="fr" data-doc-type="presentation">
<body>
  <header class="shell-header">…</header>   <!-- barre noire IBM -->
  <div class="toolbar">…</div>
  <div class="stage">
    <button class="nav-arrow" id="nav-prev">…</button>
    <div class="slide-frame">
      <article class="slide active" id="slide-0" data-type="slide"
               data-id="slide-0" data-title="Titre slide">
        <div class="slide-header">
          <div class="slide-eyebrow" data-editable="text">Catégorie · Slide 01 / 09</div>
          <h1 class="slide-h1" data-editable="text">Titre <strong>en gras partiel</strong></h1>
          <p class="slide-subtitle" data-editable="text">Sous-titre.</p>
        </div>
        <div class="slide-body" data-editable="text">…composants…</div>
        <div class="slide-footer">
          <span class="slide-footer-left" data-editable="text">Produit · Présentation</span>
          <span class="slide-footer-right">Slide 1 / 9</span>
        </div>
      </article>
    </div>
    <button class="nav-arrow" id="nav-next">…</button>
  </div>
  <div class="status-bar">…</div>
  <script>const TOTAL = N; const slideNames = ["Titre slide", …];</script>
</body>
```

Attributs obligatoires sur chaque `<article class="slide">`: `id="slide-N"` (0-indexé, séquentiel), `data-type="slide"`, `data-id="slide-N"`, `data-title="Titre lisible"`. À chaque ajout ou suppression, mettre à jour dans le JS `const TOTAL = N;` et `const slideNames = ["Slide 1", …];`.

**Règle:** la bordure `border-bottom: 4px solid var(--ibm-blue-60)` sur `.slide-header` est la signature visuelle IBM Carbon. Ne jamais la supprimer. `.slide-h1` est en `font-weight: 300` (light) avec `<strong>` pour la partie bold.

## Types de slides insérables (`data-slide-type`)

| Type | Usage |
|---|---|
| `title` | couverture (1, première) |
| `agenda` | plan, sommaire (1) |
| `section` | coupure de section, fond `#161616` |
| `content` | titre, texte, tuiles (la plus fréquente) |
| `diagram` | zone de schéma d'architecture |

Suite usuelle: `title`, `agenda`, (`section`, `content` x N) x M, `content` de clôture. Layouts: `LAYOUT_SETS.carbon` dans `src/mcp_htmleditor/static/slide-layouts.js`.

## Cohérence à l'insertion et renumérotation

Quand l'humain insère ou supprime une slide, le système renumérote: `id` et `data-id` séquentiels, `const TOTAL`, `const slideNames[]`, l'eyebrow `Slide 0N / TT`, `.slide-footer-right` (`Slide N / TT`) et les `<option>` du dropdown (régénérées par `buildOptions()`). En écriture directe du fichier, le LLM doit maintenir tout cela lui-même.

## Composants

```html
<div class="cds-grid cols-2"> <!-- ou cols-3, cols-4 -->
  <div class="cds-tile"><div class="tile-eyebrow">Catégorie</div>
    <div class="tile-title">Titre</div><p>2 à 3 lignes max.</p></div>
</div>
<table class="cds-structured-list"> <!-- thead + tbody; variante dense: cds-structured-list compact -->
  <thead><tr><th>Col A</th><th>Col B</th></tr></thead>
  <tbody><tr><td><strong>Valeur</strong></td><td><span class="tag-blue">Tag</span></td></tr></tbody>
</table>
<div class="cds-notification"> <!-- ajouter success, warning ou error -->
  <div><div class="notif-title">Titre</div><div class="notif-body">Corps.</div></div></div>
<div class="stat-grid"><div class="stat-card">
  <div class="stat-value">270k</div><div class="stat-label">tokens</div></div></div>
```

Autres classes: `tag-blue|green|purple|gray|red` (inline), `cds-code`, `cw-bar` + `cw-seg` (proportions, `style="width:20%;background:…"`), `mention-wrap` + `mention-pill`, `agenda-list` (`td.num` bleu). Gantt et schémas: `gantt-*` et `arch-*` (voir `mcp-htmleditor skill --type gantt` et `--type arch-diagram`); un `data-type="arch-diagram"` porte une `height` explicite, pas seulement un `min-height`.

## Tokens et typographie

Utiliser **toujours les variables CSS** plutôt que les valeurs hex. `--ibm-blue-60` `#0f62fe` (principal), `--ibm-blue-70` `#0043ce`, `--ibm-blue-10` `#edf5ff`, `--ibm-gray-100` `#161616`, `--ibm-gray-10` `#f4f4f4`, `--ibm-gray-20` `#e0e0e0`, `--cds-text-primary` `#161616`, `--cds-text-secondary` `#525252`, `--cds-support-success` `#198038`, `--cds-support-error` `#da1e28`. Police: `var(--cds-font-family-sans)` (IBM Plex Sans), `--cds-font-family-mono`. Échelle: eyebrow 12px 600 majuscules, h1 36px 300, sous-titre 16px, tile title 14px 600, corps de tuile 12.5px, en-tête de table 12px 600, corps de table 13px.

Animation `fadein` de `.slide.active`: ne pas la modifier.

## Règles de construction

1. **Toujours partir du bootstrap**: `mcp-htmleditor new carbon`.
2. **Mettre à jour `TOTAL` et `slideNames`** après chaque ajout ou suppression.
3. **`id="slide-N"` est 0-indexé**: première slide = `id="slide-0"`.
4. **Ne jamais supprimer les `data-type`, `data-id`, `data-title`** sur les articles.
5. **La navigation est dans le shell**: ne jamais en déplacer les éléments dans le contenu des slides.
6. Images externes: base64; si chemin relatif, documenter la dépendance dans un commentaire HTML.
7. **Canevas fixe 16:9 (960x540)**, `overflow:hidden`: le contenu ne doit jamais nécessiter de scroll.
8. Tenir dans la hauteur utile (ci-dessous).

## Hauteur utile (contrainte silencieuse)

Une slide dispose de 540 px nets. Au delà, `.slide` (`overflow:hidden`) **rogne sans message**, le pied peut sortir du cadre et l'export PPTX tronque aussi. Budget: `.slide-header` environ 150 px, `.slide-footer` 40 px, donc environ 350 px de corps. Repères: ligne de `cds-structured-list` 40 px (28 px en compact), rangée de `cds-tile` 110 px, notification 60 à 80 px, ligne de Gantt 32 px.

Deux leviers, dans cet ordre: (1) `class="slide dense"` sur l'article (environ 50 px gagnés); (2) `class="cds-structured-list compact"` (environ 4 px par ligne). Sinon couper: au delà de 80 px de débordement, scinder en deux slides, jamais réduire la police. Vérifier par capture que le pied est visible.

La référence `ibm-carbon.html` est un catalogue autonome dont les slides dépassent 540 px: copier ses composants en respectant le budget 540 px, jamais sa densité ni son modèle de hauteur variable.

## Pointeur

En présentation plein écran, L (ou le bouton Pointeur à côté de Présenter) remplace le curseur par un point rouge et un clic entoure le bloc visé; le pointeur démarre éteint et rien n'est écrit dans le fichier.

## Ajouter une slide

1. Copier un `<article class="slide" …>` existant; changer `id`, `data-id`, `data-title` (N = prochain index).
2. Mettre à jour `TOTAL` et `slideNames`; `data-title` et l'entrée de `slideNames` sont identiques.
3. Ne pas toucher au `<select id="slide-select">`: `buildOptions()` régénère les `<option>`; en écrire en dur crée des doublons.
4. Mettre à jour l'eyebrow (`Slide 0N / TT`) et `.slide-footer-right` (`Slide N / TT`), puis renuméroter les slides suivantes.

## Conversion PPTX

Voir `mcp-htmleditor skill --type export`. Garder `data-type="slide"` sur chaque slide. Positionner les éléments (nœuds, barres, annotations) avec `style="left: X%; top: Y%; width: W%; height: H%"`. Couleurs par classe CSS à une classe ou style inline. Les SVG inline ne sont pas convertis: utiliser un `<img>` PNG base64. Les fonds de `<span>` (`tag-*`) ne survivent pas, seule la couleur du texte reste.

Reference: templates/reference/slides/ibm-carbon.html
