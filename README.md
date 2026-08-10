# Movie Inbox

Pequena base para convertir una lista desordenada de links de peliculas/series en datos mas utiles.

## Estado del proyecto

La version candidata actual es **v0.2.0-rc1**. Movie Inbox funciona como un gestor local de catalogo con almacenamiento JSON o SQLite: importa listas y archivos, consulta fuentes externas, detecta duplicados y permite administrar disponibilidad, estado de visualizacion, puntajes y reviews desde una interfaz web con autenticacion local.

El catalogo usa esquemas versionados. JSON sigue siendo el formato legible y portable de intercambio y backup; SQLite puede usarse como fuente de verdad transaccional. Los catalogos personales, reportes, caches y backups se mantienen fuera de Git. Las capacidades de cada version estan resumidas en [CHANGELOG.md](CHANGELOG.md).

El gate reproducible de pruebas y aceptacion en un servidor real esta documentado en [docs/release-checklist.md](docs/release-checklist.md).

El codigo principal vive en el paquete instalable `src/movie_inbox`. Los archivos de `scripts/` son lanzadores compatibles con los comandos usados en v0.1.

Incluye:

- `scripts/txt_to_catalog.py`: lee un `.txt` con URLs o titulos y genera JSON y/o CSV.
- `scripts/scan_video_catalog.sh`: recorre una carpeta local de peliculas y genera JSON desde archivos de video.
- `scripts/scan_library.py`: sincroniza incrementalmente una biblioteca de video con el catalogo principal.
- `scripts/view_catalog.py`: servidor local con visor, CRUD, busqueda y detalle del catalogo.
- `src/movie_inbox/domain/`: modelos, normalizacion, matching y reglas de merge.
- `src/movie_inbox/application/`: casos de uso compartidos por el visor, importadores y scanner.
- `src/movie_inbox/infrastructure/`: esquemas, repositorios JSON/SQLite y exportacion.
- `src/movie_inbox/external/`: clientes separados para Wikipedia, Wikidata, IMDb y FilmAffinity.
- `src/movie_inbox/web/`: aplicacion FastAPI, servidor Uvicorn, proxy seguro de imagenes y assets estaticos.
- `catalog.schema.json`: contrato JSON versionado del catalogo.
- `chrome-extension/`: extension de Chrome para guardar la pestana actual con datos minimos y exportar CSV/JSON.
- `PRODUCT.md` y `DESIGN.md`: contratos de producto, terminologia y lenguaje visual del visor.

## Instalacion y comandos

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
movie-inbox migrate catalog-viejo.json --json catalog-v5.json
movie-inbox enrich catalog.json --json catalog-enriquecido.json
movie-inbox match catalog.json --json catalog-con-links.json
movie-inbox db import catalog.json --db data/movie-inbox.db
movie-inbox db export data/movie-inbox.db --json backups/catalog.json
movie-inbox cache info --dir .catalog-cache/images
```

En Windows, si la carpeta `Scripts` de Python no esta en `PATH`, usa la forma equivalente:

```powershell
py -m movie_inbox serve catalog.json
```

El ejecutable suele quedar en `%LocalAppData%\Programs\Python\Python314\Scripts`. Agregar esa carpeta al `PATH` permite invocar directamente `movie-inbox` desde una terminal nueva.

Los comandos `py scripts/txt_to_catalog.py ...`, `py scripts/scan_library.py ...` y `py scripts/view_catalog.py ...` siguen funcionando y llaman a la misma implementacion del paquete.

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

## SQLite y backups JSON

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

SQLite normaliza obras, aliases, IDs externos, archivos locales, tags y procedencia. Las actualizaciones frecuentes son granulares: estado y fecha se actualizan directamente, mientras que metadata y relaciones reconstruyen solamente la parte modificada del item. Las operaciones batch conservan una transaccion unica pero sincronizan diferencias en vez de reescribir todas las relaciones. Tambien reserva tablas para temporadas y episodios, aunque esa funcionalidad todavia no forma parte del dominio ni de la interfaz. Los archivos `.db`, `.sqlite`, sus journals y `data/` se ignoran en Git.

## Uso del script

Crear un archivo, por ejemplo `links.txt`:

```txt
https://en.wikipedia.org/wiki/Blade_Runner
https://www.imdb.com/title/tt0083658/
The English Patient 1996
Mile End Kicks
```

Generar JSON y CSV:

```powershell
python scripts/txt_to_catalog.py links.txt --json catalog.json --csv catalog.csv
```

El script imprime un resumen con:

- filas/URLs/items leidos
- duplicados dentro del archivo de entrada
- items agregados
- items finales
- lista corta de URLs/items duplicados

Intentar completar metadata desde las paginas:

```powershell
python scripts/txt_to_catalog.py links.txt --json catalog.json --csv catalog.csv --fetch
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
raices que Movie Inbox puede leer al iniciar el visor. La aplicacion no ofrece un
explorador remoto ni acepta rutas fuera de esta lista:

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

El inventario fisico pertenece a la instancia. Una coincidencia fuerte aporta
disponibilidad verificada a los catalogos de todos los usuarios sin copiar obras ni
cambiar `status`, `watched_at`, `rating` o `review`. La declaracion manual de
`en_catalogo` se conserva por separado: retirar una senal no elimina la otra. Los
miembros reciben solamente el estado agregado; rutas, nombres de archivo y huellas son
exclusivos del owner.

Archivos nuevos, titulos sin ano y coincidencias ambiguas aparecen en
`Bandeja > Scanner`. Confirmar una identidad no agrega automaticamente la obra a ningun
catalogo personal. El comparador muestra titulo, ano, tipo, aliases, similitud y las
fuentes externas ya disponibles antes de vincular el archivo. `Omitir este archivo` no
borra datos ni toca el disco: retira el caso mientras conserve la misma huella y exige
confirmacion porque todavia no puede restaurarse desde la interfaz. Si un disco
desaparece o la proporcion de bajas supera el limite configurado, se conserva el ultimo
inventario valido.

Las sugerencias se construyen con el catalogo del owner y con catalogos que sus
miembros hayan compartido de forma explicita. Los catalogos privados nunca se usan como
fuente de candidatos. El matching indexa titulos y terminos al comenzar cada recorrido,
por lo que no necesita comparar cada archivo contra todas las obras de la instancia.

### Scanner Python incremental

Para un servidor o una tarea programada conviene usar el scanner Python. `scanner.example.json` muestra la configuracion de una biblioteca; las rutas relativas se resuelven desde la carpeta donde esta ese archivo.

El primer recorrido debe ser una simulacion:

```powershell
py scripts/scan_library.py --config scanner.json --dry-run --report scanner-report.json
```

El reporte separa archivos sin cambios, modificados, movidos, asociados a entradas existentes, entradas nuevas y casos `needs_review`. Si el resultado es correcto, se aplica sobre el JSON:

```powershell
py scripts/scan_library.py --config scanner.json --apply --report scanner-report.json
```

Para detectar cambios periodicamente en el mismo proceso:

```powershell
py scripts/scan_library.py --config scanner.json --apply --watch --interval 300 --report scanner-report.json
```

La CLI legacy sigue disponible para reconciliar directamente un unico catalogo. Recorre subcarpetas y guarda estado liviano en `.catalog-state`. Usa el mismo parser y motor de huellas que el scanner administrado para evitar reglas divergentes. Un movimiento dentro del disco conserva la entrada; una coincidencia unica por titulo, ano y tipo se asocia al item existente; una coincidencia ambigua no se aplica y queda en `needs_review`.

Si el disco no existe o no esta montado, el scanner aborta antes de modificar el catalogo. Tambien compara el recorrido con el ultimo estado y omite bajas cuando desaparece mas del porcentaje configurado en `max_missing_ratio` (50% por defecto), lo que cubre puntos de montaje que siguen existiendo pero aparecen vacios. Si hubo errores parciales de lectura, actualiza lo que pudo ver pero no marca archivos ausentes ni reemplaza el ultimo estado completo. El scanner solo administra `local_files` y la disponibilidad agregada `en_catalogo`: no modifica `status`, `watched_at`, `rating` ni `review`, y no consulta fuentes externas durante el recorrido.

### Export rapido con Bash

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
python scripts/txt_to_catalog.py local_catalog.json --merge catalog.json --json catalog.json --csv catalog.csv
```

Y si queres intentar linkear esos archivos locales con Wikipedia:

```powershell
python scripts/txt_to_catalog.py local_catalog.json --merge catalog.json --json catalog.json --csv catalog.csv --fetch
```

Para items locales sin URL, `--fetch` busca en Wikipedia usando el titulo limpio y el año detectado. Si encuentra un resultado probable, completa `url`, `wikipedia_title`, `wikidata_id`, imagen, resumen y titulos multilenguaje cuando Wikidata/Wikipedia los expone.

Los items que vengan de links, CSVs o JSONs de la extension entran con `en_catalogo: false` por defecto, salvo que el archivo ya traiga otro valor. Tambien se normalizan los campos personales nuevos: `watched_at`, `rating` y `review`, y los campos de titulos `original_title`, `spanish_title`, `english_title` y `alternative_titles`. Los JSONs viejos con `si`/`no` se siguen leyendo correctamente y se normalizan a booleanos.

Antes de sobrescribir un JSON existente, los scripts actualizan un unico backup automatico junto al archivo con formato `nombre.bak.json`. La siguiente escritura tambien elimina los backups historicos con timestamp creados por versiones anteriores. Para uso continuo en servidor se recomienda SQLite como fuente principal y una exportacion JSON periodica como backup portable.

El campo `kind` ya acepta `pelicula`, `serie`, `anime` y `documental`. Por ahora `serie` identifica el tipo de entrada; temporadas y capitulos quedan para una etapa posterior del modelo.

Cuando se puede resolver un `wikidata_id`, el enriquecimiento intenta completar datos de obra: `genres`, `directors`, `writers`, `cast` y `year`.

Durante el merge automatico solo se combinan entradas con una senal fuerte: URL externa compartida, mismo `wikidata_id`, o titulo exacto junto con ano exacto y tipo compatible. Los titulos iguales sin ano quedan pendientes de revision. Si cualquiera de las dos entradas tiene `en_catalogo: true`, el resultado final conserva `en_catalogo: true`.

## Sumar exports a un catalogo general

Cuando tengas un export de la extension, por ejemplo `movie-inbox-2026-04-27.csv`, podes sumarlo a tu catalogo general asi:

```powershell
python scripts/txt_to_catalog.py movie-inbox-2026-04-27.csv --merge catalog.json --json catalog.json --csv catalog.csv
```

Tambien podes guardar el resumen de importacion:

```powershell
python scripts/txt_to_catalog.py movie-inbox-2026-04-27.csv --merge catalog.json --json catalog.json --csv catalog.csv --log-json import-log.json
```

La deduplicacion se hace por URL normalizada, incluyendo `url`, `wikipedia_url`, `imdb_url` y `filmaffinity_url`. Por ejemplo, ignora diferencias como `www.` o una barra final. Tambien puede combinar mismo titulo exacto, mismo ano y tipo compatible. Cada match automatico del script externo registra en el reporte su motivo y evidencia.

Si queres que los links nuevos de Wikipedia entren enriquecidos:

```powershell
python scripts/txt_to_catalog.py movie-inbox-2026-04-27.csv --merge catalog.json --json catalog.json --csv catalog.csv --fetch
```

## Visualizar el catalogo

El JSON consolidado puede convertirse en una vista HTML estatica:

```powershell
python scripts/build_viewer.py catalog.json --html catalog-view.html
```

Despues abris `catalog-view.html` en el navegador. La vista incluye buscador, filtros por estado/tipo/fuente, conteo de resultados y tarjetas con imagen/resumen cuando el JSON tiene esa data.

Tambien podes levantar un visor local en Python para mirar uno o varios JSONs exportados por la extension:

```powershell
python scripts/view_catalog.py catalog.json
```

O una carpeta de exports:

```powershell
python scripts/view_catalog.py exports/*.json --port 8765
```

El comando usa FastAPI sobre Uvicorn con un solo worker. Para mantener compatibilidad, `--write-json` sigue disponible como alias de `--write-catalog`.

Este visor relee los archivos cada vez que apretas "Actualizar", asi que sirve para ir tirando exports nuevos de Chrome y verlos sin regenerar nada. La portada redirige al login hasta que exista una sesion valida; el menu de cuenta muestra el usuario y el catalogo personal activos y permite cerrar todas las operaciones de esa sesion.

La interfaz separa `Inicio`, `Coleccion`, `Bandeja` y `Club`. `Inicio` esta orientado al descubrimiento y muestra un spotlight pausable junto con una seleccion breve de entradas disponibles. `Coleccion` concentra busqueda, filtros, orden, carga incremental y acceso al CRUD. `Bandeja` alterna entre la curaduria y las importaciones controladas. `Club` alterna entre catalogos compartidos por miembros y colecciones locales que pueden seguirse o copiarse de forma selectiva. `Administrar`, dentro del menu de cuenta del owner, agrupa miembros, resumen, base de datos, salud de fuentes externas, matching y duplicados.

### Importaciones desde la Bandeja

`Bandeja > Importaciones` acepta archivos o texto pegado en formatos TXT, CSV y JSON. El navegador lee el contenido y lo envia como JSON autenticado al mismo origen: nunca transmite una ruta del equipo, no habilita multipart y no permite que el servidor abra un archivo elegido por el usuario. Cada origen admite hasta 8 MiB y 10.000 filas. JSON tiene profundidad limitada y claves duplicadas rechazadas; CSV permite asignar encabezados cuando no coinciden con los nombres reconocidos.

El archivo original no se conserva. La base de instancia guarda solamente las filas normalizadas, un hash y datos minimos del origen en un borrador privado del usuario que expira a las 48 horas. Cada cuenta puede mantener hasta 20 borradores dentro de esa ventana. `local_path`, `local_name` y `local_files` se eliminan siempre. Un `en_catalogo: true` puede conservarse como declaracion importada, pero no crea una vinculacion con archivos del servidor ni reemplaza al scanner.

La previsualizacion clasifica cada fila como `Nueva`, `Presente`, `Revisar` o `Invalida`. Solamente una identidad fuerte, como el mismo ID o la misma URL externa, cuenta como presente. Un titulo parecido queda para revision y no se importa automaticamente al catalogo; las repeticiones dentro del propio origen tambien se bloquean. El matching se vuelve a calcular justo antes de escribir para cubrir cambios ocurridos mientras el borrador estaba abierto.

Todos los usuarios pueden copiar las obras nuevas seleccionadas a su catalogo personal. Antes de confirmar pueden decidir si conservan estado, fecha de vista, puntaje y review. La operacion es idempotente: reintentar el mismo borrador no crea copias. El owner tambien puede convertir las filas validas en una coleccion local privada nueva; esa coleccion no hereda ningun campo personal y no modifica el catalogo. Este incremento no importa hacia colecciones existentes, no ejecuta enriquecimiento externo y no recorre discos.

El visor tiene una consola de busqueda unica. Cada consulta filtra directamente `La coleccion`, sin repetir las mismas obras en una segunda lista local. `Buscar tambien en fuentes externas` agrega resultados de Wikipedia, IMDb y FilmAffinity solamente despues de tocar `Buscar` o presionar Enter. La consulta, los filtros y el orden quedan representados en la URL para que Atras y Adelante restauren la estanteria correcta. Si abriste varios catalogos, por defecto escribe en el primero resuelto; podes elegir otro archivo con el nombre compatible `--write-json`:

Las consultas externas se ejecutan en paralelo mediante adaptadores independientes y se guardan durante 15 minutos en un cache de memoria. Un error en una fuente no cancela las otras. `External DBs` muestra estado, latencia, cantidad de resultados y errores por fuente, ademas de hits, misses y entradas del cache. Wikipedia devuelve primero datos livianos para mostrar resultados rapido y completa la metadata de la entrada elegida recien al agregarla o combinarla.

Los resultados elegidos de IMDb tambien intentan resolverse mediante su ID en Wikidata/Wikipedia antes de guardarse. Eso permite completar titulo original, titulo en espanol, titulo en ingles y aliases de otros idiomas cuando existen. La busqueda local ignora tildes y tolera una errata de un caracter en palabras largas.

```powershell
python scripts/view_catalog.py catalog_wiki_v5.json --write-json catalog_wiki_v5.json
```

Las tarjetas del visor mantienen una proporcion 2:3 estable para poder escanear la coleccion sin saltos de altura. El frente muestra portada, titulo, ano, disponibilidad, estado personal y puntuacion cuando existe. En desktop el reverso tecnico aparece con hover o foco; hacer click o tap en cualquier punto abre la ficha completa. En movil la interaccion no depende del giro ni del hover.

En movil, la navegacion principal pasa a una barra inferior con accesos tactiles a `Inicio`, `Coleccion`, `Bandeja`, `Club` y `Random`; la cabecera conserva la marca y concentra las opciones secundarias en el menu de cuenta. La coleccion y el Club usan estanterias de dos columnas, controles compactos y margenes compatibles con las areas seguras del dispositivo.

El resumen muestra cuantas entradas tienen posibles duplicados por URL externa o por titulo y ano. `Ver duplicadas` filtra esas entradas, cada card lleva un badge y el detalle explica la coincidencia. Al agregar desde una fuente externa, el catalogo editable se revisa primero por URL y por todos sus titulos conocidos antes de insertar.

La busqueda local conserva las cards principales de la estanteria y renderiza 36 entradas por tanda. Los resultados externos se muestran como cards compactas, de a 6, con `Cargar mas` cuando quedan coincidencias. Su descripcion ocupa como maximo dos lineas y `Ver mas` abre el texto completo. Las cards externas priorizan `Agregar`, `Comparar` y `Detalle`; las cards locales auxiliares aparecen unicamente despues de elegir `Comparar` o `Buscar link`.

Los items agregados manualmente entran con `status: to_watch` y `en_catalogo: false`.

Antes de agregar, el visor revisa si ya existe una entrada con titulo normalizado y año compatible. Si encuentra una posible coincidencia, muestra opciones para combinar, agregar igual o cancelar. Al combinar, conserva datos locales como `en_catalogo`, `local_name` y `local_path`, y suma el link/metadata del resultado elegido.

Cuando el detector automatico no encuentra el duplicado, en un resultado externo podes usar `Comparar`: el visor busca la entrada existente y abre la misma mesa de comparacion usada por la Bandeja. Cada diferencia permite conservar A, usar B o combinar listas; archivos locales y disponibilidad se preservan, mientras que conflictos de estado, fecha, puntaje, review o notas exigen una eleccion explicita.

Cada tarjeta tiene `Buscar link`. Ese boton usa automaticamente el titulo/año de esa entrada, busca en Wikipedia, IMDb y FilmAffinity, y deja lista la comparacion contra esa misma entrada.

El panel lateral tiene accion `Eliminar`. Antes de borrar, el navegador pide confirmacion porque se modifica directamente el catalogo elegido.

Cada tarjeta tambien permite cambiar rapidamente entre `to_watch` y `watched` con `Marcar vista` / `Marcar pendiente`. Al marcar una entrada como vista se guarda `watched_at` con la fecha local del dia.

El panel lateral incluye el registro personal para editar `watched_at`, `rating` de 0 a 10 y `review`. Los controles de visibilidad de puntaje y review permiten heredar el default del usuario o definir un override para esa obra. Por defecto las entradas nuevas tienen `rating: 0`, `review: ""` y `watched_at: ""`.

Marcar una entrada como pendiente no borra `watched_at`; si queres corregir o limpiar esa fecha, se hace desde el registro personal del panel lateral.

Cuando existen datos enriquecidos, la tarjeta muestra genero y director de forma compacta; el panel lateral muestra genero, director, guionistas y reparto con mas espacio. Esos campos tambien entran en el buscador.

La seccion `Metadata` del detalle permite corregir titulos, año, descripcion, genero, direccion, guion y reparto. Cada campo guarda su procedencia en `metadata_sources`; los datos historicos migrados se marcan como procedencia inferida. Al activar `Bloquear`, el campo entra en `locked_fields` y los merges externos posteriores no pueden modificarlo.

El panel lateral permite cambiar manualmente `en_catalogo` con `Marcar catalogo` / `Quitar catalogo`, sin tocar el estado `to_watch` o `watched`.

El panel lateral permite editar el tipo con un selector: `pelicula`, `serie`, `anime` o `documental`. Las entradas nuevas se crean como `pelicula` por defecto.

Al combinar un resultado externo se guarda el link especifico de la fuente (`wikipedia_url`, `imdb_url` o `filmaffinity_url`) sin perder el link principal que ya tuviera la entrada.

La navegacion principal incluye una `Bandeja` para trabajar sin mezclar ese proceso con la exploracion. El modo `Curaduria` reune pendientes, posibles duplicados y entradas sin referencia externa; tambien conserva una cola separada de casos pospuestos. Las decisiones `Posponer`, `No son duplicados`, `No requiere referencia` y los merges revisados quedan en `Actividad`, desde donde pueden deshacerse. El modo `Importaciones` conserva borradores temporales y muestra la clasificacion antes de cualquier escritura.

El historial conserva hasta 50 operaciones y puede funcionar como `Persistente` o `Solo esta sesion`. El modo persistente usa un unico archivo lateral `.<catalogo>.curation-history.json`, separado del esquema portable y de las exportaciones. `Limpiar historial` elimina esos snapshots con confirmacion y no modifica el catalogo. Si una obra fue editada despues de una operacion, Deshacer se bloquea para no sobrescribir el cambio posterior.

La vista `Administrar` muestra cuantas entradas estan vistas, cuantas quedan por ver y cuantas tienen links o portada. Tambien expone el catalogo editable, los archivos cargados y el estado de Wikipedia, IMDb y FilmAffinity. Los accesos de depuracion abren directamente la cola correspondiente de la Bandeja.

`Random` abre una ficha al azar sin modificar el JSON. Su casilla permite limitar la eleccion a obras disponibles en catalogo. Dentro de `Coleccion`, `Mezclar vista` cambia solamente el orden visual de los resultados actuales y `Restablecer orden` recupera el orden elegido.

Las imagenes del visor se sirven desde un cache local persistente. Una portada visible conserva su placeholder hasta que el navegador confirma la carga y entonces aparece con una transicion breve; las primeras cards de la vista y la ficha abierta tienen prioridad sobre el trabajo de fondo. La primera peticion autenticada a un catalogo registra sus portadas y activa un unico worker global que descarga de a una cada 3 segundos. El worker tambien incorpora solamente las colecciones o catalogos compartidos que alguien abre, deduplica URLs entre usuarios y continua mientras el proceso del servidor siga activo. No bloquea `/api/items` ni realiza enriquecimiento de metadata.

Cada descarga se valida con la misma allowlist y proteccion SSRF del proxy, se escribe de forma atomica y se reintenta con espera creciente ante errores temporales. El limite predeterminado es 5 MB por imagen y 512 MB en total; al alcanzarlo se eliminan primero los archivos menos usados recientemente. `Administrar > Base de datos` muestra el avance del catalogo personal y, para el owner, un resumen agregado sin revelar datos privados de otros usuarios.

En Docker el cache vive en `/var/lib/movie-inbox/image-cache`, dentro del volumen nombrado `movie-inbox-data`. Sobrevive a reinicios, `docker compose down` y recreaciones por actualizacion. Se elimina solamente al borrar ese volumen, por ejemplo con `docker compose down --volumes`, por lo que ese flag no debe usarse durante una actualizacion normal. El limite puede cambiarse con `MOVIE_INBOX_IMAGE_CACHE_MB`, la precarga con `MOVIE_INBOX_IMAGE_WARM_MODE=after-access|off` y la pausa con `MOVIE_INBOX_IMAGE_WARM_INTERVAL_SECONDS` en `.env`.

```powershell
movie-inbox cache info --dir .catalog-cache/images
movie-inbox cache prune --dir .catalog-cache/images --max-total-mb 512
movie-inbox cache clear --dir .catalog-cache/images
```

Se puede desactivar todo el cache con `--no-image-cache`, desactivar solamente la precarga con `--image-cache-warm-mode off`, ajustar su ritmo con `--image-cache-warm-interval-seconds`, cambiar la carpeta con `--image-cache-dir`, limitar cada imagen con `--image-cache-max-mb` o el total con `--image-cache-total-mb`. El proxy acepta JPEG, PNG, WebP, GIF y AVIF provenientes de los hosts conocidos de Wikimedia, IMDb y FilmAffinity. Un proveedor adicional debe habilitarse de forma explicita repitiendo `--image-host nombre.example`.

Para intentar completar links automaticamente desde la terminal:

```powershell
py scripts/match_external_links.py catalogv2.json --json catalogv3_links.json --report external-links-report.json --limit 100
```

El script busca en Wikipedia, IMDb y FilmAffinity para entradas sin link, combina automaticamente solo matches de alta confianza y deja en el reporte los casos dudosos para revisar en el visualizador.

Un titulo exacto sin ano, con ano distinto o con tipo incompatible nunca se combina automaticamente. Esos candidatos aparecen en `needs_review` con score, motivo y evidencia para decidirlos desde el visor.

## Esquema versionado y migracion

Las escrituras nuevas usan `schema_version: 5` y guardan las entradas dentro de `items`. Los catalogos legacy y las versiones 1 a 4 pasan por migraciones explicitas antes de usarse. Una version futura, una raiz mal formada o una fila invalida se rechazan y nunca se interpretan como catalogo vacio ni se reescriben silenciosamente. Cada obra puede tener varios archivos fisicos en `local_files`; `local_name` y `local_path` se mantienen por compatibilidad. La version 3 sumo procedencia y bloqueos de metadata. La version 4 agrego a cada archivo `library_id`, `relative_path`, `fingerprint`, `last_seen_at` y `available` para soportar sincronizacion incremental. La version 5 agrega `link_curation_status`, `duplicate_decisions` y `curation_updated_at` para que las decisiones de la Bandeja sean persistentes.

Para convertir un catalogo completo sin reemplazar el original:

```powershell
py scripts/migrate_catalog.py scripts/catalogv3_links.json --json scripts/catalogv5.json
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

Los checks completos, incluida la compilacion y `git diff --check`, se ejecutan localmente con:

```powershell
scripts\check.ps1
```

Si Windows bloquea la ejecucion de scripts, se puede habilitar solamente para esa corrida:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\check.ps1"
```

En Linux o en el servidor se usa `bash scripts/check.sh`. El workflow `.github/workflows/tests.yml` corre la misma validacion en Linux/Python 3.11 y Windows/Python 3.14 en cada push a `master` y en cada pull request. Un job adicional construye el wheel, lo instala en un entorno limpio, ejecuta `movie-inbox --help`, carga HTML/CSS/JS desde el paquete y consulta `/healthz` sobre una instancia real. CI valida una revision; no despliega ni accede al catalogo personal.

## Despliegue en servidor

El checkout contiene codigo, no datos. En un servidor, el catalogo y `instance.db` deben vivir fuera del repo, por ejemplo en `/var/lib/movie-inbox/`, y los backups en otra ruta persistente. Nginx apunta al proceso web que escucha en loopback; nunca apunta al directorio Git ni sirve ninguna base directamente.

El despliegue reproducible con una instancia nueva, importacion inicial y medios de solo lectura esta documentado en [docs/docker.md](docs/docker.md). El despliegue nativo, los flags de proxy y las plantillas de `systemd`/Nginx estan en [docs/deployment.md](docs/deployment.md). La estructura de almacenamiento y la migracion reversible estan en [docs/storage.md](docs/storage.md). En Docker el proceso escucha dentro del contenedor, pero el puerto del host permanece publicado en loopback; Nginx o una VPN controlan el acceso externo.

## Limpiar titulos y linkear con Wikipedia

Para dumps locales con nombres tipo `The English Patient 1996 720p BluRay x264 YIFY`, primero conviene limpiar titulos y normalizar estados:

```powershell
py scripts/enrich_catalog.py catalogv2.json --json catalog_clean.json --csv catalog_clean.csv --report enrich-report.json
```

Eso separa el año cuando puede, limpia datos de release/calidad/codecs/grupos y cambia `status: cataloged` a `status: to_watch`. El campo `en_catalogo` no se toca: una pelicula puede tener `en_catalogo: true` y a la vez `status: to_watch`.

Para intentar linkear con Wikipedia:

```powershell
py scripts/enrich_catalog.py catalog_clean.json --json catalog_wiki.json --csv catalog_wiki.csv --fetch-wikipedia --report wiki-report.json
```

Si queres probar de a poco:

```powershell
py scripts/enrich_catalog.py catalog_clean.json --json catalog_wiki_sample.json --fetch-wikipedia --limit 100 --report wiki-sample-report.json
```

El reporte lista cuantas entradas pudo linkear y cuales quedaron sin match. Para 1800 entradas conviene revisar primero una muestra antes de correr todo.

El enriquecedor usa tres caminos: completa metadata si ya hay URL de Wikipedia, resuelve IDs de IMDb `tt...` via Wikidata cuando puede, y finalmente busca por titulo limpio en Wikipedia en ingles y espanol.

Para corridas largas, el script guarda progreso cada 25 consultas por defecto y si lo interrumpis con Ctrl+C guarda salida parcial. Evita escribir encima del catalogo base durante pruebas:

```powershell
py scripts/enrich_catalog.py catalog_clean.json --json catalog_wiki_v5.json --csv catalog_wiki_v5.csv --fetch-wikipedia --report wiki-report-v5.json --progress-every 25
```

El enriquecedor acepta tanto JSON como SQLite. Para pruebas largas sigue siendo prudente escribir a una salida distinta y revisar el reporte antes de reemplazar la fuente principal.

## Extension de Chrome

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

## Siguiente paso natural

Cuando ya tengas un catalogo estable, JSON puede ser la semilla portable y SQLite la base de trabajo para:

- una webapp local
- una app Kotlin
- temporadas y episodios sobre el esquema relacional preparado
- importacion desde la extension
