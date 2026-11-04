Charte Euro-Information, **jamais mélangeable** avec IBM Carbon (`slides-carbon`). Toujours partir du bootstrap: `mcp-htmleditor new ei ma-pres.html`, jamais créer de zéro, et ne jamais recopier le CSS d'une charte dans un document de l'autre. N'utiliser que les classes de cette charte (`--ei-blue` ou `.slide-cover-logos` la signalent).

### Table de correspondance des classes

| Rôle | IBM Carbon | Euro-Information |
|---|---|---|
| Cadre interne | aucun | `.slide-inner` (`inset:10px`, arrondi 16px sur fond bleu) |
| Zone de titre | `.slide-header` | pas de conteneur, enfants de `.slide-inner` |
| Titre | `.slide-h1` + `<strong>` | `.slide-h1` + `<span>` pour la partie orange |
| Filet | bordure de `.slide-header` | `.slide-title-rule` (3px orange, 64px) |
| Pied | `.slide-footer` (`-left`, `-right`) | `.slide-foot` + `.slide-foot-logo > .logo-disc > img`, `.slide-foot-page`, `.slide-foot-title` |
| Compteur | `Slide N / TT` | `.slide-foot-page` = `N` seul |
| Tokens | `--ibm-*`, `--cds-*` | `--ei-blue`, `--ei-blue-2`, `--ei-orange`, `--ei-coral`, `--ei-gray-dark` |
| Couverture | `.slide-header` sans bordure | `.slide-cover-img`, `.slide-cover-body`, `.slide-cover-logos` |
| Section | `.slide-header` sur `#161616` | `.slide-section-body`, `-num`, `-title`, `-sub`, `-band` |

Pièges: `.slide-header` ou `.slide-footer` en EI n'ont aucun style; l'orange du titre vient de `<span>`, pas de `<strong>`; un logo de pied sans `<span class="logo-disc">` déborde de l'anneau.

## Structure obligatoire d'un fichier

Même squelette que Carbon: `<html lang="fr" data-doc-type="presentation">`, `.shell-header`, `.toolbar`, `.stage` > `.slide-frame` > `<article class="slide">`, `nav-prev`, `nav-next`, `.status-bar`, puis `<script>` avec `const TOTAL = N;` et `const slideNames = […];`. Attributs obligatoires sur chaque `<article class="slide">`: `id="slide-N"` (0-indexé, séquentiel), `data-type="slide"`, `data-id="slide-N"`, `data-title="Titre lisible"` et `data-slide-type`. À chaque ajout ou suppression, mettre à jour `TOTAL` et `slideNames`.

## Anatomie d'une slide EI

```html
<article class="slide" id="slide-N" data-type="slide" data-id="slide-N"
         data-slide-type="content" data-title="…">
  <div class="slide-inner">
    <div class="slide-eyebrow" data-editable="text">Catégorie · Slide 0N / TT</div>
    <h1 class="slide-h1" data-editable="text">Titre de la <span>slide</span></h1>
    <div class="slide-title-rule"></div>
    <div class="slide-body" data-editable="text">
      <!-- cds-grid, cds-tile, cds-structured-list, cds-notification, agenda-list -->
    </div>
  </div>
  <div class="slide-foot">
    <div class="slide-foot-logo"><span class="logo-disc"><img src="data:image/png;base64,…" alt="EI"></span></div>
    <span class="slide-foot-page">N</span>
    <span class="slide-foot-title" data-editable="text">Meeting Title · Mois Année</span>
  </div>
</article>
```

**Signature visuelle EI, à ne jamais altérer:** `--ei-blue` est porté par la slide (cadre à coins extérieurs carrés), `.slide-inner` pose la zone blanche à `inset:10px` avec arrondi 16px, l'anneau de logo reprend l'épaisseur du cadre (bordure 10px, diamètre 50px). Ce CSS vit dans le bootstrap `slides-ei-empty.html` (généré par `tools/gen_ei_bootstrap.py`): ne pas le réécrire dans une slide.

**Assets:** le bootstrap porte les images en base64 et recopie le data URI des chevrons sur `<html data-asset-chevrons="data:image/png;base64,…">`, ce qui permet à l'éditeur de poser le logo de pied sur une slide insérée. Ne jamais supprimer cet attribut, et le conserver si le fichier est reconstruit.

Slides `title` et `section`: pas de `.slide-inner`, pas de `.slide-foot`. Couverture: `.slide-cover-img` + `.slide-cover-body` + `.slide-cover-logos`; section: fond bleu plein avec `.slide-section-body` et `.slide-section-*`.

### Convention du compteur

Deux emplacements, tous deux obligatoires sur les slides à pied de page: (1) l'eyebrow `Catégorie · Slide 0N / TT` (deux chiffres, séparateur ` / `); (2) `.slide-foot-page`, le numéro seul `N`, sans total ni zéro de tête. C'est la seule convention que la renumérotation maintient: elle remplace `Slide \d+ / \d+` dans l'eyebrow et réécrit `.slide-foot-page`. Un numéro écrit ailleurs devient faux à la première insertion. Index 0-based dans les `id`, 1-based dans les compteurs: `slide-4` d'un jeu de 9 affiche `Slide 05 / 09` et `5` (la couverture est la page 1).

## Types insérables (`data-slide-type`)

`title` (couverture image + logos CM/CIC/EI, sans cadre ni pied), `agenda` (sommaire dans `.slide-inner`, avec pied), `section` (séparateur plein bleu, sans cadre ni pied), `content` (titre + tuiles, la plus fréquente), `diagram` (zone de schéma, cadre et pied comme `agenda`). Suite usuelle: `title`, `agenda`, (`section`, `content` x N) x M, `content` de clôture.

À l'insertion ou suppression par l'humain, le système renumérote `id`/`data-id`, `TOTAL`, `slideNames[]`, l'eyebrow, `.slide-foot-page` et les `<option>` (`buildOptions()`). En écriture directe, le LLM le fait lui-même.

## Composants

Disponibles en EI (mêmes noms de classes): `cds-grid` + `cols-2`/`cols-3`, `cds-tile` (+ `tile-eyebrow`, `tile-title`), `cds-structured-list` (thead + tbody), `cds-notification` (+ `notif-title`, `notif-body`), `agenda-list` (`td.num` en orange).

Carbon uniquement, absents du CSS EI: `stat-grid`/`stat-card`, `tag-*`, `cds-code`, `cw-bar`, `mention-pill`, `cds-structured-list.compact`, `gantt-*`, `arch-*` et les variantes `success`/`warning`/`error` de `cds-notification`. Dans un document EI ils donnent du texte non stylé: ajouter la règle CSS dans la slide ou s'en passer.

## Tokens

`--ei-blue` `#003A8D` (cadre, titres, section), `--ei-blue-2` `#284AAA` (eyebrow, connecteurs), `--ei-orange` `#FBAE40` (accent, filet, numéros d'agenda), `--ei-coral` `#EC6962`, `--ei-gray-dark` `#50565B`, `--ei-text` `#262626`, `--ei-font` (Segoe UI, Calibri). Les tokens `--ibm-*` et `--cds-*` n'existent pas dans un document EI, et inversement.

## Règles de construction

1. **Toujours partir du bootstrap**: `mcp-htmleditor new ei`.
2. **Mettre à jour `TOTAL` et `slideNames`** après chaque ajout ou suppression.
3. **`id="slide-N"` est 0-indexé**.
4. **Ne jamais supprimer les `data-type`, `data-id`, `data-title`** sur les articles.
5. **La navigation est dans le shell**: ne jamais en déplacer les éléments dans le contenu des slides.
6. Images en base64.
7. **Canevas fixe 16:9 (960x540)**, `overflow:hidden`: jamais de scroll.

## Hauteur utile (contrainte silencieuse)

540 px nets. Au delà, le contenu est **rogné sans message**, le pied peut sortir du cadre, l'export PPTX tronque aussi. En-tête environ 150 px, pied 40 px, corps environ 350 px. Leviers, dans l'ordre: `class="slide dense"` sur l'article (la variante `compact` des tables est Carbon uniquement). Sinon couper: au delà de 80 px de débordement, scinder en deux slides, jamais réduire la police. Vérifier par capture que le pied est visible.

## Ajouter une slide

1. Copier un `<article>` existant; changer `id`, `data-id`, `data-title` (identique à l'entrée de `slideNames`).
2. Mettre à jour `TOTAL` et `slideNames`.
3. Ne pas toucher au `<select id="slide-select">`: `buildOptions()` régénère les `<option>`, en écrire en dur crée des doublons.
4. Mettre à jour l'eyebrow (`Slide 0N / TT`) et `.slide-foot-page` (`N`), puis renuméroter les suivantes.

## Conversion PPTX

Voir `mcp-htmleditor skill --type export`. Garder `data-type="slide"` sur chaque slide. Positionner nœuds, barres et annotations en `style="left: X%; top: Y%; width: W%; height: H%"`. SVG inline non convertis: `<img>` PNG base64. Les fonds de `<span>` ne survivent pas.

Reference: templates/reference/slides/example-ei-complete.html
