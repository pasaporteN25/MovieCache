import { longDate, ratingStarsRead } from "./personal-controls.js";
import { availabilityState, displayTitle, escapeAttr, escapeHtml, kindLabel, listText, normalizeRating } from "./format.js";
import { renderBackCoverImages } from "./back-cover-images.js";

export const BACK_COVER_TEMPLATES = Object.freeze([
  "rental-classic",
  "episode-collage",
  "studio-triptych",
  "midnight-noir",
  "archive-grid"
]);

export function stableOpaqueIdHash(value) {
  const text = String(value ?? "");
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash;
}

export function backCoverTemplateForId(id) {
  return BACK_COVER_TEMPLATES[stableOpaqueIdHash(id) % BACK_COVER_TEMPLATES.length];
}

let synopsisResizeObserver;

export function mountBackCoverSynopsis(host) {
  synopsisResizeObserver?.disconnect();
  synopsisResizeObserver = undefined;
  if (!host) return;
  const section = host.querySelector(".vhs-back-cover-synopsis");
  const paragraph = section?.querySelector("p");
  const button = section?.querySelector("[data-click='toggle-back-cover-synopsis']");
  const content = host.querySelector(".vhs-back-cover-content");
  if (!section || !paragraph || !button || !content) return;

  section.dataset.clamped = "true";
  const sync = () => {
    if (!host.isConnected) return;
    const expanded = button.getAttribute("aria-expanded") === "true";
    if (expanded) paragraph.classList.remove("is-expanded");
    const overflows = paragraph.scrollHeight > paragraph.clientHeight + 1;
    if (expanded) paragraph.classList.add("is-expanded");
    button.hidden = !overflows;
    if (!overflows && expanded) {
      paragraph.classList.remove("is-expanded");
      button.setAttribute("aria-expanded", "false");
      button.textContent = "Leer más";
    }
  };
  synopsisResizeObserver = new ResizeObserver(sync);
  synopsisResizeObserver.observe(content);
  document.fonts.ready.then(sync);
  requestAnimationFrame(sync);
}

export function toggleBackCoverSynopsis(button) {
  const section = button.closest(".vhs-back-cover-synopsis");
  const paragraph = section?.querySelector("p");
  if (!paragraph) return;
  const expanded = button.getAttribute("aria-expanded") === "true";
  paragraph.classList.toggle("is-expanded", !expanded);
  button.setAttribute("aria-expanded", String(!expanded));
  button.textContent = expanded ? "Leer más" : "Leer menos";
  if (expanded) {
    button.focus({ preventScroll: true });
    button.scrollIntoView({ block: "nearest", behavior: "instant" });
  }
}

function fact(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "Sin dato")}</dd></div>`;
}

export function renderBackCover(item, { editable = false } = {}) {
  const title = displayTitle(item) || "Sin título";
  const template = backCoverTemplateForId(item?.id);
  const accessibleKey = stableOpaqueIdHash(item?.id).toString(36);
  const synopsis = String(item?.wikipedia_extract || item?.description || "").trim()
    || "Todavía no hay una sinopsis disponible para esta obra.";
  const availability = availabilityState(item);
  const rating = normalizeRating(item?.rating);
  const watched = item?.status === "watched";
  const duration = Number(item?.duration_minutes || 0) > 0
    ? `${Number(item.duration_minutes)} min`
    : "Sin dato";
  const directors = listText(item?.directors, 3) || "Sin dato";
  const writers = listText(item?.writers, 4) || "Sin dato";
  const cast = listText(item?.cast, 6) || "Sin dato";
  const genres = listText(item?.genres, 4) || "Sin dato";
  const review = String(item?.review || "").trim();
  const memorySummary = review || String(item?.notes || "").trim() || (watched
    ? "Vista, todavía sin una memoria escrita."
    : "Pendiente, todavía sin una memoria escrita.");

  return `<article class="vhs-back-cover vhs-back-cover--${template}" data-back-cover-template="${escapeAttr(template)}" data-item-id="${escapeAttr(item?.id || "")}">
    <div class="vhs-back-cover-shell">
      <div class="vhs-back-cover-content" role="region" tabindex="0" aria-label="Contenido completo de la contratapa de ${escapeAttr(title)}">
        <header class="vhs-back-cover-heading">
          <span>Movie Inbox // archivo personal</span>
          <h2>${escapeHtml(title)}</h2>
        </header>

        <section class="vhs-back-cover-synopsis" aria-labelledby="back-cover-synopsis-${accessibleKey}">
          <h3 id="back-cover-synopsis-${accessibleKey}">Sinopsis</h3>
          <p id="back-cover-synopsis-text-${accessibleKey}">${escapeHtml(synopsis)}</p>
          <button class="vhs-back-cover-read-more" type="button" data-click="toggle-back-cover-synopsis" aria-controls="back-cover-synopsis-text-${accessibleKey}" aria-expanded="false" hidden>Leer más</button>
        </section>

        <div class="vhs-back-cover-edition">
          ${renderBackCoverImages(item, title)}
          <div class="vhs-back-cover-metadata">
            <section class="vhs-back-cover-facts" aria-label="Datos de la edición">
              <dl>
                ${fact("Año", item?.year || "Sin dato")}
                ${fact("Tipo", kindLabel(item?.kind) || "Sin dato")}
                ${fact("Duración", duration)}
                ${fact("Géneros", genres)}
                ${fact("Disponibilidad", availability.effective ? "Disponible" : "No disponible")}
              </dl>
            </section>

            <section class="vhs-back-cover-credits" aria-labelledby="back-cover-credits-${accessibleKey}">
              <h3 id="back-cover-credits-${accessibleKey}">Créditos</h3>
              ${[directors, writers, cast].every(value => value === "Sin dato") ? "<p>Créditos sin completar.</p>" : `<dl>
                ${fact("Dirección", directors)}
                ${fact("Guion", writers)}
                ${fact("Reparto", cast)}
              </dl>`}
            </section>

          </div>
        </div>

        <section class="vhs-back-cover-memory" aria-labelledby="back-cover-memory-${accessibleKey}">
          <div>
            <h3 id="back-cover-memory-${accessibleKey}">Mi registro</h3>
            <p>${escapeHtml(memorySummary)}</p>
          </div>
          <dl>
            ${fact("Estado", watched ? "Vista" : "Pendiente")}
            ${fact("Fecha", longDate(item?.watched_at) || item?.watched_at || "Sin fecha")}
            <div><dt>Puntaje</dt><dd>${ratingStarsRead(rating)}</dd></div>
          </dl>
          ${editable ? `<button class="vhs-edit-sticker" type="button" data-click="edit-vhs-dossier" aria-label="Movie Inbox · Editar ficha de ${escapeAttr(title)}"><img src="/static/img/brand/movie-inbox-sticker-256.webp" srcset="/static/img/brand/movie-inbox-sticker-256.webp 1x, /static/img/brand/movie-inbox-sticker-512.webp 2x" alt="Movie Inbox — Editar ficha" width="256" height="192"></button>` : ""}
        </section>

        <footer class="vhs-back-cover-footer">
          <span aria-hidden="true" class="vhs-back-cover-barcode"></span>
          <p>Contratapa generada con datos e imágenes de tu catálogo.</p>
          <strong>VHS</strong>
        </footer>
      </div>
    </div>
  </article>`;
}
