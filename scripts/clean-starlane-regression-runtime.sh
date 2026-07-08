#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="$ROOT/.starlane/runtime/starlane-regression"
RUNS="$RUNTIME/runs"
DRY_RUN=1
FORCE=0
CLEAN_SUCCESS_TMP=0
KEEP_LAST=""

usage() {
  cat <<'EOF'
Usage:
  scripts/clean-starlane-regression-runtime.sh [--dry-run]
  scripts/clean-starlane-regression-runtime.sh --success-tmp --force
  scripts/clean-starlane-regression-runtime.sh --keep-last N --force

Options:
  --dry-run       Print what would be deleted. Default.
  --force         Actually delete selected runtime paths.
  --success-tmp   Delete tmp/ directories for successful runs.
  --keep-last N   Delete older run directories, keeping the newest N.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --force)
      FORCE=1
      DRY_RUN=0
      ;;
    --success-tmp)
      CLEAN_SUCCESS_TMP=1
      ;;
    --keep-last)
      shift
      if [ "$#" -eq 0 ]; then
        echo "--keep-last requires a number" >&2
        exit 2
      fi
      KEEP_LAST="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

case "$KEEP_LAST" in
  ""|*[!0-9]*)
    if [ -n "$KEEP_LAST" ]; then
      echo "--keep-last must be a non-negative integer" >&2
      exit 2
    fi
    ;;
esac

if [ "$CLEAN_SUCCESS_TMP" -eq 0 ] && [ -z "$KEEP_LAST" ]; then
  echo "No cleanup target selected."
  echo "Dry run only. Add --success-tmp or --keep-last N, then --force to delete."
  exit 0
fi

if [ ! -d "$RUNS" ]; then
  echo "No runtime runs found: ${RUNS#$ROOT/}"
  exit 0
fi

ensure_safe_path() {
  target="$1"
  case "$target" in
    "$RUNS"/*) ;;
    *)
      echo "Refusing to delete outside runtime runs: $target" >&2
      exit 1
      ;;
  esac
}

delete_path() {
  target="$1"
  ensure_safe_path "$target"
  if [ ! -e "$target" ]; then
    return
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "Would delete: ${target#$ROOT/}"
  else
    rm -rf "$target"
    echo "Deleted: ${target#$ROOT/}"
  fi
}

if [ "$CLEAN_SUCCESS_TMP" -eq 1 ]; then
  find "$RUNS" -mindepth 2 -maxdepth 2 -name run.json -type f -exec grep -l '"status": "success"' {} \; 2>/dev/null \
    | sed 's#/run.json$#/tmp#' \
    | while IFS= read -r tmp_dir; do
        delete_path "$tmp_dir"
      done
fi

if [ -n "$KEEP_LAST" ]; then
  total="$(find "$RUNS" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
  if [ "$total" -gt "$KEEP_LAST" ]; then
    delete_count=$((total - KEEP_LAST))
    find "$RUNS" -mindepth 1 -maxdepth 1 -type d | sort | head -n "$delete_count" \
      | while IFS= read -r run_dir; do
          delete_path "$run_dir"
        done
  fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry run only. Re-run with --force to delete."
fi
