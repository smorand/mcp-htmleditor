# Types: Mail (HTML pour client de messagerie)

Un mail HTML n'a ni pagination ni export PPTX/DOCX: sa seule destination est le corps d'un client mail (Gmail, Outlook, Apple Mail), aux regles bien plus strictes qu'un navigateur.

## Contraintes client mail

- Le `<style>` de `<head>` n'est pas fiable (supprime ou applique en partie). Seul l'attribut `style=""` pose sur chaque element qui compte est garanti. Toute couleur de fond, marge, taille de police ou bordure utile au rendu final est inline; le `<style>` du template n'est qu'un confort d'edition.
- Flexbox et CSS Grid ne sont pas fiables (Outlook de bureau, moteur Word): mise en page en `<table>` imbriquees, un wrapper 100% pour centrer, un conteneur de largeur fixe pour le contenu.
- Eviter `position:absolute` et `position:fixed`.
- `border-radius`, `overflow:hidden` et `box-shadow` ne sont pas fiables sous Outlook: ne jamais compter sur `overflow:hidden` pour cacher un debordement (le contenu reste visible hors du cadre). Ne pas les poser sur la table conteneur.

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
        <tr><td style="background-color:#161616; padding:24px 32px;">
          <h1 data-editable="text" style="margin:0; font-size:22px; color:#ffffff;">Titre</h1>
        </td></tr>
        <tr><td style="padding:24px 32px;">
          <p data-editable="text" style="margin:0 0 12px; font-size:14px; line-height:1.6; color:#1a1a1a; text-align:justify;">Texte.</p>
          <img src="data:image/png;base64,…" alt="…" style="max-width:100%; height:auto; display:block;">
        </td></tr>
        <tr><td style="padding:16px 32px; background-color:#edf5ff; border-left:4px solid #0f62fe;">
          <p data-editable="text" style="margin:0; font-size:13px; color:#1a1a1a; text-align:justify;">Encadre info.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</article>
</body>
</html>
```

- `data-doc-type="document"` sur `<html>` reutilise le mode edition document (pas de navigation slides, toolbar "+ Bloc").
- `data-doc-template="mail"` sur l'`<article>` est un marqueur de charte; aucun export DOCX n'est prevu, il ne pilote aucun `reference.docx`.
- `role="presentation"` sur les `<table>` de mise en page (ce ne sont pas des tableaux de donnees).
- `width="640"` en attribut ET `style="width:640px; max-width:640px;"`: redondance voulue, certains clients ne lisent que l'un des deux.

## Charte Carbon leger

| Usage | Valeur |
|---|---|
| En-tete (fond) | `#161616` |
| Accent principal (titres de section, filets) | `#0f62fe` |
| Encadre info (fond, barre laterale `#0f62fe`) | `#edf5ff` |
| Alerte douce (titre) | `#7a1f1f` |
| Texte principal | `#1a1a1a` |
| Texte secondaire (pied) | `#8a8f98` |
| Fond hors carte | `#f4f5f7` |
| Police | `Helvetica, Arial, sans-serif` (IBM Plex n'est garantie sur aucun poste) |

Alignement par defaut: `text-align:justify` en inline sur les paragraphes de corps (intro, encadres). Ne pas l'appliquer aux titres `h1`/`h2`, aux listes a puces, ni aux textes d'une seule ligne (sous-titre d'en-tete, pied).

## Blocs de la toolbar "+ Bloc"

Les blocs generiques (`heading1`..`heading5`, `paragraph`, `table`, `list`) sont des balises nues sans style inline: dans un mail ils sortent en rendu navigateur par defaut jusqu'a recevoir un `style=""`. Par ordre de preference:

1. **Cloner une section existante** (un `<tr><td style="…">…</td></tr>` deja style) et changer son texte. Methode recommandee pour le LLM.
2. Styler a la main apres insertion: barre de format flottante (styles inline), ou ajouter `style=""` sur l'element avant de reecrire le fichier.

## Regles de construction

1. Toujours partir du bootstrap: `mcp-htmleditor new mail`, jamais ecrire un mail de zero.
2. Une section de contenu = une ligne de table (`<tr><td style="padding:…">`), jamais une `<div>` en `display:flex` ou `display:grid`.
3. Largeur fixe 640px sur la table interne, jamais de `width:100%` sur le conteneur de contenu (seulement sur le wrapper exterieur).
4. Chaque `<h1>`, `<h2>`, `<p>`, `<li>`, `<td>` qui porte une couleur ou une taille de charte la met en `style=""` inline, jamais uniquement par classe CSS.
5. Images embarquees en base64 (`data:image/png;base64,...`), jamais de chemin relatif ni d'URL externe.
6. Pas de `<script>`: aucun JavaScript dans un mail (bloque par les clients, penalise par les filtres anti-spam).
7. Chaque `<img>` porte `style="max-width:100%; height:auto; display:block;"`, jamais de `width` en pourcentage sans `max-width` (Outlook ignore parfois le pourcentage seul).

## Avant envoi

1. Rendu navigateur (`mcp-htmleditor serve`): contenu, texte, pas de debordement dans les 640px.
2. Rendu client reel: coller le HTML dans un brouillon Gmail (ou un outil multi-client) pour confirmer que couleurs et mise en page tiennent sans le `<style>` de tete. Le rendu navigateur seul ne garantit pas la compatibilite mail.

## Ce que le type n'a pas (volontairement)

- Pas d'export dedie: le mail s'envoie tel quel (copier-coller dans un brouillon, ou piece jointe `.html`). Il n'existe pas de commande `export mail`.
- Le bouton DOCX de la toolbar reste visible (partage avec tout `data-doc-type="document"`) et produit un DOCX sans charte: l'ignorer.
- Pas de Gantt ni de schema d'architecture (pourcentages sur `position:relative` non garantis en mail): embarquer une image PNG en base64.

Reference: templates/reference/documents/mail-carbon-example.html
