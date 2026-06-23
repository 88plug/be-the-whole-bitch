---
description: Run session-log replay simulator on past Claude Code transcripts
---

Run the intensive eval harness against real session logs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/evals/simulator.py" \
  --root "${HOME}/.claude/projects" \
  --limit 0 \
  --fixtures "${CLAUDE_PLUGIN_ROOT}/evals/fixtures/golden.jsonl" \
  --top 25
```

Or the full suite:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/evals/run_intensive.sh"
```

Primary KPI: **eval_trap_failures** — sessions where the prompt said both "run X" and "give commands" but the model yielded a recipe.