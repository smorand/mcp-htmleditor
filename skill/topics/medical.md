Charte `medical` (`mcp-htmleditor new medical pres.html --serve`): congrès, staff, enseignement. Une slide = une preuve visuelle plus un commentaire structuré, pas un mur de puces. Le CSS vit dans `templates/bootstrap/slides-medical-empty.html`; les fichiers `reference/` en embarquent une copie exacte: après modification du `<style>` du bootstrap, `make sync-medical-css`, puis `make install`. Ne jamais éditer le `<style>` d'un fichier `reference/`.

**Jamais de mélange de chartes.** Pas de `cds-tile`, `slide-inner`, `tag-blue` ni classe `carbon` ou `ei` (texte non stylé, écran et export). Détection: `--med-teal` dans le CSS ou `data-doc-template="medical"`.

## Jetons

`--med-teal` #159984 (puces, filet) | `--med-teal-dark` #0F6F60 (`<span>` du titre) | `--med-orange` #EE5A02 (filet, numéros) | `--med-panel` #E9EDEE (bandeau, section) | `--med-panel-2` #F5F7F8 | `--med-hair` #D7DEE2 | `--med-ink` #252525 | `--med-body` #3A3A3A | `--med-muted` #5D5D5D (légendes, sources) | `--med-ref` #3D85C6 (citations) | `--med-red` #C81E3A (`.abn`) | `--med-navy` #0F2E4C (en-tête de tableau, `thanks`) | `--med-dark` #0B0E11, `--med-dark-panel` #14181D (surface sombre).
Polices web safe seulement: `--med-font` = Trebuchet MS (titres), `--med-font-body` = Arial. Jamais de police téléchargée.

## Classes

`.med-band` (bandeau gris 40px) | `.med-head` > `.slide-eyebrow`, `.slide-h1` (partie teal dans `<span>`), `.med-rule` > `<i></i><b></b>` | `.slide-subtitle` | `.slide-body` | `ul.med-list > li`, `ul.med-sub > li` | `.med-lead` | `.med-figure` > `img` + `figcaption.med-caption` | `.med-strip`, `.med-grid`, `.med-badge` | `.med-split`, `.med-comment` + `.med-comment-head` | `.med-compare`, `.med-chip` / `.med-chip.after`, `.med-delta` | `.med-cols`, `.med-col`, `.med-col-head` | `.med-callout` (`.warn`, `.key`) + `.callout-title`/`.callout-body` | `.med-key`, `.med-key-text`, `.med-key-sub` | `.med-stats`, `.med-stat`, `.med-stat-value`, `.med-stat-label` | `table.med-agenda`, `td.num`, `.agenda-sub` | `table.med-table`, `.abn` | `.med-case-chip`, `.med-timeline` > `.tl-step` | `.med-steps`, `.med-step`, `.step-num`, `.step-title` | `.med-takehome`, `.med-th-row` | `ol.med-refs` | `.med-foot` > `.med-sources` > `.med-source` (`.src-title`) | `.slide-foot-page` | `.med-cover`, `-event`, `-title`, `-sub`, `-foot`, `-date`, `.med-author`, `.med-logos` | `.med-section`, `-title`, `-sub`, `-figs` | `.med-thanks`, `-title`, `-sub`, `.med-contact`, `.med-ack`.

**Signature, jamais altérée:** bandeau gris 40px en haut, filet en deux segments sous le titre (teal 44px puis orange 34px, 5px de haut), bande de sources en bas à gauche, numéro de page seul à droite. Filet d'une couleur, centré, bandeau coloré, pied à trois colonnes: erreurs de charte.

## Slide

```html
<article class="slide" id="slide-4" data-type="slide" data-id="slide-4"
         data-slide-type="content" data-title="EBUS-TBNA: rendement">
  <div class="med-band"></div>
  <div class="med-head">
    <div class="slide-eyebrow" data-editable="text">Stadification · Slide 05 / 14</div>
    <h1 class="slide-h1" data-editable="text">EBUS-TBNA: ce que <span>rend</span> le geste</h1>
    <div class="med-rule"><i></i><b></b></div>
  </div>
  <div class="slide-body">
    <ul class="med-list" data-editable="text">
      <li><strong>Sensibilité 94 %</strong> sur adénopathie.<sup>2</sup></li>
    </ul>
  </div>
  <div class="med-foot">
    <div class="med-sources" data-editable="text">
      <p class="med-source"><span class="src-title">Titre</span> : Auteur A, et al. Chest. 2013;143:e211.</p>
    </div>
    <span class="slide-foot-page">5</span>
  </div>
</article>
```

Obligatoires: `id="slide-N"` (0-based), `data-type="slide"`, `data-id`, `data-title` (identique à `slideNames`), `data-slide-type`.
Compteurs, deux seuls emplacements: `.slide-eyebrow` motif `Catégorie · Slide 0N / TT`, et `.slide-foot-page` = `N` seul. Jamais un numéro ailleurs (titre, légende). Écriture directe du fichier: mettre à jour soi-même `const TOTAL`, `slideNames[]`, `id`/`data-id`, eyebrows et `.slide-foot-page` de toutes les slides suivantes; jamais d'`<option>` en dur dans `#slide-select`.

## Les 16 types (`data-slide-type`)

Le picker expose 16 layouts: `title` (couverture), `disclosure` (liens d'intérêt, position 2, affichée et lue à voix haute), `agenda`, `section` (panneau gris), `content`, `image` (sombre), `grid` (sombre, mosaïque A à D), `compare` (sombre, avant/après), `columns`, `case`, `steps`, `table`, `keymessage` (sans `.med-head`, 3 chiffres), `takehome` (exactement 3 `.med-th-row`), `references` (10 entrées max), `thanks` (bleu nuit). Ordre usuel: title, disclosure, agenda, (section puis contenus) × N, keymessage, takehome, references, thanks.

## Surfaces

Claire pour texte, tableau, plan, cas. Sombre, `class="slide dark"`, pour toute slide dont la preuve est une image médicale (TDM, EBUS, endoscopie, histologie). `section` sert de tampon entre claire et sombre. Sur surface sombre: ne jamais agrandir au delà de 100 % de la taille native; pas d'ombre ni de coins arrondis (filet 1px); ne jamais inverser les gris ni « améliorer » le contraste; jamais de texte posé sur le parenchyme (annotations en légende ou en commentaire); garder fenêtre d'acquisition et latéralité.

## Largeurs `w-*`, critique pour l'export

Rangées flex: `.med-strip`, `.med-split`, `.med-cols`, `.med-compare`, `.med-steps`, `.med-stats`, `.med-timeline`, `.med-section-figs`. **Chaque enfant direct d'une rangée porte une classe de largeur explicite**: `w-25`, `w-30`, `w-33`, `w-40`, `w-50`, `w-60`, `w-70` (volontairement sous la fraction arithmétique pour réserver le `gap`). Sans largeur, l'export PPTX empile la slide et tronque. `.med-grid` est un flex vertical de `.med-strip`, jamais un `display:grid`.

```html
<div class="med-split">
  <figure class="med-figure w-60"><img src="data:image/png;base64,…" alt="TDM">
    <figcaption class="med-caption">TDM, coupe axiale.</figcaption></figure>
  <div class="med-comment w-40"><div class="med-comment-head">À regarder</div>
    <ul class="med-list"><li>Spicules.</li></ul></div>
</div>
```

## Lisibilité

Planchers sur 960x540: `.slide-h1` 30px, couverture 42px, section 44px, puces 18px, sous-puces 15px, `.med-caption` 12px, `.med-source` 10px, page 12px. Maximum 4 puces par liste, 2 lignes par puce, environ 6 éléments par slide; une idée par slide, titre qui énonce le message; 3 teintes plus neutres; gras seulement (ni italique, ni souligné, ni capitales au delà de 3 mots, ni light); slides à peu près égales aux minutes de l'exposé; jamais de sens porté par la seule couleur (libellé texte, `.med-chip`, `.abn` avec H ou B).

## Hauteur (540px dur, rognage silencieux, PPTX tronqué)

`.med-band` 40 + `.med-head` 90 à 110 + `.med-foot` 34 à 60: corps utile 330 à 360px. Puce 25px, ligne de tableau 30px (24 en compact), callout 55 à 70px. Leviers dans l'ordre: `class="slide dense"`; `class="med-table compact"`; couper ou scinder la slide. Ne jamais réduire la taille de police. Vérifier par capture (pied et sources visibles).

## Export PPTX

Décor dessiné par l'exporteur (bandeau, filet fixe, sources, page). Fond et titres des slides `dark`, `section`, `thanks` à relire dans le PPTX avant diffusion. Pas de SVG (PNG); fond des `<span>` perdu (`.med-badge` sans pastille); images en base64, jamais d'URL distante.

## Construction

Partir du bootstrap, jamais de zéro. Copier les composants de la référence. Conserver `data-type`, `data-id`, `data-title`, renseigner `data-slide-type`. Toute image de tiers a sa ligne `.med-source` et toute image de patient passe l'anonymisation: `mcp-htmleditor skill --type medical-sources`.

Reference: templates/reference/slides/medical.html
