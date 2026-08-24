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

*(vacío)*

---

## En curso

*(vacío)*

## Hecho

### Frente: Enriquecimiento Wikidata

#### [E6] Extraer campos gratis del Wikidata ya descargado
La opción B incorpora los cinco campos acordados: `duration_minutes` desde P2047,
`countries` desde P495, `original_languages` desde P364, `producers` desde P162 y
`composers` desde P86. Duración es un entero positivo opcional en minutos; los otros
cuatro campos son listas multivalor. La extracción reutiliza la entidad y el batch de
labels existentes, respeta rangos preferidos, convierte minutos/segundos/horas y no
entra en la evidencia de identidad ni en el ranking de búsqueda.

Los campos atraviesan `CatalogItem`, procedencia y bloqueos, merge manual/automático,
API, importación y exportación. El contrato portable migra de JSON v6 a v7 con defaults
sin pérdida y SQLite migra de v4 a v5 con una columna nullable para la duración; las
listas reutilizan `metadata_values`. Verificado con 325 pruebas unitarias, 13 pruebas
reales de navegador, Ruff, mypy, compilación y Search Lab en verde.
2026-08-24, commit `9f9ebb2`.

### Frente: Cierre de coherencia de interfaz (v0.5.0)

Los 4 hallazgos que dejo el gate de cierre de Fase 5 (critica del 2026-08-22, 29/40)
tenian un ranking de mas simple a mas dificil. Los 2 mas dificiles (historial/deshacer
de Scanner, desambiguar duplicados) ya estan cerrados — ver `docs/roadmap.md` y las
entradas fechadas 2026-08-22 en `prompt-movie-inbox.md`. Los 2 mas simples y el caso
borde que la fase de desambiguacion dejo explicitamente pendiente quedaron cerrados en
este incremento. Los 4 se agrupan aca como el contenido de v0.5.0 (ver
`docs/roadmap.md`) — un incremento chico a proposito, para probar bien lo construido en
v0.4.0 antes de seguir.

#### [V5-1] `aria-live` en el estado de decision del comparador de fusion
- **Archivos**: `src/movie_inbox/web/static/index.dialogs.html` (lineas 276-289, el
  `<footer class="merge-comparator-footer">` del dialogo de fusion).
- **Que hacer**: envolver el `<div>` de la linea 281 (que contiene `#mergeDecisionStatus`
  y `#mergeDecisionMeta`, ambos actualizados juntos desde `core/merge.js`) con
  `aria-live="polite"` en ese mismo `<div>` — no en cada hijo por separado, para que un
  lector de pantalla anuncie un solo cambio combinado en vez de dos anuncios sueltos.
  Mismo patron que ya usa `#mergeComparatorFeedback` cuatro lineas arriba (linea 277,
  tambien `aria-live="polite"`) — copiar ese criterio, no inventar uno nuevo. Agregar
  ademas `aria-describedby="mergeDecisionStatus"` al boton `#confirmReviewedMerge`
  (linea 287) para que un lector de pantalla enfocado en el boton conozca el estado
  actual de la decision. No hace falta tocar `core/merge.js`: el contenido ya se
  actualiza via `textContent`, alcanza con marcar el contenedor una vez.
- **Depende de**: —
- **Modelo sugerido**: Chico. Dos atributos HTML, patron ya usado 4 lineas arriba en el
  mismo archivo, sin logica nueva.
- **Verificacion**: `scripts\check.ps1` en verde; confirmar a mano en el navegador que
  el atributo sobrevive despues de que `merge.js` reemplaza el `textContent` del `<div>`.
- **Cierre**: el estado combinado usa una unica region `aria-live` y el boton final la
  referencia con `aria-describedby`; cubierto por HTTP y Playwright real.
  2026-08-24, commit `ad53ec9`.

#### [V5-2] Buscador de texto libre en la cola de Curaduria
- **Archivos**: `src/movie_inbox/web/static/index.inbox-curation.html` (nav de tabs,
  lineas 2-18, agregar el input ahi), `src/movie_inbox/web/static/js/core/fields.js`
  (registrar el campo, junto a `curationQueue` en la linea 113),
  `src/movie_inbox/web/static/js/core/bootstrap.js` (wireo, junto a la linea 175),
  `src/movie_inbox/web/static/js/surfaces/inbox-curation.js` (`visibleCurationCases()`
  linea 268, nueva funcion `searchCurationQueue`), `src/movie_inbox/web/static/css/curation.css`.
- **Que hacer**: Scanner ya tiene exactamente este patron resuelto — `#scannerQueueSearch`
  (`index.inbox-scanner.html:27-30`, un `<label class="scanner-queue-search">` con
  `<span class="sr-only">` + `<input type="search">`), el estado `scannerQueueQuery`
  (`inbox-scanner.js:22`), el filtro por texto dentro de `visibleScannerQueue()`
  (`inbox-scanner.js:242-258`, normaliza con `normalizeText` y compara contra
  titulo/año/tipo/nombre de archivo/ruta/biblioteca) y `searchScannerQueue(event)`
  (`inbox-scanner.js:268-271`) wireado en `bootstrap.js:180`. Portar el mismo patron a
  Curaduria 1 a 1: agregar el mismo bloque de input (adaptando la clase a
  `.curation-queue-search` y el id a `curationQueueSearch`) dentro de
  `index.inbox-curation.html`, cerca de la nav de tabs; agregar
  `export let curationQueueQuery = "";` en `inbox-curation.js`; sumar el mismo filtro
  por texto dentro de `visibleCurationCases()` (que hoy solo filtra por
  `curationFilter`, no por texto) usando los campos disponibles de `entry.primary`
  (titulo, año, tipo) — mirar `curationQueueItem()` en la linea 394 para confirmar que
  campos trae cada `entry`; agregar `searchCurationQueue(event)` identica a la de
  Scanner; registrar el campo en `fields.js` y wirear el evento `input` en
  `bootstrap.js`, junto a `handleCurationClick`. En CSS, copiar la regla
  `.scanner-queue-search` de `scanner.css` adaptada a `.curation-queue-search` en
  `curation.css`.
- **Depende de**: —
- **Modelo sugerido**: Medio. Mecanico y con un patron de referencia completo ya
  funcionando, pero toca 5 archivos distintos.
- **Verificacion**: catalogo sintetico con varios casos en Curaduria, confirmar que
  escribir en el buscador filtra la cola igual que en Scanner, incluidos los acentos
  (`normalizeText` ya los maneja). `scripts\check.ps1` en verde.
- **Cierre**: busqueda por titulo, ano y tipo portada desde Scanner, con prueba de
  navegador que encuentra `Akira` al escribir `akira` sin acento.
  2026-08-24, commit `ad53ec9`.

#### [V5-3] Navegacion por flechas del teclado en la cola de Curaduria
- **Archivos**: `src/movie_inbox/web/static/js/surfaces/inbox-curation.js` (nueva
  `moveCurationQueueSelection`, nueva `focusSelectedCurationItem`),
  `src/movie_inbox/web/static/js/core/bootstrap.js` (wireo, junto a la linea 175),
  `src/movie_inbox/web/static/css/curation.css` (confirmar que ya alcanza con el
  `:focus-visible` de `.curation-queue-item` que el pase de `polish` de Fase 5 ya
  agrego — no deberia hacer falta CSS nuevo).
- **Que hacer**: portar `moveScannerQueueSelection`/`focusSelectedScannerItem`
  (`inbox-scanner.js:281-296`) a Curaduria, reusando el estado que ya existe ahi
  (`curationFilter`, `selectedCurationCaseId`, `visibleCurationCases()`,
  `renderCuration()`, `curationHistory` — no hace falta crear ninguno nuevo). Ojo con
  un detalle: la fila de Curaduria marca "seleccionada" con la clase `selected`
  (`curationQueueItem()`, linea 402: `` `curation-queue-item ${selected ? "selected" :
  ""}` ``), **no** `active` como en Scanner — `focusSelectedCurationItem` tiene que
  buscar `.curation-queue-item.selected`; copiar el selector de Scanner tal cual haria
  foco en el elemento equivocado (ninguno, silenciosamente, sin error visible). Igual
  que `moveScannerQueueSelection` resuelve para la pestaña "Actividad"
  (`scannerQueueFilter === "history" ? scannerHistory : visibleScannerQueue()`), la
  version de Curaduria tiene que ramificar sobre `curationFilter === "history"` con
  `curationHistory` — Scanner tuvo un bug real por olvidar esta rama (ver la entrada
  fechada 2026-08-22 en `prompt-movie-inbox.md`), no repetirlo aca. Wirear `keydown`
  sobre `fields.curationQueue` (no sobre `fields.inboxView`, que ya tiene el `click`
  generico) en `bootstrap.js`.
- **Depende de**: — (independiente de [V5-2]; si se resuelven en sesiones distintas,
  avisar de todas formas que ambas tocan `bootstrap.js` y `fields.js` para evitar un
  conflicto de merge chico).
- **Modelo sugerido**: Medio. Sin decisiones de diseño pendientes (ya se decidio aca
  duplicar el patron de Scanner adaptado, no generalizar un helper compartido — la
  cantidad de estado especifico de cada modulo no lo justifica), pero hay que prestar
  atencion a los 2 detalles señalados arriba para no introducir un bug silencioso.
- **Verificacion**: catalogo sintetico con 3+ casos en Curaduria, confirmar que las
  flechas mueven la seleccion igual que en Scanner, incluida la pestaña "Actividad".
  `scripts\check.ps1` en verde.
- **Cierre**: flechas verticales y horizontales recorren circularmente pendientes e
  historial, conservando foco sobre `.curation-queue-item.selected`; verificado en
  ambas ramas con Playwright. 2026-08-24, commit `ad53ec9`.

#### [V5-4] Señal de respaldo cuando archivo, fuente y fecha tambien empatan entre duplicados
- **Archivos**: `src/movie_inbox/web/static/js/surfaces/inbox-curation.js`
  (`curationQueueItem()` linea 394, `curationRecord()` linea 472),
  `src/movie_inbox/web/static/js/core/merge.js` (`renderMergeComparator()` linea 157,
  `mergeEntrySummary()` linea 199).
- **Que hacer**: caso borde dejado pendiente al cerrar la fase de desambiguacion de
  duplicados (ver la entrada fechada 2026-08-22 en `prompt-movie-inbox.md`): cuando dos
  casos duplicados con mismo titulo/año ademas comparten archivo local, fuente y fecha
  de alta, las 3 señales que ya se muestran no alcanzan para diferenciarlos. Si ademas
  todos los campos personales coincidieran, "Resolver duplicados claros" ya los
  fusiona solos sin que el usuario los vea — asi que este caso solo aparece cuando hay
  un conflicto real de datos personales (ej. dos puntajes distintos) y el usuario
  necesita alguna forma de saber cual fila es cual. Resolucion propuesta: cuando las 3
  señales existentes coinciden por completo entre los dos lados de un caso, agregar un
  ultimo recurso puramente posicional — "Duplicado 1 de 2" / "Duplicado 2 de 2" (o
  redaccion similar), calculado en el momento segun el orden en que ya llegan
  agrupados, sin necesidad de guardar ningun id nuevo. Mostrar esta numeracion
  unicamente cuando las 3 señales coinciden por completo — si al menos una difiere, no
  hace falta.
- **Depende de**: —
- **Modelo sugerido**: Medio. Toca los mismos 4 puntos de renderizado que la fase 1 de
  desambiguacion (mismo patron, mismo estilo de cambio aditivo), pero la regla de
  producto ya esta decidida aca.
- **Verificacion**: catalogo sintetico con 2 "Heat" identicas en archivo/fuente/fecha
  pero con rating distinto (9 y 3) — confirmar que la cola y el comparador muestran
  ahora una numeracion en vez de dos filas indistinguibles. `scripts\check.ps1` en
  verde.
- **Cierre**: el fallback `Duplicado 1 de 2` / `Duplicado 2 de 2` aparece unicamente
  cuando empatan las tres senales, en cola, detalle, titulo y resumen del comparador;
  verificado con un par sintetico de `Heat`. 2026-08-24, commit `ad53ec9`.

---

### Frente: Higiene de repositorio

Encontrado al mover `scripts/` a `codigoLegacy/` en la sesion del 2026-08-22 (ver
`prompt-movie-inbox.md`), marcado pero no tocado en su momento por estar fuera del
pedido puntual de esa sesion. Las 3 tareas son independientes entre si.

#### [H1] Borrar `check-output.txt` (salida de instalacion vieja, trackeada por error)
- **Archivos**: `check-output.txt` (raiz del repo, ~770 KB), `.gitignore`.
- **Que hacer**: confirmado leyendo el contenido — es la salida cruda de una corrida
  vieja de instalacion/tests (lineas de `pip install`, no datos personales),
  commiteada por accidente el 2026-08-10 (commit visible en `origin/master`).
  `git rm check-output.txt`; agregar `/check-output.txt` a `.gitignore` para que una
  futura corrida de `scripts\check.ps1`/`check.sh` que alguien redirija a ese nombre no
  lo vuelva a trackear.
- **Depende de**: —
- **Modelo sugerido**: Chico.
- **Nota**: ya esta en `origin/master`; borrarlo solo lo saca de commits futuros, sigue
  recuperable del historial si hiciera falta. No requiere reescribir historia.
- **Cierre**: archivo eliminado y `/check-output.txt` agregado a `.gitignore`.
  2026-08-24, commit `ad53ec9`.

#### [H2] Borrar `scripts/LICENSE` (duplicado exacto de `LICENSE`)
- **Archivos**: `scripts/LICENSE`.
- **Que hacer**: confirmado byte a byte identico a la `LICENSE` GPLv3 de la raiz
  (`diff` sin salida). Buscar primero si algo referencia esta ruta (`grep -r
  "scripts/LICENSE"` sobre el repo) — no deberia haber nada, pero confirmarlo antes de
  borrar. `git rm scripts/LICENSE`.
- **Depende de**: —
- **Modelo sugerido**: Chico.
- **Cierre**: hash identico confirmado, referencias revisadas y copia eliminada.
  2026-08-24, commit `ad53ec9`.

#### [H3] Cerrar el hueco de `.gitignore` que dejo trackeado un catalogo personal anidado
- **Archivos**: `.gitignore` (patrones `/scripts/*.json`, `/scripts/*.csv`,
  `/scripts/*.txt`).
- **Que hacer**: estos 3 patrones no alcanzan una subcarpeta anidada como
  `scripts/scripts/`, asi que `scripts/scripts/catalogv4.json` (catalogo personal
  real) quedo trackeado desde el commit `a21314a` (2026-08-01) y ya esta en
  `origin/master`. Cambiar los 3 patrones a su forma recursiva (`scripts/**/*.json`,
  `scripts/**/*.csv`, `scripts/**/*.txt`, sin la barra inicial, para que apliquen a
  cualquier profundidad) y correr `git rm --cached scripts/scripts/catalogv4.json`
  (sin `-f`, **sin abrir ni leer el archivo** — es dato personal real, la regla de
  `CLAUDE.md` aplica igual aca; el archivo sigue en disco, solo deja de trackearse).
  Revisar con `git ls-files scripts/` si este mismo hueco dejo pasar algun otro
  archivo personal anidado antes de dar la tarea por cerrada.
- **Depende de**: —
- **Modelo sugerido**: Chico — cambio de patron + `git rm --cached`, sin necesidad de
  abrir el archivo.
- **Importante, fuera del alcance de esta tarea**: esto solo detiene el tracking hacia
  adelante. El archivo sigue en el historial de git y ya llego a `origin/master` desde
  2026-08-01 — purgarlo de la historia (`git filter-repo` o similar) requiere reescribir
  historia y probablemente un force-push a un repo con datos personales ya expuestos en
  el remoto. Es una decision de Lucas, no de esta tarea — ver `docs/roadmap.md`.
- **Cierre**: patrones recursivos aplicados y el unico catalogo anidado que habia
  escapado dejo de estar trackeado sin abrirse ni borrarse del disco. La purga del
  historial sigue deliberadamente fuera de alcance. 2026-08-24, commit `ad53ec9`.

---

### Cerrado en sesiones anteriores

#### [E3] Reportar cobertura en `movie-inbox db info`
`show_info()` en `cli/database.py` suma 5 líneas nuevas usando `linked_sources()`/
`external_link_coverage()` de [E1]: con Wikipedia, con IMDb, con FilmAffinity, con
los 3, sin ninguno. Test nuevo en `tests/test_sqlite_repository.py` con un catálogo
sintético de 4 ítems (0/1/2/3 fuentes) que verifica las 5 líneas.
2026-08-19, commit `062f69b`.

#### [E4] Exponer cobertura en Curaduría y en `/api/items`
`build_curation_payload()` suma un bucket `partial_link` (ítems con 1 o 2 de 3
fuentes, vía `external_link_coverage()`), separado de `missing_link` (0 fuentes,
sin cambios). El router de `/api/items` ya calculaba `with_link`/`without_link`
para el log de la línea 84 pero no los incluía en la respuesta; ahora viajan bajo
una clave `links` nueva en el JSON. Test nuevo de `partial_link` en
`tests/test_curation.py` (4 ítems, 0/1/2/3 fuentes) y test HTTP nuevo en
`tests/test_view_http.py` para la clave `links` de `/api/items`.
2026-08-19, commit `062f69b`.

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
