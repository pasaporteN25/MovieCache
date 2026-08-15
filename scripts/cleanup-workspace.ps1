<#
.SYNOPSIS
    Moves disposable working-tree clutter into a dated _to_delete/ folder for manual review.

.DESCRIPTION
    This script never deletes anything. It moves each candidate file or folder into
    _to_delete/<timestamp>/, preserving its relative path, so you can look through the
    result and delete what you don't need with normal file-explorer/Recycle Bin safety.

    Review scripts/PLAN.md or the Fase 1 cleanup report before running this. In particular:
      - catalogv2.json, catalogv3_links.json, catalogv4*.json are your real catalog data,
        included here only because they were named explicitly; keep them unless you are
        sure you no longer need those snapshots.
      - check-output.txt is tracked by git (commit 8b84034). Moving it will show as a
        deletion in `git status` until you `git rm --cached` it or restore it.
      - movie-inbox-main.bundle and movie-inbox-v0.1.0.bundle are verified, complete git
        history bundles for a branch named "main" (this repo's current branch is
        "master"). Keep them unless you've confirmed that history is preserved elsewhere.

.NOTES
    Not executed automatically. Run manually after reviewing the list above:
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\cleanup-workspace.ps1
#>

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $root "_to_delete\$stamp"

function Move-ToReview {
    param([string]$RelativePath)
    $source = Join-Path $root $RelativePath
    if (-not (Test-Path $source)) {
        return
    }
    $target = Join-Path $dest $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
    Move-Item -Path $source -Destination $target
    Write-Host "Moved: $RelativePath"
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null

# Reproducible image cache: rebuilds automatically the next time an authenticated
# catalog is opened. ~514 MB / 842 files.
Move-ToReview "scripts\.catalog-cache\images"

# Legacy timestamped backups. Current script versions keep a single reusable
# catalogv3_links.bak.json instead of one per write. ~23 MB / 14 files.
Get-ChildItem -Path (Join-Path $root "scripts") -Filter "catalogv3_links.*.bak.json" -File |
    ForEach-Object { Move-ToReview "scripts\$($_.Name)" }

# Smoke-test catalog snapshots and their timestamped backups. ~17 MB / 5 backup files
# plus the current smoke-catalog.json (~3.8 MB).
Get-ChildItem -Path (Join-Path $root "scripts") -Filter "smoke-catalog.*.bak.json" -File |
    ForEach-Object { Move-ToReview "scripts\$($_.Name)" }
Move-ToReview "scripts\smoke-catalog.json"

# Superseded catalog snapshots -- this is your personal data. Review before deleting.
Move-ToReview "scripts\catalogv2.json"
Move-ToReview "scripts\catalogv3_links.json"
Move-ToReview "scripts\catalogv4.json"
Move-ToReview "scripts\catalogv4.bak.json"

# Stale local check-run output committed by accident. Tracked by git -- see note above.
Move-ToReview "check-output.txt"

# Empty git-init debris: no commits or objects, just default hook templates. Safe to
# discard once moved; nothing here is reproducible because there is nothing in them.
Move-ToReview ".git.failed-init-backup"
Move-ToReview "scripts\.git.empty-backup"
Move-ToReview "scripts\.git.nested-backup"

# Full git-history bundles for branch "main" (verified valid, complete). See note above
# before deleting -- this repo's current branch is "master", not "main".
Move-ToReview "movie-inbox-main.bundle"
Move-ToReview "movie-inbox-v0.1.0.bundle"

Write-Host ""
Write-Host "Everything moved into: $dest"
Write-Host "Nothing was deleted. Review the folder and remove what you don't need."
