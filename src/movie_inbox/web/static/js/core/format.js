      export function setInlineFeedback(field, message, tone = "") {
        field.textContent = message;
        field.dataset.tone = tone;
        field.hidden = !message;
      }

      export function normalizeText(value) {
        return String(value || "")
          .toLowerCase()
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .replace(/\([^)]*\)/g, " ")
          .replace(/[^a-z0-9]+/g, " ")
          .trim();
      }

      export function meta(value) {
        return value ? `<span>${escapeHtml(value)}</span>` : "";
      }

      export function displayTitle(item) {
        const candidates = [
          item.spanish_title,
          item.title,
          item.original_title,
          item.english_title,
          item.wikipedia_title,
          ...asList(item.alternative_titles),
          item.local_name
        ].filter(Boolean);
        return candidates.find((value) => !isExternalIdTitle(value)) || candidates[0] || "";
      }

      export function isExternalIdTitle(value) {
        const text = String(value || "").trim();
        return /^(tt|nm)\d{7,9}$/i.test(text) || /^film\d+$/i.test(text);
      }

      export function titleSizeClass(value) {
        const text = String(value || "").trim();
        const length = [...text].length;
        const longestWord = Math.max(0, ...text.split(/\s+/).map((word) => [...word].length));
        if (longestWord > 18) return "title-ultra";
        if (longestWord > 12 || length > 72) return "title-xxlong";
        if (longestWord > 8 || length > 52) return "title-xlong";
        if (length > 34) return "title-long";
        if (length > 22) return "title-medium";
        return "title-short";
      }

      export function titleSubtitle(item) {
        const shown = normalizeText(displayTitle(item));
        const values = [
          ["Original", item.original_title],
          ["Ingles", item.english_title],
          ["Base", item.title]
        ];
        const row = values.find(([, value]) => value && normalizeText(value) !== shown);
        return row ? `${row[0]}: ${row[1]}` : "";
      }

      export function localFiles(item) {
        return Array.isArray(item?.local_files)
          ? item.local_files.filter((file) => file && typeof file === "object")
          : [];
      }

      export function localFilesText(item) {
        return localFiles(item)
          .map((file) => file.name || file.path || "")
          .filter(Boolean)
          .join(", ");
      }

      const SOURCE_LABELS = {
        wikipedia: "Wikipedia",
        imdb: "IMDb",
        filmaffinity: "FilmAffinity",
        jikan: "Jikan / MyAnimeList",
        anime_offline_database: "Anime DB offline",
        wikidata: "Wikidata",
        local_files: "Archivo local",
        txt: "Importación de texto",
        web: "Búsqueda web",
        manual_merge: "Fusión manual"
      };

      export function sourceLabel(source) {
        return SOURCE_LABELS[String(source || "").trim()] || "Sin fuente";
      }

      export function formatDateTime(value) {
        if (!value) return "Sin fecha";
        const date = new Date(value);
        return Number.isNaN(date.getTime())
          ? String(value)
          : date.toLocaleString("es-AR", { dateStyle: "medium", timeStyle: "short" });
      }

      export function asList(value) {
        if (Array.isArray(value)) return value.filter(Boolean);
        if (typeof value === "string") return value.split(",").map((entry) => entry.trim()).filter(Boolean);
        return [];
      }

      export function firstListValue(value) {
        return asList(value)[0] || "";
      }

      export function listText(value, limit) {
        const list = asList(value);
        if (!list.length) return "";
        const visible = list.slice(0, limit);
        const suffix = list.length > limit ? ` y ${list.length - limit} más` : "";
        return visible.join(", ") + suffix;
      }

      export function isInCatalog(value) {
        return value === true || value === "si" || value === "sí" || value === "true";
      }

      export function availabilityState(item) {
        const details = item?._availability || {};
        const manual = typeof details.manual === "boolean"
          ? details.manual
          : isInCatalog(item?.en_catalogo);
        const server = Boolean(details.server);
        const effective = typeof details.effective === "boolean"
          ? details.effective
          : Boolean(manual || server || isInCatalog(item?.en_catalogo));
        const fileCount = Math.max(0, Number(details.file_count || 0));
        const origin = server && manual
          ? "Inventario verificado y declaración manual"
          : server
            ? "Inventario verificado"
            : manual ? "Declaración manual" : "Sin procedencia asociada";
        return { effective, manual, server, fileCount, origin, details };
      }

      export function hasHost(url, host) {
        try {
          const hostname = new URL(url).hostname.toLowerCase().replace(/\.$/, "");
          return hostname === host || hostname.endsWith(`.${host}`);
        } catch {
          return false;
        }
      }

      export function hasExternalLink(item) {
        return hasHost(item?.url, "wikipedia.org")
          || hasHost(item?.url, "imdb.com")
          || hasHost(item?.url, "filmaffinity.com")
          || hasHost(item?.url, "myanimelist.net")
          || hasHost(item?.url, "themoviedb.org")
          || hasHost(item?.wikipedia_url, "wikipedia.org")
          || hasHost(item?.imdb_url, "imdb.com")
          || hasHost(item?.filmaffinity_url, "filmaffinity.com")
          || hasHost(item?.myanimelist_url, "myanimelist.net")
          || hasHost(item?.tmdb_url, "themoviedb.org");
      }

      export function normalizeRating(value) {
        const rating = Number.parseInt(value || 0, 10);
        if (Number.isNaN(rating)) return 0;
        return Math.max(0, Math.min(10, rating));
      }

      export function todayLocalDate() {
        const date = new Date();
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
        return date.toISOString().slice(0, 10);
      }

      export function localDateOffset(offset) {
        const date = new Date();
        date.setHours(12, 0, 0, 0);
        date.setDate(date.getDate() + Number(offset || 0));
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
        return date.toISOString().slice(0, 10);
      }

      export function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;"
        }[char]));
      }

      export function escapeAttr(value) {
        return escapeHtml(value).replace(/`/g, "&#096;");
      }
