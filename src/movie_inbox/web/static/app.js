const API_TOKEN = document.querySelector('[name="movie-inbox-token"]').content;
      let items = [];
      let sourceFiles = [];
      let manualResults = [];
      let selectedManualIndex = null;
      let selectedExistingIdForSearch = null;
      let manualSearchSource = "all";
      let catalogMergeResults = [];
      let wikiReviewQueue = [];
      let wikiReviewIndex = 0;
      let randomOrder = [];
      let openPersonalId = "";
      let selectedDetailId = "";
      let activeQuery = "";
      let writeJsonPath = "";
      let databasePanel = "catalog";
      let manualVisibleCount = 6;
      let catalogMergeVisibleCount = 6;
      let externalSourcesLastUsed = [];
      let externalSourcesAttempted = [];
      let externalSearchController = null;
      let duplicatesOnly = false;
      let catalogVisibleCount = 36;
      let externalHealth = { sources: {}, cache: {} };
      const SEARCH_PAGE_SIZE = 6;
      const CATALOG_PAGE_SIZE = 36;

      function apiFetch(url, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set("X-Movie-Inbox-Token", API_TOKEN);
        return fetch(url, { ...options, headers, credentials: "same-origin" });
      }
      const fields = {
        query: document.querySelector("#query"),
        catalogSource: document.querySelector("#catalogSource"),
        externalSource: document.querySelector("#externalSource"),
        searchButton: document.querySelector("#searchButton"),
        status: document.querySelector("#status"),
        kind: document.querySelector("#kind"),
        source: document.querySelector("#source"),
        grid: document.querySelector("#grid"),
        stats: document.querySelector("#stats"),
        total: document.querySelector("#total"),
        visible: document.querySelector("#visible"),
        watchedCount: document.querySelector("#watchedCount"),
        toWatchCount: document.querySelector("#toWatchCount"),
        ratedCount: document.querySelector("#ratedCount"),
        withImage: document.querySelector("#withImage"),
        wikiLinks: document.querySelector("#wikiLinks"),
        withoutWiki: document.querySelector("#withoutWiki"),
        imdbLinks: document.querySelector("#imdbLinks"),
        faLinks: document.querySelector("#faLinks"),
        duplicateCount: document.querySelector("#duplicateCount"),
        sourceFiles: document.querySelector("#sourceFiles"),
        startWikiReview: document.querySelector("#startWikiReview"),
        previousWikiReview: document.querySelector("#previousWikiReview"),
        nextWikiReview: document.querySelector("#nextWikiReview"),
        wikiReviewStatus: document.querySelector("#wikiReviewStatus"),
        randomizeView: document.querySelector("#randomizeView"),
        resetOrder: document.querySelector("#resetOrder"),
        showDuplicates: document.querySelector("#showDuplicates"),
        clearManualSearch: document.querySelector("#clearManualSearch"),
        manualSearchStatus: document.querySelector("#manualSearchStatus"),
        manualSearchResults: document.querySelector("#manualSearchResults"),
        externalSearchSection: document.querySelector("#externalSearchSection"),
        catalogMergeSection: document.querySelector("#catalogMergeSection"),
        catalogMergeStatus: document.querySelector("#catalogMergeStatus"),
        catalogMergeResults: document.querySelector("#catalogMergeResults"),
        databaseMenuCatalog: document.querySelector("#databaseMenuCatalog"),
        databaseMenuExternal: document.querySelector("#databaseMenuExternal"),
        databaseCatalogPanel: document.querySelector("#databaseCatalogPanel"),
        databaseExternalPanel: document.querySelector("#databaseExternalPanel"),
        detailBackdrop: document.querySelector("#detailBackdrop"),
        detailDrawer: document.querySelector("#detailDrawer"),
        detailBody: document.querySelector("#detailBody"),
        closeDetail: document.querySelector("#closeDetail"),
        catalogLoadMore: document.querySelector("#catalogLoadMore"),
        descriptionDialog: document.querySelector("#descriptionDialog"),
        descriptionDialogTitle: document.querySelector("#descriptionDialogTitle"),
        descriptionDialogText: document.querySelector("#descriptionDialogText"),
        closeDescriptionDialog: document.querySelector("#closeDescriptionDialog"),
        empty: document.querySelector("#empty")
      };

      document.querySelector("#refresh").addEventListener("click", load);
      fields.searchButton.addEventListener("click", runSearch);
      fields.externalSource.addEventListener("change", renderDatabaseMenu);
      fields.clearManualSearch.addEventListener("click", clearManualSearch);
      fields.startWikiReview.addEventListener("click", startWikiReview);
      fields.previousWikiReview.addEventListener("click", previousWikiReview);
      fields.nextWikiReview.addEventListener("click", nextWikiReview);
      fields.randomizeView.addEventListener("click", randomizeView);
      fields.resetOrder.addEventListener("click", resetViewOrder);
      fields.showDuplicates.addEventListener("click", toggleDuplicatesOnly);
      fields.databaseMenuCatalog.addEventListener("click", () => setDatabasePanel("catalog"));
      fields.databaseMenuExternal.addEventListener("click", () => setDatabasePanel("external"));
      fields.closeDetail.addEventListener("click", closeDetail);
      fields.detailBackdrop.addEventListener("click", closeDetail);
      fields.catalogLoadMore.addEventListener("click", showMoreCatalogItems);
      fields.closeDescriptionDialog.addEventListener("click", () => fields.descriptionDialog.close());
      fields.query.addEventListener("keydown", (event) => {
        if (event.key === "Enter") runSearch();
        if (event.key === "Escape") clearManualSearch();
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && selectedDetailId) closeDetail();
      });
      document.addEventListener("click", handleDelegatedClick);
      document.addEventListener("change", handleDelegatedChange);
      document.addEventListener("toggle", handleDelegatedToggle, true);
      [fields.status, fields.kind, fields.source].forEach((field) => field.addEventListener("input", () => {
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }));
      load();

      function handleDelegatedClick(event) {
        const target = event.target.closest("[data-click]");
        if (!target) return;
        event.preventDefault();
        event.stopPropagation();
        const id = target.dataset.id || "";
        const index = Number(target.dataset.index);
        const actions = {
          "open-detail": () => openDetail(id),
          "toggle-watched": () => toggleWatched(event, id, target.dataset.status || "to_watch"),
          "find-link": () => findLinkForCatalog(event, id),
          "save-personal": () => savePersonal(event, id),
          "toggle-catalog": () => toggleCatalog(event, id),
          "delete-item": () => deleteCatalogItem(event, id),
          "save-metadata": () => saveMetadata(event, id),
          "show-more-manual": showMoreManualResults,
          "show-more-catalog": showMoreCatalogResults,
          "merge-result": () => mergeSearchResult(index, id),
          "add-result": () => addSearchResult(index),
          "prepare-merge": () => prepareManualMerge(index),
          "show-description": () => openSearchDescription(target.dataset.collection || "", target.dataset.key || ""),
          "force-add": () => forceAddSearchResult(index),
          "run-search": runSearch
        };
        actions[target.dataset.click]?.();
      }

      function handleDelegatedChange(event) {
        const target = event.target.closest("[data-change]");
        if (target?.dataset.change === "update-kind") updateKind(event, target.dataset.id || "");
      }

      function handleDelegatedToggle(event) {
        const target = event.target;
        if (target?.dataset?.toggle === "track-personal") trackPersonalPanel(event, target.dataset.id || "");
      }

      async function load() {
        try {
          await loadCatalog();
        } catch (error) {
          console.error("[catalog-viewer] catalog load failed", error);
          fields.empty.textContent = `No se pudo cargar el catalogo: ${error.message || error}`;
          fields.empty.hidden = false;
        }
      }

      async function loadCatalog() {
        const response = await apiFetch("/api/items");
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        items = payload.items || [];
        sourceFiles = payload.sources || [];
        writeJsonPath = payload.write_json || "";
        externalHealth = payload.external || externalHealth;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        setupSelect(fields.status, "Estado", items.map((item) => item.status));
        setupSelect(fields.kind, "Tipo", items.map((item) => item.kind));
        setupSelect(fields.source, "Fuente", items.map((item) => item.source));
        render();
        renderDatabaseMenu();
      }

      function setupSelect(select, label, values) {
        const selected = select.value;
        const unique = [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
        select.innerHTML = `<option value="">${label}</option>` + unique.map((value) => `<option value="${escapeAttr(value)}">${escapeHtml(value)}</option>`).join("");
        select.value = unique.includes(selected) ? selected : "";
      }

      function setDatabasePanel(panel) {
        databasePanel = panel;
        fields.databaseMenuCatalog.classList.toggle("active", panel === "catalog");
        fields.databaseMenuExternal.classList.toggle("active", panel === "external");
        fields.databaseCatalogPanel.hidden = panel !== "catalog";
        fields.databaseExternalPanel.hidden = panel !== "external";
        renderDatabaseMenu();
      }

      function renderDatabaseMenu() {
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
            ${externalCacheItem()}
          </div>
        `;
        fields.databaseMenuCatalog.classList.toggle("active", databasePanel === "catalog");
        fields.databaseMenuExternal.classList.toggle("active", databasePanel === "external");
        fields.databaseCatalogPanel.hidden = databasePanel !== "catalog";
        fields.databaseExternalPanel.hidden = databasePanel !== "external";
      }

      function externalDatabaseItem(label, source) {
        const health = externalHealth?.sources?.[source] || {};
        const consumed = externalSourcesLastUsed.includes(source);
        const attempted = externalSourcesAttempted.includes(source);
        const stateLabels = { ready: "lista", ok: "disponible", empty: "sin resultados", error: "error" };
        const state = stateLabels[health.status] || (fields.externalSource.checked ? "lista" : "apagada");
        const request = attempted ? (consumed ? `${health.result_count || 0} resultados` : "sin resultados") : "sin consultar";
        const latency = health.latency_ms ? `${health.latency_ms} ms` : "";
        const error = health.error ? ` | ${health.error}` : "";
        const status = [state, request, latency].filter(Boolean).join(" | ") + error;
        return `<div class="db-item"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(status)}</span></div>`;
      }

      function externalCacheItem() {
        const cache = externalHealth?.cache || {};
        const entries = Number(cache.search_entries || 0) + Number(cache.metadata_entries || 0);
        return `<div class="db-item"><strong>Cache</strong><span>${entries} entradas | ${Number(cache.hits || 0)} hits | ${Number(cache.misses || 0)} misses</span></div>`;
      }

      async function runSearch() {
        const requestedQuery = fields.query.value.trim();
        activeQuery = requestedQuery.length >= 2 ? requestedQuery : "";
        selectedManualIndex = null;
        selectedExistingIdForSearch = null;
        manualResults = [];
        catalogMergeResults = [];
        manualVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        render();
        renderDatabaseMenu();
        if (requestedQuery.length < 2) {
          if (requestedQuery) {
            fields.catalogMergeSection.classList.add("active");
            fields.catalogMergeStatus.textContent = "Escribi al menos 2 caracteres.";
          }
          return;
        }
        searchCatalogForMerge(activeQuery);
        if (fields.externalSource.checked) {
          await searchManual("all");
        }
      }

      function filteredItems() {
        const query = activeQuery.trim();
        return items.filter((item) => {
          const haystack = [
            item.title,
            item.original_title,
            item.spanish_title,
            item.english_title,
            asList(item.alternative_titles).join(" "),
            item.local_name,
            item.local_path,
            localFilesText(item),
            item.year,
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
          return (!query || matchesSearchText(haystack, query))
            && (!duplicatesOnly || Number(item._duplicate_count || 0) > 0)
            && (!fields.status.value || item.status === fields.status.value)
            && (!fields.kind.value || item.kind === fields.kind.value)
            && (!fields.source.value || item.source === fields.source.value);
        });
      }

      function applyRandomOrder(list) {
        if (!randomOrder.length) return list;
        const byId = new Map(list.map((item) => [item.id, item]));
        const ordered = randomOrder.map((id) => byId.get(id)).filter(Boolean);
        const orderedIds = new Set(ordered.map((item) => item.id));
        return [...ordered, ...list.filter((item) => !orderedIds.has(item.id))];
      }

      function render() {
        const baseFiltered = filteredItems();
        const filtered = applyRandomOrder(baseFiltered);
        const shown = filtered.slice(0, catalogVisibleCount);

        fields.stats.textContent = `${shown.length} mostradas de ${filtered.length} visibles (${items.length} items)${randomOrder.length ? " | orden aleatorio" : ""}${duplicatesOnly ? " | solo duplicadas" : ""}`;
        fields.total.textContent = items.length;
        fields.visible.textContent = filtered.length;
        fields.watchedCount.textContent = items.filter((item) => item.status === "watched").length;
        fields.toWatchCount.textContent = items.filter((item) => item.status === "to_watch").length;
        fields.ratedCount.textContent = items.filter((item) => normalizeRating(item.rating) > 0).length;
        fields.withImage.textContent = items.filter((item) => item.page_image).length;
        fields.wikiLinks.textContent = items.filter(hasExternalLink).length;
        fields.withoutWiki.textContent = items.filter((item) => !hasExternalLink(item)).length;
        fields.imdbLinks.textContent = items.filter((item) => hasHost(item.url, "imdb.com") || hasHost(item.imdb_url, "imdb.com")).length;
        fields.faLinks.textContent = items.filter((item) => hasHost(item.url, "filmaffinity.com") || hasHost(item.filmaffinity_url, "filmaffinity.com")).length;
        fields.duplicateCount.textContent = items.filter((item) => Number(item._duplicate_count || 0) > 0).length;
        fields.showDuplicates.textContent = duplicatesOnly ? "Ver todo" : "Ver duplicadas";
        fields.sourceFiles.textContent = sourceFiles.length;
        fields.empty.style.display = filtered.length ? "none" : "block";
        fields.grid.innerHTML = shown.map(card).join("");
        fields.catalogLoadMore.hidden = shown.length >= filtered.length;
        fields.catalogLoadMore.textContent = `Cargar mas (${filtered.length - shown.length})`;
        renderDetail();
      }

      function showMoreCatalogItems() {
        catalogVisibleCount += CATALOG_PAGE_SIZE;
        render();
      }

      function randomizeView() {
        const visibleIds = filteredItems().map((item) => item.id);
        randomOrder = shuffle(visibleIds);
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }

      function resetViewOrder() {
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }

      function toggleDuplicatesOnly() {
        duplicatesOnly = !duplicatesOnly;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }

      function shuffle(values) {
        const shuffled = [...values];
        for (let index = shuffled.length - 1; index > 0; index -= 1) {
          const swapIndex = Math.floor(Math.random() * (index + 1));
          [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
        }
        return shuffled;
      }

      function card(item) {
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || "";
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        const image = item.page_image
          ? `<img class="image" src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="" loading="lazy" decoding="async">`
          : `<div class="image-placeholder">${escapeHtml((shownTitle || "Sin imagen").slice(0, 18))}</div>`;
        const tags = Array.isArray(item.tags) ? item.tags : [];
        const rating = normalizeRating(item.rating);
        const personal = rating ? `${rating}/10` : item.status === "watched" ? "vista" : "sin puntaje";
        return `<article class="card" data-click="open-detail" data-id="${escapeAttr(item.id)}">
          ${image}
          <div class="body">
            <div class="title">
              <h2>${escapeHtml(shownTitle || "Sin titulo")}</h2>
            </div>
            ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
            <div class="card-badges">
              <span class="pill ${item.status === "watched" ? "good" : ""}">${escapeHtml(item.status || "sin estado")}</span>
              <span class="pill ${hasExternalLink(item) ? "good" : "muted"}">${hasExternalLink(item) ? "con link" : "sin link"}</span>
              <span class="pill ${isInCatalog(item.en_catalogo) ? "good" : "muted"}">${isInCatalog(item.en_catalogo) ? "catalogo: si" : "catalogo: no"}</span>
              ${Number(item._duplicate_count || 0) > 0 ? `<span class="pill warning">duplicada +${item._duplicate_count}</span>` : ""}
            </div>
            <div class="meta">
              ${meta(item.year)}${meta(item.kind)}${meta(item.source)}${meta(rating ? `puntaje: ${rating}/10` : "")}${meta(item.watched_at ? `vista: ${item.watched_at}` : "")}${meta(tags.join(", "))}
              ${meta(localFileCountLabel(item))}
            </div>
            ${summary ? `<p class="summary">${escapeHtml(summary)}</p>` : ""}
            <div class="card-facts">
              ${cardFact("Año", item.year)}
              ${cardFact("Director", firstListValue(item.directors))}
              ${cardFact("Genero", listText(item.genres, 2))}
              ${cardFact("Personal", personal)}
            </div>
            <div class="links">
              <a href="#" data-click="open-detail" data-id="${escapeAttr(item.id)}">Detalle</a>
              <a href="#" data-click="toggle-watched" data-id="${escapeAttr(item.id)}" data-status="${escapeAttr(item.status || "to_watch")}">${item.status === "watched" ? "Marcar pendiente" : "Marcar vista"}</a>
              <a href="#" data-click="find-link" data-id="${escapeAttr(item.id)}">Buscar link</a>
            </div>
          </div>
        </article>`;
      }

      function cardFact(label, value) {
        return `<div class="card-fact"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value || "-")}</span></div>`;
      }

      function personalPanel(item, forceOpen = false) {
        const rating = normalizeRating(item.rating);
        const ratingOptions = Array.from({ length: 11 }, (_, value) => (
          `<option value="${value}" ${value === rating ? "selected" : ""}>${value}</option>`
        )).join("");
        const open = forceOpen || openPersonalId === item.id ? " open" : "";
        const watched = item.watched_at ? `Vista: ${item.watched_at}` : "Sin fecha de vista";
        const summary = [rating ? `${rating}/10` : "Sin puntaje", watched].join(" | ");
        return `<details class="personal-panel"${open} data-toggle="track-personal" data-id="${escapeAttr(item.id)}">
          <summary>${escapeHtml(summary)}</summary>
          <div class="personal-grid">
            <label>
              Fecha vista
              <input data-personal-watched-at type="date" value="${escapeAttr(item.watched_at || "")}">
            </label>
            <label>
              Puntaje
              <select data-personal-rating>
                ${ratingOptions}
              </select>
            </label>
            <label class="review-field">
              Review
              <textarea data-personal-review rows="4">${escapeHtml(item.review || "")}</textarea>
            </label>
            <div class="personal-actions">
              <button type="button" data-click="save-personal" data-id="${escapeAttr(item.id)}">Guardar</button>
              <span class="status-line" data-personal-status></span>
            </div>
          </div>
        </details>`;
      }

      function factsPanel(item) {
        const rows = [
          ["Genero", item.genres, 4],
          ["Original", item.original_title, 1],
          ["Español", item.spanish_title, 1],
          ["Inglés", item.english_title, 1],
          ["Alternativos", item.alternative_titles, 6],
          ["Director", item.directors, 4],
          ["Guion", item.writers, 4],
          ["Reparto", item.cast, 8]
        ].map(([label, values, limit]) => {
          const text = listText(values, limit);
          return text ? `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(text)}</dd>` : "";
        }).filter(Boolean);
        const localText = localFilesText(item);
        if (localText) rows.push(`<dt>Archivos</dt><dd>${escapeHtml(localText)}</dd>`);
        if (Number(item._duplicate_count || 0) > 0) {
          const duplicateText = `${item._duplicate_count} coincidencia(s): ${item._duplicate_reason || "misma obra"}`;
          rows.push(`<dt>Duplicados</dt><dd>${escapeHtml(duplicateText)}</dd>`);
        }
        const content = rows.join("");
        return content ? `<dl class="facts">${content}</dl>` : "";
      }

      function openDetail(id) {
        selectedDetailId = id;
        renderDetail();
        fields.detailBackdrop.classList.add("open");
        fields.detailDrawer.classList.add("open");
        fields.detailDrawer.setAttribute("aria-hidden", "false");
      }

      function closeDetail() {
        selectedDetailId = "";
        fields.detailBackdrop.classList.remove("open");
        fields.detailDrawer.classList.remove("open");
        fields.detailDrawer.setAttribute("aria-hidden", "true");
        fields.detailBody.innerHTML = "";
      }

      function renderDetail() {
        if (!selectedDetailId) return;
        const item = items.find((entry) => entry.id === selectedDetailId);
        if (!item) {
          closeDetail();
          return;
        }
        const rating = normalizeRating(item.rating);
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        const image = item.page_image
          ? `<img class="drawer-poster" src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="" decoding="async">`
          : `<div class="drawer-poster"></div>`;
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || "";
        fields.detailBody.innerHTML = `
          <section class="drawer-hero">
            ${image}
            <div>
              <h2>${escapeHtml(shownTitle || "Sin titulo")}</h2>
              <div class="meta">
                ${meta(item.year)}${meta(item.source)}${meta(item.status)}${meta(rating ? `puntaje: ${rating}/10` : "")}${meta(item.watched_at ? `vista: ${item.watched_at}` : "")}${meta(isInCatalog(item.en_catalogo) ? "catalogo: si" : "catalogo: no")}${meta(Number(item._duplicate_count || 0) > 0 ? `duplicada +${item._duplicate_count}` : "")}
              </div>
              ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
              <div class="drawer-control">
                <span>Tipo</span>
                ${kindSelect(item)}
              </div>
              ${summary ? `<p class="summary">${escapeHtml(summary)}</p>` : ""}
            </div>
          </section>
          <section class="drawer-section">
            <h3>Ficha</h3>
            ${factsPanel(item) || `<span class="status-line">Sin ficha enriquecida.</span>`}
          </section>
          <section class="drawer-section">
            <h3>Metadata</h3>
            ${metadataEditor(item)}
          </section>
          <section class="drawer-section">
            <h3>Mi registro</h3>
            ${personalPanel(item, true)}
          </section>
          <section class="drawer-section">
            <h3>Links</h3>
            <div class="links">${detailLinks(item)}</div>
          </section>
          <section class="drawer-section">
            <h3>Acciones</h3>
            <div class="links">
              <a href="#" data-click="toggle-watched" data-id="${escapeAttr(item.id)}" data-status="${escapeAttr(item.status || "to_watch")}">${item.status === "watched" ? "Marcar pendiente" : "Marcar vista"}</a>
              <a href="#" data-click="toggle-catalog" data-id="${escapeAttr(item.id)}">${isInCatalog(item.en_catalogo) ? "Quitar catalogo" : "Marcar catalogo"}</a>
              <a href="#" data-click="find-link" data-id="${escapeAttr(item.id)}">Buscar link</a>
              <a href="#" data-click="delete-item" data-id="${escapeAttr(item.id)}">Eliminar</a>
            </div>
          </section>
        `;
      }

      function detailLinks(item) {
        const links = [
          item.url ? `<a href="${escapeAttr(item.url)}" target="_blank" rel="noreferrer">Abrir link</a>` : "",
          item.wikipedia_url ? `<a href="${escapeAttr(item.wikipedia_url)}" target="_blank" rel="noreferrer">Wikipedia</a>` : "",
          item.imdb_url ? `<a href="${escapeAttr(item.imdb_url)}" target="_blank" rel="noreferrer">IMDb</a>` : "",
          item.filmaffinity_url ? `<a href="${escapeAttr(item.filmaffinity_url)}" target="_blank" rel="noreferrer">FilmAffinity</a>` : "",
          item.wikidata_id ? `<a href="https://www.wikidata.org/wiki/${escapeAttr(item.wikidata_id)}" target="_blank" rel="noreferrer">Wikidata</a>` : ""
        ].filter(Boolean).join("");
        return links || `<span class="status-line">Sin links asociados.</span>`;
      }

      function metadataEditor(item) {
        const rows = [
          ["Titulo", "title", "text"],
          ["Original", "original_title", "text"],
          ["Español", "spanish_title", "text"],
          ["Inglés", "english_title", "text"],
          ["Alternativos", "alternative_titles", "text"],
          ["Tipo", "kind", "kind"],
          ["Año", "year", "text"],
          ["Descripcion", "description", "textarea"],
          ["Generos", "genres", "text"],
          ["Directores", "directors", "text"],
          ["Guionistas", "writers", "text"],
          ["Reparto", "cast", "text"]
        ];
        return `<div class="metadata-editor">
          ${rows.map(([label, field, control]) => metadataEditorRow(item, label, field, control)).join("")}
          <div class="metadata-actions">
            <button type="button" data-click="save-metadata" data-id="${escapeAttr(item.id)}">Guardar metadata</button>
            <span class="status-line" data-metadata-status></span>
          </div>
        </div>`;
      }

      function metadataEditorRow(item, label, field, control) {
        const listFields = ["alternative_titles", "genres", "directors", "writers", "cast"];
        const value = listFields.includes(field) ? asList(item[field]).join(", ") : String(item[field] || "");
        const locked = asList(item.locked_fields).includes(field);
        const origin = item.metadata_sources?.[field] || {};
        const source = origin.source
          ? `${origin.source}${origin.inferred ? " (inferida)" : ""}${origin.updated_at ? ` | ${String(origin.updated_at).slice(0, 10)}` : ""}`
          : "sin procedencia";
        const input = control === "textarea"
          ? `<textarea data-metadata-field="${field}" rows="4">${escapeHtml(value)}</textarea>`
          : control === "kind"
            ? `<select data-metadata-field="${field}">${["pelicula", "serie", "anime", "documental"].map((option) => `<option value="${option}" ${option === value ? "selected" : ""}>${option}</option>`).join("")}</select>`
            : `<input data-metadata-field="${field}" type="text" value="${escapeAttr(value)}">`;
        return `<div class="metadata-row">
          <label>${escapeHtml(label)}${input}</label>
          <div class="metadata-control">
            <span class="metadata-origin">${escapeHtml(source)}</span>
            <label class="lock-control"><input data-lock-field="${field}" type="checkbox" ${locked ? "checked" : ""}> Bloquear</label>
          </div>
        </div>`;
      }

      function kindSelect(item) {
        const value = normalizeKind(item.kind);
        const options = ["pelicula", "serie", "anime", "documental"];
        return `<select class="kind-select" data-change="update-kind" data-id="${escapeAttr(item.id)}">
          ${options.map((option) => `<option value="${option}" ${option === value ? "selected" : ""}>${option}</option>`).join("")}
        </select>`;
      }

      function cachedImageSrc(url) {
        return `/image-cache?url=${encodeURIComponent(url)}&token=${encodeURIComponent(API_TOKEN)}`;
      }

      async function searchManual(source = "all", statusPrefix = "") {
        const query = fields.query.value.trim();
        if (query.length < 2) return;
        if (externalSearchController) externalSearchController.abort();
        const controller = new AbortController();
        externalSearchController = controller;
        manualSearchSource = source;
        manualResults = [];
        selectedManualIndex = null;
        manualVisibleCount = SEARCH_PAGE_SIZE;
        fields.externalSearchSection.classList.add("active");
        fields.manualSearchStatus.textContent = statusPrefix || "Buscando...";
        fields.manualSearchResults.innerHTML = "";
        fields.searchButton.disabled = true;
        fields.searchButton.textContent = "Buscando...";
        try {
          const response = await apiFetch(`/api/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(source)}`, {
            signal: controller.signal
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          manualResults = payload.results || [];
          externalHealth = payload.external || externalHealth;
          externalSourcesAttempted = source === "all" ? ["wikipedia", "imdb", "filmaffinity"] : [source];
          externalSourcesLastUsed = [...new Set(manualResults.map((result) => result.source || "").filter(Boolean))];
          console.log("[catalog-viewer] search results", {
            source,
            query,
            count: manualResults.length,
            sources: [...new Set(manualResults.map((result) => result.source || ""))]
          });
          fields.manualSearchStatus.textContent = manualResults.length
            ? `${manualResults.length} resultados${source === "wikipedia" ? " de Wikipedia" : ""}`
            : "Sin resultados";
          renderManualResults();
          renderDatabaseMenu();
          renderDatabaseMenu();
        } catch (error) {
          if (error.name !== "AbortError") {
            fields.manualSearchStatus.textContent = "No se pudo completar la búsqueda externa.";
            console.error("[catalog-viewer] external search failed", error);
          }
        } finally {
          if (externalSearchController === controller) {
            externalSearchController = null;
            fields.searchButton.disabled = false;
            fields.searchButton.textContent = "Buscar";
          }
        }
      }

      function clearManualSearch() {
        if (externalSearchController) externalSearchController.abort();
        externalSearchController = null;
        fields.searchButton.disabled = false;
        fields.searchButton.textContent = "Buscar";
        manualResults = [];
        catalogMergeResults = [];
        selectedManualIndex = null;
        selectedExistingIdForSearch = null;
        manualSearchSource = "all";
        activeQuery = "";
        manualVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        fields.externalSource.checked = false;
        fields.query.value = "";
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        render();
        renderDatabaseMenu();
        fields.query.focus();
      }

      function prepareManualMerge(index) {
        selectedManualIndex = index;
        if (selectedExistingIdForSearch) {
          const item = items.find((entry) => entry.id === selectedExistingIdForSearch);
          catalogMergeResults = item ? [item] : [];
          catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeStatus.textContent = item ? "Entrada seleccionada para comparar." : "No se encontró la entrada seleccionada.";
          renderCatalogMergeResults();
          return;
        }
        const result = manualResults[index] || {};
        fields.query.value = [result.title, result.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        render();
        searchCatalogForMerge();
      }

      function searchCatalogForMerge(queryValue = "") {
        const query = (queryValue || fields.query.value).trim().toLowerCase();
        if (!query) return;
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeResults = items
          .map((item) => ({ item, score: catalogMatchScore(item, query) }))
          .filter((entry) => entry.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, 60)
          .map((entry) => entry.item);
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeStatus.textContent = selectedManualIndex === null
          ? `${catalogMergeResults.length} coincidencias locales.`
          : `${catalogMergeResults.length} entradas encontradas para comparar.`;
        renderCatalogMergeResults();
      }

      function renderManualResults() {
        const visible = manualResults.slice(0, manualVisibleCount);
        const more = manualResults.length > manualVisibleCount
          ? `<button class="load-more" type="button" data-click="show-more-manual">Cargar mas (${manualResults.length - manualVisibleCount})</button>`
          : "";
        fields.manualSearchResults.innerHTML = visible.map(searchResult).join("") + more;
      }

      function renderCatalogMergeResults() {
        const visible = catalogMergeResults.slice(0, catalogMergeVisibleCount);
        const more = catalogMergeResults.length > catalogMergeVisibleCount
          ? `<button class="load-more" type="button" data-click="show-more-catalog">Cargar mas (${catalogMergeResults.length - catalogMergeVisibleCount})</button>`
          : "";
        fields.catalogMergeResults.innerHTML = visible.map(catalogMergeResult).join("") + more;
      }

      function showMoreManualResults() {
        manualVisibleCount += SEARCH_PAGE_SIZE;
        renderManualResults();
      }

      function showMoreCatalogResults() {
        catalogMergeVisibleCount += SEARCH_PAGE_SIZE;
        renderCatalogMergeResults();
      }

      async function startWikiReview() {
        wikiReviewQueue = items.filter((item) => !hasExternalLink(item));
        wikiReviewIndex = 0;
        if (!wikiReviewQueue.length) {
          fields.wikiReviewStatus.textContent = "No quedan entradas sin link.";
          return;
        }
        await reviewCurrentWikiItem();
      }

      async function previousWikiReview() {
        if (!wikiReviewQueue.length) await startWikiReview();
        if (!wikiReviewQueue.length) return;
        wikiReviewIndex = Math.max(0, wikiReviewIndex - 1);
        await reviewCurrentWikiItem();
      }

      async function nextWikiReview() {
        if (!wikiReviewQueue.length) await startWikiReview();
        if (!wikiReviewQueue.length) return;
        wikiReviewIndex = Math.min(wikiReviewQueue.length - 1, wikiReviewIndex + 1);
        await reviewCurrentWikiItem();
      }

      async function reviewCurrentWikiItem() {
        const item = wikiReviewQueue[wikiReviewIndex];
        if (!item) return;
        fields.wikiReviewStatus.textContent = `${wikiReviewIndex + 1}/${wikiReviewQueue.length}: ${item.title || item.local_name || "Sin titulo"}`;
        await findLinkForItem(item);
      }

      function catalogMergeResult(item) {
        const incoming = selectedManualIndex === null ? null : manualResults[selectedManualIndex];
        const comparison = incoming ? diffComparison(incoming, item) : "";
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || item.local_name || "";
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        return `<article class="search-result ${comparison ? "comparison-result" : "compact-result"}">
          ${resultMedia(shownTitle || item.local_name, item.page_image)}
          <div class="result-body">
            <h3>${escapeHtml(shownTitle || "Sin titulo")}</h3>
            ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
            <div class="meta">
              ${meta(item.year)}${meta(item.kind)}${meta(item.source)}${meta(firstListValue(item.genres))}${meta(firstListValue(item.directors))}
            </div>
            <div class="card-badges">
              <span class="pill ${hasExternalLink(item) ? "good" : "muted"}">${hasExternalLink(item) ? "con link" : "sin link"}</span>
              <span class="pill ${isInCatalog(item.en_catalogo) ? "good" : "muted"}">${isInCatalog(item.en_catalogo) ? "catalogo: si" : "catalogo: no"}</span>
            </div>
            ${searchDescription(summary, "catalog", item.id)}
            ${comparison}
            <div class="result-actions">
              <button class="action-primary ${incoming ? "" : "span-all"}" type="button" data-click="open-detail" data-id="${escapeAttr(item.id)}">Detalle</button>
              ${incoming ? `<button class="action-secondary" type="button" data-click="merge-result" data-index="${selectedManualIndex}" data-id="${escapeAttr(item.id)}">Combinar</button>` : ""}
              ${item.url ? `<a class="action-secondary span-all" href="${escapeAttr(item.url)}" target="_blank" rel="noreferrer">Abrir link</a>` : ""}
            </div>
          </div>
        </article>`;
      }

      function searchResult(result, index) {
        const description = result.description || result.wikipedia_extract || "";
        const similarity = selectedExistingIdForSearch ? candidateSimilarity(result) : "";
        const primaryAction = selectedExistingIdForSearch ? "Combinar" : "Agregar";
        const shownTitle = displayTitle(result);
        const subtitle = titleSubtitle(result);
        return `<article class="search-result compact-result">
          ${resultMedia(shownTitle, result.page_image)}
          <div class="result-body">
            <h3>${escapeHtml(shownTitle || "Sin titulo")}</h3>
            ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
            <div class="meta">
              ${meta(result.source)}${meta(result.year)}${meta(firstListValue(result.genres))}${meta(firstListValue(result.directors))}${meta(result.url ? new URL(result.url).hostname.replace(/^www\\./, "") : "")}${meta(similarity)}
            </div>
            <div class="card-badges">
              <span class="pill good">${escapeHtml(result.source || "externo")}</span>
              <span class="pill ${result.url ? "good" : "muted"}">${result.url ? "con link" : "sin link"}</span>
            </div>
            ${searchDescription(description, "manual", index)}
            <div class="result-actions">
              <button class="action-primary" data-click="add-result" data-index="${index}">${primaryAction}</button>
              <button class="action-secondary" type="button" data-click="prepare-merge" data-index="${index}">Comparar</button>
              ${result.url ? `<a class="action-secondary span-all" href="${escapeAttr(result.url)}" target="_blank" rel="noreferrer">Detalle</a>` : ""}
            </div>
          </div>
        </article>`;
      }

      function resultMedia(title, imageUrl) {
        return imageUrl
          ? `<img class="result-media" src="${escapeAttr(cachedImageSrc(imageUrl))}" alt="" loading="lazy" decoding="async">`
          : `<div class="result-placeholder">${escapeHtml((title || "Sin imagen").slice(0, 24))}</div>`;
      }

      function searchDescription(description, collection, key) {
        if (!description) return "";
        const text = String(description).trim();
        const more = text.length > 90
          ? `<button class="description-more" type="button" data-click="show-description" data-collection="${escapeAttr(collection)}" data-key="${escapeAttr(key)}">Ver mas</button>`
          : "";
        return `<p class="result-summary">${escapeHtml(text)}</p>${more}`;
      }

      function openSearchDescription(collection, key) {
        const item = collection === "manual"
          ? manualResults[Number(key)]
          : items.find((entry) => entry.id === key);
        if (!item) return;
        const title = displayTitle(item) || "Descripcion";
        const description = item.wikipedia_extract || item.description || item.notes || item.review || "Sin descripcion.";
        fields.descriptionDialogTitle.textContent = title;
        fields.descriptionDialogText.textContent = description;
        fields.descriptionDialog.showModal();
      }

      function candidateSimilarity(result) {
        const existing = items.find((entry) => entry.id === selectedExistingIdForSearch);
        if (!existing) return "";
        let score = bestTitleSimilarity(existing, result);
        if (existing.year && String(existing.year) === String(result.year || "")) score = Math.min(100, score + 20);
        return `similitud: ${score}%`;
      }

      function bestTitleSimilarity(leftItem, rightItem) {
        const leftTitles = titleSearchValues(leftItem).map(normalizeText).filter(Boolean);
        const rightTitles = titleSearchValues(rightItem).map(normalizeText).filter(Boolean);
        let best = 0;
        for (const leftTitle of leftTitles) {
          for (const rightTitle of rightTitles) {
            const leftTerms = new Set(leftTitle.split(/\s+/).filter(Boolean));
            const rightTerms = new Set(rightTitle.split(/\s+/).filter(Boolean));
            const shared = [...leftTerms].filter((term) => rightTerms.has(term)).length;
            const total = Math.max(leftTerms.size, rightTerms.size, 1);
            best = Math.max(best, Math.round((shared / total) * 100));
          }
        }
        return best;
      }

      async function addSearchResult(index) {
        const cards = [...fields.manualSearchResults.querySelectorAll("[data-index]")];
        const button = cards.find((element) => Number(element.dataset.index) === index);
        button.disabled = true;
        button.textContent = selectedExistingIdForSearch ? "Combinando..." : "Agregando...";
        if (selectedExistingIdForSearch) {
          if (!isExternalResult(manualResults[index])) {
            button.disabled = false;
            button.textContent = "Combinar";
            alert("Este resultado no tiene un link externo reconocido. Elegí Wikipedia, IMDb o FilmAffinity.");
            console.warn("[catalog-viewer] blocked result without trusted link", { result: manualResults[index] });
            return;
          }
          await mergeSearchResult(index, selectedExistingIdForSearch);
          return;
        }
        const response = await apiFetch("/api/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(manualResults[index])
        });
        const payload = await response.json();
        if (payload.reason === "possible_duplicate") {
          button.disabled = false;
          button.textContent = "Agregar";
          showDuplicateChoice(index, payload.candidates || []);
          return;
        }
        button.textContent = payload.ok ? "Agregado" : payload.reason === "duplicate" ? "Ya existe" : "Error";
        await load();
      }

      function showDuplicateChoice(index, candidates) {
        const blocks = candidates.map((candidate) => `
          <div>
            <strong>${escapeHtml(candidate.title || "Sin titulo")}</strong>
            <div class="meta">
              ${meta(candidate.year)}${meta(candidate.source)}${meta(firstListValue(candidate.genres))}${meta(firstListValue(candidate.directors))}${meta(isInCatalog(candidate.en_catalogo) ? "catalogo: si" : "catalogo: no")}
            </div>
          </div>
          <div class="duplicate-actions">
            <button data-click="merge-result" data-index="${index}" data-id="${escapeAttr(candidate.id)}">Combinar</button>
            ${candidate.url ? `<a href="${escapeAttr(candidate.url)}" target="_blank" rel="noreferrer">Ver existente</a>` : ""}
          </div>
        `).join("");
        fields.manualSearchResults.insertAdjacentHTML("afterbegin", `
          <section class="duplicate-box">
            <strong>Posible duplicado encontrado</strong>
            <span>Ya existe una entrada con titulo y año parecidos. Podés combinarla, agregar igual o cancelar.</span>
            ${blocks}
            <div class="duplicate-actions">
              <button data-click="force-add" data-index="${index}">Agregar igual</button>
              <button data-click="run-search">Cancelar</button>
            </div>
          </section>
        `);
      }

      async function mergeSearchResult(index, targetId) {
        if (!isExternalResult(manualResults[index])) {
          alert("Este resultado no tiene un link externo reconocido. Elegí un resultado de Wikipedia, IMDb o FilmAffinity.");
          console.warn("[catalog-viewer] blocked result without trusted link", { targetId, result: manualResults[index] });
          return;
        }
        const beforeCounts = linkCounts();
        const response = await postAdd(manualResults[index], "merge", targetId);
        const payload = await response.json();
        if (!payload.ok) {
          alert(payload.reason || "No se pudo combinar");
          return;
        }
        await load();
        const afterCounts = linkCounts();
        console.log("[catalog-viewer] link merge", {
          targetId,
          result: manualResults[index],
          before: beforeCounts,
          after: afterCounts
        });
        selectedExistingIdForSearch = null;
        if (wikiReviewQueue.length) {
          wikiReviewQueue = items.filter((item) => !hasExternalLink(item));
          wikiReviewIndex = Math.min(wikiReviewIndex, Math.max(wikiReviewQueue.length - 1, 0));
          if (wikiReviewQueue.length) {
            await reviewCurrentWikiItem();
          } else {
            fields.wikiReviewStatus.textContent = "No quedan entradas sin link.";
          }
          return;
        }
        await runSearch();
      }

      async function forceAddSearchResult(index) {
        await postAdd(manualResults[index], "force", "");
        await load();
        await runSearch();
      }

      async function postAdd(result, action, targetId) {
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

      function catalogMatchScore(item, query) {
        const terms = query.split(/\s+/).filter(Boolean);
        const titles = titleSearchValues(item).map(normalizeText).filter(Boolean);
        const local = normalizeText(item.local_name || "");
        const year = String(item.year || "");
        const url = normalizeText(item.url || "");
        const haystack = `${titles.join(" ")} ${local} ${year} ${url}`;
        let score = 0;
        for (const term of terms) {
          const normalizedTerm = normalizeText(term);
          if (haystack.includes(normalizedTerm)) {
            score += 1;
          } else if (normalizedTerm.length >= 5 && haystack.split(/\s+/).some((word) => oneEditApart(word, normalizedTerm))) {
            score += 0.6;
          }
        }
        if (titles.includes(normalizeText(query))) score += 5;
        if (year && query.includes(year)) score += 2;
        return score;
      }

      function diffComparison(incoming, existing) {
        const fieldsToCompare = [
          ["Titulo", "title"],
          ["Original", "original_title"],
          ["Español", "spanish_title"],
          ["Inglés", "english_title"],
          ["Alternativos", "alternative_titles"],
          ["Año", "year"],
          ["Fuente", "source"],
          ["URL", "url"],
          ["Wikidata", "wikidata_id"],
          ["Genero", "genres"],
          ["Director", "directors"],
          ["Guion", "writers"],
          ["Reparto", "cast"],
          ["Catalogo", "en_catalogo"],
          ["Archivo", "local_name"],
          ["Archivos", "local_files"],
          ["Estado", "status"],
          ["Vista", "watched_at"],
          ["Puntaje", "rating"],
          ["Review", "review"]
        ];
        const rows = fieldsToCompare
          .map(([label, key]) => {
            const left = displayField(existing[key], key);
            const right = displayField(incoming[key], key);
            if (!left && !right) return "";
            return `<div class="diff-row">
              <strong>${escapeHtml(label)}</strong>
              <span>${escapeHtml(left || "-")}</span>
              <span>${escapeHtml(right || "-")}</span>
            </div>`;
          })
          .filter(Boolean)
          .join("");
        return `<section class="compare-box">
          <strong>Comparación: existente / resultado nuevo</strong>
          <div class="diff-grid">${rows}</div>
        </section>`;
      }

      function displayField(value, key) {
        if (key === "en_catalogo") return isInCatalog(value) ? "si" : "no";
        if (key === "local_files") return localFilesText({ local_files: value });
        if (["alternative_titles", "genres", "directors", "writers", "cast"].includes(key)) return asList(value).join(", ");
        return String(value || "");
      }

      function normalizeText(value) {
        return String(value || "")
          .toLowerCase()
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .replace(/\([^)]*\)/g, " ")
          .replace(/[^a-z0-9]+/g, " ")
          .trim();
      }

      function matchesSearchText(value, query) {
        const normalizedValue = normalizeText(value);
        const normalizedQuery = normalizeText(query);
        if (!normalizedQuery || normalizedValue.includes(normalizedQuery)) return true;
        const words = normalizedValue.split(/\s+/).filter(Boolean);
        return normalizedQuery.split(/\s+/).filter(Boolean).every((term) => (
          words.some((word) => word.includes(term) || (term.length >= 5 && oneEditApart(word, term)))
        ));
      }

      function oneEditApart(left, right) {
        if (Math.abs(left.length - right.length) > 1) return false;
        let leftIndex = 0;
        let rightIndex = 0;
        let edits = 0;
        while (leftIndex < left.length && rightIndex < right.length) {
          if (left[leftIndex] === right[rightIndex]) {
            leftIndex += 1;
            rightIndex += 1;
            continue;
          }
          edits += 1;
          if (edits > 1) return false;
          if (left.length > right.length) leftIndex += 1;
          else if (right.length > left.length) rightIndex += 1;
          else {
            leftIndex += 1;
            rightIndex += 1;
          }
        }
        if (leftIndex < left.length || rightIndex < right.length) edits += 1;
        return edits <= 1;
      }

      async function deleteCatalogItem(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        const title = item?.title || item?.local_name || "Sin titulo";
        const confirmed = confirm(`Eliminar "${title}" del catalogo? Esta accion modifica los datos.`);
        if (!confirmed) return;
        const response = await apiFetch("/api/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id,
            confirmed: true,
            source_file: item?._source_file || "",
            url: item?.url || "",
            title: item?.title || title,
            year: item?.year || "",
            local_name: item?.local_name || ""
          })
        });
        const payload = await response.json();
        if (!payload.ok) alert(payload.reason || "No se pudo eliminar");
        await load();
      }

      async function toggleWatched(event, id, currentStatus) {
        event.preventDefault();
        const nextStatus = currentStatus === "watched" ? "to_watch" : "watched";
        const item = items.find((entry) => entry.id === id);
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
        if (!payload.ok) alert(payload.reason || "No se pudo cambiar el estado");
        await load();
      }

      async function updateKind(event, id) {
        const kind = event.target.value;
        const item = items.find((entry) => entry.id === id);
        const response = await apiFetch("/api/kind", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, kind, source_file: item?._source_file || "" })
        });
        const payload = await response.json();
        if (!payload.ok) alert(payload.reason || "No se pudo cambiar el tipo");
        await load();
      }

      async function toggleCatalog(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        const nextValue = !isInCatalog(item.en_catalogo);
        const response = await apiFetch("/api/catalog", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, en_catalogo: nextValue, source_file: item?._source_file || "" })
        });
        const payload = await response.json();
        if (!payload.ok) alert(payload.reason || "No se pudo cambiar el estado de catalogo");
        await load();
      }

      function trackPersonalPanel(event, id) {
        if (event.target.open) {
          openPersonalId = id;
        } else if (openPersonalId === id) {
          openPersonalId = "";
        }
      }

      async function savePersonal(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        const panel = event.target.closest(".personal-panel");
        const watchedAt = panel?.querySelector("[data-personal-watched-at]")?.value || "";
        const rating = normalizeRating(panel?.querySelector("[data-personal-rating]")?.value);
        const review = panel?.querySelector("[data-personal-review]")?.value || "";
        const status = panel?.querySelector("[data-personal-status]");
        if (status) status.textContent = "Guardando...";
        openPersonalId = id;
        const response = await apiFetch("/api/personal", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, watched_at: watchedAt, rating, review, source_file: item?._source_file || "" })
        });
        const payload = await response.json();
        if (!payload.ok) {
          if (status) status.textContent = "";
          alert(payload.reason || "No se pudo guardar el registro personal");
          return;
        }
        await load();
      }

      async function saveMetadata(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        const editor = event.target.closest(".metadata-editor");
        if (!item || !editor) return;
        const values = {};
        editor.querySelectorAll("[data-metadata-field]").forEach((control) => {
          values[control.dataset.metadataField] = control.value;
        });
        const locked = new Set(asList(item.locked_fields));
        editor.querySelectorAll("[data-lock-field]").forEach((control) => {
          if (control.checked) locked.add(control.dataset.lockField);
          else locked.delete(control.dataset.lockField);
        });
        const status = editor.querySelector("[data-metadata-status]");
        if (status) status.textContent = "Guardando...";
        const response = await apiFetch("/api/metadata", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id,
            values,
            locked_fields: [...locked],
            source_file: item._source_file || ""
          })
        });
        const payload = await response.json();
        if (!payload.ok) {
          if (status) status.textContent = "";
          alert(payload.reason || "No se pudo guardar la metadata");
          return;
        }
        await load();
      }

      async function findLinkForCatalog(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        await findLinkForItem(item);
      }

      async function findLinkForItem(item) {
        selectedExistingIdForSearch = item.id;
        selectedManualIndex = null;
        fields.query.value = [item.title || item.local_name, item.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        fields.externalSource.checked = true;
        render();
        catalogMergeResults = [item];
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeStatus.textContent = "Elegí un resultado externo y tocá Comparar para revisar diferencias.";
        renderCatalogMergeResults();
        await searchManual("all", "Buscando coincidencias en Wikipedia, IMDb y FilmAffinity...");
        fields.query.scrollIntoView({ behavior: "smooth", block: "center" });
      }

      function meta(value) {
        return value ? `<span>${escapeHtml(value)}</span>` : "";
      }

      function displayTitle(item) {
        return item.spanish_title || item.title || item.original_title || item.english_title || item.local_name || "";
      }

      function titleSubtitle(item) {
        const shown = normalizeText(displayTitle(item));
        const values = [
          ["Original", item.original_title],
          ["Ingles", item.english_title],
          ["Base", item.title]
        ];
        const row = values.find(([, value]) => value && normalizeText(value) !== shown);
        return row ? `${row[0]}: ${row[1]}` : "";
      }

      function titleSearchValues(item) {
        return [
          item.title,
          item.original_title,
          item.spanish_title,
          item.english_title,
          ...(asList(item.alternative_titles)),
          item.wikipedia_title,
          item.local_name,
          ...localFiles(item).flatMap((file) => [file.name, file.path])
        ].filter(Boolean);
      }

      function localFiles(item) {
        return Array.isArray(item?.local_files)
          ? item.local_files.filter((file) => file && typeof file === "object")
          : [];
      }

      function localFilesText(item) {
        return localFiles(item)
          .map((file) => file.name || file.path || "")
          .filter(Boolean)
          .join(", ");
      }

      function localFileCountLabel(item) {
        const count = localFiles(item).length;
        return count ? `${count} archivo${count === 1 ? "" : "s"}` : "";
      }

      function asList(value) {
        if (Array.isArray(value)) return value.filter(Boolean);
        if (typeof value === "string") return value.split(",").map((entry) => entry.trim()).filter(Boolean);
        return [];
      }

      function firstListValue(value) {
        return asList(value)[0] || "";
      }

      function listText(value, limit) {
        const list = asList(value);
        if (!list.length) return "";
        const visible = list.slice(0, limit);
        const suffix = list.length > limit ? ` y ${list.length - limit} mas` : "";
        return visible.join(", ") + suffix;
      }

      function isInCatalog(value) {
        return value === true || value === "si" || value === "sí" || value === "true";
      }

      function hasHost(url, host) {
        try {
          const hostname = new URL(url).hostname.toLowerCase().replace(/\.$/, "");
          return hostname === host || hostname.endsWith(`.${host}`);
        } catch {
          return false;
        }
      }

      function hasExternalLink(item) {
        return hasHost(item?.url, "wikipedia.org")
          || hasHost(item?.url, "imdb.com")
          || hasHost(item?.url, "filmaffinity.com")
          || hasHost(item?.wikipedia_url, "wikipedia.org")
          || hasHost(item?.imdb_url, "imdb.com")
          || hasHost(item?.filmaffinity_url, "filmaffinity.com");
      }

      function isExternalResult(result) {
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

      function linkCounts() {
        const withLink = items.filter(hasExternalLink).length;
        return {
          withLink,
          withoutLink: items.length - withLink,
          total: items.length
        };
      }

      function normalizeKind(value) {
        const text = String(value || "pelicula").toLowerCase();
        if (["movie", "film", "película"].includes(text)) return "pelicula";
        if (["series", "tv series", "tvseries"].includes(text)) return "serie";
        if (["documentary"].includes(text)) return "documental";
        return ["pelicula", "serie", "anime", "documental"].includes(text) ? text : "pelicula";
      }

      function normalizeRating(value) {
        const rating = Number.parseInt(value || 0, 10);
        if (Number.isNaN(rating)) return 0;
        return Math.max(0, Math.min(10, rating));
      }

      function todayLocalDate() {
        const date = new Date();
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
        return date.toISOString().slice(0, 10);
      }

      function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;"
        }[char]));
      }

      function escapeAttr(value) {
        return escapeHtml(value).replace(/`/g, "&#096;");
      }
