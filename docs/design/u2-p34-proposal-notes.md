# U2-P.3 / P.4 — Altura, volumen y placas · 2026-09-07

Estado: **estudio histórico; el usuario eligió Oswald 400 + lomo B**. La integración
posterior vive en `home-type.css`, `home-spines.css` y `home-plaques.css`; la app no
importa el CSS de esta propuesta ni sus TTF. Evidencia actual en `u2-p4-evidence/`.
Las alternativas siguientes conservan el registro de lo mostrado antes de elegir.

## Pedido e interpretación

- [Referencia de placa](u2-p-plaque-reference-2026-09-07.png): metal ennegrecido,
  doble marco fino de latón envejecido, cuatro tornillos discretos y letra dorada
  alta/estrecha con espaciado. Texto real superpuesto, no nombres rasterizados.
- [Anotación del mueble](u2-p-height-annotated-2026-09-07.png): las flechas se
  interpretan como subir cada rótulo al travesaño superior. La altura libre resultante
  se incorpora al lomo hacia arriba, conservando ancho y apoyo inferior.
- Se conservan Barlow Condensed en los lomos e IBM Plex Mono en datos. Se propone
  una excepción para las placas, no un reemplazo global de la opción B de P.2.

## Alternativas mostradas

[Lámina navegable](u2-p34-visual-options.html).

- **Bebas Neue 400:** recomendación para placa, por su proporción alta/estrecha.
- **Oswald 400:** alternativa más abierta. La fuente exacta de la imagen de
  referencia no se ha identificado; ambas son aproximaciones comparadas con el mismo texto.
- **Lomo A:** asset original, más alto; no cambia la tipografía ni el ancho.
- **Lomo B:** misma geometría y raster de A, canto interior oscuro de 5 px,
  línea de luz y sombra corta. Sin perspectiva ni inclinación del texto.

El material se ensaya con un fondo raster nuevo; CSS conserva sus esquinas con
border-image, sin editar los píxeles por script. No se rehízo el asset de VHS:
la prueba busca comprobar si altura y relieve alcanzan antes de reemplazarlo.

## Geometría comprobada

Capturas de catálogo temporal reproducibles con
`.venv/Scripts/python.exe scripts/capture_u2_p34_proposals.py`.
El script inyecta el CSS sólo en la página de prueba; sirve las fuentes y placa
mediante rutas interceptadas de Playwright, sin modificar la aplicación.

| Vista | Ancho antes/después | Alto antes | Alto propuesto A/B |
| --- | --- | --- | --- |
| 1440 px | 74,875 px | 237,953 px | 281,656 px |
| 1920 px | 84 px | 237,953 px | 281,656 px |

Aumento de 43,703 px (18,37 %). Base sin cambio en los 18 lomos: 400,969 px
para el seleccionado y 404,969 px para los demás, relativos al mueble.
72 comparaciones de ancho/base/altura correctas. No es una validación responsive
de producción ni equivale a aceptación visual. Capturas: [A](u2-p34-evidence/a-1440.png),
[B](u2-p34-evidence/b-1440.png), [antes](u2-p34-evidence/before-1440.png).

Revisión Impeccable: layout sin hallazgos; type advierte las dos familias de
propuesta y el tamaño de placa 19 px fuera de DESIGN.md. Es deliberado en este
estudio aislado y no autoriza modificar el sistema vigente antes de la elección.
Ruff correcto en el script. Se inspeccionaron las capturas, no sólo las métricas.

## Pendiente al elegir

- Confirmar fuente de placa y tratamiento A/B. Luego integrar y comprobar estados,
  foco, contraste, zoom, categorías muy largas y comportamiento móvil.
- Los rótulos largos necesitan una regla de anchura/quiebre por grupo. El último
  grupo parcialmente fuera del viewport se desplaza con su placa, como los lomos;
  no se debe confundir ese recorte del carril con elipsis del nombre.
- No alterar altura/ancho del mueble, consola ni poste derecho en esta decisión.
  Continuidad P.5 y consola P.6 siguen pendientes.
- El count sigue siendo dato real, no subtítulo editorial inventado.

## Fuentes y asset

- [Bebas Neue, repositorio del autor](https://github.com/dharmatype/Bebas-Neue),
  SIL OFL 1.1. Original de Google Fonts:
  `https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf`.
  Guardado sin modificar en `u2-p-fonts/BebasNeue-Regular.ttf`, licencia completa
  `u2-p-fonts/bebasneue-OFL.txt`. No se carga en producción.
- [Oswald / licencia](https://github.com/google/fonts/blob/main/ofl/oswald/OFL.txt):
  se reutiliza el TTF variable y OFL ya archivados en `u2-p-fonts/`.
- `u2-p-plaque-blank-v1.png`: propuesta generada con el **Imagegen integrado**,
  editando la referencia de placa. Archivo original preservado. No sustituye
  ninguno de los assets actuales. El generador entregó una proporción más alta
  que la pedida; se adapta con nueve zonas CSS, preservando esquinas.

Prompt utilizado:

> Use case: precise-object-edit. Edit target: attached narrow vintage metal plaque.
> Create a reusable blank UI plaque asset by removing ALL lettering from the black
> center only. Keep the exact front-facing long rectangular silhouette, proportions
> about 4.8:1, very thin double aged brass border, four tiny inset corner screws,
> dark blackened-metal center, subdued gold patina and small worn scratches of the
> original. No redesign, no extra decoration, no new objects. Fill the removed-letter
> area with the matching understated black metal surface; the center must be blank
> with absolutely NO letters, symbols or watermark. Preserve the existing framing
> as closely as possible; plaque fills canvas edge to edge, no extra background or
> margins. Output a higher-resolution version suitable for a CSS background, keep
> long horizontal aspect ratio.
