import { load } from "../core/catalog-data.js";
import { fields } from "../core/fields.js";
import { escapeAttr, escapeHtml, meta, setInlineFeedback } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { currentIdentity, currentView, privacyPreferences, setPrivacyPreferences } from "../core/state.js";
import { loadLibraries } from "./admin-libraries.js";
import { loadClub } from "./club.js";
import { formatImportBytes } from "./inbox-imports.js";

      export let members = [];

      export let archivedMembers = [];

      export let membersLoading = false;

      export let editingMemberId = "";

      export let archivingMemberId = "";

      export let imageCacheStatus = null;

      export let imageCacheStatusLoading = false;

      export let imageCacheStatusTimer = null;

      export const IMAGE_CACHE_STATUS_INTERVAL_MS = 5000;

      export async function loadMembers({ announce = false } = {}) {
        if (membersLoading || currentIdentity?.user?.role !== "owner") return;
        membersLoading = true;
        fields.memberList.setAttribute("aria-busy", "true");
        fields.createMemberButton.disabled = true;
        if (announce) setMemberFeedback("Actualizando miembros\u2026");
        try {
          const response = await apiFetch("/api/members");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          members = payload.members || [];
          archivedMembers = payload.archived || [];
          renderMembers();
          if (announce) setMemberFeedback("Miembros actualizados.");
        } catch (error) {
          setMemberFeedback(memberErrorMessage(error.message), "error");
        } finally {
          membersLoading = false;
          fields.memberList.removeAttribute("aria-busy");
          fields.createMemberButton.disabled = false;
        }
      }

      export function renderMembers() {
        const activeCount = members.filter((member) => member.active).length;
        fields.memberCount.textContent = `${members.length} ${members.length === 1 ? "miembro" : "miembros"} · ${activeCount} activos`;
        if (!members.length) {
          fields.memberList.innerHTML = `
            <div class="member-list-empty">
              <strong>Todav\u00eda no hay miembros</strong>
              <span>El owner es la \u00fanica cuenta de esta instancia.</span>
            </div>`;
        } else {
          fields.memberList.innerHTML = members.map((member) => {
          const username = member.username || "Miembro";
          const initials = username.slice(0, 2).toUpperCase();
          const status = member.active ? "Activo" : "Desactivado";
          const passwordState = member.must_change_password
            ? '<span class="member-state member-state-attention">Cambio pendiente</span>'
            : '<span class="member-state">Acceso confirmado</span>';
          return `
            <div class="member-row" data-member-id="${escapeAttr(member.id || "")}" data-active="${member.active ? "true" : "false"}">
              <div class="member-row-identity">
                <span class="member-avatar" aria-hidden="true">${escapeHtml(initials)}</span>
                <div>
                  <strong>${escapeHtml(username)}</strong>
                  <span>${escapeHtml(member.catalog?.name || "Cat\u00e1logo personal")}</span>
                </div>
              </div>
              <div class="member-row-status">
                <span class="member-state ${member.active ? "member-state-active" : "member-state-disabled"}">${status}</span>
                ${passwordState}
              </div>
              <div class="member-row-actions">
                <button class="quiet-action" type="button" data-member-action="edit" data-member-id="${escapeAttr(member.id || "")}">Editar</button>
                <button class="quiet-action" type="button" data-member-action="reset-password" data-member-id="${escapeAttr(member.id || "")}">Restablecer acceso</button>
                <button class="quiet-action ${member.active ? "member-deactivate" : "member-activate"}" type="button" data-member-action="toggle-active" data-member-id="${escapeAttr(member.id || "")}">${member.active ? "Desactivar" : "Reactivar"}</button>
                ${member.active ? "" : `<button class="quiet-action member-archive" type="button" data-member-action="archive" data-member-id="${escapeAttr(member.id || "")}">Archivar</button>`}
              </div>
            </div>`;
          }).join("");
        }
        renderArchivedMembers();
      }

      export function renderArchivedMembers() {
        fields.archivedMemberSection.hidden = !archivedMembers.length;
        fields.archivedMemberCount.textContent = `${archivedMembers.length} ${archivedMembers.length === 1 ? "archivo" : "archivos"}`;
        fields.archivedMemberList.innerHTML = archivedMembers.map((member) => {
          const username = member.username || "Miembro archivado";
          return `
            <div class="member-row archived-member-row" data-archive-id="${escapeAttr(member.id || "")}">
              <div class="member-row-identity">
                <span class="member-avatar archived-avatar" aria-hidden="true">${escapeHtml(username.slice(0, 2).toUpperCase())}</span>
                <div><strong>${escapeHtml(username)}</strong><span>${escapeHtml(member.catalog?.name || "Catálogo preservado")}</span></div>
              </div>
              <div class="member-row-status">
                <span class="member-state member-state-disabled">Archivado</span>
                <span class="member-state ${member.catalog_available ? "" : "member-state-attention"}">${member.catalog_available ? "Catálogo disponible" : "Archivo no disponible"}</span>
              </div>
              <div class="member-row-actions">
                <button class="quiet-action member-activate" type="button" data-archive-action="restore" data-archive-id="${escapeAttr(member.id || "")}" ${member.catalog_available ? "" : "disabled"}>Restaurar</button>
              </div>
            </div>`;
        }).join("");
      }

      export function openMemberDialog() {
        fields.memberForm.reset();
        fields.memberTemporaryPassword.type = "password";
        setMemberDialogFeedback("");
        fields.memberDialog.showModal();
        fields.memberUsername.focus();
      }

      export function closeMemberDialog() {
        fields.memberDialog.close();
        fields.memberForm.reset();
        setMemberDialogFeedback("");
      }

      export async function createMember(event) {
        event.preventDefault();
        const requestedUsername = fields.memberUsername.value;
        fields.submitMember.disabled = true;
        fields.submitMember.setAttribute("aria-busy", "true");
        fields.submitMember.textContent = "Creando\u2026";
        setMemberDialogFeedback("");
        try {
          const response = await apiFetch("/api/members", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: fields.memberUsername.value,
              catalog_name: fields.memberCatalogName.value,
              temporary_password: fields.memberTemporaryPassword.value
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            setMemberDialogFeedback(memberErrorMessage(payload.reason), "error");
            return;
          }
          closeMemberDialog();
          showTemporaryPassword(payload.member?.username || requestedUsername, payload.temporary_password);
          await loadMembers();
        } catch (error) {
          setMemberDialogFeedback(memberErrorMessage(error.message), "error");
        } finally {
          fields.submitMember.disabled = false;
          fields.submitMember.removeAttribute("aria-busy");
          fields.submitMember.textContent = "Crear cuenta y cat\u00e1logo";
        }
      }

      export async function handleMemberAction(event) {
        const button = event.target.closest("[data-member-action]");
        if (!button) return;
        const member = members.find((entry) => entry.id === button.dataset.memberId);
        if (!member) return;
        const action = button.dataset.memberAction;
        if (action === "edit") {
          openEditMemberDialog(member);
          return;
        }
        if (action === "archive") {
          openArchiveMemberDialog(member);
          return;
        }
        if (action === "toggle-active" && member.active) {
          const confirmed = confirm(`\u00bfDesactivar a "${member.username}"? Sus sesiones abiertas se cerrar\u00e1n.`);
          if (!confirmed) return;
        }
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        try {
          const endpoint = action === "reset-password"
            ? `/api/members/${encodeURIComponent(member.id)}/password-reset`
            : `/api/members/${encodeURIComponent(member.id)}/status`;
          const body = action === "reset-password" ? {} : { active: !member.active };
          const response = await apiFetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          if (action === "reset-password") {
            showTemporaryPassword(member.username, payload.temporary_password);
          } else {
            setMemberFeedback(payload.member?.active ? `${member.username} fue reactivado.` : `${member.username} fue desactivado.`);
          }
          await loadMembers();
        } catch (error) {
          setMemberFeedback(memberErrorMessage(error.message), "error");
        } finally {
          button.disabled = false;
          button.removeAttribute("aria-busy");
        }
      }

      export function openEditMemberDialog(member) {
        editingMemberId = member.id;
        fields.editMemberUsername.value = member.username || "";
        fields.editMemberCatalogName.value = member.catalog?.name || "";
        setInlineFeedback(fields.editMemberFeedback, "");
        fields.editMemberDialog.showModal();
        fields.editMemberUsername.focus();
      }

      export function closeEditMemberDialog() {
        fields.editMemberDialog.close();
        editingMemberId = "";
        fields.editMemberForm.reset();
        setInlineFeedback(fields.editMemberFeedback, "");
      }

      export async function saveMemberProfile(event) {
        event.preventDefault();
        if (!editingMemberId) return;
        fields.saveMemberProfile.disabled = true;
        try {
          const response = await apiFetch(`/api/members/${encodeURIComponent(editingMemberId)}/profile`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: fields.editMemberUsername.value,
              catalog_name: fields.editMemberCatalogName.value
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const username = payload.member?.username || fields.editMemberUsername.value;
          closeEditMemberDialog();
          setMemberFeedback(`${username} fue actualizado.`);
          await loadMembers();
        } catch (error) {
          setInlineFeedback(fields.editMemberFeedback, memberErrorMessage(error.message), "error");
        } finally {
          fields.saveMemberProfile.disabled = false;
        }
      }

      export function openArchiveMemberDialog(member) {
        archivingMemberId = member.id;
        fields.archiveMemberUsernameLabel.textContent = member.username || "";
        fields.archiveMemberConfirmation.value = "";
        setInlineFeedback(fields.archiveMemberFeedback, "");
        fields.archiveMemberDialog.showModal();
        fields.archiveMemberConfirmation.focus();
      }

      export function closeArchiveMemberDialog() {
        fields.archiveMemberDialog.close();
        archivingMemberId = "";
        fields.archiveMemberForm.reset();
        setInlineFeedback(fields.archiveMemberFeedback, "");
      }

      export async function archiveMemberAccount(event) {
        event.preventDefault();
        if (!archivingMemberId) return;
        fields.confirmArchiveMember.disabled = true;
        try {
          const response = await apiFetch(`/api/members/${encodeURIComponent(archivingMemberId)}/archive`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confirmed_username: fields.archiveMemberConfirmation.value })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const username = payload.archived?.username || "La cuenta";
          closeArchiveMemberDialog();
          setMemberFeedback(`${username} fue archivado y su catálogo quedó preservado.`);
          await loadMembers();
        } catch (error) {
          setInlineFeedback(fields.archiveMemberFeedback, memberErrorMessage(error.message), "error");
        } finally {
          fields.confirmArchiveMember.disabled = false;
        }
      }

      export async function handleArchivedMemberAction(event) {
        const button = event.target.closest("[data-archive-action]");
        if (!button || button.dataset.archiveAction !== "restore") return;
        const archived = archivedMembers.find((entry) => entry.id === button.dataset.archiveId);
        if (!archived) return;
        button.disabled = true;
        try {
          const response = await apiFetch(`/api/member-archives/${encodeURIComponent(archived.id)}/restore`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}"
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          showTemporaryPassword(payload.member?.username || archived.username, payload.temporary_password);
          setMemberFeedback(`${payload.member?.username || archived.username} fue restaurado.`);
          await loadMembers();
        } catch (error) {
          setMemberFeedback(memberErrorMessage(error.message), "error");
        } finally {
          button.disabled = false;
        }
      }

      export function showTemporaryPassword(username, password) {
        fields.temporaryPasswordUsername.textContent = username;
        fields.temporaryPasswordValue.value = password || "";
        fields.temporaryPasswordFeedback.hidden = true;
        fields.temporaryPasswordDialog.showModal();
        fields.copyTemporaryPassword.focus();
      }

      export function closeTemporaryPasswordDialog() {
        fields.temporaryPasswordDialog.close();
        fields.temporaryPasswordValue.value = "";
        fields.temporaryPasswordFeedback.hidden = true;
      }

      export async function copyTemporaryPassword() {
        try {
          await navigator.clipboard.writeText(fields.temporaryPasswordValue.value);
          fields.temporaryPasswordFeedback.textContent = "Contrase\u00f1a copiada.";
          fields.temporaryPasswordFeedback.hidden = false;
        } catch {
          fields.temporaryPasswordValue.select();
          fields.temporaryPasswordFeedback.textContent = "Seleccion\u00e1 el texto y copialo manualmente.";
          fields.temporaryPasswordFeedback.hidden = false;
        }
      }

      export function setMemberFeedback(message, tone = "") {
        fields.memberFeedback.textContent = message;
        fields.memberFeedback.dataset.tone = tone;
        fields.memberFeedback.hidden = !message;
      }

      export function setMemberDialogFeedback(message, tone = "") {
        fields.memberDialogFeedback.textContent = message;
        fields.memberDialogFeedback.dataset.tone = tone;
        fields.memberDialogFeedback.hidden = !message;
      }

      export function memberErrorMessage(reason) {
        if (reason === "username_unavailable") return "Ese usuario ya existe.";
        if (reason === "member_not_found") return "La cuenta ya no est\u00e1 disponible.";
        if (reason === "member_must_be_inactive") return "Desactiv\u00e1 la cuenta antes de archivarla.";
        if (reason === "archive_confirmation_mismatch") return "El nombre escrito no coincide con el usuario.";
        if (reason === "archive_not_found") return "Ese archivo ya no est\u00e1 disponible.";
        if (reason === "archived_catalog_unavailable") return "El archivo del cat\u00e1logo no est\u00e1 disponible en el servidor.";
        if (reason === "member_provisioning_failed") return "No pudimos crear el cat\u00e1logo personal.";
        if (String(reason || "").includes("at least 12")) return "La contrase\u00f1a debe tener al menos 12 caracteres.";
        if (String(reason || "").includes("Username must")) return "Us\u00e1 entre 3 y 64 letras, n\u00fameros, puntos, guiones o guiones bajos.";
        return "No pudimos actualizar la cuenta.";
      }

      export async function openPrivacyDialog() {
        fields.systemMenu.open = false;
        setInlineFeedback(fields.privacyFeedback, "");
        applyPrivacyForm(privacyPreferences);
        fields.privacyDialog.showModal();
        fields.savePrivacy.disabled = true;
        try {
          const response = await apiFetch("/api/privacy");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          setPrivacyPreferences({ ...privacyPreferences, ...(payload.preferences || {}) });
          applyPrivacyForm(privacyPreferences);
        } catch (error) {
          setInlineFeedback(fields.privacyFeedback, privacyErrorMessage(error.message), "error");
        } finally {
          fields.savePrivacy.disabled = false;
          fields.catalogShared.focus();
        }
      }

      export function closePrivacyDialog() {
        fields.privacyDialog.close();
        setInlineFeedback(fields.privacyFeedback, "");
      }

      export function applyPrivacyForm(preferences) {
        fields.catalogShared.checked = Boolean(preferences.catalog_shared);
        fields.shareStatus.checked = Boolean(preferences.share_status);
        fields.shareWatchedAt.checked = Boolean(preferences.share_watched_at);
        fields.shareHistory.checked = Boolean(preferences.share_history);
        fields.shareRating.checked = Boolean(preferences.share_rating);
        fields.shareReview.checked = Boolean(preferences.share_review);
        syncPrivacyControls();
      }

      export function syncPrivacyControls() {
        fields.privacyFields.disabled = !fields.catalogShared.checked;
        fields.privacyFields.dataset.enabled = fields.catalogShared.checked ? "true" : "false";
      }

      export async function savePrivacyPreferences(event) {
        event.preventDefault();
        fields.savePrivacy.disabled = true;
        setInlineFeedback(fields.privacyFeedback, "Guardando privacidad…");
        const next = {
          catalog_shared: fields.catalogShared.checked,
          share_status: fields.shareStatus.checked,
          share_watched_at: fields.shareWatchedAt.checked,
          share_history: fields.shareHistory.checked,
          share_rating: fields.shareRating.checked,
          share_review: fields.shareReview.checked
        };
        try {
          const response = await apiFetch("/api/privacy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(next)
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          setPrivacyPreferences({ ...next, ...(payload.preferences || {}) });
          syncPrivacySummary();
          closePrivacyDialog();
          if (currentView === "club") await loadClub();
        } catch (error) {
          setInlineFeedback(fields.privacyFeedback, privacyErrorMessage(error.message), "error");
        } finally {
          fields.savePrivacy.disabled = false;
        }
      }

      export function privacyErrorMessage(reason) {
        if (String(reason || "").includes("Invalid visibility")) return "Elegí una opción de visibilidad válida.";
        if (reason === "identity_store_unavailable") return "La configuración de cuentas no está disponible.";
        return "No pudimos guardar la privacidad. Volvé a intentar.";
      }

      export function syncPrivacySummary() {
        fields.privacyButton.textContent = privacyPreferences.catalog_shared
          ? "Privacidad · Compartiendo"
          : "Privacidad";
      }

      export async function refreshAdminData() {
        await load();
        if (currentView === "admin") {
          await Promise.all([
            loadMembers({ announce: true }),
            loadLibraries({ announce: true }),
            loadImageCacheStatus({ announce: true })
          ]);
        }
      }

      export function handleVisibilityChange() {
        syncImageCacheStatusPolling();
      }

      export async function loadImageCacheStatus({ announce = false } = {}) {
        if (
          !fields.imageCacheStatus
          || currentIdentity?.user?.role !== "owner"
          || imageCacheStatusLoading
        ) return;
        imageCacheStatusLoading = true;
        if (announce) fields.imageCacheStatus.setAttribute("aria-busy", "true");
        try {
          const response = await apiFetch("/api/image-cache/status");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          imageCacheStatus = payload;
          renderImageCacheStatus();
        } catch (error) {
          console.error("[catalog-viewer] image cache status failed", error);
          fields.imageCacheStatus.innerHTML = `
            <div class="image-cache-status-copy">
              <strong>Portadas en este cat&aacute;logo</strong>
              <span>No pudimos consultar el cach&eacute;. Volveremos a intentarlo mientras Administrar siga abierto.</span>
            </div>
            <span class="image-cache-state is-error">Sin conexi&oacute;n</span>
          `;
          fields.imageCacheStatus.dataset.state = "error";
        } finally {
          imageCacheStatusLoading = false;
          fields.imageCacheStatus.removeAttribute("aria-busy");
        }
      }

      export function renderImageCacheStatus() {
        if (!fields.imageCacheStatus || !imageCacheStatus) return;
        const personal = imageCacheStatus.personal || {};
        const cache = imageCacheStatus.cache || {};
        const global = imageCacheStatus.global || null;
        const labels = {
          inactive: ["Esperando", "Abr&iacute; un cat&aacute;logo o colecci&oacute;n para iniciar la carga gradual."],
          working: ["Cargando", "Las portadas se guardan de a una, sin bloquear la navegaci&oacute;n."],
          retrying: ["Reintentando", "Algunas fuentes est&aacute;n demoradas; el proceso continuar&aacute; en segundo plano."],
          complete: ["Al d&iacute;a", "Las portadas disponibles de este cat&aacute;logo ya est&aacute;n guardadas."],
          error: ["Con pendientes", "Algunas portadas agotaron sus reintentos o fueron bloqueadas por seguridad."],
          limit_reached: ["L&iacute;mite alcanzado", "El cach&eacute; aplicar&aacute; su limpieza por uso antes de incorporar nuevas portadas."],
          disabled: ["Deshabilitado", "La carga progresiva est&aacute; desactivada en la configuraci&oacute;n del servidor."],
          idle: ["En espera", "Hay portadas pendientes y el worker continuar&aacute; cuando pueda."]
        };
        let [stateLabel, stateCopy] = labels[personal.state] || labels.idle;
        if (imageCacheStatus.worker?.cache_error) {
          stateLabel = "No disponible";
          stateCopy = "El servidor no puede leer el directorio persistente de portadas.";
        }
        const cacheLimit = Number(cache.max_bytes || 0);
        const cacheUsage = cacheLimit
          ? `${formatImportBytes(cache.total_bytes)} de ${formatImportBytes(cacheLimit)}`
          : formatImportBytes(cache.total_bytes);
        const aggregate = global
          ? `<span>${escapeHtml(String(global.available || 0))} recursos disponibles en ${escapeHtml(String(global.registered_scopes || 0))} espacios abiertos</span>`
          : "";
        fields.imageCacheStatus.dataset.state = personal.state || "idle";
        fields.imageCacheStatus.innerHTML = `
          <div class="image-cache-status-copy">
            <strong>Portadas en este cat&aacute;logo</strong>
            <span>${stateCopy}</span>
          </div>
          <div class="image-cache-status-metrics" aria-label="Estado de portadas">
            <span><strong>${escapeHtml(String(personal.available || 0))}</strong> disponibles</span>
            <span><strong>${escapeHtml(String(personal.pending || 0))}</strong> pendientes</span>
            <span><strong>${escapeHtml(String(personal.without_url || 0))}</strong> sin imagen</span>
            ${personal.failed ? `<span><strong>${escapeHtml(String(personal.failed))}</strong> con error</span>` : ""}
            ${personal.rejected ? `<span><strong>${escapeHtml(String(personal.rejected))}</strong> bloqueadas</span>` : ""}
          </div>
          <div class="image-cache-status-meta">
            <span>${escapeHtml(String(cache.files || 0))} archivos &middot; ${escapeHtml(cacheUsage)}</span>
            ${aggregate}
          </div>
          <span class="image-cache-state is-${escapeAttr(personal.state || "idle")}">${stateLabel}</span>
        `;
        fields.imageCacheStatus.removeAttribute("aria-busy");
      }

      export function syncImageCacheStatusPolling() {
        window.clearInterval(imageCacheStatusTimer);
        imageCacheStatusTimer = null;
        if (currentView !== "admin" || currentIdentity?.user?.role !== "owner" || document.hidden) return;
        if (!imageCacheStatus) loadImageCacheStatus();
        imageCacheStatusTimer = window.setInterval(loadImageCacheStatus, IMAGE_CACHE_STATUS_INTERVAL_MS);
      }

