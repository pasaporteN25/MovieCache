import { fields } from "./fields.js";
import { todayLocalDate } from "./format.js";
import { apiFetch } from "./http.js";
import { loadCurrentInbox, restoreRoute, setInboxMode } from "./router.js";
import { CATALOG_PAGE_SIZE, currentIdentity, currentView, curationCounts, inboxMode, items, privacyPreferences, routeRestored, setCurationCounts, setCurrentIdentity, setItems, setPrivacyPreferences, setRouteRestored } from "./state.js";
import { syncPrivacySummary } from "../surfaces/admin-members.js";
import { prepareCatalogViewModel, render, renderDatabaseMenu, setCatalogVisibleCount, setRandomOrder, setupCollectionFilterOptions } from "../surfaces/catalog-grid.js";
import { externalHealth, setExternalHealth } from "../surfaces/catalog-search.js";
import { editorialFeaturedCache, editorialHome, normalizeEditorialHome, rememberEditorialFeatured, setEditorialHome } from "../surfaces/home.js";
import { syncCurationCounts } from "../surfaces/inbox-curation.js";

      export let editorialRevision = 0;

      export let sourceFiles = [];

      export let writeJsonPath = "";

      export function setEditorialRevision(value) {
        editorialRevision = value;
      }

      export async function load() {
        try {
          if (!currentIdentity) await loadIdentity();
          await loadCatalog();
        } catch (error) {
          console.error("[catalog-viewer] catalog load failed", error);
          fields.homeView.setAttribute("aria-busy", "false");
          fields.empty.textContent = `No se pudo cargar el catalogo: ${error.message || error}`;
          fields.empty.hidden = false;
        }
      }

      export async function loadIdentity() {
        const response = await apiFetch("/api/session");
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        setCurrentIdentity(payload);
        const user = payload.user || {};
        const catalog = payload.catalog || {};
        const username = user.username || "Owner";
        if (user.must_change_password) {
          window.location.replace("/password-change");
          throw new Error("password_change_required");
        }
        fields.currentUserInitial.textContent = username.slice(0, 2).toUpperCase();
        fields.currentUserLabel.textContent = username;
        fields.currentUserName.textContent = username;
        fields.currentCatalogName.textContent = catalog.name || "Mi catálogo";
        fields.currentUserRole.textContent = user.role === "owner" ? "Administrador" : "Miembro";
        fields.adminButton.hidden = user.role !== "owner";
        fields.importCollectionDestination.hidden = user.role !== "owner";
        fields.inboxScannerMode.hidden = user.role !== "owner";
        if (user.role !== "owner" && inboxMode === "scanner") {
          await setInboxMode("curation", { loadData: false });
        }
      }

      export async function logout() {
        fields.logoutButton.disabled = true;
        fields.logoutButton.textContent = "Cerrando…";
        try {
          const response = await apiFetch("/auth/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}"
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          window.location.replace("/login");
        } catch (error) {
          if (error.message === "authentication_required") return;
          fields.logoutButton.disabled = false;
          fields.logoutButton.textContent = "Reintentar cierre";
        }
      }

      export async function loadCatalog() {
        fields.homeView.setAttribute("aria-busy", "true");
        const response = await apiFetch(`/api/items?home_date=${encodeURIComponent(todayLocalDate())}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        setItems(payload.items || []);
        setEditorialHome(normalizeEditorialHome(payload.home));
        editorialFeaturedCache.clear();
        rememberEditorialFeatured(editorialHome);
        prepareCatalogViewModel();
        editorialRevision += 1;
        sourceFiles = payload.sources || [];
        writeJsonPath = payload.write_json || "";
        setPrivacyPreferences({ ...privacyPreferences, ...(payload.privacy || {}) });
        syncPrivacySummary();
        setExternalHealth(payload.external || externalHealth);
        setCurationCounts({
          ...curationCounts,
          ...(payload.curation?.counts || {})
        });
        setRandomOrder([]);
        setCatalogVisibleCount(CATALOG_PAGE_SIZE);
        setupCollectionFilterOptions();
        render();
        fields.homeView.setAttribute("aria-busy", "false");
        renderDatabaseMenu();
        syncCurationCounts();
        if (currentView === "inbox") await loadCurrentInbox();
        if (!routeRestored) {
          setRouteRestored(true);
          restoreRoute();
        }
      }

