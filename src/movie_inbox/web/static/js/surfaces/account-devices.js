import { apiFetch } from "../core/http.js";

export function initializeDevices() {
  const get = (id) => document.getElementById(id);
  const dialog = get("devicesDialog");
  let generation = 0;
  let timer;
  let selected;
  const feedback = (message) => { get("devicesFeedback").textContent = message; };
  const date = (value) => new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  function clearQr() {
    clearInterval(timer);
    get("deviceQr").removeAttribute("src");
    get("deviceQrPanel").hidden = true;
    get("deviceQrAccount").textContent = "";
    get("deviceQrExpiry").textContent = "";
  }
  function cancelRevoke() {
    selected = null;
    get("revokeDeviceConfirm").hidden = true;
  }
  async function loadDevices() {
    const request = generation;
    get("refreshDevices").disabled = true;
    try {
      const response = await apiFetch("/api/device-sessions");
      if (!response.ok) throw new Error();
      const payload = await response.json();
      if (request !== generation || !dialog.open) return;
      const list = get("devicesList");
      list.replaceChildren();
      for (const device of payload.devices) {
        const row = document.createElement("li");
        const info = document.createElement("div");
        const name = document.createElement("strong");
        name.textContent = device.device_name;
        const seen = document.createElement("small");
        const expired = new Date(device.expires_at).getTime() <= Date.now();
        seen.textContent = `${expired ? "Necesita reconectarse · " : ""}Última actividad: ${date(device.last_seen_at)}`;
        info.append(name, seen);
        const revoke = document.createElement("button");
        revoke.type = "button";
        revoke.className = "quiet-action";
        revoke.textContent = "Revocar";
        revoke.setAttribute("aria-label", `Revocar acceso de ${device.device_name}`);
        revoke.addEventListener("click", () => {
          selected = device;
          get("revokeDevicePrompt").textContent = `¿Revocar el acceso de ${device.device_name}? Necesitará otro QR para volver a sincronizar.`;
          get("revokeDeviceConfirm").hidden = false;
          get("cancelDeviceRevoke").focus();
        });
        row.append(info, revoke);
        list.append(row);
      }
      if (!payload.devices.length) {
        const row = document.createElement("li");
        row.textContent = "Todavía no conectaste ningún teléfono.";
        list.append(row);
      }
    } catch {
      if (request === generation && dialog.open) feedback("No pudimos cargar tus dispositivos. Probá Actualizar.");
    } finally {
      get("refreshDevices").disabled = false;
    }
  }
  get("devicesButton").addEventListener("click", () => {
    get("systemMenu").open = false;
    generation++;
    feedback("");
    cancelRevoke();
    clearQr();
    dialog.showModal();
    loadDevices();
  });
  get("closeDevices").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { generation++; clearQr(); cancelRevoke(); });
  get("refreshDevices").addEventListener("click", () => { feedback(""); loadDevices(); });
  get("generateDeviceQr").addEventListener("click", async () => {
    const request = generation;
    const button = get("generateDeviceQr");
    button.disabled = true;
    clearQr();
    feedback("Preparando QR…");
    try {
      const response = await apiFetch("/api/device-pairing", { method: "POST" });
      const payload = await response.json();
      if (request !== generation || !dialog.open) return;
      if (!response.ok) {
        feedback(payload.reason === "pairing_not_configured"
          ? "Para conectar Android, configurá HTTPS y la dirección de la instancia. Después generá otro QR."
          : "No pudimos generar el QR. Volvé a intentar.");
        return;
      }
      if (!/^data:image\/(png|svg\+xml);/.test(payload.qr_image || "")) {
        feedback("No pudimos dibujar el QR. Volvé a generarlo; si continúa, revisá la instalación del servidor.");
        return;
      }
      get("deviceQr").src = payload.qr_image;
      get("deviceQrAccount").textContent = `${payload.payload.account} · ${payload.payload.origin}`;
      get("deviceQrPanel").hidden = false;
      button.textContent = "Generar otro QR";
      const expires = Number(payload.expires_at) * 1000;
      const tick = () => {
        if (Date.now() >= expires) {
          clearQr();
          feedback("Este QR venció. Generá otro para conectar el teléfono.");
        } else get("deviceQrExpiry").textContent = `Válido hasta las ${new Date(expires).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}.`;
      };
      feedback("");
      tick();
      if (!get("deviceQrPanel").hidden) timer = setInterval(tick, 1000);
    } catch {
      if (request === generation && dialog.open) feedback("No pudimos generar el QR. Revisá la conexión y volvé a intentar.");
    } finally { button.disabled = false; }
  });
  get("cancelDeviceRevoke").addEventListener("click", cancelRevoke);
  get("confirmDeviceRevoke").addEventListener("click", async () => {
    if (!selected) return;
    const device = selected;
    const request = generation;
    get("confirmDeviceRevoke").disabled = true;
    try {
      const response = await apiFetch(`/api/device-sessions/${encodeURIComponent(device.id)}`, { method: "DELETE" });
      if (request !== generation || !dialog.open) return;
      if (!response.ok && response.status !== 404) throw new Error();
      cancelRevoke();
      feedback(`Acceso revocado: ${device.device_name}.`);
      await loadDevices();
    } catch {
      if (request === generation && dialog.open) feedback("No pudimos revocar el acceso. Volvé a intentar.");
    } finally { get("confirmDeviceRevoke").disabled = false; }
  });
}
