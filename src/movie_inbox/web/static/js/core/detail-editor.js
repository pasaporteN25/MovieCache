import { availabilityState, displayTitle, escapeAttr, escapeHtml } from "./format.js";
import { availabilityIcon, streamingSignal } from "./detail-context.js";

export const EDITOR_SECTIONS = [
  ["personal", "Mi registro"], ["data", "Datos de la obra"],
  ["images", "Imágenes"], ["availability", "Disponibilidad y enlaces"],
  ["advanced", "Opciones avanzadas"]
];

export function renderDetailEditor(item, parts) {
  const title = displayTitle(item) || "Sin título";
  const id = escapeAttr(item.id);
  const state = availabilityState(item);
  const stateControl = `<div class="vhs-record-state"><span>Estado</span><button type="button" data-click="toggle-watched" data-id="${id}" data-status="${escapeAttr(item.status || "to_watch")}" aria-pressed="${item.status === "watched"}">${item.status === "watched" ? "✓ Vista · Marcar pendiente" : "Pendiente · Marcar vista"}</button><small>El estado se aplica al tocar el botón.</small></div>`;
  const rows = definitions => definitions.map(([label, field, control = "text"]) => parts.metadataEditorRow(item, label, field, control)).join("");
  return `<div class="vhs-editor">
    <nav class="vhs-editor-nav" aria-label="Secciones de la ficha">
      <img class="vhs-editor-logo" src="/static/img/brand/movie-inbox-logo-256.webp" alt="Movie Inbox" width="256" height="192">
      ${EDITOR_SECTIONS.map(([key, label]) => `<button type="button" data-click="detail-section" data-section="${key}" aria-controls="editor-${key}">${label}</button>`).join("")}
    </nav>
    <div class="vhs-editor-workspace">
      <div class="vhs-editor-content">
        <section data-editor-section="personal" id="editor-personal" aria-label="Mi registro">
          <div class="vhs-personal-layout"><div>
            ${parts.personalRecordEditor(item).replace('<div class="personal-grid">', `<div class="personal-grid">${stateControl}`)}
          </div><aside class="vhs-editor-preview" aria-label="Portada de la obra">${parts.drawerPoster(item, title)}</aside></div>
        </section>
        <div class="vhs-metadata-form" data-detail-form="metadata" data-id="${id}">
          <section data-editor-section="data" id="editor-data" aria-label="Datos de la obra" hidden>
            <h3>Datos de la obra</h3><p class="vhs-section-intro">Títulos, sinopsis y créditos de tu edición.</p>
            <div class="vhs-fields">${rows([
              ["Título", "title"], ["Tipo", "kind", "kind"], ["Año", "year"], ["Duración (minutos)", "duration_minutes"],
              ["Título original", "original_title"], ["Título en español", "spanish_title"], ["Título en inglés", "english_title"], ["Títulos alternativos", "alternative_titles"],
              ["Sinopsis", "description", "textarea"], ["Géneros", "genres"], ["Dirección", "directors"], ["Guion", "writers"], ["Reparto", "cast"]
            ])}</div>
            <details class="vhs-secondary"><summary>Sinopsis de Wikipedia</summary><p>La contratapa usa este texto cuando está disponible.</p>${rows([["Extracto de Wikipedia", "wikipedia_extract", "textarea"]])}</details>
          </section>
          <section data-editor-section="images" id="editor-images" aria-label="Imágenes" hidden>
            <h3>Imágenes</h3><p class="vhs-section-intro">Portada y panorámica de esta obra. Pegá la dirección de la imagen o dejala vacía para usar la caja sin portada.</p>
            <div class="vhs-image-edit-preview">${parts.drawerPoster(item, title)}</div>
            <div class="vhs-fields">${rows([["URL de la portada", "page_image"], ["URL de la imagen panorámica", "backdrop_image"]])}</div>
            <p class="vhs-section-intro">La vista previa se actualiza al guardar.</p>
          </section>
          <section data-editor-section="advanced" id="editor-advanced" aria-label="Opciones avanzadas" hidden>
            <h3>Opciones avanzadas</h3><p class="vhs-section-intro">Identificadores externos y mantenimiento. Cada campo editable tiene su procedencia y bloqueo dentro de «Origen y bloqueo».</p>
            <div class="vhs-fields">${rows([["TMDB ID", "tmdb_id"], ["MyAnimeList ID", "mal_id"]])}</div>
            <details class="vhs-secondary danger-zone"><summary>Eliminar del catálogo</summary><p>Quita esta entrada de tu catálogo personal. No borra videos ni el inventario del servidor.</p><button class="danger" type="button" data-click="delete-item" data-id="${id}">Eliminar del catálogo</button></details>
          </section>
          <span class="status-line" data-metadata-status role="status"></span>
        </div>
        <section data-editor-section="availability" id="editor-availability" aria-label="Disponibilidad y enlaces" hidden>
          <h3>Disponibilidad y enlaces</h3><p class="vhs-section-intro">Tu biblioteca, opciones de streaming y referencias de la obra.</p>
          <div class="drawer-access"><span class="detail-access-signal${state.effective ? " is-available" : ""}">${availabilityIcon("library")}<span>Biblioteca<small>${state.effective ? "Disponible" : "No disponible"}</small></span></span><span data-detail-streaming-signal>${streamingSignal(null, "loading")}</span></div>
          ${parts.availabilityPanel(item)}<div class="links">${parts.detailLinks(item)}</div>
          <button class="drawer-secondary-action" type="button" data-click="find-link" data-id="${id}">Buscar o completar enlaces</button>
          <div class="detail-context" data-detail-context></div>
        </section>
      </div>
      <footer class="vhs-editor-footer"><span data-editor-feedback role="status">Sin cambios pendientes</span><button type="button" class="quiet-action" data-click="return-vhs-back">Cancelar</button><button type="button" data-click="save-editor" data-editor-save disabled>Guardar cambios</button></footer>
    </div>
  </div>`;
}
