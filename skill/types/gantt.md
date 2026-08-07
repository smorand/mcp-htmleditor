# Types: Gantt

## Structure HTML complète

```html
<div data-type="gantt" style="width:100%; overflow-x:auto; padding:16px; font-family:Arial,sans-serif;">

  <!-- En-tête des périodes (optionnel mais recommandé) -->
  <div style="display:flex; margin-bottom:8px; padding-left:200px;">
    <div style="flex:1; text-align:center; font-size:12px; color:#666;">Jan</div>
    <div style="flex:1; text-align:center; font-size:12px; color:#666;">Fév</div>
    <div style="flex:1; text-align:center; font-size:12px; color:#666;">Mar</div>
    <div style="flex:1; text-align:center; font-size:12px; color:#666;">Avr</div>
    <!-- ... -->
  </div>

  <!-- Tâche -->
  <div style="display:flex; align-items:center; margin-bottom:6px;">
    <div style="width:200px; font-size:13px; font-weight:bold;">Nom de la tâche</div>
    <div data-type="gantt-task"
         data-id="task-1"
         data-label="Nom de la tâche"
         data-start="2024-01"
         data-end="2024-03"
         data-color="#4a90d9"
         style="flex:none; width:25%; background:#4a90d9; color:white;
                padding:6px 10px; border-radius:4px; font-size:12px;
                margin-left:0%; box-sizing:border-box;">
      Nom de la tâche
    </div>
  </div>

</div>
```

## Attributs obligatoires sur gantt-task

| Attribut | Description | Exemple |
|----------|-------------|---------|
| `data-type="gantt-task"` | Identifie l'élément comme tâche | — |
| `data-id` | Identifiant unique | `task-1` |
| `data-label` | Libellé affiché | `"Développement API"` |
| `data-start` | Date de début | `2024-01` (YYYY-MM) |
| `data-end` | Date de fin | `2024-03` (YYYY-MM) |

## Attributs optionnels

| Attribut | Description | Exemple |
|----------|-------------|---------|
| `data-color` | Couleur de fond | `#4a90d9` |
| `data-group` | Groupe/épic parent | `"Phase 1"` |
| `data-depends-on` | ID de tâche prérequise | `task-1` |

## Contraintes visuelles

- Largeur minimale d'une tâche: 40px (sinon le label n'est pas lisible)
- Largeur maximale: 100% du conteneur Gantt
- Le positionnement horizontal se fait via `margin-left` en % et `width` en %

Formule de calcul (pour un Gantt Q1-Q4, 12 mois = 100%):
```
margin-left% = (mois_debut - 1) / 12 * 100
width%       = (mois_fin - mois_debut + 1) / 12 * 100
```

## Ajouter une tâche

1. Calculer le `margin-left` et `width` en %
2. Choisir une couleur `data-color`
3. Ajouter l'élément dans le `data-type="gantt"`

## Supprimer une tâche

Supprimer le `<div data-type="gantt-task" ...>` correspondant.

## Déplacer une tâche

Modifier `data-start`, `data-end`, `margin-left` et `width` en conséquence.

## Représenter les dépendances

Les dépendances sont sémantiques en V1 (pas de flèches visuelles):
```html
<div data-type="gantt-task" data-id="task-2" data-depends-on="task-1" ...>
```

## Conversion PPTX

Ce qui est **préservé**: libellés, dates de début/fin.
Ce qui est **perdu**: couleurs custom, dépendances, mise en page visuelle (barres proportionnelles).
Résultat: tableau 4 colonnes (Tâche | Début | Fin | Couleur).

## Exemple complet: Roadmap Q1-Q4

```html
<div data-type="gantt" style="width:100%; overflow-x:auto; padding:16px; font-family:Arial,sans-serif;">
  <h3 style="margin:0 0 12px;">Roadmap 2024</h3>

  <!-- Header -->
  <div style="display:flex; padding-left:180px; margin-bottom:4px;">
    <div style="flex:1; text-align:center; font-size:11px; color:#999; border-left:1px dashed #ddd;">Q1</div>
    <div style="flex:1; text-align:center; font-size:11px; color:#999; border-left:1px dashed #ddd;">Q2</div>
    <div style="flex:1; text-align:center; font-size:11px; color:#999; border-left:1px dashed #ddd;">Q3</div>
    <div style="flex:1; text-align:center; font-size:11px; color:#999; border-left:1px dashed #ddd;">Q4</div>
  </div>

  <!-- Tâche 1: Jan-Mar -->
  <div style="display:flex; align-items:center; margin-bottom:6px;">
    <div style="width:180px; font-size:12px;">Discovery</div>
    <div data-type="gantt-task" data-id="t1" data-label="Discovery" data-start="2024-01" data-end="2024-03" data-color="#4a90d9"
         style="width:25%; background:#4a90d9; color:white; padding:5px 8px; border-radius:3px; font-size:11px; margin-left:0%;">
      Discovery
    </div>
  </div>

  <!-- Tâche 2: Avr-Juin -->
  <div style="display:flex; align-items:center; margin-bottom:6px;">
    <div style="width:180px; font-size:12px;">Design</div>
    <div data-type="gantt-task" data-id="t2" data-label="Design" data-start="2024-04" data-end="2024-06" data-color="#7ed321"
         style="width:25%; background:#7ed321; color:white; padding:5px 8px; border-radius:3px; font-size:11px; margin-left:25%;">
      Design
    </div>
  </div>

  <!-- Tâche 3: Mai-Sep -->
  <div style="display:flex; align-items:center; margin-bottom:6px;">
    <div style="width:180px; font-size:12px;">Développement</div>
    <div data-type="gantt-task" data-id="t3" data-label="Développement" data-start="2024-05" data-end="2024-09" data-color="#f5a623"
         style="width:41.7%; background:#f5a623; color:white; padding:5px 8px; border-radius:3px; font-size:11px; margin-left:33.3%;">
      Développement
    </div>
  </div>

  <!-- Tâche 4: Sep-Déc -->
  <div style="display:flex; align-items:center; margin-bottom:6px;">
    <div style="width:180px; font-size:12px;">Tests &amp; QA</div>
    <div data-type="gantt-task" data-id="t4" data-label="Tests &amp; QA" data-start="2024-09" data-end="2024-11" data-color="#d0021b"
         style="width:25%; background:#d0021b; color:white; padding:5px 8px; border-radius:3px; font-size:11px; margin-left:66.7%;">
      Tests &amp; QA
    </div>
  </div>

  <!-- Tâche 5: Nov-Déc -->
  <div style="display:flex; align-items:center; margin-bottom:6px;">
    <div style="width:180px; font-size:12px;">Déploiement</div>
    <div data-type="gantt-task" data-id="t5" data-label="Déploiement" data-start="2024-11" data-end="2024-12" data-color="#9013fe"
         style="width:16.7%; background:#9013fe; color:white; padding:5px 8px; border-radius:3px; font-size:11px; margin-left:83.3%;">
      Déploiement
    </div>
  </div>

  <!-- Tâche 6: transverse Jan-Déc -->
  <div style="display:flex; align-items:center; margin-bottom:6px;">
    <div style="width:180px; font-size:12px;">Communication</div>
    <div data-type="gantt-task" data-id="t6" data-label="Communication" data-start="2024-01" data-end="2024-12" data-color="#417505"
         style="width:100%; background:#417505; color:white; padding:5px 8px; border-radius:3px; font-size:11px; margin-left:0%; opacity:0.6;">
      Communication (transverse)
    </div>
  </div>
</div>
```
