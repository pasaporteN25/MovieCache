# Gate de la franja superior U2-R.4

Fecha: 2026-09-03. Referencia vinculante:
`docs/design/u2-r4-annotated-review-v1.png`.

## Dirección elegida

Se compararon tres tratamientos acotados para el mostrador:

1. Conservar el contenedor rectangular anterior: rechazado porque repetía la lógica de
   panel y restaba continuidad a la escena.
2. Marquesina abierta y corrida: elegida. Barras de neón, marca, separador,
   estadísticas y un riel fino forman una sola línea; `Colección` y `Menú` terminan el
   mostrador como dos placas físicas contiguas.
3. Cartel corpóreo alto: rechazado porque aumentaba la altura y competía con la
   cartelera.

La variante elegida conserva la semántica y los handlers existentes, aplica sólo en
desktop y trunca nombres de instancia excepcionalmente largos antes de forzar una
segunda línea.

## Correcciones verificadas

- La cartelera ya no tiene panel exterior, crece dentro de una columna más contenida y
  conserva el poster completo con `object-fit: contain`.
- La placa muestra sólo `Hoy` o `Ayer`, centrado, sin contador ni caption redundante.
- El reproductor muestra hasta seis filas ocupando la altura disponible. La regla de
  expansión se activa sólo con 4–6 filas; con 1–3 se conserva una altura de fila
  compacta.
- La preview mantiene las acciones a la izquierda, elimina `Disponible y pendiente` y
  aloja una señal SVG decorativa. La señal es `aria-hidden`, varía con el ID de obra y
  no cambia al rerenderizar la misma obra.
- La mitad inferior conserva la implementación de U2-R.3/R.4; sólo reduce altura entre
  801 y 960 px para mantener el encuadre completo.

## Capturas y matriz de aceptación

Se generaron y revisaron capturas de navegador a zoom 100 % durante el gate. Las
capturas transitorias no se versionan porque usan datos y posters sintéticos del test;
los invariantes geométricos quedan fijados en `tests/browser/test_ui_browser.py`.

| Viewport | Resultado | Observaciones |
| --- | --- | --- |
| 1280×720 | Aprobado | Sin scroll vertical; header menor a 70 px; seis filas legibles. |
| 1440×900 | Aprobado | Mueble y preview inferior entran completos tras compactación intermedia. |
| 1920×1080 | Aprobado | La franja superior mantiene densidad y la señal usa el espacio central. |

También se cubren poster completo, selector sin contador, ausencia del panel exterior,
placa dinámica `Hoy`/`Ayer`, controles contiguos, lista corta sin filas gigantes,
estabilidad/variación de la señal y preservación de la navegación móvil a 390×844.

## Próximo corte

U2-R.5 puede construir la contratapa determinista sobre este contrato. U2-R.7 seguirá
siendo el gate integral del mueble, la contratapa, móvil, zoom y accesibilidad antes de
cerrar toda la recuperación U2-R.
