(() => {
  const root = document.getElementById("publicPresentation");
  if (!root) return;

  const capability = root.dataset.capability || "";
  const description = document.getElementById("publicPresentationDescription");
  const count = document.getElementById("publicPresentationCount");
  const list = document.getElementById("publicPresentationList");
  const status = document.getElementById("publicPresentationStatus");

  const setStatus = (message, state = "") => {
    status.textContent = message;
    status.dataset.state = state;
  };

  const text = (value) => String(value || "").trim();

  const addMeta = (item, values) => {
    const filtered = values.filter(Boolean);
    if (!filtered.length) return;
    const meta = document.createElement("p");
    meta.className = "public-presentation__meta";
    meta.textContent = filtered.join(" · ");
    item.append(meta);
  };

  const renderItem = (entry) => {
    const row = document.createElement("li");
    row.className = "public-presentation__item";

    const index = document.createElement("span");
    index.className = "public-presentation__index";
    index.textContent = String(entry.position || 0).padStart(2, "0");
    row.append(index);

    const copy = document.createElement("div");
    const heading = document.createElement("h3");
    heading.textContent = text(entry.title);
    copy.append(heading);
    if (text(entry.original_title) && text(entry.original_title) !== text(entry.title)) {
      const original = document.createElement("p");
      original.className = "public-presentation__original";
      original.textContent = text(entry.original_title);
      copy.append(original);
    }
    addMeta(copy, [text(entry.year), text(entry.kind), text(entry.duration_minutes) ? `${entry.duration_minutes} min` : ""]);
    row.append(copy);

    const tags = document.createElement("div");
    tags.className = "public-presentation__tags";
    (Array.isArray(entry.genres) ? entry.genres : []).slice(0, 8).forEach((genre) => {
      const tag = document.createElement("span");
      tag.textContent = text(genre);
      tags.append(tag);
    });
    if (tags.childElementCount) row.append(tags);
    return row;
  };

  const render = (payload) => {
    const presentation = payload.presentation || {};
    const items = Array.isArray(payload.items) ? payload.items : [];
    const name = text(presentation.title) || "Funciones disponibles";
    document.title = `${name} · Movie Inbox`;
    root.querySelector("h1").textContent = name;
    description.textContent = text(presentation.description);
    description.hidden = !description.textContent;
    count.textContent = `${items.length} ${items.length === 1 ? "FUNCION DISPONIBLE" : "FUNCIONES DISPONIBLES"}`;
    list.replaceChildren(...items.map(renderItem));
    setStatus(items.length ? "" : "No hay funciones disponibles en esta cartelera.");
  };

  fetch(`/public/v1/presentations/${encodeURIComponent(capability)}`, { credentials: "omit" })
    .then((response) => (response.ok ? response.json() : Promise.reject(new Error("unavailable"))))
    .then(render)
    .catch(() => {
      list.replaceChildren();
      count.textContent = "CARTELERA NO DISPONIBLE";
      setStatus("Esta cartelera no está disponible.", "error");
    });
})();
