# Types: Mail (HTML pour client de messagerie)

## Pourquoi ce type est different des autres

Un mail HTML n'est ni une slide (pas de pagination, pas d'export PPTX) ni un
document Word-like (pas de flux vers DOCX). Sa seule destination est le corps
d'un client mail (Gmail, Outlook, Apple Mail...), qui applique des regles bien
plus strictes qu'un navigateur:

- **Le `<style>` dans `<head>` n'est pas fiable.** Beaucoup de webmails le
  suppriment a la reception, ou l'appliquent de facon incomplete. La seule
  garantie multi-client est l'attribut `style=""` pose directement sur chaque
  element qui compte pour le rendu.
- **Flexbox et CSS Grid ne sont pas fiables**, en particulier sur les clients
  Outlook de bureau (moteur de rendu Word). La mise en page utilise des
  `<table>` imbriquees: un wrapper 100% pour centrer, un conteneur a largeur
  fixe (600 a 640px) pour le contenu.
- **`position:absolute` et `position:fixed` sont a eviter**: pas de support
  fiable, aucun besoin pour un mail (pas de superposition d'elements).
- **`border-radius`, `overflow:hidden` et `box-shadow` ne sont pas fiables sous
  Outlook de bureau** (moteur de rendu Word, pas un vrai moteur CSS): les coins
  restent carres et l'ombre disparait. Sans consequence si le fond du bloc est
  uniforme (un carre au lieu d'un rectangle a coins arrondis reste lisible),
  mais ne jamais compter sur `overflow:hidden` pour cacher un debordement de
  contenu: sous Outlook, le contenu debordant reste visible en dehors du cadre
  au lieu d'etre coupe. Corrige dans le bootstrap et l'exemple de reference le
  2026-08 apres relecture: les deux avaient encore ces trois proprietes sur la
  table conteneur, dupliquees dans ce fichier de skill.

- **Toute couleur de fond, marge, taille de police ou bordure qui compte pour
  le rendu final doit etre inline.** Le `<style>` du template n'est qu'un
  confort d'edition dans le navigateur (permet a l'humain de voir un rendu
  correct pendant qu'il tape); il n'est PAS cense survivre a l'envoi.

## Structure obligatoire

```html
<!DOCTYPE html>
<html lang="fr" data-doc-type="document">
<head>…</head>
<body style="margin:0; padding:0; background-color:#f4f5f7; font-family:Helvetica,Arial,sans-serif;">

<article data-type="document" data-doc-template="mail" data-layout="single-column">

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f5f7;">
    <tr><td align="center" style="padding:24px 12px;">

      <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0"
             style="width:640px; max-width:640px; background-color:#ffffff;">

        <tr><td style="…">  <!-- une section = une ligne de table -->
          <h1 data-editable="text" style="…">Titre</h1>
        </td></tr>

        <!-- une <tr><td> par section suivante -->

      </table>

    </td></tr>
  </table>

</article>

</body>
</html>
```

- `data-doc-type="document"` sur `<html>`: reutilise le mode edition existant
  (pas de navigation slides, toolbar "+ Bloc").
- `data-doc-template="mail"` sur l'`<article>`: marqueur de charte. Aucun
  export DOCX n'est prevu pour ce type (`charter_for("mail")` retombe
  proprement sur `None`, sans erreur), donc cet attribut ne pilote aucune
  generation de `reference.docx`. Il documente juste l'intention.
- `role="presentation"` sur les `<table>` de mise en page: indique aux
  lecteurs d'ecran que ce ne sont pas des tableaux de donnees.
- `width="640"` en attribut ET `style="width:640px; max-width:640px;"`:
  redondance volontaire, certains clients ne lisent que l'un des deux.

## Charte Carbon leger

Palette simplifiee, tokens IBM Carbon reduits a l'essentiel pour rester
sobre en mail (pas de composants Carbon complexes type `cds-grid`, pas de
police IBM Plex qui n'est garantie sur aucun poste destinataire):

| Usage | Couleur | Contexte |
|---|---|---|
| En-tete (fond) | `#161616` | bandeau titre du mail |
| Accent principal | `#0f62fe` | titres de section, filets |
| Encadre info (fond) | `#edf5ff` | notification/rappel, barre laterale `#0f62fe` |
| Alerte douce (titre) | `#7a1f1f` | section "ce qu'il reste a faire" |
| Texte principal | `#1a1a1a` | corps de texte |
| Texte secondaire | `#8a8f98` | pied de page |
| Fond hors carte | `#f4f5f7` | fond de la page mail (hors du bloc blanc) |
| Police | `Helvetica, Arial, sans-serif` | garantie sur tous les postes, contrairement a IBM Plex |

**Alignement par defaut: justifie sur le texte de corps.** Les paragraphes de
contenu (intro, encadres de notification) portent `text-align:justify` en
inline, convention de courrier professionnel qui donne un bloc de texte aux
deux marges nettes plutot qu'un bord droit en dents de scie. Ne pas l'appliquer
aux titres (`h1`/`h2`), aux listes a puces, ni aux textes courts d'une seule
ligne (sous-titre d'en-tete, pied de page): le justifie n'a d'effet que sur un
texte qui occupe plusieurs lignes, et peut y creer de grands espaces blancs
quand une ligne n'a que peu de mots.

## Blocs disponibles (toolbar "+ Bloc")

Les blocs generiques (`heading1`..`heading5`, `paragraph`, `table`, `list`)
du picker sont **des balises semantiques nues**, sans style inline: ils
heritent normalement de la charte via des classes CSS pour les autres
templates (`doc-perso`, `doc-ei`), mais **un mail n'a pas de charte par
classe** puisque le `<style>` n'est pas fiable a l'envoi.

**Consequence a connaitre**: un bloc insere via le picker dans un mail
atterit avec le rendu par defaut du navigateur (texte noir, pas de
couleur de charte), jusqu'a ce qu'il recoive un style inline. Deux facons de
le corriger, dans cet ordre de preference:

1. **Cloner une section existante** du document plutot que d'inserer un bloc
   vide: copier un bloc `<tr><td style="…">…</td></tr>` deja stylé et
   modifier son texte. C'est la methode recommandee pour le LLM.
2. **Styler a la main apres insertion**: en navigateur, selectionner le texte
   insere et utiliser la barre de format flottante (gras, couleur, taille);
   ces actions produisent des styles inline (`document.execCommand`), donc
   restent mail-safe. Cote LLM: ajouter directement l'attribut `style=""`
   sur l'element insere avant de reecrire le fichier.

## Regles de construction (LLM)

1. **Toujours partir du bootstrap**: `mcp-htmleditor new mail`, jamais
   ecrire une structure de mail de zero.
2. **Une section de contenu = une ligne de table** (`<tr><td style="padding:…">`),
   jamais une `<div>` avec `display:flex` ou `display:grid`.
3. **Largeur fixe 640px** sur la table interne, jamais de `width:100%` sur le
   conteneur de contenu (uniquement sur le wrapper exterieur, pour centrer).
4. **Chaque `<h1>`, `<h2>`, `<p>`, `<li>`, `<td>` qui porte une couleur ou une
   taille de charte le fait en `style=""` inline**, jamais uniquement via une
   classe CSS.
5. **Images**: comme les autres templates, embarquer en base64
   (`data:image/png;base64,...`), jamais de chemin relatif ni d'URL externe
   (un mail n'a pas de dossier `media/` qui l'accompagne).
6. **Pas de `<script>`**: un mail HTML envoye ne doit contenir aucun
   JavaScript (bloque ou ignore par tous les clients, et certains filtres
   anti-spam penalisent sa presence). Le template mail n'en a jamais eu
   besoin (pas de navigation a piloter, contrairement aux slides).
7. **Largeur d'image interne**: `style="max-width:100%; height:auto;
   display:block;"` sur chaque `<img>`, jamais de `width` en pourcentage sans
   `max-width` explicite (Outlook ignore parfois le pourcentage seul).

## Verifier le rendu avant envoi

Le fichier HTML genere est autonome (aucune dependance externe), mais deux
verifications valent le detour avant un envoi reel:

1. **Rendu navigateur** (`mcp-htmleditor serve`): verifie le contenu, le
   texte, l'absence de debordement dans le cadre de 640px.
2. **Rendu client mail reel**: coller le HTML dans un brouillon Gmail (ou un
   outil de previsualisation multi-client) pour confirmer que les couleurs et
   la mise en page tiennent sans le `<style>` de tete. C'est la seule
   verification qui compte vraiment: le rendu navigateur seul ne suffit pas a
   garantir la compatibilite mail, exactement comme le rendu HTML seul ne
   suffit pas a garantir un rendu slide correct (cf. validation visuelle des
   slides dans `skill/workflow-create.md`).

## Ce que ce type n'a pas (volontairement)

- **Pas d'export dedie**: un mail HTML s'envoie tel quel (copier-coller dans
  le corps d'un brouillon, ou piece jointe `.html`). Aucune commande
  `mcp-htmleditor export mail` n'existe ni n'est prevue: il n'y a rien a
  convertir, contrairement a PPTX/DOCX qui reconstruisent un format binaire
  different.
- **Le bouton DOCX de la toolbar reste visible.** Il est affiche pour tout
  `data-doc-type="document"` (comportement partage avec `doc`, `doc-perso`,
  `doc-ei`, code cote `editor.js`, non specifique a la charte); cliquer
  dessus produit un DOCX sans reference charte (`charter_for("mail")` vaut
  `None`, comme pour `doc` standard). Ce n'est pas le flux prevu pour un
  mail: l'ignorer, l'envoi se fait en HTML.
- **Pas de Gantt ni de schema d'architecture**: ces composants (`skill/types/
  gantt.md`, `skill/types/arch-diagram.md`) dependent de positions en
  pourcentage sur un conteneur `position:relative`, non garanties en mail.
  Pour illustrer un planning ou une architecture dans un mail, generer une
  image (capture d'un diagramme existant, ou export PNG) et l'embarquer en
  base64 plutot que du HTML/CSS positionne.
