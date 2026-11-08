## Format déclaratif (recommandé, à partir de 4 nœuds)

**Ne jamais calculer de position à la main** dès qu'un diagramme a un flux à plusieurs rangées ou plus de 3 nœuds. Le LLM déclare des rangées, des nœuds et des relations, jamais de `%`; un moteur de layout déterministe calcule le reste.

```html
<div data-type="arch-diagram" data-diagram-id="mcp-arch" style="position:relative; width:100%; height:320px;">
  <div data-type="arch-lane" data-lane-id="edge" data-label="Edge" data-rows="0-1"></div>
  <div data-type="arch-row" data-row="0">
    <div data-type="arch-node" data-id="agent" data-label="Agent LLM" data-shape="box"
         style="border:2px solid #003A8D; background:#003A8D; color:#fff; border-radius:4px;"></div>
    <div data-type="arch-node" data-id="mcp" data-label="Serveur MCP" data-shape="box"
         style="border:2px solid #003A8D; background:#e6ecf7; color:#003A8D;"></div>
  </div>
  <div data-type="arch-row" data-row="1">
    <div data-type="arch-node" data-id="file" data-label="Fichier HTML" data-span="2"></div>
  </div>
  <div data-type="arch-edge" data-from="agent" data-to="mcp" data-label="MCP stdio"></div>
  <div data-type="arch-edge" data-from="agent" data-to="file" data-label="écriture directe"></div>
</div>
```

Puis calculer et écrire les positions, avant la validation visuelle:

```bash
mcp-htmleditor arch-layout mon-fichier.html
```

ou l'outil MCP `layout_arch_diagram(file, diagram_id=None)` (même fonction Python). Après tout calcul de layout, lancer la revue qualité: `mcp-htmleditor skill --type arch-qa`.

### Règles

- **`arch-row`**: groupe les nœuds d'une rangée horizontale. `data-row` = index 0-based, ordre du fichier sans importance. Poids optionnel `data-height-weight` (défaut 1).
- **`arch-node`** dans une rangée: `data-id` obligatoire et unique dans le diagramme (utilisé par les arêtes), `data-label`, `data-shape`, et un `style` pour la seule décoration (couleur, bordure). **Jamais** `data-x`, `data-y`, `left`, `top`, `width`, `height`: sortie du moteur, écrasée au prochain calcul. `data-span` (défaut 1) élargit un nœud sur plusieurs colonnes, façon `colspan`.
- **`arch-edge`**: `data-from`, `data-to` (deux `data-id`), `data-label` optionnel, `data-style` optionnel (`solid`/`dashed`/`dotted`). La pointe de flèche est toujours sur le nœud cible (`data-to`).
- **`arch-lane`** (optionnel): `data-lane-id`, `data-label`, `data-rows="debut-fin"` (ex. `"0-1"` ou `"2"`). Sa boîte est l'union des nœuds des rangées couvertes plus un padding.
- **`arch-row` et `arch-lane` restent en permanence dans le DOM**, jamais aplatis ni supprimés après calcul: ajouter un nœud puis relancer `arch-layout` suffit.
- **Invariant CSS dur**: `arch-row`/`arch-lane` ne doivent **jamais** recevoir `position:relative`. Les `%` calculés sur les `arch-node`/`arch-edge` se résolvent contre le conteneur `arch-diagram` de premier niveau, comme l'export PPTX les relit; un wrapper `position:relative` romprait cette parité en silence.
- **`data-layout="manual"`**: posé automatiquement par un glisser-déposer humain, il verrouille la position du nœud lors d'un recalcul; ses arêtes partent de sa position réelle.

### Primitives avancées

- **`arch-col`**: enfant direct d'`arch-row` à la place d'un `arch-node`. Il occupe un slot (même `data-span`) et répartit sa hauteur entre ses `arch-node` empilés (`data-height-weight` par enfant).
  ```html
  <div data-type="arch-row" data-row="0">
    <div data-type="arch-node" data-id="vault" data-label="Coffre-fort"></div>
    <div data-type="arch-col">
      <div data-type="arch-node" data-id="obs" data-label="Observabilité"></div>
      <div data-type="arch-node" data-id="eval" data-label="Evaluation"></div>
    </div>
  </div>
  ```
- **`arch-spacer`**: slot de rangée invisible, sans nœud, pour aligner un nœud sous une colonne précise d'une rangée plus large (`<div data-type="arch-spacer"></div>`).
- **`data-step`** sur `arch-edge`: badge numéroté (cercle coloré) au milieu du segment; couleur via `data-color`. Exemple: `<div data-type="arch-edge" data-from="a" data-to="b" data-step="5" data-color="#2CA02C"></div>`. Le badge est exporté en PPTX (cercle numéroté).

### Mouse edit et limites

- En mode édition: clic droit sur le fond (ajouter un nœud) ou sur un nœud (renommer, changer forme, créer une arête, supprimer). Le navigateur écrit le même markup déclaratif et demande `POST /arch-layout`.
- Une arête qui saute plus d'une rangée est routée mais sans vérification de traversée: le moteur émet un avertissement. Au-delà de 2 rangées d'écart, découper le diagramme.
- Pas de minimisation de croisements: trop de nœuds pour une slide (budget 540 px).

## Format legacy (2-3 nœuds, sans `arch-row`)

Le calcul manuel reste valide; les deux formats coexistent dans un fichier et `arch-layout` laisse le legacy intact. Un nœud porte sa position en attributs lisibles, en pourcentages (0-100, 1 décimale) du conteneur:

- `data-x`, `data-y` (gauche, haut), plus `data-width`/`data-height` (sans taille explicite aucun connecteur ne s'ancre);
- un style inline `position:absolute; left:X%; top:Y%; width:W%; height:H%` identique aux attributs;
- le conteneur `data-type="arch-diagram"` est `position:relative` et a une `height` explicite (pas seulement `min-height`). Pas de transform, pas de pixels.

```html
<div data-type="arch-node" class="arch-node" data-label="Serveur MCP" data-shape="box"
     data-x="27.0" data-y="2.0" data-width="21.0" data-height="15.0"
     style="position:absolute; left:27.0%; top:2.0%; width:21.0%; height:15.0%;
            border:2px solid #003A8D; background:#e6ecf7; color:#003A8D;">Serveur MCP</div>
```

`data-shape`: `box`, `circle`, `diamond`, `cylinder`, `cloud` (rendu déjà dans les fichiers Carbon; absent d'un document Euro-Information, à déclarer). `data-color` pour le fond. `circle` à dimensions inégales en pixels donne une ellipse; `diamond`: texte dans un `<span>` enfant. Forme non rectangulaire: ancrer sur le milieu des bords de la boîte, accepter le petit espace. Noms techniques réels, pas d'abréviations ambiguës.

### Connecteurs: méthode d'ancrage (obligatoire)

Pas de glyphes `→`, pas de SVG. Pour un nœud `(x, y, w, h)`: bord gauche `(x, y+h/2)`, droit `(x+w, y+h/2)`, haut `(x+w/2, y)`, bas `(x+w/2, y+h)`.

- Segment: `div` à une bordure. Horizontal `class="arch-edge arch-line-h"` avec `left:X1%; top:Y%; width:(X2-X1)%`; vertical `arch-line-v` avec `left:X%; top:Y1%; height:(Y2-Y1)%`. Un coude juxtapose un vertical et un horizontal. `dashed` via `data-style`.
- Pointe: `arch-tip arch-tip-r|l|d|u` posée sur le bord de la cible avec `transform`: `r` `translate(-100%,-50%)`, `l` `translate(0,-50%)`, `d` `translate(-50%,-100%)`, `u` `translate(-50%,0)`.
- Libellé `arch-edge-label` (`position:absolute; white-space:nowrap`): sous la rangée (`top = y+h+2`, `translateX(-50%)`) pour un segment horizontal, à côté (`left = x+2`) pour un vertical. Jamais dans la bande verticale des boîtes.
- `data-type="arch-edge"` (avec `data-from`/`data-to`) sur le **segment principal** seulement; coudes, pointes et libellé n'ont que les classes CSS, sinon la liaison est comptée plusieurs fois.

### Contrôle avant de livrer

1. Chaque segment part d'un bord calculé et arrive sur un bord calculé, jamais « à l'œil ».
2. Aucun trait ne traverse une boîte non connectée: router dans les couloirs vides.
3. Aucun libellé ne recouvre une boîte ni un autre libellé.
4. Capture d'écran relue.

Conversion PPTX: chaque nœud devient une forme native, les pourcentages sont lus dans le repère du conteneur `arch-diagram` (qui reste `position:relative`, hauteur exploitable); `data-from`/`data-to` ne tracent pas de connecteur automatique en legacy.
