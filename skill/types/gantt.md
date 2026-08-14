# Types: Gantt

## Règle de géométrie (la seule qui compte)

Un Gantt aligné exige **trois colonnes par ligne** et une **piste intermédiaire**:

```
[ libellé, largeur fixe ][ .gantt-track: position:relative; flex:1 ][ dates, largeur fixe ]
```

Les barres sont positionnées en `left` / `width` **à l'intérieur de `.gantt-track`**,
jamais en frères du libellé. Raison: un pourcentage se résout sur la largeur du parent.
Si la barre est fille de la ligne, `left:25%` se calcule sur la ligne entière (libellé et
colonne de dates comprises), alors que l'en-tête des mois commence après le libellé.
Sur une ligne de 860 px avec un libellé de 180 px, l'erreur atteint 180 px, soit plus de
deux mois de décalage: barres et en-tête ne peuvent alors jamais coïncider.

La piste est aussi le repère de l'en-tête: `.gantt-head` reprend exactement les mêmes
trois colonnes, avec les intitulés de période dans une piste de même largeur. Ainsi
`left`, `width`, séparateurs de trimestre et intitulés tombent sur les mêmes pixels.

**Interdit:** `padding-left:180px` sur l'en-tête plus `margin-left:%` sur les barres.
C'est l'ancienne recette, elle est fausse par construction.

Formule, valable seulement dans la piste (12 mois = 100 % de la piste):

```
left%  = (mois_debut - 1) / 12 * 100
width% = (mois_fin - mois_debut + 1) / 12 * 100
```

Exemple: mars à juillet → `left = 2/12*100 = 16.7%`, `width = 5/12*100 = 41.7%`.
Pour une échelle en trimestres, remplacer 12 par 4; pour des semaines, par le nombre
de semaines affichées. Le dénominateur doit être identique pour toutes les barres et
pour l'en-tête.

---

## CSS de référence

```css
.gantt-head { display:flex; align-items:flex-end; margin-bottom:6px; }
.gantt-head .gantt-label { font-size:10.5px; color:#50565B; }
.gantt-head .gantt-track { display:flex; }
.gantt-head .gantt-track > div {
  flex:1; text-align:center; font-size:10.5px; font-weight:700; color:#284AAA;
  text-transform:uppercase; letter-spacing:.06em; border-left:1px solid #e0e4ea; padding-bottom:3px;
}
.gantt-row { display:flex; align-items:center; height:26px; }
.gantt-row + .gantt-row { margin-top:4px; }
.gantt-label {
  width:158px; flex:0 0 158px; font-size:11.5px; color:#262626;
  padding-right:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.gantt-track {
  position:relative; flex:1 1 auto; height:100%;
  background:linear-gradient(to right, #eef1f6 0 1px, transparent 1px) repeat-x;
  background-size:25% 100%;                 /* un trait par trimestre */
  border-left:1px solid #e0e4ea; border-right:1px solid #e0e4ea;
}
.gantt-bar {
  position:absolute; top:3px; height:20px; border-radius:3px;
  color:#fff; font-size:10.5px; font-weight:600; line-height:20px;
  padding:0 8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  box-sizing:border-box;
}
.gantt-dates {
  flex:0 0 112px; width:112px; text-align:right; font-size:10.5px;
  color:#50565B; padding-left:10px; white-space:nowrap;
}
.gantt-legend { display:flex; gap:16px; margin-top:10px; flex-wrap:wrap; }
.gantt-legend span { font-size:11px; color:#50565B; display:inline-flex; align-items:center; gap:6px; }
.gantt-legend i { width:11px; height:11px; border-radius:2px; display:inline-block; }
```

Le `background-size:25% 100%` de la piste place un séparateur tous les 25 % de la piste,
donc exactement sur les frontières de trimestre. Avec une échelle mensuelle, utiliser
`background-size:8.3333% 100%`.

---

## Structure HTML complète (vérifiée au pixel)

```html
<div data-type="gantt" style="width:100%;">

  <!-- En-tête: mêmes 3 colonnes que les lignes -->
  <div class="gantt-head">
    <div class="gantt-label">Chantier</div>
    <div class="gantt-track" style="border:none; background:none;">
      <div>T1</div><div>T2</div><div>T3</div><div>T4</div>
    </div>
    <div class="gantt-dates">Période</div>
  </div>

  <!-- Une tâche: mars → juillet -->
  <div class="gantt-row">
    <div class="gantt-label">Éditeur WYSIWYG</div>
    <div class="gantt-track">
      <div data-type="gantt-task" class="gantt-bar"
           data-id="t3" data-label="Éditeur WYSIWYG"
           data-start="2026-03" data-end="2026-07"
           data-color="#285C99" data-group="Produit" data-depends-on="t2"
           style="left:16.7%; width:41.7%; background:#285C99;">Mar &#8594; Juil</div>
    </div>
    <div class="gantt-dates">Mar à Juil 2026</div>
  </div>

  <!-- Légende -->
  <div class="gantt-legend">
    <span><i style="background:#003A8D;"></i>Socle technique</span>
    <span><i style="background:#285C99;"></i>Produit et exports</span>
    <span><i style="background:#FBAE40;"></i>Adoption</span>
  </div>
</div>
```

Exemple complet à 8 tâches, 4 trimestres, légende et encadré de jalons:
`templates/reference/slides/example-ei-complete.html`, slide « Planning de livraison ».

---

## Attributs obligatoires sur gantt-task

| Attribut | Description | Exemple |
|----------|-------------|---------|
| `data-type="gantt-task"` | Identifie l'élément comme tâche | (pas de valeur) |
| `data-id` | Identifiant unique | `t3` |
| `data-label` | Libellé complet de la tâche | `"Éditeur WYSIWYG"` |
| `data-start` | Date de début, `YYYY-MM` | `2026-03` |
| `data-end` | Date de fin, `YYYY-MM` (mois inclus) | `2026-07` |

`data-label` porte **toujours le libellé complet**, même quand la barre affiche autre
chose: c'est cette valeur que lit l'export.

## Attributs optionnels

| Attribut | Description | Exemple |
|----------|-------------|---------|
| `data-color` | Couleur de fond, doit égaler le `background` inline | `#285C99` |
| `data-group` | Groupe ou lot parent | `"Produit"` |
| `data-depends-on` | `data-id` de la tâche prérequise | `t2` |

Les dépendances sont sémantiques: pas de flèche dessinée entre les barres.

---

## Lisibilité des barres et des colonnes

Contraintes mesurées sur une piste d'environ 590 px (ligne de 860 px, libellé 158 px,
dates 112 px), soit environ 49 px par mois:

1. **Une barre d'un ou deux mois fait 49 à 98 px: elle ne peut pas contenir un libellé.**
   Mettre le libellé complet dans la colonne de gauche et la période dans la barre
   (`Mar → Juil`). Un libellé tronqué en « Cadrage et spéci… » est un défaut, pas un
   compromis.
2. **Ne jamais répéter le libellé dans la barre**: redondance avec la colonne de gauche,
   et c'est ce qui provoque la troncature.
3. **Colonne de dates: 112 px minimum** pour un texte du type « Juin à Août 2026 ».
   À 90 px, l'année se coupe en « 202 ». Si la place manque, réduire la colonne de
   libellés (158 px tient des libellés de 22 à 25 caractères) plutôt que celle des dates.
4. **`white-space:nowrap` + `text-overflow:ellipsis`** sur libellé, barre et dates:
   la troncature devient visible au lieu de casser la hauteur de ligne.
5. **Hauteur de ligne fixe (26 px) et barre de 20 px**: un contenu qui passe sur deux
   lignes décale toutes les lignes suivantes par rapport à l'en-tête.
6. **Vérifier par capture**, en zoomant sur les frontières de trimestre: les séparateurs
   de la piste, les intitulés T1 à T4 et les extrémités de barre doivent coïncider.

---

## Ajouter, déplacer, supprimer une tâche

- **Ajouter**: dupliquer un `.gantt-row`, calculer `left` et `width` avec la formule,
  poser `data-start`, `data-end`, `data-label`, `data-id` unique, et la couleur aux deux
  endroits (`data-color` et `background`).
- **Déplacer**: modifier `data-start`, `data-end`, puis recalculer `left` et `width`.
  Les quatre valeurs doivent toujours rester cohérentes.
- **Supprimer**: retirer le `.gantt-row` entier, et nettoyer les `data-depends-on` qui
  pointaient sur son `data-id`.

---

## Conversion PPTX

Le Gantt devient un vrai Gantt: colonne de libellés, piste avec séparateurs de
trimestres, une barre arrondie par tâche à sa couleur (`data-color` ou fond
inline), colonne de dates et légende. La position vient du `left` (ou
`margin-left`) et du `width` en pourcentage de la piste; sans eux, elle est
calculée depuis `data-start` / `data-end` sur la période du graphique
(`data-period-start` / `data-period-end` du conteneur, sinon min et max des
tâches). `data-depends-on` reste sémantique, aucune flèche de dépendance n'est
dessinée. Voir `skill/workflow-export.md`.

---

## Variante: Gantt "inline" sans classes (détection structurelle)

Un deck reçu tel quel (pas rédigé avec les conventions ci-dessus) peut construire un
Gantt entièrement en `style="..."` inline, sans `data-type="gantt"` ni
`.gantt-row`/`.gantt-track`. L'export le détecte quand même **structurellement**,
sans exiger d'attribut ou de classe: c'est délibéré, pour rester correct sur un
fichier qu'on ne peut pas ou ne doit pas réécrire juste pour l'export.

Forme reconnue (voir `_is_inline_gantt`/`_is_inline_gantt_row` dans `to_pptx.py`):

```html
<div style="display:flex; align-items:stretch; min-height:26px;">
  <div style="flex:0 0 116px;">Libellé de la ligne</div>          <!-- largeur fixe -->
  <div style="flex:1; position:relative; min-height:26px;">      <!-- la piste -->
    <div style="position:absolute; left:33%; top:0; bottom:0;
                width:2px; background:#FBAE40;"></div>           <!-- repère vertical -->
    <div style="position:absolute; left:0%; width:30%;
                top:2px; height:10px; background:#003A8D;">Tâche</div>
  </div>
</div>
```

Au moins deux de ces lignes côte à côte (frères directs d'un même conteneur, sans
`data-type` ni descendant `.gantt-row`) suffisent à déclencher la détection. L'en-tête
(cellules de mois) et la légende ne sont **pas** des descendants du conteneur de
lignes: ce sont des frères, retrouvés par un flex-parent commun
(`_inline_gantt_sibling`) et **consommés avant** le parcours générique pour éviter
qu'ils ne soient rendus deux fois (une fois comme bloc générique, une fois par le
renderer Gantt).

Ce que l'export en tire, en plus du cas documenté ci-dessus:

- **Sous-lignes empilées**: chaque tâche garde son propre `top` (px) contre le
  `min-height` (px) de sa ligne, converti en bande verticale distincte au lieu de
  centrer toutes les barres sur l'axe médian de la ligne (`gantt_task_band` dans
  `pptx_components.py`).
- **Lignes verticales de repère** (jalon, "aujourd'hui"): un enfant positionné en
  absolu sans texte devient un trait fin coloré à son `left%`, via le même primitif
  `_rect` que les séparateurs de trimestre.
- **Hachures "terminé"**: un `background-image:repeating-linear-gradient(...)`
  devient un vrai remplissage à motif PPTX (`auto.fill.patterned()`,
  `MSO_PATTERN_TYPE.WIDE_UPWARD_DIAGONAL`), pas un texte de compromis; la légende
  applique le même traitement à son pastille si elle porte le même style.
- **Légende à deux natures d'entrées**: pastille de couleur (catégorie de ligne) et
  repère fin (jalon), distingués par leur forme (`_is_marker_legend_entry`); les
  deux se répartissent sur des lignes qui s'enroulent (wrap) plutôt que de forcer
  une seule ligne qui déborderait de la diapositive sur une légende à 15 entrées.
- **Libellé de barre trop long pour sa largeur**: réduit jusqu'à 5.5pt (le plancher
  du gabarit source), puis tronqué avec `…` plutôt que laissé déborder hors de la
  barre (`word_wrap=False` + `MSO_AUTO_SIZE.NONE`, sinon LibreOffice rend le
  débordement par-dessus les lignes voisines).

Aucune modification de code n'est nécessaire pour ce cas: aucun attribut `data-*` ni
classe n'a besoin d'être ajouté au fichier source, la détection est purement
structurelle. Test de référence: `tests/test_export_pptx.py::test_inline_gantt_*`.
