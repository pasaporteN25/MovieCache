#!/usr/bin/env python3
"""Incrementally reconcile one video library with a Movie Inbox catalog."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.library_scanner import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXTENSIONS,
    FilesystemScanError,
    normalize_excluded_dirs,
    normalize_extensions,
    scan_media_files,
)
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.infrastructure.schema import SCHEMA_VERSION, atomic_write_json

STATE_SCHEMA_VERSION = 1


class ScannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScannerConfig:
    catalog: Path
    state_dir: Path
    library_id: str
    root: Path
    extensions: set[str]
    excluded_dirs: set[str]
    max_missing_ratio: float

    @property
    def state_path(self) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", self.library_id).strip("-") or "library"
        return self.state_dir / f"{safe_id}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Incrementally scan a video library into a Movie Inbox catalog."
    )
    parser.add_argument("--config", type=Path, required=True, help="Scanner JSON configuration.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Update the catalog and scanner state.")
    mode.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing them (default)."
    )
    parser.add_argument(
        "--watch", action="store_true", help="Repeat the scan until interrupted. Requires --apply."
    )
    parser.add_argument(
        "--interval", type=float, default=300.0, help="Seconds between watch scans (minimum 5)."
    )
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    args = parser.parse_args(argv)

    if args.watch and not args.apply:
        parser.error("--watch requires --apply")

    config = load_config(args.config)
    commit = bool(args.apply)
    interval = max(5.0, args.interval)

    if not args.watch:
        try:
            report = run_once(config, commit)
        except (ScannerError, CatalogRepositoryError) as error:
            print(f"Scanner error: {error}")
            return 1
        write_report(args.report, report)
        print_report(report)
        return 0

    print(f"Watching {config.root} every {interval:g} seconds. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                report = run_once(config, True)
                write_report(args.report, report)
                print_report(report)
            except (ScannerError, CatalogRepositoryError) as error:
                print(f"Scanner error: {error}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nScanner stopped.")
    return 0


def load_config(path: Path) -> ScannerConfig:
    config_path = path.resolve()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ScannerError(f"Cannot read config: {config_path}") from error
    except json.JSONDecodeError as error:
        raise ScannerError(f"Invalid config JSON: {config_path} ({error})") from error
    if not isinstance(raw, dict):
        raise ScannerError("Scanner config must be a JSON object")

    libraries = raw.get("libraries")
    if not isinstance(libraries, list) or len(libraries) != 1 or not isinstance(libraries[0], dict):
        raise ScannerError("This scanner version requires exactly one entry in 'libraries'")
    library = libraries[0]
    library_id = str(library.get("id") or "").strip()
    root_value = str(library.get("path") or "").strip()
    catalog_value = str(raw.get("catalog") or "").strip()
    if not library_id or not root_value or not catalog_value:
        raise ScannerError("Config requires catalog, libraries[0].id and libraries[0].path")

    base = config_path.parent
    extensions = normalize_extensions(
        library.get("extensions") or raw.get("extensions") or DEFAULT_EXTENSIONS
    )
    excluded = normalize_excluded_dirs(
        library.get("exclude_dirs") or raw.get("exclude_dirs") or DEFAULT_EXCLUDED_DIRS
    )
    return ScannerConfig(
        catalog=resolve_config_path(catalog_value, base),
        state_dir=resolve_config_path(str(raw.get("state_dir") or ".catalog-state"), base),
        library_id=library_id,
        root=resolve_config_path(root_value, base),
        extensions=extensions,
        excluded_dirs=excluded,
        max_missing_ratio=normalize_ratio(
            library.get("max_missing_ratio", raw.get("max_missing_ratio", 0.5))
        ),
    )


def resolve_config_path(value: str, base: Path) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def normalize_ratio(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def run_once(config: ScannerConfig, commit: bool) -> dict[str, Any]:
    if not config.root.exists() or not config.root.is_dir():
        raise ScannerError(
            f"Library is offline or missing: {config.root}. Catalog removals were not evaluated."
        )

    scanned_at = datetime.now(UTC).isoformat()
    previous_state = read_state(config.state_path, config)
    scanned_files, state_files, errors = scan_files(config, previous_state, scanned_at)
    guard_message = removal_guard(previous_state, state_files, config.max_missing_ratio)
    if guard_message:
        errors.append(guard_message)
    repository = open_catalog_repository(config.catalog, normalize_item)
    service = CatalogService(repository)
    report = service.reconcile_library(
        config.library_id,
        scanned_files,
        scanned_at,
        allow_removals=not errors,
        commit=commit,
    )
    report.update(
        {
            "mode": "apply" if commit else "dry-run",
            "schema_version": SCHEMA_VERSION,
            "library_id": config.library_id,
            "library_root": str(config.root),
            "catalog": str(config.catalog),
            "scanned_at": scanned_at,
            "scan_errors": errors,
        }
    )

    state_updated = False
    if commit and not errors:
        state_payload = {
            "schema_version": STATE_SCHEMA_VERSION,
            "library_id": config.library_id,
            "root": str(config.root),
            "scan_completed_at": scanned_at,
            "complete": not errors,
            "files": state_files,
        }
        atomic_write_json(config.state_path, state_payload, backup_limit=3)
        state_updated = True
    report["state_updated"] = state_updated
    return report


def removal_guard(
    previous_state: dict[str, dict[str, Any]],
    current_state: dict[str, dict[str, Any]],
    max_missing_ratio: float,
) -> str:
    previous_count = len(previous_state)
    if not previous_count:
        return ""
    missing_count = len(set(previous_state) - set(current_state))
    missing_ratio = missing_count / previous_count
    if missing_ratio > max_missing_ratio:
        return (
            f"Removal guard: {missing_count}/{previous_count} prior files are missing "
            f"({missing_ratio:.1%}, configured maximum {max_missing_ratio:.1%})"
        )
    return ""


def read_state(path: Path, config: ScannerConfig) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    if str(raw.get("library_id") or "") != config.library_id or str(raw.get("root") or "") != str(
        config.root
    ):
        return {}
    files = raw.get("files")
    return files if isinstance(files, dict) else {}


def scan_files(
    config: ScannerConfig,
    previous_state: dict[str, dict[str, Any]],
    scanned_at: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    scanned_epoch = int(datetime.fromisoformat(scanned_at).timestamp())
    try:
        scanned_rows, errors = scan_media_files(
            config.root,
            previous_state,
            extensions=config.extensions,
            excluded_dirs=config.excluded_dirs,
            scanned_at=scanned_epoch,
        )
    except FilesystemScanError as error:
        raise ScannerError(str(error)) from error
    rows: list[dict[str, Any]] = []
    state_files: dict[str, dict[str, Any]] = {}
    for scanned in scanned_rows:
        relative_path = str(scanned.get("relative_path") or "")
        rows.append(
            {
                **scanned,
                "path": str((config.root / Path(relative_path)).resolve()),
                "library_id": config.library_id,
                "last_seen_at": scanned_at,
                "available": True,
            }
        )
        state_files[relative_path] = {
            "size_bytes": int(scanned.get("size_bytes") or 0),
            "modified_ns": int(scanned.get("modified_ns") or 0),
            "modified_at": str(scanned.get("modified_at") or ""),
            "fingerprint": str(scanned.get("fingerprint") or ""),
        }
    return rows, state_files, errors


def write_report(path: Path | None, report: dict[str, Any]) -> None:
    if path:
        atomic_write_json(path.resolve(), report, backup_limit=3)


def print_report(report: dict[str, Any]) -> None:
    print("Library scan summary")
    print(f"- Mode: {report.get('mode')}")
    print(f"- Library: {report.get('library_id')} ({report.get('library_root')})")
    print(f"- Video files: {report.get('discovered', 0)}")
    print(f"- Unchanged: {report.get('unchanged', 0)}")
    print(f"- Updated: {report.get('updated', 0)}")
    print(f"- Moved: {report.get('moved', 0)}")
    print(f"- Matched to existing entries: {report.get('matched', 0)}")
    print(f"- New entries: {report.get('created', 0)}")
    print(f"- Marked unavailable: {report.get('unavailable', 0)}")
    print(f"- Needs review: {len(report.get('needs_review') or [])}")
    if report.get("removals_skipped"):
        print("- Removals skipped because the scan was incomplete")
    if report.get("scan_errors"):
        print(f"- Scan errors: {len(report['scan_errors'])}")
    if report.get("mode") == "dry-run":
        print("- No catalog or state files were modified")


if __name__ == "__main__":
    raise SystemExit(main())
