"""Build and inspect the deliberately offline [W3] homeserver-package prototype.

This is not an application import/export command. It has no HTTP client or server,
does not extract ZIP files and only supports the explicit manual-trust mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

FORMAT = "movie-inbox-homeserver-package"
SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
PAYLOAD_NAME = "payload.json"
MAX_PAYLOAD_BYTES = 1_048_576
MAX_ITEMS = 500


class PackageError(ValueError):
    """A package is malformed, unsafe or outside this prototype's scope."""


def fail(message: str) -> NoReturn:
    raise PackageError(message)


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    """Parse strict object JSON, rejecting duplicate keys and non-finite numbers."""

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                fail(f"{label} contains a duplicate key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=lambda constant: fail(f"{label} contains {constant}"),
        )
    except UnicodeDecodeError as error:
        fail(f"{label} is not UTF-8: {error}")
    except json.JSONDecodeError as error:
        fail(f"{label} is not valid JSON: {error.msg}")
    if not isinstance(value, dict):
        fail(f"{label} must contain a JSON object")
    return value


def compact_json(value: Mapping[str, Any]) -> bytes:
    """Stable bytes for the prototype integrity digest, not a JCS implementation."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def expect_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        fail(f"{label} must be an object")
    return value


def expect_list(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        fail(f"{label} must be an array")
    return value


def expect_string(value: Any, label: str, minimum: int = 1, maximum: int = 2_000) -> str:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        fail(f"{label} must be a {minimum}-{maximum} character string")
    return value


def expect_integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        fail(f"{label} must be an integer between {minimum} and {maximum}")
    return value


def expect_keys(
    value: Mapping[str, Any], label: str, required: set[str], optional: set[str] | None = None
) -> None:
    allowed = required | (optional or set())
    missing = required - value.keys()
    unknown = value.keys() - allowed
    if missing:
        fail(f"{label} is missing: {', '.join(sorted(missing))}")
    if unknown:
        fail(f"{label} has unsupported fields: {', '.join(sorted(unknown))}")


def expect_uuid(value: Any, label: str) -> str:
    text = expect_string(value, label, 36, 36)
    try:
        parsed = uuid.UUID(text)
    except ValueError:
        fail(f"{label} must be a UUID")
    if str(parsed) != text:
        fail(f"{label} must use lowercase canonical UUID form")
    return text


def validate_payload(payload: Mapping[str, Any]) -> None:
    expect_keys(payload, "payload", {"schema_version", "kind", "collection", "items"})
    if payload["schema_version"] != SCHEMA_VERSION or payload["kind"] != "collection":
        fail("payload has an unsupported format version or kind")
    collection = expect_object(payload["collection"], "payload.collection")
    expect_keys(collection, "payload.collection", {"title", "description"})
    expect_string(collection["title"], "payload.collection.title", 2, 120)
    expect_string(collection["description"], "payload.collection.description", 0, 2_000)
    items = expect_list(payload["items"], "payload.items")
    if not 1 <= len(items) <= MAX_ITEMS:
        fail(f"payload.items must contain 1-{MAX_ITEMS} items")
    expected_positions = list(range(1, len(items) + 1))
    positions: list[int] = []
    for number, raw_item in enumerate(items, start=1):
        item = expect_object(raw_item, f"payload.items[{number}]")
        expect_keys(
            item,
            f"payload.items[{number}]",
            {"position", "title", "kind", "identity"},
            {"original_title", "year", "directors"},
        )
        positions.append(
            expect_integer(item["position"], f"payload.items[{number}].position", 1, MAX_ITEMS)
        )
        expect_string(item["title"], f"payload.items[{number}].title", 1, 500)
        expect_string(item["kind"], f"payload.items[{number}].kind", 1, 40)
        if "original_title" in item:
            expect_string(item["original_title"], f"payload.items[{number}].original_title", 1, 500)
        if "year" in item:
            expect_integer(item["year"], f"payload.items[{number}].year", 1800, 3000)
        if "directors" in item:
            directors = expect_list(item["directors"], f"payload.items[{number}].directors")
            if len(directors) > 12:
                fail(f"payload.items[{number}].directors has too many values")
            for director in directors:
                expect_string(director, f"payload.items[{number}].directors[]", 1, 160)
        identity = expect_object(item["identity"], f"payload.items[{number}].identity")
        expect_keys(
            identity,
            f"payload.items[{number}].identity",
            set(),
            {"imdb_id", "tmdb_id", "wikidata_id", "mal_id"},
        )
        if not identity:
            fail(f"payload.items[{number}].identity needs at least one external ID")
        if "imdb_id" in identity:
            imdb_id = expect_string(
                identity["imdb_id"], f"payload.items[{number}].identity.imdb_id", 7, 14
            )
            if not imdb_id.startswith("tt") or not imdb_id[2:].isdigit():
                fail(f"payload.items[{number}].identity.imdb_id is invalid")
        if "tmdb_id" in identity:
            expect_integer(
                identity["tmdb_id"], f"payload.items[{number}].identity.tmdb_id", 1, 2_147_483_647
            )
        if "wikidata_id" in identity:
            wikidata_id = expect_string(
                identity["wikidata_id"], f"payload.items[{number}].identity.wikidata_id", 2, 32
            )
            if (
                not wikidata_id.startswith("Q")
                or not wikidata_id[1:].isdigit()
                or wikidata_id == "Q0"
            ):
                fail(f"payload.items[{number}].identity.wikidata_id is invalid")
        if "mal_id" in identity:
            expect_integer(
                identity["mal_id"], f"payload.items[{number}].identity.mal_id", 1, 2_147_483_647
            )
    if positions != expected_positions:
        fail("payload.items positions must start at 1 and be contiguous")


def validate_manifest(manifest: Mapping[str, Any], payload_bytes: bytes) -> None:
    expect_keys(
        manifest,
        "manifest",
        {"format", "schema_version", "package_id", "created_at", "source", "payload", "proof"},
    )
    if manifest["format"] != FORMAT or manifest["schema_version"] != SCHEMA_VERSION:
        fail("manifest has an unsupported format version")
    expect_uuid(manifest["package_id"], "manifest.package_id")
    created_at = expect_string(manifest["created_at"], "manifest.created_at", 20, 40)
    try:
        parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        fail("manifest.created_at must be an ISO 8601 timestamp")
    if parsed_created_at.tzinfo is None:
        fail("manifest.created_at must include a timezone")
    source = expect_object(manifest["source"], "manifest.source")
    expect_keys(source, "manifest.source", {"instance_id"})
    expect_uuid(source["instance_id"], "manifest.source.instance_id")
    payload = expect_object(manifest["payload"], "manifest.payload")
    expect_keys(payload, "manifest.payload", {"path", "sha256", "bytes"})
    if payload["path"] != PAYLOAD_NAME:
        fail("manifest.payload.path must be payload.json")
    digest = expect_string(payload["sha256"], "manifest.payload.sha256", 64, 64)
    if any(character not in "0123456789abcdef" for character in digest):
        fail("manifest.payload.sha256 must be lowercase hexadecimal")
    expected_bytes = expect_integer(
        payload["bytes"], "manifest.payload.bytes", 1, MAX_PAYLOAD_BYTES
    )
    if expected_bytes != len(payload_bytes):
        fail("manifest payload byte count does not match payload.json")
    if digest != hashlib.sha256(payload_bytes).hexdigest():
        fail("manifest payload SHA-256 does not match payload.json")
    proof = expect_object(manifest["proof"], "manifest.proof")
    expect_keys(proof, "manifest.proof", {"mode"})
    if proof["mode"] != "manual":
        fail("only manual proof is supported by this offline prototype")


def build_package(
    payload_path: Path,
    output_path: Path,
    instance_id: str,
    package_id: str,
    created_at: str,
) -> dict[str, Any]:
    payload = parse_json(payload_path.read_bytes(), str(payload_path))
    validate_payload(payload)
    payload_bytes = compact_json(payload)
    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        fail("payload exceeds the 1 MiB prototype limit")
    manifest: dict[str, Any] = {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "package_id": package_id,
        "created_at": created_at,
        "source": {"instance_id": instance_id},
        "payload": {
            "path": PAYLOAD_NAME,
            "sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "bytes": len(payload_bytes),
        },
        "proof": {"mode": "manual"},
    }
    validate_manifest(manifest, payload_bytes)
    with zipfile.ZipFile(output_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, compact_json(manifest))
        archive.writestr(PAYLOAD_NAME, payload_bytes)
    return package_summary(manifest, payload)


def inspect_package(package_path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(package_path) as archive:
            names = [entry.filename for entry in archive.infolist()]
            if len(names) != len(set(names)):
                fail("package contains duplicate ZIP entries")
            if set(names) != {MANIFEST_NAME, PAYLOAD_NAME}:
                fail("manual package must contain exactly manifest.json and payload.json")
            for entry in archive.infolist():
                if entry.flag_bits & 0x1:
                    fail("encrypted ZIP entries are not supported")
                if entry.file_size > MAX_PAYLOAD_BYTES:
                    fail("package entry exceeds the 1 MiB prototype limit")
            manifest_bytes = archive.read(MANIFEST_NAME)
            payload_bytes = archive.read(PAYLOAD_NAME)
    except FileNotFoundError:
        fail(f"package does not exist: {package_path}")
    except zipfile.BadZipFile:
        fail("package is not a valid ZIP file")
    if len(manifest_bytes) > MAX_PAYLOAD_BYTES or len(payload_bytes) > MAX_PAYLOAD_BYTES:
        fail("package exceeds the 1 MiB prototype limit")
    manifest = parse_json(manifest_bytes, MANIFEST_NAME)
    payload = parse_json(payload_bytes, PAYLOAD_NAME)
    validate_manifest(manifest, payload_bytes)
    validate_payload(payload)
    return package_summary(manifest, payload)


def package_summary(manifest: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    source = expect_object(manifest["source"], "manifest.source")
    package_payload = expect_object(manifest["payload"], "manifest.payload")
    items = expect_list(payload["items"], "payload.items")
    return {
        "ok": True,
        "network": "none",
        "package_id": manifest["package_id"],
        "source_instance_id": source["instance_id"],
        "collection_title": expect_object(payload["collection"], "payload.collection")["title"],
        "items": len(items),
        "sha256": package_payload["sha256"],
        "trust": "manual confirmation required; SHA-256 is integrity, not a signature",
    }


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    commands = argument_parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build a manual offline package")
    build.add_argument("--input", type=Path, required=True, help="curated payload JSON")
    build.add_argument("--output", type=Path, required=True, help="new .mipkg ZIP path")
    build.add_argument(
        "--instance-id", required=True, help="lowercase UUID for the source instance"
    )
    build.add_argument(
        "--package-id", default=str(uuid.uuid4()), help="lowercase UUID for this package"
    )
    build.add_argument(
        "--created-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        help="ISO 8601 timestamp with timezone",
    )
    inspect = commands.add_parser("inspect", help="verify a manual offline package")
    inspect.add_argument("--package", type=Path, required=True)
    return argument_parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "build":
            result = build_package(
                arguments.input,
                arguments.output,
                arguments.instance_id,
                arguments.package_id,
                arguments.created_at,
            )
        else:
            result = inspect_package(arguments.package)
    except (OSError, PackageError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
