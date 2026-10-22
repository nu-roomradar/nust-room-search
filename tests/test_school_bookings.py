"""
school_bookings.py（教務課の教室使用予定の取り込み・仮）のテスト。

- 環境変数が無ければ何もしない（いまの本番と同じ動き）
- 日付・時間帯・教室だけを残し、予約者名などほかの列は捨てる
- 読み取りに失敗しても前回の内容を使い続け、古すぎれば使わない
- 予定のある教室は検索結果の「空き」に出ない
実行: python -m unittest discover -s tests -v
"""
import datetime
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import school_bookings as sb  # noqa: E402

PERIODS = {1: ("09:00", "10:40"), 2: ("10:50", "12:30"), 3: ("13:20", "15:00"),
           4: ("15:10", "16:50"), 5: ("17:00", "18:40"), 6: ("18:50", "20:30")}
D = datetime.date(2026, 10, 26)

CSV = ("日付,開始,終了,教室,予約者,用途\n"
       "2026-10-26,10:50,12:30,S303,山田太郎,サークル\n"
       "2026/10/26,12:00,14:00,Ｓ３０４,佐藤花子,会議\n"
       "2026-10-27,18:50,20:30,1041,鈴木一郎,補講\n"
       "こわれた行,,,,,\n")


class ParseTests(unittest.TestCase):
    def test_times_map_to_overlapping_periods(self):
        data, skipped = sb.parse_text(CSV, PERIODS)
        self.assertEqual(data[D][2], {"s303", "s304"})       # 12:00-14:00 は2限と3限にかかる
        self.assertEqual(data[D][3], {"s304"})
        self.assertEqual(data[datetime.date(2026, 10, 27)][6], {"1041"})
        self.assertEqual(skipped, 1)

    def test_personal_columns_are_dropped(self):
        data, _ = sb.parse_text(CSV, PERIODS)
        self.assertNotIn("山田", repr(data))
        self.assertNotIn("サークル", repr(data))

    def test_period_column_and_ranges(self):
        text = "日付,時限,教室\n2026-10-26,2,S303\n2026-10-26,２～３限,S305\n2026-10-26,9,S306\n"
        data, skipped = sb.parse_text(text, PERIODS)
        self.assertEqual(data[D][2], {"s303", "s305"})
        self.assertEqual(data[D][3], {"s305"})
        self.assertEqual(skipped, 1)                         # 9限は無い

    def test_json_and_english_headers(self):
        text = '[{"date": "2026-10-26", "start": "9:00", "end": "10:40", "room": "S303", "name": "x"}]'
        data, _ = sb.parse_text(text, PERIODS)
        self.assertEqual(data[D][1], {"s303"})

    def test_shift_jis_is_decoded(self):
        self.assertIn("教室", sb._decode(CSV.encode("cp932")))

    def test_time_just_outside_a_period_does_not_block_it(self):
        self.assertEqual(sb.periods_overlapping("10:40", "10:50", PERIODS), set())   # 休み時間だけ
        self.assertEqual(sb.periods_overlapping("08:00", "09:01", PERIODS), {1})


class SourceTests(unittest.TestCase):
    def setUp(self):
        sb._reset_for_tests()
        self.tmp = tempfile.mkdtemp(prefix="sb-")
        self.path = os.path.join(self.tmp, "bookings.csv")
        Path(self.path).write_text(CSV, encoding="utf-8")

    def tearDown(self):
        sb._reset_for_tests()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_disabled_without_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(sb.enabled())
            self.assertEqual(sb.booked_rooms(D, PERIODS), {})

    def test_reads_file_and_keeps_old_data_on_failure(self):
        with mock.patch.dict(os.environ, {sb.FILE_ENV: self.path}, clear=True):
            self.assertEqual(sb.booked_rooms(D, PERIODS)[2], {"s303", "s304"})
            os.remove(self.path)                             # 読み取り先が壊れても
            sb.refresh(PERIODS, force=True)
            self.assertEqual(sb.status()["error"], "FileNotFoundError")
            self.assertEqual(sb.booked_rooms(D, PERIODS)[2], {"s303", "s304"})   # 前回の内容を使う

    def test_stale_data_is_not_used(self):
        with mock.patch.dict(os.environ, {sb.FILE_ENV: self.path}, clear=True):
            sb.refresh(PERIODS, force=True)
            sb._state["loaded_at"] -= sb.MAX_STALE + 1
            sb._state["checked_at"] = sb.time.time()         # 読み直しはまだ
            self.assertEqual(sb.booked_rooms(D, PERIODS), {})

    def test_only_https_urls(self):
        with mock.patch.dict(os.environ, {sb.URL_ENV: "http://example.invalid/x.csv"}, clear=True):
            sb.refresh(PERIODS, force=True)
            self.assertEqual(sb.status()["error"], "ValueError")
            self.assertEqual(sb.booked_rooms(D, PERIODS), {})

    def test_status_does_not_expose_contents(self):
        with mock.patch.dict(os.environ, {sb.FILE_ENV: self.path}, clear=True):
            sb.refresh(PERIODS, force=True)
            st = sb.status()
            self.assertEqual(st["days"], 2)
            self.assertNotIn("S303", repr(st))


class SearchIntegrationTests(unittest.TestCase):
    """予定のある教室は、検索結果の「空き」に出ない"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="sb-app-")
        shutil.copy(ROOT / "schedule_final.db", cls.tmp)
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        import app as rr
        cls.rr = rr
        rr.app.config["TESTING"] = True
        rr.init_reports_db()          # 報告の DB は相対パス。ほかのテストが先に app を import していても、ここに作る

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        sb._reset_for_tests()
        self.c = self.rr.app.test_client()
        fixed = datetime.datetime(2026, 10, 26, 8, 0, tzinfo=self.rr.JST)   # 月曜の朝（後期）

        class FakeDT(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed
        self.clock = mock.patch.object(self.rr.datetime, "datetime", FakeDT)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        sb._reset_for_tests()

    def free_rooms(self, env):
        with mock.patch.dict(os.environ, env, clear=False):
            sb._reset_for_tests()
            html = self.c.post("/", data={"day": "月", "period": "2", "building": "all", "year": "2026",
                                          "term": "後期", "span": "1"}).get_data(as_text=True)
        return re.findall(r'data-room="([^"]+)"', html), html

    def test_booked_room_is_hidden_and_others_stay(self):
        os.environ.pop(sb.FILE_ENV, None)
        os.environ.pop(sb.URL_ENV, None)
        before, _ = self.free_rooms({})
        self.assertGreater(len(before), 2)
        target, other = before[0], before[1]
        path = os.path.join(self.tmp, "b.csv")
        Path(path).write_text(f"日付,開始,終了,教室,予約者\n2026-10-26,10:50,12:30,{target},山田\n", encoding="utf-8")
        after, html = self.free_rooms({sb.FILE_ENV: path})
        self.assertNotIn(target, after)
        self.assertIn(other, after)
        self.assertNotIn("山田", html)

    def test_other_term_view_ignores_bookings(self):
        # 予定は日付で来るので、いまの年度・学期以外を見ているときは使わない
        with mock.patch.dict(os.environ, {sb.FILE_ENV: "/nonexistent.csv"}), \
             mock.patch.object(sb, "booked_rooms", return_value={}) as booked:
            self.c.post("/", data={"day": "月", "period": "2", "building": "all", "year": "2026",
                                   "term": "前期", "span": "1"})
            booked.assert_not_called()
            self.c.post("/", data={"day": "月", "period": "2", "building": "all", "year": "2026",
                                   "term": "後期", "span": "1"})
            booked.assert_called_once()
            self.assertEqual(booked.call_args.args[0], datetime.date(2026, 10, 26))   # 月曜2限は当日の分

if __name__ == "__main__":
    unittest.main()
