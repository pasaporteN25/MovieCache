import { card } from "../core/card.js";
import { loadCatalog } from "../core/catalog-data.js";
import { fields } from "../core/fields.js";
import { escapeAttr, escapeHtml, formatDateTime, hasHost, normalizeText } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { registerUndoHandler, setOperationFeedback } from "../core/operation-feedback.js";
import { findLocalMatchForItem } from "../core/search-bridge.js";
import { renderScopeStrip, scannerActionReceipt, scannerScopeStates, summarizeScopeStates } from "../core/scope-strip.js";
import { curationCounts, currentIdentity } from "../core/state.js";
import { libraryErrorMessage, loadLibraries } from "./admin-libraries.js";
import { syncCurationCounts } from "./inbox-curation.js";
import { formatImportBytes, importKindLabel } from "./inbox-imports.js";

      export let scannerQueue = [];

      export let selectedScannerItemId = "";

      export let scannerQueueLoading = false;

      export let scannerQueueFilter = "all";

      export let scannerQueueQuery = "";

      export let scannerCreateConflicts = new Map();

      export let scannerHistory = [];

      export let scannerHistoryLoading = false;

      export let scannerHistoryMode = storedScannerHistoryMode();

      export function setScannerFeedback(message, tone = "", operation = null) {
        setOperationFeedback(message, tone, operation, "scanner");
      }

      registerUndoHandler("scanner", undoScannerOperation);

      export async function loadScannerQueue({ announce = false } = {}) {
        if (scannerQueueLoading || currentIdentity?.user?.role !== "owner") return;
        scannerQueueLoading = true;
        fields.scannerInboxPanel.setAttribute("aria-busy", "true");
        fields.refreshScannerQueue.disabled = true;
        try {
          const response = await apiFetch("/api/scanner/queue");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          scannerQueue = payload.items || [];
          const queueIds = new Set(scannerQueue.map((item) => item.id));
          scannerCreateConflicts = new Map(
            [...scannerCreateConflicts].filter(([fileId]) => queueIds.has(fileId))
          );
          curationCounts.scanner = Number(payload.count || scannerQueue.length);
          if (!scannerQueue.some((item) => item.id === selectedScannerItemId)) {
            selectedScannerItemId = scannerQueue[0]?.id || "";
          }
          await loadScannerHistory();
          renderScannerQueue();
          syncCurationCounts();
          if (announce) setScannerFeedback("Cola del inventario actualizada.", "success");
        } catch (error) {
          fields.scannerQueue.innerHTML = "";
          fields.scannerQueueDetail.innerHTML = `<div class="curation-empty"><strong>Cola no disponible</strong><p>${escapeHtml(libraryErrorMessage(error.message))}</p></div>`;
        } finally {
          scannerQueueLoading = false;
          fields.scannerInboxPanel.removeAttribute("aria-busy");
          fields.refreshScannerQueue.disabled = false;
        }
      }

      export async function loadScannerHistory() {
        if (scannerHistoryLoading) return;
        scannerHistoryLoading = true;
        try {
          const response = await apiFetch(`/api/scanner/history?mode=${encodeURIComponent(scannerHistoryMode)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          scannerHistory = payload.operations || [];
          fields.scannerHistoryCount.textContent = payload.count || 0;
        } catch (error) {
          console.error("[catalog-viewer] scanner history load failed", error);
          scannerHistory = [];
          fields.scannerHistoryCount.textContent = "!";
          if (scannerQueueFilter === "history") {
            setScannerFeedback("No se pudo cargar la actividad del inventario.", "error");
          }
        } finally {
          scannerHistoryLoading = false;
        }
      }

      export function storedScannerHistoryMode() {
        try {
          return localStorage.getItem("movie-inbox-scanner-history-mode") === "session"
            ? "session"
            : "persistent";
        } catch (_) {
          return "persistent";
        }
      }

      export async function changeScannerHistoryMode() {
        scannerHistoryMode = fields.persistScannerHistory.checked ? "persistent" : "session";
        try {
          localStorage.setItem("movie-inbox-scanner-history-mode", scannerHistoryMode);
        } catch (_) {
          // The preference remains active for this page even when storage is unavailable.
        }
        fields.persistScannerHistory.nextElementSibling.textContent = scannerHistoryMode === "persistent"
          ? "Historial persistente"
          : "Sólo esta sesión";
        selectedScannerItemId = "";
        await loadScannerHistory();
        renderScannerQueue();
        setScannerFeedback(
          scannerHistoryMode === "persistent"
            ? "Las próximas decisiones conservarán Deshacer después de reiniciar."
            : "Las próximas decisiones podrán deshacerse sólo durante esta sesión.",
          "success"
        );
      }

      export async function clearScannerHistory() {
        const count = scannerHistory.length;
        if (!count) {
          setScannerFeedback("No hay actividad para limpiar.", "");
          return;
        }
        const confirmed = confirm(
          `Eliminar ${count} ${count === 1 ? "operación" : "operaciones"} del historial? Ya no podrán deshacerse.`
        );
        if (!confirmed) return;
        fields.clearScannerHistory.disabled = true;
        try {
          const response = await apiFetch("/api/scanner/history/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              history_mode: scannerHistoryMode,
              confirmed: true
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          scannerHistory = [];
          selectedScannerItemId = "";
          renderScannerQueue();
          setScannerFeedback("Historial eliminado.", "success");
        } catch (error) {
          console.error("[catalog-viewer] scanner history clear failed", error);
          setScannerFeedback("No se pudo limpiar el historial. El inventario no fue modificado.", "error");
        } finally {
          fields.clearScannerHistory.disabled = false;
        }
      }

      export async function undoScannerOperation(operationId) {
        if (!operationId) return;
        setScannerFeedback("Restaurando estado anterior…", "working");
        try {
          const response = await apiFetch("/api/scanner/undo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              operation_id: operationId,
              history_mode: scannerHistoryMode
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            const reason = payload.reason || `HTTP ${response.status}`;
            if (response.status === 409) {
              throw new Error("El archivo cambió después de esta operación. Revisalo antes de restaurar.");
            }
            throw new Error(reason);
          }
          selectedScannerItemId = operationId;
          await Promise.all([loadScannerQueue(), loadCatalog(), loadLibraries()]);
          scannerQueueFilter = "history";
          renderScannerQueue();
          setScannerFeedback("Operación deshecha. El archivo volvió a la cola.", "success");
        } catch (error) {
          console.error("[catalog-viewer] scanner undo failed", error);
          setScannerFeedback(error.message || "No se pudo deshacer la operación.", "error");
          renderScannerQueue();
        }
      }

      export function renderScannerQueue() {
        if (scannerQueueFilter === "history") {
          renderScannerHistory();
          return;
        }
        const bucketCounts = { missing_identity: 0, year_type_conflict: 0, likely_existing: 0, no_signal: 0 };
        scannerQueue.forEach((item) => {
          const bucket = scannerQueueCauseBucket(item, scannerCandidatesForItem(item));
          bucketCounts[bucket] += 1;
        });
        fields.scannerAllCount.textContent = String(scannerQueue.length);
        fields.scannerMissingIdentityCount.textContent = String(bucketCounts.missing_identity);
        fields.scannerYearTypeConflictCount.textContent = String(bucketCounts.year_type_conflict);
        fields.scannerLikelyExistingCount.textContent = String(bucketCounts.likely_existing);
        fields.scannerNoSignalCount.textContent = String(bucketCounts.no_signal);
        fields.scannerQueueFilters.querySelectorAll("[data-scanner-filter]").forEach((button) => {
          const active = button.dataset.scannerFilter === scannerQueueFilter;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        const visible = visibleScannerQueue();
        fields.scannerQueueMeta.textContent = visible.length === scannerQueue.length
          ? `${scannerQueue.length} ${scannerQueue.length === 1 ? "pendiente" : "pendientes"}`
          : `${visible.length} de ${scannerQueue.length} pendientes`;
        if (!scannerQueue.length) {
          fields.scannerQueue.innerHTML = `<div class="curation-empty compact"><strong>Inventario al día</strong><p>No quedan identidades físicas por confirmar.</p></div>`;
          fields.scannerQueueDetail.innerHTML = `<div class="curation-empty"><strong>Sin decisiones pendientes</strong><p>Los próximos casos aparecerán después de un recorrido aplicado.</p></div>`;
          renderScopeStrip(scannerScopeStates(null));
          return;
        }
        if (!visible.length) {
          selectedScannerItemId = "";
          fields.scannerQueue.innerHTML = `<div class="curation-empty compact"><strong>Sin resultados</strong><p>Probá otro filtro o término de búsqueda.</p></div>`;
          fields.scannerQueueDetail.innerHTML = `<div class="curation-empty"><strong>No hay casos para mostrar</strong><p>La cola completa conserva ${scannerQueue.length} pendientes.</p></div>`;
          renderScopeStrip(scannerScopeStates(null));
          return;
        }
        if (!visible.some((item) => item.id === selectedScannerItemId)) {
          selectedScannerItemId = visible[0].id;
        }
        fields.scannerQueue.innerHTML = visible.map((item) => {
          const active = item.id === selectedScannerItemId;
          const bucket = scannerQueueCauseBucket(item, scannerCandidatesForItem(item));
          const partLabel = Number(item.file_count || 1) > 1 ? `${item.file_count} partes` : "";
          return `<button class="scanner-queue-item${active ? " active" : ""}" type="button" data-scanner-item="${escapeAttr(item.id)}" aria-pressed="${active}">
            <span class="member-state ${scannerQueueCauseBadgeClass(bucket)}">${escapeHtml(scannerQueueCauseLabel(bucket))}</span>
            <strong>${escapeHtml(item.detected_title || item.name || "Sin título")}</strong>
            <span>${escapeHtml([item.detected_year, importKindLabel(item.detected_kind)].filter(Boolean).join(" · ") || "Identidad incompleta")}</span>
            <small>${escapeHtml([item.library_name || "Biblioteca", partLabel].filter(Boolean).join(" · "))}</small>
          </button>`;
        }).join("");
        renderScannerQueueDetail();
      }

      export function visibleScannerQueue() {
        const query = normalizeText(scannerQueueQuery);
        return scannerQueue.filter((item) => {
          if (scannerQueueFilter !== "all"
              && scannerQueueCauseBucket(item, scannerCandidatesForItem(item)) !== scannerQueueFilter) return false;
          if (!query) return true;
          const values = [
            item.detected_title,
            item.detected_year,
            item.detected_kind,
            item.name,
            item.relative_path,
            item.library_name
          ];
          return normalizeText(values.filter(Boolean).join(" ")).includes(query);
        });
      }

      export function changeScannerQueueFilter(event) {
        const button = event.target.closest("[data-scanner-filter]");
        if (!button) return;
        scannerQueueFilter = button.dataset.scannerFilter || "all";
        renderScannerQueue();
        focusSelectedScannerItem();
      }

      export function searchScannerQueue(event) {
        scannerQueueQuery = event.target.value || "";
        renderScannerQueue();
      }

      export function selectScannerQueueItem(event) {
        const button = event.target.closest("[data-scanner-item]");
        if (!button) return;
        selectedScannerItemId = button.dataset.scannerItem || "";
        renderScannerQueue();
        focusSelectedScannerItem();
      }

      export function moveScannerQueueSelection(event) {
        if (!["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft"].includes(event.key)) return;
        const visible = scannerQueueFilter === "history" ? scannerHistory : visibleScannerQueue();
        if (!visible.length) return;
        event.preventDefault();
        const current = Math.max(0, visible.findIndex((item) => item.id === selectedScannerItemId));
        const forwards = event.key === "ArrowDown" || event.key === "ArrowRight";
        const next = (current + (forwards ? 1 : -1) + visible.length) % visible.length;
        selectedScannerItemId = visible[next].id;
        renderScannerQueue();
        focusSelectedScannerItem();
      }

      export function focusSelectedScannerItem() {
        requestAnimationFrame(() => fields.scannerQueue.querySelector(".scanner-queue-item.active")?.focus({ preventScroll: true }));
      }

      export function renderScannerQueueDetail() {
        const item = scannerQueue.find((entry) => entry.id === selectedScannerItemId);
        if (!item) {
          renderScopeStrip(scannerScopeStates(null));
          return;
        }
        const createConflict = scannerCreateConflicts.get(item.id) || null;
        const candidates = scannerCandidatesForItem(item);
        const bucket = scannerQueueCauseBucket(item, candidates);
        const visibleCandidates = candidates.slice(0, 3);
        const hiddenCandidates = candidates.slice(3);
        const distinctReviewReady = Boolean(createConflict?.reviewToken);
        const createDraft = createConflict?.draft || {};
        const createAction = candidates.length
          ? distinctReviewReady ? "create-distinct" : "review-distinct"
          : "create-detected";
        const createHeading = candidates.length
          ? distinctReviewReady ? "Confirmar obra distinta" : "¿Ninguna coincide?"
          : "Agregar al catálogo personal";
        const createDescription = candidates.length
          ? distinctReviewReady
            ? `La comprobación final encontró las fichas de arriba. Confirmar conserva ambas obras, crea una ficha separada y registra ${actionObjectLabel(item)} con su identidad.`
            : "Corregí título, año o tipo si hace falta. Revisaremos otra vez tu catálogo antes de permitir una ficha separada."
          : "Esta acción crea una ficha pendiente y vincula su disponibilidad física. El año es obligatorio y el catálogo se comprueba nuevamente antes de escribir.";
        const createButtonLabel = candidates.length
          ? distinctReviewReady
            ? `Conservar ambas y vincular ${actionObjectLabel(item)}`
            : "Revisar alta como obra distinta"
          : `Agregar obra y vincular ${actionObjectLabel(item)}`;
        const parts = Array.isArray(item.parts) && item.parts.length ? item.parts : [{
          name: item.name,
          relative_path: item.relative_path,
          size_bytes: item.size_bytes,
          part: ""
        }];
        const multipart = parts.length > 1;
        const totalSize = parts.reduce((total, part) => total + Number(part.size_bytes || 0), 0);
        const actionObject = multipart ? `${parts.length} partes` : "archivo";
        fields.scannerQueueDetail.innerHTML = `
          <header class="scanner-case-heading">
            <div>
              <span class="section-kicker">${multipart ? "Obra multiparte" : item.state === "review" ? "Coincidencia ambigua" : "Archivo nuevo"}</span>
              <h3>${escapeHtml(item.detected_title || item.name || "Sin título")}</h3>
              <p>${multipart ? `${parts.length} archivos serán tratados como una sola obra.` : escapeHtml(item.relative_path || item.name || "")}</p>
            </div>
            <span class="member-state ${scannerQueueCauseBadgeClass(bucket)}">${escapeHtml(scannerQueueCauseLabel(bucket))}</span>
          </header>
          <div class="scanner-scope-note" role="note">
            <strong>${candidates.length ? "Vincular con una obra existente" : "No encontramos una coincidencia segura"}</strong>
            <span>${candidates.length
              ? `Elegí la ficha que representa ${multipart ? "estas partes" : "este archivo"}. Vincular sólo registra su disponibilidad física; no crea ni combina fichas.`
              : `La comprobación automática no es exhaustiva: puede no reconocer variantes de título o ediciones. Buscá en tu catálogo antes de dar de alta una ficha nueva; si confirmás que no está, podés agregarla y vincular ${multipart ? "estas partes" : "este archivo"} sin marcarla como vista.`}</span>
          </div>
          <dl class="scanner-file-facts">
            <div><dt>Biblioteca</dt><dd>${escapeHtml(item.library_name || "Biblioteca")}</dd></div>
            <div><dt>Año detectado</dt><dd>${escapeHtml(item.detected_year || "Sin año")}</dd></div>
            <div><dt>Tipo detectado</dt><dd>${escapeHtml(importKindLabel(item.detected_kind) || "Película")}</dd></div>
            <div><dt>${multipart ? "Archivos y tamaño" : "Tamaño"}</dt><dd>${multipart ? `${parts.length} · ` : ""}${escapeHtml(formatImportBytes(totalSize))}</dd></div>
          </dl>
          ${multipart ? `<section class="scanner-parts" aria-label="Partes detectadas"><strong>Archivos agrupados</strong><div>${parts.map((part, index) => `<div><span>${escapeHtml(part.part ? `Parte ${part.part}` : `Archivo ${index + 1}`)}</span><code>${escapeHtml(part.relative_path || part.name || "")}</code><small>${escapeHtml(formatImportBytes(part.size_bytes))}</small></div>`).join("")}</div></section>` : ""}
          ${candidates.length ? `<section class="scanner-candidates"><div class="scanner-candidates-heading"><div><h4>Comparar coincidencias (${candidates.length})</h4><p>La similitud orienta la revisión; verificá título, año y fuente antes de vincular.</p></div></div>${visibleCandidates.map((candidate, index) => scannerCandidate(candidate, item, index)).join("")}${hiddenCandidates.length ? `<details class="scanner-candidates-more"><summary>Ver ${hiddenCandidates.length} candidata${hiddenCandidates.length === 1 ? "" : "s"} más</summary>${hiddenCandidates.map((candidate, index) => scannerCandidate(candidate, item, index + 3)).join("")}</details>` : ""}</section>` : ""}
          <section class="scanner-confirm-detected${candidates.length ? " scanner-create-guard" : ""}${distinctReviewReady ? " is-confirming" : ""}">
            <div><h4>${createHeading}</h4><p>${createDescription}</p></div>
            ${candidates.length ? "" : `<button class="quiet-action" type="button" data-scanner-search-local data-file-id="${escapeAttr(item.id)}">Buscar en tu catálogo</button>`}
            <form data-scanner-confirm-form>
              <label><span>Título</span><input name="title" value="${escapeAttr(createDraft.title ?? item.detected_title ?? "")}" maxlength="240" required></label>
              <label><span>Año</span><input name="year" value="${escapeAttr(createDraft.year ?? item.detected_year ?? "")}" inputmode="numeric" pattern="(18|19|20|21)[0-9]{2}" maxlength="4" required></label>
              <label><span>Tipo</span><select name="kind">${["pelicula", "serie", "anime", "documental"].map((kind) => `<option value="${kind}" ${kind === (createDraft.kind || item.detected_kind) ? "selected" : ""}>${importKindLabel(kind)}</option>`).join("")}</select></label>
              <button class="action-primary" type="submit" data-scanner-review="${createAction}" data-file-id="${escapeAttr(item.id)}">${createButtonLabel}</button>
            </form>
          </section>
          <footer class="scanner-case-actions">
            <div><strong>¿No pertenece al inventario?</strong><span>Omitir retira ${multipart ? "todas las partes" : "el archivo"} de esta cola mientras no cambien.</span></div>
            <button class="quiet-action danger-action" type="button" data-scanner-review="ignore" data-file-id="${escapeAttr(item.id)}">Omitir ${actionObject}</button>
            <span id="scannerReviewFeedback" role="status" aria-live="polite"></span>
          </footer>`;
        renderScopeStrip(scannerScopeStates(candidates));
      }

      export function renderScannerHistory() {
        if (!scannerHistory.some((entry) => entry.id === selectedScannerItemId)) {
          selectedScannerItemId = scannerHistory[0]?.id || "";
        }
        fields.scannerQueueMeta.textContent = `${scannerHistory.length} ${
          scannerHistory.length === 1 ? "operación" : "operaciones"
        }`;
        fields.scannerQueue.innerHTML = scannerHistory.length
          ? scannerHistory.map(scannerHistoryItem).join("")
          : `<div class="curation-empty compact"><strong>Todavía no hay actividad</strong><p>Las decisiones nuevas aparecerán en este registro.</p></div>`;
        const selected = scannerHistory.find((entry) => entry.id === selectedScannerItemId);
        fields.scannerQueueDetail.innerHTML = selected
          ? scannerHistoryDetail(selected)
          : `<div class="curation-empty"><strong>Sin operación seleccionada</strong><p>Elegí una actividad para revisar su estado.</p></div>`;
        renderScopeStrip(scannerScopeStates(null));
      }

      export function scannerHistoryItem(operation) {
        const selected = operation.id === selectedScannerItemId;
        return `<button class="scanner-queue-item history-item${selected ? " active" : ""}" type="button"
          data-scanner-item="${escapeAttr(operation.id)}" aria-pressed="${selected}">
          <span class="history-operation-mark" aria-hidden="true">${scannerActionLabel(operation.action).charAt(0)}</span>
          <strong>${escapeHtml(operation.label || "Revisión de inventario")}</strong>
          <small>${escapeHtml(formatDateTime(operation.created_at))}</small>
          <span class="pill ${operation.status === "undone" ? "muted" : "good"}">${
            operation.status === "undone" ? "deshecha" : "aplicada"
          }</span>
        </button>`;
      }

      export function scannerHistoryDetail(operation) {
        const summary = operation.summary || {};
        return `<section class="history-detail">
          <header class="scanner-case-heading">
            <div>
              <span class="section-kicker">${escapeHtml(scannerActionLabel(operation.action))}</span>
              <h3>${escapeHtml(operation.label || "Revisión de inventario")}</h3>
            </div>
            <span class="pill ${operation.status === "undone" ? "muted" : "good"}">${
              operation.status === "undone" ? "Deshecha" : "Aplicada"
            }</span>
          </header>
          <dl class="history-facts">
            <div><dt>Fecha</dt><dd>${escapeHtml(formatDateTime(operation.created_at))}</dd></div>
            <div><dt>Alcance</dt><dd>${operation.mode === "session" ? "Sólo esta sesión" : "Persistente"}</dd></div>
            ${summary.file_count > 1 ? `<div><dt>Archivos</dt><dd>${summary.file_count}</dd></div>` : ""}
          </dl>
          <footer class="curation-actions">
            ${operation.can_undo
              ? `<button class="action-primary" type="button" data-operation-action="undo-operation"
                   data-operation-source="scanner" data-operation-id="${escapeAttr(operation.id)}">Deshacer operación</button>`
              : `<span class="history-closed-note">Esta operación ya fue deshecha.</span>`}
          </footer>
        </section>`;
      }

      export function scannerActionLabel(action) {
        return {
          scanner_confirm: "Vinculación",
          scanner_ignore: "Omitido"
        }[action] || "Inventario";
      }

      export function scannerCandidatesForItem(item) {
        const conflict = scannerCreateConflicts.get(item.id);
        const verified = Array.isArray(conflict?.candidates) ? conflict.candidates : [];
        const verifiedKeys = new Set(verified.flatMap(scannerCandidateEquivalenceKeys));
        const detected = (Array.isArray(item.candidates) ? item.candidates : []).filter((candidate) =>
          !scannerCandidateEquivalenceKeys(candidate).some((key) => verifiedKeys.has(key))
        );
        const rows = [...verified, ...detected]
          .sort((left, right) => Number(right.score || 0) - Number(left.score || 0));
        const seen = new Set();
        return rows.filter((candidate) => {
          const identity = candidate.catalog_item_id
            || candidate.id
            || candidate.key
            || [normalizeText(candidate.title), candidate.year, candidate.kind].filter(Boolean).join(":");
          if (!identity || seen.has(identity)) return false;
          seen.add(identity);
          return true;
        });
      }

      export function scannerCandidateEquivalenceKeys(candidate) {
        const year = String(candidate.year || "").trim();
        const kind = String(candidate.kind || "").trim();
        const titles = [
          candidate.title,
          candidate.original_title,
          candidate.spanish_title,
          candidate.english_title,
          ...(Array.isArray(candidate.alternative_titles) ? candidate.alternative_titles : [])
        ];
        const keys = titles
          .map(normalizeText)
          .filter(Boolean)
          .map((title) => `title:${title}|${year}|${kind}`);
        if (candidate.wikidata_id) keys.push(`wikidata:${String(candidate.wikidata_id).toUpperCase()}`);
        if (candidate.mal_id) keys.push(`mal:${String(candidate.mal_id)}`);
        [candidate.url, candidate.wikipedia_url, candidate.imdb_url, candidate.filmaffinity_url, candidate.myanimelist_url]
          .filter(Boolean)
          .forEach((url) => keys.push(`url:${url}`));
        return [...new Set(keys)];
      }

      export function scannerQueueCauseBucket(item, candidates) {
        if (!item.detected_year) return "missing_identity";
        const reasons = new Set(candidates.map((candidate) => candidate.reason));
        if (reasons.has("exact_title_year_mismatch") || reasons.has("exact_title_kind_mismatch")) {
          return "year_type_conflict";
        }
        if (reasons.has("exact_title_missing_year") || reasons.has("exact_title_year_anime_kind_review")) return "likely_existing";
        return "no_signal";
      }

      export function scannerQueueCauseLabel(bucket) {
        return {
          missing_identity: "Falta identidad",
          year_type_conflict: "Conflicto de año/tipo",
          likely_existing: "Probable ficha existente",
          no_signal: "Sin señales"
        }[bucket] || "Sin señales";
      }

      export function scannerQueueCauseBadgeClass(bucket) {
        return { year_type_conflict: "member-state-attention", likely_existing: "member-state-active" }[bucket] || "";
      }

      export function actionObjectLabel(item) {
        return Number(item.file_count || 1) > 1 ? `${item.file_count} partes` : "archivo";
      }

      export function scannerCandidate(candidate, item, index) {
        const title = candidate.spanish_title || candidate.title || candidate.original_title || "Obra sin título";
        const aliases = scannerCandidateAliases(candidate, title);
        const links = scannerCandidateLinks(candidate);
        const catalogItemId = candidate.catalog_item_id || "";
        const action = catalogItemId ? "link-catalog" : "confirm-candidate";
        const reference = catalogItemId
          ? `data-catalog-item-id="${escapeAttr(catalogItemId)}"`
          : `data-candidate-key="${escapeAttr(candidate.key || "")}"`;
        return `<article class="scanner-candidate-card">
          <header class="scanner-candidate-header">
            <div>
              <span class="scanner-candidate-index">Candidata ${index + 1}</span>
              <strong>${escapeHtml(title)}</strong>
              <span class="scanner-candidate-meta">
                ${scannerCandidateOrigin(candidate.catalog_origin) ? `<span class="scanner-candidate-origin">${escapeHtml(scannerCandidateOrigin(candidate.catalog_origin))}</span>` : ""}
                ${escapeHtml(scannerCandidateReason(candidate.reason))} · ${escapeHtml(formatScannerScore(candidate.score))}
              </span>
            </div>
            <button class="action-primary" type="button" data-scanner-review="${action}" ${reference} data-file-id="${escapeAttr(selectedScannerItemId)}">Vincular ${Number(item.file_count || 1) > 1 ? `${item.file_count} partes` : "archivo"}</button>
          </header>
          <div class="scanner-field-comparison" role="table" aria-label="Comparación con ${escapeAttr(title)}">
            <div class="scanner-comparison-head" role="row"><span role="columnheader">Campo</span><span role="columnheader">Archivo</span><span role="columnheader">Obra candidata</span></div>
            ${scannerComparisonRow("Título", item.detected_title || item.name || "Sin título", title)}
            ${scannerComparisonRow("Año", item.detected_year || "Sin año", candidate.year || "Sin año")}
            ${scannerComparisonRow("Tipo", importKindLabel(item.detected_kind) || "Película", importKindLabel(candidate.kind) || "Película")}
          </div>
          ${aliases.length ? `<div class="scanner-candidate-aliases"><span>Otros nombres</span><div>${aliases.map((alias) => `<span>${escapeHtml(alias)}</span>`).join("")}</div></div>` : ""}
          ${links ? `<nav class="scanner-candidate-links" aria-label="Fuentes de ${escapeAttr(title)}">${links}</nav>` : `<span class="scanner-candidate-no-links">Sin fuentes externas asociadas</span>`}
        </article>`;
      }

      export function scannerComparisonRow(label, detected, candidate) {
        const same = normalizeText(detected) === normalizeText(candidate);
        return `<div class="scanner-comparison-row${same ? " is-match" : ""}" role="row">
          <span role="rowheader">${escapeHtml(label)}</span>
          <span role="cell">${escapeHtml(detected)}</span>
          <span role="cell">${escapeHtml(candidate)}</span>
        </div>`;
      }

      export function scannerCandidateAliases(candidate, selectedTitle) {
        const values = [
          candidate.title,
          candidate.original_title,
          candidate.spanish_title,
          candidate.english_title,
          ...(Array.isArray(candidate.alternative_titles) ? candidate.alternative_titles : [])
        ].map((value) => String(value || "").trim()).filter(Boolean);
        const seen = new Set([normalizeText(selectedTitle)]);
        return values.filter((value) => {
          const key = normalizeText(value);
          if (!key || seen.has(key)) return false;
          seen.add(key);
          return true;
        }).slice(0, 8);
      }

      export function scannerCandidateLinks(candidate) {
        const sources = [
          ["Wikipedia", candidate.wikipedia_url, "wikipedia.org"],
          ["IMDb", candidate.imdb_url, "imdb.com"],
          ["FilmAffinity", candidate.filmaffinity_url, "filmaffinity.com"],
          ["MyAnimeList", candidate.myanimelist_url, "myanimelist.net"]
        ];
        if (candidate.url) {
          if (hasHost(candidate.url, "wikipedia.org")) sources.push(["Wikipedia", candidate.url, "wikipedia.org"]);
          else if (hasHost(candidate.url, "imdb.com")) sources.push(["IMDb", candidate.url, "imdb.com"]);
          else if (hasHost(candidate.url, "filmaffinity.com")) sources.push(["FilmAffinity", candidate.url, "filmaffinity.com"]);
          else if (hasHost(candidate.url, "myanimelist.net")) sources.push(["MyAnimeList", candidate.url, "myanimelist.net"]);
        }
        if (/^Q[0-9]+$/i.test(String(candidate.wikidata_id || ""))) {
          sources.push(["Wikidata", `https://www.wikidata.org/wiki/${candidate.wikidata_id}`, "wikidata.org"]);
        }
        const seen = new Set();
        return sources.filter(([, url, host]) => url && hasHost(url, host) && !seen.has(url) && seen.add(url)).map(([label, url]) =>
          `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`
        ).join("");
      }

      export function formatScannerScore(value) {
        const score = Number(value);
        if (!Number.isFinite(score)) return "similitud sin puntaje";
        return `similitud ${Math.round((score <= 1 ? score * 100 : score))}%`;
      }

      export function scannerCandidateOrigin(origin) {
        return { own_catalog: "En tu catálogo", shared_catalog: "Catálogo compartido" }[origin] || "";
      }

      export function scannerCandidateReason(reason) {
        return {
          shared_external_url: "Misma fuente externa",
          shared_wikidata_id: "Mismo ID de Wikidata",
          shared_mal_id: "Mismo ID de MyAnimeList",
          mal_id_conflict: "ID de MyAnimeList diferente",
          exact_title_year: "Título y año exactos",
          exact_title_missing_year: "Título exacto; falta año",
          exact_title_year_mismatch: "Título exacto; año diferente",
          exact_title_year_anime_kind_review: "Título y año exactos; revisar formato de anime",
          exact_title_kind_mismatch: "Título exacto; tipo diferente",
          similar_title_requires_review: "Título similar",
          insufficient_evidence: "Título apenas similar"
        }[reason] || "Coincidencia posible";
      }

      export async function handleScannerReviewAction(event) {
        const searchLocalButton = event.target.closest?.("[data-scanner-search-local]");
        if (searchLocalButton) {
          event.preventDefault();
          const item = scannerQueue.find((entry) => entry.id === (searchLocalButton.dataset.fileId || selectedScannerItemId));
          if (item) await findLocalMatchForItem(item);
          return;
        }
        const button = event.submitter?.closest?.("[data-scanner-review]")
          || event.target.closest?.("[data-scanner-review]")
          || event.target.querySelector?.("[data-scanner-confirm-form] [data-scanner-review]");
        if (!button) return;
        event.preventDefault();
        const action = button.dataset.scannerReview;
        const fileId = button.dataset.fileId || selectedScannerItemId;
        if (action === "ignore") {
          const item = scannerQueue.find((entry) => entry.id === fileId);
          const count = Number(item?.file_count || 1);
          const confirmed = confirm(
            `¿Omitir "${item?.detected_title || item?.name || "este archivo"}"${count > 1 ? ` y sus ${count} partes` : ""}?\n\n`
            + `${count > 1 ? "Dejarán" : "Dejará"} de aparecer en la cola mientras no ${count > 1 ? "cambien" : "cambie"}. No se eliminará nada del disco ni del catálogo. Podés deshacer esta decisión después desde Actividad.`
          );
          if (!confirmed) return;
        }
        const body = {
          action: action === "ignore"
            ? "ignore"
            : ["create-detected", "review-distinct", "create-distinct"].includes(action)
              ? "create"
              : action === "link-catalog" ? "link_catalog" : "confirm"
        };
        if (action === "confirm-candidate") {
          body.candidate_key = button.dataset.candidateKey || "";
        } else if (action === "link-catalog") {
          body.catalog_item_id = button.dataset.catalogItemId || "";
        } else if (["create-detected", "review-distinct", "create-distinct"].includes(action)) {
          const form = button.closest("form");
          if (!form?.reportValidity()) return;
          const data = new FormData(form);
          body.title = data.get("title") || "";
          body.year = data.get("year") || "";
          body.kind = data.get("kind") || "pelicula";
          if (action !== "create-detected") body.distinct_intent = true;
          if (action === "create-distinct") {
            body.distinct_review_token = scannerCreateConflicts.get(fileId)?.reviewToken || "";
          }
        }
        button.disabled = true;
        const feedback = fields.scannerQueueDetail.querySelector("#scannerReviewFeedback");
        if (feedback) {
          feedback.textContent = action === "ignore"
            ? "Omitiendo archivo…"
            : action === "review-distinct" ? "Comprobando coincidencias actuales…"
              : action === "create-distinct" ? "Creando una obra distinta…"
                : action === "create-detected" ? "Comprobando catálogo y creando obra…" : "Guardando vínculo…";
        }
        try {
          const response = await apiFetch(`/api/scanner/queue/${encodeURIComponent(fileId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (response.status === 409 && payload.reason === "possible_duplicate") {
            scannerCreateConflicts.set(
              fileId,
              {
                candidates: (payload.candidates || []).map((candidate) => ({
                  ...candidate,
                  catalog_item_id: candidate.id || ""
                })),
                reviewToken: payload.distinct_review_token || "",
                draft: {
                  title: body.title || "",
                  year: body.year || "",
                  kind: body.kind || "pelicula"
                }
              }
            );
            renderScannerQueueDetail();
            const conflictFeedback = fields.scannerQueueDetail.querySelector("#scannerReviewFeedback");
            if (conflictFeedback) {
              conflictFeedback.textContent = payload.distinct_review_token
                ? "La comprobación encontró fichas parecidas. Vinculá la correcta o confirmá que querés conservar ambas; todavía no modificamos nada."
                : "Encontramos una ficha existente. Comparala y vinculá el archivo; el catálogo no fue modificado.";
            }
            return;
          }
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          scannerCreateConflicts.delete(fileId);
          const priorIndex = scannerQueue.findIndex((item) => item.id === fileId);
          await Promise.all([loadScannerQueue(), loadCatalog(), loadLibraries()]);
          selectedScannerItemId = scannerQueue[Math.min(priorIndex, scannerQueue.length - 1)]?.id || "";
          renderScannerQueue();
          const affected = Number(payload.item?.file_count || 1);
          const linkedLabel = affected > 1 ? `${affected} partes vinculadas` : "Archivo vinculado";
          const scannerMessage = action === "ignore"
            ? `${affected > 1 ? `${affected} partes omitidas` : "Archivo omitido"}. No se eliminó nada del disco.`
            : ["create-detected", "review-distinct", "create-distinct"].includes(action)
              ? payload.catalog_action === "existing"
                ? `La obra ya estaba en tu catálogo. ${linkedLabel} al inventario compartido.`
                : payload.catalog_action === "created_distinct"
                  ? `Conservamos ambas obras. Nueva ficha creada y ${linkedLabel.toLowerCase()} con su identidad.`
                  : `Obra agregada a tu catálogo. ${linkedLabel} al inventario compartido.`
              : `${linkedLabel} al inventario compartido.`;
          setScannerFeedback(
            `${scannerMessage} ${summarizeScopeStates(scannerActionReceipt(action, payload))}`,
            "success",
            payload.operation
          );
          if (selectedScannerItemId) focusSelectedScannerItem();
          else fields.refreshScannerQueue.focus({ preventScroll: true });
        } catch (error) {
          if (feedback) feedback.textContent = libraryErrorMessage(error.message);
          button.disabled = false;
        }
      }
