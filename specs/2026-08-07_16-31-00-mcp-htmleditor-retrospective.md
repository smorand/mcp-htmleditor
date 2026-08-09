# mcp-htmleditor — Specification Document

> Generated on: 2026-08-07 16:31:00 +0200 (date du premier commit du dépôt)
> Project: mcp-htmleditor
> Version: 1.0
> Status: Draft (rétrospectif)
> Type: Retrospective Specification (reverse-engineered from the existing codebase, docs, tests and git history — no live interview was conducted; this document reconstructs the specification a project-spec interview would have produced, as if written the day the repo was bootstrapped, then annotated with how the build actually evolved)

## 1. Executive Summary

`mcp-htmleditor` est un éditeur WYSIWYG de fichiers HTML piloté par agent LLM, doublé d'un serveur MCP. Un agent (Claude, Cursor, Pi, ...) écrit un fichier HTML unique sur disque en respectant des conventions strictes (`data-doc-type`, `data-type="slide"`, `data-id`, `data-title`, headings sémantiques `h1`-`h5`); un serveur HTTP local sert ce fichier dans un `<iframe>` du navigateur et recharge le rendu quand le `mtime` change. L'humain peut éditer visuellement dans le navigateur (rich-text, images, tableaux, drag-reorder) et le fichier est nettoyé de tout artefact d'édition avant chaque sauvegarde. Le produit exporte le document en PPTX natif (16:9, formes/graphes/tableaux natifs) ou en DOCX (via pandoc, avec chartes graphiques reproduites: en-têtes/pieds de page, styles de titres, couleurs).

Cible: usage personnel/outillage IA (le compte git est `sebastien.morand@ibm.com`, dépôt `~/projects/perso/`), pour produire rapidement des présentations et documents à la charte Euro-Information ou IBM Carbon (ou une charte générique/perso) sans passer par PowerPoint/Word manuellement — l'agent LLM porte la création de contenu, l'humain valide et retouche visuellement, l'export produit le livrable final.

Construit en 2 jours (25 commits, 2026-08-07 16:31 → 2026-08-09 21:08), par un seul auteur, sans ticket ni interview formelle: les décisions ont été prises et documentées à même le code et les commits. Cette spécification reconstitue a posteriori le périmètre, les scénarios, les exigences et une suite de tests E2E alignée sur le contrat réellement implémenté (et testé unitairement — 146 cas dans 13 fichiers, aucun test end-to-end MCP/navigateur n'existe à ce jour).

## 3. Scope

### 3.1 In Scope

- CLI (`mcp-htmleditor`) avec commandes: `templates` (lister les chartes), `new <key> <file>` (créer depuis un bootstrap), `serve <file>` (lancer le serveur HTTP + navigateur), `mcp` (serveur MCP stdio), `export pptx|docx <in.html> <out>`, `skill` (dump du contenu de skill Pi).
- Serveur HTTP local (Starlette/uvicorn-like, `http_server.py`) qui sert le fichier HTML, le nettoie des artefacts d'édition avant sauvegarde, expose `/status`, `/health`, `/content`, `/export/pptx`, `/export/docx`, les assets statiques.
- Serveur MCP (FastMCP, stdio) avec 6 outils: `start_server`, `stop_server`, `get_status`, `open_file`, `update_start`, `update_end`.
- Deux modes de document: **présentation** (slides 16:9) et **document** (Word-like, A4 continu).
- 5 chartes/templates bootstrap: `ei` (Euro-Information, slides), `carbon` (IBM Carbon, slides), `doc` (générique, document), `doc-perso` (charte perso, document), `doc-ei` (Euro-Information, document). Chacune avec un template de référence riche en exemple.
- Éditeur frontend navigateur en JS vanilla sans build step: toolbar rich-text, insertion image/tableau, drag-reorder de blocs/slides, déplacement de nœuds de schéma d'architecture (`data-x`/`data-y`), mode plein écran type PowerPoint, indicateur d'état de sauvegarde, boutons export PPTX/DOCX intégrés à la toolbar.
- Composants de contenu avancés dans les slides: tuiles (`cds-grid`/`cds-tile`), tableaux (fusion colspan/rowspan), diagrammes de Gantt (`data-type="gantt"`), schémas d'architecture (`arch-diagram`/`arch-node`/`arch-edge`), images annotées (`annotated-image`/`annotation`), notifications, stat cards.
- Export PPTX natif via `python-pptx`: détection de slides, géométrie 16:9, formes natives pour Gantt/schémas/tableaux, images base64 ou relatives embarquées, fidélité de charte (EI, Carbon).
- Export DOCX via `pandoc` + `reference.docx` généré et caché par charte: déduplication de titre, en-têtes/pieds de page (letterhead Word) pour les chartes EI/Perso, styles de titres H1-H5 colorés, diagnostics SVG (non supporté, recommande PNG).
- État serveur persistant (`state.py`, fichier `.mcp_state.json` à côté du HTML édité): fichier courant, port, pid, mtime, flag `update_in_progress`.
- Configuration exclusivement via `pydantic-settings` (préfixe `HTMLEDITOR_*`), XDG-compliant (`~/.config`, `~/.cache`).
- Observabilité: logs Rich sur stderr + fichier rotatif, tracing OpenTelemetry (JSONL local par défaut, export OTLP/HTTP optionnel).
- Documentation: README, AGENTS.md, `.agent_docs/*.md` (architecture, docker, html-conventions, makefile, observability, python, testing), skill Pi complète (`skill/SKILL.md` + `workflow-*.md` + `types/*.md`) et skill dynamique légère (`dynamic-skills/html-editor/SKILL.md`) pour le routage.
- Packaging: `uv tool install`, Docker multi-stage (image `python:3.13-slim` + pandoc), `docker-compose.yml`/`docker-compose.prod.yml`.
- Qualité: `make check` (ruff lint+format, mypy strict, bandit, pytest-cov ≥ 80%), hooks pre-commit locaux.

### 3.2 Out of Scope (Non-Goals)

- Pas de CI centralisée (ni GitHub Actions ni GitLab CI) — la qualité repose sur `make check` en pré-commit local, à la discipline du développeur.
- Pas d'authentification/autorisation: le serveur HTTP/MCP est prévu pour un usage local mono-utilisateur (`localhost` par défaut), aucune notion de compte, session ou rôle.
- Pas de résolution de conflit d'édition concurrente: la règle produit est "la dernière modification humaine trouvée sur disque est volontaire, jamais écrasée sans le demander" — il n'y a pas de verrouillage, de merge, ni de détection de conflit réelle au-delà de ce principe déclaratif.
- Pas de support SVG à l'export DOCX/PPTX (diagnostiqué comme warning, recommandation de convertir en PNG) — c'est une limitation connue, pas un objectif.
- Pas d'éditeur "canvas" façon GrapesJS: ce choix a été fait puis abandonné dès le commit 3 (`fix: replace GrapesJS with iframe renderer`) au profit d'un rendu HTML natif fidèle en `<iframe>`.
- Pas de base de données, pas de multi-fichiers/projet: un agent édite un fichier HTML à la fois (`open_file` bascule mais ne gère pas plusieurs fichiers simultanément côté état).
- Pas de tests end-to-end automatisés du flux MCP complet ni du navigateur (GrapesJS/Playwright) — uniquement recommandé en documentation (`skill/workflow-create.md`: "validation visuelle obligatoire"), non outillé en CI.
- Pas de déploiement multi-tenant/cloud managé documenté au-delà d'un `docker-compose` mono-instance — pas de section infra IBM Cloud/AWS/Scaleway/GCP puisque c'est un usage personnel local ou conteneurisé simple.
- Pas de watsonx, pas d'authentification OIDC, pas de secret manager — projet personnel sans exigence de conformité client.

## 4. User Personas & Actors

| Acteur | Rôle | Interface |
|---|---|---|
| **Agent LLM** | Crée/modifie le fichier HTML sur disque selon les conventions imposées, pilote le serveur via les 6 outils MCP, déclenche les exports, doit valider visuellement son rendu | MCP (stdio) + lecture/écriture directe du fichier + CLI `export` |
| **Utilisateur humain (éditeur visuel)** | Retouche le contenu dans le navigateur: texte (rich-text), images (upload/déplacement/redimension), tableaux, réordonnancement de slides/blocs, repositionnement de nœuds de schéma; déclenche l'export depuis la toolbar | Navigateur (iframe servi par le serveur HTTP) |
| **Consommateur final** | Récupère le livrable PPTX/DOCX exporté pour l'ouvrir dans PowerPoint/Word, le partager ou le présenter | Fichier exporté (hors périmètre applicatif direct) |

## 4.5 Bounded Contexts

Le projet est un contexte borné unique: pas de séparation de domaines métier distincts, un seul modèle mental (édition de document HTML + export).

| Contexte | Scope | Entités clés |
|---|---|---|
| **Éditeur de document** | Édition, synchronisation navigateur/disque, état serveur, configuration, observabilité, export vers formats bureautiques | `EditorState` (état serveur), `Settings` (config), `Document HTML` (source de vérité), `Template`/`Charter` (registre de chartes), `PPTX export` / `DOCX export` (pipelines de sortie) |

## 5. Usage Scenarios

Scénarios reconstruits à partir du contrat réellement implémenté (README, skill, tests, historique git).

### SC-001: Créer une nouvelle présentation depuis un template
**Actor:** Agent LLM
**Preconditions:** Aucun fichier HTML existant à ce chemin; charte cible connue (`ei` ou `carbon`).
**Flow:**
1. L'agent exécute `mcp-htmleditor new ei pres.html` (ou `carbon`).
2. Le CLI résout la charte via `templates.py`, copie le bootstrap (`slides-ei-empty.html` ou `slides-empty.html`) vers `pres.html`.
3. (Optionnel) `--serve`: le CLI lance aussi le serveur HTTP et ouvre le navigateur.
4. L'agent démarre le serveur MCP (`mcp-htmleditor mcp`), appelle `start_server(file="pres.html")`.
**Postconditions:** `pres.html` existe avec 1 slide titre à la charte demandée; `EditorState` persiste le fichier courant, le port, le pid dans `.mcp_state.json`.
**Exceptions:**
- [EXC-001a] Clé de template inconnue → le CLI lève une erreur claire (`KeyError` intercepté), aucun fichier créé.
- [EXC-001b] Fichier destination déjà existant → écrasement silencieux actuel (pas de confirmation) — comportement à documenter/durcir (voir Section 15).
**Cross-scenario notes:** Sert de précondition à SC-002 (édition LLM) et SC-004 (export).

### SC-002: L'agent LLM modifie le contenu du fichier (workflow d'écriture encadré)
**Actor:** Agent LLM
**Preconditions:** Serveur MCP démarré, `get_status().running == true`, fichier HTML existant et chargé.
**Flow:**
1. L'agent appelle `update_start()` → `EditorState.set_update_flag(true)`, persisté sur disque; le navigateur affiche un overlay "modification en cours" et gèle son polling de rechargement.
2. L'agent réécrit le fichier HTML complet (DOCTYPE + head + body), en conservant `data-type="slide"`, `data-id`, `data-title` sur chaque slide, et `data-editable="text"` sur les zones destinées à l'édition humaine.
3. L'agent appelle `update_end()` → flag baissé, persisté.
4. Le navigateur détecte (polling `/status`, mtime changé) que l'update est terminée et recharge le contenu depuis le fichier.
**Postconditions:** Le fichier sur disque reflète la nouvelle version; le navigateur affiche le contenu à jour sans avoir rechargé pendant l'écriture partielle.
**Exceptions:**
- [EXC-002a] L'agent oublie `update_start()`/`update_end()` → le navigateur peut recharger un fichier à moitié écrit (contenu tronqué/invalide) ou ne jamais détecter le changement si le mtime ne varie pas assez vite; aucun garde-fou serveur ne force l'encadrement (règle documentaire, pas technique).
- [EXC-002b] L'agent écrit un HTML qui casse la structure attendue (supprime `data-id`) → aucune validation serveur, la casse se répercute sur navigation JS et export (échec silencieux ou partiel).
**Cross-scenario notes:** Peut entrer en conflit avec SC-003 si l'humain édite en même temps côté navigateur — non résolu techniquement, seulement par convention ("modification humaine trouvée = volontaire, ne jamais écraser sans demander").

### SC-003: L'humain édite visuellement dans le navigateur
**Actor:** Utilisateur humain
**Preconditions:** Serveur HTTP démarré, page ouverte dans le navigateur, `update_in_progress == false`.
**Flow:**
1. L'utilisateur clique une zone `data-editable="text"` → toolbar rich-text apparaît (gras, italique, couleurs, liens, insertion image/tableau).
2. L'utilisateur modifie le texte, insère une image (upload local encodé base64 ou drag-drop) ou un tableau, réordonne un bloc/une slide par drag handle, déplace un nœud de schéma d'architecture (`data-x`/`data-y`).
3. À la sauvegarde (auto ou déclenchée), le serveur HTTP nettoie le fichier reçu (retire `_mcp_*`, `contenteditable`, poignées de drag, options dupliquées du sélecteur de slides, attributs d'extension navigateur) puis l'écrit sur disque.
4. Le fichier sur disque est renuméroté automatiquement (id, data-id séquentiels, compteurs `Slide N/TT`, dropdown de navigation régénéré) si une slide a été ajoutée/supprimée.
**Postconditions:** Le fichier disque est propre (aucun artefact d'édition), à jour, cohérent (numérotation, dropdown).
**Exceptions:**
- [EXC-003a] Sauvegarde vers un chemin sous `templates/` (bootstrap ou reference) → refusée par le serveur (lecture seule).
- [EXC-003b] Image insérée trop volumineuse ou non supportée → pas de garde documentée (gap identifié, Section 15).
- [EXC-003c] Tentative de modification pendant `update_in_progress == true` → l'overlay bloque visuellement l'édition côté UI, mais aucun verrou serveur empêchant un POST concurrent n'est documenté dans les tests.
**Cross-scenario notes:** Interagit avec SC-002 (conflit potentiel LLM/humain) et déclenche indirectement SC-004/SC-005 via les boutons export de la toolbar.

### SC-004: Exporter en PPTX
**Actor:** Agent LLM ou Utilisateur humain
**Preconditions:** Fichier HTML au format présentation (`data-doc-type="presentation"`), au moins une slide `data-type="slide"`.
**Flow:**
1. Déclenchement via CLI (`mcp-htmleditor export pptx in.html out.pptx`) ou via la route HTTP `/export/pptx` (bouton toolbar).
2. `to_pptx.py` détecte les slides, résout la charte (EI/Carbon/générique) via CSS, construit chaque diapositive en 16:9 avec formes natives pour Gantt/schémas/tableaux/images, embarque les images base64 ou résolues en chemin relatif au HTML.
3. Le fichier PPTX est écrit ou streamé en téléchargement.
**Postconditions:** Fichier `.pptx` valide, ouvrable dans PowerPoint, avec la géométrie et le style attendus.
**Exceptions:**
- [EXC-004a] Aucune slide détectée → warning émis, le contenu brut est tout de même exporté en une diapositive de secours plutôt qu'un échec (`test_document_without_slides_warns_and_keeps_content`).
- [EXC-004b] Image manquante ou distante (URL http) → warning ajouté à la liste de diagnostics, l'export continue sans cette image.
- [EXC-004c] SVG détecté → warning "PNG recommandé", pas de blocage.
**Cross-scenario notes:** Peut être appelé juste après SC-002/SC-003 sans étape intermédiaire.

### SC-005: Exporter en DOCX
**Actor:** Agent LLM ou Utilisateur humain
**Preconditions:** Fichier HTML au format document (`data-doc-type="document"`), pandoc installé sur le système.
**Flow:**
1. Déclenchement via CLI (`mcp-htmleditor export docx in.html out.docx`) ou route HTTP `/export/docx`.
2. `to_docx.py` prétraite le HTML: extrait `.doc-title`/`.doc-subtitle` en métadonnées pandoc, détecte la charte via `data-doc-template`.
3. Si la charte a un letterhead connu (EI, Perso): génère/récupère en cache un `reference.docx` patché (styles.xml + document.xml: polices, couleurs, en-têtes/pieds répétés, champ `PAGE` dynamique).
4. Appelle `pandoc` avec `--reference-doc` (si applicable) pour produire le DOCX final.
**Postconditions:** Fichier `.docx` avec un titre unique (pas de doublon Title/Heading1), styles de charte appliqués, en-tête/pied de page répétés si la charte le prévoit.
**Exceptions:**
- [EXC-005a] Pandoc absent du système → capturé, retombe sur les styles pandoc par défaut avec warning, pas d'exception non gérée.
- [EXC-005b] Charte inconnue (`data-doc-template` non reconnu) → fallback pandoc par défaut + warning.
- [EXC-005c] Référence DOCX non construite (échec de génération) → warning + pandoc par défaut.
- [EXC-005d] Figures SVG présentes → warning diagnostiqué (PNG recommandé), export non bloqué.
**Cross-scenario notes:** Le cache de `reference.docx` (par charte) est partagé entre exports successifs — un second export de la même charte réutilise le cache (`test_reference_docx_for_generates_and_caches`).

### SC-006: Créer un document (mode Word-like) depuis un template
**Actor:** Agent LLM
**Preconditions:** Aucun fichier existant à ce chemin; charte cible connue (`doc`, `doc-perso`, `doc-ei`).
**Flow:**
1. `mcp-htmleditor new doc-ei rapport.html` copie `document-ei-empty.html`.
2. Le fichier contient un titre, un en-tête de charte (si EI: filet bleu + logo), un paragraphe d'exemple.
3. L'agent enrichit ensuite le contenu (headings sémantiques h1-h5, tableaux avec `<colgroup>`, figures PNG) selon `skill/types/document.md`.
**Postconditions:** Document HTML structuré, prêt à être édité puis exporté (SC-005).
**Exceptions:**
- [EXC-006a] Clé de template inconnue → `KeyError`, message d'erreur clair, aucun fichier créé.
**Cross-scenario notes:** Symétrique de SC-001 pour le mode document.

### SC-007: Démarrer/arrêter/interroger le serveur (opérations MCP de contrôle)
**Actor:** Agent LLM
**Preconditions:** Aucune (ou serveur déjà démarré pour `stop_server`/`get_status`).
**Flow:**
1. `start_server(file, port=7842)`: si aucun serveur ne tourne déjà sur ce port pour ce fichier, démarre le serveur HTTP, ouvre le navigateur (sauf `--no-browser`), persiste l'état.
2. `get_status()`: retourne fichier courant, port, pid, mtime, `update_in_progress`, `running`.
3. `open_file(file)`: bascule le fichier servi, force le rechargement navigateur immédiat.
4. `stop_server()`: arrête le serveur HTTP, libère le port.
**Postconditions:** État serveur cohérent avec la réalité du process (pid, port, fichier).
**Exceptions:**
- [EXC-007a] `start_server` appelé alors qu'un serveur tourne déjà sur le même port → doit être idempotent/no-op documenté (README), mais aucun test automatisé ne le vérifie (gap).
- [EXC-007b] Port déjà occupé par un autre process → pas de comportement de repli documenté/testé (gap).
**Cross-scenario notes:** Précondition de tous les autres scénarios côté agent.

### SC-008: Présenter une slide en plein écran depuis le navigateur
**Actor:** Utilisateur humain
**Preconditions:** Fichier au format présentation (`data-doc-type="presentation"`) chargé et affiché dans le navigateur, au moins une slide active.
**Flow:**
1. L'utilisateur clique le bouton "Mode présentation plein écran" de la toolbar shell (`#present-btn`), ou appuie sur la touche `f`/`F` alors que le focus est dans le document de la slide.
2. Le système met en plein écran natif (Fullscreen API) le **document interne de l'iframe** (pas l'élément `<iframe>` lui-même), pour que le CSS `:fullscreen` du template (masquage toolbar/flèches, slide 100vh sans padding, fond noir) s'applique dans le bon document.
3. Le système bascule le focus clavier sur l'iframe pour que les raccourcis de navigation de la slide (flèches, espace, Home, End, Echap) fonctionnent.
4. L'utilisateur navigue avec les flèches (←/→/↑/↓), la barre d'espace, `Home`/`End`, indépendamment de l'élément qui détient réellement le focus clavier côté navigateur.
5. L'utilisateur quitte le plein écran avec `Echap` ou en ré-appuyant sur le bouton présentation.
**Postconditions:** La slide occupe 100% de l'écran sans aucune barre d'interface visible; la navigation clavier fonctionne de bout en bout comme dans un vrai logiciel de présentation (PowerPoint/Keynote); la sortie du plein écran restaure l'affichage normal (toolbar, flèches, padding).
**Exceptions:**
- [EXC-008a] L'iframe de rendu est en `sandbox` sans le jeton `allow-fullscreen` → l'API Fullscreen refuse la requête sur le document interne; le système retombe sur la mise en plein écran de l'élément `<iframe>` côté document parent, ce qui **casse silencieusement** le contrat: le CSS `:fullscreen` du template ne s'applique plus (document différent), la toolbar/les flèches restent visibles et la slide garde sa taille/padding normaux. **Bug réel rencontré et corrigé** (voir DEC-011): le `sandbox` doit inclure explicitement `allow-fullscreen` (+ `allow="fullscreen"`/`allowfullscreen` pour compatibilité).
- [EXC-008b] Le focus clavier ne bascule pas automatiquement dans l'iframe à l'entrée en plein écran (`requestFullscreen()` ne déplace pas le focus) → les touches flèches ne sont capturées par aucun gestionnaire et la présentation reste bloquée sur la première slide. **Bug réel rencontré et corrigé** (voir DEC-011): `frame.focus()` après l'obtention du plein écran, plus un relais de touches (`document` parent → `navigate()`/`goToSlide()` de l'iframe) tant que `document.fullscreenElement` est actif, quel que soit l'élément qui détient réellement le focus.
- [EXC-008c] Aucune slide active au moment du passage en plein écran (deck vide) → comportement non spécifié, non testé (gap, voir TBD-009).
**Cross-scenario notes:** Peut être déclenché à tout moment pendant SC-003 (édition navigateur); sortir du plein écran ne doit pas perdre la position de navigation (slide courante conservée).

## 6. Functional Requirements

### FR-001 [EARS-E]: Création de document depuis un template
> WHEN l'agent exécute `mcp-htmleditor new <key> <file>` THE système SHALL copier le fichier bootstrap correspondant à `<key>` (`ei`, `carbon`, `doc`, `doc-perso`, `doc-ei`) vers `<file>`.

- **Inputs:** Clé de template (string), chemin de fichier destination.
- **Outputs:** Fichier HTML créé, contenu initial de la charte demandée.
- **Business Rules:** Les 5 clés sont fixes et résolues par `templates.py`; une clé inconnue est un échec (voir FR-002).
- **Priority:** Must-have

### FR-002 [EARS-O]: Rejet des clés de template inconnues
> IF la clé de template n'existe pas dans le registre THEN THE système SHALL lever une erreur explicite et NE SHALL PAS créer de fichier.

- **Inputs:** Clé de template invalide.
- **Outputs:** `KeyError` intercepté / message CLI clair.
- **Business Rules:** Le registre de templates est la source unique de vérité (`TEMPLATES` dict dans `templates.py`).
- **Priority:** Must-have

### FR-003 [EARS-U]: Serveur HTTP de rendu et synchronisation
> The système SHALL servir le fichier HTML courant dans un navigateur via un serveur HTTP local et recharger automatiquement le rendu quand le `mtime` du fichier change.

- **Inputs:** Fichier HTML courant, intervalle de polling (`HTMLEDITOR_POLL_INTERVAL`, défaut 1000ms).
- **Outputs:** Rendu HTML à jour dans l'iframe navigateur.
- **Business Rules:** Le polling interroge `/status`; pas de WebSocket/SSE.
- **Priority:** Must-have

### FR-004 [EARS-E]: Encadrement des écritures agent par update_start/update_end
> WHEN l'agent appelle `update_start()` THE système SHALL lever le flag `update_in_progress`, afficher un overlay de blocage côté navigateur et geler le rechargement automatique jusqu'à `update_end()`.

- **Inputs:** Aucun paramètre.
- **Outputs:** Flag persistant `update_in_progress=true` dans `.mcp_state.json`; overlay visible.
- **Business Rules:** Le flag est lu par le navigateur via polling `/status`; `update_end()` inverse l'effet.
- **Priority:** Must-have
- **Rationale:** Évite qu'un navigateur recharge un fichier en cours d'écriture partielle par l'agent.

### FR-005 [EARS-E]: Nettoyage des artefacts d'édition avant sauvegarde
> WHEN le serveur HTTP reçoit une sauvegarde depuis le navigateur THE système SHALL retirer du HTML tout artefact d'édition (`_mcp_*` id/classes, `contenteditable`, poignées de drag, attributs d'extension navigateur type `data-gramm`, options dupliquées du sélecteur de slides) avant d'écrire sur disque.

- **Inputs:** HTML brut reçu du navigateur (avec artefacts DOM d'édition).
- **Outputs:** HTML propre écrit sur disque.
- **Business Rules:** Liste fermée d'attributs/classes/ids à retirer (voir `.agent_docs/html-conventions.md` et `http_server.py`).
- **Priority:** Must-have

### FR-006 [EARS-U]: Reconstruction d'un document complet à partir d'un fragment
> The système SHALL reconstruire un document HTML complet (DOCTYPE + head + body) si le contenu reçu est un fragment, en préservant le `<head>` existant, `lang`, et `data-doc-type`.

- **Inputs:** Fragment ou document HTML complet.
- **Outputs:** Document HTML valide et complet.
- **Business Rules:** Si aucun `<head>` n'existe, un head minimal UTF-8 est généré.
- **Priority:** Must-have

### FR-007 [EARS-UB]: Protection en lecture seule des templates
> The système SHALL NOT accepter une sauvegarde de fichier dont le chemin cible se trouve sous le répertoire `templates/` (bootstrap ou reference).

- **Inputs:** Chemin de destination d'une sauvegarde.
- **Outputs:** Sauvegarde rejetée si le chemin est protégé.
- **Business Rules:** Empêche la divergence involontaire entre les templates versionnés et une édition accidentelle en session.
- **Priority:** Must-have

### FR-008 [EARS-E]: Renumérotation automatique des slides
> WHEN une slide est ajoutée ou supprimée via l'éditeur navigateur THE système SHALL renuméroter séquentiellement `id`/`data-id` (`slide-0`, `slide-1`, ...), régénérer le dropdown de navigation, et mettre à jour les compteurs `Slide N/TT` des deux chartes.

- **Inputs:** Liste de slides après insertion/suppression.
- **Outputs:** Attributs et compteurs cohérents.
- **Business Rules:** Numérotation 0-indexée.
- **Priority:** Must-have

### FR-009 [EARS-U]: Six outils MCP de contrôle
> The serveur MCP SHALL exposer exactement les outils `start_server`, `stop_server`, `get_status`, `open_file`, `update_start`, `update_end` via le protocole MCP (transport stdio).

- **Inputs:** Paramètres par outil (`file`, `port` optionnel pour `start_server`; `file` pour `open_file`).
- **Outputs:** Effets serveur + réponse structurée (statut, chemin, port, pid, mtime, running).
- **Business Rules:** `get_status` ne doit jamais lever d'exception, même sans fichier chargé.
- **Priority:** Must-have

### FR-010 [EARS-U]: Persistance de l'état serveur
> The système SHALL persister l'état serveur (fichier courant, port, pid, `update_in_progress`) dans un fichier `.mcp_state.json` situé à côté du fichier HTML édité, et le recharger à l'initialisation.

- **Inputs:** Mutations d'état (`set_file`, `set_update_flag`).
- **Outputs:** Fichier `.mcp_state.json` à jour.
- **Business Rules:** `EditorState` est un singleton mémoire; le chargement d'un JSON corrompu est ignoré silencieusement (pas d'exception).
- **Priority:** Must-have

### FR-011 [EARS-U]: Deux modes de document
> The système SHALL supporter exactement deux modes de document déterminés par l'attribut `data-doc-type` sur `<html>`: `"presentation"` (slides 16:9) et `"document"` (Word-like continu).

- **Inputs:** Attribut `data-doc-type`.
- **Outputs:** Comportement d'édition et de navigation adapté au mode.
- **Business Rules:** Le mode conditionne aussi le pipeline d'export applicable (PPTX pour presentation, DOCX pour document).
- **Priority:** Must-have

### FR-012 [EARS-U]: Cinq chartes graphiques disponibles
> The système SHALL fournir exactement 5 chartes prêtes à l'emploi: `ei` et `carbon` (mode présentation), `doc`, `doc-perso`, `doc-ei` (mode document), chacune avec un template bootstrap minimal et un template de référence riche.

- **Inputs:** Aucun (registre statique).
- **Outputs:** Fichiers de templates disponibles via `mcp-htmleditor templates`/`new`.
- **Business Rules:** Le bootstrap EI (`slides-ei-empty.html`) est généré depuis la référence (`euro-information.html`) par `make bootstrap-ei` / `tools/gen_ei_bootstrap.py` — il ne doit jamais être édité manuellement.
- **Priority:** Must-have

### FR-013 [EARS-E]: Export PPTX natif
> WHEN l'export PPTX est déclenché (CLI ou route HTTP) THE système SHALL produire un fichier `.pptx` en géométrie 16:9 avec une diapositive par élément `data-type="slide"` (ou fallback `class="slide"`), en rendant Gantt/schémas d'architecture/tableaux fusionnés/images comme des formes ou objets natifs PPTX.

- **Inputs:** Fichier HTML au format présentation.
- **Outputs:** Fichier `.pptx`.
- **Business Rules:** `<script>`, `<style>`, `.shell-header` jamais exportés. Slides imbriquées ignorées.
- **Priority:** Must-have

### FR-014 [EARS-O]: Diagnostics d'export PPTX non bloquants
> IF une image est manquante, distante (URL http), ou si aucune slide n'est détectée THEN THE système SHALL émettre un warning dans la liste de diagnostics et continuer l'export plutôt que d'échouer.

- **Inputs:** Contenu HTML incomplet ou avec ressources externes.
- **Outputs:** Fichier `.pptx` produit + liste de warnings.
- **Business Rules:** Aucune exception ne doit interrompre un export tant qu'un fallback de contenu existe.
- **Priority:** Should-have (documenté comme comportement voulu, testé)

### FR-015 [EARS-E]: Export DOCX via pandoc avec charte
> WHEN l'export DOCX est déclenché sur un document avec `data-doc-template` reconnu (`perso`, `ei`) THE système SHALL générer ou réutiliser un `reference.docx` en cache reproduisant la charte (polices, couleurs, en-tête/pied de page) et l'utiliser avec `pandoc --reference-doc` pour produire le fichier final.

- **Inputs:** Fichier HTML document, charte détectée.
- **Outputs:** Fichier `.docx` avec titre unique et styles de charte.
- **Business Rules:** Le cache de `reference.docx` est indexé par charte, réutilisé entre exports successifs.
- **Priority:** Must-have

### FR-016 [EARS-O]: Fallback DOCX sans charte ou sans pandoc
> IF pandoc est absent du système OU si la charte est inconnue OU si le `reference.docx` n'a pas pu être construit THEN THE système SHALL produire un export avec les styles pandoc par défaut et ajouter un warning, SANS lever d'exception non gérée.

- **Inputs:** Environnement dégradé (pandoc absent, charte inconnue).
- **Outputs:** Fichier `.docx` produit avec styles par défaut + warning.
- **Business Rules:** Aucun cas ne doit faire planter l'export.
- **Priority:** Must-have

### FR-017 [EARS-UB]: Pas de doublon de titre à l'export DOCX
> The système SHALL NOT produire un DOCX où le titre du document apparaît deux fois (une fois en style Word "Title", une fois en "Heading1").

- **Inputs:** HTML avec `.doc-title` (et `.doc-subtitle` optionnel).
- **Outputs:** DOCX avec titre unique en style "Title" (+ "Subtitle" si présent).
- **Business Rules:** `.doc-title`/`.doc-subtitle` sont extraits en métadonnées pandoc et retirés du corps avant conversion.
- **Priority:** Must-have

### FR-018 [EARS-O]: Diagnostic SVG non supporté
> IF une figure au format SVG (fichier, data URI, ou balise inline) est détectée dans un export (PPTX ou DOCX) THEN THE système SHALL ajouter un warning recommandant un format PNG, SANS bloquer l'export.

- **Inputs:** Contenu HTML avec `<img>`/`<svg>` au format vectoriel.
- **Outputs:** Export produit + warning.
- **Business Rules:** Chaque occurrence SVG génère un warning distinct, dédupliqué si identique.
- **Priority:** Should-have

### FR-019 [EARS-U]: Configuration exclusivement par Settings
> The système SHALL lire toute sa configuration runtime (hôte, port, intervalle de polling, répertoires templates/logs/cache/bin, destination et clé OTel) exclusivement via la classe `Settings` (pydantic-settings, préfixe `HTMLEDITOR_*`), avec fallback XDG-compliant.

- **Inputs:** Variables d'environnement `HTMLEDITOR_*`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, fichier `.env`.
- **Outputs:** Instance `Settings` mémoïsée par signature d'environnement.
- **Business Rules:** Aucune lecture directe de `os.environ` ailleurs dans le code (convention documentée dans AGENTS.md).
- **Priority:** Must-have

### FR-020 [EARS-O]: Valeurs de configuration invalides retombent au défaut
> IF une variable d'environnement numérique (`HTMLEDITOR_PORT`, `HTMLEDITOR_POLL_INTERVAL`) est vide ou non entière THEN THE système SHALL retomber sur sa valeur par défaut (7842 pour le port, 1000 pour le polling) sans lever d'exception.

- **Inputs:** Variable d'environnement invalide.
- **Outputs:** Valeur par défaut appliquée.
- **Business Rules:** Aucune configuration invalide ne doit empêcher le démarrage.
- **Priority:** Must-have

### FR-021 [EARS-U]: Logging Rich + fichier rotatif
> The système SHALL journaliser sur deux canaux simultanés: console (stderr, formatage Rich, timestamp jamais omis même pour des lignes consécutives) et fichier rotatif (2 Mo, 3 backups) dans le répertoire de logs configuré.

- **Inputs:** Niveau de log résolu depuis les flags CLI (`-v`/`-q`).
- **Outputs:** Logs sur les deux canaux.
- **Business Rules:** `setup_logging()` est idempotent (n'ajoute pas de handlers en double); un répertoire de logs non-inscriptible dégrade vers console-only sans exception.
- **Priority:** Must-have

### FR-022 [EARS-U]: Tracing OpenTelemetry
> The système SHALL tracer les opérations MCP, HTTP et d'export via OpenTelemetry, avec export par défaut en JSONL local (un objet JSON par span terminé) et export OTLP/HTTP optionnel si `HTMLEDITOR_OTEL_DESTINATION` est configuré.

- **Inputs:** Spans créés via `trace_span("categorie.operation", {...})`.
- **Outputs:** Fichier `mcp-htmleditor-otel.log` (JSONL) ou export OTLP.
- **Business Rules:** Jamais de contenu de document, prompt LLM ou credential dans les attributs de span.
- **Priority:** Must-have

### FR-023 [EARS-UB]: Pas de contenu sensible dans les traces
> The système SHALL NOT inclure dans les attributs de trace: contenu du document HTML, prompts ou réponses LLM, credentials, tokens ou clés d'API.

- **Inputs:** N/A (contrainte de conception).
- **Outputs:** N/A.
- **Business Rules:** Seuls chemins, comptages, tailles, clés de charte, durées, codes/statuts sont autorisés en attributs.
- **Priority:** Must-have

### FR-024 [EARS-E]: Endpoint santé
> WHEN une requête GET est reçue sur `/health` THE système SHALL répondre avec le statut, la version, le chemin du fichier courant (ou null) et le port.

- **Inputs:** Requête HTTP GET.
- **Outputs:** JSON `{status, version, file, port}`.
- **Business Rules:** Doit répondre `status=ok` même sans fichier chargé.
- **Priority:** Must-have

### FR-025 [EARS-U]: Skill Pi packagée et exposée
> The système SHALL fournir le contenu complet de sa skill d'usage (conventions, workflows, types de composants) via la commande CLI `skill` et via une skill dynamique légère installée sous `~/.pi/agent/dynamic-skills/`.

- **Inputs:** Aucun.
- **Outputs:** Contenu Markdown assemblé (index + sous-documents).
- **Business Rules:** Zéro chevauchement de routage avec les skills d'export pptx/docx existantes (documenté dans `dynamic-skills/html-editor/SKILL.md`).
- **Priority:** Should-have

### FR-026 [EARS-E]: Mode présentation plein écran
> WHEN l'utilisateur déclenche le mode présentation (bouton `#present-btn` ou touche `f`/`F`) THE système SHALL mettre en plein écran natif le **document interne de l'iframe** (`frame.contentDocument.documentElement`), et non l'élément `<iframe>` lui-même.

- **Inputs:** Clic sur le bouton présentation, ou touche clavier `f`/`F`.
- **Outputs:** Le document de la slide passe en plein écran (Fullscreen API); `document.fullscreenElement` côté parent répond avec l'élément `<iframe>` (propagation standard entre navigateur imbriqué), et `frame.contentDocument.fullscreenElement` côté interne répond avec `<html>`.
- **Business Rules:** L'élément `<iframe id="content-frame">` DOIT déclarer `sandbox="... allow-fullscreen"` (+ `allow="fullscreen"`/`allowfullscreen`): sans ce jeton, l'API Fullscreen refuse la requête sur le document interne (comportement de navigateur standard pour un iframe sandboxé), et le fallback existant (plein écran de l'`<iframe>` côté parent) ne déclenche jamais le CSS `:fullscreen` du template puisqu'il vit dans un autre document.
- **Priority:** Must-have
- **Rationale:** Le CSS `:fullscreen .toolbar/.nav-arrow/.slide` qui masque la navigation et redimensionne la slide est écrit dans le `<style>` du template HTML lui-même (servi dans l'iframe), pas dans `editor.css` (document parent). Le pseudo-élément `:fullscreen` ne traverse jamais une frontière de document: il faut donc impérativement que ce soit le document interne qui passe effectivement en plein écran.

### FR-027 [EARS-U]: Habillage visuel du mode plein écran (zoom uniforme, pas un étirement)
> The système SHALL masquer, pendant le plein écran, la barre de navigation de la slide (sélecteur "Diapositive :", flèches précédent/suivant, compteur "N / TT") et agrandir la slide active de manière uniforme (transform scale, polices et composants compris) pour occuper au maximum la fenêtre sur fond noir, sans marge ni padding, sans déformer les proportions.

- **Inputs:** État `:fullscreen` du document interne; dimensions du viewport (`window.innerWidth`/`innerHeight`).
- **Outputs:** Slide seule, agrandie visuellement (texte, cartes, images compris) jusqu'à remplir l'écran en conservant le ratio 16:9, avec letterboxing sur l'axe contraint si le ratio de l'écran diffère — comportement équivalent à PowerPoint/Keynote en mode présentation.
- **Business Rules:** Règles CSS `:fullscreen .toolbar, :fullscreen .nav-arrow { display:none !important; }`, `:fullscreen .slide-frame { padding:0; }`, `:fullscreen body { background:#000; }` — présentes dans les templates `ei` et `carbon` (bootstrap et référence). La slide **conserve sa taille de conception native** (960×540, ratio 16:9) et reçoit `:fullscreen .slide { transform: scale(var(--fs-scale, 1)); transform-origin: center center; }`: `--fs-scale` est calculé en JS par `updateFullscreenScale()` (`Math.min(window.innerWidth/rect.width, window.innerHeight/rect.height)`, mesuré après réinitialisation à `1` pour obtenir la taille naturelle), appelé sur `fullscreenchange`, `resize`, et à chaque `render()` (changement de slide). **Corrigé après un premier essai bogué** qui étirait le conteneur (`width:100%; height:100vh`) sans agrandir le contenu — les polices/cartes en px restaient minuscules avec du vide autour, l'exact inverse de l'effet "zoom PowerPoint" recherché (voir DEC-012). Un filet de sécurité côté document parent (`editor.css`, sélecteur `body:has(#content-frame:fullscreen) #toolbar`) masque également la toolbar shell si jamais le fallback (plein écran de l'`<iframe>`) devait se produire malgré FR-026.
- **Priority:** Must-have

### FR-028 [EARS-U]: Navigation clavier indépendante du focus pendant le plein écran
> The système SHALL router les touches `ArrowRight`/`ArrowDown`/`Espace` (slide suivante), `ArrowLeft`/`ArrowUp` (slide précédente), `Home`/`End` (première/dernière slide) et `Echap` (quitter le plein écran) vers les fonctions de navigation de la slide (`navigate()`, `goToSlide()`) pendant tout le temps où `document.fullscreenElement` est actif, quel que soit l'élément DOM qui détient effectivement le focus clavier.

- **Inputs:** Événements `keydown` capturés soit par le document interne de l'iframe (gestionnaire natif du template), soit par le document parent (`editor.js`) si le focus n'a pas basculé dans l'iframe.
- **Outputs:** Changement de slide active, mise à jour du compteur et du dropdown; sortie du plein écran sur `Echap`.
- **Business Rules:** `editor.js` appelle `frame.focus()` juste après l'obtention du plein écran (et à chaque `fullscreenchange`) pour tenter de placer le focus dans l'iframe; en complément, un gestionnaire `keydown` sur le document PARENT relaie directement les touches vers `frame.contentWindow.navigate()`/`goToSlide()` tant que `document.fullscreenElement` est renseigné. Les événements clavier ne traversant jamais une frontière de document (pas de bulles entre iframe et parent), les deux mécanismes ne peuvent pas se déclencher en double sur un même appui de touche.
- **Priority:** Must-have
- **Rationale:** `requestFullscreen()` ne déplace jamais automatiquement le focus clavier vers le document mis en plein écran (comportement standard, non garanti identique entre navigateurs); sans ce relais, le clic initial sur `#present-btn` laisse le focus sur ce bouton (document parent) et aucune touche flèche n'atteint jamais le gestionnaire de navigation du template.

## 7. Non-Functional Requirements

### 7.1 Performance
- Le polling navigateur interroge `/status` toutes les `HTMLEDITOR_POLL_INTERVAL` ms (défaut 1000ms) — c'est un choix délibéré de simplicité plutôt que WebSocket/SSE. Pas d'exigence de latence formelle documentée; pas de test de charge pour de gros documents (100+ slides — gap identifié en Section 15).

### 7.2 Security
- Usage local mono-utilisateur, pas d'authentification (`HTMLEDITOR_HOST` par défaut `localhost`; `0.0.0.0` en conteneur Docker, exposant le service au réseau du host — à documenter comme risque si déployé au-delà d'un usage local).
- `bandit` exécuté systématiquement (`make security`), avec exceptions documentées et justifiées dans `pyproject.toml` pour l'appel `subprocess` à pandoc (args fixes, pas de shell, pas d'interpolation de contenu utilisateur) et pour le parsing XML des paquets Word générés localement.
- Secrets (clé OTel) exclusivement via variable d'environnement `HTMLEDITOR_OTEL_API_KEY`, jamais en dur; `.env` gitignoré, `.env.example` documenté.
- Aucune notion de rôle/permission: tout agent MCP connecté a un contrôle total du fichier servi.

### 7.3 Usability
- Toolbar rich-text minimaliste (24px, sans boutons de navigation redondants — ajusté au commit 5).
- Mode plein écran type PowerPoint pour la présentation des slides (ajouté commit 21-22, spécifié en FR-026 à FR-028 et SC-008; deux régressions réelles — toolbar visible en plein écran, navigation clavier inopérante — corrigées post-rétrospective, voir DEC-011).
- Indicateur visuel d'état de sauvegarde (point orange "en cours" → vert "sauvegardé"), sans rechargement de l'iframe sur ses propres sauvegardes (anti-flicker, commit 18).
- Pas d'exigence d'accessibilité (WCAG) documentée ni testée — gap.
- Pas d'internationalisation logicielle: seule la langue du contenu (`lang="fr"`) est gérée pour l'export pandoc; l'UI éditeur elle-même n'est pas testée en anglais.

### 7.4 Reliability
- Robustesse en échec systématiquement privilégiée sur l'échec dur: pandoc absent, JSON d'état corrompu, répertoire de logs non-inscriptible, charte inconnue, image manquante — tous ces cas dégradent gracieusement (warning/fallback) plutôt que de lever une exception, et sont couverts par des tests unitaires dédiés.
- Aucune sauvegarde/restauration de données au-delà du fichier HTML lui-même (pas de versionning applicatif, l'historique repose sur git si l'utilisateur l'active côté projet cible).
- Pas de stratégie de reprise après crash serveur documentée (`server_pid` persiste mais rien ne vérifie sa validité au redémarrage — gap).

### 7.5 Observability
- **Collector**: JSONL local par défaut (`~/.cache/mcp-htmleditor/logs/mcp-htmleditor-otel.log`); export OTLP/HTTP optionnel vers tout collecteur compatible (Jaeger, Tempo, etc.) via `HTMLEDITOR_OTEL_DESTINATION` + `HTMLEDITOR_OTEL_API_KEY` (Bearer).
- **Log applicatif**: `~/.cache/mcp-htmleditor/logs/mcp-htmleditor.log`, rotatif 2 Mo / 3 backups.
- **Spans mesurés**: `mcp.start_server`, `mcp.stop_server`, `mcp.get_status`, `mcp.open_file`, `mcp.update_start`/`update_end`, `export.pptx`, `export.docx`, `export.reference_docx`, `tool.pandoc`, `file.write` — chacun avec `duration_ms` et des attributs non-sensibles (chemins, comptages, tailles, statuts).
- **LLM tracing**: N/A — le projet n'appelle lui-même aucun LLM (c'est l'agent externe qui l'utilise en tant qu'outil).
- **Exclusion de données sensibles**: contenu HTML, prompts/réponses, credentials, tokens jamais tracés.

### 7.6 Deployment
- **Contexte projet**: personnel (`~/projects/perso/`), pas de contrainte client/compliance.
- **Cible principale**: exécution locale (`uv tool install`, CLI `mcp-htmleditor`).
- **Conteneurisation optionnelle**: Docker multi-stage (`python:3.13-slim` + pandoc), utilisateur non-root (uid 10001), health check sur `/health` (intervalle 30s), volumes `./data:/data` (documents) et `htmleditor-cache` (cache DOCX/logs), port `7842/tcp`. `docker-compose.yml` (dev) et `docker-compose.prod.yml` (overlay avec `APP_VERSION` injecté).
- **Pas de cloud managé** ni d'API gateway: hors périmètre pour un outil local/perso.
- **CI/CD**: absente. Qualité garantie par `make check` (lint + format-check + typecheck + security + test-cov ≥80%) exécuté localement, hooks pre-commit (`ruff`, `mypy`) sur commit.
- **Versionnage**: `src/mcp_htmleditor/version.py` reste `"dev"` en dépôt; `make build`/`make docker-build` l'écrasent temporairement avec `git describe --tags --always --dirty` puis restaurent `"dev"`. Pas de tag git existant à ce jour.

### 7.7 Scalability
- Pas d'exigence de montée en charge: usage mono-agent, mono-fichier, local. Aucun test de volumétrie (documents à 100+ slides) — gap identifié.

## 8. Data Model

Pas de base de données. Les "entités" du système sont des structures en mémoire/disque:

| Entité | Support | Champs clés | Cycle de vie |
|---|---|---|---|
| **Document HTML** | Fichier `.html` sur disque (source de vérité unique) | `data-doc-type`, `<head>`, slides ou blocs de contenu | Créé par `new`, modifié par agent ou navigateur, lu par export |
| **EditorState** | Singleton mémoire + `.mcp_state.json` (colocalisé au HTML) | `current_file`, `port`, `server_pid`, `update_in_progress`, `mtime` | Initialisé au démarrage serveur, persisté à chaque mutation, rechargé au redémarrage |
| **Settings** | Instance pydantic mémoïsée par signature d'environnement | host, port, poll_interval, templates_dir, log_dir, cache_dir, bin_dir, otel_destination, otel_api_key | Recalculée si l'environnement change (tests: `reset_settings`) |
| **Template/Charter registry** | Dict statique (`templates.py`) | clé (`ei`, `carbon`, `doc`, `doc-perso`, `doc-ei`) → chemin bootstrap | Statique, ne change qu'au code |
| **reference.docx (cache)** | Fichier binaire caché par charte (`~/.cache/mcp-htmleditor/reference/`) | charte, styles.xml/document.xml patchés | Généré à la demande, réutilisé (cache-hit) tant que présent |
| **Export diagnostics** | Liste en mémoire, retournée à l'appelant | messages de warning (image manquante, SVG, charte inconnue...) | Éphémère, par appel d'export |

Relations: 1 Document HTML ↔ 1 EditorState (colocalisé) ↔ 0..1 fichier `.mcp_state.json`. 1 Document HTML référence 0..1 Template d'origine (perdu après création, pas de lien persistant). 1 export DOCX ↔ 0..1 reference.docx en cache (par charte, partagé entre documents).

## 10. Documentation Requirements

Déjà largement satisfait dans l'état actuel du repo — à maintenir:

### 10.1 README.md
Présent et à jour: pitch, installation, commandes CLI, outils MCP, templates, logs. À maintenir à chaque nouvelle commande/outil.

### 10.2 AGENTS.md & .agent_docs/
`AGENTS.md` racine sert d'index compact (overview, commandes, conventions essentielles, table de renvoi vers `.agent_docs/*.md`: python, makefile, architecture, observability, testing, docker, html-conventions). Modèle correctement appliqué et à perpétuer pour toute nouvelle fonctionnalité.

### 10.3 docs/skill
La skill complète (`skill/SKILL.md` + `workflow-*.md` + `types/*.md`) fait office de documentation utilisateur/agent pour les conventions de contenu (slides, documents, gantt, arch-diagram, annotated-image, tables). La skill dynamique légère (`dynamic-skills/html-editor/SKILL.md`) assure le routage sans chevauchement avec les skills d'export pptx/docx.

## 11. Traceability Matrix

| Scenario | Functional Req | E2E Tests (Happy) | E2E Tests (Failure) | E2E Tests (Edge) |
|---|---|---|---|---|
| SC-001 | FR-001, FR-002, FR-012 | E2E-001 | E2E-002 | E2E-003 |
| SC-002 | FR-004, FR-009, FR-010 | E2E-004 | E2E-005, E2E-006 | E2E-007 |
| SC-003 | FR-005, FR-006, FR-007, FR-008 | E2E-008 | E2E-009 | E2E-010, E2E-011 |
| SC-004 | FR-013, FR-014 | E2E-012 | E2E-013, E2E-014 | E2E-015 |
| SC-005 | FR-015, FR-016, FR-017, FR-018 | E2E-016 | E2E-017, E2E-018, E2E-019 | E2E-020 |
| SC-006 | FR-001, FR-002, FR-011, FR-012 | E2E-021 | E2E-022 | — |
| SC-007 | FR-009, FR-010, FR-024 | E2E-023 | E2E-024, E2E-025 | E2E-026 |
| SC-008 | FR-026, FR-027, FR-028 | E2E-038 | E2E-039, E2E-040 | E2E-041 |
| (transverse) | FR-019, FR-020 | E2E-027 | E2E-028, E2E-029 | E2E-030 |
| (transverse) | FR-021 | E2E-031 | E2E-032 | E2E-033 |
| (transverse) | FR-022, FR-023 | E2E-034 | E2E-035 | E2E-036 |
| (transverse) | FR-025 | E2E-037 | — | — |

## 12. End-to-End Test Suite

> Contrairement à une spécification greenfield, ces tests **existent déjà en grande partie** sous forme de tests unitaires/composant (146 cas, 13 fichiers `tests/test_*.py`, couverture ≥80%). La section ci-dessous les relie formellement aux scénarios/FR ci-dessus et **ajoute les tests end-to-end manquants** (MCP stdio, navigateur, workflow mixte) identifiés comme gaps par l'analyse (voir aussi Section 15).

### 12.1 Test Summary

| Test ID | Action | Category | Scenario | FR refs | Priority |
|---|---|---|---|---|---|
| E2E-001 | Existant (`test_templates.py::test_all_templates_resolve_to_existing_files`, `test_ei_template_is_euro_information`) | Happy | SC-001 | FR-001, FR-012 | Critical |
| E2E-002 | Nouveau | Failure | SC-001 | FR-002 | High |
| E2E-003 | Existant (`test_templates.py::test_unknown_key_raises_keyerror`) | Edge | SC-001 | FR-002 | Medium |
| E2E-004 | Nouveau (MCP e2e) | Happy | SC-002 | FR-004, FR-009 | Critical |
| E2E-005 | Nouveau (MCP e2e) | Failure | SC-002 | FR-004 | High |
| E2E-006 | Nouveau | Failure | SC-002 | FR-010 | High |
| E2E-007 | Existant (`test_state.py::test_load_corrupt_file_is_ignored`) | Edge | SC-002 | FR-010 | Medium |
| E2E-008 | Existant (`test_http_helpers.py::test_strip_removes_injected_ids`, et suite) | Happy | SC-003 | FR-005, FR-006 | Critical |
| E2E-009 | Nouveau | Failure | SC-003 | FR-007 | High |
| E2E-010 | Existant (`test_http_helpers.py::test_rebuild_default_head_when_missing`) | Edge | SC-003 | FR-006 | Medium |
| E2E-011 | Nouveau (browser e2e) | Edge | SC-003 | FR-008 | Medium |
| E2E-012 | Existant (`test_export_pptx.py::test_euro_information_template_exports_every_slide`) | Happy | SC-004 | FR-013 | Critical |
| E2E-013 | Existant (`test_export_pptx.py::test_missing_and_remote_images_are_reported`) | Failure | SC-004 | FR-014 | High |
| E2E-014 | Nouveau | Failure | SC-004 | FR-013 | High |
| E2E-015 | Existant (`test_export_pptx.py::test_document_without_slides_warns_and_keeps_content`) | Edge | SC-004 | FR-014 | Medium |
| E2E-016 | Existant (`test_export_docx.py::test_to_docx_carries_the_charter`) | Happy | SC-005 | FR-015 | Critical |
| E2E-017 | Existant (`test_export_docx.py::test_reference_docx_for_swallows_a_missing_pandoc`) | Failure | SC-005 | FR-016 | High |
| E2E-018 | Existant (`test_export_docx.py::test_to_docx_reports_an_unknown_charter`) | Failure | SC-005 | FR-016 | High |
| E2E-019 | Existant (`test_export_docx.py::test_to_docx_warns_about_svg_figures`) | Failure | SC-005 | FR-018 | Medium |
| E2E-020 | Existant (`test_export_docx.py::test_to_docx_writes_the_title_once`) | Edge | SC-005 | FR-017 | High |
| E2E-021 | Existant (`test_templates.py::test_doc_ei_template_is_document`) | Happy | SC-006 | FR-001, FR-011 | Critical |
| E2E-022 | Existant (`test_templates.py::test_unknown_key_raises_keyerror`) | Failure | SC-006 | FR-002 | Medium |
| E2E-023 | Nouveau (MCP e2e) | Happy | SC-007 | FR-009, FR-024 | Critical |
| E2E-024 | Nouveau (MCP e2e) | Failure | SC-007 | FR-009 | High |
| E2E-025 | Nouveau (MCP e2e) | Failure | SC-007 | FR-009 | High |
| E2E-026 | Existant (`test_http_health.py::test_health_reports_status_and_version`) | Edge | SC-007 | FR-024 | Medium |
| E2E-027 | Existant (`test_settings.py::test_settings_defaults`) | Happy | (transverse) | FR-019 | Critical |
| E2E-028 | Existant (`test_settings.py::test_invalid_poll_interval_falls_back`) | Failure | (transverse) | FR-020 | High |
| E2E-029 | Existant (`test_config.py::test_invalid_port_falls_back`) | Failure | (transverse) | FR-020 | High |
| E2E-030 | Existant (`test_settings.py::test_tilde_is_expanded_in_path_overrides`) | Edge | (transverse) | FR-019 | Medium |
| E2E-031 | Existant (`test_logging_config.py::test_setup_logging_installs_both_handlers`) | Happy | (transverse) | FR-021 | High |
| E2E-032 | Existant (`test_logging_config.py::test_unwritable_log_dir_keeps_the_console`) | Failure | (transverse) | FR-021 | High |
| E2E-033 | Existant (`test_logging_config.py::test_setup_logging_is_idempotent`) | Edge | (transverse) | FR-021 | Medium |
| E2E-034 | Existant (`test_tracing.py::test_configure_tracing_exports_spans`) | Happy | (transverse) | FR-022 | High |
| E2E-035 | Existant (`test_tracing.py::test_exporter_reports_failure_on_unwritable_path`) | Failure | (transverse) | FR-022 | Medium |
| E2E-036 | Nouveau (revue manuelle) | Edge | (transverse) | FR-023 | High |
| E2E-037 | Existant (`test_skill_content.py::test_build_skill_content_includes_index_and_subdocs`) | Happy | (transverse) | FR-025 | Low |
| E2E-038 | Nouveau (browser e2e) | Happy | SC-008 | FR-026, FR-027 | Critical |
| E2E-039 | Nouveau (régression, bug réel corrigé) | Failure | SC-008 | FR-026 | Critical |
| E2E-040 | Nouveau (régression, bug réel corrigé) | Failure | SC-008 | FR-028 | Critical |
| E2E-041 | Nouveau (browser e2e) | Edge | SC-008 | FR-028 | Medium |

**Coverage Statistics:**
- Happy path: 12 tests
- Failure/error: 15 tests
- Edge cases: 14 tests
- Happy:Failure ratio: 1:1.25 (failure ≥ happy, conforme à la règle)
- Tests existants réutilisés: 30 (déjà présents dans `tests/*.py`)
- Tests nouveaux à écrire: 11 (E2E-002, E2E-004 à E2E-006, E2E-009, E2E-011, E2E-014, E2E-023 à E2E-025, E2E-036, E2E-038 à E2E-041) — intégration MCP stdio, navigateur, et plein écran (E2E-038 à E2E-041, aucun test automatisé n'existait pour ce mode alors que deux régressions réelles s'y sont produites, cf. DEC-011).

### 12.2 New Test Specifications (gaps à combler en priorité)

#### E2E-004: Workflow MCP complet update_start → écriture → update_end
- **Category:** Core Journey
- **Scenario:** SC-002
- **Requirements:** FR-004, FR-009, FR-010
- **Preconditions:**
  - Serveur MCP démarré en stdio (`mcp-htmleditor mcp`), client MCP de test connecté.
  - Fichier `pres.html` créé via `new carbon` avec 1 slide `data-id="slide-0"`.
  - `start_server(file="pres.html")` déjà appelé, `get_status().running == true`.
- **Steps:**
  - Given le fichier `pres.html` contient une slide `data-title="Titre"`.
  - When le client MCP appelle `update_start()`.
  - Then la réponse confirme `update_in_progress=true` et `.mcp_state.json` contient `"update_in_progress": true`.
  - And le client réécrit `pres.html` avec une deuxième slide `data-id="slide-1"` `data-title="Contenu"`.
  - And le client MCP appelle `update_end()`.
  - Then `.mcp_state.json` contient `"update_in_progress": false`.
  - And `get_status()` retourne le `mtime` du fichier mis à jour.
- **Cleanup:** Arrêter le serveur MCP, supprimer `pres.html` et `.mcp_state.json`.
- **Priority:** Critical

#### E2E-005: Écriture sans encadrement update_start/update_end
- **Category:** Error
- **Scenario:** SC-002
- **Requirements:** FR-004
- **Preconditions:** Serveur HTTP démarré, navigateur simulé (client HTTP) en polling actif sur `/status`.
- **Steps:**
  - Given `update_in_progress=false` et un fichier `pres.html` valide.
  - When un script externe écrit `pres.html` avec un contenu HTML tronqué (sans encadrer par `update_start`/`update_end`), en simulant une écriture partielle interceptée par un polling concurrent.
  - Then le endpoint `/status` reflète un `mtime` changé sans avoir vu passer de flag `update_in_progress=true`.
  - And le comportement observé (rechargement possible d'un contenu tronqué) est documenté comme risque connu, pas silencieusement toléré: le test doit échouer si un garde-fou serveur apparaît sans mise à jour de cette spec.
- **Cleanup:** Restaurer `pres.html` à un état valide.
- **Priority:** High

#### E2E-009: Sauvegarde refusée vers un chemin protégé (templates/)
- **Category:** Security
- **Scenario:** SC-003
- **Requirements:** FR-007
- **Preconditions:** Serveur HTTP démarré, fichier servi = `templates/bootstrap/slides-ei-empty.html` (chemin protégé).
- **Steps:**
  - Given le serveur sert un fichier dont le chemin absolu contient `templates/bootstrap/`.
  - When le navigateur simulé POST une sauvegarde modifiant ce fichier.
  - Then la réponse HTTP indique un refus (statut non-2xx, ex. 403) avec un message explicite `{"error": "read-only template path"}`.
  - And le contenu de `templates/bootstrap/slides-ei-empty.html` sur disque reste strictement identique (checksum inchangé) après la requête.
- **Cleanup:** Aucun (rien n'a été modifié).
- **Priority:** High

#### E2E-011: Renumérotation après suppression d'une slide au milieu du deck
- **Category:** Edge Case / State Transition
- **Scenario:** SC-003
- **Requirements:** FR-008
- **Preconditions:** Document présentation avec 3 slides `data-id="slide-0"`, `"slide-1"`, `"slide-2"`, `data-title` respectifs `"A"`, `"B"`, `"C"`.
- **Steps:**
  - Given le fichier a 3 slides numérotées 0 à 2.
  - When l'éditeur navigateur supprime la slide `data-id="slide-1"` (titre "B") via le bouton de suppression.
  - Then après sauvegarde, le fichier ne contient plus que 2 slides avec `data-id="slide-0"` (titre "A") et `data-id="slide-1"` (titre "C", renumérotée depuis `slide-2`).
  - And le compteur affiché passe de "Slide 01/03" à "Slide 01/02" pour la première slide.
  - And le dropdown `#slide-select` contient exactement 2 `<option>` avec les titres "A" et "C" dans cet ordre.
- **Cleanup:** Restaurer le fichier à 3 slides initiales.
- **Priority:** Medium

#### E2E-014: Export PPTX d'un deck avec 0 slide valide (fallback contenu)
- **Category:** Failure / Edge
- **Scenario:** SC-004
- **Requirements:** FR-013, FR-014
- **Preconditions:** Fichier `no-slides.html`, `data-doc-type="presentation"`, aucun élément `data-type="slide"` ni `class="slide"`, mais un `<body>` non vide (`<p>Contenu orphelin</p>`).
- **Steps:**
  - Given `no-slides.html` sans aucune slide détectable.
  - When `mcp-htmleditor export pptx no-slides.html out.pptx` est exécuté.
  - Then la commande se termine avec un code de sortie 0 (pas d'échec).
  - And `out.pptx` existe et contient exactement 1 diapositive portant le texte "Contenu orphelin".
  - And la sortie CLI (stderr) contient un warning explicite mentionnant "aucune slide détectée".
- **Cleanup:** Supprimer `out.pptx`.
- **Priority:** High

#### E2E-023: get_status() sans fichier chargé ne lève jamais d'exception
- **Category:** Core Journey / Error Recovery
- **Scenario:** SC-007
- **Requirements:** FR-009, FR-024
- **Preconditions:** Serveur MCP jamais initialisé avec `start_server` dans cette session de test (état vierge).
- **Steps:**
  - Given un serveur MCP fraîchement démarré, aucun `start_server` appelé.
  - When le client MCP appelle `get_status()`.
  - Then la réponse contient `{"file": null, "port": 7842, "server_pid": null, "update_in_progress": false, "running": false}`.
  - And aucune exception n'est levée côté serveur (le process reste up, `mcp-htmleditor mcp` toujours répondant à l'appel suivant).
- **Cleanup:** Aucun.
- **Priority:** Critical

#### E2E-024: start_server appelé deux fois sur le même port/fichier (idempotence)
- **Category:** Error / Concurrency
- **Scenario:** SC-007
- **Requirements:** FR-009
- **Preconditions:** `start_server(file="pres.html", port=7842)` déjà appelé et actif.
- **Steps:**
  - Given `get_status().running == true` sur le port 7842 pour `pres.html`.
  - When le client MCP appelle une seconde fois `start_server(file="pres.html", port=7842)`.
  - Then la réponse indique que le serveur est déjà actif (pas de second process lancé, pas d'erreur "port already in use").
  - And `get_status().server_pid` reste identique avant/après le second appel.
- **Cleanup:** `stop_server()`.
- **Priority:** High

#### E2E-025: start_server sur un port déjà occupé par un processus tiers
- **Category:** Error
- **Scenario:** SC-007
- **Requirements:** FR-009
- **Preconditions:** Un processus tiers (ex. `python -m http.server 7842`) occupe déjà le port 7842, aucun état `mcp-htmleditor` ne le connaît.
- **Steps:**
  - Given le port 7842 est occupé par un processus externe non géré par `EditorState`.
  - When le client MCP appelle `start_server(file="pres.html", port=7842)`.
  - Then la réponse retourne une erreur explicite (ex. `{"error": "port 7842 already in use"}`) plutôt qu'un crash silencieux ou un état incohérent.
  - And `get_status().running` reste `false` pour ce fichier après l'échec.
- **Cleanup:** Arrêter le processus tiers.
- **Priority:** High

#### E2E-036: Aucune donnée sensible dans un span de trace après un export
- **Category:** Security / Data Integrity
- **Scenario:** (transverse)
- **Requirements:** FR-023
- **Preconditions:** Tracing activé (JSONL local), document contenant un texte sensible fictif `"CONFIDENTIEL-TEST-1234"` dans une slide.
- **Steps:**
  - Given un document `secret.html` avec le texte `"CONFIDENTIEL-TEST-1234"` dans une slide.
  - When `mcp-htmleditor export pptx secret.html out.pptx` est exécuté avec tracing actif.
  - Then le fichier `mcp-htmleditor-otel.log` contient un span `export.pptx` avec ses attributs autorisés (`file.path`, `slide.count`, `warning.count`, `duration_ms`).
  - And aucune ligne du fichier de trace ne contient la sous-chaîne `"CONFIDENTIEL-TEST-1234"`.
- **Cleanup:** Supprimer `secret.html`, `out.pptx`, purger la ligne de trace de test.
- **Priority:** High

#### E2E-038: Entrer en plein écran masque la navigation et zoome la slide pour remplir l'écran
- **Category:** Core Journey
- **Scenario:** SC-008
- **Requirements:** FR-026, FR-027
- **Preconditions:** Serveur HTTP servant un fichier `deck.html` (template `ei` ou `carbon`) avec 3 slides, ouvert dans un navigateur avec viewport `1600x900`.
- **Steps:**
  - Given la page est chargée, `document.fullscreenElement` est `null`, le `.toolbar` interne est visible (`display` calculé ≠ `none`), et la `.slide.active` a une boîte visuelle (`getBoundingClientRect`) de `[960, 540]` (taille de conception native).
  - When l'utilisateur clique `#present-btn`.
  - Then `frame.contentDocument.fullscreenElement` (document interne de l'iframe) devient l'élément `<html>` (pas `null`).
  - And le `.toolbar` et les `.nav-arrow` internes ont un `display` calculé égal à `none`, et le `background-color` du `body` interne est `rgb(0, 0, 0)`.
  - And la variable CSS `--fs-scale` sur `<html>` vaut `1600/960` (≈ 1.667).
  - And la `.slide.active` a désormais une boîte visuelle (`getBoundingClientRect`, transform inclus) de `[1600, 900]` — le contenu (police, cartes) est visuellement agrandi dans les mêmes proportions, pas seulement le conteneur.
- **Cleanup:** `Escape` pour sortir du plein écran.
- **Priority:** Critical
- **Implémenté dans:** `tests/test_fullscreen_e2e.py::test_fullscreen_hides_toolbar_and_fills_the_screen`.

#### E2E-039: Régression — filet de sécurité parent si le plein écran interne est indisponible
- **Category:** Error (régression, bug réel observé et corrigé, cf. DEC-011)
- **Scenario:** SC-008
- **Requirements:** FR-026, FR-027
- **Implémentation réelle (ajustée après implémentation):** Chromium headless piloté par Playwright/CDP ne fait pas respecter de manière fiable la restriction `sandbox` sans `allow-fullscreen` comme le ferait un vrai navigateur interactif (vérifié empiriquement: reproduire le `sandbox` cassé dans un test automatisé laisse quand même `requestFullscreen()` réussir sur le document interne). Le test ne peut donc pas forcer honnêtement le mécanisme exact de refus côté sandbox de bout en bout en automatisé. Il teste à la place la partie déterministe et réellement garantissable du contrat: le filet de sécurité CSS côté document parent (`editor.css`, `body:has(#content-frame:fullscreen) #toolbar`) qui doit masquer la toolbar shell si jamais le chemin de repli (plein écran de l'`<iframe>` elle-même) est pris, quelle qu'en soit la raison.
- **Preconditions:** Deck EI à 3 slides servi normalement.
- **Steps:**
  - Given `#toolbar` (document parent) est visible.
  - When le test appelle directement `document.getElementById('content-frame').requestFullscreen()` (simulation du chemin de repli d'`editor.js`, sans passer par le bouton).
  - Then `document.fullscreenElement.id === 'content-frame'`.
  - And `#toolbar` a un `display` calculé égal à `none`.
- **Cleanup:** Aucun.
- **Implémenté dans:** `tests/test_fullscreen_e2e.py::test_fallback_shell_hides_toolbar_if_inner_fullscreen_is_unavailable`.
- **Priority:** Critical

#### E2E-040: Régression — navigation clavier inopérante si le focus reste hors iframe
- **Category:** Error (régression, bug réel observé et corrigé, cf. DEC-011)
- **Scenario:** SC-008
- **Requirements:** FR-028
- **Preconditions:** Serveur servant `deck.html` (3 slides), navigateur en plein écran via `#present-btn`, focus clavier volontairement forcé sur un élément du document PARENT (ex. `document.body.focus()` côté parent après l'entrée en plein écran, pour simuler un navigateur où le focus ne bascule jamais dans l'iframe).
- **Steps:**
  - Given le compteur interne `#progress-tag` affiche `"1 / 3"`.
  - When la touche `ArrowRight` est envoyée au niveau du document PARENT (focus hors iframe).
  - Then `#progress-tag` (document interne) affiche `"2 / 3"`.
  - And une seconde touche `ArrowRight` fait passer l'affichage à `"3 / 3"`.
  - And une touche `ArrowLeft` le fait revenir à `"2 / 3"`.
- **Cleanup:** `Escape` pour sortir du plein écran.
- **Priority:** Critical
- **Implémenté dans:** `tests/test_fullscreen_e2e.py::test_navigation_keys_work_even_if_focus_never_reaches_the_iframe`.

#### E2E-041: Sortie du plein écran conserve la slide courante
- **Category:** Edge Case / State Transition
- **Scenario:** SC-008
- **Requirements:** FR-028
- **Preconditions:** Serveur servant `deck.html` (3 slides), navigateur en plein écran, navigation jusqu'à la slide 3 via `ArrowRight` × 2.
- **Steps:**
  - Given `#progress-tag` affiche `"3 / 3"` en plein écran.
  - When l'utilisateur appuie sur `Escape`.
  - Then `document.fullscreenElement` (parent) et `frame.contentDocument.fullscreenElement` (interne) redeviennent tous deux `null`.
  - And `#progress-tag` affiche toujours `"3 / 3"` (la position de navigation n'est pas réinitialisée à la sortie).
  - And le `.toolbar` et les `.nav-arrow` internes redeviennent visibles (`display` calculé ≠ `none`).
- **Cleanup:** Aucun.
- **Priority:** Medium
- **Implémenté dans:** `tests/test_fullscreen_e2e.py::test_exiting_fullscreen_keeps_the_current_slide_and_restores_the_ui`.

## 15. Open Questions & TBDs

- **TBD-001**: Comportement exact si `mcp-htmleditor new` cible un fichier déjà existant (écrasement silencieux observé dans le code, jamais explicitement testé ni documenté comme voulu).
- **TBD-002**: Aucun test d'intégration MCP stdio réel (les 6 outils sont testés indirectement via les modules qu'ils appellent, jamais via un vrai client MCP) — gap le plus important identifié.
- **TBD-003**: Aucun test navigateur/E2E réel (édition rich-text, drag-reorder, insertion image/tableau côté DOM) — seulement documenté comme "validation visuelle obligatoire" dans `skill/workflow-create.md`, jamais automatisé (pas de Playwright en CI).
- **TBD-004**: Comportement en cas de port déjà occupé (par un tiers ou par une instance orpheline) non spécifié ni testé.
- **TBD-005**: Pas de limite documentée sur la taille d'image insérée côté navigateur (risque de fichier `.html` obèse en base64).
- **TBD-006**: Pas de garde-fou serveur empêchant une écriture concurrente humain/LLM pendant `update_in_progress=true` — uniquement une convention documentaire ("ne jamais écraser sans demander").
- **TBD-007**: Pas de stratégie de reprise si le process serveur meurt alors que `server_pid` reste persisté (état orphelin potentiel dans `.mcp_state.json`).
- **TBD-008**: `HTMLEDITOR_HOST=0.0.0.0` par défaut en conteneur Docker sans authentification — à valider si le service est un jour exposé au-delà de `localhost`.
- **TBD-009**: Comportement du mode plein écran (SC-008) si aucune slide n'est active au moment du basculement (deck vide ou HTML malformé) — non spécifié, non testé (EXC-008c).
- **TBD-010** (résolu): E2E-038 à E2E-041 sont implémentés dans `tests/test_fullscreen_e2e.py` (pytest-playwright, Chromium headless via `make sync` / `uv run playwright install chromium`), et tournent dans `make test`/`make check`. Limite documentée dans le test lui-même et dans `.agent_docs/testing.md`: Chromium headless piloté par Playwright/CDP ne fait pas respecter de manière fiable la restriction `sandbox` sans `allow-fullscreen` comme un vrai navigateur interactif, donc E2E-039 teste le filet de sécurité côté parent plutôt que le mécanisme exact de refus du sandbox.
- **TBD-011**: Les decks de référence `templates/reference/slides/ibm-carbon.html`, `example-ei-complete.html`, `example-carbon-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html` n'ont **aucun** CSS `:fullscreen` (le mode présentation plein écran n'y a jamais fonctionné, avant comme après DEC-011/DEC-012). Seuls les deux bootstraps (`slides-ei-empty.html`, `slides-empty.html`) et leur source (`euro-information.html`) ont été corrigés. Tout fichier créé par copie manuelle d'un de ces decks de référence (plutôt que via `mcp-htmleditor new`) hérite du même manque, comme l'a montré le fichier réel de l'utilisateur (`Agentic_Platform_Deck.html`, corrigé à la main, hors du repo).

## 16. Glossary

| Term | Definition | Context |
|---|---|---|
| **Charte / Charter** | Ensemble cohérent de CSS (couleurs, polices, tailles) identifiant une identité visuelle (EI, Carbon, Perso, générique). Jamais mélangée dans un même fichier. | Sections 3, 5, 6, 8 |
| **Bootstrap (template)** | Fichier HTML minimal, point de départ copié par `mcp-htmleditor new <key>`. | Sections 3, 5, 6, 8 |
| **Référence (template)** | Fichier HTML riche, exemple complet d'une charte, servi en lecture seule, source du CSS EI. | Sections 3, 5, 6 |
| **data-doc-type** | Attribut sur `<html>` déterminant le mode (`presentation` ou `document`). | Sections 5, 6, 8 |
| **data-type="slide"** | Marque un élément comme diapositive exportable en PPTX. | Sections 5, 6 |
| **data-id** | Identifiant stable d'un élément (slide, nœud de schéma, tâche Gantt), utilisé par la navigation JS et l'export. | Sections 5, 6, 8 |
| **data-editable** | Attribut activant l'édition humaine in-place (`text`, `resize,reposition`, `expand,reorder,resize`). | Sections 5, 6 |
| **update_in_progress** | Flag d'état serveur, levé par `update_start()`, baissé par `update_end()`, gèle le rechargement navigateur. | Sections 5, 6, 8 |
| **WYSIWYG** | What You See Is What You Get: le rendu navigateur reflète fidèlement l'export final. | Section 1 |
| **MCP (Model Context Protocol)** | Protocole stdio reliant l'agent LLM au serveur, exposant 6 outils. | Sections 1, 5, 6 |
| **Polling** | Interrogation cyclique du serveur (`/status`) par le navigateur pour détecter un changement de `mtime`. | Sections 5, 6, 7 |
| **Mtime** | Timestamp de modification du fichier HTML, déclencheur du rechargement navigateur. | Sections 5, 6, 7 |
| **reference.docx** | Document Word généré/caché par charte, transportant les styles pour l'export DOCX via pandoc. | Sections 5, 6, 8 |
| **Letterhead** | En-tête/pied de page Word reproduisant la charte (logo, filet, numéro de page dynamique), disponible pour EI et Perso. | Sections 5, 6 |
| **Gantt (HTML/CSS)** | Diagramme de planification en barres, positionné en % de piste, exportable en formes PPTX natives. | Sections 3, 5, 6 |
| **Arch diagram** | Schéma d'architecture: nœuds positionnés en % (`data-x`/`data-y`) et connecteurs, exportable en formes PPTX. | Sections 3, 5, 6 |
| **Annotated image** | Image avec callouts positionnés en % relatif à l'image. | Section 3 |
| **EditorState** | Singleton en mémoire + fichier `.mcp_state.json`, source de vérité de l'état serveur courant. | Sections 6, 8 |
| **Settings** | Instance pydantic-settings mémoïsée, unique point de lecture de la configuration `HTMLEDITOR_*`. | Sections 6, 7, 8 |
| **Plein écran (mode présentation)** | État Fullscreen API du document interne de l'iframe, déclenché via `#present-btn` ou la touche `f`; masque la navigation et remplit l'écran comme PowerPoint/Keynote. Requiert `allow-fullscreen` sur le `sandbox` de l'iframe et un relais de focus/touches côté document parent (voir DEC-011). | Sections 5 (SC-008), 6 (FR-026–028), 12 |

## 17. Interview Decisions Log

Aucune interview live n'a eu lieu (document rétrospectif). Les décisions ci-dessous sont reconstituées à partir de l'historique git (25 commits, 2026-08-07 16:31 → 2026-08-09 21:08) et documentées comme si elles avaient été actées en Phase 1/2 d'une interview classique.

- **DEC-001:** Rendu HTML natif en `<iframe>` plutôt que canvas GrapesJS. **Rationale:** fidélité exacte au HTML source (ce qui est vu = ce qui sera exporté), plus simple à maintenir sans framework d'édition visuelle tiers. **Alternatives considérées:** GrapesJS (implémenté puis abandonné dès le commit `fix: replace GrapesJS with iframe renderer`, 2026-08-07 17:10). **Round:** 2 (équivalent Approche).
- **DEC-002:** Synchronisation navigateur/disque par polling HTTP (`/status`, 1s) plutôt que WebSocket/SSE. **Rationale:** simplicité d'implémentation et de déploiement (pas de gestion de connexions persistantes), suffisant pour un usage mono-utilisateur local. **Alternatives considérées:** WebSocket (non retenu, non implémenté). **Round:** 3 (NFR performance).
- **DEC-003:** État serveur persisté sur disque (`.mcp_state.json`) plutôt qu'en mémoire seule. **Rationale:** permet à un nouvel appel `mcp-htmleditor mcp` de retrouver l'état d'un serveur déjà lancé (ex. redémarrage de l'agent). **Alternatives considérées:** état en mémoire uniquement (rejeté, perdrait le contexte entre sessions agent). **Round:** 3 (FR).
- **DEC-004:** Deux chartes de présentation (EI, Carbon) et trois chartes de document (doc, doc-perso, doc-ei) figées en dur dans un registre plutôt qu'un système de chartes extensible par plugin. **Rationale:** YAGNI — seuls ces usages sont nécessaires actuellement (Euro-Information et IBM Carbon, contextes professionnels de l'auteur). **Alternatives considérées:** mécanisme de chartes pluggable (différé, non nécessaire pour l'usage réel). **Round:** 1 (scope).
- **DEC-005:** Export PPTX entièrement réécrit en formes natives `python-pptx` plutôt que rendu image/capture d'écran. **Rationale:** fidélité et éditabilité du livrable final dans PowerPoint (formes vectorielles, texte sélectionnable). **Alternatives considérées:** export par capture d'écran/rendu image (implicitement écarté, jamais implémenté). **Round:** 3 (FR export, commit massif du 2026-08-08 17:01, +8250 lignes).
- **DEC-006:** Export DOCX via pandoc + `reference.docx` patché plutôt qu'une génération DOCX maison (python-docx direct). **Rationale:** réutiliser la robustesse de conversion HTML→DOCX de pandoc, ne patcher que les styles/en-têtes nécessaires à la charte. **Alternatives considérées:** génération DOCX 100% custom via `python-docx` (rejeté, plus coûteux en maintenance pour un gain marginal). **Round:** 3 (FR export DOCX).
- **DEC-007:** Nettoyage strict des artefacts d'édition avant chaque sauvegarde disque, plutôt que tolérer des résidus DOM. **Rationale:** garantir que le fichier HTML source reste portable et propre pour l'agent LLM qui le relira. **Alternatives considérées:** laisser les artefacts et les filtrer uniquement à l'export (rejeté, complexifierait chaque pipeline d'export au lieu d'une source toujours propre). **Round:** 3 (FR-005).
- **DEC-008:** Règle produit "modification humaine trouvée = volontaire, jamais écrasée sans le demander" plutôt qu'un mécanisme de verrouillage ou de merge automatique. **Rationale:** simplicité, respecte l'autonomie de l'éditeur humain; documenté dans le tout dernier commit (`docs: une modification humaine trouvée dans le fichier est volontaire`, 2026-08-09 21:08). **Alternatives considérées:** verrouillage exclusif serveur, merge automatique de diffs HTML (aucun implémenté, jugés disproportionnés pour l'usage mono-utilisateur). **Round:** 2c (scénarios d'échec/conflit).
- **DEC-009:** Pas de CI centralisée; `make check` local + hooks pre-commit comme seule porte de qualité. **Rationale:** projet personnel solo, pas de collaborateur à bloquer à l'entrée d'un repo distant; le coût d'une CI n'est pas justifié à ce stade. **Alternatives considérées:** GitHub Actions (non mis en place). **Round:** 4 (NFR déploiement).
- **DEC-010:** Configuration strictement centralisée dans `Settings` (pydantic-settings), interdiction documentée de lire `os.environ` ailleurs. **Rationale:** testabilité (mémoïzation par signature d'env, fixtures `reset_settings`), un seul point de vérité pour tous les chemins XDG. **Alternatives considérées:** lecture directe de variables d'environnement au point d'usage (rejetée par convention explicite dans AGENTS.md). **Round:** 4 (NFR sécurité/config).
- **DEC-011:** Fix post-rétrospectif du mode plein écran (SC-008, FR-026 à FR-028), trouvé lors d'une relecture manuelle par l'utilisateur ("je m'attends à ça... comme un vrai powerpoint") et non couvert initialement par cette spécification. Deux bugs réels composés: (1) l'iframe `#content-frame` était `sandbox` sans `allow-fullscreen`, donc `requestFullscreen()` sur le document interne (où vit le CSS `:fullscreen` du template) était refusé par spécification navigateur, et le code retombait sur le plein écran de l'`<iframe>` côté document PARENT, où ce CSS ne s'applique jamais (mauvais document); (2) même une fois le bon document ciblé, `requestFullscreen()` ne déplace jamais le focus clavier, donc le gestionnaire `keydown` natif du template (flèches) ne recevait aucun événement puisque le focus restait sur le bouton `#present-btn` du document parent. **Fix:** ajout de `allow-fullscreen` au `sandbox` (+ `allow="fullscreen"`/`allowfullscreen`), `frame.focus()` après obtention du plein écran, et un relais de touches côté document parent vers `navigate()`/`goToSlide()` de l'iframe tant que `document.fullscreenElement` est actif. **Alternatives considérées:** réécrire la navigation entièrement côté document parent (rejeté, dupliquerait la logique déjà présente dans chaque template au lieu de la réutiliser via `contentWindow`). **Validation:** test Playwright scriptable (`1/3 → 2/3 → 3/3 → 2/3`) puis confirmation visuelle directe de l'utilisateur en navigateur réel, puis (à la demande explicite de l'utilisateur, "toujours via make pour tout") pérennisé en 4 tests automatisés dans `tests/test_fullscreen_e2e.py` (pytest-playwright), câblés dans `make sync`/`make test`/`make check`. Au passage, deux dettes de lint préexistantes et sans rapport (`src/mcp_htmleditor/http_server.py`: imports paresseux non ignorés, ligne trop longue, `# noqa` mort) bloquaient `make check` depuis le commit `b63cb6a`; corrigées pour que la porte de qualité fonctionne à nouveau de bout en bout. **Leçon:** cette fonctionnalité était mentionnée au Scope (3.1) et en NFR Usability (7.3) mais n'avait ni scénario (SC-XXX) ni FR ni test E2E dédiés dans la version initiale de cette spécification — corrigé ici via SC-008/FR-026–028/E2E-038–041. **Round:** rétrospectif, post-publication (hors interview initiale).
- **DEC-012:** Fix du "faux plein écran" (pas d'effet zoom): `:fullscreen .slide { width:100%; height:100vh; }` (DEC-011) étirait le *conteneur* sans agrandir le *contenu* (polices/cartes en px fixes), laissant un grand vide sous un contenu resté minuscule — trouvé par l'utilisateur sur son vrai fichier ("les fontes ont pas bougé, les tailles ont pas bougé"). **Fix:** la slide garde sa taille de conception native (960×540, ratio 16:9) et reçoit `transform: scale(var(--fs-scale, 1)); transform-origin: center center;`; `--fs-scale` est calculé en JS (`Math.min(innerWidth/rect.width, innerHeight/rect.height)`, mesuré après réinitialisation à `1`) par `updateFullscreenScale()`, appelé sur `fullscreenchange`, `resize`, et à chaque `render()`. Effet: zoom uniforme (police, cartes, images) fidèle à PowerPoint/Keynote, avec letterboxing sur l'axe contraint si l'écran n'est pas en 16:9 (pas de déformation). **Alternatives considérées:** CSS `zoom` (non standard, non supporté Firefox, rejeté); redimensionner dynamiquement chaque propriété CSS interne en `vw`/`vh` (rejeté, casserait la mise en page fixe en pixels de tous les composants existants — tuiles, Gantt, schémas). **Propagation:** `templates/reference/slides/euro-information.html` (source, régénère `slides-ei-empty.html` via `make bootstrap-ei`), `templates/bootstrap/slides-empty.html` (Carbon, pas de générateur séparé), et le fichier réel de l'utilisateur (`Agentic_Platform_Deck.html`, copie autonome ne bénéficiant pas des mises à jour de template). **Gap restant:** les autres decks de référence (`ibm-carbon.html`, `example-*-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html`) n'ont **jamais** eu de CSS `:fullscreen` du tout — non corrigés ici (hors périmètre de la demande), voir TBD-011. **Validation:** mesure Playwright (`--fs-scale` == ratio exact viewport/design, `getBoundingClientRect` après transform == taille viewport, aspect-ratio préservé avec letterboxing sur un viewport non-16:9) + `tests/test_fullscreen_e2e.py::test_fullscreen_hides_toolbar_and_fills_the_screen` mis à jour. **Round:** rétrospectif, post-publication.
