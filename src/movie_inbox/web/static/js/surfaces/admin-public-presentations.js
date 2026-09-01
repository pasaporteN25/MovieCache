import { escapeAttr, escapeHtml, setInlineFeedback } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { currentIdentity } from "../core/state.js";
import { fields } from "../core/fields.js";

let presentations = [];
let ownCollections = [];

export async function loadPublicPresentations({ announce = false } = {}) {
  if (currentIdentity?.user?.role !== "owner") return;
  try {
    const [presentationResponse, collectionResponse] = await Promise.all([
      apiFetch("/api/public-presentations"),
      apiFetch("/api/collections")
    ]);
    const presentationPayload = await presentationResponse.json();
    const collectionPayload = await collectionResponse.json();
    if (!presentationResponse.ok) throw new Error(presentationPayload.reason || "public_presentations_unavailable");
    if (!collectionResponse.ok) throw new Error(collectionPayload.reason || "collections_unavailable");
    presentations = presentationPayload.presentations || [];
    ownCollections = (collectionPayload.collections || []).filter(
      (collection) => collection.owner?.id === currentIdentity?.user?.id
    );
    renderPublicPresentationForm();
    renderPublicPresentations();
    if (announce) setFeedback("Carteleras públicas actualizadas.");
  } catch (error) {
    setFeedback(errorMessage(error.message), "error");
  }
}

export function renderPublicPresentationForm() {
  const selected = fields.publicPresentationCollection.value;
  fields.publicPresentationCollection.innerHTML = ownCollections.length
    ? `<option value="">Elegí una colección propia</option>${ownCollections.map((collection) => `
      <option value="${escapeAttr(collection.id || "")}" ${collection.id === selected ? "selected" : ""}>
        ${escapeHtml(collection.title || "Colección sin título")} · ${Number(collection.counts?.total || 0)} obras
      </option>`).join("")}`
    : '<option value="">No hay colecciones propias para publicar</option>';
  fields.createPublicPresentation.disabled = !ownCollections.length;
  fields.previewPublicPresentation.disabled = !ownCollections.length;
}

export function renderPublicPresentations() {
  if (!presentations.length) {
    fields.publicPresentationList.innerHTML = `<div class="member-list-empty"><strong>Todavía no hay carteleras públicas</strong><span>Prepará un snapshot arriba. La instancia sigue privada hasta que lo publiques.</span></div>`;
    return;
  }
  fields.publicPresentationList.innerHTML = presentations.map((presentation) => {
    const active = presentation.status === "active";
    return `<article class="public-presentation-admin-row" data-public-presentation-id="${escapeAttr(presentation.id || "")}">
      <div>
        <span class="member-state ${active ? "member-state-active" : "member-state-disabled"}">${active ? "Activa" : "Revocada"}</span>
        <strong>${escapeHtml(presentation.title || "Cartelera")}</strong>
        <p>${Number(presentation.item_count || 0)} obras · snapshot ${escapeHtml(formatDate(presentation.updated_at))}</p>
      </div>
      <div class="member-row-actions">
        ${active ? `<button class="quiet-action" type="button" data-public-presentation-action="refresh" data-public-presentation-id="${escapeAttr(presentation.id || "")}">Refrescar snapshot</button>
        <button class="quiet-action member-deactivate" type="button" data-public-presentation-action="revoke" data-public-presentation-id="${escapeAttr(presentation.id || "")}">Revocar</button>` : ""}
      </div>
    </article>`;
  }).join("");
}

export async function previewPublicPresentation() {
  setFeedback("");
  try {
    const response = await apiFetch("/api/public-presentations/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formPayload())
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
    const snapshot = payload.presentation || {};
    const items = Array.isArray(snapshot.items) ? snapshot.items : [];
    fields.publicPresentationPreview.hidden = false;
    fields.publicPresentationPreview.innerHTML = `<strong>Snapshot listo · ${items.length} obras</strong><span>Se publicarían solamente título, año, tipo, géneros y duración. No hay rutas, perfiles ni estado personal.</span><ol>${items.slice(0, 4).map((item) => `<li>${escapeHtml(item.title || "Obra")}${item.year ? ` <small>${escapeHtml(item.year)}</small>` : ""}</li>`).join("")}${items.length > 4 ? `<li>y ${items.length - 4} más…</li>` : ""}</ol>`;
    setFeedback("La previsualización es privada. Publicar crea un enlace nuevo y revocable.");
  } catch (error) {
    setFeedback(errorMessage(error.message), "error");
  }
}

export async function createPublicPresentation(event) {
  event.preventDefault();
  fields.createPublicPresentation.disabled = true;
  setFeedback("Creando enlace revocable…");
  try {
    const response = await apiFetch("/api/public-presentations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formPayload())
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
    const link = new URL(payload.url, window.location.origin).href;
    fields.publicPresentationPreview.hidden = false;
    fields.publicPresentationPreview.innerHTML = `<strong>Enlace creado</strong><code>${escapeHtml(link)}</code><button class="quiet-action" type="button" data-copy-public-url="${escapeAttr(link)}">Copiar enlace</button><span>Se muestra una sola vez: guardalo ahora. Podés revocar la cartelera cuando quieras.</span>`;
    fields.publicPresentationForm.reset();
    setFeedback("Cartelera pública creada. El enlace no queda guardado en la interfaz.");
    await loadPublicPresentations();
  } catch (error) {
    setFeedback(errorMessage(error.message), "error");
  } finally {
    fields.createPublicPresentation.disabled = !ownCollections.length;
  }
}

export async function handlePublicPresentationAction(event) {
  const copy = event.target.closest("[data-copy-public-url]");
  if (copy) {
    try {
      await navigator.clipboard.writeText(copy.dataset.copyPublicUrl || "");
      setFeedback("Enlace copiado.");
    } catch {
      setFeedback("Copiá el enlace manualmente antes de cerrar esta pantalla.");
    }
    return;
  }
  const button = event.target.closest("[data-public-presentation-action]");
  if (!button) return;
  const action = button.dataset.publicPresentationAction;
  const id = button.dataset.publicPresentationId || "";
  if (action === "revoke" && !confirm("¿Revocar esta cartelera? El enlace dejará de funcionar de inmediato.")) return;
  button.disabled = true;
  try {
    const response = await apiFetch(`/api/public-presentations/${encodeURIComponent(id)}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}"
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
    setFeedback(action === "revoke" ? "Cartelera revocada inmediatamente." : "Snapshot actualizado.");
    await loadPublicPresentations();
  } catch (error) {
    setFeedback(errorMessage(error.message), "error");
  } finally {
    button.disabled = false;
  }
}

function formPayload() {
  return {
    collection_id: fields.publicPresentationCollection.value,
    title: fields.publicPresentationTitle.value,
    description: fields.publicPresentationDescription.value
  };
}

function formatDate(value) {
  const date = new Date(value || "");
  return Number.isNaN(date.getTime()) ? "sin fecha" : date.toLocaleString();
}

function setFeedback(message, tone = "") {
  setInlineFeedback(fields.publicPresentationFeedback, message, tone);
}

function errorMessage(reason) {
  if (String(reason || "").includes("Select one")) return "Elegí una colección propia para la cartelera.";
  if (String(reason || "").includes("limited to 200")) return "La colección supera el límite de 200 obras para una cartelera pública.";
  if (String(reason || "").includes("title must")) return "El título público debe tener entre 2 y 120 caracteres.";
  return "No pudimos actualizar la cartelera pública. Volvé a intentar.";
}
