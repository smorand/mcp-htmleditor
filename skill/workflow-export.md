# Workflow: exporter en PPTX ou DOCX

## Choisir le format

| Critère | PPTX | DOCX |
|---------|------|------|
| Fichier de type présentation (slides) | **oui** | non |
| Fichier de type document (texte long) | non | **oui** |
| Partage avec équipe Office | oui | oui |
| Rendu fidèle des layouts CSS | partiel | bon (via pandoc) |
| Gantt, schémas archi | tableau simple | perte de structure |

**Règle**: `data-doc-type="presentation"` → exporter en PPTX. `data-doc-type="document"` → exporter en DOCX.

## Commande CLI

```bash
# Export PPTX
mcp-htmleditor export pptx input.html output.pptx

# Export DOCX
mcp-htmleditor export docx input.html output.docx
```

## Limitations connues de la conversion

### HTML → PPTX
- Les gradients CSS sont ignorés (fond blanc par défaut)
- Les polices personnalisées ne sont pas embarquées (fallback Arial)
- Les animations CSS sont perdues
- Les Gantt sont convertis en tableaux simples (4 colonnes: Tâche, Début, Fin, Couleur)
- Les schémas d'architecture deviennent des rectangles simples sans flèches
- Les images en base64 ne sont pas incluses (V1: placeholder)
- La mise en page CSS complexe (flexbox, grid) est approximée

### HTML → DOCX
- La conversion via pandoc est fidèle au contenu textuel
- Les styles CSS inline sont approximés
- Les éléments `data-type="gantt"` et `data-type="arch-diagram"` peuvent être mal rendus
- Les images avec chemin relatif doivent exister sur disque au moment de l'export

## Post-processing recommandé

### Après export PPTX
1. Ouvrir dans PowerPoint / LibreOffice Impress
2. Vérifier les positions des textboxes (ajustements manuels souvent nécessaires)
3. Appliquer un thème PowerPoint si besoin
4. Vérifier les images (les remplacer si manquantes)

### Après export DOCX
1. Ouvrir dans Word / LibreOffice Writer
2. Appliquer un style de document (Normal, Titres, etc.)
3. Vérifier la table des matières si présente

## Règles sur les images

- **Chemin absolu**: toujours sûr pour l'export
- **Chemin relatif**: relatif à l'emplacement du fichier HTML (pas du CWD)
- **base64**: portable mais non supporté en PPTX V1 (contournement: sauvegarder l'image sur disque puis référencer)
- **URL externe**: non supporté en PPTX (télécharger l'image d'abord)

## Exemple complet

```bash
# Préparer le fichier
cp skill/templates/reference/slides/presentation-standard.html /tmp/ma-pres.html

# Exporter
mcp-htmleditor export pptx /tmp/ma-pres.html /tmp/ma-pres.pptx

# Ouvrir
open /tmp/ma-pres.pptx
```
