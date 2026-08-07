/**
 * doc-blocks.js — mcp-htmleditor
 *
 * Blocs inserables en mode document (data-doc-type="document"), sur le meme
 * modele que slide-layouts.js pour les slides. Chaque bloc expose
 * { label, icon, description, html }. Le picker modal reutilise le meme CSS.
 *
 * Les blocs titre/sous-titre/headings portent les classes doc-title, doc-subtitle,
 * doc-h1..doc-h5 pour heriter de la charte du template actif (perso, ei, standard).
 * Les balises restent semantiques (<h1>..<h5>, <p>, <table>, <ul>) pour que
 * l'export DOCX via pandoc mappe correctement vers les styles Word Heading 1-5.
 */

const DOC_BLOCKS = {

  title: {
    label: 'Titre du document',
    icon: '🏷️',
    description: 'Titre principal du document (generalement unique, en tete)',
    html: `<h1 class="doc-title" data-editable="text">Titre du document</h1>`,
  },

  subtitle: {
    label: 'Sous-titre',
    icon: '🔤',
    description: 'Sous-titre, auteur ou date sous le titre',
    html: `<p class="doc-subtitle" data-editable="text">Sous-titre, auteur, date</p>`,
  },

  heading1: {
    label: 'Titre 1 (H1)',
    icon: '1️⃣',
    description: 'Titre de partie, niveau 1',
    html: `<h1 class="doc-h1" data-editable="text">Titre de niveau 1</h1>`,
  },

  heading2: {
    label: 'Titre 2 (H2)',
    icon: '2️⃣',
    description: 'Titre de section, niveau 2',
    html: `<h2 class="doc-h2" data-editable="text">Titre de niveau 2</h2>`,
  },

  heading3: {
    label: 'Titre 3 (H3)',
    icon: '3️⃣',
    description: 'Sous-section, niveau 3',
    html: `<h3 class="doc-h3" data-editable="text">Titre de niveau 3</h3>`,
  },

  heading4: {
    label: 'Titre 4 (H4)',
    icon: '4️⃣',
    description: 'Sous-sous-section, niveau 4',
    html: `<h4 class="doc-h4" data-editable="text">Titre de niveau 4</h4>`,
  },

  heading5: {
    label: 'Titre 5 (H5)',
    icon: '5️⃣',
    description: 'Titre de dernier niveau, niveau 5',
    html: `<h5 class="doc-h5" data-editable="text">Titre de niveau 5</h5>`,
  },

  paragraph: {
    label: 'Paragraphe',
    icon: '📄',
    description: 'Bloc de texte courant',
    html: `<p data-editable="text">Redigez votre paragraphe ici.</p>`,
  },

  table: {
    label: 'Tableau',
    icon: '⊞',
    description: 'Tableau 3 colonnes par 3 lignes',
    html: `
      <table data-type="table">
        <thead>
          <tr><th>Colonne 1</th><th>Colonne 2</th><th>Colonne 3</th></tr>
        </thead>
        <tbody>
          <tr><td data-editable="text">&nbsp;</td><td data-editable="text">&nbsp;</td><td data-editable="text">&nbsp;</td></tr>
          <tr><td data-editable="text">&nbsp;</td><td data-editable="text">&nbsp;</td><td data-editable="text">&nbsp;</td></tr>
          <tr><td data-editable="text">&nbsp;</td><td data-editable="text">&nbsp;</td><td data-editable="text">&nbsp;</td></tr>
        </tbody>
      </table>`,
  },

  list: {
    label: 'Liste a puces',
    icon: '•',
    description: 'Liste a puces de trois elements',
    html: `
      <ul data-editable="text">
        <li>Premier element</li>
        <li>Deuxieme element</li>
        <li>Troisieme element</li>
      </ul>`,
  },
};
