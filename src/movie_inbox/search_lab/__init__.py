"""Packaged fixtures for the deterministic Movie Inbox Search Lab."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


BUILTIN_CORPUS_NAME = "v1.json"


def load_builtin_corpus() -> dict[str, Any]:
    resource = files(__package__).joinpath("corpus", BUILTIN_CORPUS_NAME)
    with resource.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("The packaged Search Lab corpus must be a JSON object")
    return payload


__all__ = ["BUILTIN_CORPUS_NAME", "load_builtin_corpus"]
