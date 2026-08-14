const API_TOKEN = document.querySelector('[name="movie-inbox-token"]').content;
      let currentIdentity = null;
      let members = [];
      let archivedMembers = [];
      let membersLoading = false;
      let editingMemberId = "";
      let archivingMemberId = "";
      let privacyPreferences = {
        catalog_shared: false,
        share_status: false,
        share_watched_at: false,
        share_history: false,
        share_rating: false,
        share_review: false
      };
      let clubCatalogs = [];
      let selectedClubUserId = "";
      let sharedCatalog = null;
      let clubMode = storedClubMode();
      let curatedCollections = [];
      let selectedCollectionId = "";
      let selectedCollection = null;
      let selectedCollectionItems = new Set();
      let clubLoading = false;
      let clubVisibleCount = 24;
      let items = [];
      let catalogSearchIndex = new WeakMap();
      let catalogMetrics = emptyCatalogMetrics();
      let catalogRevision = 0;
      let editorialRevision = 0;
      let lastCatalogGridKey = "";
      let lastEditorialRenderRevision = -1;
      let sourceFiles = [];
      let manualResults = [];
      let selectedManualIndex = null;
      let selectedExistingIdForSearch = null;
      let manualSearchSource = "all";
      let catalogMergeResults = [];
      let wikiReviewQueue = [];
      let wikiReviewIndex = 0;
      let randomOrder = [];
      let selectedDetailId = "";
      let detailReturnFocus = null;
      let descriptionReturnFocus = null;
      let detailReturnCardId = "";
      let detailNavigationIds = [];
      let detailNavigationMode = "catalog";
      let detailNavigationLabel = "Colección";
      let detailPersonalEditing = false;
      let detailDirtyScopes = new Set();
      let detailFeedbackState = { message: "", tone: "" };
      let detailFeedbackTimer = null;
      let pendingDetailTransition = null;
      let curationCases = [];
      let curationCounts = { pending: 0, duplicates: 0, missing_link: 0, deferred: 0, scanner: 0 };
      let curationFilter = "pending";
      let selectedCurationCaseId = "";
      let curationLoading = false;
      let curationHistory = [];
      let curationHistoryLoading = false;
      let curationHistoryMode = storedHistoryMode();
      let inboxMode = storedInboxMode();
      let importDrafts = [];
      let selectedImportDraft = null;
      let selectedImportItems = new Set();
      let importFilter = "all";
      let importDestination = "catalog";
      let importInputMode = "file";
      let importLoading = false;
      let importVisibleCount = 200;
      let managedLibraries = [];
      let scannerConfigured = false;
      let scannerAllowedRoots = [];
      let selectedLibraryId = "";
      let librariesLoading = false;
      let editingLibraryId = "";
      let browsedLibraryPath = "";
      let parentLibraryPath = "";
      let activeLibraryRunId = "";
      let libraryRunPollTimer = null;
      let scannerQueue = [];
      let selectedScannerItemId = "";
      let scannerQueueLoading = false;
      let scannerQueueFilter = "all";
      let scannerQueueQuery = "";
      let scannerCreateConflicts = new Map();
      let mergeReview = null;
      let mergeContext = null;
      let mergeChoices = {};
      let mergeTouchedChoices = new Set();
      let mergeSubmitting = false;
      let mergeRequestSequence = 0;
      let activeQuery = "";
      let collectionSearchMode = "browse";
      let writeJsonPath = "";
      let currentView = "home";
      let manualVisibleCount = 6;
      let manualSourceVisibleCounts = {};
      let catalogMergeVisibleCount = 6;
      let externalSourcesLastUsed = [];
      let externalSourcesAttempted = [];
      let externalSearchController = null;
      let externalSourceSearchStates = {};
      let duplicatesOnly = false;
      let collectionFilters = {
        status: new Set(),
        availability: new Set(),
        kind: new Set(),
        source: new Set(),
        decade: new Set(),
        genre: new Set(),
        director: new Set(),
        record: new Set(),
        release_day: new Set()
      };
      let collectionYearRange = { from: "", to: "" };
      let catalogVisibleCount = 36;
      let externalHealth = { sources: {}, cache: {} };
      let editorialHome = { generated_for: "", featured: [], hero: null, sections: [], warnings: [] };
      const editorialFeaturedCache = new Map();
      let spotlightIndex = 0;
      let imageCacheStatus = null;
      let imageCacheStatusLoading = false;
      let imageCacheStatusTimer = null;
      let routeRestored = false;
      const SEARCH_PAGE_SIZE = 6;
      const CATALOG_PAGE_SIZE = 36;
      const CLUB_PAGE_SIZE = 24;
      const SEARCH_TIMEOUT_MS = 10000;
      const EXTERNAL_SEARCH_SOURCES = ["wikipedia", "imdb", "filmaffinity"];
      const EXTERNAL_SOURCE_LABELS = {
        wikipedia: ["Wikipedia", "Artículos y datos enciclopédicos"],
        imdb: ["IMDb", "Títulos internacionales y reparto"],
        filmaffinity: ["FilmAffinity", "Referencias en español"]
      };
      externalSourceSearchStates = emptyExternalSourceSearchStates();
      const IMAGE_CACHE_STATUS_INTERVAL_MS = 5000;
      const IMPORT_MAX_BYTES = 8 * 1024 * 1024;
      const IMPORT_PREVIEW_PAGE_SIZE = 200;
      const IMPORT_COLUMN_FIELDS = [
        ["title", "Título"],
        ["url", "URL"],
        ["year", "Año"],
        ["kind", "Tipo"],
        ["status", "Estado"],
        ["watched_at", "Fecha de vista"],
        ["rating", "Puntaje"],
        ["review", "Review"],
        ["en_catalogo", "Disponibilidad declarada"]
      ];
      const COLLECTION_MULTI_FILTER_KEYS = [
        "status", "availability", "kind", "source", "decade", "genre", "director", "record", "release_day"
      ];
      const COLLECTION_ROUTE_KEYS = [
        "q", ...COLLECTION_MULTI_FILTER_KEYS, "year_from", "year_to", "sort", "duplicates", "external"
      ];

      async function apiFetch(url, options = {}) {
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
      const fields = {
        query: document.querySelector("#query"),
        externalSource: document.querySelector("#externalSource"),
        searchButton: document.querySelector("#searchButton"),
        homeButton: document.querySelector("#homeButton"),
        catalogButton: document.querySelector("#catalogButton"),
        inboxButton: document.querySelector("#inboxButton"),
        clubButton: document.querySelector("#clubButton"),
        inboxBadge: document.querySelector("#inboxBadge"),
        adminButton: document.querySelector("#adminButton"),
        systemMenu: document.querySelector("#systemMenu"),
        currentUserInitial: document.querySelector("#currentUserInitial"),
        currentUserLabel: document.querySelector("#currentUserLabel"),
        currentUserName: document.querySelector("#currentUserName"),
        currentCatalogName: document.querySelector("#currentCatalogName"),
        currentUserRole: document.querySelector("#currentUserRole"),
        privacyButton: document.querySelector("#privacyButton"),
        logoutButton: document.querySelector("#logoutButton"),
        searchConsole: document.querySelector(".search-console"),
        collectionUtilityMenu: document.querySelector(".collection-view .utility-menu"),
        randomButton: document.querySelector("#randomButton"),
        randomCatalogOnly: document.querySelector("#randomCatalogOnly"),
        randomScopeLabel: document.querySelector("#randomScopeLabel"),
        homeView: document.querySelector("#homeView"),
        clubView: document.querySelector("#clubView"),
        inboxView: document.querySelector("#inboxView"),
        inboxModeTabs: document.querySelector("#inboxModeTabs"),
        inboxCurationMode: document.querySelector("#inboxCurationMode"),
        inboxImportsMode: document.querySelector("#inboxImportsMode"),
        inboxScannerMode: document.querySelector("#inboxScannerMode"),
        curationInboxPanel: document.querySelector("#curationInboxPanel"),
        importInboxPanel: document.querySelector("#importInboxPanel"),
        scannerInboxPanel: document.querySelector("#scannerInboxPanel"),
        importDraftCount: document.querySelector("#importDraftCount"),
        scannerQueueCount: document.querySelector("#scannerQueueCount"),
        scannerQueueMeta: document.querySelector("#scannerQueueMeta"),
        scannerQueueFilters: document.querySelector("#scannerQueueFilters"),
        scannerAllCount: document.querySelector("#scannerAllCount"),
        scannerReviewCount: document.querySelector("#scannerReviewCount"),
        scannerNewCount: document.querySelector("#scannerNewCount"),
        scannerQueueSearch: document.querySelector("#scannerQueueSearch"),
        scannerQueue: document.querySelector("#scannerQueue"),
        scannerQueueDetail: document.querySelector("#scannerQueueDetail"),
        refreshScannerQueue: document.querySelector("#refreshScannerQueue"),
        collectionView: document.querySelector("#collectionView"),
        adminView: document.querySelector("#adminView"),
        homeDate: document.querySelector("#homeDate"),
        homeDateToday: document.querySelector("#homeDateToday"),
        homeDateYesterday: document.querySelector("#homeDateYesterday"),
        homeSections: document.querySelector("#homeSections"),
        homeFeedback: document.querySelector("#homeFeedback"),
        homeEmpty: document.querySelector("#homeEmpty"),
        refreshClub: document.querySelector("#refreshClub"),
        clubModeTabs: document.querySelector("#clubModeTabs"),
        clubCollectionsMode: document.querySelector("#clubCollectionsMode"),
        clubMembersMode: document.querySelector("#clubMembersMode"),
        clubCollectionsCount: document.querySelector("#clubCollectionsCount"),
        clubMembersCount: document.querySelector("#clubMembersCount"),
        clubMembersPanel: document.querySelector("#clubMembersPanel"),
        clubMemberTabs: document.querySelector("#clubMemberTabs"),
        clubFeedback: document.querySelector("#clubFeedback"),
        clubCatalogPanel: document.querySelector("#clubCatalogPanel"),
        clubLoadMore: document.querySelector("#clubLoadMore"),
        clubCollectionsPanel: document.querySelector("#clubCollectionsPanel"),
        collectionDirectory: document.querySelector("#collectionDirectory"),
        followedCollectionsSummary: document.querySelector("#followedCollectionsSummary"),
        collectionList: document.querySelector("#collectionList"),
        collectionDetailPanel: document.querySelector("#collectionDetailPanel"),
        backToCollections: document.querySelector("#backToCollections"),
        collectionDetailKicker: document.querySelector("#collectionDetailKicker"),
        collectionDetailTitle: document.querySelector("#collectionDetailTitle"),
        collectionDetailDescription: document.querySelector("#collectionDetailDescription"),
        collectionDetailSource: document.querySelector("#collectionDetailSource"),
        collectionFollowButton: document.querySelector("#collectionFollowButton"),
        collectionStats: document.querySelector("#collectionStats"),
        selectMissingCollectionItems: document.querySelector("#selectMissingCollectionItems"),
        collectionSelectionSummary: document.querySelector("#collectionSelectionSummary"),
        addCollectionSelection: document.querySelector("#addCollectionSelection"),
        addMissingCollectionItems: document.querySelector("#addMissingCollectionItems"),
        collectionItems: document.querySelector("#collectionItems"),
        refreshCuration: document.querySelector("#refreshCuration"),
        curationPendingCount: document.querySelector("#curationPendingCount"),
        curationDuplicateCount: document.querySelector("#curationDuplicateCount"),
        curationMissingCount: document.querySelector("#curationMissingCount"),
        curationDeferredCount: document.querySelector("#curationDeferredCount"),
        curationHistoryCount: document.querySelector("#curationHistoryCount"),
        persistCurationHistory: document.querySelector("#persistCurationHistory"),
        clearCurationHistory: document.querySelector("#clearCurationHistory"),
        curationFeedback: document.querySelector("#curationFeedback"),
        curationQueueTitle: document.querySelector("#curationQueueTitle"),
        curationQueueMeta: document.querySelector("#curationQueueMeta"),
        curationQueue: document.querySelector("#curationQueue"),
        curationDetail: document.querySelector("#curationDetail"),
        newImportDraft: document.querySelector("#newImportDraft"),
        importDraftList: document.querySelector("#importDraftList"),
        importSourcePanel: document.querySelector("#importSourcePanel"),
        importReviewPanel: document.querySelector("#importReviewPanel"),
        importSourceForm: document.querySelector("#importSourceForm"),
        importInputModes: document.querySelector("#importInputModes"),
        importFileInputPanel: document.querySelector("#importFileInputPanel"),
        importPasteInputPanel: document.querySelector("#importPasteInputPanel"),
        importFile: document.querySelector("#importFile"),
        importFileMeta: document.querySelector("#importFileMeta"),
        importSourceName: document.querySelector("#importSourceName"),
        importContent: document.querySelector("#importContent"),
        importFormat: document.querySelector("#importFormat"),
        analyzeImport: document.querySelector("#analyzeImport"),
        importCsvMapping: document.querySelector("#importCsvMapping"),
        importCsvFields: document.querySelector("#importCsvFields"),
        importSourceFeedback: document.querySelector("#importSourceFeedback"),
        importReviewKicker: document.querySelector("#importReviewKicker"),
        importReviewTitle: document.querySelector("#importReviewTitle"),
        importReviewMeta: document.querySelector("#importReviewMeta"),
        deleteImportDraft: document.querySelector("#deleteImportDraft"),
        importMetrics: document.querySelector("#importMetrics"),
        importStateFilters: document.querySelector("#importStateFilters"),
        selectVisibleImportItems: document.querySelector("#selectVisibleImportItems"),
        importPreviewRows: document.querySelector("#importPreviewRows"),
        importPreviewEmpty: document.querySelector("#importPreviewEmpty"),
        loadMoreImportRows: document.querySelector("#loadMoreImportRows"),
        importApplyForm: document.querySelector("#importApplyForm"),
        importDestinationModes: document.querySelector("#importDestinationModes"),
        importCollectionDestination: document.querySelector("#importCollectionDestination"),
        importPersonalOptions: document.querySelector("#importPersonalOptions"),
        importCollectionOptions: document.querySelector("#importCollectionOptions"),
        importCollectionTitle: document.querySelector("#importCollectionTitle"),
        importCollectionDescription: document.querySelector("#importCollectionDescription"),
        importSelectionSummary: document.querySelector("#importSelectionSummary"),
        applyImport: document.querySelector("#applyImport"),
        importApplyFeedback: document.querySelector("#importApplyFeedback"),
        catalogSection: document.querySelector("#catalogSection"),
        spotlight: document.querySelector("#spotlight"),
        spotlightStage: document.querySelector("#spotlightStage"),
        searchContext: document.querySelector("#searchContext"),
        searchContextText: document.querySelector("#searchContextText"),
        cancelSearch: document.querySelector("#cancelSearch"),
        reviewPrevious: document.querySelector("#reviewPrevious"),
        reviewNext: document.querySelector("#reviewNext"),
        backToCollection: document.querySelector("#backToCollection"),
        statusQuickFilters: document.querySelector("#statusQuickFilters"),
        availabilityQuickFilters: document.querySelector("#availabilityQuickFilters"),
        kindQuickFilters: document.querySelector("#kindQuickFilters"),
        advancedFiltersMenu: document.querySelector("#advancedFiltersMenu"),
        advancedFilterCount: document.querySelector("#advancedFilterCount"),
        decadeFilter: document.querySelector("#decadeFilter"),
        genreFilter: document.querySelector("#genreFilter"),
        directorFilter: document.querySelector("#directorFilter"),
        sourceFilter: document.querySelector("#sourceFilter"),
        yearFromFilter: document.querySelector("#yearFromFilter"),
        yearToFilter: document.querySelector("#yearToFilter"),
        applyYearRange: document.querySelector("#applyYearRange"),
        sort: document.querySelector("#sort"),
        activeFilters: document.querySelector("#activeFilters"),
        clearFilters: document.querySelector("#clearFilters"),
        catalogSummary: document.querySelector("#catalogSummary"),
        grid: document.querySelector("#grid"),
        stats: document.querySelector("#stats"),
        total: document.querySelector("#total"),
        catalogCount: document.querySelector("#catalogCount"),
        watchedCount: document.querySelector("#watchedCount"),
        toWatchCount: document.querySelector("#toWatchCount"),
        ratedCount: document.querySelector("#ratedCount"),
        withImage: document.querySelector("#withImage"),
        wikiLinks: document.querySelector("#wikiLinks"),
        withoutWiki: document.querySelector("#withoutWiki"),
        imdbLinks: document.querySelector("#imdbLinks"),
        faLinks: document.querySelector("#faLinks"),
        duplicateCount: document.querySelector("#duplicateCount"),
        sourceFiles: document.querySelector("#sourceFiles"),
        startWikiReview: document.querySelector("#startWikiReview"),
        previousWikiReview: document.querySelector("#previousWikiReview"),
        nextWikiReview: document.querySelector("#nextWikiReview"),
        wikiReviewStatus: document.querySelector("#wikiReviewStatus"),
        randomizeView: document.querySelector("#randomizeView"),
        resetOrder: document.querySelector("#resetOrder"),
        showDuplicates: document.querySelector("#showDuplicates"),
        clearManualSearch: document.querySelector("#clearManualSearch"),
        manualSearchStatus: document.querySelector("#manualSearchStatus"),
        manualSearchResults: document.querySelector("#manualSearchResults"),
        externalSearchSection: document.querySelector("#externalSearchSection"),
        catalogMergeSection: document.querySelector("#catalogMergeSection"),
        catalogMergeKicker: document.querySelector("#catalogMergeKicker"),
        catalogMergeTitle: document.querySelector("#catalogMergeTitle"),
        catalogMergeStatus: document.querySelector("#catalogMergeStatus"),
        catalogMergeResults: document.querySelector("#catalogMergeResults"),
        databaseCatalogPanel: document.querySelector("#databaseCatalogPanel"),
        databaseExternalPanel: document.querySelector("#databaseExternalPanel"),
        imageCacheStatus: document.querySelector("#imageCacheStatus"),
        catalogExportActions: document.querySelector("#catalogExportActions"),
        catalogExportFeedback: document.querySelector("#catalogExportFeedback"),
        createLibraryButton: document.querySelector("#createLibraryButton"),
        libraryConfiguration: document.querySelector("#libraryConfiguration"),
        libraryFeedback: document.querySelector("#libraryFeedback"),
        libraryList: document.querySelector("#libraryList"),
        libraryDialog: document.querySelector("#libraryDialog"),
        libraryForm: document.querySelector("#libraryForm"),
        libraryDialogTitle: document.querySelector("#libraryDialogTitle"),
        libraryName: document.querySelector("#libraryName"),
        libraryRootPath: document.querySelector("#libraryRootPath"),
        libraryRootHint: document.querySelector("#libraryRootHint"),
        browseLibraryPath: document.querySelector("#browseLibraryPath"),
        checkLibraryPath: document.querySelector("#checkLibraryPath"),
        libraryPathFeedback: document.querySelector("#libraryPathFeedback"),
        libraryPathBrowser: document.querySelector("#libraryPathBrowser"),
        libraryPathBrowserTitle: document.querySelector("#libraryPathBrowserTitle"),
        libraryPathBrowserCurrent: document.querySelector("#libraryPathBrowserCurrent"),
        libraryPathParent: document.querySelector("#libraryPathParent"),
        useLibraryPath: document.querySelector("#useLibraryPath"),
        libraryPathDirectories: document.querySelector("#libraryPathDirectories"),
        librarySchedule: document.querySelector("#librarySchedule"),
        libraryMissingRatio: document.querySelector("#libraryMissingRatio"),
        libraryDialogFeedback: document.querySelector("#libraryDialogFeedback"),
        closeLibraryDialog: document.querySelector("#closeLibraryDialog"),
        cancelLibraryDialog: document.querySelector("#cancelLibraryDialog"),
        submitLibrary: document.querySelector("#submitLibrary"),
        createMemberButton: document.querySelector("#createMemberButton"),
        memberCount: document.querySelector("#memberCount"),
        memberFeedback: document.querySelector("#memberFeedback"),
        memberList: document.querySelector("#memberList"),
        archivedMemberSection: document.querySelector("#archivedMemberSection"),
        archivedMemberCount: document.querySelector("#archivedMemberCount"),
        archivedMemberList: document.querySelector("#archivedMemberList"),
        memberDialog: document.querySelector("#memberDialog"),
        memberForm: document.querySelector("#memberForm"),
        memberUsername: document.querySelector("#memberUsername"),
        memberCatalogName: document.querySelector("#memberCatalogName"),
        memberTemporaryPassword: document.querySelector("#memberTemporaryPassword"),
        showMemberPassword: document.querySelector("#showMemberPassword"),
        memberDialogFeedback: document.querySelector("#memberDialogFeedback"),
        closeMemberDialog: document.querySelector("#closeMemberDialog"),
        cancelMemberDialog: document.querySelector("#cancelMemberDialog"),
        submitMember: document.querySelector("#submitMember"),
        temporaryPasswordDialog: document.querySelector("#temporaryPasswordDialog"),
        temporaryPasswordUsername: document.querySelector("#temporaryPasswordUsername"),
        temporaryPasswordValue: document.querySelector("#temporaryPasswordValue"),
        temporaryPasswordFeedback: document.querySelector("#temporaryPasswordFeedback"),
        copyTemporaryPassword: document.querySelector("#copyTemporaryPassword"),
        closeTemporaryPasswordDialog: document.querySelector("#closeTemporaryPasswordDialog"),
        finishTemporaryPassword: document.querySelector("#finishTemporaryPassword"),
        privacyDialog: document.querySelector("#privacyDialog"),
        privacyForm: document.querySelector("#privacyForm"),
        catalogShared: document.querySelector("#catalogShared"),
        shareStatus: document.querySelector("#shareStatus"),
        shareWatchedAt: document.querySelector("#shareWatchedAt"),
        shareHistory: document.querySelector("#shareHistory"),
        shareRating: document.querySelector("#shareRating"),
        shareReview: document.querySelector("#shareReview"),
        privacyFields: document.querySelector("#privacyFields"),
        privacyFeedback: document.querySelector("#privacyFeedback"),
        closePrivacyDialog: document.querySelector("#closePrivacyDialog"),
        cancelPrivacy: document.querySelector("#cancelPrivacy"),
        savePrivacy: document.querySelector("#savePrivacy"),
        editMemberDialog: document.querySelector("#editMemberDialog"),
        editMemberForm: document.querySelector("#editMemberForm"),
        editMemberUsername: document.querySelector("#editMemberUsername"),
        editMemberCatalogName: document.querySelector("#editMemberCatalogName"),
        editMemberFeedback: document.querySelector("#editMemberFeedback"),
        closeEditMemberDialog: document.querySelector("#closeEditMemberDialog"),
        cancelEditMember: document.querySelector("#cancelEditMember"),
        saveMemberProfile: document.querySelector("#saveMemberProfile"),
        archiveMemberDialog: document.querySelector("#archiveMemberDialog"),
        archiveMemberForm: document.querySelector("#archiveMemberForm"),
        archiveMemberUsernameLabel: document.querySelector("#archiveMemberUsernameLabel"),
        archiveMemberConfirmation: document.querySelector("#archiveMemberConfirmation"),
        archiveMemberFeedback: document.querySelector("#archiveMemberFeedback"),
        closeArchiveMemberDialog: document.querySelector("#closeArchiveMemberDialog"),
        cancelArchiveMember: document.querySelector("#cancelArchiveMember"),
        confirmArchiveMember: document.querySelector("#confirmArchiveMember"),
        sharedDetailDialog: document.querySelector("#sharedDetailDialog"),
        sharedDetailOwner: document.querySelector("#sharedDetailOwner"),
        sharedDetailBody: document.querySelector("#sharedDetailBody"),
        closeSharedDetail: document.querySelector("#closeSharedDetail"),
        detailDrawer: document.querySelector("#detailDrawer"),
        detailBody: document.querySelector("#detailBody"),
        closeDetail: document.querySelector("#closeDetail"),
        detailNavigation: document.querySelector("#detailNavigation"),
        detailFeedback: document.querySelector("#detailFeedback"),
        unsavedDetailDialog: document.querySelector("#unsavedDetailDialog"),
        keepEditingDetail: document.querySelector("#keepEditingDetail"),
        discardDetailChanges: document.querySelector("#discardDetailChanges"),
        saveDetailChanges: document.querySelector("#saveDetailChanges"),
        catalogLoadMore: document.querySelector("#catalogLoadMore"),
        descriptionDialog: document.querySelector("#descriptionDialog"),
        descriptionDialogTitle: document.querySelector("#descriptionDialogTitle"),
        descriptionDialogText: document.querySelector("#descriptionDialogText"),
        closeDescriptionDialog: document.querySelector("#closeDescriptionDialog"),
        mergeComparatorDialog: document.querySelector("#mergeComparatorDialog"),
        mergeComparatorTitle: document.querySelector("#mergeComparatorTitle"),
        mergeComparatorSubtitle: document.querySelector("#mergeComparatorSubtitle"),
        mergeSurvivorControl: document.querySelector("#mergeSurvivorControl"),
        mergeSurvivorLeft: document.querySelector("#mergeSurvivorLeft"),
        mergeSurvivorRight: document.querySelector("#mergeSurvivorRight"),
        mergeShowAllFields: document.querySelector("#mergeShowAllFields"),
        mergeComparatorSummary: document.querySelector("#mergeComparatorSummary"),
        mergeComparatorFeedback: document.querySelector("#mergeComparatorFeedback"),
        mergeComparatorFields: document.querySelector("#mergeComparatorFields"),
        mergeDecisionStatus: document.querySelector("#mergeDecisionStatus"),
        mergeDecisionMeta: document.querySelector("#mergeDecisionMeta"),
        closeMergeComparator: document.querySelector("#closeMergeComparator"),
        cancelMergeComparator: document.querySelector("#cancelMergeComparator"),
        confirmReviewedMerge: document.querySelector("#confirmReviewedMerge"),
        empty: document.querySelector("#empty")
      };

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
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
        syncCollectionRoute("push");
      });
      setInboxMode(inboxMode, { loadData: false });
      load();

      function handleDelegatedClick(event) {
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

      function handleKeyboardModality(event) {
        if (["Tab", "Enter", " "].includes(event.key)) document.body.dataset.inputMethod = "keyboard";
      }

      function handlePointerModality() {
        document.body.dataset.inputMethod = "pointer";
      }

      function runDetailAwareAction(target, action) {
        if (target.closest("#detailDrawer") && hasUnsavedDetailChanges()) {
          requestDetailTransition(action);
          return;
        }
        action();
      }

      async function load() {
        try {
          if (!currentIdentity) await loadIdentity();
          await loadCatalog();
        } catch (error) {
          console.error("[catalog-viewer] catalog load failed", error);
          fields.homeView.setAttribute("aria-busy", "false");
          fields.empty.textContent = `No se pudo cargar el catalogo: ${error.message || error}`;
          fields.empty.hidden = false;
        }
      }

      async function loadIdentity() {
        const response = await apiFetch("/api/session");
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        currentIdentity = payload;
        const user = payload.user || {};
        const catalog = payload.catalog || {};
        const username = user.username || "Owner";
        if (user.must_change_password) {
          window.location.replace("/password-change");
          throw new Error("password_change_required");
        }
        fields.currentUserInitial.textContent = username.slice(0, 2).toUpperCase();
        fields.currentUserLabel.textContent = username;
        fields.currentUserName.textContent = username;
        fields.currentCatalogName.textContent = catalog.name || "Mi catálogo";
        fields.currentUserRole.textContent = user.role === "owner" ? "Administrador" : "Miembro";
        fields.adminButton.hidden = user.role !== "owner";
        fields.importCollectionDestination.hidden = user.role !== "owner";
        fields.inboxScannerMode.hidden = user.role !== "owner";
        if (user.role !== "owner" && inboxMode === "scanner") {
          await setInboxMode("curation", { loadData: false });
        }
      }

      async function logout() {
        fields.logoutButton.disabled = true;
        fields.logoutButton.textContent = "Cerrando…";
        try {
          const response = await apiFetch("/auth/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}"
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          window.location.replace("/login");
        } catch (error) {
          if (error.message === "authentication_required") return;
          fields.logoutButton.disabled = false;
          fields.logoutButton.textContent = "Reintentar cierre";
        }
      }

      async function loadMembers({ announce = false } = {}) {
        if (membersLoading || currentIdentity?.user?.role !== "owner") return;
        membersLoading = true;
        fields.memberList.setAttribute("aria-busy", "true");
        fields.createMemberButton.disabled = true;
        if (announce) setMemberFeedback("Actualizando miembros\u2026");
        try {
          const response = await apiFetch("/api/members");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          members = payload.members || [];
          archivedMembers = payload.archived || [];
          renderMembers();
          if (announce) setMemberFeedback("Miembros actualizados.");
        } catch (error) {
          setMemberFeedback(memberErrorMessage(error.message), "error");
        } finally {
          membersLoading = false;
          fields.memberList.removeAttribute("aria-busy");
          fields.createMemberButton.disabled = false;
        }
      }

      async function loadLibraries({ announce = false } = {}) {
        if (librariesLoading || currentIdentity?.user?.role !== "owner") return;
        librariesLoading = true;
        fields.libraryList.setAttribute("aria-busy", "true");
        fields.createLibraryButton.disabled = true;
        if (announce) setLibraryFeedback("Actualizando bibliotecas…");
        try {
          const response = await apiFetch("/api/libraries");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          scannerConfigured = Boolean(payload.configured);
          scannerAllowedRoots = payload.allowed_roots || [];
          managedLibraries = payload.libraries || [];
          curationCounts.scanner = Number(payload.queue_count || 0);
          if (!managedLibraries.some((entry) => entry.id === selectedLibraryId)) {
            selectedLibraryId = managedLibraries[0]?.id || "";
          }
          if (selectedLibraryId) await loadLibraryDetail(selectedLibraryId, { renderAfter: false });
          renderLibraryConfiguration();
          renderLibraries();
          syncCurationCounts();
          if (announce) setLibraryFeedback("Bibliotecas actualizadas.");
        } catch (error) {
          setLibraryFeedback(libraryErrorMessage(error.message), "error");
          fields.libraryList.innerHTML = `<div class="member-list-empty"><strong>Bibliotecas no disponibles</strong><span>Reintentá desde Actualizar datos.</span></div>`;
        } finally {
          librariesLoading = false;
          fields.libraryList.removeAttribute("aria-busy");
          fields.createLibraryButton.disabled = !scannerConfigured;
        }
      }

      async function loadLibraryDetail(libraryId, { renderAfter = true } = {}) {
        const response = await apiFetch(`/api/libraries/${encodeURIComponent(libraryId)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        const detail = payload.library;
        managedLibraries = managedLibraries.map((entry) => entry.id === detail.id ? detail : entry);
        if (renderAfter) renderLibraries();
        return detail;
      }

      function renderLibraryConfiguration() {
        if (!scannerConfigured) {
          fields.libraryConfiguration.dataset.state = "disabled";
          fields.libraryConfiguration.innerHTML = `<strong>Scanner administrado desactivado</strong><span>Reiniciá el servidor con al menos un <code>--library-root RUTA</code>.</span>`;
          fields.createLibraryButton.disabled = true;
          return;
        }
        fields.libraryConfiguration.dataset.state = "ready";
        fields.libraryConfiguration.innerHTML = `<strong>${scannerAllowedRoots.length} ${scannerAllowedRoots.length === 1 ? "raíz habilitada" : "raíces habilitadas"}</strong><span>${scannerAllowedRoots.map((root) => `<code>${escapeHtml(root)}</code>`).join(" · ")}</span>`;
      }

      function renderLibraries() {
        if (!managedLibraries.length) {
          fields.libraryList.innerHTML = `<div class="member-list-empty"><strong>Todavía no hay rutas bajo seguimiento</strong><span>Agregá una biblioteca y ejecutá primero un recorrido de prueba.</span></div>`;
          return;
        }
        fields.libraryList.innerHTML = managedLibraries.map((library) => {
          const selected = library.id === selectedLibraryId;
          const counts = library.counts || {};
          const running = (library.runs || []).find((run) => ["queued", "running"].includes(run.status))
            || (library.status === "scanning" ? { status: "running" } : null);
          const workflow = libraryWorkflow(library, running);
          const lastRun = (library.runs || [])[0];
          const resultOwnsPrimary = Boolean(
            selected
            && workflow.key === "ready_apply"
            && lastRun?.mode === "dry_run"
            && lastRun?.status === "completed"
          );
          const testAgain = !running && workflow.key === "applied"
            ? `<button class="quiet-action" type="button" data-library-action="test" data-library-id="${escapeAttr(library.id)}">Probar cambios</button>`
            : "";
          return `<article class="library-record${selected ? " is-selected" : ""}" data-library-id="${escapeAttr(library.id)}" data-workflow="${escapeAttr(workflow.key)}">
            <div class="library-record-main">
              <button class="library-record-identity" type="button" data-library-action="select" data-library-id="${escapeAttr(library.id)}" aria-expanded="${selected}">
                <span class="library-drive-mark" aria-hidden="true">${escapeHtml(workflow.marker)}</span>
                <span><strong>${escapeHtml(library.name || "Biblioteca")}</strong><code>${escapeHtml(library.root_path || "")}</code></span>
              </button>
              <div class="library-record-state">
                <span class="member-state ${libraryWorkflowClass(workflow.key)}">${escapeHtml(workflow.label)}</span>
                <span>${escapeHtml(workflow.note)}</span>
              </div>
              <dl class="library-record-metrics">
                <div><dt>Archivos</dt><dd>${Number(counts.files || 0)}</dd></div>
                <div><dt>Vinculados</dt><dd>${Number(counts.matched || 0)}</dd></div>
                <div><dt>Comparar</dt><dd>${Number(counts.review || 0)}</dd></div>
                <div><dt>Nuevos</dt><dd>${Number(counts.new || 0)}</dd></div>
              </dl>
              <div class="library-record-actions">
                ${libraryPrimaryAction(library, workflow, running)}
                ${testAgain}
                <button class="quiet-action" type="button" data-library-action="edit" data-library-id="${escapeAttr(library.id)}" ${running ? "disabled" : ""}>Editar</button>
                ${libraryAutomationControl(library, running)}
              </div>
            </div>
            ${selected ? libraryRunPanel(library, running, workflow, resultOwnsPrimary) : ""}
          </article>`;
        }).join("");
      }

      function libraryWorkflow(library, running) {
        const lastRun = (library.runs || [])[0];
        const scheduled = library.schedule !== "manual";
        const hasInventory = Number(library.last_scan_at || 0) > 0;
        if (running) {
          const knownMode = running.mode === "apply" || running.mode === "dry_run";
          const applying = running.mode === "apply";
          return {
            key: "running",
            marker: "RUN",
            label: !knownMode ? "Recorrido en curso" : applying ? "Aplicación en curso" : "Prueba en curso",
            note: !knownMode
              ? "Procesando la biblioteca"
              : applying
                ? "Actualizando inventario físico"
                : "Lectura sin cambios persistentes",
            action: "",
            actionLabel: !knownMode ? "Procesando recorrido…" : applying ? "Aplicando inventario…" : "Probando recorrido…"
          };
        }
        if (!library.verified_at) {
          return {
            key: "unverified",
            marker: "NEW",
            label: "Sin verificar",
            note: "Primero, una prueba de solo lectura",
            action: "test",
            actionLabel: "Probar recorrido"
          };
        }
        if (lastRun?.mode === "dry_run" && lastRun.status !== "completed") {
          return {
            key: "attention",
            marker: "!",
            label: "Requiere atención",
            note: "La última prueba no quedó lista para aplicar",
            action: "test",
            actionLabel: "Probar de nuevo"
          };
        }
        const testedAfterInventory = lastRun?.mode === "dry_run"
          && lastRun.status === "completed"
          && Number(lastRun.finished_at || lastRun.created_at || 0) >= Number(library.last_scan_at || 0);
        if (!hasInventory || testedAfterInventory) {
          return {
            key: "ready_apply",
            marker: "TEST",
            label: "Lista para aplicar",
            note: scheduled ? `Aplicá antes de habilitar ${scheduleLabel(library.schedule).toLowerCase()}` : "La prueba no modificó el inventario",
            action: "scan",
            actionLabel: "Aplicar inventario"
          };
        }
        if (["offline", "warning", "error"].includes(library.status)) {
          return {
            key: "attention",
            marker: "!",
            label: libraryStatusLabel(library.status),
            note: "Revisá el último recorrido antes de continuar",
            action: "test",
            actionLabel: "Probar de nuevo"
          };
        }
        const note = !scheduled
          ? "Escaneo manual"
          : library.active
            ? `${scheduleLabel(library.schedule)} · automático activo`
            : `${scheduleLabel(library.schedule)} · automático pausado`;
        return {
          key: "applied",
          marker: scheduled && library.active ? "AUTO" : "OK",
          label: "Inventario actualizado",
          note,
          action: "scan",
          actionLabel: "Escanear ahora"
        };
      }

      function libraryWorkflowClass(value) {
        if (["applied", "running", "ready_apply"].includes(value)) return "member-state-active";
        if (["unverified", "attention"].includes(value)) return "member-state-attention";
        return "member-state-disabled";
      }

      function libraryPrimaryAction(library, workflow, running) {
        if (running) {
          return `<button class="action-primary library-primary-main" type="button" disabled aria-busy="true">${escapeHtml(workflow.actionLabel)}</button>`;
        }
        if (!workflow.action) return "";
        return `<button class="action-primary library-primary-main" type="button" data-library-action="${escapeAttr(workflow.action)}" data-library-id="${escapeAttr(library.id)}">${escapeHtml(workflow.actionLabel)}</button>`;
      }

      function libraryAutomationControl(library, running) {
        if (library.schedule === "manual" || !library.last_scan_at) return "";
        return `<label class="library-automation-toggle${library.active ? " is-active" : ""}">
          <input type="checkbox" data-library-action="toggle" data-library-id="${escapeAttr(library.id)}" aria-label="Escaneo automático de ${escapeAttr(library.name || "biblioteca")}" ${library.active ? "checked" : ""} ${running ? "disabled" : ""}>
          <span class="library-toggle-track" aria-hidden="true"><span></span></span>
          <span>Escaneo automático</span>
        </label>`;
      }

      function libraryRunPanel(library, running, workflow, resultOwnsPrimary) {
        const runs = (library.runs || []).slice(0, 5);
        const lastRun = runs[0];
        return `<div class="library-run-panel">
          <div class="library-run-summary">
            <div><span>Último recorrido</span><strong>${lastRun ? formatLibraryTime(lastRun.finished_at || lastRun.created_at) : "Sin recorridos"}</strong></div>
            <div><span>Próxima ejecución</span><strong>${escapeHtml(libraryNextRunLabel(library))}</strong></div>
            <div><span>Protección de bajas</span><strong>${Math.round(Number(library.max_missing_ratio || 0) * 100)}%</strong></div>
          </div>
          ${running ? `<div class="library-running" role="status"><span class="library-running-signal" aria-hidden="true"></span><strong>${running.status === "queued" ? "Recorrido en cola" : "Leyendo biblioteca"}</strong><span>Podés seguir usando Movie Inbox.</span></div>` : ""}
          ${lastRun && !running ? libraryRunResult(lastRun, library, workflow, resultOwnsPrimary) : ""}
          ${runs.length ? `<details class="library-run-history"><summary>Historial de recorridos</summary><div>${runs.map((run) => `<div><span>${escapeHtml(runModeLabel(run))}</span><strong>${escapeHtml(runStatusLabel(run.status))}</strong><time>${formatLibraryTime(run.finished_at || run.created_at)}</time></div>`).join("")}</div></details>` : ""}
          <div class="library-secondary-actions">
            <button class="text-action" type="button" data-library-action="scanner" data-library-id="${escapeAttr(library.id)}">Abrir pendientes</button>
            <button class="text-action danger-action" type="button" data-library-action="delete" data-library-id="${escapeAttr(library.id)}" ${running ? "disabled" : ""}>Quitar seguimiento</button>
          </div>
        </div>`;
      }

      function libraryNextRunLabel(library) {
        if (library.schedule === "manual") return "Sólo manual";
        if (!library.last_scan_at) return "Después de aplicar";
        if (!library.active) return "Automatización pausada";
        return library.next_scan_at ? formatLibraryTime(library.next_scan_at) : "Al iniciar el planificador";
      }

      function libraryRunResult(run, library, workflow, resultOwnsPrimary) {
        const summary = run.summary || {};
        const preview = run.preview || [];
        const parts = [
          `${Number(summary.discovered || 0)} archivos`,
          `${Number(summary.matched || 0)} vinculados`,
          `${Number(summary.review || 0)} para comparar`,
          `${Number(summary.new || 0)} nuevos`
        ];
        const errors = run.errors || [];
        const outcome = run.mode === "dry_run"
          ? run.status === "completed"
            ? "La prueba terminó sin modificar el inventario ni la disponibilidad."
            : "La prueba no modificó el inventario. Corregí las advertencias y volvé a probar."
          : run.status === "blocked"
            ? "La protección de bajas conservó el último inventario válido."
            : run.status === "completed"
              ? "El inventario compartido y la disponibilidad quedaron actualizados."
              : "Se aplicaron los resultados seguros y quedaron advertencias para revisar.";
        return `<div class="library-run-result" data-state="${escapeAttr(run.status || "")}">
          <strong>${escapeHtml(runStatusLabel(run.status))}</strong>
          <span>${escapeHtml(parts.join(" · "))}</span>
          ${errors.length ? `<details><summary>${errors.length} ${errors.length === 1 ? "advertencia" : "advertencias"}</summary><ul>${errors.slice(0, 8).map((error) => `<li>${escapeHtml(error)}</li>`).join("")}</ul></details>` : ""}
          ${preview.length ? `<details class="library-run-preview"><summary>Revisar muestra (${preview.length})</summary><div class="library-run-preview-list">${preview.map((item) => `
            <div class="library-run-preview-row">
              <span class="scanner-queue-state">${escapeHtml(libraryPreviewStateLabel(item.state))}</span>
              <strong>${escapeHtml(item.title || "Sin título detectado")}</strong>
              <span>${escapeHtml([item.year, importKindLabel(item.kind)].filter(Boolean).join(" · "))}</span>
              <code>${escapeHtml(item.relative_path || "")}</code>
            </div>`).join("")}</div></details>` : ""}
          <div class="library-run-outcome">
            <span>${escapeHtml(outcome)}</span>
            ${resultOwnsPrimary ? `<button class="action-primary library-primary-result" type="button" data-library-action="scan" data-library-id="${escapeAttr(library.id)}">${escapeHtml(workflow.actionLabel)}</button>` : ""}
          </div>
        </div>`;
      }

      function libraryPreviewStateLabel(value) {
        return { matched: "Vinculada", new: "Nueva", review: "Comparar", ignored: "Ignorada" }[value] || "Detectada";
      }

      async function handleLibraryAction(event) {
        const button = event.target.closest("[data-library-action]");
        if (!button) return;
        const library = managedLibraries.find((entry) => entry.id === button.dataset.libraryId);
        if (!library) return;
        const action = button.dataset.libraryAction;
        if (action === "select") {
          selectedLibraryId = selectedLibraryId === library.id ? "" : library.id;
          if (selectedLibraryId) await loadLibraryDetail(library.id);
          else renderLibraries();
          return;
        }
        if (action === "edit") {
          openLibraryDialog(library);
          return;
        }
        if (action === "scanner") {
          await goToInbox();
          await setInboxMode("scanner");
          return;
        }
        if (action === "delete") {
          const confirmed = confirm(`¿Quitar el seguimiento de "${library.name}"? El inventario verificado de esta ruta dejará de aportar disponibilidad.`);
          if (!confirmed) return;
          await deleteManagedLibrary(library);
          return;
        }
        button.disabled = true;
        try {
          if (action === "test" || action === "scan") {
            await queueLibraryRun(library, action === "test" ? "dry_run" : "apply");
          } else if (action === "toggle") {
            const active = button instanceof HTMLInputElement ? button.checked : !library.active;
            const response = await apiFetch(`/api/libraries/${encodeURIComponent(library.id)}/status`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ active })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
            setLibraryFeedback(payload.library.active ? `Escaneo automático activado para ${library.name}.` : `Escaneo automático pausado para ${library.name}.`);
            await loadLibraries();
          }
        } catch (error) {
          setLibraryFeedback(libraryErrorMessage(error.message), "error");
          renderLibraries();
        } finally {
          button.disabled = false;
        }
      }

      async function queueLibraryRun(library, mode) {
        const firstApply = mode === "apply" && !library.last_scan_at;
        setLibraryFeedback(
          mode === "dry_run"
            ? `Preparando una prueba de solo lectura para ${library.name}…`
            : firstApply
              ? `Aplicando el primer inventario de ${library.name}…`
              : `Actualizando el inventario de ${library.name}…`
        );
        const response = await apiFetch(`/api/libraries/${encodeURIComponent(library.id)}/runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        activeLibraryRunId = payload.run?.id || "";
        selectedLibraryId = library.id;
        await loadLibraryDetail(library.id);
        scheduleLibraryRunPoll(library.id);
      }

      function scheduleLibraryRunPoll(libraryId) {
        clearTimeout(libraryRunPollTimer);
        if (!activeLibraryRunId) return;
        libraryRunPollTimer = setTimeout(() => pollLibraryRun(libraryId), 1200);
      }

      async function pollLibraryRun(libraryId) {
        try {
          const response = await apiFetch(`/api/library-runs/${encodeURIComponent(activeLibraryRunId)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const run = payload.run || {};
          if (["queued", "running"].includes(run.status)) {
            scheduleLibraryRunPoll(libraryId);
            return;
          }
          activeLibraryRunId = "";
          await Promise.all([loadLibraries(), loadScannerQueue(), loadCatalog()]);
          const message = run.status === "completed"
            ? run.mode === "dry_run"
              ? "Prueba completada. El inventario no cambió."
              : "Inventario y disponibilidad actualizados."
            : run.status === "blocked"
              ? "No se aplicaron bajas: se conservó el último inventario válido."
              : run.mode === "dry_run"
                ? "La prueba terminó con advertencias y no modificó el inventario."
                : "El recorrido aplicado terminó con advertencias.";
          setLibraryFeedback(message, run.status === "completed" ? "" : "error");
        } catch (error) {
          activeLibraryRunId = "";
          setLibraryFeedback(libraryErrorMessage(error.message), "error");
        }
      }

      function openLibraryDialog(library = null) {
        editingLibraryId = library?.id || "";
        browsedLibraryPath = "";
        parentLibraryPath = "";
        fields.libraryForm.reset();
        fields.libraryDialogTitle.textContent = library ? "Editar biblioteca" : "Agregar biblioteca";
        fields.libraryName.value = library?.name || "";
        fields.libraryRootPath.value = library?.root_path || "";
        fields.libraryRootPath.disabled = Boolean(library);
        fields.browseLibraryPath.disabled = Boolean(library);
        fields.checkLibraryPath.disabled = Boolean(library);
        fields.libraryPathBrowser.hidden = true;
        fields.libraryPathDirectories.innerHTML = "";
        setLibraryPathFeedback("");
        fields.librarySchedule.value = library?.schedule || "manual";
        fields.libraryMissingRatio.value = Math.round(Number(library?.max_missing_ratio ?? 0.5) * 100);
        fields.libraryRootHint.textContent = library
          ? "Para cambiar la ruta, quitá el seguimiento y registrala nuevamente."
          : `Raíces habilitadas: ${scannerAllowedRoots.join(" · ")}`;
        setInlineFeedback(fields.libraryDialogFeedback, "");
        fields.libraryDialog.showModal();
        fields.libraryName.focus();
      }

      function closeLibraryDialog() {
        fields.libraryDialog.close();
        fields.libraryForm.reset();
        fields.libraryRootPath.disabled = false;
        fields.browseLibraryPath.disabled = false;
        fields.checkLibraryPath.disabled = false;
        fields.libraryPathBrowser.hidden = true;
        fields.libraryPathDirectories.innerHTML = "";
        browsedLibraryPath = "";
        parentLibraryPath = "";
        editingLibraryId = "";
        setLibraryPathFeedback("");
        setInlineFeedback(fields.libraryDialogFeedback, "");
      }

      async function browseManagedLibraryPath(path = "") {
        fields.browseLibraryPath.disabled = true;
        fields.libraryPathBrowser.hidden = false;
        fields.libraryPathDirectories.innerHTML = `<div class="library-path-empty">Leyendo carpetas permitidas…</div>`;
        setLibraryPathFeedback("");
        try {
          const response = await apiFetch(`/api/library-paths?path=${encodeURIComponent(String(path || "").trim())}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          browsedLibraryPath = payload.path || "";
          parentLibraryPath = payload.parent || "";
          fields.libraryPathBrowserTitle.textContent = browsedLibraryPath ? "Carpetas disponibles" : "Raíces permitidas";
          fields.libraryPathBrowserCurrent.textContent = browsedLibraryPath || "Elegí un disco o volumen configurado";
          fields.libraryPathParent.hidden = !parentLibraryPath;
          fields.useLibraryPath.hidden = !browsedLibraryPath;
          const directories = payload.directories || [];
          fields.libraryPathDirectories.innerHTML = directories.length
            ? directories.map((directory) => `<button class="library-path-directory" type="button" data-library-path="${escapeAttr(directory.path || "")}" ${directory.readable === false ? "disabled" : ""}>
                <span aria-hidden="true">▸</span>
                <strong>${escapeHtml(directory.name || directory.path || "Carpeta")}</strong>
                <small>${directory.readable === false ? "No disponible" : escapeHtml(directory.path || "")}</small>
              </button>`).join("")
            : `<div class="library-path-empty">Esta carpeta no contiene otras carpetas visibles. Podés usarla tal como está.</div>`;
        } catch (error) {
          browsedLibraryPath = "";
          parentLibraryPath = "";
          fields.libraryPathParent.hidden = true;
          fields.useLibraryPath.hidden = true;
          fields.libraryPathDirectories.innerHTML = `<div class="library-path-empty is-error">${escapeHtml(libraryErrorMessage(error.message))}</div>`;
        } finally {
          fields.browseLibraryPath.disabled = false;
        }
      }

      function handleLibraryPathDirectory(event) {
        const button = event.target.closest("[data-library-path]");
        if (!button || button.disabled) return;
        browseManagedLibraryPath(button.dataset.libraryPath || "");
      }

      function useBrowsedLibraryPath() {
        if (!browsedLibraryPath) return;
        fields.libraryRootPath.value = browsedLibraryPath;
        setLibraryPathFeedback("Ruta seleccionada. Comprobala antes de guardar.");
        fields.libraryRootPath.focus();
      }

      async function checkManagedLibraryPath() {
        const path = fields.libraryRootPath.value.trim();
        if (!path) {
          setLibraryPathFeedback("Elegí o escribí una ruta antes de comprobarla.", "error");
          fields.libraryRootPath.focus();
          return;
        }
        fields.checkLibraryPath.disabled = true;
        setLibraryPathFeedback("Comprobando acceso de lectura…");
        try {
          const response = await apiFetch("/api/library-paths/check", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          fields.libraryRootPath.value = payload.path || path;
          setLibraryPathFeedback(`Ruta disponible. Se encontraron ${payload.directory_count || 0} carpetas dentro.`, "success");
        } catch (error) {
          setLibraryPathFeedback(libraryErrorMessage(error.message), "error");
        } finally {
          fields.checkLibraryPath.disabled = false;
        }
      }

      function setLibraryPathFeedback(message, state = "") {
        fields.libraryPathFeedback.textContent = message;
        fields.libraryPathFeedback.dataset.state = state;
      }

      async function saveManagedLibrary(event) {
        event.preventDefault();
        fields.submitLibrary.disabled = true;
        setInlineFeedback(fields.libraryDialogFeedback, "Guardando…");
        const body = {
          name: fields.libraryName.value,
          schedule: fields.librarySchedule.value,
          max_missing_ratio: Number(fields.libraryMissingRatio.value || 50) / 100
        };
        if (!editingLibraryId) body.root_path = fields.libraryRootPath.value;
        const endpoint = editingLibraryId
          ? `/api/libraries/${encodeURIComponent(editingLibraryId)}/update`
          : "/api/libraries";
        try {
          const response = await apiFetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const name = payload.library?.name || body.name;
          selectedLibraryId = payload.library?.id || editingLibraryId;
          closeLibraryDialog();
          setLibraryFeedback(`${name} quedó guardada. ${payload.reason === "library_created" ? "Ejecutá ahora el recorrido de prueba." : ""}`.trim());
          await loadLibraries();
        } catch (error) {
          setInlineFeedback(fields.libraryDialogFeedback, libraryErrorMessage(error.message), "error");
        } finally {
          fields.submitLibrary.disabled = false;
        }
      }

      async function deleteManagedLibrary(library) {
        try {
          const response = await apiFetch(`/api/libraries/${encodeURIComponent(library.id)}/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confirmed: true })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedLibraryId = "";
          setLibraryFeedback(`${library.name} dejó de estar bajo seguimiento.`);
          await Promise.all([loadLibraries(), loadCatalog()]);
        } catch (error) {
          setLibraryFeedback(libraryErrorMessage(error.message), "error");
        }
      }

      function setLibraryFeedback(message, tone = "") {
        setInlineFeedback(fields.libraryFeedback, message, tone);
      }

      function libraryErrorMessage(reason) {
        const value = String(reason || "");
        if (value === "library_scan_busy") return "Ya hay un recorrido en curso para esta biblioteca.";
        if (value === "library_not_found") return "La biblioteca ya no está disponible.";
        if (value.includes("allowlist") || value.includes("allowed roots")) return "La ruta está fuera de las raíces habilitadas en el servidor.";
        if (value.includes("offline") || value.includes("directory")) return "La ruta no está montada o no es un directorio accesible.";
        if (value.includes("Manual libraries")) return "Las bibliotecas manuales no usan automatización. Cambiá la frecuencia para programar recorridos.";
        if (value.includes("Apply inventory")) return "Primero aplicá un inventario antes de activar recorridos automáticos.";
        if (value.includes("test scan")) return "Primero ejecutá un recorrido de prueba satisfactorio.";
        if (value.includes("already uses")) return "Esa ruta ya está registrada en otra biblioteca.";
        if (value === "library_store_unavailable") return "El inventario no está disponible. Reintentá en unos segundos.";
        if (value === "possible_duplicate") return "Encontramos obras parecidas en tu catálogo. Revisá primero las coincidencias para evitar un duplicado.";
        if (value.includes("recognizable identity") || value.includes("recognizable title")) return "El título detectado no alcanza para identificar la obra. Corregilo y volvé a intentar.";
        if (value.includes("Confirm the year")) return "Confirmá el año antes de crear la obra.";
        if (value.includes("valid four-digit year")) return "Ingresá un año válido de cuatro cifras.";
        if (value === "catalog_item_unavailable") return "La obra se guardó de forma incompleta. Actualizá la Bandeja antes de reintentar.";
        if (value === "catalog_item_not_found") return "La ficha ya no está en tu catálogo. Actualizá la Bandeja y volvé a comparar.";
        if (value.includes("not a scanner candidate")) return "Esa ficha ya no coincide con el archivo. Actualizá la Bandeja y revisá las candidatas.";
        return value && !value.startsWith("HTTP") ? value : "No pudimos completar la operación de biblioteca.";
      }

      function libraryStatusLabel(value) {
        return { unverified: "Sin comprobar", ready: "Lista", scanning: "Escaneando", paused: "Pausada", offline: "Desconectada", warning: "Con advertencias", error: "Error" }[value] || "Sin comprobar";
      }

      function scheduleLabel(value) {
        return { manual: "Manual", hourly: "Cada hora", daily: "Diaria" }[value] || "Manual";
      }

      function runStatusLabel(value) {
        return { queued: "En cola", running: "En curso", completed: "Completado", partial: "Parcial", blocked: "Bloqueado", failed: "Falló" }[value] || "Sin estado";
      }

      function runModeLabel(run) {
        return `${run.mode === "dry_run" ? "Prueba" : "Aplicación"} · ${run.trigger === "scheduled" ? "Programada" : "Manual"}`;
      }

      function formatLibraryTime(value) {
        const timestamp = Number(value || 0);
        if (!timestamp) return "Sin registro";
        return new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" }).format(new Date(timestamp * 1000));
      }

      function renderMembers() {
        const activeCount = members.filter((member) => member.active).length;
        fields.memberCount.textContent = `${members.length} ${members.length === 1 ? "miembro" : "miembros"} · ${activeCount} activos`;
        if (!members.length) {
          fields.memberList.innerHTML = `
            <div class="member-list-empty">
              <strong>Todav\u00eda no hay miembros</strong>
              <span>El owner es la \u00fanica cuenta de esta instancia.</span>
            </div>`;
        } else {
          fields.memberList.innerHTML = members.map((member) => {
          const username = member.username || "Miembro";
          const initials = username.slice(0, 2).toUpperCase();
          const status = member.active ? "Activo" : "Desactivado";
          const passwordState = member.must_change_password
            ? '<span class="member-state member-state-attention">Cambio pendiente</span>'
            : '<span class="member-state">Acceso confirmado</span>';
          return `
            <div class="member-row" data-member-id="${escapeAttr(member.id || "")}" data-active="${member.active ? "true" : "false"}">
              <div class="member-row-identity">
                <span class="member-avatar" aria-hidden="true">${escapeHtml(initials)}</span>
                <div>
                  <strong>${escapeHtml(username)}</strong>
                  <span>${escapeHtml(member.catalog?.name || "Cat\u00e1logo personal")}</span>
                </div>
              </div>
              <div class="member-row-status">
                <span class="member-state ${member.active ? "member-state-active" : "member-state-disabled"}">${status}</span>
                ${passwordState}
              </div>
              <div class="member-row-actions">
                <button class="quiet-action" type="button" data-member-action="edit" data-member-id="${escapeAttr(member.id || "")}">Editar</button>
                <button class="quiet-action" type="button" data-member-action="reset-password" data-member-id="${escapeAttr(member.id || "")}">Restablecer acceso</button>
                <button class="quiet-action ${member.active ? "member-deactivate" : "member-activate"}" type="button" data-member-action="toggle-active" data-member-id="${escapeAttr(member.id || "")}">${member.active ? "Desactivar" : "Reactivar"}</button>
                ${member.active ? "" : `<button class="quiet-action member-archive" type="button" data-member-action="archive" data-member-id="${escapeAttr(member.id || "")}">Archivar</button>`}
              </div>
            </div>`;
          }).join("");
        }
        renderArchivedMembers();
      }

      function renderArchivedMembers() {
        fields.archivedMemberSection.hidden = !archivedMembers.length;
        fields.archivedMemberCount.textContent = `${archivedMembers.length} ${archivedMembers.length === 1 ? "archivo" : "archivos"}`;
        fields.archivedMemberList.innerHTML = archivedMembers.map((member) => {
          const username = member.username || "Miembro archivado";
          return `
            <div class="member-row archived-member-row" data-archive-id="${escapeAttr(member.id || "")}">
              <div class="member-row-identity">
                <span class="member-avatar archived-avatar" aria-hidden="true">${escapeHtml(username.slice(0, 2).toUpperCase())}</span>
                <div><strong>${escapeHtml(username)}</strong><span>${escapeHtml(member.catalog?.name || "Catálogo preservado")}</span></div>
              </div>
              <div class="member-row-status">
                <span class="member-state member-state-disabled">Archivado</span>
                <span class="member-state ${member.catalog_available ? "" : "member-state-attention"}">${member.catalog_available ? "Catálogo disponible" : "Archivo no disponible"}</span>
              </div>
              <div class="member-row-actions">
                <button class="quiet-action member-activate" type="button" data-archive-action="restore" data-archive-id="${escapeAttr(member.id || "")}" ${member.catalog_available ? "" : "disabled"}>Restaurar</button>
              </div>
            </div>`;
        }).join("");
      }

      function openMemberDialog() {
        fields.memberForm.reset();
        fields.memberTemporaryPassword.type = "password";
        setMemberDialogFeedback("");
        fields.memberDialog.showModal();
        fields.memberUsername.focus();
      }

      function closeMemberDialog() {
        fields.memberDialog.close();
        fields.memberForm.reset();
        setMemberDialogFeedback("");
      }

      async function createMember(event) {
        event.preventDefault();
        const requestedUsername = fields.memberUsername.value;
        fields.submitMember.disabled = true;
        fields.submitMember.setAttribute("aria-busy", "true");
        fields.submitMember.textContent = "Creando\u2026";
        setMemberDialogFeedback("");
        try {
          const response = await apiFetch("/api/members", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: fields.memberUsername.value,
              catalog_name: fields.memberCatalogName.value,
              temporary_password: fields.memberTemporaryPassword.value
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            setMemberDialogFeedback(memberErrorMessage(payload.reason), "error");
            return;
          }
          closeMemberDialog();
          showTemporaryPassword(payload.member?.username || requestedUsername, payload.temporary_password);
          await loadMembers();
        } catch (error) {
          setMemberDialogFeedback(memberErrorMessage(error.message), "error");
        } finally {
          fields.submitMember.disabled = false;
          fields.submitMember.removeAttribute("aria-busy");
          fields.submitMember.textContent = "Crear cuenta y cat\u00e1logo";
        }
      }

      async function handleMemberAction(event) {
        const button = event.target.closest("[data-member-action]");
        if (!button) return;
        const member = members.find((entry) => entry.id === button.dataset.memberId);
        if (!member) return;
        const action = button.dataset.memberAction;
        if (action === "edit") {
          openEditMemberDialog(member);
          return;
        }
        if (action === "archive") {
          openArchiveMemberDialog(member);
          return;
        }
        if (action === "toggle-active" && member.active) {
          const confirmed = confirm(`\u00bfDesactivar a "${member.username}"? Sus sesiones abiertas se cerrar\u00e1n.`);
          if (!confirmed) return;
        }
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        try {
          const endpoint = action === "reset-password"
            ? `/api/members/${encodeURIComponent(member.id)}/password-reset`
            : `/api/members/${encodeURIComponent(member.id)}/status`;
          const body = action === "reset-password" ? {} : { active: !member.active };
          const response = await apiFetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          if (action === "reset-password") {
            showTemporaryPassword(member.username, payload.temporary_password);
          } else {
            setMemberFeedback(payload.member?.active ? `${member.username} fue reactivado.` : `${member.username} fue desactivado.`);
          }
          await loadMembers();
        } catch (error) {
          setMemberFeedback(memberErrorMessage(error.message), "error");
        } finally {
          button.disabled = false;
          button.removeAttribute("aria-busy");
        }
      }

      function openEditMemberDialog(member) {
        editingMemberId = member.id;
        fields.editMemberUsername.value = member.username || "";
        fields.editMemberCatalogName.value = member.catalog?.name || "";
        setInlineFeedback(fields.editMemberFeedback, "");
        fields.editMemberDialog.showModal();
        fields.editMemberUsername.focus();
      }

      function closeEditMemberDialog() {
        fields.editMemberDialog.close();
        editingMemberId = "";
        fields.editMemberForm.reset();
        setInlineFeedback(fields.editMemberFeedback, "");
      }

      async function saveMemberProfile(event) {
        event.preventDefault();
        if (!editingMemberId) return;
        fields.saveMemberProfile.disabled = true;
        try {
          const response = await apiFetch(`/api/members/${encodeURIComponent(editingMemberId)}/profile`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: fields.editMemberUsername.value,
              catalog_name: fields.editMemberCatalogName.value
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const username = payload.member?.username || fields.editMemberUsername.value;
          closeEditMemberDialog();
          setMemberFeedback(`${username} fue actualizado.`);
          await loadMembers();
        } catch (error) {
          setInlineFeedback(fields.editMemberFeedback, memberErrorMessage(error.message), "error");
        } finally {
          fields.saveMemberProfile.disabled = false;
        }
      }

      function openArchiveMemberDialog(member) {
        archivingMemberId = member.id;
        fields.archiveMemberUsernameLabel.textContent = member.username || "";
        fields.archiveMemberConfirmation.value = "";
        setInlineFeedback(fields.archiveMemberFeedback, "");
        fields.archiveMemberDialog.showModal();
        fields.archiveMemberConfirmation.focus();
      }

      function closeArchiveMemberDialog() {
        fields.archiveMemberDialog.close();
        archivingMemberId = "";
        fields.archiveMemberForm.reset();
        setInlineFeedback(fields.archiveMemberFeedback, "");
      }

      async function archiveMemberAccount(event) {
        event.preventDefault();
        if (!archivingMemberId) return;
        fields.confirmArchiveMember.disabled = true;
        try {
          const response = await apiFetch(`/api/members/${encodeURIComponent(archivingMemberId)}/archive`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confirmed_username: fields.archiveMemberConfirmation.value })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const username = payload.archived?.username || "La cuenta";
          closeArchiveMemberDialog();
          setMemberFeedback(`${username} fue archivado y su catálogo quedó preservado.`);
          await loadMembers();
        } catch (error) {
          setInlineFeedback(fields.archiveMemberFeedback, memberErrorMessage(error.message), "error");
        } finally {
          fields.confirmArchiveMember.disabled = false;
        }
      }

      async function handleArchivedMemberAction(event) {
        const button = event.target.closest("[data-archive-action]");
        if (!button || button.dataset.archiveAction !== "restore") return;
        const archived = archivedMembers.find((entry) => entry.id === button.dataset.archiveId);
        if (!archived) return;
        button.disabled = true;
        try {
          const response = await apiFetch(`/api/member-archives/${encodeURIComponent(archived.id)}/restore`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}"
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          showTemporaryPassword(payload.member?.username || archived.username, payload.temporary_password);
          setMemberFeedback(`${payload.member?.username || archived.username} fue restaurado.`);
          await loadMembers();
        } catch (error) {
          setMemberFeedback(memberErrorMessage(error.message), "error");
        } finally {
          button.disabled = false;
        }
      }

      function showTemporaryPassword(username, password) {
        fields.temporaryPasswordUsername.textContent = username;
        fields.temporaryPasswordValue.value = password || "";
        fields.temporaryPasswordFeedback.hidden = true;
        fields.temporaryPasswordDialog.showModal();
        fields.copyTemporaryPassword.focus();
      }

      function closeTemporaryPasswordDialog() {
        fields.temporaryPasswordDialog.close();
        fields.temporaryPasswordValue.value = "";
        fields.temporaryPasswordFeedback.hidden = true;
      }

      async function copyTemporaryPassword() {
        try {
          await navigator.clipboard.writeText(fields.temporaryPasswordValue.value);
          fields.temporaryPasswordFeedback.textContent = "Contrase\u00f1a copiada.";
          fields.temporaryPasswordFeedback.hidden = false;
        } catch {
          fields.temporaryPasswordValue.select();
          fields.temporaryPasswordFeedback.textContent = "Seleccion\u00e1 el texto y copialo manualmente.";
          fields.temporaryPasswordFeedback.hidden = false;
        }
      }

      function setMemberFeedback(message, tone = "") {
        fields.memberFeedback.textContent = message;
        fields.memberFeedback.dataset.tone = tone;
        fields.memberFeedback.hidden = !message;
      }

      function setMemberDialogFeedback(message, tone = "") {
        fields.memberDialogFeedback.textContent = message;
        fields.memberDialogFeedback.dataset.tone = tone;
        fields.memberDialogFeedback.hidden = !message;
      }

      function setInlineFeedback(field, message, tone = "") {
        field.textContent = message;
        field.dataset.tone = tone;
        field.hidden = !message;
      }

      function memberErrorMessage(reason) {
        if (reason === "username_unavailable") return "Ese usuario ya existe.";
        if (reason === "member_not_found") return "La cuenta ya no est\u00e1 disponible.";
        if (reason === "member_must_be_inactive") return "Desactiv\u00e1 la cuenta antes de archivarla.";
        if (reason === "archive_confirmation_mismatch") return "El nombre escrito no coincide con el usuario.";
        if (reason === "archive_not_found") return "Ese archivo ya no est\u00e1 disponible.";
        if (reason === "archived_catalog_unavailable") return "El archivo del cat\u00e1logo no est\u00e1 disponible en el servidor.";
        if (reason === "member_provisioning_failed") return "No pudimos crear el cat\u00e1logo personal.";
        if (String(reason || "").includes("at least 12")) return "La contrase\u00f1a debe tener al menos 12 caracteres.";
        if (String(reason || "").includes("Username must")) return "Us\u00e1 entre 3 y 64 letras, n\u00fameros, puntos, guiones o guiones bajos.";
        return "No pudimos actualizar la cuenta.";
      }

      async function openPrivacyDialog() {
        fields.systemMenu.open = false;
        setInlineFeedback(fields.privacyFeedback, "");
        applyPrivacyForm(privacyPreferences);
        fields.privacyDialog.showModal();
        fields.savePrivacy.disabled = true;
        try {
          const response = await apiFetch("/api/privacy");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          privacyPreferences = { ...privacyPreferences, ...(payload.preferences || {}) };
          applyPrivacyForm(privacyPreferences);
        } catch (error) {
          setInlineFeedback(fields.privacyFeedback, privacyErrorMessage(error.message), "error");
        } finally {
          fields.savePrivacy.disabled = false;
          fields.catalogShared.focus();
        }
      }

      function closePrivacyDialog() {
        fields.privacyDialog.close();
        setInlineFeedback(fields.privacyFeedback, "");
      }

      function applyPrivacyForm(preferences) {
        fields.catalogShared.checked = Boolean(preferences.catalog_shared);
        fields.shareStatus.checked = Boolean(preferences.share_status);
        fields.shareWatchedAt.checked = Boolean(preferences.share_watched_at);
        fields.shareHistory.checked = Boolean(preferences.share_history);
        fields.shareRating.checked = Boolean(preferences.share_rating);
        fields.shareReview.checked = Boolean(preferences.share_review);
        syncPrivacyControls();
      }

      function syncPrivacyControls() {
        fields.privacyFields.disabled = !fields.catalogShared.checked;
        fields.privacyFields.dataset.enabled = fields.catalogShared.checked ? "true" : "false";
      }

      async function savePrivacyPreferences(event) {
        event.preventDefault();
        fields.savePrivacy.disabled = true;
        setInlineFeedback(fields.privacyFeedback, "Guardando privacidad…");
        const next = {
          catalog_shared: fields.catalogShared.checked,
          share_status: fields.shareStatus.checked,
          share_watched_at: fields.shareWatchedAt.checked,
          share_history: fields.shareHistory.checked,
          share_rating: fields.shareRating.checked,
          share_review: fields.shareReview.checked
        };
        try {
          const response = await apiFetch("/api/privacy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(next)
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          privacyPreferences = { ...next, ...(payload.preferences || {}) };
          syncPrivacySummary();
          closePrivacyDialog();
          if (currentView === "club") await loadClub();
        } catch (error) {
          setInlineFeedback(fields.privacyFeedback, privacyErrorMessage(error.message), "error");
        } finally {
          fields.savePrivacy.disabled = false;
        }
      }

      function privacyErrorMessage(reason) {
        if (String(reason || "").includes("Invalid visibility")) return "Elegí una opción de visibilidad válida.";
        if (reason === "identity_store_unavailable") return "La configuración de cuentas no está disponible.";
        return "No pudimos guardar la privacidad. Volvé a intentar.";
      }

      function syncPrivacySummary() {
        fields.privacyButton.textContent = privacyPreferences.catalog_shared
          ? "Privacidad · Compartiendo"
          : "Privacidad";
      }

      async function loadCatalog() {
        fields.homeView.setAttribute("aria-busy", "true");
        const response = await apiFetch(`/api/items?home_date=${encodeURIComponent(todayLocalDate())}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
        items = payload.items || [];
        editorialHome = normalizeEditorialHome(payload.home);
        editorialFeaturedCache.clear();
        rememberEditorialFeatured(editorialHome);
        prepareCatalogViewModel();
        editorialRevision += 1;
        sourceFiles = payload.sources || [];
        writeJsonPath = payload.write_json || "";
        privacyPreferences = { ...privacyPreferences, ...(payload.privacy || {}) };
        syncPrivacySummary();
        externalHealth = payload.external || externalHealth;
        curationCounts = {
          ...curationCounts,
          ...(payload.curation?.counts || {})
        };
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        setupCollectionFilterOptions();
        render();
        fields.homeView.setAttribute("aria-busy", "false");
        renderDatabaseMenu();
        syncCurationCounts();
        if (currentView === "inbox") await loadCurrentInbox();
        if (!routeRestored) {
          routeRestored = true;
          restoreRoute();
        }
      }

      function goHome() {
        closeDetail({ restoreFocus: false, updateHistory: false });
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true });
        render();
        showView("home", { updateHistory: false, focus: true });
        syncRoute(routeValuesForView("home"), "push");
      }

      function goToCollection(options = {}) {
        showView("catalog", options);
      }

      function goToCollectionRoot() {
        resetCollectionFilters();
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true });
        showView("catalog", { updateHistory: false, focus: true });
        syncRoute(routeValuesForView("catalog"), "push");
      }

      async function goToInbox(filter = "") {
        if (filter) {
          curationFilter = filter;
          await setInboxMode("curation", { loadData: false });
        } else {
          await setInboxMode(inboxMode, { loadData: false });
        }
        showView("inbox");
        await loadCurrentInbox();
      }

      async function goToImports() {
        await setInboxMode("imports", { loadData: false });
        showView("inbox");
        await loadCurrentInbox();
      }

      async function goToClub() {
        closeDetail({ restoreFocus: false, updateHistory: false });
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true });
        showView("club");
        await loadClub();
      }

      async function goToHomeCollection(collectionId) {
        clubMode = "collections";
        try {
          localStorage.setItem("movie-inbox-club-mode", clubMode);
        } catch (_error) {
          // Navigation still works when browser storage is unavailable.
        }
        closeSharedDetail();
        await goToClub();
        if (collectionId) await openCollection(collectionId);
      }

      function activateHomeSection(sectionId) {
        const section = editorialHome.sections.find((entry) => entry.id === sectionId);
        const action = section?.action || {};
        if (action.kind === "club") {
          goToClub();
          return;
        }
        resetCollectionFilters();
        clearManualSearch({ focus: false, updateHistory: false, resetExternal: true });
        applyCollectionFilterDescriptor(action.filters || {});
        render();
        showView("catalog", { updateHistory: false, focus: true });
        syncRoute(routeValuesForView("catalog"), "push");
      }

      function goToAdmin(options = {}) {
        showView("admin", options);
        Promise.all([loadMembers(), loadLibraries(), loadImageCacheStatus()]);
      }

      async function refreshAdminData() {
        await load();
        if (currentView === "admin") {
          await Promise.all([
            loadMembers({ announce: true }),
            loadLibraries({ announce: true }),
            loadImageCacheStatus({ announce: true })
          ]);
        }
      }

      function showView(view, options = {}) {
        const updateHistory = options.updateHistory !== false;
        const scroll = options.scroll !== false;
        const focus = options.focus ?? updateHistory;
        if (view === "admin" && currentIdentity?.user?.role !== "owner") view = "home";
        currentView = ["home", "catalog", "inbox", "club", "admin"].includes(view) ? view : "home";
        fields.homeView.hidden = currentView !== "home";
        fields.clubView.hidden = currentView !== "club";
        fields.collectionView.hidden = currentView !== "catalog";
        fields.inboxView.hidden = currentView !== "inbox";
        fields.adminView.hidden = currentView !== "admin";
        syncImageCacheStatusPolling();
        setActiveNavigation(currentView);
        if (fields.systemMenu.open) fields.systemMenu.open = false;
        if (updateHistory) syncRoute(routeValuesForView(currentView), "push");
        renderHeaderStats();
        if (scroll) scrollPageTop();
        if (focus) requestAnimationFrame(() => focusViewHeading(currentView));
      }

      function scrollPageTop() {
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
      }

      function focusViewHeading(view) {
        const selector = {
          home: "#spotlightTitle",
          catalog: "#catalogTitle",
          inbox: "#inboxTitle",
          club: "#clubTitle",
          admin: "#adminTitle"
        }[view];
        if (!selector) return;
        document.querySelector(selector)?.focus({ preventScroll: true });
      }

      function setActiveNavigation(view) {
        const buttons = {
          home: fields.homeButton,
          catalog: fields.catalogButton,
          inbox: fields.inboxButton,
          club: fields.clubButton,
          admin: fields.adminButton
        };
        for (const [name, button] of Object.entries(buttons)) {
          const active = name === view;
          button.classList.toggle("active", active);
          if (active) button.setAttribute("aria-current", "page");
          else button.removeAttribute("aria-current");
        }
        fields.systemMenu.classList.toggle("active", view === "admin");
      }

      async function loadClub({ announce = false } = {}) {
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

      async function changeClubMode(event) {
        const button = event.target.closest("[data-club-mode]");
        if (!button) return;
        const mode = button.dataset.clubMode;
        if (!["collections", "members"].includes(mode) || mode === clubMode) return;
        clubMode = mode;
        localStorage.setItem("movie-inbox-club-mode", clubMode);
        renderClubMode();
        setClubFeedback("");
        if (clubMode === "members" && selectedClubUserId && !sharedCatalog) {
          await loadSharedCatalog(selectedClubUserId);
        }
      }

      function renderClubMode() {
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

      async function selectClubCatalog(event) {
        const button = event.target.closest("[data-club-user-id]");
        if (!button || button.dataset.clubUserId === selectedClubUserId) return;
        selectedClubUserId = button.dataset.clubUserId || "";
        clubVisibleCount = CLUB_PAGE_SIZE;
        renderClubTabs();
        await loadSharedCatalog(selectedClubUserId);
      }

      async function loadSharedCatalog(userId) {
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

      function renderClubTabs() {
        fields.clubMemberTabs.innerHTML = clubCatalogs.map((entry) => {
          const active = entry.user?.id === selectedClubUserId;
          const username = entry.user?.username || "Miembro";
          return `<button type="button" data-club-user-id="${escapeAttr(entry.user?.id || "")}" aria-pressed="${active}" class="${active ? "active" : ""}">
            <span class="club-member-mark" aria-hidden="true">${escapeHtml(username.slice(0, 2).toUpperCase())}</span>
            <span><strong>${escapeHtml(entry.user?.is_self ? "Mi catálogo" : username)}</strong><small>${escapeHtml(entry.catalog?.name || "Catálogo personal")} · ${escapeHtml(entry.counts?.total || 0)} obras</small></span>
          </button>`;
        }).join("");
      }

      function renderSharedCatalog() {
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

      function sharedCard(item, username, priority = false) {
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

      function showMoreClubItems() {
        clubVisibleCount += CLUB_PAGE_SIZE;
        renderSharedCatalog();
      }

      function setClubFeedback(message, tone = "") {
        fields.clubFeedback.textContent = message;
        fields.clubFeedback.dataset.tone = tone;
        fields.clubFeedback.hidden = !message;
      }

      function renderCollectionDirectory() {
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

      function collectionDirectoryCard(collection) {
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

      function collectionMosaic(preview) {
        const slots = preview.slice(0, 4);
        while (slots.length < 4) slots.push({ title: "Movie Inbox" });
        return slots.map((item) => `<div>${posterArtwork(item, displayTitle(item) || "Movie Inbox")}</div>`).join("");
      }

      async function openCollection(collectionId) {
        selectedCollectionId = String(collectionId || "");
        selectedCollection = null;
        selectedCollectionItems.clear();
        fields.collectionDirectory.hidden = true;
        fields.collectionDetailPanel.hidden = false;
        fields.collectionDetailPanel.setAttribute("aria-busy", "true");
        fields.collectionDetailTitle.textContent = "Abriendo colección…";
        await loadCollectionDetail(selectedCollectionId, { announce: true });
      }

      async function loadCollectionDetail(collectionId, { announce = false } = {}) {
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

      function closeCollectionDetail() {
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

      function renderCollectionDetail() {
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

      function collectionItemCard(item, priority = false) {
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

      async function toggleCollectionFollow(collectionId = "") {
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

      function changeCollectionSelection(event) {
        const checkbox = event.target.closest("[data-collection-select]");
        if (!checkbox) return;
        const itemId = checkbox.dataset.collectionSelect || "";
        if (checkbox.checked) selectedCollectionItems.add(itemId);
        else selectedCollectionItems.delete(itemId);
        syncCollectionSelection();
      }

      function toggleMissingCollectionSelection() {
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

      function syncCollectionSelection() {
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

      function addSelectedCollectionItems() {
        addCollectionItems([...selectedCollectionItems]);
      }

      function addMissingCollectionItems() {
        const missingIds = (selectedCollection?.items || [])
          .filter((item) => item.catalog?.state === "missing")
          .map((item) => item.collection_item_id);
        addCollectionItems(missingIds);
      }

      async function addCollectionItems(itemIds) {
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

      function editorialEntryByKey(key) {
        const featured = editorialHome.featured.find((candidate) => candidate.key === key);
        if (featured) return featured;
        for (const section of editorialHome.sections) {
          const entry = (section.items || []).find((candidate) => candidate.key === key);
          if (entry) return entry;
        }
        return null;
      }

      function openHomeCollectionDetail(key) {
        const entry = editorialEntryByKey(key);
        if (!entry || entry.origin?.kind !== "collection") return;
        const item = entry.item || {};
        const origin = entry.origin || {};
        const title = displayTitle(item) || "Sin título";
        const summary = item.wikipedia_extract || item.description || "";
        fields.sharedDetailOwner.textContent = `De ${origin.collection_title || "una colección seguida"}`;
        fields.sharedDetailBody.innerHTML = `
          <section class="drawer-hero">${drawerPoster(item, title)}<div class="drawer-intro"><span class="drawer-kicker">Ficha del Club</span><h2>${escapeHtml(title)}</h2><div class="drawer-byline">${[item.year, firstListValue(item.directors), listText(item.genres, 2)].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join("")}</div></div></section>
          <section class="home-collection-origin"><span>${escapeHtml(entry.reason?.label || "Desde una colección seguida")}</span><p>${escapeHtml(entry.reason?.detail || "Todavía no forma parte de tu catálogo personal.")}</p></section>
          <section class="drawer-synopsis"><h3>Sinopsis</h3><p>${escapeHtml(summary || "No hay una sinopsis disponible.")}</p></section>
          <details class="drawer-accordion"><summary><span>Ficha técnica</span><small>Dirección, reparto y títulos</small></summary><div class="drawer-accordion-body">${factsPanel(item) || '<span class="status-line">Sin ficha enriquecida.</span>'}</div></details>
          <div class="links shared-detail-links">${detailLinks(item)}</div>
          <div class="home-collection-detail-actions">
            <button type="button" data-click="add-home-collection-item" data-collection-id="${escapeAttr(origin.collection_id || "")}" data-id="${escapeAttr(origin.collection_item_id || "")}">Agregar a mi catálogo</button>
            <button class="quiet-action" type="button" data-click="open-home-collection" data-collection-id="${escapeAttr(origin.collection_id || "")}">Ver colección completa</button>
            <span data-home-collection-feedback role="status" aria-live="polite"></span>
          </div>`;
        fields.sharedDetailDialog.showModal();
        fields.closeSharedDetail.focus();
      }

      async function addHomeCollectionItem(collectionId, itemId, button) {
        if (!collectionId || !itemId || button.disabled) return;
        const feedback = fields.sharedDetailBody.querySelector("[data-home-collection-feedback]");
        button.disabled = true;
        button.textContent = "Agregando…";
        if (feedback) feedback.textContent = "Comprobando coincidencias antes de guardar.";
        try {
          const response = await apiFetch(`/api/collections/${encodeURIComponent(collectionId)}/add`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ item_ids: [itemId] })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const summary = payload.summary || {};
          if (summary.added) {
            button.textContent = "Agregada";
            if (feedback) feedback.textContent = "La obra ya forma parte de tu catálogo personal.";
            await loadCatalog();
          } else if (summary.present) {
            button.textContent = "Ya estaba agregada";
            if (feedback) feedback.textContent = "Encontramos esta obra en tu catálogo.";
          } else {
            button.textContent = "Requiere revisión";
            if (feedback) feedback.textContent = "Hay una posible coincidencia. Abrí la colección para compararla antes de agregar.";
          }
        } catch (error) {
          button.disabled = false;
          button.textContent = "Reintentar agregado";
          if (feedback) feedback.textContent = "No pudimos completar la comprobación. Volvé a intentar.";
        }
      }

      function openSharedDetail(itemId) {
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

      function closeSharedDetail() {
        fields.sharedDetailDialog.close();
        fields.sharedDetailBody.innerHTML = "";
      }

      function storedInboxMode() {
        try {
          const stored = localStorage.getItem("movie-inbox-inbox-mode");
          return ["curation", "imports", "scanner"].includes(stored) ? stored : "curation";
        } catch (_error) {
          return "curation";
        }
      }

      async function changeInboxMode(event) {
        const button = event.target.closest("[data-inbox-mode]");
        if (!button) return;
        await setInboxMode(button.dataset.inboxMode || "curation");
      }

      async function setInboxMode(mode, { loadData = true } = {}) {
        const requested = ["curation", "imports", "scanner"].includes(mode) ? mode : "curation";
        inboxMode = requested === "scanner" && currentIdentity?.user?.role !== "owner" ? "curation" : requested;
        try {
          localStorage.setItem("movie-inbox-inbox-mode", inboxMode);
        } catch (_error) {
          // The mode still works when browser storage is unavailable.
        }
        const importsActive = inboxMode === "imports";
        const scannerActive = inboxMode === "scanner";
        fields.inboxView.dataset.inboxMode = inboxMode;
        fields.curationInboxPanel.hidden = importsActive || scannerActive;
        fields.importInboxPanel.hidden = !importsActive;
        fields.scannerInboxPanel.hidden = !scannerActive;
        fields.inboxCurationMode.classList.toggle("active", !importsActive && !scannerActive);
        fields.inboxCurationMode.setAttribute("aria-pressed", String(!importsActive && !scannerActive));
        fields.inboxImportsMode.classList.toggle("active", importsActive);
        fields.inboxImportsMode.setAttribute("aria-pressed", String(importsActive));
        fields.inboxScannerMode.classList.toggle("active", scannerActive);
        fields.inboxScannerMode.setAttribute("aria-pressed", String(scannerActive));
        if (!loadData || currentView !== "inbox") return;
        if (scannerActive) await loadScannerQueue();
        else if (importsActive) await loadImportDrafts();
        else await loadCurationQueue();
      }

      async function loadCurrentInbox(options = {}) {
        if (inboxMode === "scanner") await loadScannerQueue(options);
        else if (inboxMode === "imports") await loadImportDrafts(options);
        else await loadCurationQueue(options);
      }

      async function loadScannerQueue({ announce = false } = {}) {
        if (scannerQueueLoading || currentIdentity?.user?.role !== "owner") return;
        scannerQueueLoading = true;
        fields.scannerInboxPanel.setAttribute("aria-busy", "true");
        fields.refreshScannerQueue.disabled = true;
        try {
          const response = await apiFetch("/api/scanner/queue");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          scannerQueue = payload.items || [];
          const queueIds = new Set(scannerQueue.map((item) => item.id));
          scannerCreateConflicts = new Map(
            [...scannerCreateConflicts].filter(([fileId]) => queueIds.has(fileId))
          );
          curationCounts.scanner = Number(payload.count || scannerQueue.length);
          if (!scannerQueue.some((item) => item.id === selectedScannerItemId)) {
            selectedScannerItemId = scannerQueue[0]?.id || "";
          }
          renderScannerQueue();
          syncCurationCounts();
          if (announce) setCurationFeedback("Cola del scanner actualizada.", "success");
        } catch (error) {
          fields.scannerQueue.innerHTML = "";
          fields.scannerQueueDetail.innerHTML = `<div class="curation-empty"><strong>Cola no disponible</strong><p>${escapeHtml(libraryErrorMessage(error.message))}</p></div>`;
        } finally {
          scannerQueueLoading = false;
          fields.scannerInboxPanel.removeAttribute("aria-busy");
          fields.refreshScannerQueue.disabled = false;
        }
      }

      function renderScannerQueue() {
        const reviewCount = scannerQueue.filter((item) => item.state === "review").length;
        const newCount = scannerQueue.filter((item) => item.state === "new").length;
        fields.scannerAllCount.textContent = String(scannerQueue.length);
        fields.scannerReviewCount.textContent = String(reviewCount);
        fields.scannerNewCount.textContent = String(newCount);
        fields.scannerQueueFilters.querySelectorAll("[data-scanner-filter]").forEach((button) => {
          const active = button.dataset.scannerFilter === scannerQueueFilter;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        const visible = visibleScannerQueue();
        fields.scannerQueueMeta.textContent = visible.length === scannerQueue.length
          ? `${scannerQueue.length} ${scannerQueue.length === 1 ? "pendiente" : "pendientes"}`
          : `${visible.length} de ${scannerQueue.length} pendientes`;
        if (!scannerQueue.length) {
          fields.scannerQueue.innerHTML = `<div class="curation-empty compact"><strong>Scanner al día</strong><p>No quedan identidades físicas por confirmar.</p></div>`;
          fields.scannerQueueDetail.innerHTML = `<div class="curation-empty"><strong>Sin decisiones pendientes</strong><p>Los próximos casos aparecerán después de un recorrido aplicado.</p></div>`;
          return;
        }
        if (!visible.length) {
          selectedScannerItemId = "";
          fields.scannerQueue.innerHTML = `<div class="curation-empty compact"><strong>Sin resultados</strong><p>Probá otro filtro o término de búsqueda.</p></div>`;
          fields.scannerQueueDetail.innerHTML = `<div class="curation-empty"><strong>No hay casos para mostrar</strong><p>La cola completa conserva ${scannerQueue.length} pendientes.</p></div>`;
          return;
        }
        if (!visible.some((item) => item.id === selectedScannerItemId)) {
          selectedScannerItemId = visible[0].id;
        }
        fields.scannerQueue.innerHTML = visible.map((item) => {
          const active = item.id === selectedScannerItemId;
          const label = item.state === "review" ? "Comparar" : "Sin coincidencia";
          const partLabel = Number(item.file_count || 1) > 1 ? `${item.file_count} partes` : "";
          return `<button class="scanner-queue-item${active ? " active" : ""}" type="button" data-scanner-item="${escapeAttr(item.id)}" aria-pressed="${active}">
            <span class="scanner-queue-state">${label}</span>
            <strong>${escapeHtml(item.detected_title || item.name || "Sin título")}</strong>
            <span>${escapeHtml([item.detected_year, importKindLabel(item.detected_kind)].filter(Boolean).join(" · ") || "Identidad incompleta")}</span>
            <small>${escapeHtml([item.library_name || "Biblioteca", partLabel].filter(Boolean).join(" · "))}</small>
          </button>`;
        }).join("");
        renderScannerQueueDetail();
      }

      function visibleScannerQueue() {
        const query = normalizeText(scannerQueueQuery);
        return scannerQueue.filter((item) => {
          if (scannerQueueFilter !== "all" && item.state !== scannerQueueFilter) return false;
          if (!query) return true;
          const values = [
            item.detected_title,
            item.detected_year,
            item.detected_kind,
            item.name,
            item.relative_path,
            item.library_name
          ];
          return normalizeText(values.filter(Boolean).join(" ")).includes(query);
        });
      }

      function changeScannerQueueFilter(event) {
        const button = event.target.closest("[data-scanner-filter]");
        if (!button) return;
        scannerQueueFilter = button.dataset.scannerFilter || "all";
        renderScannerQueue();
        focusSelectedScannerItem();
      }

      function searchScannerQueue(event) {
        scannerQueueQuery = event.target.value || "";
        renderScannerQueue();
      }

      function selectScannerQueueItem(event) {
        const button = event.target.closest("[data-scanner-item]");
        if (!button) return;
        selectedScannerItemId = button.dataset.scannerItem || "";
        renderScannerQueue();
        focusSelectedScannerItem();
      }

      function moveScannerQueueSelection(event) {
        const visible = visibleScannerQueue();
        if (!["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft"].includes(event.key) || !visible.length) return;
        event.preventDefault();
        const current = Math.max(0, visible.findIndex((item) => item.id === selectedScannerItemId));
        const forwards = event.key === "ArrowDown" || event.key === "ArrowRight";
        const next = (current + (forwards ? 1 : -1) + visible.length) % visible.length;
        selectedScannerItemId = visible[next].id;
        renderScannerQueue();
        focusSelectedScannerItem();
      }

      function focusSelectedScannerItem() {
        requestAnimationFrame(() => fields.scannerQueue.querySelector(".scanner-queue-item.active")?.focus({ preventScroll: true }));
      }

      function renderScannerQueueDetail() {
        const item = scannerQueue.find((entry) => entry.id === selectedScannerItemId);
        if (!item) return;
        const createConflict = scannerCreateConflicts.get(item.id) || null;
        const candidates = scannerCandidatesForItem(item);
        const distinctReviewReady = Boolean(createConflict?.reviewToken);
        const createDraft = createConflict?.draft || {};
        const createAction = candidates.length
          ? distinctReviewReady ? "create-distinct" : "review-distinct"
          : "create-detected";
        const createHeading = candidates.length
          ? distinctReviewReady ? "Confirmar obra distinta" : "¿Ninguna coincide?"
          : "Agregar al catálogo personal";
        const createDescription = candidates.length
          ? distinctReviewReady
            ? `La comprobación final encontró las fichas de arriba. Confirmar conserva ambas obras, crea una ficha separada y registra ${actionObjectLabel(item)} con su identidad.`
            : "Corregí título, año o tipo si hace falta. Revisaremos otra vez tu catálogo antes de permitir una ficha separada."
          : "Esta acción crea una ficha pendiente y vincula su disponibilidad física. El año es obligatorio y el catálogo se comprueba nuevamente antes de escribir.";
        const createButtonLabel = candidates.length
          ? distinctReviewReady
            ? `Conservar ambas y vincular ${actionObjectLabel(item)}`
            : "Revisar alta como obra distinta"
          : `Agregar obra y vincular ${actionObjectLabel(item)}`;
        const parts = Array.isArray(item.parts) && item.parts.length ? item.parts : [{
          name: item.name,
          relative_path: item.relative_path,
          size_bytes: item.size_bytes,
          part: ""
        }];
        const multipart = parts.length > 1;
        const totalSize = parts.reduce((total, part) => total + Number(part.size_bytes || 0), 0);
        const actionObject = multipart ? `${parts.length} partes` : "archivo";
        fields.scannerQueueDetail.innerHTML = `
          <header class="scanner-case-heading">
            <div>
              <span class="section-kicker">${multipart ? "Obra multiparte" : item.state === "review" ? "Coincidencia ambigua" : "Archivo nuevo"}</span>
              <h3>${escapeHtml(item.detected_title || item.name || "Sin título")}</h3>
              <p>${multipart ? `${parts.length} archivos serán tratados como una sola obra.` : escapeHtml(item.relative_path || item.name || "")}</p>
            </div>
            <span class="member-state member-state-attention">${candidates.length ? `${candidates.length} ${candidates.length === 1 ? "candidata" : "candidatas"}` : "Sin coincidencia"}</span>
          </header>
          <div class="scanner-scope-note" role="note">
            <strong>${candidates.length ? "Vincular con una obra existente" : "Obra ausente del catálogo"}</strong>
            <span>${candidates.length
              ? `Elegí la ficha que representa ${multipart ? "estas partes" : "este archivo"}. Vincular sólo registra su disponibilidad física; no crea ni combina fichas.`
              : `No encontramos una ficha compatible. Podés agregarla a tu catálogo personal y vincular ${multipart ? "estas partes" : "este archivo"} sin marcarla como vista.`}</span>
          </div>
          <dl class="scanner-file-facts">
            <div><dt>Biblioteca</dt><dd>${escapeHtml(item.library_name || "Biblioteca")}</dd></div>
            <div><dt>Año detectado</dt><dd>${escapeHtml(item.detected_year || "Sin año")}</dd></div>
            <div><dt>Tipo detectado</dt><dd>${escapeHtml(importKindLabel(item.detected_kind) || "Película")}</dd></div>
            <div><dt>${multipart ? "Archivos y tamaño" : "Tamaño"}</dt><dd>${multipart ? `${parts.length} · ` : ""}${escapeHtml(formatImportBytes(totalSize))}</dd></div>
          </dl>
          ${multipart ? `<section class="scanner-parts" aria-label="Partes detectadas"><strong>Archivos agrupados</strong><div>${parts.map((part, index) => `<div><span>${escapeHtml(part.part ? `Parte ${part.part}` : `Archivo ${index + 1}`)}</span><code>${escapeHtml(part.relative_path || part.name || "")}</code><small>${escapeHtml(formatImportBytes(part.size_bytes))}</small></div>`).join("")}</div></section>` : ""}
          ${candidates.length ? `<section class="scanner-candidates"><div class="scanner-candidates-heading"><div><h4>Comparar coincidencias</h4><p>La similitud orienta la revisión; verificá título, año y fuente antes de vincular.</p></div></div>${candidates.map((candidate, index) => scannerCandidate(candidate, item, index)).join("")}</section>` : ""}
          <section class="scanner-confirm-detected${candidates.length ? " scanner-create-guard" : ""}${distinctReviewReady ? " is-confirming" : ""}">
            <div><h4>${createHeading}</h4><p>${createDescription}</p></div>
            <form data-scanner-confirm-form>
              <label><span>Título</span><input name="title" value="${escapeAttr(createDraft.title ?? item.detected_title ?? "")}" maxlength="240" required></label>
              <label><span>Año</span><input name="year" value="${escapeAttr(createDraft.year ?? item.detected_year ?? "")}" inputmode="numeric" pattern="(18|19|20|21)[0-9]{2}" maxlength="4" required></label>
              <label><span>Tipo</span><select name="kind">${["pelicula", "serie", "anime", "documental"].map((kind) => `<option value="${kind}" ${kind === (createDraft.kind || item.detected_kind) ? "selected" : ""}>${importKindLabel(kind)}</option>`).join("")}</select></label>
              <button class="action-primary" type="submit" data-scanner-review="${createAction}" data-file-id="${escapeAttr(item.id)}">${createButtonLabel}</button>
            </form>
          </section>
          <footer class="scanner-case-actions">
            <div><strong>¿No pertenece al inventario?</strong><span>Omitir retira ${multipart ? "todas las partes" : "el archivo"} de esta cola mientras no cambien.</span></div>
            <button class="quiet-action danger-action" type="button" data-scanner-review="ignore" data-file-id="${escapeAttr(item.id)}">Omitir ${actionObject}</button>
            <span id="scannerReviewFeedback" role="status" aria-live="polite"></span>
          </footer>`;
      }

      function scannerCandidatesForItem(item) {
        const conflict = scannerCreateConflicts.get(item.id);
        const verified = Array.isArray(conflict?.candidates) ? conflict.candidates : [];
        const verifiedKeys = new Set(verified.flatMap(scannerCandidateEquivalenceKeys));
        const detected = (Array.isArray(item.candidates) ? item.candidates : []).filter((candidate) =>
          !scannerCandidateEquivalenceKeys(candidate).some((key) => verifiedKeys.has(key))
        );
        const rows = [
          ...verified,
          ...detected
        ];
        const seen = new Set();
        return rows.filter((candidate) => {
          const identity = candidate.catalog_item_id
            || candidate.id
            || candidate.key
            || [normalizeText(candidate.title), candidate.year, candidate.kind].filter(Boolean).join(":");
          if (!identity || seen.has(identity)) return false;
          seen.add(identity);
          return true;
        });
      }

      function scannerCandidateEquivalenceKeys(candidate) {
        const year = String(candidate.year || "").trim();
        const kind = String(candidate.kind || "").trim();
        const titles = [
          candidate.title,
          candidate.original_title,
          candidate.spanish_title,
          candidate.english_title,
          ...(Array.isArray(candidate.alternative_titles) ? candidate.alternative_titles : [])
        ];
        const keys = titles
          .map(normalizeText)
          .filter(Boolean)
          .map((title) => `title:${title}|${year}|${kind}`);
        if (candidate.wikidata_id) keys.push(`wikidata:${String(candidate.wikidata_id).toUpperCase()}`);
        [candidate.url, candidate.wikipedia_url, candidate.imdb_url, candidate.filmaffinity_url]
          .filter(Boolean)
          .forEach((url) => keys.push(`url:${url}`));
        return [...new Set(keys)];
      }

      function actionObjectLabel(item) {
        return Number(item.file_count || 1) > 1 ? `${item.file_count} partes` : "archivo";
      }

      function scannerCandidate(candidate, item, index) {
        const title = candidate.spanish_title || candidate.title || candidate.original_title || "Obra sin título";
        const aliases = scannerCandidateAliases(candidate, title);
        const links = scannerCandidateLinks(candidate);
        const catalogItemId = candidate.catalog_item_id || "";
        const action = catalogItemId ? "link-catalog" : "confirm-candidate";
        const reference = catalogItemId
          ? `data-catalog-item-id="${escapeAttr(catalogItemId)}"`
          : `data-candidate-key="${escapeAttr(candidate.key || "")}"`;
        return `<article class="scanner-candidate-card">
          <header class="scanner-candidate-header">
            <div>
              <span class="scanner-candidate-index">Candidata ${index + 1}</span>
              <strong>${escapeHtml(title)}</strong>
              <span>${escapeHtml(scannerCandidateReason(candidate.reason))} · ${escapeHtml(formatScannerScore(candidate.score))}</span>
            </div>
            <button class="action-primary" type="button" data-scanner-review="${action}" ${reference} data-file-id="${escapeAttr(selectedScannerItemId)}">Vincular ${Number(item.file_count || 1) > 1 ? `${item.file_count} partes` : "archivo"}</button>
          </header>
          <div class="scanner-field-comparison" role="table" aria-label="Comparación con ${escapeAttr(title)}">
            <div class="scanner-comparison-head" role="row"><span role="columnheader">Campo</span><span role="columnheader">Archivo</span><span role="columnheader">Obra candidata</span></div>
            ${scannerComparisonRow("Título", item.detected_title || item.name || "Sin título", title)}
            ${scannerComparisonRow("Año", item.detected_year || "Sin año", candidate.year || "Sin año")}
            ${scannerComparisonRow("Tipo", importKindLabel(item.detected_kind) || "Película", importKindLabel(candidate.kind) || "Película")}
          </div>
          ${aliases.length ? `<div class="scanner-candidate-aliases"><span>Otros nombres</span><div>${aliases.map((alias) => `<span>${escapeHtml(alias)}</span>`).join("")}</div></div>` : ""}
          ${links ? `<nav class="scanner-candidate-links" aria-label="Fuentes de ${escapeAttr(title)}">${links}</nav>` : `<span class="scanner-candidate-no-links">Sin fuentes externas asociadas</span>`}
        </article>`;
      }

      function scannerComparisonRow(label, detected, candidate) {
        const same = normalizeText(detected) === normalizeText(candidate);
        return `<div class="scanner-comparison-row${same ? " is-match" : ""}" role="row">
          <span role="rowheader">${escapeHtml(label)}</span>
          <span role="cell">${escapeHtml(detected)}</span>
          <span role="cell">${escapeHtml(candidate)}</span>
        </div>`;
      }

      function scannerCandidateAliases(candidate, selectedTitle) {
        const values = [
          candidate.title,
          candidate.original_title,
          candidate.spanish_title,
          candidate.english_title,
          ...(Array.isArray(candidate.alternative_titles) ? candidate.alternative_titles : [])
        ].map((value) => String(value || "").trim()).filter(Boolean);
        const seen = new Set([normalizeText(selectedTitle)]);
        return values.filter((value) => {
          const key = normalizeText(value);
          if (!key || seen.has(key)) return false;
          seen.add(key);
          return true;
        }).slice(0, 8);
      }

      function scannerCandidateLinks(candidate) {
        const sources = [
          ["Wikipedia", candidate.wikipedia_url, "wikipedia.org"],
          ["IMDb", candidate.imdb_url, "imdb.com"],
          ["FilmAffinity", candidate.filmaffinity_url, "filmaffinity.com"]
        ];
        if (candidate.url) {
          if (hasHost(candidate.url, "wikipedia.org")) sources.push(["Wikipedia", candidate.url, "wikipedia.org"]);
          else if (hasHost(candidate.url, "imdb.com")) sources.push(["IMDb", candidate.url, "imdb.com"]);
          else if (hasHost(candidate.url, "filmaffinity.com")) sources.push(["FilmAffinity", candidate.url, "filmaffinity.com"]);
        }
        if (/^Q[0-9]+$/i.test(String(candidate.wikidata_id || ""))) {
          sources.push(["Wikidata", `https://www.wikidata.org/wiki/${candidate.wikidata_id}`, "wikidata.org"]);
        }
        const seen = new Set();
        return sources.filter(([, url, host]) => url && hasHost(url, host) && !seen.has(url) && seen.add(url)).map(([label, url]) =>
          `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`
        ).join("");
      }

      function formatScannerScore(value) {
        const score = Number(value);
        if (!Number.isFinite(score)) return "similitud sin puntaje";
        return `similitud ${Math.round((score <= 1 ? score * 100 : score))}%`;
      }

      function scannerCandidateReason(reason) {
        return {
          shared_external_url: "Misma fuente externa",
          shared_wikidata_id: "Mismo ID de Wikidata",
          exact_title_year: "Título y año exactos",
          exact_title_missing_year: "Título exacto; falta año",
          exact_title_year_mismatch: "Título exacto; año diferente",
          exact_title_kind_mismatch: "Título exacto; tipo diferente",
          similar_title_requires_review: "Título similar"
        }[reason] || "Coincidencia posible";
      }

      async function handleScannerReviewAction(event) {
        const button = event.submitter?.closest?.("[data-scanner-review]")
          || event.target.closest?.("[data-scanner-review]")
          || event.target.querySelector?.("[data-scanner-confirm-form] [data-scanner-review]");
        if (!button) return;
        event.preventDefault();
        const action = button.dataset.scannerReview;
        const fileId = button.dataset.fileId || selectedScannerItemId;
        if (action === "ignore") {
          const item = scannerQueue.find((entry) => entry.id === fileId);
          const count = Number(item?.file_count || 1);
          const confirmed = confirm(
            `¿Omitir "${item?.detected_title || item?.name || "este archivo"}"${count > 1 ? ` y sus ${count} partes` : ""}?\n\n`
            + `${count > 1 ? "Dejarán" : "Dejará"} de aparecer en la cola mientras no ${count > 1 ? "cambien" : "cambie"}. No se eliminará nada del disco ni del catálogo. Esta decisión todavía no puede restaurarse desde la interfaz.`
          );
          if (!confirmed) return;
        }
        const body = {
          action: action === "ignore"
            ? "ignore"
            : ["create-detected", "review-distinct", "create-distinct"].includes(action)
              ? "create"
              : action === "link-catalog" ? "link_catalog" : "confirm"
        };
        if (action === "confirm-candidate") {
          body.candidate_key = button.dataset.candidateKey || "";
        } else if (action === "link-catalog") {
          body.catalog_item_id = button.dataset.catalogItemId || "";
        } else if (["create-detected", "review-distinct", "create-distinct"].includes(action)) {
          const form = button.closest("form");
          if (!form?.reportValidity()) return;
          const data = new FormData(form);
          body.title = data.get("title") || "";
          body.year = data.get("year") || "";
          body.kind = data.get("kind") || "pelicula";
          if (action !== "create-detected") body.distinct_intent = true;
          if (action === "create-distinct") {
            body.distinct_review_token = scannerCreateConflicts.get(fileId)?.reviewToken || "";
          }
        }
        button.disabled = true;
        const feedback = fields.scannerQueueDetail.querySelector("#scannerReviewFeedback");
        if (feedback) {
          feedback.textContent = action === "ignore"
            ? "Omitiendo archivo…"
            : action === "review-distinct" ? "Comprobando coincidencias actuales…"
              : action === "create-distinct" ? "Creando una obra distinta…"
                : action === "create-detected" ? "Comprobando catálogo y creando obra…" : "Guardando vínculo…";
        }
        try {
          const response = await apiFetch(`/api/scanner/queue/${encodeURIComponent(fileId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (response.status === 409 && payload.reason === "possible_duplicate") {
            scannerCreateConflicts.set(
              fileId,
              {
                candidates: (payload.candidates || []).map((candidate) => ({
                  ...candidate,
                  catalog_item_id: candidate.id || ""
                })),
                reviewToken: payload.distinct_review_token || "",
                draft: {
                  title: body.title || "",
                  year: body.year || "",
                  kind: body.kind || "pelicula"
                }
              }
            );
            renderScannerQueueDetail();
            const conflictFeedback = fields.scannerQueueDetail.querySelector("#scannerReviewFeedback");
            if (conflictFeedback) {
              conflictFeedback.textContent = payload.distinct_review_token
                ? "La comprobación encontró fichas parecidas. Vinculá la correcta o confirmá que querés conservar ambas; todavía no modificamos nada."
                : "Encontramos una ficha existente. Comparala y vinculá el archivo; el catálogo no fue modificado.";
            }
            return;
          }
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          scannerCreateConflicts.delete(fileId);
          const priorIndex = scannerQueue.findIndex((item) => item.id === fileId);
          await Promise.all([loadScannerQueue(), loadCatalog(), loadLibraries()]);
          selectedScannerItemId = scannerQueue[Math.min(priorIndex, scannerQueue.length - 1)]?.id || "";
          renderScannerQueue();
          const affected = Number(payload.item?.file_count || 1);
          const linkedLabel = affected > 1 ? `${affected} partes vinculadas` : "Archivo vinculado";
          setCurationFeedback(
            action === "ignore"
              ? `${affected > 1 ? `${affected} partes omitidas` : "Archivo omitido"}. No se eliminó nada del disco.`
              : ["create-detected", "review-distinct", "create-distinct"].includes(action)
                ? payload.catalog_action === "existing"
                  ? `La obra ya estaba en tu catálogo. ${linkedLabel} al inventario compartido.`
                  : payload.catalog_action === "created_distinct"
                    ? `Conservamos ambas obras. Nueva ficha creada y ${linkedLabel.toLowerCase()} con su identidad.`
                    : `Obra agregada a tu catálogo. ${linkedLabel} al inventario compartido.`
                : `${linkedLabel} al inventario compartido.`,
            "success"
          );
          if (selectedScannerItemId) focusSelectedScannerItem();
          else fields.refreshScannerQueue.focus({ preventScroll: true });
        } catch (error) {
          if (feedback) feedback.textContent = libraryErrorMessage(error.message);
          button.disabled = false;
        }
      }

      async function loadImportDrafts({ selectId = "", announce = false, refreshSelected = true } = {}) {
        if (importLoading) return;
        importLoading = true;
        fields.importInboxPanel.setAttribute("aria-busy", "true");
        if (announce) setImportFeedback(fields.importSourceFeedback, "Actualizando borradores…", "working");
        let targetId = String(selectId || (refreshSelected ? selectedImportDraft?.id : "") || "");
        try {
          const response = await apiFetch("/api/imports");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          importDrafts = payload.drafts || [];
          fields.importDraftCount.textContent = String(importDrafts.length);
          if (targetId && !importDrafts.some((draft) => draft.id === targetId)) targetId = "";
          if (!targetId && selectedImportDraft && !importDrafts.some((draft) => draft.id === selectedImportDraft.id)) {
            selectedImportDraft = null;
            selectedImportItems.clear();
            showImportSourcePanel({ reset: false });
          }
          renderImportDraftList();
          if (announce) setImportFeedback(fields.importSourceFeedback, "Borradores actualizados.", "success");
        } catch (error) {
          console.error("[movie-inbox] import drafts load failed", error);
          importDrafts = [];
          fields.importDraftCount.textContent = "!";
          fields.importDraftList.innerHTML = `<div class="import-draft-empty"><strong>Borradores no disponibles</strong><p>Actualizá la Bandeja para volver a intentar.</p></div>`;
          setImportFeedback(fields.importSourceFeedback, importErrorMessage(error.message), "error");
          targetId = "";
        } finally {
          importLoading = false;
          fields.importInboxPanel.setAttribute("aria-busy", "false");
        }
        if (targetId) await selectImportDraft(targetId);
      }

      function renderImportDraftList() {
        if (!importDrafts.length) {
          fields.importDraftList.innerHTML = `<div class="import-draft-empty"><strong>Sin borradores</strong><p>Elegí un archivo o pegá contenido para preparar el primer ingreso.</p></div>`;
          return;
        }
        fields.importDraftList.innerHTML = importDrafts.map((draft) => {
          const counts = draft.counts || {};
          const selected = draft.id === selectedImportDraft?.id;
          const applied = draft.status === "applied";
          const stateLabel = applied
            ? "Aplicado"
            : draft.status === "applying"
              ? "Aplicando"
              : draft.status === "failed"
                ? "Reintentar"
                : formatImportExpiry(draft.expires_at);
          return `<button class="import-draft-item${selected ? " selected" : ""}" type="button"
            data-import-draft="${escapeAttr(draft.id || "")}" aria-pressed="${selected}">
            <strong>${escapeHtml(draft.source?.name || "Importación")}</strong>
            <span class="import-draft-item-meta">
              <span>${escapeHtml(String(draft.source?.format || "").toUpperCase())}</span>
              <span>${Number(counts.total || 0)} filas</span>
              <span>${stateLabel}</span>
            </span>
            <span class="import-draft-item-states">
              <span class="new">${Number(counts.new || 0)} nuevas</span>
              ${Number(counts.review || 0) ? `<span class="review">${Number(counts.review)} revisar</span>` : ""}
              ${Number(counts.invalid || 0) ? `<span class="invalid">${Number(counts.invalid)} inválidas</span>` : ""}
            </span>
          </button>`;
        }).join("");
      }

      function showImportSourcePanel({ reset = true, focus = false } = {}) {
        selectedImportDraft = null;
        selectedImportItems.clear();
        fields.importSourcePanel.hidden = false;
        fields.importReviewPanel.hidden = true;
        if (reset) resetImportSourceForm();
        renderImportDraftList();
        if (focus) fields.importFile.focus({ preventScroll: true });
      }

      function resetImportSourceForm() {
        fields.importSourceForm.reset();
        fields.importSourceName.value = "contenido-pegado";
        fields.importFileMeta.textContent = "Ningún archivo seleccionado";
        setImportInputMode("file");
        renderImportCsvFields([]);
        setImportFeedback(fields.importSourceFeedback, "");
      }

      async function selectImportDraft(draftId) {
        const id = String(draftId || "");
        if (!id) return;
        fields.importInboxPanel.setAttribute("aria-busy", "true");
        try {
          const response = await apiFetch(`/api/imports/${encodeURIComponent(id)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedImportDraft = payload;
          importFilter = "all";
          importVisibleCount = IMPORT_PREVIEW_PAGE_SIZE;
          importDestination = "catalog";
          selectedImportItems = new Set(
            (payload.items || []).filter((entry) => entry.catalog_eligible).map((entry) => entry.id)
          );
          fields.importSourcePanel.hidden = true;
          fields.importReviewPanel.hidden = false;
          renderImportDraftList();
          renderImportReview();
        } catch (error) {
          console.error("[movie-inbox] import draft detail failed", error);
          if (error.message === "import_draft_expired" || error.message === "import_draft_not_found") {
            selectedImportDraft = null;
            showImportSourcePanel({ reset: false });
            await loadImportDrafts({ refreshSelected: false });
          }
          setImportFeedback(fields.importSourceFeedback, importErrorMessage(error.message), "error");
        } finally {
          fields.importInboxPanel.setAttribute("aria-busy", "false");
        }
      }

      function renderImportReview() {
        const draft = selectedImportDraft;
        if (!draft) return;
        const counts = draft.counts || {};
        fields.importReviewKicker.textContent = {
          applied: "Importación aplicada",
          applying: "Aplicación en curso",
          failed: "Reintento disponible"
        }[draft.status] || "Borrador listo";
        fields.importReviewTitle.textContent = draft.source?.name || "Previsualización";
        fields.importReviewMeta.textContent = `${String(draft.source?.format || "").toUpperCase()} · ${Number(counts.total || 0)} filas · ${formatImportExpiry(draft.expires_at)}`;
        fields.deleteImportDraft.disabled = draft.status === "applying";
        fields.importMetrics.innerHTML = [
          ["total", "Total"],
          ["new", "Nuevas"],
          ["present", "Presentes"],
          ["review", "Revisar"],
          ["invalid", "Inválidas"]
        ].map(([state, label]) => `<div class="import-metric" data-state="${state}"><strong>${Number(counts[state] || 0)}</strong><span>${label}</span></div>`).join("");
        fields.importStateFilters.querySelectorAll("[data-import-filter]").forEach((button) => {
          const active = button.dataset.importFilter === importFilter;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        renderImportDestination();
        renderImportPreviewRows();
        renderImportResult();
      }

      function renderImportDestination() {
        const owner = currentIdentity?.user?.role === "owner";
        fields.importCollectionDestination.hidden = !owner;
        if (!owner && importDestination === "collection") importDestination = "catalog";
        fields.importDestinationModes.querySelectorAll("[data-import-destination]").forEach((button) => {
          const active = button.dataset.importDestination === importDestination;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
          button.disabled = ["applied", "applying"].includes(selectedImportDraft?.status);
        });
        const collection = importDestination === "collection";
        fields.importPersonalOptions.hidden = collection;
        fields.importPersonalOptions.disabled = ["applied", "applying"].includes(selectedImportDraft?.status);
        fields.importCollectionOptions.hidden = !collection;
        fields.applyImport.textContent = collection ? "Crear colección privada" : "Importar selección";
        if (collection && !fields.importCollectionTitle.value.trim()) {
          fields.importCollectionTitle.value = importCollectionTitle(selectedImportDraft?.source?.name || "Colección importada");
        }
      }

      function renderImportPreviewRows() {
        const filtered = filteredImportItems();
        const rows = visibleImportItems();
        fields.importPreviewRows.innerHTML = rows.map((entry) => {
          const item = entry.item || {};
          const eligible = canSelectImportItem(entry) && selectedImportDraft?.status !== "applied";
          const selected = selectedImportItems.has(entry.id);
          const title = item.title || entry.label || "Entrada sin título";
          const original = item.original_title && item.original_title !== title ? item.original_title : "";
          const data = [item.year, importKindLabel(item.kind), item.source].filter(Boolean).join(" · ") || "Sin datos adicionales";
          const link = importUrlLabel(item.url || item.wikipedia_url || item.imdb_url || item.filmaffinity_url);
          const candidate = entry.candidates?.[0];
          const detail = candidate
            ? `Posible: ${candidate.title || candidate.id || "obra existente"}${candidate.year ? ` (${candidate.year})` : ""}`
            : importReasonLabel(entry.reason);
          return `<tr data-state="${escapeAttr(entry.state || "invalid")}">
            <td><input type="checkbox" data-import-item="${escapeAttr(entry.id || "")}" aria-label="Seleccionar ${escapeAttr(title)}" ${selected ? "checked" : ""} ${eligible ? "" : "disabled"}></td>
            <td><span class="import-title-cell"><strong>${escapeHtml(title)}</strong>${original ? `<small>${escapeHtml(original)}</small>` : ""}</span></td>
            <td><span class="import-data-cell">${escapeHtml(data)}${link ? `<br>${escapeHtml(link)}` : ""}</span></td>
            <td><span class="import-state-cell"><span class="import-state-badge ${escapeAttr(entry.state || "invalid")}">${escapeHtml(importStateLabel(entry.state))}</span><small>${escapeHtml(detail)}</small></span></td>
          </tr>`;
        }).join("");
        fields.importPreviewEmpty.hidden = Boolean(rows.length);
        fields.importPreviewRows.closest(".import-table-wrap").hidden = !rows.length;
        const remaining = Math.max(0, filtered.length - rows.length);
        fields.loadMoreImportRows.hidden = !remaining;
        fields.loadMoreImportRows.textContent = remaining
          ? `Cargar ${Math.min(IMPORT_PREVIEW_PAGE_SIZE, remaining)} más · ${remaining} pendientes`
          : "Cargar más";
        syncImportSelection();
      }

      function filteredImportItems() {
        const rows = selectedImportDraft?.items || [];
        return importFilter === "all" ? rows : rows.filter((entry) => entry.state === importFilter);
      }

      function visibleImportItems() {
        return filteredImportItems().slice(0, importVisibleCount);
      }

      function canSelectImportItem(entry) {
        return importDestination === "collection" ? Boolean(entry.collection_eligible) : Boolean(entry.catalog_eligible);
      }

      function changeImportSelection(event) {
        const checkbox = event.target.closest("[data-import-item]");
        if (!checkbox) return;
        const itemId = checkbox.dataset.importItem || "";
        if (checkbox.checked) selectedImportItems.add(itemId);
        else selectedImportItems.delete(itemId);
        syncImportSelection();
      }

      function toggleVisibleImportItems() {
        const eligible = visibleImportItems().filter(canSelectImportItem).map((entry) => entry.id);
        if (fields.selectVisibleImportItems.checked) eligible.forEach((id) => selectedImportItems.add(id));
        else eligible.forEach((id) => selectedImportItems.delete(id));
        renderImportPreviewRows();
      }

      function syncImportSelection() {
        const eligible = visibleImportItems().filter(canSelectImportItem).map((entry) => entry.id);
        const selectedVisible = eligible.filter((id) => selectedImportItems.has(id));
        fields.selectVisibleImportItems.checked = Boolean(eligible.length) && selectedVisible.length === eligible.length;
        fields.selectVisibleImportItems.indeterminate = selectedVisible.length > 0 && selectedVisible.length < eligible.length;
        fields.selectVisibleImportItems.disabled = !eligible.length || selectedImportDraft?.status === "applied";
        const count = selectedImportItems.size;
        fields.importSelectionSummary.textContent = `${count} ${count === 1 ? "seleccionada" : "seleccionadas"}`;
        fields.applyImport.disabled = !count || selectedImportDraft?.status === "applied" || selectedImportDraft?.status === "applying";
      }

      async function handleImportClick(event) {
        const newButton = event.target.closest("#newImportDraft");
        if (newButton) {
          showImportSourcePanel({ reset: true, focus: true });
          return;
        }
        const draftButton = event.target.closest("[data-import-draft]");
        if (draftButton) {
          await selectImportDraft(draftButton.dataset.importDraft || "");
          return;
        }
        const inputButton = event.target.closest("[data-import-input]");
        if (inputButton) {
          setImportInputMode(inputButton.dataset.importInput || "file", true);
          return;
        }
        const filterButton = event.target.closest("[data-import-filter]");
        if (filterButton) {
          importFilter = filterButton.dataset.importFilter || "all";
          importVisibleCount = IMPORT_PREVIEW_PAGE_SIZE;
          renderImportReview();
          return;
        }
        if (event.target.closest("#loadMoreImportRows")) {
          importVisibleCount += IMPORT_PREVIEW_PAGE_SIZE;
          renderImportPreviewRows();
          return;
        }
        const destinationButton = event.target.closest("[data-import-destination]");
        if (destinationButton) {
          importDestination = destinationButton.dataset.importDestination === "collection" ? "collection" : "catalog";
          selectedImportItems = new Set(
            (selectedImportDraft?.items || []).filter(canSelectImportItem).map((entry) => entry.id)
          );
          renderImportDestination();
          renderImportPreviewRows();
          renderImportResult();
          return;
        }
        if (event.target.closest("#deleteImportDraft")) {
          await deleteSelectedImportDraft();
          return;
        }
        const collectionButton = event.target.closest("[data-open-import-collection]");
        if (collectionButton) await openImportedCollection(collectionButton.dataset.openImportCollection || "");
      }

      function setImportInputMode(mode, focus = false) {
        importInputMode = mode === "paste" ? "paste" : "file";
        const paste = importInputMode === "paste";
        fields.importFileInputPanel.hidden = paste;
        fields.importPasteInputPanel.hidden = !paste;
        fields.importInputModes.querySelectorAll("[data-import-input]").forEach((button) => {
          const active = button.dataset.importInput === importInputMode;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        if (focus) (paste ? fields.importContent : fields.importFile).focus({ preventScroll: true });
        refreshImportMapping();
      }

      async function changeImportFile() {
        const file = fields.importFile.files?.[0];
        if (!file) {
          fields.importFileMeta.textContent = "Ningún archivo seleccionado";
          return;
        }
        fields.importFileMeta.textContent = `${file.name} · ${formatImportBytes(file.size)}`;
        if (file.size > IMPORT_MAX_BYTES) {
          setImportFeedback(fields.importSourceFeedback, "El archivo supera el límite de 8 MiB.", "error");
          return;
        }
        if (fields.importFormat.value === "auto") {
          const inferred = inferImportFormat(file.name);
          if (inferred) fields.importFormat.value = inferred;
        }
        await refreshImportMapping();
      }

      async function refreshImportMapping() {
        const format = resolvedImportFormat();
        if (format !== "csv") {
          renderImportCsvFields([]);
          return;
        }
        try {
          const content = importInputMode === "file"
            ? await readImportFile({ requireSelection: false })
            : fields.importContent.value;
          renderImportCsvFields(parseCsvHeader(content || ""));
        } catch (_error) {
          renderImportCsvFields([]);
        }
      }

      function renderImportCsvFields(headers) {
        fields.importCsvMapping.hidden = !headers.length;
        fields.importCsvFields.innerHTML = headers.length ? IMPORT_COLUMN_FIELDS.map(([field, label]) => `
          <label><span>${label}</span><select data-import-column="${field}">
            <option value="">Detectar</option>
            ${headers.map((header) => `<option value="${escapeAttr(header)}">${escapeHtml(header)}</option>`).join("")}
          </select></label>`).join("") : "";
      }

      async function analyzeImportSource(event) {
        event.preventDefault();
        fields.analyzeImport.disabled = true;
        setImportFeedback(fields.importSourceFeedback, "Analizando y comparando con tu catálogo…", "working");
        try {
          const content = importInputMode === "file"
            ? await readImportFile({ requireSelection: true })
            : fields.importContent.value;
          if (!String(content || "").trim()) throw new Error("import_content_empty");
          const file = fields.importFile.files?.[0];
          const sourceName = importInputMode === "file" ? file.name : fields.importSourceName.value;
          const response = await apiFetch("/api/imports", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              source_name: sourceName || "importacion",
              source_format: fields.importFormat.value || "auto",
              content,
              column_map: importColumnMap()
            })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedImportDraft = payload;
          selectedImportItems = new Set((payload.items || []).filter((entry) => entry.catalog_eligible).map((entry) => entry.id));
          importFilter = "all";
          importVisibleCount = IMPORT_PREVIEW_PAGE_SIZE;
          importDestination = "catalog";
          fields.importSourcePanel.hidden = true;
          fields.importReviewPanel.hidden = false;
          await loadImportDrafts({ selectId: payload.id });
        } catch (error) {
          console.error("[movie-inbox] import analysis failed", error);
          setImportFeedback(fields.importSourceFeedback, importErrorMessage(error.message), "error");
        } finally {
          fields.analyzeImport.disabled = false;
        }
      }

      async function readImportFile({ requireSelection }) {
        const file = fields.importFile.files?.[0];
        if (!file) {
          if (requireSelection) throw new Error("import_file_required");
          return "";
        }
        if (file.size > IMPORT_MAX_BYTES) throw new Error("import_file_too_large");
        return file.text();
      }

      function importColumnMap() {
        if (resolvedImportFormat() !== "csv") return {};
        return Object.fromEntries(
          [...fields.importCsvFields.querySelectorAll("[data-import-column]")]
            .map((select) => [select.dataset.importColumn, select.value])
            .filter(([, value]) => value)
        );
      }

      async function applySelectedImport(event) {
        event.preventDefault();
        const draft = selectedImportDraft;
        if (!draft || !selectedImportItems.size) return;
        if (importDestination === "collection" && !fields.importCollectionTitle.value.trim()) {
          setImportFeedback(fields.importApplyFeedback, "Escribí un nombre para la colección.", "error");
          fields.importCollectionTitle.focus();
          return;
        }
        fields.applyImport.disabled = true;
        setImportFeedback(
          fields.importApplyFeedback,
          importDestination === "collection" ? "Creando colección privada…" : "Importando a tu catálogo…",
          "working"
        );
        try {
          const personalOptions = Object.fromEntries(
            [...fields.importPersonalOptions.querySelectorAll("[data-import-option]")]
              .map((checkbox) => [checkbox.dataset.importOption, checkbox.checked])
          );
          const response = await apiFetch(`/api/imports/${encodeURIComponent(draft.id)}/apply`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              destination: importDestination,
              item_ids: [...selectedImportItems],
              personal_options: personalOptions,
              collection_title: fields.importCollectionTitle.value,
              collection_description: fields.importCollectionDescription.value
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          if (importDestination === "catalog") await loadCatalog();
          else await loadImportDrafts({ selectId: draft.id });
          setImportResultFeedback(payload);
        } catch (error) {
          console.error("[movie-inbox] import apply failed", error);
          setImportFeedback(fields.importApplyFeedback, importErrorMessage(error.message), "error");
          syncImportSelection();
        }
      }

      async function deleteSelectedImportDraft() {
        const draft = selectedImportDraft;
        if (!draft || !window.confirm(`¿Eliminar el borrador "${draft.source?.name || "Importación"}"? Esta acción no se puede deshacer.`)) return;
        fields.deleteImportDraft.disabled = true;
        try {
          const response = await apiFetch(`/api/imports/${encodeURIComponent(draft.id)}/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confirmed: true })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedImportDraft = null;
          selectedImportItems.clear();
          showImportSourcePanel({ reset: false });
          await loadImportDrafts({ refreshSelected: false });
          setImportFeedback(fields.importSourceFeedback, "Borrador eliminado.", "success");
        } catch (error) {
          setImportFeedback(fields.importApplyFeedback, importErrorMessage(error.message), "error");
          fields.deleteImportDraft.disabled = false;
        }
      }

      function renderImportResult() {
        const result = selectedImportDraft?.result;
        if (selectedImportDraft?.status === "applying") {
          setImportFeedback(fields.importApplyFeedback, "La selección se está aplicando. Actualizá los borradores para comprobar el resultado.", "working");
          return;
        }
        if (selectedImportDraft?.status === "failed") {
          setImportFeedback(fields.importApplyFeedback, "La operación anterior no terminó. Revisá la selección y volvé a importar; no se duplicarán obras exactas.", "error");
          return;
        }
        if (selectedImportDraft?.status !== "applied" || !result?.ok) {
          setImportFeedback(fields.importApplyFeedback, "");
          return;
        }
        setImportResultFeedback(result);
      }

      function setImportResultFeedback(result) {
        const summary = result.summary || {};
        if (result.destination === "collection") {
          const collection = result.collection || {};
          fields.importApplyFeedback.dataset.tone = "success";
          fields.importApplyFeedback.innerHTML = `Colección privada creada con ${Number(summary.created || 0)} obras. <button class="text-action" type="button" data-open-import-collection="${escapeAttr(collection.id || "")}">Ver colección</button>`;
          return;
        }
        const parts = [];
        if (summary.added) parts.push(`${summary.added} agregadas`);
        if (summary.present) parts.push(`${summary.present} ya presentes`);
        if (summary.review) parts.push(`${summary.review} sin importar por posible coincidencia`);
        setImportFeedback(fields.importApplyFeedback, parts.join(" · ") || "Importación completada sin cambios.", "success");
      }

      async function openImportedCollection(collectionId) {
        if (!collectionId) return;
        clubMode = "collections";
        selectedCollectionId = collectionId;
        await goToClub();
        await openCollection(collectionId);
      }

      function setImportFeedback(field, message, tone = "", html = false) {
        if (html) field.innerHTML = message;
        else field.textContent = message;
        field.dataset.tone = tone;
      }

      function importErrorMessage(reason) {
        const value = String(reason || "");
        if (value === "import_file_required") return "Elegí un archivo TXT, CSV o JSON.";
        if (value === "import_file_too_large" || value.includes("8 MiB") || value === "request_too_large") return "El contenido supera el límite de 8 MiB.";
        if (value === "import_content_empty" || value.toLowerCase().includes("empty")) return "El origen no contiene entradas para analizar.";
        if (value === "import_draft_expired") return "El borrador expiró. Prepará una nueva importación.";
        if (value === "import_draft_busy") return "Este borrador ya se está aplicando. Actualizá la Bandeja en unos segundos.";
        if (value === "import_draft_limit_reached") return "Llegaste a 20 borradores. Eliminá uno antes de preparar otra importación.";
        if (value.includes("CSV") || value.includes("JSON") || value.includes("format")) return `No pudimos interpretar el archivo: ${value}`;
        if (value === "import_store_unavailable") return "Los borradores no están disponibles. Volvé a intentar.";
        return "No pudimos completar la importación. Revisá el formato y volvé a intentar.";
      }

      function resolvedImportFormat() {
        const chosen = fields.importFormat.value || "auto";
        if (chosen !== "auto") return chosen;
        const name = importInputMode === "file" ? fields.importFile.files?.[0]?.name : fields.importSourceName.value;
        const inferred = inferImportFormat(name);
        if (inferred) return inferred;
        if (importInputMode === "paste") {
          const content = fields.importContent.value.trimStart();
          if (content.startsWith("{") || content.startsWith("[")) return "json";
          const firstLine = content.split(/\r?\n/, 1)[0] || "";
          if (/[,;\t|]/.test(firstLine) && parseCsvHeader(content).length >= 2) return "csv";
        }
        return "txt";
      }

      function inferImportFormat(name) {
        const extension = String(name || "").toLowerCase().split(".").pop();
        return ["txt", "csv", "json"].includes(extension) ? extension : "";
      }

      function parseCsvHeader(content) {
        const text = String(content || "").replace(/^\uFEFF/, "");
        if (!text.trim()) return [];
        const values = [];
        let value = "";
        let quoted = false;
        for (let index = 0; index < text.length; index += 1) {
          const character = text[index];
          if (character === '"') {
            if (quoted && text[index + 1] === '"') {
              value += '"';
              index += 1;
            } else {
              quoted = !quoted;
            }
          } else if (!quoted && (character === "," || character === ";" || character === "\t")) {
            values.push(value.trim());
            value = "";
          } else if (!quoted && (character === "\n" || character === "\r")) {
            values.push(value.trim());
            break;
          } else {
            value += character;
          }
          if (index === text.length - 1) values.push(value.trim());
          if (values.length > 100) return [];
        }
        return [...new Set(values.filter(Boolean))];
      }

      function importCollectionTitle(sourceName) {
        return String(sourceName || "Colección importada")
          .replace(/\.(txt|csv|json)$/i, "")
          .replace(/[_-]+/g, " ")
          .replace(/\s+/g, " ")
          .trim()
          .slice(0, 120) || "Colección importada";
      }

      function formatImportExpiry(value) {
        const remaining = new Date(value).getTime() - Date.now();
        if (!Number.isFinite(remaining) || remaining <= 0) return "Expirado";
        const hours = remaining / 3600000;
        return hours > 24 ? `${Math.ceil(hours / 24)} d restantes` : `${Math.max(1, Math.ceil(hours))} h restantes`;
      }

      function formatImportBytes(value) {
        const bytes = Number(value || 0);
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
      }

      function importStateLabel(state) {
        return { new: "Nueva", present: "Presente", review: "Revisar", invalid: "Inválida" }[state] || "Inválida";
      }

      function importReasonLabel(reason) {
        return {
          new_item: "No encontramos una coincidencia en tu catálogo",
          already_in_catalog: "La misma referencia ya existe en tu catálogo",
          possible_catalog_match: "El título se parece a una obra existente",
          duplicate_in_source: "Esta fila repite otra entrada del mismo origen",
          possible_duplicate_in_source: "Podría repetir otra entrada del mismo origen",
          title_not_recognized: "No pudimos reconocer un título",
          invalid_item: "La fila no cumple el formato esperado",
          json_item_not_object: "La entrada JSON no es un objeto"
        }[reason] || String(reason || "Revisión necesaria").replace(/_/g, " ");
      }

      function importKindLabel(value) {
        return { pelicula: "Película", serie: "Serie", anime: "Anime", documental: "Documental" }[value] || "";
      }

      function importUrlLabel(value) {
        try {
          return value ? new URL(value).hostname.replace(/^www\./, "") : "";
        } catch (_error) {
          return "";
        }
      }

      async function loadCurationQueue({ announce = false } = {}) {
        if (curationLoading) return;
        curationLoading = true;
        fields.inboxView.setAttribute("aria-busy", "true");
        fields.refreshCuration.disabled = true;
        if (announce) setCurationFeedback("Actualizando bandeja…", "working");
        try {
          const response = await apiFetch("/api/curation");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationCases = payload.cases || [];
          curationCounts = {
            pending: 0,
            duplicates: 0,
            missing_link: 0,
            deferred: 0,
            scanner: curationCounts.scanner || 0,
            ...(payload.counts || {})
          };
          const visible = visibleCurationCases();
          if (!visible.some((entry) => entry.id === selectedCurationCaseId)) {
            selectedCurationCaseId = visible[0]?.id || "";
          }
          await loadCurationHistory();
          syncCurationCounts();
          renderCuration();
          if (announce) setCurationFeedback("Bandeja actualizada", "success");
        } catch (error) {
          console.error("[catalog-viewer] curation load failed", error);
          setCurationFeedback("No se pudo cargar la bandeja. Reintentá desde Actualizar bandeja.", "error");
          fields.curationQueue.innerHTML = "";
          fields.curationDetail.innerHTML = curationEmptyState("Bandeja no disponible", "La colección permanece intacta.");
        } finally {
          curationLoading = false;
          fields.inboxView.setAttribute("aria-busy", "false");
          fields.refreshCuration.disabled = false;
        }
      }

      async function loadCurationHistory() {
        if (curationHistoryLoading) return;
        curationHistoryLoading = true;
        try {
          const response = await apiFetch(`/api/curation/history?mode=${encodeURIComponent(curationHistoryMode)}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationHistory = payload.operations || [];
          fields.curationHistoryCount.textContent = payload.count || 0;
        } catch (error) {
          console.error("[catalog-viewer] curation history load failed", error);
          curationHistory = [];
          fields.curationHistoryCount.textContent = "!";
          if (curationFilter === "history") {
            setCurationFeedback("No se pudo cargar el historial de curaduría.", "error");
          }
        } finally {
          curationHistoryLoading = false;
        }
      }

      function storedClubMode() {
        try {
          const stored = localStorage.getItem("movie-inbox-club-mode");
          return stored === "members" ? "members" : "collections";
        } catch (_) {
          return "collections";
        }
      }

      function storedHistoryMode() {
        try {
          return localStorage.getItem("movie-inbox-curation-history-mode") === "session"
            ? "session"
            : "persistent";
        } catch (_) {
          return "persistent";
        }
      }

      async function changeCurationHistoryMode() {
        curationHistoryMode = fields.persistCurationHistory.checked ? "persistent" : "session";
        try {
          localStorage.setItem("movie-inbox-curation-history-mode", curationHistoryMode);
        } catch (_) {
          // The preference remains active for this page even when storage is unavailable.
        }
        fields.persistCurationHistory.nextElementSibling.textContent = curationHistoryMode === "persistent"
          ? "Historial persistente"
          : "Sólo esta sesión";
        selectedCurationCaseId = "";
        await loadCurationHistory();
        renderCuration();
        setCurationFeedback(
          curationHistoryMode === "persistent"
            ? "Las próximas decisiones conservarán Deshacer después de reiniciar."
            : "Las próximas decisiones podrán deshacerse sólo durante esta sesión.",
          "success"
        );
      }

      async function clearCurationHistory() {
        const count = curationHistory.length;
        if (!count) {
          setCurationFeedback("No hay actividad para limpiar.", "");
          return;
        }
        const confirmed = confirm(
          `Eliminar ${count} ${count === 1 ? "operación" : "operaciones"} del historial? Ya no podrán deshacerse.`
        );
        if (!confirmed) return;
        fields.clearCurationHistory.disabled = true;
        try {
          const response = await apiFetch("/api/curation/history/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              history_mode: curationHistoryMode,
              confirmed: true
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          curationHistory = [];
          selectedCurationCaseId = "";
          syncCurationCounts();
          renderCuration();
          setCurationFeedback("Historial eliminado.", "success");
        } catch (error) {
          console.error("[catalog-viewer] history clear failed", error);
          setCurationFeedback("No se pudo limpiar el historial. El catálogo no fue modificado.", "error");
        } finally {
          fields.clearCurationHistory.disabled = false;
        }
      }

      function syncCurationCounts() {
        fields.curationPendingCount.textContent = curationCounts.pending || 0;
        fields.curationDuplicateCount.textContent = curationCounts.duplicates || 0;
        fields.curationMissingCount.textContent = curationCounts.missing_link || 0;
        fields.curationDeferredCount.textContent = curationCounts.deferred || 0;
        fields.curationHistoryCount.textContent = curationHistory.length || 0;
        fields.scannerQueueCount.textContent = curationCounts.scanner || 0;
        const pendingTotal = Number(curationCounts.pending || 0) + Number(curationCounts.scanner || 0);
        fields.inboxBadge.textContent = pendingTotal;
        fields.inboxBadge.hidden = !(pendingTotal > 0);
        fields.inboxButton.setAttribute(
          "aria-label",
          pendingTotal
            ? `Bandeja, ${pendingTotal} ${
                pendingTotal === 1 ? "decisión pendiente" : "decisiones pendientes"
              }`
            : "Bandeja, sin decisiones pendientes"
        );
      }

      function handleCurationClick(event) {
        const filter = event.target.closest("[data-curation-filter]");
        if (filter) {
          curationFilter = filter.dataset.curationFilter || "pending";
          selectedCurationCaseId = "";
          renderCuration();
          return;
        }
        const queueItem = event.target.closest("[data-curation-case]");
        if (queueItem) {
          selectedCurationCaseId = queueItem.dataset.curationCase || "";
          renderCuration();
          return;
        }
        const action = event.target.closest("[data-curation-action]");
        if (!action) return;
        const actionName = action.dataset.curationAction;
        if (actionName === "undo-operation") {
          undoCurationOperation(action.dataset.operationId || selectedCurationCaseId);
          return;
        }
        const selected = curationCases.find((entry) => entry.id === selectedCurationCaseId);
        if (!selected) return;
        if (actionName === "open-primary") {
          openCurationItem(selected.primary);
          return;
        }
        if (actionName === "open-secondary" && selected.secondary) {
          openCurationItem(selected.secondary);
          return;
        }
        if (actionName === "find-link") {
          findLinkFromCuration(selected.primary);
          return;
        }
        if (actionName === "compare-duplicate" && selected.secondary) {
          openInternalMergeComparator(selected);
          return;
        }
        if (actionName === "link-deferred") updateLinkCuration(selected, "deferred");
        if (actionName === "link-not-required") updateLinkCuration(selected, "not_required");
        if (actionName === "link-pending") updateLinkCuration(selected, "pending");
        if (actionName === "duplicate-deferred") updateDuplicateCuration(selected, "deferred");
        if (actionName === "duplicate-not-duplicate") updateDuplicateCuration(selected, "not_duplicate");
        if (actionName === "duplicate-pending") updateDuplicateCuration(selected, "pending");
      }

      function visibleCurationCases() {
        if (curationFilter === "history") return [];
        if (curationFilter === "deferred") {
          return curationCases.filter((entry) => entry.status === "deferred");
        }
        const pending = curationCases.filter((entry) => entry.status === "pending");
        if (curationFilter === "duplicate") return pending.filter((entry) => entry.type === "duplicate");
        if (curationFilter === "missing_link") return pending.filter((entry) => entry.type === "missing_link");
        return pending;
      }

      function renderCuration() {
        if (curationFilter === "history") {
          renderCurationHistory();
          return;
        }
        const visible = visibleCurationCases();
        if (!visible.some((entry) => entry.id === selectedCurationCaseId)) {
          selectedCurationCaseId = visible[0]?.id || "";
        }
        fields.inboxView.querySelectorAll("[data-curation-filter]").forEach((button) => {
          const active = button.dataset.curationFilter === curationFilter;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        const labels = {
          pending: "Decisiones pendientes",
          duplicate: "Posibles duplicados",
          missing_link: "Entradas sin link",
          deferred: "Decisiones pospuestas"
        };
        fields.curationQueueTitle.textContent = labels[curationFilter] || labels.pending;
        fields.curationQueueMeta.textContent = `${visible.length} ${visible.length === 1 ? "caso" : "casos"}`;
        fields.curationQueue.innerHTML = visible.length
          ? visible.map(curationQueueItem).join("")
          : curationEmptyState(
              curationFilter === "deferred" ? "No hay decisiones pospuestas" : "No quedan casos en esta cola",
              curationFilter === "pending" ? "La bandeja está al día." : "Probá otro filtro."
            );
        const selected = visible.find((entry) => entry.id === selectedCurationCaseId);
        fields.curationDetail.innerHTML = selected
          ? curationCaseDetail(selected)
          : curationEmptyState("Sin caso seleccionado", "La evidencia aparecerá cuando haya una decisión disponible.");
      }

      function renderCurationHistory() {
        if (!curationHistory.some((entry) => entry.id === selectedCurationCaseId)) {
          selectedCurationCaseId = curationHistory[0]?.id || "";
        }
        fields.inboxView.querySelectorAll("[data-curation-filter]").forEach((button) => {
          const active = button.dataset.curationFilter === "history";
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        fields.curationQueueTitle.textContent = curationHistoryMode === "persistent"
          ? "Actividad persistente"
          : "Actividad de esta sesión";
        fields.curationQueueMeta.textContent = `${curationHistory.length} ${
          curationHistory.length === 1 ? "operación" : "operaciones"
        }`;
        fields.curationQueue.innerHTML = curationHistory.length
          ? curationHistory.map(curationHistoryItem).join("")
          : curationEmptyState("Todavía no hay actividad", "Las decisiones nuevas aparecerán en este registro.");
        const selected = curationHistory.find((entry) => entry.id === selectedCurationCaseId);
        fields.curationDetail.innerHTML = selected
          ? curationHistoryDetail(selected)
          : curationEmptyState("Sin operación seleccionada", "Elegí una actividad para revisar su estado.");
      }

      function curationHistoryItem(operation) {
        const selected = operation.id === selectedCurationCaseId;
        return `<button class="curation-queue-item history-item ${selected ? "selected" : ""}" type="button"
          data-curation-case="${escapeAttr(operation.id)}" aria-pressed="${selected}">
          <span class="history-operation-mark" aria-hidden="true">${operation.action === "merge" ? "M" : "D"}</span>
          <span class="curation-queue-copy">
            <span class="curation-queue-type">${escapeHtml(curationActionLabel(operation.action))}</span>
            <strong>${escapeHtml(operation.label || "Decisión de curaduría")}</strong>
            <small>${escapeHtml(formatHistoryDate(operation.created_at))}</small>
          </span>
          <span class="pill ${operation.status === "undone" ? "muted" : "good"}">${
            operation.status === "undone" ? "deshecha" : "aplicada"
          }</span>
        </button>`;
      }

      function curationHistoryDetail(operation) {
        const summary = operation.summary || {};
        const changedFields = asList(summary.changed_fields);
        return `<section class="history-detail">
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${escapeHtml(curationActionLabel(operation.action))}</span>
              <h3>${escapeHtml(operation.label || "Decisión de curaduría")}</h3>
            </div>
            <span class="pill ${operation.status === "undone" ? "muted" : "good"}">${
              operation.status === "undone" ? "Deshecha" : "Aplicada"
            }</span>
          </header>
          <dl class="history-facts">
            <div><dt>Fecha</dt><dd>${escapeHtml(formatHistoryDate(operation.created_at))}</dd></div>
            <div><dt>Alcance</dt><dd>${operation.mode === "session" ? "Sólo esta sesión" : "Persistente"}</dd></div>
            ${summary.survivor_title ? `<div><dt>Entrada final</dt><dd>${escapeHtml(summary.survivor_title)}</dd></div>` : ""}
            ${changedFields.length ? `<div><dt>Campos revisados</dt><dd>${changedFields.length}</dd></div>` : ""}
          </dl>
          ${changedFields.length
            ? `<div class="history-field-list">${changedFields.map((field) => `<span>${escapeHtml(mergeFieldLabel(field))}</span>`).join("")}</div>`
            : ""}
          <footer class="curation-actions">
            ${operation.can_undo
              ? `<button class="action-primary" type="button" data-curation-action="undo-operation"
                   data-operation-id="${escapeAttr(operation.id)}">Deshacer operación</button>`
              : `<span class="history-closed-note">Esta operación ya fue deshecha.</span>`}
          </footer>
        </section>`;
      }

      function curationActionLabel(action) {
        return {
          merge: "Combinación",
          link_curation: "Referencia",
          duplicate_curation: "Duplicado"
        }[action] || "Curaduría";
      }

      function formatHistoryDate(value) {
        if (!value) return "Sin fecha";
        const date = new Date(value);
        return Number.isNaN(date.getTime())
          ? String(value)
          : date.toLocaleString("es-AR", { dateStyle: "medium", timeStyle: "short" });
      }

      function curationQueueItem(entry) {
        const item = entry.primary;
        const selected = entry.id === selectedCurationCaseId;
        const type = entry.type === "duplicate" ? "Duplicado" : "Sin link";
        return `<button class="curation-queue-item ${selected ? "selected" : ""}" type="button"
          data-curation-case="${escapeAttr(entry.id)}" aria-pressed="${selected}">
          ${curationThumb(item)}
          <span class="curation-queue-copy">
            <span class="curation-queue-type">${escapeHtml(type)}${entry.status === "deferred" ? " · Pospuesta" : ""}</span>
            <strong>${escapeHtml(item.title || "Sin título")}</strong>
            <small>${escapeHtml([item.year, item.kind].filter(Boolean).join(" · ") || "Sin año")}</small>
          </span>
          <span class="curation-queue-arrow" aria-hidden="true">→</span>
        </button>`;
      }

      function curationCaseDetail(entry) {
        return entry.type === "duplicate"
          ? duplicateCurationDetail(entry)
          : missingLinkCurationDetail(entry);
      }

      function duplicateCurationDetail(entry) {
        const deferred = entry.status === "deferred";
        return `
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${deferred ? "Decisión pospuesta" : "Revisión necesaria"}</span>
              <h3>¿Son la misma obra?</h3>
            </div>
            <span class="pill warning">Posible duplicado</span>
          </header>
          ${curationEvidence(entry.evidence)}
          <div class="curation-pair">
            ${curationRecord(entry.primary, "Entrada A", "open-primary")}
            <div class="curation-pair-mark" aria-hidden="true">↔</div>
            ${curationRecord(entry.secondary, "Entrada B", "open-secondary")}
          </div>
          <footer class="curation-actions">
            ${deferred
              ? `<button class="action-primary" type="button" data-curation-action="compare-duplicate">Comparar y combinar</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-pending">Volver a pendientes</button>`
              : `<button class="action-primary" type="button" data-curation-action="compare-duplicate">Comparar y combinar</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-not-duplicate">No son duplicados</button>
                 <button class="quiet-action" type="button" data-curation-action="duplicate-deferred">Posponer</button>`}
          </footer>
        `;
      }

      function missingLinkCurationDetail(entry) {
        const deferred = entry.status === "deferred";
        return `
          <header class="curation-case-heading">
            <div>
              <span class="curation-case-kicker">${deferred ? "Decisión pospuesta" : "Referencia pendiente"}</span>
              <h3>${escapeHtml(entry.primary.title || "Sin título")}</h3>
            </div>
            <span class="pill muted">Sin link</span>
          </header>
          ${curationEvidence(entry.evidence)}
          <div class="curation-single-record">${curationRecord(entry.primary, "Entrada actual", "open-primary")}</div>
          <footer class="curation-actions">
            ${deferred
              ? `<button class="action-primary" type="button" data-curation-action="link-pending">Volver a pendientes</button>`
              : `<button class="action-primary" type="button" data-curation-action="find-link">Buscar referencia</button>
                 <button class="quiet-action" type="button" data-curation-action="link-not-required">No requiere referencia</button>
                 <button class="quiet-action" type="button" data-curation-action="link-deferred">Posponer</button>`}
          </footer>
        `;
      }

      function curationRecord(item, label, action) {
        if (!item) return "";
        return `<article class="curation-record">
          <span class="curation-record-label">${escapeHtml(label)}</span>
          <div class="curation-record-main">
            ${curationThumb(item, true)}
            <div>
              <h4>${escapeHtml(item.title || "Sin título")}</h4>
              <div class="meta">${meta(item.year)}${meta(item.kind)}${meta(item.source)}</div>
              <div class="card-badges">
                <span class="pill ${item.en_catalogo ? "good" : "muted"}">${item.en_catalogo ? "manual: sí" : "manual: no"}</span>
                <span class="pill ${item.status === "watched" ? "good" : "muted"}">${item.status === "watched" ? "vista" : "pendiente"}</span>
              </div>
            </div>
          </div>
          <button class="text-action curation-open-record" type="button" data-curation-action="${action}">Abrir ficha</button>
        </article>`;
      }

      function curationThumb(item, large = false) {
        const className = large ? "curation-thumb large" : "curation-thumb";
        const title = item?.title || "Sin imagen";
        const fallback = `<span class="${className} curation-thumb-placeholder" aria-hidden="true">${escapeHtml(title.slice(0, 18))}</span>`;
        if (!item?.page_image) return fallback;
        return `<span class="curation-thumb-frame ${large ? "large" : ""}">
          <img class="${className}" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="" loading="lazy" decoding="async">
          ${fallback}
        </span>`;
      }

      function curationEvidence(evidence) {
        return `<div class="curation-evidence">
          <strong>Evidencia</strong>
          <ul>${asList(evidence).map((row) => `<li>${escapeHtml(row)}</li>`).join("")}</ul>
        </div>`;
      }

      function curationEmptyState(title, copy) {
        return `<div class="curation-empty"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(copy)}</p></div>`;
      }

      function openCurationItem(summary) {
        if (!summary?.id) return;
        const contextIds = [...new Set(
          visibleCurationCases()
            .flatMap((entry) => [entry.primary?.id, entry.secondary?.id])
            .filter(Boolean)
        )];
        openDetail(summary.id, {
          context: { mode: "curation", label: "Bandeja", ids: contextIds }
        });
      }

      async function findLinkFromCuration(summary) {
        const item = items.find((entry) => (
          entry.id === summary.id
          && (!summary.source_file || entry._source_file === summary.source_file)
        ));
        if (!item) {
          setCurationFeedback("La entrada ya no está disponible en el catálogo.", "error");
          return;
        }
        await findLinkForItem(item);
      }

      async function updateLinkCuration(entry, status) {
        await postCurationDecision("/api/curation/link", {
          id: entry.primary.id,
          source_file: entry.primary.source_file,
          status
        });
      }

      async function updateDuplicateCuration(entry, status) {
        await postCurationDecision("/api/curation/duplicate", {
          id: entry.primary.id,
          source_file: entry.primary.source_file,
          other_reference: entry.secondary.ref,
          status
        });
      }

      async function postCurationDecision(path, body) {
        fields.curationDetail.querySelectorAll("button").forEach((button) => { button.disabled = true; });
        setCurationFeedback("Guardando decisión…", "working");
        try {
          const response = await apiFetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...body,
              history_mode: curationHistoryMode
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          selectedCurationCaseId = "";
          await loadCatalog();
          setCurationFeedback("Decisión guardada", "success", payload.operation);
        } catch (error) {
          console.error("[catalog-viewer] curation update failed", error);
          setCurationFeedback("No se pudo guardar la decisión. Reintentá sin salir de la Bandeja.", "error");
          renderCuration();
        }
      }

      async function undoCurationOperation(operationId) {
        if (!operationId) return;
        fields.curationDetail.querySelectorAll("button").forEach((button) => { button.disabled = true; });
        setCurationFeedback("Restaurando estado anterior…", "working");
        try {
          const response = await apiFetch("/api/curation/undo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              operation_id: operationId,
              history_mode: curationHistoryMode
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            const reason = payload.reason || `HTTP ${response.status}`;
            if (response.status === 409) {
              throw new Error("La entrada cambió después de esta operación. Revisala antes de restaurar.");
            }
            throw new Error(reason);
          }
          selectedCurationCaseId = operationId;
          await loadCatalog();
          curationFilter = "history";
          renderCuration();
          setCurationFeedback("Operación deshecha. Se restauró el estado anterior.", "success");
        } catch (error) {
          console.error("[catalog-viewer] curation undo failed", error);
          setCurationFeedback(error.message || "No se pudo deshacer la operación.", "error");
          renderCuration();
        }
      }

      function setCurationFeedback(message, tone = "", operation = null) {
        fields.curationFeedback.innerHTML = operation?.can_undo
          ? `<span>${escapeHtml(message)}</span>
             <button class="text-action" type="button" data-curation-action="undo-operation"
               data-operation-id="${escapeAttr(operation.id)}">Deshacer</button>`
          : escapeHtml(message);
        fields.curationFeedback.dataset.tone = tone;
      }

      async function openInternalMergeComparator(entry) {
        if (!entry?.primary || !entry?.secondary) return;
        await openMergeComparator({
          type: "internal",
          left: {
            id: entry.primary.id,
            source_file: entry.primary.source_file
          },
          right: {
            id: entry.secondary.id,
            source_file: entry.secondary.source_file
          }
        });
      }

      async function openExternalMergeComparator(index, targetId) {
        const result = manualResults[index];
        const target = items.find((entry) => entry.id === targetId);
        if (!result || !target) {
          setCurationFeedback("La entrada o el resultado ya no están disponibles.", "error");
          return;
        }
        await openMergeComparator({
          type: "external",
          resultIndex: index,
          left: {
            id: target.id,
            source_file: target._source_file || ""
          },
          result
        });
      }

      async function openMergeComparator(context) {
        mergeContext = context;
        mergeReview = null;
        mergeChoices = {};
        mergeTouchedChoices = new Set();
        mergeSubmitting = false;
        fields.mergeShowAllFields.checked = false;
        fields.mergeComparatorFeedback.textContent = "";
        fields.mergeComparatorFeedback.dataset.tone = "";
        fields.mergeComparatorTitle.textContent = "Preparando comparación";
        fields.mergeComparatorSubtitle.textContent = "Cargando los valores actuales del catálogo.";
        fields.mergeSurvivorControl.hidden = true;
        fields.mergeComparatorSummary.innerHTML = "";
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.confirmReviewedMerge.disabled = true;
        fields.mergeDecisionStatus.textContent = "Leyendo entradas";
        fields.mergeDecisionMeta.textContent = "";
        if (!fields.mergeComparatorDialog.open) fields.mergeComparatorDialog.showModal();
        await requestMergeComparison("left");
      }

      async function requestMergeComparison(survivorSide) {
        if (!mergeContext) return;
        const requestId = ++mergeRequestSequence;
        const requestContext = mergeContext;
        mergeContext.survivor_side = survivorSide;
        fields.mergeComparatorDialog.dataset.loading = "true";
        fields.confirmReviewedMerge.disabled = true;
        fields.mergeComparatorFeedback.textContent = "";
        try {
          const body = {
            left: mergeContext.left,
            survivor_side: survivorSide
          };
          if (mergeContext.type === "internal") body.right = mergeContext.right;
          else body.result = mergeContext.result;
          const response = await apiFetch("/api/curation/compare", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          if (
            !payload
            || !payload.left
            || !payload.right
            || !Array.isArray(payload.fields)
            || !Array.isArray(payload.groups)
          ) {
            throw new Error("invalid_comparison_payload");
          }
          if (requestId !== mergeRequestSequence || mergeContext !== requestContext) return;
          mergeReview = payload;
          if (payload.incoming) mergeContext.incoming = payload.incoming;
          mergeChoices = Object.fromEntries(
            payload.fields
              .filter((field) => field.default_choice)
              .map((field) => [field.key, field.default_choice])
          );
          mergeTouchedChoices = new Set();
          renderMergeComparator();
        } catch (error) {
          if (requestId !== mergeRequestSequence || mergeContext !== requestContext) return;
          console.error("[catalog-viewer] merge comparison failed", error);
          mergeReview = null;
          fields.mergeComparatorTitle.textContent = "No se pudo comparar";
          fields.mergeComparatorSubtitle.textContent = "Las entradas no fueron modificadas.";
          fields.mergeSurvivorControl.hidden = true;
          fields.mergeComparatorSummary.innerHTML = "";
          fields.mergeComparatorFields.innerHTML = `<div class="curation-empty">
            <strong>Comparación no disponible</strong>
            <p>No pudimos leer ambas entradas. Podés reintentar sin cerrar esta mesa.</p>
            <button class="quiet-action merge-error-action" type="button" data-click="retry-merge-comparison">Reintentar comparación</button>
          </div>`;
          fields.mergeComparatorFeedback.textContent = "La comparación se interrumpió. El catálogo permanece intacto.";
          fields.mergeComparatorFeedback.dataset.tone = "error";
          fields.mergeDecisionStatus.textContent = "Comparación interrumpida";
          fields.mergeDecisionMeta.textContent = "";
        } finally {
          if (requestId === mergeRequestSequence) {
            fields.mergeComparatorDialog.dataset.loading = "false";
          }
        }
      }

      function retryMergeComparison() {
        if (!mergeContext || fields.mergeComparatorDialog.dataset.loading === "true") return;
        fields.mergeComparatorTitle.textContent = "Preparando comparación";
        fields.mergeComparatorSubtitle.textContent = "Volviendo a leer los valores actuales del catálogo.";
        fields.mergeSurvivorControl.hidden = true;
        fields.mergeComparatorSummary.innerHTML = "";
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.mergeDecisionStatus.textContent = "Leyendo entradas";
        fields.mergeComparatorFeedback.textContent = "";
        fields.mergeComparatorFeedback.dataset.tone = "";
        requestMergeComparison(mergeContext.survivor_side || "left");
      }

      function renderMergeComparator() {
        if (!mergeReview) return;
        const leftTitle = mergeReview.left?.title || "Entrada A";
        const rightTitle = mergeReview.right?.title || "Entrada B";
        fields.mergeComparatorTitle.textContent = `${leftTitle} / ${rightTitle}`;
        fields.mergeComparatorSubtitle.textContent = mergeReview.can_select_survivor
          ? "Elegí qué identidad permanece y resolvé los campos señalados."
          : "La entrada del catálogo conservará su identidad.";
        fields.mergeSurvivorControl.hidden = !mergeReview.can_select_survivor;
        fields.mergeSurvivorLeft.textContent = `Conservar A · ${leftTitle}`;
        fields.mergeSurvivorRight.textContent = `Conservar B · ${rightTitle}`;
        fields.mergeSurvivorControl.querySelectorAll('input[name="merge-survivor"]').forEach((input) => {
          input.checked = input.value === mergeReview.survivor_side;
        });
        fields.mergeComparatorSummary.innerHTML = `
          ${mergeEntrySummary(mergeReview.left, "Entrada A", mergeReview.survivor_side === "left")}
          <span class="merge-summary-divider" aria-hidden="true">↔</span>
          ${mergeEntrySummary(mergeReview.right, "Entrada B", mergeReview.survivor_side === "right")}
        `;

        const visibleFields = mergeReview.fields.filter((field) => (
          fields.mergeShowAllFields.checked || field.different
        ));
        fields.mergeComparatorFields.innerHTML = mergeReview.groups
          .map((group) => {
            const rows = visibleFields.filter((field) => field.group === group.key);
            if (!rows.length) return "";
            return `<section class="merge-field-group" aria-labelledby="merge-group-${escapeAttr(group.key)}">
              <header>
                <h3 id="merge-group-${escapeAttr(group.key)}">${escapeHtml(group.label)}</h3>
                <span>${rows.length} ${rows.length === 1 ? "campo" : "campos"}</span>
              </header>
              ${rows.map(mergeFieldRow).join("")}
            </section>`;
          })
          .join("") || curationEmptyState("Las entradas coinciden", "No hay diferencias para revisar.");
        updateMergeDecisionStatus();
      }

      function mergeEntrySummary(item, label, survivor) {
        return `<article class="merge-entry-summary ${survivor ? "survivor" : ""}">
          ${curationThumb(item, true)}
          <div>
            <span>${escapeHtml(label)}${survivor ? " · permanece" : ""}</span>
            <strong>${escapeHtml(item.title || "Sin título")}</strong>
            <small>${escapeHtml([item.year, item.kind, item.source].filter(Boolean).join(" · "))}</small>
            <div class="card-badges">
              <span class="pill ${item.en_catalogo ? "good" : "muted"}">${item.en_catalogo ? "manual: sí" : "manual: no"}</span>
              <span class="pill ${item.local_files_count ? "good" : "muted"}">${item.local_files_count || 0} archivos</span>
            </div>
          </div>
        </article>`;
      }

      function mergeFieldRow(field) {
        const choice = mergeChoices[field.key] || "";
        const states = [
          { side: "left", label: "Entrada A", value: field.left },
          ...(field.allowed.includes("combine")
            ? [{ side: "combine", label: mergeCombineLabel(field), value: mergeCombinedValue(field) }]
            : []),
          { side: "right", label: "Entrada B", value: field.right }
        ].filter((state) => field.allowed.includes(state.side));
        const options = field.different
          ? states.map((state) => `
              <label class="merge-choice ${state.side}">
                <input type="radio" name="merge-field-${escapeAttr(field.key)}"
                  data-merge-choice="${escapeAttr(field.key)}" value="${state.side}"
                  ${choice === state.side ? "checked" : ""}>
                <span class="merge-choice-label">${escapeHtml(state.label)}</span>
                ${mergeValue(state.value, field)}
              </label>
            `).join("")
          : `<div class="merge-field-same">${mergeValue(field.left, field)}<span>Coinciden</span></div>`;
        return `<article class="merge-field-row ${field.required && !choice ? "needs-decision" : ""}"
          data-merge-field="${escapeAttr(field.key)}">
          <header>
            <strong>${escapeHtml(field.label)}</strong>
            <span class="merge-field-signals">
              ${field.protected ? '<span class="pill warning">protegido</span>' : ""}
              ${field.locked ? '<span class="pill muted">bloqueado</span>' : ""}
              ${field.required && !choice ? '<span class="pill warning">elegir</span>' : ""}
            </span>
          </header>
          <div class="merge-field-options ${states.length === 3 ? "three" : "two"}">${options}</div>
        </article>`;
      }

      function mergeValue(value, field) {
        if (field.strategy === "local_files") {
          const files = Array.isArray(value) ? value : [];
          if (!files.length) return '<span class="merge-value empty">Sin archivos</span>';
          return `<span class="merge-value merge-file-list">${files.map((file) => `
            <span><strong>${escapeHtml(file.name || "Archivo")}</strong><small>${escapeHtml(file.path || file.relative_path || "")}</small></span>
          `).join("")}</span>`;
        }
        if (field.strategy === "list") {
          const values = asList(value);
          return values.length
            ? `<span class="merge-value merge-list-value">${values.map((entry) => `<span>${escapeHtml(entry)}</span>`).join("")}</span>`
            : '<span class="merge-value empty">Sin datos</span>';
        }
        if (field.strategy === "release_dates") {
          const dates = Array.isArray(value) ? value : [];
          return dates.length
            ? `<span class="merge-value merge-list-value">${dates.map((entry) => `<span>${escapeHtml(releaseDateLabel(entry))}</span>`).join("")}</span>`
            : '<span class="merge-value empty">Sin fechas</span>';
        }
        if (field.strategy === "boolean_or") {
          return `<span class="merge-value">${value ? "Sí" : "No"}</span>`;
        }
        if (["page_image", "backdrop_image"].includes(field.key) && value) {
          return `<span class="merge-value merge-image-value">
            <img src="${escapeAttr(cachedImageSrc(String(value)))}" alt="" loading="lazy">
            <small>${escapeHtml(urlHost(value))}</small>
          </span>`;
        }
        const text = String(value ?? "").trim();
        return `<span class="merge-value ${text ? "" : "empty"}">${escapeHtml(text || "Sin datos")}</span>`;
      }

      function mergeCombinedValue(field) {
        if (field.strategy === "list") {
          const seen = new Set();
          return [...asList(field.left), ...asList(field.right)].filter((value) => {
            const key = normalizeText(value);
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        }
        if (field.strategy === "local_files") {
          const seen = new Set();
          return [...asList(field.left), ...asList(field.right)].filter((file) => {
            const key = `${file.library_id || ""}|${file.relative_path || ""}|${file.path || ""}`.toLowerCase();
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        }
        if (field.strategy === "release_dates") {
          const seen = new Set();
          return [...asList(field.left), ...asList(field.right)].filter((entry) => {
            const key = `${entry?.date || ""}|${entry?.country || ""}|${entry?.release_type || ""}`.toLowerCase();
            if (!entry?.date || seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        }
        if (field.strategy === "boolean_or") return Boolean(field.left || field.right);
        return field.left;
      }

      function mergeCombineLabel(field) {
        if (field.strategy === "boolean_or") return "Preservar sí";
        if (field.strategy === "local_files") return "Conservar todos";
        if (field.strategy === "release_dates") return "Conservar fechas";
        return "Combinar";
      }

      function changeMergeChoice(event) {
        const input = event.target.closest("[data-merge-choice]");
        if (!input || !mergeReview) return;
        mergeChoices[input.dataset.mergeChoice] = input.value;
        mergeTouchedChoices.add(input.dataset.mergeChoice);
        const row = fields.mergeComparatorFields.querySelector(
          `[data-merge-field="${CSS.escape(input.dataset.mergeChoice)}"]`
        );
        if (row) {
          row.classList.remove("needs-decision");
          row.querySelectorAll(".merge-field-signals .warning").forEach((badge) => {
            if (badge.textContent.trim() === "elegir") badge.remove();
          });
        }
        updateMergeDecisionStatus();
      }

      async function changeMergeSurvivor(event) {
        const input = event.target.closest('input[name="merge-survivor"]');
        if (!input || !mergeReview || input.value === mergeReview.survivor_side) return;
        fields.mergeComparatorFields.innerHTML = mergeComparatorLoading();
        fields.mergeDecisionStatus.textContent = "Recalculando resultado";
        await requestMergeComparison(input.value);
      }

      function updateMergeDecisionStatus() {
        if (!mergeReview) return;
        const unresolved = mergeReview.fields.filter((field) => (
          field.different
          && field.required
          && !field.allowed.includes(mergeChoices[field.key])
        ));
        const different = mergeReview.different_count || 0;
        fields.mergeDecisionStatus.textContent = unresolved.length
          ? `${unresolved.length} ${unresolved.length === 1 ? "decisión pendiente" : "decisiones pendientes"}`
          : "Resultado listo para combinar";
        fields.mergeDecisionMeta.textContent = `${different} ${different === 1 ? "diferencia" : "diferencias"} revisadas`;
        fields.confirmReviewedMerge.disabled = mergeSubmitting || unresolved.length > 0;
      }

      async function submitReviewedMerge() {
        if (!mergeReview || !mergeContext || mergeSubmitting) return;
        mergeSubmitting = true;
        updateMergeDecisionStatus();
        fields.mergeComparatorFeedback.textContent = "Guardando combinación…";
        fields.mergeComparatorFeedback.dataset.tone = "working";
        try {
          const body = {
            left: mergeContext.left,
            survivor_side: mergeReview.survivor_side,
            choices: mergeChoices,
            review_id: mergeReview.review_id,
            history_mode: curationHistoryMode
          };
          if (mergeContext.type === "internal") {
            body.right = mergeContext.right;
          } else {
            body.incoming = mergeContext.incoming || mergeContext.result;
            body.incoming_reviewed = true;
          }
          const response = await apiFetch("/api/curation/merge", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            if (response.status === 409) throw new Error("Las entradas cambiaron. Cerrá y volvé a comparar.");
            throw new Error(payload.reason || `HTTP ${response.status}`);
          }
          const externalMerge = mergeContext.type === "external";
          closeMergeComparator(true);
          selectedCurationCaseId = "";
          await loadCatalog();
          setCurationFeedback("Entradas combinadas", "success", payload.operation);
          if (externalMerge) {
            selectedExistingIdForSearch = null;
            fields.manualSearchStatus.textContent = "Combinación guardada. Deshacer está disponible en Bandeja > Actividad.";
            renderManualResults();
            renderCatalogMergeResults();
          }
        } catch (error) {
          console.error("[catalog-viewer] reviewed merge failed", error);
          fields.mergeComparatorFeedback.textContent = error.message || "No se pudo combinar.";
          fields.mergeComparatorFeedback.dataset.tone = "error";
        } finally {
          mergeSubmitting = false;
          updateMergeDecisionStatus();
        }
      }

      function closeMergeComparator(force = false) {
        if (mergeSubmitting && !force) return;
        mergeRequestSequence += 1;
        if (fields.mergeComparatorDialog.open) fields.mergeComparatorDialog.close();
        mergeReview = null;
        mergeContext = null;
        mergeChoices = {};
        mergeTouchedChoices = new Set();
        fields.mergeComparatorFeedback.textContent = "";
      }

      function mergeComparatorLoading() {
        return `<div class="merge-loading" aria-label="Cargando comparación">
          <span></span><span></span><span></span>
        </div>`;
      }

      function urlHost(value) {
        try {
          return new URL(String(value)).hostname.replace(/^www\./, "");
        } catch (_) {
          return String(value || "");
        }
      }

      function mergeFieldLabel(key) {
        return {
          title: "Título principal",
          original_title: "Título original",
          spanish_title: "Título en español",
          english_title: "Título en inglés",
          alternative_titles: "Títulos alternativos",
          kind: "Tipo de obra",
          year: "Año",
          release_dates: "Fechas de estreno",
          description: "Descripción",
          wikipedia_extract: "Extracto de Wikipedia",
          genres: "Géneros",
          directors: "Dirección",
          writers: "Guion",
          cast: "Reparto",
          page_image: "Portada",
          backdrop_image: "Imagen panorámica",
          source: "Fuente principal",
          url: "URL principal",
          wikipedia_url: "Wikipedia",
          imdb_url: "IMDb",
          filmaffinity_url: "FilmAffinity",
          wikipedia_title: "Título de Wikipedia",
          wikidata_id: "Wikidata",
          tmdb_id: "TMDB",
          status: "Estado personal",
          watched_at: "Fecha de vista",
          rating: "Puntaje",
          review: "Review",
          notes: "Notas",
          tags: "Etiquetas",
          en_catalogo: "Disponibilidad manual",
          local_files: "Archivos locales"
        }[key] || key;
      }

      function openRandomDetail() {
        const candidates = randomCandidates();
        if (!candidates.length) return;
        const pool = candidates.length > 1 && selectedDetailId
          ? candidates.filter((item) => item.id !== selectedDetailId)
          : candidates;
        const item = pool[Math.floor(Math.random() * pool.length)];
        if (item) {
          openDetail(item.id, {
            context: {
              mode: "random",
              label: fields.randomCatalogOnly.checked ? "Al azar · Disponibles" : "Al azar · Todo",
              ids: candidates.map((candidate) => candidate.id)
            }
          });
        }
      }

      function randomCandidates() {
        const filtered = currentView === "catalog" ? filteredItems() : [];
        const candidates = filtered.length ? filtered : items;
        return fields.randomCatalogOnly.checked
          ? candidates.filter((item) => isInCatalog(item.en_catalogo))
          : candidates;
      }

      function syncRandomControl() {
        const count = randomCandidates().length;
        const catalogOnly = fields.randomCatalogOnly.checked;
        fields.randomScopeLabel.textContent = catalogOnly ? "Disponibles" : "Todo";
        fields.randomButton.disabled = count === 0;
        fields.randomButton.title = count
          ? `Abrir una ficha al azar entre ${count} ${catalogOnly ? "obras disponibles" : "obras"}`
          : catalogOnly ? "No hay obras disponibles con los filtros actuales" : "No hay obras para elegir";
      }

      function changeRandomScope(source) {
        const catalogOnly = Boolean(source.checked);
        fields.randomCatalogOnly.checked = catalogOnly;
        syncRandomControl();
      }

      function catalogDetailItems() {
        return applyRandomOrder(sortItems(filteredItems()));
      }

      function detailContextForTrigger(target) {
        if (target.closest("#homeView")) {
          return {
            mode: "home",
            label: "Inicio",
            ids: editorialPersonalIds()
          };
        }
        if (target.closest("#catalogMergeResults")) {
          return {
            mode: "search",
            label: "Resultados locales",
            ids: catalogMergeResults.map((item) => item.id)
          };
        }
        return {
          mode: "catalog",
          label: activeQuery ? `Colección · ${activeQuery}` : "Colección",
          ids: catalogDetailItems().map((item) => item.id)
        };
      }

      function openDetailFromTrigger(target, id) {
        openDetail(id, { context: detailContextForTrigger(target) });
      }

      function syncRoute(values = {}, method = "replace") {
        const url = new URL(window.location.href);
        for (const [key, value] of Object.entries(values)) {
          url.searchParams.delete(key);
          if (Array.isArray(value)) {
            value.filter(Boolean).forEach((entry) => url.searchParams.append(key, entry));
          } else if (value) {
            url.searchParams.set(key, value);
          }
        }
        if (Object.prototype.hasOwnProperty.call(values, "view")) url.hash = "";
        history[method === "push" ? "pushState" : "replaceState"]({}, "", url);
      }

      function collectionRouteValues() {
        const values = {
          q: activeQuery,
          year_from: collectionYearRange.from,
          year_to: collectionYearRange.to,
          sort: fields.sort.value && fields.sort.value !== "original" ? fields.sort.value : "",
          duplicates: duplicatesOnly ? "1" : "",
          external: activeQuery && fields.externalSource.checked ? "1" : ""
        };
        for (const key of COLLECTION_MULTI_FILTER_KEYS) {
          values[key] = [...collectionFilters[key]].sort((left, right) => left.localeCompare(right, "es"));
        }
        return values;
      }

      function routeValuesForView(view) {
        const values = { view, movie: "" };
        for (const key of COLLECTION_ROUTE_KEYS) values[key] = "";
        if (view === "catalog") Object.assign(values, collectionRouteValues());
        return values;
      }

      function syncCollectionRoute(method = "replace") {
        syncRoute(routeValuesForView("catalog"), method);
      }

      function applyCollectionRoute(params) {
        collectionFilters = emptyCollectionFilters();
        for (const key of COLLECTION_MULTI_FILTER_KEYS) {
          for (const value of params.getAll(key).map((entry) => entry.trim()).filter(Boolean)) {
            collectionFilters[key].add(value);
          }
        }
        collectionYearRange = {
          from: validCollectionYear(params.get("year_from")),
          to: validCollectionYear(params.get("year_to"))
        };
        const requestedSort = params.get("sort") || "original";
        fields.sort.value = [...fields.sort.options].some((option) => option.value === requestedSort)
          ? requestedSort
          : "original";
        duplicatesOnly = params.get("duplicates") === "1";
        fields.externalSource.checked = params.get("external") === "1";
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        syncCollectionFilterControls();
      }

      function restoreRoute() {
        if (!items.length) return;
        const params = new URLSearchParams(window.location.search);
        const rawQuery = params.get("q") || "";
        const movieId = params.get("movie") || "";
        const hasCollectionRoute = COLLECTION_ROUTE_KEYS.some((key) => params.has(key));
        const requestedView = ["home", "catalog", "inbox", "club", "admin"].includes(params.get("view"))
          ? params.get("view")
          : hasCollectionRoute ? "catalog" : "home";
        const query = requestedView === "catalog" ? rawQuery : "";
        if (requestedView === "catalog") {
          selectedManualIndex = null;
          selectedExistingIdForSearch = null;
          catalogMergeResults = [];
          fields.catalogMergeResults.innerHTML = "";
          fields.catalogMergeSection.classList.remove("active");
          fields.reviewPrevious.hidden = true;
          fields.reviewNext.hidden = true;
          setCollectionSearchMode("browse");
          applyCollectionRoute(params);
          if (!fields.externalSource.checked) {
            manualResults = [];
            fields.manualSearchResults.innerHTML = "";
            fields.externalSearchSection.classList.remove("active");
          } else if (manualResults.length) {
            renderManualResults();
          }
        }
        if (query.length >= 2 && query !== activeQuery) {
          fields.query.value = query;
          runSearch({ updateHistory: false });
        } else if (!query && activeQuery) {
          clearManualSearch({ focus: false, updateHistory: false, resetExternal: requestedView !== "catalog" });
        } else {
          render();
          setSearchState(query.length >= 2 ? "results" : "idle", query.length >= 2 ? collectionSearchMessage() : "");
        }
        if (movieId && items.some((item) => item.id === movieId) && movieId !== selectedDetailId) {
          openDetail(movieId, { updateHistory: false });
        } else if (!movieId && selectedDetailId) {
          closeDetail({ restoreFocus: false, updateHistory: false });
        }
        showView(requestedView, { updateHistory: false, scroll: false });
        if (requestedView === "inbox") loadCurrentInbox();
        if (requestedView === "club") loadClub();
        if (requestedView === "admin") loadMembers();
      }

      function normalizeEditorialHome(payload) {
        if (!payload || typeof payload !== "object") {
          return {
            generated_for: todayLocalDate(),
            featured: [],
            hero: null,
            sections: [],
            warnings: [],
            featured_source: ""
          };
        }
        const featured = Array.isArray(payload.featured)
          ? payload.featured.filter((entry) => entry && typeof entry === "object").slice(0, 4)
          : payload.hero && typeof payload.hero === "object" ? [payload.hero] : [];
        return {
          generated_for: String(payload.generated_for || todayLocalDate()),
          featured,
          hero: featured[0] || null,
          sections: Array.isArray(payload.sections) ? payload.sections : [],
          warnings: Array.isArray(payload.warnings) ? payload.warnings : [],
          featured_source: String(payload.featured_source || "")
        };
      }

      function renderEditorialHome() {
        renderEditorialHero();
        renderEditorialSections();
        const hasSections = editorialHome.sections.some((section) => section.items?.length);
        fields.homeEmpty.hidden = Boolean(editorialHome.featured.length || hasSections);
        fields.homeSections.hidden = !hasSections;
        fields.homeDate.dateTime = editorialHome.generated_for || "";
        fields.homeDate.textContent = homeDateLabel(editorialHome.generated_for);
        syncHomeDateControl();
        const collectionsUnavailable = editorialHome.warnings.includes("collections_unavailable");
        const historyUnavailable = editorialHome.warnings.includes("home_history_unavailable");
        fields.homeFeedback.hidden = !(collectionsUnavailable || historyUnavailable);
        fields.homeFeedback.innerHTML = collectionsUnavailable
          ? `Las colecciones seguidas no respondieron. Tu programación personal sigue disponible. <button type="button" data-click="refresh-home">Reintentar</button>`
          : historyUnavailable
            ? `No pudimos guardar el historial de la cartelera. Las recomendaciones de hoy siguen disponibles. <button type="button" data-click="refresh-home">Reintentar</button>`
            : "";
      }

      function renderEditorialHero() {
        const featured = editorialHome.featured;
        if (spotlightIndex >= featured.length) spotlightIndex = 0;
        const entry = featured[spotlightIndex];
        const item = entry?.item;
        if (!item) {
          fields.spotlightStage.innerHTML = `<div class="spotlight-empty">
            <strong>La pantalla espera una obra disponible</strong>
            <span>Vinculá un archivo o declará una obra disponible para encabezar la cartelera del día.</span>
          </div>`;
          return;
        }
        const title = displayTitle(item) || "Sin título";
        const reason = entry.reason || {};
        const summary = String(item.description || item.wikipedia_extract || reason.detail || "").trim();
        const metadata = [item.year, firstListValue(item.genres), firstListValue(item.directors)].filter(Boolean);
        const realBackdrop = String(item.backdrop_image || "").trim();
        const poster = String(item.page_image || "").trim();
        const imageUrl = realBackdrop || poster;
        const image = imageUrl
          ? `<img class="spotlight-image ${realBackdrop ? "is-backdrop" : "is-poster-fallback"}" data-spotlight-image src="${escapeAttr(cachedImageSrc(imageUrl))}" alt="" loading="eager" fetchpriority="high" decoding="async">`
          : "";
        const cover = !realBackdrop && poster
          ? `<img class="spotlight-poster" data-spotlight-image src="${escapeAttr(cachedImageSrc(poster))}" alt="Portada de ${escapeAttr(title)}" loading="eager" fetchpriority="high" decoding="async">`
          : "";
        const navigation = featured.length > 1
          ? `<div class="spotlight-navigation" aria-label="Navegar recomendaciones">
              <button class="spotlight-step" type="button" data-click="spotlight-previous" aria-label="Recomendación anterior">&#8249;</button>
              <span>${spotlightIndex + 1} / ${featured.length}</span>
              <button class="spotlight-step" type="button" data-click="spotlight-next" aria-label="Recomendación siguiente">&#8250;</button>
            </div>`
          : "";
        const program = featured.length > 1
          ? `<div class="spotlight-program" aria-label="Recomendaciones del día">
              ${featured.map((candidate, index) => {
                const candidateTitle = displayTitle(candidate.item || {}) || `Recomendación ${index + 1}`;
                return `<button type="button" aria-pressed="${index === spotlightIndex ? "true" : "false"}" data-click="spotlight-select" data-index="${index}">
                  <span>${String(index + 1).padStart(2, "0")}</span>
                  <strong>${escapeHtml(candidateTitle)}</strong>
                </button>`;
              }).join("")}
            </div>`
          : "";
        fields.spotlightStage.innerHTML = `<div class="spotlight-viewport">
          <article class="spotlight-slide poster-${posterVariant(item.id || title)}">
            ${image}${cover}
            <div class="spotlight-copy">
              <span class="spotlight-reason">${escapeHtml(reason.label || "Selección del día")}</span>
              <strong>${escapeHtml(title)}</strong>
              ${metadata.length ? `<span class="spotlight-metadata">${metadata.map(escapeHtml).join(" · ")}</span>` : ""}
              <p>${escapeHtml(summary || "Una obra disponible de tu archivo personal para considerar esta noche.")}</p>
              <button class="spotlight-cta" type="button" data-click="open-detail" data-id="${escapeAttr(item.id)}">Ver ficha</button>
            </div>
          </article>
          ${navigation}
        </div>${program}`;
      }

      function selectSpotlight(index, restoreFocus = false) {
        if (!editorialHome.featured.length) return;
        spotlightIndex = Math.max(0, Math.min(editorialHome.featured.length - 1, index));
        renderEditorialHero();
        if (restoreFocus && document.body.dataset.inputMethod === "keyboard") {
          fields.spotlightStage.querySelector(`[data-click="spotlight-select"][data-index="${spotlightIndex}"]`)?.focus();
        }
      }

      function moveSpotlight(offset, action = "") {
        const count = editorialHome.featured.length;
        if (count < 2) return;
        spotlightIndex = (spotlightIndex + offset + count) % count;
        renderEditorialHero();
        if (action && document.body.dataset.inputMethod === "keyboard") {
          fields.spotlightStage.querySelector(`[data-click="${action}"]`)?.focus();
        }
      }

      function renderEditorialSections() {
        fields.homeSections.innerHTML = editorialHome.sections
          .filter((section) => Array.isArray(section.items) && section.items.length)
          .map((section, sectionIndex) => editorialSection(section, sectionIndex))
          .join("");
      }

      function editorialSection(section, sectionIndex) {
        const action = section.action || {};
        const actionButton = action.kind
          ? `<button class="quiet-action home-section-action" type="button" data-click="home-section-action" data-section-id="${escapeAttr(section.id || "")}">${escapeHtml(action.label || "Explorar")}</button>`
          : "";
        return `<section class="home-program" data-home-section="${escapeAttr(section.id || "editorial")}" aria-labelledby="home-section-${escapeAttr(section.id || sectionIndex)}">
          <header class="home-program-heading">
            <div>
              <span class="section-kicker">${escapeHtml(section.eyebrow || "Programación personal")}</span>
              <h2 id="home-section-${escapeAttr(section.id || sectionIndex)}">${escapeHtml(section.title || "Selección")}</h2>
              <p>${escapeHtml(section.description || "")}</p>
            </div>
            ${actionButton}
          </header>
          <div class="home-program-grid">
            ${section.items.map((entry, index) => editorialEntry(entry, index, sectionIndex === 0)).join("")}
          </div>
        </section>`;
      }

      function editorialEntry(entry, index, prioritize) {
        const item = entry?.item || {};
        const origin = entry?.origin || {};
        const options = origin.kind === "collection"
          ? {
              action: "open-home-collection-detail",
              actionId: origin.collection_item_id || item.id || "",
              entryKey: entry.key || "",
              collectionTitle: origin.collection_title || "Colección"
            }
          : {};
        return `<div class="home-editorial-item">${card(item, index, prioritize, options)}</div>`;
      }

      function editorialPersonalIds() {
        const ids = [];
        for (const entry of editorialHome.featured) {
          if (entry.origin?.kind === "catalog" && entry.item?.id) ids.push(entry.item.id);
        }
        for (const section of editorialHome.sections) {
          for (const entry of section.items || []) {
            if (entry.origin?.kind === "catalog" && entry.item?.id) ids.push(entry.item.id);
          }
        }
        return [...new Set(ids)];
      }

      function homeDateLabel(value) {
        const parsed = new Date(`${value || todayLocalDate()}T12:00:00`);
        if (Number.isNaN(parsed.getTime())) return "Hoy";
        const label = new Intl.DateTimeFormat("es-AR", {
          weekday: "long",
          day: "numeric",
          month: "long"
        }).format(parsed);
        const prefix = value === localDateOffset(-1)
          ? "Ayer"
          : value === todayLocalDate() ? "Hoy" : "Archivo";
        return `${prefix} · ${label}`;
      }

      function rememberEditorialFeatured(payload) {
        const date = String(payload?.generated_for || "");
        if (!date) return;
        editorialFeaturedCache.set(date, {
          featured: Array.isArray(payload.featured) ? payload.featured : [],
          featured_source: String(payload.featured_source || "")
        });
      }

      function syncHomeDateControl() {
        const selected = editorialHome.generated_for || todayLocalDate();
        fields.homeDateToday.setAttribute("aria-pressed", String(selected === todayLocalDate()));
        fields.homeDateYesterday.setAttribute("aria-pressed", String(selected === localDateOffset(-1)));
      }

      function applyEditorialFeaturedDate(localDate, snapshot) {
        const featured = Array.isArray(snapshot.featured) ? snapshot.featured : [];
        editorialHome = {
          ...editorialHome,
          generated_for: localDate,
          featured,
          hero: featured[0] || null,
          featured_source: String(snapshot.featured_source || "")
        };
        spotlightIndex = 0;
        renderEditorialHero();
        fields.homeDate.dateTime = localDate;
        fields.homeDate.textContent = homeDateLabel(localDate);
        syncHomeDateControl();
      }

      async function loadEditorialFeaturedDate(localDate, options = {}) {
        const requestedDate = String(localDate || "");
        if (!requestedDate || (requestedDate === editorialHome.generated_for && !options.force)) return;
        const cached = !options.force ? editorialFeaturedCache.get(requestedDate) : null;
        if (cached) {
          applyEditorialFeaturedDate(requestedDate, cached);
          return;
        }
        const isYesterday = requestedDate === localDateOffset(-1);
        fields.homeDateToday.disabled = true;
        fields.homeDateYesterday.disabled = true;
        fields.spotlight.setAttribute("aria-busy", "true");
        fields.homeFeedback.hidden = false;
        fields.homeFeedback.textContent = isYesterday
          ? "Recuperando las recomendaciones guardadas de ayer…"
          : "Actualizando las recomendaciones de hoy…";
        try {
          const snapshotQuery = isYesterday ? "&saved_featured=true" : "";
          const response = await apiFetch(`/api/home?date=${encodeURIComponent(requestedDate)}${snapshotQuery}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          const normalized = normalizeEditorialHome(payload);
          rememberEditorialFeatured(normalized);
          applyEditorialFeaturedDate(requestedDate, normalized);
          fields.homeFeedback.hidden = true;
          fields.homeFeedback.textContent = "";
        } catch (error) {
          const retryAction = isYesterday ? "home-date-yesterday" : "home-date-today";
          fields.homeFeedback.hidden = false;
          fields.homeFeedback.innerHTML = `No pudimos recuperar esas recomendaciones. <button type="button" data-click="${retryAction}">Reintentar</button>`;
        } finally {
          fields.homeDateToday.disabled = false;
          fields.homeDateYesterday.disabled = false;
          fields.spotlight.setAttribute("aria-busy", "false");
        }
      }

      async function refreshEditorialHome() {
        const requestedDate = editorialHome.generated_for || todayLocalDate();
        if (requestedDate !== todayLocalDate()) {
          editorialFeaturedCache.delete(requestedDate);
          await loadEditorialFeaturedDate(requestedDate, { force: true });
          return;
        }
        fields.homeView.setAttribute("aria-busy", "true");
        fields.homeFeedback.hidden = false;
        fields.homeFeedback.textContent = "Actualizando la programación…";
        try {
          const response = await apiFetch(`/api/home?date=${encodeURIComponent(todayLocalDate())}`);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          editorialHome = normalizeEditorialHome(payload);
          rememberEditorialFeatured(editorialHome);
          editorialRevision += 1;
          renderEditorialHome();
          lastEditorialRenderRevision = editorialRevision;
        } catch (error) {
          fields.homeFeedback.hidden = false;
          fields.homeFeedback.innerHTML = `No pudimos actualizar la programación. <button type="button" data-click="refresh-home">Reintentar</button>`;
        } finally {
          fields.homeView.setAttribute("aria-busy", "false");
        }
      }

      function handleVisibilityChange() {
        syncImageCacheStatusPolling();
      }

      function setupCollectionFilterOptions() {
        const statuses = uniqueFilterValues(items.map((item) => item.status));
        const kinds = uniqueFilterValues(items.map((item) => item.kind));
        renderQuickFilterGroup(fields.statusQuickFilters, "status", statuses);
        renderQuickFilterGroup(fields.availabilityQuickFilters, "availability", ["available", "unavailable"]);
        renderQuickFilterGroup(fields.kindQuickFilters, "kind", kinds);

        const decades = uniqueFilterValues(
          items.map((item) => numericYear(item.year)).filter(Boolean).map((year) => String(Math.floor(year / 10) * 10)),
          { numeric: true }
        );
        setupFilterAddSelect(fields.decadeFilter, "Agregar década", decades, (value) => `Años ${value}`);
        setupFilterAddSelect(
          fields.genreFilter,
          "Agregar género",
          items.flatMap((item) => asList(item.genres))
        );
        setupFilterAddSelect(
          fields.directorFilter,
          "Agregar dirección",
          items.flatMap((item) => asList(item.directors))
        );
        setupFilterAddSelect(fields.sourceFilter, "Agregar fuente", items.map((item) => item.source), (value) => (
          filterValueLabel("Fuente", value)
        ));
        syncCollectionFilterControls();
      }

      function uniqueFilterValues(values, options = {}) {
        const byKey = new Map();
        for (const rawValue of values) {
          const value = String(rawValue || "").trim();
          const key = normalizeText(value);
          if (value && key && !byKey.has(key)) byKey.set(key, value);
        }
        const collator = new Intl.Collator("es", { sensitivity: "base", numeric: Boolean(options.numeric) });
        return [...byKey.values()].sort(collator.compare);
      }

      function setupFilterAddSelect(select, placeholder, values, label = (value) => value) {
        const unique = uniqueFilterValues(values, { numeric: select === fields.decadeFilter });
        select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>` + unique.map((value) => (
          `<option value="${escapeAttr(value)}">${escapeHtml(label(value))}</option>`
        )).join("");
        select.value = "";
      }

      function renderQuickFilterGroup(container, filter, values) {
        container.innerHTML = values.map((value) => (
          `<button type="button" data-click="toggle-collection-filter" data-filter="${escapeAttr(filter)}" data-value="${escapeAttr(value)}" aria-pressed="false">${escapeHtml(filterValueLabel(filter, value))}</button>`
        )).join("");
      }

      function filterValueLabel(label, value) {
        const normalized = String(value || "").toLowerCase();
        const labels = {
          watched: "Vista",
          to_watch: "Por ver",
          available: "Disponible",
          unavailable: "Sin disponibilidad",
          unrated: "Sin puntaje",
          unreviewed: "Sin review",
          pelicula: "Película",
          serie: "Serie",
          anime: "Anime",
          documental: "Documental",
          local_files: "Archivos locales",
          wikipedia: "Wikipedia",
          imdb: "IMDb",
          filmaffinity: "FilmAffinity"
        };
        return labels[normalized] || String(value || label);
      }

      function renderDatabaseMenu() {
        const sourceList = sourceFiles.length
          ? sourceFiles.map((file) => {
              const storage = /\.(db|sqlite|sqlite3)$/i.test(file) ? "SQLite" : "JSON";
              return `<div class="db-item"><strong>${storage}</strong><span>${escapeHtml(file)}</span></div>`;
            }).join("")
          : `<div class="db-item"><strong>Catalogo</strong><span>Sin archivo resuelto.</span></div>`;
        fields.databaseCatalogPanel.innerHTML = `
          <label>
            Catalogo editable
            <input type="text" readonly value="${escapeAttr(writeJsonPath || "-")}">
          </label>
          <div class="db-list">${sourceList}</div>
        `;
        fields.databaseExternalPanel.innerHTML = `
          <div class="db-list">
            ${externalDatabaseItem("Wikipedia", "wikipedia")}
            ${externalDatabaseItem("IMDb", "imdb")}
            ${externalDatabaseItem("FilmAffinity", "filmaffinity")}
            ${externalCacheItem()}
          </div>
        `;
      }

      async function loadImageCacheStatus({ announce = false } = {}) {
        if (
          !fields.imageCacheStatus
          || currentIdentity?.user?.role !== "owner"
          || imageCacheStatusLoading
        ) return;
        imageCacheStatusLoading = true;
        if (announce) fields.imageCacheStatus.setAttribute("aria-busy", "true");
        try {
          const response = await apiFetch("/api/image-cache/status");
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          imageCacheStatus = payload;
          renderImageCacheStatus();
        } catch (error) {
          console.error("[catalog-viewer] image cache status failed", error);
          fields.imageCacheStatus.innerHTML = `
            <div class="image-cache-status-copy">
              <strong>Portadas en este cat&aacute;logo</strong>
              <span>No pudimos consultar el cach&eacute;. Volveremos a intentarlo mientras Administrar siga abierto.</span>
            </div>
            <span class="image-cache-state is-error">Sin conexi&oacute;n</span>
          `;
          fields.imageCacheStatus.dataset.state = "error";
        } finally {
          imageCacheStatusLoading = false;
          fields.imageCacheStatus.removeAttribute("aria-busy");
        }
      }

      function renderImageCacheStatus() {
        if (!fields.imageCacheStatus || !imageCacheStatus) return;
        const personal = imageCacheStatus.personal || {};
        const cache = imageCacheStatus.cache || {};
        const global = imageCacheStatus.global || null;
        const labels = {
          inactive: ["Esperando", "Abr&iacute; un cat&aacute;logo o colecci&oacute;n para iniciar la carga gradual."],
          working: ["Cargando", "Las portadas se guardan de a una, sin bloquear la navegaci&oacute;n."],
          retrying: ["Reintentando", "Algunas fuentes est&aacute;n demoradas; el proceso continuar&aacute; en segundo plano."],
          complete: ["Al d&iacute;a", "Las portadas disponibles de este cat&aacute;logo ya est&aacute;n guardadas."],
          error: ["Con pendientes", "Algunas portadas agotaron sus reintentos o fueron bloqueadas por seguridad."],
          limit_reached: ["L&iacute;mite alcanzado", "El cach&eacute; aplicar&aacute; su limpieza por uso antes de incorporar nuevas portadas."],
          disabled: ["Deshabilitado", "La carga progresiva est&aacute; desactivada en la configuraci&oacute;n del servidor."],
          idle: ["En espera", "Hay portadas pendientes y el worker continuar&aacute; cuando pueda."]
        };
        let [stateLabel, stateCopy] = labels[personal.state] || labels.idle;
        if (imageCacheStatus.worker?.cache_error) {
          stateLabel = "No disponible";
          stateCopy = "El servidor no puede leer el directorio persistente de portadas.";
        }
        const cacheLimit = Number(cache.max_bytes || 0);
        const cacheUsage = cacheLimit
          ? `${formatImportBytes(cache.total_bytes)} de ${formatImportBytes(cacheLimit)}`
          : formatImportBytes(cache.total_bytes);
        const aggregate = global
          ? `<span>${escapeHtml(String(global.available || 0))} recursos disponibles en ${escapeHtml(String(global.registered_scopes || 0))} espacios abiertos</span>`
          : "";
        fields.imageCacheStatus.dataset.state = personal.state || "idle";
        fields.imageCacheStatus.innerHTML = `
          <div class="image-cache-status-copy">
            <strong>Portadas en este cat&aacute;logo</strong>
            <span>${stateCopy}</span>
          </div>
          <div class="image-cache-status-metrics" aria-label="Estado de portadas">
            <span><strong>${escapeHtml(String(personal.available || 0))}</strong> disponibles</span>
            <span><strong>${escapeHtml(String(personal.pending || 0))}</strong> pendientes</span>
            <span><strong>${escapeHtml(String(personal.without_url || 0))}</strong> sin imagen</span>
            ${personal.failed ? `<span><strong>${escapeHtml(String(personal.failed))}</strong> con error</span>` : ""}
            ${personal.rejected ? `<span><strong>${escapeHtml(String(personal.rejected))}</strong> bloqueadas</span>` : ""}
          </div>
          <div class="image-cache-status-meta">
            <span>${escapeHtml(String(cache.files || 0))} archivos &middot; ${escapeHtml(cacheUsage)}</span>
            ${aggregate}
          </div>
          <span class="image-cache-state is-${escapeAttr(personal.state || "idle")}">${stateLabel}</span>
        `;
        fields.imageCacheStatus.removeAttribute("aria-busy");
      }

      function syncImageCacheStatusPolling() {
        window.clearInterval(imageCacheStatusTimer);
        imageCacheStatusTimer = null;
        if (currentView !== "admin" || currentIdentity?.user?.role !== "owner" || document.hidden) return;
        if (!imageCacheStatus) loadImageCacheStatus();
        imageCacheStatusTimer = window.setInterval(loadImageCacheStatus, IMAGE_CACHE_STATUS_INTERVAL_MS);
      }

      async function downloadCatalogExport(event) {
        const button = event.target.closest("[data-catalog-export]");
        if (!button) return;
        const format = String(button.dataset.catalogExport || "").toLowerCase();
        if (!["json", "csv"].includes(format)) return;
        const buttons = [...fields.catalogExportActions.querySelectorAll("button")];
        buttons.forEach((control) => { control.disabled = true; });
        fields.catalogExportActions.setAttribute("aria-busy", "true");
        setInlineFeedback(fields.catalogExportFeedback, "Preparando la copia portable...", "working");
        try {
          const response = await apiFetch(`/api/catalog/export?format=${encodeURIComponent(format)}`);
          if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.reason || `http_${response.status}`);
          }
          const blob = await response.blob();
          const disposition = response.headers.get("Content-Disposition") || "";
          const named = disposition.match(/filename="([^"]+)"/i);
          const filename = named?.[1] || `movie-inbox-catalog.${format}`;
          const href = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = href;
          link.download = filename;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(href), 0);
          setInlineFeedback(fields.catalogExportFeedback, `${filename} descargado.`, "success");
        } catch (error) {
          console.error(error);
          setInlineFeedback(
            fields.catalogExportFeedback,
            "No pudimos preparar la descarga. Actualizá los datos e intentá nuevamente.",
            "error"
          );
        } finally {
          buttons.forEach((control) => { control.disabled = false; });
          fields.catalogExportActions.removeAttribute("aria-busy");
        }
      }

      function externalDatabaseItem(label, source) {
        const health = externalHealth?.sources?.[source] || {};
        const consumed = externalSourcesLastUsed.includes(source);
        const attempted = externalSourcesAttempted.includes(source);
        const searchState = externalSourceSearchStates[source]?.status || "idle";
        const stateLabels = { ready: "lista", ok: "disponible", empty: "sin resultados", error: "error" };
        const state = stateLabels[health.status] || (fields.externalSource.checked ? "lista" : "apagada");
        const request = searchState === "loading"
          ? "consultando"
          : ["error", "timeout"].includes(searchState)
            ? "consulta incompleta"
            : attempted ? (consumed ? `${health.result_count || 0} resultados` : "sin resultados") : "sin consultar";
        const latency = health.latency_ms ? `${health.latency_ms} ms` : "";
        const error = health.error ? ` | ${health.error}` : "";
        const status = [state, request, latency].filter(Boolean).join(" | ") + error;
        return `<div class="db-item"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(status)}</span></div>`;
      }

      function externalCacheItem() {
        const cache = externalHealth?.cache || {};
        const entries = Number(cache.search_entries || 0) + Number(cache.metadata_entries || 0);
        return `<div class="db-item"><strong>Cache</strong><span>${entries} entradas | ${Number(cache.hits || 0)} hits | ${Number(cache.misses || 0)} misses</span></div>`;
      }

      async function runSearch({ updateHistory = true } = {}) {
        const requestedQuery = fields.query.value.trim();
        fields.collectionUtilityMenu.open = false;
        if (!requestedQuery) {
          clearManualSearch({ focus: false, updateHistory });
          return;
        }
        activeQuery = requestedQuery.length >= 2 ? requestedQuery : "";
        selectedManualIndex = null;
        selectedExistingIdForSearch = null;
        manualResults = [];
        catalogMergeResults = [];
        manualVisibleCount = SEARCH_PAGE_SIZE;
        manualSourceVisibleCounts = {};
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        fields.reviewPrevious.hidden = true;
        fields.reviewNext.hidden = true;
        setCollectionSearchMode("browse");
        render();
        renderDatabaseMenu();
        if (requestedQuery.length < 2) {
          setSearchState("error", "La búsqueda necesita al menos 2 caracteres.");
          if (updateHistory) syncCollectionRoute("push");
          return;
        }
        if (updateHistory) syncCollectionRoute("push");
        showView("catalog", { updateHistory: false, scroll: false });
        await searchManual("all");
      }

      function setSearchState(state, message = "") {
        const comparisonMode = collectionSearchMode !== "browse";
        fields.collectionView.classList.toggle("has-search-results", Boolean(activeQuery) && state !== "idle");
        fields.searchContext.hidden = state !== "searching" && state !== "error" && !comparisonMode;
        fields.searchContext.dataset.state = state;
        fields.searchContextText.textContent = message;
        fields.cancelSearch.hidden = state !== "searching";
        fields.clearManualSearch.hidden = state === "idle" && !comparisonMode;
        fields.backToCollection.hidden = !comparisonMode;
      }

      function setCollectionSearchMode(mode = "browse") {
        collectionSearchMode = ["browse", "compare", "link"].includes(mode) ? mode : "browse";
        const comparisonMode = collectionSearchMode !== "browse";
        fields.collectionView.classList.toggle("is-compare-mode", comparisonMode);
        fields.collectionView.dataset.searchMode = collectionSearchMode;
        fields.backToCollection.hidden = !comparisonMode;
        if (!comparisonMode && !activeQuery) {
          fields.catalogMergeKicker.textContent = "Comparación";
          fields.catalogMergeTitle.textContent = "Entrada de la colección";
        }
      }

      function collectionSearchMessage() {
        const count = filteredItems().length;
        const noun = count === 1 ? "título" : "títulos";
        return `${count} ${noun} en tu colección para “${activeQuery}”.`;
      }

      function comparisonSearchMessage() {
        if (collectionSearchMode === "link") {
          const selected = items.find((item) => item.id === selectedExistingIdForSearch);
          return `Buscando una referencia para “${displayTitle(selected || {}) || activeQuery}”.`;
        }
        const incoming = manualResults[selectedManualIndex] || {};
        return `Elegí la entrada local que corresponde a “${displayTitle(incoming) || activeQuery}”.`;
      }

      function emptyCollectionFilters() {
        return Object.fromEntries(COLLECTION_MULTI_FILTER_KEYS.map((key) => [key, new Set()]));
      }

      function validCollectionYear(value) {
        const year = String(value || "").trim();
        return /^(18|19|20|21)\d{2}$/.test(year) ? year : "";
      }

      function matchingFilterValue(values, value) {
        const key = normalizeText(value);
        return [...values].find((candidate) => normalizeText(candidate) === key) || "";
      }

      function setCollectionFilterValue(filter, value, selected) {
        if (!COLLECTION_MULTI_FILTER_KEYS.includes(filter) || !String(value || "").trim()) return;
        const values = collectionFilters[filter];
        const existing = matchingFilterValue(values, value);
        if (selected && !existing) values.add(String(value).trim());
        if (!selected && existing) values.delete(existing);
      }

      function toggleCollectionFilter(filter, value) {
        if (!COLLECTION_MULTI_FILTER_KEYS.includes(filter) || !value) return;
        setCollectionFilterValue(filter, value, !matchingFilterValue(collectionFilters[filter], value));
        collectionFiltersChanged();
      }

      function collectionFiltersChanged() {
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        syncCollectionFilterControls();
        render();
        syncCollectionRoute("push");
      }

      function applyCollectionFilterDescriptor(descriptor) {
        if (!descriptor || typeof descriptor !== "object") return;
        for (const key of COLLECTION_MULTI_FILTER_KEYS) {
          const values = Array.isArray(descriptor[key]) ? descriptor[key] : [descriptor[key]];
          values.filter(Boolean).forEach((value) => setCollectionFilterValue(key, String(value), true));
        }
        collectionYearRange = {
          from: validCollectionYear(descriptor.year_from),
          to: validCollectionYear(descriptor.year_to)
        };
        if (descriptor.sort && [...fields.sort.options].some((option) => option.value === descriptor.sort)) {
          fields.sort.value = descriptor.sort;
        }
        syncCollectionFilterControls();
      }

      function applyCollectionYearRange() {
        const from = validCollectionYear(fields.yearFromFilter.value);
        const to = validCollectionYear(fields.yearToFilter.value);
        const invalidFrom = Boolean(fields.yearFromFilter.value && !from);
        const invalidTo = Boolean(fields.yearToFilter.value && !to);
        fields.yearFromFilter.setCustomValidity(invalidFrom ? "Ingresá un año entre 1800 y 2199." : "");
        fields.yearToFilter.setCustomValidity(invalidTo ? "Ingresá un año entre 1800 y 2199." : "");
        if (invalidFrom || invalidTo) {
          (invalidFrom ? fields.yearFromFilter : fields.yearToFilter).reportValidity();
          return;
        }
        collectionYearRange = from && to && Number(from) > Number(to)
          ? { from: to, to: from }
          : { from, to };
        collectionFiltersChanged();
      }

      function syncCollectionFilterControls() {
        document.querySelectorAll('[data-click="toggle-collection-filter"]').forEach((button) => {
          const values = collectionFilters[button.dataset.filter];
          const selected = values instanceof Set && Boolean(matchingFilterValue(values, button.dataset.value || ""));
          button.setAttribute("aria-pressed", String(selected));
        });
        fields.yearFromFilter.value = collectionYearRange.from;
        fields.yearToFilter.value = collectionYearRange.to;
        const advancedKeys = ["source", "decade", "genre", "director", "record", "release_day"];
        const count = advancedKeys.reduce((total, key) => total + collectionFilters[key].size, 0)
          + (collectionYearRange.from || collectionYearRange.to ? 1 : 0);
        fields.advancedFilterCount.hidden = count === 0;
        fields.advancedFilterCount.textContent = String(count);
        fields.advancedFiltersMenu.classList.toggle("has-active-filters", count > 0);
      }

      function filterSetMatchesValue(values, value) {
        return !values.size || Boolean(matchingFilterValue(values, value));
      }

      function filterSetMatchesList(values, candidates) {
        if (!values.size) return true;
        return asList(candidates).some((candidate) => matchingFilterValue(values, candidate));
      }

      function matchesYearFilters(item) {
        const decades = collectionFilters.decade;
        const hasRange = Boolean(collectionYearRange.from || collectionYearRange.to);
        if (!decades.size && !hasRange) return true;
        const year = numericYear(item.year);
        if (!year) return false;
        const decadeMatch = decades.size && matchingFilterValue(decades, String(Math.floor(year / 10) * 10));
        const rangeMatch = hasRange
          && (!collectionYearRange.from || year >= Number(collectionYearRange.from))
          && (!collectionYearRange.to || year <= Number(collectionYearRange.to));
        return Boolean(decadeMatch || rangeMatch);
      }

      function matchesReleaseDay(item) {
        const days = collectionFilters.release_day;
        if (!days.size) return true;
        return (Array.isArray(item.release_dates) ? item.release_dates : []).some((release) => {
          if (release?.precision !== "day") return false;
          const value = String(release.date || "");
          return value.length >= 10 && matchingFilterValue(days, value.slice(5, 10));
        });
      }

      function matchesPersonalRecord(item) {
        const records = collectionFilters.record;
        if (!records.size) return true;
        return (records.has("unrated") && normalizeRating(item.rating) === 0)
          || (records.has("unreviewed") && !String(item.review || "").trim());
      }

      function emptyCatalogMetrics() {
        return {
          total: 0,
          catalogued: 0,
          watched: 0,
          toWatch: 0,
          rated: 0,
          withImage: 0,
          externalLinks: 0,
          withoutExternalLinks: 0,
          imdbLinks: 0,
          filmAffinityLinks: 0,
          duplicates: 0
        };
      }

      function catalogSearchDocument(item) {
        return [
          item.title,
          item.original_title,
          item.spanish_title,
          item.english_title,
          asList(item.alternative_titles).join(" "),
          item.local_name,
          item.local_path,
          localFilesText(item),
          item.year,
          Array.isArray(item.release_dates) ? item.release_dates.map((entry) => entry?.date || "").join(" ") : "",
          item.description,
          item.wikipedia_extract,
          item.notes,
          item.review,
          item.watched_at,
          item.rating,
          asList(item.genres).join(" "),
          asList(item.directors).join(" "),
          asList(item.writers).join(" "),
          asList(item.cast).join(" "),
          Array.isArray(item.tags) ? item.tags.join(" ") : item.tags
        ].join(" ");
      }

      function prepareCatalogViewModel() {
        const metrics = emptyCatalogMetrics();
        const searchIndex = new WeakMap();
        for (const item of items) {
          searchIndex.set(item, normalizeText(catalogSearchDocument(item)));
          metrics.total += 1;
          if (isInCatalog(item.en_catalogo)) metrics.catalogued += 1;
          if (item.status === "watched") metrics.watched += 1;
          if (item.status === "to_watch") metrics.toWatch += 1;
          if (normalizeRating(item.rating) > 0) metrics.rated += 1;
          if (item.page_image) metrics.withImage += 1;
          if (hasExternalLink(item)) metrics.externalLinks += 1;
          else metrics.withoutExternalLinks += 1;
          if (hasHost(item.url, "imdb.com") || hasHost(item.imdb_url, "imdb.com")) metrics.imdbLinks += 1;
          if (hasHost(item.url, "filmaffinity.com") || hasHost(item.filmaffinity_url, "filmaffinity.com")) {
            metrics.filmAffinityLinks += 1;
          }
          if (Number(item._duplicate_count || 0) > 0) metrics.duplicates += 1;
        }
        catalogSearchIndex = searchIndex;
        catalogMetrics = metrics;
        catalogRevision += 1;
        lastCatalogGridKey = "";
      }

      function filteredItems() {
        const normalizedQuery = normalizeText(activeQuery.trim());
        return items.filter((item) => {
          const searchText = catalogSearchIndex.get(item) || normalizeText(catalogSearchDocument(item));
          return (!normalizedQuery || matchesNormalizedSearchText(searchText, normalizedQuery))
            && (!duplicatesOnly || Number(item._duplicate_count || 0) > 0)
            && filterSetMatchesValue(collectionFilters.status, item.status)
            && filterSetMatchesValue(
              collectionFilters.availability,
              isInCatalog(item.en_catalogo) ? "available" : "unavailable"
            )
            && filterSetMatchesValue(collectionFilters.kind, item.kind)
            && filterSetMatchesValue(collectionFilters.source, item.source)
            && filterSetMatchesList(collectionFilters.genre, item.genres)
            && filterSetMatchesList(collectionFilters.director, item.directors)
            && matchesYearFilters(item)
            && matchesReleaseDay(item)
            && matchesPersonalRecord(item);
        });
      }

      function sortItems(list) {
        const mode = fields.sort.value || "original";
        if (mode === "original") return list;
        const sorted = [...list];
        if (mode === "title-asc") {
          return sorted.sort((left, right) => displayTitle(left).localeCompare(displayTitle(right), "es", { sensitivity: "base" }));
        }
        if (mode === "year-desc") {
          return sorted.sort((left, right) => numericYear(right.year) - numericYear(left.year));
        }
        if (mode === "year-asc") {
          return sorted.sort((left, right) => {
            const leftYear = numericYear(left.year) || Number.MAX_SAFE_INTEGER;
            const rightYear = numericYear(right.year) || Number.MAX_SAFE_INTEGER;
            return leftYear - rightYear;
          });
        }
        if (mode === "rating-desc") {
          return sorted.sort((left, right) => normalizeRating(right.rating) - normalizeRating(left.rating));
        }
        if (mode === "added-desc") {
          return sorted.sort((left, right) => String(right.added_at || "").localeCompare(String(left.added_at || "")));
        }
        return sorted;
      }

      function numericYear(value) {
        const year = Number.parseInt(value || 0, 10);
        return Number.isNaN(year) ? 0 : year;
      }

      function resetCollectionFilters() {
        collectionFilters = emptyCollectionFilters();
        collectionYearRange = { from: "", to: "" };
        fields.sort.value = "original";
        duplicatesOnly = false;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        syncCollectionFilterControls();
      }

      function clearFilters() {
        resetCollectionFilters();
        render();
        syncCollectionRoute("push");
      }

      function clearFilter(filter, value = "") {
        if (filter === "query") {
          clearManualSearch({ focus: false });
          return;
        }
        if (COLLECTION_MULTI_FILTER_KEYS.includes(filter)) {
          if (value) setCollectionFilterValue(filter, value, false);
          else collectionFilters[filter].clear();
        } else if (filter === "year") {
          collectionYearRange = { from: "", to: "" };
        } else if (filter === "sort") {
          fields.sort.value = "original";
        } else if (filter === "duplicates") {
          duplicatesOnly = false;
        } else if (filter === "random") {
          randomOrder = [];
        }
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        syncCollectionFilterControls();
        render();
        syncCollectionRoute("push");
      }

      function renderActiveFilters() {
        const filters = [];
        if (activeQuery) filters.push(["query", "", `Búsqueda: ${activeQuery}`]);
        const labels = {
          status: "Estado",
          availability: "Disponibilidad",
          kind: "Tipo",
          source: "Fuente",
          decade: "Década",
          genre: "Género",
          director: "Dirección",
          record: "Memoria"
        };
        for (const key of COLLECTION_MULTI_FILTER_KEYS) {
          for (const value of collectionFilters[key]) {
            let label = `${labels[key] || key}: ${filterValueLabel(key, value)}`;
            if (key === "decade") label = `Años ${value}`;
            if (key === "release_day") label = releaseDayFilterLabel(value);
            filters.push([key, value, label]);
          }
        }
        if (collectionYearRange.from || collectionYearRange.to) {
          const range = collectionYearRange.from && collectionYearRange.to
            ? `${collectionYearRange.from}–${collectionYearRange.to}`
            : collectionYearRange.from ? `Desde ${collectionYearRange.from}` : `Hasta ${collectionYearRange.to}`;
          filters.push(["year", "", range]);
        }
        if (fields.sort.value && fields.sort.value !== "original") {
          filters.push(["sort", "", fields.sort.selectedOptions[0]?.textContent || "Orden personalizado"]);
        }
        if (duplicatesOnly) filters.push(["duplicates", "", "Sólo duplicadas"]);
        if (randomOrder.length) filters.push(["random", "", "Vista mezclada"]);
        fields.activeFilters.hidden = filters.length === 0;
        fields.activeFilters.innerHTML = filters.length
          ? `<span>Activos</span>${filters.map(([filter, value, label]) => (
              `<button type="button" data-click="clear-filter" data-filter="${escapeAttr(filter)}" data-value="${escapeAttr(value)}" aria-label="Quitar ${escapeAttr(label)}">${escapeHtml(label)} <span aria-hidden="true">×</span></button>`
            )).join("")}`
          : "";
      }

      function releaseDayFilterLabel(value) {
        const [month, day] = String(value || "").split("-").map(Number);
        const parsed = new Date(2024, month - 1, day);
        if (!month || !day || Number.isNaN(parsed.getTime())) return "Fecha de estreno";
        const label = new Intl.DateTimeFormat("es-AR", { day: "numeric", month: "long" }).format(parsed);
        return `Estrenadas un ${label}`;
      }

      function hasActiveCollectionFilters() {
        return COLLECTION_MULTI_FILTER_KEYS.some((key) => collectionFilters[key].size)
          || Boolean(collectionYearRange.from || collectionYearRange.to)
          || duplicatesOnly;
      }

      function applyRandomOrder(list) {
        if (!randomOrder.length) return list;
        const byId = new Map(list.map((item) => [item.id, item]));
        const ordered = randomOrder.map((id) => byId.get(id)).filter(Boolean);
        const orderedIds = new Set(ordered.map((item) => item.id));
        return [...ordered, ...list.filter((item) => !orderedIds.has(item.id))];
      }

      function render() {
        const baseFiltered = sortItems(filteredItems());
        const filtered = applyRandomOrder(baseFiltered);
        const shown = filtered.slice(0, catalogVisibleCount);

        renderHeaderStats();
        fields.total.textContent = catalogMetrics.total;
        fields.catalogCount.textContent = catalogMetrics.catalogued;
        fields.watchedCount.textContent = catalogMetrics.watched;
        fields.toWatchCount.textContent = catalogMetrics.toWatch;
        fields.ratedCount.textContent = catalogMetrics.rated;
        fields.withImage.textContent = catalogMetrics.withImage;
        fields.wikiLinks.textContent = catalogMetrics.externalLinks;
        fields.withoutWiki.textContent = catalogMetrics.withoutExternalLinks;
        fields.imdbLinks.textContent = catalogMetrics.imdbLinks;
        fields.faLinks.textContent = catalogMetrics.filmAffinityLinks;
        fields.duplicateCount.textContent = catalogMetrics.duplicates;
        fields.showDuplicates.textContent = duplicatesOnly ? "Ver todo" : "Ver duplicadas";
        fields.sourceFiles.textContent = sourceFiles.length;
        fields.catalogSummary.textContent = catalogSummaryText(filtered);
        fields.empty.style.display = filtered.length ? "none" : "block";
        fields.empty.textContent = activeQuery
          ? `No encontramos obras para “${activeQuery}” con los filtros actuales.`
          : "No hay obras que coincidan con los filtros actuales.";
        const gridKey = `${catalogRevision}:${currentView === "catalog" ? "catalog" : "background"}:${shown.map((item) => item.id).join("|")}`;
        if (gridKey !== lastCatalogGridKey) {
          fields.grid.innerHTML = shown
            .map((item, index) => card(item, index, currentView === "catalog"))
            .join("");
          lastCatalogGridKey = gridKey;
        }
        fields.catalogLoadMore.hidden = shown.length >= filtered.length;
        fields.catalogLoadMore.textContent = `Cargar más (${filtered.length - shown.length})`;
        if (lastEditorialRenderRevision !== editorialRevision) {
          renderEditorialHome();
          lastEditorialRenderRevision = editorialRevision;
        }
        renderActiveFilters();
        syncRandomControl();
        renderDetail();
      }

      function renderHeaderStats() {
        fields.stats.textContent = `${catalogMetrics.total} obras · ${catalogMetrics.watched} vistas · ${catalogMetrics.catalogued} disponibles`;
      }

      function catalogSummaryText(filtered) {
        const count = filtered.length;
        const noun = count === 1 ? "título" : "títulos";
        if (activeQuery) return `${count} ${noun} para “${activeQuery}”`;
        if (hasActiveCollectionFilters()) return `${count} ${noun} con los filtros actuales`;
        if (randomOrder.length) return `${count} ${noun} en orden aleatorio`;
        return `${count} ${noun} en la estantería`;
      }

      function showMoreCatalogItems() {
        catalogVisibleCount += CATALOG_PAGE_SIZE;
        render();
      }

      function randomizeView() {
        const visibleIds = filteredItems().map((item) => item.id);
        randomOrder = shuffle(visibleIds);
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }

      function resetViewOrder() {
        randomOrder = [];
        fields.sort.value = "original";
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }

      function toggleDuplicatesOnly() {
        duplicatesOnly = !duplicatesOnly;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
        syncCollectionRoute("push");
        goToCollection();
      }

      function shuffle(values) {
        const shuffled = [...values];
        for (let index = shuffled.length - 1; index > 0; index -= 1) {
          const swapIndex = Math.floor(Math.random() * (index + 1));
          [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
        }
        return shuffled;
      }

      function card(item, index = 0, prioritize = false, options = {}) {
        const shownTitle = displayTitle(item);
        const title = shownTitle || "Sin título";
        const titleClass = titleSizeClass(title);
        const rating = normalizeRating(item.rating);
        const watched = item.status === "watched";
        const catalogued = isInCatalog(item.en_catalogo);
        const fromCollection = options.action === "open-home-collection-detail";
        const collectionTitle = String(options.collectionTitle || "Colección");
        const action = options.action || "open-detail";
        const actionId = options.actionId || item.id || "";
        const entryKey = options.entryKey || "";
        const duplicate = Number(item._duplicate_count || 0) > 0
          ? `<span class="dvd-sticker">Duplicada +${escapeHtml(item._duplicate_count)}</span>`
          : "";
        const accessibleStatus = fromCollection
          ? `en la colección ${collectionTitle}, disponible para agregar`
          : `${watched ? "vista" : "pendiente"}, ${catalogued ? "disponible" : "sin disponibilidad"}, ${rating} puntos`;
        const backMeta = [item.year, firstListValue(item.directors)].filter(Boolean).join(" · ") || "Ficha sin completar";
        return `<article class="card dvd-card${fromCollection ? " is-collection-entry" : ""}" data-click="${escapeAttr(action)}" data-id="${escapeAttr(actionId)}" data-key="${escapeAttr(entryKey)}">
          <div class="dvd-flipper" aria-hidden="true">
            <div class="dvd-face dvd-front">
              <div class="dvd-case">
                <span class="dvd-spine"></span>
                <div class="dvd-cover">
                  ${posterArtwork(item, title, prioritize && index < 6)}
                  <span class="dvd-gloss"></span>
                  ${duplicate}
                  <div class="dvd-title-block">
                    <div class="dvd-title-meta">
                      <span>${escapeHtml(item.year || "Año desconocido")}</span>
                      ${rating ? `<strong>${rating}/10</strong>` : ""}
                    </div>
                    <h2 class="${titleClass}">${escapeHtml(title)}</h2>
                    <div class="dvd-front-statuses">
                      ${fromCollection
                        ? `<span class="dvd-front-status collection">Colección</span><span class="dvd-front-status pending">Por agregar</span>`
                        : `<span class="dvd-front-status ${catalogued ? "catalogued" : "muted"}">${catalogued ? "Disponible" : "No disponible"}</span><span class="dvd-front-status ${watched ? "watched" : "pending"}">${watched ? "Vista" : "Pendiente"}</span>`}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="dvd-face dvd-back">
              <div class="dvd-case dvd-back-case">
                <span class="dvd-spine"></span>
                <div class="dvd-back-cover">
                  <div class="dvd-back-header">
                    <span>Archivo nocturno</span>
                    <h2 class="${titleClass}">${escapeHtml(title)}</h2>
                  </div>
                  <p class="dvd-back-summary">${escapeHtml(dvdBackSummary(item))}</p>
                  <p class="dvd-back-meta">${escapeHtml(backMeta)}</p>
                  <div class="dvd-back-statuses">
                    ${fromCollection
                      ? `<span class="active">En ${escapeHtml(collectionTitle)}</span><span>Fuera de tu catálogo</span><strong>Lista para revisar</strong>`
                      : `<span class="${watched ? "active" : ""}">${watched ? "✓ Vista" : "Pendiente"}</span><span class="${catalogued ? "active" : ""}">${catalogued ? "Disponible" : "No disponible"}</span><strong>${rating ? `${rating} pts` : "0 pts · Sin puntuar"}</strong>`}
                  </div>
                  <span class="dvd-back-hint">Click para abrir la ficha →</span>
                  <div class="dvd-barcode"><span></span><small>${escapeHtml(String(item.id || "movie-inbox").slice(0, 18))}</small></div>
                </div>
              </div>
            </div>
          </div>
          ${openCardButton(item, title, accessibleStatus, { action, actionId, entryKey })}
        </article>`;
      }

      function openCardButton(item, title, accessibleStatus, options = {}) {
        const action = options.action || "open-detail";
        const actionId = options.actionId || item.id || "";
        return `<button class="dvd-open-surface" type="button" data-click="${escapeAttr(action)}" data-id="${escapeAttr(actionId)}" data-key="${escapeAttr(options.entryKey || "")}" aria-haspopup="dialog" aria-label="Abrir ficha de ${escapeAttr(title)}: ${escapeAttr(accessibleStatus)}"></button>`;
      }

      function dvdBackSummary(item) {
        const summary = String(item.wikipedia_extract || item.description || item.notes || "Sin sinopsis disponible.").trim();
        return summary.length > 190 ? `${summary.slice(0, 187).trimEnd()}…` : summary;
      }

      function posterArtwork(item, title, priority = false) {
        const variant = posterVariant(item.id || title);
        const placeholder = `<div class="dvd-placeholder poster-${variant}" aria-hidden="true">
          <span>Movie Inbox presenta</span>
          <strong class="${titleSizeClass(title)}">${escapeHtml(title)}</strong>
          <small>Edición videoclub</small>
        </div>`;
        if (!item.page_image) return placeholder;
        const fetchPriority = priority ? "high" : "auto";
        return `<img class="dvd-cover-image" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="Portada de ${escapeAttr(title)}" loading="lazy" fetchpriority="${fetchPriority}" decoding="async">${placeholder}`;
      }

      function posterVariant(seed) {
        const value = [...String(seed || "")].reduce((total, character) => total + character.codePointAt(0), 0);
        return (value % 4) + 1;
      }

      function handlePosterLoad(event) {
        const spotlightImage = event.target.closest?.("[data-spotlight-image]");
        if (spotlightImage) {
          spotlightImage.classList.add("is-loaded");
          return;
        }
        const image = event.target.closest?.("[data-poster-image]");
        if (!image) return;
        image.hidden = false;
        image.classList.add("is-loaded");
      }

      function handlePosterError(event) {
        const spotlightImage = event.target.closest?.("[data-spotlight-image]");
        if (spotlightImage) {
          spotlightImage.hidden = true;
          spotlightImage.closest(".spotlight-slide")?.classList.add("is-image-missing");
          return;
        }
        const image = event.target.closest?.("[data-poster-image]");
        if (!image) return;
        image.classList.remove("is-loaded");
        image.hidden = true;
        const fallback = image.nextElementSibling;
        if (fallback?.matches(".dvd-placeholder, .drawer-poster-placeholder, .curation-thumb-placeholder")) {
          fallback.hidden = false;
        }
      }

      function personalRecordPanel(item) {
        if (detailPersonalEditing) return personalRecordEditor(item);
        const rating = normalizeRating(item.rating);
        const review = String(item.review || "").trim();
        const privacy = item._privacy || {};
        return `<div class="personal-record-read">
          <div class="record-heading">
            <div>
              <span class="drawer-kicker">Memoria personal</span>
              <h3>Mi registro</h3>
            </div>
            <button class="quiet-action record-edit-action" type="button" data-click="edit-personal" data-id="${escapeAttr(item.id)}">Editar registro</button>
          </div>
          <dl class="personal-read-grid">
            <div>
              <dt>Fecha vista</dt>
              <dd>${escapeHtml(item.watched_at || "Sin fecha")}</dd>
            </div>
            <div>
              <dt>Puntuación</dt>
              <dd>${rating ? `${rating}/10` : "Sin puntuar"} ${personalVisibilityBadge("rating", privacy.rating)}</dd>
            </div>
          </dl>
          <div class="personal-review-read">
            <span>Review ${personalVisibilityBadge("review", privacy.review)}</span>
            <p>${escapeHtml(review || "Sin review")}</p>
          </div>
        </div>`;
      }

      function personalRecordEditor(item) {
        const rating = normalizeRating(item.rating);
        const privacy = item._privacy || {};
        const ratingOptions = Array.from({ length: 11 }, (_, value) => (
          `<option value="${value}" ${value === rating ? "selected" : ""}>${value}</option>`
        )).join("");
        return `<div class="personal-record-editor" data-detail-form="personal" data-id="${escapeAttr(item.id)}">
          <div class="record-heading">
            <div>
              <span class="drawer-kicker">Edición</span>
              <h3>Mi registro</h3>
            </div>
            <span class="status-line" data-personal-status></span>
          </div>
          <div class="personal-grid">
            <label>
              Fecha vista
              <input name="watched_at" data-personal-watched-at type="date" value="${escapeAttr(item.watched_at || "")}">
            </label>
            <label>
              Puntaje
              <select name="rating" data-personal-rating>
                ${ratingOptions}
              </select>
            </label>
            <label class="review-field">
              Review
              <textarea name="review" data-personal-review rows="6">${escapeHtml(item.review || "")}</textarea>
            </label>
            <fieldset class="personal-privacy-fields">
              <legend>Visibilidad en el Club</legend>
              <label>
                Puntaje
                <select name="rating_privacy" data-personal-rating-privacy>
                  ${personalPrivacyOptions("rating", privacy.rating)}
                </select>
              </label>
              <label>
                Review
                <select name="review_privacy" data-personal-review-privacy>
                  ${personalPrivacyOptions("review", privacy.review)}
                </select>
              </label>
              <small>Estos ajustes reemplazan tu preferencia general solamente para esta obra.</small>
            </fieldset>
            <div class="personal-actions">
              <button type="button" data-click="save-personal" data-detail-save data-id="${escapeAttr(item.id)}">Guardar cambios</button>
              <button class="quiet-action" type="button" data-click="cancel-personal" data-id="${escapeAttr(item.id)}">Cancelar</button>
            </div>
          </div>
        </div>`;
      }

      function personalPrivacyOptions(field, selectedMode = "inherit") {
        const inheritedShared = field === "rating"
          ? Boolean(privacyPreferences.share_rating)
          : Boolean(privacyPreferences.share_review);
        const selected = ["inherit", "shared", "private"].includes(selectedMode)
          ? selectedMode
          : "inherit";
        const options = [
          ["inherit", `Heredar (${inheritedShared ? "compartido" : "privado"})`],
          ["shared", "Compartir esta obra"],
          ["private", "Mantener privada"]
        ];
        return options.map(([value, label]) => (
          `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`
        )).join("");
      }

      function personalVisibilityBadge(field, mode = "inherit") {
        const inheritedShared = field === "rating"
          ? Boolean(privacyPreferences.share_rating)
          : Boolean(privacyPreferences.share_review);
        const shared = mode === "shared" || (mode !== "private" && inheritedShared);
        const label = privacyPreferences.catalog_shared && shared ? "Visible en Club" : "Privado";
        return `<small class="personal-visibility ${label === "Privado" ? "is-private" : "is-shared"}">${label}</small>`;
      }

      function factsPanel(item) {
        const rows = [
          ["Género", item.genres, 4],
          ["Estreno", primaryReleaseDateLabel(item), 1],
          ["Original", item.original_title, 1],
          ["Español", item.spanish_title, 1],
          ["Inglés", item.english_title, 1],
          ["Alternativos", item.alternative_titles, 6],
          ["Director", item.directors, 4],
          ["Guion", item.writers, 4],
          ["Reparto", item.cast, 8]
        ].map(([label, values, limit]) => {
          const text = listText(values, limit);
          return text ? `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(text)}</dd>` : "";
        }).filter(Boolean);
        const content = rows.join("");
        return content ? `<dl class="facts">${content}</dl>` : "";
      }

      function primaryReleaseDateLabel(item) {
        const dates = Array.isArray(item?.release_dates) ? item.release_dates : [];
        const selected = dates.find((entry) => entry?.is_primary) || dates[0];
        return selected ? releaseDateLabel(selected) : "";
      }

      function releaseDateLabel(entry) {
        const raw = String(entry?.date || "");
        const [year, month, day] = raw.split("-");
        const months = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
        let label = year || "Fecha desconocida";
        if (entry?.precision === "month" && month) label = `${months[Number(month) - 1] || month} de ${year}`;
        if (entry?.precision === "day" && month && day) label = `${Number(day)} de ${months[Number(month) - 1] || month} de ${year}`;
        if (entry?.country) label += ` · ${entry.country}`;
        return label;
      }

      function availabilityPanel(item) {
        const localText = localFilesText(item);
        const duplicates = Number(item._duplicate_count || 0);
        const state = availabilityState(item);
        const sourceText = (state.details.sources || [])
          .map((source) => `${source.library_name} (${source.file_count})`)
          .join(" · ");
        const fileLabel = `${state.fileCount} ${state.fileCount === 1 ? "archivo verificado" : "archivos verificados"}`;
        return `<div class="availability-panel">
          <dl class="availability-list">
            <div><dt>Disponibilidad</dt><dd>${state.effective ? "Disponible" : "No disponible"} · ${escapeHtml(state.origin)}</dd></div>
            <div><dt>Declaración manual</dt><dd>${state.manual ? "Activa" : "Inactiva"}</dd></div>
            <div><dt>Inventario del servidor</dt><dd>${state.server ? fileLabel : "Sin archivos vinculados"}</dd></div>
            ${sourceText ? `<div><dt>Bibliotecas</dt><dd>${escapeHtml(sourceText)}</dd></div>` : ""}
            ${localText ? `<div><dt>Archivos heredados</dt><dd>${escapeHtml(localText)}</dd></div>` : ""}
            <div><dt>Fuente de metadata</dt><dd>${escapeHtml(item.source || "Sin fuente")}</dd></div>
            ${duplicates ? `<div><dt>Duplicados</dt><dd>${escapeHtml(`${duplicates} coincidencia(s): ${item._duplicate_reason || "misma obra"}`)}</dd></div>` : ""}
          </dl>
          <button class="drawer-secondary-action" type="button" data-click="toggle-catalog" data-id="${escapeAttr(item.id)}" aria-pressed="${state.manual}">
            ${state.manual ? "Quitar declaración manual" : "Declarar disponibilidad manual"}
          </button>
        </div>`;
      }

      function openDetail(id, { updateHistory = true, context = null, skipGuard = false } = {}) {
        if (!id) return;
        if (!skipGuard && selectedDetailId && selectedDetailId !== id && hasUnsavedDetailChanges()) {
          requestDetailTransition(() => openDetail(id, { updateHistory, context, skipGuard: true }));
          return;
        }
        const activeElement = document.activeElement;
        detailReturnFocus = activeElement?.matches?.("[data-click='open-detail']")
          ? activeElement
          : activeElement?.closest?.(".dvd-card") ? activeElement : null;
        detailReturnCardId = id;
        setDetailContext(context, id);
        selectedDetailId = id;
        detailPersonalEditing = false;
        detailDirtyScopes.clear();
        clearDetailFeedback();
        renderDetail({ force: true });
        fields.detailBody.scrollTop = 0;
        if (!fields.detailDrawer.open) fields.detailDrawer.showModal();
        document.body.classList.add("drawer-open");
        if (updateHistory) syncRoute({ movie: id }, "push");
        requestAnimationFrame(() => fields.closeDetail.focus());
      }

      function closeDetail({ restoreFocus = true, updateHistory = true, skipGuard = false } = {}) {
        if (!selectedDetailId && !fields.detailDrawer.open) return;
        if (!skipGuard && hasUnsavedDetailChanges()) {
          requestDetailTransition(() => closeDetail({ restoreFocus, updateHistory, skipGuard: true }));
          return;
        }
        selectedDetailId = "";
        if (fields.detailDrawer.open) fields.detailDrawer.close();
        fields.detailBody.innerHTML = "";
        fields.detailNavigation.innerHTML = "";
        document.body.classList.remove("drawer-open");
        detailPersonalEditing = false;
        detailDirtyScopes.clear();
        pendingDetailTransition = null;
        clearDetailFeedback();
        if (updateHistory) syncRoute({ movie: "" }, "replace");
        const currentCard = [...document.querySelectorAll(".dvd-card")]
          .find((card) => card.dataset.id === detailReturnCardId);
        const returnTarget = detailReturnFocus?.isConnected
          ? detailReturnFocus
          : currentCard?.querySelector(".dvd-open-surface");
        if (restoreFocus) returnTarget?.focus();
        detailReturnFocus = null;
        detailReturnCardId = "";
      }

      function setDetailContext(context, selectedId) {
        if (context) {
          detailNavigationMode = context.mode || "catalog";
          detailNavigationLabel = context.label || "Colección";
          detailNavigationIds = uniqueExistingIds(context.ids || []);
        } else if (!detailNavigationIds.includes(selectedId)) {
          detailNavigationMode = "catalog";
          detailNavigationLabel = activeQuery ? `Colección · ${activeQuery}` : "Colección";
          detailNavigationIds = uniqueExistingIds(catalogDetailItems().map((item) => item.id));
        }
        if (!detailNavigationIds.includes(selectedId)) detailNavigationIds.unshift(selectedId);
      }

      function uniqueExistingIds(values) {
        const valid = new Set(items.map((item) => item.id));
        return [...new Set(values)].filter((id) => valid.has(id));
      }

      function renderDetailNavigation() {
        if (!selectedDetailId) {
          fields.detailNavigation.innerHTML = "";
          return;
        }
        if (detailNavigationMode === "random") {
          fields.detailNavigation.innerHTML = `
            <span class="drawer-navigation-label">${escapeHtml(detailNavigationLabel)}</span>
            <button class="drawer-navigation-random" type="button" data-click="detail-random">Otro al azar</button>
          `;
          return;
        }
        const index = detailNavigationIds.indexOf(selectedDetailId);
        const total = detailNavigationIds.length;
        fields.detailNavigation.innerHTML = `
          <button type="button" data-click="detail-previous" aria-label="Abrir ficha anterior" ${index <= 0 ? "disabled" : ""}>← <span>Anterior</span></button>
          <span class="drawer-navigation-counter">${escapeHtml(detailNavigationLabel)} · ${Math.max(index + 1, 1)} / ${Math.max(total, 1)}</span>
          <button type="button" data-click="detail-next" aria-label="Abrir ficha siguiente" ${index < 0 || index >= total - 1 ? "disabled" : ""}><span>Siguiente</span> →</button>
        `;
      }

      function navigateDetail(offset) {
        const index = detailNavigationIds.indexOf(selectedDetailId);
        const nextId = detailNavigationIds[index + offset];
        if (!nextId) return;
        requestDetailTransition(() => showDetailFromQueue(nextId));
      }

      function showDetailFromQueue(id) {
        detailPersonalEditing = false;
        detailDirtyScopes.clear();
        selectedDetailId = id;
        detailReturnCardId = id;
        clearDetailFeedback();
        renderDetail({ force: true });
        syncRoute({ movie: id }, "replace");
        fields.detailBody.scrollTop = 0;
        requestAnimationFrame(() => fields.closeDetail.focus());
      }

      function openAnotherRandomDetail() {
        const candidates = randomCandidates().filter((item) => item.id !== selectedDetailId);
        if (!candidates.length) return;
        const item = candidates[Math.floor(Math.random() * candidates.length)];
        requestDetailTransition(() => {
          detailNavigationIds = randomCandidates().map((candidate) => candidate.id);
          detailNavigationLabel = fields.randomCatalogOnly.checked ? "Al azar · Disponibles" : "Al azar · Todo";
          showDetailFromQueue(item.id);
        });
      }

      function renderDetail({ force = false } = {}) {
        if (!selectedDetailId) return;
        if (!force && hasUnsavedDetailChanges()) {
          renderDetailNavigation();
          syncDetailFeedback();
          return;
        }
        const item = items.find((entry) => entry.id === selectedDetailId);
        if (!item) {
          closeDetail({ skipGuard: true });
          return;
        }
        const rating = normalizeRating(item.rating);
        const shownTitle = displayTitle(item);
        const title = shownTitle || "Sin título";
        const subtitle = titleSubtitle(item);
        const summary = item.wikipedia_extract || item.description || item.notes || "";
        const watched = item.status === "watched";
        const availability = availabilityState(item);
        const metadataSection = detailPersonalEditing ? "" : `
          <details class="drawer-accordion drawer-editor">
            <summary><span>Editar metadata</span><small>Campos, procedencia y bloqueos</small></summary>
            <div class="drawer-accordion-body">${metadataEditor(item)}</div>
          </details>
        `;
        renderDetailNavigation();
        fields.detailBody.innerHTML = `
          <section class="drawer-hero">
            ${drawerPoster(item, title)}
            <div class="drawer-intro">
              <span class="drawer-kicker">Ficha del videoclub</span>
              <h2>${escapeHtml(title)}</h2>
              ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
              <div class="drawer-byline">${[item.year, firstListValue(item.directors), listText(item.genres, 2)].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join("")}</div>
            </div>
          </section>
          <section class="drawer-quick-actions" aria-label="Estado y disponibilidad">
            <button class="drawer-state ${watched ? "active" : ""}" type="button" data-click="toggle-watched" data-id="${escapeAttr(item.id)}" data-status="${escapeAttr(item.status || "to_watch")}" aria-pressed="${watched}">
              <span>Estado</span><strong>${watched ? "Vista" : "Pendiente"}</strong><small>${item.watched_at ? escapeHtml(item.watched_at) : "Sin fecha"}</small>
            </button>
            <div class="drawer-state ${availability.effective ? "active" : ""}">
              <span>Disponibilidad</span><strong>${availability.effective ? "Disponible" : "No disponible"}</strong><small>${escapeHtml(availability.origin)}</small>
            </div>
            <button class="drawer-state rating-state ${rating ? "active" : ""}" type="button" data-click="edit-personal" data-id="${escapeAttr(item.id)}">
              <span>Puntuación</span><strong>${rating ? `${rating}/10` : "Sin puntuar"}</strong><small>Editar registro</small>
            </button>
          </section>
          <section class="drawer-synopsis">
            <h3>Sinopsis</h3>
            <p>${escapeHtml(summary || "Todavía no hay una sinopsis disponible para esta película.")}</p>
          </section>
          <section class="drawer-section drawer-personal-section">
            ${personalRecordPanel(item)}
          </section>
          <details class="drawer-accordion">
            <summary><span>Ficha técnica</span><small>Dirección, reparto y títulos</small></summary>
            <div class="drawer-accordion-body">${factsPanel(item) || `<span class="status-line">Sin ficha enriquecida.</span>`}</div>
          </details>
          <details class="drawer-accordion">
            <summary><span>Disponibilidad y fuentes</span><small>Archivos, catálogos y enlaces</small></summary>
            <div class="drawer-accordion-body">
              ${availabilityPanel(item)}
              <div class="links">${detailLinks(item)}</div>
              <button class="drawer-secondary-action" type="button" data-click="find-link" data-id="${escapeAttr(item.id)}">Buscar o completar enlaces</button>
            </div>
          </details>
          ${metadataSection}
          <details class="drawer-accordion danger-zone">
            <summary><span>Mantenimiento</span><small>Acciones sensibles</small></summary>
            <div class="drawer-accordion-body">
              <p>Eliminar quita esta ficha del catálogo personal. No borra videos ni el inventario del servidor; otra ficha equivalente puede conservar la disponibilidad.</p>
              <button class="danger" type="button" data-click="delete-item" data-id="${escapeAttr(item.id)}">Eliminar del catálogo</button>
            </div>
          </details>
        `;
        primeDetailForms();
        syncDetailFeedback();
      }

      function drawerPoster(item, title) {
        const placeholder = `<div class="drawer-poster drawer-poster-placeholder poster-${posterVariant(item.id || title)}" aria-hidden="true"><span>Movie Inbox</span><strong>${escapeHtml(title)}</strong></div>`;
        const image = item.page_image
          ? `<img class="drawer-poster" data-poster-image src="${escapeAttr(cachedImageSrc(item.page_image))}" alt="Portada de ${escapeAttr(title)}" loading="eager" fetchpriority="high" decoding="async">`
          : "";
        return `<div class="drawer-poster-frame">${image}${placeholder}</div>`;
      }

      function editPersonalRecord() {
        if (!selectedDetailId || detailPersonalEditing) return;
        if (detailDirtyScopes.has("metadata")) {
          requestDetailTransition(editPersonalRecord);
          return;
        }
        detailPersonalEditing = true;
        renderDetail({ force: true });
        const editor = fields.detailBody.querySelector("[data-detail-form='personal']");
        editor?.scrollIntoView({ block: "center" });
        requestAnimationFrame(() => editor?.querySelector("[data-personal-watched-at]")?.focus());
      }

      function cancelPersonalEdit() {
        detailDirtyScopes.delete("personal");
        detailPersonalEditing = false;
        renderDetail({ force: true });
      }

      function detailLinks(item) {
        const links = [
          item.url ? `<a href="${escapeAttr(item.url)}" target="_blank" rel="noreferrer">Abrir link</a>` : "",
          item.wikipedia_url ? `<a href="${escapeAttr(item.wikipedia_url)}" target="_blank" rel="noreferrer">Wikipedia</a>` : "",
          item.imdb_url ? `<a href="${escapeAttr(item.imdb_url)}" target="_blank" rel="noreferrer">IMDb</a>` : "",
          item.filmaffinity_url ? `<a href="${escapeAttr(item.filmaffinity_url)}" target="_blank" rel="noreferrer">FilmAffinity</a>` : "",
          item.wikidata_id ? `<a href="https://www.wikidata.org/wiki/${escapeAttr(item.wikidata_id)}" target="_blank" rel="noreferrer">Wikidata</a>` : ""
        ].filter(Boolean).join("");
        return links || `<span class="status-line">Sin links asociados.</span>`;
      }

      function metadataEditor(item) {
        const rows = [
          ["Titulo", "title", "text"],
          ["Original", "original_title", "text"],
          ["Español", "spanish_title", "text"],
          ["Inglés", "english_title", "text"],
          ["Alternativos", "alternative_titles", "text"],
          ["Tipo", "kind", "kind"],
          ["Año", "year", "text"],
          ["Descripción", "description", "textarea"],
          ["Generos", "genres", "text"],
          ["Directores", "directors", "text"],
          ["Guionistas", "writers", "text"],
          ["Reparto", "cast", "text"],
          ["TMDB ID", "tmdb_id", "text"],
          ["Imagen landscape", "backdrop_image", "text"]
        ];
        return `<div class="metadata-editor" data-detail-form="metadata" data-id="${escapeAttr(item.id)}">
          ${rows.map(([label, field, control]) => metadataEditorRow(item, label, field, control)).join("")}
          <div class="metadata-actions">
            <button type="button" data-click="save-metadata" data-detail-save data-id="${escapeAttr(item.id)}">Guardar metadata</button>
            <span class="status-line" data-metadata-status></span>
          </div>
        </div>`;
      }

      function metadataEditorRow(item, label, field, control) {
        const listFields = ["alternative_titles", "genres", "directors", "writers", "cast"];
        const value = listFields.includes(field) ? asList(item[field]).join(", ") : String(item[field] || "");
        const locked = asList(item.locked_fields).includes(field);
        const origin = item.metadata_sources?.[field] || {};
        const source = origin.source
          ? `${origin.source}${origin.inferred ? " (inferida)" : ""}${origin.updated_at ? ` | ${String(origin.updated_at).slice(0, 10)}` : ""}`
          : "sin procedencia";
        const input = control === "textarea"
          ? `<textarea data-metadata-field="${field}" rows="4">${escapeHtml(value)}</textarea>`
          : control === "kind"
            ? `<select data-metadata-field="${field}">${["pelicula", "serie", "anime", "documental"].map((option) => `<option value="${option}" ${option === value ? "selected" : ""}>${option}</option>`).join("")}</select>`
            : `<input data-metadata-field="${field}" type="text" value="${escapeAttr(value)}">`;
        return `<div class="metadata-row">
          <label>${escapeHtml(label)}${input}</label>
          <div class="metadata-control">
            <span class="metadata-origin">${escapeHtml(source)}</span>
            <label class="lock-control"><input data-lock-field="${field}" type="checkbox" ${locked ? "checked" : ""}> Bloquear</label>
          </div>
        </div>`;
      }

      function primeDetailForms() {
        fields.detailBody.querySelectorAll("[data-detail-form]").forEach((form) => {
          form.dataset.initial = serializeDetailForm(form);
        });
      }

      function serializeDetailForm(form) {
        const values = [...form.querySelectorAll("input, select, textarea")].map((control, index) => {
          const key = control.dataset.metadataField
            || control.dataset.lockField
            || control.name
            || String(index);
          const value = control.type === "checkbox" ? control.checked : control.value;
          return [key, value];
        });
        return JSON.stringify(values);
      }

      function handleDetailFormMutation(event) {
        const form = event.target.closest("[data-detail-form]");
        if (!form) return;
        const scope = form.dataset.detailForm;
        if (serializeDetailForm(form) === form.dataset.initial) detailDirtyScopes.delete(scope);
        else detailDirtyScopes.add(scope);
        syncDetailFeedback();
      }

      function hasUnsavedDetailChanges() {
        return detailDirtyScopes.size > 0;
      }

      function handleBeforeUnload(event) {
        if (!hasUnsavedDetailChanges()) return;
        event.preventDefault();
        event.returnValue = "";
      }

      function setDetailFeedback(message, tone = "", timeout = 2400) {
        if (detailFeedbackTimer) window.clearTimeout(detailFeedbackTimer);
        detailFeedbackState = { message, tone };
        syncDetailFeedback();
        if (timeout > 0) {
          detailFeedbackTimer = window.setTimeout(() => {
            detailFeedbackState = { message: "", tone: "" };
            detailFeedbackTimer = null;
            syncDetailFeedback();
          }, timeout);
        }
      }

      function clearDetailFeedback() {
        if (detailFeedbackTimer) window.clearTimeout(detailFeedbackTimer);
        detailFeedbackTimer = null;
        detailFeedbackState = { message: "", tone: "" };
        syncDetailFeedback();
      }

      function syncDetailFeedback() {
        if (!fields.detailFeedback) return;
        const dirty = hasUnsavedDetailChanges();
        fields.detailFeedback.textContent = dirty
          ? `Cambios sin guardar · ${detailDirtyScopes.size}`
          : detailFeedbackState.message;
        fields.detailFeedback.dataset.tone = dirty ? "dirty" : detailFeedbackState.tone;
        fields.detailDrawer.classList.toggle("has-dirty-detail", dirty);
      }

      function requestDetailTransition(action) {
        if (!hasUnsavedDetailChanges()) {
          action();
          return;
        }
        pendingDetailTransition = action;
        if (!fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.showModal();
        requestAnimationFrame(() => fields.saveDetailChanges.focus());
      }

      function keepEditingDetail() {
        pendingDetailTransition = null;
        if (fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.close();
        if (selectedDetailId) syncRoute({ movie: selectedDetailId }, "replace");
        requestAnimationFrame(() => fields.detailBody.querySelector("[data-detail-form] input, [data-detail-form] select, [data-detail-form] textarea")?.focus());
      }

      function discardDetailChanges() {
        const transition = pendingDetailTransition;
        pendingDetailTransition = null;
        detailDirtyScopes.clear();
        detailPersonalEditing = false;
        if (fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.close();
        syncDetailFeedback();
        transition?.();
      }

      async function saveDetailChanges() {
        fields.saveDetailChanges.disabled = true;
        fields.keepEditingDetail.disabled = true;
        fields.discardDetailChanges.disabled = true;
        setDetailFeedback("Guardando cambios…", "working", 0);
        const saved = await saveDirtyDetailForms();
        fields.saveDetailChanges.disabled = false;
        fields.keepEditingDetail.disabled = false;
        fields.discardDetailChanges.disabled = false;
        if (!saved) return;
        const transition = pendingDetailTransition;
        pendingDetailTransition = null;
        if (fields.unsavedDetailDialog.open) fields.unsavedDetailDialog.close();
        detailPersonalEditing = false;
        setDetailFeedback("Cambios guardados", "success");
        await loadCatalog();
        transition?.();
      }

      async function saveDirtyDetailForms() {
        const personal = fields.detailBody.querySelector("[data-detail-form='personal']");
        const metadata = fields.detailBody.querySelector("[data-detail-form='metadata']");
        if (detailDirtyScopes.has("personal") && !await persistPersonalForm(personal, selectedDetailId)) return false;
        detailDirtyScopes.delete("personal");
        if (detailDirtyScopes.has("metadata") && !await persistMetadataForm(metadata, selectedDetailId)) return false;
        detailDirtyScopes.delete("metadata");
        syncDetailFeedback();
        return true;
      }

      function cachedImageSrc(url) {
        return `/image-cache?url=${encodeURIComponent(url)}`;
      }

      function emptyExternalSourceSearchStates() {
        return Object.fromEntries(EXTERNAL_SEARCH_SOURCES.map((source) => [source, {
          status: "idle",
          count: 0,
          error: ""
        }]));
      }

      function requestedExternalSources(source, includeExternal) {
        if (!includeExternal) return [];
        return source === "all" || !EXTERNAL_SEARCH_SOURCES.includes(source)
          ? [...EXTERNAL_SEARCH_SOURCES]
          : [source];
      }

      function setSearchBusy(busy) {
        fields.searchButton.disabled = busy;
        fields.searchButton.textContent = busy ? "Buscando..." : "Buscar";
        fields.searchConsole.setAttribute("aria-busy", String(busy));
        if (busy) fields.searchButton.setAttribute("aria-busy", "true");
        else fields.searchButton.removeAttribute("aria-busy");
      }

      function isCurrentSearch(controller) {
        return externalSearchController === controller && !controller.signal.aborted;
      }

      function mergeExternalHealth(payload, source) {
        const incoming = payload?.external || {};
        externalHealth = {
          ...externalHealth,
          sources: {
            ...(externalHealth?.sources || {}),
            ...(incoming.sources?.[source] ? { [source]: incoming.sources[source] } : {})
          },
          cache: incoming.cache || externalHealth?.cache || {}
        };
      }

      function replaceExternalSourceResults(source, results) {
        const rows = (Array.isArray(results) ? results : []).map((result) => ({
          ...result,
          source: result.source || source
        }));
        manualResults = manualResults
          .filter((result) => result.source !== source)
          .concat(rows);
        manualSourceVisibleCounts[source] = SEARCH_PAGE_SIZE;
        externalSourcesLastUsed = [...new Set(manualResults.map((result) => result.source || "").filter(Boolean))];
        return rows;
      }

      function updateExternalSearchSummary() {
        const states = externalSourcesAttempted.map((source) => externalSourceSearchStates[source] || {});
        const loading = states.filter((state) => state.status === "loading").length;
        const failed = states.filter((state) => ["error", "timeout"].includes(state.status)).length;
        const completed = states.length - loading;
        const count = manualResults.length;
        if (!states.length) {
          fields.manualSearchStatus.textContent = "";
        } else if (loading) {
          fields.manualSearchStatus.textContent = `${completed}/${states.length} fuentes listas · ${count} ${count === 1 ? "resultado" : "resultados"}`;
        } else if (count) {
          fields.manualSearchStatus.textContent = `${count} ${count === 1 ? "resultado" : "resultados"}${failed ? ` · ${failed} ${failed === 1 ? "fuente incompleta" : "fuentes incompletas"}` : ""}`;
        } else if (failed) {
          fields.manualSearchStatus.textContent = "No pudimos completar las fuentes externas. Podés reintentarlas por separado.";
        } else {
          fields.manualSearchStatus.textContent = "Sin resultados externos";
        }
      }

      async function loadLocalSearchResults(query, controller) {
        try {
          const response = await apiFetch(`/api/search?q=${encodeURIComponent(query)}&external=false&catalog=true`, {
            signal: controller.signal
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          if (!isCurrentSearch(controller)) return;
          catalogMergeResults = payload.catalog?.results || [];
          catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeKicker.textContent = "Tu catálogo";
          fields.catalogMergeTitle.textContent = "Coincidencias locales";
          fields.catalogMergeStatus.textContent = `${catalogMergeResults.length} ${catalogMergeResults.length === 1 ? "obra encontrada" : "obras encontradas"}, sin aplicar los filtros de la estantería.`;
          renderCatalogMergeResults();
        } catch (error) {
          if (error.name === "AbortError" || !isCurrentSearch(controller)) return;
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeStatus.textContent = "No pudimos actualizar las coincidencias locales. Tu colección sigue disponible.";
          console.error("[catalog-viewer] local search failed", error);
        }
      }

      async function loadExternalSourceResults(query, source, controller) {
        const sourceController = new AbortController();
        let timedOut = false;
        const abortSource = () => sourceController.abort();
        controller.signal.addEventListener("abort", abortSource, { once: true });
        const timeoutId = window.setTimeout(() => {
          timedOut = true;
          sourceController.abort();
        }, SEARCH_TIMEOUT_MS);
        try {
          const response = await apiFetch(`/api/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(source)}&external=true&catalog=false`, {
            signal: sourceController.signal
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          if (!isCurrentSearch(controller)) return;
          mergeExternalHealth(payload, source);
          const rows = replaceExternalSourceResults(source, payload.results || []);
          const health = payload.external?.sources?.[source] || {};
          externalSourceSearchStates[source] = rows.length
            ? { status: "ready", count: rows.length, error: "" }
            : health.status === "error"
              ? { status: "error", count: 0, error: health.error || "source_error" }
              : { status: "empty", count: 0, error: "" };
        } catch (error) {
          if (!isCurrentSearch(controller)) return;
          replaceExternalSourceResults(source, []);
          externalSourceSearchStates[source] = timedOut
            ? { status: "timeout", count: 0, error: "timeout" }
            : { status: "error", count: 0, error: error.message || "source_error" };
          if (error.name !== "AbortError") console.error(`[catalog-viewer] ${source} search failed`, error);
        } finally {
          window.clearTimeout(timeoutId);
          controller.signal.removeEventListener("abort", abortSource);
          if (isCurrentSearch(controller)) {
            updateExternalSearchSummary();
            renderManualResults();
            renderDatabaseMenu();
          }
        }
      }

      async function searchManual(source = "all", statusPrefix = "") {
        const query = fields.query.value.trim();
        if (query.length < 2) return;
        const includeExternal = fields.externalSource.checked;
        if (externalSearchController) externalSearchController.abort();
        const controller = new AbortController();
        externalSearchController = controller;
        const sources = requestedExternalSources(source, includeExternal);
        manualSearchSource = source;
        manualResults = [];
        selectedManualIndex = null;
        manualVisibleCount = SEARCH_PAGE_SIZE;
        manualSourceVisibleCounts = {};
        externalSourcesAttempted = [...sources];
        externalSourcesLastUsed = [];
        externalSourceSearchStates = emptyExternalSourceSearchStates();
        sources.forEach((name) => {
          externalSourceSearchStates[name] = { status: "loading", count: 0, error: "" };
        });
        fields.externalSearchSection.classList.toggle("active", includeExternal);
        fields.manualSearchStatus.textContent = statusPrefix || (includeExternal ? "Consultando fuentes…" : "");
        fields.manualSearchResults.innerHTML = "";
        setSearchBusy(true);
        if (includeExternal) renderManualResults();
        setSearchState(
          "searching",
          collectionSearchMode === "browse"
            ? includeExternal
              ? `Buscando “${query}” en tu catálogo y fuentes externas…`
              : `Buscando “${query}” en tu catálogo…`
            : comparisonSearchMessage()
        );
        const tasks = [];
        if (collectionSearchMode === "browse") tasks.push(loadLocalSearchResults(query, controller));
        sources.forEach((name) => tasks.push(loadExternalSourceResults(query, name, controller)));
        try {
          await Promise.allSettled(tasks);
          if (!isCurrentSearch(controller)) return;
          updateExternalSearchSummary();
          setSearchState(
            "results",
            collectionSearchMode === "browse" ? collectionSearchMessage() : comparisonSearchMessage()
          );
          if (includeExternal) renderManualResults();
          renderDatabaseMenu();
        } finally {
          if (externalSearchController === controller) {
            externalSearchController = null;
            setSearchBusy(false);
            if (includeExternal) renderManualResults();
          }
        }
      }

      async function retryExternalSource(source) {
        const query = fields.query.value.trim();
        if (!EXTERNAL_SEARCH_SOURCES.includes(source) || query.length < 2 || externalSearchController) return;
        const controller = new AbortController();
        externalSearchController = controller;
        if (!externalSourcesAttempted.includes(source)) externalSourcesAttempted.push(source);
        replaceExternalSourceResults(source, []);
        externalSourceSearchStates[source] = { status: "loading", count: 0, error: "" };
        fields.externalSearchSection.classList.add("active");
        setSearchBusy(true);
        updateExternalSearchSummary();
        renderManualResults();
        setSearchState("searching", `Reintentando ${EXTERNAL_SOURCE_LABELS[source][0]} para “${query}”…`);
        try {
          await loadExternalSourceResults(query, source, controller);
          if (!isCurrentSearch(controller)) return;
          updateExternalSearchSummary();
          setSearchState(
            "results",
            collectionSearchMode === "browse" ? collectionSearchMessage() : comparisonSearchMessage()
          );
        } finally {
          if (externalSearchController === controller) {
            externalSearchController = null;
            setSearchBusy(false);
            renderManualResults();
            renderDatabaseMenu();
          }
        }
      }

      function cancelExternalSearch() {
        if (!externalSearchController) return;
        const controller = externalSearchController;
        externalSearchController = null;
        controller.abort();
        externalSourcesAttempted.forEach((source) => {
          if (externalSourceSearchStates[source]?.status === "loading") {
            externalSourceSearchStates[source] = { status: "canceled", count: 0, error: "" };
          }
        });
        setSearchBusy(false);
        fields.manualSearchStatus.textContent = "Búsqueda externa cancelada.";
        renderManualResults();
        setSearchState(
          "results",
          collectionSearchMode === "browse" ? collectionSearchMessage() : comparisonSearchMessage()
        );
      }

      function clearManualSearch({ focus = true, updateHistory = true, resetExternal = false } = {}) {
        const hadSearch = Boolean(activeQuery || fields.query.value.trim());
        fields.collectionUtilityMenu.open = false;
        if (externalSearchController) externalSearchController.abort();
        externalSearchController = null;
        setSearchBusy(false);
        manualResults = [];
        manualSourceVisibleCounts = {};
        catalogMergeResults = [];
        selectedManualIndex = null;
        selectedExistingIdForSearch = null;
        manualSearchSource = "all";
        activeQuery = "";
        setCollectionSearchMode("browse");
        manualVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        externalSourceSearchStates = emptyExternalSourceSearchStates();
        if (resetExternal) fields.externalSource.checked = false;
        fields.query.value = "";
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        fields.catalogMergeKicker.textContent = "Comparación";
        fields.catalogMergeTitle.textContent = "Entrada de la colección";
        fields.reviewPrevious.hidden = true;
        fields.reviewNext.hidden = true;
        setSearchState("idle");
        if (updateHistory && hadSearch) syncCollectionRoute("push");
        render();
        renderDatabaseMenu();
        if (focus) fields.query.focus();
      }

      async function prepareManualMerge(index) {
        selectedManualIndex = index;
        if (selectedExistingIdForSearch) {
          setCollectionSearchMode("link");
          const item = items.find((entry) => entry.id === selectedExistingIdForSearch);
          catalogMergeResults = item ? [item] : [];
          catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeKicker.textContent = "Comparación";
          fields.catalogMergeTitle.textContent = "Entrada seleccionada";
          fields.catalogMergeStatus.textContent = item ? "Entrada seleccionada para comparar." : "No se encontró la entrada seleccionada.";
          renderCatalogMergeResults();
          setSearchState("results", comparisonSearchMessage());
          fields.searchContext.scrollIntoView({ behavior: "smooth", block: "start" });
          return;
        }
        const result = manualResults[index] || {};
        setCollectionSearchMode("compare");
        fields.query.value = [result.title, result.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        render();
        syncCollectionRoute("push");
        await searchCatalogForMerge("", result);
        setSearchState("results", comparisonSearchMessage());
        fields.searchContext.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      async function searchCatalogForMerge(queryValue = "", incomingResult = null) {
        const query = (queryValue || fields.query.value).trim();
        if (!query) return;
        setCollectionSearchMode("compare");
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeKicker.textContent = "Comparación";
        fields.catalogMergeTitle.textContent = "Elegí una entrada local";
        fields.catalogMergeStatus.textContent = "Enriqueciendo la opción externa y comparando todos sus títulos…";
        fields.catalogMergeResults.innerHTML = "";
        try {
          const response = incomingResult
            ? await apiFetch("/api/search/catalog-candidates", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ result: incomingResult })
              })
            : await apiFetch(`/api/search?q=${encodeURIComponent(query)}&external=false`);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          catalogMergeResults = incomingResult
            ? payload.results || []
            : payload.catalog?.results || [];
          fields.catalogMergeStatus.textContent = `${catalogMergeResults.length} ${catalogMergeResults.length === 1 ? "entrada encontrada" : "entradas encontradas"}. Las coincidencias seguras aparecen primero.`;
          renderCatalogMergeResults();
        } catch (error) {
          catalogMergeResults = [];
          fields.catalogMergeStatus.textContent = "No pudimos comparar con el catálogo. Reintentá desde el resultado externo.";
          console.error("[catalog-viewer] catalog candidate search failed", error);
        }
      }

      function renderManualResults() {
        const grouped = Object.fromEntries(EXTERNAL_SEARCH_SOURCES.map((source) => [source, []]));
        manualResults.forEach((result, index) => {
          if (grouped[result.source]) grouped[result.source].push({ result, index });
        });
        fields.manualSearchResults.innerHTML = Object.entries(EXTERNAL_SOURCE_LABELS).map(([source, labels]) => {
          const rows = grouped[source];
          const state = externalSourceSearchStates[source] || { status: "idle", count: 0, error: "" };
          const visibleCount = manualSourceVisibleCounts[source] || SEARCH_PAGE_SIZE;
          const visible = rows.slice(0, visibleCount);
          const more = rows.length > visibleCount
            ? `<button class="load-more source-load-more" type="button" data-click="show-more-manual" data-source="${source}">Cargar más de ${escapeHtml(labels[0])} (${rows.length - visibleCount})</button>`
            : "";
          return `<section class="search-source-group" data-source-group="${source}" aria-busy="${state.status === "loading"}">
            <header class="search-source-heading">
              <div><strong>${escapeHtml(labels[0])}</strong><span>${escapeHtml(labels[1])}</span></div>
              <span>${externalSourceStateLabel(state, rows.length)}</span>
            </header>
            ${rows.length
              ? `<div class="search-source-track">${visible.map(({ result, index }) => searchResult(result, index)).join("")}</div>${more}`
              : externalSourceFeedback(source, state)}
          </section>`;
        }).join("");
      }

      function externalSourceStateLabel(state, count) {
        if (state.status === "loading") return "Consultando…";
        if (state.status === "timeout") return "Tiempo agotado";
        if (state.status === "error") return "No disponible";
        if (state.status === "canceled") return "Cancelada";
        if (state.status === "idle") return "Sin consultar";
        return `${count} ${count === 1 ? "resultado" : "resultados"}`;
      }

      function externalSourceFeedback(source, state) {
        const label = EXTERNAL_SOURCE_LABELS[source]?.[0] || source;
        if (state.status === "loading") {
          return `<div class="search-source-feedback is-loading" role="status">
            <span class="source-search-spinner" aria-hidden="true"></span>
            <span>Consultando ${escapeHtml(label)}…</span>
          </div>`;
        }
        if (["error", "timeout"].includes(state.status)) {
          const message = state.status === "timeout"
            ? `${label} tardó más de ${SEARCH_TIMEOUT_MS / 1000} segundos.`
            : `${label} no respondió correctamente.`;
          return `<div class="search-source-feedback is-error" role="status">
            <span>${escapeHtml(message)}</span>
            <button class="quiet-action source-retry" type="button" data-click="retry-external-source" data-source="${source}" ${externalSearchController ? "disabled" : ""}>Reintentar</button>
          </div>`;
        }
        if (state.status === "canceled") {
          return `<p class="search-source-empty">Consulta cancelada.</p>`;
        }
        if (state.status === "idle") {
          return `<p class="search-source-empty">Esta fuente no fue consultada.</p>`;
        }
        return `<p class="search-source-empty">Sin coincidencias en esta fuente.</p>`;
      }

      function renderCatalogMergeResults() {
        const visible = catalogMergeResults.slice(0, catalogMergeVisibleCount);
        const more = catalogMergeResults.length > catalogMergeVisibleCount
          ? `<button class="load-more" type="button" data-click="show-more-catalog">Cargar más (${catalogMergeResults.length - catalogMergeVisibleCount})</button>`
          : "";
        fields.catalogMergeResults.innerHTML = visible.length
          ? `<div class="search-source-track">${visible.map(catalogMergeResult).join("")}</div>${more}`
          : `<p class="search-source-empty">No encontramos una coincidencia local. Probá otro título o agregá la obra como nueva.</p>`;
      }

      function showMoreManualResults(source = "") {
        if (source) manualSourceVisibleCounts[source] = (manualSourceVisibleCounts[source] || SEARCH_PAGE_SIZE) + SEARCH_PAGE_SIZE;
        else manualVisibleCount += SEARCH_PAGE_SIZE;
        renderManualResults();
      }

      function showMoreCatalogResults() {
        catalogMergeVisibleCount += SEARCH_PAGE_SIZE;
        renderCatalogMergeResults();
      }

      async function startWikiReview() {
        wikiReviewQueue = items.filter((item) => !hasExternalLink(item));
        wikiReviewIndex = 0;
        if (!wikiReviewQueue.length) {
          fields.wikiReviewStatus.textContent = "No quedan entradas sin link.";
          fields.reviewPrevious.hidden = true;
          fields.reviewNext.hidden = true;
          return;
        }
        await reviewCurrentWikiItem();
      }

      async function previousWikiReview() {
        if (!wikiReviewQueue.length) await startWikiReview();
        if (!wikiReviewQueue.length) return;
        wikiReviewIndex = Math.max(0, wikiReviewIndex - 1);
        await reviewCurrentWikiItem();
      }

      async function nextWikiReview() {
        if (!wikiReviewQueue.length) await startWikiReview();
        if (!wikiReviewQueue.length) return;
        wikiReviewIndex = Math.min(wikiReviewQueue.length - 1, wikiReviewIndex + 1);
        await reviewCurrentWikiItem();
      }

      async function reviewCurrentWikiItem() {
        const item = wikiReviewQueue[wikiReviewIndex];
        if (!item) return;
        fields.wikiReviewStatus.textContent = `${wikiReviewIndex + 1}/${wikiReviewQueue.length}: ${item.title || item.local_name || "Sin titulo"}`;
        fields.reviewPrevious.hidden = false;
        fields.reviewNext.hidden = false;
        fields.reviewPrevious.disabled = wikiReviewIndex === 0;
        fields.reviewNext.disabled = wikiReviewIndex >= wikiReviewQueue.length - 1;
        await findLinkForItem(item);
      }

      function catalogMergeResult(item, index) {
        const incoming = selectedManualIndex === null ? null : manualResults[selectedManualIndex];
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || item.local_name || "";
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        return `<article class="search-result compact-result">
          ${resultMedia(shownTitle || item.local_name, item.page_image, index < 6)}
          <div class="result-body">
            <h3 class="${titleSizeClass(shownTitle)}">${escapeHtml(shownTitle || "Sin titulo")}</h3>
            ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
            <div class="meta">
              ${meta(item.year)}${meta(item.kind)}${meta(item.source)}${meta(firstListValue(item.genres))}${meta(firstListValue(item.directors))}
            </div>
            <div class="card-badges">
              ${item._search?.reason ? `<span class="pill match-reason">${escapeHtml(searchReasonLabel(item._search))}</span>` : ""}
              <span class="pill ${hasExternalLink(item) ? "good" : "muted"}">${hasExternalLink(item) ? "con link" : "sin link"}</span>
              <span class="pill ${isInCatalog(item.en_catalogo) ? "good" : "muted"}">${isInCatalog(item.en_catalogo) ? "disponible: sí" : "disponible: no"}</span>
            </div>
            ${searchDescription(summary, "catalog", item.id)}
            <div class="result-actions">
              <button class="action-primary ${incoming ? "" : "span-all"}" type="button" data-click="open-detail" data-id="${escapeAttr(item.id)}">Detalle</button>
              ${incoming ? `<button class="action-secondary" type="button" data-click="merge-result" data-index="${selectedManualIndex}" data-id="${escapeAttr(item.id)}">Combinar</button>` : ""}
              ${item.url ? `<a class="action-secondary span-all" href="${escapeAttr(item.url)}" target="_blank" rel="noreferrer">Abrir link</a>` : ""}
            </div>
          </div>
        </article>`;
      }

      function searchResult(result, index) {
        const description = result.description || result.wikipedia_extract || "";
        const similarity = selectedExistingIdForSearch ? candidateSimilarity(result) : "";
        const primaryAction = selectedExistingIdForSearch ? "Combinar" : "Agregar";
        const shownTitle = displayTitle(result);
        const subtitle = titleSubtitle(result);
        return `<article class="search-result compact-result">
          ${resultMedia(shownTitle, result.page_image, index < 6)}
          <div class="result-body">
            <h3 class="${titleSizeClass(shownTitle)}">${escapeHtml(shownTitle || "Sin titulo")}</h3>
            ${subtitle ? `<div class="meta">${meta(subtitle)}</div>` : ""}
            <div class="meta">
              ${meta(result.source)}${meta(result.year)}${meta(firstListValue(result.genres))}${meta(firstListValue(result.directors))}${meta(result.url ? new URL(result.url).hostname.replace(/^www\\./, "") : "")}${meta(similarity)}
            </div>
            <div class="card-badges">
              <span class="pill good">${escapeHtml(result.source || "externo")}</span>
              <span class="pill ${result.url ? "good" : "muted"}">${result.url ? "con link" : "sin link"}</span>
            </div>
            ${searchDescription(description, "manual", index)}
            <div class="result-actions">
              <button class="action-primary" data-click="add-result" data-index="${index}">${primaryAction}</button>
              <button class="action-secondary" type="button" data-click="prepare-merge" data-index="${index}">Comparar</button>
              ${result.url ? `<a class="action-secondary span-all" href="${escapeAttr(result.url)}" target="_blank" rel="noreferrer">Detalle</a>` : ""}
            </div>
          </div>
        </article>`;
      }

      function resultMedia(title, imageUrl, priority = false) {
        const placeholder = `<div class="result-placeholder" aria-hidden="true">${escapeHtml((title || "Sin imagen").slice(0, 24))}</div>`;
        if (!imageUrl) return `<div class="result-media-frame">${placeholder}</div>`;
        return `<div class="result-media-frame">
          <img class="result-media" data-poster-image src="${escapeAttr(cachedImageSrc(imageUrl))}" alt="" loading="lazy" fetchpriority="${priority ? "high" : "auto"}" decoding="async">
          ${placeholder}
        </div>`;
      }

      function searchDescription(description, collection, key) {
        if (!description) return "";
        const text = String(description).trim();
        const more = text.length > 90
          ? `<button class="description-more" type="button" data-click="show-description" data-collection="${escapeAttr(collection)}" data-key="${escapeAttr(key)}">Ver más</button>`
          : "";
        return `<p class="result-summary">${escapeHtml(text)}</p>${more}`;
      }

      function openSearchDescription(collection, key) {
        const item = collection === "manual"
          ? manualResults[Number(key)]
          : items.find((entry) => entry.id === key);
        if (!item) return;
        const title = displayTitle(item) || "Descripción";
        const description = item.wikipedia_extract || item.description || item.notes || item.review || "Sin descripción.";
        descriptionReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        fields.descriptionDialogTitle.textContent = title;
        fields.descriptionDialogText.textContent = description;
        fields.descriptionDialog.showModal();
        fields.closeDescriptionDialog.focus();
      }

      function closeDescriptionDialog() {
        if (fields.descriptionDialog.open) fields.descriptionDialog.close();
      }

      function restoreDescriptionFocus() {
        const target = descriptionReturnFocus;
        descriptionReturnFocus = null;
        if (target?.isConnected) target.focus({ preventScroll: true });
      }

      function candidateSimilarity(result) {
        const existing = items.find((entry) => entry.id === selectedExistingIdForSearch);
        if (!existing) return "";
        let score = bestTitleSimilarity(existing, result);
        if (existing.year && String(existing.year) === String(result.year || "")) score = Math.min(100, score + 20);
        return `similitud: ${score}%`;
      }

      function searchReasonLabel(search = {}) {
        const labels = {
          shared_external_url: "mismo enlace",
          shared_wikidata_id: "mismo Wikidata",
          exact_title_year: "título y año exactos",
          exact_title_missing_year: "título exacto; falta año",
          exact_title_year_mismatch: "título exacto; año distinto",
          exact_title_kind_mismatch: "título exacto; tipo distinto",
          similar_title_requires_review: "título similar",
          insufficient_evidence: "coincidencia posible"
        };
        if (labels[search.reason]) return labels[search.reason];
        const fieldLabels = {
          title: "título",
          original_title: "título original",
          spanish_title: "título en español",
          english_title: "título en inglés",
          alternative_titles: "nombre alternativo",
          local_file: "archivo local",
          external_id: "identificador externo",
          external_link: "enlace externo",
          director: "dirección"
        };
        return fieldLabels[search.matched_field] || "coincidencia local";
      }

      function bestTitleSimilarity(leftItem, rightItem) {
        const leftTitles = titleSearchValues(leftItem).map(normalizeText).filter(Boolean);
        const rightTitles = titleSearchValues(rightItem).map(normalizeText).filter(Boolean);
        let best = 0;
        for (const leftTitle of leftTitles) {
          for (const rightTitle of rightTitles) {
            const leftTerms = new Set(leftTitle.split(/\s+/).filter(Boolean));
            const rightTerms = new Set(rightTitle.split(/\s+/).filter(Boolean));
            const shared = [...leftTerms].filter((term) => rightTerms.has(term)).length;
            const total = Math.max(leftTerms.size, rightTerms.size, 1);
            best = Math.max(best, Math.round((shared / total) * 100));
          }
        }
        return best;
      }

      async function addSearchResult(index) {
        const cards = [...fields.manualSearchResults.querySelectorAll("[data-index]")];
        const button = cards.find((element) => Number(element.dataset.index) === index);
        if (!button) return;
        const targetId = selectedExistingIdForSearch;
        const idleLabel = targetId ? "Combinar" : "Agregar";
        let completed = false;
        button.disabled = true;
        button.textContent = targetId ? "Preparando..." : "Agregando...";
        try {
          if (targetId) {
            if (!isExternalResult(manualResults[index])) {
              reportExternalResultProblem("Ese resultado no tiene un enlace reconocido. Elegí una opción de Wikipedia, IMDb o FilmAffinity.");
              return;
            }
            await mergeSearchResult(index, targetId);
            return;
          }
          const response = await apiFetch("/api/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(manualResults[index])
          });
          const payload = await response.json();
          if (payload.reason === "possible_duplicate") {
            button.textContent = idleLabel;
            showDuplicateChoice(index, payload.candidates || []);
            return;
          }
          if (!response.ok || (!payload.ok && payload.reason !== "duplicate")) {
            throw new Error(payload.reason || `HTTP ${response.status}`);
          }
          completed = true;
          button.textContent = payload.reason === "duplicate" ? "Ya existe" : "Agregado";
          await load();
          if (payload.background_enrichment === "scheduled") {
            window.setTimeout(() => load(), 12000);
          }
        } catch (error) {
          console.error("[catalog-viewer] add result failed", error);
          reportExternalResultProblem("No pudimos guardar ese resultado. Reintentá desde esta búsqueda.");
        } finally {
          if (button.isConnected) {
            button.disabled = completed;
            if (["Preparando...", "Agregando..."].includes(button.textContent)) button.textContent = idleLabel;
          }
        }
      }

      function showDuplicateChoice(index, candidates) {
        const blocks = candidates.map((candidate) => `
          <div>
            <strong>${escapeHtml(candidate.title || "Sin titulo")}</strong>
            <div class="meta">
              ${meta(candidate.year)}${meta(candidate.source)}${meta(firstListValue(candidate.genres))}${meta(firstListValue(candidate.directors))}${meta(isInCatalog(candidate.en_catalogo) ? "disponibilidad manual: sí" : "disponibilidad manual: no")}
            </div>
          </div>
          <div class="duplicate-actions">
            <button data-click="merge-result" data-index="${index}" data-id="${escapeAttr(candidate.id)}">Combinar</button>
            ${candidate.url ? `<a href="${escapeAttr(candidate.url)}" target="_blank" rel="noreferrer">Ver existente</a>` : ""}
          </div>
        `).join("");
        fields.manualSearchResults.insertAdjacentHTML("afterbegin", `
          <section class="duplicate-box">
            <strong>Posible duplicado encontrado</strong>
            <span>Ya existe una entrada con titulo y año parecidos. Podés combinarla, agregar igual o cancelar.</span>
            ${blocks}
            <div class="duplicate-actions">
              <button data-click="force-add" data-index="${index}">Agregar igual</button>
              <button data-click="run-search">Cancelar</button>
            </div>
          </section>
        `);
      }

      async function mergeSearchResult(index, targetId) {
        if (!isExternalResult(manualResults[index])) {
          reportExternalResultProblem("Ese resultado no se puede comparar porque no tiene un enlace externo reconocido.");
          return;
        }
        await openExternalMergeComparator(index, targetId);
      }

      function reportExternalResultProblem(message) {
        fields.manualSearchStatus.textContent = message;
        setSearchState("error", `${message} La colección no fue modificada.`);
      }

      async function forceAddSearchResult(index) {
        await postAdd(manualResults[index], "force", "");
        await load();
        await runSearch();
      }

      async function postAdd(result, action, targetId) {
        const target = items.find((entry) => entry.id === targetId);
        return apiFetch("/api/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            result,
            action,
            target_id: targetId,
            target_source_file: target?._source_file || "",
            expected_source: ""
          })
        });
      }

      function normalizeText(value) {
        return String(value || "")
          .toLowerCase()
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .replace(/\([^)]*\)/g, " ")
          .replace(/[^a-z0-9]+/g, " ")
          .trim();
      }

      function matchesSearchText(value, query) {
        return matchesNormalizedSearchText(normalizeText(value), normalizeText(query));
      }

      function matchesNormalizedSearchText(normalizedValue, normalizedQuery) {
        if (!normalizedQuery || normalizedValue.includes(normalizedQuery)) return true;
        const words = normalizedValue.split(/\s+/).filter(Boolean);
        return normalizedQuery.split(/\s+/).filter(Boolean).every((term) => (
          words.some((word) => word.includes(term) || (term.length >= 5 && oneEditApart(word, term)))
        ));
      }

      function oneEditApart(left, right) {
        if (Math.abs(left.length - right.length) > 1) return false;
        let leftIndex = 0;
        let rightIndex = 0;
        let edits = 0;
        while (leftIndex < left.length && rightIndex < right.length) {
          if (left[leftIndex] === right[rightIndex]) {
            leftIndex += 1;
            rightIndex += 1;
            continue;
          }
          edits += 1;
          if (edits > 1) return false;
          if (left.length > right.length) leftIndex += 1;
          else if (right.length > left.length) rightIndex += 1;
          else {
            leftIndex += 1;
            rightIndex += 1;
          }
        }
        if (leftIndex < left.length || rightIndex < right.length) edits += 1;
        return edits <= 1;
      }

      async function deleteCatalogItem(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        const title = item?.title || item?.local_name || "Sin título";
        const confirmed = confirm(
          `¿Eliminar "${title}" del catálogo personal?\n\nNo se borrarán videos ni el inventario del servidor.`
        );
        if (!confirmed) return;
        const button = event.target.closest("[data-click='delete-item']");
        if (button) button.disabled = true;
        setDetailFeedback("Eliminando entrada…", "working", 0);
        try {
          const response = await apiFetch("/api/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              id,
              confirmed: true,
              source_file: item?._source_file || "",
              url: item?.url || "",
              title: item?.title || title,
              year: item?.year || "",
              local_name: item?.local_name || ""
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
          closeDetail({ restoreFocus: false, updateHistory: true, skipGuard: true });
          await load();
        } catch (error) {
          console.error("[catalog-viewer] delete failed", error);
          setDetailFeedback("No pudimos eliminar la entrada. Reintentá.", "error", 0);
        } finally {
          if (button?.isConnected) button.disabled = false;
        }
      }

      async function toggleWatched(event, id, currentStatus) {
        event.preventDefault();
        const nextStatus = currentStatus === "watched" ? "to_watch" : "watched";
        const item = items.find((entry) => entry.id === id);
        const detailAction = selectedDetailId === id;
        if (detailAction) setDetailFeedback("Guardando estado…", "working", 0);
        try {
          const response = await apiFetch("/api/status", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              id,
              status: nextStatus,
              watched_at: nextStatus === "watched" ? todayLocalDate() : item?.watched_at || "",
              source_file: item?._source_file || ""
            })
          });
          const payload = await response.json();
          if (!payload.ok) throw new Error(payload.reason || "No se pudo cambiar el estado");
          if (detailAction) setDetailFeedback(nextStatus === "watched" ? "Marcada como vista" : "Marcada como pendiente", "success");
          await load();
        } catch (error) {
          console.error("[catalog-viewer] status update failed", error);
          if (detailAction) setDetailFeedback("No pudimos guardar el estado. Reintentá.", "error", 0);
          else setSearchState("error", "No pudimos guardar el estado. Reintentá.");
        }
      }

      async function toggleCatalog(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        const manualValue = availabilityState(item).manual;
        const nextValue = !manualValue;
        const detailAction = selectedDetailId === id;
        if (detailAction) setDetailFeedback("Guardando disponibilidad…", "working", 0);
        try {
          const response = await apiFetch("/api/catalog", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, en_catalogo: nextValue, source_file: item?._source_file || "" })
          });
          const payload = await response.json();
          if (!payload.ok) throw new Error(payload.reason || "No se pudo cambiar el estado de catalogo");
          if (detailAction) {
            const message = nextValue
              ? "Disponibilidad personal declarada"
              : item._availability?.server
                ? "Declaración retirada; sigue disponible en el servidor"
                : "Disponibilidad personal retirada";
            setDetailFeedback(message, "success");
          }
          await load();
        } catch (error) {
          console.error("[catalog-viewer] catalog update failed", error);
          if (detailAction) setDetailFeedback("No pudimos guardar la disponibilidad. Reintentá.", "error", 0);
          else setSearchState("error", "No pudimos guardar la disponibilidad. Reintentá.");
        }
      }

      async function savePersonal(event, id) {
        event.preventDefault();
        const form = event.target.closest("[data-detail-form='personal']");
        if (!form) return;
        event.target.disabled = true;
        setDetailFeedback("Guardando registro…", "working", 0);
        const saved = await persistPersonalForm(form, id);
        event.target.disabled = false;
        if (!saved) return;
        detailDirtyScopes.delete("personal");
        detailPersonalEditing = false;
        setDetailFeedback("Registro guardado", "success");
        await load();
      }

      async function persistPersonalForm(form, id) {
        const item = items.find((entry) => entry.id === id);
        if (!item || !form) return false;
        const watchedAt = form.querySelector("[data-personal-watched-at]")?.value || "";
        const rating = normalizeRating(form.querySelector("[data-personal-rating]")?.value);
        const review = form.querySelector("[data-personal-review]")?.value || "";
        const ratingPrivacy = form.querySelector("[data-personal-rating-privacy]")?.value || "inherit";
        const reviewPrivacy = form.querySelector("[data-personal-review-privacy]")?.value || "inherit";
        const status = form.querySelector("[data-personal-status]");
        if (status) status.textContent = "Guardando…";
        try {
          const response = await apiFetch("/api/personal", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, watched_at: watchedAt, rating, review, source_file: item?._source_file || "" })
          });
          const payload = await response.json();
          if (!payload.ok) throw new Error(payload.reason || "No se pudo guardar");
          const privacyResponse = await apiFetch(`/api/privacy/items/${encodeURIComponent(id)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ rating: ratingPrivacy, review: reviewPrivacy })
          });
          const privacyPayload = await privacyResponse.json();
          if (!privacyResponse.ok || !privacyPayload.ok) {
            throw new Error(privacyPayload.reason || "No se pudo guardar la privacidad");
          }
          item._privacy = privacyPayload.privacy || { rating: ratingPrivacy, review: reviewPrivacy };
          if (status) status.textContent = "Guardado";
          form.dataset.initial = serializeDetailForm(form);
          return true;
        } catch (error) {
          console.error("[catalog-viewer] personal record update failed", error);
          if (status) status.textContent = "No se pudo guardar. Revisá los datos e intentá otra vez.";
          setDetailFeedback("Error al guardar el registro", "error", 0);
          return false;
        }
      }

      async function saveMetadata(event, id) {
        event.preventDefault();
        const editor = event.target.closest("[data-detail-form='metadata']");
        if (!editor) return;
        event.target.disabled = true;
        setDetailFeedback("Guardando metadata…", "working", 0);
        const saved = await persistMetadataForm(editor, id);
        event.target.disabled = false;
        if (!saved) return;
        detailDirtyScopes.delete("metadata");
        setDetailFeedback("Metadata guardada", "success");
        await load();
      }

      async function persistMetadataForm(editor, id) {
        const item = items.find((entry) => entry.id === id);
        if (!item || !editor) return false;
        const values = {};
        editor.querySelectorAll("[data-metadata-field]").forEach((control) => {
          values[control.dataset.metadataField] = control.value;
        });
        const locked = new Set(asList(item.locked_fields));
        editor.querySelectorAll("[data-lock-field]").forEach((control) => {
          if (control.checked) locked.add(control.dataset.lockField);
          else locked.delete(control.dataset.lockField);
        });
        const status = editor.querySelector("[data-metadata-status]");
        if (status) status.textContent = "Guardando...";
        try {
          const response = await apiFetch("/api/metadata", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              id,
              values,
              locked_fields: [...locked],
              source_file: item._source_file || ""
            })
          });
          const payload = await response.json();
          if (!payload.ok) throw new Error(payload.reason || "No se pudo guardar");
          if (status) status.textContent = "Guardada";
          editor.dataset.initial = serializeDetailForm(editor);
          return true;
        } catch (error) {
          console.error("[catalog-viewer] metadata update failed", error);
          if (status) status.textContent = "No se pudo guardar. Revisá los campos e intentá otra vez.";
          setDetailFeedback("Error al guardar la metadata", "error", 0);
          return false;
        }
      }

      async function findLinkForCatalog(event, id) {
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        if (fields.detailDrawer.open) closeDetail({ restoreFocus: false, updateHistory: false, skipGuard: true });
        await findLinkForItem(item);
      }

      async function findLinkForItem(item) {
        showView("catalog", { updateHistory: false, scroll: false });
        selectedExistingIdForSearch = item.id;
        selectedManualIndex = null;
        setCollectionSearchMode("link");
        fields.query.value = [item.title || item.local_name, item.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        fields.externalSource.checked = true;
        render();
        syncCollectionRoute("push");
        catalogMergeResults = [item];
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeKicker.textContent = "Comparación";
        fields.catalogMergeTitle.textContent = "Entrada seleccionada";
        fields.catalogMergeStatus.textContent = "Elegí un resultado externo y tocá Comparar para revisar diferencias.";
        renderCatalogMergeResults();
        await searchManual("all", "Buscando coincidencias en Wikipedia, IMDb y FilmAffinity...");
        fields.query.scrollIntoView({ behavior: "smooth", block: "center" });
      }

      function meta(value) {
        return value ? `<span>${escapeHtml(value)}</span>` : "";
      }

      function displayTitle(item) {
        const candidates = [
          item.spanish_title,
          item.title,
          item.original_title,
          item.english_title,
          item.wikipedia_title,
          ...asList(item.alternative_titles),
          item.local_name
        ].filter(Boolean);
        return candidates.find((value) => !isExternalIdTitle(value)) || candidates[0] || "";
      }

      function isExternalIdTitle(value) {
        const text = String(value || "").trim();
        return /^(tt|nm)\d{7,9}$/i.test(text) || /^film\d+$/i.test(text);
      }

      function titleSizeClass(value) {
        const text = String(value || "").trim();
        const length = [...text].length;
        const longestWord = Math.max(0, ...text.split(/\s+/).map((word) => [...word].length));
        if (longestWord > 18) return "title-ultra";
        if (longestWord > 12 || length > 72) return "title-xxlong";
        if (longestWord > 8 || length > 52) return "title-xlong";
        if (length > 34) return "title-long";
        if (length > 22) return "title-medium";
        return "title-short";
      }

      function titleSubtitle(item) {
        const shown = normalizeText(displayTitle(item));
        const values = [
          ["Original", item.original_title],
          ["Ingles", item.english_title],
          ["Base", item.title]
        ];
        const row = values.find(([, value]) => value && normalizeText(value) !== shown);
        return row ? `${row[0]}: ${row[1]}` : "";
      }

      function titleSearchValues(item) {
        return [
          item.title,
          item.original_title,
          item.spanish_title,
          item.english_title,
          ...(asList(item.alternative_titles)),
          item.wikipedia_title,
          item.local_name,
          ...localFiles(item).flatMap((file) => [file.name, file.path])
        ].filter(Boolean);
      }

      function localFiles(item) {
        return Array.isArray(item?.local_files)
          ? item.local_files.filter((file) => file && typeof file === "object")
          : [];
      }

      function localFilesText(item) {
        return localFiles(item)
          .map((file) => file.name || file.path || "")
          .filter(Boolean)
          .join(", ");
      }

      function localFileCountLabel(item) {
        const count = localFiles(item).length;
        return count ? `${count} archivo${count === 1 ? "" : "s"}` : "";
      }

      function asList(value) {
        if (Array.isArray(value)) return value.filter(Boolean);
        if (typeof value === "string") return value.split(",").map((entry) => entry.trim()).filter(Boolean);
        return [];
      }

      function firstListValue(value) {
        return asList(value)[0] || "";
      }

      function listText(value, limit) {
        const list = asList(value);
        if (!list.length) return "";
        const visible = list.slice(0, limit);
        const suffix = list.length > limit ? ` y ${list.length - limit} más` : "";
        return visible.join(", ") + suffix;
      }

      function isInCatalog(value) {
        return value === true || value === "si" || value === "sí" || value === "true";
      }

      function availabilityState(item) {
        const details = item?._availability || {};
        const manual = typeof details.manual === "boolean"
          ? details.manual
          : isInCatalog(item?.en_catalogo);
        const server = Boolean(details.server);
        const effective = typeof details.effective === "boolean"
          ? details.effective
          : Boolean(manual || server || isInCatalog(item?.en_catalogo));
        const fileCount = Math.max(0, Number(details.file_count || 0));
        const origin = server && manual
          ? "Servidor y declaración manual"
          : server
            ? "Inventario del servidor"
            : manual ? "Declaración manual" : "Sin procedencia asociada";
        return { effective, manual, server, fileCount, origin, details };
      }

      function hasHost(url, host) {
        try {
          const hostname = new URL(url).hostname.toLowerCase().replace(/\.$/, "");
          return hostname === host || hostname.endsWith(`.${host}`);
        } catch {
          return false;
        }
      }

      function hasExternalLink(item) {
        return hasHost(item?.url, "wikipedia.org")
          || hasHost(item?.url, "imdb.com")
          || hasHost(item?.url, "filmaffinity.com")
          || hasHost(item?.wikipedia_url, "wikipedia.org")
          || hasHost(item?.imdb_url, "imdb.com")
          || hasHost(item?.filmaffinity_url, "filmaffinity.com");
      }

      function isExternalResult(result) {
        return result?.source === "wikipedia"
          || result?.source === "imdb"
          || result?.source === "filmaffinity"
          || hasHost(result?.url, "wikipedia.org")
          || hasHost(result?.url, "imdb.com")
          || hasHost(result?.url, "filmaffinity.com")
          || hasHost(result?.wikipedia_url, "wikipedia.org")
          || hasHost(result?.imdb_url, "imdb.com")
          || hasHost(result?.filmaffinity_url, "filmaffinity.com");
      }

      function linkCounts() {
        const withLink = items.filter(hasExternalLink).length;
        return {
          withLink,
          withoutLink: items.length - withLink,
          total: items.length
        };
      }

      function normalizeKind(value) {
        const text = String(value || "pelicula").toLowerCase();
        if (["movie", "film", "película"].includes(text)) return "pelicula";
        if (["series", "tv series", "tvseries"].includes(text)) return "serie";
        if (["documentary"].includes(text)) return "documental";
        return ["pelicula", "serie", "anime", "documental"].includes(text) ? text : "pelicula";
      }

      function normalizeRating(value) {
        const rating = Number.parseInt(value || 0, 10);
        if (Number.isNaN(rating)) return 0;
        return Math.max(0, Math.min(10, rating));
      }

      function todayLocalDate() {
        const date = new Date();
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
        return date.toISOString().slice(0, 10);
      }

      function localDateOffset(offset) {
        const date = new Date();
        date.setHours(12, 0, 0, 0);
        date.setDate(date.getDate() + Number(offset || 0));
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
        return date.toISOString().slice(0, 10);
      }

      function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;"
        }[char]));
      }

      function escapeAttr(value) {
        return escapeHtml(value).replace(/`/g, "&#096;");
      }
