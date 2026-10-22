"""
school_bookings.py（教務課の教室使用予定の取り込み・仮）のテスト。

- 環境変数が無ければ何もしない（いまの本番と同じ動き）
- 日付・時間帯・教室だけを残し、予約者名などほかの列は捨てる。ログ・status にも出さない
- 読めない応答（ログイン画面の HTML・空・見出し違い）では前回の内容を使い続け、古すぎれば使わない
- 読み取りは検索の応答の外で行い、上流が遅くても検索は待たされない
- 転送（リダイレクト）は追わず、鍵を転送先に送らない
- 予定のある教室は検索結果の「空き」に出ない
実行: python -m unittest discover -s tests -v
"""
import datetime
import http.server
import importlib
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
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
        data, counts = sb.parse_text(CSV, PERIODS)
        self.assertEqual(data[D][2], {"s303", "s304"})       # 12:00-14:00 は2限と3限にかかる
        self.assertEqual(data[D][3], {"s304"})
        self.assertEqual(data[datetime.date(2026, 10, 27)][6], {"1041"})
        self.assertEqual(counts["bad"], 1)

    def test_personal_columns_are_dropped(self):
        data, _ = sb.parse_text(CSV, PERIODS)
        self.assertNotIn("山田", repr(data))
        self.assertNotIn("サークル", repr(data))

    def test_period_column_and_ranges(self):
        text = "日付,時限,教室\n2026-10-26,2,S303\n2026-10-26,２～３限,S305\n2026-10-26,9,S306\n"
        data, counts = sb.parse_text(text, PERIODS)
        self.assertEqual(data[D][2], {"s303", "s305"})
        self.assertEqual(data[D][3], {"s305"})
        self.assertEqual(counts["bad"], 1)                   # 9限は無い

    def test_json_and_english_headers(self):
        text = '[{"Date": "2026-10-26", "start": "9:00", "end": "10:40", "room": "S303", "name": "x"}]'
        data, _ = sb.parse_text(text, PERIODS)
        self.assertEqual(data[D][1], {"s303"})

    def test_shift_jis_is_decoded(self):
        self.assertIn("教室", sb._decode(CSV.encode("cp932")))

    def test_time_just_outside_a_period_does_not_block_it(self):
        self.assertEqual(sb.periods_overlapping("10:40", "10:50", PERIODS), set())   # 休み時間だけ
        self.assertEqual(sb.periods_overlapping("08:00", "09:01", PERIODS), {1})

    def test_joint_room_abbreviation_is_split(self):
        self.assertEqual(sb.room_keys("1456/7/8"), ["1456", "1457", "1458"])
        self.assertEqual(sb.room_keys("Ｓ３０３／４"), ["s303", "s304"])
        self.assertEqual(sb.room_keys("階段教室(大)"), ["階段教室(大)"])

    def test_row_without_time_blocks_the_whole_day(self):
        data, _ = sb.parse_text("日付,教室,予約者\n2026-10-26,S303,x\n", PERIODS)
        self.assertEqual(set(data[D]), set(PERIODS))         # 終日（空きに出さない側）

    def test_blank_rows_and_out_of_hours_are_not_errors(self):
        text = "日付,開始,終了,教室\n2026-10-26,10:50,12:30,S303\n,,,\n2026-10-26,21:00,22:00,S303\n"
        data, counts = sb.parse_text(text, PERIODS)
        self.assertEqual(counts["bad"], 0)
        self.assertEqual(counts["ignored"], 2)

    def test_date_with_weekday_and_time_suffix(self):
        data, _ = sb.parse_text("日付,開始,終了,教室\n2026/10/26(月),10:50,24:00,S303\n", PERIODS)
        self.assertEqual(set(data[D]), {2, 3, 4, 5, 6})

    def test_unreadable_responses_are_errors_not_empty(self):
        for text in ("<!DOCTYPE html><html><body>ログイン</body></html>", "",
                     '{"items": [{"日付": "2026-10-26"}]}', "使用年月日,施設名\n2026-10-26,S303\n",
                     "教室予定一覧\n日付,教室\n2026-10-26,S303\n", "日付\t教室\n2026-10-26\tS303\n",
                     '[{"foo": 1}]', "日付,開始,終了,教室\nあ,い,う,え\n"):
            with self.assertRaises(ValueError, msg=text[:30]):
                sb.parse_text(text, PERIODS)

    def test_header_only_means_no_bookings(self):
        self.assertEqual(sb.parse_text("日付,開始,終了,教室\n", PERIODS)[0], {})
        self.assertEqual(sb.parse_text("[]", PERIODS)[0], {})


class SourceTests(unittest.TestCase):
    def setUp(self):
        sb._reset_for_tests()
        self.sync = mock.patch.object(sb, "SYNC", True)
        self.sync.start()
        self.tmp = tempfile.mkdtemp(prefix="sb-")
        self.path = os.path.join(self.tmp, "bookings.csv")
        Path(self.path).write_text(CSV, encoding="utf-8")

    def tearDown(self):
        self.sync.stop()
        sb._reset_for_tests()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_disabled_without_env(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(sb, "_read_source") as read:
            self.assertFalse(sb.enabled())
            self.assertEqual(sb.booked_rooms(D, PERIODS), {})
            read.assert_not_called()

    def test_reads_file_and_keeps_old_data_on_failure(self):
        with mock.patch.dict(os.environ, {sb.FILE_ENV: self.path}, clear=True):
            self.assertEqual(sb.booked_rooms(D, PERIODS)[2], {"s303", "s304"})
            os.remove(self.path)                             # 読み取り先が壊れても
            sb.refresh(PERIODS, force=True)
            self.assertEqual(sb.status()["error"], "FileNotFoundError")
            self.assertEqual(sb.booked_rooms(D, PERIODS)[2], {"s303", "s304"})   # 前回の内容を使う

    def test_login_page_does_not_wipe_previous_data(self):
        with mock.patch.dict(os.environ, {sb.FILE_ENV: self.path}, clear=True):
            sb.refresh(PERIODS, force=True)
            Path(self.path).write_text("<html><body>ログインしてください</body></html>", encoding="utf-8")
            sb.refresh(PERIODS, force=True)
            self.assertEqual(sb.status()["error"], "ValueError")
            self.assertEqual(sb.booked_rooms(D, PERIODS)[2], {"s303", "s304"})
            Path(self.path).write_text("日付,開始,終了,教室\n", encoding="utf-8")   # 正しく「予定なし」
            sb.refresh(PERIODS, force=True)
            self.assertIsNone(sb.status()["error"])
            self.assertEqual(sb.booked_rooms(D, PERIODS), {})

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

    def test_status_and_logs_do_not_expose_contents(self):
        secret_url = "https://example.invalid/bookings.csv?key=SECRET123"
        with mock.patch.dict(os.environ, {sb.FILE_ENV: self.path}, clear=True):
            with self.assertLogs(level="WARNING") as logs:
                sb.refresh(PERIODS, known_keys={"s303"}, force=True)
            st = sb.status()
        self.assertEqual(set(st), {"enabled", "loaded_at", "error", "days", "bad_rows", "unmatched"})
        self.assertEqual(st["days"], 2)
        self.assertEqual(st["unmatched"], 2)                 # s304・1041 は時間割の教室と照合できない
        for word in ("s303", "s304", "山田", "サークル"):
            self.assertNotIn(word, repr(st).lower())
            self.assertNotIn(word, "\n".join(logs.output).lower())
        with mock.patch.dict(os.environ, {sb.URL_ENV: secret_url, sb.TOKEN_ENV: "TOKEN456"}, clear=True), \
             mock.patch.object(sb._OPENER, "open", side_effect=urllib.error.URLError(f"failed {secret_url}")):
            with self.assertLogs(level="WARNING") as logs:
                sb.refresh(PERIODS, force=True)
        self.assertNotIn("SECRET123", "\n".join(logs.output))
        self.assertNotIn("TOKEN456", "\n".join(logs.output))

    def test_bad_interval_does_not_break_startup(self):
        for raw, want in (("5m", 300), ("0", 60), ("999999", sb.MAX_STALE // 2), ("", 300)):
            with mock.patch.dict(os.environ, {sb.INTERVAL_ENV: raw}):
                self.assertEqual(sb._interval_from_env(), want, raw)
        with mock.patch.dict(os.environ, {sb.INTERVAL_ENV: "5m"}):
            importlib.reload(sb)                             # import でアプリが落ちない
        importlib.reload(sb)

    def test_token_is_not_forwarded_on_redirect(self):
        req = sb._build_request("https://example.invalid/x.csv", "TOKEN456")
        self.assertIn("Authorization", req.unredirected_hdrs)
        self.assertNotIn("Authorization", req.headers)

    def test_redirects_are_not_followed(self):
        hits = []

        class Target(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.headers.get("Authorization"))
                self.send_response(200); self.end_headers(); self.wfile.write(b"x")

            def log_message(self, *a):
                pass

        target = http.server.HTTPServer(("127.0.0.1", 0), Target)

        class Redirect(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{target.server_port}/")
                self.end_headers()

            def log_message(self, *a):
                pass

        redirect = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
        for srv in (target, redirect):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with mock.patch.dict(os.environ, {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}):
                opener = sb.urllib.request.build_opener(sb.urllib.request.ProxyHandler({}), sb._NoRedirect)
                with self.assertRaises(urllib.error.HTTPError):
                    opener.open(sb._build_request(f"http://127.0.0.1:{redirect.server_port}/", "TOKEN456"), timeout=5)
            self.assertEqual(hits, [])                       # 転送先には行かない（鍵も送らない）
        finally:
            for srv in (target, redirect):
                srv.shutdown()
                srv.server_close()

    def test_slow_source_is_cut_off(self):
        class Slow:
            def read(self, n):
                time.sleep(0.02)
                return b"x"
        with mock.patch.object(sb, "READ_DEADLINE", 0.1):
            with self.assertRaises(TimeoutError):
                sb._read_all(Slow(), time.monotonic() + 0.1)


class BackgroundTests(unittest.TestCase):
    """読み取りは検索の応答の外で行う"""

    def setUp(self):
        sb._reset_for_tests()
        sb._worker.update(pid=None, ready=threading.Event())

    def tearDown(self):
        sb._reset_for_tests()
        sb._worker.update(pid=None, ready=threading.Event())

    def test_slow_source_does_not_block_search(self):
        def slow():
            time.sleep(2)
            return "日付,開始,終了,教室\n2026-10-26,10:50,12:30,S303\n"
        with mock.patch.dict(os.environ, {sb.FILE_ENV: "/unused.csv"}), \
             mock.patch.object(sb, "_read_source", side_effect=slow), \
             mock.patch.object(sb, "FIRST_LOAD_WAIT", 0.2):
            t0 = time.monotonic()
            self.assertEqual(sb.booked_rooms(D, PERIODS), {})   # まだ読めていない → 待たずに時間割だけ
            self.assertLess(time.monotonic() - t0, 1.0)
            self.assertTrue(sb._worker["ready"].wait(5))         # 裏で読み終わる
            self.assertEqual(sb.booked_rooms(D, PERIODS)[2], {"s303"})


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
        self.sync = mock.patch.object(sb, "SYNC", True)
        self.sync.start()
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
        self.sync.stop()
        sb._reset_for_tests()

    def search(self, term="後期"):
        html = self.c.post("/", data={"day": "月", "period": "2", "building": "all", "year": "2026",
                                      "term": term, "span": "1"}).get_data(as_text=True)
        return re.findall(r'data-room="([^"]+)"', html), html

    def test_booked_room_is_hidden_and_others_stay(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(sb.FILE_ENV, None)
            os.environ.pop(sb.URL_ENV, None)
            before, _ = self.search()
        self.assertGreater(len(before), 2)
        target, other = before[0], before[1]
        path = os.path.join(self.tmp, "b.csv")
        Path(path).write_text(f"日付,開始,終了,教室,予約者\n2026-10-26,10:50,12:30,{target},山田\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {sb.FILE_ENV: path}):
            sb._reset_for_tests()
            after, html = self.search()
        self.assertNotIn(target, after)
        self.assertIn(other, after)
        self.assertNotIn("山田", html)

    def test_other_term_view_ignores_bookings(self):
        # 予定は日付で来るので、いまの年度・学期以外を見ているときは使わない
        with mock.patch.dict(os.environ, {sb.FILE_ENV: "/nonexistent.csv"}), \
             mock.patch.object(sb, "booked_rooms", return_value={}) as booked:
            self.search(term="前期")
            booked.assert_not_called()
            self.search(term="後期")
            booked.assert_called_once()
            self.assertEqual(booked.call_args.args[0], datetime.date(2026, 10, 26))   # 月曜2限は当日の分


if __name__ == "__main__":
    unittest.main()
