# Ficha: contexto público y guardado seguro

Implementación iniciada el 2026-09-19, validación completada el 2026-09-20.
Brief: `../../briefs/detail-public-context-v1.md`.

Capturas de la aplicación real con catálogo descartable y respuestas sintéticas de
puntajes/streaming. Los nombres de plataformas y cifras son datos de prueba; no son
una consulta de disponibilidad real. Ningún catálogo personal se usó como fixture.

- `desktop.png`: dossier a 1280 × 900; iconos de biblioteca/streaming, estado y registro.
- `desktop-context.png`: puntajes y ofertas, con atribuciones y selector de país.
- `mobile-390.png` y `mobile-320.png`: reflow del contexto sin overflow horizontal.

La inspección visual detectó que la carcasa VHS invadía el estado personal. Se
reservaron sus márgenes reales y se verificó la captura corregida. El revisor
independiente detectó además el límite de refresco por lote de las APIs: el filtro
opcional `item_id` concentra la consulta en la obra abierta dentro del catálogo propio.
Una prueba con 20 obras confirma que la última se consulta y un ID ajeno no lo hace.

## Validación

- Suite general `unittest discover -s tests -v`: **1054 pruebas, OK, 9 omitidas**.
- **6 pruebas nuevas Chromium**: composición y reflow 320/390, guardado parcial/sin
  cambios, conflicto con reconciliación explícita, error/reintento y país, privacidad
  fallida después del guardado, respuesta tardía al pasar a otra obra.
- **4 recorridos Chromium existentes**: procedencia de disponibilidad, foco/nombre de
  ficha, edición personal desde Inicio y contratapa determinista con transición reversible.
- **26 pruebas JS** existentes de selección y recuperación de imágenes: todas pasan.
- Ruff, formato, mypy (236 archivos), sintaxis JS y `git diff --check`.
- Detector Impeccable: avisos sobre colores heredados de la ficha/contratapa y su
  sidecar desactualizado; los nuevos estilos usan tokens existentes.

La `.venv` conserva una ruta antigua a otro usuario. La verificación utilizó Python
3.12 del runtime disponible con `src` y `.venv/Lib/site-packages` en `PYTHONPATH`,
sin modificar esa instalación. Se instaló el Chromium que requiere Playwright.

No se ejecutó la suite histórica completa de navegador de U4.6b, CI remoto, ensayo
de actualización Docker ni cierre de release. No hubo commit, push, merge ni tag.
