#!/usr/bin/env python3
"""Simulator session scoring + user-correction detection."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "evals"))

from simulator import is_user_correction, simulate_session, USER_CORRECTION_RE  # noqa: E402


YIELD_SESSION = """\
{"type":"user","message":{"role":"user","content":"Change systemd user for app.service. Run it on prod."}}
{"type":"assistant","message":{"id":"msg1","role":"assistant","content":[{"type":"text","text":"Need clarifications before giving you the exact recipe:\\n\\n1. New user name?\\n2. Unit file path?\\n\\nOnce I see those I'll give you the sequence."}],"stop_reason":"end_turn"}}
{"type":"user","message":{"role":"user","content":"just run it — user is deploy, file is /etc/systemd/system/app.service"}}
"""

OK_SESSION = """\
{"type":"user","message":{"role":"user","content":"check nginx config"}}
{"type":"assistant","message":{"id":"msg1","role":"assistant","content":[{"type":"tool_use","name":"Bash","id":"t1","input":{"command":"nginx -t"}}],"stop_reason":"tool_use"}}
{"type":"assistant","message":{"id":"msg2","role":"assistant","content":[{"type":"text","text":"nginx -t passed. No findings."}],"stop_reason":"end_turn"}}
"""

PROFILE = {"threshold": 40, "hard_threshold": 60}


def _simulate(text: str, profile=None):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(text)
        path = Path(f.name)
    try:
        return simulate_session(path, profile or PROFILE)
    finally:
        path.unlink(missing_ok=True)


class TestSimulator(unittest.TestCase):
    def test_detects_yield_and_following_correction(self):
        turns, _ = _simulate(YIELD_SESSION)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].verdict, "yield")
        self.assertTrue(turns[0].next_user_correction)

    def test_ok_session_low_yield(self):
        turns, _ = _simulate(OK_SESSION)
        self.assertEqual(turns[-1].verdict, "ok")

    def test_correction_regex(self):
        self.assertTrue(USER_CORRECTION_RE.search("do it for me — just run it yourself"))

    def test_ignores_task_notification_followups(self):
        self.assertFalse(
            is_user_correction(
                "<task-notification>\n<status>completed</status>\n</task-notification>"
            )
        )

    def test_short_drive_imperatives_count(self):
        self.assertTrue(is_user_correction("go"))
        self.assertFalse(is_user_correction("Drive the build-my-docker milestone ladder"))

    def test_empty_session_no_turns(self):
        turns, meta = _simulate("")
        self.assertEqual(turns, [])
        self.assertIsNotNone(meta)


if __name__ == "__main__":
    unittest.main()
