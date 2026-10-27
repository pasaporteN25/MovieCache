# Inicio como mostrador de búsqueda — IP1/IP2/IP3

Evidencia de la entrega de Inicio con un único póster y un buscador integrado, descrita en el [brief](../../briefs/home-search-desk-v1.md). El carrusel, el autoplay, la tabla de programación y los controles Hoy/Ayer se retiraron: a la izquierda vive el buscador (`#homeSearchSlot`), a la derecha el póster de la obra consultada (Sugerencia, Resultado o Tu selección). En IP3 se quitó la consola inferior (la información vive en los lomos y en la ficha), el póster creció un 20 % (`clamp(248px, 16.3vw, 328px)`) y, al elegir un VHS, la placa y el lomo se resaltan y el hueco bajo el campo muestra el panel «Sección seleccionada» con «Volver a la sugerencia». El estante VHS no cambia.

Las capturas usan datos de prueba ilustrativos y afiches generados por el script; los resultados externos son simulados y no representan una biblioteca real. Se regeneran con `python docs/design/home-search-desk-v1/capture.py` (requiere `.[browser-test]` y `playwright install chromium`).

| Ancho | Inicio en reposo | Campo con foco (sugerencias) | Búsqueda «Heat» (fila local activa) | VHS elegido (IP3) |
| --- | --- | --- | --- | --- |
| 390 px | [home-390.png](home-390.png) | [focus-390.png](focus-390.png) | [search-390.png](search-390.png) | [section-390.png](section-390.png) |
| 1280 px | [home-1280.png](home-1280.png) | [focus-1280.png](focus-1280.png) | [search-1280.png](search-1280.png) | [section-1280.png](section-1280.png) |
| 1440 px | [home-1440.png](home-1440.png) | [focus-1440.png](focus-1440.png) | [search-1440.png](search-1440.png) | [section-1440.png](section-1440.png) |
| 1920 px | [home-1920.png](home-1920.png) | [focus-1920.png](focus-1920.png) | [search-1920.png](search-1920.png) | [section-1920.png](section-1920.png) |

En las búsquedas se ven los tres estados de fila: «Ya la tenés», «Revisar» (coincidencia dudosa, nunca escribe) y «+ Pendiente». En 390 px el desplegable ocupa la pantalla y el póster se oculta mientras está abierto. Ninguna captura tiene scroll lateral.

En las capturas «VHS elegido» se ve la placa de la sección con aro rosa, el lomo elegido con su resplandor y el panel bajo el campo. A 390 px el panel queda sobre el póster; con el desplegable abierto desaparece junto con él.
