# Abrir la caja hacia el dossier (U2.3)

> Registro histórico. En `release/0.10.0`, «Abrir ficha» presenta la contratapa
> independiente y reemplaza la transición de toda la página por una entrada CSS
> local de la caja. Ver [consulta rápida de Inicio](home-quick-consultation-v1.md).

## Alcance

`Ver más`, en la previsualización de una estantería de Inicio, abre el mismo dossier
compartido (`#detailDrawer`) que ya usan Colección, Club y el resto de la app —
`/api/*` y las rutas no cambian. Esta entrega agrega dos cosas encima de ese flujo ya
existente: una transición decorativa y reversible entre la caja y el dossier, y un
cassette VHS negro que acompaña la ficha una vez abierta.

## Decisión del owner, 2026-09-03

El cassette VHS negro es un elemento visual permanente del dossier compartido, sin
importar desde dónde se abra (Inicio, Colección, Club) — no un estado condicional según
el punto de entrada. Se resuelve enteramente en CSS vanilla, sin librerías ni un asset
nuevo, igual que la ambientación de la cartelera antes de tener el PNG real.

## Transición reversible

`openDetailWithCaseTransition(target, id)` (`detail.js`) envuelve la apertura en
`document.startViewTransition()` cuando el navegador lo soporta y no hay
`prefers-reduced-motion`; si falta cualquiera de las dos condiciones, abre directo, sin
animación. `closeDetail()` recuerda (`detailOpenedWithCaseTransition`) si el dossier
actual se abrió por ese camino y envuelve el cierre de la misma manera, así que la
animación es reversible de verdad: abrir y cerrar usan el mismo mecanismo, no una
animación de entrada sin salida.

Sólo el botón `Ver más` de la previsualización de estantería usa este camino
(`data-click="open-detail-with-case-transition"`); `Editar mi ficha` y el resto de los
puntos de entrada al dossier siguen usando `openDetail()`/`openDetailFromTrigger()` sin
cambios — la transición es específica de "abrir la caja", no un rediseño global de cómo
se abre cualquier ficha.

Las keyframes (`vhs-case-open`/`vhs-case-close` en `core-detail.css`) animan
`::view-transition-old(root)`/`::view-transition-new(root)`: no intentan un morph
geométrico exacto desde el lomo o la previsualización (dos formas demasiado distintas
para que un "shared element transition" real se vea convincente), sino un efecto de
apertura/cierre decorativo sobre la transición completa de la pantalla. `a11y.css` suma
un respaldo (`::view-transition-*{ animation: none !important }`) bajo
`prefers-reduced-motion` por si el navegador dispara una transición de todos modos —
aunque el guard en JS ya evita llamar a la API en ese caso.

**No bloquea Escape ni el foco**: la API sólo agrega una capa visual sobre una
mutación del DOM que ya sucede sincrónicamente dentro del callback (abrir/cerrar el
`<dialog>` nativo); Escape sigue disparando el `cancel` existente y el diálogo sigue
siendo interactivo durante toda la transición. Un fix necesario en el camino: el foco de
retorno (`detailReturnFocus`) se capturaba comparando
`activeElement.matches("[data-click='open-detail']")`, un literal que dejaba de
coincidir con el nuevo `data-click`; ahora compara con `dataset.click?.startsWith("open-detail")`,
cubriendo cualquier variante futura del mismo verbo.

## Cassette VHS negro reutilizable

`drawerPoster()` (la única función compartida por el dossier personal, la ficha de
Club y la ficha de colección de Inicio) agrega `.drawer-vhs-case` con dos
`.drawer-vhs-reel`, 100% CSS: una carcasa oscura detrás de la portada real o su
placeholder, que se asoma por los cuatro lados (14px) y bastante más abajo (38px) para
que los dos "carretes" queden visibles debajo de la carátula en vez de tapados por
ella. Es decorativo (`aria-hidden="true"`, `pointer-events: none`), nunca sustituye la
portada ni sus estados de carga/error ya existentes (`handlePosterLoad`/`handlePosterError`
en `card.js` siguen operando exactamente igual sobre `[data-poster-image]`).

Al ser parte de `drawerPoster()` y no de una plantilla nueva, el componente es
automáticamente el mismo en el dossier personal (`#detailDrawer`), la ficha compartida
de Club (`#sharedDetailDialog`) y el detalle de una recomendación de colección en
Inicio — un solo lugar para mantenerlo.

## Fuera de alcance

- No cambia `/api/*`, rutas ni el contenido del dossier más allá del cassette.
- No es un shared-element transition geométrico (lomo → dossier); ver justificación
  arriba.
- No agrega una librería de animación: sólo View Transitions API nativa + CSS.

## Pruebas

`test_home_shelf_view_more_opens_dossier_with_reversible_case_transition` cubre: el
cassette existe, es `aria-hidden`/`pointer-events: none`; Escape cierra sin bloquear
foco (usa `page.wait_for_function` para el foco en vez de una sola lectura síncrona,
porque Chromium asienta el foco un tick después de que el `<dialog>` cierra mientras la
transición todavía se está capturando); y con `prefers-reduced-motion` el mismo abrir y
cerrar sigue funcionando. Se optó por no instrumentar `document.startViewTransition`
para contar invocaciones: envolver la función real con un wrapper cambia lo suficiente
el timing como para introducir exactamente esa misma carrera en el foco — la prueba
verifica comportamiento end-to-end, no la llamada a la API en sí. También se corrigió
`page.wait_for_selector("#detailDrawer:not([open])")` (usado en pruebas de esta
entrega) para pasar `state="hidden"`: el estado por defecto de Playwright es
`"visible"`, que nunca se cumple para un diálogo cerrado.
