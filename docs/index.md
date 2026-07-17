# Be The Whole Bitch

A Claude Code plugin that stops the model from yielding authority on reversible work. It scores finished turns for handoff language and shell recipes, then injects a one-shot drive correction on the next prompt.

## Install

```text
/plugin marketplace add 88plug/claude-code-plugins
/plugin install be-the-whole-bitch@88plug
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
