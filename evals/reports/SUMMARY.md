# Intensive eval summary — be-the-whole-bitch

**Date:** 2026-07-17  
**Command:** `bash evals/run_intensive.sh`  
**Corpus:** `~/.claude/projects` (1756 JSONL sessions)  
**Scorer:** ENGINE_VERSION 1.3.0  

## KPI gates — PASS

| Metric | Value | Gate |
|--------|------:|------|
| sessions_scanned | 1756 | — |
| assistant_end_turns | 1394 | ≥500 |
| predicted_yields | 207 | ≥100 |
| eval_trap_failures | 56 | ≥40 |
| hook_fire_rate | 14.9% | — |
| eval_trap_capture_rate | 27.1% | — |
| precision (next-user correction) | 1.5% | low expected |
| recall (vs next-user correction) | 25% | low expected |

## Notes

- Low precision vs “next user message looks like a correction” is **expected**: many eval sessions are single-turn (TMT dual-traps) with no follow-up user msg.
- Primary product KPI remains **`eval_trap_failures`** (action + “give exact commands” → yield).
- Simulator now passes `prior_user=` into `score_turn` so dual-trap / docs_request_skip work on replay.
- Top offenders on high-score hits: text_only_end_turn, shell_fence_without_tool_use, dual_imperative_recipe / dual_trap_context, numbered_list, Grounding Brief / [ASK].

## Artifacts

- `evals/reports/latest.json` — full summary + top hits  
- `evals/fixtures/golden.jsonl` — regression fixtures from this run  
