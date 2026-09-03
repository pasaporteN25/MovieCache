# Cartelera-lista Winamp y ambientación "Noche de cine" (U2.1)

## Punto de partida

U1.1 ya había resuelto el selector fijo de la cartelera como una lista de botones
nativos con roving tabindex, navegable con flechas, Home/End y Enter (semántica nativa
de `<button>`), con click/tap como alternativa. U2.1 no repite esa mecánica: la
mantiene intacta y la lleva al terreno visual que pedía la lámina de referencia —
lista compacta al estilo reproductor Winamp, con `Cartelera disponible` visible y una
ambientación de noche de cine detrás.

## Cambios de esta entrega

- **Rótulo visible.** El kicker de la sección pasa de "Programación personal" a
  `Cartelera disponible`, el término exacto que pide el brief maestro
  (`docs/briefs/home-video-store-v2.md`). El `<h2>` con la fecha (`Cartelera del día` /
  `Cartelera de ayer`) no cambia.
- **Densidad tipo lista de reproducción.** Las filas del selector bajan de 64px a 52px
  de alto mínimo, con menos padding; la fila activa suma un indicador triangular
  decorativo (`::before`, `aria-hidden` implícito por ser contenido generado sin texto)
  imitando el cursor de reproducción de un player clásico. El estado real sigue siendo
  `aria-pressed`; el triángulo es puramente visual y no es la única señal de selección
  (el fondo y el borde superior ya lo eran).
- **Ambientación "Noche de cine".** `.spotlight-ambience` es una capa decorativa
  (`aria-hidden="true"`, `pointer-events: none`, `z-index: 0`) detrás de la barra y el
  escenario, compuesta enteramente con gradientes CSS (glow rosa/cyan, viñeta y puntos
  tipo bokeh en violeta/dorado) — cero fotos, logos, actores o texto. No es el asset
  final.

## Decisión sobre el asset real, 2026-09-02

El brief maestro pide un archivo auditado como `vhs-cassette-frame-v1.png` (prompt,
procedencia, hash, licencia). Esta sesión no tiene una herramienta de generación de
imágenes disponible. El owner generará el PNG por su cuenta con el prompt que se le
entregó en el chat (ambientación panorámica de videoclub/sala de cine nocturna, sin
logos, actores reconocibles, texto ni datos de una instancia). Cuando llegue:

1. Guardarlo como `src/movie_inbox/web/static/img/noche-de-cine-v1.png`.
2. Documentar procedencia/hash/licencia en `docs/assets/noche-de-cine-v1.md`, igual
   que `docs/assets/vhs-cassette-frame-v1.md`.
3. Agregar una única línea `background-image: url("../img/noche-de-cine-v1.png"), ...`
   a `.spotlight-ambience` en `home.css`, dejando los gradientes CSS actuales como
   capas de relleno/blend por si el PNG tiene transparencia. No hace falta tocar el
   HTML ni el JS.

Hasta entonces, la ambientación CSS ya es original, auditable por lectura directa (no
requiere ficha de procedencia porque no hay imagen involucrada) y coherente con la
paleta de `DESIGN.md`.

## Estados heredados, sin cambios de comportamiento

Carga (`home-loading-hero`/`home-loading-section`), vacío (`spotlight-empty`,
`homeEmpty`) y error/advertencia (`homeFeedback` para `collections_unavailable` /
`home_history_unavailable`, más el error genérico de `#empty` si `/api/items` falla)
ya existían de entregas anteriores y siguen intactos: esta entrega es puramente visual
sobre el contenedor y no toca `/api/home` ni `home_service.py`.

## Viewport sin scroll vertical (estado parcial)

El criterio de "el escenario completo entra sin scroll vertical en escritorio" se
declara explícitamente tanto en U2.1 como en U2.2 porque se completa entre las dos: la
cartelera más compacta de esta entrega reduce la altura que consume arriba, pero la
pieza que realmente decide el ajuste (una sola estantería editorial activa en vez de
apilar todas las filas verticalmente) es U2.2. Esta entrega no regresiona la altura
existente; no la resuelve por sí sola.

## Accesibilidad y pruebas

- `.spotlight-ambience` no es un landmark ni se anuncia; screen readers la ignoran por
  `aria-hidden` y por no llevar texto.
- El indicador de fila activa es decorativo; la identificación de estado sigue siendo
  `aria-pressed` + fondo/borde, ya cubiertos por pruebas previas.
- Nueva prueba de navegador
  (`test_home_marquee_shows_the_available_billboard_label_and_decorative_ambience`)
  confirma el rótulo visible, que la ambientación es `aria-hidden`/`pointer-events:
  none` y que no queda por encima de los controles reales en el z-index compartido.
  Las pruebas existentes de teclado, tabulación y ancho móvil del selector
  (`test_home_selector_keeps_one_tab_stop_and_changes_preview_with_arrows`,
  `test_collection_navigation_and_responsive_layout`) siguen en verde sin cambios.
