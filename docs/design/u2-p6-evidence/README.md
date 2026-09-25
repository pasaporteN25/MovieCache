# U2-P.6 — Consola de ficha breve · 2026-09-07

Capturas de un catálogo temporal y aislado, generadas con:

```powershell
.venv/Scripts/python.exe scripts/capture_u2_p6_review.py
```

## Resultado

- Se elimina la miniportada y el panel lateral «Ficha detalle»; VHS queda como firma
  visual compacta dentro de estado.
- La placa izquierda centra sus acciones. El display distribuye título/año,
  tipo/género, sinopsis, dos imágenes, créditos y estado resumido.
- Los dos marcos consumen imágenes del ítem y conservan su geometría con un fallback
  explícito «Sin imagen» cuando faltan o fallan.
- Móvil apila la información en orden de lectura y mantiene los dos marcos 16:9,
  créditos/estado y botones de 44 px, sin overflow horizontal de página.
- El bloque derecho usa créditos y estado en paralelo para evitar la compresión que
  apareció en la primera captura de escritorio.

Capturas: [1280](console-1280.png), [1440](console-1440.png),
[1920](console-1920.png), [390 móvil](console-mobile-390.png),
[320 móvil](console-mobile-320.png) y
[fallback sin imágenes](console-missing-images-1440.png). Las métricas reproducibles
están en [metrics.json](metrics.json).

Las dos imágenes visibles son fondos ambientales ya incluidos en el repositorio y se
inyectan únicamente en el fixture de captura para demostrar el estado de carga exitosa.
No se guardan como información factual de una obra ni modifican catálogos personales.
La regresión final suma 44/44 pruebas correctas (35 navegador, 7 empaquetado y 2
tokens). Las capturas no sustituyen la aceptación visual del usuario ni pruebas físicas.
