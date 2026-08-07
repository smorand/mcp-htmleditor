# Types: Slides

## Structure minimale d'un slide

```html
<section
  data-type="slide"
  data-id="slide-unique-id"
  data-title="Titre du slide"
  style="width:1280px; min-height:720px; padding:60px; box-sizing:border-box; background:white;">
  <!-- contenu -->
</section>
```

Attributs obligatoires:
- `data-type="slide"` — identifie le slide pour la navigation et l'export
- `data-id` — identifiant unique dans le document (ex: slug ou timestamp)
- `data-title` — titre utilisé dans la navigation et les exports

## Layouts disponibles

### full — pleine page
```html
<section data-type="slide" data-id="s1" data-title="Full" style="padding:60px;">
  <div data-editable="text" style="text-align:center;">Contenu centré</div>
</section>
```

### split-50/50 — deux colonnes égales
```html
<section data-type="slide" data-id="s2" data-title="Split" style="padding:40px; display:flex; gap:40px;">
  <div style="flex:1;" data-editable="text">Colonne gauche</div>
  <div style="flex:1;" data-editable="text">Colonne droite</div>
</section>
```

### title-only — slide de titre
```html
<section data-type="slide" data-id="s3" data-title="Titre" style="display:flex; align-items:center; justify-content:center; flex-direction:column;">
  <h1 data-editable="text" style="font-size:48px; text-align:center;">Titre principal</h1>
  <p data-editable="text" style="font-size:24px; color:#666; text-align:center;">Sous-titre</p>
</section>
```

### content-left — contenu à gauche, image à droite
```html
<section data-type="slide" data-id="s4" data-title="Content Left" style="display:flex; gap:40px; padding:40px;">
  <div style="flex:3;">
    <h2 data-editable="text">Titre</h2>
    <ul data-editable="text"><li>Point 1</li><li>Point 2</li></ul>
  </div>
  <div style="flex:2;">
    <img src="" data-editable="resize,reposition" style="width:100%;" />
  </div>
</section>
```

### content-right — image à gauche, contenu à droite
Inverse du précédent (swap les flex children).

## Animations CSS disponibles

Appliquer via une classe CSS sur la section ou un élément enfant:

```css
/* Dans le <style> du document */
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideFromLeft { from { transform: translateX(-100%); } to { transform: translateX(0); } }
@keyframes slideFromBottom { from { transform: translateY(100%); } to { transform: translateY(0); } }

.anim-fade-in { animation: fadeIn 0.5s ease-in; }
.anim-slide-left { animation: slideFromLeft 0.4s ease-out; }
.anim-slide-bottom { animation: slideFromBottom 0.4s ease-out; }
```

Appliquer: `<h1 class="anim-fade-in">Titre</h1>`

## Transitions entre slides

Les slides sont navigués via JavaScript dans GrapesJS (show/hide).
Pour un effet de transition, ajouter une classe au slide:

```html
<section data-type="slide" data-transition="fade" ...>
```

Note: les transitions CSS ne sont pas automatiquement appliquées en V1.
La navigation est instantanée (show/hide via display).

## Règles de navigation

**Ne jamais:**
- Supprimer `data-id` ou `data-type="slide"` d'une section
- Changer `data-id` d'un slide existant (casse les références)
- Imbriquer des sections `data-type="slide"` l'une dans l'autre

## Tailles recommandées

| Format | Dimensions | Usage |
|--------|-----------|-------|
| 16:9 HD | 1280 × 720 px | Standard moderne, écran |
| 16:9 Full HD | 1920 × 1080 px | Haute résolution |
| 4:3 | 1024 × 768 px | Export PPTX standard |

Pour l'export PPTX, le ratio 4:3 (1024×768) est le mieux supporté.

## Polices recommandées (system-safe)

```css
font-family: Arial, Helvetica, sans-serif;       /* corps de texte */
font-family: Georgia, 'Times New Roman', serif;  /* titres élégants */
font-family: Verdana, Geneva, sans-serif;        /* lisibilité écran */
font-family: Tahoma, Geneva, sans-serif;         /* compact */
```

Ne pas utiliser de Google Fonts ou polices externes (risque d'indisponibilité, export PPTX).
