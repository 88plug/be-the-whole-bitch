#!/usr/bin/env bash
# capture-stop.sh — Stop: score yield-back; drop one-shot correction marker.
# Always exit 0 — never block the session. Silent if python is missing.
set -euo pipefail
trap 'exit 0' EXIT

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/resolve-paths.sh
. "${SELF_DIR}/lib/resolve-paths.sh"

btwb_ensure_dirs
INPUT=""
if [ ! -t 0 ]; then INPUT="$(cat || true)"; fi

PY="$(btwb_python || true)"
# No interpreter: silent success (do not log, do not fail the session).
[ -n "${PY}" ] || exit 0

read_field() {
  "${PY}" -c 'import json,sys
try: d=json.loads(sys.argv[1])
except Exception: d={}
print(d.get(sys.argv[2],"") or "")' "${INPUT}" "$1" 2>/dev/null || true
}

SESSION_ID="$(read_field session_id)"
TRANSCRIPT="$(read_field transcript_path)"
[ -n "${SESSION_ID}" ] || SESSION_ID="unknown"

if [ -z "${TRANSCRIPT}" ] || [ ! -f "${TRANSCRIPT}" ]; then
  btwb_log_debug "no transcript; skip session=${SESSION_ID}"
  exit 0
fi

OUT="$("${PY}" "${BTWB_SCORE_PY}" \
  --transcript "${TRANSCRIPT}" \
  --profile "${BTWB_PROFILE}" \
  --emit-detail 2>>"${BTWB_LOGS_DIR}/error.log" || true)"

BADGE="$(printf '%s' "${OUT}" | sed -n '1p')"
DETAIL="$(printf '%s' "${OUT}" | sed -n '2p')"
VERDICT="${BADGE%%|*}"

SLUG="$(btwb_slug "${SESSION_ID}")"
CORR="${BTWB_MARKERS_DIR}/${SLUG}.correction"

if [ "${VERDICT}" = "yield" ] && [ -n "${DETAIL}" ]; then
  SCORE="$(printf '%s' "${DETAIL}" | "${PY}" -c 'import json,sys
try: print(json.load(sys.stdin).get("score",0))
except Exception: print(0)' 2>/dev/null || true)"
  OFFENDERS="$(printf '%s' "${DETAIL}" | "${PY}" -c 'import json,sys
try:
  o=json.load(sys.stdin).get("offenders",[])
  print(", ".join(o[:5]))
except Exception: print("")' 2>/dev/null || true)"
  MSG="Previous turn yielded authority (score ${SCORE}). Run the verifying command yourself — no instructions to the operator."
  [ -n "${OFFENDERS}" ] && MSG="${MSG} Signals: ${OFFENDERS}."
  printf '%s' "${MSG}" | btwb_atomic_write "${CORR}" 0600 || true
  btwb_log_debug "yield session=${SESSION_ID} score=${SCORE}"
else
  rm -f "${CORR}" 2>/dev/null || true
fi

exit 0
