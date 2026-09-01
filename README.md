# Movie Inbox

Gestor self-hosted para organizar obras, disponibilidad fisica y memoria personal a partir de listas, fuentes externas y bibliotecas locales.

## Estado del proyecto

La version estable actual es **v0.6.0**. Movie Inbox es una aplicacion web multiusuario para una instancia personal o familiar: cada cuenta tiene su propio catalogo, mientras que el inventario fisico y las bibliotecas administradas pertenecen al servidor. Importa listas, consulta fuentes externas, detecta duplicados y permite administrar disponibilidad, estado de visualizacion, puntajes y reviews.

v0.3.0 cerro el gate de calidad de busqueda (cero falsos positivos conocidos en
auto-match y merge, con `movie-inbox search-lab run --enforce` como gate real en CI).
v0.4.0 unifico el lenguaje visual y la arquitectura de `Inicio`, `Coleccion`, `Bandeja`,
`Club` y `Administrar`: una franja de alcance persistente distingue `Archivo fisico`,
`Identidad compartida` y `Ficha en tu catalogo` en cada decision; disponibilidad se
presenta siempre como `Disponible` (o no) con su procedencia real, nunca como el flag
manual crudo; y la cola de revision se organiza por causa y confianza en vez de una
lista plana.

v0.5.0 completa ese cierre: Scanner incorpora actividad y deshacer, Curaduria suma
busqueda y navegacion por teclado, los duplicados quedan diferenciados aun en empates
extremos y la busqueda externa reconoce titulos multilingues verificados contra el
mismo identificador de IMDb. El acceso conserva el carnet de videoclub con una
secuencia de credenciales mas clara y adaptable.

v0.6.0 profundiza descubrimiento y operacion familiar: diagnostica regresiones
multilingues sin red, conserva consultas ambiguas como `Verano 1993`, permite buscar
por direccion sin usarla como prueba de identidad y suma un prototipo opt-in del indice
oficial no comercial de IMDb. Las bibliotecas aceptan exclusiones propias y el admin
puede publicar su disponibilidad como una coleccion de Club sin exponer rutas ni
archivos. Detalle completo de las versiones en [CHANGELOG.md](CHANGELOG.md).

El paquete instalable y la interfaz web son el camino recomendado. Los lanzadores de
compatibilidad con v0.1 (`txt_to_catalog.py`, `scan_library.py`, `view_catalog.py`,
`enrich_catalog.py`, `match_external_links.py`, `migrate_catalog.py`) no viven en este
repositorio: quedan en `codigoLegacy/`, fuera de Git, para quien todavia los necesite
localmente — ver [Estado de compatibilidad](#estado-de-compatibilidad) al final de este
documento.

En una instalacion nueva, SQLite es la fuente de verdad recomendada. JSON conserva un contrato versionado como formato de importacion, exportacion y auditoria, pero una exportacion individual no reemplaza el backup completo de la instancia. Catalogos, cuentas, reportes, caches y backups se mantienen fuera de Git. Las capacidades de cada version estan resumidas en [CHANGELOG.md](CHANGELOG.md).

El gate reproducible de pruebas y aceptacion en un servidor real esta documentado en [docs/release-checklist.md](docs/release-checklist.md).

El codigo principal vive en el paquete instalable `src/movie_inbox`.

Nucleo actual:

- `scripts/docker-backup.sh`: detiene brevemente Compose, crea un backup verificado y comprueba el reinicio.
- `src/movie_inbox/domain/`: modelos, normalizacion, matching y reglas de merge.
- `src/movie_inbox/application/`: casos de uso compartidos por el visor, importadores y scanner.
- `src/movie_inbox/infrastructure/`: esquemas, repositorios JSON/SQLite y exportacion.
- `src/movie_inbox/external/`: clientes separados para Wikipedia, Wikidata, IMDb, FilmAffinity y Jikan.
- `src/movie_inbox/web/`: aplicacion FastAPI, servidor Uvicorn, proxy seguro de imagenes y assets estaticos.
- `catalog.schema.json`: contrato JSON versionado del catalogo.
- `PRODUCT.md` y `DESIGN.md`: contratos de producto, terminologia y lenguaje visual del visor.

Herramientas conservadas por compatibilidad, todavia en el repositorio:

- `scripts/scan_video_catalog.sh`: genera un JSON puntual desde archivos de video.
- `scripts/build_viewer.py`: visor HTML estatico para exportaciones.
- `chrome-extension/`: capturador experimental con exportacion CSV/JSON, sin sincronizacion directa con la instancia.

Los lanzadores de v0.1 que solo llamaban al mismo comando del paquete
(`txt_to_catalog.py`, `scan_library.py`, `view_catalog.py`, mas los shims de import
`catalog_*.py`) se movieron a `codigoLegacy/` — ver
[Estado de compatibilidad](#estado-de-compatibilidad).

## Puesta en marcha

Para una instancia permanente, Docker Compose es el camino recomendado. Mantiene SQLite, catalogos de miembros y cache de imagenes en un volumen persistente; las bibliotecas se montan en solo lectura y los backups se escriben fuera del volumen. La guia completa, incluido el primer acceso y la actualizacion sin perder datos, esta en [docs/docker.md](docs/docker.md).

La instalacion nativa sigue siendo util para desarrollar o ejecutar herramientas puntuales.

Para trabajar desde un checkout, instala el paquete en modo editable:

```powershell
py -m pip install -e .
```

Eso habilita un unico comando con subcomandos:

```powershell
movie-inbox import links.txt --json catalog.json --fetch
movie-inbox scan --config scanner.json --dry-run
movie-inbox account bootstrap --instance-db .movie-inbox/instance.db --catalog catalog.json --username lucas
movie-inbox serve catalog.json
movie-inbox migrate catalog-viejo.json --json catalog-v6.json
movie-inbox enrich catalog.json --json catalog-enriquecido.json
movie-inbox match catalog.json --json catalog-con-links.json
movie-inbox db import catalog.json --db data/movie-inbox.db
movie-inbox db export data/movie-inbox.db --json backups/catalog.json
movie-inbox cache info --dir .catalog-cache/images
movie-inbox backup create data --output-dir backups --retention-days 14
movie-inbox backup verify backups/movie-inbox-instance-20260811-033000Z.tar.gz
movie-inbox search-lab run --json reports/search-baseline.json --html reports/search-baseline.html
movie-inbox search-lab external-diagnostics --enforce
movie-inbox imdb-dataset stats --output-dir data/imdb
movie-inbox anime-dataset stats --output-dir data/anime
```

En Windows, si la carpeta `Scripts` de Python no esta en `PATH`, usa la forma equivalente:

```powershell
py -m movie_inbox serve catalog.json
```

El ejecutable suele quedar en `%LocalAppData%\Programs\Python\Python314\Scripts`. Agregar esa carpeta al `PATH` permite invocar directamente `movie-inbox` desde una terminal nueva.

Los ejemplos de este documento marcados "(compatibilidad)" usan directamente `movie-inbox <subcomando>` — los lanzadores sueltos que antes llamaban a esa misma implementacion (`scripts/txt_to_catalog.py`, `scripts/scan_library.py`, `scripts/view_catalog.py`) se movieron a `codigoLegacy/`, fuera de Git (ver [Estado de compatibilidad](#estado-de-compatibilidad)).

### Search Lab de v0.3.0

`Search Lab` mide el ranking productivo actual sin cambiarlo. El corpus incluido usa
datos sinteticos y respuestas externas grabadas, por lo que el runner no consulta la
red, no abre SQLite y no escribe en ningun catalogo. Una baseline que no alcanza los
umbrales se informa como `FAIL (baseline recorded)` pero retorna codigo `0`:

```powershell
movie-inbox search-lab run `
  --json reports/search-baseline.json `
  --html reports/search-baseline.html
```

Para convertirlo en un gate de CI se agrega `--enforce`; en ese modo retorna codigo
`1` mientras alguna metrica quede debajo del objetivo o aparezca un resultado
prohibido. Tambien se puede inspeccionar un export JSON real en modo de solo lectura:

```powershell
movie-inbox search-lab inspect backups/catalog.json "Heat" --mode catalog --html reports/heat.html
movie-inbox search-lab inspect backups/catalog.json "The Fly" --mode identity --year 1986
movie-inbox search-lab inspect backups/catalog.json "1917" --mode scanner --year 2019
```

`inspect` no acepta una base `.db`, no crea locks y se niega a usar el archivo de
entrada como destino de un reporte. El corpus, las metricas y el orden de trabajo de
v0.3.0 estan documentados en [docs/search-quality.md](docs/search-quality.md).

`compare` corre el mismo corpus dorado bajo una estrategia candidata (umbrales de
ranking/matching con nombre, en `domain/search_strategy.py`) y genera un reporte de dos
columnas contra la baseline productiva, sin cambiar el comportamiento real de busqueda:

```powershell
movie-inbox search-lab compare --candidate estrategia-candidata.json --html reports/compare.html
```

### Indice local opt-in de IMDb

`imdb-dataset` es un prototipo separado del catalogo real. Descarga exclusivamente
`title.basics` y `title.akas` desde los datasets oficiales no comerciales de IMDb,
construye un SQLite local y permite medirlo o consultarlo sin escribir fichas ni
participar de merges:

```powershell
movie-inbox imdb-dataset sync --output-dir data/imdb --report reports/imdb-sync.json
movie-inbox imdb-dataset stats --output-dir data/imdb
movie-inbox imdb-dataset lookup --output-dir data/imdb --title "Heat" --year 1995
movie-inbox imdb-dataset lookup --output-dir data/imdb --tconst tt0113277
```

No se descarga durante la instalacion ni al iniciar el servidor. La medicion de
referencia del 2026-08-29 descargo aproximadamente 704 MB y produjo un indice de
aproximadamente 8,1 GB en 24 minutos; reservar espacio y ejecutarlo como una tarea de
mantenimiento. Su uso queda sujeto a las condiciones personales/no comerciales y a la
atribucion que imprime el propio comando.

### Respaldo local opt-in para anime

`anime-dataset` construye un SQLite separado y descartable a partir de un snapshot
local de `anime-offline-database`. Movie Inbox no descarga ni empaqueta el snapshot:
el owner elige el archivo `.jsonl` o `.json`, y el comando conserva en el indice su
fecha, licencia y SHA-256.

```powershell
movie-inbox anime-dataset sync `
  --snapshot downloads/anime-offline-database.jsonl `
  --output-dir data/anime `
  --report reports/anime-sync.json
movie-inbox anime-dataset stats --output-dir data/anime
movie-inbox anime-dataset lookup --output-dir data/anime --title "El cuaderno de la muerte"
movie-inbox anime-dataset lookup --output-dir data/anime --external-id anilist:1535
```

El servidor permanece igual si no se configura el indice. Para activarlo como
respaldo secundario de Jikan:

```powershell
movie-inbox serve catalog.json --anime-offline-index data/anime/anime-offline.db
```

Jikan conserva prioridad. El indice solo suma aliases e IDs compatibles a una
coincidencia viva o presenta resultados propios —rotulados `Anime DB offline`— cuando
Jikan falla, entra en cooldown o responde sin coincidencias. Sus resultados muestran
la atribucion ODbL/DbCL y la fecha del snapshot; nunca se presentan como datos en vivo.

### Primer acceso

El visor requiere una cuenta owner. En el primer `serve`, si la instancia todavia no tiene usuarios, la terminal solicita una contrasena y adopta el catalogo indicado sin reescribirlo:

```powershell
movie-inbox serve catalog.json --owner-username lucas
```

Para preparar un servicio sin terminal interactiva se puede hacer el bootstrap por separado:

```powershell
movie-inbox account bootstrap `
  --instance-db data/instance.db `
  --catalog data/movie-inbox.db `
  --username lucas

movie-inbox serve data/movie-inbox.db --instance-db data/instance.db
```

El comando solicita la contrasena sin mostrarla. `--password-file` permite usar un secreto temporal durante un despliegue automatizado; ese archivo debe eliminarse despues. La base de instancia guarda cuentas, hashes de contrasena, sesiones y la relacion owner/catalogo. Por defecto vive en `.movie-inbox/instance.db` junto al catalogo editable.

El catalogo conserva su formato normal y sigue pudiendo importarse o exportarse como JSON. La adopcion inicial solamente registra su propiedad en la base de instancia: no mueve ni modifica obras, reviews o archivos locales.

### Miembros y catalogos personales

El owner administra miembros desde `Administrar > Miembros`. Una cuenta nueva recibe una contrasena temporal, debe reemplazarla en su primer acceso y obtiene un catalogo SQLite vacio. El owner puede editar el usuario y el nombre de su catalogo, desactivar o reactivar la cuenta, restablecer el acceso y archivarla de forma reversible. Desactivar o restablecer revoca inmediatamente sus sesiones; archivar exige desactivar primero y escribir el username como confirmacion. El archivo conserva el catalogo en disco y restaurarlo genera una credencial temporal nueva.

Por defecto, los catalogos nuevos se crean en `.movie-inbox/catalogs/` junto a `instance.db`. La ubicacion puede definirse al iniciar el servidor:

```powershell
py -m movie_inbox serve scripts/catalogv4.json `
  --member-catalog-dir data/member-catalogs
```

Cada request abre exclusivamente las fuentes registradas para la cuenta autenticada. La API usa referencias opacas como `source-1`, por lo que no publica rutas absolutas del servidor. JSON permanece disponible como importacion y exportacion individual; cuentas, sesiones y pertenencia siguen viviendo solamente en `instance.db`.

### Club y privacidad

Cada catalogo es privado por defecto. Desde `Privacidad`, cualquier cuenta puede habilitar su estante en `Club` para las demas cuentas activas de la misma instancia. `status`, `watched_at` y la actividad reciente tienen controles generales independientes. Puntajes y reviews tambien tienen un valor general, pero cada ficha puede heredarlo, compartir ese campo solamente para la obra actual o mantenerlo privado.

`Club` es de solo lectura y no mezcla obras entre usuarios. La respuesta compartida usa una lista explicita de metadata publica: nunca incluye rutas, archivos locales, notas, bloqueos, procedencia ni referencias operativas del servidor. Desactivar o archivar una cuenta retira inmediatamente su catalogo del Club. Una cuenta restaurada comienza otra vez con privacidad cerrada, aunque conserva sus obras y su registro personal.

El Club tambien separa `Miembros` de `Colecciones`. Una coleccion es una lista curada de referencias y no contiene estado personal. Seguirla conserva el estante en lectura y recibe sus cambios dentro de la misma instancia; no copia nada al catalogo. `Agregar`, `Agregar seleccion` y `Agregar faltantes` copian solamente identidad, titulos, metadata y links, con `status: to_watch`, `en_catalogo: false`, rating 0 y review vacia. Duplicados exactos se omiten y las coincidencias dudosas quedan sin copiar.

Cada instancia instala una sola vez la coleccion inicial `Akira Kurosawa`, basada en la tabla de obras como director de Wikipedia. Incluye 31 registros, entre ellos la obra codirigida `Those Who Make Tomorrow`, y no se sigue automaticamente. Colecciones, seguimientos y la marca de instalacion viven en `instance.db`; no forman parte del JSON personal.

## Persistencia y backups

Para crear una base SQLite sin modificar el JSON original:

```powershell
py -m movie_inbox db import scripts/catalogv3_links.json --db data/movie-inbox.db
```

El import compara el documento canonico completo despues de escribir: titulos, aliases, reviews, metadata, links y archivos locales, no solamente los IDs. No reemplaza una base con datos salvo que se use `--replace`; en ese caso primero crea un backup JSON de la base anterior. El visor, scanner, enriquecedor y matcher seleccionan el repositorio por extension, por lo que la base se abre directamente:

```powershell
py -m movie_inbox serve data/movie-inbox.db
py -m movie_inbox db info data/movie-inbox.db
```

Para generar un backup legible y versionado:

```powershell
py -m movie_inbox db export data/movie-inbox.db --json backups/catalog-2026-07-15.json
```

Cada usuario tambien puede abrir `Administrar > Base de datos` y descargar su catalogo personal. `Descargar JSON` conserva el documento versionado completo y es la opcion indicada para restaurar o migrar las obras; `Descargar CSV` ofrece una copia comoda para planillas. Ninguna de las dos descargas incluye cuentas, sesiones, privacidad, colecciones, seguimientos ni inventario compartido: para recuperar toda una instancia Docker se respalda el volumen completo como indica [docs/docker.md](docs/docker.md).

`movie-inbox backup create` genera un `.tar.gz` atomico de una instancia completa y un
checksum SHA-256 lateral. Exige `movie-inbox.db` e `instance.db`, lee el archivo para
verificarlo antes de publicarlo, conserva catalogos de miembros y estado operativo, y
omite por defecto `image-cache` porque puede reconstruirse. En Docker se ejecuta con
una parada breve mediante `scripts/docker-backup.sh`; el timer systemd y la retencion
diaria estan documentados en [docs/docker.md](docs/docker.md#backups-automaticos).

SQLite normaliza obras, aliases, IDs externos, archivos locales, tags y procedencia. Las actualizaciones frecuentes son granulares: estado y fecha se actualizan directamente, mientras que metadata y relaciones reconstruyen solamente la parte modificada del item. Las operaciones batch conservan una transaccion unica pero sincronizan diferencias en vez de reescribir todas las relaciones. Tambien reserva tablas para temporadas y episodios, aunque esa funcionalidad todavia no forma parte del dominio ni de la interfaz. Los archivos `.db`, `.sqlite`, sus journals y `data/` se ignoran en Git.

## Importacion TXT por CLI (compatibilidad)

Para el uso cotidiano se recomienda `Bandeja > Importaciones`, que ofrece previsualizacion y deduplicacion antes de escribir. La CLI sigue siendo util para conversiones repetibles o trabajo fuera del servidor.

Crear un archivo, por ejemplo `links.txt`:

```txt
https://en.wikipedia.org/wiki/Blade_Runner
https://www.imdb.com/title/tt0083658/
The English Patient 1996
Mile End Kicks
```

Generar JSON y CSV:

```powershell
movie-inbox import links.txt --json catalog.json --csv catalog.csv
```

El comando imprime un resumen con:

- filas/URLs/items leidos
- duplicados dentro del archivo de entrada
- items agregados
- items finales
- lista corta de URLs/items duplicados

Intentar completar metadata desde las paginas:

```powershell
movie-inbox import links.txt --json catalog.json --csv catalog.csv --fetch
```

El modo `--fetch` usa solo librerias standard de Python. Para lineas que son solo texto intenta buscar por titulo en Wikipedia; para links de Wikipedia usa la API publica de Wikipedia y completa, cuando existe:

- titulo
- descripcion corta
- resumen
- imagen principal
- id de Wikidata

Para otros sitios intenta extraer lo mas comun desde OpenGraph, `<title>` o metadata HTML.

## Escanear una carpeta local de peliculas

### Scanner administrado en el servidor

Para una instancia self-hosted, el modo recomendado es habilitar explicitamente las
raices que Movie Inbox puede leer al iniciar el visor. El owner puede recorrer esas
raices desde un explorador interno y comprobar una carpeta antes de guardarla; la API
no acepta ni muestra rutas fuera de esa lista, y los miembros nunca ven rutas:

```powershell
movie-inbox serve data/movie-inbox.db `
  --instance-db data/instance.db `
  --library-root "D:\Peliculas" `
  --library-root "E:\Series"
```

El owner registra despues cada ruta desde `Administrar > Bibliotecas`. Toda biblioteca
nueva sigue una secuencia explicita: `Probar recorrido` lee y clasifica sin persistir,
`Aplicar inventario` vuelve a recorrer la ruta y guarda la disponibilidad, y solamente
entonces puede habilitarse `Escaneo automatico` si la frecuencia es horaria o diaria.
Una biblioteca manual nunca necesita activarse y conserva `Escanear ahora` como accion
principal. Los recorridos se ejecutan fuera del request HTTP y su estado persiste en
`instance.db`.

El recorrido ignora por defecto subcarpetas llamadas `extra`, `extras`, `sample` o
`samples`, sin importar mayusculas. Los archivos `CD1/CD2`, `disc1/disc2` o `disk1/disk2`
que comparten carpeta, titulo, ano y tipo se presentan como una sola obra en la Bandeja.
Confirmar u omitir ese caso actualiza todas sus partes en una unica transaccion, aunque
el inventario conserva cada archivo y suma su disponibilidad real.

El inventario fisico pertenece a la instancia. Una coincidencia fuerte aporta
disponibilidad verificada a los catalogos de todos los usuarios sin copiar obras ni
cambiar `status`, `watched_at`, `rating` o `review`. La declaracion manual de
`en_catalogo` se conserva por separado: retirar una senal no elimina la otra. Los
miembros reciben solamente el estado agregado; rutas, nombres de archivo y huellas son
exclusivos del owner.

La interfaz llama `Disponible` al resultado efectivo de ambas procedencias. En la ficha,
`Inventario del servidor` y `Declaracion manual` se muestran por separado; por eso una
declaracion manual inactiva no vuelve indisponible una obra que conserva un archivo
vinculado en una biblioteca administrada.

Archivos nuevos, titulos sin ano y coincidencias ambiguas aparecen en
`Bandeja > Scanner`. Elegir una candidata vincula el archivo con una identidad existente
del inventario compartido y no copia esa obra a ningun catalogo. Cuando ninguna candidata
corresponde y tampoco existe una ficha parecida, `Agregar obra y vincular` vuelve a
comprobar el catalogo personal del owner, crea una entrada pendiente y le aporta
disponibilidad fisica verificada. Si aparece cualquier coincidencia revisable, el Scanner
ofrece comparar y vincular la existente. Si ninguna corresponde, `Conservar ambas`
repite la comprobacion con el titulo, ano y tipo confirmados; un segundo paso explicito
crea una ficha separada, confirma el archivo con su identidad y registra las candidatas
revisadas como obras diferentes. No cambia fecha de vista, rating ni review.
La cola se puede filtrar entre casos para comparar y archivos sin coincidencia, o buscar
por titulo, ano, ruta y biblioteca. `Omitir este archivo` no borra datos ni toca el disco:
retira el caso mientras conserve la misma huella y exige confirmacion. La decision, igual
que vincular un archivo, queda en `Actividad` y puede deshacerse mientras nada mas haya
cambiado el caso desde entonces. Si un disco desaparece o la proporcion de bajas supera el
limite configurado, se conserva el ultimo inventario valido.

Las sugerencias se construyen con el catalogo del owner y con catalogos que sus
miembros hayan compartido de forma explicita. Los catalogos privados nunca se usan como
fuente de candidatos. El matching indexa titulos y terminos al comenzar cada recorrido,
por lo que no necesita comparar cada archivo contra todas las obras de la instancia.

### Scanner Python incremental (compatibilidad)

Este comando conserva el flujo anterior para reconciliar un catalogo de forma puntual. En una instancia permanente conviene usar `Administrar > Bibliotecas`, que limita las raices visibles, separa Probar/Aplicar/Automatizar y persiste el inventario compartido. `scanner.example.json` muestra la configuracion de la CLI; las rutas relativas se resuelven desde la carpeta donde esta ese archivo.

El primer recorrido debe ser una simulacion:

```powershell
movie-inbox scan --config scanner.json --dry-run --report scanner-report.json
```

El reporte separa archivos sin cambios, modificados, movidos, asociados a entradas existentes, entradas nuevas y casos `needs_review`. Si el resultado es correcto, se aplica sobre el JSON:

```powershell
movie-inbox scan --config scanner.json --apply --report scanner-report.json
```

Para detectar cambios periodicamente en el mismo proceso:

```powershell
movie-inbox scan --config scanner.json --apply --watch --interval 300 --report scanner-report.json
```

La CLI legacy sigue disponible para reconciliar directamente un unico catalogo. Recorre subcarpetas y guarda estado liviano en `.catalog-state`. Usa el mismo parser y motor de huellas que el scanner administrado para evitar reglas divergentes. Un movimiento dentro del disco conserva la entrada; una coincidencia unica por titulo, ano y tipo se asocia al item existente; una coincidencia ambigua no se aplica y queda en `needs_review`.

Si el disco no existe o no esta montado, el scanner aborta antes de modificar el catalogo. Tambien compara el recorrido con el ultimo estado y omite bajas cuando desaparece mas del porcentaje configurado en `max_missing_ratio` (50% por defecto), lo que cubre puntos de montaje que siguen existiendo pero aparecen vacios. Si hubo errores parciales de lectura, actualiza lo que pudo ver pero no marca archivos ausentes ni reemplaza el ultimo estado completo. El scanner solo administra `local_files` y la disponibilidad agregada `en_catalogo`: no modifica `status`, `watched_at`, `rating` ni `review`, y no consulta fuentes externas durante el recorrido.

### Export rapido con Bash (compatibilidad)

Si tenes una carpeta con archivos de video, podes generar un JSON compatible con el catalogo:

```bash
bash scripts/scan_video_catalog.sh "/ruta/a/peliculas" --json local_catalog.json --verbose
```

Si no pasas una ruta, escanea el directorio actual:

```bash
bash scripts/scan_video_catalog.sh --json local_catalog.json --verbose
```

El script recorre subcarpetas, toma solo archivos de video e ignora subtitulos, carpetas y otros archivos. Los items generados tienen:

- `source`: `local_files`
- `en_catalogo`: `true`
- `local_name`: nombre del archivo de video
- `local_path`: ruta relativa dentro de la carpeta escaneada
- `local_files`: lista estructurada de archivos asociados a la misma obra
- `rating`: `0`
- `review`: vacio
- `watched_at`: vacio
- `url`: vacio

Extensiones de video incluidas: `mkv`, `mp4`, `avi`, `mov`, `m4v`, `webm`, `wmv`, `flv`, `mpg`, `mpeg`, `ts`, `m2ts`, `mts`, `vob`, `ogv`, `ogm`, `rmvb`, `3gp`, `3g2`, `asf`, `divx`.

El titulo se limpia para quitar datos tipicos de release, por ejemplo `720p`, `BluRay`, `x264`, `YIFY`, codecs y grupos.

Despues podes sumarlo al catalogo general:

```powershell
movie-inbox import local_catalog.json --merge catalog.json --json catalog.json --csv catalog.csv
```

Y si queres intentar linkear esos archivos locales con Wikipedia:

```powershell
movie-inbox import local_catalog.json --merge catalog.json --json catalog.json --csv catalog.csv --fetch
```

Para items locales sin URL, `--fetch` busca en Wikipedia usando el titulo limpio y el año detectado. Si encuentra un resultado probable, completa `url`, `wikipedia_title`, `wikidata_id`, imagen, resumen y titulos multilenguaje cuando Wikidata/Wikipedia los expone.

Los items que vengan de links, CSVs o JSONs de la extension entran con `en_catalogo: false` por defecto, salvo que el archivo ya traiga otro valor. Tambien se normalizan los campos personales nuevos: `watched_at`, `rating` y `review`, y los campos de titulos `original_title`, `spanish_title`, `english_title` y `alternative_titles`. Los JSONs viejos con `si`/`no` se siguen leyendo correctamente y se normalizan a booleanos.

Antes de sobrescribir un JSON existente, los scripts actualizan un unico backup automatico junto al archivo con formato `nombre.bak.json`. La siguiente escritura tambien elimina los backups historicos con timestamp creados por versiones anteriores. Para uso continuo en servidor se recomienda SQLite como fuente principal y una exportacion JSON periodica como backup portable.

El campo `kind` ya acepta `pelicula`, `serie`, `anime` y `documental`. Por ahora `serie` identifica el tipo de entrada; temporadas y capitulos quedan para una etapa posterior del modelo.

Cuando se puede resolver un `wikidata_id`, el enriquecimiento intenta completar datos de
obra: año y fechas de estreno, duración en minutos, países, idiomas originales,
productores, compositores, géneros, dirección, guion y reparto. Los campos con más de
un valor se conservan como listas y la duración desconocida permanece vacía, no como
cero minutos.

Durante el merge automatico solo se combinan entradas con una senal fuerte: URL externa compartida, mismo `wikidata_id`, o titulo exacto junto con ano exacto y tipo compatible. Los titulos iguales sin ano quedan pendientes de revision. Si cualquiera de las dos entradas tiene `en_catalogo: true`, el resultado final conserva `en_catalogo: true`.

## Sumar exports a un catalogo general (compatibilidad)

La Bandeja web reemplaza este recorrido para una instancia activa. Estos comandos siguen siendo validos para catalogos JSON independientes o migraciones controladas.

Cuando tengas un export de la extension, por ejemplo `movie-inbox-2026-04-27.csv`, podes sumarlo a tu catalogo general asi:

```powershell
movie-inbox import movie-inbox-2026-04-27.csv --merge catalog.json --json catalog.json --csv catalog.csv
```

Tambien podes guardar el resumen de importacion:

```powershell
movie-inbox import movie-inbox-2026-04-27.csv --merge catalog.json --json catalog.json --csv catalog.csv --log-json import-log.json
```

La deduplicacion se hace por URL normalizada, incluyendo `url`, `wikipedia_url`, `imdb_url` y `filmaffinity_url`. Por ejemplo, ignora diferencias como `www.` o una barra final. Tambien puede combinar mismo titulo exacto, mismo ano y tipo compatible. Cada match automatico del script externo registra en el reporte su motivo y evidencia.

Si queres que los links nuevos de Wikipedia entren enriquecidos:

```powershell
movie-inbox import movie-inbox-2026-04-27.csv --merge catalog.json --json catalog.json --csv catalog.csv --fetch
```

## Interfaz web

El servidor actual se inicia con `movie-inbox serve` y trabaja directamente con SQLite o JSON mediante el mismo contrato de repositorio. En Docker, Compose inicia ese mismo proceso y conserva sus datos en el volumen de la instancia.

### Visor HTML estatico (compatibilidad)

El JSON consolidado puede convertirse en una vista HTML estatica:

```powershell
python scripts/build_viewer.py catalog.json --html catalog-view.html
```

Despues abris `catalog-view.html` en el navegador. La vista incluye buscador, filtros por estado/tipo/fuente, conteo de resultados y tarjetas con imagen/resumen cuando el JSON tiene esa data.

### Servidor nativo

Tambien podes levantar un visor local en Python para mirar uno o varios JSONs exportados por la extension:

```powershell
movie-inbox serve catalog.json
```

O una carpeta de exports:

```powershell
movie-inbox serve exports/*.json --port 8765
```

El comando usa FastAPI sobre Uvicorn con un solo worker. Para mantener compatibilidad, `--write-json` sigue disponible como alias de `--write-catalog`.

Cuando la fuente es JSON, `Actualizar` vuelve a leer el archivo; con SQLite consulta el estado transaccional actual. La portada redirige al login hasta que exista una sesion valida; el menu de cuenta muestra el usuario y el catalogo personal activos y permite cerrar todas las operaciones de esa sesion.

La interfaz separa `Inicio`, `Coleccion`, `Bandeja` y `Club`. `Inicio` propone hasta cuatro recomendaciones diarias estables, formadas solo por obras disponibles que tengan una imagen real, con sinopsis y seleccion manual. El selector `Hoy / Ayer` reemplaza esa misma marquesina y conserva por usuario las dos jornadas mas recientes; no modifica el catalogo. Sus programas combinan pendientes disponibles, faltantes de colecciones seguidas, recuerdos personales incompletos y rutas por director, genero o decada. `Estrenadas un dia como hoy` queda al final de esa programacion, en el quinto lugar cuando estan disponibles los cuatro programas anteriores. Cada sugerencia se calcula con datos locales y no se repite entre secciones; `Random` sigue siendo la accion independiente para explorar sin un criterio fijo. Los accesos desde Inicio abren `Coleccion` con su criterio real aplicado y representado en la URL. `Coleccion` concentra busqueda, filtros rapidos de estado, disponibilidad y tipo, un panel de facetas avanzadas, orden, carga incremental y acceso al CRUD. `Bandeja` alterna entre la curaduria y las importaciones controladas. `Club` alterna entre catalogos compartidos por miembros y colecciones locales que pueden seguirse o copiarse de forma selectiva. `Administrar`, dentro del menu de cuenta del owner, agrupa miembros, resumen, base de datos, salud de fuentes externas, matching y duplicados.

### Importaciones desde la Bandeja

`Bandeja > Importaciones` acepta archivos o texto pegado en formatos TXT, CSV y JSON. El navegador lee el contenido y lo envia como JSON autenticado al mismo origen: nunca transmite una ruta del equipo, no habilita multipart y no permite que el servidor abra un archivo elegido por el usuario. Cada origen admite hasta 8 MiB y 10.000 filas. JSON tiene profundidad limitada y claves duplicadas rechazadas; CSV permite asignar encabezados cuando no coinciden con los nombres reconocidos.

El archivo original no se conserva. La base de instancia guarda solamente las filas normalizadas, un hash y datos minimos del origen en un borrador privado del usuario que expira a las 48 horas. Cada cuenta puede mantener hasta 20 borradores dentro de esa ventana. `local_path`, `local_name` y `local_files` se eliminan siempre. Un `en_catalogo: true` puede conservarse como declaracion importada, pero no crea una vinculacion con archivos del servidor ni reemplaza al scanner.

La previsualizacion clasifica cada fila como `Nueva`, `Presente`, `Revisar` o `Invalida`. Solamente una identidad fuerte, como el mismo ID o la misma URL externa, cuenta como presente. Un titulo parecido queda para revision y no se importa automaticamente al catalogo; las repeticiones dentro del propio origen tambien se bloquean. El matching se vuelve a calcular justo antes de escribir para cubrir cambios ocurridos mientras el borrador estaba abierto.

Todos los usuarios pueden copiar las obras nuevas seleccionadas a su catalogo personal. Antes de confirmar pueden decidir si conservan estado, fecha de vista, puntaje y review. La operacion es idempotente: reintentar el mismo borrador no crea copias. El owner tambien puede convertir las filas validas en una coleccion local privada nueva; esa coleccion no hereda ningun campo personal y no modifica el catalogo. Este incremento no importa hacia colecciones existentes, no ejecuta enriquecimiento externo y no recorre discos.

El visor tiene una consola de busqueda unica. Al tocar `Buscar`, el servidor consulta el
catalogo personal completo por titulo principal, original, espanol, ingles, aliases,
nombres de archivo, IDs y links, ignorando tildes y tolerando una errata en
palabras largas. Descripcion, reparto, genero, tags, direccion y guion no forman parte
del buscador para que una coincidencia incidental de esos campos no se confunda con una
coincidencia de titulo; siguen visibles en la ficha. `Buscar tambien en fuentes externas` agrega Wikipedia, IMDb,
FilmAffinity y Jikan solamente despues de la accion explicita. La consulta, el orden y las
facetas de estado, disponibilidad, tipo, fuente, director, genero, decada, rango de
anos y memoria personal quedan representados en la URL para que Atras y Adelante
restauren la estanteria correcta. Distintas facetas se combinan con `AND`; varios
valores dentro de la misma faceta se combinan con `OR`. Si abriste varios catalogos,
por defecto escribe en el primero resuelto;
podes elegir otro archivo con el nombre compatible `--write-json`:

Las consultas externas se ejecutan en paralelo mediante adaptadores independientes. Los
resultados positivos se guardan durante 15 minutos y una respuesta vacia solamente 30
segundos; una fuente con error no se cachea ni cancela las otras. Las URLs conocidas,
los IDs de IMDb y las consultas `titulo + ano` se interpretan antes de buscar, y cada
fuente ordena sus alternativas por coincidencia de titulo y ano. Wikipedia prioriza la
coincidencia exacta dentro de la consulta amplia y usa la resolucion directa como
respaldo; si falla un idioma conserva los resultados del otro. Los resultados aparecen en estanterias separadas de Wikipedia,
IMDb, FilmAffinity y Jikan apenas responde cada fuente, con seis opciones iniciales, carga
adicional y reintento independiente cuando una consulta falla o supera 10 segundos.
Jikan respeta `Retry-After`; los limites, timeouts y errores 5xx abren una pausa visible.
Si se configuro el indice offline, la misma estanteria distingue su respaldo local y
mantiene la procedencia y atribucion del snapshot. `External DBs`
muestra estado, latencia, cantidad de resultados y errores, ademas de hits, misses y
entradas del cache. Wikipedia devuelve primero datos livianos y completa la metadata de
la entrada elegida recien al agregarla o combinarla.

Los resultados elegidos de IMDb tambien intentan resolverse mediante su ID en
Wikidata/Wikipedia antes de guardarse. Eso permite completar titulo original, titulo en
espanol, titulo en ingles, aliases y fechas de estreno con su precision cuando existen.
Al comparar un resultado externo, el servidor enriquece primero esa opcion y aplica el
mismo ranking sobre todo el catalogo, por lo que aliases o nombres locales que no
coinciden con la consulta inicial siguen pudiendo aparecer antes de crear un duplicado.

TMDb es una integracion distinta de IMDb y permanece desactivada por defecto. La
configuracion opt-in acepta un API Read Access Token unicamente desde un archivo del
servidor mediante `--tmdb-read-access-token-file` o
`MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE`; nunca acepta el secreto como argumento
literal, dato del navegador o campo del catalogo. Con token, el nucleo [F5.1] registra
un adaptador server-side: una busqueda multi separa peliculas/series, un ID IMDb usa
`/find` y el detalle seleccionado agrupa traducciones, aliases, creditos, IDs externos
e imagenes en una sola respuesta ampliada. Sin token, TMDb no aparece en el registry ni
en health y no recibe llamadas. La estanteria, atribucion y operacion de retirada siguen
en [F5.2]-[F5.3]. En Docker se usa el overlay y el procedimiento de
[docs/docker.md](docs/docker.md).

```powershell
movie-inbox serve catalog_wiki_v5.json --write-json catalog_wiki_v5.json
```

Las tarjetas del visor mantienen una proporcion 2:3 estable para poder escanear la coleccion sin saltos de altura. El frente muestra portada, titulo, ano, disponibilidad, estado personal y puntuacion cuando existe. En desktop el reverso tecnico aparece con hover o foco; hacer click o tap en cualquier punto abre la ficha completa. En movil la interaccion no depende del giro ni del hover.

En movil, la navegacion principal pasa a una barra inferior con accesos tactiles a `Inicio`, `Coleccion`, `Bandeja`, `Club` y `Random`; la cabecera conserva la marca y concentra las opciones secundarias en el menu de cuenta. La coleccion y el Club usan estanterias de dos columnas, controles compactos y margenes compatibles con las areas seguras del dispositivo.

El resumen muestra cuantas entradas tienen posibles duplicados por URL externa o por titulo y ano. `Ver duplicadas` filtra esas entradas, cada card lleva un badge y el detalle explica la coincidencia. Al agregar desde una fuente externa, el catalogo editable se revisa primero por URL y por todos sus titulos conocidos antes de insertar.

La busqueda local conserva las cards principales de la estanteria y renderiza 36 entradas por tanda. Los resultados externos se muestran como cards compactas, de a 6, con `Cargar mas` cuando quedan coincidencias. Su descripcion ocupa como maximo dos lineas y `Ver mas` abre el texto completo. Las cards externas priorizan `Agregar`, `Comparar` y `Detalle`; las cards locales auxiliares aparecen unicamente despues de elegir `Comparar` o `Buscar link`.

Los items agregados manualmente entran con `status: to_watch` y `en_catalogo: false`.

Antes de agregar, el visor revisa si ya existe una entrada con titulo normalizado y año compatible. Si encuentra una posible coincidencia, muestra opciones para combinar, agregar igual o cancelar. Al combinar, conserva datos locales como `en_catalogo`, `local_name` y `local_path`, y suma el link/metadata del resultado elegido.

Cuando el detector automatico no encuentra el duplicado, en un resultado externo podes usar `Comparar`: el visor busca la entrada existente y abre la misma mesa de comparacion usada por la Bandeja. Cada diferencia permite conservar A, usar B o combinar listas; archivos locales y disponibilidad se preservan, mientras que conflictos de estado, fecha, puntaje, review o notas exigen una eleccion explicita.

Cada tarjeta tiene `Buscar link`. Ese boton usa automaticamente el titulo/año de esa entrada, busca en Wikipedia, IMDb, FilmAffinity y Jikan, y deja lista la comparacion contra esa misma entrada.

El panel lateral tiene accion `Eliminar`. Antes de borrar, el navegador pide confirmacion porque se modifica directamente el catalogo elegido.

Cada tarjeta tambien permite cambiar rapidamente entre `to_watch` y `watched` con `Marcar vista` / `Marcar pendiente`. Al marcar una entrada como vista se guarda `watched_at` con la fecha local del dia.

El panel lateral incluye el registro personal para editar `watched_at`, `rating` de 0 a 10 y `review`. Los controles de visibilidad de puntaje y review permiten heredar el default del usuario o definir un override para esa obra. Por defecto las entradas nuevas tienen `rating: 0`, `review: ""` y `watched_at: ""`.

Marcar una entrada como pendiente no borra `watched_at`; si queres corregir o limpiar esa fecha, se hace desde el registro personal del panel lateral.

Cuando existen datos enriquecidos, la tarjeta muestra genero y director de forma compacta; el panel lateral muestra genero, director, guionistas y reparto con mas espacio. Esos campos no forman parte del buscador principal, para que una coincidencia incidental (por ejemplo, un actor cuyo nombre contiene la consulta) no se confunda con una coincidencia de titulo.

La seccion `Metadata` del detalle permite corregir titulos, año, descripcion, genero, direccion, guion y reparto. Cada campo guarda su procedencia en `metadata_sources`; los datos historicos migrados se marcan como procedencia inferida. Al activar `Bloquear`, el campo entra en `locked_fields` y los merges externos posteriores no pueden modificarlo.

El panel lateral permite cambiar manualmente `en_catalogo` con `Marcar catalogo` / `Quitar catalogo`, sin tocar el estado `to_watch` o `watched`.

El panel lateral permite editar el tipo con un selector: `pelicula`, `serie`, `anime` o `documental`. Las entradas nuevas se crean como `pelicula` por defecto.

Al combinar un resultado externo se guarda el link especifico de la fuente (`wikipedia_url`, `imdb_url`, `filmaffinity_url` o `myanimelist_url`) sin perder el link principal que ya tuviera la entrada.

La navegacion principal incluye una `Bandeja` para trabajar sin mezclar ese proceso con la exploracion, con tres modos. `Curaduria` reune pendientes, posibles duplicados y entradas `Sin referencia` externa; tambien conserva una cola separada de casos pospuestos. Las decisiones `Posponer`, `No son duplicados`, `No requiere referencia` y los merges revisados quedan en `Actividad`, desde donde pueden deshacerse. `Inventario` (el scanner administrado por la instancia, marcado `Admin` porque no modifica tu catalogo personal) organiza su cola por causa y confianza en vez de una lista plana: `Falta identidad`, `Conflicto de año/tipo`, `Probable ficha existente` o `Sin señales`. Cuando no encuentra una candidata segura lo dice explicitamente (`No encontramos una coincidencia segura`, no una ausencia comprobada) y ofrece buscar en tu catalogo antes de dar de alta una ficha nueva; cada candidata muestra ademas su procedencia (`En tu catalogo` / `Catalogo compartido`). `Importaciones` conserva borradores temporales y muestra la clasificacion antes de cualquier escritura.

Una franja de alcance persistente acompaña toda la decision en Curaduria e Inventario, marcando cual de tres estados afecta lo que estas por confirmar: `Archivo fisico`, `Identidad compartida` o `Ficha en tu catalogo`. Disponibilidad se presenta siempre igual en Coleccion, la ficha, Curaduria y el comparador de fusion: `Disponible` (o no) con su procedencia real — inventario verificado, declaracion manual, o ambas — nunca como un flag manual crudo.

El historial conserva hasta 50 operaciones y puede funcionar como `Persistente` o `Solo esta sesion`. El modo persistente usa un unico archivo lateral `.<catalogo>.curation-history.json`, separado del esquema portable y de las exportaciones. `Limpiar historial` elimina esos snapshots con confirmacion y no modifica el catalogo. Si una obra fue editada despues de una operacion, Deshacer se bloquea para no sobrescribir el cambio posterior.

La vista `Administrar` muestra cuantas entradas estan vistas, cuantas quedan por ver y cuantas tienen links o portada. Tambien expone el catalogo editable, los archivos cargados y el estado de Wikipedia, IMDb, FilmAffinity y Jikan. Los accesos de depuracion abren directamente la cola correspondiente de la Bandeja.

`Random` abre una ficha al azar sin modificar el JSON. Su casilla permite limitar la eleccion a obras disponibles en catalogo. Dentro de `Coleccion`, `Mezclar vista` cambia solamente el orden visual de los resultados actuales y `Restablecer orden` recupera el orden elegido.

Las imagenes del visor se sirven desde un cache local persistente. Una portada visible conserva su placeholder hasta que el navegador confirma la carga y entonces aparece con una transicion breve; las primeras cards de la vista y la ficha abierta tienen prioridad sobre el trabajo de fondo. La primera peticion autenticada a un catalogo registra sus portadas y activa un unico worker global que descarga de a una cada 3 segundos. El worker tambien incorpora solamente las colecciones o catalogos compartidos que alguien abre, deduplica URLs entre usuarios y continua mientras el proceso del servidor siga activo. No bloquea `/api/items` ni realiza enriquecimiento de metadata.

Cada descarga se valida con la misma allowlist y proteccion SSRF del proxy, se escribe de forma atomica y se reintenta con espera creciente ante errores temporales. El limite predeterminado es 5 MB por imagen y 512 MB en total; al alcanzarlo se eliminan primero los archivos menos usados recientemente. `Administrar > Base de datos` muestra el avance del catalogo personal y, para el owner, un resumen agregado sin revelar datos privados de otros usuarios.

En Docker el cache vive en `/var/lib/movie-inbox/image-cache`, dentro del volumen nombrado `movie-inbox-data`. Sobrevive a reinicios, `docker compose down` y recreaciones por actualizacion. Se elimina solamente al borrar ese volumen, por ejemplo con `docker compose down --volumes`, por lo que ese flag no debe usarse durante una actualizacion normal. El limite puede cambiarse con `MOVIE_INBOX_IMAGE_CACHE_MB`, la precarga con `MOVIE_INBOX_IMAGE_WARM_MODE=after-access|off` y la pausa con `MOVIE_INBOX_IMAGE_WARM_INTERVAL_SECONDS` en `.env`.

```powershell
movie-inbox cache info --dir .catalog-cache/images
movie-inbox cache prune --dir .catalog-cache/images --max-total-mb 512
movie-inbox cache clear --dir .catalog-cache/images
```

Se puede desactivar todo el cache con `--no-image-cache`, desactivar solamente la precarga con `--image-cache-warm-mode off`, ajustar su ritmo con `--image-cache-warm-interval-seconds`, cambiar la carpeta con `--image-cache-dir`, limitar cada imagen con `--image-cache-max-mb` o el total con `--image-cache-total-mb`. El proxy acepta JPEG, PNG, WebP, GIF y AVIF provenientes de los hosts conocidos de Wikimedia, IMDb, FilmAffinity y el CDN de MyAnimeList. Un proveedor adicional debe habilitarse de forma explicita repitiendo `--image-host nombre.example`.

Para intentar completar links automaticamente desde la terminal:

```powershell
movie-inbox match catalogv2.json --json catalogv3_links.json --report external-links-report.json --limit 100
```

El comando busca en Wikipedia, IMDb, FilmAffinity y Jikan para entradas sin link, combina automaticamente solo matches de alta confianza y deja en el reporte los casos dudosos para revisar en el visualizador.

Un titulo exacto sin ano, con ano distinto o con tipo incompatible nunca se combina automaticamente. Esos candidatos aparecen en `needs_review` con score, motivo y evidencia para decidirlos desde el visor.

## Esquema versionado y migracion

Las escrituras nuevas usan `schema_version: 8` y guardan las entradas dentro de `items`.
Los catalogos legacy y las versiones 1 a 6 pasan por migraciones explicitas antes de
usarse. Una version futura, una raiz mal formada o una fila invalida se rechazan y nunca
se interpretan como catalogo vacio ni se reescriben silenciosamente. Cada obra puede
tener varios archivos fisicos en `local_files`; `local_name` y `local_path` se mantienen
por compatibilidad. La version 3 sumo procedencia y bloqueos de metadata. La version 4
agrego identidad incremental a cada archivo. La version 5 agrego decisiones persistentes
de curaduria. La version 6 incorpora `release_dates`, conservando fecha, precision, pais,
tipo de estreno, fuente y la marca de fecha principal.
La versión 7 incorpora `duration_minutes`, `countries`, `original_languages`,
`producers` y `composers`; los catálogos v6 reciben `null` y listas vacías al migrar,
sin confundir ausencia de datos con una duración de cero minutos.

Para convertir un catalogo completo sin reemplazar el original:

```powershell
movie-inbox migrate catalogv3_links.json --json catalogv6.json
```

Las escrituras del visor y del importador son atomicas: primero se completa un archivo temporal y luego se reemplaza el JSON. El visor bloquea cada catalogo durante operaciones de escritura concurrentes y conserva un unico backup automatico reemplazable.

## Seguridad del visor web

El visor exige una cuenta local y guarda solamente hashes `scrypt` de las contrasenas. Las sesiones usan tokens aleatorios opacos: el navegador recibe el token en una cookie `HttpOnly`, `SameSite=Strict` y `Secure` cuando el origen publico usa HTTPS; SQLite conserva unicamente su hash y una expiracion absoluta. El login devuelve errores genericos y limita intentos repetidos en memoria.

Ademas, el visor genera un token anti-CSRF en cada inicio y lo exige junto con la sesion. FastAPI valida hosts confiables y, para escrituras y login, un origen exacto; acepta solamente `Content-Type: application/json`, limita el cuerpo a 2 MB y devuelve estados HTTP 4xx/5xx. El proxy de imagenes exige sesion, limita los destinos a una allowlist exacta, valida sus IPs y vuelve a aplicar ambas reglas en cada redireccion. SVG remoto no se acepta. La documentacion OpenAPI publica esta deshabilitada y `/healthz` no expone datos.

Detras de Nginx se indica el origen externo con `--public-origin` y se limita la confianza de headers reenviados con `--forwarded-allow-ips`. La aplicacion autentica usuarios, pero HTTPS y una VPN siguen siendo recomendables para una instancia personal expuesta fuera de la red local.

## Pruebas

La suite usa `unittest` de la libreria standard y cubre migraciones, repositorios JSON/SQLite, modelos, matching conservador, limites entre capas y seguridad HTTP/SSRF:

```powershell
py -m unittest discover -s tests -v
```

Los checks completos, incluidos Ruff, mypy sobre el dominio, compilacion, tests y
`git diff --check`, se ejecutan localmente con:

```powershell
scripts\check.ps1
```

Si Windows bloquea la ejecucion de scripts, se puede habilitar solamente para esa corrida:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\check.ps1"
```

En Linux o en el servidor se usa `bash scripts/check.sh`. El workflow `.github/workflows/tests.yml` corre la misma validacion en Linux/Python 3.11 y Windows/Python 3.14 en cada push a `master` y en cada pull request. Jobs adicionales construyen el wheel en un entorno limpio y prueban en Chromium el acceso autenticado, el teclado, los dialogos y los viewports de escritorio y movil. CI valida una revision; no despliega ni accede al catalogo personal.

La prueba de navegador es opcional en desarrollo porque descarga Chromium:

```powershell
py -m pip install -e ".[test,browser-test]"
py -m playwright install chromium
py -m unittest discover -s tests/browser -p "test_*.py" -v
```

## Despliegue en servidor

El checkout contiene codigo, no datos. En un servidor, el catalogo y `instance.db` deben vivir fuera del repo, por ejemplo en `/var/lib/movie-inbox/`, y los backups en otra ruta persistente. Nginx apunta al proceso web que escucha en loopback; nunca apunta al directorio Git ni sirve ninguna base directamente.

El despliegue reproducible con una instancia nueva, importacion inicial y medios de solo lectura esta documentado en [docs/docker.md](docs/docker.md). El despliegue nativo, los flags de proxy y las plantillas de `systemd`/Nginx estan en [docs/deployment.md](docs/deployment.md). La estructura de almacenamiento y la migracion reversible estan en [docs/storage.md](docs/storage.md). La secuencia de versiones vive en [docs/roadmap.md](docs/roadmap.md) y el gate de busqueda de `v0.3.0` en [docs/search-quality.md](docs/search-quality.md). En Docker el proceso escucha dentro del contenedor, pero el puerto del host permanece publicado en loopback; Nginx o una VPN controlan el acceso externo.

## Limpiar titulos y linkear con Wikipedia

Para dumps locales con nombres tipo `The English Patient 1996 720p BluRay x264 YIFY`, primero conviene limpiar titulos y normalizar estados:

```powershell
movie-inbox enrich catalogv2.json --json catalog_clean.json --csv catalog_clean.csv --report enrich-report.json
```

Eso separa el año cuando puede, limpia datos de release/calidad/codecs/grupos y cambia `status: cataloged` a `status: to_watch`. El campo `en_catalogo` no se toca: una pelicula puede tener `en_catalogo: true` y a la vez `status: to_watch`.

Para intentar linkear con Wikipedia:

```powershell
movie-inbox enrich catalog_clean.json --json catalog_wiki.json --csv catalog_wiki.csv --fetch-wikipedia --report wiki-report.json
```

Si queres probar de a poco:

```powershell
movie-inbox enrich catalog_clean.json --json catalog_wiki_sample.json --fetch-wikipedia --limit 100 --report wiki-sample-report.json
```

El reporte lista cuantas entradas pudo linkear y cuales quedaron sin match. Para 1800 entradas conviene revisar primero una muestra antes de correr todo.

El enriquecedor usa tres caminos: completa metadata si ya hay URL de Wikipedia, resuelve IDs de IMDb `tt...` via Wikidata cuando puede, y finalmente busca por titulo limpio en Wikipedia en ingles y espanol.

Para corridas largas, el comando guarda progreso cada 25 consultas por defecto y si lo interrumpis con Ctrl+C guarda salida parcial. Evita escribir encima del catalogo base durante pruebas:

```powershell
movie-inbox enrich catalog_clean.json --json catalog_wiki_v5.json --csv catalog_wiki_v5.csv --fetch-wikipedia --report wiki-report-v5.json --progress-every 25
```

El enriquecedor acepta tanto JSON como SQLite. Para pruebas largas sigue siendo prudente escribir a una salida distinta y revisar el reporte antes de reemplazar la fuente principal.

## Extension de Chrome (experimental)

1. Abrir `chrome://extensions`.
2. Activar "Developer mode".
3. Click en "Load unpacked".
4. Elegir la carpeta `chrome-extension`.

La extension permite:

- guardar la pestana actual
- agregar tipo, estado, tags y notas
- exportar CSV o JSON
- activar una exportacion automatica cada N dias

Nota: Chrome puede pedir confirmacion o guardar los archivos en la carpeta de descargas segun tu configuracion.

## Estado de compatibilidad

La aplicacion web, SQLite, Docker, la Bandeja y el scanner administrado son el camino principal. Estas piezas permanecen en el repositorio porque todavia sirven para migraciones o capturas puntuales, pero no gobiernan el flujo self-hosted:

- visor HTML estatico (`scripts/build_viewer.py`)
- scanner Bash por archivo de configuracion (`scripts/scan_video_catalog.sh`)
- extension de Chrome basada en exportaciones manuales

Los wrappers de v0.1 que solo llamaban al mismo comando del paquete
(`txt_to_catalog.py`, `scan_library.py`, `view_catalog.py`, `enrich_catalog.py`,
`match_external_links.py`, `migrate_catalog.py` → `movie-inbox
import|scan|serve|enrich|match|migrate`, respectivamente) y los 13 shims de import
`catalog_*.py` (compatibilidad con nombres de modulo planos pre-paquete) ya no viven en
este repositorio: asumian acceso directo del host a rutas de catalogo y biblioteca, algo
que no encaja con una instancia Docker, donde el camino es la app web + `movie-inbox`
**dentro** del contenedor (`docker compose exec app movie-inbox ...`), no un script
suelto apuntando a una ruta que el contenedor puede no montar igual. Se movieron —no se
borraron— a `codigoLegacy/` en el checkout local, ignorado por Git
(`.gitignore`); quien todavia los necesite los sigue teniendo a mano, pero no forman
parte de lo que se clona, se publica en un release ni se ejecuta en CI o Docker.

Temporadas y episodios, sincronizacion directa de la extension y una app Kotlin siguen siendo lineas futuras.
