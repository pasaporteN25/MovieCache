# Retoque visual de VHS — 2026-09-29

Alcance autorizado: cambios visuales de la planificación, sin merge de release.

- Zoom proporcional de 4,5% con elevación de 4 px; la grilla permanece estable.
- Imagen completa en contain. Cinta sobre portada real inactiva; fallback con cinta.
- Datos sólo debajo de la sinopsis, con separación entre etiqueta y valor.
- Imagen a un tercio, datos/créditos a dos tercios; móvil apilado. Las cinco identidades
  de contratapa comparten composición. Créditos sin datos ocupan una sola nota.
- Sinopsis al 96% del tamaño anterior, mínimo de 11 px.

## Pendiente de interacción

No hay todavía clamp ni Leer más/menos. El texto completo y el scroll se conservan
para no perder información. La ficha de ejemplo cabe sin scroll a 1440×1000;
contenidos largos y móvil todavía necesitan desplazamiento. No es el gate final de release.

## Evidencia

Capturas del navegador con catálogo temporal y datos de prueba:
`back-cover-1440.png`, `back-cover-390.png`, `back-cover-320.png`,
`case-artwork-focus.png`, `cases-with-artwork.png`, `case-focus.png`,
`collection-desktop.png`. Metropolis usa la imagen de prueba ya existente en el repo.

La cinta opcional sigue definida en `core/card.js` y `css/vhs-experience.css`.
No tiene activador de hover/foco; la cinta principal del placeholder sigue vigente.

## Verificación

Seis pruebas de navegador: cuatro de caja/editor más imagen/plantillas y apertura
animada desde Inicio. Incluyen cinco plantillas con 0/1/2 imágenes, fallos y respuestas
tardías; proporción antes/después del zoom, teclado, guardado, regreso y responsive.
Ruff, formato, mypy y suite JS complementan esta revisión.
El detector informa colores/radios heredados de los materiales aprobados; no se
introdujeron colores nuevos. El sidecar de Impeccable está desactualizado respecto a
DESIGN.md, y su regeneración queda fuera del retoque.

Resultado: 6 pruebas de navegador y 34 JS pasaron. Ruff, formato, mypy y diff-check correctos. Revisión independiente de Impeccable sin defectos bloqueantes en el alcance visual.
