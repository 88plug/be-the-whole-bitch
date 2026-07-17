#!/usr/bin/env python3
"""Unit tests for yield-back scorer (synthetic transcripts only)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from btwb_lib import parse_assistant_turns  # noqa: E402
from btwb_score import score_turn  # noqa: E402


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


def _score_transcript(text: str, message_id: str | None = None, profile=None):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(text)
        path = Path(f.name)
    try:
        turns = parse_assistant_turns(path)
        if message_id:
            turn = next(t for t in turns if t.message_id == message_id)
        else:
            turn = turns[-1]
        return score_turn(turn, profile)
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


if __name__ == "__main__":
    unittest.main()
