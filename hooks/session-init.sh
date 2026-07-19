#!/usr/bin/env bash
# session-init.sh — SessionStart: arm a brief authority contract.
# Always exit 0 — never block the session.
set -euo pipefail
trap 'exit 0' EXIT

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/resolve-paths.sh
. "${SELF_DIR}/lib/resolve-paths.sh"

btwb_ensure_dirs
SLUG="$(btwb_slug "${CLAUDE_PROJECT_ID:-default}")"
rm -f "${BTWB_MARKERS_DIR}/${SLUG}.correction" 2>/dev/null || true
btwb_log_debug "session-init armed project=${CLAUDE_PROJECT_ID:-default}"

# Brief directive — short enough not to crowd SessionStart context.
CONTEXT='[be-the-whole-bitch] drive. reversible work: you run it. no recipes. irreversible → confirm only.'

PY="$(btwb_python || true)"
[ -n "${PY}" ] || exit 0

printf '%s' "${CONTEXT}" | "${PY}" -c \
  'import json,sys
msg=sys.stdin.read()
print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":msg}}))' || true

exit 0
