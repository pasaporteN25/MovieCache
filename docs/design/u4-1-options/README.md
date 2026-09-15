# U4.1 — Composiciones de integración material

Fecha: 2026-09-09. Estado: **cerrada; opción B elegida por el owner**.

Las tres imágenes son north stars generadas con la herramienta integrada de imágenes a
partir de `source-annotated.png`. Evalúan composición, jerarquía, profundidad y uniones;
no especifican píxeles y no autorizan rasterizar textos, controles o contenido factual.

## Invariantes compartidos

- Misma arquitectura funcional: marca, cartelera, poster, playlist, selección, videoteca,
  categorías, lomos, acciones y ficha breve.
- Consola gráfica semiilustrada, metal oscuro pintado, latón contenido, serigrafía,
  biseles y sombras internas.
- Cyan, magenta y dorado como señales pequeñas; sin neón ambiental dominante.
- Fondo completamente nuevo, abstracto y de contraste bajo; sin pared ni habitación.
- Poste izquierdo visible y continuidad fuera del encuadre derecho, sin cierre ni vacío.
- No inventar funciones, datos ni controles. La fidelidad textual del mockup no reemplaza
  el contenido HTML real.

## Opciones

### A — Chasis continuo

`option-a-continuous-chassis.png`. El aparato encierra toda la experiencia: la franja de
selección se empotra al pie de la playlist y la consola inferior ocupa aperturas del mismo
chasis. Es la opción más material y cercana al mueble existente.

### B — Espina de control

`option-b-control-spine.png`. El marco de cartelera y el poste izquierdo forman una
columna estructural; de ella nacen el carril de selección, el travesaño y la videoteca.
Prioriza la continuidad vertical y hace más explícita la idea de una sola máquina.

La primera generación agregó palabras decorativas no pertenecientes al producto. La
versión guardada las reemplaza por metal y ventilación; esa rotulación no debe reaparecer.

**Decisión posterior del owner:** las inscripciones de la primera generación sí deben
reaparecer. Se autorizan expresamente `ARCHIVO / PELÍCULAS / MEMORIA` y
`REBOBINAR / EXPLORAR / CONSERVAR` como detalle serigrafiado no interactivo de la espina.
La opción guardada sigue sin ellas porque preserva el instante exacto presentado para la
elección; la decisión posterior manda sobre esa imagen.

### C — Tablero instrumental

`option-c-instrument-board.png`. Reduce volumen y textura, usa una retícula compartida y
trata cartelera, señal y ficha como aperturas de una gran placa gráfica. Sólo la hilera VHS
se proyecta físicamente. Es la opción menos hiperrealista y la más viable con HTML/CSS.

## Prompts finales

- **A:** conservar las regiones funcionales dentro de un único chasis continuo; empotrar
  selección y ficha en aperturas alineadas; fondo abstracto; continuidad derecha.
- **B:** formar una espina estructural con cartelera/poste izquierdo y extender desde ella
  carril, travesaño, estante y consola; eliminar toda rotulación ornamental inventada.
- **C:** reducir el volumen hacia un tablero instrumental semiilustrado con retícula común,
  displays recesados y VHS como único objeto claramente proyectado.

En los tres prompts se prohibieron pared/ladrillo, habitación fotográfica, tarjetas
flotantes, paneles SaaS redondeados, exceso de brillo, logos nuevos, marcas de agua y
funciones o afirmaciones inventadas.
