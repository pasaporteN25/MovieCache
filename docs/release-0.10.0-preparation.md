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

## Retoque visual implementado — 2026-09-29

- Acercamiento proporcional del 4,5%, elevación de 4 px y datos inferiores visibles.
- Cinta adicional sobre portadas reales inactiva, con código conservado y documentado.
- Datos sin duplicar, junto a créditos compactos e imagen completa; las cinco variantes
  comparten disposición adaptable. Sinopsis apenas menor, sin bajar de 11 px.
- Evidencia y alcance en [vhs-refinement-v2](design/vhs-refinement-v2/README.md).

## Interacción pendiente

- Sinopsis de 5/6 líneas con «Leer más/menos» sólo cuando desborda; expandir y permitir
  scroll según necesidad, colapsar sin perder foco y reiniciar al cambiar de obra.
- Hasta entonces no se oculta texto: las fichas largas y móviles siguen permitiendo
  scroll. Esta entrega visual no completa el objetivo de evitar scroll inicial.

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
