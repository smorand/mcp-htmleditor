/**
 * slide-layouts.js — mcp-htmleditor
 *
 * Définit les 5 types de slides IBM Carbon insérables via le menu
 * "Insérer une slide". Chaque layout est un fragment HTML minimal avec
 * les attributs data-* requis (data-type, data-id, data-title, data-slide-type).
 *
 * Le placeholder {{ID}} est remplacé par un id unique à l'insertion.
 * Le placeholder {{N}} / {{TT}} sont mis à jour par la renumérotation.
 *
 * Ce fichier est chargé dans la page parente (editor.html) et les layouts
 * sont injectés dans l'iframe lors de l'insertion.
 */

const SLIDE_LAYOUTS = {

  /* ── 1. Titre général de présentation ───────────────────────── */
  title: {
    label: 'Titre de présentation',
    icon: '🎬',
    description: 'Slide de couverture (généralement unique, en première position)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="title" data-title="Titre de la présentation">
        <div class="slide-header" style="border-bottom:none; padding-top:120px;">
          <div class="slide-eyebrow" data-editable="text">Présentation</div>
          <h1 class="slide-h1" data-editable="text" style="font-size:52px;">
            <strong>Titre</strong> principal
          </h1>
          <p class="slide-subtitle" data-editable="text" style="font-size:18px;">
            Sous-titre, auteur, date ou contexte de la présentation.
          </p>
        </div>
        <div class="slide-footer">
          <span class="slide-footer-left" data-editable="text">Produit · Présentation</span>
          <span class="slide-footer-right">Slide {{N}} / {{TT}}</span>
        </div>
      </article>`,
  },

  /* ── 2. Plan / Agenda ───────────────────────────────────────── */
  agenda: {
    label: 'Plan / Agenda',
    icon: '📋',
    description: 'Sommaire de la présentation (généralement unique)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="agenda" data-title="Plan">
        <div class="slide-header">
          <div class="slide-eyebrow" data-editable="text">Sommaire · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text"><strong>Plan</strong> de la présentation</h1>
        </div>
        <div class="slide-body" data-editable="text">
          <table class="cds-structured-list">
            <tbody>
              <tr><td style="width:48px;"><strong>01</strong></td><td>Première section</td></tr>
              <tr><td><strong>02</strong></td><td>Deuxième section</td></tr>
              <tr><td><strong>03</strong></td><td>Troisième section</td></tr>
              <tr><td><strong>04</strong></td><td>Quatrième section</td></tr>
            </tbody>
          </table>
        </div>
        <div class="slide-footer">
          <span class="slide-footer-left" data-editable="text">Produit · Présentation</span>
          <span class="slide-footer-right">Slide {{N}} / {{TT}}</span>
        </div>
      </article>`,
  },

  /* ── 3. Coupure de section ──────────────────────────────────── */
  section: {
    label: 'Coupure de section',
    icon: '🔲',
    description: 'Séparateur de section (plusieurs possibles)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="section" data-title="Section"
               style="background:#161616;">
        <div class="slide-header" style="border-bottom:4px solid #4589ff; padding-top:160px;">
          <div class="slide-eyebrow" data-editable="text" style="color:#78a9ff;">Section {{N}}</div>
          <h1 class="slide-h1" data-editable="text" style="color:#f4f4f4; font-size:48px;">
            <strong>Titre</strong> de la section
          </h1>
          <p class="slide-subtitle" data-editable="text" style="color:#c6c6c6;">
            Introduction courte de la section.
          </p>
        </div>
        <div class="slide-footer" style="background:#262626; border-top-color:#393939;">
          <span class="slide-footer-left" data-editable="text" style="color:#8d8d8d;">Produit · Présentation</span>
          <span class="slide-footer-right" style="color:#6f6f6f;">Slide {{N}} / {{TT}}</span>
        </div>
      </article>`,
  },

  /* ── 4. Slide normale (texte + tuiles) ──────────────────────── */
  content: {
    label: 'Contenu standard',
    icon: '📝',
    description: 'Titre + texte et tuiles (la plus fréquente)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="content" data-title="Titre de la slide">
        <div class="slide-header">
          <div class="slide-eyebrow" data-editable="text">Section · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Titre de la <strong>slide</strong></h1>
          <p class="slide-subtitle" data-editable="text">Sous-titre optionnel.</p>
        </div>
        <div class="slide-body" data-editable="text">
          <div class="cds-grid cols-3">
            <div class="cds-tile">
              <div class="tile-eyebrow">Point 1</div>
              <div class="tile-title">Titre</div>
              <p>Description courte.</p>
            </div>
            <div class="cds-tile">
              <div class="tile-eyebrow">Point 2</div>
              <div class="tile-title">Titre</div>
              <p>Description courte.</p>
            </div>
            <div class="cds-tile">
              <div class="tile-eyebrow">Point 3</div>
              <div class="tile-title">Titre</div>
              <p>Description courte.</p>
            </div>
          </div>
        </div>
        <div class="slide-footer">
          <span class="slide-footer-left" data-editable="text">Produit · Présentation</span>
          <span class="slide-footer-right">Slide {{N}} / {{TT}}</span>
        </div>
      </article>`,
  },

  /* ── 5. Slide schéma / diagramme ────────────────────────────── */
  diagram: {
    label: 'Schéma / Diagramme',
    icon: '🗺️',
    description: 'Zone de schéma d\'architecture ou visualisation',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="diagram" data-title="Schéma">
        <div class="slide-header">
          <div class="slide-eyebrow" data-editable="text">Architecture · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Titre du <strong>schéma</strong></h1>
        </div>
        <div class="slide-body">
          <div data-type="arch-diagram"
               style="position:relative; min-height:280px; border:1px dashed #e0e0e0; padding:24px; display:flex; align-items:center; justify-content:center; gap:24px;">
            <div data-type="arch-node" data-label="Composant A" data-shape="box"
                 style="border:2px solid #0f62fe; background:#edf5ff; padding:12px 24px; font-weight:600; color:#161616;">
              Composant A
            </div>
            <span style="font-size:28px; color:#525252;">→</span>
            <div data-type="arch-node" data-label="Composant B" data-shape="box"
                 style="border:2px solid #161616; background:#f4f4f4; padding:12px 24px; font-weight:600; color:#161616;">
              Composant B
            </div>
          </div>
        </div>
        <div class="slide-footer">
          <span class="slide-footer-left" data-editable="text">Produit · Présentation</span>
          <span class="slide-footer-right">Slide {{N}} / {{TT}}</span>
        </div>
      </article>`,
  },
};
