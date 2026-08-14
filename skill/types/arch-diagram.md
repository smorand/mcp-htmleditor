# Types: Schéma d'architecture

## Format déclaratif (recommandé, à partir de 4 nœuds)

**Ne jamais calculer de position à la main dès qu'un diagramme a un flux à plusieurs
rangées ou plus de 3 nœuds.** Un moteur de layout déterministe (`arch_layout.py`)
existe précisément pour ça: le LLM déclare des rangées, des nœuds et des relations,
jamais de `%`, et une commande calcule tout le reste. Ça élimine par construction les
bugs récurrents du calcul manuel: superposition de nœuds, flèches penchées, labels
posés loin de leur flèche, lane qui déborde de son contenu.

### Ce que le LLM écrit

```html
<div data-type="arch-diagram" data-diagram-id="mcp-arch" style="position:relative; width:100%; height:320px;">

  <div data-type="arch-lane" data-lane-id="edge" data-label="Edge" data-rows="0-1"></div>

  <div data-type="arch-row" data-row="0">
    <div data-type="arch-node" data-id="agent" data-label="Agent LLM" data-shape="box"
         style="border:2px solid #003A8D; background:#003A8D; color:#fff; border-radius:4px;"></div>
    <div data-type="arch-node" data-id="mcp" data-label="Serveur MCP" data-shape="box"
         style="border:2px solid #003A8D; background:#e6ecf7; color:#003A8D; border-radius:4px;"></div>
  </div>

  <div data-type="arch-row" data-row="1">
    <div data-type="arch-node" data-id="file" data-label="Fichier HTML" data-span="2"
         style="border:2px solid #FBAE40; background:#fff6e6; color:#8a5b00; border-radius:4px;"></div>
  </div>

  <div data-type="arch-edge" data-from="agent" data-to="mcp" data-label="MCP stdio"></div>
  <div data-type="arch-edge" data-from="agent" data-to="file" data-label="écriture directe"></div>

</div>
```

Puis calculer et écrire les positions:

```bash
mcp-htmleditor arch-layout mon-fichier.html
```

ou via l'outil MCP `layout_arch_diagram(file, diagram_id=None)`, avant de valider
visuellement (capture d'écran, cf. `skill/workflow-create.md` § Validation visuelle).
Les deux appellent la même fonction Python, zéro comportement différent.

### Règles

- **`arch-row`** groupe les nœuds d'une même rangée horizontale (`data-row` = index
  0-based, ordre non important dans le fichier: le moteur les trie). Poids optionnel
  `data-height-weight` (défaut 1, rangées égales).
- **`arch-node`** à l'intérieur d'une rangée: `data-id` obligatoire et unique dans le
  diagramme (utilisé par les arêtes), `data-label`, `data-shape`, et un `style` pour la
  seule décoration visuelle (couleur, bordure) — **jamais** `data-x`, `data-y`, `left`,
  `top`, `width`, `height`: ces attributs sont uniquement la sortie du moteur, les écrire
  à la main serait immédiatement écrasé au prochain calcul. `data-span` (défaut 1) élargit
  un nœud sur plusieurs unités de colonne, façon `colspan`.
- **`arch-edge`** entre deux `data-id`: `data-from`, `data-to`, `data-label` optionnel,
  `data-style` optionnel (`solid`/`dashed`/`dotted`). Le moteur route un segment droit
  entre nœuds de la même rangée, et un coude (ou une ligne verticale unique si les deux
  nœuds sont alignés en colonne) entre rangées adjacentes. La pointe de flèche est
  toujours posée sur le nœud cible (`data-to`), quel que soit l'ordre visuel gauche/droite.
- **`arch-lane`** (optionnel): `data-lane-id`, `data-label`, `data-rows="debut-fin"`
  (index de rangées couvertes, ex. `"0-1"` ou juste `"2"`). Sa boîte est calculée comme
  l'union des nœuds des rangées couvertes plus un padding fixe — jamais devinée à l'œil,
  donc jamais trop petite pour son contenu.
- **`arch-row`/`arch-lane` restent en permanence dans le DOM**, jamais aplatis ni
  supprimés après calcul: ajouter un nœud à une rangée existante puis relancer
  `arch-layout` fonctionne sans reconstruire le diagramme.
- **Invariant CSS dur**: `arch-row`/`arch-lane` ne doivent **jamais** recevoir
  `position:relative`. Les `%` calculés sur les `arch-node`/`arch-edge` se résolvent
  contre le conteneur `arch-diagram` de premier niveau, exactement comme l'export PPTX
  les relit (`export/to_pptx.py::_render_arch`, traversée récursive) — poser
  `position:relative` sur un wrapper intermédiaire romprait cette parité en silence.

### Primitives avancées (V2): piles imbriquées, alignement, badges d'étape

Trois ajouts pour couvrir les diagrammes narratifs (flux numérotés, cartes avec icône
+ sous-description, colonnes à hauteur mixte) sans sortir du modèle déclaratif:

- **`arch-col`** (pile verticale imbriquée dans un slot de rangée): un enfant direct
  d'`arch-row` peut être un `arch-col` au lieu d'un `arch-node`. Il occupe un slot de
  la distribution horizontale (même `data-span`) mais répartit sa propre hauteur entre
  ses `arch-node` enfants (empilés, poids optionnel `data-height-weight` par enfant).
  Cas d'usage: une carte large à côté de deux petites cartes empilées dans la même
  rangée (ex. "Coffre-fort" à côté de "Observabilité"/"Evaluation" empilés).
  ```html
  <div data-type="arch-row" data-row="0">
    <div data-type="arch-node" data-id="vault" data-label="Coffre-fort"></div>
    <div data-type="arch-col">
      <div data-type="arch-node" data-id="obs" data-label="Observabilité"></div>
      <div data-type="arch-node" data-id="eval" data-label="Evaluation"></div>
    </div>
  </div>
  ```
- **`arch-spacer`** (réservation de largeur invisible): un slot de rangée sans nœud,
  utilisé pour aligner un nœud d'une rangée sous une colonne précise d'une autre
  rangée plus large, sans que le nœud isolé s'étale sur toute la largeur.
  ```html
  <div data-type="arch-row" data-row="0">
    <div data-type="arch-node" data-id="proxy" data-label="IA Gen Proxy"></div>
    <div data-type="arch-spacer"></div>
    <div data-type="arch-spacer"></div>
  </div>
  <div data-type="arch-row" data-row="1">
    <div data-type="arch-node" data-id="vllm" data-label="vLLM"></div>
    <div data-type="arch-node" data-id="qwen" data-label="Qwen"></div>
    <div data-type="arch-node" data-id="slot" data-label="slot libre"></div>
  </div>
  ```
  Ici `proxy` s'aligne exactement sur la colonne de `vllm`, sans chevaucher `qwen`.
- **`data-step`** sur `arch-edge` (badge numéroté): pose un cercle coloré contenant
  le numéro au **véritable milieu du segment** (pas au point offset du libellé texte,
  les deux peuvent coexister). Couleur via `data-color` (défaut bleu). Convention des
  diagrammes à étapes numérotées (①②③...) avec une légende à côté du schéma.
  ```html
  <div data-type="arch-edge" data-from="harness" data-to="gateway"
       data-step="5" data-color="#2CA02C"></div>
  ```

Limite connue: le badge (`arch-edge-badge`) n'est pas encore converti à l'export PPTX
(seul le segment/pointe/label le sont); documenté comme élément perdu à l'export tant
que `export/to_pptx.py` n'a pas de branche dédiée.

### Édition à la souris (mode édition du navigateur)

En mode édition, un diagramme déclaratif (contenant au moins un `arch-row`) offre des
actions à la souris symétriques du texte/documents:

- **Clic droit sur le fond du diagramme** → "＋ Ajouter nœud": choisit une rangée
  existante ou en crée une nouvelle, insère un `arch-node` nu (sans position).
- **Clic droit sur un nœud** → "Renommer", "Changer forme", "➜ Créer une arête
  depuis ce nœud" (clique ensuite sur le nœud cible, ou Echap pour annuler),
  "Supprimer" (retire aussi toute arête qui référençait ce nœud).

Chaque action déclenche automatiquement: sauvegarde du DOM (`saveContent`), puis
`POST /arch-layout` (le navigateur ne calcule jamais de position lui-même, il
écrit le même markup déclaratif que le LLM et demande au serveur de le résoudre),
puis rechargement automatique via le polling existant. Un diagramme legacy (sans
`arch-row`) garde l'ancien comportement (nœud positionné en dur à la création, à
`data-x="40.0"`) pour ne rien casser sur les fichiers existants.

### Hors scope V1 (limite documentée, pas un oubli)

- Une arête qui saute plus d'une rangée est routée quand même (même formule de coude),
  mais **sans vérification** qu'elle ne traverse pas une rangée intermédiaire: le moteur
  émet un avertissement (`diagrams_updated`/`warnings` du rapport CLI/MCP). Au-delà de 2
  rangées d'écart, découper le diagramme ou passer par une rangée intermédiaire.
- Pas de minimisation de croisements: si un diagramme a besoin de ça, c'est qu'il a trop
  de nœuds pour une slide de toute façon (cf. `skill/types/slides.md` § budget 540 px).
- Un nœud verrouillé (`data-layout="manual"`, posé automatiquement par un glisser-déposer
  humain dans le navigateur) garde sa position exacte lors d'un recalcul ultérieur; ses
  arêtes sont routées depuis sa position réelle, pas depuis la ligne médiane théorique de
  sa rangée.

---

## Format legacy (diagrammes simples, 2-3 nœuds)

Pour un tout petit schéma (2-3 nœuds, pas de flux multi-rangées), le calcul manuel
reste valide et documenté ci-dessous — c'est le format que l'exporteur PPTX a toujours
lu, et qu'un `mcp-htmleditor arch-layout` sur un diagramme sans `arch-row` laisse
intact (les deux formats coexistent dans le même fichier).

## Positionnement: data-x / data-y en pourcentages (règle absolue)

Un nœud (`data-type="arch-node"`) porte sa position dans des attributs LISIBLES:

- `data-x`: position gauche en pourcentage (0-100) du conteneur, arrondie à 1 décimale.
- `data-y`: position haut en pourcentage (0-100) du conteneur, arrondie à 1 décimale.
- un style inline `position:absolute; left:X%; top:Y%;` qui reproduit exactement `data-x`/`data-y` pour le rendu.

Le conteneur `data-type="arch-diagram"` doit être `position:relative` pour servir
de repère aux pourcentages. Pas de transform matrix, pas de coordonnées en pixels,
pas d'attribut cryptique: le LLM lit `data-x`/`data-y` directement et sans ambiguïté,
et l'humain peut déplacer les boîtes à la souris en mode édition (l'éditeur réécrit
`data-x`/`data-y` + `left`/`top` en %). LLM et humain travaillent sur le même format.

**Donner aussi `data-width`/`data-height` et les `width`/`height` en %.** Sans taille
explicite, la boîte prend la largeur de son texte, ses bords sont inconnus, et aucun
connecteur ne peut être ancré dessus.

### Exemple d'un nœud

```html
<div data-type="arch-node" class="arch-node" data-label="Serveur MCP" data-shape="box"
     data-x="27.0" data-y="2.0" data-width="21.0" data-height="15.0"
     style="position:absolute; left:27.0%; top:2.0%; width:21.0%; height:15.0%;
            border:2px solid #003A8D; background:#e6ecf7; color:#003A8D; border-radius:4px;">
  Serveur MCP<small>transport stdio</small>
</div>
```

```css
.arch-node {
  box-sizing:border-box; display:flex; flex-direction:column;
  align-items:center; justify-content:center; text-align:center;
  font-size:11.5px; font-weight:700; line-height:1.25; padding:4px 6px;
}
.arch-node small { display:block; font-weight:400; font-size:9.5px; margin-top:2px; opacity:.85; }
```

---

## Connecteurs: méthode d'ancrage (obligatoire)

Les flèches en glyphes Unicode (`→`, `⇓`) posées « à l'estime » produisent des liaisons
coupées et des libellés posés sur les boîtes. La méthode validée est purement CSS et
entièrement calculable.

### 1. Calculer les bords du nœud

Pour un nœud `(x, y, w, h)` en % du conteneur:

| Point d'ancrage | Coordonnées |
|---|---|
| bord gauche, milieu vertical | `(x, y + h/2)` |
| bord droit, milieu vertical | `(x + w, y + h/2)` |
| bord haut, milieu horizontal | `(x + w/2, y)` |
| bord bas, milieu horizontal | `(x + w/2, y + h)` |

Pour la boîte de l'exemple ci-dessus: bord droit `(48.0, 9.5)`, bord bas `(37.5, 17.0)`.
Nommer ces valeurs une fois (`ROW1_MID = 9.5`) et les réutiliser: toutes les boîtes d'une
même rangée partagent le même milieu vertical, donc un unique segment horizontal.

### 2. Tracer le segment en ligne CSS

Un trait est un `div` sans surface, avec une seule bordure. Pas de SVG, pas de glyphe.

```css
.arch-edge   { position:absolute; }
.arch-line-h { height:0; border-top:1.5px solid #284AAA; }
.arch-line-v { width:0;  border-left:1.5px solid #284AAA; }
.arch-line-h.dashed { border-top-style:dashed; }
.arch-line-v.dashed { border-left-style:dashed; }
```

- horizontal: `style="left:X1%; top:Y%; width:(X2-X1)%;"`
- vertical: `style="left:X%; top:Y1%; height:(Y2-Y1)%;"`

Un coude est la simple juxtaposition d'un segment vertical et d'un segment horizontal
qui partagent leur point de rencontre.

### 3. Poser la pointe de flèche

Triangle CSS, ancré par `transform` pour que sa pointe touche exactement le bord visé:

```css
.arch-tip   { width:0; height:0; }
.arch-tip-r { border-left:7px solid #284AAA;  border-top:4.5px solid transparent; border-bottom:4.5px solid transparent; }
.arch-tip-l { border-right:7px solid #284AAA; border-top:4.5px solid transparent; border-bottom:4.5px solid transparent; }
.arch-tip-d { border-top:7px solid #284AAA;   border-left:4.5px solid transparent; border-right:4.5px solid transparent; }
.arch-tip-u { border-bottom:7px solid #284AAA; border-left:4.5px solid transparent; border-right:4.5px solid transparent; }
```

| Direction | `transform` | Sens de la flèche |
|---|---|---|
| `r` | `translate(-100%,-50%)` | vers la droite, pointe sur le bord gauche de la cible |
| `l` | `translate(0,-50%)` | vers la gauche, pointe sur le bord droit de la cible |
| `d` | `translate(-50%,-100%)` | vers le bas, pointe sur le bord haut de la cible |
| `u` | `translate(-50%,0)` | vers le haut, pointe sur le bord bas de la cible |

Le `left`/`top` de la pointe est le point d'ancrage de la cible, pas la fin du segment:
c'est le `transform` qui la recule de sa propre taille. Une flèche bidirectionnelle est
un segment plus deux pointes opposées.

### 4. Déporter le libellé

```css
.arch-edge-label { position:absolute; font-size:9.5px; color:#50565B; white-space:nowrap; }
```

Un libellé centré sur un intervalle de 4 à 5 % de large déborde toujours sous les boîtes
voisines. Règles:

- **Rangée horizontale**: fixer une ligne de libellés unique **sous** les boîtes
  (`top = y + h + 2`), et centrer chaque libellé sur le milieu de son segment avec
  `transform:translateX(-50%)`.
- **Segment vertical**: poser le libellé **à côté** du trait (`left = x + 2`), à mi-hauteur,
  sans `transform`.
- Ne jamais placer un libellé dans la bande verticale occupée par les boîtes d'une rangée.

---

## Exemple complet et calculable

Trois nœuds, une rangée plus une descente en coude. Toutes les valeurs découlent des
formules de bord: rangée 1 en `y=2, h=15` donc `ROW1_MID = 9.5`; boîte centrale en
`y=42, h=17` donc `FILE_MID = 50.5`.

```html
<div data-type="arch-diagram" style="position:relative; width:100%; height:100%; min-height:250px;">

  <!-- Nœuds: A (1→22), B (27→48), Fichier (26→74) -->
  <div data-type="arch-node" class="arch-node" data-label="Agent LLM" data-shape="box"
       data-x="1.0" data-y="2.0" data-width="21.0" data-height="15.0"
       style="position:absolute; left:1.0%; top:2.0%; width:21.0%; height:15.0%;
              border:2px solid #003A8D; background:#003A8D; color:#fff; border-radius:4px;">Agent LLM</div>

  <div data-type="arch-node" class="arch-node" data-label="Serveur MCP" data-shape="box"
       data-x="27.0" data-y="2.0" data-width="21.0" data-height="15.0"
       style="position:absolute; left:27.0%; top:2.0%; width:21.0%; height:15.0%;
              border:2px solid #003A8D; background:#e6ecf7; color:#003A8D; border-radius:4px;">Serveur MCP</div>

  <div data-type="arch-node" class="arch-node" data-label="Fichier HTML" data-shape="box"
       data-x="26.0" data-y="42.0" data-width="48.0" data-height="17.0"
       style="position:absolute; left:26.0%; top:42.0%; width:48.0%; height:17.0%;
              border:2px solid #FBAE40; background:#fff6e6; color:#8a5b00; border-radius:4px;">Fichier HTML</div>

  <!-- A → B: bord droit de A (22, 9.5) vers bord gauche de B (27, 9.5) -->
  <div data-type="arch-edge" data-from="agent-llm" data-to="serveur-mcp" data-style="solid"
       class="arch-edge arch-line-h" style="left:22.0%; top:9.5%; width:5.0%;"></div>
  <div class="arch-edge arch-tip arch-tip-r" style="left:27.0%; top:9.5%; transform:translate(-100%,-50%);"></div>
  <div class="arch-edge-label" style="left:24.5%; top:19.0%; transform:translateX(-50%);">MCP stdio</div>

  <!-- A → Fichier: descente depuis le bas de A (11.5, 17) puis coude vers la droite -->
  <div class="arch-edge arch-line-v" style="left:11.5%; top:17.0%; height:33.5%;"></div>
  <div class="arch-edge arch-line-h" style="left:11.5%; top:50.5%; width:14.5%;"></div>
  <div class="arch-edge arch-tip arch-tip-r" style="left:26.0%; top:50.5%; transform:translate(-100%,-50%);"></div>
  <div class="arch-edge-label" style="left:13.5%; top:42.0%;">écriture directe</div>

</div>
```

Détail des calculs: bord bas de A = `1 + 21/2 = 11.5` en x, `2 + 15 = 17` en y; la descente
va de `17` à `FILE_MID = 50.5`, donc `height = 33.5`; le coude court de `11.5` au bord
gauche du fichier `26`, donc `width = 14.5`.

Schéma complet à 7 nœuds et 12 connecteurs, vérifié par capture:
`templates/reference/slides/example-ei-complete.html`, slide « Architecture mcp-htmleditor ».

### Contrôle avant de livrer

1. Chaque segment part d'un bord calculé et arrive sur un bord calculé, jamais sur une
   valeur arrondie « à l'œil ».
2. Aucun trait ne traverse une boîte à laquelle il n'est pas connecté: router dans les
   couloirs vides entre rangées et entre colonnes.
3. Aucun libellé ne recouvre une boîte ni un autre libellé.
4. Capture d'écran relue: une liaison coupée en morceaux se voit immédiatement.

---

## Shapes disponibles

| Valeur `data-shape` | Rendu CSS | Usage |
|---------------------|-----------|-------|
| `box` | Rectangle, `border-radius:0` ou 4px | Service, composant |
| `circle` | `border-radius:50%` | Acteur, endpoint |
| `diamond` | `transform:rotate(45deg)` | Décision, condition |
| `cylinder` | Simulé avec `border-radius` top/bottom | Base de données |
| `cloud` | `border-radius:50px` + style | Cloud provider |

```css
.arch-box      { border-radius: 0; }
.arch-circle   { border-radius: 50%; width: 80px; height: 80px; display:flex; align-items:center; justify-content:center; }
.arch-diamond  { transform: rotate(45deg); }
.arch-diamond .label { transform: rotate(-45deg); }
.arch-cylinder { border-radius: 8px / 20px; }
.arch-cloud    { border-radius: 50px; }
```

Attention: une forme non rectangulaire (`circle`, `diamond`) déplace ses bords visuels par
rapport à sa boîte. Ancrer les connecteurs sur le milieu des bords de la boîte, et accepter
le petit espace, plutôt que de viser le contour réel.

### Où ce CSS existe déjà, et ce qui est réellement rendu

Dans les deux fichiers de la charte IBM Carbon (`templates/bootstrap/slides-empty.html`,
copié par `mcp-htmleditor new carbon`, et `templates/reference/slides/ibm-carbon.html`), ce
CSS est **déjà embarqué**, et doubleé de sélecteurs d'attribut, donc `data-shape` et
`data-style` suffisent, sans classe ni style inline:

```css
.arch-circle, .arch-node[data-shape="circle"] { border-radius: 50%; }
.arch-line-h.dashed, .arch-edge[data-style="dashed"] { border-style: dashed; }
```

Les 5 formes et les 3 styles de trait ont un rendu visuel vérifié par capture dans ces deux
fichiers. Deux limites à connaître:

- `circle` sur un nœud dont `data-width` et `data-height` ne donnent pas le même nombre de
  pixels produit une **ellipse**, pas un cercle. Pour un vrai cercle, poser des dimensions
  égales en pixels plutôt qu'en pourcentages.
- `diamond` fait tourner la boîte entière: mettre le texte dans un `<span>` enfant, il est
  remis d'aplomb par `.arch-node[data-shape="diamond"] > *`.

Dans un document Euro-Information, ce CSS n'existe pas: il faut le déclarer dans la slide
ou dans le `<style>` du document.

## Attributs d'un nœud

| Attribut | Description | Exemple |
|----------|-------------|---------|
| `data-type="arch-node"` | Identifie un nœud | (pas de valeur) |
| `data-label` | Libellé affiché | `"API Gateway"` |
| `data-shape` | Forme visuelle | `box`, `circle`, `diamond`, `cylinder`, `cloud` |
| `data-x` | Position gauche en % (0-100) | `27.0` |
| `data-y` | Position haut en % (0-100) | `2.0` |
| `data-width` | Largeur en % | `21.0` |
| `data-height` | Hauteur en % | `15.0` |
| `data-color` | Couleur de fond | `#e6ecf7` |

## Attributs d'un connecteur

| Attribut | Description | Exemple |
|----------|-------------|---------|
| `data-type="arch-edge"` | Identifie un connecteur | (pas de valeur) |
| `data-from` | `data-label` ou id du nœud source | `agent-llm` |
| `data-to` | `data-label` ou id du nœud cible | `serveur-mcp` |
| `data-style` | `solid`, `dashed`, `dotted` | `solid` |
| `data-label` | Libellé de la liaison | `"MCP stdio"` |

Porter `data-type="arch-edge"` sur **le segment principal** de la liaison. Les segments de
coude, les pointes et le libellé sont de la décoration: leur donner seulement les classes
CSS, sinon un connecteur est compté plusieurs fois.

## Conventions de nommage

- Utiliser les noms techniques réels: `"API Gateway"`, `"PostgreSQL"`, `"Redis Cache"`
- Pas d'abréviations ambiguës: `"Auth Service"` plutôt que `"AS"`
- Pour les bases de données: ajouter le type `"DB: PostgreSQL"` ou `"Cache: Redis"`

## Layouts suggérés

### Left-to-right (flux de gauche à droite)
```
[Client] → [Load Balancer] → [API] → [DB]
```
Une rangée: même `data-y` et même `data-height`, `data-x` croissant, un pas régulier
(par exemple largeur 21 %, gouttière 5 %). Un seul milieu vertical pour tous les segments.

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
Rangées empilées: `data-y` croissant avec un couloir vide de 8 à 12 % entre deux rangées
pour laisser passer les segments horizontaux et les libellés.

## Conversion PPTX

Chaque nœud devient une forme PPTX native, avec la forme déduite de `data-shape`
(box, circle, diamond, cylinder, cloud), le fond et la bordure lus sur le style,
le libellé et son sous-libellé (`<small>`, `.arch-node-label`). Les pourcentages
`data-x` / `data-y` / `data-width` / `data-height` sont interprétés **dans le
repère du conteneur** `arch-diagram`, jamais dans celui de la slide: le conteneur
doit donc rester `position:relative` avec une hauteur exploitable.

Les connecteurs sont convertis selon leur écriture: les traits CSS
(`.arch-line-h`, `.arch-line-v`) deviennent des segments, les pointes
(`.arch-tip-r/l/u/d`) des triangles, les flèches texte (`→`, `↓`) et les
`.arch-edge-label` des zones de texte positionnées. `data-from` / `data-to` ne
sont pas utilisés pour tracer des connecteurs automatiques: la géométrie du HTML
est reprise telle quelle. Voir `skill/workflow-export.md`.
