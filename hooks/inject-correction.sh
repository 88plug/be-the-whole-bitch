#!/usr/bin/env bash
set -u
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/resolve-paths.sh
. "${SELF_DIR}/lib/resolve-paths.sh"

INPUT=""
if [ ! -t 0 ]; then INPUT="$(cat)"; fi

PY="$(btwb_python || true)"
[ -z "${PY}" ] && exit 0

SESSION_ID="unknown"
if [ -n "${INPUT}" ]; then
  SESSION_ID="$(printf '%s' "${INPUT}" | "${PY}" -c \
    'import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get("session_id","") or "unknown")' 2>/dev/null)"
fi

SLUG="$(btwb_slug "${SESSION_ID}")"
CORR="${BTWB_MARKERS_DIR}/${SLUG}.correction"
[ -f "${CORR}" ] || exit 0

MSG="$(cat "${CORR}" 2>/dev/null)"
rm -f "${CORR}" 2>/dev/null || true
[ -n "${MSG}" ] || exit 0

FULL="[be-the-whole-bitch] ${MSG} Do not mention this reminder."

printf '%s' "${FULL}" | "${PY}" -c \
  'import json,sys
msg=sys.stdin.read()
print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":msg}}))'
exit 0