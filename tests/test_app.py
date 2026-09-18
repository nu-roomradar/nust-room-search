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
    """get_current_term_label などが見る「今」を固定する"""
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

    def test_current_term_switches_on_sep_20(self):
        """4/1〜9/20 が前期、それ以外は後期。境界の両側を押さえる"""
        for month, day, expected in [(4, 1, '前期'), (9, 20, '前期'),
                                     (9, 21, '後期'), (3, 31, '後期')]:
            with _fixed_now(month, day):
                self.assertEqual(rr.get_current_term_label(), expected, f"{month}/{day}")

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


class TermFilterTests(unittest.TestCase):
    """検索が「今の学期」の時間割で絞り込まれること（4/1〜9/20 前期、それ以外 後期）"""

    def setUp(self):
        self.c = rr.app.test_client()
        rr._rate_store.clear()
        conn = sqlite3.connect(rr.REPORTS_DB); conn.execute("DELETE FROM reports"); conn.commit(); conn.close()
        # 後期には授業があるが前期には無い（曜日, 時限, 教室）を実データから1つ選ぶ
        db = sqlite3.connect(str(ROOT / "schedule_final.db"))
        self.day, self.period, self.room = db.execute("""
            SELECT s.曜日, s.時限, s.教室 FROM schedules s
            JOIN classrooms c ON c.name = s.教室
            WHERE s.履修期名 = '後期'
              AND s.曜日 IN ('月','火','水','木','金','土') AND s.時限 BETWEEN 1 AND 6
              AND NOT EXISTS (SELECT 1 FROM schedules t
                              WHERE t.曜日 = s.曜日 AND t.時限 = s.時限 AND t.教室 = s.教室
                                AND t.履修期名 = '前期')
            LIMIT 1""").fetchone()
        db.close()

    def rooms(self):
        html = self.c.post("/", data={"day": self.day, "period": str(self.period), "building": "all"}).get_data(as_text=True)
        return set(re.findall(r"openModal\('([^']+)'", html)), html

    def test_room_is_free_in_first_term_but_occupied_in_second(self):
        with _fixed_now(5, 1):
            rooms, html = self.rooms()
            self.assertIn(self.room, rooms)
        with _fixed_now(10, 1):
            rooms, html = self.rooms()
            self.assertNotIn(self.room, rooms)


class YearAndTermSelectionTests(unittest.TestCase):
    """年度と学期をサイト上で選べること。以前は日付から決め打ちで、他を見る手段が無かった"""

    def setUp(self):
        self.c = rr.app.test_client()
        rr._rate_store.clear()
        conn = sqlite3.connect(rr.REPORT_DB if hasattr(rr, "REPORT_DB") else rr.REPORTS_DB)
        conn.execute("DELETE FROM reports"); conn.commit(); conn.close()
        self.years = rr.get_available_years()

    def search(self, **over):
        body = {"day": "月", "period": "2", "building": "all"}
        body.update(over)
        return self.c.post("/", data=body).get_data(as_text=True)

    def rooms(self, html):
        return set(re.findall(r"openModal\('([^']+)'", html))

    def test_form_offers_year_and_term(self):
        html = self.c.get("/").get_data(as_text=True)
        self.assertIn('name="year"', html)
        self.assertIn('name="term"', html)
        for t in rr.VALID_TERMS:
            self.assertIn(f'value="{t}"', html)
        for y in self.years:
            self.assertIn(f'value="{y}"', html)

    def test_db_exposes_at_least_one_year(self):
        self.assertTrue(self.years, "DB に年度が入っていない（年度列の移行漏れ）")

    def test_term_changes_the_result(self):
        a = self.rooms(self.search(term="前期"))
        b = self.rooms(self.search(term="後期"))
        self.assertNotEqual(a, b, "前期と後期で空き教室が同じなのはおかしい")

    def test_selected_term_is_echoed_back(self):
        for term in rr.VALID_TERMS:
            html = self.search(term=term)
            self.assertRegex(html, rf'<option value="{term}" selected')
            self.assertIn(f"{term} 月曜 2限", html)

    def test_invalid_values_fall_back_instead_of_failing(self):
        for bad in ({"term": "ぬるぽ"}, {"year": "9999"}, {"year": "abc"}, {"term": ""}):
            html = self.search(**bad)
            self.assertIn("の空き教室", html)          # 落ちずに結果が出る
            self.assertNotIn("エラーが発生", html)

    def test_notice_only_when_viewing_another_term(self):
        notice = "の時間割を表示しています"
        current = rr.get_current_term_label()
        other = [t for t in rr.VALID_TERMS if t != current][0]
        self.assertNotIn(notice, self.search(term=current))
        self.assertIn(notice, self.search(term=other))

    def test_default_term_follows_the_date(self):
        with _fixed_now(5, 1):
            self.assertIn('<option value="前期" selected', self.c.get("/").get_data(as_text=True))
        with _fixed_now(10, 1):
            self.assertIn('<option value="後期" selected', self.c.get("/").get_data(as_text=True))

    def test_current_year_follows_the_japanese_academic_year(self):
        with _fixed_now(4, 1):
            self.assertEqual(rr.get_current_year(), 2026)
        with _fixed_now(3, 31):
            self.assertEqual(rr.get_current_year(), 2025)   # 1〜3月は前年度

    def test_resolve_year_prefers_current_then_newest(self):
        self.assertEqual(rr.resolve_year(None, []), None)
        self.assertEqual(rr.resolve_year("2026", [2026, 2025]), 2026)
        self.assertEqual(rr.resolve_year("2025", [2026, 2025]), 2025)
        self.assertEqual(rr.resolve_year("9999", [2026, 2025]), rr.get_current_year()
                         if rr.get_current_year() in (2026, 2025) else 2026)
        self.assertEqual(rr.resolve_year(None, [2019, 2018]), 2019)   # 現年度が無ければ最新

    def test_only_the_selected_year_is_searched(self):
        """他の年度の授業・教室が混ざらないこと（混ざると空き判定が狂う）"""
        conn = sqlite3.connect(f"file:{rr.DB_NAME}?mode=ro", uri=True)
        try:
            year = self.years[0]
            occupied = {r[0] for r in conn.execute(
                "SELECT DISTINCT 教室 FROM schedules WHERE 年度=? AND 曜日='月' AND 時限=2 AND 履修期名='前期'",
                (year,))}
            master = {r[0] for r in conn.execute(
                "SELECT name FROM classrooms WHERE 年度=?", (year,))}
        finally:
            conn.close()
        shown = self.rooms(self.search(term="前期", year=str(year)))
        self.assertEqual(shown, master - occupied,
                         "画面の空き教室が「その年度の教室マスタ − その年度の占有」と一致しない")


if __name__ == "__main__":
    unittest.main()
