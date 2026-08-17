      import { availabilityState, escapeHtml } from "./format.js";

      export function availabilityCopy(item) {
        const state = availabilityState(item);
        const label = state.effective ? "Disponible" : "No disponible";
        return {
          ...state,
          label,
          text: state.effective ? `${label} · ${state.origin}` : label,
          tone: state.effective ? "good" : "muted"
        };
      }

      export function availabilityPill(item) {
        const copy = availabilityCopy(item);
        return `<span class="pill ${copy.tone}">${escapeHtml(copy.text)}</span>`;
      }
