# Almacenamiento

Movie Inbox mantiene un modelo canonico independiente del formato de persistencia. Los casos de uso dependen de `CatalogRepository`; la extension del archivo selecciona `JsonCatalogRepository` o `SqliteCatalogRepository`.

## Responsabilidades

- SQLite es la opcion recomendada como fuente de verdad para un proceso de servidor.
- JSON es el formato de importacion, exportacion, auditoria y backup portable.
- Los datos personales no se guardan en Git.
- Una migracion debe ser reversible mediante una exportacion JSON verificada.

## Esquema SQLite v1

La tabla `schema_migrations` gobierna la version de la base. Una version superior se rechaza; una base con tablas sin historial tampoco se interpreta como un catalogo vacio.

El esquema separa:

- `catalog_items`: datos escalares de la obra y campos desconocidos conservados en `extra_json`.
- `alternative_titles`: aliases multilenguaje.
- `external_ids`: URLs e IDs de Wikipedia, Wikidata, IMDb y FilmAffinity.
- `metadata_values`: generos, directores, guionistas y reparto.
- `local_files`: archivos fisicos y estado de disponibilidad.
- `metadata_provenance`, `locked_fields` y `tags`: curacion personal.
- `seasons` y `episodes`: estructura reservada para una futura fase de series.

Temporadas y episodios todavia no se importan desde JSON ni aparecen en el CRUD. Las actualizaciones de una obra preservan esas filas para que el esquema pueda evolucionar sin perderlas.

## Migracion reversible

```powershell
py -m movie_inbox db import catalog.json --db data/movie-inbox.db
py -m movie_inbox db info data/movie-inbox.db
py -m movie_inbox db export data/movie-inbox.db --json backups/catalog.json
```

`db import` no reemplaza una base no vacia sin `--replace`. Antes de un reemplazo crea una exportacion `pre-import-*.bak.json`. Tanto import como export vuelven a leer el destino y verifican el orden de IDs.

No se migra automaticamente ningun catalogo del usuario. El comando siempre recibe origen y destino explicitos.
