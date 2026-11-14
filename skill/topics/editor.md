Ce que la personne voit et fait dans l'éditeur, et ce qu'un agent doit en savoir. Les notes du présentateur s'écrivent selon `mcp-htmleditor skill --type create`.

## Raccourcis clavier

`F` plein écran de la présentation, `P` pointeur (`L` aussi), `S` fenêtre présentateur, `E` mode édition (éditeur seulement), `?` aide des raccourcis (icône à droite de la barre d'outils; un deck ouvert seul affiche son propre overlay). `N` passe à la slide suivante dans la fenêtre présentateur. Les touches sont ignorées avec Ctrl, Meta ou Alt, et dans un champ de saisie ou un élément éditable. Un deck ouvert directement en fichier gère `F`, `P`, `S`.

## Fenêtre présentateur

`S` ou le bouton Presenter ouvre une fenêtre: slide courante, slide suivante, notes de la slide en grand (taille réglable), compteur, minuteur avec remise à zéro, horloge, boutons précédent et suivant. Elle suit le deck et le deck la suit; `S` ou sa fermeture la ferme. Elle lit le HTML du deck: ne rien ajouter pour elle.

## Notes du présentateur

`<aside data-role="speaker-notes">` enfant direct de la slide, texte brut. Masquée à l'écran et à l'impression par une règle du deck (sélecteur d'attribut, jamais une classe), exportée dans la page de notes PPTX. En mode Édition d'une présentation, le bouton Notes ouvre un panneau en bas lié à la slide courante: la saisie crée, met à jour ou supprime l'`aside` et enregistre comme toute édition. Si l'humain tape des notes pendant que l'agent travaille, relire le fichier avant d'écrire.

## Panneau Requests

Le bouton `Requests (n)` (n = demandes en attente) ouvre ou ferme le panneau des demandes et des suggestions, fermé par défaut. Boucle de l'agent:

1. `list_requests` (filtres `slide` et `status`; chaque demande porte la position de sa slide).
2. Faire le travail, puis `complete_request` en `done` ou `skipped` avec une raison.
3. `clear_requests` retire les demandes finies (`scope` `finished`, défaut) ou toutes (`all`, en attente comprises: à n'utiliser que sur demande).
4. `write_review` remplace les suggestions (6 au plus).

## GET /health

Sur le port du serveur, sans condition d'hôte: `{"ok": true, "pid", "file", "page", "port", "version", "started", "uptime_seconds"}`. `file` (chemin absolu) et `page` (son nom) valent `null` sans fichier chargé. Rien n'est lu ni écrit. Avant de démarrer, d'arrêter ou de redémarrer un serveur, vérifier avec `get_status` ou `/health` quel fichier il sert et son pid; ne jamais arrêter un serveur qu'on n'a pas lancé.
