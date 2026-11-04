## Revue qualité d'un schéma d'architecture (sous-agent)

Le calcul de layout garantit la géométrie, pas la qualité visuelle (label caché, couleurs incohérentes, budget de hauteur dépassé): ces défauts se voient sur l'image rendue. La revue se fait donc dans un sous-agent isolé, pour ne pas polluer le contexte principal avec des captures.

## Quand la lancer

**Systématiquement**, juste après tout `mcp-htmleditor arch-layout` ou tout appel MCP `layout_arch_diagram`, sur les diagrammes venant d'être recalculés. Ne jamais attendre un retour négatif de l'utilisateur.

## Protocole du sous-agent

Accès requis: lecture et écriture du fichier HTML, `mcp-htmleditor arch-layout`, une capture d'image (agent-browser, Playwright ou Chrome headless; procédure d'affichage d'une slide précise: `mcp-htmleditor skill --type create`, § Validation visuelle).

Tâche à donner, adaptable:

```
Révise le rendu du ou des diagrammes d'architecture de <fichier.html>, slide(s) <N>.
Charge la checklist avec `mcp-htmleditor arch-checklist` (ou lis le fichier indiqué)
et vérifie CHAQUE règle contre une capture de la slide.

Boucle bornée à 2 passes maximum:
1. Capture la slide.
2. Compare à la checklist, liste chaque règle non respectée.
3. Si des défauts existent: corrige le markup déclaratif dans le HTML (jamais de
   coordonnée écrite à la main), relance `mcp-htmleditor arch-layout`, recapture.
4. Si des défauts persistent après 2 passes: arrête-toi, pas de 3e correction,
   remonte la liste exacte des défauts restants.

Rapporte en texte seul (aucune capture): les corrections appliquées, puis les
défauts non résolus.
```

## Intégration dans le flux de l'agent principal

```
1. update_start()
2. Écrire ou modifier le markup déclaratif (arch-row / arch-node / arch-col / arch-edge / arch-lane;
   règles: mcp-htmleditor skill --type arch-diagram)
3. mcp-htmleditor arch-layout <fichier>   (ou layout_arch_diagram côté MCP)
4. Lancer le sous-agent de revue (en tâche de fond si plusieurs diagrammes)
5. Reprendre son rapport sans le détailler à l'utilisateur
   (« N corrections appliquées, M défauts restants: ... »)
6. update_end()
```

## Modifier les règles vérifiées

La checklist est un fichier utilisateur, résolu par `mcp-htmleditor arch-checklist`: `~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md` (`HTMLEDITOR_ARCH_CHECKS_DIR` pour un autre dossier). Pour ajouter un contrôle, ajouter une ligne `- [ ]` dans ce fichier: aucune réinstallation ni changement de code, le sous-agent relit le fichier à chaque revue. Une checklist utilisateur remplace la checklist livrée ci-dessous.
