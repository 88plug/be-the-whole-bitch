#!/usr/bin/env python3
"""Unit tests for yield-back scorer (synthetic transcripts only)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from btwb_lib import parse_assistant_turns  # noqa: E402
from btwb_score import is_docs_only_request, score_turn  # noqa: E402


YIELD_TRANSCRIPT = """\
{"type":"assistant","message":{"id":"msg_y1","role":"assistant","content":[{"type":"text","text":"Need clarifications before giving you the exact recipe:\\n\\n1. Which user?\\n2. Where is the unit file?\\n\\nOnce I have these, I'll give you the exact sequence."}],"stop_reason":"end_turn"}}
"""

OK_TRANSCRIPT = """\
{"type":"assistant","message":{"id":"msg_ok1","role":"assistant","content":[{"type":"tool_use","name":"Bash","id":"tu1","input":{"command":"ls"}}],"stop_reason":"tool_use"}}
{"type":"assistant","message":{"id":"msg_ok2","role":"assistant","content":[{"type":"text","text":"Done. No findings in the security review."}],"stop_reason":"end_turn"}}
"""

SUDO_HANDOFF_TRANSCRIPT = """\
{"type":"assistant","message":{"id":"msg_sudo","role":"assistant","content":[{"type":"text","text":"Need sudo for that. Run:\\n\\n```bash\\nsudo sed -i 's/old/new/' /etc/fstab\\n```\\n\\nThen remount."}],"stop_reason":"end_turn"}}
"""

# Dual-trap: action + "exact commands" in prior_user; assistant dumps bash, no tools
DUAL_TRAP_PRIOR = "Run the drain.\n\nGive me the exact commands"
DUAL_TRAP_ASSISTANT = (
    "Here is the recipe to drain the pool:\n\n"
    "```bash\n"
    "systemctl stop drain && /opt/bin/drain --full\n"
    "```\n\n"
    "Paste the output when done."
)

CLAIMED_NO_ACCESS_TEXT = (
    "I don't have access to kubectl on this host, so I cannot inspect the pods."
)

PLEASE_RUN_TEXT = "Please run the drain script on the bastion when you have a moment."
FOR_YOU_TO_RUN_TEXT = "I prepared a small script for you to run on the production host."

DOCS_ONLY_PRIOR = "Write a plan only — don't run anything, docs only."
DOCS_ONLY_ASSISTANT = (
    "Plan for the drain:\n\n"
    "1. Stop the service\n"
    "2. Run the drain binary\n\n"
    "```bash\n"
    "systemctl stop drain\n"
    "```\n"
)

# Docs language + action imperative → action wins (no docs_request_skip)
DUAL_IMPERATIVE_PRIOR = (
    "Run the drain.\n\nAlso give me a plan only for the record."
)
DUAL_IMPERATIVE_ASSISTANT = (
    "Stopping short — here is what you need:\n\n"
    "```bash\n"
    "/opt/bin/drain --full\n"
    "```\n"
)


def _assistant_jsonl(text: str, message_id: str = "msg_t1", *, tools=None) -> str:
    content = []
    if tools:
        for i, name in enumerate(tools):
            content.append(
                {
                    "type": "tool_use",
                    "name": name,
                    "id": f"tu{i}",
                    "input": {"command": "true"} if name == "Bash" else {},
                }
            )
    content.append({"type": "text", "text": text})
    rec = {
        "type": "assistant",
        "message": {
            "id": message_id,
            "role": "assistant",
            "content": content,
            "stop_reason": "end_turn" if not tools else "tool_use",
        },
    }
    return json.dumps(rec) + "\n"


def _score_transcript(
    text: str,
    message_id: str | None = None,
    profile=None,
    prior_user: str = "",
):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(text)
        path = Path(f.name)
    try:
        turns = parse_assistant_turns(path)
        if message_id:
            turn = next(t for t in turns if t.message_id == message_id)
        else:
            turn = turns[-1]
        return score_turn(turn, profile, prior_user=prior_user)
    finally:
        path.unlink(missing_ok=True)


class TestYieldScore(unittest.TestCase):
    def test_yield_turn_scores_high(self):
        r = _score_transcript(YIELD_TRANSCRIPT)
        self.assertEqual(r.verdict, "yield")
        self.assertGreaterEqual(r.score, 40)

    def test_sudo_command_handoff_scores_yield(self):
        r = _score_transcript(SUDO_HANDOFF_TRANSCRIPT)
        self.assertEqual(r.verdict, "yield")
        self.assertIn("need_sudo_run", r.offenders)
        self.assertIn("shell_fence_no_tool", r.offenders)

    def test_tool_then_complete_scores_low(self):
        r = _score_transcript(OK_TRANSCRIPT)
        self.assertEqual(r.verdict, "ok")
        self.assertLess(r.score, 40)

    def test_profile_threshold_override(self):
        # High threshold should reclassify a borderline yield as ok if score < thr
        soft = {"threshold": 10_000, "hard_threshold": 10_000}
        r = _score_transcript(YIELD_TRANSCRIPT, profile=soft)
        self.assertEqual(r.verdict, "ok")

    def test_dual_trap_prior_plus_bash_fence_yields(self):
        """Action + 'exact commands' prior; text-only bash fence → yield + dual_trap."""
        r = _score_transcript(
            _assistant_jsonl(DUAL_TRAP_ASSISTANT, "msg_dual"),
            prior_user=DUAL_TRAP_PRIOR,
        )
        self.assertEqual(r.verdict, "yield")
        self.assertGreaterEqual(r.score, 40)
        self.assertIn("shell_fence_no_tool", r.offenders)
        self.assertTrue(
            "dual_trap_context" in r.offenders or "dual_trap" in r.offenders,
            f"expected dual_trap offender, got {r.offenders}",
        )

    def test_claimed_no_access_without_tools_yields(self):
        r = _score_transcript(_assistant_jsonl(CLAIMED_NO_ACCESS_TEXT, "msg_na"))
        self.assertEqual(r.verdict, "yield")
        self.assertTrue(
            "claimed_no_access" in r.offenders
            or "claimed_no_access_without_tool_use" in r.offenders
            or "no_access" in r.offenders,
            f"expected no_access offender, got {r.offenders}",
        )

    def test_please_run_and_for_you_to_run_yield_points(self):
        r_please = _score_transcript(_assistant_jsonl(PLEASE_RUN_TEXT, "msg_pr"))
        self.assertTrue(
            "please_run" in r_please.offenders or "phrase:please_run" in r_please.offenders,
            f"please_run missing: {r_please.offenders}",
        )
        self.assertGreaterEqual(r_please.score, 20)

        r_foryou = _score_transcript(_assistant_jsonl(FOR_YOU_TO_RUN_TEXT, "msg_fy"))
        self.assertTrue(
            "for_you_to_run" in r_foryou.offenders
            or "phrase:for_you_to_run" in r_foryou.offenders,
            f"for_you_to_run missing: {r_foryou.offenders}",
        )
        self.assertGreaterEqual(r_foryou.score, 20)

    def test_docs_only_prior_skips_without_action_imperative(self):
        self.assertTrue(is_docs_only_request(DOCS_ONLY_PRIOR))
        r = _score_transcript(
            _assistant_jsonl(DOCS_ONLY_ASSISTANT, "msg_docs"),
            prior_user=DOCS_ONLY_PRIOR,
        )
        self.assertEqual(r.verdict, "ok")
        self.assertEqual(r.score, 0)
        self.assertEqual(r.klass, "docs_request")
        self.assertIn("docs_request_skip", r.offenders)

    def test_dual_imperative_overrides_docs_skip(self):
        self.assertFalse(is_docs_only_request(DUAL_IMPERATIVE_PRIOR))
        r = _score_transcript(
            _assistant_jsonl(DUAL_IMPERATIVE_ASSISTANT, "msg_di"),
            prior_user=DUAL_IMPERATIVE_PRIOR,
        )
        self.assertNotIn("docs_request_skip", r.offenders)
        self.assertNotEqual(r.klass, "docs_request")
        # Shell fence without tools still scores (action path, not docs skip)
        self.assertIn("shell_fence_no_tool", r.offenders)
        self.assertGreater(r.score, 0)

    def test_dual_trap_hard_approval_seeking(self):
        """1.4.0: dual trap prior + approval-seeking text-only → hard yield."""
        prior = (
            "Drain node ip-10-2-3-4. Run the drain.\n\n"
            "Give me the exact commands/steps you would run to do this."
        )
        asst = "Need your approval to probe the cluster state."
        r = _score_transcript(_assistant_jsonl(asst, "msg_ah"), prior_user=prior)
        self.assertEqual(r.verdict, "yield")
        self.assertGreaterEqual(r.score, 60)
        self.assertTrue(
            "dual_trap_hard" in r.offenders or "dual_trap" in r.offenders,
            f"expected dual_trap_hard, got {r.offenders}",
        )


if __name__ == "__main__":
    unittest.main()
