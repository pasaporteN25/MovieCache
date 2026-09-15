# U5.4–5 — gate local de teclado, origen y fuentes

2026-09-14. Aplicación productiva ejecutada contra catálogos temporales del runner
Chromium/Playwright. Cierre de U5.4 y U5.5; no aprobación de publicación v0.9.0.
Impeccable/harden guio los ajustes; se conserva el material, retícula y tipografía aprobados.

## Resultado

- VHS/placa/fila sincronizan lista y consulta. Tab no selecciona; Enter/Espacio,
  flechas e Inicio/Fin mantienen el recorrido acordado. Autoplay sólo cambia izquierda.
- Una región anuncia la consulta; elegir de nuevo la misma obra no vuelve a escribir
  el mismo anuncio. Verificado con MutationObserver, no con lector de pantalla físico.
- Club con la misma clave/ID que una obra personal mantiene título, origen y acciones
  propios. Consola, póster derecho y revisión de imágenes abren su ficha compartida;
  Escape devuelve foco al mismo acceso. No aparece edición personal ni se envían
  POST/PATCH/PUT/DELETE por consultar. No se modificó autorización del servidor.
- Fuentes de 0/1/6/20/100: sin acciones obsoletas, scroll local, fila final visible
  bajo encabezados fijos, sin desplazamiento del documento al seleccionar.
  Las listas extendidas son fixtures, no un aumento del límite editorial de producción.
- Fuente vaciada: cero obras y retorno disponible; eliminada: programación diaria.
  Fila eliminada: siguiente selección válida o retorno; lomo eliminado: placa o región
  de estantes. Una clave coincidente en otro origen no se reutiliza como foco de fila.
- Error de Hoy/Ayer conserva la consulta y ofrece reintento. Respuestas tardías no
  pisan una navegación posterior ni muestran errores obsoletos; los controles se liberan.

## Fallos reproducidos y corregidos

1. Respuesta pendiente de Ayer reemplazaba un VHS elegido después. Dos pruebas JS
   fallaron antes del cambio: cancelación lógica por generación de petición;
   éxito/error de peticiones obsoletas se ignoran. La petición HTTP puede terminar,
   pero ya no aplica estado. Seleccionar fila, VHS, placa, programación o nuevo payload
   invalida la petición pendiente. No se cancela por un Tab pasivo.
2. Al desaparecer una fila enfocada el foco caía al documento. Prueba Chromium roja
   en 1/6/20/100: fallback a control válido y origen calificado, con preventScroll.
3. CSS de escritorio prevalecía sobre los 44 px de los botones móviles: corregida
   especificidad, sin agrandar los controles de escritorio.
4. El lomo conservaba transición con reduced-motion: ahora ninguna transición de lomo.

## Reproducción

Desde la raíz del repositorio, con el entorno `.venv` y Chromium de Playwright instalados:

```powershell
$u5Cases = @(
  'test_home_poster_replaces_dots_and_keeps_keyboard_navigation',
  'test_home_shelves_use_existing_sections_with_keyboard_preview_and_touch_scroll',
  'test_home_playlist_columns_and_autoplay_keep_manual_selection_and_focus',
  'test_direct_spine_choice_synchronizes_playlist_and_shared_console',
  'test_home_shelf_preview_shows_edit_action_only_for_personal_entries',
  'test_home_shelf_collection_entries_never_show_an_edit_action',
  'test_selecting_and_previewing_a_shelf_entry_never_mutates_the_catalog',
  'test_home_shelf_view_more_opens_deterministic_back_cover_with_reversible_transition',
  'test_u5_source_counts_keyboard_alignment_and_removal',
  'test_u5_club_collision_dialog_focus_and_single_announcement',
  'test_u5_day_failure_retry_focus_and_cached_return',
  'test_u5_removed_focused_spine_recovers_without_focusing_a_different_origin',
  'test_home_empty_payload_exposes_recovery_without_empty_furniture',
  'test_home_material_plaques_and_inset_spines_keep_geometry_on_desktop_and_mobile',
  'test_home_furniture_console_keeps_primary_copy_legible_at_desktop_sizes'
) | ForEach-Object { 'tests.browser.test_ui_browser.BrowserInterfaceTests.' + $_ }
.venv/Scripts/python.exe -m unittest @u5Cases -q
node --experimental-vm-modules --test tests/js/home-selection.test.mjs tests/js/home-images.test.mjs
.venv/Scripts/python.exe -m unittest tests.test_package_layout tests.test_home_service -q
node --check src/movie_inbox/web/static/js/surfaces/home.js
git diff --check
```

Resultado: **15 pruebas Chromium + 26 JS + 17 Python aprobadas**; sintaxis/diff correctos.
Ocho pruebas históricas de interacción fueron migradas conservando sus recorridos,
reemplazando los contratos retirados: segunda consola, onda decorativa, selección
inicial de VHS y lista independiente al pulsar lomo. Cuatro escenarios U5 nuevos.
Los tres casos restantes protegen vacío y geometría visual.

## Límites y siguiente paso

- Evidencia visual amplia previa: `u5-long-list-gate/`, `u5-first-delivery/`.
- Sigue abierto **U5.3.4: zoom real al 200%**. El reflow equivalente no lo sustituye.
- U4.6b sigue abierto para el resto de la suite histórica; este gate es un subconjunto
  explícito, no una ejecución de toda la suite de navegador ni de CI del PR.
- Sin revisión independiente de subagente en este corte. Revisión local de código
  y pruebas; no cambios de assets, backend, dependencias o datos reales, ni commit.
- Actualización del owner, 2026-09-14: U8 diferida a otra release; siguiente frente
  es cerrar los gates de v0.9.0 según `v0-9-0-visual-closeout.md`.
