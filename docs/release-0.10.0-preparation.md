# Preparación de release/0.10.0

Estado al 2026-09-29: abierta. PR [#2](https://github.com/pasaporteN25/MovieCache/pull/2)
contra `master`. El owner pidió dejarlo listo para revisar, sin fusionarlo todavía.
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

## Interacción completada

- Sinopsis de seis líneas con «Leer más/menos» sólo cuando desborda; expandir conserva
  el texto completo y permite scroll, colapsar conserva el foco visible y cada obra
  abre compacta. Evidencia en [vhs-synopsis-v1](design/vhs-synopsis-v1/README.md).
- En móvil puede seguir habiendo scroll inicial por el espacio físico de la caja; no
  se ocultan datos de la obra para evitarlo.

El fondo fotográfico del editor continúa diferido por el owner; no implementarlo
automáticamente al preparar la rama. No mezclar la integración de sonido con los retoques.

## Antes del merge

- [x] Completar y revisar los retoques acordados.
- [x] Actualizar changelog y evidencia conforme al resultado final.
- [x] Validación automática local de [release-checklist.md](release-checklist.md):
  Ruff, formato, mypy estricto (246 archivos), compilación y `git diff --check`;
  1126 pruebas Python correctas (9 omitidas), 73 de navegador y 34 JS. Wheel
  `0.10.0.dev0` construido e instalado en un entorno limpio con assets verificados.
  La suite detectó un test dependiente de la resolución del reloj de Windows;
  las notas de rate limit usan ahora un cursor secuencial y el gate volvió a pasar.
- [ ] Confirmar CI del último commit y estado del PR contra `master`.
- [ ] Cerrar versión/changelog siguiendo la sección 8 del checklist.
- [ ] Aceptación manual sobre biblioteca descartable y backup/restauración Docker:
  pendiente; este equipo no tiene Docker ni hay servidor de pruebas disponible.
- [ ] Fusionar después de completar la aceptación y revisar el PR.

Esta preparación no es un merge ni un despliegue.
