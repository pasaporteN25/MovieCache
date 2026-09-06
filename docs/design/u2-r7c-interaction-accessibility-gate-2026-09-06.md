# U2-R.7c: gate de interacción y accesibilidad

Fecha: 2026-09-06. Estado: **cerrado; sin hallazgos P1 abiertos**.

## Alcance y método

Se recorrió la home recuperada con el catálogo sintético del navegador. La cobertura
combina teclado, mouse y un contexto Chromium móvil independiente con `has_touch`,
`is_mobile` y `prefers-reduced-motion: reduce`; no usa catálogos personales.

El gate comprueba el árbol accesible calculado por el navegador mediante roles y nombres,
además del foco DOM y su indicador visible. No reemplaza una campaña manual exhaustiva
con NVDA/VoiceOver, pero sí cierra las rutas y estados que bloqueaban la aceptación U2-R.

## Matriz verificada

| Recorrido | Resultado | Evidencia automatizada |
| --- | --- | --- |
| Click directo en un lomo | Activa su estantería y preview sin reprogramar la playlist superior. | `test_direct_spine_choice_activates_its_bay_but_keeps_playlist_independent` |
| Enter en un lomo | Repite el mismo cambio de estado, conserva el foco y muestra un outline de al menos 2 px. | mismo caso |
| Flechas y Home/End | Mueven cartelera, playlist, lomos y recorrido lateral sin crear un segundo tab stop. | `test_home_selector_keeps_one_tab_stop_and_changes_preview_with_arrows`, `test_home_playlist_columns_and_autoplay_keep_manual_selection_and_focus`, `test_home_shelves_use_existing_sections_with_keyboard_preview_and_touch_scroll` |
| Cambio explícito de estantería | Sincroniza la fuente superior sólo al activar el módulo, restaurando su selección recordada. | `test_direct_spine_choice_activates_its_bay_but_keeps_playlist_independent` |
| Temporizador | Avanza la cartelera sin perder la selección manual ni el foco; se detiene fuera de Inicio. | `test_home_playlist_columns_and_autoplay_keep_manual_selection_and_focus` |
| Movimiento reducido | El tick no avanza la cartelera, el recorrido usa scroll inmediato y la apertura/cierre conserva el cambio de estado. | `test_mobile_touch_accessible_names_and_reduced_motion_survive_reflow`, `test_home_shelf_furniture_has_four_bays_real_overflow_and_wheel_limits`, `test_home_shelf_view_more_opens_deterministic_back_cover_with_reversible_transition` |
| Foco y retorno | `Ver más` lleva el foco al cierre de la contratapa; Escape devuelve el foco al disparador. | `test_home_shelf_view_more_opens_deterministic_back_cover_with_reversible_transition` |
| Touch real | Un tap selecciona un lomo de otra estantería, abre la contratapa y permite cerrarla en un contexto táctil real. | `test_mobile_touch_accessible_names_and_reduced_motion_survive_reflow` |
| Nombres accesibles | Mueble, playlist y lomos exponen rol/nombre; cada lomo conserva título, año, formato, motivo y posición completos. | mismo caso y regresiones de contenido largo de R7b |
| Reflow 390/320 px | No aparece overflow horizontal; el mueble sigue alcanzable y el lomo seleccionado conserva un target mínimo de 44×44 px. | mismo caso y `test_mobile_home_restores_header_preview_and_broken_poster_flow` |

## Audit Health Score de R7c

| # | Dimensión | Score | Evidencia principal |
| --- | --- | --- | --- |
| 1 | Accesibilidad | 3/4 | Teclado, nombres, foco, touch y movimiento reducido cubiertos; queda como mejora una pasada manual con lector de pantalla. |
| 2 | Performance | 3/4 | Autoplay acotado, imágenes lazy y transiciones evitadas bajo reduced motion; profiling integral pertenece a R7d. |
| 3 | Responsive | 4/4 | 390/320 px sin overflow ni targets táctiles menores a 44×44 en el recorrido crítico. |
| 4 | Theming | 3/4 | Foco, forced colors y jerarquía de señal son coherentes; resta inventariar tonos materiales heredados. |
| 5 | Integridad de implementación | 4/4 | Roles, estado y foco siguen el modelo específico cartelera → playlist → mueble → contratapa. |
| **Total** |  | **17/20 — Muy bueno** | **R7c puede cerrar.** |

## Detector e integridad

El detector de `impeccable` sobre todo `src/movie_inbox/web/static` produjo 147 entradas:
146 avisos consultivos de documentación de color/tipografía y un warning. El warning
`side-tab` de `home.css` es un falso positivo verificado: la declaración detectada forma
el triángulo de 6 px del indicador seleccionado mediante bordes transparentes de un
pseudo-elemento; no es un borde lateral aplicado a una tarjeta.

Los avisos consultivos no describen una regresión de interacción. Su inventario y la
decisión de qué tonos materiales deben incorporarse a `DESIGN.md` quedan en R7d; no se
tokenizan automáticamente sombras, desgaste ni colores propios de los objetos VHS.

## Hallazgos por severidad

- **P0/P1:** ninguno verificado.
- **P2:** ninguno verificado dentro del recorrido U2-R.7c.
- **P3:** ninguno que justifique cambiar la interfaz antes del cierre contractual.

## Verificación

- Matriz focal de interacción/accesibilidad: **10/10**.
- Caso táctil nuevo repetido de forma aislada: **1/1**.
- Regresión de foco visible repetida de forma aislada: **1/1**.
- Detector integral: **0 hallazgos bloqueantes**; un warning descartado en contexto.

## Próximo corte

Continúa **U2-R.7d**: suites completas, formato/tipos/compilación, resolución o registro
de gates rojos y actualización final del brief, la revisión y el backlog.
