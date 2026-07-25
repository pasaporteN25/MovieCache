# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Movie Inbox sirve hoy a una persona que administra su propia biblioteca audiovisual
desde una computadora o un servidor personal. El usuario necesita distinguir lo que
posee, lo que quiere ver y lo que ya vio, y conservar una memoria propia de cada obra.

El producto incorporara login y multiples usuarios. El modelo de permisos, el grado
de separacion entre bibliotecas y la posibilidad de compartir catalogos siguen
abiertos.

## Product Purpose

Movie Inbox es la fuente personal unificada para registrar peliculas, series, anime y
documentales. Conecta la disponibilidad fisica de una obra con su estado personal:
pendiente, vista, puntaje, review y recuerdo asociado.

El producto debe permitir guardar tanto obras presentes en discos locales como obras
que el usuario desea conseguir, quiza consiga en el futuro o simplemente quiere
recordar despues de haberlas visto. El exito consiste en que esa historia personal y
la biblioteca real puedan consultarse y mantenerse desde un unico lugar.

## Positioning

Movie Inbox combina dos dimensiones que normalmente viven separadas: la gestion de
archivos disponibles en una biblioteca local y el registro personal de descubrimiento,
visualizacion y memoria. Las fuentes externas enriquecen y enlazan las entradas, pero
el catalogo propio sigue siendo la autoridad y permanece bajo control del usuario.

## Operating Context

- Se ejecuta como aplicacion web local o self-hosted y se administra desde el navegador.
- Puede importar titulos y enlaces desde TXT, CSV y JSON.
- Un scanner incremental sincroniza archivos de video desde discos y subdirectorios.
- Wikipedia, Wikidata, IMDb y FilmAffinity aportan enlaces y metadata externa.
- Una extension de Chrome puede capturar obras descubiertas durante la navegacion.
- JSON funciona como formato legible de intercambio y backup; SQLite ofrece
  almacenamiento transaccional y consultas estructuradas.
- La curacion incluye busqueda, matching asistido, deduplicacion y revision manual de
  coincidencias ambiguas.

## Capabilities and Constraints

- `en_catalogo` representa disponibilidad fisica y es independiente de `to_watch` o
  `watched`.
- El registro personal incluye fecha de visualizacion, puntaje de 0 a 10 y review.
- El matching automatico debe ser conservador: una coincidencia dudosa requiere
  revision humana antes de combinar entradas.
- Las correcciones manuales y los campos bloqueados deben sobrevivir al enriquecimiento
  posterior.
- El esquema admite peliculas, series, anime y documentales. Temporadas y episodios
  estan reservados para una fase futura.
- SQLite es la direccion preferida como fuente de verdad; JSON debe mantenerse como
  formato portable de importacion, exportacion y backup.
- La aplicacion web es la interfaz principal actual.
- Un cliente Kotlin es una integracion futura importante, pero no forma parte de la
  siguiente etapa inmediata.
- Login y multiples usuarios son una prioridad cercana. Autenticacion, roles y
  aislamiento de datos todavia no estan decididos.
- Sonarr, Radarr, Letterboxd y otras fuentes son integraciones posibles. Su orden y el
  alcance de la sincronizacion siguen abiertos.
- El despliegue debe poder vivir en un servidor personal y leer bibliotecas distribuidas
  en varios discos.

## Brand Commitments

El nombre del producto es **Movie Inbox**. La terminologia debe conservar la diferencia
entre coleccion fisica, pendientes, obras vistas y memoria personal; ninguna de esas
dimensiones debe presentarse como sustituta de las otras.

## Evidence on Hand

- El paquete instalable y la CLI viven en `src/movie_inbox/`.
- La interfaz web funcional vive en `src/movie_inbox/web/`.
- El contrato de intercambio esta versionado en `catalog.schema.json`.
- Existen repositorios JSON y SQLite, importadores, enriquecimiento externo, matching,
  cache de imagenes y scanner incremental.
- La extension existente vive en `chrome-extension/`.
- Los catalogos personales, bases, caches, reportes y backups no forman parte del
  repositorio y no deben usarse como contenido publico o prueba comercial.
- No existen testimonios, clientes, metricas de adopcion ni afirmaciones comerciales
  que futuras superficies deban inventar.

## Product Principles

1. El usuario conserva la propiedad y portabilidad de su catalogo.
2. Disponibilidad fisica, intencion de ver y memoria personal son estados distintos.
3. La automatizacion propone y enriquece; las decisiones ambiguas permanecen bajo
   control humano.
4. Las integraciones amplian el producto sin convertir servicios externos en su fuente
   de verdad.
5. La evolucion hacia multiples usuarios y clientes adicionales debe preservar una
   experiencia personal, confiable y recuperable.
