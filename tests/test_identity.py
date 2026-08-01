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
from movie_inbox.application.identity_repository import IdentityCatalogMismatch
from movie_inbox.application.member_service import MemberService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
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


if __name__ == "__main__":
    unittest.main()
