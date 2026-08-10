from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.image_proxy import (
    IMAGE_CONTENT_EXTENSIONS,
    cached_image,
    cached_image_keys,
    clear_image_cache,
    download_image,
    image_cache_key,
    image_cache_info,
    image_is_cached,
    prune_image_cache,
)


class ImageCacheTests(unittest.TestCase):
    def test_cache_writes_atomically_and_reuses_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache_dir = Path(temporary) / "images"
            config = ViewerConfig(
                patterns=["catalog.json"],
                title="test",
                write_json="catalog.json",
                image_cache=True,
                image_cache_dir=str(cache_dir),
                image_cache_max_bytes=1024,
                image_cache_total_bytes=2048,
                image_allowed_hosts=("images.example.com",),
                port=8765,
                api_token="token",
            )
            png = b"\x89PNG\r\n\x1a\n" + b"content"
            with (
                patch("movie_inbox.web.image_proxy.validate_http_url", side_effect=lambda url, *_: url),
                patch("movie_inbox.web.image_proxy.download_image", return_value=(png, "image/png")) as download,
            ):
                self.assertEqual(cached_image(config, "https://images.example.com/a.png"), (png, "image/png"))
                self.assertEqual(cached_image(config, "https://images.example.com/a.png"), (png, "image/png"))
            self.assertEqual(download.call_count, 1)
            self.assertEqual(len(list(cache_dir.glob("*.png"))), 1)
            self.assertEqual(list(cache_dir.glob("*.tmp")), [])
            self.assertIn(image_cache_key("https://images.example.com/a.png"), cached_image_keys(cache_dir))
            with patch("movie_inbox.web.image_proxy.validate_http_url", side_effect=lambda url, *_: url):
                self.assertTrue(image_is_cached(config, "https://images.example.com/a.png"))

    def test_lru_prune_removes_oldest_files_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache_dir = Path(temporary)
            paths = [cache_dir / name for name in ("old.jpg", "middle.png", "new.webp")]
            for index, path in enumerate(paths, start=1):
                path.write_bytes(b"x" * 10)
                os.utime(path, (index, index))
            result = prune_image_cache(cache_dir, 20)
            self.assertFalse(paths[0].exists())
            self.assertTrue(paths[1].exists())
            self.assertTrue(paths[2].exists())
            self.assertEqual(result.removed_files, 1)
            self.assertEqual(result.total_bytes, 20)

    def test_cache_info_and_clear_include_all_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache_dir = Path(temporary)
            (cache_dir / "one.jpg").write_bytes(b"123")
            (cache_dir / "legacy.svg").write_bytes(b"4567")
            self.assertEqual(image_cache_info(cache_dir).total_bytes, 7)
            cleared = clear_image_cache(cache_dir)
            self.assertEqual(cleared.removed_files, 2)
            self.assertEqual(list(cache_dir.iterdir()), [])

    def test_svg_is_not_a_supported_proxy_format(self) -> None:
        self.assertNotIn("image/svg+xml", IMAGE_CONTENT_EXTENSIONS)

        class Headers:
            @staticmethod
            def get_content_type() -> str:
                return "image/svg+xml"

            @staticmethod
            def get(_: str) -> str | None:
                return None

        class Response:
            headers = Headers()

            def __enter__(self):
                return self

            def __exit__(self, *_: object) -> None:
                return None

            @staticmethod
            def read(_: int) -> bytes:
                return b"<svg></svg>"

        with patch("movie_inbox.web.image_proxy.open_public_url", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "supported raster image"):
                download_image("https://images.example.com/poster.svg", 1024, ("images.example.com",))


if __name__ == "__main__":
    unittest.main()
