"""scripts/fetch_ga4_metrics.py の、GA4 に問い合わせない部分の検査"""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_ga4_metrics as g  # noqa: E402

D = datetime.date


class WeekTests(unittest.TestCase):
    def test_previous_full_week_from_monday_and_midweek(self):
        self.assertEqual(g.last_full_weeks(D(2026, 10, 12)), [(D(2026, 10, 5), D(2026, 10, 11))])
        self.assertEqual(g.last_full_weeks(D(2026, 10, 8)), [(D(2026, 9, 28), D(2026, 10, 4))])

    def test_several_weeks_oldest_first(self):
        w = g.last_full_weeks(D(2026, 10, 12), 3)
        self.assertEqual([s for s, _ in w], [D(2026, 9, 21), D(2026, 9, 28), D(2026, 10, 5)])
        self.assertTrue(all((e - s).days == 6 and s.weekday() == 0 for s, e in w))

    def test_merge_overwrites_same_week_and_sorts(self):
        old = [{"week_start": "2026-10-05", "x": 1}, {"week_start": "2026-09-28", "x": 1}]
        new = [{"week_start": "2026-10-05", "x": 2}, {"week_start": "2026-10-12", "x": 3}]
        self.assertEqual([(w["week_start"], w["x"]) for w in g.merge_weeks(old, new)],
                         [("2026-09-28", 1), ("2026-10-05", 2), ("2026-10-12", 3)])

    def test_markdown_table(self):
        z = {"users": 0, "sessions": 0, "page_views": 0}
        weeks = [{"week_start": "2026-10-05", "week_end": "2026-10-11", "app": {**z, "users": 8, "sessions": 10},
                  "lp": z, "events": {"search": 4}},
                 {"week_start": "2026-10-12", "week_end": "2026-10-18", "app": {**z, "users": 12, "sessions": 15},
                  "lp": z, "events": {}}]
        md = g.to_markdown(weeks)
        self.assertIn("| 2026-10-05〜10-11 | 8 | 10 | — | 4 |", md)
        self.assertIn("| 2026-10-12〜10-18 | 12 | 15 | +50% | 0 |", md)


if __name__ == "__main__":
    unittest.main()
