# Types: Slides médicales (charte `medical`)

## 1. Positionnement

Charte de présentation médicale: congrès, staff, enseignement, orientée pneumologie et
pneumologie interventionnelle (EBUS, cryobiopsie, endoscopie, pleuroscopie, stadification
du CBNPC, PID). Une slide y est presque toujours **une preuve visuelle plus un commentaire
structuré**, pas un mur de puces.

| Fichier | Rôle |
|---|---|
| `templates/bootstrap/slides-medical-empty.html` | bootstrap `medical` (`new medical`), 1 couverture, **source unique du CSS de la charte** |
| `templates/reference/slides/medical.html` | catalogue de composants: une slide par `data-slide-type`, à copier |
| `templates/reference/slides/example-medical-complete.html` | exemple riche de bout en bout (déroulé complet d'une intervention) |

Le CSS de la charte vit dans le bootstrap. Les deux fichiers `reference/` en embarquent
une copie **exacte** (fichiers autonomes); après modification du `<style>` du bootstrap,
lancer `make sync-medical-css`. Ne jamais éditer le `<style>` d'un fichier `reference/`.

**Jamais de mélange de chartes.** Un document est `medical`, ou `carbon`, ou `ei`, jamais
deux. La détection se fait sur `--med-teal` dans le CSS ou sur
`data-doc-template="medical"` sur `<html>` (côté navigateur: `detectTemplate()` de
`slide-layouts.js`; côté export: `detect_theme()` de `pptx_style.py`, qui accepte aussi la
présence d'un `.med-rule`). Copier une classe `cds-tile`, `slide-inner` ou `tag-blue` dans
une slide médicale donne du texte non stylé, à l'écran comme à l'export.

---

## 2. Jetons de la charte et table des classes

### Couleurs (variables CSS, `:root`)

| Jeton | Valeur | Usage |
|---|---|---|
| `--med-teal` | `#159984` | premier segment du filet, puces, bordure d'encadré clé, étapes |
| `--med-teal-dark` | `#0F6F60` | partie colorée du titre (`<span>`), en-têtes de colonne teal, valeurs de chiffres clés |
| `--med-orange` | `#EE5A02` | second segment du filet, numéros de plan, tirets de sous-puces |
| `--med-panel` | `#E9EDEE` | bandeau haut, fond de coupure de section, pastilles neutres |
| `--med-panel-2` | `#F5F7F8` | fond des encadrés de commentaire, cartes d'étape, lignes paires de tableau |
| `--med-hair` | `#D7DEE2` | filets fins, bordure d'image, séparateurs de tableau |
| `--med-ink` | `#252525` | encre des titres et du texte fort |
| `--med-body` | `#3A3A3A` | corps de texte, cellules de tableau |
| `--med-muted` | `#5D5D5D` | sur-titre, légendes, sous-titres, lignes de source |
| `--med-ref` | `#3D85C6` | citations: titre d'article, appels de note `<sup>`, numéros de bibliographie |
| `--med-red` | `#C81E3A` | valeur anormale (`.abn`), encadré d'alerte |
| `--med-navy` | `#0F2E4C` | en-tête de tableau, en-tête de colonne neutre, slide de remerciements |
| `--med-dark` | `#0B0E11` | surface sombre d'une slide d'imagerie |
| `--med-dark-panel` | `#14181D` | bandeau et panneaux sur surface sombre |
| `--med-dark-hair` | `#2A323B` | filet d'image sur surface sombre |
| `--med-dark-text` | `#E8EDF2` | texte sur surface sombre |
| `--med-dark-muted` | `#9AA7B4` | légendes et sources sur surface sombre |
| `--med-cyan` | `#4FC3D9` | accent de titre d'encadré et de citation sur surface sombre |
| `--med-amber` | `#F2A33C` | badge de repérage de vignette (A, B, C, D) |

Polices, **web safe uniquement** (aucune police n'est embarquée dans le PPTX):
`--med-font` = `'Trebuchet MS'` pour les titres et les grands nombres,
`--med-font-body` = `Arial` pour le corps. Ne jamais introduire une police téléchargée:
sur le poste du congrès elle sera substituée et la mise en page bougera.

### Rôle vers classe

| Rôle | Classe |
|---|---|
| Bandeau gris haut | `.med-band` (40px, plein cadre) |
| Bloc de titre | `.med-head` (sur-titre, titre, filet) |
| Sur-titre avec compteur | `.slide-eyebrow` |
| Titre | `.slide-h1`, partie teal dans un `<span>` |
| Sous-titre facultatif | `.slide-subtitle` |
| Filet deux segments | `.med-rule` > `<i></i><b></b>` |
| Corps | `.slide-body` |
| Puces, sous-puces | `ul.med-list > li`, `ul.med-sub > li` |
| Phrase d'attaque | `.med-lead` |
| Figure et légende | `.med-figure` > `img` + `figcaption.med-caption` |
| Bande de vignettes, mosaïque | `.med-strip`, `.med-grid`, badge `.med-badge` |
| Image plus commentaire | `.med-split`, `.med-comment` + `.med-comment-head` |
| Avant, après | `.med-compare`, `.med-chip` / `.med-chip.after`, `.med-delta` |
| Colonnes de texte | `.med-cols`, `.med-col`, `.med-col-head` (`.teal`, `.orange`) |
| Encadrés | `.med-callout` (`.warn`, `.key`) + `.callout-title` / `.callout-body` |
| Message clé | `.med-key` + `.med-key-text` / `.med-key-sub` |
| Chiffres clés | `.med-stats`, `.med-stat`, `.med-stat-value`, `.med-stat-label` |
| Plan | `table.med-agenda`, `td.num`, `.agenda-sub` |
| Tableau | `table.med-table` (`.compact`), `.abn` pour une valeur anormale |
| Cas clinique | `.med-case-chip`, `.med-timeline` > `.tl-step` |
| Étapes de geste | `.med-steps`, `.med-step`, `.step-num`, `.step-title` |
| Messages à retenir | `.med-takehome`, `.med-th-row` |
| Bibliographie | `ol.med-refs` (compteur CSS) |
| Bande de sources | `.med-foot` > `.med-sources` > `.med-source` (+ `.src-title`, `.src-ref`) |
| Numéro de page | `.slide-foot-page` |
| Couverture | `.med-cover`, `.med-cover-event`, `.med-cover-title`, `.med-cover-sub`, `.med-author`, `.med-cover-foot`, `.med-cover-date`, `.med-logos` |
| Coupure de section | `.med-section`, `.med-section-title`, `.med-section-sub`, `.med-section-figs` |
| Remerciements | `.med-thanks`, `.med-thanks-title`, `.med-thanks-sub`, `.med-contact`, `.med-ack` |
| Variante dense | `class="slide dense"` |
| Surface sombre | `class="slide dark"` |

**Signature visuelle, à ne jamais altérer:** le bandeau gris de 40px en haut, le filet en
deux segments sous le titre (teal 44px puis orange 34px, hauteur 5px, écart 4px), et la
bande de sources bibliographiques en bas à gauche avec le numéro de page seul à droite.
Un filet d'une seule couleur, un filet centré, un bandeau coloré ou un pied de page à
trois colonnes ne sont pas des variantes: ce sont des erreurs de charte.

---

## 3. Anatomie d'une slide

```html
<article class="slide" id="slide-4" data-type="slide" data-id="slide-4"
         data-slide-type="content" data-title="EBUS-TBNA: rendement diagnostique">

  <div class="med-band"></div>                        <!-- bandeau gris, 40px -->

  <div class="med-head">
    <div class="slide-eyebrow" data-editable="text">Stadification · Slide 05 / 14</div>
    <h1 class="slide-h1" data-editable="text">EBUS-TBNA: ce que <span>rend</span> le geste</h1>
    <div class="med-rule"><i></i><b></b></div>        <!-- teal puis orange, jamais un seul -->
  </div>

  <div class="slide-body">
    <ul class="med-list" data-editable="text">
      <li><strong>Sensibilité 94 %</strong> sur adénopathie de plus de 10 mm.<sup>2</sup></li>
      <li>Valeur prédictive négative insuffisante en cas de TDM discordante.</li>
    </ul>
  </div>

  <div class="med-foot">
    <div class="med-sources" data-editable="text">
      <p class="med-source"><span class="src-title">Titre de l'article</span> :
         Silvestri GA, Gonzalez AV, Jantz MA, et al. Chest. 2013;143(5 Suppl):e211-50.</p>
    </div>
    <span class="slide-foot-page">5</span>
  </div>

</article>
```

Attributs obligatoires sur chaque `<article>`: `id="slide-N"` (0-based, séquentiel),
`data-type="slide"`, `data-id="slide-N"`, `data-title` (identique à l'entrée de
`slideNames`), plus `data-slide-type` qui pilote le fond et le rendu à l'export.

### Compteurs et renumérotation

Deux emplacements, et deux seulement:

1. `.slide-eyebrow`, motif exact `Catégorie · Slide 0N / TT` (deux chiffres, séparateur
   ` / `);
2. `.slide-foot-page`, le numéro seul, `N`, sans total ni zéro de tête.

`renumberSlides()` (éditeur) réécrit le motif `Slide \d+ / \d+` dans l'eyebrow et
remplace entièrement `.slide-foot-page`. Un numéro écrit ailleurs (dans le titre, dans
une légende, dans un `.med-caption`) devient faux dès la première insertion humaine. Un
eyebrow sans compteur (les layouts `keymessage`, `section`, `thanks`, `title` n'en ont
pas) est laissé tel quel. Les gabarits d'insertion contiennent `{{N}}` / `{{TT}}`, résolus
par la passe de renumérotation, pas à l'insertion.

**Quand le LLM écrit le fichier directement**, la renumérotation ne tourne pas: il doit
mettre à jour lui même `const TOTAL`, `slideNames[]`, les `id`/`data-id`, les eyebrows et
les `.slide-foot-page` de **toutes** les slides suivantes. Ne jamais écrire d'`<option>`
en dur dans `#slide-select`: `buildOptions()` les régénère depuis `slideNames`.

---

## 4. Les 16 types de slide

Le picker « Insérer slide » expose 16 layouts pour cette charte (les chartes `carbon` et
`ei` n'en exposent que 5). Définitions: `LAYOUT_SETS.medical` dans
`src/mcp_htmleditor/static/slide-layouts.js`.

| `data-slide-type` | Usage | Fréquence | Surface |
|---|---|---|---|
| `title` | couverture: congrès, titre, orateur, établissement, date, logos | 1 | claire |
| `disclosure` | liens d'intérêt, tableau de 5 lignes, mention hors AMM | 1, en position 2 | claire |
| `agenda` | plan numéroté, 4 à 5 lignes | 1 | claire |
| `section` | séparateur gris pleine surface | 2 à 5 | panneau gris |
| `content` | puces plus bande de vignettes légendées | la plus fréquente | claire |
| `image` | une image et sa lecture commentée à droite | fréquent | **sombre** |
| `grid` | mosaïque de 4 images repérées A à D | selon besoin | **sombre** |
| `compare` | avant, après, même fenêtre et même zoom | 1 à 2 | **sombre** |
| `columns` | 2 ou 3 colonnes parallèles (taxonomie, diagnostics) | selon besoin | claire |
| `case` | cas clinique: anamnèse, expositions, chronologie relative | 1 à 3 | claire |
| `steps` | geste technique: alerte plus 3 étapes numérotées | 1 à 2 | claire |
| `table` | comparaison de techniques, résultats biologiques | 1 à 3 | claire |
| `keymessage` | une phrase affirmative plein cadre plus 3 chiffres | 1 à 2 | claire |
| `takehome` | exactement 3 phrases, reprises des slides clés | 1 | claire |
| `references` | bibliographie Vancouver, 10 entrées maximum par slide | 1 à 2 | claire |
| `thanks` | clôture bleu nuit: contact, remerciements d'équipe | 1 | bleu nuit |

Séquence usuelle d'un exposé:
`title` → `disclosure` → `agenda` → (`section` → `content` / `image` / `grid` /
`compare` / `columns` / `case` / `steps` / `table`) × N → `keymessage` → `takehome` →
`references` → `thanks`.

### Markup des types non évidents

`image` (surface sombre, image 60 % et commentaire 40 %):

```html
<div class="med-split">
  <figure class="med-figure w-60">
    <img src="data:image/png;base64,…" alt="TDM thoracique, coupe axiale">
    <figcaption class="med-caption">TDM, coupe axiale, fenêtre parenchyme. Nodule LSD.</figcaption>
  </figure>
  <div class="med-comment w-40">
    <div class="med-comment-head">Ce qu'il faut regarder</div>
    <ul class="med-list"><li>Spicules périphériques.</li><li>Conséquence pour le geste.</li></ul>
  </div>
</div>
```

`grid` (mosaïque: un `.med-grid` empile des `.med-strip`, jamais un `display:grid`):

```html
<div class="med-grid">
  <div class="med-strip">
    <figure class="med-figure w-50"><img src="…" alt="…">
      <figcaption class="med-caption"><span class="med-badge">A</span>TDM initiale.</figcaption></figure>
    <figure class="med-figure w-50"><img src="…" alt="…">
      <figcaption class="med-caption"><span class="med-badge">B</span>EBUS radial.</figcaption></figure>
  </div>
  <div class="med-strip">…C et D…</div>
</div>
```

`compare`, `case` (pastille d'identité en position absolue), `steps`:

```html
<div class="med-compare">
  <div class="w-50"><span class="med-chip">Avant · J0</span>
    <figure class="med-figure"><img src="…" alt="Avant">
      <figcaption class="med-caption">Même fenêtre, même zoom, même orientation.</figcaption></figure></div>
  <div class="w-50"><span class="med-chip after">Après · J+14</span>
    <figure class="med-figure"><img src="…" alt="Après">…</figure></div>
</div>
<div class="med-delta">Lumière trachéale 2 mm → 11 mm</div>

<span class="med-case-chip">CAS 1 · 58 ans, H, ex-fumeur 40 PA</span>
<div class="med-timeline">
  <div class="tl-step w-33"><b>J0</b>Découverte</div>
  <div class="tl-step w-33"><b>J+14</b>Prélèvement</div>
  <div class="tl-step w-33"><b>M+3</b>Réévaluation</div>
</div>
<p class="med-caption">Cas anonymisé, consentement écrit obtenu pour l'usage pédagogique.</p>

<div class="med-callout warn">
  <div><div class="callout-title">Risque à connaître</div>
       <div class="callout-body">Formulation de l'erreur à ne pas commettre.</div></div>
</div>
<div class="med-steps">
  <div class="med-step w-33"><span class="step-num">1</span>
    <div class="step-title">Repérage</div><p>Consigne opératoire.</p></div>
  <div class="med-step w-33">…</div><div class="med-step w-33">…</div>
</div>
```

`keymessage` (pas de `.med-head`: le message EST le titre), `takehome` (exactement 3
lignes, chacune renvoyant à sa référence), `references`:

```html
<div class="med-key">
  <div class="med-key-text">L'EBUS-TBNA restadifie le N2 avec une spécificité de 88 %.</div>
  <div class="med-key-sub">Sous réserve d'un opérateur entraîné et de 3 passages par site.</div>
  <div class="med-stats">
    <div class="med-stat w-33"><div class="med-stat-value">94 %</div>
      <div class="med-stat-label">Sensibilité</div></div>
    <div class="med-stat w-33">…</div><div class="med-stat w-33">…</div>
  </div>
</div>

<div class="med-takehome">
  <div class="med-th-row">Première phrase complète, affirmative.<sup>1</sup></div>
  <div class="med-th-row">Deuxième phrase.<sup>2,5</sup></div>
  <div class="med-th-row">Troisième phrase.<sup>4-7</sup></div>
</div>

<ol class="med-refs">
  <li>Herth FJF, Eberhardt R, Vilmann P, et al. Titre de l'article. <em>Thorax</em>.
      2021;76(3):210-8. doi:10.1136/thoraxjnl-2020-215123</li>
  <li>Figure 2 reproduite de : Wahidi MM, et al. Titre. <em>Chest</em>. 2020;157(4):985-93.</li>
</ol>
```

---

## 5. Surface claire et surface sombre

**Claire (`#FFFFFF`)** pour tout ce qui est texte, tableau, plan, message clé, messages à
retenir, bibliographie, cas clinique.

**Sombre (`class="slide dark"`)** pour toute slide dont la preuve principale est une image
médicale: TDM, radiographie, TEP-TDM, EBUS et EBUS radial, endoscopie bronchique en
lumière blanche ou en NBI, pleuroscopie, histologie, échographie. Raison: un pourtour
neutre sombre supprime la halation autour d'une image majoritairement noire et préserve
la perception des niveaux de gris; sur fond blanc, l'œil comprime les gris sombres et la
lésion se lit moins bien.

Les coupures de `section` (panneau gris) servent de tampon entre une séquence claire et
une séquence sombre: l'œil ne doit jamais passer directement du blanc au quasi noir.

Règles d'image sur surface sombre, non négociables:

- ne jamais agrandir au delà de 100 % de la taille native de l'image source;
- pas d'ombre portée, pas de coins arrondis, filet fin (1px) uniquement;
- ne jamais inverser les niveaux de gris ni « améliorer » le contraste après export;
- jamais de texte posé sur le parenchyme: les annotations vont dans la légende ou dans le
  panneau de commentaire;
- conserver la fenêtre d'acquisition (window / level) de la source et le repère de
  latéralité.

---

## 6. Largeurs de colonne (`w-*`), critique pour l'export

Sont des rangées flex: `.med-strip`, `.med-split`, `.med-cols`, `.med-compare`,
`.med-steps`, `.med-stats`, `.med-timeline`, `.med-section-figs`.

**Chaque enfant direct d'une rangée porte une classe de largeur explicite**, prise dans
`w-25` (22,5 %), `w-30` (29 %), `w-33` (31,3 %), `w-40` (37,5 %), `w-50` (48 %), `w-60`
(59 %), `w-70` (68 %). Les valeurs sont volontairement inférieures à la fraction
arithmétique: elles réservent l'écart (`gap`) de la rangée.

Raison, dite platement: l'exporteur PPTX ne reconnaît une rangée de colonnes côte à côte
que si **au moins un enfant déclare une largeur explicite** (`flex:0 0 X%`). Un `flex:1`
partout est indiscernable d'une pile verticale, et la slide s'exporte empilée, contenu
tronqué en bas. Une rangée sans largeurs est donc un bug d'export, pas un raccourci
d'écriture.

Même raison pour `.med-grid`: c'est un conteneur flex **vertical** de rangées
`.med-strip`, et non un `display:grid`. L'exporteur ne mesure pas les
`grid-template-columns`.

---

## 7. Citer ses sources

Deux mécanismes, jamais mélangés dans un même jeu de slides.

1. **Pied autoporteur**: la citation courte sous la slide, dans `.med-source`. Pour un
   exposé à peu de citations, ou une présentation qui circulera slide par slide.
2. **Appel de note en exposant** (`<sup>`) plus une slide `references`. Pour un exposé de
   congrès avec une vraie bibliographie.

Convention AMA / Vancouver pour les appels: chiffres arabes en exposant, **sans crochets**,
placés **après** la ponctuation, `2,5` pour plusieurs références, `4-7` pour une plage.
Les appels s'utilisent aussi dans les légendes de figure et dans les cellules de tableau.

### Formulations prêtes à l'emploi

Figure reproduite d'un article, avec le markup complet:

```html
<div class="med-sources">
  <p class="med-source"><span class="src-title">Titre de l'article</span> :
     Herth FJF, Eberhardt R, Vilmann P, et al. Thorax. 2021;76(3):210-8.
     Figure 2, reproduite avec autorisation.</p>
</div>
```

Les autres cas, à recopier tels quels dans un `<p class="med-source">`:

```
Figure modifiée par l'auteur :
  Adapté de : Wahidi MM, et al. Chest. 2020;157(4):985-93. Figure 1, adapté avec l'autorisation d'Elsevier.

Open access :
  … Respirology. 2022;27(9):744-52. Figure 3. CC BY 4.0.

Image de son propre service :
  Courtoisie de l'unité de pneumologie interventionnelle, <établissement>. Image anonymisée, consentement obtenu.

Image d'un confrère :
  Image aimablement fournie par le Dr <Nom>, service de radiologie, <établissement>. Reproduite avec autorisation.

Données personnelles non publiées :
  Données personnelles, unité de pneumologie interventionnelle, <établissement>, 2024-2026 (n = 214). Non publié.

Tableau de recommandation capturé :
  Source : recommandation ERS/ESTS, 2025. Tableau 4, reproduit avec l'autorisation de l'European Respiratory Society.

Recommandation paraphrasée (préférable à la capture) :
  D'après : NCCN Guidelines, Non-Small Cell Lung Cancer, v3.2026. Consulté le 12 mars 2026.

Image web ou atlas :
  Source : <auteur>. <titre de l'image>. <site>. Consulté le JJ mois AAAA. <URL>

Matériel d'un industriel :
  Source : monographie produit <société>, 2025. Utilisée avec autorisation. <Société> n'est pas
  intervenue dans le contenu de cette présentation.

Schéma généré par IA :
  Schéma généré avec <outil>, <version>, <date>; relu et corrigé par l'auteur.
```

Point juridique: écrire « adapté » ou « modifié » signale que la figure a été altérée, ce
qui exige l'autorisation du détenteur des droits. Redessiner intégralement à partir des
données publiées n'exige pas cette autorisation; ré-étiqueter ou recolorier la figure
d'origine ne suffit jamais à s'en dispenser.

### Slide de bibliographie

Style Vancouver / AMA, noms de revue abrégés NLM, DOI en fin d'entrée. Quand une même
publication fournit à la fois l'idée et la figure, la figure reçoit **sa propre entrée
numérotée**, formulée `Figure N reproduite de : …`.

### Règles à faire respecter

- Toute slide portant des pixels de tiers a une ligne `.med-source` non vide.
- Le style de la ligne de source est invariant sur tout le jeu: 10px, gris `--med-muted`,
  en bas à gauche, 2 lignes maximum.
- Citer n'est pas obtenir un droit. L'attribution ne vaut pas autorisation: tenir le
  statut de droits **par image** (propre / CC BY / autorisation obtenue / autorisation en
  attente) et ne pas diffuser un jeu de slides contenant une image en attente.

---

## 8. Anonymisation des images de patient

Liste de contrôle non négociable.

- **Jamais**: nom, initiales, numéro d'hospitalisation ou d'IPP, date calendaire de
  soins, date de naissance complète. L'ICMJE cite explicitement noms, initiales et
  numéros d'hôpital comme interdits.
- **À la place**: tranche d'âge, sexe, exposition pertinente (« 58 ans, H, ex-fumeur
  40 PA ») et chronologie relative (J0, J+14, M+3).
- **DICOM**: nettoyer l'en-tête **et** les annotations incrustées dans les pixels.
  En-tête: `PatientName`, `PatientID`, date de naissance, `AccessionNumber`,
  `StudyDate`, institution, médecin demandeur, tags privés. Pixels: texte de coin,
  bandeaux du PACS. Exporter un PNG ou JPEG aplati depuis une source anonymisée, jamais
  une capture d'écran de PACS.
- **Garder les incrustations cliniquement nécessaires**: latéralité D/G, barre d'échelle,
  modalité, fenêtre, orientation. Perdre la latéralité est une faute clinique, pas un
  gain de confidentialité.
- **Visages, tatouages, cicatrices, bijoux**: recadrer ou masquer. Masquer les yeux est
  explicitement jugé insuffisant par l'ICMJE: une photographie identifiable exige un
  consentement écrit.
- **Vidéo**: vérifier la première et la dernière image, plus l'incrustation de la colonne
  d'endoscopie.
- Toute séquence de cas clinique porte la mention de consentement dans la bande de
  légende.
- Maladie rare plus petit établissement plus date précise: le patient est
  ré-identifiable même sans son nom.

---

## 9. Lisibilité

Planchers de taille sur le canevas 960x540, jamais en dessous:

| Élément | Plancher |
|---|---|
| Titre de slide (`.slide-h1`) | 30px |
| Titre de couverture | 42px |
| Titre de section | 44px |
| Puces (`.med-list > li`) | 18px |
| Sous-puces (`.med-sub > li`) | 15px |
| Légendes (`.med-caption`) | 12px |
| Lignes de source (`.med-source`) | 10px |
| Numéro de page | 12px |

Discipline de contenu:

- 4 puces maximum par liste, 2 lignes maximum par puce, environ 6 éléments discrets
  maximum par slide;
- une idée par slide, et un titre qui **énonce le message** (« L'EBUS-TBNA restadifie le
  N2 avec une spécificité de 88 % ») plutôt qu'une étiquette de sujet (« Résultats »);
- 3 teintes maximum plus les neutres;
- pas d'italique ni de souligné pour insister (gras seulement), pas de capitales au delà
  d'une étiquette de 3 mots, pas de graisse light;
- nombre de slides à peu près égal au nombre de minutes de l'exposé;
- slide de liens d'intérêt en position 2, affichée et lue à voix haute;
- **jamais de sens porté par la seule couleur**: associer un libellé texte à la couleur
  (`.med-chip`, `.abn` avec un indicateur H ou B).

---

## 10. Budget de hauteur

Même canevas dur de 540px que les autres chartes: `.slide` est en `overflow:hidden`, le
contenu au delà est **rogné en silence**, et l'export PPTX le tronque également.

| Zone | Coût |
|---|---|
| `.med-band` | 40px |
| `.med-head` | 90 à 110px selon la longueur du titre |
| `.med-foot` | 34 à 60px selon le nombre de lignes de source (46px de base, 38px en `dense`) |
| **Corps disponible** | **environ 330 à 360px** |

Ordres de grandeur: une puce 25px, une ligne de `.med-table` 30px (24px en `compact`),
un `.med-callout` 55 à 70px, une figure 320x240 avec sa légende dans une bande de 3
vignettes environ 130px, une ligne de `.med-th-row` 55px, une ligne de `.med-refs` 26px.

Leviers, dans cet ordre:

1. `class="slide dense"` sur l'article (paddings resserrés en tête, corps et pied);
2. `class="med-table compact"` sur le tableau;
3. couper du contenu, et scinder la slide en deux.

**Ne jamais réduire la taille de police** (voir les planchers du § 9).

Vérification par capture:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --screenshot=/tmp/slide.png --window-size=1200,860 --hide-scrollbars "file:///chemin.html"
```

Pour cibler une slide précise, injecter `current = N; render();` avant la capture, puis
vérifier que la bande de sources et le numéro de page sont visibles.

---

## 11. Export PPTX de la charte

Le décor est dessiné par `_chrome_medical()` (`export/to_pptx.py`):

- fond selon le `data-slide-type`: blanc par défaut, `--med-dark` si la slide porte
  `dark`, panneau gris pour `section`, bleu nuit pour `thanks`;
- bandeau gris de 40px (variante `#14181D` sur surface sombre);
- pastille de cas clinique (`.med-case-chip`) en haut à droite;
- bloc de titre (`.med-head`) puis le filet deux segments, dessiné par
  `_render_med_rule()` avec une géométrie fixe (44px teal, 34px orange, 5px de haut): la
  charte l'exprime par des sélecteurs de balise (`.med-rule i`) que le résolveur par
  classe n'indexe pas, et c'est une signature de charte, pas une décision par slide;
- bande de sources en bas à gauche, dont la hauteur **grandit avec le nombre de
  citations** (`_render_medical_foot()`, plancher 34px), et numéro de page seul à droite;
- couverture (`_chrome_medical_cover()`): bloc de titre centré verticalement, date en bas
  à gauche, rangée de logos alignée à droite;
- `section` et `thanks` (`_chrome_medical_full()`): pleine surface, contenu centré, plus
  la ligne de remerciements (`.med-ack`) posée en bas.

`THEME_MEDICAL` porte la police (Trebuchet MS), les couleurs et l'en-tête de tableau
`--med-navy`. `_MEDICAL_STYLES` porte l'échelle typographique par classe, et
`_THEME_TAG_STYLES["medical"]` rattrape les tailles que la charte exprime par sélecteurs
descendants (`ul.med-list > li`, `.med-col p`, `.med-table td`), non indexables par
classe: elle fixe `li` à 17pt, `p` à 15pt, `td` à 14pt, `th` à 12pt. Sans ces valeurs, un
`<li>` sortirait au 12pt générique et le PPTX ne ressemblerait pas à la slide rendue.

Les variantes au niveau slide (`.slide.dark .x`) sont honorées: le constructeur publie
les classes de l'article dans `StyleResolver.active_scope`, et les règles à portée
(scoped rules) dont la portée est incluse dans cette portée active sont fusionnées par
dessus les règles sans portée. C'est ce qui fait sortir une slide sombre avec ses
panneaux sombres (`.slide.dark .med-band`, `.slide.dark .med-comment`) et ses titres
clairs (`.slide.dark .slide-h1`).

### Défauts d'export mesurés au 2026-08-21 (à connaître, non corrigés)

Export de `templates/reference/slides/medical.html` vérifié slide par slide:

- **le fond de slide sort toujours blanc**, y compris pour `dark` (attendu `#0B0E11`),
  `section` (attendu `#E9EDEE`) et `thanks` (attendu `#0F2E4C`). La règle
  `.slide { background:#fff }` est indexable par classe et l'emporte sur le fond par
  défaut du décor, alors que les variantes qui devraient la surcharger ne sont pas
  indexables (`.slide.dark` a une cible à deux classes,
  `.slide[data-slide-type="section"]` est un sélecteur d'attribut). Conséquence: sur une
  slide `thanks` le texte blanc devient invisible, et sur une slide `dark` les légendes
  claires sont illisibles;
- **les puces d'une slide sombre sortent en `#3A3A3A`** (`.slide.dark .med-list > li`
  utilise un combinateur enfant, non indexé), donc gris foncé sur panneau sombre;
- le filet de la slide `thanks` sort en teal `#159984` au lieu du teal clair `#7FD8C8`
  de la charte (géométrie et couleurs fixes dans `_render_med_rule`).

En pratique: **relire le PPTX** avant diffusion, et corriger les fonds à la main dans
PowerPoint pour les slides `dark`, `section` et `thanks` tant que ces points ne sont pas
traités côté code. Un jeu de slides destiné à être présenté en HTML (mode plein écran,
touche F) n'est pas concerné.

Autres limites connues:

- pas de SVG (aucune conversion vectorielle): utiliser un PNG;
- les fonds de `<span>` ne survivent pas, seule la couleur du texte est reprise, donc le
  badge `.med-badge` (A, B, C, D) perd sa pastille ambre;
- images en base64 ou en chemin relatif au fichier HTML; les URL distantes sont signalées
  et ignorées;
- le débordement au delà de 540px est tronqué, comme dans le navigateur.

---

## 12. Règles de construction

1. Partir du bootstrap: `mcp-htmleditor new medical pres.html --serve`. Ne jamais écrire
   un jeu de slides médical de zéro.
2. Copier les composants depuis `templates/reference/slides/medical.html`, jamais depuis
   un fichier `carbon` ou `ei`, et ne jamais introduire une classe d'une autre charte.
3. Mettre à jour `TOTAL`, `slideNames[]`, les `id`/`data-id`, les eyebrows et les
   `.slide-foot-page` à chaque ajout ou suppression.
4. Conserver `data-type="slide"`, `data-id`, `data-title`, et renseigner
   `data-slide-type`.
5. Toute rangée flex porte des largeurs `w-*` explicites sur chacun de ses enfants (§ 6).
6. Images en base64, jamais d'URL distante.
7. Toute image de tiers reçoit sa ligne `.med-source` (§ 7); toute image de patient passe
   la liste de contrôle d'anonymisation (§ 8).
8. Vérifier chaque slide par capture d'écran: pied de page visible, aucune troncature,
   planchers de taille respectés (§ 9 et § 10).
9. Séquence de l'exposé: `title` → `disclosure` → `agenda` → (`section` →
   `content` / `image` / `grid` / `compare` / `columns` / `case` / `steps` / `table`) × N
   → `keymessage` → `takehome` → `references` → `thanks`.
10. Après modification du `<style>` du bootstrap: `make sync-medical-css`, puis
    `make install` (ou `HTMLEDITOR_TEMPLATES_DIR=$PWD/templates`) pour que la copie
    installée ne prenne pas le dessus.
