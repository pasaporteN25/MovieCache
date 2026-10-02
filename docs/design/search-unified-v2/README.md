# Búsqueda unificada — U12

Dirección aprobada el 2026-10-02: [brief de búsqueda unificada](../../briefs/search-unified-v2.md). Esta entrega extiende el mostrador de U10 y las filas compactas y revisión integrada de duplicados de [U12 v1](../search-workbench-v1/README.md). La revisión visual de escritorio y de 320/390 px concluyó **Ship**.

## Decisiones de diseño

Una consulta activa muestra una sola lista de obras guardadas y referencias externas. Las filas comparten miniatura sin recorte, título, metadata, resumen y acciones. Se conserva el mundo nocturno del mostrador: superficies petróleo, tinta cálida, separadores metálicos, placa Oswald, títulos Barlow Condensed y datos IBM Plex Mono. Las filas permanecen planas; el foco cyan y el cambio de superficie ayudan a ubicar la acción. La revisión de duplicados conserva su panel contextual.

La relevancia entregada por el servidor determina el orden común; ante empate aparece primero la obra guardada. El puntaje no se presenta como probabilidad de identidad. «En tu colección», estado y disponibilidad distinguen las obras propias; fuente y atribución identifican las referencias externas. Abrir/editar y agregar/comparar/enlace externo conservan sus tareas respectivas.

Una paginación acumula los resultados. Los estados progresivos, errores y reintentos de las fuentes se reúnen en un desplegable compacto; los filtros personales activos tienen un aviso. Los títulos y acciones admiten salto de línea en pantallas angostas. Limpiar la consulta recupera la estantería VHS. La selección conserva la identidad de la referencia cuando responde otra fuente; el matching conservador y las decisiones explícitas de X12 siguen vigentes.

## Evidencia visual

| Estado | Captura |
| --- | --- |
| Escritorio, página completa (1280 × 900 de viewport) | [desktop-full.png](desktop-full.png) |
| Escritorio, lista unificada | [desktop.png](desktop.png) |
| Escritorio, revisión de duplicados integrada | [desktop-duplicate.png](desktop-duplicate.png) |
| Móvil, viewport 390 × 844 | [mobile-390.png](mobile-390.png) |
| Móvil, viewport 320 × 844 | [mobile-320.png](mobile-320.png) |

Las capturas renderizan la interfaz de producción con un servidor local y catálogo/base de identidad temporales creados por el arnés de navegador. [capture.py](capture.py) intercepta búsqueda y agregado con fixtures ilustrativos: Heat guardada (1995), referencias de IMDb/Wikipedia/FilmAffinity y seis filas sintéticas para mostrar paginación. Las respuestas, relevancias y el posible duplicado están preparados para la revisión; no son resultados obtenidos de esas fuentes ni representan una biblioteca personal real. Los enlaces externos aportan contexto de procedencia y algunos son deliberadamente ficticios. La ausencia de portadas permite comprobar el placeholder honesto.

Para reproducir desde la raíz del repositorio, con las dependencias del proyecto y Chromium de Playwright instalados:

```powershell
.venv\Scripts\python.exe docs\design\search-unified-v2\capture.py
```

El script inicia y cierra el servidor temporal, espera las fuentes tipográficas, desactiva animaciones para las capturas y comprueba que no haya desbordamiento horizontal a 390 y 320 px. Escribe las cinco imágenes en este directorio.

## Validación y relación con el sistema vigente

La entrega registró **60 pruebas de navegador y 73 pruebas HTTP aprobadas**. La revisión de las capturas de escritorio y móvil dio **Ship**. Las imágenes ilustran la composición; las pruebas cubren el comportamiento de la entrega.

Este documento registra una extensión de superficie, no una sustitución del sistema visual. [DESIGN.md](../../../DESIGN.md) permanece como autoridad incumbente y conserva su texto histórico de U10 sobre resultados externos separados; el brief aprobado de U12 v2 establece la lista común para esta consulta. La paleta material y los roles tipográficos se heredan del mostrador. Las variantes de color y el pequeño panel elevado de duplicados son locales a esta superficie.

[detector.json](detector.json) conserva avisos de colores literales fuera de los tokens documentados, entre ellos los tonos del fallback VHS y variantes de filas/controles. Son discrepancias documentales pendientes, no una autorización para ampliar la paleta global. El sidecar [.impeccable/design.json](../../../.impeccable/design.json), generado el 2026-08-31, sigue anterior a las extensiones U10/U12. Esta pasada conserva ambos archivos y deja explícita esa deriva documental sin repararla fuera del alcance solicitado.
