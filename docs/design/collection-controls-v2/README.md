# Colección: panel de filtros

Prototipo propuesto el 2026-10-04 a pedido del owner, después de descartar las
tres composiciones de v1. Modo Operate; conserva la identidad petróleo y latón.

- Panel derecho superpuesto, sin cambiar las dimensiones de la colección.
- En móvil ocupa la pantalla, con confirmación siempre visible.
- Selección en borrador: sólo Mostrar obras aplica. Cancelar, cerrar y Escape
  conservan los filtros anteriores; Restablecer selección sólo limpia el borrador.
- Vista principal con búsqueda, botón de filtros con cantidad y orden.
- Filtros aplicados visibles y removibles debajo de la barra.

Datos sintéticos. No consume el catálogo ni proveedores ni modifica la app.
La lista representa el contexto de uso; este prototipo no propone reemplazar
las tarjetas o la vista de colección actual. Aprobado por el owner e implementado el 2026-10-04.

`verify.py` comprobó a 1440 y 390 px: sin desborde ni cambio de dimensiones al abrir,
selección sin aplicar, cancelación, aplicación, reset del borrador, Escape y chips.
Las capturas muestran la vista inicial, el panel y la selección aplicada.

`implemented-*.png` y `implemented-panel-*.png` muestran la app real con VHS
y un catálogo sintético, a 1440 y 390 px.
