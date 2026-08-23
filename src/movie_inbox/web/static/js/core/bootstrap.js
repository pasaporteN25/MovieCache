import { handlePosterError, handlePosterLoad } from "./card.js";
import { load, logout } from "./catalog-data.js";
import { cancelPersonalEdit, closeDetail, deleteCatalogItem, discardDetailChanges, editPersonalRecord, findLinkForCatalog, handleBeforeUnload, handleDetailFormMutation, hasUnsavedDetailChanges, keepEditingDetail, navigateDetail, openAnotherRandomDetail, openDetail, openDetailFromTrigger, openRandomDetail, requestDetailTransition, saveDetailChanges, saveMetadata, savePersonal } from "./detail.js";
import { fields } from "./fields.js";
import { localDateOffset, todayLocalDate } from "./format.js";
import { changeMergeChoice, changeMergeSurvivor, closeMergeComparator, mergeSearchResult, renderMergeComparator, retryMergeComparison, submitReviewedMerge } from "./merge.js";
import { changeInboxMode, goHome, goToAdmin, goToClub, goToCollectionRoot, goToImports, goToInbox, restoreRoute, setInboxMode } from "./router.js";
import { CATALOG_PAGE_SIZE, inboxMode } from "./state.js";
import { browseManagedLibraryPath, checkManagedLibraryPath, closeLibraryDialog, handleLibraryAction, handleLibraryPathDirectory, openLibraryDialog, parentLibraryPath, saveManagedLibrary, useBrowsedLibraryPath } from "../surfaces/admin-libraries.js";
import { archiveMemberAccount, closeArchiveMemberDialog, closeEditMemberDialog, closeMemberDialog, closePrivacyDialog, closeTemporaryPasswordDialog, copyTemporaryPassword, createMember, handleArchivedMemberAction, handleMemberAction, handleVisibilityChange, openMemberDialog, openPrivacyDialog, refreshAdminData, saveMemberProfile, savePrivacyPreferences, syncPrivacyControls } from "../surfaces/admin-members.js";
import { applyCollectionYearRange, changeRandomScope, clearFilter, clearFilters, collectionFiltersChanged, downloadCatalogExport, randomizeView, render, renderDatabaseMenu, resetViewOrder, setCatalogVisibleCount, setCollectionFilterValue, setRandomOrder, showMoreCatalogItems, syncCollectionRoute, toggleCatalog, toggleCollectionFilter, toggleWatched } from "../surfaces/catalog-grid.js";
import { addSearchResult, cancelExternalSearch, clearManualSearch, closeDescriptionDialog, forceAddSearchResult, nextWikiReview, openSearchDescription, prepareManualMerge, previousWikiReview, restoreDescriptionFocus, retryExternalSource, runSearch, showMoreCatalogResults, showMoreManualResults } from "../surfaces/catalog-search.js";
import { addCollectionItems, addMissingCollectionItems, addSelectedCollectionItems, changeClubMode, changeCollectionSelection, closeCollectionDetail, closeSharedDetail, loadClub, openCollection, openSharedDetail, selectClubCatalog, showMoreClubItems, toggleCollectionFollow, toggleMissingCollectionSelection } from "../surfaces/club.js";
import { activateHomeSection, addHomeCollectionItem, goToHomeCollection, loadEditorialFeaturedDate, moveSpotlight, openHomeCollectionDetail, refreshEditorialHome, selectSpotlight } from "../surfaces/home.js";
import { autoResolveDuplicates, changeCurationHistoryMode, clearCurationHistory, curationHistoryMode, handleCurationClick, loadCurationQueue } from "../surfaces/inbox-curation.js";
import { analyzeImportSource, applySelectedImport, changeImportFile, changeImportSelection, handleImportClick, refreshImportMapping, toggleVisibleImportItems } from "../surfaces/inbox-imports.js";
import { changeScannerHistoryMode, changeScannerQueueFilter, clearScannerHistory, handleScannerReviewAction, loadScannerQueue, moveScannerQueueSelection, scannerHistoryMode, searchScannerQueue, selectScannerQueueItem } from "../surfaces/inbox-scanner.js";

      export function handleDelegatedClick(event) {
        const target = event.target.closest("[data-click]");
        if (!target) return;
        event.preventDefault();
        event.stopPropagation();
        const id = target.dataset.id || "";
        const index = Number(target.dataset.index);
        const actions = {
          "open-detail": () => openDetailFromTrigger(target, id),
          "open-shared-detail": () => openSharedDetail(id),
          "open-home-collection-detail": () => openHomeCollectionDetail(target.dataset.key || ""),
          "open-collection": () => openCollection(id),
          "toggle-collection-follow": () => toggleCollectionFollow(id),
          "add-collection-item": () => addCollectionItems([id]),
          "add-home-collection-item": () => addHomeCollectionItem(target.dataset.collectionId || "", id, target),
          "open-home-collection": () => goToHomeCollection(target.dataset.collectionId || id),
          "home-section-action": () => activateHomeSection(target.dataset.sectionId || ""),
          "spotlight-previous": () => moveSpotlight(-1, "spotlight-previous"),
          "spotlight-next": () => moveSpotlight(1, "spotlight-next"),
          "spotlight-select": () => selectSpotlight(Number(target.dataset.index || 0), true),
          "home-date-today": () => loadEditorialFeaturedDate(todayLocalDate()),
          "home-date-yesterday": () => loadEditorialFeaturedDate(localDateOffset(-1)),
          "home-empty-catalog": goToCollectionRoot,
          "home-empty-import": goToImports,
          "home-empty-club": goToClub,
          "refresh-home": refreshEditorialHome,
          "toggle-watched": () => runDetailAwareAction(target, () => toggleWatched(event, id, target.dataset.status || "to_watch")),
          "focus-personal": editPersonalRecord,
          "edit-personal": editPersonalRecord,
          "cancel-personal": cancelPersonalEdit,
          "find-link": () => runDetailAwareAction(target, () => findLinkForCatalog(event, id)),
          "save-personal": () => savePersonal(event, id),
          "toggle-catalog": () => runDetailAwareAction(target, () => toggleCatalog(event, id)),
          "delete-item": () => requestDetailTransition(() => deleteCatalogItem(event, id)),
          "save-metadata": () => saveMetadata(event, id),
          "detail-previous": () => navigateDetail(-1),
          "detail-next": () => navigateDetail(1),
          "detail-random": openAnotherRandomDetail,
          "retry-merge-comparison": retryMergeComparison,
          "show-more-manual": () => showMoreManualResults(target.dataset.source || ""),
          "retry-external-source": () => retryExternalSource(target.dataset.source || ""),
          "show-more-catalog": showMoreCatalogResults,
          "merge-result": () => mergeSearchResult(index, id),
          "add-result": () => addSearchResult(index),
          "prepare-merge": () => prepareManualMerge(index),
          "show-description": () => openSearchDescription(target.dataset.collection || "", target.dataset.key || ""),
          "force-add": () => forceAddSearchResult(index),
          "clear-filter": () => clearFilter(target.dataset.filter || "", target.dataset.value || ""),
          "toggle-collection-filter": () => toggleCollectionFilter(target.dataset.filter || "", target.dataset.value || ""),
          "run-search": runSearch
        };
        actions[target.dataset.click]?.();
      }

      export function handleKeyboardModality(event) {
        if (["Tab", "Enter", " "].includes(event.key)) document.body.dataset.inputMethod = "keyboard";
      }

      export function handlePointerModality() {
        document.body.dataset.inputMethod = "pointer";
      }

      export function runDetailAwareAction(target, action) {
        if (target.closest("#detailDrawer") && hasUnsavedDetailChanges()) {
          requestDetailTransition(action);
          return;
        }
        action();
      }

      // --- wiring: reproduced verbatim from the original app.js bootstrap ---
      document.querySelector("#refresh").addEventListener("click", refreshAdminData);
      fields.searchButton.addEventListener("click", () => runSearch());
      fields.homeButton.addEventListener("click", goHome);
      fields.catalogButton.addEventListener("click", goToCollectionRoot);
      fields.inboxButton.addEventListener("click", () => goToInbox());
      fields.clubButton.addEventListener("click", goToClub);
      fields.adminButton.addEventListener("click", goToAdmin);
      fields.privacyButton.addEventListener("click", openPrivacyDialog);
      fields.logoutButton.addEventListener("click", logout);
      fields.createMemberButton.addEventListener("click", openMemberDialog);
      fields.createLibraryButton.addEventListener("click", () => openLibraryDialog());
      fields.catalogExportActions.addEventListener("click", downloadCatalogExport);
      fields.libraryForm.addEventListener("submit", saveManagedLibrary);
      fields.libraryList.addEventListener("click", handleLibraryAction);
      fields.browseLibraryPath.addEventListener("click", () => browseManagedLibraryPath(fields.libraryRootPath.value));
      fields.checkLibraryPath.addEventListener("click", checkManagedLibraryPath);
      fields.libraryPathParent.addEventListener("click", () => browseManagedLibraryPath(parentLibraryPath));
      fields.useLibraryPath.addEventListener("click", useBrowsedLibraryPath);
      fields.libraryPathDirectories.addEventListener("click", handleLibraryPathDirectory);
      fields.closeLibraryDialog.addEventListener("click", closeLibraryDialog);
      fields.cancelLibraryDialog.addEventListener("click", closeLibraryDialog);
      fields.libraryDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeLibraryDialog();
      });
      fields.memberForm.addEventListener("submit", createMember);
      fields.memberList.addEventListener("click", handleMemberAction);
      fields.archivedMemberList.addEventListener("click", handleArchivedMemberAction);
      fields.closeMemberDialog.addEventListener("click", closeMemberDialog);
      fields.cancelMemberDialog.addEventListener("click", closeMemberDialog);
      fields.showMemberPassword.addEventListener("change", () => {
        fields.memberTemporaryPassword.type = fields.showMemberPassword.checked ? "text" : "password";
      });
      fields.copyTemporaryPassword.addEventListener("click", copyTemporaryPassword);
      fields.closeTemporaryPasswordDialog.addEventListener("click", closeTemporaryPasswordDialog);
      fields.finishTemporaryPassword.addEventListener("click", closeTemporaryPasswordDialog);
      fields.memberDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeMemberDialog();
      });
      fields.temporaryPasswordDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeTemporaryPasswordDialog();
      });
      fields.privacyForm.addEventListener("submit", savePrivacyPreferences);
      fields.catalogShared.addEventListener("change", syncPrivacyControls);
      fields.closePrivacyDialog.addEventListener("click", closePrivacyDialog);
      fields.cancelPrivacy.addEventListener("click", closePrivacyDialog);
      fields.privacyDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closePrivacyDialog();
      });
      fields.editMemberForm.addEventListener("submit", saveMemberProfile);
      fields.closeEditMemberDialog.addEventListener("click", closeEditMemberDialog);
      fields.cancelEditMember.addEventListener("click", closeEditMemberDialog);
      fields.editMemberDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeEditMemberDialog();
      });
      fields.archiveMemberForm.addEventListener("submit", archiveMemberAccount);
      fields.closeArchiveMemberDialog.addEventListener("click", closeArchiveMemberDialog);
      fields.cancelArchiveMember.addEventListener("click", closeArchiveMemberDialog);
      fields.archiveMemberDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeArchiveMemberDialog();
      });
      fields.refreshClub.addEventListener("click", () => loadClub({ announce: true }));
      fields.clubModeTabs.addEventListener("click", changeClubMode);
      fields.clubMemberTabs.addEventListener("click", selectClubCatalog);
      fields.clubLoadMore.addEventListener("click", showMoreClubItems);
      fields.backToCollections.addEventListener("click", closeCollectionDetail);
      fields.collectionFollowButton.addEventListener("click", toggleCollectionFollow);
      fields.selectMissingCollectionItems.addEventListener("change", toggleMissingCollectionSelection);
      fields.collectionItems.addEventListener("change", changeCollectionSelection);
      fields.addCollectionSelection.addEventListener("click", addSelectedCollectionItems);
      fields.addMissingCollectionItems.addEventListener("click", addMissingCollectionItems);
      fields.closeSharedDetail.addEventListener("click", closeSharedDetail);
      fields.sharedDetailDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeSharedDetail();
      });
      fields.sharedDetailDialog.addEventListener("click", (event) => {
        if (event.target === fields.sharedDetailDialog) closeSharedDetail();
      });
      fields.refreshCuration.addEventListener("click", () => loadCurationQueue({ announce: true }));
      fields.inboxView.addEventListener("click", handleCurationClick);
      fields.inboxModeTabs.addEventListener("click", changeInboxMode);
      fields.scannerQueue.addEventListener("click", selectScannerQueueItem);
      fields.scannerQueue.addEventListener("keydown", moveScannerQueueSelection);
      fields.scannerQueueFilters.addEventListener("click", changeScannerQueueFilter);
      fields.scannerQueueSearch.addEventListener("input", searchScannerQueue);
      fields.scannerQueueDetail.addEventListener("click", handleScannerReviewAction);
      fields.scannerQueueDetail.addEventListener("submit", handleScannerReviewAction);
      fields.refreshScannerQueue.addEventListener("click", () => loadScannerQueue({ announce: true }));
      fields.persistScannerHistory.checked = scannerHistoryMode === "persistent";
      fields.persistScannerHistory.nextElementSibling.textContent = scannerHistoryMode === "persistent"
        ? "Historial persistente"
        : "Sólo esta sesión";
      fields.persistScannerHistory.addEventListener("change", changeScannerHistoryMode);
      fields.clearScannerHistory.addEventListener("click", clearScannerHistory);
      fields.importInboxPanel.addEventListener("click", handleImportClick);
      fields.importSourceForm.addEventListener("submit", analyzeImportSource);
      fields.importApplyForm.addEventListener("submit", applySelectedImport);
      fields.importFile.addEventListener("change", changeImportFile);
      fields.importFormat.addEventListener("change", refreshImportMapping);
      fields.importContent.addEventListener("blur", refreshImportMapping);
      fields.importPreviewRows.addEventListener("change", changeImportSelection);
      fields.selectVisibleImportItems.addEventListener("change", toggleVisibleImportItems);
      fields.persistCurationHistory.checked = curationHistoryMode === "persistent";
      fields.persistCurationHistory.nextElementSibling.textContent = curationHistoryMode === "persistent"
        ? "Historial persistente"
        : "Sólo esta sesión";
      fields.persistCurationHistory.addEventListener("change", changeCurationHistoryMode);
      fields.clearCurationHistory.addEventListener("click", clearCurationHistory);
      fields.autoResolveCuration.addEventListener("click", autoResolveDuplicates);
      fields.randomButton.addEventListener("click", openRandomDetail);
      fields.randomCatalogOnly.addEventListener("change", () => changeRandomScope(fields.randomCatalogOnly));
      fields.cancelSearch.addEventListener("click", cancelExternalSearch);
      fields.reviewPrevious.addEventListener("click", previousWikiReview);
      fields.reviewNext.addEventListener("click", nextWikiReview);
      fields.backToCollection.addEventListener("click", () => {
        goToCollectionRoot();
      });
      fields.externalSource.addEventListener("change", renderDatabaseMenu);
      fields.clearFilters.addEventListener("click", clearFilters);
      [
        [fields.decadeFilter, "decade"],
        [fields.genreFilter, "genre"],
        [fields.directorFilter, "director"],
        [fields.sourceFilter, "source"]
      ].forEach(([field, filter]) => field.addEventListener("change", () => {
        if (!field.value) return;
        setCollectionFilterValue(filter, field.value, true);
        field.value = "";
        collectionFiltersChanged();
      }));
      fields.applyYearRange.addEventListener("click", applyCollectionYearRange);
      [fields.yearFromFilter, fields.yearToFilter].forEach((field) => field.addEventListener("keydown", (event) => {
        if (event.key === "Enter") applyCollectionYearRange();
      }));
      fields.clearManualSearch.addEventListener("click", () => clearManualSearch());
      fields.startWikiReview.addEventListener("click", () => goToInbox("missing_link"));
      fields.previousWikiReview.addEventListener("click", previousWikiReview);
      fields.nextWikiReview.addEventListener("click", nextWikiReview);
      fields.randomizeView.addEventListener("click", randomizeView);
      fields.resetOrder.addEventListener("click", resetViewOrder);
      fields.showDuplicates.addEventListener("click", () => goToInbox("duplicate"));
      fields.closeDetail.addEventListener("click", closeDetail);
      fields.detailDrawer.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeDetail();
      });
      fields.detailDrawer.addEventListener("click", (event) => {
        if (event.target === fields.detailDrawer) closeDetail();
      });
      fields.detailBody.addEventListener("input", handleDetailFormMutation);
      fields.detailBody.addEventListener("change", handleDetailFormMutation);
      fields.keepEditingDetail.addEventListener("click", keepEditingDetail);
      fields.discardDetailChanges.addEventListener("click", discardDetailChanges);
      fields.saveDetailChanges.addEventListener("click", saveDetailChanges);
      fields.unsavedDetailDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        keepEditingDetail();
      });
      fields.unsavedDetailDialog.addEventListener("click", (event) => {
        if (event.target === fields.unsavedDetailDialog) keepEditingDetail();
      });
      fields.catalogLoadMore.addEventListener("click", showMoreCatalogItems);
      fields.closeDescriptionDialog.addEventListener("click", closeDescriptionDialog);
      fields.descriptionDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeDescriptionDialog();
      });
      fields.descriptionDialog.addEventListener("close", restoreDescriptionFocus);
      fields.closeMergeComparator.addEventListener("click", () => closeMergeComparator());
      fields.cancelMergeComparator.addEventListener("click", () => closeMergeComparator());
      fields.confirmReviewedMerge.addEventListener("click", submitReviewedMerge);
      fields.mergeShowAllFields.addEventListener("change", renderMergeComparator);
      fields.mergeSurvivorControl.addEventListener("change", changeMergeSurvivor);
      fields.mergeComparatorFields.addEventListener("change", changeMergeChoice);
      fields.mergeComparatorDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeMergeComparator();
      });
      fields.mergeComparatorDialog.addEventListener("click", (event) => {
        if (event.target === fields.mergeComparatorDialog) closeMergeComparator();
      });
      fields.query.addEventListener("keydown", (event) => {
        if (event.key === "Enter") runSearch();
        if (event.key === "Escape") clearManualSearch();
      });
      document.addEventListener("visibilitychange", handleVisibilityChange);
      document.addEventListener("keydown", handleKeyboardModality, true);
      document.addEventListener("pointerdown", handlePointerModality, true);
      window.addEventListener("beforeunload", handleBeforeUnload);
      window.addEventListener("popstate", restoreRoute);
      document.addEventListener("load", handlePosterLoad, true);
      document.addEventListener("error", handlePosterError, true);
      document.addEventListener("click", handleDelegatedClick);
      fields.sort.addEventListener("input", () => {
        setRandomOrder([]);
        setCatalogVisibleCount(CATALOG_PAGE_SIZE);
        render();
        syncCollectionRoute("push");
      });
      setInboxMode(inboxMode, { loadData: false });
      load();

      // tests/browser/test_ui_browser.py drives these directly via page.evaluate()
      // as a shortcut past UI paths that are inconvenient to script (e.g. reaching
      // the description dialog without a live external search result). ES modules
      // don't leak bindings to the page's global scope like the old flat script did,
      // so re-attach only the handful Playwright actually calls this way.
      window.openDetail = openDetail;
      window.closeDetail = closeDetail;
      window.openSearchDescription = openSearchDescription;

