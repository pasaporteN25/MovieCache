# SDD — especificación y convenciones del proyecto

Este documento fija parámetros y convenciones de trabajo para que los agentes (Claude,
Codex, y quien se sume después) avancen con menos ambigüedad. No repite lo que ya fijan
otros contratos — los referencia:

- **Qué es Movie Inbox y para quién** → [`PRODUCT.md`](PRODUCT.md).
- **Lenguaje visual** → [`DESIGN.md`](DESIGN.md).
- **Capas, invariantes técnicos y reparto de frentes entre agentes** → [`CLAUDE.md`](CLAUDE.md).
- **Gate de release y pasos de cierre** → [`docs/release-checklist.md`](docs/release-checklist.md).
- **El tablero de trabajo en curso** → [`tareas.md`](tareas.md).

Lo que sigue es lo que faltaba tener por escrito: parámetros de referencia del proyecto,
la convención de commits, cómo se arman los IDs de `tareas.md` y qué tipo de documento
usar para qué. Cualquier agente lo edita cuando detecta una convención real y no
registrada; un cambio de fondo (no una aclaración) lo decide el owner.

## Parámetros del proyecto

| Parámetro | Valor |
| --- | --- |
| Paquete instalable | `movie-inbox` (`src/movie_inbox`) |
| Repositorio | `github.com/pasaporteN25/MovieCache`, remoto `origin` por SSH |
| Repo relacionado | `../movieIndexAndroid` — cliente Android autónomo, tablero propio; consume `/api/v1/` de este repo ([ADR-0005](docs/adr/0005-mobile-direction.md)) |
| Licencia | GPLv3 (`LICENSE`) |
| Owner | Lucas — decide producto, corre el QA manual de release y hace la fusión/tag a `master` |
| Idioma | Español rioplatense en docs, `tareas.md`, mensajes de commit y comentarios; identificadores y código en inglés |
| Rama estable | `master` — sólo recibe merge commits de cierre de versión, nunca commits directos |
| Rama de desarrollo | `release/X.Y.Z` — vive mientras esa versión está abierta; ver "Versionado" abajo |
| Versionado | `X.Y.Z`, tag anotado `vX.Y.Z` sobre el merge commit de cierre (`git tag -a vX.Y.Z -m vX.Y.Z`) |

## Convención de commits

```
<tipo>: <descripción imperativa, en minúscula> [<ID de tarea>]
```

Tipos en uso: `feat`, `fix`, `docs`, `test`, `chore`, `style`, `refactor`. El `[ID]` entre
corchetes va cuando el commit avanza o cierra una tarea de `tareas.md` (ej.
`feat: add revocable device sessions [A1.2]`); un commit puramente mecánico (release,
formato) no lleva ID. Nunca se hace `--amend` salvo pedido explícito, y una rama de
release nunca se fusiona con squash ni rebase — ver
[`docs/release-checklist.md`](docs/release-checklist.md) §8.3, porque otros documentos
citan hashes de commits de esa rama.

## Convención de IDs en `tareas.md`

Formato: `[LETRA#]` identifica una tarea de nivel de iniciativa; `[LETRA#.#]` un paso
dentro de ella; desgloses más finos siguen con un número o letra más
(`D1.1`, `W3.1`, `V9.V1`, `U2-R.0`). El sufijo `-P` (visto en `[U2-P]`) marca un paso que
es puramente del frente visual dentro de una iniciativa mixta.

**Una letra identifica una iniciativa, no un tema fijo para siempre.** Se reutiliza
mientras esa iniciativa sigue viva —a veces durante semanas y varias versiones—, y se
elige una letra nueva (no necesariamente la siguiente del abecedario) sólo para algo
genuinamente distinto de lo que ya está abierto. No hay un registro central: se infiere
leyendo los headers `#### [LETRA...]` de `tareas.md`, que es la fuente viva. La tabla de
abajo es una foto para orientarse, tomada el 2026-09-24 — confirmá en `tareas.md` antes
de asumir que una letra sigue significando lo mismo o sigue libre.

| Letra | Iniciativa (uso observado) |
| --- | --- |
| A | API de dispositivo v1 / origen del cliente Android (`A2` se mudó a `movieIndexAndroid`) |
| B | Motor de búsqueda y colecciones |
| C | Resolución N-a-1 de grupos de duplicados |
| D | Despliegue HTTPS/proxy |
| E | Cobertura y extracción de metadata (Wikipedia, Wikidata, FilmAffinity) |
| F | Fuentes externas: índice local de IMDb, anime/Jikan, TMDb |
| H | Higiene de repositorio (archivos trackeados por error) |
| I | Integraciones evaluadas y postergadas (Radarr, Sonarr, Letterboxd) — cerrada |
| L | Reglas de exclusión de bibliotecas |
| M | Verticales nuevas (juegos, música) |
| MW | Mobile web (revisión en navegador de celular) |
| P | Privacidad del scanner / compartir disponibilidad como colección de Club |
| Q | Refinamiento de búsqueda multilenguaje y del comparador |
| S | `S1`/`S2`: purga del historial. `S0`: Search Lab (ranking intercambiable) — ambos cerrados |
| T | Tipado estricto por capas (mypy) |
| U | Evolución visual de Home — todo el frente visual vive acá |
| V | **Excepción a la regla**: `V5` es curación (aria-live, buscador, teclado en la cola); `V9` es el cierre de la versión 0.9.0. No asumas que comparten tema |
| W | Presentación pública, paquetes e intercambio entre homeservers |
| X | API de dispositivo — sync, sesiones, removals, drafts offline, ids durables por fuente |

## Qué tipo de documento usar

| Documento | Para qué | No para |
| --- | --- | --- |
| `docs/adr/000N-titulo.md` | Una decisión de arquitectura o producto, con su evidencia y sus condiciones de reversión | Una tarea concreta sin decisión de rumbo detrás — eso es `tareas.md` |
| `docs/briefs/nombre.md` | El contrato de entrega de un incremento: qué se construye, contrato de API/datos, criterios de aceptación | Una evaluación todavía abierta — eso es `docs/analisis/` |
| `docs/analisis/AAAA-MM-DD-tema.md` | Una evaluación medida de una alternativa o de una superficie existente, insumo para decidir | Anunciar una decisión ya tomada — una vez decidida, el rumbo va a un ADR |
| `docs/design/...` | Auditoría o evidencia visual: capturas, criterios de aceptación del owner sobre el frente visual | Contrato de datos o de API — eso es un brief |
| `tareas.md` | El tablero vivo: toda tarea concreta, su estado y su commit de cierre | Documentación que sobrevive al cierre de la tarea — si hace falta, va a uno de los de arriba y `tareas.md` lo enlaza |
| `CHANGELOG.md` | Sólo lo que le importa a quien actualiza o usa la instancia | Decisiones de proceso interno — eso es este documento o `tareas.md` |
| `SDD.md` (este archivo) | Convenciones y parámetros de trabajo entre agentes | Producto, diseño o decisiones técnicas puntuales — esos ya tienen su propio documento |
