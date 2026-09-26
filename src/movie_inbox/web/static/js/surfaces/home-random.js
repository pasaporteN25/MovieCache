import { fields } from "../core/fields.js";
import { availabilityState, displayTitle, escapeAttr, escapeHtml } from "../core/format.js";
import { drawRandomItem, randomResultState } from "../core/random-draw.js";
import { items } from "../core/state.js";
import { randomCandidates } from "./catalog-grid.js";
import { renderEditorialSections, selectHomeRandomResult } from "./home.js";

// U8 — the terminal "Al azar" VHS at the end of the Home library. One result id
// feeds the spine, the consultation console, the right poster and "Ver más"; the
// draw never opens the dossier by itself.

let resultId = "";
let busy = false;
const HOME_RANDOM_REVEAL_MS = 420;
const HOME_RANDOM_SETTLE_MS = 260;

function catalogOnly() {
  return Boolean(fields.randomCatalogOnly?.checked);
}

function resultItem() {
  return resultId ? items.find((item) => String(item.id) === resultId) || null : null;
}

function reducedMotion() {
  return typeof window !== "undefined"
    && Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
}

// "rewind" (A, recommended) or "strip" (B); the owner chooses in U8.4.1.
function revealEffect() {
  return fields.homeView?.dataset?.randomEffect === "strip" ? "strip" : "rewind";
}

export function homeRandomEntry() {
  const item = resultItem();
  if (!item) return null;
  return { key: `random:${item.id}`, item, origin: { kind: "catalog" }, reason: { label: "Al azar" } };
}

export function homeRandomState() {
  if (busy) return "busy";
  if (resultId) {
    const item = resultItem();
    if (!item) return "error";
    return randomResultState(item, { available: availabilityState(item).effective, catalogOnly: catalogOnly() });
  }
  return randomCandidates().length ? "initial" : "empty";
}

function scopeLabel() {
  return catalogOnly() ? "Disponibles" : "Todo";
}

function emptyReason() {
  if (!items.length) return "Todavía no hay obras en tu catálogo.";
  return catalogOnly() ? "No hay obras disponibles para sortear." : "No hay obras para sortear.";
}

function spineCopy(state, item) {
  const title = (item && displayTitle(item)) || "Sin título";
  const year = String(item?.year || "S/A");
  switch (state) {
    case "busy": return { title: "Eligiendo…", year: "", label: "Eligiendo una obra al azar…" };
    case "available": return { title, year, label: `${title}. ${year}. Resultado al azar, disponible. Activá para elegir otra obra.` };
    case "unavailable": return { title, year, label: `${title}. ${year}. Resultado al azar, no disponible. Activá para elegir otra obra.` };
    case "out-of-scope": return { title, year, label: `${title}. ${year}. No entra en «Solo disponibles». Activá para elegir otra obra disponible.` };
    case "error": return { title: "Obra retirada", year: "", label: "La obra sorteada ya no está en tu catálogo. Activá para elegir otra." };
    case "empty": return { title: "Sin obras", year: "", label: `${emptyReason()} Activá para ver las opciones.` };
    default: return { title: "Elegir una obra", year: "", label: `Elegir una obra al azar entre ${scopeLabel() === "Todo" ? "todo el catálogo" : "las disponibles"}.` };
  }
}

function noteMarkup(state) {
  if (state === "empty") {
    const scopeAction = catalogOnly() && items.length
      ? '<button type="button" class="spotlight-preview-action" data-click="home-random-include-all">Incluir no disponibles</button>' : "";
    return `<div class="home-random-note" role="note"><p>${escapeHtml(emptyReason())}</p>${scopeAction}<button type="button" class="spotlight-preview-action is-secondary" data-click="home-random-collection">Abrir colección</button></div>`;
  }
  if (state === "out-of-scope") {
    return '<div class="home-random-note" role="note"><p>Esta obra no está disponible y quedó fuera de «Solo disponibles».</p><button type="button" class="spotlight-preview-action" data-click="home-random-draw">Elegir otra</button></div>';
  }
  if (state === "error") {
    return '<div class="home-random-note" role="note"><p>La obra sorteada ya no está en tu catálogo.</p><button type="button" class="spotlight-preview-action" data-click="home-random-draw">Elegir otra</button></div>';
  }
  return "";
}

export function homeRandomBay(selected = false) {
  const state = homeRandomState();
  const item = resultItem();
  const copy = spineCopy(state, item);
  const titleLength = Array.from(copy.title).length;
  const lengthClass = titleLength <= 22 ? "short" : titleLength <= 36 ? "long" : "xlong";
  const vhsState = selected && ["available", "unavailable", "out-of-scope"].includes(state) ? "selected" : "closed";
  return `<section class="home-program home-random-bay" data-home-random data-random-state="${state}" aria-labelledby="home-random-title">
    <h2 id="home-random-title" class="home-shelf-heading"><span class="home-random-plaque"><span>Al azar</span><small>${escapeHtml(scopeLabel())}</small></span></h2>
    <div class="home-random-rail">
      <button class="home-shelf-tape vhs-spine home-random-tape" type="button" data-click="home-random-draw" data-vhs-state="${vhsState}" data-random-state="${state}" data-title-length="${lengthClass}" aria-label="${escapeAttr(copy.label)}"${state === "busy" ? ' aria-busy="true"' : ""}>
        <span class="vhs-spine-sticker" aria-hidden="true"></span>
        <span class="vhs-spine-title" aria-hidden="true">${escapeHtml(copy.title)}</span>
        ${state === "unavailable" || state === "out-of-scope" ? '<span class="home-random-mark" aria-hidden="true">?</span>' : ""}
        <span class="vhs-spine-meta" aria-hidden="true"><span class="vhs-spine-year">${escapeHtml(copy.year || "—")}</span><span class="vhs-spine-format">VHS</span></span>
      </button>
      ${noteMarkup(state)}
    </div>
  </section>`;
}

function announce(text) {
  if (fields.homeSelectionAnnouncement) fields.homeSelectionAnnouncement.textContent = text;
}

function spine() {
  return fields.homeSections?.querySelector?.("[data-home-random] .home-random-tape") || null;
}

function revealBay() {
  const rail = fields.homeSections;
  const bay = rail?.querySelector?.("[data-home-random]");
  if (!rail || !bay?.getBoundingClientRect) return;
  const bounds = rail.getBoundingClientRect(), box = bay.getBoundingClientRect();
  if (box.right > bounds.right) rail.scrollLeft += box.right - bounds.right;
  else if (box.left < bounds.left) rail.scrollLeft += box.left - bounds.left;
}

function playEffect(effect, pool, done) {
  const tape = spine();
  const title = tape?.querySelector(".vhs-spine-title");
  if (!title) {
    done();
    return;
  }
  if (effect === "strip") {
    // B: a short run of real catalogue titles, decorative and hidden from AT.
    const names = pool.map((item) => displayTitle(item)).filter(Boolean);
    let step = 0;
    const timer = window.setInterval(() => {
      if (!title.isConnected || !names.length) return;
      title.textContent = names[step % names.length];
      step += 1;
    }, 70);
    window.setTimeout(() => {
      window.clearInterval(timer);
      done();
    }, HOME_RANDOM_REVEAL_MS);
    return;
  }
  // A: the current label rewinds along the spine before the result settles in.
  title.classList.add("is-rewinding");
  window.setTimeout(done, HOME_RANDOM_REVEAL_MS);
}

function settle() {
  const title = spine()?.querySelector(".vhs-spine-title");
  if (!title) return;
  title.classList.add("is-settling");
  window.setTimeout(() => title.classList.remove("is-settling"), HOME_RANDOM_SETTLE_MS);
}

function finalAnnouncement(item) {
  const state = randomResultState(item, { available: availabilityState(item).effective, catalogOnly: catalogOnly() });
  const title = displayTitle(item) || "Sin título";
  return `Al azar: ${title}${item.year ? `, ${item.year}` : ""}. ${state === "available" ? "Disponible" : "No disponible"}.`;
}

// Header "Al azar" and the spine share this draw while Home is visible.
export function drawHomeRandom({ reveal = false, focusSpine = false } = {}) {
  // Clicks while the label is moving coalesce into the draw already chosen.
  if (busy) return false;
  const candidates = randomCandidates();
  if (reveal) revealBay();
  if (!candidates.length) {
    renderEditorialSections();
    announce(`Al azar: ${emptyReason()}`);
    if (focusSpine) spine()?.focus({ preventScroll: true });
    return false;
  }
  const item = drawRandomItem(candidates, { excludeId: resultId });
  const hadFocus = Boolean(spine() && document.activeElement === spine());
  const finish = () => {
    busy = false;
    resultId = String(item.id);
    selectHomeRandomResult(homeRandomEntry());
    announce(finalAnnouncement(item));
    if (hadFocus || focusSpine) spine()?.focus({ preventScroll: true });
    if (!reducedMotion()) settle();
  };
  if (reducedMotion()) {
    finish();
    return true;
  }
  busy = true;
  renderEditorialSections();
  if (hadFocus || focusSpine) spine()?.focus({ preventScroll: true });
  const pool = candidates.filter((candidate) => candidate !== item).slice(0, 8);
  playEffect(revealEffect(), pool, finish);
  return true;
}

// Preference changes keep the consultation; the spine explains the new scope.
export function syncHomeRandomScope() {
  renderEditorialSections();
}

export function includeUnavailableInHomeRandom() {
  if (!fields.randomCatalogOnly) return;
  fields.randomCatalogOnly.checked = false;
  fields.randomCatalogOnly.dispatchEvent(new Event("change", { bubbles: true }));
  spine()?.focus({ preventScroll: true });
}
