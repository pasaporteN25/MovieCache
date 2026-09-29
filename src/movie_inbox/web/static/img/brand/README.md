# Movie Inbox — marca del videoclub

Identidad aprobada el 2026-09-28: Movie Inbox, cassette VHS, cigarrillo y humo
con forma de película. Negro, crema y acentos mostaza. No reemplaza todavía
la marca del encabezado global.

- `movie-inbox-logo-master.png`: marca crema sobre transparencia, para fondos oscuros.
- `movie-inbox-sticker-master.png`: sticker de papel con la acción «Editar ficha».
- `vhs-blank-master.png`: carcasa vacía; el título siempre se dibuja con texto HTML.
- Logo y sticker: variantes PNG y WebP de **128, 256, 512 y 1024 px de ancho**,
  con proporción conservada. El original es el master; no se presenta como vector.
- `vhs-blank-512.webp`: textura compartida por todas las cajas, 140 KB aproximadamente.

La interfaz usa las variantes WebP de 256/512 px. Las versiones de 128 px son
previsualizaciones compactas; la acción del sticker siempre conserva un nombre
accesible en el botón. No usar la imagen como sustituto de ese nombre.

Generación: herramienta integrada **Imagegen**, sin API ni CLI alternativo.
Los tamaños se exportaron con Sharp; script reproducible:
`docs/design/vhs-case-v1/export-assets.cjs` (requiere `sharp`, o `SHARP_MODULE`).

## Prompts finales

**Sticker**
Create one production transparent PNG asset: ONLY the large cream paper MOVIE INBOX
sticker shown on the right of this approved design. Match faithfully its black stacked
MOVIE INBOX lettering, retro VHS cassette at lower left, cigarette at right with smoke
curling like film, mustard line, and EDITAR FICHA caption along bottom. Flat front view,
near rectangular sticker with gently rounded worn edges and tiny peeled top right corner.
No rotation, no perspective. Tight framing with 3% transparent margin. No background,
no other objects, no mockup board or explanatory labels. This sticker will be a small
clickable UI asset so retain strong readable lettering and simplify tiny distress.

**Logo**
Extract brand identity into a clean flat logo on genuinely transparent background:
preserve exact stacked MOVIE INBOX typography, VHS cassette and cigarette with curling
filmstrip smoke from this sticker. Remove paper, remove EDITAR FICHA footer and its
bottom divider. Render artwork in solid warm cream ink and three small mustard lines.
CRITICAL no glow, no shadows, no halo, no diffuse light, no backdrop, no light emission.
Crisp opaque cream ink with transparent negative spaces like a screen print stencil.
Tight bounding box, flat 2D identity artwork intended on black background. Every pixel
outside the ink must be fully transparent.

**Caja**
Generate a single production UI background asset based precisely on the rightmost black
VHS case from the reference. Straight-on orthographic front view black plastic VHS rental
case, subtle grain, rubbed silver-gray edges, few scuffs, small diagonal molded corners,
slender spine at left. Black color, no teal blue fill. Entire case fully visible tight
framing 1% transparent margin. IMPORTANT remove all labels, tape, text, illustrations,
logos, metadata and shelf: ONLY blank black VHS case. Width:height 2:3. Transparent
outside rounded case. Will host dynamic text and real movie posters on top. High quality
tactile restrained realistic texture.
