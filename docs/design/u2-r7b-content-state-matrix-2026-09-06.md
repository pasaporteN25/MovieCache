# U2-R.7b: matriz de contenido y estados límite

Fecha: 2026-09-06. Estado: **cerrado; sin bloqueos abiertos**.

## Alcance

Se recorrieron estados vacíos, cantidades límite de categorías, textos extensos,
posters ausentes o rotos, procedencia personal/Club y contratapas deterministas. Las
pruebas usan el catálogo sintético del navegador; no leen datos personales.

## Matriz verificada

| Estado | Resultado | Evidencia automatizada |
| --- | --- | --- |
| Home sin funciones ni categorías | Muestra pantalla en espera y tres recuperaciones; no deja filas, navegación ni mueble vacíos. | `test_home_empty_payload_exposes_recovery_without_empty_furniture` |
| Una categoría | Muestra un único módulo y oculta controles laterales innecesarios. | `test_home_single_category_long_content_and_broken_posters_remain_contained` |
| Dos categorías cortas | Compacta módulos, rotula `1 título` y no inventa overflow. | `test_home_shelf_furniture_compacts_and_labels_short_categories` |
| Cuatro categorías | Conserva los cuatro módulos en un recorrido lateral real, con límites y controles coherentes. | `test_home_shelf_furniture_has_four_bays_real_overflow_and_wheel_limits` |
| Título y géneros extensos | No generan overflow horizontal; playlist y lomo preservan el contenido completo en sus nombres accesibles. | `test_home_single_category_long_content_and_broken_posters_remain_contained` |
| Nombre de instancia largo | `Movie Inbox Browser Test` entra completo en 1280×720, 1440×900 y 1920×1080 sin agrandar la cabecera. | mismo caso extremo |
| Poster ausente | Cartelera, preview y mueble presentan el fallback material correspondiente. | gate visual R7a y casos de home existentes |
| Poster roto | Cartelera, preview superior y consola ocultan la imagen fallida y revelan un fallback estable. | mismo caso extremo y `test_mobile_home_restores_header_preview_and_broken_poster_flow` |
| Entrada personal | Ofrece `Ver más` y `Editar mi ficha`; la edición abre el formulario personal. | `test_home_shelf_preview_shows_edit_action_only_for_personal_entries` |
| Entrada de Club | Ofrece `Ver ficha del Club`, nunca edición personal, y permite agregar al catálogo desde la ficha compartida. | `test_home_shelf_collection_entries_never_show_an_edit_action` |
| Contratapa determinista | Cinco IDs conservan plantilla estable; cada variante muestra dos marcos y el contenido largo se desplaza dentro de la carcasa. | `test_back_cover_template_mapper_is_stable_for_opaque_ids` y `test_home_shelf_view_more_opens_deterministic_back_cover_with_reversible_transition` |

## Correcciones aplicadas

### Recuperación de posters rotos

La cartelera y su preview ahora renderizan fallback junto a toda imagen remota. El
manejador compartido mantiene uno solo visible: carga correcta oculta el fallback y
error oculta la imagen. La consola inferior conserva el mismo contrato.

### Nombre de instancia sin truncado prematuro

La marca puede ocupar más ancho y usa una escala compacta de 32–38 px cuando la altura
es limitada. Estadísticas y navegación siguen en la misma línea; la cabecera permanece
en 60 px y no aparece overflow horizontal.

### Estabilidad del gate de navegación

La regresión que vuelve a Inicio mediante la marca espera a que el catálogo termine de
cargar antes de abrir otra utilidad. Esto elimina una carrera de prueba donde el HTML
inicial ya estaba visible pero el listener delegado aún no había terminado de arrancar.

## Verificación

- `BrowserInterfaceTests` + `DesignTokenTests`: **32/32**.
- Caso extremo dedicado repetido de forma aislada: **1/1**.
- JavaScript validado con `node --check`.
- `git diff --check`: sin errores.

## Próximo corte

Continúa **U2-R.7c**, gate de interacción y accesibilidad: click, Enter, flechas,
temporizador, foco/retorno, touch, nombres accesibles, reduced motion y reflow móvil.
