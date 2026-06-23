#!/usr/bin/env bash
# Intensive eval suite: full corpus replay + fixture extraction + unit tests.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "== unit tests =="
python3 tests/test_yield_score.py
python3 tests/test_simulator.py

echo "== plugin validate =="
python3 .ci/validate_plugin.py .

echo "== full corpus simulator (this may take a few minutes) =="
python3 evals/simulator.py \
  --root "${HOME}/.claude/projects" \
  --limit 0 \
  --fixtures evals/fixtures/golden.jsonl \
  --top 30 \
  --json > evals/reports/latest.json

python3 -c "
import json, sys
from pathlib import Path
r=json.loads(Path('evals/reports/latest.json').read_text())
s=r['summary']
print('INTENSIVE EVAL SUMMARY')
for k,v in s.items():
    print(f'  {k}: {v}')
fixtures = Path('evals/fixtures/golden.jsonl').read_text().strip().split(chr(10))
print(f'fixtures written: {len(fixtures)} lines')
assert s['assistant_end_turns'] >= 500, 'corpus too small'
assert s['eval_trap_failures'] >= 40, f'eval_trap regressed: {s[\"eval_trap_failures\"]}'
assert s['predicted_yields'] >= 100, f'yield detection regressed: {s[\"predicted_yields\"]}'
print('KPI gates: PASS')
"

echo "== golden fixture regression =="
python3 tests/test_golden_fixtures.py