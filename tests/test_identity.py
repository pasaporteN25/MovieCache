from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from movie_inbox.application.auth_service import (
    AuthenticationError,
    AuthService,
    DeviceSession,
    PasswordHasher,
    PasswordPolicyError,
    session_token_hash,
)
from movie_inbox.application.identity_repository import (
    IdentityCatalogMismatch,
    IdentityMemberActive,
    IdentityNotFound,
)
from movie_inbox.application.member_service import MemberService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.privacy import ItemPrivacyOverride, PrivacyPreferences
from movie_inbox.infrastructure.identity_repository import (
    INSTANCE_SCHEMA_V1,
    INSTANCE_SCHEMA_VERSION,
    SqliteIdentityRepository,
)
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.personal_catalogs import SqlitePersonalCatalogProvisioner
from movie_inbox.infrastructure.repositories import open_catalog_repository


class IdentityTests(unittest.TestCase):
    def test_owner_adopts_existing_catalog_without_rewriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog_path = root / "catalog.json"
            JsonCatalogRepository(catalog_path, normalize_item).write(
                [normalize_item({"id": "heat", "title": "Heat", "year": "1995"})]
            )
            before = catalog_path.read_bytes()
            repository = SqliteIdentityRepository(root / "instance.db")
            service = AuthService(repository)

            user, catalog = service.bootstrap_owner(
                "lucas",
                "a-long-local-password",
                catalog_name="Archivo de Lucas",
                source_paths=[str(catalog_path)],
                write_path=str(catalog_path),
            )

            self.assertEqual(user.role, "owner")
            self.assertEqual(catalog.name, "Archivo de Lucas")
            self.assertEqual(Path(catalog.write_path), catalog_path.resolve())
            self.assertEqual(catalog_path.read_bytes(), before)
            self.assertEqual(repository.default_catalog_for(user.id), catalog)

    def test_password_and_session_token_are_never_stored_in_plaintext(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog_path = root / "catalog.json"
            JsonCatalogRepository(catalog_path, normalize_item).write([])
            database = root / "instance.db"
            repository = SqliteIdentityRepository(database)
            service = AuthService(repository)
            password = "a-long-local-password"
            user, _ = service.bootstrap_owner(
                "lucas",
                password,
                catalog_name="Mi catalogo",
                source_paths=[str(catalog_path)],
                write_path=str(catalog_path),
            )

            token, identity = service.login("LUCAS", password)
            self.assertEqual(identity.user.id, user.id)
            with closing(sqlite3.connect(database)) as connection:
                stored_password = connection.execute("SELECT password_hash FROM users").fetchone()[
                    0
                ]
                stored_token = connection.execute("SELECT token_hash FROM sessions").fetchone()[0]
            self.assertNotEqual(stored_password, password)
            self.assertTrue(stored_password.startswith("scrypt$"))
            self.assertNotEqual(stored_token, token)
            self.assertEqual(stored_token, session_token_hash(token))
            self.assertIsNotNone(service.authenticate(token))

            service.logout(token)
            self.assertIsNone(service.authenticate(token))

    def test_expired_sessions_and_invalid_credentials_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            now = [1_000.0]
            root = Path(temporary)
            catalog_path = root / "catalog.json"
            JsonCatalogRepository(catalog_path, normalize_item).write([])
            repository = SqliteIdentityRepository(root / "instance.db")
            service = AuthService(repository, session_ttl_seconds=60, clock=lambda: now[0])
            service.bootstrap_owner(
                "owner",
                "a-long-local-password",
                catalog_name="Mi catalogo",
                source_paths=[str(catalog_path)],
                write_path=str(catalog_path),
            )
            with self.assertRaises(AuthenticationError):
                service.login("owner", "incorrect-password")

            token, _ = service.login("owner", "a-long-local-password")
            now[0] = 1_061.0
            self.assertIsNone(service.authenticate(token))

    def test_device_tokens_are_hashed_rotated_and_revocable_independently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            now = [1_000.0]
            root = Path(temporary)
            catalog_path = root / "catalog.json"
            JsonCatalogRepository(catalog_path, normalize_item).write([])
            database = root / "instance.db"
            service = AuthService(
                SqliteIdentityRepository(database),
                clock=lambda: now[0],
                device_access_ttl_seconds=60,
                device_refresh_ttl_seconds=300,
                # This test is about rotation and revocation, not the retry
                # window [X4.1] adds -- see DeviceRefreshRetryTests.
                device_refresh_grace_seconds=0,
            )
            service.bootstrap_owner(
                "owner",
                "a-long-local-password",
                catalog_name="Mi catalogo",
                source_paths=[str(catalog_path)],
                write_path=str(catalog_path),
            )

            session = service.login_device("owner", "a-long-local-password", "Pixel de Lucas")
            self.assertIsNotNone(service.authenticate_device(session.access_token))
            with closing(sqlite3.connect(database)) as connection:
                access_hash, refresh_hash, device_name = connection.execute(
                    "SELECT access_token_hash, refresh_token_hash, device_name FROM device_sessions"
                ).fetchone()
            self.assertEqual(device_name, "Pixel de Lucas")
            self.assertEqual(access_hash, session_token_hash(session.access_token))
            self.assertEqual(refresh_hash, session_token_hash(session.refresh_token))
            self.assertNotEqual(access_hash, session.access_token)
            self.assertNotEqual(refresh_hash, session.refresh_token)

            now[0] = 1_010.0
            rotated = service.refresh_device_session(session.refresh_token)
            assert rotated is not None
            self.assertNotEqual(rotated.access_token, session.access_token)
            self.assertNotEqual(rotated.refresh_token, session.refresh_token)
            self.assertIsNone(service.authenticate_device(session.access_token))
            now[0] = 1_011.0
            self.assertIsNone(service.refresh_device_session(session.refresh_token))
            self.assertIsNotNone(service.authenticate_device(rotated.access_token))

            service.logout_device(rotated.access_token)
            self.assertIsNone(service.authenticate_device(rotated.access_token))
            self.assertIsNone(service.refresh_device_session(rotated.refresh_token))

            password_token, password_identity = service.login("owner", "a-long-local-password")
            replacement = service.login_device("owner", "a-long-local-password", "Tablet de Lucas")
            service.change_password(
                password_identity,
                "a-long-local-password",
                "a-different-local-password",
            )
            self.assertIsNone(service.authenticate(password_token))
            self.assertIsNone(service.authenticate_device(replacement.access_token))
            self.assertIsNone(service.refresh_device_session(replacement.refresh_token))

    def test_catalog_binding_cannot_be_silently_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.json"
            second = root / "second.json"
            JsonCatalogRepository(first, normalize_item).write([])
            JsonCatalogRepository(second, normalize_item).write([])
            repository = SqliteIdentityRepository(root / "instance.db")
            service = AuthService(repository)
            service.bootstrap_owner(
                "owner",
                "a-long-local-password",
                catalog_name="Mi catalogo",
                source_paths=[str(first)],
                write_path=str(first),
            )
            with self.assertRaises(IdentityCatalogMismatch):
                service.validate_owner_catalog([str(second)], str(second))

    def test_password_policy_and_hash_verification(self) -> None:
        hasher = PasswordHasher()
        encoded = hasher.hash("a-long-local-password")
        self.assertTrue(hasher.verify("a-long-local-password", encoded))
        self.assertFalse(hasher.verify("another-password", encoded))
        with self.assertRaises(PasswordPolicyError):
            hasher.hash("short")

    def test_member_lifecycle_provisions_an_isolated_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner_catalog = root / "owner.json"
            JsonCatalogRepository(owner_catalog, normalize_item).write(
                [normalize_item({"id": "heat", "title": "Heat", "year": "1995"})]
            )
            repository = SqliteIdentityRepository(root / "instance.db")
            auth = AuthService(repository)
            owner, _ = auth.bootstrap_owner(
                "owner",
                "a-long-owner-password",
                catalog_name="Owner catalog",
                source_paths=[str(owner_catalog)],
                write_path=str(owner_catalog),
            )
            members = MemberService(
                repository,
                SqlitePersonalCatalogProvisioner(root / "member-catalogs"),
            )

            provisioned = members.create_member(
                owner,
                "maria",
                temporary_password="a-temporary-password",
            )

            member = provisioned.member
            member_path = Path(member.catalog.write_path)
            self.assertTrue(member.user.must_change_password)
            self.assertEqual(member.user.role, "member")
            self.assertTrue(member_path.exists())
            self.assertEqual(open_catalog_repository(member_path, normalize_item).read(), [])
            self.assertEqual(
                [record.user.username for record in members.list_members(owner)], ["maria"]
            )

            old_token, temporary_identity = auth.login("maria", "a-temporary-password")
            self.assertTrue(temporary_identity.user.must_change_password)
            new_token, ready_identity = auth.change_password(
                temporary_identity,
                "a-temporary-password",
                "a-permanent-password",
            )
            self.assertFalse(ready_identity.user.must_change_password)
            self.assertIsNone(auth.authenticate(old_token))
            self.assertIsNotNone(auth.authenticate(new_token))

            members.set_active(owner, member.user.id, False)
            self.assertIsNone(auth.authenticate(new_token))
            with self.assertRaises(AuthenticationError):
                auth.login("maria", "a-permanent-password")

            members.set_active(owner, member.user.id, True)
            active_token, _ = auth.login("maria", "a-permanent-password")
            reset = members.reset_password(
                owner,
                member.user.id,
                temporary_password="another-temporary-password",
            )
            self.assertTrue(reset.member.user.must_change_password)
            self.assertIsNone(auth.authenticate(active_token))
            _, reset_identity = auth.login("maria", "another-temporary-password")
            self.assertTrue(reset_identity.user.must_change_password)
            self.assertEqual(
                [item.id for item in JsonCatalogRepository(owner_catalog, normalize_item).read()],
                ["heat"],
            )

    def test_v1_instance_is_migrated_to_current_instance_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "instance.db"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(INSTANCE_SCHEMA_V1)
                connection.execute(
                    "INSERT INTO instance_migrations(version, name, applied_at) "
                    "VALUES (1, 'v1', 'now')"
                )
                connection.commit()

            repository = SqliteIdentityRepository(database)
            repository.initialize()

            with closing(sqlite3.connect(database)) as connection:
                versions = [
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM instance_migrations ORDER BY version"
                    )
                ]
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            # Every migration runs, in order, with no gaps. Derived from the
            # constant so adding one does not need this list edited by hand.
            self.assertEqual(versions, list(range(1, INSTANCE_SCHEMA_VERSION + 1)))
            self.assertIn("user_privacy_preferences", tables)
            self.assertIn("streaming_regions", tables)
            self.assertIn("streaming_providers", tables)
            self.assertIn("member_streaming_preferences", tables)
            self.assertIn("item_privacy_overrides", tables)
            self.assertIn("archived_members", tables)
            self.assertIn("curated_collections", tables)
            self.assertIn("media_libraries", tables)
            self.assertIn("library_scan_runs", tables)
            self.assertIn("library_files", tables)
            self.assertIn("curated_collection_items", tables)
            self.assertIn("collection_follows", tables)
            self.assertIn("scanner_history", tables)
            self.assertIn("import_drafts", tables)
            self.assertIn("import_draft_items", tables)
            self.assertIn("home_featured_snapshots", tables)
            self.assertIn("public_presentations", tables)
            self.assertIn("device_sessions", tables)

    def test_v7_scanner_history_is_repaired_without_losing_existing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "instance.db"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE instance_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TEXT NOT NULL
                    );
                    CREATE TABLE scanner_history (
                        id TEXT PRIMARY KEY,
                        action TEXT NOT NULL,
                        label TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'applied',
                        mode TEXT NOT NULL DEFAULT 'persistent',
                        created_at TEXT NOT NULL,
                        undone_at TEXT NOT NULL DEFAULT '',
                        summary_json TEXT NOT NULL DEFAULT '{}',
                        before_json TEXT NOT NULL DEFAULT '{}',
                        after_json TEXT NOT NULL DEFAULT '{}'
                    );
                    INSERT INTO scanner_history(id, action, label, created_at)
                    VALUES ('history-1', 'link', 'Vincular', '2026-08-22T10:00:00Z');
                    -- Minimal stand-ins for the real v5/v3 tables this fixture
                    -- otherwise skips (this test only exercises v8's
                    -- scanner_history repair in isolation) -- v9's and v10's
                    -- own migrations ALTER these tables, so they must exist.
                    CREATE TABLE library_scan_runs (id TEXT PRIMARY KEY);
                    CREATE TABLE media_libraries (id TEXT PRIMARY KEY);
                    CREATE TABLE curated_collections (id TEXT PRIMARY KEY);
                    CREATE TABLE import_drafts (id TEXT PRIMARY KEY);
                    """
                )
                connection.executemany(
                    "INSERT INTO instance_migrations(version, name, applied_at) "
                    "VALUES (?, ?, 'now')",
                    [(version, f"v{version}") for version in range(1, 8)],
                )
                connection.commit()

            SqliteIdentityRepository(database).initialize()

            with closing(sqlite3.connect(database)) as connection:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(scanner_history)")
                }
                version = connection.execute(
                    "SELECT MAX(version) FROM instance_migrations"
                ).fetchone()[0]
                history = connection.execute(
                    "SELECT id, catalog_before_json, catalog_after_json, catalog_path "
                    "FROM scanner_history"
                ).fetchone()

            self.assertEqual(version, INSTANCE_SCHEMA_VERSION)
            self.assertTrue(
                {"catalog_before_json", "catalog_after_json", "catalog_path"} <= columns
            )
            self.assertEqual(history, ("history-1", "null", "null", ""))

    def test_privacy_and_archival_are_reversible_without_losing_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner_catalog = root / "owner.json"
            JsonCatalogRepository(owner_catalog, normalize_item).write([])
            repository = SqliteIdentityRepository(root / "instance.db")
            auth = AuthService(repository)
            owner, _ = auth.bootstrap_owner(
                "owner",
                "a-long-owner-password",
                catalog_name="Owner catalog",
                source_paths=[str(owner_catalog)],
                write_path=str(owner_catalog),
            )
            members = MemberService(
                repository, SqlitePersonalCatalogProvisioner(root / "member-catalogs")
            )
            provisioned = members.create_member(
                owner,
                "maria",
                temporary_password="a-temporary-password",
            )
            member = provisioned.member
            member_repository = open_catalog_repository(
                Path(member.catalog.write_path), normalize_item
            )
            member_repository.write([normalize_item({"id": "heat", "title": "Heat", "rating": 9})])

            preferences = PrivacyPreferences(catalog_shared=True, share_rating=True)
            repository.update_privacy(member.user.id, preferences)
            repository.set_item_privacy(
                member.user.id,
                member.catalog.id,
                "heat",
                ItemPrivacyOverride(rating="private", review="inherit"),
            )
            self.assertEqual(repository.privacy_for(member.user.id), preferences)
            self.assertEqual(
                repository.item_privacy_overrides(member.user.id, member.catalog.id)["heat"].rating,
                "private",
            )

            with self.assertRaises(IdentityMemberActive):
                members.archive_member(owner, member.user.id, confirmed_username="maria")
            members.set_active(owner, member.user.id, False)
            archived = members.archive_member(owner, member.user.id, confirmed_username="maria")
            self.assertIsNone(repository.account(member.user.id))
            self.assertTrue(Path(archived.sources[0].path).exists())
            archived_item = member_repository.get("heat")
            assert archived_item is not None
            self.assertEqual(archived_item.title, "Heat")

            restored = members.restore_member(
                owner,
                archived.id,
                temporary_password="a-restored-password",
            )
            self.assertEqual(restored.member.user.username, "maria")
            self.assertEqual(restored.member.catalog.write_path, member.catalog.write_path)
            restored_item = member_repository.get("heat")
            assert restored_item is not None
            self.assertEqual(restored_item.rating, 9)
            _, restored_identity = auth.login("maria", "a-restored-password")
            self.assertTrue(restored_identity.user.must_change_password)
            self.assertEqual(repository.list_archived_members(), [])

    def test_member_without_catalog_sources_is_not_archived(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner_catalog = root / "owner.json"
            JsonCatalogRepository(owner_catalog, normalize_item).write([])
            database = root / "instance.db"
            repository = SqliteIdentityRepository(database)
            owner, _ = AuthService(repository).bootstrap_owner(
                "owner",
                "a-long-owner-password",
                catalog_name="Owner catalog",
                source_paths=[str(owner_catalog)],
                write_path=str(owner_catalog),
            )
            members = MemberService(
                repository, SqlitePersonalCatalogProvisioner(root / "member-catalogs")
            )
            member = members.create_member(owner, "maria").member
            members.set_active(owner, member.user.id, False)
            with closing(sqlite3.connect(database)) as connection:
                connection.execute(
                    "DELETE FROM catalog_sources WHERE catalog_id = ?", (member.catalog.id,)
                )
                connection.commit()

            with self.assertRaises(IdentityNotFound):
                members.archive_member(owner, member.user.id, confirmed_username="maria")
            self.assertIsNotNone(repository.account(member.user.id))


class DeviceRefreshRetryTests(unittest.TestCase):
    """[X4.1]: a refresh whose response was lost can be retried.

    The phone sent its refresh token, the server rotated, and the response never
    arrived: the phone still holds only the token it just spent. Without a retry
    window that phone is locked out until someone scans a QR again.
    """

    GRACE = 120

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        catalog_path = root / "catalog.json"
        JsonCatalogRepository(catalog_path, normalize_item).write([])
        self.database = root / "instance.db"
        self.now = [1_000.0]
        self.service = AuthService(
            SqliteIdentityRepository(self.database),
            clock=lambda: self.now[0],
            device_access_ttl_seconds=60,
            device_refresh_ttl_seconds=10_000,
            device_refresh_grace_seconds=self.GRACE,
        )
        self.service.bootstrap_owner(
            "owner",
            "a-long-local-password",
            catalog_name="Mi catalogo",
            source_paths=[str(catalog_path)],
            write_path=str(catalog_path),
        )
        self.first = self.service.login_device("owner", "a-long-local-password", "Pixel")

    def test_only_hashes_of_the_previous_token_are_stored(self) -> None:
        self.service.refresh_device_session(self.first.refresh_token)

        with closing(sqlite3.connect(self.database)) as connection:
            previous, valid_until = connection.execute(
                "SELECT previous_refresh_token_hash, previous_refresh_valid_until"
                " FROM device_sessions"
            ).fetchone()

        self.assertEqual(previous, session_token_hash(self.first.refresh_token))
        self.assertNotEqual(previous, self.first.refresh_token)
        self.assertEqual(valid_until, int(self.now[0]) + self.GRACE)

    def test_the_token_a_lost_response_left_behind_still_refreshes(self) -> None:
        # The server rotated, the phone never saw the answer.
        self.assertIsNotNone(self.service.refresh_device_session(self.first.refresh_token))
        self.now[0] += 10

        retried = self.service.refresh_device_session(self.first.refresh_token)

        assert retried is not None
        self.assertIsNotNone(self.service.authenticate_device(retried.access_token))
        self.assertIsNotNone(self.service.refresh_device_session(retried.refresh_token))

    def test_a_retry_replaces_the_pair_the_phone_never_received(self) -> None:
        lost = self.service.refresh_device_session(self.first.refresh_token)
        assert lost is not None

        retried = self.service.refresh_device_session(self.first.refresh_token)

        assert retried is not None
        self.assertIsNone(self.service.authenticate_device(lost.access_token))
        self.assertIsNotNone(self.service.authenticate_device(retried.access_token))

    def test_the_window_closes(self) -> None:
        self.service.refresh_device_session(self.first.refresh_token)

        self.now[0] += self.GRACE + 1

        self.assertIsNone(self.service.refresh_device_session(self.first.refresh_token))

    def test_a_retry_does_not_extend_the_window(self) -> None:
        # Otherwise anyone holding an old token could keep it alive by using it.
        self.service.refresh_device_session(self.first.refresh_token)
        self.now[0] += self.GRACE - 10
        self.assertIsNotNone(self.service.refresh_device_session(self.first.refresh_token))

        self.now[0] += 20

        self.assertIsNone(self.service.refresh_device_session(self.first.refresh_token))

    def test_a_token_two_rotations_back_is_unknown(self) -> None:
        second = self.service.refresh_device_session(self.first.refresh_token)
        assert second is not None
        self.service.refresh_device_session(second.refresh_token)

        self.assertIsNone(self.service.refresh_device_session(self.first.refresh_token))

    def test_a_retry_does_not_outlive_the_session(self) -> None:
        self.service.refresh_device_session(self.first.refresh_token)
        retried = self.service.refresh_device_session(self.first.refresh_token)
        assert retried is not None
        self.service.logout_device(retried.access_token)

        self.assertIsNone(self.service.refresh_device_session(self.first.refresh_token))

    def test_changing_the_password_still_ends_every_device_session(self) -> None:
        self.service.refresh_device_session(self.first.refresh_token)
        _, identity = self.service.login("owner", "a-long-local-password")
        self.service.change_password(identity, "a-long-local-password", "a-different-password!")

        self.assertIsNone(self.service.refresh_device_session(self.first.refresh_token))


class DeviceSessionListTests(unittest.TestCase):
    """[X4.2]: an account sees its paired phones, by a stable id and no credential."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        catalog_path = root / "catalog.json"
        JsonCatalogRepository(catalog_path, normalize_item).write([])
        self.database = root / "instance.db"
        self.now = [1_000.0]
        self.repository = SqliteIdentityRepository(self.database)
        self.service = AuthService(
            self.repository,
            clock=lambda: self.now[0],
            device_access_ttl_seconds=60,
            device_refresh_ttl_seconds=500,
        )
        self.owner, _ = self.service.bootstrap_owner(
            "owner",
            "a-long-local-password",
            catalog_name="Mi catalogo",
            source_paths=[str(catalog_path)],
            write_path=str(catalog_path),
        )
        _, self.identity = self.service.login("owner", "a-long-local-password")
        self.members = MemberService(
            self.repository, SqlitePersonalCatalogProvisioner(root / "member-catalogs")
        )

    def _pair(self, name: str) -> DeviceSession:
        return self.service.login_device("owner", "a-long-local-password", name)

    def test_it_lists_the_account_s_phones_most_recently_used_first(self) -> None:
        self._pair("Pixel")
        self.now[0] += 5
        tablet = self._pair("Tablet")
        self.now[0] += 5
        self.service.authenticate_device(tablet.access_token)

        names = [row.device_name for row in self.service.list_device_sessions(self.identity)]

        self.assertEqual(names, ["Tablet", "Pixel"])

    def test_the_id_survives_a_refresh(self) -> None:
        session = self._pair("Pixel")
        (before,) = self.service.list_device_sessions(self.identity)

        self.now[0] += 10
        self.service.refresh_device_session(session.refresh_token)

        (after,) = self.service.list_device_sessions(self.identity)
        self.assertEqual(after.id, before.id)

    def test_last_seen_follows_authenticated_use(self) -> None:
        session = self._pair("Pixel")
        self.now[0] += 30

        self.service.authenticate_device(session.access_token)

        (row,) = self.service.list_device_sessions(self.identity)
        self.assertEqual(row.created_at, 1_000)
        self.assertEqual(row.last_seen_at, 1_030)

    def test_a_row_carries_no_credential(self) -> None:
        session = self._pair("Pixel")
        (row,) = self.service.list_device_sessions(self.identity)

        self.assertEqual(
            set(vars(row)), {"id", "device_name", "created_at", "last_seen_at", "expires_at"}
        )
        rendered = repr(row)
        for secret in (
            session.access_token,
            session.refresh_token,
            session_token_hash(session.access_token),
            session_token_hash(session.refresh_token),
        ):
            self.assertNotIn(secret, rendered)

    def test_another_account_s_phones_are_not_listed(self) -> None:
        self._pair("Pixel")
        member = self.members.create_member(self.owner, "maria").member
        self.repository.save_device_session(
            "member-access-hash",
            "member-refresh-hash",
            member.user.id,
            "Telefono de Maria",
            1_000,
            1_060,
            1_500,
        )

        names = [row.device_name for row in self.service.list_device_sessions(self.identity)]

        self.assertEqual(names, ["Pixel"])

    def test_an_expired_session_is_not_listed(self) -> None:
        self._pair("Pixel")

        self.now[0] += 501

        self.assertEqual(self.service.list_device_sessions(self.identity), [])

    def _id_of(self, name: str) -> str:
        return next(
            row.id
            for row in self.service.list_device_sessions(self.identity)
            if row.device_name == name
        )

    def test_a_revoked_phone_is_out_on_its_next_call(self) -> None:
        session = self._pair("Pixel")

        self.assertTrue(self.service.revoke_device_session(self.identity, self._id_of("Pixel")))

        self.assertIsNone(self.service.authenticate_device(session.access_token))
        self.assertIsNone(self.service.refresh_device_session(session.refresh_token))

    def test_revoking_also_closes_the_retry_window(self) -> None:
        # [X4.1] keeps the replaced refresh token usable for a while; a phone
        # someone just cut off must not get back in through it.
        session = self._pair("Pixel")
        rotated = self.service.refresh_device_session(session.refresh_token)
        assert rotated is not None

        self.service.revoke_device_session(self.identity, self._id_of("Pixel"))

        self.assertIsNone(self.service.refresh_device_session(session.refresh_token))
        self.assertIsNone(self.service.refresh_device_session(rotated.refresh_token))

    def test_revoking_one_phone_leaves_the_others(self) -> None:
        self._pair("Pixel")
        tablet = self._pair("Tablet")

        self.service.revoke_device_session(self.identity, self._id_of("Pixel"))

        self.assertIsNotNone(self.service.authenticate_device(tablet.access_token))
        self.assertEqual(
            [row.device_name for row in self.service.list_device_sessions(self.identity)],
            ["Tablet"],
        )

    def test_an_account_cannot_revoke_another_account_s_phone(self) -> None:
        member = self.members.create_member(self.owner, "maria").member
        self.repository.save_device_session(
            "member-access-hash",
            "member-refresh-hash",
            member.user.id,
            "Telefono de Maria",
            1_000,
            1_060,
            1_500,
        )
        (theirs,) = self.repository.list_device_sessions(member.user.id, 1_000)

        revoked = self.service.revoke_device_session(self.identity, theirs.id)

        self.assertFalse(revoked)
        self.assertEqual(len(self.repository.list_device_sessions(member.user.id, 1_000)), 1)

    def test_an_unknown_or_malformed_id_revokes_nothing(self) -> None:
        self._pair("Pixel")

        for bad in ("", "no-such-phone", "x" * 65, "%' OR '1'='1"):
            with self.subTest(session_id=bad[:12]):
                self.assertFalse(self.service.revoke_device_session(self.identity, bad))
        self.assertEqual(len(self.service.list_device_sessions(self.identity)), 1)

    def test_revoking_twice_is_not_an_error(self) -> None:
        self._pair("Pixel")
        session_id = self._id_of("Pixel")

        self.assertTrue(self.service.revoke_device_session(self.identity, session_id))
        self.assertFalse(self.service.revoke_device_session(self.identity, session_id))

    def test_the_migration_gives_existing_sessions_distinct_ids(self) -> None:
        # A real instance at v20, built by the real migrations rather than by
        # undoing the latest one, so this keeps meaning the same thing whichever
        # version happens to be last.
        root = Path(self.temporary.name)
        catalog_path = root / "catalog.json"
        old_database = root / "old-instance.db"
        with patch("movie_inbox.infrastructure.identity_repository.INSTANCE_SCHEMA_VERSION", 20):
            old_repository = SqliteIdentityRepository(old_database)
            owner, _ = AuthService(old_repository).bootstrap_owner(
                "owner",
                "a-long-local-password",
                catalog_name="Mi catalogo",
                source_paths=[str(catalog_path)],
                write_path=str(catalog_path),
            )
        with closing(sqlite3.connect(old_database)) as connection:
            for index, name in enumerate(("Pixel", "Tablet")):
                connection.execute(
                    """INSERT INTO device_sessions(
                        access_token_hash, refresh_token_hash, user_id, device_name,
                        created_at, access_expires_at, refresh_expires_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, 1000, 1060, 1500, 1000)""",
                    (f"access-{index}", f"refresh-{index}", owner.id, name),
                )
            connection.commit()
            self.assertNotIn(
                "session_id",
                {row[1] for row in connection.execute("PRAGMA table_info(device_sessions)")},
            )

        rows = SqliteIdentityRepository(old_database).list_device_sessions(owner.id, 1_000)

        ids = {row.id for row in rows}
        self.assertEqual(len(ids), 2)
        self.assertNotIn("", ids)


if __name__ == "__main__":
    unittest.main()
