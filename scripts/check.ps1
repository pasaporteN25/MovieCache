$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "Python was not found. Install Python 3.11 or newer and reopen the terminal."
}

Push-Location $root
try {
    & $python.Source -m pip install -e ".[test,dev]"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python.Source -m ruff check src scripts tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python.Source -m ruff format --check src scripts tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $mypyTargets = @(
        "src/movie_inbox/domain"
        "src/movie_inbox/application/auth_service.py"
        "src/movie_inbox/application/collection_repository.py"
        "src/movie_inbox/application/curation_history.py"
        "src/movie_inbox/application/identity_repository.py"
        "src/movie_inbox/application/import_repository.py"
        "src/movie_inbox/application/library_repository.py"
        "src/movie_inbox/application/member_service.py"
        "src/movie_inbox/application/privacy_service.py"
        "src/movie_inbox/application/repository.py"
        "src/movie_inbox/application/scanner_history.py"
    )
    & $python.Source -m mypy @mypyTargets
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python.Source -m compileall -q src scripts tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python.Source -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    git diff --check
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
