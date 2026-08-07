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
1. Estimer la position en % dans l'image
2. Choisir le style (`callout`, `arrow`, `circle`, `text-only`)
3. Ajouter le `<div data-type="annotation">` dans le conteneur `data-type="annotated-image"`

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

Ce qui est **préservé**: image (si chemin absolu ou fichier local), positions des annotations (% → pouces), textes.
Ce qui est **perdu**: styles CSS custom, images en base64 (V1), polices.

Résultat: image ajoutée sur le slide + textboxes positionnés pour chaque annotation.
