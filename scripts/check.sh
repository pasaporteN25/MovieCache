#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

"$PYTHON" -m pip install -e ".[test,dev]"
"$PYTHON" -m ruff check src scripts tests
"$PYTHON" -m ruff format --check src scripts tests
"$PYTHON" -m mypy src/movie_inbox
"$PYTHON" -m compileall -q src scripts tests
"$PYTHON" -m unittest discover -s tests -v
git diff --check
