# Be The Whole Bitch

[![Docs](https://img.shields.io/badge/docs-online-blue?style=flat)](https://88plug.github.io/be-the-whole-bitch/)

A Claude Code plugin that stops the model from yielding authority on reversible work. It scores finished turns for handoff language and shell recipes, then injects a one-shot drive correction on the next prompt.

## Install

```text
/plugin marketplace add 88plug/claude-code-plugins
/plugin install be-the-whole-bitch@88plug
```

### Grok Build

```text
grok plugin marketplace add 88plug/claude-code-plugins
grok plugin install be-the-whole-bitch@88plug --trust
```


## Yield-back

A **yield-back** is any turn that hands the operator work the agent could have done: bash fences to paste, "you can run this", "paste the output", numbered questions it could probe first, or "let me know" on an action task.

| Signal | Weight idea | Example |
| --- | --- | --- |
| Text-only end_turn | Structural | Finished with prose, no tool call |
| Shell fence, no tool | Structural | A bash code fence handed as a recipe, no tool call |
| Handoff phrases | Lexical | "you can run", "paste the output" |
| Numbered list / open questions | Lexical | Recipe dump instead of execution |

Default thresholds: **40** soft yield, **60** hard yield (`profiles/default.json`).

!!! note
    Detection runs on **Stop** after the response is already shown. The correction lands on the **next** turn. Hooks cannot rewrite a streamed reply.

## Hooks

Three hooks, no extra model call:

- **SessionStart** — arm the authority contract; clear stale correction markers.
- **Stop** — score the last assistant turn; on yield, write a per-session correction marker.
- **UserPromptSubmit** — inject `[be-the-whole-bitch] …` once if a marker exists, then delete it.

## Commands

- `/be-the-whole-bitch:status` — whether the previous turn was flagged as a yield.
- `/be-the-whole-bitch:audit` — score the last turn with full offender detail.
- `/be-the-whole-bitch:eval` — replay session logs; primary KPI is **eval_trap_failures** (dual-imperative traps where the model still yielded a recipe).

## Irreversible exception

Force-push, production schema destruction, payments, and similar ops must confirm or obey **trigger-my-training**. That is the only intentional yield. Everything else: drive.

## Development

```bash
python .ci/validate_plugin.py .
bash tests/smoke.sh
```

## License

[FSL-1.1-ALv2](https://github.com/88plug/be-the-whole-bitch/blob/main/LICENSE) — Functional Source License, Apache-2.0 future grant.

## Features

| Feature | What it does |
| --- | --- |
| Yield-back scoring | Deterministic score on every Stop from structural + lexical signals |
| Soft / hard thresholds | Default soft **40**, hard **60** (`profiles/default.json`) |
| One-shot correction | Next UserPromptSubmit injects once, then deletes the marker |
| Dual-imperative rule | "Run X" + "give commands" → run wins, not a recipe dump |
| No-access probe rule | Claims of missing kubectl/ssh/access need real probes first |
| Docs-request skip | Pure plan / write-up turns are not forced into tool theater |
| Session-log eval | Simulator KPI: **eval_trap_failures** on dual-imperative traps |
| Zero extra LLM cost | Scorer is local Python on the transcript; hooks only inject context |

## Metrics

Eval harness replay of real Claude Code session logs (scorer 1.4.0, 2026-07-17 intensive lap):

| Metric | Value |
| --- | --- |
| Dual-trap capture (manual) | **98.8%** (85/86) |
| Dual-trap misses | **1** (~17× fewer than prior lap) |
| Predicted yields | 223 |
| Eval trap failures | 64 |
| Hook fire rate | 16.0% |

KPI gates passed: assistant end turns ≥500, predicted yields ≥100, eval_trap_failures ≥40. Full write-up in `evals/reports/SUMMARY.md`.
