# U2-P.7 — Ajustes de aceptación 1A / 2A / 3A · 2026-09-08

Capturas de un catálogo temporal y aislado, generadas con:

```powershell
.venv/Scripts/python.exe scripts/capture_u2_p7_review.py
```

## Resultado

- **1A:** en 390/320 el preview compartido queda inmediatamente debajo de la categoría
  activa. Cambiar de estante mueve la misma instancia; escritorio conserva la consola
  fija dentro del mueble.
- **2A:** la consola ocupa 21 % de la altura del mueble y aprovecha la bahía inferior
  sin reducir los lomos. Sinopsis, imágenes, créditos y estado ganan aire real.
- **3A:** el rótulo `Videoteca · Tu archivo por categoría` diferencia esta superficie
  de `Cartelera disponible` sin modificar la independencia de sus selecciones.
- Móvil usa datos de 12 px con wrap; a 320 créditos y estado se apilan. Página:
  0 px de overflow horizontal en los cinco viewports.

Evidencia principal: [Home 1440](home-1440.png), [consola 1440](console-1440.png),
[categoría y preview adyacentes a 390](active-category-390.png),
[preview 390](preview-390.png) y [preview 320](preview-320.png). Capturas adicionales y
mediciones están en este directorio y [metrics.json](metrics.json).

Las imágenes del fixture son fondos ambientales ya incluidos en el repositorio; sólo
demuestran carga exitosa y no se guardan como datos de ninguna obra. Regresión final:
44/44 pruebas correctas. El usuario aprobó las variantes 1A/2A/3A y el resultado visual
el 2026-09-08; la emulación no equivale a prueba en dispositivos físicos.
