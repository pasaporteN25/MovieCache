"""Packaged fixtures for the deterministic Movie Inbox Search Lab."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

BUILTIN_CORPUS_NAME = "v1.json"
BUILTIN_EXTERNAL_DIAGNOSTICS_CORPUS_NAME = "external_diagnostics_v1.json"


def _load_corpus(name: str) -> dict[str, Any]:
    resource = files(__package__).joinpath("corpus", name)
    with resource.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("The packaged Search Lab corpus must be a JSON object")
    return payload


def load_builtin_corpus() -> dict[str, Any]:
    return _load_corpus(BUILTIN_CORPUS_NAME)


def load_builtin_external_diagnostics_corpus() -> dict[str, Any]:
    return _load_corpus(BUILTIN_EXTERNAL_DIAGNOSTICS_CORPUS_NAME)


__all__ = [
    "BUILTIN_CORPUS_NAME",
    "BUILTIN_EXTERNAL_DIAGNOSTICS_CORPUS_NAME",
    "load_builtin_corpus",
    "load_builtin_external_diagnostics_corpus",
]
