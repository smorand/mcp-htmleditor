# Workflow: créer un template depuis un PPTX/DOCX existant

## Vue d'ensemble

Ce workflow permet de transformer une présentation ou un document existant
en template HTML réutilisable dans mcp-htmleditor.

## Étapes

### 1. Convertir avec pandoc

```bash
# PPTX → HTML
pandoc input.pptx -o output.html --standalone --extract-media=./media

# DOCX → HTML
pandoc input.docx -o output.html --standalone --extract-media=./media
```

L'option `--extract-media=./media` extrait les images dans un sous-dossier `media/`.

### 2. Analyser la structure HTML produite

Ouvrir `output.html` et identifier:
- Les balises de structure (sections, divs, articles)
- Les éléments textuels répétables (titres, corps, bullets)
- Les images (localisation dans le HTML)
- Les tableaux

### 3. Ajouter les attributs data-type et data-editable

Pour chaque slide/section:
```html
<!-- Ajouter data-type="slide", data-id unique, data-title -->
<section data-type="slide" data-id="slide-cover" data-title="Couverture">
  <!-- Sur les éléments texte éditables -->
  <h1 data-editable="text">Titre</h1>
  <p data-editable="text">Sous-titre</p>
  <!-- Sur les images -->
  <img src="media/img1.png" data-editable="resize,reposition" />
</section>
```

Pour les composants spéciaux, ajouter les `data-type` appropriés:
- Tableau → `data-type="table"`
- Zone Gantt → `data-type="gantt"`
- Schéma → `data-type="arch-diagram"`

### 4. Ajouter data-doc-type sur `<html>`

```html
<!-- Pour une présentation -->
<html data-doc-type="presentation">

<!-- Pour un document -->
<html data-doc-type="document">
```

### 5. Nettoyer le CSS généré par pandoc

Pandoc génère souvent un CSS très verbeux. Remplacer par un CSS minimal:

```html
<style>
  /* Styles essentiels uniquement */
  section[data-type="slide"] {
    width: 1280px;
    min-height: 720px;
    padding: 60px;
    box-sizing: border-box;
    background: white;
    font-family: Arial, sans-serif;
  }
</style>
```

### 6. Sauvegarder dans le bon dossier

```bash
# Pour une présentation
cp output.html skill/templates/reference/slides/mon-template.html

# Pour un document
cp output.html skill/templates/reference/documents/mon-template.html
```

### 7. Documenter le template

Ajouter un commentaire HTML en haut du fichier:

```html
<!--
  Template: mon-template
  Origine: Converti depuis mon-fichier.pptx (pandoc 3.x)
  Usage: Présentation standard IBM
  Slides: cover, agenda, content-2col, closing
  Date: 2024-01
-->
```

## Résoudre les problèmes courants

### Images manquantes
Si les images sont référencées par chemin relatif et ne se trouvent pas au bon endroit:
1. Copier le dossier `media/` dans le même répertoire que le template
2. Ou convertir les images en base64:
   ```python
   import base64
   with open("media/img1.png", "rb") as f:
       b64 = base64.b64encode(f.read()).decode()
   # Remplacer src="media/img1.png" par src="data:image/png;base64,{b64}"
   ```

### Mise en page cassée
Pandoc peut générer des positionnements absolus qui ne s'affichent pas bien dans GrapesJS.
Remplacer les positions absolues par du CSS flexbox ou grid.

### Polices manquantes
Utiliser uniquement les polices système: Arial, Helvetica, Georgia, Times New Roman, Verdana, Tahoma.
