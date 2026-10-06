import { displayTitle, escapeAttr, escapeHtml } from "../core/format.js";
import { openInternalMergeComparator } from "../core/merge.js";
import { items } from "../core/state.js";

      // [X12 D] Merging where the duplicate shows up: a search for a title lists
      // both entries, so they can be chosen and merged right there, with the
      // same reviewed comparator curation uses. Nothing merges without it.
      export const mergeSelection = new Set();

      const MAX_MEMBERS = 50;

      export function isSelectedForMerge(id) {
        return mergeSelection.has(String(id || ""));
      }

      export function toggleMergeSelection(id) {
        const key = String(id || "");
        if (!key) return;
        if (mergeSelection.has(key)) mergeSelection.delete(key);
        else if (mergeSelection.size < MAX_MEMBERS) mergeSelection.add(key);
      }

      export function clearMergeSelection() {
        mergeSelection.clear();
      }

      // Entries merged or deleted elsewhere leave the selection on their own.
      export function pruneMergeSelection() {
        const known = new Set(items.map((item) => item.id));
        for (const id of [...mergeSelection]) if (!known.has(id)) mergeSelection.delete(id);
      }

      export function mergeSelectButton(item) {
        const selected = isSelectedForMerge(item.id);
        return `<button class="action-secondary merge-select" type="button" data-click="toggle-merge-select" data-id="${escapeAttr(item.id)}" aria-pressed="${selected}">${selected ? "✓ Para unir" : "Seleccionar para unir"}</button>`;
      }

      export function mergeSelectionBar() {
        pruneMergeSelection();
        const count = mergeSelection.size;
        if (!count) return "";
        const titles = [...mergeSelection]
          .map((id) => displayTitle(items.find((item) => item.id === id) || {}))
          .filter(Boolean);
        return `<div class="merge-selection-bar" role="region" aria-label="Obras elegidas para unir">
          <span><strong>${count} ${count === 1 ? "obra elegida" : "obras elegidas"}</strong>${titles.length ? ` · ${escapeHtml(titles.slice(0, 3).join(", "))}${titles.length > 3 ? "…" : ""}` : ""}</span>
          <button class="action-primary" type="button" data-click="merge-selected" ${count < 2 ? "disabled" : ""}>${count < 2 ? "Elegí otra para unir" : `Comparar y unir ${count}`}</button>
          <button class="quiet-action" type="button" data-click="clear-merge-selection">Cancelar</button>
        </div>`;
      }

      // The entries in view that curation already thinks are one work.
      export function visibleDuplicateGroups(visibleIds) {
        const visible = new Set(visibleIds);
        const seen = new Set();
        const groups = [];
        for (const id of visibleIds) {
          if (seen.has(id)) continue;
          const item = items.find((entry) => entry.id === id);
          const others = (item?._duplicate_ids || []).filter((other) => visible.has(other) && !seen.has(other));
          if (!others.length) continue;
          const group = [id, ...others];
          group.forEach((member) => seen.add(member));
          groups.push({ ids: group, level: item._duplicate_level || "possible" });
        }
        return groups;
      }

      export function duplicateHint(visibleIds) {
        return visibleDuplicateGroups(visibleIds).map(({ ids, level }) => {
          const names = ids.map((id) => displayTitle(items.find((item) => item.id === id) || {}));
          const lead = level === "same" ? "Son la misma obra" : "Parecen la misma obra";
          return `<p class="merge-hint" role="status"><span>${lead}: ${escapeHtml([...new Set(names)].join(" / "))} (${ids.length} fichas).</span>
            <button class="action-secondary" type="button" data-click="merge-ids" data-ids="${escapeAttr(ids.join(","))}">Compararlas</button></p>`;
        }).join("");
      }

      export async function mergeItems(ids) {
        const members = ids
          .map((id) => items.find((item) => item.id === id))
          .filter(Boolean)
          .map((item) => ({ ref: item._curation_ref || "", id: item.id, source_file: item._source_file || "" }));
        if (members.length < 2) return;
        await openInternalMergeComparator({ members });
      }

      export async function mergeSelected() {
        await mergeItems([...mergeSelection]);
      }
