# U9.1a · muestras de sonido

2026-09-26. Tres propuestas para sentir el contacto con una caja VHS al seleccionarla.
Muestras de exploración; todavía no están conectadas a la aplicación. U9.1b sigue
pendiente: escuchar, elegir y probar el timbre en contexto con clic/tap/flechas.

| Muestra | Intención | Duración del efecto | Escucha (tres repeticiones) |
| --- | --- | --- | --- |
| [01 · Roce](01-roce.wav) | Fricción de una caja al deslizarse: ruido filtrado, presión variable. | 120 ms | [Reproducir](01-roce-escucha.wav) |
| [02 · Clic](02-clic.wav) | Encastre plástico: dos ataques pequeños, cuerpo hueco. | 100 ms | [Reproducir](02-clic-escucha.wav) |
| [03 · Toque](03-toque.wav) | Contacto amortiguado sobre una etiqueta: grave y breve. | 90 ms | [Reproducir](03-toque-escucha.wav) |

Las versiones `-escucha.wav` contienen el mismo efecto a idéntico nivel, repetido tres
veces, con 250 ms de silencio inicial y 700 ms después de cada repetición. Las pausas
son sólo para comparar; no forman parte del efecto que se integraría.

## Procedencia y licencia

Síntesis procedural creada para Movie Inbox con [generate.py](generate.py): ruido
pseudoaleatorio de semilla fija, filtros y senos amortiguados. Sin grabaciones,
samples de terceros, sonidos de películas, servicios de generación ni descargas.
Los nombres describen la intención material; no son grabaciones de objetos reales.

El generador y los WAV se incorporan bajo GPLv3, la [licencia del proyecto](../../../LICENSE).
Se conserva el código fuente editable que produce cada recurso; no se necesita un
servicio o herramienta propietaria para modificarlos o regenerarlos.

## Reproducción y validación

Desde la raíz, con Python 3.11 o posterior, sin instalar dependencias:

```powershell
python docs/design/u9-sound-samples/generate.py
```

Formato PCM WAV, mono, 48 kHz, 16 bits. Cada efecto pesa menos de 12 KB. Nivel RMS
objetivo de −29 dBFS con pico limitado a −14 dBFS, entradas/salidas a cero. Esto no
iguala automáticamente la sonoridad percibida ni el volumen físico de los parlantes.
[manifest.json](manifest.json) registra duración, niveles y hashes reproducibles.

Se verifica formato, duración, ausencia de clipping, extremos a cero y regeneración
idéntica. La evaluación perceptiva queda pendiente de escucha del owner; no se afirma
una validación auditiva humana a partir de estas mediciones.

Próximo paso: elegir la muestra y ajustar intensidad en el prototipo. La integración
prevista conserva sonido apagado inicialmente, prueba explícita y mute inmediato;
sin sonido en hover, foco pasivo, restauración o carga de la página.
