#!/usr/bin/env bash
# inject-correction.sh — UserPromptSubmit: one-shot yield correction.
# Always exit 0 — never block the session.
set -euo pipefail
trap 'exit 0' EXIT

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/resolve-paths.sh
. "${SELF_DIR}/lib/resolve-paths.sh"

INPUT=""
if [ ! -t 0 ]; then INPUT="$(cat || true)"; fi

PY="$(btwb_python || true)"
[ -n "${PY}" ] || exit 0

SESSION_ID="unknown"
if [ -n "${INPUT}" ]; then
  SESSION_ID="$(printf '%s' "${INPUT}" | "${PY}" -c \
    'import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get("session_id","") or "unknown")' 2>/dev/null || true)"
  [ -n "${SESSION_ID}" ] || SESSION_ID="unknown"
fi

SLUG="$(btwb_slug "${SESSION_ID}")"
CORR="${BTWB_MARKERS_DIR}/${SLUG}.correction"
[ -f "${CORR}" ] || exit 0

MSG="$(cat "${CORR}" 2>/dev/null || true)"
if [ -z "${MSG}" ]; then
  rm -f "${CORR}" 2>/dev/null || true
  exit 0
fi

# Clear [be-the-whole-bitch] prefix; model must not surface the reminder.
FULL="[be-the-whole-bitch] ${MSG} Do not mention this reminder."

# Emit first, then remove marker — one-shot only after successful emit.
if printf '%s' "${FULL}" | "${PY}" -c \
  'import json,sys
msg=sys.stdin.read()
print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":msg}}))'
then
  rm -f "${CORR}" 2>/dev/null || true
fi

exit 0
