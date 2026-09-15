# Estanterías de lomos y previsualización VHS (U2.2)

Reemplaza el tratamiento visual de U1.2 (`docs/briefs/home-shelves-v1.md`, todavía
vigente como registro histórico) sin tocar `/api/home`, `home_service.py` ni el
contrato de datos: `EditorialHomeService` sigue siendo la única fuente del orden, las
secciones y sus hasta seis entradas.

## Selector de categoría: una sola estantería activa en escritorio

`#homeShelfCategories` es una nueva barra de botones nativos con roving tabindex
(flechas izquierda/derecha, Home/End, clic/Enter), un tab por sección no vacía. En
escritorio (`min-width: 861px`), `.home-program[data-active="false"]` se oculta por
CSS: sólo la estantería elegida se muestra, cumpliendo "no apilar todas las filas". En
móvil (`max-width: 860px`, el mismo corte que ya usa `.spotlight-selector-options`),
`#homeShelfCategories` se oculta y **todas** las secciones vuelven a apilarse y hacer
scroll vertical, igual que antes de esta entrega — el brief maestro permite
explícitamente ese crecimiento en pantallas chicas.

Con una sola sección no vacía, el selector no se renderiza (no tiene sentido elegir
entre una opción); esa sección se muestra sola, igual que siempre.

## Lomos en vez de cajas frontales

`homeShelfTape()` ya no usa `.vhs-cassette`/`vhs-cassette-frame-v1.png`: cada obra es
un botón `.vhs-spine` angosto (`clamp(64px, 7vw, 92px)` de ancho, `clamp(190px, 22vw,
250px)` de alto), con una etiqueta dorada decorativa arriba y el título/año-género en
texto vertical (`writing-mode: vertical-rl`) real, no rotado por imagen — sigue siendo
HTML accesible, sólo cambia su presentación visual. El estado seleccionado se resuelve
con `aria-pressed` + borde dorado + elevación; la carcasa nunca fue la única señal de
estado. Roving tabindex, flechas/Home/End y clic se heredan sin cambios de U1.2.

## La previsualización se convierte en la caja frontal auditada

`vhs-cassette-frame-v1.png` se mueve de la fila a la previsualización: al elegir un
lomo, `.home-shelf-preview-art` monta `.home-shelf-preview-frame` (el marco, decorativo,
`aria-hidden`) por encima de la portada real o su placeholder — la ventana de etiqueta
vacía del PNG deja ver la portada, mientras el marco enmarca visualmente la carátula. Es
exactamente el mecanismo que pedía el brief maestro ("previsualización basada en
`vhs-cassette-frame-v1.png`, caja frontal/portada"). `docs/assets/vhs-cassette-frame-v1.md`
se actualizó para reflejar el nuevo selector CSS (mismo archivo, mismo hash: no hace
falta re-auditar un asset que no cambió de contenido).

## Acciones de la previsualización: `Ver más` y `Editar mi ficha`

- El botón que abre el dossier completo ahora se llama `Ver más` (antes "Abrir
  ficha"), el término que usa el resto de la epopeya U2 para esa acción.
- Para entradas de origen `catalog` (obra propia, editable) se suma `Editar mi ficha`:
  abre el mismo dossier y lo deja directamente en modo de edición del registro
  personal (`openDetailForPersonalEdit()` en `detail.js` = `openDetail()` +
  `editPersonalRecord()`, reutilizando el editor de fecha/puntaje/review que ya existe
  dentro de la ficha — no hay un editor nuevo).
- Para entradas de origen `collection` (recomendación de una colección de Club, todavía
  no en el catálogo personal) no aparece `Editar mi ficha`: sólo `Ver ficha del Club`,
  igual que antes. Esto es lo mínimo que pide U2.2 ("aparece solamente para una obra
  editable"); [U2.4] es quien debe endurecer permisos, Club y superficies de sólo
  lectura de punta a punta.

## Fuera de alcance

- No se cambia `/api/home`, el orden de secciones ni el límite de seis entradas.
- No se implementa todavía la transición reversible hacia el dossier completo (U2.3).
- No se audita ni construye un asset nuevo: se reutiliza `vhs-cassette-frame-v1.png`
  con una nueva regla CSS.

## Accesibilidad y pruebas

- El marco decorativo y la etiqueta dorada del lomo son puramente visuales
  (`aria-hidden`, sin texto generado); título/año/género/motivo siguen siendo HTML real.
- `prefers-reduced-motion` anula las transiciones de `.vhs-spine` y
  `.home-shelf-preview-frame` (ver `a11y.css`).
- Pruebas de navegador nuevas: `test_home_shelf_categories_show_one_active_shelf_on_desktop_and_all_on_mobile`
  (roving tabindex del selector, una sola estantería visible en escritorio, todas
  visibles y categorías ocultas en 390px) y
  `test_home_shelf_preview_shows_edit_action_only_for_personal_entries` (el botón
  aparece sólo para origen `catalog` y abre el dossier ya en modo edición, con foco en
  el campo de fecha). La prueba existente de estanterías
  (`test_home_shelves_use_existing_sections_with_keyboard_preview_and_touch_scroll`) se
  actualizó para verificar el marco en la previsualización en vez de en la fila, y el
  scroll táctil con más entradas (los lomos angostos no desbordan un viewport móvil por
  sí solos con sólo dos obras).
