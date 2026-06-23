#!/usr/bin/env bash
# tests/smoke.sh — lightweight wiring check run in CI.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="${PYTHON:-python3}"

echo "=== smoke: engine import ==="
"$PY" -c "
import sys
sys.path.insert(0, 'bin')
import btwb_lib, btwb_score, btwb_timeline, btwb_backtest
print('all engine modules import ok')
"

echo "=== smoke: unit tests ==="
"$PY" tests/test_yield_score.py
"$PY" tests/test_simulator.py

echo "=== smoke: plugin validate ==="
"$PY" .ci/validate_plugin.py .

echo "=== smoke: golden fixtures (if present) ==="
if [ -f evals/fixtures/golden.jsonl ]; then
  "$PY" tests/test_golden_fixtures.py
else
  echo "  skip: no golden.jsonl yet"
fi

echo "=== smoke: hook bash syntax ==="
find hooks/ -name "*.sh" | while read -r f; do
  bash -n "$f" && echo "  ok: $f"
done

echo "=== smoke: scorer self-check ==="
"$PY" -c "
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
turn = parse_assistant_turns(path)[0]
r = score_turn(turn)
assert r.verdict == 'yield', f'expected yield, got {r.verdict} score={r.score}'
path.unlink()
print('sudo handoff self-check ok')
"

echo "=== smoke: all good ==="