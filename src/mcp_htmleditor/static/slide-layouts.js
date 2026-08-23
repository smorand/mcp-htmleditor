/**
 * slide-layouts.js — mcp-htmleditor
 *
 * Layouts de slides insérables via « Insérer une slide », groupés par template
 * (carbon = IBM Carbon, ei = Euro-Information, medical = présentation médicale).
 * Fragment HTML minimal avec attributs data-* requis. {{ID}} est remplacé à
 * l'insertion.
 *
 * detectTemplate(doc) → 'ei' | 'carbon' | 'medical'. getLayouts(doc) → le bon jeu.
 */

function detectTemplate(doc) {
  if (!doc) return 'carbon';
  const html = doc.documentElement.outerHTML;
  if (/--med-teal|data-doc-template="medical"/i.test(html)) return 'medical';
  if (/--ei-blue|slide-cover-logos|Euro.Information/i.test(html)) return 'ei';
  return 'carbon';
}

function getLayouts(doc) {
  return LAYOUT_SETS[detectTemplate(doc)] || LAYOUT_SETS.carbon;
}

const LAYOUT_SETS = {};

LAYOUT_SETS.carbon = {

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
          <!-- Connecteur ancré par calcul: bord droit de A (36, 47) vers bord gauche de B (64, 47).
               Voir skill/types/arch-diagram.md, jamais de flèche en glyphe posée à l'estime. -->
          <div data-type="arch-diagram"
               style="position:relative; min-height:280px; border:1px dashed #e0e0e0; padding:24px;">
            <div data-type="arch-node" data-label="Composant A" data-shape="box"
                 data-x="12.0" data-y="38.0" data-width="24.0" data-height="18.0"
                 style="position:absolute; left:12.0%; top:38.0%; width:24.0%; height:18.0%; box-sizing:border-box; display:flex; align-items:center; justify-content:center; border:2px solid #0f62fe; background:#edf5ff; font-weight:600; color:#161616;">
              Composant A
            </div>
            <div data-type="arch-edge" data-from="Composant A" data-to="Composant B" data-style="solid"
                 style="position:absolute; left:36.0%; top:47.0%; width:28.0%; height:0; border-top:1.5px solid #525252;"></div>
            <div style="position:absolute; left:64.0%; top:47.0%; width:0; height:0; border-left:7px solid #525252; border-top:4.5px solid transparent; border-bottom:4.5px solid transparent; transform:translate(-100%,-50%);"></div>
            <div data-type="arch-node" data-label="Composant B" data-shape="box"
                 data-x="64.0" data-y="38.0" data-width="24.0" data-height="18.0"
                 style="position:absolute; left:64.0%; top:38.0%; width:24.0%; height:18.0%; box-sizing:border-box; display:flex; align-items:center; justify-content:center; border:2px solid #161616; background:#f4f4f4; font-weight:600; color:#161616;">
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

/* ============================================================
   Euro-Information layouts
   Reproduit le design EI: couverture image + logos, section bleue,
   contenu/agenda/diagram avec cadre bleu (10px) et intérieur arrondi 16px,
   plus l'anneau de logo au coin bas-gauche.
   Le logo rond ({{CHEVRONS}}) et la couverture ({{COVER}}) sont récupérés
   depuis le document actif à l'insertion, ou à défaut depuis les attributs
   data-asset-* de <html> (voir editor.js resolveTemplateAssets).
   Markup du logo obligatoire: .slide-foot-logo > .logo-disc > img, seul
   dimensionné par le CSS du template (16px). Sans .logo-disc, l'image sort
   du disque blanc.
   Compteur EI: eyebrow « Catégorie · Slide 0N / TT » + .slide-foot-page,
   les deux étant remis à jour par renumberSlides().
   ============================================================ */
LAYOUT_SETS.ei = {

  title: {
    label: 'Titre de présentation',
    icon: '🎬',
    description: 'Couverture EI: image tech + logos (généralement unique)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="title" data-title="Titre de la présentation">
        <img class="slide-cover-img" src="{{COVER}}" alt="Couverture">
        <div class="slide-cover-body">
          <div class="slide-cover-title" data-editable="text">Titre de la présentation</div>
          <div class="slide-cover-subtitle" data-editable="text">Sous-titre · Mois Année</div>
        </div>
        <div class="slide-cover-logos">
          <div class="logos-left">
            <img class="logo-cm"  src="{{CM}}"  alt="Crédit Mutuel">
            <img class="logo-cic" src="{{CIC}}" alt="CIC">
          </div>
          <img class="logo-ei" src="{{EI}}" alt="Euro Information">
        </div>
      </article>`,
  },

  agenda: {
    label: 'Plan / Agenda',
    icon: '📋',
    description: 'Sommaire EI (généralement unique)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="agenda" data-title="Plan">
        <div class="slide-inner">
          <div class="slide-eyebrow" data-editable="text">Sommaire · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Plan de la <span>présentation</span></h1>
          <div class="slide-title-rule"></div>
          <div class="slide-body" data-editable="text">
            <table class="agenda-list"><tbody>
              <tr><td class="num">01</td><td>Première section</td></tr>
              <tr><td class="num">02</td><td>Deuxième section</td></tr>
              <tr><td class="num">03</td><td>Troisième section</td></tr>
            </tbody></table>
          </div>
        </div>
        <div class="slide-foot">
          <div class="slide-foot-logo"><span class="logo-disc"><img src="{{CHEVRONS}}" alt="EI"></span></div>
          <span class="slide-foot-page">{{N}}</span>
          <span class="slide-foot-title" data-editable="text">Meeting Title · Mois Année</span>
        </div>
      </article>`,
  },

  section: {
    label: 'Coupure de section',
    icon: '🔲',
    description: 'Séparateur fond bleu EI (plusieurs possibles)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="section" data-title="Section">
        <div class="slide-section-band"></div>
        <div class="slide-section-body">
          <div class="slide-section-num" data-editable="text">Section</div>
          <div class="slide-section-title" data-editable="text">Titre de la section</div>
          <div class="slide-section-sub" data-editable="text">Introduction courte de la section.</div>
        </div>
      </article>`,
  },

  content: {
    label: 'Contenu standard',
    icon: '📝',
    description: 'Titre + tuiles, cadre bleu EI (la plus fréquente)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="content" data-title="Titre de la slide">
        <div class="slide-inner">
          <div class="slide-eyebrow" data-editable="text">Section · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Titre de la <span>slide</span></h1>
          <div class="slide-title-rule"></div>
          <div class="slide-body" data-editable="text">
            <div class="cds-grid cols-3">
              <div class="cds-tile"><div class="tile-eyebrow">Point 1</div><div class="tile-title">Titre</div><p>Description courte.</p></div>
              <div class="cds-tile"><div class="tile-eyebrow">Point 2</div><div class="tile-title">Titre</div><p>Description courte.</p></div>
              <div class="cds-tile"><div class="tile-eyebrow">Point 3</div><div class="tile-title">Titre</div><p>Description courte.</p></div>
            </div>
          </div>
        </div>
        <div class="slide-foot">
          <div class="slide-foot-logo"><span class="logo-disc"><img src="{{CHEVRONS}}" alt="EI"></span></div>
          <span class="slide-foot-page">{{N}}</span>
          <span class="slide-foot-title" data-editable="text">Meeting Title · Mois Année</span>
        </div>
      </article>`,
  },

  diagram: {
    label: 'Schéma / Diagramme',
    icon: '🗺️',
    description: 'Zone de schéma d\'architecture, cadre bleu EI',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="diagram" data-title="Schéma">
        <div class="slide-inner">
          <div class="slide-eyebrow" data-editable="text">Architecture · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Titre du <span>schéma</span></h1>
          <div class="slide-title-rule"></div>
          <div class="slide-body">
            <!-- Connecteur ancré par calcul: bord droit de A (36, 47) vers bord gauche de B (64, 47).
                 Voir skill/types/arch-diagram.md, jamais de flèche en glyphe posée à l'estime. -->
            <div data-type="arch-diagram"
                 style="position:relative; min-height:220px;">
              <div data-type="arch-node" data-label="Composant A" data-shape="box"
                   data-x="12.0" data-y="38.0" data-width="24.0" data-height="18.0"
                   style="position:absolute; left:12.0%; top:38.0%; width:24.0%; height:18.0%; box-sizing:border-box; display:flex; align-items:center; justify-content:center; border:2px solid #003A8D; background:#eef3fb; font-weight:700; color:#003A8D;">Composant A</div>
              <div data-type="arch-edge" data-from="Composant A" data-to="Composant B" data-style="solid"
                   style="position:absolute; left:36.0%; top:47.0%; width:28.0%; height:0; border-top:1.5px solid #284AAA;"></div>
              <div style="position:absolute; left:64.0%; top:47.0%; width:0; height:0; border-left:7px solid #284AAA; border-top:4.5px solid transparent; border-bottom:4.5px solid transparent; transform:translate(-100%,-50%);"></div>
              <div data-type="arch-node" data-label="Composant B" data-shape="box"
                   data-x="64.0" data-y="38.0" data-width="24.0" data-height="18.0"
                   style="position:absolute; left:64.0%; top:38.0%; width:24.0%; height:18.0%; box-sizing:border-box; display:flex; align-items:center; justify-content:center; border:2px solid #284AAA; background:#f4f6f9; font-weight:700; color:#003A8D;">Composant B</div>
            </div>
          </div>
        </div>
        <div class="slide-foot">
          <div class="slide-foot-logo"><span class="logo-disc"><img src="{{CHEVRONS}}" alt="EI"></span></div>
          <span class="slide-foot-page">{{N}}</span>
          <span class="slide-foot-title" data-editable="text">Meeting Title · Mois Année</span>
        </div>
      </article>`,
  },
};

/* ============================================================
   Medical layouts (charte "medical")
   Reproduit la charte medicale: bandeau gris haut, titre + filet
   teal/orange, bande de sources bibliographiques en pied, numero de page
   seul a droite (renumerote par renumberSlides via .slide-foot-page).
   Surface sombre (class="slide dark") pour toute slide dont la preuve
   principale est une image medicale (TDM, EBUS, endoscopie, histologie).
   Chaque enfant d'une rangee porte sa largeur (w-33, w-50, w-60...): sans
   largeur explicite, l'export PPTX retombe en empilement vertical.
   Regles completes: skill/types/medical.md
   ============================================================ */
LAYOUT_SETS.medical = {

  title: {
    label: 'Couverture',
    icon: '🎬',
    description: 'Titre, orateur, établissement, congrès (généralement unique)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="title" data-title="Titre de la présentation">
        <div class="med-band"></div>
        <div class="med-cover">
          <div class="med-cover-event" data-editable="text">Congrès · Session · Ville</div>
          <div class="med-cover-title" data-editable="text">Titre de la <span>présentation</span></div>
          <div class="med-rule"><i></i><b></b></div>
          <div class="med-cover-sub" data-editable="text">Sous-titre: question clinique traitée en une phrase.</div>
          <div class="med-author" data-editable="text">
            <div class="author-name">Dr Prénom Nom, MD</div>
            <div class="author-role">Fonction · Unité</div>
            <div class="author-org">Établissement, Ville · Affiliation académique</div>
            <div class="author-mail">prenom.nom@exemple.org</div>
          </div>
        </div>
        <div class="med-cover-foot">
          <span class="med-cover-date" data-editable="text">Jour Mois Année</span>
          <div class="med-logos"></div>
        </div>
      </article>`,
  },

  disclosure: {
    label: 'Liens d\'intérêt',
    icon: '⚖️',
    description: 'Déclaration de conflits d\'intérêts, obligatoire en position 2',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="disclosure" data-title="Liens d'intérêt">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Déclaration · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Liens d'<span>intérêt</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <table class="med-table compact" data-editable="text">
            <tbody>
              <tr><td style="width:38%;"><strong>Consultant</strong></td><td>Aucun</td></tr>
              <tr><td><strong>Bureau des orateurs</strong></td><td>Aucun</td></tr>
              <tr><td><strong>Financement de recherche</strong></td><td>Aucun</td></tr>
              <tr><td><strong>Prêt de matériel</strong></td><td>Aucun</td></tr>
              <tr><td><strong>Redevances / propriété intellectuelle</strong></td><td>Aucune</td></tr>
            </tbody>
          </table>
          <p class="med-caption" style="margin-top:10px;" data-editable="text">
            Cette présentation mentionne un usage hors AMM de : aucun
          </p>
        </div>
        <div class="med-foot">
          <div class="med-sources"></div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  agenda: {
    label: 'Plan',
    icon: '📋',
    description: 'Sommaire numéroté, 4 à 5 lignes (généralement unique)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="agenda" data-title="Plan">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Sommaire · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Plan de la <span>présentation</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <table class="med-agenda" data-editable="text"><tbody>
            <tr><td class="num">01</td><td>Première partie<span class="agenda-sub">Précision en une ligne</span></td></tr>
            <tr><td class="num">02</td><td>Deuxième partie</td></tr>
            <tr><td class="num">03</td><td>Troisième partie</td></tr>
            <tr><td class="num">04</td><td>Messages à retenir</td></tr>
          </tbody></table>
        </div>
        <div class="med-foot">
          <div class="med-sources"></div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  section: {
    label: 'Coupure de section',
    icon: '🔲',
    description: 'Séparateur gris pleine surface (plusieurs possibles)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="section" data-title="Section">
        <div class="med-section">
          <div class="med-rule"><i></i><b></b></div>
          <div class="med-section-title" data-editable="text">En pratique</div>
          <div class="med-section-sub" data-editable="text">Introduction de la section en une phrase.</div>
        </div>
      </article>`,
  },

  content: {
    label: 'Texte + images',
    icon: '📝',
    description: 'Puces + bande de vignettes légendées (la plus fréquente)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="content" data-title="Titre de la slide">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Section · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Indications : <span>précision</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <ul class="med-list" data-editable="text">
            <li><strong>Message principal</strong> de la slide, une phrase.</li>
            <li>Résultat chiffré: sensibilité <strong>94 %</strong> (IC 95 % 88-97).</li>
            <li>Conséquence pratique pour la décision clinique.</li>
          </ul>
          <div class="med-strip" style="margin-top:12px;">
            <figure class="med-figure w-33">
              <img src="" alt="Description de l'image">
              <figcaption class="med-caption" data-editable="text">Légende courte de la vignette.</figcaption>
            </figure>
            <figure class="med-figure w-33">
              <img src="" alt="Description de l'image">
              <figcaption class="med-caption" data-editable="text">Légende courte de la vignette.</figcaption>
            </figure>
            <figure class="med-figure w-33">
              <img src="" alt="Description de l'image">
              <figcaption class="med-caption" data-editable="text">Légende courte de la vignette.</figcaption>
            </figure>
          </div>
        </div>
        <div class="med-foot">
          <div class="med-sources" data-editable="text">
            <p class="med-source"><span class="src-title">Titre de l'article</span> : Auteurs. Journal. Année;Vol(N):pages.</p>
          </div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  image: {
    label: 'Image + commentaire',
    icon: '🩻',
    description: 'Surface sombre: imagerie à gauche, lecture commentée à droite',
    html: `
      <article class="slide dark" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="image" data-title="Image commentée">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Imagerie · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Ce que montre <span>l'image</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <div class="med-split">
            <figure class="med-figure w-60">
              <img src="" alt="Description de l'image">
              <figcaption class="med-caption" data-editable="text">Modalité, plan, fenêtre. Repère anatomique.</figcaption>
            </figure>
            <div class="med-comment w-40">
              <div class="med-comment-head" data-editable="text">Ce qu'il faut regarder</div>
              <ul class="med-list" data-editable="text">
                <li>Premier élément sémiologique.</li>
                <li>Deuxième élément.</li>
                <li>Conséquence pour le geste.</li>
              </ul>
            </div>
          </div>
        </div>
        <div class="med-foot">
          <div class="med-sources" data-editable="text">
            <p class="med-source">Courtoisie de l'unité, image anonymisée, consentement obtenu.</p>
          </div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  grid: {
    label: 'Mosaïque d\'images',
    icon: '🖼️',
    description: 'Surface sombre: 4 images maximum, légendes repérées A à D',
    html: `
      <article class="slide dark" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="grid" data-title="Mosaïque">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Iconographie · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Quatre <span>aspects</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <div class="med-grid">
            <div class="med-strip">
              <figure class="med-figure w-50">
                <img src="" alt="Description">
                <figcaption class="med-caption" data-editable="text"><span class="med-badge">A</span>Légende A.</figcaption>
              </figure>
              <figure class="med-figure w-50">
                <img src="" alt="Description">
                <figcaption class="med-caption" data-editable="text"><span class="med-badge">B</span>Légende B.</figcaption>
              </figure>
            </div>
            <div class="med-strip">
              <figure class="med-figure w-50">
                <img src="" alt="Description">
                <figcaption class="med-caption" data-editable="text"><span class="med-badge">C</span>Légende C.</figcaption>
              </figure>
              <figure class="med-figure w-50">
                <img src="" alt="Description">
                <figcaption class="med-caption" data-editable="text"><span class="med-badge">D</span>Légende D.</figcaption>
              </figure>
            </div>
          </div>
        </div>
        <div class="med-foot">
          <div class="med-sources" data-editable="text">
            <p class="med-source">Courtoisie de l'unité, images anonymisées.</p>
          </div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  compare: {
    label: 'Avant / après',
    icon: '🔀',
    description: 'Deux images comparables (même fenêtre, même zoom)',
    html: `
      <article class="slide dark" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="compare" data-title="Avant / après">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Évolution · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Avant et <span>après</span> le geste</h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <div class="med-compare">
            <div class="w-50">
              <span class="med-chip" data-editable="text">Avant · J0</span>
              <figure class="med-figure">
                <img src="" alt="Avant">
                <figcaption class="med-caption" data-editable="text">Même fenêtre, même zoom, même orientation.</figcaption>
              </figure>
            </div>
            <div class="w-50">
              <span class="med-chip after" data-editable="text">Après · J+14</span>
              <figure class="med-figure">
                <img src="" alt="Après">
                <figcaption class="med-caption" data-editable="text">Même fenêtre, même zoom, même orientation.</figcaption>
              </figure>
            </div>
          </div>
          <div class="med-delta" data-editable="text">Lumière trachéale 2 mm → 11 mm</div>
        </div>
        <div class="med-foot">
          <div class="med-sources" data-editable="text">
            <p class="med-source">Courtoisie de l'unité, images anonymisées.</p>
          </div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  columns: {
    label: 'Texte en colonnes',
    icon: '🧱',
    description: 'Deux ou trois colonnes parallèles (taxonomie, diagnostics)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="columns" data-title="Colonnes">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Section · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Trois <span>situations</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <div class="med-cols">
            <div class="med-col w-33">
              <div class="med-col-head teal" data-editable="text">Situation 1</div>
              <ul class="med-list" data-editable="text"><li>Élément.</li><li>Élément.</li></ul>
            </div>
            <div class="med-col w-33">
              <div class="med-col-head" data-editable="text">Situation 2</div>
              <ul class="med-list" data-editable="text"><li>Élément.</li><li>Élément.</li></ul>
            </div>
            <div class="med-col w-33">
              <div class="med-col-head orange" data-editable="text">Situation 3</div>
              <ul class="med-list" data-editable="text"><li>Élément.</li><li>Élément.</li></ul>
            </div>
          </div>
        </div>
        <div class="med-foot">
          <div class="med-sources"></div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  case: {
    label: 'Cas clinique',
    icon: '🧑‍⚕️',
    description: 'Anamnèse + expositions + chronologie relative (anonymisé)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="case" data-title="Cas clinique">
        <div class="med-band"></div>
        <span class="med-case-chip" data-editable="text">CAS 1 · 58 ans, H, ex-fumeur 40 PA</span>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Cas clinique · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Histoire de la <span>maladie</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <div class="med-cols">
            <div class="med-col w-50">
              <div class="med-col-head teal" data-editable="text">Anamnèse</div>
              <ul class="med-list" data-editable="text">
                <li>Motif de consultation, durée.</li>
                <li>Comorbidité pertinente.</li>
                <li>Traitements déjà reçus.</li>
              </ul>
            </div>
            <div class="med-col w-50">
              <div class="med-col-head orange" data-editable="text">Expositions et risque</div>
              <ul class="med-list" data-editable="text">
                <li>Tabac, professionnel, environnemental.</li>
                <li>Antécédents familiaux.</li>
              </ul>
            </div>
          </div>
          <div class="med-timeline" data-editable="text">
            <div class="tl-step w-33"><b>J0</b>Découverte</div>
            <div class="tl-step w-33"><b>J+14</b>Prélèvement</div>
            <div class="tl-step w-33"><b>M+3</b>Réévaluation</div>
          </div>
          <p class="med-caption" style="margin-top:8px;" data-editable="text">
            Cas anonymisé, consentement écrit obtenu pour l'usage pédagogique.
          </p>
        </div>
        <div class="med-foot">
          <div class="med-sources"></div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  steps: {
    label: 'Étapes de procédure',
    icon: '🔧',
    description: 'Encadré d\'alerte + 3 étapes numérotées (geste technique)',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="steps" data-title="Étapes">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">En pratique · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Manipulation de <span>l'aiguille</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <div class="med-callout warn">
            <div>
              <div class="callout-title" data-editable="text">Risque à connaître</div>
              <div class="callout-body" data-editable="text">Formulation de l'erreur à ne pas commettre.</div>
            </div>
          </div>
          <div class="med-steps" style="margin-top:12px;">
            <div class="med-step w-33">
              <span class="step-num">1</span>
              <div class="step-title" data-editable="text">Première étape</div>
              <p data-editable="text">Consigne opératoire, une à deux lignes.</p>
            </div>
            <div class="med-step w-33">
              <span class="step-num">2</span>
              <div class="step-title" data-editable="text">Deuxième étape</div>
              <p data-editable="text">Consigne opératoire.</p>
            </div>
            <div class="med-step w-33">
              <span class="step-num">3</span>
              <div class="step-title" data-editable="text">Troisième étape</div>
              <p data-editable="text">Consigne opératoire.</p>
            </div>
          </div>
        </div>
        <div class="med-foot">
          <div class="med-sources"></div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  table: {
    label: 'Tableau',
    icon: '📊',
    description: 'Comparaison de techniques, résultats biologiques',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="table" data-title="Tableau">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Comparaison · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Moyens de <span>prélèvement</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <table class="med-table" data-editable="text">
            <thead><tr><th>Technique</th><th>Calibre</th><th>Rendement</th><th>Limite</th></tr></thead>
            <tbody>
              <tr><td><strong>FNA</strong></td><td>19-25 G</td><td>Élevé</td><td>Cytologie seule</td></tr>
              <tr><td><strong>FNB</strong></td><td>19-22 G</td><td>Élevé</td><td>Coût</td></tr>
              <tr><td><strong>Cryosonde</strong></td><td>1,1 mm</td><td>Tissu intact</td><td>Saignement <span class="abn">2 %</span></td></tr>
            </tbody>
          </table>
          <div class="med-callout">
            <div>
              <div class="callout-title" data-editable="text">À retenir</div>
              <div class="callout-body" data-editable="text">Lecture du tableau en une phrase.</div>
            </div>
          </div>
        </div>
        <div class="med-foot">
          <div class="med-sources" data-editable="text">
            <p class="med-source"><span class="src-title">Titre de l'article</span> : Auteurs. Journal. Année;Vol(N):pages.</p>
          </div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  keymessage: {
    label: 'Message clé',
    icon: '💬',
    description: 'Une phrase affirmative plein cadre, plus 3 chiffres clés',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="keymessage" data-title="Message clé">
        <div class="med-band"></div>
        <div class="slide-body">
          <div class="med-key">
            <div class="med-key-text" data-editable="text">Affirmation en une phrase, pas un titre de sujet.</div>
            <div class="med-key-sub" data-editable="text">Précision ou condition d'application.</div>
            <div class="med-stats" style="margin-top:16px;">
              <div class="med-stat w-33"><div class="med-stat-value" data-editable="text">94 %</div><div class="med-stat-label" data-editable="text">Sensibilité</div></div>
              <div class="med-stat w-33"><div class="med-stat-value" data-editable="text">0,05 %</div><div class="med-stat-label" data-editable="text">Complications</div></div>
              <div class="med-stat w-33"><div class="med-stat-value" data-editable="text">n = 214</div><div class="med-stat-label" data-editable="text">Patients</div></div>
            </div>
          </div>
        </div>
        <div class="med-foot">
          <div class="med-sources"></div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  takehome: {
    label: 'Messages à retenir',
    icon: '✅',
    description: 'Exactement 3 phrases, reprises des slides clés',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="takehome" data-title="Messages à retenir">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Conclusion · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Messages à <span>retenir</span></h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <div class="med-takehome" data-editable="text">
            <div class="med-th-row">Première phrase à retenir, complète.<sup>1</sup></div>
            <div class="med-th-row">Deuxième phrase à retenir.<sup>2</sup></div>
            <div class="med-th-row">Troisième phrase à retenir.<sup>3</sup></div>
          </div>
        </div>
        <div class="med-foot">
          <div class="med-sources"></div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  references: {
    label: 'Bibliographie',
    icon: '📚',
    description: 'Liste Vancouver numérotée, 10 entrées maximum par slide',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="references" data-title="Bibliographie">
        <div class="med-band"></div>
        <div class="med-head">
          <div class="slide-eyebrow" data-editable="text">Références · Slide {{N}} / {{TT}}</div>
          <h1 class="slide-h1" data-editable="text">Bibliographie</h1>
          <div class="med-rule"><i></i><b></b></div>
        </div>
        <div class="slide-body">
          <ol class="med-refs" data-editable="text">
            <li>Auteur A, Auteur B, Auteur C. Titre de l'article. <em>Journal abrégé</em>. Année;Vol(N):pages. doi:10.xxxx/yyyy</li>
            <li>Figure 2 reproduite de : Auteur D, et al. Titre. <em>Journal abrégé</em>. Année;Vol(N):pages.</li>
            <li>Société savante. Titre de la recommandation. Version. Année. Consulté le JJ mois AAAA. URL</li>
          </ol>
        </div>
        <div class="med-foot">
          <div class="med-sources"></div>
          <span class="slide-foot-page">{{N}}</span>
        </div>
      </article>`,
  },

  thanks: {
    label: 'Remerciements',
    icon: '🙏',
    description: 'Slide de clôture bleu nuit: contact et équipe',
    html: `
      <article class="slide" id="{{ID}}" data-type="slide" data-id="{{ID}}"
               data-slide-type="thanks" data-title="Remerciements">
        <div class="med-thanks">
          <div class="med-rule light"><i></i><b></b></div>
          <div class="med-thanks-title" data-editable="text">Merci de votre attention</div>
          <div class="med-thanks-sub" data-editable="text">Questions ?</div>
          <div class="med-contact" data-editable="text">
            <strong>Dr Prénom Nom</strong><br>
            Fonction · Unité, Établissement<br>
            prenom.nom@exemple.org
          </div>
        </div>
        <div class="med-ack" data-editable="text">
          Remerciements : équipe d'endoscopie, anatomopathologie, radiologie, chirurgie thoracique, équipe infirmière.
        </div>
      </article>`,
  },
};
