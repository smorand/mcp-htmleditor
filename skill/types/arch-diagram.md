# Types: Schéma d'architecture

## Structure HTML avec exemple

```html
<div data-type="arch-diagram"
     style="position:relative; width:100%; min-height:300px; padding:20px; font-family:Arial,sans-serif;">

  <!-- Nœud -->
  <div data-type="arch-node"
       data-label="API Gateway"
       data-shape="box"
       data-x="10" data-y="40"
       data-width="20" data-height="10"
       style="position:absolute; left:10%; top:40%; width:20%; box-sizing:border-box;
              border:2px solid #333; padding:12px; text-align:center;
              background:#f5f5f5; border-radius:4px; font-weight:bold;">
    API Gateway
  </div>

  <!-- Flèche (élément HTML simple) -->
  <div style="position:absolute; left:30%; top:44%; font-size:24px; color:#666;">→</div>

  <!-- Nœud destination -->
  <div data-type="arch-node"
       data-label="Service Auth"
       data-shape="box"
       data-x="35" data-y="40"
       data-width="20" data-height="10"
       style="position:absolute; left:35%; top:40%; width:20%; box-sizing:border-box;
              border:2px solid #4a90d9; padding:12px; text-align:center;
              background:#e8f0fe; border-radius:4px; font-weight:bold;">
    Service Auth
  </div>

</div>
```

## Shapes disponibles

| Valeur `data-shape` | Rendu CSS | Usage |
|---------------------|-----------|-------|
| `box` | Rectangle, `border-radius:0` | Service, composant |
| `circle` | `border-radius:50%` | Acteur, endpoint |
| `diamond` | `transform:rotate(45deg)` | Décision, condition |
| `cylinder` | Simulé avec `border-radius` top/bottom | Base de données |
| `cloud` | `border-radius:50px` + style | Cloud provider |

CSS pour chaque shape:
```css
/* box */
.arch-box { border-radius: 0; }
/* circle */
.arch-circle { border-radius: 50%; width: 80px; height: 80px; display:flex; align-items:center; justify-content:center; }
/* diamond */
.arch-diamond { transform: rotate(45deg); }
.arch-diamond .label { transform: rotate(-45deg); }
/* cylinder */
.arch-cylinder { border-radius: 8px / 20px; }
/* cloud */
.arch-cloud { border-radius: 50px; }
```

## Attributs d'un nœud

| Attribut | Description | Exemple |
|----------|-------------|---------|
| `data-type="arch-node"` | Identifie un nœud | — |
| `data-label` | Libellé affiché | `"API Gateway"` |
| `data-shape` | Forme visuelle | `box`, `circle`, `diamond`, `cylinder`, `cloud` |
| `data-x` | Position gauche en % (0-100) | `10` |
| `data-y` | Position haut en % (0-100) | `40` |
| `data-width` | Largeur en % | `20` |
| `data-height` | Hauteur en % | `10` |
| `data-color` | Couleur de fond | `#e8f0fe` |

## Edges (connexions entre nœuds)

En V1, les edges sont des éléments HTML positionnés manuellement (flèches ASCII ou SVG simple):

```html
<!-- Flèche horizontale -->
<div data-type="arch-edge" data-from="node-a" data-to="node-b" data-style="solid"
     style="position:absolute; left:30%; top:45%; font-size:20px;">→</div>

<!-- Flèche avec label -->
<div data-type="arch-edge" data-from="node-a" data-to="node-b" data-label="HTTP/REST"
     style="position:absolute; left:30%; top:45%; font-size:12px; color:#666;">
  ──── HTTP/REST ────▶
</div>
```

Styles d'edge disponibles:
- `solid`: `────▶`
- `dashed`: `- - - ▶`
- `dotted`: `· · · ▶`

## Conventions de nommage

- Utiliser les noms techniques réels: `"API Gateway"`, `"PostgreSQL"`, `"Redis Cache"`
- Pas d'abréviations ambiguës: `"Auth Service"` plutôt que `"AS"`
- Pour les bases de données: ajouter le type `"DB: PostgreSQL"` ou `"Cache: Redis"`

## Layouts suggérés

### Left-to-right (flux de gauche à droite)
```
[Client] → [Load Balancer] → [API] → [DB]
```
Positionner les nœuds avec `data-x` croissant, `data-y` constant.

### Top-to-bottom (hiérarchique)
```
        [Frontend]
            ↓
       [API Gateway]
       /           \
   [Service A]  [Service B]
       \           /
        [Database]
```
Positionner avec `data-y` croissant, `data-x` pour les branches.

## Conversion PPTX

Nodes → rectangles python-pptx avec le label en textbox.
Ce qui est **perdu**: shapes custom (circle, diamond), couleurs, edges.
Ce qui est **préservé**: positions (% → pouces), labels.
