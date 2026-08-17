      import { fields } from "./fields.js";

      export function curationScopeStates() {
        return { physical: false, identity: false, catalog: true };
      }

      export function scannerScopeStates(candidates) {
        if (candidates === null) {
          return { physical: false, identity: false, catalog: false };
        }
        return {
          physical: true,
          identity: Array.isArray(candidates) && candidates.length > 0,
          catalog: true
        };
      }

      export function scannerActionReceipt(action, payload) {
        if (action === "ignore") {
          return { physical: true, identity: false, catalog: false };
        }
        const catalogAction = String(payload?.catalog_action || "");
        if (catalogAction && catalogAction !== "existing") {
          return { physical: true, identity: true, catalog: true };
        }
        return { physical: true, identity: true, catalog: false };
      }

      export function summarizeScopeStates(states) {
        if (states.catalog) return "Tu catálogo cambió.";
        if (states.identity) return "Tu catálogo no cambió.";
        if (states.physical) return "Tu catálogo y la identidad compartida no cambiaron.";
        return "Nada cambió.";
      }

      const SCOPE_LABELS = {
        physical: "el archivo físico",
        identity: "la identidad compartida",
        catalog: "tu catálogo"
      };

      export function describeScopeStates(states) {
        const active = ["physical", "identity", "catalog"].filter((key) => states[key]).map((key) => SCOPE_LABELS[key]);
        return active.length
          ? `Esta decisión puede afectar: ${active.join(", ")}.`
          : "Todavía no hay una decisión seleccionada.";
      }

      export function renderScopeStrip(states) {
        if (!fields.scopeStrip) return;
        for (const chip of fields.scopeStrip.querySelectorAll("[data-scope-chip]")) {
          const key = chip.getAttribute("data-scope-chip");
          chip.dataset.active = states[key] ? "true" : "false";
        }
        if (fields.scopeStripSummary) {
          fields.scopeStripSummary.textContent = describeScopeStates(states);
        }
      }
