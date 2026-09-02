from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DockerPackagingTests(unittest.TestCase):
    def test_local_check_scripts_include_the_ci_lint_gate(self) -> None:
        powershell = (ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")
        shell = (ROOT / "scripts" / "check.sh").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        mypy_configuration = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        for script in (powershell, shell):
            self.assertIn(".[test,dev]", script)
            self.assertIn("ruff check src scripts tests", script)
            self.assertIn("ruff format --check src scripts tests", script)

        strict_targets = ("src/movie_inbox", "tests")
        for target in strict_targets:
            for gate in (powershell, shell, workflow):
                self.assertIn(target, gate)
        self.assertIn("strict = true", mypy_configuration)
        self.assertNotIn("ignore_errors = true", mypy_configuration)
        self.assertIn('module = "tests.browser.*"', mypy_configuration)
        self.assertIn('disable_error_code = ["attr-defined"]', mypy_configuration)

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
        self.assertIn("--public-presentation-origin", compose)
        self.assertIn("MOVIE_INBOX_PUBLIC_PRESENTATION_ORIGIN", compose)
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
        self.assertIn("MOVIE_INBOX_PUBLIC_PRESENTATION_ORIGIN=", environment)
        self.assertNotIn("MOVIE_INBOX_OWNER_PASSWORD=", environment)

    def test_nginx_templates_keep_private_and_capability_routes_separate(self) -> None:
        full = (ROOT / "deploy" / "nginx.movie-inbox.conf.example").read_text(encoding="utf-8")
        bootstrap = (ROOT / "deploy" / "nginx.movie-inbox.http-bootstrap.conf.example").read_text(
            encoding="utf-8"
        )

        self.assertIn("server_name inbox.example.com", full)
        self.assertIn("server_name cartelera.example.com", full)
        self.assertIn("location ^~ /p/", full)
        self.assertIn("location ^~ /public/", full)
        self.assertIn("location / { return 404; }", full)
        self.assertIn("proxy_set_header X-Forwarded-For $remote_addr", full)
        self.assertNotIn("$proxy_add_x_forwarded_for", full)
        self.assertGreaterEqual(full.count("access_log off"), 4)
        self.assertIn("/.well-known/acme-challenge/", bootstrap)
        self.assertIn("location / { return 404; }", bootstrap)

    def test_tmdb_compose_overlay_is_opt_in_and_file_backed(self) -> None:
        base_compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        overlay = (ROOT / "compose.tmdb.example.yaml").read_text(encoding="utf-8")
        environment = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertNotIn("tmdb_read_access_token", base_compose)
        self.assertIn("/run/secrets/tmdb_read_access_token", overlay)
        self.assertIn("MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE", overlay)
        self.assertIn("# MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE=", environment)
        self.assertNotIn("MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN=", environment)

    def test_anime_offline_overlay_is_opt_in_and_read_only(self) -> None:
        base_compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        overlay = (ROOT / "compose.anime-offline.example.yaml").read_text(encoding="utf-8")
        environment = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertNotIn("MOVIE_INBOX_ANIME_OFFLINE_INDEX", base_compose)
        self.assertIn("MOVIE_INBOX_ANIME_OFFLINE_INDEX: /anime-index/anime-offline.db", overlay)
        self.assertIn("MOVIE_INBOX_ANIME_INDEX_DIR", overlay)
        self.assertIn("target: /anime-index", overlay)
        self.assertIn("read_only: true", overlay)
        self.assertIn("create_host_path: false", overlay)
        self.assertIn("# MOVIE_INBOX_ANIME_INDEX_DIR=", environment)

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
        self.assertIn("verify_backup_destination", script)
        self.assertIn('--entrypoint sh "$BACKUP_SERVICE"', script)
        self.assertIn("test -d /backups && test -w /backups", script)
        self.assertNotIn('! -w "$backup_host_path"', script)
        self.assertIn('gsub(/^"|"$/, "", target)', script)
        self.assertNotIn(r'gsub(/^\"|\"$/, "", target)', script)
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
        self.assertIn("for compose_attempt in 1 2", workflow)
        self.assertIn('test "$compose_started" = "true"', workflow)
        self.assertIn("docker compose restart movie-inbox", workflow)
        self.assertIn(".private-backup-smoke", workflow)
        self.assertIn("--entrypoint python movie-inbox-backup", workflow)
        self.assertIn('tarfile.open(sys.argv[1], "r:gz")', workflow)
        self.assertNotIn('tar -tzf "$archive"', workflow)
        self.assertIn("ReadonlyRootfs", workflow)
        self.assertIn("test ! -w /imports", workflow)
        self.assertIn("Validate Nginx proxy templates", workflow)
        self.assertIn("nginx:stable-alpine nginx -t", workflow)


if __name__ == "__main__":
    unittest.main()
