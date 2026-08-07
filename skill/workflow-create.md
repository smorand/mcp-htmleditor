# Workflow: créer et modifier un fichier HTML

## Partir d'un template bootstrap

La méthode la plus rapide pour un nouveau fichier:

```bash
# Copier le template approprié
cp skill/templates/bootstrap/slides-empty.html mon-fichier.html
# ou pour un document
cp skill/templates/bootstrap/document-empty.html mon-document.html
```

Ensuite, ouvrir dans l'éditeur:
```
start_server(file="mon-fichier.html")
```

## Partir de zéro — structure minimale

### Présentation
```html
<!DOCTYPE html>
<html data-doc-type="presentation">
<head>
  <meta charset="UTF-8">
  <title>Ma présentation</title>
</head>
<body>
  <section data-type="slide" data-id="slide-1" data-title="Titre">
    <h1 data-editable="text">Titre de la présentation</h1>
    <p data-editable="text">Sous-titre ou accroche</p>
  </section>
</body>
</html>
```

### Document
```html
<!DOCTYPE html>
<html data-doc-type="document">
<head>
  <meta charset="UTF-8">
  <title>Mon document</title>
</head>
<body>
  <article data-type="document">
    <h1 data-editable="text">Titre du document</h1>
    <p data-editable="text">Introduction…</p>
  </article>
</body>
</html>
```

## Bonnes pratiques par type de contenu

- **Slides**: voir `skill/types/slides.md`
- **Gantt**: voir `skill/types/gantt.md`
- **Schéma d'architecture**: voir `skill/types/arch-diagram.md`
- **Images annotées**: voir `skill/types/annotated-image.md`
- **Tableaux**: voir `skill/types/tables.md`
- **Document texte**: voir `skill/types/document.md`

## Règles de nommage des fichiers

- Kebab-case: `mon-rapport-q1-2024.html`
- Pas d'espaces, pas d'accents dans les noms de fichiers
- Préfixes suggérés: `slides-`, `doc-`, `report-`, `roadmap-`

## Règles de commit git

Format: `type: description courte` (max 72 caractères)

Types:
- `feat:` ajout d'un nouveau slide/section/composant
- `edit:` modification de contenu existant
- `style:` changement de style sans modification de contenu
- `fix:` correction d'un problème
- `export:` export d'un fichier

Exemples:
```
feat: ajout slide "Roadmap 2025"
edit: mise à jour chiffres Q3 dans tableau résultats
style: harmonisation couleurs présentation IBM
```

## Modifier du texte dans un slide

Workflow LLM:
1. `update_start()`
2. Lire le fichier HTML courant
3. Localiser l'élément via `data-id`, `data-title`, ou le contenu textuel
4. Modifier le contenu de l'élément `data-editable="text"`
5. Réécrire le fichier HTML complet (conserver head, body, doctype, data-doc-type)
6. `update_end()`

## Ajouter une slide

1. `update_start()`
2. Ajouter une `<section data-type="slide" data-id="slide-X" data-title="...">` dans le body
3. `data-id` doit être unique dans le document (ex: timestamp ou slug)
4. `update_end()`

## Insérer une image

Pour la portabilité (partage, export), préférer le base64:

```python
import base64
with open("image.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
img_tag = f'<img src="data:image/png;base64,{b64}" data-editable="resize,reposition" style="max-width:100%;" />'
```

Pour les images locales, utiliser un chemin **relatif** au fichier HTML.

## Quand utiliser data-doc-type="presentation" vs "document"

| Critère | presentation | document |
|---------|-------------|----------|
| Slides multiples | oui | non |
| Navigation prev/next | oui | non |
| Export PPTX optimal | oui | médiocre |
| Export DOCX optimal | médiocre | oui |
| Mode lecture longue | non | oui |
