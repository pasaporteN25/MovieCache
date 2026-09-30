# U10 — Colección: mostrador y portadas

Dirección aprobada el 2026-09-28 para `release/0.10.0`. Modo: Operate.
Estado: U10.1–U10.4 implementadas y verificadas; evidencia en
`../design/collection-counter-v1/README.md`.
Sustituye el selector Explorar/Buscar/Agregar de U3; conserva sus contratos de
comparación, vinculación y filtros enlazables.

## Dirección

Un mostrador del mismo videoclub de Inicio: petróleo, metal gastado, placas cálidas
y aberturas empotradas. Buscador siempre visible, filtros rápidos como botones,
orden junto al conteo y Agregar como acción independiente. Portadas de frente con
título y estados debajo, cinco columnas en escritorio y dos en móvil. La página
crece con Cargar más, sin sustituir las filas anteriores.

Referencia aprobada: `../design/collection-counter-v1/concept.png`. La imagen
contiene datos ilustrativos; producción usa exclusivamente el catálogo real.
Se compacta la placa del título y se mantienen botones de filtro, en lugar de los
desplegables ilustrados. No se añade selector de tamaño en este corte.

## Tareas y dependencias

- **U10.1 — Unificar navegación.** HTML, catalog-grid/search y router: entrada única,
  Agregar conserva consulta, volver restaura filtros/orden/posición, enlaces antiguos
  `mode=search` compatibles. Comparar/vincular conservan ancla. Sin dependencias.
- **U10.2 — Mostrador.** CSS acotado a Colección, materiales/fuentes existentes de
  Inicio, controles legibles, orden expuesto y acabado del flujo Agregar. Depende de U10.1.
- **U10.3 — Portadas y carga.** Presentación propia de Colección, portadas sin títulos
  superpuestos, estados reales, bloques de 30 y carga progresiva de imágenes.
  Historial conserva cantidad visible. Depende de U10.1/2.
- **U10.4 — Verificación y cierre.** Pruebas de búsqueda+filtros, limpiar, agregar y
  volver, enlaces antiguos, comparación/vinculación, carga e historial; revisión
  visual en 1920/1440/1280/390/320, teclado y movimiento reducido. Documentar evidencia.

## Límites y aceptación

No cambiar matching, fuentes externas, permisos, datos ni la Home. Se reutiliza el
kit material sin convertir la captura generada en fondo de la aplicación. Portada
ausente o fallida, título largo, catálogo vacío, cero resultados, carga y errores
deben conservar controles utilizables. Los filtros locales nunca aparentan filtrar
las fuentes externas. No hay publicación ni despliegue dentro de esta entrega.
