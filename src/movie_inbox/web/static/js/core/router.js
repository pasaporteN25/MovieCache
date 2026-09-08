import { closeDetail, openDetail, selectedDetailId } from "./detail.js";
import { fields } from "./fields.js";
import { API_TOKEN, apiFetch } from "./http.js";
import { CATALOG_PAGE_SIZE, currentIdentity, currentView, inboxMode, items, setCurrentView, setInboxModeValue, setSelectedExistingIdForSearch } from "./state.js";
import { loadLibraries } from "../surfaces/admin-libraries.js";
import { loadImageCacheStatus, loadMembers, syncImageCacheStatusPolling } from "../surfaces/admin-members.js";
import { loadPublicPresentations } from "../surfaces/admin-public-presentations.js";
import { loadStreamingConfiguration } from "../surfaces/admin-streaming.js";
import { COLLECTION_MULTI_FILTER_KEYS, applyCollectionRoute, collectionRouteValues, collectionSearchMessage, render, renderHeaderStats, resetCollectionFilters, setCatalogVisibleCount, setCollectionSearchMode } from "../surfaces/catalog-grid.js";
import { activeQuery, clearManualSearch, manualResults, renderManualResults, runSearch, setCatalogMergeResults, setManualResults, setSearchState, setSelectedManualCandidate, setSelectedManualIndex, showCollectionAnchor, showFixedLocalItemForLink } from "../surfaces/catalog-search.js";
import { loadClub } from "../surfaces/club.js";
import { loadCurationQueue, setCurationFilter } from "../surfaces/inbox-curation.js";
import { loadImportDrafts } from "../surfaces/inbox-imports.js";
import { loadScannerQueue } from "../surfaces/inbox-scanner.js";

      export const COLLECTION_ROUTE_KEYS = [
        "q", ...COLLECTION_MULTI_FILTER_KEYS, "year_from", "year_to", "sort", "duplicates", "external", "mode", "link_id", "candidate_source", "candidate_ref"
      ];

      export function goHome() {
        closeDetail({ restoreFocus: false, updateHistory: false });
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true, forceModeChange: true });
        render();
        showView("home", { updateHistory: false, focus: true });
        syncRoute(routeValuesForView("home"), "push");
      }

      export function goToCollection(options = {}) {
        showView("catalog", options);
      }

      export function goToCollectionRoot() {
        resetCollectionFilters();
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true, forceModeChange: true });
        setCollectionSearchMode("browse");
        showView("catalog", { updateHistory: false, focus: true });
        syncRoute(routeValuesForView("catalog"), "push");
      }

      export function goToCollectionSearch() {
        resetCollectionFilters();
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true, forceModeChange: true });
        setCollectionSearchMode("search");
        showView("catalog", { updateHistory: false, focus: false });
        syncRoute(routeValuesForView("catalog"), "push");
        requestAnimationFrame(() => fields.query.focus());
      }

      export function goToCollectionAdd() {
        resetCollectionFilters();
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true, forceModeChange: true });
        fields.externalSource.checked = true;
        setCollectionSearchMode("add");
        showView("catalog", { updateHistory: false, focus: false });
        syncRoute(routeValuesForView("catalog"), "push");
        requestAnimationFrame(() => fields.query.focus());
      }

      export async function goToInbox(filter = "") {
        if (filter) {
          setCurationFilter(filter);
          await setInboxMode("curation", { loadData: false });
        } else {
          await setInboxMode(inboxMode, { loadData: false });
        }
        showView("inbox");
        await loadCurrentInbox();
      }

      export async function goToImports() {
        await setInboxMode("imports", { loadData: false });
        showView("inbox");
        await loadCurrentInbox();
      }

      export async function goToClub() {
        closeDetail({ restoreFocus: false, updateHistory: false });
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true, forceModeChange: true });
        showView("club");
        await loadClub();
      }

      export function goToAdmin(options = {}) {
        showView("admin", options);
        Promise.all([loadMembers(), loadLibraries(), loadImageCacheStatus(), loadPublicPresentations(), loadStreamingConfiguration()]);
      }

      export function showView(view, options = {}) {
        const updateHistory = options.updateHistory !== false;
        const scroll = options.scroll !== false;
        const focus = options.focus ?? updateHistory;
        if (view === "admin" && currentIdentity?.user?.role !== "owner") view = "home";
        setCurrentView(["home", "catalog", "inbox", "club", "admin"].includes(view) ? view : "home");
        fields.homeView.hidden = currentView !== "home";
        fields.clubView.hidden = currentView !== "club";
        fields.collectionView.hidden = currentView !== "catalog";
        fields.inboxView.hidden = currentView !== "inbox";
        fields.adminView.hidden = currentView !== "admin";
        syncImageCacheStatusPolling();
        setActiveNavigation(currentView);
        if (fields.systemMenu.open) fields.systemMenu.open = false;
        if (updateHistory) syncRoute(routeValuesForView(currentView), "push");
        renderHeaderStats();
        if (scroll) scrollPageTop();
        if (focus) requestAnimationFrame(() => focusViewHeading(currentView));
      }

      export function scrollPageTop() {
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
      }

      export function focusViewHeading(view) {
        const selector = {
          home: "#spotlightTitle",
          catalog: "#catalogTitle",
          inbox: "#inboxTitle",
          club: "#clubTitle",
          admin: "#adminTitle"
        }[view];
        if (!selector) return;
        document.querySelector(selector)?.focus({ preventScroll: true });
      }

      export function setActiveNavigation(view) {
        const buttons = {
          home: fields.homeButton,
          catalog: fields.catalogButton,
          inbox: fields.inboxButton,
          club: fields.clubButton,
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

      export function storedInboxMode() {
        try {
          const stored = localStorage.getItem("movie-inbox-inbox-mode");
          return ["curation", "imports", "scanner"].includes(stored) ? stored : "curation";
        } catch (_error) {
          return "curation";
        }
      }

      export async function changeInboxMode(event) {
        const button = event.target.closest("[data-inbox-mode]");
        if (!button) return;
        await setInboxMode(button.dataset.inboxMode || "curation");
      }

      export async function setInboxMode(mode, { loadData = true } = {}) {
        const requested = ["curation", "imports", "scanner"].includes(mode) ? mode : "curation";
        setInboxModeValue(requested === "scanner" && currentIdentity?.user?.role !== "owner" ? "curation" : requested);
        try {
          localStorage.setItem("movie-inbox-inbox-mode", inboxMode);
        } catch (_error) {
          // The mode still works when browser storage is unavailable.
        }
        const importsActive = inboxMode === "imports";
        const scannerActive = inboxMode === "scanner";
        fields.inboxView.dataset.inboxMode = inboxMode;
        fields.curationInboxPanel.hidden = importsActive || scannerActive;
        fields.scopeStrip.hidden = importsActive;
        fields.curationFeedback.hidden = importsActive;
        fields.importInboxPanel.hidden = !importsActive;
        fields.scannerInboxPanel.hidden = !scannerActive;
        fields.inboxCurationMode.classList.toggle("active", !importsActive && !scannerActive);
        fields.inboxCurationMode.setAttribute("aria-pressed", String(!importsActive && !scannerActive));
        fields.inboxImportsMode.classList.toggle("active", importsActive);
        fields.inboxImportsMode.setAttribute("aria-pressed", String(importsActive));
        fields.inboxScannerMode.classList.toggle("active", scannerActive);
        fields.inboxScannerMode.setAttribute("aria-pressed", String(scannerActive));
        if (!loadData || currentView !== "inbox") return;
        if (scannerActive) await loadScannerQueue();
        else if (importsActive) await loadImportDrafts();
        else await loadCurationQueue();
      }

      export async function loadCurrentInbox(options = {}) {
        if (inboxMode === "scanner") await loadScannerQueue(options);
        else if (inboxMode === "imports") await loadImportDrafts(options);
        else await loadCurationQueue(options);
      }

      export function syncRoute(values = {}, method = "replace", state = {}) {
        const url = new URL(window.location.href);
        for (const [key, value] of Object.entries(values)) {
          url.searchParams.delete(key);
          if (Array.isArray(value)) {
            value.filter(Boolean).forEach((entry) => url.searchParams.append(key, entry));
          } else if (value) {
            url.searchParams.set(key, value);
          }
        }
        if (Object.prototype.hasOwnProperty.call(values, "view")) url.hash = "";
        const nextState = { ...(history.state || {}), ...state };
        history[method === "push" ? "pushState" : "replaceState"](nextState, "", url);
      }

      export function routeValuesForView(view) {
        const values = { view, movie: "" };
        for (const key of COLLECTION_ROUTE_KEYS) values[key] = "";
        if (view === "catalog") Object.assign(values, collectionRouteValues());
        return values;
      }

      export function restoreRoute() {
        if (!items.length) return;
        const params = new URLSearchParams(window.location.search);
        const rawQuery = params.get("q") || "";
        const movieId = params.get("movie") || "";
        const hasCollectionRoute = COLLECTION_ROUTE_KEYS.some((key) => params.has(key));
        const requestedView = ["home", "catalog", "inbox", "club", "admin"].includes(params.get("view"))
          ? params.get("view")
          : hasCollectionRoute ? "catalog" : "home";
        const query = requestedView === "catalog" ? rawQuery : "";
        const collectionState = history.state?.collection || {};
        if (requestedView === "catalog") {
          setSelectedManualIndex(null);
          fields.reviewPrevious.hidden = true;
          fields.reviewNext.hidden = true;
          applyCollectionRoute(params);
          const mode = params.get("mode") || "";
          const linkId = params.get("link_id") || "";
          const candidateSource = params.get("candidate_source") || "";
          const candidateRef = params.get("candidate_ref") || "";
          const candidate = collectionState.candidate || null;
          const restoredMode = ["search", "add", "compare", "link"].includes(mode)
            ? mode
            : "browse";
          setCatalogVisibleCount(Number(collectionState.visibleCount) || CATALOG_PAGE_SIZE);
          const linkedItem = mode === "link" && linkId ? items.find((item) => item.id === linkId) : null;
          if (linkedItem) {
            setSelectedExistingIdForSearch(linkId);
            showFixedLocalItemForLink(linkId);
          } else if (restoredMode === "compare") {
            setSelectedExistingIdForSearch(null);
            setSelectedManualCandidate(candidateSource, candidateRef);
            if (candidate) {
              setManualResults([candidate]);
              setSelectedManualIndex(0);
              renderManualResults();
              showCollectionAnchor("compare", candidate);
            } else {
              setManualResults([]);
              setSelectedManualIndex(null);
              showCollectionAnchor("compare", {}, true);
            }
            setCollectionSearchMode("compare");
          } else {
            setSelectedExistingIdForSearch(null);
            setSelectedManualCandidate();
            setCatalogMergeResults([]);
            fields.catalogMergeResults.innerHTML = "";
            fields.catalogMergeSection.classList.remove("active");
            setCollectionSearchMode(restoredMode);
          }
          if (!fields.externalSource.checked) {
            setManualResults([]);
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
          clearManualSearch({
            focus: false,
            updateHistory: false,
            resetExternal: requestedView !== "catalog",
            forceModeChange: true
          });
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
        if (requestedView === "catalog") {
          requestAnimationFrame(() => {
            const focusTarget = collectionState.focusId
              ? document.getElementById(collectionState.focusId)
              : null;
            focusTarget?.focus({ preventScroll: true });
            if (Number.isFinite(Number(collectionState.scrollY))) {
              window.scrollTo({ top: Number(collectionState.scrollY), behavior: "auto" });
            }
          });
        }
        if (requestedView === "inbox") loadCurrentInbox();
        if (requestedView === "club") loadClub();
        if (requestedView === "admin") {
          loadMembers();
          loadPublicPresentations();
          loadStreamingConfiguration();
        }
      }
