import { load } from "../core/catalog-data.js";
import { fields } from "../core/fields.js";
import { displayTitle, escapeHtml, hasExternalLink, hasHost } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { mergeSearchResult } from "../core/merge.js";
import { showView } from "../core/router.js";
import { findLinkForItem } from "../core/search-bridge.js";
import { CATALOG_PAGE_SIZE, SEARCH_PAGE_SIZE, items, selectedExistingIdForSearch, setSelectedExistingIdForSearch } from "../core/state.js";
import { collectionSearchMessage, collectionSearchMode, comparisonSearchMessage, render, renderDatabaseMenu, setCatalogVisibleCount, setCollectionSearchMode, setRandomOrder, syncCollectionRoute } from "./catalog-grid.js";
import { catalogMergeResult, externalSourceFeedback, externalSourceStateLabel, oneEditApart, searchResult, showDuplicateChoice } from "./catalog-search-cards.js";

      export let manualResults = [];

      export let selectedManualIndex = null;

      export let manualSearchSource = "all";

      export let catalogMergeResults = [];

      export let wikiReviewQueue = [];

      export let wikiReviewIndex = 0;

      export let descriptionReturnFocus = null;

      export let activeQuery = "";

      export let manualSourceVisibleCounts = {};

      export let catalogMergeVisibleCount = 6;

      export let externalSourcesLastUsed = [];

      export let externalSourcesAttempted = [];

      export let externalSearchController = null;

      export let externalSourceSearchStates = {};

      export let externalHealth = { sources: {}, cache: {} };

      export const SEARCH_TIMEOUT_MS = 10000;

      export const EXTERNAL_SEARCH_SOURCES = ["wikipedia", "imdb", "filmaffinity"];

      export const EXTERNAL_SOURCE_LABELS = {
        wikipedia: ["Wikipedia", "Artículos y datos enciclopédicos"],
        imdb: ["IMDb", "Títulos internacionales y reparto"],
        filmaffinity: ["FilmAffinity", "Referencias en español"]
      };
      externalSourceSearchStates = emptyExternalSourceSearchStates();

      export function setManualResults(value) {
        manualResults = value;
      }

      export function setSelectedManualIndex(value) {
        selectedManualIndex = value;
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

      export async function runSearch({ updateHistory = true } = {}) {
        const requestedQuery = fields.query.value.trim();
        fields.collectionUtilityMenu.open = false;
        if (!requestedQuery) {
          clearManualSearch({ focus: false, updateHistory });
          return;
        }
        activeQuery = requestedQuery.length >= 2 ? requestedQuery : "";
        if (collectionSearchMode !== "browse") {
          await refineComparisonSearch(requestedQuery, { updateHistory });
          return;
        }
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
        setCollectionSearchMode("browse");
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
        const comparisonMode = collectionSearchMode !== "browse";
        fields.collectionView.classList.toggle("has-search-results", Boolean(activeQuery) && state !== "idle");
        fields.searchContext.hidden = state !== "searching" && state !== "error" && !comparisonMode;
        fields.searchContext.dataset.state = state;
        fields.searchContextText.textContent = message;
        fields.cancelSearch.hidden = state !== "searching";
        fields.clearManualSearch.hidden = state === "idle" && !comparisonMode;
        fields.backToCollection.hidden = !comparisonMode;
      }

      export function emptyExternalSourceSearchStates() {
        return Object.fromEntries(EXTERNAL_SEARCH_SOURCES.map((source) => [source, {
          status: "idle",
          count: 0,
          error: ""
        }]));
      }

      export function requestedExternalSources(source, includeExternal) {
        if (!includeExternal) return [];
        return source === "all" || !EXTERNAL_SEARCH_SOURCES.includes(source)
          ? [...EXTERNAL_SEARCH_SOURCES]
          : [source];
      }

      export function setSearchBusy(busy) {
        fields.searchButton.disabled = busy;
        fields.searchButton.textContent = busy ? "Buscando..." : "Buscar";
        fields.searchConsole.setAttribute("aria-busy", String(busy));
        if (busy) fields.searchButton.setAttribute("aria-busy", "true");
        else fields.searchButton.removeAttribute("aria-busy");
      }

      export function isCurrentSearch(controller) {
        return externalSearchController === controller && !controller.signal.aborted;
      }

      export function mergeExternalHealth(payload, source) {
        const incoming = payload?.external || {};
        externalHealth = {
          ...externalHealth,
          sources: {
            ...(externalHealth?.sources || {}),
            ...(incoming.sources?.[source] ? { [source]: incoming.sources[source] } : {})
          },
          cache: incoming.cache || externalHealth?.cache || {}
        };
      }

      export function replaceExternalSourceResults(source, results) {
        const rows = (Array.isArray(results) ? results : []).map((result) => ({
          ...result,
          source: result.source || source
        }));
        manualResults = manualResults
          .filter((result) => result.source !== source)
          .concat(rows);
        manualSourceVisibleCounts[source] = SEARCH_PAGE_SIZE;
        externalSourcesLastUsed = [...new Set(manualResults.map((result) => result.source || "").filter(Boolean))];
        return rows;
      }

      export function updateExternalSearchSummary() {
        const states = externalSourcesAttempted.map((source) => externalSourceSearchStates[source] || {});
        const loading = states.filter((state) => state.status === "loading").length;
        const failed = states.filter((state) => ["error", "timeout"].includes(state.status)).length;
        const completed = states.length - loading;
        const count = manualResults.length;
        if (!states.length) {
          fields.manualSearchStatus.textContent = "";
        } else if (loading) {
          fields.manualSearchStatus.textContent = `${completed}/${states.length} fuentes listas · ${count} ${count === 1 ? "resultado" : "resultados"}`;
        } else if (count) {
          fields.manualSearchStatus.textContent = `${count} ${count === 1 ? "resultado" : "resultados"}${failed ? ` · ${failed} ${failed === 1 ? "fuente incompleta" : "fuentes incompletas"}` : ""}`;
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
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeKicker.textContent = "Tu catálogo";
          fields.catalogMergeTitle.textContent = "Coincidencias locales";
          fields.catalogMergeStatus.textContent = `${catalogMergeResults.length} ${catalogMergeResults.length === 1 ? "obra encontrada" : "obras encontradas"}, sin aplicar los filtros de la estantería.`;
          renderCatalogMergeResults();
        } catch (error) {
          if (error.name === "AbortError" || !isCurrentSearch(controller)) return;
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
          externalSourceSearchStates[source] = rows.length
            ? { status: "ready", count: rows.length, error: "" }
            : health.status === "error"
              ? { status: "error", count: 0, error: health.error || "source_error" }
              : { status: "empty", count: 0, error: "" };
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
        const includeExternal = fields.externalSource.checked;
        if (externalSearchController) externalSearchController.abort();
        const controller = new AbortController();
        externalSearchController = controller;
        const sources = requestedExternalSources(source, includeExternal);
        manualSearchSource = source;
        manualResults = [];
        selectedManualIndex = null;
        manualSourceVisibleCounts = {};
        externalSourcesAttempted = [...sources];
        externalSourcesLastUsed = [];
        externalSourceSearchStates = emptyExternalSourceSearchStates();
        sources.forEach((name) => {
          externalSourceSearchStates[name] = { status: "loading", count: 0, error: "" };
        });
        fields.externalSearchSection.classList.toggle("active", includeExternal);
        fields.manualSearchStatus.textContent = statusPrefix || (includeExternal ? "Consultando fuentes…" : "");
        fields.manualSearchResults.innerHTML = "";
        setSearchBusy(true);
        if (includeExternal) renderManualResults();
        setSearchState(
          "searching",
          collectionSearchMode === "browse"
            ? includeExternal
              ? `Buscando “${query}” en tu catálogo y fuentes externas…`
              : `Buscando “${query}” en tu catálogo…`
            : comparisonSearchMessage()
        );
        const tasks = [];
        if (collectionSearchMode === "browse") tasks.push(loadLocalSearchResults(query, controller));
        sources.forEach((name) => tasks.push(loadExternalSourceResults(query, name, controller)));
        try {
          await Promise.allSettled(tasks);
          if (!isCurrentSearch(controller)) return;
          updateExternalSearchSummary();
          setSearchState(
            "results",
            collectionSearchMode === "browse" ? collectionSearchMessage() : comparisonSearchMessage()
          );
          if (includeExternal) renderManualResults();
          renderDatabaseMenu();
        } finally {
          if (externalSearchController === controller) {
            externalSearchController = null;
            setSearchBusy(false);
            if (includeExternal) renderManualResults();
          }
        }
      }

      export async function retryExternalSource(source) {
        const query = fields.query.value.trim();
        if (!EXTERNAL_SEARCH_SOURCES.includes(source) || query.length < 2 || externalSearchController) return;
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
          await loadExternalSourceResults(query, source, controller);
          if (!isCurrentSearch(controller)) return;
          updateExternalSearchSummary();
          setSearchState(
            "results",
            collectionSearchMode === "browse" ? collectionSearchMessage() : comparisonSearchMessage()
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
          collectionSearchMode === "browse" ? collectionSearchMessage() : comparisonSearchMessage()
        );
      }

      export function clearManualSearch({ focus = true, updateHistory = true, resetExternal = false } = {}) {
        const hadSearch = Boolean(activeQuery || fields.query.value.trim());
        fields.collectionUtilityMenu.open = false;
        if (externalSearchController) externalSearchController.abort();
        externalSearchController = null;
        setSearchBusy(false);
        manualResults = [];
        manualSourceVisibleCounts = {};
        catalogMergeResults = [];
        selectedManualIndex = null;
        setSelectedExistingIdForSearch(null);
        manualSearchSource = "all";
        activeQuery = "";
        setCollectionSearchMode("browse");
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
        setCollectionSearchMode("compare");
        fields.query.value = [result.title, result.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        render();
        syncCollectionRoute("push");
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
        const grouped = Object.fromEntries(EXTERNAL_SEARCH_SOURCES.map((source) => [source, []]));
        manualResults.forEach((result, index) => {
          if (grouped[result.source]) grouped[result.source].push({ result, index });
        });
        fields.manualSearchResults.innerHTML = Object.entries(EXTERNAL_SOURCE_LABELS).map(([source, labels]) => {
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
            ${rows.length
              ? `<div class="search-source-track">${visible.map(({ result, index }) => searchResult(result, index)).join("")}</div>${more}`
              : externalSourceFeedback(source, state)}
          </section>`;
        }).join("");
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
        const cards = [...fields.manualSearchResults.querySelectorAll("[data-index]")];
        const button = cards.find((element) => Number(element.dataset.index) === index);
        if (!button) return;
        const targetId = selectedExistingIdForSearch;
        const idleLabel = targetId ? "Combinar" : "Agregar";
        let completed = false;
        button.disabled = true;
        button.textContent = targetId ? "Preparando..." : "Agregando...";
        try {
          if (targetId) {
            if (!isExternalResult(manualResults[index])) {
              reportExternalResultProblem("Ese resultado no tiene un enlace reconocido. Elegí una opción de Wikipedia, IMDb o FilmAffinity.");
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
          button.textContent = payload.reason === "duplicate" ? "Ya existe" : "Agregado";
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
        await postAdd(manualResults[index], "force", "");
        await load();
        await runSearch();
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
          || hasHost(result?.url, "wikipedia.org")
          || hasHost(result?.url, "imdb.com")
          || hasHost(result?.url, "filmaffinity.com")
          || hasHost(result?.wikipedia_url, "wikipedia.org")
          || hasHost(result?.imdb_url, "imdb.com")
          || hasHost(result?.filmaffinity_url, "filmaffinity.com");
      }
