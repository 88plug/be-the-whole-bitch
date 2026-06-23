#!/usr/bin/env python3
"""
Replay simulator: process real past session JSONL as if be-the-whole-bitch hooks ran.

For each assistant end_turn, scores yield-back (Stop hook). Looks at the next real
user message for operator correction signals (ground truth). Reports precision/recall
and per-category breakdown.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from btwb_score import score_turn  # noqa: E402
from btwb_timeline import TimelineEvent, parse_timeline, session_tags  # noqa: E402

# Operator pushed back — mined from corpus (see backtest report)
USER_CORRECTION_RE = re.compile(
    r"(?i)"
    r"(?:"
    r"do it for me|just run it|just do it|stop asking|why didn't you|"
    r"run it yourself|execute it|you didn't run|ffs|wtf|"
    r"don't ask|don't tell me to run|you tell me to run|"
    r"paste the output.*you|"
    r"^run\.?$|^go\.?$|^continue\.?$"
    r")"
)

USER_DRIVE_RE = re.compile(
    r"(?i)(?:^|\n)\s*(?:run|go|continue|do it|ship)\.?\s*$"
)

TASK_NOTIFICATION_RE = re.compile(r"^\s*<task-notification>", re.I)
MILESTONE_CONTINUATION_RE = re.compile(
    r"(?i)^\s*drive the .+ (?:milestone|ladder|phase)\b"
)
SYSTEM_REMINDER_ONLY_RE = re.compile(r"^\s*<system-reminder>", re.I)


def is_user_correction(text: str) -> bool:
    """True when the next user message is an operator pushback, not a system ping."""
    if not text or not text.strip():
        return False
    stripped = text.strip()
    if TASK_NOTIFICATION_RE.search(stripped):
        return False
    if MILESTONE_CONTINUATION_RE.search(stripped):
        return False
    if SYSTEM_REMINDER_ONLY_RE.search(stripped) and not USER_CORRECTION_RE.search(stripped):
        return False
    if USER_CORRECTION_RE.search(stripped):
        return True
    if len(stripped) <= 40 and USER_DRIVE_RE.search(stripped):
        return True
    return False

EVAL_TRAP_CMD_ONLY_RE = re.compile(r"give me the exact commands", re.I)
EVAL_TRAP_RUN_RE = re.compile(r"\brun the (?:drain|migration|apply)\b", re.I)


@dataclass
class SimulatedTurn:
    session: str
    turn_index: int
    message_id: str
    score: int
    verdict: str
    klass: str
    offenders: List[str]
    excerpt: str
    predicted_yield: bool
    hook_would_fire: bool
    next_user_correction: bool
    next_user_text: str
    eval_trap: bool
    eval_trap_failure: bool  # had "run" imperative but model yielded recipe
    tags: Dict[str, bool] = field(default_factory=dict)


@dataclass
class SimReport:
    sessions_scanned: int = 0
    sessions_with_timeline: int = 0
    assistant_end_turns: int = 0
    predicted_yields: int = 0
    hook_would_fire: int = 0
    ground_truth_corrections: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    eval_trap_failures: int = 0
    turns: List[SimulatedTurn] = field(default_factory=list)

    def metrics(self) -> Dict[str, Any]:
        prec = self.true_positives / self.predicted_yields if self.predicted_yields else 0.0
        rec = self.true_positives / self.ground_truth_corrections if self.ground_truth_corrections else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        # Eval-trap is the primary KPI: single-turn evals rarely get a follow-up user msg,
        # so correction-based precision/recall understates detector value.
        trap_recall = (
            self.eval_trap_failures / self.predicted_yields if self.predicted_yields else 0.0
        )
        hook_coverage = (
            self.hook_would_fire / self.assistant_end_turns if self.assistant_end_turns else 0.0
        )
        return {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "predicted_yields": self.predicted_yields,
            "ground_truth_corrections": self.ground_truth_corrections,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "eval_trap_failures": self.eval_trap_failures,
            "eval_trap_capture_rate": round(trap_recall, 4),
            "hook_fire_rate": round(hook_coverage, 4),
        }


def _next_user_text(events: List[TimelineEvent], start: int) -> Tuple[str, bool]:
    for ev in events[start + 1 :]:
        if ev.kind == "user" and ev.user:
            text = ev.user.text
            corrected = is_user_correction(text)
            return text[:300], corrected
    return "", False


def _eval_trap_failure(user_before: str, result_verdict: str) -> bool:
    if result_verdict != "yield":
        return False
    if not EVAL_TRAP_CMD_ONLY_RE.search(user_before):
        return False
    return bool(EVAL_TRAP_RUN_RE.search(user_before))


def simulate_session(path: Path, profile: Dict) -> Tuple[List[SimulatedTurn], Dict[str, bool]]:
    events = parse_timeline(path)
    if not events:
        return [], {}
    tags = session_tags(path, events)
    turns: List[SimulatedTurn] = []

    last_user = ""
    for i, ev in enumerate(events):
        if ev.kind == "user" and ev.user:
            last_user = ev.user.text
            continue
        if ev.kind != "assistant" or not ev.assistant:
            continue
        if ev.assistant.stop_reason != "end_turn":
            continue
        if not ev.assistant.has_text:
            continue

        r = score_turn(ev.assistant, profile)
        next_text, user_corr = _next_user_text(events, i)
        trap_fail = _eval_trap_failure(last_user, r.verdict)

        turns.append(
            SimulatedTurn(
                session=str(path),
                turn_index=ev.index,
                message_id=ev.assistant.message_id,
                score=r.score,
                verdict=r.verdict,
                klass=r.klass,
                offenders=r.offenders[:8],
                excerpt=r.excerpt,
                predicted_yield=r.verdict == "yield",
                hook_would_fire=r.verdict == "yield",
                next_user_correction=user_corr,
                next_user_text=next_text,
                eval_trap=tags.get("eval_trap", False),
                eval_trap_failure=trap_fail,
                tags=tags,
            )
        )

    return turns, tags


def run_simulation(
    root: Path,
    limit: Optional[int],
    profile: Dict,
    min_score_report: int = 40,
) -> SimReport:
    files = sorted(p for p in root.rglob("*.jsonl") if "subagents" not in p.parts)
    if limit:
        files = files[:limit]

    report = SimReport(sessions_scanned=len(files))

    for path in files:
        turns, tags = simulate_session(path, profile)
        if not turns and not tags:
            continue
        report.sessions_with_timeline += 1

        for t in turns:
            report.assistant_end_turns += 1
            if t.predicted_yield:
                report.predicted_yields += 1
            if t.hook_would_fire:
                report.hook_would_fire += 1
            if t.next_user_correction:
                report.ground_truth_corrections += 1
            if t.predicted_yield and t.next_user_correction:
                report.true_positives += 1
            elif t.predicted_yield and not t.next_user_correction:
                report.false_positives += 1
            elif not t.predicted_yield and t.next_user_correction:
                report.false_negatives += 1
            if t.eval_trap_failure:
                report.eval_trap_failures += 1
            if t.score >= min_score_report:
                report.turns.append(t)

    report.turns.sort(key=lambda t: (-t.score, t.session))
    return report


def _redact_for_export(obj: Any) -> Any:
    """Strip local paths and user text before any artifact leaves the machine."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if k in ("session", "next_user_text"):
                continue
            if k == "excerpt" and isinstance(v, str):
                out[k] = v[:120]
            else:
                out[k] = _redact_for_export(v)
        return out
    if isinstance(obj, list):
        return [_redact_for_export(x) for x in obj]
    return obj


def write_fixtures(report: SimReport, out: Path, top_n: int = 50) -> None:
    """Local-only regression index — gitignored; never commit."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for t in report.turns[:top_n]:
            fh.write(
                json.dumps(
                    _redact_for_export(
                        {
                            "session_hash": str(hash(t.session)),
                            "turn_index": t.turn_index,
                            "message_id": t.message_id,
                            "score": t.score,
                            "klass": t.klass,
                            "offenders": t.offenders,
                            "excerpt": t.excerpt,
                            "next_user_correction": t.next_user_correction,
                            "eval_trap_failure": t.eval_trap_failure,
                            "expect_verdict": "yield"
                            if t.eval_trap_failure or t.next_user_correction
                            else t.verdict,
                        }
                    )
                )
                + "\n"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay be-the-whole-bitch on real session logs")
    ap.add_argument("--root", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--limit", type=int, default=0, help="Max sessions (0=all)")
    ap.add_argument("--threshold", type=int, default=40)
    ap.add_argument("--fixtures", type=Path, help="Write top regression fixtures JSONL")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=20, help="Top hits to print")
    args = ap.parse_args()

    profile = {"threshold": args.threshold, "hard_threshold": 60}
    limit = None if args.limit == 0 else args.limit
    report = run_simulation(Path(args.root), limit, profile)

    if args.fixtures:
        write_fixtures(report, args.fixtures)

    payload = {
        "summary": {
            "sessions_scanned": report.sessions_scanned,
            "sessions_with_timeline": report.sessions_with_timeline,
            "assistant_end_turns": report.assistant_end_turns,
            **report.metrics(),
        },
        "top_hits": [_redact_for_export(asdict(t)) for t in report.turns[: args.top]],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        m = payload["summary"]
        print("=== be-the-whole-bitch session replay simulator ===")
        print(f"sessions scanned:     {m['sessions_scanned']}")
        print(f"sessions w/ timeline: {m['sessions_with_timeline']}")
        print(f"assistant end_turns:  {m['assistant_end_turns']}")
        print(f"predicted yields:     {m['predicted_yields']}")
        print(f"ground-truth corrections (next user msg): {m['ground_truth_corrections']}")
        print(f"TP / FP / FN:         {m['true_positives']} / {m['false_positives']} / {m['false_negatives']}")
        print(f"precision / recall:   {m['precision']} / {m['recall']}  (f1={m['f1']})")
        print(f"eval-trap failures:   {m['eval_trap_failures']}  (run+give-commands → yield)")
        print(f"hook fire rate:       {m.get('hook_fire_rate', 0)}  (yields / end_turns)")
        print(f"eval-trap capture:    {m.get('eval_trap_capture_rate', 0)}  (trap fails / yields)")
        print("NOTE: low precision vs user-correction is expected — eval sessions are single-turn.")
        print("\n--- top hits ---")
        for t in report.turns[: args.top]:
            flags = []
            if t.next_user_correction:
                flags.append("USER_CORRECTED")
            if t.eval_trap_failure:
                flags.append("EVAL_TRAP_FAIL")
            flag = f" [{','.join(flags)}]" if flags else ""
            print(f"[{t.score}] {t.klass}{flag}")
            print(f"  {Path(t.session).name}")
            print(f"  {t.excerpt[:100]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())