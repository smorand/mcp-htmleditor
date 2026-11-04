# Workflow: revue qualité d'un schéma d'architecture (sous-agent)

## Pourquoi un sous-agent dédié

Le calcul de layout (`arch-layout` / `layout_arch_diagram`) garantit la géométrie
(pas de collision, arêtes droites sur colonnes alignées, détour automatique des
obstacles) mais ne garantit pas la qualité *visuelle* d'ensemble: un label caché,
une couleur incohérente entre deux connecteurs du même flux, un budget de hauteur
dépassé — ces défauts demandent de **regarder l'image rendue**, pas seulement le
HTML. Faire cette revue dans la conversation principale de l'agent pollue son
contexte avec des captures d'écran et des itérations de correction qui n'ont pas
besoin d'y rester. D'où l'usage systématique d'un sous-agent isolé.

## Quand le déclencher

**Systématiquement**, immédiatement après tout appel à `mcp-htmleditor arch-layout`
ou à l'outil MCP `layout_arch_diagram`, sur le ou les diagrammes venant d'être
recalculés. Ne pas attendre un retour utilisateur négatif: la revue fait partie du
calcul de layout au même titre que l'absence de collision.

## Protocole (à donner au sous-agent)

Le sous-agent doit avoir accès à: lecture/écriture du fichier HTML, exécution de
`mcp-htmleditor arch-layout`, et un moyen de capturer une image (agent-browser,
Playwright, ou Chrome headless `--screenshot`, voir
`skill/workflow-create.md` § Validation visuelle pour la procédure exacte incluant
comment forcer l'affichage d'une slide précise en mode présentation).

Tâche à donner au sous-agent, verbatim adaptable:

```
Tu vas réviser le rendu du/des diagramme(s) d'architecture dans <fichier.html>,
slide(s) <N>. Charge la checklist qualité via `mcp-htmleditor arch-checklist`
(ou lis directement le fichier qu'elle indique) et vérifie CHAQUE règle contre
une capture d'écran de la slide.

Boucle bornée à 2 passes maximum:
1. Capture la slide.
2. Compare à la checklist, liste précisément chaque règle non respectée.
3. Si des défauts sont trouvés: corrige directement le HTML (édition de
   markup déclaratif — jamais de coordonnée écrite à la main), relance
   `mcp-htmleditor arch-layout` sur le fichier, recapture.
4. Si après 2 passes des défauts persistent: arrête-toi, ne tente pas de 3e
   correction. Remonte la liste exacte des défauts restants.

Rapporte en fin de tâche: la liste des corrections appliquées, et la liste des
défauts non résolus (le cas échéant), sans capture d'écran dans ton rapport
(juste le texte — l'agent principal peut re-capturer lui-même si besoin).
```

## Intégration dans le flux de l'agent principal

```
1. update_start()
2. Écrire/modifier le markup déclaratif (arch-row / arch-node / arch-col / arch-edge / arch-lane)
3. mcp-htmleditor arch-layout <fichier>   (ou layout_arch_diagram côté MCP)
4. Lancer le sous-agent de revue (protocole ci-dessus), en tâche de fond si
   plusieurs diagrammes sont à réviser en parallèle
5. Récupérer son rapport, l'intégrer sans le reformuler en détail à l'utilisateur
   (juste: "N corrections appliquées, M défauts restants: ...")
6. update_end()
```

## Étendre ou modifier les règles vérifiées

La checklist n'est pas dans ce fichier: elle vit dans
`~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md` (résolu par
`mcp-htmleditor arch-checklist`, voir `skill/checks/arch-diagram-checklist.md`
pour le contenu par défaut et sa logique de résolution). Ajouter un contrôle: ouvrir
ce fichier, ajouter une ligne `- [ ]`. Aucune réinstallation, aucun changement de
code n'est nécessaire — le sous-agent relit le fichier à chaque revue.
