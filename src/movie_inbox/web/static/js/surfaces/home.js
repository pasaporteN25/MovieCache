import { cachedImageSrc, card, posterVariant } from "../core/card.js";
import { editorialRevision, loadCatalog, setEditorialRevision } from "../core/catalog-data.js";
import { detailLinks, drawerPoster, factsPanel } from "../core/detail.js";
import { fields } from "../core/fields.js";
import { displayTitle, escapeAttr, escapeHtml, firstListValue, listText, localDateOffset, todayLocalDate } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { goToClub, routeValuesForView, showView, syncRoute } from "../core/router.js";
import { clubMode, setClubMode } from "../core/state.js";
import { applyCollectionFilterDescriptor, render, resetCollectionFilters, setLastEditorialRenderRevision } from "./catalog-grid.js";
import { clearManualSearch } from "./catalog-search.js";
import { closeSharedDetail, openCollection } from "./club.js";

      export let editorialHome = { generated_for: "", featured: [], hero: null, sections: [], warnings: [] };

      export const editorialFeaturedCache = new Map();

      export let spotlightIndex = 0;

      export function setEditorialHome(value) {
        editorialHome = value;
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
        const section = editorialHome.sections.find((entry) => entry.id === sectionId);
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
        const featured = Array.isArray(payload.featured)
          ? payload.featured.filter((entry) => entry && typeof entry === "object").slice(0, 4)
          : payload.hero && typeof payload.hero === "object" ? [payload.hero] : [];
        return {
          generated_for: String(payload.generated_for || todayLocalDate()),
          featured,
          hero: featured[0] || null,
          sections: Array.isArray(payload.sections) ? payload.sections : [],
          warnings: Array.isArray(payload.warnings) ? payload.warnings : [],
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
      }

      export function renderEditorialHero() {
        const featured = editorialHome.featured;
        if (spotlightIndex >= featured.length) spotlightIndex = 0;
        const entry = featured[spotlightIndex];
        const item = entry?.item;
        if (!item) {
          fields.spotlightStage.innerHTML = `<div class="spotlight-empty">
            <strong>La pantalla espera una obra disponible</strong>
            <span>Vinculá un archivo o declará una obra disponible para encabezar la cartelera del día.</span>
          </div>`;
          return;
        }
        const title = displayTitle(item) || "Sin título";
        const reason = entry.reason || {};
        const summary = String(item.description || item.wikipedia_extract || reason.detail || "").trim();
        const metadata = [item.year, firstListValue(item.genres), firstListValue(item.directors)].filter(Boolean);
        const realBackdrop = String(item.backdrop_image || "").trim();
        const poster = String(item.page_image || "").trim();
        const imageUrl = realBackdrop || poster;
        const image = imageUrl
          ? `<img class="spotlight-image ${realBackdrop ? "is-backdrop" : "is-poster-fallback"}" data-spotlight-image src="${escapeAttr(cachedImageSrc(imageUrl))}" alt="" loading="eager" fetchpriority="high" decoding="async">`
          : "";
        const cover = !realBackdrop && poster
          ? `<img class="spotlight-poster" data-spotlight-image src="${escapeAttr(cachedImageSrc(poster))}" alt="Portada de ${escapeAttr(title)}" loading="eager" fetchpriority="high" decoding="async">`
          : "";
        const navigation = featured.length > 1
          ? `<div class="spotlight-navigation" aria-label="Navegar recomendaciones">
              <button class="spotlight-step" type="button" data-click="spotlight-previous" aria-label="Recomendación anterior">&#8249;</button>
              <span>${spotlightIndex + 1} / ${featured.length}</span>
              <button class="spotlight-step" type="button" data-click="spotlight-next" aria-label="Recomendación siguiente">&#8250;</button>
            </div>`
          : "";
        const program = featured.length > 1
          ? `<div class="spotlight-program" aria-label="Recomendaciones del día">
              ${featured.map((candidate, index) => {
                const candidateTitle = displayTitle(candidate.item || {}) || `Recomendación ${index + 1}`;
                return `<button type="button" aria-pressed="${index === spotlightIndex ? "true" : "false"}" data-click="spotlight-select" data-index="${index}">
                  <span>${String(index + 1).padStart(2, "0")}</span>
                  <strong>${escapeHtml(candidateTitle)}</strong>
                </button>`;
              }).join("")}
            </div>`
          : "";
        fields.spotlightStage.innerHTML = `<div class="spotlight-viewport">
          <article class="spotlight-slide poster-${posterVariant(item.id || title)}">
            ${image}${cover}
            <div class="spotlight-copy">
              <span class="spotlight-reason">${escapeHtml(reason.label || "Selección del día")}</span>
              <strong>${escapeHtml(title)}</strong>
              ${metadata.length ? `<span class="spotlight-metadata">${metadata.map(escapeHtml).join(" · ")}</span>` : ""}
              <p>${escapeHtml(summary || "Una obra disponible de tu archivo personal para considerar esta noche.")}</p>
              <button class="spotlight-cta" type="button" data-click="open-detail" data-id="${escapeAttr(item.id)}">Ver ficha</button>
            </div>
          </article>
          ${navigation}
        </div>${program}`;
      }

      export function selectSpotlight(index, restoreFocus = false) {
        if (!editorialHome.featured.length) return;
        spotlightIndex = Math.max(0, Math.min(editorialHome.featured.length - 1, index));
        renderEditorialHero();
        if (restoreFocus && document.body.dataset.inputMethod === "keyboard") {
          fields.spotlightStage.querySelector(`[data-click="spotlight-select"][data-index="${spotlightIndex}"]`)?.focus();
        }
      }

      export function moveSpotlight(offset, action = "") {
        const count = editorialHome.featured.length;
        if (count < 2) return;
        spotlightIndex = (spotlightIndex + offset + count) % count;
        renderEditorialHero();
        if (action && document.body.dataset.inputMethod === "keyboard") {
          fields.spotlightStage.querySelector(`[data-click="${action}"]`)?.focus();
        }
      }

      export function renderEditorialSections() {
        fields.homeSections.innerHTML = editorialHome.sections
          .filter((section) => Array.isArray(section.items) && section.items.length)
          .map((section, sectionIndex) => editorialSection(section, sectionIndex))
          .join("");
      }

      export function editorialSection(section, sectionIndex) {
        const action = section.action || {};
        const actionButton = action.kind
          ? `<button class="quiet-action home-section-action" type="button" data-click="home-section-action" data-section-id="${escapeAttr(section.id || "")}">${escapeHtml(action.label || "Explorar")}</button>`
          : "";
        return `<section class="home-program" data-home-section="${escapeAttr(section.id || "editorial")}" aria-labelledby="home-section-${escapeAttr(section.id || sectionIndex)}">
          <header class="home-program-heading">
            <div>
              <span class="section-kicker">${escapeHtml(section.eyebrow || "Programación personal")}</span>
              <h2 id="home-section-${escapeAttr(section.id || sectionIndex)}">${escapeHtml(section.title || "Selección")}</h2>
              <p>${escapeHtml(section.description || "")}</p>
            </div>
            ${actionButton}
          </header>
          <div class="home-program-grid">
            ${section.items.map((entry, index) => editorialEntry(entry, index, sectionIndex === 0)).join("")}
          </div>
        </section>`;
      }

      export function editorialEntry(entry, index, prioritize) {
        const item = entry?.item || {};
        const origin = entry?.origin || {};
        const options = origin.kind === "collection"
          ? {
              action: "open-home-collection-detail",
              actionId: origin.collection_item_id || item.id || "",
              entryKey: entry.key || "",
              collectionTitle: origin.collection_title || "Colección"
            }
          : {};
        return `<div class="home-editorial-item">${card(item, index, prioritize, options)}</div>`;
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
        spotlightIndex = 0;
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
          editorialHome = normalizeEditorialHome(payload);
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

