# Types: Document (mode Word-like)

## Structure du conteneur

```html
<!DOCTYPE html>
<html data-doc-type="document">
<head>
  <meta charset="UTF-8">
  <title>Mon document</title>
  <style>
    article[data-type="document"] {
      max-width: 800px;
      margin: 0 auto;
      padding: 60px 40px;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 15px;
      line-height: 1.7;
      color: #222;
    }
  </style>
</head>
<body>
  <article data-type="document">
    <!-- contenu -->
  </article>
</body>
</html>
```

## Éléments supportés

| Élément | Usage |
|---------|-------|
| `<h1>` | Titre principal (une seule occurrence recommandée) |
| `<h2>` | Titre de section |
| `<h3>` | Sous-section |
| `<h4>` | Sous-sous-section |
| `<p>` | Paragraphe |
| `<ul>` / `<ol>` | Listes |
| `<blockquote>` | Citation |
| `<pre><code>` | Bloc de code |
| `<table>` | Tableau (voir `types/tables.md`) |
| `<img>` | Image inline |

Tous les éléments textuels doivent avoir `data-editable="text"` pour être éditables dans GrapesJS.

## Images inline

```html
<img src="images/figure-1.png"
     data-editable="resize,reposition"
     alt="Figure 1: Architecture"
     style="max-width:100%; margin:20px 0; display:block;" />
<p style="font-size:12px; color:#666; text-align:center; margin-top:-10px;">
  Figure 1: Architecture du système
</p>
```

## Mise en page

### Single-column (défaut)
```html
<article data-type="document" data-layout="single-column" style="max-width:800px; margin:0 auto;">
```

### Two-column
```html
<article data-type="document" data-layout="two-column"
         style="columns:2; column-gap:40px; max-width:1100px; margin:0 auto;">
```

Note: le mode deux colonnes est déconseillé pour les documents longs (coupures de page imprévisibles).

## Styles texte via classes CSS

Définir dans le `<style>` du document:

```css
.bold { font-weight: bold; }
.italic { font-style: italic; }
.underline { text-decoration: underline; }
.highlight { background-color: #ffe066; }
.code { font-family: 'Courier New', monospace; background: #f0f0f0; padding: 2px 4px; border-radius: 2px; }
.caption { font-size: 12px; color: #666; text-align: center; }
```

Appliquer: `<span class="bold">texte important</span>`

## Différences avec le mode slides

| Critère | presentation | document |
|---------|-------------|----------|
| Navigation entre sections | prev/next | scroll continu |
| Structure | `<section data-type="slide">` | `<article data-type="document">` |
| Taille fixe | oui (1280×720) | non (max-width) |
| Export optimal | PPTX | DOCX |
| Pagination | implicite (slides) | CSS page-break |

## Quand utiliser export docx vs garder en HTML

**Exporter en DOCX si:**
- Le document doit être partagé avec des utilisateurs Office/Word
- Des modifications ultérieures sont prévues dans Word
- Le document doit être imprimé avec une mise en page précise

**Garder en HTML si:**
- Le document est consulté dans un navigateur
- Des liens hypertextes sont essentiels
- La mise en page CSS est complexe (multi-colonnes, dégradés)
- Le document est en cours d'édition via mcp-htmleditor
