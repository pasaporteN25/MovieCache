// Búsquedas recientes de Inicio (C2). Personales: viven sólo en localStorage del
// navegador y nunca se mandan al servidor. Todo el acceso al almacenamiento va en
// try/catch; si falla, la interfaz sigue funcionando sin recientes.
export const RECENT_SEARCH_LIMIT = 5;
export const RECENT_SEARCH_PREFIX = "movie-inbox:recent-searches:";

export function recentSearchKey(username) {
  return `${RECENT_SEARCH_PREFIX}${username || ""}`;
}

export function normalizeRecent(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function defaultStorage() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

export function createRecentSearches(username, storage = undefined) {
  const key = recentSearchKey(username);
  const backend = () => (storage === undefined ? defaultStorage() : storage);

  function read() {
    try {
      const raw = backend()?.getItem(key);
      const parsed = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(parsed)) return [];
      const seen = new Set();
      const out = [];
      for (const entry of parsed) {
        const text = typeof entry === "string" ? entry.trim() : "";
        const norm = normalizeRecent(text);
        if (!norm || seen.has(norm)) continue;
        seen.add(norm);
        out.push(text);
      }
      return out.slice(0, RECENT_SEARCH_LIMIT);
    } catch {
      return [];
    }
  }

  function write(values) {
    try {
      backend()?.setItem(key, JSON.stringify(values.slice(0, RECENT_SEARCH_LIMIT)));
    } catch {
      /* sin almacenamiento: la interfaz sigue sin recientes */
    }
    return values.slice(0, RECENT_SEARCH_LIMIT);
  }

  return {
    key,
    list: read,
    add(query) {
      const text = String(query ?? "").replace(/\s+/g, " ").trim();
      const norm = normalizeRecent(text);
      if (!norm) return read();
      const rest = read().filter((entry) => normalizeRecent(entry) !== norm);
      return write([text, ...rest]);
    },
    remove(query) {
      const norm = normalizeRecent(query);
      return write(read().filter((entry) => normalizeRecent(entry) !== norm));
    },
    clear() {
      try {
        backend()?.removeItem(key);
      } catch {
        /* ver arriba */
      }
      return [];
    }
  };
}
