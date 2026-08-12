#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$#" -ne 0 ]]; then
  echo "Usage: bash scripts/docker-backup.sh" >&2
  echo "This command does not accept file or wildcard arguments." >&2
  exit 64
fi

PROJECT_DIR=${MOVIE_INBOX_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
APP_SERVICE=${MOVIE_INBOX_APP_SERVICE:-movie-inbox}
BACKUP_SERVICE=${MOVIE_INBOX_BACKUP_SERVICE:-movie-inbox-backup}
LOCK_FILE=${MOVIE_INBOX_BACKUP_LOCK:-/run/lock/movie-inbox-backup.lock}
HEALTH_TIMEOUT_SECONDS=${MOVIE_INBOX_BACKUP_HEALTH_TIMEOUT_SECONDS:-90}

cd "$PROJECT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi
if ! command -v flock >/dev/null 2>&1; then
  echo "flock is required" >&2
  exit 1
fi

resolve_backup_host_path() {
  docker compose --profile maintenance config | awk '
    $1 == "source:" {
      source = $0
      sub(/^[[:space:]]*source:[[:space:]]*/, "", source)
    }
    $1 == "target:" {
      target = $2
      gsub(/^\"|\"$/, "", target)
      if (target == "/backups") {
        print source
        exit
      }
    }
  '
}

prepare_backup_destination() {
  local backup_host_path
  backup_host_path=$(resolve_backup_host_path)
  backup_host_path=${backup_host_path#\"}
  backup_host_path=${backup_host_path%\"}
  backup_host_path=${backup_host_path#\'}
  backup_host_path=${backup_host_path%\'}

  if [[ -z "$backup_host_path" ]]; then
    echo "Could not resolve the host path mounted at /backups." >&2
    echo "Check the $BACKUP_SERVICE volumes with:" >&2
    echo "  docker compose --profile maintenance config" >&2
    exit 1
  fi
  if [[ "$backup_host_path" != /* ]]; then
    backup_host_path="$PROJECT_DIR/$backup_host_path"
  fi

  umask 077
  if ! mkdir -p -- "$backup_host_path"; then
    echo "Could not create backup destination: $backup_host_path" >&2
    exit 1
  fi
  if [[ ! -d "$backup_host_path" || ! -w "$backup_host_path" ]]; then
    echo "Backup destination is not a writable directory: $backup_host_path" >&2
    exit 1
  fi
  echo "Backup destination: $backup_host_path"
}

prepare_backup_destination

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "A Movie Inbox backup is already running; this invocation was skipped."
  exit 0
fi

was_running=0
if docker compose ps --status running --services | grep -Fxq "$APP_SERVICE"; then
  was_running=1
fi

wait_for_health() {
  local container_id status attempts
  container_id=$(docker compose ps -q "$APP_SERVICE")
  if [[ -z "$container_id" ]]; then
    echo "Movie Inbox did not create a container after the backup." >&2
    return 1
  fi
  attempts=$((HEALTH_TIMEOUT_SECONDS / 2))
  for ((index = 0; index < attempts; index++)); do
    status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)
    case "$status" in
      healthy|running)
        echo "Movie Inbox restarted successfully ($status)."
        return 0
        ;;
      unhealthy|exited|dead)
        echo "Movie Inbox failed to restart ($status)." >&2
        return 1
        ;;
    esac
    sleep 2
  done
  echo "Movie Inbox did not become healthy within ${HEALTH_TIMEOUT_SECONDS}s." >&2
  return 1
}

restart_application() {
  local original_status=$?
  trap - EXIT INT TERM
  if [[ "$was_running" -eq 1 ]]; then
    if ! docker compose start "$APP_SERVICE"; then
      original_status=1
    elif ! wait_for_health; then
      original_status=1
    fi
  fi
  exit "$original_status"
}
trap restart_application EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$was_running" -eq 1 ]]; then
  echo "Stopping Movie Inbox for a consistent backup..."
  docker compose stop -t 30 "$APP_SERVICE"
fi

echo "Creating verified instance backup..."
docker compose run --rm --no-deps "$BACKUP_SERVICE"
