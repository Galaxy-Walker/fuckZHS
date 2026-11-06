import json
import os
import tempfile
import unittest
from unittest.mock import patch

from habit import HabitState


class HabitStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "habit_state.json")

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, **kwargs):
        return HabitState(self.path, "acc", "course", **kwargs)

    def test_fresh_state(self):
        state = self.make()
        self.assertEqual(state.today_seconds(), 0)
        self.assertTrue(state.can_start()[0])
        self.assertEqual(state.completed_sessions(), 0)

    def test_complete_one_day_and_same_day_guard(self):
        with patch("habit._today", return_value="2026-11-05"):
            state = self.make()
            state.add_seconds(1500)
            self.assertTrue(state.today_completed())
            self.assertEqual(state.completed_sessions(), 1)
            self.assertEqual(state.can_start(), (False, "today"))
            self.assertFalse(state.mark_today_complete())  # already counted

        with patch("habit._today", return_value="2026-11-06"):
            reloaded = self.make()
            self.assertEqual(reloaded.completed_sessions(), 1)
            self.assertTrue(reloaded.can_start()[0])
            reloaded.add_seconds(1500)
            self.assertEqual(reloaded.completed_sessions(), 2)

    def test_partial_day_resumes(self):
        with patch("habit._today", return_value="2026-11-05"):
            state = self.make()
            state.add_seconds(600)
            self.assertFalse(state.today_completed())
            self.assertEqual(state.remaining_seconds(), 900)
            reloaded = self.make()
            self.assertEqual(reloaded.today_seconds(), 600)
            self.assertEqual(reloaded.remaining_seconds(), 900)

    def test_five_distinct_days(self):
        with patch("habit._today", return_value="2026-11-05"):
            state = self.make()
        for day in range(5, 10):
            with patch("habit._today", return_value=f"2026-11-{day:02d}"):
                state.add_seconds(1500)
                state.mark_today_complete()
        self.assertEqual(state.completed_sessions(), 5)
        self.assertEqual(state.can_start(), (False, "done"))

    def test_summary_and_reset(self):
        with patch("habit._today", return_value="2026-11-05"):
            state = self.make()
            state.add_seconds(1500)
        text = HabitState.summary_all(self.path)
        self.assertIn("1/5", text)
        self.assertIn("2026-11-05", text)
        state.reset()
        self.assertEqual(state.completed_sessions(), 0)
        leftovers = [name for name in os.listdir(self.tmp.name)
                     if name.startswith(".habit_state.")]
        self.assertEqual(leftovers, [])

    def test_atomic_file_is_valid_json(self):
        with patch("habit._today", return_value="2026-11-05"):
            state = self.make()
            state.add_seconds(30)
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("accounts", data)


if __name__ == "__main__":
    unittest.main()
