# U4.2 — Revisión de assets y del fallo de integración

2026-09-09. Inspección visual y de CSS; no es un gate de aceptación.
Se compararon el north star U2, la B original, los assets del kit y las capturas
rechazadas de U4.2. No se modificó la implementación durante esta exploración.

## Hallazgos

1. **Los encuentros estructurales no se conservaron.** En la B original, la base del
   marco del póster, el zócalo de la playlist y la cabeza del estante se unen en una
   pieza con espesor. El grid nuevo sólo alineó rectángulos y dejó huecos entre ellos.
   Compartir coordenada izquierda no garantiza que se lean como un mismo objeto.
2. **Las placas flotan por su geometría.** La nueva viga CSS termina alrededor de 7,7 %
   de la altura del mueble; el carril con sus placas comienza a 8,8 %. Las placas quedan
   dentro de la cavidad, por debajo de la viga. Falta superficie de montaje detrás.
3. **La sustitución del asset quitó aperturas sin construir otras.** Acciones y ficha
   inferior conservaron posiciones porcentuales de los huecos del viejo mueble. Al
   quitarlo, los botones quedaron sobre vacío y el display como rectángulo cyan externo.
4. **Se mezclan escalas de material.** Lomos y placas conservan grano, cantos y desgaste
   fuertes. Los rieles nuevos son franjas suaves, sin el mismo espesor ni tratamiento.
   Eliminar textura de una pieza sólo agranda el contraste con las demás.
5. **El exterior del mueble v2 está horneado.** Es RGB, con un campo oscuro exterior,
   poste terminal y aperturas fijas. Cambiar el fondo de la página no cambia ese campo.
   El panel derecho antiguo de formato también fija una geometría ya superada por P.6.
6. **La continuidad derecha se verificó de forma incompleta.** El test geométrico se
   ejecuta a 1280 px. El sobreancho CSS fijo de 24 px funciona con ese gutter, pero a
   1920 px el contenedor tiene ancho máximo: en la captura el mueble termina unos
   124 px antes del borde. No tener overflow de página no prueba continuidad.
7. **El catálogo mínimo escondía la calidad del conjunto.** Dos cintas y grandes vacíos
   sirven para probar estados, pero no para aprobar la integración y densidad de Home.
   Cada nueva alternativa debe mostrar la cartelera poblada y la ficha inferior entera.

## Decisión por pieza

| Pieza existente | Valor que conservar | Problema y tratamiento a evaluar |
| --- | --- | --- |
| Mueble continuo v2, 1802×873 RGB | Cavidad, labio, sombra de contacto, latón contenido | Exterior opaco, postes y huecos fijos: sustituir o rehacer por piezas compatibles con una composición común |
| Módulo de estante v1, 2017×780 RGBA | Profundidad clara y planos interior/frontal | Repetición de extremos y costuras; usar sólo como referencia de construcción |
| Marco de póster v1, 1024×1536 RGBA | HOY centrado, dos lámparas, marco tangible | Exterior independiente: integrar su borde en el mismo soporte de la playlist |
| Lomo v1, 724×2172 RGBA | Silueta alta, canto de cartón, tinta crema | Grano y luz propia muy fuertes: conservar geometría y armonizar material; no cambiar orientación aprobada |
| Placa de categoría v1 | Tipografía y metal oscuro/dorado aprobados | Ruido y sombra exterior a distinta escala: empotrar en travesaño, simplificar desgaste |
| Fondo de ladrillos | Ninguno: el owner pidió reemplazo completo | Campo derivado del material elegido, sin escena fotográfica |
| Fondo generado y mueble v3 rechazados | Sólo evidencia del intento | No recuperar automáticamente como assets de producción |
| Carcasa CSS rechazada | Estructura semántica y responsive reutilizable si sirve | No es autoridad visual ni motivo para imponer CSS exclusivo |

## Contrato para la siguiente implementación

El medio se decide por ingrediente. Son válidos assets raster coherentes, geometría
CSS/SVG y combinaciones; texto, imágenes de obras y controles continúan vivos.
Un posible kit incluye fascia superior, uniones laterales, labio de estante, biseles de
display y tratamiento de fondo nacidos de una misma referencia. Su tamaño de grano,
dirección de luz y escala de desgaste se calibran juntos.

Las tres propuestas de esta carpeta prueban la composición de todo U4. La programación
de U4.3–U4.5 sigue por etapas, pero el fondo y la carcasa de U4.2 deben admitir de entrada
sus uniones. Si una unión requiere HTML, se entrega junto al fragmento material necesario;
no se presenta una carcasa vacía como si la integración estuviera resuelta.

Antes de cerrar U4.2: comprobar las uniones con contenido en 1280, 1440 y 1920; verificar
la continuidad hasta cada borde; comparar con la imagen elegida; comprobar que no se
perdieron grosor, textura o jerarquía. Los tests funcionales se reportan por separado de
la aceptación estética.
