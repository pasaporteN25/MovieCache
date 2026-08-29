import { loadCatalog } from "../core/catalog-data.js";
import { fields } from "../core/fields.js";
import { escapeAttr, escapeHtml, setInlineFeedback } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { goToInbox, setInboxMode } from "../core/router.js";
import { curationCounts, currentIdentity } from "../core/state.js";
import { syncCurationCounts } from "./inbox-curation.js";
import { importKindLabel } from "./inbox-imports.js";
import { loadScannerQueue } from "./inbox-scanner.js";

      export let managedLibraries = [];

      export let scannerConfigured = false;

      export let scannerAllowedRoots = [];

      export let selectedLibraryId = "";

      export let librariesLoading = false;

      export let editingLibraryId = "";

      export let browsedLibraryPath = "";

      export let parentLibraryPath = "";

      export let activeLibraryRunId = "";

      export let libraryRunPollTimer = null;

      export async function loadLibraries({ announce = false } = {}) {
        if (librariesLoading || currentIdentity?.user?.role !== "owner") return;
        librariesLoading = true;
        fields.libraryList.setAttribute("aria-busy", "true");
        fields.createLibraryButton.disabled = true;
        if (announce) setLibraryFeedback("Actualizando bibliotecas…");
        try {
          const response = await apiFetch("/api/libraries");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          scannerConfigured = Boolean(payload.configured);
          scannerAllowedRoots = payload.allowed_roots || [];
          managedLibraries = payload.libraries || [];
          curationCounts.scanner = Number(payload.queue_count || 0);
          if (!managedLibraries.some((entry) => entry.id === selectedLibraryId)) {
            selectedLibraryId = managedLibraries[0]?.id || "";
          }
          if (selectedLibraryId) await loadLibraryDetail(selectedLibraryId, { renderAfter: false });
          renderLibraryConfiguration();
          renderLibraries();
          syncCurationCounts();
          if (announce) setLibraryFeedback("Bibliotecas actualizadas.");
        } catch (error) {
          setLibraryFeedback(libraryErrorMessage(error.message), "error");
          fields.libraryList.innerHTML = `<div class="member-list-empty"><strong>Bibliotecas no disponibles</strong><span>Reintentá desde Actualizar datos.</span></div>`;
        } finally {
          librariesLoading = false;
          fields.libraryList.removeAttribute("aria-busy");
          fields.createLibraryButton.disabled = !scannerConfigured;
        }
      }

      export async function loadLibraryDetail(libraryId, { renderAfter = true } = {}) {
        const response = await apiFetch(`/api/libraries/${encodeURIComponent(libraryId)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        const detail = payload.library;
        managedLibraries = managedLibraries.map((entry) => entry.id === detail.id ? detail : entry);
        if (renderAfter) renderLibraries();
        return detail;
      }

      export function renderLibraryConfiguration() {
        if (!scannerConfigured) {
          fields.libraryConfiguration.dataset.state = "disabled";
          fields.libraryConfiguration.innerHTML = `<strong>Inventario administrado desactivado</strong><span>Reiniciá el servidor con al menos un <code>--library-root RUTA</code>.</span>`;
          fields.createLibraryButton.disabled = true;
          return;
        }
        fields.libraryConfiguration.dataset.state = "ready";
        fields.libraryConfiguration.innerHTML = `<strong>${scannerAllowedRoots.length} ${scannerAllowedRoots.length === 1 ? "raíz habilitada" : "raíces habilitadas"}</strong><span>${scannerAllowedRoots.map((root) => `<code>${escapeHtml(root)}</code>`).join(" · ")}</span>`;
      }

      export function renderLibraries() {
        if (!managedLibraries.length) {
          fields.libraryList.innerHTML = `<div class="member-list-empty"><strong>Todavía no hay rutas bajo seguimiento</strong><span>Agregá una biblioteca y ejecutá primero un recorrido de prueba.</span></div>`;
          return;
        }
        fields.libraryList.innerHTML = managedLibraries.map((library) => {
          const selected = library.id === selectedLibraryId;
          const counts = library.counts || {};
          const running = (library.runs || []).find((run) => ["queued", "running"].includes(run.status))
            || (library.status === "scanning" ? { status: "running" } : null);
          const workflow = libraryWorkflow(library, running);
          const lastRun = (library.runs || [])[0];
          const resultOwnsPrimary = Boolean(
            selected
            && workflow.key === "ready_apply"
            && lastRun?.mode === "dry_run"
            && lastRun?.status === "completed"
          );
          const testAgain = !running && workflow.key === "applied"
            ? `<button class="quiet-action" type="button" data-library-action="test" data-library-id="${escapeAttr(library.id)}">Probar cambios</button>`
            : "";
          return `<article class="library-record${selected ? " is-selected" : ""}" data-library-id="${escapeAttr(library.id)}" data-workflow="${escapeAttr(workflow.key)}">
            <div class="library-record-main">
              <button class="library-record-identity" type="button" data-library-action="select" data-library-id="${escapeAttr(library.id)}" aria-expanded="${selected}">
                <span class="library-drive-mark" aria-hidden="true">${escapeHtml(workflow.marker)}</span>
                <span><strong>${escapeHtml(library.name || "Biblioteca")}</strong><code>${escapeHtml(library.root_path || "")}</code></span>
              </button>
              <div class="library-record-state">
                <span class="member-state ${libraryWorkflowClass(workflow.key)}">${escapeHtml(workflow.label)}</span>
                <span>${escapeHtml(workflow.note)}</span>
              </div>
              <dl class="library-record-metrics">
                <div><dt>Archivos</dt><dd>${Number(counts.files || 0)}</dd></div>
                <div><dt>Vinculados</dt><dd>${Number(counts.matched || 0)}</dd></div>
                <div><dt>Comparar</dt><dd>${Number(counts.review || 0)}</dd></div>
                <div><dt>Nuevos</dt><dd>${Number(counts.new || 0)}</dd></div>
              </dl>
              <div class="library-record-actions">
                ${libraryPrimaryAction(library, workflow, running)}
                ${testAgain}
                <button class="quiet-action" type="button" data-library-action="edit" data-library-id="${escapeAttr(library.id)}" ${running ? "disabled" : ""}>Editar</button>
                ${libraryAutomationControl(library, running)}
              </div>
            </div>
            ${selected ? libraryRunPanel(library, running, workflow, resultOwnsPrimary) : ""}
          </article>`;
        }).join("");
      }

      export function libraryWorkflow(library, running) {
        const lastRun = (library.runs || [])[0];
        const scheduled = library.schedule !== "manual";
        const hasInventory = Number(library.last_scan_at || 0) > 0;
        if (running) {
          const knownMode = running.mode === "apply" || running.mode === "dry_run";
          const applying = running.mode === "apply";
          return {
            key: "running",
            marker: "RUN",
            label: !knownMode ? "Recorrido en curso" : applying ? "Aplicación en curso" : "Prueba en curso",
            note: !knownMode
              ? "Procesando la biblioteca"
              : applying
                ? "Actualizando inventario físico"
                : "Lectura sin cambios persistentes",
            action: "",
            actionLabel: !knownMode ? "Procesando recorrido…" : applying ? "Aplicando inventario…" : "Probando recorrido…"
          };
        }
        if (!library.verified_at) {
          return {
            key: "unverified",
            marker: "NEW",
            label: "Sin verificar",
            note: "Primero, una prueba de solo lectura",
            action: "test",
            actionLabel: "Probar recorrido"
          };
        }
        if (lastRun?.mode === "dry_run" && lastRun.status !== "completed") {
          return {
            key: "attention",
            marker: "!",
            label: "Requiere atención",
            note: "La última prueba no quedó lista para aplicar",
            action: "test",
            actionLabel: "Probar de nuevo"
          };
        }
        const testedAfterInventory = lastRun?.mode === "dry_run"
          && lastRun.status === "completed"
          && Number(lastRun.finished_at || lastRun.created_at || 0) >= Number(library.last_scan_at || 0);
        if (!hasInventory || testedAfterInventory) {
          return {
            key: "ready_apply",
            marker: "TEST",
            label: "Lista para aplicar",
            note: scheduled ? `Aplicá antes de habilitar ${scheduleLabel(library.schedule).toLowerCase()}` : "La prueba no modificó el inventario",
            action: "scan",
            actionLabel: "Aplicar inventario"
          };
        }
        if (["offline", "warning", "error"].includes(library.status)) {
          return {
            key: "attention",
            marker: "!",
            label: libraryStatusLabel(library.status),
            note: "Revisá el último recorrido antes de continuar",
            action: "test",
            actionLabel: "Probar de nuevo"
          };
        }
        const note = !scheduled
          ? "Escaneo manual"
          : library.active
            ? `${scheduleLabel(library.schedule)} · automático activo`
            : `${scheduleLabel(library.schedule)} · automático pausado`;
        return {
          key: "applied",
          marker: scheduled && library.active ? "AUTO" : "OK",
          label: "Inventario actualizado",
          note,
          action: "scan",
          actionLabel: "Escanear ahora"
        };
      }

      export function libraryWorkflowClass(value) {
        if (["applied", "running", "ready_apply"].includes(value)) return "member-state-active";
        if (["unverified", "attention"].includes(value)) return "member-state-attention";
        return "member-state-disabled";
      }

      export function libraryPrimaryAction(library, workflow, running) {
        if (running) {
          return `<button class="action-primary library-primary-main" type="button" disabled aria-busy="true">${escapeHtml(workflow.actionLabel)}</button>`;
        }
        if (!workflow.action) return "";
        return `<button class="action-primary library-primary-main" type="button" data-library-action="${escapeAttr(workflow.action)}" data-library-id="${escapeAttr(library.id)}">${escapeHtml(workflow.actionLabel)}</button>`;
      }

      export function libraryAutomationControl(library, running) {
        if (library.schedule === "manual" || !library.last_scan_at) return "";
        return `<label class="library-automation-toggle${library.active ? " is-active" : ""}">
          <input type="checkbox" data-library-action="toggle" data-library-id="${escapeAttr(library.id)}" aria-label="Escaneo automático de ${escapeAttr(library.name || "biblioteca")}" ${library.active ? "checked" : ""} ${running ? "disabled" : ""}>
          <span class="library-toggle-track" aria-hidden="true"><span></span></span>
          <span>Escaneo automático</span>
        </label>`;
      }

      export function libraryRunPanel(library, running, workflow, resultOwnsPrimary) {
        const runs = (library.runs || []).slice(0, 5);
        const lastRun = runs[0];
        return `<div class="library-run-panel">
          <div class="library-run-summary">
            <div><span>Último recorrido</span><strong>${lastRun ? formatLibraryTime(lastRun.finished_at || lastRun.created_at) : "Sin recorridos"}</strong></div>
            <div><span>Próxima ejecución</span><strong>${escapeHtml(libraryNextRunLabel(library))}</strong></div>
            <div><span>Protección de bajas</span><strong>${Math.round(Number(library.max_missing_ratio || 0) * 100)}%</strong></div>
          </div>
          ${running ? `<div class="library-running" role="status"><span class="library-running-signal" aria-hidden="true"></span><strong>${running.status === "queued" ? "Recorrido en cola" : "Leyendo biblioteca"}</strong><span>Podés seguir usando Movie Inbox.</span></div>` : ""}
          ${lastRun && !running ? libraryRunResult(lastRun, library, workflow, resultOwnsPrimary) : ""}
          ${runs.length ? `<details class="library-run-history"><summary>Historial de recorridos</summary><div>${runs.map((run) => `<div><span>${escapeHtml(runModeLabel(run))}</span><strong>${escapeHtml(runStatusLabel(run.status))}</strong><time>${formatLibraryTime(run.finished_at || run.created_at)}</time></div>`).join("")}</div></details>` : ""}
          <div class="library-secondary-actions">
            <button class="text-action" type="button" data-library-action="scanner" data-library-id="${escapeAttr(library.id)}">Abrir pendientes</button>
            <button class="text-action danger-action" type="button" data-library-action="delete" data-library-id="${escapeAttr(library.id)}" ${running ? "disabled" : ""}>Quitar seguimiento</button>
          </div>
        </div>`;
      }

      export function libraryNextRunLabel(library) {
        if (library.schedule === "manual") return "Sólo manual";
        if (!library.last_scan_at) return "Después de aplicar";
        if (!library.active) return "Automatización pausada";
        return library.next_scan_at ? formatLibraryTime(library.next_scan_at) : "Al iniciar el planificador";
      }

      export function libraryRunResult(run, library, workflow, resultOwnsPrimary) {
        const summary = run.summary || {};
        const preview = run.preview || [];
        const newlyExcluded = run.newly_excluded || [];
        const parts = [
          `${Number(summary.discovered || 0)} archivos`,
          `${Number(summary.matched || 0)} vinculados`,
          `${Number(summary.review || 0)} para comparar`,
          `${Number(summary.new || 0)} nuevos`
        ];
        const errors = run.errors || [];
        const outcome = run.mode === "dry_run"
          ? run.status === "completed"
            ? "La prueba terminó sin modificar el inventario ni la disponibilidad."
            : "La prueba no modificó el inventario. Corregí las advertencias y volvé a probar."
          : run.status === "blocked"
            ? "La protección de bajas conservó el último inventario válido."
            : run.status === "completed"
              ? "El inventario compartido y la disponibilidad quedaron actualizados."
              : "Se aplicaron los resultados seguros y quedaron advertencias para revisar.";
        return `<div class="library-run-result" data-state="${escapeAttr(run.status || "")}">
          <strong>${escapeHtml(runStatusLabel(run.status))}</strong>
          <span>${escapeHtml(parts.join(" · "))}</span>
          ${errors.length ? `<details><summary>${errors.length} ${errors.length === 1 ? "advertencia" : "advertencias"}</summary><ul>${errors.slice(0, 8).map((error) => `<li>${escapeHtml(error)}</li>`).join("")}</ul></details>` : ""}
          ${preview.length ? `<details class="library-run-preview"><summary>Revisar muestra (${preview.length})</summary><div class="library-run-preview-list">${preview.map((item) => `
            <div class="library-run-preview-row">
              <span class="scanner-queue-state">${escapeHtml(libraryPreviewStateLabel(item.state))}</span>
              <strong>${escapeHtml(item.title || "Sin título detectado")}</strong>
              <span>${escapeHtml([item.year, importKindLabel(item.kind)].filter(Boolean).join(" · "))}</span>
              <code>${escapeHtml(item.relative_path || "")}</code>
            </div>`).join("")}</div></details>` : ""}
          ${newlyExcluded.length ? `<details class="library-run-preview library-run-newly-excluded"><summary>${newlyExcluded.length} ${newlyExcluded.length === 1 ? "archivo ya registrado quedó excluido por una regla" : "archivos ya registrados quedaron excluidos por una regla"}</summary><div class="library-run-preview-list">${newlyExcluded.map((item) => `
            <div class="library-run-preview-row">
              <strong>${escapeHtml(item.title || "Sin título detectado")}</strong>
              <span>${escapeHtml(item.year || "")}</span>
              <code>${escapeHtml(item.relative_path || "")}</code>
            </div>`).join("")}</div></details>` : ""}
          <div class="library-run-outcome">
            <span>${escapeHtml(outcome)}</span>
            ${resultOwnsPrimary ? `<button class="action-primary library-primary-result" type="button" data-library-action="scan" data-library-id="${escapeAttr(library.id)}">${escapeHtml(workflow.actionLabel)}</button>` : ""}
          </div>
        </div>`;
      }

      export function libraryPreviewStateLabel(value) {
        return { matched: "Vinculada", new: "Nueva", review: "Comparar", ignored: "Ignorada" }[value] || "Detectada";
      }

      export async function handleLibraryAction(event) {
        const button = event.target.closest("[data-library-action]");
        if (!button) return;
        const library = managedLibraries.find((entry) => entry.id === button.dataset.libraryId);
        if (!library) return;
        const action = button.dataset.libraryAction;
        if (action === "select") {
          selectedLibraryId = selectedLibraryId === library.id ? "" : library.id;
          if (selectedLibraryId) await loadLibraryDetail(library.id);
          else renderLibraries();
          return;
        }
        if (action === "edit") {
          openLibraryDialog(library);
          return;
        }
        if (action === "scanner") {
          await goToInbox();
          await setInboxMode("scanner");
          return;
        }
        if (action === "delete") {
          const confirmed = confirm(`¿Quitar el seguimiento de "${library.name}"? El inventario verificado de esta ruta dejará de aportar disponibilidad.`);
          if (!confirmed) return;
          await deleteManagedLibrary(library);
          return;
        }
        button.disabled = true;
        try {
          if (action === "test" || action === "scan") {
            await queueLibraryRun(library, action === "test" ? "dry_run" : "apply");
          } else if (action === "toggle") {
            const active = button instanceof HTMLInputElement ? button.checked : !library.active;
            const response = await apiFetch(`/api/libraries/${encodeURIComponent(library.id)}/status`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ active })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
            setLibraryFeedback(payload.library.active ? `Escaneo automático activado para ${library.name}.` : `Escaneo automático pausado para ${library.name}.`);
            await loadLibraries();
          }
        } catch (error) {
          setLibraryFeedback(libraryErrorMessage(error.message), "error");
          renderLibraries();
        } finally {
          button.disabled = false;
        }
      }

      export async function queueLibraryRun(library, mode) {
        const firstApply = mode === "apply" && !library.last_scan_at;
        setLibraryFeedback(
          mode === "dry_run"
            ? `Preparando una prueba de solo lectura para ${library.name}…`
            : firstApply
              ? `Aplicando el primer inventario de ${library.name}…`
              : `Actualizando el inventario de ${library.name}…`
        );
        const response = await apiFetch(`/api/libraries/${encodeURIComponent(library.id)}/runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        activeLibraryRunId = payload.run?.id || "";
        selectedLibraryId = library.id;
        await loadLibraryDetail(library.id);
        scheduleLibraryRunPoll(library.id);
      }

      export function scheduleLibraryRunPoll(libraryId) {
        clearTimeout(libraryRunPollTimer);
        if (!activeLibraryRunId) return;
        libraryRunPollTimer = setTimeout(() => pollLibraryRun(libraryId), 1200);
      }

      export async function pollLibraryRun(libraryId) {
        try {
          const response = await apiFetch(`/api/library-runs/${encodeURIComponent(activeLibraryRunId)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const run = payload.run || {};
          if (["queued", "running"].includes(run.status)) {
            scheduleLibraryRunPoll(libraryId);
            return;
          }
          activeLibraryRunId = "";
          await Promise.all([loadLibraries(), loadScannerQueue(), loadCatalog()]);
          const message = run.status === "completed"
            ? run.mode === "dry_run"
              ? "Prueba completada. El inventario no cambió."
              : "Inventario y disponibilidad actualizados."
            : run.status === "blocked"
              ? "No se aplicaron bajas: se conservó el último inventario válido."
              : run.mode === "dry_run"
                ? "La prueba terminó con advertencias y no modificó el inventario."
                : "El recorrido aplicado terminó con advertencias.";
          setLibraryFeedback(message, run.status === "completed" ? "" : "error");
        } catch (error) {
          activeLibraryRunId = "";
          setLibraryFeedback(libraryErrorMessage(error.message), "error");
        }
      }

      export function renderLibraryExclusionRuleRows(patterns) {
        fields.libraryExclusionRuleRows.innerHTML = patterns.length
          ? patterns.map((pattern) => libraryExclusionRuleRow(pattern)).join("")
          : libraryExclusionRuleRow("");
        setInlineFeedback(fields.libraryExclusionRulesFeedback, "");
      }

      function libraryExclusionRuleRow(pattern) {
        return `<div class="library-exclusion-rule-row">
          <input type="text" class="library-exclusion-rule-input" value="${escapeAttr(pattern)}" placeholder="bonus*" maxlength="255">
          <button type="button" class="quiet-action" data-exclusion-remove>Quitar</button>
        </div>`;
      }

      export function addLibraryExclusionRuleRow() {
        fields.libraryExclusionRuleRows.insertAdjacentHTML("beforeend", libraryExclusionRuleRow(""));
        const inputs = fields.libraryExclusionRuleRows.querySelectorAll(".library-exclusion-rule-input");
        inputs[inputs.length - 1]?.focus();
      }

      export function handleLibraryExclusionRuleRowClick(event) {
        const button = event.target.closest("[data-exclusion-remove]");
        if (!button) return;
        const row = button.closest(".library-exclusion-rule-row");
        row?.remove();
        if (!fields.libraryExclusionRuleRows.children.length) {
          fields.libraryExclusionRuleRows.insertAdjacentHTML("beforeend", libraryExclusionRuleRow(""));
        }
      }

      function collectLibraryExclusionPatterns() {
        return [...fields.libraryExclusionRuleRows.querySelectorAll(".library-exclusion-rule-input")]
          .map((input) => input.value.trim())
          .filter(Boolean);
      }

      export function libraryExclusionRulesErrorMessage(payload) {
        const errors = Array.isArray(payload?.errors) ? payload.errors : [];
        if (!errors.length) return libraryErrorMessage(payload?.reason);
        const reasons = {
          empty: "no puede estar vacío",
          too_long: "es demasiado largo",
          has_path_separator: "no puede tener \"/\" ni \"\\\\\"",
          excludes_everything: "excluiría toda la biblioteca",
          too_many_rules: "hay demasiadas reglas"
        };
        return errors.map((error) => `"${error.pattern}": ${reasons[error.reason] || "no es válido"}`).join(" · ");
      }

      export function openLibraryDialog(library = null) {
        editingLibraryId = library?.id || "";
        browsedLibraryPath = "";
        parentLibraryPath = "";
        fields.libraryForm.reset();
        renderLibraryExclusionRuleRows(library?.exclusion_patterns || []);
        fields.libraryDialogTitle.textContent = library ? "Editar biblioteca" : "Agregar biblioteca";
        fields.libraryName.value = library?.name || "";
        fields.libraryRootPath.value = library?.root_path || "";
        fields.libraryRootPath.disabled = Boolean(library);
        fields.browseLibraryPath.disabled = Boolean(library);
        fields.checkLibraryPath.disabled = Boolean(library);
        fields.libraryPathBrowser.hidden = true;
        fields.libraryPathDirectories.innerHTML = "";
        setLibraryPathFeedback("");
        fields.librarySchedule.value = library?.schedule || "manual";
        fields.libraryMissingRatio.value = Math.round(Number(library?.max_missing_ratio ?? 0.5) * 100);
        fields.libraryRootHint.textContent = library
          ? "Para cambiar la ruta, quitá el seguimiento y registrala nuevamente."
          : `Raíces habilitadas: ${scannerAllowedRoots.join(" · ")}`;
        setInlineFeedback(fields.libraryDialogFeedback, "");
        fields.libraryDialog.showModal();
        fields.libraryName.focus();
      }

      export function closeLibraryDialog() {
        fields.libraryDialog.close();
        fields.libraryForm.reset();
        fields.libraryRootPath.disabled = false;
        fields.browseLibraryPath.disabled = false;
        fields.checkLibraryPath.disabled = false;
        fields.libraryPathBrowser.hidden = true;
        fields.libraryPathDirectories.innerHTML = "";
        browsedLibraryPath = "";
        parentLibraryPath = "";
        editingLibraryId = "";
        setLibraryPathFeedback("");
        setInlineFeedback(fields.libraryDialogFeedback, "");
      }

      export async function browseManagedLibraryPath(path = "") {
        fields.browseLibraryPath.disabled = true;
        fields.libraryPathBrowser.hidden = false;
        fields.libraryPathDirectories.innerHTML = `<div class="library-path-empty">Leyendo carpetas permitidas…</div>`;
        setLibraryPathFeedback("");
        try {
          const response = await apiFetch(`/api/library-paths?path=${encodeURIComponent(String(path || "").trim())}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          browsedLibraryPath = payload.path || "";
          parentLibraryPath = payload.parent || "";
          fields.libraryPathBrowserTitle.textContent = browsedLibraryPath ? "Carpetas disponibles" : "Raíces permitidas";
          fields.libraryPathBrowserCurrent.textContent = browsedLibraryPath || "Elegí un disco o volumen configurado";
          fields.libraryPathParent.hidden = !parentLibraryPath;
          fields.useLibraryPath.hidden = !browsedLibraryPath;
          const directories = payload.directories || [];
          fields.libraryPathDirectories.innerHTML = directories.length
            ? directories.map((directory) => `<button class="library-path-directory" type="button" data-library-path="${escapeAttr(directory.path || "")}" ${directory.readable === false ? "disabled" : ""}>
                <span aria-hidden="true">▸</span>
                <strong>${escapeHtml(directory.name || directory.path || "Carpeta")}</strong>
                <small>${directory.readable === false ? "No disponible" : escapeHtml(directory.path || "")}</small>
              </button>`).join("")
            : `<div class="library-path-empty">Esta carpeta no contiene otras carpetas visibles. Podés usarla tal como está.</div>`;
        } catch (error) {
          browsedLibraryPath = "";
          parentLibraryPath = "";
          fields.libraryPathParent.hidden = true;
          fields.useLibraryPath.hidden = true;
          fields.libraryPathDirectories.innerHTML = `<div class="library-path-empty is-error">${escapeHtml(libraryErrorMessage(error.message))}</div>`;
        } finally {
          fields.browseLibraryPath.disabled = false;
        }
      }

      export function handleLibraryPathDirectory(event) {
        const button = event.target.closest("[data-library-path]");
        if (!button || button.disabled) return;
        browseManagedLibraryPath(button.dataset.libraryPath || "");
      }

      export function useBrowsedLibraryPath() {
        if (!browsedLibraryPath) return;
        fields.libraryRootPath.value = browsedLibraryPath;
        setLibraryPathFeedback("Ruta seleccionada. Comprobala antes de guardar.");
        fields.libraryRootPath.focus();
      }

      export async function checkManagedLibraryPath() {
        const path = fields.libraryRootPath.value.trim();
        if (!path) {
          setLibraryPathFeedback("Elegí o escribí una ruta antes de comprobarla.", "error");
          fields.libraryRootPath.focus();
          return;
        }
        fields.checkLibraryPath.disabled = true;
        setLibraryPathFeedback("Comprobando acceso de lectura…");
        try {
          const response = await apiFetch("/api/library-paths/check", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          fields.libraryRootPath.value = payload.path || path;
          setLibraryPathFeedback(`Ruta disponible. Se encontraron ${payload.directory_count || 0} carpetas dentro.`, "success");
        } catch (error) {
          setLibraryPathFeedback(libraryErrorMessage(error.message), "error");
        } finally {
          fields.checkLibraryPath.disabled = false;
        }
      }

      export function setLibraryPathFeedback(message, state = "") {
        fields.libraryPathFeedback.textContent = message;
        fields.libraryPathFeedback.dataset.state = state;
      }

      async function saveLibraryExclusionRules(libraryId) {
        const patterns = collectLibraryExclusionPatterns();
        try {
          const response = await apiFetch(`/api/libraries/${encodeURIComponent(libraryId)}/exclusion-rules`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patterns })
          });
          const payload = await response.json();
          if (!response.ok) {
            setInlineFeedback(fields.libraryExclusionRulesFeedback, libraryExclusionRulesErrorMessage(payload), "error");
            return false;
          }
          setInlineFeedback(fields.libraryExclusionRulesFeedback, "");
          return true;
        } catch (error) {
          setInlineFeedback(fields.libraryExclusionRulesFeedback, libraryErrorMessage(error.message), "error");
          return false;
        }
      }

      export async function saveManagedLibrary(event) {
        event.preventDefault();
        fields.submitLibrary.disabled = true;
        setInlineFeedback(fields.libraryDialogFeedback, "Guardando…");
        const body = {
          name: fields.libraryName.value,
          schedule: fields.librarySchedule.value,
          max_missing_ratio: Number(fields.libraryMissingRatio.value || 50) / 100
        };
        if (!editingLibraryId) body.root_path = fields.libraryRootPath.value;
        const endpoint = editingLibraryId
          ? `/api/libraries/${encodeURIComponent(editingLibraryId)}/update`
          : "/api/libraries";
        try {
          const response = await apiFetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const name = payload.library?.name || body.name;
          const libraryId = payload.library?.id || editingLibraryId;
          selectedLibraryId = libraryId;
          if (!(await saveLibraryExclusionRules(libraryId))) return;
          closeLibraryDialog();
          setLibraryFeedback(`${name} quedó guardada. ${payload.reason === "library_created" ? "Ejecutá ahora el recorrido de prueba." : ""}`.trim());
          await loadLibraries();
        } catch (error) {
          setInlineFeedback(fields.libraryDialogFeedback, libraryErrorMessage(error.message), "error");
        } finally {
          fields.submitLibrary.disabled = false;
        }
      }

      export async function deleteManagedLibrary(library) {
        try {
          const response = await apiFetch(`/api/libraries/${encodeURIComponent(library.id)}/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confirmed: true })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedLibraryId = "";
          setLibraryFeedback(`${library.name} dejó de estar bajo seguimiento.`);
          await Promise.all([loadLibraries(), loadCatalog()]);
        } catch (error) {
          setLibraryFeedback(libraryErrorMessage(error.message), "error");
        }
      }

      export function setLibraryFeedback(message, tone = "") {
        setInlineFeedback(fields.libraryFeedback, message, tone);
      }

      export function libraryErrorMessage(reason) {
        const value = String(reason || "");
        if (value === "library_scan_busy") return "Ya hay un recorrido en curso para esta biblioteca.";
        if (value === "library_not_found") return "La biblioteca ya no está disponible.";
        if (value.includes("allowlist") || value.includes("allowed roots")) return "La ruta está fuera de las raíces habilitadas en el servidor.";
        if (value.includes("offline") || value.includes("directory")) return "La ruta no está montada o no es un directorio accesible.";
        if (value.includes("Manual libraries")) return "Las bibliotecas manuales no usan automatización. Cambiá la frecuencia para programar recorridos.";
        if (value.includes("Apply inventory")) return "Primero aplicá un inventario antes de activar recorridos automáticos.";
        if (value.includes("test scan")) return "Primero ejecutá un recorrido de prueba satisfactorio.";
        if (value.includes("already uses")) return "Esa ruta ya está registrada en otra biblioteca.";
        if (value === "library_store_unavailable") return "El inventario no está disponible. Reintentá en unos segundos.";
        if (value === "possible_duplicate") return "Encontramos obras parecidas en tu catálogo. Revisá primero las coincidencias para evitar un duplicado.";
        if (value.includes("recognizable identity") || value.includes("recognizable title")) return "El título detectado no alcanza para identificar la obra. Corregilo y volvé a intentar.";
        if (value.includes("Confirm the year")) return "Confirmá el año antes de crear la obra.";
        if (value.includes("valid four-digit year")) return "Ingresá un año válido de cuatro cifras.";
        if (value === "catalog_item_unavailable") return "La obra se guardó de forma incompleta. Actualizá la Bandeja antes de reintentar.";
        if (value === "catalog_item_not_found") return "La ficha ya no está en tu catálogo. Actualizá la Bandeja y volvé a comparar.";
        if (value.includes("not a scanner candidate")) return "Esa ficha ya no coincide con el archivo. Actualizá la Bandeja y revisá las candidatas.";
        return value && !value.startsWith("HTTP") ? value : "No pudimos completar la operación de biblioteca.";
      }

      export function libraryStatusLabel(value) {
        return { unverified: "Sin comprobar", ready: "Lista", scanning: "Escaneando", paused: "Pausada", offline: "Desconectada", warning: "Con advertencias", error: "Error" }[value] || "Sin comprobar";
      }

      export function scheduleLabel(value) {
        return { manual: "Manual", hourly: "Cada hora", daily: "Diaria" }[value] || "Manual";
      }

      export function runStatusLabel(value) {
        return { queued: "En cola", running: "En curso", completed: "Completado", partial: "Parcial", blocked: "Bloqueado", failed: "Falló" }[value] || "Sin estado";
      }

      export function runModeLabel(run) {
        return `${run.mode === "dry_run" ? "Prueba" : "Aplicación"} · ${run.trigger === "scheduled" ? "Programada" : "Manual"}`;
      }

      export function formatLibraryTime(value) {
        const timestamp = Number(value || 0);
        if (!timestamp) return "Sin registro";
        return new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" }).format(new Date(timestamp * 1000));
      }

