import { fields } from "./fields.js";
import { showView } from "./router.js";
import { SEARCH_PAGE_SIZE, setSelectedExistingIdForSearch } from "./state.js";
import { render, setCollectionSearchMode, syncCollectionRoute } from "../surfaces/catalog-grid.js";
import { renderCatalogMergeResults, runSearch, searchManual, setActiveQuery, setCatalogMergeResults, setCatalogMergeVisibleCount, setSelectedManualIndex } from "../surfaces/catalog-search.js";

      export async function findLinkForItem(item) {
        showView("catalog", { updateHistory: false, scroll: false });
        setSelectedExistingIdForSearch(item.id);
        setSelectedManualIndex(null);
        setCollectionSearchMode("link");
        fields.query.value = [item.title || item.local_name, item.year].filter(Boolean).join(" ");
        setActiveQuery(fields.query.value.trim());
        fields.externalSource.checked = true;
        render();
        syncCollectionRoute("push");
        setCatalogMergeResults([item]);
        setCatalogMergeVisibleCount(SEARCH_PAGE_SIZE);
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeKicker.textContent = "Comparación";
        fields.catalogMergeTitle.textContent = "Entrada seleccionada";
        fields.catalogMergeStatus.textContent = "Elegí un resultado externo y tocá Comparar para revisar diferencias.";
        renderCatalogMergeResults();
        await searchManual("all", "Buscando coincidencias en Wikipedia, IMDb, FilmAffinity y Jikan...");
        fields.query.scrollIntoView({ behavior: "smooth", block: "center" });
      }

      export async function findLocalMatchForItem(item) {
        fields.query.value = [item.detected_title, item.detected_year].filter(Boolean).join(" ");
        await runSearch({ updateHistory: false });
        fields.query.scrollIntoView({ behavior: "smooth", block: "center" });
      }
