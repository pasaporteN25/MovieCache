# Kit VHS de Inicio (U1.3)

- **Propósito:** las estanterías privadas usan una carcasa VHS reconocible sin convertir
  los datos del catálogo en arte raster. El marco hace visible la metáfora; HTML conserva
  títulos, metadatos, estados, lector de pantalla y acciones.
- **Kit y estados:** `core-vhs.css` define `.vhs-cassette` en estado `closed` o
  `selected`, y `.vhs-case[data-vhs-state="open"]` para la ficha desplegada. El cassette
  lleva sólo el PNG auditado; la etiqueta central y toda la información se superponen con
  contenido vivo. El estado seleccionado es una elevación breve del marco y el abierto
  muestra la ficha ya existente, no una ruta ni un editor paralelo.
- **Alcance:** se aplica a Inicio privado. Las filas continúan usando el payload editorial
  v1, scroll táctil y selección roving de U1.2. No se modifica la cartelera pública ni
  su payload; una adaptación pública requerirá otra tarea.
- **Accesibilidad y movimiento:** botones nativos conservan foco, Tab y las flechas de
  U1.2; el marco es `aria-hidden`. `prefers-reduced-motion` anula las transiciones del
  cassette y de la caja sin perder ningún estado.
- **Activos:** `vhs-cassette-frame-v1.png` es un PNG RGBA frontal, sin texto, logos ni
  contenido de owner. Su procedencia, integridad, prompt y licencia están en
  `docs/assets/vhs-cassette-frame-v1.md`.
