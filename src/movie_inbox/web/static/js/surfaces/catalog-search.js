import { load } from "../core/catalog-data.js";
import { fields } from "../core/fields.js";
import { displayTitle, escapeHtml, hasExternalLink, hasHost } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { mergeSearchResult } from "../core/merge.js";
import { showView } from "../core/router.js";
import { findLinkForItem } from "../core/search-bridge.js";
import { CATALOG_PAGE_SIZE, SEARCH_PAGE_SIZE, items, selectedExistingIdForSearch, setSelectedExistingIdForSearch } from "../core/state.js";
import { collectionModeCopy, collectionSearchMessage, collectionSearchMode, comparisonSearchMessage, filteredItems, hasActiveCollectionFilters, render, renderDatabaseMenu, setCatalogVisibleCount, setCollectionSearchMode, setRandomOrder, syncCollectionRoute } from "./catalog-grid.js";
import { duplicateHint, mergeSelectionBar } from "./merge-selection.js";
import { catalogMergeResult, externalSourceFeedback, externalSourceStateLabel, localSearchResult, oneEditApart, searchResult, showDuplicateChoice } from "./catalog-search-cards.js";

      export let manualResults = [];
      export const completedExternalResults = new Map();

      export function externalResultKey(result) {
        return `${resultShelfSource(result)}|${candidateReference(result)}`;
      }

      export let selectedManualIndex = null;

      export let selectedManualCandidateSource = "";

      export let selectedManualCandidateRef = "";

      export let manualSearchSource = "all";

      export let catalogMergeResults = [];

      export let wikiReviewQueue = [];

      export let wikiReviewIndex = 0;

      export let descriptionReturnFocus = null;

      export let activeQuery = "";

      export let manualSourceVisibleCounts = {};

      export let catalogMergeVisibleCount = 6;
      let unifiedVisibleCount = 6;
      let localSearchState = "idle";

      export function usesUnifiedSearch() {
        return Boolean(activeQuery) && ["search", "add"].includes(collectionSearchMode);
      }

      export let externalSourcesLastUsed = [];

      export let externalSourcesAttempted = [];

      export let externalSearchController = null;

      export let externalSourceSearchStates = {};

      export let externalHealth = { sources: {}, cache: {} };

      export const SEARCH_TIMEOUT_MS = 10000;

      export const EXTERNAL_SEARCH_SOURCES = ["wikipedia", "imdb", "filmaffinity", "jikan", "tmdb"];

      export const EXTERNAL_SOURCE_LABELS = {
        wikipedia: ["Wikipedia", "Artículos y datos enciclopédicos"],
        imdb: ["IMDb", "Títulos internacionales y reparto"],
        filmaffinity: ["FilmAffinity", "Referencias en español"],
        jikan: ["Jikan", "Anime y títulos de MyAnimeList"],
        tmdb: ["TMDb", "Traducciones, reparto e imágenes"]
      };

      // TMDb es opt-in por instancia: sin token configurado en el servidor,
      // no hay entrada de health para "tmdb" y la fuente queda invisible por
      // completo (sin estanteria fantasma, sin consultas, sin degradacion).
      export function isExternalSourceConfigured(source) {
        if (source !== "tmdb") return true;
        return Boolean(externalHealth?.sources?.tmdb);
      }

      export function configuredExternalSources() {
        return EXTERNAL_SEARCH_SOURCES.filter(isExternalSourceConfigured);
      }
      externalSourceSearchStates = emptyExternalSourceSearchStates();

      export function setManualResults(value) {
        manualResults = value;
      }

      export function setSelectedManualIndex(value) {
        selectedManualIndex = value;
      }

      export function setSelectedManualCandidate(source = "", reference = "") {
        selectedManualCandidateSource = String(source || "");
        selectedManualCandidateRef = String(reference || "");
      }

      export function setCatalogMergeResults(value) {
        catalogMergeResults = value;
      }

      export function setActiveQuery(value) {
        activeQuery = value;
      }

      export function setCatalogMergeVisibleCount(value) {
        catalogMergeVisibleCount = value;
      }

      export function setExternalHealth(value) {
        externalHealth = value;
      }

      export function setDescriptionReturnFocus(value) {
        descriptionReturnFocus = value;
      }

      // [Q4] tareas.md: "director:X" is the backend contract, but nobody
      // needs to know that syntax to use it -- the discoverable toggle
      // builds it from whatever the user already typed. Typing the prefix
      // directly still works too (checked case-insensitively, never doubled).
      export function effectiveSearchQuery(rawQuery) {
        if (!fields.searchByDirector.checked || /^director:/i.test(rawQuery)) return rawQuery;
        return `director:${rawQuery}`;
      }

      export async function runSearch({ updateHistory = true } = {}) {
        resetDuplicateReview();
        const requestedQuery = fields.query.value.trim();
        fields.collectionUtilityMenu.open = false;
        if (!requestedQuery) {
          clearManualSearch({ focus: false, updateHistory });
          return;
        }
        activeQuery = requestedQuery.length >= 2 ? requestedQuery : "";
        if (["compare", "link"].includes(collectionSearchMode)) {
          await refineComparisonSearch(requestedQuery, { updateHistory });
          return;
        }
        const requestedMode = collectionSearchMode === "add" ? "add" : "search";
        selectedManualIndex = null;
        setSelectedExistingIdForSearch(null);
        manualResults = [];
        catalogMergeResults = [];
        manualSourceVisibleCounts = {};
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        setRandomOrder([]);
        setCatalogVisibleCount(CATALOG_PAGE_SIZE);
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        fields.reviewPrevious.hidden = true;
        fields.reviewNext.hidden = true;
        setCollectionSearchMode(requestedMode);
        if (requestedMode === "add") fields.externalSource.checked = true;
        render();
        renderDatabaseMenu();
        if (requestedQuery.length < 2) {
          setSearchState("error", "La búsqueda necesita al menos 2 caracteres.");
          if (updateHistory) syncCollectionRoute("push");
          return;
        }
        if (updateHistory) syncCollectionRoute("push");
        showView("catalog", { updateHistory: false, scroll: false });
        await searchManual("all");
      }

      // Refina la busqueda sin abandonar "compare"/"link": conserva el lado ya
      // fijado (resultado externo elegido, o ficha local elegida) y vuelve a
      // consultar solamente el lado opuesto. Salir del modo sigue siendo
      // responsabilidad exclusiva de clearManualSearch()/goToCollectionRoot().
      export async function refineComparisonSearch(requestedQuery, { updateHistory = true } = {}) {
        if (requestedQuery.length < 2) {
          setSearchState("error", "La búsqueda necesita al menos 2 caracteres.");
          if (updateHistory) syncCollectionRoute("push");
          return;
        }
        if (updateHistory) syncCollectionRoute("push");
        if (collectionSearchMode === "compare") {
          await searchCatalogForMerge(requestedQuery);
          return;
        }
        manualResults = [];
        manualSourceVisibleCounts = {};
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        await searchManual("all");
      }

      export function setSearchState(state, message = "") {
        fields.externalResultsJump.hidden = true;
        const comparisonMode = ["compare", "link"].includes(collectionSearchMode);
        fields.collectionView.classList.toggle("has-search-results", Boolean(activeQuery) && state !== "idle");
        fields.searchContext.hidden = state !== "searching" && state !== "error" && !comparisonMode;
        fields.searchContext.dataset.state = state;
        fields.searchContextText.textContent = message;
        fields.cancelSearch.hidden = state !== "searching";
        fields.clearManualSearch.hidden = state === "idle" && !comparisonMode;
        fields.backToCollection.hidden = !comparisonMode;
      }

      export function emptyExternalSourceSearchStates() {
        return Object.fromEntries(configuredExternalSources().map((source) => [source, {
          status: "idle",
          count: 0,
          error: "",
          retryAfterSeconds: 0,
          fallbackReason: ""
        }]));
      }

      export function resultShelfSource(result) {
        if (result?._search_shelf) return result._search_shelf;
        return result?.source === "anime_offline_database" ? "jikan" : result?.source || "";
      }

      export function candidateReference(result = {}) {
        const reference = result.tmdb_id
          || result.imdb_id
          || result.mal_id
          || result.wikidata_id
          || result.url;
        return String(reference || [result.title, result.year].filter(Boolean).join("|") || "unknown");
      }

      export function showCollectionAnchor(kind, item = {}, unavailable = false) {
        fields.collectionAnchor.hidden = false;
        fields.collectionAnchorLabel.textContent = kind === "link"
          ? "Obra local fija"
          : "Referencia externa fija";
        fields.collectionAnchorTitle.textContent = unavailable
          ? "La referencia elegida ya no está disponible"
          : displayTitle(item) || "Obra sin título";
        const source = resultShelfSource(item) || item.source || "catálogo local";
        const details = [item.year, source].filter(Boolean).join(" · ");
        fields.collectionAnchorMeta.textContent = unavailable
          ? "Podés volver al paso anterior sin perder la consulta."
          : details;
      }

      export function requestedExternalSources(source, includeExternal) {
        if (!includeExternal) return [];
        if (source === "all" || !EXTERNAL_SEARCH_SOURCES.includes(source)) return configuredExternalSources();
        return isExternalSourceConfigured(source) ? [source] : [];
      }

      export function setSearchBusy(busy) {
        fields.searchButton.disabled = busy;
        fields.searchButton.textContent = busy ? "Buscando..." : collectionModeCopy().action;
        fields.searchConsole.setAttribute("aria-busy", String(busy));
        if (busy) fields.searchButton.setAttribute("aria-busy", "true");
        else fields.searchButton.removeAttribute("aria-busy");
      }

      export function isCurrentSearch(controller) {
        return externalSearchController === controller && !controller.signal.aborted;
      }

      export function mergeExternalHealth(payload, source) {
        const incoming = payload?.external || {};
        const sourceHealth = incoming.sources?.[source] ? { [source]: incoming.sources[source] } : {};
        const offlineHealth = source === "jikan" && incoming.sources?.anime_offline_database
          ? { anime_offline_database: incoming.sources.anime_offline_database }
          : {};
        externalHealth = {
          ...externalHealth,
          sources: {
            ...(externalHealth?.sources || {}),
            ...sourceHealth,
            ...offlineHealth
          },
          cache: incoming.cache || externalHealth?.cache || {}
        };
      }

      export function replaceExternalSourceResults(source, results) {
        const selectedKey = selectedManualIndex === null ? "" : externalResultKey(manualResults[selectedManualIndex] || {});
        const duplicateIndex = fields.duplicateReview.dataset.index;
        const duplicateKey = duplicateIndex === undefined ? "" : externalResultKey(manualResults[Number(duplicateIndex)] || {});
        const rows = (Array.isArray(results) ? results : []).map((result) => ({
          ...result,
          source: result.source || source,
          _search_shelf: result._search_shelf || source
        }));
        manualResults = manualResults
          .filter((result) => resultShelfSource(result) !== source)
          .concat(rows);
        if (selectedKey) {
          const nextIndex = manualResults.findIndex((result) => externalResultKey(result) === selectedKey);
          selectedManualIndex = nextIndex < 0 ? null : nextIndex;
        }
        if (duplicateKey) {
          const nextIndex = manualResults.findIndex((result) => externalResultKey(result) === duplicateKey);
          if (nextIndex < 0) resetDuplicateReview();
          else {
            fields.duplicateReview.dataset.index = String(nextIndex);
            fields.duplicateReview.querySelectorAll("[data-index]").forEach((button) => { button.dataset.index = String(nextIndex); });
          }
        }
        manualSourceVisibleCounts[source] = SEARCH_PAGE_SIZE;
        externalSourcesLastUsed = [...new Set(manualResults.map(resultShelfSource).filter(Boolean))];
        return rows;
      }

      export function updateExternalSearchSummary() {
        const states = externalSourcesAttempted.map((source) => externalSourceSearchStates[source] || {});
        const loading = states.filter((state) => state.status === "loading").length;
        const failed = states.filter((state) => ["error", "timeout", "cooldown"].includes(state.status)).length;
        const fallbacks = states.filter((state) => state.status === "fallback").length;
        const completed = states.length - loading;
        const count = manualResults.length;
        fields.externalResultsJump.textContent = loading
          ? `Resultados externos · consultando ${loading} fuentes`
          : `Resultados externos · ${count}${failed ? " · consulta incompleta" : ""}`;
        if (!states.length) {
          fields.manualSearchStatus.textContent = "";
        } else if (loading) {
          fields.manualSearchStatus.textContent = `${completed}/${states.length} fuentes listas · ${count} ${count === 1 ? "resultado" : "resultados"}`;
        } else if (count) {
          const degraded = failed
            ? ` · ${failed} ${failed === 1 ? "fuente incompleta" : "fuentes incompletas"}`
            : fallbacks
              ? ` · ${fallbacks} ${fallbacks === 1 ? "fuente con respaldo local" : "fuentes con respaldo local"}`
              : "";
          fields.manualSearchStatus.textContent = `${count} ${count === 1 ? "resultado" : "resultados"}${degraded}`;
        } else if (failed) {
          fields.manualSearchStatus.textContent = "No pudimos completar las fuentes externas. Podés reintentarlas por separado.";
        } else {
          fields.manualSearchStatus.textContent = "Sin resultados externos";
        }
      }

      export async function loadLocalSearchResults(query, controller) {
        try {
          const response = await apiFetch(`/api/search?q=${encodeURIComponent(query)}&external=false&catalog=true`, {
            signal: controller.signal
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          if (!isCurrentSearch(controller)) return;
          catalogMergeResults = payload.catalog?.results || [];
          catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
          localSearchState = "ready";
          if (usesUnifiedSearch()) {
            renderManualResults();
            return;
          }
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeKicker.textContent = "Antes de agregar";
          fields.catalogMergeTitle.textContent = "Coincidencias en tu catálogo";
          fields.catalogMergeStatus.textContent = `${catalogMergeResults.length} ${catalogMergeResults.length === 1 ? "obra parecida" : "obras parecidas"}. Revisalas para evitar duplicados.`;
          renderCatalogMergeResults();
        } catch (error) {
          if (error.name === "AbortError" || !isCurrentSearch(controller)) return;
          localSearchState = "error";
          if (usesUnifiedSearch()) {
            renderManualResults();
            return;
          }
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeStatus.textContent = "No pudimos actualizar las coincidencias locales. Tu colección sigue disponible.";
          console.error("[catalog-viewer] local search failed", error);
        }
      }

      export async function loadExternalSourceResults(query, source, controller) {
        const sourceController = new AbortController();
        let timedOut = false;
        const abortSource = () => sourceController.abort();
        controller.signal.addEventListener("abort", abortSource, { once: true });
        const timeoutId = window.setTimeout(() => {
          timedOut = true;
          sourceController.abort();
        }, SEARCH_TIMEOUT_MS);
        try {
          const response = await apiFetch(`/api/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(source)}&external=true&catalog=false`, {
            signal: sourceController.signal
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          if (!isCurrentSearch(controller)) return;
          mergeExternalHealth(payload, source);
          const rows = replaceExternalSourceResults(source, payload.results || []);
          const health = payload.external?.sources?.[source] || {};
          const offlineRows = rows.filter((row) => row.source === "anime_offline_database");
          if (offlineRows.length) {
            externalSourceSearchStates[source] = {
              status: "fallback",
              count: offlineRows.length,
              error: health.error || "",
              retryAfterSeconds: Number(health.retry_after_seconds || 0),
              fallbackReason: offlineRows[0].fallback_reason || "unavailable"
            };
          } else if (rows.length) {
            externalSourceSearchStates[source] = { status: "ready", count: rows.length, error: "" };
          } else if (health.status === "cooldown") {
            externalSourceSearchStates[source] = {
              status: "cooldown",
              count: 0,
              error: health.error || "source_cooldown",
              retryAfterSeconds: Number(health.retry_after_seconds || 0)
            };
          } else if (health.status === "error") {
            externalSourceSearchStates[source] = { status: "error", count: 0, error: health.error || "source_error" };
          } else {
            externalSourceSearchStates[source] = { status: "empty", count: 0, error: "" };
          }
        } catch (error) {
          if (!isCurrentSearch(controller)) return;
          replaceExternalSourceResults(source, []);
          externalSourceSearchStates[source] = timedOut
            ? { status: "timeout", count: 0, error: "timeout" }
            : { status: "error", count: 0, error: error.message || "source_error" };
          if (error.name !== "AbortError") console.error(`[catalog-viewer] ${source} search failed`, error);
        } finally {
          window.clearTimeout(timeoutId);
          controller.signal.removeEventListener("abort", abortSource);
          if (isCurrentSearch(controller)) {
            updateExternalSearchSummary();
            renderManualResults();
            renderDatabaseMenu();
          }
        }
      }

      export async function searchManual(source = "all", statusPrefix = "") {
        const query = fields.query.value.trim();
        if (query.length < 2) return;
        resetDuplicateReview();
        const includeExternal = fields.externalSource.checked || ["add", "link"].includes(collectionSearchMode);
        fields.externalSource.checked = includeExternal;
        if (externalSearchController) externalSearchController.abort();
        const controller = new AbortController();
        externalSearchController = controller;
        const sources = requestedExternalSources(source, includeExternal);
        manualSearchSource = source;
        manualResults = [];
        selectedManualIndex = null;
        unifiedVisibleCount = SEARCH_PAGE_SIZE;
        completedExternalResults.clear();
        localSearchState = usesUnifiedSearch() ? "loading" : "idle";
        manualSourceVisibleCounts = {};
        externalSourcesAttempted = [...sources];
        externalSourcesLastUsed = [];
        externalSourceSearchStates = emptyExternalSourceSearchStates();
        sources.forEach((name) => {
          externalSourceSearchStates[name] = { status: "loading", count: 0, error: "" };
        });
        fields.externalSearchSection.classList.toggle("active", includeExternal || usesUnifiedSearch());
        fields.manualSearchStatus.textContent = statusPrefix || (includeExternal ? "Consultando fuentes…" : "");
        fields.manualSearchResults.innerHTML = "";
        setSearchBusy(true);
        if (includeExternal || usesUnifiedSearch()) renderManualResults();
        setSearchState(
          "searching",
          collectionSearchMode === "search"
            ? includeExternal
              ? `Buscando “${query}” en tu catálogo y fuentes externas…`
              : `Buscando “${query}” en tu catálogo…`
            : collectionSearchMode === "add"
              ? `Buscando “${query}” para agregar y comprobando duplicados…`
            : comparisonSearchMessage()
        );
        const effectiveQuery = effectiveSearchQuery(query);
        const tasks = [];
        if (usesUnifiedSearch()) tasks.push(loadLocalSearchResults(effectiveQuery, controller));
        sources.forEach((name) => tasks.push(loadExternalSourceResults(effectiveQuery, name, controller)));
        try {
          await Promise.allSettled(tasks);
          if (!isCurrentSearch(controller)) return;
          updateExternalSearchSummary();
          setSearchState(
            "results",
            collectionSearchMode === "search"
              ? collectionSearchMessage()
              : collectionSearchMode === "add"
                ? `Revisá las fuentes y las coincidencias locales antes de agregar “${query}”.`
                : comparisonSearchMessage()
          );
          if (includeExternal || usesUnifiedSearch()) renderManualResults();
          renderDatabaseMenu();
        } finally {
          if (externalSearchController === controller) {
            externalSearchController = null;
            setSearchBusy(false);
            if (includeExternal || usesUnifiedSearch()) renderManualResults();
          }
        }
      }

      export async function retryExternalSource(source) {
        const query = fields.query.value.trim();
        if (!isExternalSourceConfigured(source) || !EXTERNAL_SEARCH_SOURCES.includes(source) || query.length < 2 || externalSearchController) return;
        resetDuplicateReview();
        const controller = new AbortController();
        externalSearchController = controller;
        if (!externalSourcesAttempted.includes(source)) externalSourcesAttempted.push(source);
        replaceExternalSourceResults(source, []);
        externalSourceSearchStates[source] = { status: "loading", count: 0, error: "" };
        fields.externalSearchSection.classList.add("active");
        setSearchBusy(true);
        updateExternalSearchSummary();
        renderManualResults();
        setSearchState("searching", `Reintentando ${EXTERNAL_SOURCE_LABELS[source][0]} para “${query}”…`);
        try {
          await loadExternalSourceResults(effectiveSearchQuery(query), source, controller);
          if (!isCurrentSearch(controller)) return;
          updateExternalSearchSummary();
          setSearchState(
            "results",
            collectionSearchMode === "search" ? collectionSearchMessage() : comparisonSearchMessage()
          );
        } finally {
          if (externalSearchController === controller) {
            externalSearchController = null;
            setSearchBusy(false);
            renderManualResults();
            renderDatabaseMenu();
          }
        }
      }

      export function cancelExternalSearch() {
        if (!externalSearchController) return;
        const controller = externalSearchController;
        externalSearchController = null;
        controller.abort();
        externalSourcesAttempted.forEach((source) => {
          if (externalSourceSearchStates[source]?.status === "loading") {
            externalSourceSearchStates[source] = { status: "canceled", count: 0, error: "" };
          }
        });
        setSearchBusy(false);
        fields.manualSearchStatus.textContent = "Búsqueda externa cancelada.";
        renderManualResults();
        setSearchState(
          "results",
          collectionSearchMode === "search" ? collectionSearchMessage() : comparisonSearchMessage()
        );
      }

      export function clearManualSearch({
        focus = true,
        updateHistory = true,
        resetExternal = false,
        forceModeChange = false
      } = {}) {
        resetDuplicateReview();
        const hadSearch = Boolean(activeQuery || fields.query.value.trim());
        if (["compare", "link"].includes(collectionSearchMode) && !forceModeChange) {
          fields.query.value = "";
          activeQuery = "";
          setSearchState("error", "Ingresá al menos 2 caracteres o usá Volver para salir sin perder el paso anterior.");
          if (updateHistory) syncCollectionRoute("push");
          if (focus) fields.query.focus();
          return;
        }
        const returnMode = collectionSearchMode === "add" ? "add" : "browse";
        fields.collectionUtilityMenu.open = false;
        if (externalSearchController) externalSearchController.abort();
        externalSearchController = null;
        setSearchBusy(false);
        manualResults = [];
        manualSourceVisibleCounts = {};
        catalogMergeResults = [];
        selectedManualIndex = null;
        setSelectedManualCandidate();
        setSelectedExistingIdForSearch(null);
        manualSearchSource = "all";
        activeQuery = "";
        setCollectionSearchMode(returnMode);
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        setCatalogVisibleCount(CATALOG_PAGE_SIZE);
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        externalSourceSearchStates = emptyExternalSourceSearchStates();
        if (resetExternal) fields.externalSource.checked = false;
        fields.query.value = "";
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        fields.catalogMergeKicker.textContent = "Comparación";
        fields.catalogMergeTitle.textContent = "Entrada de la colección";
        fields.reviewPrevious.hidden = true;
        fields.reviewNext.hidden = true;
        setSearchState("idle");
        if (updateHistory && hadSearch) syncCollectionRoute("push");
        render();
        renderDatabaseMenu();
        if (focus) fields.query.focus();
      }

      export function showFixedLocalItemForLink(itemId) {
        setCollectionSearchMode("link");
        const item = items.find((entry) => entry.id === itemId);
        showCollectionAnchor("link", item || {}, !item);
        catalogMergeResults = item ? [item] : [];
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeKicker.textContent = "Comparación";
        fields.catalogMergeTitle.textContent = "Entrada seleccionada";
        fields.catalogMergeStatus.textContent = item ? "Entrada seleccionada para comparar." : "No se encontró la entrada seleccionada.";
        renderCatalogMergeResults();
      }

      export async function prepareManualMerge(index) {
        selectedManualIndex = index;
        if (selectedExistingIdForSearch) {
          showFixedLocalItemForLink(selectedExistingIdForSearch);
          setSearchState("results", comparisonSearchMessage());
          fields.searchContext.scrollIntoView({ behavior: "smooth", block: "start" });
          return;
        }
        const result = manualResults[index] || {};
        syncCollectionRoute("replace");
        setSelectedManualCandidate(resultShelfSource(result), candidateReference(result));
        setCollectionSearchMode("compare");
        showCollectionAnchor("compare", result);
        fields.query.value = [result.title, result.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        render();
        syncCollectionRoute("push", { candidate: result });
        await searchCatalogForMerge("", result);
        setSearchState("results", comparisonSearchMessage());
        fields.searchContext.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      export async function searchCatalogForMerge(queryValue = "", incomingResult = null) {
        const query = (queryValue || fields.query.value).trim();
        if (!query) return;
        setCollectionSearchMode("compare");
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeKicker.textContent = "Comparación";
        fields.catalogMergeTitle.textContent = "Elegí una entrada local";
        fields.catalogMergeStatus.textContent = "Enriqueciendo la opción externa y comparando todos sus títulos…";
        fields.catalogMergeResults.innerHTML = "";
        try {
          const response = incomingResult
            ? await apiFetch("/api/search/catalog-candidates", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ result: incomingResult })
              })
            : await apiFetch(`/api/search?q=${encodeURIComponent(query)}&external=false`);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          catalogMergeResults = incomingResult
            ? payload.results || []
            : payload.catalog?.results || [];
          fields.catalogMergeStatus.textContent = `${catalogMergeResults.length} ${catalogMergeResults.length === 1 ? "entrada encontrada" : "entradas encontradas"}. Las coincidencias seguras aparecen primero.`;
          renderCatalogMergeResults();
        } catch (error) {
          catalogMergeResults = [];
          fields.catalogMergeStatus.textContent = "No pudimos comparar con el catálogo. Reintentá desde el resultado externo.";
          console.error("[catalog-viewer] catalog candidate search failed", error);
        }
      }

      export function renderManualResults() {
        fields.collectionView.classList.toggle("has-unified-search", usesUnifiedSearch());
        if (usesUnifiedSearch()) {
          renderUnifiedResults();
          return;
        }
        fields.externalSearchSection.querySelector("#externalSearchTitle").textContent = "Resultados externos";
        const grouped = Object.fromEntries(EXTERNAL_SEARCH_SOURCES.map((source) => [source, []]));
        manualResults.forEach((result, index) => {
          const shelf = resultShelfSource(result);
          if (grouped[shelf]) grouped[shelf].push({ result, index });
        });
        fields.manualSearchResults.innerHTML = Object.entries(EXTERNAL_SOURCE_LABELS).map(([source, labels]) => {
          if (!isExternalSourceConfigured(source)) return "";
          const rows = grouped[source];
          const state = externalSourceSearchStates[source] || { status: "idle", count: 0, error: "" };
          const visibleCount = manualSourceVisibleCounts[source] || SEARCH_PAGE_SIZE;
          const visible = rows.slice(0, visibleCount);
          const more = rows.length > visibleCount
            ? `<button class="load-more source-load-more" type="button" data-click="show-more-manual" data-source="${source}">Cargar más de ${escapeHtml(labels[0])} (${rows.length - visibleCount})</button>`
            : "";
          return `<section class="search-source-group" data-source-group="${source}" aria-busy="${state.status === "loading"}">
            <header class="search-source-heading">
              <div><strong>${escapeHtml(labels[0])}</strong><span>${escapeHtml(labels[1])}</span></div>
              <span>${externalSourceStateLabel(state, rows.length)}</span>
            </header>
            ${externalSourceNotice(source, state)}
            ${rows.length
              ? `<div class="search-source-track">${visible.map(({ result, index }) => searchResult(result, index)).join("")}</div>${more}`
              : externalSourceFeedback(source, state)}
            ${externalSourceAttribution(source, rows)}
          </section>`;
        }).join("");
      }

      export function unifiedResults() {
        const allowedIds = new Set(filteredItems({ includeQuery: false }).map((item) => item.id));
        const local = catalogMergeResults.filter((item) => allowedIds.has(item.id))
          .map((result, index) => ({ result, index, local: true }));
        const external = manualResults.map((result, index) => ({ result, index, local: false }));
        return [...local, ...external].sort((left, right) => {
          const score = Number(right.result._search?.score || 0) - Number(left.result._search?.score || 0);
          if (score) return score;
          if (left.local !== right.local) return left.local ? -1 : 1;
          return `${displayTitle(left.result)}|${left.result.source}|${candidateReference(left.result)}`
            .localeCompare(`${displayTitle(right.result)}|${right.result.source}|${candidateReference(right.result)}`, "es");
        });
      }

      function renderUnifiedResults() {
        const focused = fields.manualSearchResults.contains(document.activeElement) ? document.activeElement : null;
        const focusRow = focused?.closest("article");
        const focusKey = focusRow?.dataset.resultKey;
        const focusId = focusRow?.dataset.localId;
        const focusAction = focused?.dataset.click;
        const sourcesOpen = Boolean(fields.manualSearchResults.querySelector(".unified-sources")?.open);
        const rows = unifiedResults();
        const visible = rows.slice(0, unifiedVisibleCount);
        const localCount = rows.filter((row) => row.local).length;
        const pending = externalSourcesAttempted.filter((source) => externalSourceSearchStates[source]?.status === "loading").length;
        const failed = externalSourcesAttempted.filter((source) => ["error", "timeout", "cooldown"].includes(externalSourceSearchStates[source]?.status)).length;
        fields.catalogMergeSection.classList.remove("active");
        fields.externalSearchSection.classList.add("active");
        fields.externalSearchSection.querySelector("#externalSearchTitle").textContent = "Resultados de búsqueda";
        fields.manualSearchStatus.textContent = `${rows.length} resultados · ${localCount} en tu colección · por relevancia`;
        const states = externalSourcesAttempted.map((source) => {
          const state = externalSourceSearchStates[source] || {};
          return `<div class="unified-source-state" data-source-state="${source}"><strong>${escapeHtml(EXTERNAL_SOURCE_LABELS[source][0])}</strong><span>${externalSourceStateLabel(state, state.count || 0)}</span>${["error", "timeout", "cooldown"].includes(state.status) ? externalSourceFeedback(source, state) : ""}${externalSourceNotice(source, state)}</div>`;
        }).join("");
        const notices = `${localSearchState === "error" ? '<p role="status">No pudimos consultar tu colección. Reintentá la búsqueda.</p>' : ""}${hasActiveCollectionFilters() ? '<p class="unified-filter-note">Los filtros de tu colección se aplican a las obras guardadas.</p>' : ""}`;
        const empty = pending || localSearchState === "loading" ? "Buscando coincidencias…" : "No encontramos obras para esta búsqueda.";
        const more = rows.length > unifiedVisibleCount ? `<button class="load-more unified-load-more" type="button" data-click="show-more-manual">Cargar ${Math.min(SEARCH_PAGE_SIZE, rows.length - unifiedVisibleCount)} más · ${visible.length} de ${rows.length}</button>` : "";
        const attribution = externalSourcesAttempted.map((source) => externalSourceAttribution(source, manualResults.filter((result) => resultShelfSource(result) === source).map((result) => ({ result })))).join("");
        fields.manualSearchResults.innerHTML = `${states ? `<details class="unified-sources"><summary>Fuentes consultadas${pending ? ` · ${pending} buscando` : ""}${failed ? ` · ${failed} incompletas` : ""}</summary><div>${states}</div></details>` : ""}${notices}${mergeSelectionBar()}${duplicateHint(visible.filter((row) => row.local).map((row) => row.result.id))}<div class="unified-result-list" aria-label="Resultados ordenados por relevancia">${visible.length ? visible.map(({ result, index, local }) => local ? localSearchResult(result, index) : searchResult(result, index)).join("") : `<p class="search-source-empty" role="status">${empty}</p>`}</div>${more}${attribution}`;
        const sourcesDetails = fields.manualSearchResults.querySelector(".unified-sources");
        if (sourcesDetails) sourcesDetails.open = sourcesOpen;
        if (focusAction) {
          const rowSelector = focusKey ? `[data-result-key="${CSS.escape(focusKey)}"] ` : focusId ? `[data-local-id="${CSS.escape(focusId)}"] ` : "";
          fields.manualSearchResults.querySelector(`${rowSelector}[data-click="${CSS.escape(focusAction)}"]`)?.focus({ preventScroll: true });
        } else if (focused?.tagName === "SUMMARY") sourcesDetails?.querySelector("summary")?.focus({ preventScroll: true });
      }

      export function externalSourceNotice(source, state) {
        if (source !== "jikan" || state.status !== "fallback") return "";
        const reasons = {
          empty: "Jikan no encontró coincidencias",
          rate_limited: "Jikan alcanzó su límite temporal",
          timeout: "Jikan superó el tiempo de espera",
          upstream_error: "Jikan está temporalmente inestable",
          unavailable: "Jikan no está disponible"
        };
        const reason = reasons[state.fallbackReason] || reasons.unavailable;
        return `<p class="source-provenance is-fallback" role="status"><strong>Respaldo local.</strong> ${escapeHtml(reason)}; mostramos coincidencias del snapshot offline, con su procedencia original.</p>`;
      }

      export function externalSourceAttribution(source, rows) {
        if (source === "tmdb") {
          return `<div class="source-attribution source-attribution-tmdb">
            <img src="/static/img/tmdb-logo.svg" alt="TMDb" width="92" height="12" loading="lazy">
            <span>Este producto usa TMDb y sus APIs pero no está avalado, certificado ni aprobado de ninguna forma por TMDb.</span>
          </div>`;
        }
        if (source !== "jikan") return "";
        const hasOffline = rows.some(({ result }) => result.source === "anime_offline_database");
        const offlineConfigured = Boolean(externalHealth?.sources?.anime_offline_database);
        return `<div class="source-attribution">
          <span><a href="https://jikan.moe/" target="_blank" rel="noreferrer">Jikan</a> es una API no oficial y no está afiliada a MyAnimeList.</span>
          ${hasOffline || offlineConfigured ? `<span>El respaldo usa <a href="https://github.com/manami-project/anime-offline-database" target="_blank" rel="noreferrer">anime-offline-database</a> bajo ODbL/DbCL; snapshot finito, no datos en vivo.</span>` : ""}
        </div>`;
      }

      export function renderCatalogMergeResults() {
        const visible = catalogMergeResults.slice(0, catalogMergeVisibleCount);
        const more = catalogMergeResults.length > catalogMergeVisibleCount
          ? `<button class="load-more" type="button" data-click="show-more-catalog">Cargar más (${catalogMergeResults.length - catalogMergeVisibleCount})</button>`
          : "";
        fields.catalogMergeResults.innerHTML = visible.length
          ? `<div class="search-source-track">${visible.map(catalogMergeResult).join("")}</div>${more}`
          : `<p class="search-source-empty">No encontramos una coincidencia local. Probá otro título o agregá la obra como nueva.</p>`;
      }

      export function showMoreManualResults(source = "") {
        if (usesUnifiedSearch()) {
          const firstNew = unifiedVisibleCount;
          unifiedVisibleCount += SEARCH_PAGE_SIZE;
          renderManualResults();
          fields.manualSearchResults.querySelectorAll(".unified-result-list article")[firstNew]?.querySelector("h3")?.focus({ preventScroll: true });
          return;
        }
        if (source) manualSourceVisibleCounts[source] = (manualSourceVisibleCounts[source] || SEARCH_PAGE_SIZE) + SEARCH_PAGE_SIZE;
        renderManualResults();
      }

      export function showMoreCatalogResults() {
        setCatalogMergeVisibleCount(catalogMergeVisibleCount + SEARCH_PAGE_SIZE);
        renderCatalogMergeResults();
      }

      export async function startWikiReview() {
        wikiReviewQueue = items.filter((item) => !hasExternalLink(item));
        wikiReviewIndex = 0;
        if (!wikiReviewQueue.length) {
          fields.wikiReviewStatus.textContent = "No quedan entradas sin referencia.";
          fields.reviewPrevious.hidden = true;
          fields.reviewNext.hidden = true;
          return;
        }
        await reviewCurrentWikiItem();
      }

      export async function previousWikiReview() {
        if (!wikiReviewQueue.length) await startWikiReview();
        if (!wikiReviewQueue.length) return;
        wikiReviewIndex = Math.max(0, wikiReviewIndex - 1);
        await reviewCurrentWikiItem();
      }

      export async function nextWikiReview() {
        if (!wikiReviewQueue.length) await startWikiReview();
        if (!wikiReviewQueue.length) return;
        wikiReviewIndex = Math.min(wikiReviewQueue.length - 1, wikiReviewIndex + 1);
        await reviewCurrentWikiItem();
      }

      export async function reviewCurrentWikiItem() {
        const item = wikiReviewQueue[wikiReviewIndex];
        if (!item) return;
        fields.wikiReviewStatus.textContent = `${wikiReviewIndex + 1}/${wikiReviewQueue.length}: ${item.title || item.local_name || "Sin titulo"}`;
        fields.reviewPrevious.hidden = false;
        fields.reviewNext.hidden = false;
        fields.reviewPrevious.disabled = wikiReviewIndex === 0;
        fields.reviewNext.disabled = wikiReviewIndex >= wikiReviewQueue.length - 1;
        await findLinkForItem(item);
      }

      export function openSearchDescription(collection, key) {
        const item = collection === "manual"
          ? manualResults[Number(key)]
          : items.find((entry) => entry.id === key);
        if (!item) return;
        const title = displayTitle(item) || "Descripción";
        const description = item.wikipedia_extract || item.description || item.notes || item.review || "Sin descripción.";
        setDescriptionReturnFocus(document.activeElement instanceof HTMLElement ? document.activeElement : null);
        fields.descriptionDialogTitle.textContent = title;
        fields.descriptionDialogText.textContent = description;
        fields.descriptionDialog.showModal();
        fields.closeDescriptionDialog.focus();
      }

      export function closeDescriptionDialog() {
        if (fields.descriptionDialog.open) fields.descriptionDialog.close();
      }

      export function restoreDescriptionFocus() {
        const target = descriptionReturnFocus;
        setDescriptionReturnFocus(null);
        if (target?.isConnected) target.focus({ preventScroll: true });
      }

      export async function addSearchResult(index) {
        const button = fields.manualSearchResults.querySelector(`.external-result [data-click="add-result"][data-index="${index}"]`);
        if (!button) return;
        const targetId = selectedExistingIdForSearch;
        const idleLabel = targetId ? "Combinar" : "Agregar a colección";
        let completed = false;
        button.disabled = true;
        button.textContent = targetId ? "Preparando..." : "Agregando...";
        try {
          if (targetId) {
            if (!isExternalResult(manualResults[index])) {
              reportExternalResultProblem("Ese resultado no tiene un enlace reconocido. Elegí una opción de Wikipedia, IMDb, FilmAffinity o Jikan.");
              return;
            }
            await mergeSearchResult(index, targetId);
            return;
          }
          const response = await apiFetch("/api/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(manualResults[index])
          });
          const payload = await response.json();
          if (payload.reason === "possible_duplicate") {
            button.textContent = idleLabel;
            showDuplicateChoice(index, payload.candidates || []);
            return;
          }
          if (!response.ok || (!payload.ok && payload.reason !== "duplicate")) {
            throw new Error(payload.reason || `HTTP ${response.status}`);
          }
          completed = true;
          if (payload.reason === "duplicate") {
            button.textContent = "Ya existe";
          } else if (payload.reason === "merged_into_existing") {
            button.textContent = "Combinado";
            fields.manualSearchStatus.textContent = `Se combinó con "${payload.item?.title || "la ficha existente"}", ya en tu colección.`;
          } else {
            button.textContent = "Agregado";
          }
          completedExternalResults.set(externalResultKey(manualResults[index]), button.textContent);
          await load();
          if (payload.background_enrichment === "scheduled") {
            window.setTimeout(() => load(), 12000);
          }
        } catch (error) {
          console.error("[catalog-viewer] add result failed", error);
          reportExternalResultProblem("No pudimos guardar ese resultado. Reintentá desde esta búsqueda.");
        } finally {
          if (button.isConnected) {
            button.disabled = completed;
            if (["Preparando...", "Agregando..."].includes(button.textContent)) button.textContent = idleLabel;
          }
        }
      }

      export function reportExternalResultProblem(message) {
        fields.manualSearchStatus.textContent = message;
        setSearchState("error", `${message} La colección no fue modificada.`);
      }

      export async function forceAddSearchResult(index) {
        const button = fields.duplicateReview.querySelector('[data-click="force-add"]');
        if (button) button.disabled = true;
        try {
          const response = await postAdd(manualResults[index], "force", "");
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          resetDuplicateReview();
          await load();
          await runSearch();
        } catch (error) {
          console.error("[catalog-viewer] force add failed", error);
          reportExternalResultProblem("No pudimos agregar la obra distinta. Reintentá desde esta revisión.");
          if (button?.isConnected) button.disabled = false;
        }
      }

      export function resetDuplicateReview() {
        fields.duplicateReview.hidden = true;
        fields.duplicateReview.innerHTML = "";
        delete fields.duplicateReview.dataset.index;
      }

      export function dismissDuplicateReview() {
        const index = fields.duplicateReview.dataset.index;
        resetDuplicateReview();
        fields.manualSearchResults.querySelector(`.external-result [data-click="add-result"][data-index="${index}"]`)
          ?.focus({ preventScroll: true });
      }

      export async function postAdd(result, action, targetId) {
        const target = items.find((entry) => entry.id === targetId);
        return apiFetch("/api/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            result,
            action,
            target_id: targetId,
            target_source_file: target?._source_file || "",
            expected_source: ""
          })
        });
      }

      export function matchesNormalizedSearchText(normalizedValue, normalizedQuery) {
        if (!normalizedQuery || normalizedValue.includes(normalizedQuery)) return true;
        const words = normalizedValue.split(/\s+/).filter(Boolean);
        return normalizedQuery.split(/\s+/).filter(Boolean).every((term) => (
          words.some((word) => word.includes(term) || (term.length >= 5 && oneEditApart(word, term)))
        ));
      }

      export function isExternalResult(result) {
        return result?.source === "wikipedia"
          || result?.source === "imdb"
          || result?.source === "filmaffinity"
          || result?.source === "jikan"
          || result?.source === "tmdb"
          || hasHost(result?.url, "wikipedia.org")
          || hasHost(result?.url, "imdb.com")
          || hasHost(result?.url, "filmaffinity.com")
          || hasHost(result?.url, "myanimelist.net")
          || hasHost(result?.url, "themoviedb.org")
          || hasHost(result?.wikipedia_url, "wikipedia.org")
          || hasHost(result?.imdb_url, "imdb.com")
          || hasHost(result?.filmaffinity_url, "filmaffinity.com")
          || hasHost(result?.myanimelist_url, "myanimelist.net")
          || hasHost(result?.tmdb_url, "themoviedb.org");
      }
