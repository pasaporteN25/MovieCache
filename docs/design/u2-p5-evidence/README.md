# U2-P.5 — Continuidad del mueble · 2026-09-07

Capturas de un catálogo temporal y aislado, generadas con:

```powershell
.venv/Scripts/python.exe scripts/capture_u2_p5_review.py
```

## Resultado

- El mueble completo se extiende fuera del borde derecho: 76,797 px a 1280;
  86,391 px a 1440; 112 px a 1920. La fracción visible es 94,13 %, 94,16 % y
  93,55 % respectivamente; el poste del extremo derecho queda fuera del cuadro.
- No se repite una franja ni se edita el raster. El marco, huecos, consola y luces
  conservan un único registro al escalarse como una pieza.
- El carril compensa el sobreancho y mantiene un margen derecho visible de 54,969;
  62,094 y 72,906 px. Al llegar al final, el último lomo entra completo en el área
  visible. Las placas viajan junto con sus grupos.
- Desbordamiento horizontal de página: 0 px en los tres viewports.
- P.5 sólo se activa desde 861 px. La composición móvil apilada de P.4 no cambia.

Capturas iniciales: [1280](visible-1280.png), [1440](visible-1440.png),
[1920](visible-1920.png). Extremo final del carril:
[1280](end-1280.png), [1440](end-1440.png), [1920](end-1920.png).

Las capturas muestran el resultado visual y las pruebas verifican la geometría;
no sustituyen aceptación del usuario ni pruebas en dispositivos físicos.
