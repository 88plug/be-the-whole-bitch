#!/usr/bin/env python3
"""Regression: committed synthetic transcripts — no local session paths."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "scorer_regression.jsonl"
sys.path.insert(0, str(ROOT / "bin"))

from btwb_lib import parse_assistant_turns  # noqa: E402
from btwb_score import score_turn  # noqa: E402


class TestScorerRegression(unittest.TestCase):
    def test_synthetic_fixtures_match_expectation(self):
        profile = {"threshold": 40, "hard_threshold": 60}
        mismatches = []
        with FIXTURES.open() as fh:
            for line in fh:
                row = json.loads(line)
                with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
                    f.write(row["transcript"])
                    path = Path(f.name)
                try:
                    turns = parse_assistant_turns(path)
                    mid = row["message_id"]
                    turn = next((t for t in turns if t.message_id == mid), turns[-1])
                    r = score_turn(turn, profile)
                    if r.verdict != row["expect_verdict"]:
                        mismatches.append((row["label"], r.verdict, row["expect_verdict"], r.score))
                finally:
                    path.unlink()
        self.assertEqual(mismatches, [], f"regression mismatches: {mismatches}")


if __name__ == "__main__":
    unittest.main()