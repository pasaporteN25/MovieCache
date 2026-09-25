# U5.3.3–4 — listas extensas y evidencia visual

Actualización: U5.3.4/U6.5 cerradas por aceptación manual del owner el 2026-09-14;
capturas y límites en `../u5-u6-owner-acceptance/`. Lo siguiente conserva el registro
de la prueba automatizada anterior, cuya limitación de zoom no se reescribe.

2026-09-14. U5.3.3 implementada. U5.3.4 parcialmente verificada: escritorio,
reflow, extremos de lista y foco aprobados en el navegador conectado; falta zoom
real 200%. No cierra U5.4–5 ni el runner histórico U4.6b.

## Implementación

- Más de seis obras: ventana de scroll local de 266 px como mínimo, ampliada en
  escritorio ancho según el espacio de cartelera. No crece con cada fila adicional.
- Seis obras o menos: se conserva el display habitual, sin introducir scroll vertical.
- Encabezados de columnas fijos; fila seleccionada alineada por debajo del encabezado,
  incluyendo Inicio/Fin. Foco cyan y selección magenta se conservan.
- Autoplay conserva el scroll de la fuente actual; cambiar de fuente reinicia el
  contenedor. Redimensionar mantiene visible una fila/lomo que tenga el foco, sin
  cambiar obra ni reenfocar controles.
- Materiales, dimensiones de VHS, tipografía y retícula B preservados con Impeccable.
  No se generaron assets ni se modificó el límite editorial de seis obras del servidor.

## Reproducción segura

Ejecutar `.venv/Scripts/python.exe scripts/serve_u4_2c_review.py` y abrir la URL que
imprime. El servidor usa catálogo y cuenta descartables. La sesión de esta prueba
usó `http://127.0.0.1:56503/`. Los enlaces 1/6/20/100 obras cambian sólo el payload
de demostración de ese proceso; elegir su placa para programar la tabla.
Las obras de escala tienen IDs sintéticos: sirven para lista/consulta, no para ensayar
guardado de metadata. El catálogo real del usuario no fue usado ni alterado.

## Mediciones

`matrix.json`: 1/6/20/100 obras × 1280×720, 1440×900, 1920×1080, 390×844 y 320×740.
`empty-matrix.json`: estado vacío en esos cinco tamaños. Probe reutilizable:
`tests/browser/home_list_metrics.js`.

- Sin overflow horizontal del documento en los 25 casos (−15 px por scrollbar).
- 1/6 obras sin scroll local; 20/100 con scroll dentro de la tabla.
- Fila final visible bajo el encabezado y sin superposición con consola en las
  20 mediciones con datos. Dos carteleras de igual ancho y una consola.
- 20→100 obras: misma altura de documento en 1440 y 1920; en 1280 aumenta 15 px
  por el salto de línea de la cabecera al mostrar tres dígitos, no por las 80 filas.
- `keyboard.json`: teclas nativas Inicio/Fin, fila 1→100, `scrollY = 21` constante;
  sólo el contenedor cambia de 0 a 3572 px. Se distinguió este ensayo de los cambios
  de scroll producidos por el autoenfoque del instrumento al usar locators.
- `reflow-720.json`: tras reducir de 1920 a 720, la fila 100 conserva foco y vuelve
  a estar completamente visible. El primer ensayo detectó esa pérdida de visibilidad;
  se corrigió con `handleHomeResize()` y se verificó nuevamente.
- Capturas revisadas: `100-end-1280.png`, `100-end-1440.png`, `100-end-1920.png`.
  Son capturas de viewport; a 720 px de alto parte de la consola queda debajo del
  pliegue y se accede por scroll normal. No se achicó la Home para hacerla caber entera.

## Límite del zoom

Se intentó el atajo de ampliación del navegador, pero el entorno integrado no lo
aplicó: viewport y devicePixelRatio quedaron en 1440 y 1. Sólo expone control de
viewport/visibilidad. 720×450 comprueba el reflow equivalente a 1440×900 / 200%,
**no** la ampliación real de texto/imágenes. No se declara el zoom 200% aprobado.

Para cerrar ese punto: en un navegador con zoom real, usar 1440×900 al 200%, seleccionar
el estante de 100 obras, recorrer Inicio/Fin, volver a programación y comprobar foco,
texto/acciones accesibles y ausencia de overflow de documento. Restaurar zoom al 100%.
La revisión móvil profunda sigue en MW1.

## Pruebas

23 tests JS (`home-selection.test.mjs` + `home-images.test.mjs`) aprobados; incluye
sticky header, scroll por fuente y redimensionado. 17 tests Python de Home/empaquetado
aprobados. Sintaxis JS/Python y `git diff --check` correctos. Detector Impeccable de
layout sobre `home-inset.css`: sin hallazgos. No se ejecutó la suite histórica completa
de navegador ni se acredita una revisión independiente que no se realizó.

Sin commit, push, merge ni cambio de versión. U8 no se inició.
