import { cachedImageSrc } from "./card.js";
import { escapeAttr } from "./format.js";

// Equivalencias de tamaños conocidas, alineadas con domain/image_coverage.py.
// Hosts desconocidos conservan su query: podría identificar otra imagen.
export function backCoverImageKey(value) {
  const url = new URL(value);
  const host = url.hostname.toLowerCase();
  const path = url.pathname;
  let match;
  if (host === "image.tmdb.org" && (match = path.match(/^\/t\/p\/[^/]+(\/[^/]+)$/))) return `tmdb:${match[1]}`;
  if (host === "upload.wikimedia.org") {
    match = path.match(/^(\/[^/]+\/[^/]+)\/thumb(\/[0-9a-f]\/[0-9a-f]{2}\/[^/]+)\/[^/]+$/);
    return `wikimedia:${match ? match[1] + match[2] : path}`;
  }
  if (["m.media-amazon.com", "ia.media-imdb.com"].includes(host)
      && (match = path.match(/^(\/images\/M\/.+?)(?:\._V1_[^/]*)?\.(?:jpe?g|png|webp)$/))) return `amazon:${match[1]}`;
  if (["pics.filmaffinity.com", "images.filmaffinity.com"].includes(host)
      && (match = path.match(/^(\/.+-\d+)-(?:large|mmed|msmall|mtiny|full)\.(?:jpe?g|png|webp)$/))) return `filmaffinity:${match[1]}`;
  if (host === "cdn.myanimelist.net"
      && (match = path.match(/^(\/images\/(?:anime|manga)\/\d+\/\d+)[lt]?\.(?:jpe?g|webp)$/))) return `myanimelist:${match[1]}`;
  url.hash = "";
  return url.href;
}

export function backCoverImages(item) {
  const images = [];
  // Si ambos campos son la misma imagen, su rol de portada es el conocido.
  for (const [field, role, label] of [["page_image", "poster", "Portada"], ["backdrop_image", "backdrop", "Panorámica"]]) {
    const value = String(item?.[field] || "").trim();
    if (!value) continue;
    try {
      const url = new URL(value);
      if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) continue;
      const key = backCoverImageKey(value);
      if (!images.some(image => image.key === key)) images.push({ url: value, role, label, key });
    } catch { /* Un campo mal formado no impide abrir la ficha. */ }
  }
  return images.reverse();
}

export function renderBackCoverImages(item, title) {
  const images = backCoverImages(item);
  const frames = images.map((image, index) => `<figure class="vhs-back-cover-frame vhs-back-cover-frame-${index + 1}" data-image-role="${image.role}" data-back-cover-image-state="loading" aria-busy="true">
    <div class="vhs-back-cover-media">
      <img data-back-cover-image src="${escapeAttr(cachedImageSrc(image.url))}" alt="${image.label} de ${escapeAttr(title)}" aria-hidden="true" loading="eager" decoding="async">
      <div class="vhs-back-cover-image-fallback"><span>Cargando imagen…</span></div>
    </div>
    <figcaption>${image.label}</figcaption>
  </figure>`).join("");
  return `<div class="vhs-back-cover-frames" data-image-count="${images.length}" role="group" aria-label="Imágenes de ${escapeAttr(title)}">
    ${frames || `<div class="vhs-back-cover-images-empty"><span>Archivo visual</span><p>Sin imágenes guardadas para esta obra.</p></div>`}
  </div>`;
}

function settleBackCoverImage(event, loaded) {
  const image = event.target;
  if (!image?.isConnected || !image.matches?.("[data-back-cover-image]")) return;
  const frame = image.closest("[data-back-cover-image-state]");
  if (!frame) return;
  frame.dataset.backCoverImageState = loaded ? "loaded" : "error";
  frame.setAttribute("aria-busy", "false");
  image.hidden = !loaded;
  image.setAttribute("aria-hidden", String(!loaded));
  const fallback = frame.querySelector(".vhs-back-cover-image-fallback");
  fallback.hidden = loaded;
  if (!loaded) fallback.querySelector("span").textContent = "No se pudo cargar la imagen";
}

export function handleBackCoverImageLoad(event) { settleBackCoverImage(event, true); }
export function handleBackCoverImageError(event) { settleBackCoverImage(event, false); }
