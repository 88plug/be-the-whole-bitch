#!/usr/bin/env bash
# tests/smoke.sh — fleet smoke bar + plugin wiring. Zero third-party deps.
# Exit non-zero on first hard failure. Run from anywhere.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Prefer fleet T1 resolver when present (thin Claude PATH / Homebrew-safe)
if [ -f scripts/run-python.sh ]; then
  PY=(bash scripts/run-python.sh)
else
  PY=("${PYTHON:-python3}")
fi

echo "=== smoke: .claude-plugin/plugin.json exists, no root plugin.json ==="
test -f .claude-plugin/plugin.json
if [ -f plugin.json ]; then
  echo "  FAIL: root plugin.json must not exist (single-manifest layout)" >&2
  exit 1
fi
echo "  ok: single manifest at .claude-plugin/plugin.json"

echo "=== smoke: keywords=20, no version ==="
"${PY[@]}" - <<'PY'
import json, sys
from pathlib import Path
m = json.loads(Path(".claude-plugin/plugin.json").read_text())
assert "version" not in m, "version field must be absent (rolling regime)"
kws = m.get("keywords") or []
assert len(kws) == 20, f"expected 20 keywords, got {len(kws)}"
assert m.get("name"), "plugin.json missing name"
print(f"  ok: name={m['name']} keywords={len(kws)}")
PY

echo "=== smoke: no bare command python3/python/uv/uvx/npx in manifests ==="
for f in .claude-plugin/plugin.json hooks/hooks.json .mcp.json; do
  [ -f "$f" ] || continue
  if grep -qE '"command"[[:space:]]*:[[:space:]]*"(python3?|uvx?|npx)"' "$f"; then
    echo "  FAIL: bare interpreter command in $f" >&2
    exit 1
  fi
  echo "  ok: $f"
done

echo "=== smoke: hooks + scripts bash -n ==="
while read -r f; do
  [ -n "$f" ] || continue
  bash -n "$f" && echo "  ok: $f"
done < <(find hooks scripts -name "*.sh" 2>/dev/null | sort)

echo "=== smoke: run-python.sh thin PATH ==="
if [ -f scripts/run-python.sh ]; then
  bash -n scripts/run-python.sh
  bash scripts/run-python.sh -c 'import sys; assert sys.version_info >= (3, 10)'
  # Simulate Claude GUI spawn (minimal PATH)
  out="$(env -i HOME="$HOME" PATH="/usr/bin:/bin" bash scripts/run-python.sh -c 'import sys; print(sys.version_info[0])')"
  echo "$out" | grep -q '^3$'
  echo "  ok: run-python resolves Python 3 on thin PATH"
else
  echo "  FAIL: scripts/run-python.sh missing (T1 required)" >&2
  exit 1
fi

echo "=== smoke: validate_plugin.py (if present) ==="
if [ -f .ci/validate_plugin.py ]; then
  "${PY[@]}" .ci/validate_plugin.py .
  echo "  ok: validate_plugin.py"
else
  echo "  skip: .ci/validate_plugin.py not present"
fi

echo "=== smoke: engine import ==="
"${PY[@]}" -c "
import sys
sys.path.insert(0, 'bin')
import btwb_lib, btwb_score, btwb_timeline, btwb_backtest
print('  ok: all engine modules import')
"

echo "=== smoke: unit tests ==="
"${PY[@]}" tests/test_yield_score.py
"${PY[@]}" tests/test_simulator.py
"${PY[@]}" tests/test_golden_fixtures.py

echo "=== smoke: scorer self-check ==="
"${PY[@]}" -c "
import sys
sys.path.insert(0, 'bin')
from btwb_lib import parse_assistant_turns
from btwb_score import score_turn
from pathlib import Path
import tempfile

transcript = '''{\"type\":\"assistant\",\"message\":{\"id\":\"m1\",\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"Need sudo for that. Run:\\\\n\\\\n\`\`\`bash\\\\nsudo true\\\\n\`\`\`\"}],\"stop_reason\":\"end_turn\"}}'''
with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
    f.write(transcript)
    path = Path(f.name)
try:
    turn = parse_assistant_turns(path)[0]
    r = score_turn(turn)
    assert r.verdict == 'yield', f'expected yield, got {r.verdict} score={r.score}'
finally:
    path.unlink(missing_ok=True)
print('  ok: sudo handoff self-check')
"

echo "=== smoke: all good ==="
