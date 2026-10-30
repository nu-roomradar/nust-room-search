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


class PurposeTests(unittest.TestCase):
    """使った目的のワンタップ調査（2026-10-25〜）"""

    def test_purpose_events_are_counted(self):
        for code in ("study", "group", "meeting", "break", "other"):
            self.assertIn(f"purpose_{code}", g.EVENTS)
        self.assertIn("purpose_skip", g.EVENTS)

    def test_markdown_has_purpose_table_only_after_answers_arrive(self):
        z = {"users": 0, "sessions": 0, "page_views": 0}
        before = {"week_start": "2026-10-19", "week_end": "2026-10-25", "app": z, "lp": z, "events": {"search": 3}}
        after = {"week_start": "2026-10-26", "week_end": "2026-11-01", "app": z, "lp": z,
                 "events": {"purpose_study": 5, "purpose_break": 2, "purpose_skip": 4}}
        self.assertNotIn("何に使う", g.to_markdown([before]))
        md = g.to_markdown([before, after])
        self.assertIn("| 2026-10-26〜11-01 | 5 | 0 | 0 | 2 | 0 | 7 | 4 |", md)
        self.assertNotIn("| 2026-10-19〜10-25 | 0 |", md.split("何に使う")[1])


class SearchValueTests(unittest.TestCase):
    def test_unknown_values_are_dropped(self):
        """GA4 には外部から偽の記録を送れる。アプリが送る値以外はダッシュボードに入れない"""
        items = [{"label": "main", "count": 5}, {"label": "<img src=x onerror=alert(1)>", "count": 50},
                 {"label": "(not set)", "count": 2}, {"label": "funabashi", "count": 1}]
        kept, dropped = g.keep_known("search_building", items)
        self.assertEqual([i["label"] for i in kept], ["main", "funabashi"])
        self.assertEqual(dropped, 2)
        self.assertEqual(g.keep_known("search_period", [{"label": "7", "count": 1}])[1], 1)
        self.assertEqual(g.keep_known("search_day", [{"label": "日", "count": 1}])[1], 1)

    def test_dashboard_escapes_data_before_innerhtml(self):
        """dashboard.html は JSON の文字を esc() を通してから画面に入れる"""
        html = (Path(__file__).resolve().parents[1] / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("const esc = s =>", html)
        self.assertIn("const name = esc(labelFn ? labelFn(i.label) : i.label);", html)
        self.assertIn("const title = p => esc(", html)
        self.assertNotIn("${p.permalink", html)


class ReportRoomTests(unittest.TestCase):
    def test_counts_only_reports_of_real_rooms(self):
        rows = [(["report_room", "S303", "タワースコラ"], ["3"]),
                (["reserve_room", "S303", "タワースコラ"], ["9"]),        # 廃止した仮予約は数えない
                (["report_room", "<b>x</b>", "タワースコラ"], ["50"]),    # 教室マスタに無い（偽の記録）
                (["report_room", "(not set)", "(not set)"], ["4"]),
                (["report_room", "1041", "駿河台校舎"], ["3"]),
                (["report_room", "S303", "タワースコラ"], ["1"])]
        got = g.top_report_rooms(rows, {"S303", "1041"})
        self.assertEqual(got, [{"label": "S303", "building": "タワースコラ", "count": 4},
                               {"label": "1041", "building": "駿河台校舎", "count": 3}])

    def test_known_rooms_come_from_the_timetable_db(self):
        rooms = g.known_rooms()
        self.assertIn("S303", rooms)
        self.assertGreater(len(rooms), 100)
        self.assertEqual(g.known_rooms("/nonexistent.db"), set())

    def test_markdown_lists_reported_rooms(self):
        md = g.to_markdown([], [{"label": "S303", "building": "タワースコラ", "count": 4}])
        self.assertIn("## 「実は使われていた」報告の多い教室（直近28日）", md)
        self.assertIn("| S303 | タワースコラ | 4 |", md)
        self.assertNotIn("報告の多い教室", g.to_markdown([]))


class DailyHistoryTests(unittest.TestCase):
    def test_totals_kept_and_app_lp_split_added(self):
        total = [(["20261028"], ["925", "921", "1976", "1115"]), (["20261027"], ["11", "4", "31", "14"])]
        hosts = [(["20261028", "nust-room-search.onrender.com"], ["600", "590", "1200", "700"]),
                 (["20261028", "nu-roomradar.github.io"], ["400", "398", "776", "415"]),
                 (["20261028", "evil.example"], ["9", "9", "9", "9"])]          # 知らないホストは捨てる
        h = g.daily_history(total, hosts)
        self.assertEqual([d["date"] for d in h], ["2026-10-27", "2026-10-28"])
        self.assertEqual(h[1]["active_users"], 925)
        self.assertEqual(h[1]["app"], {"active_users": 600, "new_users": 590, "page_views": 1200, "sessions": 700})
        self.assertEqual(h[1]["lp"]["page_views"], 776)
        self.assertNotIn("app", h[0])


class ReportCancelAndSlotTests(unittest.TestCase):
    """2026-10-26〜: 報告の取り消しを引き、報告の曜日・時限を数える"""

    def test_cancel_event_is_fetched(self):
        self.assertIn("report_cancel", g.EVENTS)

    def test_rooms_subtract_cancellations(self):
        rows = [(["report_room", "S303", "タワースコラ"], ["3"]),
                (["report_cancel", "S303", "タワースコラ"], ["1"]),
                (["report_room", "1041", "駿河台校舎"], ["1"]),
                (["report_cancel", "1041", "駿河台校舎"], ["1"]),   # 全部取り消された教室は出さない
                (["report_cancel", "131", "駿河台校舎"], ["1"])]    # 期間より前の報告の取り消し（負にしない）
        self.assertEqual(g.top_report_rooms(rows, {"S303", "1041", "131"}),
                         [{"label": "S303", "building": "タワースコラ", "count": 2}])

    def test_slots_by_day_and_period(self):
        rows = [(["report_room", "火", "2"], ["3"]),
                (["report_cancel", "火", "2"], ["1"]),
                (["report_room", "金", "6"], ["1"]),
                (["search", "火", "2"], ["40"]),                 # 検索は数えない
                (["purpose_study", "火", "2"], ["5"]),           # 使った目的の調査も数えない
                (["report_room", "(not set)", "(not set)"], ["7"]),  # 2026-10-25 までの報告
                (["report_room", "日", "<b>", ], ["9"]),         # アプリが送らない値（偽の記録）
                (["report_cancel", "月", "1"], ["2"])]           # 負にしない
        got = g.report_slots(rows)
        self.assertEqual(list(got), ["月", "火", "水", "木", "金", "土"])
        self.assertEqual(got["火"], [0, 2, 0, 0, 0, 0])
        self.assertEqual(got["金"], [0, 0, 0, 0, 0, 1])
        self.assertEqual(got["月"], [0] * 6)

    def test_markdown_weekly_column_is_net_of_cancellations(self):
        z = {"users": 0, "sessions": 0, "page_views": 0}
        weeks = [{"week_start": "2026-10-26", "week_end": "2026-11-01", "app": {**z, "users": 3, "sessions": 4},
                  "lp": z, "events": {"search": 9, "report_room": 5, "report_cancel": 2}}]
        self.assertIn("| 2026-10-26〜11-01 | 3 | 4 | — | 9 | 3 |", g.to_markdown(weeks))

    def test_markdown_slot_grid_only_when_there_are_reports(self):
        slots = {d: [0] * 6 for d in "月火水木金土"}
        self.assertNotIn("曜日・時限", g.to_markdown([], slots=slots))
        slots["火"][1] = 2
        md = g.to_markdown([], slots=slots)
        self.assertIn("## 「実は使われていた」報告の曜日・時限（直近28日）", md)
        self.assertIn("| 時限 | 月 | 火 | 水 | 木 | 金 | 土 |", md)
        self.assertIn("| 2限 | · | 2 | · | · | · | · |", md)

    def test_search_breakdown_counts_only_search_events(self):
        """検索条件の内訳に、同じ名前の値を送る使った目的の調査・報告を混ぜない"""
        rows = [(["search", "2"], ["10"]), (["purpose_group", "2"], ["4"]), (["report_room", "3"], ["1"]),
                (["search", "3"], ["5"]), (["search", "9"], ["1"])]
        kept, dropped = g.search_breakdown("search_period", rows)
        self.assertEqual(sorted((i["label"], i["count"]) for i in kept), [("2", 10), ("3", 5)])
        self.assertEqual(dropped, 1)

    def test_app_sends_day_period_and_cancellations(self):
        js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("gtag('event', 'report_room', reportEventParams());", js)
        self.assertIn("gtag('event', 'report_cancel', reportEventParams());", js)
        self.assertIn("search_day: RR.day, search_period: String(RR.period)", js)


if __name__ == "__main__":
    unittest.main()
