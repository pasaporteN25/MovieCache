const API_TOKEN = document.querySelector('[name="movie-inbox-token"]').content;
const form = document.querySelector("#passwordChangeForm");
const currentPassword = document.querySelector("#currentPassword");
const newPassword = document.querySelector("#newPassword");
const confirmPassword = document.querySelector("#confirmPassword");
const showPasswords = document.querySelector("#showPasswords");
const feedback = document.querySelector("#passwordFeedback");
const submit = document.querySelector("#passwordSubmit");
const logout = document.querySelector("#passwordLogout");

showPasswords.addEventListener("change", () => {
  const type = showPasswords.checked ? "text" : "password";
  currentPassword.type = type;
  newPassword.type = type;
  confirmPassword.type = type;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (newPassword.value !== confirmPassword.value) {
    setFeedback("Las contrase\u00f1as nuevas no coinciden.");
    confirmPassword.focus();
    return;
  }
  setBusy(true);
  setFeedback("");
  try {
    const response = await jsonRequest("/auth/change-password", {
      current_password: currentPassword.value,
      new_password: newPassword.value,
      confirm_password: confirmPassword.value
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      setFeedback(passwordErrorMessage(payload.reason));
      return;
    }
    window.location.replace("/");
  } catch {
    setFeedback("No pudimos guardar la contrase\u00f1a. Revis\u00e1 el servidor y volv\u00e9 a intentar.");
  } finally {
    setBusy(false);
  }
});

logout.addEventListener("click", async () => {
  logout.disabled = true;
  try {
    await jsonRequest("/auth/logout", {});
  } finally {
    window.location.replace("/login");
  }
});

async function jsonRequest(url, body) {
  return fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Movie-Inbox-Token": API_TOKEN
    },
    body: JSON.stringify(body)
  });
}

function passwordErrorMessage(reason) {
  if (reason === "invalid_current_password") return "La contrase\u00f1a temporal no es correcta.";
  if (reason === "password_confirmation_mismatch") return "Las contrase\u00f1as nuevas no coinciden.";
  if (String(reason || "").includes("at least 12")) return "Us\u00e1 una contrase\u00f1a de al menos 12 caracteres.";
  if (String(reason || "").includes("different")) return "La nueva contrase\u00f1a debe ser diferente.";
  if (reason === "identity_store_unavailable") return "La base de cuentas no est\u00e1 disponible.";
  return "No pudimos actualizar la contrase\u00f1a.";
}

function setBusy(busy) {
  submit.disabled = busy;
  submit.toggleAttribute("aria-busy", busy);
  submit.textContent = busy ? "Guardando\u2026" : "Guardar y entrar";
}

function setFeedback(message) {
  feedback.textContent = message;
  feedback.hidden = !message;
}
