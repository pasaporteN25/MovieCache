from __future__ import annotations

import tempfile
import unittest
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
    MemberStreamingPreferences,
    RegionPolicy,
    StreamingConfigurationError,
    StreamingProvider,
    StreamingRegion,
    effective_region,
    is_available_offer,
    member_preferences,
    normalize_region_code,
    region_policy,
    visible_providers,
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
