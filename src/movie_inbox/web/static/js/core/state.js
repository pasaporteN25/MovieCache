import { storedInboxMode } from "./router.js";
import { storedClubMode } from "../surfaces/club.js";

      export let currentIdentity = null;

      export let privacyPreferences = {
        catalog_shared: false,
        share_status: false,
        share_watched_at: false,
        share_history: false,
        share_rating: false,
        share_review: false
      };

      export let clubMode = storedClubMode();

      export let items = [];

      export let selectedExistingIdForSearch = null;

      export let curationCounts = { pending: 0, duplicates: 0, missing_link: 0, deferred: 0, scanner: 0 };

      export let inboxMode = storedInboxMode();

      export let currentView = "home";

      export let routeRestored = false;

      export const SEARCH_PAGE_SIZE = 6;

      export const CATALOG_PAGE_SIZE = 36;

      export function setCurrentIdentity(value) {
        currentIdentity = value;
      }

      export function setPrivacyPreferences(value) {
        privacyPreferences = value;
      }

      export function setClubMode(value) {
        clubMode = value;
      }

      export function setItems(value) {
        items = value;
      }

      export function setSelectedExistingIdForSearch(value) {
        selectedExistingIdForSearch = value;
      }

      export function setCurationCounts(value) {
        curationCounts = value;
      }

      export function setInboxModeValue(value) {
        inboxMode = value;
      }

      export function setCurrentView(value) {
        currentView = value;
      }

      export function setRouteRestored(value) {
        routeRestored = value;
      }

