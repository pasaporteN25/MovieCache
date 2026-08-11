const API_TOKEN = document.querySelector('[name="movie-inbox-token"]').content;
const form = document.querySelector("#loginForm");
const username = document.querySelector("#loginUsername");
const password = document.querySelector("#loginPassword");
const showPassword = document.querySelector("#showPassword");
const feedback = document.querySelector("#loginFeedback");
const submit = document.querySelector("#loginSubmit");
const memberAlias = document.querySelector("#loginMemberAlias");

username.addEventListener("input", () => {
  memberAlias.textContent = username.value.trim() || "Sin identificar";
});

showPassword.addEventListener("change", () => {
  password.type = showPassword.checked ? "text" : "password";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setFeedback("");
  submit.disabled = true;
  submit.setAttribute("aria-busy", "true");
  submit.textContent = "Verificando\u2026";
  try {
    const response = await fetch("/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Movie-Inbox-Token": API_TOKEN
      },
      body: JSON.stringify({
        username: username.value,
        password: password.value
      })
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      setFeedback(loginErrorMessage(payload.reason, response));
      password.select();
      return;
    }
    window.location.replace(payload.user?.must_change_password ? "/password-change" : "/");
  } catch {
    setFeedback("No pudimos contactar la instancia. Revis\u00e1 el servidor y volv\u00e9 a intentar.");
  } finally {
    submit.disabled = false;
    submit.removeAttribute("aria-busy");
    submit.textContent = "Entrar";
  }
});

if (new URLSearchParams(window.location.search).get("expired") === "1") {
  setFeedback("Tu sesi\u00f3n termin\u00f3. Ingres\u00e1 nuevamente para continuar.");
}

function loginErrorMessage(reason, response) {
  if (reason === "invalid_credentials") return "Usuario o contrase\u00f1a incorrectos.";
  if (reason === "too_many_attempts") {
    const seconds = Number(response.headers.get("Retry-After") || 60);
    const minutes = Math.max(1, Math.ceil(seconds / 60));
    return `Demasiados intentos. Prob\u00e1 nuevamente en ${minutes} min.`;
  }
  if (reason === "identity_store_unavailable") {
    return "La base de cuentas no est\u00e1 disponible. Revis\u00e1 el servidor antes de reintentar.";
  }
  return "No pudimos iniciar la sesi\u00f3n. Volv\u00e9 a intentar.";
}

function setFeedback(message) {
  feedback.textContent = message;
  feedback.hidden = !message;
}
