# U7 A · primera entrega visual

Implementada localmente el 2026-09-26 sobre `release/0.10.0`, sin commit.
Alcance: U7.0, U7.1b y U7.5c.1–3 del plan U7/U9. No cierra U7 B ni inicia U9.

## Resultado y composición

- Dos imágenes distintas: panorámica primero, portada después, respetando los cinco
  diseños de contratapa. Una sola: una ventana sin repetición. Ninguna: un único
  aviso «Sin imágenes guardadas para esta obra» con el resto de la ficha disponible.
- Se eligió la ventana única frente al hueco/repetición de una segunda ventana.
  [Comparación 0/1/2](comparison.png) y [contratapa angosta](mobile.png).
  Son capturas del renderer productivo con datos descartables; la panorámica es una
  ilustración explícitamente rotulada de prueba, no una escena de Metropolis.
- Imágenes completas con `object-fit: contain`, roles honestos, dimensiones
  reservadas y estado de carga/error local. Las fichas angostas permiten que los
  valores técnicos bajen de línea; el contenido conserva su scroll accesible.
- Se reutiliza `/image-cache`; su validación de hosts sigue siendo del servidor.
  Se descartan URLs mal formadas, esquemas no HTTP(S) y credenciales en URL.
- Variantes de tamaño conocidas de TMDb, Wikimedia, IMDb/Amazon, FilmAffinity y
  MyAnimeList cuentan como una imagen. Si ambos campos repiten la portada, conserva
  ese rol. Para hosts desconocidos no se descartan queries que podrían identificar
  imágenes diferentes. No se agregan búsquedas, API ni datos persistidos.
- Los eventos afectan sólo a su imagen conectada al DOM; una respuesta tardía de
  una ficha retirada no cambia la obra actual. Club y permisos conservan sus rutas.

## Matriz comprobada

| Caso | Resultado |
| --- | --- |
| Campos vacíos | Estado vacío único; no se solicitan imágenes. |
| Una portada / una panorámica | Una ventana, rol correcto y proporción conservada. |
| Dos imágenes distintas | Dos ventanas, orden estable. |
| Misma imagen con otro tamaño | Una ventana; no se presenta como material distinto. |
| URL mal formada o credenciales | No se genera solicitud de imagen. |
| Respuesta 403 / 404 | Error local; la otra imagen y Escape siguen disponibles. |
| Solicitud retenida / cache frío | Cargando imagen, espacio reservado y ficha operativa. |
| Respuesta tras cambiar de obra | La nueva obra mantiene su propia imagen. |

## Validación

- 45 pruebas de navegador aprobadas; nueva matriz de 0/1/2 imágenes en las cinco
  plantillas a 1280 y 390 px. Las comprobaciones de errores/respuestas tardías se
  ejecutan con respuestas locales, sin proveedores externos ni datos personales.
- 31 pruebas JS aprobadas: selección, seguridad de URL, deduplicación y HTML.
- Tras el ajuste final de composición, 28 pruebas aprobadas entre los dos escenarios
  de navegador afectados y empaquetado, capas y cobertura de imágenes.
- Ruff/formato, mypy del archivo de pruebas, sintaxis JS y diff comprobados.
- Detector: sólo avisos de paleta; se conserva el material existente.
- No se repitió la suite general del backend en este corte de presentación. La
  última corrida completa previa conserva dos fallos conocidos de temporización
  externa, documentados en `../../briefs/home-loading-v1.md`.

La adquisición de imágenes nuevas, galería persistente, atribución ampliada y edición
de selección siguen en U7.2–4/U7.5b/U7.6. No se promete cobertura total.
