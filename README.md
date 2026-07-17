<div align="center">

# Be The Whole Bitch

Enforce full agent authority on reversible work — run commands yourself, never hand the operator a paste recipe.

[![plugin-validate](https://github.com/88plug/be-the-whole-bitch/actions/workflows/plugin-validate.yml/badge.svg)](https://github.com/88plug/be-the-whole-bitch/actions/workflows/plugin-validate.yml)
[![License: FSL-1.1-ALv2](https://img.shields.io/badge/license-FSL--1.1--ALv2-blue?style=flat)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-online-blue?style=flat)](https://88plug.github.io/be-the-whole-bitch)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2?style=flat)](https://github.com/88plug/claude-code-plugins)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/88plug/be-the-whole-bitch)

</div>

## Install

```text
/plugin marketplace add 88plug/claude-code-plugins
/plugin install be-the-whole-bitch@88plug
```

## What it does

Claude is trained to be helpful by *explaining* — which often means ending a turn with shell blocks for you to paste, numbered questions it could have probed, or "let me know" on action tasks. That is a **yield-back**: the agent hands authority to the operator instead of driving.

This plugin scores every finished turn for yield-back. When the score crosses threshold, the next prompt gets a one-shot drive correction. The model is pushed to run the command itself.

| Surface | Role |
| --- | --- |
| Skill | Authority contract: execute, don't instruct; probe before "no access"; dual-imperative → run wins |
| SessionStart hook | Arms the contract for the session |
| Stop hook | Scores the last assistant turn; queues a correction on yield |
| UserPromptSubmit hook | Injects a one-shot `[be-the-whole-bitch]` drive reminder, then clears it |
| Commands | Score, status, and session-log eval |

## Yield-back enforcement

The scorer (`bin/btwb_score.py`) reads the session transcript on every **Stop**. It weights structural and lexical signals:

| Signal | Why it matters |
| --- | --- |
| Text-only `end_turn` (no tool use) | Finished without acting |
| Shell fence without a tool call | Handed you a recipe instead of running it |
| Phrases like "you can run", "paste the output", "let me know" | Explicit handoff |
| Numbered lists + open questions | Recipe / clarification dump |

Default profile (`profiles/default.json`): **threshold 40** → `yield` (soft); **hard_threshold 60** → hard yield. Verdict `yield` writes a per-session correction marker. The next **UserPromptSubmit** injects it once and deletes the marker.

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

## Development

```bash
python .ci/validate_plugin.py .
bash tests/smoke.sh
```

Smoke covers engine imports, unit tests, plugin validate, golden fixtures, hook `bash -n`, and a scorer self-check (sudo handoff → `yield`).

## License

[FSL-1.1-ALv2](LICENSE) — Functional Source License, Apache-2.0 future grant.
