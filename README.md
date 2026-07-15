# Movie Inbox

Pequena base para convertir una lista desordenada de links de peliculas/series en datos mas utiles.

## Estado del proyecto

La version de desarrollo actual es **v0.2.0**. Movie Inbox funciona como un gestor local de catalogo con almacenamiento JSON o SQLite: importa listas y archivos, consulta fuentes externas, detecta duplicados y permite administrar disponibilidad, estado de visualizacion, puntajes y reviews desde una interfaz web.

El catalogo usa esquemas versionados. JSON sigue siendo el formato legible y portable de intercambio y backup; SQLite puede usarse como fuente de verdad transaccional. Los catalogos personales, reportes, caches y backups se mantienen fuera de Git. Las capacidades de cada version estan resumidas en [CHANGELOG.md](CHANGELOG.md).

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

## Instalacion y comandos

Para trabajar desde un checkout, instala el paquete en modo editable:

```powershell
py -m pip install -e .
```

Eso habilita un unico comando con subcomandos:

```powershell
movie-inbox import links.txt --json catalog.json --fetch
movie-inbox scan --config scanner.json --dry-run
movie-inbox serve catalog.json
movie-inbox migrate catalog-viejo.json --json catalog-v4.json
movie-inbox enrich catalog.json --json catalog-enriquecido.json
movie-inbox match catalog.json --json catalog-con-links.json
movie-inbox db import catalog.json --db data/movie-inbox.db
movie-inbox db export data/movie-inbox.db --json backups/catalog.json
```

En Windows, si la carpeta `Scripts` de Python no esta en `PATH`, usa la forma equivalente:

```powershell
py -m movie_inbox serve catalog.json
```

El ejecutable suele quedar en `%LocalAppData%\Programs\Python\Python314\Scripts`. Agregar esa carpeta al `PATH` permite invocar directamente `movie-inbox` desde una terminal nueva.

Los comandos `py scripts/txt_to_catalog.py ...`, `py scripts/scan_library.py ...` y `py scripts/view_catalog.py ...` siguen funcionando y llaman a la misma implementacion del paquete.

## SQLite y backups JSON

Para crear una base SQLite sin modificar el JSON original:

```powershell
py -m movie_inbox db import scripts/catalogv3_links.json --db data/movie-inbox.db
```

El import verifica los IDs despues de escribir. No reemplaza una base con datos salvo que se use `--replace`; en ese caso primero crea un backup JSON de la base anterior. El visor, scanner, enriquecedor y matcher seleccionan el repositorio por extension, por lo que la base se abre directamente:

```powershell
py -m movie_inbox serve data/movie-inbox.db
py -m movie_inbox db info data/movie-inbox.db
```

Para generar un backup legible y versionado:

```powershell
py -m movie_inbox db export data/movie-inbox.db --json backups/catalog-2026-07-15.json
```

SQLite normaliza obras, aliases, IDs externos, archivos locales, tags y procedencia. Tambien reserva tablas para temporadas y episodios, pero esa funcionalidad todavia no forma parte del dominio ni de la interfaz. Los archivos `.db`, `.sqlite`, sus journals y `data/` se ignoran en Git.

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

El scanner recorre subcarpetas y guarda estado liviano en `.catalog-state`. Usa tamano, fecha de modificacion y una huella parcial para evitar leer de nuevo archivos que no cambiaron. Un movimiento dentro del disco conserva la entrada; una coincidencia unica por titulo, ano y tipo se asocia al item existente; una coincidencia ambigua no se aplica y queda en `needs_review`.

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

Antes de sobrescribir un JSON existente, los scripts crean un backup automatico junto al archivo con formato `nombre.YYYYMMDD-HHMMSS-microsegundos.bak.json`. Para uso continuo en servidor se recomienda SQLite como fuente principal y una exportacion JSON periodica como backup portable.

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

Este visor relee los archivos cada vez que apretas "Actualizar", asi que sirve para ir tirando exports nuevos de Chrome y verlos sin regenerar nada.

El visor tiene una consola de busqueda unica con fuentes combinables. `Catalogo` queda siempre activo para buscar en los datos locales y `Externo` se puede marcar cuando tambien queres consultar Wikipedia, IMDb y FilmAffinity. La busqueda se ejecuta solo al tocar `Buscar` o presionar Enter; marcar/desmarcar una fuente no dispara consultas. Si abriste varios catalogos, por defecto escribe en el primero resuelto; podes elegir otro archivo con el nombre compatible `--write-json`:

Las consultas externas se ejecutan en paralelo mediante adaptadores independientes y se guardan durante 15 minutos en un cache de memoria. Un error en una fuente no cancela las otras. `External DBs` muestra estado, latencia, cantidad de resultados y errores por fuente, ademas de hits, misses y entradas del cache. Wikipedia devuelve primero datos livianos para mostrar resultados rapido y completa la metadata de la entrada elegida recien al agregarla o combinarla.

Los resultados elegidos de IMDb tambien intentan resolverse mediante su ID en Wikidata/Wikipedia antes de guardarse. Eso permite completar titulo original, titulo en espanol, titulo en ingles y aliases de otros idiomas cuando existen. La busqueda local ignora tildes y tolera una errata de un caracter en palabras largas.

```powershell
python scripts/view_catalog.py catalog_wiki_v5.json --write-json catalog_wiki_v5.json
```

Las tarjetas del visor local ahora son una vista rapida para escanear: imagen, titulo, subtitulo con titulo original/ingles cuando difiere, badges de estado/link/catalogo, mini ficha y acciones basicas. Al hacer click en una tarjeta se abre un panel lateral con la ficha completa, titulos multilenguaje, links asociados, registro personal y acciones destructivas.

El resumen muestra cuantas entradas tienen posibles duplicados por URL externa o por titulo y ano. `Ver duplicadas` filtra esas entradas, cada card lleva un badge y el detalle explica la coincidencia. Al agregar desde una fuente externa, el catalogo editable se revisa primero por URL y por todos sus titulos conocidos antes de insertar.

Los resultados de busqueda local y externa se muestran como cards compactas, de a 6, y suman `Cargar mas` cuando quedan mas coincidencias. La descripcion ocupa como maximo dos lineas y `Ver mas` abre el texto completo. Las cards externas priorizan `Agregar`, `Comparar` y `Detalle`; las locales priorizan `Detalle` y muestran `Combinar` cuando venis comparando contra un resultado externo. La grilla principal renderiza 36 entradas por tanda para evitar crear de golpe todas las cards e imagenes del catalogo.

Los items agregados manualmente entran con `status: to_watch` y `en_catalogo: false`.

Antes de agregar, el visor revisa si ya existe una entrada con titulo normalizado y año compatible. Si encuentra una posible coincidencia, muestra opciones para combinar, agregar igual o cancelar. Al combinar, conserva datos locales como `en_catalogo`, `local_name` y `local_path`, y suma el link/metadata del resultado elegido.

Cuando el detector automatico no encuentra el duplicado, en un resultado externo podes usar `Comparar`: el visor busca la entrada existente, muestra diferencias campo por campo y permite usar `Combinar`.

Cada tarjeta tiene `Buscar link`. Ese boton usa automaticamente el titulo/año de esa entrada, busca en Wikipedia, IMDb y FilmAffinity, y deja lista la comparacion contra esa misma entrada.

El panel lateral tiene accion `Eliminar`. Antes de borrar, el navegador pide confirmacion porque se modifica directamente el catalogo elegido.

Cada tarjeta tambien permite cambiar rapidamente entre `to_watch` y `watched` con `Marcar vista` / `Marcar pendiente`. Al marcar una entrada como vista se guarda `watched_at` con la fecha local del dia.

El panel lateral incluye el registro personal para editar `watched_at`, `rating` de 0 a 10 y `review`. Por defecto las entradas nuevas tienen `rating: 0`, `review: ""` y `watched_at: ""`.

Marcar una entrada como pendiente no borra `watched_at`; si queres corregir o limpiar esa fecha, se hace desde el registro personal del panel lateral.

Cuando existen datos enriquecidos, la tarjeta muestra genero y director de forma compacta; el panel lateral muestra genero, director, guionistas y reparto con mas espacio. Esos campos tambien entran en el buscador.

La seccion `Metadata` del detalle permite corregir titulos, año, descripcion, genero, direccion, guion y reparto. Cada campo guarda su procedencia en `metadata_sources`; los datos historicos migrados se marcan como procedencia inferida. Al activar `Bloquear`, el campo entra en `locked_fields` y los merges externos posteriores no pueden modificarlo.

El panel lateral permite cambiar manualmente `en_catalogo` con `Marcar catalogo` / `Quitar catalogo`, sin tocar el estado `to_watch` o `watched`.

El panel lateral permite editar el tipo con un selector: `pelicula`, `serie`, `anime` o `documental`. Las entradas nuevas se crean como `pelicula` por defecto.

Al combinar un resultado externo se guarda el link especifico de la fuente (`wikipedia_url`, `imdb_url` o `filmaffinity_url`) sin perder el link principal que ya tuviera la entrada.

El lateral queda separado en `Resumen`, `Filtros`, `Menu` y `Herramientas`. En `Menu`, `Bases de datos` muestra el catalogo editable y los archivos cargados; `External DBs` muestra el estado de Wikipedia, IMDb y FilmAffinity. En herramientas incluye `Revisar sin link`, `Anterior` y `Siguiente` para recorrer de forma sistematica las entradas que todavia no tienen link asociado de Wikipedia, IMDb o FilmAffinity.

El resumen lateral muestra cuantas entradas estan vistas, cuantas quedan por ver, cuantas tienen algun link asociado y cuantas siguen sin link.

El lateral tambien incluye `Randomizar` para mezclar solo la vista actual, respetando filtros y busquedas sin modificar el JSON. `Orden normal` vuelve al orden original.

Las imagenes del visor se sirven con un cache local. La primera vez que una tarjeta necesita `page_image`, el servidor la descarga y la guarda en `.catalog-cache/images` junto al catalogo editable; despues se sirve desde esa carpeta. Se puede desactivar con `--no-image-cache`, cambiar la carpeta con `--image-cache-dir` o limitar el tamano por imagen con `--image-cache-max-mb`.

Para intentar completar links automaticamente desde la terminal:

```powershell
py scripts/match_external_links.py catalogv2.json --json catalogv3_links.json --report external-links-report.json --limit 100
```

El script busca en Wikipedia, IMDb y FilmAffinity para entradas sin link, combina automaticamente solo matches de alta confianza y deja en el reporte los casos dudosos para revisar en el visualizador.

Un titulo exacto sin ano, con ano distinto o con tipo incompatible nunca se combina automaticamente. Esos candidatos aparecen en `needs_review` con score, motivo y evidencia para decidirlos desde el visor.

## Esquema versionado y migracion

Las escrituras nuevas usan `schema_version: 4` y guardan las entradas dentro de `items`. Los catalogos legacy y las versiones 1 a 3 pasan por migraciones explicitas antes de usarse. Una version futura, una raiz mal formada o una fila invalida se rechazan y nunca se interpretan como catalogo vacio ni se reescriben silenciosamente. Cada obra puede tener varios archivos fisicos en `local_files`; `local_name` y `local_path` se mantienen por compatibilidad. La version 3 sumo procedencia y bloqueos de metadata. La version 4 agrega a cada archivo `library_id`, `relative_path`, `fingerprint`, `last_seen_at` y `available` para soportar sincronizacion incremental sin eliminar campos anteriores.

Para convertir un catalogo completo sin reemplazar el original:

```powershell
py scripts/migrate_catalog.py scripts/catalogv3_links.json --json scripts/catalogv4.json
```

Las escrituras del visor y del importador son atomicas: primero se completa un archivo temporal y luego se reemplaza el JSON. El visor bloquea cada catalogo durante operaciones de escritura concurrentes y conserva como maximo los 10 backups automaticos mas recientes.

## Seguridad del visor web

El visor genera un token aleatorio en cada inicio y lo exige en todas las operaciones de API. FastAPI valida hosts confiables y, para escrituras, un origen exacto; acepta solamente `Content-Type: application/json`, limita el cuerpo a 2 MB y devuelve estados HTTP 4xx/5xx. El proxy de imagenes solo acepta HTTP/HTTPS publico en puertos estandar, bloquea destinos privados, loopback, link-local o reservados y vuelve a validar cada redireccion. La documentacion OpenAPI publica esta deshabilitada y `/healthz` no expone datos.

Detras de Nginx se indica el origen externo con `--public-origin` y se limita la confianza de headers reenviados con `--forwarded-allow-ips`. El token de sesion no reemplaza autenticacion: el acceso debe protegerse con una VPN o en el proxy HTTPS.

## Pruebas

La suite usa `unittest` de la libreria standard y cubre migraciones, repositorios JSON/SQLite, modelos, matching conservador, limites entre capas y seguridad HTTP/SSRF:

```powershell
py -m unittest discover -s tests -v
```

Los checks completos, incluida la compilacion y `git diff --check`, se ejecutan localmente con:

```powershell
scripts\check.ps1
```

En Linux o en el servidor se usa `bash scripts/check.sh`. El workflow `.github/workflows/tests.yml` corre la misma validacion en Linux/Python 3.11 y Windows/Python 3.14 en cada push a `master` y en cada pull request. CI valida una revision; no despliega ni accede al catalogo personal.

## Despliegue en servidor

El checkout contiene codigo, no datos. En un servidor, la base debe vivir fuera del repo, por ejemplo en `/var/lib/movie-inbox/movie-inbox.db`, y los backups en otra ruta persistente. Nginx apunta al proceso web que escucha en loopback; nunca apunta al directorio Git ni sirve la base directamente.

El flujo completo, los flags de proxy y las plantillas de `systemd`/Nginx estan documentados en [docs/deployment.md](docs/deployment.md). La estructura de almacenamiento y la migracion reversible estan en [docs/storage.md](docs/storage.md). Uvicorn debe permanecer en loopback; Nginx o una VPN controlan el acceso externo.

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

