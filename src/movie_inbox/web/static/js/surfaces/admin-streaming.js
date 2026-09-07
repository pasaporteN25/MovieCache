import { escapeAttr, escapeHtml, setInlineFeedback } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { currentIdentity } from "../core/state.js";
import { fields } from "../core/fields.js";

let configuration = { regions: [], policy: {}, providers: {}, upstream_configured: false };

export async function loadStreamingConfiguration({ announce = false } = {}) {
  if (currentIdentity?.user?.role !== "owner") return;
  try {
    const response = await apiFetch("/api/streaming/configuration");
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.reason || "streaming_unavailable");
    configuration = payload;
    renderStreamingConfiguration();
    if (announce) setFeedback("Configuración de plataformas actualizada.");
  } catch (error) {
    setFeedback(errorMessage(error.message), "error");
  }
}

export function renderStreamingConfiguration() {
  const regions = configuration.regions || [];
  const policy = configuration.policy || {};
  const enabled = regions.filter((region) => region.enabled);

  fields.streamingPolicy.innerHTML = `
    <label>Región por defecto de la instancia
      <select id="streamingDefaultRegion" ${enabled.length ? "" : "disabled"}>
        <option value="">Sin definir</option>
        ${enabled.map((region) => `
          <option value="${escapeAttr(region.code)}" ${region.code === policy.default_region ? "selected" : ""}>
            ${escapeHtml(region.name)} (${escapeHtml(region.code)})
          </option>`).join("")}
      </select>
    </label>
    <label class="streaming-policy-toggle">
      <input id="streamingMembersMayChoose" type="checkbox" ${policy.members_may_choose ? "checked" : ""}>
      <span>Cada miembro puede elegir su propia región</span>
    </label>
    <p class="streaming-policy-note">La credencial es de la instancia; el mercado que mira cada persona no tiene por qué serlo.</p>`;

  if (!regions.length) {
    fields.streamingRegionList.innerHTML = `<div class="member-list-empty">
      <strong>Todavía no hay regiones configuradas</strong>
      <span>${configuration.upstream_configured
        ? "Agregá una región para empezar a consultar disponibilidad."
        : "Sin credencial de TMDb no se puede consultar disponibilidad, pero podés dejar las regiones preparadas."}</span>
    </div>`;
    return;
  }

  fields.streamingRegionList.innerHTML = regions.map((region) => {
    const providers = (configuration.providers || {})[region.code] || [];
    return `<article class="streaming-region-row" data-streaming-region="${escapeAttr(region.code)}">
      <div>
        <span class="member-state ${region.enabled ? "member-state-active" : "member-state-disabled"}">
          ${region.enabled ? "Activa" : "Inactiva"}
        </span>
        <strong>${escapeHtml(region.name)}</strong>
        <p>${escapeHtml(region.code)} · ${providers.length} plataforma${providers.length === 1 ? "" : "s"}</p>
        ${providers.length ? `<ul class="streaming-provider-list">${providers.slice(0, 12).map((provider) => `
          <li>${escapeHtml(provider.name)}</li>`).join("")}${providers.length > 12
            ? `<li class="streaming-provider-more">y ${providers.length - 12} más</li>` : ""}</ul>` : ""}
      </div>
      <div class="member-row-actions">
        <button class="quiet-action" type="button" data-streaming-action="toggle" data-streaming-region="${escapeAttr(region.code)}">
          ${region.enabled ? "Desactivar" : "Activar"}
        </button>
        <button class="quiet-action" type="button" data-streaming-action="refresh" data-streaming-region="${escapeAttr(region.code)}"
          ${configuration.upstream_configured && region.enabled ? "" : "disabled"}>
          Traer plataformas
        </button>
      </div>
    </article>`;
  }).join("");
}

export async function handleStreamingAction(event) {
  const button = event.target.closest("[data-streaming-action]");
  if (!button) return;
  const action = button.dataset.streamingAction;
  const code = button.dataset.streamingRegion || "";
  if (action === "toggle") {
    const region = (configuration.regions || []).find((row) => row.code === code);
    await post(`/api/streaming/regions/${encodeURIComponent(code)}/status`, {
      enabled: !region?.enabled
    });
  } else if (action === "refresh") {
    await post(`/api/streaming/regions/${encodeURIComponent(code)}/providers/refresh`, {});
  }
}

export async function addStreamingRegion(event) {
  event.preventDefault();
  const code = fields.streamingRegionCode.value.trim();
  if (!code) {
    setFeedback("Indicá un código de país de dos letras, por ejemplo AR.", "error");
    return;
  }
  const added = await post("/api/streaming/regions", {
    code,
    name: fields.streamingRegionName.value.trim() || code.toUpperCase()
  });
  if (added) {
    fields.streamingRegionCode.value = "";
    fields.streamingRegionName.value = "";
  }
}

export async function saveStreamingPolicy() {
  const region = document.getElementById("streamingDefaultRegion");
  const members = document.getElementById("streamingMembersMayChoose");
  await post("/api/streaming/policy", {
    default_region: region ? region.value : "",
    members_may_choose: Boolean(members && members.checked)
  });
}

async function post(url, body) {
  try {
    const response = await apiFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.reason || "streaming_unavailable");
    await loadStreamingConfiguration();
    setFeedback("Configuración guardada.");
    return true;
  } catch (error) {
    setFeedback(errorMessage(error.message), "error");
    return false;
  }
}

function setFeedback(message, tone = "") {
  setInlineFeedback(fields.streamingFeedback, message, tone);
}

function errorMessage(reason) {
  const messages = {
    invalid_region: "El código de región tiene que ser de dos letras, como AR o BR.",
    invalid_policy: "Esa región no está activa, así que no puede ser la de por defecto.",
    invalid_provider: "La lista de plataformas que devolvió la fuente no es válida.",
    region_not_found: "Esa región ya no está configurada.",
    streaming_source_not_configured: "Cargá la credencial de TMDb para traer plataformas.",
    streaming_source_unavailable: "No se pudo consultar la fuente. Probá de nuevo en un rato.",
    streaming_unavailable: "No se pudo guardar la configuración de plataformas."
  };
  return messages[reason] || "No se pudo completar la operación.";
}
