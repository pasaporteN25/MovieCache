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
        self.assertIn('ENTRYPOINT ["movie-inbox"]', dockerfile)

    def test_compose_keeps_state_persistent_and_media_read_only(self) -> None:
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

        self.assertIn("movie-inbox-data:/var/lib/movie-inbox", compose)
        self.assertIn("target: /media/library/disco1", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("create_host_path: false", compose)
        self.assertIn("/run/secrets/owner_password", compose)
        self.assertIn("cap_drop:\n      - ALL", compose)
        self.assertIn("no-new-privileges=true", compose)
        self.assertIn("127.0.0.1}", compose)
        self.assertIn("MOVIE_INBOX_IMAGE_WARM_MODE:-after-access", compose)
        self.assertIn("MOVIE_INBOX_IMAGE_WARM_INTERVAL_SECONDS:-3", compose)
        self.assertIn("movie-inbox-backup:", compose)
        self.assertIn("movie-inbox-data:/var/lib/movie-inbox:ro", compose)
        self.assertIn("MOVIE_INBOX_BACKUP_RETENTION_DAYS:-14", compose)
        self.assertIn("network_mode: none", compose)
        backup_service = compose.split("  movie-inbox-backup:", 1)[1]
        self.assertIn("cap_drop:\n      - ALL", backup_service)
        self.assertIn("cap_add:\n      - DAC_READ_SEARCH", backup_service)

    def test_omv_example_uses_precreated_read_only_mount_slots(self) -> None:
        compose = (ROOT / "compose.omv.example.yaml").read_text(encoding="utf-8")

        for slot in range(1, 4):
            self.assertIn(f"target: /media/library/disco{slot}", compose)
        self.assertEqual(compose.count("read_only: true"), 3)

    def test_example_environment_contains_no_password(self) -> None:
        environment = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("MOVIE_INBOX_OWNER_PASSWORD_FILE", environment)
        self.assertIn("MOVIE_INBOX_IMAGE_WARM_MODE=after-access", environment)
        self.assertIn("MOVIE_INBOX_IMAGE_WARM_INTERVAL_SECONDS=3", environment)
        self.assertIn("MOVIE_INBOX_BACKUP_PATH=./backups", environment)
        self.assertIn("MOVIE_INBOX_BACKUP_RETENTION_DAYS=14", environment)
        self.assertNotIn("MOVIE_INBOX_OWNER_PASSWORD=", environment)

    def test_scheduled_backup_stops_restarts_and_health_checks_the_service(self) -> None:
        script = (ROOT / "scripts" / "docker-backup.sh").read_text(encoding="utf-8")
        service = (ROOT / "deploy" / "movie-inbox-backup.service.example").read_text(
            encoding="utf-8"
        )
        timer = (ROOT / "deploy" / "movie-inbox-backup.timer.example").read_text(encoding="utf-8")

        self.assertIn("flock -n", script)
        self.assertIn("resolve_backup_host_path", script)
        self.assertIn("docker compose --profile maintenance config", script)
        self.assertIn("This command does not accept file or wildcard arguments.", script)
        self.assertIn('mkdir -p -- "$backup_host_path"', script)
        self.assertIn("Backup destination:", script)
        self.assertIn('docker compose stop -t 30 "$APP_SERVICE"', script)
        self.assertIn('docker compose run --rm --no-deps "$BACKUP_SERVICE"', script)
        self.assertIn('docker compose start "$APP_SERVICE"', script)
        self.assertIn("wait_for_health", script)
        self.assertIn("ExecStart=/usr/bin/bash /opt/movie-inbox/scripts/docker-backup.sh", service)
        self.assertIn("OnCalendar=*-*-* 03:30:00", timer)
        self.assertIn("Persistent=true", timer)

    def test_ci_builds_imports_and_restarts_the_container(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

        self.assertIn("docker-smoke:", workflow)
        self.assertIn("docker compose build", workflow)
        self.assertIn("docker compose run --rm movie-inbox db import", workflow)
        self.assertIn("docker compose restart movie-inbox", workflow)
        self.assertIn(".private-backup-smoke", workflow)
        self.assertIn("ReadonlyRootfs", workflow)
        self.assertIn("test ! -w /imports", workflow)


if __name__ == "__main__":
    unittest.main()
