import { fields } from "./fields.js";
import { escapeAttr, escapeHtml } from "./format.js";

const undoHandlers = {};

export function registerUndoHandler(source, handler) {
  undoHandlers[source] = handler;
}

export function setOperationFeedback(message, tone = "", operation = null, source = "curation") {
  fields.curationFeedback.innerHTML = operation?.can_undo
    ? `<span>${escapeHtml(message)}</span>
       <button class="text-action" type="button" data-operation-action="undo-operation"
         data-operation-source="${escapeAttr(source)}"
         data-operation-id="${escapeAttr(operation.id)}">Deshacer</button>`
    : escapeHtml(message);
  fields.curationFeedback.dataset.tone = tone;
}

export function handleOperationFeedbackClick(event) {
  const action = event.target.closest('[data-operation-action="undo-operation"]');
  if (!action) return false;
  const handler = undoHandlers[action.dataset.operationSource || ""];
  if (handler) handler(action.dataset.operationId || "");
  return true;
}
