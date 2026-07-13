const DEFAULT_SETTINGS = {
  autoExportEnabled: false,
  autoExportDays: 7
};

chrome.runtime.onInstalled.addListener(async () => {
  const { settings, items = [] } = await chrome.storage.local.get(["settings", "items"]);
  if (!settings) {
    await chrome.storage.local.set({ settings: DEFAULT_SETTINGS });
  }
  await chrome.storage.local.set({ items: items.map(normalizeStoredItem) });
  await refreshAlarm();
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "refresh-alarm") {
    refreshAlarm().then(() => sendResponse({ ok: true }));
    return true;
  }
  return false;
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== "movie-inbox-auto-export") return;
  const { settings = DEFAULT_SETTINGS } = await chrome.storage.local.get("settings");
  if (!settings.autoExportEnabled) return;
  const { items = [] } = await chrome.storage.local.get("items");
  await downloadText(toCsv(items.map(normalizeStoredItem)), filename("movie-inbox", "csv"));
});

async function refreshAlarm() {
  await chrome.alarms.clear("movie-inbox-auto-export");
  const { settings = DEFAULT_SETTINGS } = await chrome.storage.local.get("settings");
  if (!settings.autoExportEnabled) return;

  const days = Math.max(1, Number(settings.autoExportDays) || 7);
  chrome.alarms.create("movie-inbox-auto-export", {
    periodInMinutes: days * 24 * 60
  });
}

async function downloadText(text, name) {
  const url = `data:text/csv;charset=utf-8,${encodeURIComponent(text)}`;
  await chrome.downloads.download({ url, filename: name, saveAs: false });
}

function filename(prefix, ext) {
  const stamp = new Date().toISOString().slice(0, 10);
  return `${prefix}-${stamp}.${ext}`;
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
