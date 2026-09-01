import { availabilityPill } from "../core/availability.js";
import { cachedImageSrc, card } from "../core/card.js";
import { load, loadCatalog } from "../core/catalog-data.js";
import { openDetail } from "../core/detail.js";
import { fields } from "../core/fields.js";
import { asList, escapeAttr, escapeHtml, formatDateTime, localFilesText, meta, normalizeText, sourceLabel } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { mergeFieldLabel, openInternalMergeComparator } from "../core/merge.js";
import { handleOperationFeedbackClick } from "../core/operation-feedback.js";
import { curationScopeStates, renderScopeStrip, summarizeScopeStates } from "../core/scope-strip.js";
import { findLinkForItem } from "../core/search-bridge.js";
import { curationCounts, items, setCurationCounts } from "../core/state.js";

      export let curationCases = [];

      export let curationFilter = "pending";

      export let curationQueueQuery = "";

      export let selectedCurationCaseId = "";

      export let curationLoading = false;

      export let curationHistory = [];

      export let curationHistoryLoading = false;

      export let curationHistoryMode = storedHistoryMode();

      export function setCurationFilter(value) {
        curationFilter = value;
      }

      export function setSelectedCurationCaseId(value) {
        selectedCurationCaseId = value;
      }

      export async function loadCurationQueue({ announce = false } = {}) {
        if (curationLoading) return;
        curationLoading = true;
        fields.inboxView.setAttribute("aria-busy", "true");
        fields.refreshCuration.disabled = true;
        if (announce) setCurationFeedback("Actualizando bandeja…", "working");
        try {
          const response = await apiFetch("/api/curation");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationCases = payload.cases || [];
          setCurationCounts({
            pending: 0,
            duplicates: 0,
            missing_link: 0,
            deferred: 0,
            scanner: curationCounts.scanner || 0,
            ...(payload.counts || {})
          });
          const visible = visibleCurationCases();
          if (!visible.some((entry) => entry.id === selectedCurationCaseId)) {
            selectedCurationCaseId = visible[0]?.id || "";
          }
          await loadCurationHistory();
          syncCurationCounts();
          renderCuration();
          if (announce) setCurationFeedback("Bandeja actualizada", "success");
        } catch (error) {
          console.error("[catalog-viewer] curation load failed", error);
          setCurationFeedback("No se pudo cargar la bandeja. Reintentá desde Actualizar bandeja.", "error");
          fields.curationQueue.innerHTML = "";
          fields.curationDetail.innerHTML = curationEmptyState("Bandeja no disponible", "La colección permanece intacta.");
        } finally {
          curationLoading = false;
          fields.inboxView.setAttribute("aria-busy", "false");
          fields.refreshCuration.disabled = false;
        }
      }

      export async function loadCurationHistory() {
        if (curationHistoryLoading) return;
        curationHistoryLoading = true;
        try {
          const response = await apiFetch(`/api/curation/history?mode=${encodeURIComponent(curationHistoryMode)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationHistory = payload.operations || [];
          fields.curationHistoryCount.textContent = payload.count || 0;
        } catch (error) {
          console.error("[catalog-viewer] curation history load failed", error);
          curationHistory = [];
          fields.curationHistoryCount.textContent = "!";
          if (curationFilter === "history") {
            setCurationFeedback("No se pudo cargar el historial de curaduría.", "error");
          }
        } finally {
          curationHistoryLoading = false;
        }
      }

      export function storedHistoryMode() {
        try {
          return localStorage.getItem("movie-inbox-curation-history-mode") === "session"
            ? "session"
            : "persistent";
        } catch (_) {
          return "persistent";
        }
      }

      export async function changeCurationHistoryMode() {
        curationHistoryMode = fields.persistCurationHistory.checked ? "persistent" : "session";
        try {
          localStorage.setItem("movie-inbox-curation-history-mode", curationHistoryMode);
        } catch (_) {
          // The preference remains active for this page even when storage is unavailable.
        }
        fields.persistCurationHistory.nextElementSibling.textContent = curationHistoryMode === "persistent"
          ? "Historial persistente"
          : "Sólo esta sesión";
        selectedCurationCaseId = "";
        await loadCurationHistory();
        renderCuration();
        setCurationFeedback(
          curationHistoryMode === "persistent"
            ? "Las próximas decisiones conservarán Deshacer después de reiniciar."
            : "Las próximas decisiones podrán deshacerse sólo durante esta sesión.",
          "success"
        );
      }

      export async function clearCurationHistory() {
        const count = curationHistory.length;
        if (!count) {
          setCurationFeedback("No hay actividad para limpiar.", "");
          return;
        }
        const confirmed = confirm(
          `Eliminar ${count} ${count === 1 ? "operación" : "operaciones"} del historial? Ya no podrán deshacerse.`
        );
        if (!confirmed) return;
        fields.clearCurationHistory.disabled = true;
        try {
          const response = await apiFetch("/api/curation/history/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              history_mode: curationHistoryMode,
              confirmed: true
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationHistory = [];
          selectedCurationCaseId = "";
          syncCurationCounts();
          renderCuration();
          setCurationFeedback("Historial eliminado.", "success");
        } catch (error) {
          console.error("[catalog-viewer] history clear failed", error);
          setCurationFeedback("No se pudo limpiar el historial. El catálogo no fue modificado.", "error");
        } finally {
          fields.clearCurationHistory.disabled = false;
        }
      }

      export async function autoResolveDuplicates() {
        fields.autoResolveCuration.disabled = true;
        setCurationFeedback("Buscando duplicados que se puedan combinar solos…", "working");
        try {
          const response = await apiFetch("/api/curation/auto-resolve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ history_mode: curationHistoryMode })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          await loadCurationQueue();
          const { resolved, needs_review: needsReview } = payload;
          setCurationFeedback(
            resolved
              ? `${resolved} ${resolved === 1 ? "caso combinado automáticamente" : "casos combinados automáticamente"}${needsReview ? `. ${needsReview} ${needsReview === 1 ? "sigue necesitando" : "siguen necesitando"} tu revisión.` : "."}`
              : "Ningún duplicado se pudo combinar solo — todos necesitan tu revisión.",
            "success"
          );
        } catch (error) {
          console.error("[catalog-viewer] auto-resolve duplicates failed", error);
          setCurationFeedback("No se pudo resolver duplicados automáticamente.", "error");
        } finally {
          fields.autoResolveCuration.disabled = false;
        }
      }

      export function syncCurationCounts() {
        fields.curationPendingCount.textContent = curationCounts.pending || 0;
        fields.curationDuplicateCount.textContent = curationCounts.duplicates || 0;
        fields.curationMissingCount.textContent = curationCounts.missing_link || 0;
        fields.curationDeferredCount.textContent = curationCounts.deferred || 0;
        fields.curationHistoryCount.textContent = curationHistory.length || 0;
        fields.scannerQueueCount.textContent = curationCounts.scanner || 0;
        const personal = Number(curationCounts.pending || 0);
        const scanner = Number(curationCounts.scanner || 0);
        fields.inboxBadge.textContent = personal;
        fields.inboxBadge.hidden = !(personal > 0);
        fields.inboxScannerBadge.textContent = scanner;
        fields.inboxScannerBadge.hidden = !(scanner > 0);
        fields.inboxButton.setAttribute("aria-label", inboxBadgeAriaLabel(personal, scanner));
      }

      export function inboxBadgeAriaLabel(personal, scanner) {
        const parts = [];
        if (personal) {
          parts.push(
            `${personal} ${personal === 1 ? "decisión pendiente" : "decisiones pendientes"} en tu catálogo`
          );
        }
        if (scanner) {
          parts.push(
            `${scanner} ${scanner === 1 ? "pendiente" : "pendientes"} en el inventario de la instancia`
          );
        }
        return parts.length ? `Bandeja, ${parts.join(" y ")}` : "Bandeja, sin decisiones pendientes";
      }

      export function handleCurationClick(event) {
        if (handleOperationFeedbackClick(event)) return;
        const filter = event.target.closest("[data-curation-filter]");
        if (filter) {
          curationFilter = filter.dataset.curationFilter || "pending";
          selectedCurationCaseId = "";
          renderCuration();
          return;
        }
        const queueItem = event.target.closest("[data-curation-case]");
        if (queueItem) {
          selectedCurationCaseId = queueItem.dataset.curationCase || "";
          renderCuration();
          return;
        }
        const action = event.target.closest("[data-curation-action]");
        if (!action) return;
        const actionName = action.dataset.curationAction;
        if (actionName === "undo-operation") {
          undoCurationOperation(action.dataset.operationId || selectedCurationCaseId);
          return;
        }
        const selected = curationCases.find((entry) => entry.id === selectedCurationCaseId);
        if (!selected) return;
        if (actionName === "open-member") {
          const member = caseMembers(selected).find((entry) => entry.ref === action.dataset.memberRef);
          if (member) openCurationItem(member);
          return;
        }
        if (actionName === "open-primary") {
          openCurationItem(selected.primary);
          return;
        }
        if (actionName === "open-secondary" && selected.secondary) {
          openCurationItem(selected.secondary);
          return;
        }
        if (actionName === "find-link") {
          findLinkFromCuration(selected.primary);
          return;
        }
        if (actionName === "compare-duplicate" && caseMembers(selected).length >= 2) {
          openInternalMergeComparator(selected);
          return;
        }
        if (actionName === "link-deferred") updateLinkCuration(selected, "deferred");
        if (actionName === "link-not-required") updateLinkCuration(selected, "not_required");
        if (actionName === "link-pending") updateLinkCuration(selected, "pending");
        if (actionName === "duplicate-deferred") updateDuplicateCuration(selected, "deferred");
        if (actionName === "duplicate-not-duplicate") updateDuplicateCuration(selected, "not_duplicate");
        if (actionName === "duplicate-pending") updateDuplicateCuration(selected, "pending");
      }

      export function visibleCurationCases() {
        if (curationFilter === "history") return [];
        const query = normalizeText(curationQueueQuery);
        return curationCases.filter((entry) => {
          if (curationFilter === "deferred" && entry.status !== "deferred") return false;
          if (curationFilter !== "deferred" && entry.status !== "pending") return false;
          if (curationFilter === "duplicate" && entry.type !== "duplicate") return false;
          if (curationFilter === "missing_link" && entry.type !== "missing_link") return false;
          if (!query) return true;
          const searchable = entry.type === "duplicate" ? caseMembers(entry) : [entry.primary || {}];
          return searchable.flatMap((item) => [item.title, item.year, item.kind])
            .some((value) => normalizeText(value).includes(query));
        });
      }

      export function caseMembers(entry) {
        if (Array.isArray(entry?.members)) return entry.members;
        return [entry?.primary, entry?.secondary].filter(Boolean);
      }

      export function searchCurationQueue(event) {
        curationQueueQuery = event.target.value || "";
        renderCuration();
      }

      export function moveCurationQueueSelection(event) {
        if (!["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft"].includes(event.key)) return;
        const visible = curationFilter === "history" ? curationHistory : visibleCurationCases();
        if (!visible.length) return;
        event.preventDefault();
        const current = Math.max(0, visible.findIndex((entry) => entry.id === selectedCurationCaseId));
        const forwards = event.key === "ArrowDown" || event.key === "ArrowRight";
        const next = (current + (forwards ? 1 : -1) + visible.length) % visible.length;
        selectedCurationCaseId = visible[next].id;
        renderCuration();
        focusSelectedCurationItem();
      }

      export function focusSelectedCurationItem() {
        requestAnimationFrame(() => fields.curationQueue.querySelector(".curation-queue-item.selected")?.focus({ preventScroll: true }));
      }

      export function renderCuration() {
        if (curationFilter === "history") {
          renderCurationHistory();
          return;
        }
        const visible = visibleCurationCases();
        if (!visible.some((entry) => entry.id === selectedCurationCaseId)) {
          selectedCurationCaseId = visible[0]?.id || "";
        }
        fields.inboxView.querySelectorAll("[data-curation-filter]").forEach((button) => {
          const active = button.dataset.curationFilter === curationFilter;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        const labels = {
          pending: "Decisiones pendientes",
          duplicate: "Posibles duplicados",
          missing_link: "Entradas sin referencia",
          deferred: "Decisiones pospuestas"
        };
        fields.curationQueueTitle.textContent = labels[curationFilter] || labels.pending;
        fields.curationQueueMeta.textContent = `${visible.length} ${visible.length === 1 ? "caso" : "casos"}`;
        fields.curationQueue.innerHTML = visible.length
          ? visible.map(curationQueueItem).join("")
          : curationEmptyState(
              curationFilter === "deferred" ? "No hay decisiones pospuestas" : "No quedan casos en esta cola",
              curationFilter === "pending" ? "La bandeja está al día." : "Probá otro filtro."
            );
        const selected = visible.find((entry) => entry.id === selectedCurationCaseId);
        fields.curationDetail.innerHTML = selected
          ? curationCaseDetail(selected)
          : curationEmptyState("Sin caso seleccionado", "La evidencia aparecerá cuando haya una decisión disponible.");
        renderScopeStrip(curationScopeStates());
      }

      export function renderCurationHistory() {
        if (!curationHistory.some((entry) => entry.id === selectedCurationCaseId)) {
          selectedCurationCaseId = curationHistory[0]?.id || "";
        }
        fields.inboxView.querySelectorAll("[data-curation-filter]").forEach((button) => {
          const active = button.dataset.curationFilter === "history";
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        fields.curationQueueTitle.textContent = curationHistoryMode === "persistent"
          ? "Actividad persistente"
          : "Actividad de esta sesión";
        fields.curationQueueMeta.textContent = `${curationHistory.length} ${
          curationHistory.length === 1 ? "operación" : "operaciones"
        }`;
        fields.curationQueue.innerHTML = curationHistory.length
          ? curationHistory.map(curationHistoryItem).join("")
          : curationEmptyState("Todavía no hay actividad", "Las decisiones nuevas aparecerán en este registro.");
        const selected = curationHistory.find((entry) => entry.id === selectedCurationCaseId);
        fields.curationDetail.innerHTML = selected
          ? curationHistoryDetail(selected)
          : curationEmptyState("Sin operación seleccionada", "Elegí una actividad para revisar su estado.");
        renderScopeStrip(curationScopeStates());
      }

      export function curationHistoryItem(operation) {
        const selected = operation.id === selectedCurationCaseId;
        return `<button class="curation-queue-item history-item ${selected ? "selected" : ""}" type="button"
          data-curation-case="${escapeAttr(operation.id)}" aria-pressed="${selected}">
          <span class="history-operation-mark" aria-hidden="true">${operation.action.startsWith("merge") ? "M" : "D"}</span>
          <span class="curation-queue-copy">
            <span class="curation-queue-type">${escapeHtml(curationActionLabel(operation.action))}</span>
            <strong>${escapeHtml(operation.label || "Decisión de curaduría")}</strong>
            <small>${escapeHtml(formatDateTime(operation.created_at))}</small>
          </span>
          <span class="pill ${operation.status === "undone" ? "muted" : "good"}">${
            operation.status === "undone" ? "deshecha" : "aplicada"
          }</span>
        </button>`;
      }

      export function curationHistoryDetail(operation) {
        const summary = operation.summary || {};
        const changedFields = asList(summary.changed_fields);
        return `<section class="history-detail">
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${escapeHtml(curationActionLabel(operation.action))}</span>
              <h3>${escapeHtml(operation.label || "Decisión de curaduría")}</h3>
            </div>
            <span class="pill ${operation.status === "undone" ? "muted" : "good"}">${
              operation.status === "undone" ? "Deshecha" : "Aplicada"
            }</span>
          </header>
          <dl class="history-facts">
            <div><dt>Fecha</dt><dd>${escapeHtml(formatDateTime(operation.created_at))}</dd></div>
            <div><dt>Alcance</dt><dd>${operation.mode === "session" ? "Sólo esta sesión" : "Persistente"}</dd></div>
            ${summary.survivor_title ? `<div><dt>Entrada final</dt><dd>${escapeHtml(summary.survivor_title)}</dd></div>` : ""}
            ${summary.member_count ? `<div><dt>Entradas tratadas</dt><dd>${escapeHtml(summary.member_count)}</dd></div>` : ""}
            ${changedFields.length ? `<div><dt>Campos revisados</dt><dd>${changedFields.length}</dd></div>` : ""}
          </dl>
          ${changedFields.length
            ? `<div class="history-field-list">${changedFields.map((field) => `<span>${escapeHtml(mergeFieldLabel(field))}</span>`).join("")}</div>`
            : ""}
          <footer class="curation-actions">
            ${operation.can_undo
              ? `<button class="action-primary" type="button" data-curation-action="undo-operation"
                   data-operation-id="${escapeAttr(operation.id)}">Deshacer operación</button>`
              : `<span class="history-closed-note">Esta operación ya fue deshecha.</span>`}
          </footer>
        </section>`;
      }

      export function curationActionLabel(action) {
        return {
          merge: "Combinación",
          merge_group: "Combinación grupal",
          link_curation: "Referencia",
          duplicate_curation: "Duplicado",
          duplicate_group_curation: "Grupo de duplicados"
        }[action] || "Curaduría";
      }

      export function curationQueueItem(entry) {
        const members = caseMembers(entry);
        const item = entry.type === "duplicate" ? members[0] : entry.primary;
        const selected = entry.id === selectedCurationCaseId;
        const type = entry.type === "duplicate" ? "Duplicado" : "Sin referencia";
        return `<button class="curation-queue-item ${selected ? "selected" : ""}" type="button"
          data-curation-case="${escapeAttr(entry.id)}" aria-pressed="${selected}">
          ${curationThumb(item)}
          <span class="curation-queue-copy">
            <span class="curation-queue-type">${escapeHtml(type)}${entry.status === "deferred" ? " · Pospuesta" : ""}</span>
            <strong>${escapeHtml(item.title || "Sin título")}</strong>
            <small>${escapeHtml([item.year, item.kind].filter(Boolean).join(" · ") || "Sin año")}</small>
            ${entry.type === "duplicate"
              ? `<small class="curation-queue-duplicate-hint">${members.length} entradas conectadas</small>`
              : ""}
          </span>
          <span class="curation-queue-arrow" aria-hidden="true">→</span>
        </button>`;
      }

      export function curationCaseDetail(entry) {
        return entry.type === "duplicate"
          ? duplicateCurationDetail(entry)
          : missingLinkCurationDetail(entry);
      }

      export function duplicateCurationDetail(entry) {
        const deferred = entry.status === "deferred";
        const members = caseMembers(entry);
        return `
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${deferred ? "Decisión pospuesta" : "Revisión necesaria"}</span>
              <h3>¿Son la misma obra?</h3>
            </div>
            <span class="pill warning">${members.length} posibles duplicados</span>
          </header>
          ${curationEvidence(entry.evidence)}
          <div class="curation-group" aria-label="${members.length} entradas del grupo">
            ${members.map((member, index) => curationRecord(
              member,
              `Entrada ${index + 1} de ${members.length}`,
              "open-member",
              "",
              member.ref
            )).join("")}
          </div>
          <footer class="curation-actions">
            ${deferred
              ? `<button class="action-primary" type="button" data-curation-action="compare-duplicate">Comparar ${members.length} entradas</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-pending">Volver a pendientes</button>`
              : `<button class="action-primary" type="button" data-curation-action="compare-duplicate">Comparar ${members.length} entradas</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-not-duplicate">Ninguna es la misma obra</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-deferred">Posponer</button>`}
          </footer>
        `;
      }

      export function missingLinkCurationDetail(entry) {
        const deferred = entry.status === "deferred";
        return `
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${deferred ? "Decisión pospuesta" : "Referencia pendiente"}</span>
              <h3>${escapeHtml(entry.primary.title || "Sin título")}</h3>
            </div>
            <span class="pill muted">Sin referencia</span>
          </header>
          ${curationEvidence(entry.evidence)}
          <div class="curation-single-record">${curationRecord(entry.primary, "Entrada actual", "open-primary")}</div>
          <footer class="curation-actions">
            ${deferred
              ? `<button class="action-primary" type="button" data-curation-action="link-pending">Volver a pendientes</button>`
              : `<button class="action-primary" type="button" data-curation-action="find-link">Buscar referencia</button>
                 <button class="quiet-action" type="button" data-curation-action="link-not-required">No requiere referencia</button>
                 <button class="quiet-action" type="button" data-curation-action="link-deferred">Posponer</button>`}
          </footer>
        `;
      }

      export function curationRecord(item, label, action, positionLabel = "", memberRef = "") {
        if (!item) return "";
        return `<article class="curation-record">
          <span class="curation-record-label">${escapeHtml(label)}${positionLabel ? ` · ${escapeHtml(positionLabel)}` : ""}</span>
          <div class="curation-record-main">
            ${curationThumb(item, true)}
            <div>
              <h4>${escapeHtml(item.title || "Sin título")}</h4>
              <div class="meta">${meta(item.year)}${meta(item.kind)}${meta(sourceLabel(item.source))}</div>
              <div class="meta">${meta(item.added_at ? `Agregada ${formatDateTime(item.added_at)}` : "")}${meta(localFilesText(item))}</div>
              <div class="card-badges">
                ${availabilityPill(item)}
                <span class="pill ${item.status === "watched" ? "good" : "muted"}">${item.status === "watched" ? "vista" : "pendiente"}</span>
              </div>
            </div>
          </div>
          <button class="text-action curation-open-record" type="button" data-curation-action="${action}"
            ${memberRef ? `data-member-ref="${escapeAttr(memberRef)}"` : ""}>Abrir ficha</button>
        </article>`;
      }

      export function duplicateSignalsCollide(left, right) {
        if (!left || !right) return false;
        const fileSignal = (item) => {
          if (Array.isArray(item.local_files)) return localFilesText(item).trim();
          return String(item.local_files_count || 0);
        };
        return fileSignal(left) === fileSignal(right)
          && sourceLabel(left.source) === sourceLabel(right.source)
          && formatDateTime(left.added_at) === formatDateTime(right.added_at);
      }

      export function curationThumb(item, large = false) {
        const className = large ? "curation-thumb large" : "curation-thumb";
        const title = item?.title || "Sin imagen";
        const fallback = `<span class="${className} curation-thumb-placeholder" aria-hidden="true">${escapeHtml(title.slice(0, 18))}</span>`;
        if (!item?.page_image) return fallback;
        return `<span class="curation-thumb-frame ${large ? "large" : ""}">
          <img class="${className}" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="" loading="lazy" decoding="async">
          ${fallback}
        </span>`;
      }

      export function curationEvidence(evidence) {
        return `<div class="curation-evidence">
          <strong>Evidencia</strong>
          <ul>${asList(evidence).map((row) => `<li>${escapeHtml(row)}</li>`).join("")}</ul>
        </div>`;
      }

      export function curationEmptyState(title, copy) {
        return `<div class="curation-empty"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(copy)}</p></div>`;
      }

      export function openCurationItem(summary) {
        if (!summary?.id) return;
        const contextIds = [...new Set(
          visibleCurationCases()
            .flatMap((entry) => entry.type === "duplicate"
              ? caseMembers(entry).map((member) => member.id)
              : [entry.primary?.id])
            .filter(Boolean)
        )];
        openDetail(summary.id, {
          context: { mode: "curation", label: "Bandeja", ids: contextIds }
        });
      }

      export async function findLinkFromCuration(summary) {
        const item = items.find((entry) => (
          entry.id === summary.id
          && (!summary.source_file || entry._source_file === summary.source_file)
        ));
        if (!item) {
          setCurationFeedback("La entrada ya no está disponible en el catálogo.", "error");
          return;
        }
        await findLinkForItem(item);
      }

      export async function updateLinkCuration(entry, status) {
        await postCurationDecision("/api/curation/link", {
          id: entry.primary.id,
          source_file: entry.primary.source_file,
          status
        });
      }

      export async function updateDuplicateCuration(entry, status) {
        await postCurationDecision("/api/curation/duplicate", {
          members: caseMembers(entry).map((member) => ({
            ref: member.ref,
            id: member.id,
            source_file: member.source_file
          })),
          status
        });
      }

      export async function postCurationDecision(path, body) {
        fields.curationDetail.querySelectorAll("button").forEach((button) => { button.disabled = true; });
        setCurationFeedback("Guardando decisión…", "working");
        try {
          const response = await apiFetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...body,
              history_mode: curationHistoryMode
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedCurationCaseId = "";
          await loadCatalog();
          setCurationFeedback(
            `Decisión guardada. ${summarizeScopeStates(curationScopeStates())}`,
            "success",
            payload.operation
          );
        } catch (error) {
          console.error("[catalog-viewer] curation update failed", error);
          setCurationFeedback("No se pudo guardar la decisión. Reintentá sin salir de la Bandeja.", "error");
          renderCuration();
        }
      }

      export async function undoCurationOperation(operationId) {
        if (!operationId) return;
        fields.curationDetail.querySelectorAll("button").forEach((button) => { button.disabled = true; });
        setCurationFeedback("Restaurando estado anterior…", "working");
        try {
          const response = await apiFetch("/api/curation/undo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              operation_id: operationId,
              history_mode: curationHistoryMode
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            const reason = payload.reason || `HTTP ${response.status}`;
            if (response.status === 409) {
              throw new Error("La entrada cambió después de esta operación. Revisala antes de restaurar.");
            }
            throw new Error(reason);
          }
          selectedCurationCaseId = operationId;
          await loadCatalog();
          curationFilter = "history";
          renderCuration();
          setCurationFeedback("Operación deshecha. Se restauró el estado anterior.", "success");
        } catch (error) {
          console.error("[catalog-viewer] curation undo failed", error);
          setCurationFeedback(error.message || "No se pudo deshacer la operación.", "error");
          renderCuration();
        }
      }

      export function setCurationFeedback(message, tone = "", operation = null) {
        fields.curationFeedback.innerHTML = operation?.can_undo
          ? `<span>${escapeHtml(message)}</span>
             <button class="text-action" type="button" data-curation-action="undo-operation"
               data-operation-id="${escapeAttr(operation.id)}">Deshacer</button>`
          : escapeHtml(message);
        fields.curationFeedback.dataset.tone = tone;
      }
