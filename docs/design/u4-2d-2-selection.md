# U4.2d.2 — Selección compartida

2026-09-11. Implementada y verificada, sin commit todavía. No cambia assets ni CSS
productivo; no retira la consola inferior (d.3).

## Contrato implementado

- `playlistSource` conserva la programación de la tabla.
- `carouselItemId` / `spotlightIndex` conservan la rotación independiente del póster.
- `selectionSource` + `selectedEntryKey` identifican la obra consultada en la consola
  superior. No se resuelve una obra del Club por coincidencia de ID con el catálogo.
- Clic o flechas sobre un VHS actualizan esa consulta y su categoría activa sin
  reprogramar la tabla ni mover el póster. La rotación posterior conserva la consulta.
- Una fila vuelve a tomar la consulta desde la programación actual. Si la consulta
  pertenece a otro origen, no queda una fila marcada falsamente: la primera conserva
  un punto de entrada con Tab. Se preserva el foco del lomo y de las acciones de la
  consola durante el rerender del póster.
- La activación explícita de una categoría sigue programando esa categoría. Hoy/Ayer
  y la selección explícita del póster mantienen su comportamiento de volver a la
  programación diaria; no se confunden con una rotación automática.
- Fuente/entrada ausente: se usa la primera obra programada o se vacía la consulta,
  sin dejar acciones de una obra obsoleta. Una lista diaria vacía no impide consultar VHS.
- Las acciones superiores usan la obra y el origen consultados. Club muestra su ficha,
  no edición personal; el origen se propaga al abrir detalle mediante `bootstrap.js`.
  Los permisos del backend y los flujos de escritura no se modifican.

## Archivos

- `src/movie_inbox/web/static/js/surfaces/home.js`: estado, resolución, render y foco.
- `src/movie_inbox/web/static/js/core/bootstrap.js`: origen explícito al abrir ficha Club.
- `tests/js/home-selection.test.mjs`: seis pruebas del módulo real, con adaptadores
  inertes de DOM/dependencias. No reemplazan una prueba de navegador.
- `tests/browser/test_ui_browser.py`: actualizada la expectativa anterior que exigía
  que el VHS no cambiara la consulta superior. Se preservan cambios previos del archivo.
- El comparador d.1 incorpora el comportamiento nuevo y un botón de prueba que llama
  al mismo `tickHomeAutoplay` productivo; no altera preferencias de movimiento reducido.
  Propuesta/Anterior compara **encuadre**, no versiones históricas de interacción.

## Evidencia

```powershell
node --experimental-vm-modules --test tests/js/home-selection.test.mjs
.venv/Scripts/python.exe -m unittest tests.test_package_layout tests.test_home_service tests.test_home_snapshot_repository
```

Resultado: **6/6 JS y 20/20 Python**. El flag experimental sólo corresponde al
aislamiento del módulo en las pruebas Node; la aplicación no agrega dependencias.

Navegador conectado, comparador con renderer real y fixture sintética:

- «Órbitas de papel» actualiza la consola; rotación avanza a «El faro de niebla» sin
  cambiar consulta ni las seis filas (contenido comparado antes/después).
- Flechas de playlist y de VHS actualizan la consulta y conservan foco en el control.
- Cambio explícito a Ayer devuelve `selectionSource=daily`.
- En 390×844, flecha sobre VHS consulta «La habitación 27» y mantiene foco; sin
  overflow de página. Inspección desktop 1440×900, sin alterar la composición d.1.
- Sin errores capturados de consola. Captura:
  `u4-2d-1-composition/selection-shared-d2-1440.png`.

No se ejecutó la suite completa de Playwright ni se ejercieron escrituras reales en
el comparador. El gate integral de acciones/permisos y consolidación queda en d.3/U4.6.
La prueba de coincidencia de claves Club/catálogo, foco tras autoplay, eliminación de
entrada, fuente vacía y movimiento reducido corre en las seis pruebas JS.

## Sigue U4.2d.3

Aplicar el encuadre centrado a producción, reunir imágenes/créditos/estados y acciones
útiles en la consola superior, retirar el componente inferior y validar el conjunto.
U4.3 pulirá esa consola definitiva. No se cierra U4.2 ni U4 completo con esta entrega.
