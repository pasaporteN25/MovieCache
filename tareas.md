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

## En curso

*(vacío)*

## Hecho

#### [E3] Reportar cobertura en `movie-inbox db info`
`show_info()` en `cli/database.py` suma 5 líneas nuevas usando `linked_sources()`/
`external_link_coverage()` de [E1]: con Wikipedia, con IMDb, con FilmAffinity, con
los 3, sin ninguno. Test nuevo en `tests/test_sqlite_repository.py` con un catálogo
sintético de 4 ítems (0/1/2/3 fuentes) que verifica las 5 líneas.
2026-08-19, commit `<pendiente>`.

#### [E4] Exponer cobertura en Curaduría y en `/api/items`
`build_curation_payload()` suma un bucket `partial_link` (ítems con 1 o 2 de 3
fuentes, vía `external_link_coverage()`), separado de `missing_link` (0 fuentes,
sin cambios). El router de `/api/items` ya calculaba `with_link`/`without_link`
para el log de la línea 84 pero no los incluía en la respuesta; ahora viajan bajo
una clave `links` nueva en el JSON. Test nuevo de `partial_link` en
`tests/test_curation.py` (4 ítems, 0/1/2/3 fuentes) y test HTTP nuevo en
`tests/test_view_http.py` para la clave `links` de `/api/items`.
2026-08-19, commit `<pendiente>`.

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

#### [S0-a..d] Search Lab: ranking intercambiable (candidato vs. baseline) — frente cerrado
Las 4 tareas planificadas en la sesión anterior se implementaron en orden en
esta sesión, cada una verificada con `scripts\check.ps1` completo (284 tests
al cierre) antes de pasar a la siguiente. `domain/search_strategy.py` nuevo:
`SearchStrategy` (dataclass congelado, 9 umbrales con nombre) +
`PRODUCTION_BASELINE`, enhebrado como parámetro opcional por
`domain/search.py`, `domain/matching.py`, `application/search_service.py` y
`application/search_evaluation.py` — comportamiento default intacto,
verificado por la suite completa sin tocar un assert. El Scanner real
(`ManagedLibraryService._classification`) también acepta estrategia, sin
cambio de comportamiento para el Scanner en producción.
`movie-inbox search-lab compare --candidate ruta.json` nuevo, con reporte
JSON y HTML de 2 columnas; probado en vivo contra el corpus dorado, no solo
con tests.

Dos correcciones reales a la especificación original del tablero, encontradas
al implementar: `SearchStrategy` tenía que ir en `domain/`, no en
`application/` como decía la tarea — `domain/matching.py` lo necesita, y
`domain/` no puede importar `application/`. Y la lógica de comparar
(`compare_search_strategies`) fue a `application/search_evaluation.py`, no a
`cli/search_lab.py`, siguiendo el mismo patrón que ya usan
`evaluate_search_corpus`/`inspect_catalog_search`. También apareció una
tercera copia del `0.72` del Scanner (en `library_service.py::review_file`,
la confirmación manual de un candidato) que la investigación original no
había visto — quedó sincronizada contra
`PRODUCTION_BASELINE.scanner_review_floor`.
2026-08-19, commits `6ddab22` (S0-a), `7f67759` (S0-b), `2dabde9` (S0-c),
`37fe6bb` (S0-d).

#### [E1] Función real de cobertura 0–3 (no booleana)
`linked_sources(item)`/`external_link_coverage(item)` nuevos en
`domain/catalog.py`, reusando `KNOWN_LINK_HOSTS`/`source_url_field`/
`trusted_external_url` ya existentes en vez de hardcodear la lista de
fuentes aparte. 3 tests en `tests/test_matching.py`.
2026-08-19, commit `362c02c`.

#### [E2] Arreglar el gate de enlaces múltiples en `match_external_links.py`
Los dos bugs descritos eran reales: el loop pasó de `has_external_link`
(salta apenas hay 1 link) a `external_link_coverage(item) >=
args.target_coverage` (flag nuevo, default 3). Y
`merge_best_candidate_per_missing_source()` reemplazó el merge de solo
`candidates[0]` — ahora agrupa candidatas aceptadas por fuente y mergea la
mejor de cada fuente que todavía falta. Primer test de extremo a extremo del
archivo: un ítem sin links con Wikipedia e IMDb aceptados en la misma
corrida termina con ambos `wikipedia_url` e `imdb_url` (antes solo uno
sobrevivía). 5 tests en `tests/test_match_external_links.py` (nuevo).
2026-08-19, commit `c56aba6`.

#### [E5] Extraer sinopsis completa de Wikipedia
El endpoint REST summary que se probaba primero no puede devolver el
artículo completo bajo ningún parámetro — es estructuralmente un resumen.
`fetch_wikipedia_metadata()` unificado para usar `action=query` con el
artículo completo como único mecanismo (sigue siendo una sola llamada de
red). `_split_wikipedia_sections()`/`_find_synopsis_section()` nuevos en
`external/wikipedia.py` ubican la sección "Argumento"/"Plot"/"Sinopsis"
aprovechando que `explaintext=1` sin `exintro=1` conserva los marcadores
`== Título ==` como texto plano — incluye el caso de subsección anidada
(`===` dentro de una `==`), confirmado en vivo contra los artículos reales
de "Heat" y "El padrino". `infer_kind_from_text`/`infer_year` siguen
recibiendo solo la intro, no la sinopsis completa, para no arriesgar una
clasificación de tipo equivocada por una mención tardía ajena al género
real de la obra. Sin cambios de frontend — cada consumidor de
`wikipedia_extract` ya trunca o es una vista de detalle que se beneficia
directamente de una sinopsis más completa. 6 tests en
`tests/test_external_metadata.py`.
2026-08-19, commit `85ed572`.

*(mover acá con fecha y commit al cerrar)*
