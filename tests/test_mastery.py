# -*- coding: utf-8 -*-
"""mastery.py 的单元测试。"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mastery  # noqa: E402


def new_state():
    return mastery.default_state("test")


class MasteryTests(unittest.TestCase):
    def test_first_pass_requires_variant(self):
        state = new_state()
        result = mastery.record_result(
            state, "位权", "pass", unit="U4", kind="first"
        )
        concept = result["concept"]
        self.assertEqual(concept["level"], 2)
        self.assertFalse(concept["variant_passed"])
        self.assertFalse(concept["advance_ready"])
        self.assertEqual(result["action"]["type"], "practice")
        self.assertEqual(result["action"].get("mode"), "variant")

    def test_variant_pass_advances(self):
        state = new_state()
        mastery.record_result(state, "位权", "pass", unit="U4", kind="first")
        result = mastery.record_result(
            state, "位权", "pass", unit="U4", kind="variant"
        )
        concept = result["concept"]
        self.assertEqual(concept["level"], 3)
        self.assertTrue(concept["variant_passed"])
        self.assertTrue(concept["advance_ready"])
        self.assertEqual(result["action"]["type"], "advance")

    def test_partial_and_fail(self):
        state = new_state()
        partial = mastery.record_result(state, "位权", "partial", kind="first")
        self.assertEqual(partial["concept"]["level"], 1)
        self.assertEqual(partial["action"]["type"], "practice")
        fail = mastery.record_result(state, "位权", "fail", kind="practice")
        self.assertEqual(fail["concept"]["level"], 0)
        self.assertFalse(fail["concept"]["advance_ready"])
        self.assertEqual(fail["action"]["type"], "reteach")

    def test_review_due_cap_and_defer(self):
        state = new_state()
        past = (date.today() - timedelta(days=2)).isoformat()
        for name in ["A", "B", "C", "D", "E", "F"]:
            state["mastery"]["concepts"][name] = {
                "name": name,
                "level": 2,
                "last_result": "pass",
                "next_review_at": past,
                "attempts": 1,
            }
        action = mastery.recommend(state)
        self.assertEqual(action["type"], "review")
        self.assertEqual(action["suggested_count"], 3)
        self.assertEqual(action["deferred_count"], 3)

    def test_review_under_threshold_shows_all(self):
        state = new_state()
        past = (date.today() - timedelta(days=2)).isoformat()
        for name in ["A", "B", "C", "D"]:
            state["mastery"]["concepts"][name] = {
                "name": name,
                "level": 2,
                "last_result": "pass",
                "next_review_at": past,
                "attempts": 1,
            }
        action = mastery.recommend(state)
        self.assertEqual(action["type"], "review")
        self.assertEqual(action["suggested_count"], 4)
        self.assertEqual(action["deferred_count"], 0)

    def test_immediate_fail_beats_review(self):
        state = new_state()
        past = (date.today() - timedelta(days=2)).isoformat()
        state["mastery"]["concepts"]["旧知识"] = {
            "name": "旧知识",
            "level": 2,
            "last_result": "pass",
            "next_review_at": past,
        }
        state["mastery"]["concepts"]["新知识"] = {
            "name": "新知识",
            "level": 1,
            "last_result": "fail",
            "next_review_at": (date.today() + timedelta(days=1)).isoformat(),
        }
        action = mastery.recommend(state)
        self.assertEqual(action["type"], "reteach")
        self.assertEqual(action["target"], "新知识")

    def test_practice_targets_weak_first(self):
        state = new_state()
        mastery.record_result(state, "已掌握", "pass", kind="first")
        mastery.record_result(state, "已掌握", "pass", kind="variant")
        mastery.record_result(state, "薄弱", "fail", kind="first")
        targets = mastery.practice_targets(state, count=3)
        self.assertEqual(targets[0]["concept"], "薄弱")
        self.assertEqual(targets[0]["level"], 0)
        self.assertIn("概念辨析题", targets[0]["question_types"])

    def test_complete_unit_requires_advance_ready(self):
        state = new_state()
        state["route"]["total_units"] = 2
        mastery.record_result(
            state,
            "位权",
            "pass",
            unit="U4",
            unit_title="进位计数制",
            complete_unit=True,
            kind="first",
        )
        self.assertEqual(state["progress"]["completed_units"], [])
        mastery.record_result(
            state,
            "位权",
            "pass",
            unit="U4",
            unit_title="进位计数制",
            complete_unit=True,
            kind="variant",
        )
        self.assertEqual(len(state["progress"]["completed_units"]), 1)
        self.assertEqual(state["progress"]["completed_units"][0]["name"], "进位计数制")
        self.assertEqual(state["progress"]["overall_percent"], 50)

    def test_old_state_is_normalized(self):
        old = {
            "meta": {"name": "old"},
            "route": {"total_units": 1, "units": []},
            "progress": {"completed_units": [], "overall_percent": 0},
        }
        state = mastery.normalize_state(old)
        self.assertIn("mastery", state)
        self.assertIn("concepts", state["mastery"])
        self.assertEqual(state["meta"]["version"], mastery.VERSION)

    def test_invalid_result_raises(self):
        with self.assertRaises(ValueError):
            mastery.record_result(new_state(), "x", "maybe")

    def test_review_action_after_due(self):
        state = new_state()
        mastery.record_result(state, "位权", "pass", kind="first")
        state["mastery"]["concepts"]["位权"]["next_review_at"] = (
            date.today() - timedelta(days=1)
        ).isoformat()
        action = mastery.recommend(state)
        self.assertEqual(action["type"], "review")


if __name__ == "__main__":
    unittest.main()
