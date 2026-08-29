from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from movie_inbox.external.imdb_datasets import (
    IMDB_DATASETS_BASE_URL,
    download_dataset_file,
)


class _FakeResponse:
    def __init__(self, data: bytes, *, fail_after: int | None = None) -> None:
        self._buffer = io.BytesIO(data)
        self._fail_after = fail_after
        self._served = 0

    def read(self, size: int) -> bytes:
        if self._fail_after is not None and self._served >= self._fail_after:
            raise TimeoutError("connection dropped mid-stream")
        chunk = self._buffer.read(size)
        self._served += len(chunk)
        return chunk

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class DownloadDatasetFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / "title.basics.tsv.gz"

    def test_a_successful_download_writes_the_exact_bytes_and_reports_their_count(
        self,
    ) -> None:
        payload = b"pretend-gzip-bytes" * 1000
        with patch(
            "movie_inbox.external.imdb_datasets.urlopen",
            return_value=_FakeResponse(payload),
        ) as mock_urlopen:
            result = download_dataset_file("title.basics", self.destination)
        self.assertEqual(self.destination.read_bytes(), payload)
        self.assertEqual(result.bytes_downloaded, len(payload))
        self.assertEqual(result.name, "title.basics")
        self.assertEqual(result.url, f"{IMDB_DATASETS_BASE_URL}title.basics.tsv.gz")
        mock_urlopen.assert_called_once()

    def test_an_unknown_dataset_name_is_rejected_before_any_network_call(self) -> None:
        with patch("movie_inbox.external.imdb_datasets.urlopen") as mock_urlopen:
            with self.assertRaises(ValueError):
                download_dataset_file("name.basics", self.destination)
        mock_urlopen.assert_not_called()

    def test_a_stream_interrupted_partway_leaves_no_partial_file_behind(self) -> None:
        payload = b"x" * (5 * 1_048_576)
        with patch(
            "movie_inbox.external.imdb_datasets.urlopen",
            return_value=_FakeResponse(payload, fail_after=1_048_576),
        ):
            with self.assertRaises(TimeoutError):
                download_dataset_file("title.basics", self.destination)
        self.assertFalse(self.destination.exists())
        leftovers = list(self.root.glob(".*.tmp"))
        self.assertEqual(leftovers, [])

    def test_a_dataset_larger_than_one_chunk_is_streamed_in_full(self) -> None:
        payload = b"y" * int(2.5 * 1_048_576)
        with patch(
            "movie_inbox.external.imdb_datasets.urlopen",
            return_value=_FakeResponse(payload),
        ):
            result = download_dataset_file("title.akas", self.destination)
        self.assertEqual(self.destination.read_bytes(), payload)
        self.assertEqual(result.bytes_downloaded, len(payload))


if __name__ == "__main__":
    unittest.main()
