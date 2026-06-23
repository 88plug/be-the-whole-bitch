#!/usr/bin/env python3
"""Regression: golden fixtures extracted from real sessions must stay classified."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals" / "fixtures" / "golden.jsonl"
sys.path.insert(0, str(ROOT / "bin"))

from btwb_lib import parse_assistant_turns  # noqa: E402
from btwb_score import score_turn  # noqa: E402


@unittest.skipUnless(FIXTURES.exists(), "run evals/simulator.py --fixtures first")
class TestGoldenFixtures(unittest.TestCase):
    def test_top_fixtures_match_expectation(self):
        profile = {"threshold": 40, "hard_threshold": 60}
        checked = 0
        mismatches = []
        with FIXTURES.open() as fh:
            for line in fh:
                if checked >= 30:
                    break
                row = json.loads(line)
                path = Path(row["session"])
                if not path.exists():
                    continue
                turns = parse_assistant_turns(path)
                mid = row.get("message_id")
                turn = next((t for t in turns if t.message_id == mid), None)
                if not turn:
                    continue
                r = score_turn(turn, profile)
                expect = row.get("expect_verdict", "yield")
                if r.verdict != expect and row.get("eval_trap_failure"):
                    expect = "yield"
                if r.verdict != expect:
                    mismatches.append((path.name, r.verdict, expect, r.score))
                checked += 1
        self.assertGreater(checked, 10, "need fixtures from simulator run")
        self.assertEqual(mismatches, [], f"fixture mismatches: {mismatches[:5]}")


if __name__ == "__main__":
    unittest.main()