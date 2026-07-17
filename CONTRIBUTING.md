# Contributing

Short guide for validating local changes. Keep PRs scoped.

## Smoke / validate

Full wiring check (imports, unit tests, plugin validate, golden fixtures, hook syntax):

```bash
bash tests/smoke.sh
```

Plugin structure only (manifest, frontmatter, bash `-n` on hooks/scripts):

```bash
python3 .ci/validate_plugin.py .
```

Unit / fixture tests:

```bash
python3 tests/test_yield_score.py
python3 tests/test_simulator.py
python3 tests/test_golden_fixtures.py
```

Intensive session-log eval (optional, slower):

```bash
bash evals/run_intensive.sh
```

## Command frontmatter

Every file under `commands/*.md` must start with YAML frontmatter that includes `description:` (required by Claude Code discovery and `.ci/validate_plugin.py`).

## Manifest sync

Keep these descriptions aligned when you change product copy:

- `.claude-plugin/plugin.json` → `description`
- `.claude-plugin/marketplace.json` → top-level + `plugins[0].description`
- `marketplace-entry.json` → `description`
