from __future__ import annotations

import tempfile
import time
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.image_proxy import image_cache_key
from movie_inbox.web.image_warmer import ImageCacheWarmer


class ImageCacheWarmerTests(unittest.TestCase):
    def test_worker_starts_after_registration_and_deduplicates_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            calls: list[str] = []
            config = self.config(Path(temporary))

            def fetcher(_: ViewerConfig, image_url: str) -> tuple[bytes, str]:
                self.cache_file(config, image_url)
                calls.append(image_url)
                return b"image", "image/jpeg"

            warmer = ImageCacheWarmer(config, interval_seconds=0.01, fetcher=fetcher)
            self.assertFalse(warmer.status("catalog:one")["worker"]["running"])
            try:
                with self.validation_patches(config):
                    warmer.register_items(
                        "catalog:one",
                        [
                            {
                                "page_image": "https://images.example.com/a.jpg",
                                "backdrop_image": "https://images.example.com/background.jpg",
                            },
                            {"page_image": "https://images.example.com/a.jpg"},
                            {"page_image": "https://images.example.com/b.jpg"},
                            {},
                        ],
                    )
                    self.assertTrue(self.wait_until(lambda: len(calls) == 3))
                    status = warmer.status("catalog:one", include_global=True)
            finally:
                warmer.stop()

            self.assertEqual(
                calls,
                [
                    "https://images.example.com/a.jpg",
                    "https://images.example.com/b.jpg",
                    "https://images.example.com/background.jpg",
                ],
            )
            self.assertEqual(status["personal"]["state"], "complete")
            self.assertEqual(status["personal"]["available"], 2)
            self.assertEqual(status["personal"]["without_url"], 1)
            self.assertEqual(status["global"]["registered_scopes"], 1)
            self.assertEqual(status["global"]["available"], 3)

    def test_foreground_request_is_not_delayed_by_the_background_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            calls: list[str] = []
            config = self.config(Path(temporary))
            first = "https://images.example.com/first.jpg"
            second = "https://images.example.com/second.jpg"

            def fetcher(_: ViewerConfig, image_url: str) -> tuple[bytes, str]:
                self.cache_file(config, image_url)
                calls.append(image_url)
                return b"image", "image/jpeg"

            warmer = ImageCacheWarmer(config, interval_seconds=0.01, fetcher=fetcher)
            try:
                with self.validation_patches(config), warmer.foreground(first):
                    warmer.register_items(
                        "catalog:one",
                        [{"page_image": first}, {"page_image": second}],
                    )
                    self.assertTrue(self.wait_until(lambda: bool(calls)))
                    self.assertEqual(calls[0], second)
                with self.validation_patches(config):
                    self.assertTrue(self.wait_until(lambda: len(calls) == 2))
            finally:
                warmer.stop()

            self.assertEqual(calls, [second, first])

    def test_failed_downloads_back_off_and_stop_after_the_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            calls = 0
            should_fail = True
            config = self.config(Path(temporary))
            image_url = "https://images.example.com/error.jpg"

            def fetcher(_: ViewerConfig, current_url: str) -> tuple[bytes, str]:
                nonlocal calls, should_fail
                calls += 1
                if should_fail:
                    raise OSError("temporary failure")
                self.cache_file(config, current_url)
                return b"image", "image/jpeg"

            warmer = ImageCacheWarmer(
                config,
                interval_seconds=0,
                max_attempts=2,
                fetcher=fetcher,
            )
            try:
                with self.validation_patches(config):
                    warmer.register_items(
                        "catalog:one",
                        [{"page_image": image_url}],
                    )
                    self.assertTrue(
                        self.wait_until(
                            lambda: warmer.status("catalog:one")["personal"]["state"] == "error",
                            timeout=2,
                        )
                    )
                    failed_status = warmer.status("catalog:one")
                    should_fail = False
                    warmer.register_items("catalog:one", [{"page_image": image_url}])
                    self.assertTrue(
                        self.wait_until(
                            lambda: warmer.status("catalog:one")["personal"]["state"] == "complete",
                            timeout=1,
                        )
                    )
            finally:
                warmer.stop()

            self.assertEqual(calls, 3)
            self.assertEqual(failed_status["personal"]["failed"], 1)
            self.assertEqual(failed_status["personal"]["pending"], 0)

    def test_disabled_warming_never_starts_a_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.config(Path(temporary), image_cache_warm=False)
            warmer = ImageCacheWarmer(config, fetcher=lambda *_: (b"", "image/jpeg"))
            with self.validation_patches(config):
                warmer.register_items(
                    "catalog:one",
                    [{"page_image": "https://images.example.com/a.jpg"}],
                )
                status = warmer.status("catalog:one")

            self.assertFalse(status["worker"]["running"])
            self.assertEqual(status["personal"]["state"], "disabled")
            self.assertEqual(status["personal"]["queued"], 0)

    def test_rejected_poster_is_reported_without_starting_a_download(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.config(Path(temporary))
            warmer = ImageCacheWarmer(config, fetcher=lambda *_: (b"", "image/jpeg"))
            with patch(
                "movie_inbox.web.image_warmer.validate_http_url",
                side_effect=ValueError("blocked"),
            ):
                warmer.register_items(
                    "catalog:one",
                    [{"page_image": "http://127.0.0.1/private.jpg"}],
                )
            status = warmer.status("catalog:one")

            self.assertFalse(status["worker"]["running"])
            self.assertEqual(status["personal"]["state"], "error")
            self.assertEqual(status["personal"]["rejected"], 1)

    def test_unreadable_cache_is_reported_instead_of_breaking_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.config(Path(temporary))
            warmer = ImageCacheWarmer(config)
            warmer.register_items("catalog:one", [])
            with patch(
                "movie_inbox.web.image_warmer.cached_image_keys",
                side_effect=OSError("permission denied"),
            ):
                status = warmer.status("catalog:one")

            self.assertEqual(status["personal"]["state"], "error")
            self.assertEqual(status["worker"]["cache_error"], "cache_unavailable")

    @contextmanager
    def validation_patches(self, config: ViewerConfig) -> Iterator[None]:
        with (
            patch(
                "movie_inbox.web.image_warmer.validate_http_url",
                side_effect=lambda url, *_: url,
            ),
            patch(
                "movie_inbox.web.image_warmer.image_is_cached",
                side_effect=lambda _, url: (
                    Path(config.image_cache_dir) / f"{image_cache_key(url)}.jpg"
                ).is_file(),
            ),
        ):
            yield

    @staticmethod
    def config(cache_dir: Path, *, image_cache_warm: bool = True) -> ViewerConfig:
        return ViewerConfig(
            patterns=["catalog.json"],
            title="test",
            write_json="catalog.json",
            image_cache=True,
            image_cache_dir=str(cache_dir),
            image_cache_max_bytes=1024,
            image_cache_total_bytes=4096,
            image_cache_warm=image_cache_warm,
            image_allowed_hosts=("images.example.com",),
            port=8765,
            api_token="token",
        )

    @staticmethod
    def cache_file(config: ViewerConfig, image_url: str) -> None:
        cache_dir = Path(config.image_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{image_cache_key(image_url)}.jpg").write_bytes(b"image")

    @staticmethod
    def wait_until(predicate, *, timeout: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return bool(predicate())


if __name__ == "__main__":
    unittest.main()
