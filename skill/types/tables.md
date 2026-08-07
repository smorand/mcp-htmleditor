# Types: Tableaux

## Structure HTML standard

```html
<table data-type="table" data-editable="cells"
       style="width:100%; border-collapse:collapse; font-family:Arial,sans-serif; font-size:13px;">
  <thead>
    <tr>
      <th style="border:1px solid #ccc; padding:10px; background:#f0f0f0; font-weight:bold; text-align:left;">
        En-tête 1
      </th>
      <th style="border:1px solid #ccc; padding:10px; background:#f0f0f0; font-weight:bold; text-align:left;">
        En-tête 2
      </th>
      <th style="border:1px solid #ccc; padding:10px; background:#f0f0f0; font-weight:bold; text-align:left;">
        En-tête 3
      </th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="border:1px solid #ccc; padding:10px;">Valeur A1</td>
      <td style="border:1px solid #ccc; padding:10px;">Valeur A2</td>
      <td style="border:1px solid #ccc; padding:10px;">Valeur A3</td>
    </tr>
    <tr>
      <td style="border:1px solid #ccc; padding:10px;">Valeur B1</td>
      <td style="border:1px solid #ccc; padding:10px;">Valeur B2</td>
      <td style="border:1px solid #ccc; padding:10px;">Valeur B3</td>
    </tr>
  </tbody>
</table>
```

**Règle**: `<thead>` est **obligatoire**. L'export PPTX s'appuie dessus pour les styles d'en-tête.

## Styles disponibles

### standard (par défaut)
Bordures grises, en-tête gris clair.

### striped — lignes alternées
```html
<table data-type="table" data-style="striped" ...>
```
CSS:
```css
tbody tr:nth-child(even) { background: #f9f9f9; }
```

### bordered — bordures épaisses
```css
table { border: 2px solid #333; }
th, td { border: 1px solid #999; }
```

### minimal — sans bordures
```css
th { border-bottom: 2px solid #333; padding: 8px; }
td { padding: 8px; border-bottom: 1px solid #eee; }
```

## Fusion de cellules

```html
<!-- Colspan: fusion horizontale sur 2 colonnes -->
<td colspan="2" style="border:1px solid #ccc; padding:10px;">Cellule fusionnée</td>

<!-- Rowspan: fusion verticale sur 2 lignes -->
<td rowspan="2" style="border:1px solid #ccc; padding:10px;">Cellule fusionnée</td>
```

## Redimensionnement des colonnes

Utiliser `data-col-width` en % sur les `<th>` ou `<colgroup>`:

```html
<table data-type="table">
  <colgroup>
    <col data-col-width="40" style="width:40%;" />
    <col data-col-width="30" style="width:30%;" />
    <col data-col-width="30" style="width:30%;" />
  </colgroup>
  <thead>...</thead>
  <tbody>...</tbody>
</table>
```

## Ajouter/supprimer des lignes

Via le menu contextuel GrapesJS (clic droit sur `data-type="table"`).

Manuellement:
```html
<!-- Ajouter une ligne à <tbody> -->
<tr>
  <td style="border:1px solid #ccc; padding:10px;">&nbsp;</td>
  <td style="border:1px solid #ccc; padding:10px;">&nbsp;</td>
</tr>
```

## Conversion PPTX

Ce qui est **préservé**: texte des cellules, structure lignes/colonnes, en-têtes.
Ce qui est **perdu**: colspan/rowspan, couleurs de fond, styles custom, bordures custom.
Résultat: table python-pptx avec style par défaut.
