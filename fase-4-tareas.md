# Fase 4 — Desglose de tareas para agentes de distinta capacidad

## Fase 4 cerrada (2026-08-16)

Las 20 tareas de A1 a E2 de abajo están completas y verificadas: 256 tests unitarios + 6
Playwright + ruff + mypy + wheel-smoke + `scripts\check.ps1` en verde, `web/app.py` en
15.0 KB, el estático más grande (`detail.js`) en 37.9 KB — ambos bajo gate. El resumen de
cierre autoritativo está en la sección "## Progreso" de `prompt-movie-inbox.md`, no acá.

Durante la revisión de los borradores (A9) y el recorrido manual final (D3) aparecieron 3
bugs reales dejados por el agente que los dejó sin verificar — no estaban listados abajo
porque nadie los había encontrado todavía al escribir este archivo: `router.js` tenía una
copia duplicada de `apiFetch` (`SyntaxError`, tiraba toda la app en blanco) y usaba
`COLLECTION_MULTI_FILTER_KEYS` sin importarlo; `catalog-data.js` usaba
`curationCounts`/`privacyPreferences` sin importarlos. Ninguno se hubiera visto sin correr
la app en un browser real — la suite de Python nunca ejecuta el JS.

Este archivo queda como referencia histórica — el contenido de abajo (tablas de tareas,
reglas R1-R6, apéndices) ya no refleja trabajo pendiente. La "Leyenda de modelos" sigue
siendo útil como plantilla si una fase futura vuelve a delegar tareas chicas a Qwen/Codex.

---

## Plan de ejecución acordado (2026-08-16)

Split decidido: Sonnet 5 (en esta misma sesión, sin más agentes en background) toma
todo lo que requiere cruzar archivos o juicio; Qwen3 4B/8B (por fuera, del lado del
usuario) toma lo puramente mecánico de un solo archivo. Orden de prioridad de Sonnet,
respetando dependencias (A4 primero, A10 último, D/E al final):

1. A4 (state.js, ~15 min) — 2. A9 (~10 min) — 3. A3 (~10 min) — 4. A5 (~10 min) —
5. A8 (~15 min) — 6. B1 (~10 min) — 7. B4 (~12 min) — 8. B5 (~12 min) —
9. B7 (~12 min) — 10. B8 (~12 min) — 11. B2 (~15 min) — 12. B9 (~15 min) —
13. B6 (~15 min) — 14. B3 (~20 min, incluye partir el archivo) — 15. A7 (~20 min) —
16. A10 (~20 min, último) — [Qwen: C1, C2] — 17. D1 (~5 min) — 18. D2 (~10 min) —
19. D3 (~20 min) — 20. E2 (~15 min).

Total estimado Sonnet: ~4.5h de trabajo activo (aproximado, sube si aparecen más bugs
tipo R1). Para Qwen quedan: A1, A2, A6, C1, C2 (bloqueadas hasta que Sonnet termine
A10), D4, E1.


Estado al momento de escribir esto: `web/app.py` → routers, `index.html` → fragments y
`style.css` → `static/css/*.css` están **hechos y verificados** (256 tests, ruff, mypy,
Playwright, wheel-smoke, todo en verde). Lo único que falta es partir
`src/movie_inbox/web/static/app.js` (7800 líneas, 393 KB, sigue intacto en disco) en
módulos ES, más el cierre de la fase.

Un agente ya dejó **20 archivos borrador sin verificar** en `static/js/` (ver "Estado
actual" abajo) antes de que lo cortara. `app.js` original y el `<script>` de
`index.html` **no fueron tocados** — la app sigue funcionando exactamente igual que
antes. Las tareas de abajo son mayormente de **revisión y corrección** de esos
borradores, no de escribirlos de cero — es más barato así.

## Reglas transversales (aplican a varias tareas, leer una vez)

**R1 — Bug conocido, ya confirmado por el agente anterior.** Un módulo ES que hace
`export let x = ...` da a quien lo importa un binding de **solo lectura**
(`import { x } from './state.js'` permite leer `x` y ver cambios futuros, pero
`x = nuevoValor` desde OTRO archivo tira `SyntaxError` o simplemente no compila). Hoy,
en el `app.js` original, cualquier función puede reasignar cualquier variable porque
todo comparte un solo scope. Al partir en módulos, **cada variable compartida en
`core/state.js` necesita un setter exportado** (ej. `export function setCurrentView(v)
{ currentView = v; }`) para que otros archivos puedan escribirla; leerla no necesita
setter. Antes de dar por buena CUALQUIER tarea que toque `core/state.js` o que escriba
una variable compartida desde otro archivo, confirmá que sigue este patrón.

**R2 — No cambia comportamiento, ni uno.** Mové/copiá texto tal cual. No "mejores" el
código, no consolides duplicados, no arregles bugs que encuentres — anotalos aparte.

**R3 — Límite de tamaño.** Ningún archivo nuevo puede superar 40 KB
(`wc -c archivo.js`). Si lo supera, hay que partirlo más (ver tarea B3).

**R4 — Ubicación de archivos.** Todo va directo a `static/js/`, `static/js/core/` o
`static/js/surfaces/`, sin subcarpetas nuevas — `pyproject.toml` ya tiene el glob para
esos tres niveles exactos y no más.

**R5 — Verificación mínima por tarea.** Después de cada tarea: `py -m unittest discover
-s tests -v` no debería agregar fallas nuevas (algunas ya van a fallar hasta que el
cutover — tarea C — esté completo; no es tu culpa, no las persigas antes de tiempo).

**R6 — Diálogo de ficha duplicado, a propósito.** `detailDrawer` (núcleo,
`core/detail.js`) y `sharedDetailDialog` (de Club, `surfaces/club.js`) son dos diálogos
paralelos con HTML parecido. Es intencional, no lo unifiques.

## Leyenda de modelos

| Nivel | Cuándo usarlo | Claude | Codex (OpenAI)¹ | Qwen3 |
|---|---|---|---|---|
| **Mecánica, 1 archivo, sin decisiones** (copiar un rango de líneas, agregar `export`) | Copy-paste guiado por número de línea, cero ambigüedad | Haiku 4.5 | codex-mini / gpt-5.1-codex-mini | 4B viable si el prompt trae los números de línea exactos; 8B con margen |
| **Mecánica con 2-6 imports cruzados** (resolver referencias listadas explícitamente) | Igual que arriba + seguir una lista corta de "importá X de Y" | Sonnet 5 | gpt-5.1-codex | 8B viable con la lista de imports ya resuelta por vos, no que la deduzca; 4B no recomendado |
| **Requiere criterio** (decidir dónde va algo ambiguo, revisar semántica JS, coordinar 3+ archivos a la vez, el arranque/bootstrap) | Bootstrap, el fix de R1 en sí mismo, la verificación final | Opus 5 | gpt-5.1-codex (razonamiento alto / modo "max" si existe) | No recomendado — alto riesgo de romper algo sutil sin darse cuenta |

¹ Nombres de la familia Codex al momento de escribir esto (enero 2026, mi corte de
conocimiento) — verificá el catálogo vigente de OpenAI antes de asignar, puede haber
modelos más nuevos.

## Estado actual — borradores sin verificar (no re-escribir, revisar)

```
static/js/core/http.js            862 B
static/js/core/search-bridge.js  1.6 KB
static/js/core/state.js          1.6 KB
static/js/core/catalog-data.js   4.9 KB
static/js/core/format.js         5.8 KB
static/js/core/card.js           7.8 KB
static/js/core/router.js        11.7 KB
static/js/core/bootstrap.js     19.9 KB
static/js/core/merge.js         21.8 KB
static/js/core/fields.js        22.6 KB
static/js/core/detail.js        38.8 KB   ← cerca del límite de 40 KB
static/js/surfaces/home.js             21.2 KB
static/js/surfaces/admin-members.js    26.7 KB
static/js/surfaces/inbox-curation.js   26.9 KB
static/js/surfaces/inbox-scanner.js    27.6 KB
static/js/surfaces/club.js             27.8 KB
static/js/surfaces/inbox-imports.js    32.8 KB
static/js/surfaces/admin-libraries.js  33.4 KB
static/js/surfaces/catalog-grid.js     36.6 KB
static/js/surfaces/catalog-search.js   42.5 KB  ← SUPERA el límite, ver tarea B3
```

`static/app.js` (el original, 393 KB) y `static/index.shell-close.html` (todavía con
`<script src="/static/app.js" defer>`, sin `type="module"`) **no se tocaron** — la app
sigue andando. `core/catalog-data.js` y `core/search-bridge.js` son nombres que el
agente anterior inventó (no estaban en el plan original) para `findLinkForItem` y
vecinas — la tarea A9 aclara qué revisar ahí.

---

## Grupo A — Núcleo (`static/js/core/`)

| ID | Tarea | Origen en `app.js` (original, intacto) | Verificar | Bloqueada por | Modelo |
|---|---|---|---|---|---|
| A1 | `http.js` | L1 (`API_TOKEN`, sin indentar) + L158-174 (`apiFetch`) | Que estén las 2 cosas, que `apiFetch` tenga el header CSRF y el manejo de 401/403 | — | Haiku 4.5 / codex-mini / Qwen3 4B |
| A2 | `fields.js` | L175-477, un solo `const fields = {...}` de ~300 propiedades | Que sea `export const fields`, que no falte ninguna propiedad (diff línea a línea contra el original) | — | Haiku 4.5 / codex-mini / Qwen3 8B |
| A3 | `format.js` | Funciones de formato/escaping (ver lista abajo) | Que NO estén `linkCounts`, `normalizeKind`, `matchesSearchText`, `localFileCountLabel` (muertas, confirmado por grep, deben borrarse) ni las variables `manualVisibleCount`/`mergeTouchedChoices` (solo-escritura) | — | Sonnet 5 / gpt-5.1-codex / Qwen3 8B |
| A4 | **`state.js` — aplicar R1** | Variables candidatas: `currentIdentity`, `items`, `currentView`, `inboxMode`, `clubMode`, `curatedCollections`, `selectedCollectionId`, `selectedCollection`, `selectedCollectionItems`, `curationCounts`, `selectedExistingIdForSearch`, `catalogMergeResults`, `privacyPreferences`, `routeRestored` | Cada una necesita `export let` PARA LEER + una función `setXxx(valor)` exportada PARA ESCRIBIR desde otro archivo. Confirmá cuáles de esta lista realmente las escribe más de una superficie (si alguna la escribe solo su dueña, no hace falta setter, alcanza con que esa superficie la mantenga local) | — | **Opus 5** / gpt-5.1-codex (razonamiento alto) / no recomendado en Qwen3 |
| A5 | `router.js` | `syncRoute`, `routeValuesForView`, `restoreRoute`, `showView`, `scrollPageTop`, `focusViewHeading`, `setActiveNavigation`, `goHome`, `goToCollection`, `goToCollectionRoot`, `goToInbox`, `goToImports`, `goToClub`, `goToAdmin` | Que importe `collectionRouteValues`/`applyCollectionRoute` de `catalog-grid.js` en vez de asumirlas locales | A4 (usa `currentView`/setters) | Sonnet 5 / gpt-5.1-codex / Qwen3 8B con la lista de imports ya dada |
| A6 | `card.js` | `card`, `openCardButton`, `posterArtwork`, `posterVariant`, `dvdBackSummary`, `handlePosterLoad`, `handlePosterError`, `cachedImageSrc`, `shuffle` | Que `home.js` pueda importar `card` desde acá (lo usa `editorialEntry`) | — | Haiku 4.5 / codex-mini / Qwen3 8B |
| A7 | `detail.js` | Ver lista completa en el Apéndice 1 (~41 funciones) | Aplicá R6. Confirmá que `findLinkForCatalog` importa `findLinkForItem` de donde haya quedado (A9) | A4, A9 | Sonnet 5 / gpt-5.1-codex / no recomendado en Qwen3 (archivo grande + varios imports) |
| A8 | `merge.js` | `openInternalMergeComparator`, `openExternalMergeComparator`, `openMergeComparator`, `requestMergeComparison`, `retryMergeComparison`, `renderMergeComparator`, `mergeEntrySummary`, `mergeFieldRow`, `mergeValue`, `mergeCombinedValue`, `mergeCombineLabel`, `changeMergeChoice`, `changeMergeSurvivor`, `updateMergeDecisionStatus`, `submitReviewedMerge`, `closeMergeComparator`, `mergeComparatorLoading`, `urlHost`, `mergeFieldLabel`, `mergeSearchResult` | `submitReviewedMerge` necesita importar `selectedExistingIdForSearch`+setter (A4), `renderManualResults`/`renderCatalogMergeResults` (`catalog-search.js`) y `setCurationFeedback` (`inbox-curation.js`) | A4, B3, B5 | Sonnet 5 / gpt-5.1-codex / no recomendado en Qwen3 |
| A9 | `catalog-data.js` + `search-bridge.js` — **revisar qué hizo el agente anterior acá** | `findLinkForItem` y `titleSearchValues` (L7584-7603 y L7650-7661 del original) | El agente los partió en 2 archivos sin que se lo pidiéramos así. Decidí si tiene sentido consolidarlos en uno solo (`core/search-bridge.js`, por ejemplo) o dejarlos como están — lo único que importa es que Curaduría (A11/B5) y Detalle (A7) puedan importar `findLinkForItem` de un solo lugar consistente | — | Sonnet 5 / gpt-5.1-codex / no recomendado en Qwen3 (requiere decidir, no solo copiar) |
| A10 | `bootstrap.js` — **última del grupo, depende de TODO** | L479-678 del original (wiring: ~190 `addEventListener`, en orden) + `setInboxMode(...)` + `load()` finales | Que el orden de wiring sea idéntico al original, que importe todo lo que necesita de núcleo y superficies. Es el archivo más sensible — un import mal puesto rompe el arranque completo | A1-A9, todo el Grupo B | **Opus 5** / gpt-5.1-codex (razonamiento alto) / no recomendado en Qwen3 |

---

## Grupo B — Superficies (`static/js/surfaces/`)

| ID | Tarea | Contenido | Verificar | Bloqueada por | Modelo |
|---|---|---|---|---|---|
| B1 | `home.js` | `goToHomeCollection`, `activateHomeSection`, `editorialEntryByKey`, `openHomeCollectionDetail`, `addHomeCollectionItem`, `normalizeEditorialHome`, `renderEditorialHome`, `renderEditorialHero`, `selectSpotlight`, `moveSpotlight`, `renderEditorialSections`, `editorialSection`, `editorialEntry`, `editorialPersonalIds`, `homeDateLabel`, `rememberEditorialFeatured`, `syncHomeDateControl`, `applyEditorialFeaturedDate`, `loadEditorialFeaturedDate`, `refreshEditorialHome` | `goToHomeCollection` escribe `clubMode` → tiene que usar el setter de A4, no asignación directa (R1). `activateHomeSection` importa `resetCollectionFilters`/`applyCollectionFilterDescriptor` de B2 | A4, B2 | Sonnet 5 / gpt-5.1-codex / Qwen3 8B con imports ya resueltos |
| B2 | `catalog-grid.js` | Ver Apéndice 2 (~55 funciones: estado/filtros/render de la grilla) | Que `randomCandidates` importe `currentView` de A4 | A4 | Sonnet 5 / gpt-5.1-codex / no recomendado en Qwen3 (archivo grande) |
| B3 | `catalog-search.js` — **primero medir, después decidir si partir** | Resto de funciones de Colección (búsqueda externa, resultados manuales, wiki-review — aprox. L6614-L7371 del original, salvo `findLinkForItem` que va en A9) | **Ya mide 42.5 KB, supera el límite de 40 KB (R3).** Primer paso: `wc -c` para confirmar. Si sigue arriba de 40 KB, partirlo en dos (ej. `catalog-search.js` + `catalog-search-external.js`) por función, sin cambiar nada de contenido | — | Sonnet 5 / gpt-5.1-codex / no recomendado en Qwen3 |
| B4 | `club.js` | `loadClub`, `changeClubMode`, `renderClubMode`, `selectClubCatalog`, `loadSharedCatalog`, `renderClubTabs`, `renderSharedCatalog`, `sharedCard`, `showMoreClubItems`, `setClubFeedback`, `renderCollectionDirectory`, `collectionDirectoryCard`, `collectionMosaic`, `openCollection`, `loadCollectionDetail`, `closeCollectionDetail`, `renderCollectionDetail`, `collectionItemCard`, `toggleCollectionFollow`, `changeCollectionSelection`, `toggleMissingCollectionSelection`, `syncCollectionSelection`, `addSelectedCollectionItems`, `addMissingCollectionItems`, `addCollectionItems`, `openSharedDetail`, `closeSharedDetail`, `storedClubMode` | Aplicá R6 (no toques `openSharedDetail`, es el diálogo paralelo a propósito) | — | Sonnet 5 / gpt-5.1-codex / Qwen3 8B |
| B5 | `inbox-curation.js` | `loadCurationQueue`, `loadCurationHistory`, `storedHistoryMode`, `changeCurationHistoryMode`, `clearCurationHistory`, `syncCurationCounts`, `handleCurationClick`, `visibleCurationCases`, `renderCuration`, `renderCurationHistory`, `curationHistoryItem`, `curationHistoryDetail`, `curationActionLabel`, `formatHistoryDate`, `curationQueueItem`, `curationCaseDetail`, `duplicateCurationDetail`, `missingLinkCurationDetail`, `curationRecord`, `curationThumb`, `curationEvidence`, `curationEmptyState`, `openCurationItem`, `findLinkFromCuration`, `updateLinkCuration`, `updateDuplicateCuration`, `postCurationDecision`, `undoCurationOperation`, `setCurationFeedback` | `findLinkFromCuration` importa `findLinkForItem` de A9. `syncCurationCounts` lee `curationCounts` de A4 (escrito por B9/admin-libraries) | A4, A9 | Sonnet 5 / gpt-5.1-codex / Qwen3 8B con imports resueltos |
| B6 | `inbox-imports.js` | `loadImportDrafts`, `renderImportDraftList`, `showImportSourcePanel`, `resetImportSourceForm`, `selectImportDraft`, `renderImportReview`, `renderImportDestination`, `renderImportPreviewRows`, `filteredImportItems`, `visibleImportItems`, `canSelectImportItem`, `changeImportSelection`, `toggleVisibleImportItems`, `syncImportSelection`, `handleImportClick`, `setImportInputMode`, `changeImportFile`, `refreshImportMapping`, `renderImportCsvFields`, `analyzeImportSource`, `readImportFile`, `importColumnMap`, `applySelectedImport`, `deleteSelectedImportDraft`, `renderImportResult`, `setImportResultFeedback`, `openImportedCollection`, `setImportFeedback`, `importErrorMessage`, `resolvedImportFormat`, `inferImportFormat`, `parseCsvHeader`, `importCollectionTitle`, `formatImportExpiry`, `formatImportBytes`, `importStateLabel`, `importReasonLabel`, `importKindLabel`, `importUrlLabel` | `openImportedCollection` escribe `clubMode`/`selectedCollectionId` (setters de A4) y llama `goToClub`(A5)/`openCollection`(B4) | A4, A5, B4 | Sonnet 5 / gpt-5.1-codex / no recomendado en Qwen3 (varios imports cruzados) |
| B7 | `inbox-scanner.js` | `loadScannerQueue`, `renderScannerQueue`, `visibleScannerQueue`, `changeScannerQueueFilter`, `searchScannerQueue`, `selectScannerQueueItem`, `moveScannerQueueSelection`, `focusSelectedScannerItem`, `renderScannerQueueDetail`, `scannerCandidatesForItem`, `scannerCandidateEquivalenceKeys`, `actionObjectLabel`, `scannerCandidate`, `scannerComparisonRow`, `scannerCandidateAliases`, `scannerCandidateLinks`, `formatScannerScore`, `scannerCandidateReason`, `handleScannerReviewAction` | `handleScannerReviewAction` llama `setCurationFeedback` (B5) y `loadLibraries` (B9) — **import circular con B9, es intencional (R2), no lo "arregles"** | B5 | Sonnet 5 / gpt-5.1-codex / no recomendado en Qwen3 |
| B8 | `admin-members.js` | `loadMembers`, `renderMembers`, `renderArchivedMembers`, `openMemberDialog`, `closeMemberDialog`, `createMember`, `handleMemberAction`, `openEditMemberDialog`, `closeEditMemberDialog`, `saveMemberProfile`, `openArchiveMemberDialog`, `closeArchiveMemberDialog`, `archiveMemberAccount`, `handleArchivedMemberAction`, `showTemporaryPassword`, `closeTemporaryPasswordDialog`, `copyTemporaryPassword`, `setMemberFeedback`, `setMemberDialogFeedback`, `memberErrorMessage`, `openPrivacyDialog`, `closePrivacyDialog`, `applyPrivacyForm`, `syncPrivacyControls`, `savePrivacyPreferences`, `privacyErrorMessage`, `syncPrivacySummary`, `refreshAdminData`, `loadImageCacheStatus`, `renderImageCacheStatus`, `syncImageCacheStatusPolling` | Si usa `formatImportBytes`/`importKindLabel`, importarlas de B6 en vez de duplicarlas (confirmar con grep) | B6 | Sonnet 5 / gpt-5.1-codex / Qwen3 8B |
| B9 | `admin-libraries.js` | `loadLibraries`, `loadLibraryDetail`, `renderLibraryConfiguration`, `renderLibraries`, `libraryWorkflow`, `libraryWorkflowClass`, `libraryPrimaryAction`, `libraryAutomationControl`, `libraryRunPanel`, `libraryNextRunLabel`, `libraryRunResult`, `libraryPreviewStateLabel`, `handleLibraryAction`, `queueLibraryRun`, `scheduleLibraryRunPoll`, `pollLibraryRun`, `openLibraryDialog`, `closeLibraryDialog`, `browseManagedLibraryPath`, `handleLibraryPathDirectory`, `useBrowsedLibraryPath`, `checkManagedLibraryPath`, `setLibraryPathFeedback`, `saveManagedLibrary`, `deleteManagedLibrary`, `setLibraryFeedback`, `libraryErrorMessage`, `libraryStatusLabel`, `scheduleLabel`, `runStatusLabel`, `runModeLabel`, `formatLibraryTime` | `handleLibraryAction`/`pollLibraryRun` importan de B7 (`goToInbox`+`setInboxMode` de A5/B7, `loadScannerQueue` de B7) — **import circular con B7, intencional (R2)** | A5, B7 | Sonnet 5 / gpt-5.1-codex / no recomendado en Qwen3 |

---

## Grupo C — Cutover (hacer al final, en orden, con TODO el resto ya verificado)

| ID | Tarea | Detalle | Bloqueada por | Modelo |
|---|---|---|---|---|
| C1 | `static/app.js` delgado | Reemplazar el contenido completo por una sola línea: `import "/static/js/core/bootstrap.js";` | A10, todo Grupo B | Haiku 4.5 / codex-mini / Qwen3 4B |
| C2 | Cutover de `index.shell-close.html` | Cambiar `<script src="/static/app.js" defer></script>` por `<script type="module" src="/static/app.js"></script>` | C1 | Haiku 4.5 / codex-mini / Qwen3 4B |

---

## Grupo D — Verificación final (después de C2)

| ID | Tarea | Detalle | Modelo |
|---|---|---|---|
| D1 | Suite completa | `py -m unittest discover -s tests -v` — tiene que quedar verde salvo `test_package_layout.py` (ver Grupo E) | Sonnet 5 / gpt-5.1-codex / Qwen3 8B (ejecutar e interpretar el resultado, no arreglar bugs de fondo) |
| D2 | Playwright | `py -m unittest discover -s tests/browser -p "test_*.py" -v` — única red de seguridad automatizada real para JS, tiene que quedar 100% verde | Sonnet 5 / gpt-5.1-codex / Qwen3 8B |
| D3 | Recorrido manual en browser | Levantar el server y probar a mano: Inicio, Colección (buscar/filtrar/abrir ficha), Bandeja en sus 3 modos, Club, Admin, comparador de fusión desde Curaduría. Mirar la consola por errores de import/JS | **Opus 5** (o una persona) / gpt-5.1-codex con herramientas de browser / no aplica en Qwen3 (no tiene herramientas de browser) |
| D4 | Tamaños | `wc -c` sobre cada archivo nuevo de `static/js/`, confirmar que ninguno supera 40 KB después de B3 | Haiku 4.5 / codex-mini / Qwen3 4B |

---

## Grupo E — Cierre de la fase

| ID | Tarea | Detalle | Modelo |
|---|---|---|---|
| E1 | `test_package_layout.py`, último ajuste | Ya está reescrito (ver `git diff`), solo falta confirmar que `static_asset("js/core/http.js")` (línea ~82) resuelve `True` una vez que A1/C1 estén hechos — hoy es el único test rojo de toda la suite | Haiku 4.5 / codex-mini / Qwen3 4B |
| E2 | Gate final completo | Tamaños (`web/app.py` < 15 KB ya OK, ningún `web/static/*` > 40 KB), `ruff check`, `ruff format --check`, `mypy src/movie_inbox/domain`, `scripts\check.ps1`, y si hay Docker disponible el equivalente local de `docker-smoke` | **Opus 5** / gpt-5.1-codex (razonamiento alto) / no recomendado en Qwen3 |

---

## Apéndice 1 — `core/detail.js` (tarea A7), lista completa

`detailContextForTrigger`, `openDetailFromTrigger`, `openRandomDetail`,
`personalRecordPanel`, `personalRecordEditor`, `personalPrivacyOptions`,
`personalVisibilityBadge`, `availabilityPanel`, `openDetail`, `closeDetail`,
`setDetailContext`, `uniqueExistingIds`, `renderDetailNavigation`, `navigateDetail`,
`showDetailFromQueue`, `openAnotherRandomDetail`, `renderDetail`, `drawerPoster`,
`editPersonalRecord`, `cancelPersonalEdit`, `metadataEditor`, `metadataEditorRow`,
`primeDetailForms`, `serializeDetailForm`, `handleDetailFormMutation`,
`hasUnsavedDetailChanges`, `handleBeforeUnload`, `setDetailFeedback`,
`clearDetailFeedback`, `syncDetailFeedback`, `requestDetailTransition`,
`keepEditingDetail`, `discardDetailChanges`, `saveDetailChanges`,
`saveDirtyDetailForms`, `deleteCatalogItem`, `savePersonal`, `persistPersonalForm`,
`saveMetadata`, `persistMetadataForm`, `findLinkForCatalog`.

## Apéndice 2 — `catalog-grid.js` (tarea B2), lista completa

`randomCandidates`, `syncRandomControl`, `changeRandomScope`, `catalogDetailItems`,
`collectionRouteValues`, `syncCollectionRoute`, `applyCollectionRoute`,
`setupCollectionFilterOptions`, `uniqueFilterValues`, `setupFilterAddSelect`,
`renderQuickFilterGroup`, `filterValueLabel`, `renderDatabaseMenu`,
`downloadCatalogExport`, `externalDatabaseItem`, `externalCacheItem`,
`setCollectionSearchMode`, `collectionSearchMessage`, `comparisonSearchMessage`,
`emptyCollectionFilters`, `validCollectionYear`, `matchingFilterValue`,
`setCollectionFilterValue`, `toggleCollectionFilter`, `collectionFiltersChanged`,
`applyCollectionFilterDescriptor`, `applyCollectionYearRange`,
`syncCollectionFilterControls`, `filterSetMatchesValue`, `filterSetMatchesList`,
`matchesYearFilters`, `matchesReleaseDay`, `matchesPersonalRecord`,
`emptyCatalogMetrics`, `catalogSearchDocument`, `prepareCatalogViewModel`,
`filteredItems`, `sortItems`, `numericYear`, `resetCollectionFilters`, `clearFilters`,
`clearFilter`, `renderActiveFilters`, `releaseDayFilterLabel`,
`hasActiveCollectionFilters`, `applyRandomOrder`, `render`, `renderHeaderStats`,
`catalogSummaryText`, `showMoreCatalogItems`, `randomizeView`, `resetViewOrder`,
`toggleDuplicatesOnly`, `toggleWatched`, `toggleCatalog`.

## Orden sugerido si un solo agente/persona va a ir tarea por tarea

A1, A2, A3, A4 (crítica, R1) → A5, A6, A9 (en paralelo) → A7, A8, B1-B9 (en paralelo,
cada una ya sabe qué importar) → B3 primero que las demás si hay que partirla → A10
(bootstrap, al final del núcleo) → C1 → C2 → D1-D4 → E1 → E2.

Si son **varios agentes en paralelo**: todo lo que no tiene "Bloqueada por" en su fila
puede arrancar ya mismo. Lo único que de verdad tiene que ir al final es A10 (bootstrap)
y el Grupo C/D/E completo.
