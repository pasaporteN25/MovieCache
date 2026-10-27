# Inicio como mostrador de búsqueda — IP1/IP2

Evidencia de la entrega de Inicio con un único póster y un buscador integrado, descrita en el [brief](../../briefs/home-search-desk-v1.md). El carrusel, el autoplay, la tabla de programación y los controles Hoy/Ayer se retiraron: a la izquierda vive el buscador (`#homeSearchSlot`), a la derecha el póster de la obra consultada (Sugerencia, Resultado o Tu selección) y debajo su consola. El estante VHS no cambia.

Las capturas usan datos de prueba ilustrativos y afiches generados por el script; los resultados externos son simulados y no representan una biblioteca real. Se regeneran con `python docs/design/home-search-desk-v1/capture.py` (requiere `.[browser-test]` y `playwright install chromium`).

| Ancho | Inicio en reposo | Búsqueda «Heat» (fila local activa) |
| --- | --- | --- |
| 390 px | [home-390.png](home-390.png) | [search-390.png](search-390.png) |
| 1280 px | [home-1280.png](home-1280.png) | [search-1280.png](search-1280.png) |
| 1440 px | [home-1440.png](home-1440.png) | [search-1440.png](search-1440.png) |
| 1920 px | [home-1920.png](home-1920.png) | [search-1920.png](search-1920.png) |

En las búsquedas se ven los tres estados de fila: «Ya la tenés», «Revisar» (coincidencia dudosa, nunca escribe) y «+ Pendiente». En 390 px el desplegable ocupa la pantalla y el póster se oculta mientras está abierto. Ninguna captura tiene scroll lateral.
