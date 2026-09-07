import { availabilityState, displayTitle, escapeAttr, escapeHtml, listText, normalizeRating } from "./format.js";

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

function fact(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "Sin dato")}</dd></div>`;
}

function framePlaceholder(title, number) {
  return `<div class="vhs-back-cover-frame vhs-back-cover-frame-${number}" role="img" aria-label="Fotograma ${number} de ${escapeAttr(title)} no disponible">
    <span>Fotograma ${String(number).padStart(2, "0")}</span>
    <strong>No disponible</strong>
  </div>`;
}

export function renderBackCover(item) {
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
          <p>${escapeHtml([item?.year, duration, genres].filter(Boolean).join(" · "))}</p>
        </header>

        <section class="vhs-back-cover-synopsis" aria-labelledby="back-cover-synopsis-${accessibleKey}">
          <h3 id="back-cover-synopsis-${accessibleKey}">Sinopsis</h3>
          <p>${escapeHtml(synopsis)}</p>
        </section>

        <div class="vhs-back-cover-frames" aria-label="Espacios reservados para fotogramas">
          ${framePlaceholder(title, 1)}
          ${framePlaceholder(title, 2)}
        </div>

        <section class="vhs-back-cover-credits" aria-labelledby="back-cover-credits-${accessibleKey}">
          <h3 id="back-cover-credits-${accessibleKey}">Créditos</h3>
          <dl>
            ${fact("Dirección", directors)}
            ${fact("Guion", writers)}
            ${fact("Reparto", cast)}
          </dl>
        </section>

        <section class="vhs-back-cover-facts" aria-label="Datos de la edición">
          <dl>
            ${fact("Año", item?.year || "Sin dato")}
            ${fact("Tipo", item?.kind || "Sin dato")}
            ${fact("Duración", duration)}
            ${fact("Géneros", genres)}
            ${fact("Disponibilidad", availability.effective ? "Disponible" : "No disponible")}
          </dl>
        </section>

        <section class="vhs-back-cover-memory" aria-labelledby="back-cover-memory-${accessibleKey}">
          <div>
            <h3 id="back-cover-memory-${accessibleKey}">Memoria personal</h3>
            <p>${escapeHtml(memorySummary)}</p>
          </div>
          <dl>
            ${fact("Estado", watched ? "Vista" : "Pendiente")}
            ${fact("Fecha", item?.watched_at || "Sin fecha")}
            ${fact("Puntaje", rating ? `${rating}/10` : "Sin puntuar")}
          </dl>
        </section>

        <footer class="vhs-back-cover-footer">
          <span aria-hidden="true" class="vhs-back-cover-barcode"></span>
          <p>Contratapa generada con datos de tu catálogo. Los espacios de fotograma no representan imágenes reales.</p>
          <strong>VHS</strong>
        </footer>
      </div>
    </div>
  </article>`;
}
