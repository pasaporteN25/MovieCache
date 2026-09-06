# U2-R.7a: gate visual desktop

Fecha: 2026-09-06. Estado: **gate cerrado; sin hallazgos P1 abiertos**.

## Alcance y método

Se comparó la home implementada con `u2-recovery-north-star-v1.png` y con la revisión
vinculante `u2-r4-annotated-review-v1.png`. La prueba usó un catálogo sintético de 24
obras, seis funciones y cuatro categorías de seis lomos; no se leyó ningún catálogo
personal. Se capturaron el primer viewport y el final del flujo en 1280×720, 1440×900 y
1920×1080.

La corrección aplicó la decisión **1A + 2A**: compactación selectiva gobernada por altura
y piso tipográfico según función. El mueble conserva 640 px y la consola aprobada en
U2-R.C3; el espacio se recupera en la franja superior y en el ritmo entre secciones.

Evidencia final:

| Viewport | Primer encuadre | Franja inferior |
| --- | --- | --- |
| 1280×720 | [superior](u2-r7a-evidence/1280x720-top.jpg) | [inferior](u2-r7a-evidence/1280x720-lower.jpg) |
| 1440×900 | [superior](u2-r7a-evidence/1440x900-top.jpg) | [inferior](u2-r7a-evidence/1440x900-lower.jpg) |
| 1920×1080 | [superior](u2-r7a-evidence/1920x1080-top.jpg) | [inferior](u2-r7a-evidence/1920x1080-lower.jpg) |

## Veredicto de integridad

**Pasa.** La implementación expresa una videoteca nocturna específica: cartelera 2:3,
playlist CRT, lomos HTML dentro de un único mueble, consola retrofuturista y acciones
físicas doradas. No volvió al hero genérico ni a filas de cards. El DOM conserva títulos,
metadata, estados y controles reales; los assets sólo aportan materialidad.

La lectura principal **cartelera → estantería → consola** entra completa en 1920×1080.
En 1440×900 el recorrido bajó de 228 a 154 px. En 1280×720 conserva flujo vertical para
no volver a comprimir ni ocultar el contenido inferior aceptado en U2-R.C3.

## Audit Health Score de R7a

Accesibilidad e interacción se vuelven a medir de forma integral en R.7c y el resultado
definitivo pertenece a R.7d.

| # | Dimensión | Score | Evidencia principal |
| --- | --- | --- | --- |
| 1 | Accesibilidad | 3/4 | Piso visible corregido; resta el recorrido asistivo de R.7c. |
| 2 | Performance | 3/4 | Posters lazy y estructura estable; falta profiling final. |
| 3 | Responsive | 4/4 | Sin overflow horizontal y escena completa en 1080p. |
| 4 | Theming | 3/4 | Lenguaje coherente; quedan colores materiales por documentar. |
| 5 | Integridad de implementación | 4/4 | Sistema propio y consistente con las referencias. |
| **Total** |  | **17/20 — Muy bueno** | **R7a puede cerrar.** |

## Mediciones finales

| Métrica | 1280×720 | 1440×900 | 1920×1080 |
| --- | ---: | ---: | ---: |
| Alto de página | 1050 px | 1054 px | 1080 px |
| Flujo vertical requerido | 330 px | 154 px | 0 px |
| Alto cabecera | 60 px | 60 px | 60 px |
| Alto cartelera/lista | 276 px | 274 px | 300 px |
| Alto mueble | 640 px | 640 px | 640 px |
| Filas reales | 6 | 6 | 6 |
| Overflow horizontal de página | 0 px | 0 px | 0 px |

Tipografía visible relevante:

| Elemento | 1280 | 1440 | 1920 |
| --- | ---: | ---: | ---: |
| Estadísticas de instancia | 12 px | 12 px | 12 px |
| Encabezado de playlist | 11 px | 11 px | 11 px |
| Celdas de playlist | 12 px | 12 px | 12 px |
| Título de lomo | 11 px | 11 px | 11 px |
| Metadata de lomo | 10 px | 10 px | 10 px |
| Sinopsis de consola | 12 px | 12 px | 12 px |
| Acción inferior | 12 px | 12 px | 13 px |

La columna de hechos de la preview recibió ancho desde el osciloscopio decorativo. Una
regresión de navegador comprueba que su contenido no desborde en ninguno de los tres
viewports.

## Hallazgos resueltos

### [Resuelto P1] Encuadre completo en el viewport mayor

- 1920×1080 pasó de 202 px de recorrido vertical a 0 px.
- El mueble no se redujo por debajo de 640 px y su consola conserva al menos 112 px.
- 720p mantiene flujo vertical explícito, sin ocultación ni compresión de texto.

### [Resuelto P1] Microtexto operativo dentro de la escala acordada

- Estadísticas, celdas, acciones y sinopsis operativas usan 12 px.
- Encabezados tabulares usan 11 px; etiquetas secundarias y metadata de lomo, 10 px.
- `DesignTokenTests.test_minimum_label_size_and_high_contrast_fallback_are_present`
  queda verde y la hoja efectiva ya no contiene declaraciones de `font-size: 8px/9px`.

## Hallazgos P2 que siguen su propio corte

### Un nombre de instancia largo pierde su final en desktop

`Movie Inbox Browser Test` conserva nombre accesible completo, pero todavía usa ellipsis
visual. R.7b verificará si puede ceder espacio gradualmente sin separar marca y
estadísticas ni agrandar la cabecera.

### La paleta material contiene tonos literales no documentados

No altera el gate visual actual. R.7d inventariará sólo los tonos estables y visibles;
no se tokenizará automáticamente cada sombra o desgaste de los assets.

## Verificación

- `DesignTokenTests`: 2/2.
- Regresiones focales de cartelera y consola: 2/2.
- Detector `layout` de `impeccable`: 0 hallazgos.
- Detector `type`: 14 avisos consultivos por clamps y tamaños display históricos fuera
  de la rampa documental; ninguno corresponde ya a texto visible de 6–9 px ni bloquea
  este gate. Su normalización global, si aporta valor, pertenece al cierre R.7d.
- Revisión visual final de las seis capturas: sin recortes operativos, sin overflow
  horizontal y con la composición completa visible en 1080p.

## Próximo corte

Continúa **U2-R.7b**, matriz de contenido y estados límite: 0/1/4 categorías, filas
vacías, poster roto, títulos y géneros extensos, permisos personal/Club y contratapa con
sus dos placeholders.
