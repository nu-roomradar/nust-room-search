"""
app.py（検索アプリ）の最小テスト。
時間割DB（schedule_final.db）は本物をコピーし、揮発DB（reservations.db / reports.db）は
一時ディレクトリに作る。app.py は cwd 直下の DB ファイルを使うため、import 前に chdir する。
実行: python -m unittest discover -s tests -v
"""
import datetime
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
rr = None          # setUpModule で import する app モジュール
_tmp = None
_cwd = None


def setUpModule():
    global rr, _tmp, _cwd
    _tmp = tempfile.mkdtemp(prefix="rr-app-")
    shutil.copy(ROOT / "schedule_final.db", _tmp)
    _cwd = os.getcwd()
    os.chdir(_tmp)
    sys.path.insert(0, str(ROOT))
    import app as _app  # noqa: E402  import 時に揮発DBを cwd（一時dir）に作る
    rr = _app
    rr.app.config["TESTING"] = True


def tearDownModule():
    os.chdir(_cwd)
    shutil.rmtree(_tmp, ignore_errors=True)


def _fixed_now(month, day):
    """get_active_terms などが見る「今」を固定する"""
    fixed = datetime.datetime(2026, month, day, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=9)))

    class FakeDT(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed
    return mock.patch.object(rr.datetime, "datetime", FakeDT)


class PureLogicTests(unittest.TestCase):
    def test_period_end_dt_has_right_time_weekday_and_tz(self):
        for idx, day in enumerate("月火水木金土"):
            dt = rr.period_end_dt(day, 3)
            self.assertEqual((dt.hour, dt.minute), (15, 0), day)     # 3限は 13:20–15:00
            self.assertEqual(dt.weekday(), idx, day)
            self.assertEqual(dt.utcoffset(), datetime.timedelta(hours=9))
            self.assertGreaterEqual(dt.date(), datetime.datetime.now(rr.JST).date())

    def test_active_terms_switch_on_sep_20(self):
        with _fixed_now(4, 1):
            self.assertEqual(rr.get_active_terms(), ['前期', '通年'])
        with _fixed_now(9, 20):
            self.assertEqual(rr.get_current_term_label(), '前期')
        with _fixed_now(9, 21):
            self.assertEqual(rr.get_active_terms(), ['後期', '通年'])
        with _fixed_now(3, 31):
            self.assertEqual(rr.get_current_term_label(), '後期')

    def test_rate_limit_blocks_after_limit_and_recovers_after_window(self):
        rr._rate_store.clear()
        for _ in range(rr.RATE_LIMIT):
            self.assertFalse(rr.is_rate_limited("ip-a"))
        self.assertTrue(rr.is_rate_limited("ip-a"))
        self.assertFalse(rr.is_rate_limited("ip-b"))               # 別IPは独立
        later = time.time() + rr.RATE_WINDOW + 1
        with mock.patch.object(rr.time, "time", return_value=later):
            self.assertFalse(rr.is_rate_limited("ip-a"))           # 窓が過ぎれば回復

    def test_cancel_code_format(self):
        for _ in range(50):
            code = rr.make_cancel_code()
            self.assertRegex(code, r"^[A-Z0-9]{6}$")


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.c = rr.app.test_client()
        rr._rate_store.clear()
        for db, table in ((rr.RESERVE_DB, "reservations"), (rr.REPORTS_DB, "reports")):
            conn = sqlite3.connect(db)
            conn.execute(f"DELETE FROM {table}")
            conn.commit(); conn.close()

    def reserve(self, **over):
        body = {"room": "1041", "building": "船橋校舎", "day": "月", "period": 2, "name": "テスト太郎", "purpose": "自習"}
        body.update(over)
        return self.c.post("/api/reserve", json=body)

    def test_reserve_roundtrip(self):
        r = self.reserve()
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["ok"]); self.assertEqual(j["count"], 1)
        code = j["cancel_code"]

        lst = self.c.get("/api/reserve/list?day=月&period=2").get_json()
        self.assertEqual([x["room"] for x in lst["reservations"]], ["1041"])
        self.assertEqual(lst["reservations"][0]["name"], "テスト太郎")

        wrong = self.c.post("/api/reserve/cancel", json={"room": "1041", "day": "月", "period": 2, "cancel_code": "XXXXXX"})
        self.assertFalse(wrong.get_json()["ok"])
        right = self.c.post("/api/reserve/cancel", json={"room": "1041", "day": "月", "period": 2, "cancel_code": code})
        self.assertTrue(right.get_json()["ok"])
        self.assertEqual(self.c.get("/api/reserve/list?day=月&period=2").get_json()["reservations"], [])

    def test_reserve_rejects_invalid_input(self):
        for bad in ({"day": "日"}, {"period": 7}, {"period": "2"}, {"name": ""}, {"room": " "}):
            r = self.reserve(**bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertEqual(r.get_json()["error"], "invalid")
        self.assertEqual(self.c.post("/api/reserve", data="not json").status_code, 400)
        self.assertEqual(self.c.get("/api/reserve/list?day=日&period=2").status_code, 400)
        self.assertEqual(self.c.get("/api/reserve/list?day=月&period=9").status_code, 400)

    def test_reserve_truncates_long_fields(self):
        self.reserve(name="あ" * 40, purpose="い" * 100)
        item = self.c.get("/api/reserve/list?day=月&period=2").get_json()["reservations"][0]
        self.assertEqual(len(item["name"]), 30)
        self.assertEqual(len(item["purpose"]), 60)

    def test_reserve_rate_limited_returns_429(self):
        with mock.patch.object(rr, "RATE_LIMIT", 2):
            self.assertEqual(self.reserve().status_code, 200)
            self.assertEqual(self.reserve().status_code, 200)
            r = self.reserve()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.get_json()["error"], "rate_limited")

    def test_expired_reservations_are_cleaned_on_list(self):
        past = (datetime.datetime.now(rr.JST) - datetime.timedelta(days=1)).isoformat()
        conn = sqlite3.connect(rr.RESERVE_DB)
        conn.execute("INSERT INTO reservations (room, building, day, period, name, purpose, cancel_code, created_at, expires_at) "
                     "VALUES ('1041','船橋校舎','月',2,'古い','',  'ABC123', ?, ?)", (past, past))
        conn.commit(); conn.close()
        self.assertEqual(self.c.get("/api/reserve/list?day=月&period=2").get_json()["reservations"], [])

    def test_report_counts_and_cancel(self):
        body = {"room": "1041", "day": "月", "period": 2}
        first = self.c.post("/api/report", json=body).get_json()
        second = self.c.post("/api/report", json=body).get_json()
        self.assertEqual((first["count"], second["count"]), (1, 2))
        self.assertEqual(rr.get_report_counts("月", 2), {"1041": 2})
        self.assertEqual(rr.get_report_counts("火", 2), {})

        r = self.c.post("/api/report/cancel", json={**body, "cancel_code": first["cancel_code"]})
        self.assertTrue(r.get_json()["ok"])
        self.assertEqual(rr.get_report_counts("月", 2), {"1041": 1})
        self.assertEqual(self.c.post("/api/report", json={"room": "", "day": "月", "period": 2}).status_code, 400)
        self.assertEqual(self.c.post("/api/report/cancel", json={"room": "1041"}).status_code, 400)


class PageTests(unittest.TestCase):
    def setUp(self):
        self.c = rr.app.test_client()
        rr._rate_store.clear()
        conn = sqlite3.connect(rr.REPORTS_DB); conn.execute("DELETE FROM reports"); conn.commit(); conn.close()

    def test_index_get_shows_form_and_notice(self):
        r = self.c.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn('id="search-form"', html)
        self.assertIn("テスト運用中", html)          # CLAUDE.md ルール1
        self.assertIn("大学公式", html)

    def test_search_post_lists_rooms_and_keeps_notice(self):
        r = self.c.post("/", data={"day": "月", "period": "2", "building": "all"})
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("room-card", html)
        self.assertIn("テスト運用中", html)
        rooms = re.findall(r"openModal\('([^']+)'", html)
        self.assertGreater(len(rooms), 10)         # 時間割DBから空き教室が引けている

        only_f = self.c.post("/", data={"day": "月", "period": "2", "building": "funabashi"}).get_data(as_text=True)
        self.assertIn("船橋校舎", only_f)
        self.assertNotIn("room-card tower", only_f)

    def test_reported_room_is_greyed_out_after_threshold(self):
        html = self.c.post("/", data={"day": "月", "period": "2", "building": "all"}).get_data(as_text=True)
        room = re.findall(r"openModal\('([^']+)'", html)[0]
        for _ in range(rr.REPORT_THRESHOLD):
            self.c.post("/api/report", json={"room": room, "day": "月", "period": 2})
        html = self.c.post("/", data={"day": "月", "period": "2", "building": "all"}).get_data(as_text=True)
        self.assertIn("使用中の可能性", html)
        self.assertRegex(html, r'class="room-card \w+ reported')


if __name__ == "__main__":
    unittest.main()
