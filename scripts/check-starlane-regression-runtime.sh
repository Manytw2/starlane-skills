#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="$ROOT/.starlane/runtime/starlane-regression"
RUNS="$RUNTIME/runs"

rel() {
  case "$1" in
    "$ROOT"/*) printf '%s\n' "${1#"$ROOT"/}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

size_of() {
  if [ -e "$1" ]; then
    du -sh "$1" 2>/dev/null | awk '{print $1}'
  else
    printf '0B\n'
  fi
}

count_status() {
  status="$1"
  if [ ! -d "$RUNS" ]; then
    printf '0\n'
    return
  fi
  find "$RUNS" -mindepth 2 -maxdepth 2 -name run.json -type f -exec grep -l "\"status\": \"$status\"" {} \; 2>/dev/null | wc -l | tr -d ' '
}

latest_run() {
  if [ ! -d "$RUNS" ]; then
    return
  fi
  find "$RUNS" -mindepth 1 -maxdepth 1 -type d | sort | tail -1
}

latest_failed_run() {
  if [ ! -d "$RUNS" ]; then
    return
  fi
  find "$RUNS" -mindepth 2 -maxdepth 2 -name run.json -type f -exec grep -l '"status": "failed"' {} \; 2>/dev/null \
    | sed 's#/run.json$##' \
    | sort \
    | tail -1
}

total_runs=0
if [ -d "$RUNS" ]; then
  total_runs="$(find "$RUNS" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
fi

tmp_size="0B"
if [ -d "$RUNS" ]; then
  tmp_size="$(find "$RUNS" -mindepth 2 -maxdepth 2 -type d -name tmp -exec du -sk {} + 2>/dev/null | awk '{sum += $1} END {if (sum == "") sum = 0; printf "%.1fM\n", sum / 1024}')"
fi

printf 'Starlane regression runtime status\n\n'
printf 'Runtime dir: %s\n' "$(rel "$RUNTIME")"
printf 'Runs:\n'
printf '  total: %s\n' "$total_runs"
printf '  success: %s\n' "$(count_status success)"
printf '  failed: %s\n' "$(count_status failed)"
printf '  running: %s\n' "$(count_status running)"
printf '\nDisk usage:\n'
printf '  runtime: %s\n' "$(size_of "$RUNTIME")"
printf '  tmp: %s\n' "$tmp_size"

latest="$(latest_run || true)"
if [ -n "${latest:-}" ]; then
  printf '\nLatest run: %s\n' "$(basename "$latest")"
fi

failed="$(latest_failed_run || true)"
if [ -n "${failed:-}" ]; then
  printf 'Latest failed run: %s\n' "$(basename "$failed")"
fi
