# Colección: buscar, filtrar y recuperarse sin ruido

Estado: exploración solicitada por el owner el 2026-10-04; ninguna opción está elegida.
Modo: Operate. Alcance: controles del mostrador y estado sin resultados; conservar
las cajas, materiales de videoclub, fuentes, matching y el historial enlazable.

## Problema

La consulta, ocho teclas de filtros, dos checkboxes, chips, orden y cuatro acciones
de recuperación compiten con el mismo peso. El vacío separa botones y explicación;
«Buscar para agregar» hace poco claro si buscar incorpora una obra automáticamente.

## Opciones comparables

La [maqueta interactiva](../design/collection-controls-v1/index.html) permite comparar:

- **Mostrador compacto:** consulta dominante; estado/disponibilidad/tipo como tres
  selectores, filtros adicionales desplegables y orden junto al conteo. Recomendada
  para búsqueda frecuente: deja espacio a obras y resultados sin perder filtros.
- **Mesa de consulta:** conserva filtros rápidos visibles, pero con grupos separados,
  teclas segmentadas y controles secundarios agrupados. Menos cambio de hábitos;
  ocupa más alto en el teléfono.
- **Archivo con panel lateral:** filtros a la izquierda, consulta/resultados a la
  derecha. Conveniente para explorar por varias facetas; en móvil el panel se pliega.

Todas muestran alcance de búsqueda explícito («Mi colección» / «También en fuentes»),
limpieza en la consulta, chips sólo cuando existen y un vacío con una acción principal:
«Buscar en fuentes». Buscar nunca agrega sin confirmación. Director es un modo de
consulta, separado de disponibilidad; actores requieren una especificación futura.

## Criterios para implementar la opción elegida

- Consulta, filtros, orden, URL e historial representan el mismo estado.
- Filtros de facetas distintas se intersectan; varios de una misma se unen.
- Con cero resultados, explicar si el alcance es local y ofrecer ampliar o quitar
  filtros; no declarar que una obra no existe.
- Conservar títulos completos, estados de fuentes, carga, cancelación y duplicados.
- Usable con teclado, foco visible, nombres accesibles y sin overflow a 320/390 px.
- Usar las fuentes locales y colores de Colección. No crear un nuevo tema global.
- Elegir una composición con el owner antes de cambiar los controles productivos.

Las cifras y búsquedas de la maqueta son ilustrativas. No usa el catálogo real,
no consulta proveedores y no escribe obras.
