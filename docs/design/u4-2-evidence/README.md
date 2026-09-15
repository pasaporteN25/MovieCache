# U4.2 — Escenario y bastidor, revisión estructural

Fecha: 2026-09-09. Estado: **reconstrucción CSS rechazada por el owner**.

Estas capturas documentan una iteración fallida. Los tests verdes de abajo verificaron
comportamiento, no integración visual. La nueva revisión de assets y alternativas vive
en `../u4-2-options-v2/`. También queda por corregir el cierre prematuro a 1920 px:
el sobreancho fijo de 24 px no compensa los márgenes de un contenedor con ancho máximo.

## Motivo de la reapertura

La primera entrega resolvía fondo, columna y mueble mediante dos assets grandes. Aunque
la geometría pasaba las pruebas, el resultado seguía pareciendo el layout anterior con
otra piel: la columna lateral estaba pegada a la escena y la carcasa competía con los
controles vivos. Las capturas de esa iteración permanecen en la raíz de este directorio
como comparación rechazada.

## Revisión

- Se retiraron de producción `night-console-field-v1.png` y
  `vhs-continuous-furniture-v3.png`.
- El fondo desktop es ahora un campo mate casi liso, construido con gradientes de muy
  baja intensidad. No representa pared, habitación ni iluminación de neón.
- La antigua «espina» pasa a ser la pared técnica izquierda de un único grid estructural.
  Comparte el mismo borde con cartelera, título de Videoteca, navegación y mueble; ya no
  usa posición absoluta ni invade la cabecera.
- Ventilaciones, tornillos, serigrafías y cue se conservan como detalle del bastidor.
- La carcasa es CSS: una cavidad oscura y rieles continuos alineados con las aperturas
  existentes. No tiene poste derecho y consume el gutter final para terminar exactamente
  en el borde del viewport sin generar overflow.
- La composición interna de la cartelera no se modifica: corresponde a U4.3. Placas,
  lomos y consola conservan temporalmente su tratamiento U2-P hasta U4.4 y U4.5.

## Evidencia

La carpeta `rework-css/` contiene la escena en 1280×720, 1440×900, 1920×1080, 390×844
y 320×740. La carpeta `rework-css-full/` contiene el mueble poblado con 18 títulos de
referencia, incluyendo títulos largos y foco al final del recorrido.

Las capturas usan el catálogo temporal de navegador y nunca la biblioteca personal.

## Verificación

- `BrowserInterfaceTests`: **36/36**.
- `PackageLayoutTests`: **7/7**.
- Capturas reproducibles con `capture_u2_p_review.py` y
  `capture_u2_p3_review.py`; ambas verifican ausencia de overflow horizontal.
- Impeccable layout sobre `index.home.html`: `[]`.
- `git diff --check`: sin errores; sólo avisos de normalización CRLF en archivos ajenos
  preexistentes.
