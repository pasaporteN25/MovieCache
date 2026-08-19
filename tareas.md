# Tareas — Movie Inbox

Tablero en Markdown, versionado en el repo. Columnas = estado (`Backlog` / `En curso` /
`Hecho`). Dentro de `Backlog`, las tareas se agrupan por frente. Cada tarea tiene alcance
de archivo/línea concreto, dependencias explícitas y un nivel de modelo sugerido —
mecánica de un solo archivo sin decisiones → chico; pocos imports cruzados ya resueltos →
medio; requiere criterio, coordina 3+ archivos o toca semántica sutil (matching,
identidad) → grande. Nunca asignar una tarea de "requiere criterio" a un modelo chico.

Al cerrar una tarea: moverla a `Hecho` con fecha y commit, no borrarla. Al abrir un frente
nuevo (Integraciones, Landing, lo que sea), agregar una sección `### Frente: X` nueva acá
mismo — este archivo es el tablero completo, no uno por fase.

---

## Backlog

### Frente: Enriquecimiento y cobertura de links externos

Investigado a fondo en sesión 2026-08-18. Causa raíz confirmada con líneas exactas: hoy
un ítem nunca puede terminar con más de 1 de los 3 links (IMDb/Wikipedia/FilmAffinity)
por dos bugs estructurales independientes en `match_external_links.py`, no por falta de
cobertura de las fuentes en sí.

#### [E1] Función real de cobertura 0–3 (no booleana)
- **Archivos**: `src/movie_inbox/domain/catalog.py` — agregar cerca de `has_external_link`
  (línea 293-294).
- **Qué hacer**: nueva función (ej. `linked_sources(item) -> set[str]` o
  `external_link_coverage(item) -> int`) que chequee `wikipedia_url`, `imdb_url` y
  `filmaffinity_url` de forma independiente vía `trusted_external_url()` — no el campo
  genérico `url`, y no `external_urls()` tal cual (es un set por URL canónica, no por
  fuente, así que no da un 0–3 limpio). `CatalogItem` ya tiene los 3 campos
  (`domain/models.py` líneas 134-136), sin cambio de schema necesario para esta parte.
- **Depende de**: —
- **Modelo sugerido**: Chico/Medio (Claude Haiku, o Codex equivalente). Un solo archivo,
  patrón ya existente al lado (`has_external_link`) para copiar, sin decisiones de
  diseño reales.
- **Verificación**: test unitario nuevo al lado de donde ya se prueba `has_external_link`
  (buscar sus usos en `tests/` para ubicar el archivo correcto).

#### [E2] Arreglar el gate de enlaces múltiples en `match_external_links.py`
- **Archivos**: `src/movie_inbox/cli/match_external_links.py` líneas 71-100 (el loop
  principal y el merge de candidatos).
- **Qué hacer** — dos bugs juntos, es el mismo fix:
  1. Línea 72: `if has_external_link(item): continue` salta el ítem apenas tiene 1 link.
     Cambiar a `if external_link_coverage(item) >= objetivo: continue` (de [E1]), donde
     `objetivo` es configurable (mínimo IMDb+Wikipedia = 2, ideal = 3, según lo que
     pediste).
  2. Líneas 81-100: `rank_candidates()` ordena candidatas de las 3 fuentes juntas y solo
     se mergea `candidates[0]` — si Wikipedia e IMDb aciertan en la misma corrida, se
     descarta una. Hay que agrupar candidatas aceptadas por fuente y mergear la mejor de
     **cada** fuente que todavía falte, no solo la mejor global.
- **Depende de**: [E1]
- **Modelo sugerido**: Grande (Claude Sonnet/Opus). Requiere criterio real: cómo agrupar
  por fuente sin romper el orden de `rank_candidates`, qué pasa si una fuente da varias
  candidatas parciales, interacción con el gate conservador de `decide_match` (no tocar
  ese gate — invariante 3 del proyecto).
- **Verificación**: `match_external_links.py` no tiene NINGÚN test hoy (solo el chequeo
  de layering en `tests/test_layering.py`). Esta tarea debe agregar el primer test de
  extremo a extremo — hay dos patrones ya usados en el repo para copiar: el de
  `tests/test_curation.py` (repositorio + tempdir) o el de fake-gateway de
  `tests/test_external_service.py`.

#### [E3] Reportar cobertura en `movie-inbox db info`
- **Archivos**: `src/movie_inbox/cli/database.py`, función `show_info()` (líneas
  153-166).
- **Qué hacer**: agregar líneas de conteo — con Wikipedia / con IMDb / con FilmAffinity /
  con los 3 / sin ninguno — usando [E1]. Mismo lugar donde ya se imprimen `Items`,
  `Series`, `Local files`.
- **Depende de**: [E1]
- **Modelo sugerido**: Chico. Puramente aditivo, un archivo, sigue un patrón visible en
  el mismo archivo.

#### [E4] Exponer cobertura en Curaduría y en `/api/items`
- **Archivos**: `src/movie_inbox/application/curation_service.py`
  (`build_curation_payload`/`curation_counts`, líneas 18-31 y 71-90),
  `src/movie_inbox/web/routers/catalog.py` (línea 84, hoy solo loguea `with_link`, no
  va en la respuesta JSON de líneas 98-110).
- **Qué hacer**: sumar un bucket nuevo (ej. `partial_link`, distinto de `missing_link`
  que ya existe) para ítems con 1 o 2 de 3 fuentes, y agregar el conteo/cobertura a la
  respuesta de `/api/items` (hoy no viaja, solo se loguea).
- **Depende de**: [E1]
- **Modelo sugerido**: Medio. Dos archivos, pero el patrón de `missing_link` ya existente
  en `curation_service.py` es la plantilla directa a seguir.

#### [E5] Extraer sinopsis completa de Wikipedia (hoy solo la intro)
- **Archivos**: `src/movie_inbox/external/wikipedia.py`,
  `fetch_wikipedia_metadata()`/`fetch_wikipedia_metadata_action_api()` (líneas 207-294).
- **Qué hacer**: hoy todo pasa por `exintro=1` / el REST summary, que da solo el párrafo
  introductorio (`wikipedia_extract`). La sinopsis completa (sección "Argumento"/"Plot")
  nunca se lee, aunque `PRODUCT.md` línea 114 ya asume que Inicio puede mostrar obras
  "con sinopsis". Cambiar a traer el artículo completo (mismo llamado, sin `exintro=1`,
  o `action=parse` con búsqueda de sección) y parsear la sección de sinopsis. Es una
  sola llamada, no una nueva — no agrega costo de red.
- **Depende de**: —
- **Modelo sugerido**: Medio/Grande. Un archivo, pero parsear secciones de wikitext/HTML
  tiene casos borde reales (nombres de sección varían: "Argumento", "Sinopsis", "Plot").
- **Verificación**: `tests/test_external_metadata.py` ya cubre este archivo — extender
  ahí.

#### [E6] Extraer campos gratis del Wikidata ya descargado
- **Archivos**: `src/movie_inbox/external/wikidata.py`, `fetch_wikidata_metadata()`
  (líneas 20-53), `WIKIDATA_LIST_FIELDS` (líneas 12-17).
- **Qué hacer**: el JSON completo de la entidad Wikidata ya se descarga por cada
  enrichment, pero solo se leen 4 propiedades (género/director/guionista/reparto). Sin
  llamada de red nueva se puede sumar duración (P2047), país (P495), idioma original
  (P364), productor (P162), compositor (P86) — siguiendo el mismo patrón de
  `WIKIDATA_LIST_FIELDS` ya existente.
- **Depende de**: — (pero **antes de implementar, confirmar conmigo** si estos campos
  necesitan entrar al schema de `CatalogItem`/`catalog.schema.json` o si alguno ya
  existe sin usar, como pasó con `backdrop_image`/`tmdb_id` — no asumir schema nuevo sin
  chequear primero).
- **Modelo sugerido**: Chico/Medio para la extracción en sí (patrón mecánico a repetir);
  Medio para la parte de schema si hace falta agregar campos.

---

### Frente: Search Lab — comparación baseline vs. candidato

Investigado a fondo en sesión 2026-08-18. A diferencia del frente de arriba, acá **no
hay bug que arreglar** — es una funcionalidad nueva, y hoy no existe ningún gancho para
construirla: el nombre `"production-baseline"` está hardcodeado como string literal en
dos lugares (`application/search_evaluation.py` líneas 40 y 88), afirmado por un test
(`tests/test_search_lab.py` línea 31), y `search-lab run` llama directo a las mismas
funciones de producción — no hay parámetro de algoritmo, flag de CLI, feature flag ni
config alternativa en ningún lado.

Decidido en sesión 2026-08-18: no el dict mínimo de overrides (cubría solo las 3
constantes de `domain/search.py`, dejaba el contexto `scanner` completo sin poder
compararse). Se eligió una función de ranking realmente intercambiable. La sesión de
Plan mode que el tablero pedía se hizo en esa misma sesión — el resultado son las 4
tareas ordenadas de abajo, ya ejecutables. Diseño resuelto: un objeto `SearchStrategy`
(dataclass de campos numéricos con nombre, no callables) que fluye como parámetro
opcional hacia abajo por `domain/search.py`, `domain/matching.py`,
`application/search_service.py` y `application/search_evaluation.py`, con
`PRODUCTION_BASELINE` como default que preserva el comportamiento actual byte a byte.
Es "el dict de overrides" de la propuesta original, pero ampliado a las dos familias de
umbrales (scoring Y matching) en vez de solo una, expuesto como la implementación
*default* de una estrategia de verdad intercambiable — no descarta que a futuro alguien
reemplace `SearchStrategy` por una implementación con lógica propia, solo no hace falta
todavía. `inspect_catalog_search` sí recibe el mismo parámetro por consistencia interna
(barato una vez hecho S0-b), pero `search-lab inspect` no suma una superficie de CLI de
comparación — eso queda exclusivo de `search-lab compare` (S0-d), porque comparar dos
algoritmos sobre una query ad-hoc no tiene el mismo valor que sobre el corpus dorado.

#### [S0-a] Extraer los umbrales sueltos de ranking/matching a un objeto `SearchStrategy`
- **Archivos**: nuevo `src/movie_inbox/application/search_strategy.py`. Constantes de
  origen a copiar (todavía no se borran ni se conectan sus usos actuales, eso es S0-b):
  `domain/search.py` líneas 17/21/25 (`YEAR_MATCH_BONUS`/`YEAR_MISMATCH_PENALTY`/
  `EXTERNAL_RELEVANCE_THRESHOLD`), `domain/matching.py` línea 76 (`0.75`, umbral de
  `similar_title_requires_review`) y líneas 122-125 (`0.18`/`-0.35`/`0.08` de
  `candidate_score`), `application/search_service.py` líneas 42 y 83 (el `28` de
  admisión), `application/search_evaluation.py` línea 343 **y**
  `application/library_service.py` línea 647 — el mismo `0.72` duplicado en dos
  archivos hoy (cambiar uno sin el otro ya es un bug latente, independiente de esta
  tarea).
- **Qué hacer**: dataclass congelado `SearchStrategy` con un campo nombrado por cada
  número de arriba (ej. `year_match_bonus: float = 12.0`,
  `similar_title_review_threshold: float = 0.75`, `scanner_review_floor: float = 0.72`)
  más `name: str = "production-baseline"`. Instancia de módulo
  `PRODUCTION_BASELINE = SearchStrategy()` con los valores actuales exactos. Todavía NO
  se conecta a ninguna función real — esta tarea es puramente declarativa, cero cambio
  de comportamiento.
- **Depende de**: —
- **Modelo sugerido**: Chico/Medio. Mecánico — copiar números ya identificados a campos
  con nombre; el único criterio real es agruparlos con claridad.
- **Verificación**: test nuevo que compara cada campo de `PRODUCTION_BASELINE` contra el
  valor hardcodeado real citado arriba, para que este archivo no se desincronice del
  resto en tareas futuras.

#### [S0-b] Enhebrar `SearchStrategy` en las funciones de scoring y matching
- **Archivos**: `domain/search.py` (`text_match_score`, `external_result_score`),
  `domain/matching.py` (`decide_match`, `candidate_score`),
  `application/search_service.py` (`_catalog_search_score`, `search_catalog_items`,
  `rank_catalog_candidates`).
- **Qué hacer**: agregar un parámetro opcional `strategy: SearchStrategy =
  PRODUCTION_BASELINE` a cada una de estas funciones, reemplazando el número extraído en
  S0-a por `strategy.campo_correspondiente`. Ninguna debe cambiar de comportamiento con
  el default — la suite completa, incluido
  `test_search_lab.py::test_builtin_corpus_meets_the_v030_quality_gate` (fija métricas
  exactas), tiene que seguir pasando sin tocar un solo assert.
- **Depende de**: [S0-a]
- **Modelo sugerido**: Grande. Toca 3 archivos de semántica de matching/búsqueda a la
  vez; `domain/matching.py` sigue sin importar `domain/search.py` — cada módulo lee su
  propio subconjunto de campos de `SearchStrategy`, no hay que fusionarlos.
- **Verificación**: la suite completa sin cambios de expectativa es la prueba principal.
  Sumar 1-2 tests que pasen una `SearchStrategy` con un umbral distinto y confirmen que
  el resultado cambia (prueba de que el enhebrado funciona de verdad, no quedó un número
  hardcodeado atrás sin conectar).

#### [S0-c] Hacer que `evaluate_search_corpus` y el Scanner de verdad acepten una estrategia
- **Archivos**: `application/search_evaluation.py` (`evaluate_search_corpus` líneas
  27-52, `inspect_catalog_search` líneas 55-98, `_evaluate_case` línea 213,
  `_external_results` línea 292, `_scanner_results` línea 331),
  `application/library_service.py` (`ManagedLibraryService._classification`, línea 623).
- **Qué hacer**: agregar `strategy: SearchStrategy = PRODUCTION_BASELINE` a
  `evaluate_search_corpus` **e** `inspect_catalog_search` (las dos hardcodean
  `"algorithm": "production-baseline"` hoy, líneas 40 y 88 — no solo la primera),
  enhebrarlo hacia `_evaluate_case`/`_external_results`/`_scanner_results`, y reemplazar
  el string fijo por `strategy.name`. El punto delicado es `_scanner_results`: llama a
  `ManagedLibraryService._classification(None, candidate, index)`, que es la lógica REAL
  del Scanner en producción (no un espejo de prueba) y tiene su propio `0.72` en la
  línea 647. Agregarle el mismo parámetro opcional `strategy` a `_classification`
  (default `PRODUCTION_BASELINE`, cero cambio de comportamiento para el Scanner real) y
  usarlo tanto ahí como en `_scanner_results` — de paso deja de haber un `0.72`
  duplicado en dos archivos.
- **Depende de**: [S0-b]
- **Modelo sugerido**: Grande. `_classification` es código de producción real (la cola
  del Scanner), no solo de Search Lab — el default tiene que ser un no-op verificable, y
  hay que revisar que ninguna otra llamada existente a `_classification` se vea afectada.
- **Verificación**: `tests/test_search_lab.py:31` (fija `report["algorithm"] ==
  "production-baseline"`) sigue pasando con el default, más un test nuevo que corra con
  una `SearchStrategy` distinta y confirme que `report["algorithm"]` cambia. Correr
  también la suite de Scanner/`library_service` existente sin cambios de expectativa,
  para confirmar que el comportamiento real del Scanner no se movió.

#### [S0-d] Subcomando de comparación y reporte HTML de 2 columnas
- **Archivos**: `cli/search_lab.py` (nuevo subcomando y `render_html_report`), un nuevo
  lugar para estrategias candidatas de ejemplo (a definir en la tarea, ej. JSON sueltos
  bajo `search_lab/`).
- **Qué hacer**: un candidato se define como datos — un JSON con los mismos campos que
  `SearchStrategy`, todos numéricos, sin código — cargable con `--candidate ruta.json`.
  `movie-inbox search-lab compare --candidate ruta.json` corre el corpus dorado dos
  veces (baseline y candidato) y arma un reporte con las métricas de ambos lado a lado
  por contexto (`catalog`/`identity`/`external`/`scanner`) más una columna de
  diferencia. HTML de 2 columnas siguiendo el estilo ya existente de
  `render_html_report`. `search-lab run`/`search-lab inspect` no cambian su interfaz —
  la comparación es exclusiva del nuevo subcomando.
- **Depende de**: [S0-c]
- **Modelo sugerido**: Grande. Nuevo subcomando de CLI, nuevo schema de reporte, HTML
  nuevo — superficie grande aunque cada pieza sea mecánica una vez que S0-c ya expone
  `strategy` en `evaluate_search_corpus`.
- **Verificación**: test de extremo a extremo en `tests/test_search_lab.py` que corra
  `search-lab compare` con un JSON de candidato de prueba (ej.
  `external_relevance_threshold` más bajo) contra el corpus dorado y confirme que el
  reporte trae ambas columnas y que al menos una métrica difiere entre baseline y
  candidato.

---

## En curso

*(vacío)*

## Hecho

#### [E8] Unificar el gate de Wikipedia por título en `decide_match`
`fetch_wikipedia_by_title()`/`fetch_wikipedia_by_wikidata_title()` en
`external/wikipedia.py` pasaron de `wikipedia_match_score() >= 3` a juntar
candidatas y decidir con `decide_match` (mismo gate conservador que
`match_external_links.py`). Los 3 llamadores reales (`enrich`, `import`, el
auto-enrich en vivo de la webapp) heredan el fix sin cambios propios.
`wikipedia_match_score`/`normalize_match_text`/`strip_html` quedaron sin uso
y se borraron. 4 tests nuevos en `tests/test_external_metadata.py`.
2026-08-18, commit `d29b3bb`.

#### [E7] FilmAffinity: fetch de metadata dedicado
`fetch_filmaffinity_metadata(url)` nuevo en `external/filmaffinity.py` lee
el microdata schema.org de la ficha (género, reparto, dirección, guion,
sinopsis, título original), verificado contra una página real
(`film267267.html`, Heat 1995) capturada en vivo, no markup asumido.
Conectado en `fetch_metadata()`. La nota media del sitio está disponible en
el HTML (`content="7.5"`) pero deliberadamente no se trae: `CatalogItem.rating`
es el puntaje personal 0-10, no hay campo de "nota externa" en el schema
todavía. Primer fixture y primeros tests del archivo, en
`tests/test_external_filmaffinity.py`.
2026-08-18, commit `8176477`.

*(mover acá con fecha y commit al cerrar)*
