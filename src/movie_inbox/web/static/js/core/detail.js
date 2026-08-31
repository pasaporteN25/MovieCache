import { cachedImageSrc, card, posterVariant } from "./card.js";
import { load, loadCatalog } from "./catalog-data.js";
import { fields } from "./fields.js";
import { asList, availabilityState, displayTitle, escapeAttr, escapeHtml, firstListValue, listText, localFilesText, meta, normalizeRating, titleSubtitle } from "./format.js";
import { apiFetch } from "./http.js";
import { syncRoute } from "./router.js";
import { findLinkForItem } from "./search-bridge.js";
import { items, privacyPreferences } from "./state.js";
import { catalogDetailItems, randomCandidates } from "../surfaces/catalog-grid.js";
import { activeQuery, catalogMergeResults } from "../surfaces/catalog-search.js";
import { editorialPersonalIds } from "../surfaces/home.js";

      export let selectedDetailId = "";

      export let detailReturnFocus = null;

      export let detailReturnCardId = "";

      export let detailNavigationIds = [];

      export let detailNavigationMode = "catalog";

      export let detailNavigationLabel = "Colección";

      export let detailPersonalEditing = false;

      export let detailDirtyScopes = new Set();

      export let detailFeedbackState = { message: "", tone: "" };

      export let detailFeedbackTimer = null;

      export let pendingDetailTransition = null;

      export function openRandomDetail() {
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
              label: fields.randomCatalogOnly.checked ? "Al azar · Disponibles" : "Al azar · Todo",
              ids: candidates.map((candidate) => candidate.id)
            }
          });
        }
      }

      export function detailContextForTrigger(target) {
        if (target.closest("#homeView")) {
          return {
            mode: "home",
            label: "Inicio",
            ids: editorialPersonalIds()
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

      export function openDetailFromTrigger(target, id) {
        openDetail(id, { context: detailContextForTrigger(target) });
      }

      export function personalRecordPanel(item) {
        if (detailPersonalEditing) return personalRecordEditor(item);
        const rating = normalizeRating(item.rating);
        const review = String(item.review || "").trim();
        const privacy = item._privacy || {};
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
              <dd>${rating ? `${rating}/10` : "Sin puntuar"} ${personalVisibilityBadge("rating", privacy.rating)}</dd>
            </div>
          </dl>
          <div class="personal-review-read">
            <span>Review ${personalVisibilityBadge("review", privacy.review)}</span>
            <p>${escapeHtml(review || "Sin review")}</p>
          </div>
        </div>`;
      }

      export function personalRecordEditor(item) {
        const rating = normalizeRating(item.rating);
        const privacy = item._privacy || {};
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
            <fieldset class="personal-privacy-fields">
              <legend>Visibilidad en el Club</legend>
              <label>
                Puntaje
                <select name="rating_privacy" data-personal-rating-privacy>
                  ${personalPrivacyOptions("rating", privacy.rating)}
                </select>
              </label>
              <label>
                Review
                <select name="review_privacy" data-personal-review-privacy>
                  ${personalPrivacyOptions("review", privacy.review)}
                </select>
              </label>
              <small>Estos ajustes reemplazan tu preferencia general solamente para esta obra.</small>
            </fieldset>
            <div class="personal-actions">
              <button type="button" data-click="save-personal" data-detail-save data-id="${escapeAttr(item.id)}">Guardar cambios</button>
              <button class="quiet-action" type="button" data-click="cancel-personal" data-id="${escapeAttr(item.id)}">Cancelar</button>
            </div>
          </div>
        </div>`;
      }

      export function personalPrivacyOptions(field, selectedMode = "inherit") {
        const inheritedShared = field === "rating"
          ? Boolean(privacyPreferences.share_rating)
          : Boolean(privacyPreferences.share_review);
        const selected = ["inherit", "shared", "private"].includes(selectedMode)
          ? selectedMode
          : "inherit";
        const options = [
          ["inherit", `Heredar (${inheritedShared ? "compartido" : "privado"})`],
          ["shared", "Compartir esta obra"],
          ["private", "Mantener privada"]
        ];
        return options.map(([value, label]) => (
          `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`
        )).join("");
      }

      export function personalVisibilityBadge(field, mode = "inherit") {
        const inheritedShared = field === "rating"
          ? Boolean(privacyPreferences.share_rating)
          : Boolean(privacyPreferences.share_review);
        const shared = mode === "shared" || (mode !== "private" && inheritedShared);
        const label = privacyPreferences.catalog_shared && shared ? "Visible en Club" : "Privado";
        return `<small class="personal-visibility ${label === "Privado" ? "is-private" : "is-shared"}">${label}</small>`;
      }

      export function factsPanel(item) {
        const rows = [
          ["Género", item.genres, 4],
          ["Estreno", primaryReleaseDateLabel(item), 1],
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

      export function primaryReleaseDateLabel(item) {
        const dates = Array.isArray(item?.release_dates) ? item.release_dates : [];
        const selected = dates.find((entry) => entry?.is_primary) || dates[0];
        return selected ? releaseDateLabel(selected) : "";
      }

      export function releaseDateLabel(entry) {
        const raw = String(entry?.date || "");
        const [year, month, day] = raw.split("-");
        const months = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
        let label = year || "Fecha desconocida";
        if (entry?.precision === "month" && month) label = `${months[Number(month) - 1] || month} de ${year}`;
        if (entry?.precision === "day" && month && day) label = `${Number(day)} de ${months[Number(month) - 1] || month} de ${year}`;
        if (entry?.country) label += ` · ${entry.country}`;
        return label;
      }

      export function availabilityPanel(item) {
        const localText = localFilesText(item);
        const duplicates = Number(item._duplicate_count || 0);
        const state = availabilityState(item);
        const sourceText = (state.details.sources || [])
          .map((source) => `${source.library_name} (${source.file_count})`)
          .join(" · ");
        const fileLabel = `${state.fileCount} ${state.fileCount === 1 ? "archivo verificado" : "archivos verificados"}`;
        return `<div class="availability-panel">
          <dl class="availability-list">
            <div><dt>Disponibilidad</dt><dd>${state.effective ? "Disponible" : "No disponible"} · ${escapeHtml(state.origin)}</dd></div>
            <div><dt>Declaración manual</dt><dd>${state.manual ? "Activa" : "Inactiva"}</dd></div>
            <div><dt>Inventario del servidor</dt><dd>${state.server ? fileLabel : "Sin archivos vinculados"}</dd></div>
            ${sourceText ? `<div><dt>Bibliotecas</dt><dd>${escapeHtml(sourceText)}</dd></div>` : ""}
            ${localText ? `<div><dt>Archivos heredados</dt><dd>${escapeHtml(localText)}</dd></div>` : ""}
            <div><dt>Fuente de metadata</dt><dd>${escapeHtml(item.source || "Sin fuente")}</dd></div>
            ${duplicates ? `<div><dt>Duplicados</dt><dd>${escapeHtml(`${duplicates} coincidencia(s): ${item._duplicate_reason || "misma obra"}`)}</dd></div>` : ""}
          </dl>
          <button class="drawer-secondary-action" type="button" data-click="toggle-catalog" data-id="${escapeAttr(item.id)}" aria-pressed="${state.manual}">
            ${state.manual ? "Quitar declaración manual" : "Declarar disponibilidad manual"}
          </button>
        </div>`;
      }

      export function openDetail(id, { updateHistory = true, context = null, skipGuard = false } = {}) {
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
        clearDetailFeedback();
        renderDetail({ force: true });
        fields.detailBody.scrollTop = 0;
        if (!fields.detailDrawer.open) fields.detailDrawer.showModal();
        document.body.classList.add("drawer-open");
        if (updateHistory) syncRoute({ movie: id }, "push");
        requestAnimationFrame(() => fields.closeDetail.focus());
      }

      export function closeDetail({ restoreFocus = true, updateHistory = true, skipGuard = false } = {}) {
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

      export function setDetailContext(context, selectedId) {
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

      export function uniqueExistingIds(values) {
        const valid = new Set(items.map((item) => item.id));
        return [...new Set(values)].filter((id) => valid.has(id));
      }

      export function renderDetailNavigation() {
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

      export function navigateDetail(offset) {
        const index = detailNavigationIds.indexOf(selectedDetailId);
        const nextId = detailNavigationIds[index + offset];
        if (!nextId) return;
        requestDetailTransition(() => showDetailFromQueue(nextId));
      }

      export function showDetailFromQueue(id) {
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

      export function openAnotherRandomDetail() {
        const candidates = randomCandidates().filter((item) => item.id !== selectedDetailId);
        if (!candidates.length) return;
        const item = candidates[Math.floor(Math.random() * candidates.length)];
        requestDetailTransition(() => {
          detailNavigationIds = randomCandidates().map((candidate) => candidate.id);
          detailNavigationLabel = fields.randomCatalogOnly.checked ? "Al azar · Disponibles" : "Al azar · Todo";
          showDetailFromQueue(item.id);
        });
      }

      export function renderDetail({ force = false } = {}) {
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
        const availability = availabilityState(item);
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
          <section class="drawer-quick-actions" aria-label="Estado y disponibilidad">
            <button class="drawer-state ${watched ? "active" : ""}" type="button" data-click="toggle-watched" data-id="${escapeAttr(item.id)}" data-status="${escapeAttr(item.status || "to_watch")}" aria-pressed="${watched}">
              <span>Estado</span><strong>${watched ? "Vista" : "Pendiente"}</strong><small>${item.watched_at ? escapeHtml(item.watched_at) : "Sin fecha"}</small>
            </button>
            <div class="drawer-state ${availability.effective ? "active" : ""}">
              <span>Disponibilidad</span><strong>${availability.effective ? "Disponible" : "No disponible"}</strong><small>${escapeHtml(availability.origin)}</small>
            </div>
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
              <p>Eliminar quita esta ficha del catálogo personal. No borra videos ni el inventario del servidor; otra ficha equivalente puede conservar la disponibilidad.</p>
              <button class="danger" type="button" data-click="delete-item" data-id="${escapeAttr(item.id)}">Eliminar del catálogo</button>
            </div>
          </details>
        `;
        primeDetailForms();
        syncDetailFeedback();
      }

      export function drawerPoster(item, title) {
        const placeholder = `<div class="drawer-poster drawer-poster-placeholder poster-${posterVariant(item.id || title)}" aria-hidden="true"><span>Movie Inbox</span><strong>${escapeHtml(title)}</strong></div>`;
        const image = item.page_image
          ? `<img class="drawer-poster" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="Portada de ${escapeAttr(title)}" loading="eager" fetchpriority="high" decoding="async">`
          : "";
        return `<div class="drawer-poster-frame">${image}${placeholder}</div>`;
      }

      export function editPersonalRecord() {
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

      export function cancelPersonalEdit() {
        detailDirtyScopes.delete("personal");
        detailPersonalEditing = false;
        renderDetail({ force: true });
      }

      export function detailLinks(item) {
        const links = [
          item.url ? `<a href="${escapeAttr(item.url)}" target="_blank" rel="noreferrer">Abrir link</a>` : "",
          item.wikipedia_url ? `<a href="${escapeAttr(item.wikipedia_url)}" target="_blank" rel="noreferrer">Wikipedia</a>` : "",
          item.imdb_url ? `<a href="${escapeAttr(item.imdb_url)}" target="_blank" rel="noreferrer">IMDb</a>` : "",
          item.filmaffinity_url ? `<a href="${escapeAttr(item.filmaffinity_url)}" target="_blank" rel="noreferrer">FilmAffinity</a>` : "",
          item.myanimelist_url ? `<a href="${escapeAttr(item.myanimelist_url)}" target="_blank" rel="noreferrer">MyAnimeList</a>` : "",
          item.wikidata_id ? `<a href="https://www.wikidata.org/wiki/${escapeAttr(item.wikidata_id)}" target="_blank" rel="noreferrer">Wikidata</a>` : ""
        ].filter(Boolean).join("");
        return links || `<span class="status-line">Sin referencias asociadas.</span>`;
      }

      export function metadataEditor(item) {
        const rows = [
          ["Titulo", "title", "text"],
          ["Original", "original_title", "text"],
          ["Español", "spanish_title", "text"],
          ["Inglés", "english_title", "text"],
          ["Alternativos", "alternative_titles", "text"],
          ["Tipo", "kind", "kind"],
          ["Año", "year", "text"],
          ["Descripción", "description", "textarea"],
          ["Generos", "genres", "text"],
          ["Directores", "directors", "text"],
          ["Guionistas", "writers", "text"],
          ["Reparto", "cast", "text"],
          ["TMDB ID", "tmdb_id", "text"],
          ["MyAnimeList ID", "mal_id", "text"],
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

      export function metadataEditorRow(item, label, field, control) {
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

      export function primeDetailForms() {
        fields.detailBody.querySelectorAll("[data-detail-form]").forEach((form) => {
          form.dataset.initial = serializeDetailForm(form);
        });
      }

      export function serializeDetailForm(form) {
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

      export function handleDetailFormMutation(event) {
        const form = event.target.closest("[data-detail-form]");
        if (!form) return;
        const scope = form.dataset.detailForm;
        if (serializeDetailForm(form) === form.dataset.initial) detailDirtyScopes.delete(scope);
        else detailDirtyScopes.add(scope);
        syncDetailFeedback();
      }

      export function hasUnsavedDetailChanges() {
        return detailDirtyScopes.size > 0;
      }

      export function handleBeforeUnload(event) {
        if (!hasUnsavedDetailChanges()) return;
        event.preventDefault();
        event.returnValue = "";
      }

      export function setDetailFeedback(message, tone = "", timeout = 2400) {
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

      export function clearDetailFeedback() {
        if (detailFeedbackTimer) window.clearTimeout(detailFeedbackTimer);
        detailFeedbackTimer = null;
        detailFeedbackState = { message: "", tone: "" };
        syncDetailFeedback();
      }

      export function syncDetailFeedback() {
        if (!fields.detailFeedback) return;
        const dirty = hasUnsavedDetailChanges();
        fields.detailFeedback.textContent = dirty
          ? `Cambios sin guardar · ${detailDirtyScopes.size}`
          : detailFeedbackState.message;
        fields.detailFeedback.dataset.tone = dirty ? "dirty" : detailFeedbackState.tone;
        fields.detailDrawer.classList.toggle("has-dirty-detail", dirty);
      }

      export function requestDetailTransition(action) {
        if (!hasUnsavedDetailChanges()) {
          action();
          return;
        }
        pendingDetailTransition = action;
        if (!fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.showModal();
        requestAnimationFrame(() => fields.saveDetailChanges.focus());
      }

      export function keepEditingDetail() {
        pendingDetailTransition = null;
        if (fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.close();
        if (selectedDetailId) syncRoute({ movie: selectedDetailId }, "replace");
        requestAnimationFrame(() => fields.detailBody.querySelector("[data-detail-form] input, [data-detail-form] select, [data-detail-form] textarea")?.focus());
      }

      export function discardDetailChanges() {
        const transition = pendingDetailTransition;
        pendingDetailTransition = null;
        detailDirtyScopes.clear();
        detailPersonalEditing = false;
        if (fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.close();
        syncDetailFeedback();
        transition?.();
      }

      export async function saveDetailChanges() {
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

      export async function saveDirtyDetailForms() {
        const personal = fields.detailBody.querySelector("[data-detail-form='personal']");
        const metadata = fields.detailBody.querySelector("[data-detail-form='metadata']");
        if (detailDirtyScopes.has("personal") && !await persistPersonalForm(personal, selectedDetailId)) return false;
        detailDirtyScopes.delete("personal");
        if (detailDirtyScopes.has("metadata") && !await persistMetadataForm(metadata, selectedDetailId)) return false;
        detailDirtyScopes.delete("metadata");
        syncDetailFeedback();
        return true;
      }

      export async function deleteCatalogItem(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        const title = item?.title || item?.local_name || "Sin título";
        const confirmed = confirm(
          `¿Eliminar "${title}" del catálogo personal?\n\nNo se borrarán videos ni el inventario del servidor.`
        );
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

      export async function savePersonal(event, id) {
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

      export async function persistPersonalForm(form, id) {
        const item = items.find((entry) => entry.id === id);
        if (!item || !form) return false;
        const watchedAt = form.querySelector("[data-personal-watched-at]")?.value || "";
        const rating = normalizeRating(form.querySelector("[data-personal-rating]")?.value);
        const review = form.querySelector("[data-personal-review]")?.value || "";
        const ratingPrivacy = form.querySelector("[data-personal-rating-privacy]")?.value || "inherit";
        const reviewPrivacy = form.querySelector("[data-personal-review-privacy]")?.value || "inherit";
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
          const privacyResponse = await apiFetch(`/api/privacy/items/${encodeURIComponent(id)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ rating: ratingPrivacy, review: reviewPrivacy })
          });
          const privacyPayload = await privacyResponse.json();
          if (!privacyResponse.ok || !privacyPayload.ok) {
            throw new Error(privacyPayload.reason || "No se pudo guardar la privacidad");
          }
          item._privacy = privacyPayload.privacy || { rating: ratingPrivacy, review: reviewPrivacy };
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

      export async function saveMetadata(event, id) {
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

      export async function persistMetadataForm(editor, id) {
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

      export async function findLinkForCatalog(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        if (fields.detailDrawer.open) closeDetail({ restoreFocus: false, updateHistory: false, skipGuard: true });
        await findLinkForItem(item);
      }
