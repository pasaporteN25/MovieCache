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
      let selectedDetailId = "";
      let detailReturnFocus = null;
      let detailReturnCardId = "";
      let detailNavigationIds = [];
      let detailNavigationMode = "catalog";
      let detailNavigationLabel = "Colección";
      let detailPersonalEditing = false;
      let detailDirtyScopes = new Set();
      let detailFeedbackState = { message: "", tone: "" };
      let detailFeedbackTimer = null;
      let pendingDetailTransition = null;
      let curationCases = [];
      let curationCounts = { pending: 0, duplicates: 0, missing_link: 0, deferred: 0 };
      let curationFilter = "pending";
      let selectedCurationCaseId = "";
      let curationLoading = false;
      let curationHistory = [];
      let curationHistoryLoading = false;
      let curationHistoryMode = storedHistoryMode();
      let mergeReview = null;
      let mergeContext = null;
      let mergeChoices = {};
      let mergeTouchedChoices = new Set();
      let mergeSubmitting = false;
      let mergeRequestSequence = 0;
      let activeQuery = "";
      let collectionSearchMode = "browse";
      let writeJsonPath = "";
      let currentView = "home";
      let manualVisibleCount = 6;
      let catalogMergeVisibleCount = 6;
      let externalSourcesLastUsed = [];
      let externalSourcesAttempted = [];
      let externalSearchController = null;
      let externalSearchTimedOut = false;
      let duplicatesOnly = false;
      let catalogVisibleCount = 36;
      let externalHealth = { sources: {}, cache: {} };
      let spotlightItems = [];
      let spotlightIndex = 0;
      let spotlightTimer = null;
      let spotlightPaused = false;
      let spotlightDetailPaused = false;
      let spotlightViewPaused = false;
      let routeRestored = false;
      const SEARCH_PAGE_SIZE = 6;
      const CATALOG_PAGE_SIZE = 36;
      const SEARCH_TIMEOUT_MS = 10000;
      const SPOTLIGHT_INTERVAL_MS = 8000;
      const COLLECTION_ROUTE_KEYS = ["q", "status", "kind", "source", "sort", "duplicates", "external"];

      function apiFetch(url, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set("X-Movie-Inbox-Token", API_TOKEN);
        return fetch(url, { ...options, headers, credentials: "same-origin" });
      }
      const fields = {
        query: document.querySelector("#query"),
        externalSource: document.querySelector("#externalSource"),
        searchButton: document.querySelector("#searchButton"),
        homeButton: document.querySelector("#homeButton"),
        catalogButton: document.querySelector("#catalogButton"),
        inboxButton: document.querySelector("#inboxButton"),
        inboxBadge: document.querySelector("#inboxBadge"),
        adminButton: document.querySelector("#adminButton"),
        systemMenu: document.querySelector("#systemMenu"),
        searchConsole: document.querySelector(".search-console"),
        collectionUtilityMenu: document.querySelector(".collection-view .utility-menu"),
        randomButton: document.querySelector("#randomButton"),
        randomCatalogOnly: document.querySelector("#randomCatalogOnly"),
        mobileRandomCatalogOnly: document.querySelector("#mobileRandomCatalogOnly"),
        randomScopeLabel: document.querySelector("#randomScopeLabel"),
        homeView: document.querySelector("#homeView"),
        inboxView: document.querySelector("#inboxView"),
        collectionView: document.querySelector("#collectionView"),
        adminView: document.querySelector("#adminView"),
        homeCollectionButton: document.querySelector("#homeCollectionButton"),
        homeGrid: document.querySelector("#homeGrid"),
        homeEmpty: document.querySelector("#homeEmpty"),
        refreshCuration: document.querySelector("#refreshCuration"),
        curationPendingCount: document.querySelector("#curationPendingCount"),
        curationDuplicateCount: document.querySelector("#curationDuplicateCount"),
        curationMissingCount: document.querySelector("#curationMissingCount"),
        curationDeferredCount: document.querySelector("#curationDeferredCount"),
        curationHistoryCount: document.querySelector("#curationHistoryCount"),
        persistCurationHistory: document.querySelector("#persistCurationHistory"),
        clearCurationHistory: document.querySelector("#clearCurationHistory"),
        curationFeedback: document.querySelector("#curationFeedback"),
        curationQueueTitle: document.querySelector("#curationQueueTitle"),
        curationQueueMeta: document.querySelector("#curationQueueMeta"),
        curationQueue: document.querySelector("#curationQueue"),
        curationDetail: document.querySelector("#curationDetail"),
        catalogSection: document.querySelector("#catalogSection"),
        spotlight: document.querySelector("#spotlight"),
        spotlightStage: document.querySelector("#spotlightStage"),
        spotlightToggle: document.querySelector("#spotlightToggle"),
        searchContext: document.querySelector("#searchContext"),
        searchContextText: document.querySelector("#searchContextText"),
        cancelSearch: document.querySelector("#cancelSearch"),
        reviewPrevious: document.querySelector("#reviewPrevious"),
        reviewNext: document.querySelector("#reviewNext"),
        backToCollection: document.querySelector("#backToCollection"),
        status: document.querySelector("#status"),
        kind: document.querySelector("#kind"),
        source: document.querySelector("#source"),
        sort: document.querySelector("#sort"),
        activeFilters: document.querySelector("#activeFilters"),
        clearFilters: document.querySelector("#clearFilters"),
        catalogSummary: document.querySelector("#catalogSummary"),
        grid: document.querySelector("#grid"),
        stats: document.querySelector("#stats"),
        total: document.querySelector("#total"),
        catalogCount: document.querySelector("#catalogCount"),
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
        catalogMergeTitle: document.querySelector("#catalogMergeTitle"),
        catalogMergeStatus: document.querySelector("#catalogMergeStatus"),
        catalogMergeResults: document.querySelector("#catalogMergeResults"),
        databaseCatalogPanel: document.querySelector("#databaseCatalogPanel"),
        databaseExternalPanel: document.querySelector("#databaseExternalPanel"),
        detailDrawer: document.querySelector("#detailDrawer"),
        detailBody: document.querySelector("#detailBody"),
        closeDetail: document.querySelector("#closeDetail"),
        detailNavigation: document.querySelector("#detailNavigation"),
        detailFeedback: document.querySelector("#detailFeedback"),
        unsavedDetailDialog: document.querySelector("#unsavedDetailDialog"),
        keepEditingDetail: document.querySelector("#keepEditingDetail"),
        discardDetailChanges: document.querySelector("#discardDetailChanges"),
        saveDetailChanges: document.querySelector("#saveDetailChanges"),
        catalogLoadMore: document.querySelector("#catalogLoadMore"),
        descriptionDialog: document.querySelector("#descriptionDialog"),
        descriptionDialogTitle: document.querySelector("#descriptionDialogTitle"),
        descriptionDialogText: document.querySelector("#descriptionDialogText"),
        closeDescriptionDialog: document.querySelector("#closeDescriptionDialog"),
        mergeComparatorDialog: document.querySelector("#mergeComparatorDialog"),
        mergeComparatorTitle: document.querySelector("#mergeComparatorTitle"),
        mergeComparatorSubtitle: document.querySelector("#mergeComparatorSubtitle"),
        mergeSurvivorControl: document.querySelector("#mergeSurvivorControl"),
        mergeSurvivorLeft: document.querySelector("#mergeSurvivorLeft"),
        mergeSurvivorRight: document.querySelector("#mergeSurvivorRight"),
        mergeShowAllFields: document.querySelector("#mergeShowAllFields"),
        mergeComparatorSummary: document.querySelector("#mergeComparatorSummary"),
        mergeComparatorFeedback: document.querySelector("#mergeComparatorFeedback"),
        mergeComparatorFields: document.querySelector("#mergeComparatorFields"),
        mergeDecisionStatus: document.querySelector("#mergeDecisionStatus"),
        mergeDecisionMeta: document.querySelector("#mergeDecisionMeta"),
        closeMergeComparator: document.querySelector("#closeMergeComparator"),
        cancelMergeComparator: document.querySelector("#cancelMergeComparator"),
        confirmReviewedMerge: document.querySelector("#confirmReviewedMerge"),
        empty: document.querySelector("#empty")
      };

      document.querySelector("#refresh").addEventListener("click", load);
      fields.searchButton.addEventListener("click", () => runSearch());
      fields.homeButton.addEventListener("click", goHome);
      fields.catalogButton.addEventListener("click", goToCollectionRoot);
      fields.inboxButton.addEventListener("click", () => goToInbox());
      fields.adminButton.addEventListener("click", goToAdmin);
      fields.homeCollectionButton.addEventListener("click", goToCollectionRoot);
      fields.refreshCuration.addEventListener("click", () => loadCurationQueue({ announce: true }));
      fields.inboxView.addEventListener("click", handleCurationClick);
      fields.persistCurationHistory.checked = curationHistoryMode === "persistent";
      fields.persistCurationHistory.nextElementSibling.textContent = curationHistoryMode === "persistent"
        ? "Historial persistente"
        : "Sólo esta sesión";
      fields.persistCurationHistory.addEventListener("change", changeCurationHistoryMode);
      fields.clearCurationHistory.addEventListener("click", clearCurationHistory);
      fields.randomButton.addEventListener("click", openRandomDetail);
      fields.randomCatalogOnly.addEventListener("change", () => changeRandomScope(fields.randomCatalogOnly));
      fields.mobileRandomCatalogOnly.addEventListener("change", () => changeRandomScope(fields.mobileRandomCatalogOnly));
      fields.spotlightToggle.addEventListener("click", toggleSpotlight);
      fields.cancelSearch.addEventListener("click", cancelExternalSearch);
      fields.reviewPrevious.addEventListener("click", previousWikiReview);
      fields.reviewNext.addEventListener("click", nextWikiReview);
      fields.backToCollection.addEventListener("click", () => {
        goToCollectionRoot();
      });
      fields.externalSource.addEventListener("change", renderDatabaseMenu);
      fields.clearFilters.addEventListener("click", clearFilters);
      fields.clearManualSearch.addEventListener("click", () => clearManualSearch());
      fields.startWikiReview.addEventListener("click", () => goToInbox("missing_link"));
      fields.previousWikiReview.addEventListener("click", previousWikiReview);
      fields.nextWikiReview.addEventListener("click", nextWikiReview);
      fields.randomizeView.addEventListener("click", randomizeView);
      fields.resetOrder.addEventListener("click", resetViewOrder);
      fields.showDuplicates.addEventListener("click", () => goToInbox("duplicate"));
      fields.closeDetail.addEventListener("click", closeDetail);
      fields.detailDrawer.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeDetail();
      });
      fields.detailDrawer.addEventListener("click", (event) => {
        if (event.target === fields.detailDrawer) closeDetail();
      });
      fields.detailBody.addEventListener("input", handleDetailFormMutation);
      fields.detailBody.addEventListener("change", handleDetailFormMutation);
      fields.keepEditingDetail.addEventListener("click", keepEditingDetail);
      fields.discardDetailChanges.addEventListener("click", discardDetailChanges);
      fields.saveDetailChanges.addEventListener("click", saveDetailChanges);
      fields.unsavedDetailDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        keepEditingDetail();
      });
      fields.unsavedDetailDialog.addEventListener("click", (event) => {
        if (event.target === fields.unsavedDetailDialog) keepEditingDetail();
      });
      fields.catalogLoadMore.addEventListener("click", showMoreCatalogItems);
      fields.closeDescriptionDialog.addEventListener("click", () => fields.descriptionDialog.close());
      fields.closeMergeComparator.addEventListener("click", () => closeMergeComparator());
      fields.cancelMergeComparator.addEventListener("click", () => closeMergeComparator());
      fields.confirmReviewedMerge.addEventListener("click", submitReviewedMerge);
      fields.mergeShowAllFields.addEventListener("change", renderMergeComparator);
      fields.mergeSurvivorControl.addEventListener("change", changeMergeSurvivor);
      fields.mergeComparatorFields.addEventListener("change", changeMergeChoice);
      fields.mergeComparatorDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeMergeComparator();
      });
      fields.mergeComparatorDialog.addEventListener("click", (event) => {
        if (event.target === fields.mergeComparatorDialog) closeMergeComparator();
      });
      fields.query.addEventListener("keydown", (event) => {
        if (event.key === "Enter") runSearch();
        if (event.key === "Escape") clearManualSearch();
      });
      document.addEventListener("visibilitychange", handleVisibilityChange);
      document.addEventListener("keydown", handleKeyboardModality, true);
      document.addEventListener("pointerdown", handlePointerModality, true);
      window.addEventListener("beforeunload", handleBeforeUnload);
      window.addEventListener("popstate", restoreRoute);
      document.addEventListener("error", handlePosterError, true);
      document.addEventListener("click", handleDelegatedClick);
      [fields.status, fields.kind, fields.source, fields.sort].forEach((field) => field.addEventListener("input", () => {
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
        syncCollectionRoute("push");
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
          "open-detail": () => openDetailFromTrigger(target, id),
          "toggle-watched": () => runDetailAwareAction(target, () => toggleWatched(event, id, target.dataset.status || "to_watch")),
          "focus-personal": editPersonalRecord,
          "edit-personal": editPersonalRecord,
          "cancel-personal": cancelPersonalEdit,
          "find-link": () => runDetailAwareAction(target, () => findLinkForCatalog(event, id)),
          "save-personal": () => savePersonal(event, id),
          "toggle-catalog": () => runDetailAwareAction(target, () => toggleCatalog(event, id)),
          "delete-item": () => requestDetailTransition(() => deleteCatalogItem(event, id)),
          "save-metadata": () => saveMetadata(event, id),
          "detail-previous": () => navigateDetail(-1),
          "detail-next": () => navigateDetail(1),
          "detail-random": openAnotherRandomDetail,
          "retry-merge-comparison": retryMergeComparison,
          "show-more-manual": showMoreManualResults,
          "show-more-catalog": showMoreCatalogResults,
          "merge-result": () => mergeSearchResult(index, id),
          "add-result": () => addSearchResult(index),
          "prepare-merge": () => prepareManualMerge(index),
          "show-description": () => openSearchDescription(target.dataset.collection || "", target.dataset.key || ""),
          "force-add": () => forceAddSearchResult(index),
          "clear-filter": () => clearFilter(target.dataset.filter || ""),
          "run-search": runSearch
        };
        actions[target.dataset.click]?.();
      }

      function handleKeyboardModality(event) {
        if (["Tab", "Enter", " "].includes(event.key)) document.body.dataset.inputMethod = "keyboard";
      }

      function handlePointerModality() {
        document.body.dataset.inputMethod = "pointer";
      }

      function runDetailAwareAction(target, action) {
        if (target.closest("#detailDrawer") && hasUnsavedDetailChanges()) {
          requestDetailTransition(action);
          return;
        }
        action();
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
        curationCounts = {
          ...curationCounts,
          ...(payload.curation?.counts || {})
        };
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        setupSelect(fields.status, "Estado", items.map((item) => item.status));
        setupSelect(fields.kind, "Tipo", items.map((item) => item.kind));
        setupSelect(fields.source, "Fuente", items.map((item) => item.source));
        seedSpotlight();
        render();
        renderSpotlight();
        startSpotlight();
        renderDatabaseMenu();
        syncCurationCounts();
        if (currentView === "inbox") await loadCurationQueue();
        if (!routeRestored) {
          routeRestored = true;
          restoreRoute();
        }
      }

      function goHome() {
        closeDetail({ restoreFocus: false, updateHistory: false });
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true });
        seedSpotlight();
        renderSpotlight();
        render();
        showView("home", { updateHistory: false, focus: true });
        syncRoute(routeValuesForView("home"), "push");
      }

      function goToCollection(options = {}) {
        showView("catalog", options);
      }

      function goToCollectionRoot() {
        resetCollectionFilters();
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true });
        showView("catalog", { updateHistory: false, focus: true });
        syncRoute(routeValuesForView("catalog"), "push");
      }

      async function goToInbox(filter = "") {
        if (filter) curationFilter = filter;
        showView("inbox");
        await loadCurationQueue();
      }

      function goToAdmin(options = {}) {
        showView("admin", options);
      }

      function showView(view, options = {}) {
        const updateHistory = options.updateHistory !== false;
        const scroll = options.scroll !== false;
        const focus = options.focus ?? updateHistory;
        currentView = ["home", "catalog", "inbox", "admin"].includes(view) ? view : "home";
        fields.homeView.hidden = currentView !== "home";
        fields.collectionView.hidden = currentView !== "catalog";
        fields.inboxView.hidden = currentView !== "inbox";
        fields.adminView.hidden = currentView !== "admin";
        spotlightViewPaused = currentView !== "home";
        if (spotlightViewPaused) stopSpotlight();
        else startSpotlight();
        setActiveNavigation(currentView);
        if (fields.systemMenu.open) fields.systemMenu.open = false;
        if (updateHistory) syncRoute(routeValuesForView(currentView), "push");
        renderHeaderStats();
        if (scroll) scrollPageTop();
        if (focus) requestAnimationFrame(() => focusViewHeading(currentView));
      }

      function scrollPageTop() {
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
      }

      function focusViewHeading(view) {
        const selector = {
          home: "#spotlightTitle",
          catalog: "#catalogTitle",
          inbox: "#inboxTitle",
          admin: "#adminTitle"
        }[view];
        if (!selector) return;
        document.querySelector(selector)?.focus({ preventScroll: true });
      }

      function setActiveNavigation(view) {
        const buttons = {
          home: fields.homeButton,
          catalog: fields.catalogButton,
          inbox: fields.inboxButton,
          admin: fields.adminButton
        };
        for (const [name, button] of Object.entries(buttons)) {
          const active = name === view;
          button.classList.toggle("active", active);
          if (active) button.setAttribute("aria-current", "page");
          else button.removeAttribute("aria-current");
        }
        fields.systemMenu.classList.toggle("active", view === "admin");
      }

      async function loadCurationQueue({ announce = false } = {}) {
        if (curationLoading) return;
        curationLoading = true;
        fields.inboxView.setAttribute("aria-busy", "true");
        fields.refreshCuration.disabled = true;
        if (announce) setCurationFeedback("Actualizando bandeja…", "working");
        try {
          const response = await apiFetch("/api/curation");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationCases = payload.cases || [];
          curationCounts = {
            pending: 0,
            duplicates: 0,
            missing_link: 0,
            deferred: 0,
            ...(payload.counts || {})
          };
          const visible = visibleCurationCases();
          if (!visible.some((entry) => entry.id === selectedCurationCaseId)) {
            selectedCurationCaseId = visible[0]?.id || "";
          }
          await loadCurationHistory();
          syncCurationCounts();
          renderCuration();
          if (announce) setCurationFeedback("Bandeja actualizada", "success");
        } catch (error) {
          console.error("[catalog-viewer] curation load failed", error);
          setCurationFeedback("No se pudo cargar la bandeja. Reintentá desde Actualizar bandeja.", "error");
          fields.curationQueue.innerHTML = "";
          fields.curationDetail.innerHTML = curationEmptyState("Bandeja no disponible", "La colección permanece intacta.");
        } finally {
          curationLoading = false;
          fields.inboxView.setAttribute("aria-busy", "false");
          fields.refreshCuration.disabled = false;
        }
      }

      async function loadCurationHistory() {
        if (curationHistoryLoading) return;
        curationHistoryLoading = true;
        try {
          const response = await apiFetch(`/api/curation/history?mode=${encodeURIComponent(curationHistoryMode)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationHistory = payload.operations || [];
          fields.curationHistoryCount.textContent = payload.count || 0;
        } catch (error) {
          console.error("[catalog-viewer] curation history load failed", error);
          curationHistory = [];
          fields.curationHistoryCount.textContent = "!";
          if (curationFilter === "history") {
            setCurationFeedback("No se pudo cargar el historial de curaduría.", "error");
          }
        } finally {
          curationHistoryLoading = false;
        }
      }

      function storedHistoryMode() {
        try {
          return localStorage.getItem("movie-inbox-curation-history-mode") === "session"
            ? "session"
            : "persistent";
        } catch (_) {
          return "persistent";
        }
      }

      async function changeCurationHistoryMode() {
        curationHistoryMode = fields.persistCurationHistory.checked ? "persistent" : "session";
        try {
          localStorage.setItem("movie-inbox-curation-history-mode", curationHistoryMode);
        } catch (_) {
          // The preference remains active for this page even when storage is unavailable.
        }
        fields.persistCurationHistory.nextElementSibling.textContent = curationHistoryMode === "persistent"
          ? "Historial persistente"
          : "Sólo esta sesión";
        selectedCurationCaseId = "";
        await loadCurationHistory();
        renderCuration();
        setCurationFeedback(
          curationHistoryMode === "persistent"
            ? "Las próximas decisiones conservarán Deshacer después de reiniciar."
            : "Las próximas decisiones podrán deshacerse sólo durante esta sesión.",
          "success"
        );
      }

      async function clearCurationHistory() {
        const count = curationHistory.length;
        if (!count) {
          setCurationFeedback("No hay actividad para limpiar.", "");
          return;
        }
        const confirmed = confirm(
          `Eliminar ${count} ${count === 1 ? "operación" : "operaciones"} del historial? Ya no podrán deshacerse.`
        );
        if (!confirmed) return;
        fields.clearCurationHistory.disabled = true;
        try {
          const response = await apiFetch("/api/curation/history/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              history_mode: curationHistoryMode,
              confirmed: true
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationHistory = [];
          selectedCurationCaseId = "";
          syncCurationCounts();
          renderCuration();
          setCurationFeedback("Historial eliminado.", "success");
        } catch (error) {
          console.error("[catalog-viewer] history clear failed", error);
          setCurationFeedback("No se pudo limpiar el historial. El catálogo no fue modificado.", "error");
        } finally {
          fields.clearCurationHistory.disabled = false;
        }
      }

      function syncCurationCounts() {
        fields.curationPendingCount.textContent = curationCounts.pending || 0;
        fields.curationDuplicateCount.textContent = curationCounts.duplicates || 0;
        fields.curationMissingCount.textContent = curationCounts.missing_link || 0;
        fields.curationDeferredCount.textContent = curationCounts.deferred || 0;
        fields.curationHistoryCount.textContent = curationHistory.length || 0;
        fields.inboxBadge.textContent = curationCounts.pending || 0;
        fields.inboxBadge.hidden = !(curationCounts.pending > 0);
        fields.inboxButton.setAttribute(
          "aria-label",
          curationCounts.pending
            ? `Bandeja, ${curationCounts.pending} ${
                curationCounts.pending === 1 ? "decisión pendiente" : "decisiones pendientes"
              }`
            : "Bandeja, sin decisiones pendientes"
        );
      }

      function handleCurationClick(event) {
        const filter = event.target.closest("[data-curation-filter]");
        if (filter) {
          curationFilter = filter.dataset.curationFilter || "pending";
          selectedCurationCaseId = "";
          renderCuration();
          return;
        }
        const queueItem = event.target.closest("[data-curation-case]");
        if (queueItem) {
          selectedCurationCaseId = queueItem.dataset.curationCase || "";
          renderCuration();
          return;
        }
        const action = event.target.closest("[data-curation-action]");
        if (!action) return;
        const actionName = action.dataset.curationAction;
        if (actionName === "undo-operation") {
          undoCurationOperation(action.dataset.operationId || selectedCurationCaseId);
          return;
        }
        const selected = curationCases.find((entry) => entry.id === selectedCurationCaseId);
        if (!selected) return;
        if (actionName === "open-primary") {
          openCurationItem(selected.primary);
          return;
        }
        if (actionName === "open-secondary" && selected.secondary) {
          openCurationItem(selected.secondary);
          return;
        }
        if (actionName === "find-link") {
          findLinkFromCuration(selected.primary);
          return;
        }
        if (actionName === "compare-duplicate" && selected.secondary) {
          openInternalMergeComparator(selected);
          return;
        }
        if (actionName === "link-deferred") updateLinkCuration(selected, "deferred");
        if (actionName === "link-not-required") updateLinkCuration(selected, "not_required");
        if (actionName === "link-pending") updateLinkCuration(selected, "pending");
        if (actionName === "duplicate-deferred") updateDuplicateCuration(selected, "deferred");
        if (actionName === "duplicate-not-duplicate") updateDuplicateCuration(selected, "not_duplicate");
        if (actionName === "duplicate-pending") updateDuplicateCuration(selected, "pending");
      }

      function visibleCurationCases() {
        if (curationFilter === "history") return [];
        if (curationFilter === "deferred") {
          return curationCases.filter((entry) => entry.status === "deferred");
        }
        const pending = curationCases.filter((entry) => entry.status === "pending");
        if (curationFilter === "duplicate") return pending.filter((entry) => entry.type === "duplicate");
        if (curationFilter === "missing_link") return pending.filter((entry) => entry.type === "missing_link");
        return pending;
      }

      function renderCuration() {
        if (curationFilter === "history") {
          renderCurationHistory();
          return;
        }
        const visible = visibleCurationCases();
        if (!visible.some((entry) => entry.id === selectedCurationCaseId)) {
          selectedCurationCaseId = visible[0]?.id || "";
        }
        fields.inboxView.querySelectorAll("[data-curation-filter]").forEach((button) => {
          const active = button.dataset.curationFilter === curationFilter;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        const labels = {
          pending: "Decisiones pendientes",
          duplicate: "Posibles duplicados",
          missing_link: "Entradas sin link",
          deferred: "Decisiones pospuestas"
        };
        fields.curationQueueTitle.textContent = labels[curationFilter] || labels.pending;
        fields.curationQueueMeta.textContent = `${visible.length} ${visible.length === 1 ? "caso" : "casos"}`;
        fields.curationQueue.innerHTML = visible.length
          ? visible.map(curationQueueItem).join("")
          : curationEmptyState(
              curationFilter === "deferred" ? "No hay decisiones pospuestas" : "No quedan casos en esta cola",
              curationFilter === "pending" ? "La bandeja está al día." : "Probá otro filtro."
            );
        const selected = visible.find((entry) => entry.id === selectedCurationCaseId);
        fields.curationDetail.innerHTML = selected
          ? curationCaseDetail(selected)
          : curationEmptyState("Sin caso seleccionado", "La evidencia aparecerá cuando haya una decisión disponible.");
      }

      function renderCurationHistory() {
        if (!curationHistory.some((entry) => entry.id === selectedCurationCaseId)) {
          selectedCurationCaseId = curationHistory[0]?.id || "";
        }
        fields.inboxView.querySelectorAll("[data-curation-filter]").forEach((button) => {
          const active = button.dataset.curationFilter === "history";
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        fields.curationQueueTitle.textContent = curationHistoryMode === "persistent"
          ? "Actividad persistente"
          : "Actividad de esta sesión";
        fields.curationQueueMeta.textContent = `${curationHistory.length} ${
          curationHistory.length === 1 ? "operación" : "operaciones"
        }`;
        fields.curationQueue.innerHTML = curationHistory.length
          ? curationHistory.map(curationHistoryItem).join("")
          : curationEmptyState("Todavía no hay actividad", "Las decisiones nuevas aparecerán en este registro.");
        const selected = curationHistory.find((entry) => entry.id === selectedCurationCaseId);
        fields.curationDetail.innerHTML = selected
          ? curationHistoryDetail(selected)
          : curationEmptyState("Sin operación seleccionada", "Elegí una actividad para revisar su estado.");
      }

      function curationHistoryItem(operation) {
        const selected = operation.id === selectedCurationCaseId;
        return `<button class="curation-queue-item history-item ${selected ? "selected" : ""}" type="button"
          data-curation-case="${escapeAttr(operation.id)}" aria-pressed="${selected}">
          <span class="history-operation-mark" aria-hidden="true">${operation.action === "merge" ? "M" : "D"}</span>
          <span class="curation-queue-copy">
            <span class="curation-queue-type">${escapeHtml(curationActionLabel(operation.action))}</span>
            <strong>${escapeHtml(operation.label || "Decisión de curaduría")}</strong>
            <small>${escapeHtml(formatHistoryDate(operation.created_at))}</small>
          </span>
          <span class="pill ${operation.status === "undone" ? "muted" : "good"}">${
            operation.status === "undone" ? "deshecha" : "aplicada"
          }</span>
        </button>`;
      }

      function curationHistoryDetail(operation) {
        const summary = operation.summary || {};
        const changedFields = asList(summary.changed_fields);
        return `<section class="history-detail">
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${escapeHtml(curationActionLabel(operation.action))}</span>
              <h3>${escapeHtml(operation.label || "Decisión de curaduría")}</h3>
            </div>
            <span class="pill ${operation.status === "undone" ? "muted" : "good"}">${
              operation.status === "undone" ? "Deshecha" : "Aplicada"
            }</span>
          </header>
          <dl class="history-facts">
            <div><dt>Fecha</dt><dd>${escapeHtml(formatHistoryDate(operation.created_at))}</dd></div>
            <div><dt>Alcance</dt><dd>${operation.mode === "session" ? "Sólo esta sesión" : "Persistente"}</dd></div>
            ${summary.survivor_title ? `<div><dt>Entrada final</dt><dd>${escapeHtml(summary.survivor_title)}</dd></div>` : ""}
            ${changedFields.length ? `<div><dt>Campos revisados</dt><dd>${changedFields.length}</dd></div>` : ""}
          </dl>
          ${changedFields.length
            ? `<div class="history-field-list">${changedFields.map((field) => `<span>${escapeHtml(mergeFieldLabel(field))}</span>`).join("")}</div>`
            : ""}
          <footer class="curation-actions">
            ${operation.can_undo
              ? `<button class="action-primary" type="button" data-curation-action="undo-operation"
                   data-operation-id="${escapeAttr(operation.id)}">Deshacer operación</button>`
              : `<span class="history-closed-note">Esta operación ya fue deshecha.</span>`}
          </footer>
        </section>`;
      }

      function curationActionLabel(action) {
        return {
          merge: "Combinación",
          link_curation: "Referencia",
          duplicate_curation: "Duplicado"
        }[action] || "Curaduría";
      }

      function formatHistoryDate(value) {
        if (!value) return "Sin fecha";
        const date = new Date(value);
        return Number.isNaN(date.getTime())
          ? String(value)
          : date.toLocaleString("es-AR", { dateStyle: "medium", timeStyle: "short" });
      }

      function curationQueueItem(entry) {
        const item = entry.primary;
        const selected = entry.id === selectedCurationCaseId;
        const type = entry.type === "duplicate" ? "Duplicado" : "Sin link";
        return `<button class="curation-queue-item ${selected ? "selected" : ""}" type="button"
          data-curation-case="${escapeAttr(entry.id)}" aria-pressed="${selected}">
          ${curationThumb(item)}
          <span class="curation-queue-copy">
            <span class="curation-queue-type">${escapeHtml(type)}${entry.status === "deferred" ? " · Pospuesta" : ""}</span>
            <strong>${escapeHtml(item.title || "Sin título")}</strong>
            <small>${escapeHtml([item.year, item.kind].filter(Boolean).join(" · ") || "Sin año")}</small>
          </span>
          <span class="curation-queue-arrow" aria-hidden="true">→</span>
        </button>`;
      }

      function curationCaseDetail(entry) {
        return entry.type === "duplicate"
          ? duplicateCurationDetail(entry)
          : missingLinkCurationDetail(entry);
      }

      function duplicateCurationDetail(entry) {
        const deferred = entry.status === "deferred";
        return `
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${deferred ? "Decisión pospuesta" : "Revisión necesaria"}</span>
              <h3>¿Son la misma obra?</h3>
            </div>
            <span class="pill warning">Posible duplicado</span>
          </header>
          ${curationEvidence(entry.evidence)}
          <div class="curation-pair">
            ${curationRecord(entry.primary, "Entrada A", "open-primary")}
            <div class="curation-pair-mark" aria-hidden="true">↔</div>
            ${curationRecord(entry.secondary, "Entrada B", "open-secondary")}
          </div>
          <footer class="curation-actions">
            ${deferred
              ? `<button class="action-primary" type="button" data-curation-action="compare-duplicate">Comparar y combinar</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-pending">Volver a pendientes</button>`
              : `<button class="action-primary" type="button" data-curation-action="compare-duplicate">Comparar y combinar</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-not-duplicate">No son duplicados</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-deferred">Posponer</button>`}
          </footer>
        `;
      }

      function missingLinkCurationDetail(entry) {
        const deferred = entry.status === "deferred";
        return `
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${deferred ? "Decisión pospuesta" : "Referencia pendiente"}</span>
              <h3>${escapeHtml(entry.primary.title || "Sin título")}</h3>
            </div>
            <span class="pill muted">Sin link</span>
          </header>
          ${curationEvidence(entry.evidence)}
          <div class="curation-single-record">${curationRecord(entry.primary, "Entrada actual", "open-primary")}</div>
          <footer class="curation-actions">
            ${deferred
              ? `<button class="action-primary" type="button" data-curation-action="link-pending">Volver a pendientes</button>`
              : `<button class="action-primary" type="button" data-curation-action="find-link">Buscar referencia</button>
                 <button class="quiet-action" type="button" data-curation-action="link-not-required">No requiere referencia</button>
                 <button class="quiet-action" type="button" data-curation-action="link-deferred">Posponer</button>`}
          </footer>
        `;
      }

      function curationRecord(item, label, action) {
        if (!item) return "";
        return `<article class="curation-record">
          <span class="curation-record-label">${escapeHtml(label)}</span>
          <div class="curation-record-main">
            ${curationThumb(item, true)}
            <div>
              <h4>${escapeHtml(item.title || "Sin título")}</h4>
              <div class="meta">${meta(item.year)}${meta(item.kind)}${meta(item.source)}</div>
              <div class="card-badges">
                <span class="pill ${item.en_catalogo ? "good" : "muted"}">${item.en_catalogo ? "en catálogo" : "fuera de catálogo"}</span>
                <span class="pill ${item.status === "watched" ? "good" : "muted"}">${item.status === "watched" ? "vista" : "pendiente"}</span>
              </div>
            </div>
          </div>
          <button class="text-action curation-open-record" type="button" data-curation-action="${action}">Abrir ficha</button>
        </article>`;
      }

      function curationThumb(item, large = false) {
        const className = large ? "curation-thumb large" : "curation-thumb";
        const title = item?.title || "Sin imagen";
        const fallback = `<span class="${className} curation-thumb-placeholder">${escapeHtml(title.slice(0, 18))}</span>`;
        if (!item?.page_image) return fallback;
        return `<span class="curation-thumb-frame ${large ? "large" : ""}">
          <img class="${className}" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="" loading="lazy" decoding="async">
          ${fallback.replace('class="', 'hidden class="')}
        </span>`;
      }

      function curationEvidence(evidence) {
        return `<div class="curation-evidence">
          <strong>Evidencia</strong>
          <ul>${asList(evidence).map((row) => `<li>${escapeHtml(row)}</li>`).join("")}</ul>
        </div>`;
      }

      function curationEmptyState(title, copy) {
        return `<div class="curation-empty"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(copy)}</p></div>`;
      }

      function openCurationItem(summary) {
        if (!summary?.id) return;
        const contextIds = [...new Set(
          visibleCurationCases()
            .flatMap((entry) => [entry.primary?.id, entry.secondary?.id])
            .filter(Boolean)
        )];
        openDetail(summary.id, {
          context: { mode: "curation", label: "Bandeja", ids: contextIds }
        });
      }

      async function findLinkFromCuration(summary) {
        const item = items.find((entry) => (
          entry.id === summary.id
          && (!summary.source_file || entry._source_file === summary.source_file)
        ));
        if (!item) {
          setCurationFeedback("La entrada ya no está disponible en el catálogo.", "error");
          return;
        }
        await findLinkForItem(item);
      }

      async function updateLinkCuration(entry, status) {
        await postCurationDecision("/api/curation/link", {
          id: entry.primary.id,
          source_file: entry.primary.source_file,
          status
        });
      }

      async function updateDuplicateCuration(entry, status) {
        await postCurationDecision("/api/curation/duplicate", {
          id: entry.primary.id,
          source_file: entry.primary.source_file,
          other_reference: entry.secondary.ref,
          status
        });
      }

      async function postCurationDecision(path, body) {
        fields.curationDetail.querySelectorAll("button").forEach((button) => { button.disabled = true; });
        setCurationFeedback("Guardando decisión…", "working");
        try {
          const response = await apiFetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...body,
              history_mode: curationHistoryMode
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedCurationCaseId = "";
          await loadCatalog();
          setCurationFeedback("Decisión guardada", "success", payload.operation);
        } catch (error) {
          console.error("[catalog-viewer] curation update failed", error);
          setCurationFeedback("No se pudo guardar la decisión. Reintentá sin salir de la Bandeja.", "error");
          renderCuration();
        }
      }

      async function undoCurationOperation(operationId) {
        if (!operationId) return;
        fields.curationDetail.querySelectorAll("button").forEach((button) => { button.disabled = true; });
        setCurationFeedback("Restaurando estado anterior…", "working");
        try {
          const response = await apiFetch("/api/curation/undo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              operation_id: operationId,
              history_mode: curationHistoryMode
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            const reason = payload.reason || `HTTP ${response.status}`;
            if (response.status === 409) {
              throw new Error("La entrada cambió después de esta operación. Revisala antes de restaurar.");
            }
            throw new Error(reason);
          }
          selectedCurationCaseId = operationId;
          await loadCatalog();
          curationFilter = "history";
          renderCuration();
          setCurationFeedback("Operación deshecha. Se restauró el estado anterior.", "success");
        } catch (error) {
          console.error("[catalog-viewer] curation undo failed", error);
          setCurationFeedback(error.message || "No se pudo deshacer la operación.", "error");
          renderCuration();
        }
      }

      function setCurationFeedback(message, tone = "", operation = null) {
        fields.curationFeedback.innerHTML = operation?.can_undo
          ? `<span>${escapeHtml(message)}</span>
             <button class="text-action" type="button" data-curation-action="undo-operation"
               data-operation-id="${escapeAttr(operation.id)}">Deshacer</button>`
          : escapeHtml(message);
        fields.curationFeedback.dataset.tone = tone;
      }

      async function openInternalMergeComparator(entry) {
        if (!entry?.primary || !entry?.secondary) return;
        await openMergeComparator({
          type: "internal",
          left: {
            id: entry.primary.id,
            source_file: entry.primary.source_file
          },
          right: {
            id: entry.secondary.id,
            source_file: entry.secondary.source_file
          }
        });
      }

      async function openExternalMergeComparator(index, targetId) {
        const result = manualResults[index];
        const target = items.find((entry) => entry.id === targetId);
        if (!result || !target) {
          setCurationFeedback("La entrada o el resultado ya no están disponibles.", "error");
          return;
        }
        await openMergeComparator({
          type: "external",
          resultIndex: index,
          left: {
            id: target.id,
            source_file: target._source_file || ""
          },
          result
        });
      }

      async function openMergeComparator(context) {
        mergeContext = context;
        mergeReview = null;
        mergeChoices = {};
        mergeTouchedChoices = new Set();
        mergeSubmitting = false;
        fields.mergeShowAllFields.checked = false;
        fields.mergeComparatorFeedback.textContent = "";
        fields.mergeComparatorFeedback.dataset.tone = "";
        fields.mergeComparatorTitle.textContent = "Preparando comparación";
        fields.mergeComparatorSubtitle.textContent = "Cargando los valores actuales del catálogo.";
        fields.mergeSurvivorControl.hidden = true;
        fields.mergeComparatorSummary.innerHTML = "";
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.confirmReviewedMerge.disabled = true;
        fields.mergeDecisionStatus.textContent = "Leyendo entradas";
        fields.mergeDecisionMeta.textContent = "";
        if (!fields.mergeComparatorDialog.open) fields.mergeComparatorDialog.showModal();
        await requestMergeComparison("left");
      }

      async function requestMergeComparison(survivorSide) {
        if (!mergeContext) return;
        const requestId = ++mergeRequestSequence;
        const requestContext = mergeContext;
        mergeContext.survivor_side = survivorSide;
        fields.mergeComparatorDialog.dataset.loading = "true";
        fields.confirmReviewedMerge.disabled = true;
        fields.mergeComparatorFeedback.textContent = "";
        try {
          const body = {
            left: mergeContext.left,
            survivor_side: survivorSide
          };
          if (mergeContext.type === "internal") body.right = mergeContext.right;
          else body.result = mergeContext.result;
          const response = await apiFetch("/api/curation/compare", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          if (
            !payload
            || !payload.left
            || !payload.right
            || !Array.isArray(payload.fields)
            || !Array.isArray(payload.groups)
          ) {
            throw new Error("invalid_comparison_payload");
          }
          if (requestId !== mergeRequestSequence || mergeContext !== requestContext) return;
          mergeReview = payload;
          if (payload.incoming) mergeContext.incoming = payload.incoming;
          mergeChoices = Object.fromEntries(
            payload.fields
              .filter((field) => field.default_choice)
              .map((field) => [field.key, field.default_choice])
          );
          mergeTouchedChoices = new Set();
          renderMergeComparator();
        } catch (error) {
          if (requestId !== mergeRequestSequence || mergeContext !== requestContext) return;
          console.error("[catalog-viewer] merge comparison failed", error);
          mergeReview = null;
          fields.mergeComparatorTitle.textContent = "No se pudo comparar";
          fields.mergeComparatorSubtitle.textContent = "Las entradas no fueron modificadas.";
          fields.mergeSurvivorControl.hidden = true;
          fields.mergeComparatorSummary.innerHTML = "";
          fields.mergeComparatorFields.innerHTML = `<div class="curation-empty">
            <strong>Comparación no disponible</strong>
            <p>No pudimos leer ambas entradas. Podés reintentar sin cerrar esta mesa.</p>
            <button class="quiet-action merge-error-action" type="button" data-click="retry-merge-comparison">Reintentar comparación</button>
          </div>`;
          fields.mergeComparatorFeedback.textContent = "La comparación se interrumpió. El catálogo permanece intacto.";
          fields.mergeComparatorFeedback.dataset.tone = "error";
          fields.mergeDecisionStatus.textContent = "Comparación interrumpida";
          fields.mergeDecisionMeta.textContent = "";
        } finally {
          if (requestId === mergeRequestSequence) {
            fields.mergeComparatorDialog.dataset.loading = "false";
          }
        }
      }

      function retryMergeComparison() {
        if (!mergeContext || fields.mergeComparatorDialog.dataset.loading === "true") return;
        fields.mergeComparatorTitle.textContent = "Preparando comparación";
        fields.mergeComparatorSubtitle.textContent = "Volviendo a leer los valores actuales del catálogo.";
        fields.mergeSurvivorControl.hidden = true;
        fields.mergeComparatorSummary.innerHTML = "";
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.mergeDecisionStatus.textContent = "Leyendo entradas";
        fields.mergeComparatorFeedback.textContent = "";
        fields.mergeComparatorFeedback.dataset.tone = "";
        requestMergeComparison(mergeContext.survivor_side || "left");
      }

      function renderMergeComparator() {
        if (!mergeReview) return;
        const leftTitle = mergeReview.left?.title || "Entrada A";
        const rightTitle = mergeReview.right?.title || "Entrada B";
        fields.mergeComparatorTitle.textContent = `${leftTitle} / ${rightTitle}`;
        fields.mergeComparatorSubtitle.textContent = mergeReview.can_select_survivor
          ? "Elegí qué identidad permanece y resolvé los campos señalados."
          : "La entrada del catálogo conservará su identidad.";
        fields.mergeSurvivorControl.hidden = !mergeReview.can_select_survivor;
        fields.mergeSurvivorLeft.textContent = `Conservar A · ${leftTitle}`;
        fields.mergeSurvivorRight.textContent = `Conservar B · ${rightTitle}`;
        fields.mergeSurvivorControl.querySelectorAll('input[name="merge-survivor"]').forEach((input) => {
          input.checked = input.value === mergeReview.survivor_side;
        });
        fields.mergeComparatorSummary.innerHTML = `
          ${mergeEntrySummary(mergeReview.left, "Entrada A", mergeReview.survivor_side === "left")}
          <span class="merge-summary-divider" aria-hidden="true">↔</span>
          ${mergeEntrySummary(mergeReview.right, "Entrada B", mergeReview.survivor_side === "right")}
        `;

        const visibleFields = mergeReview.fields.filter((field) => (
          fields.mergeShowAllFields.checked || field.different
        ));
        fields.mergeComparatorFields.innerHTML = mergeReview.groups
          .map((group) => {
            const rows = visibleFields.filter((field) => field.group === group.key);
            if (!rows.length) return "";
            return `<section class="merge-field-group" aria-labelledby="merge-group-${escapeAttr(group.key)}">
              <header>
                <h3 id="merge-group-${escapeAttr(group.key)}">${escapeHtml(group.label)}</h3>
                <span>${rows.length} ${rows.length === 1 ? "campo" : "campos"}</span>
              </header>
              ${rows.map(mergeFieldRow).join("")}
            </section>`;
          })
          .join("") || curationEmptyState("Las entradas coinciden", "No hay diferencias para revisar.");
        updateMergeDecisionStatus();
      }

      function mergeEntrySummary(item, label, survivor) {
        return `<article class="merge-entry-summary ${survivor ? "survivor" : ""}">
          ${curationThumb(item, true)}
          <div>
            <span>${escapeHtml(label)}${survivor ? " · permanece" : ""}</span>
            <strong>${escapeHtml(item.title || "Sin título")}</strong>
            <small>${escapeHtml([item.year, item.kind, item.source].filter(Boolean).join(" · "))}</small>
            <div class="card-badges">
              <span class="pill ${item.en_catalogo ? "good" : "muted"}">${item.en_catalogo ? "en catálogo" : "fuera de catálogo"}</span>
              <span class="pill ${item.local_files_count ? "good" : "muted"}">${item.local_files_count || 0} archivos</span>
            </div>
          </div>
        </article>`;
      }

      function mergeFieldRow(field) {
        const choice = mergeChoices[field.key] || "";
        const states = [
          { side: "left", label: "Entrada A", value: field.left },
          ...(field.allowed.includes("combine")
            ? [{ side: "combine", label: mergeCombineLabel(field), value: mergeCombinedValue(field) }]
            : []),
          { side: "right", label: "Entrada B", value: field.right }
        ].filter((state) => field.allowed.includes(state.side));
        const options = field.different
          ? states.map((state) => `
              <label class="merge-choice ${state.side}">
                <input type="radio" name="merge-field-${escapeAttr(field.key)}"
                  data-merge-choice="${escapeAttr(field.key)}" value="${state.side}"
                  ${choice === state.side ? "checked" : ""}>
                <span class="merge-choice-label">${escapeHtml(state.label)}</span>
                ${mergeValue(state.value, field)}
              </label>
            `).join("")
          : `<div class="merge-field-same">${mergeValue(field.left, field)}<span>Coinciden</span></div>`;
        return `<article class="merge-field-row ${field.required && !choice ? "needs-decision" : ""}"
          data-merge-field="${escapeAttr(field.key)}">
          <header>
            <strong>${escapeHtml(field.label)}</strong>
            <span class="merge-field-signals">
              ${field.protected ? '<span class="pill warning">protegido</span>' : ""}
              ${field.locked ? '<span class="pill muted">bloqueado</span>' : ""}
              ${field.required && !choice ? '<span class="pill warning">elegir</span>' : ""}
            </span>
          </header>
          <div class="merge-field-options ${states.length === 3 ? "three" : "two"}">${options}</div>
        </article>`;
      }

      function mergeValue(value, field) {
        if (field.strategy === "local_files") {
          const files = Array.isArray(value) ? value : [];
          if (!files.length) return '<span class="merge-value empty">Sin archivos</span>';
          return `<span class="merge-value merge-file-list">${files.map((file) => `
            <span><strong>${escapeHtml(file.name || "Archivo")}</strong><small>${escapeHtml(file.path || file.relative_path || "")}</small></span>
          `).join("")}</span>`;
        }
        if (field.strategy === "list") {
          const values = asList(value);
          return values.length
            ? `<span class="merge-value merge-list-value">${values.map((entry) => `<span>${escapeHtml(entry)}</span>`).join("")}</span>`
            : '<span class="merge-value empty">Sin datos</span>';
        }
        if (field.strategy === "boolean_or") {
          return `<span class="merge-value">${value ? "Sí" : "No"}</span>`;
        }
        if (["page_image", "backdrop_image"].includes(field.key) && value) {
          return `<span class="merge-value merge-image-value">
            <img src="${escapeAttr(cachedImageSrc(String(value)))}" alt="" loading="lazy">
            <small>${escapeHtml(urlHost(value))}</small>
          </span>`;
        }
        const text = String(value ?? "").trim();
        return `<span class="merge-value ${text ? "" : "empty"}">${escapeHtml(text || "Sin datos")}</span>`;
      }

      function mergeCombinedValue(field) {
        if (field.strategy === "list") {
          const seen = new Set();
          return [...asList(field.left), ...asList(field.right)].filter((value) => {
            const key = normalizeText(value);
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        }
        if (field.strategy === "local_files") {
          const seen = new Set();
          return [...asList(field.left), ...asList(field.right)].filter((file) => {
            const key = `${file.library_id || ""}|${file.relative_path || ""}|${file.path || ""}`.toLowerCase();
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        }
        if (field.strategy === "boolean_or") return Boolean(field.left || field.right);
        return field.left;
      }

      function mergeCombineLabel(field) {
        if (field.strategy === "boolean_or") return "Preservar sí";
        if (field.strategy === "local_files") return "Conservar todos";
        return "Combinar";
      }

      function changeMergeChoice(event) {
        const input = event.target.closest("[data-merge-choice]");
        if (!input || !mergeReview) return;
        mergeChoices[input.dataset.mergeChoice] = input.value;
        mergeTouchedChoices.add(input.dataset.mergeChoice);
        const row = fields.mergeComparatorFields.querySelector(
          `[data-merge-field="${CSS.escape(input.dataset.mergeChoice)}"]`
        );
        if (row) {
          row.classList.remove("needs-decision");
          row.querySelectorAll(".merge-field-signals .warning").forEach((badge) => {
            if (badge.textContent.trim() === "elegir") badge.remove();
          });
        }
        updateMergeDecisionStatus();
      }

      async function changeMergeSurvivor(event) {
        const input = event.target.closest('input[name="merge-survivor"]');
        if (!input || !mergeReview || input.value === mergeReview.survivor_side) return;
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.mergeDecisionStatus.textContent = "Recalculando resultado";
        await requestMergeComparison(input.value);
      }

      function updateMergeDecisionStatus() {
        if (!mergeReview) return;
        const unresolved = mergeReview.fields.filter((field) => (
          field.different
          && field.required
          && !field.allowed.includes(mergeChoices[field.key])
        ));
        const different = mergeReview.different_count || 0;
        fields.mergeDecisionStatus.textContent = unresolved.length
          ? `${unresolved.length} ${unresolved.length === 1 ? "decisión pendiente" : "decisiones pendientes"}`
          : "Resultado listo para combinar";
        fields.mergeDecisionMeta.textContent = `${different} ${different === 1 ? "diferencia" : "diferencias"} revisadas`;
        fields.confirmReviewedMerge.disabled = mergeSubmitting || unresolved.length > 0;
      }

      async function submitReviewedMerge() {
        if (!mergeReview || !mergeContext || mergeSubmitting) return;
        mergeSubmitting = true;
        updateMergeDecisionStatus();
        fields.mergeComparatorFeedback.textContent = "Guardando combinación…";
        fields.mergeComparatorFeedback.dataset.tone = "working";
        try {
          const body = {
            left: mergeContext.left,
            survivor_side: mergeReview.survivor_side,
            choices: mergeChoices,
            review_id: mergeReview.review_id,
            history_mode: curationHistoryMode
          };
          if (mergeContext.type === "internal") {
            body.right = mergeContext.right;
          } else {
            body.incoming = mergeContext.incoming || mergeContext.result;
            body.incoming_reviewed = true;
          }
          const response = await apiFetch("/api/curation/merge", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            if (response.status === 409) throw new Error("Las entradas cambiaron. Cerrá y volvé a comparar.");
            throw new Error(payload.reason || `HTTP ${response.status}`);
          }
          const externalMerge = mergeContext.type === "external";
          closeMergeComparator(true);
          selectedCurationCaseId = "";
          await loadCatalog();
          setCurationFeedback("Entradas combinadas", "success", payload.operation);
          if (externalMerge) {
            selectedExistingIdForSearch = null;
            fields.manualSearchStatus.textContent = "Combinación guardada. Deshacer está disponible en Bandeja > Actividad.";
            renderManualResults();
            renderCatalogMergeResults();
          }
        } catch (error) {
          console.error("[catalog-viewer] reviewed merge failed", error);
          fields.mergeComparatorFeedback.textContent = error.message || "No se pudo combinar.";
          fields.mergeComparatorFeedback.dataset.tone = "error";
        } finally {
          mergeSubmitting = false;
          updateMergeDecisionStatus();
        }
      }

      function closeMergeComparator(force = false) {
        if (mergeSubmitting && !force) return;
        mergeRequestSequence += 1;
        if (fields.mergeComparatorDialog.open) fields.mergeComparatorDialog.close();
        mergeReview = null;
        mergeContext = null;
        mergeChoices = {};
        mergeTouchedChoices = new Set();
        fields.mergeComparatorFeedback.textContent = "";
      }

      function mergeComparatorLoading() {
        return `<div class="merge-loading" aria-label="Cargando comparación">
          <span></span><span></span><span></span>
        </div>`;
      }

      function urlHost(value) {
        try {
          return new URL(String(value)).hostname.replace(/^www\./, "");
        } catch (_) {
          return String(value || "");
        }
      }

      function mergeFieldLabel(key) {
        return {
          title: "Título principal",
          original_title: "Título original",
          spanish_title: "Título en español",
          english_title: "Título en inglés",
          alternative_titles: "Títulos alternativos",
          kind: "Tipo de obra",
          year: "Año",
          description: "Descripción",
          wikipedia_extract: "Extracto de Wikipedia",
          genres: "Géneros",
          directors: "Dirección",
          writers: "Guion",
          cast: "Reparto",
          page_image: "Portada",
          backdrop_image: "Imagen panorámica",
          source: "Fuente principal",
          url: "URL principal",
          wikipedia_url: "Wikipedia",
          imdb_url: "IMDb",
          filmaffinity_url: "FilmAffinity",
          wikipedia_title: "Título de Wikipedia",
          wikidata_id: "Wikidata",
          tmdb_id: "TMDB",
          status: "Estado personal",
          watched_at: "Fecha de vista",
          rating: "Puntaje",
          review: "Review",
          notes: "Notas",
          tags: "Etiquetas",
          en_catalogo: "En catálogo",
          local_files: "Archivos locales"
        }[key] || key;
      }

      function openRandomDetail() {
        const candidates = randomCandidates();
        if (!candidates.length) return;
        const pool = candidates.length > 1 && selectedDetailId
          ? candidates.filter((item) => item.id !== selectedDetailId)
          : candidates;
        const item = pool[Math.floor(Math.random() * pool.length)];
        if (item) {
          openDetail(item.id, {
            context: {
              mode: "random",
              label: fields.randomCatalogOnly.checked ? "Random · Catálogo" : "Random · Todo",
              ids: candidates.map((candidate) => candidate.id)
            }
          });
        }
      }

      function randomCandidates() {
        const filtered = currentView === "catalog" ? filteredItems() : [];
        const candidates = filtered.length ? filtered : items;
        return fields.randomCatalogOnly.checked
          ? candidates.filter((item) => isInCatalog(item.en_catalogo))
          : candidates;
      }

      function syncRandomControl() {
        const count = randomCandidates().length;
        const catalogOnly = fields.randomCatalogOnly.checked;
        fields.mobileRandomCatalogOnly.checked = catalogOnly;
        fields.randomScopeLabel.textContent = catalogOnly ? "Catálogo" : "Todo";
        fields.randomButton.disabled = count === 0;
        fields.randomButton.title = count
          ? `Abrir una ficha al azar entre ${count} ${catalogOnly ? "entradas en catálogo" : "entradas"}`
          : catalogOnly ? "No hay entradas en catálogo con los filtros actuales" : "No hay entradas disponibles";
      }

      function changeRandomScope(source) {
        const catalogOnly = Boolean(source.checked);
        fields.randomCatalogOnly.checked = catalogOnly;
        fields.mobileRandomCatalogOnly.checked = catalogOnly;
        syncRandomControl();
      }

      function catalogDetailItems() {
        return applyRandomOrder(sortItems(filteredItems()));
      }

      function detailContextForTrigger(target) {
        if (target.closest("#homeGrid, #spotlightStage")) {
          return {
            mode: "home",
            label: "Inicio",
            ids: spotlightItems.map((item) => item.id)
          };
        }
        if (target.closest("#catalogMergeResults")) {
          return {
            mode: "search",
            label: "Resultados locales",
            ids: catalogMergeResults.map((item) => item.id)
          };
        }
        return {
          mode: "catalog",
          label: activeQuery ? `Colección · ${activeQuery}` : "Colección",
          ids: catalogDetailItems().map((item) => item.id)
        };
      }

      function openDetailFromTrigger(target, id) {
        openDetail(id, { context: detailContextForTrigger(target) });
      }

      function syncRoute(values = {}, method = "replace") {
        const url = new URL(window.location.href);
        for (const [key, value] of Object.entries(values)) {
          if (value) url.searchParams.set(key, value);
          else url.searchParams.delete(key);
        }
        if (Object.prototype.hasOwnProperty.call(values, "view")) url.hash = "";
        history[method === "push" ? "pushState" : "replaceState"]({}, "", url);
      }

      function collectionRouteValues() {
        return {
          q: activeQuery,
          status: fields.status.value,
          kind: fields.kind.value,
          source: fields.source.value,
          sort: fields.sort.value && fields.sort.value !== "original" ? fields.sort.value : "",
          duplicates: duplicatesOnly ? "1" : "",
          external: activeQuery && fields.externalSource.checked ? "1" : ""
        };
      }

      function routeValuesForView(view) {
        const values = { view, movie: "" };
        for (const key of COLLECTION_ROUTE_KEYS) values[key] = "";
        if (view === "catalog") Object.assign(values, collectionRouteValues());
        return values;
      }

      function syncCollectionRoute(method = "replace") {
        syncRoute(routeValuesForView("catalog"), method);
      }

      function selectRouteValue(select, value, fallback = "") {
        const available = [...select.options].some((option) => option.value === value);
        select.value = available ? value : fallback;
      }

      function applyCollectionRoute(params) {
        selectRouteValue(fields.status, params.get("status") || "");
        selectRouteValue(fields.kind, params.get("kind") || "");
        selectRouteValue(fields.source, params.get("source") || "");
        selectRouteValue(fields.sort, params.get("sort") || "original", "original");
        duplicatesOnly = params.get("duplicates") === "1";
        fields.externalSource.checked = params.get("external") === "1";
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
      }

      function restoreRoute() {
        if (!items.length) return;
        const params = new URLSearchParams(window.location.search);
        const rawQuery = params.get("q") || "";
        const movieId = params.get("movie") || "";
        const requestedView = ["home", "catalog", "inbox", "admin"].includes(params.get("view"))
          ? params.get("view")
          : rawQuery ? "catalog" : "home";
        const query = requestedView === "catalog" ? rawQuery : "";
        if (requestedView === "catalog") {
          selectedManualIndex = null;
          selectedExistingIdForSearch = null;
          catalogMergeResults = [];
          fields.catalogMergeResults.innerHTML = "";
          fields.catalogMergeSection.classList.remove("active");
          fields.reviewPrevious.hidden = true;
          fields.reviewNext.hidden = true;
          setCollectionSearchMode("browse");
          applyCollectionRoute(params);
          if (!fields.externalSource.checked) {
            manualResults = [];
            fields.manualSearchResults.innerHTML = "";
            fields.externalSearchSection.classList.remove("active");
          } else if (manualResults.length) {
            renderManualResults();
          }
        }
        if (query.length >= 2 && query !== activeQuery) {
          fields.query.value = query;
          runSearch({ updateHistory: false });
        } else if (!query && activeQuery) {
          clearManualSearch({ focus: false, updateHistory: false, resetExternal: requestedView !== "catalog" });
        } else {
          render();
          setSearchState(query.length >= 2 ? "results" : "idle", query.length >= 2 ? collectionSearchMessage() : "");
        }
        if (movieId && items.some((item) => item.id === movieId) && movieId !== selectedDetailId) {
          openDetail(movieId, { updateHistory: false });
        } else if (!movieId && selectedDetailId) {
          closeDetail({ restoreFocus: false, updateHistory: false });
        }
        showView(requestedView, { updateHistory: false, scroll: false });
        if (requestedView === "inbox") loadCurationQueue();
      }

      function seedSpotlight() {
        const catalogItems = items.filter((item) => isInCatalog(item.en_catalogo));
        const candidates = catalogItems.filter((item) => item.backdrop_image || item.page_image);
        spotlightItems = shuffle(candidates.length ? candidates : catalogItems).slice(0, 8);
        spotlightIndex = 0;
      }

      function renderSpotlight() {
        const item = spotlightItems[spotlightIndex];
        if (!item) {
          fields.spotlight.hidden = false;
          fields.spotlightStage.innerHTML = `<div class="spotlight-empty">
            <strong>Tu pantalla está lista</strong>
            <span>Marcá una película como “en catálogo” para sumarla al carrusel.</span>
          </div>`;
          syncSpotlightControl();
          return;
        }
        fields.spotlight.hidden = false;
        const title = displayTitle(item) || "Sin título";
        const realBackdrop = String(item.backdrop_image || "").trim();
        const poster = String(item.page_image || "").trim();
        const imageUrl = realBackdrop || poster;
        const image = imageUrl
          ? `<img class="spotlight-image ${realBackdrop ? "is-backdrop" : "is-poster-fallback"}" data-spotlight-image src="${escapeAttr(cachedImageSrc(imageUrl))}" alt="" decoding="async">`
          : "";
        const cover = !realBackdrop && poster
          ? `<img class="spotlight-poster" data-spotlight-image src="${escapeAttr(cachedImageSrc(poster))}" alt="" decoding="async">`
          : "";
        fields.spotlightStage.innerHTML = `<article class="spotlight-slide poster-${posterVariant(item.id || title)}">
          ${image}${cover}
          <div class="spotlight-copy">
            <span>${escapeHtml([item.year, firstListValue(item.genres)].filter(Boolean).join(" · ") || "Archivo nocturno")}</span>
            <strong>${escapeHtml(title)}</strong>
            <button class="spotlight-cta" type="button" data-click="open-detail" data-id="${escapeAttr(item.id)}">Ver ficha</button>
          </div>
          <div class="spotlight-counter" aria-hidden="true">${String(spotlightIndex + 1).padStart(2, "0")} / ${String(spotlightItems.length).padStart(2, "0")}</div>
        </article>`;
      }

      function advanceSpotlight() {
        if (spotlightPaused || spotlightDetailPaused || spotlightItems.length < 2) return;
        spotlightIndex = (spotlightIndex + 1) % spotlightItems.length;
        renderSpotlight();
      }

      function startSpotlight() {
        stopSpotlight();
        if (
          spotlightItems.length > 1
          && !spotlightPaused
          && !spotlightDetailPaused
          && !spotlightViewPaused
          && !document.hidden
          && !window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ) {
          spotlightTimer = window.setInterval(advanceSpotlight, SPOTLIGHT_INTERVAL_MS);
        }
      }

      function stopSpotlight() {
        window.clearInterval(spotlightTimer);
        spotlightTimer = null;
      }

      function syncSpotlightControl() {
        const hasItems = spotlightItems.length > 0;
        fields.spotlightToggle.disabled = spotlightDetailPaused || !hasItems;
        fields.spotlightToggle.textContent = !hasItems
          ? "Sin títulos"
          : spotlightDetailPaused
          ? "Ficha abierta"
          : spotlightPaused ? "Reanudar" : "Pausar";
        fields.spotlightToggle.setAttribute("aria-pressed", String(spotlightPaused));
      }

      function toggleSpotlight() {
        spotlightPaused = !spotlightPaused;
        syncSpotlightControl();
        if (spotlightPaused) stopSpotlight();
        else startSpotlight();
      }

      function handleVisibilityChange() {
        if (document.hidden) stopSpotlight();
        else startSpotlight();
      }

      function setupSelect(select, label, values) {
        const selected = select.value;
        const unique = [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
        select.innerHTML = `<option value="">${label}</option>` + unique.map((value) => (
          `<option value="${escapeAttr(value)}">${escapeHtml(filterValueLabel(label, value))}</option>`
        )).join("");
        select.value = unique.includes(selected) ? selected : "";
      }

      function filterValueLabel(label, value) {
        const normalized = String(value || "").toLowerCase();
        const labels = {
          watched: "Vista",
          to_watch: "Por ver",
          pelicula: "Película",
          serie: "Serie",
          anime: "Anime",
          documental: "Documental",
          local_files: "Archivos locales",
          wikipedia: "Wikipedia",
          imdb: "IMDb",
          filmaffinity: "FilmAffinity"
        };
        return labels[normalized] || String(value || label);
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

      async function runSearch({ updateHistory = true } = {}) {
        const requestedQuery = fields.query.value.trim();
        fields.collectionUtilityMenu.open = false;
        if (!requestedQuery) {
          clearManualSearch({ focus: false, updateHistory });
          return;
        }
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
        if (fields.externalSource.checked) {
          await searchManual("all");
        } else {
          setSearchState("results", collectionSearchMessage());
        }
      }

      function setSearchState(state, message = "") {
        const comparisonMode = collectionSearchMode !== "browse";
        fields.searchContext.hidden = state !== "searching" && state !== "error" && !comparisonMode;
        fields.searchContext.dataset.state = state;
        fields.searchContextText.textContent = message;
        fields.cancelSearch.hidden = state !== "searching";
        fields.clearManualSearch.hidden = state === "idle" && !comparisonMode;
        fields.backToCollection.hidden = !comparisonMode;
      }

      function setCollectionSearchMode(mode = "browse") {
        collectionSearchMode = ["browse", "compare", "link"].includes(mode) ? mode : "browse";
        const comparisonMode = collectionSearchMode !== "browse";
        fields.collectionView.classList.toggle("is-compare-mode", comparisonMode);
        fields.collectionView.dataset.searchMode = collectionSearchMode;
        fields.backToCollection.hidden = !comparisonMode;
        if (!comparisonMode) fields.catalogMergeTitle.textContent = "Entrada de la colección";
      }

      function collectionSearchMessage() {
        const count = filteredItems().length;
        const noun = count === 1 ? "título" : "títulos";
        return `${count} ${noun} en tu colección para “${activeQuery}”.`;
      }

      function comparisonSearchMessage() {
        if (collectionSearchMode === "link") {
          const selected = items.find((item) => item.id === selectedExistingIdForSearch);
          return `Buscando una referencia para “${displayTitle(selected || {}) || activeQuery}”.`;
        }
        const incoming = manualResults[selectedManualIndex] || {};
        return `Elegí la entrada local que corresponde a “${displayTitle(incoming) || activeQuery}”.`;
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

      function sortItems(list) {
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
        return sorted;
      }

      function numericYear(value) {
        const year = Number.parseInt(value || 0, 10);
        return Number.isNaN(year) ? 0 : year;
      }

      function resetCollectionFilters() {
        fields.status.value = "";
        fields.kind.value = "";
        fields.source.value = "";
        fields.sort.value = "original";
        duplicatesOnly = false;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
      }

      function clearFilters() {
        resetCollectionFilters();
        render();
        syncCollectionRoute("push");
      }

      function clearFilter(filter) {
        if (filter === "query") {
          clearManualSearch({ focus: false });
          return;
        }
        if (filter === "status" || filter === "kind" || filter === "source") {
          fields[filter].value = "";
        } else if (filter === "sort") {
          fields.sort.value = "original";
        } else if (filter === "duplicates") {
          duplicatesOnly = false;
        } else if (filter === "random") {
          randomOrder = [];
        }
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
        syncCollectionRoute("push");
      }

      function renderActiveFilters() {
        const filters = [];
        if (activeQuery) filters.push(["query", `Búsqueda: ${activeQuery}`]);
        if (fields.status.value) filters.push(["status", filterValueLabel("Estado", fields.status.value)]);
        if (fields.kind.value) filters.push(["kind", filterValueLabel("Tipo", fields.kind.value)]);
        if (fields.source.value) filters.push(["source", filterValueLabel("Fuente", fields.source.value)]);
        if (fields.sort.value && fields.sort.value !== "original") {
          filters.push(["sort", fields.sort.selectedOptions[0]?.textContent || "Orden personalizado"]);
        }
        if (duplicatesOnly) filters.push(["duplicates", "Sólo duplicadas"]);
        if (randomOrder.length) filters.push(["random", "Vista mezclada"]);
        fields.activeFilters.hidden = filters.length === 0;
        fields.activeFilters.innerHTML = filters.length
          ? `<span>Activos</span>${filters.map(([filter, label]) => (
              `<button type="button" data-click="clear-filter" data-filter="${escapeAttr(filter)}">${escapeHtml(label)} <span aria-hidden="true">×</span></button>`
            )).join("")}`
          : "";
      }

      function applyRandomOrder(list) {
        if (!randomOrder.length) return list;
        const byId = new Map(list.map((item) => [item.id, item]));
        const ordered = randomOrder.map((id) => byId.get(id)).filter(Boolean);
        const orderedIds = new Set(ordered.map((item) => item.id));
        return [...ordered, ...list.filter((item) => !orderedIds.has(item.id))];
      }

      function render() {
        const baseFiltered = sortItems(filteredItems());
        const filtered = applyRandomOrder(baseFiltered);
        const shown = filtered.slice(0, catalogVisibleCount);

        renderHeaderStats();
        fields.total.textContent = items.length;
        fields.catalogCount.textContent = items.filter((item) => isInCatalog(item.en_catalogo)).length;
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
        fields.catalogSummary.textContent = catalogSummaryText(filtered);
        fields.empty.style.display = filtered.length ? "none" : "block";
        fields.empty.textContent = activeQuery
          ? `No encontramos obras para “${activeQuery}” con los filtros actuales.`
          : "No hay obras que coincidan con los filtros actuales.";
        fields.grid.innerHTML = shown.map(card).join("");
        fields.catalogLoadMore.hidden = shown.length >= filtered.length;
        fields.catalogLoadMore.textContent = `Cargar más (${filtered.length - shown.length})`;
        renderHomeShelf();
        renderActiveFilters();
        syncRandomControl();
        renderDetail();
      }

      function renderHeaderStats() {
        const watched = items.filter((item) => item.status === "watched").length;
        const catalogued = items.filter((item) => isInCatalog(item.en_catalogo)).length;
        fields.stats.textContent = `${items.length} obras · ${watched} vistas · ${catalogued} en catálogo`;
      }

      function catalogSummaryText(filtered) {
        const count = filtered.length;
        const noun = count === 1 ? "título" : "títulos";
        if (activeQuery) return `${count} ${noun} para “${activeQuery}”`;
        const hasFilters = fields.status.value || fields.kind.value || fields.source.value || duplicatesOnly;
        if (hasFilters) return `${count} ${noun} con los filtros actuales`;
        if (randomOrder.length) return `${count} ${noun} en orden aleatorio`;
        return `${count} ${noun} en la estantería`;
      }

      function renderHomeShelf() {
        const selection = spotlightItems.slice(0, 6);
        fields.homeGrid.innerHTML = selection.map(card).join("");
        fields.homeEmpty.hidden = selection.length > 0;
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
        fields.sort.value = "original";
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }

      function toggleDuplicatesOnly() {
        duplicatesOnly = !duplicatesOnly;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
        syncCollectionRoute("push");
        goToCollection();
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
        const shownTitle = displayTitle(item);
        const title = shownTitle || "Sin título";
        const titleClass = titleSizeClass(title);
        const rating = normalizeRating(item.rating);
        const watched = item.status === "watched";
        const catalogued = isInCatalog(item.en_catalogo);
        const duplicate = Number(item._duplicate_count || 0) > 0
          ? `<span class="dvd-sticker">Duplicada +${escapeHtml(item._duplicate_count)}</span>`
          : "";
        const accessibleStatus = `${watched ? "vista" : "pendiente"}, ${catalogued ? "en catálogo" : "fuera de catálogo"}, ${rating} puntos`;
        const backMeta = [item.year, firstListValue(item.directors)].filter(Boolean).join(" · ") || "Ficha sin completar";
        return `<article class="card dvd-card" data-click="open-detail" data-id="${escapeAttr(item.id)}">
          <div class="dvd-flipper" aria-hidden="true">
            <div class="dvd-face dvd-front">
              <div class="dvd-case">
                <span class="dvd-spine"></span>
                <div class="dvd-cover">
                  ${posterArtwork(item, title)}
                  <span class="dvd-gloss"></span>
                  ${duplicate}
                  <div class="dvd-title-block">
                    <div class="dvd-title-meta">
                      <span>${escapeHtml(item.year || "Año desconocido")}</span>
                      ${rating ? `<strong>${rating}/10</strong>` : ""}
                    </div>
                    <h2 class="${titleClass}">${escapeHtml(title)}</h2>
                    <div class="dvd-front-statuses">
                      <span class="dvd-front-status ${catalogued ? "catalogued" : "muted"}">${catalogued ? "Catálogo" : "No catálogo"}</span>
                      <span class="dvd-front-status ${watched ? "watched" : "pending"}">${watched ? "Vista" : "Pendiente"}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="dvd-face dvd-back">
              <div class="dvd-case dvd-back-case">
                <span class="dvd-spine"></span>
                <div class="dvd-back-cover">
                  <div class="dvd-back-header">
                    <span>Archivo nocturno</span>
                    <h2 class="${titleClass}">${escapeHtml(title)}</h2>
                  </div>
                  <p class="dvd-back-summary">${escapeHtml(dvdBackSummary(item))}</p>
                  <p class="dvd-back-meta">${escapeHtml(backMeta)}</p>
                  <div class="dvd-back-statuses">
                    <span class="${watched ? "active" : ""}">${watched ? "✓ Vista" : "Pendiente"}</span>
                    <span class="${catalogued ? "active" : ""}">${catalogued ? "En catálogo" : "Fuera"}</span>
                    <strong>${rating ? `${rating} pts` : "0 pts · Sin puntuar"}</strong>
                  </div>
                  <span class="dvd-back-hint">Click para abrir la ficha →</span>
                  <div class="dvd-barcode"><span></span><small>${escapeHtml(String(item.id || "movie-inbox").slice(0, 18))}</small></div>
                </div>
              </div>
            </div>
          </div>
          ${openCardButton(item, title, accessibleStatus)}
        </article>`;
      }

      function openCardButton(item, title, accessibleStatus) {
        return `<button class="dvd-open-surface" type="button" data-click="open-detail" data-id="${escapeAttr(item.id)}" aria-haspopup="dialog" aria-label="Abrir ficha de ${escapeAttr(title)}: ${escapeAttr(accessibleStatus)}"></button>`;
      }

      function dvdBackSummary(item) {
        const summary = String(item.wikipedia_extract || item.description || item.notes || "Sin sinopsis disponible.").trim();
        return summary.length > 190 ? `${summary.slice(0, 187).trimEnd()}…` : summary;
      }

      function posterArtwork(item, title) {
        const variant = posterVariant(item.id || title);
        const placeholder = `<div class="dvd-placeholder poster-${variant}"${item.page_image ? " hidden" : ""}>
          <span>Movie Inbox presenta</span>
          <strong>${escapeHtml(title)}</strong>
          <small>Edición videoclub</small>
        </div>`;
        if (!item.page_image) return placeholder;
        return `<img class="dvd-cover-image" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="Portada de ${escapeAttr(title)}" loading="lazy" decoding="async">${placeholder}`;
      }

      function posterVariant(seed) {
        const value = [...String(seed || "")].reduce((total, character) => total + character.codePointAt(0), 0);
        return (value % 4) + 1;
      }

      function handlePosterError(event) {
        const spotlightImage = event.target.closest?.("[data-spotlight-image]");
        if (spotlightImage) {
          spotlightImage.hidden = true;
          spotlightImage.closest(".spotlight-slide")?.classList.add("is-image-missing");
          return;
        }
        const image = event.target.closest?.("[data-poster-image]");
        if (!image) return;
        image.hidden = true;
        const fallback = image.nextElementSibling;
        if (fallback?.matches(".dvd-placeholder, .drawer-poster-placeholder, .curation-thumb-placeholder")) {
          fallback.hidden = false;
        }
      }

      function personalRecordPanel(item) {
        if (detailPersonalEditing) return personalRecordEditor(item);
        const rating = normalizeRating(item.rating);
        const review = String(item.review || "").trim();
        return `<div class="personal-record-read">
          <div class="record-heading">
            <div>
              <span class="drawer-kicker">Memoria personal</span>
              <h3>Mi registro</h3>
            </div>
            <button class="quiet-action record-edit-action" type="button" data-click="edit-personal" data-id="${escapeAttr(item.id)}">Editar registro</button>
          </div>
          <dl class="personal-read-grid">
            <div>
              <dt>Fecha vista</dt>
              <dd>${escapeHtml(item.watched_at || "Sin fecha")}</dd>
            </div>
            <div>
              <dt>Puntuación</dt>
              <dd>${rating ? `${rating}/10` : "Sin puntuar"}</dd>
            </div>
          </dl>
          <div class="personal-review-read">
            <span>Review</span>
            <p>${escapeHtml(review || "Sin review")}</p>
          </div>
        </div>`;
      }

      function personalRecordEditor(item) {
        const rating = normalizeRating(item.rating);
        const ratingOptions = Array.from({ length: 11 }, (_, value) => (
          `<option value="${value}" ${value === rating ? "selected" : ""}>${value}</option>`
        )).join("");
        return `<div class="personal-record-editor" data-detail-form="personal" data-id="${escapeAttr(item.id)}">
          <div class="record-heading">
            <div>
              <span class="drawer-kicker">Edición</span>
              <h3>Mi registro</h3>
            </div>
            <span class="status-line" data-personal-status></span>
          </div>
          <div class="personal-grid">
            <label>
              Fecha vista
              <input name="watched_at" data-personal-watched-at type="date" value="${escapeAttr(item.watched_at || "")}">
            </label>
            <label>
              Puntaje
              <select name="rating" data-personal-rating>
                ${ratingOptions}
              </select>
            </label>
            <label class="review-field">
              Review
              <textarea name="review" data-personal-review rows="6">${escapeHtml(item.review || "")}</textarea>
            </label>
            <div class="personal-actions">
              <button type="button" data-click="save-personal" data-detail-save data-id="${escapeAttr(item.id)}">Guardar cambios</button>
              <button class="quiet-action" type="button" data-click="cancel-personal" data-id="${escapeAttr(item.id)}">Cancelar</button>
            </div>
          </div>
        </div>`;
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
        const content = rows.join("");
        return content ? `<dl class="facts">${content}</dl>` : "";
      }

      function availabilityPanel(item) {
        const localText = localFilesText(item);
        const duplicates = Number(item._duplicate_count || 0);
        return `<dl class="availability-list">
          <div><dt>En catálogo</dt><dd>${isInCatalog(item.en_catalogo) ? "Sí" : "No"}</dd></div>
          <div><dt>Archivos</dt><dd>${escapeHtml(localText || "Sin archivo asociado")}</dd></div>
          <div><dt>Fuente</dt><dd>${escapeHtml(item.source || "Sin fuente")}</dd></div>
          ${duplicates ? `<div><dt>Duplicados</dt><dd>${escapeHtml(`${duplicates} coincidencia(s): ${item._duplicate_reason || "misma obra"}`)}</dd></div>` : ""}
        </dl>`;
      }

      function openDetail(id, { updateHistory = true, context = null, skipGuard = false } = {}) {
        if (!id) return;
        if (!skipGuard && selectedDetailId && selectedDetailId !== id && hasUnsavedDetailChanges()) {
          requestDetailTransition(() => openDetail(id, { updateHistory, context, skipGuard: true }));
          return;
        }
        const activeElement = document.activeElement;
        detailReturnFocus = activeElement?.matches?.("[data-click='open-detail']")
          ? activeElement
          : activeElement?.closest?.(".dvd-card") ? activeElement : null;
        detailReturnCardId = id;
        setDetailContext(context, id);
        selectedDetailId = id;
        detailPersonalEditing = false;
        detailDirtyScopes.clear();
        spotlightDetailPaused = true;
        stopSpotlight();
        syncSpotlightControl();
        clearDetailFeedback();
        renderDetail({ force: true });
        fields.detailBody.scrollTop = 0;
        if (!fields.detailDrawer.open) fields.detailDrawer.showModal();
        document.body.classList.add("drawer-open");
        if (updateHistory) syncRoute({ movie: id }, "push");
        requestAnimationFrame(() => fields.closeDetail.focus());
      }

      function closeDetail({ restoreFocus = true, updateHistory = true, skipGuard = false } = {}) {
        if (!selectedDetailId && !fields.detailDrawer.open) return;
        if (!skipGuard && hasUnsavedDetailChanges()) {
          requestDetailTransition(() => closeDetail({ restoreFocus, updateHistory, skipGuard: true }));
          return;
        }
        selectedDetailId = "";
        if (fields.detailDrawer.open) fields.detailDrawer.close();
        fields.detailBody.innerHTML = "";
        fields.detailNavigation.innerHTML = "";
        document.body.classList.remove("drawer-open");
        detailPersonalEditing = false;
        detailDirtyScopes.clear();
        pendingDetailTransition = null;
        clearDetailFeedback();
        spotlightDetailPaused = false;
        syncSpotlightControl();
        startSpotlight();
        if (updateHistory) syncRoute({ movie: "" }, "replace");
        const currentCard = [...document.querySelectorAll(".dvd-card")]
          .find((card) => card.dataset.id === detailReturnCardId);
        const returnTarget = detailReturnFocus?.isConnected
          ? detailReturnFocus
          : currentCard?.querySelector(".dvd-open-surface");
        if (restoreFocus) returnTarget?.focus();
        detailReturnFocus = null;
        detailReturnCardId = "";
      }

      function setDetailContext(context, selectedId) {
        if (context) {
          detailNavigationMode = context.mode || "catalog";
          detailNavigationLabel = context.label || "Colección";
          detailNavigationIds = uniqueExistingIds(context.ids || []);
        } else if (!detailNavigationIds.includes(selectedId)) {
          detailNavigationMode = "catalog";
          detailNavigationLabel = activeQuery ? `Colección · ${activeQuery}` : "Colección";
          detailNavigationIds = uniqueExistingIds(catalogDetailItems().map((item) => item.id));
        }
        if (!detailNavigationIds.includes(selectedId)) detailNavigationIds.unshift(selectedId);
      }

      function uniqueExistingIds(values) {
        const valid = new Set(items.map((item) => item.id));
        return [...new Set(values)].filter((id) => valid.has(id));
      }

      function renderDetailNavigation() {
        if (!selectedDetailId) {
          fields.detailNavigation.innerHTML = "";
          return;
        }
        if (detailNavigationMode === "random") {
          fields.detailNavigation.innerHTML = `
            <span class="drawer-navigation-label">${escapeHtml(detailNavigationLabel)}</span>
            <button class="drawer-navigation-random" type="button" data-click="detail-random">Otro al azar</button>
          `;
          return;
        }
        const index = detailNavigationIds.indexOf(selectedDetailId);
        const total = detailNavigationIds.length;
        fields.detailNavigation.innerHTML = `
          <button type="button" data-click="detail-previous" aria-label="Abrir ficha anterior" ${index <= 0 ? "disabled" : ""}>← <span>Anterior</span></button>
          <span class="drawer-navigation-counter">${escapeHtml(detailNavigationLabel)} · ${Math.max(index + 1, 1)} / ${Math.max(total, 1)}</span>
          <button type="button" data-click="detail-next" aria-label="Abrir ficha siguiente" ${index < 0 || index >= total - 1 ? "disabled" : ""}><span>Siguiente</span> →</button>
        `;
      }

      function navigateDetail(offset) {
        const index = detailNavigationIds.indexOf(selectedDetailId);
        const nextId = detailNavigationIds[index + offset];
        if (!nextId) return;
        requestDetailTransition(() => showDetailFromQueue(nextId));
      }

      function showDetailFromQueue(id) {
        detailPersonalEditing = false;
        detailDirtyScopes.clear();
        selectedDetailId = id;
        detailReturnCardId = id;
        clearDetailFeedback();
        renderDetail({ force: true });
        syncRoute({ movie: id }, "replace");
        fields.detailBody.scrollTop = 0;
        requestAnimationFrame(() => fields.closeDetail.focus());
      }

      function openAnotherRandomDetail() {
        const candidates = randomCandidates().filter((item) => item.id !== selectedDetailId);
        if (!candidates.length) return;
        const item = candidates[Math.floor(Math.random() * candidates.length)];
        requestDetailTransition(() => {
          detailNavigationIds = randomCandidates().map((candidate) => candidate.id);
          detailNavigationLabel = fields.randomCatalogOnly.checked ? "Random · Catálogo" : "Random · Todo";
          showDetailFromQueue(item.id);
        });
      }

      function renderDetail({ force = false } = {}) {
        if (!selectedDetailId) return;
        if (!force && hasUnsavedDetailChanges()) {
          renderDetailNavigation();
          syncDetailFeedback();
          return;
        }
        const item = items.find((entry) => entry.id === selectedDetailId);
        if (!item) {
          closeDetail({ skipGuard: true });
          return;
        }
        const rating = normalizeRating(item.rating);
        const shownTitle = displayTitle(item);
        const title = shownTitle || "Sin título";
        const subtitle = titleSubtitle(item);
        const summary = item.wikipedia_extract || item.description || item.notes || "";
        const watched = item.status === "watched";
        const catalogued = isInCatalog(item.en_catalogo);
        const metadataSection = detailPersonalEditing ? "" : `
          <details class="drawer-accordion drawer-editor">
            <summary><span>Editar metadata</span><small>Campos, procedencia y bloqueos</small></summary>
            <div class="drawer-accordion-body">${metadataEditor(item)}</div>
          </details>
        `;
        renderDetailNavigation();
        fields.detailBody.innerHTML = `
          <section class="drawer-hero">
            ${drawerPoster(item, title)}
            <div class="drawer-intro">
              <span class="drawer-kicker">Ficha del videoclub</span>
              <h2>${escapeHtml(title)}</h2>
              ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
              <div class="drawer-byline">${[item.year, firstListValue(item.directors), listText(item.genres, 2)].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join("")}</div>
            </div>
          </section>
          <section class="drawer-quick-actions" aria-label="Estado personal">
            <button class="drawer-state ${watched ? "active" : ""}" type="button" data-click="toggle-watched" data-id="${escapeAttr(item.id)}" data-status="${escapeAttr(item.status || "to_watch")}" aria-pressed="${watched}">
              <span>Estado</span><strong>${watched ? "Vista" : "Pendiente"}</strong><small>${item.watched_at ? escapeHtml(item.watched_at) : "Sin fecha"}</small>
            </button>
            <button class="drawer-state ${catalogued ? "active" : ""}" type="button" data-click="toggle-catalog" data-id="${escapeAttr(item.id)}" aria-pressed="${catalogued}">
              <span>Mi catálogo</span><strong>${catalogued ? "Incluida" : "No incluida"}</strong><small>Cambiar estado</small>
            </button>
            <button class="drawer-state rating-state ${rating ? "active" : ""}" type="button" data-click="edit-personal" data-id="${escapeAttr(item.id)}">
              <span>Puntuación</span><strong>${rating ? `${rating}/10` : "Sin puntuar"}</strong><small>Editar registro</small>
            </button>
          </section>
          <section class="drawer-synopsis">
            <h3>Sinopsis</h3>
            <p>${escapeHtml(summary || "Todavía no hay una sinopsis disponible para esta película.")}</p>
          </section>
          <section class="drawer-section drawer-personal-section">
            ${personalRecordPanel(item)}
          </section>
          <details class="drawer-accordion">
            <summary><span>Ficha técnica</span><small>Dirección, reparto y títulos</small></summary>
            <div class="drawer-accordion-body">${factsPanel(item) || `<span class="status-line">Sin ficha enriquecida.</span>`}</div>
          </details>
          <details class="drawer-accordion">
            <summary><span>Disponibilidad y fuentes</span><small>Archivos, catálogos y enlaces</small></summary>
            <div class="drawer-accordion-body">
              ${availabilityPanel(item)}
              <div class="links">${detailLinks(item)}</div>
              <button class="drawer-secondary-action" type="button" data-click="find-link" data-id="${escapeAttr(item.id)}">Buscar o completar enlaces</button>
            </div>
          </details>
          ${metadataSection}
          <details class="drawer-accordion danger-zone">
            <summary><span>Mantenimiento</span><small>Acciones sensibles</small></summary>
            <div class="drawer-accordion-body">
              <p>Eliminar quita esta entrada del catálogo editable. No borra archivos de video.</p>
              <button class="danger" type="button" data-click="delete-item" data-id="${escapeAttr(item.id)}">Eliminar del catálogo</button>
            </div>
          </details>
        `;
        primeDetailForms();
        syncDetailFeedback();
      }

      function drawerPoster(item, title) {
        const placeholder = `<div class="drawer-poster drawer-poster-placeholder poster-${posterVariant(item.id || title)}"${item.page_image ? " hidden" : ""}><span>Movie Inbox</span><strong>${escapeHtml(title)}</strong></div>`;
        const image = item.page_image
          ? `<img class="drawer-poster" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="Portada de ${escapeAttr(title)}" decoding="async">`
          : "";
        return `<div class="drawer-poster-frame">${image}${placeholder}</div>`;
      }

      function editPersonalRecord() {
        if (!selectedDetailId || detailPersonalEditing) return;
        if (detailDirtyScopes.has("metadata")) {
          requestDetailTransition(editPersonalRecord);
          return;
        }
        detailPersonalEditing = true;
        renderDetail({ force: true });
        const editor = fields.detailBody.querySelector("[data-detail-form='personal']");
        editor?.scrollIntoView({ block: "center" });
        requestAnimationFrame(() => editor?.querySelector("[data-personal-watched-at]")?.focus());
      }

      function cancelPersonalEdit() {
        detailDirtyScopes.delete("personal");
        detailPersonalEditing = false;
        renderDetail({ force: true });
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
          ["Reparto", "cast", "text"],
          ["TMDB ID", "tmdb_id", "text"],
          ["Imagen landscape", "backdrop_image", "text"]
        ];
        return `<div class="metadata-editor" data-detail-form="metadata" data-id="${escapeAttr(item.id)}">
          ${rows.map(([label, field, control]) => metadataEditorRow(item, label, field, control)).join("")}
          <div class="metadata-actions">
            <button type="button" data-click="save-metadata" data-detail-save data-id="${escapeAttr(item.id)}">Guardar metadata</button>
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

      function primeDetailForms() {
        fields.detailBody.querySelectorAll("[data-detail-form]").forEach((form) => {
          form.dataset.initial = serializeDetailForm(form);
        });
      }

      function serializeDetailForm(form) {
        const values = [...form.querySelectorAll("input, select, textarea")].map((control, index) => {
          const key = control.dataset.metadataField
            || control.dataset.lockField
            || control.name
            || String(index);
          const value = control.type === "checkbox" ? control.checked : control.value;
          return [key, value];
        });
        return JSON.stringify(values);
      }

      function handleDetailFormMutation(event) {
        const form = event.target.closest("[data-detail-form]");
        if (!form) return;
        const scope = form.dataset.detailForm;
        if (serializeDetailForm(form) === form.dataset.initial) detailDirtyScopes.delete(scope);
        else detailDirtyScopes.add(scope);
        syncDetailFeedback();
      }

      function hasUnsavedDetailChanges() {
        return detailDirtyScopes.size > 0;
      }

      function handleBeforeUnload(event) {
        if (!hasUnsavedDetailChanges()) return;
        event.preventDefault();
        event.returnValue = "";
      }

      function setDetailFeedback(message, tone = "", timeout = 2400) {
        if (detailFeedbackTimer) window.clearTimeout(detailFeedbackTimer);
        detailFeedbackState = { message, tone };
        syncDetailFeedback();
        if (timeout > 0) {
          detailFeedbackTimer = window.setTimeout(() => {
            detailFeedbackState = { message: "", tone: "" };
            detailFeedbackTimer = null;
            syncDetailFeedback();
          }, timeout);
        }
      }

      function clearDetailFeedback() {
        if (detailFeedbackTimer) window.clearTimeout(detailFeedbackTimer);
        detailFeedbackTimer = null;
        detailFeedbackState = { message: "", tone: "" };
        syncDetailFeedback();
      }

      function syncDetailFeedback() {
        if (!fields.detailFeedback) return;
        const dirty = hasUnsavedDetailChanges();
        fields.detailFeedback.textContent = dirty
          ? `Cambios sin guardar · ${detailDirtyScopes.size}`
          : detailFeedbackState.message;
        fields.detailFeedback.dataset.tone = dirty ? "dirty" : detailFeedbackState.tone;
        fields.detailDrawer.classList.toggle("has-dirty-detail", dirty);
      }

      function requestDetailTransition(action) {
        if (!hasUnsavedDetailChanges()) {
          action();
          return;
        }
        pendingDetailTransition = action;
        if (!fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.showModal();
        requestAnimationFrame(() => fields.saveDetailChanges.focus());
      }

      function keepEditingDetail() {
        pendingDetailTransition = null;
        if (fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.close();
        if (selectedDetailId) syncRoute({ movie: selectedDetailId }, "replace");
        requestAnimationFrame(() => fields.detailBody.querySelector("[data-detail-form] input, [data-detail-form] select, [data-detail-form] textarea")?.focus());
      }

      function discardDetailChanges() {
        const transition = pendingDetailTransition;
        pendingDetailTransition = null;
        detailDirtyScopes.clear();
        detailPersonalEditing = false;
        if (fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.close();
        syncDetailFeedback();
        transition?.();
      }

      async function saveDetailChanges() {
        fields.saveDetailChanges.disabled = true;
        fields.keepEditingDetail.disabled = true;
        fields.discardDetailChanges.disabled = true;
        setDetailFeedback("Guardando cambios…", "working", 0);
        const saved = await saveDirtyDetailForms();
        fields.saveDetailChanges.disabled = false;
        fields.keepEditingDetail.disabled = false;
        fields.discardDetailChanges.disabled = false;
        if (!saved) return;
        const transition = pendingDetailTransition;
        pendingDetailTransition = null;
        if (fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.close();
        detailPersonalEditing = false;
        setDetailFeedback("Cambios guardados", "success");
        await loadCatalog();
        transition?.();
      }

      async function saveDirtyDetailForms() {
        const personal = fields.detailBody.querySelector("[data-detail-form='personal']");
        const metadata = fields.detailBody.querySelector("[data-detail-form='metadata']");
        if (detailDirtyScopes.has("personal") && !await persistPersonalForm(personal, selectedDetailId)) return false;
        detailDirtyScopes.delete("personal");
        if (detailDirtyScopes.has("metadata") && !await persistMetadataForm(metadata, selectedDetailId)) return false;
        detailDirtyScopes.delete("metadata");
        syncDetailFeedback();
        return true;
      }

      function cachedImageSrc(url) {
        return `/image-cache?url=${encodeURIComponent(url)}`;
      }

      async function searchManual(source = "all", statusPrefix = "") {
        const query = fields.query.value.trim();
        if (query.length < 2) return;
        if (externalSearchController) externalSearchController.abort();
        const controller = new AbortController();
        externalSearchController = controller;
        externalSearchTimedOut = false;
        const timeoutId = window.setTimeout(() => {
          if (externalSearchController === controller) {
            externalSearchTimedOut = true;
            controller.abort();
          }
        }, SEARCH_TIMEOUT_MS);
        manualSearchSource = source;
        manualResults = [];
        selectedManualIndex = null;
        manualVisibleCount = SEARCH_PAGE_SIZE;
        fields.externalSearchSection.classList.add("active");
        fields.manualSearchStatus.textContent = statusPrefix || "Buscando...";
        fields.manualSearchResults.innerHTML = "";
        fields.searchButton.disabled = true;
        fields.searchButton.setAttribute("aria-busy", "true");
        fields.searchConsole.setAttribute("aria-busy", "true");
        fields.searchButton.textContent = "Buscando...";
        setSearchState(
          "searching",
          collectionSearchMode === "browse"
            ? `${collectionSearchMessage()} Consultando fuentes externas…`
            : comparisonSearchMessage()
        );
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
          fields.manualSearchStatus.textContent = manualResults.length
            ? `${manualResults.length} ${manualResults.length === 1 ? "resultado" : "resultados"}${source === "wikipedia" ? " de Wikipedia" : ""}`
            : "Sin resultados";
          setSearchState(
            "results",
            collectionSearchMode === "browse" ? collectionSearchMessage() : comparisonSearchMessage()
          );
          renderManualResults();
          renderDatabaseMenu();
        } catch (error) {
          if (error.name === "AbortError" && externalSearchTimedOut) {
            fields.manualSearchStatus.textContent = "La búsqueda externa tardó demasiado. Podés reintentar.";
            setSearchState("error", `La consulta externa para “${query}” superó los 10 segundos.`);
          } else if (error.name !== "AbortError") {
            fields.manualSearchStatus.textContent = "No se pudo completar la búsqueda externa.";
            setSearchState("error", `La colección sigue disponible, pero falló la consulta externa para “${query}”.`);
            console.error("[catalog-viewer] external search failed", error);
          }
        } finally {
          window.clearTimeout(timeoutId);
          if (externalSearchController === controller) {
            externalSearchController = null;
            externalSearchTimedOut = false;
            fields.searchButton.disabled = false;
            fields.searchButton.removeAttribute("aria-busy");
            fields.searchConsole.setAttribute("aria-busy", "false");
            fields.searchButton.textContent = "Buscar";
          }
        }
      }

      function cancelExternalSearch() {
        if (!externalSearchController) return;
        externalSearchTimedOut = false;
        externalSearchController.abort();
        externalSearchController = null;
        fields.searchButton.disabled = false;
        fields.searchButton.removeAttribute("aria-busy");
        fields.searchConsole.setAttribute("aria-busy", "false");
        fields.searchButton.textContent = "Buscar";
        fields.manualSearchStatus.textContent = "Búsqueda externa cancelada.";
        setSearchState(
          "results",
          collectionSearchMode === "browse" ? collectionSearchMessage() : comparisonSearchMessage()
        );
      }

      function clearManualSearch({ focus = true, updateHistory = true, resetExternal = false } = {}) {
        const hadSearch = Boolean(activeQuery || fields.query.value.trim());
        fields.collectionUtilityMenu.open = false;
        if (externalSearchController) externalSearchController.abort();
        externalSearchController = null;
        externalSearchTimedOut = false;
        fields.searchButton.disabled = false;
        fields.searchButton.removeAttribute("aria-busy");
        fields.searchConsole.setAttribute("aria-busy", "false");
        fields.searchButton.textContent = "Buscar";
        manualResults = [];
        catalogMergeResults = [];
        selectedManualIndex = null;
        selectedExistingIdForSearch = null;
        manualSearchSource = "all";
        activeQuery = "";
        setCollectionSearchMode("browse");
        manualVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        if (resetExternal) fields.externalSource.checked = false;
        fields.query.value = "";
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        fields.catalogMergeTitle.textContent = "Entrada de la colección";
        fields.reviewPrevious.hidden = true;
        fields.reviewNext.hidden = true;
        setSearchState("idle");
        if (updateHistory && hadSearch) syncCollectionRoute("push");
        render();
        renderDatabaseMenu();
        if (focus) fields.query.focus();
      }

      function prepareManualMerge(index) {
        selectedManualIndex = index;
        if (selectedExistingIdForSearch) {
          setCollectionSearchMode("link");
          const item = items.find((entry) => entry.id === selectedExistingIdForSearch);
          catalogMergeResults = item ? [item] : [];
          catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeTitle.textContent = "Entrada seleccionada";
          fields.catalogMergeStatus.textContent = item ? "Entrada seleccionada para comparar." : "No se encontró la entrada seleccionada.";
          renderCatalogMergeResults();
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
        searchCatalogForMerge();
        setSearchState("results", comparisonSearchMessage());
        fields.searchContext.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      function searchCatalogForMerge(queryValue = "") {
        const query = (queryValue || fields.query.value).trim().toLowerCase();
        if (!query) return;
        setCollectionSearchMode("compare");
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeResults = items
          .map((item) => ({ item, score: catalogMatchScore(item, query) }))
          .filter((entry) => entry.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, 60)
          .map((entry) => entry.item);
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeTitle.textContent = selectedManualIndex === null
          ? "Coincidencias de la colección"
          : "Elegí una entrada local";
        fields.catalogMergeStatus.textContent = selectedManualIndex === null
          ? `${catalogMergeResults.length} ${catalogMergeResults.length === 1 ? "coincidencia local" : "coincidencias locales"}.`
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
          fields.reviewPrevious.hidden = true;
          fields.reviewNext.hidden = true;
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
        fields.reviewPrevious.hidden = false;
        fields.reviewNext.hidden = false;
        fields.reviewPrevious.disabled = wikiReviewIndex === 0;
        fields.reviewNext.disabled = wikiReviewIndex >= wikiReviewQueue.length - 1;
        await findLinkForItem(item);
      }

      function catalogMergeResult(item) {
        const incoming = selectedManualIndex === null ? null : manualResults[selectedManualIndex];
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || item.local_name || "";
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        return `<article class="search-result compact-result">
          ${resultMedia(shownTitle || item.local_name, item.page_image)}
          <div class="result-body">
            <h3 class="${titleSizeClass(shownTitle)}">${escapeHtml(shownTitle || "Sin titulo")}</h3>
            ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
            <div class="meta">
              ${meta(item.year)}${meta(item.kind)}${meta(item.source)}${meta(firstListValue(item.genres))}${meta(firstListValue(item.directors))}
            </div>
            <div class="card-badges">
              <span class="pill ${hasExternalLink(item) ? "good" : "muted"}">${hasExternalLink(item) ? "con link" : "sin link"}</span>
              <span class="pill ${isInCatalog(item.en_catalogo) ? "good" : "muted"}">${isInCatalog(item.en_catalogo) ? "catalogo: si" : "catalogo: no"}</span>
            </div>
            ${searchDescription(summary, "catalog", item.id)}
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
            <h3 class="${titleSizeClass(shownTitle)}">${escapeHtml(shownTitle || "Sin titulo")}</h3>
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
          reportExternalResultProblem("Ese resultado no se puede comparar porque no tiene un enlace externo reconocido.");
          return;
        }
        await openExternalMergeComparator(index, targetId);
      }

      function reportExternalResultProblem(message) {
        fields.manualSearchStatus.textContent = message;
        setSearchState("error", `${message} La colección no fue modificada.`);
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
        const title = item?.title || item?.local_name || "Sin título";
        const confirmed = confirm(`¿Eliminar "${title}" del catálogo? Esta acción modifica los datos.`);
        if (!confirmed) return;
        const button = event.target.closest("[data-click='delete-item']");
        if (button) button.disabled = true;
        setDetailFeedback("Eliminando entrada…", "working", 0);
        try {
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
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          closeDetail({ restoreFocus: false, updateHistory: true, skipGuard: true });
          await load();
        } catch (error) {
          console.error("[catalog-viewer] delete failed", error);
          setDetailFeedback("No pudimos eliminar la entrada. Reintentá.", "error", 0);
        } finally {
          if (button?.isConnected) button.disabled = false;
        }
      }

      async function toggleWatched(event, id, currentStatus) {
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

      async function toggleCatalog(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        const nextValue = !isInCatalog(item.en_catalogo);
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
          if (detailAction) setDetailFeedback(nextValue ? "Disponible en catálogo" : "Fuera de catálogo", "success");
          await load();
        } catch (error) {
          console.error("[catalog-viewer] catalog update failed", error);
          if (detailAction) setDetailFeedback("No pudimos guardar la disponibilidad. Reintentá.", "error", 0);
          else setSearchState("error", "No pudimos guardar la disponibilidad. Reintentá.");
        }
      }

      async function savePersonal(event, id) {
        event.preventDefault();
        const form = event.target.closest("[data-detail-form='personal']");
        if (!form) return;
        event.target.disabled = true;
        setDetailFeedback("Guardando registro…", "working", 0);
        const saved = await persistPersonalForm(form, id);
        event.target.disabled = false;
        if (!saved) return;
        detailDirtyScopes.delete("personal");
        detailPersonalEditing = false;
        setDetailFeedback("Registro guardado", "success");
        await load();
      }

      async function persistPersonalForm(form, id) {
        const item = items.find((entry) => entry.id === id);
        if (!item || !form) return false;
        const watchedAt = form.querySelector("[data-personal-watched-at]")?.value || "";
        const rating = normalizeRating(form.querySelector("[data-personal-rating]")?.value);
        const review = form.querySelector("[data-personal-review]")?.value || "";
        const status = form.querySelector("[data-personal-status]");
        if (status) status.textContent = "Guardando…";
        try {
          const response = await apiFetch("/api/personal", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, watched_at: watchedAt, rating, review, source_file: item?._source_file || "" })
          });
          const payload = await response.json();
          if (!payload.ok) throw new Error(payload.reason || "No se pudo guardar");
          if (status) status.textContent = "Guardado";
          form.dataset.initial = serializeDetailForm(form);
          return true;
        } catch (error) {
          console.error("[catalog-viewer] personal record update failed", error);
          if (status) status.textContent = "No se pudo guardar. Revisá los datos e intentá otra vez.";
          setDetailFeedback("Error al guardar el registro", "error", 0);
          return false;
        }
      }

      async function saveMetadata(event, id) {
        event.preventDefault();
        const editor = event.target.closest("[data-detail-form='metadata']");
        if (!editor) return;
        event.target.disabled = true;
        setDetailFeedback("Guardando metadata…", "working", 0);
        const saved = await persistMetadataForm(editor, id);
        event.target.disabled = false;
        if (!saved) return;
        detailDirtyScopes.delete("metadata");
        setDetailFeedback("Metadata guardada", "success");
        await load();
      }

      async function persistMetadataForm(editor, id) {
        const item = items.find((entry) => entry.id === id);
        if (!item || !editor) return false;
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
        try {
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
          if (!payload.ok) throw new Error(payload.reason || "No se pudo guardar");
          if (status) status.textContent = "Guardada";
          editor.dataset.initial = serializeDetailForm(editor);
          return true;
        } catch (error) {
          console.error("[catalog-viewer] metadata update failed", error);
          if (status) status.textContent = "No se pudo guardar. Revisá los campos e intentá otra vez.";
          setDetailFeedback("Error al guardar la metadata", "error", 0);
          return false;
        }
      }

      async function findLinkForCatalog(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        if (fields.detailDrawer.open) closeDetail({ restoreFocus: false, updateHistory: false, skipGuard: true });
        await findLinkForItem(item);
      }

      async function findLinkForItem(item) {
        showView("catalog", { updateHistory: false, scroll: false });
        selectedExistingIdForSearch = item.id;
        selectedManualIndex = null;
        setCollectionSearchMode("link");
        fields.query.value = [item.title || item.local_name, item.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        fields.externalSource.checked = true;
        render();
        syncCollectionRoute("push");
        catalogMergeResults = [item];
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeTitle.textContent = "Entrada seleccionada";
        fields.catalogMergeStatus.textContent = "Elegí un resultado externo y tocá Comparar para revisar diferencias.";
        renderCatalogMergeResults();
        await searchManual("all", "Buscando coincidencias en Wikipedia, IMDb y FilmAffinity...");
        fields.query.scrollIntoView({ behavior: "smooth", block: "center" });
      }

      function meta(value) {
        return value ? `<span>${escapeHtml(value)}</span>` : "";
      }

      function displayTitle(item) {
        const candidates = [
          item.spanish_title,
          item.title,
          item.original_title,
          item.english_title,
          item.wikipedia_title,
          ...asList(item.alternative_titles),
          item.local_name
        ].filter(Boolean);
        return candidates.find((value) => !isExternalIdTitle(value)) || candidates[0] || "";
      }

      function isExternalIdTitle(value) {
        const text = String(value || "").trim();
        return /^(tt|nm)\d{7,9}$/i.test(text) || /^film\d+$/i.test(text);
      }

      function titleSizeClass(value) {
        const text = String(value || "").trim();
        const length = [...text].length;
        const longestWord = Math.max(0, ...text.split(/\s+/).map((word) => [...word].length));
        if (longestWord > 18) return "title-ultra";
        if (longestWord > 12 || length > 72) return "title-xxlong";
        if (longestWord > 8 || length > 52) return "title-xlong";
        if (length > 34) return "title-long";
        if (length > 22) return "title-medium";
        return "title-short";
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
