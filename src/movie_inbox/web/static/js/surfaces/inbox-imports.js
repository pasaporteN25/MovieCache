import { load, loadCatalog } from "../core/catalog-data.js";
import { fields } from "../core/fields.js";
import { escapeAttr, escapeHtml, meta } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { goToClub } from "../core/router.js";
import { currentIdentity, setClubMode } from "../core/state.js";
import { openCollection, setSelectedCollectionId } from "./club.js";

      export let importDrafts = [];

      export let selectedImportDraft = null;

      export let selectedImportItems = new Set();

      export let importFilter = "all";

      export let importDestination = "catalog";

      export let importInputMode = "file";

      export let importLoading = false;

      export let importVisibleCount = 200;

      export const IMPORT_MAX_BYTES = 8 * 1024 * 1024;

      export const IMPORT_PREVIEW_PAGE_SIZE = 200;

      export const IMPORT_COLUMN_FIELDS = [
        ["title", "Título"],
        ["url", "URL"],
        ["year", "Año"],
        ["kind", "Tipo"],
        ["status", "Estado"],
        ["watched_at", "Fecha de vista"],
        ["rating", "Puntaje"],
        ["review", "Review"],
        ["en_catalogo", "Disponibilidad declarada"]
      ];

      export async function loadImportDrafts({ selectId = "", announce = false, refreshSelected = true } = {}) {
        if (importLoading) return;
        importLoading = true;
        fields.importInboxPanel.setAttribute("aria-busy", "true");
        if (announce) setImportFeedback(fields.importSourceFeedback, "Actualizando borradores…", "working");
        let targetId = String(selectId || (refreshSelected ? selectedImportDraft?.id : "") || "");
        try {
          const response = await apiFetch("/api/imports");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          importDrafts = payload.drafts || [];
          fields.importDraftCount.textContent = String(importDrafts.length);
          if (targetId && !importDrafts.some((draft) => draft.id === targetId)) targetId = "";
          if (!targetId && selectedImportDraft && !importDrafts.some((draft) => draft.id === selectedImportDraft.id)) {
            selectedImportDraft = null;
            selectedImportItems.clear();
            showImportSourcePanel({ reset: false });
          }
          renderImportDraftList();
          if (announce) setImportFeedback(fields.importSourceFeedback, "Borradores actualizados.", "success");
        } catch (error) {
          console.error("[movie-inbox] import drafts load failed", error);
          importDrafts = [];
          fields.importDraftCount.textContent = "!";
          fields.importDraftList.innerHTML = `<div class="import-draft-empty"><strong>Borradores no disponibles</strong><p>Actualizá la Bandeja para volver a intentar.</p></div>`;
          setImportFeedback(fields.importSourceFeedback, importErrorMessage(error.message), "error");
          targetId = "";
        } finally {
          importLoading = false;
          fields.importInboxPanel.setAttribute("aria-busy", "false");
        }
        if (targetId) await selectImportDraft(targetId);
      }

      export function renderImportDraftList() {
        if (!importDrafts.length) {
          fields.importDraftList.innerHTML = `<div class="import-draft-empty"><strong>Sin borradores</strong><p>Elegí un archivo o pegá contenido para preparar el primer ingreso.</p></div>`;
          return;
        }
        fields.importDraftList.innerHTML = importDrafts.map((draft) => {
          const counts = draft.counts || {};
          const selected = draft.id === selectedImportDraft?.id;
          const applied = draft.status === "applied";
          const stateLabel = applied
            ? "Aplicado"
            : draft.status === "applying"
              ? "Aplicando"
              : draft.status === "failed"
                ? "Reintentar"
                : formatImportExpiry(draft.expires_at);
          return `<button class="import-draft-item${selected ? " selected" : ""}" type="button"
            data-import-draft="${escapeAttr(draft.id || "")}" aria-pressed="${selected}">
            <strong>${escapeHtml(draft.source?.name || "Importación")}</strong>
            <span class="import-draft-item-meta">
              <span>${escapeHtml(String(draft.source?.format || "").toUpperCase())}</span>
              <span>${Number(counts.total || 0)} filas</span>
              <span>${stateLabel}</span>
            </span>
            <span class="import-draft-item-states">
              <span class="new">${Number(counts.new || 0)} nuevas</span>
              ${Number(counts.review || 0) ? `<span class="review">${Number(counts.review)} revisar</span>` : ""}
              ${Number(counts.invalid || 0) ? `<span class="invalid">${Number(counts.invalid)} inválidas</span>` : ""}
            </span>
          </button>`;
        }).join("");
      }

      export function showImportSourcePanel({ reset = true, focus = false } = {}) {
        selectedImportDraft = null;
        selectedImportItems.clear();
        fields.importSourcePanel.hidden = false;
        fields.importReviewPanel.hidden = true;
        if (reset) resetImportSourceForm();
        renderImportDraftList();
        if (focus) fields.importFile.focus({ preventScroll: true });
      }

      export function resetImportSourceForm() {
        fields.importSourceForm.reset();
        fields.importSourceName.value = "contenido-pegado";
        fields.importFileMeta.textContent = "Ningún archivo seleccionado";
        setImportInputMode("file");
        renderImportCsvFields([]);
        setImportFeedback(fields.importSourceFeedback, "");
      }

      export async function selectImportDraft(draftId) {
        const id = String(draftId || "");
        if (!id) return;
        fields.importInboxPanel.setAttribute("aria-busy", "true");
        try {
          const response = await apiFetch(`/api/imports/${encodeURIComponent(id)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedImportDraft = payload;
          importFilter = "all";
          importVisibleCount = IMPORT_PREVIEW_PAGE_SIZE;
          importDestination = "catalog";
          selectedImportItems = new Set(
            (payload.items || []).filter((entry) => entry.catalog_eligible).map((entry) => entry.id)
          );
          fields.importSourcePanel.hidden = true;
          fields.importReviewPanel.hidden = false;
          renderImportDraftList();
          renderImportReview();
        } catch (error) {
          console.error("[movie-inbox] import draft detail failed", error);
          if (error.message === "import_draft_expired" || error.message === "import_draft_not_found") {
            selectedImportDraft = null;
            showImportSourcePanel({ reset: false });
            await loadImportDrafts({ refreshSelected: false });
          }
          setImportFeedback(fields.importSourceFeedback, importErrorMessage(error.message), "error");
        } finally {
          fields.importInboxPanel.setAttribute("aria-busy", "false");
        }
      }

      export function renderImportReview() {
        const draft = selectedImportDraft;
        if (!draft) return;
        const counts = draft.counts || {};
        fields.importReviewKicker.textContent = {
          applied: "Importación aplicada",
          applying: "Aplicación en curso",
          failed: "Reintento disponible"
        }[draft.status] || "Borrador listo";
        fields.importReviewTitle.textContent = draft.source?.name || "Previsualización";
        fields.importReviewMeta.textContent = `${String(draft.source?.format || "").toUpperCase()} · ${Number(counts.total || 0)} filas · ${formatImportExpiry(draft.expires_at)}`;
        fields.deleteImportDraft.disabled = draft.status === "applying";
        fields.importMetrics.innerHTML = [
          ["total", "Total"],
          ["new", "Nuevas"],
          ["present", "Presentes"],
          ["review", "Revisar"],
          ["invalid", "Inválidas"]
        ].map(([state, label]) => `<div class="import-metric" data-state="${state}"><strong>${Number(counts[state] || 0)}</strong><span>${label}</span></div>`).join("");
        fields.importStateFilters.querySelectorAll("[data-import-filter]").forEach((button) => {
          const active = button.dataset.importFilter === importFilter;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        renderImportDestination();
        renderImportPreviewRows();
        renderImportResult();
      }

      export function renderImportDestination() {
        const owner = currentIdentity?.user?.role === "owner";
        fields.importCollectionDestination.hidden = !owner;
        if (!owner && importDestination === "collection") importDestination = "catalog";
        fields.importDestinationModes.querySelectorAll("[data-import-destination]").forEach((button) => {
          const active = button.dataset.importDestination === importDestination;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
          button.disabled = ["applied", "applying"].includes(selectedImportDraft?.status);
        });
        const collection = importDestination === "collection";
        fields.importPersonalOptions.hidden = collection;
        fields.importPersonalOptions.disabled = ["applied", "applying"].includes(selectedImportDraft?.status);
        fields.importCollectionOptions.hidden = !collection;
        fields.applyImport.textContent = collection ? "Crear colección privada" : "Importar selección";
        if (collection && !fields.importCollectionTitle.value.trim()) {
          fields.importCollectionTitle.value = importCollectionTitle(selectedImportDraft?.source?.name || "Colección importada");
        }
      }

      export function renderImportPreviewRows() {
        const filtered = filteredImportItems();
        const rows = visibleImportItems();
        fields.importPreviewRows.innerHTML = rows.map((entry) => {
          const item = entry.item || {};
          const eligible = canSelectImportItem(entry) && selectedImportDraft?.status !== "applied";
          const selected = selectedImportItems.has(entry.id);
          const title = item.title || entry.label || "Entrada sin título";
          const original = item.original_title && item.original_title !== title ? item.original_title : "";
          const data = [item.year, importKindLabel(item.kind), item.source].filter(Boolean).join(" · ") || "Sin datos adicionales";
          const link = importUrlLabel(item.url || item.wikipedia_url || item.imdb_url || item.filmaffinity_url);
          const candidate = entry.candidates?.[0];
          const detail = candidate
            ? `Posible: ${candidate.title || candidate.id || "obra existente"}${candidate.year ? ` (${candidate.year})` : ""}`
            : importReasonLabel(entry.reason);
          return `<tr data-state="${escapeAttr(entry.state || "invalid")}">
            <td><input type="checkbox" data-import-item="${escapeAttr(entry.id || "")}" aria-label="Seleccionar ${escapeAttr(title)}" ${selected ? "checked" : ""} ${eligible ? "" : "disabled"}></td>
            <td><span class="import-title-cell"><strong>${escapeHtml(title)}</strong>${original ? `<small>${escapeHtml(original)}</small>` : ""}</span></td>
            <td><span class="import-data-cell">${escapeHtml(data)}${link ? `<br>${escapeHtml(link)}` : ""}</span></td>
            <td><span class="import-state-cell"><span class="import-state-badge ${escapeAttr(entry.state || "invalid")}">${escapeHtml(importStateLabel(entry.state))}</span><small>${escapeHtml(detail)}</small></span></td>
          </tr>`;
        }).join("");
        fields.importPreviewEmpty.hidden = Boolean(rows.length);
        fields.importPreviewRows.closest(".import-table-wrap").hidden = !rows.length;
        const remaining = Math.max(0, filtered.length - rows.length);
        fields.loadMoreImportRows.hidden = !remaining;
        fields.loadMoreImportRows.textContent = remaining
          ? `Cargar ${Math.min(IMPORT_PREVIEW_PAGE_SIZE, remaining)} más · ${remaining} pendientes`
          : "Cargar más";
        syncImportSelection();
      }

      export function filteredImportItems() {
        const rows = selectedImportDraft?.items || [];
        return importFilter === "all" ? rows : rows.filter((entry) => entry.state === importFilter);
      }

      export function visibleImportItems() {
        return filteredImportItems().slice(0, importVisibleCount);
      }

      export function canSelectImportItem(entry) {
        return importDestination === "collection" ? Boolean(entry.collection_eligible) : Boolean(entry.catalog_eligible);
      }

      export function changeImportSelection(event) {
        const checkbox = event.target.closest("[data-import-item]");
        if (!checkbox) return;
        const itemId = checkbox.dataset.importItem || "";
        if (checkbox.checked) selectedImportItems.add(itemId);
        else selectedImportItems.delete(itemId);
        syncImportSelection();
      }

      export function toggleVisibleImportItems() {
        const eligible = visibleImportItems().filter(canSelectImportItem).map((entry) => entry.id);
        if (fields.selectVisibleImportItems.checked) eligible.forEach((id) => selectedImportItems.add(id));
        else eligible.forEach((id) => selectedImportItems.delete(id));
        renderImportPreviewRows();
      }

      export function syncImportSelection() {
        const eligible = visibleImportItems().filter(canSelectImportItem).map((entry) => entry.id);
        const selectedVisible = eligible.filter((id) => selectedImportItems.has(id));
        fields.selectVisibleImportItems.checked = Boolean(eligible.length) && selectedVisible.length === eligible.length;
        fields.selectVisibleImportItems.indeterminate = selectedVisible.length > 0 && selectedVisible.length < eligible.length;
        fields.selectVisibleImportItems.disabled = !eligible.length || selectedImportDraft?.status === "applied";
        const count = selectedImportItems.size;
        fields.importSelectionSummary.textContent = `${count} ${count === 1 ? "seleccionada" : "seleccionadas"}`;
        fields.applyImport.disabled = !count || selectedImportDraft?.status === "applied" || selectedImportDraft?.status === "applying";
      }

      export async function handleImportClick(event) {
        const newButton = event.target.closest("#newImportDraft");
        if (newButton) {
          showImportSourcePanel({ reset: true, focus: true });
          return;
        }
        const draftButton = event.target.closest("[data-import-draft]");
        if (draftButton) {
          await selectImportDraft(draftButton.dataset.importDraft || "");
          return;
        }
        const inputButton = event.target.closest("[data-import-input]");
        if (inputButton) {
          setImportInputMode(inputButton.dataset.importInput || "file", true);
          return;
        }
        const filterButton = event.target.closest("[data-import-filter]");
        if (filterButton) {
          importFilter = filterButton.dataset.importFilter || "all";
          importVisibleCount = IMPORT_PREVIEW_PAGE_SIZE;
          renderImportReview();
          return;
        }
        if (event.target.closest("#loadMoreImportRows")) {
          importVisibleCount += IMPORT_PREVIEW_PAGE_SIZE;
          renderImportPreviewRows();
          return;
        }
        const destinationButton = event.target.closest("[data-import-destination]");
        if (destinationButton) {
          importDestination = destinationButton.dataset.importDestination === "collection" ? "collection" : "catalog";
          selectedImportItems = new Set(
            (selectedImportDraft?.items || []).filter(canSelectImportItem).map((entry) => entry.id)
          );
          renderImportDestination();
          renderImportPreviewRows();
          renderImportResult();
          return;
        }
        if (event.target.closest("#deleteImportDraft")) {
          await deleteSelectedImportDraft();
          return;
        }
        const collectionButton = event.target.closest("[data-open-import-collection]");
        if (collectionButton) await openImportedCollection(collectionButton.dataset.openImportCollection || "");
      }

      export function setImportInputMode(mode, focus = false) {
        importInputMode = mode === "paste" ? "paste" : "file";
        const paste = importInputMode === "paste";
        fields.importFileInputPanel.hidden = paste;
        fields.importPasteInputPanel.hidden = !paste;
        fields.importInputModes.querySelectorAll("[data-import-input]").forEach((button) => {
          const active = button.dataset.importInput === importInputMode;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        if (focus) (paste ? fields.importContent : fields.importFile).focus({ preventScroll: true });
        refreshImportMapping();
      }

      export async function changeImportFile() {
        const file = fields.importFile.files?.[0];
        if (!file) {
          fields.importFileMeta.textContent = "Ningún archivo seleccionado";
          return;
        }
        fields.importFileMeta.textContent = `${file.name} · ${formatImportBytes(file.size)}`;
        if (file.size > IMPORT_MAX_BYTES) {
          setImportFeedback(fields.importSourceFeedback, "El archivo supera el límite de 8 MiB.", "error");
          return;
        }
        if (fields.importFormat.value === "auto") {
          const inferred = inferImportFormat(file.name);
          if (inferred) fields.importFormat.value = inferred;
        }
        await refreshImportMapping();
      }

      export async function refreshImportMapping() {
        const format = resolvedImportFormat();
        if (format !== "csv") {
          renderImportCsvFields([]);
          return;
        }
        try {
          const content = importInputMode === "file"
            ? await readImportFile({ requireSelection: false })
            : fields.importContent.value;
          renderImportCsvFields(parseCsvHeader(content || ""));
        } catch (_error) {
          renderImportCsvFields([]);
        }
      }

      export function renderImportCsvFields(headers) {
        fields.importCsvMapping.hidden = !headers.length;
        fields.importCsvFields.innerHTML = headers.length ? IMPORT_COLUMN_FIELDS.map(([field, label]) => `
          <label><span>${label}</span><select data-import-column="${field}">
            <option value="">Detectar</option>
            ${headers.map((header) => `<option value="${escapeAttr(header)}">${escapeHtml(header)}</option>`).join("")}
          </select></label>`).join("") : "";
      }

      export async function analyzeImportSource(event) {
        event.preventDefault();
        fields.analyzeImport.disabled = true;
        setImportFeedback(fields.importSourceFeedback, "Analizando y comparando con tu catálogo…", "working");
        try {
          const content = importInputMode === "file"
            ? await readImportFile({ requireSelection: true })
            : fields.importContent.value;
          if (!String(content || "").trim()) throw new Error("import_content_empty");
          const file = fields.importFile.files?.[0];
          const sourceName = importInputMode === "file" ? file.name : fields.importSourceName.value;
          const response = await apiFetch("/api/imports", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              source_name: sourceName || "importacion",
              source_format: fields.importFormat.value || "auto",
              content,
              column_map: importColumnMap()
            })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedImportDraft = payload;
          selectedImportItems = new Set((payload.items || []).filter((entry) => entry.catalog_eligible).map((entry) => entry.id));
          importFilter = "all";
          importVisibleCount = IMPORT_PREVIEW_PAGE_SIZE;
          importDestination = "catalog";
          fields.importSourcePanel.hidden = true;
          fields.importReviewPanel.hidden = false;
          await loadImportDrafts({ selectId: payload.id });
        } catch (error) {
          console.error("[movie-inbox] import analysis failed", error);
          setImportFeedback(fields.importSourceFeedback, importErrorMessage(error.message), "error");
        } finally {
          fields.analyzeImport.disabled = false;
        }
      }

      export async function readImportFile({ requireSelection }) {
        const file = fields.importFile.files?.[0];
        if (!file) {
          if (requireSelection) throw new Error("import_file_required");
          return "";
        }
        if (file.size > IMPORT_MAX_BYTES) throw new Error("import_file_too_large");
        return file.text();
      }

      export function importColumnMap() {
        if (resolvedImportFormat() !== "csv") return {};
        return Object.fromEntries(
          [...fields.importCsvFields.querySelectorAll("[data-import-column]")]
            .map((select) => [select.dataset.importColumn, select.value])
            .filter(([, value]) => value)
        );
      }

      export async function applySelectedImport(event) {
        event.preventDefault();
        const draft = selectedImportDraft;
        if (!draft || !selectedImportItems.size) return;
        if (importDestination === "collection" && !fields.importCollectionTitle.value.trim()) {
          setImportFeedback(fields.importApplyFeedback, "Escribí un nombre para la colección.", "error");
          fields.importCollectionTitle.focus();
          return;
        }
        fields.applyImport.disabled = true;
        setImportFeedback(
          fields.importApplyFeedback,
          importDestination === "collection" ? "Creando colección privada…" : "Importando a tu catálogo…",
          "working"
        );
        try {
          const personalOptions = Object.fromEntries(
            [...fields.importPersonalOptions.querySelectorAll("[data-import-option]")]
              .map((checkbox) => [checkbox.dataset.importOption, checkbox.checked])
          );
          const response = await apiFetch(`/api/imports/${encodeURIComponent(draft.id)}/apply`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              destination: importDestination,
              item_ids: [...selectedImportItems],
              personal_options: personalOptions,
              collection_title: fields.importCollectionTitle.value,
              collection_description: fields.importCollectionDescription.value
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          if (importDestination === "catalog") await loadCatalog();
          else await loadImportDrafts({ selectId: draft.id });
          setImportResultFeedback(payload);
        } catch (error) {
          console.error("[movie-inbox] import apply failed", error);
          setImportFeedback(fields.importApplyFeedback, importErrorMessage(error.message), "error");
          syncImportSelection();
        }
      }

      export async function deleteSelectedImportDraft() {
        const draft = selectedImportDraft;
        if (!draft || !window.confirm(`¿Eliminar el borrador "${draft.source?.name || "Importación"}"? Esta acción no se puede deshacer.`)) return;
        fields.deleteImportDraft.disabled = true;
        try {
          const response = await apiFetch(`/api/imports/${encodeURIComponent(draft.id)}/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confirmed: true })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedImportDraft = null;
          selectedImportItems.clear();
          showImportSourcePanel({ reset: false });
          await loadImportDrafts({ refreshSelected: false });
          setImportFeedback(fields.importSourceFeedback, "Borrador eliminado.", "success");
        } catch (error) {
          setImportFeedback(fields.importApplyFeedback, importErrorMessage(error.message), "error");
          fields.deleteImportDraft.disabled = false;
        }
      }

      export function renderImportResult() {
        const result = selectedImportDraft?.result;
        if (selectedImportDraft?.status === "applying") {
          setImportFeedback(fields.importApplyFeedback, "La selección se está aplicando. Actualizá los borradores para comprobar el resultado.", "working");
          return;
        }
        if (selectedImportDraft?.status === "failed") {
          setImportFeedback(fields.importApplyFeedback, "La operación anterior no terminó. Revisá la selección y volvé a importar; no se duplicarán obras exactas.", "error");
          return;
        }
        if (selectedImportDraft?.status !== "applied" || !result?.ok) {
          setImportFeedback(fields.importApplyFeedback, "");
          return;
        }
        setImportResultFeedback(result);
      }

      export function setImportResultFeedback(result) {
        const summary = result.summary || {};
        if (result.destination === "collection") {
          const collection = result.collection || {};
          fields.importApplyFeedback.dataset.tone = "success";
          fields.importApplyFeedback.innerHTML = `Colección privada creada con ${Number(summary.created || 0)} obras. <button class="text-action" type="button" data-open-import-collection="${escapeAttr(collection.id || "")}">Ver colección</button>`;
          return;
        }
        const parts = [];
        if (summary.added) parts.push(`${summary.added} agregadas`);
        if (summary.present) parts.push(`${summary.present} ya presentes`);
        if (summary.review) parts.push(`${summary.review} sin importar por posible coincidencia`);
        setImportFeedback(fields.importApplyFeedback, parts.join(" · ") || "Importación completada sin cambios.", "success");
      }

      export async function openImportedCollection(collectionId) {
        if (!collectionId) return;
        setClubMode("collections");
        setSelectedCollectionId(collectionId);
        await goToClub();
        await openCollection(collectionId);
      }

      export function setImportFeedback(field, message, tone = "", html = false) {
        if (html) field.innerHTML = message;
        else field.textContent = message;
        field.dataset.tone = tone;
      }

      export function importErrorMessage(reason) {
        const value = String(reason || "");
        if (value === "import_file_required") return "Elegí un archivo TXT, CSV o JSON.";
        if (value === "import_file_too_large" || value.includes("8 MiB") || value === "request_too_large") return "El contenido supera el límite de 8 MiB.";
        if (value === "import_content_empty" || value.toLowerCase().includes("empty")) return "El origen no contiene entradas para analizar.";
        if (value === "import_draft_expired") return "El borrador expiró. Prepará una nueva importación.";
        if (value === "import_draft_busy") return "Este borrador ya se está aplicando. Actualizá la Bandeja en unos segundos.";
        if (value === "import_draft_limit_reached") return "Llegaste a 20 borradores. Eliminá uno antes de preparar otra importación.";
        if (value.includes("CSV") || value.includes("JSON") || value.includes("format")) return `No pudimos interpretar el archivo: ${value}`;
        if (value === "import_store_unavailable") return "Los borradores no están disponibles. Volvé a intentar.";
        return "No pudimos completar la importación. Revisá el formato y volvé a intentar.";
      }

      export function resolvedImportFormat() {
        const chosen = fields.importFormat.value || "auto";
        if (chosen !== "auto") return chosen;
        const name = importInputMode === "file" ? fields.importFile.files?.[0]?.name : fields.importSourceName.value;
        const inferred = inferImportFormat(name);
        if (inferred) return inferred;
        if (importInputMode === "paste") {
          const content = fields.importContent.value.trimStart();
          if (content.startsWith("{") || content.startsWith("[")) return "json";
          const firstLine = content.split(/\r?\n/, 1)[0] || "";
          if (/[,;\t|]/.test(firstLine) && parseCsvHeader(content).length >= 2) return "csv";
        }
        return "txt";
      }

      export function inferImportFormat(name) {
        const extension = String(name || "").toLowerCase().split(".").pop();
        return ["txt", "csv", "json"].includes(extension) ? extension : "";
      }

      export function parseCsvHeader(content) {
        const text = String(content || "").replace(/^\uFEFF/, "");
        if (!text.trim()) return [];
        const values = [];
        let value = "";
        let quoted = false;
        for (let index = 0; index < text.length; index += 1) {
          const character = text[index];
          if (character === '"') {
            if (quoted && text[index + 1] === '"') {
              value += '"';
              index += 1;
            } else {
              quoted = !quoted;
            }
          } else if (!quoted && (character === "," || character === ";" || character === "\t")) {
            values.push(value.trim());
            value = "";
          } else if (!quoted && (character === "\n" || character === "\r")) {
            values.push(value.trim());
            break;
          } else {
            value += character;
          }
          if (index === text.length - 1) values.push(value.trim());
          if (values.length > 100) return [];
        }
        return [...new Set(values.filter(Boolean))];
      }

      export function importCollectionTitle(sourceName) {
        return String(sourceName || "Colección importada")
          .replace(/\.(txt|csv|json)$/i, "")
          .replace(/[_-]+/g, " ")
          .replace(/\s+/g, " ")
          .trim()
          .slice(0, 120) || "Colección importada";
      }

      export function formatImportExpiry(value) {
        const remaining = new Date(value).getTime() - Date.now();
        if (!Number.isFinite(remaining) || remaining <= 0) return "Expirado";
        const hours = remaining / 3600000;
        return hours > 24 ? `${Math.ceil(hours / 24)} d restantes` : `${Math.max(1, Math.ceil(hours))} h restantes`;
      }

      export function formatImportBytes(value) {
        const bytes = Number(value || 0);
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
      }

      export function importStateLabel(state) {
        return { new: "Nueva", present: "Presente", review: "Revisar", invalid: "Inválida" }[state] || "Inválida";
      }

      export function importReasonLabel(reason) {
        return {
          new_item: "No encontramos una coincidencia en tu catálogo",
          already_in_catalog: "La misma referencia ya existe en tu catálogo",
          possible_catalog_match: "El título se parece a una obra existente",
          duplicate_in_source: "Esta fila repite otra entrada del mismo origen",
          possible_duplicate_in_source: "Podría repetir otra entrada del mismo origen",
          title_not_recognized: "No pudimos reconocer un título",
          invalid_item: "La fila no cumple el formato esperado",
          json_item_not_object: "La entrada JSON no es un objeto"
        }[reason] || String(reason || "Revisión necesaria").replace(/_/g, " ");
      }

      export function importKindLabel(value) {
        return { pelicula: "Película", serie: "Serie", anime: "Anime", documental: "Documental" }[value] || "";
      }

      export function importUrlLabel(value) {
        try {
          return value ? new URL(value).hostname.replace(/^www\./, "") : "";
        } catch (_error) {
          return "";
        }
      }

