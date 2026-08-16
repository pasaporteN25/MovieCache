import { card, posterArtwork } from "../core/card.js";
import { load, loadCatalog } from "../core/catalog-data.js";
import { detailLinks, drawerPoster, factsPanel } from "../core/detail.js";
import { fields } from "../core/fields.js";
import { displayTitle, escapeAttr, escapeHtml, firstListValue, listText, meta, normalizeRating, titleSizeClass } from "../core/format.js";
import { apiFetch } from "../core/http.js";
import { clubMode, setClubMode } from "../core/state.js";
import { members } from "./admin-members.js";

      export let clubCatalogs = [];

      export let selectedClubUserId = "";

      export let sharedCatalog = null;

      export let curatedCollections = [];

      export let selectedCollectionId = "";

      export let selectedCollection = null;

      export let selectedCollectionItems = new Set();

      export let clubLoading = false;

      export let clubVisibleCount = 24;

      export const CLUB_PAGE_SIZE = 24;

      export function setSelectedCollectionId(value) {
        selectedCollectionId = value;
      }

      export async function loadClub({ announce = false } = {}) {
        if (clubLoading) return;
        clubLoading = true;
        fields.clubView.setAttribute("aria-busy", "true");
        fields.refreshClub.disabled = true;
        if (announce) setClubFeedback("Actualizando el Club…");
        try {
          const [communityResponse, collectionsResponse] = await Promise.all([
            apiFetch("/api/community"),
            apiFetch("/api/collections")
          ]);
          const communityPayload = await communityResponse.json();
          const collectionsPayload = await collectionsResponse.json();
          if (!communityResponse.ok) throw new Error(communityPayload.reason || `HTTP ${communityResponse.status}`);
          if (!collectionsResponse.ok) throw new Error(collectionsPayload.reason || `HTTP ${collectionsResponse.status}`);
          clubCatalogs = communityPayload.catalogs || [];
          curatedCollections = collectionsPayload.collections || [];
          if (!clubCatalogs.some((entry) => entry.user?.id === selectedClubUserId)) {
            selectedClubUserId = clubCatalogs[0]?.user?.id || "";
          }
          if (!curatedCollections.some((entry) => entry.id === selectedCollectionId)) {
            selectedCollectionId = "";
            selectedCollection = null;
            selectedCollectionItems.clear();
          }
          renderClubMode();
          renderClubTabs();
          renderCollectionDirectory();
          if (clubMode === "members") {
            if (selectedClubUserId) await loadSharedCatalog(selectedClubUserId);
            else {
              sharedCatalog = null;
              renderSharedCatalog();
            }
          } else if (selectedCollectionId) {
            await loadCollectionDetail(selectedCollectionId);
          }
          if (announce) setClubFeedback("Club actualizado.");
        } catch (error) {
          console.error("[catalog-viewer] club load failed", error);
          clubCatalogs = [];
          curatedCollections = [];
          sharedCatalog = null;
          selectedCollection = null;
          renderClubMode();
          renderClubTabs();
          renderSharedCatalog();
          renderCollectionDirectory();
          setClubFeedback("No pudimos cargar los estantes del Club.", "error");
        } finally {
          clubLoading = false;
          fields.clubView.setAttribute("aria-busy", "false");
          fields.refreshClub.disabled = false;
        }
      }

      export async function changeClubMode(event) {
        const button = event.target.closest("[data-club-mode]");
        if (!button) return;
        const mode = button.dataset.clubMode;
        if (!["collections", "members"].includes(mode) || mode === clubMode) return;
        setClubMode(mode);
        localStorage.setItem("movie-inbox-club-mode", clubMode);
        renderClubMode();
        setClubFeedback("");
        if (clubMode === "members" && selectedClubUserId && !sharedCatalog) {
          await loadSharedCatalog(selectedClubUserId);
        }
      }

      export function renderClubMode() {
        const collectionsActive = clubMode === "collections";
        fields.clubCollectionsPanel.hidden = !collectionsActive;
        fields.clubMembersPanel.hidden = collectionsActive;
        fields.clubCollectionsMode.classList.toggle("active", collectionsActive);
        fields.clubCollectionsMode.setAttribute("aria-pressed", String(collectionsActive));
        fields.clubMembersMode.classList.toggle("active", !collectionsActive);
        fields.clubMembersMode.setAttribute("aria-pressed", String(!collectionsActive));
        fields.clubCollectionsCount.textContent = curatedCollections.length;
        fields.clubMembersCount.textContent = clubCatalogs.length;
      }

      export async function selectClubCatalog(event) {
        const button = event.target.closest("[data-club-user-id]");
        if (!button || button.dataset.clubUserId === selectedClubUserId) return;
        selectedClubUserId = button.dataset.clubUserId || "";
        clubVisibleCount = CLUB_PAGE_SIZE;
        renderClubTabs();
        await loadSharedCatalog(selectedClubUserId);
      }

      export async function loadSharedCatalog(userId) {
        fields.clubCatalogPanel.setAttribute("aria-busy", "true");
        setClubFeedback("Abriendo estante compartido…");
        try {
          const response = await apiFetch(`/api/community/${encodeURIComponent(userId)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          sharedCatalog = payload;
          renderSharedCatalog();
          setClubFeedback("");
        } catch (error) {
          sharedCatalog = null;
          renderSharedCatalog();
          setClubFeedback(
            error.message === "shared_catalog_not_found"
              ? "Ese catálogo dejó de estar compartido."
              : "No pudimos abrir este catálogo.",
            "error"
          );
        } finally {
          fields.clubCatalogPanel.setAttribute("aria-busy", "false");
        }
      }

      export function renderClubTabs() {
        fields.clubMemberTabs.innerHTML = clubCatalogs.map((entry) => {
          const active = entry.user?.id === selectedClubUserId;
          const username = entry.user?.username || "Miembro";
          return `<button type="button" data-club-user-id="${escapeAttr(entry.user?.id || "")}" aria-pressed="${active}" class="${active ? "active" : ""}">
            <span class="club-member-mark" aria-hidden="true">${escapeHtml(username.slice(0, 2).toUpperCase())}</span>
            <span><strong>${escapeHtml(entry.user?.is_self ? "Mi catálogo" : username)}</strong><small>${escapeHtml(entry.catalog?.name || "Catálogo personal")} · ${escapeHtml(entry.counts?.total || 0)} obras</small></span>
          </button>`;
        }).join("");
      }

      export function renderSharedCatalog() {
        if (!sharedCatalog) {
          fields.clubCatalogPanel.innerHTML = `<div class="club-empty"><strong>El estante compartido está vacío</strong><p>Cuando alguien habilite su catálogo aparecerá en este espacio.</p></div>`;
          fields.clubLoadMore.hidden = true;
          return;
        }
        const catalogItems = sharedCatalog.items || [];
        const visibleItems = catalogItems.slice(0, clubVisibleCount);
        const username = sharedCatalog.user?.username || "Miembro";
        const history = sharedCatalog.history || [];
        const historySection = history.length ? `
          <section class="club-history" aria-labelledby="clubHistoryTitle">
            <div><h4 id="clubHistoryTitle">Actividad de vistas</h4><span>${history.length} recientes</span></div>
            <ol>${history.slice(0, 8).map((entry) => `<li><strong>${escapeHtml(displayTitle(entry) || "Sin título")}</strong>${entry.watched_at ? `<time datetime="${escapeAttr(entry.watched_at)}">${escapeHtml(entry.watched_at)}</time>` : ""}</li>`).join("")}</ol>
          </section>` : "";
        fields.clubCatalogPanel.innerHTML = `
          <header class="club-catalog-heading">
            <div><span>${escapeHtml(username)}</span><h3>${escapeHtml(sharedCatalog.catalog?.name || "Catálogo compartido")}</h3></div>
            <div class="club-catalog-count"><strong>${catalogItems.length}</strong><span>obras visibles</span></div>
          </header>
          ${historySection}
          <div class="club-grid">${visibleItems.map((item, index) => sharedCard(item, username, index < 6)).join("")}</div>`;
        fields.clubLoadMore.hidden = visibleItems.length >= catalogItems.length;
      }

      export function sharedCard(item, username, priority = false) {
        const title = displayTitle(item) || "Sin título";
        const hasStatus = Object.prototype.hasOwnProperty.call(item, "status");
        const hasRating = Object.prototype.hasOwnProperty.call(item, "rating");
        const hasReview = Object.prototype.hasOwnProperty.call(item, "review");
        const signals = [
          hasStatus ? `<span>${item.status === "watched" ? "Vista" : "Pendiente"}</span>` : "",
          hasRating && normalizeRating(item.rating) ? `<strong>${normalizeRating(item.rating)}/10</strong>` : "",
          hasReview && String(item.review || "").trim() ? "<span>Con review</span>" : ""
        ].filter(Boolean).join("");
        return `<article class="club-card">
          <div class="club-card-poster">${posterArtwork(item, title, priority)}</div>
          <div class="club-card-body">
            <div><span>${escapeHtml([item.kind, item.year].filter(Boolean).join(" · ") || "Obra")}</span><h4 class="${titleSizeClass(title)}">${escapeHtml(title)}</h4></div>
            <div class="club-card-signals">${signals || "<span>Registro privado</span>"}</div>
            <button type="button" data-click="open-shared-detail" data-id="${escapeAttr(item.id || "")}" aria-label="Ver ficha compartida de ${escapeAttr(title)} por ${escapeAttr(username)}">Ver ficha</button>
          </div>
        </article>`;
      }

      export function showMoreClubItems() {
        clubVisibleCount += CLUB_PAGE_SIZE;
        renderSharedCatalog();
      }

      export function setClubFeedback(message, tone = "") {
        fields.clubFeedback.textContent = message;
        fields.clubFeedback.dataset.tone = tone;
        fields.clubFeedback.hidden = !message;
      }

      export function renderCollectionDirectory() {
        const followedCount = curatedCollections.filter((collection) => collection.followed).length;
        fields.followedCollectionsSummary.textContent = `${followedCount} siguiendo`;
        fields.collectionDirectory.hidden = Boolean(selectedCollection);
        fields.collectionDetailPanel.hidden = !selectedCollection;
        if (!curatedCollections.length) {
          fields.collectionList.innerHTML = `<div class="club-empty"><strong>Todavía no hay colecciones</strong><p>Las colecciones publicadas por el administrador aparecerán acá.</p></div>`;
          return;
        }
        fields.collectionList.innerHTML = curatedCollections
          .map((collection) => collectionDirectoryCard(collection))
          .join("");
      }

      export function collectionDirectoryCard(collection) {
        const count = Number(collection.counts?.total || 0);
        const owner = collection.owner?.username || "Movie Inbox";
        const followed = Boolean(collection.followed);
        const collectionLabel = collection.built_in
          ? "Colección inicial"
          : collection.visibility === "private"
            ? "Colección privada"
            : `Publicada por ${owner}`;
        return `<article class="collection-card${followed ? " is-followed" : ""}">
          <div class="collection-mosaic" aria-hidden="true">${collectionMosaic(collection.preview || [])}</div>
          <div class="collection-card-copy">
            <div class="collection-card-heading">
              <span>${escapeHtml(collectionLabel)}</span>
              <h4>${escapeHtml(collection.title || "Colección")}</h4>
            </div>
            <p>${escapeHtml(collection.description || "Una selección del Club.")}</p>
            <div class="collection-card-meta"><strong>${count}</strong><span>obras</span>${followed ? '<span class="collection-followed-mark">Siguiendo</span>' : ""}</div>
            <div class="collection-card-actions">
              <button type="button" data-click="open-collection" data-id="${escapeAttr(collection.id || "")}">Ver colección</button>
              <button class="quiet-action" type="button" data-click="toggle-collection-follow" data-id="${escapeAttr(collection.id || "")}">${followed ? "Dejar de seguir" : "Seguir"}</button>
            </div>
          </div>
        </article>`;
      }

      export function collectionMosaic(preview) {
        const slots = preview.slice(0, 4);
        while (slots.length < 4) slots.push({ title: "Movie Inbox" });
        return slots.map((item) => `<div>${posterArtwork(item, displayTitle(item) || "Movie Inbox")}</div>`).join("");
      }

      export async function openCollection(collectionId) {
        selectedCollectionId = String(collectionId || "");
        selectedCollection = null;
        selectedCollectionItems.clear();
        fields.collectionDirectory.hidden = true;
        fields.collectionDetailPanel.hidden = false;
        fields.collectionDetailPanel.setAttribute("aria-busy", "true");
        fields.collectionDetailTitle.textContent = "Abriendo colección…";
        await loadCollectionDetail(selectedCollectionId, { announce: true });
      }

      export async function loadCollectionDetail(collectionId, { announce = false } = {}) {
        if (!collectionId) return;
        fields.collectionDetailPanel.setAttribute("aria-busy", "true");
        if (announce) setClubFeedback("Preparando la colección…");
        try {
          const response = await apiFetch(`/api/collections/${encodeURIComponent(collectionId)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedCollectionId = collectionId;
          selectedCollection = payload;
          selectedCollectionItems = new Set(
            [...selectedCollectionItems].filter((itemId) => payload.items?.some(
              (item) => item.collection_item_id === itemId && item.catalog?.state === "missing"
            ))
          );
          renderCollectionDetail();
          renderCollectionDirectory();
          setClubFeedback("");
          if (announce) fields.collectionDetailTitle.focus({ preventScroll: true });
        } catch (error) {
          selectedCollectionId = "";
          selectedCollection = null;
          selectedCollectionItems.clear();
          renderCollectionDirectory();
          setClubFeedback(
            error.message === "collection_not_found"
              ? "Esa colección ya no está disponible."
              : "No pudimos abrir la colección.",
            "error"
          );
        } finally {
          fields.collectionDetailPanel.setAttribute("aria-busy", "false");
        }
      }

      export function closeCollectionDetail() {
        const previousId = selectedCollectionId;
        selectedCollectionId = "";
        selectedCollection = null;
        selectedCollectionItems.clear();
        renderCollectionDirectory();
        setClubFeedback("");
        requestAnimationFrame(() => {
          fields.collectionList.querySelector(`[data-id="${CSS.escape(previousId)}"]`)?.focus();
        });
      }

      export function renderCollectionDetail() {
        if (!selectedCollection) return;
        const counts = selectedCollection.counts || {};
        fields.collectionDetailKicker.textContent = selectedCollection.built_in
          ? "Colección inicial"
          : selectedCollection.visibility === "private"
            ? "Colección privada"
            : "Colección del Club";
        fields.collectionDetailTitle.textContent = selectedCollection.title || "Colección";
        fields.collectionDetailTitle.setAttribute("tabindex", "-1");
        fields.collectionDetailDescription.textContent = selectedCollection.description || "";
        fields.collectionFollowButton.textContent = selectedCollection.followed ? "Dejar de seguir" : "Seguir";
        fields.collectionFollowButton.classList.toggle("is-following", Boolean(selectedCollection.followed));
        const sourceUrl = String(selectedCollection.source_url || "");
        fields.collectionDetailSource.hidden = !sourceUrl;
        fields.collectionDetailSource.href = sourceUrl || "#";
        fields.collectionDetailSource.textContent = selectedCollection.source_label || "Ver fuente";
        fields.collectionStats.innerHTML = [
          [counts.total || 0, "Obras"],
          [counts.missing || 0, "Faltantes"],
          [counts.present || 0, "En tu catálogo"],
          [counts.review || 0, "Para revisar"]
        ].map(([value, label]) => `<div><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
        fields.collectionItems.innerHTML = (selectedCollection.items || [])
          .map((item, index) => collectionItemCard(item, index < 6))
          .join("");
        fields.addMissingCollectionItems.disabled = !(counts.missing > 0);
        syncCollectionSelection();
      }

      export function collectionItemCard(item, priority = false) {
        const title = displayTitle(item) || "Sin título";
        const state = item.catalog?.state || "missing";
        const missing = state === "missing";
        const stateLabel = state === "present"
          ? "En tu catálogo"
          : state === "review"
            ? "Posible coincidencia"
            : "Disponible para agregar";
        const actionLabel = state === "present" ? "Ya está" : state === "review" ? "Requiere revisión" : "Agregar";
        const selected = selectedCollectionItems.has(item.collection_item_id);
        return `<article class="club-card collection-item-card" data-catalog-state="${escapeAttr(state)}">
          <div class="club-card-poster">${posterArtwork(item, title, priority)}</div>
          <div class="club-card-body">
            <div><span>${escapeHtml([item.kind, item.year].filter(Boolean).join(" · ") || "Obra")}</span><h4 class="${titleSizeClass(title)}">${escapeHtml(title)}</h4></div>
            <div class="club-card-signals"><span>${escapeHtml(stateLabel)}</span></div>
            <div class="collection-item-actions">
              <label class="collection-item-select${missing ? "" : " is-disabled"}">
                <input type="checkbox" data-collection-select="${escapeAttr(item.collection_item_id || "")}" ${selected ? "checked" : ""} ${missing ? "" : "disabled"}>
                <span class="sr-only">Seleccionar ${escapeHtml(title)}</span>
              </label>
              <button type="button" data-click="add-collection-item" data-id="${escapeAttr(item.collection_item_id || "")}" ${missing ? "" : "disabled"}>${actionLabel}</button>
            </div>
          </div>
        </article>`;
      }

      export async function toggleCollectionFollow(collectionId = "") {
        const targetId = String(collectionId || selectedCollectionId || "");
        const collection = selectedCollection?.id === targetId
          ? selectedCollection
          : curatedCollections.find((entry) => entry.id === targetId);
        if (!collection) return;
        const following = !collection.followed;
        fields.collectionFollowButton.disabled = true;
        try {
          const response = await apiFetch(`/api/collections/${encodeURIComponent(targetId)}/follow`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ following })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curatedCollections = curatedCollections.map((entry) => (
            entry.id === targetId ? { ...entry, ...payload.collection } : entry
          ));
          if (selectedCollection?.id === targetId) {
            selectedCollection = {
              ...selectedCollection,
              ...payload.collection,
              counts: selectedCollection.counts
            };
          }
          renderCollectionDirectory();
          if (selectedCollection) renderCollectionDetail();
          setClubFeedback(
            following ? "Colección agregada a tus seguidas." : "Dejaste de seguir la colección."
          );
        } catch (error) {
          setClubFeedback("No pudimos cambiar el seguimiento. Volvé a intentar.", "error");
        } finally {
          fields.collectionFollowButton.disabled = false;
        }
      }

      export function changeCollectionSelection(event) {
        const checkbox = event.target.closest("[data-collection-select]");
        if (!checkbox) return;
        const itemId = checkbox.dataset.collectionSelect || "";
        if (checkbox.checked) selectedCollectionItems.add(itemId);
        else selectedCollectionItems.delete(itemId);
        syncCollectionSelection();
      }

      export function toggleMissingCollectionSelection() {
        const missingIds = (selectedCollection?.items || [])
          .filter((item) => item.catalog?.state === "missing")
          .map((item) => item.collection_item_id);
        if (fields.selectMissingCollectionItems.checked) {
          missingIds.forEach((itemId) => selectedCollectionItems.add(itemId));
        } else {
          missingIds.forEach((itemId) => selectedCollectionItems.delete(itemId));
        }
        fields.collectionItems.querySelectorAll("[data-collection-select]").forEach((checkbox) => {
          checkbox.checked = selectedCollectionItems.has(checkbox.dataset.collectionSelect || "");
        });
        syncCollectionSelection();
      }

      export function syncCollectionSelection() {
        const missingIds = (selectedCollection?.items || [])
          .filter((item) => item.catalog?.state === "missing")
          .map((item) => item.collection_item_id);
        const selectedMissing = missingIds.filter((itemId) => selectedCollectionItems.has(itemId));
        fields.collectionSelectionSummary.textContent = `${selectedMissing.length} seleccionadas`;
        fields.addCollectionSelection.disabled = !selectedMissing.length;
        fields.selectMissingCollectionItems.checked = Boolean(missingIds.length)
          && selectedMissing.length === missingIds.length;
        fields.selectMissingCollectionItems.indeterminate = selectedMissing.length > 0
          && selectedMissing.length < missingIds.length;
        fields.selectMissingCollectionItems.disabled = !missingIds.length;
      }

      export function addSelectedCollectionItems() {
        addCollectionItems([...selectedCollectionItems]);
      }

      export function addMissingCollectionItems() {
        const missingIds = (selectedCollection?.items || [])
          .filter((item) => item.catalog?.state === "missing")
          .map((item) => item.collection_item_id);
        addCollectionItems(missingIds);
      }

      export async function addCollectionItems(itemIds) {
        if (!selectedCollectionId || !itemIds.length) return;
        fields.collectionDetailPanel.setAttribute("aria-busy", "true");
        fields.addCollectionSelection.disabled = true;
        fields.addMissingCollectionItems.disabled = true;
        setClubFeedback(`Procesando ${itemIds.length} ${itemIds.length === 1 ? "obra" : "obras"}…`);
        try {
          const response = await apiFetch(`/api/collections/${encodeURIComponent(selectedCollectionId)}/add`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ item_ids: itemIds })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedCollectionItems.clear();
          await loadCatalog();
          await loadCollectionDetail(selectedCollectionId);
          const summary = payload.summary || {};
          const parts = [];
          if (summary.added) parts.push(`${summary.added} agregadas`);
          if (summary.present) parts.push(`${summary.present} ya estaban`);
          if (summary.review) parts.push(`${summary.review} requieren revisión`);
          setClubFeedback(parts.join(" · ") || "No hubo cambios.", summary.review ? "warning" : "");
        } catch (error) {
          setClubFeedback(
            "No pudimos completar la operación. Actualizá la colección para comprobar qué obras se guardaron.",
            "error"
          );
        } finally {
          fields.collectionDetailPanel.setAttribute("aria-busy", "false");
          syncCollectionSelection();
        }
      }

      export function openSharedDetail(itemId) {
        const item = sharedCatalog?.items?.find((entry) => String(entry.id || "") === String(itemId || ""));
        if (!item) return;
        const title = displayTitle(item) || "Sin título";
        const summary = item.wikipedia_extract || item.description || "";
        const personalRows = [
          Object.prototype.hasOwnProperty.call(item, "status") ? `<div><dt>Estado</dt><dd>${item.status === "watched" ? "Vista" : "Pendiente"}</dd></div>` : "",
          Object.prototype.hasOwnProperty.call(item, "watched_at") ? `<div><dt>Fecha vista</dt><dd>${escapeHtml(item.watched_at || "Sin fecha")}</dd></div>` : "",
          Object.prototype.hasOwnProperty.call(item, "rating") ? `<div><dt>Puntaje</dt><dd>${normalizeRating(item.rating) ? `${normalizeRating(item.rating)}/10` : "Sin puntuar"}</dd></div>` : ""
        ].filter(Boolean).join("");
        const review = Object.prototype.hasOwnProperty.call(item, "review") ? String(item.review || "").trim() : "";
        fields.sharedDetailOwner.textContent = `Compartida por ${sharedCatalog.user?.username || "un miembro"}`;
        fields.sharedDetailBody.innerHTML = `
          <section class="drawer-hero">${drawerPoster(item, title)}<div class="drawer-intro"><span class="drawer-kicker">Ficha del Club</span><h2>${escapeHtml(title)}</h2><div class="drawer-byline">${[item.year, firstListValue(item.directors), listText(item.genres, 2)].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join("")}</div></div></section>
          ${personalRows ? `<section class="shared-personal-record"><h3>Registro compartido</h3><dl>${personalRows}</dl>${review ? `<blockquote>${escapeHtml(review)}</blockquote>` : ""}</section>` : ""}
          <section class="drawer-synopsis"><h3>Sinopsis</h3><p>${escapeHtml(summary || "No hay una sinopsis disponible.")}</p></section>
          <details class="drawer-accordion"><summary><span>Ficha técnica</span><small>Dirección, reparto y títulos</small></summary><div class="drawer-accordion-body">${factsPanel(item) || '<span class="status-line">Sin ficha enriquecida.</span>'}</div></details>
          <div class="links shared-detail-links">${detailLinks(item)}</div>`;
        fields.sharedDetailDialog.showModal();
        fields.closeSharedDetail.focus();
      }

      export function closeSharedDetail() {
        fields.sharedDetailDialog.close();
        fields.sharedDetailBody.innerHTML = "";
      }

      export function storedClubMode() {
        try {
          const stored = localStorage.getItem("movie-inbox-club-mode");
          return stored === "members" ? "members" : "collections";
        } catch (_) {
          return "collections";
        }
      }

