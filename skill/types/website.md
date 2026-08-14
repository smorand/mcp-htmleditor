# Types: Site web (`website`)

## Pourquoi ce type est différent des autres

Un site web (page unique, charte Carbon) n'a **aucune destination d'export**: pas de
PPTX (ce n'est pas une slide), pas de DOCX (ce n'est pas un document à imprimer). Sa
seule destination est le navigateur lui-même — le fichier HTML final EST le livrable.
Cette absence de contrainte d'export change ce qui est permis, à l'inverse du mail
(`skill/types/mail.md`), qui doit au contraire éviter flexbox/grid/`position` pour
survivre au moteur de rendu d'un client mail:

- **Flexbox, CSS Grid et `position:sticky`/`absolute` sont libres d'usage.** Aucun
  exporteur ne lira jamais ce fichier: seul le rendu navigateur compte.
- **`border-radius`, `box-shadow`, `overflow:hidden` sont libres** (contrairement au
  mail, où Outlook les ignore).
- **Un vrai `<script>` interactif est encouragé** pour les composants qui en ont
  l'usage (onglets, menu mobile, accordéon) — voir « Interactivité » ci-dessous pour la
  règle qui évite le conflit avec le mode édition.

## Structure obligatoire

```html
<!DOCTYPE html>
<html lang="fr" data-doc-type="website">
<head>…</head>
<body>

<article data-type="document" data-doc-template="website" data-layout="single-column">
  <nav class="site-nav">…</nav>
  <section class="site-hero">…</section>
  <section class="site-tabs">…</section>
  <section class="site-cards">…</section>
  <footer class="site-footer">…</footer>
</article>

<script>/* interactivite reelle, ex. switchSiteTab() */</script>
</body>
</html>
```

`data-doc-type="website"` (pas `"document"`) est ce qui distingue un site d'un document
Word-like dans `editor.js` (`isWebsite`): il réutilise tout le mode édition document
(texte, blocs déplaçables/insérables via `data-type="document"` sur l'`<article>`), mais
**n'affiche ni bouton d'export PPTX ni bouton d'export DOCX** — voir
`updateDocActionsVisibility()`. N'utilisez jamais `data-doc-type="document"` pour un
site: le bouton d'export DOCX apparaîtrait alors qu'aucun code ne produit un rendu
correct pour ce contenu (nav, tabs, grilles ne se transposent pas en Word).

Chaque section de premier niveau à l'intérieur de l'`<article>` (nav, hero, tabs,
cartes, footer) est un bloc déplaçable/réordonnable comme dans un document, via la
poignée de glisser-déposer du mode édition.

## Interactivité: séparer le clic du texte éditable

Un composant interactif (onglet, menu déroulant) a deux parties qui ne doivent jamais
être le même élément:

1. **L'élément cliquable** (le `<button>` ou conteneur qui porte `onclick`) — jamais
   `data-editable`.
2. **Le texte affiché** — un `<span data-editable="text">` **imbriqué** dans l'élément
   cliquable.

```html
<button class="site-tab active" onclick="switchSiteTab(this, 'tab-1')" type="button">
  <span data-editable="text">Vue d'ensemble</span>
</button>
```

Pourquoi: en mode édition, `[data-editable~="text"]` reçoit `contenteditable`. Si le
`<button>` lui-même portait `data-editable`, cliquer dessus pour changer d'onglet
risquerait de ne jamais déclencher `onclick` (le navigateur pourrait gérer le clic comme
un simple placement de curseur sur tout l'élément). En imbriquant le texte dans le
conteneur cliquable, l'événement remonte naturellement du `<span>` au `<button>`: le clic
bascule toujours l'onglet, dans les deux modes, vérifié par un test Playwright réel
(`tests/test_website_template_e2e.py`), pas supposé. En mode édition, le navigateur peut
aussi poser un curseur d'édition dans le `<span>` cliqué (comportement normal de tout
`[data-editable]`, pas un défaut à corriger) — l'onglet a déjà basculé avant cela, et
l'humain peut ensuite éditer le libellé normalement s'il le souhaite.

## Composants du bootstrap (`templates/bootstrap/website-empty.html`)

- `.site-nav`: barre de navigation sombre fixe (`position:sticky`), logo + liens
  horizontaux + bouton CTA.
- `.site-hero`: titre principal centré, sous-titre, deux boutons d'action
  (`.cds-btn-primary` / `.cds-btn-secondary`).
- `.site-tabs`: onglets fonctionnels (`switchSiteTab()`), 3 panneaux de contenu.
- `.site-cards`: grille de 3 cartes (`display:grid`, `grid-template-columns:repeat(3,1fr)`).
- `.site-footer`: 4 colonnes de liens + ligne de copyright.

Catalogue complet de variantes (nav avec sous-menu, tabs verticaux, cartes avec image,
footer minimal): `templates/reference/websites/ibm-carbon.html`.

## Ce qu'il ne faut jamais faire

- Ne jamais ajouter `data-doc-type="document"` à un site: cela ferait apparaître le
  bouton d'export DOCX pour un contenu qui n'a pas de rendu Word correct.
- Ne jamais marquer `data-editable` directement sur un élément qui porte aussi
  `onclick`: voir « Interactivité » ci-dessus.
- Ne pas utiliser ce type pour un document destiné à devenir un PPTX ou un DOCX: dans
  ce cas, utiliser `carbon`/`ei` (slides) ou `doc`/`doc-perso`/`doc-ei` (documents).
