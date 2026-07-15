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
    & $python.Source -m pip install -e ".[test]"
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
