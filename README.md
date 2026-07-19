<div align="center">

# Be The Whole Bitch

Agent authority guardrails for Claude Code and Grok: enforce full drive on reversible work — never yield paste recipes.

[![plugin-validate](https://github.com/88plug/be-the-whole-bitch/actions/workflows/plugin-validate.yml/badge.svg)](https://github.com/88plug/be-the-whole-bitch/actions/workflows/plugin-validate.yml)
[![License: FSL-1.1-ALv2](https://img.shields.io/badge/license-FSL--1.1--ALv2-blue?style=flat)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-online-blue?style=flat)](https://88plug.github.io/be-the-whole-bitch/)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2?style=flat)](https://github.com/88plug/claude-code-plugins)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/88plug/be-the-whole-bitch)

</div>

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


Hub-first install from the [88plug Claude Code plugins](https://github.com/88plug/claude-code-plugins) marketplace. No clone required to use it.

## Quickstart

1. Install the plugin (block above).
2. Start a normal Claude Code session and give an action task: fix a test, run a deploy check, probe a service.
3. If the model yields a paste recipe instead of driving, the Stop hook scores the turn.
4. On your next prompt, a one-shot `[be-the-whole-bitch]` drive correction is injected.
5. Check the last flag anytime:

```text
/be-the-whole-bitch:status
/be-the-whole-bitch:audit
```

## What it does

LLMs and coding agents are trained to be helpful by *explaining*. On Claude Code that often means ending a turn with shell blocks for you to paste, numbered questions the agent could have probed, or "let me know" on reversible work. That is a **yield-back**: the agent hands authority to the operator instead of driving.

This Claude Code plugin scores every finished assistant turn for yield-back. When the score crosses threshold, the next prompt gets a one-shot drive correction. The model is pushed to run the command itself — instruction-following for agent behavior, not more prose. Pure transcript scoring plus context injection. No extra model call.

| Surface | Role |
| --- | --- |
| Skill | Authority contract: execute, don't instruct; probe before "no access"; dual-imperative → run wins |
| SessionStart hook | Arms the contract for the session |
| Stop hook | Scores the last assistant turn; queues a correction on yield |
| UserPromptSubmit hook | Injects a one-shot `[be-the-whole-bitch]` drive reminder, then clears it |
| Commands | Score, status, and session-log eval |

## Why use it

If you run Claude Code as a coding agent for automation and developer tools workflows, yield-back burns your time. You become the shell. This plugin is guardrails for bias-to-action: hooks + a skill that keep the agent driving on reversible work, and only yield when the op is irreversible.

Pairs cleanly with [trigger-my-training](https://github.com/88plug/trigger-my-training) for the irreversible gate. This plugin owns reversible drive; that one owns grounding before destructive steps.

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

## Yield-back enforcement

The scorer (`bin/btwb_score.py`) reads the session transcript on every **Stop**. It weights structural and lexical signals used in prompt-engineering style handoffs.

### What it catches

- **Paste recipes** — shell fences plus "you can run" / "paste the output" / "let me know" without a tool call
- **Dual-imperative** — operator said run *and* asked for steps; model dumped a recipe instead of driving
- **No-access claims** — "I don't have access" / kubectl/ssh without probing first
- **Ask-without-acting** — AskUserQuestion (or text-only end_turn) when the work was reversible
- **Recipe shape** — numbered lists + open questions that hand the turn back

| Signal | Why it matters |
| --- | --- |
| Text-only `end_turn` (no tool use) | Finished without acting |
| Shell fence without a tool call | Handed you a recipe instead of running it |
| Phrases like "you can run", "paste the output", "let me know" | Explicit handoff |
| Numbered lists + open questions | Recipe / clarification dump |

Default profile (`profiles/default.json`): **threshold 40** → `yield` (soft); **hard_threshold 60** → hard yield. Verdict `yield` writes a per-session correction marker. The next **UserPromptSubmit** injects it once and deletes the marker.

> [!NOTE]
> Detection runs on **Stop** after the response is already shown. The correction lands on the **next** turn. Hooks cannot rewrite a streamed reply.

## Hooks

1. **SessionStart** (`hooks/session-init.sh`) — clears stale markers; injects the authority contract.
2. **Stop** (`hooks/capture-stop.sh`) — scores the last turn; on yield, writes a one-shot correction message.
3. **UserPromptSubmit** (`hooks/inject-correction.sh`) — if a correction exists for this session, injects `[be-the-whole-bitch] …` as `additionalContext` and removes the marker.

No model call of its own. Pure transcript scoring + context injection.

## Irreversible exception

Yield is **allowed** for irreversible ops. Force-push, prod schema destroy, payments, and similar must confirm or follow **trigger-my-training** grounding. That is the only intentional yield. Everything reversible: drive.

## Commands

| Command | What it does |
| --- | --- |
| `/be-the-whole-bitch:status` | Report whether the Stop hook flagged a yield on the previous turn |
| `/be-the-whole-bitch:audit` | Score the last assistant turn (`btwb_score.py --emit-detail`) |
| `/be-the-whole-bitch:eval` | Replay real session logs with the simulator; KPI is **eval_trap_failures** |

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

## Development

```bash
python .ci/validate_plugin.py .
bash tests/smoke.sh
```

Smoke covers engine imports, unit tests, plugin validate, golden fixtures, hook `bash -n`, and a scorer self-check (sudo handoff → `yield`). Local clone is for contributors only — operators install from the hub.

## License

[FSL-1.1-ALv2](LICENSE) — Functional Source License, Apache-2.0 future grant.
