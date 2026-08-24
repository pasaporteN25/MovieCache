# Almacenamiento

Movie Inbox mantiene un modelo canonico independiente del formato de persistencia. Los casos de uso dependen de `CatalogRepository`; la extension del archivo selecciona `JsonCatalogRepository` o `SqliteCatalogRepository`.

La identidad de la instancia vive en una segunda base SQLite. Esta separacion evita que usuarios, contrasenas o sesiones entren en el esquema portable del catalogo.

## Responsabilidades

- SQLite es la opcion recomendada como fuente de verdad para un proceso de servidor.
- JSON es el formato de importacion, exportacion, auditoria y backup portable.
- Los datos personales no se guardan en Git.
- Una migracion debe ser reversible mediante una exportacion JSON verificada.
- `instance.db` debe tratarse como un secreto y respaldarse separado de los JSON exportados.

## Base de instancia v8

La base de instancia contiene:

- `users`: owner y miembros locales, hash `scrypt`, rol, estado y cambio obligatorio de contrasena.
- `catalogs`: catalogo personal predeterminado de cada usuario.
- `catalog_sources`: archivos JSON/SQLite que forman ese catalogo y fuente writable.
- `sessions`: hashes de tokens opacos y expiracion absoluta.
- `user_privacy_preferences`: opt-in del catalogo y visibilidad general de estado,
  fecha, actividad, puntajes y reviews.
- `item_privacy_overrides`: excepciones `shared` o `private` para rating y review de
  una obra; `inherit` se representa eliminando la excepcion.
- `archived_members` y `archived_catalog_sources`: baja reversible de cuentas sin
  borrar los archivos de su catalogo.
- `curated_collections` y `curated_collection_items`: definicion y obras de las
  colecciones locales, separadas de cualquier estado personal.
- `collection_follows`: suscripciones de lectura por usuario dentro de la instancia.
- `collection_seed_records`: instalaciones de colecciones iniciales que no deben
  reaparecer si el administrador las elimina mas adelante.
- `import_drafts` e `import_draft_items`: borradores de importacion aislados por
  usuario, filas normalizadas, clasificacion y resultado de la aplicacion.
- `media_libraries`: rutas permitidas, frecuencia, estado y proteccion ante bajas de
  cada biblioteca fisica administrada por el owner.
- `library_scan_runs`: cola e historial persistente de pruebas, aplicaciones manuales
  y recorridos programados; conserva los 100 mas recientes por biblioteca.
- `library_files`: inventario privado de rutas relativas, huellas, identidad confirmada
  y disponibilidad observada; nunca se expone a miembros.
- `home_featured_snapshots`: referencias y motivos de las dos selecciones editoriales
  mas recientes de cada usuario.
- `scanner_history`: decisiones reversibles del Scanner, incluido el estado del
  inventario y, cuando corresponde, de la ficha personal creada o reutilizada.

El primer bootstrap adopta el catalogo existente de forma logica. Registra sus rutas absolutas bajo el owner, pero no reescribe ni mueve el archivo. Arranques posteriores validan ese vinculo y rechazan una ruta distinta para evitar abrir accidentalmente datos ajenos bajo la misma identidad.

Los miembros nuevos reciben una base SQLite vacia en el directorio configurado con `--member-catalog-dir`, por defecto `catalogs/` junto a `instance.db`. El nombre fisico usa un identificador aleatorio y no depende del username. Desactivar una cuenta o restablecer su contrasena revoca todas sus sesiones, pero conserva su catalogo. Archivar elimina la identidad activa y guarda su vinculacion en las tablas de archivo; restaurar vuelve a enlazar el mismo archivo bajo una cuenta nueva con cambio obligatorio de contrasena. Por seguridad, la privacidad vuelve a sus defaults cerrados al restaurar.

El servidor resuelve las fuentes desde la sesion autenticada. Las rutas absolutas permanecen en `instance.db`; el frontend recibe referencias opacas y no puede seleccionar otro catalogo enviando una ruta manual.

Una exportacion JSON incluye solamente el catalogo. No incluye cuentas, sesiones, preferencias de privacidad, overrides, colecciones, seguimientos, inventario fisico ni el historial de recomendaciones. Para restaurar una instancia completa se respaldan por separado todos los catalogos activos o archivados e `instance.db`; las raices permitidas se conservan en la configuracion del proceso. Para restaurar solamente las obras se importa el JSON y se crea un owner nuevo.

Las migraciones de instancia se aplican al abrir la base. La v2 agrega privacidad y
archivo reversible; la v3 agrega colecciones locales y seguimientos; la v4 agrega
borradores de importacion acotados; la v5 agrega bibliotecas administradas, recorridos
e inventario compartido; la v6 agrega las dos selecciones destacadas mas recientes de
cada usuario; la v7 agrega el historial reversible del Scanner; y la v8 completa sus
snapshots de catalogo en instalaciones que hubieran aplicado una definicion temprana
de v7. La primera seleccion editorial registrada para una fecha queda fija. Ese
historial guarda referencias, orden y motivo, no copias de obras ni rutas. Las cuentas
existentes conservan sus catalogos privados y ninguna coleccion se sigue
automaticamente. Una version superior se rechaza en lugar de reinterpretarse.

## Disponibilidad con procedencia

`en_catalogo` continua siendo una declaracion portable del catalogo personal. El
scanner no la reescribe: guarda su evidencia en `library_files` y la API calcula una
disponibilidad efectiva como `declaracion manual OR archivo verificado`. Esto permite
que un disco desmontado retire solamente su propia evidencia y evita borrar una copia
fisica declarada por el usuario.

Las decisiones de `Bandeja > Scanner` se guardan contra una identidad compartida de
obra basada en IDs externos o en titulo exacto, ano y tipo. Esa identidad puede aportar
disponibilidad a catalogos creados despues del recorrido. La API personal puede incluir
nombre de biblioteca y cantidad de archivos para el owner; las vistas de miembros y
Club reciben solamente conteos agregados, nunca rutas, nombres o fingerprints.
Confirmar vincula el archivo al inventario de la instancia, pero no crea una entrada en
ningun catalogo personal. Omitir conserva el archivo fisico y recuerda la decision
mientras no cambie su huella. La Actividad del Scanner permite deshacer ambas
decisiones; crear una ficha y vincularla tambien restaura el estado personal previo si
no hubo una modificacion posterior en conflicto.
La clasificacion puede consultar el catalogo del owner y catalogos de miembros con
`catalog_shared` activo; un catalogo privado nunca aporta candidatos a la Bandeja del
administrador. La serializacion compartida vuelve a retirar cualquier lista de fuentes
como defensa adicional.

## Esquema SQLite v5

La tabla `schema_migrations` gobierna la version de la base. Una version superior se rechaza; una base con tablas sin historial tampoco se interpreta como un catalogo vacio.

El esquema separa:

- `catalog_items`: datos escalares de la obra, incluida la duración canónica en
  minutos, y campos desconocidos conservados en `extra_json`.
- `alternative_titles`: aliases multilenguaje.
- `external_ids`: URLs e IDs de Wikipedia, Wikidata, IMDb y FilmAffinity.
- `metadata_values`: países, idiomas originales, productores, compositores,
  géneros, directores, guionistas y reparto.
- `local_files`: archivos fisicos y estado de disponibilidad.
- `metadata_provenance`, `locked_fields` y `tags`: curacion personal.
- `duplicate_decisions`: decisiones persistentes sobre pares que se pospusieron o no son duplicados.
- `seasons` y `episodes`: estructura reservada para una futura fase de series.

La migracion v2 suma `backdrop_image` y `tmdb_id`: permite guardar arte horizontal para el reel y una identidad estable para futuros proveedores de imagenes, sin obligar a configurar una API externa para usar el catalogo.

La migracion v3 agrega `link_curation_status` y `curation_updated_at` a las obras, ademas de la tabla relacional `duplicate_decisions`. De este modo `Posponer`, `No son duplicados` y `No requiere referencia` se conservan tanto en SQLite como en las exportaciones JSON v5.

La migración v4 agrega fechas de estreno con precisión y procedencia. La v5 suma
`duration_minutes` como entero positivo opcional; los cuatro campos multivalor nuevos
reutilizan `metadata_values`, por lo que no requieren tablas específicas. El contrato
JSON portable correspondiente es v7 y migra catálogos v6 con duración desconocida y
listas vacías.

Temporadas y episodios todavia no se importan desde JSON ni aparecen en el CRUD. Las actualizaciones de una obra preservan esas filas para que el esquema pueda evolucionar sin perderlas.

## Migracion reversible

```powershell
py -m movie_inbox db import catalog.json --db data/movie-inbox.db
py -m movie_inbox db info data/movie-inbox.db
py -m movie_inbox db export data/movie-inbox.db --json backups/catalog.json
```

`db import` no reemplaza una base no vacia sin `--replace`. Antes de un reemplazo crea una exportacion `pre-import-*.bak.json`. Tanto import como export vuelven a leer el destino y comparan el documento canonico completo, incluidos aliases, reviews, metadata, procedencia y archivos locales.

No se migra automaticamente ningun catalogo del usuario. El comando siempre recibe origen y destino explicitos.

## Borradores e importacion web

La interfaz acepta TXT, CSV y JSON como contenido no confiable. El documento original no se persiste: `instance.db` guarda un hash SHA-256 del contenido, nombre sanitizado, formato, filas normalizadas y su clasificacion. Cada borrador pertenece a un usuario y expira a las 48 horas; abrir Importaciones purga los vencidos. Cada cuenta puede conservar hasta 20 borradores simultaneos. Un apply trabado conserva una gracia corta para no borrar una operacion activa y luego tambien se elimina.

Los parsers aplican limites de 8 MiB, 10.000 filas, 100 columnas, 32.768 caracteres por campo y profundidad JSON 16. JSON rechaza claves duplicadas y constantes no finitas. La entrada no puede contener binarios o NUL. La API recibe solamente `application/json` autenticado y validado contra el mismo origen; no acepta multipart, rutas del cliente, ZIP ni instrucciones para abrir archivos del servidor.

Las filas persisten sin `local_path`, `local_name` ni `local_files`. `en_catalogo` puede sobrevivir como declaracion booleana, pero se considera no verificada y no enlaza archivos fisicos. El destino `catalog` puede conservar o neutralizar `status`, `watched_at`, `rating` y `review`; el destino `collection` normaliza cada obra al conjunto de campos compartibles y siempre crea una coleccion privada nueva del owner.

La operacion vuelve a clasificar las filas contra el catalogo actual, reclama el borrador de forma transaccional y guarda su resultado para que los reintentos sean idempotentes. IDs o URLs externas iguales se tratan como presentes; coincidencias por titulo quedan para revision y no se escriben automaticamente.

Todavia queda pendiente un paquete compartible con manifiesto versionado, imagenes opcionales o intercambio entre instancias. El borrador de importacion no ejecuta el scanner ni enriquecimiento externo y todavia no puede incorporar filas a una coleccion existente. JSON sigue siendo el formato portable para intercambio completo y las colecciones publicadas siguen limitadas a la instancia local.

## Historial de curaduria

El historial reversible es estado operativo y no forma parte del documento canonico. En modo persistente se guarda junto al catalogo principal como `.<nombre>.curation-history.json`; tanto un catalogo JSON como uno SQLite usan el mismo contrato lateral. El archivo contiene solamente las ultimas 50 operaciones y se reemplaza de forma atomica, sin generar backups rotativos.

Cada operacion conserva los estados anterior y posterior de las entradas afectadas. `Deshacer` compara primero el estado posterior esperado con el catalogo actual: si hubo una edicion posterior, devuelve un conflicto y no escribe. Al restaurar un merge recupera ambas entradas, sus IDs, posiciones y decisiones de curaduria.

El modo `Solo esta sesion` mantiene esos snapshots en memoria y no crea el sidecar. Cerrar la sesion del navegador o reiniciar el servidor elimina esa capacidad de recuperacion. `Limpiar historial` borra el registro del modo activo, pero nunca modifica las obras.
