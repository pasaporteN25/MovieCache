# Estado de integración y cola vigente — 2026-10-04

## Ya en master: v0.10.0

- Home integrada, cartelera/lista, VHS al azar y primera entrega de imágenes.
- Colección U10; cajas, sticker y editor U11; sinopsis desplegable y proporciones.
- API de dispositivo, pairing, borradores, charadas, precondiciones personales,
  sesiones renovables/revocables, bajas y recibos de altas (X1–X10).
- Llenado de imágenes desde TMDb, fuentes externas y gates del motor de búsqueda.

## Implementado, todavía fuera de master

La rama de integración es `release/0.11.0`; todos sus commits van al PR #3.

- U12: resultados locales/externos unificados por relevancia y revisión de duplicados.
- X11: ids de dispositivos independientes del orden y ubicación de las fuentes.
- X12 A/B/C1/C2: identidad compartida, enriquecimiento Wikidata, motivos en Curaduría
  y conservación de selección/foco tras resolver.
- Avances locales X12 D/E2: seleccionar obras para comparar/unir desde la búsqueda,
  pistas de duplicados y navegación en contratapa. Se consolidan sin declararlos
  cierre de toda la fase D ni E.
- Rótulos centrados «Hoy/Ayer en cartel» y «Tu selección».
- Convención de ramas, instrucciones compartidas, plantilla de PR y opciones de Colección.

La variante local antigua de U12 tenía exactamente el mismo árbol que la release:
se integró mediante merge commit para conservar también su historial.

GitHub no permite cambiar el origen del PR #3. Su ref histórico
`codex/search-workbench-v011` se mantiene temporalmente como alias de la release,
apuntando al mismo commit al publicar. No trabajar en ese alias ni crear ramas nuevas
con ese prefijo. La release no está cerrada ni fusionada por esta consolidación.

## Pendiente de implementación o cierre

| Orden | Frente | Próximo resultado |
| --- | --- | --- |
| 1 | Controles de Colección | Elegir opción y construir búsqueda/filtros/vacío coherentes |
| 2 | X12 C | D y E hechas el 2026-10-06; falta C3–C6: búsqueda de referencia en el caso, copias e idiomas, unir como partes, anime a Jikan |
| 3 | X13 | Claves de API desde el menú |
| 4 | X14 | Certificado local y configuración HTTPS sin OpenSSL manual |
| Antes de M2 Android | Puente web/mobile | QR de apareamiento y lista/revocación de teléfonos |
| Por dependencias | U7 B | Galería/corrección persistente y gate de cobertura/identidad |
| Diferido respecto de lo anterior | U9 | Elegir sonido, preferencia, integración y gate de silencio |
| Menores | B2.1 y Curaduría | Consulta de una letra y comparación de señales por fuente |
| Entorno | TMDb | Smoke de overlay Docker y puntajes contra API real |
| Después | MW1, exploraciones e integraciones | Revisión web móvil; Radarr/Sonarr/Letterboxd; otros medios |

No confundir checkboxes históricos con bloqueos vigentes. Los cierres de v0.9.0 y
v0.10.0 ya ocurrieron. `tareas.md` mantiene el detalle; este documento ordena su lectura.

## Antes de cerrar la release

Fijar el corte de alcance y ejecutar `docs/release-checklist.md` con CI del commit
final. La base de instancia migra v23→v25 y no permite volver a 0.10.0 sobre ella:
backup antes de actualizar. X11 cambia una vez todos los ids de una réplica antigua;
sincronizar cambios pendientes antes de renovar esa réplica.
