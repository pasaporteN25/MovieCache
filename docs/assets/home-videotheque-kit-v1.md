# Kit material de videoteca v1

Assets originales para la recuperación visual de Inicio. Se generaron el 2026-09-03
con la herramienta integrada de generación de imágenes de OpenAI. No contienen títulos,
marcas, actores, obras, posters ni datos de una instancia. Se incorporan bajo
GPL-3.0-only como el proyecto.

La composición aceptada que guió el kit vive en
`docs/design/u2-recovery-north-star-v1.png`. Las fotografías de contratapas aportadas
por el usuario se usaron exclusivamente como referencia de material y distribución;
no se copiaron su texto, marcas, personajes ni imágenes.

## Inventario

| Archivo | Formato | Uso | SHA-256 |
| --- | --- | --- | --- |
| `static/img/night-videotheque-wall-v1.png` | PNG RGB, 1852 × 849 | Fondo de ladrillo nocturno, recortable | `abf0c01372afaad92eff9efbc6bd7667346740db9586186cd0e9c86836c29c30` |
| `static/img/poster-marquee-frame-v1.png` | PNG RGBA, 1024 × 1536 | Marco vertical; exterior y hueco del poster transparentes | `13095402d2ecddbf22a932ffbeb7f053f893c611b68916426ab41b12f890ad00` |
| `static/img/vhs-shelf-bay-v1.png` | PNG RGBA, 2017 × 780 | Módulo vacío de mueble continuo | `e30e7a4daa492919a7b6b9de77e196810dbc42c71e7cccb32b817eb846903ddf` |
| `static/img/vhs-spine-shell-v1.png` | PNG RGBA, 724 × 2172 | Shell de lomo para texto dinámico | `b7f958da7576f151d436443791080cef1797056cefe49c7ef170c947efce1caf` |
| `static/img/vhs-back-cover-shell-v1.png` | PNG RGBA, 988 × 1592 | Base vacía para 4–5 plantillas de contratapa | `d7c3add4ffd96b21b9cf07b6f868ff73acb4c89ee161cf6fe6d060c454579c9e` |

Las rutas de la tabla son relativas a `src/movie_inbox/web/`. El north star mide
1672 × 1011 y su SHA-256 es
`d4b3d22bd2b4e527a69ae68f40de2fc8fc597b5385ef6898ba6c609ac36dcb69`.

## Reglas de integración

- No usar estas imágenes como un screenshot gigante ni incrustar contenido dentro.
- El poster real va detrás del hueco alfa de `poster-marquee-frame-v1.png`.
- El mueble puede repetirse por módulo, pero la unión visual debe ocultarse mediante
  solape/recorte; no dejar calles vacías entre categorías.
- El lomo es un shell, no un botón rasterizado: título, año, formato, estados, foco y
  nombre accesible siguen en el DOM.
- La contratapa es un substrate común. Sus plantillas, placeholders, texto y acciones
  son HTML/CSS; el asset no decide la composición.
- Placas de categoría, botones físicos dorados, barcodes decorativos e indicadores se
  resuelven en CSS/SVG para conservar texto nítido, estados y accesibilidad.
- Si una pieza se reemplaza, crear `v2`, conservar este archivo hasta migrar todos sus
  usos, recalcular el hash y documentar el nuevo prompt.

## Prompts de producción

### Pared

```text
Create a production-ready UI background asset for the Movie Inbox web app, using the
latest user-approved mashup image in the conversation as the primary visual direction.
Asset: "night-videotheque-wall-v1", a seamless ultra-wide frontal wall/background of a
nocturnal 1980s video rental store. Dark near-black navy painted brick, subtle cyan and
magenta neon bounce, restrained warm aged-gold edge light, faint CRT texture, cinematic
but low-contrast so foreground UI remains legible. No furniture, shelves, VHS tapes,
poster frames, signs, readable text, letters, logos, brands, people, movie imagery,
controls or watermarks. Flat frontal perspective, calm center, edges slightly vignetted.
Landscape, safe to crop responsively. Modular background layer, not a full UI mockup.
```

### Marco de cartelera

```text
Create a production-ready PNG cutout for a web UI: a compact vertical cinema poster
frame matching a restrained nocturnal 1980s video-rental store. Real alpha transparency
outside the frame and inside the large poster opening. Simple rectangular straight-on
frame, slim worn black metal and dark wood, tiny aged brass trim, two small warm-gold
indicator bulbs near a shallow blank header plaque, subtle cyan and magenta reflected
edges. Quiet and utilitarian: no arch, jukebox styling, side neon tubes, excessive bulbs
or bulky base. No text, logos, brands, poster art, arrows, buttons, people or background.
```

### Módulo de estantería

```text
Create a transparent PNG of one wide empty frontal 1980s video-rental shelf/cabinet bay:
worn deep purple-black wood and metal, aged brass trim, scratches, rubbed corners and
subtle cyan/magenta reflections. Deep dark empty cavity for dynamic upright VHS spines,
solid lower lip and slim structural uprights. No plaque, objects, VHS tapes, labels,
text, barcode, logos, poster, controls or people. Straight-on view; alpha outside.
```

### Shell de lomo

```text
Create a transparent PNG of one blank upright VHS slipcase spine, perfectly frontal and
vertical: worn matte near-black material, paper grain, scratches, rubbed corners, thin
aged-brass border and restrained cyan/magenta edge reflections. Calm blank center for
dynamic vertical HTML title and blank lower zones for year/format. No text, characters,
numbers, symbols, logos, barcode, art, people, background or shelf. Alpha outside.
```

### Shell de contratapa

```text
Create a transparent PNG of a generic blank worn VHS back cover, using supplied VHS
photos only for material inspiration: near-black/navy cardboard, rubbed beige edges,
creases, scuffs, subtle cyan/magenta reflections and a restrained aged-gold accent.
Keep the interior calm for 4–5 semantic HTML layouts with synopsis, credits, runtime and
two image placeholders. No baked regions, photos, text, barcode, logos, ratings, movie
art, actors, people or background. Straight-on portrait cutout; alpha outside.
```
