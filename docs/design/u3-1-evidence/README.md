# Evidencia U3.1 — estado previo de Colección

Capturas reproducibles tomadas el 2026-09-08 con el fixture autenticado de navegador.
No representan la propuesta nueva: documentan la superficie que U3 debe reemplazar.

El usuario aprobó el wireflow y el contrato derivados de esta evidencia el 2026-09-08.

## Hallazgos prioritarios

1. **La intención no es visible.** Explorar, buscar y agregar comparten la misma consola;
   el comando global `Agregar` sólo abre la raíz de Colección.
2. **Búsqueda y filtros divergen.** Los filtros de estantería siguen visibles, pero las
   tarjetas de «Coincidencias locales» aclaran que no los aplican. La consulta reemplaza
   la grilla material por otro componente.
3. **La restauración de Comparar es incompleta.** El modo y la consulta llegan a la URL,
   pero la obra externa elegida depende de `manualResults[selectedManualIndex]`; no hay
   referencia estable para recarga o enlace compartido.
4. **La consola domina el viewport.** Mide 191 px en browse desktop y 686 px con un solo
   resultado. En 390 px pasa de 264 a 819 px, antes de recuperar la estantería.
5. **Móvil pierde legibilidad operacional.** Consulta y botón compiten por ancho, los
   filtros rápidos quedan recortados en un carril y la navegación inferior reduce el
   área útil de acciones/resultados.

## Capturas

- [Explorar · 1440](browse-1440.png)
- [Filtros avanzados · 1440](filters-1440.png)
- [Búsqueda local · 1440](search-1440.png)
- [Vacío de búsqueda · 1440](empty-1440.png)
- [Explorar · 390](browse-390.png)
- [Filtros avanzados · 390](filters-390.png)
- [Búsqueda local · 390](search-390.png)
- [Vacío de búsqueda · 390](empty-390.png)

Las mediciones completas están en [metrics.json](metrics.json). La captura no usa datos
personales ni fuentes externas en vivo; contiene dos obras artificiales del fixture de
pruebas y valida 0 px de overflow horizontal.
