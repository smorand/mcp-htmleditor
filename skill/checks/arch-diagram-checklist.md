# Checklist qualité des schémas d'architecture (`arch-diagram`)

Fichier éditable sans toucher au code: copie utilisateur dans `~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md` (seedée une fois par `make install`, jamais réécrite). Ajouter une règle = ajouter une ligne `- [ ]`. Relue à chaque appel; `HTMLEDITOR_ARCH_CHECKS_DIR` pointe vers un autre dossier.

## Utilisation

Après tout `mcp-htmleditor arch-layout` ou `layout_arch_diagram`, un sous-agent isolé: 1) capture la slide, 2) vérifie CHAQUE règle sur l'image et le HTML, 3) corrige le HTML, relance `arch-layout`, recapture. Boucle bornée à **2 passes maximum**: ensuite il remonte les défauts restants, sans 3e passe.

## Règles génériques

- [ ] Aucune arête ne traverse une boîte à laquelle elle n'est pas connectée.
- [ ] Aucun label (connecteur, badge, label de lane ou de col) ne chevauche une boîte ni un autre label.
- [ ] Aucune boîte ne dépasse le conteneur `arch-diagram` (bords droit et bas visibles).
- [ ] Aucun texte tronqué par sa boîte (retour à la ligne débordant, `overflow:hidden`).
- [ ] Le diagramme plus le reste de la slide tient dans 540px; sinon réduire le contenu, jamais la police.
- [ ] Les connecteurs d'un même flux portent le même `data-color`.
- [ ] Les badges `data-step` suivent l'ordre de lecture du flux, pas l'ordre du HTML.

## Rangées simples

- [ ] Arête entre deux nœuds distants d'une rangée avec un nœud tiers entre eux: elle contourne (le moteur détoure sous, puis au-dessus).
- [ ] Arête inter-rangées avec un troisième nœud dans la colonne de la source ou de la cible: détour vérifié visuellement.
- [ ] Source et cible bloquées chacune sur leur côté naturel: le contournement latéral reste dans 0-100% (`left`, `top`).
- [ ] Nœuds alignés en colonnes: ligne droite sans coude; sinon ajuster les `data-span`.
- [ ] Sortie par le côté ou coude bas/haut: aucune traversée; si les gouttières sont bloquées, réorganiser les `arch-spacer` et `data-span`.

## Rangées mixtes avec `arch-col`

- [ ] Le label de coin d'un `arch-col` n'est pas caché par le premier nœud imbriqué (sinon réduire le padding de ce nœud).
- [ ] La hauteur d'un `arch-col` suit son contenu réel: ajuster `data-height-weight` par nœud.
- [ ] Aucune arête entre deux `arch-col` ne traverse un `arch-col` intermédiaire ni une légende située sous le diagramme.

## Lanes (`arch-lane`)

- [ ] Le label de la lane ne chevauche pas le premier nœud qu'elle contient.
- [ ] La lane contient exactement les nœuds voulus: elle couvre toutes les rangées de `data-rows`, sinon séparer en rangées distinctes.

## Multi flux (couleurs, badges)

- [ ] Chaque flux a une légende ou liste latérale, dans le même ordre que ses badges.
- [ ] Les badges ont la même taille et sont centrés sur le trait.
- [ ] Un badge entre deux nœuds empilés dans un même `arch-col` reste lisible et proche de son arête (le moteur le déplace sur le côté).

## Libellés, nœuds étroits, contenu de slide

- [ ] Un libellé d'arête (`nowrap`) plus long que son segment: raccourcir le texte, ne pas changer la police.
- [ ] Un nœud étroit à icône et libellé, relié d'un seul côté: contenu aligné du côté de la sortie (`align-items:flex-end`).
- [ ] Un bloc après le diagramme (ex. notification) n'est pas coupé par `overflow:hidden`: `flex-shrink:0`, ou réduire le `min-height` du diagramme.

## Export PPTX

- [ ] Nœud imbriqué dans un `arch-col`: exporté à la bonne position.
- [ ] Badge `data-step`: cercle coloré, numéro centré.
- [ ] Rendu PPTX proche du rendu navigateur (les hauteurs y sont estimées).
