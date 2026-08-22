"""Make the local src layout importable for legacy script entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_src() -> None:
    src = Path(__file__).resolve().parents[1] / "src"
    value = str(src)
    if value not in sys.path:
        sys.path.insert(0, value)
