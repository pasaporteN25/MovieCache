const DEFAULT_SETTINGS = {
  autoExportEnabled: false,
  autoExportDays: 7
};

const fields = {
  title: document.querySelector("#title"),
  url: document.querySelector("#url"),
  kind: document.querySelector("#kind"),
  status: document.querySelector("#status"),
  tags: document.querySelector("#tags"),
  notes: document.querySelector("#notes"),
  count: document.querySelector("#count"),
  autoExportEnabled: document.querySelector("#autoExportEnabled"),
  autoExportDays: document.querySelector("#autoExportDays")
};

document.querySelector("#save").addEventListener("click", saveCurrent);
document.querySelector("#exportCsv").addEventListener("click", () => exportItems("csv"));
document.querySelector("#exportJson").addEventListener("click", () => exportItems("json"));
document.querySelector("#clear").addEventListener("click", clearItems);
fields.autoExportEnabled.addEventListener("change", saveSettings);
fields.autoExportDays.addEventListener("change", saveSettings);

init();

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  fields.title.value = cleanTitle(tab?.title || "");
  fields.url.value = tab?.url || "";

  const { settings = DEFAULT_SETTINGS, items = [] } = await chrome.storage.local.get(["settings", "items"]);
  const normalizedItems = items.map(normalizeStoredItem);
  await chrome.storage.local.set({ items: normalizedItems });
  fields.count.textContent = String(normalizedItems.length);
  fields.autoExportEnabled.checked = Boolean(settings.autoExportEnabled);
  fields.autoExportDays.value = settings.autoExportDays || 7;
}

async function saveCurrent() {
  const addedAt = new Date().toISOString();
  const url = fields.url.value.trim();
  const source = sourceName(url);
  const item = {
    id: stableId(url),
    title: fields.title.value.trim(),
    kind: fields.kind.value,
    status: fields.status.value,
    watched_at: fields.status.value === "watched" ? todayLocalDate() : "",
    rating: 0,
    url,
    source,
    original_title: "",
    spanish_title: "",
    english_title: "",
    alternative_titles: [],
    year: "",
    description: "",
    wikipedia_url: source === "wikipedia" ? url : "",
    imdb_url: source === "imdb" ? url : "",
    filmaffinity_url: source === "filmaffinity" ? url : "",
    wikipedia_title: "",
    wikidata_id: "",
    genres: [],
    directors: [],
    writers: [],
    cast: [],
    page_image: "",
    wikipedia_extract: "",
    en_catalogo: false,
    local_files: [],
    local_name: "",
    local_path: "",
    tags: fields.tags.value.split(",").map((tag) => tag.trim()).filter(Boolean),
    notes: fields.notes.value.trim(),
    review: "",
    metadata_sources: {
      title: { source, url, updated_at: addedAt, inferred: false },
      kind: { source: "manual", url: "", updated_at: addedAt, inferred: false }
    },
    locked_fields: ["kind"],
    added_at: addedAt
  };

  if (!item.url) return;

  const { items = [] } = await chrome.storage.local.get("items");
  const next = [item, ...items.filter((existing) => existing.url !== item.url)];
  await chrome.storage.local.set({ items: next });
  fields.count.textContent = String(next.length);
}

async function exportItems(format) {
  const { items = [] } = await chrome.storage.local.get("items");
  const normalizedItems = items.map(normalizeStoredItem);
  const text = format === "json" ? JSON.stringify({ schema_version: 3, items: normalizedItems }, null, 2) : toCsv(normalizedItems);
  const type = format === "json" ? "application/json" : "text/csv";
  await downloadText(text, filename("movie-inbox", format), type);
}

async function clearItems() {
  const confirmed = confirm("Vaciar todos los items guardados?");
  if (!confirmed) return;
  await chrome.storage.local.set({ items: [] });
  fields.count.textContent = "0";
}

async function saveSettings() {
  const settings = {
    autoExportEnabled: fields.autoExportEnabled.checked,
    autoExportDays: Math.max(1, Number(fields.autoExportDays.value) || 7)
  };
  await chrome.storage.local.set({ settings });
  chrome.runtime.sendMessage({ type: "refresh-alarm" });
}

async function downloadText(text, name, mimeType) {
  const url = URL.createObjectURL(new Blob([text], { type: `${mimeType};charset=utf-8` }));
  await chrome.downloads.download({ url, filename: name, saveAs: true });
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

function toCsv(items) {
  const headers = [
    "id",
    "url",
    "source",
    "title",
    "original_title",
    "spanish_title",
    "english_title",
    "alternative_titles",
    "kind",
    "status",
    "watched_at",
    "rating",
    "year",
    "description",
    "wikipedia_url",
    "imdb_url",
    "filmaffinity_url",
    "wikipedia_title",
    "wikidata_id",
    "genres",
    "directors",
    "writers",
    "cast",
    "page_image",
    "wikipedia_extract",
    "en_catalogo",
    "local_files",
    "local_name",
    "local_path",
    "tags",
    "notes",
    "review",
    "metadata_sources",
    "locked_fields",
    "added_at"
  ];
  const rows = items.map((item) => headers.map((key) => csvCell(cellValue(item, key))).join(","));
  return [headers.join(","), ...rows].join("\n");
}

function cellValue(item, key) {
  const value = key === "added_at" ? item.added_at || item.addedAt : item[key];
  if (["local_files", "metadata_sources"].includes(key)) return JSON.stringify(value || (key === "local_files" ? [] : {}));
  return Array.isArray(value) ? value.join(", ") : value ?? "";
}

function csvCell(value) {
  const text = String(value).replaceAll('"', '""');
  return /[",\n]/.test(text) ? `"${text}"` : text;
}

function filename(prefix, ext) {
  const stamp = new Date().toISOString().slice(0, 10);
  return `${prefix}-${stamp}.${ext}`;
}

function todayLocalDate() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function sourceName(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (host.includes("wikipedia.org")) return "wikipedia";
    if (host.includes("imdb.com")) return "imdb";
    if (host.includes("filmaffinity.com")) return "filmaffinity";
    if (host.includes("letterboxd.com")) return "letterboxd";
    return host;
  } catch {
    return "";
  }
}

function cleanTitle(title) {
  return title
    .replace(/\s+-\s+Wikipedia$/i, "")
    .replace(/\s+-\s+IMDb$/i, "")
    .trim();
}

function stableId(value) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function normalizeStoredItem(item) {
  const kindMap = { movie: "pelicula", film: "pelicula", series: "serie", episode: "serie", other: "pelicula" };
  const kind = kindMap[item.kind] || item.kind;
  return {
    ...item,
    kind: ["pelicula", "serie", "anime", "documental"].includes(kind) ? kind : "pelicula",
    status: item.status === "watched" ? "watched" : "to_watch",
    local_files: Array.isArray(item.local_files) ? item.local_files : [],
    metadata_sources: item.metadata_sources && typeof item.metadata_sources === "object" ? item.metadata_sources : {},
    locked_fields: Array.isArray(item.locked_fields) ? item.locked_fields : []
  };
}
