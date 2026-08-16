import { displayTitle, escapeAttr, escapeHtml, firstListValue, isInCatalog, meta, normalizeRating, titleSizeClass } from "./format.js";

      export function shuffle(values) {
        const shuffled = [...values];
        for (let index = shuffled.length - 1; index > 0; index -= 1) {
          const swapIndex = Math.floor(Math.random() * (index + 1));
          [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
        }
        return shuffled;
      }

      export function card(item, index = 0, prioritize = false, options = {}) {
        const shownTitle = displayTitle(item);
        const title = shownTitle || "Sin título";
        const titleClass = titleSizeClass(title);
        const rating = normalizeRating(item.rating);
        const watched = item.status === "watched";
        const catalogued = isInCatalog(item.en_catalogo);
        const fromCollection = options.action === "open-home-collection-detail";
        const collectionTitle = String(options.collectionTitle || "Colección");
        const action = options.action || "open-detail";
        const actionId = options.actionId || item.id || "";
        const entryKey = options.entryKey || "";
        const duplicate = Number(item._duplicate_count || 0) > 0
          ? `<span class="dvd-sticker">Duplicada +${escapeHtml(item._duplicate_count)}</span>`
          : "";
        const accessibleStatus = fromCollection
          ? `en la colección ${collectionTitle}, disponible para agregar`
          : `${watched ? "vista" : "pendiente"}, ${catalogued ? "disponible" : "sin disponibilidad"}, ${rating} puntos`;
        const backMeta = [item.year, firstListValue(item.directors)].filter(Boolean).join(" · ") || "Ficha sin completar";
        return `<article class="card dvd-card${fromCollection ? " is-collection-entry" : ""}" data-click="${escapeAttr(action)}" data-id="${escapeAttr(actionId)}" data-key="${escapeAttr(entryKey)}">
          <div class="dvd-flipper" aria-hidden="true">
            <div class="dvd-face dvd-front">
              <div class="dvd-case">
                <span class="dvd-spine"></span>
                <div class="dvd-cover">
                  ${posterArtwork(item, title, prioritize && index < 6)}
                  <span class="dvd-gloss"></span>
                  ${duplicate}
                  <div class="dvd-title-block">
                    <div class="dvd-title-meta">
                      <span>${escapeHtml(item.year || "Año desconocido")}</span>
                      ${rating ? `<strong>${rating}/10</strong>` : ""}
                    </div>
                    <h2 class="${titleClass}">${escapeHtml(title)}</h2>
                    <div class="dvd-front-statuses">
                      ${fromCollection
                        ? `<span class="dvd-front-status collection">Colección</span><span class="dvd-front-status pending">Por agregar</span>`
                        : `<span class="dvd-front-status ${catalogued ? "catalogued" : "muted"}">${catalogued ? "Disponible" : "No disponible"}</span><span class="dvd-front-status ${watched ? "watched" : "pending"}">${watched ? "Vista" : "Pendiente"}</span>`}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="dvd-face dvd-back">
              <div class="dvd-case dvd-back-case">
                <span class="dvd-spine"></span>
                <div class="dvd-back-cover">
                  <div class="dvd-back-header">
                    <span>Archivo nocturno</span>
                    <h2 class="${titleClass}">${escapeHtml(title)}</h2>
                  </div>
                  <p class="dvd-back-summary">${escapeHtml(dvdBackSummary(item))}</p>
                  <p class="dvd-back-meta">${escapeHtml(backMeta)}</p>
                  <div class="dvd-back-statuses">
                    ${fromCollection
                      ? `<span class="active">En ${escapeHtml(collectionTitle)}</span><span>Fuera de tu catálogo</span><strong>Lista para revisar</strong>`
                      : `<span class="${watched ? "active" : ""}">${watched ? "✓ Vista" : "Pendiente"}</span><span class="${catalogued ? "active" : ""}">${catalogued ? "Disponible" : "No disponible"}</span><strong>${rating ? `${rating} pts` : "0 pts · Sin puntuar"}</strong>`}
                  </div>
                  <span class="dvd-back-hint">Click para abrir la ficha →</span>
                  <div class="dvd-barcode"><span></span><small>${escapeHtml(String(item.id || "movie-inbox").slice(0, 18))}</small></div>
                </div>
              </div>
            </div>
          </div>
          ${openCardButton(item, title, accessibleStatus, { action, actionId, entryKey })}
        </article>`;
      }

      export function openCardButton(item, title, accessibleStatus, options = {}) {
        const action = options.action || "open-detail";
        const actionId = options.actionId || item.id || "";
        return `<button class="dvd-open-surface" type="button" data-click="${escapeAttr(action)}" data-id="${escapeAttr(actionId)}" data-key="${escapeAttr(options.entryKey || "")}" aria-haspopup="dialog" aria-label="Abrir ficha de ${escapeAttr(title)}: ${escapeAttr(accessibleStatus)}"></button>`;
      }

      export function dvdBackSummary(item) {
        const summary = String(item.wikipedia_extract || item.description || item.notes || "Sin sinopsis disponible.").trim();
        return summary.length > 190 ? `${summary.slice(0, 187).trimEnd()}…` : summary;
      }

      export function posterArtwork(item, title, priority = false) {
        const variant = posterVariant(item.id || title);
        const placeholder = `<div class="dvd-placeholder poster-${variant}" aria-hidden="true">
          <span>Movie Inbox presenta</span>
          <strong class="${titleSizeClass(title)}">${escapeHtml(title)}</strong>
          <small>Edición videoclub</small>
        </div>`;
        if (!item.page_image) return placeholder;
        const fetchPriority = priority ? "high" : "auto";
        return `<img class="dvd-cover-image" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="Portada de ${escapeAttr(title)}" loading="lazy" fetchpriority="${fetchPriority}" decoding="async">${placeholder}`;
      }

      export function posterVariant(seed) {
        const value = [...String(seed || "")].reduce((total, character) => total + character.codePointAt(0), 0);
        return (value % 4) + 1;
      }

      export function handlePosterLoad(event) {
        const spotlightImage = event.target.closest?.("[data-spotlight-image]");
        if (spotlightImage) {
          spotlightImage.classList.add("is-loaded");
          return;
        }
        const image = event.target.closest?.("[data-poster-image]");
        if (!image) return;
        image.hidden = false;
        image.classList.add("is-loaded");
      }

      export function handlePosterError(event) {
        const spotlightImage = event.target.closest?.("[data-spotlight-image]");
        if (spotlightImage) {
          spotlightImage.hidden = true;
          spotlightImage.closest(".spotlight-slide")?.classList.add("is-image-missing");
          return;
        }
        const image = event.target.closest?.("[data-poster-image]");
        if (!image) return;
        image.classList.remove("is-loaded");
        image.hidden = true;
        const fallback = image.nextElementSibling;
        if (fallback?.matches(".dvd-placeholder, .drawer-poster-placeholder, .curation-thumb-placeholder")) {
          fallback.hidden = false;
        }
      }

      export function cachedImageSrc(url) {
        return `/image-cache?url=${encodeURIComponent(url)}`;
      }

