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
"$PYTHON" -m mypy \
  src/movie_inbox/domain \
  src/movie_inbox/application/auth_service.py \
  src/movie_inbox/application/collection_repository.py \
  src/movie_inbox/application/curation_history.py \
  src/movie_inbox/application/identity_repository.py \
  src/movie_inbox/application/import_repository.py \
  src/movie_inbox/application/library_repository.py \
  src/movie_inbox/application/member_service.py \
  src/movie_inbox/application/privacy_service.py \
  src/movie_inbox/application/repository.py \
  src/movie_inbox/application/scanner_history.py
"$PYTHON" -m compileall -q src scripts tests
"$PYTHON" -m unittest discover -s tests -v
git diff --check
