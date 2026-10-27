// Buscador de Inicio (IP1/IP2). Combobox accesible que consume /api/search sin
// matching propio. «+ Pendiente» escribe por /api/add (mismo camino que Colección) y
// nunca manda action "force" ni target_id. Las recientes son personales (C2).
import { apiFetch } from "../core/http.js";
import { createRecentSearches } from "../core/recent-searches.js";

export const LOCAL_DEBOUNCE_MS = 150;
export const EXTERNAL_DEBOUNCE_MS = 400;
export const EXTERNAL_MIN_CHARS = 3;
export const EXTERNAL_VISIBLE = 3;
export const LOCAL_VISIBLE = 5;

// Misma lista que EXTERNAL_LINK_HOSTS (domain/catalog.py); sólo cambia el rótulo.
export const LINK_HOSTS = {
  wikipedia: "wikipedia.org",
  imdb: "imdb.com",
  filmaffinity: "filmaffinity.com",
  jikan: "myanimelist.net",
  tmdb: "themoviedb.org"
};
const SOURCE_LABELS = {
  wikipedia: "Wikipedia", imdb: "IMDb", filmaffinity: "FilmAffinity", jikan: "MyAnimeList",
  anime_offline_database: "MyAnimeList", tmdb: "TMDb", wikidata: "Wikidata"
};

export function detectLinkSource(text) {
  const value = String(text || "").trim();
  if (!/^https?:\/\//i.test(value)) return "";
  let host = "";
  try { host = new URL(value).hostname.toLowerCase().replace(/\.$/, ""); } catch { return ""; }
  for (const [source, expected] of Object.entries(LINK_HOSTS)) {
    if (host === expected || host.endsWith(`.${expected}`)) return source;
  }
  return "";
}

export function sourceLabel(result) {
  const key = result?._search_shelf || result?.source || "";
  return SOURCE_LABELS[key] || key || "Fuente externa";
}

export function resultScore(result) {
  const score = Number(result?._search?.score);
  return Number.isFinite(score) ? score : 0;
}

// Los 3 primeros por _search.score (estable ante empates).
export function topExternal(results, limit = EXTERNAL_VISIBLE) {
  return (Array.isArray(results) ? results : [])
    .map((result, index) => ({ result, index }))
    .sort((a, b) => resultScore(b.result) - resultScore(a.result) || a.index - b.index)
    .slice(0, limit)
    .map(({ result }) => result);
}

// C1: estado de pertenencia. Sin dato del servidor se trata como «Revisar»: nunca
// se ofrece agregar si no se sabe que la obra falta.
export function membershipOf(result) {
  const m = result?._membership;
  const state = m?.state;
  if (state === "present") return { state, itemId: m.item_id || null };
  if (state === "missing") return { state, itemId: null };
  return { state: "review", itemId: null };
}

// Estado visible de la fila: combina C1 con lo ocurrido en C5 (override).
export function rowStateFor(result, override = "") {
  if (override) return override;
  const { state } = membershipOf(result);
  return state === "present" ? "present" : state === "missing" ? "missing" : "review";
}

export const STATE_LABELS = {
  present: "Ya la tenés", missing: "+ Pendiente", review: "Revisar",
  busy: "Agregando...", added: "Agregada", existing: "Ya la tenés", error: "Reintentar"
};

export function buildExpandPath(query) {
  const params = new URLSearchParams({ view: "catalog", mode: "add", q: String(query ?? "").trim() });
  return `?${params.toString()}`;
}

export function externalKey(result) {
  return String(result?.tmdb_id || result?.imdb_id || result?.mal_id || result?.wikidata_id
    || result?.url || [result?.title, result?.year].filter(Boolean).join("|") || "unknown");
}

function titleOf(item) {
  return item?.spanish_title || item?.title || item?.original_title || item?.english_title || "Obra sin título";
}
function imageOf(item) {
  return item?.page_image || item?.image_url || item?.poster_url || "";
}

// Adapta una obra local o externa a la forma de entrada de los pósters de Inicio.
export function toPreviewEntry(item, extra = {}) {
  if (!item) return null;
  return { key: extra.key || item.id || externalKey(item), item, title: titleOf(item), year: item.year || "",
    image: imageOf(item), id: extra.id ?? (item.id || null), origin: { kind: extra.kind || "catalog" } };
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function thumb(image) {
  return image
    ? `<img class="hs-thumb" src="/image-cache?url=${encodeURIComponent(image)}" alt="" loading="lazy" decoding="async">`
    : `<span class="hs-thumb hs-thumb-empty" aria-hidden="true"></span>`;
}

// `/` enfoca el buscador salvo que el foco ya esté escribiendo en otro campo.
export function isTextEntryTarget(target) {
  if (!target || target.nodeType === 9) return false;
  if (target.isContentEditable) return true;
  const tag = String(target.tagName || "").toLowerCase();
  if (tag === "textarea" || tag === "select") return true;
  if (tag !== "input") return false;
  const type = String(target.type || "text").toLowerCase();
  return !["checkbox", "radio", "button", "submit", "reset", "range", "color", "file", "image"].includes(type);
}

let mountCounter = 0;

export function mountHomeSearch(container, options = {}) {
  const {
    onPreview = () => {}, onExpand = () => {}, onOpenItem = () => {}, onAdded = () => {},
    suggestions = [], username = "",
    fetcher = apiFetch,
    recents = createRecentSearches(username),
    debounce = {}
  } = options;
  const localDelay = debounce.local ?? LOCAL_DEBOUNCE_MS;
  const externalDelay = debounce.external ?? EXTERNAL_DEBOUNCE_MS;
  let emptyCatalog = Boolean(options.emptyCatalog);
  const uid = `hs${++mountCounter}`;
  const labelText = () => (emptyCatalog ? "Buscá la primera película que querés recordar" : "Buscar una película, serie o persona");
  let suggestionList = Array.isArray(suggestions) ? suggestions : [];

  container.innerHTML = `
    <div class="hs-root" data-open="false">
      <div class="hs-bar">
        <label class="hs-label" for="${uid}-input">${labelText()}</label>
        <button type="button" class="hs-close" data-close>Cerrar</button>
      </div>
      <input id="${uid}-input" class="hs-input" type="search" role="combobox" autocomplete="off" spellcheck="false"
        aria-autocomplete="list" aria-expanded="false" aria-controls="${uid}-list" placeholder="Título, año o pegá un enlace">
      <div id="${uid}-list" class="hs-panel" role="listbox" aria-label="Resultados de búsqueda" hidden></div>
      <p id="${uid}-status" class="hs-status" role="status" aria-live="polite"></p>
    </div>`;
  const input = container.querySelector(".hs-input");
  const panel = container.querySelector(".hs-panel");
  const status = container.querySelector(".hs-status");
  const root = container.querySelector(".hs-root");
  const label = container.querySelector(".hs-label");

  let rows = [];
  let active = -1;
  let open = false;
  let seq = 0;
  let localController = null;
  let externalController = null;
  let localTimer = null;
  let externalTimer = null;
  const model = { query: "", local: [], localState: "idle", external: [], externalTotal: 0, externalState: "idle", warning: "" };
  const overrides = new Map();
  const messages = new Map();

  const query = () => input.value.trim();

  function abortAll() {
    clearTimeout(localTimer); clearTimeout(externalTimer);
    localController?.abort(); externalController?.abort();
    localController = externalController = null;
  }

  function buildRows() {
    rows = [];
    const q = query();
    const groups = [];
    if (!q) {
      const recent = recents.list();
      if (recent.length) groups.push({ id: "recent", label: "Recientes", clearAll: true, rows: recent.map((text) => ({ kind: "recent", text })) });
      if (!emptyCatalog && suggestionList.length) {
        groups.push({ id: "suggest", label: "Sugerencias", rows: suggestionList.map((entry) => ({ kind: "suggestion", entry })) });
      }
    } else {
      if (model.local.length) groups.push({ id: "local", label: "En tu colección", rows: model.local.slice(0, LOCAL_VISIBLE).map((item) => ({ kind: "local", item })) });
      if (model.external.length) {
        const link = detectLinkSource(q);
        const label = link ? `Enlace de ${SOURCE_LABELS[link]}` : "Para agregar";
        groups.push({ id: "external", label, rows: model.external.map((result) => ({ kind: "external", result })) });
      }
      const total = model.local.length + model.externalTotal;
      groups.push({ id: "foot", label: "", rows: [{ kind: "expand", count: total }] });
    }
    let index = 0;
    for (const group of groups) for (const row of group.rows) { row.index = index++; row.id = `${uid}-opt-${row.index}`; rows.push(row); }
    return groups;
  }

  function rowHtml(row) {
    const selected = row.index === active;
    const base = `id="${row.id}" role="option" class="hs-row hs-${row.kind}" data-index="${row.index}" aria-selected="${selected}"`;
    if (row.kind === "recent") {
      return `<div ${base}><span class="hs-text">${escapeHtml(row.text)}</span>
        <button type="button" class="hs-remove" tabindex="-1" data-remove="${escapeHtml(row.text)}" aria-label="Quitar ${escapeHtml(row.text)} de recientes">×</button></div>`;
    }
    if (row.kind === "suggestion") {
      const e = row.entry;
      return `<div ${base}>${thumb(e.image)}<span class="hs-text"><strong>${escapeHtml(e.title)}</strong>${e.year ? ` <span class="hs-meta">${escapeHtml(e.year)}</span>` : ""}</span></div>`;
    }
    if (row.kind === "local") {
      const i = row.item;
      return `<div ${base}>${thumb(imageOf(i))}<span class="hs-text"><strong>${escapeHtml(titleOf(i))}</strong>${i.year ? ` <span class="hs-meta">${escapeHtml(i.year)}</span>` : ""}</span><span class="hs-state hs-state-present">Abrir</span></div>`;
    }
    if (row.kind === "external") {
      const r = row.result;
      const state = rowStateFor(r, overrides.get(externalKey(r)));
      const note = messages.get(externalKey(r));
      return `<div ${base} data-state="${state}">${thumb(imageOf(r))}<span class="hs-text"><strong>${escapeHtml(titleOf(r))}</strong>${r.year ? ` <span class="hs-meta">${escapeHtml(r.year)}</span>` : ""}
        <span class="hs-source">${escapeHtml(sourceLabel(r))}</span>${note ? `<span class="hs-note">${escapeHtml(note)}</span>` : ""}</span>
        <span class="hs-state hs-state-${state}">${STATE_LABELS[state]}</span></div>`;
    }
    return `<div ${base}><span class="hs-text">Ampliar en Colección (${row.count})</span></div>`;
  }

  function render() {
    const groups = buildRows();
    const q = query();
    const parts = groups.map((group) => {
      const body = group.rows.map(rowHtml).join("");
      if (!group.label) return `<div class="hs-footer" role="presentation">${body}</div>`;
      const clear = group.clearAll ? `<button type="button" class="hs-clear" tabindex="-1" data-clear-all>Borrar todo</button>` : "";
      return `<div class="hs-group" role="group" aria-labelledby="${uid}-g-${group.id}">
        <div class="hs-group-head"><span id="${uid}-g-${group.id}" class="hs-group-label">${group.label}</span>${clear}</div>${body}</div>`;
    });
    if (q && model.warning) parts.push(`<p class="hs-warning">${escapeHtml(model.warning)}</p>`);
    if (q && model.localState === "ready" && !model.local.length && model.externalState !== "loading" && !model.external.length) {
      parts.unshift(`<p class="hs-empty">Sin resultados. Ampliá en Colección o pegá un enlace.</p>`);
    }
    panel.innerHTML = parts.join("");
    const visible = open && (rows.length > 0 || parts.length > 0);
    panel.hidden = !visible;
    input.setAttribute("aria-expanded", String(visible));
    root.dataset.open = String(visible);
    if (active >= rows.length) active = -1;
    if (active >= 0 && rows[active]) input.setAttribute("aria-activedescendant", rows[active].id);
    else input.removeAttribute("aria-activedescendant");
    if (q) {
      const bits = [];
      if (model.localState === "ready") bits.push(`${model.local.length} en tu colección`);
      if (model.externalState === "ready") bits.push(`${model.externalTotal} para agregar`);
      if (bits.length) status.textContent = bits.join(", ");
    }
  }

  function setActive(next) {
    active = next;
    render();
    panel.querySelector('[aria-selected="true"]')?.scrollIntoView?.({ block: "nearest" });
    onPreview(active >= 0 ? previewFor(rows[active]) : null);
  }

  function previewFor(row) {
    if (!row) return null;
    if (row.kind === "suggestion") return row.entry;
    if (row.kind === "local") return toPreviewEntry(row.item, { kind: "catalog" });
    if (row.kind === "external") {
      const { itemId } = membershipOf(row.result);
      return toPreviewEntry(row.result, { kind: "external", id: itemId });
    }
    return null;
  }

  function remember() { recents.add(query()); }

  function expand() {
    const q = query();
    if (!q) return;
    remember();
    close(false);
    onExpand(q);
  }

  function close(restorePoster = true) {
    open = false; active = -1;
    abortAll();
    render();
    if (restorePoster) onPreview(null);
  }

  async function addExternal(row) {
    const result = row.result;
    const key = externalKey(result);
    if (overrides.get(key) === "busy") return;
    overrides.set(key, "busy"); messages.delete(key); render();
    try {
      const { _membership, ...body } = result;
      const response = await fetcher("/api/add", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
      });
      const payload = await response.json().catch(() => ({}));
      if (payload.reason === "possible_duplicate") {
        overrides.set(key, "review");
        status.textContent = "Coincidencia dudosa: revisala en Colección.";
      } else if (payload.reason === "duplicate" || payload.reason === "merged_into_existing") {
        overrides.set(key, "existing");
        status.textContent = "Ya la tenés en tu colección.";
      } else if (response.ok && payload.ok) {
        overrides.set(key, "added");
        status.textContent = "Agregada como pendiente.";
        remember();
        onAdded(payload);
      } else {
        throw new Error(payload.reason || `HTTP ${response.status}`);
      }
    } catch (error) {
      overrides.set(key, "error");
      messages.set(key, "No pudimos guardarla. Reintentá.");
      status.textContent = "No pudimos agregar la obra. Reintentá.";
    }
    render();
  }

  function activate(row) {
    if (!row) return;
    if (row.kind === "recent") { input.value = row.text; onInput(); input.focus(); return; }
    if (row.kind === "suggestion") {
      const id = row.entry.id || row.entry.item?.id;
      if (id) { close(false); onOpenItem(id, row.entry); }
      return;
    }
    if (row.kind === "local") { remember(); close(false); onOpenItem(row.item.id, row.item); return; }
    if (row.kind === "expand") { expand(); return; }
    if (row.kind === "external") {
      const state = rowStateFor(row.result, overrides.get(externalKey(row.result)));
      if (state === "present" || state === "existing") {
        const id = membershipOf(row.result).itemId;
        remember();
        if (id) { close(false); onOpenItem(id, row.result); }
      } else if (state === "review") {
        expand();
      } else if (state === "missing" || state === "error") {
        addExternal(row);
      }
    }
  }

  async function runLocal(q, id) {
    localController = new AbortController();
    const controller = localController;
    model.localState = "loading";
    try {
      const response = await fetcher(`/api/search?q=${encodeURIComponent(q)}&external=false&catalog=true`, { signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      if (id !== seq) return;
      model.local = payload.catalog?.results || [];
      model.localState = "ready";
    } catch (error) {
      if (error.name === "AbortError" || id !== seq) return;
      model.local = []; model.localState = "error";
      model.warning = "No pudimos actualizar tu colección.";
    }
    render();
  }

  function flattenExternal(payload) {
    if (Array.isArray(payload.results)) return payload.results;
    return Object.values(payload.sources || {}).flatMap((entry) => entry?.results || []);
  }

  async function runExternal(q, id) {
    externalController = new AbortController();
    const controller = externalController;
    model.externalState = "loading";
    try {
      const response = await fetcher(`/api/search?q=${encodeURIComponent(q)}&external=true&catalog=false&membership=true`, { signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      if (id !== seq) return;
      const all = flattenExternal(payload);
      model.externalTotal = all.length;
      model.external = topExternal(all);
      model.externalState = "ready";
      const sources = Object.values(payload.external?.sources || {});
      model.warning = !all.length && sources.some((s) => s?.status === "error" || s?.status === "cooldown")
        ? "Una fuente externa no respondió. Tu colección sigue disponible." : "";
    } catch (error) {
      if (error.name === "AbortError" || id !== seq) return;
      model.external = []; model.externalTotal = 0; model.externalState = "error";
      model.warning = "Una fuente externa no respondió. Tu colección sigue disponible.";
    }
    render();
  }

  function onInput() {
    abortAll();
    const q = query();
    const id = ++seq;
    open = true; active = -1;
    model.query = q; model.warning = "";
    model.local = []; model.external = []; model.externalTotal = 0;
    model.localState = model.externalState = "idle";
    status.textContent = "";
    render();
    onPreview(null);
    if (!q) return;
    localTimer = setTimeout(() => runLocal(q, id), localDelay);
    if (q.length >= EXTERNAL_MIN_CHARS || detectLinkSource(q)) {
      externalTimer = setTimeout(() => runExternal(q, id), externalDelay);
    }
  }

  input.addEventListener("input", onInput);
  input.addEventListener("focus", () => { if (!open) { open = true; render(); } });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) { open = true; render(); }
      if (!rows.length) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive(active < 0 ? (step > 0 ? 0 : rows.length - 1) : (active + step + rows.length) % rows.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (active >= 0 && rows[active]) activate(rows[active]);
      else expand();
    } else if (event.key === "Escape") {
      if (open || query()) { event.preventDefault(); close(true); }
    }
  });
  panel.addEventListener("mousedown", (event) => event.preventDefault());
  panel.addEventListener("click", (event) => {
    const removeBtn = event.target.closest?.("[data-remove]");
    if (removeBtn) { recents.remove(removeBtn.dataset.remove); render(); return; }
    if (event.target.closest?.("[data-clear-all]")) { recents.clear(); render(); return; }
    const rowEl = event.target.closest?.("[data-index]");
    if (rowEl) activate(rows[Number(rowEl.dataset.index)]);
  });
  root.querySelector("[data-close]").addEventListener("click", () => close(true));
  container.addEventListener("focusout", (event) => {
    if (event.relatedTarget && container.contains(event.relatedTarget)) return;
    if (open) { open = false; active = -1; render(); }
  });

  return {
    input,
    focus() { input.focus(); },
    close: () => close(true),
    setEmptyCatalog(value) {
      const next = Boolean(value);
      if (next === emptyCatalog) return;
      emptyCatalog = next;
      label.textContent = labelText();
      if (open) render();
    },
    setSuggestions(list) { suggestionList = Array.isArray(list) ? list : []; if (open) render(); },
    destroy() { abortAll(); container.innerHTML = ""; }
  };
}
