from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DockerPackagingTests(unittest.TestCase):
    def test_image_is_multi_stage_non_root_and_health_checked(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertGreaterEqual(dockerfile.count("\nFROM "), 2)
        self.assertIn(" AS builder", dockerfile)
        self.assertIn(" AS runtime", dockerfile)
        self.assertIn("USER movie-inbox:movie-inbox", dockerfile)
        self.assertIn('install -d "/media/library/disco${slot}"', dockerfile)
        self.assertIn("HEALTHCHECK ", dockerfile)
        self.assertIn("ENTRYPOINT [\"movie-inbox\"]", dockerfile)

    def test_compose_keeps_state_persistent_and_media_read_only(self) -> None:
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

        self.assertIn("movie-inbox-data:/var/lib/movie-inbox", compose)
        self.assertIn("target: /media/library/disco1", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("create_host_path: false", compose)
        self.assertIn("/run/secrets/owner_password", compose)
        self.assertIn("cap_drop:\n      - ALL", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertIn("127.0.0.1}", compose)

    def test_omv_example_uses_precreated_read_only_mount_slots(self) -> None:
        compose = (ROOT / "compose.omv.example.yaml").read_text(encoding="utf-8")

        for slot in range(1, 4):
            self.assertIn(f"target: /media/library/disco{slot}", compose)
        self.assertEqual(compose.count("read_only: true"), 3)

    def test_example_environment_contains_no_password(self) -> None:
        environment = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("MOVIE_INBOX_OWNER_PASSWORD_FILE", environment)
        self.assertNotIn("MOVIE_INBOX_OWNER_PASSWORD=", environment)

    def test_ci_builds_imports_and_restarts_the_container(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

        self.assertIn("docker-smoke:", workflow)
        self.assertIn("docker compose build", workflow)
        self.assertIn("docker compose run --rm movie-inbox db import", workflow)
        self.assertIn("docker compose restart movie-inbox", workflow)
        self.assertIn("ReadonlyRootfs", workflow)


if __name__ == "__main__":
    unittest.main()
