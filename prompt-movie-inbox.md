# Prompt maestro — Movie Inbox

> Pegar tal cual en Claude Code, en la raíz del repo.
> Está pensado para varias sesiones: el agente hace una fase, para, y vos revisás.

---

Trabajás sobre **Movie Inbox**, un gestor self-hosted de catálogo audiovisual. Python +
FastAPI + SQLite, frontend vanilla sin build step. Versión estable v0.2.1, con v0.3.0 en
curso.

Antes de escribir una sola línea, leé estos archivos completos: `PRODUCT.md`, `DESIGN.md`,
`docs/roadmap.md`, `CHANGELOG.md` (sección `[Sin publicar]`), `tests/test_layering.py`,
`pyproject.toml` y `.github/workflows/tests.yml`. No son documentación decorativa: son
contratos vigentes y algunos están verificados por tests.

## Invariantes que no se negocian

Si una tarea parece exigir romper alguna de estas, **pará y preguntame** en vez de decidir
por tu cuenta.

1. **Layering.** `domain/` y `application/` no importan `infrastructure`, `external`, `web`
   ni `cli`. `tests/test_layering.py` lo verifica por AST.
2. **Terminología de PRODUCT.md.** `en_catalogo` (disponibilidad física) es independiente de
   `to_watch` y `watched`. Archivo físico, identidad compartida y ficha personal son tres
   cosas distintas y nunca se presentan como intercambiables.
3. **Matching conservador.** Una coincidencia dudosa requiere revisión humana. Descripción,
   review, reparto, género o tags nunca convierten una obra en candidata de identidad.
   Cero falsos positivos conocidos en auto-match es el gate de salida de v0.3.0.
4. **Privacidad.** Las vistas compartidas nunca exponen rutas, archivos locales, notas ni
   estado operativo. El owner no tiene excepción.
5. **Correcciones manuales y campos bloqueados** sobreviven a cualquier enriquecimiento
   posterior.
6. **JSON portable.** `catalog.schema.json` es un contrato versionado. SQLite es la fuente
   de verdad; JSON sigue siendo formato de importación, exportación y backup.

## Cómo quiero que trabajes

- **Una fase por sesión.** Al terminar una fase, pará y hacé un resumen de qué cambió y qué
  gate quedó verde. No arranques la siguiente sin que yo lo confirme.
- **Plan primero.** En fases 3, 4 y 5, entrá en plan mode y mostrame el plan antes de tocar
  archivos.
- **Verde antes de avanzar.** `python -m unittest discover -s tests` tiene que pasar al final
  de cada fase. Si una fase requiere romper un test temporalmente, decímelo explícitamente.
- **Commits chicos y atómicos**, con mensaje que explique el *por qué*. No commitees sin que
  yo lo pida.
- **Actualizá `CHANGELOG.md`** (sección `[Sin publicar]`) con cada cambio de comportamiento
  visible al usuario. Seguí el estilo que ya está: en español, orientado a lo que cambia para
  la persona, no a la implementación.
- Los archivos personales (`scripts/*.json`, `catalog*.json`, `.catalog-cache/`, `.movie-inbox/`)
  son datos reales míos. No los leas para "entender el dominio" ni los uses como fixtures.

---

## Gestión de tareas (a partir de 2026-08-18)

El trabajo más allá de esta fase (Enriquecimiento y cobertura de links, Search Lab, y lo
que se sume después — Integraciones, Landing) se trackea en `tareas.md` (raíz del repo),
un tablero en Markdown con columnas Backlog/En curso/Hecho, agrupado por frente, con
alcance de archivo/línea y nivel de modelo sugerido por tarea. Se eligió Markdown en vez
de un kanban autohosteado (se evaluó Kanboard) para no sumar infraestructura nueva que
mantener. Leerlo junto con este archivo al arrancar una sesión nueva.

## Progreso (actualizado 2026-08-22)

Fases 0, 1, 2, 3 y 4 cerradas. v0.3.0 publicado. **Fase 5 (v0.4.0) cerrada
por completo y publicada: tag `v0.4.0` creado (local, sin pushear todavía).**
Los 4 P1 (P1-c, P1-a, P1-b, P1-d), el P1 y P2 propios del intento de gate
(`--control-border`, caching HTTP), los 4 P3 (`extract`/`typeset`/`adapt`/
`polish`) y el gate final con puntaje (`$impeccable critique`, 29/40 contra
22/40 del 2026-08-14) están todos cerrados. `pyproject.toml`,
`src/movie_inbox/__init__.py`, `CHANGELOG.md`, `CLAUDE.md` y
`docs/roadmap.md` reflejan v0.4.0. `README.md` reescrito completo (estaba
desactualizado: no documentaba Scanner/Inventario en absoluto, terminología
vieja, faltaba `search-lab compare`) — ver detalle en la entrada de abajo.
Sesión nueva a partir de acá — no hace falta releer el historial de
conversación, esto + `CLAUDE.md` + `git log` alcanza.

También en esta sesión (2026-08-19), del tablero `tareas.md` (frente
Enriquecimiento y cobertura de links): `[E3]` y `[E4]` cerrados (commit
`062f69b`), y un bug suelto de la pasada de `extract` corregido — el
`rgba(69, 76, 120, .66)` de `catalog.css` que había quedado con el valor
viejo de `--control-border` (commit `bea4a43`). `[E6]` sigue en Backlog a
pedido de Lucas.

**Próximo incremento (sin fase/versión asignada todavía): cerrar los 4
hallazgos que dejó el gate de Fase 5.** Están rankeados de más simple a
más difícil (ver la entrada fechada 2026-08-22 más abajo para el detalle
técnico de cada uno) y la decisión es arrancar por el más difícil:

1. **Historial y deshacer para Scanner — cerrado.** Los 3 pasos (vincular
   a identidad existente `860c28a`, omitir `3829fd1`, crear y vincular —
   ver la entrada de abajo) están completos, probados y verificados en
   browser real. Era el más difícil de los 4 hallazgos y el único ya
   resuelto.
2. **Desambiguar casos duplicados con mismo título y año — cerrado, las
   2 fases.** Fase 1 (mostrar señales de fuente/fecha/archivo en la cola,
   el detalle y el comparador de fusión) y fase 2 (botón "Resolver
   duplicados claros": combina solo los pares sin conflicto real,
   reusando el motor de fusión existente sin lógica de decisión nueva —
   ver la entrada fechada 2026-08-22 más abajo). Quedan 3 puntos
   explícitamente pospuestos que no hay que perder: empate de fecha de
   agregado, grupos de 3+ duplicados, y visibilidad de archivos
   escaneados para miembros comunes — esto último requeriría relajar una
   invariante dura de privacidad, es una decisión de producto aparte.
3. Paridad de teclado/búsqueda en Curaduría respecto a Scanner.
4. `aria-live` en el estado de decisión del comparador de fusión — el más
   simple.

Las dos preguntas que habían quedado abiertas ya se resolvieron el mismo
2026-08-22: Lucas confirmó en un browser real que el diálogo de fusión sí
cierra con Escape (la hipótesis de limitación de la herramienta de testing
era correcta, no había bug) — el hallazgo queda retirado en firme, no
requiere ninguna acción. Y sobre `scripts/`: no se borró nada, pero los
lanzadores de compatibilidad con v0.1 y los shims de import se movieron a
`codigoLegacy/` (fuera de Git). Detalle completo de ambas resoluciones en
la entrada fechada 2026-08-22 más abajo.

**Desambiguar duplicados — fase 2 (árbol de auto-resolución), cierre del
hallazgo completo (2026-08-22).** Plan mode con un agente Explore para
las dudas de wireo (¿cruza `curation_workflow.py` con `curation_service.py`
hoy? ¿el `source_file` de un caso ya es una ruta real o un token de
referencia? ¿hay forma de leer todos los ítems del catálogo desde el
workflow service?) más lectura directa mía de `_default_choice()` en
`domain/merge_review.py`.

Hallazgo que simplificó toda la fase: `_default_choice()` (línea 240) ya
implementa "el valor no vacío gana" para **todo** campo del merge,
incluidos los personales protegidos, y `local_files`/`en_catalogo`
siempre se combinan. Un campo protegido solo exige una decisión humana
cuando ambos lados tienen un valor distinto y no vacío — un conflicto
real. Esto quiere decir que todo el árbol que habíamos diseñado a mano
con Lucas (idénticas → suprimir; difieren solo en un campo vacío →
combinar quedándose con el dato cargado; una con archivo y otra sin
archivo → combinar) **ya estaba implementado** en el merge existente.
La distinción "mismo archivo vs. archivo distinto" que habíamos discutido
dejó de hacer falta programarla aparte: alcanza con intentar
`merge(choices={})` sobre cada par pendiente — si no hay conflicto real
se aplica solo, si lo hay levanta `MergeReviewError` y cae al flujo
manual (ahora con toda la desambiguación visual de la fase 1). Cero
lógica de decisión nueva, todo el método nuevo
(`CurationWorkflowService.auto_resolve_duplicates`) es orquestación:
arma los casos pendientes con `build_curation_payload` (la función
pública, no la privada `_duplicate_cases`), intenta `compare()` +
`merge()` por par, cuenta éxitos y los que caen a revisión manual —
incluidos los que un merge anterior de la misma tanda ya resolvió (un
trío idéntico A/B/C: al combinar A+B, el intento posterior de A+C todavía
funciona porque A sigue igual, pero B+C falla con `CurationItemNotFound`
porque B ya no existe — se cuenta como "necesita revisión" sin romper el
resto del lote; confirmado exactamente así en un test y en vivo: 3
idénticos dan 2 resueltos y 1 a revisión, no 1 y 2 como pensé al
principio).

Detalle de plomería que hubo que resolver con el agente Explore, no
obvio de entrada: el `source_file` que ve el frontend en un caso de
`/api/curation` es un token de referencia ("source-1"), no una ruta real
— lo redacta `public_rows()` antes de que el caso llegue al navegador.
El método nuevo no puede reusar esos casos ya redactados; recibe
`items` ya cargados por el router (`load_items(catalog.config.patterns)`,
igual patrón que usa el router de scanner) con `_source_file` apuntando
a la ruta real, y arma los `CatalogPointer` desde ahí. También hubo que
mover `application/curation_workflow.py` a importar de
`application/curation_service.py` — cruce nuevo pero no un patrón nuevo,
`scanner_workflow.py` ya hace lo mismo con este archivo.

Botón nuevo "Resolver duplicados claros" al lado de "Actualizar bandeja"
en Curaduría, sin diálogo de confirmación previo (a diferencia de
"Omitir" o "Limpiar historial") porque esto es reversible como cualquier
otra decisión de Curaduría. Cada combinación generó su propia entrada de
historial — ningún manejo especial de deshacer en lote hizo falta.

Verificado: 3 tests nuevos en `test_curation_workflow.py` (trío idéntico
resuelto a 2+1, conflicto real de puntaje que no se toca, "gana el dato
cargado" cuando el otro lado está vacío) más 1 test HTTP end-to-end.
Suite completa: **316/316 verde**. Browser real: catálogo sintético con
el mismo trío de "Heat" más un par de "Sicario" con puntajes 9 y 3
(conflicto real) — un click resolvió 2 (los Heat) y dejó 2 pendientes (el
tercer par de Heat que ya no aplicaba, más el conflicto real de Sicario);
Actividad mostró las 2 combinaciones nuevas; deshacer una restauró
exactamente esa fusión (2 Heat de vuelta) sin tocar la otra ni el
conflicto de Sicario, que siguió intacto en la cola con su
desambiguación de la fase 1. Sin errores de consola.

Con esto, **el hallazgo "desambiguar duplicados" queda cerrado por
completo, las 2 fases**. `docs/roadmap.md` actualizado. Quedan 2 de los
4 hallazgos originales del gate de Fase 5: paridad de teclado/búsqueda
en Curaduría, y `aria-live` del comparador — más los 3 puntos pospuestos
de esta fase (empate de fecha, grupos de 3+, visibilidad de archivos
para miembros).

**Desambiguar duplicados — fase 1 (mostrar señales), implementación y
cierre (2026-08-22).** Después de la conversación de diseño (ver la
entrada de abajo), plan mode con un agente Plan cuya síntesis verifiqué a
mano en los 3 puntos más cargados antes de aceptarla — confirmé
directamente que `compare()` en `curation_workflow.py` ya pega
`_availability` sobre la respuesta del comparador (así que ese lado no
necesitaba cambios de backend, menos trabajo del que yo mismo había
supuesto), que `_duplicate_cases()` ordena el par alfabéticamente para
elegir `primary` (por eso 2 de 3 filas de un trío idéntico comparten
literalmente el mismo `primary`), y que `GET /api/curation` no pasa por
`public_payload()` como sí hace `/api/curation/compare` — expone la ruta
absoluta del catálogo en `source_file` hoy, sin relación con este cambio
y solo al propio dueño de esa sesión, nunca a otro usuario. Anotado, no
lo tocué.

Cambio de backend puramente aditivo: `added_at` y `local_files` en
`_item_summary()` de `curation_service.py`; solo `added_at` en la de
`merge_review.py` (el otro lado, disponibilidad, ya llegaba). Frontend:
nuevo `sourceLabel()` en `core/format.js` (los valores reales de
`source` en el dominio — `local_files`, `wikidata`, `manual_merge`,
vacío — no estaban cubiertos por el helper existente, acotado a 3
fuentes externas de búsqueda); `formatHistoryDate` se renombró a
`formatDateTime` y se movió de `inbox-curation.js` a `core/format.js`
porque ya era genérico y ahora lo usan 3 archivos, no 1 (hubo que
actualizar también su uso en `inbox-scanner.js`, que lo importaba
indirectamente desde `inbox-curation.js`). Las 3 superficies: el panel
de detalle (`curationRecord`) y el resumen del comparador
(`mergeEntrySummary`) muestran las señales siempre; la fila de la cola
(`curationQueueItem`) y el título del comparador
(`renderMergeComparator`) solo cuando título y año realmente coinciden,
para no meter ruido en duplicados que no colisionan visualmente (mismo
link externo, título distinto). El título del comparador prioriza año
sobre fuente cuando el año difiere — es el dato más informativo y ya se
calculaba pero no se usaba.

Verificado: 3 tests nuevos/extendidos (`test_curation.py`,
`test_curation_workflow.py`, `test_view_http.py`) más toda la suite
existente — **312/312 verde**. Browser real con 3 copias sintéticas de
"Heat" (mismo título/año, fuentes y fechas distintas, una con
`local_files`): las 3 filas de la cola —antes texto idéntico— ahora
muestran pistas distintas ("IMDb ↔ Wikipedia", "IMDb ↔ Archivo local",
"Archivo local ↔ Wikipedia"); el título del comparador de fusión pasó de
"Heat / Heat" a "Heat (Archivo local) / Heat (Wikipedia)". Sin errores
de consola.

Queda la fase 2 (árbol de auto-resolución) para una sesión futura, con
su propio plan — muta datos del catálogo y merece su propia revisión
ahora que la desambiguación visual está funcionando y probada.

**Scanner: historial y deshacer — paso 1/3, vincular a identidad
existente (2026-08-22).** Precedido por `EnterPlanMode` (dos agentes
Explore en paralelo sobre persistencia real de Scanner y UI de Curaduría/
Scanner, un agente Plan para el diseño, verificación manual de los
hallazgos más importantes antes de aceptarlos) y una `AskUserQuestion`:
Lucas eligió que el alcance incluya deshacer los 3 casos completos
(vincular, crear, omitir) de punta a punta, no dejar "omitir" afuera ni
construir el motor sin exponerlo.

Hallazgo que cambió el diseño respecto a copiar el patrón de Curaduría
literal: confirmar u omitir en Scanner pisa `candidates_json` con `'[]'`
y nunca lo regenera (ni en un rescan) — a diferencia de Curaduría, donde
el "antes" siempre se reconstruye leyendo el ítem actual. Por eso el
"antes" se captura activamente en `resolve_review()` antes de mutar, no
después. También confirmé (leyendo `curation_workflow()` en
`web/catalog_api.py`) que el historial de Curaduría es por-catálogo, no
por-instancia, lo que descartó compartir el mismo `curation-history.json`
con Scanner — quedó una tabla `scanner_history` propia en `instance.db`
(migración v7).

Motor nuevo: `application/scanner_history.py` +
`infrastructure/scanner_history.py` (`SqliteScannerHistoryRepository`,
misma forma que `CurationHistoryRepository`, reusa `normalize_history_mode`
de Curaduría), `ReviewedFileState` + `LibraryConflict` +
`restore_reviewed_files()` en `library_repository.py` (chequeo de "¿cambió
desde la operación?", mismo patrón que `_transition_path` de Curaduría),
`library_service.py` partido en `resolve_review()`/`apply_review()`
(refactor que preserva comportamiento), `application/scanner_workflow.py`
nuevo (`ScannerWorkflowService.review()`/`undo()`/`history()`). Wireado
solo para `link_catalog` en este paso — `create` y el fallback de
`ignore` en `scanner.py` siguen llamando a `library_service.review_file()`
directo, sin pasar por el historial todavía.

Frontend: nuevo módulo compartido `core/operation-feedback.js` (el toast
con "Deshacer" inline que Curaduría ya tenía, extraído para que Scanner
lo use sin crear un import circular — `handleCurationClick` gana una
línea que delega ahí primero). Tab "Actividad" nueva en Scanner
(`data-scanner-filter="history"`, reusa toda la maquinaria de filtros que
ya existía para las otras pestañas), con sus propios controles de modo
persistente/sesión (no el bloque compartido del shell, que ya tenía su
propio botón de refresh y hubiera quedado duplicado). Al pasar,
encontré y corregí un bug que hubiera introducido yo mismo: la navegación
por flechas de Scanner (`moveScannerQueueSelection`) operaba siempre
sobre la cola regular — sin el fix, las flechas se comportaban mal
apenas se entra a la pestaña Actividad.

Verificado: `tests/test_scanner_workflow.py` nuevo (commit dejando fila
restaurable, deshacer restaurando `candidates_json` byte a byte —no
`[]`—, rechazo por `LibraryConflict` si la fila cambió desde la
operación, aislamiento de historial por sesión) más un test HTTP end-to-
end en `test_view_http.py`. Suite completa: **305/305 verde**. Además,
levanté un servidor real con catálogo e instancia sintéticos en el
scratchpad (nunca datos reales) y probé el flujo completo en un browser
real: crear biblioteca, escanear, vincular un archivo con el mismo click
que usaría Lucas, ver la operación en la pestaña Actividad, deshacerla
con el botón real de la interfaz y confirmar que el archivo volvió a la
cola con su candidata original intacta — no una lista vacía. Sin errores
nuevos en consola.

Commiteado (Lucas confirmó, junto con la mudanza de `scripts/` de la
entrada anterior, dos commits separados): `565875b` (scripts →
`codigoLegacy/`) y `860c28a` (este paso).

**Scanner: historial y deshacer — paso 2/3, omitir (2026-08-22).**
Wireo mucho más chico que el paso 1: la rama `else` de
`review_scanner_item()` en `scanner.py` (el fallback que ya cubría tanto
`confirm` vía `candidate_key` como `ignore`) pasa a llamar a
`scanner_workflow.review()` en vez de `library_service.review_file()`
directo — el motor ya estaba armado genérico desde el paso 1, así que
`ignore` lo hereda gratis (misma forma de UPDATE destructivo que
`confirm` a nivel de fila). Confirmé la generalidad releyendo
`review_files()`: el único cambio de código nuevo fue esta rama del
router. El frontend no necesitó ningún cambio de lógica — la pestaña
Actividad y el toast ya son genéricos por acción desde el paso 1.

Como Lucas eligió alcance completo (no dejar "omitir" con el motor listo
pero oculto), actualicé las dos promesas explícitas de que "todavía no
puede restaurarse": el párrafo de `README.md` sobre `Omitir este
archivo` y el texto del diálogo de confirmación en `inbox-scanner.js`.

Verificado: nuevo test HTTP end-to-end (`test_scanner_ignore_can_be_undone_and_restores_the_queue_item`)
más un segundo pase de browser real repitiendo el mismo protocolo del
paso 1 pero con "Omitir" — confirmé el diálogo con el texto nuevo, el
toast con deshacer inline, la fila de Actividad mostrando "Archivo
omitido: ..." y la restauración completa a la cola. Suite completa:
**306/306 verde**, sin errores de consola.

Commiteado sin pausar a confirmar de nuevo — Lucas ya había elegido
explícitamente "seguir con el paso 2 sin parar de nuevo a preguntar" al
aprobar el paso 1.

**Scanner: historial y deshacer — paso 3/3, crear y vincular (cierre del
hallazgo completo) (2026-08-22).** El paso más difícil de los tres, como
anticipaba el plan: la única acción que toca dos sistemas en una sola
decisión (catálogo personal + fila de Scanner) y la única con un ítem
"antes" que puede no existir (si se crea de cero) o ser idéntico al
"después" (si se reusa uno existente).

Extraje `_capture`/`_transition`/`_transition_path` de
`CurationWorkflowService` a funciones de módulo
(`capture_catalog_state`/`transition_catalog_states` en
`curation_workflow.py`) tal como decía el plan — refactor puro, los 6
tests de `test_curation_workflow.py` siguen pasando sin tocarlos.
`ScannerWorkflowService.create_and_link()` las reusa directo para el lado
catálogo: si `created=True` el "antes" es "este id no existía"; si
`created=False` (reuso) el "antes" y el "después" son el mismo estado
capturado. La rama `create` de `scanner.py` pasó de hacer el trabajo
inline a delegar en este método completo.

Dos bugs reales encontrados y corregidos antes de cerrar, ninguno visible
en los tests unitarios hasta que los hice pasar por un browser real:

- **`infrastructure/scanner_history.py` no persistía `catalog_before`,
  `catalog_after` ni `catalog_path`.** El diseño los agregó al diccionario
  de la operación pero la tabla SQLite (`scanner_history`, migración v7)
  nunca ganó esas columnas — se guardaban y se leían como si nada,
  silenciosamente descartados. El deshacer de "crear" completaba sin
  error pero nunca borraba la ficha creada. Como la migración v7 nunca
  llegó a usarse fuera de este mismo trabajo en curso (sin pushear
  todavía), la corregí en el lugar en vez de sumar una v8 solo para
  arreglar una v7 que nunca se publicó.
- **`CurationConflict` no estaba mapeado en las rutas de Scanner.** El
  lado catálogo del deshacer reusa la misma excepción de conflicto que
  Curaduría (`CurationConflict`), distinta de `LibraryConflict` del lado
  Scanner — y me olvidé de agregarla a los `except` de
  `web/routers/scanner.py` y a `scanner_application_error_response`. Se
  manifestó en el browser real, no en los tests unitarios (que llaman al
  workflow directo, sin pasar por las rutas): al deshacer una creación
  cuyo enriquecimiento en background ya había tocado la ficha, el server
  tiraba 500 en vez de 409. Reproducible siempre en este entorno porque
  `ensure_scanner_item` crea fichas sin metadata, así que el
  enriquecimiento en background dispara en cada "crear" real. Agregado
  un test HTTP dedicado para que no vuelva a pasar desapercibido.

Verificado: 2 tests nuevos en `test_scanner_workflow.py` (crear una obra
nueva y deshacer borra la ficha; deshacer rechaza si algo tocó la ficha
después —enriquecimiento simulado—) más 3 en `test_view_http.py` (crear
y deshacer end-to-end, deshacer no toca una ficha reusada, el conflicto
reporta 409 en vez de romper). Suite completa: **311/311 verde**. Browser
real con servidor e instancia sintéticos: creé una obra nueva desde la
interfaz, vi el toast con deshacer inline, deshice y confirmé que la
ficha desapareció del catálogo y el archivo volvió a la cola — ahí
encontré el primer bug (la ficha no desaparecía) y lo arreglé; después
encontré el segundo bug al reintentar deshacer sobre la operación que ya
había quedado en conflicto por el enriquecimiento real.

Con esto, **el hallazgo "historial y deshacer para Scanner" —el más
difícil de los 4 que dejó el gate de Fase 5— queda cerrado por completo**.
`docs/roadmap.md` actualizado para reflejarlo. Quedan los otros 3
(desambiguar duplicados, paridad de teclado/búsqueda en Curaduría,
`aria-live` del comparador), en ese orden de dificultad.

**Diseño: desambiguar casos duplicados con mismo título y año
(2026-08-22).** Conversación larga con Lucas, sin tocar código todavía —
esto es la síntesis para no perder ninguna decisión.

*El problema, tal como lo encontró la crítica de cierre:* con 3 copias
sintéticas de "Heat" en el catálogo, la cola de duplicados, el panel de
detalle y el título del comparador de fusión mostraban las tres filas
como texto idéntico — sin abrir cada una no hay forma de saber cuál es
cuál.

*Señales de desambiguación acordadas, en este orden de utilidad:*
nombre/ruta del archivo local, fuente de origen, fecha de agregado.
Casos borde ya identificados para cuando se implemente la parte visual:
un ítem puede tener varios archivos (multi-parte, mostrar "N archivos" en
vez de un nombre); el mismo nombre puede repetirse en bibliotecas
distintas (no es ambigüedad real — Lucas: eso debería reflejarse como una
sola ficha con múltiples entradas en `local_files`, cada una con su
propio `library_id`); ambas entradas con la misma fuente `local_files`
probablemente sea el mismo archivo visto en dos escaneos, no dos archivos
distintos; la fecha de agregado puede estar vacía (ítems migrados) o
empatada (importación masiva).

*Confirmado leyendo el código real, no supuesto:* ya existe un mecanismo
de identidad de archivo por contenido —`sampled_fingerprint()` en
`infrastructure/library_scanner.py`, un SHA-256 del tamaño más los
primeros y últimos bytes muestreados— que además de detectar archivos
movidos a nivel Scanner (`library_service.py`, busca por fingerprint
entre los archivos "desaparecidos" de la corrida cuando la ruta no
matchea) **ya llega hasta la ficha del catálogo**:
`normalize_local_files()` en `domain/metadata.py` guarda `fingerprint` y
`library_id` en cada entrada de `local_files`. La base de datos para
"misma obra, dos bibliotecas, reflejado en una ficha" ya existe. Lo que
falta confirmar (al implementar, no ahora): si el flujo actual de
"confirmar desde Scanner" ya acumula en esa lista o solo escribe una
entrada.

*Árbol de auto-resolución acordado* para un par de duplicados con mismo
título/año, siempre registrado en el historial existente y deshacible
(nunca una acción silenciosa e irreversible):

- Ninguna tiene archivo y son idénticas en **todo**, incluidos campos
  personales (rating, review, watched_at, tags, notas) — auto-suprimir
  una. "Idénticas" tiene que incluir los campos personales: si difieren
  en uno solo (por ejemplo el rating), no es un caso de auto-supresión.
- Ninguna tiene archivo pero difieren en algún campo personal —
  auto-combinar conservando el valor no vacío de cada campo (mismo
  criterio que ya usa el merge existente con la disponibilidad: un dato
  cargado nunca se pisa con uno vacío).
- Ambas tienen archivo, con fingerprint distinto — caso real de decisión
  humana, pero probablemente no necesita lógica nueva: es exactamente lo
  que ya resuelve el comparador de fusión existente (combina
  `local_files` en vez de descartar uno). El trabajo acá es mostrar bien
  las señales de desambiguación para decidir con confianza, no inventar
  un flujo de resolución nuevo.
- Ambas tienen archivo con el mismo fingerprint (mismo archivo visto dos
  veces, por ejemplo en dos escaneos) — auto-unificar, quedándose con los
  metadatos más enriquecidos mientras se preservan todas las rutas
  (nunca se descarta una ruta por "elegir la más rica").
- Una tiene archivo y la otra no, mismo título/año — "deseo adquirido"
  (la ficha sin archivo era algo que se seguía/quería, la que tiene
  archivo confirma que ya se consiguió): auto-combinar, avisar después
  con el toast normal, deshacible como todo lo demás.
- Ninguna regla aplica con confianza, o el título/año coincide por
  casualidad entre obras distintas — cae al flujo manual existente
  ("No son duplicados" / comparar y fusionar a mano). Este escape hatch
  ya está resuelto por el sistema de historial: nada de esto debe ser
  permanente sin poder deshacerse.

*Tres puntos explícitamente pospuestos por Lucas — anotados para no
perderlos, no para resolver ahora:*

1. Qué hacer cuando la fecha de agregado también empata entre las dos
   entradas — sin regla todavía.
2. Grupos de 3+ duplicados idénticos (no solo pares) — no se confirmó
   todavía si la lógica actual de detección/comparación entiende grupos
   o solo compara de a pares; si es lo segundo, un grupo de 3 podría
   mostrarse como 3 comparaciones de a pares en vez de un solo grupo,
   confundiendo más de lo que aclara.
3. Que los miembros comunes de una instancia puedan ver los archivos
   escaneados si el admin lo habilita (hoy los archivos/rutas locales
   nunca se exponen en vistas compartidas, sin excepción, ni para el
   owner). Esto requeriría relajar una invariante dura documentada en
   `CLAUDE.md`, no es un ajuste chico, y es una feature aparte de
   desambiguar duplicados — queda anotada para su propio hilo de diseño
   futuro, no se decide acá.

Lucas: "comenza en modo automático con lo que puedas de lo que ya
decidimos" — sigue investigación del código real (detección de
duplicados en `domain/`, forma de los 3 sitios de renderizado en
`inbox-curation.js`, si el payload del caso de duplicado ya expone lo
necesario) y plan mode antes de tocar archivos, mismo proceso que
Scanner.

**Cierre de Fase 5: release v0.4.0, README, evaluación de `scripts/` y
ranking del próximo incremento (2026-08-22).** De los 6 hallazgos del gate
final, los 2 arreglos chicos ya estaban cerrados (ver más abajo). Esta
sesión cerró el resto del trámite de fase:

- **Release v0.4.0.** Siguiendo el mismo procedimiento que v0.3.0:
  `pyproject.toml` y `src/movie_inbox/__init__.py` a `0.4.0` (los dos —
  tocar solo `pyproject.toml` rompe
  `test_package_layout.py::test_runtime_version_matches_package_metadata`),
  `CHANGELOG.md` con la sección `[Sin publicar]` movida a `[0.4.0] -
  2026-08-22` y una nueva `[Sin publicar]` vacía arriba, `CLAUDE.md` con la
  línea de versión actualizada, `docs/roadmap.md` con el hito v0.4.0
  cerrado (29/40 contra 22/40, los 4 hallazgos que quedan pendientes
  listados explícitamente). Tag anotado `v0.4.0` creado sobre el commit de
  release (`22a7e26`) — **local, no se pusheó** (no se pidió). Suite
  completa verde antes de taggear.
- **README reescrito.** Lucas: "siento que quedo muy desactualizado" — y
  tenía razón: Scanner/Inventario no estaba documentado en absoluto (todo
  el párrafo de Bandeja hablaba solo de Curaduría), la terminología vieja
  seguía (`Sin link` en vez de `Sin referencia`), y `search-lab compare`
  no estaba. "Estado del proyecto" ahora dice v0.4.0 con resumen de
  v0.3.0/v0.4.0 y puntero a "Estado de compatibilidad". Esa sección de
  compatibilidad quedó más explícita sobre por qué los lanzadores legacy
  de `scripts/` no encajan bien con un deploy Docker (ver el punto
  siguiente).
- **Evaluación de `scripts/*.py` (pedido de Lucas: "¿ya no se usan, no?
  con las rutas de Docker pierde sentido, evalualo").** Confirmado con
  `wc -l` y lectura directa, no supuesto: son wrappers de compatibilidad
  genuinos, no lógica muerta ni duplicada. Dos familias distintas:
  `view_catalog.py`/`txt_to_catalog.py`/`scan_library.py` en la raíz de
  `scripts/` son lanzadores finos (`tests/test_layering.py::test_legacy_entrypoints_are_thin_wrappers`
  exige menos de 25 líneas) que llaman a la implementación real en
  `src/movie_inbox/cli/`; los 13 `scripts/catalog_*.py` son shims de
  compatibilidad de import (`from movie_inbox.domain.X import *`) para
  nombres de módulo planos pre-paquete. La lógica real ya vive toda en
  `src/movie_inbox/cli/`, así que borrar `scripts/` no perdería
  funcionalidad — el argumento de Lucas sobre Docker es válido en el
  sentido de que nadie ejecuta estos wrappers *dentro* del contenedor
  (`movie-inbox <subcomando>` es el único entrypoint documentado ahí), son
  puramente para gente que todavía invoca los scripts v0.1 directo. Las
  dos `AskUserQuestion` sobre esto habían quedado sin responder, pero
  Lucas resolvió el punto directo en el mensaje siguiente: no borrar, pero
  sacarlos de Git.

  **Ejecutado (2026-08-22):** `git mv` de los 22 archivos (los 6
  lanzadores, los 13 shims `catalog_*.py`, `_package_bootstrap.py` y el
  `scripts/README.md` desactualizado) de `scripts/` a una carpeta nueva
  `codigoLegacy/` en la raíz, agregada a `.gitignore`. `build_viewer.py`,
  `scan_video_catalog.sh`, `check.ps1`/`check.sh`, `docker-backup.sh` y
  `cleanup-workspace.ps1` **no se movieron** — siguen siendo herramientas
  activas (CI invoca `wheel_smoke.py` y `docker-backup.sh` directamente).
  Confirmado con un grep de todo el repo (tests, `src/`, docs, CI) que
  nada tracked dependía de los 22 archivos movidos, más allá de menciones
  en prosa. `git mv` preservó el historial como rename, no como
  borrado+creación.

  Como los wrappers y shims ya no viven en una ruta que un clone limpio o
  CI puedan ver, hubo que actualizar todo lo que asumía su presencia, no
  solo moverlos: `tests/test_layering.py` perdió
  `test_legacy_entrypoints_are_thin_wrappers` (el contrato que verificaba
  ya no aplica a nada trackeado — dejarlo apuntando a `codigoLegacy/`
  habría roto CI en cualquier clone fresco); `CLAUDE.md` y la sección
  "Estado de compatibilidad" de `README.md` se reescribieron para explicar
  la mudanza; y **13 ejemplos de comando en `README.md`** que todavía
  usaban `python scripts/txt_to_catalog.py`, `py scripts/scan_library.py`,
  `python scripts/view_catalog.py`, `py scripts/enrich_catalog.py`,
  `py scripts/match_external_links.py` y `py scripts/migrate_catalog.py`
  se pasaron a su equivalente real `movie-inbox <subcomando>` (mismos
  flags, mismo comportamiento — eran wrappers finos del mismo código). El
  docstring de ejemplos de `src/movie_inbox/cli/enrich_catalog.py` tenía
  el mismo problema y se corrigió igual. Suite completa despues del
  cambio: **300/300 verde** (301 menos el test eliminado), `git diff
  --check` limpio.

  Encontrados de paso, marcados pero **no tocados** (fuera del pedido
  puntual de Lucas): `check-output.txt` en la raíz está trackeado en Git y
  parece salida de una corrida vieja de `check.ps1`/`check.sh` olvidada;
  `scripts/LICENSE` es una copia idéntica de la `LICENSE` GPLv3 de la
  raíz, sin motivo aparente para existir duplicada; `scripts/scripts/catalogv4.json`
  sigue trackeado en Git pese a ser un catálogo personal — el patrón
  `/scripts/*.json` de `.gitignore` no alcanza una subcarpeta anidada
  `scripts/scripts/`, así que este archivo entró en algún commit viejo y
  sigue en el historial. Es dato personal (no se leyó ni se tocó por la
  regla de `CLAUDE.md`), pero vale una decisión explícita de Lucas sobre
  si sacarlo de Git (y de la historia, si llegó a pushearse).
- **Ranking del próximo incremento**, a pedido explícito de Lucas
  ("puntua los 4 hallazgos del mas simple al mas dificil, vamos a empezar
  por el mas dificil"), de más simple a más difícil:
  1. `aria-live` en el comparador de fusión — agregar
     `aria-live="polite"` a `#mergeDecisionStatus` y `aria-describedby` en
     el botón de confirmar. Un atributo, un elemento, patrón de anuncio ya
     usado en el resto del código.
  2. Paridad de teclado/búsqueda en Curaduría — Scanner ya tiene
     `moveScannerQueueSelection` (flechas, cableado en
     `bootstrap.js:178`) y `#scannerQueueSearch`; es adaptar ese mismo
     código a la cola de Curaduría, no inventar nada, pero toca
     HTML+CSS+JS y hay que decidir si el handler se generaliza o se
     duplica.
  3. Desambiguar casos duplicados con mismo título y año — antes de tocar
     código hace falta decidir qué mostrar como diferenciador (¿ruta de
     archivo? ¿fecha agregada? ¿fuente?) y qué pasa cuando ni eso alcanza,
     y después aplicarlo consistente en 3 lugares (fila de cola, panel de
     detalle, título del diálogo de fusión). Pide criterio de diseño, no
     solo reusar un patrón existente.
  4. **Historial y deshacer para Scanner — el más difícil.** La
     arquitectura de Curaduría ya existe y es reusable como referencia:
     `infrastructure/curation_history.py`
     (`JsonCurationHistoryRepository.append(operation, namespace="")`,
     sidecar `.{catalog}.curation-history.json` vía
     `curation_history_path()`), listado por
     `GET /api/curation/history` y deshecho por
     `POST /api/curation/undo` (`web/routers/curation.py:41,104`, delega
     en `request_workflow(request).undo(...)` de
     `application/curation_workflow.py`). Confirmado que Scanner
     (`web/routers/scanner.py:273,332`) devuelve códigos de razón
     descriptivos (`scanner_item_linked_to_catalog`,
     `scanner_item_created_and_linked`) en la respuesta JSON pero **no
     llama a ningún repositorio de historial ni tiene ruta de deshacer** —
     el hueco es real, no aparente. Lo que hace esto más difícil que
     copiar el patrón de Curaduría: las 3 acciones de Scanner (vincular a
     identidad existente, crear y vincular, omitir) tocan un inventario
     compartido entre usuarios, no solo el catálogo personal de quien
     actúa, así que deshacer una vinculación después de que otro usuario
     ya la haya referenciado es un caso real a resolver, no un detalle.
     El parámetro `namespace` de `.append()` nunca se vio usado en este
     repaso — puede ser una pista de que el repositorio ya está pensado
     para más de un namespace, o puede ser para otra cosa; confirmarlo es
     el primer paso, no un hecho.

**Fase 5, gate final: 29/40 (2026-08-19/22).** Los 4 P3 (extract/typeset/
adapt/polish) ya estaban cerrados; tocaba correr de nuevo la revisión con
puntaje sobre la misma superficie (Bandeja > Scanner y Curaduría) para
comparar contra el 22/40 del 2026-08-14. Primer paso, otra vez, fue
corregir el nombre del comando: lo que este archivo viene llamando
"`$impeccable audit`" desde 2026-08-14 es en realidad `critique` (`audit`
es a11y/perf/responsive, ya lo había confirmado en la sesión de
`typeset`). Corrí `critique`, que exige un proceso formal — dos
sub-agentes aislados en paralelo (uno de revisión de diseño, otro de
evidencia mecánica + navegador), ninguno viendo el output del otro hasta
que yo los sintetizo — con servidor y catálogo sintético reales para que
ambos pudieran usar la app de verdad, no solo leer código.

Resultado: **29/40** (contra 22/40), 0 P0, con mejoras reales confirmadas
en vivo (los 4 P1 originales siguen resueltos) pero una capa nueva del
mismo problema que esta fase viene persiguiendo: casos duplicados con
mismo título y año son indistinguibles en la cola, el detalle y hasta el
título del diálogo de fusión (con 3 copias de "Heat" en el catálogo
sintético, las tres filas y el diálogo dicen literalmente "Heat / Heat").
También confirmé que el P2 original de la crítica del 14/08 ("Scanner no
deja recibo durable ni reversible") nunca se había cerrado — no era uno
de los 4 P1 con nombre, así que quedó fuera del radar hasta ahora.
Reporte completo con los 6 hallazgos priorizados (3 P1, 2 P2, 1 P3) en el
mensaje de esa sesión y en `.impeccable/critique/2026-08-22T00-04-30Z__...md`
(archivo local, gitignored igual que las 4 corridas anteriores — nunca
estuvieron en git).

De los 6 hallazgos, dos eran arreglos chicos y los cerré ese mismo día:

1. **Cerrado.** El workbench de Curaduría se salía de la pantalla en
   mobile (390px) en vez de pasar a una columna — confirmado en vivo,
   `clientWidth` 390 contra `scrollWidth` 702. Causa real en
   `curation.css:453` y `:433`: un track de grilla `1fr` a secas en vez de
   `minmax(0, 1fr)` — el mínimo implícito de un `1fr` sin `minmax` es el
   tamaño de su contenido, no cero, así que un descendiente ancho fuerza
   el desborde de toda la columna. `scanner.css:547` tenía el mismo
   patrón — corregido preventivamente aunque la cola de Scanner está
   vacía en el catálogo sintético y no se pudo observar el desborde ahí
   directamente. Esto **la propia pasada de `adapt` de esta sesión no lo
   encontró** — me distraje con un artefacto de la herramienta de testing
   (ver la entrada de `adapt` de abajo) y nunca volví a revisar el
   contenido real del workbench con las métricas correctas. Verificado
   antes/después: `clientWidth` 390 / `scrollWidth` 702 (roto) →
   `clientWidth` 390 / `scrollWidth` 390 (arreglado). Commit `ce0c8f2`
   (el título del commit quedó mal por un copy-paste — dice "touch
   target" en vez de describir el fix de grid — Lucas prefirió dejarlo
   así en vez de un amend).

2. **Retirado, no confirmado.** El reporte inicial decía "el diálogo de
   fusión no cierra con Escape" como P1, verificado con una tecla
   simulada real (no un evento de JS). Antes de arreglarlo, probé la
   MISMA tecla contra otro diálogo (`#detailDrawer`) que tiene el patrón
   de cierre idéntico y textualmente correcto (`cancel` + `preventDefault`
   + `close()` propio, igual que todos los demás diálogos de
   `bootstrap.js`) — tampoco cerró. Como el patrón de código es correcto
   en los dos casos y ningún diálogo cierra con Escape en este entorno de
   testing, lo más probable es que sea una limitación de la herramienta
   de automatización del browser (el cierre nativo de `<dialog>` con
   Escape se implementa a nivel de motor del browser, no como algo
   interceptable por JS, y no todas las herramientas de automatización lo
   simulan fielmente) — no un bug real de la app. Le pedí a Lucas que lo
   pruebe él mismo en un browser de verdad antes de tocar nada; sigue
   pendiente su respuesta. **Lección para la próxima vez que un hallazgo
   de teclado/interacción parezca "confirmado": probar el mismo mecanismo
   contra un control hermano que se sabe que funciona, antes de reportarlo
   como bug de un componente específico.**

   **Resuelto (2026-08-22):** Lucas lo probó en un browser real — el
   diálogo cierra con Escape sin problema. Confirma que fue un artefacto
   de la herramienta de automatización, no un bug de la app. Sin acción
   pendiente.

Quedan 4 hallazgos más grandes sin arrancar (los 2 P1 restantes —
desambiguar duplicados idénticos, deshacer para Scanner — más paridad de
teclado/búsqueda Curaduría-Scanner y el `aria-live` del comparador) y la
pregunta de si corresponde correr `critique` una tercera vez después de
esos, o si 29/40 con hallazgos ya priorizados es un cierre aceptable para
Fase 5.

**Fase 5, P3 (`$impeccable polish`) cerrado (2026-08-19), commits
`d4a30d3` (CSS) y `a12eab4` (terminología).** El más grande de los 4 P3.
Investigado con un scan mecánico sin `--scope` (colores) más un Explore
agent en paralelo cubriendo el resto del checklist de `polish.md`
(estados de interacción, código muerto, terminología) — cada afirmación
del agent verificada a mano contra el archivo real antes de actuar, no
solo confiada.

*Colores*: `detect.mjs` sin scope dio 50 hallazgos `design-system-color`.
Agrupé por triplete RGB ignorando el alpha — no por línea — y eso separó
el ruido de lo real: 16 son negro puro (`#000`/`rgba(0,0,0,*)`) en
`box-shadow`/`text-shadow`/`mask-image`, falso positivo confirmado
(`DESIGN.md` ya documenta las sombras como fórmulas `rgba(0,0,0,.XX)`
literales, sin tokenizar, en su propia sección "Shadow Vocabulary`).
3 eran reales: un casi-negro `rgba(3, 4, 14, alpha)` usado como
`::backdrop` en 4 `<dialog>` distintos con 4 alphas distintas y ningún
nombre (`--scrim-rgb` nuevo), `#262b52` reusado igual en dos degradés sin
relación (`--surface-shade` nuevo), y dos `color: #fff` de texto donde el
resto de la app usa `--ink` (4/255 de diferencia por canal, imperceptible,
mismo criterio que los 4 casi-duplicados que `extract` ya había corregido).
El resto (~30) son colores de un solo uso — gradientes de carátula, tonos
puntuales — sin evidencia de duplicado, dejados igual que `extract` dejó
los suyos.

También encontré dos falsos positivos más del mismo estilo que el
`overused-font` de `typeset`: el detector marca `body::before` (la textura
de grilla de 48px que es literalmente la "señal CRT" del brief de diseño)
y el degradado de texto del `<h1>` de marca (usa los 3 colores de señal
documentados, no una paleta genérica) como patrones "de IA genérica" — son
justo lo contrario, coinciden con el brief a propósito. No se tocó
ninguno de los dos.

*Estados de interacción*: la base genérica (`core.css:131-169`) ya cubre
`:focus-visible`/`:hover`/`:active`/`:disabled` en cada botón/input nativo.
El hueco real es específico: `.library-record-identity`, `.scanner-queue-item`
y `.curation-queue-item` tienen un `:hover` a medida sin su
`:focus-visible` correspondiente — quien navega con teclado ve solo el
outline genérico donde el mouse ve además un cambio de color. El caso de
`.scanner-queue-item` importa más que los otros: `inbox-scanner.js` mueve
el foco de teclado ahí mismo después de navegar con flechas. Agregado el
`:focus-visible` que faltaba en los 3. Al revés, `.merge-choice` tenía
`:focus-visible`/`:checked` pero ningún `:hover` — agregado también.

*Código muerto*: JS limpio (sin `console.log`, `debugger`, código
comentado ni TODOs). En CSS, `.library-path-browser-current` en
`scanner.css` no la usa ningún HTML/JS — quedó de un cambio de clase a ID;
la regla siguiente ya cubre el mismo elemento por ID con la misma
propiedad y más. Borrada.

*Terminología*: dos renombres. `Scanner` → `Inventario` en los 5 lugares
donde todavía se colaba (la pestaña principal ya se había renombrado en
P1-a; quedaban el estado vacío de la cola, un aviso de refresco, un label
`sr-only`, un `aria-label` y el aviso de Admin › Bibliotecas). Y `Sin
link`/`Con link` → `Sin referencia`/`Con referencia` en los 10 sitios de
Curaduría, Admin y tarjetas de búsqueda — le pregunté a Lucas primero
porque es vocabulario establecido en 8+ archivos, no un bug obvio; eligió
renombrar. El identificador interno `missing_link` (claves de objeto,
atributos `data-`, comparaciones en JS) no se tocó, solo el texto visible.
De paso encontré un tercero: un checkbox "Review" en Importaciones,
la única palabra en inglés entre hermanos en español → "Reseña".

No tocado a propósito: las clases CTA compartidas (`.action-primary`,
`.quiet-action`, etc.) no tienen hover/active/disabled propios más allá
del genérico — darle a cada una su propio lenguaje de interacción es una
decisión de sistema de componentes completa, no un fix de polish acotado.
Y el badge de Bandeja sigue sin incluir los borradores de Importaciones
(confirmado que sigue siendo cierto, aunque el detalle de "un solo número
sumado" de la crítica original ya no aplica — ahora son 2 badges
separados) — sumar un tercer conteo es una decisión de arquitectura de
información, no algo para decidir en este pase.

Verificado con `scripts\check.ps1` en verde (301 tests), `detect.mjs`
confirmando exactamente los 8 sitios de color arreglados (ni uno de más
ni de menos) y el resto intacto, y `getComputedStyle` contra el catálogo
sintético — el token `--scrim-rgb` resuelve igual que el literal viejo vía
`::backdrop`, el texto del spotlight resuelve a `--ink`, y "Sin
referencia" se ve correctamente en Curaduría.

Los 4 P3 de Fase 5 quedan cerrados. Sigue el gate final: correr
`$impeccable audit` de nuevo sobre la misma superficie y comparar contra
el 16/20 de la corrida anterior.

**Fase 5, P3 (`$impeccable adapt`) cerrado (2026-08-19).** Investigación
grande, resultado chico — y vale documentar por qué, para que una sesión
futura no asuma que "adapt" tiene tanto por corregir como tuvo `typeset`.
Scan mecánico (`detect.mjs --scope layout`) dio 0. Leí — no solo grepeé —
los 34 bloques `@media (max-width: ...)` de los 12 archivos CSS que
tienen alguno. El patrón fue consistente en todos lados salvo uno: los
controles interactivos suben a `min-height: 44px` (o más) dentro de su
breakpoint móvil, coherente con el token `--touch-target: 44px` y con las
inserciones de `env(safe-area-inset-*)` donde hace falta. Confirmé además
dos cosas puntuales que `DESIGN.md` promete explícitamente: la navegación
principal sí se convierte en barra inferior fija en móvil (con safe-area y
objetivos de 52px), y el flip por hover del DVD Case en `core-card.css`
está detrás de `@media (hover: hover) and (pointer: fine)` con el acceso a
la ficha cableado como `data-click` en toda la tarjeta — nunca depende
exclusivamente del hover, tal como pide `DESIGN.md`.

Único hallazgo real: `core-merge.css:322`, dentro del breakpoint de 640px,
`.merge-show-all { min-height: 34px; }` — el toggle "mostrar todos los
campos" del comparador de fusión, que en desktop mide 38px, se achicaba
en móvil a 34px — más chico que su propio default de escritorio y por
debajo del mínimo táctil, exactamente al revés del patrón que aparece
~15 veces en los otros 11 archivos. Corregido a 44px, mismo patrón exacto
que ya usan `curation.css`, `scanner.css` e `imports.css`. Un cambio de
una línea.

Los valores de breakpoint no son uniformes (`scanner.css` usa 1120px/
700px, `imports.css` 980px/700px, `login.css` 760px, contra los 1100/860/
640/440 que documenta `DESIGN.md`) — leí el contenido real detrás de cada
uno antes de asumir que era un bug, y son quiebres genuinos por el ancho
interno de cada grid, no deriva arbitraria; `adapt.md` del propio skill
pide breakpoints por contenido en vez de perseguir tamaños de dispositivo
fijos, así que se dejaron como están.

Nota aparte, no de producto: el testing en vivo con la herramienta de
browser mostró `window.innerWidth` desactualizado después de una
navegación SPA con el viewport ya redimensionado (`visualViewport.width`,
el ancho real de `<html>`/`<body>` y cada medición directa de elemento
seguían mostrando 390px correctamente) — lo rastreé con varias mediciones
independientes antes de concluir que es una rareza de la herramienta de
testing, no un bug de Movie Inbox, y no seguí insistiendo con eso.
Verificado con `scripts\check.ps1` en verde (301 tests). Queda `polish`.

**Fase 5, P3 (`$impeccable typeset`) cerrado (2026-08-19).** Segunda mitad:
los 49 `design-system-font-size` que había quedado sin tocar (ver la entrada
de abajo para la primera mitad, `font-family`). A diferencia de esa primera
mitad, acá cada sitio pedía criterio real, así que se leyeron los 49 en
contexto completo y se agruparon por rol antes de tocar nada — un Plan agent
rehizo la categorización de forma independiente desde los archivos reales
(no desde mi resumen) y encontró 3 sitios que se me habían pasado
(`core-card.css:259`, `curation.css:252` y `:272`); verifiqué esas 3
correcciones a mano contra el archivo antes de confirmarlas. El agent
también confirmó que ningún JS del frontend lee `getComputedStyle`,
`offsetHeight` ni nada equivalente sobre estas clases — la única función
relacionada, `titleSizeClass()` en `core/format.js`, solo mapea longitud de
string a un nombre de clase fijo, nunca lee un tamaño renderizado. Encontré
(y confirmé leyendo el archivo) que `club.css` define
`.dvd-placeholder strong.title-medium` pero nunca `.club-card h4.title-medium`
— un hueco real donde `titleSizeClass()` puede asignar esa clase a un `h4`
que cae silenciosamente al tamaño base; es un bug de una regla faltante, no
de un valor de tamaño, así que quedó anotado sin tocar.

Entré en plan mode (obligatorio en Fase 5) con la categorización completa y
verificada. Dos decisiones necesitaban mi input, no el del agente:
"¿además de unificar, qué otras opciones hay?" para el cluster más grande
(11 encabezados de sección, 18-42px en 8 pantallas) — resueltas por
catalogar cada valor distinto como su propio token con su valor actual
(cero cambio visual), fusionando solo los dos pares que ya eran idénticos
byte a byte (32px/32px, 34px/34px) en vez de inventar escalones nuevos; y
si un cluster de "número de estadística" (22px en 3 archivos, más 25px y
20px en otros dos) se unifica a 22px — confirmé que sí. Esos son los
**únicos 2 cambios de valor real de las 49** (`club.css:334` 25→22px,
`imports.css:215` 20→22px); las otras 47 son cero cambio visual.

36 tokens nuevos en `tokens.css` (agrupados por familia: rampa faltante de
15px reencontrada 5 veces en archivos sin relación → `--text-compact`;
cluster de estadística → `--text-stat`; una marca "↔" de comparador
idéntica en `core-merge.css` y `curation.css` → `--text-comparator-mark`;
dos cascadas de truncado de título por longitud —`core-card.css` y
`club.css`— mantenidas como familias separadas porque los valores son
parecidos pero nunca idénticos, sin evidencia de duplicado real; el resto,
roles de un solo uso con su propio nombre). Reemplazo de los 49 con un
script (no a mano) que verificó la cantidad esperada de ocurrencias antes
de cada reemplazo — falló en seco si algo no cuadraba, no corrigió nada
silenciosamente. `DESIGN.md` suma `compact` (15px) y `stat` (22px) al
frontmatter; el resto queda component-scoped para una futura pasada de
`document`, igual que los tokens de `extract`.

Verificado con `scripts\check.ps1` en verde (301 tests) y `getComputedStyle`
contra el mismo catálogo sintético (Inicio, Colección, Club, Curaduría) —
14 selectores representativos de los 6 grupos, todos resuelven exactamente
al valor esperado, incluida la marca de comparador compartida entre dos
archivos. `detect.mjs --scope type` pasó de 77 hallazgos (al arrancar esta
tarea de `typeset`) a **0** — `font-family` y `font-size` quedan
completamente cerrados. Quedan `adapt` y `polish`.

**Fase 5, P3 (`$impeccable typeset`) parcial (2026-08-19).** Primer error a
corregir: le pedí al skill `audit` en vez de `typeset` — son comandos
distintos (`audit` es a11y/perf/responsive, no el review de heurísticas UX
que veníamos llamando "audit" en este archivo). El comando real que
corresponde a esta entrada de la cola es `typeset`, que hace su propio
análisis en vivo en vez de leer hallazgos guardados — corregido antes de
tocar nada.

El scan mecánico (`detect.mjs --scope type`) sobre `src/movie_inbox/web/static/css/`
completo dio 77 hallazgos: 28 `overused-font` y 49 `design-system-font-size`.
Los 28 eran el mismo patrón que ya resolvió `extract` para colores pero sin
tocar: `"Arial Narrow", "Trebuchet MS", sans-serif` (roles display/feature/title)
y `"Courier New", monospace` (rol label) repetidos como literales — 27 y 65
veces respectivamente, en los mismos 12 archivos — en vez de vivir en
`tokens.css` como el resto de los valores documentados en `DESIGN.md`.
Confirmé que las 27 y las 65 ocurrencias eran texto idéntico byte a byte
antes de tocar nada. Agregué `--font-display`, `--font-body` y `--font-label`
a `tokens.css` (mismo lugar que los tokens de color) y reemplacé las 92
ocurrencias por `var(...)` con un script, no a mano — mecánico y sin
excepciones que revisar. Verificado con `scripts\check.ps1` en verde (301
tests) y con `getComputedStyle` contra un catálogo sintético nuevo (Bandeja,
Colección, Club) confirmando que cada rol resuelve exactamente al mismo
valor que el literal que reemplazó. Efecto de lado: el scan mecánico bajó de
28 a 0 hallazgos de `overused-font` — no fue necesario un `ignore-value`,
porque el valor genérico que el detector reconoce (`"Arial Narrow"`/
`"Space Grotesk"`) ya no aparece como declaración `font-family:` literal en
ningún lado salvo dentro de la definición del token mismo, que el detector
no interpreta como una declaración de fuente.

Los 49 `design-system-font-size` quedan **sin tocar, a propósito**. No es un
hallazgo mecánico resolvible con un script: son valores realmente arbitrarios
(7px, 17px, 18px, 19px, 20px, 21px, 22px, 23px, 25px, 26px, 29px, 32px, 34px,
36px, 38px, 42px, 44px, ninguno de la rampa de `DESIGN.md`), repartidos en 12
archivos, y cada uno pide criterio real, no snapping mecánico. Dos ejemplos
concretos que muestran por qué: `curation.css` tiene dos encabezados con el
mismo rol visual (Arial Narrow, itálica, mayúsculas) en 42px (`.curation-heading h2`)
y 34px (`.curation-case-heading h3`) — dos pasos de jerarquía reales sin
nombre, no un error; y `.curation-thumb` usa `font-size: 7px` para un glifo de
fallback en una caja de 40×56px, que probablemente esté bien así (no es texto
de lectura) pero tampoco tiene un token que documente esa intención. Además
encontré (no vía el detector, que solo mira literales) que `.dvd-case`
`.title-short`/`.title-medium` en `core-card.css` resuelven a `35px` en
runtime — el rol `title` de `DESIGN.md` documenta `24px` fijo, así que hay un
tercer caso de tamaño no documentado, probablemente detrás de un `clamp()` o
cálculo que el scan estático no puede leer.

Pendiente para la próxima sesión de esta misma tarea: decidir, caso por caso
y con capturas o el browser real, cuáles de los 49 (más el de `core-card.css`)
son pasos de rampa nuevos que merecen nombre propio en `DESIGN.md`, cuáles
deberían alinearse a un rol existente, y cuáles son excepciones legítimas
como el glifo de 7px. `adapt` y `polish` siguen sin arrancar.

**Fase 5, P3 (`$impeccable extract`) cerrado (2026-08-18).** Los ~150
colores literales de `core-card.css`, `home.css`, `catalog.css`,
`core-detail.css` y `club.css` que no pasaban por `tokens.css` ni por el
frontmatter de `DESIGN.md` quedaron formalizados como tokens. La mayoría
(~110) eran el mismo patrón: `rgba(R, G, B, alpha)` con el RGB exacto de un
color de señal ya existente, escrito a mano porque CSS no permite
`rgba(var(--hex), alpha)` sin un triplete RGB aparte — se agregaron 11
tokens `--x-rgb` (`--red-rgb`, `--teal-rgb`, `--gold-rgb`, `--violet-rgb`,
`--case-rgb`, `--paper-rgb`, `--cream-rgb`, `--muted-rgb`, `--ink-rgb`,
`--line-rgb`, `--text-pink-rgb`) y se migraron todas las ocurrencias a
`rgba(var(--x-rgb), alpha)`. El resto eran dos familias reales sin nombrar:
la rampa de 3 paradas del fallback de carátula (`.poster-1..4`, un color de
señal cada uno, con tono medio apagado y remate casi negro) y el tinte
pálido de los chips de estado / ícono de placeholder — confirmé con Lucas
que esta segunda familia es intencionalmente distinta de los `--text-*-soft`
que ya existían para kickers y mensajes de feedback (dos roles de contraste
distintos, no un duplicado), así que se sumó como familia nueva
(`--chip-tint-*`) en vez de fusionarla. También apareció una familia
"danger" real (bordes/fondos de zona peligrosa y de botón destructivo) que
no es ninguno de los 4 colores de señal y no estaba documentada; se
formalizó con 3 tokens nuevos (`--danger-rgb`, `--danger-border`,
`--danger-ink`).

Encontrados y corregidos 4 casos concretos de valores casi duplicados dentro
del mismo rol (no drift real de paleta, sino la misma intención escrita a
mano dos veces con un dígito de diferencia): el remate del degradé violeta
de carátula, el ícono "sin portada" de la ficha (distinto del de Colección),
y dos bordes de advertencia dorados en Colección — los cuatro casos quedan
en el CHANGELOG. Se dejaron sin tocar, a propósito, dos hallazgos fuera del
alcance de esta pasada: los stops de degradé únicos del spotlight de Inicio
(un solo uso cada uno, tokenizarlos sería sobre-extracción) y un
`rgba(69, 76, 120, .66)` en `catalog.css` que resultó ser una copia
hardcodeada del valor VIEJO de `--control-border` (antes del fix de
contraste del P1) que el P1 nunca actualizó — sigue mostrando el borde de
bajo contraste original en ese único punto; queda anotado para una sesión
aparte, no se tocó sin confirmación.

`DESIGN.md` se actualizó en el mismo commit: 13 colores nuevos en el
frontmatter, más *backfill* de 4 tokens que ya existían en `tokens.css`
desde antes pero nunca habían llegado al frontmatter (`text-pink`,
`text-cyan-soft`, `text-gold-soft`, `text-danger-soft`) porque hacía falta
nombrarlos para explicar por qué la familia de chip-tint es distinta. Los
otros 7 tokens de `tokens.css` que también faltan en `DESIGN.md`
(`text-soft`, `text-highlight`, `surface-deep`, etc., sin relación con este
hallazgo) quedaron sin tocar a propósito, para una futura pasada de
`$impeccable document`.

Verificado con `scripts\check.ps1` en verde (263 tests + `git diff --check`)
y un script de verificación numérica que resuelve cada `var()` nuevo contra
`tokens.css` y lo compara valor por valor contra el literal que reemplazó en
las ~150 ocurrencias — 100% idéntico salvo los 4 cambios aprobados de
arriba. Recorrido manual en browser real contra un catálogo sintético (4
obras sin portada, una por cada color de señal, para forzar los 4 degradés
de `poster-N`): verificado vía `getComputedStyle` además de inspección
visual, confirmando que `.poster-3` resuelve al degradé dorado exacto y que
`.dvd-front-status.catalogued`/`.danger-zone`/`.action-danger` resuelven a
los tokens nuevos correctos. Cero errores de consola. No se armó una cuenta
de Club para este recorrido — `club.css` se verificó solo por el script
numérico, ya que no introduce ningún token nuevo (reusa exactamente los
mismos `--x-rgb` ya confirmados en las otras cuatro pantallas).

Quedan `typeset`, `adapt` y `polish` — cada uno para una sesión/aprobación
aparte, según lo pedido.

**Fase 5, P1-d cerrado (2026-08-17).** La cola de Scanner se organiza por
causa y confianza en vez de solo `Comparar`/`Sin coincidencia`:
`scannerQueueCauseBucket()` nuevo en `inbox-scanner.js` clasifica cada caso
top-down en `Falta identidad` (`!detected_year`, prioridad — problema de
higiene del archivo, no de matching), `Conflicto de año/tipo` (alguna
candidata con `exact_title_year_mismatch`/`exact_title_kind_mismatch`),
`Probable ficha existente` (`exact_title_missing_year`) o `Sin señales`
(`else` incondicional — catch-all, no un set enumerado). Los 5 chips de
filtro reemplazan a los 2 viejos (no se agregan, la crítica pedía "no solo
por Comparar y Sin coincidencia"), y el header del panel de detalle se
unificó con el mismo vocabulario que la fila de la lista (antes decían cosas
distintas para el mismo caso). Cuando un caso tiene más de 3 candidatas se
muestran las 3 de mayor score (arreglado de paso: el array fusionado de
candidatas de scan-time + create-time-conflict no estaba ordenado por score,
sino por origen) y el resto queda en un `<details>` nativo "Ver N candidatas
más" — mismo patrón ya usado en `admin-libraries.js`.

Mi primer diseño de los 4 buckets tenía dos errores reales que un Plan agent
encontró y yo verifiqué a mano antes de implementar: (1) enumerar los
`reason` de "Sin señales" por lista cerrada tiene un hueco — si dos catalog
items distintos matchean ambos por `exact_title_year` (`len(accepted) > 1`
en `_classification()`), esas candidatas aparecen visibles con un `reason`
"aceptado" que ninguna lista cerrada cubre; el fix es un `else`
incondicional. (2) Clasificar por "la candidata de mayor score" invierte la
señal que la crítica quiere destacar — verifiqué a mano `candidate_score()`:
un año-mismatch con título exacto cae a `0.73` mientras un título apenas
parecido con año casualmente igual puede superar `0.9`; el fix es "¿hay
ALGUNA candidata con este reason?", no "¿cuál es el reason de la candidata
top?". Confirmado 100% Scanner — Curaduría no tiene ningún array de
candidatas con `score`/`reason` que agrupar por causa. También se confirmó
que "mantener merges automáticos solo para IDs externos o título+año
exactos" (la otra mitad del pedido de la crítica) ya estaba cerrado sin
código que tocar, y que no existe ninguna superficie de lote en todo el
proyecto — nada que revisar ahí. Verificado con 262 tests de Python
(`scripts\check.ps1` en verde) + 11 Playwright (2 nuevos, con fixture propio
de 5 candidatas para el tope 3 — score verificado a mano campo por campo) +
recorrido manual en browser real contra un catálogo sintético que ejercita
los 4 buckets (incluido el caso mixto de "Quartz Lantern Meridian", con
razones de dos buckets distintos en el mismo caso, priorizado correctamente).

**Fase 5, P1-b cerrado (2026-08-17).** Scanner deja de presentar "sin
candidata" como ausencia comprobada: la rama sin candidatas cambia de "Obra
ausente del catálogo" a "No encontramos una coincidencia segura", aclara que
la comprobación no es exhaustiva, y ofrece un botón "Buscar en tu catálogo"
(`findLocalMatchForItem()` nuevo en `core/search-bridge.js`, reusa
`runSearch()` de Colección) antes de permitir el alta. Cada candidata de
Scanner muestra además su procedencia — `En tu catálogo` o `Catálogo
compartido` — junto a la razón de confianza que ya existía; el backend la
calcula taggeando transitoriamente `catalog_universe()` (`_scope_owner`,
mismo patrón no persistido que `_availability` de P1-c) y sumando
`catalog_origin` a cada candidata en `_classification()` y en
`ensure_scanner_item()`. La crítica original pedía 3 etiquetas de procedencia
(`En tu catálogo` / `Identidad del inventario` / `Catálogo compartido`); un
Plan agent y yo confirmamos que el código solo sostiene 2 reales — toda
candidata de Scanner está respaldada por un catalog item real de alguna
cuenta, no existe una tercera fuente de "identidad sin ficha" — así que
colapsamos a 2 en vez de inventar una categoría sin dato detrás. De paso se
agregó un tie-break (`_better_candidate()`) para cuando la misma obra vive en
tu catálogo y en uno compartido a la vez: sin él, cuál "gana" en un empate de
score dependía del orden de iteración de las cuentas, no de nada semántico —
verificado con un test que deliberadamente lista la candidata compartida
primero. Verificado con 262 tests de Python (`scripts\check.ps1` en verde) +
9 Playwright + recorrido manual en browser real contra un catálogo sintético
con cuenta compartida (consola sin errores, layout mobile sin overflow).
Queda P1-d — triage de la cola por causa y confianza —, el más grande de los
cuatro, para una sesión aparte.

**Fase 5, P1-c cerrado (2026-08-17, commit `4771c5c`).** Presentador único de
disponibilidad: `core/availability.js` nuevo, adoptado en `card.js`, `merge.js`
e `inbox-curation.js`; backend decora la cola de Curaduría y compare/merge vía
`AvailabilityService` (solo para mostrar, nunca lo que persiste
`apply_reviewed_merge`). De paso se encontró y corrigió que el comparador
(`merge.js`) tenía el mismo bug que Curaduría — la crítica original lo daba
por ya resuelto y no lo estaba. Verificado con tests nuevos (unitario + HTTP +
Playwright) y recorrido manual en browser contra un catálogo sintético.

**Fase 5, P1-a cerrado (2026-08-17).** Franja persistente de 3 estados
(`Archivo físico`/`Identidad compartida`/`Ficha en tu catálogo`, colores
anclados en `DESIGN.md`) en `core/scope-strip.js` nuevo, cableada en
Curaduría y Scanner; modos rotulados por alcance (`Tu catálogo` /
`Inventario de la instancia · Admin`); badge de Bandeja separado en dos
(`#inboxBadge` + `#inboxScannerBadge`) en vez de sumado. Bug real encontrado
y corregido en el camino: el feedback de éxito de Scanner escribía en un
elemento que quedaba `display:none` en modo Scanner — ninguna confirmación
exitosa se veía. Todo frontend, cero cambios de backend. Verificado con
Playwright nuevo (incluida una regresión específica del bug) y recorrido
manual en browser. Quedan P1-b y P1-d — en ese orden, según la Fase 5 de
abajo.

- **Fase 0** — `CLAUDE.md` existe (63 líneas).
- **Fase 1** — ruff/mypy configurados, `lint` job en CI, reformateo aplicado.
  Reporte de limpieza del working tree entregado; `scripts/cleanup-workspace.ps1`
  propuesto y **sin ejecutar** (nada borrado todavía, es tu decisión).
- **Fase 2** — Gate de calidad de búsqueda de v0.3.0 **cerrado**:
  `movie-inbox search-lab run --enforce` pasa (Precision@5 0.91, MRR/Recall@5
  1.0, 0 resultados prohibidos, 0 falsos positivos de auto-match). Job
  `search-lab` agregado a CI como gate real. Quedan 3 ítems del roadmap de
  v0.3.0 sin tocar porque no son de ranking: Curaduría todavía muestra
  `manual: sí/no` crudo (es el P1-c de Fase 5), la cola del Scanner no está
  organizada por causa/confianza (P1-d de Fase 5), y no existe comparación
  baseline-vs-candidato en Search Lab (siguiente incremento, sin fecha).
- **Fase 3** — `tests/test_frontend_quality.py` recortado a
  `tests/test_design_tokens.py` (solo tokens CSS). Garantías reales migradas a
  `tests/browser/test_ui_browser.py`, organizado en 3 clases por superficie.
  `browser-smoke` mide ~13s local, muy por debajo del límite de 8 min.
- **Fase 4** — `app.js`/`style.css`/`index.html`/`web/app.py` partidos, cero
  cambios de comportamiento. `web/app.py` (2153 líneas) → `web/dependencies.py`
  + `web/responses.py` + 8 routers en `web/routers/`, `app.py` bajó a 15.0 KB.
  `index.html` → 11 fragments servidos por `assets.py::render_html()`.
  `style.css` → 14 archivos en `static/css/`. `app.js` → 21 módulos ES nativos
  en `static/js/core/` y `static/js/surfaces/` (sin bundler, `<script
  type="module">`), el más grande `detail.js` a 37.9 KB. 256 tests + 6
  Playwright + ruff + mypy + wheel-smoke + `scripts\check.ps1` en verde;
  `docker-smoke` no se pudo correr local (sin Docker en este entorno) pero usa
  el mismo empaquetado ya verificado por wheel-smoke. Todo commiteado en 8
  commits atómicos sobre `master` (CLAUDE.md; groundwork de assets.py/
  pyproject.toml; CSS; HTML; JS; routers; tests; este archivo +
  `fase-4-tareas.md`), sin pushear.
  Decisiones que se apartaron del plan original (detalladas en el resumen de
  la sesión): `tests/test_package_layout.py` y dos tests de
  `tests/test_view_http.py` perdieron asserts de copy/nombres de función
  contra archivos que ya no existen como blob único; se agregaron 3 hooks de
  test (`window.openDetail/closeDetail/openSearchDescription`) en
  `bootstrap.js` porque Playwright los llama directo y los módulos ES no
  filtran al scope global como el `app.js` viejo.
  Encontrados y corregidos 3 bugs reales introducidos por la extracción
  automática (no preexistentes): una copia duplicada de `apiFetch` en
  `router.js`, y dos imports faltantes (`localFiles`,
  `COLLECTION_MULTI_FILTER_KEYS`, `curationCounts`/`privacyPreferences`) —
  ninguno se hubiera visto sin correr la app en un browser real.

**v0.3.0 publicado (2026-08-17).** El gate de salida ya estaba cerrado desde la
Fase 2; lo que faltaba era el trámite de release. Actualizados: `pyproject.toml`
(→ `0.3.0`), `CHANGELOG.md` (`[Sin publicar]` → `[0.3.0] - 2026-08-17`, con un
`[Sin publicar]` nuevo y vacío arriba), `CLAUDE.md` (línea de versión estable) y
`docs/roadmap.md`. Dos items que no llegaron a tiempo —disponibilidad efectiva
unificada en Curaduría, cola organizada por causa/confianza— se reasignaron
formalmente a v0.4.0; en la práctica ya eran P1-c y P1-d de la Fase 5 de abajo, esto
solo alinea `docs/roadmap.md` con lo que este archivo ya decía. Un tercer item
(comparación baseline-vs-candidato en Search Lab) queda sin versión asignada a
propósito — no encaja en el tema de v0.4.0 ("coherencia de interfaz"), es trabajo de
ranking. Falta commitear estos cambios y taggear `v0.3.0`: no se hizo solo porque no
se commitea sin pedido explícito, y un tag debe apuntar a un commit que ya tenga el
bump — preguntar antes de commitear/taggear.

**Pregunta de mobile vs. Fase 5 — resuelta (2026-08-17).** Mobile no se adelanta a la
Fase 5 dentro de este repo: van a ser proyectos separados. La visión real de Lucas es
más ambiciosa que un cliente delgado online-only — uso sin conexión con sync
oportunista en LAN/VPN cuando el server esté alcanzable, no solo lectura remota
mientras el server esté arriba. Eso justifica un repo aparte (`movie-inbox-android` o
como se termine llamando), con su propio toolchain Kotlin/Gradle, para no mezclarlo
con este repo Python. El plan inicial de esa idea quedó capturado en
`movie-inbox-android-plan.md` (raíz de este repo) para retomar en otra sesión o con
otro agente — es una foto de dónde quedó la conversación, no un plan ejecutable
todavía. Lo que sí sigue siendo trabajo de *este* repo: la Fase 5 (v0.4.0) de abajo, y
eventualmente una capa `/api/v1/` con auth por usuario/dispositivo cuando se retome
mobile. Ninguna de las dos depende técnicamente de la otra (no comparten archivos con
`web/security.py`/`web/dependencies.py` ni entre sí) — es una decisión de dónde poner
la atención primero, no de dependencias de código.

---

# Fase 0 — CLAUDE.md

El repo no tiene `CLAUDE.md` ni `AGENTS.md`. Eso significa que cada sesión de agente
re-descubre las reglas desde cero y algunas se pierden.

Escribí un `CLAUDE.md` en la raíz que contenga, en forma compacta:

- Cómo correr tests, linters y el servidor local (sacalo del README y del workflow, no lo
  inventes).
- Las 6 invariantes de arriba, con puntero al archivo que las define.
- El mapa de capas: qué va en `domain/`, `application/`, `infrastructure/`, `external/`,
  `web/`, `cli/`, y qué NO va en cada una.
- La regla de que `scripts/` son lanzadores finos de compatibilidad (<25 líneas, verificado
  por `test_layering.py`) y que la lógica nueva va al paquete.
- Qué archivos son datos personales y no se tocan.

**Que sea corto.** Apuntá a menos de 100 líneas. Un CLAUDE.md largo se ignora. Todo lo que
ya está bien explicado en PRODUCT.md o DESIGN.md se referencia, no se copia.

**Gate:** existe `CLAUDE.md`, tiene menos de 100 líneas, y todo comando que menciona se puede
ejecutar tal cual.

---

# Fase 1 — Herramientas y limpieza

Esto va temprano a propósito: es barato y protege todo lo que viene después.

## 1a. Linter y type checker

`pyproject.toml` no tiene ruff, black ni mypy. El proyecto tiene ~100 módulos Python, varios
de 40-50 KB.

- Agregá `ruff` (lint + format) y `mypy` como dependencias opcionales `[dev]`.
- Configurá ruff en `pyproject.toml`. Empezá con un ruleset conservador (`E`, `F`, `I`, `UP`,
  `B`) y `line-length` coherente con el código actual — mirá qué ancho usa hoy, no impongas 88
  si el código está escrito a 100.
- Corré `ruff check --fix` y `ruff format`. **En un commit separado del resto**, para que el
  diff de reformato no se mezcle con cambios de lógica.
- Para mypy: arrancá en modo laxo con `--ignore-missing-imports`, y hacelo estricto SOLO en
  `src/movie_inbox/domain/` (que es puro y no tiene dependencias externas). Extenderlo al resto
  es trabajo para después.
- Sumá un job `lint` al workflow `.github/workflows/tests.yml`.

## 1b. Limpieza del working tree

Todo esto está gitignoreado, así que no afecta el repo, pero ensucia la carpeta y hace lento
cualquier listado o búsqueda:

- `scripts/.catalog-cache/images/` — ~536 MB, 843 archivos
- 15 archivos `scripts/catalogv3_links.*.bak.json` de ~1.7 MB cada uno
- `scripts/smoke-catalog.*.bak.json` (hasta 3.8 MB cada uno) + `catalogv2/v3/v4.json`
- `check-output.txt` en la raíz, 771 KB
- `.git.failed-init-backup/`, `scripts/.git.empty-backup/`, `scripts/.git.nested-backup/`
- `movie-inbox-main.bundle`, `movie-inbox-v0.1.0.bundle`

**No borres nada.** Son datos míos y algunos son backups de git. Hacé dos cosas:

1. Un reporte en pantalla: qué es cada grupo, cuánto pesa, y si es reproducible o no.
2. Proponé (sin ejecutar) un `scripts/cleanup-workspace.ps1` que mueva lo descartable a una
   carpeta `_to_delete/` con fecha. Yo decido después qué borrar.

Además, verificá si hay algo que **debería** estar en `.gitignore` y no está — corré
`git status --porcelain` y contame si aparece algún archivo generado o personal.

**Gate:** `ruff check` sale limpio, `mypy src/movie_inbox/domain` sale limpio, el job de lint
está en CI y pasa, la suite de tests sigue verde, y tengo el reporte de limpieza.

---

# Fase 2 — Cerrar v0.3.0

Según `docs/roadmap.md`, v0.3.0 es "confianza en búsqueda, matching e inventario" y el gate de
salida exige cero falsos positivos conocidos en auto-match y merge, más métricas mínimas del
corpus dorado.

`movie-inbox search-lab run` ya existe y mide el ranking productivo, pero hoy una baseline que
no alcanza los umbrales reporta `FAIL (baseline recorded)` y **retorna código 0**. O sea: no es
un gate, es un informe.

1. Corré `movie-inbox search-lab run --json reports/search-baseline.json --html reports/search-baseline.html`
   y mostrame los números actuales: Precision@5, MRR, Recall@5, resultados prohibidos y
   precisión de auto-match, en los cuatro contextos.
2. Decime, con esos números en la mano, **qué falta para poder activar `--enforce` sin que CI
   se ponga rojo**. Si falta trabajo de ranking, listámelo priorizado; no lo hagas todavía.
3. Si los números ya alcanzan: agregá un job `search-lab` al workflow con `--enforce` y
   dejalo como gate real.
4. Repasá `docs/roadmap.md` contra el `CHANGELOG` y decime qué ítems de v0.3.0 están hechos y
   cuáles no. El roadmap dice que Search Lab "todavía mide únicamente el ranking productivo
   actual" y que la comparación baseline vs candidato "comienza en el siguiente incremento" —
   confirmá si eso sigue siendo cierto.

**Gate:** sé exactamente qué falta para cerrar v0.3.0, con números, no con impresiones.

---

# Fase 3 — Destrabar los tests de frontend

`tests/test_frontend_quality.py` afirma que ciertos strings literales existen dentro de
`app.js` y `style.css`. Por ejemplo:

```python
self.assertIn("Conservar ambas y vincular", self.javascript)
self.assertIn("body.distinct_review_token", self.javascript)
self.assertIn("function prepareCatalogViewModel()", self.javascript)
self.assertIn("scanner-create-guard.is-confirming", self.css)
```

Eso no prueba comportamiento: prueba que un texto aparece en un archivo. Cualquier refactor
los rompe sin que nada esté realmente mal. **Hoy son un candado contra el trabajo de la fase 4
y de v0.4.0.**

Objetivo: cada garantía real que hoy protegen esos tests tiene que seguir protegida, pero
desde el lugar correcto.

1. Recorré `test_frontend_quality.py` test por test y clasificá cada assertion:
   - **Garantía real de comportamiento** → migrar a `tests/browser/test_ui_browser.py`
     (Playwright ya está en CI). Ejemplos: gestión de foco del diálogo, que las regiones
     estructurales no sean `aria-live`, que `Al azar` esté fuera del `<nav>`, que la
     disponibilidad efectiva no se presente como el flag manual.
   - **Garantía de diseño verificable estáticamente** → puede quedarse como test de archivo,
     pero sobre *tokens CSS*, no sobre strings de UI. El test de contraste AA y el de
     `--text-label: 10px` son legítimos: leen variables, no copy.
   - **Assertion sobre copy o sobre nombres internos de función** → borrar. `"Conservar ambas
     y vincular"` es copy que va a cambiar en v0.4.0; `"function prepareCatalogViewModel()"`
     es un detalle de implementación.
2. Escribí los tests de Playwright equivalentes ANTES de borrar los viejos. Quiero ver el
   solapamiento en un commit, y el borrado en el siguiente.
3. `tests/browser/test_ui_browser.py` hoy tiene 6 KB. Va a crecer bastante: organizalo por
   superficie (Colección, Bandeja, Ficha) y no en un solo test gigante.
4. Ojo: el job `browser-smoke` de CI tiene `timeout-minutes: 10`. Si la suite crece mucho,
   avisame antes de que se acerque al límite.

**Gate:** `test_frontend_quality.py` ya no contiene assertions sobre copy ni sobre nombres de
función; las garantías equivalentes corren en Playwright; `browser-smoke` pasa en CI y tarda
menos de 8 minutos.

---

# Fase 4 — Partir el frontend y `web/app.py`

Estado actual:

```
src/movie_inbox/web/static/app.js      393 KB   ← un solo archivo
src/movie_inbox/web/static/style.css   205 KB   ← un solo archivo
src/movie_inbox/web/static/index.html   57 KB
src/movie_inbox/web/app.py              87 KB
```

v0.4.0 es un rediseño transversal de interfaz. Hacerlo sobre un `app.js` de 393 KB es caro y
cada iteración mete el archivo entero en contexto.

**Esta fase no cambia comportamiento. Ni uno solo.** Si en el camino encontrás un bug, anotalo
y seguí; no lo arregles acá.

## 4a. Mapa antes de cortar

Primero, sin tocar nada: dame un mapa de `app.js`. Qué bloques hay, cuántas líneas ocupa cada
uno, qué estado global comparten, y dónde están los acoplamientos que van a doler. Mismo
ejercicio, más breve, para `style.css` y `web/app.py`.

Con ese mapa proponeme el corte. Mi hipótesis de partida, pero discutila si el código dice otra
cosa:

- Por superficie: `home`, `collection`, `inbox/scanner`, `inbox/curation`, `inbox/imports`,
  `club`, `admin`.
- Más un núcleo compartido: cliente HTTP + CSRF, presentador único de disponibilidad, estado
  y router, helpers de DOM, formateo.

## 4b. Ejecución

- **ES modules nativos** (`<script type="module">`). Sin bundler, sin build step, sin
  dependencias nuevas. Es una decisión deliberada del proyecto y la quiero mantener.
- Un módulo por vez, con la suite verde entre cada uno. No un big bang.
- CSS: partí en archivos por superficie más un `tokens.css` con las variables. Si `index.html`
  termina con muchos `<link>`, usá `@import` desde un `style.css` raíz y medí si el costo de
  red importa en localhost (probablemente no).

## 4c. Trampas concretas de este repo

Estas te van a morder si no las mirás antes:

1. **`pyproject.toml` empaqueta assets con globs planos:**
   ```toml
   [tool.setuptools.package-data]
   "movie_inbox.web" = ["static/*.html", "static/*.css", "static/*.js"]
   ```
   `static/*.js` **no matchea subdirectorios**. Si movés archivos a `static/js/`, la wheel sale
   sin ellos y el job `wheel-smoke` te lo va a decir tarde. Actualizá los globs.
2. **`scripts/wheel_smoke.py`** verifica assets empaquetados. Actualizalo en el mismo commit
   que cambie la estructura.
3. **`web/assets.py`** y el montaje de estáticos en FastAPI tienen que servir subdirectorios y
   devolver `Content-Type: text/javascript` para los módulos, o el browser los rechaza.
4. **`web/security.py`**: si hay CSP con `script-src`, los ES modules pueden requerir ajuste.
   Verificalo antes de cortar, no después.
5. **`tests/test_package_layout.py`** y **`tests/test_docker_packaging.py`** probablemente
   asumen la estructura actual. Leelos primero.

## 4d. `web/app.py`

87 KB en un módulo. Partilo en routers de FastAPI por superficie, alineados con el corte del
frontend. `app.py` queda solo con la creación de la app, middleware y el registro de routers.
Ojo con los imports circulares y con no violar el layering al hacerlo.

**Gate:** ningún archivo de `web/static/` supera 40 KB; `web/app.py` baja de 15 KB; los cuatro
jobs de CI pasan (tests, wheel-smoke, browser-smoke, docker-smoke); y el comportamiento observable
es idéntico — mismo resultado en la suite de Playwright, sin tests nuevos ni modificados salvo
imports.

---

# Fase 5 — v0.4.0: los 4 P1 de Impeccable

**Recién arrancá esta fase cuando las anteriores estén cerradas.** Sobre el frontend ya partido
esto es viable; sobre el monolito, no.

Leé `.impeccable/critique/2026-08-14T05-13-09Z__src-movie-inbox-web-static-index-html.md`
completo. Marca 4 P1 y un score de 22/40.

**Mi lectura, y quiero que la valides o la refutes antes de proponer nada:** los cuatro P1 son
el mismo problema con cuatro caras. La cadena
`archivo físico → identidad compartida → ficha personal` no es visible en pantalla, y por eso:

- **P1-a** — la Bandeja mezcla alcance compartido (Scanner, inventario de la instancia) y
  personal (Curaduría, tu catálogo) bajo una sola metáfora y un solo badge.
- **P1-b** — "Sin coincidencia" se presenta como ausencia comprobada ("Obra ausente del
  catálogo") cuando solo significa que el algoritmo no encontró candidata. Ese salto epistémico
  es lo que produjo duplicados como `1917`.
- **P1-c** — Curaduría muestra `manual: sí/no` mientras el resto de la app calcula
  disponibilidad efectiva (declaración manual **o** evidencia del servidor). Una misma ficha se
  ve `Disponible` en Colección y `manual: no` en Curaduría.
- **P1-d** — la cola está diseñada para casos, no para 600-700 casos: hasta 8 candidatas por
  caso, todas con el mismo peso visual, sin triage por causa ni confianza.

Si estás de acuerdo, el trabajo se ordena así:

1. **Un presentador único de disponibilidad**, compartido por Colección, ficha, Curaduría y
   comparador: `Disponible` + procedencia (`Inventario verificado`, `Declaración manual`, o
   ambas). Esto solo ya cierra P1-c. Es el cambio más chico y el de mayor retorno: empezá acá.
2. **Una franja de alcance persistente** durante toda la decisión, con los tres estados
   (`Archivo físico`, `Identidad compartida`, `Ficha en tu catálogo`), y cada CTA marcando qué
   filas cambia — antes y después. Separá los contadores del badge por alcance. Cierra P1-a.
3. **Procedencia en cada candidata** (`En tu catálogo`, `Identidad del inventario`, `Catálogo
   compartido`) más la razón de confianza. Y renombrar: `No encontramos una coincidencia segura`
   en vez de `Obra ausente del catálogo`, con búsqueda local prellenada antes de permitir el
   alta. Cierra P1-b.
4. **Triage de la cola por causa y confianza**: `Falta identidad`, `Probable ficha existente`,
   `Conflicto de año/tipo`, `Sin señales`. Top 3 candidatas visibles, el resto a demanda. Cierra
   P1-d. Es el más grande — dejalo último y proponemelo por separado.

También hay un P2 que vale la pena y es barato: **Scanner no deja recibo durable ni reversible**.
Al resolver, el caso desaparece y el feedback va a la franja general. Un recibo junto al detalle
(`Inventario compartido: 1 archivo vinculado a 1917` / `Tu catálogo: sin cambios`) más historial
con Deshacer, como ya tiene Curaduría.

Y las observaciones menores de terminología: `Scanner` → `Escáner` o `Archivos`, `Sin link` →
`Sin referencia`, y sacar `manual: sí/no` que es lenguaje de implementación.

**Restricción de diseño:** `DESIGN.md` es un contrato vigente y la auditoría dice explícitamente
que la estética funciona ("no hace falta rediseñar la estética para resolver este problema").
Esto es arquitectura de información, no un cambio de look. No toques la paleta, la tipografía ni
el vocabulario de sombras.

**Gate:** una nueva corrida de `$impeccable audit` sobre la misma superficie, con score y P1
count comparables contra la corrida del 2026-08-14. Y una prueba concreta: que yo pueda mirar
una sola pantalla y decir sin dudar qué entidad sobrevive después de `Combinar` y dónde quedan
los archivos.

---

## Arrancá

Confirmame que leíste los contratos, decime si algo de este plan te parece mal ordenado o mal
entendido, y empezá por la **Fase 0**.
