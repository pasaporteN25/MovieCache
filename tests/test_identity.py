from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from movie_inbox.application.auth_service import (
    AuthService,
    AuthenticationError,
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
from movie_inbox.infrastructure.identity_repository import INSTANCE_SCHEMA_V1, SqliteIdentityRepository
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
                stored_password = connection.execute("SELECT password_hash FROM users").fetchone()[0]
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
            self.assertEqual([record.user.username for record in members.list_members(owner)], ["maria"])

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
                    "INSERT INTO instance_migrations(version, name, applied_at) VALUES (1, 'v1', 'now')"
                )
                connection.commit()

            repository = SqliteIdentityRepository(database)
            repository.initialize()

            with closing(sqlite3.connect(database)) as connection:
                versions = [row[0] for row in connection.execute(
                    "SELECT version FROM instance_migrations ORDER BY version"
                )]
                tables = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )}
            self.assertEqual(versions, [1, 2, 3, 4, 5])
            self.assertIn("user_privacy_preferences", tables)
            self.assertIn("item_privacy_overrides", tables)
            self.assertIn("archived_members", tables)
            self.assertIn("curated_collections", tables)
            self.assertIn("media_libraries", tables)
            self.assertIn("library_scan_runs", tables)
            self.assertIn("library_files", tables)
            self.assertIn("curated_collection_items", tables)
            self.assertIn("collection_follows", tables)
            self.assertIn("import_drafts", tables)
            self.assertIn("import_draft_items", tables)

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
            members = MemberService(repository, SqlitePersonalCatalogProvisioner(root / "member-catalogs"))
            provisioned = members.create_member(
                owner,
                "maria",
                temporary_password="a-temporary-password",
            )
            member = provisioned.member
            member_repository = open_catalog_repository(Path(member.catalog.write_path), normalize_item)
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
            self.assertEqual(member_repository.get("heat").title, "Heat")

            restored = members.restore_member(
                owner,
                archived.id,
                temporary_password="a-restored-password",
            )
            self.assertEqual(restored.member.user.username, "maria")
            self.assertEqual(restored.member.catalog.write_path, member.catalog.write_path)
            self.assertEqual(member_repository.get("heat").rating, 9)
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
            members = MemberService(repository, SqlitePersonalCatalogProvisioner(root / "member-catalogs"))
            member = members.create_member(owner, "maria").member
            members.set_active(owner, member.user.id, False)
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("DELETE FROM catalog_sources WHERE catalog_id = ?", (member.catalog.id,))
                connection.commit()

            with self.assertRaises(IdentityNotFound):
                members.archive_member(owner, member.user.id, confirmed_username="maria")
            self.assertIsNotNone(repository.account(member.user.id))


if __name__ == "__main__":
    unittest.main()
