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
from btwb_lib import (  # noqa: E402
    AssistantTurn,
    count_shell_fences,
    last_scorable_context,
    last_scorable_turn,
    strip_code_fences,
)

ENGINE_VERSION = "1.2.0"

# (pattern, points, offender_label) — labels are human-readable for correction hooks
YIELD_PHRASES: List[Tuple[str, int, str]] = [
    (r"\byou can run\b", 25, "phrase:you_can_run"),
    (r"\byou(?:'ll| will) (?:need to |have to )?run\b", 25, "phrase:youll_need_to_run"),
    (r"\brun this command\b", 25, "phrase:run_this_command"),
    (r"\brun the following\b", 20, "phrase:run_the_following"),
    (r"\btry running\b", 20, "phrase:try_running"),
    (r"\bpaste (?:back |me )?(?:the )?(?:output|result|response)\b", 25, "phrase:paste_the_output"),
    (r"\bpaste the output\b", 25, "phrase:paste_the_output"),
    (r"\bhere(?:'s| is) what you need to do\b", 20, "phrase:heres_what_to_do"),
    (r"\bhere are the (?:exact )?commands\b", 25, "phrase:here_are_the_commands"),
    (r"\bI(?:'ll| will) give you the exact\b", 20, "phrase:will_give_exact"),
    (r"\bgive you the exact (?:commands?|sequence|recipe|steps)\b", 20, "phrase:will_give_exact"),
    (r"\bdetails needed\b", 15, "phrase:details_needed"),
    (r"\bneed clarifications\b", 15, "phrase:need_clarifications"),
    (r"\[ASK\]", 20, "marker:ASK"),
    (r"\bGrounding Brief\b", 15, "marker:grounding_brief"),
    (r"\blet me know if\b", 25, "phrase:let_me_know_if"),
    (r"\blet me know\b(?! if\b)", 15, "phrase:let_me_know"),
    (r"\bwould you like me to\b", 25, "phrase:would_you_like_me"),
    (r"\bwould you like\b(?! me\b)", 15, "phrase:would_you_like"),
    (r"\bNeed sudo[^\n]*Run:", 25, "phrase:need_sudo_run"),
    (r"\bStop here\.\b", 15, "phrase:stop_here"),
    (r"\bI (?:did not|cannot|can't) run\b", 15, "phrase:cannot_run"),
    (r"\bI(?:'m| am) not running\b", 15, "phrase:not_running"),
    (r"\bI can(?:'t|not) execute\b", 15, "phrase:cannot_execute"),
    (r"\bwant me to write a (?:small )?script you can run\b", 20, "phrase:script_you_can_run"),
    (r"\bonce you(?:'ve| have) run\b", 20, "phrase:once_you_run"),
    (r"\bafter you run\b", 20, "phrase:after_you_run"),
    (r"\bcopy[- ]paste\b", 15, "phrase:copy_paste"),
    (r"\bexecute this(?: command)?\b", 20, "phrase:execute_this"),
    (r"\bexact (?:commands?|sequence|recipe)\b", 15, "phrase:exact_recipe"),
]

# Keep short aliases so older fixtures/tests still match primary offenders
_LEGACY_ALIAS = {
    "phrase:you_can_run": "you_can_run",
    "phrase:run_this_command": "run_this_command",
    "phrase:paste_the_output": "paste_output",
    "phrase:heres_what_to_do": "heres_what_to_do",
    "phrase:will_give_exact": "will_give_exact",
    "phrase:details_needed": "details_needed",
    "phrase:need_clarifications": "need_clarifications",
    "marker:ASK": "ask_marker",
    "marker:grounding_brief": "grounding_brief",
    "phrase:let_me_know_if": "let_me_know",
    "phrase:would_you_like_me": "would_you_like_me",
    "phrase:would_you_like": "would_you_like",
    "phrase:need_sudo_run": "need_sudo_run",
    "phrase:stop_here": "stop_here",
    "phrase:cannot_run": "cannot_run",
    "phrase:not_running": "not_running",
    "phrase:script_you_can_run": "script_you_can_run",
    "shell_fence_without_tool_use": "shell_fence_no_tool",
}

COMPLETE_PHRASES: List[Tuple[str, int, str]] = [
    (r"\bno findings\b", -30, "complete:no_findings"),
    (r"\breview complete\b", -30, "complete:review_complete"),
    (r"\bcompleted successfully\b", -20, "complete:completed"),
    (r"\ball tests pass\b", -15, "complete:tests_pass"),
]

NUMBERED_LIST_RE = re.compile(r"(?:^|\n)\s*\d+\.\s+", re.MULTILINE)

# User asked for plan/docs only — shell fences and recipes are legitimate handoff
DOCS_ONLY_USER_RE = re.compile(
    r"(?i)"
    r"(?:"
    r"\b(?:just |only )?(?:write|draft|document|produce|give me|provide)\b[^\n.]{0,80}\b"
    r"(?:plan|runbook|readme|write-?up|docs?(?:\s+only)?|documentation|outline|guide)\b"
    r"|"
    r"\b(?:plan|docs?|documentation|runbook|write-?up|outline)\s+only\b"
    r"|"
    r"\bdon'?t\s+(?:run|execute|do anything|touch|change)\b"
    r"|"
    r"\bno\s+(?:execution|running|commands|tool(?:\s+use)?|changes)\b"
    r"|"
    r"\b(?:for|as)\s+documentation\b"
    r"|"
    r"\bwithout\s+(?:running|executing|doing)\s+anything\b"
    r"|"
    r"\bwhat would (?:the|a) plan\b"
    r"|"
    r"\bexplain (?:how|the approach|the plan)\b"
    r"|"
    r"\bdo not (?:run|execute|apply)\b"
    r")"
)

# Action imperatives that override docs dampening (dual-imperative: run wins)
ACTION_IMPERATIVE_RE = re.compile(
    r"(?i)\b(?:"
    r"run the|just run|execute|apply (?:it|this|the)|do it(?: yourself)?|"
    r"ship it|deploy it|go ahead and|probe|fix it|implement"
    r")\b"
)


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
    default = {"threshold": 40, "hard_threshold": 60, "docs_request_skip": True}
    if not path or not path.exists():
        return default
    try:
        data = json.loads(path.read_text())
        for k in ("threshold", "hard_threshold", "docs_request_skip"):
            if k in data:
                default[k] = data[k]
    except Exception:
        pass
    return default


def _emit_offender(offenders: List[str], label: str) -> None:
    """Append clear label plus legacy short alias when present (tests/hooks)."""
    if label not in offenders:
        offenders.append(label)
    legacy = _LEGACY_ALIAS.get(label)
    if legacy and legacy not in offenders:
        offenders.append(legacy)


def is_docs_only_request(prior_user: str) -> bool:
    """True when the operator asked for plan/docs, not live execution."""
    if not prior_user or not prior_user.strip():
        return False
    if not DOCS_ONLY_USER_RE.search(prior_user):
        return False
    # Dual-imperative: "run X" + "give plan" → still action; do not skip
    if ACTION_IMPERATIVE_RE.search(prior_user):
        return False
    return True


def score_turn(
    turn: AssistantTurn,
    profile: Optional[Dict] = None,
    prior_user: str = "",
) -> YieldResult:
    profile = profile or {}
    threshold = int(profile.get("threshold", 40))
    hard_threshold = int(profile.get("hard_threshold", 60))
    docs_skip = bool(profile.get("docs_request_skip", True))

    raw = turn.text
    prose = strip_code_fences(raw)
    score = 0
    offenders: List[str] = []

    # Pure-docs turns: operator wanted a write-up — do not flag yield
    if docs_skip and is_docs_only_request(prior_user):
        excerpt = prose.strip().replace("\n", " ")[:240]
        return YieldResult(
            score=0,
            verdict="ok",
            klass="docs_request",
            structural_yield=False,
            text_only_end_turn=turn.has_text and not turn.has_tool_use and turn.stop_reason == "end_turn",
            offenders=["docs_request_skip"],
            message_id=turn.message_id,
            excerpt=excerpt,
        )

    text_only = turn.has_text and not turn.has_tool_use
    end_turn = turn.stop_reason == "end_turn"
    structural = text_only and end_turn and len(prose.strip()) >= 40

    if structural:
        score += 20
        _emit_offender(offenders, "text_only_end_turn")

    shell_fences = 0 if turn.has_tool_use else count_shell_fences(raw)
    if shell_fences >= 1:
        score += 25
        _emit_offender(offenders, "shell_fence_without_tool_use")

    # Dual-imperative recipe shape: multi-step command dump without tools
    has_numbered = bool(NUMBERED_LIST_RE.search(prose))
    if text_only and shell_fences >= 2:
        score += 20
        _emit_offender(offenders, "dual_imperative_recipe")
    elif text_only and shell_fences >= 1 and has_numbered:
        score += 15
        _emit_offender(offenders, "dual_imperative_recipe")

    if "?" in prose:
        score += 10
        _emit_offender(offenders, "contains_question")

    if has_numbered:
        score += 15
        _emit_offender(offenders, "numbered_list")

    seen_phrase_tags: set = set()
    for pattern, pts, tag in YIELD_PHRASES:
        if tag in seen_phrase_tags:
            continue
        if re.search(pattern, prose, re.IGNORECASE):
            score += pts
            _emit_offender(offenders, tag)
            seen_phrase_tags.add(tag)
            # Also mark canonical short form as seen so alias variants don't double-score
            legacy = _LEGACY_ALIAS.get(tag)
            if legacy:
                seen_phrase_tags.add(legacy)

    for pattern, pts, tag in COMPLETE_PHRASES:
        if re.search(pattern, prose, re.IGNORECASE):
            score += pts
            _emit_offender(offenders, tag)

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
    turn, prior_user = last_scorable_context(path)
    if not turn:
        # Fallback preserves prior behavior if context walk fails
        turn = last_scorable_turn(path)
        prior_user = ""
    if not turn:
        return YieldResult(
            score=0,
            verdict="ok",
            klass="no_turn",
            structural_yield=False,
            text_only_end_turn=False,
            excerpt="",
        )
    return score_turn(turn, profile, prior_user=prior_user)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Score last assistant turn for yield-back")
    ap.add_argument("--transcript", required=True, help="Path to session JSONL")
    ap.add_argument("--profile", help="JSON profile with threshold/hard_threshold")
    ap.add_argument("--emit-detail", action="store_true", help="Print JSON detail on line 2")
    args = ap.parse_args(argv)

    path = Path(args.transcript)
    result = score_transcript(path, Path(args.profile) if args.profile else None)

    badge = f"{result.verdict}|{result.score}"
    print(badge)
    if args.emit_detail:
        print(json.dumps(result.to_dict(), separators=(",", ":")))
    return 0 if result.verdict == "ok" else 0


if __name__ == "__main__":
    sys.exit(main())
