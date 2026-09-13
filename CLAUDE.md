# CLAUDE.md

Movie Inbox: gestor self-hosted de catálogo audiovisual. Python + FastAPI + SQLite,
frontend vanilla sin build step. Estable v0.8.0; la 0.9.0 está abierta, ver "Versiones".

Antes de trabajar, leé los contratos vigentes: `PRODUCT.md`, `DESIGN.md`,
`docs/roadmap.md`, `CHANGELOG.md` (`[Sin publicar]`), `tests/test_layering.py`.
No son documentación decorativa.

## Comandos

```powershell
py -m pip install -e ".[test]"
py -m unittest discover -s tests -v          # suite completa, tiene que quedar verde
scripts\check.ps1                            # install + compileall + tests + git diff --check
py -m unittest discover -s tests/browser -p "test_*.py" -v   # requiere [browser-test] + playwright install chromium
movie-inbox serve catalog.json --owner-username <user>       # servidor local
```

En Linux/CI: `bash scripts/check.sh`. CI (`.github/workflows/tests.yml`) corre `test`
(Linux 3.11 / Windows 3.14), `wheel-smoke`, `browser-smoke` (10 min de límite) y
`docker-smoke`.

## Invariantes (ver prompt-movie-inbox.md para el detalle)

1. **Layering** — `domain/` y `application/` no importan `infrastructure`, `external`,
   `web` ni `cli`. Verificado por AST en `tests/test_layering.py`.
2. **Terminología** (`PRODUCT.md`) — `en_catalogo` (disponibilidad física) es
   independiente de `to_watch`/`watched`. Nunca se presentan como intercambiables.
3. **Matching conservador** — coincidencia dudosa = revisión humana. Descripción,
   review, reparto, género o tags nunca deciden identidad. Gate de v0.3.0: cero falsos
   positivos conocidos en auto-match.
4. **Privacidad** — vistas compartidas (`Club`) nunca exponen rutas, archivos locales,
   notas ni estado operativo. Sin excepción para el owner. **Excepción explícita y
   acotada ([P2])**: si el admin activa "compartir disponibilidad" para una biblioteca
   puntual (opt-in por biblioteca, nunca automático), el título de la colección de Club
   resultante puede mostrar — y por defecto arranca con — el nombre que el admin le
   puso a esa biblioteca. Nunca la ruta, los archivos ni ningún otro dato operativo; el
   admin puede cambiar ese título antes o después de publicarlo.
5. **Correcciones manuales y `locked_fields`** sobreviven a cualquier enriquecimiento.
6. **JSON portable** — `catalog.schema.json` es un contrato versionado. SQLite es la
   fuente de verdad; JSON es importación/exportación/backup.

Si una tarea parece exigir romper alguna, parar y preguntar en vez de decidir solo.

## Mapa de capas (`src/movie_inbox/`)

- `domain/` — modelos, normalización, matching, reglas de merge. Puro, sin I/O ni deps
  externas. Nada de FastAPI, SQLite ni clientes HTTP acá.
- `application/` — casos de uso compartidos por visor, importadores y scanner
  (servicios, repositorios abstractos). Orquesta `domain/`, no implementa persistencia.
- `infrastructure/` — esquemas, repositorios JSON/SQLite, exportación, scanner de
  archivos. Implementa los contratos de `application/`.
- `external/` — clientes de Wikipedia, Wikidata, IMDb, FilmAffinity.
- `web/` — FastAPI, Uvicorn, proxy de imágenes, assets estáticos, seguridad HTTP.
- `cli/` — subcomandos de `movie-inbox`. Los comandos batch (`match_external_links.py`,
  `enrich_catalog.py`, `scan_library.py`, `imdb_dataset.py`) no pueden importar `web`.

Los lanzadores finos de compatibilidad con v0.1 (`view_catalog.py`, `txt_to_catalog.py`,
`scan_library.py`, `enrich_catalog.py`, `match_external_links.py`, `migrate_catalog.py`)
y los shims de import (`catalog_*.py`) ya no viven en `scripts/`: se movieron a
`codigoLegacy/` (fuera de Git, ver `.gitignore`) porque nadie los ejecuta dentro del
contenedor Docker — ahí el camino es `movie-inbox <subcomando>`. La lógica nueva va
siempre al paquete.

## Reparto de trabajo entre agentes (desde 2026-09-07)

El trabajo corre en paralelo, dividido por especialidad:

- **Claude** — infraestructura, backend, modelo de datos, capas, contratos con fuentes
  externas, migraciones y pruebas. Frentes propios: activación real de TMDb,
  disponibilidad en streaming, charadas y dirección móvil
  (`docs/analisis/streaming-charadas-movil-2026-09-07.md`).
- **Codex** — dirección visual y frontend de presentación: [U2-P] y sus derivados.

El cliente Android es otro repositorio, `../movieIndexAndroid`, con su propio tablero
(decisión del owner del 2026-08-17). Acá sólo vive lo que ese cliente consume: la API
`/api/v1/`, su contrato OpenAPI y los vectores de prueba que el cliente porta.

`tareas.md` es compartido: cada frente agrega su sección y no reescribe las ajenas. Antes
de commitear, comprobar que el árbol no arrastra trabajo sin commitear del otro frente en
los mismos archivos.

## Versiones

La 0.9.0 está abierta en la rama `release/0.9.0` y se cierra al fusionar su PR contra
`master`. Mientras tanto se trabaja y se commitea en esa rama: todo lo que se commitea en
este checkout entra en la versión. `master` no recibe commits directos, sólo esa fusión, y
con merge commit, porque los documentos citan hashes de la rama. Lo que falta para cerrarla
está en [V9] de `tareas.md`; el gate y los pasos de cierre, en `docs/release-checklist.md`.

## Archivos personales — no tocar, no leer como fixture

Datos reales del usuario, fuera del repo por `.gitignore`: `scripts/*.json`,
`scripts/*.csv`, `scripts/*.txt`, `catalog*.json`, `.catalog-cache/`, `.movie-inbox/`,
`data/`, `imports/`, `media/`, `secrets/`, `backups/`, `*.db`/`*.sqlite*`,
`*.bak.json`, `*.curation-history.json`.
