#!/usr/bin/env python3
"""Score the last assistant turn for yield-back (authority handoff to operator)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from btwb_lib import AssistantTurn, last_scorable_turn, strip_code_fences  # noqa: E402

ENGINE_VERSION = "1.1.0"

SHELL_FENCE_RE = re.compile(r"```(?:bash|sh|shell|zsh)\b", re.IGNORECASE)

YIELD_PHRASES: List[Tuple[str, int, str]] = [
    (r"\byou can run\b", 25, "you_can_run"),
    (r"\brun this command\b", 25, "run_this_command"),
    (r"\bpaste the output\b", 25, "paste_output"),
    (r"\bhere(?:'s| is) what you need to do\b", 20, "heres_what_to_do"),
    (r"\bI(?:'ll| will) give you the exact\b", 20, "will_give_exact"),
    (r"\bdetails needed\b", 15, "details_needed"),
    (r"\bneed clarifications\b", 15, "need_clarifications"),
    (r"\[ASK\]", 20, "ask_marker"),
    (r"\bGrounding Brief\b", 15, "grounding_brief"),
    (r"\blet me know if\b", 15, "let_me_know"),
    (r"\bwould you like me to\b", 15, "would_you_like_me"),
    (r"\bwould you like\b", 10, "would_you_like"),
    (r"\bNeed sudo[^\n]*Run:", 25, "need_sudo_run"),
    (r"\bStop here\.\b", 15, "stop_here"),
    (r"\bI (?:did not|cannot|can't) run\b", 15, "cannot_run"),
    (r"\bI(?:'m| am) not running\b", 15, "not_running"),
    (r"\bwant me to write a (?:small )?script you can run\b", 20, "script_you_can_run"),
]

COMPLETE_PHRASES: List[Tuple[str, int, str]] = [
    (r"\bno findings\b", -30, "no_findings"),
    (r"\breview complete\b", -30, "review_complete"),
    (r"\bcompleted successfully\b", -20, "completed"),
    (r"\ball tests pass\b", -15, "tests_pass"),
]

NUMBERED_LIST_RE = re.compile(r"(?:^|\n)\s*\d+\.\s+", re.MULTILINE)


@dataclass
class YieldResult:
    score: int
    verdict: str
    klass: str
    structural_yield: bool
    text_only_end_turn: bool
    offenders: List[str] = field(default_factory=list)
    message_id: str = ""
    excerpt: str = ""
    engine_version: str = ENGINE_VERSION

    def to_dict(self) -> Dict:
        return asdict(self)


def _load_profile(path: Optional[Path]) -> Dict:
    default = {"threshold": 40, "hard_threshold": 60}
    if not path or not path.exists():
        return default
    try:
        data = json.loads(path.read_text())
        default.update({k: data[k] for k in ("threshold", "hard_threshold") if k in data})
    except Exception:
        pass
    return default


def score_turn(turn: AssistantTurn, profile: Optional[Dict] = None) -> YieldResult:
    profile = profile or {}
    threshold = int(profile.get("threshold", 40))
    hard_threshold = int(profile.get("hard_threshold", 60))

    raw = turn.text
    prose = strip_code_fences(raw)
    score = 0
    offenders: List[str] = []

    text_only = turn.has_text and not turn.has_tool_use
    end_turn = turn.stop_reason == "end_turn"
    structural = text_only and end_turn and len(prose.strip()) >= 40

    if structural:
        score += 20
        offenders.append("text_only_end_turn")

    if not turn.has_tool_use and SHELL_FENCE_RE.search(raw):
        score += 25
        offenders.append("shell_fence_no_tool")

    if "?" in prose:
        score += 10
        offenders.append("contains_question")

    if NUMBERED_LIST_RE.search(prose):
        score += 15
        offenders.append("numbered_list")

    lower = prose.lower()
    for pattern, pts, tag in YIELD_PHRASES:
        if re.search(pattern, prose, re.IGNORECASE):
            score += pts
            offenders.append(tag)

    for pattern, pts, tag in COMPLETE_PHRASES:
        if re.search(pattern, lower):
            score += pts
            offenders.append(tag)

    score = max(0, min(100, score))

    if score >= hard_threshold:
        klass = "hard_yield_back"
    elif score >= threshold:
        klass = "soft_yield_back"
    elif score >= 20:
        klass = "complete_and_stop"
    else:
        klass = "incidental_stop"

    verdict = "yield" if score >= threshold else "ok"
    excerpt = prose.strip().replace("\n", " ")[:240]

    return YieldResult(
        score=score,
        verdict=verdict,
        klass=klass,
        structural_yield=structural and score >= threshold,
        text_only_end_turn=text_only and end_turn,
        offenders=offenders,
        message_id=turn.message_id,
        excerpt=excerpt,
    )


def score_transcript(path: Path, profile_path: Optional[Path] = None) -> YieldResult:
    profile = _load_profile(profile_path)
    turn = last_scorable_turn(path)
    if not turn:
        return YieldResult(
            score=0,
            verdict="ok",
            klass="no_turn",
            structural_yield=False,
            text_only_end_turn=False,
            excerpt="",
        )
    return score_turn(turn, profile)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Score last assistant turn for yield-back")
    ap.add_argument("--transcript", required=True, help="Path to session JSONL")
    ap.add_argument("--profile", help="JSON profile with threshold/hard_threshold")
    ap.add_argument("--emit-detail", action="store_true", help="Print JSON detail on line 2")
    args = ap.parse_args(argv)

    path = Path(args.transcript)
    profile = _load_profile(Path(args.profile) if args.profile else None)
    result = score_transcript(path, Path(args.profile) if args.profile else None)

    badge = f"{result.verdict}|{result.score}"
    print(badge)
    if args.emit_detail:
        print(json.dumps(result.to_dict(), separators=(",", ":")))
    return 0 if result.verdict == "ok" else 0


if __name__ == "__main__":
    sys.exit(main())