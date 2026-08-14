# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Movie Inbox sirve hoy a una persona que administra su propia biblioteca audiovisual
desde una computadora o un servidor personal. El usuario necesita distinguir lo que
posee, lo que quiere ver y lo que ya vio, y conservar una memoria propia de cada obra.

El producto comienza con una instancia self-hosted privada: el administrador crea
cuentas y no existe registro publico. Cada usuario tiene un catalogo personal; las
obras agregadas por una persona no entran automaticamente en catalogos ajenos.

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
- La busqueda local consulta titulos multilenguaje, aliases, archivos e identificadores
  desde el servidor. Las fuentes externas se presentan por separado y usan el mismo
  matching conservador antes de escribir.

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
- La identidad usa owner local, miembros creados por invitacion, sesiones seguras y
  un catalogo personal creado o adoptado para cada cuenta.
- Cada catalogo es privado por defecto y puede compartirse en modo lectura solamente
  con las cuentas activas de la misma instancia.
- `status`, `watched_at` e historial tienen visibilidad general por usuario; rating y
  review tienen defaults independientes y overrides por obra.
- Las vistas compartidas nunca publican rutas, archivos locales, notas ni estado
  operativo. El owner no obtiene una excepcion a estas reglas de privacidad.
- Las colecciones curadas viven separadas de los catalogos personales. Seguir una
  coleccion local no copia obras; cada copia es explicita, neutraliza los campos
  personales y pasa por el matching conservador del catalogo de destino.
- `Club` distingue catalogos compartidos por miembros de colecciones publicadas por
  el administrador. La instancia incluye una coleccion inicial de Akira Kurosawa que
  no se sigue automaticamente.
- Compartir entre instalaciones, perfiles accesibles sin cuenta y registro abierto
  quedan para fases posteriores. No existe federacion entre homeservers.
- La interfaz importa TXT, CSV y JSON no confiables mediante borradores privados de
  48 horas. Antes de escribir permite previsualizar y clasificar filas, copiar obras
  al catalogo personal o crear una coleccion local privada. Todavia no incorpora filas
  a colecciones existentes ni ejecuta enriquecimiento externo durante la importacion.
- El scanner incremental puede ejecutarse por CLI o administrarse desde la web. Las
  rutas estan limitadas por configuracion del servidor; el owner prueba sin escribir,
  aplica el inventario y recien entonces puede automatizar recorridos horarios o
  diarios. Las identidades dudosas se resuelven desde la Bandeja.
- El owner puede recorrer graficamente solamente las raices autorizadas y comprobar
  lectura antes de registrar una biblioteca. `extras` y `sample` se omiten por defecto;
  discos multipartes comparten identidad y decision sin perder sus archivos fisicos.
- En la cola del Scanner, una candidata confirma solamente la identidad fisica. Un caso
  sin coincidencia puede crear una obra pendiente en el catalogo personal del owner y
  vincularla, comprobando antes coincidencias fuertes para evitar duplicados.
- El inventario fisico pertenece a la instancia y aporta disponibilidad verificada a
  todos los catalogos sin exponer rutas a miembros. La declaracion manual permanece
  como una senal separada.
- Docker Compose soporta una instancia nueva con estado persistente y hasta ocho
  raices fisicas de solo lectura. La relocalizacion de un `instance.db` existente
  queda para un incremento posterior; systemd y Nginx siguen soportados.
- Las portadas se cargan progresivamente despues del primer acceso a cada catalogo o
  coleccion y quedan en el almacenamiento persistente de la instancia. La navegacion
  visible tiene prioridad y nunca espera a que termine la cola global.
- Una instancia Docker puede producir backups completos verificados fuera de su volumen,
  omitiendo el cache reproducible y conservando catalogos, cuentas, privacidad,
  colecciones e inventario. La programacion pertenece al host y detiene brevemente la
  aplicacion para obtener un estado coherente de SQLite.
- `Inicio` ofrece una programacion editorial diaria, estable y explicable. Su cartelera
  principal propone entre una y cuatro obras disponibles con sinopsis y seleccion
  manual; las secciones pueden reunir pendientes
  disponibles, obras faltantes de colecciones seguidas, recuerdos personales por
  completar y rutas por director, genero o decada. La seleccion usa exclusivamente
  datos locales, evita repetir obras y no reemplaza la accion separada `Random`.
- Los accesos editoriales hacia `Coleccion` conservan su criterio mediante filtros
  enlazables. Distintas facetas se combinan por interseccion y varios valores de una
  misma faceta por union; la URL, los chips y Atras/Adelante representan el mismo estado.
- Las fechas de estreno se conservan con precision, pais, tipo y fuente. Una fecha
  completa puede alimentar efemerides; un dato anual o mensual nunca se presenta como
  si conocieramos el dia exacto.
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
