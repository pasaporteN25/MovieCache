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
      const HOME_MOBILE_MEDIA = "(max-width: 860px)";

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

      function homeSignalHash(seed) {
        let value = 2166136261;
        for (const character of String(seed || "movie-inbox")) {
          value ^= character.codePointAt(0);
          value = Math.imul(value, 16777619);
        }
        return value >>> 0;
      }

      export function homeSignalPoints(seed, sampleCount = 46) {
        const count = Math.max(12, Number(sampleCount) || 46);
        let state = homeSignalHash(seed) || 1;
        const points = [];
        for (let index = 0; index < count; index += 1) {
          state ^= state << 13;
          state ^= state >>> 17;
          state ^= state << 5;
          state >>>= 0;
          const progress = index / (count - 1);
          const envelope = 0.42 + (Math.sin(progress * Math.PI) * 0.58);
          const noise = ((state & 0xffff) / 0xffff) - 0.5;
          const harmonic = Math.sin((progress * Math.PI * 8) + ((state >>> 24) / 34));
          const y = 29 + ((noise * 25) + (harmonic * 5)) * envelope;
          points.push(`${(progress * 360).toFixed(1)},${Math.max(5, Math.min(53, y)).toFixed(1)}`);
        }
        return points.join(" ");
      }

      function homeSignalMarkup(item) {
        const seed = String(item?.id || displayTitle(item) || "movie-inbox");
        const marker = 36 + (homeSignalHash(seed) % 289);
        const points = homeSignalPoints(seed);
        return `<div class="spotlight-preview-signal" data-signal-seed="${escapeAttr(seed)}" aria-hidden="true">
          <svg viewBox="0 0 360 58" preserveAspectRatio="none" focusable="false">
            <path class="spotlight-signal-grid" d="M0 8H360 M0 29H360 M0 50H360 M45 0V58 M90 0V58 M135 0V58 M180 0V58 M225 0V58 M270 0V58 M315 0V58" />
            <polyline class="spotlight-signal-echo" points="${points}" />
            <polyline class="spotlight-signal-wave" points="${points}" />
            <line class="spotlight-signal-marker" x1="${marker}" y1="3" x2="${marker}" y2="55" />
          </svg>
        </div>`;
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
        if (fields.spotlightStage?.querySelector(".spotlight-poster-trigger:focus")) return false;
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
        fields.homeVideothequeHeading.hidden = !hasSections;
        fields.homeFurniture.hidden = !hasSections;
        fields.homeSections.hidden = !hasSections;
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
            ${homeDateControlMarkup()}
            <strong>La pantalla espera una obra disponible</strong>
            <span>Vinculá un archivo o declará una obra disponible para encabezar la cartelera del día.</span>
          </div>`;
          return;
        }
        const carouselItem = carouselEntry?.item || {};
        const carouselTitle = displayTitle(carouselItem) || "Sin título";
        const carouselPoster = String(carouselItem.page_image || "").trim();
        const selectedItem = selectedEntry?.item || carouselItem;
        const selectedTitle = displayTitle(selectedItem) || "Sin título";
        const selectedReason = selectedEntry?.reason || {};
        const selectedSummary = String(selectedItem.description || selectedItem.wikipedia_extract || selectedReason.detail || "").trim();
        const sourceLabel = playlistSourceLabel();
        const carouselPosterFallback = `<div class="spotlight-poster-fallback poster-${posterVariant(carouselItem.id || carouselTitle)}" aria-hidden="true"${carouselPoster ? " hidden" : ""}><span>Sin portada</span></div>`;
        const posterMarkup = carouselPoster
          ? `<img class="spotlight-poster" data-spotlight-image src="${escapeAttr(cachedImageSrc(carouselPoster))}" alt="Portada de ${escapeAttr(carouselTitle)}" loading="eager" fetchpriority="high" decoding="async">${carouselPosterFallback}`
          : carouselPosterFallback;
        const selector = `<aside class="spotlight-selector" aria-label="Cartelera automática">
          <div class="spotlight-selector-heading">
            <span>${escapeHtml(homeDatePeriodLabel(editorialHome.generated_for))}</span>
          </div>
          <div class="spotlight-poster-card">
            <button class="spotlight-poster-trigger" type="button" data-click="spotlight-select" data-index="${spotlightIndex}" aria-label="Seleccionar ${escapeAttr(carouselTitle)} de la cartelera"${featured.length > 1 ? ' aria-describedby="spotlight-navigation-help"' : ""}>
              ${posterMarkup}
            </button>
          </div>
          ${featured.length > 1 ? `<span id="spotlight-navigation-help" class="sr-only">Recomendación ${spotlightIndex + 1} de ${featured.length}. Usá las flechas para cambiar de portada, Inicio o Fin para ir a los extremos y Enter para seleccionar. La rotación se pausa mientras la portada tiene el foco.</span>` : ""}
        </aside>`;
        const tableRows = sourceEntries.map((entry, index) => {
          const item = entry?.item || {};
          const key = entryKey(entry, index);
          const itemId = entryItemId(entry);
          const selected = key === selectedEntryKey;
          const onAir = key === carouselItemId && playlistSource === "daily";
          const genres = listText(item.genres, 2) || "—";
          const directors = listText(item.directors, 2) || "—";
          const duration = homeDurationLabel(item);
          return `<tr role="row" class="playlist-entry${selected ? " is-selected" : ""}${onAir ? " is-on-air" : ""}" data-playlist-entry="${escapeAttr(key)}" data-entry-key="${escapeAttr(key)}" data-item-id="${escapeAttr(itemId)}" data-entry-index="${index}" data-click="playlist-select" tabindex="${selected ? "0" : "-1"}" aria-selected="${selected}" aria-label="${escapeAttr(`${displayTitle(item) || "Sin título"}. Dirección: ${directors}. ${item.year || "Año desconocido"}. ${item.kind || "Película"}. ${genres}. ${duration}`)}">
            <td class="playlist-index"><span class="playlist-position">${String(index + 1).padStart(2, "0")}</span></td>
            <td class="playlist-title">${escapeHtml(displayTitle(item) || "Sin título")}</td>
            <td class="playlist-director">${escapeHtml(directors)}</td>
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
        const selectedPoster = String(selectedItem.page_image || "").trim();
        const selectedPosterFallback = `<span class="spotlight-preview-art-fallback poster-${posterVariant(selectedItem.id || selectedTitle)}" aria-hidden="true"${selectedPoster ? " hidden" : ""}></span>`;
        const selectedPosterMarkup = selectedPoster
          ? `<img data-poster-image src="${escapeAttr(cachedImageSrc(selectedPoster))}" alt="" loading="lazy" decoding="async">${selectedPosterFallback}`
          : selectedPosterFallback;
        fields.spotlightStage.innerHTML = `<div class="spotlight-layout">
          ${selector}
          <div class="spotlight-viewport">
            <div class="spotlight-playlist-head">
              <div class="spotlight-playlist-source"><span>Fuente</span><strong data-playlist-source>${escapeHtml(sourceLabel)}</strong></div>
              ${homeDateControlMarkup()}
            </div>
            <div class="spotlight-table-wrap">
              <table class="spotlight-playlist" data-row-count="${Math.min(sourceEntries.length, 6)}" role="grid" aria-label="Playlist de ${escapeAttr(sourceLabel)}">
                <thead><tr><th scope="col">#</th><th scope="col">Título</th><th scope="col">Director</th><th scope="col">Año</th><th scope="col">Tipo</th><th scope="col">Géneros</th><th scope="col">Duración</th></tr></thead>
                <tbody>${tableRows || `<tr><td colspan="7" class="playlist-empty">No hay obras en esta fuente.</td></tr>`}</tbody>
              </table>
            </div>
            <aside class="spotlight-preview" aria-labelledby="spotlight-selected-title">
              <div class="spotlight-preview-actions">${previewViewAction}${previewEditAction}</div>
              <div class="spotlight-preview-art">${selectedPosterMarkup}</div>
              <div class="spotlight-copy">
                <h3 id="spotlight-selected-title">${escapeHtml(selectedTitle)}</h3>
                <span class="spotlight-metadata">${escapeHtml([selectedItem.year, selectedItem.kind, firstListValue(selectedItem.genres)].filter(Boolean).join(" · ") || "Ficha por completar")}</span>
                <p>${escapeHtml(selectedSummary || "Una obra disponible de tu archivo personal para considerar esta noche.")}</p>
              </div>
              ${homeSignalMarkup(selectedItem)}
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

      export function setCarouselItem(index, restoreFocus = false) {
        const featured = editorialHome.featured || [];
        if (!featured.length) return;
        const requestedIndex = Number.isFinite(Number(index)) ? Number(index) : 0;
        spotlightIndex = ((requestedIndex % featured.length) + featured.length) % featured.length;
        carouselItemId = entryKey(featured[spotlightIndex], spotlightIndex);
        renderEditorialHero();
        if (restoreFocus) {
          fields.spotlightStage.querySelector(".spotlight-poster-trigger")?.focus({ preventScroll: true });
        }
      }

      export function moveSpotlightSelector(event) {
        if (!event.target.closest("[data-click='spotlight-select']")) return;
        const count = editorialHome.featured.length;
        if (!count) return;
        const offsets = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
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
        }
        renderEditorialSections();
        renderEditorialHero();
        alignHomePlaylistAndShelf({ focusRow: restoreFocus && !focusPreview });
        if (restoreFocus) {
          if (focusPreview) fields.spotlightStage.querySelector(".spotlight-preview-action")?.focus({ preventScroll: true });
          else fields.spotlightStage.querySelector(`[data-playlist-entry][data-entry-key="${CSS.escape(selectedEntryKey)}"]`)?.focus({ preventScroll: true });
        }
      }

      export function selectHomeShelfEntry(sectionId, key, restoreFocus = false) {
        const section = editorialHome.sections.find((entry, index) => homeSectionId(entry, index) === sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        const index = entries.findIndex((entry, candidateIndex) => entryKey(entry, candidateIndex) === key);
        if (index < 0) return;
        // A spine owns the lower furniture state: selecting one also activates
        // its bay, without reprogramming the playlist/marquee above.
        activeHomeSectionId = sectionId;
        activeShelfId = sectionId;
        homeShelfSelections.set(sectionId, index);
        renderEditorialSections();
        if (restoreFocus) {
          const selectedSpine = fields.homeSections.querySelector(`[data-click="home-shelf-select"][data-section-id="${CSS.escape(sectionId)}"][data-entry-index="${index}"]`);
          selectedSpine?.scrollIntoView({ block: "nearest", inline: "nearest" });
          selectedSpine?.focus({ preventScroll: true });
        }
      }

      export function moveHomeShelf(event) {
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
        fields.homeSections.setAttribute("aria-labelledby", "homeVideothequeTitle");
        fields.homeSections.removeAttribute("aria-label");
        fields.homeSections.setAttribute("tabindex", ids.length ? "0" : "-1");
        fields.homeSections.dataset.bayCount = String(ids.length);
        fields.homeSections.innerHTML = sections
          .map((section, sectionIndex) => editorialSection(section, sectionIndex, ids[sectionIndex] === activeHomeSectionId))
          .join("");
        renderHomeShelfPreview();
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
        syncHomeShelfPreviewPlacement();
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

      function homeShelfEntryForSelection(sectionId = activeHomeSectionId) {
        const section = homeSectionById(sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        // The shelf's preview reflects only its own remembered selection, never
        // the winamp-style playlist's current item above.
        const rememberedIndex = homeShelfSelections.get(sectionId);
        return entries[Number.isInteger(rememberedIndex) ? Math.max(0, Math.min(entries.length - 1, rememberedIndex)) : 0] || null;
      }

      export function activateHomeShelf(sectionId, restoreFocus = false) {
        const section = homeSectionById(sectionId);
        const entries = Array.isArray(section?.items) ? section.items : [];
        if (!section || !entries.length) return false;
        const rememberedIndex = homeShelfSelections.get(sectionId);
        const index = Number.isInteger(rememberedIndex)
          ? Math.max(0, Math.min(entries.length - 1, rememberedIndex))
          : 0;
        const entry = entries[index];
        activeHomeSectionId = sectionId;
        activeShelfId = sectionId;
        playlistSource = `shelf:${sectionId}`;
        selectedEntryKey = entryKey(entry, index);
        selectedItemId = entryItemId(entry);
        homeShelfSelections.set(sectionId, index);
        renderEditorialSections();
        renderEditorialHero();
        alignHomePlaylistAndShelf({ focusSpine: restoreFocus, focusBay: true });
        return true;
      }

      export function moveHomeShelfBay(event) {
        const bay = event.target.closest(".home-shelf-bay");
        if (!bay || event.target !== bay || !["Enter", " "].includes(event.key)) return;
        event.preventDefault();
        activateHomeShelf(bay.dataset.homeSection || "", true);
      }

      function alignHomePlaylistAndShelf({ focusRow = false, focusSpine = false, focusBay = false } = {}) {
        const key = selectedEntryKey;
        if (!key) return;
        const row = fields.spotlightStage?.querySelector(`[data-playlist-entry][data-entry-key="${CSS.escape(key)}"]`);
        const spine = fields.homeSections?.querySelector(`[data-click="home-shelf-select"][data-entry-key="${CSS.escape(key)}"]`);
        const bay = spine?.closest(".home-shelf-bay");
        row?.scrollIntoView({ block: "nearest", inline: "nearest" });
        if (focusBay) bay?.scrollIntoView({ block: "nearest", inline: "start" });
        else spine?.scrollIntoView({ block: "nearest", inline: "nearest" });
        if (focusRow) row?.focus({ preventScroll: true });
        else if (focusSpine) spine?.focus({ preventScroll: true });
        else if (focusBay) bay?.focus({ preventScroll: true });
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
        const entries = Array.isArray(section.items) ? section.items : [];
        const sectionId = homeSectionId(section, sectionIndex);
        const countLabel = `${entries.length} ${entries.length === 1 ? "título" : "títulos"}`;
        const rememberedIndex = homeShelfSelections.get(sectionId);
        // The shelf keeps its own selection, independent of whatever the
        // winamp-style playlist above is currently showing.
        const selectedIndex = Math.max(0, Math.min(entries.length - 1, Number.isInteger(rememberedIndex) ? rememberedIndex : 0));
        return `<section class="home-program home-shelf-bay" data-home-section="${escapeAttr(sectionId)}" data-bay-index="${sectionIndex}" data-active="${active}" data-click="home-shelf-activate" data-section-id="${escapeAttr(sectionId)}" tabindex="0" aria-labelledby="home-section-${escapeAttr(sectionId)}">
          <h2 id="home-section-${escapeAttr(sectionId)}" class="sr-only home-shelf-bay-plaque" title="${escapeAttr(section.title || "Selección")}"><span>${escapeHtml(section.title || "Selección")}</span><small>${escapeHtml(countLabel)}</small></h2>
          <div class="home-shelf-rail" role="group" aria-label="Opciones de ${escapeAttr(section.title || "la estantería")}">
            ${entries.map((entry, index) => homeShelfTape(entry, index, sectionId, active && index === selectedIndex)).join("")}
          </div>
        </section>`;
      }

      function homeShelfRail() {
        return fields.homeSections;
      }

      export function syncHomeShelfPreviewPlacement() {
        const host = fields.homeShelfPreview;
        if (!host || !fields.homeFurniture || !fields.homeSections) return;
        const activeBay = activeHomeSectionId
          ? fields.homeSections.querySelector(
            `[data-home-section="${CSS.escape(activeHomeSectionId)}"]`
          )
          : null;
        const mobile = typeof window !== "undefined"
          && window.matchMedia?.(HOME_MOBILE_MEDIA).matches;
        const target = mobile && activeBay ? activeBay : fields.homeFurniture;
        if (host.parentElement !== target) target.append(host);
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
        if (
          !event.target.closest("#homeSections")
          || event.target.closest("[data-click='home-shelf-select'], .home-shelf-preview-host")
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
          || event.target.closest(".home-shelf-preview-host")
          || rail.scrollWidth <= rail.clientWidth
        ) return;
        const delta = Math.abs(event.deltaX) >= Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
        if (!delta) return;
        event.preventDefault();
        rail.scrollBy({ left: delta, behavior: "auto" });
      }

      export function homeShelfTape(entry, index, sectionId, selected) {
        const item = entry?.item || {};
        const title = displayTitle(item) || `Obra ${index + 1}`;
        const year = String(item.year || "S/A");
        const kind = String(item.kind || "obra");
        const titleLength = Array.from(title).length;
        const titleLengthClass = titleLength <= 22 ? "short" : titleLength <= 36 ? "long" : "xlong";
        const reason = entry?.reason?.label || "Selección del archivo";
        return `<button class="home-shelf-tape vhs-spine" type="button" data-vhs-state="${selected ? "selected" : "closed"}" data-title-length="${titleLengthClass}" title="${escapeAttr(title)}" aria-pressed="${selected}" tabindex="${selected ? "0" : "-1"}" data-click="home-shelf-select" data-section-id="${escapeAttr(sectionId)}" data-entry-index="${index}" data-entry-key="${escapeAttr(entryKey(entry, index))}" aria-label="${escapeAttr(`${title}. ${year}. Tipo: ${kind}. ${reason}. Opción ${index + 1}`)}">
          <span class="vhs-spine-sticker" aria-hidden="true"></span>
          <span class="vhs-spine-title">${escapeHtml(title)}</span>
          <span class="vhs-spine-meta" aria-hidden="true"><span class="vhs-spine-year">${escapeHtml(year)}</span><span class="vhs-spine-format">VHS</span></span>
        </button>`;
      }

      function homeFurnitureFrame(imageUrl, title, label) {
        const url = String(imageUrl || "").trim();
        const fallback = `<span class="home-furniture-frame-fallback" role="img" aria-label="${escapeAttr(`${label} no disponible`)}"><b aria-hidden="true">SIN IMAGEN</b></span>`;
        const image = url
          ? `<img data-poster-image src="${escapeAttr(cachedImageSrc(url))}" alt="${escapeAttr(`${label} de ${title}`)}" loading="lazy" decoding="async">${fallback}`
          : fallback;
        return `<span class="home-furniture-frame">${image}</span>`;
      }

      function homeFurnitureFact(label, value) {
        const text = String(value || "Sin dato");
        return `<div><dt>${escapeHtml(label)}</dt><dd title="${escapeAttr(text)}">${escapeHtml(text)}</dd></div>`;
      }

      export function homeShelfPreview(sectionId, entry) {
        const section = homeSectionById(sectionId) || {};
        const sectionAction = section.action || {};
        const item = entry?.item || {};
        const origin = entry?.origin || {};
        const title = displayTitle(item) || "Sin título";
        const reason = entry?.reason || {};
        const genre = firstListValue(item.genres);
        const metadata = [item.kind ? String(item.kind) : "", genre].filter(Boolean);
        const summary = String(
          item.description || item.wikipedia_extract || reason.detail || ""
        ).trim();
        const metadataMarkup = metadata.length
          ? `<p class="home-shelf-preview-meta">${metadata
            .map((value) => `<span>${escapeHtml(value)}</span>`)
            .join("")}</p>`
          : "";
        const duration = homeDurationLabel(item);
        const availability = availabilityState(item);
        const status = item.status === "watched" ? "Vista" : "Pendiente";
        const credits = {
          director: listText(item.directors, 2) || "Sin dato",
          writers: listText(item.writers, 2) || "Sin dato",
          cast: listText(item.cast, 3) || "Sin dato"
        };
        const isCollection = origin.kind === "collection";
        const viewMoreAction = isCollection
          ? `<button type="button" class="home-shelf-preview-action" data-click="open-home-collection-detail" data-key="${escapeAttr(entry?.key || "")}">Ver ficha del Club</button>`
          : `<button type="button" class="home-shelf-preview-action" data-click="open-detail-with-case-transition" data-id="${escapeAttr(item.id || "")}">Ver más</button>`;
        const editAction = isCollection
          ? ""
          : `<button type="button" class="quiet-action home-shelf-preview-action" data-click="edit-home-shelf-entry" data-id="${escapeAttr(item.id || "")}">Editar mi ficha</button>`;
        const frames = [
          homeFurnitureFrame(item.backdrop_image, title, "Imagen panorámica"),
          homeFurnitureFrame(item.page_image, title, "Imagen de portada")
        ].join("");
        const categoryAction = sectionAction.kind
          ? `<button class="home-furniture-category-action" type="button" data-click="home-section-action" data-section-id="${escapeAttr(sectionId)}">${escapeHtml(sectionAction.label || "Ver colección")}</button>`
          : "";
        return `<aside class="home-shelf-preview vhs-case" data-vhs-state="open" data-home-shelf-preview="${escapeAttr(sectionId)}" data-selected-entry-key="${escapeAttr(entry?.key || "")}" data-selected-item-id="${escapeAttr(item.id || "")}" aria-labelledby="home-shelf-preview-${escapeAttr(sectionId)}">
          <div class="home-furniture-action-panel">
            <div class="home-shelf-preview-actions">${viewMoreAction}${editAction}</div>
          </div>
          <div class="home-furniture-display">
            <div class="home-furniture-display-heading">
              <p><span>Categoría activa</span><strong>${escapeHtml(section.title || "Selección")}</strong></p>
              ${categoryAction}
            </div>
            <div class="home-furniture-display-body">
              <div class="home-shelf-preview-copy">
                ${isCollection ? `<span>En ${escapeHtml(origin.collection_title || "una colección seguida")}</span>` : ""}
                <h3 id="home-shelf-preview-${escapeAttr(sectionId)}"><span>${escapeHtml(title)}</span>${item.year ? `<small>(${escapeHtml(String(item.year))})</small>` : ""}</h3>
                ${metadataMarkup}
                <p class="home-shelf-preview-summary">${escapeHtml(summary || "Abrí la ficha para completar la información de esta obra.")}</p>
              </div>
              <div class="home-furniture-frame-strip">${frames}</div>
              <section class="home-furniture-credit-status" aria-label="Créditos y estado resumido">
                <dl class="home-furniture-credits">
                  ${homeFurnitureFact("Dirección", credits.director)}
                  ${homeFurnitureFact("Guion", credits.writers)}
                  ${homeFurnitureFact("Reparto", credits.cast)}
                </dl>
                <dl class="home-shelf-preview-facts">
                  ${homeFurnitureFact("Acceso", availability.effective ? "Disponible" : "No disponible")}
                  ${homeFurnitureFact("Estado", status)}
                  ${homeFurnitureFact("Duración", duration)}
                </dl>
                <span class="home-furniture-format-signature" aria-hidden="true">VHS</span>
              </section>
            </div>
          </div>
        </aside>`;
      }

      export function renderHomeShelfPreview() {
        if (!fields.homeShelfPreview) return;
        const sectionId = activeHomeSectionId || "active";
        const entry = homeShelfEntryForSelection(sectionId);
        fields.homeShelfPreview.innerHTML = entry
          ? homeShelfPreview(sectionId, entry)
          : "";
        fields.homeShelfPreview.hidden = !entry;
        syncHomeShelfPreviewPlacement();
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

      export function homeDatePeriodLabel(value) {
        if (value === localDateOffset(-1)) return "Ayer";
        if (!value || value === todayLocalDate()) return "Hoy";
        return "Archivo";
      }

      function homeDateControlMarkup() {
        const selected = editorialHome.generated_for || todayLocalDate();
        const todaySelected = selected === todayLocalDate();
        const yesterdaySelected = selected === localDateOffset(-1);
        return `<div class="spotlight-date-control spotlight-date-control-desktop" data-home-date-control>
          <span class="spotlight-date-control-label">Programación</span>
          <div class="spotlight-date-tabs" role="group" aria-label="Día de las recomendaciones">
            <button type="button" data-click="home-date-today" aria-pressed="${todaySelected}">Hoy</button>
            <button type="button" data-click="home-date-yesterday" aria-pressed="${yesterdaySelected}">Ayer</button>
          </div>
          <time class="spotlight-date" data-home-date-label datetime="${escapeAttr(selected)}">${escapeHtml(homeDateLabel(selected))}</time>
        </div>`;
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
        document.querySelectorAll('[data-click="home-date-today"]').forEach((button) => {
          button.setAttribute("aria-pressed", String(selected === todayLocalDate()));
        });
        document.querySelectorAll('[data-click="home-date-yesterday"]').forEach((button) => {
          button.setAttribute("aria-pressed", String(selected === localDateOffset(-1)));
        });
        document.querySelectorAll("#homeDate, [data-home-date-label]").forEach((time) => {
          time.dateTime = selected;
          time.textContent = homeDateLabel(selected);
        });
      }

      function setHomeDateControlsDisabled(disabled) {
        document.querySelectorAll('[data-click="home-date-today"], [data-click="home-date-yesterday"]').forEach((button) => {
          button.disabled = disabled;
        });
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
        setHomeDateControlsDisabled(true);
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
          setHomeDateControlsDisabled(false);
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
