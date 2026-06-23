#!/usr/bin/env bash
set -u
BTWB_HOOK_NAME="session-init"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/resolve-paths.sh
. "${SELF_DIR}/lib/resolve-paths.sh"

btwb_ensure_dirs
SLUG="$(btwb_slug "${CLAUDE_PROJECT_ID:-default}")"
rm -f "${BTWB_MARKERS_DIR}/${SLUG}.correction" 2>/dev/null || true

CONTEXT='[be-the-whole-bitch] Authority contract armed. You run commands yourself on this machine. Never end a turn by handing the operator a command to paste, asking numbered questions you could probe first, or saying "let me know" on action tasks. If the prompt says both "run X" and "give commands", run X wins. Defer irreversible ops to trigger-my-training; everything else — drive.'

PY="$(btwb_python || true)"
if [ -n "${PY}" ]; then
  printf '%s' "${CONTEXT}" | "${PY}" -c \
    'import json,sys
msg=sys.stdin.read()
print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":msg}}))'
fi
exit 0