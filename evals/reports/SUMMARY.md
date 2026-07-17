# Intensive eval summary — be-the-whole-bitch

**Date:** 2026-07-17 · **Scorer:** 1.4.0  
**Command:** `python3 evals/simulator.py --root ~/.claude/projects --limit 0 --json`

## Before / after this lap

| Metric | Pre-eval lap (1.3.0) | After 1.4.0 lap | Δ |
|--------|---------------------:|----------------:|---|
| predicted_yields | 207 | **223** | +16 |
| eval_trap_failures | 56 | **64** | +8 |
| dual-trap capture (manual) | 80.2% (69/86) | **98.8% (85/86)** | +18.6pp |
| dual-trap misses | 17 | **1** | **~17× fewer misses** |
| hook_fire_rate | 14.9% | 16.0% | +1.1pp |

## Honest note on the previous lap
The first eval pass mainly **built the harness** and fixed small FPs. Product power was ~flat.
This lap targeted dual-trap **misses** (approval-seeking without recipes) and forced hard yield.

## KPI gates — PASS
assistant_end_turns 1394 ≥500 · predicted_yields 223 ≥100 · eval_trap_failures 64 ≥40
