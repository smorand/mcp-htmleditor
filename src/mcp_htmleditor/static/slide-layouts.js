/**
 * slide-layouts.js — mcp-htmleditor
 *
 * Layouts de slides insérables via « Insérer une slide », groupés par template
 * (carbon = IBM Carbon, ei = Euro-Information, medical = présentation médicale).
 * Fragment HTML minimal avec attributs data-* requis. {{ID}} est remplacé à
 * l'insertion.
 *
 * detectTemplate(doc) → 'ei' | 'carbon' | 'medical' | 'breathe'. getLayouts(doc) → le bon jeu.
 * Breathe (SPEC-0023 DEC-001): la déclaration data-doc-template gagne, puis le marqueur --breathe-ice.
 */

function detectTemplate(doc) {
  if (!doc) return 'carbon';
  const declared = doc.documentElement.getAttribute('data-doc-template');
  const html = doc.documentElement.outerHTML;
  const css = Array.from(doc.querySelectorAll('style'), (s) => s.textContent).join('').replace(/\/\*[\s\S]*?\*\//g, '');
  if (declared === 'breathe' || (declared !== 'medical' && css.includes('--breathe-ice'))) return 'breathe';
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
               Voir mcp-htmleditor skill --type arch-diagram, jamais de flèche en glyphe posée à l'estime. -->
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
   data-asset-* de <html> (voir editor-slides.js resolveTemplateAssets).
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
                 Voir mcp-htmleditor skill --type arch-diagram, jamais de flèche en glyphe posée à l'estime. -->
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

/* breathe-layouts:begin */
/* Generated by tools/sync_breathe_layouts.py from templates/reference/slides/breathe.html (SPEC-0023):
   edit the reference deck, then run make sync-breathe-layouts. */
LAYOUT_SETS.breathe = {
  "cover": {label: "Cover", icon: "🎬", description: "Navy title pane, ice pane with the botanical emblem; the airway starts here.", html: "<article class=\"slide med-bg-cover-s0\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"title\" data-title=\"Cover\" style=\"background-color:var(--med-ice)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-cover-pane w-60 med-px-600\">\n          <div class=\"med-kicker med-on-deep\" data-editable=\"text\">Congress 2026 · City · 1 to 4 Month 2026</div>\n          <h1 class=\"med-cover-title\" data-editable=\"text\"><span class=\"med-cover-line\">A clear title that states</span> <span class=\"med-cover-big\">The Key Idea</span> <span class=\"med-cover-line\">of this talk</span></h1>\n          <div class=\"med-cover-sub\" data-editable=\"text\">One line on the angle of the talk</div>\n          <div class=\"med-push\">\n            <div class=\"med-author-name\" data-editable=\"text\">Dr Lamya CHRIF MORAND</div>\n            <div class=\"med-aff\"><i class=\"med-ico med-ico-scope-dark\"></i><span data-editable=\"text\">Interventional Pulmonology Unit</span></div>\n            <div class=\"med-aff\"><i class=\"med-ico med-ico-hospital-dark\"></i><span data-editable=\"text\">International Hospital Kenitra</span></div>\n            <div class=\"med-aff\"><i class=\"med-ico med-ico-cap-dark\"></i><span data-editable=\"text\">Ibn Tofail University, Kenitra, Morocco</span></div>\n          </div>\n        </div>\n        <div class=\"med-pane w-40 med-px-360\">\n          <figure class=\"med-cover-emblem\">\n            <img class=\"med-disc\" data-asset=\"logo-disc.png\" src=\"\" alt=\"Breathe Well, Live Better: botanical lungs emblem of Dr Lamya CHRIF MORAND\">\n            <img class=\"med-partner\" data-asset=\"wiip-strong-logo-alpha.png\" src=\"\" alt=\"WiIP Strong logo\">\n          </figure>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-navy\" style=\"left:72px\" aria-hidden=\"true\">The patient pathway</span>\n      <aside data-role=\"speaker-notes\">Cover. Background med-bg-cover-s0 (airway starts with a node on the left, label \"The patient pathway\"). Title: two calm lines around one big key phrase in aqua (.med-cover-big, 62 px, about 16 characters). Affiliation lines: circled icon (med-ico-*-dark, 28 px) plus text. The emblem disc and the partner logo sit on the ice pane; remove the partner logo if not relevant. Logo B never on the same slide as the stethoscope watermark.</aside>\n    </article>"},
  "disclosure": {label: "Disclosure", icon: "⚖️", description: "Disclosure", html: "<article class=\"slide med-bg-side-s0\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"disclosure\" data-title=\"Disclosure\" style=\"background-color:var(--med-ice)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-side-pane w-30 med-px-300\">\n          <div class=\"med-kicker med-on-deep\" data-editable=\"text\">Conflicts of interest</div>\n          <h1 class=\"med-title med-on-deep\" data-editable=\"text\">Disclosure</h1>\n        </div>\n        <div class=\"med-pane med-main-pane w-70 med-px-660\">\n          <div class=\"med-disc\">\n            <i class=\"med-ico med-ico-shield-ring med-s52\"></i>\n            <div>\n              <div class=\"med-disc-label\" data-editable=\"text\">Financial relationships with ineligible companies, past 24 months</div>\n              <div class=\"med-disc-value\" data-editable=\"text\">None</div>\n            </div>\n          </div>\n          <div class=\"med-disc\">\n            <i class=\"med-ico med-ico-doc-ring med-s52\"></i>\n            <div>\n              <div class=\"med-disc-label\" data-editable=\"text\">Off label use discussed in this talk</div>\n              <div class=\"med-disc-value\" data-editable=\"text\">None</div>\n            </div>\n          </div>\n          <div class=\"med-dbl med-gap-l\"><i class=\"med-dbl-tick\"></i><div class=\"med-note\" data-editable=\"text\">Devices and techniques are named generically, without brand names.</div></div>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-sources\"></div>\n            <span class=\"slide-foot-page\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <aside data-role=\"speaker-notes\">Disclosure, position 2, read aloud. Wording of the congress (ATS wording by default). Background med-bg-side-s0: navy side pane 300 px, airway not started yet.</aside>\n    </article>"},
  "pathway": {label: "Pathway", icon: "📋", description: "The airway zoomed, four stages as stations at x 190/397/603/810.", html: "<article class=\"slide med-bg-track-s0\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"agenda\" data-title=\"Pathway\" style=\"background-color:var(--med-ice)\">\n      <div class=\"med-body\">\n        <div class=\"med-kicker\" data-editable=\"text\">Outline</div>\n        <h1 class=\"med-title\" data-editable=\"text\">Following the <span class=\"med-hl\">patient pathway</span></h1>\n        <div class=\"med-lead med-gap-s\" data-editable=\"text\">One line that frames the talk: the problem is <strong>not only clinical</strong>.</div>\n        <div class=\"med-foot-row med-push\">\n          <div class=\"med-sources\"></div>\n          <span class=\"slide-foot-page\">{{N}}</span>\n        </div>\n      </div>\n      <div class=\"med-track\">\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-search-done med-s88\"></i><div class=\"med-station-num\">01</div><div class=\"med-station-name\" data-editable=\"text\">Detect</div><div class=\"med-station-sub\" data-editable=\"text\">Short sub line</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-scope-done med-s88\"></i><div class=\"med-station-num\">02</div><div class=\"med-station-name\" data-editable=\"text\">Diagnose</div><div class=\"med-station-sub\" data-editable=\"text\">Short sub line</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-microscope-done med-s88\"></i><div class=\"med-station-num\">03</div><div class=\"med-station-name\" data-editable=\"text\">Characterise</div><div class=\"med-station-sub\" data-editable=\"text\">Short sub line</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-clock-done med-s88\"></i><div class=\"med-station-num\">04</div><div class=\"med-station-name\" data-editable=\"text\">Treat on time</div><div class=\"med-station-sub\" data-editable=\"text\">Short sub line</div></div>\n      </div>\n      <aside data-role=\"speaker-notes\">Pathway (agenda). Background med-bg-track-s0: the airway zoomed at y 300, start node on the left. Four stations, one icon each (med-ico-*-done, 88 px). Keep the same four stage names in the dividers and the rail labels.</aside>\n    </article>"},
  "part-2-diagnose": {label: "Part 2: Diagnose", icon: "📍", description: "Chapter band with the cabinet watermark, the airway zoomed below (stage 2 here).", html: "<article class=\"slide med-bg-divider-s2\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"section\" data-title=\"Part 2: Diagnose\" style=\"background-color:var(--med-navy)\">\n      <div class=\"med-chapter-band\">\n        <div class=\"med-chapter-num w-25\" data-editable=\"text\">02</div>\n        <div class=\"med-dbl med-on-deep w-70\"><i class=\"med-dbl-tick med-on-deep\"></i>\n          <div class=\"med-kicker med-on-deep\" data-editable=\"text\">Part 2 · The patient pathway</div>\n          <div class=\"med-chapter-title\" data-editable=\"text\">Diagnose</div>\n          <div class=\"med-chapter-q\" data-editable=\"text\">The question this part answers, in one line.</div>\n        </div>\n      </div>\n      <div class=\"med-track med-divider-track\">\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-search-done med-s88\"></i><div class=\"med-station-num\">01</div><div class=\"med-station-name\">Detect</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-scope-now med-s88\"></i><div class=\"med-station-num med-now\">02</div><div class=\"med-station-name med-now\">Diagnose</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-microscope-todo med-s88\"></i><div class=\"med-station-num med-todo\">03</div><div class=\"med-station-name med-todo\">Characterise</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-clock-todo med-s88\"></i><div class=\"med-station-num med-todo\">04</div><div class=\"med-station-name med-todo\">Treat on time</div></div>\n      </div>\n      <aside data-role=\"speaker-notes\">Section divider. Background med-bg-divider-sN (N = current stage 1 to 4): navy band with the stethoscope and lungs watermark, airway at y 420 solid up to stage N. Icons: -done before N, -now at N, -todo after N; text classes med-now / med-todo. No page number.</aside>\n    </article>"},
  "key-figures": {label: "Key figures", icon: "🔢", description: "The count on ice (teal), the alarm on navy (pink).", html: "<article class=\"slide med-bg-split-s1\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"keymessage\" data-title=\"Key figures\" style=\"background-color:var(--med-navy)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-fig-pane w-50 med-px-480\">\n          <div class=\"med-fig-head\">\n            <h1 class=\"med-title\" data-editable=\"text\">The title states <span class=\"med-hl\">the message</span></h1>\n          </div>\n          <div class=\"med-num\" data-editable=\"text\">1,234</div>\n          <div class=\"med-num-label\" data-editable=\"text\">what the number counts</div>\n          <div class=\"med-sources med-push\" data-editable=\"text\">\n            <p class=\"med-source\"><span class=\"src-title\">Short title of the source</span>: Author A, et al. Journal. 2026.</p>\n          </div>\n        </div>\n        <div class=\"med-pane med-fig-pane med-right w-50 med-px-480\">\n          <div class=\"med-fig-head\">\n            <div class=\"med-fig-icon\"><i class=\"med-ico med-ico-lungs-dark med-s52\"></i><div class=\"med-kicker med-on-deep\" data-editable=\"text\">Population · year</div></div>\n          </div>\n          <div class=\"med-num med-alarm\" data-editable=\"text\">567</div>\n          <div class=\"med-num-label med-on-deep\" data-editable=\"text\">the alarm figure (deaths, delays, late stage)</div>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-note med-on-deep\" data-editable=\"text\">One italic line on what the two figures mean together.</div>\n            <span class=\"slide-foot-page med-on-deep\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-ice\" style=\"left:206px\" aria-hidden=\"true\"><b>01</b>Detect</span>\n      <aside data-role=\"speaker-notes\">Key figures. Background med-bg-split-sN: ice half left, navy half right. The neutral count in teal on ice, the alarm in pink on navy (pink fails contrast on light surfaces). Numbers 128 px, about 5 characters. Rail label: left = station x + 16 (206, 413, 619), station 4 uses right:166px.</aside>\n    </article>"},
  "key-figures-deep": {label: "Key figures, deep", icon: "🔢", description: "Two alarm figures on navy.", html: "<article class=\"slide med-bg-deep-s1\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"keymessage\" data-title=\"Key figures, deep\" style=\"background-color:var(--med-navy)\">\n      <div class=\"med-body\">\n        <h1 class=\"med-title med-on-deep\" data-editable=\"text\">Two alarms, <span class=\"med-hl-aqua\">one pattern</span></h1>\n        <div class=\"med-figs-deep\">\n          <div class=\"med-fig-col w-50\">\n            <div class=\"med-kicker med-on-deep\" data-editable=\"text\">Cohort A · year</div>\n            <div class=\"med-num med-alarm med-md\" data-editable=\"text\">79.5%</div>\n            <div class=\"med-num-label med-on-deep\" data-editable=\"text\">what the figure measures (n patients)</div>\n          </div>\n          <div class=\"med-fig-col w-50\">\n            <div class=\"med-kicker med-on-deep\" data-editable=\"text\">Cohort B · year</div>\n            <div class=\"med-num med-alarm med-md\" data-editable=\"text\">72%</div>\n            <div class=\"med-num-label med-on-deep\" data-editable=\"text\">what the figure measures (n patients)</div>\n          </div>\n        </div>\n        <div class=\"med-note med-on-deep med-gap-l\" data-editable=\"text\">One italic line that qualifies the figures.</div>\n        <div class=\"med-foot-row med-push\">\n          <div class=\"med-sources\" data-editable=\"text\">\n            <p class=\"med-source med-on-deep\"><span class=\"src-title\">Short title of the source</span>: Author A, et al. Journal. 2026.</p>\n          </div>\n          <span class=\"slide-foot-page med-on-deep\">{{N}}</span>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-navy\" style=\"left:206px\" aria-hidden=\"true\"><b>01</b>Detect</span>\n      <aside data-role=\"speaker-notes\">Variant of key figures when both figures are alarms. Background med-bg-deep-sN. Numbers 104 px (med-md), up to 6 characters each.</aside>\n    </article>"},
  "statement": {label: "Statement", icon: "📍", description: "Statement on ice", html: "<article class=\"slide med-bg-ice-s2\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"section\" data-title=\"Statement\" style=\"background-color:var(--med-ice)\">\n      <div class=\"med-statement\">\n        <div class=\"med-quote\" aria-hidden=\"true\">“</div>\n        <div class=\"med-statement-text\" data-editable=\"text\">One sentence the room should remember, with <span class=\"med-hl\">one highlight</span>.</div>\n      </div>\n      <span class=\"med-rail-label med-on-ice\" style=\"left:413px\" aria-hidden=\"true\"><b>02</b>Diagnose</span>\n      <aside data-role=\"speaker-notes\">Statement. Background med-bg-ice-sN. 40 px Georgia, 2 to 3 lines. A pause slide: say it, then wait.</aside>\n    </article>"},
  "content-with-picture": {label: "Content with picture", icon: "📝", description: "Check list left, picture on the navy panel.", html: "<article class=\"slide med-bg-image-s2\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"content\" data-title=\"Content with picture\" style=\"background-color:#FFFFFF\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-text-pane w-60 med-px-540\">\n          <div class=\"med-kicker\" data-editable=\"text\">Topic</div>\n          <h1 class=\"med-title\" data-editable=\"text\">The title states <span class=\"med-hl\">the message</span></h1>\n          <ul class=\"med-checks\" data-editable=\"text\">\n            <li class=\"med-check\"><i class=\"med-ico med-ico-check-solid\"></i>First point, with <strong>the key words in bold</strong>.</li>\n            <li class=\"med-check\"><i class=\"med-ico med-ico-check-solid\"></i>Second point, two lines at most.</li>\n            <li class=\"med-check\"><i class=\"med-ico med-ico-check-solid\"></i>Third point.</li>\n          </ul>\n          <div class=\"med-dbl med-push\"><i class=\"med-dbl-tick\"></i><div class=\"med-take\" data-editable=\"text\">The takeaway in one line.</div></div>\n        </div>\n        <div class=\"med-pane med-pic-pane w-40 med-px-420\">\n          <div class=\"med-pic-frame\"><img class=\"med-pic\" data-asset=\"sample-clinical-b.jpg\" src=\"\" alt=\"Sample clinical image\"><div class=\"med-caption med-on-deep\" data-editable=\"text\">What the picture shows, in one line.</div></div>\n          <div class=\"med-pic-text\">\n            <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source\">Image: origin, year. Anonymised.</p></div>\n            <span class=\"slide-foot-page\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-white\" style=\"left:413px\" aria-hidden=\"true\"><b>02</b>Diagnose</span>\n      <aside data-role=\"speaker-notes\">Content with picture. Background med-bg-image-sN: navy panel 420 x 430 bleeding top right. Landscape picture 372 px wide, caption on the panel, source under it. Check icons: med-ico-check-solid or any med-ico-*-ring.</aside>\n    </article>"},
  "content-with-card": {label: "Content with card", icon: "📝", description: "Content with a card (no picture)", html: "<article class=\"slide med-bg-white-s2\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"content\" data-title=\"Content with card\" style=\"background-color:#FFFFFF\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-text-pane w-60 med-px-600\">\n          <div class=\"med-kicker\" data-editable=\"text\">Topic</div>\n          <h1 class=\"med-title\" data-editable=\"text\">The title states <span class=\"med-hl\">the message</span></h1>\n          <ul class=\"med-checks\" data-editable=\"text\">\n            <li class=\"med-check\"><i class=\"med-ico med-ico-people-ring\"></i>First point, with <strong>the key words in bold</strong>.</li>\n            <li class=\"med-check\"><i class=\"med-ico med-ico-coins-ring\"></i>Second point, two lines at most.</li>\n            <li class=\"med-check\"><i class=\"med-ico med-ico-map-ring\"></i>Third point.</li>\n          </ul>\n          <div class=\"med-dbl med-push\"><i class=\"med-dbl-tick\"></i><div class=\"med-take\" data-editable=\"text\">The takeaway in one line.</div></div>\n        </div>\n        <div class=\"med-pane med-card-pane w-40 med-px-360\">\n          <div class=\"med-card\">\n            <div class=\"med-kicker\" data-editable=\"text\">In practice</div>\n            <div class=\"med-card-text\" data-editable=\"text\">A short panel: a definition, a protocol step or a recommendation, four lines at most.</div>\n          </div>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source\"><span class=\"src-title\">Source</span>: Author A, et al. Journal. 2026.</p></div>\n            <span class=\"slide-foot-page\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-white\" style=\"left:413px\" aria-hidden=\"true\"><b>02</b>Diagnose</span>\n      <aside data-role=\"speaker-notes\">Variant of content without a picture: an ice card with a teal top rule. Background med-bg-white-sN.</aside>\n    </article>"},
  "table": {label: "Table", icon: "📊", description: "Table", html: "<article class=\"slide med-bg-white-s2\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"table\" data-title=\"Table\" style=\"background-color:#FFFFFF\">\n      <div class=\"med-body\">\n        <div class=\"med-kicker\" data-editable=\"text\">Topic</div>\n        <h1 class=\"med-title\" data-editable=\"text\">The title states <span class=\"med-hl\">the message</span></h1>\n        <table class=\"med-table\" data-type=\"table\" data-style=\"striped\">\n          <colgroup><col style=\"width:34%\"><col style=\"width:30%\"><col style=\"width:36%\"></colgroup>\n          <thead>\n            <tr><th>Technique</th><th>Use</th><th>What it needs</th></tr>\n          </thead>\n          <tbody>\n            <tr><td class=\"med-cell\" data-editable=\"text\"><strong>Row one</strong></td><td class=\"med-cell\" data-editable=\"text\">Short cell</td><td class=\"med-cell\" data-editable=\"text\">Short cell</td></tr>\n            <tr><td class=\"med-cell\" data-editable=\"text\"><strong>Row two</strong></td><td class=\"med-cell\" data-editable=\"text\">Short cell</td><td class=\"med-cell\" data-editable=\"text\">Short cell</td></tr>\n            <tr><td class=\"med-cell\" data-editable=\"text\"><strong>Row three</strong></td><td class=\"med-cell\" data-editable=\"text\">Short cell</td><td class=\"med-cell\" data-editable=\"text\">Short cell</td></tr>\n          </tbody>\n        </table>\n        <div class=\"med-dbl med-gap-l\"><i class=\"med-dbl-tick\"></i><div class=\"med-take\" data-editable=\"text\">The takeaway in one line.</div></div>\n        <div class=\"med-foot-row med-push\">\n          <div class=\"med-sources\" data-editable=\"text\">\n            <p class=\"med-source\"><span class=\"src-title\">Source</span>: Author A, et al. Journal. 2026.</p>\n          </div>\n          <span class=\"slide-foot-page\">{{N}}</span>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-white\" style=\"left:413px\" aria-hidden=\"true\"><b>02</b>Diagnose</span>\n      <aside data-role=\"speaker-notes\">Table. Native table, navy header, ice stripes, 19 px cells (med-compact: 17 px). 4 rows, 4 columns at most; widths in the colgroup.</aside>\n    </article>"},
  "clinical-image": {label: "Clinical image", icon: "🩻", description: "Clinical image on the dark surface", html: "<article class=\"slide med-bg-dark-s2\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"image\" data-title=\"Clinical image\" style=\"background-color:var(--med-navy-deep)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-dark-pic-pane w-60 med-px-600\">\n          <img class=\"med-pic\" data-asset=\"sample-clinical-b.jpg\" src=\"\" alt=\"Sample clinical image\">\n          <div class=\"med-caption med-on-deep\" data-editable=\"text\">Modality, plane, what to look at.</div>\n        </div>\n        <div class=\"med-pane med-dark-side w-40 med-px-360\">\n          <div class=\"med-kicker med-on-deep\" data-editable=\"text\">What to look at</div>\n          <h1 class=\"med-title med-on-deep\" data-editable=\"text\">The finding, <span class=\"med-hl-aqua\">in one line</span></h1>\n          <ul class=\"med-checks med-gap-m\" data-editable=\"text\">\n            <li class=\"med-check med-on-deep\"><i class=\"med-ico med-ico-search-dark\"></i>First observation.</li>\n            <li class=\"med-check med-on-deep\"><i class=\"med-ico med-ico-search-dark\"></i>Second observation.</li>\n          </ul>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source med-on-deep\">Image: origin, year. Anonymised.</p></div>\n            <span class=\"slide-foot-page med-on-deep\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-navy med-on-dark\" style=\"left:413px\" aria-hidden=\"true\"><b>02</b>Diagnose</span>\n      <aside data-role=\"speaker-notes\">Clinical image (CT, EBUS, endoscopy, histology). Background med-bg-dark-sN (deep navy). Never enlarge beyond the native size, no text on the parenchyma, keep laterality and scale.</aside>\n    </article>"},
  "compare": {label: "Compare", icon: "🆚", description: "What exists (ice) against what blocks (navy)", html: "<article class=\"slide med-bg-compare-s3\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"compare\" data-title=\"Compare\" style=\"background-color:#FFFFFF\">\n      <div class=\"med-compare-head\">\n        <h1 class=\"med-title\" data-editable=\"text\">The title states <span class=\"med-hl\">the contrast</span></h1>\n      </div>\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-vs-pane w-50 med-px-480\">\n          <div class=\"med-vs-head\"><i class=\"med-ico med-ico-hospital-ring med-s44\"></i><span data-editable=\"text\">Available</span></div>\n          <ul class=\"med-checks\" data-editable=\"text\">\n            <li class=\"med-check\"><i class=\"med-ico med-ico-check-solid\"></i>What exists</li>\n            <li class=\"med-check\"><i class=\"med-ico med-ico-check-solid\"></i>What works</li>\n            <li class=\"med-check\"><i class=\"med-ico med-ico-check-solid\"></i>Who is trained</li>\n          </ul>\n          <div class=\"med-sources med-push\" data-editable=\"text\"><p class=\"med-source\"><span class=\"src-title\">Source</span>: Author A, et al. Journal. 2026.</p></div>\n        </div>\n        <div class=\"med-pane med-vs-pane med-right w-50 med-px-480\">\n          <div class=\"med-vs-head med-on-deep\"><i class=\"med-ico med-ico-coins-dark med-s44\"></i><span data-editable=\"text\">Accessible?</span></div>\n          <ul class=\"med-checks\" data-editable=\"text\">\n            <li class=\"med-check med-on-deep\"><i class=\"med-ico med-ico-coins-dark\"></i>What blocks the patient</li>\n            <li class=\"med-check med-on-deep\"><i class=\"med-ico med-ico-pin-dark\"></i>Second barrier</li>\n            <li class=\"med-check med-on-deep\"><i class=\"med-ico med-ico-clock-dark\"></i>Third barrier</li>\n          </ul>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-dbl med-on-deep\"><i class=\"med-dbl-tick med-on-deep\"></i><div class=\"med-take med-on-deep\" data-editable=\"text\">The takeaway in one line.</div></div>\n            <span class=\"slide-foot-page med-on-deep\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-white\" style=\"left:619px\" aria-hidden=\"true\"><b>03</b>Characterise</span>\n      <aside data-role=\"speaker-notes\">Compare. Background med-bg-compare-sN: white title band, ice column left, navy column right. The navy head may use the pink alarm accent.</aside>\n    </article>"},
  "statement-deep": {label: "Statement, deep", icon: "📍", description: "Statement, deep (conclusion)", html: "<article class=\"slide med-bg-deep-s5\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"section\" data-title=\"Statement, deep\" style=\"background-color:var(--med-navy)\">\n      <div class=\"med-statement\">\n        <div class=\"med-quote med-on-deep\" aria-hidden=\"true\">“</div>\n        <div class=\"med-statement-text med-on-deep\" data-editable=\"text\">The conclusion in one sentence, with <span class=\"med-hl-aqua\">one highlight</span>.</div>\n        <div class=\"med-statement-sub med-on-deep\" data-editable=\"text\">One line that opens the future.</div>\n      </div>\n      <aside data-role=\"speaker-notes\">Conclusion statement. Background med-bg-deep-s5: the airway is complete (stage 5, all passed).</aside>\n    </article>"},
  "clinical-case": {label: "Clinical case", icon: "🩺", description: "Facts, picture, question to the room", html: "<article class=\"slide med-bg-image-s3\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"case\" data-title=\"Clinical case\" style=\"background-color:#FFFFFF\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-text-pane w-60 med-px-540\">\n          <div class=\"med-kicker\" data-editable=\"text\">Clinical case</div>\n          <h1 class=\"med-title\" data-editable=\"text\">Patient, age, <span class=\"med-hl\">presenting problem</span></h1>\n          <div class=\"med-facts\">\n            <div><div class=\"med-fact-label\">History</div><div class=\"med-fact\" data-editable=\"text\">Relevant history in one line</div></div>\n            <div><div class=\"med-fact-label\">Imaging</div><div class=\"med-fact\" data-editable=\"text\">Key finding in one line</div></div>\n            <div><div class=\"med-fact-label\">Procedure</div><div class=\"med-fact\" data-editable=\"text\">What was done, how</div></div>\n          </div>\n          <div class=\"med-dbl med-push\"><i class=\"med-dbl-tick\"></i><div class=\"med-take\" data-editable=\"text\">What would you do next?</div></div>\n        </div>\n        <div class=\"med-pane med-pic-pane w-40 med-px-420\">\n          <div class=\"med-pic-frame\"><img class=\"med-pic\" data-asset=\"sample-clinical-b.jpg\" src=\"\" alt=\"Sample clinical image\"><div class=\"med-caption med-on-deep\" data-editable=\"text\">Modality, plane.</div></div>\n          <div class=\"med-pic-text\">\n            <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source\">Image: origin, year. Anonymised.</p></div>\n            <span class=\"slide-foot-page\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-white\" style=\"left:619px\" aria-hidden=\"true\"><b>03</b>Characterise</span>\n      <aside data-role=\"speaker-notes\">Clinical case. Facts as label plus one line, the question to the room as the takeaway. Picture anonymised (no name, date, ID, face, device banner).</aside>\n    </article>"},
  "annotated-image": {label: "Annotated image", icon: "🩻", description: "Annotated procedure image (markers baked in the picture, legend native)", html: "<article class=\"slide med-bg-dark-s3\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"image\" data-title=\"Annotated image\" style=\"background-color:var(--med-navy-deep)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-dark-pic-pane w-60 med-px-600\">\n          <img class=\"med-pic\" data-asset=\"sample-annotated-b.jpg\" src=\"\" alt=\"Sample annotated procedure still\">\n          <div class=\"med-caption med-on-deep\" data-editable=\"text\">Procedure, view, step.</div>\n        </div>\n        <div class=\"med-pane med-dark-side w-40 med-px-360\">\n          <div class=\"med-kicker med-on-deep\" data-editable=\"text\">Step by step</div>\n          <h1 class=\"med-title med-on-deep\" data-editable=\"text\">What the numbers <span class=\"med-hl-aqua\">show</span></h1>\n          <ol class=\"med-legend\" data-editable=\"text\">\n            <li class=\"med-legend-item\"><b class=\"med-legend-num\">1</b>First landmark.</li>\n            <li class=\"med-legend-item\"><b class=\"med-legend-num\">2</b>Second landmark.</li>\n            <li class=\"med-legend-item\"><b class=\"med-legend-num\">3</b>Third landmark.</li>\n          </ol>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source med-on-deep\">Image: origin, year. Anonymised.</p></div>\n            <span class=\"slide-foot-page med-on-deep\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-navy med-on-dark\" style=\"left:619px\" aria-hidden=\"true\"><b>03</b>Characterise</span>\n      <aside data-role=\"speaker-notes\">Annotated image. Numbered aqua markers baked into the picture (tools/breathe_assets.py, sample() shows how), legend native in the HTML with the same numbers.</aside>\n    </article>"},
  "timeline": {label: "Timeline", icon: "📝", description: "Milestones on the zoomed airway (complete)", html: "<article class=\"slide med-bg-track-s5\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"content\" data-title=\"Timeline\" style=\"background-color:var(--med-ice)\">\n      <div class=\"med-body\">\n        <div class=\"med-kicker\" data-editable=\"text\">Timeline</div>\n        <h1 class=\"med-title\" data-editable=\"text\">From the first step <span class=\"med-hl\">to today</span></h1>\n        <div class=\"med-foot-row med-push\">\n          <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source\"><span class=\"src-title\">Source</span>: Author A, et al. Journal. 2026.</p></div>\n          <span class=\"slide-foot-page\">{{N}}</span>\n        </div>\n      </div>\n      <div class=\"med-track\">\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-doc-done med-s88\"></i><div class=\"med-station-year\" data-editable=\"text\">2013</div><div class=\"med-station-name\" data-editable=\"text\">First milestone</div><div class=\"med-station-sub\" data-editable=\"text\">Short sub line</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-cap-done med-s88\"></i><div class=\"med-station-year\" data-editable=\"text\">2018</div><div class=\"med-station-name\" data-editable=\"text\">Second milestone</div><div class=\"med-station-sub\" data-editable=\"text\">Short sub line</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-people-done med-s88\"></i><div class=\"med-station-year\" data-editable=\"text\">2022</div><div class=\"med-station-name\" data-editable=\"text\">Third milestone</div><div class=\"med-station-sub\" data-editable=\"text\">Short sub line</div></div>\n        <div class=\"med-station w-25\"><i class=\"med-ico med-ico-chart-now med-s88\"></i><div class=\"med-station-year\" data-editable=\"text\">2026</div><div class=\"med-station-name med-now\" data-editable=\"text\">Today</div><div class=\"med-station-sub\" data-editable=\"text\">Short sub line</div></div>\n      </div>\n      <aside data-role=\"speaker-notes\">Timeline. Background med-bg-track-s5 (complete airway) or -s0. Four milestones at the station positions; the last one can use the -now icon.</aside>\n    </article>"},
  "paper-highlight": {label: "Paper highlight", icon: "📝", description: "Paper highlight", html: "<article class=\"slide med-bg-white-s4\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"content\" data-title=\"Paper highlight\" style=\"background-color:#FFFFFF\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-text-pane w-60 med-px-600\">\n          <div class=\"med-kicker\" data-editable=\"text\">Key paper</div>\n          <h1 class=\"med-title\" data-editable=\"text\">What this paper <span class=\"med-hl\">changes</span></h1>\n          <div class=\"med-paper\">\n            <div class=\"med-kicker\" data-editable=\"text\">Journal · 2026</div>\n            <div class=\"med-paper-title\" data-editable=\"text\">Title of the paper as published, two lines at most</div>\n            <div class=\"med-paper-authors\" data-editable=\"text\">Author A, Author B, Author C, et al.</div>\n          </div>\n          <div class=\"med-dbl med-push\"><i class=\"med-dbl-tick\"></i><div class=\"med-take\" data-editable=\"text\">The one line synthesis.</div></div>\n        </div>\n        <div class=\"med-pane med-paper-side w-40 med-px-360\">\n          <div class=\"med-kicker\" data-editable=\"text\">Main result</div>\n          <div class=\"med-num med-md\" data-editable=\"text\">94%</div>\n          <div class=\"med-num-label\" data-editable=\"text\">what the figure measures (n patients)</div>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source\"><span class=\"src-title\">Short title</span>: Author A, et al. Journal. 2026.</p></div>\n            <span class=\"slide-foot-page\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-white\" style=\"right:166px\" aria-hidden=\"true\"><b>04</b>Treat on time</span>\n      <aside data-role=\"speaker-notes\">Paper highlight. Citation card on ice, one key figure (teal; pink only on navy), one line synthesis.</aside>\n    </article>"},
  "video-poster": {label: "Video poster", icon: "🩻", description: "Video poster (insert the MP4 over the poster in PowerPoint)", html: "<article class=\"slide med-bg-dark-s4\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"image\" data-title=\"Video poster\" style=\"background-color:var(--med-navy-deep)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-dark-pic-pane w-60 med-px-600\">\n          <img class=\"med-pic\" data-asset=\"sample-video-b.jpg\" src=\"\" alt=\"Poster frame of the video\">\n          <div class=\"med-caption med-on-deep\" data-editable=\"text\">Procedure, length of the clip.</div>\n        </div>\n        <div class=\"med-pane med-dark-side w-40 med-px-360\">\n          <div class=\"med-kicker med-on-deep\" data-editable=\"text\">Video</div>\n          <h1 class=\"med-title med-on-deep\" data-editable=\"text\">What to watch <span class=\"med-hl-aqua\">in the clip</span></h1>\n          <ul class=\"med-checks med-gap-m\" data-editable=\"text\">\n            <li class=\"med-check med-on-deep\"><i class=\"med-ico med-ico-clock-dark\"></i>First moment to watch.</li>\n            <li class=\"med-check med-on-deep\"><i class=\"med-ico med-ico-clock-dark\"></i>Second moment to watch.</li>\n          </ul>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source med-on-deep\">Video: origin, year. Anonymised.</p></div>\n            <span class=\"slide-foot-page med-on-deep\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-navy med-on-dark\" style=\"right:166px\" aria-hidden=\"true\"><b>04</b>Treat on time</span>\n      <aside data-role=\"speaker-notes\">Video poster. After the export, insert the MP4 in PowerPoint exactly over the poster picture (same box), set it to play on click.</aside>\n    </article>"},
  "survey": {label: "Survey", icon: "📝", description: "Figures in the navy side pane, results table on ice", html: "<article class=\"slide med-bg-side-s4\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"content\" data-title=\"Survey\" style=\"background-color:var(--med-ice)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-side-pane w-30 med-px-300\">\n          <div class=\"med-kicker med-on-deep\" data-editable=\"text\">Survey</div>\n          <h1 class=\"med-title med-on-deep\" data-editable=\"text\">The title states <span class=\"med-hl-aqua\">the message</span></h1>\n          <div class=\"med-push\">\n            <div class=\"med-stat\"><div class=\"med-stat-num\" data-editable=\"text\">51</div><div class=\"med-stat-label\" data-editable=\"text\">respondents</div></div>\n            <div class=\"med-stat\"><div class=\"med-stat-num\" data-editable=\"text\">16</div><div class=\"med-stat-label\" data-editable=\"text\">countries</div></div>\n            <div class=\"med-stat\"><div class=\"med-stat-num\" data-editable=\"text\">5</div><div class=\"med-stat-label\" data-editable=\"text\">regions</div></div>\n          </div>\n        </div>\n        <div class=\"med-pane med-main-pane w-70 med-px-660\">\n          <table class=\"med-table\" data-type=\"table\" data-style=\"striped\" style=\"margin-top:0\">\n            <colgroup><col style=\"width:34%\"><col style=\"width:28%\"><col style=\"width:38%\"></colgroup>\n            <thead><tr><th>Resource</th><th>Available</th><th>Barrier</th></tr></thead>\n            <tbody>\n              <tr><td class=\"med-cell\" data-editable=\"text\"><strong>Resource one</strong></td><td class=\"med-cell\" data-editable=\"text\">52.0% of units</td><td class=\"med-cell\" data-editable=\"text\">Equipment, 56.0%</td></tr>\n              <tr><td class=\"med-cell\" data-editable=\"text\"><strong>Resource two</strong></td><td class=\"med-cell\" data-editable=\"text\">24.0% of units</td><td class=\"med-cell\" data-editable=\"text\">Cost, 40.0%</td></tr>\n              <tr><td class=\"med-cell\" data-editable=\"text\"><strong>Resource three</strong></td><td class=\"med-cell\" data-editable=\"text\">51.0% of units</td><td class=\"med-cell\" data-editable=\"text\">Training, 36.0%</td></tr>\n            </tbody>\n          </table>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-sources\" data-editable=\"text\"><p class=\"med-source\"><span class=\"src-title\">Survey title</span>. Status, sample sizes.</p></div>\n            <span class=\"slide-foot-page\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-ice\" style=\"right:166px\" aria-hidden=\"true\"><b>04</b>Treat on time</span>\n      <aside data-role=\"speaker-notes\">Survey. Three headline figures in aqua in the navy pane (46 px), the results table on ice. 4 rows at most with short cells.</aside>\n    </article>"},
  "priorities": {label: "Priorities", icon: "🎯", description: "3 x 2 icon items", html: "<article class=\"slide med-bg-side-s4\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"steps\" data-title=\"Priorities\" style=\"background-color:var(--med-ice)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-side-pane w-30 med-px-300\">\n          <h1 class=\"med-title med-on-deep\" data-editable=\"text\">From barriers to <span class=\"med-hl-aqua\">solutions</span>: six priorities</h1>\n          <div class=\"med-dbl med-on-deep med-push\"><i class=\"med-dbl-tick med-on-deep\"></i><div class=\"med-note med-on-deep\" data-editable=\"text\">The closing line of the priorities.</div></div>\n        </div>\n        <div class=\"med-pane med-grid-pane w-70 med-px-660\">\n          <div class=\"med-prio-grid\">\n            <div class=\"med-prio-row\">\n              <div class=\"med-prio w-50\"><i class=\"med-ico med-ico-search-ring med-s52\"></i><div><div class=\"med-prio-num\">01</div><div class=\"med-prio-title\" data-editable=\"text\">Priority one</div><div class=\"med-prio-text\" data-editable=\"text\">Two short lines of detail</div></div></div>\n              <div class=\"med-prio w-50\"><i class=\"med-ico med-ico-scope-ring med-s52\"></i><div><div class=\"med-prio-num\">02</div><div class=\"med-prio-title\" data-editable=\"text\">Priority two</div><div class=\"med-prio-text\" data-editable=\"text\">Two short lines of detail</div></div></div>\n            </div>\n            <div class=\"med-prio-row\">\n              <div class=\"med-prio w-50\"><i class=\"med-ico med-ico-cap-ring med-s52\"></i><div><div class=\"med-prio-num\">03</div><div class=\"med-prio-title\" data-editable=\"text\">Priority three</div><div class=\"med-prio-text\" data-editable=\"text\">Two short lines of detail</div></div></div>\n              <div class=\"med-prio w-50\"><i class=\"med-ico med-ico-coins-ring med-s52\"></i><div><div class=\"med-prio-num\">04</div><div class=\"med-prio-title\" data-editable=\"text\">Priority four</div><div class=\"med-prio-text\" data-editable=\"text\">Two short lines of detail</div></div></div>\n            </div>\n            <div class=\"med-prio-row\">\n              <div class=\"med-prio w-50\"><i class=\"med-ico med-ico-people-ring med-s52\"></i><div><div class=\"med-prio-num\">05</div><div class=\"med-prio-title\" data-editable=\"text\">Priority five</div><div class=\"med-prio-text\" data-editable=\"text\">Two short lines of detail</div></div></div>\n              <div class=\"med-prio w-50\"><i class=\"med-ico med-ico-map-ring med-s52\"></i><div><div class=\"med-prio-num\">06</div><div class=\"med-prio-title\" data-editable=\"text\">Priority six</div><div class=\"med-prio-text\" data-editable=\"text\">Two short lines of detail</div></div></div>\n            </div>\n          </div>\n          <div class=\"med-foot-row med-push\">\n            <div class=\"med-sources\"></div>\n            <span class=\"slide-foot-page\">{{N}}</span>\n          </div>\n        </div>\n      </div>\n      <span class=\"med-rail-label med-on-ice\" style=\"right:166px\" aria-hidden=\"true\"><b>04</b>Treat on time</span>\n      <aside data-role=\"speaker-notes\">Priorities. 3 to 6 items, one circled icon each (med-ico-*-ring, 52 px), title 20 px, two lines of detail at 17 px.</aside>\n    </article>"},
  "references": {label: "References", icon: "📚", description: "References", html: "<article class=\"slide med-bg-white-s5\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"references\" data-title=\"References\" style=\"background-color:#FFFFFF\">\n      <div class=\"med-body\">\n        <div class=\"med-kicker\" data-editable=\"text\">Sources</div>\n        <h1 class=\"med-title\" data-editable=\"text\">References</h1>\n        <ol class=\"med-refs\" data-editable=\"text\">\n          <li class=\"med-ref\"><b class=\"med-ref-num\">1</b>Author A, Author B, et al. Title of the paper. <em>Journal.</em> 2026;12(3):123. doi:10.0000/xxxx. PMID 00000000.</li>\n          <li class=\"med-ref\"><b class=\"med-ref-num\">2</b>Author A, et al. Title of the paper. <em>Journal.</em> 2025;8:45.</li>\n          <li class=\"med-ref\"><b class=\"med-ref-num\">3</b>Organisation. Title of the report or fact sheet (version). Year. website</li>\n        </ol>\n        <div class=\"med-foot-row med-push\">\n          <div class=\"med-sources\"></div>\n          <span class=\"slide-foot-page\">{{N}}</span>\n        </div>\n      </div>\n      <aside data-role=\"speaker-notes\">References, Vancouver style, 8 entries at most at 16 px. Numbers are real elements (med-ref-num) so they reach the PPTX.</aside>\n    </article>"},
  "thanks-collage": {label: "Thanks, collage", icon: "🙏", description: "The airway ends in a bronchial fan; collage edge to edge", html: "<article class=\"slide med-bg-thanks-s5\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"thanks\" data-title=\"Thanks, collage\" style=\"background-color:var(--med-navy)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-thanks-pane w-40 med-px-400\">\n          <div class=\"med-thanks-title\" data-editable=\"text\">Thank you</div>\n          <div class=\"med-thanks-sub\" data-editable=\"text\">for your attention</div>\n          <div class=\"med-hashtag\" data-editable=\"text\">#SharingIsGrowing</div>\n          <div class=\"med-partner-card\"><img data-asset=\"wiip-strong-logo.png\" src=\"\" alt=\"WiIP Strong logo\"></div>\n          <div class=\"med-thanks-sign med-push\">\n            <img class=\"med-disc\" data-asset=\"logo-disc.png\" src=\"\" alt=\"Botanical lungs emblem\">\n            <div>\n              <div class=\"med-author-name\" data-editable=\"text\">Dr Lamya CHRIF MORAND</div>\n              <div class=\"med-aff\"><i class=\"med-ico med-ico-mail-dark\"></i><span data-editable=\"text\">lamya.chrif@gmail.com</span></div>\n            </div>\n          </div>\n        </div>\n        <figure class=\"med-pane med-collage w-60 med-px-560\">\n          <img data-asset=\"collage-sample-b.jpg\" src=\"\" alt=\"Sample collage\">\n        </figure>\n      </div>\n      <aside data-role=\"speaker-notes\">Thanks with collage. The collage is one picture 1120 x 1080 (2x of 560 x 540) built by tools/collage.sh (grid in its header). Photo slots not filled yet are ice or aqua tiles, listed here with their coordinates, never placeholder text.</aside>\n    </article>"},
  "thanks-message": {label: "Thanks, message", icon: "🙏", description: "Message and a framed photo", html: "<article class=\"slide med-bg-thanks-s5\" id=\"{{ID}}\" data-type=\"slide\" data-id=\"{{ID}}\"\n             data-slide-type=\"thanks\" data-title=\"Thanks, message\" style=\"background-color:var(--med-navy)\">\n      <div class=\"med-bleed\">\n        <div class=\"med-pane med-thanks-pane w-60 med-px-560\">\n          <div class=\"med-thanks-title\" data-editable=\"text\">Thank you</div>\n          <div class=\"med-message\" data-editable=\"text\">A short closing message for the audience, two lines at most.</div>\n          <div class=\"med-hashtag\" data-editable=\"text\">#SharingIsGrowing</div>\n          <div class=\"med-thanks-sign med-push\">\n            <img class=\"med-disc\" data-asset=\"logo-disc.png\" src=\"\" alt=\"Botanical lungs emblem\">\n            <div>\n              <div class=\"med-author-name\" data-editable=\"text\">Dr Lamya CHRIF MORAND</div>\n              <div class=\"med-aff\"><i class=\"med-ico med-ico-mail-dark\"></i><span data-editable=\"text\">lamya.chrif@gmail.com</span></div>\n            </div>\n          </div>\n        </div>\n        <div class=\"med-pane med-photo-pane w-40 med-px-400\">\n          <img class=\"med-photo\" data-asset=\"sample-photo-b.jpg\" src=\"\" alt=\"Sample photo\">\n        </div>\n      </div>\n      <aside data-role=\"speaker-notes\">Thanks with a message and one framed photo (300 x 300, cropped to fill, white frame).</aside>\n    </article>"},
};
/* breathe-layouts:end */

/* ============================================================
   Medical layouts (charte "medical")
   Reproduit la charte medicale: bandeau gris haut, titre + filet
   teal/orange, bande de sources bibliographiques en pied, numero de page
   seul a droite (renumerote par renumberSlides via .slide-foot-page).
   Surface sombre (class="slide dark") pour toute slide dont la preuve
   principale est une image medicale (TDM, EBUS, endoscopie, histologie).
   Chaque enfant d'une rangee porte sa largeur (w-33, w-50, w-60...): sans
   largeur explicite, l'export PPTX retombe en empilement vertical.
   Regles completes: skill/topics/medical.md
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
