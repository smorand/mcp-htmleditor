# Checklist qualité — schémas d'architecture (`arch-diagram`)

**Ce fichier est éditable sans toucher au code.** L'emplacement réellement utilisé est
`~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md` (seedé une fois par
`make install`, jamais réécrit ensuite: contrairement aux templates, cette copie est
faite pour être modifiée à la main). Pour ajouter ou changer une règle: éditer ce
fichier directement, ajouter une ligne `- [ ]` dans la bonne section ou en créer une
nouvelle. `mcp-htmleditor skill` relit le fichier à chaque appel, aucune réinstallation
n'est nécessaire. `HTMLEDITOR_ARCH_CHECKS_DIR` permet de pointer vers un autre dossier
si besoin (partage d'équipe, checklist par projet, etc.).

## Comment cette checklist est utilisée

Après tout calcul de layout (`mcp-htmleditor arch-layout` ou l'outil MCP
`layout_arch_diagram`), l'agent qui pilote l'édition doit lancer une revue via un
**sous-agent isolé** (voir `skill/workflow-arch-qa.md` pour le protocole exact), qui:

1. Capture une image de la slide concernée (agent-browser / Playwright / Chrome headless).
2. Vérifie CHAQUE règle ci-dessous contre l'image et le HTML.
3. Corrige directement dans le fichier HTML si un défaut est trouvé.
4. Relance `arch-layout`, reprend une capture, revérifie.
5. Boucle bornée à **2 passes maximum**: au-delà, remonte les défauts restants à
   l'agent principal sans forcer une 3e passe (évite la boucle infinie de correction).

## Règles génériques (tout type de diagramme)

- [ ] Aucune arête ne traverse une boîte à laquelle elle n'est pas connectée
      (source et cible exclues de la vérification).
- [ ] Aucun label (texte de connecteur, badge numéroté, label de lane/col) ne
      chevauche une boîte ni un autre label.
- [ ] Aucune boîte ne dépasse les limites du conteneur `arch-diagram` (bords
      droit/bas entièrement visibles, rien coupé par l'`overflow` du parent).
- [ ] Aucun texte n'est tronqué par sa propre boîte (pas de retour à la ligne
      qui déborde du cadre, pas de `overflow:hidden` qui coupe une lettre).
- [ ] Le conteneur `arch-diagram` respecte le budget dur 540px de la slide (voir
      `skill/types/slides.md` § Hauteur utile): si le diagramme plus le reste de
      la slide dépasse, réduire le contenu, jamais la taille de police.
- [ ] Les couleurs par flux sont cohérentes: si plusieurs connecteurs partagent
      une même origine logique (même flux narratif), ils portent le même
      `data-color`.
- [ ] Les badges numérotés (`data-step`) suivent l'ordre de lecture attendu
      (1, 2, 3… dans le sens naturel du flux, pas dans l'ordre d'écriture du HTML).

## Rangées simples (flowchart, `arch-row` sans `arch-col`)

- [ ] Toute arête reliant deux nœuds distants dans la même rangée a été vérifiée
      visuellement: si un nœud tiers se trouve géométriquement entre eux, l'arête
      doit contourner (le moteur détecte l'obstacle et détoure automatiquement,
      en essayant sous la rangée puis au-dessus, `_best_detour`).
- [ ] Une arête inter-rangées "classique" (pas d'obstacle entre les rangées, mais
      un TROISIÈME nœud partageant le col de la cible ou de la source) a été
      vérifiée: le moteur détoure aussi ce cas depuis l'ajout de la vérification
      d'obstacle sur l'élbow standard, pas seulement sur le cas même-rangée.
- [ ] Si la source ET la cible sont chacune bloquées sur leur côté "naturel"
      (ex. la source a un voisin juste au-dessus, la cible a un voisin juste en
      dessous): le moteur tente un contournement par la gouttière de colonne la
      plus proche de la cible (`_side_detour_geometry`), jamais par le bord
      extérieur du diagramme (souvent occupé par une colonne qui touche déjà le
      bord à 0% ou 100%). Vérifier visuellement que ce contournement latéral ne
      sort pas des limites du diagramme (`left`/`top` doivent rester dans 0-100%).
- [ ] L'alignement en colonnes entre rangées adjacentes est exploité au maximum
      (deux nœuds alignés produisent une ligne droite unique, sans coude) — si un
      alignement évident n'est pas exploité, ajuster les `data-span` pour aligner
      les `mid_x`.

## Rangées mixtes avec `arch-col` (piles imbriquées, diagrammes narratifs)

- [ ] Le label de coin d'un `arch-col` (`data-label`) est-il visible, ou caché
      par le premier nœud imbriqué ? Si caché: soit accepter (la bordure seule
      suffit à montrer le regroupement), soit réduire le padding du premier
      nœud enfant pour laisser la place au label.
- [ ] Chaque `arch-col` a une hauteur cohérente avec son contenu réel: un col
      avec deux nœuds à texte court ne doit pas être aussi haut qu'un col avec
      deux nœuds à sous-description longue — ajuster `data-height-weight` par
      nœud si besoin.
- [ ] Aucune arête entre deux `arch-col` distincts de la même rangée ne traverse
      un troisième col placé entre eux (le moteur détoure automatiquement sous
      la rangée; vérifier visuellement que ce détour ne chevauche pas une
      légende ou un élément hors diagramme situé sous la slide).

## Lanes (`arch-lane`)

- [ ] Le label de la lane (coin supérieur gauche) ne chevauche-t-il pas le
      premier nœud qu'elle contient ?
- [ ] La lane contient-elle exactement les nœuds voulus, pas plus ? Une lane
      couvre TOUTES les rangées de sa plage `data-rows`, pas un slot spécifique:
      si un nœud d'une rangée couverte ne doit visuellement pas être inclus,
      restructurer en rangées séparées plutôt que d'accepter le débordement
      sémantique.

## Diagrammes multi-flux (plusieurs connecteurs de couleurs différentes, badges numérotés)

- [ ] Chaque flux (couleur) a-t-il une légende ou une liste latérale
      correspondante (ex. « Flux de la requête ») ? Si oui, l'ordre des badges
      doit correspondre à l'ordre de cette légende.
- [ ] Les badges numérotés sont-ils tous à la même taille, bien centrés sur le
      trait (pas décalés dans le vide) ?
- [x] **CORRIGÉ.** Un badge numéroté sur une arête reliant deux nœuds empilés dans
      le même `arch-col` (adjacents, gutter `NESTED_GUTTER_PCT` de 2 % du col — trop
      étroit pour loger le badge de 14px sans toucher les deux bordures) est
      automatiquement déplacé sur le côté (`_badge_position`), hors de l'emprise
      des deux nœuds, plutôt que laissé au milieu géométrique invisible. Déclenché
      par `_vertical_gap` < `BADGE_MIN_GUTTER_PCT` (5 %) quand les deux nœuds sont
      alignés/superposés horizontalement (`_render_edge`, `arch_layout.py`); un
      gutter horizontal normal (`GUTTER_COL_PCT`/`GUTTER_ROW_PCT`, 4-6 %) n'est
      jamais concerné, seul l'empilement vertical dans un col l'est. Repli: si les
      deux côtés (gauche et droite du couple) sont eux-mêmes occupés par un autre
      nœud, le badge retombe sur le milieu géométrique (defect cosmétique mineur
      resté acceptable dans ce cas rare, jamais un blocage). Vérifier visuellement
      que le badge déplacé reste lisible et proche visuellement de son arête
      (test `test_badge_on_stacked_nodes_is_pushed_clear_of_the_narrow_gutter`).

## Nœuds étroits avec icône + libellé (ex. « Utilisateur », acteur seul)

- [ ] Un nœud à contenu centré (`align-items:center`) dont la seule sortie est
      une arête d'un seul côté (typiquement un acteur/icône relié par une
      flèche) laisse-t-il un vide visible entre le contenu visuel (icône,
      texte) et le début du trait ? Si oui, aligner le contenu du côté de la
      sortie (`align-items:flex-end` si l'arête part à droite, etc.) plutôt que
      de centrer — la boîte garde sa taille, seul le contenu se rapproche du
      point de sortie réel.

## Libellés de connecteur trop longs pour l'espace disponible

- [ ] Le libellé d'une arête (`data-label`, rendu en `.arch-edge-label`,
      `white-space:nowrap`) dépasse-t-il visuellement les nœuds voisins parce
      que le segment est court (ex. deux nœuds adjacents avec un simple coude
      de raccord) ? Le moteur ne réduit ni ne wrappe jamais un libellé
      automatiquement (`white-space:nowrap` fixe). Corriger en RACCOURCISSANT
      le texte (préférer un mot court et clair, ex. « Async » plutôt que
      « Tâches asynchrones ») plutôt qu'en changeant la police ou en
      wrappant — un libellé qui tient sur un mot reste plus lisible qu'un
      libellé sur deux lignes avec une police réduite.

## Sortie d'arête par le côté plutôt que par le bas (CORRIGÉ, heuristique)

- [x] **CORRIGÉ (heuristique, pas garanti dans tous les cas).** Quand la cible
      d'une arête inter-rangées (`row_diff != 0`) est plus décalée
      horizontalement que verticalement par rapport à la source
      (`abs(mid_x source - mid_x cible) > abs(mid_y source - mid_y cible)`), le
      moteur essaie d'abord une sortie par le côté (droite puis gauche,
      `_side_exit_geometry`): sortie horizontale immédiate au niveau de la
      source, descente/montée dans la gouttière de colonne la plus proche,
      entrée horizontale dans la cible. N'est utilisée que si le trajet ne
      traverse aucun obstacle (`_crosses_any_obstacle`, sur les deux côtés
      testés); sinon repli automatique sur l'ancien coude bas/haut
      (`_adjacent_row_geometry`), sans jamais introduire de nouvel
      avertissement (`_route_edge` / `arch_layout.py`).
      **Limite connue, résiduelle**: l'heuristique compare seulement `dx` et
      `dy` des centres, elle ne mesure pas la longueur réelle du chemin
      candidat vs l'ancien coude — dans un diagramme où les deux gouttières de
      colonne (gauche et droite de la source) sont bloquées par un autre
      nœud, le moteur retombe sur le coude bas/haut même si `dx > dy` (cas
      couvert par `test_side_exit_falls_back_to_the_elbow_when_the_channel_is_blocked`).
      C'est correct (aucune régression, `0 warning`) mais reste le coude
      moins direct dans ce cas de bordure; si rencontré fréquemment sur un
      diagramme donné, envisager de réorganiser les `arch-spacer`/`data-span`
      pour dégager une gouttière plutôt que d'attendre un fix moteur supplémentaire.

## Diagramme + contenu de slide qui se chevauchent ou se coupent

- [ ] Si la slide a un bloc de contenu APRÈS le diagramme (ex. notification
      « Questions ouvertes »), ce bloc est-il coupé en bas par l'`overflow:hidden`
      du conteneur `.slide-body` ? Cause typique: le wrapper `arch-diagram` a un
      `min-height` fixe qui, combiné à `flex:1`, force le bloc suivant (sans
      `flex-shrink:0` explicite) à être compressé sous sa hauteur naturelle par
      le flex-shrink par défaut, débordant ensuite dans l'espace masqué par le
      parent. Fix: ajouter `flex-shrink:0` sur le bloc de contenu qui ne doit
      jamais rétrécir, et/ou réduire le `min-height` du diagramme de quelques
      dizaines de px si la place manque réellement.

## Export PPTX (fidélité)

- [ ] Un nœud imbriqué dans un `arch-col` s'exporte-t-il à la bonne position ?
      (Bug corrigé dans `to_pptx.py::_render_arch_children` — vérifier sur tout
      nouveau cas de nesting profond ou de primitive ajoutée depuis.)
- [ ] Un badge numéroté (`data-step`) s'exporte-t-il en cercle coloré avec le
      numéro centré ? (`to_pptx.py::_render_arch_badge`, corrigé — vérifier sur
      tout nouveau cas si le format du badge a changé depuis.)
- [ ] Comparer visuellement le rendu PPTX (LibreOffice ou PowerPoint) au rendu
      navigateur: les proportions doivent rester proches — le PPTX approxime
      les hauteurs par un flux de blocs, pas par le CSS réel du navigateur.
