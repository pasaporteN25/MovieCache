# Almacenamiento

Movie Inbox mantiene un modelo canonico independiente del formato de persistencia. Los casos de uso dependen de `CatalogRepository`; la extension del archivo selecciona `JsonCatalogRepository` o `SqliteCatalogRepository`.

La identidad de la instancia vive en una segunda base SQLite. Esta separacion evita que usuarios, contrasenas o sesiones entren en el esquema portable del catalogo.

## Responsabilidades

- SQLite es la opcion recomendada como fuente de verdad para un proceso de servidor.
- JSON es el formato de importacion, exportacion, auditoria y backup portable.
- Los datos personales no se guardan en Git.
- Una migracion debe ser reversible mediante una exportacion JSON verificada.
- `instance.db` debe tratarse como un secreto y respaldarse separado de los JSON exportados.

## Base de instancia v1

La base de instancia contiene:

- `users`: owner inicial, hash `scrypt`, rol y estado de la cuenta.
- `catalogs`: catalogo personal predeterminado de cada usuario.
- `catalog_sources`: archivos JSON/SQLite que forman ese catalogo y fuente writable.
- `sessions`: hashes de tokens opacos y expiracion absoluta.

El primer bootstrap adopta el catalogo existente de forma logica. Registra sus rutas absolutas bajo el owner, pero no reescribe ni mueve el archivo. Arranques posteriores validan ese vinculo y rechazan una ruta distinta para evitar abrir accidentalmente datos ajenos bajo la misma identidad.

Una exportacion JSON incluye solamente el catalogo. No incluye cuentas ni sesiones. Para restaurar una instancia completa se respaldan por separado el catalogo, `instance.db` y la configuracion del scanner; para restaurar solamente las obras se importa el JSON y se crea un owner nuevo.

## Esquema SQLite v3

La tabla `schema_migrations` gobierna la version de la base. Una version superior se rechaza; una base con tablas sin historial tampoco se interpreta como un catalogo vacio.

El esquema separa:

- `catalog_items`: datos escalares de la obra y campos desconocidos conservados en `extra_json`.
- `alternative_titles`: aliases multilenguaje.
- `external_ids`: URLs e IDs de Wikipedia, Wikidata, IMDb y FilmAffinity.
- `metadata_values`: generos, directores, guionistas y reparto.
- `local_files`: archivos fisicos y estado de disponibilidad.
- `metadata_provenance`, `locked_fields` y `tags`: curacion personal.
- `duplicate_decisions`: decisiones persistentes sobre pares que se pospusieron o no son duplicados.
- `seasons` y `episodes`: estructura reservada para una futura fase de series.

La migracion v2 suma `backdrop_image` y `tmdb_id`: permite guardar arte horizontal para el reel y una identidad estable para futuros proveedores de imagenes, sin obligar a configurar una API externa para usar el catalogo.

La migracion v3 agrega `link_curation_status` y `curation_updated_at` a las obras, ademas de la tabla relacional `duplicate_decisions`. De este modo `Posponer`, `No son duplicados` y `No requiere referencia` se conservan tanto en SQLite como en las exportaciones JSON v5.

Temporadas y episodios todavia no se importan desde JSON ni aparecen en el CRUD. Las actualizaciones de una obra preservan esas filas para que el esquema pueda evolucionar sin perderlas.

## Migracion reversible

```powershell
py -m movie_inbox db import catalog.json --db data/movie-inbox.db
py -m movie_inbox db info data/movie-inbox.db
py -m movie_inbox db export data/movie-inbox.db --json backups/catalog.json
```

`db import` no reemplaza una base no vacia sin `--replace`. Antes de un reemplazo crea una exportacion `pre-import-*.bak.json`. Tanto import como export vuelven a leer el destino y comparan el documento canonico completo, incluidos aliases, reviews, metadata, procedencia y archivos locales.

No se migra automaticamente ningun catalogo del usuario. El comando siempre recibe origen y destino explicitos.

## Historial de curaduria

El historial reversible es estado operativo y no forma parte del documento canonico. En modo persistente se guarda junto al catalogo principal como `.<nombre>.curation-history.json`; tanto un catalogo JSON como uno SQLite usan el mismo contrato lateral. El archivo contiene solamente las ultimas 50 operaciones y se reemplaza de forma atomica, sin generar backups rotativos.

Cada operacion conserva los estados anterior y posterior de las entradas afectadas. `Deshacer` compara primero el estado posterior esperado con el catalogo actual: si hubo una edicion posterior, devuelve un conflicto y no escribe. Al restaurar un merge recupera ambas entradas, sus IDs, posiciones y decisiones de curaduria.

El modo `Solo esta sesion` mantiene esos snapshots en memoria y no crea el sidecar. Cerrar la sesion del navegador o reiniciar el servidor elimina esa capacidad de recuperacion. `Limpiar historial` borra el registro del modo activo, pero nunca modifica las obras.
