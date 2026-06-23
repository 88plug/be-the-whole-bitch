#!/usr/bin/env python3
import json
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


class TestYieldScore(unittest.TestCase):
    def test_yield_turn_scores_high(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(YIELD_TRANSCRIPT)
            path = Path(f.name)
        turn = parse_assistant_turns(path)[0]
        r = score_turn(turn)
        self.assertEqual(r.verdict, "yield")
        self.assertGreaterEqual(r.score, 40)
        path.unlink()

    def test_sudo_command_handoff_scores_yield(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(SUDO_HANDOFF_TRANSCRIPT)
            path = Path(f.name)
        turn = parse_assistant_turns(path)[0]
        r = score_turn(turn)
        self.assertEqual(r.verdict, "yield")
        self.assertIn("need_sudo_run", r.offenders)
        self.assertIn("shell_fence_no_tool", r.offenders)
        path.unlink()

    def test_tool_then_complete_scores_low(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(OK_TRANSCRIPT)
            path = Path(f.name)
        turns = parse_assistant_turns(path)
        r = score_turn(turns[-1])
        self.assertEqual(r.verdict, "ok")
        path.unlink()


if __name__ == "__main__":
    unittest.main()