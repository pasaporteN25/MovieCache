# Night cinema ambient v1

| Campo | Valor |
| --- | --- |
| Archivo | `src/movie_inbox/web/static/img/night-cinema-ambient-v1.png` |
| Uso previsto | Fondo decorativo ultraancho de `Cartelera disponible` en U2.1; nunca representa una obra del catálogo. |
| Formato | PNG RGB, 2,048 × 768 px. |
| Integridad SHA-256 | `a4df22a54fa840258798e314683265eedd1fca4f2d8329627c06a2c2fb617af1` |
| Origen | Generado el 2026-09-02 con la herramienta integrada de generación de imágenes de OpenAI, sin imagen de entrada ni material de terceros aportado. |
| Licencia en el repositorio | GPL-3.0-only, como el proyecto. |

## Prompt de producción

```text
Wide panoramic ambient illustration, "empty midnight video-rental store" mood,
cinematic and nocturnal. Dark navy-to-near-black gradient base with soft glowing
accents in magenta/pink, cyan, and violet neon, plus a single warm gold highlight,
evoking a closed video club after hours — a hint of a distant marquee glow, soft bokeh
light dots, faint CRT scanline texture, subtle vignette toward the edges. Completely
abstract/atmospheric: no readable text, no logos, no brand marks, no recognizable actors
or people, no depiction of any specific film, no posters, no VHS boxes, no shelving, no
store signage, no owner or instance-specific content. Landscape orientation, roughly
2400×900px (ultra-wide banner), safe to crop on left/right. Center and top area should
stay visually calm/low-contrast so foreground UI text can sit on top of it. Style:
painterly digital art or soft 3D render, not photographic, not a screenshot.
```

El resultado debe permanecer como ambiente de fondo: el contenido que se superpone
continúa siendo HTML accesible, con contraste propio. No se debe recortar de modo que el
brillo dorado compita con títulos o controles centrales. Antes de reemplazarlo, generar
un nombre versionado, recalcular el hash y actualizar esta ficha; no sobrescribir un
asset publicado.
