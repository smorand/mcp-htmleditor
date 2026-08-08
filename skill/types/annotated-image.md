# Types: Image annotée

## Structure HTML complète

```html
<div data-type="annotated-image"
     style="position:relative; display:inline-block; width:100%;">

  <!-- Image de base -->
  <img src="path/to/image.png"
       data-editable="resize,reposition"
       alt="Description de l'image"
       style="width:100%; display:block;" />

  <!-- Annotation (callout) -->
  <div data-type="annotation"
       data-x="25"
       data-y="40"
       data-style="callout"
       style="position:absolute; left:25%; top:40%;
              background:rgba(255,255,0,0.9); color:#333;
              padding:6px 12px; border-radius:4px;
              font-size:12px; font-weight:bold;
              box-shadow:0 2px 6px rgba(0,0,0,0.2);
              white-space:nowrap;">
    Processeur principal
  </div>

  <!-- Annotation avec flèche (arrow style) -->
  <div data-type="annotation"
       data-x="60"
       data-y="20"
       data-style="arrow"
       style="position:absolute; left:60%; top:20%;
              background:#333; color:white;
              padding:5px 10px; border-radius:3px;
              font-size:11px;">
    ◀ Port USB-C
  </div>

</div>
```

## Coordonnées

- `data-x` et `data-y` sont en **pourcentage (0-100)** relatifs à l'image
- `data-x=0` = bord gauche de l'image
- `data-y=0` = haut de l'image
- Correspondent directement à `left: X%` et `top: Y%` en CSS
- Le conteneur `data-type="annotated-image"` doit être `position:relative` et l'image en
  `width:100%; display:block`, sinon les pourcentages ne se résolvent pas sur l'image

---

## Placement: méthode de contrôle (obligatoire)

Une position estimée à l'œil tombe sur le contenu: barres, étiquettes de valeur, axes.
Deux méthodes, dans cet ordre de préférence.

### Méthode 1: réserver les zones vides dès la génération de l'image

C'est la seule méthode déterministe. Quand l'image est produite par le même travail
(matplotlib, capture d'écran cadrée, schéma exporté), lui réserver la place des
annotations:

- **Supprimer le titre interne de l'image**: il double le titre de slide et occupe la bande
  haute, qui est la meilleure zone d'annotation. Déplacer l'information dans
  `.slide-subtitle`.
- Augmenter la marge du côté visé (`fig.subplots_adjust`) ou allonger l'axe des valeurs de
  15 à 20 % au-delà de la valeur maximale, ce qui dégage une bande libre.
- Noter les zones libres obtenues en pourcentages, puis y poser les annotations.

### Méthode 2: vérifier par capture d'écran

Quand l'image est fournie telle quelle: poser les annotations, capturer, **relire la
capture**, corriger. Une annotation n'est valide qu'après relecture visuelle.

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --screenshot=/tmp/check.png --window-size=1200,760 --hide-scrollbars "file:///chemin/fichier.html"
```

Pour une slide précise, injecter `current = N; render();` avant la capture (la fonction du
template gère la classe `active`, l'étiquette de progression et l'état des flèches).

### Positions types, sur un graphique en barres

| Zone | `data-x` / `data-y` | Condition d'usage |
|---|---|---|
| Bande haute gauche | `8` / `3` | pas de titre interne dans l'image |
| Bande haute gauche, 2e ligne | `8` / `15` | espacement d'environ 12 points par ligne |
| Bande haute droite | `70` / `24` | la barre la plus haute est à gauche |
| Sous l'axe des abscisses | `8` / `92` | l'image a une marge basse |

Règles de sûreté:

- Deux annotations empilées: au moins 12 points d'écart en `data-y`, sinon les ombres se
  chevauchent.
- `white-space:nowrap` impose une largeur: une annotation longue posée à `data-x=70` sort
  de l'image. Au-delà de 40 caractères, raccourcir le texte plutôt que de le laisser
  déborder.
- Trois annotations au maximum par image: au-delà, passer à des pastilles numérotées
  (`data-style="circle"`) plus une légende sous l'image.
- Garder `data-x`/`data-y` strictement égaux aux `left`/`top` du style inline.

### Exemple vérifié par capture

```html
<div data-type="annotated-image" style="position:relative; display:block; width:100%; max-width:780px; margin:0 auto;">
  <img src="data:image/png;base64,…" data-editable="resize,reposition"
       alt="Temps de production par type de livrable" style="width:100%; display:block;">
  <div data-type="annotation" class="annot annot-coral" data-x="8" data-y="3" data-style="callout"
       style="left:8%; top:3%;">Dossier d'architecture : 9 h ramenées à 2 h 30</div>
  <div data-type="annotation" class="annot annot-blue" data-x="8" data-y="15" data-style="callout"
       style="left:8%; top:15%;">Gain le plus fort sur les livrables structurés</div>
  <div data-type="annotation" class="annot annot-orange" data-x="70" data-y="24" data-style="callout"
       style="left:70%; top:24%;">Comptes rendus : quasi immédiat</div>
</div>
```

```css
.annot {
  position:absolute; font-size:10.5px; font-weight:700; padding:4px 9px;
  border-radius:3px; white-space:nowrap; box-shadow:0 2px 6px rgba(0,0,0,.18);
}
.annot-blue   { background:#003A8D; color:#fff; }
.annot-orange { background:#FBAE40; color:#4a3000; }
.annot-coral  { background:#EC6962; color:#fff; }
```

Slide complète: `templates/reference/slides/example-ei-complete.html`, slide
« Gains mesurés sur le pilote » (les trois positions ci-dessus ont été obtenues après
suppression du titre interne du graphique, puis vérifiées par capture).

## Styles d'annotation

| `data-style` | Description | CSS type |
|--------------|-------------|----------|
| `callout` | Fond jaune semi-transparent | `background:rgba(255,255,0,0.9)` |
| `arrow` | Fond sombre avec flèche ASCII | `background:#333; color:white` |
| `circle` | Cercle numéroté | `border-radius:50%; width:24px; height:24px` |
| `text-only` | Texte simple sans fond | `background:transparent` |

## Règles sur les images

**Base64 (recommandé pour la portabilité):**
```python
import base64
with open("screenshot.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
src = f"data:image/png;base64,{b64}"
```
Utiliser quand: le fichier HTML doit être partageable ou exporté.

**Chemin relatif:**
```html
<img src="images/architecture.png" />
```
Utiliser quand: le fichier HTML reste dans son répertoire et les images aussi.
Le chemin est relatif à l'emplacement du fichier HTML (pas du CWD).

**URL externe:**
```html
<img src="https://example.com/image.png" />
```
Déconseillé (dépendance réseau, export PPTX ne supporte pas).

## Ajouter une annotation en HTML

Étapes:
1. Repérer une zone vide de l'image (méthode 1 ou 2 ci-dessus), pas « au feeling »
2. Choisir le style (`callout`, `arrow`, `circle`, `text-only`)
3. Ajouter le `<div data-type="annotation">` dans le conteneur `data-type="annotated-image"`
4. Capturer et relire: aucune annotation ne doit recouvrir une donnée ni sortir de l'image

```html
<div data-type="annotation"
     data-x="45" data-y="30"
     data-style="callout"
     style="position:absolute; left:45%; top:30%;
            background:rgba(255,255,0,0.9); padding:5px 10px; border-radius:3px; font-size:12px;">
  Mon annotation
</div>
```

## Conversion PPTX

Ce qui est **préservé**: l'image (base64 embarqué, chemin relatif résolu par
rapport au fichier HTML), les positions des annotations calculées **dans le
repère de l'image** et non de la slide, leurs textes, leur couleur de fond et de
texte (classe CSS ou style inline).
Ce qui est **perdu**: ombres, opacité, flèches dessinées en CSS autour de
l'annotation, images distantes (`http://`, signalées et ignorées).

Résultat: image cadrée dans son bloc + une pastille colorée par annotation.
Voir `skill/workflow-export.md` pour l'état exact de la conversion.
