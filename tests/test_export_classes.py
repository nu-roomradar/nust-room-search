"""
scripts/export_classes.py（授業の生データ一覧）のテスト。
原本が無い環境ではスキップする。
実行: python -m unittest discover -s tests -v
"""
import csv
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_classes.py"
PROD_DB = ROOT / "schedule_final.db"
SRC = ROOT / "data" / "source"
COMMITTED_CSV = ROOT / "data" / "classes_2026.csv"

sys.path.insert(0, str(ROOT / "scripts"))
import export_classes as ec  # noqa: E402

HAVE_SOURCES = SRC.is_dir() and any(SRC.rglob("[0-9]_*.xls"))   # 年度フォルダの中を見る
needs_sources = unittest.skipUnless(HAVE_SOURCES, "原本 data/source/<年度>/*.xls が無い")


def run(*args):
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=1800)
    return p.returncode, p.stdout + p.stderr


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


class CliTests(unittest.TestCase):
    def test_rejects_bad_divisions(self):
        for bad in ("x", "", "1,x"):
            rc, out = run("--divisions", bad)
            self.assertEqual(rc, 1, bad)
            self.assertIn("--divisions", out)

    def test_missing_source_dir_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = run("--src", str(Path(tmp) / "nope"))
        self.assertEqual(rc, 1)
        self.assertIn("原本のフォルダがありません", out)


@needs_sources
class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ec-"))
        cls.out = cls.tmp / "classes.csv"
        rc, out = run("--out", str(cls.out))
        assert rc == 0, out
        cls.rows = read_csv(cls.out)

    def test_has_the_columns_the_db_throws_away(self):
        self.assertEqual(list(self.rows[0].keys()), ec.FIELDS)
        for col in ("時間割CD", "単位", "対象学年", "教員名"):
            self.assertTrue(any(r[col] for r in self.rows), f"{col} が全行空")

    def test_row_count_matches_the_database(self):
        con = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
        try:
            n = con.execute("SELECT COUNT(*) FROM schedules").fetchone()[0]
        finally:
            con.close()
        self.assertEqual(len(self.rows), n, "CSV と schedules の行数が違う（数え方がずれている）")

    def test_matches_the_database_row_for_row(self):
        con = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
        try:
            db = con.execute(
                "SELECT 学科,履修期名,曜日,時限,教室,校舎,科目名 FROM schedules").fetchall()
        finally:
            con.close()
        from collections import Counter
        csv_keys = Counter((r["学科"], r["履修期名"], r["曜日"], int(r["時限"]),
                            r["教室"], r["校舎"], r["科目名"]) for r in self.rows)
        self.assertEqual(csv_keys, Counter(db))

    def test_undecided_room_is_excluded(self):
        self.assertNotIn("000", {r["教室"] for r in self.rows})

    def test_divisions_filter_shrinks_the_output(self):
        out2 = self.tmp / "rikou.csv"
        rc, msg = run("--divisions", "1,3,4", "--out", str(out2))
        self.assertEqual(rc, 0, msg)
        rows2 = read_csv(out2)
        self.assertLess(len(rows2), len(self.rows))
        self.assertNotIn("短期大学部", {r["区分"] for r in rows2})

    def test_committed_csv_is_up_to_date(self):
        """コミット済みの年度別 CSV が原本とずれていないこと（原本を入れ替えたら再生成する）

        既定の出力は年度ごとに 1 ファイル（data/classes_<年度>.csv）。
        """
        years = sorted({r["年度"] for r in self.rows})
        checked = 0
        for year in years:
            path = ROOT / "data" / f"classes_{year}.csv"
            if not path.exists():
                continue
            expected = [r for r in self.rows if r["年度"] == year]
            self.assertEqual(read_csv(path), expected,
                             f"data/classes_{year}.csv が古い。"
                             f"python scripts/export_classes.py で再生成する")
            checked += 1
        self.assertGreater(checked, 0, "コミット済みの CSV が 1 つも無い")

    def test_default_output_is_split_per_year(self):
        """年度を混ぜた 1 枚にしない（どの年度の行か見分けづらく、差分も取りにくい）"""
        years = sorted({r["年度"] for r in self.rows})
        for year in years:
            path = ROOT / "data" / f"classes_{year}.csv"
            if path.exists():
                self.assertEqual({r["年度"] for r in read_csv(path)}, {year},
                                 f"classes_{year}.csv に他の年度が混ざっている")


if __name__ == "__main__":
    unittest.main()
