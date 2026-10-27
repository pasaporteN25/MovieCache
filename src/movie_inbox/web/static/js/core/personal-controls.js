import { escapeAttr, escapeHtml } from "./format.js";

// [X12 E3/E4] The two controls of "Mi registro" that the browser used to draw:
// a date picker in Spanish (the native one spoke English, mm/dd/yyyy) and the
// rating as ten stars. Both keep writing the same hidden fields, `watched_at`
// as YYYY-MM-DD and `rating` as an integer 0-10, so saving, dirty tracking and
// the API are untouched.

const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
  "septiembre", "octubre", "noviembre", "diciembre"];
const WEEKDAYS = [["Lu", "lunes"], ["Ma", "martes"], ["Mi", "miércoles"], ["Ju", "jueves"],
  ["Vi", "viernes"], ["Sá", "sábado"], ["Do", "domingo"]];

const STAR_PATH = "M12 2.6l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.5l-5.9 3.1 1.2-6.5L2.5 9.5l6.6-.9z";
const icon = (path, className = "") => `<svg class="${className}" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${path}"/></svg>`;
const CHEVRON_LEFT = "M15 5l-7 7 7 7";
const CHEVRON_RIGHT = "M9 5l7 7-7 7";
const CALENDAR = "M7 3v3M17 3v3M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z";

// ---------------------------------------------------------------- dates

function pad(value) {
  return String(value).padStart(2, "0");
}

export function isoDate(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function parseIsoDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || "").trim());
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return isoDate(date) === match[0] ? date : null;
}

// What a person types: 30/9/2026, 30-09-2026, 30.09.26 or an ISO date.
export function parseTypedDate(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const iso = parseIsoDate(text);
  if (iso) return isoDate(iso);
  const match = /^(\d{1,2})[/.\-\s](\d{1,2})[/.\-\s](\d{2}|\d{4})$/.exec(text);
  if (!match) return null;
  const year = match[3].length === 2 ? 2000 + Number(match[3]) : Number(match[3]);
  const date = new Date(year, Number(match[2]) - 1, Number(match[1]));
  if (date.getDate() !== Number(match[1]) || date.getMonth() !== Number(match[2]) - 1) return null;
  return isoDate(date);
}

export function displayDate(iso) {
  const date = parseIsoDate(iso);
  return date ? `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}` : "";
}

export function longDate(iso) {
  const date = parseIsoDate(iso);
  return date ? `${date.getDate()} de ${MONTHS[date.getMonth()]} de ${date.getFullYear()}` : "";
}

function today() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

export function datePickerField(value) {
  const iso = parseIsoDate(value) ? value : "";
  return `<div class="vhs-date-field" data-date-field>
    <span class="vhs-field-label" id="watchedAtLabel">Fecha vista</span>
    <div class="vhs-date-control">
      <input class="vhs-date-text" type="text" inputmode="numeric" autocomplete="off" placeholder="dd/mm/aaaa"
        value="${escapeAttr(displayDate(iso))}" aria-labelledby="watchedAtLabel" aria-describedby="watchedAtHint" data-date-text>
      <button class="vhs-date-toggle" type="button" aria-haspopup="dialog" aria-expanded="false" aria-label="Elegir la fecha en el calendario" data-date-toggle>${icon(CALENDAR, "vhs-icon")}</button>
      <input type="hidden" name="watched_at" value="${escapeAttr(iso)}" data-personal-watched-at>
    </div>
    <small class="vhs-field-hint" id="watchedAtHint" data-date-hint>${iso ? escapeHtml(longDate(iso)) : "Sin fecha"}</small>
    <div class="vhs-calendar" role="dialog" aria-modal="false" aria-label="Calendario" hidden data-calendar></div>
  </div>`;
}

function calendarMarkup(view, selectedIso) {
  const year = view.getFullYear();
  const month = view.getMonth();
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7; // Monday first.
  const start = new Date(year, month, 1 - offset);
  const todayIso = isoDate(today());
  const days = Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
    const iso = isoDate(date);
    const future = date > today();
    const classes = [
      "vhs-day",
      date.getMonth() !== month ? "is-outside" : "",
      iso === todayIso ? "is-today" : "",
      iso === selectedIso ? "is-selected" : ""
    ].filter(Boolean).join(" ");
    const label = `${WEEKDAYS[(date.getDay() + 6) % 7][1]} ${longDate(iso)}${iso === todayIso ? ", hoy" : ""}${future ? ", todavía no llegó" : ""}`;
    return `<button type="button" class="${classes}" data-day="${iso}" tabindex="-1" aria-label="${escapeAttr(label)}"
      ${iso === selectedIso ? 'aria-pressed="true"' : ""} ${future ? 'aria-disabled="true"' : ""}>${date.getDate()}</button>`;
  });
  const rows = Array.from({ length: 6 }, (_, row) => `<div class="vhs-week" role="row">${days.slice(row * 7, row * 7 + 7).map((day) => `<span role="gridcell">${day}</span>`).join("")}</div>`);
  return `<header class="vhs-calendar-head">
      <button type="button" class="vhs-calendar-step" data-month-step="-1" aria-label="Mes anterior">${icon(CHEVRON_LEFT, "vhs-icon")}</button>
      <strong aria-live="polite">${MONTHS[month]} ${year}</strong>
      <button type="button" class="vhs-calendar-step" data-month-step="1" aria-label="Mes siguiente">${icon(CHEVRON_RIGHT, "vhs-icon")}</button>
    </header>
    <div class="vhs-calendar-grid" role="grid" aria-label="${escapeAttr(`${MONTHS[month]} ${year}`)}">
      <div class="vhs-week vhs-weekdays" role="row">${WEEKDAYS.map(([short, long]) => `<abbr role="columnheader" title="${long}">${short}</abbr>`).join("")}</div>
      ${rows.join("")}
    </div>
    <footer class="vhs-calendar-foot">
      <button type="button" data-date-shortcut="today">Hoy</button>
      <button type="button" data-date-shortcut="yesterday">Ayer</button>
      <button type="button" class="is-quiet" data-date-shortcut="clear">Limpiar</button>
    </footer>`;
}

function mountDateField(field) {
  const text = field.querySelector("[data-date-text]");
  const hidden = field.querySelector("[data-personal-watched-at]");
  const hint = field.querySelector("[data-date-hint]");
  const toggle = field.querySelector("[data-date-toggle]");
  const panel = field.querySelector("[data-calendar]");
  let view = parseIsoDate(hidden.value) || today();
  let focusIso = hidden.value || isoDate(today());

  const commit = (iso) => {
    if (hidden.value !== iso) {
      hidden.value = iso;
      hidden.dispatchEvent(new Event("input", { bubbles: true }));
    }
    text.value = displayDate(iso);
    text.removeAttribute("aria-invalid");
    hint.textContent = iso ? longDate(iso) : "Sin fecha";
    hint.classList.remove("is-error");
  };

  const render = () => {
    panel.innerHTML = calendarMarkup(view, hidden.value);
    const target = panel.querySelector(`[data-day="${focusIso}"]`) || panel.querySelector(".vhs-day:not(.is-outside)");
    if (target) target.tabIndex = 0;
    return target;
  };

  const open = () => {
    view = parseIsoDate(hidden.value) || today();
    focusIso = hidden.value || isoDate(today());
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    const target = render();
    // The editor scrolls: bring the whole calendar into view, footer included.
    panel.scrollIntoView({ block: "nearest" });
    target?.focus({ preventScroll: true });
  };

  const close = (returnFocus = true) => {
    if (panel.hidden) return;
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    if (returnFocus) toggle.focus();
  };

  const moveFocus = (date) => {
    focusIso = isoDate(date);
    if (date.getMonth() !== view.getMonth() || date.getFullYear() !== view.getFullYear()) {
      view = new Date(date.getFullYear(), date.getMonth(), 1);
    }
    render()?.focus();
  };

  toggle.addEventListener("click", () => (panel.hidden ? open() : close()));

  text.addEventListener("change", () => {
    const iso = parseTypedDate(text.value);
    if (iso === null || (iso && parseIsoDate(iso) > today())) {
      text.setAttribute("aria-invalid", "true");
      hint.textContent = iso === null ? "Escribila como 30/09/2026." : "Esa fecha todavía no llegó.";
      hint.classList.add("is-error");
      return;
    }
    commit(iso);
  });

  panel.addEventListener("click", (event) => {
    const step = event.target.closest("[data-month-step]");
    if (step) {
      view = new Date(view.getFullYear(), view.getMonth() + Number(step.dataset.monthStep), 1);
      focusIso = isoDate(new Date(view.getFullYear(), view.getMonth(), Math.min(parseIsoDate(focusIso)?.getDate() || 1, 28)));
      render();
      panel.querySelector(`[data-month-step="${step.dataset.monthStep}"]`)?.focus();
      return;
    }
    const shortcut = event.target.closest("[data-date-shortcut]");
    if (shortcut) {
      const kind = shortcut.dataset.dateShortcut;
      const date = today();
      if (kind === "yesterday") date.setDate(date.getDate() - 1);
      commit(kind === "clear" ? "" : isoDate(date));
      close();
      return;
    }
    const day = event.target.closest("[data-day]");
    if (day && day.getAttribute("aria-disabled") !== "true") {
      commit(day.dataset.day);
      close();
    }
  });

  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      // Closes the calendar, not the whole editor around it.
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    const day = event.target.closest("[data-day]");
    if (!day) return;
    const current = parseIsoDate(day.dataset.day);
    const offsets = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    let next = null;
    if (event.key in offsets) next = new Date(current.getFullYear(), current.getMonth(), current.getDate() + offsets[event.key]);
    else if (event.key === "Home") next = new Date(current.getFullYear(), current.getMonth(), current.getDate() - ((current.getDay() + 6) % 7));
    else if (event.key === "End") next = new Date(current.getFullYear(), current.getMonth(), current.getDate() + (6 - ((current.getDay() + 6) % 7)));
    else if (event.key === "PageUp" || event.key === "PageDown") {
      const delta = (event.key === "PageUp" ? -1 : 1) * (event.shiftKey ? 12 : 1);
      next = new Date(current.getFullYear(), current.getMonth() + delta, Math.min(current.getDate(), 28));
    }
    if (next) {
      event.preventDefault();
      moveFocus(next);
    }
  });

  // A click anywhere else puts the calendar away, leaving the focus where it went.
  const outside = (event) => {
    // The editor re-renders often; a field that left the page lets go too.
    if (!field.isConnected) {
      document.removeEventListener("pointerdown", outside);
      return;
    }
    if (!panel.hidden && !field.contains(event.target)) close(false);
  };
  document.addEventListener("pointerdown", outside);
}

// ---------------------------------------------------------------- stars

export function ratingStarsField(value) {
  const rating = Math.max(0, Math.min(10, Number(value) || 0));
  const stars = Array.from({ length: 10 }, (_, index) => {
    const position = index + 1;
    const checked = position === rating;
    const tabbable = checked || (!rating && position === 1);
    return `<button type="button" class="vhs-star${position <= rating ? " is-on" : ""}" role="radio" data-star="${position}"
      aria-checked="${checked}" aria-label="${position} de 10" tabindex="${tabbable ? 0 : -1}">${icon(STAR_PATH, "vhs-star-icon")}</button>`;
  }).join("");
  return `<div class="vhs-rating-field" data-rating-field>
    <span class="vhs-field-label" id="ratingLabel">Puntaje</span>
    <div class="vhs-rating-row">
      <div class="vhs-stars" role="radiogroup" aria-labelledby="ratingLabel">${stars}</div>
      <output class="vhs-rating-value" data-rating-value>${rating ? `${rating}<small>/10</small>` : "Sin puntuar"}</output>
    </div>
    <button type="button" class="vhs-rating-clear" data-rating-clear ${rating ? "" : "hidden"}>Quitar puntaje</button>
    <input type="hidden" name="rating" value="${rating}" data-personal-rating>
  </div>`;
}

// Small, read-only: the back cover and the record read view.
export function ratingStarsRead(value) {
  const rating = Math.max(0, Math.min(10, Number(value) || 0));
  if (!rating) return "Sin puntuar";
  const stars = Array.from({ length: 10 }, (_, index) => icon(STAR_PATH, `vhs-star-icon${index < rating ? " is-on" : ""}`)).join("");
  return `<span class="vhs-stars-read" role="img" aria-label="${rating} de 10">${stars}<span class="vhs-stars-read-value" aria-hidden="true">${rating}/10</span></span>`;
}

function mountRatingField(field) {
  const hidden = field.querySelector("[data-personal-rating]");
  const output = field.querySelector("[data-rating-value]");
  const clear = field.querySelector("[data-rating-clear]");
  const group = field.querySelector(".vhs-stars");
  const stars = [...field.querySelectorAll("[data-star]")];

  const paint = (shown) => stars.forEach((star, index) => star.classList.toggle("is-on", index < shown));

  const set = (rating, focus = false) => {
    const value = Math.max(0, Math.min(10, rating));
    if (hidden.value !== String(value)) {
      hidden.value = String(value);
      hidden.dispatchEvent(new Event("input", { bubbles: true }));
    }
    stars.forEach((star, index) => {
      const checked = index + 1 === value;
      star.setAttribute("aria-checked", String(checked));
      star.tabIndex = checked || (!value && index === 0) ? 0 : -1;
    });
    paint(value);
    output.innerHTML = value ? `${value}<small>/10</small>` : "Sin puntuar";
    clear.hidden = !value;
    if (focus) stars[Math.max(0, value - 1)].focus();
  };

  group.addEventListener("click", (event) => {
    const star = event.target.closest("[data-star]");
    if (star) set(Number(star.dataset.star));
  });
  // Hovering previews; leaving shows the saved value again.
  group.addEventListener("pointerover", (event) => {
    const star = event.target.closest("[data-star]");
    if (star) paint(Number(star.dataset.star));
  });
  group.addEventListener("pointerleave", () => paint(Number(hidden.value) || 0));
  group.addEventListener("keydown", (event) => {
    const current = Number(hidden.value) || 0;
    const moves = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 };
    let next = null;
    if (event.key in moves) next = Math.max(1, current + moves[event.key]);
    else if (event.key === "Home") next = 1;
    else if (event.key === "End") next = 10;
    else if (event.key === "Delete" || event.key === "Backspace" || event.key === "0") next = 0;
    else if (/^[1-9]$/.test(event.key)) next = Number(event.key);
    if (next === null) return;
    event.preventDefault();
    set(next, true);
  });
  clear.addEventListener("click", () => set(0, true));
}

export function mountPersonalControls(root) {
  root?.querySelectorAll("[data-date-field]").forEach(mountDateField);
  root?.querySelectorAll("[data-rating-field]").forEach(mountRatingField);
}
