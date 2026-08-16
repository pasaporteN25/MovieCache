export const API_TOKEN = document.querySelector('[name="movie-inbox-token"]').content;

      export async function apiFetch(url, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set("X-Movie-Inbox-Token", API_TOKEN);
        const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
        if (response.status === 401) {
          window.location.replace("/login?expired=1");
          throw new Error("authentication_required");
        }
        if (response.status === 403) {
          const payload = await response.clone().json().catch(() => ({}));
          if (payload.reason === "password_change_required") {
            window.location.replace("/password-change");
            throw new Error("password_change_required");
          }
        }
        return response;
      }

