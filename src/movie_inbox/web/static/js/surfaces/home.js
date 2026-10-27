import { cachedImageSrc, posterVariant } from "../core/card.js";
import { editorialRevision, loadCatalog, setEditorialRevision } from "../core/catalog-data.js";
import { detailLinks, drawerPoster, factsPanel, openDetail } from "../core/detail.js";
import { fields } from "../core/fields.js";
import { availabilityState, displayTitle, escapeAttr, escapeHtml, firstListValue, listText, localDateOffset, todayLocalDate } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { goHome, goToClub, goToCollectionAddWithQuery, routeValuesForView, showView, syncRoute } from "../core/router.js";
import { clubMode, currentIdentity, currentView, setClubMode } from "../core/state.js";
import { applyCollectionFilterDescriptor, render, resetCollectionFilters, setLastEditorialRenderRevision } from "./catalog-grid.js";
import { clearManualSearch } from "./catalog-search.js";
import { closeSharedDetail, openCollection } from "./club.js";
import { homeRandomBay, homeRandomEntry } from "./home-random.js";
import { mountHomeSearch } from "./home-search.js";

      export let editorialHome = { generated_for: "", featured: [], hero: null, sections: [], warnings: [] };

      // Keep a bounded fallback for payloads produced by older servers that do
      // not yet expose the limits object. Current API responses carry the
      // authoritative value in payload.limits.featured_items.
      const HOME_FEATURED_FALLBACK_LIMIT = 6;

      export const editorialFeaturedCache = new Map();

      export const homeShelfSelections = new Map();
      const homeShelfSelectionKeys = new Map();

      export let playlistSource = "daily";
      export let selectedItemId = "";
      export let selectedEntryKey = "";
      // La obra consultada puede venir de un estante, del azar o del buscador.
      // Keep its source as well as its key: catalog and Club IDs can overlap.
      // "daily" (sugerencia del día), "shelf:<id>", "random" o "preview" (buscador).
      export let selectionSource = "daily";
      // Entrada que el buscador previsualiza (C3). Vive sólo mientras selectionSource === "preview".
      let previewEntry = null;
      let homeDateRequestId = 0;
      let homeDateRequestPending = false;
      let homeSummaryExpanded = false;
      const HOME_SHELF_BAY_LIMIT = 4;
      const HOME_MOBILE_MEDIA = "(max-width: 860px)";

      export let activeHomeSectionId = "";
      export let activeShelfId = "";

      export function setEditorialHome(value) {
        cancelPendingHomeDate();
        editorialHome = value;
        homeShelfSelections.clear();
        homeShelfSelectionKeys.clear();
        activeHomeSectionId = "";
        activeShelfId = "";
        playlistSource = "daily";
        selectedItemId = "";
        selectedEntryKey = "";
        selectionSource = "daily";
        previewEntry = null;
        homeSummaryExpanded = false;
        if (fields.homeSelectionAnnouncement) fields.homeSelectionAnnouncement.textContent = "";
      }

      function entryKey(entry, index = 0) {
        return String(entry?.key || entry?.item?.id || `entry-${index}`);
      }

      function entryItemId(entry) {
        return String(entry?.item?.id || "");
      }

      function rememberShelfEntry(sectionId, entries, index) {
        homeShelfSelections.set(sectionId, index);
        homeShelfSelectionKeys.set(sectionId, entryKey(entries[index], index));
      }

      function rememberedShelfIndex(sectionId, entries) {
        const key = homeShelfSelectionKeys.get(sectionId);
        const index = entries.findIndex((entry, candidateIndex) => entryKey(entry, candidateIndex) === key);
        // Removed entries resolve to the first valid work, never an unrelated
        // work that happens to have inherited the old numerical position.
        return index < 0 ? 0 : index;
      }

      function homeDurationLabel(item) {
        const value = item?.duration_minutes ?? item?.duration ?? item?.runtime ?? "";
        const text = String(value).trim();
        if (!text) return "—";
        return /\bmin(?:uto)?s?\b/i.test(text) ? text : `${text} min`;
      }

      function playlistEntries(source = playlistSource) {
        if (source === "daily" || !source) return editorialHome.featured || [];
        // Al azar y el buscador son fuentes de consulta: nunca forman una lista visible.
        if (source === "random") {
          const entry = homeRandomEntry();
          return entry ? [entry] : [];
        }
        if (source === "preview") return previewEntry ? [previewEntry] : [];
        if (source.startsWith("shelf:")) {
          const shelfId = source.slice(6);
          return editorialHome.sections.find((section, index) => homeSectionId(section, index) === shelfId)?.items || [];
        }
        return editorialHome.featured || [];
      }

      function ensureHomeSelection(entries = playlistEntries()) {
        const selected = playlistEntries(selectionSource).find((entry, index) => entryKey(entry, index) === selectedEntryKey);
        if (selected) {
          selectedItemId = entryItemId(selected);
          return selected;
        }
        // A refreshed/removed source must not leave stale actions in the console.
        selectionSource = playlistSource;
        if (!entries.length) {
          selectedEntryKey = "";
          selectedItemId = "";
          return null;
        }
        selectedEntryKey = entryKey(entries[0], 0);
        selectedItemId = entryItemId(entries[0]);
        return entries[0];
      }

      export function getHomePlaybackState() {
        return { playlistSource, selectedItemId, selectedEntryKey, selectionSource, activeShelfId };
      }

      export async function goToHomeCollection(collectionId) {
        setClubMode("collections");
        try {
          localStorage.setItem("movie-inbox-club-mode", clubMode);
        } catch (_error) {
          // Navigation still works when browser storage is unavailable.
        }
        closeSharedDetail();
        await goToClub();
        if (collectionId) await openCollection(collectionId);
      }

      export function activateHomeSection(sectionId) {
        const section = editorialHome.sections.find((entry, index) => homeSectionId(entry, index) === sectionId);
        const action = section?.action || {};
        if (action.kind === "club") {
          goToClub();
          return;
        }
        resetCollectionFilters();
        clearManualSearch({
          focus: false,
          updateHistory: false,
          resetExternal: true,
          forceModeChange: true
        });
        applyCollectionFilterDescriptor(action.filters || {});
        render();
        showView("catalog", { updateHistory: false, focus: true });
        syncRoute(routeValuesForView("catalog"), "push");
      }

      export function editorialEntryByKey(key) {
        const featured = editorialHome.featured.find((candidate) => candidate.key === key);
        if (featured) return featured;
        for (const section of editorialHome.sections) {
          const entry = (section.items || []).find((candidate) => candidate.key === key);
          if (entry) return entry;
        }
        return null;
      }

      export function openHomeCollectionDetail(key, source = "") {
        const entry = source
          ? playlistEntries(source).find((candidate, index) => entryKey(candidate, index) === key)
          : editorialEntryByKey(key);
        if (!entry || entry.origin?.kind !== "collection") return;
        const item = entry.item || {};
        const origin = entry.origin || {};
        const title = displayTitle(item) || "Sin título";
        const summary = item.wikipedia_extract || item.description || "";
        fields.sharedDetailOwner.textContent = `De ${origin.collection_title || "una colección seguida"}`;
        fields.sharedDetailBody.innerHTML = `
          <section class="drawer-hero">${drawerPoster(item, title)}<div class="drawer-intro"><span class="drawer-kicker">Ficha del Club</span><h2>${escapeHtml(title)}</h2><div class="drawer-byline">${[item.year, firstListValue(item.directors), listText(item.genres, 2)].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join("")}</div></div></section>
          <section class="home-collection-origin"><span>${escapeHtml(entry.reason?.label || "Desde una colección seguida")}</span><p>${escapeHtml(entry.reason?.detail || "Todavía no forma parte de tu catálogo personal.")}</p></section>
          <section class="drawer-synopsis"><h3>Sinopsis</h3><p>${escapeHtml(summary || "No hay una sinopsis disponible.")}</p></section>
          <details class="drawer-accordion"><summary><span>Ficha técnica</span><small>Dirección, reparto y títulos</small></summary><div class="drawer-accordion-body">${factsPanel(item) || '<span class="status-line">Sin ficha enriquecida.</span>'}</div></details>
          <div class="links shared-detail-links">${detailLinks(item)}</div>
          <div class="home-collection-detail-actions">
            <button type="button" data-click="add-home-collection-item" data-collection-id="${escapeAttr(origin.collection_id || "")}" data-id="${escapeAttr(origin.collection_item_id || "")}">Agregar a mi catálogo</button>
            <button class="quiet-action" type="button" data-click="open-home-collection" data-collection-id="${escapeAttr(origin.collection_id || "")}">Ver colección completa</button>
            <span data-home-collection-feedback role="status" aria-live="polite"></span>
          </div>`;
        fields.sharedDetailDialog.showModal();
        fields.closeSharedDetail.focus();
      }

      export async function addHomeCollectionItem(collectionId, itemId, button) {
        if (!collectionId || !itemId || button.disabled) return;
        const feedback = fields.sharedDetailBody.querySelector("[data-home-collection-feedback]");
        button.disabled = true;
        button.textContent = "Agregando…";
        if (feedback) feedback.textContent = "Comprobando coincidencias antes de guardar.";
        try {
          const response = await apiFetch(`/api/collections/${encodeURIComponent(collectionId)}/add`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ item_ids: [itemId] })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const summary = payload.summary || {};
          if (summary.added) {
            button.textContent = "Agregada";
            if (feedback) feedback.textContent = "La obra ya forma parte de tu catálogo personal.";
            await loadCatalog();
          } else if (summary.present) {
            button.textContent = "Ya estaba agregada";
            if (feedback) feedback.textContent = "Encontramos esta obra en tu catálogo.";
          } else {
            button.textContent = "Requiere revisión";
            if (feedback) feedback.textContent = "Hay una posible coincidencia. Abrí la colección para compararla antes de agregar.";
          }
        } catch (error) {
          button.disabled = false;
          button.textContent = "Reintentar agregado";
          if (feedback) feedback.textContent = "No pudimos completar la comprobación. Volvé a intentar.";
        }
      }

      export function normalizeEditorialHome(payload) {
        if (!payload || typeof payload !== "object") {
          return {
            generated_for: todayLocalDate(),
            featured: [],
            hero: null,
            sections: [],
            warnings: [],
            featured_source: ""
          };
        }
        const configuredLimit = Number(payload.limits?.featured_items);
        const featuredLimit = Number.isInteger(configuredLimit) && configuredLimit > 0
          ? configuredLimit
          : HOME_FEATURED_FALLBACK_LIMIT;
        const featured = Array.isArray(payload.featured)
          ? payload.featured.filter((entry) => entry && typeof entry === "object").slice(0, featuredLimit)
          : payload.hero && typeof payload.hero === "object" ? [payload.hero] : [];
        return {
          generated_for: String(payload.generated_for || todayLocalDate()),
          featured,
          hero: featured[0] || null,
          sections: Array.isArray(payload.sections) ? payload.sections : [],
          warnings: Array.isArray(payload.warnings) ? payload.warnings : [],
          limits: payload.limits && typeof payload.limits === "object"
            ? payload.limits
            : { featured_items: HOME_FEATURED_FALLBACK_LIMIT },
          featured_source: String(payload.featured_source || "")
        };
      }

      // Buscador de Inicio (IP2). Se monta una sola vez en #homeSearchSlot: los datos nuevos
      // sólo refrescan sus sugerencias, así que escribir o tener el foco no se interrumpe.
      let homeSearch = null;

      export function ensureHomeSearch(emptyCatalog = false) {
        if (homeSearch) {
          homeSearch.setSuggestions?.(homeSuggestions());
          homeSearch.setEmptyCatalog?.(emptyCatalog);
          return homeSearch;
        }
        const slot = fields.homeSearchSlot;
        if (!slot) return null;
        homeSearch = mountHomeSearch(slot, {
          username: currentIdentity?.user?.username || "",
          suggestions: homeSuggestions(),
          emptyCatalog,
          onPreview: previewHomeEntry,
          // C4: Ampliar abre Colección en modo Agregar con la consulta; Atrás vuelve a Inicio.
          onExpand: (query) => goToCollectionAddWithQuery(query),
          onOpenItem: (id) => openDetail(id),
          onAdded: () => { Promise.resolve(loadCatalog()).catch(() => {}); }
        }) || null;
        return homeSearch;
      }

      // `/` y «Buscar» en Inicio. Desde otra vista (o con una ficha abierta) se vuelve a
      // Inicio sin mover el foco a su título, y el foco queda en el campo.
      export function focusHomeSearch() {
        const needsHome = currentView !== "home" || fields.homeView.hidden;
        if (needsHome) goHome({ focusHeading: false });
        const search = ensureHomeSearch(!fields.homeEmpty.hidden);
        search?.focus();
        return Boolean(search);
      }

      export function renderEditorialHome() {
        renderEditorialHero();
        renderEditorialSections();
        const hasSections = editorialHome.sections.some((section) => section.items?.length);
        ensureHomeSearch(!(editorialHome.featured.length || hasSections));
        fields.homeEmpty.hidden = Boolean(editorialHome.featured.length || hasSections);
        fields.homeVideothequeHeading.hidden = !hasSections;
        fields.homeFurniture.hidden = !hasSections;
        fields.homeSections.hidden = !hasSections;
        const collectionsUnavailable = editorialHome.warnings.includes("collections_unavailable");
        const historyUnavailable = editorialHome.warnings.includes("home_history_unavailable");
        fields.homeFeedback.hidden = !(collectionsUnavailable || historyUnavailable);
        fields.homeFeedback.innerHTML = collectionsUnavailable
          ? `Las colecciones seguidas no respondieron. Tu programación personal sigue disponible. <button type="button" data-click="refresh-home">Reintentar</button>`
          : historyUnavailable
            ? `No pudimos guardar el historial de la cartelera. Las recomendaciones de hoy siguen disponibles. <button type="button" data-click="refresh-home">Reintentar</button>`
            : "";
      }

      // El mostrador es una sola pieza: el buscador (#homeSearchSlot) vive fuera de la
      // zona que se reescribe. Sólo se renderiza el póster consultado y su consola.
      function consultationHost() {
        return fields.spotlightStage.querySelector?.("#homeConsultation") || fields.spotlightStage;
      }

      export function renderEditorialHero() {
        const host = consultationHost();
        const activeElement = host.contains(document.activeElement) ? document.activeElement : null;
        const focusSurface = activeElement?.dataset?.homeFocus || "";
        if (playlistSource.startsWith("shelf:") && !homeSectionById(playlistSource.slice(6))) {
          playlistSource = "daily";
          selectionSource = "daily";
          selectedEntryKey = "";
          fields.homeSelectionAnnouncement.textContent = "El estante ya no está disponible. Volvimos a la sugerencia del día.";
        }
        const selectedEntry = ensureHomeSelection(playlistEntries());
        fields.spotlightStage.classList.toggle("is-empty", !selectedEntry?.item);
        fields.spotlightStage.querySelector?.(".spotlight-layout")?.classList.remove("home-loading-hero");
        if (!selectedEntry?.item) {
          host.innerHTML = `<div class="home-desk-note">
            <strong>La pantalla espera una obra disponible</strong>
            <span>Vinculá un archivo o declará una obra disponible para que Inicio te sugiera qué ver.</span>
          </div>`;
          return;
        }
        host.innerHTML = `${homeConsultedPoster(selectedEntry)}${homeSelectionPreview(selectedEntry)}`;
        if (activeElement && host.contains(activeElement) === false) {
          const target = focusSurface ? host.querySelector(`[data-home-focus="${CSS.escape(focusSurface)}"]`) : null;
          (target || host.querySelector('[data-home-focus="consultation-poster"]'))?.focus({ preventScroll: true });
        }
      }

      // Vuelve a la sugerencia del día y suelta cualquier selección de estante, azar o búsqueda.
      export function returnHomeProgramming(restoreFocus = false) {
        cancelPendingHomeDate();
        playlistSource = "daily";
        selectionSource = "daily";
        selectedEntryKey = "";
        selectedItemId = "";
        previewEntry = null;
        renderEditorialHero();
        renderEditorialSections();
        announceHomeSelection();
        if (restoreFocus) consultationHost().querySelector('[data-home-focus="consultation-poster"]')?.focus({ preventScroll: true });
      }

      // C3: el buscador consulta en el póster sin tocar estantes ni programación.
      // Acepta la forma editorial ({ key, item, origin }) o una plana
      // ({ id | item_id, title, year, page_image, ... }); sin id local la obra es externa.
      function normalizePreviewEntry(entry) {
        if (!entry || typeof entry !== "object") return null;
        if (entry.item && typeof entry.item === "object") {
          const id = entryItemId(entry);
          return { ...entry, key: String(entry.key || id || `preview-${displayTitle(entry.item)}`), origin: entry.origin || { kind: id ? "catalog" : "external" } };
        }
        const id = String(entry.id || entry.item_id || entry._membership?.item_id || "");
        const item = { ...entry, id, page_image: entry.page_image || entry.image || entry.poster || "" };
        const title = displayTitle(item);
        if (!title && !id) return null;
        return {
          key: String(id || `preview-${title}-${item.year || ""}`),
          item,
          origin: { kind: id ? "catalog" : "external" }
        };
      }

      export function previewHomeEntry(entry) {
        const normalized = normalizePreviewEntry(entry);
        if (!normalized) {
          // Sin búsqueda activa no hay nada que soltar: no pisa un VHS elegido a mano.
          if (selectionSource === "preview") returnHomeProgramming();
          return;
        }
        cancelPendingHomeDate();
        const leavingShelf = selectionSource !== "preview" && selectionSource !== "daily";
        previewEntry = normalized;
        selectionSource = "preview";
        selectedEntryKey = normalized.key;
        selectedItemId = entryItemId(normalized);
        // Los lomos conservan su marca sólo mientras siguen siendo la consulta.
        if (leavingShelf) renderEditorialSections();
        renderEditorialHero();
        announceHomeSelection();
      }

      // Entre 3 y 5 obras para el campo vacío: primero lo disponible del día, después lo
      // que falta de las colecciones seguidas y, si no alcanza, el resto de lo que ya llegó.
      export function homeSuggestions(limit = 5) {
        const max = Math.max(0, Math.min(5, Math.floor(Number(limit)) || 0));
        const featured = (editorialHome.featured || []).filter((entry) => entry?.item);
        const sectionEntries = (editorialHome.sections || []).flatMap((section) => (section.items || []).filter((entry) => entry?.item));
        const seen = new Set();
        const picked = [];
        const take = (entry) => {
          if (picked.length >= max) return;
          const item = entry.item;
          const identity = item.id ? `${entry.origin?.kind || "catalog"}:${item.id}` : `titulo:${displayTitle(item)}:${item.year || ""}`;
          if (seen.has(identity)) return;
          seen.add(identity);
          picked.push(entry);
        };
        featured.filter((entry) => entry.origin?.kind !== "collection" && availabilityState(entry.item).effective).forEach(take);
        [...featured, ...sectionEntries].filter((entry) => entry.origin?.kind === "collection").forEach(take);
        featured.forEach(take);
        sectionEntries.forEach(take);
        return picked;
      }

      export function selectHomeShelfEntry(sectionId, key, restoreFocus = false) {
        const section = editorialHome.sections.find((entry, index) => homeSectionId(entry, index) === sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        const index = entries.findIndex((entry, candidateIndex) => entryKey(entry, candidateIndex) === key);
        if (index < 0) return;
        cancelPendingHomeDate();
        // A deliberate VHS selection programs its editorial subset, never the
        // whole associated collection, and leaves the daily poster independent.
        activeHomeSectionId = sectionId;
        activeShelfId = sectionId;
        rememberShelfEntry(sectionId, entries, index);
        selectionSource = `shelf:${sectionId}`;
        playlistSource = selectionSource;
        selectedEntryKey = entryKey(entries[index], index);
        selectedItemId = entryItemId(entries[index]);
        renderEditorialSections();
        renderEditorialHero();
        announceHomeSelection();
        alignHomeShelf();
        if (restoreFocus) {
          const selectedSpine = fields.homeSections.querySelector(`[data-click="home-shelf-select"][data-section-id="${CSS.escape(sectionId)}"][data-entry-index="${index}"]`);
          selectedSpine?.focus({ preventScroll: true });
        }
      }

      // U8: the random VHS consults its result; the table keeps its own source.
      export function selectHomeRandomResult(entry) {
        if (!entry?.item) return;
        cancelPendingHomeDate();
        selectionSource = "random";
        selectedEntryKey = entry.key;
        selectedItemId = entryItemId(entry);
        renderEditorialSections();
        renderEditorialHero();
      }

      export function moveHomeShelf(event) {
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        const control = event.target.closest("[data-click='home-shelf-select']");
        if (!control) return;
        const sectionId = control.dataset.sectionId || "";
        const section = editorialHome.sections.find((entry, index) => homeSectionId(entry, index) === sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        if (!entries.length) return;
        const offsets = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
        let nextIndex = Number(control.dataset.entryIndex || 0);
        if (event.key === "Home") nextIndex = 0;
        else if (event.key === "End") nextIndex = entries.length - 1;
        else if (event.key in offsets) nextIndex = (nextIndex + offsets[event.key] + entries.length) % entries.length;
        else return;
        event.preventDefault();
        selectHomeShelfEntry(sectionId, entryKey(entries[nextIndex], nextIndex), true);
      }

      export function nonEmptyHomeSections() {
        return editorialHome.sections.filter((section) => Array.isArray(section.items) && section.items.length);
      }

      export function homeSectionId(section, sectionIndex) {
        return String(section.id || `editorial-${sectionIndex}`);
      }

      export function renderEditorialSections() {
        const previousFocus = fields.homeSections.contains(document.activeElement) ? document.activeElement : null;
        const sections = nonEmptyHomeSections().slice(0, HOME_SHELF_BAY_LIMIT);
        const ids = sections.map((section, index) => homeSectionId(section, index));
        if (!ids.includes(activeHomeSectionId)) {
          activeHomeSectionId = ids[0] || "";
          activeShelfId = activeHomeSectionId;
        }
        fields.homeShelfCategories.innerHTML = ids.length > 1 ? homeFurnitureControls(ids.length) : "";
        fields.homeShelfCategories.hidden = ids.length <= 1;
        fields.homeSections.setAttribute("role", "region");
        fields.homeSections.setAttribute("aria-labelledby", "homeVideothequeTitle");
        fields.homeSections.removeAttribute("aria-label");
        fields.homeSections.setAttribute("tabindex", ids.length ? "0" : "-1");
        fields.homeSections.dataset.bayCount = String(ids.length);
        fields.homeSections.innerHTML = sections
          .map((section, sectionIndex) => editorialSection(section, sectionIndex, ids[sectionIndex] === activeHomeSectionId))
          .join("") + (ids.length ? homeRandomBay(selectionSource === "random") || "" : "");
        if (previousFocus && previousFocus !== fields.homeSections && !previousFocus.isConnected) {
          const randomSpine = previousFocus.matches?.(".home-random-tape, [data-home-random] button")
            ? fields.homeSections.querySelector(".home-random-tape") : null;
          const sectionId = previousFocus.dataset?.sectionId;
          const key = previousFocus.dataset?.entryKey;
          const sameSpine = key && fields.homeSections.querySelector(`[data-section-id="${CSS.escape(sectionId || "")}"][data-entry-key="${CSS.escape(key)}"]`);
          const plaque = sectionId && fields.homeSections.querySelector(`[data-click="home-shelf-activate"][data-section-id="${CSS.escape(sectionId)}"]`);
          if (randomSpine || sameSpine || plaque) (randomSpine || sameSpine || plaque).focus({ preventScroll: true });
          else if (ids.length) fields.homeSections.focus({ preventScroll: true });
          else fields.spotlightStage.querySelector?.('[data-home-focus="consultation-poster"]')?.focus({ preventScroll: true });
        }
        syncHomeFurnitureControls();
        requestAnimationFrame(syncHomeFurnitureControls);
      }

      export function homeFurnitureControls(count) {
        return `<div class="home-shelf-navigation" role="group" aria-label="Recorrido del mueble">
          <span class="home-shelf-navigation-label">${count} categorías · recorrido lateral</span>
          <button class="home-shelf-scroll-control" type="button" data-click="home-shelf-scroll" data-direction="prev" aria-label="Mostrar categoría anterior">←</button>
          <button class="home-shelf-scroll-control" type="button" data-click="home-shelf-scroll" data-direction="next" aria-label="Mostrar categoría siguiente">→</button>
        </div>`;
      }

      export function syncHomeFurnitureControls() {
        const rail = homeShelfRail();
        const navigation = fields.homeShelfCategories;
        if (!rail || !navigation) return;
        const count = Number(rail.dataset.bayCount || 0);
        const maxScroll = Math.max(0, rail.scrollWidth - rail.clientWidth);
        const hasOverflow = count > 1 && maxScroll > 1;
        navigation.hidden = !hasOverflow;
        navigation.dataset.overflow = String(hasOverflow);
        const previous = navigation.querySelector('[data-direction="prev"]');
        const next = navigation.querySelector('[data-direction="next"]');
        if (previous) previous.disabled = !hasOverflow || rail.scrollLeft <= 1;
        if (next) next.disabled = !hasOverflow || rail.scrollLeft >= maxScroll - 1;
      }

      function homeSectionById(sectionId) {
        return editorialHome.sections.find((section, index) => homeSectionId(section, index) === sectionId) || null;
      }

      export function activateHomeShelf(sectionId, restoreFocus = false) {
        cancelPendingHomeDate();
        const section = homeSectionById(sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        if (!section || !entries.length) return false;
        const index = rememberedShelfIndex(sectionId, entries);
        const entry = entries[index];
        activeHomeSectionId = sectionId;
        activeShelfId = sectionId;
        playlistSource = `shelf:${sectionId}`;
        selectionSource = playlistSource;
        selectedEntryKey = entryKey(entry, index);
        selectedItemId = entryItemId(entry);
        rememberShelfEntry(sectionId, entries, index);
        renderEditorialSections();
        renderEditorialHero();
        alignHomeShelf();
        if (restoreFocus) fields.homeSections.querySelector(`[data-click="home-shelf-activate"][data-section-id="${CSS.escape(sectionId)}"]`)?.focus({ preventScroll: true });
        announceHomeSelection();
        return true;
      }

      export function moveHomeShelfBay(event) {
        const bay = event.target.closest(".home-shelf-bay");
        if (!bay || event.target !== bay || !["Enter", " "].includes(event.key)) return;
        event.preventDefault();
        activateHomeShelf(bay.dataset.homeSection || "", true);
      }

      function alignHomeShelf({ focusSpine = false, focusBay = false } = {}) {
        const key = selectedEntryKey;
        if (!key) return;
        const shelfId = selectionSource.startsWith("shelf:") ? selectionSource.slice(6) : "";
        const spine = shelfId ? fields.homeSections?.querySelector(`[data-click="home-shelf-select"][data-section-id="${CSS.escape(shelfId)}"][data-entry-key="${CSS.escape(key)}"]`) : null;
        const bay = spine?.closest(".home-shelf-bay");
        // Sólo se desplaza el estante local. scrollIntoView también movería el documento
        // y alejaría el lomo enfocado.
        const rail = typeof window !== "undefined" && window.matchMedia?.(HOME_MOBILE_MEDIA).matches
          ? spine?.closest(".home-shelf-rail") : fields.homeSections;
        if (spine && rail?.getBoundingClientRect) {
          const bounds = rail.getBoundingClientRect(), item = spine.getBoundingClientRect();
          if (item.left < bounds.left) rail.scrollLeft += item.left - bounds.left;
          else if (item.right > bounds.right) rail.scrollLeft += item.right - bounds.right;
        }
        if (focusSpine) spine?.focus({ preventScroll: true });
        else if (focusBay) bay?.focus({ preventScroll: true });
      }

      export function handleHomeResize() {
        syncHomeFurnitureControls();
        if (document.activeElement?.matches?.('[data-click="home-shelf-select"]')) {
          alignHomeShelf();
        }
      }

      export function homeCategorySelector(sections, ids) {
        return `<div class="home-shelf-category-options" role="group" aria-label="Categorías de estanterías">
          ${sections.map((section, index) => {
            const id = ids[index];
            const active = id === activeHomeSectionId;
            return `<button class="home-shelf-category" type="button" aria-pressed="${active}" tabindex="${active ? "0" : "-1"}" data-click="home-category-select" data-section-id="${escapeAttr(id)}">${escapeHtml(section.title || "Selección")}</button>`;
          }).join("")}
        </div>`;
      }

      export function selectHomeCategory(sectionId, restoreFocus = false) {
        const ids = nonEmptyHomeSections().map((section, index) => homeSectionId(section, index));
        if (!ids.includes(sectionId)) return;
        activeHomeSectionId = sectionId;
        activeShelfId = sectionId;
        playlistSource = `shelf:${sectionId}`;
        selectionSource = playlistSource;
        const section = nonEmptyHomeSections().find((candidate, index) => homeSectionId(candidate, index) === sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        if (!entries.some((entry, index) => entryKey(entry, index) === selectedEntryKey)) {
          const first = entries[0];
          selectedEntryKey = first ? entryKey(first, 0) : "";
          selectedItemId = first ? entryItemId(first) : "";
        }
        renderEditorialSections();
        renderEditorialHero();
        if (restoreFocus) {
          fields.homeShelfCategories.querySelector(`[data-click="home-category-select"][data-section-id="${CSS.escape(sectionId)}"]`)?.focus();
        }
      }

      export function moveHomeCategorySelector(event) {
        if (!event.target.closest("[data-click='home-category-select']")) return;
        const ids = nonEmptyHomeSections().map((section, index) => homeSectionId(section, index));
        if (!ids.length) return;
        const offsets = { ArrowRight: 1, ArrowLeft: -1 };
        const currentIndex = Math.max(0, ids.indexOf(activeHomeSectionId));
        if (event.key === "Home") {
          event.preventDefault();
          selectHomeCategory(ids[0], true);
          return;
        }
        if (event.key === "End") {
          event.preventDefault();
          selectHomeCategory(ids[ids.length - 1], true);
          return;
        }
        if (!(event.key in offsets)) return;
        event.preventDefault();
        selectHomeCategory(ids[(currentIndex + offsets[event.key] + ids.length) % ids.length], true);
      }

      export function editorialSection(section, sectionIndex, active) {
        const entries = Array.isArray(section.items) ? section.items : [];
        const sectionId = homeSectionId(section, sectionIndex);
        const countLabel = `${entries.length} ${entries.length === 1 ? "título" : "títulos"}`;
        // El estante conserva su propia selección, independiente del póster consultado.
        const selectedIndex = rememberedShelfIndex(sectionId, entries);
        return `<section class="home-program home-shelf-bay" data-home-section="${escapeAttr(sectionId)}" data-bay-index="${sectionIndex}" data-active="${active}" aria-labelledby="home-section-${escapeAttr(sectionId)}">
          <h2 id="home-section-${escapeAttr(sectionId)}" class="home-shelf-heading"><button type="button" class="sr-only home-shelf-bay-plaque" data-click="home-shelf-activate" data-section-id="${escapeAttr(sectionId)}" aria-pressed="${playlistSource === `shelf:${sectionId}`}" title="${escapeAttr(section.title || "Selección")}"><span>${escapeHtml(section.title || "Selección")}</span><small>${escapeHtml(countLabel)}</small></button></h2>
          <div class="home-shelf-rail" role="group" aria-label="Opciones de ${escapeAttr(section.title || "la estantería")}">
            ${entries.map((entry, index) => homeShelfTape(entry, index, sectionId, selectionSource === `shelf:${sectionId}` && entryKey(entry, index) === selectedEntryKey, index === selectedIndex)).join("")}
          </div>
        </section>`;
      }

      function homeShelfRail() {
        return fields.homeSections;
      }

      function homeFurnitureScrollBehavior() {
        return typeof window !== "undefined"
          && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth";
      }

      export function scrollHomeFurniture(direction = "next") {
        const rail = homeShelfRail();
        if (!rail || rail.scrollWidth <= rail.clientWidth) return false;
        const amount = Math.max(240, Math.round(rail.clientWidth * 0.72));
        rail.scrollBy({ left: direction === "prev" ? -amount : amount, behavior: homeFurnitureScrollBehavior() });
        return true;
      }

      export function moveHomeFurniture(event) {
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        if (
          !event.target.closest("#homeSections")
          || event.target.closest("[data-click='home-shelf-select']")
        ) return;
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const rail = homeShelfRail();
        const amount = Math.max(240, Math.round(rail.clientWidth * 0.72));
        const target = event.key === "Home"
          ? 0
          : event.key === "End"
            ? rail.scrollWidth
            : rail.scrollLeft + (event.key === "ArrowLeft" ? -amount : amount);
        rail.scrollTo({ left: target, behavior: homeFurnitureScrollBehavior() });
      }

      export function handleHomeFurnitureWheel(event) {
        const rail = homeShelfRail();
        if (
          !rail
          || !event.target.closest("#homeSections")
          || rail.scrollWidth <= rail.clientWidth
        ) return;
        const delta = Math.abs(event.deltaX) >= Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
        if (!delta) return;
        event.preventDefault();
        rail.scrollBy({ left: delta, behavior: "auto" });
      }

      export function homeShelfTape(entry, index, sectionId, selected, tabbable = selected) {
        const item = entry?.item || {};
        const title = displayTitle(item) || `Obra ${index + 1}`;
        const year = String(item.year || "S/A");
        const kind = String(item.kind || "obra");
        const titleLength = Array.from(title).length;
        const titleLengthClass = titleLength <= 22 ? "short" : titleLength <= 36 ? "long" : "xlong";
        const reason = entry?.reason?.label || "Selección del archivo";
        return `<button class="home-shelf-tape vhs-spine" type="button" data-vhs-state="${selected ? "selected" : "closed"}" data-title-length="${titleLengthClass}" title="${escapeAttr(title)}" aria-pressed="${selected}" tabindex="${tabbable ? "0" : "-1"}" data-click="home-shelf-select" data-section-id="${escapeAttr(sectionId)}" data-entry-index="${index}" data-entry-key="${escapeAttr(entryKey(entry, index))}" aria-label="${escapeAttr(`${title}. ${year}. Tipo: ${kind}. ${reason}. Opción ${index + 1}`)}">
          <span class="vhs-spine-sticker" aria-hidden="true"></span>
          <span class="vhs-spine-title">${escapeHtml(title)}</span>
          <span class="vhs-spine-meta" aria-hidden="true"><span class="vhs-spine-year">${escapeHtml(year)}</span><span class="vhs-spine-format">VHS</span></span>
        </button>`;
      }

      // Una obra externa (sin id local) se previsualiza pero no tiene ficha que abrir.
      function homeEntryIsExternal(entry) {
        return entry?.origin?.kind === "external";
      }

      function homeConsultationAction(entry) {
        return entry.origin?.kind === "collection"
          ? `data-click="open-home-collection-detail" data-key="${escapeAttr(selectedEntryKey)}" data-source="${escapeAttr(selectionSource)}"`
          : `data-click="open-detail-with-case-transition" data-id="${escapeAttr(entry.item.id || "")}"`;
      }

      function homePosterHeading() {
        return selectionSource === "daily" ? "Sugerencia" : selectionSource === "preview" ? "Resultado" : "Tu selección";
      }

      export function homeConsultedPoster(entry) {
        if (!entry?.item) return "";
        const title = displayTitle(entry.item) || "Sin título";
        const url = String(entry.item.page_image || "").trim();
        const fallback = `<span class="spotlight-poster-fallback"${url ? " hidden" : ""}><span>${escapeHtml(title)}<small>Sin portada</small></span></span>`;
        const picture = `${url ? `<img class="spotlight-poster" data-spotlight-image src="${escapeAttr(cachedImageSrc(url))}" alt="Portada de ${escapeAttr(title)}" loading="eager" decoding="async">` : ""}${fallback}`;
        const frame = homeEntryIsExternal(entry)
          ? `<div class="spotlight-poster-trigger is-static" data-home-focus="consultation-poster">${picture}</div>`
          : `<button type="button" class="spotlight-poster-trigger" data-home-focus="consultation-poster" ${homeConsultationAction(entry)} aria-label="Ver ficha de ${escapeAttr(title)}">${picture}</button>`;
        return `<aside class="spotlight-selector home-consulted-poster" aria-label="Póster de la obra consultada" data-consulted-key="${escapeAttr(selectedEntryKey)}" data-consulted-source="${escapeAttr(selectionSource)}">
          <div class="spotlight-selector-heading"><span>${homePosterHeading()}</span></div>
          <div class="spotlight-poster-card">${frame}</div>
        </aside>`;
      }

      function homeFurnitureFact(label, value) {
        return `<div><dt>${escapeHtml(label)}</dt><dd title="${escapeAttr(value)}">${escapeHtml(value)}</dd></div>`;
      }

      // El resumen se abre sin reconstruir la cartelera ni mover el foco.
      // Su estado pertenece a la consulta, no a una película en particular.
      export function toggleHomeSummary() {
        const preview = fields.spotlightStage.querySelector(".spotlight-preview");
        const toggle = preview?.querySelector('[data-click="home-summary-toggle"]');
        const body = preview?.querySelector("#homeSelectionSummary");
        if (!toggle || !body) return;
        homeSummaryExpanded = !homeSummaryExpanded;
        preview.dataset.summaryOpen = String(homeSummaryExpanded);
        toggle.setAttribute("aria-expanded", String(homeSummaryExpanded));
        body.setAttribute("aria-hidden", String(!homeSummaryExpanded));
        body.inert = !homeSummaryExpanded;
      }

      // La barra mantiene identidad, estados y acceso a la ficha siempre visibles.
      // Sinopsis, créditos y edición se consultan en el despliegue, sin repetir imágenes.
      export function homeSelectionPreview(entry) {
        if (!entry?.item) return "";
        const item = entry.item;
        const origin = entry.origin || {};
        const sectionId = selectionSource.startsWith("shelf:") ? selectionSource.slice(6) : "";
        const section = sectionId ? homeSectionById(sectionId) : null;
        const title = displayTitle(item) || "Sin título";
        const summary = String(item.description || item.wikipedia_extract || "").trim();
        const external = homeEntryIsExternal(entry);
        const contextLabel = origin.kind === "collection"
          ? `En ${origin.collection_title || "una colección seguida"}`
          : external ? "Resultado de búsqueda"
          : selectionSource === "preview" ? "Resultado de tu archivo"
          : selectionSource === "random" ? "Al azar" : section?.title || "Sugerencia del día";
        const categoryAction = section?.action?.kind
          ? `<button class="home-furniture-category-action" type="button" data-click="home-section-action" data-section-id="${escapeAttr(sectionId)}">${escapeHtml(section.action.label || "Ver colección")}</button>`
          : "";
        const duration = homeDurationLabel(item);
        const metadata = [item.year, item.kind, firstListValue(item.genres), duration === "—" ? "" : duration]
          .filter(Boolean).join(" · ") || "Ficha por completar";
        const credits = [["Dirección", listText(item.directors, 2)], ["Guion", listText(item.writers, 2)], ["Reparto", listText(item.cast, 3)]]
          .filter(([, value]) => value);
        const available = availabilityState(item).effective;
        const watched = item.status === "watched";
        const viewAction = external ? "" : `<button class="spotlight-preview-action" type="button" data-home-focus="consultation-view" ${homeConsultationAction(entry)}>${origin.kind === "collection" ? "Ver ficha del Club" : "Abrir ficha"}<span aria-hidden="true">→</span></button>`;
        const editAction = origin.kind === "catalog"
          ? `<button class="home-console-edit" type="button" data-home-focus="consultation-edit" data-click="edit-home-shelf-entry" data-id="${escapeAttr(item.id || "")}">Editar mi ficha</button>` : "";
        return `<aside class="spotlight-preview" aria-labelledby="spotlight-selected-title" data-summary-open="${homeSummaryExpanded}" data-selection-source="${escapeAttr(selectionSource)}" data-selected-entry-key="${escapeAttr(selectedEntryKey)}" data-selected-item-id="${escapeAttr(selectedItemId)}">
          <div class="home-console-header">
            <div class="spotlight-copy">
              <h3 id="spotlight-selected-title">${escapeHtml(title)}</h3>
              <div class="home-console-meta">
                <span class="spotlight-metadata">${escapeHtml(metadata)}</span>
                ${external ? "" : `<dl class="spotlight-preview-facts" aria-label="Estado resumido">
                  <div data-fact="access" data-state="${available ? "on" : "off"}"><dt>Acceso</dt><dd>${available ? "Disponible" : "No disponible"}</dd></div>
                  <div data-fact="status" data-state="${watched ? "on" : "off"}"><dt>Estado</dt><dd>${watched ? "Vista" : "Pendiente"}</dd></div>
                </dl>`}
              </div>
            </div>
            <div class="spotlight-preview-actions">
              <button class="home-console-toggle" type="button" data-click="home-summary-toggle" data-home-focus="consultation-summary" aria-expanded="${homeSummaryExpanded}" aria-controls="homeSelectionSummary">Resumen<svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><path d="m3 6 5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></button>
              ${viewAction}
            </div>
          </div>
          <div id="homeSelectionSummary" class="home-console-disclosure" aria-hidden="${!homeSummaryExpanded}"${homeSummaryExpanded ? "" : " inert"}>
            <div class="home-console-disclosure-clip">
              <div class="home-console-body">
                <section class="spotlight-copy home-console-synopsis" aria-label="Sinopsis">
                  <span class="home-console-label">Sinopsis</span>
                  <p>${escapeHtml(summary || "Todavía no hay una sinopsis para esta obra.")}</p>
                  <div class="home-console-heading"><strong>${escapeHtml(contextLabel)}</strong>${categoryAction}</div>
                </section>
                ${credits.length || editAction ? `<section class="home-console-details" aria-label="Créditos y edición">
                  ${credits.length ? `<dl class="home-furniture-credits">${credits.map(([label, value]) => homeFurnitureFact(label, value)).join("")}</dl>` : ""}
                  ${editAction}
                </section>` : ""}
              </div>
            </div>
          </div>
        </aside>`;
      }

      function announceHomeSelection() {
        const entry = ensureHomeSelection();
        const announcement = entry
          ? `Consulta: ${displayTitle(entry.item) || "Sin título"}` : "Sin obra seleccionada";
        if (fields.homeSelectionAnnouncement && fields.homeSelectionAnnouncement.textContent !== announcement) {
          fields.homeSelectionAnnouncement.textContent = announcement;
        }
      }

      export function editorialPersonalIds() {
        const ids = [];
        for (const entry of editorialHome.featured) {
          if (entry.origin?.kind === "catalog" && entry.item?.id) ids.push(entry.item.id);
        }
        for (const section of editorialHome.sections) {
          for (const entry of section.items || []) {
            if (entry.origin?.kind === "catalog" && entry.item?.id) ids.push(entry.item.id);
          }
        }
        const randomEntry = homeRandomEntry();
        if (randomEntry?.item?.id) ids.push(randomEntry.item.id);
        return [...new Set(ids)];
      }

      export function homeDateLabel(value) {
        const parsed = new Date(`${value || todayLocalDate()}T12:00:00`);
        if (Number.isNaN(parsed.getTime())) return "Hoy";
        const label = new Intl.DateTimeFormat("es-AR", {
          weekday: "long",
          day: "numeric",
          month: "long"
        }).format(parsed);
        const prefix = value === localDateOffset(-1)
          ? "Ayer"
          : value === todayLocalDate() ? "Hoy" : "Archivo";
        return `${prefix} · ${label}`;
      }

      export function homeDatePeriodLabel(value) {
        if (value === localDateOffset(-1)) return "Ayer";
        if (!value || value === todayLocalDate()) return "Hoy";
        return "Archivo";
      }

      export function rememberEditorialFeatured(payload) {
        const date = String(payload?.generated_for || "");
        if (!date) return;
        editorialFeaturedCache.set(date, {
          featured: Array.isArray(payload.featured) ? payload.featured : [],
          featured_source: String(payload.featured_source || "")
        });
      }

      // A newer explicit navigation wins over an in-flight day lookup. The
      // request may finish, but must not replace its selection or error state.
      function cancelPendingHomeDate() {
        homeDateRequestId += 1;
        if (!homeDateRequestPending) return;
        homeDateRequestPending = false;
        fields.spotlight.setAttribute("aria-busy", "false");
        fields.homeFeedback.hidden = true;
        fields.homeFeedback.textContent = "";
      }

      export function applyEditorialFeaturedDate(localDate, snapshot) {
        const featured = Array.isArray(snapshot.featured) ? snapshot.featured : [];
        editorialHome = {
          ...editorialHome,
          generated_for: localDate,
          featured,
          hero: featured[0] || null,
          featured_source: String(snapshot.featured_source || "")
        };
        playlistSource = "daily";
        selectionSource = "daily";
        selectedEntryKey = "";
        selectedItemId = "";
        previewEntry = null;
        renderEditorialSections();
        renderEditorialHero();
        announceHomeSelection();
      }

      export async function loadEditorialFeaturedDate(localDate, options = {}) {
        const requestedDate = String(localDate || "");
        if (!requestedDate) return;
        cancelPendingHomeDate();
        const requestId = homeDateRequestId;
        if (requestedDate === editorialHome.generated_for && !options.force) {
          returnHomeProgramming(true);
          return;
        }
        const cached = !options.force ? editorialFeaturedCache.get(requestedDate) : null;
        if (cached) {
          applyEditorialFeaturedDate(requestedDate, cached);
          fields.homeFeedback.hidden = true;
          fields.homeFeedback.textContent = "";
          return;
        }
        const isYesterday = requestedDate === localDateOffset(-1);
        homeDateRequestPending = true;
        fields.spotlight.setAttribute("aria-busy", "true");
        fields.homeFeedback.hidden = false;
        fields.homeFeedback.textContent = isYesterday
          ? "Recuperando las recomendaciones guardadas de ayer…"
          : "Actualizando las recomendaciones de hoy…";
        try {
          const snapshotQuery = isYesterday ? "&saved_featured=true" : "";
          const response = await apiFetch(`/api/home?date=${encodeURIComponent(requestedDate)}${snapshotQuery}`);
          const payload = await response.json();
          if (requestId !== homeDateRequestId) return;
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const normalized = normalizeEditorialHome(payload);
          rememberEditorialFeatured(normalized);
          applyEditorialFeaturedDate(requestedDate, normalized);
          fields.homeFeedback.hidden = true;
          fields.homeFeedback.textContent = "";
        } catch (error) {
          if (requestId !== homeDateRequestId) return;
          const retryAction = isYesterday ? "home-date-yesterday" : "home-date-today";
          fields.homeFeedback.hidden = false;
          fields.homeFeedback.innerHTML = `No pudimos recuperar esas recomendaciones. <button type="button" data-click="${retryAction}">Reintentar</button>`;
        } finally {
          if (requestId === homeDateRequestId) {
            homeDateRequestPending = false;
            fields.spotlight.setAttribute("aria-busy", "false");
          }
        }
      }

      export async function refreshEditorialHome() {
        const requestedDate = editorialHome.generated_for || todayLocalDate();
        if (requestedDate !== todayLocalDate()) {
          editorialFeaturedCache.delete(requestedDate);
          await loadEditorialFeaturedDate(requestedDate, { force: true });
          return;
        }
        fields.homeView.setAttribute("aria-busy", "true");
        fields.homeFeedback.hidden = false;
        fields.homeFeedback.textContent = "Actualizando la programación…";
        try {
          const response = await apiFetch(`/api/home?date=${encodeURIComponent(todayLocalDate())}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          setEditorialHome(normalizeEditorialHome(payload));
          rememberEditorialFeatured(editorialHome);
          setEditorialRevision(editorialRevision + 1);
          renderEditorialHome();
          setLastEditorialRenderRevision(editorialRevision);
        } catch (error) {
          fields.homeFeedback.hidden = false;
          fields.homeFeedback.innerHTML = `No pudimos actualizar la programación. <button type="button" data-click="refresh-home">Reintentar</button>`;
        } finally {
          fields.homeView.setAttribute("aria-busy", "false");
        }
      }
