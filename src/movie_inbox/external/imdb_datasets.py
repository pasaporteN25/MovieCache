"""Download IMDb's official non-commercial bulk TSV datasets.

Scope: [F1] in tareas.md. `external/common.py`'s `fetch_text`/`fetch_json`
cap the response at `read(800_000)` and always text-decode it, which is
unusable for a multi-hundred-MB gzip binary — this module streams straight
to disk instead, reusing only the same `User-Agent` convention.
`download_dataset_file` is the seam tests mock, matching this codebase's
existing convention of patching the importing module's own bound name.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

IMDB_DATASETS_BASE_URL = "https://datasets.imdbws.com/"
AVAILABLE_DATASETS = ("title.basics", "title.akas")

_USER_AGENT = "MovieInbox/0.2 (+local personal catalog)"
_CHUNK_SIZE = 1_048_576


@dataclass(frozen=True)
class DownloadResult:
    name: str
    url: str
    bytes_downloaded: int
    elapsed_seconds: float


def download_dataset_file(name: str, destination: Path, *, timeout: float = 30.0) -> DownloadResult:
    if name not in AVAILABLE_DATASETS:
        raise ValueError(
            f"Unknown IMDb dataset {name!r}; available: {', '.join(AVAILABLE_DATASETS)}"
        )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = f"{IMDB_DATASETS_BASE_URL}{name}.tsv.gz"
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    started = time.monotonic()
    bytes_downloaded = 0
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            delete=False,
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
        ) as handle:
            temporary_path = Path(handle.name)
            with urlopen(request, timeout=timeout) as response:
                while True:
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    bytes_downloaded += len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return DownloadResult(
        name=name,
        url=url,
        bytes_downloaded=bytes_downloaded,
        elapsed_seconds=time.monotonic() - started,
    )
