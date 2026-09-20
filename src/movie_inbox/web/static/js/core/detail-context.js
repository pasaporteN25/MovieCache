import { escapeAttr, escapeHtml } from "./format.js";
import { apiFetch } from "./http.js";

const number = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 });
const regions = new Intl.DisplayNames(["es"], { type: "region" });

function regionName(code) {
  try { return regions.of(code) || code; } catch { return code; }
}

async function read(url, options) {
  const response = await apiFetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.reason || "request_failed");
  return payload;
}

function notice(attribution, sources) {
  return sources.map(source => attribution?.[source])
    .filter(Boolean).map(text => `<p class="detail-attribution">${escapeHtml(text)}</p>`).join("");
}

export function ratingsMarkup(payload, id) {
  const rows = (payload.ratings?.[id] || [])
    .filter(row => !row.expires_at || Date.parse(row.expires_at) > Date.now())
    .slice().sort((a, b) => b.votes - a.votes);
  if (!rows.length) return `<p class="detail-context-empty">Todavía no hay puntajes públicos para esta obra.</p>`;
  return `<dl class="detail-public-scores">${rows.map(row => `<div${row.is_meaningful === false ? ' class="is-low-vote"' : ""}>
    <dt>${escapeHtml(({ imdb: "IMDb", tmdb: "TMDb" })[row.source] || row.source)}</dt>
    <dd><strong>${number.format(row.average)}</strong><span> / ${number.format(row.scale)}</span></dd>
    <dd class="detail-votes">${number.format(row.votes)} votos${row.is_meaningful === false ? " · Poco representativo" : ""}</dd>
  </div>`).join("")}</dl>${notice(payload.attribution, [...new Set(rows.map(row => row.source))])}`;
}

function offerGroup(label, offers) {
  if (!offers.length) return "";
  const unique = [...new Map(offers.map(offer => [offer.provider_id, offer])).values()];
  return `<div class="detail-offer-group"><h4>${label}</h4><ul>${unique.map(offer => `<li>${escapeHtml(offer.provider_name)}</li>`).join("")}</ul></div>`;
}

export function streamingMarkup(payload, id) {
  const row = payload.availability?.[id];
  if (!row?.known) return `<p class="detail-context-empty">Todavía no tenemos información de streaming para esta obra.</p>`;
  const available = row.available_on || [];
  const acquire = row.acquire_on || [];
  const groups = offerGroup("Con suscripción", available.filter(offer => offer.kind === "flatrate"))
    + offerGroup("Gratis", available.filter(offer => offer.kind === "free"))
    + offerGroup("Con anuncios", available.filter(offer => offer.kind === "ads"))
    + offerGroup("Alquilar", acquire.filter(offer => offer.kind === "rent"))
    + offerGroup("Comprar", acquire.filter(offer => offer.kind === "buy"));
  let link = "";
  try {
    const url = new URL(row.link);
    if (url.protocol === "https:") link = `<a class="detail-streaming-link" href="${escapeAttr(url.href)}" target="_blank" rel="noopener noreferrer">Consultar opciones de streaming ↗</a>`;
  } catch { /* A missing link does not prevent reading the offers. */ }
  return `${groups || '<p class="detail-context-empty">No encontramos opciones en las plataformas visibles de este país.</p>'}${link}${notice(payload.attribution, ["justwatch"])}`;
}

export function availabilityIcon(kind) {
  const shape = kind === "library"
    ? '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8" cy="11" r="2"/><circle cx="16" cy="11" r="2"/><path d="M7 19v-3h10v3"/>'
    : '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="m10 8 5 3-5 3zM8 21h8m-4-4v4"/>';
  return `<svg class="detail-availability-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">${shape}</svg>`;
}

export function streamingSignal(row, state = "ready") {
  const available = row?.known && row.available_on?.length > 0;
  const label = state === "loading" ? "Consultando" : state === "error" ? "Sin conexión"
    : !row?.known ? "Sin información" : available ? "Disponible"
      : row.acquire_on?.length ? "Alquiler / compra" : "Sin opciones";
  return `<span class="detail-access-signal${available ? " is-available" : ""}">${availabilityIcon("streaming")}<span>Streaming<small>${label}</small></span></span>`;
}

export function mountDetailContext(host, id, signalHost) {
  if (!host) return;
  host.innerHTML = `<section class="detail-public-section" aria-labelledby="detailPublicHeading">
    <div class="record-heading"><h3 id="detailPublicHeading">Puntajes públicos</h3><span class="detail-context-note">Opiniones de otras personas</span></div>
    <div data-public-ratings aria-live="polite" aria-busy="true"><p class="detail-context-empty">Cargando puntajes…</p></div>
  </section>
  <section class="detail-streaming-section" aria-labelledby="detailStreamingHeading">
    <div class="record-heading"><h3 id="detailStreamingHeading">Dónde verla</h3><div data-streaming-region></div></div>
    <div data-streaming-offers aria-live="polite" aria-busy="true"><p class="detail-context-empty">Consultando streaming…</p></div>
  </section>`;
  const ratingsHost = host.querySelector("[data-public-ratings]");
  const offersHost = host.querySelector("[data-streaming-offers]");
  const regionHost = host.querySelector("[data-streaming-region]");
  let preferences;
  let generation = 0;
  const alive = () => host.isConnected;
  const signal = (row, state) => { if (alive() && signalHost?.isConnected) signalHost.innerHTML = streamingSignal(row, state); };
  function error(target, message, retry) {
    if (!alive()) return;
    target.setAttribute("aria-busy", "false");
    target.innerHTML = `<p class="detail-context-empty">${message}</p><button type="button" class="quiet-action detail-context-retry">Reintentar</button>`;
    target.querySelector("button").addEventListener("click", retry);
  }
  async function loadRatings() {
    ratingsHost.setAttribute("aria-busy", "true");
    try {
      const payload = await read(`/api/ratings?item_id=${encodeURIComponent(id)}`);
      if (!alive()) return;
      ratingsHost.innerHTML = ratingsMarkup(payload, id);
      ratingsHost.setAttribute("aria-busy", "false");
    } catch {
      error(ratingsHost, "No se pudieron cargar los puntajes públicos.", loadRatings);
    }
  }
  function renderRegion() {
    const code = preferences.effective_region;
    if (!preferences.may_choose) {
      regionHost.innerHTML = `<span class="detail-context-note">${escapeHtml(code ? regionName(code) : "Sin país configurado")}</span>`;
      return;
    }
    regionHost.innerHTML = `<label class="detail-region-label">País <select aria-label="País para streaming"><option value="">Predeterminado${code && !preferences.preferences?.region ? ` · ${escapeHtml(regionName(code))}` : ""}</option>${preferences.available_regions.map(region => `<option value="${escapeAttr(region)}"${preferences.preferences?.region === region ? " selected" : ""}>${escapeHtml(regionName(region))}</option>`).join("")}</select></label>`;
    regionHost.querySelector("select").addEventListener("change", async event => {
      const select = event.target;
      const previous = preferences.preferences?.region || "";
      const hadFocus = document.activeElement === select;
      // Invalidate the previous country's read as soon as the new choice starts.
      ++generation;
      select.disabled = true;
      offersHost.innerHTML = '<p class="detail-context-empty">Cambiando país…</p>';
      offersHost.setAttribute("aria-busy", "true");
      signal(null, "loading");
      try {
        await read("/api/streaming/preferences", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...preferences.preferences, region: select.value })
        });
        if (alive()) await loadStreaming();
      } catch {
        select.value = previous;
        signal(null, "error");
        error(offersHost, "No se pudo cambiar el país. Revisá la conexión y volvé a intentarlo.", loadStreaming);
      } finally {
        select.disabled = false;
        if (alive() && hadFocus && (document.activeElement === document.body || document.activeElement === select)) regionHost.querySelector("select")?.focus();
      }
    });
  }
  async function loadStreaming() {
    const request = ++generation;
    offersHost.setAttribute("aria-busy", "true");
    offersHost.innerHTML = '<p class="detail-context-empty">Consultando streaming…</p>';
    signal(null, "loading");
    try {
      preferences = await read("/api/streaming/preferences");
      if (!alive() || request !== generation) return;
      renderRegion();
      if (!preferences.effective_region) {
        offersHost.innerHTML = '<p class="detail-context-empty">La instancia todavía no tiene un país configurado para consultar streaming.</p>';
        signal(null);
      } else {
        const payload = await read(`/api/streaming/availability?item_id=${encodeURIComponent(id)}`);
        if (!alive() || request !== generation) return;
        offersHost.innerHTML = streamingMarkup(payload, id);
        signal(payload.availability?.[id]);
      }
      offersHost.setAttribute("aria-busy", "false");
    } catch {
      if (request === generation) {
        signal(null, "error");
        error(offersHost, "No se pudo consultar la disponibilidad en streaming.", loadStreaming);
      }
    }
  }
  void loadRatings();
  void loadStreaming();
}
