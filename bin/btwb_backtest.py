#!/usr/bin/env python3
"""Scan ~/.claude/projects JSONL corpus for yield-back turns."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from btwb_lib import parse_assistant_turns  # noqa: E402
from btwb_score import score_turn  # noqa: E402


def iter_sessions(root: Path, limit: int | None) -> list[Path]:
    files = sorted(
        p for p in root.rglob("*.jsonl")
        if "subagents" not in p.parts
    )
    if limit:
        return files[:limit]
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--limit", type=int, default=500, help="Max session files (0 = all)")
    ap.add_argument("--threshold", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    limit = None if args.limit == 0 else args.limit
    profile = {"threshold": args.threshold, "hard_threshold": 60}

    hits = []
    scanned = 0
    for path in iter_sessions(root, limit):
        scanned += 1
        try:
            turns = parse_assistant_turns(path)
        except Exception:
            continue
        for turn in turns:
            if not turn.has_text:
                continue
            r = score_turn(turn, profile)
            if r.verdict == "yield":
                hits.append(
                    {
                        "session": str(path),
                        "message_id": r.message_id,
                        "score": r.score,
                        "klass": r.klass,
                        "offenders": r.offenders[:8],
                        "excerpt": r.excerpt,
                    }
                )

    summary = {
        "scanned_files": scanned,
        "yield_turns": len(hits),
        "hard_yield": sum(1 for h in hits if h["klass"] == "hard_yield_back"),
        "soft_yield": sum(1 for h in hits if h["klass"] == "soft_yield_back"),
    }

    if args.json:
        print(json.dumps({"summary": summary, "hits": hits[:100]}, indent=2))
    else:
        print(f"scanned {summary['scanned_files']} session files")
        print(f"yield turns: {summary['yield_turns']} (hard={summary['hard_yield']} soft={summary['soft_yield']})")
        for h in hits[:15]:
            print(f"\n[{h['score']}] {h['klass']} — {h['session']}")
            print(f"  {h['excerpt'][:120]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())