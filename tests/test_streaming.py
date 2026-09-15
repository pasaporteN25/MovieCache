from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.streaming_repository import StreamingRegionNotFound
from movie_inbox.application.streaming_service import (
    StreamingAuthorizationError,
    StreamingService,
    StreamingSourceUnavailable,
)
from movie_inbox.domain.streaming import (
    ACQUISITION_OFFERS,
    AVAILABILITY_OFFERS,
    MAX_RETENTION_DAYS,
    STALE_AFTER_DAYS,
    AvailabilitySnapshot,
    MemberStreamingPreferences,
    PlatformOffer,
    RegionPolicy,
    StreamingConfigurationError,
    StreamingProvider,
    StreamingRegion,
    effective_region,
    is_available_offer,
    member_preferences,
    normalize_region_code,
    platform_availability,
    region_policy,
    snapshot_is_expired,
    snapshot_is_stale,
    visible_providers,
    work_key,
)
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.streaming_repository import SqliteStreamingRepository


class StreamingDomainTests(unittest.TestCase):
    def test_region_codes_are_iso_alpha_2_and_upper_cased(self) -> None:
        self.assertEqual(normalize_region_code("ar"), "AR")
        self.assertEqual(normalize_region_code(" Br "), "BR")
        for invalid in ("ARG", "", "1A", None, "a"):
            with self.subTest(value=invalid), self.assertRaises(StreamingConfigurationError):
                normalize_region_code(invalid)

    def test_only_watchable_offers_count_as_platform_availability(self) -> None:
        # Owner decision recorded in ADR-0004: renting is real information but it
        # is not availability, and saying otherwise would tell the viewer
        # something false about what they can watch right now.
        for kind in ("flatrate", "free", "ads"):
            with self.subTest(kind=kind):
                self.assertTrue(is_available_offer(kind))
        for kind in ("rent", "buy"):
            with self.subTest(kind=kind):
                self.assertFalse(is_available_offer(kind))
        self.assertFalse(AVAILABILITY_OFFERS & ACQUISITION_OFFERS)

    def test_default_region_must_be_one_the_instance_enabled(self) -> None:
        policy = region_policy({"default_region": "AR"}, enabled_regions=["AR", "BR"])
        self.assertEqual(policy.default_region, "AR")
        with self.assertRaises(StreamingConfigurationError):
            region_policy({"default_region": "UY"}, enabled_regions=["AR"])

    def test_member_choice_only_counts_while_allowed_and_still_enabled(self) -> None:
        chosen = MemberStreamingPreferences(region="BR")
        allowed = RegionPolicy(default_region="AR", members_may_choose=True)
        locked = RegionPolicy(default_region="AR", members_may_choose=False)
        self.assertEqual(effective_region(allowed, chosen, enabled_regions=["AR", "BR"]), "BR")
        self.assertEqual(effective_region(locked, chosen, enabled_regions=["AR", "BR"]), "AR")
        # Disabling BR must not strand the member on a market nobody consults.
        self.assertEqual(effective_region(allowed, chosen, enabled_regions=["AR"]), "AR")
        self.assertEqual(effective_region(allowed, chosen, enabled_regions=[]), "")

    def test_ignored_providers_filter_the_view_without_naming_subscriptions(self) -> None:
        providers = [
            StreamingProvider("AR", "8", "Netflix"),
            StreamingProvider("AR", "337", "Disney Plus"),
        ]
        preferences = member_preferences(
            {"ignored_providers": ["337"]}, known_providers=["8", "337"]
        )
        self.assertEqual(
            [row.name for row in visible_providers(providers, preferences)], ["Netflix"]
        )
        with self.assertRaises(StreamingConfigurationError):
            member_preferences({"ignored_providers": ["999"]}, known_providers=["8"])


class StreamingRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "instance.db"
        identity = SqliteIdentityRepository(self.path)
        identity.initialize()
        AuthService(identity).bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(Path(self.temporary.name) / "catalog.json")],
            write_path=str(Path(self.temporary.name) / "catalog.json"),
        )
        self.repository = SqliteStreamingRepository(self.path)

    def test_migration_creates_the_streaming_tables(self) -> None:
        self.assertEqual(self.repository.list_regions(), [])
        self.assertEqual(self.repository.region_policy(), RegionPolicy())

    def test_regions_providers_and_policy_round_trip(self) -> None:
        self.repository.upsert_region(StreamingRegion("AR", "Argentina", True))
        self.repository.upsert_region(StreamingRegion("BR", "Brasil", False))
        self.assertEqual([row.code for row in self.repository.list_regions()], ["AR", "BR"])

        self.repository.set_region_policy(RegionPolicy("AR", True))
        self.assertEqual(self.repository.region_policy(), RegionPolicy("AR", True))

        self.repository.replace_providers(
            "AR",
            [
                StreamingProvider("AR", "8", "Netflix", 1),
                StreamingProvider("AR", "119", "Prime", 2),
            ],
        )
        self.assertEqual(
            [row.name for row in self.repository.list_providers("AR")], ["Netflix", "Prime"]
        )

        # Replacing is wholesale: a platform that left the market disappears
        # instead of lingering as a stale row.
        self.repository.replace_providers("AR", [StreamingProvider("AR", "8", "Netflix", 1)])
        self.assertEqual([row.provider_id for row in self.repository.list_providers("AR")], ["8"])

    def test_providers_cannot_be_written_for_an_unconfigured_region(self) -> None:
        with self.assertRaises(StreamingRegionNotFound):
            self.repository.replace_providers("UY", [StreamingProvider("UY", "8", "Netflix")])

    def test_member_preferences_round_trip_and_default_to_empty(self) -> None:
        owner = SqliteIdentityRepository(self.path).owner()
        assert owner is not None
        self.assertEqual(self.repository.member_preferences(owner.id), MemberStreamingPreferences())
        stored = self.repository.set_member_preferences(
            owner.id, MemberStreamingPreferences("AR", ("337",))
        )
        self.assertEqual(self.repository.member_preferences(owner.id), stored)


class StreamingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name) / "instance.db"
        identity = SqliteIdentityRepository(path)
        identity.initialize()
        AuthService(identity).bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(Path(self.temporary.name) / "catalog.json")],
            write_path=str(Path(self.temporary.name) / "catalog.json"),
        )
        self.identity_repository = identity
        self.repository = SqliteStreamingRepository(path)
        self.service = StreamingService(
            self.repository,
            region_loader=lambda: [{"code": "AR", "name": "Argentina"}],
            provider_loader=lambda region: [
                {"region_code": region, "provider_id": "8", "name": "Netflix"},
                {"region_code": region, "provider_id": "350", "name": "Apple TV"},
                {"region_code": region, "provider_id": "2", "name": "Apple TV Store"},
            ],
        )

    def _identity(self):
        owner = self.identity_repository.owner()
        assert owner is not None
        catalog = self.identity_repository.default_catalog_for(owner.id)

        class _Identity:
            user = owner

        _Identity.catalog = catalog  # type: ignore[attr-defined]
        return _Identity()

    def test_refresh_stores_the_upstream_names_verbatim(self) -> None:
        self.service.add_region({"code": "AR", "name": "Argentina"})
        providers = self.service.refresh_providers("AR")
        names = [provider.name for provider in providers]
        # ADR-0004: the subscription service and the store are different rows and
        # must stay distinguishable, so neither may be collapsed into the other.
        self.assertIn("Apple TV", names)
        self.assertIn("Apple TV Store", names)
        self.assertNotEqual(
            {p.provider_id for p in providers if p.name == "Apple TV"},
            {p.provider_id for p in providers if p.name == "Apple TV Store"},
        )

    def test_disabling_the_default_region_clears_it(self) -> None:
        self.service.add_region({"code": "AR", "name": "Argentina"})
        self.service.set_policy({"default_region": "AR", "members_may_choose": True})
        self.service.set_region_enabled("AR", False)
        self.assertEqual(self.repository.region_policy().default_region, "")

    def test_member_cannot_choose_a_region_when_the_owner_did_not_allow_it(self) -> None:
        self.service.add_region({"code": "AR", "name": "Argentina"})
        self.service.set_policy({"default_region": "AR", "members_may_choose": False})
        with self.assertRaises(StreamingAuthorizationError):
            self.service.update_preferences(self._identity(), {"region": "AR"})

    def test_member_cannot_choose_a_region_the_instance_never_enabled(self) -> None:
        self.service.add_region({"code": "AR", "name": "Argentina"})
        self.service.set_policy({"default_region": "AR", "members_may_choose": True})
        with self.assertRaises(StreamingConfigurationError):
            self.service.update_preferences(self._identity(), {"region": "UY"})

    def test_without_a_credential_the_back_office_still_works_but_cannot_refresh(self) -> None:
        offline = StreamingService(self.repository)
        offline.add_region({"code": "AR", "name": "Argentina"})
        self.assertFalse(offline.upstream_configured)
        self.assertEqual([row.code for row in offline.repository.list_regions()], ["AR"])
        with self.assertRaises(StreamingSourceUnavailable):
            offline.refresh_providers("AR")
        with self.assertRaises(StreamingSourceUnavailable):
            offline.available_upstream_regions()


if __name__ == "__main__":
    unittest.main()


class AvailabilityDomainTests(unittest.TestCase):
    def _snapshot(self, days_old: float, offers=()) -> AvailabilitySnapshot:
        checked = datetime.now(UTC) - timedelta(days=days_old)
        return AvailabilitySnapshot(
            work_key="movie:78",
            region_code="AR",
            checked_at=checked.isoformat().replace("+00:00", "Z"),
            offers=tuple(offers),
        )

    def test_work_key_separates_films_from_series_with_the_same_id(self) -> None:
        # Upstream ids overlap across media types; without the type a series
        # could answer for a film.
        self.assertNotEqual(work_key("1398", "movie"), work_key("1398", "tv"))
        for bad in (("", "movie"), ("abc", "movie"), ("78", "pelicula"), (None, None)):
            with self.subTest(value=bad), self.assertRaises(StreamingConfigurationError):
                work_key(*bad)

    def test_rent_only_offers_are_reported_but_are_not_availability(self) -> None:
        snapshot = self._snapshot(1, [PlatformOffer("3", "Google Play Movies", "rent")])
        result = platform_availability(snapshot)
        self.assertTrue(result.known)
        self.assertFalse(result.en_plataforma)
        self.assertEqual(
            [offer.provider_name for offer in result.acquire_on], ["Google Play Movies"]
        )
        self.assertEqual(result.available_on, ())

    def test_subscription_offers_make_a_work_available(self) -> None:
        snapshot = self._snapshot(1, [PlatformOffer("8", "Netflix", "flatrate")])
        self.assertTrue(platform_availability(snapshot).en_plataforma)

    def test_missing_or_expired_snapshots_are_unknown_not_unavailable(self) -> None:
        # "We never checked" and "it is on no platform" are different answers;
        # collapsing them would state something we never verified.
        self.assertFalse(platform_availability(None).known)
        expired = self._snapshot(
            MAX_RETENTION_DAYS + 1, [PlatformOffer("8", "Netflix", "flatrate")]
        )
        result = platform_availability(expired)
        self.assertFalse(result.known)
        self.assertFalse(result.en_plataforma)

    def test_retention_ceiling_and_refresh_threshold_are_distinct(self) -> None:
        fresh = self._snapshot(1)
        stale = self._snapshot(STALE_AFTER_DAYS + 1)
        self.assertFalse(snapshot_is_stale(fresh))
        self.assertTrue(snapshot_is_stale(stale))
        self.assertFalse(snapshot_is_expired(stale))
        self.assertTrue(snapshot_is_expired(self._snapshot(MAX_RETENTION_DAYS + 1)))
        # The contractual ceiling has to sit inside the six months the terms allow.
        self.assertLessEqual(MAX_RETENTION_DAYS, 180)

    def test_an_unreadable_timestamp_is_treated_as_expired(self) -> None:
        broken = AvailabilitySnapshot("movie:78", "AR", "no es una fecha")
        self.assertTrue(snapshot_is_expired(broken))
        self.assertFalse(platform_availability(broken).known)

    def test_a_viewer_hiding_every_offering_platform_gets_no_false_negative(self) -> None:
        snapshot = self._snapshot(1, [PlatformOffer("8", "Netflix", "flatrate")])
        hidden = MemberStreamingPreferences(ignored_providers=("8",))
        result = platform_availability(snapshot, hidden)
        self.assertTrue(result.known)
        self.assertFalse(result.en_plataforma)
        self.assertEqual(result.available_on, ())


class AvailabilityServiceTests(StreamingServiceTests):
    """Reuses the [S1] fixture and adds an availability loader on top."""

    def setUp(self) -> None:
        super().setUp()
        self.calls: list[tuple[str, str, str]] = []
        self.fail_next = False

        def loader(media_type: str, tmdb_id: str, region: str) -> dict[str, object]:
            self.calls.append((media_type, tmdb_id, region))
            if self.fail_next:
                raise TimeoutError("upstream caido")
            return {
                "link": "https://www.themoviedb.org/movie/78/watch?locale=AR",
                "offers": [
                    {"provider_id": "8", "provider_name": "Netflix", "kind": "flatrate"},
                    {"provider_id": "3", "provider_name": "Google Play", "kind": "rent"},
                ],
            }

        self.service.availability_loader = loader
        self.service.add_region({"code": "AR", "name": "Argentina"})
        self.service.set_policy({"default_region": "AR", "members_may_choose": False})

    def _items(self) -> list[dict[str, object]]:
        return [
            {"id": "heat", "tmdb_id": "949", "kind": "pelicula", "en_catalogo": True},
            {"id": "sopranos", "tmdb_id": "1398", "kind": "serie", "en_catalogo": False},
            {"id": "sin-identidad", "kind": "pelicula"},
        ]

    def test_availability_never_writes_en_catalogo(self) -> None:
        # CLAUDE.md invariant 2: owning the file and being on a platform are
        # independent facts, and this flow must not conflate them.
        items = self._items()
        before = [dict(item) for item in items]
        resolved = self.service.availability_for(self._identity(), items)
        self.assertEqual(items, before)
        self.assertTrue(resolved["heat"].en_plataforma)
        self.assertTrue(items[0]["en_catalogo"])
        self.assertFalse(items[1]["en_catalogo"])
        # A work available on a platform did not become "in the catalogue".
        self.assertFalse(items[1]["en_catalogo"])
        self.assertTrue(resolved["sopranos"].en_plataforma)

    def test_a_work_without_upstream_identity_is_unknown_not_unavailable(self) -> None:
        resolved = self.service.availability_for(self._identity(), self._items())
        self.assertNotIn("sin-identidad", resolved)

    def test_media_type_follows_the_catalogue_kind(self) -> None:
        self.service.availability_for(self._identity(), self._items())
        self.assertIn(("movie", "949", "AR"), self.calls)
        self.assertIn(("tv", "1398", "AR"), self.calls)

    def test_a_fresh_snapshot_is_not_fetched_again(self) -> None:
        self.service.availability_for(self._identity(), self._items())
        first = len(self.calls)
        self.service.availability_for(self._identity(), self._items())
        self.assertEqual(len(self.calls), first, "un snapshot fresco no debe reconsultarse")

    def test_an_upstream_failure_keeps_serving_the_stored_snapshot(self) -> None:
        self.service.availability_for(self._identity(), self._items())
        stored = self.repository.availability("AR", ["movie:949"])["movie:949"]
        # Age the row past the refresh threshold, then make the upstream fail.
        aged = datetime.now(UTC) - timedelta(days=STALE_AFTER_DAYS + 1)
        self.repository.save_availability(
            AvailabilitySnapshot(
                stored.work_key,
                stored.region_code,
                aged.isoformat().replace("+00:00", "Z"),
                stored.offers,
                stored.link,
            )
        )
        self.fail_next = True
        resolved = self.service.availability_for(self._identity(), self._items())
        self.assertTrue(resolved["heat"].known)
        self.assertTrue(resolved["heat"].en_plataforma)

    def test_refreshes_are_capped_per_request(self) -> None:
        self.service.max_refresh_per_request = 1
        self.service.availability_for(self._identity(), self._items())
        self.assertEqual(len(self.calls), 1)

    def test_without_an_enabled_region_nothing_is_consulted(self) -> None:
        self.service.set_region_enabled("AR", False)
        self.assertEqual(self.service.availability_for(self._identity(), self._items()), {})
        self.assertEqual(self.calls, [])

    def test_expired_rows_are_purged_and_a_full_purge_empties_the_store(self) -> None:
        self.service.availability_for(self._identity(), self._items())
        self.assertTrue(self.repository.availability("AR", ["movie:949"]))
        self.assertEqual(self.service.purge_expired_availability(), 0)
        aged = datetime.now(UTC) - timedelta(days=MAX_RETENTION_DAYS + 5)
        self.repository.save_availability(
            AvailabilitySnapshot("movie:949", "AR", aged.isoformat().replace("+00:00", "Z"))
        )
        self.assertEqual(self.service.purge_expired_availability(), 1)
        self.service.availability_for(self._identity(), self._items())
        self.assertEqual(self.service.purge_all_availability(), 2)
        self.assertEqual(self.repository.availability("AR", ["movie:949", "tv:1398"]), {})
