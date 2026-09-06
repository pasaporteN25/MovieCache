# U2-R.7a: gate visual desktop

Fecha: 2026-09-06. Estado: **gate abierto; dos hallazgos P1**.

## Alcance y método

Se comparó la home implementada con `u2-recovery-north-star-v1.png` y con la revisión
vinculante `u2-r4-annotated-review-v1.png`. La prueba usó un catálogo sintético de 24
obras, seis funciones y cuatro categorías de seis lomos; no se leyó ningún catálogo
personal. Se capturaron el primer viewport y el final del flujo en 1280×720, 1440×900 y
1920×1080.

Evidencia:

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

## Audit Health Score preliminar

Este score fotografía el arranque de R.7. Accesibilidad e interacción se vuelven a medir
en R.7c y el resultado definitivo pertenece a R.7d.

| # | Dimensión | Score | Hallazgo principal |
| --- | --- | --- | --- |
| 1 | Accesibilidad | 2/4 | Texto operativo visible de 8–10 px. |
| 2 | Performance | 3/4 | Posters lazy y estructura estable; falta profiling del gate final. |
| 3 | Responsive | 3/4 | Sin overflow horizontal; la escena completa no entra en 1080p. |
| 4 | Theming | 3/4 | Lenguaje coherente, con colores materiales aún fuera de tokens documentados. |
| 5 | Integridad de implementación | 4/4 | Sistema propio y consistente con las referencias. |
| **Total** |  | **15/20 — Bueno** | **Corregir los dos P1 antes del cierre.** |

## Mediciones

| Métrica | 1280×720 | 1440×900 | 1920×1080 |
| --- | ---: | ---: | ---: |
| Alto de página | 1050 px | 1128 px | 1282 px |
| Flujo vertical requerido | 330 px | 228 px | 202 px |
| Alto cabecera | 60 px | 64 px | 64 px |
| Alto cartelera/lista | 260 px | 306 px | 400 px |
| Alto mueble | 640 px | 640 px | 700 px |
| Filas reales | 6 | 6 | 6 |
| Ancho visible del recorrido | 1129 px | 1275 px | 1488 px |
| Ancho total del recorrido | 1831 px | 1952 px | 2380 px |
| Categorías parcialmente visibles | 3 de 4 | 3 de 4 | 3 de 4 |
| Overflow horizontal de página | 0 px | 0 px | 0 px |

Tipografía visible relevante:

| Elemento | 1280 | 1440 | 1920 |
| --- | ---: | ---: | ---: |
| Estadísticas de instancia | 8 px | 8 px | 8 px |
| Encabezado de playlist | 8 px | 8 px | 8 px |
| Celdas de playlist | 10 px | 10 px | 10 px |
| Título de lomo | 11 px | 11 px | 11 px |
| Metadata de lomo | 8,32 px | 9,36 px | 10 px |
| Sinopsis de consola | 12 px | 12 px | 12 px |
| Acción inferior | 12 px | 12 px | 13 px |

El detector de `impeccable` sobre HTML y CSS de Inicio reportó 25 avisos de escala
tipográfica; entre ellos están los tamaños de 6–9 px que el test de tokens también
detecta. Los avisos de colores literales se revisaron como deuda de tokens, no como una
ruptura automática: varios modelan el metal, CRT y desgaste específicos del brief.

## Hallazgos priorizados

### [P1] La escena completa no entra en el viewport de mayor resolución

- **Categoría:** Responsive / fidelidad visual.
- **Impacto:** incluso a 1920×1080 el usuario no puede leer en un mismo encuadre la
  relación cartelera → estantería → consola que sí presenta el north star; debe recorrer
  202 px para descubrir la franja de acciones y detalle.
- **Evidencia:** los tres pares de capturas y la tabla de flujo vertical.
- **Recomendación:** crear un modo desktop compacto gobernado por altura que reduzca
  espacio estructural antes que texto o contenido. Mantener el flujo vertical aceptado
  en 720p, pero recuperar la escena completa en 1080p.
- **Comando sugerido:** `$impeccable layout`.

### [P1] Microtexto operativo fuera de la escala documentada

- **Categoría:** Accesibilidad / tipografía / integridad.
- **Impacto:** estadísticas, encabezados y metadata pierden reconocimiento para baja
  visión y en pantallas de densidad alta. La falla no es cosmética: son datos que
  distinguen funciones, disponibilidad y procedencia.
- **Evidencia:** tamaños computados de 8–10 px y el gate rojo de
  `DesignTokenTests.test_minimum_label_size_and_high_contrast_fallback_are_present`.
- **Recomendación:** consolidar el piso visible en la rampa documentada, dando espacio a
  las columnas o reduciendo información secundaria antes de reducir texto.
- **Comando sugerido:** `$impeccable typeset`.

### [P2] Un nombre de instancia largo pierde su final en desktop

- **Categoría:** Responsive / identidad.
- **Impacto:** `Movie Inbox Browser Test` aparece como `MOVIE INBOX BROWS…`. El nombre
  accesible sigue completo y no rompe el layout, pero el owner pierde parte de su marca.
- **Recomendación:** verificar en R.7b si el título puede ceder espacio de forma gradual
  antes del ellipsis sin separar marca y estadísticas.
- **Comando sugerido:** `$impeccable harden`.

### [P2] La paleta material contiene tonos literales no documentados

- **Categoría:** Theming / integridad.
- **Impacto:** no altera la captura actual, pero dificulta mantener contraste y roles de
  señal al ajustar la escena.
- **Recomendación:** inventariar sólo los tonos realmente visibles de Inicio y promover
  los estables a tokens; no tokenizar automáticamente cada sombra del asset.
- **Comando sugerido:** `$impeccable document`.

## Hallazgos positivos

- Cabecera de 60–64 px en una línea y navegación agrupada como la revisión anotada.
- Cartelera sin caja exterior, poster completo 2:3, placa `Hoy` centrada y sin contador.
- Seis filas reales: ninguna tabla falsa ni hueco dominante.
- Cuatro categorías dentro de un único mueble; tres quedan total o parcialmente visibles
  y el cuarto exige overflow lateral real, con controles en ambos límites.
- Consola útil en los tres tamaños: sinopsis de dos líneas, hechos y acciones contenidos.
- Cero overflow horizontal de página en los tres viewports.

## Próximo corte

R.7a permanece abierto hasta corregir y recapturar los dos P1. Después se ejecuta R.7b;
el título de instancia largo viaja con esa matriz de contenido. El orden recomendado es:

1. **[P1] `$impeccable typeset`** — eliminar texto visible por debajo del piso acordado.
2. **[P1] `$impeccable layout`** — recuperar el encuadre completo en 1920×1080.
3. **[P2] `$impeccable harden`** — verificar nombre largo y datos extremos en R.7b.
4. **[Final] `$impeccable polish`** — repetir capturas y gate integral.

Se pueden ejecutar esos cortes de a uno, juntos o en otro orden. Después de las
correcciones debe repetirse `$impeccable audit` para comprobar el cambio de score.
