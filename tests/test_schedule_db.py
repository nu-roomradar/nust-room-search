"""
schedule_final.db（時間割DB）の整合性テスト。
DB の作成手順は失われており（docs/OPERATIONS.md 6.）、差し替え時に欠けや壊れを見逃すと
検索結果が静かに間違う。最低限の形と量をここで保証する。
実行: python -m unittest discover -s tests -v
"""
import sqlite3
import unittest
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "schedule_final.db"
BUILDINGS = {"タワースコラ", "駿河台校舎", "船橋校舎"}
TERMS = {"前期", "後期"}
DAYS = {"月", "火", "水", "木", "金", "土"}
# 教室が未定の授業（実験など）に使われている仮の教室名。classrooms には存在しなくてよい
PLACEHOLDER_ROOMS = {"0000"}


class ScheduleDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def q(self, sql, *args):
        return self.c.execute(sql, args).fetchall()

    def test_tables_and_columns(self):
        cols = {r[1] for r in self.q("PRAGMA table_info(schedules)")}
        self.assertTrue({"学科", "履修期名", "曜日", "時限", "教室", "校舎", "科目名"} <= cols)
        cols = {r[1] for r in self.q("PRAGMA table_info(classrooms)")}
        self.assertTrue({"name", "building"} <= cols)

    def test_both_terms_and_all_buildings_have_data(self):
        rows = {(b, t): n for b, t, n in self.q("SELECT 校舎, 履修期名, COUNT(*) FROM schedules GROUP BY 校舎, 履修期名")}
        self.assertEqual({b for b, _ in rows}, BUILDINGS)
        self.assertEqual({t for _, t in rows}, TERMS, "履修期名は 前期/後期 に正規化されていること")
        for key, n in rows.items():
            self.assertGreater(n, 300, f"{key} の行数が少なすぎる（差し替えで欠けた可能性）")

    def test_days_and_periods_are_in_range(self):
        self.assertEqual({r[0] for r in self.q("SELECT DISTINCT 曜日 FROM schedules")}, DAYS)
        self.assertEqual({r[0] for r in self.q("SELECT DISTINCT 時限 FROM schedules")}, {1, 2, 3, 4, 5, 6})
        self.assertEqual(self.q("SELECT COUNT(*) FROM schedules WHERE 教室 IS NULL OR TRIM(教室) = ''")[0][0], 0)

    def test_every_rikou_room_is_in_classrooms(self):
        """理工学部・大学院の授業が使う教室は必ず検索対象に載っていること

        短期大学部の行は例外。短大専用教室はあえて classrooms に入れていない
        （占有判定には効かせるが、理工の学生には「空き」として出さない）。
        詳細は scripts/build_schedule_db.py の docstring と docs/OPERATIONS.md 6.
        """
        missing = {r[0] for r in self.q(
            "SELECT DISTINCT 教室 FROM schedules "
            "WHERE 教室 NOT IN (SELECT name FROM classrooms) AND 学科 NOT LIKE '短大 %'")}
        self.assertEqual(missing - PLACEHOLDER_ROOMS, set(),
                         "schedules にあって classrooms に無い教室（検索で永遠に表示されない）")

    def test_tandai_only_rooms_are_kept_out_of_classrooms(self):
        """短大専用教室が検索対象に混ざっていないこと（混ざると行っても使えない教室を出す）"""
        rooms = {r[0] for r in self.q("SELECT DISTINCT 教室 FROM schedules WHERE 学科 LIKE '短大 %'")}
        master = {r[0] for r in self.q("SELECT name FROM classrooms")}
        rikou = {r[0] for r in self.q("SELECT DISTINCT 教室 FROM schedules WHERE 学科 NOT LIKE '短大 %'")}
        tandai_only = rooms - rikou
        self.assertGreater(len(tandai_only), 0, "短大専用の教室が1つも無いのは想定外")
        self.assertEqual(tandai_only & master, set(),
                         "短大専用教室が classrooms に入っている")

    def test_no_broken_room_names(self):
        """カッコの対応が崩れた教室名が検索結果に出ないこと

        原本の「スタジオ（S701 S702 S705）」を全角カッコを守らずに空白で割った結果、
        「スタジオ（S701」「S705）」という教室が 2026-09 まで実在していた。
        """
        bad = [n for (n,) in self.q("SELECT name FROM classrooms")
               if n.count("(") + n.count("（") != n.count(")") + n.count("）")]
        self.assertEqual(bad, [], "カッコの対応が崩れた教室名がある")

    def test_classrooms_master_is_sane(self):
        self.assertEqual({r[0] for r in self.q("SELECT DISTINCT building FROM classrooms")}, BUILDINGS)
        self.assertGreater(self.q("SELECT COUNT(*) FROM classrooms")[0][0], 150)
        self.assertEqual(self.q("SELECT COUNT(*) FROM classrooms WHERE name IS NULL OR TRIM(name) = ''")[0][0], 0)
        dup = self.q("SELECT name FROM classrooms GROUP BY name HAVING COUNT(*) > 1")
        self.assertEqual(dup, [])

    # 船橋と駿河台に同じ番号の部屋があり、DB は教室名だけで束ねている（2026-09-11 時点で判明）。
    # 駿河台側の授業が船橋の同名教室を「使用中」にするが、空きを埋まって見せる方向なので安全側。
    # 原本を回収して校舎ごとに分けるまでは既知として許容し、これ以外が増えたら検知する。
    KNOWN_NAME_COLLISIONS = {"134", "143", "144", "まち製図室１～５"}

    def test_room_building_is_consistent_between_tables(self):
        bad = {r[0] for r in self.q("""
            SELECT DISTINCT s.教室 FROM schedules s
            JOIN classrooms c ON c.name = s.教室 WHERE s.校舎 != c.building""")}
        self.assertEqual(bad - self.KNOWN_NAME_COLLISIONS, set(),
                         "schedules と classrooms で校舎が食い違う教室が増えた（docs/OPERATIONS.md 6. 参照）")


if __name__ == "__main__":
    unittest.main()
