#!/usr/bin/env python3
"""validate_plugin.py — CI gate for the be-the-whole-bitch plugin.

Checks, with pyyaml optional for frontmatter:
  * every JSON file parses;
  * single-manifest layout (.claude-plugin/plugin.json only; no root plugin.json);
  * manifest has required fields, 20 keywords, and well-formed hooks;
  * marketplace.json is well-formed;
  * every command/skill markdown has valid frontmatter;
  * every referenced hook script exists;
  * no ${CLAUDE_PLUGIN_*:-default} in manifests (Claude Code leaves :- literal);
  * bash -n passes on every shell script;
  * py_compile passes on every Python file.

usage: validate_plugin.py [PLUGIN_ROOT]   (default ".")
Exit 0 == all good; non-zero == CI fail, with a summary of problems.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
PLUGIN_NAME = "be-the-whole-bitch"
errors: list[str] = []
checks = 0


def ok(msg: str) -> None:
    global checks
    checks += 1
    print(f"  ok: {msg}")


def fail(msg: str) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}")


def rel(p: Path | str) -> str:
    try:
        return str(Path(p).relative_to(ROOT))
    except Exception:
        return str(p)


def load_json(relpath: str):
    path = ROOT / relpath
    if not path.is_file():
        fail(f"missing file: {relpath}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {relpath}: {exc}")
        return None


def all_json_parse() -> None:
    skip_parts = {".git", "__pycache__", "site", ".venv", "venv", "node_modules"}
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_parts]
        if any(p in Path(dirpath).parts for p in skip_parts):
            continue
        for fn in files:
            if fn.endswith(".json"):
                r = rel(Path(dirpath) / fn)
                if load_json(r) is not None:
                    ok(f"json parses: {r}")


def check_no_root_manifest() -> None:
    """Spec defines no root-level plugin.json; single manifest under .claude-plugin/."""
    if (ROOT / "plugin.json").is_file():
        fail(
            "root plugin.json must not exist "
            "(spec defines none; use .claude-plugin/plugin.json)"
        )
    else:
        ok("no root plugin.json (single-manifest layout)")


def check_hooks_obj(obj, src: str) -> None:
    if not isinstance(obj, dict):
        fail(f"{src}: hooks object not a dict")
        return
    hooks = obj.get("hooks", obj)
    for event in ("SessionStart", "Stop", "UserPromptSubmit"):
        if event not in hooks:
            fail(f"{src}: hooks missing event {event}")
            continue
        for group in hooks[event]:
            for h in group.get("hooks", []):
                cmd = h.get("command", "")
                if "${CLAUDE_PLUGIN_ROOT}" not in cmd:
                    fail(f"{src}: hook command missing ${{CLAUDE_PLUGIN_ROOT}}: {cmd!r}")
                for tok in cmd.replace('"', " ").split():
                    if tok.endswith(".sh") and "CLAUDE_PLUGIN_ROOT" in cmd:
                        script_rel = tok.split("CLAUDE_PLUGIN_ROOT}/", 1)[-1]
                        p = ROOT / script_rel
                        if not p.is_file():
                            fail(f"{src}: hook script missing: {script_rel}")
    ok(f"hooks reference real scripts: {src}")


def check_manifest(relpath: str) -> None:
    data = load_json(relpath)
    if data is None:
        return
    for field in ("name", "description", "keywords"):
        if not data.get(field):
            fail(f"{relpath}: missing required field '{field}'")
    if data.get("name") and data["name"] != PLUGIN_NAME:
        fail(f"{relpath}: name must be '{PLUGIN_NAME}'")
    if "version" in data:
        fail(f"{relpath}: must not have version field (rolling plugin)")
    nkw = len(data.get("keywords", []))
    if nkw != 20:
        fail(f"{relpath}: keywords must be exactly 20 (found {nkw})")
    lic = data.get("license")
    if lic != "FSL-1.1-ALv2":
        fail(f"{relpath}: license must be FSL-1.1-ALv2 (found {lic!r})")
    # Hooks: omit field when hooks/hooks.json exists (Claude auto-loads it;
    # declaring the same file in plugin.json double-declares and blocks updates).
    hooks = data.get("hooks")
    auto_hj = ROOT / "hooks" / "hooks.json"
    if isinstance(hooks, str):
        hp = ROOT / hooks.lstrip("./")
        if not hp.is_file():
            fail(f"{relpath}: hooks path not found: {hooks}")
        elif auto_hj.is_file() and hp.resolve() == auto_hj.resolve():
            fail(
                f"{relpath}: hooks must not point at hooks/hooks.json "
                "(Claude auto-loads it; omit the field instead)"
            )
        else:
            check_hooks_obj(load_json(rel(hp)), relpath)
    elif isinstance(hooks, dict):
        if auto_hj.is_file():
            fail(
                f"{relpath}: omit inline hooks when hooks/hooks.json exists "
                "(duplicate hooks block marketplace updates)"
            )
        else:
            check_hooks_obj({"hooks": hooks}, relpath)
    elif auto_hj.is_file():
        check_hooks_obj(load_json("hooks/hooks.json"), "hooks/hooks.json")
    else:
        fail(f"{relpath}: missing or malformed hooks (no hooks/hooks.json either)")
    ok(f"manifest ok: {relpath}")


def check_marketplace() -> None:
    data = load_json(".claude-plugin/marketplace.json")
    if data is None:
        return
    plugins = data.get("plugins")
    if not plugins:
        fail("marketplace.json: no plugins array")
    else:
        names = [p.get("name") for p in plugins]
        if PLUGIN_NAME not in names:
            fail(f"marketplace.json: {PLUGIN_NAME} not listed")
    ok("marketplace.json ok")


def check_bad_default_form() -> None:
    """Claude Code does not expand ${CLAUDE_PLUGIN_ROOT:-default} in manifests."""
    bad = re.compile(r"\$\{CLAUDE_PLUGIN_(?:ROOT|DATA):-")
    candidates = [
        ROOT / ".claude-plugin" / "plugin.json",
        ROOT / ".mcp.json",
        ROOT / "hooks" / "hooks.json",
    ]
    for p in candidates:
        if p.is_file() and bad.search(p.read_text(encoding="utf-8")):
            fail(
                f"{rel(p)}: uses ${{CLAUDE_PLUGIN_*:-default}} — Claude Code substitutes "
                f"only the plain ${{CLAUDE_PLUGIN_ROOT}} form; the :- default is left literal"
            )
    ok("no :-default CLAUDE_PLUGIN_* forms in manifests")


def parse_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("---"):
        return None, "no YAML frontmatter"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "unterminated frontmatter"
    if yaml is None:
        # Without pyyaml, still require a description-ish line.
        block = parts[1]
        fm = {}
        for line in block.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
        return fm, None
    try:
        d = yaml.safe_load(parts[1])
    except Exception as exc:
        return None, (
            f"frontmatter YAML parse error ({exc.__class__.__name__}) — "
            "often an unquoted description containing ': '"
        )
    if not isinstance(d, dict):
        return None, "frontmatter is not a mapping"
    return d, None


def check_commands() -> None:
    cdir = ROOT / "commands"
    if not cdir.is_dir():
        fail("commands/ dir missing")
        return
    found = False
    for fn in sorted(cdir.iterdir()):
        if not fn.name.endswith(".md"):
            continue
        found = True
        fm, err = parse_frontmatter(fn)
        if err:
            fail(f"commands/{fn.name}: {err}")
        elif not fm or not fm.get("description"):
            fail(f"commands/{fn.name}: frontmatter missing 'description'")
        else:
            ok(f"command frontmatter ok: {fn.name}")
    if not found:
        fail("commands/: no .md files")


def check_skill() -> None:
    sp = ROOT / "skills" / PLUGIN_NAME / "SKILL.md"
    if not sp.is_file():
        fail(f"SKILL.md missing at skills/{PLUGIN_NAME}/SKILL.md")
        return
    fm, err = parse_frontmatter(sp)
    if err:
        fail(f"SKILL.md: {err}")
    elif not fm or not fm.get("name") or not fm.get("description"):
        fail("SKILL.md: frontmatter needs name + description")
    else:
        ok("SKILL.md frontmatter ok")


def check_bash_syntax() -> None:
    for dirpath, _dirs, files in os.walk(ROOT):
        if "/.git" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".sh"):
                continue
            p = Path(dirpath) / fn
            r = subprocess.run(
                ["bash", "-n", str(p)], capture_output=True, text=True
            )
            if r.returncode != 0:
                fail(f"bash -n {rel(p)}: {r.stderr.strip()}")
            else:
                ok(f"bash -n ok: {rel(p)}")


def check_python_syntax() -> None:
    import py_compile

    for dirpath, _dirs, files in os.walk(ROOT):
        if "/.git" in dirpath or "__pycache__" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = Path(dirpath) / fn
            try:
                py_compile.compile(str(p), doraise=True)
                ok(f"py_compile ok: {rel(p)}")
            except py_compile.PyCompileError as exc:
                fail(f"py_compile {rel(p)}: {exc}")


def main() -> int:
    print(f"== {PLUGIN_NAME} plugin validation ==")
    all_json_parse()
    check_no_root_manifest()
    check_manifest(".claude-plugin/plugin.json")
    check_marketplace()
    check_bad_default_form()
    check_commands()
    check_skill()
    check_bash_syntax()
    check_python_syntax()
    print(f"\n{checks} checks run, {len(errors)} failures")
    if errors:
        print("\n".join(f"  - {e}" for e in errors))
        return 1
    print("ALL GOOD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
