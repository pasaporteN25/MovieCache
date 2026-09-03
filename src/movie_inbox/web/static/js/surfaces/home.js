import { cachedImageSrc, posterVariant } from "../core/card.js";
import { editorialRevision, loadCatalog, setEditorialRevision } from "../core/catalog-data.js";
import { detailLinks, drawerPoster, factsPanel } from "../core/detail.js";
import { fields } from "../core/fields.js";
import { availabilityState, displayTitle, escapeAttr, escapeHtml, firstListValue, listText, localDateOffset, todayLocalDate } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { goToClub, routeValuesForView, showView, syncRoute } from "../core/router.js";
import { clubMode, setClubMode } from "../core/state.js";
import { applyCollectionFilterDescriptor, render, resetCollectionFilters, setLastEditorialRenderRevision } from "./catalog-grid.js";
import { clearManualSearch } from "./catalog-search.js";
import { closeSharedDetail, openCollection } from "./club.js";

      export let editorialHome = { generated_for: "", featured: [], hero: null, sections: [], warnings: [] };

      // Keep a bounded fallback for payloads produced by older servers that do
      // not yet expose the limits object. Current API responses carry the
      // authoritative value in payload.limits.featured_items.
      const HOME_FEATURED_FALLBACK_LIMIT = 6;

      export const editorialFeaturedCache = new Map();

      export const homeShelfSelections = new Map();

      // Compatibility: spotlightIndex remains the position of the item on air.
      // It no longer represents the row/preview selection.
      export let spotlightIndex = 0;

      export let carouselItemId = "";
      export let playlistSource = "daily";
      export let selectedItemId = "";
      export let selectedEntryKey = "";
      let homeAutoplayTimer = 0;
      const HOME_AUTOPLAY_INTERVAL_MS = 6500;
      const HOME_SHELF_BAY_LIMIT = 4;

      export let activeHomeSectionId = "";
      export let activeShelfId = "";

      export function setEditorialHome(value) {
        editorialHome = value;
        homeShelfSelections.clear();
        activeHomeSectionId = "";
        activeShelfId = "";
        playlistSource = "daily";
        carouselItemId = "";
        selectedItemId = "";
        selectedEntryKey = "";
        spotlightIndex = 0;
      }

      function entryKey(entry, index = 0) {
        return String(entry?.key || entry?.item?.id || `entry-${index}`);
      }

      function entryItemId(entry) {
        return String(entry?.item?.id || "");
      }

      function homeDurationLabel(item) {
        const value = item?.duration_minutes ?? item?.duration ?? item?.runtime ?? "";
        const text = String(value).trim();
        if (!text) return "—";
        return /\bmin(?:uto)?s?\b/i.test(text) ? text : `${text} min`;
      }

      function playlistEntries(source = playlistSource) {
        if (source === "daily" || !source) return editorialHome.featured || [];
        if (source.startsWith("shelf:")) {
          const shelfId = source.slice(6);
          return editorialHome.sections.find((section, index) => homeSectionId(section, index) === shelfId)?.items || [];
        }
        return editorialHome.featured || [];
      }

      function playlistSourceLabel(source = playlistSource) {
        if (source === "daily" || !source) return "Cartelera del día";
        const shelfId = source.startsWith("shelf:") ? source.slice(6) : source;
        const section = editorialHome.sections.find((candidate, index) => homeSectionId(candidate, index) === shelfId);
        return section?.title || "Estantería activa";
      }

      function currentPlaylistIndex(entries = playlistEntries()) {
        const index = entries.findIndex((entry, candidateIndex) => entryKey(entry, candidateIndex) === selectedEntryKey
          || (selectedItemId && entryItemId(entry) === selectedItemId));
        return index >= 0 ? index : 0;
      }

      function ensureHomeSelection(entries = playlistEntries()) {
        if (!entries.length) {
          selectedEntryKey = "";
          selectedItemId = "";
          return null;
        }
        const selectedIndex = currentPlaylistIndex(entries);
        const selected = entries[selectedIndex] || entries[0];
        selectedEntryKey = entryKey(selected, selectedIndex);
        selectedItemId = entryItemId(selected);
        return selected;
      }

      function ensureCarousel(entries = editorialHome.featured || []) {
        if (!entries.length) {
          carouselItemId = "";
          spotlightIndex = 0;
          return null;
        }
        let index = entries.findIndex((entry, candidateIndex) => entryKey(entry, candidateIndex) === carouselItemId);
        if (index < 0) index = Math.max(0, Math.min(entries.length - 1, spotlightIndex));
        spotlightIndex = index;
        carouselItemId = entryKey(entries[index], index);
        return entries[index];
      }

      export function getHomePlaybackState() {
        return { carouselItemId, playlistSource, selectedItemId, selectedEntryKey, activeShelfId, spotlightIndex };
      }

      export function tickHomeAutoplay() {
        if (typeof document !== "undefined" && document.visibilityState === "hidden") return false;
        if (fields.homeView?.hidden) return false;
        if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return false;
        const featured = editorialHome.featured || [];
        if (featured.length < 2) return false;
        ensureCarousel(featured);
        const currentIndex = featured.findIndex((entry, index) => entryKey(entry, index) === carouselItemId);
        spotlightIndex = (Math.max(0, currentIndex) + 1) % featured.length;
        carouselItemId = entryKey(featured[spotlightIndex], spotlightIndex);
        renderEditorialHero();
        return true;
      }

      function syncHomeAutoplay() {
        if (homeAutoplayTimer) {
          window.clearInterval(homeAutoplayTimer);
          homeAutoplayTimer = 0;
        }
        if (typeof window === "undefined" || typeof document === "undefined") return;
        if (document.visibilityState === "hidden" || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
        homeAutoplayTimer = window.setInterval(tickHomeAutoplay, HOME_AUTOPLAY_INTERVAL_MS);
      }

      export function handleHomeVisibilityChange() {
        syncHomeAutoplay();
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
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true });
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

      export function openHomeCollectionDetail(key) {
        const entry = editorialEntryByKey(key);
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

      export function renderEditorialHome() {
        renderEditorialHero();
        renderEditorialSections();
        const hasSections = editorialHome.sections.some((section) => section.items?.length);
        fields.homeEmpty.hidden = Boolean(editorialHome.featured.length || hasSections);
        fields.homeSections.hidden = !hasSections;
        fields.homeDate.dateTime = editorialHome.generated_for || "";
        fields.homeDate.textContent = homeDateLabel(editorialHome.generated_for);
        syncHomeDateControl();
        const collectionsUnavailable = editorialHome.warnings.includes("collections_unavailable");
        const historyUnavailable = editorialHome.warnings.includes("home_history_unavailable");
        fields.homeFeedback.hidden = !(collectionsUnavailable || historyUnavailable);
        fields.homeFeedback.innerHTML = collectionsUnavailable
          ? `Las colecciones seguidas no respondieron. Tu programación personal sigue disponible. <button type="button" data-click="refresh-home">Reintentar</button>`
          : historyUnavailable
            ? `No pudimos guardar el historial de la cartelera. Las recomendaciones de hoy siguen disponibles. <button type="button" data-click="refresh-home">Reintentar</button>`
            : "";
        syncHomeAutoplay();
      }

      export function renderEditorialHero() {
        const activeElement = fields.spotlightStage?.contains(document.activeElement) ? document.activeElement : null;
        const focusIndex = activeElement?.dataset?.index || "";
        const focusEntryKey = activeElement?.dataset?.entryKey || "";
        const focusAction = activeElement?.dataset?.click || "";
        const oldTable = fields.spotlightStage?.querySelector(".spotlight-table-wrap");
        const tableScrollTop = oldTable?.scrollTop || 0;
        const tableScrollLeft = oldTable?.scrollLeft || 0;
        const featured = editorialHome.featured || [];
        const carouselEntry = ensureCarousel(featured);
        const sourceEntries = playlistEntries();
        const selectedEntry = ensureHomeSelection(sourceEntries);
        fields.spotlightStage.classList.toggle("is-empty", !carouselEntry?.item && !selectedEntry?.item);
        if (!carouselEntry?.item && !selectedEntry?.item) {
          fields.spotlightStage.innerHTML = `<div class="spotlight-empty">
            <strong>La pantalla espera una obra disponible</strong>
            <span>Vinculá un archivo o declará una obra disponible para encabezar la cartelera del día.</span>
          </div>`;
          return;
        }
        const carouselItem = carouselEntry?.item || {};
        const carouselTitle = displayTitle(carouselItem) || "Sin título";
        const carouselPoster = String(carouselItem.page_image || "").trim();
        const carouselReason = carouselEntry?.reason || {};
        const selectedItem = selectedEntry?.item || carouselItem;
        const selectedTitle = displayTitle(selectedItem) || "Sin título";
        const selectedReason = selectedEntry?.reason || {};
        const selectedSummary = String(selectedItem.description || selectedItem.wikipedia_extract || selectedReason.detail || "").trim();
        const sourceLabel = playlistSourceLabel();
        const posterMarkup = carouselPoster
          ? `<img class="spotlight-poster" data-spotlight-image src="${escapeAttr(cachedImageSrc(carouselPoster))}" alt="Portada de ${escapeAttr(carouselTitle)}" loading="eager" fetchpriority="high" decoding="async">`
          : `<div class="spotlight-poster-fallback poster-${posterVariant(carouselItem.id || carouselTitle)}" aria-hidden="true"><span>Cartelera</span><strong>${escapeHtml(carouselTitle)}</strong></div>`;
        const selector = `<aside class="spotlight-selector" aria-label="Cartelera automática">
          <div class="spotlight-selector-heading">
            <span>Cartelera disponible</span>
            <strong>${String(spotlightIndex + 1).padStart(2, "0")} / ${String(featured.length).padStart(2, "0")}</strong>
          </div>
          <div class="spotlight-poster-card">
            <button class="spotlight-poster-trigger" type="button" data-click="spotlight-select" data-index="${spotlightIndex}" aria-label="Seleccionar ${escapeAttr(carouselTitle)} de la cartelera">
              ${posterMarkup}
              <span class="spotlight-poster-caption"><strong>${escapeHtml(carouselTitle)}</strong><small>${escapeHtml(carouselReason.label || "Selección del día")}</small></span>
            </button>
            <div class="spotlight-carousel-controls" role="group" aria-label="Controles de cartelera">
              <button type="button" data-click="spotlight-prev" data-index="${spotlightIndex}" aria-label="Obra anterior">←</button>
              <button type="button" data-click="spotlight-next" data-index="${spotlightIndex}" aria-label="Obra siguiente">→</button>
            </div>
          </div>
          <div class="spotlight-selector-options">
            ${featured.map((candidate, index) => {
              const candidateTitle = displayTitle(candidate.item || {}) || `Recomendación ${index + 1}`;
              const candidateReason = candidate.reason?.label || "Selección del día";
              const selected = index === spotlightIndex;
              return `<button class="spotlight-selector-option" type="button" aria-pressed="${selected}" tabindex="${selected ? "0" : "-1"}" data-click="spotlight-air-select" data-index="${index}" aria-label="${escapeAttr(`${candidateTitle}. ${candidateReason}. Recomendación ${index + 1} de ${featured.length}`)}">
                <span>${String(index + 1).padStart(2, "0")}</span>
                <strong>${escapeHtml(candidateTitle)}</strong>
                <small>${escapeHtml(candidateReason)}</small>
              </button>`;
            }).join("")}
          </div>
        </aside>`;
        const tableRows = sourceEntries.map((entry, index) => {
          const item = entry?.item || {};
          const key = entryKey(entry, index);
          const itemId = entryItemId(entry);
          const selected = key === selectedEntryKey;
          const onAir = key === carouselItemId && playlistSource === "daily";
          const genres = listText(item.genres, 2) || "—";
          const duration = homeDurationLabel(item);
          return `<tr role="row" class="playlist-entry${selected ? " is-selected" : ""}${onAir ? " is-on-air" : ""}" data-playlist-entry="${escapeAttr(key)}" data-entry-key="${escapeAttr(key)}" data-item-id="${escapeAttr(itemId)}" data-entry-index="${index}" data-click="playlist-select" tabindex="${selected ? "0" : "-1"}" aria-selected="${selected}" aria-label="${escapeAttr(`${displayTitle(item) || "Sin título"}. ${item.year || "Año desconocido"}. ${item.kind || "Película"}. ${genres}. ${duration}`)}">
            <td class="playlist-index">${String(index + 1).padStart(2, "0")}</td>
            <td class="playlist-title">${escapeHtml(displayTitle(item) || "Sin título")}</td>
            <td>${escapeHtml(item.year || "—")}</td>
            <td>${escapeHtml(item.kind || "película")}</td>
            <td>${escapeHtml(genres)}</td>
            <td>${escapeHtml(duration)}</td>
          </tr>`;
        }).join("");
        const selectedOrigin = selectedEntry?.origin || {};
        const selectedAvailability = availabilityState(selectedItem);
        const selectedDuration = homeDurationLabel(selectedItem);
        const selectedStatus = selectedItem.status === "watched" ? "Vista" : "Pendiente";
        const previewViewAction = selectedOrigin.kind === "collection"
          ? `<button class="spotlight-preview-action" type="button" data-click="open-home-collection-detail" data-key="${escapeAttr(selectedEntry?.key || "")}">Ver ficha del Club</button>`
          : `<button class="spotlight-preview-action" type="button" data-click="open-detail-with-case-transition" data-id="${escapeAttr(selectedItem.id || "")}">Ver más</button>`;
        const previewEditAction = selectedOrigin.kind === "catalog"
          ? `<button class="spotlight-preview-action is-secondary" type="button" data-click="edit-home-shelf-entry" data-id="${escapeAttr(selectedItem.id || "")}">Editar mi ficha</button>`
          : "";
        fields.spotlightStage.innerHTML = `<div class="spotlight-layout">
          ${selector}
          <div class="spotlight-viewport">
            <div class="spotlight-playlist-head"><span>Fuente</span><strong data-playlist-source>${escapeHtml(sourceLabel)}</strong></div>
            <div class="spotlight-table-wrap">
              <table class="spotlight-playlist" role="grid" aria-label="Playlist de ${escapeAttr(sourceLabel)}">
                <thead><tr><th scope="col">#</th><th scope="col">Título</th><th scope="col">Año</th><th scope="col">Tipo</th><th scope="col">Géneros</th><th scope="col">Duración</th></tr></thead>
                <tbody>${tableRows || `<tr><td colspan="6" class="playlist-empty">No hay obras en esta fuente.</td></tr>`}</tbody>
              </table>
            </div>
            <aside class="spotlight-preview" aria-labelledby="spotlight-selected-title">
              <div class="spotlight-preview-actions">${previewViewAction}${previewEditAction}</div>
              <div class="spotlight-preview-art">${selectedItem.page_image ? `<img src="${escapeAttr(cachedImageSrc(String(selectedItem.page_image)))}" alt="" loading="lazy" decoding="async">` : `<span class="poster-${posterVariant(selectedItem.id || selectedTitle)}" aria-hidden="true"></span>`}</div>
              <div class="spotlight-copy">
                <span class="spotlight-reason">${escapeHtml(selectedReason.label || sourceLabel)}</span>
                <h3 id="spotlight-selected-title">${escapeHtml(selectedTitle)}</h3>
                <span class="spotlight-metadata">${escapeHtml([selectedItem.year, selectedItem.kind, firstListValue(selectedItem.genres)].filter(Boolean).join(" · ") || "Ficha por completar")}</span>
                <p>${escapeHtml(selectedSummary || "Una obra disponible de tu archivo personal para considerar esta noche.")}</p>
              </div>
              <dl class="spotlight-preview-facts">
                <div><dt>Disponibilidad</dt><dd>${selectedAvailability.effective ? "Disponible" : "No disponible"}</dd></div>
                <div><dt>Estado</dt><dd>${escapeHtml(selectedStatus)}</dd></div>
                <div><dt>Duración</dt><dd>${escapeHtml(selectedDuration)}</dd></div>
              </dl>
            </aside>
          </div>
        </div>`;
        const nextTable = fields.spotlightStage.querySelector(".spotlight-table-wrap");
        if (nextTable) {
          nextTable.scrollTop = tableScrollTop;
          nextTable.scrollLeft = tableScrollLeft;
        }
        if (activeElement && fields.spotlightStage.contains(activeElement) === false) {
          const focusTarget = focusEntryKey
            ? fields.spotlightStage.querySelector(`[data-playlist-entry][data-entry-key="${CSS.escape(focusEntryKey)}"]`)
            : focusIndex
              ? fields.spotlightStage.querySelector(`[data-click="${CSS.escape(focusAction || "spotlight-select")}"][data-index="${CSS.escape(focusIndex)}"]`)
              : null;
          focusTarget?.focus({ preventScroll: true });
        }
      }

      export function selectSpotlight(index, restoreFocus = false) {
        if (!editorialHome.featured.length) return;
        playlistSource = "daily";
        activeHomeSectionId = nonEmptyHomeSections().length ? activeHomeSectionId : "";
        spotlightIndex = Math.max(0, Math.min(editorialHome.featured.length - 1, index));
        const entry = editorialHome.featured[spotlightIndex];
        carouselItemId = entryKey(entry, spotlightIndex);
        selectedEntryKey = carouselItemId;
        selectedItemId = entryItemId(entry);
        renderEditorialHero();
        if (restoreFocus) {
          fields.spotlightStage.querySelector(".spotlight-poster-trigger")?.focus({ preventScroll: true });
        }
      }

      export function setCarouselItem(index, restoreFocus = false, focusAction = "spotlight-air-select") {
        const featured = editorialHome.featured || [];
        if (!featured.length) return;
        const requestedIndex = Number.isFinite(Number(index)) ? Number(index) : 0;
        spotlightIndex = ((requestedIndex % featured.length) + featured.length) % featured.length;
        carouselItemId = entryKey(featured[spotlightIndex], spotlightIndex);
        renderEditorialHero();
        if (restoreFocus) {
          const focusTarget = focusAction === "spotlight-prev" || focusAction === "spotlight-next"
            ? fields.spotlightStage.querySelector(`[data-click="${focusAction}"]`)
            : fields.spotlightStage.querySelector(`.spotlight-selector-option[data-index="${spotlightIndex}"]`);
          focusTarget?.focus({ preventScroll: true });
        }
      }

      export function moveSpotlightSelector(event) {
        if (!event.target.closest("[data-click='spotlight-select'], [data-click='spotlight-air-select'], [data-click='spotlight-prev'], [data-click='spotlight-next']")) return;
        const count = editorialHome.featured.length;
        if (!count) return;
        const offsets = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
        if (event.target.closest("[data-click='spotlight-prev']") && event.key === "Enter") {
          event.preventDefault();
          setCarouselItem(spotlightIndex - 1, true, "spotlight-prev");
          return;
        }
        if (event.target.closest("[data-click='spotlight-next']") && event.key === "Enter") {
          event.preventDefault();
          setCarouselItem(spotlightIndex + 1, true, "spotlight-next");
          return;
        }
        if (event.key === "Home") {
          event.preventDefault();
          setCarouselItem(0, true);
          return;
        }
        if (event.key === "End") {
          event.preventDefault();
          setCarouselItem(count - 1, true);
          return;
        }
        if (!(event.key in offsets)) return;
        event.preventDefault();
        setCarouselItem((spotlightIndex + offsets[event.key] + count) % count, true);
      }

      export function movePlaylistSelection(event) {
        const control = event.target.closest("[data-playlist-entry]");
        if (!control) return;
        const entries = playlistEntries();
        if (!entries.length) return;
        const current = Number(control.dataset.entryIndex || 0);
        let next = current;
        if (event.key === "Home") next = 0;
        else if (event.key === "End") next = entries.length - 1;
        else if (event.key === "ArrowDown") next = Math.min(entries.length - 1, current + 1);
        else if (event.key === "ArrowUp") next = Math.max(0, current - 1);
        else if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectPlaylistEntry(control.dataset.entryKey || "", true, true);
          return;
        } else return;
        event.preventDefault();
        selectPlaylistEntry(entryKey(entries[next], next), true);
      }

      export function selectPlaylistEntry(key, restoreFocus = false, focusPreview = false) {
        const entries = playlistEntries();
        const index = entries.findIndex((entry, candidateIndex) => entryKey(entry, candidateIndex) === key);
        if (index < 0) return;
        const entry = entries[index];
        selectedEntryKey = entryKey(entry, index);
        selectedItemId = entryItemId(entry);
        if (playlistSource.startsWith("shelf:")) {
          const shelfId = playlistSource.slice(6);
          homeShelfSelections.set(shelfId, index);
          renderEditorialSections();
        }
        renderEditorialHero();
        if (restoreFocus) {
          if (focusPreview) fields.spotlightStage.querySelector(".spotlight-preview-action")?.focus({ preventScroll: true });
          else fields.spotlightStage.querySelector(`[data-playlist-entry][data-entry-key="${CSS.escape(selectedEntryKey)}"]`)?.focus({ preventScroll: true });
        }
      }

      export function selectHomeShelfEntry(sectionId, key, restoreFocus = false) {
        const section = editorialHome.sections.find((entry, index) => homeSectionId(entry, index) === sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        const index = entries.findIndex((entry) => entry?.key === key);
        if (index < 0) return;
        playlistSource = `shelf:${sectionId}`;
        activeHomeSectionId = sectionId;
        activeShelfId = sectionId;
        selectedEntryKey = entryKey(entries[index], index);
        selectedItemId = entryItemId(entries[index]);
        homeShelfSelections.set(sectionId, index);
        renderEditorialSections();
        renderEditorialHero();
        if (restoreFocus) {
          fields.homeSections.querySelector(`[data-click="home-shelf-select"][data-section-id="${CSS.escape(sectionId)}"][data-entry-index="${index}"]`)?.focus();
        }
      }

      export function moveHomeShelf(event) {
        const control = event.target.closest("[data-click='home-shelf-select']");
        if (!control) return;
        const sectionId = control.dataset.sectionId || "";
        const section = editorialHome.sections.find((entry) => entry.id === sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        if (!entries.length) return;
        const offsets = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
        let nextIndex = Number(control.dataset.entryIndex || 0);
        if (event.key === "Home") nextIndex = 0;
        else if (event.key === "End") nextIndex = entries.length - 1;
        else if (event.key in offsets) nextIndex = (nextIndex + offsets[event.key] + entries.length) % entries.length;
        else return;
        event.preventDefault();
        selectHomeShelfEntry(sectionId, entries[nextIndex].key || "", true);
      }

      export function nonEmptyHomeSections() {
        return editorialHome.sections.filter((section) => Array.isArray(section.items) && section.items.length);
      }

      export function homeSectionId(section, sectionIndex) {
        return String(section.id || `editorial-${sectionIndex}`);
      }

      export function renderEditorialSections() {
        const sections = nonEmptyHomeSections().slice(0, HOME_SHELF_BAY_LIMIT);
        const ids = sections.map((section, index) => homeSectionId(section, index));
        if (!ids.includes(activeHomeSectionId)) {
          activeHomeSectionId = ids[0] || "";
          activeShelfId = activeHomeSectionId;
        }
        fields.homeShelfCategories.innerHTML = ids.length > 1 ? homeFurnitureControls(ids.length) : "";
        fields.homeShelfCategories.hidden = ids.length <= 1;
        fields.homeSections.setAttribute("role", "region");
        fields.homeSections.setAttribute("aria-label", "Mueble horizontal de estanterías");
        fields.homeSections.setAttribute("tabindex", ids.length ? "0" : "-1");
        fields.homeSections.dataset.bayCount = String(ids.length);
        fields.homeSections.innerHTML = sections
          .map((section, sectionIndex) => editorialSection(section, sectionIndex, ids[sectionIndex] === activeHomeSectionId))
          .join("");
      }

      export function homeFurnitureControls(count) {
        return `<div class="home-shelf-navigation" role="group" aria-label="Recorrido del mueble">
          <span class="home-shelf-navigation-label">${count} módulos · recorrido lateral</span>
          <button class="home-shelf-scroll-control" type="button" data-click="home-shelf-scroll" data-direction="prev" aria-label="Mostrar módulo anterior">←</button>
          <button class="home-shelf-scroll-control" type="button" data-click="home-shelf-scroll" data-direction="next" aria-label="Mostrar módulo siguiente">→</button>
        </div>`;
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
        const action = section.action || {};
        const entries = Array.isArray(section.items) ? section.items : [];
        const sectionId = homeSectionId(section, sectionIndex);
        const selectedIndex = Math.max(0, Math.min(entries.length - 1, homeShelfSelections.get(sectionId) || 0));
        const selectedEntry = entries[selectedIndex];
        const actionButton = action.kind
          ? `<button class="quiet-action home-section-action" type="button" data-click="home-section-action" data-section-id="${escapeAttr(sectionId)}">${escapeHtml(action.label || "Explorar")}</button>`
          : "";
        return `<section class="home-program home-shelf-bay" data-home-section="${escapeAttr(sectionId)}" data-bay-index="${sectionIndex}" data-active="${active}" aria-labelledby="home-section-${escapeAttr(sectionId)}">
          <header class="home-program-heading">
            <div>
              <span class="section-kicker">${escapeHtml(section.eyebrow || "Programación personal")}</span>
              <h2 id="home-section-${escapeAttr(sectionId)}">${escapeHtml(section.title || "Selección")}</h2>
              <p>${escapeHtml(section.description || "")}</p>
            </div>
            ${actionButton}
          </header>
          <div class="home-shelf-rail" role="group" aria-label="Opciones de ${escapeAttr(section.title || "la estantería")}">
            ${entries.map((entry, index) => homeShelfTape(entry, index, sectionId, index === selectedIndex)).join("")}
          </div>
          ${homeShelfPreview(sectionId, selectedEntry)}
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
        if (!event.target.closest("#homeSections") || event.target.closest("[data-click='home-shelf-select']")) return;
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
        if (!rail || !event.target.closest("#homeSections") || rail.scrollWidth <= rail.clientWidth) return;
        const delta = Math.abs(event.deltaX) >= Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
        if (!delta) return;
        event.preventDefault();
        rail.scrollBy({ left: delta, behavior: "auto" });
      }

      export function homeShelfTape(entry, index, sectionId, selected) {
        const item = entry?.item || {};
        const title = displayTitle(item) || `Obra ${index + 1}`;
        const meta = [item.year, firstListValue(item.genres)].filter(Boolean).join(" · ") || "Ficha por completar";
        const reason = entry?.reason?.label || "Selección del archivo";
        return `<button class="home-shelf-tape vhs-spine" type="button" data-vhs-state="${selected ? "selected" : "closed"}" aria-pressed="${selected}" tabindex="${selected ? "0" : "-1"}" data-click="home-shelf-select" data-section-id="${escapeAttr(sectionId)}" data-entry-index="${index}" data-entry-key="${escapeAttr(entry?.key || "")}" aria-label="${escapeAttr(`${title}. ${reason}. Opción ${index + 1}`)}">
          <span class="vhs-spine-sticker" aria-hidden="true"></span>
          <span class="vhs-spine-title">${escapeHtml(title)}</span>
          <span class="vhs-spine-meta">${escapeHtml(meta)}</span>
        </button>`;
      }

      export function homeShelfPreview(sectionId, entry) {
        const item = entry?.item || {};
        const origin = entry?.origin || {};
        const title = displayTitle(item) || "Sin título";
        const poster = String(item.page_image || "").trim();
        const reason = entry?.reason || {};
        const metadata = [item.year, firstListValue(item.directors), firstListValue(item.genres)].filter(Boolean);
        const summary = String(reason.detail || item.wikipedia_extract || item.description || "").trim();
        const isCollection = origin.kind === "collection";
        const viewMoreAction = isCollection
          ? `<button type="button" class="home-shelf-preview-action" data-click="open-home-collection-detail" data-key="${escapeAttr(entry?.key || "")}">Ver ficha del Club</button>`
          : `<button type="button" class="home-shelf-preview-action" data-click="open-detail-with-case-transition" data-id="${escapeAttr(item.id || "")}">Ver más</button>`;
        const editAction = isCollection
          ? ""
          : `<button type="button" class="quiet-action home-shelf-preview-action" data-click="edit-home-shelf-entry" data-id="${escapeAttr(item.id || "")}">Editar mi ficha</button>`;
        const artwork = poster
          ? `<img data-poster-image src="${escapeAttr(cachedImageSrc(poster))}" alt="Portada de ${escapeAttr(title)}" loading="lazy" decoding="async">`
          : `<div class="home-shelf-preview-placeholder poster-${posterVariant(item.id || title)}" aria-hidden="true"><span>Archivo personal</span><strong>${escapeHtml(title)}</strong></div>`;
        return `<aside class="home-shelf-preview vhs-case" data-vhs-state="open" data-home-shelf-preview="${escapeAttr(sectionId)}" aria-labelledby="home-shelf-preview-${escapeAttr(sectionId)}">
          <div class="home-shelf-preview-art"><span class="home-shelf-preview-frame" aria-hidden="true"></span>${artwork}</div>
          <div class="home-shelf-preview-copy">
            <span>${escapeHtml(isCollection ? `En ${origin.collection_title || "una colección seguida"}` : reason.label || "Selección del archivo")}</span>
            <h3 id="home-shelf-preview-${escapeAttr(sectionId)}">${escapeHtml(title)}</h3>
            ${metadata.length ? `<p class="home-shelf-preview-meta">${metadata.map(escapeHtml).join(" · ")}</p>` : ""}
            <p class="home-shelf-preview-summary">${escapeHtml(summary || "Abrí la ficha para completar la información de esta obra.")}</p>
            <div class="home-shelf-preview-actions">${viewMoreAction}${editAction}</div>
          </div>
        </aside>`;
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

      export function rememberEditorialFeatured(payload) {
        const date = String(payload?.generated_for || "");
        if (!date) return;
        editorialFeaturedCache.set(date, {
          featured: Array.isArray(payload.featured) ? payload.featured : [],
          featured_source: String(payload.featured_source || "")
        });
      }

      export function syncHomeDateControl() {
        const selected = editorialHome.generated_for || todayLocalDate();
        fields.homeDateToday.setAttribute("aria-pressed", String(selected === todayLocalDate()));
        fields.homeDateYesterday.setAttribute("aria-pressed", String(selected === localDateOffset(-1)));
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
        selectedEntryKey = "";
        selectedItemId = "";
        spotlightIndex = 0;
        carouselItemId = "";
        renderEditorialHero();
        fields.homeDate.dateTime = localDate;
        fields.homeDate.textContent = homeDateLabel(localDate);
        syncHomeDateControl();
      }

      export async function loadEditorialFeaturedDate(localDate, options = {}) {
        const requestedDate = String(localDate || "");
        if (!requestedDate || (requestedDate === editorialHome.generated_for && !options.force)) return;
        const cached = !options.force ? editorialFeaturedCache.get(requestedDate) : null;
        if (cached) {
          applyEditorialFeaturedDate(requestedDate, cached);
          return;
        }
        const isYesterday = requestedDate === localDateOffset(-1);
        fields.homeDateToday.disabled = true;
        fields.homeDateYesterday.disabled = true;
        fields.spotlight.setAttribute("aria-busy", "true");
        fields.homeFeedback.hidden = false;
        fields.homeFeedback.textContent = isYesterday
          ? "Recuperando las recomendaciones guardadas de ayer…"
          : "Actualizando las recomendaciones de hoy…";
        try {
          const snapshotQuery = isYesterday ? "&saved_featured=true" : "";
          const response = await apiFetch(`/api/home?date=${encodeURIComponent(requestedDate)}${snapshotQuery}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const normalized = normalizeEditorialHome(payload);
          rememberEditorialFeatured(normalized);
          applyEditorialFeaturedDate(requestedDate, normalized);
          fields.homeFeedback.hidden = true;
          fields.homeFeedback.textContent = "";
        } catch (error) {
          const retryAction = isYesterday ? "home-date-yesterday" : "home-date-today";
          fields.homeFeedback.hidden = false;
          fields.homeFeedback.innerHTML = `No pudimos recuperar esas recomendaciones. <button type="button" data-click="${retryAction}">Reintentar</button>`;
        } finally {
          fields.homeDateToday.disabled = false;
          fields.homeDateYesterday.disabled = false;
          fields.spotlight.setAttribute("aria-busy", "false");
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
