## Règle de géométrie (la seule qui compte)

Un Gantt aligné exige **trois colonnes par ligne** et une **piste intermédiaire**:

```
[ libellé, largeur fixe ][ .gantt-track: position:relative; flex:1 ][ dates, largeur fixe ]
```

Les barres sont positionnées en `left` / `width` **à l'intérieur de `.gantt-track`**, jamais en frères du libellé: un pourcentage se résout sur la largeur du parent, donc fille de la ligne, `left:25%` se calcule libellé et dates compris et décale les barres de l'en-tête (180 px d'erreur pour un libellé de 180 px). `.gantt-head` reprend les mêmes trois colonnes, avec les intitulés de période dans une piste de même largeur.

**Interdit:** `padding-left:180px` sur l'en-tête plus `margin-left:%` sur les barres. C'est l'ancienne recette, elle est fausse par construction.

Formule, valable seulement dans la piste (12 mois = 100 % de la piste):

```
left%  = (mois_debut - 1) / 12 * 100
width% = (mois_fin - mois_debut + 1) / 12 * 100
```

Mars à juillet: `left = 2/12*100 = 16.7%`, `width = 5/12*100 = 41.7%`. Trimestres: 4 au lieu de 12; semaines: le nombre de semaines affichées. Le dénominateur est identique pour toutes les barres et pour l'en-tête.

## CSS de référence

```css
.gantt-head { display:flex; align-items:flex-end; margin-bottom:6px; }
.gantt-head .gantt-label { font-size:10.5px; color:#50565B; }
.gantt-head .gantt-track { display:flex; }
.gantt-head .gantt-track > div {
  flex:1; text-align:center; font-size:10.5px; font-weight:700; color:#284AAA;
  text-transform:uppercase; border-left:1px solid #e0e4ea; padding-bottom:3px; }
.gantt-row { display:flex; align-items:center; height:26px; }
.gantt-row + .gantt-row { margin-top:4px; }
.gantt-label { width:158px; flex:0 0 158px; font-size:11.5px; padding-right:10px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.gantt-track { position:relative; flex:1 1 auto; height:100%;
  background:linear-gradient(to right, #eef1f6 0 1px, transparent 1px) repeat-x;
  background-size:25% 100%;  /* un trait par trimestre; mensuel: 8.3333% */
  border-left:1px solid #e0e4ea; border-right:1px solid #e0e4ea; }
.gantt-bar { position:absolute; top:3px; height:20px; border-radius:3px; color:#fff;
  font-size:10.5px; font-weight:600; line-height:20px; padding:0 8px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; box-sizing:border-box; }
.gantt-dates { flex:0 0 112px; width:112px; text-align:right; font-size:10.5px;
  padding-left:10px; white-space:nowrap; }
.gantt-legend { display:flex; gap:16px; margin-top:10px; flex-wrap:wrap; }
.gantt-legend span { font-size:11px; color:#50565B; display:inline-flex; align-items:center; gap:6px; }
.gantt-legend i { width:11px; height:11px; border-radius:2px; display:inline-block; }
```

## Structure HTML complète

```html
<div data-type="gantt" style="width:100%;">
  <div class="gantt-head">
    <div class="gantt-label">Chantier</div>
    <div class="gantt-track" style="border:none; background:none;">
      <div>T1</div><div>T2</div><div>T3</div><div>T4</div>
    </div>
    <div class="gantt-dates">Période</div>
  </div>
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
  <div class="gantt-legend">
    <span><i style="background:#003A8D;"></i>Socle technique</span>
    <span><i style="background:#FBAE40;"></i>Adoption</span>
  </div>
</div>
```

## Attributs de `gantt-task`

Obligatoires: `data-type="gantt-task"`, `data-id` (unique, `t3`), `data-label` (libellé complet, **toujours**, même si la barre affiche autre chose: c'est ce que lit l'export), `data-start` et `data-end` (`YYYY-MM`, mois de fin inclus).

Optionnels: `data-color` (égale le `background` inline), `data-group` (lot parent), `data-depends-on` (`data-id` de la tâche prérequise). Les dépendances sont sémantiques: aucune flèche n'est dessinée.

## Lisibilité (piste d'environ 590 px, soit 49 px par mois)

1. Une barre d'un ou deux mois (49 à 98 px) ne peut pas contenir un libellé: libellé complet dans la colonne de gauche, période dans la barre (`Mar → Juil`). Un libellé tronqué en « Cadrage et spéci… » est un défaut.
2. Ne jamais répéter le libellé dans la barre.
3. Colonne de dates: 112 px minimum (« Juin à Août 2026 »; à 90 px l'année se coupe en « 202 »). Si la place manque, réduire la colonne de libellés (158 px tient 22 à 25 caractères), pas celle des dates.
4. `white-space:nowrap` + `text-overflow:ellipsis` sur libellé, barre et dates.
5. Hauteur de ligne fixe (26 px) et barre de 20 px: une ligne qui passe sur deux lignes décale toutes les suivantes.
6. Vérifier par capture, en zoomant sur les frontières de trimestre: séparateurs, intitulés T1 à T4 et extrémités de barre coïncident.

## Ajouter, déplacer, supprimer une tâche

- Ajouter: dupliquer un `.gantt-row`, calculer `left` et `width`, poser `data-start`, `data-end`, `data-label`, un `data-id` unique, la couleur aux deux endroits (`data-color` et `background`).
- Déplacer: modifier `data-start`, `data-end`, puis recalculer `left` et `width`; les quatre restent cohérents.
- Supprimer: retirer le `.gantt-row` entier et nettoyer les `data-depends-on` qui pointaient sur son `data-id`.

## Conversion PPTX

Le Gantt devient un vrai Gantt: libellés, piste avec séparateurs de trimestres, une barre arrondie par tâche à sa couleur (`data-color` ou fond inline), dates, légende. La position vient de `left` (ou `margin-left`) et `width` en pourcentage de la piste; sans eux, elle est calculée depuis `data-start` / `data-end` sur la période du graphique (`data-period-start` / `data-period-end` du conteneur, sinon min et max des tâches). Aucune flèche de dépendance.

## Variante inline

Un Gantt écrit en `style` inline, sans `data-type="gantt"` ni `.gantt-row`, est détecté structurellement à l'export: au moins deux lignes sœurs `display:flex` (libellé à largeur fixe, piste `position:relative` avec barres `position:absolute` en `left`/`width` %). L'en-tête et la légende sont des frères du conteneur de lignes, pas des descendants. Aucun attribut `data-*` ni classe à ajouter au fichier source; pour un nouveau Gantt, suivre la structure ci-dessus. L'export en tire aussi:

- sous-lignes empilées: le `top` (px) de chaque tâche contre le `min-height` de sa ligne donne une bande verticale distincte;
- repères verticaux (jalon, « aujourd'hui »): enfant absolu sans texte, rendu en trait fin à son `left%`;
- hachures « terminé »: `repeating-linear-gradient` devient un remplissage à motif;
- libellé de barre trop long: réduit jusqu'à 5.5pt puis tronqué par `…`.

Export: `mcp-htmleditor skill --type export`.
