Charte `medical`: citer ses sources et anonymiser les images de patient. Mise en page des slides: `mcp-htmleditor skill --type medical`.

## Citer ses sources

Deux mécanismes, jamais mélangés dans un même jeu de slides:
1. Pied autoporteur: citation courte dans `.med-source` (peu de citations, ou slides diffusées une à une).
2. Appel de note en exposant `<sup>` plus une slide `references` (exposé avec vraie bibliographie).

Appels au format AMA / Vancouver: chiffres arabes en exposant, sans crochets, placés après la ponctuation, `2,5` pour plusieurs références, `4-7` pour une plage; aussi dans les légendes de figure et les cellules de tableau.

Figure reproduite d'un article, markup complet:

```html
<div class="med-sources">
  <p class="med-source"><span class="src-title">Titre de l'article</span> :
     Herth FJF, Eberhardt R, Vilmann P, et al. Thorax. 2021;76(3):210-8.
     Figure 2, reproduite avec autorisation.</p>
</div>
```

Autres cas, à recopier dans un `<p class="med-source">`:

```
Figure modifiée : Adapté de : Wahidi MM, et al. Chest. 2020;157(4):985-93. Figure 1, adapté avec l'autorisation d'Elsevier.
Open access : … Respirology. 2022;27(9):744-52. Figure 3. CC BY 4.0.
Son service : Courtoisie de l'unité de pneumologie interventionnelle, <établissement>. Image anonymisée, consentement obtenu.
Confrère : Image aimablement fournie par le Dr <Nom>, service de radiologie, <établissement>. Reproduite avec autorisation.
Non publié : Données personnelles, unité de pneumologie interventionnelle, <établissement>, 2024-2026 (n = 214). Non publié.
Recommandation capturée : Source : recommandation ERS/ESTS, 2025. Tableau 4, reproduit avec l'autorisation de l'European Respiratory Society.
Recommandation paraphrasée (préférable) : D'après : NCCN Guidelines, Non-Small Cell Lung Cancer, v3.2026. Consulté le 12 mars 2026.
Web ou atlas : Source : <auteur>. <titre>. <site>. Consulté le JJ mois AAAA. <URL>
Industriel : Source : monographie produit <société>, 2025. Utilisée avec autorisation. <Société> n'est pas intervenue dans le contenu de cette présentation.
Schéma IA : Schéma généré avec <outil>, <version>, <date>; relu et corrigé par l'auteur.
```

« Adapté » ou « modifié » signale une figure altérée, qui exige l'autorisation du détenteur des droits. Redessiner intégralement à partir des données publiées ne l'exige pas; ré-étiqueter ou recolorier la figure d'origine ne dispense jamais de l'autorisation.

Slide de bibliographie: style Vancouver / AMA, revues abrégées NLM, DOI en fin d'entrée. Si une publication fournit l'idée et la figure, la figure reçoit sa propre entrée numérotée: `Figure N reproduite de : …`.

Règles:
- Toute slide portant des pixels de tiers a une ligne `.med-source` non vide.
- Style de la ligne invariant sur tout le jeu: 10px, gris `--med-muted`, en bas à gauche, 2 lignes maximum.
- Citer n'est pas obtenir un droit. L'attribution ne vaut pas autorisation: tenir le statut de droits par image (propre, CC BY, autorisation obtenue, autorisation en attente) et ne pas diffuser un jeu contenant une image en attente.

## Anonymisation des images de patient

Liste de contrôle non négociable.
- Jamais: nom, initiales, numéro d'hospitalisation ou d'IPP, date calendaire de soins, date de naissance complète (l'ICMJE cite noms, initiales et numéros d'hôpital comme interdits).
- À la place: tranche d'âge, sexe, exposition pertinente (« 58 ans, H, ex-fumeur 40 PA ») et chronologie relative (J0, J+14, M+3).
- DICOM: nettoyer l'en-tête et les annotations incrustées dans les pixels. En-tête: `PatientName`, `PatientID`, date de naissance, `AccessionNumber`, `StudyDate`, institution, médecin demandeur, tags privés. Pixels: texte de coin, bandeaux du PACS. Exporter un PNG ou JPEG aplati depuis une source anonymisée, jamais une capture d'écran de PACS.
- Garder les incrustations cliniquement nécessaires: latéralité D/G, barre d'échelle, modalité, fenêtre, orientation. Perdre la latéralité est une faute clinique, pas un gain de confidentialité.
- Visages, tatouages, cicatrices, bijoux: recadrer ou masquer. Masquer les yeux est jugé insuffisant par l'ICMJE: une photographie identifiable exige un consentement écrit.
- Vidéo: vérifier la première et la dernière image, plus l'incrustation de la colonne d'endoscopie.
- Toute séquence de cas clinique porte la mention de consentement dans la bande de légende.
- Maladie rare plus petit établissement plus date précise: le patient est ré-identifiable même sans son nom.
