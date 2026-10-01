import { cachedImageSrc } from "../core/card.js";
import { fields } from "../core/fields.js";
import { asList, displayTitle, escapeAttr, escapeHtml, firstListValue, hasExternalLink, isInCatalog, localFiles, meta, normalizeText, sourceLabel, titleSizeClass, titleSubtitle } from "../core/format.js";
import { items, selectedExistingIdForSearch } from "../core/state.js";
import { EXTERNAL_SOURCE_LABELS, SEARCH_TIMEOUT_MS, externalSearchController, manualResults, selectedManualIndex } from "./catalog-search.js";

      export function catalogMergeResult(item, index) {
        const incoming = selectedManualIndex === null ? null : manualResults[selectedManualIndex];
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || item.local_name || "";
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        return `<article class="search-result compact-result">
          ${resultMedia(shownTitle || item.local_name, item.page_image, index < 6)}
          <div class="result-body">
            <h3 class="${titleSizeClass(shownTitle)}">${escapeHtml(shownTitle || "Sin titulo")}</h3>
            ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
            <div class="meta">
              ${meta(item.year)}${meta(item.kind)}${meta(item.source)}${meta(firstListValue(item.genres))}${meta(firstListValue(item.directors))}
            </div>
            <div class="card-badges">
              ${item._search?.reason ? `<span class="pill match-reason">${escapeHtml(searchReasonLabel(item._search))}</span>` : ""}
              <span class="pill ${hasExternalLink(item) ? "good" : "muted"}">${hasExternalLink(item) ? "con referencia" : "sin referencia"}</span>
              <span class="pill ${isInCatalog(item.en_catalogo) ? "good" : "muted"}">${isInCatalog(item.en_catalogo) ? "disponible: sí" : "disponible: no"}</span>
            </div>
            ${searchDescription(summary, "catalog", item.id)}
            <div class="result-actions">
              <button class="action-primary ${incoming ? "" : "span-all"}" type="button" data-click="open-detail" data-id="${escapeAttr(item.id)}">Detalle</button>
              ${incoming ? `<button class="action-secondary" type="button" data-click="merge-result" data-index="${selectedManualIndex}" data-id="${escapeAttr(item.id)}">Combinar</button>` : ""}
              ${item.url ? `<a class="action-secondary span-all" href="${escapeAttr(item.url)}" target="_blank" rel="noreferrer">Abrir link</a>` : ""}
            </div>
          </div>
        </article>`;
      }

      export function searchResult(result, index) {
        const description = result.description || result.wikipedia_extract || "";
        const similarity = selectedExistingIdForSearch ? candidateSimilarity(result) : "";
        const primaryAction = selectedExistingIdForSearch ? "Combinar" : "Agregar a colección";
        const shownTitle = displayTitle(result);
        const subtitle = titleSubtitle(result);
        const badges = [
          result._search?.reason === "director_match" ? `<span class="pill match-reason">${escapeHtml(searchReasonLabel(result._search))}</span>` : "",
          !result.url ? `<span class="pill muted">Sin enlace de fuente</span>` : ""
        ].filter(Boolean).join("");
        return `<article class="search-result compact-result external-result" data-result-index="${index}">
          ${resultMedia(shownTitle, result.page_image, index < 6)}
          <div class="result-body">
            <h3 class="${titleSizeClass(shownTitle)}">${escapeHtml(shownTitle || "Sin titulo")}</h3>
            ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
            <div class="meta">
              ${meta(result.year)}${meta(result.kind)}${meta(firstListValue(result.genres))}${meta(firstListValue(result.directors))}${meta(similarity)}
            </div>
            ${badges ? `<div class="card-badges">${badges}</div>` : ""}
            ${searchDescription(description, "manual", index)}
            <div class="result-actions">
              <button class="action-primary" data-click="add-result" data-index="${index}">${primaryAction}</button>
              <button class="action-secondary" type="button" data-click="prepare-merge" data-index="${index}">Comparar con mi colección</button>
              ${result.url ? `<a class="action-secondary" href="${escapeAttr(result.url)}" target="_blank" rel="noreferrer">Abrir en ${escapeHtml(sourceLabel(result.source))}</a>` : ""}
            </div>
          </div>
        </article>`;
      }

      export function resultMedia(title, imageUrl, priority = false) {
        const placeholder = `<div class="result-placeholder" aria-hidden="true">${escapeHtml((title || "Sin imagen").slice(0, 24))}</div>`;
        if (!imageUrl) return `<div class="result-media-frame">${placeholder}</div>`;
        return `<div class="result-media-frame">
          <img class="result-media" data-poster-image src="${escapeAttr(cachedImageSrc(imageUrl))}" alt="" loading="lazy" fetchpriority="${priority ? "high" : "auto"}" decoding="async">
          ${placeholder}
        </div>`;
      }

      export function searchDescription(description, collection, key) {
        if (!description) return "";
        const text = String(description).trim();
        const more = text.length > 90
          ? `<button class="description-more" type="button" data-click="show-description" data-collection="${escapeAttr(collection)}" data-key="${escapeAttr(key)}">Ver más</button>`
          : "";
        return `<p class="result-summary${more ? "" : " summary-full"}">${escapeHtml(text)}</p>${more}`;
      }

      export function candidateSimilarity(result) {
        const existing = items.find((entry) => entry.id === selectedExistingIdForSearch);
        if (!existing) return "";
        let score = bestTitleSimilarity(existing, result);
        if (existing.year && String(existing.year) === String(result.year || "")) score = Math.min(100, score + 20);
        return `similitud: ${score}%`;
      }

      export function searchReasonLabel(search = {}) {
        const labels = {
          director_match: "coincide por dirección",
          shared_external_url: "mismo enlace",
          shared_wikidata_id: "mismo Wikidata",
          shared_mal_id: "mismo MyAnimeList ID",
          mal_id_conflict: "MyAnimeList ID distinto",
          exact_title_year: "título y año exactos",
          exact_title_missing_year: "título exacto; falta año",
          exact_title_year_mismatch: "título exacto; año distinto",
          exact_title_year_anime_kind_review: "título y año; revisar formato de anime",
          exact_title_kind_mismatch: "título exacto; tipo distinto",
          similar_title_requires_review: "título similar",
          insufficient_evidence: "coincidencia posible"
        };
        if (labels[search.reason]) return labels[search.reason];
        const fieldLabels = {
          title: "título",
          original_title: "título original",
          spanish_title: "título en español",
          english_title: "título en inglés",
          alternative_titles: "nombre alternativo",
          local_file: "archivo local",
          external_id: "identificador externo",
          external_link: "enlace externo"
        };
        return fieldLabels[search.matched_field] || "coincidencia local";
      }

      export function bestTitleSimilarity(leftItem, rightItem) {
        const leftTitles = titleSearchValues(leftItem).map(normalizeText).filter(Boolean);
        const rightTitles = titleSearchValues(rightItem).map(normalizeText).filter(Boolean);
        let best = 0;
        for (const leftTitle of leftTitles) {
          for (const rightTitle of rightTitles) {
            const leftTerms = new Set(leftTitle.split(/\s+/).filter(Boolean));
            const rightTerms = new Set(rightTitle.split(/\s+/).filter(Boolean));
            const shared = [...leftTerms].filter((term) => rightTerms.has(term)).length;
            const total = Math.max(leftTerms.size, rightTerms.size, 1);
            best = Math.max(best, Math.round((shared / total) * 100));
          }
        }
        return best;
      }

      export function titleSearchValues(item) {
        return [
          item.title,
          item.original_title,
          item.spanish_title,
          item.english_title,
          ...(asList(item.alternative_titles)),
          item.wikipedia_title,
          item.local_name,
          ...localFiles(item).flatMap((file) => [file.name, file.path])
        ].filter(Boolean);
      }

      export function oneEditApart(left, right) {
        if (Math.abs(left.length - right.length) > 1) return false;
        let leftIndex = 0;
        let rightIndex = 0;
        let edits = 0;
        while (leftIndex < left.length && rightIndex < right.length) {
          if (left[leftIndex] === right[rightIndex]) {
            leftIndex += 1;
            rightIndex += 1;
            continue;
          }
          edits += 1;
          if (edits > 1) return false;
          if (left.length > right.length) leftIndex += 1;
          else if (right.length > left.length) rightIndex += 1;
          else {
            leftIndex += 1;
            rightIndex += 1;
          }
        }
        if (leftIndex < left.length || rightIndex < right.length) edits += 1;
        return edits <= 1;
      }

      export function externalSourceStateLabel(state, count) {
        if (state.status === "loading") return "Consultando…";
        if (state.status === "timeout") return "Tiempo agotado";
        if (state.status === "cooldown") return "En pausa temporal";
        if (state.status === "fallback") return `${count} · respaldo local`;
        if (state.status === "error") return "No disponible";
        if (state.status === "canceled") return "Cancelada";
        if (state.status === "idle") return "Sin consultar";
        return `${count} ${count === 1 ? "resultado" : "resultados"}`;
      }

      export function externalSourceFeedback(source, state) {
        const label = EXTERNAL_SOURCE_LABELS[source]?.[0] || source;
        if (state.status === "loading") {
          return `<div class="search-source-feedback is-loading" role="status">
            <span class="source-search-spinner" aria-hidden="true"></span>
            <span>Consultando ${escapeHtml(label)}…</span>
          </div>`;
        }
        if (["error", "timeout", "cooldown"].includes(state.status)) {
          const message = state.status === "timeout"
            ? `${label} tardó más de ${SEARCH_TIMEOUT_MS / 1000} segundos.`
            : state.status === "cooldown"
              ? `${label} está en pausa temporal${state.retryAfterSeconds ? ` por ${formatRetryDelay(state.retryAfterSeconds)}` : ""}.`
              : `${label} no respondió correctamente.`;
          return `<div class="search-source-feedback is-error" role="status">
            <span>${escapeHtml(message)}</span>
            <button class="quiet-action source-retry" type="button" data-click="retry-external-source" data-source="${source}" ${externalSearchController ? "disabled" : ""}>${state.status === "cooldown" ? "Comprobar de nuevo" : "Reintentar"}</button>
          </div>`;
        }
        if (state.status === "canceled") {
          return `<p class="search-source-empty">Consulta cancelada.</p>`;
        }
        if (state.status === "idle") {
          return `<p class="search-source-empty">Esta fuente no fue consultada.</p>`;
        }
        return `<p class="search-source-empty">Sin coincidencias en esta fuente.</p>`;
      }

      export function formatRetryDelay(seconds) {
        const value = Math.max(1, Number(seconds || 0));
        if (value < 60) return `${Math.ceil(value)} s`;
        return `${Math.ceil(value / 60)} min`;
      }

      export function showDuplicateChoice(index, candidates) {
        const incoming = manualResults[index] || {};
        const title = displayTitle(incoming) || "Sin título";
        const blocks = candidates.map((candidate) => `<article class="duplicate-candidate">
          <div class="duplicate-candidate-main">
            <strong>${escapeHtml(displayTitle(candidate) || candidate.title || "Sin título")}</strong>
            <span class="duplicate-candidate-reason">${escapeHtml(searchReasonLabel({ reason: candidate.reason }))}</span>
            <div class="meta">${meta(candidate.year)}${meta(candidate.kind)}${meta(firstListValue(candidate.directors))}</div>
          </div>
          <div class="duplicate-candidate-actions">
            <button class="duplicate-compare" type="button" data-click="merge-result" data-index="${index}" data-id="${escapeAttr(candidate.id)}">Comparar y combinar</button>
            <button class="duplicate-open" type="button" data-click="open-detail" data-id="${escapeAttr(candidate.id)}">Abrir ficha guardada</button>
          </div>
        </article>`).join("");
        fields.duplicateReview.dataset.index = String(index);
        fields.duplicateReview.innerHTML = `<section aria-labelledby="duplicateReviewTitle">
          <header class="duplicate-review-header">
            <div>
              <h3 id="duplicateReviewTitle" tabindex="-1">Revisá esta posible coincidencia</h3>
              <p>Esta obra todavía no se agregó. Elegí si corresponde a una ficha guardada.</p>
            </div>
            <button class="duplicate-dismiss" type="button" data-click="dismiss-duplicate">Seguir buscando</button>
          </header>
          <div class="duplicate-review-layout">
            <div class="duplicate-incoming">
              <span>Querés agregar</span>
              <strong>${escapeHtml(title)}</strong>
              <div class="meta">${meta(incoming.year)}${meta(incoming.kind)}${meta(sourceLabel(incoming.source))}</div>
            </div>
            <div class="duplicate-candidates">
              <h4>En tu colección · ${candidates.length}</h4>
              ${blocks || `<p class="duplicate-empty">No llegaron candidatas para comparar. Podés seguir buscando o agregarla como obra distinta.</p>`}
            </div>
          </div>
          <details class="duplicate-distinct">
            <summary>Es otra obra distinta</summary>
            <p>Se creará una segunda ficha aunque tenga un título parecido. Comprobá que no sea la misma obra antes de seguir.</p>
            <button type="button" data-click="force-add" data-index="${index}">Agregar como obra distinta</button>
          </details>
        </section>`;
        fields.duplicateReview.hidden = false;
        fields.duplicateReview.scrollIntoView({ block: "nearest" });
        fields.duplicateReview.querySelector("#duplicateReviewTitle")?.focus({ preventScroll: true });
      }
