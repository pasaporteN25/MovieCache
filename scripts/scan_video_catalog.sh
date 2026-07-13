#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  scan_video_catalog.sh [MOVIES_DIR] [--json output.json] [--verbose]

Scans MOVIES_DIR recursively and emits catalog-compatible JSON for video files.
When MOVIES_DIR is omitted, the current directory is scanned.
Subtitles, folders and non-video files are ignored.
EOF
}

ROOT="."
OUTPUT=""
VERBOSE=0
TOTAL_FILES=0
VIDEO_FILES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      OUTPUT=${2:-}
      if [[ -z "$OUTPUT" ]]; then
        usage
        exit 2
      fi
      shift 2
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ "$ROOT" == "." ]]; then
        ROOT=$1
        shift
      else
        echo "Unknown argument: $1" >&2
        usage
        exit 2
      fi
      ;;
  esac
done

if [[ ! -d "$ROOT" ]]; then
  echo "Directory not found: $ROOT" >&2
  exit 1
fi

ROOT=$(cd "$ROOT" && pwd)

json_escape() {
  local value=${1:-}
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\t'/\\t}
  value=${value//$'\r'/}
  value=${value//$'\n'/ }
  printf '%s' "$value"
}

is_video_file() {
  local file=$1
  local ext=${file##*.}
  ext=${ext,,}
  case "$ext" in
    3g2|3gp|asf|avi|divx|flv|m2ts|m4v|mkv|mov|mp4|mpeg|mpg|mts|ogm|ogv|rmvb|ts|vob|webm|wmv)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

clean_title() {
  local name=$1
  name=${name%.*}
  name=${name//./ }
  name=${name//_/ }
  name=${name//-/ }
  name=$(printf '%s' "$name" | sed -E '
    s/[[:space:]]+/ /g;
    s/[[:space:]]*(19[0-9]{2}|20[0-9]{2}).*/ \1/;
    s/[[:space:]]+(480p|576p|720p|1080p|2160p|4k|8k).*//I;
    s/[[:space:]]+(bluray|blu ray|brrip|bdrip|webrip|web dl|webdl|hdrip|dvdrip|hdtv).*//I;
    s/[[:space:]]+(x264|x265|h264|h265|hevc|avc|aac|dts|ac3|yify|rarbg).*//I;
    s/[[:space:]]+$//;
    s/^[[:space:]]+//;
  ')
  printf '%s' "$name"
}

item_id() {
  local value=$1
  if command -v sha1sum >/dev/null 2>&1; then
    printf '%s' "$value" | sha1sum | awk '{print substr($1, 1, 12)}'
  else
    printf 'local-%s' "$(printf '%s' "$value" | cksum | awk '{print $1}')"
  fi
}

emit_json() {
  local first=1
  local now
  now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  echo "Scanning: $ROOT" >&2
  printf '{\n  "schema_version": 3,\n  "items": [\n'
  while IFS= read -r -d '' file; do
    TOTAL_FILES=$((TOTAL_FILES + 1))
    if ! is_video_file "$file"; then
      if [[ "$VERBOSE" -eq 1 ]]; then
        echo "skip: $file" >&2
      fi
      continue
    fi
    VIDEO_FILES=$((VIDEO_FILES + 1))

    local local_name
    local local_path
    local title
    local id
    local_name=$(basename "$file")
    local_path=${file#"$ROOT"/}
    title=$(clean_title "$local_name")
    id=$(item_id "$local_path")

    if [[ "$VERBOSE" -eq 1 ]]; then
      echo "video: $local_path" >&2
    fi

    if [[ $first -eq 0 ]]; then
      printf ',\n'
    fi
    first=0

    printf '  {\n'
    printf '    "id": "%s",\n' "$(json_escape "$id")"
    printf '    "url": "",\n'
    printf '    "source": "local_files",\n'
    printf '    "title": "%s",\n' "$(json_escape "$title")"
    printf '    "original_title": "",\n'
    printf '    "spanish_title": "",\n'
    printf '    "english_title": "",\n'
    printf '    "alternative_titles": [],\n'
    printf '    "kind": "pelicula",\n'
    printf '    "status": "to_watch",\n'
    printf '    "watched_at": "",\n'
    printf '    "rating": 0,\n'
    printf '    "year": "",\n'
    printf '    "description": "",\n'
    printf '    "wikipedia_url": "",\n'
    printf '    "imdb_url": "",\n'
    printf '    "filmaffinity_url": "",\n'
    printf '    "wikipedia_title": "",\n'
    printf '    "wikidata_id": "",\n'
    printf '    "genres": [],\n'
    printf '    "directors": [],\n'
    printf '    "writers": [],\n'
    printf '    "cast": [],\n'
    printf '    "page_image": "",\n'
    printf '    "wikipedia_extract": "",\n'
    printf '    "en_catalogo": true,\n'
    printf '    "local_files": [{"path": "%s", "name": "%s", "size_bytes": 0, "modified_at": "", "part": ""}],\n' "$(json_escape "$local_path")" "$(json_escape "$local_name")"
    printf '    "local_name": "%s",\n' "$(json_escape "$local_name")"
    printf '    "local_path": "%s",\n' "$(json_escape "$local_path")"
    printf '    "tags": [],\n'
    printf '    "notes": "",\n'
    printf '    "review": "",\n'
    printf '    "metadata_sources": {"title": {"source": "local_files", "url": "", "updated_at": "%s", "inferred": false}, "kind": {"source": "local_files", "url": "", "updated_at": "%s", "inferred": false}},\n' "$now" "$now"
    printf '    "locked_fields": [],\n'
    printf '    "added_at": "%s"\n' "$now"
    printf '  }'
  done < <(find "$ROOT" -type f -print0)
  printf '\n  ]\n}\n'
}

if [[ -n "$OUTPUT" ]]; then
  emit_json > "$OUTPUT"
  echo "Wrote JSON: $OUTPUT" >&2
else
  emit_json
fi

echo "Files found: $TOTAL_FILES" >&2
echo "Video files exported: $VIDEO_FILES" >&2
if [[ "$VIDEO_FILES" -eq 0 ]]; then
  echo "No video files matched the configured extensions." >&2
fi
