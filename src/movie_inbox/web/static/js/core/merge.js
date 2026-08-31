import { availabilityPill } from "./availability.js";
import { cachedImageSrc, card } from "./card.js";
import { loadCatalog } from "./catalog-data.js";
import { releaseDateLabel } from "./detail.js";
import { fields } from "./fields.js";
import { asList, escapeAttr, escapeHtml, formatDateTime, normalizeText, sourceLabel } from "./format.js";
import { apiFetch } from "./http.js";
import { items, setSelectedExistingIdForSearch } from "./state.js";
import { isExternalResult, manualResults, renderCatalogMergeResults, renderManualResults, reportExternalResultProblem } from "../surfaces/catalog-search.js";
import { curationEmptyState, curationHistoryMode, curationThumb, duplicateSignalsCollide, setCurationFeedback, setSelectedCurationCaseId } from "../surfaces/inbox-curation.js";

      export let mergeReview = null;

      export let mergeContext = null;

      export let mergeChoices = {};

      export let mergeSubmitting = false;

      export let mergeRequestSequence = 0;

      export async function openInternalMergeComparator(entry) {
        if (!entry?.primary || !entry?.secondary) return;
        await openMergeComparator({
          type: "internal",
          left: {
            id: entry.primary.id,
            source_file: entry.primary.source_file
          },
          right: {
            id: entry.secondary.id,
            source_file: entry.secondary.source_file
          }
        });
      }

      export async function openExternalMergeComparator(index, targetId) {
        const result = manualResults[index];
        const target = items.find((entry) => entry.id === targetId);
        if (!result || !target) {
          setCurationFeedback("La entrada o el resultado ya no están disponibles.", "error");
          return;
        }
        await openMergeComparator({
          type: "external",
          resultIndex: index,
          left: {
            id: target.id,
            source_file: target._source_file || ""
          },
          result
        });
      }

      export async function openMergeComparator(context) {
        mergeContext = context;
        mergeReview = null;
        mergeChoices = {};
        mergeSubmitting = false;
        fields.mergeShowAllFields.checked = false;
        fields.mergeComparatorFeedback.textContent = "";
        fields.mergeComparatorFeedback.dataset.tone = "";
        fields.mergeComparatorTitle.textContent = "Preparando comparación";
        fields.mergeComparatorSubtitle.textContent = "Cargando los valores actuales del catálogo.";
        fields.mergeSurvivorControl.hidden = true;
        fields.mergeComparatorSummary.innerHTML = "";
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.confirmReviewedMerge.disabled = true;
        fields.mergeDecisionStatus.textContent = "Leyendo entradas";
        fields.mergeDecisionMeta.textContent = "";
        if (!fields.mergeComparatorDialog.open) fields.mergeComparatorDialog.showModal();
        await requestMergeComparison("left");
      }

      export async function requestMergeComparison(survivorSide) {
        if (!mergeContext) return;
        const requestId = ++mergeRequestSequence;
        const requestContext = mergeContext;
        mergeContext.survivor_side = survivorSide;
        fields.mergeComparatorDialog.dataset.loading = "true";
        fields.confirmReviewedMerge.disabled = true;
        fields.mergeComparatorFeedback.textContent = "";
        try {
          const body = {
            left: mergeContext.left,
            survivor_side: survivorSide
          };
          if (mergeContext.type === "internal") body.right = mergeContext.right;
          else body.result = mergeContext.result;
          const response = await apiFetch("/api/curation/compare", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          if (
            !payload
            || !payload.left
            || !payload.right
            || !Array.isArray(payload.fields)
            || !Array.isArray(payload.groups)
          ) {
            throw new Error("invalid_comparison_payload");
          }
          if (requestId !== mergeRequestSequence || mergeContext !== requestContext) return;
          mergeReview = payload;
          if (payload.incoming) mergeContext.incoming = payload.incoming;
          mergeChoices = Object.fromEntries(
            payload.fields
              .filter((field) => field.default_choice)
              .map((field) => [field.key, field.default_choice])
          );
          renderMergeComparator();
        } catch (error) {
          if (requestId !== mergeRequestSequence || mergeContext !== requestContext) return;
          console.error("[catalog-viewer] merge comparison failed", error);
          mergeReview = null;
          fields.mergeComparatorTitle.textContent = "No se pudo comparar";
          fields.mergeComparatorSubtitle.textContent = "Las entradas no fueron modificadas.";
          fields.mergeSurvivorControl.hidden = true;
          fields.mergeComparatorSummary.innerHTML = "";
          fields.mergeComparatorFields.innerHTML = `<div class="curation-empty">
            <strong>Comparación no disponible</strong>
            <p>No pudimos leer ambas entradas. Podés reintentar sin cerrar esta mesa.</p>
            <button class="quiet-action merge-error-action" type="button" data-click="retry-merge-comparison">Reintentar comparación</button>
          </div>`;
          fields.mergeComparatorFeedback.textContent = "La comparación se interrumpió. El catálogo permanece intacto.";
          fields.mergeComparatorFeedback.dataset.tone = "error";
          fields.mergeDecisionStatus.textContent = "Comparación interrumpida";
          fields.mergeDecisionMeta.textContent = "";
        } finally {
          if (requestId === mergeRequestSequence) {
            fields.mergeComparatorDialog.dataset.loading = "false";
          }
        }
      }

      export function retryMergeComparison() {
        if (!mergeContext || fields.mergeComparatorDialog.dataset.loading === "true") return;
        fields.mergeComparatorTitle.textContent = "Preparando comparación";
        fields.mergeComparatorSubtitle.textContent = "Volviendo a leer los valores actuales del catálogo.";
        fields.mergeSurvivorControl.hidden = true;
        fields.mergeComparatorSummary.innerHTML = "";
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.mergeDecisionStatus.textContent = "Leyendo entradas";
        fields.mergeComparatorFeedback.textContent = "";
        fields.mergeComparatorFeedback.dataset.tone = "";
        requestMergeComparison(mergeContext.survivor_side || "left");
      }

      export function mergeTitleFragment(item, other) {
        if (item.year && item.year !== other.year) return `${item.title} (${item.year})`;
        return `${item.title} (${sourceLabel(item.source)})`;
      }

      export function renderMergeComparator() {
        if (!mergeReview) return;
        const rawLeftTitle = mergeReview.left?.title || "Entrada A";
        const rawRightTitle = mergeReview.right?.title || "Entrada B";
        const titlesCollide = Boolean(mergeReview.left && mergeReview.right) && rawLeftTitle === rawRightTitle;
        const needsPosition = titlesCollide
          && String(mergeReview.left.year || "") === String(mergeReview.right.year || "")
          && duplicateSignalsCollide(mergeReview.left, mergeReview.right);
        const leftTitle = needsPosition
          ? `${rawLeftTitle} (Duplicado 1 de 2)`
          : (titlesCollide ? mergeTitleFragment(mergeReview.left, mergeReview.right) : rawLeftTitle);
        const rightTitle = needsPosition
          ? `${rawRightTitle} (Duplicado 2 de 2)`
          : (titlesCollide ? mergeTitleFragment(mergeReview.right, mergeReview.left) : rawRightTitle);
        fields.mergeComparatorTitle.textContent = `${leftTitle} / ${rightTitle}`;
        fields.mergeComparatorSubtitle.textContent = mergeReview.can_select_survivor
          ? "Elegí qué identidad permanece y resolvé los campos señalados."
          : "La entrada del catálogo conservará su identidad.";
        fields.mergeSurvivorControl.hidden = !mergeReview.can_select_survivor;
        fields.mergeSurvivorLeft.textContent = `Conservar A · ${leftTitle}`;
        fields.mergeSurvivorRight.textContent = `Conservar B · ${rightTitle}`;
        fields.mergeSurvivorControl.querySelectorAll('input[name="merge-survivor"]').forEach((input) => {
          input.checked = input.value === mergeReview.survivor_side;
        });
        fields.mergeComparatorSummary.innerHTML = `
          ${mergeEntrySummary(mergeReview.left, "Entrada A", mergeReview.survivor_side === "left", needsPosition ? "Duplicado 1 de 2" : "")}
          <span class="merge-summary-divider" aria-hidden="true">↔</span>
          ${mergeEntrySummary(mergeReview.right, "Entrada B", mergeReview.survivor_side === "right", needsPosition ? "Duplicado 2 de 2" : "")}
        `;

        const visibleFields = mergeReview.fields.filter((field) => (
          fields.mergeShowAllFields.checked || field.different
        ));
        fields.mergeComparatorFields.innerHTML = mergeReview.groups
          .map((group) => {
            const rows = visibleFields.filter((field) => field.group === group.key);
            if (!rows.length) return "";
            return `<section class="merge-field-group" aria-labelledby="merge-group-${escapeAttr(group.key)}">
              <header>
                <h3 id="merge-group-${escapeAttr(group.key)}">${escapeHtml(group.label)}</h3>
                <span>${rows.length} ${rows.length === 1 ? "campo" : "campos"}</span>
              </header>
              ${rows.map(mergeFieldRow).join("")}
            </section>`;
          })
          .join("") || curationEmptyState("Las entradas coinciden", "No hay diferencias para revisar.");
        updateMergeDecisionStatus();
      }

      export function mergeEntrySummary(item, label, survivor, positionLabel = "") {
        return `<article class="merge-entry-summary ${survivor ? "survivor" : ""}">
          ${curationThumb(item, true)}
          <div>
            <span>${escapeHtml(label)}${positionLabel ? ` · ${escapeHtml(positionLabel)}` : ""}${survivor ? " · permanece" : ""}</span>
            <strong>${escapeHtml(item.title || "Sin título")}</strong>
            <small>${escapeHtml([item.year, item.kind, sourceLabel(item.source)].filter(Boolean).join(" · "))}</small>
            ${item.added_at ? `<small class="merge-entry-added">Agregada ${escapeHtml(formatDateTime(item.added_at))}</small>` : ""}
            <div class="card-badges">
              ${availabilityPill(item)}
              <span class="pill ${item.local_files_count ? "good" : "muted"}">${item.local_files_count || 0} archivos</span>
            </div>
          </div>
        </article>`;
      }

      export function mergeFieldRow(field) {
        const choice = mergeChoices[field.key] || "";
        const states = [
          { side: "left", label: "Entrada A", value: field.left },
          ...(field.allowed.includes("combine")
            ? [{ side: "combine", label: mergeCombineLabel(field), value: mergeCombinedValue(field) }]
            : []),
          { side: "right", label: "Entrada B", value: field.right }
        ].filter((state) => field.allowed.includes(state.side));
        const options = field.different
          ? states.map((state) => `
              <label class="merge-choice ${state.side}">
                <input type="radio" name="merge-field-${escapeAttr(field.key)}"
                  data-merge-choice="${escapeAttr(field.key)}" value="${state.side}"
                  ${choice === state.side ? "checked" : ""}>
                <span class="merge-choice-label">${escapeHtml(state.label)}</span>
                ${mergeValue(state.value, field)}
              </label>
            `).join("")
          : `<div class="merge-field-same">${mergeValue(field.left, field)}<span>Coinciden</span></div>`;
        return `<article class="merge-field-row ${field.required && !choice ? "needs-decision" : ""}"
          data-merge-field="${escapeAttr(field.key)}">
          <header>
            <strong>${escapeHtml(field.label)}</strong>
            <span class="merge-field-signals">
              ${field.protected ? '<span class="pill warning">protegido</span>' : ""}
              ${field.locked ? '<span class="pill muted">bloqueado</span>' : ""}
              ${field.required && !choice ? '<span class="pill warning">elegir</span>' : ""}
            </span>
          </header>
          <div class="merge-field-options ${states.length === 3 ? "three" : "two"}">${options}</div>
        </article>`;
      }

      export function mergeValue(value, field) {
        if (field.strategy === "local_files") {
          const files = Array.isArray(value) ? value : [];
          if (!files.length) return '<span class="merge-value empty">Sin archivos</span>';
          return `<span class="merge-value merge-file-list">${files.map((file) => `
            <span><strong>${escapeHtml(file.name || "Archivo")}</strong><small>${escapeHtml(file.path || file.relative_path || "")}</small></span>
          `).join("")}</span>`;
        }
        if (field.strategy === "list") {
          const values = asList(value);
          return values.length
            ? `<span class="merge-value merge-list-value">${values.map((entry) => `<span>${escapeHtml(entry)}</span>`).join("")}</span>`
            : '<span class="merge-value empty">Sin datos</span>';
        }
        if (field.strategy === "release_dates") {
          const dates = Array.isArray(value) ? value : [];
          return dates.length
            ? `<span class="merge-value merge-list-value">${dates.map((entry) => `<span>${escapeHtml(releaseDateLabel(entry))}</span>`).join("")}</span>`
            : '<span class="merge-value empty">Sin fechas</span>';
        }
        if (field.strategy === "boolean_or") {
          return `<span class="merge-value">${value ? "Sí" : "No"}</span>`;
        }
        if (["page_image", "backdrop_image"].includes(field.key) && value) {
          return `<span class="merge-value merge-image-value">
            <img src="${escapeAttr(cachedImageSrc(String(value)))}" alt="" loading="lazy">
            <small>${escapeHtml(urlHost(value))}</small>
          </span>`;
        }
        const text = String(value ?? "").trim();
        return `<span class="merge-value ${text ? "" : "empty"}">${escapeHtml(text || "Sin datos")}</span>`;
      }

      export function mergeCombinedValue(field) {
        if (field.strategy === "list") {
          const seen = new Set();
          return [...asList(field.left), ...asList(field.right)].filter((value) => {
            const key = normalizeText(value);
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        }
        if (field.strategy === "local_files") {
          const seen = new Set();
          return [...asList(field.left), ...asList(field.right)].filter((file) => {
            const key = `${file.library_id || ""}|${file.relative_path || ""}|${file.path || ""}`.toLowerCase();
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        }
        if (field.strategy === "release_dates") {
          const seen = new Set();
          return [...asList(field.left), ...asList(field.right)].filter((entry) => {
            const key = `${entry?.date || ""}|${entry?.country || ""}|${entry?.release_type || ""}`.toLowerCase();
            if (!entry?.date || seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        }
        if (field.strategy === "boolean_or") return Boolean(field.left || field.right);
        return field.left;
      }

      export function mergeCombineLabel(field) {
        if (field.strategy === "boolean_or") return "Preservar sí";
        if (field.strategy === "local_files") return "Conservar todos";
        if (field.strategy === "release_dates") return "Conservar fechas";
        return "Combinar";
      }

      export function changeMergeChoice(event) {
        const input = event.target.closest("[data-merge-choice]");
        if (!input || !mergeReview) return;
        mergeChoices[input.dataset.mergeChoice] = input.value;
        const row = fields.mergeComparatorFields.querySelector(
          `[data-merge-field="${CSS.escape(input.dataset.mergeChoice)}"]`
        );
        if (row) {
          row.classList.remove("needs-decision");
          row.querySelectorAll(".merge-field-signals .warning").forEach((badge) => {
            if (badge.textContent.trim() === "elegir") badge.remove();
          });
        }
        updateMergeDecisionStatus();
      }

      export async function changeMergeSurvivor(event) {
        const input = event.target.closest('input[name="merge-survivor"]');
        if (!input || !mergeReview || input.value === mergeReview.survivor_side) return;
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.mergeDecisionStatus.textContent = "Recalculando resultado";
        await requestMergeComparison(input.value);
      }

      export function updateMergeDecisionStatus() {
        if (!mergeReview) return;
        const unresolved = mergeReview.fields.filter((field) => (
          field.different
          && field.required
          && !field.allowed.includes(mergeChoices[field.key])
        ));
        const different = mergeReview.different_count || 0;
        fields.mergeDecisionStatus.textContent = unresolved.length
          ? `${unresolved.length} ${unresolved.length === 1 ? "decisión pendiente" : "decisiones pendientes"}`
          : "Resultado listo para combinar";
        fields.mergeDecisionMeta.textContent = `${different} ${different === 1 ? "diferencia" : "diferencias"} revisadas`;
        fields.confirmReviewedMerge.disabled = mergeSubmitting || unresolved.length > 0;
      }

      export async function submitReviewedMerge() {
        if (!mergeReview || !mergeContext || mergeSubmitting) return;
        mergeSubmitting = true;
        updateMergeDecisionStatus();
        fields.mergeComparatorFeedback.textContent = "Guardando combinación…";
        fields.mergeComparatorFeedback.dataset.tone = "working";
        try {
          const body = {
            left: mergeContext.left,
            survivor_side: mergeReview.survivor_side,
            choices: mergeChoices,
            review_id: mergeReview.review_id,
            history_mode: curationHistoryMode
          };
          if (mergeContext.type === "internal") {
            body.right = mergeContext.right;
          } else {
            body.incoming = mergeContext.incoming || mergeContext.result;
            body.incoming_reviewed = true;
          }
          const response = await apiFetch("/api/curation/merge", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            if (response.status === 409) throw new Error("Las entradas cambiaron. Cerrá y volvé a comparar.");
            throw new Error(payload.reason || `HTTP ${response.status}`);
          }
          const externalMerge = mergeContext.type === "external";
          closeMergeComparator(true);
          setSelectedCurationCaseId("");
          await loadCatalog();
          setCurationFeedback("Entradas combinadas", "success", payload.operation);
          if (externalMerge) {
            setSelectedExistingIdForSearch(null);
            fields.manualSearchStatus.textContent = "Combinación guardada. Deshacer está disponible en Bandeja > Actividad.";
            renderManualResults();
            renderCatalogMergeResults();
          }
        } catch (error) {
          console.error("[catalog-viewer] reviewed merge failed", error);
          fields.mergeComparatorFeedback.textContent = error.message || "No se pudo combinar.";
          fields.mergeComparatorFeedback.dataset.tone = "error";
        } finally {
          mergeSubmitting = false;
          updateMergeDecisionStatus();
        }
      }

      export function closeMergeComparator(force = false) {
        if (mergeSubmitting && !force) return;
        mergeRequestSequence += 1;
        if (fields.mergeComparatorDialog.open) fields.mergeComparatorDialog.close();
        mergeReview = null;
        mergeContext = null;
        mergeChoices = {};
        fields.mergeComparatorFeedback.textContent = "";
      }

      export function mergeComparatorLoading() {
        return `<div class="merge-loading" aria-label="Cargando comparación">
          <span></span><span></span><span></span>
        </div>`;
      }

      export function urlHost(value) {
        try {
          return new URL(String(value)).hostname.replace(/^www\./, "");
        } catch (_) {
          return String(value || "");
        }
      }

      export function mergeFieldLabel(key) {
        return {
          title: "Título principal",
          original_title: "Título original",
          spanish_title: "Título en español",
          english_title: "Título en inglés",
          alternative_titles: "Títulos alternativos",
          kind: "Tipo de obra",
          year: "Año",
          release_dates: "Fechas de estreno",
          description: "Descripción",
          wikipedia_extract: "Extracto de Wikipedia",
          genres: "Géneros",
          directors: "Dirección",
          writers: "Guion",
          cast: "Reparto",
          page_image: "Portada",
          backdrop_image: "Imagen panorámica",
          source: "Fuente principal",
          url: "URL principal",
          wikipedia_url: "Wikipedia",
          imdb_url: "IMDb",
          filmaffinity_url: "FilmAffinity",
          myanimelist_url: "MyAnimeList",
          wikipedia_title: "Título de Wikipedia",
          wikidata_id: "Wikidata",
          tmdb_id: "TMDB",
          mal_id: "MyAnimeList ID",
          status: "Estado personal",
          watched_at: "Fecha de vista",
          rating: "Puntaje",
          review: "Review",
          notes: "Notas",
          tags: "Etiquetas",
          en_catalogo: "Disponibilidad manual",
          local_files: "Archivos locales"
        }[key] || key;
      }

      export async function mergeSearchResult(index, targetId) {
        if (!isExternalResult(manualResults[index])) {
          reportExternalResultProblem("Ese resultado no se puede comparar porque no tiene un enlace externo reconocido.");
          return;
        }
        await openExternalMergeComparator(index, targetId);
      }
