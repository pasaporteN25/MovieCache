#!/usr/bin/env python3
"""
Build a self-contained HTML viewer from the merged catalog JSON.

Usage:
    python scripts/build_viewer.py catalog.json --html catalog-view.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a browsable HTML view from catalog.json.")
    parser.add_argument("catalog", type=Path, help="Merged catalog JSON.")
    parser.add_argument("--html", type=Path, default=Path("catalog-view.html"), help="Output HTML path.")
    args = parser.parse_args()

    items = read_catalog(args.catalog)
    args.html.write_text(render_html(items), encoding="utf-8")
    print(f"Wrote {args.html} with {len(items)} items.")
    return 0


def read_catalog(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("items", []) if isinstance(raw, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def render_html(items: list[dict[str, object]]) -> str:
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Movie Inbox</title>
    <style>
      :root {{
        color-scheme: light;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #20242a;
        background: #f4f1ea;
      }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; }}
      main {{ margin: 0 auto; max-width: 1240px; padding: 24px; }}
      header {{
        align-items: end;
        display: grid;
        gap: 16px;
        grid-template-columns: minmax(220px, 1fr) minmax(320px, 1.3fr);
        margin-bottom: 18px;
      }}
      h1 {{ font-size: 28px; line-height: 1.1; margin: 0; }}
      .stats {{ color: #5d6470; font-size: 13px; margin-top: 6px; }}
      .toolbar {{
        display: grid;
        gap: 8px;
        grid-template-columns: minmax(180px, 1fr) 140px 140px 140px;
      }}
      input, select {{
        background: #fffdf8;
        border: 1px solid #c7c0b4;
        border-radius: 6px;
        color: #20242a;
        font: inherit;
        min-height: 38px;
        padding: 8px 10px;
        width: 100%;
      }}
      .grid {{
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      }}
      .card {{
        background: #fffdf8;
        border: 1px solid #d4cec3;
        border-radius: 8px;
        display: grid;
        gap: 10px;
        min-height: 180px;
        overflow: hidden;
      }}
      .image {{
        background: #e1ddd4;
        height: 150px;
        object-fit: cover;
        width: 100%;
      }}
      .body {{ display: grid; gap: 8px; padding: 12px; }}
      .title {{
        align-items: start;
        display: flex;
        gap: 8px;
        justify-content: space-between;
      }}
      h2 {{ font-size: 16px; line-height: 1.25; margin: 0; }}
      .pill {{
        border: 1px solid #c7c0b4;
        border-radius: 999px;
        color: #48505a;
        flex: 0 0 auto;
        font-size: 11px;
        padding: 3px 7px;
      }}
      .meta {{ color: #68707b; display: flex; flex-wrap: wrap; gap: 6px; font-size: 12px; }}
      .summary {{
        color: #32373e;
        display: -webkit-box;
        font-size: 13px;
        line-height: 1.4;
        margin: 0;
        overflow: hidden;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 4;
      }}
      .links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
      a {{ color: #2e686c; font-size: 13px; font-weight: 700; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
      .empty {{
        border: 1px dashed #bfb7aa;
        border-radius: 8px;
        color: #666d76;
        display: none;
        padding: 28px;
        text-align: center;
      }}
      @media (max-width: 760px) {{
        main {{ padding: 16px; }}
        header {{ grid-template-columns: 1fr; }}
        .toolbar {{ grid-template-columns: 1fr 1fr; }}
      }}
      @media (max-width: 480px) {{
        .toolbar {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>Movie Inbox</h1>
          <div class="stats" id="stats"></div>
        </div>
        <div class="toolbar">
          <input id="query" type="search" placeholder="Buscar titulo, nota, tag...">
          <select id="status"></select>
          <select id="kind"></select>
          <select id="source"></select>
        </div>
      </header>
      <section class="grid" id="grid"></section>
      <p class="empty" id="empty">No hay resultados para esos filtros.</p>
    </main>
    <script>
      const items = {data};
      const fields = {{
        query: document.querySelector("#query"),
        status: document.querySelector("#status"),
        kind: document.querySelector("#kind"),
        source: document.querySelector("#source"),
        grid: document.querySelector("#grid"),
        stats: document.querySelector("#stats"),
        empty: document.querySelector("#empty")
      }};

      setupSelect(fields.status, "Estado", items.map((item) => item.status));
      setupSelect(fields.kind, "Tipo", items.map((item) => item.kind));
      setupSelect(fields.source, "Fuente", items.map((item) => item.source));
      Object.values(fields).forEach((field) => {{
        if (field && (field.tagName === "INPUT" || field.tagName === "SELECT")) {{
          field.addEventListener("input", render);
        }}
      }});
      render();

      function setupSelect(select, label, values) {{
        const unique = [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
        select.innerHTML = `<option value="">${{label}}</option>` + unique.map((value) => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`).join("");
      }}

      function render() {{
        const query = fields.query.value.trim().toLowerCase();
        const filtered = items.filter((item) => {{
          const haystack = [
            item.title,
            item.local_name,
            item.local_path,
            item.year,
            item.description,
            item.wikipedia_extract,
            item.notes,
            Array.isArray(item.tags) ? item.tags.join(" ") : item.tags
          ].join(" ").toLowerCase();
          return (!query || haystack.includes(query))
            && (!fields.status.value || item.status === fields.status.value)
            && (!fields.kind.value || item.kind === fields.kind.value)
            && (!fields.source.value || item.source === fields.source.value);
        }});

        fields.stats.textContent = `${{filtered.length}} visibles de ${{items.length}} items`;
        fields.empty.style.display = filtered.length ? "none" : "block";
        fields.grid.innerHTML = filtered.map(card).join("");
      }}

      function card(item) {{
        const summary = item.wikipedia_extract || item.description || item.notes || "";
        const image = item.page_image ? `<img class="image" src="${{escapeAttr(item.page_image)}}" alt="">` : "";
        const tags = Array.isArray(item.tags) ? item.tags : String(item.tags || "").split(",").map((tag) => tag.trim()).filter(Boolean);
        const tagText = tags.length ? tags.join(", ") : "";
        return `<article class="card">
          ${{image}}
          <div class="body">
            <div class="title">
              <h2>${{escapeHtml(item.title || "Sin titulo")}}</h2>
              <span class="pill">${{escapeHtml(item.status || "sin estado")}}</span>
            </div>
            <div class="meta">
              ${{meta(item.kind)}}${{meta(item.year)}}${{meta(item.source)}}${{meta(`catalogo: ${{isInCatalog(item.en_catalogo) ? "si" : "no"}}`)}}${{meta(tagText)}}
            </div>
            ${{summary ? `<p class="summary">${{escapeHtml(summary)}}</p>` : ""}}
            <div class="links">
              ${{item.url ? `<a href="${{escapeAttr(item.url)}}" target="_blank" rel="noreferrer">Abrir link</a>` : ""}}
              ${{item.wikidata_id ? `<a href="https://www.wikidata.org/wiki/${{escapeAttr(item.wikidata_id)}}" target="_blank" rel="noreferrer">Wikidata</a>` : ""}}
            </div>
          </div>
        </article>`;
      }}

      function meta(value) {{
        return value ? `<span>${{escapeHtml(value)}}</span>` : "";
      }}

      function isInCatalog(value) {{
        return value === true || value === "si" || value === "sí" || value === "true";
      }}

      function escapeHtml(value) {{
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({{
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;"
        }}[char]));
      }}

      function escapeAttr(value) {{
        return escapeHtml(value).replace(/`/g, "&#096;");
      }}
    </script>
  </body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
