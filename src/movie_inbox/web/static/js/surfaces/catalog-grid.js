import { card, shuffle } from "../core/card.js";
import { editorialRevision, load, sourceFiles, writeJsonPath } from "../core/catalog-data.js";
import { renderDetail, selectedDetailId, setDetailFeedback } from "../core/detail.js";
import { fields } from "../core/fields.js";
import { asList, availabilityState, displayTitle, escapeAttr, escapeHtml, hasExternalLink, hasHost, isInCatalog, localFilesText, normalizeRating, normalizeText, setInlineFeedback, todayLocalDate } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { goToCollection, routeValuesForView, syncRoute } from "../core/router.js";
import { CATALOG_PAGE_SIZE, currentView, items, selectedExistingIdForSearch } from "../core/state.js";
import { activeQuery, clearManualSearch, externalHealth, externalSourceSearchStates, externalSourcesAttempted, externalSourcesLastUsed, manualResults, matchesNormalizedSearchText, selectedManualIndex, setSearchState } from "./catalog-search.js";
import { renderEditorialHome } from "./home.js";

      export let catalogSearchIndex = new WeakMap();

      export let catalogMetrics = emptyCatalogMetrics();

      export let catalogRevision = 0;

      export let lastCatalogGridKey = "";

      export let lastEditorialRenderRevision = -1;

      export let randomOrder = [];

      export let collectionSearchMode = "browse";

      export let duplicatesOnly = false;

      export let collectionFilters = {
        status: new Set(),
        availability: new Set(),
        kind: new Set(),
        source: new Set(),
        decade: new Set(),
        genre: new Set(),
        director: new Set(),
        record: new Set(),
        release_day: new Set()
      };

      export let collectionYearRange = { from: "", to: "" };

      export let catalogVisibleCount = 36;

      export const COLLECTION_MULTI_FILTER_KEYS = [
        "status", "availability", "kind", "source", "decade", "genre", "director", "record", "release_day"
      ];

      export function setLastEditorialRenderRevision(value) {
        lastEditorialRenderRevision = value;
      }

      export function setRandomOrder(value) {
        randomOrder = value;
      }

      export function setCatalogVisibleCount(value) {
        catalogVisibleCount = value;
      }

      export function randomCandidates() {
        const filtered = currentView === "catalog" ? filteredItems() : [];
        const candidates = filtered.length ? filtered : items;
        return fields.randomCatalogOnly.checked
          ? candidates.filter((item) => isInCatalog(item.en_catalogo))
          : candidates;
      }

      export function syncRandomControl() {
        const count = randomCandidates().length;
        const catalogOnly = fields.randomCatalogOnly.checked;
        fields.randomScopeLabel.textContent = catalogOnly ? "Disponibles" : "Todo";
        fields.randomButton.disabled = count === 0;
        fields.randomButton.title = count
          ? `Abrir una ficha al azar entre ${count} ${catalogOnly ? "obras disponibles" : "obras"}`
          : catalogOnly ? "No hay obras disponibles con los filtros actuales" : "No hay obras para elegir";
      }

      export function changeRandomScope(source) {
        const catalogOnly = Boolean(source.checked);
        fields.randomCatalogOnly.checked = catalogOnly;
        syncRandomControl();
      }

      export function catalogDetailItems() {
        return applyRandomOrder(sortItems(filteredItems()));
      }

      export function collectionRouteValues() {
        const values = {
          q: activeQuery,
          year_from: collectionYearRange.from,
          year_to: collectionYearRange.to,
          sort: fields.sort.value && fields.sort.value !== "original" ? fields.sort.value : "",
          duplicates: duplicatesOnly ? "1" : "",
          external: activeQuery && fields.externalSource.checked ? "1" : "",
          director: activeQuery && fields.searchByDirector.checked ? "1" : "",
          mode: collectionSearchMode !== "browse" ? collectionSearchMode : "",
          link_id: collectionSearchMode === "link" ? selectedExistingIdForSearch || "" : ""
        };
        for (const key of COLLECTION_MULTI_FILTER_KEYS) {
          values[key] = [...collectionFilters[key]].sort((left, right) => left.localeCompare(right, "es"));
        }
        return values;
      }

      export function syncCollectionRoute(method = "replace") {
        syncRoute(routeValuesForView("catalog"), method);
      }

      export function applyCollectionRoute(params) {
        collectionFilters = emptyCollectionFilters();
        for (const key of COLLECTION_MULTI_FILTER_KEYS) {
          for (const value of params.getAll(key).map((entry) => entry.trim()).filter(Boolean)) {
            collectionFilters[key].add(value);
          }
        }
        collectionYearRange = {
          from: validCollectionYear(params.get("year_from")),
          to: validCollectionYear(params.get("year_to"))
        };
        const requestedSort = params.get("sort") || "original";
        fields.sort.value = [...fields.sort.options].some((option) => option.value === requestedSort)
          ? requestedSort
          : "original";
        duplicatesOnly = params.get("duplicates") === "1";
        fields.externalSource.checked = params.get("external") === "1";
        fields.searchByDirector.checked = params.get("director") === "1";
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        syncCollectionFilterControls();
      }

      export function setupCollectionFilterOptions() {
        const statuses = uniqueFilterValues(items.map((item) => item.status));
        const kinds = uniqueFilterValues(items.map((item) => item.kind));
        renderQuickFilterGroup(fields.statusQuickFilters, "status", statuses);
        renderQuickFilterGroup(fields.availabilityQuickFilters, "availability", ["available", "unavailable"]);
        renderQuickFilterGroup(fields.kindQuickFilters, "kind", kinds);

        const decades = uniqueFilterValues(
          items.map((item) => numericYear(item.year)).filter(Boolean).map((year) => String(Math.floor(year / 10) * 10)),
          { numeric: true }
        );
        setupFilterAddSelect(fields.decadeFilter, "Agregar década", decades, (value) => `Años ${value}`);
        setupFilterAddSelect(
          fields.genreFilter,
          "Agregar género",
          items.flatMap((item) => asList(item.genres))
        );
        setupFilterAddSelect(
          fields.directorFilter,
          "Agregar dirección",
          items.flatMap((item) => asList(item.directors))
        );
        setupFilterAddSelect(fields.sourceFilter, "Agregar fuente", items.map((item) => item.source), (value) => (
          filterValueLabel("Fuente", value)
        ));
        syncCollectionFilterControls();
      }

      export function uniqueFilterValues(values, options = {}) {
        const byKey = new Map();
        for (const rawValue of values) {
          const value = String(rawValue || "").trim();
          const key = normalizeText(value);
          if (value && key && !byKey.has(key)) byKey.set(key, value);
        }
        const collator = new Intl.Collator("es", { sensitivity: "base", numeric: Boolean(options.numeric) });
        return [...byKey.values()].sort(collator.compare);
      }

      export function setupFilterAddSelect(select, placeholder, values, label = (value) => value) {
        const unique = uniqueFilterValues(values, { numeric: select === fields.decadeFilter });
        select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>` + unique.map((value) => (
          `<option value="${escapeAttr(value)}">${escapeHtml(label(value))}</option>`
        )).join("");
        select.value = "";
      }

      export function renderQuickFilterGroup(container, filter, values) {
        container.innerHTML = values.map((value) => (
          `<button type="button" data-click="toggle-collection-filter" data-filter="${escapeAttr(filter)}" data-value="${escapeAttr(value)}" aria-pressed="false">${escapeHtml(filterValueLabel(filter, value))}</button>`
        )).join("");
      }

      export function filterValueLabel(label, value) {
        const normalized = String(value || "").toLowerCase();
        const labels = {
          watched: "Vista",
          to_watch: "Por ver",
          available: "Disponible",
          unavailable: "Sin disponibilidad",
          unrated: "Sin puntaje",
          unreviewed: "Sin review",
          pelicula: "Película",
          serie: "Serie",
          anime: "Anime",
          documental: "Documental",
          local_files: "Archivos locales",
            wikipedia: "Wikipedia",
            imdb: "IMDb",
            filmaffinity: "FilmAffinity",
            jikan: "Jikan / MyAnimeList",
            anime_offline_database: "Anime DB offline"
        };
        return labels[normalized] || String(value || label);
      }

      export function renderDatabaseMenu() {
        const sourceList = sourceFiles.length
          ? sourceFiles.map((file) => {
              const storage = /\.(db|sqlite|sqlite3)$/i.test(file) ? "SQLite" : "JSON";
              return `<div class="db-item"><strong>${storage}</strong><span>${escapeHtml(file)}</span></div>`;
            }).join("")
          : `<div class="db-item"><strong>Catalogo</strong><span>Sin archivo resuelto.</span></div>`;
        fields.databaseCatalogPanel.innerHTML = `
          <label>
            Catalogo editable
            <input type="text" readonly value="${escapeAttr(writeJsonPath || "-")}">
          </label>
          <div class="db-list">${sourceList}</div>
        `;
        fields.databaseExternalPanel.innerHTML = `
          <div class="db-list">
            ${externalDatabaseItem("Wikipedia", "wikipedia")}
            ${externalDatabaseItem("IMDb", "imdb")}
            ${externalDatabaseItem("FilmAffinity", "filmaffinity")}
            ${externalDatabaseItem("Jikan", "jikan")}
            ${externalOfflineDatabaseItem()}
            ${externalCacheItem()}
          </div>
        `;
      }

      export async function downloadCatalogExport(event) {
        const button = event.target.closest("[data-catalog-export]");
        if (!button) return;
        const format = String(button.dataset.catalogExport || "").toLowerCase();
        if (!["json", "csv"].includes(format)) return;
        const buttons = [...fields.catalogExportActions.querySelectorAll("button")];
        buttons.forEach((control) => { control.disabled = true; });
        fields.catalogExportActions.setAttribute("aria-busy", "true");
        setInlineFeedback(fields.catalogExportFeedback, "Preparando la copia portable...", "working");
        try {
          const response = await apiFetch(`/api/catalog/export?format=${encodeURIComponent(format)}`);
          if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.reason || `http_${response.status}`);
          }
          const blob = await response.blob();
          const disposition = response.headers.get("Content-Disposition") || "";
          const named = disposition.match(/filename="([^"]+)"/i);
          const filename = named?.[1] || `movie-inbox-catalog.${format}`;
          const href = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = href;
          link.download = filename;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(href), 0);
          setInlineFeedback(fields.catalogExportFeedback, `${filename} descargado.`, "success");
        } catch (error) {
          console.error(error);
          setInlineFeedback(
            fields.catalogExportFeedback,
            "No pudimos preparar la descarga. Actualizá los datos e intentá nuevamente.",
            "error"
          );
        } finally {
          buttons.forEach((control) => { control.disabled = false; });
          fields.catalogExportActions.removeAttribute("aria-busy");
        }
      }

      export function externalDatabaseItem(label, source) {
        const health = externalHealth?.sources?.[source] || {};
        const consumed = externalSourcesLastUsed.includes(source);
        const attempted = externalSourcesAttempted.includes(source);
        const searchState = externalSourceSearchStates[source]?.status || "idle";
        const stateLabels = { ready: "lista", ok: "disponible", empty: "sin resultados", error: "error", cooldown: "pausa temporal" };
        const state = stateLabels[health.status] || (fields.externalSource.checked ? "lista" : "apagada");
        const request = searchState === "loading"
          ? "consultando"
          : ["error", "timeout"].includes(searchState)
            ? "consulta incompleta"
            : attempted ? (consumed ? `${health.result_count || 0} resultados` : "sin resultados") : "sin consultar";
        const latency = health.latency_ms ? `${health.latency_ms} ms` : "";
        const error = health.error ? ` | ${health.error}` : "";
        const cooldown = Number(health.retry_after_seconds || 0)
          ? `reintento en ${formatSourceDelay(health.retry_after_seconds)}`
          : "";
        const status = [state, request, latency, cooldown].filter(Boolean).join(" | ") + error;
        return `<div class="db-item"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(status)}</span></div>`;
      }

      export function externalOfflineDatabaseItem() {
        const health = externalHealth?.sources?.anime_offline_database;
        if (!health) return "";
        const labels = { ready: "lista", ok: "disponible", empty: "sin coincidencias", error: "error" };
        const state = labels[health.status] || health.status || "lista";
        const snapshot = health.snapshot_date ? `snapshot ${health.snapshot_date}` : "snapshot local";
        const count = health.last_attempt_at ? `${Number(health.result_count || 0)} resultados` : "sin consultar";
        return `<div class="db-item"><strong>Anime DB offline</strong><span>${escapeHtml([state, snapshot, count].join(" | "))}</span></div>`;
      }

      export function formatSourceDelay(seconds) {
        const value = Math.max(1, Number(seconds || 0));
        return value < 60 ? `${Math.ceil(value)} s` : `${Math.ceil(value / 60)} min`;
      }

      export function externalCacheItem() {
        const cache = externalHealth?.cache || {};
        const entries = Number(cache.search_entries || 0) + Number(cache.metadata_entries || 0);
        return `<div class="db-item"><strong>Cache</strong><span>${entries} entradas | ${Number(cache.hits || 0)} hits | ${Number(cache.misses || 0)} misses</span></div>`;
      }

      export function setCollectionSearchMode(mode = "browse") {
        collectionSearchMode = ["browse", "compare", "link"].includes(mode) ? mode : "browse";
        const comparisonMode = collectionSearchMode !== "browse";
        fields.collectionView.classList.toggle("is-compare-mode", comparisonMode);
        fields.collectionView.dataset.searchMode = collectionSearchMode;
        fields.backToCollection.hidden = !comparisonMode;
        if (!comparisonMode && !activeQuery) {
          fields.catalogMergeKicker.textContent = "Comparación";
          fields.catalogMergeTitle.textContent = "Entrada de la colección";
        }
      }

      export function collectionSearchMessage() {
        const count = filteredItems().length;
        const noun = count === 1 ? "título" : "títulos";
        return `${count} ${noun} en tu colección para “${activeQuery}”.`;
      }

      export function comparisonSearchMessage() {
        if (collectionSearchMode === "link") {
          const selected = items.find((item) => item.id === selectedExistingIdForSearch);
          return `Buscando una referencia para “${displayTitle(selected || {}) || activeQuery}”.`;
        }
        const incoming = manualResults[selectedManualIndex] || {};
        return `Elegí la entrada local que corresponde a “${displayTitle(incoming) || activeQuery}”.`;
      }

      export function emptyCollectionFilters() {
        return Object.fromEntries(COLLECTION_MULTI_FILTER_KEYS.map((key) => [key, new Set()]));
      }

      export function validCollectionYear(value) {
        const year = String(value || "").trim();
        return /^(18|19|20|21)\d{2}$/.test(year) ? year : "";
      }

      export function matchingFilterValue(values, value) {
        const key = normalizeText(value);
        return [...values].find((candidate) => normalizeText(candidate) === key) || "";
      }

      export function setCollectionFilterValue(filter, value, selected) {
        if (!COLLECTION_MULTI_FILTER_KEYS.includes(filter) || !String(value || "").trim()) return;
        const values = collectionFilters[filter];
        const existing = matchingFilterValue(values, value);
        if (selected && !existing) values.add(String(value).trim());
        if (!selected && existing) values.delete(existing);
      }

      export function toggleCollectionFilter(filter, value) {
        if (!COLLECTION_MULTI_FILTER_KEYS.includes(filter) || !value) return;
        setCollectionFilterValue(filter, value, !matchingFilterValue(collectionFilters[filter], value));
        collectionFiltersChanged();
      }

      export function collectionFiltersChanged() {
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        syncCollectionFilterControls();
        render();
        syncCollectionRoute("push");
      }

      export function applyCollectionFilterDescriptor(descriptor) {
        if (!descriptor || typeof descriptor !== "object") return;
        for (const key of COLLECTION_MULTI_FILTER_KEYS) {
          const values = Array.isArray(descriptor[key]) ? descriptor[key] : [descriptor[key]];
          values.filter(Boolean).forEach((value) => setCollectionFilterValue(key, String(value), true));
        }
        collectionYearRange = {
          from: validCollectionYear(descriptor.year_from),
          to: validCollectionYear(descriptor.year_to)
        };
        if (descriptor.sort && [...fields.sort.options].some((option) => option.value === descriptor.sort)) {
          fields.sort.value = descriptor.sort;
        }
        syncCollectionFilterControls();
      }

      export function applyCollectionYearRange() {
        const from = validCollectionYear(fields.yearFromFilter.value);
        const to = validCollectionYear(fields.yearToFilter.value);
        const invalidFrom = Boolean(fields.yearFromFilter.value && !from);
        const invalidTo = Boolean(fields.yearToFilter.value && !to);
        fields.yearFromFilter.setCustomValidity(invalidFrom ? "Ingresá un año entre 1800 y 2199." : "");
        fields.yearToFilter.setCustomValidity(invalidTo ? "Ingresá un año entre 1800 y 2199." : "");
        if (invalidFrom || invalidTo) {
          (invalidFrom ? fields.yearFromFilter : fields.yearToFilter).reportValidity();
          return;
        }
        collectionYearRange = from && to && Number(from) > Number(to)
          ? { from: to, to: from }
          : { from, to };
        collectionFiltersChanged();
      }

      export function syncCollectionFilterControls() {
        document.querySelectorAll('[data-click="toggle-collection-filter"]').forEach((button) => {
          const values = collectionFilters[button.dataset.filter];
          const selected = values instanceof Set && Boolean(matchingFilterValue(values, button.dataset.value || ""));
          button.setAttribute("aria-pressed", String(selected));
        });
        fields.yearFromFilter.value = collectionYearRange.from;
        fields.yearToFilter.value = collectionYearRange.to;
        const advancedKeys = ["source", "decade", "genre", "director", "record", "release_day"];
        const count = advancedKeys.reduce((total, key) => total + collectionFilters[key].size, 0)
          + (collectionYearRange.from || collectionYearRange.to ? 1 : 0);
        fields.advancedFilterCount.hidden = count === 0;
        fields.advancedFilterCount.textContent = String(count);
        fields.advancedFiltersMenu.classList.toggle("has-active-filters", count > 0);
      }

      export function filterSetMatchesValue(values, value) {
        return !values.size || Boolean(matchingFilterValue(values, value));
      }

      export function filterSetMatchesList(values, candidates) {
        if (!values.size) return true;
        return asList(candidates).some((candidate) => matchingFilterValue(values, candidate));
      }

      export function matchesYearFilters(item) {
        const decades = collectionFilters.decade;
        const hasRange = Boolean(collectionYearRange.from || collectionYearRange.to);
        if (!decades.size && !hasRange) return true;
        const year = numericYear(item.year);
        if (!year) return false;
        const decadeMatch = decades.size && matchingFilterValue(decades, String(Math.floor(year / 10) * 10));
        const rangeMatch = hasRange
          && (!collectionYearRange.from || year >= Number(collectionYearRange.from))
          && (!collectionYearRange.to || year <= Number(collectionYearRange.to));
        return Boolean(decadeMatch || rangeMatch);
      }

      export function matchesReleaseDay(item) {
        const days = collectionFilters.release_day;
        if (!days.size) return true;
        return (Array.isArray(item.release_dates) ? item.release_dates : []).some((release) => {
          if (release?.precision !== "day") return false;
          const value = String(release.date || "");
          return value.length >= 10 && matchingFilterValue(days, value.slice(5, 10));
        });
      }

      export function matchesPersonalRecord(item) {
        const records = collectionFilters.record;
        if (!records.size) return true;
        return (records.has("unrated") && normalizeRating(item.rating) === 0)
          || (records.has("unreviewed") && !String(item.review || "").trim());
      }

      export function emptyCatalogMetrics() {
        return {
          total: 0,
          catalogued: 0,
          watched: 0,
          toWatch: 0,
          rated: 0,
          withImage: 0,
          externalLinks: 0,
          withoutExternalLinks: 0,
          imdbLinks: 0,
          filmAffinityLinks: 0,
          duplicates: 0
        };
      }

      export function catalogSearchDocument(item) {
        return [
          item.title,
          item.original_title,
          item.spanish_title,
          item.english_title,
          asList(item.alternative_titles).join(" "),
          item.local_name,
          item.local_path,
          localFilesText(item),
          item.year,
          Array.isArray(item.release_dates) ? item.release_dates.map((entry) => entry?.date || "").join(" ") : "",
          item.description,
          item.wikipedia_extract,
          item.notes,
          item.review,
          item.watched_at,
          item.rating,
          asList(item.genres).join(" "),
          asList(item.directors).join(" "),
          asList(item.writers).join(" "),
          asList(item.cast).join(" "),
          Array.isArray(item.tags) ? item.tags.join(" ") : item.tags
        ].join(" ");
      }

      export function prepareCatalogViewModel() {
        const metrics = emptyCatalogMetrics();
        const searchIndex = new WeakMap();
        for (const item of items) {
          searchIndex.set(item, normalizeText(catalogSearchDocument(item)));
          metrics.total += 1;
          if (isInCatalog(item.en_catalogo)) metrics.catalogued += 1;
          if (item.status === "watched") metrics.watched += 1;
          if (item.status === "to_watch") metrics.toWatch += 1;
          if (normalizeRating(item.rating) > 0) metrics.rated += 1;
          if (item.page_image) metrics.withImage += 1;
          if (hasExternalLink(item)) metrics.externalLinks += 1;
          else metrics.withoutExternalLinks += 1;
          if (hasHost(item.url, "imdb.com") || hasHost(item.imdb_url, "imdb.com")) metrics.imdbLinks += 1;
          if (hasHost(item.url, "filmaffinity.com") || hasHost(item.filmaffinity_url, "filmaffinity.com")) {
            metrics.filmAffinityLinks += 1;
          }
          if (Number(item._duplicate_count || 0) > 0) metrics.duplicates += 1;
        }
        catalogSearchIndex = searchIndex;
        catalogMetrics = metrics;
        catalogRevision += 1;
        lastCatalogGridKey = "";
      }

      export function filteredItems() {
        const normalizedQuery = normalizeText(activeQuery.trim());
        return items.filter((item) => {
          const searchText = catalogSearchIndex.get(item) || normalizeText(catalogSearchDocument(item));
          return (!normalizedQuery || matchesNormalizedSearchText(searchText, normalizedQuery))
            && (!duplicatesOnly || Number(item._duplicate_count || 0) > 0)
            && filterSetMatchesValue(collectionFilters.status, item.status)
            && filterSetMatchesValue(
              collectionFilters.availability,
              isInCatalog(item.en_catalogo) ? "available" : "unavailable"
            )
            && filterSetMatchesValue(collectionFilters.kind, item.kind)
            && filterSetMatchesValue(collectionFilters.source, item.source)
            && filterSetMatchesList(collectionFilters.genre, item.genres)
            && filterSetMatchesList(collectionFilters.director, item.directors)
            && matchesYearFilters(item)
            && matchesReleaseDay(item)
            && matchesPersonalRecord(item);
        });
      }

      export function sortItems(list) {
        const mode = fields.sort.value || "original";
        if (mode === "original") return list;
        const sorted = [...list];
        if (mode === "title-asc") {
          return sorted.sort((left, right) => displayTitle(left).localeCompare(displayTitle(right), "es", { sensitivity: "base" }));
        }
        if (mode === "year-desc") {
          return sorted.sort((left, right) => numericYear(right.year) - numericYear(left.year));
        }
        if (mode === "year-asc") {
          return sorted.sort((left, right) => {
            const leftYear = numericYear(left.year) || Number.MAX_SAFE_INTEGER;
            const rightYear = numericYear(right.year) || Number.MAX_SAFE_INTEGER;
            return leftYear - rightYear;
          });
        }
        if (mode === "rating-desc") {
          return sorted.sort((left, right) => normalizeRating(right.rating) - normalizeRating(left.rating));
        }
        if (mode === "added-desc") {
          return sorted.sort((left, right) => String(right.added_at || "").localeCompare(String(left.added_at || "")));
        }
        return sorted;
      }

      export function numericYear(value) {
        const year = Number.parseInt(value || 0, 10);
        return Number.isNaN(year) ? 0 : year;
      }

      export function resetCollectionFilters() {
        collectionFilters = emptyCollectionFilters();
        collectionYearRange = { from: "", to: "" };
        fields.sort.value = "original";
        duplicatesOnly = false;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        syncCollectionFilterControls();
      }

      export function clearFilters() {
        resetCollectionFilters();
        render();
        syncCollectionRoute("push");
      }

      export function clearFilter(filter, value = "") {
        if (filter === "query") {
          clearManualSearch({ focus: false });
          return;
        }
        if (COLLECTION_MULTI_FILTER_KEYS.includes(filter)) {
          if (value) setCollectionFilterValue(filter, value, false);
          else collectionFilters[filter].clear();
        } else if (filter === "year") {
          collectionYearRange = { from: "", to: "" };
        } else if (filter === "sort") {
          fields.sort.value = "original";
        } else if (filter === "duplicates") {
          duplicatesOnly = false;
        } else if (filter === "random") {
          randomOrder = [];
        }
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        syncCollectionFilterControls();
        render();
        syncCollectionRoute("push");
      }

      export function renderActiveFilters() {
        const filters = [];
        if (activeQuery) filters.push(["query", "", `Búsqueda: ${activeQuery}`]);
        const labels = {
          status: "Estado",
          availability: "Disponibilidad",
          kind: "Tipo",
          source: "Fuente",
          decade: "Década",
          genre: "Género",
          director: "Dirección",
          record: "Memoria"
        };
        for (const key of COLLECTION_MULTI_FILTER_KEYS) {
          for (const value of collectionFilters[key]) {
            let label = `${labels[key] || key}: ${filterValueLabel(key, value)}`;
            if (key === "decade") label = `Años ${value}`;
            if (key === "release_day") label = releaseDayFilterLabel(value);
            filters.push([key, value, label]);
          }
        }
        if (collectionYearRange.from || collectionYearRange.to) {
          const range = collectionYearRange.from && collectionYearRange.to
            ? `${collectionYearRange.from}–${collectionYearRange.to}`
            : collectionYearRange.from ? `Desde ${collectionYearRange.from}` : `Hasta ${collectionYearRange.to}`;
          filters.push(["year", "", range]);
        }
        if (fields.sort.value && fields.sort.value !== "original") {
          filters.push(["sort", "", fields.sort.selectedOptions[0]?.textContent || "Orden personalizado"]);
        }
        if (duplicatesOnly) filters.push(["duplicates", "", "Sólo duplicadas"]);
        if (randomOrder.length) filters.push(["random", "", "Vista mezclada"]);
        fields.activeFilters.hidden = filters.length === 0;
        fields.activeFilters.innerHTML = filters.length
          ? `<span>Activos</span>${filters.map(([filter, value, label]) => (
              `<button type="button" data-click="clear-filter" data-filter="${escapeAttr(filter)}" data-value="${escapeAttr(value)}" aria-label="Quitar ${escapeAttr(label)}">${escapeHtml(label)} <span aria-hidden="true">×</span></button>`
            )).join("")}`
          : "";
      }

      export function releaseDayFilterLabel(value) {
        const [month, day] = String(value || "").split("-").map(Number);
        const parsed = new Date(2024, month - 1, day);
        if (!month || !day || Number.isNaN(parsed.getTime())) return "Fecha de estreno";
        const label = new Intl.DateTimeFormat("es-AR", { day: "numeric", month: "long" }).format(parsed);
        return `Estrenadas un ${label}`;
      }

      export function hasActiveCollectionFilters() {
        return COLLECTION_MULTI_FILTER_KEYS.some((key) => collectionFilters[key].size)
          || Boolean(collectionYearRange.from || collectionYearRange.to)
          || duplicatesOnly;
      }

      export function applyRandomOrder(list) {
        if (!randomOrder.length) return list;
        const byId = new Map(list.map((item) => [item.id, item]));
        const ordered = randomOrder.map((id) => byId.get(id)).filter(Boolean);
        const orderedIds = new Set(ordered.map((item) => item.id));
        return [...ordered, ...list.filter((item) => !orderedIds.has(item.id))];
      }

      export function render() {
        const baseFiltered = sortItems(filteredItems());
        const filtered = applyRandomOrder(baseFiltered);
        const shown = filtered.slice(0, catalogVisibleCount);

        renderHeaderStats();
        fields.total.textContent = catalogMetrics.total;
        fields.catalogCount.textContent = catalogMetrics.catalogued;
        fields.watchedCount.textContent = catalogMetrics.watched;
        fields.toWatchCount.textContent = catalogMetrics.toWatch;
        fields.ratedCount.textContent = catalogMetrics.rated;
        fields.withImage.textContent = catalogMetrics.withImage;
        fields.wikiLinks.textContent = catalogMetrics.externalLinks;
        fields.withoutWiki.textContent = catalogMetrics.withoutExternalLinks;
        fields.imdbLinks.textContent = catalogMetrics.imdbLinks;
        fields.faLinks.textContent = catalogMetrics.filmAffinityLinks;
        fields.duplicateCount.textContent = catalogMetrics.duplicates;
        fields.showDuplicates.textContent = duplicatesOnly ? "Ver todo" : "Ver duplicadas";
        fields.sourceFiles.textContent = sourceFiles.length;
        fields.catalogSummary.textContent = catalogSummaryText(filtered);
        fields.empty.style.display = filtered.length ? "none" : "block";
        fields.empty.textContent = activeQuery
          ? `No encontramos obras para “${activeQuery}” con los filtros actuales.`
          : "No hay obras que coincidan con los filtros actuales.";
        const gridKey = `${catalogRevision}:${currentView === "catalog" ? "catalog" : "background"}:${shown.map((item) => item.id).join("|")}`;
        if (gridKey !== lastCatalogGridKey) {
          fields.grid.innerHTML = shown
            .map((item, index) => card(item, index, currentView === "catalog"))
            .join("");
          lastCatalogGridKey = gridKey;
        }
        fields.catalogLoadMore.hidden = shown.length >= filtered.length;
        fields.catalogLoadMore.textContent = `Cargar más (${filtered.length - shown.length})`;
        if (lastEditorialRenderRevision !== editorialRevision) {
          renderEditorialHome();
          lastEditorialRenderRevision = editorialRevision;
        }
        renderActiveFilters();
        syncRandomControl();
        renderDetail();
      }

      export function renderHeaderStats() {
        fields.stats.textContent = `${catalogMetrics.total} obras · ${catalogMetrics.watched} vistas · ${catalogMetrics.catalogued} disponibles`;
      }

      export function catalogSummaryText(filtered) {
        const count = filtered.length;
        const noun = count === 1 ? "título" : "títulos";
        if (activeQuery) return `${count} ${noun} para “${activeQuery}”`;
        if (hasActiveCollectionFilters()) return `${count} ${noun} con los filtros actuales`;
        if (randomOrder.length) return `${count} ${noun} en orden aleatorio`;
        return `${count} ${noun} en la estantería`;
      }

      export function showMoreCatalogItems() {
        catalogVisibleCount += CATALOG_PAGE_SIZE;
        render();
      }

      export function randomizeView() {
        const visibleIds = filteredItems().map((item) => item.id);
        randomOrder = shuffle(visibleIds);
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }

      export function resetViewOrder() {
        randomOrder = [];
        fields.sort.value = "original";
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }

      export function toggleDuplicatesOnly() {
        duplicatesOnly = !duplicatesOnly;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
        syncCollectionRoute("push");
        goToCollection();
      }

      export async function toggleWatched(event, id, currentStatus) {
        event.preventDefault();
        const nextStatus = currentStatus === "watched" ? "to_watch" : "watched";
        const item = items.find((entry) => entry.id === id);
        const detailAction = selectedDetailId === id;
        if (detailAction) setDetailFeedback("Guardando estado…", "working", 0);
        try {
          const response = await apiFetch("/api/status", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              id,
              status: nextStatus,
              watched_at: nextStatus === "watched" ? todayLocalDate() : item?.watched_at || "",
              source_file: item?._source_file || ""
            })
          });
          const payload = await response.json();
          if (!payload.ok) throw new Error(payload.reason || "No se pudo cambiar el estado");
          if (detailAction) setDetailFeedback(nextStatus === "watched" ? "Marcada como vista" : "Marcada como pendiente", "success");
          await load();
        } catch (error) {
          console.error("[catalog-viewer] status update failed", error);
          if (detailAction) setDetailFeedback("No pudimos guardar el estado. Reintentá.", "error", 0);
          else setSearchState("error", "No pudimos guardar el estado. Reintentá.");
        }
      }

      export async function toggleCatalog(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        const manualValue = availabilityState(item).manual;
        const nextValue = !manualValue;
        const detailAction = selectedDetailId === id;
        if (detailAction) setDetailFeedback("Guardando disponibilidad…", "working", 0);
        try {
          const response = await apiFetch("/api/catalog", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, en_catalogo: nextValue, source_file: item?._source_file || "" })
          });
          const payload = await response.json();
          if (!payload.ok) throw new Error(payload.reason || "No se pudo cambiar el estado de catalogo");
          if (detailAction) {
            const message = nextValue
              ? "Disponibilidad personal declarada"
              : item._availability?.server
                ? "Declaración retirada; sigue disponible en el servidor"
                : "Disponibilidad personal retirada";
            setDetailFeedback(message, "success");
          }
          await load();
        } catch (error) {
          console.error("[catalog-viewer] catalog update failed", error);
          if (detailAction) setDetailFeedback("No pudimos guardar la disponibilidad. Reintentá.", "error", 0);
          else setSearchState("error", "No pudimos guardar la disponibilidad. Reintentá.");
        }
      }
