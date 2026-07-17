#!/usr/bin/env bash
# Live hook eval: drive SessionStart → Stop → UserPromptSubmit like Claude Code.
# Uses the INSTALLED plugin root when available, else this checkout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLED="$(ls -d "${HOME}/.claude/plugins/cache/88plug/be-the-whole-bitch"/*/ 2>/dev/null | sort -V | tail -1 || true)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT_OVERRIDE:-${INSTALLED:-$ROOT}}"
PLUGIN_ROOT="${PLUGIN_ROOT%/}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/btwb-live.XXXXXX")"
export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
export CLAUDE_PLUGIN_DATA="${WORKDIR}/plugin-data"
export CLAUDE_CONFIG_DIR="${WORKDIR}/claude-config"
mkdir -p "$CLAUDE_PLUGIN_DATA" "$CLAUDE_CONFIG_DIR" "$WORKDIR/transcripts"

SESSION_ID="live-eval-btwb-$$"
TRANSCRIPT="$WORKDIR/transcripts/${SESSION_ID}.jsonl"
REPORT="$WORKDIR/report.json"
PASS=0
FAIL=0

log() { printf '  %s\n' "$*"; }
ok() { PASS=$((PASS + 1)); log "PASS: $*"; }
bad() { FAIL=$((FAIL + 1)); log "FAIL: $*"; }

write_transcript() {
  local user_text="$1" asst_text="$2"
  python3 - "$TRANSCRIPT" "$user_text" "$asst_text" <<'PY'
import json, sys
path, user, asst = sys.argv[1], sys.argv[2], sys.argv[3]
recs = [
  {"type": "user", "message": {"role": "user", "content": user}},
  {
    "type": "assistant",
    "message": {
      "id": "msg_live1",
      "role": "assistant",
      "content": [{"type": "text", "text": asst}],
      "stop_reason": "end_turn",
    },
  },
]
with open(path, "w", encoding="utf-8") as fh:
  for r in recs:
    fh.write(json.dumps(r) + "\n")
PY
}

hook_payload() {
  python3 -c 'import json,sys; print(json.dumps({"session_id":sys.argv[1],"transcript_path":sys.argv[2]}))' "$SESSION_ID" "$TRANSCRIPT"
}

run_session_init() {
  bash "$PLUGIN_ROOT/hooks/session-init.sh" </dev/null 2>"$WORKDIR/session-init.err" | tee "$WORKDIR/session-init.out" >/dev/null || true
}

run_stop() {
  hook_payload | bash "$PLUGIN_ROOT/hooks/capture-stop.sh" 2>"$WORKDIR/stop.err" | tee "$WORKDIR/stop.out" >/dev/null || true
}

run_inject() {
  hook_payload | bash "$PLUGIN_ROOT/hooks/inject-correction.sh" 2>"$WORKDIR/inject.err" | tee "$WORKDIR/inject.out" || true
}

marker_path() {
  # resolve same as resolve-paths
  bash -c '
    . "'"$PLUGIN_ROOT"'/hooks/lib/resolve-paths.sh"
    echo "${BTWB_MARKERS_DIR}/$(btwb_slug "'"$SESSION_ID"'").correction"
  '
}

echo "=== BTWB live hook eval ==="
echo "plugin_root: $PLUGIN_ROOT"
echo "workdir:     $WORKDIR"
echo "engine:      $(grep -E '^ENGINE_VERSION' "$PLUGIN_ROOT/bin/btwb_score.py" | head -1)"

# --- Case 1: dual-trap yield must fire ---
echo ""
echo "-- case dual_trap_yield --"
USER_DUAL=$'Drain node ip-10-2-3-4. Run the drain.\n\nGive me the exact commands/steps you would run to do this.'
ASST_DUAL='Need your approval to probe the cluster. Once approved I will check kubectl.'
write_transcript "$USER_DUAL" "$ASST_DUAL"
run_session_init
run_stop
MARKER="$(marker_path)"
if [[ -f "$MARKER" ]]; then
  ok "dual_trap wrote correction marker"
  log "marker: $(cat "$MARKER" | head -c 200)"
else
  bad "dual_trap did not write marker at $MARKER"
  log "stop.err: $(cat "$WORKDIR/stop.err" 2>/dev/null | tail -5)"
fi

INJ="$(run_inject)"
if echo "$INJ" | grep -q 'be-the-whole-bitch'; then
  ok "inject contains [be-the-whole-bitch]"
else
  bad "inject missing brand: $INJ"
fi
if echo "$INJ" | grep -qiE 'yield|drive|recipes|run the command yourself'; then
  ok "inject operator-voice content"
else
  bad "inject content weak: $INJ"
fi
# one-shot: second inject empty
INJ2="$(run_inject)"
if [[ -z "$INJ2" ]] || ! echo "$INJ2" | grep -q 'be-the-whole-bitch'; then
  ok "inject is one-shot (second empty)"
else
  bad "inject fired twice: $INJ2"
fi

# --- Case 2: tool-use success should NOT yield ---
echo ""
echo "-- case tool_success_no_yield --"
SESSION_ID="live-eval-btwb-ok-$$"
TRANSCRIPT="$WORKDIR/transcripts/${SESSION_ID}.jsonl"
python3 - "$TRANSCRIPT" <<'PY'
import json,sys
path=sys.argv[1]
recs=[
  {"type":"user","message":{"role":"user","content":"list the files"}},
  {"type":"assistant","message":{"id":"m1","role":"assistant","content":[{"type":"tool_use","name":"Bash","id":"t1","input":{"command":"ls"}}],"stop_reason":"tool_use"}},
  {"type":"assistant","message":{"id":"m2","role":"assistant","content":[{"type":"text","text":"Done. Listed three files. No findings."}],"stop_reason":"end_turn"}},
]
open(path,"w").write("\n".join(json.dumps(r) for r in recs)+"\n")
PY
run_stop
MARKER="$(marker_path)"
if [[ ! -f "$MARKER" ]]; then
  ok "tool success did not leave correction"
else
  bad "false yield marker: $(cat "$MARKER")"
  rm -f "$MARKER"
fi

# --- Case 3: paste recipe yield ---
echo ""
echo "-- case paste_recipe --"
SESSION_ID="live-eval-btwb-paste-$$"
TRANSCRIPT="$WORKDIR/transcripts/${SESSION_ID}.jsonl"
write_transcript "fix the deploy now" \
  $'Run this command:\n\n```bash\nkubectl apply -f deploy.yaml\n```\n\nPaste the output when done.'
run_stop
MARKER="$(marker_path)"
if [[ -f "$MARKER" ]]; then
  ok "paste recipe wrote correction"
else
  bad "paste recipe missed"
fi
run_inject >/dev/null

# --- Case 4: scorer CLI live on dual transcript ---
echo ""
echo "-- case scorer_cli --"
python3 - "$WORKDIR/score-dual.jsonl" <<'PY'
import json,sys
path=sys.argv[1]
user="Run the drain.\n\nGive me the exact commands"
asst="Need approval. Once approved I'll check."
open(path,"w").write(json.dumps({"type":"user","message":{"role":"user","content":user}})+"\n")
open(path,"a").write(json.dumps({"type":"assistant","message":{"id":"x","role":"assistant","content":[{"type":"text","text":asst}],"stop_reason":"end_turn"}})+"\n")
PY
# score with prior via score_turn unit path
SCORE_OUT="$(cd "$PLUGIN_ROOT" && python3 - <<PY
import sys
sys.path.insert(0, "bin")
from btwb_lib import parse_assistant_turns
from btwb_score import score_turn
turns = parse_assistant_turns(__import__("pathlib").Path("$WORKDIR/score-dual.jsonl"))
r = score_turn(turns[-1], prior_user="Run the drain.\\n\\nGive me the exact commands")
print(f"{r.verdict}|{r.score}")
print(",".join(r.offenders[:6]))
PY
)"
if echo "$SCORE_OUT" | head -1 | grep -q '^yield|'; then
  ok "scorer CLI yield: $(echo "$SCORE_OUT" | head -1)"
else
  bad "scorer CLI: $SCORE_OUT"
fi

echo ""
echo "=== RESULT: $PASS passed, $FAIL failed ==="
python3 -c "import json; print(json.dumps({'pass':$PASS,'fail':$FAIL,'plugin_root':'$PLUGIN_ROOT','workdir':'$WORKDIR'}, indent=2))" | tee "$REPORT"
[[ "$FAIL" -eq 0 ]]
