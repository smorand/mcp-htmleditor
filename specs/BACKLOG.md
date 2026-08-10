# Backlog

> Idées différées, hors périmètre d'une spec existante ou pas encore assez cadrées pour
> devenir des FR. Ne PAS modifier les specs `specs/*.md` existantes pour ces idées:
> chacune deviendra sa propre spec (`/project:spec`) le jour où elle est priorisée.
> Format par entrée: ID, titre, description, rationale du report, spec/contexte d'origine.

## BACKLOG-001: Édition de diagramme de Gantt dans l'éditeur

**Description:** Aujourd'hui `mcp-htmleditor` sait insérer un bloc Gantt vide via le picker
de slide (`data-type="gantt"` + `gantt-task` enfants) et l'exporter en formes natives
PPTX, mais toute édition d'un Gantt existant (déplacer une tâche, changer ses dates
`data-start`/`data-end`, ajouter/supprimer une tâche, changer sa couleur) exige que
l'agent LLM réécrive le HTML à la main — aucune interaction souris dans le navigateur
équivalente au drag-move déjà en place pour les `arch-node` (voir
`makeArchNodeDraggable` dans `editor.js`). Idée: poignées de drag horizontal sur chaque
barre de tâche (déplacer/redimensionner en modifiant `data-start`/`data-end` ou les `%`
inline), un bouton `+` pour ajouter une tâche, un menu contextuel pour la couleur/le
libellé — sur le même modèle que le drag-reorder de blocs déjà livré.

**Rationale du report:** Nécessite une interview dédiée (scope: dates absolues vs
pourcentages inline, granularité du snap, gestion du chevauchement de tâches, export
PPTX à revalider après chaque interaction). YAGNI pour l'instant: les Gantt sont encore
rédigés/ajustés par l'agent LLM directement dans le HTML, ce qui couvre l'usage actuel.

**Origine:** Suggéré par l'utilisateur (session du 2026-08-10, hors interview de spec).
Contexte technique: `specs/2026-08-07_16-31-00-mcp-htmleditor-retrospective.md` FR-008
(renumérotation), architecture Gantt documentée dans `skill/types/gantt.md`.

---

## BACKLOG-002: Édition de schéma d'architecture dans l'éditeur

**Description:** Le déplacement de nœud (`arch-node`, `data-x`/`data-y` en %) existe déjà
en mode édition navigateur (drag de position). Manquent: ajouter/supprimer un nœud ou un
connecteur (`arch-edge`) depuis l'UI, redimensionner un nœud (largeur/hauteur), choisir sa
forme (`data-shape`) ou le style de connecteur (`data-style`: solid/dashed/dotted) sans
repasser par l'agent LLM. Idée: étendre le menu contextuel déjà présent sur les éléments
`data-type` (voir en-tête de `editor.js`, "Context menus on data-type elements") avec des
actions nœud/connecteur, poignées de redimensionnement aux coins, et un mode "relier deux
nœuds" au clic pour créer un `arch-edge`.

**Rationale du report:** Le schéma d'architecture est le composant le plus complexe à
éditer visuellement (positions relatives, connecteurs qui doivent rester attachés aux
nœuds qu'ils relient, export PPTX en formes natives à préserver). Nécessite une interview
dédiée sur le modèle d'interaction avant de coder. YAGNI: le drag de position couvre déjà
l'ajustement fin, la création/suppression reste rare et gérée par l'agent LLM.

**Origine:** Suggéré par l'utilisateur (session du 2026-08-10, hors interview de spec).
Contexte technique: `specs/2026-08-07_16-31-00-mcp-htmleditor-retrospective.md` (section 3.1,
composants avancés), règles dans `skill/types/arch-diagram.md`.

---

## BACKLOG-003: Hardening de l'export PPTX

**Description:** Renforcer la robustesse et la fidélité de `export/to_pptx.py` au-delà
des diagnostics non bloquants déjà en place (image manquante/distante, SVG non supporté,
absence de slide). Pistes à creuser dans une interview dédiée: limites de taille de
fichier/nombre de slides testées, comportement sur polices non installées côté serveur
d'export, fidélité des dégradés CSS complexes, gestion des z-index/superpositions,
tests de non-régression visuelle automatisés (actuellement seulement documentés comme
procédure manuelle dans `.agent_docs/testing.md`, jamais en CI), et couverture des
templates de référence qui n'ont pas encore de garde-fous équivalents (cf. TBD-011 de la
spec rétrospective: `ibm-carbon.html`, `example-*-complete.html`, etc.).

**Rationale du report:** "Hardening" est un thème, pas encore un ensemble de FR: il faut
une interview pour transformer chaque piste en exigence testable (EARS) avec des tests
E2E dédiés, plutôt que de coder au fil de l'eau. Pas de CI existante (voir NFR 7.6 de la
spec rétrospective) — le hardening doit aussi statuer sur ce point avant de produire des
tests de non-régression visuelle fiables.

**Origine:** Suggéré par l'utilisateur (session du 2026-08-10, hors interview de spec).
Contexte technique: `specs/2026-08-07_16-31-00-mcp-htmleditor-retrospective.md` FR-013/
FR-014 (export PPTX et diagnostics non bloquants), section 12.1 (gaps E2E identifiés),
`.agent_docs/testing.md` (procédure de validation manuelle, regression set de slide counts).
