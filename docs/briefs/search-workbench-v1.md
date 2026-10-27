# U12 — Mesa de búsqueda y revisión de coincidencias

Dirección aprobada el 2026-10-01 para `release/0.11.0`. Modo: Operate.
Primera entrega de la actualización visual de búsqueda. Conserva la identidad del
mostrador U10: petróleo, metal discreto, tinta cálida y datos cyan. Una obra de una
fuente externa aún no es un VHS de la colección; se presenta como ficha de consulta.

## Trabajo y jerarquía

La persona busca, reconoce una obra externa, decide si añadirla o relacionarla con
su archivo y conserva claro qué fuente respondió. La cabecera y los filtros siguen
siendo los de Colección. Resultados externos, estados por fuente y comparación se
leen debajo como una tarea continua, sin carriles horizontales de tarjetas altas.

- Cada fuente conserva su encabezado, cantidad, estado de carga/error y reintento.
  Sus resultados son filas con miniatura 2:3, título, año/tipo, dato distintivo y
  descripción breve. La procedencia no se repite como chip y URL dentro de cada fila.
- Las acciones dicen qué hacen: agregar, comparar con la colección y abrir la fuente.
  Un resultado ya agregado comunica estado sin competir con una acción disponible.
- Una respuesta `possible_duplicate` abre una revisión integrada en la búsqueda.
  Muestra la obra solicitada y hasta cinco candidatas del archivo, con el motivo
  real de coincidencia. No se escribe nada antes de la elección humana.
- La ficha guardada se abre en Movie Inbox. El enlace a la fuente externa se rotula
  por separado. Comparar y combinar reutiliza el comparador detallado existente.
- «Seguir buscando» cierra la revisión y devuelve el foco al resultado sin
  consultar las fuentes otra vez. «Agregar como obra distinta» requiere una segunda
  acción explícita dentro de la revisión.

## Límites y estados

No cambiar el algoritmo de matching, los contratos de fuentes ni el significado de
disponibilidad. La grilla local conserva sus cajas VHS. Esta entrega cubre una fuente
con un único resultado, muchas filas, 0–5 candidatas, títulos largos, ausencia o fallo
de imagen, cargas parciales, errores/reintentos, teclado, móvil y movimiento reducido.
La ficha externa y la revisión deben permanecer legibles a 320 px sin scroll lateral.

## Entrega

1. Estructura y copia de filas externas; estilos acotados a Colección.
2. Revisión integrada de posibles duplicados, foco, salida y confirmación de obra
   distinta; sin recargar resultados al cancelar.
3. Pruebas de interacción y revisión visual de escritorio/móvil con datos
   descartables; documentación del corte en el backlog y changelog.

No incluye publicación de la v0.11.0 ni rediseño del comparador de campos.
