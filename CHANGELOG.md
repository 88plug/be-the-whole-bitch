# Changelog

## 2026.6.1

- Initial release: yield-back enforcement for reversible work
- Hooks: SessionStart (authority contract), Stop (score last turn), UserPromptSubmit (one-shot drive correction)
- Scorer engine: structural + phrase signals, soft/hard thresholds via `profiles/default.json`
- Skill: execute-don't-instruct; dual-imperative resolution; irreversible ops deferred to trigger-my-training
- Commands: `/be-the-whole-bitch:status`, `:audit`, `:eval`
- Eval harness: session-log simulator; primary KPI `eval_trap_failures`
- Tests: unit, golden fixtures, smoke wiring, plugin validate CI
