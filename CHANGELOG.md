# Changelog

## 2026.7.19

- Validator accepts auto-loaded `hooks/hooks.json` (omit `hooks` in plugin.json — no double-declare)
- Data root prefers `GROK_PLUGIN_DATA` then `CLAUDE_PLUGIN_DATA` (dual-harness)
- Export path vars for sourced hook consumers; drop unused ruff import

## 2026.7.17

- Scorer **1.3.0** (TR-backed enhancement wave)
- Wider yield phrases: please run / for you to run / say "go" / paste the full URL / please verify / can you check if / prove it / can't sign in for you
- `no_access` without tool use: "I don't have access", kubectl/ssh claims
- AskUserQuestion / ask_user_question treated as hard yield when the turn did not execute
- Dual-imperative: broader action verbs; docs-request + action + text-only shell fence → `dual_trap_context` boost
- Correction inject voice: "you yielded. run the command yourself — no recipes, no paste-back, no let me know. drive."

## 2026.6.1

- Initial release: yield-back enforcement for reversible work
- Hooks: SessionStart (authority contract), Stop (score last turn), UserPromptSubmit (one-shot drive correction)
- Scorer engine: structural + phrase signals, soft/hard thresholds via `profiles/default.json`
- Skill: execute-don't-instruct; dual-imperative resolution; irreversible ops deferred to trigger-my-training
- Commands: `/be-the-whole-bitch:status`, `:audit`, `:eval`
- Eval harness: session-log simulator; primary KPI `eval_trap_failures`
- Tests: unit, golden fixtures, smoke wiring, plugin validate CI
