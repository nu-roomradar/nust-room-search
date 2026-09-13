"""
scripts/build_schedule_db.py の回帰テスト。

このスクリプトは年1回しか使わないので、壊れていても気づきにくい。
最低限「現行 DB を再現できること」と「本番 DB を勝手に触らないこと」を固定する。
原本（data/source/*.xls）が揃っているときだけ本体の検査を走らせ、無ければスキップする。
実行: python -m unittest discover -s tests -v
"""
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_schedule_db.py"
PROD_DB = ROOT / "schedule_final.db"
SRC = ROOT / "data" / "source"

sys.path.insert(0, str(ROOT / "scripts"))
import build_schedule_db as bsd  # noqa: E402

HAVE_SOURCES = SRC.is_dir() and any(SRC.glob("[0-9]_*.xls"))
needs_sources = unittest.skipUnless(HAVE_SOURCES, "原本 data/source/*.xls が無い")


def run(*args):
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=1800)
    return p.returncode, p.stdout + p.stderr


def rows_of(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        s = con.execute("SELECT 学科,履修期名,曜日,時限,教室,校舎,科目名 FROM schedules").fetchall()
        r = con.execute("SELECT name,building FROM classrooms").fetchall()
    finally:
        con.close()
    return s, r


class RoomTokenTests(unittest.TestCase):
    """教室名セルの割り方。中黒の扱いが理工と短大で逆なので、両方を固定する"""

    def test_splits_on_spaces_only(self):
        self.assertEqual(bsd.tokenize_rooms("633 635"), ["633", "635"])
        self.assertEqual(bsd.tokenize_rooms("819　826"), ["819", "826"])

    def test_does_not_split_inside_parentheses(self):
        self.assertEqual(bsd.tokenize_rooms("8号館実験室(819 826 829)"), ["8号館実験室(819 826 829)"])

    def test_middle_dot_splits_only_between_room_codes(self):
        # 短大の原本: 教室番号の区切り
        self.assertEqual(bsd.split_middle_dot("1111・521"), ["1111", "521"])
        self.assertEqual(bsd.split_middle_dot("521・522"), ["521", "522"])
        # 理工の原本: 教室名そのもの。割ると壊れる
        self.assertEqual(bsd.split_middle_dot("テクノ・工作技術センター"), ["テクノ・工作技術センター"])
        self.assertEqual(bsd.split_middle_dot("1041"), ["1041"])

    def test_junk_token_is_listed_as_dropped(self):
        self.assertIn("他", bsd.EXCEPTION_DROP)


class CliTests(unittest.TestCase):
    def test_rejects_bad_divisions(self):
        for bad in ("x", "", "1,x"):
            rc, out = run("--divisions", bad, "--no-write")
            self.assertEqual(rc, 1, bad)
            self.assertIn("--divisions", out)

    def test_missing_source_dir_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = run("--src", str(Path(tmp) / "nope"), "--no-write")
        self.assertEqual(rc, 1)
        self.assertIn("原本のフォルダがありません", out)

    @needs_sources
    def test_unknown_division_fails_clearly(self):
        rc, out = run("--divisions", "9", "--no-write")
        self.assertEqual(rc, 1)
        self.assertIn("合う原本がありません", out)


@needs_sources
class ReproductionTests(unittest.TestCase):
    """原本から現行 DB を再現できること。壊れたら年1回の入れ替えが成り立たない"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="bsd-"))
        cls.rikou = cls.tmp / "rikou.db"
        cls.allx = cls.tmp / "all.db"
        rc, out = run("--divisions", "1,3,4", "--out", str(cls.rikou))
        assert rc == 0, out
        rc, out = run("--out", str(cls.allx))
        assert rc == 0, out

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_rikou_only_reproduces_production_db_exactly(self):
        prod_s, prod_r = rows_of(PROD_DB)
        new_s, new_r = rows_of(self.rikou)
        self.assertEqual(Counter(new_s), Counter(prod_s), "schedules が現行 DB と一致しない")
        self.assertEqual(set(new_r), set(prod_r), "classrooms が現行 DB と一致しない")

    def test_including_tandai_adds_rows_but_not_classrooms(self):
        prod_s, prod_r = rows_of(PROD_DB)
        all_s, all_r = rows_of(self.allx)
        self.assertGreater(len(all_s), len(prod_s), "短大を入れたのに行が増えていない")
        self.assertEqual(set(all_r), set(prod_r),
                         "教室マスタが変わっている（短大専用教室を検索対象に入れてはいけない）")

    def test_tandai_marks_shared_rooms_as_occupied(self):
        prod_s, prod_r = rows_of(PROD_DB)
        all_s, _ = rows_of(self.allx)
        names = {n for n, _ in prod_r}
        old = {(x[1], x[2], x[3], x[4]) for x in prod_s}
        new = {(x[1], x[2], x[3], x[4]) for x in all_s}
        added = {x for x in new - old if x[3] in names}
        self.assertGreater(len(added), 0, "短大を入れても共用教室の占有が増えていない")

    def test_no_junk_room_in_output(self):
        all_s, _ = rows_of(self.allx)
        self.assertNotIn("他", {x[4] for x in all_s})

    def test_production_db_is_untouched(self):
        digest = hashlib.md5(PROD_DB.read_bytes()).hexdigest()
        rc, out = run("--out", str(self.tmp / "again.db"), "--report")
        self.assertEqual(rc, 0, out)
        self.assertEqual(hashlib.md5(PROD_DB.read_bytes()).hexdigest(), digest,
                         "--replace なしで本番 DB が変わった")


if __name__ == "__main__":
    unittest.main()
