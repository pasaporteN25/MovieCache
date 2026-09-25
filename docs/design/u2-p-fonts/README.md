# Fuentes de comparación U2-P.2

TTF descargados el 2026-09-06. Sólo usados por `../u2-p-font-comparison.html`;
estos archivos no se incorporan al paquete de producción. La app usa WOFF2 oficiales
de la opción B en `src/movie_inbox/web/static/fonts/` (integración verificada 2026-09-07).

| Archivo | Fuente primaria | Peso ensayado |
| --- | --- | --- |
| `Oswald-Variable.ttf` | [Google Fonts / Oswald](https://github.com/google/fonts/tree/main/ofl/oswald) | 600; archivo variable 200–700 |
| `BarlowCondensed-SemiBold.ttf` | [Google Fonts / Barlow Condensed](https://github.com/google/fonts/tree/main/ofl/barlowcondensed) | 600 normal |
| `IBMPlexMono-Regular.ttf` | [Google Fonts / IBM Plex Mono](https://github.com/google/fonts/tree/main/ofl/ibmplexmono) | 400 normal |

Los originales se obtuvieron de `raw.githubusercontent.com/google/fonts/main/ofl/`
sin modificar sus bytes (Oswald sólo cambia el nombre del archivo local).
Cada licencia OFL 1.1 y su copyright se conservan completos al lado de la fuente.
Se permite redistribución e integración sujetas a esa licencia; no vender la fuente
por sí sola ni eliminar sus avisos. [Proyecto original IBM Plex](https://github.com/IBM/plex).

Decisión del usuario, 2026-09-06: **opción B, Barlow Condensed 600 en lomos y placas;
IBM Plex Mono 400 en consola y datos**. Integración WOFF2 local completada.
La decisión posterior de placas (2026-09-07, abajo) reemplaza sólo el rol de placas
por Oswald 400; esta comparación inicial permanece como registro histórico.
La lámina conserva la recomendación inicial A como registro, no como decisión vigente.
La muestra de marca permite discutir el alcance; no autoriza un cambio global.

La prueba carga tres TTF locales (417.096 bytes en total), sin CDN ni instalación
en Windows. Producción incluye cuatro WOFF2 oficiales latin/latin-ext sin modificación,
sólo de las familias/pesos elegidos, con licencias completas. Se comprobaron CSP,
fallback y carga local. Si se convierten/subconjuntan en el futuro, revisar las
condiciones de nombres reservados (Plex declara uno) y conservar los avisos.
No desplegar las alternativas descartadas ni usar pesos/cursivas sintéticos.

## Comparación de placas — 2026-09-07

La referencia nueva del usuario abre una excepción para la
tipografía de placas, sin cambiar Barlow en lomos ni Plex en datos. La lámina
`../u2-p34-visual-options.html` compara Oswald 400 con Bebas Neue 400.
Se añade `BebasNeue-Regular.ttf` oficial sin modificar y `bebasneue-OFL.txt`, desde
[Google Fonts](https://github.com/google/fonts/tree/main/ofl/bebasneue).
Decisión posterior: **Oswald 400 para placas y categorías**, Barlow 600 en lomos y
Plex 400 en datos. Los TTF de esta carpeta siguen siendo sólo material de estudio;
producción incorpora los WOFF2 latin/latin-ext oficiales de Oswald 400 sin conversión
en `src/movie_inbox/web/static/fonts/`, junto con su licencia completa.
Bebas Neue permanece descartada y no se distribuye con la aplicación.
