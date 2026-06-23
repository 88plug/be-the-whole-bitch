#!/usr/bin/env bash
# resolve-paths.sh — shared paths for be-the-whole-bitch hooks.

BTWB_PLUGIN_SLUG="be-the-whole-bitch-88plug"

: "${CLAUDE_CONFIG_DIR:=${HOME}/.claude}"

if [ -z "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  _btwb_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  CLAUDE_PLUGIN_ROOT="$(cd "${_btwb_lib_dir}/../.." && pwd)"
fi

btwb_resolve_data_root() {
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    printf '%s\n' "${CLAUDE_PLUGIN_DATA}"
    return 0
  fi
  local base="${CLAUDE_CONFIG_DIR}/plugins/data"
  local exact="${base}/${BTWB_PLUGIN_SLUG}"
  if [ -d "${exact}" ]; then
    printf '%s\n' "${exact}"
    return 0
  fi
  local g
  for g in "${base}"/be-the-whole-bitch*; do
    if [ -d "${g}" ]; then
      printf '%s\n' "${g}"
      return 0
    fi
  done
  printf '%s\n' "${exact}"
}

BTWB_DATA_ROOT="$(btwb_resolve_data_root)"
BTWB_MARKERS_DIR="${BTWB_DATA_ROOT}/markers"
BTWB_LOGS_DIR="${BTWB_DATA_ROOT}/logs"
BTWB_SCORE_PY="${CLAUDE_PLUGIN_ROOT}/bin/btwb_score.py"
BTWB_PROFILE="${CLAUDE_PLUGIN_ROOT}/profiles/default.json"

btwb_ensure_dirs() {
  mkdir -p "${BTWB_MARKERS_DIR}" "${BTWB_LOGS_DIR}" 2>/dev/null || true
}

btwb_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  return 1
}

btwb_slug() {
  printf '%s' "${1:-unknown}" | sed 's/[^a-zA-Z0-9._-]/_/g' | head -c 64
}

btwb_atomic_write() {
  local dest="$1"
  local mode="${2:-0600}"
  local tmp
  tmp="$(mktemp "${dest}.XXXXXX")"
  cat >"${tmp}"
  chmod "${mode}" "${tmp}" 2>/dev/null || true
  mv -f "${tmp}" "${dest}"
}

btwb_log_debug() {
  btwb_ensure_dirs
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"${BTWB_LOGS_DIR}/hooks.log" 2>/dev/null || true
}