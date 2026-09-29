# Preparación de release/0.10.0

Estado al 2026-09-29: abierta. Subir avances a esta rama; no fusionar todavía.
Se conserva la versión `0.10.0.dev0` y el changelog en «Sin publicar» hasta el cierre.

## Trabajo ya guardado

- U10: Colección unificada y mostrador, `87e3b04`.
- U11: cajas, sticker, assets y editor por tareas, `31660c2`.
- U9: muestras de sacar/abrir VHS y secuencia completa. Material de exploración;
  no hay elección sonora aprobada ni integración de audio en la aplicación.

La entrega U11 validó 68 pruebas de navegador, 80 HTTP/paquete y 34 JS (182),
además de Ruff y mypy sobre los cambios. Eso no sustituye el gate final de release.

## Retoques pendientes — planificados, sin implementar

- Acercamiento proporcional pequeño de la caja, sin cambiar sólo la altura.
- Desactivar la cinta adicional cuando existe portada, conservando y documentando
  la variante reutilizable. Mantener la cinta principal del fallback.
- Contratapa inicialmente compacta: comparar 5/6 líneas de sinopsis y ofrecer
  «Leer más/menos» sólo cuando haga falta. Scroll al expandir si el contenido lo exige.
- Quitar año/duración/géneros repetidos debajo del título; redistribuir datos y
  créditos para evitar el hueco del bloque que ocupa dos filas. Revisar las cinco
  plantillas, contenido largo, imágenes ausentes y anchos pequeños.
- Decisión aún abierta: mantener visibles los datos inferiores durante el acercamiento
  de la caja. Fue recomendado, pero no se toma como confirmado.

El fondo fotográfico del editor continúa diferido por el owner; no implementarlo
automáticamente al preparar la rama. No mezclar la integración de sonido con los retoques.

## Antes del merge

- [ ] Completar y revisar los retoques acordados.
- [ ] Actualizar changelog y evidencia conforme al resultado final.
- [ ] Ejecutar el gate completo de [release-checklist.md](release-checklist.md):
  lint, formato, mypy, compilación, suite, navegador, wheel y aceptación descartable.
- [ ] Confirmar CI del último commit y estado del PR contra `master`.
- [ ] Cerrar versión/changelog siguiendo la sección 8 del checklist.
- [ ] Fusionar sólo después de que el owner dé por terminados los retoques.

Esta preparación no es un merge ni un despliegue.
