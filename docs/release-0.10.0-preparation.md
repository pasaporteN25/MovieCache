# Preparación de release/0.10.0

Estado al 2026-09-29: el PR [#2](https://github.com/pasaporteN25/MovieCache/pull/2)
se fusionó en `c28745c` con `0.10.0.dev0`. El owner informó que completó la
aceptación manual. El cierre de versión estable se hace en un merge adicional para
preservar la regla de no commitear directamente en `master`.

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

## Cierre de versión

- [x] Completar y revisar los retoques acordados.
- [x] Actualizar changelog y evidencia conforme al resultado final.
- [x] Validación automática local de [release-checklist.md](release-checklist.md):
  Ruff, formato, mypy estricto (246 archivos), compilación y `git diff --check`;
  1126 pruebas Python correctas (9 omitidas), 73 de navegador y 34 JS. Wheel
  `0.10.0.dev0` construido e instalado en un entorno limpio con assets verificados.
  La suite detectó un test dependiente de la resolución del reloj de Windows;
  las notas de rate limit usan ahora un cursor secuencial y el gate volvió a pasar.
- [x] Confirmar CI del último commit del PR #2: siete jobs en verde.
- [x] Aceptación manual informada por el owner el 2026-09-29. No se adjuntó a este
  checkout un registro de pasos, backup o restauración; no se afirma evidencia técnica
  que no esté disponible aquí.
- [ ] Integrar el cierre de `0.10.0` en `master` mediante merge commit y verificar CI.
- [ ] Crear y subir el tag anotado `v0.10.0` sobre ese merge commit.
- [ ] Publicar el GitHub Release de `v0.10.0`.

Este documento registra el cierre; no representa un despliegue.
